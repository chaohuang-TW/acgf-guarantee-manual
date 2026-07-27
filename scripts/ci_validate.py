#!/usr/bin/env python3
"""Single build-and-validation entry point used locally and by every workflow."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = Path("/tmp/search-index-before.json")


def run(*command: str) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> None:
    current_index = ROOT / "site/assets/data/search-index.json"
    if current_index.is_file():
        shutil.copy2(current_index, BASELINE)
    python = sys.executable
    node = os.environ.get("NODE_BINARY") or shutil.which("node")
    if not node:
        raise RuntimeError("Node.js is required for the search logic test")
    install = [python, "-m", "playwright", "install"]
    if os.environ.get("CI"):
        install.append("--with-deps")
    install.append("chromium")
    run(*install)
    run(python, "scripts/build_site.py")
    for script in [
        "audit_content.py",
        "audit_reading_units.py",
        "audit_source_preview_boundaries.py",
        "audit_full_manual_boundaries.py",
        "audit_search_quality.py",
        "audit_search_context.py",
        "audit_search_targets.py",
        "validate_page_rendering.py",
        "validate_site.py",
    ]:
        run(python, f"scripts/{script}")
    run(node, "tests/test_search_logic.js")
    run(python, "scripts/e2e_reading_units.py")
    print("CI VALIDATION PASSED")


if __name__ == "__main__":
    main()
