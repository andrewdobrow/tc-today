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


// -- RESPONSIVE ACQUISITION MODAL --
// Desktop keeps the Kit Morning Brief modal. Mobile article traffic gets a
// simple subscription prompt after 5 seconds OR a short reading scroll. The
// monthly-free article is intentionally eligible: on mobile this modal replaces
// the old free-article sticky banner so the acquisition path is not suppressed.
(() => {
  const desktopKit = {
    uid: "be625cadfe",
    src: "https://treasure-coast-today.kit.com/be625cadfe/index.js",
    mode: "desktop-newsletter-modal"
  };
  const MOBILE_QUERY = "(max-width: 680px)";
  const MOBILE_DELAY_MS = 5000;
  const MOBILE_SCROLL_RATIO = 0.45;
  const MOBILE_DISMISS_KEY = "tct_mobile_subscription_modal_dismissed_until_v2";
  const MOBILE_DISMISS_MS = 7 * 24 * 60 * 60 * 1000;
  const MEMBER_HINT_KEY = "tct_member_entitled_hint";
  const METER_STATE_KEY = "tct_monthly_free_article_v1";
  const mobile = window.matchMedia(MOBILE_QUERY);

  function loadDesktopKitModal() {
    if (mobile.matches) return;
    if (document.querySelector(`script[data-uid="${desktopKit.uid}"]`)) return;
    const script = document.createElement("script");
    script.async = true;
    script.dataset.uid = desktopKit.uid;
    script.dataset.tctNewsletterMode = desktopKit.mode;
    script.src = desktopKit.src;
    document.body.appendChild(script);
  }

  function currentArticleSlug() {
    const match = window.location.pathname.match(/^\/articles\/([^/]+?)(?:\.html)?\/?$/i);
    return match ? match[1] : "";
  }

  function currentMeterPeriod() {
    try {
      const parts = new Intl.DateTimeFormat("en-US", { timeZone:"America/New_York", year:"numeric", month:"2-digit" }).formatToParts(new Date());
      const year = parts.find(part => part.type === "year")?.value || "";
      const month = parts.find(part => part.type === "month")?.value || "";
      return `${year}-${month}`;
    } catch {
      const now = new Date();
      return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
    }
  }

  function currentArticleIsMonthlyFree() {
    const slug = currentArticleSlug();
    if (!slug) return false;
    try {
      const state = JSON.parse(localStorage.getItem(METER_STATE_KEY) || "null");
      return Boolean(state && state.period === currentMeterPeriod() && state.slug === slug && !state.pending);
    } catch {
      return false;
    }
  }

  function paywallIsVisible() {
    const paywall = document.querySelector("[data-tct-paywall]");
    if (!paywall) return false;
    const rect = paywall.getBoundingClientRect();
    return rect.top < window.innerHeight && rect.bottom > 0;
  }

  function cooldownActive() {
    try { return Number(localStorage.getItem(MOBILE_DISMISS_KEY) || 0) > Date.now(); }
    catch { return false; }
  }

  function subscriberLikely() {
    if (document.body?.classList.contains("tct-member-entitled")) return true;
    try { return localStorage.getItem(MEMBER_HINT_KEY) === "1"; }
    catch { return false; }
  }

  function mobilePromptSuppressed() {
    if (!mobile.matches || !currentArticleSlug()) return true;
    if (subscriberLikely() || cooldownActive()) return true;
    // If the reader is already looking at the inline paywall, do not cover it
    // with a second sales surface. Monthly-free readers are still eligible while
    // they are reading because their paywall sits below the completed article.
    if (!currentArticleIsMonthlyFree() && paywallIsVisible()) return true;
    return false;
  }

  function dismissMobileSubscriptionModal(persistCooldown = true) {
    const overlay = document.querySelector("[data-tct-mobile-subscription-modal]");
    if (!overlay) return;
    if (persistCooldown) {
      try { localStorage.setItem(MOBILE_DISMISS_KEY, String(Date.now() + MOBILE_DISMISS_MS)); } catch {}
    }
    overlay.remove();
    document.documentElement.classList.remove("tct-mobile-subscription-open");
  }

  function showMobileSubscriptionModal() {
    if (document.querySelector("[data-tct-mobile-subscription-modal]") || mobilePromptSuppressed()) return false;
    const next = encodeURIComponent(window.location.pathname + window.location.search);
    const overlay = document.createElement("div");
    overlay.className = "tct-mobile-subscription-overlay";
    overlay.setAttribute("data-tct-mobile-subscription-modal", "true");
    overlay.innerHTML = `
      <section class="tct-mobile-subscription-modal" role="dialog" aria-modal="true" aria-labelledby="tct-mobile-subscription-title">
        <button class="tct-mobile-subscription-close" type="button" aria-label="Close subscription offer">&times;</button>
        <div class="tct-mobile-subscription-card">
          <div class="tct-mobile-subscription-regular-price">$4.99</div>
          <div class="tct-mobile-subscription-offer">$1 FOR THE FIRST MONTH</div>
          <h2 id="tct-mobile-subscription-title">Never miss another local story.</h2>
          <ul class="tct-mobile-subscription-benefits" aria-label="Subscription benefits">
            <li>Unlimited access to Treasure Coast news</li>
            <li>Read on any device</li>
            <li>Support local, independent journalism</li>
          </ul>
          <div class="tct-mobile-subscription-brand" aria-hidden="true">TCT</div>
          <a class="tct-mobile-subscription-cta" href="/subscribe.html?next=${next}">SUBSCRIBE NOW</a>
        </div>
        <div class="tct-mobile-subscription-after">$4.99/month after. Cancel anytime.</div>
        <a class="tct-mobile-subscription-signin" href="/subscribe.html?signin=1&next=${next}">Already a subscriber? Sign in</a>
      </section>`;
    document.body.appendChild(overlay);
    document.documentElement.classList.add("tct-mobile-subscription-open");
    overlay.querySelector(".tct-mobile-subscription-close")?.addEventListener("click", () => dismissMobileSubscriptionModal(true));
    overlay.addEventListener("click", event => { if (event.target === overlay) dismissMobileSubscriptionModal(true); });
    return true;
  }

  function armMobileSubscriptionModal() {
    if (!mobile.matches || !currentArticleSlug()) return;
    const startY = window.scrollY;
    let finished = false;
    let timer = null;
    let retryTimer = null;

    const cleanup = () => {
      if (timer !== null) window.clearTimeout(timer);
      if (retryTimer !== null) window.clearTimeout(retryTimer);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("keydown", onKeydown);
    };
    const attempt = () => {
      if (finished) return;
      if (showMobileSubscriptionModal()) {
        finished = true;
        cleanup();
        return;
      }
      // Membership state can settle shortly after main.js. Retry once rather
      // than letting a stale entitlement hint permanently kill the prompt.
      if (!cooldownActive() && mobile.matches && currentArticleSlug() && retryTimer === null) {
        retryTimer = window.setTimeout(() => {
          retryTimer = null;
          attempt();
        }, 1500);
      }
    };
    const onScroll = () => {
      if (Math.abs(window.scrollY - startY) >= Math.max(180, window.innerHeight * MOBILE_SCROLL_RATIO)) attempt();
    };
    const onKeydown = event => {
      if (event.key === "Escape" && document.querySelector("[data-tct-mobile-subscription-modal]")) dismissMobileSubscriptionModal(true);
    };

    window.addEventListener("scroll", onScroll, { passive:true });
    window.addEventListener("keydown", onKeydown);
    timer = window.setTimeout(attempt, MOBILE_DELAY_MS);
  }

  window.setTimeout(() => {
    loadDesktopKitModal();
    armMobileSubscriptionModal();
  }, 0);
})();

