"use strict";
/* FMM Live Moderator - Streamer-/Moderator-App (ohne Build-Schritt, ohne externe Bibliotheken) */
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const view = $("#view");
let TOKEN = null, ME = null, DRAFT = null, STEP = 1, TAB = "wichtig";
let EVENTS = new Map(), LAST_ID = 0, ES = null, WAKE = null, AUDIO = null;

const RANK = { ok: 0, frage: 1, beobachten: 2, ausblenden: 3, stummschalten: 4, blockieren: 5, dringend: 6 };
const LABEL = { ok: "OK", frage: "Frage", beobachten: "Beobachten", ausblenden: "Ausblenden", stummschalten: "Stummschalten empfohlen", blockieren: "Blockieren empfohlen", dringend: "DRINGEND" };
const TODO = {
  dringend: "Sofort ansehen. Bei akuter Gefahr: Notruf 112. Hilfe ansprechen: TelefonSeelsorge 0800 111 0 111 (kostenlos, rund um die Uhr).",
  blockieren: "In der TikTok-App: Zuschauer antippen → blockieren und melden.",
  stummschalten: "In der TikTok-App: Zuschauer antippen → stummschalten.",
  ausblenden: "Nicht darauf eingehen. In TikTok ggf. melden. Begriff evtl. in den Schlüsselwortfilter aufnehmen.",
  beobachten: "Im Auge behalten - noch kein Handeln nötig.",
};
const STATE_TEXT = { inaktiv: "Aus", wartet: "Bereit", verbinde: "Verbinde …", live: "LIVE", fehler: "Problem" };

function toast(msg, ms = 2600) {
  const t = $("#toast"); t.textContent = msg; t.classList.remove("hidden");
  clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.add("hidden"), ms);
}

function readToken() {
  const h = new URLSearchParams(location.hash.slice(1));
  let t = h.get("t") || h.get("m");
  if (t) {
    // Token bleibt im #-Teil der Adresse (wird nie an den Server gesendet), damit ein
    // iPhone-Home-Bildschirm-Symbol den Zugang behaelt (eigener Speicher je Web-App).
    try { localStorage.setItem("fmm_token", t); } catch (e) {}
  } else {
    try { t = localStorage.getItem("fmm_token"); } catch (e) {}
  }
  return t;
}

async function api(method, path, body) {
  const res = await fetch(path, {
    method, headers: { "Authorization": "Bearer " + TOKEN, ...(body ? { "Content-Type": "application/json" } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  let data = {};
  try { data = await res.json(); } catch (e) {}
  if (!res.ok) {
    const err = new Error(typeof data.detail === "string" ? data.detail : "Fehler " + res.status);
    err.status = res.status; throw err;
  }
  return data;
}

function fmtTime(ts) { return new Date(ts * 1000).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }); }
function fmtDate(ts) { return new Date(ts * 1000).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }); }

// ------------------------------------------------------------------ Start
async function boot() {
  TOKEN = readToken();
  if (!TOKEN) {
    try {
      const cs = await (await fetch("/api/claim-status")).json();
      if (cs.claimable) return renderClaim(cs);
      if (cs.self_hosted) return renderNoToken("Öffne deinen Moderator über das Symbol auf deinem Home-Bildschirm bzw. dein Lesezeichen. Zugang verloren? Render → dein Dienst → Environment → ADMIN_TOKEN kopieren, dann diese Adresse mit /admin am Ende öffnen und „Neuer Link“ wählen.");
    } catch (e) {}
    return renderNoToken();
  }
  try {
    ME = await api("GET", "/api/me");
  } catch (e) {
    if (e.status === 401) { try { localStorage.removeItem("fmm_token"); } catch (x) {} return renderNoToken(e.message); }
    view.innerHTML = `<div class="card"><h2>Server nicht erreichbar</h2><p>${esc(e.message)}</p><button class="primary" id="retry">Erneut versuchen</button></div>`;
    $("#retry").onclick = () => location.reload();
    return;
  }
  $("#ver").textContent = "v" + ME.version;
  $("#who").textContent = ME.role === "mod" ? `Moderator-Ansicht für ${ME.streamer.name}` : ME.streamer.name;
  DRAFT = ME.settings ? JSON.parse(JSON.stringify(ME.settings)) : null;
  if (ME.role === "streamer" && !ME.streamer.setup_done) { STEP = ME.streamer.tiktok_user ? 2 : 1; renderWizard(); }
  else renderDash();
  setInterval(() => api("POST", "/api/heartbeat", { client: navigator.userAgent.slice(0, 190) }).catch(() => {}), 60000);
}

