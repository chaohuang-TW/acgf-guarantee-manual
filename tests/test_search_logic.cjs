const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("assets/js/search.js", "utf8");
const css = fs.readFileSync("assets/css/site.css", "utf8");
const context = { console, URL };
context.globalThis = context;
vm.runInNewContext(source, context, { filename: "search.js" });
const { bodyMatchOffsets, buildContextText, cleanSnippetText, continuationNeeded, deduplicateAdjacentResults, filterMatches, filterRecordsByScope, findLogicalPassage, queryConcepts, resultTarget, searchRecords, selectReadingSegment, selectReadingSegments, snippet, tokenizeQuery, zeroResultMessage, buildRecoveryVocabulary, levenshteinDistance, evaluateTypoToken, buildZeroResultRecovery } = context.ManualSearch;
const concepts = JSON.parse(fs.readFileSync("data/search-concepts.json", "utf8"));
const intents = JSON.parse(fs.readFileSync("data/search-intents.json", "utf8"));
const index = JSON.parse(fs.readFileSync("site/assets/data/search-index.json", "utf8"));

const rank = (query, url) => searchRecords(index, query, concepts, intents).matches.findIndex(({ record }) => record.url === url) + 1;

assert.deepEqual(JSON.parse(JSON.stringify(tokenizeQuery("青農　保證成數、貸款"))), {
  phrase: "青農 保證成數、貸款",
  words: ["青農", "保證成數", "貸款"],
});
const feeConcepts = queryConcepts("保費 費率", concepts);
assert.equal(feeConcepts.concepts.every((concept) => concept.id === "guarantee-fee"), true);
assert.equal(queryConcepts("未知用語", concepts).concepts[0].terms[0], "未知用語");

const clean = cleanSnippetText("保 證 手 續 費\n收取方式及計算公式\n--------------------\n後續說明");
assert.equal(clean.includes("保證手續費收取方式及計算公式"), true);
assert.equal(/[\u3400-\u9fff]\s+[\u3400-\u9fff]/.test(clean), false);
assert.equal(clean.includes("-----"), false);

const fee = searchRecords(index, "保費", concepts, intents).matches;
assert.equal(rank("保費", "versions/115-04/pages/page-022.html") <= 3, true);
assert.equal(rank("手續費率", "versions/115-04/pages/page-028.html") <= 3, true);
assert.equal(searchRecords(index, "格式25", concepts, intents).matches[0].record.url, "versions/115-04/pages/page-177.html");
assert.deepEqual(index.find((record) => record.pdfPage === 21).headings, ["二、擔保品及保證人"]);
assert.equal(searchRecords(index, "擔保品", concepts, intents).matches[0].record.url, "versions/115-04/pages/page-021.html");
assert.equal(rank("抵押品", "versions/115-04/pages/page-021.html") <= 3, true);
assert.equal(searchRecords(index, "擔保品及保證人", concepts, intents).matches[0].record.url, "versions/115-04/pages/page-021.html");
assert.equal(rank("保證人", "versions/115-04/pages/page-021.html") <= 3, true);
for (const query of ["格式25A", "格式 25A", "擔保品處分情形表", "擔保品及借、保戶財產處分情形表", "擔保品表格"]) {
  assert.equal(searchRecords(index, query, concepts, intents).matches[0].record.url, "versions/115-04/pages/page-178.html", query);
}
assert.notEqual(searchRecords(index, "擔保品", concepts, intents).matches[0].record.url, "versions/115-04/pages/page-178.html");
assert.equal(searchRecords(index, "青農 保證成數", concepts, intents).matches[0].coverage, 2);
assert.equal(searchRecords(index, "手續費 計算", concepts, intents).matches[0].record.url, "versions/115-04/pages/page-122.html");
assert.equal(searchRecords(index, "代償 應備文件", concepts, intents).matches[0].record.url, "versions/115-04/pages/page-180.html");