// -- FIRST-PARTY MOST READ (privacy-preserving aggregate counts) --
(() => {
  const endpointMeta = document.querySelector('meta[name="tct-story-analytics-endpoint"]');
  const endpoint = endpointMeta ? String(endpointMeta.content || '').trim() : '';
  const modules = Array.from(document.querySelectorAll('[data-tct-most-read]'));
  if (!endpoint) return;

  const post = (payload, options = {}) => fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    cache: 'no-store',
    credentials: 'omit',
    ...options
  });

  async function renderMostRead() {
    if (!modules.length) return;
    try {
      const [topResponse, indexResponse] = await Promise.all([
        post({ action: 'top', hours: 24, limit: 5 }),
        fetch('/data/story-index.json', { cache: 'no-store', credentials: 'same-origin' })
      ]);
      if (!topResponse.ok || !indexResponse.ok) return;
      const topPayload = await topResponse.json();
      const indexPayload = await indexResponse.json();
      if (!topPayload || topPayload.schema_ready !== true || !Array.isArray(topPayload.stories)) return;
      const index = indexPayload && indexPayload.stories ? indexPayload.stories : {};
      const rows = topPayload.stories.map(item => ({ ...item, meta: index[item.slug] })).filter(item => item.meta && item.meta.headline && item.meta.url);
      if (!rows.length) return;
      modules.forEach(module => {
        const list = module.querySelector('[data-tct-most-read-list]');
        if (!list) return;
        list.innerHTML = rows.map(item => `<li><a href="${String(item.meta.url).replace(/"/g, '&quot;')}"><span><span class="most-read-title">${String(item.meta.headline).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}</span><span class="most-read-meta">${String(item.meta.category || 'Local News').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}</span></span></a></li>`).join('');
        module.hidden = false;
      });
    } catch (_) {}
  }

  function recordArticleView() {
    const body = document.body;
    const slug = body && body.dataset ? String(body.dataset.articleSlug || '').trim() : '';
    if (!slug || !/^[a-z0-9][a-z0-9-]{5,180}$/.test(slug)) return;
    const key = `tct-story-viewed:${slug}`;
    try { if (sessionStorage.getItem(key) === '1') return; sessionStorage.setItem(key, '1'); } catch (_) {}
    window.setTimeout(() => {
      post({ action: 'record', slug }, { keepalive: true }).catch(() => {});
    }, 2500);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => { renderMostRead(); recordArticleView(); }, { once: true });
  } else {
    renderMostRead(); recordArticleView();
  }
})();

