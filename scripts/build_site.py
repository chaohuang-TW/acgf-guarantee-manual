#!/usr/bin/env python3
"""Build a dependency-free static reading site for GitHub Project Pages."""

from __future__ import annotations

import html
import json
import posixpath
import re
import shutil
from pathlib import Path, PurePosixPath

from page_rendering import load_page_rendering

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
PAGES = json.loads((ROOT / "data" / "pages.json").read_text(encoding="utf-8"))
VERSION = json.loads((ROOT / "data" / "version.json").read_text(encoding="utf-8"))
VERSIONS = json.loads((ROOT / "data" / "versions.json").read_text(encoding="utf-8"))
TOC = json.loads((ROOT / "data" / "toc.json").read_text(encoding="utf-8"))
TEMPLATES = {path.stem: path.read_text(encoding="utf-8") for path in (ROOT / "templates").glob("*.html")}
PAGE_RENDERING, _, RESOLVED_RENDERING = load_page_rendering()
PREVIEW_ROOT = ROOT / "assets" / "page-previews" / VERSION["id"]
PREVIEW_MANIFEST = {
    int(item["pdfPage"]): item
    for item in json.loads((PREVIEW_ROOT / "manifest.json").read_text(encoding="utf-8"))
}

BASE_PATH = "/acgf-guarantee-manual/"
ORIGIN = "https://chaohuang-tw.github.io"
VERSION_ROOT = f"versions/{VERSION['id']}"
PDF_NAME = VERSION["sourceFile"]
VERSION_LABEL = VERSION["versionLabel"]
PDF_PAGE_COUNT = VERSION["pdfPageCount"]
REPOSITORY_URL = "https://github.com/chaohuang-TW/acgf-guarantee-manual"
DISCLAIMER = "本網站為公開資料數位閱讀版，非農業信用保證基金官方網站。內容如與正式PDF、後續函釋或公告不一致，以正式發布文件為準。"


def e(value: object) -> str:
    return html.escape(str(value), quote=True)


