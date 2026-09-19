"""声の時計（`studio/narration.py`）—— **図の 1歩 が、その数を声が言う瞬間に動くこと**。

オーナー 2026-09-19 12:3x `9155fe09`「ナレーションとアニメーションの表現をリンクさせたりしないと
わかりやすくなんないでしょ？画面がある意味が文字だけになってんのどうにかしろよ」。

**陰性対照を 2件 持っています**（この repo の癖）: `plan` を渡さない `slide_frames` と
`lit=None` の `compose` は、**前の形と 1画素も違わない絵**を出すこと。
"""
from __future__ import annotations

import pytest

from studio import narration as N, viz as V


# ---------------------------------------------------------------- 時計そのもの

def test_句ごとの秒が_コマの秒数に収まる():
    say = "合わせて138万8700円。手取りは1861万1300円です。"
    tl = N.timeline(say, 7.8, {})
    assert len(tl) == 2
    assert tl[0].t0 == 0.0
    assert tl[-1].t1 <= 7.8
    # 句は `say` を**そのまま分けたもの**（字を落とさない）
    assert "".join(p.text for p in tl) == say


def test_モーラの多い句が長い秒を取る():
    short_first = N.timeline("はい。手取りは1861万1300円です。", 8.0, {})
    assert short_first[0].t1 - short_first[0].t0 < short_first[1].t1 - short_first[1].t0


def test_拗音は前のモーラにくっつく_促音と長音は数える():
    assert N.morae("きょう") == 2          # きょ + う
    assert N.morae("がっこう") == 4        # が っ こ う
    assert N.morae("ラーメン") == 4


# ---------------------------------------------------------------- 数で声と絵をつなぐ

def test_数の字が声の中で見つかれば_その秒に合う():
    say = "合わせて138万8700円。手取りは1861万1300円です。"
    tl = N.timeline(say, 7.8, {})
    pos = N.find_cue(say, "1861万1300円")
    assert pos is not None
    a, _b = N.span_time(tl, say, *pos, {})
    assert a > tl[0].t1, "2つ目の句の数が、1つ目の句の間に合っている"


def test_数の切れ目を見る_短い数が長い数の中に当たらない():
    """`0円` が `600万円` の 0 に当たった実物（コマ6・2026-09-19 12:5x）。"""
    say = "600万円の20%は120万円。表の42万7500円を引いて、所得税は78万8700円。"
    assert N.find_cue(say, "0円") is None
    assert N.find_cue(say, "42万7500円") is not None


def test_声に出ない歩は_前の歩の後ろに詰める_止まらない():
    say = "20年が境目です。21年目は枠が70万円ふえます。"
    spec = {"kind": "table", "rows": [["枠", "800万円", "870万円"], ["税金", "138万8700円", "128万2200円"]]}
    w = N.cue_windows(say, 6.0, V.step_keys(spec), {})
    assert len(w) == 2
    assert all(b > a for a, b in w)
    assert w[0][1] <= w[1][0] + 1e-9, "歩の順は必ず単調"
    assert w[-1][1] <= 6.0 + 1e-9


def test_1歩_が動く長さは上限で切れる_始まりは動かない():
    say = "合わせて138万8700円です。"
    spec = {"kind": "bars", "items": [{"label": "税金", "value": 1388700}]}
    w = N.cue_windows(say, 9.0, V.step_keys(spec), {})
    a, b = w[0]
    assert b - a <= N.MAX_CUE_SECONDS + 1e-9
    tl = N.timeline(say, 9.0, {})
    want = N.span_time(tl, say, *N.find_cue(say, "138万8700円"), {})
    assert abs(a - want[0]) < 1e-6, "切るのは終わりだけ"


# ---------------------------------------------------------------- 歩の数は 1か所

@pytest.mark.parametrize("spec,n", [
    ({"kind": "bars", "items": [{"value": 1}, {"value": 2}]}, 2),
    ({"kind": "bars", "items": [{"value": 1}], "total": {"value": 2}}, 2),
    ({"kind": "waterfall", "start": {"value": 3}, "steps": [{"value": 1}], "end": {"value": 2}}, 3),
    ({"kind": "table", "rows": [["a", "1"], ["b", "2"], ["c", "3"]]}, 3),
])
def test_歩の数と手がかりの数が揃っている(spec, n):
    assert V.steps(spec) == n
    assert len(V.step_keys(spec)) == n


# ---------------------------------------------------------------- 絵の刻み

def _plan(say, seconds, spec):
    tl = N.timeline(say, seconds, {})
    wins = N.cue_windows(say, seconds, V.step_keys(spec), {}) if spec else []
    return N.frame_plan(seconds, tl, wins, V.steps(spec) if spec else 0)


def test_刻みの合計はコマの秒数と同じ():
    say = "枠を引くと1200万円がはみ出ます。半分の600万円に税金がかかります。"
    spec = {"kind": "bars", "items": [{"label": "はみ出た分", "value": 12000000},
                                      {"label": "半分", "value": 6000000}]}
    plan = _plan(say, 6.3, spec)
    assert abs(sum(d for d, *_ in plan) - 6.3) < 1e-6


