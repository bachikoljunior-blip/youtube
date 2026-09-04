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


# ---------------------------------------------------------------------------
# 2026-09-05 未明・最適化の回に足した2件。
#
# **守っているもの1**: 採点に使えない窓（`significant` が False、または物差しが
# 使えない）で、`headline()` が**割合を印字しないこと**。09/05 01:48 の
# 「その日の1本」の決めは、この行の「43% 対 1.3%」を引用して、1日1枠の動画を
# 48h 見込み 1回 の長尺へ回しました。**名乗りを断りながら弾だけ配ると、
# 断ったことは効きません。**
#
# **守っているもの2**: 名指しされた腕（`eta.py` の `lever_hint`）と、実際に
# 働いた腕（`runs.jsonl` の `lever`）の隔たりが、`headline()` に出ること。
# 実測 2026-09-05: `rpm` は名指し 25% に対し働いたのは 3.2%（8倍）。
# ---------------------------------------------------------------------------


def _write_eta(tmp_path, rows):
    import json as _json
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    p = tmp_path / "data" / "eta.jsonl"
    p.write_text("\n".join(_json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                 encoding="utf-8")
    return p


def test_採点に使えない窓では割合を出さない(monkeypatch, tmp_path):
    import datetime as _dt
    today = _dt.datetime.now(kind_yield.JST).date().isoformat()
    # verdict が 5回中3回 動いた「ように見える」窓。物差し（gate1p_days）は無い。
    rows = [_row(f"{today}T0{i}:00:00+09:00", "verdict", -1 if i < 4 else 0, True)
            for i in range(1, 6)]
    rows += [_row(f"{today}T1{i}:00:00+09:00", "fix", 0, True) for i in range(0, 9)]
    _write(tmp_path, rows)
    _patch_root(monkeypatch, tmp_path)

    m = kind_yield.measure()
    assert not m["ruler"]["usable"], "物差しが無い窓では usable は False"
    line = kind_yield.headline()
    assert "割合は出しません" in line
    # **回数は隠しません。**数を伏せるのではなく、割合を作らないだけ。
    assert "verdict 5回 中 3回" in line
    assert "%" not in line.split("／**腕に届く種別へ行った回は")[0].split("直近")[1]


def test_名指しされた腕と働いた腕の隔たりが出る(monkeypatch, tmp_path):
    import datetime as _dt
    today = _dt.datetime.now(kind_yield.JST).date().isoformat()
    rows = []
    for i in range(10):
        r = _row(f"{today}T0{i}:00:00+09:00", "fix", 0, True)
        r["lever"] = "per_video"
        rows.append(r)
    _write(tmp_path, rows)
    # 名指しは半分が rpm。働いたのは 0回 ＝ 隔たりは ∞。
    _write_eta(tmp_path, [{"at": f"{today}T0{i}:30:00+09:00",
                           "lever_hint": "rpm" if i % 2 else "per_video"}
                          for i in range(10)])
    _patch_root(monkeypatch, tmp_path)

    a = kind_yield.arms()
    assert a["named"]["rpm"] == 5
    assert "rpm" not in a["worked"]
    assert a["gap"] == float("inf")
    assert "`rpm`" in kind_yield.headline()


def test_腕を選ばなかった回は働いた側の母数に入らない(monkeypatch, tmp_path):
    import datetime as _dt
    today = _dt.datetime.now(kind_yield.JST).date().isoformat()
    rows = []
    for i, lv in enumerate(["per_video", "none", None, "rpm"]):
        r = _row(f"{today}T0{i}:00:00+09:00", "fix", 0, True)
        if lv is not None:
            r["lever"] = lv
        rows.append(r)
    _write(tmp_path, rows)
    _patch_root(monkeypatch, tmp_path)
    a = kind_yield.arms()
    assert a["n_worked"] == 2 and a["unlevered"] == 2
