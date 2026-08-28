"""`src/pair_sweep.py`（M19 の2手目）を、**既知の当たりで**固定する。

`docs/trigger_main.md` §4 ——
> **`src/` に道具を新しく足す回は、「既知の当たり」を1件、検査に先に固定すること。**

この手段の既知の当たりは **`gassan`（高額介護合算療養費・7節）**、
つまり **`kogaku` × `kaigo`** の1組だけです（n=1）。
`tests/test_calc_axes.py` が「**入力の軸では組にならない**」を固定しているので、
こちらは**出力の側で何が起きたか**を固定します。

**2つに割れました。片方は緑・片方は赤（＝まだ届いていない）**ので、
そのまま2本の検査にしてあります。**赤いほうを消さないこと。**
"""
from src import pair_sweep


def test_既知の当たりの2本は_出力の側なら母数に入る():
    """`kogaku` も `kaigo` も、**同じ単位の並び**を出す（＝組の母数に入る）。

    **ここが 2026-08-19 の前進です。** それまでは2本とも1本も出しておらず、
    組にすらなれませんでした。塞いだ穴は2つ:

    1. `_enum_with` —— `kogaku.limit(name, cost)` と `kaigo.pay(level, used_units,
       rate)` は「**文字列の引数**と**既定値の無い数値の引数**を同時に持つ」形で、
       `section_sweep._enum_axis` は候補をその引数だけで呼ぶので必ず落ちます
    2. `unit_of` の**接尾一致** —— `1か月あたりの医療費` を「か月」、
       `1年の合計` を「年」と読んでいて、`kogaku` の円の欄が円の組に入らなかった
    """
    kogaku = [s for s in pair_sweep.series_of("kogaku") if s["unit"].startswith("円")]
    kaigo = [s for s in pair_sweep.series_of("kaigo") if s["unit"].startswith("円")]
    assert kogaku, "kogaku から円の並びが1本も出ていません（_enum_with / unit_of）"
    assert kaigo, "kaigo から円の並びが1本も出ていません（_enum_with / unit_of）"


def test_既知の当たりは_比の形で出る():
    """**2026-08-28 に、赤から緑へ書き換えました**（前の版が指示していたとおり）。

    前の版はこう書いて、**9日 赤いまま**でした ——
    「`gassan` の7節は『**医療だけで年間限度額の 95.0〜96.4% が埋まる**』という
    **和に対する割合**で、いまの3つはどれもその形を見ていない。
    **足りないのは母数ではなく形のほう**。次に触る回は形を1つ増やすこと
    （例: `A ÷ (A+B)` が区間で一定に近い）」。

    `pair_sweep._share_band` がその形です。**帯まで見ること** ——
    「出た」だけを固定すると、`_span(A) < MOVES` の穴（定数 ÷ 定数の 0pt）が
    戻っても緑のままになります。実測でその穴が上位12件を丸ごと埋めました。
    """
    hits = pair_sweep.sweep_pairs(["kogaku", "kaigo"])
    assert hits, "既知の当たり（kogaku × kaigo）が1件も出ていません"
    assert hits[0]["形"] == "比の形", hits[0]
    lo, hi = (float(v.rstrip("%")) for v in hits[0]["詳しく"]["割合"].split("〜"))
    assert 90.0 <= lo <= hi <= 98.0, (
        f"帯が `gassan` の 95.0〜96.4% から離れています: {lo}〜{hi}")
    assert hi - lo > 0.0, "帯の幅が 0pt です（定数 ÷ 定数の穴が戻っています）"


def test_動かない並びは_比の形にしない():
    """`_span(A) < MOVES` を捨てる門。**これが無いと上位が丸ごと偽物になります。**

    実測（2026-08-28 の試作）: 門を入れる前の 260件 のうち、
    **上位12件すべて**が `year_with_multi_hit` の定数欄（帯の幅 0.000pt）でした。
    定数 ÷ (定数 ＋ 定数) は必ず一定なので、当然そうなります。
    `_echoes` が塞いだのと同じ穴が、割り算の形で出てきたものです。
    """
    flat = {"ys": [100000.0] * 8}
    # `_span` は (最大 − 最小) / 最大 なので、**`SHARE_MOVES`（0.30）を超える幅**にする
    moves = {"ys": [100000.0 * (1.0 + 0.1 * i) for i in range(12)]}
    other = {"ys": [5000.0] * 8}           # `gassan` と同じ比（相手が 3〜5% を占める）
    assert pair_sweep._share_band(flat, other) is None, "動かない A を拾っています"
    assert pair_sweep._share_band(moves, other) is not None
    # **`MOVES`（5%）では足りません**（2026-08-28 に測り直した）。
    # 5% しか動かない A は、帯が細くなるのが算術上あたりまえ。
    small = {"ys": [100000.0 * (1.0 + 0.01 * i) for i in range(8)]}
    assert pair_sweep._share_band(small, other) is None, (
        "A が 7% しか動かない組を拾っています —— `SHARE_MOVES` が緩んでいます")


