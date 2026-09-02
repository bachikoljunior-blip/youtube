"""**`--compact --apply` は、規則5 の下で1本も動かさないこと。**（2026-09-02）

## なぜ要るか（**この repo でいちばん危ない1手だったから**）

オーナー原文（`CLAUDE.md` 冒頭「固定その4」・`src/house_rule.OWNER_VERBATIM_SAME_DAY`）:

    「現在の日付にしか予約しないってことだからね？」

＝ **その日の1本を、その日に予約する。先の日付には1本も置かない。**

`scripts/reschedule.py --compact` がやるのは、まさに
**「先の日付へ 1日1本ずつ並べ直す」**ことです。2026-09-02 の実物で撃つと
「09/03〜09/27 へ 25本」の案が出ます —— **その25本 は全部 先の日付**です。

**そして、この手はあちこちから名指しされていました**:

    src/next_slot.calendar_lines()   毎周いちばん最初の画面（`[暦]`）
    scripts/pool_drain._calendar_hold()  池化を**止めて**、代わりにこれを勧める
    docs/trigger_main.md §4          「6択より先に撃つこと」
    受け取り帳の申し送り **3件**      「枠が戻る 16:00 に、まず これを撃つこと」

**どれも直しましたが、申し送りは残り、次の回はそれを読みます。**
だから最後の砦をここに置きます —— **道具そのものが撃たない。**

## 「案は出す・撃たない」にしてある理由

規則5 が外れた回が、そのまま読めるようにするためです。
**割り当ての印字は今までどおり**で、最後に「この手は、いま撃てません」と言い、
逆向きの手（`pool_drain --apply --keep 0`）を名指しします。

## この検査が押さえているもの

    1. `house_rule.same_day_only()` が真のあいだ、`_compact()` は
       `--apply` を付けても `uploader._service()` に**到達しない**
    2. そのとき、禁じ手ではなく**外す手**を名指しすること
    3. 規則5 が外れたら、その門は**消える**こと（案を出したあと `--apply` へ進む）

**戻すにはこの検査を消すしかありません。**
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src import house_rule  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "reschedule_mod", ROOT / "scripts" / "reschedule.py")
reschedule = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reschedule)


class _Args:
    """`_compact()` が読む欄だけ（`argparse` の既定と同じ値）。"""

    apply = True
    max = 195
    #: **`None` にすること**（CLI の既定と同じ）。数を決め打つと、
    #: `--max-days` の自動探しを飛ばして「後ろへ動かす割り当て」で落ちます
    #: ＝ **この門に届く前に死ぬ**ので、何も検査できません（1発目がそれ）。
    max_days = None
    min_days = 8.0
    step_min = 30
    hour = 9
    until_hour = 21
    lead_min = 20
    allow_gap = True
    force_window = True
    since = None
    per_day = 1


def _run(monkeypatch, capsys) -> str:
    """`_compact()` を撃って、印字を返す。**口へ行ったら、そこで落とす。**"""
    def _boom(*_a, **_k):
        raise AssertionError("**撃ってはいけません** —— `uploader._service()` に届きました")

    monkeypatch.setattr(reschedule.uploader, "_service", _boom)
    rc = reschedule._compact(_Args())
    assert rc == 0, rc
    return capsys.readouterr().out


def test_規則5では1本も動かさない(monkeypatch, capsys):
    """**1 と 2**: 口へ行かず、外す手を名指しすること。"""
    if not house_rule.same_day_only():
        pytest.skip("規則5 が外れています（この検査の前提）")
    out = _run(monkeypatch, capsys)
    assert "この手は、いま撃てません" in out, out[-800:]
    assert "pool_drain.py --apply --keep 0" in out, out[-800:]
    # **案そのものは出ていること**（規則が外れた回が読むため）
    assert "[compact]" in out


def test_規則5を外すと門が消える(monkeypatch, capsys):
    """**3**: 門を規則に紐づけてあること（消したのではないこと）。

    規則を外すと `--apply` の先へ進み、`uploader._service()` に届きます ——
    その `AssertionError` が出ることで、「門が消えた」と言えます。
    """
    monkeypatch.setattr(house_rule, "SAME_DAY_SCHEDULING_ONLY", False)
    with pytest.raises(AssertionError, match="撃ってはいけません"):
        _run(monkeypatch, capsys)