assert.equal(index.length, 196);
const sharedPage46 = index.find((record) => record.pdfPage === 46);
assert.deepEqual(sharedPage46.readingSegments.map((segment) => segment.id), [
  "subrogation-requirements",
  "subrogation-scope",
  "subrogation-documents",
]);
const interestResult = searchRecords(index, "代償利息", concepts, intents).matches.find(({ record }) => record.pdfPage === 46);
assert.equal(interestResult.segment.id, "subrogation-scope");
assert.equal(resultTarget(interestResult.record, null, interestResult.segment), "versions/115-04/chapters/part-3/subrogation-scope.html#pdf-page-46");
assert.equal(interestResult.segment.text.includes("無執行實益"), false);
assert.equal(interestResult.segment.text.includes("格式 25Ａ"), false);
assert.equal(snippet(interestResult.segment.text, interestResult.matchedTerms).includes("代償利息"), true);
assert.equal(searchRecords(index, "法定訴訟費用", concepts, intents).matches.find(({ record }) => record.pdfPage === 46).segment.id, "subrogation-scope");
const documentsResult = searchRecords(index, "代位清償應檢送文件", concepts, intents).matches.find(({ record }) => record.pdfPage === 46);
assert.equal(documentsResult.segment.id, "subrogation-documents");
assert.equal(resultTarget(documentsResult.record, null, documentsResult.segment), "versions/115-04/chapters/part-3/subrogation-documents.html#pdf-page-46");
assert.equal(selectReadingSegment(sharedPage46, queryConcepts("無執行實益", concepts)).id, "subrogation-requirements");
const format25aResults = searchRecords(index, "格式25A", concepts, intents).matches;
assert.equal(format25aResults[0].record.url, "versions/115-04/pages/page-178.html");
assert.equal(format25aResults.find(({ record }) => record.pdfPage === 46).segment.id, "subrogation-documents");
const sharedPage32 = index.find((record) => record.pdfPage === 32);
assert.equal(selectReadingSegment(sharedPage32, queryConcepts("內容變更事項", concepts)).id, "guarantee-changes");
assert.equal(selectReadingSegment(sharedPage32, queryConcepts("終止保證", concepts)).id, "guarantee-termination");
assert.equal(searchRecords(index, "內容變更事項", concepts, intents).matches[0].segment.id, "guarantee-changes");
assert.equal(searchRecords(index, "終止保證", concepts, intents).matches[0].segment.id, "guarantee-termination");
const sharedPage43 = index.find((record) => record.pdfPage === 43);
assert.equal(selectReadingSegment(sharedPage43, queryConcepts("其他有合理理由", concepts)).id, "overdue-guarantee");
assert.equal(selectReadingSegment(sharedPage43, queryConcepts("第二年起保證手續費", concepts)).id, "release-liability");