function renderClaim(cs) {
  view.innerHTML = `<div class="card"><h1>Willkommen bei deinem eigenen Live Moderator 🎉</h1>
    <p>Dein Server läuft. Jetzt machen wir ihn zu <b>deinem</b> Moderator. Das passiert nur ein einziges Mal.</p>
    ${cs.ai_available ? "" : `<div class="note warn">Hinweis: Es ist noch kein KI-Schlüssel hinterlegt. Der Moderator arbeitet dann nur mit Regeln. Du kannst ihn später eintragen: Render → dein Dienst → „Environment“ → ANTHROPIC_API_KEY → speichern.</div>`}
    <label for="cn">Wie heißt du? (Vorname oder Künstlername)</label>
    <input type="text" id="cn" maxlength="80" autocomplete="nickname">
    ${cs.needs_key ? `<label for="ck">Admin-Schlüssel</label><input type="text" id="ck" autocomplete="off" spellcheck="false">
      <p class="muted">Aus Sicherheitsgründen ist die freie Ersteinrichtung abgelaufen. Den Schlüssel findest du in deinem Render-Konto → dein Dienst → „Environment“ → ADMIN_TOKEN.</p>` : ""}
    <div class="actions"><button class="primary" id="cgo">Moderator übernehmen</button></div></div>`;
  $("#cgo").onclick = async () => {
    const name = $("#cn").value.trim(); if (!name) return toast("Bitte Namen eingeben");
    try {
      const r = await fetch("/api/claim", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, admin_key: cs.needs_key ? $("#ck").value : "" }) });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || "Fehler");
      try { localStorage.setItem("fmm_token", d.token); } catch (e) {}
      location.replace("/app#t=" + d.token); location.reload();
    } catch (e) { toast(e.message, 5000); }
  };
}

function renderNoToken(msg) {
  view.innerHTML = `<div class="card"><h2>Willkommen</h2>
  <p>${esc(msg || "Bitte öffne den persönlichen Link, den du von deiner Agentur per WhatsApp bekommen hast.")}</p>
  <p class="muted">Der Link enthält deinen persönlichen Zugang. Du brauchst kein Passwort und kein TikTok-Login.</p></div>`;
}

// ------------------------------------------------------------------ Assistent
const STEPS = 6;
function stepBar() { return `<div class="steps">${Array.from({ length: STEPS }, (_, i) => `<span class="${i < STEP ? "on" : ""}"></span>`).join("")}</div>`; }
function nav(nextLabel = "Weiter", canBack = true) {
  return `<div class="actions">${canBack && STEP > 1 ? `<button class="ghost" id="back">Zurück</button>` : ""}<button class="primary" id="next">${nextLabel}</button></div>`;
}
function bindNav(onNext) {
  const b = $("#back"); if (b) b.onclick = () => { STEP--; renderWizard(); };
  $("#next").onclick = async (ev) => {
    const btn = ev.currentTarget; btn.disabled = true;
    try { if ((await onNext()) !== false) { STEP++; renderWizard(); } }
    catch (e) { toast(e.message, 4000); }
    finally { btn.disabled = false; }
  };
}

