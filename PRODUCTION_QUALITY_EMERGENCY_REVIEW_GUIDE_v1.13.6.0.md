# TCT v1.13.6.0 production review guide

After applying this overlay, run **Update Treasure Coast Today**. The production workflow runs its regression suite before generation/deployment.

## Required post-run checks

1. Homepage hero
   - The Causeway Cove hero (if it remains the selected hero) must have a visible image.
   - No real hero may render an empty gray media panel.
   - `data/final-live-image-contract.json` must report `status: passed` and `failure_count: 0`.

2. WPTV meetup
   - `WPTV holds education meetup in Port St. Lucie on August 20` must disappear from Latest News, Top Stories and county/topic surfaces.
   - Its archive record must be purged.
   - Its old article URL must become a `noindex,follow` redirect to `/archive.html`.
   - Legitimate WPTV reporting must continue to publish normally.

3. Category/county cleanup
   - `Four Indian River County elementary schools reach 90% reading proficiency milestone` must not carry Crime & Safety.
   - `Indian River County Superintendent highlights new bus routing system on first day of school` must not carry Crime & Safety and should project to Indian River County, not all three Treasure Coast counties.
   - Legitimate crime/public-safety coverage must remain in Crime & Safety.

4. Logs
   - Look for `Final live image contract ...` and confirm it passes.
   - `Nonstory publication contract` must pass after the archive purge.
   - County membership authority must pass with zero unsupported memberships remaining.

If any of these fail, do not treat the run as successful; preserve the log and the freshly generated reports for the next repair increment.
