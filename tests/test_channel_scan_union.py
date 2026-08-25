"""**チャンネルの動画を数える口が、予約中の動画を落とさないこと**を固定する。

## なぜ要るか（2026-08-15 23:0x に実測した）

CLAUDE.md は「投稿済みは説明欄の `[t:テーマID]` から**チャンネル越しに復元する。
ファイルに持たない**」と言っています。その復元の入口は `history._scan` ひとつで、
そこは長らく **uploads プレイリストだけ**を読んでいました。

    uploads プレイリスト  69本
    search(forMine)      76本
    差 7本 —— **7本とも private（予約中）で publishAt が入っている**

同じ日のうちに 69 と 76 の両方を返しています。**遅れて揃う口**なので、
件数を見ても壊れているように見えません。

落ちた7本の説明欄には `[t:s-kojo-2]` などが入っていました。つまり
**投稿済みなのに未投稿として数えられ**、`batch_build.pick` がもう一度選びます。
実際この回は `s-kojo-2` / `s-kojo-3` を作り直し、**同じ計算・同じ金額**の
ショートを予約しました（`1万2709円` が 8/18 と 8/19 に）。
同じ穴で 8/16・8/17 にも既に二重予約が入っていました。

**これは見栄えの話ではありません。** YouTube は「同じチャンネルの動画を続けて
数本視聴した後、繰り返しのように感じられる可能性のあるコンテンツ」を
**収益化の対象外**と書いています。収益化されなければ収入はゼロなので、
**自分で作った重複が門を閉じます。**

## ここで固定すること

1. **プレイリストに出ない動画を拾うこと**（これが直しの本体）
2. **重複を返さないこと**（両方に出る動画は1回）
3. **search が落ちても、プレイリストぶんは返すこと**
   （何も返さないと「全テーマ未使用」になり、**全部作り直す**側に倒れます）
4. **ページを最後までたどること**（1ページ50本で切ると古いほうから欠ける）
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from googleapiclient.errors import HttpError  # noqa: E402

from src import history  # noqa: E402


class _Req:
    def __init__(self, payload):
        self._payload = payload

    def execute(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class _Endpoint:
    """`list(...)` を呼ばれた回数ぶん、用意したページを順に返す。"""

    def __init__(self, pages):
        self._pages = list(pages)
        self.calls = 0

    def list(self, **kw):
        self.calls += 1
        return _Req(self._pages.pop(0) if self._pages else {"items": []})


class _YouTube:
    def __init__(self, playlist_pages, search_pages):
        self._pl = _Endpoint(playlist_pages)
        self._se = _Endpoint(search_pages)

    def playlistItems(self):
        return self._pl

    def search(self):
        return self._se


def _pl_page(ids, token=""):
    page = {"items": [{"contentDetails": {"videoId": i}} for i in ids]}
    if token:
        page["nextPageToken"] = token
    return page


def _se_page(ids, token=""):
    page = {"items": [{"id": {"videoId": i}} for i in ids]}
    if token:
        page["nextPageToken"] = token
    return page


def test_予約中の動画を拾う():
    """**これが直しの本体。** プレイリストに出ない private を search が拾う。"""
    yt = _YouTube([_pl_page(["a", "b"])], [_se_page(["a", "b", "private1"])])
    assert history.channel_video_ids(yt, "UU") == ["a", "b", "private1"]


def test_重複を返さない():
    yt = _YouTube([_pl_page(["a", "b"])], [_se_page(["b", "a"])])
    assert history.channel_video_ids(yt, "UU") == ["a", "b"]


def test_searchが落ちてもプレイリストぶんは返す():
    """**何も返さないと「全テーマ未使用」になり、全部作り直す側に倒れます。**"""
    yt = _YouTube([_pl_page(["a", "b"])],
                  [HttpError(resp=type("R", (), {"status": 403, "reason": "x"})(), content=b"{}")])
    assert history.channel_video_ids(yt, "UU") == ["a", "b"]


def test_ページを最後までたどる():
    """1ページで切ると、**古いほうから黙って欠けます。**"""
    yt = _YouTube(
        [_pl_page([f"p{i}" for i in range(50)], token="next"), _pl_page(["p50"])],
        [_se_page(["s0"])],
    )
    got = history.channel_video_ids(yt, "UU")
    assert "p50" in got and "s0" in got, got
    assert len(got) == 52, len(got)


def test_上限で止まる():
    """暴走しないこと（上限を超えて呼び続けない）。"""
    pages = [_pl_page([f"v{p}-{i}" for i in range(50)], token="t") for p in range(20)]
    yt = _YouTube(pages, [_se_page(["s0"])])
    got = history.channel_video_ids(yt, "UU", cap=100)
    assert len(got) <= 150, len(got)
    assert yt._pl.calls <= 3, yt._pl.calls
