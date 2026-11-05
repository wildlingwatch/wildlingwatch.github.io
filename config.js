// Wildling Watch site settings. These values are safe to publish: the anon key only allows
// what the database security rules permit. NEVER put the service role key or any Stripe
// secret key in this file. Those belong in Supabase function secrets (see README.md).
window.WILDLING_CONFIG = {
  // Supabase → Project Settings → API → Project URL, e.g. 'https://abcd1234.supabase.co'
  supabaseUrl: '',
  // Supabase → Project Settings → API → Project API keys → anon / public
  supabaseAnonKey: '',
  // Turn on after the Stripe products, secrets and both functions are set up (README step 5).
  paymentsEnabled: false,
};
