# Architektur & Grundsatzentscheidungen

Stand: 17.10.2026 · Version 1.0.0

## 1. Entscheidung: Cloud-Webanwendung statt Windows-Installer

| Anforderung | Windows-Installer (.exe) | Cloud-Webanwendung (gewählt) |
|---|---|---|
| Streamer geht **nur mit dem iPhone** live | ❌ PC müsste während jedes LIVEs laufen | ✅ läuft unabhängig von jedem Gerät des Streamers |
| Installation für Laien | Installer, Windows-SmartScreen-Warnung (ohne teures Code-Signing-Zertifikat), Updates nötig | ✅ Link antippen, fertig. Keine Installation |
| API-Schlüssel geschützt | ❌ Schlüssel müsste in der .exe stecken oder vom Streamer besorgt werden | ✅ Schlüssel liegt nur auf dem Server |
| Updates an alle Streamer | Jeder muss neu installieren | ✅ Einmal deployen, alle haben sofort die neue Version |
| Agentur sieht Status, Version, Fehler | Bräuchte zusätzlich Telemetrie-Server | ✅ Eingebaut (/admin) |
| Kosten | Code-Signing ca. 200–400 €/Jahr | ca. 4,50 USD/Monat Hosting |

Deshalb gibt es **keinen Windows-Installer und keine GitHub-Release-Datei**. Das „Download-Paket“ für WhatsApp ist der **persönliche Zugangslink** des Streamers. Die Anleitung liegt online unter `/anleitung` (druckbar als PDF).

## 2. Systembild

```
 Streamer (iPhone, TikTok-App)  ──LIVE──▶  TikTok
                                              │  öffentlicher LIVE-Chat (nur lesen)
                                              ▼
 ┌──────────────────────── Cloud-Server (Fly.io, Frankfurt) ────────────────────────┐
 │  BotManager: je Streamer ein Wachdienst                                          │
 │    - prüft alle 60 s, ob der Streamer LIVE ist (direkt bei TikTok, kostenlos)    │
 │    - verbindet sich mit dem Chat (TikTokLive; Signatur über Euler Stream, frei)  │
 │  Pipeline je Streamer:                                                           │
 │    Kommentar ─▶ Regel-Engine (Sperrwörter, Links, Telefon, Flut, Verwarnungen)   │
 │              └▶ KI-Stapel alle 2,5 s (Claude, strukturierte JSON-Antwort)        │
 │              ─▶ SQLite (je Streamer getrennt) ─▶ Live-Push (Server-Sent Events)  │
 │  Kostenbremse: Tageslimit je Streamer, danach nur Regeln                         │
 └──────────────────────────────────────────────────────────────────────────────────┘
        ▲                         ▲                              ▲
   /app#t=…                  /app#m=…                         /admin
   Streamer: Assistent,      Moderator (Vertrauensperson):    Agentur: Streamer anlegen,
   Live-Ansicht, Regeln,     nur lesen                        Links, Status, Version,
   Berichte                                                   Kosten, Fehler
```

## 3. Mandantentrennung (mehrere Streamer)

- Jeder Streamer ist ein eigener Datensatz mit eigenen Regeln, KI-Einstellungen, Ereignissen, Live-Sessions, Kosten und Fehlern.
- Jede Datenbankabfrage ist an die `streamer_id` gebunden, die **aus dem Zugangstoken** abgeleitet wird. Ein Streamer kann fremde Daten nicht adressieren (getestet).
- Rollen: `streamer` (alles für den eigenen Kanal), `mod` (nur lesen + „erledigt“ markieren), `admin` (Agentur).
- Zugangstoken: 24 Byte Zufall, in der Datenbank nur als SHA-256-Hash gespeichert. Die Agentur kann einen Link jederzeit erneuern (alter wird ungültig), sperren oder alle Daten löschen.
- Der Token steht im `#`-Teil der Adresse und wird vom Browser nie an Server oder Logs übertragen. Er bleibt bewusst in der Adresse, damit ein iPhone-Home-Bildschirm-Symbol den Zugang behält.

## 4. Was bewusst NICHT gebaut wurde

- **Automatisches Stummschalten, Blockieren oder Löschen in TikTok und Chat-Antworten des Bots.** TikTok bietet dafür keine offizielle Schnittstelle. Der einzige Weg wäre die Session-Cookies des TikTok-Kontos über einen Drittanbieter. Das entspricht einer Passwortweitergabe und verstößt gegen die TikTok-Nutzungsbedingungen. Siehe `FUNKTIONEN.md`.
- **Login mit TikTok-Konto.** Wird nicht gebraucht.

## 5. Skalierungspfad (vorbereitet, für den Pilot nicht nötig)

| Stufe | Maßnahme |
|---|---|
| bis ca. 20 Streamer | aktueller Aufbau (1 Server, SQLite, kostenloser Euler-Zugang) |
| 20–100 Streamer | Euler Stream Business (50 USD/Monat, 100 gleichzeitige Verbindungen); Live-Status mehrerer Streamer gebündelt abfragen (TikTok `check_alive` akzeptiert mehrere Räume) |
| > 100 Streamer | Postgres statt SQLite, mehrere Worker; optional eigener API-Schlüssel je Streamer |
| Abrechnung | Kosten werden heute schon je Streamer erfasst (`usage`-Tabelle, Admin-Dashboard „KI 30 T.“) → monatlich weiterberechnen |

## 6. Technik

- Python 3.12, FastAPI, Uvicorn, TikTokLive 7.0.1, Anthropic SDK 1.15
- Frontend ohne Build-Schritt (HTML/CSS/JS, keine externen Skripte, alle Nutzertexte HTML-escaped)
- Daten: SQLite im WAL-Modus auf persistentem Volume; Chat-Daten werden nach 30 Tagen gelöscht
- Konfiguration nur über Umgebungsvariablen (`.env.example`); Secrets nie im Code oder Repo
