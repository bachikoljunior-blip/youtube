"""**動画IDの読みを、日枠の窓ごとに1回にする**（2026-09-01 の定期の回）。

`tests/test_scan_cache.py` は `_scan` の**答え**（テーマID）を控えます。
**その中で呼ばれる `channel_video_ids` は素通しでした** —— そして
`_scan` を通らない呼び手が5つあります（`status._channel_main` /
`reschedule._scheduled`（＝`pool_drain`）/ `upload_only` /
`critique_queue` / `descriptions` の註）。

実測（窓 2026-08-31 00:00 PT・`data/api_calls.jsonl` 1,494行）:

    `history.py:channel_video_ids`  **3,409単位**（窓 10,000 の **34%**）
      `search.list` 30回 ＝ 3,000単位（**100単位/ページ**）
      呼ばれた回数 **10回** → 1回ぶんを残して **約 3,100単位** が重複

`scripts/pool_drain.py` は残り 267本 を外すのに 13,617単位 要り、
「最低2日ぶんの枠が要る」と印字します（**規則1 が破れるのは 2026-09-12**）。
ここが落ちたら、その2日が戻ります。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import history  # noqa: E402


@pytest.fixture(autouse=True)
def _sandbox(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(history.config, "ROOT", tmp_path)
    monkeypatch.delenv("YT_NO_SCAN_CACHE", raising=False)
    yield tmp_path


class _Boom:
    """**呼ばれたら落ちる YouTube。** 控えが効いていれば1度も触られません。"""

    def playlistItems(self):                                   # noqa: N802
        raise AssertionError("控えが効いていれば playlistItems は呼ばれません")

    def search(self):
        raise AssertionError("控えが効いていれば search は呼ばれません")


class _Endpoint:
    def __init__(self, owner, name, items):
        self.owner, self.name, self.items = owner, name, items

    def list(self, **_kw):
        self.owner.calls.append(self.name)
        return self

    def execute(self):
        return {"items": self.items}


class _Fake:
    """1ページだけ返す口。`calls` に手を数える。"""

    def __init__(self, ids, search_ids=()):
        self.ids = list(ids)
        self.search_ids = list(search_ids)
        self.calls: list[str] = []

    def playlistItems(self):                                   # noqa: N802
        return _Endpoint(self, "playlistItems.list", [
            {"contentDetails": {"videoId": v}} for v in self.ids])

    def search(self):
        return _Endpoint(self, "search.list", [
            {"id": {"videoId": v}} for v in self.search_ids])


def test_a_second_read_in_the_same_window_costs_no_units(monkeypatch, capsys):
    """**2回目は口を1つも叩かない。** ここが 3,100単位/日 の本体。"""
    history._put_cached_video_ids("UUx", 400, ["v1", "v2"])
    from src import dupes

    monkeypatch.setattr(dupes, "ledger_rows", lambda: [])

    out = history.channel_video_ids(_Boom(), "UUx")

    assert out == ["v1", "v2"]
    assert "API 0単位" in capsys.readouterr().out


def test_the_ledger_fills_in_what_was_uploaded_after_the_window_opened(monkeypatch):
    """控えは**足し算だけ**。窓の頭より後に上げた本が落ちないこと。

    落ちると `batch_build.pick` が同じ計算のショートをもう一度作ります
    （＝ 収益化の対象外。`channel_video_ids` の「何が起きたか」）。
    """
    history._put_cached_video_ids("UUx", 400, ["old1", "old2"])
    from src import dupes

    monkeypatch.setattr(dupes, "ledger_rows",
                        lambda: [{"id": "old2"}, {"id": "fresh"}])

    out = history.channel_video_ids(_Boom(), "UUx")

    assert out == ["fresh", "old1", "old2"]      # **新しいほうが先**（新しい順）
    assert len(out) == len(set(out))             # 二重に入れない


def test_a_partial_read_is_not_cached(monkeypatch):
    """**口が欠けた回は控えない。** 控えると、その窓じゅう欠けたまま答えます。"""
    from googleapiclient.errors import HttpError

    class _Resp:
        status = 403
        reason = "quotaExceeded"

    class _Broken(_Fake):
        def search(self):
            raise HttpError(_Resp(), b"{}")

    monkeypatch.setattr(history.auth, "note_day_quota", lambda *a, **k: None)
    history.channel_video_ids(_Broken(["v1"]), "UUx")

    assert history._cached_video_ids("UUx", 400) is None


def test_a_different_playlist_or_cap_is_a_different_answer():
    """鍵は 窓・uploads・`cap` の3つ。**切られ方が違えば別の答え**です。"""
    history._put_cached_video_ids("UUx", 400, ["v1"])

    assert history._cached_video_ids("UUx", 400) == ["v1"]
    assert history._cached_video_ids("UUy", 400) is None
    assert history._cached_video_ids("UUx", 50) is None


def test_the_env_switch_turns_both_caches_off(monkeypatch):
    """**栓は1つ**（`YT_NO_SCAN_CACHE=1`）。2つあると片方が忘れられます。"""
    history._put_cached_video_ids("UUx", 400, ["v1"])
    history._put_cached_topics({"s-a"}, 400)
    monkeypatch.setenv("YT_NO_SCAN_CACHE", "1")

    assert history._cached_video_ids("UUx", 400) is None
    assert history._cached_topics() is None


def test_an_empty_read_is_never_stored():
    """**空の読みを控えないこと。** 直った瞬間に気づけなくなります。"""
    history._put_cached_video_ids("UUx", 400, [])
    assert history._cached_video_ids("UUx", 400) is None


def test_the_two_caches_do_not_share_a_file():
    """**別のファイル**であること（片方の書き込みが他方を消さない）。"""
    assert history._video_ids_cache_path() != history._scan_cache_path()


def test_the_cache_is_written_after_a_clean_read():
    """欠けなかった回は控える —— そこが無いと2回目が効きません。"""
    history.channel_video_ids(_Fake(["v1", "v2"], search_ids=["v3"]), "UUx")

    assert history._cached_video_ids("UUx", 400) == ["v1", "v2", "v3"]
