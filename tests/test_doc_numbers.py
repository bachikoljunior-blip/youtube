"""**docstring が書いている数を、その表の実物と突き合わせる**（45本ぜんぶに掛ける）。

`check_tables()` が守っているのは値です。**文は誰も見ていませんでした。**
この repo は「値は正しく、文だけが古い」で通算4回落ちています。直近:

    2026-08-18  `seimeihoken` の節6の表に所得税の控除を **66,000円**（実際は 86,001円）

書いた回は正規表現を4つ手で書いて塞ぎましたが、**同じものが `tsukin` にも手で書いてあり、
残る42本には1つもありませんでした**（`docs/JOURNAL.md` 2026-08-18 09:1x の見直し3 ——
「節を1つ足すより、既にある294節の文を守るほうが桁が大きい」）。

**ここは代わりではなく下敷きです。** `tsukin` / `seimeihoken` / `keihi` が手で書いている
行ごとの突き合わせは、**こちらより強い検査です。消さないこと**（あちらは何行目の値かまで見る）。
こちらが見るのは「**この表のどこにも無い数**」だけで、45本に一律に掛かります。

## 速さ

`python -m src.calc.<表>` を45回 subprocess で回すと分単位ですが、
**`runpy` で同じ処理を in-process でやると 4秒**です（2026-08-18 に実測）。
`sections()`（`scripts/topic_forge.py`）が subprocess なのは、あちらが
`SystemExit` を跨いで独立に走らせたいからで、こちらは読むだけなので事情が違います。
"""
from __future__ import annotations

import contextlib
import io
import pathlib
import runpy
import sys
import warnings

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.calc import _checks  # noqa: E402

CALC_DIR = pathlib.Path(__file__).resolve().parents[1] / "src" / "calc"
MODULES = sorted(p.stem for p in CALC_DIR.glob("*.py") if not p.stem.startswith("_"))

_BACKING: dict[str, str] = {}


def backing(module: str) -> str:
    """その表の「裏」＝ `__main__` の出力 ＋ ソースの字。

    **ソースも裏に数えます。** 出力だけにすると 45本中24本で 117件が鳴り、
    中身は `shahoken` の等級の上下限（88,000円・650,000円）のような
    **条文から正しく引用しているが `__main__` が印字しない値**でした
    （2026-08-18 に実測）。当たりを含まないまま育つ一覧にしないため。
    """
    if module not in _BACKING:
        buf = io.StringIO()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)  # runpy の二重 import 警告
            with contextlib.redirect_stdout(buf):
                runpy.run_module(f"src.calc.{module}", run_name="__main__")
        _BACKING[module] = buf.getvalue() + (CALC_DIR / f"{module}.py").read_text()
    return _BACKING[module]


@pytest.mark.parametrize("module", MODULES)
def test_docstringの数が実物で裏を取れている(module: str):
    mod = __import__(f"src.calc.{module}", fromlist=["*"])
    _checks.numbers_backed(mod.__doc__ or "", backing(module), name=module)


# ---- この検査そのものが効くことの検査 -----------------------------------
#
# **足した検査は、緑のまま0件で通ります**（`docs/trigger_main.md` §4）。
# 下の3件は、実際に踏んだ書き間違いを注入して**鳴ること**を見ています。


def test_実際に踏んだ書き間違いを捕まえる():
    """`seimeihoken` 節6の 86,001円 を、書いたときの 66,000円 に戻す。"""
    from src.calc import seimeihoken as sh
    bad = (sh.__doc__ or "").replace("86,001", "66,000")
    assert bad != sh.__doc__, "注入元の 86,001 が docstring から消えています"
    with pytest.raises(_checks.TableError) as e:
        _checks.numbers_backed(bad, backing("seimeihoken"), name="seimeihoken")
    assert "66,000" in str(e.value)


