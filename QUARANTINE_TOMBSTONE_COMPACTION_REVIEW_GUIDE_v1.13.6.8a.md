# v1.13.6.8a — Quarantine Tombstone Compaction Review Guide

After applying this overlay, run **Test Editorial Engine** first. Expected result: **1,023 passed** with the existing deprecation warnings only.

Then rerun **Generate News**. The previous 50.02 MiB registry failure should not recur. The first successful registry write will compact historical `quarantined_stories` into tombstones and should create substantial headroom below the unchanged 50 MiB ceiling.

Review `data/editorial_story_registry.json` after the run:

- `history_compaction.last_quarantine_tombstone_write.records_compacted` should be non-zero on the first run;
- `history_compaction.last_quarantine_tombstone_write.bytes_reclaimed` should show substantial reclaimed space;
- `history_compaction.last_serialized_bytes` must remain below `max_serialized_bytes`;
- quarantined story IDs must remain present under `quarantined_stories`;
- live publication/canonical/permalink contracts should continue to pass normally.

This patch deliberately does **not** raise `REGISTRY_MAX_BYTES` and does not delete quarantine IDs. It removes only full historical diagnostic snapshots that cannot authorize publication.
