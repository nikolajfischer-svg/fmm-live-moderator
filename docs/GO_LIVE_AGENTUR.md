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

## B. Deployment (mache ich, sobald Fly eingeloggt ist, oder du selbst)

```powershell
cd C:\Users\Nikolai\Desktop\FMM_Live_Moderator
powershell -ExecutionPolicy Bypass -File scripts\deploy_fly.ps1 -AppName fmm-live-moderator
```

Das Skript
1. legt die App in Frankfurt an (falls der Name vergeben ist, einen anderen wählen, z. B. `fmm-moderator-nf`),
2. erstellt das 1-GB-Volume,
3. erzeugt einen zufälligen `ADMIN_TOKEN` und speichert ihn in `ADMIN_TOKEN.txt` auf deinem Desktop,
4. fragt den Anthropic-Schlüssel verdeckt ab und setzt ihn als Fly-Secret (er landet nie in einer Datei),
5. deployt und prüft `/healthz`.

## C. Abnahme nach dem Online-Gang (Pflicht vor dem Versand an den Streamer)

1. `https://<app>.fly.dev/admin` öffnen → mit dem `ADMIN_TOKEN` anmelden.
2. Einen Test-Streamer anlegen, z. B. „Test Agentur“.
3. Den Link auf dem iPhone öffnen und den Assistenten durchspielen. Als Benutzernamen einen Account nehmen, der **gerade LIVE** ist.
4. **Prüfpunkt Cloud-IP:** „Verbindung testen“ muss „ist gerade LIVE“ melden, danach Bot aktivieren. Im Tab „Alle“ müssen innerhalb einer Minute echte Kommentare erscheinen.
   - Klappt das nicht und das Dashboard zeigt „TikTok blockiert…“: kostenlosen Euler-Schlüssel holen (https://www.eulerstream.com → Community) und `fly secrets set SIGN_API_KEY=...` setzen. Wenn das nicht hilft, einen Proxy über `TIKTOK_PROXY` eintragen.
5. Test-Streamer im Dashboard löschen.
6. **Erst dann** den echten Streamer anlegen und den Link verschicken.

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
