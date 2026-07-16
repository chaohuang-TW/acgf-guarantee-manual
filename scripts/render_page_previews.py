#!/usr/bin/env python3
"""Render only configured source-preview pages as reproducible WebP files."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image

from page_rendering import ROOT, load_page_rendering, printed_page_map


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def main() -> None:
    version = json.loads((ROOT / "data" / "version.json").read_text(encoding="utf-8"))
    config, pages, resolved = load_page_rendering()
    if config.get("version") != version["id"]:
        raise SystemExit("page-rendering version does not match data/version.json")
    source = ROOT / "source" / version["sourceFile"]
    source_sha = digest(source)
    if source_sha != version["sha256"]:
        raise SystemExit("source PDF SHA-256 mismatch")

    preview = config["preview"]
    width = int(preview["width"])
    quality = int(preview["quality"])
    if preview.get("format") != "webp":
        raise SystemExit("only WebP preview output is supported")
    output = ROOT / "assets" / "page-previews" / version["id"]
    output.mkdir(parents=True, exist_ok=True)
    target_numbers = sorted(number for number, item in resolved.items() if item["mode"] == "source-preview")
    target_names = {f"pdf-page-{number:03d}.webp" for number in target_numbers}
    for stale in output.glob("pdf-page-*.webp"):
        if stale.name not in target_names:
            stale.unlink()

    page_by_number = {int(page["pdfPage"]): page for page in pages}
    printed_by_pdf = {pdf_page: printed for printed, pdf_page in printed_page_map(pages).items()}
    document = pdfium.PdfDocument(source)
    manifest = []
    for number in target_numbers:
        pdf_page = document[number - 1]
        page_width, page_height = pdf_page.get_size()
        expected_height = round(width * page_height / page_width)
        image = pdf_page.render(scale=width / page_width, fill_color=(255, 255, 255, 255)).to_pil().convert("RGB")
        if image.size != (width, expected_height):
            image = image.resize((width, expected_height), Image.Resampling.LANCZOS)
        target = output / f"pdf-page-{number:03d}.webp"
        image.save(target, format="WEBP", quality=quality, method=6, exact=True, exif=b"")
        rendering = resolved[number]
        page_data = page_by_number[number]
        manifest.append(
            {
                "pdfPage": number,
                "printedPage": str(page_data["printedPage"] or printed_by_pdf.get(number, "")),
                "mode": "source-preview",
                "label": rendering["label"],
                "file": target.name,
                "width": image.width,
                "height": image.height,
                "sha256": digest(target),
                "sourcePdfSha256": source_sha,
                "reason": rendering["reason"],
            }
        )
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Rendered {len(manifest)} source previews to {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
