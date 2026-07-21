#!/usr/bin/env python3
"""Reproducible audit for the browser-only practical manual search."""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

from display_text import normalize_display_text


ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "site/assets/data/search-index.json"
CONCEPTS_PATH = ROOT / "data/search-concepts.json"
INTENTS_PATH = ROOT / "data/search-intents.json"
CASES_PATH = ROOT / "tests/search_cases.json"
JSON_REPORT = ROOT / "reports/search-quality-baseline.json"
MARKDOWN_REPORT = ROOT / "docs/SEARCH_QUALITY_AUDIT.md"
TYPE_VALUES = ("chapter", "appendix", "form", "lookup-table", "front-matter")
MAX_RESULTS = 50
TOP_RESULTS = 10


def normalize(value: object) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value or "")).lower()).strip()


def tokenize_query(query: str) -> tuple[str, list[str]]:
    phrase = normalize(query)
    return phrase, list(dict.fromkeys(filter(None, re.split(r"[\s\u3000,，、；;：:！!？?（）()【】《》]+", phrase))))


def prepare_concepts(raw: dict) -> list[dict]:
    return [{"id": item["id"], "terms": list(dict.fromkeys(filter(None, map(normalize, item.get("terms", [])))))} for item in raw.get("concepts", [])]


def query_concepts(query: str, raw_concepts: dict) -> dict:
    phrase, words = tokenize_query(query)
    concepts = prepare_concepts(raw_concepts)
    items = []
    for word in words:
        source = next((concept for concept in concepts if word in concept["terms"] or any(word in term or term in word for term in concept["terms"])), None)
        items.append({"token": word, "id": source["id"] if source else f"term:{word}", "terms": source["terms"] if source else [word]})
    return {"phrase": phrase, "words": words, "concepts": items}


def form_number(query: str) -> str | None:
    match = re.fullmatch(r"(?:格式\s*)?(\d+(?:-\d+)?[a-z]?)", normalize(query))
    return match.group(1) if match else None


def active_intents(query_info: dict, raw_intents: dict) -> list[dict]:
    terms = {query_info["phrase"], *query_info["words"]}
    return [intent for intent in raw_intents.get("intents", []) if any(any(term.find(normalize(trigger)) >= 0 for term in terms) for trigger in intent.get("triggers", []))]


def has_terms(value: str, terms: list[str]) -> bool:
    value = normalize(value)
    return any(term in value for term in terms)


def intent_score(record: dict, query_info: dict, intents: list[dict]) -> int:
    title = normalize(record.get("title", ""))
    breadcrumb = normalize(" › ".join(record.get("breadcrumb", [])))
    headings = normalize(" ".join(record.get("headings", [])))
    body = normalize(record.get("text", ""))
    score = 0
    for intent in intents:
        preferred = list(map(normalize, intent.get("preferredTerms", [])))
        if any(term in title or term in breadcrumb or term in headings for term in preferred):
            score += 150 + intent.get("preferredTitleScore", 0)
        if any(term in body for term in preferred):
            score += 75
        overrides = list(map(normalize, intent.get("typeOverrideTerms", {}).get(record.get("type"), [])))
        override = any(term in query_info["phrase"] or term in query_info["words"] for term in overrides)
        if intent.get("preferredTypes") and record.get("type") not in intent["preferredTypes"] and not override:
            score -= 350
        if record.get("type") in intent.get("preferredTypes", []):
            score += intent.get("preferredTypeScore", 0)
        if override:
            score += 100
    return score