const sharedFixture = {
  type: "chapter",
  pdfPage: 999,
  printedPage: "測試",
  title: "測試共享頁",
  breadcrumb: ["測試"],
  text: "第一段共同詞規定。第二段共同詞規定。",
  url: "versions/test/page.html",
  readingUrl: "versions/test/first.html",
  scope: "chapter:test/first",
  readingSegments: [
    { id: "first", title: "第一段", breadcrumb: ["測試", "第一段"], scope: "chapter:test/first", readingUrl: "versions/test/first.html", startOffset: 0, endOffset: 9, text: "第一段共同詞規定。" },
    { id: "second", title: "第二段", breadcrumb: ["測試", "第二段"], scope: "chapter:test/second", readingUrl: "versions/test/second.html", startOffset: 9, endOffset: 18, text: "第二段共同詞規定。" },
  ],
};
assert.equal(selectReadingSegment(sharedFixture, queryConcepts("完全未命中", concepts)), null);
assert.equal(selectReadingSegments(sharedFixture, queryConcepts("完全未命中", concepts)).length, 0);
const sharedFixtureResults = searchRecords([sharedFixture], "共同詞", concepts, intents).matches;
assert.deepEqual(JSON.parse(JSON.stringify(sharedFixtureResults.map(({ segment }) => segment.id))), ["first", "second"]);
assert.equal(deduplicateAdjacentResults(sharedFixtureResults).length, 2);
assert.equal(bodyMatchOffsets(sharedFixture.readingSegments[1].text, queryConcepts("共同詞", concepts))[0].rawOffset > 0, true);
const continuationRecord = index.find((record) => record.pdfPage === 22);
const subrogation = index.find((record) => record.pdfPage === 44);
assert.equal(continuationRecord.contextBefore.includes("同意者"), false);
assert.equal(continuationRecord.contextStartPdfPage, 21);
assert.equal(buildContextText(continuationRecord).text.includes("同意者，不在此限"), true);
assert.equal(continuationNeeded(continuationRecord.text), true);
assert.equal(findLogicalPassage(continuationRecord, ["擔保品"], true).startPdfPage, 21);
const onlyCurrentPassage = findLogicalPassage(subrogation, ["代位清償"], true);
assert.equal(onlyCurrentPassage.startPdfPage, 44);
assert.equal(onlyCurrentPassage.endPdfPage, 44);
const crossPageFixture = {
  type: "chapter", pdfPage: 44, printedPage: "36", contextStartPdfPage: 43, contextStartPrintedPage: "35", contextEndPdfPage: 45, contextEndPrintedPage: "37",
  contextBefore: "前頁無關文字。", text: "本頁條文說明代位清償的必要條件與程序，內容仍需延續至下一頁，並說明受託機構應先完成必要查核，且須保存完整授信與債權資料", contextAfter: "，並由受託機構依規定檢具文件後提出申請，始得依本手冊程序辦理；相關佐證應妥善留存並供後續核對。下一條獨立規定。"
};
const crossPagePassage = findLogicalPassage(crossPageFixture, ["代位清償"], true);
assert.equal(crossPagePassage.startPdfPage, 44);
assert.equal(crossPagePassage.endPdfPage, 45);
assert.equal(crossPagePassage.anchorPdfPage, 44);
assert.equal(findLogicalPassage(index.find((record) => record.pdfPage === 178), ["擔保品"], true), null);
assert.equal(subrogation.readingUrl, "versions/115-04/chapters/part-3/subrogation-requirements.html");
assert.equal(resultTarget(subrogation, { anchorPdfPage: 44 }), "versions/115-04/chapters/part-3/subrogation-requirements.html#pdf-page-44");
assert.equal(resultTarget(index.find((record) => record.pdfPage === 21), { anchorPdfPage: 21 }), "versions/115-04/chapters/part-1/guarantee-application.html#pdf-page-21");
assert.equal(resultTarget(index.find((record) => record.pdfPage === 178), { anchorPdfPage: 178 }), "versions/115-04/forms/form-25a.html#pdf-page-178");
assert.equal(resultTarget(index.find((record) => record.pdfPage === 60), { anchorPdfPage: 60 }), "versions/115-04/appendices/appendix-02.html#pdf-page-60");
assert.equal(resultTarget(index.find((record) => record.pdfPage === 5), { anchorPdfPage: 5 }), "versions/115-04/pages/page-005.html#pdf-page-5");
assert.equal(index.every((record) => record.readingUrl), true);
const duplicateFixtures = [
  { record: { type: "chapter", scope: "chapter:test", pdfPage: 10, contextStartPdfPage: 9, contextEndPdfPage: 11, text: "第一條 擔保品應依規定辦理，並應確認價值、權利設定與保證人責任，受託機構應保存相關文件及紀錄。", contextAfter: "第一條 擔保品應依規定辦理，並應確認價值、權利設定與保證人責任，受託機構應保存相關文件及紀錄。" }, matchedTerms: ["擔保品"], coveredTerms: ["擔保品"], bodyMatches: true },
  { record: { type: "chapter", scope: "chapter:other", pdfPage: 50, text: "其他章節的獨立規定，內容足以作為不同結果保留。" }, matchedTerms: ["其他"], coveredTerms: ["其他"], bodyMatches: true },
  { record: { type: "chapter", scope: "chapter:test", pdfPage: 11, contextStartPdfPage: 10, contextEndPdfPage: 12, text: "第一條 擔保品應依規定辦理，並應確認價值、權利設定與保證人責任，受託機構應保存相關文件及紀錄。", contextAfter: "第一條 擔保品應依規定辦理，並應確認價值、權利設定與保證人責任，受託機構應保存相關文件及紀錄。" }, matchedTerms: ["擔保品"], coveredTerms: ["擔保品"], bodyMatches: true }
];
assert.equal(deduplicateAdjacentResults(duplicateFixtures).length, 2);
for (const type of ["chapter", "appendix", "form", "lookup-table", "front-matter"]) assert.equal(index.some((record) => record.type === type), true);
assert.equal(index.find((record) => record.pdfPage === 28).type, "chapter");
assert.equal(index.find((record) => record.pdfPage === 122).type, "lookup-table");
assert.equal(index.find((record) => record.pdfPage === 177).type, "form");
assert.equal(index.find((record) => record.pdfPage === 5).type, "front-matter");
assert.equal(index.every((record) => record.scope), true);
const chapterScope = filterRecordsByScope(index, "chapter:part-1/guarantee-ratio");
assert.equal(chapterScope.length > 0, true);
assert.equal(chapterScope.every((record) => record.scope === "chapter:part-1/guarantee-ratio"), true);
const partScope = filterRecordsByScope(index, "chapter:part-1/");
assert.equal(partScope.length > chapterScope.length, true);
assert.equal(partScope.every((record) => record.scope.startsWith("chapter:part-1/")), true);
assert.equal(searchRecords(chapterScope, "保證成數", concepts, intents).matches.every(({ record }) => record.scope === "chapter:part-1/guarantee-ratio"), true);
for (const type of ["all", "chapter", "appendix", "form", "lookup-table"]) {
  const filtered = filterMatches(fee, type);
  assert.equal(filtered.every(({ record }) => type === "all" || record.type === type), true);
  assert.deepEqual(filtered.map(({ record }) => record.url), fee.filter(({ record }) => type === "all" || record.type === type).map(({ record }) => record.url));
}
assert.notEqual(searchRecords(index, "保費", concepts, intents).matches[0].record.type, "front-matter");
assert.equal(index.every((record) => String(record.text || "").trim() || record.type !== "front-matter"), true);
assert.equal(searchRecords(index, "不存在的查詢", concepts, intents).matches.length, 0);
assert.equal(zeroResultMessage("原保地貸款").includes("原住民族地區相關貸款請另查最新正式規定"), true);