// -- SITEWIDE ARTICLE SEARCH --
// Lazy-load the compact story index only after the reader opens/searches. The
// same index powers the masthead overlay and the dedicated /search.html page.
(() => {
  const INDEX_URL = '/data/story-index.json';
  let indexPromise = null;

  const escapeHtml = value => String(value == null ? '' : value).replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[char]));

  const normalize = value => String(value == null ? '' : value)
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();

  function expandCommonTerms(query) {
    const raw = normalize(query);
    const aliases = {
      'psl': 'port st lucie',
      'irc': 'indian river county'
    };
    return aliases[raw] || raw;
  }

  async function loadIndex() {
    if (!indexPromise) {
      indexPromise = fetch(INDEX_URL, { cache: 'no-store', credentials: 'same-origin' })
        .then(response => {
          if (!response.ok) throw new Error('search index unavailable');
          return response.json();
        })
        .then(payload => payload && payload.stories ? Object.values(payload.stories) : [])
        .catch(error => {
          indexPromise = null;
          throw error;
        });
    }
    return indexPromise;
  }

  function scoreStories(stories, rawQuery) {
    const phrase = expandCommonTerms(rawQuery);
    if (phrase.length < 2) return [];
    const terms = phrase.split(/\s+/).filter(Boolean);

    return stories.map(meta => {
      const headline = normalize(meta.headline);
      const teaser = normalize(meta.teaser);
      const category = normalize(meta.category);
      const places = normalize([...(meta.cities || []), ...(meta.counties || [])].join(' '));
      const haystack = [headline, teaser, category, places].join(' ');
      if (!terms.every(term => haystack.includes(term))) return null;

      let score = 0;
      if (headline === phrase) score += 160;
      else if (headline.includes(phrase)) score += 90;
      else if (haystack.includes(phrase)) score += 30;
      terms.forEach(term => {
        if (headline.startsWith(term)) score += 18;
        else if (headline.includes(term)) score += 12;
        if (places.includes(term)) score += 6;
        if (category.includes(term)) score += 4;
        if (teaser.includes(term)) score += 2;
      });
      return { meta, score };
    }).filter(Boolean).sort((a, b) => {
      if (b.score !== a.score) return b.score - a.score;
      return String(b.meta.date || '').localeCompare(String(a.meta.date || ''));
    });
  }

  function formatDate(raw) {
    if (!raw) return '';
    const match = String(raw).match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (!match) return String(raw);
    const date = new Date(`${match[1]}-${match[2]}-${match[3]}T12:00:00`);
    try {
      return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric' }).format(date);
    } catch (_) {
      return String(raw);
    }
  }

  function resultHtml(item, compact = false) {
    const meta = item.meta;
    const places = [...(meta.cities || []), ...(meta.counties || [])].filter(Boolean);
    const metaLine = [meta.category || 'Local News', places[0] || '', formatDate(meta.date)].filter(Boolean).join(' · ');
    const teaser = String(meta.teaser || '').trim();
    return `<a class="tct-search-result${compact ? ' tct-search-result--compact' : ''}" href="${escapeHtml(meta.url || '#')}">
      <span class="tct-search-result-meta">${escapeHtml(metaLine)}</span>
      <strong class="tct-search-result-title">${escapeHtml(meta.headline || 'Untitled story')}</strong>
      ${!compact && teaser ? `<span class="tct-search-result-teaser">${escapeHtml(teaser)}</span>` : ''}
    </a>`;
  }

  async function renderInto({ query, resultsEl, statusEl, limit, compact = false, fullResultsLink = false }) {
    const clean = String(query || '').trim();
    if (clean.length < 2) {
      if (resultsEl) resultsEl.innerHTML = '';
      if (statusEl) statusEl.textContent = clean ? 'Type at least two characters to search.' : 'Start typing to search TCT articles.';
      return;
    }
    if (statusEl) statusEl.textContent = 'Searching…';
    try {
      const stories = await loadIndex();
      const matches = scoreStories(stories, clean);
      const visible = matches.slice(0, limit);
      if (resultsEl) {
        let html = visible.map(item => resultHtml(item, compact)).join('');
        if (fullResultsLink && matches.length > visible.length) {
          html += `<a class="tct-search-view-all" href="/search.html?q=${encodeURIComponent(clean)}">View all ${matches.length} results →</a>`;
        }
        resultsEl.innerHTML = html;
      }
      if (statusEl) {
        if (!matches.length) statusEl.textContent = `No TCT articles found for “${clean}.”`;
        else if (matches.length === 1) statusEl.textContent = '1 article found';
        else statusEl.textContent = `${matches.length} articles found`;
      }
    } catch (_) {
      if (resultsEl) resultsEl.innerHTML = '';
      if (statusEl) statusEl.textContent = 'Search is temporarily unavailable. You can still browse the archive.';
    }
  }

  // Masthead search overlay.
  const overlay = document.querySelector('[data-tct-search-overlay]');
  const toggles = Array.from(document.querySelectorAll('[data-tct-search-toggle]'));
  if (overlay && toggles.length) {
    const input = overlay.querySelector('[data-tct-search-input]');
    const results = overlay.querySelector('[data-tct-search-results]');
    const status = overlay.querySelector('[data-tct-search-status]');
    const form = overlay.querySelector('[data-tct-search-form]');
    const closers = Array.from(overlay.querySelectorAll('[data-tct-search-close]'));
    let previousFocus = null;
    let timer = null;

    function openSearch() {
      previousFocus = document.activeElement;
      overlay.hidden = false;
      document.documentElement.classList.add('tct-search-open');
      toggles.forEach(button => button.setAttribute('aria-expanded', 'true'));
      window.setTimeout(() => {
        if (input) input.focus();
        loadIndex().catch(() => {});
      }, 0);
    }

    function closeSearch() {
      overlay.hidden = true;
      document.documentElement.classList.remove('tct-search-open');
      toggles.forEach(button => button.setAttribute('aria-expanded', 'false'));
      if (previousFocus && typeof previousFocus.focus === 'function') previousFocus.focus();
    }

    toggles.forEach(button => button.addEventListener('click', event => {
      event.preventDefault();
      openSearch();
    }));
    closers.forEach(button => button.addEventListener('click', closeSearch));
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && !overlay.hidden) closeSearch();
    });

    if (input) input.addEventListener('input', () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => renderInto({
        query: input.value,
        resultsEl: results,
        statusEl: status,
        limit: 7,
        compact: true,
        fullResultsLink: true
      }), 110);
    });

    if (form) form.addEventListener('submit', event => {
      const query = input ? input.value.trim() : '';
      if (!query) {
        event.preventDefault();
        if (input) input.focus();
      }
    });
  }

  // Dedicated full search results page.
  const pageForm = document.querySelector('[data-tct-search-page-form]');
  if (pageForm) {
    const pageInput = pageForm.querySelector('[data-tct-search-page-input]');
    const pageResults = document.querySelector('[data-tct-search-page-results]');
    const pageStatus = document.querySelector('[data-tct-search-page-status]');
    let pageTimer = null;

    const runPageSearch = query => renderInto({
      query,
      resultsEl: pageResults,
      statusEl: pageStatus,
      limit: 100,
      compact: false,
      fullResultsLink: false
    });

    const initial = new URLSearchParams(window.location.search).get('q') || '';
    if (pageInput) pageInput.value = initial;
    if (initial) runPageSearch(initial);

    if (pageInput) pageInput.addEventListener('input', () => {
      window.clearTimeout(pageTimer);
      pageTimer = window.setTimeout(() => runPageSearch(pageInput.value), 130);
    });

    pageForm.addEventListener('submit', event => {
      event.preventDefault();
      const query = pageInput ? pageInput.value.trim() : '';
      const url = query ? `/search.html?q=${encodeURIComponent(query)}` : '/search.html';
      try { history.replaceState(null, '', url); } catch (_) {}
      if (query && typeof window.gtag === 'function') {
        try { window.gtag('event', 'search', { search_term: query }); } catch (_) {}
      }
      runPageSearch(query);
    });
  }
})();
