"""Echter Lesetest gegen ein laufendes, oeffentliches TikTok LIVE (nur lesen, kein Login).

Aufruf:  python scripts/live_lesetest.py <benutzer> [sekunden] [modell|offline]
Die Testdatenbank liegt in einem temporaeren Ordner und wird danach geloescht.
"""
import asyncio
import shutil
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fmm_live.ai import ClaudeClassifier, OfflineClassifier  # noqa: E402
from fmm_live.config import _PRICES, load_settings  # noqa: E402
from fmm_live.db import Database  # noqa: E402
from fmm_live.live import TikTokSource  # noqa: E402
from fmm_live.pipeline import Hub, Pipeline  # noqa: E402


async def main() -> None:
    user = sys.argv[1].lstrip("@")
    seconds = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    model = sys.argv[3] if len(sys.argv) > 3 else "offline"
    s = load_settings()
    tmp = Path(tempfile.mkdtemp(prefix="fmm_lesetest_"))
    db = Database(tmp / "t.sqlite3")
    sid, _ = db.create_streamer("Lesetest", {})
    clf = OfflineClassifier() if model == "offline" else ClaudeClassifier(s.anthropic_api_key, model, "low")
    p_in, p_out = _PRICES.get(model, (0, 0))
    pipe = Pipeline(sid, {}, db, Hub(), clf, batch_seconds=2.5, batch_max=25, price_in=p_in, price_out=p_out,
                    daily_budget_usd=1.0)
    pipe.start()
    src = TikTokSource(user, s.sign_api_key)
    t0 = time.time()
    live = await src.is_live()
    print(f"is_live(@{user}) = {live}  ({time.time() - t0:.1f} s)")
    if not live:
        return
    state = {"connected": None, "viewers": 0}
    session = db.start_session(sid, None)
    pipe.new_session(session)

    def on_conn(room):
        state["connected"] = time.time()
        print(f"VERBUNDEN mit Raum {room} nach {time.time() - t0:.1f} s")

    def on_viewers(n):
        state["viewers"] = n

    try:
        await asyncio.wait_for(src.run(pipe.submit, on_conn, on_viewers), timeout=seconds)
        print("Stream beendet")
    except asyncio.TimeoutError:
        print(f"Testzeit {seconds} s vorbei")
    except Exception as exc:
        print(f"FEHLER: {type(exc).__name__}: {exc}")
    finally:
        await src.close()
    await pipe.drain(15)
    events = db.events(sid, limit=100000)
    dec = Counter(e["decision"] for e in events)
    usage = db.usage_summary(sid)
    print(f"Zuschauer: {state['viewers']} | Kommentare geprüft: {len(events)} | Entscheidungen: {dict(dec)}")
    if usage:
        print(f"KI: {usage[0]['calls']} Aufrufe, {usage[0]['cost_usd']} USD")
    lat = [e for e in events]
    for e in [x for x in events if x["decision"] != "ok"][:12]:
        print(f"  [{e['decision']:13}] {e['text'][:60]!r} -> {e['reason'][:60]}")
    for e in [x for x in events if x["decision"] == "ok"][:5]:
        print(f"  [ok           ] {e['text'][:60]!r}")
    print(f"Fehlerprotokoll: {db.errors(sid)}")
    await pipe.stop()
    db.close()
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
