#!/usr/bin/env python3
"""Real-browser, presentation-contract checks for Experience Redesign 1.0.

This complements, rather than replaces, the repository's existing full CI.
Evidence is written outside the checkout. Desktop browser emulation is not
represented as real-device or real-user acceptance.
"""

from __future__ import annotations

import http.server
import json
import os
import sys
import threading
import traceback
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from playwright.sync_api import Page, expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
EVIDENCE = Path(os.environ.get("EXPERIENCE_EVIDENCE_DIR", "/tmp/manual-experience-redesign/e2e"))
AXE_PATH = Path(os.environ.get("AXE_PATH", "/tmp/manual-redesign-tooling/node_modules/axe-core/axe.min.js"))
CACHE = Path.home() / "Library/Caches/ms-playwright"
VIEWPORTS = [
    {"width": 320, "height": 900},
    {"width": 390, "height": 900},
    {"width": 768, "height": 1024},
    {"width": 1024, "height": 900},
    {"width": 1440, "height": 1000},
    {"width": 1920, "height": 1080},
    {"width": 844, "height": 390},
]
sys.path.insert(0, str(ROOT / "scripts"))
from reading_units import load_resolved_units  # noqa: E402


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


def overflow(page: Page) -> None:
    dimensions = page.evaluate("() => ({width: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth})")
    assert dimensions["scroll"] <= dimensions["width"] + 1, f"Horizontal overflow: {dimensions}; {page.url}"


def no_duplicate_ids(page: Page) -> None:
    duplicates = page.evaluate("""() => {
      const ids = [...document.querySelectorAll('[id]')].map(node => node.id);
      return [...new Set(ids.filter((id, index) => ids.indexOf(id) !== index))];
    }""")
    assert not duplicates, f"Duplicate DOM IDs: {duplicates}"


def assert_keyboard_toolbar_clear(page: Page) -> None:
    page.locator(".skip-link").focus()
    for _ in range(80):
        page.keyboard.press("Tab")
        page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
        obstruction = page.evaluate("""() => {
          const focus = document.activeElement;
          const tools = document.querySelector('[data-reading-tools]');
          if (!focus || !tools || tools.contains(focus) || focus.closest('dialog') || !focus.matches('a,button,input,select,textarea,summary')) return null;
          const a = focus.getBoundingClientRect(), b = tools.getBoundingClientRect();
          if (a.bottom <= 0 || a.top >= innerHeight) return {tag: focus.tagName, text: focus.textContent, offscreen: {top:a.top,bottom:a.bottom}};
          if (getComputedStyle(tools).position !== 'fixed') return null;
          return a.right > b.left && a.left < b.right && a.bottom > b.top && a.top < b.bottom
            ? {tag: focus.tagName, text: focus.textContent, focus: {top:a.top,bottom:a.bottom}, toolbar: {top:b.top,bottom:b.bottom}} : null;
        }""")
        assert obstruction is None, f"Keyboard focus obscured by toolbar: {obstruction}"


def monitor(page: Page, diagnostics: list, phase: dict) -> None:
    page.on("pageerror", lambda error: diagnostics.append({"phase": phase["name"], "kind": "pageerror", "message": str(error)}))
    page.on("console", lambda message: diagnostics.append({"phase": phase["name"], "kind": "console", "message": message.text}) if message.type == "error" else None)
    page.on("response", lambda response: diagnostics.append({"phase": phase["name"], "kind": "http", "status": response.status, "url": response.url}) if response.status >= 400 else None)
    page.on("requestfailed", lambda request: diagnostics.append({"phase": phase["name"], "kind": "requestfailed", "url": request.url, "failure": request.failure}))


