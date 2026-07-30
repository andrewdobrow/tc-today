# Latest News Rail Review Guide — v1.12.0.2

After production generation, review `data/latest-news-rail-contract.json`.

Required values:

- `passed: true`
- `policy: strict_reverse_tct_publication_chronology`
- Five `selected_slugs` when at least five eligible archive records exist
- `selected_publication_times` ordered newest to oldest

On the live homepage, compare the rail against the newest canonical records in
`archive.json`. The rail may differ from Top Stories because importance ranking is
not used. A newly published low-urgency community article must appear above an older
high-urgency article.
