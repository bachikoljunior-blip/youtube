"""**チャンネルの読みを、日枠の窓ごとに1回にする**（2026-08-28 の最適化の回）。

`src/upload_cap.py` は今朝、計測のぶんに **400単位** を残す門を足しました。
残している相手は「前提を閉じる読み」で、`eta.py` が毎回
「軌跡の腕が動くのは前提を1件 閉じたときだけ」と言う、その唯一の操作です。

**その 400単位 は、`_scan` の前では 2時間 しか持ちません**:

    `_scan` 1回          **17単位**（cap=400 ＝ channels.list 1
                          ＋ playlistItems.list 8ページ ＋ videos.list 8束）
    呼ばれる速さ         **15回/時**（`data/day_quota.jsonl` の窓 08/27。
                          403 の側で数えた ＝ 下限）
    → 255単位/時 ／ 400単位 ＝ **1.6時間**（窓は 23時間）

窓は 08/28 16:00 JST に開き、08-28 の前提が要る読みは **22:00 JST** です。
**18:00 に残りが尽きます。** それで閉じられないのは 08/27 夕・08/28 未明に続く
**3回目**になります。

ここが落ちたら、その3回目が戻っています。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import history  # noqa: E402


@pytest.fixture(autouse=True)
def _sandbox(tmp_path, monkeypatch):
    """控えの置き場を tmp に逃がす（本物の `data/` を触らない）。"""
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(history.config, "ROOT", tmp_path)
    monkeypatch.delenv("YT_NO_SCAN_CACHE", raising=False)
    yield tmp_path


class _Boom:
    """**呼ばれたら落ちる YouTube。** 控えが効いていれば1度も触られません。"""

    def channels(self):
        raise AssertionError("控えが効いていれば API は呼ばれません")


def test_second_call_in_the_same_window_costs_no_units(monkeypatch, capsys):
    history._put_cached_topics({"s-a", "s-b"}, 400)
    monkeypatch.setattr(history, "build", lambda *a, **k: _Boom())
    monkeypatch.setattr(history, "credentials", lambda: None)
    monkeypatch.setattr(history, "ledger_topics", lambda: {})

    assert history._scan(want_map=False) == {"s-a", "s-b"}
    assert "API 0単位" in capsys.readouterr().out


def test_the_cache_is_still_unioned_with_the_ledger(monkeypatch):
    """**控えた読みも、いまの控え（ledger）と和を取ること。**

    ここが無いと、窓の頭のチャンネルの答えで窓じゅう走ることになり、
    **その窓に上げた本が全部「未投稿」に見えます** ——
    `batch_build.pick` が同じ計算をもう一度作る側です。
    """
    history._put_cached_topics({"s-a"}, 400)
    monkeypatch.setattr(history, "build", lambda *a, **k: _Boom())
    monkeypatch.setattr(history, "credentials", lambda: None)
    monkeypatch.setattr(history, "ledger_topics",
                        lambda: {"s-a": "v1", "s-new": "v2"})

    assert history._scan(want_map=False) == {"s-a", "s-new"}


def test_a_cache_from_another_window_is_ignored(monkeypatch):
    """窓が変われば読み直すこと（枠も戻っているので、読める）。"""
    history._put_cached_topics({"s-a"}, 400)
    cache = history.config.ROOT / history._SCAN_CACHE
    rec = json.loads(cache.read_text(encoding="utf-8"))
    rec["window"] = "1999-01-01T00:00:00+00:00"
    cache.write_text(json.dumps(rec), encoding="utf-8")

    assert history._cached_topics() is None


def test_the_map_never_uses_the_cache(monkeypatch):
    """`topic_video_map()` は撮り直しで答えが変わるので、控えない。

    集合の和は順番を持ちませんが、写像は「テーマ→**どの**動画」なので
    古い動画IDを返しえます。**呼ぶ回数が多いのは集合の側**です。
    """
    history._put_cached_topics({"s-a"}, 400)
    called = {"n": 0}

    def _build(*_a, **_k):
        called["n"] += 1
        raise AssertionError("ここまで来れば控えを使っていない")

    monkeypatch.setattr(history, "build", _build)
    monkeypatch.setattr(history, "credentials", lambda: None)
    with pytest.raises(AssertionError):
        history._scan(want_map=True)
    assert called["n"] == 1


def test_a_partial_read_is_never_cached(monkeypatch):
    """**欠けた読みを控えると、その窓じゅう欠けたまま**になります。"""
    monkeypatch.setattr(history, "_put_cached_topics",
                        lambda *a, **k: pytest.fail("欠けた回を控えています"))

    class _Videos:
        def list(self, **_kw):
            from googleapiclient.errors import HttpError

            class _R:
                status, reason = 403, "quotaExceeded"

            raise HttpError(_R(), b'{"error": {"message": "quota"}}')

    class _Ch:
        def list(self, **_kw):
            class _Req:
                def execute(self):
                    return {"items": [{"contentDetails": {
                        "relatedPlaylists": {"uploads": "UUx"}}}]}

            return _Req()

    class _Yt:
        def channels(self):
            return _Ch()

        def videos(self):
            return _Videos()

    monkeypatch.setattr(history, "build", lambda *a, **k: _Yt())
    monkeypatch.setattr(history, "credentials", lambda: None)
    monkeypatch.setattr(history, "channel_video_ids", lambda *a, **k: ["aaa"])
    monkeypatch.setattr(history, "ledger_topics", lambda: {"s-a": "v1"})
    assert history._scan(want_map=False) == {"s-a"}


def test_the_escape_hatch_works(monkeypatch):
    """`YT_NO_SCAN_CACHE=1` で外せること（外した回は理由を JOURNAL に）。"""
    history._put_cached_topics({"s-a"}, 400)
    assert history._cached_topics() == {"s-a"}
    monkeypatch.setenv("YT_NO_SCAN_CACHE", "1")
    assert history._cached_topics() is None
