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


def test_数字の並びが全部そろわない当たりは_別の数():
    """図の「13万7602円」が、声の「13万**2398**円」の `13` に当たっていた実物。

    2026-09-20 00:5x（optimizer・Opus 5・ultracode）に在庫の台本 56本 を当て直して数えた:
    **28歩・10本** が、この形で**別の数の所で動いて**いました（`find_cue` の覆る条件 (a)(b)(c)）。
    """
    say = "国民健康保険では43万円だけを引きました。残りは13万2398円です。"
    assert N.find_cue(say, "13万7602円") is None, "1組目 の 13 だけで当たってはいけない"
    assert N.find_cue(say, "13万2398円") is not None, "全部そろう数は今までどおり当たる"
    # **1組 しか数字の無い needle は 1字も変わらない**（覆る条件 (b)）
    assert N.find_cue("1年で180万の年金です。", "180万円") is not None


def test_声が_1歩_も指さないコマは_図が動かない():
    """**2026-09-19 14:4x に向きを変えた**（optimizer・Opus 5・ultracode）。

    前の版は「当たらなかった歩は前の歩の後ろに詰める（＝止まらない）」でした。
    在庫 42本 を数えると、**声が 1歩 も指さないコマ 70 のうち 79%（55コマ）は
    `say` に数字が 1つ も在りません** —— そこで表が 1行 ずつ湧くのは
    **声と何の関係も無い動き**で、オーナー 09/19 12:3x が「リンクしていない」と
    言っている物そのものでした。いまは **幅 0 の窓 ＝ 頭から全部 出ていて動かない**。
    """
    say = "20年が境目です。21年目は枠が70万円ふえます。"
    spec = {"kind": "table", "rows": [["枠", "800万円", "870万円"], ["税金", "138万8700円", "128万2200円"]]}
    w = N.cue_windows(say, 6.0, V.step_keys(spec), {})
    assert len(w) == 2
    assert all(a == b == 0.0 for a, b in w), "指されない図は動かない"
    # 図は**最初の絵から出来ています**（進み 1.0）
    assert N.progress_at(0.5, w, 2) == 1.0
    assert w[-1][1] <= 6.0 + 1e-9


def test_先頭の_もう出ている歩は動かず_新しい行だけが声に合う():
    """積み上がる表・棒（コマが進むごとに 1行 増え、声はその回の新しい行だけを言う）。

    実物 `2026-09-20-nenkin-tedori-hayamihyou` コマ30: 声が 18万・20万 の話をしている間に、
    前のコマで もう出ている 10万・12万・15万 の行が 1行 ずつ湧いていた（2026-09-19 14:3x の実測）。
    """
    say = "毎月18万円なら約16万円。毎月20万円なら約17万4000円です。"
    spec = {"kind": "table", "head": ["毎月", "手取り"],
            "rows": [["10万円", "約9万7000円"], ["12万円", "約11万5000円"],
                     ["15万円", "約13万7000円"], ["18万円", "約16万円"],
                     ["20万円", "約17万4000円"]]}
    w = N.cue_windows(say, 8.0, V.step_keys(spec), {})
    assert len(w) == 5
    assert all(a == b == 0.0 for a, b in w[:3]), "もう出ている 3行 は動かない"
    assert w[3][1] > w[3][0] and w[4][0] >= w[3][1], "新しい 2行 だけが順に動く"
    tl = N.timeline(say, 8.0, {})
    want = N.span_time(tl, say, *N.find_cue(say, "約17万4000円"), {})
    assert abs(w[4][0] - want[0]) < 1e-6, "最後の行は、声がその数を言う瞬間に始まる"
    # **陰性対照**: 声がどの行も指さない版に替えても、この形（動く/動かない）が入れ替わらないこと
    assert N.progress_at(0.0, w, 5) >= 3 / 5 - 1e-9, "頭の絵で もう 3行 出ている"


def test_carry_は_呼ぶ側が数えた_既出の分も受ける():
    """`render.build` が「前のコマで もう動いた歩」を数えて渡す道（長尺の繰り返しの表）。"""
    say = "この3つ目が、今日いちばん大事な所です。"
    spec = {"kind": "table", "rows": [["1 いくら", "37万2500円"], ["2 いつまで", "50日分"]]}
    keys = V.step_keys(spec)
    w = N.cue_windows(say, 5.0, keys, {}, carry=2)
    assert all(a == b == 0.0 for a, b in w)
    # 声が指す歩が在るときは、`carry` はその手前までしか効かない（指された歩は必ず動く）
    say2 = "2つ目は50日分です。"
    w2 = N.cue_windows(say2, 5.0, keys, {}, carry=2)
    assert w2[1][1] > w2[1][0], "声が指した歩は、carry で消されない"


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


