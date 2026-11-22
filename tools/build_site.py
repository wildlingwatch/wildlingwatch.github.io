"""Build the standalone site (index.html) from the artifact page, adding Supabase duels, guest accounts, cloud saves and Stripe checkout."""
import sys
src_path, out_path = sys.argv[1], sys.argv[2]
src = open(src_path, encoding='utf-8').read()

def rep(old, new):
    global src
    n = src.count(old)
    assert n == 1, (n, old[:100])
    src = src.replace(old, new)

# ---------- duel rules / messages for the standalone site ----------
rep("<li>Both players need to be signed in to claude.ai with access to this game.</li>",
    "<li>No account needed: just open the game, create a duel and send your friend the code.</li>")
rep("'Duels need a live connection, which this view does not have. You and your friend both need to be signed in to claude.ai with access to this game. Duels do not work through a public link.'",
    "(CFG.supabaseUrl ? 'Could not reach the duel server. Check your internet connection and reload the page.' : 'Online duels are not set up yet. Add your Supabase keys to config.js (see README).')")

# ---------- networking: Supabase Realtime presence, same shape as the claude.ai room ----------
rep("""async function getRoom(){
  if (!roomTried){ roomTried=true; try { roomNS = (window.claude && window.claude.use) ? await window.claude.use('room') : null; } catch(e) { roomNS=null; } }
  return roomNS;
}""", r"""async function getRoom(){
  if (!roomTried){
    roomTried=true;
    if (await CLOUD.ready) roomNS = { join: supaJoin };
    else { try { roomNS = (window.claude && window.claude.use) ? await window.claude.use('room') : null; } catch(e) { roomNS=null; } }
  }
  return roomNS;
}
// One Supabase Realtime channel per duel code. Each open tab is one presence key; the player's account id travels in the payload.
const TAB_ID = Math.random().toString(36).slice(2,10);
async function supaJoin(name){
  const ch = CLOUD.sb.channel(name, { config: { presence: { key: TAB_ID } } });
  let peers = [], mine = {};
  const handlers = new Set();
  const emit = () => { const snap={peers}; handlers.forEach(h => { try { h(snap); } catch(e) {} }); };
  ch.on('presence', { event: 'sync' }, () => {
    const st = ch.presenceState();
    peers = Object.entries(st).map(([key, metas]) => {
      const m = metas[metas.length-1] || {}, pr = (m.p && typeof m.p==='object') ? m.p : {};
      const same = key===TAB_ID;
      return { peer:key, by:null, sameTab:same, isMe: same || (!!pr.uid && pr.uid===CLOUD.uid), kind:'viewer', guest:false, presence:pr, updatedAt:Date.now() };
    });
    emit();
  });
  await new Promise((res, rej) => {
    const t = setTimeout(() => rej(new Error('timeout')), 10000);
    ch.subscribe(status => {
      if (status==='SUBSCRIBED'){ clearTimeout(t); res(); }
      else if (status==='CHANNEL_ERROR' || status==='TIMED_OUT'){ clearTimeout(t); rej(new Error(status)); }
    });
  });
  return {
    name,
    presence: async patch => { mine = {...mine, ...patch, uid: CLOUD.uid}; await ch.track({ p: mine }); },
    peers: () => peers,
    onPeers: (h) => { handlers.add(h); setTimeout(() => h({peers}), 0); return () => handlers.delete(h); },
    leave: async () => { handlers.clear(); try { await CLOUD.sb.removeChannel(ch); } catch(e) {} },
  };
}""")

# ---------- cloud saves: every save also goes to the player's guest account ----------
rep("function saveProfile(){ try { localStorage.setItem('wildling-profile', JSON.stringify(profile)); } catch(e) {} }",
    "function saveProfile(){ profile.updatedAt=Date.now(); try { localStorage.setItem('wildling-profile', JSON.stringify(profile)); } catch(e) {} if (typeof cloudPush==='function') cloudPush(); }")

