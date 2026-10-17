from fmm_live.rules import RuleEngine, keyword_filter_export, merged_settings, simple_question


def engine(**over):
    return RuleEngine(merged_settings(over))


def test_blocked_word_plain_and_leetspeak():
    e = engine()
    assert e.check("a", "a", "du hurensohn").decision == "ausblenden"
    assert e.check("b", "b", "du h u r 3 n s o h n").decision == "ausblenden"
    assert e.check("c", "c", "W1CHS3R!!!").decision == "ausblenden"


def test_short_word_needs_boundary():
    e = engine()
    assert e.check("a", "a", "hdf").decision == "ausblenden"
    assert e.check("b", "b", "schöne hdfarben") is None  # kein Treffer mitten im Wort


def test_normal_messages_pass():
    e = engine()
    for i, text in enumerate(["Hallo aus Hamburg ❤️", "voll schöner Stream", "haha geil", "Grüße an alle"]):
        assert e.check(str(i), str(i), text) is None, text


def test_links_phone_email():
    e = engine()
    assert e.check("a", "a", "folgt mir auf www.spam.de").category == "spam"
    assert e.check("b", "b", "schreib mir 0151 2345 6789").category == "persoenliche_daten"
    assert e.check("c", "c", "mail an max@test.de").category == "persoenliche_daten"
    assert engine(block_links=False).check("d", "d", "www.spam.de") is None


def test_repetition_and_flood():
    e = engine()
    assert e.check("x", "x", "kauft jetzt", now=100) is None
    assert e.check("x", "x", "kauft jetzt", now=101) is None
    assert e.check("x", "x", "kauft jetzt", now=102).decision == "beobachten"
    assert e.check("x", "x", "kauft jetzt", now=103).decision == "beobachten"
    assert e.check("x", "x", "kauft jetzt", now=104).decision == "ausblenden"
    q = engine()
    assert all(q.check("q", "q", "wie geht es dir?", now=300 + i) is None for i in range(3))
    e2 = engine()
    results = [e2.check("y", "y", f"msg {i}", now=200 + i) for i in range(8)]
    assert results[-1] is not None and "Flut" in results[-1].reason


def test_allowlist_and_disabled_category():
    e = engine(allowed_users=["bestie"])
    assert e.check("a", "bestie", "du hurensohn").decision == "ok"
    off = engine(categories={"beleidigung": False, "hass": False})
    assert off.check("b", "b", "du hurensohn") is None


def test_strikes_escalate():
    e = engine()
    assert e.apply_strikes("v", "ausblenden") == ("ausblenden", 1)
    assert e.apply_strikes("v", "ausblenden") == ("stummschalten", 2)
    e.apply_strikes("v", "ausblenden")
    assert e.apply_strikes("v", "ausblenden") == ("blockieren", 4)
    assert e.apply_strikes("w", "ok") == ("ok", 0)


def test_keyword_export_limit_and_custom():
    s = merged_settings({"blocked_words": ["hater123"]})
    kw = keyword_filter_export(s)
    assert "hater123" in kw and len(kw) <= 200
    assert keyword_filter_export(merged_settings({"use_base_list": False, "blocked_words": ["a"]})) == ["a"]


def test_question_heuristic():
    assert simple_question("Wann kommt das nächste Live")
    assert simple_question("bist du aus berlin?")
    assert not simple_question("hallo")
