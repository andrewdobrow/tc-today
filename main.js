// -- HERO EXPAND / COLLAPSE (grid cards link out, only heroes expand) --
function toggleExpand(btn) {
  const container = btn.closest(".hero");
  if (container) expandContainer(container);
}

function expandContainer(container) {
  const expand = container.querySelector(".article-expand");
  if (!expand) return;
  const summary = container.querySelector(".hero-summary");
  const foot    = container.querySelector(".hero-foot");
  const btn     = container.querySelector(".expand-btn");
  const isOpen  = expand.classList.contains("open");

  if (isOpen) {
    collapseContainer(container);
  } else {
    container.dataset.scrollTarget = window.pageYOffset + container.getBoundingClientRect().top - 70;
    expand.classList.add("open");
    if (summary) summary.style.display = "none";
    if (foot)    foot.style.display    = "none";
    if (btn)     btn.innerHTML = "Close &uarr;";
    setTimeout(() => expand.scrollIntoView({ behavior: "smooth", block: "nearest" }), 50);
  }
}

function collapseContainer(container) {
  const expand  = container.querySelector(".article-expand");
  const summary = container.querySelector(".hero-summary");
  const foot    = container.querySelector(".hero-foot");
  const btn     = container.querySelector(".expand-btn");

  expand.classList.remove("open");
  if (summary) summary.style.display = "";
  if (foot)    foot.style.display    = "";
  if (btn)     btn.innerHTML = "Continue reading &darr;";

  const target = parseFloat(container.dataset.scrollTarget);
  if (!isNaN(target)) {
    requestAnimationFrame(() => {
      window.scrollTo({ top: Math.max(0, target), behavior: "auto" });
    });
  }
}

function collapseThis(collapseBtn) {
  collapseContainer(collapseBtn.closest(".hero"));
}

// Clicking a hero (not a button/link) toggles it. Grid cards are <a> links so
// they navigate normally.
document.addEventListener("click", e => {
  if (e.target.closest("button, a")) return;
  const container = e.target.closest(".hero");
  if (!container) return;
  expandContainer(container);
});

// -- SHARE --
async function shareArticle(btn) {
  const headline = btn.dataset.headline || document.title;
  const url      = btn.dataset.url || window.location.href;
  const shareData = { title: headline, text: headline, url };
  try {
    if (navigator.share) {
      await navigator.share(shareData);
    } else {
      await navigator.clipboard.writeText(url);
      const orig = btn.innerHTML;
      btn.innerHTML = "Copied &#10003;";
      setTimeout(() => { btn.innerHTML = orig; }, 1500);
    }
  } catch (e) {}
}

// -- CATEGORY FILTER --
document.querySelectorAll(".cat-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    try {
      const cat = btn.dataset.cat;
      if (!cat) return; // Archive/Events are plain links

      document.querySelectorAll(".cat-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");

      const titles = {
        "all":          "Treasure Coast Today | Local News",
        "local_gov":    "Local Government — Treasure Coast Today",
        "crime":        "Crime & Safety — Treasure Coast Today",
        "business":     "Business — Treasure Coast Today",
        "sports":       "Sports — Treasure Coast Today",
        "things_to_do": "Things To Do — Treasure Coast Today",
        "florida":      "Florida — Treasure Coast Today",
        "martin":       "Martin County — Treasure Coast Today",
        "st_lucie":     "St. Lucie County — Treasure Coast Today",
        "indian_river": "Indian River County — Treasure Coast Today",
      };
      document.title = titles[cat] || "Treasure Coast Today";

      try {
        const newUrl = cat && cat !== "all"
          ? `${window.location.pathname}?cat=${cat}`
          : window.location.pathname;
        history.replaceState(null, "", newUrl);
      } catch (e) {}

      // Switch hero sections
      document.querySelectorAll("[data-cat-hero]").forEach(hero => {
        hero.style.display = hero.dataset.catHero === cat ? "block" : "none";
      });

      window.scrollTo({ top: 0, behavior: "smooth" });

      // Filter grid cards
      document.querySelectorAll(".grid-card").forEach(card => {
        if (card.classList.contains("support-grid-card")) return;
        let show;
        if (cat === "all") {
          show = card.dataset.topnews === "true";
        } else {
          const memberships = (card.dataset.cats || card.dataset.cat || "")
            .split(/\s+/)
            .filter(Boolean);
          show = memberships.includes(cat);
        }
        card.style.display = show ? "flex" : "none";
      });

      // Show only the active category's Older section. Top News shows none.
      document.querySelectorAll(".older-section").forEach(section => {
        section.style.display = (cat !== "all" && section.dataset.olderCat === cat)
          ? "block" : "none";
      });

      // Reposition support card to 5th visible slot
      const grid        = document.getElementById("articlesGrid");
      const supportCard = grid ? grid.querySelector(".support-grid-card") : null;
      if (supportCard && grid) {
        const visible = Array.from(grid.querySelectorAll(".grid-card:not(.support-grid-card)"))
          .filter(c => c.style.display !== "none");
        const insertAfter = visible.length >= 4 ? visible[3] : visible[visible.length - 1];
        if (insertAfter) insertAfter.insertAdjacentElement("afterend", supportCard);
        supportCard.style.display = "flex";
      }
    } catch (e) {
      console.error("Category filter error:", e);
    }
  });
});

