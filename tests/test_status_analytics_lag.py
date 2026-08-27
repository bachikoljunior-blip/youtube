"""**「あと N日」と「実データが在るか」は別物**（2026-08-18 に足した）。

## なぜ検査するか（**同じ読み違えが2回続けて起きています**）

8/19 が期限の前提（尺を30秒に縮めると engaged が上がる）は、根拠が
**8/16〜18 に公開した3本**です。ところが Analytics の日次は、この時点で
**8/14 までしか届いていませんでした**（3日遅れ）。実測（1本ずつ問い合わせ）:

    _4zhMy-VIyg  NHKylqsNfTw  CdX2oIb7BG8
    7b2-Z6Jw5DQ  crO3FUvL2NI  nPzWa_yhoQ0   → **6本とも NO ROWS**

それでも前提の節は「**あと1日**」とだけ出していたので、
**2回の申し送りが「次の回が判定できます」と書き、2回とも実データはありません。**

**期限は日付の引き算で出ますが、判定できるかは遅れとの引き算です。**
だから遅れを、期限のすぐ隣に出します。

## 分けて持っている理由

遅れを測れるのは `print_channel_signals`（Analytics を叩く）だけですが、
**要るのは前提の節のほう**で、そちらは**日枠が閉じた回にも出ます。**
同じ回で両方が走るとは限らないので、点として `data/analytics_lag.jsonl`
に積み、前提の節は**API を1回も叩かずに**そこから読みます。
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import status  # noqa: E402


def _use_tmp(monkeypatch, tmp_path):
    monkeypatch.setattr(status, "_LAG_PATH", tmp_path / "analytics_lag.jsonl")


def test_積んだ点から遅れを出す(monkeypatch, tmp_path):
    _use_tmp(monkeypatch, tmp_path)
    last = (datetime.now(status.JST).date() - timedelta(days=3)).isoformat()
    status._save_analytics_lag(last)

    assert status._analytics_lag() == (last, 3)


def test_いちばん新しい最終日を使う(monkeypatch, tmp_path):
    """**行の順ではなく日付で選ぶこと。** 積む順は回の順で、日付順とは限らない。"""
    _use_tmp(monkeypatch, tmp_path)
    today = datetime.now(status.JST).date()
    status._save_analytics_lag((today - timedelta(days=3)).isoformat())
    status._save_analytics_lag((today - timedelta(days=9)).isoformat())   # 古い点が後から来る

    got = status._analytics_lag()
    assert got == ((today - timedelta(days=3)).isoformat(), 3)


def test_点が無ければ黙る(monkeypatch, tmp_path):
    """**まだ一度も測れていない回で、嘘の0日を出さないこと。**"""
    _use_tmp(monkeypatch, tmp_path)
    assert status._analytics_lag() is None


def test_壊れた行でも回を止めない(monkeypatch, tmp_path):
    """**故障注入。** 計器が壊れても前提の節は出ること。"""
    _use_tmp(monkeypatch, tmp_path)
    (tmp_path / "analytics_lag.jsonl").write_text("これはJSONではありません\n", encoding="utf-8")
    assert status._analytics_lag() is None


def test_前提の節に遅れが出る(monkeypatch, tmp_path, capsys):
    """**期限のすぐ隣に出ること。** ここが本体です。"""
    _use_tmp(monkeypatch, tmp_path)
    last = (datetime.now(status.JST).date() - timedelta(days=3)).isoformat()
    status._save_analytics_lag(last)

    status.print_hypotheses()
    out = capsys.readouterr().out
    assert "実データは 3日 遅れています" in out
    assert last in out


def test_書けなくても落ちない(monkeypatch, tmp_path):
    """**故障注入。** 書き先が無くても `print_channel_signals` を殺さないこと。"""
    monkeypatch.setattr(status, "_LAG_PATH", tmp_path / "no" / "such" / "dir" / "x.jsonl")
    monkeypatch.setattr(Path, "mkdir", lambda *a, **k: (_ for _ in ()).throw(OSError("読み取り専用")))
    status._save_analytics_lag("2026-08-14")     # 例外を投げないこと


def test_遅れの日数はJSTで数える(monkeypatch):
    """**同じ出力に2つの数字が並ばないこと**（2026-08-18 に実際に並びました）。

    `print_channel_signals` は `date.today()`（UTC）、前提の節は JST で数えていて、
    **JST 01:4x に「3日前」と「4日遅れ」が同時に出ました。**
    期限は JST で書かれている（`hypotheses.yaml`）ので、JST に揃えます。

    **数える場所が1つであることを、ここで固定します。**
    """
    import inspect
    # **`inspect.getsource` を直に呼ばないこと**（2026-08-27 に踏んだ）。
    #     20分の走りの最中に同じ木へ `git merge` を撃つと、ファイルが下へずれ、
    #     **import 時の行番号で別の場所を切り出します** —— この検査が
    #     **コードは無傷のまま赤くなります**（実測: 兄弟が `scripts/status.py` に
    #     60行 入れた回。単体では緑なので「気まぐれ」と読まれます）。
    #     `conftest.source_of()` が、そのときは**そう言って**落とします。
    from conftest import source_of
    src = source_of(status.print_channel_signals, "print_channel_signals")
    assert "_lag_days(" in src, "遅れの数え方が写されています（2か所目）"
    assert "date.today() - date.fromisoformat" not in src, "UTC で数え直しています"

    today_jst = datetime.now(status.JST).date()
    assert status._lag_days((today_jst - timedelta(days=3)).isoformat()) == 3
    assert status._lag_days(today_jst.isoformat()) == 0
