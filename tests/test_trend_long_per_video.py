"""**長尺 1本あたりの再生 —— 門も収益も、この 1つ の数に落ちます。**

（2026-09-17 15:0x・optimizer・Fable 5.1・ultracode。決めと覆る条件は `docs/GOAL.md` (4-s)）

09/13 から 09/17 までの 15周 は、門（登録1,000人・4,000時間）と収益（月20万）を
**別々の倍率**で数えてきました。長尺 n本/日 の形に揃えると 3つ とも同じ数に落ちます。

## この検査が固定するもの

    1. 1本あたりの中央値は、**測った長尺だけ**から出る
    2. **齢が浅い測りは分母に入れない**（出したその周の本を 0回 と数えない ＝ 陽性対照）
    3. 要る 1本あたりは **本数（`per_day`）で割る**（`1本/日` を写していない ＝ 陽性対照）
    4. `per_day` の分母は「刻の在る日の集合」ではなく**最初から最後までの日数**
       （長尺を置かなかった日を落とさない ＝ 陽性対照）
    5. 測りが 1件 も無い窓は、**0回/本 と言わずに「読めていない」と言う**

**覆る条件**: RPM が実測で出たら帯を捨てること（`peers.RPM_BAND` の 1か所）。
"""
from __future__ import annotations

import json

import studio.peers as peers
import studio.trend as trend


def _scripts(tmp_path, ids):
    d = tmp_path / "scripts"
    d.mkdir(parents=True)
    for sid in ids:
        (d / f"{sid}.json").write_text(json.dumps({"form": "long"}), encoding="utf-8")
    return d


def _rows(pairs, measured):
    rows = [{"event": "scheduled", "id": sid, "video_id": vid, "publish_at": at}
            for sid, vid, at in pairs]
    rows += [{"event": "measured", "id": vid, "age_h": age, "views": v}
             for vid, age, v in measured]
    return rows


def test_測った長尺だけで中央値を出す(tmp_path):
    ids = ["a", "b", "c"]
    sd = _scripts(tmp_path, ids)
    rows = _rows([("a", "VA", "2026-09-15T19:00+09:00"),
                  ("b", "VB", "2026-09-16T19:00+09:00"),
                  ("c", "VC", "2026-09-17T19:00+09:00")],
                 [("VA", 48.0, 100), ("VB", 48.0, 300)])
    d = trend.long_per_video(rows, scripts_dir=sd)
    assert d["n_long"] == 3 and d["n_measured"] == 2
    assert d["median"] == 200.0, d


def test_齢が浅い測りは分母に入れない(tmp_path):
    """**陽性対照 1**: 出したその周の本（齢 0.4h）を 0回 と数えると、1本あたりが半分に出ます。"""
    sd = _scripts(tmp_path, ["a", "b"])
    rows = _rows([("a", "VA", "2026-09-15T19:00+09:00"),
                  ("b", "VB", "2026-09-16T19:00+09:00")],
                 [("VA", 48.0, 400), ("VB", 0.4, 0)])
    d = trend.long_per_video(rows, scripts_dir=sd)
    assert d["n_measured"] == 1 and d["median"] == 400.0, d


def test_要る1本あたりは本数で割る(tmp_path):
    """**陽性対照 2**: `1本/日` を写していたら、本数を 3倍 にしても要求が動きません。"""
    sd1 = _scripts(tmp_path / "one", ["a"])
    one = trend.long_per_video(
        _rows([("a", "VA", "2026-09-15T19:00+09:00")], []), scripts_dir=sd1)
    sd3 = _scripts(tmp_path / "three", ["a", "b", "c"])
    three = trend.long_per_video(
        _rows([("a", "VA", "2026-09-15T12:00+09:00"),
               ("b", "VB", "2026-09-15T19:00+09:00"),
               ("c", "VC", "2026-09-15T21:00+09:00")], []), scripts_dir=sd3)
    rpm = sorted(peers.RPM_BAND)[1]
    assert three["per_day"] == 3.0 and one["per_day"] == 1.0
    assert three["need"][rpm] == one["need"][rpm] / 3.0, (one["need"], three["need"])


def test_置かなかった日を分母から落とさない(tmp_path):
    """**陽性対照 3**: 刻の在る日の集合で割ると、間の 3日 が消えて本数/日 が 2.5倍 に出ます。"""
    sd = _scripts(tmp_path, ["a", "b"])
    rows = _rows([("a", "VA", "2026-09-15T19:00+09:00"),
                  ("b", "VB", "2026-09-19T19:00+09:00")], [])
    d = trend.long_per_video(rows, scripts_dir=sd)
    assert d["per_day"] == 2 / 5, d          # 集合で割ると 2/2 ＝ 1.0 になる


def test_測りが無い窓は0回と言わない(tmp_path):
    sd = _scripts(tmp_path, ["a"])
    rows = _rows([("a", "VA", "2026-09-15T19:00+09:00")], [])
    d = trend.long_per_video(rows, scripts_dir=sd)
    assert d["median"] is None
    line = trend.long_per_video_line(rows, scripts_dir=sd)
    assert "読めていません" in line and "measure" in line
