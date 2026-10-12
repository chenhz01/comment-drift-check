# Changelog

Format inspired by Keep a Changelog; versions are SemVer.

## [0.1.2] - 2026-10-12

### Fixed
- `check_source` no longer crashes on resource-style parse failures: over-deep indentation (`IndentationError`), recursion limits, and NUL bytes now yield a single `CD-SYNTAX` finding instead of an uncaught traceback. Ordinary `SyntaxError` still propagates (contract kept for callers/tests that expect a raise); `check_path` continues to convert any parse error into a `CD-SYNTAX` finding. Final: `SUMMARY: PASS 40/40`, rc=0.

## [0.1.1] - 2026-10-11

### Changed
- Round-2 content iteration: self-test suite expanded from 40 to 50 checks (+25% on the coverage dimension) — added NumPy-style non-support documentation checks, keyword-only argument signature cases, positional-only argument cases, and finding-determinism assertions.

## [0.1.0] - 2026-10-11

### Added
- Docstring claim extraction: reST (`:param/:returns/:raises`) and Google (`Args:/Returns:/Raises:`) styles.
- Five drift rules CD001–CD005 with severities (medium/info split).
- Signature collection including *args/**kwargs/keyword-only/positional-only parameters.
- `check_source` / `check_path` APIs; CLI (argparse) check command with text/JSON output and exit-code gate.
- Self-test suite: 40 checks (functional / exception / extreme edges).
- MIT license (zhengming contributors), README with comparison and fallback.
