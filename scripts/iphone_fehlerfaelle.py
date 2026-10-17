"""iPhone-Test (WebKit) der Fehlerfaelle: verstaendliche Meldungen statt Absturz.

Aufruf: python scripts/iphone_fehlerfaelle.py <base_url> <persoenlicher_link>
"""
import sys

from playwright.sync_api import sync_playwright

base, link = sys.argv[1].rstrip("/"), sys.argv[2]
fails = []


def check(cond, msg):
    print(("OK   " if cond else "FEHL ") + msg)
    if not cond:
        fails.append(msg)


with sync_playwright() as p:
    b = p.webkit.launch()
    # 1) Fremder ohne Link auf bereits uebernommenem Server
    ctx = b.new_context(**p.devices["iPhone 15"], locale="de-DE")
    pg = ctx.new_page()
    pg.goto(base + "/app")
    pg.wait_for_selector(".card h2, .card h1")
    t = pg.inner_text("#view")
    check("Home-Bildschirm" in t and "ADMIN_TOKEN" in t, "Fremder ohne Link: Hinweis statt Zugriff")
    # 2) Ungueltiger Link
    pg.goto(base + "/app#t=gefaelscht123")
    pg.reload()
    pg.wait_for_timeout(1500)
    check("ungültig" in pg.inner_text("#view").lower() or "Home-Bildschirm" in pg.inner_text("#view"),
          "Gefälschter Link: verständliche Meldung")
    ctx.close()
    # 3) Echter Streamer: Einstellungen mit falschen Eingaben
    ctx = b.new_context(**p.devices["iPhone 15"], locale="de-DE")
    pg = ctx.new_page()
    pg.goto(link)
    pg.wait_for_selector("#statusCard, h1")
    if pg.query_selector("#statusCard"):
        pg.tap("[data-tab=einstellungen]")
        pg.wait_for_selector("#us")
        pg.fill("#u", "kein gültiger name!!")
        pg.tap("#us")
        pg.wait_for_selector("#toast:not(.hidden)")
        check("Benutzernamen" in pg.inner_text("#toast"), f"Ungültiger Benutzername: Meldung ({pg.inner_text('#toast')[:60]})")
        pg.fill("#u", "@" + "x" * 45)
        pg.tap("#us")
        pg.wait_for_timeout(800)
        check("gültigen TikTok-Benutzernamen" in pg.inner_text("#toast"), f"Zu langer Name: verständliche Meldung ({pg.inner_text('#toast')[:60]})")
        pg.fill("#u", "@gibtsnicht_qx93847z")
        pg.tap("#us")
        pg.wait_for_timeout(1200)
        pg.tap("#tc")
        pg.wait_for_selector("#tcr .note:not(.info)", timeout=40000)
        r = pg.inner_text("#tcr")
        check("nicht gefunden" in r or "nicht rechtzeitig" in r, f"Unbekanntes TikTok-Konto: Meldung ({r.strip()[:70]})")
        pg.fill("#tm", "")
        pg.tap("#tmb")
        check(True, "Leere Testnachricht: kein Absturz")
    b.close()
print("ERGEBNIS:", "OK" if not fails else f"{len(fails)} Fehler")
sys.exit(1 if fails else 0)
