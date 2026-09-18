"""`trend.yen_now` —— **目標の単位（円）を読む唯一の口**の検査。

2026-09-18 09:4x・optimizer・Opus・1周 1体。決めと覆る条件は `docs/GOAL.md` (4-w)。

**なぜこの検査が要るか**: この口が出す数は「**門が いま開いたら いくらか**」で、
固定2（期限内に届くか）の答えを直に作ります。**帯を写した瞬間に黙って古くなる**ので、
「`peers.RPM_BAND` から引いていること」を撃って確かめます（覆る条件 (1) の当のもの）。
"""
from __future__ import annotations

import json

import pytest

from studio import peers, trend


def _board(tmp_path, short_views: int, long_views: int,
           n_short: int = 3, n_long: int = 3):
    """ショート `n_short`本・長尺 `n_long`本、齢は門の上。台本は tmp の disk に置く。"""
    rows: list[dict] = []
    for i in range(n_short):
        (tmp_path / f"s{i}.json").write_text(json.dumps({"form": "short"}), encoding="utf-8")
        rows.append({"event": "scheduled", "id": f"s{i}", "video_id": f"vs{i}",
                     "publish_at": f"2026-09-0{i + 1}T10:00:00+09:00"})
        rows.append({"event": "measured", "id": f"vs{i}", "views": short_views,
                     "age_h": trend.LPV_MIN_AGE_H + 1.0})
    for i in range(n_long):
        (tmp_path / f"l{i}.json").write_text(json.dumps({"form": "long"}), encoding="utf-8")
        rows.append({"event": "scheduled", "id": f"l{i}", "video_id": f"vl{i}",
                     "publish_at": f"2026-09-0{i + 1}T19:00:00+09:00"})
        rows.append({"event": "measured", "id": f"vl{i}", "views": long_views,
                     "age_h": trend.LPV_MIN_AGE_H + 1.0})
    return rows


def test_円_は_再生_かける_RPM_割る1000(tmp_path):
    d = trend.yen_now(_board(tmp_path, 1000, 100), tmp_path)
    s, l = d["forms"]["short"], d["forms"]["long"]
    assert s["median"] == 1000.0 and l["median"] == 100.0
    # ショート 1,000回 × ¥35/1000 ＝ ¥35/本 ／ 長尺 100回 × ¥1,000/1000 ＝ ¥100/本
    assert s["yen_per_video"]["中"] == pytest.approx(35.0)
    assert l["yen_per_video"]["中"] == pytest.approx(100.0)


def test_本数_で_割らず_かける(tmp_path):
    """**n倍 出せば 円/日 も n倍**（覆る条件 (3) が崩れるまでは線形）。"""
    d = trend.yen_now(_board(tmp_path, 1000, 100), tmp_path)
    s = d["forms"]["short"]
    assert s["per_day"] == pytest.approx(1.0)  # 3本 / 3日
    assert s["yen_per_day"]["中"] == pytest.approx(s["yen_per_video"]["中"] * s["per_day"])


def test_月は日の30倍_倍率は目標割る月(tmp_path):
    d = trend.yen_now(_board(tmp_path, 1000, 100), tmp_path)
    for lv in trend.YEN_LEVELS:
        assert d["yen_month"][lv] == pytest.approx(d["yen_day"][lv] * trend.YEN_DAYS_PER_MONTH)
        assert d["times"][lv] == pytest.approx(peers.GOAL_YEN / d["yen_month"][lv])
    assert d["goal"] == peers.GOAL_YEN


def test_長尺の帯は_peers_から引く_写しを持たない(tmp_path):
    """**帯を 2か所 に持たないこと**（覆る条件 (1)）。"""
    d = trend.yen_now(_board(tmp_path, 1000, 100), tmp_path)
    assert d["bands"]["long"] == tuple(float(x) for x in peers.RPM_BAND)
    # ショートの帯は `src/rpm_mix.py` の `BANDS`「ショート 低/中/高」と同じ数
    assert trend.SHORT_RPM_BAND == (20.0, 35.0, 60.0)


