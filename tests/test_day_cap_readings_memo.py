"""`day_cap._readings()` —— **同じファイルを、1回の走りで何十回も読み直さない。**

## なぜ要るか（2026-08-30 06:2x に測った）

`python -m cProfile -s cumtime scripts/eta.py --reflect` の実測:

    eta.py --reflect        **65.8秒**
      day_cap._readings     **201回・累計 40.8秒**（走り全体の 62%）
      day_cap.long_form     160回・累計 33.7秒（中身はほぼ上）
      json.loads          **5,286,452回** ＝ `data/views.jsonl` を 201回 読み直している

`--reflect` は **`--ship` が毎回 呼びます**。この repo の ship は 7日で 358件 なので、
**同じファイルを 7万回 読み直していた**ことになります。

**これは 2026-08-28 に `day_cap.cap()` で直したのと同じ形です**
（`scripts/eta.py` の `_view_cap_per_day`。そのとき 4分 → 24秒 になった）。
**あちらは memo を `eta.py` 側に置いた**ので、`_readings` を直に呼ぶ
`long_form()` / `by_day()` / `day_total()` / `src/deep_short.py` には効いていません。
**1か所で直すこと** —— 呼ぶ側ごとに memo を置くと、次に足された呼び口だけが
また 200回 読みます。**この 40秒 の由来がそれです。**

## ここで固定するもの

1. **同じファイル・同じ齢なら、2回目は読まない**（`read_text` が呼ばれない）
2. **ファイルが変わったら読み直す**（追記して mtime が動いたら、新しい数が出る）
3. **控えそのものを渡さない**（呼ぶ側が触っても、次の呼びに漏れない）

## 覆る条件

`data/views.jsonl` は追記だけなので、mtime と大きさで足ります。
**同じ mtime のまま中身が変わる積み方**（書き換え・切り詰め）を始めたら、
ここは古い数を返します。そのときは鍵に内容の指紋を足すこと。
"""
from __future__ import annotations

import datetime as dt
import json
import time

from src import day_cap


def _write(p, rows):
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _row(vid, at, hours, views):
    return {"at": at, "id": vid, "hours": hours, "views": views}


def test_2回目はファイルを読まない(tmp_path, monkeypatch):
    p = tmp_path / "views.jsonl"
    _write(p, [_row("a", "2026-08-20T00:00:00Z", 24.0, 100),
               _row("b", "2026-08-20T01:00:00Z", 24.0, 200)])
    day_cap._READINGS_MEMO.clear()

    first = day_cap._readings(p)
    assert set(first) == {"a", "b"}

    # **2回目は `read_text` を落としても答えが出ること。**
    calls = []
    orig = type(p).read_text

    def boom(self, *a, **kw):
        calls.append(1)
        return orig(self, *a, **kw)

    monkeypatch.setattr(type(p), "read_text", boom)
    second = day_cap._readings(p)
    assert second == first
    assert calls == [], "控えがあるのに読み直している"


def test_齢の下限がちがえば別に数える(tmp_path):
    p = tmp_path / "views.jsonl"
    _write(p, [_row("a", "2026-08-20T00:00:00Z", 10.0, 100)])
    day_cap._READINGS_MEMO.clear()
    assert set(day_cap._readings(p, min_age_h=6.0)) == {"a"}
    # 齢 48時間 では、この読み（10時間）は入らない。
    assert day_cap._readings(p, min_age_h=48.0) == {}


def test_ファイルが変わったら読み直す(tmp_path):
    p = tmp_path / "views.jsonl"
    _write(p, [_row("a", "2026-08-20T00:00:00Z", 24.0, 100)])
    day_cap._READINGS_MEMO.clear()
    assert set(day_cap._readings(p)) == {"a"}

    time.sleep(0.01)
    _write(p, [_row("a", "2026-08-20T00:00:00Z", 24.0, 100),
               _row("c", "2026-08-21T00:00:00Z", 24.0, 300)])
    # **古い数を返すくらいなら、読み直すほうがいい。**
    assert set(day_cap._readings(p)) == {"a", "c"}


def test_控えそのものを渡さない(tmp_path):
    p = tmp_path / "views.jsonl"
    _write(p, [_row("a", "2026-08-20T00:00:00Z", 24.0, 100)])
    day_cap._READINGS_MEMO.clear()
    got = day_cap._readings(p)
    got["a"] = (dt.datetime.now(day_cap.JST), 0.0, 0)
    got["zzz"] = (dt.datetime.now(day_cap.JST), 0.0, 0)
    again = day_cap._readings(p)
    assert "zzz" not in again, "呼ぶ側の書き込みが控えに漏れている"
    assert again["a"][2] == 100
