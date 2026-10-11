-- TCT iOS push registry. Safe and inert until push-device is deployed and
-- readers explicitly enable alerts. NO triggers and NO outbound senders.
-- The service role is used only inside the push-device Edge Function.
create table if not exists public.ios_push_devices (
    installation_id uuid primary key,
    registration_secret_hash text not null check (registration_secret_hash ~ '^[0-9a-f]{64}$'),
    apns_token text check (apns_token is null or apns_token ~ '^[0-9a-f]{32,512}$'),
    environment text not null default 'production'
        check (environment in ('production', 'sandbox')),
    enabled boolean not null default false,
    martin boolean not null default true,
    st_lucie boolean not null default true,
    indian_river boolean not null default true,
    breaking boolean not null default true,
    digest boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    last_seen_at timestamptz not null default now()
);

create index if not exists ios_push_devices_active_idx
    on public.ios_push_devices(environment, last_seen_at desc)
    where enabled = true and apns_token is not null;

-- Nothing is publicly readable or writable, even for logged-in Supabase users.
alter table public.ios_push_devices enable row level security;
revoke all on public.ios_push_devices from anon, authenticated;
grant select, insert, update, delete on public.ios_push_devices to service_role;
-- Never add anon/authenticated SELECT policies: device tokens are private.
comment on table public.ios_push_devices is
    'Opt-in APNs tokens for TCT iOS; service-role Edge Function access only. No automatic notifications.';
