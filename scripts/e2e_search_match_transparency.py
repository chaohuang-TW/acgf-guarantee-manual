#!/usr/bin/env python3
"""Responsive real-browser checks for Search UX 4.2 and 4.4 Stage 1."""

from __future__ import annotations

import http.server
import threading
import sys
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse
from urllib.parse import parse_qs

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

    format25a_path = None

    def search(query: str):
        try:
            if query == "25a":
                page.goto(f"{base}/")
                searchbox = page.get_by_role("combobox", name="全文搜尋")
                assert page.locator(".search-result").count() == 0, "Raw 25a must start without previous query results"
                searchbox.fill("25a")
                searchbox.press("Enter")
                page.wait_for_url(lambda url: parse_qs(urlparse(url).query).get("q") == ["25a"], timeout=10000)
            else:
                page.goto(f"{base}/?q={quote(query, safe='')}")
            page.locator(".search-result").first.wait_for(timeout=10000)
            page.wait_for_timeout(120)
            first = page.locator(".search-result").first
            href = first.locator("h3 a").get_attribute("href")
            reasons = [r.text_content().strip() for r in page.locator(".match-reason").all()]
            if query == "25a":
                assert searchbox.input_value() == "25a", "Raw query must remain unchanged in the searchbox"
                assert parse_qs(urlparse(page.url).query).get("q") == ["25a"], "URL q must remain the raw 25a query"
                path = urlparse(urljoin(f"{base}/", href)).path
                assert format25a_path is not None and path == format25a_path, f"Raw 25a must use the same formal reading target as 格式25A: {path}"
                first_reasons = [r.text_content().strip() for r in first.locator(".match-reason").all()]
                exact_reason = next((reason for reason in first_reasons if "書表編號完全符合「25a」" in reason), None)
                assert exact_reason is not None, f"First result must have raw 25a exact-form reason: {first_reasons}"
                recovery_count = page.locator(".search-zero-recovery").count()
                assert recovery_count == 0, "Nonzero raw 25a search must not show recovery"
                print(f"[{width}px] RAW_25A_UI PASS query={searchbox.input_value()} target={href} reason={exact_reason} recovery={recovery_count}", flush=True)
            return first, href, reasons
        except Exception:
            if query == "25a":
                page.screenshot(path=f"/tmp/search_ux_4_4_raw25a_{width}_failure.png", full_page=True)
                Path(f"/tmp/search_ux_4_4_raw25a_{width}_failure.html").write_text(page.content(), encoding="utf-8")
            raise

    # 1. Canonical form variants resolve to their exact target and retain the raw query in the reason.
    form_cases = [
        ("格式25A", "form-25a.html"),
        ("格式25 A", "form-25a.html"),
        ("格式 ２５ Ａ", "form-25a.html"),
        ("格式 25 a", "form-25a.html"),
        ("25a", "form-25a.html"),
        ("格式25B", "form-25b.html"),
        ("格式 25 B", "form-25b.html"),
        ("格式25C", "form-25c.html"),
        ("格式 25 C", "form-25c.html"),
        ("格式3 - 1", "form-3-1.html"),
        ("格式 3 - 1 A", "form-3-1a.html"),
    ]
    for query, expected_target in form_cases:
        first, href, reason_texts = search(query)
        path = urlparse(urljoin(f"{base}/", href)).path
        assert path.endswith(expected_target), f"{query} should rank {expected_target} first, got {path}"
        if query == "格式25A":
            format25a_path = path
        assert any(f"書表編號完全符合「{query}」" in text for text in reason_texts), f"Exact reason must preserve raw query {query!r}: {reason_texts}"
        assert first.locator(".result-match-reasons").is_visible(), "result-match-reasons should be visible"
    assert page.locator(".result-match-meta").count() == 0, "Old result-match-meta must not exist"
    assert page.locator(".search-hit").count() > 0, "Search hit highlights should exist"

    # 2. Concept expansion (抵押品)
    first_res, collateral_url, collateral_reasons = search("抵押品")
    collateral_title = first_res.locator("h3 a").text_content().strip()
    print(f"[{width}px] 抵押品 matched result: title='{collateral_title}', url='{collateral_url}', reasons={collateral_reasons}")
    assert any("相關詞「抵押品」→「擔保品」" in text for text in collateral_reasons), f"Expected concept expansion reason for 抵押品, got: {collateral_reasons}"

    # 3. Direct heading / Direct body (代償利息)
    _, _, reason_texts = search("代償利息")
    assert any("章節標題命中「代償利息」" in text or "正文直接命中「代償利息」" in text for text in reason_texts), f"Expected direct match for 代償利息, got: {reason_texts}"

    # 4. Multi-token (青農 保證成數)
    _, _, reason_texts = search("青農 保證成數")
    assert any("青農" in text for text in reason_texts), f"Expected reason for 青農, got: {reason_texts}"
    assert any("保證成數" in text for text in reason_texts), f"Expected reason for 保證成數, got: {reason_texts}"

    # 5. 第4 remains a general query; 4.3 typo recovery still works.
    _, _, reason_texts = search("第4")
    assert len(reason_texts) > 0, "第4 should remain a general search query"
    page.goto(f"{base}/?q={quote('代位清嘗', safe='')}")
    page.locator(".search-zero-recovery").wait_for(timeout=10000)
    assert "代位清償" in page.locator(".search-zero-recovery").text_content(), "UX 4.3 typo recovery should remain visible"

    # 6. Horizontal overflow check at every target viewport.
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
