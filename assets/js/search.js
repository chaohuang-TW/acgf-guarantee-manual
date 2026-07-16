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

  const siteRoot = new URL(document.body.dataset.siteRoot || "./", document.baseURI);
  const indexUrl = new URL(document.body.dataset.searchIndex, document.baseURI);
  let indexPromise;

  function loadIndex() {
    if (!indexPromise) {
      indexPromise = fetch(indexUrl).then((response) => {
        if (!response.ok) throw new Error("搜尋索引載入失敗");
        return response.json();
      });
    }
    return indexPromise;
  }

  function snippet(original, query) {
    const haystack = normalize(original);
    const needle = normalize(query);
    const position = haystack.indexOf(needle);
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
        const records = await loadIndex();
        const matches = records.filter((record) => normalize(record.text).includes(query));
        status.textContent = `找到 ${matches.length} 筆結果，先顯示 ${Math.min(50, matches.length)} 筆。`;
        results.innerHTML = matches.slice(0, 50).map((record) => `
          <article class="search-result">
            <h3><a href="${escapeHtml(new URL(record.url, siteRoot).href)}">${escapeHtml(record.title)}</a></h3>
            <p class="result-path">${escapeHtml(record.breadcrumb.join(" › "))}</p>
            <p>${escapeHtml(snippet(record.text, query))}</p>
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

  document.querySelectorAll("[data-search]").forEach(attach);
})();
