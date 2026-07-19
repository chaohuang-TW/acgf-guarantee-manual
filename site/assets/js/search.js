(function () {
  "use strict";

  const normalize = (value) => value
    .normalize("NFKC")
    .toLocaleLowerCase("zh-Hant")
    .replace(/\s+/g, " ")
    .trim();

  const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"
  })[character]);

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
      synonymsPromise = fetch(synonymsUrl)
        .then((response) => (response.ok ? response.json() : {}))
        .catch(() => ({}));
    }
    return synonymsPromise;
  }

  function normalizedSynonyms(raw) {
    return Object.fromEntries(Object.entries(raw || {}).map(([term, values]) => [
      normalize(term),
      [...new Set((Array.isArray(values) ? values : []).map(normalize).filter(Boolean))],
    ]));
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

  function textMatch(value, term) {
    return normalize(value).includes(term);
  }

  function fieldScore(value, original, synonyms, exactWeight, containsWeight, synonymExactWeight, synonymContainsWeight) {
    const normalized = normalize(value);
    if (normalized === original) return exactWeight;
    if (normalized.includes(original)) return containsWeight;
    if (synonyms.some((term) => normalized === term)) return synonymExactWeight;
    if (synonyms.some((term) => normalized.includes(term))) return synonymContainsWeight;
    return 0;
  }

  function recordSearchResult(record, index, original, terms) {
    const synonyms = terms.filter((term) => term !== original);
    const title = record.title || "";
    const breadcrumb = (record.breadcrumb || []).join(" › ");
    const body = record.text || "";
    const originalMatches = [title, breadcrumb, body].some((value) => textMatch(value, original));
    const synonymMatches = synonyms.some((term) => [title, breadcrumb, body].some((value) => textMatch(value, term)));
    const requestedForm = formNumber(original);
    const exactForm = requestedForm && new RegExp(`^格式\\s*${requestedForm.replace(/[.*+?^${}()|[\\]\\]/g, "\\$&")}(?:：|\\s|$)`).test(title);
    if (!originalMatches && !synonymMatches && !exactForm) return null;
    const titleScore = fieldScore(title, original, synonyms, 100, 80, 75, 65);
    const breadcrumbScore = fieldScore(breadcrumb, original, synonyms, 0, 55, 0, 45);
    const bodyScore = fieldScore(body, original, synonyms, 0, 30, 0, 20);
    return {
      record,
      index,
      score: titleScore + breadcrumbScore + bodyScore + (exactForm ? 120 : 0),
      originalMatches,
      titleMatches: titleScore > 0,
      matchedTerm: originalMatches ? original : synonyms.find((term) => textMatch(title, term) || textMatch(breadcrumb, term) || textMatch(body, term)) || original,
    };
  }

  function searchRecords(records, query, rawSynonyms) {
    const terms = expandQuery(query, rawSynonyms);
    const original = terms[0] || "";
    const matches = records.map((record, index) => recordSearchResult(record, index, original, terms)).filter(Boolean);
    matches.sort((left, right) => right.score - left.score || Number(right.originalMatches) - Number(left.originalMatches) || Number(right.titleMatches) - Number(left.titleMatches) || left.index - right.index);
    return { terms, matches };
  }

  function snippet(original, query) {
    const haystack = normalize(original);
    const needle = normalize(query);
    const position = Math.max(0, haystack.indexOf(needle));
    const start = Math.max(0, position - 55);
    const end = Math.min(original.length, position + needle.length + 95);
    return `${start > 0 ? "…" : ""}${original.slice(start, end)}${end < original.length ? "…" : ""}`;
  }

  function attach(panel) {
    const form = panel.querySelector("form");
    const input = panel.querySelector("input[type=search]");
    const status = panel.querySelector(".search-status");
    const results = panel.querySelector(".search-results");
    let timer;

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
        const siteRoot = new URL(document.body.dataset.siteRoot || "./", document.baseURI);
        const synonymNote = terms.length > 1 ? ` 已同時搜尋：${terms.slice(1).join("、")}。` : "";
        status.textContent = `找到 ${matches.length} 筆結果，先顯示 ${Math.min(50, matches.length)} 筆。${synonymNote}`;
        results.innerHTML = matches.slice(0, 50).map(({ record, matchedTerm }) => `
          <article class="search-result">
            <h3><a href="${escapeHtml(new URL(record.url, siteRoot).href)}">${escapeHtml(record.title)}</a></h3>
            <p class="result-path">${escapeHtml(record.breadcrumb.join(" › "))}</p>
            <p>${escapeHtml(snippet(record.text, matchedTerm))}</p>
            <p class="result-pages">手冊頁：${escapeHtml(record.printedPage || "無")}　PDF頁：${record.pdfPage}／203</p>
          </article>`).join("");
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
    document.querySelectorAll("[data-keyword]").forEach((button) => {
      button.addEventListener("click", () => {
        input.value = button.dataset.keyword;
        input.focus();
        run();
      });
    });
  }

  globalThis.ManualSearch = { expandQuery, formNumber, searchRecords };
  if (typeof document !== "undefined") document.querySelectorAll("[data-search]").forEach(attach);
})();
