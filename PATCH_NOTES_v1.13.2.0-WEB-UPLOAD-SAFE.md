# Treasure Coast Today v1.13.2.0
## County Membership Authority + Business Eligibility + Workflow Recovery

### Emergency workflow recovery
The 2026-08-07 production run completed category generation, publication identity consolidation, story regression validation, and archive writes, then terminated at the final persistent-story identity integrity check because two `fragmented_unified_incident` candidates were present.

This release changes that one condition from a fatal publication blocker to an advisory relationship signal. A fragmented unified-incident component does not itself grant canonical/publication write authority and can contain conservative similarity candidates, so it is unsafe to auto-merge and operationally unsafe to discard an otherwise successful run solely because the candidate exists.

The final identity report now distinguishes:
- **hard violations**: still fail closed and raise an error;
- **fragmented unified-incident candidates**: recorded as advisories with no publication write authority.

Hard failures remain unchanged for broad-event mappings/write authority, contaminated active stories, quarantine references, circular story-ID authorization, and timeline-coherence violations.

### County Membership Authority Gate
County placement is now derived from source authority rather than generated TCT copy. Generated headline, teaser, body, classifier labels, cached county labels, or an internal TCT permalink cannot self-authorize Martin, St. Lucie, or Indian River County membership.

Conflicting outside-county source evidence blocks false Treasure Coast county membership. The known Palm Beach County heat/tree story therefore cannot re-enter Martin County through archive recovery, cached generation, or final live projection.

Archive migration is conservative. Historical rows created before source-provenance persistence may keep only county memberships they already possessed when there is no surviving source-derived county evidence and no explicit outside-county conflict. This migration-only grandfather authority cannot add new counties and stops applying when real source locality exists.

### Business & Development eligibility
Business & Development is now enforced before model generation rather than observe-only. A source must have a Treasure Coast business/development nexus plus a business/development primary focus. Competing story forms such as elections, crime, animal-welfare investigations, heat/weather policy, sports, and schools cannot enter Business merely because a generated framing mentions economic impact.

Regression fixtures include the recent South Florida data-center bleed, early-voting bleed, Martin County dogs investigation, and legitimate local development/opening/jobs/transaction examples.

### Archive migration validation
Production-archive simulation on the supplied repository:
- 695 archive records assessed
- 191 legacy rows preserved by the migration-only authority rule
- 23 rows repaired
- 26 rows had county-key changes in total (including source-supported corrections/additions)
- 0 unsupported county memberships remained
- the known Palm Beach heat/tree story lost the erroneous Martin County membership
- sampled legacy Fort Pierce, Port St. Lucie, and Vero Beach rows retained their county membership

### Test validation
The workflow-equivalent pytest boundary was run in seven partitions because this execution environment limits a single command duration:
- 140 passed
- 120 passed
- 127 passed
- 99 passed
- 124 passed
- 140 passed
- 28 passed
- **778 passed, 0 failed total**

Generator runtime hotfix and false-jurisdiction hotfix were both verified idempotent against this generator. `scripts/validate_package.py` passed with 34 modules imported and 119 public exports verified.

### Overlay safety
This overlay intentionally contains no production archive, story registry, generation cache, generated pages, sitemap, or feed output. It changes code/tests only, plus these release documents.
