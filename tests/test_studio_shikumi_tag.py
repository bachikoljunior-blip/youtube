"""札「しくみ」（なぜそう決まっているか）の門（2026-09-11 20:0x・hourly・Opus）。

オーナー 09/11 19:5x「制度の仕組みは説明した方が良くない？計算結果だけ出されても
何でそうなるの？ってなる」（受け取り帳 `f3edb61f`）＋ 19:3x「今回だけ教えても
またおんなじことになるだろ」（`10f70f79`）＝ **その本だけ直すのではなく、毎本の型にする**。

止めない（`warnings()` の側）—— 題材によっては仕組みが結論そのもので、説明する所が無い本も在る。
**覆る条件**: 「しくみ」の札を持つ本が 3本 続けて 48h で、札の無い直近 3本 の中位を下回ったら、
この札は本を長くしているだけ ＝ §3 の 7-b ごと外すこと（数は §7）。
"""
from studio import script


def _seg(say: str, tag: str = "") -> dict:
    return {"say": say, "show": "", "sub": "", "tag": tag, "board": []}


def _script(tags: list[str]) -> script.Script:
    return script.Script(
        id="test-shikumi", date="2026-09-12", title="ためし #Shorts",
        takeaway="ためし", description="ためし", tags=[],
        yomi={}, segments=[_seg("ためしの文です。", t) for t in tags],
    )


def test_しくみの札は使える():
    s = _script(["前提", "しくみ", "決まり", "計算", "結論"])
    assert [p for p in s.problems() if "tag" in p] == []


def test_しくみが0なら名指しする_止めない():
    s = _script(["前提", "決まり", "計算", "結論", "見る所"])
    warns = [w for w in s.warnings() if "しくみ" in w]
    assert len(warns) == 1, warns
    # 止めない ＝ problems() には出ない
    assert [p for p in s.problems() if "しくみ" in p] == []


def test_しくみが在れば鳴らない():
    s = _script(["前提", "しくみ", "決まり", "計算", "結論"])
    assert [w for w in s.warnings() if "しくみ" in w] == []


def test_知らない札は止まる():
    s = _script(["前提", "仕組み", "決まり", "計算", "結論"])
    assert any("仕組み" in p for p in s.problems())


def test_画面の札にも色が在る():
    from studio import slides
    for t in script.TAGS:
        assert t in slides.TAG_COLORS, t


def test_09_12の本は_しくみを持つ():
    s = script.load("2026-09-12-taishoku-koujo-70man")
    assert [i for i, g in enumerate(s.segments, 1) if g.tag == "しくみ"]