rep("/* ---------- 1v1 duel (live room) ---------- */", r"""/* ---------- cloud: guest accounts, saves and purchases (Supabase + Stripe) ---------- */
// var (not const) so saveProfile can safely check it before this line has run.
var CFG = window.WILDLING_CONFIG || {};
var CLOUD = { sb:null, uid:null, ready:Promise.resolve(false), saveT:null, status:'off' };
function notice(msg){ const el=$('notice'); el.textContent=msg; el.hidden=false; clearTimeout(notice.t); notice.t=setTimeout(() => { el.hidden=true; }, 5000); }
CLOUD.ready = (async () => {
  if (!CFG.supabaseUrl || !CFG.supabaseAnonKey || !window.supabase) return false;
  try {
    CLOUD.sb = window.supabase.createClient(CFG.supabaseUrl, CFG.supabaseAnonKey, { auth: { persistSession:true, autoRefreshToken:true } });
    let { data: { session } } = await CLOUD.sb.auth.getSession();
    if (!session){ const r = await CLOUD.sb.auth.signInAnonymously(); if (r.error) throw r.error; session = r.data.session; }
    CLOUD.uid = session.user.id;
    await cloudPull(true);
    CLOUD.status='on'; renderCloudStatus();
    handlePurchaseReturn();
    return true;
  } catch(e) { console.warn('Cloud save unavailable:', e); CLOUD.status='error'; renderCloudStatus(); return false; }
})();
async function cloudPull(first){
  const { data, error } = await CLOUD.sb.from('profiles').select('data, gem_credits, premium, premium_seasons').eq('id', CLOUD.uid).maybeSingle();
  if (error || !data) return { gems:0, premium:false };
  const srv = (data.data && typeof data.data==='object') ? data.data : {};
  const hasSrv = Object.keys(srv).length > 0;
  if (first && hasSrv && (profile.syncedUid !== CLOUD.uid || (srv.updatedAt||0) > (profile.updatedAt||0))){
    profile = {...profile, ...srv, pass:{...profile.pass, ...(srv.pass||{})}, equip:{...profile.equip, ...(srv.equip||{})}};
  }
  profile.syncedUid = CLOUD.uid;
  const credits = data.gem_credits||0, delta = credits - (profile.creditsApplied||0);
  if (delta > 0) profile.gems = (profile.gems||0) + delta;
  profile.creditsApplied = credits;
  const owns = (data.premium_seasons||[]).includes(SEASON.id) || (SEASON.id===1 && !!data.premium);
  const wasPremium = !!profile.pass.premium; profile.pass.premium = owns;
  saveProfile();
  if (inHome) renderHome(); else if (inMenu) renderMenu();
  return { gems: Math.max(0,delta), premium: !wasPremium && owns };
}
function cloudPush(){
  if (!CLOUD || !CLOUD.sb || !CLOUD.uid) return;
  clearTimeout(CLOUD.saveT);
  CLOUD.saveT = setTimeout(async () => { try { await CLOUD.sb.from('profiles').update({ data: profile, updated_at: new Date().toISOString() }).eq('id', CLOUD.uid); } catch(e) {} }, 1500);
}
function renderCloudStatus(){ const el=$('cloudStatus'); if (!el) return; el.textContent = CLOUD.status==='on' ? 'Progress is saved to your guest account.' : CLOUD.status==='error' ? 'Cloud save is unavailable right now. Progress is kept in this browser.' : ''; }
async function buyPack(pack){
  if (!(await CLOUD.ready)){ notice('Purchases need a connection to the game server. Try again in a moment.'); return; }
  try {
    const { data: { session } } = await CLOUD.sb.auth.getSession();
    const res = await fetch(`${CFG.supabaseUrl}/functions/v1/create-checkout`, { method:'POST', headers:{ 'Content-Type':'application/json', Authorization:`Bearer ${session.access_token}`, apikey: CFG.supabaseAnonKey }, body: JSON.stringify({ pack }) });
    const j = await res.json().catch(() => ({}));
    if (res.ok && j.url) { location.href = j.url; return; }
    notice(j.error || 'Checkout could not start. Please try again.');
  } catch(e) { notice('Checkout could not start. Check your connection and try again.'); }
}
async function handlePurchaseReturn(){
  const q = new URLSearchParams(location.search), st = q.get('purchase'); if (!st) return;
  history.replaceState(null, '', location.pathname + location.hash);
  if (st !== 'success'){ notice('Checkout cancelled. You were not charged.'); return; }
  notice('Payment received. Adding your purchase…');
  for (let i=0; i<8; i++){
    await new Promise(r => setTimeout(r, 2500));
    const got = await cloudPull(false);
    if (got.gems || got.premium){ sfx('coin'); notice(got.premium ? 'Premium Trail Pass unlocked. Thank you!' : `${got.gems.toLocaleString()} gems added. Thank you!`); return; }
  }
  notice('Your payment went through and is still being processed. Your purchase will appear shortly.');
}

/* ---------- 1v1 duel (live room) ---------- */""")

