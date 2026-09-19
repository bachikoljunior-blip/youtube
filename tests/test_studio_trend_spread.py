"""**同じ日に何本 出しても、配られるのは 1本 だけではないか**（`trend.same_day_spread`）
—— 2026-09-18 05:xx JST・optimizer・Fable 5.1・ultracode・**API 0単位**。

実測 09/16: 同じ日・同じ形（short）・同じ族で **10:00 1,191回 対 12:00 1回**。
**賭けは `docs/JOURNAL.md` 2026-09-18 05:1x の 4 に先に書いてあります**
（あとから読み方を選ばないため ＝ §5 の形）。

止めるのは 5つ:

  (1) **読み A**（中央が小さく、最大が大きい）を A と言うこと
  (2) **読み B**（同じ桁）を B と言うこと ＝ **陰性対照**（この行は必ず A を出す行ではない）
  (3) どちらにも寄らない日は `None`（覆る条件 (3)）
  (4) **形を混ぜないこと** —— 長尺はどの日も 1回/本 なので、混ぜると A が必ず出る
  (5) **齢の窓の外の測りを読まないこと**（出したその周の 0回 を入れない）
"""
import json

from studio import trend


def _sched(sid, vid, day, hhmm="10:00"):
    return {"event": "scheduled", "id": sid, "video_id": vid,
            "publish_at": f"{day}T{hhmm}+09:00", "at": f"{day}T00:00:00+09:00"}


def _meas(vid, views, age_h=24.0):
    return {"event": "measured", "id": vid, "views": views, "age_h": age_h,
            "at": "2026-09-17T10:00:00+09:00"}


def _scripts(tmp_path, forms):
    for sid, form in forms.items():
        (tmp_path / f"{sid}.json").write_text(
            json.dumps({"form": form, "title": sid, "description": "", "tags": []}),
            encoding="utf-8")
    return tmp_path


def test_読みAをAと言う(tmp_path):
    rows = [_sched("s1", "v1", "2026-09-16", "10:00"), _meas("v1", 1191),
            _sched("s2", "v2", "2026-09-16", "12:00"), _meas("v2", 1),
            _sched("s3", "v3", "2026-09-16", "15:00"), _meas("v3", 2)]
    d = _scripts(tmp_path, {"s1": "short", "s2": "short", "s3": "short"})
    got = trend.same_day_spread(rows, scripts_dir=d)
    assert len(got) == 1
    assert got[0]["verdict"] == "A"
    assert got[0]["views"] == [1, 2, 1191]
    assert "読み A" in trend.same_day_spread_line(rows, scripts_dir=d)


def test_陰性対照_同じ桁ならB(tmp_path):
    rows = [_sched("s1", "v1", "2026-09-16", "10:00"), _meas("v1", 700),
            _sched("s2", "v2", "2026-09-16", "12:00"), _meas("v2", 500),
            _sched("s3", "v3", "2026-09-16", "15:00"), _meas("v3", 600)]
    d = _scripts(tmp_path, {"s1": "short", "s2": "short", "s3": "short"})
    got = trend.same_day_spread(rows, scripts_dir=d)
    assert got[0]["verdict"] == "B"
    assert "読み B" in trend.same_day_spread_line(rows, scripts_dir=d)


def test_どちらにも寄らない日は_None(tmp_path):
    # 中央 60（門 20 より上）・最大 ÷ 中央 = 5.0（門 3.0 より上）
    rows = [_sched("s1", "v1", "2026-09-16", "10:00"), _meas("v1", 300),
            _sched("s2", "v2", "2026-09-16", "12:00"), _meas("v2", 60),
            _sched("s3", "v3", "2026-09-16", "15:00"), _meas("v3", 40)]
    d = _scripts(tmp_path, {"s1": "short", "s2": "short", "s3": "short"})
    assert trend.same_day_spread(rows, scripts_dir=d)[0]["verdict"] is None


def test_形を混ぜない(tmp_path):
    """長尺はどの日も 1回/本 —— 混ぜると A が必ず出ます（覆る条件 (2)）。"""
    rows = [_sched("s1", "v1", "2026-09-16", "10:00"), _meas("v1", 1191),
            _sched("L1", "v9", "2026-09-16", "19:00"), _meas("v9", 1),
            _sched("L2", "v8", "2026-09-16", "21:00"), _meas("v8", 0)]
    d = _scripts(tmp_path, {"s1": "short", "L1": "long", "L2": "long"})
    # short は 1本 しかないので読める日が無い ＝ 混ざっていない証拠
    assert trend.same_day_spread(rows, scripts_dir=d) == []


