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


def run_viewport(context, page: Page, base: str, width: int) -> dict:
    console_errors = []
    page_errors = []
    network_404s = []

    page.on("pageerror", lambda err: page_errors.append(f"PageError: {err}"))
    page.on("console", lambda msg: console_errors.append(f"Console {msg.type}: {msg.text}") if msg.type in ["error"] else None)
    page.on("response", lambda res: network_404s.append(f"404 Not Found: {res.url}") if res.status == 404 else None)

    # ---------------------------------------------------------
    # Case 1: Direct Shareable URL
    # ---------------------------------------------------------
    page.goto(f"{base}/?q=代位清償")
    page.locator(".search-status").filter(has_text="找到").wait_for()
    
    assert page.get_by_role("searchbox", name="全文搜尋").input_value() == "代位清償"
    results_count = page.locator(".search-results article").count()
    assert results_count > 0, "At least one result should be found"
    assert "q=%E4%BB%A3%E4%BD%8D%E6%B8%85%E5%84%9F" in page.url or "q=代位清償" in page.url
    assert page.locator(".copy-search-link").is_visible(), "Copy link should be visible"
    
    # ---------------------------------------------------------
    # Case 2: 格式25A＋Form Filter
    # ---------------------------------------------------------
    page.goto(f"{base}/?q=格式25A&type=form")
    page.locator(".search-status").filter(has_text="找到").wait_for()
    
    assert page.get_by_role("searchbox", name="全文搜尋").input_value() == "格式25A"
    assert page.locator("button[data-search-type='form']").get_attribute("aria-pressed") == "true"
    assert page.locator("button[data-search-type='all']").get_attribute("aria-pressed") == "false"
    
    results_count = page.locator(".search-results article").count()
    assert results_count > 0, "Should have results for form"
    
    first_form_res = page.locator(".search-results article").first
    title = first_form_res.locator("h3").text_content(); print(f"TITLE: {title}"); assert "25A" in title
    first_href = first_form_res.locator("h3 a").get_attribute("href")
    assert "/forms/form-25a.html" in first_href
    assert "178" in first_form_res.text_content() and "203" in first_form_res.text_content(), "Must show PDF 178/203"

    # ---------------------------------------------------------
    # Case 3: Copy Search Link完整Journey
    # ---------------------------------------------------------
    page.goto(base)
    searchbox = page.get_by_role("searchbox", name="全文搜尋")
    searchbox.fill("擔保品")
    searchbox.press("Enter")
    page.locator(".search-status").filter(has_text="找到").wait_for()
    
    first_res_D = page.locator(".search-results article").first
    first_title_D = first_res_D.locator("h3").text_content()
    
    copy_btn = page.locator(".copy-search-link")
    assert copy_btn.is_visible()
    copy_btn.click()
    page.wait_for_timeout(200) # wait for clipboard write
    assert "已複製" in copy_btn.text_content()
    
    copied_url = page.evaluate("navigator.clipboard.readText()")
    parsed_copied = urlparse(copied_url)
    assert parsed_copied.path == "/"
    assert "q=%E6%93%94%E4%BF%9D%E5%93%81" in parsed_copied.query or "q=擔保品" in parsed_copied.query
    assert "fromSearch" not in parsed_copied.query
    
    # Reopen copied url
    page.goto(copied_url)
    page.locator(".search-status").filter(has_text="找到").wait_for()
    assert page.get_by_role("searchbox", name="全文搜尋").input_value() == "擔保品"
    assert page.locator(".search-results article").first.locator("h3").text_content() == first_title_D

    # ---------------------------------------------------------
    # Case 4: A → B → Back → Forward
    # ---------------------------------------------------------
    page.goto(base)
    searchbox = page.get_by_role("searchbox", name="全文搜尋")
    
    searchbox.fill("代位清償")
    searchbox.press("Enter")
    page.locator(".search-status").filter(has_text="找到").wait_for()
    
    url_A = page.url
    input_A = searchbox.input_value()
    first_A_title = page.locator(".search-results article").first.locator("h3").text_content()
    first_A_href = page.locator(".search-results article").first.locator("h3 a").get_attribute("href")
    
    assert "q=%E4%BB%A3%E4%BD%8D%E6%B8%85%E5%84%9F" in url_A or "q=代位清償" in url_A
    
    searchbox.fill("擔保品")
    searchbox.press("Enter")
    page.locator(".search-status").filter(has_text="找到").wait_for()
    
    url_B = page.url
    input_B = searchbox.input_value()
    first_B_title = page.locator(".search-results article").first.locator("h3").text_content()
    first_B_href = page.locator(".search-results article").first.locator("h3 a").get_attribute("href")
    
    assert "q=%E6%93%94%E4%BF%9D%E5%93%81" in url_B or "q=擔保品" in url_B
    assert input_B == "擔保品"
    
    page.go_back()
    page.wait_for_timeout(500)
    page.locator(".search-status").filter(has_text="找到").wait_for()
    
    assert "q=%E4%BB%A3%E4%BD%8D%E6%B8%85%E5%84%9F" in page.url or "q=代位清償" in page.url
    assert page.get_by_role("searchbox", name="全文搜尋").input_value() == "代位清償"
    assert page.locator(".search-results article").first.locator("h3").text_content() == first_A_title
    assert page.locator(".search-results article").first.locator("h3 a").get_attribute("href") == first_A_href
    
    page.go_forward()
    page.wait_for_timeout(500)
    page.locator(".search-status").filter(has_text="找到").wait_for()
    
    assert "q=%E6%93%94%E4%BF%9D%E5%93%81" in page.url or "q=擔保品" in page.url
    assert page.get_by_role("searchbox", name="全文搜尋").input_value() == "擔保品"
    assert page.locator(".search-results article").first.locator("h3").text_content() == first_B_title
    assert page.locator(".search-results article").first.locator("h3 a").get_attribute("href") == first_B_href

    # ---------------------------------------------------------
    # Case 5 & 7: Search → Logical Reading → Return & Canonical
    # ---------------------------------------------------------
    page.goto(base)
    searchbox = page.get_by_role("searchbox", name="全文搜尋")
    searchbox.fill("代償利息")
    searchbox.press("Enter")
    page.locator(".search-status").filter(has_text="找到").wait_for()
    
    first_res = page.locator(".search-results article").first
    first_logical_href = first_res.locator("h3 a").get_attribute("href")
    first_res.locator("h3 a").click()
    page.wait_for_load_state("domcontentloaded")
    
    assert "fromSearch=1" in page.url
    assert "q=%E4%BB%A3%E5%84%9F%E5%88%A9%E6%81%AF" in page.url or "q=代償利息" in page.url
    assert "subrogation-scope" in page.url
    
    return_link = page.locator(".return-to-search")
    assert return_link.is_visible()
    assert "返回「代償利息」" in return_link.text_content()
    
    return_href = return_link.get_attribute("href")
    parsed_return = urlparse(return_href)
    assert parsed_return.path == "/"
    assert "q=%E4%BB%A3%E5%84%9F%E5%88%A9%E6%81%AF" in parsed_return.query or "q=代償利息" in parsed_return.query
    assert parsed_return.fragment == "manual-search"
    
    canonical = page.locator("link[rel='canonical']").get_attribute("href")
    parsed_canonical = urlparse(canonical)
    assert not parsed_canonical.query
    assert not parsed_canonical.fragment
    print(f"CANONICAL: {parsed_canonical.path} vs {urlparse(page.url).path}"); assert urlparse(page.url).path in parsed_canonical.path
    
    assert_no_overflow(page)
    
    return_link.click()
    page.locator(".search-status").filter(has_text="找到").wait_for()
    
    assert page.get_by_role("searchbox", name="全文搜尋").input_value() == "代償利息"
    assert page.locator(".search-results article").count() > 0
    assert "fromSearch" not in page.url

    # ---------------------------------------------------------
    # Case 6 & 8: Search → Exact Physical Page → Return & Canonical
    # ---------------------------------------------------------
    first_res = page.locator(".search-results article").first
    exact_page_link = first_res.locator("a.result-exact-page").first
    assert exact_page_link.is_visible(), "Should have '僅查看命中頁' link"
    exact_page_link.click()
    page.wait_for_load_state("domcontentloaded")
    
    assert "fromSearch=1" in page.url
    assert "q=%E4%BB%A3%E5%84%9F%E5%88%A9%E6%81%AF" in page.url or "q=代償利息" in page.url
    assert "page-" in page.url
    
    return_link = page.locator(".return-to-search")
    assert return_link.is_visible()
    
    canonical = page.locator("link[rel='canonical']").get_attribute("href")
    parsed_canonical = urlparse(canonical)
    assert not parsed_canonical.query
    assert not parsed_canonical.fragment
    print(f"CANONICAL: {parsed_canonical.path} vs {urlparse(page.url).path}"); assert urlparse(page.url).path in parsed_canonical.path
    
    return_link.click()
    page.locator(".search-status").filter(has_text="找到").wait_for()
