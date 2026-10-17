"""Veroeffentlichung auf Fly.io + Abnahme in der Cloud + Erzeugen der beiden Links.

Aufruf (nach `flyctl auth login`):
  python scripts/cloud_release.py --app fmm-live-moderator --streamer "Lena" --live-users user1,user2
Optional: --anthropic-key-file <datei mit ANTHROPIC_API_KEY=...>  --model claude-haiku-5-5
          --operator-email ... --operator-address "..."  --skip-deploy

Secrets werden per `flyctl secrets import` ueber stdin gesetzt (nie als Kommandozeilen-Argument).
Ergebnis: Desktop/FMM_Live_Moderator_LINKS.txt (Streamer-Link, WhatsApp-Text, Admin-Link).
"""
import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
STATE = ROOT / ".release_state.json"  # lokal, in .gitignore (enthaelt den Admin-Token)


def flyctl() -> str:
    for cand in (shutil.which("flyctl"), shutil.which("fly"),
                 str(Path(os.environ.get("USERPROFILE", "")) / ".fly" / "bin" / "flyctl.exe")):
        if cand and Path(cand).exists():
            return cand
    sys.exit("flyctl nicht gefunden")


def run(args: list[str], stdin: str | None = None, check: bool = True) -> subprocess.CompletedProcess:
    print("  $ flyctl " + " ".join(a if "=" not in a else a.split("=")[0] + "=***" for a in args[1:]))
    cp = subprocess.run(args, input=stdin, text=True, capture_output=True, cwd=ROOT, encoding="utf-8", errors="replace")
    if check and cp.returncode != 0:
        print(cp.stdout[-2000:], cp.stderr[-2000:])
        sys.exit(f"Befehl fehlgeschlagen: {' '.join(args[:3])}")
    return cp


