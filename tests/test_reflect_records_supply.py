"""**反映の前に、在庫の点が積まれること。**（2026-08-26 07:4x に実測して足した）

`eta.py --reflect` の「この回で動いた入力」は、在庫（`stock`）と作る速さ
（`make_rate_per_day`）を **`data/supply.jsonl` の点の差**からしか出しません。
点を積むのは `python -m src.supply --record` だけで、**`topic_forge` も
`batch_build` も積みません。**

だから、テーマを6件 forge して長尺を4本 予約した回が `--ship` を打つと

    [!] **この回で動かせる入力は、1つもありませんでした。**

と出ます。**その印字は「この回が予測の入力に触っていない」と言っており、
在庫を触った回では嘘になります。** 同じ回で `supply --record` を撃ってから
`--reflect` をもう一度撃つと、**同じ作業のまま2件**出ました
（`density_surfaces` と `make_rate_per_day` 18.2 → 19.3）。

**故障注入つき**（`_record_supply` を外すと落ちる側も見る。
片側だけでは「効いている」と言えません）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import run_marker  # noqa: E402


def test_reflect_は在庫の点を先に積む(monkeypatch):
    """`_reflect_now` が `_record_supply` を、`eta.py --reflect` より**先に**呼ぶ。"""
    order: list[str] = []

    monkeypatch.delenv(run_marker.SKIP_REFLECT_ENV, raising=False)
    monkeypatch.setattr(run_marker, "_record_supply",
                        lambda: order.append("supply"))

    class _Done:
        returncode = 0
        stdout = "=== この回の反映 ===\n"
        stderr = ""

    def fake_run(cmd, **kw):
        order.append("reflect:" + " ".join(str(c) for c in cmd[-3:]))
        return _Done()

    import subprocess
    monkeypatch.setattr(subprocess, "run", fake_run)

    run_marker._reflect_now("upload: 長尺4本")

    assert order, "反映も在庫の点も呼ばれていません"
    assert order[0] == "supply", (
        f"在庫の点が反映より先に積まれていません: {order}。"
        "**順番が本体です** —— 後で積んでも、その回の反映には入りません")
    assert any(o.startswith("reflect:") for o in order), \
        f"反映そのものが呼ばれていません: {order}"


def test_在庫の点を積まないと順番の検査が落ちる(monkeypatch):
    """**故障注入。** `_record_supply` を no-op に差し替えたら、上の検査は落ちる。"""
    order: list[str] = []

    monkeypatch.delenv(run_marker.SKIP_REFLECT_ENV, raising=False)
    monkeypatch.setattr(run_marker, "_record_supply", lambda: None)   # ← 外す

    class _Done:
        returncode = 0
        stdout = ""
        stderr = ""

    import subprocess
    monkeypatch.setattr(subprocess, "run",
                        lambda cmd, **kw: (order.append("reflect"), _Done())[1])

    run_marker._reflect_now("upload: 長尺4本")

    assert order == ["reflect"], (
        "故障注入したのに在庫の点が積まれています。"
        "上の検査が本当に順番を見ているか、確かめ直すこと")


def test_record_supply_は回を止めない(monkeypatch, capsys):
    """積めなくても例外を投げない（**記録であって門ではない**）。"""
    import subprocess

    def boom(cmd, **kw):
        raise OSError("no such file")

    monkeypatch.setattr(subprocess, "run", boom)
    run_marker._record_supply()                 # 例外が出ないこと
    out = capsys.readouterr().out
    assert "回は止めません" in out, out


def test_record_supply_は終了コードを見る(monkeypatch, capsys):
    """`--record` が非ゼロで返っても、そのまま「積みました」と言わない。"""
    import subprocess

    class _Failed:
        returncode = 2
        stdout = ""
        stderr = "boom"

    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: _Failed())
    run_marker._record_supply()
    out = capsys.readouterr().out
    assert "積みました" not in out, out
    assert "積めませんでした" in out, out


def test_supply_record_の口が実在する():
    """`python -m src.supply --record` の口が消えていないこと。"""
    from src import supply

    src = Path(supply.__file__).read_text(encoding="utf-8")
    assert '"--record"' in src or "'--record'" in src, \
        "`src/supply.py` から `--record` が消えています。" \
        "`run_marker._record_supply` の呼び先ごと見直すこと"


@pytest.mark.parametrize("env", ["1", "yes"])
def test_skip_reflect_のときは在庫も積まない(monkeypatch, env):
    """`YT_SKIP_REFLECT` の回では、在庫の点も積まない（検査の中で書かないため）。"""
    called: list[str] = []
    monkeypatch.setenv(run_marker.SKIP_REFLECT_ENV, env)
    monkeypatch.setattr(run_marker, "_record_supply",
                        lambda: called.append("supply"))
    run_marker._reflect_now("x")
    assert called == [], f"飛ばす回なのに在庫の点を積んでいます: {called}"
