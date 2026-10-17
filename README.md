# FMM Live Moderator

KI-Chatmoderation für TikTok LIVE, als Cloud-Webanwendung für die Streamer der Agentur. Der Streamer öffnet einen persönlichen Link, richtet in ca. 5 Minuten alles ein und kann danach **nur mit dem iPhone** live gehen. Der Moderator läuft in der Cloud.

- **Streamer:** `/app#t=<token>`: Einrichtungsassistent, Live-Ansicht (Wichtig / Fragen / Alle), Berichte, Einstellungen
- **Moderator (Vertrauensperson):** `/app#m=<token>`: nur lesen
- **Agentur:** `/admin`: Streamer anlegen, Links, Status, Version, Kosten, Fehler
- **Anleitung:** `/anleitung` · **Datenschutz:** `/datenschutz`

## Dokumentation
| Datei | Inhalt |
|---|---|
| [docs/GO_LIVE_AGENTUR.md](docs/GO_LIVE_AGENTUR.md) | Online-Gang, Abnahme, Streamer einladen, Betrieb |
| [docs/FUNKTIONEN.md](docs/FUNKTIONEN.md) | Was wirklich unterstützt wird und was bewusst nicht |
| [docs/KOSTEN.md](docs/KOSTEN.md) | Laufende Kosten, gemessene KI-Kosten, Kostenschutz |
| [docs/ARCHITEKTUR.md](docs/ARCHITEKTUR.md) | Cloud statt Installer, Mandantentrennung, Skalierung |
| [docs/TESTPROTOKOLL.md](docs/TESTPROTOKOLL.md) | Durchgeführte Tests und Befunde |
| [docs/WHATSAPP_NACHRICHT.md](docs/WHATSAPP_NACHRICHT.md) | Text für den Versand |

## Lokal starten
```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt pytest httpx
copy .env.example .env   # ADMIN_TOKEN, ANTHROPIC_API_KEY, PUBLIC_URL=http://localhost:8000 eintragen
.venv\Scripts\python -m fmm_live.web
```
Dann `http://localhost:8000/admin` öffnen.

## Tests
```powershell
.venv\Scripts\python -m pytest -q                                   # 18 automatische Tests, ohne Kosten
.venv\Scripts\python scripts\ki_praxistest.py claude-haiku-5-5      # echte KI, < 1 Cent
.venv\Scripts\python scripts\live_lesetest.py <live-benutzer> 60    # echter TikTok-LIVE, nur lesen
```

## Aufbau
```
fmm_live/
  config.py    Umgebungsvariablen
  db.py        SQLite, mandantengetrennt, Token nur als Hash
  rules.py     Regel-Engine, Presets, Schlüsselwortfilter-Export
  ai.py        Claude-Klassifizierer (strukturierte JSON-Ausgabe), Offline-Fallback
  pipeline.py  Regeln → KI-Stapel → Speichern → Live-Push, Kostenbremse
  live.py      TikTok-Lesezugang, BotManager (Wachdienst je Streamer)
  web.py       FastAPI: Seiten, Streamer-, Moderator- und Admin-API, SSE
  static/      Oberfläche (ohne Build-Schritt)
```
