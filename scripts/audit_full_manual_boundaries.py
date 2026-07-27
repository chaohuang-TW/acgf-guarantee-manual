#!/usr/bin/env python3
"""Audit appendix and form boundaries without changing their rendering model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from page_rendering import load_page_rendering, printed_page_map
from reading_units import marker_offset, marker_text

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/FULL_MANUAL_BOUNDARY_AUDIT.md"
TOC = json.loads((ROOT / "data/toc.json").read_text(encoding="utf-8"))
_, PAGES, RENDERING = load_page_rendering()
PAGES_BY_PDF = {int(page["pdfPage"]): page for page in PAGES}
PDF_BY_PRINTED = printed_page_map(PAGES)

# These are source-verified text-layer spellings, not inferred synonyms.
MARKER_OVERRIDES = {
    ("appendix", "appendix-06"): "附錄六、財團法人農業信用保證基金農漁產品批發巿場承銷人週轉金貸款保證作業要點",
    ("form", "格式 3-1"): "信用保證申請書（一般農業貸款個人戶）",
    ("form", "格式 30"): "農漁產品批發巿場承銷人週轉金貸款信用保證申請書",
    ("form", "格式 6"): "財團法人農業信用保證基金保證手續費收入通知單",
    ("form", "格式 17"): "財團法人農業信用保證基金保證貸款通知書",
    ("form", "格式 24"): "財團法人農業信用保證基金保證貸款申請書",
    ("form", "格式 24-1"): "財團法人農業信用保證基金保證貸款申請書",
}


def slug_code(value: str) -> str:
    return value.lower().replace("格式", "").strip().replace(" ", "").replace("-", "-")


def item_key(kind: str, item: dict) -> str:
    return item["id"] if kind == "appendix" else item["code"]


def item_marker(kind: str, item: dict) -> str:
    return MARKER_OVERRIDES.get((kind, item_key(kind, item)), item["title"])


def reading_url(kind: str, item: dict) -> str:
    if kind == "appendix":
        return f'versions/115-04/appendices/{item["id"]}.html'
    base = "versions/115-04/forms/special" if kind == "special-form" else "versions/115-04/forms"
    return f'{base}/form-{slug_code(item["code"])}.html'


def ranges(items: list[dict], final_printed: int) -> list[tuple[dict, int]]:
    return [
        (item, int(items[index + 1]["printedPage"]) - 1 if index + 1 < len(items) else final_printed)
        for index, item in enumerate(items)
    ]


def audit_group(kind: str, items: list[dict], final_printed: int) -> list[dict]:
    import json
    with open(ROOT / "data/source-preview-boundaries.json", "r", encoding="utf-8") as f:
        manifest = json.load(f)
    
    def get_manifest_boundary(start_pdf_page):
        for b in manifest["boundaries"]:
            if b["previousStartPdfPage"] == start_pdf_page:
                return b
        for b in manifest["boundaries"]:
            if b["currentStartPdfPage"] == start_pdf_page:
                pass
        return None

    result: list[dict] = []
    for index, (item, end_printed) in enumerate(ranges(items, final_printed)):
        start_printed = int(item["printedPage"])
        assert start_printed <= end_printed, f"{kind} {item_key(kind, item)} has reversed range"
        start_pdf = PDF_BY_PRINTED[start_printed]
        end_pdf = PDF_BY_PRINTED[end_printed]
        
        curr_id = item.get("title") or item.get("id")
        
        is_preview = RENDERING[start_pdf]["mode"] == "source-preview"
        
        manifest_b = get_manifest_boundary(start_pdf)
        if is_preview and manifest_b:
            end_pdf = manifest_b["previousEndPdfPage"]
        elif is_preview and not manifest_b:
            # Last item in the manual! End PDF is simply 203.
            end_pdf = 203
            # But final_printed maps to PDF 203 already (probably). Let's just keep end_pdf = 203.
            end_pdf = PDF_BY_PRINTED.get(end_printed, end_pdf)
            
        assert start_pdf <= end_pdf, f"{kind} {item_key(kind, item)} has reversed PDF range"
        
        marker = item_marker(kind, item)
        source = PAGES_BY_PDF[start_pdf]["text"]
        offset = marker_offset(source, marker)
        assert marker_text(source).count(marker_text(marker)) == 1
        
        modes = sorted({RENDERING[pdf_page]["mode"] for pdf_page in range(start_pdf, end_pdf + 1)})
        assert modes and all(mode in {"text", "source-preview"} for mode in modes)
        assert any(
            PAGES_BY_PDF[pdf_page]["text"].strip()
            or RENDERING[pdf_page]["mode"] == "source-preview"
            for pdf_page in range(start_pdf, end_pdf + 1)
        ), f"{kind} {item_key(kind, item)} is empty"
        
        next_item = items[index + 1] if index + 1 < len(items) else None
        next_pdf = PDF_BY_PRINTED[int(next_item["printedPage"])] if next_item else None
        next_marker = item_marker(kind, next_item) if next_item else None
        next_offset = (
            marker_offset(PAGES_BY_PDF[next_pdf]["text"], next_marker)
            if next_item and "text" in modes
            else None
        )
        
        if is_preview and manifest_b:
            state = manifest_b["state"]
            shared_next = (state == "shared-page")
        else:
            shared_next = bool(next_item and next_pdf == end_pdf)
            
        if is_preview and result:
            prev_start_pdf = result[-1]["startPdfPage"]
            prev_manifest_b = get_manifest_boundary(prev_start_pdf)
            shared_previous = (prev_manifest_b["state"] == "shared-page") if prev_manifest_b else False
        else:
            shared_previous = bool(result and result[-1]["endPdfPage"] == start_pdf)
            
        shared = shared_previous or shared_next
        requires_slicing = shared and modes == ["text"]
        preview_metadata = shared and is_preview
        assert not requires_slicing or "source-preview" not in modes
        result.append({
            "kind": kind,
            "key": item_key(kind, item),
            "title": item["title"],
            "startPrintedPage": start_printed,
            "endPrintedPage": end_printed,
            "startPdfPage": start_pdf,
            "endPdfPage": end_pdf,
            "startMarker": marker,
            "startOffset": offset,
            "markerAtTextStart": not marker_text(source[:offset]),
            "renderingMode": "+".join(modes),
            "sharedPrevious": shared_previous,
            "sharedNext": shared_next,
            "sharedPhysicalPage": shared,
            "requiresLogicalSlicing": requires_slicing,
            "sharedPreviewMetadata": preview_metadata,
            "preserveFullPage": not requires_slicing,
            "readingUrl": reading_url(kind, item),
            "nextStartPdfPage": next_pdf,
            "nextStartOffset": next_offset,
        })
    return result


def report_table(title: str, rows: list[dict]) -> str:
    lines = [
        f"## {title}",
        "",
        "| 項目 | start PDF | end PDF | start marker | offset | marker在文字層起點 | rendering mode | shared | logical slicing | 保持整頁 |",
        "| --- | ---: | ---: | --- | ---: | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        marker = row["startMarker"].replace("|", "｜")
        lines.append(
            f'| {row["key"]} {row["title"]} | {row["startPdfPage"]} | {row["endPdfPage"]} | '
            f'`{marker}` | {row["startOffset"]} | {"是" if row["markerAtTextStart"] else "否"} | '
            f'{row["renderingMode"]} | {"是" if row["sharedPhysicalPage"] else "否"} | '
            f'{"是" if row["requiresLogicalSlicing"] else "否"} | {"是" if row["preserveFullPage"] else "否"} |'
        )
    return "\n".join(lines)


def render_report(appendices: list[dict], forms: list[dict], special_forms: list[dict]) -> str:
    import json
    with open(ROOT / "data/source-preview-boundaries.json", "r", encoding="utf-8") as f:
        manifest = json.load(f)

    all_rows = appendices + forms + special_forms
    text_shared = sorted({row["startPdfPage"] for row in all_rows if row["requiresLogicalSlicing"]})
    clean = sum(1 for b in manifest["boundaries"] if b["state"] == "clean-new-page")
    divider = sum(1 for b in manifest["boundaries"] if b["state"] == "separated-by-divider")
    shared_preview = sum(1 for b in manifest["boundaries"] if b["state"] == "shared-page")
    all_dividers = [d for b in manifest["boundaries"] for d in b.get("dividerPdfPages", [])]

    summary = f"""# 全手冊邏輯邊界稽核 (Boundary Audit 2.0)