def test_桁ずれを捕まえる():
    from src.calc import seimeihoken as sh
    bad = (sh.__doc__ or "").replace("112,000", "1,120,000")
    assert bad != sh.__doc__
    with pytest.raises(_checks.TableError):
        _checks.numbers_backed(bad, backing("seimeihoken"), name="seimeihoken")


def test_単位だけの間違いは捕まえられない():
    """**射程の外を、検査として固定しておく。**

    2026-08-17 の `70割 → 50割`（`KEIGEN_STEPS` はパーセント）は、
    `70` がソースのどこかに在るので**通ります**。
    「単位も見ている」と次の回が誤解しないよう、ここに書いて留めます。
    """
    _checks.numbers_backed("軽減は 70割 で効きます。", backing("kokuho"), name="kokuho")


def test_暦の日付は量として拾わない():
    assert _checks.doc_numbers("2019年の改正で 18.3% になった") == ["18.3"]
    assert _checks.doc_numbers("2026年8月18日に 500円") == ["500"]


def test_散文の数え上げは拾わない():
    """`回` `件` を単位に入れていない（`8回持ち越し` を表の値と突き合わせない）。"""
    assert _checks.doc_numbers("8回持ち越し・4件あった") == []


def test_万の書き方は拾わない():
    r"""**`7万7430円` の `7430` を拾わないこと**（2026-08-18 に踏んだ）。

    `(?<![\d.,])` だけだと切れ目が `万` の後ろに来るので、**在りもしない数**を拾います。
    `config/topics.yaml` の angle はこの書き方をするので、実測で **45件が偽物**でした。

    **一度は正規化（`7万7430` → `77430`）で直そうとして、戻しています。**
    万の書き方をする文はたいてい丸めた散文で、正規化すると 45本中16本が赤くなり、
    中身は `zangyo` の `62万円`（実際は 619,898）のような**丸めた散文**ばかりでした。
    """
    assert _checks.doc_numbers("同じ治療で7万7430円") == []
    assert _checks.doc_numbers("年収140万円のとき") == []
    assert _checks.doc_numbers("値打ちは24,475円") == ["24,475"]


