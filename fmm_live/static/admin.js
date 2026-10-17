"use strict";
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
let TOKEN = "";
try { TOKEN = sessionStorage.getItem("fmm_admin") || ""; } catch (e) {}
{
  // Admin-Link: /admin#k=<ADMIN_TOKEN> - der #-Teil wird nie an den Server gesendet
  const k = new URLSearchParams(location.hash.slice(1)).get("k");
  if (k) { TOKEN = k; try { sessionStorage.setItem("fmm_admin", k); } catch (e) {} history.replaceState(null, "", "/admin"); }
}
const STATE = { inaktiv: "Aus", wartet: "Bereit (wartet auf LIVE)", verbinde: "Verbinde", live: "LIVE", fehler: "Fehler" };

function toast(m, ms = 3000) { const t = $("#toast"); t.textContent = m; t.classList.remove("hidden"); clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.add("hidden"), ms); }
const ago = (ts) => { if (!ts) return "nie"; const s = Date.now() / 1000 - ts; if (s < 90) return "gerade eben"; if (s < 3600) return Math.round(s / 60) + " Min."; if (s < 86400) return Math.round(s / 3600) + " Std."; return Math.round(s / 86400) + " Tage"; };

async function api(method, path, body) {
  const r = await fetch(path, { method, headers: { Authorization: "Bearer " + TOKEN, ...(body ? { "Content-Type": "application/json" } : {}) }, body: body ? JSON.stringify(body) : undefined });
  let d = {}; try { d = await r.json(); } catch (e) {}
  if (!r.ok) { const e = new Error(d.detail || "Fehler " + r.status); e.status = r.status; throw e; }
  return d;
}

function whatsappText(name, link) {
  return `Hi ${name}! 👋 Hier ist dein persönlicher Zugang zum FMM Live Moderator - deiner KI-Chatmoderation für TikTok LIVE.\n\n` +
    `1. Link antippen: ${link}\n2. Den Schritten folgen (ca. 5 Minuten)\n3. Fertig - der Moderator startet bei jedem LIVE automatisch.\n\n` +
    `Du brauchst keine App und kein Passwort. Gib dein TikTok-Passwort niemals weiter - auch nicht an uns. Bitte leite diesen Link nicht weiter, er ist dein persönlicher Zugang. Bei Fragen melde dich einfach!`;
}
function linkBox(name, link) {
  const msg = whatsappText(name, link);
  return `<div class="note ok"><b>Zugangslink für ${esc(name)}</b> (nur jetzt sichtbar - bitte direkt versenden):
    <div class="kw" style="margin-top:6px">${esc(link)}</div>
    <div class="actions"><a class="btn primary" target="_blank" rel="noopener" href="https://wa.me/?text=${encodeURIComponent(msg)}">Per WhatsApp senden</a>
    <button class="cp" data-v="${esc(msg)}">Nachricht kopieren</button><button class="cp" data-v="${esc(link)}">Nur Link kopieren</button></div></div>`;
}
function bindCopy(root) {
  root.querySelectorAll(".cp").forEach((b) => b.onclick = () => navigator.clipboard.writeText(b.dataset.v).then(() => toast("Kopiert ✅"), () => toast("Bitte manuell kopieren")));
}

