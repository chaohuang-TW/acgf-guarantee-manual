#!/usr/bin/env python3
"""Data-driven responsive E2E checks for configured continuous-reading units."""

from __future__ import annotations

import http.server
import json
import sys
import threading
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
sys.path.insert(0, str(ROOT / "scripts"))
from build_site import CONTINUOUS_READING_UNIT_IDS  # noqa: E402
from display_text import non_whitespace_characters  # noqa: E402
from reading_units import load_resolved_units  # noqa: E402

VIEWPORTS = [
    {"width": 390, "height": 844},
    {"width": 768, "height": 1024},
    {"width": 1440, "height": 900},
]

# Queries are literal excerpts from the resolved source fragments. Their target
# page is selected by fragment position, so PDF page numbers remain data-driven.
SEARCH_CASES = [
    {"unitId": "credit-deterioration", "query": "信用卡遭強制停用", "fragmentIndex": -1},
    {"unitId": "pre-negotiation", "query": "最大債權金融機構", "fragmentIndex": -1},
    {"unitId": "overdue-guarantee", "query": "塗銷抵押權之處理方式", "fragmentIndex": -2},
    {"unitId": "overdue-guarantee", "query": "其他有合理理由", "fragmentIndex": -1},
]


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


def compact(value: str) -> str:
    return "".join(unicodedata.normalize("NFKC", value).split()).lower()


def assert_no_overflow(page: Page, width: int) -> None:
    dimensions = page.evaluate("() => ({scroll: document.documentElement.scrollWidth, client: document.documentElement.clientWidth})")
    assert dimensions["scroll"] <= dimensions["client"], f"[{width}px] horizontal overflow: {dimensions}"


def assert_search_landing(page: Page, base: str, unit: dict, query: str, pdf_page: int) -> None:
    fragment = next(item for item in unit["fragments"] if int(item["pdfPage"]) == pdf_page)
    assert compact(query) in compact(fragment["text"]), f"Search query is not source text on PDF {pdf_page}: {query!r}"

    page.goto(f"{base}/")
    searchbox = page.get_by_role("combobox", name="全文搜尋")
    searchbox.fill(query)
    searchbox.press("Enter")
    page.locator(".search-status").filter(has_text="找到").wait_for(timeout=10000)

    expected_path = "/" + unit["readingUrl"].lstrip("/")
    expected_hash = f"#pdf-page-{pdf_page}"
    matching_link = None
    for link in page.locator(".search-results article h3 a").all():
        resolved = urlsplit(urljoin(page.url, link.get_attribute("href") or ""))
        if resolved.path.endswith(expected_path) and resolved.fragment == expected_hash.removeprefix("#"):
            matching_link = link
            break
    assert matching_link is not None, f"Search result missing {expected_path}{expected_hash} for {query!r}"

    href = urljoin(page.url, matching_link.get_attribute("href") or "")
    parsed = urlsplit(href)
    assert parsed.path.endswith(expected_path) and parsed.fragment == expected_hash[1:], f"Wrong search target: {href}"
    matching_link.click()
    page.wait_for_url(lambda url: urlsplit(str(url)).path.endswith(expected_path) and urlsplit(str(url)).fragment == expected_hash[1:], timeout=10000)

    anchor = page.locator(f"{expected_hash}")
    assert anchor.count() == 1, f"Search target anchor missing: {expected_hash}"
    page.locator(".search-landing-note").wait_for(timeout=5000)
    landing_host_has_note = page.evaluate("""(id) => {
      const anchor = document.getElementById(id);
      if (!anchor) return false;
      const note = document.querySelector('.search-landing-note');
      let host = anchor.closest('p');
      if (!host) {
        host = anchor.nextElementSibling;
        if (host === note) host = note.nextElementSibling;
      }
      const notePrecedesHost = Boolean(note && host && (note.compareDocumentPosition(host) & Node.DOCUMENT_POSITION_FOLLOWING));
      return Boolean(host && host.classList.contains('search-landing-target') && note && (host.contains(note) || notePrecedesHost));
    }""", expected_hash[1:])
    assert landing_host_has_note, f"Search landing note is not on the anchor host for {expected_hash}"
    page.wait_for_function("""(id) => {
      const anchor = document.getElementById(id);
      const active = document.querySelector('.reading-hit-current');
      return Boolean(anchor && active && (anchor.compareDocumentPosition(active) & Node.DOCUMENT_POSITION_FOLLOWING));
    }""", arg=expected_hash[1:], timeout=5000)
    first_hit_follows = page.evaluate("""(id) => {
      const anchor = document.getElementById(id);
      const active = document.querySelector('.reading-hit-current');
      return Boolean(anchor && active && (anchor.compareDocumentPosition(active) & Node.DOCUMENT_POSITION_FOLLOWING));
    }""", expected_hash[1:])
    assert first_hit_follows, f"Active search hit does not follow {expected_hash} for {query!r}"
    print(f"SEARCH LANDING PASS {unit['id']} / PDF {pdf_page}: query={query!r}; first-hit-after-anchor=True")


