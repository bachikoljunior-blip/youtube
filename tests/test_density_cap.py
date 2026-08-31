"""**1日の公開本数の上限が、文書ではなく機械の側に在るか。**（2026-08-30・解除条件4）

## なぜ置いたか

`docs/MEANS.md` M14 は 2026-08-25 から「崩れる点は 10本/日」と書いており、
`config/hypotheses.yaml` の `next_done` も 08-28 に「頭打ちと確定させた」と
書いていました。**それでも機械は 08/27 に 19本、08/28 に 22本 置きました。**

**書いてある数と、出している数が別だった** ——`AUTOMATION_PAUSED.md` の
Resume gate 4（量そのもの）が縛っているのは、まさにこの差です。
だからここが見るのは「文書に何と書いてあるか」ではなく、
**`scripts/batch_build.py` が実際に何本 通すか**です。

## 3つの数が同じ所から来ているか

    src.house_rule.PUBLISH_PER_DAY       **上限の唯一の出どころ**（オーナーの規則1）
    scripts/eta.py PLAN_PUBLISH_PER_DAY  到達日の段1〜4 が乗っている本数
    scripts/batch_build.density_cap()    機械が実際に置く上限

**この3つがずれたら、また「言っている所と、している所が別」に戻ります。**
ずれた瞬間にここが赤くなります。

## **2026-08-31: 出どころが `HOUR_HI` から `house_rule` へ移りました**

オーナーが規則を固定しました（原文は `src/house_rule.py`・`CLAUDE.md` 冒頭）:

    「動画は1日一本作り置きはなしにして。次の投稿予定までにそこで投稿する
      動画を改善し続ける。それは固定にして。その上で目標を目指す」

`src.density_verdict.HOUR_HI`（13）は**測れている帯の上端＝観測**であって、
出してよい本数ではありません。**帯が動いても、規則は動きません。**

## 覆る条件

**ありません。** `density_verdict` の倍率が 0.5 以上に戻っても、上限は 1本/日 のままです
（帯が広がることと、規則が変わることは別ものです）。
外れるのは、オーナーが自分の言葉で規則を外したときだけ。
**この検査は上限の値そのものは主張していません** —— 主張しているのは
`tests/test_house_rule.py` のほうです。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.batch_build import cap_by_density, density_cap  # noqa: E402
from src import density_verdict  # noqa: E402


# --- 上限の出どころが1か所か ---------------------------------------------

def test_上限は規則から来ている():
    """**2026-08-31 まではここが `density_verdict.HOUR_HI` でした。**

    帯（観測）ではなく規則を読んでいるか。**規則のほうが勝ちます。**
    """
    from src import house_rule                              # noqa: PLC0415

    assert density_cap() == house_rule.PUBLISH_PER_DAY
    assert density_cap() <= density_verdict.HOUR_HI, (
        "測れている帯の上端より多く置こうとしています")


def test_計画の本数と機械の上限が同じ数である():
    """`eta.PLAN_PUBLISH_PER_DAY` は段1〜4 が乗っている本数。

    **機械がそれより多く置けるなら、到達日は出せない本数で出ています。**
    逆に少なくしか置けないなら、到達日は届かない本数で出ています。
    """
    import importlib

    eta = importlib.import_module("eta")
    assert eta.PLAN_PUBLISH_PER_DAY == density_cap()


# --- 日を名指しした指定（`--date` / 帯の歩き / `--hours`）-------------------

def test_同じ日に上限より多く置こうとしたら落とす():
    cap = 13
    when = [f"2026-09-01@{9 + i // 2}:{'00' if i % 2 == 0 else '30'}"
            for i in range(20)]
    keep, notes = cap_by_density(when, cap=cap, ledger={})
    assert len(keep) == cap
    assert keep == list(range(cap))          # **先頭から採る**（後ろを落とす）
    assert notes and "7本" in notes[0]


def test_控えで埋まっているぶんを数える():
    """**控えは帯の外も数えます。** ここが `_per_day_soft()` との差です ——

    あちらは `busy & set(grid)` ＝ 帯（09:00〜13:30）の枠しか見ないので、
    長尺の 20:00 や、同じ日の別の回が置いた本を数えません。
    """
    cap = 13
    ledger = {"2026-09-01": {20 * 60, 21 * 60, 22 * 60}}   # **全部 帯の外**
    when = [f"2026-09-01@{h}" for h in range(9, 24)]        # 15本
    keep, _ = cap_by_density(when, cap=cap, ledger=ledger)
    assert len(keep) == cap - 3


def test_控えが上限まで埋まっていたら1本も通さない():
    cap = 13
    ledger = {"2026-09-01": {h * 60 for h in range(6, 19)}}   # 13本
    keep, notes = cap_by_density(when=[f"2026-09-01@{h}:30" for h in range(9, 13)],
                                 cap=cap, ledger=ledger)
    assert keep == []
    assert notes


def test_日をまたいだら日ごとに数える():
    cap = 3
    when = ([f"2026-09-01@{h}" for h in range(9, 14)]        # 5本
            + [f"2026-09-02@{h}" for h in range(9, 14)])     # 5本
    keep, _ = cap_by_density(when, cap=cap, ledger={})
    kept = [when[i] for i in keep]
    assert sum(1 for w in kept if w.startswith("2026-09-01")) == cap
    assert sum(1 for w in kept if w.startswith("2026-09-02")) == cap


# --- 日を名指ししない指定（`--hour` / 長尺の `ring`）------------------------

def test_同じ時刻の繰り返しは1日1本ずつ散るので落とさない():
    """`next_publish_at()` は「その時刻で最初に空いている**日**」を返します。

    だから `["9"] * 20` は **20日 に散って 1日1本**です。**落とすものはありません。**
    ここを本数で数えると、散っているだけの回まで削ってしまいます。
    """
    keep, notes = cap_by_density(["9"] * 20, cap=3, ledger={})
    assert len(keep) == 20
    assert notes == []


def test_輪の時刻の種類が上限を超えたら落とす():
    """長尺の `ring` は日を名指ししませんが、**時刻の種類のぶんだけ同じ日に着きます。**

    20種類の時刻 × 20本 なら、その全部が同じ日の 20本 になります。
    """
    when = [str(h) for h in range(0, 20)]
    keep, notes = cap_by_density(when, cap=13, ledger={})
    assert len(keep) == 13
    assert notes


def test_控えが読めなくてもこの回の中の詰め込みは止まる():
    """控えが空でも（読めなくても）、**この回が同じ日へ積むぶんは数えます。**"""
    when = [f"2026-09-01@{h}" for h in range(0, 24)]
    keep, _ = cap_by_density(when, cap=13, ledger={})
    assert len(keep) == 13


def test_上限に届かない回は何も落とさない():
    when = [f"2026-09-01@{h}" for h in range(9, 14)]
    keep, notes = cap_by_density(when, cap=13, ledger={})
    assert keep == list(range(len(when)))
    assert notes == []
