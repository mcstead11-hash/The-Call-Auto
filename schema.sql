-- The Call: vote storage. Paste into Supabase > SQL Editor and run once.
-- Also turn on Authentication > Sign In / Providers > "Allow anonymous sign-ins".

create table if not exists public.votes (
  play_id    text        not null check (char_length(play_id) between 1 and 80),
  user_id    uuid        not null default auth.uid() references auth.users on delete cascade,
  team       text        not null check (team ~ '^[A-Z]{1,4}$'),
  pick       text        not null check (pick in ('a', 'b')),
  created_at timestamptz not null default now(),
  primary key (play_id, user_id)  -- one vote per person per play
);

alter table public.votes enable row level security;

-- Each visitor can add their own vote and read it back. There are no update or
-- delete policies, so a vote is final.
drop policy if exists "insert own vote" on public.votes;
create policy "insert own vote" on public.votes
  for insert to authenticated with check (user_id = auth.uid());

drop policy if exists "read own vote" on public.votes;
create policy "read own vote" on public.votes
  for select to authenticated using (user_id = auth.uid());

-- Newer Supabase projects don't grant table access to the API roles by default.
grant usage on schema public to anon, authenticated;
grant select, insert on public.votes to authenticated;

-- Everyone can see the totals, never the individual rows.
create or replace function public.tally(p_play text)
returns table (team text, pick text, n bigint)
language sql stable security definer set search_path = public
as $$
  select v.team, v.pick, count(*) from public.votes v
  where v.play_id = p_play
  group by v.team, v.pick
$$;

revoke all on function public.tally(text) from public;
grant execute on function public.tally(text) to anon, authenticated;