def slug_code(code: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", code.lower().replace("格式", "form")).strip("-")


PRINTED_TO_PDF = {int(page["printedPage"]): page["pdfPage"] for page in PAGES if page["printedPage"]}
# PDF page 126 is the final page of appendix 18 (printed page 116) and has no
# extractable text layer. This mapping comes from the surrounding printed pages
# and the original table of contents; no page text is invented.
PRINTED_TO_PDF[116] = 126


def pdf_for_printed(number: int) -> int:
    if number not in PRINTED_TO_PDF:
        raise ValueError(f"No PDF page mapping for printed page {number}")
    return PRINTED_TO_PDF[number]


def output_path(relative: str) -> Path:
    return SITE / relative


def rel_from(relative: str, target: str) -> str:
    directory = str(PurePosixPath(relative).parent)
    if target == "":
        prefix = posixpath.relpath(".", directory)
        return "./" if prefix == "." else prefix.rstrip("/") + "/"
    return posixpath.relpath(target, directory)


def fill(template: str, **values: str) -> str:
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", value)
    return template


def search_box(compact: bool = False) -> str:
    class_name = "search-panel compact" if compact else "search-panel"
    return f"""
      <div class="{class_name}" data-search>
        <form role="search" novalidate>
          <label for="site-search">全文搜尋</label>
          <div class="search-row">
            <input id="site-search" name="q" type="search" autocomplete="off" placeholder="搜尋保證成數、同一經濟利害關係人、轉（展）期、代位清償……">
            <button type="submit">搜尋</button>
          </div>
        </form>
        <p class="search-status" aria-live="polite"></p>
        <div class="search-results"></div>
      </div>
    """


def breadcrumb(items: list[tuple[str, str | None]], current: str) -> str:
    links = []
    for label, url in items:
        links.append(f'<a href="{e(url)}">{e(label)}</a>' if url else f"<span>{e(label)}</span>")
    links.append(f'<span aria-current="page">{e(current)}</span>')
    return '<nav class="breadcrumb" aria-label="麵包屑">' + "<span aria-hidden=\"true\">›</span>".join(links) + "</nav>"


def resolve_page_rendering(page: dict) -> dict:
    return RESOLVED_RENDERING[int(page["pdfPage"])]


def text_body(page: dict) -> str:
    return f'<pre class="source-text">{e(page["text"])}</pre>'


def blank_page_body() -> str:
    return (
        '<div class="blank-source-page" role="note"><strong>原始PDF空白頁</strong>'
        '<p>本頁在來源文件中為空白頁，未進行文字重建或內容補充。</p></div>'
    )


def source_preview_body(page: dict, relative: str, rendering: dict, pdf_url: str) -> str:
    pdf_page = page["pdfPage"]
    manifest = PREVIEW_MANIFEST.get(pdf_page)
    if not manifest:
        raise ValueError(f"Missing preview manifest entry for PDF page {pdf_page}")
    preview_url = rel_from(
        relative, f"assets/page-previews/{VERSION['id']}/{manifest['file']}"
    )
    full_pdf_url = rel_from(relative, f"downloads/{PDF_NAME}")
    details = ""
    if page["hasTextLayer"]:
        details = (
            '<details class="extracted-text-details"><summary>查看PDF文字層</summary>'
            '<div class="layout-note" role="note">下列文字取自PDF既有文字層，僅供搜尋、複製與無障礙輔助。'
            '複雜表格的欄列位置可能失真，正式內容請以原頁預覽或PDF為準。</div>'
            f'<pre class="source-text source-text-secondary">{e(page["text"])}</pre></details>'
        )
    return f"""
        <figure class="source-preview">
          <a class="source-preview-link" href="{e(preview_url)}" aria-label="放大查看原始PDF第{pdf_page}頁預覽">
            <img class="source-preview-image" src="{e(preview_url)}" alt="原始PDF第{pdf_page}頁預覽：{e(rendering['label'])}" width="{manifest['width']}" height="{manifest['height']}" loading="lazy" decoding="async">
          </a>
          <figcaption>本頁含複雜表格或正式書表，網頁依原始PDF版面呈現。正式內容仍以原始PDF為準。</figcaption>
        </figure>
        <nav class="preview-actions" aria-label="PDF第{pdf_page}頁預覽操作">
          <a href="{e(preview_url)}">放大查看原頁預覽</a>
          <a href="{e(pdf_url)}">開啟原始PDF此頁</a>
          <a href="{e(full_pdf_url)}">開啟／下載完整PDF</a>
        </nav>
        {details}
    """


def page_card(page: dict, relative: str, heading_level: int = 2) -> str:
    printed = page["printedPage"] or "無"
    pdf_page = page["pdfPage"]
    pdf_url = rel_from(relative, f"downloads/{PDF_NAME}") + f"#page={pdf_page}"
    rendering = resolve_page_rendering(page)
    if rendering["mode"] == "source-preview":
        actions = ""
        body = source_preview_body(page, relative, rendering, pdf_url)
    elif rendering["mode"] == "blank-page":
        actions = f'<div class="page-actions"><a href="{e(pdf_url)}">開啟原始PDF此頁</a></div>'
        body = blank_page_body()
    else:
        actions = f'<div class="page-actions"><a href="{e(pdf_url)}">開啟原始PDF此頁</a></div>'
        body = text_body(page)
    return f"""
      <section class="page-card" id="pdf-page-{pdf_page}">
        <h{heading_level}>手冊頁：{e(printed)} <small>PDF頁：{pdf_page}／{PDF_PAGE_COUNT}</small></h{heading_level}>
        {actions}
        {body}
      </section>
    """


def page_range(start_printed: int, end_printed: int) -> list[dict]:
    start_pdf = pdf_for_printed(start_printed)
    end_pdf = pdf_for_printed(end_printed)
    return [page for page in PAGES if start_pdf <= page["pdfPage"] <= end_pdf]


def write(relative: str, title: str, main: str) -> None:
    path = output_path(relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    root = rel_from(relative, "index.html")
    version_url = rel_from(relative, f"{VERSION_ROOT}/index.html")
    versions_url = rel_from(relative, "versions/index.html")
    pdf_url = rel_from(relative, f"downloads/{PDF_NAME}")
    html_text = fill(
        TEMPLATES["base"],
        TITLE=e(title + "｜農業信用保證業務作業手冊"),
        CANONICAL=e(ORIGIN + BASE_PATH + relative.replace("index.html", "")),
        ASSET_PREFIX=e(rel_from(relative, "")),
        SITE_ROOT=e(rel_from(relative, "")),
        SEARCH_INDEX=e(rel_from(relative, "assets/data/search-index.json")),
        HOME_URL=e(root),
        VERSION_URL=e(version_url),
        VERSIONS_URL=e(versions_url),
        PDF_URL=e(pdf_url),
        VERSION_LABEL=e(VERSION_LABEL),
        EDITION=e(VERSION["edition"]),
        MAIN=main,
    )
    html_text = "\n".join(line.rstrip() for line in html_text.splitlines()) + "\n"
    path.write_text(html_text, encoding="utf-8")


def unit_ranges(items: list[dict], final_printed: int) -> list[tuple[dict, int]]:
    result = []
    for index, item in enumerate(items):
        end = items[index + 1]["printedPage"] - 1 if index + 1 < len(items) else final_printed
        result.append((item, end))
    return result


def local_part_nav(part: dict, relative: str) -> str:
    links = []
    for section in part["sections"]:
        target = f'{VERSION_ROOT}/chapters/{part["id"]}/{section["id"]}.html'
        links.append(f'<li><a href="{e(rel_from(relative, target))}">{e(section["title"])}</a></li>')
    return f'<details open><summary>{e(part["title"])}</summary><ol>{"".join(links)}</ol></details>'


def build_home() -> None:
    keywords = ["保證對象", "保證成數", "不予保證", "保證手續費", "同一經濟利害關係人", "轉（展）期", "逾期處理", "代位清償"]
    keyword_html = "".join(f'<button type="button" data-keyword="{e(word)}">{e(word)}</button>' for word in keywords)
    hero = f"""
      <div class="current-version">目前版本 <strong>{e(VERSION_LABEL)}</strong></div>
      <h1>農業信用保證業務作業手冊</h1>
      <p class="subtitle">{e(VERSION['edition'])}｜公開資料數位閱讀版</p>
      {search_box()}
      <div class="popular" aria-label="熱門關鍵字"><span>熱門關鍵字</span>{keyword_html}</div>
    """
    quick = []
    for part in TOC["parts"]:
        url = f'{VERSION_ROOT}/chapters/{part["id"]}/index.html'
        quick.append(f'<a class="entry primary" href="{e(url)}"><strong>{e(part["shortTitle"])}</strong><span>{e(part["title"])}</span></a>')
    secondary = [
        ("附錄", f"{VERSION_ROOT}/appendices/index.html"),
        ("查索表", f"{VERSION_ROOT}/appendices/appendix-18.html"),
        ("信用保證書表", f"{VERSION_ROOT}/forms/index.html"),
        ("下載完整PDF", f"downloads/{PDF_NAME}"),
    ]
    quick.extend(f'<a class="entry" href="{e(url)}"><strong>{e(label)}</strong><span>開啟資料</span></a>' for label, url in secondary)
    version_panel = f"""
      <h2 id="version-title">版本資訊</h2>
      <dl><div><dt>資料版本</dt><dd>{e(VERSION_LABEL)}</dd></div><div><dt>來源文件</dt><dd>財團法人農業信用保證基金<br>保證業務作業手冊（{e(VERSION['edition'])}）</dd></div><div><dt>PDF實體頁數</dt><dd>{PDF_PAGE_COUNT}頁</dd></div></dl>
      <p><a class="button-link" href="downloads/{PDF_NAME}">開啟／下載完整原始PDF</a></p>
      <p><a href="versions/index.html">查看版本紀錄</a></p>
      <p class="disclaimer">{e(DISCLAIMER)}</p>
    """
    main = fill(TEMPLATES["home"], HERO=hero, QUICK_LINKS=f'<div class="entry-grid">{"".join(quick)}</div>', VERSION_PANEL=version_panel)
    write("index.html", "首頁", main)


def build_versions_history() -> None:
    relative = "versions/index.html"
    records = []
    for version in VERSIONS:
        status_label = "目前版本" if version["isCurrent"] else "已非最新版"
        release_url = f'{REPOSITORY_URL}/releases/tag/{version["releaseTag"]}'
        initial_release_url = f'{REPOSITORY_URL}/releases/tag/{version["initialReleaseTag"]}'
        no_text_count = len(version["noTextLayerPages"])
        records.append(fill(
            TEMPLATES["versions"],
            VERSION_LABEL=e(version["versionLabel"]),
            EDITION=e(version["edition"]),
            STATUS=e(status_label),
            PUBLISHED_AT=e(version["digitalPublishedAt"]),
            UPDATED_AT=e(version["digitalUpdatedAt"]),
            PDF_PAGE_COUNT=e(version["pdfPageCount"]),
            SEARCH_RECORD_COUNT=e(version["searchRecordCount"]),
            NO_TEXT_COUNT=e(no_text_count),
            RELEASE_TAG=e(version["releaseTag"]),
            INITIAL_RELEASE_TAG=e(version["initialReleaseTag"]),
            SHA256=e(version["sha256"]),
            VERSION_URL=e(rel_from(relative, version["sitePath"] + "index.html")),
            PDF_URL=e(rel_from(relative, version["pdfPath"])),
            RELEASE_URL=e(release_url),
            INITIAL_RELEASE_URL=e(initial_release_url),
            REPOSITORY_URL=e(REPOSITORY_URL),
        ))
    content = f"""
      <h1>版本紀錄</h1>
      <p>本頁記錄農業信用保證業務作業手冊數位閱讀版的公開版本。各版本依原始PDF獨立保存，新版發布後不覆蓋或刪除舊版。</p>
      <div class="version-history">{''.join(records)}</div>
      <section class="version-policy" aria-labelledby="version-policy-title">
        <h2 id="version-policy-title">版本保存原則</h2>
        <ol>
          <li>新版本以新的版本ID與網址保存。</li>
          <li>舊版本不覆蓋、不刪除。</li>
          <li>根目錄首頁只指向目前版本。</li>
          <li>舊版本須標示「已非最新版」。</li>
          <li>正式內容仍以原始PDF、後續函釋及公告為準。</li>
        </ol>
        <p class="version-disclaimer">{e(DISCLAIMER)}</p>
      </section>
    """
    main = fill(
        TEMPLATES["index-list"],
        BREADCRUMB=breadcrumb([("首頁", rel_from(relative, "index.html"))], "版本紀錄"),
        CONTENT=content,
    )
    write(relative, "版本紀錄", main)


def build_version_index() -> None:
    relative = f"{VERSION_ROOT}/index.html"
    part_links = []
    for part in TOC["parts"]:
        url = rel_from(relative, f'{VERSION_ROOT}/chapters/{part["id"]}/index.html')
        sections = "".join(f"<li>{e(section['title'])} <small>手冊頁 {section['printedPage']}</small></li>" for section in part["sections"])
        part_links.append(f'<section class="toc-group"><h2><a href="{e(url)}">{e(part["title"])}</a></h2><ol>{sections}</ol></section>')
    extra = f"""
      <section class="toc-group"><h2><a href="{e(rel_from(relative, VERSION_ROOT + '/appendices/index.html'))}">附錄一至附錄十八</a></h2><p>依原始目錄逐項建立入口。</p></section>
      <section class="toc-group"><h2><a href="{e(rel_from(relative, VERSION_ROOT + '/forms/index.html'))}">信用保證書表</a></h2><p>{len(TOC['forms'])}項格式入口。</p></section>
      <section class="toc-group"><h2><a href="{e(rel_from(relative, VERSION_ROOT + '/forms/special/index.html'))}">專用書表</a></h2><p>{len(TOC['specialForms'])}項格式入口。</p></section>
    """
    content = f'<h1>{e(VERSION_LABEL)}完整目錄</h1>{search_box(compact=True)}<div class="toc-layout">{"".join(part_links)}{extra}</div>'
    main = fill(TEMPLATES["index-list"], BREADCRUMB=breadcrumb([("首頁", rel_from(relative, "index.html"))], "完整目錄"), CONTENT=content)
    write(relative, "完整目錄", main)


def build_parts() -> None:
    part_ends = [23, 35, 44, 46]
    for part, part_end in zip(TOC["parts"], part_ends):
        relative = f'{VERSION_ROOT}/chapters/{part["id"]}/index.html'
        content = [f'<h1>{e(part["title"])}</h1><p class="source-meta">手冊頁 {part["printedPage"]}-{part_end}</p>']
        for page in page_range(part["printedPage"], part_end):
            content.append(page_card(page, relative))
        main = fill(
            TEMPLATES["section"],
            BREADCRUMB=breadcrumb([("首頁", rel_from(relative, "index.html")), ("完整目錄", rel_from(relative, VERSION_ROOT + "/index.html"))], part["title"]),
            LOCAL_NAV=local_part_nav(part, relative),
            CONTENT="".join(content),
        )
        write(relative, part["title"], main)

        for section, section_end in unit_ranges(part["sections"], part_end):
            section_relative = f'{VERSION_ROOT}/chapters/{part["id"]}/{section["id"]}.html'
            section_content = [f'<h1>{e(section["title"])}</h1><p class="source-meta">手冊頁 {section["printedPage"]}-{section_end}</p>']
            for page in page_range(section["printedPage"], section_end):
                section_content.append(page_card(page, section_relative))
            section_main = fill(
                TEMPLATES["section"],
                BREADCRUMB=breadcrumb([("首頁", rel_from(section_relative, "index.html")), ("完整目錄", rel_from(section_relative, VERSION_ROOT + "/index.html")), (part["title"], rel_from(section_relative, relative))], section["title"]),
                LOCAL_NAV=local_part_nav(part, section_relative),
                CONTENT="".join(section_content),
            )
            write(section_relative, section["title"], section_main)


def build_appendices() -> None:
    relative = f"{VERSION_ROOT}/appendices/index.html"
    rows = []
    for item in TOC["appendices"]:
        target = f'{VERSION_ROOT}/appendices/{item["id"]}.html'
        rows.append(f'<li><a href="{e(rel_from(relative, target))}">{e(item["title"])}</a><span>手冊頁 {item["printedPage"]}</span></li>')
    content = f'<h1>附錄</h1><p>完整收錄附錄一至附錄十八。複雜查索表版面請以原始PDF為準。</p><ol class="index-rows">{"".join(rows)}</ol>'
    main = fill(TEMPLATES["index-list"], BREADCRUMB=breadcrumb([("首頁", rel_from(relative, "index.html")), ("完整目錄", rel_from(relative, VERSION_ROOT + "/index.html"))], "附錄"), CONTENT=content)
    write(relative, "附錄", main)

    for item, end in unit_ranges(TOC["appendices"], 116):
        item_relative = f'{VERSION_ROOT}/appendices/{item["id"]}.html'
        note = '<div class="layout-note"><strong>本表版面請以原始PDF為準</strong><p>文字層僅供全文搜尋，不據此重建欄列或數字位置。</p></div>' if item.get("layoutOnly") else ""
        cards = "".join(page_card(page, item_relative) for page in page_range(item["printedPage"], end))
        content = f'<h1>{e(item["title"])}</h1><p class="source-meta">手冊頁 {item["printedPage"]}-{end}</p>{note}{cards}'
        main = fill(TEMPLATES["section"], BREADCRUMB=breadcrumb([("首頁", rel_from(item_relative, "index.html")), ("完整目錄", rel_from(item_relative, VERSION_ROOT + "/index.html")), ("附錄", rel_from(item_relative, relative))], item["title"]), LOCAL_NAV='<p><a href="index.html">返回附錄目錄</a></p>', CONTENT=content)
        write(item_relative, item["title"], main)


def build_forms(items: list[dict], special: bool = False) -> None:
    base = f"{VERSION_ROOT}/forms/special" if special else f"{VERSION_ROOT}/forms"
    relative = f"{base}/index.html"
    rows = []
    for item in items:
        slug = slug_code(item["code"])
        target = f"{base}/{slug}.html"
        group = f'<small>{e(item["group"])}</small>' if special else ""
        rows.append(f'<li><a href="{e(rel_from(relative, target))}"><strong>{e(item["code"])}</strong> {e(item["title"])}</a><span>手冊頁 {item["printedPage"]}</span>{group}</li>')
    heading = "專用書表" if special else "信用保證書表"
    intro = "正式填表版面以原始PDF為準。本網站不提供可填寫或送出的線上表單。"
    content = f'<h1>{heading}</h1><p>{intro}</p><ol class="index-rows">{"".join(rows)}</ol>'
    crumbs = [("首頁", rel_from(relative, "index.html")), ("完整目錄", rel_from(relative, VERSION_ROOT + "/index.html"))]
    if special:
        crumbs.append(("信用保證書表", rel_from(relative, VERSION_ROOT + "/forms/index.html")))
    main = fill(TEMPLATES["index-list"], BREADCRUMB=breadcrumb(crumbs, heading), CONTENT=content)
    write(relative, heading, main)

    final = 186 if special else 174
    for item, end in unit_ranges(items, final):
        item_relative = f'{base}/{slug_code(item["code"])}.html'
        note = '<div class="layout-note"><strong>正式書表版面請以原始PDF為準</strong><p>下列擷取文字僅供搜尋與輔助查閱，未重新設計為線上表單。</p></div>'
        cards = "".join(page_card(page, item_relative) for page in page_range(item["printedPage"], end))
        content = f'<h1>{e(item["code"])}：{e(item["title"])}</h1><p class="source-meta">手冊頁 {item["printedPage"]}-{end}</p>{note}{cards}'
        parent_title = "專用書表" if special else "信用保證書表"
        main = fill(TEMPLATES["section"], BREADCRUMB=breadcrumb([("首頁", rel_from(item_relative, "index.html")), ("完整目錄", rel_from(item_relative, VERSION_ROOT + "/index.html")), (parent_title, rel_from(item_relative, relative))], f'{item["code"]}：{item["title"]}'), LOCAL_NAV=f'<p><a href="{e(rel_from(item_relative, relative))}">返回{parent_title}目錄</a></p>', CONTENT=content)
        write(item_relative, f'{item["code"]}：{item["title"]}', main)


def classify_page(page: dict) -> tuple[str, list[str], str]:
    printed = int(page["printedPage"]) if page["printedPage"] else None
    if printed is None:
        return ("前置頁或分隔頁", ["手冊"], f'{VERSION_ROOT}/pages/page-{page["pdfPage"]:03d}.html')
    if printed <= 46:
        part = next(part for part, end in zip(TOC["parts"], [23, 35, 44, 46]) if printed <= end)
        section = max((s for s in part["sections"] if s["printedPage"] <= printed), key=lambda s: s["printedPage"])
        return (section["title"], [part["title"], section["title"]], f'{VERSION_ROOT}/pages/page-{page["pdfPage"]:03d}.html')
    if printed <= 116:
        item = max((a for a in TOC["appendices"] if a["printedPage"] <= printed), key=lambda a: a["printedPage"])
        return (item["title"], ["附錄", item["title"]], f'{VERSION_ROOT}/pages/page-{page["pdfPage"]:03d}.html')
    source = TOC["forms"] if printed <= 174 else TOC["specialForms"]
    item = max((f for f in source if f["printedPage"] <= printed), key=lambda f: f["printedPage"])
    parent = item.get("group", "信用保證書表")
    return (f'{item["code"]}：{item["title"]}', [parent, item["code"]], f'{VERSION_ROOT}/pages/page-{page["pdfPage"]:03d}.html')


def build_physical_pages_and_search() -> None:
    index = []
    for page in PAGES:
        relative = f'{VERSION_ROOT}/pages/page-{page["pdfPage"]:03d}.html'
        title, crumbs, url = classify_page(page)
        content = f'<h1>{e(title)}</h1>{page_card(page, relative)}'
        main = fill(TEMPLATES["index-list"], BREADCRUMB=breadcrumb([("首頁", rel_from(relative, "index.html")), ("完整目錄", rel_from(relative, VERSION_ROOT + "/index.html"))], f'PDF頁 {page["pdfPage"]}'), CONTENT=content)
        write(relative, f'{title}｜PDF頁 {page["pdfPage"]}', main)
        if page["hasTextLayer"]:
            index.append({
                "id": f'page-{page["pdfPage"]:03d}',
                "version": VERSION["id"],
                "title": title,
                "breadcrumb": crumbs,
                "url": url,
                "printedPage": page["printedPage"],
                "pdfPage": page["pdfPage"],
                "text": page["searchText"],
            })
    data_dir = SITE / "assets" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "search-index.json").write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def build_robots_and_sitemap() -> None:
    html_files = sorted(path.relative_to(SITE).as_posix() for path in SITE.rglob("*.html"))
    urls = [ORIGIN + BASE_PATH + (path[:-10] if path.endswith("index.html") else path) for path in html_files]
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(f"  <url><loc>{e(url)}</loc></url>" for url in urls) + "\n</urlset>\n"
    (SITE / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    (SITE / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {ORIGIN}{BASE_PATH}sitemap.xml\n", encoding="utf-8")


def main() -> None:
    if SITE.exists():
        for child in SITE.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    (SITE / "downloads").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "source" / PDF_NAME, SITE / "downloads" / PDF_NAME)
    (SITE / ".nojekyll").write_text("", encoding="utf-8")
    shutil.copytree(ROOT / "assets", SITE / "assets", dirs_exist_ok=True)
    build_home()
    build_versions_history()
    build_version_index()
    build_parts()
    build_appendices()
    build_forms(TOC["forms"], special=False)
    build_forms(TOC["specialForms"], special=True)
    build_physical_pages_and_search()
    build_robots_and_sitemap()
    print(f"Built {len(list(SITE.rglob('*.html')))} HTML pages")


if __name__ == "__main__":
    main()
