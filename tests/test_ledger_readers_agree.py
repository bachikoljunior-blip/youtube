"""**同じ帳面を読む関数どうしが、同じ答えを出すこと。**

## なぜこの検査が要るか（2026-08-25）

`data/uploaded.jsonl` の読み方には規則が2つあります。

    1. **後の行を採る** —— 足すだけの帳面なので、予約を動かすと同じ
       `video_id` の行が増える。最初の行は動かされた過去の予定
    2. **JST の日で割る** —— `at` は UTC。素直に採ると JST の朝が前日に落ちる

**この2つを、3つの関数が別々に持っています。**

    src/ab_split.published()             8/25 に直した
    src/motion_groups.scheduled_at()     8/25 に直した
    scripts/eta.published_at()           **直っていなかった（5件目）**
    scripts/trajectory.published_per_day()  **直っていなかった（6件目）**
                                         —— 8/25 に `motion_groups` を借りる形へ直した

群の分母が条件と食い違う形は 8/19・8/23・8/25（2件）・8/25（`eta`）で**5件**出ており、
**5件とも「1つ直しても、同じ帳面の別の読み手が古いまま残る」形**でした。
1件ずつ直すのをやめるために、**読み手どうしを突き合わせる**のがこの検査です。

**新しい読み手を書いたら、ここに足すこと。** 足さないなら、既存の3つの
どれかを借りること —— **どちらもしないと6件目になります。**
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import timezone, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import ab_split, motion_groups  # noqa: E402

JST = timezone(timedelta(hours=9))


def _traj():
    spec = importlib.util.spec_from_file_location(
        "_traj_mod", ROOT / "scripts" / "trajectory.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _eta():
    spec = importlib.util.spec_from_file_location("_eta_mod", ROOT / "scripts" / "eta.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


#: **2つの規則が両方効く1本。**
#:   - 行が2つある（後の行 = 09-19T20:00Z が正）
#:   - その後の行は **UTC で 09/19・JST で 09/20** ＝ 日をまたぐ
#: だから「最初の行を採る」実装と「UTC で割る」実装は、**別々の日**を答えます。
LEDGER = [
    {"video_id": "v1", "topic": "t-1", "at": "2026-09-22T04:30:00Z"},
    {"video_id": "v1", "topic": "t-1", "at": "2026-09-19T20:00:00Z"},
]
#: 3つの読み手が一致すべき答え（JST の日）
WANT_DAY = "2026-09-20"


@pytest.fixture()
def ledger(tmp_path: Path) -> Path:
    p = tmp_path / "uploaded.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in LEDGER) + "\n", encoding="utf-8")
    return p


def test_四つの読み手が同じ日を答える(ledger: Path, tmp_path: Path):
    """**後の行を採る**と**JST で割る**が、4つとも効いていること。

    4つ目（`scripts/trajectory.published_per_day()`）は **6件目**でした ——
    このファイルが書かれたのと同じ日に、`供給（本/日）` を
    「行数 × UTC の日」で数えているのが見つかっています
    （実測: 08/26 が 18本、08/27 が 15本 → 正しくは **14本 / 19本**）。
    **借りる形へ直したので、ここでは「借りた先と同じ日を答える」ことだけを見ます。**
    """
    # 1) ab_split
    rows = ab_split.published(ledger)
    assert len(rows) == 1, "**1行1件ではなく1本1件**（動かした本を2回数えない）"
    got_ab = rows[0]["publish"].isoformat()

    # 2) motion_groups
    got_mg = motion_groups.jst_day(motion_groups.scheduled_at(ledger)["v1"])

    # 3) eta（観測が無いので控えが唯一の出どころ ＝ 5件目が出た経路そのもの）
    empty = tmp_path / "views.jsonl"
    empty.write_text("", encoding="utf-8")
    got_eta = (_eta().published_at(views_path=empty, uploaded_path=ledger)["v1"]
               .astimezone(JST).date().isoformat())

    # 4) trajectory（日ごとの本数。**1本しか居ないので {WANT_DAY: 1} になるはず**）
    traj = _traj()
    counts = traj.published_per_day(ledger, observed={})

    assert got_ab == got_mg == got_eta == WANT_DAY, (
        f"読み手どうしが食い違っています: ab_split={got_ab} "
        f"motion_groups={got_mg} eta={got_eta}（正: {WANT_DAY}）"
    )
    assert counts == {WANT_DAY: 1}, (
        f"trajectory.published_per_day が {counts} と答えました（正: {{{WANT_DAY!r}: 1}}）。"
        "**行数で数えている**か、**UTC の日で割っています**"
    )


def test_最初の行を採る実装なら落ちること(ledger: Path, tmp_path: Path):
    """**この検査が本当に5件目を捕まえるか**を、逆から確かめる。

    「最初の行を採る」＝直す前の `eta.published_at()` と同じ読み方をすると、
    答えは 09/22（JST）になり、上の検査は落ちます。**落ちなければ、
    この検査は5件目を素通りさせる形**なので、ここで固定しておきます。
    """
    first_at = LEDGER[0]["at"]                       # 最初の行 ＝ 動かされた過去の予定
    assert motion_groups.jst_day(first_at) == "2026-09-22"
    assert motion_groups.jst_day(first_at) != WANT_DAY, \
        "最初の行と後の行が同じ日なら、この標本は2つの規則を試せていない"


def test_UTCで割る実装なら落ちること():
    """**JST の規則のほう**も、逆から固定する。

    後の行は UTC で 09/19、JST で 09/20。**先頭10文字を採る**実装
    （＝ UTC の日で割る）は 09/19 と答えるので、上の検査は落ちます。
    """
    later_at = LEDGER[1]["at"]
    assert later_at[:10] == "2026-09-19", "UTC の日"
    assert motion_groups.jst_day(later_at) == WANT_DAY, "JST の日"
    assert later_at[:10] != WANT_DAY, \
        "UTC と JST が同じ日なら、この標本は日またぎを試せていない"
