# Weitergabe durch die Agentur (ohne laufende Kosten)

## Prüfung: Ist die Weitergabe für die Agentur kostenlos?
**Ja.**

| Was | Wer | Kosten für die Agentur |
|---|---|---|
| Quellcode + Releases auf GitHub (öffentliches Repository) | Agentur | 0 € |
| Einstiegsseite (GitHub Pages) = universeller Link | Agentur | 0 € |
| Prüfstraße (GitHub Actions, öffentliches Repo) | Agentur | 0 € |
| Server je Streamer (Render) | Streamer, eigenes Konto, eigene Zahlungsdaten | 0 € |
| KI je Streamer (Anthropic) | Streamer, eigener Schlüssel | 0 € |

Die Agentur betreibt keine Server, sieht keine Passwörter oder Zahlungsdaten und hat keinen Zugriff auf die Server der Streamer.

**Folge:** Ohne zentralen Server gibt es kein zentrales Dashboard. Jeder Streamer sieht nur seinen eigenen Moderator. Die Agentur hilft im Bedarfsfall über die Anleitung, ohne selbst Zugriff zu haben.

## Der universelle Link
`https://__OWNER__.github.io/fmm-live-moderator/` (eine Seite für alle Streamer: Kosten, 3 Schritte, Deploy-Button).

## Updates verteilen
1. Code ändern, Version in `fmm_live/__init__.py` erhöhen, auf GitHub hochladen, Release anlegen.
2. Streamer aktualisieren selbst: Render → ihr Dienst → **Manual Deploy → Deploy latest commit**.
   Auto-Deploy ist bewusst aus, damit kein Update ungefragt mitten im LIVE kommt.

## Cloud-Verbindungstest (kostenlos)
GitHub → Actions → „Prüfung“ → **Run workflow** → bei `live_users` 2–3 gerade laufende TikTok-LIVEs eintragen.
Der Test baut den Container, richtet ihn ein, startet ihn neu und liest echten LIVE-Chat von einer Rechenzentrums-IP.
