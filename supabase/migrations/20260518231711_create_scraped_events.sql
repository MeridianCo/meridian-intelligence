create table if not exists public.scraped_events (
  id uuid primary key default gen_random_uuid(),
  fingerprint text not null unique,
  title text not null,
  city text,
  event_url text,
  source_url text,
  payload jsonb not null default '{}'::jsonb,
  score integer not null default 0,
  duplicate_count integer not null default 1,
  search_text text not null default '',
  scraped_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_scraped_events_city
on public.scraped_events(city);

create index if not exists idx_scraped_events_score
on public.scraped_events(score desc);

create index if not exists idx_scraped_events_search_text
on public.scraped_events using gin(to_tsvector('simple', search_text));

alter table public.scraped_events enable row level security;

create policy "service_role_manage_scraped_events"
on public.scraped_events
for all
to service_role
using (true)
with check (true);

create policy "authenticated_read_scraped_events"
on public.scraped_events
for select
to authenticated
using (true);

grant select on public.scraped_events to authenticated;
grant select, insert, update, delete on public.scraped_events to service_role;
