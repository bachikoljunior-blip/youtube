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


def test_周の頭では撃たれていない():
    """**2026-09-06 に反転した。** それまでは「COUNT の枝より前に置くこと」だった。

    手法は 09/05 に `studio/` でゼロから組み直し（`docs/METHOD.md` §8）、`run_marker` の門も
    `daily_pick` の決めも、いまの回は撃たない。**親が毎周 撃つ `next_round.py` が旧道具の判定を
    印字し続けていた**（09/06 17:02 JST の実測: private に戻した旧作りの本を「枠はもう決まっています」
    と出していた）。関数 `kinds_allowed()` は残すが、`main()` からは呼ばない。
    **覆る条件**: METHOD に旧道具を使う判断が書かれたとき。
    """
    src = (ROOT / "scripts" / "next_round.py").read_text()
    main = src.split("def main()")[1]
    assert "kinds_allowed()" not in main, "旧道具の下読みが親の周の頭に戻っています"
    assert "from src import slot_cost" not in main, "旧道具（slot_cost）の読み出しが親の周に戻っています"
    assert "from src import daily_pick" not in main, "旧道具（daily_pick）の読み出しが親の周に戻っています"


def test_下読みは門と食い違わない():
    """**この検査は、実際に踏んだ食い違いから来ています**（2026-09-04 23:5x）。

    最初の版は台帳が空の日に「**門は立ちません**」と印字しました。
    **その回の `--ship` が、自分の印字どおりに撃って止められました** ——
    免除は 09-04 19:xx に `dry_ledger_gate` で**枠の本を名乗る `fix` だけ**へ
    絞られており、下読みはその関数を読んでいませんでした。

    **下読みが「通る」と言った日に門が止めたら、下読みは害です**
    （周の頭で嘘を渡すぶん、終わりで止める門より悪い）。ここで縛ります。
    """
    import run_marker as rm

    got = next_round.kinds_allowed()
    slot = rm.untreated_slot()
    over = (rm.fix_run_len() >= rm.FIX_RUN_CAP
            or rm.fix_since_move() >= rm.FIX_SINCE_MOVE_CAP)
    ready = rm.judgeable_today()
    # 門の側の答え（本文を名乗らない `fix` ＝ 空の `--ship`）
    gate_trips = slot["fired"] or (over and bool(ready)) or (
        over and rm.dry_ledger_gate("", ready, slot, over)["trip"])
    said_blocked = "fix" in got["blocked"]
    assert said_blocked == bool(gate_trips), (
        f"下読み（fix 止め={said_blocked}）と門（止め={gate_trips}）が食い違っています")


def test_止まるなら枠の本を名指しする():
    """止めるなら、**通る手**を必ず名指しすること（出口を塞がない門にしない）。"""
    got = next_round.kinds_allowed()
    if "fix" in got["blocked"]:
        body = "\n".join(got["lines"])
        import run_marker as rm
        slot = rm.untreated_slot()
        tgt = slot.get("video_id") or slot.get("topic")
        if tgt:
            assert tgt in body, f"止めたのに枠の本 {tgt} を名指ししていません"