function renderWizard() {
  window.scrollTo(0, 0);
  const s = ME.streamer;
  if (STEP === 1) {
    view.innerHTML = `<div class="card">${stepBar()}<small>Schritt 1 von ${STEPS}</small>
      <h1>Hallo ${esc(s.name)}! 👋</h1>
      <p>In wenigen Minuten ist dein KI-Moderator startklar. Er liest deinen LIVE-Chat mit, erkennt Beleidigungen, Spam und wichtige Fragen und zeigt dir oder deinem Moderator sofort, was zu tun ist.</p>
      <label for="u">Dein TikTok-Benutzername</label>
      <input type="text" id="u" placeholder="@deinname" autocapitalize="none" autocomplete="off" spellcheck="false" value="${esc(s.tiktok_user ? "@" + s.tiktok_user : "")}">
      <div class="note info">🔒 Wir fragen <b>nie</b> nach deinem TikTok-Passwort. Gib es niemandem weiter - auch nicht der Agentur.</div>
      <div class="note warn">⭐ <b>Wichtig:</b> Die Adresse oben im Browser ist jetzt dein persönlicher Zugang. Lege sie gleich als Lesezeichen an oder tippe auf Teilen → „Zum Home-Bildschirm“.</div>
      ${nav("Weiter", false)}</div>`;
    bindNav(async () => {
      const r = await api("PUT", "/api/profile", { tiktok_user: $("#u").value });
      ME.streamer.tiktok_user = r.tiktok_user; return true;
    });
  } else if (STEP === 2) {
    view.innerHTML = `<div class="card">${stepBar()}<small>Schritt 2 von ${STEPS}</small>
      <h1>So arbeitet dein Moderator</h1>
      <div class="note ok">✅ <b>Kein Login nötig.</b> Der Bot liest deinen öffentlichen LIVE-Chat über deinen Benutzernamen <b>@${esc(s.tiktok_user)}</b> mit - genau wie ein Zuschauer.</div>
      <h3>Was der Bot macht</h3>
      <ol class="howto"><li>Er prüft jeden Kommentar sofort (Regeln + KI).</li>
      <li>Wichtiges erscheint in dieser App: Beleidigungen, Spam, Belästigung, Fragen an dich.</li>
      <li>Er sagt dir genau, was zu tun ist (z. B. „stummschalten empfohlen“).</li></ol>
      <h3>Was der Bot nicht macht</h3>
      <p>Er schaltet in TikTok niemanden selbst stumm und blockiert niemanden. TikTok bietet dafür keine offizielle Schnittstelle, und wir nutzen keine Tricks mit deinem Konto. Das Ausführen übernimmst du oder dein Moderator mit zwei Fingertipps in der TikTok-App.</p>
      <h3>Tipp: Eigenen Moderator einsetzen</h3>
      <p>Wenn du nur mit dem iPhone streamst, kannst du während des LIVEs nicht in diese App schauen. Dann hilft ein Mensch als Moderator:</p>
      <ol class="howto"><li>In TikTok die Person als <b>LIVE-Moderator</b> festlegen (in den LIVE-Einstellungen unter „Moderatoren“; die genaue Bezeichnung kann je nach App-Version abweichen).</li>
      <li>Der Person den <b>Moderator-Link</b> dieser App schicken (gibt es später unter „Einstellungen“). Sie sieht dann alle Hinweise live auf ihrem eigenen Handy.</li></ol>
      <p class="muted">Der Moderator bekommt nur Lesezugriff. Deine Einstellungen kann er nicht ändern.</p>
      ${nav("Verstanden, weiter")}</div>`;
    bindNav(async () => true);
  } else if (STEP === 3) {
    view.innerHTML = `<div class="card">${stepBar()}<small>Schritt 3 von ${STEPS}</small>
      <h1>Moderationsregeln</h1>${rulesForm()}${nav("Speichern & weiter")}</div>`;
    bindRulesForm();
    bindNav(async () => { readRulesForm(); await saveSettings(); return true; });
  } else if (STEP === 4) {
    view.innerHTML = `<div class="card">${stepBar()}<small>Schritt 4 von ${STEPS}</small>
      <h1>KI-Funktionen</h1>${aiForm()}${nav("Speichern & weiter")}</div>`;
    bindNav(async () => { readAiForm(); await saveSettings(); return true; });
  } else if (STEP === 5) {
    view.innerHTML = `<div class="card">${stepBar()}<small>Schritt 5 von ${STEPS}</small>
      <h1>Verbindung testen</h1>
      <p>1. Wir prüfen, ob dein TikTok-Konto <b>@${esc(s.tiktok_user)}</b> erreichbar ist.</p>
      <button id="tc" class="primary" style="width:100%">Verbindung testen</button>
      <div id="tcr"></div>
      <h3>2. Probiere den Moderator aus</h3>
      <p class="muted">Schreib eine Testnachricht, wie sie im Chat stehen könnte, z. B. eine Frage oder einen Spam-Link.</p>
      <div class="row"><input type="text" id="tm" placeholder="Wann kommt das nächste LIVE?" maxlength="300"><button id="tmb" style="flex:none">Prüfen</button></div>
      <div id="tmr"></div>
      ${nav("Weiter")}</div>`;
    $("#tc").onclick = testConnection;
    $("#tmb").onclick = testMessage;
    $("#tm").onkeydown = (e) => { if (e.key === "Enter") testMessage(); };
    bindNav(async () => true);
  } else if (STEP === 6) {
    view.innerHTML = `<div class="card">${stepBar()}<small>Schritt 6 von ${STEPS}</small>
      <h1>Bot aktivieren</h1>
      <p>Sobald du aktivierst, wartet der Moderator in der Cloud auf dein nächstes LIVE und startet automatisch. Dein Handy oder PC muss dafür <b>nicht</b> eingeschaltet sein.</p>
      <div class="note warn"><b>Vor jedem LIVE (einmalig einrichten):</b> Kopiere die Wortliste in den Schlüsselwortfilter deiner TikTok-LIVE-Einstellungen. Dann blendet TikTok diese Wörter selbst sofort aus.</div>
      ${keywordBox()}
      ${nav("Bot jetzt aktivieren")}</div>`;
    bindKeywordBox();
    bindNav(async () => {
      await api("POST", "/api/setup-complete");
      ME = await api("GET", "/api/me");
      toast("Bot ist aktiv ✅"); renderDash(); return false;
    });
  }
}

