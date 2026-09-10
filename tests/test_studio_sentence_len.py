"""§3 の 6「1文 40字以内」を lint が `[?]` で名指しする（2026-09-10 19:5x・hourly・Fable）。
止めない（problems() には入れない）: 割るか残すかは書き手が決める。"""
from studio import script


def _seg(say):
    return script.Segment(say=say, show="x", sub="")


def test_41字の1文は挙がる():
    s = "あ" * 41 + "。"
    assert script.long_sentences(s) == [s]


def test_40字ちょうどは挙がらない():
    assert script.long_sentences("あ" * 39 + "。") == []  # 句点を含めて 40字


def test_2文に割れば挙がらない():
    assert script.long_sentences("あ" * 30 + "。" + "い" * 30 + "。") == []


def test_warningsに出てproblemsには出ない():
    sc = script.Script(id="t-1", date="2026-09-11", title="t #Shorts", takeaway="t",
                       segments=[_seg("あ" * 45 + "。")] * 5)
    assert any("1文 が 46字" in w for w in sc.warnings())
    assert not any("1文" in p for p in sc.problems())


def test_陽性対照_門を外すと落ちる(monkeypatch):
    monkeypatch.setattr(script, "MAX_SENTENCE", 999)
    assert script.long_sentences("あ" * 45 + "。") == []
