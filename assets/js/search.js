(function () {
  "use strict";

  const TYPE_LABELS = {
    chapter: "正文",
    appendix: "附錄",
    form: "書表",
    "lookup-table": "查索表",
    "front-matter": "其他",
  };
  const HAN = /[\u3400-\u9fff]/u;
  const CJK_PUNCTUATION = new Set("，。；：！？、】【（）「」『』【】《》〈〉／/%％﹪、○");
  const ITEM_START = /^(?:[壹貳參肆伍陸柒捌玖拾][、．.]|[一二三四五六七八九十][、．.]|[（(][一二三四五六七八九十0-9０-９]+[）)]|[０-９0-9]+[、.．]|※|備註：|附註：|第[一二三四五六七八九十0-9０-９]+[篇章節])/;
  const FEE_TERMS = ["保費", "手續費率", "保證手續費", "保證手續費率"];

  const normalize = (value) => String(value || "")
    .normalize("NFKC")
    .toLocaleLowerCase("zh-Hant")
    .replace(/\s+/g, " ")
    .trim();

  function isLayoutCharacter(character) {
    return HAN.test(character) || CJK_PUNCTUATION.has(character) || /[０-９]/.test(character);
  }

  function normalizeLineSpaces(line) {
    return line.replace(/[ \t\u3000]+/g, (space, offset, source) => {
      const left = source.slice(0, offset).at(-1) || "";
      const right = source.slice(offset + space.length).at(0) || "";
      return (isLayoutCharacter(left) && isLayoutCharacter(right)) || (/\d/.test(left) && /[％﹪%]/.test(right)) ? "" : " ";
    }).trim();
  }

  function joinDisplayLines(left, right) {
    if (!left) return right;
    return /[\x00-\x7F]/.test(left.at(-1)) && /[A-Za-z0-9]/.test(left.at(-1)) && /^[A-Za-z0-9]/.test(right)
      ? `${left} ${right}`
      : `${left}${right}`;
  }

  function normalizeDisplayText(rawText) {
    const paragraphs = [];
    let current = "";
    for (const original of String(rawText || "").replace(/\r\n?/g, "\n").split("\n")) {
      const line = normalizeLineSpaces(original);
      if (!line) {
        if (current) paragraphs.push(current);
        current = "";
      } else if (current && (ITEM_START.test(line) || /[。！？]$/.test(current))) {
        paragraphs.push(current);
        current = line;
      } else {
        current = joinDisplayLines(current, line);
      }
    }
    if (current) paragraphs.push(current);
    return paragraphs;
  }

  function cleanSnippetText(rawText) {
    return normalizeDisplayText(rawText).join("").replace(/-{5,}/g, "").replace(/\s+/g, " ").trim();
  }

  function normalizedCharacterMap(value) {
    const output = [];
    const positions = [];
    let offset = 0;
    for (const character of String(value || "")) {
      const start = offset;
      offset += character.length;
      const normalized = character.normalize("NFKC").toLocaleLowerCase("zh-Hant");
      for (const part of normalized) {
        if (/\s/.test(part)) {
          if (output.at(-1) === " ") positions[positions.length - 1].end = offset;
          else {
            output.push(" ");
            positions.push({ start, end: offset });
          }
        } else {
          output.push(part);
          positions.push({ start, end: offset });
        }
      }
    }
    return { normalized: output.join("").trim(), positions };
  }

  function highlightRanges(value, terms) {
    const { normalized, positions } = normalizedCharacterMap(value);
    const candidates = [];
    for (const term of [...new Set(terms.map(normalize).filter(Boolean))]) {
      let offset = normalized.indexOf(term);
      while (offset !== -1) {
        const end = offset + term.length;
        if (positions[offset] && positions[end - 1]) candidates.push({ start: positions[offset].start, end: positions[end - 1].end });
        offset = normalized.indexOf(term, offset + Math.max(1, term.length));
      }
    }
    candidates.sort((left, right) => left.start - right.start || right.end - left.end);
    return candidates.reduce((ranges, candidate) => {
      if (!ranges.length || candidate.start >= ranges.at(-1).end) ranges.push(candidate);
      return ranges;
    }, []);
  }

  function highlightParts(value, terms) {
    const text = String(value || "");
    const ranges = highlightRanges(text, terms);
    const parts = [];
    let cursor = 0;
    for (const range of ranges) {
      if (cursor < range.start) parts.push({ text: text.slice(cursor, range.start), marked: false });
      parts.push({ text: text.slice(range.start, range.end), marked: true });
      cursor = range.end;
    }
    if (cursor < text.length || !parts.length) parts.push({ text: text.slice(cursor), marked: false });
    return parts;
  }

  function snippet(rawText, terms) {
    const text = cleanSnippetText(rawText);
    const matchingTerms = terms.filter((term) => normalize(text).includes(normalize(term)));
    const ranges = highlightRanges(text, matchingTerms);
    if (!ranges.length) return { text: text.slice(0, 160), terms: [] };
    const match = ranges[0];
    const start = Math.max(0, match.start - 65);
    const end = Math.min(text.length, Math.max(match.end + 100, start + 120));
    return { text: `${start ? "…" : ""}${text.slice(start, end)}${end < text.length ? "…" : ""}`, terms: matchingTerms };
  }

  let indexPromise;
  let synonymsPromise;

  function loadIndex() {
    if (!indexPromise) {
      const indexUrl = new URL(document.body.dataset.searchIndex, document.baseURI);
      indexPromise = fetch(indexUrl).then((response) => {
        if (!response.ok) throw new Error("搜尋索引載入失敗");
        return response.json();
      });
    }
    return indexPromise;
  }

  function loadSynonyms() {
    if (!synonymsPromise) {
      const siteRoot = new URL(document.body.dataset.siteRoot || "./", document.baseURI);
      const synonymsUrl = new URL("assets/data/search-synonyms.json", siteRoot);
      synonymsPromise = fetch(synonymsUrl).then((response) => response.ok ? response.json() : {}).catch(() => ({}));
    }
    return synonymsPromise;
  }

  function normalizedSynonyms(raw) {
    return Object.fromEntries(Object.entries(raw || {}).map(([term, values]) => [normalize(term), [...new Set((Array.isArray(values) ? values : []).map(normalize).filter(Boolean))]]));
  }

  function expandQuery(query, rawSynonyms) {
    const original = normalize(query);
    const synonyms = normalizedSynonyms(rawSynonyms);
    return [...new Set([original, ...(synonyms[original] || [])].filter(Boolean))];
  }

  function formNumber(query) {
    const match = normalize(query).match(/^(?:格式\s*)?(\d+(?:-\d+)?)$/);
    return match ? match[1] : null;
  }

  function fieldScore(value, original, synonyms, exactWeight, containsWeight, synonymExactWeight, synonymContainsWeight) {
    const normalized = normalize(value);
    if (normalized === original) return exactWeight;
    if (normalized.includes(original)) return containsWeight;
    if (synonyms.some((term) => normalized === term)) return synonymExactWeight;
    if (synonyms.some((term) => normalized.includes(term))) return synonymContainsWeight;
    return 0;
  }

  function feeRuleScore(record, original) {
    if (!FEE_TERMS.includes(original)) return 0;
    const titleAndBreadcrumb = normalize(`${record.title || ""} ${(record.breadcrumb || []).join(" › ")}`);
    const body = normalize(record.text);
    let score = 0;
    if (titleAndBreadcrumb.includes("保證手續費率")) score += 25;
    if (titleAndBreadcrumb.includes("保證手續費")) score += 15;
    if (titleAndBreadcrumb.includes("手續費收取方式及計算公式")) score += 30;
    if (body.includes("保證手續費率表")) score += 200;
    if (body.includes("手續費收取方式及計算公式")) score += 80;
    return score;
  }

  function matchingTerms(value, terms) {
    const field = normalize(value);
    return terms.filter((term) => field.includes(term));
  }

  function recordSearchResult(record, index, original, terms) {
    const synonyms = terms.filter((term) => term !== original);
    const title = record.title || "";
    const breadcrumb = (record.breadcrumb || []).join(" › ");
    const body = record.text || "";
    const originalMatches = [title, breadcrumb, body].some((value) => normalize(value).includes(original));
    const synonymMatches = synonyms.some((term) => [title, breadcrumb, body].some((value) => normalize(value).includes(term)));
    const requestedForm = formNumber(original);
    const exactForm = requestedForm && new RegExp(`^格式\\s*${requestedForm.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?:：|\\s|$)`).test(title);
    if (!originalMatches && !synonymMatches && !exactForm) return null;
    const titleScore = fieldScore(title, original, synonyms, 100, 80, 75, 65);
    const breadcrumbScore = fieldScore(breadcrumb, original, synonyms, 0, 55, 0, 45);
    const bodyScore = fieldScore(body, original, synonyms, 0, 300, 0, 20);
    const titleTerms = matchingTerms(title, terms);
    const breadcrumbTerms = matchingTerms(breadcrumb, terms);
    const bodyTerms = matchingTerms(body, terms);
    return {
      record,
      index,
      score: titleScore + breadcrumbScore + bodyScore + feeRuleScore(record, original) + (exactForm ? 120 : 0),
      originalMatches,
      titleMatches: titleScore > 0,
      titleTerms,
      breadcrumbTerms,
      bodyTerms,
    };
  }

  function searchRecords(records, query, rawSynonyms) {
    const terms = expandQuery(query, rawSynonyms);
    const original = terms[0] || "";
    const matches = records.map((record, index) => recordSearchResult(record, index, original, terms)).filter(Boolean);
    matches.sort((left, right) => right.score - left.score || Number(right.originalMatches) - Number(left.originalMatches) || Number(right.titleMatches) - Number(left.titleMatches) || left.index - right.index);
    return { terms, matches };
  }

  function filterMatches(matches, selectedType) {
    return selectedType === "all" ? matches : matches.filter(({ record }) => record.type === selectedType);
  }

  function zeroResultMessage(query) {
    if (normalize(query) === "原保地貸款") return "找不到完全符合的內容，請嘗試正式用語或查看完整目錄。建議：保證對象、農業貸款；原住民族地區相關貸款請另查最新正式規定。";
    return "找不到完全符合的內容，請嘗試正式用語或查看完整目錄。";
  }

  function appendHighlighted(parent, value, terms) {
    for (const part of highlightParts(value, terms)) {
      const node = part.marked ? document.createElement("mark") : document.createTextNode(part.text);
      if (part.marked) node.textContent = part.text;
      parent.append(node);
    }
  }

  function appendTextElement(parent, tagName, className, value, terms) {
    const element = document.createElement(tagName);
    if (className) element.className = className;
    appendHighlighted(element, value, terms);
    parent.append(element);
    return element;
  }

  function resultElement(result, siteRoot) {
    const { record, titleTerms, breadcrumbTerms, bodyTerms } = result;
    const article = document.createElement("article");
    article.className = "search-result";
    const heading = document.createElement("h3");
    const link = document.createElement("a");
    link.href = new URL(record.url, siteRoot).href;
    appendHighlighted(link, record.title, titleTerms);
    heading.append(link);
    const type = document.createElement("span");
    type.className = "result-type";
    type.textContent = TYPE_LABELS[record.type] || TYPE_LABELS["front-matter"];
    heading.append(type);
    article.append(heading);
    appendTextElement(article, "p", "result-path", (record.breadcrumb || []).join(" › "), breadcrumbTerms);
    const resultSnippet = snippet(record.text, bodyTerms);
    appendTextElement(article, "p", "result-snippet", resultSnippet.text, resultSnippet.terms);
    const pages = document.createElement("p");
    pages.className = "result-pages";
    pages.textContent = `手冊頁：${record.printedPage || "無"}　PDF頁：${record.pdfPage}／203`;
    article.append(pages);
    return article;
  }

  function attach(panel) {
    const form = panel.querySelector("form");
    const input = panel.querySelector("input[type=search]");
    const status = panel.querySelector(".search-status");
    const results = panel.querySelector(".search-results");
    const filterButtons = [...panel.querySelectorAll("[data-search-type]")];
    let timer;
    let selectedType = "all";

    async function run() {
      const query = normalize(input.value);
      if (!query) {
        status.textContent = "請輸入搜尋文字。";
        results.replaceChildren();
        return;
      }
      status.textContent = "搜尋中…";
      try {
        const [records, synonyms] = await Promise.all([loadIndex(), loadSynonyms()]);
        const { terms, matches } = searchRecords(records, query, synonyms);
        const filtered = filterMatches(matches, selectedType);
        if (!matches.length) {
          status.textContent = zeroResultMessage(query);
          results.replaceChildren();
          return;
        }
        const siteRoot = new URL(document.body.dataset.siteRoot || "./", document.baseURI);
        const synonymNote = terms.length > 1 ? ` 已同時搜尋：${terms.slice(1).join("、")}。` : "";
        status.textContent = `找到 ${filtered.length} 筆結果，先顯示 ${Math.min(50, filtered.length)} 筆。${synonymNote}`;
        results.replaceChildren(...filtered.slice(0, 50).map((result) => resultElement(result, siteRoot)));
      } catch (error) {
        status.textContent = "搜尋索引目前無法載入，請稍後再試或查閱完整PDF。";
        results.replaceChildren();
      }
    }

    form.addEventListener("submit", (event) => {
      event.preventDefault();
      window.clearTimeout(timer);
      run();
    });
    input.addEventListener("input", () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(run, 250);
    });
    for (const button of filterButtons) {
      button.addEventListener("click", () => {
        selectedType = button.dataset.searchType;
        for (const option of filterButtons) option.setAttribute("aria-pressed", String(option === button));
        run();
      });
    }
    document.querySelectorAll("[data-keyword]").forEach((button) => {
      button.addEventListener("click", () => {
        input.value = button.dataset.keyword;
        input.focus();
        run();
      });
    });
  }

  globalThis.ManualSearch = { cleanSnippetText, expandQuery, filterMatches, formNumber, highlightParts, normalizeDisplayText, searchRecords, snippet, zeroResultMessage };
  if (typeof document !== "undefined") document.querySelectorAll("[data-search]").forEach(attach);
})();
