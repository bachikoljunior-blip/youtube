"""**「いちばん早い期日」が、引き代の無い腕の前提でも黙って通っていた。**

（2026-09-01 夕・最適化の回）

`arm_speed.next_close()` は 2026-08-31 から `claim_levers` を返しています。
その回の docstring は理由をこう書いています ——

    日付だけを見て「**この回は `verdict` で日付が動かせます**」と印字すると、
    **腕に引き代の無い前提**を名指ししたときに嘘になります。
    `claim_levers` を読む側が、その1件を断れるようにします。

**読む側は、断っていませんでした。** `scripts/eta.py` の
「**この回に閉じられる前提はありません —— いちばん早い期日は …**」は
`nc["on"]` しか見ていません。

実測 2026-09-01 12:4x（この検査を書いた回に数えた。**数は写しません**）:
いちばん早い期日の1件の腕は `sub_rate` ＝ その回の `arm_dead_at_inf`
（`×10^9` でも到達日は出ない）。**次の `verdict` は 0日 の回でした。**

**この検査が守るのは規則です** —— `dead` を渡したら、その腕の前提を
「次の1件」に数えないこと。**渡さない回は従来どおり黙ること。**
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import arm_speed                            # noqa: E402

TODAY = date(2026, 9, 1)

DOC = {"hypotheses": [
    {"claim": "登録を頼む", "lever": "sub_rate", "deadline": "2026-09-03"},
    {"claim": "置く位置", "lever": "density", "deadline": "2026-09-05"},
    {"claim": "題を問いに", "lever": "per_video", "deadline": "2026-09-22"},
    {"claim": "長尺の面", "lever": "rpm", "deadline": "2026-09-22"},
    {"claim": "閉じたやつ", "lever": "per_video", "deadline": "2026-08-01",
     "closed_on": "2026-08-30"},
]}


def test_渡さなければ従来どおり黙る():
    """**「読めない」と「無い」は別。** 集合を作れない回は何も言わないこと。"""
    nc = arm_speed.next_close(doc=DOC, today=TODAY)
    assert nc["on"] == date(2026, 9, 3)
    assert nc["live_on"] is None
    assert nc["live_claims"] == []
    assert nc["dead_skipped"] == 0


def test_死んだ腕を外した側の日付を返す():
    nc = arm_speed.next_close(doc=DOC, today=TODAY, dead={"sub_rate", "density"})
    # **いちばん早い期日そのものは動きません**（開いている件数の話ではない）
    assert nc["on"] == date(2026, 9, 3)
    assert nc["claim_levers"] == {"登録を頼む": "sub_rate"}
    # **動かせる側は 09-22。** 19日 遅い ＝ その差が「待っても動かない日数」
    assert nc["live_on"] == date(2026, 9, 22)
    assert nc["live_days"] == 21
    assert set(nc["live_claims"]) == {"題を問いに", "長尺の面"}
    assert nc["dead_skipped"] == 2


def test_生きた腕の前提が1件も無ければ日付を出さない():
    """**推測で日付を作らないこと。** 出すのは `None` で、読む側が `premise` へ回る。"""
    nc = arm_speed.next_close(doc=DOC, today=TODAY,
                              dead={"sub_rate", "density", "per_video", "rpm"})
    assert nc["on"] == date(2026, 9, 3)
    assert nc["live_on"] is None
    assert nc["dead_skipped"] == 4


def test_腕の書いていない前提は生きた側に数えない():
    """`lever:` が空だと `arm_speed.closed()` から落ち、θ にも入りません。

    **「腕が書いていない」を「生きている」と読むと、燃料が水増しされます。**
    """
    doc = {"hypotheses": [
        {"claim": "腕が空", "deadline": "2026-09-02"},
        {"claim": "死んだ腕", "lever": "sub_rate", "deadline": "2026-09-04"},
    ]}
    nc = arm_speed.next_close(doc=doc, today=TODAY, dead={"sub_rate"})
    assert nc["on"] == date(2026, 9, 2)
    assert nc["live_on"] is None


def test_故障を注入すると落ちる():
    """**発火したことのない検査は検査ではない。**

    `dead` から `sub_rate` を落とす（＝ `eta.py` が ×10^9 を撃たなくなった版）と、
    **09-03 の1件が「動かせる次の1件」に戻ります。**
    """
    nc = arm_speed.next_close(doc=DOC, today=TODAY, dead={"density"})
    assert nc["live_on"] == date(2026, 9, 3)
    assert nc["live_claims"] == ["登録を頼む"]
    assert nc["dead_skipped"] == 1
