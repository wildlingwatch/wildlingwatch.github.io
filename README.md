# Wildling Watch

A creature-catching tower defense you can host on any website. Players need no sign-up: the game
creates a guest account for them automatically.

| File | What it is |
|---|---|
| `index.html` | Website landing page (features, prices, support) |
| `play/index.html` | The whole game (12 campaign trails, 4 with branching routes) |
| `config.js` | Your public Supabase settings and the payments switch |
| `supabase/migrations/…_init.sql` | Database tables and security rules |
| `supabase/functions/create-checkout` | Starts a Stripe checkout for a gem pack or the premium pass |
| `supabase/functions/stripe-webhook` | Adds gems or premium after Stripe confirms the payment |

Without any keys the game still works fully offline: progress stays in the browser, duels and
purchases show as unavailable.

## What runs where

- **Online duels** use Supabase Realtime. Players share a 4-letter code; no account needed.
- **Guest accounts and cloud saves** use Supabase anonymous sign-in. Progress is saved to the
  `profiles` table and survives page reloads and browser restarts.
- **Purchases** use Stripe Checkout. The game only ever sends a pack id. Card details are entered on
  Stripe's own page. Gems and premium are granted by the webhook, never by the browser.

---

## Setup

You need a free [Supabase](https://supabase.com) account, a [Stripe](https://stripe.com) account, and
Node.js (for `npx`). All commands run from this folder.

### 1. Create the Supabase project

1. In the Supabase dashboard, create a new project.
2. **Authentication → Sign In / Providers → Anonymous sign-ins:** turn it **on**.
3. **Project Settings → API:** copy the **Project URL** and the **anon public** key into `config.js`.

### 2. Create the database

```sh
npx supabase login
npx supabase link --project-ref YOUR_PROJECT_REF   # the "abcd1234" part of your project URL
npx supabase db push
```

(Or paste each SQL file in `supabase/migrations`, oldest first, into **SQL Editor → New query** and run it.)

The second migration adds one premium Trail Pass per season. If you already
ran the first one, `npx supabase db push` applies only the new file. Season passes need no new Stripe price:
every season's pass uses `STRIPE_PRICE_PREMIUM`. After pulling this change, redeploy both functions
(`npx supabase functions deploy create-checkout` and `npx supabase functions deploy stripe-webhook --no-verify-jwt`).

### 3. Try it locally

```sh
npx serve .
```

Open the address it prints. The home page should say "Progress is saved to your guest account".
Open the game in a second browser (or a private window) to duel yourself: create a duel in one,
join with the code in the other. Duels against your own other tab work but give no rewards.

### 4. Put it online

Any static host works. The simplest:

- **Netlify:** drag this folder onto [app.netlify.com/drop](https://app.netlify.com/drop).
- **Cloudflare Pages** or **Vercel:** connect the Git repository, no build step, output folder `/`.
- **itch.io:** zip `index.html` and `config.js` and upload as an HTML game.

Note your site's address (for example `https://wildling-watch.netlify.app`); Stripe needs it.

### 5. Turn on purchases (start in Stripe **test mode**)

1. **Stripe → Product catalog:** create five one-time products and copy each **Price id** (`price_…`):

   | Pack id | Product | Price | Grants |
   |---|---|---|---|
   | `pouch` | Pouch of gems | $0.99 | 100 gems |
   | `sack` | Sack of gems | $4.99 | 550 gems |
   | `chest` | Chest of gems | $9.99 | 1,200 gems |
   | `hoard` | Hoard of gems | $19.99 | 2,600 gems |
   | `premium` | Premium Trail Pass | $5.00 | Premium pass |

   The gem amounts live in `supabase/functions/stripe-webhook/index.ts` (`PACKS`) and are shown in
   `index.html` (`GEM_PACKS`). Change both together.

2. **Deploy the two functions:**

   ```sh
   npx supabase functions deploy create-checkout
   npx supabase functions deploy stripe-webhook --no-verify-jwt
   ```

3. **Stripe → Developers → Webhooks → Add endpoint:**
   - URL: `https://YOUR_PROJECT_REF.supabase.co/functions/v1/stripe-webhook`
   - Events: `checkout.session.completed` and `checkout.session.async_payment_succeeded`
   - Copy the endpoint's **signing secret** (`whsec_…`).

4. **Store the secrets** (these never go in `config.js`):

   ```sh
   npx supabase secrets set \
     STRIPE_SECRET_KEY=sk_test_... \
     STRIPE_WEBHOOK_SECRET=whsec_... \
     STRIPE_PRICE_POUCH=price_... \
     STRIPE_PRICE_SACK=price_... \
     STRIPE_PRICE_CHEST=price_... \
     STRIPE_PRICE_HOARD=price_... \
     STRIPE_PRICE_PREMIUM=price_... \
     SITE_URL=https://your-site.example
   ```

   Checkout only accepts requests from `SITE_URL`. To test from `npx serve`, temporarily also set
   `ALLOWED_ORIGIN=*` (remove it before launch with `npx supabase secrets unset ALLOWED_ORIGIN`).

5. In `config.js` set `paymentsEnabled: true` and redeploy the site.

6. **Test:** buy a pack with Stripe's test card `4242 4242 4242 4242` (any future date, any CVC).
   You return to the game, and within a few seconds the gems appear. Check **Supabase → Table
   editor → purchases** for the record.

7. **Go live:** switch Stripe to live mode, create the same products there, and run step 4 again
   with the live keys, live price ids and the live webhook's signing secret.

---

## Security notes

- The **anon key** in `config.js` is public by design. The database rules only let a player read
  their own row and change their own save data. Only the webhook (running with the service role)
  can add bought gems or premium.
- Keep `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` and the Supabase **service role key** out of the
  repository and out of `config.js`.
- **Earned** gems, stars and pass progress are calculated in the player's browser, so a determined
  player can edit their own save. Bought gems and premium are recorded on the server and can't be
  forged. Duel results are reported by each player's game, which is fine for casual play but not
  for prize tournaments.
- **Seasons:** a new season starts on the date in `SEASONS` in the game code. Add the next season's
  rewards there before the current one ends.
- Guest accounts live in one browser. If a player clears their site data, they get a new guest
  account. A future "save with email" option would use Supabase's account linking.
- Before selling to real players, check Stripe's requirements for your country (business details,
  refund policy) and add a privacy policy and terms page to the site.
