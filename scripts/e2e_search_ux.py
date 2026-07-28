#!/usr/bin/env python3
"""Responsive real-browser E2E checks for Search UX 3.0."""

from __future__ import annotations

import http.server
import threading
from pathlib import Path
from urllib.parse import urlparse, parse_qs

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


def assert_no_overflow(page: Page) -> None:
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Layout overflow detected!"


def check_console_errors(page: Page) -> list:
    errors = []
    page.on("pageerror", lambda err: errors.append(err))
    return errors


def run_viewport(page: Page, base: str, width: int) -> dict:
    errors = check_console_errors(page)

    # 1. Direct shareable URL load
    page.goto(f"{base}/?q=代償&type=chapter")
    page.locator(".search-status").filter(has_text="找到").wait_for()
    
    # 2. Type filter restoration
    assert page.get_by_role("searchbox", name="全文搜尋").input_value() == "代償"
    assert page.locator("button[data-search-type='chapter']").get_attribute("aria-pressed") == "true"
    
    # 3. Keyword button trigger
    page.goto(base)
    page.locator("[data-keyword='利息']").first.click()
    page.locator(".search-status").filter(has_text="找到").wait_for()
    assert page.get_by_role("searchbox", name="全文搜尋").input_value() == "利息"
    assert "q=%E5%88%A9%E6%81%AF" in page.url

    # 4. Browser Back/Forward (popstate)
    page.go_back()
    assert "q=" not in page.url
    page.go_forward()
    assert "q=%E5%88%A9%E6%81%AF" in page.url
    page.locator(".search-status").filter(has_text="找到").wait_for()

    # 5. Search -> Reading target -> Return navigation
    first_result = page.locator(".search-results article h3 a").first
    first_result.click()
    page.wait_for_load_state("domcontentloaded")
    assert "fromSearch=1" in page.url
    assert "q=%E5%88%A9%E6%81%AF" in page.url
    
    return_link = page.locator(".return-to-search")
    assert return_link.is_visible()
    return_link.click()
    page.wait_for_load_state("domcontentloaded")
    assert "fromSearch" not in page.url
    assert "q=%E5%88%A9%E6%81%AF" in page.url

    # 6. Exact physical page return navigation
    first_exact = page.locator(".search-results article a.result-exact-page").first
    first_exact.click()
    page.wait_for_load_state("domcontentloaded")
    assert "fromSearch=1" in page.url
    return_link = page.locator(".return-to-search")
    assert return_link.is_visible()
    return_link.click()
    page.wait_for_load_state("domcontentloaded")

    # 7. Page reload
    page.reload()
    page.locator(".search-status").filter(has_text="找到").wait_for()
    assert page.get_by_role("searchbox", name="全文搜尋").input_value() == "利息"

    # 8. Clear query resets URL
    page.get_by_role("searchbox", name="全文搜尋").fill("")
    page.get_by_role("searchbox", name="全文搜尋").press("Enter")
    page.wait_for_timeout(500) # give it a moment to clear
    assert "q=" not in page.url
    
    # 9. Layout overflow prevention
    assert_no_overflow(page)

    # 10. Console/page errors check
    assert not errors, f"Console errors detected: {errors}"

    return {"status": "ok", "width": width}


def main() -> None:
    server = http.server.HTTPServer(("", 0), QuietHandler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    print(f"Test server running on {base}")

    try:
        import os
        os.chdir(SITE)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for vp in VIEWPORTS:
                context = browser.new_context(viewport=vp)
                page = context.new_page()
                print(f"Testing viewport {vp['width']}x{vp['height']}...")
                result = run_viewport(page, base, vp["width"])
                print(f"Viewport {result['width']} passed.")
                context.close()
            browser.close()
        print("SEARCH UX 3.0 E2E AUDIT PASSED")
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