# ------------------------------------------- 最後の当たりより後ろ（2026-09-19 22:xx）

def test_最後の当たりより後ろの歩は_そこで出そろって止まる():
    """`carry` の**鏡**（`N.cue_windows` の覆る条件 (d)(e)）。

    実物 `2026-09-23-kakyu-1sai-shita-short` コマ8: 声は「1歳ちがうと42万3700円ちがいます」で、
    表は 6行。**1行目 が「42万3700円」で引かれたあと、2〜6行目 が声の無い所で
    1行 ずつ湧いて**いました ＝ どこにも留まっていない動き。
    """
    say = "1歳ちがうと42万3700円ちがいます。"
    spec = {"kind": "table", "head": ["年齢差", "合計"],
            "rows": [["1歳年下", "42万3700円"], ["2歳年下", "84万7400円"],
                     ["3歳年下", "127万1100円"], ["4歳年下", "169万4800円"]]}
    w = N.cue_windows(say, 6.0, V.step_keys(spec), {})
    assert len(w) == 4
    assert w[0][1] > w[0][0], "声が言った 1行目 は動く"
    tail = w[1:]
    assert all(a == b for a, b in tail), "うしろの 3行 は幅 0（そこで出そろう）"
    assert all(abs(a - w[0][1]) < 1e-9 for a, _b in tail), "出そろうのは**最後の当たりの終わり**"
    # コマの終わりまで**何も動きません**（前は余りを等分して湧いていた）
    assert N.progress_at(w[0][1] + 0.01, w, 4) == 1.0


def test_錨が_2つ_あれば_あいだの歩は前後の数に留まる():
    """**直し方の安いほう**（`lint` の助言文）—— 表の最後の行を声に 1つ 言わせる。"""
    say = "1歳ちがうと42万3700円、6歳なら254万2200円ちがいます。"
    spec = {"kind": "table", "head": ["年齢差", "合計"],
            "rows": [["1歳年下", "42万3700円"], ["2歳年下", "84万7400円"],
                     ["3歳年下", "127万1100円"], ["6歳年下", "254万2200円"]]}
    w = N.cue_windows(say, 6.0, V.step_keys(spec), {})
    assert w[0][1] > w[0][0] and w[-1][1] > w[-1][0], "両端は声に当たる"
    assert all(w[k][1] > w[k][0] for k in (1, 2)), "あいだの 2行 は前後の錨のあいだで伸びる"
    assert w[1][0] >= w[0][1] - 1e-9 and w[2][1] <= w[3][0] + 1e-9, "順は単調"


def test_錨の無い歩を数える_止めない_参考の数とは別():
    from studio.script import Script, Segment
    seg = Segment(show="1歳 ＝ 42万3700円", sub="", say="1歳ちがうと42万3700円ちがいます。",
                  viz={"kind": "table", "head": ["年齢差", "合計"],
                       "rows": [["1歳年下", "42万3700円"], ["2歳年下", "84万7400円"],
                                ["3歳年下", "127万1100円"]]})
    s = Script(id="t", date="2026-09-23", title="t", takeaway="t", description="d", segments=[seg])
    got = s.unmoored_viz_steps()
    assert got is not None
    bad, moving, _ex = got
    assert (bad, moving) == (2, 3), "最後の当たり（1行目）より後ろの 2行 だけ"
    assert any("錨の無い歩" in w for w in s.warnings())
    assert not any("錨の無い歩" in p for p in s.problems()), "止めません"


def test_声が_1歩_も指さないコマは_錨の話に入らない():
    """図ぜんたいが止まっているコマは、**直す物ではありません**（幅 0 ＝ 読める板）。"""
    from studio.script import Script, Segment
    seg = Segment(show="20年が境目", sub="", say="20年が境目です。",
                  viz={"kind": "table", "rows": [["枠", "800万円"], ["税金", "138万8700円"]]})
    s = Script(id="t", date="2026-09-23", title="t", takeaway="t", description="d", segments=[seg])
    assert s.unmoored_viz_steps() is None, "動く歩が 0 のコマは数えない"
    assert s.unlinked_viz_steps() is not None, "（参考）の側には出る"