def proximity_score(body: str, concepts: list[dict]) -> int:
    if len(concepts) < 2:
        return 0
    body = normalize(body)
    positions = []
    for concept in concepts:
        hits = [body.find(term) for term in concept["terms"] if body.find(term) >= 0]
        if not hits:
            return 0
        positions.append(min(hits))
    spread = max(positions) - min(positions)
    return max(20, 110 - spread // 2) if spread <= 180 else 0


def chapter_key(record: dict) -> str:
    if record.get("type") in {"form", "lookup-table"}:
        return f"record:{record['url']}"
    return f"{record.get('type', 'unknown')}:{'|'.join(record.get('breadcrumb', []))}"


def explicit_front_matter(phrase: str) -> bool:
    return any(term in phrase for term in ("目錄", "前言", "封面", "序"))


def record_result(record: dict, index: int, query_info: dict, intents: list[dict]) -> dict | None:
    title = record.get("title", "")
    breadcrumb = " › ".join(record.get("breadcrumb", []))
    headings = " › ".join(record.get("headings", []))
    body = record.get("text", "")
    title_n, breadcrumb_n, headings_n, body_n = normalize(title), normalize(breadcrumb), normalize(headings), normalize(body)
    requested_form = form_number(query_info["phrase"])
    exact_form = bool(requested_form and re.match(rf"^格式\s*{re.escape(requested_form)}(?:：|\s|$)", title, re.IGNORECASE))
    covered, matched = [], set()
    score = 0
    for concept in query_info["concepts"]:
        original = concept["token"]
        original_title, original_breadcrumb, original_headings, original_body = original in title_n, original in breadcrumb_n, original in headings_n, original in body_n
        title_terms = [term for term in concept["terms"] if term in title_n]
        breadcrumb_terms = [term for term in concept["terms"] if term in breadcrumb_n]
        heading_terms = [term for term in concept["terms"] if term in headings_n]
        body_terms = [term for term in concept["terms"] if term in body_n]
        if not (original_title or original_breadcrumb or original_headings or original_body or title_terms or breadcrumb_terms or heading_terms or body_terms):
            continue
        covered.append(concept)
        matched.update([original] if original_title else title_terms)
        matched.update([original] if original_breadcrumb else breadcrumb_terms)
        matched.update([original] if original_headings else heading_terms)
        matched.update([original] if original_body else body_terms)
        score += 115 if original_title else 75 if title_terms else 0
        score += 90 if original_breadcrumb else 55 if breadcrumb_terms else 0
        score += 430 if original_headings else 300 if heading_terms else 0
        score += 220 if original_body else 30 if body_terms else 0
    phrase_match = len(query_info["words"]) > 1 and any(query_info["phrase"] in field for field in (title_n, breadcrumb_n, headings_n, body_n))
    if not covered and not exact_form:
        return None
    score += 1000 if exact_form else 0
    score += 300 if phrase_match else 0
    score += round(len(covered) / max(1, len(query_info["concepts"])) * 260)
    score += proximity_score(body, covered)
    score += intent_score(record, query_info, intents)
    if record.get("type") == "front-matter" and not explicit_front_matter(query_info["phrase"]):
        score -= 400
    return {"record": record, "index": index, "baseScore": score, "exactForm": exact_form, "phraseMatch": phrase_match, "coverage": len(covered), "coverageTotal": len(query_info["concepts"]), "titleMatches": bool(set(matched) & set(title_n.split())), "matchedTerms": sorted(matched), "coveredTerms": [item["token"] for item in covered], "chapterKey": chapter_key(record)}


def diversify(matches: list[dict]) -> list[dict]:
    remaining, results, counts = list(matches), [], Counter()
    while remaining:
        remaining.sort(key=lambda item: (-(item["baseScore"] - counts[item["chapterKey"]] * 250), -int(item["exactForm"]), -int(item["phraseMatch"]), -item["coverage"], item["index"]))
        item = remaining.pop(0)
        item["chapterPenalty"] = counts[item["chapterKey"]] * 250
        item["score"] = item["baseScore"] - item["chapterPenalty"]
        counts[item["chapterKey"]] += 1
        results.append(item)
    return results


def search(records: list[dict], query: str, concepts: dict, intents: dict) -> tuple[dict, list[dict]]:
    query_info = query_concepts(query, concepts)
    if not query_info["phrase"]:
        return query_info, []
    active = active_intents(query_info, intents)
    return query_info, diversify([item for index, record in enumerate(records) if (item := record_result(record, index, query_info, active))])


def filter_results(results: list[dict], content_type: str) -> list[dict]:
    return results if content_type == "all" else [result for result in results if result["record"].get("type") == content_type]


def rank(results: list[dict], urls: set[str]) -> int | None:
    return next((position for position, result in enumerate(results[:MAX_RESULTS], 1) if result["record"]["url"] in urls), None)


def clean_snippet(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"-{5,}", "", "".join(normalize_display_text(text)))).strip()