def http(method: str, url: str, token: str = "", body: dict | None = None, timeout: float = 90) -> tuple[int, dict, dict]:
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8")
            return r.status, {k.lower(): v for k, v in r.headers.items()}, (json.loads(raw) if raw.startswith(("{", "[")) else {"_text": raw[:50000]})
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {"_text": raw[:2000]}
        return e.code, {k.lower(): v for k, v in e.headers.items()}, data


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", required=True)
    ap.add_argument("--streamer", required=True)
    ap.add_argument("--live-users", required=True, help="kommagetrennte Liste aktuell laufender oeffentlicher LIVEs")
    ap.add_argument("--anthropic-key-file", default="")
    ap.add_argument("--model", default="")
    ap.add_argument("--operator-email", default="")
    ap.add_argument("--operator-address", default="")
    ap.add_argument("--region", default="fra")
    ap.add_argument("--skip-deploy", action="store_true")
    ap.add_argument("--base-url", default="", help="nur fuer Tests: andere Server-Adresse")
    ap.add_argument("--admin-token", default="", help="nur fuer Tests")
    ap.add_argument("--out", default="")
    ap.add_argument("--state", default="")
    a = ap.parse_args()
    fly = flyctl()
    global STATE
    if a.state:
        STATE = Path(a.state)
    base = a.base_url.rstrip("/") or f"https://{a.app}.fly.dev"
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    admin_token = a.admin_token or state.get("admin_token") or secrets.token_urlsafe(32)
    state["admin_token"] = admin_token
    STATE.write_text(json.dumps(state))

    if not a.skip_deploy:
        print("1) App, Speicher und Secrets")
        apps = json.loads(run([fly, "apps", "list", "--json"]).stdout or "[]")
        if not any(x.get("Name") == a.app for x in apps):
            run([fly, "apps", "create", a.app])
        toml = (ROOT / "fly.toml").read_text(encoding="utf-8")
        import re
        (ROOT / "fly.toml").write_text(re.sub(r'(?m)^app = ".*"', f'app = "{a.app}"', toml), encoding="utf-8")
        vols = json.loads(run([fly, "volumes", "list", "-a", a.app, "--json"]).stdout or "[]")
        if not any(v.get("name") == "moderator_data" for v in vols):
            run([fly, "volumes", "create", "moderator_data", "--size", "1", "--region", a.region, "-a", a.app, "--yes"])
        lines = [f"ADMIN_TOKEN={admin_token}", f"PUBLIC_URL={base}",
                 "HOSTING_INFO=Fly.io (Fly.io Inc.), Rechenzentrum Frankfurt am Main"]
        if a.anthropic_key_file:
            for line in Path(a.anthropic_key_file).read_text(encoding="utf-8").splitlines():
                if line.startswith("ANTHROPIC_API_KEY="):
                    lines.append(line.strip().replace('"', ""))
        if a.model:
            lines.append(f"LM_MODEL={a.model}")
        if a.operator_email:
            lines.append(f"OPERATOR_EMAIL={a.operator_email}")
        if a.operator_address:
            lines.append(f"OPERATOR_ADDRESS={a.operator_address}")
        run([fly, "secrets", "import", "-a", a.app, "--stage"], stdin="\n".join(lines) + "\n")
        print("2) Deploy (Build in der Fly-Cloud)")
        run([fly, "deploy", "-a", a.app, "--ha=false", "--remote-only", "--yes"])

    print("3) Abnahme in der Cloud")
    problems: list[str] = []

    def check(cond: bool, msg: str) -> None:
        print(("   OK   " if cond else "   FEHL ") + msg)
        if not cond:
            problems.append(msg)

    for _ in range(30):
        code, hdr, data = http("GET", base + "/healthz")
        if code == 200:
            break
        time.sleep(4)
    check(code == 200, f"Server erreichbar ({data})")
    code, hdr, _ = http("GET", base + "/app")
    check("script-src 'self'" in hdr.get("content-security-policy", ""), "Sicherheits-Header (CSP) aktiv")
    check("max-age" in hdr.get("strict-transport-security", ""), "HTTPS erzwungen (HSTS)")
    check(http("GET", base + "/api/admin/overview")[0] == 401, "Admin ohne Schlüssel gesperrt")
    check(http("GET", base + "/api/admin/overview", "falsch")[0] == 401, "Admin mit falschem Schlüssel gesperrt")
    check(http("GET", base + "/api/me", "erfunden")[0] == 401, "Erfundener Streamer-Link gesperrt")
    code, _, ov = http("GET", base + "/api/admin/overview", admin_token)
    check(code == 200, "Admin-Zugang funktioniert")
    check(bool(ov.get("ai_available")), f"KI eingerichtet (Modell: {ov.get('model')})")
    page = http("GET", base + "/datenschutz")[2].get("_text", "")
    check("{{" not in page, "Datenschutzseite ohne Platzhalter")

    print("4) Echter Verbindungstest Cloud -> öffentliches TikTok-LIVE")
    diag_ok = False
    for user in [u.strip() for u in a.live_users.split(",") if u.strip()]:
        code, _, d = http("POST", base + "/api/admin/diagnose", admin_token, {"tiktok_user": user, "seconds": 20})
        print(f"   @{user}: live={d.get('live')} verbunden_nach={d.get('connected_after_s')}s "
              f"kommentare={d.get('comments')} fehler={d.get('error')}")
        if d.get("live") and d.get("connected_after_s") is not None and d.get("comments", 0) > 0:
            diag_ok, live_ok_user = True, user
            break
    check(diag_ok, "Cloud empfängt echten LIVE-Chat")

    print("5) iPhone-Test (Safari-Engine) gegen die Cloud mit Test-Streamer")
    code, _, inv = http("POST", base + "/api/admin/streamers", admin_token, {"name": "Abnahme-Test"})
    test_id = inv.get("id")
    if diag_ok:
        cp = subprocess.run([sys.executable, str(ROOT / "scripts" / "iphone_test.py"), inv["link"], live_ok_user,
                             str(ROOT / "data" / "iphone_cloud")], capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
        print("   " + "\n   ".join(cp.stdout.strip().splitlines()[-22:]))
        check(cp.returncode == 0, "iPhone-Durchlauf in der Cloud fehlerfrei")
        # Widerruf pruefen: neuer Link -> alter Link wirkungslos
        t_old = inv["link"].split("#t=")[1]
        http("POST", f"{base}/api/admin/streamers/{test_id}/rotate", admin_token)
        check(http("GET", base + "/api/me", t_old)[0] == 401, "Widerruf: alter Einladungslink sofort ungültig")
        check(http("GET", base + "/api/admin/overview", t_old)[0] == 401, "Einladungslink hat keine Admin-Rechte")
    http("DELETE", f"{base}/api/admin/streamers/{test_id}", admin_token)

    if problems:
        print("\nABNAHME NICHT BESTANDEN - kein Streamer-Link erzeugt:")
        for p in problems:
            print("  - " + p)
        sys.exit(1)

    print("6) Persönlichen Streamer-Link erzeugen")
    if state.get("streamer_link"):
        link = state["streamer_link"]
    else:
        code, _, inv = http("POST", base + "/api/admin/streamers", admin_token, {"name": a.streamer})
        link = inv["link"]
        state["streamer_link"] = link
        STATE.write_text(json.dumps(state))
    admin_link = f"{base}/admin#k={admin_token}"
    msg = (f"Hi {a.streamer}! 👋 Hier ist dein persönlicher Zugang zum FMM Live Moderator - deiner "
           f"KI-Chatmoderation für TikTok LIVE.\n\n1. Link antippen: {link}\n2. Den Schritten folgen (ca. 5 Minuten)\n"
           f"3. Fertig - der Moderator startet bei jedem LIVE automatisch.\n\nDu brauchst keine App und kein Passwort. "
           f"Gib dein TikTok-Passwort niemals weiter - auch nicht an uns. Bitte leite diesen Link nicht weiter, er ist "
           f"dein persönlicher Zugang. Bei Fragen melde dich einfach!")
    out = Path(a.out) if a.out else DESKTOP / "FMM_Live_Moderator_LINKS.txt"
    out.write_text(f"STREAMER-LINK ({a.streamer}):\n{link}\n\nWHATSAPP-NACHRICHT:\n{msg}\n\n"
                   f"ADMIN-LINK (nur für dich, nicht weitergeben):\n{admin_link}\n", encoding="utf-8")
    print(f"\nFERTIG. Links und WhatsApp-Text: {out}")


if __name__ == "__main__":
    main()
