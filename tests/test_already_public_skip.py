"""**もう公開済みの本を、予約へ戻そうとしないこと**（2026-08-28 に実測で踏んだ）。

## なぜ要るか（**幻が1行あるだけで、34日の前倒しが 0/16 になっていました**）

`scripts/queue_lag.py` は「もう予約に在る本を入れ替えるだけで何日 早まるか」を
毎回 印字します。2026-08-28 の実測は **合計 34日**
（`opening_motion` だけで 判定 10/07 → 09/07 ＝ **30日**）。
**この数は 08/28 未明から3周 続けて印字され、1度も当たっていませんでした。**

前の回（08/28 20:0x）は理由を「**この役の口からは `--apply` が通らない**」と
書きました。この回に撃ち直すと、**それは理由の半分**でした:

    `queue_lag.py --apply`                      → 分類器が拒否（**再現した**）
    `reschedule.py --move <1手目>`（同じ手）      → **拒否されない。**
                                                   YouTube が **400 invalidPublishAt**

`videos.list` で実物を読むと:

    `cJw79xThyTY`  控え `data/uploaded.jsonl` … `at` = **2026-10-04**
                   YouTube 実物 ………………… **public**・
                                              `publishedAt` = **2026-08-28T11:00:08Z**

きょうだいの回が動かした本で、**控えは git 越しなので merge まで入りません。**
そして `apply_moves` は**最初の失敗で全部を止める**作りでした ——
`--plan` の**1手目がこの本**だったので、**16手が 0手**になります。

## この検査が守っているもの

1. 公開済みと分かった時点で `videos.update` を**撃たない**（50単位を捨てない）
2. **控えを実物へ直す** —— 直さないと `queue_lag` ・`day_cap` ・`live_ring` ・
   群の床が、幻の枠を数え続けます
3. `apply_moves` は**その組だけ飛ばして、残りを当てる**
4. **飛ばすのは組ごと**（早める本が飛んだ組で、後ろへ送る側だけ撃たない ——
   それは「1本 遠のくだけ」の純損）

**覆る条件**: YouTube が公開済みの本にも `publishAt` を立てさせるようになったら、
1 は要りません（2〜4 は控えの話なので残ります）。
`test_公開済みなら撃たない` が落ちて、そう教えます。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import reschedule  # noqa: E402
import queue_lag  # noqa: E402
#: **`queue_lag.apply_moves` は `from scripts import reschedule` で取ります。**
#: `sys.path` に `scripts/` を足して `import reschedule` した物とは**別の
#: モジュール実体**なので、差し替えるならこちら側です（ここを間違えると、
#: 検査は本物の `main()` を呼んで YouTube を触りにいきます）。
from scripts import reschedule as _sched  # noqa: E402


class _Call:
    def __init__(self, value):
        self._value = value

    def execute(self):
        return self._value


class _Videos:
    def __init__(self, status: dict, snippet: dict | None = None) -> None:
        self._status = status
        self._snippet = snippet
        self.updated: list[dict] = []
        self.reads = 0

    def list(self, **kw):
        self.reads += 1
        self.last_parts = kw.get("part", "")
        item = {"status": dict(self._status)}
        if self._snippet is not None:
            item["snippet"] = dict(self._snippet)
        return _Call({"items": [item]})

    def update(self, **kw):
        self.updated.append(kw)
        return _Call({})


class _Svc:
    def __init__(self, videos: _Videos) -> None:
        self._videos = videos

    def videos(self):
        return self._videos


PUBLIC = {"privacyStatus": "public", "uploadStatus": "processed",
          "license": "youtube"}
SNIPPET = {"publishedAt": "2026-08-28T11:00:08Z"}


# ------------------------------------------------ 1・2: 関門そのもの

def test_公開済みなら撃たない(monkeypatch):
    """**50単位を捨てない。** 400 を買っても何も直りません。"""
    monkeypatch.delenv("YT_FORCE_UPDATE", raising=False)
    monkeypatch.setattr(reschedule.dupes, "retime", lambda *a, **k: True)
    videos = _Videos(PUBLIC, SNIPPET)

    with pytest.raises(reschedule.AlreadyPublic) as got:
        reschedule._update(_Svc(videos), "cJw79xThyTY", "2026-08-29T13:30:00Z")

    assert videos.updated == [], "公開済みなのに videos.update を撃っている"
    assert videos.reads == 1, "現状の読み（1単位）は要る。ここは削らないこと"
    assert got.value.video_id == "cJw79xThyTY"
    assert got.value.published_at == "2026-08-28T11:00:08Z"


def test_控えを実物へ直す(monkeypatch):
    """**直さないと、幻の予約が全部の道具に残ります**（ここが本体）。"""
    monkeypatch.delenv("YT_FORCE_UPDATE", raising=False)
    seen: list[tuple] = []
    monkeypatch.setattr(reschedule.dupes, "retime",
                        lambda vid, at: seen.append((vid, at)) or True)
    videos = _Videos(PUBLIC, SNIPPET)

    with pytest.raises(reschedule.AlreadyPublic):
        reschedule._update(_Svc(videos), "cJw79xThyTY", "2026-08-29T13:30:00Z")

    assert seen == [("cJw79xThyTY", "2026-08-28T11:00:08Z")], (
        "控えを実物の publishedAt へ書き戻していない")


def test_snippet_も読んでいること(monkeypatch):
    """`publishedAt` は `snippet` にしかありません。**単位は増えません**
    （`videos.list` は part の数によらず 1単位）。"""
    monkeypatch.delenv("YT_FORCE_UPDATE", raising=False)
    monkeypatch.setattr(reschedule.dupes, "retime", lambda *a, **k: True)
    videos = _Videos(PUBLIC, SNIPPET)

    with pytest.raises(reschedule.AlreadyPublic):
        reschedule._update(_Svc(videos), "v", "2026-08-29T13:30:00Z")

    assert "snippet" in videos.last_parts
    assert "status" in videos.last_parts


# ------------------------------------------------ 黙らせただけにしない

def test_予約中の本は今までどおり動く(monkeypatch):
    """**この関門が、ふつうの入れ替えを止めていないこと。**"""
    monkeypatch.delenv("YT_FORCE_UPDATE", raising=False)
    videos = _Videos({"privacyStatus": "private",
                      "publishAt": "2026-10-04T00:00:00Z",
                      "uploadStatus": "processed"}, SNIPPET)

    wrote = reschedule._update(_Svc(videos), "v", "2026-08-29T13:30:00Z")

    assert wrote is True
    assert len(videos.updated) == 1


def test_予約を外す回は公開済みでも通る(monkeypatch):
    """`publish_at=None`（`--unschedule`）は、公開済みの本にこそ効きます。
    **ここを塞ぐと、公開してしまった本を private へ戻す道が消えます。**"""
    monkeypatch.delenv("YT_FORCE_UPDATE", raising=False)
    videos = _Videos(PUBLIC, SNIPPET)

    wrote = reschedule._update(_Svc(videos), "v", None)

    assert wrote is True
    assert len(videos.updated) == 1


def test_現状を読めなかった回は今までどおり(monkeypatch):
    """`fallback_status` で代えた回は**実物を知りません。**
    知らないことを根拠に止めないこと。"""
    monkeypatch.delenv("YT_FORCE_UPDATE", raising=False)

    class _Unreadable(_Videos):
        def list(self, **kw):
            raise RuntimeError("読めません")

    videos = _Unreadable(PUBLIC, SNIPPET)
    wrote = reschedule._update(
        _Svc(videos), "v", "2026-08-29T13:30:00Z",
        fallback_status={"privacyStatus": "public"})

    assert wrote is True, "読めなかった回まで止めている"


# ------------------------------------------------ 3・4: 止めずに飛ばす

class _Plan:
    """`apply_moves` が使うのは `moves()` だけです。"""

    def __init__(self, moves):
        self._moves = moves

    def moves(self):
        return list(self._moves)


def _fake_main(calls, public: set[str]):
    def main(argv):
        vid, when = argv[1], argv[2]
        calls.append((vid, when))
        if vid in public:
            return reschedule.RC_ALREADY_PUBLIC
        return 0
    return main


def test_公開済みの1手目で全部を止めない(monkeypatch):
    """**実測 2026-08-28: 1手目がこれで、16手が 0手になっていました。**"""
    calls: list[tuple] = []
    monkeypatch.setattr(_sched, "main", _fake_main(calls, {"A"}))

    rc = queue_lag.apply_moves(_Plan([("A", "t1"), ("B", "t2"),
                                      ("C", "t3"), ("D", "t4")]))

    assert rc == 0
    assert [c[0] for c in calls] == ["A", "C", "D"], (
        "1手目で止まったか、飛ばした組の後半まで撃っている")


def test_飛ばすのは組ごと(monkeypatch):
    """早める側が飛んだのに後ろへ送る側だけ撃つと、**1本 遠のくだけの純損**です。"""
    calls: list[tuple] = []
    monkeypatch.setattr(_sched, "main", _fake_main(calls, {"A"}))

    queue_lag.apply_moves(_Plan([("A", "t1"), ("B", "t2")]))

    assert "B" not in [c[0] for c in calls], (
        "早める本が公開済みなのに、後ろへ送る本だけを動かしている")


def test_後半だけ公開済みなら前半は残す(monkeypatch):
    """早めた側は当たっています。**戻す理由はありません。**"""
    calls: list[tuple] = []
    monkeypatch.setattr(_sched, "main", _fake_main(calls, {"B"}))

    rc = queue_lag.apply_moves(_Plan([("A", "t1"), ("B", "t2"),
                                      ("C", "t3"), ("D", "t4")]))

    assert rc == 0
    assert [c[0] for c in calls] == ["A", "B", "C", "D"]


def test_本物の失敗では今までどおり止まる(monkeypatch):
    """**黙らせただけにしないこと。** 枠切れや権限は、飛ばさず止めます。"""
    calls: list[tuple] = []

    def main(argv):
        calls.append(argv[1])
        if argv[1] == "B":
            raise SystemExit("枠が尽きました")
        return 0

    monkeypatch.setattr(_sched, "main", main)

    rc = queue_lag.apply_moves(_Plan([("A", "t1"), ("B", "t2"),
                                      ("C", "t3"), ("D", "t4")]))

    assert rc == 1
    assert calls == ["A", "B"], "止まるべき所で先へ進んでいる"


# ------------------------------------------------ 帳面は「当たった数」を書くこと

def test_当たった数を呼ぶ側から読める(monkeypatch):
    """`_note_apply` は長らく **`len(plan.swaps) * 2`（＝予定の数）**を
    書いていました。実測（`data/queue_lag.jsonl`・08/27 の4行）は
    **moves 28 / 24 / 20 / 20** と満額で、**`opening_motion` の判定日は
    10/07 のまま**です。**止まったことが帳面に1文字も残りません。**"""
    calls: list[tuple] = []
    monkeypatch.setattr(_sched, "main", _fake_main(calls, {"C"}))
    plan = _Plan([("A", "t1"), ("B", "t2"), ("C", "t3"), ("D", "t4")])

    queue_lag.apply_moves(plan)

    assert plan.applied == 2, "当たったのは A・B の2手だけ"
    assert plan.skipped_public == ["C"]


def test_止まった回も当たった数を残す(monkeypatch):
    """**途中で止まった回こそ残すこと** —— 次の回が「約束したのに動かない」の
    理由を、帳面から言えるように。"""
    def main(argv):
        if argv[1] == "C":
            raise SystemExit("枠が尽きました")
        return 0

    monkeypatch.setattr(_sched, "main", main)
    plan = _Plan([("A", "t1"), ("B", "t2"), ("C", "t3"), ("D", "t4")])

    assert queue_lag.apply_moves(plan) == 1
    assert plan.applied == 2, "止まる前に当たった2手が残っていない"
