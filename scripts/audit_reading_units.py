#!/usr/bin/env python3
"""Audit logical reading-unit boundaries and generated section pages."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

from display_text import non_whitespace_characters
from reading_units import load_resolved_units, marker_text

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
PAGES = {
    int(page["pdfPage"]): page
    for page in json.loads((ROOT / "data/pages.json").read_text(encoding="utf-8"))
}
TOC = json.loads((ROOT / "data/toc.json").read_text(encoding="utf-8"))


def visible_text(relative: str) -> str:
    return html.unescape((SITE / relative).read_text(encoding="utf-8"))


def main() -> None:
    units = load_resolved_units()
    toc_sections = [section for part in TOC["parts"] for section in part["sections"]]
    assert len(units) == len(toc_sections) == 16
    assert {unit["id"] for unit in units} == {section["id"] for section in toc_sections}

    fragments_by_pdf: dict[int, list[tuple[dict, dict]]] = {}
    for unit in units:
        assert unit["startPdfPage"] <= unit["endPdfPage"]
        assert unit["fragments"]
        target = SITE / unit["readingUrl"]
        assert target.is_file(), unit["readingUrl"]
        page_html = target.read_text(encoding="utf-8")
        assert len(re.findall(r"<h1(?:\s|>)", page_html)) == 1
        assert not re.search(r"手冊頁\s*(\d+)\s*[-–]\s*(\d+)", page_html) or all(
            int(start) <= int(end)
            for start, end in re.findall(r"手冊頁\s*(\d+)\s*[-–]\s*(\d+)", page_html)
        )
        for fragment in unit["fragments"]:
            source = PAGES[fragment["pdfPage"]]["text"]
            assert source[fragment["startOffset"]:fragment["endOffset"]] == fragment["text"]
            assert non_whitespace_characters(fragment["text"]) in non_whitespace_characters(source)
            assert f'id="pdf-page-{fragment["pdfPage"]}"' in page_html
            fragments_by_pdf.setdefault(fragment["pdfPage"], []).append((unit, fragment))

    for pdf_page in range(9, 55):
        fragments = sorted(fragments_by_pdf[pdf_page], key=lambda item: item[1]["startOffset"])
        assert fragments, f"Missing chapter fragments for PDF {pdf_page}"
        for (_, left), (_, right) in zip(fragments, fragments[1:]):
            assert left["endOffset"] == right["startOffset"], f"Gap or overlap on PDF {pdf_page}"
        source = PAGES[pdf_page]["text"]
        start = fragments[0][1]["startOffset"]
        end = fragments[-1][1]["endOffset"]
        combined = "".join(fragment["text"] for _, fragment in fragments)
        assert non_whitespace_characters(combined) == non_whitespace_characters(source[start:end])

    shared = {pdf: items for pdf, items in fragments_by_pdf.items() if len(items) > 1}
    assert set(shared) == {32, 43, 46}
    assert [item[0]["id"] for item in shared[46]] == [
        "subrogation-requirements",
        "subrogation-scope",
        "subrogation-documents",
    ]

    unit_text = {
        unit["id"]: "".join(fragment["text"] for fragment in unit["fragments"])
        for unit in units
    }
    changes = unit_text["guarantee-changes"]
    termination = unit_text["guarantee-termination"]
    requirements = unit_text["subrogation-requirements"]
    scope = unit_text["subrogation-scope"]
    documents = unit_text["subrogation-documents"]
    physical_46 = visible_text("versions/115-04/pages/page-046.html")
    changes, termination, requirements, scope, documents = map(
        marker_text, [changes, termination, requirements, scope, documents]
    )
    assert "內容變更事項" in changes and "貳、終止保證之處理" not in changes
    assert "貳、終止保證之處理" in termination and "內容變更事項" not in termination
    assert "構評估認為無執行實益" in requirements and "貳、代位清償範圍" not in requirements
    assert "代償利息之計算方式" in scope and "參、代位清償應檢送文件" not in scope
    assert "參、代位清償應檢送文件" in documents and "代償利息之計算方式" not in documents
    for marker in ["構評估認為無執行實益", "貳、代位清償範圍", "參、代位清償應檢送文件"]:
        assert marker in physical_46
    assert "24-23" not in visible_text("versions/115-04/chapters/part-2/guarantee-changes.html")
    assert "38-37" not in visible_text("versions/115-04/chapters/part-3/subrogation-scope.html")
    print(f"READING UNIT AUDIT PASSED: {len(units)} units; {len(shared)} shared physical pages")


if __name__ == "__main__":
    main()
