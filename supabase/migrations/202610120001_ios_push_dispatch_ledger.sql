-- Independent one-shot alert dispatch ledger; no triggers or automated sending.
-- The slug PRIMARY KEY locks each article against repeat alerts even when two
-- different audience groups are selected. Do not delete ledger rows to retry.
create table if not exists public.ios_push_dispatches (
    slug text primary key check (slug ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9-]+$'),
    audience text not null check (audience in ('breaking', 'martin', 'st_lucie', 'indian_river')),
    title text not null,
    body text not null,
    status text not null default 'reserved' check (status in ('reserved', 'completed', 'partial')),
    attempted integer not null default 0,
    accepted integer not null default 0,
    rejected integer not null default 0,
    created_at timestamptz not null default now(),
    finished_at timestamptz
);

alter table public.ios_push_dispatches enable row level security;
revoke all on public.ios_push_dispatches from anon, authenticated;
grant select, insert, update, delete on public.ios_push_dispatches to service_role;

comment on table public.ios_push_dispatches is
    'One-shot APNs dispatch lock and aggregate send counts; manual-only, never automatically retries.';
