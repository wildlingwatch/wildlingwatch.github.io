-- Wildling Watch: guest accounts, cloud saves and purchases.

-- One row per player (guest or not). Created automatically when an account is created.
create table if not exists public.profiles (
  id          uuid primary key references auth.users (id) on delete cascade,
  data        jsonb not null default '{}'::jsonb,   -- the game's saved progress (written by the game)
  gem_credits integer not null default 0,           -- total gems bought with real money (server only)
  premium     boolean not null default false,       -- premium Trail Pass owned (server only)
  updated_at  timestamptz not null default now()
);

alter table public.profiles enable row level security;

drop policy if exists "Players read their own profile" on public.profiles;
create policy "Players read their own profile" on public.profiles
  for select using (auth.uid() = id);

drop policy if exists "Players update their own profile" on public.profiles;
create policy "Players update their own profile" on public.profiles
  for update using (auth.uid() = id) with check (auth.uid() = id);

-- Players may only change their save data. gem_credits and premium can only be changed by the
-- payment webhook, which runs with the service role.
revoke insert, update, delete on public.profiles from anon, authenticated;
grant select on public.profiles to authenticated;
grant update (data, updated_at) on public.profiles to authenticated;

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id) values (new.id) on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- Every completed Stripe checkout, recorded once. The primary key makes webhook retries harmless.
create table if not exists public.purchases (
  session_id text primary key,
  user_id    uuid references auth.users (id) on delete set null,
  pack       text not null,
  gems       integer not null default 0,
  premium    boolean not null default false,
  amount     integer,            -- amount paid, in cents
  currency   text,
  created_at timestamptz not null default now()
);

alter table public.purchases enable row level security;

drop policy if exists "Players read their own purchases" on public.purchases;
create policy "Players read their own purchases" on public.purchases
  for select using (auth.uid() = user_id);

revoke insert, update, delete on public.purchases from anon, authenticated;
grant select on public.purchases to authenticated;

-- Called only by the stripe-webhook function. Grants a purchase exactly once per checkout session.
create or replace function public.grant_purchase(
  p_session text, p_user uuid, p_pack text, p_gems integer, p_premium boolean, p_amount integer, p_currency text
)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.purchases (session_id, user_id, pack, gems, premium, amount, currency)
  values (p_session, p_user, p_pack, p_gems, p_premium, p_amount, p_currency)
  on conflict (session_id) do nothing;

  if not found then
    return false; -- already granted
  end if;

  update public.profiles
     set gem_credits = gem_credits + greatest(p_gems, 0),
         premium     = premium or p_premium
   where id = p_user;
  return true;
end;
$$;

revoke execute on function public.grant_purchase(text, uuid, text, integer, boolean, integer, text) from public, anon, authenticated;
grant execute on function public.grant_purchase(text, uuid, text, integer, boolean, integer, text) to service_role;
