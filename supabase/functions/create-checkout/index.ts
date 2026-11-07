// Starts a Stripe Checkout session for the signed-in (guest) player.
// The client sends only a pack id; prices come from server-side secrets, never from the browser.
import Stripe from "npm:stripe@18.0.0";
import { createClient } from "npm:@supabase/supabase-js@2.45.4";

const stripe = new Stripe(Deno.env.get("STRIPE_SECRET_KEY") ?? "", {
  apiVersion: "2025-03-31.basil",
  httpClient: Stripe.createFetchHttpClient(),
});

// Stripe Price ids, set with `supabase secrets set STRIPE_PRICE_POUCH=price_... ...`
const PRICES: Record<string, string | undefined> = {
  pouch: Deno.env.get("STRIPE_PRICE_POUCH"),
  sack: Deno.env.get("STRIPE_PRICE_SACK"),
  chest: Deno.env.get("STRIPE_PRICE_CHEST"),
  hoard: Deno.env.get("STRIPE_PRICE_HOARD"),
  premium: Deno.env.get("STRIPE_PRICE_PREMIUM"),
};

const SITE_URL = (Deno.env.get("SITE_URL") ?? "http://localhost:3000").replace(/\/$/, "");
const cors = {
  "Access-Control-Allow-Origin": Deno.env.get("ALLOWED_ORIGIN") ?? SITE_URL,
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { ...cors, "Content-Type": "application/json" } });

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return json({ error: "Method not allowed" }, 405);

  try {
    const supabase = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_ANON_KEY")!, {
      global: { headers: { Authorization: req.headers.get("Authorization") ?? "" } },
    });
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return json({ error: "Please reload the game and try again." }, 401);

    const { pack } = await req.json().catch(() => ({ pack: "" }));
    // Every season's premium pass ("premium" for Season 1, "premium-s2", ...) uses the same $5 price.
    const season = pack === "premium" ? 1 : /^premium-s\d{1,4}$/.test(String(pack)) ? Number(String(pack).slice(9)) : 0;
    const price = season ? PRICES.premium : PRICES[String(pack)];
    if (!price) return json({ error: "That item is not for sale right now." }, 400);

    if (season) {
      const { data } = await supabase.from("profiles").select("premium, premium_seasons").eq("id", user.id).maybeSingle();
      const owned = (data?.premium_seasons ?? []).includes(season) || (season === 1 && data?.premium);
      if (owned) return json({ error: "You already own this season's premium Trail Pass." }, 409);
    }

    const session = await stripe.checkout.sessions.create({
      mode: "payment",
      line_items: [{ price, quantity: 1 }],
      client_reference_id: user.id,
      metadata: { pack: String(pack), user_id: user.id },
      success_url: `${SITE_URL}/play/?purchase=success`,
      cancel_url: `${SITE_URL}/play/?purchase=cancelled`,
    });
    return json({ url: session.url });
  } catch (err) {
    console.error("create-checkout failed", err);
    return json({ error: "Checkout could not start. Please try again." }, 500);
  }
});