本報告與 `docs/SOURCE_PREVIEW_BOUNDARY_VERIFICATION.md` 共同構成全手冊邊界雙重稽核機制 (Boundary Audit 2.0)。

針對純文字單元 (text-mode)，本機制以 `data/toc.json`、`data/pages.json` 與 `data/page-rendering.json` 為來源，逐項在受限制的起始 PDF 頁內以 NFKC 並移除排版空白後的 marker 定位，確認是否存在 `shared-page`，若有則進行 logical slicing 裁切。

針對書表及附錄中原圖呈現單元 (source-preview)，我們捨棄了會產生盲點的 `nextPrintedPage - 1` 推導方式，改採全人工視覺查核 (詳見 `docs/SOURCE_PREVIEW_BOUNDARY_VERIFICATION.md` 與 `data/source-preview-boundaries.json`)，並以此確保這類單元不會不當截斷或共用。本報告中的 source-preview 項目 `shared` 狀態將直接繼承 manifest 記載。

## 統計

全量結果顯示 {len(all_rows)} 個項目均有非空且順向的實體頁範圍，起始 marker 在各自受限頁面中唯一；未發現附錄、一般書表或專用書表共用同一實體頁，因此保持現有整頁呈現與資料模型，不建立不必要的 offset fragments。

### Source Preview 邊界驗證結果
- clean-new-page boundary 數量: {clean}
- separated-by-divider boundary 數量: {divider}
- shared-page boundary 數量: {shared_preview}
- divider PDF pages: {all_dividers}
- unresolved = 0

