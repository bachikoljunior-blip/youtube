"""`status` は、旧作りの本が枠に並んでいたら名指しで言うこと（2026-09-08 23:0x・hourly・Fable）。

実測: 旧 `reschedule.py` が 09/02 に打った publishAt が 09/08 23:00 JST に発火し、`Yy7GmcGoQ6I` が
public になった。`status` は一日中「23:00 private  Yy7GmcGoQ6I」を きょうの枠に印字していたが、
印が無いので 3周の hourly が読み飛ばした。印字はしていた ＝ 見えていなかったのは「それが旧作りで、
戻すべき物だ」という判断のほう。だから判断ごと印字する。
"""
from studio import cli


def _v(vid, privacy):
    return {"id": vid, "title": vid, "privacy": privacy, "publish_at": None, "published_at": "", "views": 0, "likes": 0}


ROWS = [{"event": "scheduled", "id": "2026-09-08-x", "video_id": "STUDIO"},
        {"event": "measured", "id": "OLDPUB"}]


def test_studioの本には印を付けない():
    assert cli.lineup_mark(_v("STUDIO", "private"), cli.studio_video_ids(ROWS)) == ""
    assert cli.lineup_mark(_v("STUDIO", "public"), cli.studio_video_ids(ROWS)) == ""


def test_旧作りの予約は_戻せと言う():
    m = cli.lineup_mark(_v("Yy7GmcGoQ6I", "private"), cli.studio_video_ids(ROWS))
    assert "!!" in m and "private へ戻す" in m


def test_旧作りの公開ずみは_印だけ():
    m = cli.lineup_mark(_v("OLDPUB", "public"), cli.studio_video_ids(ROWS))
    assert "旧作り" in m and "!!" not in m


def test_台帳のscheduledだけを数える():
    # measured しか無い ID は studio の本ではない（旧作りの本も measure される）
    assert cli.studio_video_ids(ROWS) == {"STUDIO"}
