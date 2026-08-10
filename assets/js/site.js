(function () {
  "use strict";

  function initBackToTop() {
    let button = document.getElementById("back-to-top");
    if (!button) {
      button = document.createElement("button");
      button.type = "button";
      button.id = "back-to-top";
      button.className = "back-to-top";
      button.hidden = true;
      button.setAttribute("aria-label", "返回頁首");
      button.textContent = "回頂部";
      document.body.append(button);
    }

    function toggle() {
      if (window.scrollY > 400) {
        button.hidden = false;
        button.classList.add("is-visible");
      } else {
        button.hidden = true;
        button.classList.remove("is-visible");
      }
    }

    window.addEventListener("scroll", toggle, { passive: true });
    button.addEventListener("click", () => {
      const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      window.scrollTo({ top: 0, behavior: reduceMotion ? "auto" : "smooth" });
    });
    toggle();
  }

  function fallbackCopyText(text) {
    return new Promise((resolve, reject) => {
      const input = document.createElement("input");
      input.value = text;
      input.style.position = "fixed";
      input.style.opacity = "0";
      document.body.appendChild(input);
      input.select();
      try {
        const successful = document.execCommand("copy");
        document.body.removeChild(input);
        if (successful) resolve();
        else reject(new Error("execCommand failed"));
      } catch (err) {
        document.body.removeChild(input);
        reject(err);
      }
    });
  }

  function initCopyPageLinks() {
    document.addEventListener("click", async (event) => {
      const button = event.target.closest(".copy-page-link");
      if (!button) return;
      const anchor = button.dataset.pageAnchor;
      if (!anchor) return;
      const targetUrl = new URL(window.location.href);
      targetUrl.searchParams.delete("fromSearch");
      targetUrl.searchParams.delete("q");
      targetUrl.searchParams.delete("type");
      targetUrl.hash = `#${anchor}`;
      const textToCopy = targetUrl.href;

      const originalText = button.dataset.originalText || button.textContent;
      button.dataset.originalText = originalText;

      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          await navigator.clipboard.writeText(textToCopy);
        } else {
          await fallbackCopyText(textToCopy);
        }
        button.textContent = "已複製連結！";
        button.classList.add("is-copied");
        button.classList.remove("is-error");
        setTimeout(() => {
          button.textContent = originalText;
          button.classList.remove("is-copied");
        }, 2000);
      } catch (err) {
        button.textContent = "無法自動複製，請手動複製網址列";
        button.classList.add("is-error");
        button.classList.remove("is-copied");
        setTimeout(() => {
          button.textContent = originalText;
          button.classList.remove("is-error");
        }, 3000);
      }
    });
  }

  function isSearchLandingEligible(urlStr) {
    try {
      const url = new URL(urlStr, window.location.origin);
      return url.searchParams.get("fromSearch") === "1" && !!url.searchParams.get("q");
    } catch (e) {
      return false;
    }
  }

  function targetIdFromSearchLanding(urlStr) {
    try {
      const url = new URL(urlStr, window.location.origin);
      const hash = url.hash;
      if (hash && hash.startsWith("#pdf-page-")) {
        return hash;
      }
      return null;
    } catch (e) {
      return null;
    }
  }

  function initSearchLandingCue() {
    const currentUrl = window.location.href;
    if (isSearchLandingEligible(currentUrl)) {
      const hash = targetIdFromSearchLanding(currentUrl);
      if (hash) {
        try {
          const targetElement = document.querySelector(hash);
          if (targetElement && targetElement.classList.contains("page-card")) {
            if (targetElement.querySelector(".search-landing-note")) {
              return;
            }
            targetElement.classList.add("search-landing-target");
            const note = document.createElement("div");
            note.className = "search-landing-note";
            note.textContent = "搜尋結果定位至此";
            const header = targetElement.querySelector("h2, h3, h4, h5, h6");
            if (header && header.nextSibling) {
              targetElement.insertBefore(note, header.nextSibling);
            } else {
              targetElement.insertBefore(note, targetElement.firstChild);
            }
          }
        } catch (e) {
          // invalid hash no throw
        }
      }
    }
  }

  function initInPageSearchHighlight() {
    const currentUrl = window.location.href;
    if (!isSearchLandingEligible(currentUrl)) return;

    // Idempotency check
    if (document.querySelector(".reading-hit-nav")) return;

    const url = new URL(currentUrl);
    const q = url.searchParams.get("q");
    if (!q || !globalThis.ManualSearch || !globalThis.ManualSearch.findHighlightRanges) return;

    const queryInfo = globalThis.ManualSearch.tokenizeQuery(q);
    const terms = [queryInfo.phrase, ...queryInfo.words].filter(Boolean);
    if (!terms.length) return;

    const hitNodes = [];
    const containers = document.querySelectorAll(".page-card > .display-text");

    for (const container of containers) {
      const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null, false);
      const textNodes = [];
      let node;
      while ((node = walker.nextNode())) {
        if (node.parentNode && node.parentNode.tagName === "MARK" && node.parentNode.classList.contains("reading-hit")) continue;
        textNodes.push(node);
      }

      for (const textNode of textNodes) {
        const text = textNode.nodeValue;
        if (!text.trim()) continue;

        const matches = globalThis.ManualSearch.findHighlightRanges(text, terms);
        if (!matches.length) continue;

        const fragment = document.createDocumentFragment();
        let currentIndex = 0;
        for (const match of matches) {
          if (match.start > currentIndex) {
            fragment.appendChild(document.createTextNode(text.slice(currentIndex, match.start)));
          }
          const mark = document.createElement("mark");
          mark.className = "reading-hit";
          mark.textContent = text.slice(match.start, match.end);
          fragment.appendChild(mark);
          hitNodes.push(mark);
          currentIndex = match.end;
        }
        if (currentIndex < text.length) {
          fragment.appendChild(document.createTextNode(text.slice(currentIndex)));
        }
        textNode.parentNode.replaceChild(fragment, textNode);
      }
    }

    if (!hitNodes.length) return;

    const navBar = document.createElement("div");
    navBar.className = "reading-hit-nav";
    navBar.setAttribute("role", "region");
    navBar.setAttribute("aria-label", "搜尋命中導覽");

    const counter = document.createElement("span");
    counter.className = "reading-hit-count";

    const prevBtn = document.createElement("button");
    prevBtn.type = "button";
    prevBtn.className = "reading-hit-prev";
    prevBtn.textContent = "上一個";
    prevBtn.setAttribute("aria-label", "上一個命中");

    const nextBtn = document.createElement("button");
    nextBtn.type = "button";
    nextBtn.className = "reading-hit-next";
    nextBtn.textContent = "下一個";
    nextBtn.setAttribute("aria-label", "下一個命中");

    const controls = document.createElement("div");
    controls.className = "reading-hit-controls";
    controls.appendChild(prevBtn);
    controls.appendChild(counter);
    controls.appendChild(nextBtn);
    navBar.appendChild(controls);

    const mainContainer = document.querySelector("main") || document.body;
    mainContainer.appendChild(navBar);

    let currentHitIndex = 0;

    function updateActiveHit(index) {
      if (hitNodes[currentHitIndex]) {
        hitNodes[currentHitIndex].classList.remove("reading-hit-current");
      }
      currentHitIndex = index;

      const activeNode = hitNodes[currentHitIndex];
      activeNode.classList.add("reading-hit-current");
      counter.textContent = `${currentHitIndex + 1} / ${hitNodes.length}`;

      prevBtn.disabled = currentHitIndex === 0;
      nextBtn.disabled = currentHitIndex === hitNodes.length - 1;

      const rect = activeNode.getBoundingClientRect();
      const scrollY = window.scrollY + rect.top - (window.innerHeight / 2);
      window.scrollTo({ top: scrollY, behavior: "smooth" });
    }

    prevBtn.addEventListener("click", () => {
      if (currentHitIndex > 0) updateActiveHit(currentHitIndex - 1);
    });

    nextBtn.addEventListener("click", () => {
      if (currentHitIndex < hitNodes.length - 1) updateActiveHit(currentHitIndex + 1);
    });

    setTimeout(() => {
      const hash = targetIdFromSearchLanding(currentUrl);
      let targetIndex = 0;
      if (hash) {
        const targetElement = document.querySelector(hash);
        if (targetElement) {
          const firstHitIndex = hitNodes.findIndex(node => {
            const card = node.closest(".page-card");
            if (!card) return false;
            const pos = targetElement.compareDocumentPosition(card);
            return card === targetElement || (pos & Node.DOCUMENT_POSITION_FOLLOWING);
          });
          if (firstHitIndex !== -1) {
            targetIndex = firstHitIndex;
          }
        }
      }
      updateActiveHit(targetIndex);
    }, 100);
  }

  globalThis.SiteUtils = { fallbackCopyText, isSearchLandingEligible, targetIdFromSearchLanding, initSearchLandingCue, initInPageSearchHighlight };
  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", () => {
        initBackToTop();
        initCopyPageLinks();
        initSearchLandingCue();
        initInPageSearchHighlight();
      });
    } else {
      initBackToTop();
      initCopyPageLinks();
      initSearchLandingCue();
      initInPageSearchHighlight();
    }
  }
})();
