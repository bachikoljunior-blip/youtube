"""画面が字だけのコマを名指しする（`Script.text_only_segments`）。

オーナー 2026-09-19 12:3x `9155fe09`「画面がある意味が文字だけになってんのどうにかしろよ」。
**在庫 42本 を数えたら、図の在るコマは 307/1312（23%）しかありません**（2026-09-19 15:2x）。
"""
from __future__ import annotations

from studio.script import Script


def _book(segs):
    return Script(id="2026-09-30-test", date="2026-09-30", title="て", takeaway="て",
                  description="て", segments=segs)


def _seg(**kw):
    d = dict(say="て。", show="て", sub="て", tag="計算")
    d.update(kw)
    return d


def test_板に数が2つ以上あって図が無いコマを名指しする():
    b = _book([_seg(board=["退職金 2000万円", "− 枠 1500万円", "＝ 500万円"]),
               _seg(board=["会社をやめるとき", "退職金をもらう人へ"]),
               _seg(board=["枠は 1500万円"])])
    got = b.text_only_segments()
    assert got is not None
    n, tot, ex = got
    assert (n, tot) == (1, 3), "数が 1つ のコマ・数が無いコマは名指ししない"
    assert ex == "コマ1"


def test_図が在るコマは名指ししない():
    viz = {"kind": "bars", "items": [{"label": "枠", "value": 15000000},
                                     {"label": "のこり", "value": 5000000}]}
    b = _book([_seg(board=["退職金 2000万円", "− 枠 1500万円"], viz=viz)])
    assert b.text_only_segments() is None


def test_止めない_問題ではなく読む材料():
    b = _book([_seg(board=["退職金 2000万円", "− 枠 1500万円"])])
    assert not [x for x in b.problems() if "数のコマ" in x], "`problems` に入れない（焼けなくなる）"
    assert [x for x in b.warnings() if "数のコマ" in x], "`warnings` には出る"
