"""**取り置きが、自分で名指しした相手を止めていました。**

## 実物（2026-09-02 16:5x）

`upload_cap._ledger_hold()` の返り文は、こう言います:

    残しているのは、**前提を閉じる読み**と**次の1本を良くする書き込み**
    （`improve`・50単位）のためです

そして同じ回に

    python scripts/refresh_thumbnail.py --missing --video MqQKSnbM0OI

—— **まさにその「次の1本を良くする書き込み・50単位」**（09/03 に出す本の
サムネイルが YouTube に載っていない）—— を、この門が止めました。

**取り置きはただの床**（`used < cap - RESERVE_UNITS`）で、
**誰が撃つかを1文字も見ていません。** 文と実装が別だった、この repo で
いちばん多い壊れ方の、この門ぶんです。

## ここで固定するもの

1. `improve_one=True` の回だけ、取り置きが `RESERVE_UNITS - IMPROVE_UNITS` へ下がる
2. **既定は1単位も緩まない**（束 ＝ `--missing` の全本には渡さない）
3. `YT_NO_RESERVE=1` の逃げ道は残る

## 覆る条件

取り置きを食い切って 403 が出るようになったら `IMPROVE_UNITS` を 0 にすること
（読みの側は 350単位 残るので、前提を閉じる回は止まりません）。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import upload_cap  # noqa: E402


def _rows(used: int) -> list[dict]:
    return [{"api": "data", "ok": True, "units": used, "by": "テスト"}]


def _patch(monkeypatch, used: int) -> None:
    from src import quota_ledger as ql
    monkeypatch.setattr(ql, "rows", lambda *a, **k: _rows(used))
    monkeypatch.delenv("YT_NO_RESERVE", raising=False)
    # 下の `measured_budget()` は、この検査では黙らせる（見るのは帳面の門）。
    monkeypatch.setattr(upload_cap, "measured_budget", lambda *a, **k: {})


def _band() -> tuple[int, int]:
    """**既定では止まり、`improve_one` なら通る**帯の、代表の1点。"""
    from src import quota_ledger as ql
    cap = int(ql.DAY_UNITS)
    return cap - upload_cap.RESERVE_UNITS, cap - upload_cap.RESERVE_UNITS + 1


def test_その帯では既定は止まる(monkeypatch):
    _, used = _band()
    _patch(monkeypatch, used)
    assert upload_cap.reserve_hold() is not None


def test_その帯では次の1本だけ通る(monkeypatch):
    _, used = _band()
    _patch(monkeypatch, used)
    assert upload_cap.reserve_hold(improve_one=True) is None, (
        "**門が自分で名指しした 50単位** です。ここを止めると、"
        "規則3（次の枠で出る1本を、出る瞬間まで良くし続ける）が撃てません")


def test_取り置きを食い切った窓では次の1本も止まる(monkeypatch):
    """**50単位 を通すのは取り置きの中からだけ。** 枠そのものは越えません。"""
    from src import quota_ledger as ql
    _patch(monkeypatch, int(ql.DAY_UNITS) + 1)
    assert upload_cap.reserve_hold(improve_one=True) is not None


def test_余っている窓はどちらも通る(monkeypatch):
    _patch(monkeypatch, 0)
    assert upload_cap.reserve_hold() is None
    assert upload_cap.reserve_hold(improve_one=True) is None


def test_逃げ道は残っている(monkeypatch):
    from src import quota_ledger as ql
    _patch(monkeypatch, int(ql.DAY_UNITS) + 1)
    monkeypatch.setenv("YT_NO_RESERVE", "1")
    assert upload_cap.reserve_hold() is None


def test_緩む幅は_IMPROVE_UNITS_ちょうど():
    """**「ついでにもう少し」を入れないこと。** 1本ぶん（50単位）だけです。"""
    assert upload_cap.IMPROVE_UNITS == 50
    assert 0 < upload_cap.IMPROVE_UNITS < upload_cap.RESERVE_UNITS


def test_束には渡していない():
    """`--missing`（全本）の道が `improve_one` を渡していないこと。"""
    src = (ROOT / "scripts" / "refresh_thumbnail.py").read_text(encoding="utf-8")
    assert "_improve_one = False" in src
    assert "if only_video and not only_long:" in src, (
        "**1本だけの道でしか立てないこと**（束に渡すと 158本 ＝ 7,900単位）")
    assert "reserve_hold(improve_one=_improve_one)" in src
