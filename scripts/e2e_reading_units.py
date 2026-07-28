#!/usr/bin/env python3
"""Responsive real-browser E2E checks for search and logical reading units."""

from __future__ import annotations

import http.server
import threading
from pathlib import Path
import urllib.parse

def clean_url(u: str) -> str:
    parsed = urllib.parse.urlparse(u)
    return f"{parsed.path}#{parsed.fragment}" if parsed.fragment else parsed.path

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


def search(page: Page, base: str, query: str):
    page.goto(base)
    page.get_by_role("searchbox", name="全文搜尋").fill(query)
    page.get_by_role("button", name="搜尋").click()
    page.locator(".search-status").filter(has_text="找到").wait_for()
    first = page.locator(".search-results article h3 a").first
    assert first.count() == 1
    return first


def assert_no_overflow(page: Page) -> None:
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def run_viewport(page: Page, base: str, width: int) -> dict:
    page.goto(base)
    assert page.get_by_role("heading", name="農業信用保證業務作業手冊").is_visible()
    assert_no_overflow(page)

    interest = search(page, base, "代償利息")
    assert clean_url(interest.get_attribute("href") or "").endswith(
        "/chapters/part-3/subrogation-scope.html#pdf-page-46"
    )
    toggle = page.locator(".search-context-toggle")
    if toggle.count():
        first_toggle = toggle.first
        first_toggle.click()
        assert first_toggle.get_attribute("aria-expanded") == "true"
        first_toggle.click()
        assert first_toggle.get_attribute("aria-expanded") == "false"
    interest.click()
    page.wait_for_load_state("domcontentloaded")
    assert clean_url(page.url).endswith("/chapters/part-3/subrogation-scope.html#pdf-page-46")
    assert "代償利息之計算方式" in page.locator(".manual-content").inner_text()
    assert_no_overflow(page)

    local_link = page.locator(
        '.section-nav a[href$="subrogation-requirements.html"]'
    )
    assert local_link.count() == 1
    local_link.click()
    page.wait_for_load_state("domcontentloaded")
    assert "/chapters/part-3/subrogation-requirements.html" in page.url
    page.go_back()
    page.wait_for_load_state("domcontentloaded")
    assert clean_url(page.url).endswith("/chapters/part-3/subrogation-scope.html#pdf-page-46")

    search(page, base, "代償利息")
    exact_page = page.locator(".search-results article:first-of-type .result-exact-page")
    assert exact_page.count() == 1
    exact_page.click()
    page.wait_for_load_state("domcontentloaded")
    assert clean_url(page.url).endswith("/pages/page-046.html#pdf-page-46")
    assert "代償利息之計算方式" in page.locator(".page-card").inner_text()
    page.go_back()
    page.wait_for_load_state("domcontentloaded")
    assert page.url.startswith(base)
    assert page.get_by_role("searchbox", name="全文搜尋").is_visible()

    changes = search(page, base, "內容變更事項")
    assert clean_url(changes.get_attribute("href") or "").endswith(
        "/chapters/part-2/guarantee-changes.html#pdf-page-32"
    )
    changes.click()
    page.wait_for_load_state("domcontentloaded")
    changes_text = page.locator(".manual-content").inner_text()
    assert "內容變更事項" in changes_text
    assert "貳、終止保證之處理" not in changes_text
    assert "24-23" not in page.locator("body").inner_text()

    main_toc = page.locator(
        'header.site-header nav[aria-label="主要導覽"]'
    ).get_by_role("link", name="完整目錄")
    assert main_toc.count() == 1
    main_toc.click()
    page.wait_for_load_state("domcontentloaded")
    assert clean_url(page.url).endswith("/versions/115-04/index.html")

    form = search(page, base, "格式25A")
    assert clean_url(form.get_attribute("href") or "").endswith(
        "/forms/form-25a.html#pdf-page-178"
    )
    form.click()
    page.wait_for_load_state("domcontentloaded")
    assert clean_url(page.url).endswith("/forms/form-25a.html#pdf-page-178")
    assert page.locator(".source-preview-image").count() == 1
    assert_no_overflow(page)
    return {"width": width, "expandedToggle": bool(toggle.count())}


def main() -> None:
    errors: list[str] = []
    page_errors: list[str] = []
    missing: list[str] = []
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(SITE), **kwargs)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}/"
    matrix: list[dict] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            for viewport in VIEWPORTS:
                page = browser.new_page(viewport=viewport)
                page.on(
                    "console",
                    lambda message: errors.append(message.text)
                    if message.type == "error"
                    else None,
                )
                page.on("pageerror", lambda error: page_errors.append(str(error)))
                page.on(
                    "response",
                    lambda response: missing.append(response.url)
                    if response.status == 404
                    else None,
                )
                matrix.append(run_viewport(page, base, viewport["width"]))
                page.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    assert not errors, f"Console errors: {errors}"
    assert not page_errors, f"Page errors: {page_errors}"
    assert not missing, f"Network 404 responses: {missing}"
    assert [item["width"] for item in matrix] == [390, 768, 1440]
    print(
        "PLAYWRIGHT RESPONSIVE E2E PASSED: "
        "390x900, 768x900, 1440x1000 full interactions; "
        "console errors 0; page errors 0; network 404 0"
    )


if __name__ == "__main__":
    main()
