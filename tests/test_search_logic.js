const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("assets/js/search.js", "utf8");
const css = fs.readFileSync("assets/css/site.css", "utf8");
const context = { console };
context.globalThis = context;
vm.runInNewContext(source, context, { filename: "search.js" });
const { buildContextText, cleanSnippetText, continuationNeeded, deduplicateAdjacentResults, filterMatches, filterRecordsByScope, findLogicalPassage, queryConcepts, resultTarget, searchRecords, tokenizeQuery, zeroResultMessage } = context.ManualSearch;
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

assert.equal(source.includes("createElement(\"mark\")"), false);
assert.equal(source.includes("innerHTML"), false);
assert.equal(css.includes(".search-result mark"), false);
assert.equal(css.includes("#ffe39a"), false);

console.log("SEARCH LOGIC TESTS PASSED");
