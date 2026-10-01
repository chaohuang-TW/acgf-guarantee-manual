/* Execution adapter only: import the one authoritative, unchanged search core. */
"use strict";
importScripts("search.js");
let records, concepts, intents;
self.addEventListener("message", event => {
  const job = event.data;
  if (job.records) ({ records, concepts, intents } = job);
  try {
    const result = self.ManualSearch.searchRecords(records, job.query, concepts, intents);
    for (const match of result.matches) {
      const record = match.record;
      const display = match.segment || record;
      const passage = (record.readingSegments || []).length > 1 ? null : self.ManualSearch.findLogicalPassage(record, match.matchedTerms, match.bodyMatches);
      const preview = passage ? passage.preview : self.ManualSearch.snippet(display.text || record.text, match.matchedTerms);
      match.uiPresentation = {
        passage, preview,
        titleRanges: self.ManualSearch.findHighlightRanges(display.title, match.matchedTerms),
        previewRanges: self.ManualSearch.findHighlightRanges(preview, match.matchedTerms),
        fullRanges: passage?.expanded ? self.ManualSearch.findHighlightRanges(passage.fullText, match.matchedTerms) : null,
      };
    }
    self.postMessage({ id: job.id, result });
  } catch (error) {
    self.postMessage({ id: job.id, error: String(error) });
  }
});
