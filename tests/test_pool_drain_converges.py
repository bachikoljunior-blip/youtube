"""**掃きが「控えは残っているのに、もう外れている」で止まらないこと。**

## なぜ要るか（2026-09-02 16:0x・自動の掃きの1回目で、続けて2つ踏んだ）

門（`scripts/ahead_gate.py`）は**控えの本数**で鳴ります。だから
**控えが実物より多いままだと、直しようのない数で鳴り続けます。**
その形が2つ在りました。

### (1) **「もうその値です」を、控えを直さずに飛ばしていた**

`reschedule._update()` が `False` を返す道は2つあります（`src/ledger_truth.py`）:

    "same"       **実物はもうその値でした**（`videos.list` がそう言った）
    "move_hold"  この窓でもう `MOVE_CAP` 回 動かした ＝ **YouTube を1文字も変えていない**

`pool_drain` は返り値しか見ていなかったので、**両方を同じ枝**で
「撃っていないので控えも直しません」と飛ばしていました。
実測: 控えは先の日付の予約を **107本**、口は **41本**。
差の 66本 は**もう外れている**本で、**控えは永久に 0本 になりません。**

**`"same"` は `videos.list` の返りそのもの**なので、推測ではありません。
そこだけ控えを直します。

### (2) **消えた本 1本 で、残り全部の掃きが落ちていた**

`_update()` は「動画が見つかりません」を**裸の `SystemExit`** で投げており、
掃きのループはそれを「この窓ではもう書けません」（日枠・取り置き）と読んで
**止まります**。実測:

    [pool] **この窓ではもう書けません**（97本 外したところ）:
           動画が見つかりません: iicEp33dILY

**枠はまだ 4,000単位 以上 残っていました。**
いまは `reschedule.VideoGone`（`SystemExit` の子）で、掃きだけが見分けて飛ばします。
**子にしてあるので、受けていない呼び側の振る舞いは変わりません。**

## 覆る条件

`_update()` の `report` が返す `reason` を増やしたら、ここも一緒に見ること
（**控えを直してよいのは、実物を読めた枝だけ**）。
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import pool_drain  # noqa: E402
import reschedule  # noqa: E402

JST = timezone(timedelta(hours=9))


def _row(days: int, vid: str) -> dict:
    at = datetime.now(timezone.utc) + timedelta(days=days)
    return {"id": vid, "title": "t", "at": at, "topic": ""}


class _Recorder:
    """`dupes.retime` の呼ばれ方を控える。"""

    def __init__(self):
        self.calls: list[tuple[str, object]] = []

    def __call__(self, vid, at):
        self.calls.append((vid, at))
        return True


# ---------------------------------------------------------------- VideoGone
def test_VideoGone_は_SystemExit_の子であること():
    """**子にしてあるので、受けていない呼び側の振る舞いは変わりません。**"""
    assert issubclass(reschedule.VideoGone, SystemExit)
    assert "vid1" in str(reschedule.VideoGone("vid1"))


def test_消えた本で掃きが止まらないこと(monkeypatch):
    """**注入する故障**: 3本のうち真ん中が `VideoGone`。残りが外れること。"""
    rec = _Recorder()
    monkeypatch.setattr(pool_drain.dupes, "retime", rec)
    monkeypatch.setattr(pool_drain.uploader, "_service", lambda: object())
    monkeypatch.setattr(pool_drain.uploader, "base_status", lambda *a, **k: {})
    monkeypatch.setattr(pool_drain, "thumbnail_first", lambda *a, **k: "")
    monkeypatch.setattr(pool_drain, "swap_reserve", lambda *a, **k: None)
    rows = [_row(3, "a"), _row(4, "gone"), _row(5, "c")]
    monkeypatch.setattr(pool_drain, "pool", lambda *a, **k: rows)

    def fake_update(svc, vid, at, fallback_status=None, report=None):
        if vid == "gone":
            raise reschedule.VideoGone(vid)
        if report is not None:
            report.update({"wrote": True, "reason": "wrote"})
        return True

    monkeypatch.setattr(pool_drain.reschedule, "_update", fake_update)
    assert pool_drain.main(["--apply", "--keep", "0", "--no-inbox"]) == 0
    # **3本とも控えから落ちること**（消えた本も、公開されないので幻）
    assert sorted(v for v, _ in rec.calls) == ["a", "c", "gone"]
    assert all(at is None for _, at in rec.calls)


# ---------------------------------------------------------------- same / move_hold
def test_実物でもう外れていた本は_控えを直す(monkeypatch):
    """**注入する故障**: 実物はもう予約なし（`"same"`）。控えだけが古い。"""
    rec = _Recorder()
    monkeypatch.setattr(pool_drain.dupes, "retime", rec)
    monkeypatch.setattr(pool_drain.uploader, "_service", lambda: object())
    monkeypatch.setattr(pool_drain.uploader, "base_status", lambda *a, **k: {})
    monkeypatch.setattr(pool_drain, "thumbnail_first", lambda *a, **k: "")
    monkeypatch.setattr(pool_drain, "swap_reserve", lambda *a, **k: None)
    monkeypatch.setattr(pool_drain, "pool", lambda *a, **k: [_row(3, "a")])

    def fake_update(svc, vid, at, fallback_status=None, report=None):
        if report is not None:
            report.update({"wrote": False, "reason": "same"})
        return False

    monkeypatch.setattr(pool_drain.reschedule, "_update", fake_update)
    assert pool_drain.main(["--apply", "--keep", "0", "--no-inbox"]) == 0
    assert rec.calls == [("a", None)]


def test_撃っていない本は_控えを触らないこと(monkeypatch):
    """**`move_hold` は YouTube を1文字も変えていません。**

    ここで控えを直すと、**実物は予約のまま公開されます** ——
    2026-09-01 にオーナーが画面で踏んだ穴そのもの（`src/ledger_truth.py`）。
    """
    rec = _Recorder()
    monkeypatch.setattr(pool_drain.dupes, "retime", rec)
    monkeypatch.setattr(pool_drain.uploader, "_service", lambda: object())
    monkeypatch.setattr(pool_drain.uploader, "base_status", lambda *a, **k: {})
    monkeypatch.setattr(pool_drain, "thumbnail_first", lambda *a, **k: "")
    monkeypatch.setattr(pool_drain, "swap_reserve", lambda *a, **k: None)
    monkeypatch.setattr(pool_drain, "pool", lambda *a, **k: [_row(3, "a")])

    def fake_update(svc, vid, at, fallback_status=None, report=None):
        if report is not None:
            report.update({"wrote": False, "reason": "move_hold"})
        return False

    monkeypatch.setattr(pool_drain.reschedule, "_update", fake_update)
    pool_drain.main(["--apply", "--keep", "0", "--no-inbox"])
    assert rec.calls == []


def test_日枠の_SystemExit_では今までどおり止まること(monkeypatch):
    """**取り置きと日枠は、飛ばさずに止まること**（`VideoGone` と混ぜない）。"""
    rec = _Recorder()
    monkeypatch.setattr(pool_drain.dupes, "retime", rec)
    monkeypatch.setattr(pool_drain.uploader, "_service", lambda: object())
    monkeypatch.setattr(pool_drain.uploader, "base_status", lambda *a, **k: {})
    monkeypatch.setattr(pool_drain, "thumbnail_first", lambda *a, **k: "")
    monkeypatch.setattr(pool_drain, "swap_reserve", lambda *a, **k: None)
    monkeypatch.setattr(pool_drain, "pool", lambda *a, **k: [_row(3, "a"), _row(4, "b")])

    def fake_update(svc, vid, at, fallback_status=None, report=None):
        raise SystemExit("この窓の単位は、計測のぶんを残して止めています")

    monkeypatch.setattr(pool_drain.reschedule, "_update", fake_update)
    assert pool_drain.main(["--apply", "--keep", "0", "--no-inbox"]) == 1
    assert rec.calls == []


# ---------------------------------------------------------------- _update の report
def test_report_は_同じ値の枝で_same_を返すこと():
    """**返り値だけでは、`False` の2つの意味が区別できません。**"""
    text = (ROOT / "scripts" / "reschedule.py").read_text(encoding="utf-8")
    assert '"reason": "same"' in text
    assert '"reason": "move_hold"' in text


@pytest.mark.parametrize("word", ["same", "move_hold"])
def test_掃きが_report_を読んでいること(word):
    text = (ROOT / "scripts" / "pool_drain.py").read_text(encoding="utf-8")
    assert "report=rep" in text
    assert word in text
