-- Treasure Coast Today pay-first membership UX and protected-content pipeline.
-- Safe to run more than once.

create table if not exists public.membership_checkout_links (
  session_id text primary key,
  sent_at timestamptz not null default now()
);

alter table public.membership_checkout_links enable row level security;

-- Browser clients never receive direct table access to paid article bodies.
-- Access is only through the entitlement-checking protected-article Edge Function.
alter table public.protected_articles enable row level security;

create index if not exists protected_articles_updated_at_idx
  on public.protected_articles(updated_at desc);
