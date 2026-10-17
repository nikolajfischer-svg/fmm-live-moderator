"""Regel-Engine: schnelle, kostenlose Vorpruefung jedes Kommentars vor der KI.

Entscheidungen sind immer EMPFEHLUNGEN fuer Streamer/Moderator - die Software fuehrt
keine TikTok-Aktionen aus (keine offizielle, zulaessige Schnittstelle vorhanden).
"""
from __future__ import annotations

import copy
import re
import time
import unicodedata
from collections import defaultdict, deque
from dataclasses import dataclass, field

# Rangfolge der Entscheidungen (hoeher = schwerer)
DECISIONS = ["ok", "frage", "beobachten", "ausblenden", "stummschalten", "blockieren", "dringend"]
RANK = {d: i for i, d in enumerate(DECISIONS)}

CATEGORIES = {
    "beleidigung": "Beleidigung / Mobbing",
    "hass": "Hass / Diskriminierung",
    "sexuell": "Sexuelle Inhalte / Belästigung",
    "bedrohung": "Drohung / Gewalt",
    "spam": "Spam / Werbung / Links",
    "persoenliche_daten": "Persönliche Daten (Telefon, Adresse, E-Mail)",
    "selbstgefaehrdung": "Hinweis auf Selbstgefährdung (Hilfe nötig)",
}

PRESETS = {
    "familienfreundlich": {
        "label": "Familienfreundlich (streng)",
        "flood_msgs": 4, "caps_decision": "ausblenden",
        "ai_strictness": "streng: auch milde Beleidigungen, anzügliche Andeutungen und Provokationen ausblenden",
    },
    "standard": {
        "label": "Standard (empfohlen)",
        "flood_msgs": 6, "caps_decision": "beobachten",
        "ai_strictness": "ausgewogen: klare Verstöße ausblenden, harmlose Frotzeleien und Umgangssprache erlauben",
    },
    "locker": {
        "label": "Locker (nur grobe Verstöße)",
        "flood_msgs": 10, "caps_decision": "ok",
        "ai_strictness": "locker: nur eindeutige Beleidigungen, Hass, Drohungen, Spam und Belästigung melden",
    },
}

# Grundliste fuer das TikTok-Schlüsselwortfilter und die Regelpruefung (erweiterbar je Streamer).
BASE_BLOCKLIST = [
    "hurensohn", "huso", "wichser", "fotze", "missgeburt", "spast", "schlampe", "nutte",
    "bastard", "arschloch", "fick dich", "fickdich", "verpiss dich", "hdf", "kys",
    "kill yourself", "bring dich um", "häng dich auf", "neger", "nigger", "kanake",
    "zigeuner", "schwuchtel", "transe", "judensau", "sieg heil", "heil hitler",
]

DEFAULT_SETTINGS = {
    "preset": "standard",
    "categories": {key: True for key in CATEGORIES},
    "blocked_words": [],
    "use_base_list": True,
    "allowed_users": [],
    "block_links": True,
    "ai": {
        "enabled": True,
        "questions": True,
        "reply_suggestions": True,
        "house_rules": "",
    },
}

LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s", "€": "e"})
LINK_RE = re.compile(
    r"(https?://|www\.|\b[a-z0-9-]{2,}\s?(\.|\(dot\)|punkt)\s?(com|de|net|org|io|ly|me|gg|tv|shop|link|ru|xyz)\b"
    r"|t\.me/|wa\.me/|onlyfans|0nlyfans|insta\s*:|snap\s*:|telegram\s*:)",
    re.IGNORECASE,
)
PHONE_RE = re.compile(r"(\+|00)?\d[\d\s\-/]{7,}\d")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]{2,}")


def merged_settings(raw: dict | None) -> dict:
    """Fuellt fehlende Schluessel mit Standardwerten auf (vorwaertskompatibel)."""
    out = copy.deepcopy(DEFAULT_SETTINGS)
    raw = raw or {}
    for key, value in raw.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key].update(value)
        else:
            out[key] = value
    if out.get("preset") not in PRESETS:
        out["preset"] = "standard"
    return out


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower().translate(LEET)
    text = re.sub(r"(.)\1{2,}", r"\1\1", text)  # "duuuuu" -> "duu"
    return text


def compact(text: str) -> str:
    return re.sub(r"[^a-zäöüß0-9]", "", text)


def effective_blocklist(settings: dict) -> list[str]:
    words = list(BASE_BLOCKLIST) if settings.get("use_base_list", True) else []
    words += [w for w in settings.get("blocked_words", []) if isinstance(w, str)]
    seen, out = set(), []
    for w in words:
        w = w.strip().lower()
        if w and w not in seen:
            seen.add(w)
            out.append(w)
    return out


def keyword_filter_export(settings: dict, limit: int = 200) -> list[str]:
    """Liste fuer TikToks eingebauten LIVE-Schlüsselwortfilter (max. 200 Begriffe laut TikTok)."""
    return effective_blocklist(settings)[:limit]


@dataclass
class RuleResult:
    decision: str
    category: str
    reason: str
    final: bool  # True = Regel ist eindeutig, KI wird nicht gefragt


@dataclass
class ViewerState:
    times: deque = field(default_factory=lambda: deque(maxlen=30))
    texts: deque = field(default_factory=lambda: deque(maxlen=10))
    strikes: int = 0


