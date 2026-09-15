#!/usr/bin/env python3
"""Responsive real-browser E2E checks for Search UX 4.2 Match Transparency."""

from __future__ import annotations

import http.server
import threading
import sys
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

    # 1. Exact form match with case preservation (格式25A)
    page.goto(f"{base}/?q=格式25A")
    page.locator(".search-result").first.wait_for(timeout=5000)
    page.wait_for_timeout(500)
    reasons = page.locator(".result-match-reasons").first
    assert reasons.is_visible(), "result-match-reasons should be visible"
    reason_texts = [r.text_content().strip() for r in page.locator(".match-reason").all()]
    assert any("書表編號完全符合「格式25A」" in text for text in reason_texts), f"Expected exact form reason with 格式25A, got: {reason_texts}"
    assert not any("格式25a" in text for text in reason_texts), f"Lowercase 格式25a must not appear in reason text: {reason_texts}"
    assert page.locator(".result-match-meta").count() == 0, "Old result-match-meta must not exist"
    assert page.locator(".search-hit").count() > 0, "Search hit highlights should exist"

    # 2. Concept expansion (抵押品)
    page.goto(f"{base}/?q=抵押品")
    page.locator(".search-result").first.wait_for(timeout=5000)
    page.wait_for_timeout(500)
    first_res = page.locator(".search-result").first
    collateral_title = first_res.locator("h3 a").text_content().strip()
    collateral_url = first_res.locator("h3 a").get_attribute("href")
    collateral_reasons = [r.text_content().strip() for r in first_res.locator(".match-reason").all()]
    print(f"[{width}px] 抵押品 matched result: title='{collateral_title}', url='{collateral_url}', reasons={collateral_reasons}")
    assert any("相關詞「抵押品」→「擔保品」" in text for text in collateral_reasons), f"Expected concept expansion reason for 抵押品, got: {collateral_reasons}"

    # 3. Direct heading / Direct body (代償利息)
    page.goto(f"{base}/?q=代償利息")
    page.locator(".search-result").first.wait_for(timeout=5000)
    page.wait_for_timeout(500)
    reason_texts = [r.text_content().strip() for r in page.locator(".match-reason").all()]
    assert any("章節標題命中「代償利息」" in text or "正文直接命中「代償利息」" in text for text in reason_texts), f"Expected direct match for 代償利息, got: {reason_texts}"

    # 4. Multi-token (青農 保證成數)
    page.goto(f"{base}/?q=青農 保證成數")
    page.locator(".search-result").first.wait_for(timeout=5000)
    page.wait_for_timeout(500)
    reason_texts = [r.text_content().strip() for r in page.locator(".match-reason").all()]
    assert any("青農" in text for text in reason_texts), f"Expected reason for 青農, got: {reason_texts}"
    assert any("保證成數" in text for text in reason_texts), f"Expected reason for 保證成數, got: {reason_texts}"

    # 5. Mobile overflow check for 390
    if width == 390:
        doc_overflow = page.evaluate("() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1")
        assert doc_overflow, f"Document overflowed at {width}px width"

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
                    viewport={"width": vp["width"], "height": vp["height"]}
                )
                page = context.new_page()
                res = run_viewport(context, page, base_url, vp["width"])
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
