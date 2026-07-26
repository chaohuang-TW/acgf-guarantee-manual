#!/usr/bin/env python3
"""Resolve verified logical reading units from physical PDF page text."""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def marker_text(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKC", value)
        if not character.isspace()
    )


def normalized_with_offsets(value: str) -> tuple[str, list[int]]:
    normalized: list[str] = []
    offsets: list[int] = []
    for raw_offset, raw_character in enumerate(value):
        for character in unicodedata.normalize("NFKC", raw_character):
            if character.isspace():
                continue
            normalized.append(character)
            offsets.append(raw_offset)
    return "".join(normalized), offsets


def marker_offset(raw_text: str, marker: str, *, after: bool = False) -> int:
    normalized, offsets = normalized_with_offsets(raw_text)
    needle = marker_text(marker)
    matches: list[int] = []
    start = 0
    while True:
        position = normalized.find(needle, start)
        if position < 0:
            break
        matches.append(position)
        start = position + 1
    if len(matches) != 1:
        raise ValueError(f"Marker must occur exactly once in constrained page: {marker!r}; found {len(matches)}")
    position = matches[0] + (len(needle) - 1 if after else 0)
    raw_offset = offsets[position]
    return raw_offset + (1 if after else 0)


def load_resolved_units() -> list[dict]:
    source = json.loads((ROOT / "data/reading-units.json").read_text(encoding="utf-8"))
    pages = {
        int(page["pdfPage"]): page
        for page in json.loads((ROOT / "data/pages.json").read_text(encoding="utf-8"))
    }
    units: list[dict] = []
    for item in source["units"]:
        unit = dict(item)
        fragments: list[dict] = []
        for pdf_page in range(unit["startPdfPage"], unit["endPdfPage"] + 1):
            page = pages[pdf_page]
            raw_text = page["text"]
            start = marker_offset(raw_text, unit["startMarker"]) if pdf_page == unit["startPdfPage"] else 0
            end = (
                marker_offset(raw_text, unit["endBeforeMarker"])
                if pdf_page == unit["endPdfPage"] and unit.get("endBeforeMarker")
                else len(raw_text)
            )
            if end <= start:
                raise ValueError(f"Empty or reversed reading fragment: {unit['id']} PDF {pdf_page}")
            text = raw_text[start:end]
            if not text.strip():
                raise ValueError(f"Empty reading fragment: {unit['id']} PDF {pdf_page}")
            fragments.append({
                "pdfPage": pdf_page,
                "printedPage": page["printedPage"],
                "startOffset": start,
                "endOffset": end,
                "text": text,
            })
        unit["fragments"] = fragments
        units.append(unit)
    return units


def units_by_pdf(units: list[dict]) -> dict[int, list[dict]]:
    result: dict[int, list[dict]] = {}
    for unit in units:
        for fragment in unit["fragments"]:
            result.setdefault(fragment["pdfPage"], []).append({
                "id": unit["id"],
                "partId": unit["partId"],
                "title": unit["title"],
                "breadcrumb": [
                    next(
                        part["title"]
                        for part in json.loads((ROOT / "data/toc.json").read_text(encoding="utf-8"))["parts"]
                        if part["id"] == unit["partId"]
                    ),
                    unit["title"],
                ],
                "scope": unit["scope"],
                "readingUrl": unit["readingUrl"],
                "startOffset": fragment["startOffset"],
                "endOffset": fragment["endOffset"],
                "text": fragment["text"],
            })
    return result
