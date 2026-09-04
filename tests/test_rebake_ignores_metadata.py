"""**題・サムネ・別案だけが違う台本で、20分の動画を焼き直さないこと。**

実測（2026-09-04・最適化の回）: commit `abade351`（11:45）は
`title_alternatives`（**次に題を替えるときの候補**。動画にも YouTube にも
1文字も出ない）**だけ**を直しており、それだけで `script_sha` が変わり、
`rebake_plan_for()` が 55〜90分 の焼き直しを命じました。
同じ日、この形で動画IDが **4つ** 捨てられ、ship 65件・`--moves` 0以外 **0件**。

**覆る条件**: `src/pipeline.py` が `title` か `thumbnail_*` をコマに焼き込むように
なったら、その欄は `RENDER_IGNORED_FIELDS` から外すこと（本当に焼き直しが要ります）。
"""
from __future__ import annotations

import json

from scripts import ahead_sweep as sweep

BASE = {
    "title": "【60歳以上の方へ】題",
    "title_alternatives": ["別案1", "別案2"],
    "thumbnail_kicker": "年180万・75歳まで",
    "thumbnail_line1": "差は2052万円",
    "thumbnail_line2": "何歳から",
    "segments": [{"narration": "あ"}, {"narration": "い"}],
    "chapters": [], "tags": [], "description_body": "", "first_comment": "",
}


def _j(**over) -> str:
    d = dict(BASE)
    d.update(over)
    return json.dumps(d, ensure_ascii=False)


def test_題だけ違えば焼き直しの字は同じ():
    a = sweep.script_sha(_j(), render_only=True)
    b = sweep.script_sha(_j(title="【年金の受け取り方】題"), render_only=True)
    assert a == b, "題は動画に入りません。焼き直しの判定に使わないこと"


def test_別案だけ違えば焼き直しの字は同じ():
    """`abade351` が実際に踏んだ形。**この1欄で 90分 が命じられていました。**"""
    a = sweep.script_sha(_j(), render_only=True)
    b = sweep.script_sha(_j(title_alternatives=["別案1"]), render_only=True)
    assert a == b


def test_サムネの文字だけ違えば焼き直しの字は同じ():
    a = sweep.script_sha(_j(), render_only=True)
    b = sweep.script_sha(_j(thumbnail_kicker="75歳まで生きた場合・年180万円"),
                         render_only=True)
    assert a == b


def test_ナレーションが違えば焼き直しの字は変わる():
    """**焼かないと直らない側は、必ず焼き直すこと。**"""
    a = sweep.script_sha(_j(), render_only=True)
    b = sweep.script_sha(_j(segments=[{"narration": "あ"}, {"narration": "う"}]),
                         render_only=True)
    assert a != b


def test_既定は全部の欄を見る():
    """`render_only=False` は今までどおり —— 控えの同一性など、別の用途が読む字。"""
    a = sweep.script_sha(_j())
    b = sweep.script_sha(_j(title="別の題"))
    assert a != b


# ---------------------------------------------------------------------------
# **「焼き直しでは直らない差」は2種類あります**（2026-09-04 21:5x に分けた）
#
#   `METADATA_FIELDS`    YouTube には出る（題・サムネ）  → `metadata_fix.py`（50単位）
#   `LOCAL_ONLY_FIELDS`  どこにも出ない（別案）          → **撃つ手はありません**
#
# 分ける前は1つの集合だったので、`rebake_plan()` は差が `title_alternatives` だけの
# 回にも「**題かサムネだけが違います** —— `metadata_fix.py`（50単位）」と命じていました。
# 実測 21:5x の `GFvAcxvDmYM`: 手元と控えの差は `title_alternatives` **1欄だけ**で
# 題もサムネも一致 —— そのとおり撃てば **50単位 使って YouTube 側は1文字も変わりません。**
# ---------------------------------------------------------------------------


