"""**もう同じ値なら `videos.update` を撃たないこと**（2026-08-27 に実測して足した）。

## なぜ要るか（数はぜんぶ実測。`data/day_quota.jsonl` の窓 08/27 07:00Z 〜）

    通った `videos.update`      **273回**（13,650単位）
    撃たれた本の数              **58本**
    → 同じ本の2回目以降        **215回 ＝ 10,750単位**（**79%**）

**日枠は 1万単位**なので、これは *その日の枠を丸ごと、同じ値の書き直しに焼いた*
ということです。控えにも残っています —— `1Tduvr67ohI` `QfQWE1ykEx4` `6TK2jXQsB5s`
は `data/uploaded.jsonl` に **`at` が1文字も違わない行が2本ずつ**
（`dupes.retime` は動かすたびに1行 足すので、同じ値で撃った証拠が残ります）。

焼け切ると、その窓では `queue_lag --apply` の 12手（1,200単位）が撃てません。
あれは判定日を合計 **7日** 手前に倒す手で、`data/queue_lag.jsonl` の4行は
`hook_form` が **4回とも 09-10 のまま** ＝ 約束した前倒しが1度も実現していません。

**`_update` は現状を必ず読んでいます**（`videos.list` ＝ 1単位）。
読んだ値と書く値を比べていなかっただけです。**関門はここ1か所**なので
（入口は `--move`・`--compact`・`--spread`・`long_pack`・`live_slots`・`queue_lag`
と6つある）、呼び出し側ではなくここで止めます。

**覆る条件**: こちらが書き換える欄が `privacyStatus` と `publishAt` の2つ
だけ、でなくなったとき。下の `test_書き換えるのはこの2欄だけ` が落ちて、そう教えます。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import reschedule  # noqa: E402


class _Call:
    def __init__(self, value):
        self._value = value

    def execute(self):
        return self._value


class _Videos:
    def __init__(self, status: dict | None, *, readable: bool = True) -> None:
        self._status = status
        self._readable = readable
        self.updated: list[dict] = []
        self.reads = 0

    def list(self, **kw):
        self.reads += 1
        if not self._readable:
            raise RuntimeError("読めません")
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
             "uploadStatus": "processed",
             "license": "youtube"}


# ------------------------------------------------ 撃たない側

def test_同じ時刻へ動かす回は撃たない(monkeypatch):
    """**この回の 215回・10,750単位**は、全部この形でした。"""
    monkeypatch.delenv("YT_FORCE_UPDATE", raising=False)
    videos = _Videos(SCHEDULED)

    wrote = reschedule._update(_Svc(videos), "vid1", "2026-08-28T11:00:00Z")

    assert wrote is False
    assert videos.updated == [], "同じ値なのに 50単位 撃っている"
    assert videos.reads == 1, "現状の読み（1単位）は必要。ここは削らないこと"


def test_Zと00_00の書き方の違いで撃たないこと(monkeypatch):
    """控えは `Z`、API は `+00:00` を返すことがあります。**同じ瞬間です。**"""
    monkeypatch.delenv("YT_FORCE_UPDATE", raising=False)
    videos = _Videos(dict(SCHEDULED, publishAt="2026-08-28T11:00:00+00:00"))

    assert reschedule._update(_Svc(videos), "vid1", "2026-08-28T11:00:00Z") is False
    assert videos.updated == []


def test_予約なしの本を予約なしにする回は撃たない(monkeypatch):
    monkeypatch.delenv("YT_FORCE_UPDATE", raising=False)
    videos = _Videos({"privacyStatus": "private", "uploadStatus": "processed"})

    assert reschedule._update(_Svc(videos), "vid1", None) is False
    assert videos.updated == []


# ------------------------------------------------ 撃つ側（**飛ばしすぎないこと**）

def test_時刻がちがえば撃つ(monkeypatch):
    monkeypatch.delenv("YT_FORCE_UPDATE", raising=False)
    videos = _Videos(SCHEDULED)

    assert reschedule._update(_Svc(videos), "vid1", "2026-08-28T10:00:00Z") is True
    assert len(videos.updated) == 1
    assert videos.updated[0]["body"]["status"]["publishAt"] == "2026-08-28T10:00:00Z"


def test_予約を外す回は撃つ(monkeypatch):
    """`publishAt` が在る本を「予約なし」にするのは、**中身が変わります。**"""
    monkeypatch.delenv("YT_FORCE_UPDATE", raising=False)
    videos = _Videos(SCHEDULED)

    assert reschedule._update(_Svc(videos), "vid1", None) is True
    assert "publishAt" not in videos.updated[0]["body"]["status"]


def test_公開中の本を非公開に戻す回は撃つ(monkeypatch):
    """時刻が同じでも `privacyStatus` がちがえば飛ばさないこと。

    **2026-08-28 に、この検査の前提のほうを直しました。** もとは
    「公開中の本に `publishAt` を立て直す」形で書いてありましたが、
    **YouTube はそれを受け付けません** —— 実測（`cJw79xThyTY`・
    `2026-08-29T13:30` へ `--move`）:

        HttpError 400 … `invalidPublishAt`
        「The request metadata specifies an invalid scheduled publishing time.」

    つまりあの形は**通ったことが1度もない道**で、検査だけが通していました。
    いまは `_update` が手前で `AlreadyPublic` を投げます
    （`tests/test_already_public_skip.py`）。

    **この検査が見たいのは「privacy がちがえば飛ばさない」ほう**なので、
    予約を外す形（`publish_at=None`）で見ます。**これは実物でも通る道**です
    （公開してしまった本を private へ戻す —— `unschedule.py`）。
    """
    monkeypatch.delenv("YT_FORCE_UPDATE", raising=False)
    videos = _Videos(dict(SCHEDULED, privacyStatus="public"))

    assert reschedule._update(_Svc(videos), "vid1", None) is True
    assert videos.updated[0]["body"]["status"]["privacyStatus"] == "private"


def test_控えで代えた回は飛ばさない(monkeypatch):
    """**YouTube 側の実物を知らない回**です。飛ばすと、直っていないものを
    「直った」と言うことになります。"""
    monkeypatch.delenv("YT_FORCE_UPDATE", raising=False)
    videos = _Videos(SCHEDULED, readable=False)

    wrote = reschedule._update(_Svc(videos), "vid1", "2026-08-28T11:00:00Z",
                               fallback_status=dict(SCHEDULED))

    assert wrote is True, "読めなかった回に、控えだけを根拠に飛ばしている"
    assert len(videos.updated) == 1


def test_YT_FORCE_UPDATE_で撃ち直せる(monkeypatch):
    """**逃げ道を1つ残すこと。** 実物と控えが食い違う回に手で当て直せます。"""
    monkeypatch.setenv("YT_FORCE_UPDATE", "1")
    videos = _Videos(SCHEDULED)

    assert reschedule._update(_Svc(videos), "vid1", "2026-08-28T11:00:00Z") is True
    assert len(videos.updated) == 1


# ------------------------------------------------ 覆る条件

def test_書き換えるのはこの2欄だけ(monkeypatch):
    """**この検査が落ちたら、上の飛ばし方も足りていません。**

    `_update` が `privacyStatus` / `publishAt` 以外の欄も書き換えるように
    なったら、その欄も比べないと「同じ値」と言えません。
    """
    monkeypatch.delenv("YT_FORCE_UPDATE", raising=False)
    videos = _Videos(SCHEDULED)
    reschedule._update(_Svc(videos), "vid1", "2026-08-28T10:00:00Z")

    sent = videos.updated[0]["body"]["status"]
    before = {k: v for k, v in SCHEDULED.items()
              if k not in ("uploadStatus", "failureReason", "rejectionReason")}
    changed = {k for k in set(sent) | set(before) if sent.get(k) != before.get(k)}
    assert changed <= {"privacyStatus", "publishAt"}, (
        f"比べていない欄を書き換えています: {sorted(changed)}。"
        "**`_update` の飛ばし方に、その欄を足すこと**")


def test_読み取り専用の欄は送り返さない(monkeypatch):
    monkeypatch.delenv("YT_FORCE_UPDATE", raising=False)
    videos = _Videos(SCHEDULED)
    reschedule._update(_Svc(videos), "vid1", "2026-08-28T10:00:00Z")

    assert "uploadStatus" not in videos.updated[0]["body"]["status"]


# ------------------------------------------------ 時刻の比べ方そのもの

@pytest.mark.parametrize("a,b,same", [
    ("2026-08-28T11:00:00Z", "2026-08-28T11:00:00+00:00", True),
    ("2026-08-28T11:00:00Z", "2026-08-28T11:00:00.000Z", True),
    ("2026-08-28T11:00:00Z", "2026-08-28T20:00:00+09:00", True),
    ("2026-08-28T11:00:00Z", "2026-08-28T12:00:00Z", False),
    (None, None, True),
    ("2026-08-28T11:00:00Z", None, False),
    ("ごみ", "ごみ", True),
    ("ごみ", "2026-08-28T11:00:00Z", False),
])
def test_同じ瞬間かを見分ける(a, b, same):
    assert reschedule._same_instant(a, b) is same
