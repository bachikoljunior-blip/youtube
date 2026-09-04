"""**先読みの門が開く前に、試す形（長尺）が「次の未決の日」まで取るのを止める**
（`src.daily_pick.probe_hold` ／ `record()` の中の呼び口）。**API 0単位。**

## なぜ要るか（2026-09-04・最適化の回）

`outside_long_readout()` は 齢24h に届いていない試す本について
「**次の未決の日は、それまで決めないこと**」と印字します。**散文で、誰も止めませんでした。**
実測 `data/daily_pick.jsonl`（`at` 順）: 09-03 02:03 〜 09-04 21:26 の決めは **17回 連続で長尺**、
うち 09-05 の決めは試す本 `1huadpEk6HY` が **齢 9h**（門は 齢24h）のときに書かれています。
同じ画面が同じ回に「取った枠から、まだ 1本も 48h の観測が出ていません —— 枠だけ減って、
前提は 1件も進んでいません（0本／2本）」と刷っていました。`data/eta.jsonl` の 再生/日(7d) は
6,299（08-25）→ 943（09-04）＝ **-85%**。

**止めるのは「次の未決の日」だけ**です。下の4本が、その境目を実物で押さえます。
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import pytest

from src import daily_pick

JST = timezone(timedelta(hours=9))
TOPICS = [{"id": "long-probe", "style": "outside_long"},
          {"id": "s-plain", "style": ""}]


def _uploaded(tmp_path, pub: str):
    p = tmp_path / "uploaded.jsonl"
    p.write_text(json.dumps({"at": pub, "video_id": "PROBE1", "topic": "long-probe"},
                            ensure_ascii=False) + "\n", encoding="utf-8")
    return p


def test_門が開く前は次の未決の日を長尺で取れない(tmp_path):
    """試す本は 齢12h（門は 齢24h）。**その翌日**を長尺で決めようとしたら止まる。"""
    up = _uploaded(tmp_path, "2026-09-04T00:00:00Z")
    now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    msg = daily_pick.probe_hold("長尺", date(2026, 9, 6), now=now,
                                topics=TOPICS, uploaded_path=up)
    assert msg, "門が開く前の『次の未決の日』は止まること"
    assert "PROBE1" in msg and "09/05 09:00" in msg, msg
    with pytest.raises(ValueError):
        daily_pick.record("長尺", "long-probe", "18本目 2回", day=date(2026, 9, 6),
                          now=now, path=tmp_path / "picks.jsonl",
                          topics=TOPICS, uploaded_path=up)


def test_試す本そのものの日は止めない(tmp_path):
    """止めるのは**先の枠**だけ。試す本が出た日（と、それ以前）は 1つも動かしません。"""
    up = _uploaded(tmp_path, "2026-09-04T00:00:00Z")
    now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    assert daily_pick.probe_hold("長尺", date(2026, 9, 4), now=now,
                                 topics=TOPICS, uploaded_path=up) == ""
    row = daily_pick.record("長尺", "long-probe", "きょうの1本 2回", day=date(2026, 9, 4),
                            now=now, path=tmp_path / "picks.jsonl",
                            topics=TOPICS, uploaded_path=up)
    assert row["form"] == "長尺"


def test_門が開いたあとは止めない_ショートも止めない(tmp_path):
    """齢24h を越えたら `outside_long_readout` の門が読めるので、ここは黙ります。
    **既定の形（ショート）は、どの日でも一度も止めません。**"""
    up = _uploaded(tmp_path, "2026-09-04T00:00:00Z")
    later = datetime(2026, 9, 5, 1, 0, tzinfo=timezone.utc)      # 齢25h
    assert daily_pick.probe_hold("長尺", date(2026, 9, 6), now=later,
                                 topics=TOPICS, uploaded_path=up) == ""
    early = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    assert daily_pick.probe_hold("ショート", date(2026, 9, 6), now=early,
                                 topics=TOPICS, uploaded_path=up) == ""
    daily_pick.record("ショート", "s-plain", "既定の形 1049回", day=date(2026, 9, 6),
                      now=early, path=tmp_path / "picks.jsonl",
                      topics=TOPICS, uploaded_path=up)


def test_数字で上書きできる_行に残る(tmp_path):
    """**固定は目標の本文だけ。** 止めは数字で越えられ、越えた印が行に残ります。"""
    up = _uploaded(tmp_path, "2026-09-04T00:00:00Z")
    now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    p = tmp_path / "picks.jsonl"
    with pytest.raises(ValueError):        # 数字の無い言い訳は通さない
        daily_pick.record("長尺", "long-probe", "理由 1件", day=date(2026, 9, 6), now=now,
                          path=p, anyway="なんとなく", topics=TOPICS, uploaded_path=up)
    row = daily_pick.record("長尺", "long-probe", "理由 1件", day=date(2026, 9, 6), now=now,
                            path=p, anyway="外の p90 647,526回 を取りに行く",
                            topics=TOPICS, uploaded_path=up)
    assert row["anyway"] and "647,526" in row["anyway"]


def test_写しは決めではないので止めない(tmp_path):
    """`replace_video()` の `carry`（焼き直しが ID を写しただけの行）は決めではありません ——
    ここで止めると、**焼き直しが決めを新しい ID へ写せなくなります**。"""
    up = _uploaded(tmp_path, "2026-09-04T00:00:00Z")
    now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    row = daily_pick.record("長尺", "long-probe", "焼き直し: 1本", day=date(2026, 9, 6),
                            now=now, path=tmp_path / "picks.jsonl",
                            kind=daily_pick.PICK_KIND_CARRY,
                            topics=TOPICS, uploaded_path=up)
    assert daily_pick.pick_kind(row) == daily_pick.PICK_KIND_CARRY


# ---------------------------------------------------------------------------
# **札ではなく実物で「試す本」を選ぶ**（2026-09-04 22:2x に踏んだ・`treated_probe`）
#
# 上の4本は `style: outside_long` の**札だけ**で試す本を選んでいました。実測（同じ回に撃った）:
#   pick_legs('1huadpEk6HY')  = ['(2) 章・締め', '(4) 題・サムネ', '(5) 間合い']  ← 4脚中 3脚 ✗
#   draft_legs('zaishoku-2026-62man') = 同じ3脚 ✗   ← 手元の台本も外の型に上げていない
#   treated_count('長尺')     = (0, 36)             ← 実物で数えると処置は 1本も公開ずみでない
# 札だけの本が 24h の門を握り、次の未決の日を止めていました ——
# **前提を閉じられない本の数字を待って、閉じられる本（4脚○）の枠を止めていた。**
# ---------------------------------------------------------------------------

def test_処置でない本は次の未決の日を止めない(tmp_path, monkeypatch):
    """**控えが読めた上で脚が✗** の本は前提を閉じられないので、閂を握れません。"""
    up = _uploaded(tmp_path, "2026-09-04T00:00:00Z")
    now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(daily_pick, "treated_probe",
                        lambda vid, **kw: ("no", "外の型の脚が 3本 通っていません"))
    assert daily_pick.probe_hold("長尺", date(2026, 9, 6), now=now,
                                 topics=TOPICS, uploaded_path=up) == ""
    row = daily_pick.record("長尺", "long-probe", "処置は 0本／36本", day=date(2026, 9, 6),
                            now=now, path=tmp_path / "picks.jsonl",
                            topics=TOPICS, uploaded_path=up)
    assert row["form"] == "長尺"


def test_控えが読めないだけでは閂を外さない(tmp_path, monkeypatch):
    """`"unknown"` は証拠ではありません —— **推測で止めない**の裏返しで、**推測で外さない**。"""
    up = _uploaded(tmp_path, "2026-09-04T00:00:00Z")
    now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(daily_pick, "treated_probe",
                        lambda vid, **kw: ("unknown", "台本の控えが読めません"))
    assert daily_pick.probe_hold("長尺", date(2026, 9, 6), now=now,
                                 topics=TOPICS, uploaded_path=up), "読めないだけでは外さないこと"


def test_treated_probe_は実物の脚で三値を返す(tmp_path, monkeypatch):
    """`pick_legs` の `(脚, 読めない理由)` を **`yes` / `no` / `unknown` に写す**こと。

    **`unknown` と `no` を混ぜないのが要点**です —— 「控えが読めない」と
    「読めた上で脚が✗」は、閂の外し方が違います（`no` だけが外す）。
    """
    monkeypatch.setattr(daily_pick, "pick_legs",
                        lambda vid, **kw: ([], "台本の控えが読めません"))
    assert daily_pick.treated_probe("X")[0] == "unknown"
    monkeypatch.setattr(daily_pick, "pick_legs",
                        lambda vid, **kw: (["(4) 題・サムネ"], None))
    state, why = daily_pick.treated_probe("X")
    assert state == "no" and "(4) 題・サムネ" in why, (state, why)
    monkeypatch.setattr(daily_pick, "pick_legs", lambda vid, **kw: ([], None))
    assert daily_pick.treated_probe("X")[0] == "yes"
    monkeypatch.undo()
    # 本を名指していない決めは、控えを読むまでもなく `unknown`
    assert daily_pick.treated_probe("", queue=tmp_path)[0] == "unknown"


def test_処置でない本は先読みの門を握らない(tmp_path, monkeypatch):
    """`outside_long_readout` の判定も、札ではなく実物で。**処置でない本の判定は `None`**。"""
    up = _uploaded(tmp_path, "2026-09-04T00:00:00Z")
    views = tmp_path / "views.jsonl"
    views.write_text(json.dumps({"id": "PROBE1", "hours": 26, "views": 999},
                                ensure_ascii=False) + "\n", encoding="utf-8")
    now = datetime(2026, 9, 5, 4, 0, tzinfo=timezone.utc)          # 齢28h
    monkeypatch.setattr(daily_pick, "treated_probe",
                        lambda vid, **kw: ("no", "外の型の脚が 3本 通っていません"))
    lines, verdict = daily_pick.outside_long_readout(now, topics=TOPICS,
                                                     uploaded_path=up, views_path=views)
    assert verdict is None, "処置でない本の 999回 で次の日の形を決めないこと"
    assert any("この本は処置ではありません" in x for x in lines), lines
