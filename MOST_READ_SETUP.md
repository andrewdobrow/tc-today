# TCT Most Read — one-time database setup

The site and Edge Function are deployment-safe before the database table exists: the **Most Read** module stays hidden until the schema is ready.

Apply `supabase/migrations/202609080001_story_analytics.sql` once to the production Supabase project (using your normal Supabase migration workflow or the SQL editor). The hourly table stores only `slug`, hour bucket and aggregate view count; it does **not** store IP addresses, account IDs, device IDs or other reader identifiers.

The routine GitHub Actions workflow probes and deploys the `story-analytics` Edge Function automatically if the endpoint is missing. After the migration is applied, its `capability` action reports `schema_ready: true` and Most Read begins collecting/displaying data automatically.