async function saveSettings() {
  const r = await api("PUT", "/api/settings", DRAFT);
  DRAFT = r.settings; ME.settings = JSON.parse(JSON.stringify(r.settings)); ME.keyword_filter = r.keyword_filter;
}

function rulesForm() {
  const presets = Object.entries(ME.presets).map(([k, label]) =>
    `<label class="choice ${DRAFT.preset === k ? "sel" : ""}"><input type="radio" name="preset" value="${k}" ${DRAFT.preset === k ? "checked" : ""}>${esc(label)}</label>`).join("");
  const cats = Object.entries(ME.categories).map(([k, label]) =>
    `<label class="toggle"><input type="checkbox" data-cat="${k}" ${DRAFT.categories[k] !== false ? "checked" : ""}><div><b>${esc(label)}</b></div></label>`).join("");
  return `<h3>Wie streng?</h3>${presets}
    <h3>Was soll erkannt werden?</h3>${cats}
    <label class="toggle"><input type="checkbox" id="links" ${DRAFT.block_links ? "checked" : ""}><div><b>Links und Werbung melden</b><small>Webadressen, Telegram, „Insta:“ …</small></div></label>
    <label class="toggle"><input type="checkbox" id="base" ${DRAFT.use_base_list ? "checked" : ""}><div><b>Grundliste verbotener Wörter nutzen</b><small>Gängige Beleidigungen und Hassbegriffe (von uns gepflegt)</small></div></label>
    <label for="bw">Eigene verbotene Wörter <small>(eins pro Zeile)</small></label>
    <textarea id="bw" placeholder="z. B. Spitznamen von Hatern">${esc((DRAFT.blocked_words || []).join("\n"))}</textarea>
    <label for="au">Vertrauenswürdige Zuschauer <small>(werden nie gemeldet, eins pro Zeile)</small></label>
    <textarea id="au" placeholder="@bestefreundin">${esc((DRAFT.allowed_users || []).map((u) => "@" + u).join("\n"))}</textarea>`;
}
function bindRulesForm() {
  view.querySelectorAll("input[name=preset]").forEach((r) => r.onchange = () => {
    view.querySelectorAll(".choice").forEach((c) => c.classList.toggle("sel", $("input", c).checked));
  });
}
function readRulesForm() {
  const p = view.querySelector("input[name=preset]:checked"); if (p) DRAFT.preset = p.value;
  view.querySelectorAll("[data-cat]").forEach((c) => DRAFT.categories[c.dataset.cat] = c.checked);
  DRAFT.block_links = $("#links").checked; DRAFT.use_base_list = $("#base").checked;
  DRAFT.blocked_words = $("#bw").value.split(/\n|,/).map((x) => x.trim()).filter(Boolean);
  DRAFT.allowed_users = $("#au").value.split(/\n|,/).map((x) => x.trim().replace(/^@/, "")).filter(Boolean);
}
function aiForm() {
  const a = DRAFT.ai;
  const off = ME.ai_available ? "" : `<div class="note warn">Die KI ist auf dem Server gerade nicht eingerichtet. Bis dahin arbeitet der Moderator nur mit Regeln (Wortliste, Links, Spam, Fragen mit „?“).</div>`;
  return `${off}
    <label class="toggle"><input type="checkbox" id="ai_on" ${a.enabled ? "checked" : ""}><div><b>KI-Prüfung</b><small>Erkennt auch versteckte Beleidigungen, Ironie, Belästigung und Drohungen, die keine Wortliste findet.</small></div></label>
    <label class="toggle"><input type="checkbox" id="ai_q" ${a.questions ? "checked" : ""}><div><b>Fragen hervorheben</b><small>Echte Fragen an dich landen im Tab „Fragen“, damit keine untergeht.</small></div></label>
    <label class="toggle"><input type="checkbox" id="ai_s" ${a.reply_suggestions ? "checked" : ""}><div><b>Antwortvorschläge</b><small>Kurzer Vorschlag, was du auf eine Frage antworten könntest.</small></div></label>
    <label for="hr">Deine Hausregeln <small>(optional, in eigenen Worten)</small></label>
    <textarea id="hr" maxlength="800" placeholder="z. B. Keine Fragen nach meinem Wohnort. Kritik an meinem Aussehen ausblenden. Werbung für andere Streamer ist okay.">${esc(a.house_rules || "")}</textarea>
    <p class="muted">Die KI prüft Kommentare über Anthropic (Claude). Es werden nur Kommentartext und Anzeigename übertragen.</p>`;
}
function readAiForm() {
  DRAFT.ai = { enabled: $("#ai_on").checked, questions: $("#ai_q").checked, reply_suggestions: $("#ai_s").checked, house_rules: $("#hr").value.trim() };
}
function keywordBox() {
  const list = (ME.keyword_filter || []).join(", ");
  return `<label>Wortliste für den TikTok-Schlüsselwortfilter <small>(${(ME.keyword_filter || []).length} Begriffe)</small></label>
    <div class="kw" id="kwl">${esc(list)}</div>
    <div class="actions"><button id="kwc">Liste kopieren</button></div>
    <ol class="howto muted"><li>TikTok öffnen → LIVE vorbereiten → Einstellungen (Zahnrad).</li>
    <li>Kommentar-Einstellungen → Schlüsselwörter filtern (Bezeichnung je nach App-Version).</li>
    <li>Begriffe einfügen und speichern. TikTok erlaubt bis zu 200 Begriffe.</li></ol>`;
}
function bindKeywordBox() {
  const b = $("#kwc"); if (!b) return;
  b.onclick = async () => {
    const txt = (ME.keyword_filter || []).join(", ");
    try { await navigator.clipboard.writeText(txt); toast("Kopiert ✅"); }
    catch (e) { const r = document.createRange(); r.selectNodeContents($("#kwl")); getSelection().removeAllRanges(); getSelection().addRange(r); toast("Text markiert - bitte kopieren"); }
  };
}

