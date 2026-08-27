"""**同じ本を、1つの窓で何度も動かさないこと**（2026-08-28 の最適化の回に足した）。

## なぜ要るか —— **`test_reschedule_noop.py` の関門が捕まえない側です**

08/27 10:22Z に入った関門は「**もうその値なら撃たない**」で、正しく効きます。
**ただし捕まえるのは、値が同じ回だけ。** 窓 08/27 の再撃ちを
`data/uploaded.jsonl` の `retimed_at` で割ると:

    2回以上 撃たれた本                      **29本**
      うち 毎回おなじ時刻へ（関門が捕まえる）    **14本**
      うち **違う時刻へ**（関門を素通りする）    **15本**

そして 15本 の散らばり方が、食い違いではなく**振動**です（中央値 **30日**）:

    lIli_5r0YSY   16:24 → 10/01     16:44 → 08/31
    SLeIwUJa36A   16:25 → 10/03     16:44 → 09/03
    pvN0_4zZleo   16:25 → 10/02     16:44 → 09/02

**1つの掃きが1か月 先へ置き、19分後の掃きが1か月 手前へ引き戻しています。**
書き込みを数えると、窓はこう割れます（`videos.update` は 50単位）:

    窓 08/26   65回 /  **2本** ＝ 1本あたり **32.5回**   → 捨てた **3,150単位**
    窓 08/27  173回 / **58本** ＝ 1本あたり  **2.98回**  → 捨てた **5,750単位**

**合わせて 8,900単位 ＝ ほぼ1日ぶんの枠。効くのはその本の最後の1回だけ**なので、
残りは定義上むだです。焼け切ると、その窓では `queue_lag --apply` の入れ替え
（14手・1,400単位 ＝ 判定日を合計 **9日** 手前に倒す手）が撃てません。

**覆る条件**は `src.upload_cap.MOVE_CAP` の註にあります
（要は「どちらの掃きが正しいか分かったら、掃きのほうを直すこと」）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from src import config, upload_cap  # noqa: E402

import reschedule  # noqa: E402


class _Call:
    def __init__(self, value):
        self._value = value

    def execute(self):
        return self._value


class _Videos:
    def __init__(self, status: dict) -> None:
        self._status = status
        self.updated: list[dict] = []

    def list(self, **kw):
        return _Call({"items": [{"status": dict(self._status)}]})

    def update(self, **kw):
        self.updated.append(kw)
        return _Call({})


class _Svc:
    def __init__(self, videos: _Videos) -> None:
        self._videos = videos

    def videos(self):
        return self._videos


SCHEDULED = {"privacyStatus": "private",
             "publishAt": "2026-08-28T11:00:00Z",
             "uploadStatus": "processed"}

#: **この窓の中の時刻**でなければ数えられません（`_in_window`）。
#: だから固定の日付ではなく、いま効いている窓の頭から作ります。
def _at(offset_s: int = 0) -> str:
    from datetime import timedelta
    return (upload_cap.window_start() + timedelta(seconds=60 + offset_s)) \
        .isoformat(timespec="seconds")


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    """**本物の帳面には触らないこと**（`tests/conftest.py` の冒頭）。"""
    monkeypatch.setattr(config, "ROOT", tmp_path)
    (tmp_path / "data").mkdir()
    path = tmp_path / "data" / "day_quota.jsonl"

    def write(rows: list[dict]) -> None:
        with path.open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    return write


def _shot(video_id: str, offset_s: int = 0) -> dict:
    return {"at": _at(offset_s), "ok": True,
            "detail": f"videos.update {video_id}"}


# ------------------------------------------------ 数えるほう

def test_この窓のその本の書き込みだけを数える(ledger, monkeypatch):
    ledger([_shot("vidA", 0), _shot("vidA", 10), _shot("vidB", 20),
            {"at": _at(30), "ok": True, "detail": "thumbnails.set vidA"}])

    assert upload_cap.moves_in_window("vidA") == 2, "別の呼び出しまで数えている"
    assert upload_cap.moves_in_window("vidB") == 1
    assert upload_cap.moves_in_window("vidC") == 0


def test_同じ秒の二重書きは1回と数える(ledger):
    """`dedupe_ok` に通していないと、**幻が「もう撃った」の側に出ます。**

    `batch_build` が `_update` の**あとにもう1行**書いていた形です
    （`upload_cap.dedupe_ok` の註。枠を 55% 高く見せていたのと同じ幻）。
    """
    ledger([_shot("vidA", 0), _shot("vidA", 0)])

    assert upload_cap.moves_in_window("vidA") == 1


def test_403の行は数えない(ledger):
    """`ok` の無い行は **403 そのもの**です（単位を使っていません）。"""
    ledger([{"at": _at(0), "detail": "videos.update vidA"},
            {"at": _at(10), "detail": "videos.update vidA"}])

    assert upload_cap.moves_in_window("vidA") == 0


# ------------------------------------------------ 止めるほう

def test_上限まではふつうに撃つ(ledger, monkeypatch):
    monkeypatch.delenv("YT_FORCE_UPDATE", raising=False)
    monkeypatch.delenv("YT_NO_MOVE_CAP", raising=False)
    ledger([_shot("vid1", 0)])                       # 1回目まで ＝ 上限の下
    videos = _Videos(SCHEDULED)

    assert reschedule._update(_Svc(videos), "vid1", "2026-08-29T10:00:00Z") is True
    assert len(videos.updated) == 1


def test_上限に届いたら撃たない(ledger, monkeypatch):
    """**時刻が違っても撃ちません。** ここが `test_reschedule_noop` との違いです。"""
    monkeypatch.delenv("YT_FORCE_UPDATE", raising=False)
    monkeypatch.delenv("YT_NO_MOVE_CAP", raising=False)
    ledger([_shot("vid1", 0), _shot("vid1", 10)])
    videos = _Videos(SCHEDULED)

    assert reschedule._update(_Svc(videos), "vid1", "2026-08-29T10:00:00Z") is False
    assert videos.updated == [], "3回目の置き直しに 50単位 撃っている"


def test_止めるのはその1本だけ(ledger, monkeypatch):
    """**窓ぜんぶを止める `reserve_hold` とは別物です。**

    `SystemExit` を投げると、1本が上限に届いただけで掃きが丸ごと死にます。
    """
    monkeypatch.delenv("YT_FORCE_UPDATE", raising=False)
    monkeypatch.delenv("YT_NO_MOVE_CAP", raising=False)
    ledger([_shot("vid1", 0), _shot("vid1", 10)])

    # 例外ではなく False（呼ぶ側は次の本へ進める）
    assert reschedule._update(_Svc(_Videos(SCHEDULED)), "vid1",
                              "2026-08-29T10:00:00Z") is False
    # 上限に届いていない本は、同じ掃きの中で撃てる
    videos = _Videos(SCHEDULED)
    assert reschedule._update(_Svc(videos), "vid2",
                              "2026-08-29T10:00:00Z") is True
    assert len(videos.updated) == 1


def test_逃げ道(ledger, monkeypatch):
    ledger([_shot("vid1", 0), _shot("vid1", 10)])
    monkeypatch.delenv("YT_FORCE_UPDATE", raising=False)
    monkeypatch.setenv("YT_NO_MOVE_CAP", "1")
    videos = _Videos(SCHEDULED)

    assert reschedule._update(_Svc(videos), "vid1", "2026-08-29T10:00:00Z") is True
    assert len(videos.updated) == 1


def test_投稿は止めないこと():
    """**この関門を `videos.insert` の側に置かないこと。**

    `docs/GOAL.md`「投稿が途切れるのが最大の損失」に真っ向から反します。
    `move_hold` を呼ぶのは `reschedule._update`（＝ `videos.update`）だけ。
    """
    from tests.conftest import source_of

    src = source_of(reschedule._update)
    assert "move_hold" in src, "関門が外れています"

    root = Path(__file__).resolve().parent.parent
    callers = [p for p in list(root.glob("src/*.py")) + list(root.glob("scripts/*.py"))
               if "move_hold(" in p.read_text(encoding="utf-8")
               and p.name not in ("upload_cap.py", "reschedule.py")]
    assert callers == [], f"`videos.insert` の側に漏れています: {callers}"
