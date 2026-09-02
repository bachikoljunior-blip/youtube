"""**公開ずみの本を足して数える**（2026-09-03 01:xx に踏んで足した）

要件「09/01 以降に公開した本が 20本」に対し、それまでの `house_rule.needs_beyond_rule()` は
`allowed = (期日 − 今日) × 1` **だけ**で、09/01 以降にもう公開になった本を
0 に置いていました。だから公開の有無にかかわらず**毎日 1本ずつ足りなくなって見え**、
台帳の 09-26／10-06（どちらも `lever: per_video`）が 09/02 に期限を 1日 送られ、
09/03 の回にも同じ「1日 足りません」が出ました —— 本文の註は
「これは毎日 腐ります。送り直すのが正しい手ではありません」と書いたままで、
**腐らせていたのは数える側でした。**

さらに同じ画面が「暦の穴を埋めること（`reschedule.py --compact`）」を勧めていましたが、
固定その4（予約はその日のぶんだけ・先の日付は空が正しい）の下でその手は無く、
同じ file の上の節が「`--compact --apply` は撃たないこと」と書いていました。

**既知の当たり**（09/03 に 09/22 を見る・公開ずみ 2本）を先に固定します。
"""
from __future__ import annotations

import unittest.mock as um
from datetime import date

from src import house_rule

_WHAT_SINCE = ("規則（1日1本）の下で 09/01 以降に公開した本が 20本 積むのを待つ"
               "（1日1本なので 20日）")


def test_公開ずみを足すと届く():
    """09/03 に 09/22 を見る: 公開ずみ 2本 ＋ 19日 ＝ 21本 ≥ 20本 → **満ちます**。"""
    assert house_rule.needs_beyond_rule(_WHAT_SINCE, "2026-09-22",
                                        today="2026-09-03", published=2) is None


def test_公開ずみが0なら前と同じに足りない():
    hit = house_rule.needs_beyond_rule(_WHAT_SINCE, "2026-09-22",
                                       today="2026-09-03", published=0)
    assert hit is not None
    assert hit["short_days"] == 1 and hit["done"] == 0 and hit["since"] == "2026-09-01"


def test_公開ずみは控えの実物から数える():
    """`published` を渡さなければ、`09/01 以降` を読んで控えを数えること（**時刻**で比べる）。"""
    rows = [
        {"video_id": "a", "at": "2026-09-01T13:00:00Z"},   # 09/01 22:00 JST ＝ 公開ずみ
        {"video_id": "b", "at": "2026-09-02T04:00:00Z"},   # 09/02 13:00 JST ＝ 公開ずみ
        {"video_id": "b", "at": "2026-09-02T04:00:00Z"},   # 同じ本の重複行は 1本
        {"video_id": "c", "at": "2026-09-03T00:00:00Z"},   # 09/03 09:00 JST ＝ 00:00 JST 境では未来
        {"video_id": "z", "at": "2026-08-30T03:30:00Z"},   # 09/01 より前は数えない
        {"video_id": "q"},                                 # 読めない行は数えない
    ]
    assert house_rule.since_of(_WHAT_SINCE, today="2026-09-03") == date(2026, 9, 1)
    assert house_rule.published_since(date(2026, 9, 1), today="2026-09-03", rows=rows) == 2
    with um.patch.object(house_rule, "published_since", lambda *a, **k: 2):
        assert house_rule.needs_beyond_rule(_WHAT_SINCE, "2026-09-22",
                                            today="2026-09-03") is None


def test_以降の無い要件は前のまま():
    """出どころの日付が読めない要件に、控えの本数を足さないこと（前の判定を保つ）。"""
    hit = house_rule.needs_beyond_rule("09/10（16本 公開）の読み", "2026-09-10",
                                       today="2026-08-31")
    assert hit is not None and hit["done"] == 0 and hit["allowed"] == 10


def test_年の無い以降は今日以前でいちばん近い月日():
    assert house_rule.since_of("12/30 以降に 3本", today="2026-01-02") == date(2025, 12, 30)
    assert house_rule.since_of("2026-09-01 以降に 3本", today="2026-09-03") == date(2026, 9, 1)
    assert house_rule.since_of("本数だけ 3本", today="2026-09-03") is None


def test_行は公開ずみと残りの日数を分けて出し_compactを勧めない():
    """固定その4 の下で「暦の穴を埋めろ（`--compact`）」は無い手です。"""
    rows = [{"claim": "live 判定", "deadline": "2026-09-26",
             "needs": [{"on_date": "2026-09-22", "what": _WHAT_SINCE}]}]
    with um.patch.object(house_rule, "published_since", lambda *a, **k: 0):
        body = "\n".join(house_rule.unreachable_lines(rows, today="2026-09-03"))
    assert "公開ずみ **0本**" in body and "**19本**" in body, body
    assert "--compact" not in body
