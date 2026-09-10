"""**同じ周の 3回 読みが割れるのは、齢ではなく「いま伸びたか」** ——
§7 (h) の覆る条件 (3) が 2026-09-10 10:2x に初めて引かれ、引いた数を見たら第3の口ではなかった。

註と derivation は `studio/trend.py` の `shakes`。要点だけ:
(3) は「`n_values > 1` が **齢 48h 超の行**で出たら第3の口 ＝ 中央値へ」だったが、
実際に引いた `EkNqtkK49Bw`（齢 96.3h・142 対 141）の低いほうは **41分 前の台帳の行の値そのもの**で、
本は 140 → 141 → **142** と伸びている ＝ **遅れた複製**。
中央値へ移すと 141（いちばん新しい値）を捨て、伸び中の本では 192〜249回 を捨てうる
＝ `max` が直した当の -74回 の誤りへ戻る。**齢 48h 超は「落ち着いた」ではない。**
"""
import json
import pathlib

from studio import trend

LEDGER = pathlib.Path(__file__).resolve().parents[1] / "data" / "studio" / "ledger.jsonl"


def _rows() -> list[dict]:
    return [json.loads(l) for l in LEDGER.read_text().splitlines() if l.strip()]


def _row(vid: str, age: float, views: int, *, n: int = 1, lo: int | None = None) -> dict:
    r = {"event": "measured", "id": vid, "age_h": age, "views": views,
         "n_values": n, "at": f"2026-09-10T{int(age) % 24:02d}:00:00+09:00"}
    if lo is not None:
        r["views_min"] = lo
    return r


# ---------- 実物（§5 の教訓の形 4つ目: 直した門が実物のどの形を通るかを列挙する） ----------

def test_本物の台帳では割れた行は全部_遅れの側() -> None:
    sh = trend.shakes(_rows())
    assert sh, "本物の台帳に `n_values > 1` の行が 1つも無い —— measure が n_values を書いていない"
    still = [s for s in sh if s["verdict"] == "still"]
    assert not still, f"第3の口が出た。`trend.shakes` の覆る条件 (1) を撃つこと: {still}"


def test_齢_48h_超で割れた行は_低いほうが窓で通った値() -> None:
    """(3) を引いた当の行。**齢は 48h 超・しかし低いほうは本がこの窓で通った値** ＝ 遅れの側。

    **2026-09-10 13:4x にここを書き直した。** 前の形は `len(set(rounds)) > 1`（＝ 推定が
    直近 3周 で動いたか）を見ており、**`1huadpEk6HY`（齢 148.1h・5 対 6・rounds [6,6,6]）で
    落ちました** —— 5 は 83分 前の台帳の値そのものなので遅れの側なのに、周の門は
    「動いていない」＝ 第3の口 と貼る。**周は代理で、遅れは時間で起きます**
    （`trend._lag_evidence` の註）。
    """
    sh = [s for s in trend.shakes(_rows()) if s["age_h"] > 48]
    assert sh, "齢 48h 超で割れた行が消えた —— (3) の分子が 0 に戻ったなら、この検査ごと見直すこと"
    for s in sh:
        assert s["verdict"] == "lag"
        assert s["floor"] is not None and s["low"] >= s["floor"], \
            f"低い読みが窓の先頭より下なのに `lag` と呼んでいる: {s}"


# ---------- 陽性対照（落ちるまで撃つ・§5 の教訓の形 3つ目） ----------

def test_陽性対照_窓で1度も通っていない低い読みは第3の口() -> None:
    # **齢は 48h の下**に置く —— 古い門（齢だけ）では拾えない形で、新しい門だけが拾う
    rows = [_row("X", 28.0, 500), _row("X", 29.0, 500), _row("X", 30.0, 500, n=2, lo=498)]
    s, = trend.shakes(rows)
    assert s["age_h"] < 48
    assert s["verdict"] == "still", "窓の先頭より下の読みを遅れ扱い ＝ 門が効いていない"
    assert s["floor"] == 500 and s["low"] == 498
    assert "第3の口が出ています" in trend.shakes_line(rows)


def test_陰性対照_窓の先頭より上なら_台帳が書いていなくても遅れ() -> None:
    """点と点のあいだの値に複製が座ることは在る（台帳は 41分ごとにしか見ていない）。
    **完全一致だけを条件にすると、そこを第3の口に化かします**（`_lag_evidence` の註）。"""
    rows = [_row("X", 60.0, 480), _row("X", 61.0, 500), _row("X", 62.0, 500, n=2, lo=498)]
    s, = trend.shakes(rows)
    assert s["verdict"] == "lag" and s["held_h"] is None and s["floor"] == 480


def test_陽性対照_齢で切る古い門なら_実物が第3の口になる() -> None:
    """**元の手と違う物を見ているか**（§5 の教訓の形）。齢 48h 超の行は実物に在り、
    古い門（齢だけ）はそれを第3の口と呼ぶ。新しい門は呼ばない ＝ 2つは違う答えを返す。"""
    sh = trend.shakes(_rows())
    old_gate = [s for s in sh if s["age_h"] > 48]          # 齢だけで切る門
    new_gate = [s for s in sh if s["verdict"] == "still"]   # 低い読みが窓で通った値かで切る門
    assert old_gate and not new_gate, "2つの門が同じ答え ＝ 足しても増えていない"


def test_周の門と範囲の門は_実物で1行_割れる() -> None:
    """**確かめる手を足すときは、それが元の手と違う物を見ているかを先に撃つ**（§5 の教訓の形）。
    10:2x の周の門（推定が直近 3周 動いたか）と 13:4x の範囲の門は、実物で **1行** 割れる ——
    `1huadpEk6HY`（rounds [6,6,6] ＝ 周の門は第3の口・低い 5 は窓で通った値 ＝ 範囲の門は遅れ）。
    **0行 になったら、周の門を落としてよい**（`trend.shakes` の覆る条件 (3)）。
    """
    sh = trend.shakes(_rows())
    split = [s for s in sh
             if (len(set(s["rounds"])) == 1 and len(s["rounds"]) >= trend.SETTLED_ROUNDS)
             != (s["verdict"] == "still")]
    assert split, "2つの門が実物で1行も割れない ＝ 周の門を落とす番（覆る条件 (3)）"


# ---------- 陰性対照 ----------

def test_陰性対照_伸びた直後は齢がいくつでも遅れ() -> None:
    rows = [_row("X", 90.0, 140), _row("X", 91.0, 141), _row("X", 92.0, 142, n=2, lo=141)]
    s, = trend.shakes(rows)
    assert s["verdict"] == "lag", "伸びた直後の割れを第3の口と呼んでいる（実物 EkNqtkK49Bw の形）"
    assert s["low"] == 141 and s["high"] == 142 and s["span"] == 1


def test_陰性対照_割れていない行は挙げない() -> None:
    assert trend.shakes([_row("X", 60.0, 500), _row("X", 61.0, 500)]) == []
    assert "0行" in trend.shakes_line([_row("X", 60.0, 500)])
