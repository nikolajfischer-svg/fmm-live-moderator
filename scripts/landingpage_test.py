"""Fremder Streamer, frisches iPhone-Profil: Einstiegsseite + alle Links (tonlos, keine Anmeldung, keine Eingaben)."""
import sys

from playwright.sync_api import sync_playwright

url = sys.argv[1]
out = sys.argv[2] if len(sys.argv) > 2 else "landing_out"
fails = []


def check(cond, msg):
    print(("OK   " if cond else "FEHL ") + msg)
    if not cond:
        fails.append(msg)


with sync_playwright() as p:
    b = p.webkit.launch()
    ctx = b.new_context(**p.devices["iPhone 15"], locale="de-DE")
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    r = pg.goto(url)
    check(r.status == 200, f"Einstiegsseite lädt (HTTP {r.status})")
    pg.screenshot(path=f"{out}_seite.png", full_page=True)
    t = pg.evaluate("document.body.textContent")  # inkl. eingeklappter FAQ
    for word in ("Was kostet das", "KI-Schlüssel holen", "Eigenen Server starten", "Moderator übernehmen",
                 "Kein TikTok-Passwort", "keine offizielle Schnittstelle"):
        check(word.lower() in t.lower(), f"Inhalt vorhanden: „{word}“")
    w = pg.evaluate("[document.documentElement.scrollWidth, innerWidth]")
    check(w[0] <= w[1] + 1, f"kein seitliches Scrollen ({w})")
    check("__OWNER__" not in pg.content(), "keine Platzhalter mehr")
    links = pg.evaluate("[...document.querySelectorAll('a')].map(a=>[a.innerText.trim(), a.href])")
    for text, href in links:
        resp = ctx.request.get(href, max_redirects=10, fail_on_status_code=False)
        ok = resp.status < 400
        check(ok, f"Link „{text[:30]}“ -> {href[:80]} (HTTP {resp.status})")
    # Deploy-Button wie ein Streamer antippen: landet bei Render (Anmeldung/Registrierung), nichts wird angelegt
    href = pg.locator('a:has-text("Server bei Render starten")').get_attribute("href")
    rp = ctx.new_page()
    rp.goto(href, wait_until="domcontentloaded")
    rp.wait_for_timeout(4000)
    rp.screenshot(path=f"{out}_render.png")
    rt = rp.inner_text("body")[:400].replace("\n", " ")
    check("render.com" in rp.url, f"Render-Seite öffnet sich ({rp.url[:90]})")
    print("     Render zeigt:", rt[:200])
    check(not errors, f"keine JavaScript-Fehler ({errors[:1]})")
    b.close()
print("ERGEBNIS:", "OK" if not fails else f"{len(fails)} Fehler")