def search(page: Page, base: str, query: str) -> None:
    page.goto(base + "/", wait_until="domcontentloaded")
    box = page.get_by_role("combobox", name="全文搜尋")
    expect(box).to_have_count(1)
    box.fill(query)
    box.press("Enter")
    page.wait_for_url(lambda url: parse_qs(urlparse(str(url)).query).get("q") == [query], timeout=10000)
    page.wait_for_function("""() => {
      const status = document.querySelector('.search-status');
      return status && (status.textContent.includes('找到') || status.textContent.includes('找不到'));
    }""", timeout=10000)
    expect(box).to_have_value(query)
    no_duplicate_ids(page)
    overflow(page)


def load_previews(page: Page) -> None:
    for image in page.locator("img.source-preview-image, .workspace-source-preview img").all():
        image.scroll_into_view_if_needed()
        image.evaluate("image => image.loading = 'eager'")
        expect(image).to_be_visible()
        page.wait_for_function("image => image.complete && image.naturalWidth > 0", arg=image.element_handle(), timeout=15000)
        dimensions = image.evaluate("""image => ({width: image.width, height: image.height,
          naturalWidth: image.naturalWidth, naturalHeight: image.naturalHeight,
          cropped: getComputedStyle(image).objectFit === 'cover'})""")
        assert dimensions["width"] > 0 and dimensions["height"] > 0
        assert not dimensions["cropped"], "Original source preview must not be cropped"
        assert abs(dimensions["width"] / dimensions["height"] - dimensions["naturalWidth"] / dimensions["naturalHeight"]) < 0.01


def open_tool(page: Page, kind: str) -> None:
    button = page.locator(f"[data-reading-open='{kind}']")
    button.focus()
    button.press("Enter")
    expect(page.locator("dialog.reading-drawer")).to_be_visible()
    expect(button).to_have_attribute("aria-expanded", "true")
    expect(page.get_by_role("button", name="關閉閱讀工具")).to_be_focused()


def close_tool(page: Page, kind: str) -> None:
    page.keyboard.press("Escape")
    expect(page.locator("dialog.reading-drawer")).not_to_be_visible()
    expect(page.locator(f"[data-reading-open='{kind}']")).to_be_focused()
    expect(page.locator(f"[data-reading-open='{kind}']")).to_have_attribute("aria-expanded", "false")


def axe(page: Page, report: dict, name: str) -> None:
    assert AXE_PATH.is_file(), f"axe-core unavailable: {AXE_PATH}"
    page.add_script_tag(path=str(AXE_PATH))
    result = page.evaluate("""async () => {
      const result = await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']}});
      return {url: location.href, violations: result.violations, passes: result.passes.length,
        incomplete: result.incomplete, version: axe.version};
    }""")
    report.setdefault("axe", []).append({"name": name, **result})
    assert not result["violations"], f"axe violations for {name}: {[item['id'] for item in result['violations']]}"


