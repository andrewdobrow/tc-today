# Treasure Coast Today v1.13.7.1k
## Category Hero → Top Stories Candidate Integrity

### Production defect
A current story could lead a county/topic category and still disappear completely from the Top News / Top Stories deck.

The 2026-09-01 production state exposed this with the Debevec material update. The canonical article had been refreshed and was the Martin County hero, but `render_index()` built the Top Stories input pool from category **cards only**. It then added every category hero headline to the archive-backfill exclusion set. The result was deterministic:

1. Debevec was the Martin County hero.
2. Category heroes were omitted from `all_cards_pool`.
3. Its headline was nevertheless placed in `_current_hls`.
4. Archive backfill therefore refused to add it.
5. The story never reached `_select_top_story_cards()` and could not appear in Top Stories.

This was not a ranking loss. It was a candidate-construction omission before ranking.

### Fix
- Added `_category_hero_top_story_candidates()`.
- Every live category hero is cloned into the all-news Top Stories candidate pool before archive backfill and ranking.
- Ordinary unenriched cards remain excluded as before; category heroes are explicitly eligible because they are already live editorial placements.
- Projected hero copies are marked `_top_stories_category_hero_candidate` so homepage-card metadata cannot mutate the actual category hero.
- Canonical category-hero identities render as **Top-News-only** grid cards when selected. They do not render as duplicate cards underneath the same hero on Martin County / Crime & Safety / other category views.
- A projected hero that does not win a Top Stories slot is not emitted as a redundant hidden card.
- Existing canonical permalink deduplication and the existing `front_page_hero` exclusion remain authoritative, so the visible overall homepage hero is still not duplicated immediately beneath itself.

### Regression coverage
Added tests proving that:
- an archive-recovery category hero without the ordinary `enriched` card flag is projected into the Top Stories pool;
- the projection is a clone and does not mutate the category hero;
- an old canonical with a validated recent material update is rankable once projected;
- `render_index()` includes category heroes in the Top Stories candidate pool;
- category-hero-equivalent Top Stories cards are rendered as Top-News-only rather than duplicated on their category surface.

### Current Debevec replay
Using the post-1j repository state and the actual Debevec archive receipt, the projected Martin County hero is now eligible under:
- timestamp basis: `archive:canonical_last_material_update_at`
- age: ~1.07 hours at replay time
- priority score: 78.93

The previous production Top Stories deck's lowest selected score was 39.36. The defect was therefore candidate omission, not failure to clear the ranking cutoff.

### Validation
- Focused homepage / Top Stories / permalink / category-membership tests: **38 passed**.
- Exact Test Editorial Engine pytest command:
  - **1090 passed, 0 failed**
  - 44 existing deprecation warnings
- `scripts/validate_package.py`: **passed**
  - 38 modules imported
  - 122 public exports verified
- `scripts/generate.py` compiles successfully.

### Deployment
Apply this overlay on top of v1.13.7.1j, run **Test Editorial Engine**, and only if green run one **Generate News**.

Expected production evidence after the run:
- `data/top-stories-ranking-report.json` must now contain category-hero stories in either `selected` or `excluded`; they must no longer vanish before the ranker.
- If the Debevec canonical is still within the current material-update freshness window, it should be able to compete normally for Top Stories.
- Martin County must continue to show Debevec as its hero without a duplicate Debevec grid card immediately underneath it.
