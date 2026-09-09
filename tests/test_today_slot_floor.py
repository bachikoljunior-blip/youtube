"""**間隔の下限が、固定その4 の下で毎周 外れていました**（2026-09-04 07:0x に実測）。

## なぜ

`sibling_check --phase spawn` は「在庫が薄いときは、間隔の下限より生成を優先する」
（`RUNWAY_FLOOR_DAYS` ＝ 14日）を持っています。**8/16 に入れたときは正しい線**でした ——
当時は作り置きで、`runway_days()`（予約が何日先まで埋まっているか）は本当に在庫でした。

**固定その4**（オーナー原文「現在の日付にしか予約しないってことだからね？」）が入って、
`runway_days()` は**定義上 ≤1日**になりました。しかも `CLAUDE.md` はそれを
「**先の日付が空であることが、正しい状態です**」と書いています。

＝ **`runway < 14日` は毎周 真** → **間隔の下限は毎周 外れる。**
オーナーの「今までの最高速度の**二分の一**の速度でやって」（2026-09-02 18:4x）を
毎周 数え直している `quota.effective_floor_minutes()`（実測 101分）は、
**印字されるだけで、1度も効いていませんでした。** 実測の出力:

    在庫: 予約は **0.1日先**まで（下限を外す境目は 14日）
      → **間隔の下限 101分を外します。**在庫が薄いので、生成の回数のほうが目標に近い。

**この repo でいちばん多い壊れ方（言っている所と、している所が別）の、この行ぶんです。**

## 置き直した線

危ないのは「先が空なこと」ではなく **「きょうの枠がまだ空なこと」**です。
きょうの本が置かれていれば、その日の公開は続きます。置かれないまま日が暮れると、
**その日が丸ごと落ちます** —— そこだけが下限より重い。

## 【2026-09-09 09:0x に線を引き直した先を差し替えた】

この検査は `src/next_slot.today_count()` を monkeypatch して枝を測っていました。
**その控え（`data/uploaded.jsonl`）は 2026-09-05 15:01 で死んでいます** ——
同じ日に道具が `studio/` へ組み直され、新しい道具はそこを書かない。
＝ 数える元が毎日 0 を返し、`today_slot_empty()` は **4日間ずっと「まだ空です」**と答え、
下限は毎周 外れていました（**この docstring が上で書いている壊れ方の、2周目**）。

いまは `data/studio/ledger.jsonl` を読みます。**この検査もそちらを差し替えます** ——
死んだ控えを monkeypatch しても、もう何も動きません（実際、
`きょうの枠が空なら空と答える` はその形で赤くなり、残り2件は
**たまたま実物のきょうの枠が埋まっていたから緑**でした ＝ 測っていません）。
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import sibling_check  # noqa: E402

JST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 9, 9, 8, 44, tzinfo=JST)


def _ledger(tmp_path, rows):
    """台帳を1枚 書いて、その道を返す。**実物の `data/studio/ledger.jsonl` は触らない。**"""
    p = tmp_path / "ledger.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                 encoding="utf-8")
    return p


#: きょう（NOW の日）の枠へ置いた本
TODAY = {"event": "scheduled", "id": "2026-09-09-x", "video_id": "TODAY1",
         "publish_at": "2026-09-09T10:00+09:00", "at": "2026-09-09T00:33:27+09:00"}
#: きのうの本（先の日付にも過去にも、きょうの枠は埋まらない）
YDAY = {"event": "scheduled", "id": "2026-09-08-x", "video_id": "YDAY1",
        "publish_at": "2026-09-08T10:00+09:00", "at": "2026-09-08T00:54:07+09:00"}


def test_きょうの枠が埋まっていれば空でないと答える(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sibling_check, "STUDIO_LEDGER", _ledger(tmp_path, [TODAY]))
    assert sibling_check.today_slot_empty(NOW) is False


def test_きょうの枠が空なら空と答える(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sibling_check, "STUDIO_LEDGER", _ledger(tmp_path, [YDAY]))
    assert sibling_check.today_slot_empty(NOW) is True


def test_読めなければ_None_で_下限はそのまま(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**計器が黙った回だけ、いちばん速く回る形にしないこと。**

    `None` は「読めなかった」で、呼ぶ側はそのとき**下限をそのまま効かせます**
    （`--phase spawn` の枝）。`False`（＝ 埋まっている）と混ぜないこと。

    **そして「読めない」と「空」も混ぜないこと** —— 2026-09-09 に踏んだのはそちらで、
    控えが死んでいるのに `0本` と答え、`0 < 1` で「空です」になっていました。
    """
    monkeypatch.setattr(sibling_check, "STUDIO_LEDGER", tmp_path / "no-such-file.jsonl")
    assert sibling_check.today_slot_empty(NOW) is None


def test_先の日付が空でも_それだけでは下限を外さない(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**固定その4 の下では、先の日付が空なのが正しい状態です。**

    ここが `runway_days()` を見ていたあいだ、下限は毎周 外れていました。
    """
    # 台帳にきょうの本だけ（＝ 先の日付は1本も無い）でも「空でない」
    monkeypatch.setattr(sibling_check, "STUDIO_LEDGER", _ledger(tmp_path, [TODAY]))
    assert sibling_check.today_slot_empty(NOW) is False
