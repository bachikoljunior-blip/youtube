"""`src/kind_yield.py` —— **種別（ship_kind）べつの歩留り**の検査。

**何を守っているか**: 2026-09-04 昼の最適化の回で、`lever_followed=True` の
118回 のうち 115回（97%）が `moves` 0 で、うち 70回 が `CLAUDE.md` の言う
「定義上 0日」の種別だと実測しました。**腕の名指しだけでは、日付が動かない回が
合格します。** この module はその掛け合わせを出す唯一の場所なので、
**数え方が壊れたら、`eta.py` の頭の行が静かに嘘になります。**
"""
from __future__ import annotations

import json

from src import kind_yield


def _write(tmp_path, rows):
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    p = tmp_path / "data" / "runs.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                 encoding="utf-8")
    return p


def _patch_root(monkeypatch, tmp_path):
    monkeypatch.setattr(kind_yield, "ROOT", tmp_path)


def _row(at, kind, moves, followed=None):
    r = {"at": at, "ship_kind": kind, "moves": moves}
    if followed is not None:
        r["lever_followed"] = followed
    return r


def test_歩留りは種別ごとに数える(monkeypatch, tmp_path):
    import datetime as _dt
    today = _dt.datetime.now(kind_yield.JST).date().isoformat()
    _write(tmp_path, [
        _row(f"{today}T01:00:00+09:00", "verdict", -1, True),
        _row(f"{today}T02:00:00+09:00", "verdict", 0, True),
        _row(f"{today}T03:00:00+09:00", "fix", 0, True),
        _row(f"{today}T04:00:00+09:00", "fix", 0, False),
    ])
    _patch_root(monkeypatch, tmp_path)
    m = kind_yield.measure()
    assert m["n"] == 4
    assert m["by_kind"]["verdict"] == {"n": 2, "moved": 1, "rate": 0.5}
    assert m["by_kind"]["fix"]["moved"] == 0
    # **腕に従った印は、動かなかった回でも立ちます。**ここが検査の眼目。
    assert m["followed_n"] == 3
    assert m["followed_zero"] == 2
    assert m["followed_by_definition_zero"] == 1


def test_数が足りないうちは種別を名指ししない(monkeypatch, tmp_path):
    """`significant` の門（verdict が 5回・3件 以上）を割ったら名乗らないこと。"""
    import datetime as _dt
    today = _dt.datetime.now(kind_yield.JST).date().isoformat()
    _write(tmp_path, [_row(f"{today}T0{i}:00:00+09:00", "verdict", -1) for i in range(1, 4)])
    _patch_root(monkeypatch, tmp_path)
    m = kind_yield.measure()
    assert m["significant"] is False
    assert "名乗れません" in kind_yield.headline()


def test_台帳が空なら供給のほうを名指しする(monkeypatch, tmp_path):
    import datetime as _dt
    today = _dt.datetime.now(kind_yield.JST).date().isoformat()
    _write(tmp_path, [_row(f"{today}T0{i}:00:00+09:00", "verdict", -1) for i in range(1, 7)])
    _patch_root(monkeypatch, tmp_path)
    monkeypatch.setattr(kind_yield, "_ledger_open", lambda: 0)
    line = kind_yield.headline()
    assert "`premise`" in line and "台帳が空" in line


def test_実物でも落ちない():
    """本物の `data/runs.jsonl` で例外を出さないこと（`eta.py` が毎回呼びます）。"""
    m = kind_yield.measure()
    assert isinstance(m["n"], int)
    h = kind_yield.headline()
    assert h is None or isinstance(h, str)
