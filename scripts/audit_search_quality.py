#!/usr/bin/env python3
"""Create a reproducible baseline audit for the current client-side search."""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "site" / "assets" / "data" / "search-index.json"
CASES_PATH = ROOT / "tests" / "search_cases.json"
JSON_REPORT = ROOT / "reports" / "search-quality-baseline.json"
MARKDOWN_REPORT = ROOT / "docs" / "SEARCH_QUALITY_AUDIT.md"
MAX_RESULTS = 50
TOP_RESULTS = 10


def normalize(value: str) -> str:
    """Match the NFKC/lowercase/whitespace behavior in assets/js/search.js."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value).lower()).strip()


def search(records: list[dict], query: str) -> list[dict]:
    needle = normalize(query)
    return [record for record in records if needle in normalize(record["text"])]


def rank_of_expected(records: list[dict], expected_urls: set[str]) -> int | None:
    for rank, record in enumerate(records, start=1):
        if record["url"] in expected_urls:
            return rank
    return None


def has_large_pdf_spacing(text: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]\s+[\u3400-\u9fff]", text) or re.search(r"\s{3,}", text))


def top_record(record: dict) -> dict:
    return {
        "title": record["title"],
        "url": record["url"],
        "printedPage": record.get("printedPage", ""),
        "pdfPage": record["pdfPage"],
        "hasLargePdfSpacing": has_large_pdf_spacing(record["text"]),
        "genericTitle": record["title"] == "前置頁或分隔頁",
    }


def case_result(case: dict, records: list[dict]) -> dict:
    expected_urls = set(case["expectedUrls"])
    matches = search(records, case["query"])
    analyzed = matches[:MAX_RESULTS]
    rank = rank_of_expected(analyzed, expected_urls)
    alias_ranks = {alias: rank_of_expected(search(records, alias)[:MAX_RESULTS], expected_urls) for alias in case["aliases"]}
    formal_alias_rank = next((rank for rank in alias_ranks.values() if rank is not None), None)
    if case.get("ambiguous"):
        outcome = "AMBIGUOUS"
    elif rank is not None and rank <= 3:
        outcome = "PASS"
    elif rank is not None and rank <= 10:
        outcome = "WEAK"
    else:
        outcome = "FAIL"
    top = [top_record(record) for record in analyzed[:TOP_RESULTS]]
    return {
        "query": case["query"],
        "intent": case["intent"],
        "expectedUrls": case["expectedUrls"],
        "expectedType": case["expectedType"],
        "aliases": case["aliases"],
        "ambiguous": case.get("ambiguous", False),
        "resultCount": len(matches),
        "analysisLimitReached": len(matches) > MAX_RESULTS,
        "firstCorrectRank": rank,
        "correctInTop3": rank is not None and rank <= 3,
        "correctInTop10": rank is not None and rank <= 10,
        "top10": top,
        "zeroResults": not matches,
        "onlyFormalTermFindsExpected": rank is None and formal_alias_rank is not None,
        "needsSynonym": (rank is None or rank > 10) and formal_alias_rank is not None,
        "aliasRanks": alias_ranks,
        "summaryHasLargePdfSpacing": any(item["hasLargePdfSpacing"] for item in top),
        "genericTitleInTop10": any(item["genericTitle"] for item in top),
        "outcome": outcome,
    }


def markdown(report: dict) -> str:
    summary = report["summary"]
    rows = [
        "# 搜尋品質 2.0 基準稽核",
        "",
        "## 稽核方法",
        "",
        "本稽核直接讀取目前 `site/assets/data/search-index.json` 與實務查詢案例，逐筆模擬 `search.js`：Unicode NFKC、轉小寫、合併空白後，以完整子字串 `includes` 比對；結果維持現有索引順序，最多檢視前50筆與列出前10筆。此報告僅量測，不修改搜尋邏輯、索引或前台。",
        "",
        "## 統計",
        "",
        f"- 案例數：{summary['caseCount']}",
        f"- PASS：{summary['PASS']}；WEAK：{summary['WEAK']}；FAIL：{summary['FAIL']}；AMBIGUOUS：{summary['AMBIGUOUS']}",
        f"- 零結果查詢：{', '.join(summary['zeroResultQueries']) or '無'}",
        f"- 需要同義詞的查詢：{', '.join(summary['needsSynonymQueries']) or '無'}",
        "",
        "## 實務查詢結果",
        "",
        "| 查詢 | 意圖 | 類型 | 結果數 | 首個正確排名 | 分類 |",
        "| --- | --- | --- | ---: | ---: | --- |",
    ]
    for item in report["cases"]:
        rank = item["firstCorrectRank"] if item["firstCorrectRank"] is not None else "—"
        rows.append(f"| {item['query']} | {item['intent']} | {item['expectedType']} | {item['resultCount']} | {rank} | {item['outcome']} |")
    rows.extend([
        "",
        "## 建議同義詞對照表",
        "",
        "| 常用查詢 | 建議同義詞或正式用語 |",
        "| --- | --- |",
        "| 代償 | 代位清償 |",
        "| 保費 | 保證手續費、保證手續費率 |",
        "| 送保 | 申請信用保證、網路送保 |",
        "| 同一關係人 | 同一經濟利害關係人 |",
        "| 展期 | 轉（展）期 |",
        "| 青農 | 青壯年農民、青年農民 |",
        "| 天災貸款 | 農業天然災害低利貸款 |",
        "",
        "## 建議排名權重",
        "",
        "1. 標題完全符合應優先於僅出現在內文的結果。",
        "2. 章節標題與指定格式名稱應優先於目錄、前置頁或一般提及。",
        "3. 查索表、書表與附錄可依查詢意圖提供內容類型加權。",
        "",
        "## 建議內容類型篩選",
        "",
        "建議提供 `chapter`、`appendix`、`form`、`lookup-table`、`front-matter` 篩選；預設隱藏或降權 `front-matter`，避免「前置頁或分隔頁」干擾實務查詢。",
        "",
        "## 建議優先修正順序",
        "",
        "1. 先處理零結果與需同義詞的常用口語查詢。",
        "2. 再處理正確結果落在前10名以外的查詢。",
        "3. 針對前10名出現大量PDF排版空白或籠統標題的紀錄調整摘要與排序。",
        "4. 最後加入內容類型篩選與查索表／書表導向。",
        "",
        "## 觀察清單",
        "",
        f"- 排名最差查詢：{', '.join(summary['worstQueries']) or '無'}",
        f"- 摘要最混亂查詢：{', '.join(summary['messiestSummaryQueries']) or '無'}",
        f"- 標題最不清楚的搜尋紀錄：{', '.join(summary['genericTitleQueries']) or '無'}",
        "",
    ])
    return "\n".join(rows)


def main() -> None:
    records = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    index_urls = {record["url"] for record in records}
    missing_urls = sorted({url for case in cases for url in case["expectedUrls"] if url not in index_urls})
    if missing_urls:
        raise SystemExit(f"expected URLs missing from search index: {missing_urls}")
    results = [case_result(case, records) for case in cases]
    counts = Counter(item["outcome"] for item in results)
    ranked = sorted(results, key=lambda item: float("inf") if item["firstCorrectRank"] is None else item["firstCorrectRank"], reverse=True)
    report = {
        "method": {
            "normalization": "Unicode NFKC, lowercase, whitespace collapse",
            "matching": "full substring includes",
            "indexOrder": "preserved",
            "analysisLimit": MAX_RESULTS,
            "topResultsIncluded": TOP_RESULTS,
        },
        "summary": {
            "caseCount": len(results),
            "PASS": counts["PASS"],
            "WEAK": counts["WEAK"],
            "FAIL": counts["FAIL"],
            "AMBIGUOUS": counts["AMBIGUOUS"],
            "zeroResultQueries": [item["query"] for item in results if item["zeroResults"]],
            "needsSynonymQueries": [item["query"] for item in results if item["needsSynonym"]],
            "worstQueries": [item["query"] for item in ranked[:5]],
            "messiestSummaryQueries": [item["query"] for item in results if item["summaryHasLargePdfSpacing"]],
            "genericTitleQueries": [item["query"] for item in results if item["genericTitleInTop10"]],
            "suggestedSynonymPairs": 7,
        },
        "cases": results,
    }
    JSON_REPORT.parent.mkdir(parents=True, exist_ok=True)
    JSON_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    MARKDOWN_REPORT.write_text(markdown(report), encoding="utf-8")
    print(f"SEARCH QUALITY AUDIT PASSED: {len(results)} cases")
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