async function testConnection() {
  const out = $("#tcr"); out.innerHTML = `<div class="note info">Prüfe … (kann bis zu 20 Sekunden dauern)</div>`;
  try {
    const r = await api("POST", "/api/test-connection");
    out.innerHTML = `<div class="note ${r.ok ? "ok" : "bad"}">${r.ok ? "✅" : "⚠️"} ${esc(r.message)}</div>`;
  } catch (e) { out.innerHTML = `<div class="note bad">⚠️ ${esc(e.message)}</div>`; }
}
async function testMessage() {
  const text = $("#tm").value.trim(); if (!text) return;
  const out = $("#tmr"); out.innerHTML = `<div class="note info">Moderator prüft …</div>`;
  try {
    const r = await api("POST", "/api/test-message", { text });
    out.innerHTML = eventHtml(r.event, true);
  } catch (e) { out.innerHTML = `<div class="note bad">⚠️ ${esc(e.message)}</div>`; }
}

// ------------------------------------------------------------------ Live-Ansicht
function eventHtml(e, isTest = false) {
  const d = e.decision;
  const cat = e.category && ME.categories[e.category] ? ME.categories[e.category] : "";
  const todo = TODO[d] ? `<div class="todo">👉 ${esc(TODO[d])}</div>` : "";
  const sugg = e.suggestion ? `<div class="sugg">💬 KI-Antwortidee (ungeprüft): ${esc(e.suggestion)}</div>` : "";
  const handle = e.viewer_handle ? ` <span>@${esc(e.viewer_handle)}</span>` : "";
  const btn = (!isTest && RANK[d] >= 2) ? `<div class="actions" style="margin-top:8px"><button class="small ghost" data-done="${e.id}">${e.handled ? "Erledigt ✓" : "Als erledigt markieren"}</button></div>` : "";
  return `<div class="ev d-${d} ${e.handled ? "handled" : ""}" id="ev${e.id || ""}">
    <div class="meta"><span class="pill d-${d}">${esc(LABEL[d] || d)}</span>${cat ? `<span>${esc(cat)}</span>` : ""}<span>${e.ts ? fmtTime(e.ts) : ""}</span>${e.source === "ki" ? "<span>KI</span>" : e.source ? "<span>Regel</span>" : ""}</div>
    <div class="text"><b>${esc(e.viewer_name || "Zuschauer")}</b>${handle}: ${esc(e.text)}</div>
    ${e.reason ? `<div class="why muted">${esc(e.reason)}</div>` : ""}${todo}${sugg}${btn}</div>`;
}

function statusHtml(st) {
  const live = st.state === "live";
  const extra = live ? `${st.viewers ? ` · ${st.viewers} Zuschauer` : ""} · ${st.stats ? st.stats.comments : 0} Kommentare geprüft` : "";
  return `<div class="status"><span class="dot ${esc(st.state)}"></span><div style="flex:1"><b>${esc(STATE_TEXT[st.state] || st.state)}</b><br><small>${esc(st.message || "")}${extra}</small></div></div>`;
}

