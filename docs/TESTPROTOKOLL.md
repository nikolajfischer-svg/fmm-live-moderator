# Testprotokoll

## Qualitätskontrolle v1.1.1 (17.10.2026), Sicht eines fremden Streamers

### BESTANDEN (tatsächlich getestet)
- **Einstiegsseite (öffentlich, GitHub Pages)** im frischen iPhone-Profil (WebKit, keine Anmeldungen): lädt, alle Inhalte vorhanden, kein seitliches Scrollen, keine Platzhalter. Alle Links erreichbar (Anthropic-Konsole, Render-Deploy, Anleitung).
- **Render-Deploy-Button:** führt zu Renders Anmeldung und danach direkt zu „Blueprint anlegen“ mit diesem Repository. `render.yaml` ist öffentlich abrufbar.
- **Render-Build nachgestellt:** frische Kopie aus Git, neue Python-3.12-Umgebung, nur `requirements.txt`, Renders Startbefehl, Port 10000, keine persönlichen Zugangsdaten. Build in 22 s, alle Dateien vorhanden, Server startet.
- **Datenbank:** wird beim ersten Start auf dem leeren Speicher angelegt.
- **Fehlender KI-Schlüssel:** verständlicher Hinweis mit Weg (Render → Environment). Der Moderator arbeitet mit Regeln weiter.
- **Neustart:** Zugang, Einstellungen und Daten bleiben erhalten. Eine erneute Übernahme ist nicht möglich.
- **Zugriffsschutz:** Ersteinrichtung nur einmal; Fremde ohne Link sehen nur einen Hinweis; gefälschte Links abgewiesen; Streamer-Link ohne Admin-Rechte; Admin nur mit Schlüssel; Widerruf sofort wirksam (auch offene Live-Verbindungen).
- **Datentrennung:** eigener Server je Streamer. Zusätzlich im Mehrmandanten-Modus getestet: Streamer B sieht keine Daten von A.
- **Echter TikTok-LIVE-Chat (nur lesen, tonlos):** automatische Verbindung in 3–5 s, echte Kommentare kommen an. Nach hartem Verbindungsabbruch selbstständig wieder verbunden in 13 s, **0 doppelte Kommentare**, ein durchgehender Bericht.
- **KI (Claude Haiku 5.5):** 15/15 typische deutsche Fälle richtig (Beleidigung, Hetze, Drohung, Belästigung, Spam, Selbstgefährdung, Manipulationsversuch, Fragen), zweimal in Folge. Auf echtem Chat keine Fehlalarme mehr bei harmlosen fremdsprachigen Kommentaren.
- **iPhone-Durchlauf (WebKit, iPhone 15):** Ersteinrichtung → 6 Schritte → Bot aktiv → Live-Ansicht mit echten Kommentaren → Statuszähler → Berichte → Einstellungen → Anleitung → Neu laden → Bot aus. Keine CSP- oder JavaScript-Fehler.
- **Fehlerfälle auf dem iPhone:** ungültiger oder zu langer Benutzername, unbekanntes TikTok-Konto, gefälschter Link, Fremder ohne Link: jeweils verständliche deutsche Meldung.
- **Kosten/Sicherheit:** keine Schlüssel im öffentlichen Repository (gesamte Historie geprüft); keine persönlichen Testdaten veröffentlicht; Agentur ohne laufende Kosten (öffentliches Repo, Pages kostenlos); keine Zahlungsdaten an die Agentur; die App verspricht keine automatischen TikTok-Moderationsaktionen.
- 29 automatische Tests grün.

### NICHT GETESTET (ohne externe Registrierung bzw. echten Cloud-Account nicht prüfbar)
- **Echter Deploy bei Render** (Build, Speicher-Volume, Gesundheitsprüfung und Ersteinrichtung auf `*.onrender.com`). Nachgestellt und bestanden, aber nicht auf Render selbst ausgeführt.
- **TikTok-Chat von einer Rechenzentrums-IP.** Alle echten Tests liefen über einen privaten Anschluss. Ob TikTok Render-IPs drosselt, zeigt sich erst beim ersten Deploy. Ausweichwege: `SIGN_API_KEY` (Euler, kostenlos) bzw. `TIKTOK_PROXY`.
- **Anthropic-Registrierung, Guthabenkauf und Schlüsselerzeugung** aus Sicht eines neuen Nutzers. Die Schritte sind beschrieben, die Oberflächen der Anbieter können abweichen.
- **Echtes iPhone mit Safari** (nur WebKit-Emulation): Home-Bildschirm-Symbol, „Bildschirm wach halten“, Ton bei dringenden Hinweisen.

### FEHLGESCHLAGEN
- Keine offenen Fehler. Während der QS gefunden und behoben: doppelter Kommentar nach Wiederverbindung, geteilter Bericht bei kurzem Abbruch, „Fehler 422“ statt verständlicher Meldung, schwankende Einstufung sexualisierter Aufforderungen, Fehlalarme bei fremdsprachigen Kommentaren, veraltete Agentur-Texte im Selbst-Betrieb.

