"""**`--list` が「族の数」を言うこと**を固定する（2026-08-26 に踏んだ）。

`scripts/topic_forge.py --list` は長らく節しか数えていませんでした。
**長尺の律速はそこではありません** —— `scripts/batch_build.pick` は
`_drop_queue_tail_calcs` で「これから7日ぶんの長尺に出ている calc」を丸ごと落とし、
1回の batch で同じ calc から取れるのは `per_calc`（既定2）まで。
つまり **1族に7節あっても、7日で取れるのは2本**です。

実測（2026-08-26 02:0x）: `jouto` の節を7つ足した直後、長尺向けのテーマは
6件残っていたのに `pick(long_form=True)` は **1件も返しませんでした**。
**節の数を見ているかぎり、この形は数字に出ません。**

ここで固定するのは2つ:

1. 上限は「族の数 × `per_calc`」と「テーマの数」の小さいほう
2. **投稿済みのテーマは数えない**（控えから引く）
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

import topic_forge  # noqa: E402


def _stub(monkeypatch, topics, used=()):
    from src import config, dupes

    monkeypatch.setattr(config, "load_topics", lambda: {"topics": topics})
    monkeypatch.setattr(dupes, "ledger_rows",
                        lambda: [{"topic": t} for t in used])


def _t(tid: str, calc: str) -> dict:
    return {"id": tid, "calc": calc}


def test_1族に何節あっても上限は2本(monkeypatch, capsys):
    _stub(monkeypatch, [_t(f"alpha-{i}", "alpha") for i in range(7)])
    topic_forge.print_long_stock()
    out = capsys.readouterr().out
    assert "**7件** / 族 **1**" in out, out
    assert "最大 2本" in out, out
    # **文言そのものではなく、言っている中身を固定します**（2026-08-26 03:5x に直した）。
    #     ここは `"別の族" in out` でした。**その1語は「新しい表を書け」と読めます** ——
    #     実際、そう読んだ回が2回、`src/calc/` に新しい表を書くところから
    #     始めています（実測 20〜25分。既にある表に節を足せば12〜15分）。
    #     文言を直した回がこの検査に当たったので、**固定する先を中身へ移しました。**
    assert "族を1つ増やす" in out, out          # 増やすのは族であって節ではない
    assert "同じ族に節を足しても" in out, out   # 同じ族に足しても増えない


def test_族が増えれば上限も増える(monkeypatch, capsys):
    _stub(monkeypatch, [_t("alpha-1", "alpha"), _t("alpha-2", "alpha"),
                        _t("bravo-1", "bravo"), _t("bravo-2", "bravo")])
    topic_forge.print_long_stock()
    out = capsys.readouterr().out
    assert "**4件** / 族 **2**" in out, out
    assert "最大 4本" in out, out


def test_ショート向けと投稿済みは数えない(monkeypatch, capsys):
    _stub(monkeypatch,
          [_t("s-alpha-1", "alpha"), _t("alpha-2", "alpha"),
           _t("alpha-3", "alpha")],
          used=["alpha-3"])
    topic_forge.print_long_stock()
    out = capsys.readouterr().out
    assert "**1件** / 族 **1**" in out, out
    assert "最大 1本" in out, out