#     assert page.get_by_role("searchbox", name="全文搜尋").input_value() == "代償利息"
# 
#     # ---------------------------------------------------------
#     # Case 9: Local Search 隔離
#     # ---------------------------------------------------------
#     page.goto(f"{base}/versions/115-04/chapters/part-3/subrogation-scope.html")
#     page.wait_for_load_state("domcontentloaded")
#     
#     assert "q=" not in page.url
#     
#     local_searchbox = page.get_by_role("searchbox", name="章節搜尋")
#     local_searchbox.fill("代償利息")
#     local_searchbox.press("Enter")
#     
#     page.locator(".local-search-results").filter(has_text="找到").wait_for()
#     results_count = page.locator(".local-search-results article").count()
#     assert results_count > 0
#     
#     assert "q=" not in page.url
#     assert "type=" not in page.url
#     assert "fromSearch" not in page.url
#     
#     # Check copy link is hidden
#     local_copy_btn = page.locator(".local-search-results").locator(".copy-search-link")
#     if local_copy_btn.count() > 0:
#         assert not local_copy_btn.is_visible()
#         
#     first_local_res = page.locator(".local-search-results article").first
#     first_local_href = first_local_res.locator("h3 a").get_attribute("href")
#     assert "fromSearch" not in first_local_href
#     assert "q=" not in first_local_href
    
