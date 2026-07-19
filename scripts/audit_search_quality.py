#!/usr/bin/env python3
"""Create a reproducible audit for the browser's ranked, filterable search."""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

from display_text import normalize_display_text


ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "site" / "assets" / "data" / "search-index.json"
SYNONYMS_PATH = ROOT / "data" / "search-synonyms.json"
CASES_PATH = ROOT / "tests" / "search_cases.json"
JSON_REPORT = ROOT / "reports" / "search-quality-baseline.json"
MARKDOWN_REPORT = ROOT / "docs" / "SEARCH_QUALITY_AUDIT.md"
INITIAL_BASELINE_COMMIT = "3f1747f008e9b07c634e258c912a6705cff4345a"
PHASE1_COMMIT = "07a3972c9e1424155222baee0c2e2404022e2924"
MAX_RESULTS = 50
TOP_RESULTS = 10
TYPE_VALUES = ("chapter", "appendix", "form", "lookup-table", "front-matter")
FEE_TERMS = {"保費", "手續費率", "保證手續費", "保證手續費率"}


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value or "")).lower()).strip()


def normalized_synonyms(raw: dict) -> dict[str, list[str]]:
    return {
        normalize(term): list(dict.fromkeys(filter(None, (normalize(value) for value in values))))
        for term, values in raw.items()
        if isinstance(values, list)
    }


def expand_query(query: str, synonyms: dict[str, list[str]]) -> list[str]:
    original = normalize(query)
    return list(dict.fromkeys(filter(None, [original, *synonyms.get(original, [])])))


def form_number(query: str) -> str | None:
    match = re.fullmatch(r"(?:格式\s*)?(\d+(?:-\d+)?)", normalize(query))
    return match.group(1) if match else None


def field_score(value: str, original: str, synonyms: list[str], exact: int, contains: int, synonym_exact: int, synonym_contains: int) -> int:
    value = normalize(value)
    if value == original:
        return exact
    if original in value:
        return contains
    if any(value == term for term in synonyms):
        return synonym_exact
    if any(term in value for term in synonyms):
        return synonym_contains
    return 0


def fee_rule_score(record: dict, original: str) -> int:
    if original not in FEE_TERMS:
        return 0
    title_and_breadcrumb = normalize(f"{record.get('title', '')} {' › '.join(record.get('breadcrumb', []))}")
    body = normalize(record.get("text", ""))
    score = 0
    if "保證手續費率" in title_and_breadcrumb:
        score += 25
    if "保證手續費" in title_and_breadcrumb:
        score += 15
    if "手續費收取方式及計算公式" in title_and_breadcrumb:
        score += 30
    if "保證手續費率表" in body:
        score += 200
    if "手續費收取方式及計算公式" in body:
        score += 80
    return score


def search(records: list[dict], query: str, synonyms: dict[str, list[str]]) -> tuple[list[str], list[dict]]:
    terms = expand_query(query, synonyms)
    original, alternatives = terms[0], terms[1:]
    requested_form = form_number(original)
    results = []
    for index, record in enumerate(records):
        title = record.get("title", "")
        breadcrumb = " › ".join(record.get("breadcrumb", []))
        body = record.get("text", "")
        fields = (title, breadcrumb, body)
        original_matches = any(original in normalize(value) for value in fields)
        synonym_matches = any(term in normalize(value) for term in alternatives for value in fields)
        exact_form = bool(requested_form and re.match(rf"^格式\s*{re.escape(requested_form)}(?:：|\s|$)", title))
        if not original_matches and not synonym_matches and not exact_form:
            continue
        title_score = field_score(title, original, alternatives, 100, 80, 75, 65)
        breadcrumb_score = field_score(breadcrumb, original, alternatives, 0, 55, 0, 45)
        body_score = field_score(body, original, alternatives, 0, 300, 0, 20)
        results.append({
            "record": record,
            "index": index,
            "score": title_score + breadcrumb_score + body_score + fee_rule_score(record, original) + (120 if exact_form else 0),
            "originalMatches": original_matches,
            "titleMatches": title_score > 0,
        })
    results.sort(key=lambda item: (-item["score"], -int(item["originalMatches"]), -int(item["titleMatches"]), item["index"]))
    return terms, results


def filter_results(results: list[dict], content_type: str) -> list[dict]:
    return results if content_type == "all" else [item for item in results if item["record"].get("type") == content_type]


def rank_of_expected(results: list[dict], expected_urls: set[str]) -> int | None:
    for rank, result in enumerate(results[:MAX_RESULTS], start=1):
        if result["record"]["url"] in expected_urls:
            return rank
    return None


def clean_snippet_text(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"-{5,}", "", "".join(normalize_display_text(text)))).strip()


def has_large_pdf_spacing(text: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]\s+[\u3400-\u9fff]", text) or re.search(r"\s{3,}", text))


def match_positions(text: str, terms: list[str]) -> list[int]:
    normalized = normalize(text)
    return [normalized.find(term) for term in terms if normalized.find(term) >= 0]