def run_unit_viewport(page: Page, base: str, width: int, unit: dict, relations: list[dict]) -> dict:
    console_errors: list[str] = []
    page_errors: list[str] = []
    network_404s: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
    page.on("response", lambda response: network_404s.append(response.url) if response.status == 404 else None)

    url = f"{base}/{unit['readingUrl']}"
    page.goto(url)
    page.wait_for_load_state("networkidle")
    assert_no_overflow(page, width)

    assert page.locator("h1").count() == 1, f"[{width}px] {unit['id']}: expected one H1"
    assert page.locator("h1").inner_text().strip() == unit["title"], f"[{width}px] {unit['id']}: H1/title mismatch"
    assert page.locator("article.continuous-reading").count() == 1, f"[{width}px] {unit['id']}: continuous article missing"
    assert page.locator(".page-card").count() == 0, f"[{width}px] {unit['id']}: page-card found in continuous unit"

    expected_pages = [int(fragment["pdfPage"]) for fragment in unit["fragments"]]
    anchors = page.locator(".continuous-reading .source-page-anchor")
    actual_pages = [int(value) for value in anchors.evaluate_all("nodes => nodes.map(node => node.dataset.pdfPage)")]
    assert actual_pages == expected_pages, f"[{width}px] {unit['id']}: anchor order {actual_pages} != {expected_pages}"
    for pdf_page in expected_pages:
        assert page.locator(f".continuous-reading #pdf-page-{pdf_page}").count() == 1, f"[{width}px] {unit['id']}: anchor count for {pdf_page}"

    raw_source = "".join(fragment["text"] for fragment in unit["fragments"])
    rendered_source = page.locator(".continuous-source-heading").inner_text() + page.locator(".continuous-source-text").inner_text()
    assert non_whitespace_characters(raw_source) == non_whitespace_characters(rendered_source), f"[{width}px] {unit['id']}: DOM source fidelity mismatch"

    provenance = page.locator(".continuous-reading .source-page-link")
    assert provenance.count() == len(unit["fragments"]), f"[{width}px] {unit['id']}: provenance count mismatch"
    for fragment, link in zip(unit["fragments"], provenance.all()):
        pdf_page = int(fragment["pdfPage"])
        href = link.get_attribute("href") or ""
        assert f"page-{pdf_page:03d}.html#pdf-page-{pdf_page}" in href, f"[{width}px] {unit['id']}: bad provenance URL {href}"
        assert link.evaluate("node => node.tagName === 'A' && node.tabIndex >= 0"), f"[{width}px] {unit['id']}: provenance not keyboard-focusable"

    toc = page.locator(".continuous-reading .topic-toc")
    if toc.count():
        assert toc.count() == 1
        # Read the actual visible source labels after opening the native TOC.
        # Preserve the original exact-text, anchor and keyboard-link checks.
        disclosure = page.locator(".topic-toc-disclosure")
        if disclosure.count() and not disclosure.evaluate("node => node.open"):
            disclosure.locator("summary").focus()
            page.keyboard.press("Enter")
        for link in toc.locator("a").all():
            assert link.evaluate("node => node.tagName === 'A' && node.tabIndex >= 0"), f"[{width}px] {unit['id']}: TOC link not focusable"
            target_id = (link.get_attribute("href") or "").removeprefix("#")
            target = page.locator(f"#{target_id}")
            assert target.count() == 1 and link.inner_text() == target.inner_text(), f"[{width}px] {unit['id']}: TOC is not exact source text"

    pagination = page.locator(".continuous-reading ~ .reading-pagination")
    if not pagination.count():
        pagination = page.locator(".reading-pagination")
    assert pagination.count() == 1 and pagination.locator("a").count() > 0, f"[{width}px] {unit['id']}: pagination missing"
    for link in pagination.locator("a").all():
        assert link.evaluate("node => node.tagName === 'A' && node.tabIndex >= 0"), f"[{width}px] {unit['id']}: pagination link not focusable"

    expected_forms: dict[str, dict] = {}
    for relation in relations:
        if relation["contentRef"]["id"] == unit["id"]:
            expected_forms.setdefault(relation["form"]["number"], relation["form"])
    cards = page.locator(".related-forms .related-form-card")
    assert cards.count() == len(expected_forms), f"[{width}px] {unit['id']}: related form count mismatch"
    actual_form_titles = [card.locator(".related-form-title").inner_text().strip() for card in cards.all()]
    assert set(actual_form_titles) == {form["title"] for form in expected_forms.values()}, f"[{width}px] {unit['id']}: related form titles mismatch"

    if width == 390:
        # Real Tab traversal to a source link, then Enter and browser Back.
        # Source controls are now a native progressive disclosure. Open it with
        # the keyboard, then retain the original source-link/Enter/Back checks.
        page.locator(".source-provenance-details > summary").focus()
        page.keyboard.press("Enter")
        focused_source = False
        tab_count = 0
        for tab_count in range(1, 81):
            page.keyboard.press("Tab")
            focused_source = page.evaluate("() => document.activeElement?.classList?.contains('source-page-link') || false")
            if focused_source:
                break
        assert focused_source, f"[390px] {unit['id']}: Tab traversal did not reach a provenance link in 80 steps"
        expected_physical = expected_pages[0]
        page.keyboard.press("Enter")
        page.wait_for_url(lambda current: f"page-{expected_physical:03d}.html" in str(current) and str(current).endswith(f"#pdf-page-{expected_physical}"), timeout=10000)
        page.locator(f".page-card#pdf-page-{expected_physical}").wait_for()
        page.go_back(wait_until="domcontentloaded")
        assert page.url.endswith(unit["readingUrl"]), f"[390px] {unit['id']}: browser back failed: {page.url}"
        assert page.locator("article.continuous-reading").count() == 1
        print(f"KEYBOARD PASS {unit['id']}: Tab reached source link in {tab_count} steps; Enter navigation and browser Back")

    assert not console_errors, f"[{width}px] {unit['id']}: console errors: {console_errors}"
    assert not page_errors, f"[{width}px] {unit['id']}: page errors: {page_errors}"
    assert not network_404s, f"[{width}px] {unit['id']}: 404s: {network_404s}"
    print(f"E2E PASS {unit['id']} at {width}px: H1, source fidelity, {len(expected_pages)} anchors/provenance, TOC, Related Forms, pagination, overflow=0, console=0, pageerror=0, 404=0")
    return {"unitId": unit["id"], "width": width, "anchors": expected_pages, "sourceFidelity": True, "overflow": False, "consoleErrors": console_errors, "pageErrors": page_errors, "network404s": network_404s}


