# Online-Gang & Übergabe: Schritte für die Agentur

Die Software ist fertig und getestet. Online gehen kann sie erst, wenn ein Hosting-Konto existiert. Dafür brauchst du ein Konto und eine Zahlungsmethode, das kann ich nicht für dich anlegen. Danach übernehme ich den Rest.

## A. Deine Schritte (ca. 15 Minuten)

1. **Fly.io-Konto anlegen:** https://fly.io/app/sign-up → Kreditkarte hinterlegen (ca. 4,50 USD/Monat).
2. **Fly-Werkzeug installieren:** PowerShell öffnen und ausführen:
   ```powershell
   iwr https://fly.io/install.ps1 -useb | iex
   ```
3. **Anmelden:** im selben Fenster `fly auth login` (öffnet den Browser).
4. **Eigenen Anthropic-Schlüssel für dieses Projekt anlegen:** https://console.anthropic.com → API Keys → „Create Key“ (Name: `live-moderator`). Unter Limits ein Monatslimit setzen, z. B. 30 USD.
5. **Modell entscheiden:** Opus 5.5 (Standard) oder Haiku 5.5 (empfohlen für den Pilot, siehe `KOSTEN.md`).
6. **Datenschutzseite ergänzen:** In `fmm_live/static/datenschutz.html` Anschrift und E-Mail eintragen, oder mir die Daten geben.
7. Mir Bescheid geben: „Fly ist eingeloggt“. Den Anthropic-Schlüssel nicht in den Chat schreiben, sondern selbst setzen (siehe B.3).

## B. Veröffentlichung + Abnahme (automatisch)

```powershell
.venv\Scripts\python scripts\cloud_release.py --app fmm-live-moderator --streamer "Name" --live-users user1,user2 `
  --anthropic-key-file <datei> --model claude-haiku-5-5 --operator-email ... --operator-address "..."
```

Das Skript legt App und Volume in Frankfurt an, setzt die Secrets über stdin (kein Schlüssel auf der Kommandozeile) und baut in der Fly-Cloud. Danach folgt die Abnahme:
- Sicherheits-Header, HTTPS, Admin- und Streamer-Zugriffsschutz, Datenschutzseite
- **echter Verbindungstest Cloud → öffentliches TikTok-LIVE** (`/api/admin/diagnose`)
- iPhone-Durchlauf mit Safari-Engine (WebKit, iPhone 15) gegen die Cloud
- Widerruf: Ein erneuerter Link macht den alten sofort ungültig, und der Einladungslink hat keine Admin-Rechte

Nur wenn alles bestanden ist, erzeugt es den Streamer-Link und schreibt `Desktop\FMM_Live_Moderator_LINKS.txt` mit Streamer-Link, fertiger WhatsApp-Nachricht und Admin-Link (`/admin#k=…`, meldet automatisch an).

## C. Automatischer Betrieb
- Fly startet die Maschine bei Absturz neu (`[[restart]] policy = "always"`) und prüft alle 30 s `/healthz`.
- Die Maschine schläft nie (`auto_stop_machines = "off"`, `min_machines_running = 1`).
- Ein interner Wachhund startet alle 60 s beendete Bot-Wachdienste neu. Fehler im Wachdienst werden protokolliert, danach läuft er weiter.

## D. Streamer einladen

1. `/admin` → „Neuen Streamer anlegen“ → Name eintragen → „Anlegen“.
2. „Per WhatsApp senden“ antippen. Der Text mit Link ist vorausgefüllt (Vorlage siehe `WHATSAPP_NACHRICHT.md`).
3. Der Link ist nur einmal sichtbar. Geht er verloren: „Neuer Link“.

## E. Betrieb

- **Updates:** Code ändern, Version in `fmm_live/__init__.py` erhöhen, `fly deploy`. Alle Streamer haben sofort die neue Version.
- **Logs:** `fly logs`. **Neustart:** `fly apps restart`.
- **Notschalter:** `fly secrets set TIKTOK_ENABLED=false` (alle Bots aus) bzw. `AI_ENABLED=false` (nur Regeln, keine KI-Kosten).
- **Datensicherung:** `fly volumes snapshots list`. Fly erstellt tägliche Snapshots, 5 Tage Aufbewahrung.
- **DSGVO-Löschung:** Im Dashboard „Löschen“ entfernt alle Daten eines Streamers.
