# v1.13.6.1d review guide

Review only the registry storage-pressure path.

Expected behavior:

1. Below 45 MiB, the registry remains two-space pretty-printed JSON.
2. Above 45 MiB, candidate evidence is pressure-compacted as before and JSON indentation tightens to one space.
3. Only if the tighter pressure representation still exceeds 50 MiB does the writer use the pre-existing emergency evidence limit and compact JSON formatting.
4. If compact JSON still exceeds 50 MiB, generation fails closed exactly as before.
5. Parsing the saved registry must preserve story/event identity data exactly.

On the next production run, confirm the prior `50.19 MiB` registry exception is absent and generation proceeds beyond the Local Government audit batch. Then continue validating the separate forward-live-identity hotfix later in the run.
