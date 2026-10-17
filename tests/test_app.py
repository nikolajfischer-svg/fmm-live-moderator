import time

import pytest
from fastapi.testclient import TestClient

from fmm_live.web import create_app

from .conftest import ADMIN, FakeSource, make_settings, token_from_link

H_ADMIN = {"Authorization": f"Bearer {ADMIN}"}


def auth(t):
    return {"Authorization": f"Bearer {t}"}


def new_streamer(client, name="Lena"):
    r = client.post("/api/admin/streamers", json={"name": name}, headers=H_ADMIN)
    assert r.status_code == 200, r.text
    assert r.json()["link"].startswith("https://mod.example/app#t=")
    return token_from_link(r.json()["link"])


def wait_for(fn, timeout=8.0):
    end = time.time() + timeout
    while time.time() < end:
        v = fn()
        if v:
            return v
        time.sleep(0.1)
    raise AssertionError("Bedingung nicht erfüllt")


COMMENTS = [
    {"text": "Hallo zusammen", "viewer_id": "1", "viewer_name": "Anna", "viewer_handle": "anna"},
    {"text": "du idiot", "viewer_id": "2", "viewer_name": "Troll", "viewer_handle": "troll"},
    {"text": "wann kommt das nächste live?", "viewer_id": "3", "viewer_name": "Ben", "viewer_handle": "ben"},
    {"text": "folgt mir www.spam.de", "viewer_id": "4", "viewer_name": "Bot", "viewer_handle": "spambot"},
    {"text": "du idiot nochmal", "viewer_id": "2", "viewer_name": "Troll", "viewer_handle": "troll"},
    {"text": "ich ritz mich heute wieder", "viewer_id": "5", "viewer_name": "Kim", "viewer_handle": "kim"},
]


@pytest.fixture
def setup(tmp_path, fake_classifier):
    sources = {}

    def factory(user):
        src = sources.get(user) or FakeSource(user, COMMENTS)
        sources[user] = src
        return src

    app = create_app(make_settings(tmp_path), source_factory=factory, classifier=fake_classifier)
    with TestClient(app) as client:
        yield client, sources, fake_classifier


def test_health(setup):
    client, *_ = setup
    assert client.get("/healthz").json()["ok"] is True
    assert client.get("/app").status_code == 200
    assert client.get("/admin").status_code == 200
    assert client.get("/anleitung").status_code == 200
    assert client.get("/datenschutz").status_code == 200
    assert client.get("/static/icon-180.png").status_code == 200


def test_admin_requires_token(setup):
    client, *_ = setup
    assert client.get("/api/admin/overview").status_code == 401
    assert client.get("/api/admin/overview", headers=auth("falsch")).status_code == 401
    assert client.post("/api/admin/streamers", json={"name": "x"}).status_code == 401


def test_invalid_streamer_token(setup):
    client, *_ = setup
    assert client.get("/api/me", headers=auth("gibtsnicht")).status_code == 401


def test_full_pilot_flow(setup):
    client, sources, classifier = setup
    t = new_streamer(client)
    me = client.get("/api/me", headers=auth(t)).json()
    assert me["role"] == "streamer" and not me["streamer"]["setup_done"]
    assert len(me["keyword_filter"]) > 10

    # Schritt 1: Benutzername (auch als URL eingegeben)
    r = client.put("/api/profile", json={"tiktok_user": "https://www.tiktok.com/@Lena.Live/live"}, headers=auth(t))
    assert r.json()["tiktok_user"] == "lena.live"
    assert client.put("/api/profile", json={"tiktok_user": "böse<script>"}, headers=auth(t)).status_code == 400

    # Schritt 3/4: Regeln + KI
    s = me["settings"]
    s["preset"] = "familienfreundlich"
    s["blocked_words"] = ["Hater123", "hater123", " "]
    s["ai"]["house_rules"] = "Keine Wohnortfragen"
    r = client.put("/api/settings", json=s, headers=auth(t)).json()
    assert r["settings"]["blocked_words"] == ["hater123"] and "hater123" in r["keyword_filter"]

    # Schritt 5: Verbindungstest + Testnachricht
    r = client.post("/api/test-connection", headers=auth(t)).json()
    assert r["ok"] and r["found"] and r["live"] is True
    sources["lena.live"].runs = 0
    ev = client.post("/api/test-message", json={"text": "Bist du aus Berlin?"}, headers=auth(t)).json()["event"]
    assert ev["decision"] == "frage" and ev["is_test"] and ev["suggestion"]
    ev = client.post("/api/test-message", json={"text": "hater123 ist da"}, headers=auth(t)).json()["event"]
    assert ev["decision"] == "ausblenden" and ev["source"] == "regel"

    # Schritt 6: Aktivieren -> Fake-LIVE laeuft -> Kommentare werden moderiert
    assert client.post("/api/setup-complete", headers=auth(t)).json()["ok"]
    events = wait_for(lambda: [e for e in client.get("/api/events", headers=auth(t)).json()["events"]
                               if not e["is_test"]] if len(client.get("/api/events", headers=auth(t)).json()["events"]) >= 8 else None)
    by_text = {e["text"]: e for e in events}
    assert by_text["Hallo zusammen"]["decision"] == "ok"
    assert by_text["du idiot"]["decision"] == "ausblenden"
    assert by_text["du idiot nochmal"]["decision"] == "stummschalten"  # Wiederholungstäter
    assert by_text["wann kommt das nächste live?"]["decision"] == "frage"
    assert by_text["folgt mir www.spam.de"]["decision"] == "ausblenden"
    assert by_text["folgt mir www.spam.de"]["source"] == "regel"
    assert by_text["ich ritz mich heute wieder"]["decision"] == "dringend"

    sessions = wait_for(lambda: [x for x in client.get("/api/sessions", headers=auth(t)).json()["sessions"] if x["ended_at"]])
    rep = client.get(f"/api/sessions/{sessions[0]['id']}/report", headers=auth(t)).json()
    assert rep["total"] == 6 and rep["decisions"]["dringend"] == 1
    assert rep["top_offenders"][0][0] == "troll"

    # Erledigt markieren
    eid = by_text["du idiot"]["id"]
    assert client.post(f"/api/events/{eid}/handled", headers=auth(t)).json()["ok"]

    # Admin sieht Status, Kosten und Version
    ov = client.get("/api/admin/overview", headers=H_ADMIN).json()
    row = ov["streamers"][0]
    assert row["tiktok_user"] == "lena.live" and row["bot_active"] and row["version"]
    assert row["usage_30d"]["cost_usd"] > 0  # Kosten werden dem Streamer zugeordnet


