"""**外の帯の上位のショートの型を、実物の台本で数える脚**（`src/outside_short`）。**API 0単位。**

## なぜ要るか（2026-09-05 05:3x・サブの回）

長尺の側は「**札だけの本が、処置として枠を食う**」を 2日 かけて踏みました
（`src/daily_pick.treated_probe` の註）。ショートの側は**札すら無い**まま、
同じ位置に居ました（前提「外の帯の上位のショートの作り」・期限 09-08・腕 `per_video`）。

**だから順番は 脚 → 札 → 本です。** この検査は**脚**だけを押さえます ——
`config/topics.yaml` に `style: outside_short` を置く回は、**先にここを緑にしてから**
置くこと。逆順にすると、長尺と同じ穴を同じ順で踏みます。

**尺の脚が重い理由は実測です**（`data/niche_corpus.jsonl`・この回に数えた）:
140〜180秒 n=46 中央 2.8回/日 対 0〜60秒 n=20 中央 0.4回/日 ＝ **×7.0**（4升 とも単調）。
自分のショートは **109本 が 109本とも 23.6〜32.6秒**。
"""
from __future__ import annotations

import json

import pytest

from src import outside_short as osh


def _script(chars: int, title: str = "年金通知書が来ました 公開します",
            body: str = "封筒が届いたので開けます。") -> dict:
    n = max(1, chars // len(body) + 1)
    return {"title": title, "segments": [{"narration": (body * n)[:chars]}]}


def test_尺の帯は_秒から文字へ_同じ物差しで直る():
    """**`EFFECTIVE_CHARS_PER_SECOND` は写さずに読むこと** —— 長尺が 09/05 03:4x に
    「命じる尺と落とす床が食い違う」で1本も出せなくなった、その同じ穴を塞ぎます。"""
    from src import script_writer
    lo, hi = osh.total_chars_band()
    cps = script_writer.EFFECTIVE_CHARS_PER_SECOND
    assert lo == int(osh.LENGTH_BAND[0] * cps)
    assert hi == int(osh.LENGTH_BAND[1] * cps)
    assert lo > int(script_writer.SHORT_TOTAL_CHARS), (
        "**外の型の下限が、いまのショートの上限より下なら、この脚は何も言っていません。**"
        f" 下限 {lo}字 ／ いまの上限 {script_writer.SHORT_TOTAL_CHARS}字")


def test_いまの作りのショートは_尺の脚を落とす():
    """`SHORT_TOTAL_CHARS = 140`（30.2秒）の本は、外の帯でいちばん遅い升に入る。"""
    legs = dict((n, ok) for n, ok, _ in osh.legs_of_script(_script(140)))
    assert legs["(1) 尺"] is False


def test_帯に入った台本は_3脚とも通る():
    lo, hi = osh.total_chars_band()
    legs = osh.legs_of_script(_script((lo + hi) // 2))
    assert all(ok for _n, ok, _w in legs), legs


def test_題だけ外の型でも_尺が落ちれば処置ではない(tmp_path):
    """**薄い升（題・n=3）だけで「処置」を名乗らせないこと。**"""
    q = tmp_path / "critique_queue"
    q.mkdir()
    (q / "X.script.json").write_text(json.dumps(_script(140)), encoding="utf-8")
    state, why = osh.probe("X", queue=q)
    assert state == "no"
    assert "(1) 尺" in why


def test_控えが読めない本は_unknown_で_no_ではない(tmp_path):
    """`treated_probe` と同じ向き —— **読めないものを、通ったにも落ちたにも数えません。**"""
    state, _why = osh.probe("NOPE", queue=tmp_path)
    assert state == "unknown"


def test_帯の升は_いま数え直しても_LENGTH_BAND_が速い升のまま():
    """**べた書きの数を信じないこと。** 帯は撃つたびに増えます。

    ここが落ちたら、`LENGTH_BAND` を速い升へ動かすこと（**検査を消さないこと**）。
    """
    lines = osh.band_lines()
    assert lines, lines
    assert "食い違っています" not in "".join(lines), lines


@pytest.mark.parametrize("title,ok", [
    ("年金通知書！遂に来ました！公開します！", True),
    ("小規模企業共済 1か月で税額9万4500円減る #Shorts", False),
])
def test_題の型は_実物提示のときだけ通る(title, ok):
    lo, hi = osh.total_chars_band()
    legs = dict((n, o) for n, o, _ in osh.legs_of_script(_script((lo + hi) // 2, title=title)))
    assert legs["(2) 題"] is ok


# --- `style: outside_short` の札が付いたときだけ、床が立つこと -------------------
#
# **既定の道は1文字も変えていません**（実測: 上限 140字 のメッセージがそのまま出る）。
# 札が無いうちは、この帯は誰にも当たりません —— `config/topics.yaml` の
# `style: outside_short` は **まだ 0件** です（上の検査が見ています）。


class _V:
    headline = ""


class _Seg:
    def __init__(self, n: str):
        self.narration = n
        self.visual = _V()


class _Script:
    def __init__(self, chars: int):
        self.segments = [_Seg("あ" * 30) for _ in range(chars // 30)]

    def model_dump(self):
        return {"segments": [{"narration": s.narration} for s in self.segments]}


def _totals(script, topic_id, sw):
    return [p for p in sw.short_script_problems(script, topic_id) if "ナレーション合計" in p]


def test_札が無ければ_床は立たない():
    from src import script_writer as sw
    assert sw.short_total_band("") == (0, sw.SHORT_TOTAL_CHARS, "")
    assert _totals(_Script(120), "", sw) == []          # 短くても何も言わない
    assert _totals(_Script(180), "", sw)                # 上限は今までどおり


def test_札が付くと_帯は外の升へ移る(monkeypatch):
    from src import script_writer as sw
    monkeypatch.setattr(sw, "_topic_style", lambda _t: "outside_short")
    lo, hi, why = sw.short_total_band("x")
    assert (lo, hi) == osh.total_chars_band()
    assert "outside_short" in why
    # **いまの作り（140字）は、その帯では「短すぎる」**
    short = _totals(_Script(120), "x", sw)
    assert short and "下限" in short[0]
    # **帯に入っていれば何も言わない**
    assert _totals(_Script((lo + hi) // 2), "x", sw) == []