// -- INITIAL STATE: show only Top News hero + deduped grid on load --
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".grid-card").forEach(card => {
    if (card.classList.contains("support-grid-card")) return;
    card.style.display = card.dataset.topnews === "true" ? "flex" : "none";
  });

  const params = new URLSearchParams(window.location.search);
  const catParam = params.get("cat");
  if (catParam) {
    const btn = document.querySelector(`.cat-btn[data-cat="${catParam}"]`);
    if (btn) btn.click();
  }
});


// -- RESPONSIVE KIT NEWSLETTER PRESENTATION --
// Use the compact sticky signup only on desktop. Mobile receives Kit's modal
// form instead, preventing a fixed signup bar from competing with the masthead.
(() => {
  const mobileQuery = window.matchMedia("(max-width: 680px)");
  const embeds = {
    desktop: {
      uid: "4edef44197",
      src: "https://treasure-coast-today.kit.com/4edef44197/index.js",
      mode: "desktop-sticky"
    },
    mobile: {
      uid: "be625cadfe",
      src: "https://treasure-coast-today.kit.com/be625cadfe/index.js",
      mode: "mobile-modal"
    }
  };
  const initialMobileState = mobileQuery.matches;

  function loadResponsiveKitForm() {
    const config = mobileQuery.matches ? embeds.mobile : embeds.desktop;
    if (document.querySelector(`script[data-uid="${config.uid}"]`)) return;

    const script = document.createElement("script");
    script.async = true;
    script.dataset.uid = config.uid;
    script.dataset.tctNewsletterMode = config.mode;
    script.src = config.src;
    document.body.appendChild(script);
  }

  // Defer one task so any legacy footer embed already in the parsed page can
  // be detected rather than duplicated. Newly generated pages contain no
  // hard-coded sticky or modal script.
  window.setTimeout(loadResponsiveKitForm, 0);

  const handleBreakpointChange = event => {
    if (event.matches !== initialMobileState) window.location.reload();
  };
  if (mobileQuery.addEventListener) {
    mobileQuery.addEventListener("change", handleBreakpointChange);
  } else if (mobileQuery.addListener) {
    mobileQuery.addListener(handleBreakpointChange);
  }
})();


