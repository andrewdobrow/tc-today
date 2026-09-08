-- Privacy-preserving aggregate story view counts for the TCT Most Read module.
-- No IP addresses, account IDs, device IDs or other reader identifiers are stored.
create table if not exists public.story_pageviews_hourly (
  hour timestamptz not null,
  slug text not null check (slug ~ '^[a-z0-9][a-z0-9-]{5,180}$'),
  views bigint not null default 0 check (views >= 0),
  primary key (hour, slug)
);

alter table public.story_pageviews_hourly enable row level security;
revoke all on table public.story_pageviews_hourly from public, anon, authenticated;

create or replace function public.increment_story_pageview(p_slug text)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  if p_slug is null or p_slug !~ '^[a-z0-9][a-z0-9-]{5,180}$' then
    raise exception 'invalid slug';
  end if;
  insert into public.story_pageviews_hourly(hour, slug, views)
  values (date_trunc('hour', now()), p_slug, 1)
  on conflict (hour, slug) do update set views = public.story_pageviews_hourly.views + 1;
end;
$$;

create or replace function public.top_story_pageviews(p_hours integer default 24, p_limit integer default 5)
returns table(slug text, views bigint)
language sql
security definer
stable
set search_path = public
as $$
  select s.slug, sum(s.views)::bigint as views
  from public.story_pageviews_hourly s
  where s.hour >= date_trunc('hour', now()) - make_interval(hours => greatest(1, least(coalesce(p_hours, 24), 168)))
  group by s.slug
  order by views desc, max(s.hour) desc, s.slug asc
  limit greatest(1, least(coalesce(p_limit, 5), 10));
$$;

revoke all on function public.increment_story_pageview(text) from public, anon, authenticated;
revoke all on function public.top_story_pageviews(integer, integer) from public, anon, authenticated;
grant execute on function public.increment_story_pageview(text) to service_role;
grant execute on function public.top_story_pageviews(integer, integer) to service_role;

create index if not exists story_pageviews_hourly_recent_idx
  on public.story_pageviews_hourly(hour desc);