def run_matrix(browser, engine: str, base: str, viewport: dict, units: dict) -> dict:
    context = browser.new_context(viewport=viewport, reduced_motion="reduce")
    page = context.new_page()
    diagnostics: list[dict] = []
    phase = {"name": "normal"}
    monitor(page, diagnostics, phase)
    width = viewport["width"]
    tag = f"{engine}-{width}x{viewport['height']}"
    report = {"engine": engine, "viewport": viewport, "browserVersion": browser.version, "journeys": [], "diagnostics": diagnostics}

    try:
        page.goto(base + "/", wait_until="domcontentloaded")
        expect(page.get_by_role("combobox", name="全文搜尋")).to_be_visible()
        expect(page.locator("#manual-search")).to_have_count(1)
        expect(page.locator(".identity-notice")).to_be_visible()
        assert "非農業信用保證基金官方網站" in page.locator(".identity-notice").inner_text()
        overflow(page)
        no_duplicate_ids(page)
        menu = page.locator("details.global-menu")
        if width < 900:
            expect(menu).not_to_have_attribute("open", "")
            menu.locator("summary").focus()
            page.keyboard.press("Enter")
            expect(menu).to_have_attribute("open", "")
            page.get_by_role("navigation", name="主要導覽").get_by_role("link", name="書表", exact=True).click()
            expect(page).to_have_url(base + "/versions/115-04/forms/index.html")
        report["journeys"].append("mobile-global-menu-keyboard-navigation")

        if engine == "chromium" and width in (390, 1440):
            page.goto(base + "/", wait_until="domcontentloaded")
            axe(page, report, "homepage")
            page.screenshot(path=str(EVIDENCE / f"{tag}-homepage.png"), full_page=False)

        form_cases = [
            ("格式 ２５ Ａ", "form-25a.html"),
            ("25a", "form-25a.html"),
            ("格式3 - 1", "form-3-1.html"),
            ("格式 3 - 1 A", "form-3-1a.html"),
        ]
        normal_25a = None
        for query, target in form_cases:
            search(page, base, query)
            first = page.locator(".search-result").first
            first.scroll_into_view_if_needed()
            page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
            href = first.locator("h3 a").get_attribute("href")
            assert urlparse(href).path.endswith(target), (query, href)
            assert f"書表編號完全符合「{query}」" in first.locator(".result-match-reasons").inner_text()
            assert page.locator(".search-zero-recovery").count() == 0
            if query == "25a":
                normal_25a = {"href": href, "reasons": first.locator(".result-match-reasons").inner_text()}
        report["journeys"].append("exact-form-raw-query-and-distinct-targets")

        if engine == "chromium" and width == 390:
            fallback_context = browser.new_context(viewport=viewport, reduced_motion="reduce")
            fallback_context.add_init_script("window.Worker = undefined")
            fallback = fallback_context.new_page()
            monitor(fallback, diagnostics, phase)
            try:
                search(fallback, base, "25a")
                first_fallback = fallback.locator(".search-result").first
                assert first_fallback.locator("h3 a").get_attribute("href") == normal_25a["href"]
                assert first_fallback.locator(".result-match-reasons").inner_text() == normal_25a["reasons"]
                assert fallback.locator(".search-zero-recovery").count() == 0
            finally:
                fallback_context.close()
            report["journeys"].append("worker-unavailable-real-ui-fallback-identical-exact-form")

        search(page, base, "不予保證")
        first = page.locator(".search-result h3 a").first
        assert urlparse(first.get_attribute("href")).path.endswith("excluded-guarantee.html")
        first.click()
        expect(page.locator("article.continuous-reading")).to_have_count(1)
        page.locator(".reading-hit-current").wait_for(timeout=5000)
        expect(page.locator(".return-to-search")).to_be_visible()
        assert parse_qs(urlparse(page.url).query)["q"] == ["不予保證"]
        page.locator(".return-to-search").click()
        page.locator(".search-result").first.wait_for()
        expect(page.get_by_role("combobox", name="全文搜尋")).to_have_value("不予保證")
        assert "fromSearch" not in parse_qs(urlparse(page.url).query)
        report["journeys"].append("search-reading-return-state")

        search(page, base, "代位清嘗")
        expect(page.locator(".search-result")).to_have_count(0)
        expect(page.locator(".recovery-chip")).to_have_text("代位清償")
        page.locator(".recovery-chip").focus()
        page.keyboard.press("Enter")
        page.locator(".search-result").first.wait_for()
        expect(page.get_by_role("combobox", name="全文搜尋")).to_have_value("代位清償")
        assert parse_qs(urlparse(page.url).query)["q"] == ["代位清償"]
        report["journeys"].append("typo-recovery-keyboard-and-raw-state")

        search(page, base, "保證")
        page.locator(".advanced-filters summary").click()
        for selected, label in [("chapter", "正文"), ("appendix", "附錄"), ("form", "書表"), ("lookup-table", "查索表"), ("all", None)]:
            button = page.locator(f"[data-search-type='{selected}']")
            expect(button).to_be_enabled()
            button.click()
            expect(button).to_have_attribute("aria-pressed", "true")
            expect(page.get_by_role("combobox", name="全文搜尋")).to_have_value("保證")
            if label:
                labels = page.locator(".search-result .result-type").all_text_contents()
                assert labels and set(labels) == {label}, (selected, labels)
            overflow(page)
        if engine == "chromium" and width in (390, 1440):
            axe(page, report, "search-results")
            page.screenshot(path=str(EVIDENCE / f"{tag}-search.png"), full_page=False)
        report["journeys"].append("all-five-content-filters")

        box = page.get_by_role("combobox", name="全文搜尋")
        previous_query = parse_qs(urlparse(page.url).query).get("q")
        box.dispatch_event("compositionstart")
        box.fill("保證成數")
        box.press("Enter")
        page.wait_for_timeout(350)
        assert parse_qs(urlparse(page.url).query).get("q") == previous_query, "IME composition Enter submitted a query"
        box.dispatch_event("compositionend")
        box.press("Enter")
        page.wait_for_url(lambda url: parse_qs(urlparse(str(url)).query).get("q") == ["保證成數"])
        page.locator(".search-result").first.wait_for()
        box.fill("代位清償")
        box.press("Enter")
        box.fill("25a")
        box.press("Enter")
        page.wait_for_url(lambda url: parse_qs(urlparse(str(url)).query).get("q") == ["25a"])
        page.wait_for_function("document.querySelector('.search-result h3 a')?.href.includes('form-25a.html')")
        expect(box).to_have_value("25a")
        assert "書表編號完全符合「25a」" in page.locator(".search-result").first.locator(".result-match-reasons").inner_text()
        report["journeys"].append("simulated-ime-composition-and-rapid-query-final-state")

        box.fill("")
        box.press("Enter")
        page.wait_for_function("!new URL(location.href).searchParams.has('q')")
        expect(page.locator(".search-result")).to_have_count(0)
        page.locator("[data-search-type='form']").click()
        expect(box).to_have_value("")
        expect(page.locator(".search-result")).to_have_count(0)
        assert "q" not in parse_qs(urlparse(page.url).query)
        assert "請輸入搜尋文字" in page.locator(".search-status").inner_text()
        report["journeys"].append("empty-clear-enter-filter-no-stale-results")

        overdue = units["overdue-guarantee"]
        page.goto(base + "/" + overdue["readingUrl"], wait_until="domcontentloaded")
        expect(page.locator("h1")).to_have_text(overdue["title"])
        expect(page.locator("[data-reading-tools]")).to_have_count(1)
        assert page.locator("[data-reading-tools]").evaluate("node => Boolean(node.closest('.section-nav'))") == (width >= 1280)
        assert "陸、解除保證責任" not in page.locator(".continuous-source-text").inner_text()
        section_menu = page.locator(".section-nav > details")
        if width < 900:
            expect(section_menu).not_to_have_attribute("open", "")
            section_menu.locator("summary").focus()
            page.keyboard.press("Enter")
            expect(section_menu).to_have_attribute("open", "")
        for disclosure in [".source-provenance-details", ".topic-toc-disclosure"]:
            node = page.locator(disclosure)
            expect(node).not_to_have_attribute("open", "")
            node.locator("summary").focus()
            page.keyboard.press("Enter")
            expect(node).to_have_attribute("open", "")

        assert_keyboard_toolbar_clear(page)
        report["journeys"].append("80-tab-focus-visibility-including-native-summaries")

        if engine == "chromium" and width == 390:
            normal_context = browser.new_context(viewport=viewport, reduced_motion="no-preference")
            normal_page = normal_context.new_page()
            monitor(normal_page, diagnostics, phase)
            try:
                normal_page.goto(base + "/" + overdue["readingUrl"], wait_until="domcontentloaded")
                assert not normal_page.evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches")
                for disclosure in [".section-nav > details", ".source-provenance-details", ".topic-toc-disclosure"]:
                    normal_page.locator(disclosure).locator("summary").focus()
                    normal_page.keyboard.press("Enter")
                assert_keyboard_toolbar_clear(normal_page)
                report["journeys"].append("normal-motion-80-tab-focus-visibility")
            except Exception:
                normal_page.screenshot(path=str(EVIDENCE / f"{tag}-normal-motion-focus-failure.png"), full_page=False)
                (EVIDENCE / f"{tag}-normal-motion-focus-failure.html").write_text(normal_page.content(), encoding="utf-8")
                raise
            finally:
                normal_context.close()

        page.locator(".continuous-source-text p").nth(2).scroll_into_view_if_needed()
        reading_position = page.evaluate_handle("""() => [...document.querySelectorAll('.manual-content .display-text p')]
          .find(node => {const rect = node.getBoundingClientRect(); return rect.bottom > 0 && rect.top < innerHeight;})""")
        original_top = reading_position.evaluate("node => node.getBoundingClientRect().top")
        open_tool(page, "source")
        page.locator(".workspace-source-body[aria-busy='false']").wait_for(timeout=15000)
        page.wait_for_timeout(100)
        shifted_top = reading_position.evaluate("node => node.getBoundingClientRect().top")
        if width >= 1280:
            assert abs(shifted_top - original_top) <= 4, f"Reading paragraph moved on workspace open: {original_top} -> {shifted_top}"
        assert page.locator("dialog.reading-drawer").evaluate("node => node.matches(':modal')") == (width < 1280)
        if width < 1280:
            for _ in range(20):
                page.keyboard.press("Tab")
                assert page.evaluate("document.querySelector('dialog.reading-drawer').contains(document.activeElement)"), "Modal focus escaped"
        if engine == "chromium" and width in (390, 1440):
            axe(page, report, "reading-source-workspace")
            page.screenshot(path=str(EVIDENCE / f"{tag}-workspace.png"), full_page=False)
        close_tool(page, "source")
        page.wait_for_timeout(100)
        if width >= 1280:
            final_top = reading_position.evaluate("node => node.getBoundingClientRect().top")
            assert abs(final_top - original_top) <= 4, f"Reading paragraph moved on workspace close: {original_top} -> {final_top}"
        open_tool(page, "contents")
        assert page.locator(".reading-drawer .workspace-link-list a").count() > 0
        contents_link = page.locator(".reading-drawer .workspace-link-list").first.locator("a").last
        contents_target = urlparse(contents_link.get_attribute("href")).fragment
        assert contents_target, "The verified chapter TOC must retain real anchor links"
        contents_link.click()
        page.wait_for_url(lambda url: urlparse(str(url)).fragment == contents_target)
        if width < 1280:
            expect(page.locator("dialog.reading-drawer")).not_to_be_visible()
        else:
            close_tool(page, "contents")
        page.wait_for_timeout(100)
        target_position = page.locator(f"[id='{contents_target}']").evaluate("node => ({top: node.getBoundingClientRect().top, bottom: node.getBoundingClientRect().bottom, height: innerHeight})")
        assert target_position["bottom"] > 0 and target_position["top"] < target_position["height"], f"Contents click did not reveal its actual target: {contents_target}; {target_position}"
        open_tool(page, "forms")
        forms_count = page.locator(".related-forms .related-form-card").count()
        assert page.locator(".reading-drawer .workspace-link-list a").count() == forms_count
        close_tool(page, "forms")
        report["journeys"].append("reading-workspace-keyboard-focus-position-and-disclosures")

        if width < 600:
            expect(page.locator("details.reading-size")).not_to_have_attribute("open", "")
            page.locator("details.reading-size summary").click()
        page.locator("button[data-reading-size='24']").click()
        assert page.evaluate("document.documentElement.dataset.readingSize") == "24"
        page.reload(wait_until="domcontentloaded")
        expect(page.locator("button[data-reading-size='24']")).to_have_attribute("aria-pressed", "true")
        assert page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--reading-font-size').trim()") == "24px"
        if width < 600:
            page.locator("details.reading-size summary").click()
        page.locator("button[data-reading-size='20']").click()
        report["journeys"].append("bounded-font-preference-reload")

        form_link = page.locator(".related-forms .related-form-card").first
        expected_form = urlparse(form_link.evaluate("node => node.href")).path
        form_link.click()
        assert urlparse(page.url).path == expected_form, f"Related form navigated to {page.url}, expected {expected_form}"
        expect(page.locator(".related-rules")).to_be_visible()
        load_previews(page)
        page.go_back(wait_until="domcontentloaded")
        assert urlparse(page.url).path.endswith(overdue["readingUrl"])
        report["journeys"].append("confirmed-related-form-and-browser-back")

        page.emulate_media(media="print")
        assert page.locator("[data-reading-tools]").evaluate("node => getComputedStyle(node).display") == "none"
        assert page.locator(".continuous-source-text").evaluate("node => getComputedStyle(node).display") != "none"
        assert "中華民國115年4月" in page.locator("body").inner_text()
        assert page.locator(".source-meta").evaluate("node => getComputedStyle(node).display") != "none"
        if engine == "chromium" and width == 1440:
            page.pdf(path=str(EVIDENCE / "long-reading-print.pdf"), format="A4", print_background=True)
        page.emulate_media(media="screen")
        report["journeys"].append("long-reading-print-content-version-source")

        search(page, base, "25a")
        first_link = page.locator(".search-result h3 a").first
        first_link.click()
        assert urlparse(page.url).path.endswith("form-25a.html")
        assert urlparse(page.url).fragment == "pdf-page-178"
        load_previews(page)
        expect(page.locator(".source-preview-image")).to_have_count(1)
        open_tool(page, "source")
        page.locator(".workspace-source-body[aria-busy='false']").wait_for(timeout=15000)
        load_previews(page)
        close_tool(page, "source")
        if engine == "chromium" and width in (390, 1440):
            axe(page, report, "form-original-preview")
            page.screenshot(path=str(EVIDENCE / f"{tag}-form.png"), full_page=False)
        page.go_back(wait_until="domcontentloaded")
        page.locator(".search-result").first.wait_for()
        expect(page.get_by_role("combobox", name="全文搜尋")).to_have_value("25a")
        report["journeys"].append("exact-form-source-and-browser-back")

        search(page, base, "格式 3 - 1 A")
        page.locator(".search-result h3 a").first.click()
        expect(page.locator(".source-preview-image")).to_have_count(3)
        load_previews(page)
        overflow(page)
        report["journeys"].append("multi-page-special-form-complete-proportions")

        if engine == "chromium" and width == 390:
            phase["name"] = "intentional-preview-failure"
            page.route("**/pdf-page-178.webp", lambda route: route.abort("failed"))
            page.goto(base + "/versions/115-04/forms/form-25a.html", wait_until="domcontentloaded")
            page.locator(".source-preview-image").evaluate("image => image.loading = 'eager'")
            expect(page.locator(".source-preview-error")).to_be_visible(timeout=15000)
            expect(page.locator(".preview-actions a").filter(has_text="開啟原始PDF此頁")).to_be_visible()
            page.unroute("**/pdf-page-178.webp")
            page.route("**/versions/115-04/pages/page-*.html", lambda route: route.abort("failed"))
            page.goto(base + "/" + overdue["readingUrl"], wait_until="domcontentloaded")
            open_tool(page, "source")
            expect(page.locator(".workspace-source-body .workspace-error")).to_be_visible(timeout=15000)
            expect(page.locator(".workspace-source-body a").filter(has_text="開啟完整PDF")).to_be_visible()
            close_tool(page, "source")
            page.wait_for_timeout(100)
            page.unroute("**/versions/115-04/pages/page-*.html")
            phase["name"] = "normal"
            report["journeys"].append("intentional-image-and-source-fetch-failures-with-original-pdf-fallback")

        if engine == "chromium" and width in (390, 1440):
            page.goto(base + "/versions/115-04/index.html", wait_until="domcontentloaded")
            axe(page, report, "complete-directory")
            expect(page.get_by_role("combobox", name="全文搜尋")).to_have_count(1)
            for url, name in [("versions/115-04/forms/index.html", "forms-index"), ("versions/115-04/appendices/index.html", "appendix-index"), ("versions/index.html", "versions")]:
                page.goto(base + "/" + url, wait_until="domcontentloaded")
                axe(page, report, name)
                overflow(page)

        if engine == "chromium" and width == 390:
            page.emulate_media(forced_colors="active")
            page.goto(base + "/" + overdue["readingUrl"], wait_until="domcontentloaded")
            assert page.evaluate("matchMedia('(forced-colors: active)').matches")
            expect(page.locator(".continuous-source-text")).to_be_visible()
            open_tool(page, "contents")
            expect(page.get_by_role("button", name="關閉閱讀工具")).to_be_focused()
            expect(page.locator(".reading-drawer .workspace-link-list a").first).to_be_visible()
            overflow(page)
            page.screenshot(path=str(EVIDENCE / f"{tag}-forced-colors.png"), full_page=False)
            close_tool(page, "contents")
            expect(page.locator("[data-reading-open='contents']")).to_be_visible()
            overflow(page)
            page.emulate_media(forced_colors="none")
            assert not page.evaluate("matchMedia('(forced-colors: active)').matches")
            report["journeys"].append("emulated-forced-colors-reading-tools-keyboard-and-return")

        if engine == "chromium" and width in (390, 1440):
            page.goto(base + "/" + overdue["readingUrl"], wait_until="domcontentloaded")
            page.wait_for_function("document.documentElement.dataset.readingSize === '20'")
            page.wait_for_function("parseFloat(getComputedStyle(document.querySelector('.continuous-source-text')).fontSize) === 20")
            page.evaluate("""() => {
              const sizes = [...document.querySelectorAll('body, body *')].map(node => [node, parseFloat(getComputedStyle(node).fontSize)]);
              for (const [node, size] of sizes) if (Number.isFinite(size)) node.style.fontSize = `${size * 2}px`;
            }""")
            page.wait_for_function("parseFloat(getComputedStyle(document.querySelector('.continuous-source-text')).fontSize) >= 40")
            assert float(page.locator(".continuous-source-text").evaluate("node => parseFloat(getComputedStyle(node).fontSize)")) >= 40
            overflow(page)
            assert_keyboard_toolbar_clear(page)
            page.locator(".continuous-source-text p").last.evaluate("node => node.scrollIntoView({block: 'start', behavior: 'instant'})")
            final_reading = page.locator(".continuous-source-text p").last.evaluate("""node => {
              const paragraph = node.getBoundingClientRect();
              const tools = document.querySelector('[data-reading-tools]').getBoundingClientRect();
              return {paragraphTop: paragraph.top, paragraphBottom: paragraph.bottom,
                toolbarTop: tools.top, toolbarBottom: tools.bottom, toolbarHeight: tools.height,
                footerPadding: getComputedStyle(document.querySelector('.site-footer')).paddingBottom,
                toolbarClearance: getComputedStyle(document.documentElement).getPropertyValue('--reading-toolbar-clearance').trim()};
            }""")
            assert final_reading["paragraphTop"] >= -1, final_reading
            assert final_reading["paragraphBottom"] <= final_reading["toolbarTop"] or width >= 1280, f"Final reading paragraph obscured at200%: {final_reading}"
            report["textResize200"] = final_reading
            open_tool(page, "contents")
            assert page.locator(".reading-drawer .workspace-link-list a").count() > 0
            overflow(page)
            close_tool(page, "contents")
            page.screenshot(path=str(EVIDENCE / f"{tag}-text-resize-200.png"), full_page=False)
            report["journeys"].append("simulated-200-percent-text-resize-reflow-and-tools")
            physical_url = page.locator(".source-page-link").first.evaluate("node => node.href")
            page.goto(physical_url, wait_until="domcontentloaded")
            page.wait_for_function("document.documentElement.dataset.readingSize === '20'")
            page.wait_for_function("parseFloat(getComputedStyle(document.querySelector('.page-card .display-text')).fontSize) === 20")
            page.evaluate("""() => {
              const sizes = [...document.querySelectorAll('body, body *')].map(node => [node, parseFloat(getComputedStyle(node).fontSize)]);
              for (const [node, size] of sizes) if (Number.isFinite(size)) node.style.fontSize = `${size * 2}px`;
            }""")
            page.wait_for_function("parseFloat(getComputedStyle(document.querySelector('.page-card .display-text')).fontSize) >= 40")
            assert float(page.locator(".page-card .display-text").evaluate("node => parseFloat(getComputedStyle(node).fontSize)")) >= 40
            overflow(page)
            assert_keyboard_toolbar_clear(page)
            report["journeys"].append("physical-source-page-simulated-200-percent-text-resize")

        no_duplicate_ids(page)
        overflow(page)
        unexpected = [item for item in diagnostics if item["phase"] == "normal"]
        assert not unexpected, f"Normal-journey diagnostics: {unexpected}"
        report["status"] = "PASS"
        print(f"{tag} PASS: {len(report['journeys'])} journeys; normal console/pageerror/http/requestfailed=0", flush=True)
        return report
    except Exception as error:
        report["status"] = "FAIL"
        report["error"] = traceback.format_exc()
        page.screenshot(path=str(EVIDENCE / f"{tag}-failure.png"), full_page=False)
        (EVIDENCE / f"{tag}-failure.html").write_text(page.content(), encoding="utf-8")
        print(f"{tag} FAIL: {report['error']}", flush=True)
        return report
    finally:
        context.close()


