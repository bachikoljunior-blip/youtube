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

def test_本物の台帳に_maxが高すぎた行は無い() -> None:
    """**2026-09-10 20:2x に分子をもう一度 移しました** —— `confirmed`（低い読みが一過性）ではなく
    **`over_max`**（その本の確定した水準より高い値を `max` が台帳に書いた行）です。

    19:0x は「`still` かつ あとの点が高い側へ戻った」を分子に置きましたが、
    **その決着が 20:2x に 1行 出て、同じ行が「中央値へ移す」を否定しました** ——
    あとの点が高い側なら低い読みは捨ててよい側（`max` が正解）・低い側で水準になれば
    それは数え直しで、包絡を落とすのは `recounts()` の仕事です。
    **＝ 割れの決着は、どちらへ転んでも `settle_stats` を動かしません**（`trend.shakes` の註）。

    **【2026-09-12 13:3x に、この検査の主張を「行が 0」から「大きさが門の下」へ移しました】**
    （optimizer・Opus）。**行は実物で 4行 出ました**（`EkNqtkK49Bw` 145 対 146・本物の掘り起こし）。
    **それでも `settle_stats` は動かしません** —— 掘り起こし 1回 対 割れ 249回 ＝ 0.4%
    （門 10%）。**数と決めと覆る条件は `trend.over_verdict` の註**（ここには写さない）。
    ＝ **回数で赤くする検査は、1回 の掘り起こしで 249回 を直している側の物差しを倒せました。**
    """
    sh = trend.shakes(_rows())
    assert sh, "本物の台帳に `n_values > 1` の行が 1つも無い —— measure が n_values を書いていない"
    ov = trend.over_verdict(_rows())
    assert not ov["drawn"], (
        "掘り起こしの大きさが門を越えた。`trend.over_verdict` の覆る条件 (1) を撃つこと"
        f"（`reads=5` の中央値と最大を並べる）: {ov}")
    # **(2) 形の見張り** —— 3本 以上 の別々の本で出たら、比が門の下でも形を見直すこと
    assert len(ov["ids"]) < 3, f"掘り起こしが 3本 以上 で出た ＝ 覆る条件 (2): {ov}"
    # **(3) 分母が読めない台帳になったら、比ではなく絶対値で切る**
    if ov["worst_span"] < 10:
        assert ov["worst_over"] < 5, f"割れの最大が 10回 未満 ＝ 絶対値の門で見ること: {ov}"
    # **決着の内訳を、次の回が手で数えなくてよいように押さえる**（20:2x の実測: high 26 / low 1）
    settled = [s for s in sh if s["after"] in ("high", "low")]
    assert settled, "決着した行が 1行も無い ＝ `_settled_after` が動いていない"
    lows = [s for s in settled if s["after"] == "low"]
    known = {r["id"] for r in trend.recounts(_rows())}
    for s in lows:
        if s["verdict"] == "recount" or s["id"] in known:
            continue
        # **2026-09-10 21:5x に 3つ目の枝を足しました**（optimizer・Opus。実測で落ちた）——
        # `CIPYV_r1Hdo` 齢 103.5h・287 対 290・`held_h` **1.21時間**。
        # `recounts()` は生が包絡を `ENVELOPE_LAG_H`（6.0時間）より長く下回るまで挙げないので、
        # **どの本の 1度目の数え直しも、決着した瞬間は必ずこの形**になります
        # （`trend.shakes` の 19:0x の註が、まさにそう書いてあった側）。
        # ＝ ここで赤くしていたのは道具ではなく**この検査の主張**でした
        # （METHOD §5 の教訓の形 3つ目「落ちなければ、疑うのは道具ではなく検査のデータ」の裏返し）。
        held = s["held_h"]
        assert held is not None and held < trend.ENVELOPE_LAG_H, (
            "低い側で水準になり、しかも生が包絡を "
            f"{trend.ENVELOPE_LAG_H}時間 より長く下回っているのに `recounts()` が挙げていない "
            f"＝ 数え直しの機構そのものを見ること: {s}")


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
    # **2026-09-10 17:3x に 3つ目の札が出ました**（`recount`）——`lywTMXD6WDM` 齢 103.4h・213 対 214。
    # 低いほうは窓の先頭 214 より下ですが、**この本は `recounts()` が挙げている**（216→214）＝
    # 「再生は減らない」を前提にした窓の門が当たらない本です（`trend._settled_after` の註）。
    # **2026-09-10 19:0x に 4つ目の状態が出ました**（`still` かつ **保留**）——`CIPYV_r1Hdo`
    # 齢 101.6h・290 対 287。低いほうは窓の先頭より下だが `recounts()` はまだ挙げられない
    # （1度目の数え直しは `hours_below` が 0）＝ **決着が付くまで分子に入れない**。
    recounted = {r["id"] for r in trend.recounts(_rows())}
    for s in sh:
        assert s["verdict"] in ("lag", "recount", "still")
        if s["verdict"] == "recount":
            assert s["id"] in recounted, f"数え直しの本でないのに `recount` と貼っている: {s}"
            continue
        if s["verdict"] == "still":
            assert s["floor"] is not None and s["low"] < s["floor"], \
                f"窓で通った値なのに `still` と呼んでいる: {s}"
            assert not s["over_max"], f"`max` が確定した水準より高い ＝ 覆る条件 (1) を撃つこと: {s}"
            continue
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
    # **札は出るが、あとの点が無いので決着していない**（2026-09-10 19:0x）
    assert s["confirmed"] is False
    assert s["over_max"] is False
    assert "保留 1行" in trend.shakes_line(rows)
    # あとの点が高い側へ戻れば決着（＝ 2つの状態が同じ字にならないこと）。
    # **それでも分子（`max` が高すぎた行）は 0 のまま**（2026-09-10 20:2x）
    back = rows + [_row("X", 31.0, 500), _row("X", 32.0, 500)]
    assert trend.shakes(back)[0]["confirmed"] is True
    assert trend.shakes(back)[0]["over_max"] is False
    line = trend.shakes_line(back)
    assert "低い読みが一過性 1行" in line
    assert "掘り起こした行 0行" in line


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
    assert old_gate, "齢 48h 超で割れた行が実物から消えた ＝ この対照ごと見直すこと"
    assert len(new_gate) < len(old_gate), "2つの門が同じ答え ＝ 足しても増えていない"
    # **3つ目の門（`max` が水準を掘り起こしたか）も、2つ目と違う答えを返すこと**
    # （2026-09-10 20:2x・門は 2026-09-11 03:0x）—— **実物の分子は 0**。
    #
    # **2026-09-11 03:0x に、ここの土台が実物から消えました**: 19:0x/20:2x が撃った
    # `CIPYV_r1Hdo` の `still` は、その本を `recounts()` が挙げた時点で `recount` に変わり、
    # いま実物の `still` は **0行**（この検査は「消えたら見直すこと」と書いてあった）。
    # → **`still` が在ることを前提にした行は、合成の対照のほうへ移しました**
    #   （`test_studio_shakes_confirmed.py` の陰性／陽性 2件）。ここに残すのは
    #   **実物で分子が 0 であること**だけ ＝ 実物と合成の役目を分ける。
    #
    # **2026-09-12 13:3x に、ここも「行 0」から「大きさが門の下」へ移しました**
    # （`trend.over_verdict` の註。実物は 4行 出ており、行では 0 に戻りません）。
    assert not trend.over_verdict(_rows())["drawn"], \
        "実物の掘り起こしが大きさの門を越えた ＝ `trend.over_verdict` の覆る条件 (1) を撃つこと"
    assert not [s for s in sh if s["verdict"] == "still" and s["over_max"]], \
        "`still` と `over_max` が同じ答え ＝ 門を足しても増えていない"


