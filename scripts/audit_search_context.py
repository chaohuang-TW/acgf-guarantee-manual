#!/usr/bin/env python3
"""Validate bounded, source-derived cross-page search context."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = json.loads((ROOT / "site/assets/data/search-index.json").read_text(encoding="utf-8"))
PAGES = {item["pdfPage"]: item for item in json.loads((ROOT / "data/pages.json").read_text(encoding="utf-8"))}
CASES = [
    (22, 21, "chapter", "同意者，不在此限"),
    (38, 37, "chapter", "之責"),
    (49, 48, "chapter", "如有第二款"),
    (60, 59, "appendix", "請人及其同一經濟利害關係人"),
    (61, 60, "appendix", "六成，一般農業貸款"),
    (63, 62, "appendix", "用卡）或保證債務"),
    (67, 66, "appendix", "三、保證人"),
    (79, 78, "appendix", "但有特殊情形"),
]


def main() -> None:
    assert len(INDEX) == 196
    indexed = {item["pdfPage"]: item for item in INDEX}
    contextual = [item for item in INDEX if "contextStartPdfPage" in item]
    assert contextual
    for item in contextual:
        assert item["type"] in {"chapter", "appendix"}
        assert item["scope"] != "appendix:appendix-18"
        assert item["contextStartPdfPage"] <= item["pdfPage"] <= item["contextEndPdfPage"]
        for pdf in range(item["contextStartPdfPage"], item["contextEndPdfPage"] + 1):
            related = indexed[pdf]
            assert related["scope"] == item["scope"] and related["type"] == item["type"]
            assert PAGES[pdf]["hasTextLayer"]
    for pdf, previous, kind, marker in CASES:
        record = indexed[pdf]
        assert record["type"] == kind
        assert record["contextStartPdfPage"] == previous
        assert record.get("contextBefore") and PAGES[previous]["hasTextLayer"]
    for item in INDEX:
        if item["type"] in {"form", "lookup-table", "front-matter"}:
            assert "contextBefore" not in item and "contextAfter" not in item
    print(f"SEARCH CONTEXT AUDIT PASSED: {len(CASES)} real cross-page cases; {len(contextual)} contextual records")


if __name__ == "__main__":
    main()
