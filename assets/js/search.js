(function () {
  "use strict";

  const TYPE_LABELS = { chapter: "正文", appendix: "附錄", form: "書表", "lookup-table": "查索表", "front-matter": "其他" };
  const VALID_TYPES = ["all", "chapter", "appendix", "form", "lookup-table", "front-matter"];

  function readSearchStateFromUrl(urlStr) {
    const url = new URL(urlStr);
    let q = url.searchParams.get("q");
    if (q === null) return { q: "", type: "all" };
    let type = url.searchParams.get("type") || "all";
    if (!VALID_TYPES.includes(type)) type = "all";
    return { q, type };
  }

  function writeSearchStateToUrl(state, replace = false) {
    const url = new URL(window.location.href);
    if (!state.q) {
      url.searchParams.delete("q");
      url.searchParams.delete("type");
    } else {
      url.searchParams.set("q", state.q);
      if (state.type && state.type !== "all") {
        url.searchParams.set("type", state.type);
      } else {
        url.searchParams.delete("type");
      }
    }
    const method = replace ? history.replaceState : history.pushState;
    method.call(history, null, "", url.href);
  }

  function searchStateUrl(state, baseUri) {
    const url = new URL(baseUri);
    if (state.q) {
      url.searchParams.set("q", state.q);
      if (state.type && state.type !== "all") {
        url.searchParams.set("type", state.type);
      }
    }
    return url.href;
  }

  function decorateResultUrlWithSearchState(urlStr, searchState) {
    if (!searchState || !searchState.q) return urlStr;
    const url = new URL(urlStr);
    url.searchParams.set("fromSearch", "1");
    url.searchParams.set("q", searchState.q);
    if (searchState.type && searchState.type !== "all") {
      url.searchParams.set("type", searchState.type);
    }
    return url.href;
  }
  const HAN = /[\u3400-\u9fff]/u;
  const CJK_PUNCTUATION = new Set("，。；：！？、】【（）「」『』【】《》〈〉／/%％﹪、○");
  const ITEM_START = /^(?:[壹貳參肆伍陸柒捌玖拾][、．.]|[一二三四五六七八九十][、．.]|[（(][一二三四五六七八九十0-9０-９]+[）)]|[０-９0-9]+[、.．]|※|備註：|附註：|第[一二三四五六七八九十0-9０-９]+[篇章節])/;
  const FRONT_MATTER_TERMS = ["目錄", "前言", "封面", "序"];

  const normalize = (value) => String(value || "").normalize("NFKC").toLocaleLowerCase("zh-Hant").replace(/\s+/g, " ").trim();

  function normalizeWithMap(value) {
    const source = String(value || "");
    let normalized = "";
    const offsets = [];
    let pendingSpace = false;
    for (let index = 0; index < source.length; index += 1) {
      const character = source[index].normalize("NFKC").toLocaleLowerCase("zh-Hant");
      if (/\s/.test(character)) {
        pendingSpace = normalized.length > 0;
        continue;
      }
      if (pendingSpace) {
        normalized += " ";
        offsets.push(index);
        pendingSpace = false;
      }
      normalized += character;
      offsets.push(index);
    }
    return { text: normalized, offsets };
  }

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

  function compactNormalizeWithMap(value) {
    const source = String(value || "");
    let text = "";
    const offsets = [];
    for (let index = 0; index < source.length; index += 1) {
      for (const character of source[index].normalize("NFKC").toLocaleLowerCase("zh-Hant")) {
        if (/\s/.test(character)) continue;
        text += character;
        offsets.push(index);
      }
    }
    return { text, offsets };
  }

  function bodyMatchOffsets(body, queryInfo) {
    const mapped = compactNormalizeWithMap(body);
    const candidates = [];
    const add = (term, priority, direct, source) => {
      const normalized = compactNormalizeWithMap(term).text;
      if (!normalized) return;
      const existing = candidates.find((candidate) => candidate.normalized === normalized);
      if (!existing || priority < existing.priority) {
        if (existing) candidates.splice(candidates.indexOf(existing), 1);
        candidates.push({ term, normalized, priority, direct, source });
      }
    };
    add(queryInfo.phrase, 0, true, "exact-phrase");
    queryInfo.words.forEach((term) => add(term, 1, true, "original-term"));
    queryInfo.concepts.forEach((concept) => {
      add(concept.terms[0], 2, false, "concept-canonical");
      concept.terms.slice(1).forEach((term) => add(term, 3, false, "concept-expansion"));
    });
    const matches = [];
    for (const candidate of candidates) {
      let start = 0;
      while (start < mapped.text.length) {
        const position = mapped.text.indexOf(candidate.normalized, start);
        if (position < 0) break;
        matches.push({
          ...candidate,
          normalizedOffset: position,
          rawOffset: mapped.offsets[position],
        });
        start = position + Math.max(1, candidate.normalized.length);
      }
    }
    return matches.sort((left, right) => left.priority - right.priority || left.rawOffset - right.rawOffset);
  }

  function metadataSegment(record, queryInfo) {
    const terms = [...new Set([queryInfo.phrase, ...queryInfo.words])].filter(Boolean);
    const ranked = (record.readingSegments || []).map((segment, index) => {
      const title = normalize(segment.title);
      const breadcrumb = normalize((segment.breadcrumb || []).join(" › "));
      let score = 0;
      for (const term of terms) {
        if (title === term) score += 500;
        else if (title.includes(term)) score += 350;
        if (breadcrumb.includes(term)) score += 200;
      }
      return { segment, index, score, terms: terms.filter((term) => title.includes(term) || breadcrumb.includes(term)) };
    }).filter((item) => item.score > 0);
    ranked.sort((left, right) => right.score - left.score || left.index - right.index);
    return ranked[0] || null;
  }

  function selectReadingSegments(record, queryInfo) {
    const segments = record.readingSegments || [];
    if (!segments.length) return [];
    const located = segments.flatMap((segment) => bodyMatchOffsets(segment.text, queryInfo).map((match) => ({
      ...match,
      rawOffset: segment.startOffset + match.rawOffset,
      segment,
    }))).sort((left, right) => left.priority - right.priority || left.rawOffset - right.rawOffset);
    if (located.length) {
      const directSegments = segments.map((segment) => ({
        segment,
        matches: located.filter((match) => match.segment.id === segment.id && match.direct),
      })).filter((item) => item.matches.length);
      const selected = directSegments.length > 1
        ? directSegments
        : [{
            segment: (directSegments[0]?.segment || located[0].segment),
            matches: directSegments[0]?.matches || located.filter((match) => match.segment.id === located[0].segment.id && match.priority === located[0].priority),
          }];
      return selected.map(({ segment, matches }) => ({
        segment,
        direct: matches.some((match) => match.direct),
        terms: [...new Set(matches.map((match) => match.term))],
        offsets: matches.map((match) => match.rawOffset),
        source: "body-offset",
      }));
    }
    const metadata = metadataSegment(record, queryInfo);
    return metadata ? [{
      segment: metadata.segment,
      direct: false,
      terms: metadata.terms,
      offsets: [],
      source: "metadata",
    }] : [];
  }

  function selectReadingSegment(record, queryInfo) {
    return selectReadingSegments(record, queryInfo)[0]?.segment || null;
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
    const segmentMatches = selectReadingSegments(record, queryInfo);
    const primarySegment = segmentMatches[0]?.segment || null;
    const title = primarySegment?.title || record.title || "";
    const breadcrumb = (primarySegment?.breadcrumb || record.breadcrumb || []).join(" › ");
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
    const offsetMatches = record.readingSegments?.length ? bodyMatchOffsets(body, queryInfo) : [];
    let bodyMatches = false;
    let score = 0;
    for (const concept of queryInfo.concepts) {
      const originalInTitle = titleNormalized.includes(concept.token);
      const originalInBreadcrumb = breadcrumbNormalized.includes(concept.token);
      const originalInHeadings = headingsNormalized.includes(concept.token);
      const originalInBody = bodyNormalized.includes(concept.token) || offsetMatches.some((match) => match.direct && compactNormalizeWithMap(match.term).text === compactNormalizeWithMap(concept.token).text);
      const expansionInTitle = fieldMatches(title, concept.terms);
      const expansionInBreadcrumb = fieldMatches(breadcrumb, concept.terms);
      const expansionInHeadings = fieldMatches(headings, concept.terms);
      const expansionInBody = fieldMatches(body, concept.terms);
      if (!expansionInBody.length) {
        offsetMatches
          .filter((match) => concept.terms.some((term) => compactNormalizeWithMap(term).text === compactNormalizeWithMap(match.term).text))
          .forEach((match) => expansionInBody.push(match.term));
      }
      const hasMatch = originalInTitle || originalInBreadcrumb || originalInHeadings || originalInBody || expansionInTitle.length || expansionInBreadcrumb.length || expansionInHeadings.length || expansionInBody.length;
      if (!hasMatch) continue;
      if (originalInBody || expansionInBody.length) bodyMatches = true;
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
      segment: segmentMatches[0]?.segment || null,
      segmentMatches,
      index,
      baseScore: score,
      exactForm: Boolean(exactForm),
      phraseMatch,
      coverage: covered.length,
      coverageTotal: queryInfo.concepts.length,
      titleMatches: [...matchedTerms].some((term) => titleNormalized.includes(term)),
      bodyMatches,
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
    const ranked = diversify(matches);
    const expanded = ranked.flatMap((match) => {
      if (match.segmentMatches.length <= 1) return [match];
      return match.segmentMatches.map((selection) => ({
        ...match,
        segment: selection.segment,
        matchedTerms: selection.terms.length ? selection.terms : match.matchedTerms,
      }));
    });
    return { queryInfo, intents, matches: expanded };
  }

  function filterMatches(matches, selectedType) {
    return selectedType === "all" ? matches : matches.filter(({ record }) => record.type === selectedType);
  }

  function filterRecordsByScope(records, scope) {
    if (!scope) return records;
    const isGroupScope = scope.endsWith("/") || scope.endsWith(":");
    return records.filter((record) => isGroupScope ? String(record.scope || "").startsWith(scope) : record.scope === scope);
  }

  function contextEligible(record) {
    return ["chapter", "appendix"].includes(record.type) && Number.isInteger(record.contextStartPdfPage) && Number.isInteger(record.contextEndPdfPage);
  }

  function continuationNeeded(text) {
    return /^(?:前項|前款|前目|其|並應|並|另|但|惟|如|若|除|仍|應|得|不得|同意者|不在此限)/.test(cleanSnippetText(text)) || /[、，；：]$/.test(cleanSnippetText(text));
  }

  function buildContextText(record) {
    const raw = [
      { pdfPage: record.contextStartPdfPage, printedPage: record.contextStartPrintedPage, source: "before", text: record.contextBefore || "" },
      { pdfPage: record.pdfPage, printedPage: record.printedPage, source: "current", text: record.text || "" },
      { pdfPage: record.contextEndPdfPage, printedPage: record.contextEndPrintedPage, source: "after", text: record.contextAfter || "" },
    ].filter((segment) => segment.text);
    let offset = 0;
    const segments = raw.map((segment) => {
      const text = cleanSnippetText(segment.text);
      const item = { ...segment, text, start: offset, end: offset + text.length };
      offset = item.end + 1;
      return item;
    });
    return { segments, text: segments.map((segment) => segment.text).join("\n"), current: segments.find((segment) => segment.source === "current") };
  }

  function findLogicalPassage(record, terms, bodyMatches = true) {
    if (!bodyMatches || !contextEligible(record)) return null;
    const context = buildContextText(record);
    const text = context.text;
    const current = context.current;
    if (!current) return null;
    const currentNormalized = normalizeWithMap(current.text);
    const positions = terms.map((term) => currentNormalized.text.indexOf(normalize(term))).filter((position) => position >= 0).map((position) => current.start + currentNormalized.offsets[position]);
    if (!positions.length) return null;
    const position = Math.min(...positions);
    const before = text.slice(0, position);
    const after = text.slice(position);
    const sentenceStart = Math.max(before.lastIndexOf("。"), before.lastIndexOf("！"), before.lastIndexOf("？"));
    const sentenceEndIndex = [after.indexOf("。"), after.indexOf("！"), after.indexOf("？")].filter((value) => value >= 0).sort((a, b) => a - b)[0];
    const start = continuationNeeded(record.text) && record.contextBefore ? 0 : Math.max(0, sentenceStart >= 0 ? sentenceStart + 1 : position - 280);
    const end = Math.min(text.length, sentenceEndIndex === undefined ? position + 620 : position + sentenceEndIndex + 1);
    const fullText = text.slice(start, Math.min(text.length, Math.max(end, start + 260)));
    if (fullText.length < 80) return null;
    const used = context.segments.filter((segment) => segment.end > start && segment.start < start + fullText.length);
    const first = used[0] || current;
    const last = used.at(-1) || current;
    return { fullText, preview: fullText.length > 560 ? `${fullText.slice(0, 560)}…` : fullText, expanded: fullText.length > 560, startPdfPage: first.pdfPage, endPdfPage: last.pdfPage, startPrintedPage: first.printedPage, endPrintedPage: last.printedPage, anchorPdfPage: first.pdfPage };
  }

  function resultTarget(record, passage, segment = null) {
    const target = segment?.readingUrl || record.readingUrl || record.url;
    const anchor = passage?.anchorPdfPage || record.pdfPage;
    return `${target}#pdf-page-${anchor}`;
  }

  function passageSimilarity(left, right) {
    const grams = (value) => {
      const text = normalize(value).replace(/\s+/g, "");
      return new Set(Array.from({ length: Math.max(0, text.length - 1) }, (_, index) => text.slice(index, index + 2)));
    };
    const a = grams(left), b = grams(right);
    if (a.size < 12 || b.size < 12) return 0;
    const common = [...a].filter((item) => b.has(item)).length;
    return common / (a.size + b.size - common);
  }

  function deduplicateAdjacentResults(matches) {
    const retained = [];
    for (const match of matches) {
      const passage = findLogicalPassage(match.record, match.matchedTerms, match.bodyMatches);
      const matchScope = match.segment?.scope || match.record.scope;
      const identity = match.segment
        ? `${match.segment.id}|${match.segment.readingUrl}|${matchScope}`
        : `${match.record.readingUrl || match.record.url}|${matchScope}`;
      const previous = retained.find((item) => {
        const itemScope = item.segment?.scope || item.record.scope;
        const itemIdentity = item.segment
          ? `${item.segment.id}|${item.segment.readingUrl}|${itemScope}`
          : `${item.record.readingUrl || item.record.url}|${itemScope}`;
        return itemIdentity === identity && item.record.type === match.record.type && Math.abs(item.record.pdfPage - match.record.pdfPage) === 1 && item.coveredTerms.join("|") === match.coveredTerms.join("|");
      });
      const previousPassage = previous && findLogicalPassage(previous.record, previous.matchedTerms, previous.bodyMatches);
      const duplicate = previous && passage && previousPassage && (passageSimilarity(passage.fullText, previousPassage.fullText) >= 0.58 || normalize(match.record.text) === normalize(previous.record.text));
      if (!duplicate) retained.push(match);
    }
    return retained;
  }


  function highlightText(text, terms) {
    const fragment = document.createDocumentFragment();
    if (!text || !terms || !terms.length) {
      fragment.appendChild(document.createTextNode(text || ""));
      return fragment;
    }

    const mapped = compactNormalizeWithMap(text);
    if (!mapped.text) {
      fragment.appendChild(document.createTextNode(text));
      return fragment;
    }

    const uniqueTerms = [...new Set(terms.filter(Boolean))];
    const normalizedTerms = uniqueTerms
      .map(t => compactNormalizeWithMap(t).text)
      .filter(Boolean)
      .sort((a, b) => b.length - a.length);

    if (!normalizedTerms.length) {
      fragment.appendChild(document.createTextNode(text));
      return fragment;
    }

    const matches = [];
    for (const nTerm of normalizedTerms) {
      let startIndex = 0;
      while (startIndex < mapped.text.length) {
        const pos = mapped.text.indexOf(nTerm, startIndex);
        if (pos < 0) break;
        const startRaw = mapped.offsets[pos];
        const endRaw = mapped.offsets[pos + nTerm.length - 1] + 1;

        const overlap = matches.some(m => Math.max(startRaw, m.start) < Math.min(endRaw, m.end));
        if (!overlap) {
          matches.push({ start: startRaw, end: endRaw });
        }
        startIndex = pos + nTerm.length;
      }
    }

    matches.sort((a, b) => a.start - b.start);

    let currentIndex = 0;
    for (const match of matches) {
      if (match.start > currentIndex) {
        fragment.appendChild(document.createTextNode(text.slice(currentIndex, match.start)));
      }
      const mark = document.createElement("mark");
      mark.className = "search-hit";
      mark.textContent = text.slice(match.start, match.end);
      fragment.appendChild(mark);
      currentIndex = match.end;
    }
    if (currentIndex < text.length) {
      fragment.appendChild(document.createTextNode(text.slice(currentIndex)));
    }

    return fragment;
  }

  function snippet(rawText, terms) {
    const text = cleanSnippetText(rawText);
    const mapped = compactNormalizeWithMap(text);
    const positions = terms.map((term) => {
      const nTerm = compactNormalizeWithMap(term).text;
      if (!nTerm) return -1;
      const idx = mapped.text.indexOf(nTerm);
      return idx >= 0 ? mapped.offsets[idx] : -1;
    }).filter((position) => position >= 0);
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

  function resultElement(result, siteRoot, searchState) {
    const { record } = result;
    const presentation = result.segment || record;
    const article = document.createElement("article");
    article.className = "search-result";
    const heading = document.createElement("h3");
    const link = document.createElement("a");
    const sharedPage = (record.readingSegments || []).length > 1;
    const passage = sharedPage ? null : findLogicalPassage(record, result.matchedTerms, result.bodyMatches);
    link.href = decorateResultUrlWithSearchState(new URL(resultTarget(record, passage, result.segment), siteRoot).href, searchState);
    link.appendChild(highlightText(presentation.title, result.matchedTerms));
    heading.append(link);
    const type = document.createElement("span");
    type.className = "result-type";
    type.textContent = TYPE_LABELS[record.type] || "其他";
    heading.append(type);
    article.append(heading);
    appendText(article, "p", "result-path", (presentation.breadcrumb || record.breadcrumb || []).join(" › "));
    const snippetP = document.createElement("p");
    snippetP.className = "result-snippet";
    snippetP.appendChild(highlightText(passage ? passage.preview : snippet(presentation.text || record.text, result.matchedTerms), result.matchedTerms));
    article.appendChild(snippetP);
    if (passage?.expanded) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "search-context-toggle";
      button.textContent = "顯示完整段落";
      button.setAttribute("aria-expanded", "false");
      const full = document.createElement("p");
      full.className = "result-context-full";
      full.appendChild(highlightText(passage.fullText, result.matchedTerms));
      article.appendChild(full);
      full.hidden = true;
      button.addEventListener("click", () => {
        full.hidden = !full.hidden;
        button.setAttribute("aria-expanded", String(!full.hidden));
        button.textContent = full.hidden ? "顯示完整段落" : "收合完整段落";
      });
      article.append(button);
    }
    const meta = [result.matchedTerms.length ? `命中：${result.matchedTerms.slice(0, 3).join("、")}` : "", result.coveredTerms.length ? `涵蓋：${result.coveredTerms.join("、")}` : ""].filter(Boolean).join("　");
    if (meta) appendText(article, "p", "result-match-meta", meta);
    const pages = passage && (passage.startPdfPage !== record.pdfPage || passage.endPdfPage !== record.pdfPage)
      ? `內容涵蓋手冊頁：${passage.startPrintedPage}–${passage.endPrintedPage}　命中頁：手冊頁${record.printedPage || "無"}　PDF頁：${record.pdfPage}／203`
      : `手冊頁：${record.printedPage || "無"}　PDF頁：${record.pdfPage}／203`;
    appendText(article, "p", "result-pages", pages);
    if (record.readingUrl && record.readingUrl !== record.url) {
      const exact = document.createElement("a");
      exact.className = "result-exact-page";
      exact.href = decorateResultUrlWithSearchState(new URL(`${record.url}#pdf-page-${record.pdfPage}`, siteRoot).href, searchState);
      exact.textContent = "僅查看命中頁";
      article.append(exact);
    }
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

    const copyButton = document.createElement("button");
    copyButton.type = "button";
    copyButton.className = "copy-search-link";
    copyButton.textContent = "複製搜尋連結";
    copyButton.hidden = true;
    copyButton.addEventListener("click", async () => {
      const originalText = copyButton.textContent;
      try {
        const siteRoot = new URL(document.body.dataset.siteRoot || "./", document.baseURI).href;
        const text = searchStateUrl({ q: input.value, type: selectedType }, siteRoot);
        if (navigator.clipboard && navigator.clipboard.writeText) {
          await navigator.clipboard.writeText(text);
        } else if (globalThis.SiteUtils && globalThis.SiteUtils.fallbackCopyText) {
          await globalThis.SiteUtils.fallbackCopyText(text);
        } else {
          throw new Error("No clipboard available");
        }
        copyButton.textContent = "已複製";
        setTimeout(() => { copyButton.textContent = originalText; }, 2000);
      } catch (err) {}
    });
    if (status.parentNode) {
      status.parentNode.insertBefore(copyButton, status.nextSibling);
    }

    const initialState = readSearchStateFromUrl(window.location.href);
    if (initialState.q && selectedScope === "all") {
      input.value = initialState.q;
      selectedType = initialState.type;
      for (const option of filterButtons) {
        option.setAttribute("aria-pressed", String(option.dataset.searchType === selectedType));
      }
    }

    function updateScopeButtons() {
      for (const option of scopeButtons) option.setAttribute("aria-pressed", String(option.dataset.searchScope === selectedScope));
    }

    function render() {
      const filtered = deduplicateAdjacentResults(filterMatches(currentMatches, selectedType));
      const shown = filtered.slice(0, visibleCount);
      const siteRoot = new URL(document.body.dataset.siteRoot || "./", document.baseURI);
      status.textContent = `找到 ${filtered.length} 筆結果，先顯示 ${shown.length} 筆。`;
      copyButton.hidden = selectedScope !== "all";
      const stateToPass = selectedScope === "all" ? { q: input.value, type: selectedType } : null;
      results.replaceChildren(...shown.map((result) => resultElement(result, siteRoot, stateToPass)));
      if (moreButton) moreButton.hidden = shown.length >= filtered.length;
    }

    async function run(historyMode = "push") {
      const query = input.value;
      visibleCount = resultLimit;
      if (moreButton) moreButton.hidden = true;
      if (searchAllButton) searchAllButton.hidden = true;
      if (!normalize(query)) {
        status.textContent = "請輸入搜尋文字。";
        results.replaceChildren();
        copyButton.hidden = true;
        if (selectedScope === "all" && historyMode !== "skip") {
          writeSearchStateToUrl({ q: "", type: "all" }, historyMode === "replace");
          document.title = window.__originalTitle || document.title;
        }
        return;
      }
      if (selectedScope === "all" && historyMode !== "skip") {
        writeSearchStateToUrl({ q: query, type: selectedType }, historyMode === "replace");
      }
      if (selectedScope === "all") {
        window.__originalTitle = window.__originalTitle || document.title;
        document.title = `${normalize(query)}｜搜尋｜農業信用保證業務作業手冊`;
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
          copyButton.hidden = true;
          return;
        }
        if (!currentMatches.length) {
          status.textContent = zeroResultMessage(query);
          results.replaceChildren();
          copyButton.hidden = true;
          return;
        }
        render();
      } catch (error) {
        status.textContent = "搜尋索引目前無法載入，請稍後再試或查閱完整PDF。";
        results.replaceChildren();
        copyButton.hidden = true;
      }
    }

    let lastRunQuery = null;
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      window.clearTimeout(timer);
      lastRunQuery = input.value;
      run("push");
    });
    input.addEventListener("input", () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        if (input.value === lastRunQuery) return;
        lastRunQuery = input.value;
        run("replace");
      }, 250);
    });
    for (const button of filterButtons) button.addEventListener("click", () => {
      selectedType = button.dataset.searchType;
      for (const option of filterButtons) option.setAttribute("aria-pressed", String(option === button));
      visibleCount = resultLimit;
      if (currentMatches.length) {
         if (selectedScope === "all" && normalize(input.value)) writeSearchStateToUrl({ q: input.value, type: selectedType }, false);
         render();
      } else {
         run("push");
      }
    });
    for (const button of scopeButtons) button.addEventListener("click", () => {
      selectedScope = button.dataset.searchScope;
      updateScopeButtons();
      run("push");
    });
    if (moreButton) moreButton.addEventListener("click", () => { visibleCount += resultLimit; render(); });
    if (searchAllButton) searchAllButton.addEventListener("click", () => {
      selectedScope = "all";
      updateScopeButtons();
      run("push");
    });

    window.addEventListener("popstate", () => {
      if (selectedScope !== "all") return;
      const state = readSearchStateFromUrl(window.location.href);
      if (input.value !== state.q || selectedType !== state.type) {
        input.value = state.q;
        selectedType = state.type;
        for (const option of filterButtons) {
          option.setAttribute("aria-pressed", String(option.dataset.searchType === selectedType));
        }
        run("skip");
      }
    });

    panel.__manualSearch = { input, run, setScopeAll: () => {
      selectedScope = "all";
      selectedType = "all";
      updateScopeButtons();
      for (const option of filterButtons) option.setAttribute("aria-pressed", String(option.dataset.searchType === "all"));
    } };
    if (initialState.q && selectedScope === "all") run("skip");
  }

  globalThis.ManualSearch = { highlightText, bodyMatchOffsets, buildContextText, cleanSnippetText, continuationNeeded, deduplicateAdjacentResults, diversify, filterMatches, filterRecordsByScope, findLogicalPassage, formNumber, queryConcepts, resultTarget, searchRecords, selectReadingSegment, selectReadingSegments, snippet, tokenizeQuery, zeroResultMessage, readSearchStateFromUrl, writeSearchStateToUrl, searchStateUrl, decorateResultUrlWithSearchState };
  if (typeof document !== "undefined") {
    document.querySelectorAll("[data-search]").forEach(attach);
    document.querySelectorAll("[data-keyword]").forEach((button) => button.addEventListener("click", () => {
      const panel = button.closest("section")?.querySelector("[data-search]") || document.querySelector("[data-search]");
      const search = panel?.__manualSearch;
      if (!search) return;
      search.input.value = button.dataset.keyword;
      if (search.setScopeAll) search.setScopeAll();
      search.input.focus();
      search.run("push");
    }));

    const state = readSearchStateFromUrl(window.location.href);
    const fromSearch = new URL(window.location.href).searchParams.get("fromSearch");
    if (fromSearch && state.q) {
      const returnLink = document.createElement("a");
      returnLink.className = "return-to-search";
      const siteRoot = new URL(document.body.dataset.siteRoot || "./", document.baseURI).href;
      returnLink.href = searchStateUrl(state, siteRoot) + "#manual-search";
      returnLink.textContent = `← 返回「${state.q}」搜尋結果`;

      const main = document.querySelector("main");
      const breadcrumb = document.querySelector(".breadcrumb");
      if (breadcrumb && breadcrumb.parentNode) {
        breadcrumb.parentNode.insertBefore(returnLink, breadcrumb.nextSibling);
      } else if (main) {
        main.prepend(returnLink);
      }
    }
  }
})();
