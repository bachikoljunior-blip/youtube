"""出口の一手（登録の言葉）の門と、その A/B（2026-09-15 02:xx・optimizer・Fable）。

**なぜこの検査が在るか**: この repo でいちばん多い壊れ方は「言っている所と、している所が別」。
一手は 253本 とも 0件 のまま、METHOD にも CLAUDE.md にも「登録を増やす」と書いてありました。
**門と A/B を消すには、この file を消すしかありません**（diff に出ます）。
"""
from __future__ import annotations

import json

import pytest

from studio import script, trend


def _seg(**kw):
    base = {"say": "たとえば、60歳の人。", "show": "", "sub": "", "tag": "", "board": []}
    base.update(kw)
    return script.Segment(**base)


def _script(last_say: str, last_sub: str = "", date: str = "2026-09-20") -> script.Script:
    return script.Script(
        id="t-cta", date=date, title="て #Shorts", takeaway="て",
        yomi={}, segments=[_seg(), _seg(say=last_say, sub=last_sub)],
    )


def test_最後のコマに登録が無ければ止まる():
    ps = _script("去年の医療費は、いくらでしたか。").problems()
    assert any("登録の一手" in p for p in ps)


def test_声に登録が在れば通る():
    ps = _script("登録すると、あすの分がとどきます。").problems()
    assert not any("登録の一手" in p for p in ps)


def test_画面の字だけでも通る():
    ps = _script("いくらでしたか。", last_sub="登録するとあすの分がとどきます").problems()
    assert not any("登録の一手" in p for p in ps)


def test_最後のコマ以外に在っても止まる():
    """一手は**出口**に置く。途中に在っても門は開かない（置き場が効きの当のもの）。"""
    s = script.Script(id="t-cta", date="2026-09-20", title="て #Shorts", takeaway="て",
                      yomi={}, segments=[_seg(say="登録すると、とどきます。"), _seg()])
    assert any("登録の一手" in p for p in s.problems())


def test_公開ずみの本は遡って赤くしない():
    """`CTA_FROM` より前の本は、もう直せない ＝ 門を当てない（陰性対照）。"""
    ps = _script("去年の医療費は、いくらでしたか。", date="2026-09-14").problems()
    assert not any("登録の一手" in p for p in ps)
    assert script.CTA_FROM == "2026-09-15"


def test_型は声の上限に収まる():
    c = script.default_cta()
    assert len(c.say) <= script.MAX_SAY
    assert script.has_cta(c)
    long = script.default_cta("年金を60歳から早くもらうと失うもの")
    assert len(long.say) <= script.MAX_SAY


def test_いま出す本は3本とも一手を持っている():
    """09/15 以降の台本（公開前）に一手が入っていること。**この回に入れた当のもの**。"""
    got = []
    for p in sorted(script.SCRIPTS.glob("*.json")):
        d = json.loads(p.read_text())
        if d["date"] < script.CTA_FROM:
            continue
        s = script.load(p.stem)
        got.append((p.stem, script.has_cta(s.segments[-1])))
    assert got, "09/15 以降の台本が 1本も無い"
    assert all(ok for _, ok in got), [n for n, ok in got if not ok]


# ---- A/B の側 -------------------------------------------------------------

def _rows(tmp_path, cta: bool):
    (tmp_path / "a.json").write_text(json.dumps({
        "id": "a", "date": "2026-09-20", "title": "て #Shorts", "takeaway": "て",
        "segments": [{"say": "たとえば。"},
                     {"say": "登録すると、とどきます。" if cta else "いくらでしたか。"}],
    }, ensure_ascii=False))
    return [
        {"event": "scheduled", "id": "a", "video_id": "V1", "at": "2026-09-20T00:00:00+09:00"},
        {"event": "analytics_video", "id": "V1", "views": 1000, "subs_gained": 5,
         "at": "2026-09-22T00:00:00+09:00"},
    ]


def test_A_Bは一手の在る側と無い側を分ける(tmp_path):
    with_ = trend.cta_cohorts(_rows(tmp_path, True), scripts=tmp_path)
    assert with_["with"]["n"] == 1 and with_["without"]["n"] == 0
    assert with_["with"]["rate"] == pytest.approx(0.005)
    without = trend.cta_cohorts(_rows(tmp_path, False), scripts=tmp_path)
    assert without["with"]["n"] == 0 and without["without"]["n"] == 1


def test_3本たまるまで向きを読ませない(tmp_path):
    c = trend.cta_cohorts(_rows(tmp_path, True), scripts=tmp_path)
    assert c["ready"] is False
    assert trend.CTA_RUN_NEED == 3
    assert "たまるまで" in trend.cta_line(_rows(tmp_path, True), scripts=tmp_path)


def test_行は毎周印字される側に在る():
    import inspect
    src = inspect.getsource(trend.lines)
    assert "cta_line(rows)" in src, "`trend.lines` から外れたら、この A/B は誰も見ない"
