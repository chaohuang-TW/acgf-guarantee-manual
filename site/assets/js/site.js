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

  globalThis.SiteUtils = { fallbackCopyText, isSearchLandingEligible, targetIdFromSearchLanding, initSearchLandingCue };
  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", () => {
        initBackToTop();
        initCopyPageLinks();
        initSearchLandingCue();
      });
    } else {
      initBackToTop();
      initCopyPageLinks();
      initSearchLandingCue();
    }
  }
})();
