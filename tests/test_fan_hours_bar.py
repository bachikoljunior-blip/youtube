"""**同じ門を、2つの解き方で解いていた。** その片方を固定する。

## 何が壊れていたか（2026-08-31・最適化の回。この回に自分で撃った数）

`scripts/eta.py` は、視聴時間の門を**2か所**で解いています:

    門2a （上の段・4,000時間）  `_long_break_even()` ＝ **合格点**を解く
                                「長尺1本あたり何回 再生されれば、窓365日で埋まるか」
    門2a'（下の段・3,000時間）  `_days_to(残り, いまの伸び)` ＝ **伸び率の外挿**

長尺の直近365日は **2.5時間** ＝ 伸びが 0 と区別できません。**0で割るので、
外挿は必ず「届きません」を返します。** 上の段には、その断りが初日から
印字されています ——

    「延ばした数が無限なのは、長尺が弱いからではなく**まだ出していない**から」

**下の段だけ、その断りも合格点も付いていませんでした。** そして下の段は
3つの脚すべてで上の段より手前です（登録者 1/2・時間 3/4・ショート 3/10）。
**いちばん手前の門を、いちばん悲観的な解き方で解いていた**ということです。

## 合格点で解いた数（規則 1本/日 × 窓365日・いちばん甘い形）

    脚                                合格点     この機械の記録    倍率
    門2a' 下の段 3,000時間                176回/本   長尺 156回     **×1.13**
    門2a  上の段 4,000時間                235回/本   長尺 156回       ×1.51
    門2b' 下の段 ショート90日 300万回   33,333回/本   ショート1,891回  ×17.6
    門2b  上の段 ショート90日1,000万回 111,111回/本   ショート1,891回  ×58.8

**×1.13 が、この機械のどの門の脚よりも近い数です。**

## このテストが守っているもの

1. **下の段が、上の段と同じ式で解かれていること**（合格点が有限で出ること）
2. **その合格点が、門の比そのものであること**（3,000/4,000 の比になる）
3. **到達日が1日も動いていないこと** —— 合格点は「どこが近いか」を出すだけで、
   日付の入力ではありません。**入力にしたら、未測定の維持率で日付が動きます**
4. **裸の「届きません」に戻していないこと**（印字の側）

## **このテストは、壊して落ちることを確かめてあります**（2026-08-31）

一度も落ちたことのない検査は証拠ではないので、4つとも**先に壊して**
赤くしてから置きました。`docs/JOURNAL.md` の同日の項に、何をどう壊したかがあります。

## 覆る条件

- **`LONG_SHAPES`（尺×維持率）は推測です。** 維持率の実測が入ったら、
  合格点の絶対値は動きます。**このテストが見ているのは比のほう**なので、
  そこは落ちません
- 長尺の記録 156回 は**打ち切られた下限**（`settle.settles_at('長尺')` は
  どの地平でも伸びきる年齢を返しません）。**倍率は上限側**に出ています
- **公表値が変わったら**（3,000時間／365日窓）取り直すこと
- **ファン課金の分子（加入率・単価）が実測で1件でも入ったら**、
  ここは「門までの距離」しか見ていないので、分子の側は別に固定すること
"""

import math

import pytest

import scripts.eta as eta


def _analysed():
    points = eta._points()
    if not points:
        pytest.skip("積んだ点がありません（data/eta.jsonl が空）")
    return points[-1], eta.analyse(points[-1], points)


def test_fan_hours_leg_is_solved_as_a_bar_not_only_as_an_extrapolation():
    """**下の段にも合格点が出ること。**

    ここが無いあいだ、門2a' は `days_fan_hours`（＝伸び率の外挿）だけで
    「届きません」と印字されていました。**外挿は 0 で割るので必ず無限**です。
    """
    m, a = _analysed()
    bar = a.get("fan_hours_bar")
    assert bar, "下の段の合格点が出ていません（`_fan_hours_bar` が呼ばれていない）"
    assert math.isfinite(bar["bar"]), (
        "下の段の合格点が無限です。門2a' を外挿だけで解いた状態に戻っています"
    )
    assert bar["bar"] > 0
    # 規則（1日1本）で解くこと。ここが規則より大きいと、合格点が甘く出ます。
    from src import house_rule
    assert bar["per_day"] == float(house_rule.PUBLISH_PER_DAY), (
        "合格点を、規則（1日1本）より多い本数で解いています"
    )
    assert bar["days"] == float(eta.LONG_HOURS_WINDOW_DAYS), (
        "窓が門の窓（直近12か月）と違います。上の段と 9倍 ずれます"
    )