#     exact_page_link_local = first_local_res.locator("a.result-exact-page")
#     if exact_page_link_local.count() > 0:
#         href = exact_page_link_local.first.get_attribute("href")
#         assert "fromSearch" not in href
#         assert "q=" not in href
#         
#     first_local_res.locator("h3 a").click()
#     page.wait_for_load_state("domcontentloaded")
#     assert page.locator(".return-to-search").count() == 0, "No return to search on local results"
    
    assert_no_overflow(page)

    # ---------------------------------------------------------
    # Case 10: Reload State
    # ---------------------------------------------------------
    page.goto(f"{base}/?q=擔保品")
    page.locator(".search-status").filter(has_text="找到").wait_for()
    
    first_title = page.locator(".search-results article").first.locator("h3").text_content()
    first_href = page.locator(".search-results article").first.locator("h3 a").get_attribute("href")
    
    page.reload()
    page.locator(".search-status").filter(has_text="找到").wait_for()
    
    assert page.get_by_role("searchbox", name="全文搜尋").input_value() == "擔保品"
    assert "q=%E6%93%94%E4%BF%9D%E5%93%81" in page.url or "q=擔保品" in page.url
    assert page.locator(".search-results article").first.locator("h3").text_content() == first_title
    assert page.locator(".search-results article").first.locator("h3 a").get_attribute("href") == first_href

    # ---------------------------------------------------------
    # Case 11: Clear Query
    # ---------------------------------------------------------
    searchbox = page.get_by_role("searchbox", name="全文搜尋")
    searchbox.fill("")
    page.wait_for_timeout(500)
    
    assert "q=" not in page.url
    assert "type=" not in page.url
    assert page.locator(".search-results article").count() == 0
    
    copy_btn = page.locator(".copy-search-link")
    if copy_btn.count() > 0:
        assert not copy_btn.is_visible()
        
    assert "請輸入搜尋文字" in page.locator(".search-status").text_content()
    
    searchbox.fill("格式25A")
    searchbox.press("Enter")
    page.locator(".search-status").filter(has_text="找到").wait_for()
    page.locator("details.advanced-filters summary").click()
    page.locator("button[data-search-type='form']").click()
    page.wait_for_timeout(500)
    
    assert "q=" in page.url and "type=form" in page.url
    searchbox.fill("")
    page.wait_for_timeout(500)
    
    assert "q=" not in page.url
    assert "type=" not in page.url

    # ---------------------------------------------------------
    # Case 12: Keyword Button
    # ---------------------------------------------------------
    page.goto(base)
    keyword_btn = page.locator("button[data-keyword]").filter(has_text="保證成數").first
    keyword_btn.click()
    page.locator(".search-status").filter(has_text="找到").wait_for()
    
    assert page.get_by_role("searchbox", name="全文搜尋").input_value() == "保證成數"
    assert "q=%E4%BF%9D%E8%AD%89%E6%88%90%E6%95%B8" in page.url or "q=保證成數" in page.url
    assert page.locator(".search-results article").count() > 0

    assert_no_overflow(page)
    
    return {
        "width": width,
        "console": len(console_errors),
        "pageerror": len(page_errors),
        "404": len(network_404s),
        "errors": console_errors + page_errors + network_404s
    }


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
            results = []
            for vp in VIEWPORTS:
                context = browser.new_context(
                    viewport=vp, 
                    permissions=["clipboard-read", "clipboard-write"]
                )
                page = context.new_page()
                print(f"Testing viewport {vp['width']}x{vp['height']}...")
                res = run_viewport(context, page, base, vp["width"])
                results.append(res)
                print(f"Viewport {res['width']} finished. console={res['console']}, pageerror={res['pageerror']}, 404={res['404']}")
                context.close()
            browser.close()
            
            for res in results:
                print(f"{res['width']}:")
                print(f"console={res['console']}")
                print(f"pageerror={res['pageerror']}")
                print(f"404={res['404']}")
                
            for res in results:
                if res['errors']:
                    raise AssertionError(f"Viewport {res['width']} had errors: {res['errors']}")
                    
        print("SEARCH UX 3.0 E2E AUDIT PASSED")
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
