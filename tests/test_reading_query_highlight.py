import sys
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

def run_tests():
    base_dir = Path(__file__).parent.parent
    search_js = (base_dir / "assets/js/search.js").read_text()
    site_js = (base_dir / "assets/js/site.js").read_text()

    html_template = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
      <meta charset="utf-8">
      <script>{search_js}</script>
      <script>{site_js}</script>
    </head>
    <body>
      <div class="page-card" id="pdf-page-46">
        <div class="display-text">測試代償利息，以及代償利息，第二行。還有PDF跟pdf以及Pdf。長詞優先測試：信用保證與信用保證基金。特殊字元：100%。XSS：&lt;script&gt;alert(1)&lt;/script&gt;。包含 inline <strong>strong</strong> text。</div>
        <div class="raw-text-details">這個不應該被highlight: 代償利息</div>
      </div>
      <div class="page-card" id="pdf-page-47">
        <div class="display-text">第二頁也有代償利息。</div>
      </div>
      <script>
        function runHighlight() {{
          // Re-evaluate the highlight logic manually if needed
          window.SiteUtils.initInPageSearchHighlight();
        }}
      </script>
    </body>
    </html>
    """

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()

        def route_handler(route):
            route.fulfill(content_type="text/html", body=html_template)

        context.route("**/*", route_handler)
        page = context.new_page()

        def evaluate_test(query, target_hash=""):
            page.goto(f"http://test.local/?fromSearch=1&q={query}{target_hash}")
            page.evaluate("runHighlight()")
            page.wait_for_timeout(150) # wait for setTimeout in initInPageSearchHighlight

            # get hits
            hits = page.evaluate('Array.from(document.querySelectorAll(".reading-hit")).map(el => el.textContent)')
            nav_count = page.evaluate('document.querySelectorAll(".reading-hit-nav").length')
            current = page.evaluate('Array.from(document.querySelectorAll(".reading-hit-current")).map(el => el.textContent)')
            disabled_prev = page.evaluate('document.querySelector(".reading-hit-prev")?.disabled')
            disabled_next = page.evaluate('document.querySelector(".reading-hit-next")?.disabled')
            counter_text = page.evaluate('document.querySelector(".reading-hit-count")?.textContent')
            raw_text_hits = page.evaluate('document.querySelectorAll(".raw-text-details .reading-hit").length')
            strong_text = page.evaluate('document.querySelector("strong")?.textContent')

            return {
                "hits": hits,
                "nav_count": nav_count,
                "current": current,
                "disabled_prev": disabled_prev,
                "disabled_next": disabled_next,
                "counter_text": counter_text,
                "raw_text_hits": raw_text_hits,
                "strong_text": strong_text
            }

        print("Running tests...")

        # 1. 中文單詞 & 2. 重複命中
        res = evaluate_test("代償利息")
        assert len(res["hits"]) == 3, f"Expected 3 hits for 代償利息, got {len(res['hits'])}"
        assert res["nav_count"] == 1, "nav bar should appear"
        assert len(res["current"]) == 1, "current should be 1"
        assert res["disabled_prev"] is True, "prev should be disabled on first hit"
        assert res["disabled_next"] is False, "next should be enabled"
        assert res["counter_text"] == "1 / 3", f"counter should be 1 / 3, got {res['counter_text']}"
        assert res["raw_text_hits"] == 0, "raw-text-details should not be highlighted"

        # 3. 多詞
        res = evaluate_test("測試 代償利息")
        assert len(res["hits"]) >= 4, "Should highlight both words"

        # 4. PDF/pdf/Pdf
        res = evaluate_test("pdf")
        assert len(res["hits"]) == 3, "Case-insensitive PDF match failed"
        assert res["hits"] == ["PDF", "pdf", "Pdf"], f"Got {res['hits']}"

        # 5. 長詞優先
        res = evaluate_test("信用保證 信用保證基金")
        assert "信用保證基金" in res["hits"], "Long word should be matched as one hit"

        # 6. 特殊字元
        res = evaluate_test("100%")
        assert res["hits"] == ["100%"]

        # 7. XSS
        res = evaluate_test("<script>alert(1)</script>")
        assert "<script>alert(1)</script>" in res["hits"]
        assert "1" in res["hits"]

        # 8. 空query
        res = evaluate_test("")
        assert len(res["hits"]) == 0

        # 9. 無命中
        res = evaluate_test("找不到的詞")
        assert len(res["hits"]) == 0
        assert res["nav_count"] == 0

        # 10. textContent preservation & 11. inline strong preservation
        res = evaluate_test("inline")
        assert res["strong_text"] == "strong", "Strong tag should be preserved"

        # 12. raw-text-details不得highlight (tested in 1)

        # 13. double init
        page.goto("http://test.local/?fromSearch=1&q=代償利息")
        page.evaluate("runHighlight()")
        page.evaluate("runHighlight()")
        page.wait_for_timeout(150)
        hits = page.evaluate('document.querySelectorAll(".reading-hit").length')
        nav_count = page.evaluate('document.querySelectorAll(".reading-hit-nav").length')
        assert hits == 3, "Double init should not increase hit count"
        assert nav_count == 1, "Double init should not duplicate nav bar"

        # 14. current唯一 (tested in 1)

        # 15. Prev boundary & 16. Next boundary
        page.goto("http://test.local/?fromSearch=1&q=代償利息")
        page.evaluate("runHighlight()")
        page.wait_for_timeout(150)

        # click next
        page.click(".reading-hit-next")
        page.wait_for_timeout(50)
        current = page.evaluate('document.querySelectorAll(".reading-hit-current").length')
        counter = page.evaluate('document.querySelector(".reading-hit-count").textContent')
        assert current == 1
        assert counter == "2 / 3"

        # click next again (at 3)
        page.click(".reading-hit-next")
        page.wait_for_timeout(50)
        assert page.evaluate('document.querySelector(".reading-hit-next").disabled') is True

        # click prev back to 1
        page.click(".reading-hit-prev")
        page.click(".reading-hit-prev")
        page.wait_for_timeout(50)
        assert page.evaluate('document.querySelector(".reading-hit-prev").disabled') is True

        # 17. 1/1兩邊disabled
        res = evaluate_test("100%") # only 1 hit
        assert res["disabled_prev"] is True
        assert res["disabled_next"] is True
        assert res["counter_text"] == "1 / 1"

        # Initial target jump
        page.goto("http://test.local/?fromSearch=1&q=代償利息#pdf-page-47")
        page.evaluate("runHighlight()")
        page.wait_for_timeout(150)
        counter = page.evaluate('document.querySelector(".reading-hit-count").textContent')
        assert counter == "3 / 3", "Should jump to the hit inside pdf-page-47"

        print("All 17 conditions passed!")
        browser.close()

if __name__ == "__main__":
    run_tests()
