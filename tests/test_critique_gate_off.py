"""**外した検査が、黙って戻ってこないようにする**（2026-08-21）。

`config/hypotheses.yaml`「独立したエージェントの評価スコアは、engaged 比率を
予測する」は 2026-08-21 に **falsified** で閉じました。実測は
`scripts/critique_record.py --check` の **順位相関 -0.27**（しきい値 +0.40）で、
**しきい値に届かないどころか符号が逆**です。

`next_if_false` の1つ目は「**ゲートを外す**」。外し方は
`scripts/critique_run.py` が `--anyway` 無しでは回らないこと、その1つだけです。

## なぜ検査にするか

**このリポジトリで「外した」ものが戻る道は2つ**あって、どちらも黙って通ります。

1. 文書だけ直して**道具を直し忘れる**（`critique_record.py` の冒頭に
   「較正期間なので生産を止めません」が残っていたのと同じ形。8/15 に踏んでいます）
2. 次に来た側が `OFF_REASON` を読まずに「待ち行列が310本ある」を見て回し始める
   —— **1本あたり `claude -p` が3体**。930回ぶんの費用が、予測しない点のために出ます

**覆る条件は残してあります**（`--anyway`）。外したのは「engaged を予測する」
であって「評価そのものが無意味」ではないので、**別の的に当て直す道は塞ぎません。**
その時はこの検査の期待値のほうを書き換えること。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

CLAIM = "独立したエージェントの評価スコアは、engaged 比率を予測する"


def _hypotheses() -> list[dict]:
    raw = yaml.safe_load((ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
    return raw["hypotheses"] if isinstance(raw, dict) else raw


def _entry() -> dict:
    for h in _hypotheses():
        if h.get("claim") == CLAIM:
            return h
    raise AssertionError(f"前提が見つかりません: {CLAIM}")


def test_前提は外れで閉じている():
    h = _entry()
    assert h.get("closed_on") == "2026-08-21", h.get("closed_on")
    assert h.get("outcome") == "falsified", h.get("outcome")
    assert "-0.27" in h.get("verdict", ""), "実測の順位相関が verdict に無い"


def test_道具は_anyway_無しでは回らない():
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "critique_run.py"), "--next"],
        capture_output=True, text=True, timeout=120,
    )
    assert r.returncode == 2, f"rc={r.returncode}\n{r.stdout}\n{r.stderr}"
    assert "外れました" in r.stdout
    assert "--anyway" in r.stdout


def test_外した理由に覆る条件が書いてある():
    src = (ROOT / "scripts" / "critique_run.py").read_text(encoding="utf-8")
    assert "覆る条件" in src, "**外した理由だけ書いて、戻し方を書かないこと**を防ぐ"


def test_待ちに答えが入っている():
    raw = yaml.safe_load((ROOT / "config" / "watches.yaml").read_text(encoding="utf-8"))
    watches = raw["watches"] if isinstance(raw, dict) else raw
    by_id = {w["id"]: w for w in watches}
    for wid in ("独立評価-6本", "冒頭の問い-両群16本"):
        assert by_id[wid].get("answered"), f"{wid} に answered がありません"
