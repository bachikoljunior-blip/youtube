"""**取り置きの門は、読みで焼けた枠を「余っている」と答えないこと**（2026-09-01 に足した）。

## なぜ要るか（実測。この数はどちらも同じ窓・同じ瞬間のものです）

窓 2026-09-01 07:00Z 起点を、2つの計器で同時に読むと:

    `upload_cap.measured_budget()["spent"]`   **9,400単位**  ← 書き込みだけ数える
    `quota_ledger.spent()["data"]`           **13,359単位**  ← `HttpRequest.execute` を1点で包む
                                              差 **3,959単位**（本当の消費の 30%）

差は**読み**です —— `search.list` 3,300単位（33回・**単価 100**）ほか計 3,859単位。
`RESERVE_UNITS` の註は「**読みは 1単位**なので 400単位 ＝ 読み 400回」と
書いていますが、`history.channel_video_ids` の1掃引だけで
**3,300単位 ＝ 取り置き 8.25個ぶん**が、門からは1単位も見えずに消えます。

註の「覆る条件」——「**関門が止めていないのに 403**」—— は、この窓で成立:
**403 を 45回 観測**。枠が戻るのは 09/01 16:00 JST ＝ **11.2時間、読みも書きも通りません。**

## いくつ早く止まるか（**この窓の帳面を、時刻順に足し直した数**）

    08:05:50Z  帳面の累計が **9,614単位**（＝ 10,000 − 400 を越える）
               越えさせたのは `reschedule.py:_update`（＝ `pool_drain --apply`）
    08:41:54Z  **最初の 403**（`videos.update Cq9WRKLMeHs`）
               ↑ **36分 あと。**その間に **3,746単位**が、止まらずに焼けています

つまりこの門は、**壁に当たる 36分 手前で止まり、400単位 を残します。**
残らなかった側が実測です —— 窓は 08:41Z に死に、**そこから 11.2時間**
`verdict` の読みも `improve` の書き込みも撃てないままです。

**それが到達日に効く道**: `eta.py` は毎周「軌跡の腕が動くのは前提を1件 閉じたときだけ」と
印字します。閉じるのに要る読みも、規則3の `improve`（題名・説明・サムネ ＝ 50単位）も、
**枠の向こう側**になります。`docs/trigger_main.md` §4 が
「**枠が尽きた回に残るのは、事実上 `fix` だけ**」と書いているのは、この帰結です。

## この検査が見ているもの

1. **帳面が黙る窓では、何も止めないこと**（行が0 ＝ 推測。上の門と同じ規則）
2. 帳面の消費が `DAY_UNITS - RESERVE_UNITS` に届いたら止めること
3. **書き込みしか数えない側が「余っている」と答えても、帳面の側が勝つこと**
   （＝ この検査の本体。緩む向きには効かないこと）
4. `YT_NO_RESERVE=1` の逃げ道は、こちらにも効くこと

## 覆る条件

`quota_ledger.COST` は**公表値**です。403 が **9,600単位 より手前**で出るように
なったら `DAY_UNITS` が高すぎます —— そのときは実測で下げること
（この検査は `DAY_UNITS` を読むので、下げれば一緒に動きます）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import quota_ledger, upload_cap                       # noqa: E402

#: 「書き込みだけの門」から見ると、まだたっぷり余っている窓
_ROOMY = {"floor": 10_000, "spent": 0, "left": 10_000, "from": "08/27"}


def _ledger(monkeypatch, *, data: int, n: int = 1, by=None) -> None:
    monkeypatch.setattr(quota_ledger, "spent",
                        lambda now=None: {"data": data, "n": n,
                                          "by": by or {"だれか": data},
                                          "method": {}, "other": 0})


def test_帳面に行が無い窓では止めない(monkeypatch):
    """**推測で書き込みを止めないこと。** 帳面は 2026-08-31 に置いたので、
    それ以前の窓は空です。空を「使っていない」と読まないこと。"""
    monkeypatch.setattr(upload_cap, "measured_budget", lambda now=None: dict(_ROOMY))
    _ledger(monkeypatch, data=99_999, n=0)
    assert upload_cap.reserve_hold() is None


def test_書き込みだけの門が余っていると答えても_帳面の側が勝つ(monkeypatch):
    """**この検査の本体。** 実測の再現 —— 書き込み 9,400／本当 13,359。

    `measured_budget()` は「余っている」と答える形にしてあります。
    それでも止まらなければ、実測 2026-09-01 の窓（403 を 45回）が再現します。
    """
    monkeypatch.setattr(upload_cap, "measured_budget", lambda now=None: dict(_ROOMY))
    _ledger(monkeypatch, data=13_359, n=2_193,
            by={"reschedule.py:_update": 9_668,
                "history.py:channel_video_ids": 3_409})
    held = upload_cap.reserve_hold()
    assert held, ("**帳面が 13,359単位 を数えているのに、門が通しています。**"
                  " 書き込みだけを数える側が『余っている』と答えた窓です ——"
                  " 実測 2026-09-01 の窓は、ここで 403 を 45回 見ました。")
    assert "帳面" in held and "13,359" in held
    # **何が食ったかを名指しすること**（次の回が当てどころを探さずに済む）
    assert "history.py:channel_video_ids" in held


def test_取り置きのぶんが残っていれば止めない(monkeypatch):
    monkeypatch.setattr(upload_cap, "measured_budget", lambda now=None: dict(_ROOMY))
    _ledger(monkeypatch, data=quota_ledger.DAY_UNITS - upload_cap.RESERVE_UNITS - 1)
    assert upload_cap.reserve_hold() is None


def test_取り置きに届いたら止める(monkeypatch):
    monkeypatch.setattr(upload_cap, "measured_budget", lambda now=None: dict(_ROOMY))
    _ledger(monkeypatch, data=quota_ledger.DAY_UNITS - upload_cap.RESERVE_UNITS)
    assert upload_cap.reserve_hold()


def test_逃げ道はこちらにも効く(monkeypatch):
    """**外す向きは残すこと。** 使った回は理由を JOURNAL に。"""
    monkeypatch.setattr(upload_cap, "measured_budget", lambda now=None: dict(_ROOMY))
    _ledger(monkeypatch, data=99_999)
    monkeypatch.setenv("YT_NO_RESERVE", "1")
    assert upload_cap.reserve_hold() is None


def test_帳面が壊れていても本体を止めないこと(monkeypatch):
    """**記録の側で何が起きても、判断は下の門へ落ちること**（`install()` と同じ約束）。"""
    def boom(now=None):
        raise RuntimeError("帳面が読めない")

    monkeypatch.setattr(quota_ledger, "spent", boom)
    monkeypatch.setattr(upload_cap, "measured_budget", lambda now=None: dict(_ROOMY))
    assert upload_cap.reserve_hold() is None
