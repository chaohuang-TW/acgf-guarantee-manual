const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const walk = (directory) => fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
  const child = path.join(directory, entry.name);
  return entry.isDirectory() ? walk(child) : entry.name.endsWith(".html") ? [child] : [];
});
const htmlFiles = walk("site");
const anchors = htmlFiles.flatMap((file) => [...fs.readFileSync(file, "utf8").matchAll(/<a\b[^>]*href="[^"]+\.pdf(?:#[^"]*)?"[^>]*>/g)].map((match) => ({ file, tag: match[0] })));
assert.equal(anchors.length > 0, true);
assert.equal(anchors.every(({ tag }) => (tag.includes('target="_blank"') && tag.includes('rel="noopener noreferrer"')) || /\sdownload(?:\s|>)/.test(tag)), true);
assert.equal(anchors.some(({ tag }) => /\sdownload(?:\s|>)/.test(tag)), true);

const home = fs.readFileSync("site/index.html", "utf8");
assert.match(home, /href="versions\/115-04\/index\.html"(?![^>]*target=)/);
assert.match(home, /<details class="advanced-filters">/);
assert.doesNotMatch(home, /<details class="advanced-filters" open/);
assert.match(home, /開啟原始PDF ↗/);
assert.match(home, /下載原始PDF/);

for (const file of [
  "site/versions/115-04/chapters/part-1/guarantee-ratio.html",
  "site/versions/115-04/appendices/appendix-07.html",
  "site/versions/115-04/appendices/appendix-18.html",
  "site/versions/115-04/forms/index.html",
]) {
  const html = fs.readFileSync(file, "utf8");
  assert.match(html, /data-search-scope="[^"]+"/);
  assert.match(html, /data-search-limit="5"/);
  assert.match(html, /class="search-more" hidden/);
  assert.match(html, /class="search-search-all" hidden>改搜尋全手冊/);
  assert.match(html, /<details class="advanced-filters">/);
  assert.doesNotMatch(html, /<details class="advanced-filters" open/);
}

const js = fs.readFileSync("assets/js/search.js", "utf8");
const css = fs.readFileSync("assets/css/site.css", "utf8");
assert.match(js, /filterRecordsByScope/);
assert.match(js, /localScopeLabel}未找到相關內容/);
assert.equal(js.includes('createElement("mark")'), false);
assert.equal(css.includes("#ffe39a"), false);

console.log("SEARCH EXPERIENCE TESTS PASSED");
