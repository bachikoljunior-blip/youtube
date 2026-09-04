"""**死んだ物差しの上の 0 を、「測って 0」と出さないこと。**

2026-09-05 未明・最適化の回。実測で名指しした欠陥:

    `data/runs.jsonl` の `gate1p_days` は 29件すべて 511.538（3.5時間）＝
    `moves_measured` は **定数から定数を引いた 0.0**。それを `optimized.py` が
    「動かず 28件・合計 +0.0日」と出し、`eta.py` の頭は `--moves`（回の宣言）を
    **「直近5日の実測」**と印字していました。**どちらも測定に読めます。**

この検査が守るのは3つ:

    1. `ruler()` が「1度も動いていない」を `frozen` として名指しすること
    2. 刻みあたりの ship が多すぎる物差しを `too_coarse` として落とすこと
    3. `headline()` が、使えない物差しのとき**歩留りを「宣言」と言い直す**こと

**覆る条件**: `ruler()['usable']` が True になったら（＝ 物差しが ship の粒に
追いついたら）、`measure()` の分子を `--moves` から `moves_measured` へ移すこと。
そのときは、この検査ではなく `measure()` の側を書き換えます。
"""
from __future__ import annotations

import json

from src import kind_yield


def _write(tmp_path, rows, monkeypatch):
    d = tmp_path / "data"
    d.mkdir(parents=True, exist_ok=True)
    (d / "runs.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8")
    monkeypatch.setattr(kind_yield, "ROOT", tmp_path)


def _ship(at, kind="fix", **kw):
    r = {"at": at, "ship_kind": kind, "moves": 0}
    r.update(kw)
    return r


def _today(h, m=0):
    from datetime import datetime

    now = datetime.now(kind_yield.JST)
    return now.replace(hour=h, minute=m, second=0, microsecond=0).isoformat()


def test_1度も動かない物差しはfrozenで名指しされる(tmp_path, monkeypatch):
    rows = [_ship(_today(1, i), gate1p_days=511.538) for i in range(0, 30, 2)]
    _write(tmp_path, rows, monkeypatch)
    rl = kind_yield.ruler()
    assert rl["n"] == 15
    assert rl["distinct"] == 1
    assert rl["frozen"] is True
    assert rl["usable"] is False
    assert "1度も動いていません" in rl["note"]


def test_刻みあたりのshipが多すぎる物差しはtoo_coarse(tmp_path, monkeypatch):
    # 20本 の ship に対して刻みは1回だけ ＝ 20本/刻み。
    rows = [_ship(_today(1, i), gate1p_days=(500.0 if i < 20 else 499.0))
            for i in range(0, 40, 2)]
    _write(tmp_path, rows, monkeypatch)
    rl = kind_yield.ruler()
    assert rl["frozen"] is False
    assert rl["too_coarse"] is True
    assert rl["usable"] is False
    assert rl["ships_per_tick"] > kind_yield.RULER_SHIPS_PER_TICK_MAX


def test_1本ずつ動く物差しはusable(tmp_path, monkeypatch):
    rows = [_ship(_today(1, i), gate1p_days=500.0 - i) for i in range(0, 20, 2)]
    _write(tmp_path, rows, monkeypatch)
    rl = kind_yield.ruler()
    assert rl["frozen"] is False
    assert rl["too_coarse"] is False
    assert rl["usable"] is True


def test_標本が足りなければ動いていないと言わない(tmp_path, monkeypatch):
    _write(tmp_path, [_ship(_today(1), gate1p_days=511.5)], monkeypatch)
    rl = kind_yield.ruler()
    assert rl["frozen"] is False
    assert rl["usable"] is False
    assert "まだ測れません" in rl["note"]


def test_headlineは使えない物差しのとき歩留りを宣言と言い直す(tmp_path, monkeypatch):
    rows = [_ship(_today(1, i), kind="verdict" if i < 10 else "fix",
                  moves=(-1 if i < 6 else 0), gate1p_days=511.538)
            for i in range(0, 40, 2)]
    _write(tmp_path, rows, monkeypatch)
    line = kind_yield.headline()
    assert line is not None
    # 「実測」と言い切らないこと（宣言だから）
    assert "**申告**" in line
    assert "回が自分で打った数で、差し引きではありません" in line
    # 物差しの状態が、名指しの隣に必ず出ること
    assert "差し引きは、まだ採点に使えません" in line


def test_measureは物差しの状態を持って返す(tmp_path, monkeypatch):
    rows = [_ship(_today(1, i), gate1p_days=511.538) for i in range(0, 20, 2)]
    _write(tmp_path, rows, monkeypatch)
    m = kind_yield.measure()
    assert "ruler" in m
    assert m["ruler"]["field"] == kind_yield.RULER_FIELD
    assert m["ruler"]["usable"] is False


def test_安い入口が在る():
    """**名指しの出口が `eta.py`（数分・API を叩く）だけに戻らないこと。**

    実測 2026-09-05: `eta.py` は 120秒 で 1文字も出しませんでした。
    `python -m src.kind_yield` は API 0単位・1秒 未満です。
    """
    src = (kind_yield.ROOT / "src" / "kind_yield.py").read_text(encoding="utf-8")
    assert '__name__ == "__main__"' in src
    assert "print(headline()" in src