def test_比の形は_端に張り付いたら節にしない():
    """`SHARE_EDGE`。99.9% は「相手が無視できる」だけで、2つを並べたことにならない。"""
    big = {"ys": [1_000_000.0 * (1.0 + 0.1 * i) for i in range(12)]}
    tiny = {"ys": [10.0] * 8}
    assert pair_sweep._share_band(big, tiny) is None


def test_入力をそのまま返す欄は_組にしない():
    """`_echoes`。**これが無いと一覧の上位が丸ごと偽物になります。**

    埋める代表値は軸ごとに1つなので、所得の軸を持つ関数はどれも同じ目盛りで
    振られます。入力をそのまま返す欄は**表がちがっても並びが同じ**になり、
    崖の高さが 0.00% で「一致」しました（実測 18件中8件）。
    """
    xs = [100.0, 200.0, 400.0]
    assert pair_sweep._echoes(xs, list(xs))
    assert not pair_sweep._echoes(xs, [100.0, 200.0, 401.0])


def test_単位は名前の末尾でだけ引く():
    """`1か月あたりの医療費` は「か月」ではありません（2026-08-19 に踏んだ）。"""
    assert pair_sweep.unit_of("1か月あたりの医療費", [750000.0, 972630.0]) == "円?"
    assert pair_sweep.unit_of("1年の合計", [676890.0, 690248.0]) == "円?"
    assert pair_sweep.unit_of("実効の負担率", [22.2, 30.0]) == "%"
    assert pair_sweep.unit_of("限度額の倍率", [7.0, 7.2]) == "倍"


def test_拾う形は宣言したものだけ():
    """`SHAPES` が正本。**形を足したらここが赤くなります**（宣言させるため）。"""
    hits = pair_sweep.sweep_pairs(["kaigo", "kogaku", "iryohi", "inshi"])
    for h in hits:
        assert h["形"] in pair_sweep.SHAPES, h


def test_期間は名前の途中で引く():
    """**単位とは逆で、期間は欄の名前の途中に出ます**（2026-08-28 に足した）。

    `unit_of` が末尾だけを見るのは正しい（`1か月あたりの医療費` の「か月」は
    単位ではない）。**その同じ語が、期間としては正しい合図**です。
    """
    assert pair_sweep.period_of("1か月あたりの医療費") == "月"
    assert pair_sweep.period_of("1年の合計") == "年"
    assert pair_sweep.period_of("多数回の額（1か月）") == "月"
    # 期間の言い方に見えて、そうではない語（`_PERIOD_NOT`）
    assert pair_sweep.period_of("年収") is None
    assert pair_sweep.period_of("39歳の保険料") is None
    # 名前が黙っている欄は `None`。**推測しないこと**（弾きすぎると当たりが落ちる）
    assert pair_sweep.period_of("保険料") is None


def test_月額と年額は組にしない():
    """**この検査が、2026-08-28 の実測を固定します。**

    `比の形` の上位に `kogaku × kokuho`（90.3%〜95.1%）が出ていましたが、
    A は `多数回の額` ＝ **月額 44,400円**、B は `保険料` ＝ **年額 415,415円** で、
    **12倍の期間ちがいをそのまま割っていました。**

    **片方でも期間が読めないときは止めません**（`periods_clash` の註）。
    止めると、既知の当たり `kogaku × kaigo` まで落ちます。
    """
    tsuki = {"unit": "円", "period": "月", "axis": None,
             "xs": [1.0, 2.0], "ys": [40_000.0, 44_400.0]}
    toshi = {"unit": "円", "period": "年", "axis": None,
             "xs": [1.0, 2.0], "ys": [400_000.0, 415_415.0]}
    fumei = {"unit": "円", "period": None, "axis": None,
             "xs": [1.0, 2.0], "ys": [400_000.0, 415_415.0]}

    assert pair_sweep.periods_clash(tsuki, toshi)
    assert not pair_sweep.periods_clash(tsuki, fumei)
    assert not pair_sweep.periods_clash(fumei, fumei)
    assert pair_sweep.pair_hits(tsuki, toshi) == []


def test_期間の読めた欄が並びに載る():
    """`series_of` が `period` を持たない版に戻ったら、ここが落ちます。"""
    rows = pair_sweep.series_of("kogaku")
    assert rows, "kogaku から並びが1本も出ていません"
    assert all("period" in r for r in rows)
    assert {r["period"] for r in rows} != {None}, (
        "kogaku の欄から期間が1つも読めていません"
        "（`多数回の額（1か月）` などの改名が戻っていないか）")
