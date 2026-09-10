"""**門 (2) の比は「いつ測ったか」で上下する** —— その振れ幅を見張る
（2026-09-10 09:4x JST・optimizer・Opus）。

註と derivation は `studio/trend.py` の `gate_span`。要点だけ:
`_pairs` は 2点目の刻で組を帯／外に分けるので、**いま撃った `measure` は居る側の分母だけを増やす**。
本が落ち着いていればその組は伸びないので、**測っている側の率だけが下がる**
＝ 比は自分が居る側から逃げる。帯の中を続けて撃つと、**本の側が 1つも動かないまま門 0.5 へ寄る。**
"""
import json
import pathlib

import pytest

from studio import trend

LEDGER = pathlib.Path(__file__).resolve().parents[1] / "data" / "studio" / "ledger.jsonl"


def _rows() -> list[dict]:
    return [json.loads(l) for l in LEDGER.read_text().splitlines() if l.strip()]


def _occasions(rows: list[dict]) -> list[str]:
    return sorted({r["at"] for r in rows if r.get("event") == "measured"})


def _truncated(rows: list[dict], keep: set[str]) -> list[dict]:
    return [r for r in rows if r.get("event") != "measured" or r["at"] in keep]


def test_振れ幅は今の点を挟む() -> None:
    g = trend.gate_span(_rows())
    assert g["n"], "本物の台帳で読み直せた回が 0 —— 24時間 に測りが無いか、gate_ratio が出ていない"
    assert g["lo"] <= g["now"] <= g["hi"]
    # **実物を返り値に残すこと**（§5 の「判定した実物を残す」）——次の回が列挙で確かめられる
    assert len(g["points"]) == g["n"]
    assert all(len(p) == 3 for p in g["points"])


def test_振れ幅は鋸の歯で点ではない() -> None:
    """24時間 の幅が `gate_span` の覆る条件 (2) の門（0.2倍）より広いこと。

    **これが狭くなったら**（帯と外が同じ速さで積まれるようになったら）、
    点で読んでよい ＝ そのときこの検査ごと書き換える（覆る条件 (2)）。
    """
    g = trend.gate_span(_rows())
    assert g["hi"] - g["lo"] > 0.2, (
        f"振れ幅が {g['hi'] - g['lo']:.3f}倍 に狭まった —— `gate_span` の覆る条件 (2)。"
        "点で読んでよい形になったので、註とこの検査を書き直すこと")


def test_門は振れ幅の上限で読む_越えたら教える() -> None:
    """**門 (2) は上限が 0.5 を切った回にだけ引く**（`gate_span` の覆る条件 (1)）。

    **これは「越えたら教える」検査です** —— 上限が 0.5 を切ったら赤になり、
    そのとき初めて「帯は刻では説明が付かない」と言えます。
    **赤で教えた回に、次の門へ書き換えるところまでが1組**（§7 09:0x の形）。
    """
    g = trend.gate_span(_rows())
    assert g["hi"] > 0.5, (
        f"直近 {trend.GATE_SPAN_H:.0f}時間 の上限が {g['hi']:.3f}倍 ＝ 門 0.5 を切った。"
        "**刻では説明が付かない ＝ 門 (2) は本当に引かれた**（判定は `hourly`・§5）。"
        "この検査を次の門へ書き換えること")


def test_帯の中で測ると分子が動かないまま比が下がる() -> None:
    """**主張そのものを、本物の台帳から確かめる。**

    測りの刻で台帳を切って読み直し、「帯の中で測った回のうち、
    **帯の分子が動かないまま分母だけ増えた**回」を集める。
    その回では比は**上がらない**（下がるか、同じ）。
    ＝ 比の動きが本の側の事実ではないことの、実物での証拠。
    """
    rows = _rows()
    occ = _occasions(rows)
    prev = None
    checked = 0
    for at in occ:
        inf = trend.informative(_truncated(rows, set(occ[:occ.index(at) + 1])))
        cur = (inf.get("gate_ratio"), inf.get("band_gapmatched"), inf.get("out_gapmatched"))
        if prev and None not in (cur[0], prev[0]):
            (r0, b0, o0), (r1, b1, o1) = prev, cur
            # 分子が両側とも動かず、帯の分母だけが増えた回
            if b0[0] == b1[0] and o0 == o1 and b1[1] > b0[1]:
                checked += 1
                assert r1 <= r0 + 1e-9, (
                    f"{at}: 分子 {b1[0]} は動いていないのに比が {r0:.3f} → {r1:.3f} と上がった")
        prev = cur
    assert checked >= 3, (
        f"分子が止まったまま分母だけ増えた回が {checked}回 しか無い —— "
        "帯の中で続けて測る形が消えたなら、`gate_span` の覆る条件 (2)(3) を見ること")


def test_印字は上限を門に使うと言う() -> None:
    line = trend._span_line(_rows())
    assert "振れ幅" in line
    assert "上限" in line
    # **点（`now`）ではなく上限（`hi`）を門に使うと書いてあること**
    g = trend.gate_span(_rows())
    assert f"上限 {g['hi']:.3f}" in line


def test_測りが無ければ黙る() -> None:
    """陽性対照の受け皿 —— 台帳に `measured` が無ければ振れ幅は出せない（印字も空）。"""
    g = trend.gate_span([{"event": "built", "at": "2026-09-10T09:00:00+09:00"}])
    assert g["n"] == 0 and g["hi"] is None
    assert trend._span_line([]) == ""


@pytest.mark.parametrize("hours", [24.0, 48.0])
def test_窓を伸ばしても上限は下がらない(hours: float) -> None:
    """`hours` は遡る長さなので、**伸ばして上限が下がることはない**（同じ点の集合を含む）。

    覆る条件 (4)（24時間 なのは帯が 1日に 1度しか回らないから）が守られている印。
    """
    rows = _rows()
    a = trend.gate_span(rows, hours=24.0)
    b = trend.gate_span(rows, hours=hours)
    assert b["hi"] >= a["hi"] - 1e-9
    assert b["n"] >= a["n"]
