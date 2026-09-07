"""公開ずみの本を「上げた順」で選ばないこと（2026-09-07 16:4x・optimizer・Opus）。

実測の穴: `recent_videos(60)` は uploads（**上げた順**）の先頭 60本 しか見ない。
08/16〜08/19 に上げて private のまま置いてあった旧作りの本に、あとから publishAt が
付いて公開されると、その本は uploads の 690番目あたりに居るので**永久に入らない**。
09/05 に 5本・09/06 に 8本・09/07 に 1本 が そうして公開されていたのに、
`status` の「きょうの枠」にも「直近 公開 10本」にも出ず、`measure` は 1行も
台帳に書いていなかった（＝ §7 の判定が、同じ日に出た本を1本も見ていなかった）。
"""
import datetime as dt

from studio import yt


def _utc(t):
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _v(vid, published, privacy="public", publish_at=None):
    return {"id": vid, "title": vid, "privacy": privacy, "publish_at": publish_at,
            "published_at": published, "duration": "", "views": 0, "likes": 0}


def test_古く上げて今日公開された本が公開順に出る(monkeypatch):
    """uploads の末尾に居る（＝古く上げた）本でも、公開が新しければ先頭に来る。"""
    now = yt.now_jst()
    old_upload_new_publish = _v("OLDUP", _utc(now - dt.timedelta(hours=8)))
    new_upload_old_publish = _v("NEWUP", _utc(now - dt.timedelta(days=20)))
    # all_videos は「上げた順」なので、新しく上げたほうが先に並んでいる
    monkeypatch.setattr(yt, "all_videos", lambda *a, **k: [new_upload_old_publish, old_upload_new_publish])
    assert [v["id"] for v in yt.published()] == ["OLDUP", "NEWUP"]


def test_きょうの枠は古く上げた本も数える(monkeypatch):
    """`schedule` の「1日1本」の門は today_lineup で数えるので、ここが漏れると素通りする。"""
    now = yt.now_jst()
    today9 = now.replace(hour=9, minute=0, second=0, microsecond=0)
    rows = [_v("NEWUP", _utc(now - dt.timedelta(days=20))), _v("OLDUP", _utc(today9))]
    monkeypatch.setattr(yt, "all_videos", lambda *a, **k: rows)
    monkeypatch.setattr(yt, "scheduled_all", lambda: [])
    assert [v["id"] for v in yt.today_lineup()] == ["OLDUP"]


def test_齢で絞れる(monkeypatch):
    now = yt.now_jst()
    rows = [_v("FRESH", _utc(now - dt.timedelta(hours=5))), _v("STALE", _utc(now - dt.timedelta(days=30)))]
    monkeypatch.setattr(yt, "all_videos", lambda *a, **k: rows)
    assert [v["id"] for v in yt.published(24 * 7)] == ["FRESH"]


def test_上げた順で先頭を切る関数を残さない():
    """`recent_videos` に戻ったら、この穴がそのまま開き直る。"""
    assert not hasattr(yt, "recent_videos"), "公開ずみは yt.published() で選ぶこと（上げた順で切らない）"