## v1.1.0 (17.10.2026): Self-Hosting je Streamer
- 28 automatische Tests grün, darunter: Ersteinrichtung, zweite Übernahme abgelehnt, abgelaufenes Fenster nur mit ADMIN_TOKEN, im Agenturmodus gesperrt
- Unabhängige Sicherheitsprüfung (kein kritischer Befund) umgesetzt: Widerruf trennt offene Live-Verbindungen, CSP/HSTS, Größen- und Ratenlimits, Prompt-Injection-Isolation, Admin nur per Header, secure_delete, bereinigte Fehlertexte, Volume-Rechte
- iPhone-Durchlauf mit Safari-Engine (WebKit, iPhone 15): Ersteinrichtung → Assistent → Bot aktiv → echter LIVE-Chat → Berichte → Einstellungen → Anleitung → Neu laden: **alles OK**, keine CSP- oder JS-Fehler
- Rauchtest-Skript (wie in der Prüfstraße), lokal: Ersteinrichtung, Rechte, CSP, TikTok-Diagnose, Neustart mit Datenerhalt: **OK**
- Offen: Container-Build und TikTok-Test von einer Rechenzentrums-IP. Läuft automatisch in GitHub Actions, sobald das Repository veröffentlicht ist. Ein echter Render-Deploy ist erst mit dem ersten Streamer-Konto möglich.

## v1.0.0 (17.10.2026)

## Automatische Tests: 18/18 grün
`.venv\Scripts\python.exe -m pytest -q`

- Regel-Engine: Sperrwörter inkl. Leetspeak und Leerzeichen, Wortgrenzen, keine Fehlalarme bei normalen Nachrichten, Links, Telefonnummern, E-Mails, Wiederholung, Flut, Ausnahmeliste, abgeschaltete Kategorien, Eskalation, Wortlisten-Export
- Gesamtablauf über die echte Web-API mit simuliertem LIVE: Einladung → Benutzername (auch als URL) → Regeln → KI → Verbindungstest → Testnachrichten → Aktivieren → LIVE erkannt → 6 Kommentare richtig eingestuft (inkl. Wiederholungstäter und „dringend“) → Session beendet → Bericht → erledigt markieren → Admin sieht Status, Version und Kosten
- Mandantentrennung: Streamer B sieht und ändert keine Daten von A; Moderator-Rolle darf nur lesen; Link erneuern macht alten ungültig; Sperren und Löschen
- Admin ohne bzw. mit falschem Token wird abgewiesen
- KI-Ausfall: Moderation läuft mit Regeln weiter, Fehler landet im Dashboard
- Tageslimit: KI wird nach Überschreiten nicht mehr aufgerufen
- Neustart: Einstellungen und aktiver Bot bleiben erhalten, der Wachdienst startet von selbst

## Echte KI (Anthropic), 15 typische deutsche Chat-Kommentare
- `claude-opus-5-5`: 15/15 richtig, 2,7 US-Cent, 10 s
- `claude-haiku-5-5`: 15/15 richtig, 0,07 US-Cent, 4,6 s
- Befund behoben: Haiku erfand in einer Antwortidee einen Fakt über den Streamer. Der Prompt verbietet das jetzt.

## Echte TikTok-LIVEs (nur lesen, ohne Login, ohne Euler-Schlüssel, privater Anschluss)
- Stream 1 (135 Zuschauer): LIVE erkannt in 0,8 s, Chat verbunden nach 3,7 s, Kommentare kommen an
  - Befund behoben: jede Nachricht kam doppelt → Entdoppelung per Nachrichten-ID
  - Befund behoben: Warnung beim Trennen (blockierender Aufruf) → sauberes Schließen
- Stream 2 (1.671 Zuschauer) mit echter KI (Haiku): Verbindung nach 4,3 s, 3 KI-Aufrufe, 0,08 US-Cent, keine Fehler
- Kompletter Server mit Browser-Oberfläche (iPhone-Format 375×812): Assistent Schritt 1–6 durchgeklickt, Verbindungstest „ist gerade LIVE“, Testnachricht Frage → Antwortidee, verschleierte Beleidigung „h*rens*hn“ → ausblenden, Bot aktiviert → Status „LIVE · 136 Zuschauer“, echte Kommentare in der Live-Ansicht
  - Befund behoben: Zuschauer, die ihre unbeantwortete Frage dreimal stellten, wurden als Spam ausgeblendet. Jetzt gilt bei Fragen Toleranz, bei anderen Nachrichten „beobachten“, erst ab 5× „ausblenden“
- Agentur-Dashboard: Kennzahlen, Status LIVE, Kosten, Streamer anlegen mit WhatsApp-Text

## Noch offen (erst nach dem Online-Gang möglich)
- [ ] Assistent auf echtem iPhone mit Safari durchspielen (Home-Bildschirm-Symbol, Bildschirm wach halten)
- [ ] Erstes echtes LIVE des Pilot-Streamers begleiten