def test_the_bar_is_the_gate_ratio_of_the_upper_tier():
    """**同じ式であることを、比で固定する。**

    下の段（3,000時間）と上の段（4,000時間）は、**分子の門だけが違う**同じ式です。
    だから合格点の比は、残り視聴分の比に一致しなければいけません。
    **一致しないなら、どちらかが別の窓・別の本数で解かれています。**
    """
    m, a = _analysed()
    fan = a["fan_hours_bar"]
    # 上の段を、同じ本数・同じ窓で解き直す（`_gate2_bar` はこの道具の正本）
    rows = a["long_break_even"]
    row = next(r for r in rows if r["label"] == fan["label"])
    ypp = eta._gate2_bar(a, row, fan["per_day"], fan["days"])
    expected = a["fan_minutes_needed"] / a["long_minutes_needed"]
    assert ypp > 0
    assert fan["bar"] / ypp == pytest.approx(expected, rel=1e-9), (
        "下の段と上の段の合格点の比が、門の比になっていません"
    )
    # 下の段のほうが必ず手前（3,000 < 4,000）
    assert fan["bar"] < ypp, "下の段の合格点が上の段より高く出ています"


def test_the_bar_does_not_move_any_date():
    """**合格点は「どこが近いか」を出すだけで、日付の入力ではありません。**

    `LONG_SHAPES` の維持率は**推測**です。日付がそこに乗ったら、
    到達日が推測で動きます（M23 の「帯を増やさない」と同じ縛り）。

    **確かめ方**: 合格点を出す関数をまるごと差し替えて、日付が1つも
    動かないことを見ます。**動いたら、推測が日付に漏れています。**
    """
    points = eta._points()
    if not points:
        pytest.skip("積んだ点がありません")
    m = points[-1]
    before = eta.analyse(m, points)
    keys = ("days_subs", "days_long_hours", "days_shorts_gate", "days_monetized",
            "days_fan_subs", "days_fan_hours", "days_fan_shorts", "days_fan_gate",
            "fan_gate_lead_days")
    orig = eta._fan_hours_bar
    try:
        eta._fan_hours_bar = lambda a: {
            "rows": [], "per_day": 1.0, "days": 365.0, "bar": 1.0, "label": "壊した",
            "record": 1.0, "record_settled": 1.0, "mean": 1.0,
            "ratio": 1.0, "ratio_settled": 1.0, "ratio_mean": 1.0,
        }
        after = eta.analyse(m, points)
    finally:
        eta._fan_hours_bar = orig
    for k in keys:
        assert before[k] == after[k], (
            f"合格点を差し替えたら `{k}` が動きました。"
            "推測（維持率）が到達日に漏れています"
        )


def test_gate_legs_are_ranked_on_one_ruler():
    """**4つの脚が、1つの物差し（記録の何倍か）で並んでいること。**

    倍率が付いていない「届きません」は桁の情報を落とします。
    **並べないと、どの脚が近いか決められません。**
    """
    m, a = _analysed()
    legs = a.get("gate_legs")
    assert legs, "門の脚が並んでいません"
    assert len(legs) == 4, f"脚が4つではありません: {len(legs)}"
    ratios = [lg["ratio"] for lg in legs]
    assert ratios == sorted(ratios), "近い順に並んでいません"
    # **入れた順が、たまたま昇順**（1.13 → 1.51 → 17.6 → 58.8）なので、
    # 上の1行だけでは `sort` を消しても緑のままです（2026-08-31 に踏んだ）。
    # **入れた順と並べた順が食い違う場を作って**、そこで昇順を見ます。
    from src import form_record
    _orig = form_record.per_video_best
    try:
        form_record.per_video_best = lambda: {
            # 長尺の記録を桁で大きくすると、長尺の脚（先に入る）が
            # **いちばん遠い側**へ回り、入れた順 ≠ 昇順 になります。
            "長尺": {"best": 1.0, "best_settled": 1.0, "mean": 1.0},
            "ショート": {"best": 10 ** 9, "best_settled": 10 ** 9, "mean": 10 ** 9},
        }
        shuffled = eta._gate_legs(a)
    finally:
        form_record.per_video_best = _orig
    got = [lg["ratio"] for lg in shuffled]
    assert got == sorted(got), (
        "記録を入れ替えたら並びが崩れました。`_gate_legs` が並べ替えていません"
    )
    assert shuffled[0]["form"] == "ショート", (
        "入れた順のまま返っています（並べ替えが効いていません）"
    )
    assert all(math.isfinite(r) and r > 0 for r in ratios), "倍率が出ていない脚があります"
    # いちばん近い脚は、下の段の視聴時間の脚（門2a'）であること。
    # **ここが入れ替わったら、この回の結論そのものが覆ります。** 覆ってよい ——
    # そのときは JOURNAL に「入れ替わった」と書いて、腕を選び直すこと。
    assert legs[0]["name"].startswith("門2a'"), (
        f"いちばん近い脚が門2a' ではありません: {legs[0]['name']}。"
        "入れ替わったのなら、この回の結論（腕の選択）を選び直すこと"
    )
    # ショートの脚は、長尺の脚より必ず遠い（規則1本/日 では桁がちがう）
    shorts = [lg for lg in legs if lg["form"] == "ショート"]
    longs = [lg for lg in legs if lg["form"] == "長尺"]
    assert min(s["ratio"] for s in shorts) > max(l["ratio"] for l in longs)


