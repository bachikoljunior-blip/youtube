"""`yt.reschedule` は**打った刻を読み返す**（2026-09-16 23:3x・optimizer・Fable 5.1・ultracode）。

**踏んだ形**: 09/15 14:27 の 2回 の `reschedule` は、どちらも例外を投げずに帰り、
`cmd_reschedule` は「動かした」と印字して台帳に `scheduled` を書いた。
**そして 2本 とも、刻が来ても public にならなかった**（26.6時間／11.6時間）。
同じ 2日 に `reschedule` を通していない 5本 は、**5本 とも刻どおりに出ている。**

＝ 打ちっぱなしにしていたのが穴。**返りの `status` を見るのは 0単位**、
返りが持っていないときだけ `videos.list`（1単位）。
"""
from __future__ import annotations

import datetime as dt

from studio import yt
from studio.common import JST

AT = dt.datetime(2026, 9, 17, 21, 0, tzinfo=JST)
WANT = "2026-09-17T12:00:00Z"        # AT を UTC にした形


class _Svc:
    """`videos().update()` と `videos().list()` の最小の型。撃った回数を数える。"""

    def __init__(self, update_status, list_status=None):
        self.update_status, self.list_status = update_status, list_status
        self.updates, self.lists = 0, 0
        self._next = None

    def videos(self):
        return self

    def update(self, **kw):
        self.updates += 1
        self._next = {"id": "A", "status": self.update_status}
        return self

    def list(self, **kw):
        self.lists += 1
        self._next = {"items": [{"id": "A", "status": self.list_status or {}}]}
        return self

    def execute(self):
        return self._next


def test_刻が入れば_stuck(monkeypatch):
    s = _Svc({"privacyStatus": "private", "publishAt": WANT})
    monkeypatch.setattr(yt, "svc", lambda: s)
    r = yt.reschedule("A", AT)
    assert r["stuck"] and r["got"] == WANT
    assert s.lists == 0          # 返りが持っていれば **0単位** の読み返しで済む


def test_返りに刻が無ければ1単位で引き直す(monkeypatch):
    s = _Svc({"privacyStatus": "private"}, list_status={"privacyStatus": "private", "publishAt": WANT})
    monkeypatch.setattr(yt, "svc", lambda: s)
    r = yt.reschedule("A", AT)
    assert r["stuck"] and s.lists == 1


def test_どちらにも刻が無ければ_stuckでない(monkeypatch):
    """**これが 09/15 に 2本 起きた形**（打ったのに入らなかった）。"""
    s = _Svc({"privacyStatus": "private"}, list_status={"privacyStatus": "private"})
    monkeypatch.setattr(yt, "svc", lambda: s)
    r = yt.reschedule("A", AT)
    assert not r["stuck"] and r["got"] is None


def test_別の刻が返ったら_stuckでない(monkeypatch):
    """打った刻と違う刻が入っている周も落とす（「入った」と読むと枠を落とす）。"""
    s = _Svc({"privacyStatus": "private", "publishAt": "2026-09-19T12:00:00Z"})
    monkeypatch.setattr(yt, "svc", lambda: s)
    assert not yt.reschedule("A", AT)["stuck"]


def test_陽性対照_刻を1つ足すと_stuckが反転する(monkeypatch):
    """**動くはずの物**: 同じ呼びの返りに publishAt を足すだけで False → True。"""
    s = _Svc({"privacyStatus": "private"}, list_status={"privacyStatus": "private"})
    monkeypatch.setattr(yt, "svc", lambda: s)
    assert yt.reschedule("A", AT)["stuck"] is False
    s2 = _Svc({"privacyStatus": "private"}, list_status={"privacyStatus": "private", "publishAt": WANT})
    monkeypatch.setattr(yt, "svc", lambda: s2)
    assert yt.reschedule("A", AT)["stuck"] is True
