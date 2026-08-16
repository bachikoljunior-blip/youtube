"""**画面の文字**の折り返しを、検査が見ていること。

    python -m pytest tests/test_visual_wrap.py -q

## なぜ要るか（2026-08-16）

`verify._check_subtitles` は、**読み上げの字幕（.ass）だけ**を見ていました。
ところが折っているのは同じ `subtitles._chunk` で、`visuals._wrap` が
**見出し・箇条書き・注記・棒のラベルの全部**をそこへ委ねています。
**折り方は共通なのに、検査は片側にしか無かった。**

実物 `kLJ2Wsi3gQM`（8/25 12:00 予定）の箇条書きが
**『上限額 9,』／『110円→7,830円』** と割れ、**機械検査は緑のまま通しました**
（見つけたのは目視です）。同じ字が字幕に出ていれば
`数字の途中で改行している` で落ちていた形です。

だから、ここが見ているのは**桁区切りの1件ではありません。**
`_best_cut` が次に別の理由で規則を踏み越えたとき、
**画面側でも止まること**のほうです。

`tests/test_line_breaks.py` とは見ている層が違います ——
あちらは `_chunk`（割る側）、こちらは `verify`（**割れたものを見つける側**）。
**割る側を直しても、見つける側が無ければ次の形で素通りします。**
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import verify  # noqa: E402


def _script(visual: dict) -> dict:
    return {"segments": [{"narration": "ダミー", "visual": visual}]}


def test_桁区切りで折れた箇条書きを見つける():
    """**実物の欠陥そのもの。** 直す前は、この入力が緑で通っていた。

    **折る側を壊して再現しないこと**（最初そう書いて、通ってしまった）。
    カンマを `_NUM_TOKEN` から外すと**折る側と見つける側が同時に壊れます** ——
    行末が `,` でも、その `,` がもう「数の字」ではないので検査が黙る。
    **同じ表を両方が読んでいるときの故障注入は、片方だけを壊すこと。**
    ここでは**折った結果**（実物の画面に出ていた3行）を直に差し込みます。
    """
    from src import visuals
    saved = visuals._wrap_item
    try:
        visuals._wrap_item = lambda text, portrait, tighten=0: (
            "上限額 9,<br>110円→7<br>,830円"
        )
        problems = verify._check_visual_wrap(
            _script({"kind": "list", "items": ["上限額 9,110円→7,830円"]}), True
        )
    finally:
        visuals._wrap_item = saved
    assert problems, "桁区切りで折れているのに、検査が何も言わなかった"
    assert "数字の途中" in problems[0], problems


def test_いまの折り方なら通る():
    """直したあとの実物。**検査だけ足して折り方を直さないと、ここが赤になる。**"""
    assert verify._check_visual_wrap(
        _script({"kind": "list", "items": ["上限額 9,110円→7,830円",
                                           "下限額 2,562円は変わらず"]}), True
    ) == []


def test_カタカナの語の途中も見る():
    """字幕側だけにあった検査を、こちらへも写してあること。"""
    from src import visuals
    saved = visuals._wrap_item
    try:
        visuals._wrap_item = lambda text, portrait, tighten=0: (
            "セルフメディケーショ<br>ン税制の対象は"
        )
        problems = verify._check_visual_wrap(
            _script({"kind": "list",
                     "items": ["セルフメディケーション税制の対象は"]}), True
        )
    finally:
        visuals._wrap_item = saved
    assert problems and "カタカナ" in problems[0], problems


def test_空白のところで折れたのは鳴らさない():
    """**誤報を出すと1本が投稿されません。** 実測で3件がこれでした。

    `25%  11,212,500円` は元から空白で区切られた別々の値で、
    そこで折れても画面上は何も壊れていない。`_wrap` が行の端の空白を
    捨てるので、**折れた行だけを見ると数の割れと区別がつきません。**
    """
    assert verify._check_visual_wrap(
        _script({"kind": "list", "items": ["300,000円 201,000円"]}), True
    ) == []


def test_桁のあいだで割れたら鳴る():
    """空白を許すことで**本物まで見逃していないか**（上の裏返し）。

    `11,212,500円` は11文字で、1行9文字にはどう折っても入りません。
    **どこにも良い切れ目が無いので、`_best_cut` は limit で妥協します** ——
    `11,212,50` ／ `0円`。これは空白の折れではなく、**桁の割れ**です。
    """
    problems = verify._check_visual_wrap(
        _script({"kind": "list", "items": ["25%  11,212,500円"]}), True
    )
    assert problems and "数字の途中" in problems[0], problems


def test_棒のラベルと見出しも見ている():
    """**欄を1つ足したときに落ちること。** 一覧が片肺になるのを止める。"""
    from src import verify as v
    fields = {f for f, _ in v._WRAPPED_FIELDS}
    assert "headline" in fields and "note" in fields, v._WRAPPED_FIELDS
    # 棒のラベルと箇条書きは `_wrapped_visual_lines` が直に拾う
    lines = v._wrapped_visual_lines(
        {"visual": {"kind": "chart",
                    "bars": [{"label": "60歳前の上限額は9110円です", "value": 1}]}},
        True,
    )
    assert lines, "棒のラベルが折られていない（拾えていない）"


def test_台本が無い回は黙る():
    assert verify._check_visual_wrap(None, True) == []
    assert verify._check_visual_wrap({}, True) == []


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