function renderDash() {
  const isStreamer = ME.role === "streamer";
  const tabs = [["wichtig", "Wichtig"], ["fragen", "Fragen"], ["alle", "Alle"], ["berichte", "Berichte"]];
  if (isStreamer) tabs.push(["einstellungen", "Einstellungen"]);
  tabs.push(["hilfe", "Hilfe"]);
  view.innerHTML = `
    <div class="card" id="statusCard">${statusHtml(ME.status)}
      <div class="actions">
        ${isStreamer ? `<button id="botBtn" class="${ME.streamer.bot_active ? "" : "primary"}">${ME.streamer.bot_active ? "Bot ausschalten" : "Bot einschalten"}</button>` : ""}
        <button id="wakeBtn" class="ghost">Bildschirm wach halten</button>
      </div></div>
    <div class="tabs" id="tabs">${tabs.map(([k, l]) => `<button data-tab="${k}" class="${TAB === k ? "on" : ""}">${l}<span class="badge hidden" id="b-${k}"></span></button>`).join("")}</div>
    <div id="tabBody"></div>`;
  view.querySelectorAll("[data-tab]").forEach((b) => b.onclick = () => { TAB = b.dataset.tab; renderDash(); });
  const bb = $("#botBtn");
  if (bb) bb.onclick = async () => {
    bb.disabled = true;
    try { const r = await api("POST", "/api/bot", { active: !ME.streamer.bot_active }); ME.streamer.bot_active = !ME.streamer.bot_active; ME.status = r.status; renderDash(); }
    catch (e) { toast(e.message); bb.disabled = false; }
  };
  $("#wakeBtn").onclick = toggleWake;
  if (WAKE) $("#wakeBtn").textContent = "Bildschirm bleibt an ✓";
  renderTab();
  ensureStream();
}

function renderTab() {
  const body = $("#tabBody"); if (!body) return;
  const all = [...EVENTS.values()].sort((a, b) => b.id - a.id);
  const important = all.filter((e) => RANK[e.decision] >= 2 && !e.is_test);
  const questions = all.filter((e) => e.decision === "frage" && !e.is_test);
  const openImportant = important.filter((e) => !e.handled).length;
  const bw = $("#b-wichtig"); if (bw) { bw.textContent = openImportant; bw.classList.toggle("hidden", !openImportant); }
  if (TAB === "wichtig") {
    body.innerHTML = important.length ? important.slice(0, 150).map((e) => eventHtml(e)).join("")
      : `<div class="card muted">Noch nichts Auffälliges. Hier erscheinen Beleidigungen, Spam, Belästigung und dringende Hinweise, sobald dein LIVE läuft.</div>`;
  } else if (TAB === "fragen") {
    body.innerHTML = questions.length ? questions.slice(0, 150).map((e) => eventHtml(e)).join("")
      : `<div class="card muted">Noch keine Fragen. Echte Fragen an dich erscheinen hier, damit keine untergeht.</div>`;
  } else if (TAB === "alle") {
    body.innerHTML = all.length ? all.slice(0, 200).map((e) => eventHtml(e)).join("") : `<div class="card muted">Noch keine Kommentare.</div>`;
  } else if (TAB === "berichte") { renderReports(body); return; }
  else if (TAB === "einstellungen") { renderSettings(body); return; }
  else if (TAB === "hilfe") { renderHelp(body); return; }
  body.querySelectorAll("[data-done]").forEach((b) => b.onclick = async () => {
    try { await api("POST", `/api/events/${b.dataset.done}/handled`); const ev = EVENTS.get(+b.dataset.done); if (ev) ev.handled = 1; renderTab(); }
    catch (e) { toast(e.message); }
  });
}

async function loadEvents() {
  try {
    const r = await api("GET", `/api/events?after=${LAST_ID}&limit=300`);
    r.events.forEach(addEvent);
  } catch (e) {}
}
function addEvent(e) {
  EVENTS.set(e.id, e); LAST_ID = Math.max(LAST_ID, e.id);
  if (EVENTS.size > 1500) { const oldest = [...EVENTS.keys()].sort((a, b) => a - b).slice(0, 300); oldest.forEach((k) => EVENTS.delete(k)); }
}

