"""全本の写し（`yt.all_videos()`）を周をまたいで持つこと（2026-09-19 10:xx・optimizer・Fable 5.1・ultracode）。

実測の穴（`data/studio/api.jsonl`・09/18 16:00〜09/19 09:15 JST）: `all_videos()` はプロセスごとに
uploads 16ページ ＋ videos.list 16 ＝ 32単位 を引き直していて、1日 25回 ＝ **816単位**（上げる以外の最大の口）。
その 816 が日枠を押し出し、09:03 の 403 から 16:00 まで `status`／`measure` が読めなかった。

検査が守る形（`studio/yt.py` の写しの段）:
  - 2度目のプロセスは file から読み、YouTube を 1度も撃たない（0単位）
  - 寿命を過ぎたら引き直す／token が替わったら別の file（別チャンネルの写しを読まない）
  - 刻の過ぎた予約は public と読む・未来の予約は予約のまま
  - `upload` の直後に写しへ 1行 足す（同じ周の次の `schedule` が「きょうの枠」に数える）
  - `refresh_stats` は写しの `views` を 1単位 で新しくし、写しが無ければ 0回
  - pytest の下で置き場を明示しなければ、file を読まない・書かない
"""
import datetime as dt
import json

import pytest

from studio import yt


def _utc(t):
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class _Exec:
    def __init__(self, payload):
        self._p = payload

    def execute(self):
        return self._p


class _Svc:
    """playlistItems.list（1ページ）と videos.list を持つ偽の口。撃った回数を数える。"""

    def __init__(self, items, stats=None):
        self.items = items
        self.stats = stats or {}
        self.calls = []

    def channels(self):
        s = self

        class _C:
            def list(self, **k):
                s.calls.append("channels.list")
                return _Exec({"items": [{"id": "UC1", "snippet": {"title": "t"},
                                         "contentDetails": {"relatedPlaylists": {"uploads": "UU1"}},
                                         "statistics": {"subscriberCount": "1", "viewCount": "2", "videoCount": "3"}}]})
        return _C()

    def playlistItems(self):
        s = self

        class _P:
            def list(self, **k):
                s.calls.append("playlistItems.list")
                return _Exec({"items": [{"contentDetails": {"videoId": v["id"]}} for v in s.items]})
        return _P()

    def videos(self):
        s = self

        class _V:
            def list(self, part="", id="", **k):
                s.calls.append(f"videos.list:{part}")
                ids = id.split(",")
                if part == "statistics":
                    return _Exec({"items": [{"id": i, "statistics": s.stats.get(i, {"viewCount": "0"})} for i in ids]})
                return _Exec({"items": [dict(v) for v in s.items if v["id"] in ids]})
        return _V()