#: **道具が受け取る本**（`metadata_fix_plan` が中身を返す側）。
#: 既定でこちらを渡します —— この節が測っているのは「**どの欄が違えば撃つ手が在るか**」で、
#: 「**その本を道具が受け取るか**」は別の門です（`tests/test_metadata_fix_reachable.py`）。
def _accepts(vid: str, topic: str) -> dict:
    return {"video_id": vid, "topic": topic, "title": "題"}


def _plan(stash: str, draft: str, *, plan_call=_accepts) -> dict:
    return sweep.rebake_plan(
        cur={"video_id": "vid1", "topic": "t"}, stash_text=stash, draft_text=draft,
        draft_newer=True, attempted=False, scheduled=False, slot_at=None,
        now=__import__("datetime").datetime.now(sweep.JST),
        meta_fix_plan_call=plan_call)


def test_2つの集合は重ならず_和が焼き直しの無視欄():
    assert not (sweep.METADATA_FIELDS & sweep.LOCAL_ONLY_FIELDS)
    assert sweep.RENDER_IGNORED_FIELDS == sweep.METADATA_FIELDS | sweep.LOCAL_ONLY_FIELDS


def test_題が違えば_metadata_fix_を名指しする():
    why = _plan(_j(), _j(title="【年金の受け取り方】題"))["why"]
    assert "焼いても変わらない" in why
    assert "metadata_fix.py vid1" in why
    assert "title" in why


def test_別案だけが違えば_撃つ手は無いと言うこと():
    """**50単位 を丸損させないこと。**

    `title_alternatives` は動画にも YouTube にも出ないので、`metadata_fix.py` を
    撃っても1文字も変わりません。**「焼き直しでは直らない」＝「metadata を撃て」では
    ありません。**
    """
    why = _plan(_j(), _j(title_alternatives=["別案1"]))["why"]
    assert "焼いても変わらない" in why
    assert "metadata_fix.py" not in why or "撃つ手はありません" in why
    assert "撃つ手はありません" in why
    assert "title_alternatives" in why


def test_題と別案の両方が違えば_metadata_fix_を名指しする():
    """片方でも YouTube に出る欄が違えば、撃つ手は在ります。

    **ただし「在る」の条件が1つ増えました**（2026-09-05 01:3x）——
    下の `test_道具が受け取らない本には撃つ手を出さない` を見ること。
    """
    why = _plan(_j(), _j(title="別の題", title_alternatives=["別案1"]))["why"]
    assert "metadata_fix.py vid1" in why
    assert "撃つ手はありません" not in why


def test_道具が受け取らない本には撃つ手を出さない():
    """**欄が違うこと ＝ 撃つ手が在ること、ではありません。**（2026-09-05 01:3x に踏んだ）

    この節はもともと「**片方でも YouTube に出る欄が違えば、撃つ手は在ります**」を
    測っていました。**それは偽でした** —— `metadata_fix.py` の門は
    `metadata_only(pick_legs(vid))` で、**4脚 全通の本を受け取りません**
    （`metadata_only([])` は `False`）。

    実測 `GFvAcxvDmYM`（09/05 の枠の本）: 4脚 全通・`thumbnail_line2` だけが違う。
    画面は `metadata_fix.py` を命じ、撃つと「脚は全部 ○ です」で終わりました。
    """
    why = _plan(_j(), _j(thumbnail_line2="別の字"), plan_call=lambda v, t: None)["why"]
    # **撃つ手（走らせる行）が出ていないこと。** 名前は「撃っても直しません」の説明に出ます。
    assert "scripts/metadata_fix.py" not in why
    assert "撃っても直しません" in why
    # **物差しの無い欄では、50単位 を使う理由が無いことまで言うこと。**
    assert "50単位 を使う理由になりません" in why


def test_changed_fields_は読めなければ黙る():
    assert sweep._changed_fields("{", "{}") == set()
    assert sweep._changed_fields("[]", "{}") == set()
    assert sweep._changed_fields(_j(), _j(title="ち")) == {"title"}
