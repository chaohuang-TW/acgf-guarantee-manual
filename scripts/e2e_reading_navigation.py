#!/usr/bin/env python3
"""Browser E2E Matrix for Reading Navigation 2.0 and Search Landing Cue."""

from __future__ import annotations

import http.server
import json
import re
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


def slug_code(code: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", code.lower().replace("格式", "form")).strip("-")


def get_authoritative_sequence():
    toc_file = ROOT / "data/toc.json"
    with open(toc_file, "r", encoding="utf-8") as f:
        toc = json.load(f)

    parts = toc.get("parts", [])
    appendices = toc.get("appendices", [])
    forms = toc.get("forms", [])
    special_forms = toc.get("specialForms", [])

    combined = []
    for item in forms:
        combined.append(("forms", item))
    for item in special_forms:
        combined.append(("specialForms", item))

    def form_sort_key(entry):
        idx, (category, item) = entry
        page = item.get("printedPage")
        if page is None:
            return (float('inf'), idx)
        try:
            if isinstance(page, int):
                return (float(page), idx)
            return (float(str(page).replace("頁", "").strip()), idx)
        except ValueError:
            return (float('inf'), idx)

    combined_sorted = [x[1] for x in sorted(enumerate(combined), key=form_sort_key)]

    authoritative_forms = []
    for cat, item in combined_sorted:
        slug = slug_code(item["code"])
        path = f"forms/{slug}.html" if cat == "forms" else f"forms/special/{slug}.html"
        authoritative_forms.append({
            "cat": cat,
            "code": item["code"],
            "title": item["title"],
            "printedPage": item.get("printedPage"),
            "path": path,
            "full_title": f"{item['code']}：{item['title']}"
        })

    return {
        "toc": toc,
        "parts": parts,
        "appendices": appendices,
        "forms": authoritative_forms
    }


def assert_clean_nav_href(href: str) -> None:
    assert href, "Href must exist and not be empty"
    parsed = urllib.parse.urlparse(href)
    assert not parsed.query, f"Query must be empty in nav link: {href}"
    assert not parsed.fragment, f"Fragment must be empty in nav link: {href}"
    assert "fromSearch" not in href, f"fromSearch found in nav link: {href}"
    assert "q=" not in href, f"q= found in nav link: {href}"
    assert "type=" not in href, f"type= found in nav link: {href}"


def assert_no_overflow(page: Page) -> None:
    overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
    assert not overflow, "Horizontal overflow detected"


def open_and_wait(page: Page, url: str) -> None:
    page.goto(url)
    page.wait_for_load_state("domcontentloaded")


def setup_monitoring(page: Page, console_errors: list, page_errors: list, network_404s: list) -> None:
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda err: page_errors.append(str(err)))
    page.on("response", lambda resp: network_404s.append(resp.url) if resp.status == 404 else None)


