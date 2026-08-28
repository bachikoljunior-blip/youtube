"""**外の口が欠けた回でも、生成の段まで進めること**（2026-08-17）。

`src/history.py` は「落ちても止めない」を**3か所のうち1か所にしか掛けていません**でした。

    channels().list        try/except あり（ただし**空を返す**＝全テーマ未投稿）
    playlistItems().list   **素通し**  ← ここで死ぬ
    search().list          try/except あり（註つき「落ちても止めない」）
    videos().list          **素通し**

同じ節の中に、守る側と素通しの側が並んでいます。この repo が8回くり返している
「**片方だけ**」の形です。

2026-08-17 03:5x に実際に踏みました —— Data API の1日枠が切れた回で、
uploads プレイリストの**2ページ目**が 403 になり、例外が
`posted_topic_ids()` → `pipeline.main` まで上がって**生成ごと死にました。**
1ページ目は通っていたので、**手元には答えの大半があったのに全部捨てています。**

これが塞いでいたもの: 日枠が戻るのは JST 16:00 なので、それ以前の十数周は
**作る段にすら入れません**（`docs/trigger_main.md` §5 の
「作る段は Data API を1単位も使わない」は、実装と食い違っていました）。

**そして「続行」の中身が本体です。** 投稿済みのテーマが「未投稿」に見えると、
`batch_build.pick` が同じ計算・同じ金額のショートをもう一度作ります。それは
「繰り返しのように感じられるコンテンツ」＝**収益化の対象外**そのものなので、
欠けた回は**手元の控えで埋めます**。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from googleapiclient.errors import HttpError

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import history  # noqa: E402


@pytest.fixture(autouse=True)
def _sandbox_the_scan_cache(tmp_path, monkeypatch):
    """**本物の `data/` に書かせないこと**（2026-08-28 に踏んだ）。

    `_scan` は窓ごとの控え（`data/scan_topics.json`）を書きます。
    この檻を外すと、ここの検査が**本物の控えに `s-new` を書き込み**、
    次に走った回が「投稿済みテーマ 1件」で動きます —— 実際に、
    足した直後の実行で `_cached_topics()` が `{'s-new'}` を返しました。
    """
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(history.config, "ROOT", tmp_path)


class _Resp:
    def __init__(self, status: int) -> None:
        self.status = status
        self.reason = "quotaExceeded"


def _quota_error() -> HttpError:
    return HttpError(_Resp(403), b'{"error": {"message": "quota"}}')


class _Req:
    """`.execute()` を1回ぶん返す（例外も返せる）。"""

    def __init__(self, result):
        self._result = result

    def execute(self):
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


class _PlaylistItems:
    """1ページ目は返り、2ページ目で日枠切れ。**実際に踏んだ形そのもの。**"""

    def __init__(self) -> None:
        self.calls = 0

    def list(self, **_kw):
        self.calls += 1
        if self.calls == 1:
            return _Req({"items": [{"contentDetails": {"videoId": "aaa"}}],
                         "nextPageToken": "PAGE2"})
        return _Req(_quota_error())


class _Search:
    def list(self, **_kw):
        return _Req(_quota_error())


class _Youtube:
    def __init__(self) -> None:
        self._pi = _PlaylistItems()
        self._se = _Search()

    def playlistItems(self):
        return self._pi

    def search(self):
        return self._se


def test_first_page_survives_a_dead_second_page(capsys):
    """**取れたところまでで返す。** 例外を上げると1ページ目ごと捨てることになる。"""
    got = history.channel_video_ids(_Youtube(), "UUxxxx")
    assert got == ["aaa"]
    assert "最後まで読めませんでした" in capsys.readouterr().out


def test_ledger_topics_reads_the_local_copy(monkeypatch):
    from src import dupes

    monkeypatch.setattr(dupes, "ledger_rows", lambda: [
        {"id": "vid1", "title": "t", "topic": "s-a"},
        {"id": "vid2", "title": "t", "topic": ""},        # ← テーマ印なし。落とす
    ])
    assert history.ledger_topics() == {"s-a": "vid1"}


def test_only_ledger_does_not_claim_everything_is_unposted(monkeypatch, capsys):
    """**「全テーマ未使用」で返さないこと。**

    それは「投稿済みを全部もう一度作ってよい」と言うのと同じです。
    空より控えのほうが必ず近い。
    """
    monkeypatch.setattr(history, "ledger_topics", lambda: {"s-a": "vid1", "s-b": "vid2"})
    assert history._only_ledger(False, "検査") == {"s-a", "s-b"}
    assert history._only_ledger(True, "検査") == {"s-a": "vid1", "s-b": "vid2"}
    assert "控え" in capsys.readouterr().out


def test_only_ledger_still_returns_when_the_ledger_is_broken(monkeypatch, capsys):
    """**控えが壊れていても回を止めない。** そこまで来たら空しか無い。"""
    def boom():
        raise OSError("壊れている")

    monkeypatch.setattr(history, "ledger_topics", boom)
    assert history._only_ledger(False, "検査") == set()
    assert history._only_ledger(True, "検査") == {}
    assert "控えも読めません" in capsys.readouterr().out


@pytest.mark.parametrize("want_map", [True, False])
def test_dead_channel_call_falls_back_to_the_ledger(monkeypatch, want_map):
    """`channels().list` が 403 の回も、控えで答える。"""
    class _Ch:
        def list(self, **_kw):
            return _Req(_quota_error())

    class _Yt:
        def channels(self):
            return _Ch()

    monkeypatch.setattr(history, "build", lambda *a, **k: _Yt())
    monkeypatch.setattr(history, "credentials", lambda: None)
    monkeypatch.setattr(history, "ledger_topics", lambda: {"s-a": "vid1"})
    got = history._scan(want_map=want_map)
    assert got == ({"s-a": "vid1"} if want_map else {"s-a"})


def test_partial_description_scan_is_filled_from_the_ledger(monkeypatch, capsys):
    """説明欄の読みが途中で落ちた回も、**控えを足してから**返す。"""
    class _Videos:
        def list(self, **_kw):
            return _Req(_quota_error())

    class _Ch:
        def list(self, **_kw):
            return _Req({"items": [{"contentDetails":
                                    {"relatedPlaylists": {"uploads": "UUx"}}}]})

    class _Yt:
        def channels(self):
            return _Ch()

        def videos(self):
            return _Videos()

    monkeypatch.setattr(history, "build", lambda *a, **k: _Yt())
    monkeypatch.setattr(history, "credentials", lambda: None)
    monkeypatch.setattr(history, "channel_video_ids", lambda *a, **k: ["aaa", "bbb"])
    monkeypatch.setattr(history, "ledger_topics", lambda: {"s-a": "vid1"})
    assert history._scan(want_map=False) == {"s-a"}
    assert "控えから" in capsys.readouterr().out


# --------------------------------------------------------------------------
# **落ちていないのに欠ける道**（2026-08-28 に足した）
#
# 上の検査は全部 `HttpError` から入ります。ところが実際に9日 効いていた欠けは
# 例外を1つも出しません —— `channel_video_ids(cap=400)` が、チャンネルの
# 608本 のうち**古い 208本 を黙って切って**いました（`partial` は False のまま）。
#
# 実測 2026-08-28（`data/uploaded.jsonl`・API 0単位）:
#     チャンネル 608本 ／ 見えない 208本 ／「未投稿」に見えるテーマ 188件
#     こうなった日 2026-08-19
#
# だから `_scan` の控え合流を**無条件**にしました。ここはその門です。
# --------------------------------------------------------------------------


def _yt_all_ok(descriptions):
    """説明欄の読みが**全部 通る**チャンネル（例外は1つも出ない）。"""
    class _Videos:
        def list(self, **kw):
            want = set(kw["id"].split(","))
            return _Req({"items": [{"id": v, "snippet": {"description": d}}
                                   for v, d in descriptions.items() if v in want]})

    class _Ch:
        def list(self, **_kw):
            return _Req({"items": [{"contentDetails":
                                    {"relatedPlaylists": {"uploads": "UUx"}}}]})

    class _Yt:
        def channels(self):
            return _Ch()

        def videos(self):
            return _Videos()

    return _Yt()


def test_cap_truncation_is_filled_from_the_ledger(monkeypatch, capsys):
    """**上限で切られた回**も、控えと和を取ること（例外は1つも出ない）。

    ここが落ちたら `_scan` の合流がまた `if partial or not video_ids:` に
    戻っています。**戻すと 188件 が「未投稿」に化けます** ——
    `src/bars.py` の「同じ絵を出さない」守りが、そのぶん比べなくなります。
    """
    monkeypatch.setattr(history, "build",
                        lambda *a, **k: _yt_all_ok({"new": "[t:s-new]"}))
    monkeypatch.setattr(history, "credentials", lambda: None)
    # 上限で切られた ＝ **新しい1本しか返らない**（古い本は見えない）
    monkeypatch.setattr(history, "channel_video_ids", lambda *a, **k: ["new"])
    monkeypatch.setattr(history, "ledger_topics",
                        lambda: {"s-old": "vid-old", "s-new": "new"})

    got = history._scan(want_map=False)
    assert got == {"s-new", "s-old"}, "上限で切られた古い側が未投稿に化けています"
    assert "説明欄の読みが途中で落ちた回" not in capsys.readouterr().out


def test_cap_truncation_is_filled_in_the_map_too(monkeypatch):
    """テーマ→動画の写像でも同じこと（`critique_record` がこちらを使います）。"""
    monkeypatch.setattr(history, "build",
                        lambda *a, **k: _yt_all_ok({"new": "[t:s-new]"}))
    monkeypatch.setattr(history, "credentials", lambda: None)
    monkeypatch.setattr(history, "channel_video_ids", lambda *a, **k: ["new"])
    monkeypatch.setattr(history, "ledger_topics",
                        lambda: {"s-old": "vid-old", "s-new": "vid-stale"})

    got = history._scan(want_map=True)
    assert got["s-old"] == "vid-old"
    # **チャンネルの答えを控えで上書きしないこと**（`setdefault`）。
    # チャンネルのほうが新しいので、撮り直した本はそちらが正しい。
    assert got["s-new"] == "new"


def test_hitting_the_cap_says_so(capsys):
    """**満杯なのか丁度なのかを、印字で区別できること。**

    `チャンネルの動画 400本` だけでは読めません。読めないと、
    次に来た側は9日 気づきません（実測: 08/19 → 08/28）。
    """
    class _PI:
        def list(self, **_kw):
            return _Req({"items": [{"contentDetails": {"videoId": f"v{i}"}}
                                   for i in range(50)]})

    class _Yt:
        def playlistItems(self):
            return _PI()

        def search(self):
            raise AssertionError("上限に達したら search は要りません")

    got = history.channel_video_ids(_Yt(), "UUx", cap=50)
    assert len(got) >= 50
    assert "上限" in capsys.readouterr().out
