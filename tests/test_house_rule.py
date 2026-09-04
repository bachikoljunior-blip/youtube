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

def test_上限は床なら1本_外れていれば観測の中():
    """**旗を読むこと。数をべた書きしないこと。**（2026-09-05 に書き替えた）

    ここは長らく `PUBLISH_PER_DAY == 1` をべた書きしていました。
    オーナーが 2026-09-04 17:3x に床を外した（原文「目標以外全部外して良いよ」）あと、
    **床が外れているのに「1本であること」を守り続ける検査**になっていました ——
    `tests/test_eta_house_rule.py` が同じ所で先に踏んで、こう書いています:
    **「規則の効き方そのものが旗で切り替わる作りになったら、検査も旗を読むこと。」**

    **どちらの側も緩めていません**:

        床が立っている  規則そのもの ＝ **1本/日**
        床が外れている  **1 以上、かつ「再生が付く上限」を超えないこと**
                        （`src/day_cap.py` の実測 10本/日。**出しても再生が
                          付かない本数まで歩いたら、実在しない世界です**）

    **覆る条件**: `publish_per_day_is_floor()` が消えたら、この分岐は要らなくなります。
    """
    from src import day_cap

    n = house_rule.PUBLISH_PER_DAY
    assert n == house_rule.cap()
    if house_rule.publish_per_day_is_floor():
        assert n == 1, f"床が立っているのに {n}本/日 です"
    else:
        assert n >= 1, n
        assert n <= day_cap.cap(), (
            f"{n}本/日 は、再生が付く上限 {day_cap.cap()}本/日 を超えています"
            "（出しても再生が付かない本数まで歩いています）")
    assert house_rule.STOCKPILE_ALLOWED is False


def test_機械の上限が規則から来ている():
    """**定数の写しではなく、同じ所を読んでいるか。**"""
    assert density_cap() == house_rule.PUBLISH_PER_DAY


#: **この3件は「1日1本」ではなく「規則の本数を超えないこと」を見ます**
#: （2026-09-05 に書き替えた。`PUBLISH_PER_DAY` が 1 → 10 になったため）。
#: **見張っている物は1つも減っていません** —— 超過を落とすこと・控えを足して
#: 数えること・時刻の種類で数えること。**変わったのは、上限を規則から読む所だけ**です。
#: べた書きの 1 に戻すと、次に本数が動いた回にまた全部 赤くなります。


def test_同じ日に上限を超えるぶんは落とす():
    """`cap=` を渡さない ＝ **機械が実際に使う上限**で数えます。"""
    cap = house_rule.cap()
    when = [f"2026-09-01@{h}" for h in range(6, 6 + cap + 3)]   # 上限＋3本 とも同じ日
    keep, notes = cap_by_density(when, ledger={})
    assert len(keep) == cap, f"1日に {cap}本 を超えて置けてしまいます"
    assert notes


def test_その日に既に上限ぶん控えがあれば1本も通さない():
    cap = house_rule.cap()
    # 帯の外の時刻でも1本は1本（`cap_by_density` は控えを足して数えます）
    ledger = {"2026-09-01": {(20 + i) * 60 for i in range(cap)}}
    keep, _ = cap_by_density([f"2026-09-01@{h}" for h in range(6, 6 + cap + 3)],
                             ledger=ledger)
    assert keep == []


def test_時刻の種類が上限を超えたら同じ日に着くぶんを落とす():
    """日を名指ししない指定（長尺の `ring`）も、**時刻の種類ぶんは同じ日に着きます。**"""
    cap = house_rule.cap()
    keep, notes = cap_by_density([str(h) for h in range(0, cap + 2)], ledger={})
    assert len(keep) == cap
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
