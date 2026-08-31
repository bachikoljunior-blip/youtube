"""**オーナーが固定した運転規則が、文書ではなく機械の側に在るか。**（2026-08-31）

## 原文（`src/house_rule.py`・`CLAUDE.md` 冒頭・`docs/GOAL.md`）

    「動画は1日一本作り置きはなしにして。次の投稿予定までにそこで投稿する動画を
      改善し続ける。それは固定にして。その上で目標を目指す」

## なぜ置いたか

**この repo でいちばん多い壊れ方は「言っている所と、している所が別」です。**
`tests/test_density_cap.py` の冒頭に実例があります —— `docs/MEANS.md` が
「崩れる点は 10本/日」と書いていた裏で、機械は 08/27 に 19本、08/28 に 22本 置きました。

**規則を `CLAUDE.md` に書くだけなら、同じことが起きます。** だからここが見るのは
文書の言い分ではなく、**`scripts/batch_build.py` が実際に何本 通すか**です。

## ここが見るのは2つだけ

    1. **1日に2本以上 置けないこと**（`cap_by_density()` の実際の返り）
    2. **規則の本文が repo に在ること**（`CLAUDE.md` と `docs/GOAL.md` の両方）

**戻すには、この検査を消すしかありません。** 消せば diff に出ます ——
それが狙いです（黙って上限だけ上げる道を塞ぐ）。

## 覆る条件

**ありません。** オーナーが自分の言葉で外すまで固定です
（`A14` の「それ以外は変えてよい」の**外側**）。
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.batch_build import cap_by_density, density_cap  # noqa: E402
from src import house_rule  # noqa: E402


# --- 1. 1日に2本以上 置けないこと ------------------------------------------

def test_規則は1日1本である():
    assert house_rule.PUBLISH_PER_DAY == 1
    assert house_rule.cap() == 1
    assert house_rule.STOCKPILE_ALLOWED is False


def test_機械の上限が規則から来ている():
    """**定数の写しではなく、同じ所を読んでいるか。**"""
    assert density_cap() == house_rule.PUBLISH_PER_DAY


def test_同じ日に2本目を置こうとしたら落とす():
    """`cap=` を渡さない ＝ **機械が実際に使う上限**で数えます。"""
    when = [f"2026-09-01@{h}" for h in range(9, 14)]     # 5本 とも同じ日
    keep, notes = cap_by_density(when, ledger={})
    assert len(keep) == 1, "1日に2本以上 置けてしまいます"
    assert notes


def test_その日に既に1本_控えがあれば1本も通さない():
    ledger = {"2026-09-01": {20 * 60}}                   # 帯の外でも1本は1本
    keep, _ = cap_by_density([f"2026-09-01@{h}" for h in range(9, 14)],
                             ledger=ledger)
    assert keep == []


def test_時刻の種類が2つ以上なら同じ日に着くぶんを落とす():
    """日を名指ししない指定（長尺の `ring`）も、**時刻の種類ぶんは同じ日に着きます。**"""
    keep, notes = cap_by_density([str(h) for h in range(18, 23)], ledger={})
    assert len(keep) == 1
    assert notes


def test_計画の本数も規則と同じ数である():
    """`eta.PLAN_PUBLISH_PER_DAY` は到達日の段1〜4 が乗っている本数。

    **機械がそれより多く置けるなら、到達日は出せない本数で出ています。**
    """
    eta = importlib.import_module("eta")
    assert eta.PLAN_PUBLISH_PER_DAY == house_rule.PUBLISH_PER_DAY


def test_作り置きの口が既定で1本になっている():
    """`--count` の既定。**渡さずに撃った回が、黙って2本 作らないこと。**"""
    src = (ROOT / "scripts" / "batch_build.py").read_text(encoding="utf-8")
    assert 'ap.add_argument("--count", type=int, default=1,' in src, (
        "`--count` の既定が 1 ではありません（作り置きの口）")


# --- 2. 規則の本文が repo に在ること ----------------------------------------

def test_原文が消えていない():
    gone = house_rule.verbatim_missing_from(ROOT)
    assert gone == [], f"オーナー原文が消えています: {gone}"


def test_原文が一字も変わっていない():
    """**要約・補足・善意の修正をしないこと。** 文字列そのものを見ます。"""
    assert house_rule.OWNER_VERBATIM == (
        "動画は1日一本作り置きはなしにして。"
        "次の投稿予定までにそこで投稿する動画を改善し続ける。"
        "それは固定にして。その上で目標を目指す")


def test_固定であることが書いてある():
    """「固定」「A14 の外側」が `CLAUDE.md` に在るか ——

    **次に来た回が「より速い道が見つかったから」で外さないための1行**です。
    """
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    head = text[:text.index("<!-- PERMANENT-DIRECTIVE:BEGIN -->")]
    assert house_rule.OWNER_VERBATIM in head, (
        "原文が `CLAUDE.md` の冒頭ブロック（恒久指示の前）に在りません")
    assert "A14" in head and "固定" in head
