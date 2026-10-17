"""Praxistest Wiederverbindung + Doppelte + KI auf echtem LIVE-Chat (nur lesen, tonlos).

Aufruf: python scripts/reconnect_test.py <user1,user2,...> [modell]
Startet den echten Bot-Wachdienst, trennt nach 40 s die Chat-Verbindung hart (simulierter Abbruch)
und misst, ob und wie schnell er sich selbst wieder verbindet.
"""
import asyncio
import os
import shutil
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

tmp = Path(tempfile.mkdtemp(prefix="fmm_reconnect_"))
os.environ["DATA_DIR"] = str(tmp)
os.environ["LIVE_POLL_SECONDS"] = "15"
os.environ["BATCH_SECONDS"] = "2"
if len(sys.argv) > 2:
    os.environ["LM_MODEL"] = sys.argv[2]

from fmm_live.ai import ClaudeClassifier, OfflineClassifier  # noqa: E402
from fmm_live.config import load_settings  # noqa: E402
from fmm_live.db import Database  # noqa: E402
from fmm_live.live import BotManager, TikTokSource  # noqa: E402
from fmm_live.pipeline import Hub  # noqa: E402


async def pick_user(users):
    best = None
    for u in users:
        src = TikTokSource(u)
        try:
            if await asyncio.wait_for(src.is_live(), 15):
                n = {"c": 0}

                async def count(_c):
                    n["c"] += 1
                try:
                    await asyncio.wait_for(src.run(count, lambda r: None, lambda v: None), 15)
                except asyncio.TimeoutError:
                    pass
                await src.close()
                print(f"  @{u}: {n['c']} Kommentare in 15 s")
                if n["c"] >= 3 and (best is None or n["c"] > best[1]):
                    best = (u, n["c"])
                if best and best[1] >= 8:
                    break
        except Exception as exc:
            print(f"  @{u}: {type(exc).__name__}")
    return best[0] if best else None


async def main():
    s = load_settings()
    user = await pick_user([u.strip() for u in sys.argv[1].split(",") if u.strip()])
    if not user:
        sys.exit("kein aktiver LIVE mit Chat gefunden")
    print(f"Test-LIVE: @{user}")
    db = Database(s.db_path)
    sources = []

    def factory(u):
        src = TikTokSource(u)
        sources.append(src)
        return src

    clf = ClaudeClassifier(s.anthropic_api_key, s.model, "low") if s.anthropic_api_key else OfflineClassifier()
    mgr = BotManager(s, db, Hub(), clf, source_factory=factory, daily_budget_usd=0.5)
    sid, _ = db.create_streamer("Reconnect-Test", {})
    db.update_streamer(sid, tiktok_user=user, setup_done=1, bot_active=1)
    await mgr.sync(sid)
    bot = mgr.bots[sid]
    t0 = time.time()
    while bot.status.state != "live" and time.time() - t0 < 60:
        await asyncio.sleep(0.5)
    print(f"1) Automatische Verbindung: {bot.status.state} nach {time.time() - t0:.1f} s")
    await asyncio.sleep(40)
    before = len(db.events(sid, limit=100000))
    print(f"2) Kommentare vor dem Abbruch: {before}")
    t_drop = time.time()
    # harter Abbruch der Chat-Verbindung (wie Netzwerkausfall/Server-Trennung)
    await sources[0].client._ws.disconnect() if sources[0].client else None
    states = []
    while time.time() - t_drop < 120:
        states.append(bot.status.state)
        if bot.status.state == "live" and time.time() - t_drop > 2 and "wartet" in states:
            break
        await asyncio.sleep(0.5)
    reconnect = time.time() - t_drop
    ok = bot.status.state == "live"
    print(f"3) Nach Abbruch: Zustände {list(dict.fromkeys(states))} -> wieder verbunden: {ok} nach {reconnect:.1f} s")
    await asyncio.sleep(30)
    await mgr.shutdown()
    events = db.events(sid, limit=100000)
    print(f"4) Kommentare gesamt: {len(events)} (nach Wiederverbindung: {len(events) - before})")
    dup = Counter((e["viewer_id"], e["text"], round(e["ts"])) for e in events)
    dups = [k for k, v in dup.items() if v > 1]
    print(f"5) Doppelte Kommentare: {len(dups)}")
    dec = Counter(e["decision"] for e in events)
    print(f"6) KI-Entscheidungen auf echtem Chat ({clf.model}): {dict(dec)}")
    for e in [e for e in events if e["decision"] != "ok"][:8]:
        print(f"     [{e['decision']}] {e['text'][:60]!r} - {e['reason'][:50]}")
    print(f"7) Sessions: {[(x['comments'], bool(x['ended_at'])) for x in db.sessions(sid)]}")
    print(f"8) Fehlerprotokoll: {[e['message'][:80] for e in db.errors(sid)]}")
    usage = db.usage_summary(sid)
    print(f"9) KI-Kosten: {usage[0]['cost_usd'] if usage else 0} USD")
    db.close()
    shutil.rmtree(tmp, ignore_errors=True)


asyncio.run(main())