function ensureStream() {
  if (ES) return;
  loadEvents().then(renderTab);
  ES = new EventSource(`/api/stream?t=${encodeURIComponent(TOKEN)}`);
  ES.onmessage = (m) => {
    let p; try { p = JSON.parse(m.data); } catch (e) { return; }
    if (p.type === "status") {
      ME.status = p.status; const c = $("#statusCard"); if (c) c.firstElementChild.outerHTML = statusHtml(p.status);
    } else if (p.type === "event") {
      addEvent(p.event);
      if (p.stats && !p.event.is_test) { ME.status.stats = p.stats; const c = $("#statusCard"); if (c) c.firstElementChild.outerHTML = statusHtml(ME.status); }
      if (p.event.decision === "dringend" && !p.event.is_test) alarm();
      if (["wichtig", "fragen", "alle"].includes(TAB)) renderTab();
    } else if (p.type === "handled") {
      const ev = EVENTS.get(p.id); if (ev) { ev.handled = 1; renderTab(); }
    } else if (p.type === "session_end") { toast("LIVE beendet - Bericht unter „Berichte“", 5000); }
    else if (p.type === "revoked") { ES.close(); ES = null; try { localStorage.removeItem("fmm_token"); } catch (e) {} renderNoToken("Dieser Zugangslink wurde deaktiviert, weil ein neuer Link erzeugt wurde. Bitte öffne den neuen Link."); }
  };
  ES.onopen = () => loadEvents().then(renderTab);
}

function alarm() {
  try {
    AUDIO = AUDIO || new (window.AudioContext || window.webkitAudioContext)();
    const o = AUDIO.createOscillator(), g = AUDIO.createGain();
    o.frequency.value = 880; o.connect(g); g.connect(AUDIO.destination); g.gain.value = 0.15;
    o.start(); o.stop(AUDIO.currentTime + 0.35);
  } catch (e) {}
  if (navigator.vibrate) navigator.vibrate([200, 100, 200]);
  toast("⚠️ Dringender Hinweis im Tab „Wichtig“", 6000);
}

async function toggleWake() {
  try {
    if (WAKE) { await WAKE.release(); WAKE = null; }
    else if ("wakeLock" in navigator) { WAKE = await navigator.wakeLock.request("screen"); WAKE.addEventListener("release", () => { WAKE = null; }); }
    else toast("Dein Browser unterstützt das nicht. Tipp: Auto-Sperre in den iPhone-Einstellungen verlängern.", 5000);
  } catch (e) { toast("Nicht möglich: " + e.message); }
  renderDash();
}

async function renderReports(body) {
  body.innerHTML = `<div class="card">Lade Berichte …</div>`;
  try {
    const r = await api("GET", "/api/sessions");
    if (!r.sessions.length) { body.innerHTML = `<div class="card muted">Noch keine LIVEs aufgezeichnet. Nach deinem ersten LIVE findest du hier eine Zusammenfassung.</div>`; return; }
    body.innerHTML = `<div class="card"><h2>Deine LIVEs</h2><table><tr><th>Start</th><th>Kommentare</th><th>Auffällig</th><th></th></tr>
      ${r.sessions.map((s) => `<tr><td>${fmtDate(s.started_at)}${s.ended_at ? "" : " <span class='pill d-frage'>läuft</span>"}</td><td>${s.comments}</td><td>${s.flagged}</td><td><button class="small" data-rep="${s.id}">Bericht</button></td></tr>`).join("")}</table></div><div id="rep"></div>`;
    body.querySelectorAll("[data-rep]").forEach((b) => b.onclick = () => showReport(+b.dataset.rep));
  } catch (e) { body.innerHTML = `<div class="card">⚠️ ${esc(e.message)}</div>`; }
}
async function showReport(id) {
  const out = $("#rep"); out.innerHTML = `<div class="card">Lade …</div>`;
  try {
    const r = await api("GET", `/api/sessions/${id}/report`);
    const dec = Object.entries(r.decisions).map(([k, v]) => `<div class="stat"><small>${esc(LABEL[k] || k)}</small><b>${v}</b></div>`).join("");
    const cats = Object.entries(r.categories).map(([k, v]) => `<li>${esc(k)}: ${v}</li>`).join("") || "<li>keine</li>";
    const off = r.top_offenders.map(([n, c]) => `<li>${esc(n || "unbekannt")}: ${c}×</li>`).join("") || "<li>keine</li>";
    const qs = r.questions.map((q) => `<li><b>${esc(q.viewer)}:</b> ${esc(q.text)}</li>`).join("") || "<li>keine</li>";
    out.innerHTML = `<div class="card"><h2>Bericht vom ${fmtDate(r.session.started_at)}</h2>
      <p class="muted">Dauer: ${r.duration_min} Min. · ${r.total} Kommentare geprüft</p><div class="grid">${dec}</div>
      <h3>Verstöße nach Art</h3><ul>${cats}</ul><h3>Auffälligste Zuschauer</h3><ul>${off}</ul>
      <p class="muted">Tipp: Wiederholungstäter in TikTok blockieren.</p><h3>Fragen aus dem Chat</h3><ul>${qs}</ul></div>`;
  } catch (e) { out.innerHTML = `<div class="card">⚠️ ${esc(e.message)}</div>`; }
}

