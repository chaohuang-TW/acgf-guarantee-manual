#!/usr/bin/env python3
"""Real-browser end-to-end checks for logical reading units and search targets."""

from __future__ import annotations

import contextlib
import http.server
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


def search(page, query: str) -> str:
    page.goto(page.url.split("#")[0].split("versions/")[0])
    page.get_by_role("searchbox", name="全文搜尋").fill(query)
    page.get_by_role("button", name="搜尋").click()
    page.locator(".search-status").filter(has_text="找到").wait_for()
    return page.locator(".search-results article h3 a").first.get_attribute("href") or ""


def content_text(page) -> str:
    return "\n".join(page.locator(".manual-content .display-text").all_inner_texts())


def main() -> None:
    errors: list[str] = []
    missing: list[str] = []
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(SITE), **kwargs)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}/"
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("response", lambda response: missing.append(response.url) if response.status == 404 else None)

            page.goto(base)
            assert page.get_by_role("heading", name="農業信用保證業務作業手冊").is_visible()
            target = search(page, "代位清償")
            assert target.endswith("/chapters/part-3/subrogation-requirements.html#pdf-page-44")
            page.locator(".search-results article h3 a").first.click()
            page.wait_for_load_state("domcontentloaded")
            requirements = content_text(page)
            assert "構評估認為無執行實益" in requirements
            assert "貳、代位清償範圍" not in requirements

            page.goto(base + "versions/115-04/chapters/part-3/subrogation-scope.html")
            scope = content_text(page)
            assert "貳、代位清償範圍" in scope and "代償利息之計算方式" in scope
            assert "參、代位清償應檢送文件" not in scope and "38-37" not in page.locator("body").inner_text()

            page.goto(base + "versions/115-04/chapters/part-2/guarantee-changes.html")
            changes = content_text(page)
            assert "內容變更事項" in changes and "貳、終止保證之處理" not in changes
            assert "24-23" not in page.locator("body").inner_text()

            assert search(page, "代償利息").endswith("/chapters/part-3/subrogation-scope.html#pdf-page-46")
            search(page, "代位清償應檢送文件")
            documents_link = page.locator(
                '.search-results article h3 a[href$="/chapters/part-3/subrogation-documents.html#pdf-page-46"]'
            )
            assert documents_link.count() == 1
            documents_link.click()
            assert page.url.endswith("/chapters/part-3/subrogation-documents.html#pdf-page-46")
            assert search(page, "格式25A").endswith("/forms/form-25a.html#pdf-page-178")
            assert search(page, "擔保品").endswith("/chapters/part-1/guarantee-application.html#pdf-page-21")

            for width in (390, 768, 1440):
                page.set_viewport_size({"width": width, "height": 900})
                page.goto(base + "versions/115-04/chapters/part-3/subrogation-requirements.html#pdf-page-44")
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    assert not errors, f"Console/page errors: {errors}"
    assert not missing, f"Network 404 responses: {missing}"
    print("PLAYWRIGHT E2E PASSED: desktop 1440/768 and mobile 390; console errors 0; network 404 0")


if __name__ == "__main__":
    main()
