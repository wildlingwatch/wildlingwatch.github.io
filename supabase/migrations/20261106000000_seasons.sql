-- Wildling Watch: one premium Trail Pass per season.

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
