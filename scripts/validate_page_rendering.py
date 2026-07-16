#!/usr/bin/env python3
"""Validate hybrid text, source-preview, and blank-page rendering."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image
from pypdf import PdfReader

from page_rendering import ALLOWED_MODES, ROOT, expand_rule, load_page_rendering, printed_page_map

SITE = ROOT / "site"
VERSION = json.loads((ROOT / "data" / "version.json").read_text(encoding="utf-8"))
TOC = json.loads((ROOT / "data" / "toc.json").read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def page_section(document: str, pdf_page: int) -> str:
    marker = f'id="pdf-page-{pdf_page}"'
    start = document.find(marker)
    if start < 0:
        return ""
    start = document.rfind("<section", 0, start)
    end = document.find("</section>", start)
    return document[start : end + len("</section>")] if end >= 0 else ""


def human_size(value: int) -> str:
    return f"{value / 1024 / 1024:.2f} MiB"


def main() -> int:
    errors: list[str] = []
    try:
        config, pages, resolved = load_page_rendering()
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"PAGE RENDERING VALIDATION FAILED\n- {exc}")
        return 1

    if config.get("version") != "115-04" or config.get("version") != VERSION["id"]:
        errors.append("page-rendering version mismatch")
    if config.get("defaultMode") != "text":
        errors.append("defaultMode must be text")
    if config.get("preview") != {"format": "webp", "width": 1600, "quality": 86}:
        errors.append("preview settings must be WebP, 1600px, quality 86")
    rules = config.get("rules")
    if not isinstance(rules, list) or not rules:
        errors.append("rules must be a non-empty list")
        rules = []
    ids = [rule.get("id") for rule in rules]
    if len(ids) != len(set(ids)):
        errors.append("duplicate rendering rule ids")
    for rule in rules:
        if rule.get("mode") not in ALLOWED_MODES:
            errors.append(f"invalid rule mode: {rule.get('id')}")
        raw_pages = rule.get("pdfPages", [])
        if len(raw_pages) != len(set(raw_pages)):
            errors.append(f"duplicate PDF page in rule: {rule.get('id')}")
        try:
            expanded = expand_rule(rule, pages)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if any(number < 1 or number > VERSION["pdfPageCount"] for number in expanded):
            errors.append(f"PDF page out of range in rule: {rule.get('id')}")

    modes = {mode: sorted(number for number, item in resolved.items() if item["mode"] == mode) for mode in ALLOWED_MODES}
    preview_pages = modes["source-preview"]
    blank_pages = modes["blank-page"]
    text_pages = modes["text"]
    if set(preview_pages) & set(blank_pages):
        errors.append("a page is both source-preview and blank-page")
    if not {2, 4}.issubset(blank_pages):
        errors.append("PDF pages 2 and 4 must be blank-page")
    no_text = {int(page["pdfPage"]) for page in pages if not page["hasTextLayer"]}
    if not no_text.issubset(set(preview_pages) | set(blank_pages)):
        errors.append("an image-only page is not source-preview or blank-page")

    source_pdf = ROOT / "source" / VERSION["sourceFile"]
    download_pdf = SITE / "downloads" / VERSION["sourceFile"]
    if len(PdfReader(str(source_pdf)).pages) != 203:
        errors.append("source PDF page count is not 203")
    if digest(source_pdf) != VERSION["sha256"]:
        errors.append("source PDF SHA-256 mismatch")
    if not download_pdf.is_file() or digest(download_pdf) != VERSION["sha256"]:
        errors.append("download PDF SHA-256 mismatch")

    source_dir = ROOT / "assets" / "page-previews" / VERSION["id"]
    site_dir = SITE / "assets" / "page-previews" / VERSION["id"]
    manifest_path = source_dir / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"invalid preview manifest: {exc}")
        manifest = []
    manifest_numbers = [int(item.get("pdfPage", 0)) for item in manifest]
    if manifest_numbers != sorted(preview_pages) or len(manifest_numbers) != len(set(manifest_numbers)):
        errors.append("manifest pages do not exactly match sorted source-preview pages")
    pdf_document = pdfium.PdfDocument(source_pdf)
    printed_by_pdf = {pdf_page: printed for printed, pdf_page in printed_page_map(pages).items()}
    preview_sizes: list[int] = []
    for item in manifest:
        number = int(item.get("pdfPage", 0))
        filename = item.get("file", "")
        if filename != f"pdf-page-{number:03d}.webp" or Path(filename).name != filename:
            errors.append(f"invalid manifest filename for PDF page {number}")
            continue
        page_data = next(page for page in pages if int(page["pdfPage"]) == number)
        expected_printed = str(page_data["printedPage"] or printed_by_pdf.get(number, ""))
        rendering = resolved[number]
        if item.get("printedPage") != expected_printed or item.get("mode") != "source-preview":
            errors.append(f"manifest page metadata mismatch for PDF page {number}")
        if item.get("label") != rendering["label"] or item.get("reason") != rendering["reason"]:
            errors.append(f"manifest rendering metadata mismatch for PDF page {number}")
        source_image = source_dir / filename
        site_image = site_dir / filename
        if not source_image.is_file() or not site_image.is_file():
            errors.append(f"missing source or site preview for PDF page {number}")
            continue
        if source_image.read_bytes() != site_image.read_bytes():
            errors.append(f"source/site preview differs for PDF page {number}")
        if digest(source_image) != item.get("sha256"):
            errors.append(f"manifest SHA mismatch for PDF page {number}")
        if item.get("sourcePdfSha256") != VERSION["sha256"]:
            errors.append(f"manifest source SHA mismatch for PDF page {number}")
        try:
            with Image.open(source_image) as image:
                width, height = image.size
                if image.format != "WEBP" or width != 1600:
                    errors.append(f"invalid image format or width for PDF page {number}")
                if (width, height) != (item.get("width"), item.get("height")) or height <= 0:
                    errors.append(f"manifest dimensions mismatch for PDF page {number}")
                pdf_width, pdf_height = pdf_document[number - 1].get_size()
                image_ratio = width / height
                pdf_ratio = pdf_width / pdf_height
                ratio_error = abs(image_ratio - pdf_ratio) / pdf_ratio
                if ratio_error >= 0.005:
                    errors.append(f"preview aspect ratio differs by 0.5% or more for PDF page {number}")
        except OSError as exc:
            errors.append(f"invalid WebP for PDF page {number}: {exc}")
        preview_sizes.append(source_image.stat().st_size)
        if source_image.stat().st_size > 1.5 * 1024 * 1024:
            errors.append(f"preview exceeds 1.5 MiB for PDF page {number}")
    stray = sorted(path.name for path in source_dir.glob("pdf-page-*.webp") if path.name not in {item.get("file") for item in manifest})
    if stray:
        errors.append(f"unconfigured preview files: {stray}")
    for number in blank_pages:
        if (source_dir / f"pdf-page-{number:03d}.webp").exists():
            errors.append(f"blank page has an image: {number}")

    for number, rendering in resolved.items():
        html_path = SITE / f"versions/{VERSION['id']}/pages/page-{number:03d}.html"
        if not html_path.is_file():
            errors.append(f"physical page HTML missing: {number}")
            continue
        section = page_section(html_path.read_text(encoding="utf-8"), number)
        if not section:
            errors.append(f"page card missing: {number}")
            continue
        mode = rendering["mode"]
        has_text = bool(next(page for page in pages if int(page["pdfPage"]) == number)["hasTextLayer"])
        if mode == "source-preview":
            for token in ('<figure class="source-preview">', '<img class="source-preview-image"', "<figcaption>", f"#page={number}"):
                if token not in section:
                    errors.append(f"source-preview HTML missing {token}: {number}")
            has_details = '<details class="extracted-text-details">' in section
            if has_text != has_details:
                errors.append(f"source-preview details mismatch: {number}")
            if '<pre class="source-text">' in section:
                errors.append(f"source-preview exposes primary source text: {number}")
        elif mode == "blank-page":
            if 'class="blank-source-page"' not in section or "source-preview-image" in section:
                errors.append(f"invalid blank-page HTML: {number}")
        elif '<pre class="source-text">' not in section or "source-preview-image" in section:
            errors.append(f"invalid text-mode HTML: {number}")

    html_files = sorted(SITE.rglob("*.html"))
    for html_path in html_files:
        document = html_path.read_text(encoding="utf-8")
        if re.search(r"<(iframe|canvas)\b", document, re.I):
            errors.append(f"iframe or canvas found: {html_path.relative_to(SITE)}")
        for image_tag in re.findall(r"<img\b[^>]*>", document, re.I):
            for attribute in ("alt", "width", "height", "loading"):
                if not re.search(rf"\b{attribute}=", image_tag):
                    errors.append(f"image missing {attribute}: {html_path.relative_to(SITE)}")
            if 'loading="lazy"' not in image_tag:
                errors.append(f"image is not lazy-loaded: {html_path.relative_to(SITE)}")
            source_match = re.search(r'\bsrc="([^"]+)"', image_tag)
            if source_match and re.match(r"(?:https?:)?//|data:", source_match.group(1)):
                errors.append(f"external or embedded image: {html_path.relative_to(SITE)}")

    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    for forbidden in ("tesseract", "easyocr", "openai", "anthropic", "tensorflow", "torch"):
        if forbidden in requirements:
            errors.append(f"forbidden OCR or AI dependency: {forbidden}")
    if len(TOC.get("parts", [])) != 4 or len(TOC.get("appendices", [])) != 18:
        errors.append("TOC main part or appendix count mismatch")
    if len(TOC.get("forms", [])) != 37 or len(TOC.get("specialForms", [])) != 7:
        errors.append("TOC form count mismatch")

    search_path = SITE / "assets" / "data" / "search-index.json"
    search = json.loads(search_path.read_text(encoding="utf-8")) if search_path.is_file() else []
    if len(search) != 196:
        errors.append("search index count is not 196")
    baseline = Path("/tmp/search-index-before.json")
    if baseline.is_file() and baseline.read_bytes() != search_path.read_bytes():
        errors.append("search index differs from pre-build baseline")

    total = sum(preview_sizes)
    largest = max(preview_sizes, default=0)
    average = round(total / len(preview_sizes)) if preview_sizes else 0
    if errors:
        print("PAGE RENDERING VALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PAGE RENDERING VALIDATION PASSED")
    print(f"- Text mode pages: {len(text_pages)}")
    print(f"- Source-preview pages: {len(preview_pages)}")
    print(f"- Blank-page pages: {len(blank_pages)}")
    print(f"- Preview image total: {human_size(total)} ({total} bytes)")
    print(f"- Largest preview: {human_size(largest)} ({largest} bytes)")
    print(f"- Average preview: {human_size(average)} ({average} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