# ---------- store buttons go to Stripe checkout ----------
rep("  const live = GEM_PACKS.some(pk => STORE_LINKS[pk.id]);", "  const live = CLOUD.status==='on' && !!CFG.paymentsEnabled;")
rep("Checkout opens on our payment provider’s secure page in a new tab. Gems are added once the payment is confirmed.", "Checkout opens on Stripe’s secure payment page. Gems are added to your account once the payment is confirmed.")
rep("const url=STORE_LINKS[pk.id]; return `<div class=\"pack ", "return `<div class=\"pack ")
rep("${url?`<a class=\"btn primary\" href=\"${url}\" target=\"_blank\" rel=\"noopener\">${pk.price}</a>`:`<button type=\"button\" class=\"btn\" disabled>${pk.price} · at launch</button>`}",
    "${live?`<button type=\"button\" class=\"btn primary\" data-buy=\"${pk.id}\">${pk.price}</button>`:`<button type=\"button\" class=\"btn\" disabled>${pk.price} · at launch</button>`}")
rep("  const url = STORE_LINKS.premium;", "  const url = CLOUD.status==='on' && !!CFG.paymentsEnabled;")
rep("${url ? `<a class=\"btn primary\" href=\"${url}\" target=\"_blank\" rel=\"noopener\">Get Premium · $5</a>`", "${url ? `<button type=\"button\" class=\"btn primary\" data-buy=\"${PREMIUM_PACK}\">Get Premium · $5</button>`")
rep("function renderPacks(){", "document.addEventListener('click', ev => { const b=ev.target.closest && ev.target.closest('button[data-buy]'); if (b){ b.disabled=true; buyPack(b.dataset.buy).finally(() => { b.disabled=false; }); } });\nfunction renderPacks(){")

# ---------- notice banner + cloud status on the home page ----------
rep('<div class="home-stats" id="homeStats"></div>', '<div class="home-stats" id="homeStats"></div>\n        <p class="meta" id="cloudStatus" style="margin:10px 0 0"></p>')
rep("</style>", ".notice{position:fixed;left:50%;bottom:max(16px,env(safe-area-inset-bottom,0px));transform:translateX(-50%);z-index:50;background:var(--sun);color:#221a00;font-weight:700;border-radius:999px;padding:10px 18px;max-width:calc(100vw - 32px);box-shadow:0 10px 26px rgba(0,0,0,.45)}\n</style>")
rep('<div class="wrap">', '<div class="notice" id="notice" role="status" hidden></div>\n<div class="wrap">')

# ---------- standalone document ----------
head_end = src.index('</style>') + len('</style>')
head, body = src[:head_end], src[head_end:]
head = head.replace('<meta name="claude:viewport-fit-sides" content="cover">\n', '')
OG = '''<meta name="description" content="Play Wildling Watch free in your browser: a creature-catching tower defense.">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Wildling Watch">
<meta property="og:url" content="https://wildlingwatch.github.io/play/">
<meta property="og:title" content="Play Wildling Watch">
<meta property="og:description" content="Station elemental wildlings, catch the rare ones and evolve your team. Free in your browser, no download.">
<meta property="og:image" content="https://wildlingwatch.github.io/assets/share.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="https://wildlingwatch.github.io/assets/share.jpg">
'''
assert head.count('<title>Wildling Watch</title>\n') == 1
head = head.replace('<title>Wildling Watch</title>\n', '<title>Wildling Watch</title>\n' + OG)
body = body.replace('<script>\n(() => {', '<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/dist/umd/supabase.min.js"></script>\n<script src="../config.js"></script>\n<script>\n(() => {', 1)
doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="description" content="A creature-catching tower defense: station elemental wildlings, catch rare ones, evolve your team and duel your friends.">
<style>:root{{color-scheme:dark;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}}body{{margin:0;font:14px/1.4 system-ui,-apple-system,sans-serif}}img{{max-width:100%}}[hidden]{{display:none!important}}</style>
{head.strip()}
</head>
<body>
{body.strip()}
</body>
</html>
"""
open(out_path, 'w', encoding='utf-8').write(doc)
print('built', out_path, len(doc))
