import asyncio
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fmm_live.ai import BatchResult, Verdict  # noqa: E402
from fmm_live.config import Settings  # noqa: E402

ADMIN = "test-admin-token-1234567890"


def make_settings(tmp_path: Path, **over) -> Settings:
    base = dict(
        data_dir=tmp_path, admin_token=ADMIN, anthropic_api_key="", model="test-model", effort="low",
        sign_api_key="", public_url="https://mod.example", ai_enabled=True, tiktok_enabled=True,
        live_poll_seconds=15, retention_days=30, batch_seconds=0.2, batch_max=10,
        price_in=4.0, price_out=20.0,
    )
    base.update(over)
    return Settings(**base)


class FakeClassifier:
    """Simuliert die KI: 'idiot' -> ausblenden, '?' -> frage, 'boom' -> Fehler."""

    model = "fake-model"

    def __init__(self):
        self.calls = 0

    async def classify(self, comments, settings):
        self.calls += 1
        if any("boom" in c["text"] for c in comments):
            raise RuntimeError("KI down")
        out = BatchResult({}, input_tokens=1000, output_tokens=200, model=self.model)
        for c in comments:
            t = c["text"].lower()
            if "idiot" in t:
                out.verdicts[c["i"]] = Verdict("ausblenden", "beleidigung", "Beleidigung", "")
            elif "ritz" in t:
                out.verdicts[c["i"]] = Verdict("dringend", "selbstgefaehrdung", "Hinweis auf Selbstverletzung", "")
            elif t.endswith("?"):
                out.verdicts[c["i"]] = Verdict("frage", "", "Frage", "Gute Frage - bald!")
            else:
                out.verdicts[c["i"]] = Verdict("ok", "", "", "")
        return out


class FakeSource:
    def __init__(self, user, comments, live=True, not_found=False):
        self.user = user
        self.comments = comments
        self.live = live
        self.not_found = not_found
        self.runs = 0

    async def is_live(self):
        if self.not_found:
            from fmm_live.live import UserNotFound
            raise UserNotFound("nope")
        return self.live and self.runs == 0

    async def run(self, on_comment, on_connected, on_viewers):
        self.runs += 1
        on_connected("12345")
        on_viewers(42)
        for c in self.comments:
            await on_comment(c)
        await asyncio.sleep(1.0)  # KI-Stapel abarbeiten lassen

    async def close(self):
        pass


def token_from_link(link: str) -> str:
    return re.search(r"#t=(.+)$", link).group(1)


@pytest.fixture
def fake_classifier():
    return FakeClassifier()
