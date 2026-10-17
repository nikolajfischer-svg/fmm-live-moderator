# Kosten

Stand: 17.10.2026 · Version 1.1 (Self-Hosting: jeder Streamer betreibt und bezahlt seinen eigenen Moderator)

## Agentur
**0 € laufend.** Das Repository auf GitHub, die Einstiegsseite (GitHub Pages) und die Prüfstraße (GitHub Actions) sind für öffentliche Repositories kostenlos. Siehe `VERTEILUNG.md`.

## Streamer (zahlt direkt beim Anbieter, monatlich kündbar)
| Posten | Kosten/Monat |
|---|---|
| Render Web-Service `0.5c-512mb` (Frankfurt, dauerhaft an) | ca. 7 USD* |
| Render Speicher 1 GB | 0,25 USD |
| Render-Arbeitsbereich „Hobby“ | 0 USD |
| Anthropic-KI, Standardmodell Claude Haiku 5.5 | meist 1–3 USD (gemessen: ca. 0,05 USD je 1.000 KI-geprüfte Kommentare) |
| **Summe** | **ca. 8–10 USD** |

\* Laut Render-Preisangaben 2026 („Starter“, 512 MB, 0,5 CPU). Render zeigt den genauen Preis vor dem Bestätigen an.

Anthropic arbeitet mit Guthaben (Kauf ab 5 USD). Der Moderator hat ein eingebautes Tageslimit von 2 USD (`AI_DAILY_BUDGET_USD`). Danach prüft er nur noch mit Regeln. Zusätzlich empfiehlt die Anleitung ein Monatslimit im Anthropic-Konto.

Wer die beste Qualität will, kann bei Render unter Environment `LM_MODEL=claude-opus-5-5` setzen. Kosten: ca. 1,79 USD je 1.000 Kommentare. Im Test war die Trefferquote gleich (15/15).

## Warum kein kostenloser Server?
Kostenlose Pläne (Render Free, Koyeb Free) legen den Server nach 15–60 Minuten ohne Aufrufe schlafen. Ein schlafender Server erkennt den LIVE-Start nicht. Der Moderator muss rund um die Uhr laufen, deshalb ist der kleinste Bezahltarif nötig.
