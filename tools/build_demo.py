"""Build the free demo from the full game.
Usage: python3 build_demo.py wildling-watch.html demo-artifact.html itch/index.html
The demo has the first 4 campaign trails, 2 Endless maps and the first Boss Drop boss.
It has no real-money purchases, no duels and no promo codes, and it links to the full game."""
import sys
src_path, art_out, itch_out = sys.argv[1], sys.argv[2], sys.argv[3]
src = open(src_path, encoding='utf-8').read()

# Where the "Get the full game" buttons go. Leave empty until the full version has a public URL.
FULL_GAME_URL = 'https://wildlingwatch.github.io/'

def rep(old, new, count=1):
    global src
    n = src.count(old)
    assert n == count, (n, old[:100])
    src = src.replace(old, new)

DEMO_TRAILS, DEMO_ENDLESS = 4, 1   # Endless is locked in the demo; its card previews the first trail

# ---------- identity ----------
rep('<title>Wildling Watch</title>', '<title>Wildling Watch Demo</title>')
rep('      <h1>Wildling Watch</h1>', '      <h1>Wildling Watch <span class="demo-tag">Demo</span></h1>')
# separate save data from the full game (itch.io serves many games from one domain)
for k in ['audio', 'best-', 'diff', 'duelname', 'endless-map', 'profile']:
    src = src.replace(f"'wildling-{k}", f"'wildling-demo-{k}")

# ---------- demo settings + upsell helper ----------
rep("(() => {\n", f"""(() => {{
// ===== DEMO BUILD =====
const DEMO_TRAILS = {DEMO_TRAILS}, DEMO_ENDLESS = {DEMO_ENDLESS}, FULL_GAME_URL = {FULL_GAME_URL!r};
const fullLink = (label='Get the full game') => FULL_GAME_URL ? `<a class="btn primary" href="${{FULL_GAME_URL}}" target="_blank" rel="noopener">${{label}}</a>` : `<span class="meta">The full game is coming soon.</span>`;
""", 1)

# ---------- content limits ----------
rep("const endlessLevel = () => Math.max(0, LEVELS.findIndex(L=>L.id===endlessMap));",
    "const endlessLevel = () => Math.min(DEMO_ENDLESS-1, Math.max(0, LEVELS.findIndex(L=>L.id===endlessMap)));")
rep("esel.innerHTML = LEVELS.map((Lv,i)=>", "esel.innerHTML = LEVELS.slice(0,DEMO_ENDLESS).map((Lv,i)=>")
rep("const SDd=SD(diff), st=SDd[L.id]||0, open = i===0 || (SDd[LEVELS[i-1].id]||0)>0;",
    "const SDd=SD(diff), st=SDd[L.id]||0, full=i>=DEMO_TRAILS, open = !full && (i===0 || (SDd[LEVELS[i-1].id]||0)>0);")
rep("${open?'':'<span class=\"meta\">Clear the trail before it to open</span>'}",
    "${full?'<span class=\"meta demo-lock\">Full game</span>':open?'':'<span class=\"meta\">Clear the trail before it to open</span>'}")
rep("        <div class=\"levels\" id=\"levels\"></div>", "        <div class=\"demo-note\" id=\"demoCamp\"></div>\n        <div class=\"levels\" id=\"levels\"></div>")
rep("  $('winNext').hidden = S.level>=LEVELS.length-1;",
    "  $('winNext').hidden = S.level>=DEMO_TRAILS-1;\n  if (S.level>=DEMO_TRAILS-1) $('winText').textContent += ` That's every trail in the demo. The full game has ${LEVELS.length} trails, duels and more.`;")
# Boss Drop: only the first boss
rep("""<button type="button" class="btn ${afford?'primary':''}" data-boss="${i}" ${afford?'':'disabled'}>Fight · ${B.cost} gems</button>""",
    """${B.tier>0 ? `<div class="demo-note">This boss is in the full game. ${fullLink()}</div>` : `<button type="button" class="btn ${afford?'primary':''}" data-boss="${i}" ${afford?'':'disabled'}>Fight · ${B.cost} gems</button>`}""")
