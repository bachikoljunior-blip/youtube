"""**`--sweep` が「置く先 0本」と言う回に、`eta.py` が「まだ N本 残っています」と言わないこと。**

## なぜ要るか（2026-09-05 03:2x に実測して足した）

同じ時刻に、同じ腕（`sub_rate`）について、2つの画面が正面から食い違っていました:

    scripts/eta.py       「ただし**上がっている本**に **1本** 残っています
                          （いまの再生/日 の 1% ＝ 0.8回/日）。`--sweep`（1本 50単位）」
    src.sub_ask --sweep  「読めた 23本 ／ 既に入っている 23本 ／ **置く先 0本**」

食い違っていた1本は `iwdNOasGYE4` で、**実物の説明欄には依頼が入っていました**。
根は2つ在り、どちらもこの検査が見ます。

1. **控えの穴** —— `apply_to_video()` が `SWEEP_LOG` に何も書きませんでした。
   `--sweep` だけが `_note_sweep()` を呼んでいたので、**`--apply` で覆った本**と
   **上げたときから入っていた本**は、控えの上では永久に「未覆」でした。
   `eta._sub_ask_uncovered()` は控えを唯一の根拠にしているので、
   そのぶんを毎周「まだ残っています」と刷り、回を**空の腕**へ送っていました。

2. **母集団の食い違い** —— eta は `rank_by_traffic()` の全部（実測 250本）を数え、
   `--sweep` は `sweep_targets()`（再生/日 0.5 以上・上位 40本 ＝ 実測 23本）しか
   相手にしません。**割合の分母も別物**でした。

**この検査が守るのは「2つの画面が同じ母集団を、同じ控えで数える」ことだけです。**
数そのもの（23本・0.5回/日・40本）は実物から動くので、ここには書きません。

## 覆る条件

説明欄を実物から読み直す口が立って `eta` がそれを見るようになったら、控えは
写しでなくなるので 1. は要らなくなります。`sub_ask.HEAD` を空にして依頼そのものを
畳んだときは、`sweep()` が 0単位 で戻るので、この file ごと消してよい。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src import sub_ask  # noqa: E402


def _eta():
    spec = importlib.util.spec_from_file_location("_eta_ledger", ROOT / "scripts" / "eta.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_apply_records_the_book_even_when_it_was_already_covered(tmp_path, monkeypatch):
    """**「既に入っています」で戻る道でも控えへ書くこと** —— 1. の穴。"""
    log = tmp_path / "sweep.jsonl"
    monkeypatch.setattr(sub_ask, "SWEEP_LOG", log)

    class _Videos:
        def list(self, **kw):
            return self

        def execute(self):
            return {"items": [{"id": "vid1", "snippet": {
                "title": "t", "description": sub_ask.HEAD + "本文"}}]}

    class _Svc:
        def videos(self):
            return _Videos()

    assert sub_ask.apply_to_video("vid1", service=_Svc()) == 0
    rows = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()]
    assert [r["id"] for r in rows] == ["vid1"], "覆っている本が控えに載っていません"

    # 二度撃っても行は増えないこと（控えは「覆っているか」の台帳で、撃った回数ではない）
    sub_ask.apply_to_video("vid1", service=_Svc())
    rows = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1, "同じ本が二重に載っています（次の回の割合が狂います）"


def test_eta_counts_the_same_books_the_sweep_would_touch(monkeypatch):
    """**eta の「残り N本」が `--sweep` の「置く先」と同じ母集団であること** —— 2. の食い違い。"""
    eta = _eta()
    # 門の外（再生/日 が低い）の本を1つ混ぜる。`--sweep` は触りません。
    monkeypatch.setattr(sub_ask, "rank_by_traffic",
                        lambda *a, **k: [(9.0, "hot"), (0.0001, "cold")])
    monkeypatch.setattr(sub_ask, "swept_ids", lambda *a, **k: {"hot"})
    got = eta._sub_ask_uncovered()
    assert got is not None
    n, per_day, share = got
    assert n == 0, f"`--sweep` が触らない本を『残り』に数えています（{got}）"
    assert share == 0.0


def test_eta_and_sweep_agree_on_the_live_repo():
    """**いまの repo で、2つの画面が同じ答えを出すこと**（API 0単位）。"""
    eta = _eta()
    got = eta._sub_ask_uncovered()
    if got is None:
        return
    done = sub_ask.swept_ids()
    targets = sub_ask.sweep_targets()
    assert got[0] == len([1 for d, v in targets if v not in done and d > 0])