def test_進みは_歩の境目を越えない():
    """丸めで **まだ動いていない歩**が 0.001 だけ進んだ実物（コマ7・手取り 5万5800円）。"""
    say = "合わせて138万8700円。手取りは1861万1300円です。"
    spec = {"kind": "waterfall", "start": {"label": "退職金", "value": 20000000},
            "steps": [{"label": "税金", "value": 1388700}],
            "end": {"label": "手取り", "value": 18611300}}
    plan = _plan(say, 7.8, spec)
    tl = N.timeline(say, 7.8, {})
    wins = N.cue_windows(say, 7.8, V.step_keys(spec), {})
    # 2歩目 が終わってから 3歩目 が始まるまでの間、進みは ちょうど 2/3 以下
    t = (wins[1][1] + wins[2][0]) / 2
    assert N.progress_at(t, wins, 3) <= 2 / 3 + 1e-9
    fr = V.frames_cued(spec, 7.8, (600, 400), plan)
    assert len(fr) == len(plan)


def test_光る字は_声の進みと一緒に前へ動く():
    say = "合わせて138万8700円。手取りは1861万1300円です。"
    plan = _plan(say, 7.8, None)
    lits = [(a, b) for _d, _p, a, b in plan]
    assert lits[0] != lits[-1], "句が 2つ 在れば、光る所は動く"
    assert [x for x in sorted(set(lits))] == sorted(set(lits))
    assert lits[-1][1] == len(say)


def test_句が1つのコマは刻まない_焼きを増やさない():
    plan = _plan("カワウソの年金計算室でした", 3.0, None)
    assert len(plan) == 1


# ---------------------------------------------------------------- 陰性対照

def test_陰性対照_lit_を渡さない絵は前と1画素も違わない(tmp_path):
    from studio import slides as S
    a = S.compose("手取り 1861万1300円", "税金は138万8700円", "合わせて138万8700円。", 3, 10,
                  None, tag="結論", board=["税金 138万8700円"], form="short")
    b = S.compose("手取り 1861万1300円", "税金は138万8700円", "合わせて138万8700円。", 3, 10,
                  None, tag="結論", board=["税金 138万8700円"], form="short", lit=None)
    assert list(a.convert("RGB").getdata()) == list(b.convert("RGB").getdata())


def test_陰性対照_planを渡さないslide_framesは今までの形(tmp_path):
    from studio import slides as S
    spec = {"kind": "bars", "items": [{"label": "枠", "value": 8000000}]}
    old = S.slide_frames("枠は 800万円", "1年40万円かける20年", "枠は800万円です。", 4, 10, None,
                         tmp_path, 4.0, spec, tag="計算", form="short")
    assert abs(sum(t for _p, t in old) - 4.0) < 1e-6
    assert old[-1][0].name == "slide-04.png"


def test_消す絵の名は_3桁でも当たる():
    """声に合わせると 1コマ 100枚 を越えることが在る（2桁 のままだと消され残る）。"""
    from pathlib import Path
    from studio.slides import is_transient_frame
    assert is_transient_frame(Path("slide-07-09.png"))
    assert is_transient_frame(Path("slide-07-123.png"))
    assert not is_transient_frame(Path("slide-07.png"))


def test_図が在るコマは_sub_を描かない_板のコマは今までどおり():
    from studio.slides import sub_on_screen
    assert sub_on_screen("税金は合わせて138万8700円", True) == ""
    assert sub_on_screen("税金は合わせて138万8700円", False) == "税金は合わせて138万8700円"


# ---------------------------------------------------------------- 声が言わない歩（材料・門ではない）

def test_声がその数を言わない歩を数える_止めない():
    from studio.script import Script, Segment
    s = Script(id="t", date="2026-09-20", title="t", takeaway="t", description="d", segments=[
        Segment(show="枠は 800万円", sub="", say="枠は800万円です。",
                viz={"kind": "bars", "items": [{"label": "枠", "value": 8000000}],
                     "total": {"label": "合計", "value": 9999999}}),
    ])
    got = s.unlinked_viz_steps()
    assert got is not None
    hit, tot, _ex = got
    assert (hit, tot) == (1, 2), "800万円 は声に在る・9999999 は無い"
    assert any("図の歩" in w for w in s.warnings())
    # **止めません** —— `problems()`（焼けなくなる側）には 1件 も入れないこと
    assert not any("図の歩" in p for p in s.problems())


def test_全部の歩が声に在れば黙る():
    from studio.script import Script, Segment
    s = Script(id="t", date="2026-09-20", title="t", takeaway="t", description="d", segments=[
        Segment(show="枠は 800万円", sub="", say="枠は800万円です。",
                viz={"kind": "bars", "items": [{"label": "枠", "value": 8000000}]}),
    ])
    assert s.unlinked_viz_steps() is None
    assert not any("図の歩" in w for w in s.warnings())