#: **見たうえで「当たりではない」と判断した、未裏取りのテーマ。**
#:
#: **2026-08-26 に「件数の上限」からこの一覧へ替えました。** 上限（`hits <= 12`）は
#: **在庫がふえるたびに赤くなります** —— テーマは毎回ふえるので、
#: この門は「たまに正しく鳴る」ではなく**常時赤**へ向かいます。
#: 常時赤の門は、新しく壊した1件を隠します
#: （`tests/test_narrated.py` の `KNOWN_UNSHOWN` と同じ形。同日の3件目）。
#:
#: **一覧にすると「増えた」と「新しい」が分かれます。** 在庫がふえても、
#: 中身が同じなら鳴りません。**新しい ID が出たときだけ鳴ります。**
#:
#: 中身は2つの型しかありません（2026-08-26 に13件とも見た）:
#:   (型1) calc が**1つの数として印字しない導出値**。
#:         `s-fukugyo-5pct-1en` の `10,209円` は手取りの落ち幅（180,000 − 169,791）で、
#:         calc が印字するのは税額の `10,210円` のほう。**1円ずれているのが主題そのもの**
#:   (型2) **丸めた形**（`14.15` ← 14.1500 ／ `2.96` ← 2.9565…）。
#:         丸めた瞬間に、どの表にも無い数になります
REVIEWED_UNBACKED = {
    "tenshoku-nenshu", "s-kojo-3", "s-shitsugyo-4", "s-shitsugyo-5",
    "s-fukugyo-5pct-1en", "s-zangyo-ichiritsu-3man-45h", "s-fukugyo-10pct-1en",
    "s-kojo-23pct-tokutei-fuyo", "s-fukugyo-zeiritsu20-1en",
    "s-shobyo-rounding-remainder-200", "s-shobyo-drop-14-15-points",
    "s-ideco-kakekin-3bai-deguchi",
    # 2026-08-26 に増えたぶん（型1。`10.21` は配当控除の率で、表は税額を印字する）
    "haito-kojo-nashi-330man",
    # 2026-08-28 に増えたぶん（型1。**中身を実際に見て足しています** ——
    # 最適化の回。この検査は 08-27 から赤で居座り、その赤が同じ回に見つけた
    # 本物の警報（`slide_pace` に長尺が混ざる）を隠していました。
    # `docs/JOURNAL.md` 2026-08-28 06:3x「恒久的に赤い検査を1つ置くと、
    # 同じファイルの本物の警報が読まれなくなります」）。
    #
    # 鳴っていたのは **`180,000`** の1件だけ。angle の原文は
    # 「医療分だけを見ると670,000円から850,000円で **180,000円** 上がっているのに
    #   合計が下がるのは…」。**引き算そのものが、この題材の主題**です:
    #
    #     850,000 − 670,000 = 180,000   ← 表は両端を印字し、差は印字しない
    #     両端 670,000 / 850,000 は、どちらも `backing` に在ります（確認ずみ）
    #
    # 内訳も表と合います: 74歳 670,000+260,000+30,000 = **960,000**、
    # 75歳 850,000+21,000 = **871,000**、差 **89,000**（題そのもの）。
    # **実物に当たってはいません。**型1（calc が1つの数として印字しない導出値）です。
    "kouki-genkaku-89000-sagaru",
    # 2026-08-29 に増えたぶん（型1。**中身を実際に見て足しています**）。
    # 鳴っていたのは **`2,000`** の1件だけ。angle の原文は
    # 「毎月の支払額を8,000円から10,000円へ **2,000円だけ** 上げる」。
    #
    #     10,000 − 8,000 = 2,000   ← 表は両端を印字し、きざみは印字しない
    #     両端 8,000 / 10,000 は、どちらも `payment_grid()` の行に在ります
    #
    # **実物に当たってはいません。**（`_checks.near_candidates` は
    # 「表の `2026` を丸めたのでは」と勧めますが、**それは西暦**です ——
    # 丸めの候補は当たり率 97.2% でも、**残りがこの形で出ます**）。
    #
    # **同じ回に、鳴っていたもう1件（`84,809`）は表のほうを直しました** ——
    # あちらは「支払額を変えるといくら変わるか」という**表の主題そのもの**で、
    # `ribo.main()` が上下の開きを印字するようにしてあります。
    # **差が主題なら表に印字する。きざみのような言い回しの数は、ここへ足す。**
    "ribo-300000-payment-step",
    # 2026-08-29 11:5x に増えたぶん（型1。**中身を実際に見て足しています**）。
    # 鳴っていたのは **`827,065`** の1件だけ。題名は
    # 「返還を10年から20年に延ばすと利息が **827,065円** ふえる」。
    #
    #     1,588,964 − 761,899 = 827,065   ← 表は両端を印字し、差は印字しない
    #     両端 761,899（10年）/ 1,588,964（20年）は、どちらも
    #     `src.calc.shogaku` の「返還年数を10年から20年に延ばすと…」の行に在る
    #
    # **その表の主題は「年数を延ばすと月々と利息はどう動くか」**で、
    # 差そのものではありません（`ribo` の上下の開きとは、そこが違う）。
    # だから表は直さず、ここへ足します。
    "shogaku-10nen-20nen-827065en",
    # 2026-08-29 17:xx に増えたぶん（型1。**中身を実際に見て足しています**）。
    # 鳴っていたのは **`69,504`** の1件だけ。angle の原文は
    # 「よく見る計算の279,500円とは **69,504円** ひらいている
    #  （**表の2つの数字の差として画面に出す**）」——
    # **書いた側が、差であることを angle の中で明示しています。**
    #
    #     349,004 − 279,500 = 69,504   ← 表は両端を印字し、差は印字しない
    #     両端 349,004（合計）/ 279,500（よく見る計算）は、どちらも
    #     `src.calc.aoiro` の「65万円の青色申告特別控除は…」の行に在る
    #
    # **その表の主題は「控除がいくらの負担を減らすか」**で、
    # 「よく見る計算との差」ではない。だから表は直さず、ここへ足します。
    "aoiro-65man-jikkouritsu-nanadan",
    # 同じ日。**これは `kouki-genkaku-89000-sagaru`（上・08/28 に足した）と
    # 同じ数・同じ理由で、ID だけ別のテーマ**です。鳴っているのは **`180,000`**:
    #
    #     850,000 − 670,000 = 180,000   ← 表は両端を印字し、差は印字しない
    #
    # **上の註を書き写さないこと** —— 同じ説明が2か所に在ると、片方が黙って古びます
    # （`docs/JOURNAL.md` 2026-08-25 15:5x）。理由は上を読むこと。
    "kouki-jougen-89000-sagaru",
}


