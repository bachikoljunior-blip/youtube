"""**その型の本がどこにも1本も無い日付を、台帳が「判定できる」と言わないこと**
（`scripts/deadline_check._outside_supply`）。**API 0単位・純関数。**

## なぜ要るか（2026-09-05 05:2x・サブの回。前の回の申し送り 2. を撃って確かめた）

`kind: after` は**時計だけ**で日を出します。`data_file:` を書いても見るのは
「その計器が新しいか」で、**その要件が数えている本が在るか**は誰も見ていません。

実測（この回に撃った数）::

    daily_pick.treated_count('ショート') = (0, 216)     ← 処置は **1本も公開されていない**
    grep 'style: outside_short' config/topics.yaml = **0件**   ← 札すら無い
    09/06 の枠は既存の池のショート `DtpnSVFDtAE`（`treated_probe` は `unknown`）

それでも `deadline_check.py` は `[OK] 09-08 … → 判定できるのは 09-08` と印字し、
`arm_speed.forward()` の θ は腕 `per_video` の見込みにその1件を数えていました。

**長尺の側は同じ穴を 2日 かけて踏んでいます**（`treated_probe` の註・
`config/hypotheses.yaml` 611行 の【2026-09-04 22:3x 訂正】）。**ショートは札すら無いまま
同じ位置に居ました。** 下の5本が、その境目を実物で押さえます。

**この検査が守っているのは「止めること」ではなく「止める境目」です** ——
札が在る形（長尺）は止めません。止めると、いま焼き直している本の判定日まで消えます。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import deadline_check as dc  # noqa: E402

WHAT_SHORT = ("外の作りを写したショートが1本 公開されて 48時間"
              "（`data/views.jsonl`・齢48h・`src/daily_pick.aged_views`）")
WHAT_LONG = ("外の作りを写した長尺が1本 公開されて 48時間"
             "（`data/views.jsonl`・齢48h・`src/daily_pick.aged_views`）")


@pytest.fixture()
def counts(monkeypatch):
    """`treated_count` と `style:` の件数を、この検査から差し込めるようにする。"""
    box: dict[str, object] = {"treated": (0, 216), "drafts": 0}

    def _tc(form, **_kw):
        return box["treated"]

    monkeypatch.setattr(dc, "_outside_style_topics", lambda tag: box["drafts"])
    import src.daily_pick as dp
    monkeypatch.setattr(dp, "treated_count", _tc)
    return box


def test_札も処置も無い形は_判定できる日を出さない(counts):
    ans = dc._outside_supply(WHAT_SHORT)
    assert ans is not None
    assert ans.ready is None
    assert ans.unreachable is True
    assert "0本／216本" in ans.why


def test_札が在る形は止めない(counts):
    """長尺は `style: outside_long` が実物に在る。**止めると焼き直し中の本の判定日が消えます。**"""
    counts["drafts"] = 3
    assert dc._outside_supply(WHAT_LONG) is None


def test_処置が1本でも公開されていれば止めない(counts):
    counts["treated"] = (1, 216)
    assert dc._outside_supply(WHAT_SHORT) is None


def test_関係のない_what_は素通りする(counts):
    assert dc._outside_supply("`data/views.jsonl` に 09/05 までの公開日が入っていること") is None


def test_実物の_topics_yaml_に_outside_long_が在り_outside_short_は無い():
    """**この検査は実物を読みます** —— 札を足したら、ここが最初に教えます。

    `outside_short` が 1件 以上になったら、上の `[!!]` は自分で消えます
    （そのときこの行を `>= 1` へ直すこと。**先に直さないこと**）。
    """
    assert dc._outside_style_topics("outside_long") >= 1
    assert dc._outside_style_topics("outside_short") == 0
