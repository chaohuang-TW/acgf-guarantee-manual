#!/usr/bin/env python3
"""Create a reproducible audit for the browser's synonym-aware search."""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "site" / "assets" / "data" / "search-index.json"
SYNONYMS_PATH = ROOT / "data" / "search-synonyms.json"
CASES_PATH = ROOT / "tests" / "search_cases.json"
JSON_REPORT = ROOT / "reports" / "search-quality-baseline.json"
MARKDOWN_REPORT = ROOT / "docs" / "SEARCH_QUALITY_AUDIT.md"
BASELINE_COMMIT = "3f1747f008e9b07c634e258c912a6705cff4345a"
MAX_RESULTS = 50
TOP_RESULTS = 10


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value).lower()).strip()


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
        body_score = field_score(body, original, alternatives, 0, 30, 0, 20)
        matched_term = original if original_matches else next(term for term in alternatives if any(term in normalize(value) for value in fields))
        results.append({
            "record": record,
            "index": index,
            "score": title_score + breadcrumb_score + body_score + (120 if exact_form else 0),
            "originalMatches": original_matches,
            "titleMatches": title_score > 0,
            "matchedTerm": matched_term,
        })
    results.sort(key=lambda item: (-item["score"], -int(item["originalMatches"]), -int(item["titleMatches"]), item["index"]))
    return terms, results


def rank_of_expected(results: list[dict], expected_urls: set[str]) -> int | None:
    for rank, result in enumerate(results[:MAX_RESULTS], start=1):
        if result["record"]["url"] in expected_urls:
            return rank
    return None


def has_large_pdf_spacing(text: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]\s+[\u3400-\u9fff]", text) or re.search(r"\s{3,}", text))


def top_record(result: dict) -> dict:
    record = result["record"]
    return {
        "title": record["title"],
        "url": record["url"],
        "printedPage": record.get("printedPage", ""),
        "pdfPage": record["pdfPage"],
        "hasLargePdfSpacing": has_large_pdf_spacing(record["text"]),
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
    alias_ranks = {alias: rank_of_expected(search(records, alias, synonyms)[1], expected_urls) for alias in case["aliases"]}
    top = [top_record(result) for result in results[:TOP_RESULTS]]
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
        "top10": top,
        "zeroResults": not results,
        "directZeroResults": not direct_results,
        "onlyFormalTermFindsExpected": direct_rank is None and rank is not None,
        "needsSynonym": direct_rank is None and rank is not None,
        "aliasRanks": alias_ranks,
        "summaryHasLargePdfSpacing": any(item["hasLargePdfSpacing"] for item in top),
        "genericTitleInTop10": any(item["genericTitle"] for item in top),
        "outcome": classify(rank, case.get("ambiguous", False)),
    }


def load_baseline() -> dict:
    existing = json.loads(JSON_REPORT.read_text(encoding="utf-8"))
    return existing.get("baseline", {"commit": BASELINE_COMMIT, "summary": existing["summary"], "cases": existing["cases"]})


def comparison(baseline: dict, results: list[dict]) -> dict:
    prior = {item["query"]: item for item in baseline["cases"]}
    improvements = []
    for item in results:
        before = prior.get(item["query"], {})
        before_rank = before.get("firstCorrectRank")
        after_rank = item["firstCorrectRank"]
        if after_rank is not None:
            delta = (before_rank if before_rank is not None else MAX_RESULTS + 1) - after_rank
            improvements.append({"query": item["query"], "beforeRank": before_rank, "afterRank": after_rank, "improvement": delta})
    improvements.sort(key=lambda item: (-item["improvement"], item["afterRank"]))
    before_zero = baseline["summary"].get("zeroResultQueries", [])
    return {
        "baselineSummary": baseline["summary"],
        "zeroResultsBefore": before_zero,
        "zeroResultsAfter": [item["query"] for item in results if item["zeroResults"]],
        "mostImprovedQueries": improvements[:5],
        "stillFailingQueries": [item["query"] for item in results if item["outcome"] == "FAIL"],
    }


