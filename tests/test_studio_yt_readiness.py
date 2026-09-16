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


# --- 2026-09-16 23:3x（optimizer・Fable 5.1・ultracode）: publishAt の穴 -------------------
# 実測: `FLLHpj27v7s`（09/15 21:00 の枠）・`4MpH3QliNi4`（09/16 12:00 の枠）は刻を過ぎても
# public にならないまま、`ready_checked` が **8周 とも ok: true** を書いていた。
# 処理は本当に通っていた（upload=processed / processing=succeeded）＝ **本は無事で、刻だけが消えていた**。


def _v(status):
    return [{"id": "A", "status": {"uploadStatus": "processed", **status},
             "processingDetails": {"processingStatus": "succeeded"}}]


def test_privateなのに刻が無い本は_okでない(monkeypatch):
    """**この本は永久に出ない。** 処理は通っているので、前の門は 1つも鳴らなかった。"""
    monkeypatch.setattr(yt, "svc", lambda: _Svc(_v({"privacyStatus": "private"})))
    r = yt.readiness("A")
    assert not r["ok"] and r["no_publish_at"] and r["publish_at"] is None


def test_privateでも刻が在れば_ok(monkeypatch):
    monkeypatch.setattr(yt, "svc", lambda: _Svc(_v({"privacyStatus": "private",
                                                    "publishAt": "2026-09-17T10:00:00Z"})))
    r = yt.readiness("A")
    assert r["ok"] and not r["no_publish_at"] and r["publish_at"] == "2026-09-17T10:00:00Z"


def test_publicは刻を持たなくても_ok(monkeypatch):
    """もう出ている本は publishAt を持たない ＝ ここで赤くしない（陽性対照の裏）。"""
    monkeypatch.setattr(yt, "svc", lambda: _Svc(_v({"privacyStatus": "public"})))
    assert yt.readiness("A")["ok"]


def test_陽性対照_刻を外すと_okが落ちる(monkeypatch):
    """**動くはずの物**: 同じ本から publishAt だけを外すと ok が True → False に反転する。"""
    monkeypatch.setattr(yt, "svc", lambda: _Svc(_v({"privacyStatus": "private",
                                                    "publishAt": "2026-09-17T10:00:00Z"})))
    assert yt.readiness("A")["ok"] is True
    monkeypatch.setattr(yt, "svc", lambda: _Svc(_v({"privacyStatus": "private"})))
    assert yt.readiness("A")["ok"] is False