for (const query of ["保費", "手續費率", "青農 保證成數", "代償 應備文件", "展期 保證責任"]) {
  const counts = new Map();
  for (const result of searchRecords(index, query, concepts, intents).matches.slice(0, 10)) {
    if (["form", "lookup-table"].includes(result.record.type)) continue;
    counts.set(result.chapterKey, (counts.get(result.chapterKey) || 0) + 1);
  }
  assert.equal([...counts.values()].every((count) => count <= 3), true, `${query} should be diversified by chapter`);
}


assert.equal(source.includes('createElement("mark")'), true);
assert.equal(source.includes('mark.textContent'), true);
assert.equal(source.includes("innerHTML"), false);
assert.equal(css.includes(".search-hit"), true);
assert.equal(css.includes(".search-result mark"), false);
assert.equal(css.includes("#ffe39a"), false);

console.log("SEARCH LOGIC TESTS PASSED");

const { readSearchStateFromUrl, searchStateUrl, decorateResultUrlWithSearchState, buildMatchReasons, formatMatchReason } = context.ManualSearch;

assert.deepEqual(JSON.parse(JSON.stringify(readSearchStateFromUrl("https://example.com/"))), { q: "", type: "all" });
assert.deepEqual(JSON.parse(JSON.stringify(readSearchStateFromUrl("https://example.com/?q=test"))), { q: "test", type: "all" });
assert.deepEqual(JSON.parse(JSON.stringify(readSearchStateFromUrl("https://example.com/?q=test&type=form"))), { q: "test", type: "form" });
assert.deepEqual(JSON.parse(JSON.stringify(readSearchStateFromUrl("https://example.com/?q=test&type=invalid"))), { q: "test", type: "all" });

assert.equal(searchStateUrl({ q: "test", type: "all" }, "https://example.com/path"), "https://example.com/path?q=test");
assert.equal(searchStateUrl({ q: "test", type: "form" }, "https://example.com/path"), "https://example.com/path?q=test&type=form");
assert.equal(searchStateUrl({ q: "", type: "all" }, "https://example.com/path"), "https://example.com/path");

assert.equal(decorateResultUrlWithSearchState("https://example.com/page.html", { q: "test", type: "all" }), "https://example.com/page.html?fromSearch=1&q=test");
assert.equal(decorateResultUrlWithSearchState("https://example.com/page.html#hash", { q: "test", type: "form" }), "https://example.com/page.html?fromSearch=1&q=test&type=form#hash");
assert.equal(decorateResultUrlWithSearchState("https://example.com/page.html", { q: "", type: "all" }), "https://example.com/page.html");
assert.equal(decorateResultUrlWithSearchState("https://example.com/page.html", null), "https://example.com/page.html");

