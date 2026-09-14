"""yomi を TTS が無視する語（実測 09/06）は problems で止まる（2026-09-15 に `[?]` から `[!]` へ。実物で ひたい が 1本 出た）。熟語の中の「額」は挙げない。"""
from studio.script import Script, Segment


def _s(say: str) -> Script:
    return Script(id="t-1", date="2026-09-07", title="t #Shorts", takeaway="t",
                  segments=[Segment(say=say)] * 5)


def test_裸の額は挙がる():
    assert any("「額」" in w for w in _s("増えた額は一生続きます。").problems())


def test_熟語の額は挙がらない():
    assert not any("無視する語" in w for w in _s("増えた金額は一生続きます。年額を12で割ります。").problems())


def test_十分と額面も挙がる():
    ws = _s("額面で十分です。").problems()
    assert any("額面" in w for w in ws)
