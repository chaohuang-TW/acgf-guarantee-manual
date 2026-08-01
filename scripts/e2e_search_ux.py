#!/usr/bin/env python3
"""Responsive real-browser E2E checks for Search UX 3.0."""

from __future__ import annotations

import http.server
import threading
from pathlib import Path
from urllib.parse import urlparse

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
    title = first_form_res.locator("h3").text_content()
    if "格式25A" not in title:
        assert "25A" in title
    assert "書表" in first_form_res.text_content()
    first_href = first_form_res.locator("h3 a").get_attribute("href")
    assert "/forms/form-25a.html" in first_href
    assert "PDF頁：178／203" in first_form_res.text_content()

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

    import os
    base_path = os.environ.get("SITE_BASE_PATH", "/acgf-guarantee-manual/")
    expected_canonical_path = urlparse(page.url).path
    if base_path != "/":
        expected_canonical_path = base_path.rstrip("/") + expected_canonical_path

    assert not parsed_canonical.query
    assert not parsed_canonical.fragment
    assert parsed_canonical.path == expected_canonical_path

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
    first_logical_href = first_res.locator("h3 a").get_attribute("href")
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

    import os
    base_path = os.environ.get("SITE_BASE_PATH", "/acgf-guarantee-manual/")
    expected_canonical_path = urlparse(page.url).path
    if base_path != "/":
        expected_canonical_path = base_path.rstrip("/") + expected_canonical_path

    assert not parsed_canonical.query
    assert not parsed_canonical.fragment
    assert parsed_canonical.path == expected_canonical_path

    return_link.click()
    page.locator(".search-status").filter(has_text="找到").wait_for()

    assert page.get_by_role("searchbox", name="全文搜尋").input_value() == "代償利息"
    assert "q=%E4%BB%A3%E5%84%9F%E5%88%A9%E6%81%AF" in page.url or "q=代償利息" in page.url
    assert "fromSearch" not in page.url
    assert page.locator(".search-results article").count() > 0
    assert page.locator(".search-results article").first.locator("h3 a").get_attribute("href") == first_logical_href

    # ---------------------------------------------------------
    # UX 4.0: Autocomplete & Typeahead
    # ---------------------------------------------------------
    page.goto(base)
    searchbox = page.get_by_role("searchbox", name="全文搜尋")
    searchbox.fill("代位")
    page.wait_for_selector(".search-suggestions li", state="visible")
    
    suggestions = page.locator(".search-suggestions li")
    assert suggestions.count() > 0, "Should show autocomplete suggestions for '代位'"
    
    # Keyboard navigation
    searchbox.press("ArrowDown")
    active_suggestion = page.locator(".search-suggestions li.active")
    assert active_suggestion.count() == 1, "Should highlight one suggestion on ArrowDown"
    assert searchbox.get_attribute("aria-activedescendant") == active_suggestion.get_attribute("id")
    
    searchbox.press("Enter")
    page.locator(".search-status").filter(has_text="找到").wait_for()
    assert searchbox.input_value() == active_suggestion.text_content(), "Enter should fill searchbox with selected suggestion and search"
    assert page.locator(".search-suggestions").is_hidden(), "Suggestions should be hidden after Enter"

    # ---------------------------------------------------------
    # UX 4.0: Dynamic Filter Badges
    # ---------------------------------------------------------
    chapter_btn = page.locator("button[data-search-type='chapter']")
    assert "(" in chapter_btn.text_content(), "Filter buttons should have a badge count"
    
    # Empty filter should be disabled
    searchbox.fill("完全不會找到的字串測試容錯機制")
    searchbox.press("Enter")
    page.wait_for_function('document.querySelector(".search-status").textContent.includes("找不到")')
    assert chapter_btn.is_disabled(), "Chapter button should be disabled when it has 0 results"
    
    # ---------------------------------------------------------
    # UX 4.0: Fuzzy Search (Typo Tolerance via concept expansion)
    # ---------------------------------------------------------
    searchbox.fill("帶償")
    searchbox.press("Enter")
    page.locator(".search-status").filter(has_text="找到").wait_for()
    
    first_fuzzy_res = page.locator(".search-results article").first
    assert first_fuzzy_res.locator("mark.search-hit").count() > 0, "Should highlight hits even when fuzzy matching via '帶償'"

    # ---------------------------------------------------------
    # UX 4.0: Infinite Scroll (Virtualization)
    # ---------------------------------------------------------
    searchbox.fill("保證") # Very common word to trigger > 50 results
    searchbox.press("Enter")
    page.locator(".search-status").filter(has_text="找到").wait_for()
    
    initial_articles = page.locator(".search-results article").count()
    assert initial_articles <= 50, f"Should limit initial render, got {initial_articles}"
    
    # Scroll to bottom to trigger intersection observer
    page.locator(".search-sentinel").scroll_into_view_if_needed()
    page.wait_for_function('document.querySelectorAll(".search-results article").length > 50', timeout=2000)
    
    scrolled_articles = page.locator(".search-results article").count()
    assert scrolled_articles > 50, "Should automatically load more results on scroll"



    # ---------------------------------------------------------
    # Case 9: Local Search Reality Assertion
    # ---------------------------------------------------------
    # No local-search UI is currently generated; local-scope runtime code is not exercised by production HTML.
    page.goto(f"{base}/versions/115-04/chapters/part-3/subrogation-scope.html")
    page.wait_for_load_state("domcontentloaded")

    assert page.locator("[data-search-scope]").count() == 0, "Production HTML should not contain [data-search-scope]"
    assert page.get_by_role("searchbox", name="章節搜尋").count() == 0, "Production HTML should not contain local searchbox"

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


    # ---------------------------------------------------------
    # Case 13: Query Match Highlighting
    # ---------------------------------------------------------
    # A. 搜尋「代位清償」 (Title Hit)
    page.goto(base)
    searchbox = page.get_by_role("searchbox", name="全文搜尋")
    searchbox.fill("代位清償")
    searchbox.press("Enter")
    page.locator(".search-status").filter(has_text="找到").wait_for()

    first_res = page.locator(".search-results article").first
    title_link = first_res.locator("h3 a")
    title_marks = title_link.locator("mark.search-hit")

    assert title_marks.count() >= 1
    assert "代位清償" in title_marks.all_text_contents()
    assert title_link.text_content() == "壹、代位清償要件"
    first_href = title_link.get_attribute("href")
    assert "subrogation-requirements.html" in first_href

    # 點擊 title mark
    title_marks.first.click()
    page.wait_for_load_state("domcontentloaded")
    assert "subrogation-requirements.html" in page.url
    assert "fromSearch=1" in page.url
    assert "q=" in page.url
    assert "pdf-page" in page.url

    # 檢查 snippet mark (回到搜尋結果)
    page.go_back()
    page.locator(".search-status").filter(has_text="找到").wait_for()
    first_res = page.locator(".search-results article").first
    snippet = first_res.locator(".result-snippet")
    assert snippet.locator("mark.search-hit").count() > 0
    mark_texts = snippet.locator("mark.search-hit").all_text_contents()
    assert "代位清償" in mark_texts

    # B. 多詞搜尋
    page.goto(base)
    searchbox = page.get_by_role("searchbox", name="全文搜尋")
    searchbox.fill("信用 保證")
    searchbox.press("Enter")
    page.locator(".search-status").filter(has_text="找到").wait_for()

    marks = page.locator(".search-results article").first.locator("mark.search-hit").all_text_contents()
    assert any("信用" in m for m in marks)
    assert any("保證" in m for m in marks)
    assert page.evaluate('document.querySelectorAll("mark mark").length') == 0
    assert page.locator(".search-results article").first.locator("h3 a").is_visible()

    # D. 特殊字元
    page.goto(base)
    searchbox = page.get_by_role("searchbox", name="全文搜尋")
    searchbox.fill("<>&\"'[]()\\.*")
    searchbox.press("Enter")
    page.wait_for_timeout(500)
    assert page.locator(".search-status").is_visible()

    assert page.locator(".search-results script").count() == 0
    assert page.locator(".search-results img").count() == 0
    assert console_errors == []
    assert page_errors == []

    # E. 清除搜尋
    searchbox.fill("")
    page.wait_for_timeout(500)
    assert page.locator(".search-hit").count() == 0

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
            browser = p.chromium.launch(channel="chrome")
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