class RuleEngine:
    """Zustandsbehaftet je Live-Session (Flut, Wiederholungen, Verwarnungen)."""

    def __init__(self, settings: dict):
        self.update_settings(settings)
        self.viewers: dict[str, ViewerState] = defaultdict(ViewerState)

    def update_settings(self, settings: dict) -> None:
        self.settings = merged_settings(settings)
        self.preset = PRESETS[self.settings["preset"]]
        self._short_terms: list[re.Pattern] = []
        self._long_terms: list[str] = []
        for term in effective_blocklist(self.settings):
            norm = normalize(term)
            if len(compact(norm)) >= 5:
                self._long_terms.append(compact(norm))
            else:
                self._short_terms.append(re.compile(rf"(?<![a-zäöüß0-9]){re.escape(norm)}(?![a-zäöüß0-9])"))
        self.allowed = {u.strip().lstrip("@").lower() for u in self.settings.get("allowed_users", []) if u}

    def _cat_on(self, cat: str) -> bool:
        return bool(self.settings["categories"].get(cat, True))

    def check(self, viewer_key: str, handle: str, text: str, now: float | None = None) -> RuleResult | None:
        now = now or time.time()
        if handle and handle.lower().lstrip("@") in self.allowed:
            return RuleResult("ok", "", "Vertrauenswürdiger Zuschauer (Ausnahmeliste)", True)

        state = self.viewers[viewer_key]
        norm = normalize(text)
        comp = compact(norm)
        state.times.append(now)
        repeated = sum(1 for t, s in state.texts if s == comp and now - t < 60)
        state.texts.append((now, comp))

        # 1) Sperrwoerter
        if self._cat_on("beleidigung") or self._cat_on("hass"):
            for term in self._long_terms:
                if term and term in comp:
                    return RuleResult("ausblenden", "beleidigung", "Sperrwort erkannt", True)
            for pat in self._short_terms:
                if pat.search(norm):
                    return RuleResult("ausblenden", "beleidigung", "Sperrwort erkannt", True)

        # 2) Persoenliche Daten
        if self._cat_on("persoenliche_daten"):
            if EMAIL_RE.search(text):
                return RuleResult("ausblenden", "persoenliche_daten", "E-Mail-Adresse im Chat", True)
            if PHONE_RE.search(text) and sum(c.isdigit() for c in text) >= 8:
                return RuleResult("ausblenden", "persoenliche_daten", "Telefonnummer im Chat", True)

        # 3) Links / Werbung
        if self._cat_on("spam") and self.settings.get("block_links", True) and LINK_RE.search(text):
            return RuleResult("ausblenden", "spam", "Link oder Werbung", True)

        # 4) Flut / Wiederholung
        if self._cat_on("spam"):
            recent = sum(1 for t in state.times if now - t < 20)
            # Wiederholte Fragen sind auf TikTok normal (Zuschauer wollen gesehen werden) -> erst ab 5x ausblenden
            if repeated >= 4:
                return RuleResult("ausblenden", "spam", "Gleiche Nachricht ständig wiederholt", True)
            if repeated >= 2 and not simple_question(text):
                return RuleResult("beobachten", "spam", "Gleiche Nachricht mehrfach wiederholt", False)
            if recent > self.preset["flood_msgs"]:
                return RuleResult("beobachten", "spam", f"Chat-Flut: {recent} Nachrichten in 20 s", True)

        # 5) Grossbuchstaben-Geschrei
        letters = [c for c in text if c.isalpha()]
        if len(letters) >= 12 and sum(c.isupper() for c in letters) / len(letters) > 0.7:
            decision = self.preset["caps_decision"]
            if decision != "ok":
                return RuleResult(decision, "spam", "Nur Großbuchstaben (Schreien)", False)

        return None

    def apply_strikes(self, viewer_key: str, decision: str) -> tuple[str, int]:
        """Wiederholungstaeter eskalieren: 2 Verstoesse -> Stummschalten, 4 -> Blockieren (Empfehlung)."""
        state = self.viewers[viewer_key]
        if RANK.get(decision, 0) >= RANK["ausblenden"] and decision != "dringend":
            state.strikes += 1
            if state.strikes >= 4 and RANK[decision] < RANK["blockieren"]:
                decision = "blockieren"
            elif state.strikes >= 2 and RANK[decision] < RANK["stummschalten"]:
                decision = "stummschalten"
        return decision, state.strikes


INJECTION_RE = re.compile(
    r"(ignorier|vergiss|missacht|überschreib|ueberschreib|ignore|disregard|forget).{0,40}"
    r"(regel|anweisung|instruktion|prompt|vorgabe|rule|instruction|system)"
    r"|(markier|bewert|stuf|klassifizier|mark|label|rate).{0,40}(alle|alles|jeden|all|every).{0,30}(ok|okay|harmlos|safe|dringend)"
    r"|\b(system ?prompt|you are now|du bist jetzt|als ki|as an ai|json|\{\s*\")",
    re.IGNORECASE)


def looks_like_injection(text: str) -> bool:
    return bool(text) and bool(INJECTION_RE.search(text))


def simple_question(text: str) -> bool:
    t = text.strip().lower()
    return t.endswith("?") or bool(re.match(r"^(wie|was|wann|wo|warum|wieso|weshalb|welche[rsnm]?|kannst|bist|hast|machst|wirst)\b", t))
