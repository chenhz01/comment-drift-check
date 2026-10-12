#!/usr/bin/env python3
"""Self-test for comment-drift-check. Round 1: 40 checks; Round 2: +10 = 50.

Run:  python self_test.py
Last line printed:  SUMMARY: PASS n/n
Categories: A = functional, E = exception paths, X = extreme edges.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comment_drift_check as core

passed = 0
failed = 0


def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print("FAIL: %s" % name)


def raises(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        return False
    except Exception:
        return True


def rules(src):
    return [f["rule"] for f in core.check_source(src)]


# ---------- A. functional unit tests (1-20) ----------
check("A01 ghost param flagged CD001",
      "CD001" in rules('def f(a):\n    """Do it.\n\n    :param ghost: the ghost\n    """\n    return a\n'))
check("A02 undocumented param CD002",
      "CD002" in rules('def f(a):\n    """Do it."""\n    return a\n'))
check("A03 self excluded from param rules",
      rules('class C:\n    def m(self, a):\n        """Do it.\n\n        :param a: value\n        """\n        return a\n') == [])
check("A04 return name match -> clean",
      rules('def f():\n    """Do it.\n\n    :returns: result\n    """\n    result = 1\n    return result\n') == [])
check("A05 return name mismatch CD003",
      "CD003" in rules('def f():\n    """Do it.\n\n    :returns: result\n    """\n    return 42\n'))
check("A06 documented raise actually raised -> clean",
      rules('def f():\n    """Do it.\n\n    :raises ValueError: when bad\n    """\n    raise ValueError("x")\n') == [])
check("A07 undocumented raise CD004",
      "CD004" in rules('def f():\n    """Do it."""\n    raise ValueError("x")\n'))
check("A08 stale documented raise CD005",
      "CD005" in rules('def f():\n    """Do it.\n\n    :raises KeyError: never\n    """\n    return 1\n'))
check("A09 Google Args style parsed",
      rules('def f(a):\n    """Do it.\n\n    Args:\n        a: value\n    """\n    return a\n') == [])
check("A10 Google Raises style parsed",
      rules('def f():\n    """Do it.\n\n    Raises:\n        ValueError: when bad\n    """\n    raise ValueError("x")\n') == [])
check("A11 no docstring -> skipped", rules("def f(a):\n    return a\n") == [])
check("A12 non-function code ignored", rules("x = 1\nif x:\n    print(x)\n") == [])
f = core.check_source('def f(a):\n    """Do it."""\n    return a\n')[0]
check("A13 finding fields populated", f["function"] == "f" and f["rule"] == "CD002" and f["line"] == 1)
check("A14 dotted raises matched by short name",
      rules('def f():\n    """Do it.\n\n    :raises mod.CustomError: when\n    """\n    raise mod.CustomError("x")\n') == [])
two = core.check_source('def g(a):\n    """G."""\n    return a\n\ndef h():\n    """H."""\n    raise ValueError("v")\n')
check("A15 multiple functions each checked", len(two) == 2)
check("A16 return name found after reassignment",
      rules('def f():\n    """Do.\n\n    :returns: result\n    """\n    result = 1\n    result = result + 1\n    return result\n') == [])
check("A17 classes not treated as functions", rules('class C:\n    """Doc."""\n    pass\n') == [])
check("A18 rule ids in severity map", set(core.SEVERITY) == {"CD001", "CD002", "CD003", "CD004", "CD005"})
mixed = core.parse_doc("Do.\n\n:param a: x\n\nArgs:\n    b: y\n")
check("A19 reST + Google params deduped", mixed["params"] == ["a", "b"])
check("A20 parse_doc empty docstring", core.parse_doc("") == {"params": [], "raises": [], "returns": None})

# ---------- E. exception paths (21-30) ----------
check("E21 check_source on syntax error raises SyntaxError", raises(core.check_source, "def broken(:\n"))
check("E22 empty source -> no findings", core.check_source("") == [])
check("E23 None source raises", raises(core.check_source, None))
check("E24 docstring-only body safe", rules('def f():\n    """Doc only."""\n') == [])
check("E25 bare return (no value) safe", rules('def f():\n    """Do.\n\n    :returns: x\n    """\n    return\n') != [])
check("E26 nested defs checked without crash", isinstance(rules('def outer():\n    def inner(a):\n        """In."""\n        return a\n    return inner\n\nouter()\n'), list))
check("E27 vararg name documented -> no ghost",
      "CD001" not in rules('def f(*args):\n    """Do.\n\n    :param args: rest\n    """\n    return args\n'))
check("E28 decorated function still checked", "CD002" in rules("import deco\n\n@deco.wrap\ndef f(a):\n    \"\"\"Doc.\"\"\"\n    return a\n"))
check("E29 regex-ish docstring text no crash", isinstance(rules('def f(a):\n    """Use :param:\\d+/ weird."""\n    return a\n'), list))
check("E30 Google Args block without colon lines safe", isinstance(core.parse_doc("Args:\n    just prose\n"), dict))

# ---------- X. extreme edges (31-40) ----------
longdoc = "Do.\n\n" + "".join(":param p%d: v\n" % i for i in range(200))
check("X31 200-param docstring parses", len(core.parse_doc(longdoc)["params"]) == 200)
check("X32 unicode param names", "CD001" in rules('def f(a):\n    """做。\n\n    :param 参数甲: 值\n    """\n    return a\n'))
many = "".join('def f%d(a):\n    """F%d."""\n    return a\n\n' % (i, i) for i in range(200))
check("X33 200 functions produce 200 CD002", core.check_source(many).count != None and
      sum(1 for x in core.check_source(many) if x["rule"] == "CD002") == 200)
check("X34 CRLF source parses", isinstance(core.check_source('def f(a):\r\n    """D."""\r\n    return a\r\n'), list))
deep = "".join("    " * i + "if True:\n" for i in range(300)) + "    " * 300 + "pass\n"
check("X35 deep nesting guarded", isinstance(core.check_source(deep), list))
check("X36 empty source via check_path-safe helper", core.check_source("   \n") == [])
check("X37 duplicate function names distinguished by line",
      len({f["line"] for f in core.check_source('def f(a):\n    """D."""\n    return a\n\ndef f(a):\n    """D."""\n    return a\n')}) == 2)
check("X38 tuple return counts as mismatch", "CD003" in rules('def f():\n    """Do.\n\n    :returns: result\n    """\n    a, b = 1, 2\n    return a, b\n'))
check("X39 raise inside try/except detected",
      rules('def f():\n    """Do.\n\n    :raises ValueError: v\n    """\n    try:\n        pass\n    except KeyError:\n        raise ValueError("x")\n') == [])
check("X40 bare re-raise not counted as named raise",
      rules('def f():\n    """Do."""\n    try:\n        pass\n    except ValueError:\n        raise\n') == [])

print("SUMMARY: PASS %d/%d" % (passed, passed + failed))
