# -*- coding: utf-8 -*-
"""`scripts/method_growth.py` —— METHOD の「毎回 読む」側の伸びを、**道具が数えて門を引く**こと。

2026-09-10 12:1x JST（optimizer・Opus）。冒頭「この文書の読み方」は門を **2つ** 置いています
（行 1周 +20行・本文の字 1周 +300字）が、**どちらにも印字する口がありませんでした** ——
数え方は JOURNAL 05:5x に散文で在るだけで、6周ごとに次の回がそれを探して手で回す形。
`trend.py` の「毎周 印字する数」と同じ扱い（**覚えないこと**）にした、その見張り。

**いちばん大事な検査は `test_11_0x_が手で数えた_3点_と_1字も違わないこと`** ——
道具が別の数を出すなら、置いた門は別の物を測っています。

**陽性対照は撃って落としてある**（§5 の教訓の形3つ目）:
`measure` から引用の除外（`startswith(">")`）を外すと 3点 とも合わなくなる。
"""
import importlib.util
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _mod():
    spec = importlib.util.spec_from_file_location("method_growth", ROOT / "scripts" / "method_growth.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


M = _mod()


def _at(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=M.JST)


#: 11:0x の回が **手で** 数えて `docs/METHOD.md` の冒頭へ書いた 3点（窓の端は周の刻・JST）。
#: **この表を道具から作らないこと** —— 借りると、道具と一緒に間違えます。
点 = [
    ("2026-09-09 21:46", "2026-09-10 01:25", 16, 1850),
    ("2026-09-10 01:59", "2026-09-10 05:25", 23, 2758),
    ("2026-09-10 06:07", "2026-09-10 10:17", 3, 3699),
]


@pytest.mark.parametrize("a,b,d_lines,d_chars", 点)
def test_11_0x_が手で数えた_3点_と_1字も違わないこと(a, b, d_lines, d_chars):
    """**道具が別の数を出すなら、置いた門は別の物を測っています。**"""
    ma, mb = M.measure(M.blob_at(_at(a))), M.measure(M.blob_at(_at(b)))
    assert mb["body_lines"] - ma["body_lines"] == d_lines
    assert mb["body_chars"] - ma["body_chars"] == d_chars


def test_引用は本文に数えない():
    """**門は本文（引用を除く）に置かれています**（11:0x）。混ぜたら門の意味が変わる。

    **節の見出しは本文に入ります**（05:5x の手が `L[s0:s7]` で挟んでいる形そのもの）——
    見出しも毎周 読む字なので、外すと 11:0x の 3点 と合わなくなります。
    """
    text = "## 0.\nあいう\n> かきくけこ\n\n## 7.\n## 8.\nさし\n## 9.\n"
    m = M.measure(text)
    assert m["body_lines"] == 4                       # 見出し2つ ＋「あいう」「さし」（空行も引用も数えない）
    assert m["body_chars"] == len("## 0.") + 3 + len("## 8.") + 2
    assert m["quote_chars"] == len("> かきくけこ")


def test_毎回読む側は_7_と_9_を含まないこと():
    """§7（log）と §9 以降（過去の本）は**飛ばす側**なので、物差しに入れない。"""
    text = "## 0.\nA\n## 7.\nBBBB\n## 8.\nC\n## 9.\nDDDD\n"
    m = M.measure(text)
    assert m["body_lines"] == 4                        # 見出し2つ ＋ A と C
    assert m["body_chars"] == len("## 0.") + 1 + len("## 8.") + 1
    # **飛ばす側をいくら太らせても、この数は1字も動かないこと**（＝ 門は log では鳴らない）
    太らせた = text.replace("BBBB", "B" * 9999).replace("DDDD", "D" * 9999)
    assert M.measure(太らせた) == m


def test_節の名が変わったら黙って_0_を返さずに止まること():
    """**外れた数を配るより、止まるほうが安い**（註の覆る条件 (3)）。"""
    with pytest.raises(KeyError):
        M.measure("## 0.\nA\n")          # §7 の見出しが無い


def test_周は_round_で畳む():
    """`rounds.jsonl` は 1周に 2行（hourly・optimizer）入る。畳まないと窓が半分になる。"""
    rs = M.rounds()
    assert len(rs) == len(set(rs)), "周の刻に重複があります ＝ `round` で畳めていません"
    assert rs == sorted(rs)


def test_字の門は_2窓_続いたときだけ引く():
    """**1窓 で引かない**（11:0x が「2つ 続いたら」と書いた形）。"""
    def p(chars_per_lap):
        return {"chars_per_lap": chars_per_lap, "lines_per_lap": 1.0}
    assert "引かれません" in M.verdict([p(400), p(100)])[1]
    assert "引かれました" in M.verdict([p(100), p(400), p(400)])[1]


def test_行の門は字の門と別に印字されること():
    """**行の門は単独では効きません**（点3 は 20行 の 1/40 で +616字/周 積んだ）。
    2つを1行に畳むと、その盲点がまた隠れる。"""
    out = M.verdict([{"chars_per_lap": 400.0, "lines_per_lap": 0.5},
                     {"chars_per_lap": 400.0, "lines_per_lap": 0.5}])
    assert len(out) == 2
    assert "行の門" in out[0] and "引かれません" in out[0]      # 20行 には遠い
    assert "字の門" in out[1] and "引かれました" in out[1]      # それでも字は越えている


def test_報告は窓の端を_JST_の刻で出すこと():
    """次の回が「どこからどこまでを測ったか」を読めること（窓の取り方が違うと点は比べられない）。"""
    out = M.report(laps=6, n=2)
    assert "周の刻で挟む" in out and "commit ではない" in out
    assert "JST" in out
