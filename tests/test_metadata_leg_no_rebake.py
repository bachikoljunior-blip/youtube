"""**落ちた脚が metadata だけなら、焼き直しを命じないこと。**

09-04 に踏んだ輪（`src/daily_pick.METADATA_LEGS` の註に実測）:
焼き 55〜90分 に対し直しは 21〜30分 間隔で降るので、焼き上がった控えは必ず古い。
`pick_legs` は `draft_legs` に追いつけず、`untreated_slot_block` が
`ahead_sweep` を永久に焼き直しへ倒しました —— 09-04 だけで動画ID 4つ、
ship 65件・`--moves` 0以外 0件。

**覆る条件**: 前提「外の作り方を写した長尺」が閉じて `OUTSIDE_LONG_RULE` を
使わなくなったら、この検査ごと落とすこと（`config/hypotheses.yaml`）。
"""
from __future__ import annotations

import json

from src import daily_pick as dp

TOPICS = [{"id": "t1", "style": "outside_long"}]
CUR = {"topic": "t1", "video_id": "vid1", "form": "長尺"}


def _script(title: str) -> dict:
    return {"title": title, "segments": [], "chapters": [],
            "thumbnail_kicker": "k", "thumbnail_line1": "a", "thumbnail_line2": "b"}


def test_metadata_only_は_metadata_だけを_True():
    assert dp.metadata_only(["(4) 題・サムネ"]) is True
    assert dp.metadata_only(["(1) 冒頭", "(4) 題・サムネ"]) is False
    assert dp.metadata_only(["(1) 冒頭"]) is False
    # 1本も落ちていないときは「その場で直せ」でもない
    assert dp.metadata_only([]) is False


def test_門は_metadata_だけのとき_焼き直しを命じない(monkeypatch, tmp_path):
    monkeypatch.setattr(dp, "pick_legs", lambda v, **k: (["(4) 題・サムネ"], None))
    monkeypatch.setattr(dp, "treated_count", lambda f, **k: (0, 36))
    line = dp.untreated_slot_block(CUR, topics=TOPICS, queue=tmp_path)
    assert line, "脚が落ちているのだから、門は黙らないこと"
    assert "焼き直しは要りません" in line
    assert "枠までに脚を通してから置きます" not in line


def test_門は_焼かないと直らない脚では_焼き直しを命じる(monkeypatch, tmp_path):
    monkeypatch.setattr(dp, "pick_legs", lambda v, **k: (["(1) 冒頭"], None))
    monkeypatch.setattr(dp, "treated_count", lambda f, **k: (0, 36))
    line = dp.untreated_slot_block(CUR, topics=TOPICS, queue=tmp_path)
    assert "枠までに脚を通してから置きます" in line
    assert "焼き直しは要りません" not in line


def test_直しの中身は手元の台本から出る(monkeypatch, tmp_path):
    monkeypatch.setattr(dp, "pick_legs", lambda v, **k: (["(4) 題・サムネ"], None))
    monkeypatch.setattr(dp, "draft_legs", lambda t: ([], None))
    d = tmp_path / "data" / "scripts"
    d.mkdir(parents=True)
    (d / "t1.script.json").write_text(
        json.dumps(_script("【60歳以上の方へ】直った題"), ensure_ascii=False),
        encoding="utf-8")
    monkeypatch.setattr(dp, "ROOT", tmp_path)
    plan = dp.metadata_fix_plan(CUR, topics=TOPICS, queue=tmp_path)
    assert plan is not None
    assert plan["title"] == "【60歳以上の方へ】直った題"
    assert plan["video_id"] == "vid1"


def test_手元の台本も落ちていれば直しは出ない(monkeypatch, tmp_path):
    """写す先が無いなら、焼き直しでも metadata でもなく **台本を直すのが先**。"""
    monkeypatch.setattr(dp, "pick_legs", lambda v, **k: (["(4) 題・サムネ"], None))
    monkeypatch.setattr(dp, "draft_legs", lambda t: (["(4) 題・サムネ"], None))
    assert dp.metadata_fix_plan(CUR, topics=TOPICS, queue=tmp_path) is None
