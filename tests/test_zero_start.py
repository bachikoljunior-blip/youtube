# -*- coding: utf-8 -*-
"""`scripts/zero_start.py` —— **「0回 のまま始まった本」の下敷きを、道具が数える**こと。

**この検査が見ているもの**（2026-09-10 20:0x・optimizer・Opus）:
(1) 群の割り方（A/B）と、窓の外の本を「答えられない」として外すこと。
(2) **帯（09〜13時 JST）で絞ること** —— 絞らないと 0回 ではなく**公開の刻**を測ります。
    **陽性対照**: 帯を外すと B の数が変わる（実物で 3本 → 25本）。
(3) `standing` が台帳の**いちばん新しい** `measured` だけを見ること
    （**陽性対照**: 前の行が 0回 でも、新しい行が 0回 でなければ挙げない）。
(4) 実物の下敷き（60/57/3・初点 45.0/77.1/77.6h）—— **旧データは凍結なので、この数は動きません**。
    動いたら、動いたのはデータではなく数え方です（`zero_start` の docstring と §7 (c) を一緒に直すこと）。

`studio` を import しているので `pytest -m live` に入ります（`studio/livetests.py` の規則A）。
"""
from __future__ import annotations

import datetime as dt
import importlib.util
from pathlib import Path

from studio import common

ROOT = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location("zero_start", ROOT / "scripts" / "zero_start.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


zs = _load()


def _pub(hour: int) -> dt.datetime:
    return dt.datetime(2026, 8, 21, hour, 0, tzinfo=dt.timezone(dt.timedelta(hours=9)))


def test_窓で再生が付いた本はA_0回のままはB():
    pts = {"a": [(1.0, 0), (9.0, 12), (50.0, 300)],
           "b": [(1.0, 0), (9.0, 0), (50.0, 7)]}
    pub = {"a": _pub(10), "b": _pub(10)}
    g = zs.split(pts, pub)
    assert [x["id"] for x in g["A"]] == ["a"]
    assert [x["id"] for x in g["B"]] == ["b"]
    assert g["B"][0]["first_pos_h"] == 50.0
    assert g["B"][0]["final"] == 7


def test_窓に点の無い本は外す():
    """「答えられない本」を分母に入れないこと（0回 の側にも 再生の側にも数えない）。"""
    pts = {"c": [(1.0, 0), (30.0, 5)]}   # 齢 8〜12h の点が無い
    g = zs.split(pts, {"c": _pub(10)})
    assert g["A"] == [] and g["B"] == []


def test_帯の外の本は入らない_陽性対照つき():
    pts = {"band": [(9.0, 0), (50.0, 1)], "late": [(9.0, 0), (50.0, 1)]}
    pub = {"band": _pub(10), "late": _pub(15)}
    assert [x["id"] for x in zs.split(pts, pub)["B"]] == ["band"]
    # 陽性対照: 帯を外すと 2本 になる（＝ 帯の絞りが本当に効いている）
    assert len(zs.split(pts, pub, band=None)["B"]) == 2


def test_公開の刻が台帳に無い本は帯で外す():
    """`uploaded.jsonl` に `at` の無い本を「帯の中」と決めつけないこと。"""
    pts = {"x": [(9.0, 0), (50.0, 1)]}
    assert zs.split(pts, {})["B"] == []
    assert len(zs.split(pts, {}, band=None)["B"]) == 1


def test_summary_は空の群でも落ちない():
    s = zs.summary([])
    assert s == {"n": 0, "median": None, "max": None, "over100": 0, "zero": 0}


def test_standing_はいちばん新しい行だけを見る_陽性対照():
    rows = [
        {"event": "measured", "id": "still0", "views": 0, "age_h": 3.0},
        {"event": "measured", "id": "still0", "views": 0, "age_h": 9.5},
        {"event": "measured", "id": "grew", "views": 0, "age_h": 3.0},
        {"event": "measured", "id": "grew", "views": 4, "age_h": 9.5},   # 陽性対照: もう 0回 ではない
        {"event": "measured", "id": "young", "views": 0, "age_h": 2.0},  # 窓の手前
        {"event": "channel", "id": "ch", "views": 84781},                # 別の event は見ない
    ]
    assert [x["id"] for x in zs.standing(rows, lo=8.0)] == ["still0"]


def test_台帳の場所は_studio_と同じもの():
    """`studio` が台帳を移したら、この道具は黙って空を返す ＝ ここで落ちて教えること。"""
    assert zs.LEDGER == common.LEDGER


def test_実物の下敷き_旧データは凍結なので数は動かない():
    pts = zs.series(zs._rows(zs.VIEWS))
    pub = zs.published_jst(zs._rows(zs.UPLOADED))
    g = zs.split(pts, pub)
    a, b = zs.summary(g["A"]), zs.summary(g["B"])
    assert (a["n"], b["n"]) == (57, 3)
    assert a["zero"] == 0                      # 窓で再生が付いた本に、最後まで 0回 は 1本も無い
    assert b["max"] == 275 and b["over100"] == 1
    assert sorted(round(x["first_pos_h"], 1) for x in g["B"]) == [45.0, 77.1, 77.6]
    # 陽性対照: 帯を外すと下敷きが別物になる（19本 が 14時以降/刻 不明）
    assert len(zs.split(pts, pub, band=None)["B"]) == 25


def test_報告は下敷きと_いまの立ち位置の両方を出す():
    out = zs.report()
    assert "窓の点を持つ本 **60本**" in out
    assert "B の初点" in out
    assert "いま 0回 のまま 齢 8h を越えている本" in out
