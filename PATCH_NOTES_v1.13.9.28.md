# TCT v1.13.9.28 — deterministic Supabase CLI workflow preflight

Production failed after the expensive generation phase because `supabase/setup-cli@v1` attempted an unauthenticated GitHub lookup for the latest CLI release and hit GitHub's API rate limit. The same action also emits the Node 20 deprecation warning under the current GitHub Actions rollout.

This hotfix:

- removes `supabase/setup-cli@v1` from both TCT workflows that used it;
- pins Supabase CLI **2.117.0** instead of resolving `latest`;
- installs the pinned npm package into `$RUNNER_TEMP`, outside the repository;
- explicitly uses Node 24;
- preflights the CLI near the beginning of the production workflow, before the long editorial generation phase, so an external toolchain outage fails fast instead of wasting another full generation run;
- leaves the existing Supabase deploy commands and deployment conditions unchanged.

No site-generation, editorial, membership, database, or Supabase function code is changed.
