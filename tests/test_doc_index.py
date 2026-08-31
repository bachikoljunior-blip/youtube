"""`doc_usage --index` と、それを毎周 印字する `run_marker --write` の検査（2026-09-01）。

## なぜ要るか

`retro.py` の (a2) 問い1（この回でいちばん時間を食ったのはどこか）を縦に読むと、
**直近9件のうち6件、直近5件は5件とも「手順の読み」**でした。
`docs/trigger_main.md` は **1日 約190行**増え、**名前から場所は引けません。**

あちらの「読む前に、この1行を撃つこと」は、**行番号の表を手で貼ろうとして
2回 失敗した跡**です（貼った瞬間に、貼ったぶんだけ全部ズレた）。
そこに書かれた **覆る条件がこれ**でした ——
「`scripts/doc_usage.py` が毎周この一覧を印字するようになったら、
`grep` を手で撃つ必要もなくなります」。

## ここで固定している「既知の当たり」

1. **行番号は実物を指す**（`sed -n '<行>,+80p'` が、その節の見出しから始まる）
2. **並べ替えない**（`docs/trigger_main.md` は §2.7 が §2.6 より**前**にある。
   番号順に直すと当てどころが実物とずれる）
3. **読む順の名指しは、文書から機械で引く**（手で並べると、あちらが節を足した日に
   黙って古くなる。このリポジトリで通算11回の形）
4. **行数は次の「大見出し」まで**（`sections()` の `lines` は次の**どの深さの**
   見出しまでなので、そのまま使うと §0 が 493行 を **2行** と言う。実際に出た）
5. **`run_marker --write` が毎周 出す**（配線が外れたら、この検査が落ちる）
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import doc_usage  # noqa: E402
import run_marker  # noqa: E402

DOC = ROOT / "docs" / "trigger_main.md"


def test_読む順は文書から機械で引く():
    """**手で並べていないこと。** 差し替えた文書からは、差し替えた番号が出る。"""
    text = ("## 前置き\n"
            "    普通の回に読むのは、この3つの**見出しと箇条書きだけ**:\n"
            "      §0 の冒頭 ／ §1 ／ §9.9 の四つ\n"
            "\n"
            "本文\n")
    assert doc_usage.reading_order(text) == [
        ("0", "冒頭"), ("1", ""), ("9.9", "四つ")]


def test_読む順が無い文書では空になる():
    assert doc_usage.reading_order("## A\nあ\n") == []


def test_行番号がその節の見出しを指す():
    """**当てどころが実物であること。** これが外れると `sed` が別の節を開く。"""
    lines = DOC.read_text(encoding="utf-8").splitlines()
    rows = doc_usage.index_rows(DOC.read_text(encoding="utf-8"))
    assert rows, "大見出しが1件も取れていません"
    for r in rows:
        got = lines[r["line"] - 1]
        assert got.startswith("## "), f"L{r['line']} は大見出しではありません: {got[:40]}"
        assert r["title"] in got


def test_文書に出てくる順のまま_並べ替えない():
    """`docs/trigger_main.md` は **§2.7 が §2.6 より前**にあります（実測）。

    番号順に直して見せると、**行番号の並びが単調でなくなり**、
    「上から読む」回の当てどころがずれます。**要るのは番号ではなく行番号です。**
    """
    rows = doc_usage.index_rows(DOC.read_text(encoding="utf-8"))
    lines_no = [r["line"] for r in rows]
    assert lines_no == sorted(lines_no), "行番号が単調ではありません（並べ替えている）"


def test_行数は次の大見出しまで():
    """**`sections()` の `lines` をそのまま使わないこと。**

    あれは次の**どの深さの**見出しまでなので、小見出しの直前で切れます。
    実測 2026-09-01: そのまま出すと §0（493行）が **2行** と表示されました。
    """
    text = "## A\nあ\n### a1\nい\nう\n## B\nえ\n"
    rows = doc_usage.index_rows(text)
    assert [r["title"] for r in rows] == ["A", "B"]
    assert rows[0]["lines"] == 5            # L1〜L5（`## B` の直前まで）
    assert rows[1]["lines"] == 2


def test_読む順の節に印が付く():
    text = ("## 読む順\n"
            "    普通の回に読むのは、この2つの**見出しと箇条書きだけ**:\n"
            "      §1 ／ §4 の四つ\n"
            "\n"
            "## 1. あ\n本文\n"
            "## 2. い\n本文\n"
            "## 4. う\n本文\n")
    rows = {r["num"]: r for r in doc_usage.index_rows(text) if r["num"]}
    assert rows["1"]["read"] and rows["4"]["read"]
    assert not rows["2"]["read"]
    only = doc_usage.index_lines(text, "d.md", only_read=True)
    body = "\n".join(only)
    assert "§1" in body and "§4" in body and "§2" not in body


def test_run_marker_が毎周_この一覧を出す():
    """**配線の検査。** 外れたら、次の回はまた `grep` を手で撃つところに戻ります。"""
    out = run_marker._doc_index_lines()
    assert out, "`--write` が当てどころを1行も出していません"
    body = "\n".join(out)
    assert "出せませんでした" not in body, body
    # 読む順が名指しする節が、行番号つきで出ていること。
    for sec in ("§2.6", "§2.7", "§4", "§6"):
        assert sec in body, f"{sec} が出ていません:\n{body}"
    assert re.search(r"sed -n '\d+,\+\d+p'", body), body


def test_一覧を出せなくても回は止めない():
    """**印が本体で、これは付け足しです。** 例外で `--write` を落とさないこと。"""
    out = run_marker._doc_index_lines("docs/このファイルはありません.md")
    assert out == []
