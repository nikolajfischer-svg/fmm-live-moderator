"""TikTok-LIVE-Anbindung (nur LESEN) und Bot-Verwaltung fuer alle Streamer.

Lesen geschieht ueber die inoffizielle Bibliothek TikTokLive: kein Login, kein Passwort,
nur der oeffentliche Benutzername. Schreibende Aktionen (Muten, Blockieren, Chat senden)
werden bewusst NICHT implementiert - TikTok bietet dafuer keine offizielle Schnittstelle.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Protocol

from .ai import Classifier
from .config import Settings
from .db import Database
from .pipeline import Hub, Pipeline

log = logging.getLogger("fmm_live.live")

OnComment = Callable[[dict], Awaitable[None]]


class LiveSource(Protocol):
    async def is_live(self) -> bool: ...

    async def run(self, on_comment: OnComment, on_connected: Callable[[str], None],
                  on_viewers: Callable[[int], None]) -> None: ...

    async def close(self) -> None: ...


class UserNotFound(Exception):
    pass


class TikTokSource:
    def __init__(self, unique_id: str, sign_api_key: str = "", proxy: str = ""):
        from TikTokLive import TikTokLiveClient
        from TikTokLive.client.web.web_settings import WebDefaults

        if sign_api_key:
            WebDefaults.tiktok_sign_api_key = sign_api_key
        self.unique_id = unique_id.lstrip("@").strip()
        self._client_cls = TikTokLiveClient
        self._proxy = proxy
        self.client = None

    def _new_client(self):
        kwargs = {}
        if self._proxy:  # optionaler Proxy, falls TikTok Rechenzentrums-IPs drosselt
            import httpx
            kwargs["web_proxy"] = httpx.Proxy(self._proxy)
        return self._client_cls(unique_id=self.unique_id, **kwargs)

    async def is_live(self) -> bool:
        from TikTokLive.client.errors import UserNotFoundError

        client = self._new_client()
        try:
            return await client.is_live()
        except UserNotFoundError as exc:
            raise UserNotFound(str(exc)) from exc
        finally:
            try:
                await client.web.close()  # client.close() blockiert im laufenden Event-Loop
            except Exception:
                pass

    async def run(self, on_comment, on_connected, on_viewers) -> None:
        from TikTokLive.events import CommentEvent, ConnectEvent, LiveEndEvent, RoomUserSeqEvent

        client = self._new_client()
        self.client = client
        ended = asyncio.Event()
        seen: dict = {}  # TikTok liefert Chatnachrichten teils mehrfach aus -> per Nachrichten-ID entdoppeln

        async def _comment(event: CommentEvent) -> None:
            user = getattr(event, "user", None)
            text = getattr(event, "comment", None) or getattr(event, "content", "") or ""
            common = getattr(event, "common", None)
            msg_id = getattr(common, "msg_id", 0) if common else 0
            key = msg_id or (getattr(user, "id", ""), text)
            now = time.time()
            if key in seen and now - seen[key] < 120:
                return
            seen[key] = now
            if len(seen) > 5000:
                for k in [k for k, t in seen.items() if now - t > 120]:
                    seen.pop(k, None)
            await on_comment({
                "text": text,
                "viewer_id": str(getattr(user, "id", "") or ""),
                "viewer_name": getattr(user, "nickname", "") or "",
                "viewer_handle": getattr(user, "unique_id", "") or "",
            })

        async def _connect(event: ConnectEvent) -> None:
            on_connected(str(event.room_id))

        async def _viewers(event: RoomUserSeqEvent) -> None:
            try:
                on_viewers(int(event.total or event.total_user or 0))
            except Exception:
                pass

        async def _end(_event: LiveEndEvent) -> None:
            ended.set()

        client.add_listener(CommentEvent, _comment)
        client.add_listener(ConnectEvent, _connect)
        client.add_listener(RoomUserSeqEvent, _viewers)
        client.add_listener(LiveEndEvent, _end)
        task = await client.start(fetch_live_check=True)
        done, _ = await asyncio.wait({task, asyncio.create_task(ended.wait())},
                                     return_when=asyncio.FIRST_COMPLETED)
        await self.close()
        if task in done and task.exception():
            raise task.exception()  # type: ignore[misc]

    async def close(self) -> None:
        if self.client is not None:
            client, self.client = self.client, None
            for step in (client.disconnect, client.web.close):
                try:
                    await step()
                except Exception:
                    pass


SourceFactory = Callable[[str], LiveSource]


@dataclass
class BotStatus:
    state: str = "inaktiv"  # inaktiv | wartet | verbinde | live | fehler
    message: str = "Bot ist ausgeschaltet"
    last_check: float = 0.0
    live_since: float = 0.0
    viewers: int = 0
    room_id: str = ""
    errors_in_row: int = 0

    def as_dict(self) -> dict:
        return dict(self.__dict__)


@dataclass
class Bot:
    streamer_id: int
    pipeline: Pipeline
    status: BotStatus = field(default_factory=BotStatus)
    task: asyncio.Task | None = None
    tiktok_user: str = ""


class BotManager:
    def __init__(self, settings: Settings, db: Database, hub: Hub, classifier: Classifier | None,
                 source_factory: SourceFactory | None = None, daily_budget_usd: float = 5.0):
        self.settings = settings
        self.db = db
        self.hub = hub
        self.classifier = classifier
        self.daily_budget_usd = daily_budget_usd
        self.source_factory: SourceFactory = source_factory or (
            lambda user: TikTokSource(user, settings.sign_api_key, settings.tiktok_proxy))
        self.bots: dict[int, Bot] = {}
        self.started_at = time.time()

    # -- Verwaltung ----------------------------------------------------------
    def bot(self, streamer_id: int) -> Bot:
        bot = self.bots.get(streamer_id)
        if bot is None:
            row = self.db.get_streamer(streamer_id) or {"settings": {}}
            pipeline = Pipeline(streamer_id, row["settings"], self.db, self.hub, self.classifier,
                                batch_seconds=self.settings.batch_seconds, batch_max=self.settings.batch_max,
                                price_in=self.settings.price_in, price_out=self.settings.price_out,
                                daily_budget_usd=self.daily_budget_usd)
            pipeline.start()
            bot = Bot(streamer_id, pipeline)
            self.bots[streamer_id] = bot
        return bot

    def status(self, streamer_id: int) -> dict:
        bot = self.bots.get(streamer_id)
        data = bot.status.as_dict() if bot else BotStatus().as_dict()
        if bot:
            data["stats"] = dict(bot.pipeline.stats)
            data["session_id"] = bot.pipeline.session_id
        return data

    async def sync(self, streamer_id: int) -> None:
        """Startet/stoppt den Wachdienst passend zu den gespeicherten Einstellungen."""
        row = self.db.get_streamer(streamer_id)
        bot = self.bot(streamer_id)
        if row:
            bot.pipeline.update_settings(row["settings"])
        should_run = bool(row and row["bot_active"] and row["setup_done"] and not row["disabled"]
                          and row["tiktok_user"] and self.settings.tiktok_enabled)
        user_changed = bool(row) and bot.tiktok_user != row["tiktok_user"]
        running = bot.task is not None and not bot.task.done()
        if running and (not should_run or user_changed):
            await self._stop_task(bot)
            running = False
        if should_run and not running:
            bot.tiktok_user = row["tiktok_user"]
            bot.status = BotStatus(state="wartet", message="Bot aktiv - wartet auf dein LIVE")
            bot.task = asyncio.create_task(self._watch(bot), name=f"watch-{streamer_id}")
        if not should_run:
            msg = "Bot ist ausgeschaltet"
            if row and row["bot_active"] and not self.settings.tiktok_enabled:
                msg = "TikTok-Anbindung serverseitig deaktiviert"
            bot.status = BotStatus(state="inaktiv", message=msg)

    async def sync_all(self) -> None:
        for row in self.db.list_streamers():
            await self.sync(row["id"])

    async def _stop_task(self, bot: Bot) -> None:
        if bot.task:
            bot.task.cancel()
            try:
                await bot.task
            except (asyncio.CancelledError, Exception):
                pass
            bot.task = None
        if bot.pipeline.session_id:
            self.db.end_session(bot.pipeline.session_id)
            bot.pipeline.new_session(None)

    async def shutdown(self) -> None:
        for bot in list(self.bots.values()):
            await self._stop_task(bot)
            await bot.pipeline.stop()

    # -- Wachschleife --------------------------------------------------------
    def _publish_status(self, bot: Bot) -> None:
        self.hub.publish(bot.streamer_id, {"type": "status", "status": self.status(bot.streamer_id)})

    async def _watch(self, bot: Bot) -> None:
        source = self.source_factory(bot.tiktok_user)
        poll = max(15, self.settings.live_poll_seconds)
        while True:
            bot.status.last_check = time.time()
            try:
                live = await source.is_live()
            except UserNotFound:
                bot.status.state, bot.status.message = "fehler", f"TikTok-Konto @{bot.tiktok_user} nicht gefunden"
                self.db.add_error(bot.streamer_id, "tiktok", bot.status.message)
                self._publish_status(bot)
                await asyncio.sleep(300)
                continue
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await self._on_error(bot, "Live-Status-Abfrage", exc)
                continue

            if not live:
                bot.status.state, bot.status.message = "wartet", "Bot aktiv - wartet auf dein LIVE"
                bot.status.errors_in_row = 0
                self._publish_status(bot)
                await asyncio.sleep(poll)
                continue

            bot.status.state, bot.status.message = "verbinde", "LIVE erkannt - verbinde mit dem Chat"
            self._publish_status(bot)
            session_id = self.db.start_session(bot.streamer_id, None)
            bot.pipeline.new_session(session_id)

            def _connected(room_id: str) -> None:
                bot.status.state, bot.status.message = "live", "Moderation läuft"
                bot.status.live_since, bot.status.room_id = time.time(), room_id
                bot.status.errors_in_row = 0
                self._publish_status(bot)

            def _viewers(n: int) -> None:
                bot.status.viewers = n

            try:
                await source.run(bot.pipeline.submit, _connected, _viewers)
                bot.status.state, bot.status.message = "wartet", "LIVE beendet - Bericht verfügbar"
                self._publish_status(bot)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await self._on_error(bot, "Chat-Verbindung", exc, sleep=False)
            finally:
                self.db.end_session(session_id)
                self.hub.publish(bot.streamer_id, {"type": "session_end", "session_id": session_id})
            await asyncio.sleep(10)

    async def _on_error(self, bot: Bot, where: str, exc: Exception, sleep: bool = True) -> None:
        bot.status.errors_in_row += 1
        name = type(exc).__name__
        text = str(exc)[:200] or name
        if "Signature" in name or "RateLimit" in name or "PremiumEndpoint" in name:
            hint = "Lese-Kontingent des Verbindungsdienstes erschöpft - neuer Versuch folgt"
        elif "Blocked" in name or "Captcha" in text:
            hint = "TikTok blockiert die Verbindung vorübergehend - neuer Versuch folgt"
        else:
            hint = "Verbindungsproblem - neuer Versuch folgt"
        bot.status.state, bot.status.message = "fehler", hint
        self.db.add_error(bot.streamer_id, "tiktok", f"{where}: {name}: {text}")
        self._publish_status(bot)
        delay = min(300, 15 * (2 ** min(bot.status.errors_in_row - 1, 4)))
        await asyncio.sleep(delay if sleep else min(delay, 60))
