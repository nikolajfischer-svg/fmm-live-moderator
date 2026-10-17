# FMM Live Moderator: Einrichtung für Streamer

Dein eigener KI-Moderator für TikTok LIVE. Er läuft in **deiner eigenen Cloud**, auch wenn dein PC aus ist und du nur mit dem iPhone streamst.
Dauer: ca. 15 Minuten, nur einmal. Du brauchst **keine Programmierkenntnisse** und musst nichts installieren. Alles geht im Browser, auch auf dem iPhone.

## Was kostet das? (bezahlst du direkt beim jeweiligen Anbieter)
| Dienst | Wofür | Kosten |
|---|---|---|
| Render | dein Server, läuft rund um die Uhr | ca. 7 USD/Monat + 0,25 USD Speicher |
| Anthropic (Claude) | die KI, die Kommentare prüft | Guthaben ab 5 USD, Verbrauch ca. 1–3 USD/Monat |

Die Agentur bekommt keine Zahlungsdaten und keine Passwörter von dir.

## Schritt 1: KI-Schlüssel holen (ca. 5 Minuten)
1. Öffne **console.anthropic.com** und registriere dich (E-Mail oder Google).
2. Links **Billing** → Guthaben kaufen (5 USD reichen für Monate). Empfehlung: unter **Limits** ein Monatslimit setzen, z. B. 10 USD.
3. Links **API Keys** → **Create Key** → Name „Live Moderator“ → **Kopieren**.
   Der Schlüssel beginnt mit `sk-ant-`. Er wird nur einmal angezeigt. Bewahre ihn wie ein Passwort auf und gib ihn niemandem.

## Schritt 2: Eigenen Server starten (ca. 5 Minuten)
1. Auf der Einrichtungsseite auf **„Deploy to Render“** tippen.
2. Bei Render registrieren (E-Mail, Google oder GitHub) und eine Zahlungsmethode hinterlegen.
3. Render zeigt „FMM Live Moderator“. Bei **ANTHROPIC_API_KEY** deinen Schlüssel aus Schritt 1 einfügen.
4. Auf **Deploy Blueprint** bzw. **Apply** tippen. Render baut jetzt deinen Server (3–8 Minuten).
5. Wenn der Status **Live** zeigt: oben auf deine Adresse tippen. Sie sieht aus wie `https://fmm-live-moderator-xxxx.onrender.com`.

## Schritt 3: Moderator übernehmen und einrichten (ca. 5 Minuten)
1. Deine Adresse öffnet „Willkommen bei deinem eigenen Live Moderator“. Namen eingeben → **Moderator übernehmen**.
   Das geht nur ein einziges Mal und in den ersten 6 Stunden nach dem Start. So kann niemand Fremdes deinen Server übernehmen.
2. **Sofort sichern:** In Safari auf Teilen → **„Zum Home-Bildschirm“**. Dieses Symbol ist ab jetzt dein persönlicher Zugang.
3. Dem Assistenten folgen: TikTok-Benutzername → Regeln → KI → Verbindung testen → **Bot aktivieren**.
4. Die angezeigte Wortliste in TikTok einfügen: LIVE vorbereiten → Einstellungen → Kommentare → Schlüsselwörter filtern.

Fertig. Ab jetzt startet der Moderator bei jedem LIVE automatisch.

## Während und nach dem LIVE
- Streamst du nur mit dem iPhone? Dann trag eine Vertrauensperson in TikTok als **LIVE-Moderator** ein und schick ihr den **Moderator-Link** (App → Einstellungen). Sie sieht alle Hinweise live.
- Stummschalten und Blockieren machst du oder dein Moderator in der TikTok-App. Der Bot sagt euch, wann.
- Nach dem LIVE: Tab **Berichte**.
- Die ausführliche Bedienungsanleitung findest du in deinem Moderator unter **Hilfe → Ausführliche Anleitung**.

## Hilfe
- **Zugang verloren?** Render → dein Dienst → **Environment** → Wert von `ADMIN_TOKEN` kopieren. Dann `https://deine-adresse.onrender.com/admin` öffnen, den Schlüssel eingeben und „Neuer Link“ antippen.
- **Ersteinrichtung verpasst (mehr als 6 Stunden)?** Beim Übernehmen nach dem Admin-Schlüssel gefragt? Er steht ebenfalls unter **Environment → ADMIN_TOKEN**.
- **KI-Schlüssel ändern:** Render → **Environment** → `ANTHROPIC_API_KEY` → speichern. Der Server startet neu.
- **Kündigen:** Render → dein Dienst → Settings → **Delete Service**. Damit enden alle Kosten und alle Daten werden gelöscht. Bei Anthropic den Schlüssel löschen.
- Kein TikTok-Passwort, niemals. Der Moderator liest nur den öffentlichen LIVE-Chat.