def markdown(report: dict) -> str:
    summary = report["summary"]
    compare = report["comparison"]
    rows = [
        "# 搜尋品質 2.0 稽核",
        "",
        "## 稽核方法",
        "",
        "本稽核模擬目前 `search.js`：Unicode NFKC、轉小寫、合併空白、直接同義詞展開，以及標題／麵包屑／正文與格式編號的相關度排序。結果保留前50筆並列出前10筆；不修改搜尋索引內容。",
        "",
        "## 改版前後比較",
        "",
        f"- 改版前基準（{report['baseline']['commit'][:7]}）：PASS {compare['baselineSummary']['PASS']}／WEAK {compare['baselineSummary']['WEAK']}／FAIL {compare['baselineSummary']['FAIL']}／AMBIGUOUS {compare['baselineSummary']['AMBIGUOUS']}。",
        f"- 改版後：PASS {summary['PASS']}／WEAK {summary['WEAK']}／FAIL {summary['FAIL']}／AMBIGUOUS {summary['AMBIGUOUS']}。",
        f"- 零結果前：{', '.join(compare['zeroResultsBefore']) or '無'}。",
        f"- 零結果後：{', '.join(compare['zeroResultsAfter']) or '無'}。",
        f"- 非 AMBIGUOUS 前10名命中率：{summary['nonAmbiguousTop10Rate']}%。",
        "",
        "## 實務查詢結果",
        "",
        "| 查詢 | 擴充詞 | 結果數 | 首個正確排名 | 分類 |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for item in report["cases"]:
        rank = item["firstCorrectRank"] if item["firstCorrectRank"] is not None else "—"
        rows.append(f"| {item['query']} | {'、'.join(item['expandedTerms'])} | {item['resultCount']} | {rank} | {item['outcome']} |")
    rows.extend([
        "",
        "## 排名改善最多",
        "",
        *[f"- {item['query']}：{item['beforeRank'] if item['beforeRank'] is not None else '前50名外'} → {item['afterRank']}。" for item in compare["mostImprovedQueries"]],
        "",
        "## 仍失敗的查詢",
        "",
        f"{', '.join(compare['stillFailingQueries']) or '無'}。",
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
        "1. 標題完全／包含原查詢：100／80；標題完全／包含同義詞：75／65。",
        "2. 麵包屑包含原查詢／同義詞：55／45；正文包含原查詢／同義詞：30／20。",
        "3. 明確格式編號精確命中額外加120；其後以原查詢、標題命中與原索引順序穩定排序。",
        "",
        "## 建議內容類型篩選與優先修正順序",
        "",
        "建議後續提供 `chapter`、`appendix`、`form`、`lookup-table`、`front-matter` 篩選，並先處理仍失敗的口語查詢、再處理前置頁干擾與內容類型導向。",
        "",
    ])
    return "\n".join(rows)


def main() -> None:
    records = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    synonyms = normalized_synonyms(json.loads(SYNONYMS_PATH.read_text(encoding="utf-8")))
    index_urls = {record["url"] for record in records}
    missing_urls = sorted({url for case in cases for url in case["expectedUrls"] if url not in index_urls})
    if missing_urls:
        raise SystemExit(f"expected URLs missing from search index: {missing_urls}")
    baseline = load_baseline()
    results = [case_result(case, records, synonyms) for case in cases]
    counts = Counter(item["outcome"] for item in results)
    non_ambiguous = [item for item in results if item["outcome"] != "AMBIGUOUS"]
    top10_rate = round(100 * sum(item["correctInTop10"] for item in non_ambiguous) / len(non_ambiguous), 1)
    summary = {
        "caseCount": len(results),
        "PASS": counts["PASS"], "WEAK": counts["WEAK"], "FAIL": counts["FAIL"], "AMBIGUOUS": counts["AMBIGUOUS"],
        "zeroResultQueries": [item["query"] for item in results if item["zeroResults"]],
        "needsSynonymQueries": [item["query"] for item in results if item["needsSynonym"]],
        "nonAmbiguousTop10Rate": top10_rate,
        "synonymGroups": len(synonyms),
        "suggestedSynonymPairs": 7,
    }
    report = {"method": {"normalization": "Unicode NFKC, lowercase, whitespace collapse", "matching": "direct synonym expansion plus title, breadcrumb, and text matching", "analysisLimit": MAX_RESULTS, "topResultsIncluded": TOP_RESULTS}, "baseline": baseline, "summary": summary, "comparison": comparison(baseline, results), "cases": results}
    JSON_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    MARKDOWN_REPORT.write_text(markdown(report), encoding="utf-8")
    print(f"SEARCH QUALITY AUDIT PASSED: {len(results)} cases")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
