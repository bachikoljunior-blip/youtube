"""`scripts/owner_words.py` の見張り（オーナーの「分かりにくい」の連）。

**陽性対照で測ってあります** —— どの検査も、規則を 1つ 外すと落ちます
（§5 教訓の形 3つ目: 「在るか」で見る形は、畳んでも通ってしまう）。

**きょうの状態を不変条件に書かないこと**（§5 教訓の形 6つ目）——
実物の `data/inbox.jsonl` に当てる検査は「連が何日か」を書かず、
**門の定数から引く**か、**その場で作った台帳**で測ります。
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

ow = importlib.import_module("scripts.owner_words")


def _ledger(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "inbox.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    return p


def _row(at: str, rid: str, source: str = "owner", text: str = "x") -> dict:
    return {"at": at, "id": rid, "source": source, "text": text}


def test_オーナー以外の行は数えない(tmp_path: Path) -> None:
    """親の申し送りや道具の行が混ざっても、数えるのは `source == "owner"` だけ。"""
    rows = [
        _row("2026-09-13T10:00:00+09:00", "dd918e3f", source="parent"),
        _row("2026-09-13T11:00:00+09:00", "zzzz0001"),
    ]
    got = ow.owner_rows(_ledger(tmp_path, rows))
    assert [r["id"] for r in got] == ["zzzz0001"]
    # 陽性対照: 札の在る id でも、オーナーの行でなければ連に入らないこと
    assert ow.run(days_back=999, path=_ledger(tmp_path, rows))["run"] == 0


def test_沈黙の日は連を伸ばしも切りもしない(tmp_path: Path) -> None:
    """09/10・09/13 に族の言葉・その間はオーナーが 1言も言っていない ＝ 連は 2日。"""
    rows = [
        _row("2026-09-10T12:00:00+09:00", "552fadf1"),
        _row("2026-09-13T12:00:00+09:00", "2e87f87e"),
    ]
    res = ow.run(days_back=999, path=_ledger(tmp_path, rows))
    assert res["run"] == 2
    assert res["silent_in_run"] == 2  # 09/11・09/12 は沈黙


def test_言った日に族が無ければ連が切れる_陽性対照(tmp_path: Path) -> None:
    rows = [
        _row("2026-09-10T12:00:00+09:00", "552fadf1"),
        _row("2026-09-11T12:00:00+09:00", "f3edb61f"),
        _row("2026-09-12T12:00:00+09:00", "b8dab27b"),
    ]
    assert ow.run(days_back=999, path=_ledger(tmp_path, rows))["run"] == 3
    # まん中の日を「族でない言葉」に差し替えると、連は 1日 に落ちること
    rows[1] = _row("2026-09-11T12:00:00+09:00", "notaclarityid")
    assert ow.run(days_back=999, path=_ledger(tmp_path, rows))["run"] == 1


def test_門は定数から引く(tmp_path: Path) -> None:
    rows = [
        _row(f"2026-09-{9 + i:02d}T12:00:00+09:00", rid)
        for i, rid in enumerate(list(ow.CLARITY_IDS)[: ow.GATE])
    ]
    res = ow.run(days_back=999, path=_ledger(tmp_path, rows))
    assert res["run"] == ow.GATE and res["drawn"] is True
    # 1日 減らすと引かれないこと（陽性対照）
    res2 = ow.run(days_back=999, path=_ledger(tmp_path, rows[1:]))
    assert res2["run"] == ow.GATE - 1 and res2["drawn"] is False


def test_同じ日に族が2件でも連は1日(tmp_path: Path) -> None:
    """09/10 は 2件（`552fadf1`・`52f141fa`）—— 日で数えること。"""
    rows = [
        _row("2026-09-10T12:38:00+09:00", "552fadf1"),
        _row("2026-09-10T12:40:00+09:00", "52f141fa"),
    ]
    assert ow.run(days_back=999, path=_ledger(tmp_path, rows))["run"] == 1


def test_札の無い新しい言葉は必ず印字される(tmp_path: Path) -> None:
    """新しい言葉が黙って連を古くしないこと（§5 教訓の形 7つ目・17つ目）。"""
    rows = [
        _row("2026-09-13T12:00:00+09:00", "2e87f87e"),
        _row("2026-09-13T20:00:00+09:00", "newword1", text="まだ札の無い言葉"),
    ]
    res = ow.run(days_back=999, path=_ledger(tmp_path, rows))
    assert [r["id"] for r in res["unclassified"]] == ["newword1"]
    assert "newword1" in ow.line(res)


def test_族の言葉は全部_受け取り帳に在る() -> None:
    """`CLARITY_IDS` の id が実物の台帳から消えたら、この連は空を数えている。"""
    have = {r.get("id") for r in ow.owner_rows()}
    missing = [i for i in ow.CLARITY_IDS if i not in have]
    assert missing == [], f"受け取り帳に無い id: {missing}"
    assert ow.LOOP_ID in have


def test_印字は判定しないと言う() -> None:
    """optimizer は数を並べるまで（METHOD §5）—— 印字がそれを言い続けること。"""
    out = ow.line()
    assert "この道具は判定しません" in out
    assert "`hourly` とオーナー" in out