def test_tenant_isolation_and_mod_role(setup):
    client, *_ = setup
    ta, tb = new_streamer(client, "A"), new_streamer(client, "B")
    client.put("/api/profile", json={"tiktok_user": "streamer_a"}, headers=auth(ta))
    ev = client.post("/api/test-message", json={"text": "du idiot"}, headers=auth(ta)).json()["event"]
    # B sieht keine Daten von A und kann A's Ereignisse nicht verändern
    assert client.get("/api/events", headers=auth(tb)).json()["events"] == []
    assert client.post(f"/api/events/{ev['id']}/handled", headers=auth(tb)).status_code == 404
    # Moderator-Link: lesen ja, Einstellungen nein
    link = client.post("/api/mod-link", headers=auth(ta)).json()["link"]
    tm = link.split("#m=")[1]
    me = client.get("/api/me", headers=auth(tm)).json()
    assert me["role"] == "mod" and me["settings"] is None
    assert len(client.get("/api/events", headers=auth(tm)).json()["events"]) == 1
    assert client.put("/api/settings", json={}, headers=auth(tm)).status_code == 403
    assert client.post("/api/bot", json={"active": False}, headers=auth(tm)).status_code == 403
    # Link erneuern macht alten ungültig
    old = ta
    new = token_from_link(client.post("/api/admin/streamers/1/rotate", headers=H_ADMIN).json()["link"])
    assert client.get("/api/me", headers=auth(old)).status_code == 401
    assert client.get("/api/me", headers=auth(new)).status_code == 200
    # Sperren + Löschen
    client.post("/api/admin/streamers/2/disable", headers=H_ADMIN)
    assert client.get("/api/me", headers=auth(tb)).status_code == 401
    assert client.delete("/api/admin/streamers/1", headers=H_ADMIN).json()["ok"]
    assert client.get("/api/me", headers=auth(new)).status_code == 401
    assert client.get("/api/admin/overview", headers=H_ADMIN).json()["streamers"][0]["name"] == "B"


def test_ai_failure_falls_back_to_rules(setup):
    client, *_ = setup
    t = new_streamer(client)
    ev = client.post("/api/test-message", json={"text": "boom kaputt?"}, headers=auth(t)).json()["event"]
    assert ev["decision"] == "frage" and "KI nicht erreichbar" in ev["reason"]
    errs = client.get("/api/admin/overview", headers=H_ADMIN).json()["errors"]
    assert any("KI down" in e["message"] for e in errs)


def test_unknown_tiktok_user(tmp_path, fake_classifier):
    app = create_app(make_settings(tmp_path), source_factory=lambda u: FakeSource(u, [], not_found=True),
                     classifier=fake_classifier)
    with TestClient(app) as client:
        t = new_streamer(client)
        client.put("/api/profile", json={"tiktok_user": "gibtsnicht"}, headers=auth(t))
        r = client.post("/api/test-connection", headers=auth(t)).json()
        assert r["ok"] is False and r["found"] is False


