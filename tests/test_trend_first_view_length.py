# -*- coding: utf-8 -*-
"""`trend.first_view` —— **毎周 印字される「0回 のまま」の列に、ショートと長尺を混ぜないこと**。

**この検査が見ているもの**（2026-09-12 06:5x・optimizer・Opus。`trend.durations` の註）:
`scripts/zero_start.py` は 09/11 08:0x に尺で列を割りましたが、**`trend.first_view` は割っておらず**、
§7 の「いまの数」が毎周 写している「**0回 のまま門を越えたのは N本**」の N に、
**1580秒（26分20秒）の長尺 `fMlY_uzHOMw`** が **90秒 の Short `2YZ_4FXC-XI`** と
同じ列で数えられていました（この回に `videos.list` **1単位** で当て直した:
`PT26M20S` 対 `PT1M30S`・privacy は両方 public ＝ **0回 の出どころは処理でも公開設定でもない**）。
＝ METHOD §5 の「**絞りを 1つ 書いた道具は、書いた絞りの側だけ守ります**」の 3例目。

(1) `durations` が 2つ の口（`uploaded.jsonl` の `duration_s` ／ 台帳 `scheduled`＋`built`）から拾い、
    **分からない本は入れない**こと。
(2) `first_view` の本が尺を持ち、**尺の分からない本を「短い」と決めつけない**こと（`long is None`）。
(3) 印字が長尺を **下敷きの外** と名指しし、0回 の列を尺で割った数で締めること
    （**陽性対照つき** —— `durations` を空にすると、その 2つ が消える）。
(4) **門は 1か所**: `trend.SHORT_MAX_S` と `scripts/zero_start.SHORT_MAX_S` が食い違ったら鳴らす
    （`scripts/` は `studio` を import しない造りなので、借りずに写して検査で縛っている）。

`studio` を import しているので `pytest -m live` に入ります（`studio/livetests.py` の規則A）。
"""
from __future__ import annotations

import datetime as dt
import importlib.util
from pathlib import Path

from studio import trend

ROOT = Path(__file__).resolve().parent.parent
JST = dt.timezone(dt.timedelta(hours=9))
T0 = dt.datetime(2026, 9, 10, 10, 0, tzinfo=JST)


def _load_zero_start():
    spec = importlib.util.spec_from_file_location("zero_start", ROOT / "scripts" / "zero_start.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _m(vid: str, age_h: float, views: int) -> dict:
    return {"event": "measured", "id": vid, "age_h": age_h, "views": views,
            "at": (T0 + dt.timedelta(hours=age_h)).isoformat()}


# --- (1) 尺の口 --------------------------------------------------------------

def test_durationsは2つの口から拾い分からない本は入れない():
    up = [{"video_id": "old", "duration_s": 1580.0},
          {"video_id": "nodur"},                      # 尺が無い本は入れない
          {"video_id": "bad", "duration_s": "abc"}]   # 数でない値も入れない
    rows = [{"event": "scheduled", "id": "2026-09-10-x", "video_id": "new"},
            {"event": "built", "id": "2026-09-10-x", "seconds": 89.6}]
    d = trend.durations(rows, uploaded=up)
    assert d["old"] == (1580.0, "uploaded.jsonl")
    assert d["new"] == (89.6, "台帳 built")
    assert "nodur" not in d and "bad" not in d


def test_台帳の側が新しい口として勝つ():
    """同じ本が両方に在れば、studio の側（台帳 built）で上書きされること。"""
    up = [{"video_id": "v", "duration_s": 999.0}]
    rows = [{"event": "scheduled", "id": "s", "video_id": "v"},
            {"event": "built", "id": "s", "seconds": 90.0}]
    assert trend.durations(rows, uploaded=up)["v"] == (90.0, "台帳 built")


# --- (2) 本が尺を持つ・決めつけない ------------------------------------------

def test_0回の本は尺で割られる(monkeypatch):
    rows = [_m("short", 0.3, 0), _m("short", 3.9, 0),
            _m("long", 0.4, 0), _m("long", 5.0, 0),
            _m("nodur", 0.5, 0), _m("nodur", 4.0, 0)]
    monkeypatch.setattr(trend, "durations",
                        lambda r, uploaded=None: {"short": (90.0, "台帳 built"),
                                                  "long": (1580.0, "uploaded.jsonl")})
    f = trend.first_view(rows)
    by = {b["id"]: b for b in f["books"]}
    assert by["short"]["long"] is False
    assert by["long"]["long"] is True
    # **尺が分からない本を「短い」と決めつけない**（`durations` の註）。
    assert by["nodur"]["long"] is None and by["nodur"]["seconds"] is None
    assert [b["id"] for b in f["zero_short"]] == ["short"]
    assert [b["id"] for b in f["zero_long"]] == ["long"]
    assert [b["id"] for b in f["zero_unknown"]] == ["nodur"]
    # 3つ を足すと 0回 の列そのものに戻ること（黙って落ちる本が無い）。
    assert len(f["zero_short"]) + len(f["zero_long"]) + len(f["zero_unknown"]) == len(f["zero"])


# --- (3) 印字（陽性対照つき） -------------------------------------------------

def test_印字が長尺を下敷きの外と名指しする(monkeypatch):
    rows = [_m("short", 0.3, 0), _m("short", 3.9, 0),
            _m("long", 0.4, 0), _m("long", 5.0, 0)]
    monkeypatch.setattr(trend, "durations",
                        lambda r, uploaded=None: {"short": (90.0, "台帳 built"),
                                                  "long": (1580.0, "uploaded.jsonl")})
    out = "\n".join(trend.first_view_lines(rows))
    assert "**180秒 超・下敷きの外**" in out            # 本の行に立つ名指し
    assert "尺を混ぜたまま数えないこと" in out           # 締めの警句（長尺が居る回だけ）
    assert "尺 1580秒" in out and "尺 90秒" in out
    assert "**Shorts の尺 1本**" in out and "**下敷きの外（180秒 超）1本**" in out

    # **陽性対照**: 尺が 1つ も引けなければ、その 2つ は消え、決めつけもしない。
    monkeypatch.setattr(trend, "durations", lambda r, uploaded=None: {})
    out2 = "\n".join(trend.first_view_lines(rows))
    assert "**180秒 超・下敷きの外**" not in out2
    assert "尺を混ぜたまま数えないこと" not in out2
    assert "**尺 不明**" in out2
    assert "尺の分からない 2本" in out2


def test_0回の本が無ければ割りの字は出ない():
    rows = [_m("a", 0.5, 0), _m("a", 1.5, 3)]
    out = "\n".join(trend.first_view_lines(rows))
    assert "Shorts の尺" not in out and "下敷きの外" not in out


def test_本ごとに1行のまま():
    """尺の印は行を増やさないこと（`test_studio_first_view` の 1+2+1 と同じ数え方）。"""
    rows = [_m("a", 0.5, 0), _m("a", 1.5, 3), _m("b", 0.4, 0), _m("b", 1.0, 0)]
    assert len(trend.first_view_lines(rows)) == 1 + 2 + 1


# --- (4) 門は 1か所 -----------------------------------------------------------

def test_SHORT_MAX_Sは2つの道具で同じ数():
    """`scripts/` は `studio` を import しない造り（`scripts/*.py` 全部で 0件）なので、
    **借りずに写し、ここで縛る**。片方だけ動かしたら鳴ること。"""
    assert trend.SHORT_MAX_S == _load_zero_start().SHORT_MAX_S