def test_門が開いていないことを_返りが持っている(tmp_path):
    """**実収入は ¥0** ＝ この数は収益の報告ではない（`gated`）。"""
    assert trend.yen_now(_board(tmp_path, 1000, 100), tmp_path)["gated"] is True


def test_測りが_0本_の形は_円を作らない(tmp_path):
    """齢の門を割る測りしか無い形は、**0円 ではなく「読めない」**（黙って 0 を足さない）。"""
    (tmp_path / "s0.json").write_text(json.dumps({"form": "short"}), encoding="utf-8")
    rows = [{"event": "scheduled", "id": "s0", "video_id": "vs0",
             "publish_at": "2026-09-01T10:00:00+09:00"},
            {"event": "measured", "id": "vs0", "views": 900,
             "age_h": trend.LPV_MIN_AGE_H - 1.0}]
    d = trend.yen_now(rows, tmp_path)
    assert d["forms"]["short"]["median"] is None
    assert d["forms"]["short"]["yen_per_video"] == {}
    assert d["yen_month"]["中"] == 0.0
    assert d["times"]["中"] is None
    assert "まだ 1本 も読めていません" in trend.yen_now_line(rows, tmp_path)


def test_行に_目標と実収入0と倍率が出る(tmp_path):
    line = trend.yen_now_line(_board(tmp_path, 1000, 100), tmp_path)
    assert "¥200,000/月" in line
    assert "実収入は **¥0**" in line
    assert "倍" in line


def test_形の倍率は_片側が_FORM_MIN_N_未満なら出さない(tmp_path):
    """**この検査が挟んでいるのは n の門であって、倍率の向きではありません。**

    2026-09-19 02:3x に直しました（optimizer・Opus・1周1体）。それまで この 2行 は
    **「円/本 は ショートが長尺の」という字**を探しており、**向きを決め打ち**していました。
    同じ回に `yen_now` を 中央 → **平均** に直したら（円は n本 の**合計**なので掛けるのは平均・
    あちらの註）、**長尺のほうが高く出て、この検査が落ちました** —— 落ちた理由は
    n の門ではなく、**検査が書いた向きのほう**です。
    いまは向きに依らない字（`円/本 は `）で挟みます。**向きを字で固定しないこと。**
    """
    rows = _board(tmp_path, 1000, 100, n_long=trend.FORM_MIN_N - 1)
    assert "円/本 は " not in trend.yen_now_line(rows, tmp_path)
    rows = _board(tmp_path, 1000, 100)
    assert "円/本 は " in trend.yen_now_line(rows, tmp_path)


def test_実物の台帳で_倍率が引ける():
    """**この回の実測**（09/18 09:4x）: 帯の中段で 3桁倍。門の側の倍率とは別の数。"""
    from studio.cli import ledger_rows

    d = trend.yen_now(ledger_rows())
    assert d["times"]["中"] is not None
    assert d["times"]["中"] > 1.0, "目標に届いているなら、この検査ごと役目を終えます"


def test_短い形は_status_に置く_長い形は_trend(tmp_path):
    """**同じ段落を 2度 読ませない**（`channel_line_short` と同じ形・`yen_now_short` の註）。"""
    rows = _board(tmp_path, 1000, 100)
    short = trend.yen_now_short(rows, tmp_path)
    long = trend.yen_now_line(rows, tmp_path)
    assert "¥200,000" in long and "200,000円" in short
    assert len(short) < len(long)
    # **2026-09-19 05:5x に字を直しました**（optimizer・opus）: 前は
    # 「**固定2 はこの行で答えること**」で、立った側は実際にそうし、JOURNAL の 09/19 の
    # 3周 が そろって「固定2 への答えは 58倍 のまま」と書いていました。
    # **同じ行が、その数を「門が いま開いたら の側」と註していたのに、
    # 門がいつ開くかは どこにも出ていませんでした**（実測 676日 ＝ 期限の 591日 後）。
    # ＝ 倍率だけで答えられない字にし、扉の日は `gate_opens_clause` が同じ行に並べます。
    assert "固定2 はこの行と、扉が開く日で答えること" in short
    assert trend.yen_now_short([], tmp_path) == "", "読めないときは 1行 も出さない"
