# Tatsächlich unterstützte Moderationsfunktionen

Stand: 17.10.2026 · Version 1.0.0 · Grundlage: Code, automatische Tests und Praxistests mit echten TikTok-LIVEs.

## ✅ Funktioniert (getestet)

| Funktion | Wie | Getestet |
|---|---|---|
| LIVE automatisch erkennen | Server prüft alle 60 s, ob der Streamer LIVE ist; verbindet automatisch | echter Stream, Verbindung nach 3,7–4,3 s |
| LIVE-Chat mitlesen | öffentlicher Chat über Benutzernamen, **ohne Login/Passwort** | 2 echte Streams (135 bzw. 1.671 Zuschauer) |
| Sperrwörter (auch verschleiert, z. B. `W1CHS3R`, `h u r e n…`) | Regel-Engine, Grundliste + eigene Wörter | Unit-Tests |
| Links / Werbung / Telegram / „Insta:“ | Regel-Engine | Unit-Tests |
| Telefonnummern, E-Mail-Adressen | Regel-Engine | Unit-Tests |
| Chat-Flut, ständig wiederholte Nachrichten | Regel-Engine (wiederholte Fragen werden toleriert) | Unit-Tests + Praxisbefund |
| KI-Bewertung: Beleidigung, Hass, sexuelle Belästigung, Drohung, Spam, persönliche Daten, Selbstgefährdung | Claude, Stapel alle 2,5 s | 15/15 richtig (Opus 5.5 und Haiku 5.5) |
| Manipulationsversuche („ignoriere deine Regeln…“) | werden als „beobachten“ markiert | KI-Test |
| Fragen an den Streamer hervorheben + Antwortidee | KI | KI-Test + echter Stream |
| Wiederholungstäter eskalieren | 2. Verstoß → stummschalten, 4. → blockieren empfohlen | Unit- und API-Tests |
| Dringende Hinweise (Selbstgefährdung) | rote Meldung, Ton, Hilfetelefon-Hinweis | API-Test, KI-Test |
| Wortliste für den TikTok-Schlüsselwortfilter | App erzeugt Liste (max. 200) zum Kopieren | API-Test |
| Moderator-Link für Vertrauensperson | nur lesen, eigener Token, erneuerbar | API-Test |
| Bericht nach dem LIVE | Kommentare, Verstöße nach Art, auffälligste Zuschauer, Fragen | API-Test |
| Agentur-Dashboard | Bots aktiv/LIVE, Version, Zuletzt geöffnet, Kosten je Streamer, Fehler | Browser-Test |
| Ausfallsicherheit | KI-Fehler → Regelprüfung läuft weiter; TikTok-Fehler → automatische Wiederholung mit Wartezeit | API-Test |
| Kostenbremse | Tageslimit je Streamer (Standard 5 USD), danach nur Regeln | API-Test |

## ⚠️ Ausgeführt wird von Menschen bzw. von TikTok selbst

| Aktion | Wer führt aus |
|---|---|
| Kommentar ausblenden | **TikTok automatisch** über den Schlüsselwortfilter (Liste aus der App) |
| Zuschauer stummschalten | Streamer oder TikTok-Moderator in der TikTok-App, nach Empfehlung der App |
| Zuschauer blockieren / melden | Streamer oder TikTok-Moderator in der TikTok-App |

## ❌ Bewusst nicht umgesetzt

| Funktion | Grund |
|---|---|
| Automatisch stummschalten, blockieren, Kommentare löschen | TikTok bietet **keine offizielle Schnittstelle** für LIVE-Moderation. Die verbreitete Bibliothek TikTokLive kann nur lesen, dort gibt es überhaupt keine Mute- oder Bann-Funktion. |
| Bot schreibt in den Chat | Geht nur über einen kostenpflichtigen Drittanbieter **mit den Session-Cookies des TikTok-Kontos**. Das kommt einer Passwortweitergabe gleich, verstößt gegen die TikTok-Nutzungsbedingungen und riskiert eine Kontosperre. |

Sollte TikTok eine offizielle LIVE-Moderations-Schnittstelle veröffentlichen, kann sie an der Stelle der „Empfehlung“ angeschlossen werden. Die Entscheidungslogik bleibt gleich.

## Bekannte Grenzen

- Der Chat-Lesezugang ist **inoffiziell** (TikTokLive, Signaturdienst Euler Stream). TikTok kann ihn jederzeit ändern. Ausfälle zeigt das Dashboard an, der Bot versucht es automatisch erneut.
- **Noch nicht getestet:** Verbindung von einer Cloud-IP. Alle echten Tests liefen über einen privaten Internetanschluss. Falls TikTok die Rechenzentrums-IP drosselt, gibt es den Schalter `TIKTOK_PROXY` oder einen Euler-Schlüssel (`SIGN_API_KEY`). Das ist Prüfpunkt 1 nach dem Online-Gang.
- Wenn der Streamer nur mit dem iPhone streamt, sieht er die Hinweise während des LIVEs nicht selbst (TikTok ist im Vordergrund). Lösung: menschlicher Moderator mit Moderator-Link, Zweitgerät oder Bericht danach.
- Die KI kann sich irren. Deshalb gibt sie nur Empfehlungen, Freunde lassen sich auf eine Ausnahmeliste setzen.
- iOS-Safari erlaubt keine Push-Benachrichtigungen für nicht installierte Web-Apps. Hinweise erscheinen in der geöffneten App, ein Ton spielt nur nach erster Interaktion.
