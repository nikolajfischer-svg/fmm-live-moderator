# Laufende Kosten

Stand: 17.10.2026. Preise in USD laut Anbieter-Preislisten, KI-Werte **gemessen** mit echten Kommentaren.

## Fixkosten (Pilot mit 1 Streamer, reicht bis ca. 20 Streamer)

| Posten | Kosten/Monat |
|---|---|
| Fly.io Server shared-cpu-1x, 512 MB, Frankfurt | ca. 4,30 USD (3,69 USD Basispreis × Regionsaufschlag ~1,15) |
| Fly.io Speicher-Volume 1 GB | 0,15 USD |
| Gemeinsame IPv4-Adresse + HTTPS-Zertifikat | 0 USD |
| Euler Stream (Signatur für Chat-Zugang), Community-Stufe | 0 USD (2.500 Anfragen/Tag, 25 Verbindungen) |
| **Summe fix** | **ca. 4,50 USD/Monat** |

Optional: eigene Domain (ca. 1–2 €/Monat), Euler Business ab ca. 20+ gleichzeitig aktiven Streamern (50 USD/Monat).

## Variable Kosten: KI (Anthropic Claude)

Gemessen am 17.10.2026 mit 15 typischen deutschen Chat-Kommentaren (Stapel, Aufwand „low“):

| Modell | Treffer | Kosten je 1.000 KI-geprüfte Kommentare | Antwortzeit je Stapel |
|---|---|---|---|
| `claude-opus-5-5` (Standard) | 15/15 | ca. 1,79 USD | ca. 10 s |
| `claude-haiku-5-5` | 15/15 | ca. 0,05 USD | ca. 5 s |

Kommentare, die schon eine Regel eindeutig erkennt (Sperrwort, Link, Telefonnummer), gehen nicht an die KI. Größere Stapel senken die Kosten je Kommentar zusätzlich.

### Beispielrechnung je Streamer und Monat

Annahme: 5 LIVEs pro Woche à 2 Stunden, 1.000 Kommentare pro Stunde, also rund 43.000 Kommentare im Monat.

| Modell | KI-Kosten/Monat |
|---|---|
| Opus 5.5 | ca. 75 USD |
| Haiku 5.5 | ca. 2 USD |

Kleinere Streamer mit 200 Kommentaren pro Stunde kosten nur ein Fünftel davon.

**Empfehlung:** Für den Pilot `LM_MODEL=claude-haiku-5-5` setzen. Im Test war die Qualität gleich, bei rund 97 % weniger Kosten. Die Umstellung ist eine Zeile in der Server-Konfiguration und kann jederzeit zurückgenommen werden. Standard ist Opus 5.5, bis du entscheidest.

## Kostenschutz & Zuordnung

- **Tageslimit je Streamer:** `AI_DAILY_BUDGET_USD` (Standard 5 USD). Danach nur noch Regelprüfung, und im Dashboard erscheint ein Fehlereintrag.
- **Zuordnung:** Jeder KI-Aufruf wird mit Tokens und Kosten dem Streamer zugeordnet. Das Agentur-Dashboard zeigt „KI 30 T.“ je Streamer. Damit lässt sich monatlich pauschal oder nach Verbrauch weiterberechnen.
- **Zentral abgerechnet:** Ein Anthropic-Konto der Agentur. Der Schlüssel liegt nur auf dem Server. Ein eigener Schlüssel je Streamer ist für später vorbereitet, aber nicht umgesetzt.
- Im Anthropic-Konto zusätzlich ein **monatliches Ausgabenlimit** setzen (Console → Limits).

## Gesamt (Pilot, 1 Streamer, Haiku)

**ca. 6–7 USD pro Monat.** Mit Opus je nach Chat-Menge ca. 20–80 USD pro Monat.