def test_陽性対照_掘り起こしが割れと同じ大きさなら門を越える() -> None:
    """**2026-09-12 13:3x の大きさの門**（`trend.over_verdict`）。

    水準 287 に落ち切ってから `max` が **350** を書いた ＝ 掘り起こし **+63回**。
    同じ台帳の割れの最大も 63回 なので比は 100% ＝ **門 10% を越える**。
    """
    base = 85.0
    rows = [_row("C", base + 0.7 * i, 287) for i in range(14)]
    rows += [_row("C", base + 0.7 * 14, 350, n=2, lo=287)]
    rows += [_row("C", base + 0.7 * (15 + i), 287) for i in range(12)]
    s = [x for x in trend.shakes(rows) if x["over_max"]]
    assert len(s) == 1 and s[0]["over_by"] == 63
    ov = trend.over_verdict(rows)
    assert ov["drawn"] is True and ov["worst_over"] == 63 and ov["worst_span"] == 63
    assert "門を越えました" in trend.shakes_line(rows)


def test_陰性対照_1回の掘り起こしは_249回の割れを倒さない() -> None:
    """**この回に実物で出た形**（`EkNqtkK49Bw` 145 対 146 ＝ 掘り起こし +1回）を、
    `max` が直している側の割れ（249回）と同じ台帳に置く。**比 0.4% ＝ 門の下。**

    **回数の門（「1行 でも出たら」）はここで倒れました** —— 行は在るのに、
    `settle_stats` を動かす理由にならない（`trend.over_verdict` の註）。
    """
    rows = [_row("A", a, 145) for a in (128.0, 130.0, 132.0, 134.0)]
    rows += [_row("A", 134.9, 146, n=2, lo=145), _row("A", 136.1, 145),
             _row("A", 137.5, 146, n=2, lo=145), _row("A", 138.3, 146, n=2, lo=145)]
    rows += [_row("A", a, 145) for a in (140.7, 142.2, 143.1, 144.1, 145.0, 145.9, 146.8)]
    # 伸び中の本の遅れた複製（`max` が直している側・実測 637 対 886）
    rows += [_row("B", 8.0, 637), _row("B", 10.0, 886, n=2, lo=637), _row("B", 11.0, 886)]
    ov = trend.over_verdict(rows)
    assert ov["rows"] == 3 and ov["worst_over"] == 1 and ov["worst_span"] == 249
    assert ov["drawn"] is False, "1回 の掘り起こしで 249回 を直している側を倒している"
    assert "門の下" in trend.shakes_line(rows)


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
