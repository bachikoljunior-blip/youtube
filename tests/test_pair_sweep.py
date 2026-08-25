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


def test_既知の当たりは_いまの3つの形では_まだ出ない():
    """**赤くなったら進歩です。**そのときは消さずに、上の検査へ書き換えること。

    母数には入るようになりましたが、**拾う形**（崖の近さ・和の平坦・順序の逆転）
    のどれにも当たりません。`gassan` の7節は
    「**医療だけで年間限度額の95.0〜96.4%が埋まる**」という
    **和に対する割合**で、いまの3つはどれもその形を見ていないからです。

    **つまり足りないのは母数ではなく形のほうです。**
    次に触る回は、形を1つ増やすこと（例: `A ÷ (A+B)` が区間で一定に近い）。
    """
    hits = pair_sweep.sweep_pairs(["kogaku", "kaigo"])
    assert hits == [], (
        "既知の当たりが出るようになりました。**これは進歩です。**"
        f" 出た形: {[h['形'] for h in hits]} —— この検査を消して、"
        "「出ること」を固定する側へ書き換えてください")


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


def test_拾う形は宣言した3つだけ():
    """`SHAPES` が正本。**形を足したらここが赤くなります**（宣言させるため）。"""
    hits = pair_sweep.sweep_pairs(["kaigo", "kogaku", "iryohi", "inshi"])
    for h in hits:
        assert h["形"] in pair_sweep.SHAPES, h