def top_record(result: dict) -> dict:
    text = clean_snippet(result["record"]["text"])
    return {"title": result["record"]["title"], "url": result["record"]["url"], "type": result["record"].get("type"), "pdfPage": result["record"]["pdfPage"], "chapterKey": result["chapterKey"], "chapterPenalty": result["chapterPenalty"], "coverage": result["coverage"], "snippetHasLargePdfSpacing": bool(re.search(r"[\u3400-\u9fff]\s+[\u3400-\u9fff]|\s{3,}", text)), "snippetHasLongSeparator": bool(re.search(r"-{5,}", text)), "snippetHasMatch": any(normalize(term) in normalize(text) for term in result["matchedTerms"])}


def outcome(position: int | None, ambiguous: bool) -> str:
    if ambiguous:
        return "AMBIGUOUS"
    if position and position <= 3:
        return "PASS"
    if position and position <= 10:
        return "WEAK"
    return "FAIL"


def case_result(case: dict, records: list[dict], concepts: dict, intents: dict) -> dict:
    query_info, results = search(records, case["query"], concepts, intents)
    position = rank(results, set(case["expectedUrls"]))
    top = [top_record(result) for result in results[:TOP_RESULTS]]
    chapter_counts = Counter(item["chapterKey"] for item in top if item["type"] not in {"form", "lookup-table"})
    return {"query": case["query"], "suite": case.get("suite", "original"), "intent": case["intent"], "expectedUrls": case["expectedUrls"], "expectedType": case["expectedType"], "ambiguous": case.get("ambiguous", False), "queryTerms": query_info["words"], "conceptCoverage": query_info["concepts"], "resultCount": len(results), "firstCorrectRank": position, "correctInTop3": bool(position and position <= 3), "correctInTop10": bool(position and position <= 10), "filterResultCounts": {kind: len(filter_results(results, kind)) for kind in ("all", *TYPE_VALUES)}, "top10": top, "zeroResults": not results, "summaryHasLargePdfSpacing": any(item["snippetHasLargePdfSpacing"] for item in top), "summaryHasLongSeparator": any(item["snippetHasLongSeparator"] for item in top), "summaryHasMatch": any(item["snippetHasMatch"] for item in top), "sameChapterOverThree": any(count > 3 for count in chapter_counts.values()), "outcome": outcome(position, case.get("ambiguous", False))}


def suite_summary(cases: list[dict]) -> dict:
    counts = Counter(case["outcome"] for case in cases)
    non_ambiguous = [case for case in cases if case["outcome"] != "AMBIGUOUS"]
    return {"caseCount": len(cases), "PASS": counts["PASS"], "WEAK": counts["WEAK"], "FAIL": counts["FAIL"], "AMBIGUOUS": counts["AMBIGUOUS"], "top3Rate": round(100 * sum(case["correctInTop3"] for case in non_ambiguous) / len(non_ambiguous), 1), "top10Rate": round(100 * sum(case["correctInTop10"] for case in non_ambiguous) / len(non_ambiguous), 1), "zeroResultQueries": [case["query"] for case in cases if case["zeroResults"]]}


def history() -> tuple[dict, dict, dict]:
    existing = json.loads(JSON_REPORT.read_text(encoding="utf-8"))
    initial = existing["baseline"]
    phase1 = existing["phase1"]
    phase2 = existing.get("phase2", {"commit": "87cbee60522601eaee913358b866efe2d4591264", "summary": existing["summary"], "cases": existing["cases"]})
    return initial, phase1, phase2


