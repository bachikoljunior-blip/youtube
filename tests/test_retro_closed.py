"""持ち越しの数え方 —— **「潰した」と日誌が宣言した語を、数え続けないこと。**

## なぜ要るか（2026-08-16 に実測してから足しています）

`retro.py` の持ち越しは「2回以上の申し送りに出てくる語」で、**回数がそのまま
『まだ潰れていない証拠』として印刷されます。** ところが実物を測ると、上位が
**既に潰れたもので埋まっていました**（同日 09:3x の実測。直近8回の申し送り）:

    6回  usage                       → 07:2x に「9回運ばれた最後の1件を測って閉じた」
    5回  nenkin / ASSUMPTIONS        → 06:3x に「この回で閉じました」
    5回  sibling_check --phase spawn → 06:3x に「この回で閉じました」
    3回  status.py                   → 03:4x に「系（7回）はこの回で閉じました」

**日誌は毎回きちんと宣言していました**（実測7か所・書き方も揃っている）。
**読む側が無かっただけ**です —— `retro.py` そのものが「片方だけある」形で、
これは §2.7 が塞ぎに来た欠陥と**同じ種類**でした。

害は「多く出る」ことではありません。`retro.py` は最後に
**「この回で1件は潰すこと」**と言い、`trigger_main.md` §4 は
**「持ち越しが出ていたら、そこから選ぶのが既定」**と書いています。
**潰れたものを名指しすると、その回の選択そのものが空振りします。**

## 数え方（時系列で見ること。宣言の一括除外にしないこと）

`critique_queue` は 04:2x に閉じて、**そのあと別の理由で戻っています。**
だから落とすのは**宣言より前の言及だけ**で、後の言及は
**「一度閉じた後の再発」**として、むしろ強く出すこと。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("retro", ROOT / "scripts" / "retro.py")
retro = importlib.util.module_from_spec(spec)
sys.modules["retro"] = retro
spec.loader.exec_module(retro)


def test_宣言を拾う():
    doc = "**`nenkin`/`ASSUMPTIONS` の2語はこの回で閉じました**\n"
    found = retro.closures(doc)
    assert set(found) == {"nenkin", "ASSUMPTIONS"}


def test_宣言の無い行は拾わない():
    """**「閉じ」の字が無い行から拾うと、ただの言及で黙らせてしまいます。**"""
    assert retro.closures("`nenkin` の節を足した\n") == {}


def test_鉤括弧の宣言も拾う():
    doc = "「在庫が2週間を切ったら下限より生成を優先」はこの回で閉じました\n"
    assert "在庫が2週間を切ったら下限より生成を優先" in retro.closures(doc)


def test_同じ語が二度閉じられたら後のほうを採る():
    # 語は3字以上（`TOKEN_RE`）。1字だと拾われないので、そこで通る検査にしない
    doc = "`abc` を閉じました\n\n\n`abc` をまた閉じました\n"
    assert retro.closures(doc)["abc"] == 3


def test_宣言より前の言及は落ち_後の言及は残る():
    """**これが本体。** 行番号で見るので、同じ語でも前後で扱いが変わります。"""
    doc = "\n".join([
        "## 2026-08-16 01:0x — 題",
        "### 次の回へ",
        "1. `critique_queue` の待ち",
        "",
        "## 2026-08-16 02:0x — 題",
        "### 次の回へ",
        "1. `critique_queue` 系はこの回で閉じました",   # ← 宣言。ここまでが「前」
        "",
        "## 2026-08-16 03:0x — 題",
        "### 次の回へ",
        "1. `critique_queue` がまた詰まった",           # ← 再発
        "",
        "## 2026-08-16 04:0x — 題",
        "### 次の回へ",
        "1. `critique_queue` がまだ詰まっている",
    ])
    closed = retro.closures(doc)
    blocks = retro.handoff_blocks(doc)
    kept = [d for d, body, start in blocks
            if "critique_queue" in retro.tokens(body)
            and not ("critique_queue" in closed and start <= closed["critique_queue"])]
    assert len(kept) == 2, kept
    assert all("03:0x" in d or "04:0x" in d for d in kept), kept


def test_実物の日誌で上位が入れ替わる():
    """**故障注入ではなく実データ。** 直近8回で、潰れた語が持ち越しから消えること。"""
    journal = (ROOT / "docs" / "JOURNAL.md").read_text(encoding="utf-8")
    closed = retro.closures(journal)
    blocks = retro.handoff_blocks(journal)[-8:]
    counted: dict[str, int] = {}
    for _date, body, start in blocks:
        for tok in retro.tokens(body):
            if tok in closed and start <= closed[tok]:
                continue
            counted[tok] = counted.get(tok, 0) + 1
    # 06:3x / 07:2x で閉じたと宣言された4語は、もう持ち越しに立たない
    for tok in ("usage", "nenkin", "ASSUMPTIONS", "sibling_check --phase spawn"):
        assert counted.get(tok, 0) < 2, (tok, counted.get(tok))
    # 宣言そのものは日誌に在る（検査が「宣言が無いから通った」にならないように）
    for tok in ("usage", "nenkin", "ASSUMPTIONS", "sibling_check --phase spawn"):
        assert tok in closed, tok


def test_閉じていないことを言う行を宣言に数えない():
    """**入れた直後の実物で踏みました**（2026-08-16 09:5x）。

    「**一度閉じた後の再発**」は、**閉じていないことを言うための行**です。
    最初これを宣言として読み、`critique_queue` が丸ごと黙りました。
    **言葉の向きが逆なので、件数では絶対に気づけません**（黙るほうに出る）。
    """
    doc = "5. 持ち越し: `critique_queue` の待ち（**一度閉じた後の再発**・35本）\n"
    assert retro.closures(doc) == {}


def test_連体形は宣言に数えない():
    """「閉じた」は文中の言及に出ます。宣言は丁寧形だけ。"""
    assert retro.closures("`nenkin` を閉じた回の話をする\n") == {}
    assert "nenkin" in retro.closures("`nenkin` はこの回で閉じました\n")


def test_引用符の中の閉じましたは宣言に数えない():
    """**同じ穴の3枚目**（2026-08-16 10:xx。実物で踏みました）。

    09:5x の回が「偽の宣言を踏んだ」ことを日誌に書いた、**その説明文そのもの**が
    次の偽の宣言になりました。`REOPEN_RE` は効きません（`再発` が無い）。

        `closures()` を「`閉じました` か `閉じた`」で書いて回したら、`critique_queue` が

    バッククォートの中は **その語を名指ししている**ので、動詞として読まない。
    """
    doc = ("`closures()` を「`閉じました` か `閉じた`」で書いて回したら、"
           "**`critique_queue` が丸ごと黙りました。**\n")
    assert retro.closures(doc) == {}


def test_地の文の閉じましたは宣言のまま():
    """**片側だけ締めないこと。** 引用の外にある宣言は、今までどおり効く。"""
    got = retro.closures("**`_template.py`（7回）はこの回で閉じました**（実物で確認）。\n")
    assert "_template.py" in got


def test_引用の中に閉じましたがあっても地の文にあれば宣言():
    """1行に両方あるとき。**地の文が勝つ。**"""
    doc = "`closures()` の「`閉じました`」の判定を直し、`critique_queue` はこの回で閉じました\n"
    got = retro.closures(doc)
    assert "critique_queue" in got and "closures()" in got


def test_実物の日誌で_critique_queue_は黙らない():
    """**実データ。** 04:2x に閉じて、そのあと戻っている語。**再発として残ること。**"""
    journal = (ROOT / "docs" / "JOURNAL.md").read_text(encoding="utf-8")
    closed = retro.closures(journal)
    blocks = retro.handoff_blocks(journal)[-8:]
    kept = [d for d, body, start in blocks
            if "critique_queue" in retro.tokens(body)
            and not ("critique_queue" in closed and start <= closed["critique_queue"])]
    assert len(kept) >= 2, kept