def test_topics_yamlには掛けない():
    """**この検査を `config/topics.yaml` の angle に広げないこと**（2026-08-18 に測った）。

    数を持つテーマ 304件に掛けると **10件が鳴り、実物に当たったのは0件**でした。
    angle は calc が**1つの数として印字しない導出値**を書くからです ——
    `s-fukugyo-5pct-1en` の `10,209円` は手取りの落ち幅（180,000 − 169,791）で、
    calc が印字するのは税額の `10,210円` のほう。**1円ずれているのが、この題材の主題そのもの**です。
    ほかに「`4.3倍` のような数字を作らないでください」という**禁止の例文**まで拾います。

    docstring（0件）と angle（10件）で当たり率がまるで違うのは、
    **docstring が「この表が出した数」を書く場所で、angle は「そこから言えること」を書く場所**だからです。
    広げると `src/alerts.py` の「一覧が当たりを含まないまま育つ」の8件目になります。
    """
    from src import config
    hits = set()
    for t in config.load_topics()["topics"]:
        calc = t.get("calc")
        if not calc or calc not in MODULES:
            continue
        text = " ".join(str(t.get(k, "")) for k in ("title_seed", "angle"))
        try:
            _checks.numbers_backed(text, backing(calc), name=calc)
        except _checks.TableError:
            hits.add(str(t.get("id")))
    new = sorted(hits - REVIEWED_UNBACKED)
    assert not new, (
        f"topics.yaml の未裏取りに、**見ていないテーマ**が増えました: {new}\n"
        "  **この検査を angle に掛ける根拠にはなりません** —— これまでの件は全部、"
        "calc が1つの数として印字しない導出値でした。**中身を目で見てから** "
        "`REVIEWED_UNBACKED` に足すこと。**実物に当たっていたら、直すのは angle のほう。**"
    )


# ---- 西暦のうしろに金額が続く（2026-08-29 に踏んだ）------------------------

def test_西暦のうしろに金額が続いても数を読み違えない():
    """`1990年380,153円` の `380,153` が、表に在るなら通ること。

    **`_DATE_RE` の2つ目の枝は `月?` が任意**なので、直すまでは
    `1990年38` まで食って、残った `0,153` を「表に無い数」として鳴らしていました。
    実測: `bunkatsu-2003-noritsu-sen` の angle で3件（`0,153`・`0,697`・`6,751`）。
    **3件とも実物は `rate_gap_table()` に在ります。**

    **日付の側を壊していないこと**も、ここで一緒に見ます ——
    `2026-08` と `2026年8月15日` は、いまも日付として落ちること。
    """
    _checks.numbers_backed("1990年380,153円", "380153", name="t")
    _checks.numbers_backed("2000年340,697円と2001年336,751円",
                           "340697 336751", name="t")
    assert _checks.doc_numbers("1990年380,153円") == ["380,153"]
    # 日付は落ちる（単位の付いた数として拾われない）
    assert _checks.doc_numbers("2026年8月15日に 5円") == ["5"]
    assert _checks.doc_numbers("2026-08 に 5円") == ["5"]
    assert _checks.doc_numbers("2026年12月の残高 5円") == ["5"]


