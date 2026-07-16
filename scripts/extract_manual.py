#!/usr/bin/env python3
"""Extract the PDF text layer without OCR or editorial rewriting."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "source" / "acgf-guarantee-manual-115-04.pdf"
PAGES_JSON = ROOT / "data" / "pages.json"
VERSION_JSON = ROOT / "data" / "version.json"
EXPECTED_PAGES = 203
FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def printed_page(text: str, pdf_page: int) -> str:
    if pdf_page < 9:
        return ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    candidate = unicodedata.normalize("NFKC", lines[0]).translate(FULLWIDTH_DIGITS)
    candidate = re.sub(r"\s+", "", candidate)
    if re.fullmatch(r"\d{1,3}", candidate):
        number = int(candidate)
        if 1 <= number <= 186:
            return str(number)
    return ""


def display_text(raw: str, printed: str) -> str:
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    if printed:
        for index, line in enumerate(lines):
            normalized = unicodedata.normalize("NFKC", line).translate(FULLWIDTH_DIGITS)
            if re.sub(r"\s+", "", normalized) == printed:
                del lines[index]
                break
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(line.rstrip() for line in lines)


def search_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def main() -> int:
    if not PDF.is_file():
        print(f"ERROR: missing source PDF: {PDF}", file=sys.stderr)
        return 1

    reader = PdfReader(str(PDF))
    if len(reader.pages) != EXPECTED_PAGES:
        print(f"ERROR: expected {EXPECTED_PAGES} pages, found {len(reader.pages)}", file=sys.stderr)
        return 1

    pages = []
    no_text_pages = []
    for index, page in enumerate(reader.pages, start=1):
        raw = page.extract_text() or ""
        printed = printed_page(raw, index)
        cleaned = display_text(raw, printed)
        has_text = bool(cleaned.strip())
        if not has_text:
            no_text_pages.append(index)
        pages.append(
            {
                "pdfPage": index,
                "printedPage": printed,
                "hasTextLayer": has_text,
                "text": cleaned,
                "searchText": search_text(cleaned),
            }
        )

    digest = sha256(PDF)
    version = {
        "id": "115-04",
        "title": "農業信用保證業務作業手冊",
        "edition": "農漁會版",
        "versionLabel": "中華民國115年4月",
        "pdfPageCount": EXPECTED_PAGES,
        "sourceFile": PDF.name,
        "sha256": digest,
        "isCurrent": True,
        "noTextLayerPages": no_text_pages,
    }
    PAGES_JSON.write_text(json.dumps(pages, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    VERSION_JSON.write_text(json.dumps(version, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Extracted {len(pages)} pages")
    print(f"SHA-256: {digest}")
    print("Pages without usable text layer: " + ", ".join(map(str, no_text_pages)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