rep("  const i=+b.dataset.boss, B=BOSSES[i];", "  const i=+b.dataset.boss, B=BOSSES[i]; if (B.tier>0) return;")

# ---------- Endless is a full-game mode: show it locked, with a link ----------
rep("""      <div class="card endless-card">
        <h2>Endless</h2>
        <p class="empty">The waves never stop. Pick any trail from the campaign and see how long you can hold it. Your best wave is kept for each trail and difficulty. Endless runs are not saved, so play them in one sitting.</p>
        <label class="fld" for="endlessMap">Trail<select id="endlessMap"></select></label>
        <canvas id="endlessPreview" width="384" height="240" aria-hidden="true"></canvas>
        <dl class="kv" id="endlessBests"></dl>
        <button class="btn primary" id="playEndless" type="button">Play Endless</button>
      </div>""", """      <div class="card endless-card endless-locked" id="endlessCard">
        <div class="up-head"><h2>Endless</h2><span class="lock-chip"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>Full game</span></div>
        <div class="el-prev"><canvas id="endlessPreview" width="384" height="240" aria-hidden="true"></canvas><div class="el-ov"><b>∞</b><span>Endless mode</span></div></div>
        <p class="empty">How long can you hold the trail? The waves never stop, a titan arrives every 10th wave, and your best wave is kept for every trail and difficulty. Endless is part of the full game.</p>
        <div id="demoEndless"></div>
        <div hidden><select id="endlessMap"></select><dl id="endlessBests"></dl><button id="playEndless" type="button">Play Endless</button></div>
      </div>""")
rep("$('homeEndless').addEventListener('click', () => startRun('endless'));", "$('homeEndless').addEventListener('click', () => showEndlessLock());")
rep("function startRun(m, li=0){\n", """function showEndlessLock(){
  openMenu(); const c=$('endlessCard'); if (!c) return;
  try { c.scrollIntoView({block:'center'}); } catch(e) {}
  c.classList.remove('flash'); void c.offsetWidth; c.classList.add('flash');
}
function startRun(m, li=0){
  if (m==='endless'){ showEndlessLock(); return; }
""")
rep("""          <button class="btn big" id="homeEndless" type="button">Quick Endless</button>""", """          <button class="btn big" id="homeEndless" type="button">Endless · full game</button>""")

# Endless achievements can't be earned in the demo
import re as _re
src = _re.sub(r"  \{id:'wave(25|50)', g:'ach'[^\n]*\n", "", src)
assert "id:'wave25'" not in src

rep(": `Endless · ${LEVELS[endlessLevel()].name}`;", ": 'Free demo';")

# ---------- no real money, no duels, no promo codes ----------
rep("""      <div class="gemstore">""", """      <div class="demo-note big" id="demoShop"></div>
      <div class="gemstore" hidden>""")
rep("""`<button type="button" class="btn" disabled>Premium · $5 · at launch</button>`}<span class="meta">One-time purchase for this season. Rewards for tiers you have already reached unlock right away.</span>""",
    """fullLink('Get the full game')}<span class="meta">The premium pass is part of the full game. The free row of rewards is yours to claim here.</span>""")
rep("""          <button class="btn big" id="homeDuel" type="button">1v1 Duel</button>""", """          <button class="btn big" id="homeDuel" type="button" hidden>1v1 Duel</button>""")

# ---------- upsell copy ----------
rep("""        <div class="home-stats" id="homeStats"></div>""", """        <div class="home-stats" id="homeStats"></div>
        <div class="demo-note" id="demoHome"></div>""")
