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
    """24時間 の幅が `gate_span` の覆る条件 (2) の門より広い**回が続いていない**こと。

    **これが狭くなったら**（帯と外が同じ速さで積まれるようになったら）、
    点で読んでよい ＝ そのときこの検査ごと書き換える（覆る条件 (2)）。

    **2026-09-13 00:1x（optimizer・Opus）に、点から連へ直しました。**
    この回に 24時間 の幅が **0.168倍** ＝ 門 0.2 の下へ 1点 だけ入り、**この検査が赤になりました**。
    ところが註の (2) は「**下回ったまま `SPAN_NARROW_NEED`（3回）続いたら**」で、
    **1点 では引かれていません**（1つ 手前は 0.221倍）。
    ＝ **註は「続いたら」と言い、見張りは「点」で鳴っていました** ——
    §5 教訓の形 7つ目（註と印字が食い違えば読まれるのは印字のほう）の、**検査の側での例**。
    連を数える口は `trend.span_narrow_run`（**単位は「測り」＝ 周ではない**・同 註）。
    """
    r = trend.span_narrow_run(_rows())
    assert r["now"] is not None, "24時間 に比の点が 1つ しか無い —— 床（`quota.pace()`）を見ること"
    assert not r["drawn"], (
        f"幅が {float(r['now']):.3f}倍（門 {r['gate']}倍）で **{r['run']}/{r['need']}回 続いた** "
        f"—— `gate_span` の覆る条件 (2)。点で読んでよい形になったので、註とこの検査を書き直すこと。"
        f"並び: {r['widths']}")


def test_連は測りで数える_周ではない() -> None:
    """**単位の見張り**（`span_narrow_run` の註）。

    幅が動くのは `measure` を撃った刻だけなので、連は**測り**で数える。
    `widths` の刻が台帳の `measured` の刻の部分列であることで、それを押さえる。
    """
    rows = _rows()
    r = trend.span_narrow_run(rows)
    occ = {trend._at({"at": a}).strftime("%m/%d %H:%M") for a in _occasions(rows)}
    for w in r["widths"]:
        assert w["at"] in occ, f"{w['at']} は `measured` の刻ではありません（周で数えていないか）"
    # 新しい順に並んでいること（連は新しいほうから数える）
    ats = [w["at"] for w in r["widths"]]
    assert ats == sorted(ats, reverse=True), ats


def test_連の門は註の数と同じ場所から来ること() -> None:
    """**門を 2か所 に置かない**（`span_narrow_run` の覆る条件 (3)）。"""
    r = trend.span_narrow_run(_rows())
    assert r["gate"] == trend.SPAN_NARROW_GATE == 0.2
    assert r["need"] == trend.SPAN_NARROW_NEED == 3


def test_連の陽性対照_門を動かせば連が動くこと() -> None:
    """**陽性対照**（§5 教訓の形 3つ目「壊したら落ちるまで撃つ」）。

    **緩める側だけでは測れません**（2026-09-13 02:5x に踏んだ・optimizer・Opus）——
    `span_narrow_run` は `need`+1 回ぶんしか遡らないので、**連は need+1 で頭打ち**です。
    窓の刻が全部 門の下に入った回（この回: 幅 0.168倍 が **4刻 とも**・連 4 ＝ 頭打ちの 4）は、
    **門をいくら緩めても連は 1 も伸びません** ＝ この向きの対照は、
    **状態が飽和した日に、道具を 1行 も壊さずに赤くなります**
    （§5 教訓の形 6つ目「検査に『きょうの状態』を不変条件として書かないこと」の、
    **陽性対照の向き**の側。書いた 00:1x の回は連が **1** で、頭打ちが見えていなかった）。

    **締める側は頭打ちを持ちません** —— 全部の幅より下へ門を落とせば、連は必ず **0** です。
    だから対照は「締めたら 0・緩めたら 刻の数」の **両側**で見ます。

    **覆る条件**: `span_narrow_run` が `need`+1 の頭打ちをやめて窓の刻を全部 数えるように
    変わったら、緩める側にも頭打ちが無くなる ＝ そのときは `loose["run"]` の当て先
    （いま「刻の数」）を数え直すこと。
    """
    rows = _rows()
    base = trend.span_narrow_run(rows)
    widths = [float(w["width"]) for w in base["widths"]]
    if not widths:
        pytest.skip("窓に幅の作れる刻が無い")
    saved = trend.SPAN_NARROW_GATE
    try:
        trend.SPAN_NARROW_GATE = min(widths) / 2.0        # 全部の幅より下
        tight = trend.span_narrow_run(rows)
        trend.SPAN_NARROW_GATE = max(widths) + 1.0        # 全部の幅より上
        loose = trend.span_narrow_run(rows)
    finally:
        # **借りた物は借りた形で返す**（§5 教訓の形 11つ目）
        trend.SPAN_NARROW_GATE = saved
    assert tight["run"] == 0, (
        f"門を {min(widths) / 2.0:.3f} まで締めても連が {tight['run']} ＝ 幅を読んでいません")
    assert loose["run"] == len(widths), (
        f"門を {max(widths) + 1.0:.3f} まで緩めても連が {loose['run']} "
        f"（窓の刻 {len(widths)}）＝ 幅を読んでいません")
    assert tight["run"] < loose["run"]
    assert trend.SPAN_NARROW_GATE == 0.2


