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
      (document.querySelector(".site-footer") || document.body).append(button);
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

  function resolveSearchLandingHost(targetElement) {
    if (!targetElement) return null;
    if (targetElement.classList && targetElement.classList.contains("page-card")) {
      return targetElement;
    }
    if (targetElement.classList && targetElement.classList.contains("source-page-anchor")) {
      return targetElement.closest("p") || targetElement.nextElementSibling;
    }
    return targetElement;
  }

  function initSearchLandingCue() {
    const currentUrl = window.location.href;
    if (isSearchLandingEligible(currentUrl)) {
      const hash = targetIdFromSearchLanding(currentUrl);
      if (hash) {
        try {
          const targetElement = document.querySelector(hash);
          if (targetElement) {
            const landingHost = resolveSearchLandingHost(targetElement);
            if (landingHost) {
              if (document.querySelector(".search-landing-note")) {
                return;
              }
              landingHost.classList.add("search-landing-target");
              const note = document.createElement("div");
              note.className = "search-landing-note";
              note.textContent = "搜尋結果定位至此";
              const header = landingHost.querySelector ? landingHost.querySelector("h2, h3, h4, h5, h6") : null;
              if (header && header.nextSibling) {
                landingHost.insertBefore(note, header.nextSibling);
              } else if (landingHost.classList && landingHost.classList.contains("page-card")) {
                landingHost.insertBefore(note, landingHost.firstChild);
              } else if (landingHost.parentNode) {
                landingHost.parentNode.insertBefore(note, landingHost);
              }
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
    const containers = document.querySelectorAll(".page-card > .display-text, .continuous-source-heading, .continuous-source-text.display-text");

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
      const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      window.scrollTo({ top: scrollY, behavior: reduceMotion ? "auto" : "smooth" });
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
            if (targetElement.contains(node)) return true;
            const pos = targetElement.compareDocumentPosition(node);
            return Boolean(pos & Node.DOCUMENT_POSITION_FOLLOWING);
          });
          if (firstHitIndex !== -1) {
            targetIndex = firstHitIndex;
          }
        }
      }
      updateActiveHit(targetIndex);
    }, 100);
  }

  // Presentation-only navigation. Native details keeps a usable menu without JS.
  function initGlobalMenu() {
    const menu = document.querySelector("details.global-menu");
    if (!menu) return;
    const desktop = window.matchMedia("(min-width: 900px)");
    const sync = () => { menu.open = desktop.matches; };
    sync();
    if (desktop.addEventListener) desktop.addEventListener("change", sync);
    else desktop.addListener(sync);
    menu.addEventListener("click", (event) => {
      if (!desktop.matches && event.target.closest("a")) menu.open = false;
    });
    document.addEventListener("keydown", (event) => {
      if (event.key !== "Escape" || event.isComposing || !menu.open || desktop.matches || document.querySelector("dialog[open]")) return;
      menu.open = false;
      menu.querySelector("summary")?.focus();
    });
  }

  function initSectionNavigation() {
    const menus = [...document.querySelectorAll(".section-nav > details")];
    if (!menus.length) return;
    const desktop = window.matchMedia("(min-width: 900px)");
    const sync = () => { menus.forEach(menu => { menu.open = desktop.matches; }); };
    sync();
    if (desktop.addEventListener) desktop.addEventListener("change", sync);
    else desktop.addListener(sync);
  }

  function initSourcePreviewFallbacks() {
    for (const image of document.querySelectorAll("img.source-preview-image")) {
      const showError = () => {
        const figure = image.closest("figure");
        if (!figure || figure.querySelector(".source-preview-error")) return;
        image.hidden = true;
        const message = document.createElement("p");
        message.className = "source-preview-error";
        message.setAttribute("role", "status");
        message.textContent = "原頁預覽暫時無法載入。請使用下方「開啟原始PDF此頁」核對正式來源。";
        figure.append(message);
      };
      image.addEventListener("error", showError, { once: true });
      if (image.complete && !image.naturalWidth) showError();
    }
  }

  function initReadingWorkspace() {
    const tools = document.querySelector("[data-reading-tools]");
    const drawer = document.querySelector("dialog.reading-drawer");
    const content = drawer?.querySelector("[data-reading-drawer-content]");
    const title = drawer?.querySelector("#reading-drawer-title");
    if (!tools || !drawer || !content || !title || !drawer.showModal) return;

    const desktop = window.matchMedia("(min-width: 1280px)");
    const cache = new Map();
    let activeTool = "";
    let lastTrigger = null;
    let requestVersion = 0;
    let closePosition = null;
    let navigationDestination = null;
    let anchoringSuppressed = false;
    let previousAnchoring = "";
    tools.hidden = false;
    const sizeMenu = tools.querySelector("details.reading-size");
    const wideTools = window.matchMedia("(min-width: 600px)");
    const syncSizeMenu = () => { if (sizeMenu) sizeMenu.open = wideTools.matches; };
    syncSizeMenu();
    if (wideTools.addEventListener) wideTools.addEventListener("change", syncSizeMenu);
    else wideTools.addListener(syncSizeMenu);

    let keyboardNavigation = false;
    document.addEventListener("keydown", event => {
      if (event.key !== "Tab") return;
      keyboardNavigation = true;
      document.documentElement.classList.add("keyboard-navigation");
      window.scrollTo({ left: window.scrollX, top: window.scrollY, behavior: "instant" });
    });
    document.addEventListener("pointerdown", () => {
      keyboardNavigation = false;
      document.documentElement.classList.remove("keyboard-navigation");
    }, { passive: true });
    document.addEventListener("focusin", event => {
      const target = event.target.closest?.("a, button, input, select, textarea, summary");
      if (desktop.matches || !keyboardNavigation || !target || target.closest("dialog") || tools.contains(target)) return;
      const focusRect = target.getBoundingClientRect();
      const toolsRect = tools.getBoundingClientRect();
      const overlapsHorizontally = focusRect.right > toolsRect.left && focusRect.left < toolsRect.right;
      if (overlapsHorizontally && focusRect.bottom > toolsRect.top && focusRect.top < toolsRect.bottom) {
        window.scrollBy({ top: focusRect.bottom - toolsRect.top + 8, behavior: "instant" });
      }
    });

    function captureReadingPosition() {
      const paragraphs = [...document.querySelectorAll(".manual-content .display-text p")];
      const fallback = [...document.querySelectorAll(".manual-content .page-card, main .page-card")];
      const node = [...paragraphs, ...fallback].find(element => {
        const rect = element.getBoundingClientRect();
        return rect.bottom > 0 && rect.top < window.innerHeight;
      });
      return node ? { node, top: node.getBoundingClientRect().top } : null;
    }

    function suppressScrollAnchoring() {
      if (anchoringSuppressed) return;
      previousAnchoring = document.body.style.overflowAnchor;
      document.body.style.overflowAnchor = "none";
      anchoringSuppressed = true;
    }

    function releaseScrollAnchoring() {
      document.body.style.overflowAnchor = previousAnchoring;
      anchoringSuppressed = false;
    }

    function restoreReadingPosition(position, complete) {
      if (!position) { complete?.(); return; }
      let frames = 0;
      const adjust = () => {
        if (!position.node.isConnected) return;
        const difference = position.node.getBoundingClientRect().top - position.top;
        if (Math.abs(difference) > 1) window.scrollBy({ top: difference, behavior: "instant" });
        if (++frames < 2) requestAnimationFrame(adjust);
        else complete?.();
      };
      requestAnimationFrame(adjust);
    }

    function syncToolsLocation() {
      const sidebar = document.querySelector(".section-nav");
      if (desktop.matches && sidebar) sidebar.append(tools);
      else document.body.append(tools);
      syncToolbarClearance();
    }
    function syncToolbarClearance() {
      const clearance = desktop.matches ? 0 : Math.ceil(tools.getBoundingClientRect().height) + 24;
      document.documentElement.style.setProperty("--reading-toolbar-clearance", `${clearance}px`);
    }
    syncToolsLocation();
    if (window.ResizeObserver) {
      new ResizeObserver(syncToolbarClearance).observe(tools);
    } else {
      window.addEventListener("resize", syncToolbarClearance, { passive: true });
      tools.addEventListener("toggle", () => requestAnimationFrame(syncToolbarClearance), true);
    }

    function setReadingSize(size) {
      const allowed = [18, 20, 22, 24];
      const value = allowed.includes(Number(size)) ? Number(size) : 20;
      document.documentElement.style.setProperty("--reading-font-size", `${value}px`);
      document.documentElement.dataset.readingSize = String(value);
      for (const button of tools.querySelectorAll("[data-reading-size]")) {
        button.setAttribute("aria-pressed", String(Number(button.dataset.readingSize) === value));
      }
      const output = tools.querySelector("[data-reading-size-label]");
      if (output) output.textContent = `${value}px`;
      return value;
    }

    let savedSize = 20;
    try { savedSize = Number(localStorage.getItem("manual-reading-size")) || 20; } catch (error) {}
    setReadingSize(savedSize);
    tools.addEventListener("click", (event) => {
      const button = event.target.closest("[data-reading-size]");
      if (!button) return;
      const value = setReadingSize(button.dataset.readingSize);
      try { localStorage.setItem("manual-reading-size", String(value)); } catch (error) {}
    });

    function text(tag, className, value) {
      const node = document.createElement(tag);
      if (className) node.className = className;
      node.textContent = value;
      return node;
    }

    function close(restorePosition = true) {
      closePosition = restorePosition === false ? null : captureReadingPosition();
      requestVersion += 1;
      drawer.close();
    }

    drawer.addEventListener("close", () => {
      if (drawer.open) return;
      document.body.classList.remove("reading-workspace-open");
      tools.querySelectorAll("[data-reading-open]").forEach(button => button.setAttribute("aria-expanded", "false"));
      const destination = navigationDestination;
      navigationDestination = null;
      if (destination && destination.getAttribute("aria-hidden") !== "true") {
        const hadTabindex = destination.hasAttribute("tabindex");
        if (!hadTabindex) {
          destination.setAttribute("tabindex", "-1");
          destination.addEventListener("blur", () => destination.removeAttribute("tabindex"), { once: true });
        }
        destination.focus({ preventScroll: true });
      } else {
        lastTrigger?.focus({ preventScroll: true });
      }
      restoreReadingPosition(closePosition, () => { if (!drawer.open) releaseScrollAnchoring(); });
      closePosition = null;
    });
    drawer.addEventListener("cancel", () => {
      closePosition = captureReadingPosition();
      requestVersion += 1;
    });
    drawer.querySelector("[data-reading-close]")?.addEventListener("click", close);
    drawer.addEventListener("click", (event) => {
      if (event.target !== drawer || desktop.matches) return;
      const rect = drawer.getBoundingClientRect();
      if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) close();
    });
    drawer.addEventListener("keydown", event => {
      if (event.key !== "Tab" || event.isComposing || !drawer.matches(":modal")) return;
      const focusable = [...drawer.querySelectorAll("a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), summary, [tabindex]:not([tabindex='-1'])")]
        .filter(node => node.getClientRects().length && getComputedStyle(node).visibility !== "hidden");
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && drawer.open && desktop.matches && !event.isComposing) {
        event.preventDefault();
        close();
      }
    });

    function linkList(links, className) {
      const list = document.createElement("ul");
      list.className = className;
      for (const source of links) {
        const li = document.createElement("li");
        const link = document.createElement("a");
        link.href = source.href;
        link.textContent = source.textContent.trim();
        if (source.getAttribute("aria-current")) link.setAttribute("aria-current", source.getAttribute("aria-current"));
        link.addEventListener("click", () => {
          if (desktop.matches) return;
          const destination = new URL(link.href, document.baseURI);
          navigationDestination = destination.origin === window.location.origin && destination.pathname === window.location.pathname && destination.hash
            ? document.getElementById(destination.hash.slice(1)) : null;
          close(false);
        });
        li.append(link);
        list.append(li);
      }
      return list;
    }

    function renderContents() {
      const local = document.querySelector(".topic-toc");
      const section = document.querySelector(".section-nav");
      const localLinks = local ? [...local.querySelectorAll("a")] : [];
      const sectionLinks = section ? [...section.querySelectorAll("a")] : [];
      content.replaceChildren();
      if (localLinks.length) {
        content.append(text("h3", "workspace-section-title", "本規定目錄"), linkList(localLinks, "workspace-link-list"));
      }
      if (sectionLinks.length) {
        content.append(text("h3", "workspace-section-title", "同篇章節"), linkList(sectionLinks, "workspace-link-list"));
      }
      if (!localLinks.length && !sectionLinks.length) {
        const pageLinks = [...document.querySelectorAll(".manual-content .page-card[id], main > .page-card[id]")].map(page => {
          const link = document.createElement("a");
          link.href = `#${page.id}`;
          link.textContent = page.querySelector("h2, h3")?.textContent.trim() || page.id;
          return link;
        });
        if (pageLinks.length) content.append(linkList(pageLinks, "workspace-link-list"));
        else content.append(text("p", "workspace-empty", "此頁沒有章內目錄，可使用頁面底部的章節導覽。"));
      }
    }

    function renderForms() {
      const section = document.querySelector(".related-forms, .related-rules");
      const links = section ? [...section.querySelectorAll("a")] : [];
      content.replaceChildren();
      if (links.length) {
        const heading = section.querySelector("h2")?.textContent || "相關書表與規定";
        content.append(text("p", "workspace-context", heading), linkList(links, "workspace-link-list"));
      } else {
        content.append(text("p", "workspace-empty", "本頁沒有手冊明文確認的相關書表配對。"));
        const formIndex = document.querySelector('nav[aria-label="主要導覽"] a[data-nav="forms"]');
        if (formIndex) content.append(linkList([formIndex], "workspace-link-list"));
      }
    }

    function sourcePages() {
      const entries = new Map();
      for (const element of document.querySelectorAll(".source-page-link, [data-source-page-url]")) {
        const href = element.dataset.sourcePageUrl || element.getAttribute("href");
        if (!href) continue;
        const url = new URL(href, document.baseURI);
        if (url.origin !== window.location.origin || !url.hash.startsWith("#pdf-page-")) continue;
        if (entries.has(url.href)) continue;
        const anchor = document.getElementById(url.hash.slice(1));
        const card = element.closest(".page-card");
        const label = element.classList.contains("source-page-link")
          ? element.textContent.trim()
          : card?.querySelector("h2, h3")?.textContent.trim() || "查看原始實體頁";
        entries.set(url.href, { url, label, anchor });
      }
      return [...entries.values()];
    }

    function selectedSource(pages) {
      let selected = 0;
      let found = false;
      for (const [index, page] of pages.entries()) {
        if (page.anchor && page.anchor.getBoundingClientRect().top <= window.innerHeight / 2) {
          selected = index;
          found = true;
        }
      }
      if (!found) {
        const matching = pages.findIndex(page => page.url.hash === window.location.hash);
        if (matching >= 0) return matching;
      }
      return selected;
    }

    async function loadSource(source, host, version) {
      host.replaceChildren(text("p", "workspace-loading", "正在載入原始頁面…"));
      host.setAttribute("aria-busy", "true");
      try {
        const key = new URL(source.url.href);
        key.hash = "";
        key.search = "";
        if (!cache.has(key.href)) {
          const promise = fetch(key.href).then(response => {
            if (!response.ok) throw new Error(`Source response ${response.status}`);
            return response.text();
          });
          cache.set(key.href, promise);
          promise.catch(() => { cache.delete(key.href); });
        }
        const markup = await cache.get(key.href);
        if (version !== requestVersion || !drawer.open || activeTool !== "source") return;
        const parsed = new DOMParser().parseFromString(markup, "text/html");
        const card = parsed.getElementById(source.url.hash.slice(1));
        if (!card) throw new Error("Source page not found");
        host.replaceChildren(text("p", "workspace-source-meta", card.querySelector("h2, h3")?.textContent.trim() || source.label));
        const existingImage = card.querySelector("img.source-preview-image");
        const existingPdf = [...card.querySelectorAll("a[href]")].find(link => /\.pdf(?:#|\?|$)/i.test(link.getAttribute("href")));
        if (existingImage) {
          const figure = document.createElement("figure");
          figure.className = "workspace-source-preview";
          const image = document.createElement("img");
          image.src = new URL(existingImage.getAttribute("src"), key).href;
          image.alt = existingImage.getAttribute("alt") || source.label;
          image.width = Number(existingImage.getAttribute("width"));
          image.height = Number(existingImage.getAttribute("height"));
          image.loading = "lazy";
          image.decoding = "async";
          image.addEventListener("error", () => {
            image.hidden = true;
            figure.append(text("p", "workspace-error", "原頁影像暫時無法載入，請開啟原始PDF核對。"));
          }, { once: true });
          figure.append(image);
          host.append(figure);
        } else {
          host.append(text("p", "workspace-context", "此來源頁未提供原頁影像，請開啟原始PDF核對；下列為既有文字層。"));
        }
        const raw = card.querySelector(".source-text-raw, .source-text-secondary");
        if (raw) {
          const details = document.createElement("details");
          details.className = "workspace-source-text";
          const summary = text("summary", "", "查看PDF原始文字層");
          details.append(summary, text("pre", "source-text", raw.textContent));
          host.append(details);
        }
        const actions = document.createElement("div");
        actions.className = "workspace-source-actions";
        const physical = document.createElement("a");
        physical.href = source.url.href;
        physical.textContent = "開啟完整原始頁面";
        actions.append(physical);
        if (existingPdf) {
          const pdf = document.createElement("a");
          pdf.href = new URL(existingPdf.getAttribute("href"), key).href;
          pdf.target = "_blank";
          pdf.rel = "noopener noreferrer";
          pdf.textContent = "開啟原始PDF此頁 ↗";
          actions.append(pdf);
        }
        host.insertBefore(actions, host.children[1] || null);
      } catch (error) {
        if (version !== requestVersion || !drawer.open || activeTool !== "source") return;
        host.replaceChildren(text("p", "workspace-error", "原始頁面暫時無法載入。可使用下方入口查看完整來源。"));
        const fallback = document.createElement("a");
        fallback.href = source.url.href;
        fallback.textContent = "開啟原始頁面與PDF來源";
        host.append(fallback);
        const pdf = document.querySelector('a[href*=".pdf"]');
        if (pdf) {
          const link = document.createElement("a");
          link.href = pdf.href;
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          link.textContent = "開啟完整PDF ↗";
          host.append(link);
        }
      } finally {
        if (version === requestVersion) host.setAttribute("aria-busy", "false");
      }
    }

    function renderSource() {
      const pages = sourcePages();
      content.replaceChildren();
      if (!pages.length) {
        content.append(text("p", "workspace-empty", "請使用正文中保留的原始PDF與實體頁入口核對來源。"));
        return;
      }
      const context = desktop.matches
        ? "原始頁面與目前正文並列，閱讀位置保持不變。"
        : "核對目前正文的原始來源；關閉工具後回到原閱讀位置。";
      content.append(text("p", "workspace-context", context));
      const list = document.createElement("nav");
      list.className = "workspace-source-pages";
      list.setAttribute("aria-label", "選擇原始頁面");
      const preview = document.createElement("div");
      preview.className = "workspace-source-body";
      preview.setAttribute("aria-live", "polite");
      const buttons = pages.map((source, index) => {
        const button = text("button", "workspace-source-select", source.label);
        button.type = "button";
        button.addEventListener("click", () => select(index));
        list.append(button);
        return button;
      });
      function select(index) {
        buttons.forEach((button, i) => button.setAttribute("aria-pressed", String(i === index)));
        const version = ++requestVersion;
        loadSource(pages[index], preview, version);
      }
      content.append(list, preview);
      select(selectedSource(pages));
    }

    function open(tool, trigger) {
      const position = captureReadingPosition();
      suppressScrollAnchoring();
      if (drawer.open) drawer.close();
      activeTool = tool;
      lastTrigger = trigger;
      title.textContent = { contents: "閱讀目錄", forms: "相關書表與規定", source: "核對原始來源" }[tool] || "閱讀工具";
      drawer.classList.remove("is-contents", "is-forms", "is-source");
      drawer.classList.add(`is-${tool}`);
      document.body.classList.add("reading-workspace-open");
      if (desktop.matches) drawer.show();
      else drawer.showModal();
      tools.querySelectorAll("[data-reading-open]").forEach(button => button.setAttribute("aria-expanded", String(button === trigger)));
      if (tool === "contents") renderContents();
      else if (tool === "forms") renderForms();
      else renderSource();
      drawer.querySelector("[data-reading-close]")?.focus({ preventScroll: true });
      restoreReadingPosition(position);
    }

    tools.querySelectorAll("[data-reading-open]").forEach(button => {
      button.setAttribute("aria-controls", drawer.id);
      button.setAttribute("aria-expanded", "false");
      button.addEventListener("click", () => {
        const tool = button.dataset.readingOpen;
        if (drawer.open && activeTool === tool) close();
        else open(tool, button);
      });
    });
    const syncMode = () => {
      const position = captureReadingPosition();
      syncToolsLocation();
      if (drawer.open) open(activeTool, lastTrigger);
      restoreReadingPosition(position);
    };
    if (desktop.addEventListener) desktop.addEventListener("change", syncMode);
    else desktop.addListener(syncMode);
  }

  globalThis.SiteUtils = { fallbackCopyText, isSearchLandingEligible, targetIdFromSearchLanding, resolveSearchLandingHost, initSearchLandingCue, initInPageSearchHighlight };
  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", () => {
        initGlobalMenu();
        initSectionNavigation();
        initReadingWorkspace();
        initSourcePreviewFallbacks();
        initBackToTop();
        initCopyPageLinks();
        initSearchLandingCue();
        initInPageSearchHighlight();
      });
    } else {
      initGlobalMenu();
      initSectionNavigation();
      initReadingWorkspace();
      initSourcePreviewFallbacks();
      initBackToTop();
      initCopyPageLinks();
      initSearchLandingCue();
      initInPageSearchHighlight();
    }
  }
})();