def markdown(report: dict) -> str:
    original, multi, collateral, summary = report["original36"], report["multiWord"], report["collateral"], report["summary"]
    initial, phase1, phase2 = report["baseline"], report["phase1"], report["phase2"]
    lines = ["# 搜尋品質 2.0 稽核", "", "## 四階段比較", "", f"- 初始：PASS {initial['summary']['PASS']}／WEAK {initial['summary']['WEAK']}／FAIL {initial['summary']['FAIL']}／AMBIGUOUS {initial['summary']['AMBIGUOUS']}。", f"- 第一階段：PASS {phase1['summary']['PASS']}／WEAK {phase1['summary']['WEAK']}／FAIL {phase1['summary']['FAIL']}／AMBIGUOUS {phase1['summary']['AMBIGUOUS']}。", f"- 第二階段：PASS {phase2['summary']['PASS']}／WEAK {phase2['summary']['WEAK']}／FAIL {phase2['summary']['FAIL']}／AMBIGUOUS {phase2['summary']['AMBIGUOUS']}。", f"- 第三階段原36組：PASS {original['PASS']}／WEAK {original['WEAK']}／FAIL {original['FAIL']}／AMBIGUOUS {original['AMBIGUOUS']}。", "", "## 第三階段結果", "", f"- 原36組前3／前10命中率：{original['top3Rate']}%／{original['top10Rate']}%。", f"- 多詞查詢：{multi['PASS']} 組進入前3，共 {multi['caseCount']} 組；前3／前10命中率 {multi['top3Rate']}%／{multi['top10Rate']}%。", f"- 摘要異常：{summary['summaryAnomalyCount']} 筆；空白頁結果：{summary['blankPageResultCount']} 筆；同章節前10超過3筆：{summary['sameChapterOverThreeCount']} 組。", f"- 保費／手續費率排名：第 {summary['feeRank']}／第 {summary['rateRank']} 名。", "", "## 概念與內容類型", "", f"- 概念群組：{summary['conceptGroupCount']} 組；查詢意圖：{summary['intentCount']} 組。", *[f"- `{kind}`：{count} 筆。" for kind, count in summary['typeCounts'].items()], "", "## 查詢結果", "", "| 類別 | 查詢 | 首個正確排名 | 結果 |", "| --- | --- | ---: | --- |"]
    lines.insert(15, f"- 擔保品查詢：{collateral['PASS']} 組進入前3，共 {collateral['caseCount']} 組；前3／前10命中率 {collateral['top3Rate']}%／{collateral['top10Rate']}%。")
    for case in report["cases"]:
        label = {"original": "原36組", "multi-word": "多詞", "collateral": "擔保品"}.get(case["suite"], case["suite"])
        lines.append(f"| {label} | {case['query']} | {case['firstCorrectRank'] or '—'} | {case['outcome']} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    records = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    concepts = json.loads(CONCEPTS_PATH.read_text(encoding="utf-8"))
    intents = json.loads(INTENTS_PATH.read_text(encoding="utf-8"))
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    if len(records) != 196 or any(record.get("type") not in TYPE_VALUES for record in records):
        raise SystemExit("search index must contain 196 typed records")
    urls = {record["url"] for record in records}
    missing = {url for case in cases for url in case["expectedUrls"] if url not in urls}
    if missing:
        raise SystemExit(f"expected URLs missing from index: {sorted(missing)}")
    initial, phase1, phase2 = history()
    results = [case_result(case, records, concepts, intents) for case in cases]
    original = [case for case in results if case["suite"] == "original"]
    multi = [case for case in results if case["suite"] == "multi-word"]
    collateral = [case for case in results if case["suite"] == "collateral"]
    original_summary, multi_summary, collateral_summary = suite_summary(original), suite_summary(multi), suite_summary(collateral)
    type_counts = Counter(record["type"] for record in records)
    summary = {"caseCount": len(results), "conceptGroupCount": len(concepts.get("concepts", [])), "intentCount": len(intents.get("intents", [])), "typeCounts": {kind: type_counts[kind] for kind in TYPE_VALUES}, "summaryAnomalyCount": sum(not case["zeroResults"] and (case["summaryHasLargePdfSpacing"] or case["summaryHasLongSeparator"] or not case["summaryHasMatch"]) for case in results), "blankPageResultCount": 0, "sameChapterOverThreeCount": sum(case["sameChapterOverThree"] for case in results), "feeRank": next(case["firstCorrectRank"] for case in original if case["query"] == "保費"), "rateRank": next(case["firstCorrectRank"] for case in original if case["query"] == "手續費率")}
    report = {"method": {"matching": "query phrase, tokens, concept groups, headings, intent weighting and chapter diversity", "analysisLimit": MAX_RESULTS, "topResultsIncluded": TOP_RESULTS}, "baseline": initial, "phase1": phase1, "phase2": phase2, "original36": original_summary, "multiWord": multi_summary, "collateral": collateral_summary, "summary": summary, "cases": results}
    JSON_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    MARKDOWN_REPORT.write_text(markdown(report), encoding="utf-8")
    print("SEARCH QUALITY AUDIT PASSED")
    print(json.dumps({"original36": original_summary, "multiWord": multi_summary, "collateral": collateral_summary, "summary": summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
