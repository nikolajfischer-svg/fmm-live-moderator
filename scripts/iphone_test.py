"""iPhone-Praxistest mit Safaris Engine (WebKit, iPhone-15-Emulation, Touch).

Aufruf:  python scripts/iphone_test.py <streamer-link> <live-benutzer> [ausgabeordner]
Spielt den kompletten Einrichtungsassistenten durch, aktiviert den Bot, wartet auf echte
Kommentare und prueft Live-Ansicht, Berichte, Einstellungen, Anleitung. Screenshots je Schritt.
"""
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

link, live_user = sys.argv[1], sys.argv[2]
out = Path(sys.argv[3] if len(sys.argv) > 3 else "iphone_test_out")
out.mkdir(parents=True, exist_ok=True)
problems: list[str] = []
console: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(("OK   " if cond else "FEHL ") + msg)
    if not cond:
        problems.append(msg)


with sync_playwright() as p:
    browser = p.webkit.launch()
    ctx = browser.new_context(**p.devices["iPhone 15"], locale="de-DE")
    page = ctx.new_page()
    page.on("console", lambda m: console.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: console.append(f"pageerror: {e}"))

    def shot(name: str) -> None:
        page.screenshot(path=str(out / f"{name}.png"), full_page=True)

    def no_hscroll(where: str) -> None:
        w = page.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
        check(w[0] <= w[1] + 1, f"{where}: kein seitliches Scrollen ({w[0]} <= {w[1]})")

    page.goto(link)
    page.wait_for_selector("h1")
    if "eigenen Live Moderator" in page.inner_text("h1"):  # Ersteinrichtung eines eigenen Servers
        shot("00_uebernehmen")
        page.fill("#cn", "Test-Streamer")
        page.tap("#cgo")
        page.wait_for_selector("text=Schritt 1 von", timeout=15000)
        check("#t=" in page.url, "Ersteinrichtung: persönlicher Zugang in der Adresse gespeichert")
    shot("01_willkommen")
    check("Hallo" in page.inner_text("h1"), "Schritt 1: Begrüßung sichtbar")
    no_hscroll("Schritt 1")
    page.tap("#u")
    page.fill("#u", "@" + live_user)
    page.tap("#next")
    page.wait_for_selector("text=So arbeitet dein Moderator")
    shot("02_so_arbeitet")
    check("Kein Login nötig" in page.content(), "Schritt 2: Hinweis kein Login")
    page.tap("#next")
    page.wait_for_selector("text=Moderationsregeln")
    shot("03_regeln")
    no_hscroll("Schritt 3")
    page.tap("text=Familienfreundlich")
    page.tap("#next")
    page.wait_for_selector("text=KI-Funktionen")
    shot("04_ki")
    page.fill("#hr", "Keine Fragen nach meinem Wohnort.")
    page.tap("#next")
    page.wait_for_selector("text=Verbindung testen")
    page.tap("#tc")
    page.wait_for_selector("#tcr .note:not(.info)", timeout=40000)
    res = page.inner_text("#tcr")
    check("Verbindung klappt" in res, f"Schritt 5: Verbindungstest ({res.strip()[:80]})")
    page.fill("#tm", "wie lange streamst du heute noch?")
    page.tap("#tmb")
    page.wait_for_selector("#tmr .ev", timeout=60000)
    check("Frage" in page.inner_text("#tmr"), "Schritt 5: Testnachricht als Frage erkannt")
    shot("05_test")
    page.tap("#next")
    page.wait_for_selector("text=Bot aktivieren")
    check(len(page.inner_text("#kwl")) > 50, "Schritt 6: Wortliste für TikTok sichtbar")
    shot("06_aktivieren")
    page.tap("#next")
    page.wait_for_selector("#statusCard", timeout=20000)
    shot("07_dashboard_start")
    end = time.time() + 90
    state = ""
    while time.time() < end:
        state = page.inner_text("#statusCard")
        if "LIVE" in state.split("\n")[0]:
            break
        page.wait_for_timeout(2000)
    check("LIVE" in state.split("\n")[0], f"Live-Ansicht: Status LIVE ({state.splitlines()[1][:60] if len(state.splitlines()) > 1 else state})")
    page.tap("[data-tab=alle]")
    end = time.time() + 60
    n = 0
    while time.time() < end:
        n = page.evaluate("document.querySelectorAll('.ev').length")
        if n >= 4:
            break
        page.wait_for_timeout(2000)
    check(n >= 3, f"Live-Ansicht: echte Kommentare erscheinen ({n})")
    st = page.inner_text("#statusCard")
    check(" 0 Kommentare" not in st, f"Statuszähler läuft mit ({st.splitlines()[1][:70] if len(st.splitlines()) > 1 else st})")
    shot("08_live_alle")
    no_hscroll("Live-Ansicht")
    page.tap("[data-tab=berichte]")
    page.wait_for_timeout(1500)
    check("Deine LIVEs" in page.content() or "Noch keine LIVEs" in page.content(), "Tab Berichte lädt")
    shot("09_berichte")
    page.tap("[data-tab=einstellungen]")
    page.wait_for_selector("text=Moderator-Link")
    check("Familienfreundlich" in page.content(), "Tab Einstellungen zeigt gespeicherte Regeln")
    shot("10_einstellungen")
    page.tap("[data-tab=hilfe]")
    page.wait_for_selector("text=Ausführliche Anleitung")
    with ctx.expect_page() as new_page_info:
        page.tap("text=Ausführliche Anleitung")
    guide = new_page_info.value
    guide.wait_for_load_state()
    check("Einrichtung" in guide.content(), "Anleitung öffnet sich über denselben Link")
    guide.screenshot(path=str(out / "11_anleitung.png"), full_page=True)
    # Neu laden: Zugang bleibt erhalten (Home-Bildschirm-Fall)
    page.reload()
    page.wait_for_selector("#statusCard", timeout=20000)
    check(True, "Neu laden: Zugang bleibt erhalten, Live-Ansicht direkt")
    # Bot wieder ausschalten (Test sauber beenden)
    page.tap("#botBtn")
    page.wait_for_timeout(1500)
    check("Aus" in page.inner_text("#statusCard"), "Bot ausschalten funktioniert")
    browser.close()

csp = [c for c in console if "Content Security Policy" in c or "Refused" in c]
check(not csp, f"Keine CSP-Verstöße ({csp[:2]})")
check(not [c for c in console if c.startswith("pageerror")], f"Keine JavaScript-Fehler ({[c for c in console if c.startswith('pageerror')][:2]})")
print(f"\n{'ALLES OK' if not problems else str(len(problems)) + ' PROBLEM(E)'} - Screenshots: {out}")
sys.exit(1 if problems else 0)
