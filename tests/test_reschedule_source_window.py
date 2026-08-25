"""**測定の窓は「行き先」だけでなく「元の日」でも守る。**

## なぜ要るか（2026-08-26。**実害が1回、既に出ています**）

`scripts/reschedule.py` は 4つの口から予約を動かします。
窓（`src.measure_window`）を見ていたのは、そのうち3つ半でした:

    --spread      置き先からも**対象からも**外す      … 見ている
    --compact     置き先からも**対象からも**外す      … 見ている
    --move        **行き先だけ**                      … ← 元の日が素通り
    --unschedule  **どちらも見ていない**               … ← 素通り

**壊れたのは元の側です。** 2026-08-24、`--spread` が 08/27 を
「14本 ＝ 上限超え」と読んで4本を後ろへ送り、そのあと別の回がさらに送って、
**窓に残ったのは1本だけ**でした（`src/measure_window.py` の 08-27 の `why`）。
`--spread` はそのとき直りましたが、**1本ずつ抜く道は開いたまま**です。

そして 2026-08-26 のこの回は、**まさにその道を通ろうとしています** ——
「判定に要る本を前へ、要らない本を後ろへ」の入れ替えは `--move` の連打で、
置き先を窓の外にしても、**元が窓の中なら測定は壊れます。**

## この検査が見ているもの

**呼び出しが在るか**ではなく、**窓の日の本を動かそうとしたら止まるか**です。
口を新しく足した回も、`_update()` の手前で止まらなければここに落ちます。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import scripts.reschedule as R  # noqa: E402
from src import measure_window, uploader  # noqa: E402

WINDOW_DAY = "2026-08-27"
FREE_DAY = "2026-09-05"


@pytest.fixture()
def 窓が1日だけ立っている(monkeypatch):
    win = {"from": WINDOW_DAY, "to": WINDOW_DAY, "until": WINDOW_DAY,
           "label": "テスト", "why": "検査用の窓"}
    monkeypatch.setattr(measure_window, "find",
                        lambda d, today=None: win if d == WINDOW_DAY else None)

    def 撃たせない(*a, **k):  # pragma: no cover - 通ったら失敗させるため
        raise AssertionError("**API を呼びました。**窓の門より先へ進んでいます")

    monkeypatch.setattr(uploader, "_service", 撃たせない)
    return win


def test_窓の日から動かそうとしたら_APIの手前で止まる(窓が1日だけ立っている, monkeypatch):
    monkeypatch.setattr(R, "_current_day", lambda v: WINDOW_DAY)
    with pytest.raises(SystemExit) as e:
        R.main(["--move", "vidA", f"{FREE_DAY}T09:00"])
    assert WINDOW_DAY in str(e.value), (
        "止まったが、**元の日が窓だから**とは言っていません。"
        "理由が出ないと、止められた側は --force-window を付けて通します")


def test_窓の日の予約を外そうとしたら_APIの手前で止まる(窓が1日だけ立っている, monkeypatch):
    monkeypatch.setattr(R, "_current_day", lambda v: WINDOW_DAY)
    with pytest.raises(SystemExit):
        R.main(["--unschedule", "vidA"])


def test_窓の外の本は止めない(窓が1日だけ立っている, monkeypatch):
    """**止めるのは窓の日だけ。** 全部止めると投稿が止まります（`CLAUDE.md`）。"""
    monkeypatch.setattr(R, "_current_day", lambda v: FREE_DAY)
    with pytest.raises(AssertionError):     # 門を抜けて `_service()` まで行った
        R.main(["--move", "vidA", f"{FREE_DAY}T09:00"])


def test_控えに無い本は止めない(窓が1日だけ立っている, monkeypatch):
    """いまの日が読めない本まで止めると、**古い本を動かす道が消えます。**"""
    monkeypatch.setattr(R, "_current_day", lambda v: None)
    with pytest.raises(AssertionError):     # 門を抜けて `_service()` まで行った
        R.main(["--move", "vidA", f"{FREE_DAY}T09:00"])


def test_force_window_なら通る(窓が1日だけ立っている, monkeypatch):
    monkeypatch.setattr(R, "_current_day", lambda v: WINDOW_DAY)
    with pytest.raises(AssertionError):     # 門を抜けて `_service()` まで行った
        R.main(["--move", "vidA", f"{FREE_DAY}T09:00", "--force-window"])


def test_控えの畳み方を_この道具の中で持ち直していない():
    """`_current_day` は `ab_split.published()` に畳ませること。

    控えは足すだけの帳面で、**同じ `video_id` の行が動かすたびに増えます**。
    畳み方（後の行を採る・日は JST）を2か所で持つと、片方だけが直ります ——
    このリポジトリで7回踏んでいる形です。
    """
    src = (ROOT / "scripts" / "reschedule.py").read_text(encoding="utf-8")
    head = src.split("def _check_source_window", 1)[0]
    body = head.split("def _current_day", 1)[1]
    assert "published()" in body, (
        "`_current_day` が `ab_split.published()` を使っていません。"
        "控えの畳み方を、ここでもう一度書かないこと")
