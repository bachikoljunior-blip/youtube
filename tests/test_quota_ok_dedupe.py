"""**帳面の二重書きが、枠の実測を膨らませないこと**（2026-08-28 に実測して足した）。

## この検査が守っているもの

`data/day_quota.jsonl` の「通った」行は、`upload_cap.measured_budget()` が
**その日 API が確かに渡した単位**として読みます。だから**同じ呼び出しが2行
載ると、枠がその分 大きく見えます。**

実測（窓 08/27 07:00Z 〜、本物の帳面）:

    `videos.update` の ok 行     **273行**
    うち (時刻, 本) が同じ行     **100行 ＝ 5,000単位ぶんの幻**
    → 実際に通ったのは          **173回 ＝ 8,650単位**

`scripts/batch_build.py` の長尺の詰め直しが、`reschedule._update`
（**通ったときだけ自分で1行 書く**）を呼んだ**あとにもう1行**書いていました。
2026-08-27 の回はこの膨らんだ数を読んで **「日枠は既定の 10,000 ではない」**
と結論し、コードの註に残しています。**二重に数えた側の誤りです。**

## なぜ「数える側」で潰すか

`note_quota_ok` を呼ぶ場所はいま3つで、**入口は増えます。**
呼び出し側だけ直すと、4つ目ができたときに同じ穴が開きます
（この repo が通算11回 踏んでいる「片方だけ」の形）。

## 覆る条件

**同じ秒に、同じ本へ `videos.update` を2回 撃つのが正しくなったとき。**
いまは意味がありません —— 2回目は1回目と同じ値を書きます。そして
書き込みの入口はどれも 1.0〜1.2秒 待つので、**同じ秒の2行は二重書きだけ**です。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import upload_cap                                     # noqa: E402


def _row(at: str, detail: str, ok: bool = True) -> dict:
    return {"at": at, "detail": detail, "ok": ok} if ok else {"at": at, "detail": detail}


def test_同じ秒の同じ呼び出しは1回に数える():
    rows = [_row("2026-08-27T07:11:30+00:00", "videos.update abc"),
            _row("2026-08-27T07:11:30+00:00", "videos.update abc")]
    assert len(upload_cap.dedupe_ok(rows)) == 1


def test_別の秒なら2回とも数える():
    """**撃ち直しそのものは消さないこと。** 消すのは同じ秒の写しだけです。"""
    rows = [_row("2026-08-27T07:11:30+00:00", "videos.update abc"),
            _row("2026-08-27T07:11:32+00:00", "videos.update abc")]
    assert len(upload_cap.dedupe_ok(rows)) == 2


def test_同じ秒でも別の本なら2回とも数える():
    rows = [_row("2026-08-27T07:11:30+00:00", "videos.update abc"),
            _row("2026-08-27T07:11:30+00:00", "videos.update xyz")]
    assert len(upload_cap.dedupe_ok(rows)) == 2


def test_batch_buildは_update_のあとに帳面へ書かない():
    """**入口の側の回帰。** `reschedule._update` が通ったときだけ1行 書きます ——
    その呼び出し側がもう1行 書くと、同じ秒に2行 載ります。
    """
    src = (Path(__file__).resolve().parents[1] / "scripts" / "batch_build.py"
           ).read_text(encoding="utf-8")
    tail = src.split("def _rescue_dead_slots")[0].split("dupes.retime")[-1]
    # **註は数えないこと** —— 「呼ばない理由」がその場に書いてあります。
    code = "\n".join(ln for ln in tail.splitlines()
                     if not ln.lstrip().startswith("#"))
    assert "note_quota_ok" not in code, (
        "`batch_build` が `reschedule._update` のあとに `note_quota_ok` を"
        "呼んでいます。**`_update` が自分で書きます。** 二重に載ると"
        "`measured_budget()` の枠が実測より大きく出ます")
