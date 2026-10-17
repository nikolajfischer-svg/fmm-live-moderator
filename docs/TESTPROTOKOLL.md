# Testprotokoll v1.0.0 (17.10.2026)

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
- [ ] Chat-Verbindung von der Cloud-IP (Fly.io Frankfurt) prüfen. Siehe GO_LIVE_AGENTUR.md, Abschnitt C
- [ ] Assistent auf echtem iPhone mit Safari durchspielen (Home-Bildschirm-Symbol, Bildschirm wach halten)
- [ ] Erstes echtes LIVE des Pilot-Streamers begleiten
