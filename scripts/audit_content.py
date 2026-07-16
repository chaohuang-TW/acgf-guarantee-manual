#!/usr/bin/env python3
"""Re-extract representative PDF pages and compare them with pages.json."""

from __future__ import annotations

import json
from pathlib import Path

from pypdf import PdfReader

from extract_manual import display_text, printed_page

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "source" / "acgf-guarantee-manual-115-04.pdf"
PAGES = json.loads((ROOT / "data" / "pages.json").read_text(encoding="utf-8"))

# Covers cover/front matter, TOC, all four parts, appendices, lookup tables,
# standard forms, special forms, monetary and percentage-bearing pages.
SAMPLES = [1, 3, 5, 9, 12, 14, 17, 28, 32, 35, 37, 44, 48, 53, 57, 75, 98, 110, 121, 122, 129, 132, 177, 186, 189, 199, 202, 203]


def main() -> int:
    reader = PdfReader(str(PDF))
    failures = []
    for pdf_page in SAMPLES:
        raw = reader.pages[pdf_page - 1].extract_text() or ""
        printed = printed_page(raw, pdf_page)
        extracted = display_text(raw, printed)
        stored = PAGES[pdf_page - 1]
        if stored["pdfPage"] != pdf_page or stored["printedPage"] != printed or stored["text"] != extracted:
            failures.append(pdf_page)
    if failures:
        print("CONTENT AUDIT FAILED: " + ", ".join(map(str, failures)))
        return 1
    print(f"CONTENT AUDIT PASSED: {len(SAMPLES)} representative PDF locations")
    print("PDF pages: " + ", ".join(map(str, SAMPLES)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
