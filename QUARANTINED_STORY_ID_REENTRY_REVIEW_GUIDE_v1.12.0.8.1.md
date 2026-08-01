# Quarantined Story ID Re-entry Review Guide — v1.12.0.8.1

## Required files

- Complete production workflow log
- `data/persistent-story-identity-integrity.json`
- `data/editorial_story_registry.json`
- `data/cross-source-update-identity.json`
- `data/forward-publication-identity.json`

The workflow now uploads these files in a `tct-generation-diagnostics-<run-id>` artifact even if generation fails.

## Expected log signals

Near startup:

```text
Persistent identity denylist loaded: <N> quarantined story ID(s)
```

A nonzero value is expected while historical quarantines remain in the registry.

A stale current-run assignment may be silently reset before publication. If a quarantined ID reaches the final append stage despite that source-level rejection, the log may show:

```text
Final publication barrier revoked <N> quarantined story ID(s)
```

That is a defensive repair signal. Repeated occurrences for the same source should be investigated, but they must not cause an archive integrity violation.

## Passing contract

`persistent-story-identity-integrity.json` must show:

```json
{
  "passed": true,
  "summary": {
    "active_contaminated_count": 0,
    "broad_event_mapping_count": 0,
    "broad_story_write_authority_count": 0,
    "archive_quarantine_reference_count": 0,
    "circular_story_id_authorization_count": 0,
    "violation_count": 0
  }
}
```

## Specific regression covered

A cached decision that previously assigned the WPEC Port St. Lucie fatal-intersection crash to quarantined `story_000011` must not be reused. The source must either resolve to its repaired safe identity or be treated as a new current-run story; it may never publish with `story_000011`.

## Failure handling

The exception now includes the first exact violation, for example:

```text
archive_quarantine_reference=story_000011:<slug>
```

Download the diagnostics artifact from the failed workflow and inspect the named story or slug directly.
