"""**`premise` の回に `opened_on:` を書かせる門**（2026-09-04・最適化の回）。

なぜ要るか（実測）: `deadline_check --fit` は「立てた速さ」を `opened_on:` から、
「閉じた速さ」を `closed_on:` から数えます。前者の被覆は 22%、後者はほぼ 100% で、
引き算の差は**必ず負**に出ていました —— 09-04 の印字は「注ぎ口より漏れのほうが
速い／台帳は 09-16 に空になる」でしたが、同じ台帳の開き数は 21→33件 と**増えて**
いました。**偽の警報が、回の入力になっていました。**

ここが押さえるのは2つだけ:

1. 被覆が薄く、きょうの `opened_on:` が無いとき、`premise` の門が閉じること。
2. きょうの `opened_on:` が1件あれば開くこと（＝門は次の回へ持ち越さない）。
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import run_marker  # noqa: E402


def _yaml(tmp_path: Path, rows: list[dict]) -> Path:
    import yaml
    p = tmp_path / "hypotheses.yaml"
    p.write_text(yaml.safe_dump({"hypotheses": rows}, allow_unicode=True),
                 encoding="utf-8")
    return p


@pytest.fixture()
def _at(monkeypatch, tmp_path):
    """`premise_opened_today()` が読む台帳を、この検査のものに差し替える。"""
    def _install(rows: list[dict]) -> None:
        p = _yaml(tmp_path, rows)
        real = Path.read_text

        def fake(self, *a, **k):
            if self.name == "hypotheses.yaml":
                return real(p, *a, **k)
            return real(self, *a, **k)
        monkeypatch.setattr(Path, "read_text", fake)
    return _install


def _today() -> str:
    return datetime.now(run_marker.JST).date().isoformat()


def test_thin_cover_and_no_opened_today_closes_the_gate(_at):
    """**被覆が薄く、きょうの欄が無い** → 門が閉じる（`today` が 0）。"""
    _at([{"claim": "a"}, {"claim": "b"}, {"claim": "c"},
         {"claim": "d", "opened_on": "2026-09-01"}])
    r = run_marker.premise_opened_today()
    assert r["today"] == 0
    assert r["cover"] < run_marker.PREMISE_COVER_MIN


def test_opened_today_opens_the_gate(_at):
    """**きょうの `opened_on:` が1件** → 開く。門は次の回へ持ち越しません。"""
    _at([{"claim": "a"}, {"claim": "b"}, {"claim": "c"},
         {"claim": "d", "opened_on": _today()}])
    assert run_marker.premise_opened_today()["today"] == 1


def test_full_cover_opens_the_gate_even_without_today(_at):
    """**覆る条件**: 被覆が `PREMISE_COVER_MIN` を超えたら、門は仕事を終えています。"""
    _at([{"claim": "a", "opened_on": "2026-09-01"},
         {"claim": "b", "opened_on": "2026-09-02"},
         {"claim": "c", "opened_on": "2026-09-02"},
         {"claim": "d", "opened_on": "2026-09-03"}])
    r = run_marker.premise_opened_today()
    assert r["cover"] >= run_marker.PREMISE_COVER_MIN


def test_unreadable_ledger_opens_the_gate(monkeypatch):
    """**読めない道具で回を止めないこと** —— 読めなければ空を返して通す。"""
    def boom(self, *a, **k):
        raise OSError("no")
    monkeypatch.setattr(Path, "read_text", boom)
    assert run_marker.premise_opened_today() == {}


def test_cover_min_matches_deadline_check():
    """2つの門の数は、同じ数であること（片方だけ動かすと矛盾した案内が出ます）。"""
    import deadline_check
    assert run_marker.PREMISE_COVER_MIN == deadline_check._OPEN_COVER_MIN
