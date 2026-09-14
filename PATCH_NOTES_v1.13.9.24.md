# TCT v1.13.9.24 — Latest News publication-stream repair

## Problem
A canonical article could be successfully published and appear in its category hero / Top Stories, yet never appear in the homepage **Latest News** rail.

The rail was reusing `_archive_entry_publishable()`, which has a generic 120-word archive-recovery floor. The actual publication pipeline intentionally permits a shorter, verified source-constrained breaking brief when the originating report is itself short. That meant a valid article could pass publication, receive a permalink and `first_published` timestamp, then be silently filtered back out of Latest News.

The Sept. 14 Florida highway-agency data-breach article exposed this mismatch.

## Fix
- Latest News now has a dedicated post-publication eligibility check.
- It trusts the final archive's explicit live-placement safety state instead of re-running article-depth eligibility after publication.
- Quarantined, retired, explicitly ranking-ineligible, placeholder, self-promotional and expired Sports-preview rows remain excluded.
- Reverse chronology and canonical-publication deduplication are unchanged.
- No article bodies, registry identity, redirects, paywall, membership, Missing Persons, or Supabase behavior are changed.

## Regression coverage
Added tests proving that:
1. A valid published brief below the generic 120-word archive-recovery floor still appears in Latest News and sorts ahead of older articles.
2. Quarantined/retired rows remain excluded from Latest News.
