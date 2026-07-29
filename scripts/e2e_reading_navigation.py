#!/usr/bin/env python3
"""E2E tests for Reading Navigation 2.0 and Search Landing Cue."""

from __future__ import annotations

import http.server
import threading
import urllib.parse
from pathlib import Path

from playwright.sync_api import Page, sync_playwright, expect

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


def clean_url(u: str) -> str:
    parsed = urllib.parse.urlparse(u)
    return f"{parsed.path}#{parsed.fragment}" if parsed.fragment else parsed.path


def setup_monitoring(page: Page) -> list[str]:
    errors = []
    page.on("console", lambda msg: errors.append(f"Console error: {msg.text}") if msg.type == "error" else None)
    page.on("pageerror", lambda err: errors.append(f"Page error: {err}"))
    page.on("response", lambda resp: errors.append(f"404: {resp.url}") if resp.status == 404 else None)
    return errors


def assert_no_overflow(page: Page) -> None:
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Horizontal overflow detected"


def test_reading_navigation(page: Page, base: str) -> None:
    errors = setup_monitoring(page)
    
    # 1. Chapters: First chapter should have NO prev, but has next
    page.goto(f"{base}/versions/115-04/chapters/part-1/guarantee-subject.html")
    assert not page.locator(".reading-pagination .nav-prev").is_visible()
    next_btn = page.locator(".reading-pagination .nav-next")
    assert next_btn.is_visible()
    assert "下一節：貳、保證成數" in next_btn.inner_text()
    assert "fromSearch" not in next_btn.get_attribute("href")
    
    # 2. Appendices: test cross-boundary (should not cross into forms)
    page.goto(f"{base}/versions/115-04/appendices/appendix-18.html")
    assert page.locator(".reading-pagination .nav-prev").is_visible()
    assert not page.locator(".reading-pagination .nav-next").is_visible()

    # 3. Forms & Special Forms Continuity
    # Check "格式 31" to "格式 3A"
    page.goto(f"{base}/versions/115-04/forms/form-31.html")
    next_btn = page.locator(".reading-pagination .nav-next")
    assert next_btn.is_visible()
    assert "下一節：格式 3A" in next_btn.inner_text()
    
    # 4. Special Forms ordering (33, 33-1, 34, 34-1)
    page.goto(f"{base}/versions/115-04/forms/form-33.html")
    next_btn = page.locator(".reading-pagination .nav-next")
    assert "下一節：格式 33-1" in next_btn.inner_text()
    
    page.goto(f"{base}/versions/115-04/forms/form-33-1.html")
    next_btn = page.locator(".reading-pagination .nav-next")
    assert "下一節：格式 12" in next_btn.inner_text()
    
    # 5. Format 25 series
    page.goto(f"{base}/versions/115-04/forms/form-25a.html")
    prev_btn = page.locator(".reading-pagination .nav-prev")
    next_btn = page.locator(".reading-pagination .nav-next")
    assert prev_btn.is_visible()
    assert next_btn.is_visible()
    
    assert not errors, f"Navigation journey had errors: {errors}"
    assert_no_overflow(page)


def test_search_landing_cue_and_copy(context, base: str) -> None:
    page = context.new_page()
    errors = setup_monitoring(page)
    
    # Mock a search landing
    landing_url = f"{base}/versions/115-04/chapters/part-1/guarantee-subject.html?q=額度&fromSearch=1#pdf-page-11"
    page.goto(landing_url)
    
    # Check Landing Cue is present
    target = page.locator("#pdf-page-11")
    
    # Check class
    assert "search-landing-target" in target.get_attribute("class")
    
    note = target.locator(".search-landing-note")
    expect(note).to_be_visible()
    assert "搜尋結果定位至此" in note.inner_text()
    
    # Double check no duplicate note
    assert target.locator(".search-landing-note").count() == 1
    
    # Test invalid hash no throw and no cue
    page.goto("about:blank")
    page.goto(f"{base}/versions/115-04/chapters/part-1/guarantee-subject.html?q=額度&fromSearch=1#invalid-hash-123")
    assert page.locator(".search-landing-target").count() == 0
    assert page.locator(".search-landing-note").count() == 0
    
    # Test clean hash (no query params, should have no cue)
    page.goto("about:blank")
    page.goto(f"{base}/versions/115-04/chapters/part-1/guarantee-subject.html#pdf-page-11")
    assert page.locator(".search-landing-target").count() == 0
    assert page.locator(".search-landing-note").count() == 0
    
    # Re-run original landing url to test copy
    page.goto("about:blank")
    page.goto(landing_url)
    target = page.locator("#pdf-page-11")
    
    # Test Copy Link Sanity
    copy_btn = target.locator("button.copy-page-link")
    copy_btn.click()
    
    # Wait for copy to complete
    expect(copy_btn).to_have_text("已複製連結！", timeout=2000)
    
    clipboard_text = page.evaluate("navigator.clipboard.readText()")
    parsed = urllib.parse.urlparse(clipboard_text)
    query_params = urllib.parse.parse_qs(parsed.query)
    
    assert "fromSearch" not in query_params
    assert "q" not in query_params
    assert "type" not in query_params
    assert parsed.fragment == "pdf-page-11"
    
    # Test copied URL reopen
    copied_page = context.new_page()
    copied_errors = setup_monitoring(copied_page)
    copied_page.goto(clipboard_text)
    assert copied_page.locator(".search-landing-target").count() == 0
    assert copied_page.locator(".search-landing-note").count() == 0
    assert not copied_errors, f"Copied URL reopen had errors: {copied_errors}"
    copied_page.close()

    assert not errors, f"Landing Cue journey had errors: {errors}"
    assert_no_overflow(page)
    page.close()


def main() -> None:
    server = http.server.HTTPServer(("127.0.0.1", 0), QuietHandler)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    
    import os
    os.chdir(SITE)

    with sync_playwright() as p:
        # Use standard chromium, not google chrome channel
        browser = p.chromium.launch()
        
        # Run navigation tests per viewport
        for vp in VIEWPORTS:
            context = browser.new_context(viewport=vp)
            
            # Nav tests
            page = context.new_page()
            test_reading_navigation(page, base)
            page.close()
            
            # Landing cue tests
            context.grant_permissions(["clipboard-read", "clipboard-write"])
            test_search_landing_cue_and_copy(context, base)
            
            context.close()
            
        browser.close()
        
    server.shutdown()
    print("Reading Navigation & Search Landing Cue E2E passed!")


if __name__ == "__main__":
    main()
