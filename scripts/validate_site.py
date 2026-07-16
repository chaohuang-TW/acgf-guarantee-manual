#!/usr/bin/env python3
"""Validate content integrity, internal links, search data, and deployment safety."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
VERSION_PATH = ROOT / "data" / "version.json"
VERSIONS_PATH = ROOT / "data" / "versions.json"
VERSION = json.loads(VERSION_PATH.read_text(encoding="utf-8"))
SOURCE_PDF = ROOT / "source" / VERSION["sourceFile"]
DOWNLOAD_PDF = SITE / "downloads" / VERSION["sourceFile"]
EXPECTED_SHA = VERSION["sha256"]
EXPECTED_PDF_PAGES = VERSION["pdfPageCount"]
VERSION_ROOT = f"versions/{VERSION['id']}"
DISCLAIMER_FRAGMENT = "本網站為公開資料數位閱讀版，非農業信用保證基金官方網站"
KEYWORDS = [
    "保證對象", "保證貸款用途", "保證成數", "最高保證成數表", "不予保證規定",
    "同一經濟利害關係人", "申請信用保證", "保證手續費", "期中管理", "信用惡化",
    "前置協商", "逾期案件", "轉（展）期", "借新還舊", "代位清償", "免責", "債權追索",
    "附錄十八", "格式3", "格式25", "格式31",
]


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.links: list[str] = []
        self.resources: list[str] = []
        self.title_count = 0
        self.h1_count = 0
        self._in_title = False
        self._title_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(values["id"] or "")
        if tag == "a" and values.get("href"):
            self.links.append(values["href"] or "")
        if tag in {"script", "img", "iframe", "video", "audio", "source"} and values.get("src"):
            self.resources.append(values["src"] or "")
        if tag == "link" and values.get("href") and values.get("rel") != "canonical":
            self.resources.append(values["href"] or "")
        if tag == "title":
            self._in_title = True
            self.title_count += 1
        if tag == "h1":
            self.h1_count += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_text.append(data)


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).lower()
    value = re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", value)
    return re.sub(r"\s+", "", value)


def resolve_link(page: Path, href: str) -> Path | None:
    parts = urlsplit(href)
    if parts.scheme in {"http", "https", "mailto", "tel", "data"} or href.startswith("#"):
        return None
    target = unquote(parts.path)
    if not target:
        return None
    path = (page.parent / target).resolve()
    if target.endswith("/"):
        path = path / "index.html"
    return path


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    if not VERSIONS_PATH.is_file():
        errors.append("data/versions.json missing")
        versions = []
    else:
        try:
            versions = json.loads(VERSIONS_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"invalid data/versions.json: {exc}")
            versions = []
    if not isinstance(versions, list) or not versions:
        errors.append("data/versions.json must contain at least one version record")
        versions = []

    current_records = [record for record in versions if record.get("isCurrent") is True]
    if len(current_records) != 1:
        errors.append(f"expected exactly one current version, found {len(current_records)}")
        current = None
    else:
        current = current_records[0]

    for field in ("id", "releaseTag", "sitePath"):
        values = [record.get(field) for record in versions]
        if len(values) != len(set(values)):
            errors.append(f"duplicate version {field}")
    for record in versions:
        if record.get("status") not in {"current", "archived"}:
            errors.append(f"invalid version status: {record.get('id')}")
        if record.get("isCurrent") != (record.get("status") == "current"):
            errors.append(f"version current status mismatch: {record.get('id')}")
        if not re.fullmatch(r"v\d{3}\.\d{2}\.\d+", str(record.get("releaseTag", ""))):
            errors.append(f"invalid release tag: {record.get('releaseTag')}")
        expected_tag = "v" + str(record.get("id", "")).replace("-", ".") + ".0"
        if record.get("releaseTag") != expected_tag:
            errors.append(f"release tag does not match version id: {record.get('id')}")
        site_path = SITE / str(record.get("sitePath", ""))
        pdf_path = SITE / str(record.get("pdfPath", ""))
        source_path = ROOT / "source" / str(record.get("sourceFile", ""))
        if not site_path.is_dir():
            errors.append(f"version sitePath missing: {record.get('sitePath')}")
        if not pdf_path.is_file():
            errors.append(f"version pdfPath missing: {record.get('pdfPath')}")
        if not source_path.is_file():
            errors.append(f"version sourceFile missing: {record.get('sourceFile')}")

    if current:
        for field in ("id", "versionLabel", "edition", "pdfPageCount", "sha256", "noTextLayerPages", "isCurrent"):
            if current.get(field) != VERSION.get(field):
                errors.append(f"version metadata mismatch: {field}")

    if not SOURCE_PDF.is_file() or not DOWNLOAD_PDF.is_file():
        errors.append("source or download PDF missing")
    else:
        if len(PdfReader(str(SOURCE_PDF)).pages) != EXPECTED_PDF_PAGES:
            errors.append(f"source PDF does not contain {EXPECTED_PDF_PAGES} pages")
        source_sha = digest(SOURCE_PDF)
        download_sha = digest(DOWNLOAD_PDF)
        if source_sha != EXPECTED_SHA or download_sha != EXPECTED_SHA or source_sha != download_sha:
            errors.append("PDF SHA-256 mismatch")

    html_files = sorted(SITE.rglob("*.html"))
    if not html_files:
        errors.append("no HTML files generated")
    if current and len(html_files) != current.get("htmlPageCount"):
        errors.append(f"HTML page count mismatch: actual {len(html_files)}, recorded {current.get('htmlPageCount')}")

    for page in html_files:
        text = page.read_text(encoding="utf-8")
        parser = PageParser()
        parser.feed(text)
        relative = page.relative_to(SITE)
        if parser.title_count != 1 or not "".join(parser._title_text).strip():
            errors.append(f"invalid title: {relative}")
        if parser.h1_count != 1:
            errors.append(f"expected one h1, found {parser.h1_count}: {relative}")
        duplicates = sorted({item for item in parser.ids if parser.ids.count(item) > 1})
        if duplicates:
            errors.append(f"duplicate ids in {relative}: {duplicates}")
        if DISCLAIMER_FRAGMENT not in text:
            errors.append(f"missing disclaimer: {relative}")
        if 'href="/' in text or 'src="/' in text:
            errors.append(f"root-relative project path: {relative}")
        for resource in parser.resources:
            if urlsplit(resource).scheme in {"http", "https"} or resource.startswith("//"):
                errors.append(f"external resource in {relative}: {resource}")
            else:
                target = resolve_link(page, resource)
                if target and not target.exists():
                    errors.append(f"missing resource from {relative}: {resource}")
        for href in parser.links:
            target = resolve_link(page, href)
            if target and not target.exists():
                errors.append(f"broken link from {relative}: {href}")

    search_path = SITE / "assets" / "data" / "search-index.json"
    if not search_path.is_file():
        errors.append("search index missing")
        search = []
    else:
        search = json.loads(search_path.read_text(encoding="utf-8"))
        ids = [record["id"] for record in search]
        if len(ids) != len(set(ids)):
            errors.append("duplicate search index ids")
        for record in search:
            pdf_page = record.get("pdfPage")
            if not isinstance(pdf_page, int) or not 1 <= pdf_page <= EXPECTED_PDF_PAGES:
                errors.append(f"search PDF page out of range: {record.get('id')}")
            target = SITE / record["url"]
            if not target.is_file():
                errors.append(f"search result URL missing: {record['url']}")
            if not record.get("text", "").strip():
                errors.append(f"blank search text: {record.get('id')}")
        corpus = normalize(" ".join(record["text"] for record in search))
        for keyword in KEYWORDS:
            if normalize(keyword) not in corpus:
                errors.append(f"required keyword not searchable: {keyword}")

    if current and len(search) != current.get("searchRecordCount"):
        errors.append(f"search record count mismatch: actual {len(search)}, recorded {current.get('searchRecordCount')}")

    versions_page = SITE / "versions" / "index.html"
    if not versions_page.is_file():
        errors.append("version history page missing")
    else:
        versions_text = versions_page.read_text(encoding="utf-8")
        versions_parser = PageParser()
        versions_parser.feed(versions_text)
        if DISCLAIMER_FRAGMENT not in versions_text:
            errors.append("version history page missing disclaimer")
        if versions_parser.h1_count != 1:
            errors.append(f"version history page expected one h1, found {versions_parser.h1_count}")
        duplicate_version_ids = sorted({item for item in versions_parser.ids if versions_parser.ids.count(item) > 1})
        if duplicate_version_ids:
            errors.append(f"duplicate ids in version history page: {duplicate_version_ids}")

    expected_versions_page = (SITE / "versions" / "index.html").resolve()
    home_parser = PageParser()
    home_parser.feed((SITE / "index.html").read_text(encoding="utf-8"))
    if not any(resolve_link(SITE / "index.html", href) == expected_versions_page for href in home_parser.links):
        errors.append("homepage does not link to version history")
    content_root = SITE / VERSION_ROOT
    for content_page in sorted(content_root.rglob("*.html")):
        content_parser = PageParser()
        content_parser.feed(content_page.read_text(encoding="utf-8"))
        if not any(resolve_link(content_page, href) == expected_versions_page for href in content_parser.links):
            errors.append(f"content page does not link to version history: {content_page.relative_to(SITE)}")

    for part in range(1, 5):
        target = SITE / f"{VERSION_ROOT}/chapters/part-{part}/index.html"
        if not target.is_file() or target.stat().st_size < 1000:
            errors.append(f"missing or blank main part: part-{part}")
    for appendix in range(1, 19):
        if not (SITE / f"{VERSION_ROOT}/appendices/appendix-{appendix:02d}.html").is_file():
            errors.append(f"missing appendix entry: {appendix}")

    joined = "\n".join(path.read_text(encoding="utf-8") for path in [SITE / "index.html", SITE / "assets/js/search.js"])
    forbidden = ["google-analytics", "googletagmanager", "facebook pixel", "openai api", "chatgpt", "embedding", "localstorage", "document.cookie"]
    for token in forbidden:
        if token in joined.lower():
            errors.append(f"forbidden service or tracking token: {token}")

    if errors:
        print("VALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("VALIDATION PASSED")
    print(f"- HTML pages: {len(html_files)}")
    print(f"- Search records: {len(search)}")
    print(f"- PDF pages: {EXPECTED_PDF_PAGES}")
    print(f"- PDF SHA-256: {EXPECTED_SHA}")
    for warning in warnings:
        print(f"- WARNING: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