def main() -> int:
    if not SITE.is_dir():
        print(f"Error: {SITE} not found. Build first.", file=sys.stderr)
        return 1
    units = load_resolved_units()
    units_by_id = {unit["id"]: unit for unit in units}
    if not CONTINUOUS_READING_UNIT_IDS.issubset(units_by_id):
        raise RuntimeError("Continuous-reading config references an unknown source unit")
    candidates = [unit for unit in units if unit["id"] in CONTINUOUS_READING_UNIT_IDS]
    if len(candidates) != 4:
        raise RuntimeError(f"Expected four configured continuous-reading units; found {len(candidates)}")

    relations = json.loads((ROOT / "data/related-forms.json").read_text(encoding="utf-8"))["relations"]
    for case in SEARCH_CASES:
        unit = units_by_id[case["unitId"]]
        index = case["fragmentIndex"]
        if not 0 <= index < len(unit["fragments"]):
            index = len(unit["fragments"]) + index
        if not 0 <= index < len(unit["fragments"]):
            raise RuntimeError(f"Invalid fragment selector in search test: {case}")
        case["pdfPage"] = int(unit["fragments"][index]["pdfPage"])
        case["fragment"] = unit["fragments"][index]
        if compact(case["query"]) not in compact(case["fragment"]["text"]):
            raise RuntimeError(f"Search E2E query is not literal source text: {case['query']!r} ({case['unitId']})")

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), lambda *args: QuietHandler(*args, directory=str(SITE)))
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    print(f"Continuous Reading E2E server started at {base}")
    failures: list[str] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            for viewport in VIEWPORTS:
                for unit in candidates:
                    context = browser.new_context(viewport={"width": viewport["width"], "height": viewport["height"]})
                    page = context.new_page()
                    try:
                        run_unit_viewport(page, base, viewport["width"], unit, relations)
                    except Exception as error:
                        failures.append(f"{unit['id']}@{viewport['width']}: {error}")
                    finally:
                        context.close()
            context = browser.new_context(viewport={"width": 390, "height": 844})
            page = context.new_page()
            for case in SEARCH_CASES:
                try:
                    assert_search_landing(page, base, units_by_id[case["unitId"]], case["query"], case["pdfPage"])
                except Exception as error:
                    failures.append(f"search:{case['unitId']}:{case['pdfPage']}: {error}")
            context.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()

    if failures:
        print(f"CONTINUOUS READING E2E FAILED ({len(failures)}):")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("SEARCH LANDING CASES=4; FIRST_HIT_AFTER_ANCHOR=4/4")
    print("VIEWPORTS=390,768,1440; KEYBOARD=4/4; OVERFLOW=0; CONSOLE=0; PAGEERROR=0; 404=0")
    print("CONTINUOUS READING E2E PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
