"""**外の上位の公開日が、`--source free` の側だけ空でした**（2026-09-04 に埋めた）。

`data/niche_ceiling.jsonl` の `top[].published` は API 側（`videos.list`）には入っていて、
yt-dlp 側（`free_rows()`・flat な `entries`）にだけ**入る道がありません**でした。
申し送りが 3周 運んでいた項目です。

**なぜ日付が要るか。** この repo の形の判定（ショート／長尺）は **48時間 で 100回** の
門ひとつに乗っています。外の上位が何年もかけて 500万回 へ積み上げた本なら、
**その門は長尺を構造的に早く落とします** ＝ 形の結論そのものが、門の窓の副産物になる。
**答えは日付が入るまで出せません。**
"""
from __future__ import annotations

import json

import pytest

from scripts import niche_ceiling as nc


def test_空の公開日だけ埋める() -> None:
    rows = [{"id": "a", "published": ""}, {"id": "b", "published": "20260101"},
            {"id": "c", "published": ""}]
    asked: list[str] = []

    def fake(vid: str) -> str:
        asked.append(vid)
        return "20240315"

    got = nc.fill_published(rows, fetch=fake)
    assert got == 2
    assert asked == ["a", "c"]                      # 既に入っている行は撃たない
    assert [r["published"] for r in rows] == ["20240315", "20260101", "20240315"]


def test_取れなければ空のままで落ちない() -> None:
    rows = [{"id": "a", "published": ""}]
    assert nc.fill_published(rows, fetch=lambda v: "") == 0
    assert rows[0]["published"] == ""


def test_帳面へ入る本数までしか撃たない() -> None:
    """1本 1回の yt-dlp（数秒）。**読まれない行に数分を使わないこと。**"""
    rows = [{"id": str(i), "published": ""} for i in range(50)]
    asked: list[str] = []
    nc.fill_published(rows, fetch=lambda v: asked.append(v) or "20240101", limit=3)
    assert asked == ["0", "1", "2"]


def test_まとめて引くほうが既定(monkeypatch) -> None:
    """**1本ずつではなく `videos.list`（50本で 1単位）** —— 1本ずつの yt-dlp は
    いま bot 判定で断られます（`_fetch_upload_date` の註・2026-09-04 実測）。"""
    rows = [{"id": "a", "published": ""}, {"id": "b", "published": "20260101"},
            {"id": "c", "published": ""}]
    asked: list[list[str]] = []

    def many(ids: list[str]) -> dict:
        asked.append(list(ids))
        return {"a": "2024-03-15T00:00:00Z"}          # c は返らない ＝ 空のまま

    assert nc.fill_published(rows, fetch_many=many) == 1
    assert asked == [["a", "c"]]                      # **1回にまとめる**
    assert rows[0]["published"] == "2024-03-15T00:00:00Z"
    assert rows[2]["published"] == ""


def test_既定は1本ずつ撃たない(monkeypatch) -> None:
    """`fetch` も `fetch_many` も渡さなければ `_fetch_upload_dates`（まとめて）を使うこと。"""
    seen: list[list[str]] = []
    monkeypatch.setattr(nc, "_fetch_upload_dates", lambda ids: seen.append(list(ids)) or {})
    monkeypatch.setattr(nc, "_fetch_upload_date",
                        lambda v, timeout=60: pytest.fail("1本ずつ撃ってはいけません"))
    nc.fill_published([{"id": "a", "published": ""}])
    assert seen == [["a"]]


def test_yt_dlp_の返りは8桁の数字だけ受ける(monkeypatch) -> None:
    """`--print` は警告や空行を混ぜることがあるので、**形で弾く**こと。"""
    class _CP:
        def __init__(self, out: str) -> None:
            self.stdout, self.stderr, self.returncode = out, "", 0

    import subprocess
    for out, want in (("20240315\n", "20240315"), ("WARNING: x\n20240315\n", "20240315"),
                      ("NA\n", ""), ("\n", ""), ("2024031\n", "")):
        monkeypatch.setattr(subprocess, "run", lambda *a, out=out, **k: _CP(out))
        assert nc._fetch_upload_date("v") == want


def test_帳面を埋め直しても行の並びと中身は変わらない(tmp_path, monkeypatch) -> None:
    """**撃ち直すと別の帯になります**（検索結果は毎日 変わる）。同じ行のまま日付だけ入れること。"""
    led = tmp_path / "niche_ceiling.jsonl"
    a = {"at": "2026-09-01T00:00:00+00:00", "n": 2,
         "top": [{"id": "x", "published": "", "views": 9}]}
    b = {"at": "2026-09-02T00:00:00+00:00", "n": 3,
         "top": [{"id": "y", "published": "", "views": 8}]}
    led.write_text(json.dumps(a, ensure_ascii=False) + "\n"
                   + json.dumps(b, ensure_ascii=False) + "\n", encoding="utf-8")
    monkeypatch.setattr(nc, "_fetch_upload_dates",
                        lambda ids: {i: "2025-07-07T00:00:00Z" for i in ids})
    assert nc.backfill_published(1, path=led) == 0
    out = [json.loads(ln) for ln in led.read_text(encoding="utf-8").splitlines()]
    assert len(out) == 2
    assert out[0]["top"][0]["published"] == ""          # 新しい 1件 だけ
    assert out[1]["top"][0]["published"] == "2025-07-07T00:00:00Z"
    assert out[1]["top"][0]["views"] == 8 and out[1]["n"] == 3
