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
    hits = 0
    for t in config.load_topics()["topics"]:
        calc = t.get("calc")
        if not calc or calc not in MODULES:
            continue
        text = " ".join(str(t.get(k, "")) for k in ("title_seed", "angle"))
        try:
            _checks.numbers_backed(text, backing(calc), name=calc)
        except _checks.TableError:
            hits += 1
    assert hits <= 12, (
        f"topics.yaml の未裏取りが {hits} 件に増えました（2026-08-18 の実測は10件）。"
        "**この検査を angle に掛ける根拠にはなりません** —— 10件は全部、"
        "calc が1つの数として印字しない導出値でした。増えた中身を目で見ること。"
    )


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
