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
// County-first navigation uses ordinary links so it remains fully functional
// without JavaScript. On the homepage only, links carrying data-cat switch the
// existing client-side news view instead of navigating away.
document.querySelectorAll(".category-nav [data-cat], .mobile-nav-panel [data-cat]").forEach(btn => {
  btn.addEventListener("click", (event) => {
    try {
      const homepageGrid = document.getElementById("articlesGrid");
      if (!homepageGrid) return;
      const cat = btn.dataset.cat;
      if (!cat) return;
      event.preventDefault();

      document.querySelectorAll(".category-nav [data-cat], .mobile-nav-panel [data-cat]").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".nav-sections-toggle").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      const sections = btn.closest(".nav-sections");
      if (sections) {
        const toggle = sections.querySelector(".nav-sections-toggle");
        if (toggle) toggle.classList.add("active");
        sections.removeAttribute("open");
      }

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
    const btn = document.querySelector(`.category-nav [data-cat="${catParam}"], .mobile-nav-panel [data-cat="${catParam}"]`);
    if (btn) btn.click();
  }
});


// -- MOBILE HAMBURGER NAVIGATION --
// Mobile uses a dedicated drawer instead of the horizontal category row.
// The desktop nav remains in the DOM and functional above 900px.
(() => {
  const mobileQuery = window.matchMedia("(max-width: 900px)");
  const toggle = document.querySelector(".mobile-nav-toggle-button");
  const panel = document.getElementById("tct-mobile-nav");
  if (!toggle || !panel) return;

  function setOpen(open, { restoreFocus = false } = {}) {
    const shouldOpen = Boolean(open && mobileQuery.matches);
    panel.hidden = !shouldOpen;
    toggle.setAttribute("aria-expanded", shouldOpen ? "true" : "false");
    toggle.setAttribute("aria-label", shouldOpen ? "Close navigation menu" : "Open navigation menu");
    document.documentElement.classList.toggle("mobile-nav-open", shouldOpen);
    if (!shouldOpen && restoreFocus) toggle.focus();
  }

  toggle.addEventListener("click", event => {
    event.preventDefault();
    setOpen(panel.hidden);
  });

  panel.addEventListener("click", event => {
    if (event.target.closest("a")) setOpen(false);
  });

  document.addEventListener("click", event => {
    if (panel.hidden || !mobileQuery.matches) return;
    if (panel.contains(event.target) || toggle.contains(event.target)) return;
    setOpen(false);
  });

  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && !panel.hidden) setOpen(false, { restoreFocus: true });
  });

  const syncViewport = () => {
    if (!mobileQuery.matches) setOpen(false);
  };
  if (mobileQuery.addEventListener) mobileQuery.addEventListener("change", syncViewport);
  else mobileQuery.addListener(syncViewport);
})();


// -- MOBILE MORE MENU --
// iOS Safari can require a second tap when :hover/:focus-within reveals a
// submenu before the native <details> click completes. On mobile, toggle the
// disclosure explicitly and preserve the horizontal category-strip position.
(() => {
  const mobileMoreQuery = window.matchMedia("(max-width: 900px)");
  const menus = Array.from(document.querySelectorAll(".nav-sections"));
  if (!menus.length) return;

  function positionMobileMenu(details) {
    const menu = details.querySelector(".nav-sections-menu");
    const row = details.closest(".masthead-nav-row");
    if (!menu) return;
    if (!mobileMoreQuery.matches || !details.open || !row) {
      menu.style.removeProperty("--mobile-more-top");
      return;
    }
    const rowBottom = Math.ceil(row.getBoundingClientRect().bottom);
    menu.style.setProperty("--mobile-more-top", `${rowBottom}px`);
  }

  menus.forEach(details => {
    const summary = details.querySelector(":scope > summary");
    if (!summary) return;

    summary.addEventListener("click", event => {
      if (!mobileMoreQuery.matches) return;

      event.preventDefault();
      const scroller = details.closest(".category-nav--primary");
      const savedScrollLeft = scroller ? scroller.scrollLeft : 0;
      const shouldOpen = !details.open;

      menus.forEach(other => {
        if (other !== details) other.removeAttribute("open");
      });

      details.open = shouldOpen;
      if (shouldOpen) positionMobileMenu(details);

      requestAnimationFrame(() => {
        if (scroller) scroller.scrollLeft = savedScrollLeft;
        if (details.open) positionMobileMenu(details);
      });
    });

    details.addEventListener("toggle", () => {
      if (details.open) positionMobileMenu(details);
    });
  });

  const repositionOpenMenu = () => {
    if (!mobileMoreQuery.matches) return;
    menus.forEach(details => {
      if (details.open) positionMobileMenu(details);
    });
  };

  window.addEventListener("resize", repositionOpenMenu, { passive: true });
  if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", repositionOpenMenu, { passive: true });
    window.visualViewport.addEventListener("scroll", repositionOpenMenu, { passive: true });
  }
})();

// Close the Sections menu when focus moves away by pointer or Escape. Native
// <details>/<summary> retains keyboard and no-JS behavior; these are progressive
// enhancements only.
document.addEventListener("click", (event) => {
  document.querySelectorAll(".nav-sections[open]").forEach(menu => {
    if (!menu.contains(event.target)) menu.removeAttribute("open");
  });
});

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  document.querySelectorAll(".nav-sections[open]").forEach(menu => {
    menu.removeAttribute("open");
    const toggle = menu.querySelector("summary");
    if (toggle) toggle.focus();
  });
});


// -- SITEWIDE KIT NEWSLETTER MODAL --
// Use one modal presentation on every viewport. The inline newsletter form remains
// embedded in article/category content, while the former sticky-bar embed is no
// longer loaded or given masthead offset behavior.
(() => {
  const config = {
    uid: "be625cadfe",
    src: "https://treasure-coast-today.kit.com/be625cadfe/index.js",
    mode: "sitewide-modal"
  };

  function loadSitewideKitModal() {
    if (document.querySelector(`script[data-uid="${config.uid}"]`)) return;

    const script = document.createElement("script");
    script.async = true;
    script.dataset.uid = config.uid;
    script.dataset.tctNewsletterMode = config.mode;
    script.src = config.src;
    document.body.appendChild(script);
  }

  // Defer one task so any legacy embed already present in a cached page can be
  // detected rather than initialized a second time.
  window.setTimeout(loadSitewideKitModal, 0);
})();