def test_齢の窓の外は読まない(tmp_path):
    rows = [_sched("s1", "v1", "2026-09-16", "10:00"), _meas("v1", 1191, age_h=2.0),
            _sched("s2", "v2", "2026-09-16", "12:00"), _meas("v2", 1, age_h=24.0),
            _sched("s3", "v3", "2026-09-16", "15:00"), _meas("v3", 2, age_h=200.0)]
    d = _scripts(tmp_path, {"s1": "short", "s2": "short", "s3": "short"})
    assert trend.same_day_spread(rows, scripts_dir=d) == []


# ---------------------------------------------------------------------------
# **出した順**（`by_slot` / `last_ratio`）—— 2026-09-19 19:xx・optimizer・Opus 5・ultracode。
#
# なぜ足したか: `same_day_spread` は `sorted()` で**再生の小さい順**に並べ替えて返しており、
# **何本目 が何回だったかを 1つ も残していませんでした**。ところが 4つ の覆る条件
# （`budget` (6)・`cli.SHORT_SLOTS` の註・METHOD §38 (1)(2)）は、どれも
# **「最後に出した 1本 対 その前の中央」**という同じ比を名指しで要求します。
#
# 止めるのは 4つ:
#  (1) **順が残ること**（`by_slot` が 出した刻 の順であること ＝ 再生の順ではない）
#  (2) **比が出ること**（`last_ratio` ＝ 最後の 1本 ÷ その前の中央）
#  (3) **陰性対照** —— 最後が薄くない日で「当たりました」と言わないこと
#  (4) **門は 1か所**（`SPREAD_TAIL_HALF`）
# ---------------------------------------------------------------------------


def test_出した順が残る_再生の順ではない(tmp_path):
    rows = [_sched("s1", "v1", "2026-09-16", "07:00"), _meas("v1", 100),
            _sched("s2", "v2", "2026-09-16", "10:00"), _meas("v2", 900),
            _sched("s3", "v3", "2026-09-16", "12:00"), _meas("v3", 500)]
    d = _scripts(tmp_path, {"s1": "short", "s2": "short", "s3": "short"})
    got = trend.same_day_spread(rows, scripts_dir=d)[0]
    assert [x["at"] for x in got["by_slot"]] == ["07:00", "10:00", "12:00"]
    assert [x["views"] for x in got["by_slot"]] == [100, 900, 500]
    # **`views` は これまでどおり 再生の小さい順**（前の読み手を壊さない）
    assert got["views"] == [100, 500, 900]


def test_最後の1本が薄い日は_門に当たると言う(tmp_path):
    # その前の中央 1,000回・最後 200回 ＝ 0.2倍（門 0.5 を割る）
    rows = [_sched("s1", "v1", "2026-09-16", "07:00"), _meas("v1", 1000),
            _sched("s2", "v2", "2026-09-16", "10:00"), _meas("v2", 1000),
            _sched("s3", "v3", "2026-09-16", "21:00"), _meas("v3", 200)]
    d = _scripts(tmp_path, {"s1": "short", "s2": "short", "s3": "short"})
    got = trend.same_day_spread(rows, scripts_dir=d)[0]
    assert got["last_views"] == 200 and got["head_median"] == 1000.0
    assert got["last_ratio"] < trend.SPREAD_TAIL_HALF
    line = trend.same_day_spread_line(rows, scripts_dir=d)
    assert "出した順" in line and "当たりました" in line


def test_陰性対照_最後が薄くない日は言わない(tmp_path):
    rows = [_sched("s1", "v1", "2026-09-16", "07:00"), _meas("v1", 1000),
            _sched("s2", "v2", "2026-09-16", "10:00"), _meas("v2", 1000),
            _sched("s3", "v3", "2026-09-16", "21:00"), _meas("v3", 800)]
    d = _scripts(tmp_path, {"s1": "short", "s2": "short", "s3": "short"})
    got = trend.same_day_spread(rows, scripts_dir=d)[0]
    assert got["last_ratio"] >= trend.SPREAD_TAIL_HALF
    assert "当たりました" not in trend.same_day_spread_line(rows, scripts_dir=d)


def test_門は1か所(tmp_path):
    """「半分」は `SPREAD_TAIL_HALF` の 1か所 —— 印字も判定も同じ数から出ること。"""
    assert trend.SPREAD_TAIL_HALF == 0.5
    rows = [_sched("s1", "v1", "2026-09-16", "07:00"), _meas("v1", 1000),
            _sched("s2", "v2", "2026-09-16", "10:00"), _meas("v2", 1000),
            _sched("s3", "v3", "2026-09-16", "21:00"), _meas("v3", 200)]
    d = _scripts(tmp_path, {"s1": "short", "s2": "short", "s3": "short"})
    assert "半分 未満" in trend.same_day_spread_line(rows, scripts_dir=d)
