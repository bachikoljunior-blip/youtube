"""**`--keep 0` でも、きょうの1本は外れないこと。**（2026-09-02・規則5）

## なぜ要るか（オーナー指示の中に、そのまま両方が入っています）

固定その4（`CLAUDE.md` 冒頭・`src/house_rule.OWNER_VERBATIM_SAME_DAY`）:

    「現在の日付にしか予約しないってことだからね？」

その回に渡された手は、**2つを一度に**言っています:

    「`python scripts/pool_drain.py --apply --keep 0`
      **`--keep 0` です** —— 先の日付には1本も残さないので。
      **ただし今日 09/02 の1本が未公開で残っているなら、それは外さないこと。**」

**`--keep 0` は、素直に読むとその両方を満たせません。** `plan()` は
公開時刻の**早い順**に `keep` 本 残すので、きょうの1本が一覧の先頭に居れば
**それが最初に外れます。**

**そして、きょうの1本はいちばん取り返しがつきません** —— 明日ぶんは
明日の窓で外せますが、きょうの本を外すと**その日の公開が 0本**になります
（`CLAUDE.md`「4. 投稿を途切れさせないこと」）。
2026-08-31 に、まさに同じ形で「きょうの1本」が 14本 のうちの1本として外れ、
入れ直しが次の窓まで待ちになった実測があります
（`pool_drain.pool()` の註・`tests/test_pool_drain_keeps_new.py`）。

## この検査が押さえているもの

    1. 規則5 の下で `keep=0` にしても、**きょう（JST）の予約は残ること**
    2. `keep` が数えるのは**明日以降のぶんだけ**であること
    3. 明日以降は `keep=0` で**1本も残らない**こと（甘くなっていないこと）
    4. 規則5 が外れたら、**素直な「早い順に keep 本」へ戻ること**
       （＝ 分けを消したのではなく、規則に紐づけてあること）

**戻すにはこの検査を消すしかありません。**
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import pool_drain  # noqa: E402
from src import house_rule  # noqa: E402

JST = timezone(timedelta(hours=9))

#: 2026-09-02 13:40 JST —— きょうの1本（22:00）はまだ公開されていない。
NOW = datetime(2026, 9, 2, 13, 40, tzinfo=JST).astimezone(timezone.utc)


def _row(vid: str, when: str) -> dict:
    """`pool()` が返す形（`at` は tz つきの datetime）。"""
    return {"id": vid, "at": datetime.fromisoformat(when).astimezone(timezone.utc),
            "title": f"題 {vid}", "topic": f"t-{vid}"}


def _rows() -> list[dict]:
    return [
        _row("today", "2026-09-02T22:00:00+09:00"),      # きょう・未公開
        _row("tomorrow", "2026-09-03T20:00:00+09:00"),   # 明日
        _row("far1", "2026-09-24T20:00:00+09:00"),       # 作り置き
        _row("far2", "2026-09-24T21:00:00+09:00"),
    ]


def test_keep_zero_still_keeps_today():
    """**1・2・3 をまとめて**: `keep=0` できょうは残り、明日以降は全部 外れる。"""
    assert house_rule.same_day_only(), "規則5 が外れています（この検査の前提）"
    kept, drop = pool_drain.plan(_rows(), 0, now=NOW)
    assert [r["id"] for r in kept] == ["today"], kept
    assert [r["id"] for r in drop] == ["tomorrow", "far1", "far2"], drop


def test_keep_counts_only_the_days_ahead():
    """**`keep` が数えるのは明日以降だけ。** きょうのぶんを食べないこと。"""
    kept, drop = pool_drain.plan(_rows(), 1, now=NOW)
    assert [r["id"] for r in kept] == ["today", "tomorrow"], kept
    assert [r["id"] for r in drop] == ["far1", "far2"], drop


def test_no_today_row_is_not_a_free_pass():
    """**きょうの本が無い回は、`keep=0` で全部 外れること**（甘くなっていない）。

    実測 2026-09-02 の控えがこの形です（13:00 に公開ずみ ＝ きょうの行が無い）。
    ここで1本 残す実装だと、**明日ぶんが1本 予約に残ります** ＝ 規則5 に反します。
    """
    rows = [r for r in _rows() if r["id"] != "today"]
    kept, drop = pool_drain.plan(rows, 0, now=NOW)
    assert kept == [], kept
    assert len(drop) == 3, drop


def test_falls_back_when_the_rule_is_lifted(monkeypatch):
    """**規則5 が外れたら、素直な「早い順に keep 本」へ戻ること。**

    分けを消したのではなく、規則に紐づけてあることを見ます ——
    `SAME_DAY_SCHEDULING_ONLY` を `False` にすると、きょうの1本も
    `keep` の数え方の中に戻ります。
    """
    monkeypatch.setattr(house_rule, "SAME_DAY_SCHEDULING_ONLY", False)
    kept, drop = pool_drain.plan(_rows(), 1, now=NOW)
    assert [r["id"] for r in kept] == ["today"], kept
    assert [r["id"] for r in drop] == ["tomorrow", "far1", "far2"], drop


def test_calendar_hold_is_silent_under_the_rule():
    """**暦の穴で池化を止めないこと**（規則5 の下では、穴は欠陥ではありません）。

    この門は 2026-09-02 01:0x に「穴を埋めるほうが先」として入りました。
    埋める手は `reschedule.py --compact --apply`（先の日付へ並べ直す手）で、
    **規則5 の下では禁じられている手**です。門が残っていると、
    オーナーが名指しした `--apply --keep 0` が `--despite-gap` 無しでは
    **1本も外せません**でした。
    """
    assert house_rule.same_day_only(), "規則5 が外れています（この検査の前提）"
    assert pool_drain._calendar_hold() == []
