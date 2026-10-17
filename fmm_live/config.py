"""Konfiguration ausschliesslich ueber Umgebungsvariablen (Secrets nie im Code/Repo)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    """Minimaler .env-Leser fuer lokale Entwicklung. Echte Umgebung hat Vorrang."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "ja", "yes", "on"}


@dataclass
class Settings:
    data_dir: Path
    admin_token: str
    anthropic_api_key: str
    model: str
    effort: str
    sign_api_key: str
    public_url: str
    ai_enabled: bool
    tiktok_enabled: bool
    live_poll_seconds: int
    retention_days: int
    batch_seconds: float
    batch_max: int
    # Preise je 1 Mio. Tokens in USD (Eingabe, Ausgabe) fuer die Kostenzuordnung.
    price_in: float
    price_out: float
    daily_budget_usd: float = 5.0
    tiktok_proxy: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "moderator.sqlite3"


# Bekannte Listenpreise (USD / 1 Mio. Tokens, Stand 10/2026). Unbekannte Modelle: Opus-Preis.
_PRICES = {
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
}


def load_settings() -> Settings:
    _load_dotenv(Path.cwd() / ".env")
    model = os.environ.get("LM_MODEL", "claude-opus-5-5").strip() or "claude-opus-5-5"
    p_in, p_out = _PRICES.get(model, (4.0, 20.0))
    data_dir = Path(os.environ.get("DATA_DIR", "./data")).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        data_dir=data_dir,
        admin_token=os.environ.get("ADMIN_TOKEN", "").strip(),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "").strip(),
        model=model,
        effort=os.environ.get("LM_EFFORT", "low").strip() or "low",
        sign_api_key=os.environ.get("SIGN_API_KEY", "").strip(),
        public_url=os.environ.get("PUBLIC_URL", "http://localhost:8000").rstrip("/"),
        ai_enabled=_bool("AI_ENABLED", True),
        tiktok_enabled=_bool("TIKTOK_ENABLED", True),
        live_poll_seconds=int(os.environ.get("LIVE_POLL_SECONDS", "60")),
        retention_days=int(os.environ.get("RETENTION_DAYS", "30")),
        batch_seconds=float(os.environ.get("BATCH_SECONDS", "2.5")),
        batch_max=int(os.environ.get("BATCH_MAX", "20")),
        price_in=float(os.environ.get("PRICE_IN_PER_MTOK", p_in)),
        price_out=float(os.environ.get("PRICE_OUT_PER_MTOK", p_out)),
        daily_budget_usd=float(os.environ.get("AI_DAILY_BUDGET_USD", "5")),
        tiktok_proxy=os.environ.get("TIKTOK_PROXY", "").strip(),
    )
