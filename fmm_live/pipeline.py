"""Moderations-Pipeline je Streamer: Regeln -> KI-Stapel -> Speichern -> Live-Push."""
from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict

from .ai import Classifier, Verdict
from .db import Database
from .rules import RANK, RuleEngine, RuleResult, looks_like_injection, merged_settings, simple_question

log = logging.getLogger("fmm_live.pipeline")


class Hub:
    """Verteilt Live-Ereignisse an verbundene Browser (Server-Sent Events), getrennt je Streamer."""

    def __init__(self) -> None:
        self._subs: dict[int, set[asyncio.Queue]] = defaultdict(set)

    def subscribe(self, streamer_id: int) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._subs[streamer_id].add(q)
        return q

    def unsubscribe(self, streamer_id: int, q: asyncio.Queue) -> None:
        self._subs[streamer_id].discard(q)

    def publish(self, streamer_id: int, payload: dict) -> None:
        for q in list(self._subs.get(streamer_id, ())):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass  # langsamer Client: Ereignis verwerfen statt Server blockieren

    def subscriber_count(self, streamer_id: int) -> int:
        return len(self._subs.get(streamer_id, ()))


class Pipeline:
    def __init__(self, streamer_id: int, settings: dict, db: Database, hub: Hub,
                 classifier: Classifier | None, *, batch_seconds: float = 2.5, batch_max: int = 20,
                 price_in: float = 4.0, price_out: float = 20.0, daily_budget_usd: float = 5.0):
        self.streamer_id = streamer_id
        self.db = db
        self.hub = hub
        self.classifier = classifier
        self.batch_seconds = batch_seconds
        self.batch_max = batch_max
        self.price_in = price_in
        self.price_out = price_out
        self.daily_budget_usd = daily_budget_usd
        self.settings = merged_settings(settings)
        self.rules = RuleEngine(self.settings)
        self.session_id: int | None = None
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=2000)
        self._worker: asyncio.Task | None = None
        self.stats = {"comments": 0, "flagged": 0, "ai_calls": 0, "ai_errors": 0}
        self._budget_warned = False
        self._urgent_seen: dict[str, float] = {}

    # -- Lebenszyklus --------------------------------------------------------
    def start(self) -> None:
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._batch_loop(), name=f"pipeline-{self.streamer_id}")

    async def stop(self) -> None:
        if self._worker:
            self._worker.cancel()
            try:
                await self._worker
            except (asyncio.CancelledError, Exception):
                pass
            self._worker = None

    def update_settings(self, settings: dict) -> None:
        self.settings = merged_settings(settings)
        self.rules.update_settings(self.settings)

    def new_session(self, session_id: int | None) -> None:
        self.session_id = session_id
        self.rules = RuleEngine(self.settings)  # Verwarnungen gelten je Live
        self.stats = {"comments": 0, "flagged": 0, "ai_calls": 0, "ai_errors": 0}

    # -- Eingang -------------------------------------------------------------
    def _ai_active(self) -> bool:
        return self.classifier is not None and bool(self.settings["ai"].get("enabled", True))

    def _budget_ok(self) -> bool:
        if self.daily_budget_usd <= 0:
            return True
        rows = self.db.usage_summary(self.streamer_id, since=time.time() - 86400)
        spent = rows[0]["cost_usd"] if rows and rows[0]["cost_usd"] else 0.0
        if spent >= self.daily_budget_usd:
            if not self._budget_warned:
                self._budget_warned = True
                self.db.add_error(self.streamer_id, "kosten",
                                  f"Tagesbudget {self.daily_budget_usd:.2f} USD erreicht - nur noch Regelprüfung")
            return False
        self._budget_warned = False
        return True

    async def submit(self, comment: dict) -> None:
        """comment: text, viewer_id, viewer_name, viewer_handle, [is_test]"""
        text = (comment.get("text") or "").strip()
        if not text:
            return
        comment = {**comment, "text": text, "ts": comment.get("ts") or time.time()}
        key = comment.get("viewer_id") or comment.get("viewer_handle") or comment.get("viewer_name") or "?"
        rule = self.rules.check(str(key), comment.get("viewer_handle", ""), text, now=comment["ts"])
        if rule and rule.final:
            await self._finalize(comment, rule.decision, rule.category, rule.reason, "regel", "")
            return
        if self._ai_active() and self._budget_ok():
            try:
                self._queue.put_nowait((comment, rule))
                return
            except asyncio.QueueFull:
                self.db.add_error(self.streamer_id, "ki", "Warteschlange voll - Kommentar nur per Regel geprüft")
        await self._finalize_without_ai(comment, rule)

    async def _finalize_without_ai(self, comment: dict, rule: RuleResult | None, note: str = "") -> None:
        if rule:
            await self._finalize(comment, rule.decision, rule.category, rule.reason, "regel", "")
        elif self.settings["ai"].get("questions", True) and simple_question(comment["text"]):
            await self._finalize(comment, "frage", "", "Frage an den Streamer" + note, "regel", "")
        else:
            await self._finalize(comment, "ok", "", note.strip(" ()"), "regel", "")

    # -- KI-Stapel -----------------------------------------------------------
    async def _batch_loop(self) -> None:
        while True:
            first = await self._queue.get()
            batch = [first]
            deadline = asyncio.get_running_loop().time() + self.batch_seconds
            while len(batch) < self.batch_max:
                timeout = deadline - asyncio.get_running_loop().time()
                if timeout <= 0:
                    break
                try:
                    batch.append(await asyncio.wait_for(self._queue.get(), timeout))
                except asyncio.TimeoutError:
                    break
            await self._process_batch(batch)

    async def _process_batch(self, batch: list[tuple[dict, RuleResult | None]]) -> None:
        # Kommentare, die die KI ansprechen ("ignoriere deine Regeln ..."), werden einzeln geprueft,
        # damit sie die Bewertung anderer Kommentare im selben Stapel nicht beeinflussen koennen.
        suspicious = [b for b in batch if looks_like_injection(b[0]["text"]) or looks_like_injection(b[0].get("viewer_name", ""))]
        if suspicious and len(batch) > 1:
            clean = [b for b in batch if b not in suspicious]
            if clean:
                await self._process_batch(clean)
            for item in suspicious:
                await self._process_batch([item])
            return
        items = [{"i": idx, "text": c["text"], "viewer_name": c.get("viewer_name", "")}
                 for idx, (c, _) in enumerate(batch)]
        try:
            result = await self.classifier.classify(items, self.settings)  # type: ignore[union-attr]
            self.stats["ai_calls"] += 1
            if result.input_tokens or result.output_tokens:
                cost = (result.input_tokens * self.price_in + result.output_tokens * self.price_out) / 1_000_000
                self.db.add_usage(self.streamer_id, result.model, result.input_tokens, result.output_tokens, cost)
        except Exception as exc:  # KI-Ausfall darf die Moderation nie stoppen
            self.stats["ai_errors"] += 1
            log.warning("KI-Fehler: %s", exc)
            self.db.add_error(self.streamer_id, "ki", f"{type(exc).__name__}: {exc}")
            for comment, rule in batch:
                await self._finalize_without_ai(comment, rule, " (KI nicht erreichbar)")
            return

        for idx, (comment, rule) in enumerate(batch):
            verdict = result.verdicts.get(idx) or Verdict("beobachten", "", "Keine KI-Antwort erhalten", "")
            decision, category, reason, source = verdict.decision, verdict.category, verdict.reason, "ki"
            if rule and RANK[rule.decision] > RANK.get(decision, 0):
                decision, category, reason, source = rule.decision, rule.category, rule.reason, "regel"
            suggestion = verdict.suggestion if (decision == "frage"
                                                and self.settings["ai"].get("reply_suggestions", True)) else ""
            await self._finalize(comment, decision, category, reason, source, suggestion)

    # -- Ausgang -------------------------------------------------------------
    async def _finalize(self, comment: dict, decision: str, category: str, reason: str,
                        source: str, suggestion: str) -> None:
        key = str(comment.get("viewer_id") or comment.get("viewer_handle") or comment.get("viewer_name") or "?")
        strikes = 0
        if not comment.get("is_test"):
            escalated, strikes = self.rules.apply_strikes(key, decision)
            if escalated != decision:
                reason = f"{reason} (Wiederholungstäter, {strikes}. Verstoß)".strip()
                decision = escalated
        if decision == "dringend" and not comment.get("is_test"):
            last = self._urgent_seen.get(key, 0.0)
            if comment["ts"] - last < 300:
                decision, reason = "beobachten", f"{reason} (weiterer dringender Hinweis desselben Zuschauers)".strip()
            else:
                self._urgent_seen[key] = comment["ts"]
        flagged = decision not in ("ok", "frage")
        ev = {
            "session_id": None if comment.get("is_test") else self.session_id,
            "ts": comment["ts"],
            "viewer_id": str(comment.get("viewer_id", "")),
            "viewer_name": comment.get("viewer_name", ""),
            "viewer_handle": comment.get("viewer_handle", ""),
            "text": comment["text"],
            "decision": decision,
            "category": category or "",
            "reason": reason or "",
            "source": source,
            "suggestion": suggestion or "",
            "is_test": bool(comment.get("is_test")),
        }
        ev["id"] = self.db.add_event(self.streamer_id, ev)
        ev["strikes"] = strikes
        if not comment.get("is_test"):
            self.stats["comments"] += 1
            self.stats["flagged"] += 1 if flagged else 0
            if self.session_id:
                self.db.bump_session(self.session_id, flagged)
        self.hub.publish(self.streamer_id, {"type": "event", "event": ev, "stats": dict(self.stats)})
        future = comment.get("_future")
        if future is not None and not future.done():
            future.set_result(ev)

    async def drain(self, timeout: float = 10.0) -> None:
        """Fuer Tests: wartet, bis die KI-Warteschlange leer ist."""
        end = time.time() + timeout
        while (not self._queue.empty()) and time.time() < end:
            await asyncio.sleep(0.05)
        await asyncio.sleep(self.batch_seconds + 0.2)
