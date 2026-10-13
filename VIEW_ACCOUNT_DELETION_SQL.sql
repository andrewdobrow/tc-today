-- Keep compact, irreversible identifiers to ignore late Stripe webhook events after deletion.
-- No email addresses, customer ids, or user UUIDs are stored in plaintext.
create table if not exists public.membership_deleted_identifiers (
  identifier_hash text primary key check (identifier_hash ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default now()
);
alter table public.membership_deleted_identifiers enable row level security;
revoke all on public.membership_deleted_identifiers from anon, authenticated;
grant select, insert, update on public.membership_deleted_identifiers to service_role;
comment on table public.membership_deleted_identifiers is
  'Minimal SHA-256 replay suppression hashes for deleted membership identities. Retained to prevent accidental recreation by delayed Stripe events.';