// -- KIT STICKY BAR LAYERING --
// Kit injects the sticky form asynchronously and may wrap it in one or more
// positioned containers. Promote the actual top-level Kit container above the
// TCT masthead, reserve a fixed compact height, and keep the entire masthead
// stack below it while the form is visible.
(() => {
  const root = document.documentElement;
  const mobileQuery = window.matchMedia("(max-width: 680px)");
  let observedTarget = null;
  let resizeObserver = null;
  let rafId = 0;
  const promotedElements = new Set();
  const originalInlineStyles = new WeakMap();

  function setImportantStyle(element, property, value) {
    if (!element) return;
    let snapshot = originalInlineStyles.get(element);
    if (!snapshot) {
      snapshot = new Map();
      originalInlineStyles.set(element, snapshot);
    }
    if (!snapshot.has(property)) {
      snapshot.set(property, {
        value: element.style.getPropertyValue(property),
        priority: element.style.getPropertyPriority(property)
      });
    }
    promotedElements.add(element);
    if (element.style.getPropertyValue(property) === value &&
        element.style.getPropertyPriority(property) === "important") return;
    element.style.setProperty(property, value, "important");
  }

  function findStickyForm() {
    return document.querySelector('.formkit-form[data-format="sticky bar"]') ||
      document.querySelector(".formkit-sticky-bar");
  }

  function findTopLevelLayer(node) {
    if (!node) return null;
    let layer = node.closest(".formkit-sticky-bar") || node;
    while (layer.parentElement &&
           layer.parentElement !== document.body &&
           layer.parentElement !== document.documentElement) {
      layer = layer.parentElement;
    }
    if (layer === document.body || layer === document.documentElement) {
      return node.closest(".formkit-sticky-bar") || node;
    }
    return layer;
  }

  function elementIsVisible(element) {
    if (!element || !element.isConnected) return false;
    let current = element;
    while (current && current !== document.documentElement) {
      const style = window.getComputedStyle(current);
      if (style.display === "none" || style.visibility === "hidden" ||
          Number(style.opacity || 1) === 0) return false;
      current = current.parentElement;
    }
    const rect = element.getBoundingClientRect();
    return rect.width > 0 && (rect.height > 0 || element.scrollHeight > 0);
  }

  function clearPromotedLayer() {
    promotedElements.forEach(element => {
      element.classList.remove(
        "tct-kit-sticky-layer", "tct-kit-sticky-shell", "tct-kit-sticky-form"
      );
      const snapshot = originalInlineStyles.get(element);
      if (snapshot) {
        snapshot.forEach(({ value, priority }, property) => {
          if (value) element.style.setProperty(property, value, priority);
          else element.style.removeProperty(property);
        });
      }
      originalInlineStyles.delete(element);
    });
    promotedElements.clear();
  }

  function promoteStickyLayer(form) {
    const layer = findTopLevelLayer(form);
    if (!layer) return null;

    const height = mobileQuery.matches ? 58 : 72;
    layer.classList.add("tct-kit-sticky-layer");
    form.classList.add("tct-kit-sticky-form");

    // Neutralize every injected wrapper between the form and the promoted
    // body-level layer. A lower ancestor transform or clipping rule can trap a
    // high-z-index child beneath the masthead.
    let shell = form.parentElement;
    while (shell && shell !== layer && shell !== document.body) {
      shell.classList.add("tct-kit-sticky-shell");
      setImportantStyle(shell, "position", "relative");
      setImportantStyle(shell, "top", "auto");
      setImportantStyle(shell, "right", "auto");
      setImportantStyle(shell, "bottom", "auto");
      setImportantStyle(shell, "left", "auto");
      setImportantStyle(shell, "width", "100%");
      setImportantStyle(shell, "height", "100%");
      setImportantStyle(shell, "min-height", "0");
      setImportantStyle(shell, "max-height", `${height}px`);
      setImportantStyle(shell, "transform", "none");
      setImportantStyle(shell, "overflow", "visible");
      setImportantStyle(shell, "z-index", "2147483001");
      shell = shell.parentElement;
    }

    // Inline important declarations neutralize wrapper-level positioning and
    // transforms that can otherwise trap Kit beneath a site stacking context.
    const layerStyles = {
      position: "fixed",
      top: "0px",
      right: "0px",
      bottom: "auto",
      left: "0px",
      width: "100%",
      height: `${height}px`,
      "min-height": `${height}px`,
      "max-height": `${height}px`,
      "z-index": "2147483000",
      transform: "none",
      overflow: "visible",
      clip: "auto",
      isolation: "isolate",
      margin: "0px"
    };
    Object.entries(layerStyles).forEach(([property, value]) => {
      setImportantStyle(layer, property, value);
    });

    setImportantStyle(form, "position", "relative");
    setImportantStyle(form, "top", "auto");
    setImportantStyle(form, "bottom", "auto");
    setImportantStyle(form, "width", "100%");
    setImportantStyle(form, "height", "100%");
    setImportantStyle(form, "min-height", "0");
    setImportantStyle(form, "max-height", `${height}px`);
    setImportantStyle(form, "z-index", "2147483001");
    setImportantStyle(form, "transform", "none");
    setImportantStyle(form, "margin", "0");

    root.style.setProperty("--kit-sticky-height", `${height}px`);
    root.classList.add("kit-sticky-visible");
    return layer;
  }

  function syncStickyBarLayer() {
    rafId = 0;

    // The sticky presentation is desktop-only. On mobile, Kit's separate
    // modal embed owns newsletter acquisition and the masthead must retain
    // its normal top position.
    if (mobileQuery.matches) {
      if (resizeObserver) resizeObserver.disconnect();
      observedTarget = null;
      clearPromotedLayer();
      root.classList.remove("kit-sticky-visible");
      root.style.setProperty("--kit-sticky-height", "0px");
      return;
    }

    const form = findStickyForm();

    if (form !== observedTarget) {
      if (resizeObserver) resizeObserver.disconnect();
      clearPromotedLayer();
      observedTarget = form;
      if (form && "ResizeObserver" in window) {
        resizeObserver = new ResizeObserver(scheduleSync);
        resizeObserver.observe(form);
      }
    }

    if (!elementIsVisible(form)) {
      clearPromotedLayer();
      root.classList.remove("kit-sticky-visible");
      root.style.setProperty("--kit-sticky-height", "0px");
      return;
    }

    promoteStickyLayer(form);
  }

  function scheduleSync() {
    if (rafId) return;
    rafId = window.requestAnimationFrame(syncStickyBarLayer);
  }

  const observer = new MutationObserver(mutations => {
    const relevant = mutations.some(mutation => {
      if (mutation.type === "childList") return true;
      const target = mutation.target;
      return target instanceof Element && Boolean(
        target.matches('.formkit-sticky-bar, .formkit-sticky-bar *, .formkit-form[data-format="sticky bar"], .formkit-form[data-format="sticky bar"] *') ||
        target.closest('.formkit-sticky-bar, .formkit-form[data-format="sticky bar"]')
      );
    });
    if (relevant) scheduleSync();
  });

  function beginObservation() {
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["class", "style", "hidden"]
    });
    scheduleSync();
  }

  if (document.body) beginObservation();
  else document.addEventListener("DOMContentLoaded", beginObservation, { once: true });

  window.addEventListener("resize", scheduleSync, { passive: true });
  window.addEventListener("load", scheduleSync, { once: true });
  if (mobileQuery.addEventListener) {
    mobileQuery.addEventListener("change", scheduleSync);
  }
})();
