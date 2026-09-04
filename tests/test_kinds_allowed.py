"""**周の頭で種別の下読みが出ること**（2026-09-04 深夜・最適化の回）。

`run_marker.py` の `fix` の門は 09-01 から在り、4日 締め直しても
`fix` の比は 78% → 60% で止まりました。**実測した理由は置き場所です** ——
門は `--ship`（周の終わり）に立っているので、着いた時点で周の時間は
もう使い切っており、残る道は「免除する／言い換えて通す／周を捨てる」の3つ。
`data/runs.jsonl` の実測は **免除 50回・言い換えて +6分 で再 ship 12回・
周を捨てた 0回**（発火 106回 のうち 58% が何も変えていない）。

**だから同じ述語を、周の頭（`next_round.py`）でも出します。**
この検査が守るのは「頭で出ること」だけで、門の定数には触れません。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import next_round  # noqa: E402


def test_下読みは行を返す():
    got = next_round.kinds_allowed()
    assert isinstance(got, dict)
    assert got["lines"], "種別の下読みが1行も出ていません"
    head = got["lines"][0]
    # 4つの述語が全部 頭の行に出ること（どれが欠けても、周は何を選べるか分からない）
    for word in ("fix", "連", "判定できる前提", "枠の本"):
        assert word in head, f"下読みの頭に {word} が出ていません: {head}"


def test_止まる仕掛けではない():
    """**例外を外へ出さないこと。** 止める仕掛けを足さない（`tests/test_pause_needs_owner.py` と同じ趣旨）。"""
    got = next_round.kinds_allowed()
    assert set(got) >= {"lines", "blocked", "ok"}
    assert isinstance(got["blocked"], list)
    # `ok` が False でも、返るのは行だけ ＝ 呼び手は進める
    assert got["ok"] in (True, False)


def test_門と同じ述語を読んでいる():
    """**写しを持たないこと。** 下読みは `run_marker` の述語をそのまま呼ぶ。"""
    src = (ROOT / "scripts" / "next_round.py").read_text()
    body = src.split("def kinds_allowed")[1].split("\ndef ")[0]
    for name in ("untreated_slot", "fix_run_len", "fix_since_move", "judgeable_today"):
        assert name in body, f"{name} を呼んでいません（定数や閾値を写さないこと）"
    # 定数も写さない
    assert "FIX_RUN_CAP" in body and "getattr" in body


def test_周の頭で撃たれている():
    """**COUNT の枝より前に置くこと** —— 親は COUNT で撃ち直すので、
    後ろに置くと「数を渡した回」しか読めません。"""
    src = (ROOT / "scripts" / "next_round.py").read_text()
    main = src.split("def main()")[1]
    call = main.index("kinds_allowed()")
    count = main.index('print("COUNT")')
    assert call < count, "種別の下読みが COUNT の枝より後ろに落ちています"
