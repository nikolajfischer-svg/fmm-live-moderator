# FMM Live Moderator

Dein eigener KI-Moderator für TikTok LIVE. Er läuft in **deiner eigenen Cloud**, auch wenn du nur mit dem iPhone streamst und dein PC aus ist.

**➡️ Einrichtung für Streamer (Schritt für Schritt, auf Deutsch): [ANLEITUNG.md](ANLEITUNG.md)**

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/__OWNER__/fmm-live-moderator)

- Erkennt Beleidigungen, Hass, sexuelle Belästigung, Drohungen, Spam, Links, Telefonnummern und Hinweise auf Selbstgefährdung. Hebt Fragen an dich hervor, mit Antwortidee.
- Empfiehlt konkret, was zu tun ist („stummschalten empfohlen“). Ausgeführt wird in der TikTok-App: TikTok bietet keine offizielle Schnittstelle für automatische Moderation. Eine fertige Wortliste für TikToks eingebauten Schlüsselwortfilter liefert die App mit.
- Moderator-Link für eine Vertrauensperson, Berichte nach jedem LIVE.
- Kein TikTok-Passwort, kein Login. Gelesen wird nur der öffentliche LIVE-Chat.

## Kosten (bezahlt der Streamer direkt beim Anbieter)
| Dienst | Kosten |
|---|---|
| Render-Server (`0.5c-512mb`, Frankfurt, schläft nie) + 1 GB Speicher | ca. 7,25 USD/Monat |
| Anthropic-KI (Standard: Claude Haiku 5.5, Tageslimit 2 USD) | meist 1–3 USD/Monat, Guthaben ab 5 USD |

Details: [docs/KOSTEN.md](docs/KOSTEN.md) · Funktionsumfang: [docs/FUNKTIONEN.md](docs/FUNKTIONEN.md) · Weitergabe durch die Agentur: [docs/VERTEILUNG.md](docs/VERTEILUNG.md)

## Sicherheit
- Jeder Streamer betreibt **seinen eigenen Server**. Es gibt keine gemeinsame Datenbank.
- `ADMIN_TOKEN` erzeugt Render für jeden Server automatisch und zufällig. Den KI-Schlüssel trägt der Streamer selbst ein, beides ist nur in seinem Render-Konto sichtbar.
- Den neuen Server übernimmt beim ersten Aufruf genau eine Person, und nur in den ersten 6 Stunden. Danach geht das nur noch mit `ADMIN_TOKEN`.
- Content-Security-Policy, HSTS, Ratenlimits, widerrufbare Links. Chat-Daten werden nach 30 Tagen gelöscht.

## Für Entwickler
```powershell
python -m venv .venv; .venv\Scripts\pip install -r requirements.txt pytest httpx
.venv\Scripts\python -m pytest -q
$env:SELF_HOSTED="true"; .venv\Scripts\python -m fmm_live.web     # http://localhost:8000/app
```
Aufbau: `fmm_live/` (FastAPI, Regel-Engine, Claude-Klassifizierer, TikTok-Lesezugang, Oberfläche ohne Build-Schritt), `render.yaml` (Ein-Klick-Bereitstellung), `Dockerfile`, `.github/workflows/ci.yml` (Tests, Container-Test, optional TikTok-Test von einer Rechenzentrums-IP).