def _item(vid, published, privacy="public", publish_at=None, views="5"):
    st = {"privacyStatus": privacy}
    if publish_at:
        st["publishAt"] = publish_at
    return {"id": vid, "snippet": {"title": vid, "publishedAt": published}, "status": st,
            "statistics": {"viewCount": views, "likeCount": "0", "commentCount": "0"},
            "contentDetails": {"duration": "PT1M"}}


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_YT_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("YT_REFRESH_TOKEN", "tok-A")
    monkeypatch.setattr(yt, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(yt, "_ALL", None)
    return tmp_path


def test_2度目のプロセスは写しから読んで撃たない(cache_dir, monkeypatch):
    now = yt.now_jst()
    svc = _Svc([_item("A", _utc(now - dt.timedelta(hours=3)))])
    monkeypatch.setattr(yt, "svc", lambda: svc)
    rows = yt.all_videos()
    assert [v["id"] for v in rows] == ["A"]
    n_first = len(svc.calls)
    assert n_first >= 3          # channels.list ＋ playlistItems.list ＋ videos.list
    assert yt.cache_path().exists()
    # 別のプロセス（`_ALL` を空に）
    monkeypatch.setattr(yt, "_ALL", None)
    svc.calls.clear()
    rows2 = yt.all_videos()
    assert [v["id"] for v in rows2] == ["A"]
    assert svc.calls == [], "写しが在るのに YouTube を撃っている"


def test_寿命を過ぎたら引き直す(cache_dir, monkeypatch):
    now = yt.now_jst()
    svc = _Svc([_item("A", _utc(now - dt.timedelta(hours=3)))])
    monkeypatch.setattr(yt, "svc", lambda: svc)
    yt.all_videos()
    # file の刻を 7時間 前へ
    d = json.loads(yt.cache_path().read_text(encoding="utf-8"))
    d["at"] = (now - dt.timedelta(hours=yt.CACHE_TTL_H + 1)).isoformat()
    yt.cache_path().write_text(json.dumps(d), encoding="utf-8")
    monkeypatch.setattr(yt, "_ALL", None)
    svc.calls.clear()
    yt.all_videos()
    assert "playlistItems.list" in svc.calls


def test_refresh_Trueは写しが在っても引き直す(cache_dir, monkeypatch):
    now = yt.now_jst()
    svc = _Svc([_item("A", _utc(now - dt.timedelta(hours=3)))])
    monkeypatch.setattr(yt, "svc", lambda: svc)
    yt.all_videos()
    svc.calls.clear()
    yt.all_videos(refresh=True)
    assert "playlistItems.list" in svc.calls


def test_tokenが替わったら別の写し(cache_dir, monkeypatch):
    now = yt.now_jst()
    svc = _Svc([_item("A", _utc(now - dt.timedelta(hours=3)))])
    monkeypatch.setattr(yt, "svc", lambda: svc)
    yt.all_videos()
    p_a = yt.cache_path()
    monkeypatch.setenv("YT_REFRESH_TOKEN", "tok-B")
    assert yt.cache_path() != p_a
    monkeypatch.setattr(yt, "_ALL", None)
    svc.calls.clear()
    yt.all_videos()
    assert "playlistItems.list" in svc.calls, "別の token なのに前のチャンネルの写しを読んだ"


def test_刻の過ぎた予約はpublicと読み_未来の予約は予約のまま(cache_dir, monkeypatch):
    now = yt.now_jst()
    passed = _utc(now - dt.timedelta(minutes=30))
    future = _utc(now + dt.timedelta(hours=5))
    svc = _Svc([_item("P", _utc(now - dt.timedelta(hours=3)), privacy="private", publish_at=passed),
                _item("F", _utc(now - dt.timedelta(hours=3)), privacy="private", publish_at=future)])
    monkeypatch.setattr(yt, "svc", lambda: svc)
    yt.all_videos()
    # 引いた直後は YouTube の privacy のまま（P も private）
    assert [v["id"] for v in yt.scheduled_all()] == ["P", "F"]
    # 別のプロセスが写しから読むと、刻の過ぎた P は public
    monkeypatch.setattr(yt, "_ALL", None)
    assert [v["id"] for v in yt.published()] == ["P"]
    assert [v["id"] for v in yt.scheduled_all()] == ["F"]


def test_uploadの直後に写しへ足す_きょうの枠に数える(cache_dir, monkeypatch):
    now = yt.now_jst()
    svc = _Svc([_item("A", _utc(now - dt.timedelta(days=3)))])
    monkeypatch.setattr(yt, "svc", lambda: svc)
    yt.all_videos()
    at = (now + dt.timedelta(hours=2)).replace(second=0, microsecond=0)
    yt.cache_add({"id": "NEW", "title": "new", "privacy": "private", "publish_at": _utc(at),
                  "published_at": _utc(now), "duration": "", "views": 0, "views_absent": False,
                  "likes": 0, "comments": 0})
    assert [v["id"] for v in yt.today_lineup(date=at.date())] == ["NEW"]
    # 別のプロセスからも見える
    monkeypatch.setattr(yt, "_ALL", None)
    assert [v["id"] for v in yt.today_lineup(date=at.date())] == ["NEW"]


def test_cache_patchは行を直して_無ければFalse(cache_dir, monkeypatch):
    now = yt.now_jst()
    svc = _Svc([_item("A", _utc(now - dt.timedelta(hours=3)))])
    monkeypatch.setattr(yt, "svc", lambda: svc)
    yt.all_videos()
    assert yt.cache_patch("A", title="改題") is True
    assert yt.cache_patch("ZZZ", title="x") is False
    monkeypatch.setattr(yt, "_ALL", None)
    assert yt.all_videos()[0]["title"] == "改題"


def test_refresh_statsは1単位で写しの再生を新しくする(cache_dir, monkeypatch):
    now = yt.now_jst()
    svc = _Svc([_item("A", _utc(now - dt.timedelta(hours=3)), views="5")], stats={"A": {"viewCount": "900"}})
    monkeypatch.setattr(yt, "svc", lambda: svc)
    yt.all_videos()
    svc.calls.clear()
    n = yt.refresh_stats(["A", "not-there"])
    assert n == 1
    assert svc.calls == ["videos.list:statistics"]
    assert yt.published()[0]["views"] == 900
    # 写しにも書き戻っている（別のプロセスが読む）
    monkeypatch.setattr(yt, "_ALL", None)
    assert yt.all_videos()[0]["views"] == 900


def test_refresh_statsは写しが無ければ撃たない(cache_dir, monkeypatch):
    svc = _Svc([])
    monkeypatch.setattr(yt, "svc", lambda: svc)
    monkeypatch.setattr(yt, "_ALL", None)
    assert yt.refresh_stats(["A"]) == 0
    assert svc.calls == []


def test_cache_invalidateで引き直す(cache_dir, monkeypatch):
    now = yt.now_jst()
    svc = _Svc([_item("A", _utc(now - dt.timedelta(hours=3)))])
    monkeypatch.setattr(yt, "svc", lambda: svc)
    yt.all_videos()
    yt.cache_invalidate()
    assert not yt.cache_path().exists()
    svc.calls.clear()
    yt.all_videos()
    assert "playlistItems.list" in svc.calls


def test_pytestの下で置き場を明示しなければ読まない書かない(tmp_path, monkeypatch):
    monkeypatch.delenv("STUDIO_YT_CACHE_DIR", raising=False)
    monkeypatch.setattr(yt, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(yt, "_ALL", None)
    now = yt.now_jst()
    svc = _Svc([_item("A", _utc(now - dt.timedelta(hours=3)))])
    monkeypatch.setattr(yt, "svc", lambda: svc)
    yt.all_videos()
    assert not list(tmp_path.iterdir()), "検査の偽の返りが写しに書かれた"
    monkeypatch.setattr(yt, "_ALL", None)
    svc.calls.clear()
    yt.all_videos()
    assert "playlistItems.list" in svc.calls
