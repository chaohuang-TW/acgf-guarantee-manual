#!/usr/bin/env python3
import sys
import http.server
import threading
from pathlib import Path
from playwright.sync_api import sync_playwright, expect, Page

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"

class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass

def run():
    print("Starting Related Forms E2E...")

    server = http.server.HTTPServer(("127.0.0.1", 0), lambda *args: QuietHandler(*args, directory=str(SITE)))
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{port}"
    print(f"Server started at {base_url}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            viewports = [
                {"width": 390, "height": 900},
                {"width": 768, "height": 900},
                {"width": 1440, "height": 1000}
            ]

            for vp in viewports:
                print(f"Testing viewport {vp['width']}x{vp['height']}")
                context = browser.new_context(viewport=vp)
                page = context.new_page()

                # Journey A: 肆、申請信用保證作業
                page.goto(f"{base_url}/versions/115-04/chapters/part-1/guarantee-application.html")

                # Wait for related forms section
                section = page.locator(".related-forms")
                expect(section).to_be_visible()

                # Ensure at least one verified form is present
                form_link = section.locator(".related-form-card").first
                expect(form_link).to_be_visible()

                # Click the form link
                form_link.click()

                # Now we should be on the form page
                expect(page.locator("h1")).to_contain_text("格式")

                # Check related-rules section
                rules_section = page.locator(".related-rules")
                expect(rules_section).to_be_visible()

                # Click the rule back
                rule_link = rules_section.locator("a", has_text="肆、申請信用保證作業").first
                rule_link.click()

                # Now we should be back on the rule page
                expect(page.locator("h1")).to_have_text("肆、申請信用保證作業")

                # Journey B: 參、代位清償應檢送文件
                page.goto(f"{base_url}/versions/115-04/chapters/part-3/subrogation-documents.html")
                section = page.locator(".related-forms")
                expect(section).to_be_visible()

                # Check expected forms
                for f in ["25", "25A", "25B", "25C", "26-1"]:
                    expect(section.locator(f".related-form-number:text-is('格式{f}')")).to_be_visible()

                # Ensure 26 is NOT present
                expect(section.locator(f".related-form-number:text-is('格式26')")).not_to_be_visible()

                # Journey C: Search "代位清償應檢送文件"
                page.goto(f"{base_url}/index.html?q=代位清償應檢送文件")

                # Wait for search results
                result = page.locator(".search-result").filter(has_text="參、代位清償應檢送文件").first
                expect(result).to_be_visible()

                # Click to enter reading page
                result.locator("h3 a").click()

                # Wait for reading hits
                page.locator(".reading-hit").first.wait_for(timeout=5000)

                # Check related forms exists
                rel_forms = page.locator(".related-forms")
                expect(rel_forms).to_be_visible()

                # Ensure NO reading-hit inside related forms
                expect(rel_forms.locator(".reading-hit")).to_have_count(0)

                # Check Return Search link
                return_link = page.locator(".return-to-search")
                expect(return_link).to_be_visible()

                context.close()

            browser.close()
        print("E2E passed.")
    finally:
        server.shutdown()
        server.server_close()

if __name__ == "__main__":
    run()
