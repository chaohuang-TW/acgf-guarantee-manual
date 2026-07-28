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
    page.on("pageerror", lambda err: errors.append(f"PageError: {err}"))
    page.on("console", lambda msg: errors.append(f"Console {msg.type}: {msg.text}") if msg.type in ["error"] else None)
    page.on("response", lambda res: errors.append(f"404 Not Found: {res.url}") if res.status == 404 else None)
    return errors

def run_viewport(context, page: Page, base: str, width: int) -> dict:
    errors = check_console_errors(page)

    # 1. Direct shareable URL load
    page.goto(f"{base}/?q=代償&type=chapter")
    page.locator(".search-status").filter(has_text="找到").wait_for()
    
    # 2. Type filter restoration
    assert page.get_by_role("searchbox", name="全文搜尋").input_value() == "代償"
    assert page.locator("button[data-search-type='chapter']").get_attribute("aria-pressed") == "true"
    
    # 3. Copy Search Link E2E
    copy_btn = page.locator(".copy-search-link")
    assert copy_btn.is_visible(), "Copy link button should be visible for global search"
    # Ensure clipboard works
    copy_btn.click()
    page.wait_for_timeout(100) # Give it time to write
    copied_url = page.evaluate("navigator.clipboard.readText()")
    assert "q=%E4%BB%A3%E5%84%9F" in copied_url
    assert "type=chapter" in copied_url
    assert copied_url.startswith(base)

    # 4. Form Deep Link (?q=格式25A&type=form)
    page.goto(f"{base}/?q=格式25A&type=form")
    page.locator(".search-status").filter(has_text="找到").wait_for()
    assert page.get_by_role("searchbox", name="全文搜尋").input_value() == "格式25A"

    # 5. A -> B -> Back -> Forward with true form submission
    page.goto(base)
    searchbox = page.get_by_role("searchbox", name="全文搜尋")
    searchbox.fill("A")
    searchbox.press("Enter")
    page.locator(".search-status").filter(has_text="找到").wait_for()
    first_res_A = page.locator(".search-results article").first.text_content()

    searchbox.fill("B")
    searchbox.press("Enter")
    page.locator(".search-status").filter(has_text="找到").wait_for()
    first_res_B = page.locator(".search-results article").first.text_content()
    assert first_res_A != first_res_B, "Results should differ"

    page.go_back()
    page.wait_for_timeout(500)
    assert page.get_by_role("searchbox", name="全文搜尋").input_value() == "A"
    assert "q=A" in page.url

    page.go_forward()
    page.wait_for_timeout(500)
    assert page.get_by_role("searchbox", name="全文搜尋").input_value() == "B"
    assert "q=B" in page.url


    # Logical Page Canonical
    page.goto(f"{base}/versions/115-04/chapters/part-3/subrogation-scope.html?fromSearch=1&q=test")
    page.wait_for_load_state("domcontentloaded")
    canonical = page.locator("link[rel='canonical']").get_attribute("href")
    assert "fromSearch" not in canonical
    assert "q=" not in canonical

    # Physical Page Canonical
    page.goto(f"{base}/versions/115-04/pages/page-044.html?fromSearch=1&q=test")
    page.wait_for_load_state("domcontentloaded")
    canonical = page.locator("link[rel='canonical']").get_attribute("href")
    assert "fromSearch" not in canonical
    assert "q=" not in canonical
    
    # Layout overflow prevention
    assert_no_overflow(page)

    # Console/page errors check
    assert not errors, f"Console/Network errors detected: {errors}"

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
                # Add clipboard permissions
                context = browser.new_context(
                    viewport=vp, 
                    permissions=["clipboard-read", "clipboard-write"]
                )
                page = context.new_page()
                print(f"Testing viewport {vp['width']}x{vp['height']}...")
                result = run_viewport(context, page, base, vp["width"])
                print(f"Viewport {result['width']} passed.")
                context.close()
            browser.close()
        print("SEARCH UX 3.0 E2E AUDIT PASSED")
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
