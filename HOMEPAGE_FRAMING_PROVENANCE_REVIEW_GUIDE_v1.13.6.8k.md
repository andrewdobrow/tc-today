# v1.13.6.8k Production Review Guide

After applying v1.13.6.8k and running Generate News, inspect `data/article-framing-integrity-report.json`.

Expected behavior for the three 2026-08-30 incidents:

1. `Palm City boaters raise concerns about parking space sizes at Charlie Leighton Park after $4.5 million renovation`
   - must not be rejected for `headline_jurisdiction_missing_from_lead` merely because the archive teaser truncates/omits the locality;
   - the public membership preview contains `Palm City` and is the correct rendered lead evidence.

2. `Port St. Lucie High School football player held in ICE custody after school zone speeding violation`
   - must not be rejected for `headline_jurisdiction_missing_from_lead` when the public preview begins with `Port St. Lucie High School...`.

3. `Man arrested after hit-and-run crash, two-hour manhunt through Palm City swamp`
   - cached WFLX provenance must not be rebound to the WPBF drone story solely because both occupy source index 1 in different run packets;
   - any source-focus diagnostic must have internally consistent title/text/URL provenance.

Do not require the report's total rejected count to be zero: future genuinely bad generated articles should still be suppressed. Review each remaining rejection on its own evidence.

Also verify:
- final canonical surface contract passes;
- no new source-integrity mismatch appears;
- the homepage can still suppress a deliberately drifted source-focus regression;
- protected article HTML still contains only the public preview, never the protected remainder.
