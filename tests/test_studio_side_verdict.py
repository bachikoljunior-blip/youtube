"""**覆る条件 (5)(6) を、毎周 印字する口で見張る**（2026-09-12 03:1x JST・optimizer・Opus）。

§5 の「教訓の形（7つ目）」: **覆る条件を註に書いたら、その条件を読む印字も一緒に作ること。**
`gate_span` の (5)(6) は 2026-09-10 12:3x に註へ書かれてから印字が無く、
**(5) が引かれた回（09/12 03:0x）に、引かれたと言う口がどこにも在りませんでした。**

註と derivation は `studio/trend.py` の `side_verdict`。
"""
import json
import pathlib

from studio import trend

LEDGER = pathlib.Path(__file__).resolve().parents[1] / "data" / "studio" / "ledger.jsonl"


def _rows() -> list[dict]:
    return [json.loads(l) for l in LEDGER.read_text().splitlines() if l.strip()]


def test_側の判定は_gate_span_と同じ数を読む() -> None:
    """**2つ の口が別々の数を言わないこと** —— 印字が 2か所 に割れると、読まれるのは印字のほう（§5 7つ目）。"""
    rows = _rows()
    g, v = trend.gate_span(rows), trend.side_verdict(rows)
    assert v["n"], "本物の台帳で 24時間 の窓が埋まった点が 0 件"
    assert abs(float(g["side_hi"]) - float(v["hi"])) < 1e-9, (
        f"`gate_span` は {g['side_hi']}・`side_verdict` は {v['hi']} ＝ 門が 2か所 に割れています")
    assert abs(float(g["side_lo"]) - float(v["lo"])) < 1e-9
    assert g["side"] == v["side"]


def test_引かれたかは上限で決まる() -> None:
    """(5) は **上限** で引く（下限で読むと、帯の中を続けて撃った回に本の側が動かないまま引ける）。"""
    v = trend.side_verdict(_rows())
    assert v["under"] == (float(v["hi"]) < trend.GAP_SPLIT)
    assert v["narrow"] == ((float(v["hi"]) - float(v["lo"])) < trend.GAP_SPLIT)
    assert (int(v["run"]) >= 1) == bool(v["under"])
    assert (int(v["narrow_run"]) >= 1) == bool(v["narrow"])


def test_続いた回数は測りで数える() -> None:
    """**周ではなく測りで数える**（穴埋めの周は 1周 に 2回 立つ・`side_verdict` の註）。
    `run` は 24時間 の窓が埋まった点の数を越えられない。"""
    v = trend.side_verdict(_rows())
    assert 0 <= int(v["run"]) <= int(v["n"])
    assert 0 <= int(v["narrow_run"]) <= int(v["n"])


def test_印字は引かれたときに手を言う() -> None:
    """引かれた回は **§7 (2) の見出しを直すこと** と **床を一緒に見ること** を言う（(5) の註）。"""
    rows = _rows()
    line = trend._side_verdict_line(rows)
    v = trend.side_verdict(rows)
    assert "(5)" in line and "(6)" in line
    assert str(v["side"]) in line
    if v["under"]:
        assert "§7 (2)" in line and "床" in line, f"引かれたのに手が出ていません: {line}"
    else:
        assert "引かれません" in line
    assert line in trend._span_line(rows), "`trend` の毎周の印字に載っていません"


def test_窓が埋まっていない点は数えない() -> None:
    """**24時間 の窓が埋まっていない点は上限を低く見せる**（`side_verdict` の覆る条件 (3)）。
    ＝ 窓の頭の点は `n` に入らない。"""
    rows = _rows()
    v = trend.side_verdict(rows)
    ds = [p for p in trend._span_points(rows, trend.GATE_SPAN_H * 2) if p["diff"] is not None]
    assert int(v["n"]) < len(ds), (
        "48時間 の点が全部 数えられています ＝ 窓の頭を落とす枝が効いていません")


def test_陽性対照_差を門の上へ動かすと引かれなくなる() -> None:
    """**壊したら落ちるまで撃つ**（§5 の「教訓の形」3つ目）。
    いちばん新しい点の差を門の上へ持ち上げると、(5) は引かれなくなる。"""
    rows = _rows()
    base = trend.side_verdict(rows)
    real = trend._span_points

    def fake(r: list[dict], hours: float) -> list[dict]:
        got = [dict(p) for p in real(r, hours)]
        for p in got:
            if p["diff"] is not None:
                p["diff"] = float(p["diff"]) + trend.GAP_SPLIT
        return got

    trend._span_points = fake  # type: ignore[assignment]
    try:
        broken = trend.side_verdict(rows)
    finally:
        trend._span_points = real  # type: ignore[assignment]
    assert base["under"] and not broken["under"], (
        f"差を {trend.GAP_SPLIT} 持ち上げても判定が変わりません: {base['hi']} → {broken['hi']}")
    assert broken["side"] == "齢＋長さ"


def test_陽性対照_窓は効いている() -> None:
    """`hours` を縮めると「窓が埋まった点」は減る（`n` ≒ 直近 `hours` の測りの回数）。

    ＝ **窓を縮めるほど `run` は長く見えます**（同じ台帳で 24時間 1回 → 6時間 10回）——
    続いた回数は窓の長さの関数なので、`SIDE_RUN_LAPS` は `GATE_SPAN_H` と一緒にしか読めません
    （`side_verdict` の覆る条件 (1)）。
    """
    rows = _rows()
    wide = trend.side_verdict(rows, hours=trend.GATE_SPAN_H)
    narrow = trend.side_verdict(rows, hours=trend.GATE_SPAN_H / 4)
    assert int(narrow["n"]) < int(wide["n"]), (
        f"窓を 4分の1 にしても点の数が動きません（{narrow['n']} 対 {wide['n']}）"
        " ＝ `hours` が効いていません")


def test_空の台帳でも落ちない() -> None:
    assert trend.side_verdict([])["n"] == 0
    assert trend._side_verdict_line([]) == ""
    assert trend.side_verdict([{"event": "built", "at": "2026-09-12T03:00:00+09:00"}])["n"] == 0
