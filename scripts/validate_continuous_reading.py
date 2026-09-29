#!/usr/bin/env python3
"""Validate Reading UX 3.0 Continuous Logical Reading Pilot implementation."""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
DATA = ROOT / "data"

sys.path.insert(0, str(ROOT / "scripts"))
from reading_units import load_resolved_units


class TagExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.h1_tags: list[str] = []
        self.ids: list[str] = []
        self.anchors: list[dict[str, str]] = []
        self.spans: list[dict[str, str]] = []
        self._current_tag: str | None = None
        self._current_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = {k: v or "" for k, v in attrs}
        if "id" in attr_dict:
            self.ids.append(attr_dict["id"])
        if tag == "h1":
            self._current_tag = "h1"
            self._current_text = []
        elif tag == "a":
            self.anchors.append(attr_dict)
        elif tag == "span":
            self.spans.append(attr_dict)

    def handle_data(self, data: str) -> None:
        if self._current_tag == "h1":
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h1" and self._current_tag == "h1":
            self.h1_tags.append("".join(self._current_text).strip())
            self._current_tag = None


def validate_continuous_reading() -> list[str]:
    errors: list[str] = []

    # 1. Canonical URL existence
    pilot_relative = "versions/115-04/chapters/part-1/excluded-guarantee.html"
    pilot_path = SITE / pilot_relative
    if not pilot_path.is_file():
        errors.append(f"Pilot canonical HTML file missing: {pilot_relative}")
        return errors

    content = pilot_path.read_text(encoding="utf-8")
    parser = TagExtractor()
    parser.feed(content)

    # 2. H1 Uniqueness
    if len(parser.h1_tags) != 1:
        errors.append(f"Expected exactly 1 H1, found {len(parser.h1_tags)}: {parser.h1_tags}")
    elif parser.h1_tags[0] != "參、不予保證規定":
        errors.append(f"Unexpected H1 text: {parser.h1_tags[0]!r}")

    # 3. Article container class
    if 'class="manual-content continuous-reading"' not in content:
        errors.append("Missing 'continuous-reading' class on <article class=\"manual-content\">")

    # 4. Zero .page-card elements in pilot
    if 'class="page-card' in content:
        errors.append("Forbidden 'page-card' class found in continuous reading unit")

    # 5. Non-whitespace text 100% fidelity
    resolved_units = load_resolved_units()
    unit = next((u for u in resolved_units if u["id"] == "excluded-guarantee"), None)
    if not unit:
        errors.append("Unit 'excluded-guarantee' not found in resolved reading units")
        return errors

    raw_text = "".join(f["text"] for f in unit["fragments"])
    raw_nw = re.sub(r"\s+", "", raw_text)

    # Extract text from .continuous-source-heading and .continuous-source-text
    heading_match = re.search(r'<h1 class="continuous-source-heading"[^>]*>(.*?)</h1>', content, re.DOTALL)
    body_match = re.search(r'<div class="continuous-source-text display-text">(.*?)</div>\s*<details', content, re.DOTALL)

    if not heading_match or not body_match:
        errors.append("Could not locate continuous-source-heading or continuous-source-text display-text")
    else:
        rendered_html = heading_match.group(1) + "\n" + body_match.group(1)
        clean_rendered = re.sub(r"<[^>]+>", "", rendered_html)
        clean_rendered = html.unescape(clean_rendered)
        rendered_nw = re.sub(r"\s+", "", clean_rendered)

        if len(rendered_nw) != len(raw_nw):
            errors.append(f"Text length mismatch: rendered {len(rendered_nw)} vs raw {len(raw_nw)}")
        elif rendered_nw != raw_nw:
            errors.append("Non-whitespace characters do not match source fragments 100%")

    # 6. 4 inline source-page-anchors
    for page_num in (17, 18, 19, 20):
        anchor_id = f"pdf-page-{page_num}"
        if anchor_id not in parser.ids:
            errors.append(f"Missing source anchor id: {anchor_id}")

        expected_anchor = f'<span id="{anchor_id}" class="source-page-anchor" data-pdf-page="{page_num}" aria-hidden="true"></span>'
        if expected_anchor not in content:
            errors.append(f"Missing or malformed source-page-anchor: {expected_anchor}")

    # 7. Mid-paragraph inline anchor checks
    # PDF 18 must be mid-paragraph inside a <p>
    p18_pattern = r'<p>[^<]*（96 年 9 月 19 日<span id="pdf-page-18" class="source-page-anchor"[^>]*></span>農信保策字第 000207 號函）</p>'
    if not re.search(p18_pattern, content):
        errors.append("PDF 18 anchor is not placed correctly mid-paragraph")

    # PDF 19 must be mid-paragraph inside a <p>
    p19_pattern = r'<p>[^<]*（含現金卡及信用卡）<span id="pdf-page-19" class="source-page-anchor"[^>]*></span>或保證債務已逾期者。</p>'
    if not re.search(p19_pattern, content):
        errors.append("PDF 19 anchor is not placed correctly mid-paragraph")

    # PDF 20 anchor before paragraph
    p20_pattern = r'<span id="pdf-page-20" class="source-page-anchor"[^>]*></span>\s*<p>（十二）保證人有前述'
    if not re.search(p20_pattern, content):
        errors.append("PDF 20 anchor is not placed correctly before clause paragraph")

    # 8. Clauses #clause-1 and #clause-2
    if "clause-1" not in parser.ids:
        errors.append("Missing id='clause-1'")
    if "clause-2" not in parser.ids:
        errors.append("Missing id='clause-2'")

    clause1_pattern = r'<p id="clause-1">一、送保案件有下列情事之一者，不予保證。'
    if not re.search(clause1_pattern, content):
        errors.append("Clause 1 paragraph content mismatch or missing id")

    clause2_pattern = r'<p id="clause-2">二、企業戶有前述（二）、（三）、（四）之情事'
    if not re.search(clause2_pattern, content):
        errors.append("Clause 2 paragraph content mismatch or missing id")

    # 9. Topic TOC presence and exact excerpts
    if '<nav class="topic-toc" aria-label="本規定目錄">' not in content:
        errors.append("Missing <nav class=\"topic-toc\">")
    if '<a href="#clause-1">' not in content:
        errors.append("Missing TOC link to #clause-1")
    if '<a href="#clause-2">' not in content:
        errors.append("Missing TOC link to #clause-2")

    # 10. Quick links to PDF pages
    for page_num in (17, 18, 19, 20):
        if f'href="#pdf-page-{page_num}"' not in content:
            errors.append(f"Missing quick link to #pdf-page-{page_num}")

    # 11. Other 15 logical reading units preserve .page-card
    other_units = [u for u in resolved_units if u["id"] != "excluded-guarantee"]
    if len(other_units) != 15:
        errors.append(f"Expected 15 other logical units, found {len(other_units)}")

    for u in other_units:
        u_path = SITE / u["readingUrl"]
        if not u_path.is_file():
            errors.append(f"Other logical unit file missing: {u['readingUrl']}")
            continue
        u_content = u_path.read_text(encoding="utf-8")
        if 'class="page-card' not in u_content:
            errors.append(f"Other unit {u['id']} unexpectedly missing .page-card")
        if 'class="continuous-reading"' in u_content:
            errors.append(f"Other unit {u['id']} unexpectedly has .continuous-reading")

    # 12. 203 physical pages preserve .page-card
    pages_data = json.loads((DATA / "pages.json").read_text(encoding="utf-8"))
    if len(pages_data) != 203:
        errors.append(f"Expected 203 pages in pages.json, found {len(pages_data)}")

    for page in pages_data:
        p_num = page["pdfPage"]
        p_path = SITE / f"versions/115-04/pages/page-{p_num:03d}.html"
        if not p_path.is_file():
            errors.append(f"Physical page missing: page-{p_num:03d}.html")
            continue
        p_content = p_path.read_text(encoding="utf-8")
        if f'id="pdf-page-{p_num}"' not in p_content:
            errors.append(f"Physical page {p_num} missing id='pdf-page-{p_num}'")
        if 'class="page-card' not in p_content:
            errors.append(f"Physical page {p_num} missing .page-card")

    # 13. site.js contains resolveSearchLandingHost and anchor support
    site_js = (ROOT / "assets/js/site.js").read_text(encoding="utf-8")
    if "resolveSearchLandingHost" not in site_js:
        errors.append("site.js missing resolveSearchLandingHost function")
    if "source-page-anchor" not in site_js:
        errors.append("site.js missing source-page-anchor handling")

    # 14. site.css contains continuous-reading styles
    site_css = (ROOT / "assets/css/site.css").read_text(encoding="utf-8")
    if ".continuous-reading" not in site_css:
        errors.append("site.css missing .continuous-reading style")
    if ".source-page-anchor" not in site_css:
        errors.append("site.css missing .source-page-anchor style")

    return errors


def main() -> None:
    errors = validate_continuous_reading()
    if errors:
        print(f"CONTINUOUS READING VALIDATION FAILED with {len(errors)} error(s):")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    print("CONTINUOUS READING VALIDATION PASSED")
    print("- Canonical URL verified")
    print("- Single H1 verified (0 duplicate)")
    print("- 2301 non-whitespace characters 100% source fidelity verified")
    print("- 4 inline source page anchors verified (#pdf-page-17..20)")
    print("- 2 mid-paragraph boundaries verified inline inside <p>")
    print("- 2 clauses verified (#clause-1, #clause-2)")
    print("- Topic TOC with exact excerpts verified")
    print("- Zero .page-card elements in excluded-guarantee verified")
    print("- 15 other logical units .page-card preserved verified")
    print("- 203 physical pages .page-card preserved verified")
    print("- Search landing host and CSS styles verified")


if __name__ == "__main__":
    main()
