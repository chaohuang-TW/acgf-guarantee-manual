const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const context = { console };
context.globalThis = context;
vm.runInNewContext(fs.readFileSync("assets/js/search.js", "utf8"), context, { filename: "search.js" });
const { expandQuery, searchRecords } = context.ManualSearch;

const synonyms = { "代償": ["代位清償"], "格式25": ["不應遞迴"] };
const records = [
  { title: "一般說明", breadcrumb: ["手冊"], text: "代位清償列於本文。", url: "body", pdfPage: 1 },
  { title: "代償作業", breadcrumb: ["手冊"], text: "說明", url: "original-title", pdfPage: 2 },
  { title: "格式 25：代位清償申請書", breadcrumb: ["書表"], text: "格式", url: "format-25", pdfPage: 3 },
  { title: "同分結果", breadcrumb: ["手冊"], text: "無同義詞查詢", url: "tie-a", pdfPage: 4 },
  { title: "同分結果", breadcrumb: ["手冊"], text: "無同義詞查詢", url: "tie-b", pdfPage: 5 },
];

assert.deepEqual([...expandQuery("代償", synonyms)], ["代償", "代位清償"]);
assert.deepEqual([...expandQuery("未知", synonyms)], ["未知"]);
assert.equal(searchRecords(records, "代償", synonyms).matches[0].record.url, "original-title");
assert.equal(searchRecords(records, "格式25", synonyms).matches[0].record.url, "format-25");
assert.equal(searchRecords(records, "無同義詞查詢", synonyms).matches[0].record.url, "tie-a");
assert.equal(searchRecords(records, "未知", null).matches.length, 0);
console.log("SEARCH LOGIC TESTS PASSED");