async function load() {
  try {
    const d = await api("GET", "/api/admin/overview");
    $("#login").classList.add("hidden"); $("#main").classList.remove("hidden");
    $("#ver").textContent = "Server v" + d.version;
    const live = d.streamers.filter((s) => s.status.state === "live").length;
    const active = d.streamers.filter((s) => s.bot_active && !s.disabled).length;
    const cost = d.streamers.reduce((a, s) => a + (s.usage_30d.cost_usd || 0), 0);
    const err = d.streamers.reduce((a, s) => a + s.errors_24h, 0);
    $("#kpis").innerHTML = [
      ["Streamer", d.streamers.length], ["Bots aktiv", active], ["Gerade LIVE", live],
      ["KI-Kosten 30 Tage", "$" + cost.toFixed(3)], ["Fehler 24 h", err],
      ["KI", d.ai_available ? esc(d.model) : "nicht eingerichtet"], ["Laufzeit", Math.round(d.uptime_s / 3600) + " Std."],
    ].map(([k, v]) => `<div class="stat"><small>${k}</small><b>${v}</b></div>`).join("");
    $("#tbl").innerHTML = `<tr><th>Streamer</th><th>TikTok</th><th>Bot</th><th>Status</th><th>Zuletzt geöffnet</th><th>Letztes LIVE</th><th>KI 30 T.</th><th>Fehler 24h</th><th>Version</th><th></th></tr>` +
      d.streamers.map((s) => `<tr>
        <td><b>${esc(s.name)}</b>${s.disabled ? " <span class='pill d-blockieren'>gesperrt</span>" : ""}${!s.setup_done ? " <span class='pill'>Einrichtung offen</span>" : ""}</td>
        <td>${s.tiktok_user ? "@" + esc(s.tiktok_user) : "-"}</td>
        <td>${s.bot_active ? "an" : "aus"}</td>
        <td><span class="dot ${esc(s.status.state)}" style="display:inline-block;vertical-align:middle"></span> ${esc(STATE[s.status.state] || s.status.state)}<br><small>${esc(s.status.message)}</small></td>
        <td>${ago(s.last_seen_at)}</td>
        <td>${s.last_session ? ago(s.last_session.started_at) + "<br><small>" + s.last_session.comments + " Komm. / " + s.last_session.flagged + " auff.</small>" : "-"}</td>
        <td>$${(s.usage_30d.cost_usd || 0).toFixed(3)}<br><small>${s.usage_30d.calls || 0} Aufrufe</small></td>
        <td>${s.errors_24h}</td><td>${esc(s.version)}</td>
        <td><button class="small" data-rot="${s.id}" data-name="${esc(s.name)}">Neuer Link</button>
          <button class="small ghost" data-dis="${s.id}" data-on="${s.disabled ? 0 : 1}">${s.disabled ? "Entsperren" : "Sperren"}</button>
          <button class="small ghost" data-del="${s.id}" data-name="${esc(s.name)}">Löschen</button></td></tr>`).join("");
    $("#err").innerHTML = `<tr><th>Zeit</th><th>Streamer</th><th>Bereich</th><th>Meldung</th></tr>` + (d.errors.length ? d.errors.map((e) => {
      const s = d.streamers.find((x) => x.id === e.streamer_id);
      return `<tr><td>${new Date(e.ts * 1000).toLocaleString("de-DE")}</td><td>${esc(s ? s.name : "-")}</td><td>${esc(e.area)}</td><td>${esc(e.message)}</td></tr>`;
    }).join("") : `<tr><td colspan="4" class="muted">Keine Fehler 🎉</td></tr>`);
    document.querySelectorAll("[data-rot]").forEach((b) => b.onclick = async () => {
      if (!confirm(`Neuen Zugangslink für ${b.dataset.name} erzeugen? Der alte Link funktioniert dann nicht mehr.`)) return;
      try { const r = await api("POST", `/api/admin/streamers/${b.dataset.rot}/rotate`); $("#nr").innerHTML = linkBox(b.dataset.name, r.link); bindCopy($("#nr")); scrollTo(0, 0); } catch (e) { toast(e.message); }
    });
    document.querySelectorAll("[data-dis]").forEach((b) => b.onclick = async () => {
      try { await api("POST", `/api/admin/streamers/${b.dataset.dis}/disable?on=${b.dataset.on === "1"}`); load(); } catch (e) { toast(e.message); }
    });
    document.querySelectorAll("[data-del]").forEach((b) => b.onclick = async () => {
      if (prompt(`Alle Daten von ${b.dataset.name} endgültig löschen? Zum Bestätigen LÖSCHEN eingeben.`) !== "LÖSCHEN") return;
      try { await api("DELETE", `/api/admin/streamers/${b.dataset.del}`); toast("Gelöscht"); load(); } catch (e) { toast(e.message); }
    });
  } catch (e) {
    if (e.status === 401 || e.status === 503) { $("#main").classList.add("hidden"); $("#login").classList.remove("hidden"); if (TOKEN) toast(e.message); }
    else toast(e.message);
  }
}

$("#go").onclick = () => { TOKEN = $("#tok").value.trim(); try { sessionStorage.setItem("fmm_admin", TOKEN); } catch (e) {} load(); };
$("#out").onclick = () => { TOKEN = ""; try { sessionStorage.removeItem("fmm_admin"); } catch (e) {} location.reload(); };
$("#nb").onclick = async () => {
  const name = $("#nn").value.trim(); if (!name) return toast("Bitte Namen eingeben");
  try { const r = await api("POST", "/api/admin/streamers", { name, preset: $("#np").value }); $("#nn").value = ""; $("#nr").innerHTML = linkBox(name, r.link); bindCopy($("#nr")); load(); }
  catch (e) { toast(e.message); }
};
if (TOKEN) load(); else $("#login").classList.remove("hidden");
setInterval(() => { if (TOKEN && !$("#main").classList.contains("hidden")) load(); }, 15000);
