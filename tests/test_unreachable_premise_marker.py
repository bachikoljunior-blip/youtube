# -*- coding: utf-8 -*-
"""**§1 の印が「規則の下では満ちない前提」を出しているか。**

## なぜこの検査が要るか（2026-09-01 に足した）

`scripts/eta.py` は毎周「**軌跡の腕が動くのは `config/hypotheses.yaml` の
前提を1件 閉じたときだけ**」と印字します。だから台帳に
**「期日が永久に来ない前提」**が居座ると、到達日はそこで止まります。

その計器（`src.house_rule.unreachable_needs()`）は前から在りましたが、
印字するのは `scripts/deadline_check.py` の**末尾**だけで、
**§1（`run_marker.py --write`）の読む順には1つも入っていませんでした。**

実測 2026-09-01 04:0x の回 —— `eta.py` の名指しは `per_video`、
「この回に閉じられる前提はありません」。5つの選択肢のうち4つが枠切れで塞がり、
残るのは `fix` だけに見えていました。`deadline_check.py` を末尾まで読んで
はじめて「規則の下では満ちない要件 1件」が出て、
**その1件が公開ずみの日だけで期限より 10日 早く閉じました。**
**同じ回に `verdict` が撃てるかどうかが、この1行の有無で決まっていました。**

**配線が外れたら、ここが赤くなります。**
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import run_marker  # noqa: E402


def test_印は満ちない前提を数える関数を持っている():
    assert hasattr(run_marker, "_unreachable_premise_lines")


def test_writeがその関数を呼んでいる():
    """**呼び出しが外れたら赤。** 関数が在るだけでは、誰も読みません。"""
    src = (ROOT / "scripts" / "run_marker.py").read_text(encoding="utf-8")
    body = src.split("def write()", 1)[1].split("\ndef ", 1)[0]
    assert "_unreachable_premise_lines()" in body


def test_満ちない前提があれば行が出る(monkeypatch):
    """台帳が汚れているときだけ鳴ること（きれいなら黙る）。"""
    from src import house_rule

    fake = [{
        "claim": "長尺の面は、その日の長尺の公開本数で決まる",
        "deadline": "2099-01-01",
        "lever": "rpm",
        "needs": [{"kind": "after", "on_date": "2099-01-01",
                   "what": "`data/reach.jsonl` の窓（長尺の予約 26本 ＝ 2.0本/日）"}],
    }]
    hit = house_rule.unreachable_needs(fake)
    assert hit, "2.0本/日 は規則（1本/日）を超えているので、拾われなければならない"

    monkeypatch.setattr(house_rule, "unreachable_needs", lambda rows, **kw: hit)
    lines = run_marker._unreachable_premise_lines()
    assert lines, "満ちない要件があるのに、印が黙ってはいけない"
    joined = "\n".join(lines)
    assert "満ちない前提" in joined
    assert "rpm" in joined, "腕の札を出すこと（どの倍率が止まるかが分かる）"
    assert "公開ずみの日で判定できるなら、いま閉じる" in joined, (
        "直し方の (2) を書くこと —— 2026-09-01 はこれで 10日 前倒しできた")


def test_計器が落ちても回は止めない(monkeypatch):
    """**印が本体で、これは付け足しです。** 例外で1周を殺さないこと。"""
    from src import house_rule

    def boom(*a, **k):
        raise RuntimeError("台帳が読めない")

    monkeypatch.setattr(house_rule, "unreachable_needs", boom)
    lines = run_marker._unreachable_premise_lines()
    assert lines and "数えられませんでした" in lines[0]
