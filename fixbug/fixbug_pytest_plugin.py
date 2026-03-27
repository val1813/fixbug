#!/usr/bin/env python3
"""
pytest plugin: auto-record fixbug world-line after test run.

Install:
    pip install fixbug

Usage option 1 — per-project (recommended):
    # conftest.py
    pytest_plugins = ['fixbug.fixbug_pytest_plugin']

Usage option 2 — CLI flag:
    pytest --fixbug . tests/

The plugin calls fixbug's internal API directly (no subprocess),
so it works even if the fixbug CLI is not on PATH.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional


def pytest_addoption(parser):
    parser.addoption(
        "--fixbug",
        metavar="PROJECT_ROOT",
        default=None,
        help="Enable fixbug auto-record after test run (pass project root directory)",
    )


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    root_str: Optional[str] = config.getoption("--fixbug", default=None)
    if root_str is None:
        return

    root = Path(root_str).resolve()
    if not root.exists():
        terminalreporter.write_line(
            f"[fixbug] WARNING: project root not found: {root}", yellow=True
        )
        return

    try:
        import sys
        if str(Path(__file__).parent.parent) not in sys.path:
            sys.path.insert(0, str(Path(__file__).parent.parent))
        from fixbug._impl import WorldLineStore
    except ImportError as e:
        terminalreporter.write_line(f"[fixbug] import error: {e}", yellow=True)
        return

    store = WorldLineStore(root)
    recorded_failures = 0
    recorded_fixes = 0

    failed = terminalreporter.stats.get("failed", [])
    passed = terminalreporter.stats.get("passed", [])

    for report in failed:
        # nodeid like "tests/test_foo.py::TestClass::test_bar"
        node_id = _nodeid_to_module(report.nodeid, root)
        detail = ""
        if hasattr(report, "longreprtext"):
            detail = str(report.longreprtext)[:300]
        elif hasattr(report, "longrepr") and report.longrepr:
            detail = str(report.longrepr)[:300]
        store.record_failure(node_id, detail)
        recorded_failures += 1

    for report in passed:
        node_id = _nodeid_to_module(report.nodeid, root)
        store.record_fix(node_id)
        recorded_fixes += 1

    if recorded_failures or recorded_fixes:
        terminalreporter.write_line(
            f"[fixbug] recorded {recorded_failures} failure(s), "
            f"{recorded_fixes} fix(es) into world-line"
        )


def _nodeid_to_module(nodeid: str, root: Path) -> str:
    """Convert pytest nodeid to dot-separated module name relative to root."""
    # nodeid: "tests/test_foo.py::TestClass::test_bar"
    file_part = nodeid.split("::")[0]  # "tests/test_foo.py"
    p = Path(file_part)
    # Strip .py suffix
    parts = list(p.parts)
    if parts and parts[-1].endswith(".py"):
        parts[-1] = parts[-1][:-3]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) if parts else p.stem