// --- Match Transparency Tests ---
// A. 代償利息 → direct-body queryTerm exact matchedTerm exact
const testBodyRes = searchRecords([{ type: "chapter", title: "其他規定", text: "本文包含代償利息內容" }], "代償利息", concepts, intents);
assert.equal(testBodyRes.matches[0].matchReasons.some(r => r.kind === "direct-body" && r.queryTerm === "代償利息" && r.matchedTerm === "代償利息" && r.field === "body"), true, "Should have direct-body reason with exact terms");
assert.equal(formatMatchReason(testBodyRes.matches[0].matchReasons[0]), "正文直接命中「代償利息」");

// B. 真正 heading fixture → direct-heading
const testHeadingRes = searchRecords([{ type: "chapter", title: "代償利息之計算", text: "其他規定內容" }], "代償利息", concepts, intents);
assert.equal(testHeadingRes.matches[0].matchReasons.some(r => r.kind === "direct-heading" && r.queryTerm === "代償利息" && r.matchedTerm === "代償利息" && r.field === "title"), true, "Should have direct-heading reason");
assert.equal(formatMatchReason(testHeadingRes.matches[0].matchReasons[0]), "章節標題命中「代償利息」");

// C. 抵押品 result只有擔保品 → concept-expansion
const testConceptRes = searchRecords([{ type: "chapter", title: "其他", text: "本文包含擔保品" }], "抵押品", concepts, intents);
assert.equal(testConceptRes.matches[0].matchReasons.some(r => r.kind === "concept-expansion" && r.queryTerm === "抵押品" && r.matchedTerm === "擔保品"), true, "Should have concept-expansion reason");
assert.equal(formatMatchReason(testConceptRes.matches[0].matchReasons[0]), "相關詞「抵押品」→「擔保品」");

// D. fixture同時含抵押品及擔保品 → direct wins → 不得 concept-expansion
const testDirectSuppression = searchRecords([{ type: "chapter", title: "其他", text: "本文包含抵押品及擔保品" }], "抵押品", concepts, intents);
assert.equal(testDirectSuppression.matches[0].matchReasons.some(r => r.kind === "direct-body"), true, "Direct body should match");
assert.equal(testDirectSuppression.matches[0].matchReasons.some(r => r.kind === "concept-expansion"), false, "Direct match must suppress concept expansion");

// E. 第4 → 第四 → numeral-expansion
const testNumeralRes = searchRecords([{ type: "chapter", title: "其他", text: "本文包含第四點" }], "第4", concepts, intents);
assert.equal(testNumeralRes.matches[0].matchReasons.some(r => r.kind === "numeral-expansion" && r.queryTerm === "第4" && r.matchedTerm === "第四"), true, "Should have numeral-expansion reason");
assert.equal(formatMatchReason(testNumeralRes.matches[0].matchReasons[0]), "數字展開「第4」→「第四」");

// F. fixture同時含第4及第四 → direct wins
const testNumeralSuppression = searchRecords([{ type: "chapter", title: "其他", text: "本文包含第4點與第四點" }], "第4", concepts, intents);
assert.equal(testNumeralSuppression.matches[0].matchReasons.some(r => r.kind === "direct-body"), true, "Direct match should win for numeral");
assert.equal(testNumeralSuppression.matches[0].matchReasons.some(r => r.kind === "numeral-expansion"), false, "Direct match must suppress numeral expansion");

// G. 格式25A → exact-form queryTerm/display preserved as 格式25A 不得格式25a
const testFormRes = searchRecords([{ type: "form", title: "格式 25A：申請表", text: "" }], "格式25A", concepts, intents);
assert.equal(testFormRes.matches[0].matchReasons.some(r => r.kind === "exact-form" && r.queryTerm === "格式25A"), true, "Should preserve display casing 格式25A");
assert.equal(formatMatchReason(testFormRes.matches[0].matchReasons[0]), "書表編號完全符合「格式25A」");

// H. 青農 保證成數 → 每token最多1 reason
const testMultiToken = searchRecords([{ type: "chapter", title: "青年農民專案", text: "本專案保證成數最高九成" }], "青農 保證成數", concepts, intents);
assert.equal(testMultiToken.matches[0].matchReasons.length <= 2, true, "Multi-token query should have at most 1 reason per token");
const queryTerms = testMultiToken.matches[0].matchReasons.map(r => r.queryTerm);
assert.equal(new Set(queryTerms).size, queryTerms.length, "Each query token must have at most 1 reason");

