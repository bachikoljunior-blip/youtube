"""**字幕（`sub`）が、読み上げ（`say`）と別のことを言っているコマを名指しする。**

（2026-09-17 15:3x・optimizer・Fable 5.1・ultracode）

## 踏んだ当のもの

`data/studio/scripts/2026-09-18-fuyou-shinkokusho.json` の **コマ125・126** は、
`say` を 1つ ずらして書き直した回が `sub`／`show`／`board` を置き忘れていました:

    コマ125  say「所得とは、収入から決まった分を引いた残りです」
            sub「その線は同封の案内に書いてあります」    ← **別の文**

**`lint` も `verify` も `critique` も 1度 も鳴っていません** ——
`critique` は `say` しか読まず、`lint` は字数と読みしか見ていなかった。

## この検査が固定するもの

    1. `sub` が `say` の言い換えなら鳴らない（**2字の並び**で数える・実測の中央は 0.895）
    2. `sub` が別の文なら鳴る
    3. **止めない**（`problems()` ではなく `warnings()` 側 ＝ 陽性対照）
    4. 句読点だけの違いで鳴らない（陽性対照）
    5. **1字 では割れないこと**（この回に 1度 外した所・陽性対照）

**覆る条件**: 鳴ったコマのうち本物が 2割 未満の窓が 2つ 続いたら門を下げること
（`Script.sub_off_say` の覆る条件 (2)）。
"""
from __future__ import annotations

import studio.script as script


def _mk(pairs):
    segs = [{"say": a, "show": "x", "sub": b, "tag": "", "image": "", "board": ["a", "b"]}
            for a, b in pairs]
    return script.Script(id="t", date="2026-09-18", title="t", takeaway="t",
                         description="d", tags=[], segments=segs)


def test_言い換えなら鳴らない():
    s = _mk([("所得とは、収入から決まった分を引いた残りです。",
              "所得とは収入から決まった分を引いた残りです")])
    assert s.sub_off_say() == []


def test_別の文なら鳴る():
    """**これが本体です。** 09/18 の本の コマ125 そのもの。"""
    s = _mk([("所得とは、収入から決まった分を引いた残りです。収入そのものではありません。",
              "その線は同封の案内に書いてあります")])
    off = s.sub_off_say()
    assert len(off) == 1 and off[0][0] == 1
    assert off[0][1] < script.SUB_OVERLAP_GATE


def test_止めない():
    """**陽性対照 1**: `problems()` に入れると、式や数を `sub` に置く本が焼けなくなります。"""
    s = _mk([("百四十八万円を十二で割ると月およそ十二万円です。",
              "月にすると12万3千円から17万8千円あたりの方")])
    assert s.sub_off_say(), "この形は鳴るべきです"
    assert not any("字幕" in p for p in s.problems()), "止める側に入っています"
    assert any("字幕" in w for w in s.warnings()), "注意の側に出ていません"


def test_句読点の違いだけでは鳴らない():
    """**陽性対照 2**: 句読点を落とさずに数えると、言い換えの本が全部 鳴ります。"""
    s = _mk([("出さないと、国はあなたに家族がいることを知らないままです。",
              "出さないと国は家族がいることを知らないままです")])
    assert s.sub_off_say() == []


def test_門を動かせる():
    """**陽性対照 3**: 門を 1.01 にすると、部分集合の本まで鳴ること（門が効いている）。"""
    s = _mk([("所得とは、収入から決まった分を引いた残りです。",
              "所得とは収入から決まった分を引いた残りです")])
    assert s.sub_off_say() == []
    assert len(s.sub_off_say(gate=1.01)) == 1


def test_1字では割れないこと():
    """**陽性対照 4**: 踏んだ当のものは、**1字 で数えると ちょうど 0.50** で門を通り抜けます。

    日本語は「の・は・に・ま・す」がどの文にも在るので、**別の文どうしでも 1字 は重なります**。
    この検査は「2字 の並びで数えている」ことを固定します（戻すと落ちます）。
    """
    say = "所得とは、収入から決まった分を引いた残りです。収入そのものではありません。"
    sub = "その線は同封の案内に書いてあります"
    ig = script.SUB_IGNORE_CHARS
    one = len((set(say) - ig) & (set(sub) - ig)) / len(set(sub) - ig)
    two = (len(script._bigrams(say) & script._bigrams(sub))
           / len(script._bigrams(sub)))
    assert one >= script.SUB_OVERLAP_GATE, "1字 でも割れるなら、この註は要りません"
    assert two < script.SUB_OVERLAP_GATE, "2字 で割れていません"


def test_subが空なら数えない():
    s = _mk([("何かの文です。", "")])
    assert s.sub_off_say() == []
