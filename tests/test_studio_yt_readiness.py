"""予約ずみの本が本当に出る状態かを `status` が見ること（2026-09-08 02:5x・hourly・Fable）。

`status` の「きょうの枠」は privacy しか印字しておらず、YouTube 側の処理が失敗して
いても private のまま黙って出ない。公開前の周がそれを 1単位 で見られるようにした。
"""
from studio import yt


class _Svc:
    def __init__(self, items):
        self._items = items

    def videos(self):
        return self

    def list(self, **kw):
        assert "processingDetails" in kw["part"]
        return self

    def execute(self):
        return {"items": self._items}


def test_処理が終わった本は_ok(monkeypatch):
    monkeypatch.setattr(yt, "svc", lambda: _Svc([{"id": "A", "status": {"uploadStatus": "processed"},
                                                  "processingDetails": {"processingStatus": "succeeded"}}]))
    r = yt.readiness("A")
    assert r["ok"] and r["upload"] == "processed" and r["processing"] == "succeeded"


def test_失敗した本は_okでない(monkeypatch):
    monkeypatch.setattr(yt, "svc", lambda: _Svc([{"id": "A", "status": {"uploadStatus": "failed", "failureReason": "codec"},
                                                  "processingDetails": {"processingStatus": "failed"}}]))
    r = yt.readiness("A")
    assert not r["ok"] and r["failure"] == "codec"


def test_見つからない本は_okでない(monkeypatch):
    monkeypatch.setattr(yt, "svc", lambda: _Svc([]))
    assert not yt.readiness("A")["ok"]
