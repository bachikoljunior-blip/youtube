"""**予約を外す手は、移動の上限に数えないこと。**（2026-09-05 06:1x に払って足した）

## なぜ要るか（**この上限に 50単位 と1回の踏み外しを払った**）

`upload_cap.MOVE_CAP` が止めているのは**振動**です ——「1つの掃きが1か月 先へ、
19分後の掃きが1か月 手前へ引き戻す（中央値 30日）。**効くのは最後の1回だけ**なので
3つ目以降は定義上むだ」（実測 8,900単位）。

**`publish_at=None`（予約を外して池へ戻す手）は、その置き直しではありません。**
置き先を選び直しているのではなく、**その本を枠から降ろしている**ので、
次の1回で上書きされる余地がありません。

実測 2026-09-05::

    05:24  09/06 の空き枠へ `DtpnSVFDtAE` を入れた（＝ その窓で 2回目の移動）
    05:40  きょうだいが「その題材（`s-shokibo-11-12kagetsu-59man`）は
           09/03 に `9zkfjEH48PY` として公開ずみ」と名指し
           → 規則1 は 1日1本 なので、そのままなら **09/06 の取り分は 0**
    06:1x  外そうとしたら **`move_hold` が止めた**（「上限 2」）
           → `YT_NO_MOVE_CAP=1` で越えるしかなかった

**＝ 上限が、上限の目的（むだを止める）と逆向きに働きました。**
止めた先に在ったのは 50単位 の節約ではなく、**枠1日ぶん**
（ショートの齢48h 中央値 164回／規則の密度の日なら 1,049回・`src/slot_cost.py`）。

**覆る条件**: 外す手が振動の一部として使われ始めたら（外す→入れる→外す）、
数え直すこと。判定は `moves_in_window()` の中身ではなく **呼ぶ側が渡す旗**なので、
数え方を変えずに戻せます。
"""
from __future__ import annotations

import re
from pathlib import Path

from src import upload_cap

ROOT = Path(__file__).resolve().parents[1]


def _blocked(monkeypatch, n: int) -> None:
    """その窓で `n` 回 動かした本、という状態を作る（**実物は読みません**）。"""
    monkeypatch.delenv("YT_NO_MOVE_CAP", raising=False)
    monkeypatch.delenv("YT_FORCE_UPDATE", raising=False)
    monkeypatch.setattr(upload_cap, "moves_in_window", lambda *_a, **_k: n)


def test_置き直しは上限で止まる(monkeypatch):
    """**上限そのものは動かしていません**（振動を止める目的は生きている）。"""
    _blocked(monkeypatch, upload_cap.MOVE_CAP)
    why = upload_cap.move_hold("vvvvvvvvvvv")
    assert why and "上限" in why, why


def test_外す手は上限で止まらない(monkeypatch):
    """**枠から降ろす手は「置き直し」ではありません。**"""
    _blocked(monkeypatch, upload_cap.MOVE_CAP + 5)
    assert upload_cap.move_hold("vvvvvvvvvvv", unschedule=True) is None


def test_外す手の判定は呼ぶ側が渡している():
    """**`reschedule._update` が旗を渡していること。**

    `upload_cap` の側に条件を書き足しても、呼ぶ側が渡さなければ何も変わりません
    （この repo の「関数は在ったのに、どの回からも呼ばれていなかった」の形）。
    """
    src = (ROOT / "scripts" / "reschedule.py").read_text(encoding="utf-8")
    calls = [m.group(1) for m in
             re.finditer(r"upload_cap\.move_hold\((.{0,160}?)\)", src, re.S)]
    assert calls, "`reschedule.py` が `upload_cap.move_hold(` を呼んでいません"
    # 註や docstring の中の `move_hold()`（引数なし）は数えません。
    real = [c for c in calls if c.strip()]
    assert real, f"引数のある呼び出しが1つもありません: {calls}"
    assert any("unschedule=" in c and "publishAt" in c for c in real), real