def test_daily_budget_stops_ai(tmp_path, fake_classifier):
    app = create_app(make_settings(tmp_path), source_factory=lambda u: FakeSource(u, []), classifier=fake_classifier)
    with TestClient(app) as client:
        t = new_streamer(client)
        client.post("/api/test-message", json={"text": "hallo"}, headers=auth(t))  # legt Bot im Server-Loop an
        app.state.manager.bots[1].pipeline.daily_budget_usd = 0.001
        app.state.db.add_usage(1, "fake", 1000, 1000, 1.0)
        calls = fake_classifier.calls
        ev = client.post("/api/test-message", json={"text": "du idiot"}, headers=auth(t)).json()["event"]
        assert fake_classifier.calls == calls and ev["source"] == "regel"
        assert any("Tagesbudget" in e["message"] for e in app.state.db.errors())


def test_settings_survive_restart(tmp_path, fake_classifier):
    st = make_settings(tmp_path)
    app = create_app(st, source_factory=lambda u: FakeSource(u, [], live=False), classifier=fake_classifier)
    with TestClient(app) as client:
        t = new_streamer(client)
        client.put("/api/profile", json={"tiktok_user": "lena"}, headers=auth(t))
        client.post("/api/setup-complete", headers=auth(t))
        assert wait_for(lambda: client.get("/api/me", headers=auth(t)).json()["status"]["state"] == "wartet")
    app2 = create_app(st, source_factory=lambda u: FakeSource(u, [], live=False), classifier=fake_classifier)
    with TestClient(app2) as client:
        me = client.get("/api/me", headers=auth(t)).json()
        assert me["streamer"]["setup_done"] and me["streamer"]["bot_active"]
        assert wait_for(lambda: client.get("/api/me", headers=auth(t)).json()["status"]["state"] == "wartet")


def test_security_headers_and_privacy_page(tmp_path, fake_classifier):
    app = create_app(make_settings(tmp_path, operator_email="info@example.de", operator_address="Musterweg 1"),
                     source_factory=lambda u: FakeSource(u, []), classifier=fake_classifier)
    with TestClient(app) as client:
        r = client.get("/app")
        assert "script-src 'self'" in r.headers["content-security-policy"]
        assert r.headers["x-frame-options"] == "DENY"
        page = client.get("/datenschutz").text
        assert "Musterweg 1, info@example.de" in page and "{{" not in page


def test_admin_diagnose(setup):
    client, *_ = setup
    assert client.post("/api/admin/diagnose", json={"tiktok_user": "irgendwer"}).status_code == 401
    r = client.post("/api/admin/diagnose", json={"tiktok_user": "@irgendwer", "seconds": 5}, headers=H_ADMIN).json()
    assert r["live"] is True and r["connected_after_s"] is not None and r["comments"] == len(COMMENTS)
    assert r["error"] is None


def test_watchdog_restarts_crashed_bot(tmp_path, fake_classifier):
    class Crash(BaseException):
        pass

    class CrashSource(FakeSource):
        async def is_live(self):
            raise Crash("unerwarteter Absturz")  # nicht abgefangen -> Wachdienst endet

    app = create_app(make_settings(tmp_path), source_factory=lambda u: CrashSource(u, []), classifier=fake_classifier)
    with TestClient(app) as client:
        t = new_streamer(client)
        client.put("/api/profile", json={"tiktok_user": "lena"}, headers=auth(t))
        client.post("/api/setup-complete", headers=auth(t))
        bot = app.state.manager.bots[1]
        wait_for(lambda: bot.task is not None and bot.task.done())
        app.state.manager.source_factory = lambda u: FakeSource(u, [], live=False)
        client.post("/api/bot", json={"active": True}, headers=auth(t))  # sync() wie der Wachhund
        assert wait_for(lambda: client.get("/api/me", headers=auth(t)).json()["status"]["state"] == "wartet")


def test_injection_is_isolated_and_rate_limits(setup):
    client, _sources, classifier = setup
    t = new_streamer(client)
    pipe_calls = classifier.calls
    for i in range(10):
        assert client.post("/api/test-message", json={"text": f"hallo {i}"}, headers=auth(t)).status_code == 200
    assert client.post("/api/test-message", json={"text": "zu viel"}, headers=auth(t)).status_code == 429
    assert classifier.calls > pipe_calls
    assert client.post("/api/settings", content=b"x" * 70000, headers={**auth(t), "Content-Type": "application/json"}).status_code == 413
    assert client.get("/api/events?limit=-1", headers=auth(t)).status_code == 422


def test_admin_only_via_header(setup):
    client, *_ = setup
    assert client.get(f"/api/admin/overview?t={ADMIN}").status_code == 401
    assert client.get("/api/admin/overview", headers=H_ADMIN).status_code == 200


def test_mod_does_not_get_keywords_or_touch_last_seen(setup):
    client, *_ = setup
    t = new_streamer(client)
    tm = client.post("/api/mod-link", headers=auth(t)).json()["link"].split("#m=")[1]
    me = client.get("/api/me", headers=auth(tm)).json()
    assert me["keyword_filter"] == []
