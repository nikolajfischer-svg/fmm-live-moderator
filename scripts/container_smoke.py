"""Rauchtest gegen einen laufenden Container (nur Standardbibliothek; laeuft in GitHub Actions).

Aufruf: python scripts/container_smoke.py <base_url> <admin_token> [phase] [live_users]
  phase "claim"   : Ersteinrichtung pruefen, Token in smoke_token.txt ablegen, optional TikTok-Diagnose
  phase "restart" : nach Container-Neustart - Zugang + Daten muessen erhalten sein
"""
import json
import sys
import time
import urllib.error
import urllib.request


def http(method, url, token="", body=None, timeout=60):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read().decode()


def main():
    base, admin = sys.argv[1].rstrip("/"), sys.argv[2]
    phase = sys.argv[3] if len(sys.argv) > 3 else "claim"
    live_users = [u for u in (sys.argv[4] if len(sys.argv) > 4 else "").split(",") if u.strip()]
    fails = []

    def check(cond, msg):
        print(("OK   " if cond else "FEHL ") + msg)
        if not cond:
            fails.append(msg)

    for _ in range(40):
        try:
            if http("GET", base + "/healthz")[0] == 200:
                break
        except Exception:
            pass
        time.sleep(2)
    code, hdr, body = http("GET", base + "/healthz")
    check(code == 200, f"Container antwortet {body}")

    if phase == "claim":
        st = json.loads(http("GET", base + "/api/claim-status")[2])
        check(st["claimable"] is True and st["self_hosted"] is True, "frischer Server ist übernehmbar")
        code, _, body = http("POST", base + "/api/claim", body={"name": "Smoke"})
        data = json.loads(body)
        check(code == 200 and data.get("token"), "Ersteinrichtung erfolgreich")
        token = data.get("token", "")
        open("smoke_token.txt", "w").write(token)
        check(http("POST", base + "/api/claim", body={"name": "Fremd"})[0] == 409, "zweite Übernahme abgelehnt")
        check(http("GET", base + "/api/admin/overview", token)[0] == 401, "Streamer-Token hat keine Admin-Rechte")
        check(http("PUT", base + "/api/profile", token, {"tiktok_user": "smoke_test"})[0] == 200, "Daten schreiben")
        check("script-src 'self'" in http("GET", base + "/app")[1].get("content-security-policy", ""), "CSP aktiv")
        for user in live_users:
            code, _, body = http("POST", base + "/api/admin/diagnose", admin, {"tiktok_user": user, "seconds": 25}, 90)
            d = json.loads(body) if body.startswith("{") else {"error": body[:200]}
            print(f"     TikTok @{user}: live={d.get('live')} verbunden={d.get('connected_after_s')}s "
                  f"kommentare={d.get('comments')} fehler={d.get('error')}")
            if d.get("live") and d.get("comments", 0) > 0:
                check(True, "Rechenzentrums-IP empfängt echten TikTok-LIVE-Chat")
                break
        else:
            if live_users:
                check(False, "Rechenzentrums-IP empfängt echten TikTok-LIVE-Chat")
    else:
        token = open("smoke_token.txt").read().strip()
        code, _, body = http("GET", base + "/api/me", token)
        check(code == 200 and json.loads(body)["streamer"]["tiktok_user"] == "smoke_test",
              "nach Neustart: Zugang und Daten erhalten (Volume-Rechte ok)")
        check(json.loads(http("GET", base + "/api/claim-status")[2])["claimable"] is False,
              "nach Neustart: nicht erneut übernehmbar")
    print("ERGEBNIS:", "OK" if not fails else f"{len(fails)} Fehler")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
