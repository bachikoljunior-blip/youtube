"""**命じる前に、その道具が受け取るかを見ること。**（2026-09-05 01:3x にこの回が踏んだ）

`rebake_plan()` は「控えと台本で `METADATA_FIELDS` の欄が違う」で
`metadata_fix.py`（50単位）を命じていました。**その道具の門は別のもの**で
（`daily_pick.metadata_fix_plan` ＝ `metadata_only(pick_legs(vid))`）、
**4脚 全通の本は受け取りません**（`metadata_only([])` は `False`）。

実測 `GFvAcxvDmYM`: 4脚 全通・`thumbnail_line2` だけが違う → 命じられたとおり撃つと
「は直せません —— 脚は全部 ○ です」で終わる。**この回が1手 落としました。**
"""
from __future__ import annotations

from scripts import ahead_sweep as a


def test_受け取る本には撃つ手が出る():
    line = a.metadata_diff_line("V1", "t", ["title"],
                                plan_call=lambda v, t: {"video_id": v})
    assert "scripts/metadata_fix.py V1" in line
    assert "撃っても直しません" not in line


def test_受け取らない本には撃つ手を出さない():
    line = a.metadata_diff_line("V2", "t", ["thumbnail_line2"],
                                plan_call=lambda v, t: None)
    assert "scripts/metadata_fix.py" not in line
    assert "撃っても直しません" in line


def test_物差しの無い欄は五十単位を使う理由にならないと言う():
    line = a.metadata_diff_line("V3", "t", ["thumbnail_line2"],
                                plan_call=lambda v, t: None)
    assert "物差しの無い欄: thumbnail_line2" in line
    assert "50単位 を使う理由になりません" in line


def test_物差しの在る欄は名指しして帯の実測へ送る():
    line = a.metadata_diff_line("V4", "t", ["title", "thumbnail_kicker"],
                                plan_call=lambda v, t: None)
    assert "物差しの在る欄が違っています: title" in line
    assert "niche_ceiling.py --titles" in line
    assert "scripts/retitle.py V4" in line
    assert "物差しの無い欄: thumbnail_kicker" in line


def test_物差しの在る欄は題だけ():
    # サムネの3欄を「測れる」に足すなら、その回が実測を1つ持って来ること。
    assert a.MEASURED_METADATA_FIELDS == frozenset({"title"})
    assert a.MEASURED_METADATA_FIELDS < a.METADATA_FIELDS


def test_門が撃てない時は撃つ手を出さない():
    def boom(v, t):
        raise RuntimeError("控えが読めません")

    acts, why = a.metadata_fix_acts("V5", "t", plan_call=boom)
    assert acts is False
    assert "門を撃てません" in why


def test_実物_GFvAcxvDmYM_は受け取られない():
    """**この回が実際に踏んだ本。** 4脚 全通なので、道具は受け取りません。

    覆る条件: この本が公開されて次の本に入れ替わったら、この検査は
    「決めの本が控えに無い」で同じ False を返します（どちらでも撃つ手は出ない）。
    """
    acts, _ = a.metadata_fix_acts("GFvAcxvDmYM", "nenkin-uketorikata-65-70-75-handan")
    assert acts is False


def test_rebake_plan_が同じ本で撃つ手を出さない():
    import json
    from datetime import datetime, timedelta, timezone

    JST = timezone(timedelta(hours=9))
    stash = json.dumps({"scenes": [{"say": "あ"}], "thumbnail_line2": "控え"},
                       ensure_ascii=False)
    draft = json.dumps({"scenes": [{"say": "あ"}], "thumbnail_line2": "台本"},
                       ensure_ascii=False)
    out = a.rebake_plan(cur={"video_id": "V6", "topic": "t"},
                        stash_text=stash, draft_text=draft, draft_newer=True,
                        attempted=False, scheduled=True,
                        slot_at=datetime(2026, 9, 5, 9, tzinfo=JST),
                        now=datetime(2026, 9, 5, 1, tzinfo=JST),
                        meta_fix_plan_call=lambda v, t: None)
    assert out["do"] is False
    assert "scripts/metadata_fix.py" not in out["why"]
    assert "撃っても直しません" in out["why"]
