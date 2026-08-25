# v1.13.6.7k — Event-Cluster Publication Consolidation Integrity

## Purpose
Prevent one real-world event from fragmenting into many separately published articles merely because later sources use different angles, while preserving the ability to publish a genuinely independent accountability/consequence/policy follow-up.

## Core changes

1. **Angle-shifted same-event candidate recall**
   - Adds bounded article-content continuity evidence to `tct_engine.semantic_publication_gate`.
   - Different headlines can now reach semantic adjudication when the underlying article facts strongly align.
   - This is candidate recall only; it does not deterministically merge stories.
   - Generic locality/newsroom terms are stripped so unrelated same-county stories do not become candidates simply because they mention the same city, residents, police, or officials.

2. **Same event defaults to canonical update**
   - A different angle by itself cannot mint a new permalink.
   - Same real-world event + material new facts normally routes to `update_existing_canonical`.
   - A second permalink is allowed only when the model explicitly identifies a materially new, independently newsworthy accountability/consequence/policy/investigation/public-interest follow-up.
   - Even then, publication requires a distinct persistent story identity; the same story ID cannot use the independent-follow-up escape hatch.

3. **Independent follow-up ledger separation**
   - An authorized independent follow-up does not inherit the parent incident/weather ledger key, preventing the secondary story from collapsing back into the main event solely because it shares the underlying incident.

4. **Top Stories event diversity backstop**
   - Adds a maximum of two visible Top Stories placements from one event cluster.
   - Uses persistent story/incident identity first and strong semantic content continuity as a fallback.
   - This is presentation protection, not a substitute for publication consolidation.

5. **Current Port St. Lucie tornado cleanup**
   - Preserves two active publications:
     - authoritative main tornado event canonical
     - late/missing-alert accountability follow-up
   - Redirects five redundant tornado-angle URLs to those two canonicals.
   - Resident reaction, anniversary framing, pre-survey coverage, and damage-total coverage consolidate into the main event canonical.
   - Radar-detection explanation consolidates into the alert/accountability canonical.

## Validation
- New event-cluster regression suite: 9/9 passed.
- Package validation: 38 modules imported / 119 public exports verified.
- `py_compile` passed for both changed Python modules.
- The completed working tree was previously exercised against the broader repository CI/stabilization suites before packaging; this packaging step changes no engine code.

## Apply order
Apply after v1.13.6.7j.