rep("function renderHome(){\n", f"""function renderHome(){{
  $('demoHome').innerHTML = `<p>You're playing the <b>free demo</b>: the first {DEMO_TRAILS} trails on every difficulty and the Thorn King boss. The full game adds <b>Endless mode</b>, 8 more trails, 1v1 duels with friends, two more bosses and the premium Trail Pass.</p>${{fullLink()}}`;
""", 1)
rep("function renderMenu(){\n", """function renderMenu(){
  $('demoEndless').innerHTML = fullLink('Play Endless in the full game');
  $('demoCamp').innerHTML = `<p>The demo includes trails 1 to ${DEMO_TRAILS} on every difficulty. Campaign badges need all ${LEVELS.length} trails, which come with the full game.</p>${fullLink('Unlock all trails')}`;
  $('demoShop').innerHTML = `<p><b>Gem packs and the premium Trail Pass are in the full game.</b> In the demo, earn gems by clearing waves and trails, beating the Thorn King and claiming achievements.</p>${fullLink()}`;
""", 1)
rep(".menu-head .starbank .btn{", """.demo-tag{display:inline-block;vertical-align:middle;font-family:var(--f-data);font-size:11px;letter-spacing:.14em;color:#221a00;background:var(--sun);border-radius:6px;padding:3px 7px;margin-left:6px;transform:translateY(-3px)}
.demo-note{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;justify-content:space-between;background:linear-gradient(100deg,rgba(255,201,74,.14),rgba(255,201,74,.04));border:1px solid rgba(255,201,74,.45);border-radius:10px;padding:10px 12px;margin:10px 0;font-size:13px}
.demo-note p{margin:0;max-width:70ch;line-height:1.5}
.demo-note .btn{text-decoration:none}
.demo-note.big{margin:0 0 14px}
.demo-lock{color:var(--sun)}
.lock-chip{display:inline-flex;align-items:center;gap:5px;font-family:var(--f-data);font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:#221a00;background:var(--sun);border-radius:999px;padding:3px 9px}
.lock-chip svg{width:12px;height:12px;fill:none;stroke:#221a00;stroke-width:2.4}
.el-prev{position:relative;margin:0 0 12px;border-radius:8px;overflow:hidden}
.el-prev canvas{display:block;width:100%;height:auto;filter:saturate(.55) brightness(.6)}
.el-ov{position:absolute;inset:0;display:grid;place-content:center;justify-items:center;gap:2px;text-align:center}
.el-ov b{font-family:var(--f-display);font-weight:400;font-size:54px;line-height:1;color:var(--sun);text-shadow:0 3px 14px rgba(0,0,0,.6)}
.el-ov span{font-family:var(--f-display);font-size:18px;color:var(--ink);text-shadow:0 2px 10px rgba(0,0,0,.7)}
.endless-locked{border-color:rgba(255,201,74,.45)}
.endless-locked.flash{animation:elflash 1.2s ease}
@keyframes elflash{0%,100%{box-shadow:none}30%{box-shadow:0 0 0 3px var(--sun),0 0 30px rgba(255,201,74,.35)}}
@media (prefers-reduced-motion: reduce){.endless-locked.flash{animation:none}}
.menu-head .starbank .btn{""")

open(art_out, 'w', encoding='utf-8').write(src)

# ---------- standalone page for itch.io ----------
head_end = src.index('</style>') + len('</style>')
head, body = src[:head_end], src[head_end:]
head = head.replace('<meta name="claude:viewport-fit-sides" content="cover">\n', '')
doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="description" content="Free demo of Wildling Watch, a creature-catching tower defense.">
<style>:root{{color-scheme:dark}}body{{margin:0;font:14px/1.4 system-ui,-apple-system,sans-serif}}img{{max-width:100%}}[hidden]{{display:none!important}}</style>
{head.strip()}
</head>
<body>
{body.strip()}
</body>
</html>
"""
open(itch_out, 'w', encoding='utf-8').write(doc)
print('demo built', art_out, itch_out, len(doc))
