"""**撃てる回の画面を、撃てない回より静かにしないこと**（2026-09-02 12:3x に測った）。

`src/next_slot._calendar_quota_lines()` は長らく、向きが逆でした:

    403 の回（＝ **撃てない**回）   `[!] **この窓では 403 です** …
                                   **そこで最初に撃つのがこれです**`   ← 強い
    枠の在る回（＝ **撃てる**回）   `枠は在ります（0 / 10,000単位）`     ← 弱い

**号令が、撃てない回にだけ出ていました。**

実測（`scripts/retro.py` の「次の回へ」）—— `reschedule --compact --apply` を
「枠が戻る 16:00 に撃つこと」と書いた回が **3件** 並んでおり、**3件とも撃たれていません。**
暦の空きは 20日 のまま、いちばん長い空白は **19日 連続**。

枠が戻ったあとの回が読むのは `used < cap` の枝です。そこに「枠は在ります」としか
書いていなければ、**申し送りにどれだけ大きく書いても、その回の画面では
403 の回より静かになります。**
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import next_slot  # noqa: E402


class _Ledger:
    DAY_UNITS = 10_000

    def __init__(self, used: int) -> None:
        self._used = used

    def spent(self, _t):
        return {"data": self._used}


def _lines(monkeypatch, used: int, empty: int = 20, shut: bool = None):
    """`shut` は**観測した 403**（`upload_cap.day_quota().open is False`）。

    **既定は `used >= cap` に合わせてあります** —— 帳面と観測が一致する回。
    食い違う回は `shut` を明示すること（下の `test_観測した403のほうで分岐する`）。
    """
    import src.quota_ledger as ql
    import src.upload_cap as uc
    monkeypatch.setattr(ql, "spent", lambda _t: {"data": used})
    monkeypatch.setattr(ql, "DAY_UNITS", 10_000)
    if shut is None:
        shut = used >= 10_000
    monkeypatch.setattr(uc, "day_quota",
                        lambda _t=None: SimpleNamespace(open=not shut))
    t = datetime(2026, 9, 2, 7, 5, tzinfo=timezone.utc)
    return "\n".join(next_slot._calendar_quota_lines(t, empty=empty))


def test_撃てる回に号令が出る(monkeypatch):
    got = _lines(monkeypatch, used=0)
    assert "いま撃てます" in got
    assert "最初の1手" in got, "撃てる回に、何を最初に撃つかが書かれていません"


def test_撃てない回は_戻る時刻を言う(monkeypatch):
    got = _lines(monkeypatch, used=16_043)
    assert "403" in got
    assert "戻るのは" in got
    assert "いま撃てます" not in got


def test_観測した403のほうで分岐する(monkeypatch):
    """**帳面の見積りが枠を超えていても、403 を観測していなければ撃てます。**

    `upload_cap.day_quota()` は2つの場合に「押してよい」と答えます ——
    403 のあとに呼び出しが通った（＝ あれは日枠ではなかった）ときと、
    枠が読めなかったとき。**どちらも `spent()` は cap を超えたまま**なので、
    見積りで分岐すると**この関数だけが黙り**、窓を1つ丸ごと落とします。
    """
    got = _lines(monkeypatch, used=16_043, shut=False)
    assert "いま撃てます" in got, (
        "`day_quota()` が『押してよい』と言っている回で黙っています —— "
        "判定は帳面の見積りではなく、観測した 403 です")
    assert "16,043" in got, "見積りは但し書きとして残すこと（撃つ前に読めるように）"
    assert "公表値" in got, "なぜ超えていても撃ってよいかが書かれていません"


def test_見積りが枠の内側でも観測した403が勝つ(monkeypatch):
    """逆向き。**観測した 403 は、見積りが小さくても勝ちます。**"""
    got = _lines(monkeypatch, used=0, shut=True)
    assert "403" in got and "いま撃てます" not in got


def test_枠が読めない回は撃つ側へ倒す(monkeypatch):
    """`day_quota()` が投げたら「押してみる」。**黙るほうへ倒さないこと。**"""
    import src.quota_ledger as ql
    import src.upload_cap as uc

    def boom(_t=None):
        raise RuntimeError("読めません")

    monkeypatch.setattr(ql, "spent", lambda _t: {"data": 16_043})
    monkeypatch.setattr(ql, "DAY_UNITS", 10_000)
    monkeypatch.setattr(uc, "day_quota", boom)
    t = datetime(2026, 9, 2, 7, 5, tzinfo=timezone.utc)
    got = "\n".join(next_slot._calendar_quota_lines(t, empty=20))
    assert "いま撃てます" in got


def test_撃てる回のほうが静かにならない(monkeypatch):
    """**これがこの検査の本体です。** 強さが逆転したら赤くします。"""
    open_win = _lines(monkeypatch, used=0)
    closed = _lines(monkeypatch, used=16_043)
    assert open_win.count("[!]") >= closed.count("[!]"), (
        "撃てる回の画面が、撃てない回より静かです —— "
        "3件の申し送りが撃たれずに流れた形に戻っています")
    assert len(open_win) >= len(closed) * 0.8, "撃てる回の本文が短すぎます"


def test_空きの日数を撃てる回に見せる(monkeypatch):
    got = _lines(monkeypatch, used=0, empty=20)
    assert "20日" in got, "撃たなかったときに何が持ち越されるかが書かれていません"
    # 鳴っていない回（空き 0）には、この一行は出さない
    quiet = _lines(monkeypatch, used=0, empty=0)
    assert "持ち越します" not in quiet


def test_枠が読めない回は黙る(monkeypatch):
    import src.quota_ledger as ql

    def boom(_t):
        raise RuntimeError("読めません")

    monkeypatch.setattr(ql, "spent", boom)
    t = datetime(2026, 9, 2, 7, 5, tzinfo=timezone.utc)
    assert next_slot._calendar_quota_lines(t, empty=20) == [], \
        "読めないことを『撃てます』として印字しないこと"