def run_full_journey(context, base: str, vp: dict, auth_data: dict) -> None:
    console_errors = []
    page_errors = []
    network_404s = []

    page = context.new_page()
    setup_monitoring(page, console_errors, page_errors, network_404s)

    # ────────────────────────
    # 六、正文第一節
    # ────────────────────────
    open_and_wait(page, f"{base}/versions/115-04/chapters/part-1/guarantee-subject.html")
    assert page.locator(".reading-pagination").count() == 1
    assert page.locator(".reading-pagination .nav-prev").count() == 0
    assert page.locator(".reading-pagination .nav-next").count() == 1

    next_btn = page.locator(".reading-pagination .nav-next")
    assert "下一節：貳、保證成數" in next_btn.inner_text()
    next_href = next_btn.get_attribute("href")
    assert_clean_nav_href(next_href)
    assert next_href != "guarantee-subject.html"

    next_btn.click()
    page.wait_for_load_state("domcontentloaded")
    assert "guarantee-ratio.html" in page.url
    parsed = urllib.parse.urlparse(page.url)
    assert not parsed.query
    assert not parsed.fragment
    assert_no_overflow(page)

    # ────────────────────────
    # 七、正文中間節
    # ────────────────────────
    open_and_wait(page, f"{base}/versions/115-04/chapters/part-1/guarantee-ratio.html")
    assert page.locator(".reading-pagination").count() == 1
    assert page.locator(".reading-pagination .nav-prev").count() == 1
    assert page.locator(".reading-pagination .nav-next").count() == 1

    prev_btn = page.locator(".reading-pagination .nav-prev")
    next_btn = page.locator(".reading-pagination .nav-next")
    assert "壹、保證對象" in prev_btn.inner_text()
    assert "參、不予保證規定" in next_btn.inner_text()
    assert_clean_nav_href(prev_btn.get_attribute("href"))
    assert_clean_nav_href(next_btn.get_attribute("href"))
    assert prev_btn.get_attribute("href") != "guarantee-ratio.html"
    assert next_btn.get_attribute("href") != "guarantee-ratio.html"
    assert_no_overflow(page)

    # ────────────────────────
    # 八、正文最後節
    # ────────────────────────
    last_part = auth_data["parts"][-1]
    last_sec = last_part["sections"][-1]
    open_and_wait(page, f"{base}/versions/115-04/chapters/{last_part['id']}/{last_sec['id']}.html")
    assert page.locator(".reading-pagination .nav-prev").count() == 1
    assert page.locator(".reading-pagination .nav-next").count() == 0

    prev_href = page.locator(".reading-pagination .nav-prev").get_attribute("href")
    assert_clean_nav_href(prev_href)
    assert "appendices" not in prev_href
    assert_no_overflow(page)

    # ────────────────────────
    # 九、正文跨篇邊界
    # ────────────────────────
    p1_last_sec = auth_data["parts"][0]["sections"][-1]
    p2_first_sec = auth_data["parts"][1]["sections"][0]
    p1_last_url = f"{base}/versions/115-04/chapters/{auth_data['parts'][0]['id']}/{p1_last_sec['id']}.html"
    open_and_wait(page, p1_last_url)

    next_btn = page.locator(".reading-pagination .nav-next")
    assert p2_first_sec["title"] in next_btn.inner_text()
    next_href = next_btn.get_attribute("href")
    assert f"{p2_first_sec['id']}.html" in next_href
    assert_clean_nav_href(next_href)

    next_btn.click()
    page.wait_for_load_state("domcontentloaded")
    assert f"{p2_first_sec['id']}.html" in page.url
    parsed = urllib.parse.urlparse(page.url)
    assert not parsed.query
    assert not parsed.fragment
    assert_no_overflow(page)

    # ────────────────────────
    # 十、附錄2
    # ────────────────────────
    open_and_wait(page, f"{base}/versions/115-04/appendices/appendix-02.html")
    prev_btn = page.locator(".reading-pagination .nav-prev")
    next_btn = page.locator(".reading-pagination .nav-next")
    assert "appendix-01" in prev_btn.get_attribute("href")
    assert "appendix-03" in next_btn.get_attribute("href")
    assert_clean_nav_href(prev_btn.get_attribute("href"))
    assert_clean_nav_href(next_btn.get_attribute("href"))

    next_btn.click()
    page.wait_for_load_state("domcontentloaded")
    assert "appendix-03.html" in page.url
    parsed = urllib.parse.urlparse(page.url)
    assert not parsed.query
    assert not parsed.fragment
    assert_no_overflow(page)

    # ────────────────────────
    # 十一、附錄10
    # ────────────────────────
    open_and_wait(page, f"{base}/versions/115-04/appendices/appendix-10.html")
    prev_btn = page.locator(".reading-pagination .nav-prev")
    next_btn = page.locator(".reading-pagination .nav-next")
    assert "appendix-09" in prev_btn.get_attribute("href")
    assert "appendix-11" in next_btn.get_attribute("href")
    assert_clean_nav_href(prev_btn.get_attribute("href"))
    assert_clean_nav_href(next_btn.get_attribute("href"))
    assert_no_overflow(page)

    # ────────────────────────
    # 十二、附錄18
    # ────────────────────────
    open_and_wait(page, f"{base}/versions/115-04/appendices/appendix-18.html")
    assert page.locator(".reading-pagination .nav-prev").count() == 1
    assert page.locator(".reading-pagination .nav-next").count() == 0
    prev_href = page.locator(".reading-pagination .nav-prev").get_attribute("href")
    assert_clean_nav_href(prev_href)
    assert "forms" not in prev_href
    assert_no_overflow(page)

    # ────────────────────────
    # 十四、格式1系列 (1A, 1B, 1C)
    # ────────────────────────
    forms_dict = {f["code"]: f for f in auth_data["forms"]}
    f1a = forms_dict["格式 1A"]
    f1b = forms_dict["格式 1B"]
    f1c = forms_dict["格式 1C"]

    open_and_wait(page, f"{base}/versions/115-04/{f1a['path']}")
    next_btn = page.locator(".reading-pagination .nav-next")
    assert f1b["path"].split('/')[-1] in next_btn.get_attribute("href")
    assert_clean_nav_href(next_btn.get_attribute("href"))
    assert_no_overflow(page)

    open_and_wait(page, f"{base}/versions/115-04/{f1b['path']}")
    prev_btn = page.locator(".reading-pagination .nav-prev")
    next_btn = page.locator(".reading-pagination .nav-next")
    assert f1a["path"].split('/')[-1] in prev_btn.get_attribute("href")
    assert f1c["path"].split('/')[-1] in next_btn.get_attribute("href")
    assert_clean_nav_href(prev_btn.get_attribute("href"))
    assert_clean_nav_href(next_btn.get_attribute("href"))
    assert_no_overflow(page)

    open_and_wait(page, f"{base}/versions/115-04/{f1c['path']}")
    prev_btn = page.locator(".reading-pagination .nav-prev")
    assert f1b["path"].split('/')[-1] in prev_btn.get_attribute("href")
    assert_clean_nav_href(prev_btn.get_attribute("href"))
    assert_no_overflow(page)

    # ────────────────────────
    # 十五、格式11系列 (11, 11A)
    # ────────────────────────
    forms_list = auth_data["forms"]
    idx11 = next(i for i, f in enumerate(forms_list) if f["code"] == "格式 11")
    idx11a = next(i for i, f in enumerate(forms_list) if f["code"] == "格式 11A")

    f11_auth_prev = forms_list[idx11 - 1]
    f11_auth_next = forms_list[idx11 + 1]

    f11a_auth_prev = forms_list[idx11a - 1]
    f11a_auth_next = forms_list[idx11a + 1]

    open_and_wait(page, f"{base}/versions/115-04/{forms_list[idx11]['path']}")
    prev_btn = page.locator(".reading-pagination .nav-prev")
    next_btn = page.locator(".reading-pagination .nav-next")
    assert f11_auth_prev["path"].split('/')[-1] in prev_btn.get_attribute("href")
    assert f11_auth_next["path"].split('/')[-1] in next_btn.get_attribute("href")
    assert_clean_nav_href(prev_btn.get_attribute("href"))
    assert_clean_nav_href(next_btn.get_attribute("href"))
    assert_no_overflow(page)

    open_and_wait(page, f"{base}/versions/115-04/{forms_list[idx11a]['path']}")
    prev_btn = page.locator(".reading-pagination .nav-prev")
    next_btn = page.locator(".reading-pagination .nav-next")
    assert f11a_auth_prev["path"].split('/')[-1] in prev_btn.get_attribute("href")
    assert f11a_auth_next["path"].split('/')[-1] in next_btn.get_attribute("href")
    assert_clean_nav_href(prev_btn.get_attribute("href"))
    assert_clean_nav_href(next_btn.get_attribute("href"))
    assert_no_overflow(page)

    # ────────────────────────
    # 十六、格式25系列 (25, 25A, 25B, 25C)
    # ────────────────────────
    idx25 = next(i for i, f in enumerate(forms_list) if f["code"] == "格式 25")
    idx25a = next(i for i, f in enumerate(forms_list) if f["code"] == "格式 25A")
    idx25b = next(i for i, f in enumerate(forms_list) if f["code"] == "格式 25B")
    idx25c = next(i for i, f in enumerate(forms_list) if f["code"] == "格式 25C")

    assert idx25a == idx25 + 1
    assert idx25b == idx25a + 1
    assert idx25c == idx25b + 1

    open_and_wait(page, f"{base}/versions/115-04/{forms_list[idx25]['path']}")
    next_btn = page.locator(".reading-pagination .nav-next")
    assert "form-25a" in next_btn.get_attribute("href")
    next_btn.click()
    page.wait_for_load_state("domcontentloaded")
    assert "form-25a" in page.url
    parsed = urllib.parse.urlparse(page.url)
    assert not parsed.query and not parsed.fragment
    assert_no_overflow(page)

    next_btn = page.locator(".reading-pagination .nav-next")
    assert "form-25b" in next_btn.get_attribute("href")
    next_btn.click()
    page.wait_for_load_state("domcontentloaded")
    assert "form-25b" in page.url
    parsed = urllib.parse.urlparse(page.url)
    assert not parsed.query and not parsed.fragment
    assert_no_overflow(page)

    next_btn = page.locator(".reading-pagination .nav-next")
    assert "form-25c" in next_btn.get_attribute("href")
    next_btn.click()
    page.wait_for_load_state("domcontentloaded")
    assert "form-25c" in page.url
    parsed = urllib.parse.urlparse(page.url)
    assert not parsed.query and not parsed.fragment
    assert_no_overflow(page)

    prev_btn = page.locator(".reading-pagination .nav-prev")
    assert "form-25b" in prev_btn.get_attribute("href")

    # ────────────────────────
    # 十七、格式31
    # ────────────────────────
    idx31 = next(i for i, f in enumerate(forms_list) if f["code"] == "格式 31")
    f31_auth_next = forms_list[idx31 + 1]

    open_and_wait(page, f"{base}/versions/115-04/{forms_list[idx31]['path']}")
    next_btn = page.locator(".reading-pagination .nav-next")
    assert f31_auth_next["code"] in next_btn.inner_text()
    assert f31_auth_next["title"] in next_btn.inner_text()
    assert f31_auth_next["path"].split('/')[-1] in next_btn.get_attribute("href")
    assert_clean_nav_href(next_btn.get_attribute("href"))
    assert_no_overflow(page)

    # ────────────────────────
    # 十八、格式33系列 (33, 33-1, 34, 34-1)
    # ────────────────────────
    idx33 = next(i for i, f in enumerate(forms_list) if f["code"] == "格式 33")
    idx33_1 = next(i for i, f in enumerate(forms_list) if f["code"] == "格式 33-1")
    idx34 = next(i for i, f in enumerate(forms_list) if f["code"] == "格式 34")
    idx34_1 = next(i for i, f in enumerate(forms_list) if f["code"] == "格式 34-1")

    f33_auth_next = forms_list[idx33 + 1]
    f33_1_auth_prev = forms_list[idx33_1 - 1]
    f33_1_auth_next = forms_list[idx33_1 + 1]
    f34_auth_prev = forms_list[idx34 - 1]
    f34_auth_next = forms_list[idx34 + 1]
    f34_1_auth_prev = forms_list[idx34_1 - 1]
    f34_1_auth_next = forms_list[idx34_1 + 1]

    open_and_wait(page, f"{base}/versions/115-04/{forms_list[idx33]['path']}")
    next_btn = page.locator(".reading-pagination .nav-next")
    assert f33_auth_next["path"].split('/')[-1] in next_btn.get_attribute("href")
    assert_clean_nav_href(next_btn.get_attribute("href"))
    assert_no_overflow(page)

    open_and_wait(page, f"{base}/versions/115-04/{forms_list[idx33_1]['path']}")
    prev_btn = page.locator(".reading-pagination .nav-prev")
    next_btn = page.locator(".reading-pagination .nav-next")
    assert f33_1_auth_prev["path"].split('/')[-1] in prev_btn.get_attribute("href")
    assert f33_1_auth_next["path"].split('/')[-1] in next_btn.get_attribute("href")
    assert_clean_nav_href(prev_btn.get_attribute("href"))
    assert_clean_nav_href(next_btn.get_attribute("href"))
    assert_no_overflow(page)

    open_and_wait(page, f"{base}/versions/115-04/{forms_list[idx34]['path']}")
    prev_btn = page.locator(".reading-pagination .nav-prev")
    next_btn = page.locator(".reading-pagination .nav-next")
    assert f34_auth_prev["path"].split('/')[-1] in prev_btn.get_attribute("href")
    assert f34_auth_next["path"].split('/')[-1] in next_btn.get_attribute("href")
    assert_clean_nav_href(prev_btn.get_attribute("href"))
    assert_clean_nav_href(next_btn.get_attribute("href"))
    assert_no_overflow(page)

    open_and_wait(page, f"{base}/versions/115-04/{forms_list[idx34_1]['path']}")
    prev_btn = page.locator(".reading-pagination .nav-prev")
    next_btn = page.locator(".reading-pagination .nav-next")
    assert f34_1_auth_prev["path"].split('/')[-1] in prev_btn.get_attribute("href")
    assert f34_1_auth_next["path"].split('/')[-1] in next_btn.get_attribute("href")
    assert_clean_nav_href(prev_btn.get_attribute("href"))
    assert_clean_nav_href(next_btn.get_attribute("href"))
    assert_no_overflow(page)

    # ────────────────────────
    # 十九、真實搜尋 Landing Journey
    # ────────────────────────
    open_and_wait(page, f"{base}/")
    search_input = page.locator("form[role='search'] input[name='q'], input[type='search']")
    search_input.fill("代償利息")
    search_input.press("Enter")

    status_el = page.locator(".search-status")
    expect(status_el).to_contain_text("找到", timeout=5000)

    first_result = page.locator(".search-results article h3 a").first
    href = first_result.get_attribute("href")
    assert "fromSearch=1" in href
    assert "q=%E4%BB%A3%E5%84%9F%E5%88%A9%E6%81%AF" in href or "q=代償利息" in href
    assert "#pdf-page-" in href

    first_result.click()
    page.wait_for_load_state("domcontentloaded")

    assert "fromSearch=1" in page.url
    assert "q=" in page.url
    parsed_landing = urllib.parse.urlparse(page.url)
    assert parsed_landing.fragment.startswith("pdf-page-")

    target_id = parsed_landing.fragment
    target_el = page.locator(f"#{target_id}")
    assert target_el.count() == 1
    assert "search-landing-target" in target_el.get_attribute("class")

    note_el = target_el.locator(".search-landing-note")
    assert note_el.count() == 1
    assert note_el.inner_text().strip() == "搜尋結果定位至此"

    rts_el = page.locator(".return-to-search")
    assert rts_el.count() == 1
    assert_no_overflow(page)

    # ────────────────────────
    # 二十、Search Context 不污染 Navigation
    # ────────────────────────
    nav_link = page.locator(".reading-pagination a").first
    nav_href = nav_link.get_attribute("href")
    assert_clean_nav_href(nav_href)

    nav_link.click()
    page.wait_for_load_state("domcontentloaded")
    parsed_new = urllib.parse.urlparse(page.url)
    assert not parsed_new.query
    assert not parsed_new.fragment
    assert "fromSearch" not in page.url
    assert "q=" not in page.url
    assert "type=" not in page.url

    # ────────────────────────
    # 二十一、Copy Page 完整 Journey
    # ────────────────────────
    # Land back on search page
    open_and_wait(page, f"{base}/")
    search_input = page.locator("form[role='search'] input[name='q'], input[type='search']")
    search_input.fill("代償利息")
    search_input.press("Enter")
    expect(page.locator(".search-status")).to_contain_text("找到", timeout=5000)
    page.locator(".search-results article h3 a").first.click()
    page.wait_for_load_state("domcontentloaded")

    target_id = urllib.parse.urlparse(page.url).fragment
    target_el = page.locator(f"#{target_id}")
    copy_btn = target_el.locator("button.copy-page-link")
    copy_btn.click()

    expect(copy_btn).to_have_text("已複製連結！", timeout=3000)
    clipboard_text = page.evaluate("navigator.clipboard.readText()")
    parsed_clip = urllib.parse.urlparse(clipboard_text)

    current_path = urllib.parse.urlparse(page.url).path
    assert parsed_clip.path == current_path
    assert parsed_clip.fragment == target_id
    assert not parsed_clip.query
    assert "fromSearch" not in clipboard_text
    assert "q=" not in clipboard_text
    assert "type=" not in clipboard_text

    copied_page = context.new_page()
    setup_monitoring(copied_page, console_errors, page_errors, network_404s)
    copied_page.goto(clipboard_text)
    copied_page.wait_for_load_state("domcontentloaded")

    assert urllib.parse.urlparse(copied_page.url).path == current_path
    assert urllib.parse.urlparse(copied_page.url).fragment == target_id
    assert copied_page.locator(f"#{target_id}").count() == 1
    assert copied_page.locator(".search-landing-target").count() == 0
    assert copied_page.locator(".search-landing-note").count() == 0
    assert copied_page.locator(".return-to-search").count() == 0
    assert_no_overflow(copied_page)
    copied_page.close()

    # ────────────────────────
    # 二十二、Clean Anchor
    # ────────────────────────
    open_and_wait(page, f"{base}/versions/115-04/chapters/part-3/subrogation-scope.html#pdf-page-46")
    assert page.locator(".search-landing-target").count() == 0
    assert page.locator(".search-landing-note").count() == 0
    assert page.locator(".return-to-search").count() == 0
    assert_no_overflow(page)

    # ────────────────────────
    # 二十三、FromSearch 無 Hash
    # ────────────────────────
    open_and_wait(page, f"{base}/versions/115-04/chapters/part-3/subrogation-scope.html?fromSearch=1&q=代償利息")
    assert page.locator(".return-to-search").count() == 1
    assert page.locator(".search-landing-target").count() == 0
    assert page.locator(".search-landing-note").count() == 0
    assert_no_overflow(page)

    # ────────────────────────
    # 二十四、有效格式但 target 不存在
    # ────────────────────────
    open_and_wait(page, f"{base}/versions/115-04/chapters/part-3/subrogation-scope.html?fromSearch=1&q=代償利息#pdf-page-999")
    assert page.locator(".return-to-search").count() == 1
    assert page.locator(".search-landing-target").count() == 0
    assert page.locator(".search-landing-note").count() == 0
    assert_no_overflow(page)

    # ────────────────────────
    # 二十五、非 PDF Hash
    # ────────────────────────
    open_and_wait(page, f"{base}/versions/115-04/chapters/part-3/subrogation-scope.html?fromSearch=1&q=test#manual-search")
    assert page.locator(".search-landing-target").count() == 0
    assert page.locator(".search-landing-note").count() == 0
    assert_no_overflow(page)

    # ────────────────────────
    # 二十六、Duplicate Cue 防護
    # ────────────────────────
    open_and_wait(page, f"{base}/versions/115-04/chapters/part-3/subrogation-scope.html?fromSearch=1&q=代償利息#pdf-page-46")
    orig_title = page.evaluate("document.title")
    orig_active = page.evaluate("document.activeElement.tagName")
    orig_tabindex = page.locator("#pdf-page-46").get_attribute("tabindex")

    page.evaluate("window.SiteUtils && window.SiteUtils.initSearchLandingCue && window.SiteUtils.initSearchLandingCue()")
    page.evaluate("window.SiteUtils && window.SiteUtils.initSearchLandingCue && window.SiteUtils.initSearchLandingCue()")

    assert page.locator(".search-landing-note").count() == 1
    assert page.evaluate("document.title") == orig_title
    assert page.evaluate("document.activeElement.tagName") == orig_active
    assert page.locator("#pdf-page-46").get_attribute("tabindex") == orig_tabindex

    # ────────────────────────
    # 二十七、Responsive & 390px Bounding Box 檢查
    # ────────────────────────
    responsive_pages = [
        f"{base}/versions/115-04/chapters/part-1/guarantee-subject.html",
        f"{base}/versions/115-04/chapters/part-1/guarantee-ratio.html",
        f"{base}/versions/115-04/appendices/appendix-10.html",
        f"{base}/versions/115-04/forms/form-25a.html",
    ]
    for url in responsive_pages:
        open_and_wait(page, url)
        assert_no_overflow(page)

    if vp["width"] == 390:
        # Check landing page bounding box on 390
        open_and_wait(page, f"{base}/versions/115-04/chapters/part-3/subrogation-scope.html?fromSearch=1&q=代償利息#pdf-page-46")
        assert_no_overflow(page)

        nav_link = page.locator(".reading-pagination a").first
        if nav_link.count() > 0:
            box = nav_link.bounding_box()
            if box:
                assert box["x"] >= 0 and box["x"] + box["width"] <= 390 + 1

        note_el = page.locator(".search-landing-note").first
        if note_el.count() > 0:
            nbox = note_el.bounding_box()
            if nbox:
                assert nbox["x"] >= 0 and nbox["x"] + nbox["width"] <= 390 + 1

        rts_el = page.locator(".return-to-search").first
        if rts_el.count() > 0:
            rbox = rts_el.bounding_box()
            if rbox:
                assert rbox["x"] >= 0 and rbox["x"] + rbox["width"] <= 390 + 1

    page.close()

    # ────────────────────────
    # 四、錯誤監控斷言
    # ────────────────────────
    assert console_errors == [], f"Console errors on {vp['width']}px: {console_errors}"
    assert page_errors == [], f"Page errors on {vp['width']}px: {page_errors}"
    assert network_404s == [], f"Network 404s on {vp['width']}px: {network_404s}"

    print(f"\n{vp['width']}:\nconsole={len(console_errors)}\npageerror={len(page_errors)}\n404={len(network_404s)}")


def main() -> None:
    server = http.server.HTTPServer(("127.0.0.1", 0), QuietHandler)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    base = f"http://127.0.0.1:{server.server_port}"

    import os
    os.chdir(SITE)

    auth_data = get_authoritative_sequence()

    with sync_playwright() as p:
        browser = p.chromium.launch()

        for vp in VIEWPORTS:
            context = browser.new_context(
                viewport=vp,
                permissions=["clipboard-read", "clipboard-write"]
            )
            run_full_journey(context, base, vp, auth_data)
            context.close()

        browser.close()

    server.shutdown()
    print("\nReading Navigation & Search Landing Cue E2E Matrix PASSED!")


if __name__ == "__main__":
    main()