def top_record(result: dict, terms: list[str]) -> dict:
    record = result["record"]
    cleaned = clean_snippet_text(record["text"])
    return {
        "title": record["title"],
        "url": record["url"],
        "type": record.get("type"),
        "printedPage": record.get("printedPage", ""),
        "pdfPage": record["pdfPage"],
        "snippetHasLargePdfSpacing": has_large_pdf_spacing(cleaned),
        "snippetHasLongSeparator": bool(re.search(r"-{5,}", cleaned)),
        "snippetMatchPositions": match_positions(cleaned, terms),
        "genericTitle": record["title"] == "前置頁或分隔頁",
    }


def classify(rank: int | None, ambiguous: bool) -> str:
    if ambiguous:
        return "AMBIGUOUS"
    if rank is not None and rank <= 3:
        return "PASS"
    if rank is not None and rank <= 10:
        return "WEAK"
    return "FAIL"


def case_result(case: dict, records: list[dict], synonyms: dict[str, list[str]]) -> dict:
    expected_urls = set(case["expectedUrls"])
    terms, results = search(records, case["query"], synonyms)
    _, direct_results = search(records, case["query"], {})
    rank = rank_of_expected(results, expected_urls)
    direct_rank = rank_of_expected(direct_results, expected_urls)
    filtered = {content_type: filter_results(results, content_type) for content_type in ("all", *TYPE_VALUES)}
    top = [top_record(result, terms) for result in results[:TOP_RESULTS]]
    return {
        "query": case["query"],
        "intent": case["intent"],
        "expectedUrls": case["expectedUrls"],
        "expectedType": case["expectedType"],
        "aliases": case["aliases"],
        "ambiguous": case.get("ambiguous", False),
        "expandedTerms": terms,
        "resultCount": len(results),
        "directResultCount": len(direct_results),
        "firstCorrectRank": rank,
        "directFirstCorrectRank": direct_rank,
        "correctInTop3": rank is not None and rank <= 3,
        "correctInTop10": rank is not None and rank <= 10,
        "filterResultCounts": {content_type: len(items) for content_type, items in filtered.items()},
        "filterPreservesOrder": all(
            [item["index"] for item in items] == [item["index"] for item in results if content_type == "all" or item["record"].get("type") == content_type]
            for content_type, items in filtered.items()
        ),
        "top10": top,
        "zeroResults": not results,
        "directZeroResults": not direct_results,
        "onlyFormalTermFindsExpected": direct_rank is None and rank is not None,
        "needsSynonym": direct_rank is None and rank is not None,
        "aliasRanks": {alias: rank_of_expected(search(records, alias, synonyms)[1], expected_urls) for alias in case["aliases"]},
        "summaryHasLargePdfSpacing": any(item["snippetHasLargePdfSpacing"] for item in top),
        "summaryHasLongSeparator": any(item["snippetHasLongSeparator"] for item in top),
        "summaryHasMatchPosition": any(item["snippetMatchPositions"] for item in top),
        "genericTitleInTop10": any(item["genericTitle"] for item in top),
        "outcome": classify(rank, case.get("ambiguous", False)),
    }


def load_history() -> tuple[dict, dict]:
    existing = json.loads(JSON_REPORT.read_text(encoding="utf-8"))
    initial = existing.get("baseline", {"commit": INITIAL_BASELINE_COMMIT, "summary": existing["summary"], "cases": existing["cases"]})
    phase1 = existing.get("phase1", {"commit": PHASE1_COMMIT, "summary": existing["summary"], "cases": existing["cases"]})
    return initial, phase1


def comparison(previous: dict, results: list[dict]) -> dict:
    prior = {item["query"]: item for item in previous["cases"]}
    improvements = []
    for item in results:
        before_rank = prior.get(item["query"], {}).get("firstCorrectRank")
        after_rank = item["firstCorrectRank"]
        if after_rank is not None:
            improvements.append({"query": item["query"], "beforeRank": before_rank, "afterRank": after_rank, "improvement": (before_rank if before_rank is not None else MAX_RESULTS + 1) - after_rank})
    improvements.sort(key=lambda item: (-item["improvement"], item["afterRank"]))
    return {
        "zeroResultsBefore": previous["summary"].get("zeroResultQueries", []),
        "zeroResultsAfter": [item["query"] for item in results if item["zeroResults"]],
        "mostImprovedQueries": improvements[:5],
        "stillFailingQueries": [item["query"] for item in results if item["outcome"] == "FAIL"],
    }


