"""Web-Server: Streamer-App (Einrichtungsassistent + Live-Ansicht), Moderator-Ansicht, Agentur-Dashboard."""
from __future__ import annotations

import asyncio
import hmac
import html
import json
import logging
import time
import re
from collections import Counter, defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import VERSION
from .ai import ClaudeClassifier, OfflineClassifier
from .config import Settings, load_settings
from .db import Database
from .live import BotManager, SourceFactory, TikTokSource, UserNotFound
from .pipeline import Hub
from .rules import CATEGORIES, DECISIONS, PRESETS, keyword_filter_export, merged_settings

log = logging.getLogger("fmm_live.web")
STATIC = Path(__file__).parent / "static"


# --------------------------------------------------------------------------- Modelle
class SettingsIn(BaseModel):
    preset: str = "standard"
    categories: dict[str, bool] = Field(default_factory=dict, max_length=20)
    blocked_words: list[str] = Field(default_factory=list, max_length=300)
    use_base_list: bool = True
    allowed_users: list[str] = Field(default_factory=list, max_length=200)
    block_links: bool = True
    ai: dict[str, Any] = Field(default_factory=dict, max_length=10)


class ProfileIn(BaseModel):
    tiktok_user: str = Field(min_length=2, max_length=40)


class BotIn(BaseModel):
    active: bool


class TestMessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=300)


class NewStreamerIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    preset: str = "standard"


class ClaimIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    admin_key: str = Field(default="", max_length=200)


class DiagnoseIn(BaseModel):
    tiktok_user: str = Field(min_length=2, max_length=60)
    seconds: int = Field(default=20, ge=5, le=60)


class HeartbeatIn(BaseModel):
    client: str = Field(default="", max_length=200)


class RateLimiter:
    """Einfacher Speicher-Limiter je Schluessel (ein Server-Prozess reicht fuer den Pilot)."""

    def __init__(self) -> None:
        self._hits: dict[str, deque] = defaultdict(deque)

    def hit(self, key: str, n: int, per: float) -> None:
        q, now = self._hits[key], time.time()
        while q and now - q[0] > per:
            q.popleft()
        if len(q) >= n:
            raise HTTPException(429, "Bitte einen Moment warten und dann erneut versuchen.")
        q.append(now)


def redact(text: str) -> str:
    """Entfernt Zugangsdaten aus URLs in Fehlermeldungen (z. B. Proxy-Passwort)."""
    return re.sub(r"//[^@/\s]+@", "//***@", text)


def _clean_settings(data: SettingsIn) -> dict:
    s = merged_settings({})
    s["preset"] = data.preset if data.preset in PRESETS else "standard"
    s["categories"] = {k: bool(data.categories.get(k, True)) for k in CATEGORIES}
    s["blocked_words"] = sorted({w.strip().lower()[:40] for w in data.blocked_words if w.strip()})[:300]
    s["use_base_list"] = data.use_base_list
    s["allowed_users"] = sorted({u.strip().lstrip("@").lower()[:40] for u in data.allowed_users if u.strip()})[:200]
    s["block_links"] = data.block_links
    ai = data.ai or {}
    s["ai"] = {
        "enabled": bool(ai.get("enabled", True)),
        "questions": bool(ai.get("questions", True)),
        "reply_suggestions": bool(ai.get("reply_suggestions", True)),
        "house_rules": str(ai.get("house_rules", ""))[:800],
    }
    return s


def _clean_user(name: str) -> str:
    name = name.strip()
    for prefix in ("https://www.tiktok.com/", "http://www.tiktok.com/", "www.tiktok.com/", "tiktok.com/"):
        if name.lower().startswith(prefix):
            name = name[len(prefix):]
    name = name.split("?")[0].replace("/live", "").strip("/").lstrip("@").strip()
    if not name or not all(c.isalnum() or c in "._" for c in name):
        raise HTTPException(400, "Bitte nur den TikTok-Benutzernamen eingeben (Buchstaben, Zahlen, Punkt, Unterstrich).")
    return name.lower()


