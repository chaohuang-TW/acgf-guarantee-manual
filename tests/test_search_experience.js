const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const siteRoot = path.resolve("site");
const toc = JSON.parse(fs.readFileSync("data/toc.json", "utf8"));
const read = (file) => fs.readFileSync(path.join(siteRoot, file), "utf8");
const exists = (file) => fs.existsSync(path.join(siteRoot, file));
const anchors = (html) => [...html.matchAll(/<a\b([^>]*)>([\s\S]*?)<\/a>/g)].map((match) => ({ attrs: match[1], text: match[2].replace(/<[^>]+>/g, "").trim() }));
const href = (attributes) => (attributes.match(/\bhref="([^"]+)"/) || [])[1];

const htmlFiles = [];
const walk = (directory) => fs.readdirSync(directory, { withFileTypes: true }).forEach((entry) => {
  const child = path.join(directory, entry.name);
  if (entry.isDirectory()) walk(child);
  else if (entry.name.endsWith(".html")) htmlFiles.push(child);
});
walk(siteRoot);

const searchPanels = htmlFiles.filter((file) => /<div[^>]*\bdata-search\b/.test(fs.readFileSync(file, "utf8")));
assert.deepEqual(searchPanels.map((file) => path.relative(siteRoot, file)).sort(), ["index.html", "versions/115-04/index.html"]);
assert.match(read("index.html"), /id="manual-search"/);
for (const file of htmlFiles) {
  const html = fs.readFileSync(file, "utf8");
  const searchLink = anchors(html).find((anchor) => anchor.text === "全文搜尋");
  assert.ok(searchLink, `missing full-text search link: ${path.relative(siteRoot, file)}`);
  assert.equal(href(searchLink.attrs).endsWith("#manual-search"), true);
}

const directory = read("versions/115-04/index.html");
const chapterLinks = anchors(directory).filter((anchor) => /^chapters\/part-[1-4]\//.test(href(anchor.attrs) || "") && !href(anchor.attrs).endsWith("/index.html"));
const expectedSections = toc.parts.flatMap((part) => part.sections.map((section) => ({
  title: section.title,
  target: `chapters/${part.id}/${section.id}.html`,
})));
assert.equal(chapterLinks.length, expectedSections.length);
for (const section of expectedSections) {
  const link = chapterLinks.find((item) => href(item.attrs) === section.target && item.text === section.title);
  assert.ok(link, `missing chapter link: ${section.target}`);
  assert.equal(exists(`versions/115-04/${section.target}`), true);
}

for (const [indexFile, items, base] of [
  ["versions/115-04/appendices/index.html", toc.appendices, "appendices"],
  ["versions/115-04/forms/index.html", toc.forms, "forms"],
  ["versions/115-04/forms/special/index.html", toc.specialForms, "forms/special"],
]) {
  const list = anchors(read(indexFile));
  for (const item of items) {
    const expectedText = base.includes("forms") ? `${item.code} ${item.title}` : item.title;
    const link = list.find((anchor) => anchor.text === expectedText);
    assert.ok(link, `missing list link: ${expectedText}`);
    const destination = path.posix.normalize(path.posix.join(path.posix.dirname(indexFile), href(link.attrs)));
    assert.equal(exists(destination), true, `broken list link: ${destination}`);
  }
}

for (const part of toc.parts) {
  for (const section of part.sections) {
    const relative = `versions/115-04/chapters/${part.id}/${section.id}.html`;
    const html = read(relative);
    const localLinks = anchors(html).filter((anchor) => /href="[^"]+\.html"/.test(anchor.attrs) && toc.parts.flatMap((entry) => entry.sections).some((item) => item.title === anchor.text));
    assert.equal(localLinks.length, part.sections.length, `incomplete side navigation: ${relative}`);
    const current = localLinks.filter((anchor) => /aria-current="page"/.test(anchor.attrs));
    assert.equal(current.length, 1, `missing current chapter: ${relative}`);
    assert.equal(href(current[0].attrs), `${section.id}.html`);
  }
}

const pdfAnchors = htmlFiles.flatMap((file) => anchors(fs.readFileSync(file, "utf8")).filter((anchor) => /\.pdf(?:#|"|$)/.test(href(anchor.attrs) || "")));
assert.equal(pdfAnchors.length > 0, true);
assert.equal(pdfAnchors.every((anchor) => (/target="_blank"/.test(anchor.attrs) && /rel="noopener noreferrer"/.test(anchor.attrs)) || /\bdownload\b/.test(anchor.attrs)), true);

console.log("SEARCH EXPERIENCE TESTS PASSED");
