"""**外の帯の「×N」は、外の生涯の累計 ÷ 自分の 48時間 でした**（2026-09-04 に測った）。

公開日を埋めて数えたら、外の上位に **48時間 以内の本は 1本もありません**:

    長尺    齢 中央 **203日** ／ 最小 128日 ／ 1日あたり 6,000〜29,000回
    ショート  齢 中央 **1,729日（4.7年）** ／ 最小 274日 ／ 1日あたり 14〜186回

しかも `SP_FILTERS` は**形ごとに窓が違います**（ショートは日付なし ＝ 全期間、
長尺は `year` ＝ 今年）。**別々の窓で測った2つを、横に並べて形を決めていました。**

1日あたりに直すと向きが変わります —— 自分のショート 約525回/日 は
**外のショートの上位より上**で、外の長尺より下。
**「外の帯が上」は、形によっては齢の産物です。**
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from scripts import niche_ceiling as nc

NOW = datetime(2026, 9, 4, 0, 0, tzinfo=timezone.utc)


def _row(form: str, items: list[tuple[int, int]]) -> dict:
    """`items` は `(再生, 齢の日数)`。"""
    return {"top": [{"id": f"v{i}", "form": form, "views": v,
                     "published": (NOW - timedelta(days=d)).isoformat().replace("+00:00", "Z")}
                    for i, (v, d) in enumerate(items)]}


def test_齢で割った数を出す() -> None:
    row = _row("short", [(1000, 100), (2000, 100), (3000, 100)])
    out = "\n".join(nc.per_day_lines(row, "short", own_median_48h=1000, now=NOW))
    assert "生涯の累計" in out
    assert "齢 中央 **100日**" in out
    assert "48時間 以内に出た本 0本" in out
    assert "中央 **20回/日**" in out              # 2000 / 100
    # 自分は 1,000回/48h ＝ 500回/日 → 外の中央 20 は ×0.04
    assert "500回/日" in out and "×0.04" in out


def test_48時間以内の本は数えて出す() -> None:
    row = _row("long", [(100, 1), (200, 100), (300, 100)])
    out = "\n".join(nc.per_day_lines(row, "long", now=NOW))
    assert "48時間 以内に出た本 1本" in out


def test_標本が3本に満たなければ1行も出さない() -> None:
    """**中央値が1本で決まる帯から、形の結論を出さないこと。**"""
    assert nc.per_day_lines(_row("short", [(1000, 100), (2000, 100)]), "short", now=NOW) == []
    assert nc.per_day_lines({"top": []}, "short", now=NOW) == []


def test_公開日の空いている本は数に入れない() -> None:
    row = _row("short", [(1000, 100), (2000, 100), (3000, 100)])
    for r in row["top"][:2]:
        r["published"] = ""
    assert nc.per_day_lines(row, "short", now=NOW) == []       # 残り 1本 ＝ 門の下


def test_齢が読めない形式でも落ちない() -> None:
    row = _row("short", [(1000, 100), (2000, 100), (3000, 100)])
    row["top"][0]["published"] = "きのう"
    assert nc.age_days(row["top"][0], NOW) is None
    assert nc.per_day_lines(row, "short", now=NOW) == []       # 残り 2本 ＝ 門の下


def test_top_lines_の末尾に必ず付く(tmp_path, monkeypatch) -> None:
    """**累計と1日あたりは、必ず並べて出すこと** —— 片方だけだと窓の差が結論を作ります。"""
    import json
    led = tmp_path / "niche_ceiling.jsonl"
    row = _row("short", [(1000, 100), (2000, 100), (3000, 100)])
    row.update({"at": NOW.isoformat(), "queries": ["q"], "form": "short",
                "summary": {"short": {"n": 3, "max": 3000, "p90": 3000,
                                      "median": 2000, "channels": 3}}})
    led.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    monkeypatch.setattr(nc, "THUMBS", tmp_path / "thumbs")
    out = "\n".join(nc.top_lines("short", path=led, now=NOW, own_median=1000))
    assert "生涯の累計" in out and "中央 **20回/日**" in out
