// Receives Stripe's "payment completed" events and grants the purchase on the player's account.
// Deploy with --no-verify-jwt: Stripe calls it directly and is verified by its signature instead.
import Stripe from "npm:stripe@14.25.0";
import { createClient } from "npm:@supabase/supabase-js@2.45.4";

const stripe = new Stripe(Deno.env.get("STRIPE_SECRET_KEY") ?? "", {
  apiVersion: "2024-06-20",
  httpClient: Stripe.createFetchHttpClient(),
});
const cryptoProvider = Stripe.createSubtleCryptoProvider();

// What each pack grants. Keep in sync with GEM_PACKS in index.html.
const PACKS: Record<string, { gems: number; premium?: boolean }> = {
  pouch: { gems: 100 },
  sack: { gems: 550 },
  chest: { gems: 1200 },
  hoard: { gems: 2600 },
  premium: { gems: 0, premium: true },
};

Deno.serve(async (req) => {
  const signature = req.headers.get("Stripe-Signature");
  const body = await req.text();
  let event: Stripe.Event;
  try {
    event = await stripe.webhooks.constructEventAsync(
      body, signature ?? "", Deno.env.get("STRIPE_WEBHOOK_SECRET") ?? "", undefined, cryptoProvider,
    );
  } catch (err) {
    console.error("Bad webhook signature", err);
    return new Response("Invalid signature", { status: 400 });
  }

  if (event.type === "checkout.session.completed" || event.type === "checkout.session.async_payment_succeeded") {
    const session = event.data.object as Stripe.Checkout.Session;
    if (session.payment_status === "paid") {
      const pack = session.metadata?.pack ?? "";
      const userId = session.client_reference_id ?? session.metadata?.user_id ?? null;
      // "premium-s2", "premium-s3", ... are later seasons' premium passes.
      const grant = PACKS[pack] ?? (/^premium-s\d{1,4}$/.test(pack) ? { gems: 0, premium: true } : undefined);
      if (!grant || !userId) {
        console.error("Paid session with unknown pack or user", session.id, pack, userId);
      } else {
        const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
        const { error } = await admin.rpc("grant_purchase", {
          p_session: session.id,
          p_user: userId,
          p_pack: pack,
          p_gems: grant.gems,
          p_premium: !!grant.premium,
          p_amount: session.amount_total ?? null,
          p_currency: session.currency ?? null,
        });
        // A 500 makes Stripe retry later; grant_purchase ignores duplicates.
        if (error) {
          console.error("grant_purchase failed", error);
          return new Response("Database error", { status: 500 });
        }
      }
    }
  }
  return new Response(JSON.stringify({ received: true }), { headers: { "Content-Type": "application/json" } });
});