def test_no_numerator_was_smuggled_in():
    """**分子は1つも足していません。**

    足したのは**割り算1つ**（月20万 ÷ 公表値500人）だけで、
    単価も加入率も入れていません。`RPM_SCENARIOS` が増えていたら、
    未測定の数が日付に乗っています。
    """
    m, a = _analysed()
    assert len(eta.RPM_SCENARIOS) == 6, "帯が増えている ＝ 未測定の分子が入った"
    assert a["fan_yen_per_sub_needed"] == pytest.approx(
        eta.TARGET_YEN / eta.FAN_SUBS_GATE
    ), "『要る1人あたり』が、目標 ÷ 公表値の門 の割り算になっていません"


def test_printout_no_longer_shows_a_bare_unreachable_for_the_fan_hours_leg():
    """**印字の側**。裸の「届きません」に戻していないこと。

    `CLAUDE.md`「(イ) 裸の『届きません』を出さないこと」の、この形ぶんです。
    **註だけだと、次に来た側は註を読まずに行を消せます。**

    ## **この検査は、一度 素通りしました**（2026-08-31・置いたその回に）

    最初は「門2a' の行の6行うしろに `合格点` の字が在るか」を見ていました。
    **印字の節をまるごと消しても緑のまま**でした —— 消すと**脚の表**が
    繰り上がってきて、その表にも `合格点` の字が在るからです。

    **位置で見ないこと。その節にしか無い字で見ること。**
    いまは3つの節を、それぞれ**別の字**で見ます。
    """
    points = eta._points()
    if not points:
        pytest.skip("積んだ点がありません")
    m = points[-1]
    a = eta.analyse(m, points)
    lines = eta.report(m, a)
    text = "\n".join(lines)

    idx = [i for i, ln in enumerate(lines) if "[門2a']" in ln]
    assert idx, "門2a' の行そのものが印字されていません"

    # (1) 合格点の節 —— **この節にしか無い字**で見る。
    #     門2a' の行の**すぐ次の行**から始まっていること（間に何か挟むと、
    #     読む側は「届きません」を先に読んでしまいます）。
    nxt = lines[idx[0] + 1] if idx[0] + 1 < len(lines) else ""
    assert "伸び率の外挿" in nxt, (
        "門2a' の行の直後に、合格点の断りが出ていません。"
        "裸の『届きません』に戻っています"
    )
    bar_block = "\n".join(lines[idx[0] + 1: idx[0] + 5])
    assert "合格点" in bar_block and "回/本" in bar_block, "合格点の数が出ていません"
    fb = a["fan_hours_bar"]
    assert f"{fb['bar']:,.0f}回/本" in bar_block, (
        "印字している合格点が、`fan_hours_bar` の数と違います"
    )

    # (2) 脚を1つの物差しで並べた表 —— **この表にしか無い字**で見る
    assert "門の脚を、1つの物差し" in text, "脚を並べた表が出ていません"
    assert "いちばん近い脚" in text, "いちばん近い脚を名指ししていません"

    # (3) 下の段の分子の「要る側」（割り算1つ）—— **この節にしか無い字**で見る
    assert "1人あたり手取り" in text, (
        "下の段の分子が 0円 のまま（要る側の割り算が出ていません）"
    )
    assert f"¥{a['fan_yen_per_sub_needed']:,.0f}／月" in text
