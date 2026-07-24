#!/usr/bin/env python3
"""Validate source-page search records resolve to their complete reading target."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
INDEX = json.loads((SITE / "assets/data/search-index.json").read_text(encoding="utf-8"))


def page_html(relative_url: str) -> str:
    path = SITE / relative_url
    assert path.is_file(), f"Missing reading target: {relative_url}"
    return path.read_text(encoding="utf-8")


def main() -> None:
    assert len(INDEX) == 196
    for record in INDEX:
        reading_url = record.get("readingUrl")
        assert reading_url, f"Missing readingUrl for PDF page {record['pdfPage']}"
        html = page_html(reading_url)
        anchor = f'id="pdf-page-{record["pdfPage"]}"'
        assert anchor in html, f"Missing {anchor} in {reading_url}"

    records = {record["pdfPage"]: record for record in INDEX}
    expected = {
        5: "versions/115-04/pages/page-005.html",
        21: "versions/115-04/chapters/part-1/guarantee-application.html",
        44: "versions/115-04/chapters/part-3/subrogation-requirements.html",
        178: "versions/115-04/forms/form-25a.html",
        60: "versions/115-04/appendices/appendix-02.html",
    }
    for pdf_page, reading_url in expected.items():
        assert records[pdf_page]["readingUrl"] == reading_url

    subrogation = page_html(records[44]["readingUrl"])
    assert 'id="pdf-page-44"' in subrogation and 'id="pdf-page-45"' in subrogation
    assert records[5]["readingUrl"] == records[5]["url"]
    print(f"SEARCH TARGET AUDIT PASSED: {len(INDEX)} reading targets and anchors")


if __name__ == "__main__":
    main()
