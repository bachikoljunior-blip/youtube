"""**「いま閉じられる」と言えるのは、計器が日を出した前提だけ。**（2026-08-27）

`drift.closable_within()` は、`deadline_check` が判定日を出せなかった前提を
**`deadline`（置いた回の勘）へ落として**在庫に数えます。在庫としては正しい ——
窓の中で判定できるようになりうるからです。

**そこから「次に1件 閉じられるのは X」を作っていたのが誤りでした。** 実測 08/27:

    drift  「次に1件 閉じられるのは **2026-08-26**（期日は1日 過ぎています
            ＝ **この回に閉じられます**）」
    deadline_check  同じ前提を **[..] まだ数えはじめたところです**（要 3 ／ いま 0）

**撃ちに行った回は空振りします。** この repo で何度も出ている
「印字と、その印字が根拠にする道具の食い違い」です。

あわせて、`warming` の**待ち方**も1つに丸めていました ——
`at_time_jst` の要件は「今日の決まった時刻に出る」もので、伸び率とは無関係です。
`deadline_check.lines()` は既に分けており、**drift だけが丸めていました。**
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import drift as D  # noqa: E402


def test_勘の期日は次に閉じられる日に使わない(monkeypatch):
    """`_closable_est` の付いた在庫しか無いときは、**日を出さない**。"""
    stock = [{"claim": "a", "deadline": "2026-08-26",
              "_closable_on": "2026-08-26", "_closable_est": True}]
    monkeypatch.setattr(D, "closable_within", lambda *a, **k: stock)
    monkeypatch.setattr(D, "rounds_per_day", lambda *a, **k: 16.0)
    monkeypatch.setattr(D, "closed_per_day", lambda *a, **k: 6)
    out, dry = D.supply_report("2026-08-27")
    assert "この回に閉じられます" not in out, out
    assert "次に閉じられる日は出せません" in out
    assert not dry, "在庫はあるので、止める側へ倒さないこと"


def test_計器が出した期日ならそのまま使う(monkeypatch):
    stock = [{"claim": "a", "deadline": "2026-08-26",
              "_closable_on": "2026-08-26", "_closable_est": False}]
    monkeypatch.setattr(D, "closable_within", lambda *a, **k: stock)
    monkeypatch.setattr(D, "rounds_per_day", lambda *a, **k: 16.0)
    monkeypatch.setattr(D, "closed_per_day", lambda *a, **k: 6)
    out, _ = D.supply_report("2026-08-27")
    assert "この回に閉じられます" in out


def test_時計待ちは伸び率の話にしない(monkeypatch):
    """`at_time_jst` の要件は「今日の決まった時刻に出る」もので、伸び率とは無関係。"""
    h = {"claim": "c", "deadline": "2026-08-27",
         "needs": [{"kind": "after", "on_date": "2026-08-27", "at_time_jst": "22:00"}]}
    monkeypatch.setattr(D, "_judge_state_by_claim",
                        lambda: {"c": ("warming", None, None, 0, "")})
    _, blocked = D.split_overdue([h], "2026-08-27")
    assert len(blocked) == 1
    _, why, todo = blocked[0]
    assert "22:00" in why, why
    assert "伸び率が出ないので" not in why, "時計待ちを、伸び率の話に丸めています"
    assert "伸び率の話ではありません" in todo


def test_伸び率待ちは今までどおり(monkeypatch):
    """**分けたぶんで、元の側を壊さないこと。**"""
    h = {"claim": "c", "deadline": "2026-08-27", "needs": [{"kind": "accrual"}]}
    monkeypatch.setattr(D, "_judge_state_by_claim",
                        lambda: {"c": ("warming", None, None, 0, "")})
    _, blocked = D.split_overdue([h], "2026-08-27")
    _, why, _ = blocked[0]
    assert "まだ数えはじめたところ" in why


def test_データ待ちは手を渡す(monkeypatch):
    """**待っても出ない側**には、`refresh` の行がそのまま渡ること。"""
    h = {"claim": "c", "deadline": "2026-08-27",
         "needs": [{"kind": "after", "on_date": "2026-08-27", "at_time_jst": "22:00"}]}
    monkeypatch.setattr(
        D, "_judge_state_by_claim",
        lambda: {"c": ("warming", None, None, 0, "`python scripts/snapshot.py` を1回")})
    _, blocked = D.split_overdue([h], "2026-08-27")
    _, why, todo = blocked[0]
    assert "要るデータが在りません" in why
    assert "snapshot" in todo
