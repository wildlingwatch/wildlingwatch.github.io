-- Wildling Watch: one premium Trail Pass per season, and a weekly challenge leaderboard.

-- Seasons whose premium pass the player owns. Season 1 was the old "premium" flag.
alter table public.profiles add column if not exists premium_seasons integer[] not null default '{}';
update public.profiles set premium_seasons = array[1] where premium and not (1 = any(premium_seasons));

-- Pack ids: 'premium' is Season 1, 'premium-s2' is Season 2, and so on.
create or replace function public.grant_purchase(
  p_session text, p_user uuid, p_pack text, p_gems integer, p_premium boolean, p_amount integer, p_currency text
)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
  v_season integer := case when p_pack = 'premium' then 1
                           when p_pack ~ '^premium-s[0-9]{1,4}$' then substring(p_pack from 10)::integer
                           else null end;
begin
  insert into public.purchases (session_id, user_id, pack, gems, premium, amount, currency)
  values (p_session, p_user, p_pack, p_gems, p_premium, p_amount, p_currency)
  on conflict (session_id) do nothing;

  if not found then
    return false; -- already granted
  end if;

  update public.profiles
     set gem_credits     = gem_credits + greatest(p_gems, 0),
         premium         = premium or (p_premium and v_season = 1),
         premium_seasons = case when p_premium and v_season is not null and not (v_season = any(premium_seasons))
                                then premium_seasons || v_season else premium_seasons end
   where id = p_user;
  return true;
end;
$$;

revoke execute on function public.grant_purchase(text, uuid, text, integer, boolean, integer, text) from public, anon, authenticated;
grant execute on function public.grant_purchase(text, uuid, text, integer, boolean, integer, text) to service_role;

-- Weekly challenge: each player's best wave per week. Weeks are numbered as in the game (Monday start).
create table if not exists public.weekly_scores (
  week       integer not null,
  user_id    uuid not null references auth.users (id) on delete cascade,
  name       text not null,
  wave       integer not null check (wave between 0 and 1000),
  updated_at timestamptz not null default now(),
  primary key (week, user_id)
);
alter table public.weekly_scores enable row level security;
-- No direct access: players go through the two functions below.
revoke all on public.weekly_scores from anon, authenticated;

create or replace function public.submit_weekly(p_week integer, p_wave integer, p_name text)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_now integer := floor((extract(epoch from now()) / 86400 + 3) / 7)::integer;
  v_name text := left(regexp_replace(coalesce(p_name, ''), '[^[:alnum:] _.-]', '', 'g'), 16);
begin
  if auth.uid() is null then raise exception 'not signed in'; end if;
  if p_week < v_now - 1 or p_week > v_now + 1 then return; end if;   -- allow for time zones
  if p_wave is null or p_wave < 0 or p_wave > 1000 then return; end if;
  if length(trim(v_name)) = 0 then v_name := 'Trainer'; end if;
  insert into public.weekly_scores (week, user_id, name, wave)
  values (p_week, auth.uid(), v_name, p_wave)
  on conflict (week, user_id) do update
    set wave = greatest(weekly_scores.wave, excluded.wave), name = excluded.name, updated_at = now();
end;
$$;

create or replace function public.weekly_top(p_week integer)
returns table (name text, wave integer, me boolean)
language sql
stable
security definer
set search_path = public
as $$
  select s.name, s.wave, s.user_id = auth.uid()
    from public.weekly_scores s
   where s.week = p_week
   order by s.wave desc, s.updated_at asc
   limit 10;
$$;

revoke execute on function public.submit_weekly(integer, integer, text) from public, anon;
revoke execute on function public.weekly_top(integer) from public, anon;
grant execute on function public.submit_weekly(integer, integer, text) to authenticated;
grant execute on function public.weekly_top(integer) to authenticated;
