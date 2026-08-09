-- Treasure Coast Today membership live-mode isolation.
-- Existing sandbox subscriptions remain stripe_livemode=false and cannot grant
-- live reader entitlement after TCT_STRIPE_MODE is switched to live.
-- Safe to run more than once.

alter table public.subscriptions
  add column if not exists stripe_livemode boolean not null default false;

create index if not exists subscriptions_user_mode_status_idx
  on public.subscriptions(user_id, stripe_livemode, status);
