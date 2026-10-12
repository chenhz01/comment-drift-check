#!/usr/bin/env python3
"""comment-drift-check: docstring-vs-code consistency rules.

Rules (per function, docstring-declared claims vs AST reality):
  CD001 ghost-param         docstring documents a parameter the signature lacks
  CD002 undocumented-param  signature parameter missing from docstring (info)
  CD003 return-drift        documented return name is never returned
  CD004 undocumented-raise  code raises X, docstring does not mention it (info)
  CD005 stale-raise         docstring documents a raise the code never raises
Supports reST (:param x:) and Google (Args:/Returns:/Raises:) docstring styles.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys

__version__ = "0.1.1"

SEVERITY = {"CD001": "medium", "CD002": "info", "CD003": "medium",
            "CD004": "info", "CD005": "medium"}

_RE_PARAM = re.compile(r":param(?:eter)?\s+(\w+)\s*:")
_RE_RET = re.compile(r":returns?\s*:\s*(\w+)")
_RE_RAISE = re.compile(r":raises?\s+([\w.]+)\s*:")
_RE_GOOGLE_ITEM = re.compile(r"^\(?([\w*]+)\)?(?:\s*\([^)]*\))?\s*:")
_TYPEWORDS = {"none", "bool", "str", "int", "float", "list", "dict", "tuple", "object"}


def parse_doc(doc):
    """Extract declared params / return name / raises from a docstring."""
    params, raises, ret = [], [], None
    if not doc:
        return {"params": params, "raises": raises, "returns": ret}
    section = None
    for raw in doc.splitlines():
        line = raw.strip()
        m = _RE_PARAM.search(line)
        if m and m.group(1) not in params:
            params.append(m.group(1))
        m = _RE_RAISE.search(line)
        if m and m.group(1) not in raises:
            raises.append(m.group(1))
        m = _RE_RET.search(line)
        if m:
            ret = m.group(1)
        if line in ("Args:", "Arguments:", "Parameters:"):
            section = "args"
            continue
        if line == "Returns:":
            section = "ret"
            continue
        if line == "Raises:":
            section = "raise"
            continue
        if line.startswith(":") or not line:
            continue
        m = _RE_GOOGLE_ITEM.match(line)
        if m:
            name = m.group(1).lstrip("*")
            if section == "args" and name and name not in params:
                params.append(name)
            elif section == "ret" and ret is None and name.lower() not in _TYPEWORDS:
                ret = name
            elif section == "raise" and name and name not in raises:
                raises.append(name)
    return {"params": params, "raises": raises, "returns": ret}


def _signature_params(node):
    a = node.args
    names = [p.arg for p in (getattr(a, "posonlyargs", None) or [])]
    names += [p.arg for p in a.args]
    if a.vararg:
        names.append(a.vararg.arg)
    names += [p.arg for p in a.kwonlyargs]
    if a.kwarg:
        names.append(a.kwarg.arg)
    return [n for n in names if n not in ("self", "cls")]


def _return_names(fn):
    names = set()
    for sub in ast.walk(fn):
        if isinstance(sub, ast.Return) and isinstance(sub.value, ast.Name):
            names.add(sub.value.id)
    return names


def _raise_names(fn):
    names = set()
    for sub in ast.walk(fn):
        if isinstance(sub, ast.Raise) and sub.exc is not None:
            exc = sub.exc.func if isinstance(sub.exc, ast.Call) else sub.exc
            if isinstance(exc, ast.Name):
                names.add(exc.id)
            elif isinstance(exc, ast.Attribute):
                parts = []
                node = exc
                while isinstance(node, ast.Attribute):
                    parts.append(node.attr)
                    node = node.value
                if isinstance(node, ast.Name):
                    parts.append(node.id)
                names.add(".".join(reversed(parts)))
    return names


def check_source(source, filename="<string>"):
    """Return drift findings for one Python source string.
    Ordinary SyntaxError propagates to the caller; resource-style parse
    failures (over-deep indentation, recursion limits, NUL bytes) yield a
    single CD-SYNTAX finding instead of crashing."""
    try:
        tree = ast.parse(source)
    except IndentationError as exc:
        return [{"file": filename, "function": "", "line": exc.lineno or 0,
                 "rule": "CD-SYNTAX", "severity": "info",
                 "message": "source does not parse: %s" % exc.msg}]
    except ValueError as exc:
        return [{"file": filename, "function": "", "line": 0,
                 "rule": "CD-SYNTAX", "severity": "info",
                 "message": "source does not parse: %s" % exc}]
    except RecursionError:
        return [{"file": filename, "function": "", "line": 0,
                 "rule": "CD-SYNTAX", "severity": "info",
                 "message": "source too deeply nested to parse"}]
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        doc = ast.get_docstring(node)
        if not doc:
            continue
        info = parse_doc(doc)
        sig = _signature_params(node)
        base = {"file": filename, "function": node.name, "line": node.lineno}
        code_raises = _raise_names(node)
        short_code = {r.split(".")[-1] for r in code_raises}
        short_doc = {r.split(".")[-1] for r in info["raises"]}
        for p in info["params"]:
            if p not in sig:
                findings.append(dict(base, rule="CD001", severity=SEVERITY["CD001"],
                                     message="docstring documents parameter %r missing from signature" % p))
        for p in sig:
            if p not in info["params"]:
                findings.append(dict(base, rule="CD002", severity=SEVERITY["CD002"],
                                     message="parameter %r is not documented" % p))
        if info["returns"] and info["returns"] not in _return_names(node):
            findings.append(dict(base, rule="CD003", severity=SEVERITY["CD003"],
                                 message="documented return name %r is never returned" % info["returns"]))
        for r in info["raises"]:
            if r.split(".")[-1] not in short_code:
                findings.append(dict(base, rule="CD005", severity=SEVERITY["CD005"],
                                     message="docstring documents raise %r that is never raised" % r))
        for r in sorted(code_raises):
            if r.split(".")[-1] not in short_doc:
                findings.append(dict(base, rule="CD004", severity=SEVERITY["CD004"],
                                     message="raises %r without documenting it" % r))
    findings.sort(key=lambda f: (f["line"], f["rule"]))
    return findings


def check_path(path):
    """Check a .py file or a directory tree. Raises FileNotFoundError for
    missing paths; syntax errors become CD-SYNTAX findings."""
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            try:
                return check_source(fh.read(), path)
            except SyntaxError as exc:
                return [{"file": path, "function": "", "line": exc.lineno or 0,
                         "rule": "CD-SYNTAX", "severity": "info",
                         "message": "source does not parse: %s" % exc.msg}]
    if os.path.isdir(path):
        findings = []
        for root, dirs, files in os.walk(path):
            dirs.sort()
            for name in sorted(files):
                if name.endswith(".py"):
                    findings.extend(check_path(os.path.join(root, name)))
        return findings
    raise FileNotFoundError("no such file or directory: %s" % path)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="comment-drift-check", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("check", help="check a file or directory")
    p.add_argument("target")
    p.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)
    findings = check_path(args.target)
    if args.format == "json":
        print(json.dumps({"findings": findings, "count": len(findings)}, indent=2))
    else:
        for f in findings:
            print("%s:%s: %s [%s] %s: %s" % (f["file"], f["line"], f["rule"],
                                             f["severity"], f["function"], f["message"]))
        print("%d finding(s)" % len(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
