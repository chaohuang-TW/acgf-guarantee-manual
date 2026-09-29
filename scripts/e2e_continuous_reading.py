#!/usr/bin/env python3
"""Responsive real-browser E2E checks for Reading UX 3.0 Continuous Logical Reading Pilot."""

from __future__ import annotations

import http.server
import sys
import threading
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
VIEWPORTS = [
    {"width": 390, "height": 844},
    {"width": 768, "height": 1024},
    {"width": 1440, "height": 900},
]


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


def run_viewport(page: Page, base: str, width: int) -> dict:
    console_errors: list[str] = []
    page_errors: list[str] = []
    network_404s: list[str] = []

    page.on("pageerror", lambda err: page_errors.append(f"PageError: {err}"))
    page.on("console", lambda msg: console_errors.append(f"Console {msg.type}: {msg.text}") if msg.type in ["error"] else None)
    page.on("response", lambda res: network_404s.append(f"404 Not Found: {res.url}") if res.status == 404 else None)

    pilot_url = f"{base}/versions/115-04/chapters/part-1/excluded-guarantee.html"

    # =========================================================================
    # Test 1: Page Load, DOM Structure, and Overflow Integrity
    # =========================================================================
    page.goto(pilot_url)
    page.wait_for_load_state("networkidle")

    # Verify no horizontal scroll overflow
    scroll_width = page.evaluate("() => document.documentElement.scrollWidth")
    client_width = page.evaluate("() => document.documentElement.clientWidth")
    assert scroll_width <= client_width, f"[{width}px] Horizontal overflow detected: scrollWidth {scroll_width} > clientWidth {client_width}"

    # Verify H1 uniqueness and text
    h1s = page.locator("h1")
    assert h1s.count() == 1, f"[{width}px] Expected exactly 1 H1, found {h1s.count()}"
    assert h1s.first.text_content().strip() == "參、不予保證規定", f"[{width}px] H1 text mismatch"

    # Verify 0 .page-card elements
    cards = page.locator(".page-card")
    assert cards.count() == 0, f"[{width}px] Continuous reading unit must not contain .page-card elements, found {cards.count()}"

    # Verify continuous container
    assert page.locator(".continuous-reading").count() == 1, f"[{width}px] Missing .continuous-reading"
    assert page.locator(".continuous-header").count() == 1, f"[{width}px] Missing .continuous-header"
    assert page.locator(".source-provenance").count() == 1, f"[{width}px] Missing .source-provenance"
    assert page.locator(".topic-toc").count() == 1, f"[{width}px] Missing .topic-toc"

    # Verify 4 source anchors
    for p_num in (17, 18, 19, 20):
        anchor = page.locator(f"#pdf-page-{p_num}")
        assert anchor.count() == 1, f"[{width}px] Missing #pdf-page-{p_num} anchor"

    # Verify 2 clauses
    assert page.locator("#clause-1").count() == 1, f"[{width}px] Missing #clause-1"
    assert page.locator("#clause-2").count() == 1, f"[{width}px] Missing #clause-2"

    # Save screenshot
    screenshot_path = f"/tmp/reading_ux_3_0_continuous_{width}.png"
    page.screenshot(path=screenshot_path)

    # =========================================================================
    # Test 2: TOC Navigation Interaction
    # =========================================================================
    toc_clause_1 = page.locator('.topic-toc a[href="#clause-1"]')
    assert toc_clause_1.is_visible(), f"[{width}px] TOC link to clause 1 should be visible"
    toc_clause_1.click()
    page.wait_for_function("() => { const el = document.getElementById('clause-1'); const r = el.getBoundingClientRect(); return r.top >= 0 && r.top <= window.innerHeight; }", timeout=5000)

    toc_clause_2 = page.locator('.topic-toc a[href="#clause-2"]')
    assert toc_clause_2.is_visible(), f"[{width}px] TOC link to clause 2 should be visible"
    toc_clause_2.click()
    page.wait_for_function("() => { const el = document.getElementById('clause-2'); const r = el.getBoundingClientRect(); return r.top >= 0 && r.top <= window.innerHeight; }", timeout=5000)

    # =========================================================================
    # Test 2.5: Provenance Links to Original Physical Pages
    # =========================================================================
    page.goto(pilot_url)
    page.wait_for_load_state("networkidle")

    for p_num, pr_num in [(17, 9), (18, 10), (19, 11), (20, 12)]:
        link = page.locator(f'.source-page-link[href*="page-{p_num:03d}.html#pdf-page-{p_num}"]')
        assert link.count() == 1, f"[{width}px] Missing provenance link for PDF {p_num} (printed {pr_num})"
        href = link.get_attribute("href")
        assert not href.startswith("#pdf-page-"), f"[{width}px] Provenance href must not be local anchor, got {href}"
        assert f"page-{p_num:03d}.html#pdf-page-{p_num}" in href, f"[{width}px] Provenance href must target physical page, got {href}"
        aria = link.get_attribute("aria-label")
        assert f"第{pr_num}頁" in aria, f"[{width}px] Missing or invalid aria-label for page {pr_num}: {aria}"

    # Click printed page 10 (PDF 18)
    link_18 = page.locator('.source-page-link[href*="page-018.html#pdf-page-18"]')
    link_18.click()
    page.wait_for_load_state("networkidle")

    current_url = page.url
    assert "page-018.html" in current_url, f"[{width}px] Expected navigation to page-018.html, got {current_url}"
    assert current_url.endswith("#pdf-page-18"), f"[{width}px] Expected hash #pdf-page-18, got {current_url}"

    phys_18 = page.locator("#pdf-page-18")
    assert phys_18.count() == 1, f"[{width}px] Missing #pdf-page-18 on physical page"
    assert "page-card" in phys_18.get_attribute("class"), f"[{width}px] Physical page element must have .page-card class"

    page.go_back()
    page.wait_for_load_state("networkidle")
    assert "excluded-guarantee.html" in page.url, f"[{width}px] Expected back navigation to excluded-guarantee.html, got {page.url}"
    assert page.locator(".continuous-reading").count() == 1, f"[{width}px] Back navigation failed to restore continuous reading page"

    # =========================================================================
    # Test 3: Search Landing Cue & Heading Highlight (?q=不予保證#pdf-page-17)
    # =========================================================================
    search_url_17 = f"{pilot_url}?fromSearch=1&q=%E4%B8%8D%E4%BA%88%E4%BF%9D%E8%AD%89#pdf-page-17"
    page.goto(search_url_17)
    page.locator(".reading-hit-nav").wait_for(timeout=5000)
    page.wait_for_timeout(200)

    # Note exists and text matches
    note = page.locator(".search-landing-note")
    assert note.count() == 1, f"[{width}px] Missing .search-landing-note"
    assert note.text_content().strip() == "搜尋結果定位至此"

    # First hit is in H1
    h1_hit = page.locator(".continuous-source-heading .reading-hit")
    assert h1_hit.count() >= 1, f"[{width}px] Expected reading-hit inside H1"
    assert "reading-hit-current" in h1_hit.first.get_attribute("class"), f"[{width}px] First hit in H1 should be current hit"

    # =========================================================================
    # Test 4: Mid-paragraph Inline Anchor Landing Cue & First Hit (?q=債務#pdf-page-19)
    # =========================================================================
    search_url_19 = f"{pilot_url}?fromSearch=1&q=%E5%82%B5%E5%8B%99#pdf-page-19"
    page.goto(search_url_19)
    page.locator(".reading-hit-nav").wait_for(timeout=5000)
    page.wait_for_timeout(200)

    # Note exists
    assert page.locator(".search-landing-note").count() == 1, f"[{width}px] Missing .search-landing-note on mid-para anchor"

    # Host paragraph has search-landing-target class
    host_has_target = page.evaluate("() => { const a = document.getElementById('pdf-page-19'); const host = a.closest('p'); return host && host.classList.contains('search-landing-target'); }")
    assert host_has_target, f"[{width}px] Host paragraph must have search-landing-target"

    # Active hit must follow #pdf-page-19 anchor (inside '或保證債務已逾期者。')
    is_following_hit = page.evaluate("""() => {
        const anchor = document.getElementById('pdf-page-19');
        const active = document.querySelector('.reading-hit-current');
        if (!anchor || !active) return false;
        return Boolean(anchor.compareDocumentPosition(active) & Node.DOCUMENT_POSITION_FOLLOWING);
    }""")
    assert is_following_hit, f"[{width}px] Active hit must strictly follow #pdf-page-19 anchor in document order"

    # =========================================================================
    # Test 5: Legacy Unit Regression Check (.page-card preservation)
    # =========================================================================
    legacy_url = f"{base}/versions/115-04/chapters/part-1/guarantee-subject.html?fromSearch=1&q=%E4%BF%9D%E8%AD%89#pdf-page-13"
    page.goto(legacy_url)
    page.locator(".reading-hit-nav").wait_for(timeout=5000)
    page.wait_for_timeout(200)

    legacy_card = page.locator("#pdf-page-13")
    assert legacy_card.count() == 1, f"[{width}px] Missing legacy #pdf-page-13"
    assert "page-card" in legacy_card.get_attribute("class"), f"[{width}px] Legacy element must keep .page-card"
    assert "search-landing-target" in legacy_card.get_attribute("class"), f"[{width}px] Legacy card must receive search-landing-target"
    assert legacy_card.locator(".search-landing-note").count() == 1, f"[{width}px] Legacy card must contain .search-landing-note"

    return {
        "width": width,
        "console_errors": console_errors,
        "page_errors": page_errors,
        "network_404s": network_404s,
    }


def main() -> int:
    if not SITE.is_dir():
        print(f"Error: {SITE} not found. Build first.", file=sys.stderr)
        return 1

    server = http.server.HTTPServer(("127.0.0.1", 0), lambda *args: QuietHandler(*args, directory=str(SITE)))
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{port}"
    print(f"Continuous Reading E2E server started at {base_url}")

    results = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            for vp in VIEWPORTS:
                print(f"Testing viewport {vp['width']}x{vp['height']}...")
                context = browser.new_context(
                    viewport={"width": vp['width'], "height": vp['height']}
                )
                page = context.new_page()
                res = run_viewport(page, base_url, vp['width'])
                results.append(res)
                context.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()

    failed = False
    for res in results:
        w = res["width"]
        if res["console_errors"] or res["page_errors"] or res["network_404s"]:
            print(f"\n[{w}px] FAIL")
            for err in res["page_errors"]:
                print(f"  {err}")
            for err in res["console_errors"]:
                print(f"  {err}")
            for err in res["network_404s"]:
                print(f"  {err}")
            failed = True
        else:
            print(f"[{w}px] PASS (0 console errors, 0 404s, 0 overflow)")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