def test_印字は連と単位を言うこと() -> None:
    """**註ではなく印字が読まれる**（§5 教訓の形 7つ目）—— 連と単位が画面に出ていること。"""
    line = trend._span_line(_rows())
    r = trend.span_narrow_run(_rows())
    assert f"{r['run']}/{r['need']}回" in line, line
    assert "単位は「測り」" in line


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


# ---- **側**も点で読まない（2026-09-10 12:3x・optimizer・Opus） ----------------------
#
# 09:4x は**比**を振れ幅へ移したが、**どちらの側の比を読むか**（`gate_side`）は 1点のままだった。
# **この回に踏んだ**: 帯の外から `measure` を 1回 足すだけで 差が 0.101 → 0.020倍 に落ち、側が反転する
# （本の側は 1冊も動いていない）。derivation は `trend.gate_span` の註と JOURNAL 12:3x。

def test_側は点で読む() -> None:
    """**2026-09-12 04:0x に (5)(6) を畳みました** —— `side` は `side_now`（その刻の差）と
    `GAP_SPLIT` だけで決まること（**上限では決まらない**）。畳んだ理由と (5') は `gate_span` の註。
    """
    rows = _rows()
    g = trend.gate_span(rows)
    if g["side_hi"] is None:
        return
    assert g["side"] == ("齢＋長さ" if g["side_now"] >= trend.GAP_SPLIT else "齢だけ")


#: **2つ の読み方が食い違っていた刻**（2026-09-12 04:0x に台帳を切って列挙した・20回 のうちの 1つ）。
#: 点は 0.0325（`齢だけ`）・24時間 の上限は 0.1993（`齢＋長さ`）で、上限の側は
#: **09/11 02:13 の 1点** を 24時間 運んでいました。**畳みの陽性対照はこの刻**。
SPLIT_CUT = "2026-09-11T22:59:21+09:00"


def test_畳みの陽性対照_上限と点が食い違う刻では点を取ること() -> None:
    """**上限へ戻したら落ちる検査**（2026-09-12 04:0x・optimizer・Opus）。

    `side` を `max(diffs)` へ戻すと、この刻の答えは `齢＋長さ` になって落ちます
    ＝ **畳みが本当に効いているか**を、実物の刻 1つ で押さえる。
    """
    rows = _rows()
    keep = {o for o in _occasions(rows) if o <= SPLIT_CUT}
    if SPLIT_CUT not in keep:
        pytest.skip("台帳がこの刻を持っていない（切り詰めた台帳で走らせている）")
    g = trend.gate_span(_truncated(rows, keep))
    if g["side_hi"] is None:
        return
    assert g["side_now"] < trend.GAP_SPLIT <= g["side_hi"], (
        f"この刻は 2つ の読み方が食い違う刻として選んであります"
        f"（点 {g['side_now']:.4f}・上限 {g['side_hi']:.4f}）—— 台帳が変わったら選び直すこと")
    assert g["side"] == "齢だけ", (
        f"側が {g['side']} ＝ 上限（{g['side_hi']:.4f}）で読んでいます。"
        "2026-09-12 04:0x に畳んで、**点（`side_now`）で読む**と決めました（`gate_span` の註）")


def test_側の振れ幅は上限が下限以上であること() -> None:
    g = trend.gate_span(_rows())
    if g["side_hi"] is None:
        return
    assert g["side_lo"] <= g["side_now"] <= g["side_hi"] or g["side_lo"] <= g["side_hi"]


def test_そろっていない点は側の上限を独り占めしないこと() -> None:
    """**陽性対照つきの本命。** `SIDE_MIN_PAIRS` を外すと、帯の分母がそろう前の点
    （実測 帯 18 対 11〜13組・差 0.94〜1.44倍）が上限を独り占めします。
    いまの上限がそれより**ずっと小さい**ことで、門が効いているのを見る。
    """
    g = trend.gate_span(_rows())
    if g["side_hi"] is None:
        return
    assert g["side_hi"] < 0.9, (
        f"側の差の上限が {g['side_hi']} ＝ そろう前の点（帯 18 対 11〜13組）を読んでいます。"
        "`SIDE_MIN_PAIRS` が効いているかを見ること")


def test_側の門の数は_informative_の_20組_と同じであること() -> None:
    """**写しを 2つ 持たない** —— `informative` の註が「20組 を越えるまでは まだ測れていない」
    と書いている数と、側に当てる数は同じもの。片方だけ動いたら教える。"""
    assert trend.SIDE_MIN_PAIRS == 20
