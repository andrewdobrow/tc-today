# v1.13.9.20a — Redirect audit regression test hotfix

The v1.13.9.20 redirect audit correctly left 204 redirects at the moment of the audit, but its regression test incorrectly treated that release-time total as a permanent invariant. The redirect ledger is cumulative and may legitimately grow when later production runs verify a new duplicate/alias.

This hotfix changes only the audit regression test. It now verifies that:

- `redirect_count` matches the actual redirect rows;
- the ledger never falls below the audited 204-row baseline;
- every redirect still has a verification row;
- redirect sources remain unique;
- all redirect pages verify successfully;
- all 16 restored standalone permalinks remain absent from redirect sources; and
- all 13 audited aliases remain locked to their approved targets.

No production redirect, article, generator, archive, event, membership, or Supabase behavior is changed.
