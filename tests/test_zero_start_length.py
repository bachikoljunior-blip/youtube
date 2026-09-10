# -*- coding: utf-8 -*-
"""`scripts/zero_start.py` —— **「いま 0回 のまま」の列に、ショートと長尺を混ぜないこと**。

**この検査が見ているもの**（2026-09-11 08:0x・optimizer・Opus。`zero_start.durations` の註）:
20:0x の形は 0回 の本を**尺を混ぜて 1つの列**に並べており、実物の 3本 は
**89.6秒（studio の 5本目）・314.9秒・1580.0秒**でした。**下 2本 は Shorts フィードに乗らない尺**で、
§1 の「長尺は 1〜25回」で説明が付きます。混ぜたまま数えると
「0回 の本が 3本 も在る ＝ 配りが止まった」と読めてしまいます。

(1) `durations` が 2つ の口（`uploaded.jsonl` の `duration_s` ／ 台帳 `scheduled`＋`built`）から拾い、
    **分からない本は入れない**こと。
(2) `standing` が尺を返し、**尺の分からない本を「短い」と決めつけない**こと（`long is None`）。
(3) 印字が長尺を**下敷きの外**と名指しし、ショートだけを下敷きの初点の下端／上端に当てること
    （**陽性対照つき** —— 尺の印を外すと、その 2行 が消える）。
(4) 下敷きの側の**尺のカバレッジ**を必ず数で出すこと（読む側が「下敷きはショートだけ」と読まないため）。

`studio` を import しているので `pytest -m live` に入ります（`studio/livetests.py` の規則A）。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from studio import common  # noqa: F401  （規則A ＝ 生きている道具の検査に入れるため）

ROOT = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location("zero_start", ROOT / "scripts" / "zero_start.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


zs = _load()


def test_durations_は2つの口から拾う_無い本は入れない():
    up = [{"video_id": "old", "duration_s": 314.9},
          {"video_id": "nodur"},                       # 尺が無い本は入れない
          {"video_id": "bad", "duration_s": "abc"}]    # 数でない値も入れない
    led = [{"event": "scheduled", "id": "2026-09-10-x", "video_id": "new"},
           {"event": "built", "id": "2026-09-10-x", "seconds": 89.6}]
    d = zs.durations(up, led)
    assert d["old"] == (314.9, "uploaded.jsonl")
    assert d["new"] == (89.6, "台帳 built")
    assert "nodur" not in d and "bad" not in d


def test_同じ本に両方あれば台帳の焼いた秒を採る():
    up = [{"video_id": "v", "duration_s": 999.0}]
    led = [{"event": "scheduled", "id": "s", "video_id": "v"},
           {"event": "built", "id": "s", "seconds": 90.0}]
    assert zs.durations(up, led)["v"] == (90.0, "台帳 built")


def test_standing_は尺を返す_不明を短いと決めつけない():
    rows = [{"event": "measured", "id": "short", "views": 0, "age_h": 21.6},
            {"event": "measured", "id": "long", "views": 0, "age_h": 134.6},
            {"event": "measured", "id": "unknown", "views": 0, "age_h": 40.0}]
    durs = {"short": (89.6, "台帳 built"), "long": (1580.0, "uploaded.jsonl")}
    got = {x["id"]: x for x in zs.standing(rows, lo=8.0, durs=durs)}
    assert got["short"]["long"] is False
    assert got["long"]["long"] is True
    assert got["unknown"]["long"] is None        # 尺が分からない本を「短い」と数えない
    assert got["unknown"]["seconds"] is None


def test_立ち位置の行は長尺を下敷きの外と名指しする_陽性対照つき():
    now = [{"id": "short", "age_h": 21.6, "title": "s", "seconds": 89.6,
            "dur_src": "台帳 built", "long": False},
           {"id": "long", "age_h": 134.6, "title": "l", "seconds": 1580.0,
            "dur_src": "uploaded.jsonl", "long": True}]
    out = "\n".join(zs._standing_lines(now, 8.0, [45.0, 77.1, 77.6]))
    assert "下敷きの外" in out
    assert "下敷きが答えられるのは **ショート 1本**" in out
    assert "まだ下敷きの中のショート 1本" in out
    # 陽性対照: 尺の印を外す（全部 ショート扱い）と、上の 2行 は出ない
    flat = [dict(x, long=False) for x in now]
    out2 = "\n".join(zs._standing_lines(flat, 8.0, [45.0, 77.1, 77.6]))
    assert "下敷きの外" not in out2 and "1つ に数えないこと" not in out2


def test_下敷きの上端を越えたショートは名指しされる_陽性対照つき():
    now = [{"id": "s", "age_h": 90.0, "title": "s", "seconds": 89.6,
            "dur_src": "台帳 built", "long": False}]
    out = "\n".join(zs._standing_lines(now, 8.0, [45.0, 77.1, 77.6]))
    assert "77.6h を越えて 0回 のままのショートが 1本" in out and "+12.4時間" in out
    # 陽性対照: 齢が上端の手前なら、その行は出ない
    out2 = "\n".join(zs._standing_lines([dict(now[0], age_h=60.0)], 8.0, [45.0, 77.1, 77.6]))
    assert "越えて 0回 のままのショートは 0本" in out2


def test_下敷きの尺のカバレッジを必ず出す():
    g = {"A": [{"id": "a"}, {"id": "b"}], "B": [{"id": "c"}]}
    line = zs._base_length_line(g, {"a": (27.3, "uploaded.jsonl")})[0]
    assert "3本 のうち 尺 が分かるのは **1本**" in line
    assert zs._base_length_line(g, {})[0].endswith("尺 が分かる本は **0本**（`duration_s` が無い）")


def test_実物_長尺2本は下敷きの外_5本目はショート():
    """実物（2026-09-11 08:0x）: 89.6秒 の 5本目 と、314.9秒・1580.0秒 の旧作り 2本。"""
    durs = zs.durations(zs._rows(zs.UPLOADED), zs._rows(zs.LEDGER))
    assert durs["fMlY_uzHOMw"][0] == 1580.0
    assert durs["m7BRQs9X6Jc"][0] == 314.9
    assert durs["2YZ_4FXC-XI"][0] < zs.SHORT_MAX_S
    out = zs.report()
    assert "この下敷きは 尺 を分けていません" in out
    assert "下敷きの外" in out
