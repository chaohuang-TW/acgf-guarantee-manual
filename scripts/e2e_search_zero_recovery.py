#!/usr/bin/env python3
"""Responsive real-browser E2E checks for Search UX 4.3 Zero-Result Typo Recovery."""

from __future__ import annotations

import http.server
import sys
import threading
import urllib.parse
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
VIEWPORTS = [
    {"width": 390, "height": 900},
    {"width": 768, "height": 900},
    {"width": 1440, "height": 1000},
]


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


def run_viewport(context, page: Page, base: str, width: int) -> dict:
    console_errors = []
    page_errors = []
    network_404s = []

    page.on("pageerror", lambda err: page_errors.append(f"PageError: {err}"))
    page.on("console", lambda msg: console_errors.append(f"Console {msg.type}: {msg.text}") if msg.type in ["error"] else None)
    page.on("response", lambda res: network_404s.append(f"404 Not Found: {res.url}") if res.status == 404 else None)

    # =========================================================================
    # Journey A: Single typo recovery (代位清嘗 -> 代位清償)
    # =========================================================================
    q_a = urllib.parse.quote("代位清嘗")
    page.goto(f"{base}/?q={q_a}")
    page.locator(".search-zero-recovery").wait_for(timeout=5000)
    page.wait_for_timeout(300)

    # 0 original search results
    assert page.locator(".search-result").count() == 0, "Journey A: Original result count should be 0"
    # Zero recovery container visible
    assert page.locator(".search-zero-recovery").is_visible(), "Journey A: .search-zero-recovery should be visible"
    # Status includes original query
    status_text = page.locator(".search-status").text_content()
    assert "找不到「代位清嘗」的結果。" in status_text, f"Journey A: Status text mismatch: {status_text}"
    # Suggestion chip text is 代位清償
    chips = page.locator(".recovery-chip")
    assert chips.count() == 1, f"Journey A: Expected 1 recovery chip, got {chips.count()}"
    assert chips.first.text_content().strip() == "代位清償", f"Journey A: Chip text mismatch: {chips.first.text_content()}"

    # Click chip -> navigate to corrected query
    chips.first.click()
    page.locator(".search-result").first.wait_for(timeout=5000)
    page.wait_for_timeout(300)

    # URL updated to ?q=代位清償
    current_url = urllib.parse.unquote_plus(page.url)
    assert "q=代位清償" in current_url, f"Journey A: Expected q=代位清償 in URL, got {current_url}"
    # Search input value updated
    input_val = page.locator("input[type=search]").input_value()
    assert input_val == "代位清償", f"Journey A: Input value mismatch: {input_val}"
    # Results > 0
    res_count = page.locator(".search-result").count()
    assert res_count > 0, f"Journey A: Expected >0 results after click, got {res_count}"
    # Zero recovery container is gone
    assert page.locator(".search-zero-recovery").count() == 0, "Journey A: Recovery element must disappear"

    # =========================================================================
    # Journey B: Multi-token assembled recovery (代位清嘗 抵壓品 -> 代位清償 抵押品)
    # =========================================================================
    q_b = urllib.parse.quote("代位清嘗 抵壓品")
    page.goto(f"{base}/?q={q_b}")
    page.locator(".search-zero-recovery").wait_for(timeout=5000)
    page.wait_for_timeout(300)

    assert page.locator(".search-result").count() == 0, "Journey B: Original results should be 0"
    chips_b = page.locator(".recovery-chip")
    assert chips_b.count() == 1, f"Journey B: Expected 1 recovery chip, got {chips_b.count()}"
    assert chips_b.first.text_content().strip() == "代位清償 抵押品", f"Journey B: Chip text mismatch: {chips_b.first.text_content()}"

    chips_b.first.click()
    page.locator(".search-result").first.wait_for(timeout=5000)
    page.wait_for_timeout(300)

    current_url_b = urllib.parse.unquote_plus(page.url)
    assert "q=代位清償 抵押品" in current_url_b, f"Journey B: Expected q=代位清償 抵押品 in URL, got {current_url_b}"
    assert page.locator(".search-result").count() > 0, "Journey B: Results must be > 0"
    assert page.locator(".search-zero-recovery").count() == 0, "Journey B: Recovery must disappear"

    # =========================================================================
    # Journey C: Multi-token with one invalid token (代位清嘗 xyz123 -> reject, no chips)
    # =========================================================================
    q_c = urllib.parse.quote("代位清嘗 xyz123")
    page.goto(f"{base}/?q={q_c}")
    page.locator(".search-zero-recovery").wait_for(timeout=5000)
    page.wait_for_timeout(300)

    assert page.locator(".search-result").count() == 0, "Journey C: Results should be 0"
    assert page.locator(".recovery-chip").count() == 0, "Journey C: Partial correction chips must NOT appear"
    assert page.locator(".recovery-help").is_visible(), "Journey C: Generic help message should appear"
    help_text_c = page.locator(".recovery-help").text_content()
    assert "縮短關鍵字" in help_text_c, f"Journey C: Generic guidance missing: {help_text_c}"

    # =========================================================================
    # Journey D: True no match (火星貸款 -> no fabricated suggestion)
    # =========================================================================
    q_d = urllib.parse.quote("火星貸款")
    page.goto(f"{base}/?q={q_d}")
    page.locator(".search-zero-recovery").wait_for(timeout=5000)
    page.wait_for_timeout(300)

    assert page.locator(".search-result").count() == 0, "Journey D: Results should be 0"
    assert page.locator(".recovery-chip").count() == 0, "Journey D: No chips should appear for true no match"
    assert page.locator(".recovery-help").is_visible(), "Journey D: Generic help should be visible"
    status_d = page.locator(".search-status").text_content()
    assert "找不到「火星貸款」的結果。" in status_d, f"Journey D: Status text mismatch: {status_d}"

    # =========================================================================
    # Journey E: Nonzero query (代償 -> results > 0, recovery must NOT exist)
    # =========================================================================
    q_e = urllib.parse.quote("代償")
    page.goto(f"{base}/?q={q_e}")
    page.locator(".search-result").first.wait_for(timeout=5000)
    page.wait_for_timeout(300)

    assert page.locator(".search-result").count() > 0, "Journey E: Results should be > 0"
    assert page.locator(".search-zero-recovery").count() == 0, "Journey E: Recovery must NOT exist when results > 0"

    # =========================================================================
    # Journey F: Concept expansion query (抵押品 -> recovery NOT exist, reasons intact)
    # =========================================================================
    q_f = urllib.parse.quote("抵押品")
    page.goto(f"{base}/?q={q_f}")
    page.locator(".search-result").first.wait_for(timeout=5000)
    page.wait_for_timeout(300)

    assert page.locator(".search-result").count() > 0, "Journey F: Results should be > 0"
    assert page.locator(".search-zero-recovery").count() == 0, "Journey F: Recovery must NOT exist when results > 0"
    assert page.locator(".result-match-reasons").first.is_visible(), "Journey F: Match reasons should be visible"

    # =========================================================================
    # Journey G: Safe DOM (XSS & HTML tag injection prevention)
    # 1. Test script tag injection prevention
    q_g1 = urllib.parse.quote("<script>alert(1)</script>")
    page.goto(f"{base}/?q={q_g1}")
    page.locator(".search-panel").wait_for(timeout=5000)
    page.wait_for_timeout(500)
    assert not any("alert(1)" in s.text_content() for s in page.locator("script:not([src])").all()), "Injected script must not exist"

    # 2. Test mark tag in zero recovery
    q_g2 = urllib.parse.quote("<mark>代位清嘗</mark>")
    page.goto(f"{base}/?q={q_g2}")
    page.locator(".search-zero-recovery").wait_for(timeout=5000)
    page.wait_for_timeout(300)
    assert page.locator(".search-zero-recovery mark").count() == 0, "Raw mark tag must not become an HTML element in recovery"
    assert page.locator(".search-status mark").count() == 0, "Status must not contain mark element"
    status_g2 = page.locator(".search-status").text_content()
    assert "<mark>代位清嘗</mark>" in status_g2, "Status text should safely include raw text"

    # Journey H: Responsive layout & no horizontal overflow
    # =========================================================================
    q_h = urllib.parse.quote("代位清嘗")
    page.goto(f"{base}/?q={q_h}")
    page.locator(".search-zero-recovery").wait_for(timeout=5000)
    page.wait_for_timeout(300)

    doc_overflow = page.evaluate("() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1")
    assert doc_overflow, f"Document overflowed horizontally at {width}px width on zero recovery page"

    # Keyboard accessibility test: chip can be focused and triggered by keyboard
    chip = page.locator(".recovery-chip").first
    chip.focus()
    focused_tag = page.evaluate("() => document.activeElement.tagName.toLowerCase()")
    assert focused_tag == "button", f"Active element should be button, got {focused_tag}"

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
    print(f"Server started at {base_url}")

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
                res = run_viewport(context, page, base_url, vp['width'])
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
            print(f"[{w}px] PASS (0 console errors, 0 404s)")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