function renderSettings(body) {
  DRAFT = JSON.parse(JSON.stringify(ME.settings));
  body.innerHTML = `
    <div class="card"><h2>TikTok-Konto</h2><label for="u">Benutzername</label>
      <div class="row"><input type="text" id="u" value="@${esc(ME.streamer.tiktok_user)}" autocapitalize="none" spellcheck="false"><button id="us" style="flex:none">Speichern</button></div>
      <div class="actions"><button id="tc" class="ghost">Verbindung testen</button></div><div id="tcr"></div></div>
    <div class="card"><h2>Regeln</h2>${rulesForm()}<div class="actions"><button class="primary" id="rs">Regeln speichern</button></div></div>
    <div class="card"><h2>KI</h2>${aiForm()}<div class="actions"><button class="primary" id="as">KI-Einstellungen speichern</button></div></div>
    <div class="card"><h2>TikTok-Schlüsselwortfilter</h2>${keywordBox()}</div>
    <div class="card"><h2>Moderator-Link</h2><p>Für eine Vertrauensperson, die während deines LIVEs mitliest und in TikTok als Moderator eingetragen ist. Nur Lesezugriff.</p>
      <button id="ml">${ME.streamer.has_mod_link ? "Neuen Moderator-Link erzeugen (alter wird ungültig)" : "Moderator-Link erzeugen"}</button><div id="mlr"></div></div>
    <div class="card"><h2>Testnachricht</h2><div class="row"><input type="text" id="tm" placeholder="Testkommentar" maxlength="300"><button id="tmb" style="flex:none">Prüfen</button></div><div id="tmr"></div></div>`;
  bindRulesForm(); bindKeywordBox();
  $("#us").onclick = async () => { try { const r = await api("PUT", "/api/profile", { tiktok_user: $("#u").value }); ME.streamer.tiktok_user = r.tiktok_user; toast("Gespeichert ✅"); } catch (e) { toast(e.message, 4000); } };
  $("#tc").onclick = testConnection;
  $("#rs").onclick = async () => { try { readRulesForm(); await saveSettings(); toast("Regeln gespeichert ✅"); renderTab(); } catch (e) { toast(e.message, 4000); } };
  $("#as").onclick = async () => { try { readAiForm(); await saveSettings(); toast("Gespeichert ✅"); } catch (e) { toast(e.message, 4000); } };
  $("#tmb").onclick = testMessage;
  $("#ml").onclick = async () => {
    try {
      const r = await api("POST", "/api/mod-link"); ME.streamer.has_mod_link = true;
      const msg = `Hi! Hier ist dein Moderator-Zugang für mein TikTok LIVE. Link öffnen, dann siehst du alle Hinweise live: ${r.link}`;
      $("#mlr").innerHTML = `<div class="kw">${esc(r.link)}</div><div class="actions"><a class="btn primary" target="_blank" rel="noopener" href="https://wa.me/?text=${encodeURIComponent(msg)}">Per WhatsApp senden</a><button id="mlc">Kopieren</button></div>`;
      $("#mlc").onclick = () => navigator.clipboard.writeText(r.link).then(() => toast("Kopiert ✅"), () => toast("Bitte manuell kopieren"));
    } catch (e) { toast(e.message); }
  };
}

function renderHelp(body) {
  body.innerHTML = `<div class="card"><h2>Kurzanleitung</h2>
    <ol class="howto"><li>Bot eingeschaltet lassen. Er startet bei jedem LIVE automatisch - auch wenn du nur mit dem iPhone streamst.</li>
    <li>Tab <b>Wichtig</b>: Hier stehen Kommentare, auf die du oder dein Moderator reagieren sollten - mit konkreter Empfehlung.</li>
    <li>Tab <b>Fragen</b>: Fragen aus dem Chat, damit keine untergeht.</li>
    <li>Stummschalten / Blockieren machst du in der TikTok-App (Zuschauer antippen).</li>
    <li>Nach dem LIVE: Tab <b>Berichte</b>.</li></ol>
    <h3>Gut zu wissen</h3>
    <ul><li>Wir brauchen nie dein TikTok-Passwort.</li><li>Die KI kann sich irren - du entscheidest.</li>
    <li>Kommentare werden nach 30 Tagen automatisch gelöscht.</li><li>Fragen? Melde dich bei deiner Agentur.</li></ul>
    <p><a href="/anleitung" target="_blank">Ausführliche Anleitung</a> · <a href="/datenschutz" target="_blank">Datenschutzhinweise</a></p>
    <p class="muted">Tipp fürs iPhone: In Safari „Teilen“ → „Zum Home-Bildschirm“. Dann öffnet sich der Moderator wie eine App.</p></div>`;
}

boot();
