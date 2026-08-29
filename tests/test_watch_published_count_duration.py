"""`published_count` の尺の絞りを、既知の当たりで固定する。

**なぜ要るか（2026-08-27）。** 予約の 9割 はショートです。
「08/27〜09/07 に**長尺**を14本 公開したか」という門を、尺で絞らずに
`published_count` で数えると、**ショートだけで満ちます** ——
満ちていないものを満ちたと言う待ちは、`falsified_if` を実質 緩めます
（`src/watches.py` の冒頭が言っている「満ちたことに誰も気づけない」の逆向き）。
"""
from __future__ import annotations

import json

import pytest

from src import watches


@pytest.fixture()
def _fake_uploaded(monkeypatch, tmp_path):
    rows = [
        # 窓のなか・長尺
        {"video_id": "L1", "at": "2026-08-28T11:00:00Z", "duration_s": 402.0},
        {"video_id": "L2", "at": "2026-08-29T11:00:00Z", "duration_s": 250.0},
        # 窓のなか・ショート
        {"video_id": "S1", "at": "2026-08-28T04:00:00Z", "duration_s": 31.2},
        {"video_id": "S2", "at": "2026-08-30T04:00:00Z", "duration_s": 28.9},
        {"video_id": "S3", "at": "2026-09-01T04:00:00Z", "duration_s": 44.0},
        # 窓のそと・長尺
        {"video_id": "L0", "at": "2026-08-20T11:00:00Z", "duration_s": 500.0},
        # 尺の分からない本（古い控え）
        {"video_id": "X1", "at": "2026-08-29T11:00:00Z"},
    ]
    path = tmp_path / "uploaded.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    monkeypatch.setattr(watches, "UPLOADED", path)
    monkeypatch.setattr(watches, "analytics_last_day", lambda: None)
    return path


BASE = {"since": "2026-08-27", "until": "2026-09-07", "need": 14}


def test_絞らなければ窓のなかを全部数える(_fake_uploaded):
    g = watches._k_published_count(dict(BASE))
    assert g.now == 6          # L1 L2 S1 S2 S3 X1（窓のそとの L0 だけ落ちる）


def test_長尺だけを数える(_fake_uploaded):
    g = watches._k_published_count(dict(BASE, min_duration_s=180))
    assert g.now == 2          # L1 L2。**ショート3本では満ちない**
    assert "尺" in (g.note or "")


def test_尺の分からない本は絞った回では数えない(_fake_uploaded):
    """満ちていないものを満ちたと言うより、遅れて満ちるほうが安全。"""
    assert watches._k_published_count(dict(BASE, min_duration_s=1)).now == 5
    # X1 は尺が無いので落ちる（絞らなければ 6本）


def test_ショートだけを数えることもできる(_fake_uploaded):
    g = watches._k_published_count(dict(BASE, max_duration_s=180))
    assert g.now == 3          # S1 S2 S3


def test_台帳の長尺シェアの待ちは尺で絞っている():
    """**この待ちが尺の絞りを失ったら、ショートだけで満ちます。**"""
    got = [w for w in watches.load() if w.id == "長尺シェア-14本"]
    assert got, "config/watches.yaml の `長尺シェア-14本` が消えています"
    assert got[0].params.get("min_duration_s") == 180


# --------------------------------------------------------------- data_ready
#
# **「いま 0」は「まだ数えられていない」であって「出ていない」ではありません。**
# 2026-08-30 07:4x の実測: `長尺シェア-14本` の画面が「いま 0 / 要る 14」で、
# 控えの実物は**窓の中に 49本**（要る本数の 3.5倍）でした。
# 差は `data_ready: true` が Analytics の最終日より後の公開を落としたぶんで、
# その日（08/27）の長尺がちょうど 0本 だったからです。
# **窓のあいだじゅう「あと14本」と鳴るので、読んだ回は「供給が足りない」と読み、
# もう 3.5倍 入っている窓へ長尺を積み増す側に効きます。**


def test_実データ待ちのぶんを予約表の数として出す(_fake_uploaded, monkeypatch):
    from datetime import date
    monkeypatch.setattr(watches, "analytics_last_day", lambda: date(2026, 8, 27))
    g = watches._k_published_count(dict(BASE, min_duration_s=180, data_ready=True))
    assert g.now == 0                      # 08/27 までに公開した長尺は 0本
    assert "予約表では 2本" in (g.note or "")   # L1 L2 は控えに在る
    assert "まだ実データが来ていない" in (g.note or "")


def test_判定の数そのものは動かさない(_fake_uploaded, monkeypatch):
    """**note は増やすが `now` は増やさない。**

    実データの来ていない本で前提を閉じるほうが危険なので、
    満ち具合（`met`）の側は 08/27 までで数えたままにする。
    """
    from datetime import date
    monkeypatch.setattr(watches, "analytics_last_day", lambda: date(2026, 8, 29))
    g = watches._k_published_count(dict(BASE, min_duration_s=180, need=2,
                                        data_ready=True))
    assert g.now == 2 and g.met            # L1(08/28) L2(08/29) は実データ側
    assert "予約表では" not in (g.note or "")  # 削っていない回は出さない