def session_report(db: Database, streamer_id: int, session_id: int) -> dict:
    sessions = [s for s in db.sessions(streamer_id, limit=500) if s["id"] == session_id]
    if not sessions:
        raise HTTPException(404, "Live nicht gefunden")
    sess = sessions[0]
    events = db.events(streamer_id, session_id=session_id, limit=100000)
    decisions = Counter(e["decision"] for e in events)
    categories = Counter(e["category"] for e in events if e["category"])
    offenders = Counter(e["viewer_handle"] or e["viewer_name"] for e in events
                        if e["decision"] not in ("ok", "frage"))
    questions = [{"viewer": e["viewer_name"], "text": e["text"], "suggestion": e["suggestion"]}
                 for e in events if e["decision"] == "frage"][-30:]
    end = sess["ended_at"] or time.time()
    return {
        "session": sess,
        "duration_min": round((end - sess["started_at"]) / 60, 1),
        "total": len(events),
        "decisions": dict(decisions),
        "categories": {CATEGORIES.get(k, k): v for k, v in categories.items()},
        "top_offenders": offenders.most_common(10),
        "questions": questions,
        "keyword_suggestions": [],
    }


# --------------------------------------------------------------------------- App
def create_app(settings: Settings | None = None, *, source_factory: SourceFactory | None = None,
               classifier=None, start_bots: bool = True) -> FastAPI:
    settings = settings or load_settings()
    db = Database(settings.db_path)
    hub = Hub()
    if classifier is None:
        if settings.ai_enabled and settings.anthropic_api_key:
            classifier = ClaudeClassifier(settings.anthropic_api_key, settings.model, settings.effort)
        else:
            classifier = OfflineClassifier()
    manager = BotManager(settings, db, hub, classifier, source_factory=source_factory,
                         daily_budget_usd=settings.daily_budget_usd)

    async def _housekeeping() -> None:
        """Wachhund: startet beendete/abgestuerzte Wachdienste neu und loescht alte Chat-Daten."""
        tick = 0
        while True:
            await asyncio.sleep(60)
            tick += 1
            try:
                if start_bots:
                    await manager.sync_all()
            except Exception as exc:
                log.warning("Wachhund-Abgleich fehlgeschlagen: %s", exc)
                db.add_error(None, "wachhund", f"{type(exc).__name__}: {exc}")
            if tick % 60 == 1:
                try:
                    db.purge_old(settings.retention_days)
                except Exception as exc:
                    log.warning("Aufräumen fehlgeschlagen: %s", exc)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        db.close_open_sessions()
        if start_bots:
            await manager.sync_all()
        hk = asyncio.create_task(_housekeeping())
        yield
        hk.cancel()
        await manager.shutdown()
        db.close()

    app = FastAPI(title="FMM Live Moderator", version=VERSION, lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.state.db, app.state.manager, app.state.settings, app.state.hub = db, manager, settings, hub
    limiter = RateLimiter()
    sse_count: dict[int, int] = defaultdict(int)

    @app.middleware("http")
    async def body_limit(request: Request, call_next):
        try:
            size = int(request.headers.get("content-length") or 0)
        except ValueError:
            size = 0
        if size > 64_000:
            return JSONResponse({"detail": "Anfrage zu groß"}, status_code=413)
        return await call_next(request)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'")
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        response.headers["Cache-Control"] = response.headers.get("Cache-Control", "no-store")
        return response

    # ---------------------------------------------------------------- Auth
    def _token_from(request: Request, authorization: str | None) -> str:
        if authorization and authorization.lower().startswith("bearer "):
            return authorization[7:].strip()
        return request.query_params.get("t", "")

    def auth(request: Request, authorization: str | None = Header(default=None)) -> tuple[dict, str]:
        found = db.streamer_by_token(_token_from(request, authorization))
        if not found:
            raise HTTPException(401, "Zugangslink ungültig oder abgelaufen. Einen neuen Link erzeugst du über /admin deines Moderators (Schlüssel: ADMIN_TOKEN bei Render) oder über deine Agentur.")
        return found

    def streamer_only(ctx: tuple[dict, str] = Depends(auth)) -> dict:
        row, role = ctx
        if role != "streamer":
            raise HTTPException(403, "Diese Funktion ist nur für den Streamer selbst freigegeben.")
        return row

    def admin(request: Request, authorization: str | None = Header(default=None)) -> None:
        token = authorization[7:].strip() if authorization and authorization.lower().startswith("bearer ") else ""
        if not settings.admin_token or len(settings.admin_token) < 16:
            raise HTTPException(503, "ADMIN_TOKEN ist auf dem Server nicht (sicher) gesetzt.")
        if not hmac.compare_digest(token.encode(), settings.admin_token.encode()):
            limiter.hit("admin-fail", 20, 300)  # mehr als 20 Fehlversuche in 5 Min. -> 429
            raise HTTPException(401, "Admin-Zugang verweigert")

    def invite_link(token: str) -> str:
        return f"{settings.public_url}/app#t={token}"

    def mod_link(token: str) -> str:
        return f"{settings.public_url}/app#m={token}"

    # ---------------------------------------------------------------- Seiten
    @app.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse("/app")

    @app.get("/app", include_in_schema=False)
    async def app_page():
        return FileResponse(STATIC / "app.html", headers={"Cache-Control": "no-cache"})

    @app.get("/admin", include_in_schema=False)
    async def admin_page():
        return FileResponse(STATIC / "admin.html", headers={"Cache-Control": "no-cache"})

    @app.get("/anleitung", include_in_schema=False)
    async def guide_page():
        return FileResponse(STATIC / "anleitung.html", headers={"Cache-Control": "no-cache"})

    @app.get("/datenschutz", include_in_schema=False)
    async def privacy_page():
        page = (STATIC / "datenschutz.html").read_text(encoding="utf-8")
        contact = ", ".join(x for x in (settings.operator_address, settings.operator_email) if x)
        page = (page.replace("{{OPERATOR_NAME}}", html.escape(settings.operator_name))
                    .replace("{{OPERATOR_CONTACT}}", html.escape(contact or "Kontakt über den Betreiber dieses Moderators"))
                    .replace("{{OPERATOR_EMAIL}}", html.escape(settings.operator_email or "den Betreiber dieses Moderators"))
                    .replace("{{HOSTING_INFO}}", html.escape(settings.hosting_info or "Cloud-Hosting in der EU (Frankfurt)")))
        return HTMLResponse(page, headers={"Cache-Control": "no-cache"})

    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/healthz")
    async def health():
        return {"ok": True, "version": VERSION, "uptime_s": int(time.time() - manager.started_at)}

    # ---------------------------------------------------------------- Ersteinrichtung (eigener Server je Streamer)
    first_start = float(db.meta_setdefault("first_start", str(time.time())))

    def claim_state() -> dict:
        if not settings.self_hosted or db.count_streamers() > 0:
            return {"claimable": False, "needs_key": False}
        open_window = time.time() - first_start < settings.claim_window_hours * 3600
        return {"claimable": True, "needs_key": not open_window}

    @app.get("/api/claim-status")
    async def claim_status():
        return {**claim_state(), "self_hosted": settings.self_hosted, "version": VERSION,
                "ai_available": isinstance(manager.classifier, ClaudeClassifier)}

    @app.post("/api/claim")
    async def claim(data: ClaimIn):
        """Der erste Aufruf eines frisch gestarteten eigenen Servers macht den Aufrufer zum Besitzer.
        Nach Ablauf des Zeitfensters nur noch mit dem ADMIN_TOKEN (steht beim Hosting-Anbieter)."""
        limiter.hit("claim", 10, 300)
        state = claim_state()
        if not state["claimable"]:
            raise HTTPException(409, "Dieser Moderator ist bereits eingerichtet. Öffne deinen persönlichen Link.")
        if state["needs_key"]:
            if not settings.admin_token or not hmac.compare_digest(data.admin_key.strip().encode(),
                                                                    settings.admin_token.encode()):
                raise HTTPException(403, "Das Einrichtungsfenster ist abgelaufen. Bitte den Admin-Schlüssel "
                                         "(ADMIN_TOKEN) aus deinem Render-Konto eingeben.")
        sid, token = db.create_streamer(data.name, merged_settings({}))
        if db.count_streamers() > 1:  # gleichzeitige Anfragen: nur die erste gewinnt
            db.delete_streamer_data(sid)
            raise HTTPException(409, "Dieser Moderator ist bereits eingerichtet.")
        return {"ok": True, "token": token, "link": invite_link(token)}

    # ---------------------------------------------------------------- Streamer-API
    @app.get("/api/me")
    async def me(ctx: tuple[dict, str] = Depends(auth)):
        row, role = ctx
        if role == "streamer":
            db.update_streamer(row["id"], last_seen_at=time.time())
        s = merged_settings(row["settings"])
        return {
            "role": role,
            "version": VERSION,
            "streamer": {"id": row["id"], "name": row["name"], "tiktok_user": row["tiktok_user"],
                         "setup_done": bool(row["setup_done"]), "bot_active": bool(row["bot_active"]),
                         "has_mod_link": row["has_mod_link"]},
            "settings": s if role == "streamer" else None,
            "status": manager.status(row["id"]),
            "presets": {k: v["label"] for k, v in PRESETS.items()},
            "categories": CATEGORIES,
            "decisions": DECISIONS,
            "ai_available": isinstance(manager.classifier, ClaudeClassifier),
            "keyword_filter": keyword_filter_export(s) if role == "streamer" else [],
        }

    @app.put("/api/settings")
    async def put_settings(data: SettingsIn, row: dict = Depends(streamer_only)):
        clean = _clean_settings(data)
        db.update_streamer(row["id"], settings=clean)
        await manager.sync(row["id"])
        return {"ok": True, "settings": clean, "keyword_filter": keyword_filter_export(clean)}

    @app.put("/api/profile")
    async def put_profile(data: ProfileIn, row: dict = Depends(streamer_only)):
        user = _clean_user(data.tiktok_user)
        db.update_streamer(row["id"], tiktok_user=user)
        await manager.sync(row["id"])
        return {"ok": True, "tiktok_user": user}

    @app.post("/api/test-connection")
    async def test_connection(row: dict = Depends(streamer_only)):
        limiter.hit(f"tc-{row['id']}", 4, 60)
        user = db.get_streamer(row["id"])["tiktok_user"]
        if not user:
            raise HTTPException(400, "Bitte zuerst den TikTok-Benutzernamen speichern.")
        if not settings.tiktok_enabled:
            return {"ok": False, "found": None, "live": None,
                    "message": "TikTok-Anbindung ist auf diesem Server deaktiviert (Testmodus)."}
        factory = source_factory or (lambda u: TikTokSource(u, settings.sign_api_key, settings.tiktok_proxy))
        try:
            live = await asyncio.wait_for(factory(user).is_live(), timeout=25)
        except UserNotFound:
            return {"ok": False, "found": False, "live": False,
                    "message": f"Das Konto @{user} wurde bei TikTok nicht gefunden. Bitte Schreibweise prüfen."}
        except Exception as exc:
            db.add_error(row["id"], "verbindungstest", redact(f"{type(exc).__name__}: {exc}"))
            return {"ok": False, "found": None, "live": None,
                    "message": "TikTok hat nicht rechtzeitig geantwortet. Bitte in einer Minute erneut testen."}
        msg = (f"Verbindung klappt: @{user} ist gerade LIVE." if live
               else f"Verbindung klappt: @{user} gefunden. Sobald du LIVE gehst, startet die Moderation automatisch.")
        return {"ok": True, "found": True, "live": live, "message": msg}

    @app.post("/api/test-message")
    async def test_message(data: TestMessageIn, row: dict = Depends(streamer_only)):
        limiter.hit(f"tm-{row['id']}", 10, 60)
        limiter.hit(f"tm-day-{row['id']}", 200, 86400)
        bot = manager.bot(row["id"])
        future = asyncio.get_running_loop().create_future()
        await bot.pipeline.submit({"text": data.text, "viewer_name": "Testnachricht", "viewer_handle": "",
                                   "viewer_id": "test", "is_test": True, "_future": future})
        try:
            ev = await asyncio.wait_for(future, timeout=45)
        except asyncio.TimeoutError:
            raise HTTPException(504, "Die Prüfung hat zu lange gedauert. Bitte erneut versuchen.")
        return {"ok": True, "event": ev}

    @app.post("/api/setup-complete")
    async def setup_complete(row: dict = Depends(streamer_only)):
        current = db.get_streamer(row["id"])
        if not current["tiktok_user"]:
            raise HTTPException(400, "Bitte zuerst den TikTok-Benutzernamen speichern.")
        db.update_streamer(row["id"], setup_done=1, bot_active=1)
        await manager.sync(row["id"])
        return {"ok": True, "status": manager.status(row["id"])}

    @app.post("/api/bot")
    async def set_bot(data: BotIn, row: dict = Depends(streamer_only)):
        db.update_streamer(row["id"], bot_active=1 if data.active else 0)
        await manager.sync(row["id"])
        return {"ok": True, "status": manager.status(row["id"])}

    @app.get("/api/events")
    async def get_events(after: int = Query(0, ge=0), flagged: bool = False, limit: int = Query(200, ge=1, le=500),
                         ctx: tuple[dict, str] = Depends(auth)):
        row, _ = ctx
        return {"events": db.events(row["id"], after_id=after, only_flagged=flagged, limit=limit)}

    @app.post("/api/events/{event_id}/handled")
    async def handled(event_id: int, ctx: tuple[dict, str] = Depends(auth)):
        row, _ = ctx
        if not db.mark_handled(row["id"], event_id):
            raise HTTPException(404, "Nicht gefunden")
        hub.publish(row["id"], {"type": "handled", "id": event_id})
        return {"ok": True}

    @app.get("/api/sessions")
    async def get_sessions(ctx: tuple[dict, str] = Depends(auth)):
        row, _ = ctx
        return {"sessions": db.sessions(row["id"])}

    @app.get("/api/sessions/{session_id}/report")
    async def get_report(session_id: int, ctx: tuple[dict, str] = Depends(auth)):
        row, _ = ctx
        return session_report(db, row["id"], session_id)

    @app.post("/api/mod-link")
    async def new_mod_link(row: dict = Depends(streamer_only)):
        return {"ok": True, "link": mod_link(db.rotate_mod_token(row["id"]))}

    @app.post("/api/heartbeat")
    async def heartbeat(data: HeartbeatIn, ctx: tuple[dict, str] = Depends(auth)):
        row, role = ctx
        if role == "streamer":
            db.update_streamer(row["id"], last_seen_at=time.time(), client_info=data.client)
        return {"ok": True, "version": VERSION}

    @app.get("/api/stream")
    async def stream(request: Request, ctx: tuple[dict, str] = Depends(auth)):
        row, _ = ctx
        sid = row["id"]
        token = _token_from(request, None)
        if sse_count[sid] >= 6:
            raise HTTPException(429, "Zu viele offene Live-Ansichten für diesen Zugang.")
        sse_count[sid] += 1
        queue = hub.subscribe(sid)

        def still_valid() -> bool:
            found = db.streamer_by_token(token)
            return bool(found) and found[0]["id"] == sid

        async def gen():
            checked = time.time()
            try:
                yield f"data: {json.dumps({'type': 'status', 'status': manager.status(sid)})}\n\n"
                while True:
                    if await request.is_disconnected():
                        break
                    if time.time() - checked > 5:
                        checked = time.time()
                        if not still_valid():
                            yield f"data: {json.dumps({'type': 'revoked'})}\n\n"
                            break
                    try:
                        payload = await asyncio.wait_for(queue.get(), timeout=20)
                        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    except asyncio.TimeoutError:
                        yield f"data: {json.dumps({'type': 'status', 'status': manager.status(sid)})}\n\n"
            finally:
                hub.unsubscribe(sid, queue)
                sse_count[sid] = max(0, sse_count[sid] - 1)

        return StreamingResponse(gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # ---------------------------------------------------------------- Admin-API
    @app.get("/api/admin/overview", dependencies=[Depends(admin)])
    async def overview():
        since = time.time() - 30 * 86400
        usage = {u["streamer_id"]: u for u in db.usage_summary(since=since)}
        errors = db.errors(limit=200)
        err_count = Counter(e["streamer_id"] for e in errors if e["ts"] > time.time() - 86400)
        rows = []
        for s in db.list_streamers():
            st = manager.status(s["id"])
            rows.append({
                "id": s["id"], "name": s["name"], "tiktok_user": s["tiktok_user"],
                "setup_done": bool(s["setup_done"]), "bot_active": bool(s["bot_active"]),
                "disabled": bool(s["disabled"]), "last_seen_at": s["last_seen_at"],
                "client_info": s["client_info"], "version": VERSION, "status": st,
                "usage_30d": usage.get(s["id"], {"calls": 0, "cost_usd": 0.0}),
                "errors_24h": err_count.get(s["id"], 0),
                "last_session": (db.sessions(s["id"], limit=1) or [None])[0],
            })
        return {
            "version": VERSION, "uptime_s": int(time.time() - manager.started_at),
            "model": getattr(manager.classifier, "model", "offline"),
            "ai_available": isinstance(manager.classifier, ClaudeClassifier),
            "tiktok_enabled": settings.tiktok_enabled,
            "public_url": settings.public_url,
            "streamers": rows, "errors": errors[:50],
        }

    @app.post("/api/admin/diagnose", dependencies=[Depends(admin)])
    async def diagnose(data: DiagnoseIn):
        limiter.hit("diagnose", 6, 60)
        user = _clean_user(data.tiktok_user)
        factory = source_factory or (lambda u: TikTokSource(u, settings.sign_api_key, settings.tiktok_proxy))
        result: dict[str, Any] = {"user": user, "live": None, "connected_after_s": None, "comments": 0,
                                  "viewers": 0, "error": None, "samples": []}
        t0 = time.time()
        try:
            result["live"] = await asyncio.wait_for(factory(user).is_live(), timeout=20)
        except Exception as exc:
            result["error"] = redact(f"Live-Status: {type(exc).__name__}: {exc}")[:300]
            return result
        if not result["live"]:
            return result
        src = factory(user)

        async def on_comment(c: dict) -> None:
            result["comments"] += 1
            if len(result["samples"]) < 3:
                result["samples"].append(c["text"][:60])

        def on_connected(_room: str) -> None:
            result["connected_after_s"] = round(time.time() - t0, 1)

        def on_viewers(n: int) -> None:
            result["viewers"] = n

        try:
            await asyncio.wait_for(src.run(on_comment, on_connected, on_viewers), timeout=data.seconds)
        except asyncio.TimeoutError:
            pass
        except Exception as exc:
            result["error"] = redact(f"Chat: {type(exc).__name__}: {exc}")[:300]
        finally:
            await src.close()
        return result

    @app.post("/api/admin/streamers", dependencies=[Depends(admin)])
    async def create_streamer(data: NewStreamerIn):
        s = merged_settings({"preset": data.preset})
        sid, token = db.create_streamer(data.name, s)
        return {"ok": True, "id": sid, "link": invite_link(token)}

    @app.post("/api/admin/streamers/{sid}/rotate", dependencies=[Depends(admin)])
    async def rotate(sid: int):
        if not db.get_streamer(sid):
            raise HTTPException(404, "Nicht gefunden")
        return {"ok": True, "link": invite_link(db.rotate_token(sid))}

    @app.post("/api/admin/streamers/{sid}/disable", dependencies=[Depends(admin)])
    async def disable(sid: int, on: bool = True):
        if not db.get_streamer(sid):
            raise HTTPException(404, "Nicht gefunden")
        db.update_streamer(sid, disabled=1 if on else 0)
        await manager.sync(sid)
        return {"ok": True}

    @app.delete("/api/admin/streamers/{sid}", dependencies=[Depends(admin)])
    async def delete(sid: int):
        if not db.get_streamer(sid):
            raise HTTPException(404, "Nicht gefunden")
        db.update_streamer(sid, bot_active=0, disabled=1)
        await manager.sync(sid)
        bot = manager.bots.pop(sid, None)
        if bot:
            await bot.pipeline.stop()
        db.delete_streamer_data(sid)
        return {"ok": True}

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError):
        fields = {str(e.get("loc", [""])[-1]) for e in exc.errors()}
        if "tiktok_user" in fields:
            msg = "Bitte einen gültigen TikTok-Benutzernamen eingeben (2 bis 40 Zeichen)."
        elif "text" in fields:
            msg = "Bitte eine Nachricht mit 1 bis 300 Zeichen eingeben."
        elif "name" in fields:
            msg = "Bitte einen Namen mit 1 bis 80 Zeichen eingeben."
        else:
            msg = "Die Eingabe ist ungültig oder zu lang. Bitte prüfen und erneut versuchen."
        return JSONResponse({"detail": msg}, status_code=422)

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException):
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    return app


def run() -> None:
    import os

    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    for noisy in ("httpx", "httpx2", "httpcore", "TikTokLive"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    uvicorn.run(create_app(), host=os.environ.get("HOST", "0.0.0.0"), port=int(os.environ.get("PORT", "8000")),
                proxy_headers=True, forwarded_allow_ips="*", access_log=False)


if __name__ == "__main__":
    run()
