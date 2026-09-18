"""**「取り直せ」と言う門が、撃つと別の門を壊す手を配っていないこと**
（2026-09-19 01:xx・optimizer・Opus 5）。

## なぜ在るか（この回に踏んだ形）

`test_暦の日の押さえが_実物の前提に効いていること` が赤で、その文言はこう言います:

    **待ち方が違います。足りないのは日ではなく、計器のほうです** ——
    `data/views.jsonl` は 取り直したのは 09/07 14:50 JST（274時間 前）。
    **取り直すまで、待っても増えません。**  `python scripts/snapshot.py`

**そのとおりに撃つと、別の門が赤くなります。** `data/views.jsonl` は
`scripts/zero_start.py` の §1 が**凍結している前提で読んでいる下敷き**だからです
（`scripts/snapshot.py` の註の実測: 行が入った回に B群の最大が **275 → 382回**・
`tests/test_zero_start.py::test_実物の下敷き_旧データは凍結なので数は動かない` が赤）。

＝ **赤い門が、次の回に「撃つと壊れる手」を渡していました。**
`_BUILD_LEDGERS`（撃てない手を名指ししない）と**同じ族のもう半分**です。

守るのは 2つ:
  (1) 凍結した計器の「取り直せ」には、**必ず一言 添わること**
  (2) **手そのものは消さないこと**（取り直すべき回は在る ＝ 黙らせるのは嘘）
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import deadline_check as dc  # noqa: E402


def test_views_は凍結した下敷きとして登録されている():
    assert "data/views.jsonl" in dc._FROZEN_UNDERLAYS


def test_取り直す手そのものは消していない():
    """黙らせるのは嘘。**手は残し、一言 添えるだけ**。"""
    assert dc._METER_REFRESH["data/views.jsonl"] == "python scripts/snapshot.py"


def test_註は壊れる相手を名指しする():
    """「気をつけて」では動けない ＝ **どの検査が赤くなるか**を書くこと。"""
    note = dc._FROZEN_UNDERLAYS["data/views.jsonl"]
    assert "zero_start" in note
    assert "275" in note and "382" in note, "実測の数を残すこと（次の回が覆せるように）"


def test_凍結していない計器には何も足さない():
    """**空振りを増やさないこと** —— 添うのは凍結した物だけ。"""
    for src in ("data/reach.jsonl", "data/retention.json", "data/video_forms.json"):
        assert dc._FROZEN_UNDERLAYS.get(src, "") == ""
