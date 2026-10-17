"""Veroeffentlicht das Paket kostenlos auf GitHub (Repo, Pages-Einstiegsseite, Release, Pruefstrasse).

Voraussetzung: `gh auth login` erledigt.
Aufruf: python scripts/publish_github.py [--live-users a,b,c]
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "fmm-live-moderator"
GH = shutil.which("gh") or str(Path(os.environ.get("LOCALAPPDATA", "")) / "gh-cli" / "bin" / "gh.exe")


def sh(args, check=True, cwd=ROOT, stdin=None):
    cp = subprocess.run(args, cwd=cwd, text=True, capture_output=True, encoding="utf-8", errors="replace", input=stdin)
    if check and cp.returncode != 0:
        print(cp.stdout[-1500:], cp.stderr[-1500:])
        sys.exit(f"fehlgeschlagen: {' '.join(str(a) for a in args[:4])}")
    return cp.stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live-users", default="")
    a = ap.parse_args()
    owner = sh([GH, "api", "user", "--jq", ".login"])
    print("GitHub-Konto:", owner)
    from fmm_live import VERSION  # noqa: E402

    # Platzhalter durch den echten Kontonamen ersetzen
    for rel in ("README.md", "docs/index.html", "docs/VERTEILUNG.md"):
        p = ROOT / rel
        p.write_text(p.read_text(encoding="utf-8").replace("__OWNER__", owner), encoding="utf-8")
    pages = f"https://{owner}.github.io/{REPO}/"
    wa = ROOT / "docs" / "WHATSAPP_NACHRICHT.md"
    wa.write_text(wa.read_text(encoding="utf-8").replace("__LINK__", pages), encoding="utf-8")
    sh(["git", "add", "-A"])
    if sh(["git", "status", "--porcelain"]):
        sh(["git", "commit", "-q", "-m", f"Veroeffentlichung v{VERSION} fuer {owner}"])

    # Repository anlegen (oeffentlich, kostenlos) und hochladen
    exists = subprocess.run([GH, "repo", "view", f"{owner}/{REPO}"], capture_output=True).returncode == 0
    if not exists:
        sh([GH, "repo", "create", f"{owner}/{REPO}", "--public", "--description",
            "KI-Chatmoderation für TikTok LIVE - eigener Server je Streamer, Ein-Klick-Bereitstellung"])
    remotes = sh(["git", "remote"])
    url = f"https://github.com/{owner}/{REPO}.git"
    if "origin" not in remotes.split():
        sh(["git", "remote", "add", "origin", url])
    sh([GH, "auth", "setup-git"])
    sh(["git", "push", "-u", "origin", "main", "--tags"])

    # GitHub Pages aus /docs
    r = subprocess.run([GH, "api", "-X", "POST", f"repos/{owner}/{REPO}/pages", "-f", "source[branch]=main",
                        "-f", "source[path]=/docs"], capture_output=True, text=True)
    if r.returncode != 0 and "already" not in (r.stdout + r.stderr).lower():
        print("Pages-Hinweis:", (r.stdout + r.stderr)[-300:])

    # Release
    tag = f"v{VERSION}"
    if subprocess.run([GH, "release", "view", tag, "-R", f"{owner}/{REPO}"], capture_output=True).returncode != 0:
        notes = (f"**Einrichtung für Streamer:** {pages}\n\n"
                 "Eigener KI-Moderator für TikTok LIVE, läuft in der eigenen Cloud des Streamers (Render). "
                 "Kein Download und keine Installation nötig: die Einstiegsseite öffnen und dem Deploy-Button folgen.\n\n"
                 "- Anleitung: ANLEITUNG.md (liegt dem Release bei)\n- Kosten trägt der Streamer direkt beim Anbieter "
                 "(Render ca. 7,25 USD/Monat, KI meist 1–3 USD/Monat)\n- Kein TikTok-Passwort nötig")
        sh([GH, "release", "create", tag, "-R", f"{owner}/{REPO}", "--title", f"FMM Live Moderator {tag}",
            "--notes", notes, str(ROOT / "ANLEITUNG.md")])

    # Pruefstrasse (nur wenn als Workflow aktiviert)
    time.sleep(5)
    if not (ROOT / ".github" / "workflows" / "ci.yml").exists():
        print("Pruefstrasse nicht aktiviert (Vorlage unter ci/).")
        a.live_users = None
    args = None if a.live_users is None else [GH, "workflow", "run", "ci.yml", "-R", f"{owner}/{REPO}", "--ref", "main"]
    if args and a.live_users:
        args += ["-f", f"live_users={a.live_users}"]
    if args:
        sh(args, check=False)
    print("\nUniverseller Link:", pages)
    print("Repository:", f"https://github.com/{owner}/{REPO}")
    print("Deploy-Button:", f"https://render.com/deploy?repo=https://github.com/{owner}/{REPO}")


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    main()
