"""**`FIX_RUN_CAP` の「覆る条件 4」を、撃てる形のまま保つこと。**（2026-09-02）

## なぜ要るか（この回に撃って出た数）

`scripts/run_marker.py` の `fix_share()` は、こういう理由で作られました ——

> `FIX_RUN_CAP` の「覆る条件 1」は「`fix` 比が下がらないまま `fix_gate` の行だけが
> 増えたら作り直せ」と書いてありました。**その比を出す道具が、どこにもありませんでした。**
> …**覆る条件は、撃てる形で置かないと、書いてあっても発火しません。**

**その教訓が、同じ註の「覆る条件 4」には当たっていませんでした。**
4 は散文のまま残り、**2026-09-02 に手で数えたら、既に立っていました**::

    verdict+premise 比   門の前 7.8%（257件） → 門の後 30.6%（49件）
    fix 比               74.7% → 61.2%
    lever_followed       18.3% → 53.1%
    traj_days            08-30 135.7日 → 08-31 以降 **出ません**

**＝ 門は効いた。効いても到達日は動かない。だから律速は `fix` ではありません。**

この検査が守るのは「4 を、次の回が手で数え直さずに済むこと」です。

## この検査が落ちる条件（＝ **直し方**）

- `cond4()` が消えた／名前が変わった → **散文へ戻っています。** 戻さないこと
- `MOVING_KINDS` に、軌跡の入力に入らない種別が足された →
  分子だけ増えて**必ず立つ**判定になります。足す前に `eta.py --reflect` の
  「前 → 後」が動くかを確かめること
- `traj_days` が読めないのに `fired` が真になった →
  **「測れない」を「立っている」と読ませないこと**（`cond4()` の覆る条件2）
- `10^9`（＝「出ません」）が生の桁で刷られた → 読んだ側が「27万年」と読みます
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import run_marker as rm  # noqa: E402

GATE = "2026-09-01T10:45"


def _marks(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "runs.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return p


def _eta(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "eta.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return p


def _ships(at: str, kinds: list[str]) -> list[dict]:
    return [{"at": at, "kind": "ship", "ship_kind": k} for k in kinds]


def test_動かしうる種別が増えて到達日が動かないと立つ(tmp_path):
    """**この repo の、いまの実物の形**（2026-09-02）。"""
    marks = _marks(tmp_path,
                   _ships("2026-08-30T00:00", ["fix"] * 30)
                   + _ships("2026-09-01T12:00", ["verdict"] * 10 + ["fix"] * 15))
    eta = _eta(tmp_path, [{"at": "2026-08-30T00:00", "traj_days": 135.7},
                          {"at": "2026-09-02T00:00", "traj_days": 1e9}])
    r = rm.cond4(path=marks, eta_path=eta, since=GATE)
    assert r["fired"] is True, r
    assert r["before"]["share"] == 0.0
    assert r["after"]["share"] > 0.0


def test_到達日が近づいていれば立たない(tmp_path):
    """**効いている門を、この判定で外させないこと。**"""
    marks = _marks(tmp_path,
                   _ships("2026-08-30T00:00", ["fix"] * 30)
                   + _ships("2026-09-01T12:00", ["verdict"] * 10 + ["fix"] * 15))
    eta = _eta(tmp_path, [{"at": "2026-08-30T00:00", "traj_days": 140.0},
                          {"at": "2026-09-02T00:00", "traj_days": 100.0}])
    assert rm.cond4(path=marks, eta_path=eta, since=GATE)["fired"] is False


def test_動かしうる種別が増えていなければ立たない(tmp_path):
    """**「日付が動かない」だけでは 4 ではありません** —— 4 は
    「**動かしうる側に振ったのに**動かない」です。振っていない回で立てると、
    `fix` が律速のときにも「律速ではない」と言ってしまいます。
    """
    marks = _marks(tmp_path,
                   _ships("2026-08-30T00:00", ["verdict"] * 30)
                   + _ships("2026-09-01T12:00", ["fix"] * 25))
    eta = _eta(tmp_path, [{"at": "2026-08-30T00:00", "traj_days": 135.7},
                          {"at": "2026-09-02T00:00", "traj_days": 1e9}])
    assert rm.cond4(path=marks, eta_path=eta, since=GATE)["fired"] is False


def test_到達日が読めなければ立たない(tmp_path):
    """**「測れない」を「立っている」と読ませないこと**（`cond4()` の覆る条件2）。"""
    marks = _marks(tmp_path,
                   _ships("2026-08-30T00:00", ["fix"] * 30)
                   + _ships("2026-09-01T12:00", ["verdict"] * 10 + ["fix"] * 15))
    eta = _eta(tmp_path, [{"at": "2026-08-30T00:00"}, {"at": "2026-09-02T00:00"}])
    r = rm.cond4(path=marks, eta_path=eta, since=GATE)
    assert r["fired"] is False
    assert r["moved"] is None
    assert "判定できません" in r["why"]


def test_標本が小さいうちは立たない(tmp_path):
    """`fix_share()` と同じ 20件 の床。**数回で門を壊させないこと。**"""
    marks = _marks(tmp_path,
                   _ships("2026-08-30T00:00", ["fix"] * 30)
                   + _ships("2026-09-01T12:00", ["verdict"] * 3))
    eta = _eta(tmp_path, [{"at": "2026-08-30T00:00", "traj_days": 135.7},
                          {"at": "2026-09-02T00:00", "traj_days": 1e9}])
    assert rm.cond4(path=marks, eta_path=eta, since=GATE)["fired"] is False


def test_出ませんを生の桁で刷らない(tmp_path):
    """**`10^9` を「1000000000.0日」と出さないこと** —— 読んだ側が年数に読み替えます。"""
    marks = _marks(tmp_path,
                   _ships("2026-08-30T00:00", ["fix"] * 30)
                   + _ships("2026-09-01T12:00", ["verdict"] * 10 + ["fix"] * 15))
    eta = _eta(tmp_path, [{"at": "2026-08-30T00:00", "traj_days": 1e9},
                          {"at": "2026-09-02T00:00", "traj_days": 1e9}])
    why = rm.cond4(path=marks, eta_path=eta, since=GATE)["why"]
    assert "1000000000" not in why, why
    assert "出ません" in why


def test_動かしうる種別は軌跡の入力に入るものだけ():
    """**`upload` / `improve` / `means` を足さないこと。**

    `eta.py` は毎周「**作る・出す・直すは、軌跡の入力に入りません**」と印字します。
    入らない種別を `MOVING_KINDS` に足すと、分子だけが増えて
    **この判定は必ず立ちます**（＝ 門を無条件に外す道になります）。
    """
    assert set(rm.MOVING_KINDS) == {"verdict", "premise"}, rm.MOVING_KINDS
    for k in rm.MOVING_KINDS:
        assert k in rm.SHIP_KINDS, f"{k} は `--kind` として受け付けられません"


def test_門が止めた回に覆る条件4も見せている():
    """**その場で見せないと、誰も判定しません**（`fix_share()` が作られた理由）。"""
    src = (ROOT / "scripts" / "run_marker.py").read_text(encoding="utf-8")
    assert "cond4_line()" in src, "門の本文から `cond4_line()` が消えています"
    i = src.rindex("fix_share_line()")
    assert "cond4_line()" in src[i:i + 800], "`fix_share_line()` の隣に出ていません"


def test_実物で撃てる():
    """**この repo の実物で落ちないこと**（`data/` が無い回でも回を止めない）。"""
    r = rm.cond4()
    assert isinstance(r["fired"], bool)
    line = rm.cond4_line()
    assert "verdict" in line and "1000000000" not in line


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
