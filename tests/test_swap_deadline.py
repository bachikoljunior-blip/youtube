"""**枠が戻るのが公開より後なら、「戻ってから撃て」は嘘です。**

## なぜ要るか（2026-09-01 22:0x に踏んだ）

この判定は `next_slot.quota_note()` が**既に持っていました** ——
「戻るのは MM/DD HH:MM JST ＝ **公開に間に合いません**」。
**呼ばれる所が `pending_thumbnail()` の枝の中だけ**で、
**サムネイルが既に載っている本では一度も走りません。**

実際に走っていたのは `swap_cost_lines()` のほうで、あちらは
**同じ `window_end()` を読みながら、公開時刻と比べていません**でした。
出ていたのは:

    **枠が戻ってから、外す → 入れるの順で撃つこと**

実測 —— 次の枠は `a63FzIUV2wI`（**09/02 13:00 JST 公開**）、
枠が戻るのは **09/02 16:00 JST**。**3時間 遅い。**
**次の回に、もう出来ないことを指示していました。**
正しい文は、同じ出力の 12行 上に在ります。

これはこの repo でいちばん多い壊れ方（**言っている所と、している所が別**）の、
`status.print_quota_ledger` と同じ形です ——
**関数は在る・検査も通る・実際に走る枝から呼ばれていない。**

## 構造のほう（`window_reaches` の註に実測）

枠の頭は太平洋時間の0時 ＝ **JST 16:00**。実測（`data/api_calls.jsonl`）では
戻ってから **1.1時間／3.1時間** で焼き切れています ＝ 書ける帯は 16:00〜19:00。
`config/channel.yaml` の `publish_hour_jst` は 09-01 に **19 → 9** へ移ったので、
**そこに置かれた本は、前日の3時間の窓でしか差し替えられません。**

## 覆る条件

- `reschedule` が `videos.update` を使わない道を持ったら、この検査ごと要りません
- **門ではありません。** 撃つ側が判断します（止めると、枠の在る窓まで止まる）
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import next_slot  # noqa: E402

JST = timezone(timedelta(hours=9))
#: 枠が戻る時刻（＝ 太平洋時間の0時 ＝ 09/02 16:00 JST）
BACK = datetime(2026, 9, 2, 7, 0, tzinfo=timezone.utc)


def _burnt(monkeypatch) -> None:
    """**枠が尽きた窓**に固定する（`window_end` は上の `BACK`）。"""
    from src import quota_ledger, upload_cap

    monkeypatch.setattr(quota_ledger, "spent",
                        lambda *a, **k: {"data": quota_ledger.DAY_UNITS + 1})
    monkeypatch.setattr(upload_cap, "window_end", lambda *a, **k: BACK)


def test_枠が戻る前に出る本は_間に合わないと言う(monkeypatch) -> None:
    """**実測の姿**: 公開 09/02 13:00 JST ／ 枠が戻るのは 09/02 16:00 JST。"""
    _burnt(monkeypatch)
    pub = datetime(2026, 9, 2, 13, 0, tzinfo=JST)
    got = "\n".join(next_slot.swap_cost_lines(publish_at=pub))
    assert "間に合いません" in got, (
        "**戻る時刻が公開より後なのに、「戻ってから撃て」と言っています。**\n"
        "同じ判定文が `next_slot.quota_note()` に在ります（そちらは"
        "`pending_thumbnail()` の枝の中だけで呼ばれます）:\n  " + got)
    assert "枠が戻ってから" not in got, (
        "**もう出来ないことを、次の回に指示しています**:\n  " + got)
    assert "いまの中身のまま出ます" in got, (
        "この本がどうなるかを言っていない（読む側は「まだ手がある」と読みます）")


def test_間に合わない回は_次の枠へ行けと言う(monkeypatch) -> None:
    """**行き先の無い [!] を出さないこと。** この回の `improve` は次の本へ。"""
    _burnt(monkeypatch)
    pub = datetime(2026, 9, 2, 13, 0, tzinfo=JST)
    got = "\n".join(next_slot.swap_cost_lines(publish_at=pub))
    assert "次の枠の本へ" in got, "打つ手を名指ししていない"
    assert "publish_hour_jst" in got, (
        "**なぜ間に合わなかったか**（枠の頭 16:00 より前の時刻に置いてある）を"
        "言っていない —— 言わないと、次の本でも同じ所に置きます")


def test_戻ってから出る本は_今までどおりの案内(monkeypatch) -> None:
    """**緩める向きに外さないこと。** 間に合う本には、元の2手を出す。"""
    _burnt(monkeypatch)
    pub = datetime(2026, 9, 2, 22, 0, tzinfo=JST)      # 戻る 16:00 の 6時間 後
    got = "\n".join(next_slot.swap_cost_lines(publish_at=pub))
    assert "枠が戻ってから" in got
    assert "間に合いません" not in got


def test_公開時刻を渡されない回は_今までどおり(monkeypatch) -> None:
    """**推測で言わないこと。** 呼ぶ側が公開時刻を知らない回は元のまま。"""
    _burnt(monkeypatch)
    got = "\n".join(next_slot.swap_cost_lines())
    assert "枠が戻ってから" in got
    assert "間に合いません" not in got


def test_window_reaches_は帳面が読めない回に何も言わない(monkeypatch) -> None:
    """`None` ＝ 分からない。**`False`（もう直せません）と混ぜないこと。**"""
    from src import upload_cap

    def boom(*a, **k):
        raise RuntimeError("窓が読めない（テスト）")

    monkeypatch.setattr(upload_cap, "window_end", boom)
    assert next_slot.window_reaches(datetime(2026, 9, 2, 13, 0, tzinfo=JST)) is None


def test_lines_が公開時刻を渡している() -> None:
    """**この検査が本体です** —— 判定を持っていても、渡さなければ走りません。

    `quota_note()` がまさにそれで、**`pending_thumbnail()` の枝の中だけ**に
    置かれ、サムネイルの載った本では一度も走りませんでした。
    """
    src = (ROOT / "src" / "next_slot.py").read_text(encoding="utf-8")
    assert "swap_cost_lines(t, publish_at=" in src, (
        "`lines()` が `swap_cost_lines()` へ公開時刻を渡していません ——"
        "渡さないと、間に合うかどうかの判定は**一度も走りません**")