def markdown(report: dict) -> str:
    summary, compare = report["summary"], report["comparison"]
    initial, phase1 = report["baseline"], report["phase1"]
    lines = [
        "# 搜尋品質 2.0 稽核", "", "## 稽核方法", "",
        "本稽核模擬目前 `search.js`：Unicode NFKC、直接同義詞展開、相關度排序、內容類型篩選及顯示用摘要正規化。索引保留前50筆並列出前10筆；索引原有文字、網址及頁碼未改寫。", "",
        "## 三階段比較", "",
        f"- 初始基準（{initial['commit'][:7]}）：PASS {initial['summary']['PASS']}／WEAK {initial['summary']['WEAK']}／FAIL {initial['summary']['FAIL']}／AMBIGUOUS {initial['summary']['AMBIGUOUS']}。",
        f"- 第一階段（{phase1['commit'][:7]}）：PASS {phase1['summary']['PASS']}／WEAK {phase1['summary']['WEAK']}／FAIL {phase1['summary']['FAIL']}／AMBIGUOUS {phase1['summary']['AMBIGUOUS']}。",
        f"- 第二階段：PASS {summary['PASS']}／WEAK {summary['WEAK']}／FAIL {summary['FAIL']}／AMBIGUOUS {summary['AMBIGUOUS']}。",
        f"- 零結果（第一階段 → 第二階段）：{', '.join(compare['zeroResultsBefore']) or '無'} → {', '.join(compare['zeroResultsAfter']) or '無'}。",
        f"- 非 AMBIGUOUS 前10名命中率：{summary['nonAmbiguousTop10Rate']}%。",
        f"- 摘要異常：{summary['summaryAnomalyCount']} 筆（中文排版空白、長分隔線或無命中位置）。", "",
        "## 內容類型筆數", "",
        *[f"- {label}（`{content_type}`）：{summary['typeCounts'][content_type]} 筆。" for content_type, label in [("chapter", "正文"), ("appendix", "附錄"), ("form", "書表"), ("lookup-table", "查索表"), ("front-matter", "其他")]], "",
        "## 重點排名", "",
        *[f"- {item['query']}：第 {item['firstCorrectRank'] if item['firstCorrectRank'] is not None else '—'} 名。" for item in report['cases'] if item['query'] in {"保費", "手續費率"}], "",
        "## 實務查詢結果", "", "| 查詢 | 擴充詞 | 結果數 | 首個正確排名 | 分類 |", "| --- | --- | ---: | ---: | --- |",
    ]
    for item in report["cases"]:
        lines.append(f"| {item['query']} | {'、'.join(item['expandedTerms'])} | {item['resultCount']} | {item['firstCorrectRank'] if item['firstCorrectRank'] is not None else '—'} | {item['outcome']} |")
    lines.extend(["", "## 排名改善最多", "", *[f"- {item['query']}：{item['beforeRank'] if item['beforeRank'] is not None else '前50名外'} → {item['afterRank']}。" for item in compare['mostImprovedQueries']], "", "## 仍失敗的查詢", "", f"{', '.join(compare['stillFailingQueries']) or '無'}。", ""])
    return "\n".join(lines)


def main() -> None:
    records = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    synonyms = normalized_synonyms(json.loads(SYNONYMS_PATH.read_text(encoding="utf-8")))
    if len(records) != 196:
        raise SystemExit(f"expected 196 search records, got {len(records)}")
    if any(record.get("type") not in TYPE_VALUES for record in records):
        raise SystemExit("search index contains a missing or invalid content type")
    index_urls = {record["url"] for record in records}
    missing_urls = sorted({url for case in cases for url in case["expectedUrls"] if url not in index_urls})
    if missing_urls:
        raise SystemExit(f"expected URLs missing from search index: {missing_urls}")
    initial, phase1 = load_history()
    results = [case_result(case, records, synonyms) for case in cases]
    counts = Counter(item["outcome"] for item in results)
    non_ambiguous = [item for item in results if item["outcome"] != "AMBIGUOUS"]
    type_counts = Counter(record["type"] for record in records)
    summary_anomalies = sum(
        not item["zeroResults"] and (item["summaryHasLargePdfSpacing"] or item["summaryHasLongSeparator"] or not item["summaryHasMatchPosition"])
        for item in results
    )
    summary = {
        "caseCount": len(results), "PASS": counts["PASS"], "WEAK": counts["WEAK"], "FAIL": counts["FAIL"], "AMBIGUOUS": counts["AMBIGUOUS"],
        "zeroResultQueries": [item["query"] for item in results if item["zeroResults"]],
        "nonAmbiguousTop10Rate": round(100 * sum(item["correctInTop10"] for item in non_ambiguous) / len(non_ambiguous), 1),
        "synonymGroups": len(synonyms), "typeCounts": {content_type: type_counts[content_type] for content_type in TYPE_VALUES},
        "summaryAnomalyCount": summary_anomalies,
    }
    report = {"method": {"normalization": "Unicode NFKC, lowercase, whitespace collapse and display-text cleanup", "matching": "direct synonym expansion plus ranked title, breadcrumb and text matching", "analysisLimit": MAX_RESULTS, "topResultsIncluded": TOP_RESULTS}, "baseline": initial, "phase1": phase1, "summary": summary, "comparison": comparison(phase1, results), "cases": results}
    JSON_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    MARKDOWN_REPORT.write_text(markdown(report), encoding="utf-8")
    print(f"SEARCH QUALITY AUDIT PASSED: {len(results)} cases")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
