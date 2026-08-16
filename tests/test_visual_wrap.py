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

    ## **折る側に作らせるのをやめました**（2026-08-16 23:xx）

    ここは `25%  11,212,500円` を**そのまま**検査に渡していました。
    「11文字だから1行9文字にはどう折っても入らず、`_best_cut` は limit で
    妥協する」——**折る側がその欠陥を持っていることを前提にした検査**です。

    同じ日に**折る側を直した**ので、この入力はもう割れません（`_best_cut` の
    最後の節。数のかたまりが限度より長いときは、かたまりの外まで出て切る）。
    **検査は正しいまま、材料のほうが消えました。**

    ここで入力を「まだ割れる別の数」に取り替えるのは、
    **検査を折る側の欠陥に寄生させ続ける**ことです。次に折る側を直した回が、
    また同じ形で赤くなります。だから**この行を守っている**もの ——
    「桁の割れを、検査が見つけられること」——だけを残し、
    材料は上の2件と同じく**折った結果を直に差し込みます。**

    **これは見つける側にとっての故障注入です。** 割れた行は
    `render()` の `tighten` でも出ます（`_check_visual_wrap` の註）。
    **折る側が正しくても、見つける側は要ります。**
    """
    from src import visuals
    saved = visuals._wrap_item
    try:
        visuals._wrap_item = lambda text, portrait, tighten=0: (
            "25%  11,212,50<br>0円"
        )
        problems = verify._check_visual_wrap(
            _script({"kind": "list", "items": ["25%  11,212,500円"]}), True
        )
    finally:
        visuals._wrap_item = saved
    assert problems and "数字の途中" in problems[0], problems


def test_限度より長い数のかたまりは割らずにはみ出す():
    """**折る側**の直し（`_best_cut` の最後の節）。在庫が1件ここで詰まっていた。

    `s-zaishoku-1man-hanbun` は台本を書き直しても**2回とも同じ所で落ちました**
    —— `月給410,000円から440,000円へ` が限度6で **『410,00』／『0円から』**。
    実データ 13,125組で、数の途中の割れは **319 → 0**（悪化0・総行数は減る）。
    """
    from src import subtitles
    lines = subtitles._chunk("月給410,000円から440,000円へ", 6)
    assert lines == ["月給", "410,000円", "から", "440,000円", "へ"], lines
    # 末尾の `へ` が1文字で残るのは**寄せる側**の話です（隣に足すと限度を
    # 越えるので寄せられない）。**この直しが持ち込んだものではありません** ——
    # 数が割れていた頃も、限度8では同じ形でした。**数の割れのほうが重い。**
    # **はみ出してよい。読めない行を作るよりまし**、が判断です
    assert max(len(x) for x in lines) > 6


def test_限度より長いカタカナの語も割らずにはみ出す():
    """**同じ形の2件目**（2026-08-17）。数のかたまりだけを見ていた最後の節を、
    「1つのかたまりが限度より長い」という形のほうに広げた。

    `s-serufu-88000-uwanose` は `セルフメディケーション税制` が
    **『セルフメディケーショ』／『ン税制』**で `verify` に止められ、
    **足したばかりの在庫6件が丸ごと作れない**ところだった
    （`セルフメディケーション` は11字で、狭い欄の限度より長い）。

    実データ 6,064件 × 限度17通り・36,112組で、カタカナの割れは **138 → 0**
    （数の割れは 0 → 0 のまま・悪化0・総行数は 139,291 → 139,200 と減る）。
    """
    from src import subtitles
    from src.verify import _is_katakana
    lines = subtitles._chunk("セルフメディケーション税制", 6)
    assert not any(_is_katakana(a[-1]) and _is_katakana(b[0])
                   for a, b in zip(lines, lines[1:])), lines
    assert "".join(lines) == "セルフメディケーション税制", lines
    # はみ出してよい。**読めない行を作るよりまし**（数のかたまりと同じ判断）
    assert max(len(x) for x in lines) > 6
    # 短い単位（パーセント）でも、割らずに1行で出る
    assert subtitles._chunk("87パーセント", 5) == ["87パーセント"]


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

def test_限度より長い行が残ったら見出しを縮める():
    """**折る側を直したら、こんどは画面側に縮むつまみが無かった**（2026-08-17）。

    `_best_cut` が「限度の外まで出て切る」ようになったので、
    折った結果が限度より長い行は**正規に起きます**。ところが見出しには
    `tighten`（折り直すだけ）しか無く、`zoom` は `.body` にしか掛からない。
    結果 `セルフメディケーション税制` は**ブラウザが勝手に割り**、
    実物の1コマ目が『セルフメディケーシ』『ョン』『税制』になりました
    （`verify` は `<br>` の折り目しか見ないので素通り。目視で発見）。
    """
    from src import visuals as v
    head = v._wrap_head("セルフメディケーション税制", True, 0)
    assert head == "セルフメディケーション<br>税制", head
    ratio = v._fit_ratio(head, v.HEAD_CHARS_PORTRAIT)
    assert v.HEAD_FIT_MIN <= ratio < 1.0, ratio
    assert abs(ratio - v.HEAD_CHARS_PORTRAIT / len("セルフメディケーション")) < 1e-9
    html = v.build_html({"headline": "セルフメディケーション税制", "kind": "stat",
                         "stat": "8万8000円"}, v.THEMES[0], True)
    assert "--head-fit:" in html and "var(--head-fit, 1)" in html
    # **限度に収まっている見出し（＝ほとんど全部）には何も足さない**
    plain = v.build_html({"headline": "足切りの差が上限になる", "kind": "stat",
                          "stat": "8万8000円"}, v.THEMES[0], True)
    assert "--head-fit:" not in plain
    assert v._fit_ratio(v._wrap_head("足切りの差が上限になる", True, 0),
                        v.HEAD_CHARS_PORTRAIT) == 1.0


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
