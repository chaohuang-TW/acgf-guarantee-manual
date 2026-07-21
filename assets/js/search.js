(function () {
  "use strict";

  const TYPE_LABELS = { chapter: "正文", appendix: "附錄", form: "書表", "lookup-table": "查索表", "front-matter": "其他" };
  const HAN = /[\u3400-\u9fff]/u;
  const CJK_PUNCTUATION = new Set("，。；：！？、】【（）「」『』【】《》〈〉／/%％﹪、○");
  const ITEM_START = /^(?:[壹貳參肆伍陸柒捌玖拾][、．.]|[一二三四五六七八九十][、．.]|[（(][一二三四五六七八九十0-9０-９]+[）)]|[０-９0-9]+[、.．]|※|備註：|附註：|第[一二三四五六七八九十0-9０-９]+[篇章節])/;
  const FRONT_MATTER_TERMS = ["目錄", "前言", "封面", "序"];

  const normalize = (value) => String(value || "").normalize("NFKC").toLocaleLowerCase("zh-Hant").replace(/\s+/g, " ").trim();

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
    return /[A-Za-z0-9]/.test(left.at(-1)) && /^[A-Za-z0-9]/.test(right) ? `${left} ${right}` : `${left}${right}`;
  }

  function normalizeDisplayText(rawText) {
    const paragraphs = [];
    let current = "";
    for (const rawLine of String(rawText || "").replace(/\r\n?/g, "\n").split("\n")) {
      const line = normalizeLineSpaces(rawLine);
      if (!line) {
        if (current) paragraphs.push(current);
        current = "";
      } else if (current && (ITEM_START.test(line) || /[。！？]$/.test(current))) {
        paragraphs.push(current);
        current = line;
      } else current = joinDisplayLines(current, line);
    }
    if (current) paragraphs.push(current);
    return paragraphs;
  }

  function cleanSnippetText(rawText) {
    return normalizeDisplayText(rawText).join("").replace(/-{5,}/g, "").replace(/\s+/g, " ").trim();
  }

  function tokenizeQuery(query) {
    const phrase = normalize(query);
    const words = phrase.split(/[\s\u3000,，、；;：:！!？?（）()【】《》]+/).filter(Boolean);
    return { phrase, words: [...new Set(words)] };
  }

  function prepareConcepts(raw) {
    return (raw?.concepts || []).map((concept) => ({
      id: concept.id,
      terms: [...new Set((concept.terms || []).map(normalize).filter(Boolean))],
    }));
  }

  function queryConcepts(query, rawConcepts) {
    const { phrase, words } = tokenizeQuery(query);
    const concepts = prepareConcepts(rawConcepts);
    const items = words.map((word) => {
      const source = concepts.find((concept) => concept.terms.includes(word) || concept.terms.some((term) => word.includes(term) || term.includes(word)));
      return { token: word, id: source?.id || `term:${word}`, terms: source?.terms || [word] };
    });
    return { phrase, words, concepts: items };
  }

  function formNumber(query) {
    const match = normalize(query).match(/^(?:格式\s*)?(\d+(?:-\d+)?[a-z]?)$/);
    return match ? match[1] : null;
  }

  function fieldMatches(field, terms) {
    const normalized = normalize(field);
    return terms.filter((term) => normalized.includes(term));
  }

  function isExplicitFrontMatterQuery(phrase) {
    return FRONT_MATTER_TERMS.some((term) => phrase.includes(term));
  }

  function activeIntents(queryInfo, rawIntents) {
    const source = rawIntents?.intents || [];
    const queryTerms = new Set([queryInfo.phrase, ...queryInfo.words]);
    return source.filter((intent) => (intent.triggers || []).map(normalize).some((trigger) => [...queryTerms].some((term) => term.includes(trigger))));
  }

  function intentScore(record, queryInfo, intents) {
    const title = normalize(record.title);
    const breadcrumb = normalize((record.breadcrumb || []).join(" › "));
    const headings = normalize((record.headings || []).join(" "));
    const body = normalize(record.text);
    let score = 0;
    for (const intent of intents) {
      const preferred = (intent.preferredTerms || []).map(normalize);
      const hasPreferredTitle = preferred.some((term) => title.includes(term) || breadcrumb.includes(term) || headings.includes(term));
      const hasPreferredBody = preferred.some((term) => body.includes(term));
      if (hasPreferredTitle) score += 150 + (intent.preferredTitleScore || 0);
      if (hasPreferredBody) score += 75;
      const overrides = intent.typeOverrideTerms?.[record.type] || [];
      const hasTypeOverride = overrides.map(normalize).some((term) => queryInfo.phrase.includes(term) || queryInfo.words.includes(term));
      if (intent.preferredTypes?.length && !intent.preferredTypes.includes(record.type) && !hasTypeOverride) score -= 350;
      if (intent.preferredTypes?.includes(record.type)) score += intent.preferredTypeScore || 0;
      if (hasTypeOverride) score += 100;
    }
    return score;
  }

  function proximityScore(body, concepts) {
    if (concepts.length < 2) return 0;
    const text = normalize(body);
    const positions = concepts.map((concept) => Math.min(...concept.terms.map((term) => text.indexOf(term)).filter((position) => position >= 0)));
    if (positions.some((position) => !Number.isFinite(position))) return 0;
    const spread = Math.max(...positions) - Math.min(...positions);
    return spread <= 180 ? Math.max(20, 110 - Math.floor(spread / 2)) : 0;
  }

  function chapterKey(record) {
    if (record.type === "form" || record.type === "lookup-table") return `record:${record.url}`;
    return `${record.type || "unknown"}:${(record.breadcrumb || []).join("|")}`;
  }

  function recordSearchResult(record, index, queryInfo, intents) {
    const title = record.title || "";
    const breadcrumb = (record.breadcrumb || []).join(" › ");
    const headings = (record.headings || []).join(" › ");
    const body = record.text || "";
    const titleNormalized = normalize(title);
    const breadcrumbNormalized = normalize(breadcrumb);
    const headingsNormalized = normalize(headings);
    const bodyNormalized = normalize(body);
    const requestedForm = formNumber(queryInfo.phrase);
    const exactForm = requestedForm && new RegExp(`^格式\\s*${requestedForm.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?:：|\\s|$)`, "i").test(title);
    const covered = [];
    const matchedTerms = new Set();
    let score = 0;
    for (const concept of queryInfo.concepts) {
      const originalInTitle = titleNormalized.includes(concept.token);
      const originalInBreadcrumb = breadcrumbNormalized.includes(concept.token);
      const originalInHeadings = headingsNormalized.includes(concept.token);
      const originalInBody = bodyNormalized.includes(concept.token);
      const expansionInTitle = fieldMatches(title, concept.terms);
      const expansionInBreadcrumb = fieldMatches(breadcrumb, concept.terms);
      const expansionInHeadings = fieldMatches(headings, concept.terms);
      const expansionInBody = fieldMatches(body, concept.terms);
      const hasMatch = originalInTitle || originalInBreadcrumb || originalInHeadings || originalInBody || expansionInTitle.length || expansionInBreadcrumb.length || expansionInHeadings.length || expansionInBody.length;
      if (!hasMatch) continue;
      covered.push(concept);
      [
        ...(originalInTitle ? [concept.token] : expansionInTitle),
        ...(originalInBreadcrumb ? [concept.token] : expansionInBreadcrumb),
        ...(originalInHeadings ? [concept.token] : expansionInHeadings),
        ...(originalInBody ? [concept.token] : expansionInBody),
      ].forEach((term) => matchedTerms.add(term));
      score += originalInTitle ? 115 : expansionInTitle.length ? 75 : 0;
      score += originalInBreadcrumb ? 90 : expansionInBreadcrumb.length ? 55 : 0;
      score += originalInHeadings ? 430 : expansionInHeadings.length ? 300 : 0;
      score += originalInBody ? 220 : expansionInBody.length ? 30 : 0;
    }
    const phraseMatch = queryInfo.words.length > 1 && [titleNormalized, breadcrumbNormalized, headingsNormalized, bodyNormalized].some((field) => field.includes(queryInfo.phrase));
    if (!covered.length && !exactForm) return null;
    score += exactForm ? 1000 : 0;
    score += phraseMatch ? 300 : 0;
    score += Math.round((covered.length / Math.max(1, queryInfo.concepts.length)) * 260);
    score += proximityScore(body, covered);
    score += intentScore(record, queryInfo, intents);
    if (record.type === "front-matter" && !isExplicitFrontMatterQuery(queryInfo.phrase)) score -= 400;
    return {
      record,
      index,
      baseScore: score,
      exactForm: Boolean(exactForm),
      phraseMatch,
      coverage: covered.length,
      coverageTotal: queryInfo.concepts.length,
      titleMatches: [...matchedTerms].some((term) => titleNormalized.includes(term)),
      matchedTerms: [...matchedTerms],
      coveredTerms: covered.map((concept) => concept.token),
      chapterKey: chapterKey(record),
    };
  }

  function diversify(matches) {
    const remaining = [...matches];
    const result = [];
    const chapterCounts = new Map();
    while (remaining.length) {
      remaining.sort((left, right) => {
        const leftPenalty = (chapterCounts.get(left.chapterKey) || 0) * 250;
        const rightPenalty = (chapterCounts.get(right.chapterKey) || 0) * 250;
        return (right.baseScore - rightPenalty) - (left.baseScore - leftPenalty)
          || Number(right.exactForm) - Number(left.exactForm)
          || Number(right.phraseMatch) - Number(left.phraseMatch)
          || right.coverage - left.coverage
          || Number(right.titleMatches) - Number(left.titleMatches)
          || left.index - right.index;
      });
      const next = remaining.shift();
      next.chapterPenalty = (chapterCounts.get(next.chapterKey) || 0) * 250;
      next.score = next.baseScore - next.chapterPenalty;
      chapterCounts.set(next.chapterKey, (chapterCounts.get(next.chapterKey) || 0) + 1);
      result.push(next);
    }
    return result;
  }

  function searchRecords(records, query, rawConcepts, rawIntents) {
    const queryInfo = queryConcepts(query, rawConcepts);
    if (!queryInfo.phrase) return { queryInfo, intents: [], matches: [] };
    const intents = activeIntents(queryInfo, rawIntents);
    const matches = records.map((record, index) => recordSearchResult(record, index, queryInfo, intents)).filter(Boolean);
    return { queryInfo, intents, matches: diversify(matches) };
  }

  function filterMatches(matches, selectedType) {
    return selectedType === "all" ? matches : matches.filter(({ record }) => record.type === selectedType);
  }

  function filterRecordsByScope(records, scope) {
    if (!scope) return records;
    const isGroupScope = scope.endsWith("/") || scope.endsWith(":");
    return records.filter((record) => isGroupScope ? String(record.scope || "").startsWith(scope) : record.scope === scope);
  }

  function snippet(rawText, terms) {
    const text = cleanSnippetText(rawText);
    const normalized = normalize(text);
    const positions = terms.map((term) => normalized.indexOf(normalize(term))).filter((position) => position >= 0);
    if (!positions.length) return text.slice(0, 160);
    const position = Math.min(...positions);
    const start = Math.max(0, position - 65);
    const end = Math.min(text.length, Math.max(start + 120, position + 105));
    return `${start ? "…" : ""}${text.slice(start, end)}${end < text.length ? "…" : ""}`;
  }

  function zeroResultMessage(query) {
    if (normalize(query) === "原保地貸款") return "找不到完全符合的內容，請嘗試正式用語或查看完整目錄。建議：保證對象、農業貸款；原住民族地區相關貸款請另查最新正式規定。";
    return "找不到完全符合的內容，請嘗試正式用語或查看完整目錄。";
  }

  let indexPromise;
  let conceptsPromise;
  let intentsPromise;

  function loadData(filename, fallback) {
    const root = new URL(document.body.dataset.siteRoot || "./", document.baseURI);
    return fetch(new URL(`assets/data/${filename}`, root)).then((response) => response.ok ? response.json() : fallback).catch(() => fallback);
  }

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

  function loadConcepts() {
    if (!conceptsPromise) conceptsPromise = loadData("search-concepts.json", { concepts: [] });
    return conceptsPromise;
  }

  function loadIntents() {
    if (!intentsPromise) intentsPromise = loadData("search-intents.json", { intents: [] });
    return intentsPromise;
  }

  function appendText(parent, tagName, className, text) {
    const element = document.createElement(tagName);
    if (className) element.className = className;
    element.textContent = text;
    parent.append(element);
    return element;
  }

  function resultElement(result, siteRoot) {
    const { record } = result;
    const article = document.createElement("article");
    article.className = "search-result";
    const heading = document.createElement("h3");
    const link = document.createElement("a");
    link.href = new URL(record.url, siteRoot).href;
    link.textContent = record.title;
    heading.append(link);
    const type = document.createElement("span");
    type.className = "result-type";
    type.textContent = TYPE_LABELS[record.type] || "其他";
    heading.append(type);
    article.append(heading);
    appendText(article, "p", "result-path", (record.breadcrumb || []).join(" › "));
    appendText(article, "p", "result-snippet", snippet(record.text, result.matchedTerms));
    const meta = [result.matchedTerms.length ? `命中：${result.matchedTerms.slice(0, 3).join("、")}` : "", result.coveredTerms.length ? `涵蓋：${result.coveredTerms.join("、")}` : ""].filter(Boolean).join("　");
    if (meta) appendText(article, "p", "result-match-meta", meta);
    appendText(article, "p", "result-pages", `手冊頁：${record.printedPage || "無"}　PDF頁：${record.pdfPage}／203`);
    return article;
  }

  function attach(panel) {
    const form = panel.querySelector("form");
    const input = panel.querySelector("input[type=search]");
    const status = panel.querySelector(".search-status");
    const results = panel.querySelector(".search-results");
    const filterButtons = [...panel.querySelectorAll("[data-search-type]")];
    const scopeButtons = [...panel.querySelectorAll("[data-search-scope]")];
    const moreButton = panel.querySelector(".search-more");
    const searchAllButton = panel.querySelector(".search-search-all");
    const localScope = panel.dataset.searchScope || "";
    const localScopeLabel = panel.dataset.searchScopeLabel || "本章";
    const resultLimit = Number(panel.dataset.searchLimit || 50);
    let selectedType = "all";
    let selectedScope = localScope ? "local" : "all";
    let visibleCount = resultLimit;
    let currentMatches = [];
    let timer;

    function updateScopeButtons() {
      for (const option of scopeButtons) option.setAttribute("aria-pressed", String(option.dataset.searchScope === selectedScope));
    }

    function render() {
      const filtered = filterMatches(currentMatches, selectedType);
      const shown = filtered.slice(0, visibleCount);
      const siteRoot = new URL(document.body.dataset.siteRoot || "./", document.baseURI);
      status.textContent = `找到 ${filtered.length} 筆結果，先顯示 ${shown.length} 筆。`;
      results.replaceChildren(...shown.map((result) => resultElement(result, siteRoot)));
      if (moreButton) moreButton.hidden = shown.length >= filtered.length;
    }

    async function run() {
      const query = input.value;
      visibleCount = resultLimit;
      if (moreButton) moreButton.hidden = true;
      if (searchAllButton) searchAllButton.hidden = true;
      if (!normalize(query)) {
        status.textContent = "請輸入搜尋文字。";
        results.replaceChildren();
        return;
      }
      status.textContent = "搜尋中…";
      try {
        const [records, concepts, intents] = await Promise.all([loadIndex(), loadConcepts(), loadIntents()]);
        const scopedRecords = selectedScope === "local" ? filterRecordsByScope(records, localScope) : records;
        const searched = searchRecords(scopedRecords, query, concepts, intents);
        currentMatches = searched.matches;
        if (!currentMatches.length && selectedScope === "local") {
          status.textContent = `${localScopeLabel}未找到相關內容。`;
          results.replaceChildren();
          if (searchAllButton) searchAllButton.hidden = false;
          return;
        }
        if (!currentMatches.length) {
          status.textContent = zeroResultMessage(query);
          results.replaceChildren();
          return;
        }
        render();
      } catch (error) {
        status.textContent = "搜尋索引目前無法載入，請稍後再試或查閱完整PDF。";
        results.replaceChildren();
      }
    }

    form.addEventListener("submit", (event) => { event.preventDefault(); window.clearTimeout(timer); run(); });
    input.addEventListener("input", () => { window.clearTimeout(timer); timer = window.setTimeout(run, 250); });
    for (const button of filterButtons) button.addEventListener("click", () => {
      selectedType = button.dataset.searchType;
      for (const option of filterButtons) option.setAttribute("aria-pressed", String(option === button));
      visibleCount = resultLimit;
      if (currentMatches.length) render();
      else run();
    });
    for (const button of scopeButtons) button.addEventListener("click", () => {
      selectedScope = button.dataset.searchScope;
      updateScopeButtons();
      run();
    });
    if (moreButton) moreButton.addEventListener("click", () => { visibleCount += resultLimit; render(); });
    if (searchAllButton) searchAllButton.addEventListener("click", () => {
      selectedScope = "all";
      updateScopeButtons();
      run();
    });
    panel.__manualSearch = { input, run };
  }

  globalThis.ManualSearch = { cleanSnippetText, diversify, filterMatches, filterRecordsByScope, formNumber, queryConcepts, searchRecords, snippet, tokenizeQuery, zeroResultMessage };
  if (typeof document !== "undefined") {
    document.querySelectorAll("[data-search]").forEach(attach);
    document.querySelectorAll("[data-keyword]").forEach((button) => button.addEventListener("click", () => {
      const panel = button.closest("section")?.querySelector("[data-search]") || document.querySelector("[data-search]");
      const search = panel?.__manualSearch;
      if (!search) return;
      search.input.value = button.dataset.keyword;
      search.input.focus();
      search.run();
    }));
  }
})();
