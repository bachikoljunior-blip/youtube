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
