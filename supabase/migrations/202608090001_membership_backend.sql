-- Treasure Coast Today membership backend, dark launch.
-- Safe to run more than once.

alter table public.profiles
  add column if not exists is_admin boolean not null default false;

-- Keep a profile row in sync for every Supabase Auth user. Security is enforced
-- by RLS for browser clients; Edge Functions use the server-side admin client.
create or replace function public.handle_new_auth_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email, created_at, updated_at)
  values (new.id, new.email, now(), now())
  on conflict (id) do update
    set email = excluded.email,
        updated_at = now();
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert or update of email on auth.users
for each row execute procedure public.handle_new_auth_user();

-- Backfill anyone created before the trigger existed, including the test/admin
-- account created during setup.
insert into public.profiles (id, email, created_at, updated_at)
select id, email, now(), now()
from auth.users
on conflict (id) do update
  set email = excluded.email,
      updated_at = now();

-- Stripe retries webhooks. We record successfully processed event ids only
-- after the business update succeeds, making retries safe and observable.
create table if not exists public.stripe_webhook_events (
  event_id text primary key,
  event_type text not null,
  processed_at timestamptz not null default now()
);

alter table public.stripe_webhook_events enable row level security;

create index if not exists subscriptions_user_status_idx
  on public.subscriptions(user_id, status);
