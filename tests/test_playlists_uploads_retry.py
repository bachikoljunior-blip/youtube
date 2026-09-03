"""`playlists._uploads` はページの途中の 404 を、列挙のやり直しで越えること。

2026-09-03 に実測: `channels.list` で引いた本物の `uploads` playlistId でも、
2ページ目以降の `pageToken` で "playlist ... cannot be found" (404) が
連続 2回・別々の pageToken で返った。**個別のトークンの話ではないので、
そのトークンだけ再試行しても直らない** —— 列挙をゼロからやり直す必要がある。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from googleapiclient.errors import HttpError  # noqa: E402

from scripts import playlists  # noqa: E402


class _Resp:
    def __init__(self, status: int) -> None:
        self.status = status
        self.reason = "boom"


def _http_error(status: int) -> HttpError:
    return HttpError(_Resp(status), b"boom", uri="https://example.invalid")


class _FlakyUploadsY:
    """1回目の列挙はページ2で404、2回目はやり直して最後まで通る。"""

    def __init__(self) -> None:
        self.attempts = 0

    def channels(self):
        class _Req:
            def execute(self_inner):
                return {"items": [{"contentDetails": {
                    "relatedPlaylists": {"uploads": "UUreal"}}}]}

        class _Channels:
            def list(self_inner, **kw):
                return _Req()
        return _Channels()

    def playlistItems(self):
        outer = self

        class _Req:
            def __init__(self_inner, **kw):
                self_inner.kw = kw

            def execute(self_inner):
                tok = self_inner.kw.get("pageToken")
                if tok is None:                      # 1ページ目は常に通る
                    return {"items": [{"contentDetails": {"videoId": "v1"}}],
                            "nextPageToken": "p2"}
                if tok == "p2" and outer.attempts == 0:
                    outer.attempts += 1
                    raise _http_error(404)           # 1回目のやり直し前だけ落ちる
                return {"items": [{"contentDetails": {"videoId": "v2"}}]}

        class _Playlist:
            def list(self_inner, **kw):
                return _Req(**kw)
        return _Playlist()


def test_uploads_ページ2の404はゼロからの列挙で越える(monkeypatch):
    monkeypatch.setattr(playlists.time, "sleep", lambda *_: None)
    y = _FlakyUploadsY()
    ids = playlists._uploads(y)
    assert ids == ["v1", "v2"]
    assert y.attempts == 1                    # ちょうど1回 落ちて、やり直した


class _AlwaysBoomY:
    def channels(self):
        class _Req:
            def execute(self_inner):
                return {"items": [{"contentDetails": {
                    "relatedPlaylists": {"uploads": "UUreal"}}}]}

        class _Channels:
            def list(self_inner, **kw):
                return _Req()
        return _Channels()

    def playlistItems(self):
        class _Req:
            def execute(self_inner):
                raise _http_error(404)

        class _Playlist:
            def list(self_inner, **kw):
                return _Req()
        return _Playlist()


def test_uploads_ずっと404なら諦めて例外を上げる(monkeypatch):
    monkeypatch.setattr(playlists.time, "sleep", lambda *_: None)
    try:
        playlists._uploads(_AlwaysBoomY(), tries=2)
    except HttpError as e:
        assert e.resp.status == 404
    else:
        raise AssertionError("ずっと404なのに通ってはいけない")
