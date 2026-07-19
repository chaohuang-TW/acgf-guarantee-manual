const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("assets/js/search.js", "utf8");
const context = { console };
context.globalThis = context;
vm.runInNewContext(source, context, { filename: "search.js" });
const { cleanSnippetText, expandQuery, filterMatches, highlightParts, searchRecords, zeroResultMessage } = context.ManualSearch;
const synonyms = JSON.parse(fs.readFileSync("data/search-synonyms.json", "utf8"));
const index = JSON.parse(fs.readFileSync("site/assets/data/search-index.json", "utf8"));

assert.deepEqual([...expandQuery("代償", { "代償": ["代位清償"] })], ["代償", "代位清償"]);
assert.deepEqual([...expandQuery("未知", synonyms)], ["未知"]);

const clean = cleanSnippetText("保 證 手 續 費\n收取方式及計算公式\n--------------------\n後續說明");
assert.equal(clean.includes("保證手續費收取方式及計算公式"), true);
assert.equal(/[\u3400-\u9fff]\s+[\u3400-\u9fff]/.test(clean), false);
assert.equal(clean.includes("-----"), false);

const originalParts = highlightParts("保費與保證手續費", ["保費", "保證手續費"]);
assert.equal(originalParts.some((part) => part.marked && part.text === "保費"), true);
const synonymParts = highlightParts("代位清償作業", ["代償", "代位清償"]);
assert.equal(synonymParts.some((part) => part.marked && part.text === "代位清償"), true);
const safeParts = highlightParts("<script>alert(1)</script>", ["script"]);
assert.equal(safeParts.map((part) => part.text).join(""), "<script>alert(1)</script>");
assert.equal(source.includes("innerHTML"), false);

const ranked = searchRecords(index, "保費", synonyms).matches;
const feeExpectedRank = ranked.findIndex(({ record }) => record.url === "versions/115-04/pages/page-022.html") + 1;
assert.equal(feeExpectedRank > 0 && feeExpectedRank <= 3, true);
const rateRanked = searchRecords(index, "手續費率", synonyms).matches;
const rateExpectedRank = rateRanked.findIndex(({ record }) => record.url === "versions/115-04/pages/page-028.html") + 1;
assert.equal(rateExpectedRank > 0 && rateExpectedRank <= 3, true);
assert.equal(searchRecords(index, "格式25", synonyms).matches[0].record.url, "versions/115-04/pages/page-177.html");

assert.equal(index.length, 196);
for (const type of ["chapter", "appendix", "form", "lookup-table", "front-matter"]) assert.equal(index.some((record) => record.type === type), true);
assert.equal(index.find((record) => record.pdfPage === 28).type, "chapter");
assert.equal(index.find((record) => record.pdfPage === 122).type, "lookup-table");
assert.equal(index.find((record) => record.pdfPage === 177).type, "form");
assert.equal(index.find((record) => record.pdfPage === 5).type, "front-matter");
for (const type of ["all", "chapter", "appendix", "form", "lookup-table"]) {
  const filtered = filterMatches(ranked, type);
  assert.equal(filtered.every(({ record }) => type === "all" || record.type === type), true);
  assert.deepEqual(filtered.map(({ record }) => record.url), ranked.filter(({ record }) => type === "all" || record.type === type).map(({ record }) => record.url));
}
assert.equal(searchRecords(index, "不存在的查詢", null).matches.length, 0);
assert.equal(zeroResultMessage("原保地貸款").includes("原住民族地區相關貸款請另查最新正式規定"), true);

console.log("SEARCH LOGIC TESTS PASSED");