// I. shared physical page / multiple logical segments → no provenance leakage
const sharedRecord = {
  type: "chapter",
  title: "第二篇 期中管理",
  text: "段落A包含擔保品。段落B包含其他作業說明。",
  readingSegments: [
    { id: "seg-a", title: "第一節 變更處理", text: "段落A包含擔保品。" },
    { id: "seg-b", title: "第二節 逾期處理", text: "段落B包含其他作業說明。" }
  ]
};
const sharedSearch = searchRecords([sharedRecord], "抵押品", concepts, intents);
const segARes = sharedSearch.matches.find(m => m.segment && m.segment.id === "seg-a");
const segBRes = sharedSearch.matches.find(m => m.segment && m.segment.id === "seg-b");

assert.equal(Boolean(segARes), true, "Segment A should be matched via 擔保品");
assert.equal(segARes.matchReasons.some(r => r.kind === "concept-expansion" && r.queryTerm === "抵押品" && r.matchedTerm === "擔保品"), true, "Segment A should have concept-expansion reason");
if (segBRes) {
  assert.equal(segBRes.matchReasons.some(r => r.kind === "concept-expansion" && r.matchedTerm === "擔保品"), false, "Segment B must NOT inherit Segment A's concept-expansion reason");
}

console.log("MATCH TRANSPARENCY TESTS PASSED");

// ==========================================
// Search UX 4.3 Zero-Result Recovery Unit Tests
// ==========================================

const recoveryVocab = buildRecoveryVocabulary(index, concepts, intents);

// Test N: vocabulary normalized dedup
const uniqueTerms = new Set(recoveryVocab.map(v => v.normalizedTerm));
assert.equal(uniqueTerms.size, recoveryVocab.length, "All terms in recovery vocabulary must be distinct normalizedTerms");

// Test O: multi-source provenance merge
const multiSource = recoveryVocab.find(v => v.sources.length > 1);
assert.equal(Boolean(multiSource), true, "Vocabulary should contain multi-source terms");
const claimPaymentVocab = recoveryVocab.find(v => v.normalizedTerm === "代位清償");
assert.equal(Boolean(claimPaymentVocab), true, "代位清償 must be in vocabulary");
assert.equal(claimPaymentVocab.sources.length >= 1, true, "代位清償 must have provenance sources");

// Test A: 代位清嘗 → suggestion 代位清償
const recA = buildZeroResultRecovery({ rawQuery: "代位清嘗", records: index, concepts, intents, vocabulary: recoveryVocab });
assert.equal(recA.suggestions.length, 1, "代位清嘗 should have exactly 1 suggestion");
assert.equal(recA.suggestions[0].query, "代位清償");
assert.equal(recA.suggestions[0].kind, "typo-correction");
assert.equal(recA.suggestions[0].evidence.length, 1);
assert.equal(recA.suggestions[0].evidence[0].originalToken, "代位清嘗");
assert.equal(recA.suggestions[0].evidence[0].correctedToken, "代位清償");
assert.equal(recA.suggestions[0].evidence[0].editDistance, 1);
assert.equal(recA.suggestions[0].evidence[0].normalizedDistance, 0.25);
assert.equal(recA.suggestions[0].evidence[0].distanceGap >= 1, true);

// Test B: 抵壓品 → 抵押品
const recB = buildZeroResultRecovery({ rawQuery: "抵壓品", records: index, concepts, intents, vocabulary: recoveryVocab });
assert.equal(recB.suggestions.length, 1, "抵壓品 should have exactly 1 suggestion");
assert.equal(recB.suggestions[0].query, "抵押品");
assert.equal(recB.suggestions[0].evidence[0].editDistance, 1);

// Test C: 保証成數 → 保證成數
const recC = buildZeroResultRecovery({ rawQuery: "保証成數", records: index, concepts, intents, vocabulary: recoveryVocab });
assert.equal(recC.suggestions.length, 1, "保証成數 should have exactly 1 suggestion");
assert.equal(recC.suggestions[0].query, "保證成數");
assert.equal(recC.suggestions[0].evidence[0].editDistance, 1);

