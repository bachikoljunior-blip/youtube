"""**投稿後の付随処理は、計測のぶんを残す門に従うこと**（2026-08-28 の2周目）。

`src/uploader._post_actions` は**1本の投稿ごとに 150単位**を使います
（再生リスト作成 50 ＋ 項目 50 ＋ コメント 50）。実測 08/27 の窓は 37本 ＝
**5,550単位**、残してある `RESERVE_UNITS` 400 の **13.9倍**を、
この回まで**数えも止めもせず**に使っていました。

**止めてよい理由**: ここは元々「失敗しても動画は上がっているので落とさない」
設計で、やり残しを拾う道具が両方あります（`scripts/playlists.py` /
`scripts/post_pending_comments.py`）。一方、残している 400単位 が守るのは
「前提を閉じる読み」で、`eta.py` が毎回「軌跡の腕が動くのは前提を1件
閉じたときだけ」と言う、その唯一の操作です。

**ここが落ちたら、投稿が枠を焼き切って夜の判定が撃てなくなります。**
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import uploader  # noqa: E402


class _Boom:
    """**触られたら落ちる YouTube。** 門が効いていれば1度も来ません。"""

    def playlists(self):
        raise AssertionError("門が効いていれば再生リストは触りません")

    def playlistItems(self):
        raise AssertionError("門が効いていれば項目は触りません")

    def commentThreads(self):
        raise AssertionError("門が効いていればコメントは触りません")


CFG = {"playlist": "テスト", "first_comment": "こんにちは"}


def test_枠を残す回は_付随処理を後回しにする(monkeypatch, capsys):
    monkeypatch.setattr(uploader.upload_cap, "reserve_hold",
                        lambda *a, **k: "**残しています**（検査）")
    uploader._post_actions(_Boom(), "vid1", CFG)     # 例外を上げないこと
    out = capsys.readouterr().out
    assert "後回し" in out
    # **拾い直す道具を名指しすること。** 名指ししないと、やり残しが消えます
    assert "playlists.py" in out and "post_pending_comments.py" in out


def test_枠が余っていれば_今までどおり撃つ(monkeypatch):
    monkeypatch.setattr(uploader.upload_cap, "reserve_hold", lambda *a, **k: None)
    touched = []

    class _Req:
        def execute(self):
            return {"items": [], "id": "PL1"}

    class _Playlists:
        def list(self, **_kw):
            touched.append("playlists.list")
            return _Req()

        def insert(self, **_kw):
            touched.append("playlists.insert")
            return _Req()

    class _Items:
        def insert(self, **_kw):
            touched.append("playlistItems.insert")
            return _Req()

    class _Comments:
        def insert(self, **_kw):
            touched.append("commentThreads.insert")
            return _Req()

    class _Yt:
        def playlists(self):
            return _Playlists()

        def playlistItems(self):
            return _Items()

        def commentThreads(self):
            return _Comments()

    monkeypatch.setattr(uploader.upload_cap, "note_quota_ok", lambda **_kw: None)
    uploader._post_actions(_Yt(), "vid1", CFG)
    assert "playlistItems.insert" in touched
    assert "commentThreads.insert" in touched


def test_設定が空なら_門も要らない(monkeypatch):
    """再生リストもコメントも要らない回は、単位を1つも使いません。"""
    monkeypatch.setattr(uploader.upload_cap, "reserve_hold", lambda *a, **k: None)
    uploader._post_actions(_Boom(), "vid1", {})      # 触らない ＝ 落ちない