def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    assert SITE.is_dir(), "Build the candidate site before running these tests"
    units = {unit["id"]: unit for unit in load_resolved_units()}
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), lambda *args: QuietHandler(*args, directory=str(SITE)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    engines = os.environ.get("EXPERIENCE_BROWSERS", "chromium,webkit,firefox").split(",")
    selected_widths = os.environ.get("EXPERIENCE_WIDTHS", "")
    widths = {int(value) for value in selected_widths.split(",") if value} if selected_widths else None
    viewports = [viewport for viewport in VIEWPORTS if widths is None or viewport["width"] in widths]
    report = {"scope": "local candidate; simulated desktop browsers, not physical devices or real users", "requestedEngines": engines, "requestedViewports": viewports, "matrix": [], "unavailableBrowsers": []}
    try:
        with sync_playwright() as playwright:
            for engine in engines:
                browser_type = getattr(playwright, engine)
                options = {"headless": True, "timeout": 30000}
                if not Path(browser_type.executable_path).is_file():
                    pattern = "webkit-*/pw_run.sh" if engine == "webkit" else "firefox-*/firefox/Nightly.app/Contents/MacOS/firefox"
                    candidates = sorted(CACHE.glob(pattern))
                    if candidates:
                        options["executable_path"] = str(candidates[-1])
                try:
                    browser = browser_type.launch(**options)
                except Exception as error:
                    report["unavailableBrowsers"].append({"engine": engine, "error": str(error)})
                    print(f"{engine} UNAVAILABLE: {error}", flush=True)
                    continue
                try:
                    for viewport in viewports:
                        result = run_matrix(browser, engine, base, viewport, units)
                        report["matrix"].append(result)
                        (EVIDENCE / "experience-e2e.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                finally:
                    browser.close()
    finally:
        server.shutdown()
        server.server_close()
    report["passed"] = bool(report["matrix"]) and all(
        item["status"] == "PASS" and not any(event["phase"] == "normal" for event in item["diagnostics"])
        for item in report["matrix"]
    )
    report["requiredBrowsersAvailable"] = not any(item["engine"] in {"chromium", "webkit"} for item in report["unavailableBrowsers"])
    (EVIDENCE / "experience-e2e.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("EXPERIENCE E2E PASSED" if report["passed"] and report["requiredBrowsersAvailable"] else "EXPERIENCE E2E FAILED", flush=True)
    return 0 if report["passed"] and report["requiredBrowsersAvailable"] else 1


if __name__ == "__main__":
    sys.exit(main())