// Test D: 信用保證申情書 → 信用保證申請書
const recD = buildZeroResultRecovery({ rawQuery: "信用保證申情書", records: index, concepts, intents, vocabulary: recoveryVocab });
assert.equal(recD.suggestions.length, 1, "信用保證申情書 should have exactly 1 suggestion");
assert.equal(recD.suggestions[0].query, "信用保證申請書");
assert.equal(recD.suggestions[0].evidence[0].editDistance, 1);

// Test E: 代位清嘗 抵壓品 → 代位清償 抵押品 → evidence length = 2
const recE = buildZeroResultRecovery({ rawQuery: "代位清嘗 抵壓品", records: index, concepts, intents, vocabulary: recoveryVocab });
assert.equal(recE.suggestions.length, 1, "代位清嘗 抵壓品 should have 1 assembled suggestion");
assert.equal(recE.suggestions[0].query, "代位清償 抵押品");
assert.equal(recE.suggestions[0].evidence.length, 2, "Assembled suggestion must have 2 evidence items");

// Test F: 代位清嘗 xyz123 → suggestions = []
const recF = buildZeroResultRecovery({ rawQuery: "代位清嘗 xyz123", records: index, concepts, intents, vocabulary: recoveryVocab });
assert.equal(recF.suggestions.length, 0, "Partial correction must be rejected");

// Test G: 火星 抵壓品 → suggestions = []
const recG = buildZeroResultRecovery({ rawQuery: "火星 抵壓品", records: index, concepts, intents, vocabulary: recoveryVocab });
assert.equal(recG.suggestions.length, 0, "Partial correction must be rejected");

// Test H: 火星貸款 → []
const recH = buildZeroResultRecovery({ rawQuery: "火星貸款", records: index, concepts, intents, vocabulary: recoveryVocab });
assert.equal(recH.suggestions.length, 0, "True no match must not fabricate suggestions");

// Test I: 量子農業保證 → []
const recI = buildZeroResultRecovery({ rawQuery: "量子農業保證", records: index, concepts, intents, vocabulary: recoveryVocab });
assert.equal(recI.suggestions.length, 0, "True no match must not fabricate suggestions");

// Test J: abcdefxyz → []
const recJ = buildZeroResultRecovery({ rawQuery: "abcdefxyz", records: index, concepts, intents, vocabulary: recoveryVocab });
assert.equal(recJ.suggestions.length, 0, "True no match must not fabricate suggestions");

// Test K: 手續費綠 → ambiguity reject
const evalK = evaluateTypoToken({ token: "手續費綠", vocabulary: recoveryVocab, records: index, concepts, intents });
assert.equal(evalK.accepted, false, "手續費綠 must be rejected due to ambiguity (distanceGap < 1)");
assert.equal(evalK.distanceGap, 0, "distanceGap for 手續費綠 should be 0");

// Test L: generic candidate reject
const genericTokens = ["保證", "申請", "文件", "貸款", "通知", "利息"];
for (const gen of genericTokens) {
  const evalGen = evaluateTypoToken({ token: "呆" + gen.slice(1), vocabulary: recoveryVocab, records: index, concepts, intents });
  if (evalGen.correctedToken === gen) {
    assert.equal(evalGen.accepted, false, `Generic token ${gen} must be rejected`);
  }
}

// Test M: original result > 0 → buildZeroResultRecovery guard returns suggestions = []
const recM1 = buildZeroResultRecovery({ rawQuery: "代償", records: index, concepts, intents, vocabulary: recoveryVocab });
assert.equal(recM1.suggestions.length, 0, "Non-zero query 代償 must produce no recovery suggestions");
const recM2 = buildZeroResultRecovery({ rawQuery: "抵押品", records: index, concepts, intents, vocabulary: recoveryVocab });
assert.equal(recM2.suggestions.length, 0, "Non-zero query 抵押品 must produce no recovery suggestions");

// Test P: suggestions <= 3
assert.equal(recA.suggestions.length <= 3, true);
assert.equal(recE.suggestions.length <= 3, true);

// Test Q: structured object (no preformatted HTML strings)
assert.equal(typeof recA, "object");
assert.equal(typeof recA.suggestions[0].query, "string");
assert.equal(recA.suggestions[0].query.includes("<"), false);
assert.equal(recA.suggestions[0].evidence.every(ev => typeof ev.originalToken === "string" && !ev.originalToken.includes("<")), true);

console.log("ZERO RESULT TYPO RECOVERY TESTS PASSED");
