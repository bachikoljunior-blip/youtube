"""**`verdict` の門が、`improve` への逃げ道を塞いでいることを見る。**

## なぜ要るか（2026-09-04・最適化の回に実測して作った）

`FIX_RUN_CAP`（2026-09-01）は効きました —— `fix` の比は 08-31 **80.0%** から
09-02 以降 **59〜62%** へ落ちています（`data/runs.jsonl`）。
**それでも到達日は動いていません**（再生/日 7日: 1,941 → 1,746 → 1,344）。

押し出された回がどこへ行ったかを数えると、理由が出ます:

    09-01  fix 78  improve  5  premise 7  verdict 6
    09-03  fix 33  improve 12  premise 5  verdict **0**
    09-04  fix  8  improve  4  premise 0  verdict **0**

**`improve` へ流れ、`verdict` へは1件も流れていません。**
`FIX_RUN_CAP` が止めるのは `fix` だけで、そのエラー本文は自分で
**「`improve` は、いつでも在ります」**と逃げ道を案内していました。
`eta.py` の模型では **`verdict` 以外は定義上 0日** なので、
`fix` を `improve` に替えるのは 0日 の名前を替えただけです。

非 `verdict` の連は実測 中央値 4・p75 **14**・過去の最大 38 に対し、
**いまの連は 81**（過去の最大の 2.1倍）。しきいは p75 に置いています。

この検査が見ているのは3つだけです:

1. **`upload` は必ず通ること** —— オーナーが固定した 1日1本 は聖域で、
   **出す手を止める門は作らない。** ここが赤くなったら門を消すこと。
2. **`verdict` 自身は必ず通ること**（門の出口を門が塞いだら永久に閉まります）。
3. **閉じられる前提が無い日は、連がいくら長くても通ること** ——
   `verdict` は在庫が無ければ撃てない種別なので、連だけで止めると
   「閉じる物が無い回」を止めます。09-03 の `verdict` 0件 は**正しい**
   （判定できる日は 09-04 でした）。

**覆る条件**: `eta.py` が「腕が動くのは前提を閉じたときだけ」を撤回したら、
この門の前提そのものが消えます。そのときは門ごと畳んでよい。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import run_marker  # noqa: E402


def _marks(tmp_path, kinds):
    """`ship_kind` を並べた `runs.jsonl` を作る（新しいものが下）。"""
    p = tmp_path / "runs.jsonl"
    p.write_text("\n".join(
        json.dumps({"at": "2026-09-04T00:00:00+09:00", "kind": "ship", "ship_kind": k})
        for k in kinds) + "\n", encoding="utf-8")
    return p


def test_verdict_run_len_counts_until_the_last_verdict(tmp_path):
    """末尾から `verdict` に当たるまでを数えること。"""
    p = _marks(tmp_path, ["fix", "verdict", "fix", "improve", "premise"])
    assert run_marker.verdict_run_len(p) == 3


def test_verdict_run_len_ignores_non_ship_rows(tmp_path):
    """`--write` の印や門の記録は数に入れないこと（`fix_run_len()` と同じ約束）。"""
    p = tmp_path / "runs.jsonl"
    p.write_text(
        json.dumps({"kind": "ship", "ship_kind": "verdict"}) + "\n"
        + json.dumps({"kind": "verdict_gate", "run_len": 99}) + "\n"
        + json.dumps({"kind": "ship", "ship_kind": "fix"}) + "\n", encoding="utf-8")
    assert run_marker.verdict_run_len(p) == 1


def _run_cli(monkeypatch, kind, judgeable, run_len=99):
    """門だけを撃つ。**台帳には書きません**（`ship()` を差し替えます）。"""
    monkeypatch.setattr(run_marker, "judgeable_now", lambda: judgeable)
    monkeypatch.setattr(run_marker, "verdict_run_len", lambda *a, **k: run_len)
    # 上流の `fix` の門とは別物であることを見るため、`fix` の連は 0 に固定
    monkeypatch.setattr(run_marker, "fix_run_len", lambda *a, **k: 0)
    seen = {}

    def _fake_ship(*a, **k):
        seen["passed"] = True
        return 0

    monkeypatch.setattr(run_marker, "ship", _fake_ship)
    monkeypatch.setattr(sys, "argv", [
        "run_marker.py", "--ship", "検査", "--kind", kind,
        "--lever", "per_video", "--moves", "0"])
    try:
        run_marker.main()
    except SystemExit as e:            # ap.error() は SystemExit(2)
        if e.code not in (0, None):
            return False
    return bool(seen.get("passed"))


DUE = {"days": 0, "on": "2026-09-04", "open": 35, "source": "deadline",
       "claims": ["検査用の前提"], "claim_levers": {"検査用の前提": "per_video"}}


def test_upload_always_passes(monkeypatch):
    """**オーナーが固定した 1日1本 は聖域** —— 出す手を止める門は作らない。"""
    assert _run_cli(monkeypatch, "upload", DUE) is True


def test_verdict_itself_always_passes(monkeypatch):
    """門の出口を門が塞いだら、永久に閉まります。"""
    assert _run_cli(monkeypatch, "verdict", DUE) is True


def test_improve_is_blocked_when_a_claim_is_judgeable(monkeypatch):
    """**逃げ道はここで塞ぎます**（`FIX_RUN_CAP` が案内していた先）。"""
    assert _run_cli(monkeypatch, "improve", DUE) is False


def test_improve_passes_when_nothing_is_judgeable(monkeypatch):
    """閉じる物が無い日は、連がいくら長くても通ること。"""
    assert _run_cli(monkeypatch, "improve", {}, run_len=999) is True


def test_improve_passes_below_the_cap(monkeypatch):
    """p75 の下は触らないこと（過去の連の 75% はこの門に当たりません）。"""
    assert _run_cli(monkeypatch, "improve", DUE,
                    run_len=run_marker.VERDICT_RUN_CAP - 1) is True
