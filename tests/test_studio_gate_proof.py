"""`peers.gate_proof` —— **扉(b) を「期限の長さ」で越えた口が在るか**（2026-09-19 03:xx）。

**陽性対照を先に置いています**（02:5x の回が `gate_measured` で置いた形と同じ）——
反例が 1本 も無い台帳を渡すと `counter == 0` になり、
反例を 1本 足すと `counter == 1` になること。**先に「動くこと」を測ってから、実データを見ます。**

**この検査が守っているもの**: 「期限の中に扉(b) は無い」という結び（02:5x の回）が、
**うちの歩幅を扉の位置と読んだもの**だったこと。反例の行が `trend.lines()` から消えると、
同じ読みに戻ります ＝ **並びの検査（`test_扉bの距離の行の真下に反例の行が来る`）が本体**です。
"""
from __future__ import annotations

import datetime as dt
import json

import pytest

from studio import peers


def _corpus(tmp_path, channels):
    p = tmp_path / "niche_channels.jsonl"
    p.write_text(json.dumps({"at": "2026-09-16T16:55:26+09:00", "units": 5,
                             "n": len(channels), "channels": channels},
                            ensure_ascii=False) + "\n", encoding="utf-8")
    return p


NOW = dt.datetime(2026, 9, 19, 3, 0, tzinfo=dt.timezone(dt.timedelta(hours=9)))


def _ch(cid, title, days_old, subs, views, videos=40):
    born = NOW - dt.timedelta(days=days_old)
    return {"id": cid, "title": title, "created": born.astimezone(dt.timezone.utc)
            .isoformat().replace("+00:00", "Z"),
            "subs": subs, "views": views, "videos": videos}


def test_陽性対照_反例が0本の台帳では0_足すと1になる(tmp_path, monkeypatch):
    # 若いが、どちらの扉も越えていない口だけ
    none = [_ch("UC1", "だめな口", 40, 11, 27_500)]
    monkeypatch.setattr(peers, "NICHE_CHANNELS", _corpus(tmp_path, none))
    g = peers.gate_proof(85, NOW)
    assert g["counter"] == 0, g
    assert len(g["young"]) == 1
    assert g["min_days"] is None

    # 反例を 1本 足す（登録 5,000・総再生 90万 ＝ 0.27分/回 で 4,000時間）
    both = none + [_ch("UC2", "越えた口", 46, 5_000, 900_000)]
    monkeypatch.setattr(peers, "NICHE_CHANNELS", _corpus(tmp_path, both))
    g2 = peers.gate_proof(85, NOW)
    assert g2["counter"] == 1, g2
    assert g2["passed"][0]["id"] == "UC2"
    assert 45 < g2["min_days"] < 47


def test_期限より古い口は窓に入らない(tmp_path, monkeypatch):
    old = [_ch("UC3", "古いが巨大な口", 400, 150_000, 7_000_000)]
    monkeypatch.setattr(peers, "NICHE_CHANNELS", _corpus(tmp_path, old))
    g = peers.gate_proof(85, NOW)
    assert g["young"] == []
    assert g["counter"] == 0
    # **0本 は「越えられない」ではなく「窓が空」** ＝ 行がそう書くこと（覆る条件 (1)）
    assert "窓が空" in peers.gate_proof_line(85, NOW)


def test_台帳が無ければ_0本と言わずに_測っていないと言う(tmp_path, monkeypatch):
    monkeypatch.setattr(peers, "NICHE_CHANNELS", tmp_path / "ない.jsonl")
    g = peers.gate_proof(85, NOW)
    assert g["n_corpus"] == 0 and g["counter"] == 0
    line = peers.gate_proof_line(85, NOW)
    assert "測っていない" in line and "5単位" in line


def test_時間の扉は前提の分_回で切っている(tmp_path, monkeypatch):
    """`GATE_PROOF_MAX_MIN_PER_VIEW` は**前提**（覆る条件 (2)）＝ 境目で札が変わること。"""
    # 4,000時間 ÷ 4.0分 = 60,000回 ちょうどが境
    just_under = [_ch("UC4", "境の内", 50, 2_000, 60_500)]
    just_over = [_ch("UC5", "境の外", 50, 2_000, 59_000)]
    monkeypatch.setattr(peers, "NICHE_CHANNELS", _corpus(tmp_path, just_under))
    assert peers.gate_proof(85, NOW)["counter"] == 1
    monkeypatch.setattr(peers, "NICHE_CHANNELS", _corpus(tmp_path, just_over))
    g = peers.gate_proof(85, NOW)
    assert g["counter"] == 0
    assert g["young"][0]["subs_ok"] is True and g["young"][0]["hours_ok"] is False


def test_実データ_218チャンネルに反例が1本ある():
    """**実測**（`data/niche_channels.jsonl`・API 0単位）。

    **覆る条件 (1)**: corpus は 2026-09-16 の写しで、日が経つと若い口は窓から落ちます。
    この検査が「窓が空」で落ちたら、**corpus を取り直すこと**（`channels.list` 5単位）で、
    **結論を「越えられない」へ書き換えないこと。**
    """
    g = peers.gate_proof(85)
    if not g["young"]:
        pytest.skip("corpus が古びて窓が空（覆る条件 (1) ＝ 取り直す）")
    assert g["n_corpus"] >= 200
    assert g["counter"] >= 1, g["young"]
    assert g["min_days"] is not None and g["min_days"] < 85


def test_扉bの距離の行の真下に反例の行が来る():
    """**本体の検査** —— 2行 が離れると、また「うちの歩幅」を「扉の位置」と読みます。"""
    from studio import trend
    out = trend.lines([])
    idx = [i for i, s in enumerate(out) if "gate_measured" in s or "報告の台帳で測った距離" in s]
    jdx = [i for i, s in enumerate(out) if "peers.gate_proof" in s or "扉を越えた口が在るか" in s]
    assert idx and jdx, (idx, jdx)
    assert min(jdx) == min(idx) + 1, (idx, jdx)
