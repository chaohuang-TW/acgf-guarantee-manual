// Full-result contract: no truncation, no ranking tolerance, no URL-only check.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = process.argv[2];
require(path.join(root, 'assets/js/search.js'));
const read = p => JSON.parse(fs.readFileSync(path.join(root, p), 'utf8'));
const records = read('site/assets/data/search-index.json');
const concepts = read('data/search-concepts.json');
const intents = read('data/search-intents.json');
const cases = read('tests/search_cases.json');
const extra = ['不予保證', '格式 ２５ Ａ', '25a', '格式3 - 1', '格式 3 - 1 A', '代位清嘗', '保費', '擔保品', '抵押品', '原保地貸款', '格式25A', '格式 25 a', '信用卡遭強制停用', '最大債權金融機構', '塗銷抵押權之處理方式', '其他有合理理由', '青農 保證成數', '代償 應備文件'];
const queries = [...new Set([...cases.map(x => x.query), ...extra])];
const output = {recordCount: records.length, queries: {}};
for (const query of queries) {
  const result = ManualSearch.searchRecords(records, query, concepts, intents);
  output.queries[query] = {
    queryInfo: result.queryInfo, intents: result.intents,
    matches: result.matches.map(item => ({
      url: item.record.url, title: item.record.title, pdfPage: item.record.pdfPage, printedPage: item.record.printedPage,
      segment: item.segment, index: item.index, exactForm: item.exactForm, phraseMatch: item.phraseMatch,
      score: item.score, baseScore: item.baseScore, chapterPenalty: item.chapterPenalty,
      coverage: item.coverage, coverageTotal: item.coverageTotal,
      matchedTerms: item.matchedTerms, coveredTerms: item.coveredTerms, reasons: item.matchReasons,
      target: ManualSearch.resultTarget(item.record, null, item.segment),
      snippet: ManualSearch.snippet(item.record.text, item.matchedTerms),
    })),
  };
}
output.sha256 = crypto.createHash('sha256').update(JSON.stringify(output.queries)).digest('hex');
process.stdout.write(JSON.stringify(output));