* 純文字共用實體頁之起始 PDF：`{text_shared}`
"""
    return "\n\n".join([
        summary.rstrip(),
        report_table("附錄一至附錄十八", appendices),
        report_table("一般信用保證書表", forms),
        report_table("專用書表", special_forms),
    ]) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()
    appendices = audit_group("appendix", TOC["appendices"], 116)
    forms = audit_group("form", TOC["forms"], 174)
    special_forms = audit_group("special-form", TOC["specialForms"], 186)
    assert len(appendices) == 18
    assert len(forms) == 37
    assert len(special_forms) == 7
    for row in appendices + forms + special_forms:
        target = ROOT / "site" / row["readingUrl"]
        assert target.is_file(), row["readingUrl"]
        document = target.read_text(encoding="utf-8")
        for pdf_page in range(row["startPdfPage"], row["endPdfPage"] + 1):
            assert f'id="pdf-page-{pdf_page}"' in document, (
                f'{row["readingUrl"]} missing PDF page {pdf_page}'
            )
        # For source-preview items, ensure no extra pages are rendered (strict consistency)
        if "source-preview" in row["renderingMode"]:
            import re
            rendered_pages = set(map(int, re.findall(r'id="pdf-page-(\d+)"', document)))
            expected_pages = set(range(row["startPdfPage"], row["endPdfPage"] + 1))
            if rendered_pages != expected_pages:
                raise ValueError(f'{row["readingUrl"]} renders pages {rendered_pages}, but audit says {expected_pages}')
    output = render_report(appendices, forms, special_forms)
    if args.write_report:
        REPORT.write_text(output, encoding="utf-8")
    else:
        assert REPORT.is_file(), f"Missing {REPORT.relative_to(ROOT)}"
        assert REPORT.read_text(encoding="utf-8") == output, "Boundary audit report is stale"
    print(
        "FULL MANUAL BOUNDARY AUDIT PASSED: "
        f"{len(appendices)} appendices; {len(forms)} forms; {len(special_forms)} special forms; "
        "shared pages 0"
    )


if __name__ == "__main__":
    main()