# ---- `77.0` と `77` は同じ数（2026-08-18 に足した）----------------------

def test_小数点以下が0の数は整数と同じ鍵になる():
    """**表が `77.0` と印字し、文が `77%` と書いても通ること。**

    ここが分かれていたせいで `koyouhoken` の1節はテーマが3回作れず、
    `s-yoteinozei-3gatsu-77` は全体を1件赤にしました。
    """
    _checks.numbers_backed("3月は77%ふえる", "77.0", name="t")
    _checks.numbers_backed("倍率は2.0倍", "2", name="t")
    _checks.numbers_backed("1,655円", "1655", name="t")


def test_ちがう数はいままでどおり落ちる():
    """**緩めたのは表記だけ。値がちがえば落ちる側は動かしていません。**"""
    with pytest.raises(_checks.TableError):
        _checks.numbers_backed("3月は78%ふえる", "77.0", name="t")
    with pytest.raises(_checks.TableError):
        _checks.numbers_backed("倍率は2.5倍", "2", name="t")
    with pytest.raises(_checks.TableError):
        _checks.numbers_backed("77.5%", "77.0", name="t")


# ---- 近い数の候補（`near_candidates`）-----------------------------------
#
# `numbers_backed` は長らく「この表のどこにも無い」としか言いませんでした。
# **鳴った3回とも中身は同じで、全部「丸めた形」**でした
# （`docs/JOURNAL.md` 2026-08-18 20:1x の見直し3。当たり 3/3、直すのに約6分）。
# 当たり率は足す前に測っています —— 54本の裏から作った**丸めた形 2,840件**に対し、
# **真の値を候補に含むもの 2,761件（97.2%）**、候補が2件以上 692件（24%）。


def test_丸めた形から表の側の元の数を出す():
    """`5.36` → `5.3554`（**この検査を書かせた実物**）。"""
    assert _checks.near_candidates("5.36", backing("jidoushazei")) == ["5.3554"]


def test_落ちたときの文に近い数が出る():
    from src.calc import jidoushazei as jz
    bad = (jz.__doc__ or "").replace("5.3554", "5.36")
    assert bad != jz.__doc__, "注入元の 5.3554 が docstring から消えています"
    with pytest.raises(_checks.TableError) as e:
        _checks.numbers_backed(bad, backing("jidoushazei"), name="jidoushazei")
    msg = str(e.value)
    assert "5.36" in msg and "5.3554" in msg
    assert "丸めた" in msg


def test_末尾に0の無い整数には候補を出さない():
    """**丸めた形でない数には、何も出さない**（射程を狭いほうへ倒している）。

    `86,001` に対して `66,000` を出しにいく形を、ここで塞いでいます。
    """
    assert _checks.near_candidates("86,001", backing("seimeihoken")) == []


def test_候補は多くても3件():
    got = _checks.near_candidates("5000", backing("haiguusha"))
    assert len(got) <= 3


def test_末尾のカンマは候補に混ぜない():
    r"""`_ANY_NUM_RE` はソースの `66400,` を**カンマごと**拾います。

    桁区切りは中に残すので、落とすのは端だけ。
    """
    for got in _checks.near_candidates("66,000", backing("jidoushazei")):
        assert not got.endswith(",")


def test_候補は近い順に並ぶ():
    got = _checks.near_candidates("79.17", backing("jidoushazei"))
    assert got and got[0] == "79.1667"


def test_単位のつかない字には何も出さない():
    assert _checks.near_candidates("いくらか", "1.2345") == []
    assert _checks.near_candidates("", "1.2345") == []
