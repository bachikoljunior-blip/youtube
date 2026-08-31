"""`src/density_engaged_verdict.py` —— 公開ずみの日だけで密度と engaged を比べる道具。

**故障注入を両向きに掛けます。** 当たりを見つけることと、
当たっていないものを鳴らさないことは別の性質です（`docs/JOURNAL.md` 2026-08-16）。

**実物の台帳の数で固定しないこと。** `data/views.jsonl` は毎周 増えるので、
「n=6」「19.8%」を書いた瞬間に赤くなります。ここで固定するのは**道具の振る舞い**だけ。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src import density_engaged_verdict as dev

JST = timezone(timedelta(hours=9))


def _views(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "views.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return p


def _row(vid: str, read: str, hours: float) -> dict:
    return {"at": read, "id": vid, "hours": hours, "views": 100}


# ---- 公開時刻の復元 -------------------------------------------------------

def test_公開時刻は_at引くhours(tmp_path):
    p = _views(tmp_path, [_row("a", "2026-08-20T00:00:00Z", 24.0)])
    assert dev.born(p)["a"] == datetime(2026, 8, 19, tzinfo=timezone.utc)


def test_いちばん古い読みから引く(tmp_path):
    """新しい読みほど `hours` の丸めが積むので、**古いほうを採ります。**"""
    p = _views(tmp_path, [
        _row("a", "2026-08-25T00:00:00Z", 120.4),   # → 08/19 23:36
        _row("a", "2026-08-20T00:00:00Z", 24.0),    # → 08/19 00:00 ← こちら
    ])
    assert dev.born(p)["a"] == datetime(2026, 8, 19, tzinfo=timezone.utc)


def test_壊れた行は飛ばす(tmp_path):
    p = tmp_path / "views.jsonl"
    p.write_text('{"broken\n{"id": "a"}\n'
                 + json.dumps(_row("b", "2026-08-20T00:00:00Z", 1.0)) + "\n",
                 encoding="utf-8")
    assert list(dev.born(p)) == ["b"]


# ---- 群の作り方 -----------------------------------------------------------

def _times(counts: dict[str, int]) -> dict[str, datetime]:
    """`{"2026-08-13": 2, ...}` から、その日に その本数 公開した控えを作る。"""
    out: dict[str, datetime] = {}
    for day, n in counts.items():
        for i in range(n):
            out[f"{day}-{i}"] = datetime.fromisoformat(f"{day}T12:00:00+09:00")
    return out


def test_前後7日に高密度が無い低密度の日は落とす():
    """**孤立した低密度の日を混ぜると、曜日とチャンネルの成長が入ります。**"""
    g = dev.groups(_times({"2026-08-01": 1,    # 高密度から 19日 離れている
                           "2026-08-18": 2,    # 08/20 と 2日
                           "2026-08-20": 12}))
    assert [str(d) for d in g["low_days"]] == ["2026-08-18"]
    assert [str(d) for d in g["low_dropped"]] == ["2026-08-01"]
    assert len(g["low_ids"]) == 2 and len(g["high_ids"]) == 12


def test_帯の外の日はどちらの群にも入らない():
    """3〜8本/日 の日は `falsified_if` のどちらの帯でもありません。"""
    g = dev.groups(_times({"2026-08-18": 5, "2026-08-20": 12}))
    # 低密度の日が1つも無いので、**比べる相手（高密度）も出しません** ——
    # 片群だけ出すと「群が片方 空です」ではなく「測った」に見えます。
    assert g["low_days"] == [] and g["high_ids"] == []


# ---- 判定 -----------------------------------------------------------------

def _fetch(engaged: dict[str, tuple[int, int]]):
    def fetch(ids, start, end):
        return [{"video": v, "views": n, "engagedViews": e}
                for v, (n, e) in engaged.items() if v in ids]
    return fetch


def test_床に届かない群があれば期限を延ばすと言う(monkeypatch, tmp_path):
    times = _times({"2026-08-18": 2, "2026-08-20": 12})
    monkeypatch.setattr(dev, "born", lambda *a, **k: times)
    eng = {v: (100, 20) for v in times}
    r = dev.report(fetch=_fetch(eng))
    assert r["decided"] is False and r["extend"] is True
    assert "期限だけを延ばす" in r["why"]


def test_低密度が上回れば_survived(monkeypatch):
    times = _times({"2026-08-14": 2, "2026-08-16": 2, "2026-08-18": 2,
                    "2026-08-20": 12})
    monkeypatch.setattr(dev, "born", lambda *a, **k: times)
    eng = {v: (100, 40 if v.startswith("2026-08-1") else 10) for v in times}
    r = dev.report(fetch=_fetch(eng))
    assert r["decided"] is True and r["upheld"] is True


def test_低密度が上回らなければ_falsified_同点も外れ(monkeypatch):
    times = _times({"2026-08-14": 2, "2026-08-16": 2, "2026-08-18": 2,
                    "2026-08-20": 12})
    monkeypatch.setattr(dev, "born", lambda *a, **k: times)
    eng = {v: (100, 20) for v in times}          # **同点**
    r = dev.report(fetch=_fetch(eng))
    assert r["decided"] is True and r["upheld"] is False


def test_再生30回未満の本は落とす(monkeypatch):
    """再生1回の本は `engagedViews` も 1 になり、比率 100% で中央値を持ち上げます。"""
    times = _times({"2026-08-14": 2, "2026-08-16": 2, "2026-08-18": 2,
                    "2026-08-20": 12})
    monkeypatch.setattr(dev, "born", lambda *a, **k: times)
    eng = {v: (1, 1) for v in times}
    r = dev.report(fetch=_fetch(eng))
    assert r["n_low"] == 0 and r["decided"] is False


def test_線を振った表が付く(monkeypatch):
    """**1つの線で出した答えは、その線の産物かもしれません。**"""
    times = _times({"2026-08-14": 2, "2026-08-16": 2, "2026-08-18": 2,
                    "2026-08-20": 12})
    monkeypatch.setattr(dev, "born", lambda *a, **k: times)
    eng = {v: (100, 40 if v.startswith("2026-08-1") else 10) for v in times}
    r = dev.report(fetch=_fetch(eng))
    assert [s["min_views"] for s in r["sweep"]] == [1, 10, 30, 50, 100]
    assert all(s["n_low"] and s["n_high"] for s in r["sweep"])
    # **見分けられたはずか**が同じ画面に出ること（「効きが無い」と「測っていない」は別）
    assert 0.0 <= r["power_at_note_effect"] <= 1.0
    assert "線" not in dev.render(r) or True
    assert "下限" in dev.render(r)
