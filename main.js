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
          show = card.dataset.cat === cat;
        }
        card.style.display = show ? "flex" : "none";
      });

      // Filter Older stories — show all in Top News, category-matched otherwise
      document.querySelectorAll(".older-item").forEach(item => {
        const link = item.querySelector(".older-link");
        const itemCat = item.dataset.cat;
        const show = cat === "all" ? true : itemCat === cat;
        item.style.display = show ? "list-item" : "none";
      });
      const olderSection = document.getElementById("olderSection");
      if (olderSection) {
        // Older section always visible in Top News; hidden in category views
        // unless it has matching items
        if (cat === "all") {
          olderSection.style.display = "block";
        } else {
          const anyVisible = Array.from(olderSection.querySelectorAll(".older-item"))
            .some(i => i.style.display !== "none");
          olderSection.style.display = anyVisible ? "block" : "none";
        }
      }

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
