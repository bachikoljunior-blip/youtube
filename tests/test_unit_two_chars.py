"""**2字でひとつの単位**（`時間` など）を途中で折らない（2026-08-16 21:5x）。

## 実物

`s-jikangai-futsu-6kagetsu-126` の注記
「45時間以内で回す月の最低ライン」が、画面で

    45時
    間以内で
    回す月の
    最低ライン

と折れました（目視で発見）。**「45時」で行が終わるので、もう時間に読めません。**

## なぜ既存の規則を全部すり抜けたか

`src/subtitles._best_cut` には「数字と単位のかたまりの途中では割らない」が
ありますが、見ているのは **両側が `_NUM_TOKEN` か**です。
`時` は `_NUM_TOKEN` にあり、**`間` はありません。**

漢字の連続を見る規則にも当たりません。あちらには `num_end`
（手前も数字なら通す）という逃げ道があり、`45時` はまさにそれです。
あの逃げ道は「千円／戻ります」を許すために置いたもので、
**`時` が単位の終わりだと決めつけていました。`時間` は2字です。**

## 実データ（**直す前に前後を並べています**）

    corpus 497本 ／ 折れ目 38,938組

    直す前   単位2字を割った 96組 ／ 数字の途中 70 ／ カタカナの途中 9
    直した後 単位2字を割った  0組 ／ 数字の途中 70 ／ カタカナの途中 9

**塞いだことで数のかたまりが割れる形は1件も増えていません**（`区｜分` を
禁じたときは2件増えたので、毎回測ること）。

## 折る側と検査側の両方に置いてあります

折る側だけだと、**逃げ場が無いときの最後の1行が規則を踏み越えます**
（カタカナで実際に起きた。`verify._check_visual_wrap` の註）。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.subtitles import _chunk  # noqa: E402
from src.verify import _check_visual_wrap  # noqa: E402


def test_時間を割らない():
    """実物そのもの。`45時`／`間以内で` に落ちないこと。"""
    for limit in range(6, 13):
        for a, b in zip(_chunk("45時間以内で回す月の最低ライン", limit),
                        _chunk("45時間以内で回す月の最低ライン", limit)[1:]):
            assert not (a.endswith("時") and b.startswith("間")), (limit, a, b)


def test_ほかの2字の単位も割らない():
    """`年間` `月間` `日間` `週間` `秒間` も同じ形。"""
    cases = [
        ("残業45時間の月が年6回まで続く", "時"),
        ("勤続3年間で受け取る額を計算した", "年"),
        ("入院した30日間の自己負担を計算", "日"),
        ("休職2週間ぶんの手当を計算した", "週"),
    ]
    for text, head in cases:
        for limit in range(6, 14):
            lines = _chunk(text, limit)
            for a, b in zip(lines, lines[1:]):
                assert not (a.endswith(head) and b.startswith("間")), (text, limit, a, b)


def test_数のかたまりのほうを割らないこと():
    """**塞ぎすぎると悪化します**（`区｜分` を禁じたとき2件が数を割った）。

    逃げ場を奪っていないことを、金額の並んだ実データ由来の文で見る。
    """
    text = "所得割78万2000円で上限23万7127円"
    for limit in range(8, 16):
        lines = _chunk(text, limit)
        for a, b in zip(lines, lines[1:]):
            assert not (a[-1].isdigit() and b[0].isdigit()), (limit, a, b)


def _script(note: str) -> dict:
    return {"segments": [{"visual": {"kind": "stat", "headline": "見出し",
                                     "stat": "月21時間", "note": note}}]}


def test_検査も同じ形を見ている():
    """折る側だけに置かないこと。**最後の1行は規則を踏み越えます。**"""
    # 折れ目そのものを渡して、検査が鳴ることだけを見る（折り方は上で見た）
    from src import verify

    bad = [("45時間以内で回す月の最低ライン", "45時", "間以内で")]
    hits = [(t, a, b) for t, a, b in bad
            if a[-1] in verify._UNIT_HEAD and b[0] == "間"
            and len(a) >= 2 and a[-2] in verify._NUM_TOKEN]
    assert hits, "検査の条件がこの形を拾いません"


def test_検査は正しい折り方を鳴らさない():
    """**誤報は不投稿です。** 数字が手前に無い `時｜間` は鳴らさない。"""
    from src import verify

    ok = [("その時", "間")]          # 「その時」＋「間」＝手前が数字でない
    hits = [1 for a, b in ok
            if a[-1] in verify._UNIT_HEAD and b[0] == "間"
            and len(a) >= 2 and a[-2] in verify._NUM_TOKEN]
    assert not hits


#: この回に実際に作った9本から集めた `note`（`kind=stat` で `stat` もある欄だけ）。
#: **`title_seed` を代わりに使わないこと** —— あれは説明欄向けの長文で、
#: `note` として画面に出ることは一度もありません。最初そちらで測って、
#: **実在しない折れ方で「誤報」を数えました。**
REAL_NOTES = [
    "1か月ぶん・全額免除を追納した場合",
    "3か月の労働日数の目安",
    "45時間以内で回す月の最低ライン",
    "その年の付与が10日以上",
    "ふつうの6か月ぶん・月21時間",
    "休日労働ゼロ・12か月ぶんの置き方・変形労働時間制は除く",
    "区分ウ・窓口3割で計算",
    "医療費1000万円・窓口3割",
    "年の上限・休日労働はゼロで計算",
    "年の合計は720時間・12か月ぶんの置き方",
    "日額5,869円・労働20日",
    "暦日92日・労働20日の場合",
    "月400円・65歳から受け取る場合",
    "納付月数が変わっても同じ",
    "週4日・労働52日・3か月",
    "週4日・勤続3.5年までの累計付与",
]


def test_実データで新しい誤報が出ていない():
    """**この検査を入れた状態で、実物の注記が全部通ること。**

    誤報が1件でもあれば、その本は投稿できません（投稿が途切れるのが最大の損失）。
    `45時間以内で回す月の最低ライン` が入っているのが要点で、
    **折る側を直した後は、狭いほうの幅でも鳴りません。**
    """
    bad = [t for t in REAL_NOTES if _check_visual_wrap(_script(t), portrait=True)]
    assert not bad, f"実物の注記で鳴っています: {bad[:3]}"


def test_狭いほうの幅も見ている():
    """**穴はここでした。** `lead=False` だけ見ると、この形は素通りします。

    直す前の `45時間以内で回す月の最低ライン` は
    `lead=False` で `45時間以内で ／ 回す月の最低ライン`（無傷）、
    `lead=True` で **`45時` ／ `間以内で`**（実際に画面へ出たほう）でした。
    """
    from src import verify

    seg = {"visual": {"kind": "stat", "stat": "月21時間",
                      "note": "45時間以内で回す月の最低ライン"}}
    got = dict(verify._wrapped_visual_lines(seg, portrait=True))
    lines = got["45時間以内で回す月の最低ライン"]
    assert len(lines) >= 3, f"狭いほうの幅で折っていません: {lines}"
