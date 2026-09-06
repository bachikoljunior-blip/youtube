"""yomi を TTS が無視する語（実測 09/06）は warnings で名指しされる。熟語の中の「額」は挙げない。"""
from studio.script import Script, Segment


def _s(say: str) -> Script:
    return Script(id="t-1", date="2026-09-07", title="t #Shorts", takeaway="t",
                  segments=[Segment(say=say)] * 5)


def test_裸の額は挙がる():
    assert any("「額」" in w for w in _s("増えた額は一生続きます。").warnings())


def test_熟語の額は挙がらない():
    assert not any("額" in w for w in _s("増えた金額は一生続きます。年額を12で割ります。").warnings())


def test_十分と額面も挙がる():
    ws = _s("額面で十分です。").warnings()
    assert any("額面" in w for w in ws)
