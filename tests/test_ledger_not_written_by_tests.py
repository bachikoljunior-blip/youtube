"""**検査は、本物の `data/runs.jsonl` に1行も書かないこと。**

## なぜ要るか（2026-09-05 06:5x に踏んだ。**実物で数えた**）

`tests/conftest.py` の `_alerts_ledger_to_tmp` は `src/alerts.py` の
`LEDGER` / `RUNS` を tmp へ向けます。**それだけでは届いていませんでした** ——
`scripts/run_marker.py` は**自分で持っている別の定数**
（`MARKS = <repo>/data/runs.jsonl`・67行目）で読み書きするので、
`rm.ship()` / `rm.claim()` / `rm.mark()` を直接呼ぶ検査は
**本物の台帳へ書いていました。**

実測（この回・窓 504行）: 検査が書いた行は `ship`「ふつうの回」6件・
`fix_gate`「test」6件・`verdict_gate`「test」2件。

**`src/ledger_holes.py` が毎周 鳴らしている「`data/runs.jsonl` の `lever` が空」は、
これが全部でした** —— ship 242件 中 空 6件 に対し、検査の行を外すと
**236件 中 0件**。あの警告の本文が「**書く道を先に直すこと**」です。

**意図は最初から在りました** —— `run_marker.py` の 143行目が
「**`MARKS` から辿らないこと。あちらは検査が tmp へ差し替えます**」と
書いています。**書いてあるのに、差し替える側が無かった**だけ。
だから註ではなく検査にします（`run_marker` が自分の註に2度 書いているとおり ——
**「註や警告ではなく、通さないことだけが効いています」**）。

**この検査は時計を読みません**（`tests/test_tests_are_clockless.py`）。
"""

from __future__ import annotations

from pathlib import Path

import scripts.run_marker as rm

#: 本物の台帳。**`rm.MARKS` から辿らないこと** —— あれは差し替えられている側で、
#: それを正解にすると、差し替えが外れた日にこの検査ごと黙ります。
REAL = Path(rm.__file__).resolve().parent.parent / "data" / "runs.jsonl"


def test_marks_is_redirected_away_from_the_repo():
    """`run_marker.MARKS` が、本物の `data/runs.jsonl` を指していないこと。"""
    assert rm.MARKS.resolve() != REAL.resolve(), (
        "`scripts/run_marker.py` の `MARKS` が本物の台帳を指したままです。"
        "`tests/conftest.py` の `_alerts_ledger_to_tmp` が差し替えます —— "
        "外れると、検査を1回 走らせるたびに ship / fix_gate / claim の"
        "偽の行が `data/runs.jsonl` へ入り、`lever` が空のまま積もります"
        "（`src/ledger_holes.py` が鳴るのはこれ）。"
    )


def test_ship_does_not_touch_the_real_ledger():
    """`ship()` を呼んでも、本物の台帳は**1バイトも動かない**。"""
    before = REAL.read_bytes() if REAL.exists() else None

    rm.ship("検査が書いた行（本物の台帳へ入ってはいけない）", kind="fix", moves=0)

    after = REAL.read_bytes() if REAL.exists() else None
    assert after == before, (
        "検査が本物の `data/runs.jsonl` を書き換えました。"
        "`tests/conftest.py` の `MARKS` の差し替えを見ること。"
    )


def test_claim_does_not_touch_the_real_ledger():
    """`claim()` も同じ。**書く口は1つずつ塞ぐこと。**"""
    before = REAL.read_bytes() if REAL.exists() else None

    rm.claim("検査が書いた claim（本物の台帳へ入ってはいけない）")

    after = REAL.read_bytes() if REAL.exists() else None
    assert after == before, (
        "検査が本物の `data/runs.jsonl` を書き換えました（`claim`）。"
    )
