# TCT audience growth + SEO features — 2026-09-08

Implements requested items 1–9 from the Sep. 8 feature review. Item 10 (Discover image standardization) is intentionally not included.

Included:
1. Google Preferred Sources modules on articles, About and Newsroom.
2. Substantive city news hubs for Stuart, Jensen Beach, Palm City, Hobe Sound, Port St. Lucie, Fort Pierce, Vero Beach, Sebastian and Fellsmere when at least 3 matching stories exist.
3. Internal event detail URLs with Event structured data and external official/ticket links.
4. Smart article recirculation using durable story/event identity first, then geography/category/text relevance.
5. Existing post-paywall Morning Brief module retained without adding a duplicate newsletter CTA inside the paywall.
6. Searchable/filterable archive while retaining crawlable chronological links.
7. Privacy-preserving 24-hour Most Read module backed by aggregate hourly counts.
8. News Tip page with location/details/contact/attachment fields and newsroom navigation.
9. Final NewsArticle, author-profile, breadcrumb, paywall-schema and canonical SEO validation.

The routine workflow builds these after the core newsroom generator and validates the final rendered output after membership paywall preparation.

## One-time Most Read setup
Apply `supabase/migrations/202609080001_story_analytics.sql` once to the production Supabase project. Until that schema exists, the Most Read UI remains hidden and the rest of the site works normally. See `MOST_READ_SETUP.md`.

## Additional: sitewide article search
A compact magnifying-glass control is added to the masthead on desktop and mobile. It opens an accessible search overlay with live article results and links to a dedicated `/search.html?q=...` results page. Search uses the existing first-party `data/story-index.json`, now enriched with teaser and geographic metadata; no external search service is required. The search results page is `noindex,follow` so query-result pages do not create low-value indexed URLs.
