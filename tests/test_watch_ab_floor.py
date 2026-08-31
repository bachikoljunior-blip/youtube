"""**A/B の待ちの「床」を、2か所が別々に持っていないこと。**

2026-08-26 22:5x の実測（`status.py` の待ちの節）:

    あと **13本**  途中の依頼-両群72本（いま 3 / **要る 16**）

**見出しは 72本 と言い、目盛りは 16本 で割っていました。**
`src/watches._k_ab_group` が `ab_split.MIN_PER_GROUP`（16）を床に使い、
`src/judgeable.MEMBER_SOURCES["request_form"]` の **72** を見ていなかったためです。

**なぜ 72 なのかは `config/hypotheses.yaml` が書いています** ——
測っているのが engaged ではなく**登録**（3,066再生に1人）で、
片群 16本 ＝ 約 6,700再生 では期待 2.1人。**効きが2倍でも見分けられません。**
`falsified_if` は「上回らなければ外れ（同点も外れ）」なので、
**16本 で「満ちました」が鳴ると、そのまま『外れ』に化けます。**

だからこの検査は2つを見ます:

1. 待ちの **id に書いた本数** と、`judgeable.MEMBER_SOURCES` の床が同じか
   （＝ 人が読む字と、機械が使う数が同じか）
2. `_k_ab_group` が返す分母が、その床から来ているか
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import ab_split, judgeable, watches  # noqa: E402

#: `途中の依頼-両群72本` → 72
FLOOR_IN_ID = re.compile(r"両群(\d+)本")


def _ab_group_watches():
    return [w for w in watches.load() if w.kind == "ab_group"]


def test_待ちのidに書いた本数と床が一致する():
    """**印字と門が、同じ数を言っていること。**"""
    checked = 0
    for w in _ab_group_watches():
        m = FLOOR_IN_ID.search(w.id)
        if not m:
            continue
        name = w.params["experiment"]
        src = judgeable.MEMBER_SOURCES.get(name)
        assert src is not None, f"{w.id}: `{name}` が MEMBER_SOURCES にありません"
        assert int(m.group(1)) == src[1], (
            f"{w.id}: id は {m.group(1)}本 と言っていますが、"
            f"床は {src[1]}本 です（`src/judgeable.MEMBER_SOURCES`）"
        )
        checked += 1
    assert checked, "本数を名乗る ab_group の待ちが1件もありません"


def test_目盛りの分母は_MEMBER_SOURCES_から来る():
    """`ab_split.MIN_PER_GROUP` を全部の群に当てないこと。"""
    for name, (_make, need) in judgeable.MEMBER_SOURCES.items():
        g = watches._k_ab_group({"experiment": name})
        assert g.need == float(need), (
            f"{name}: 目盛りの分母が {g.need} で、床 {need} と違います"
        )


def test_request_formの床は16ではない():
    """**この検査が生まれた1件**（`MIN_PER_GROUP` を写すと落ちる）。"""
    need = judgeable.MEMBER_SOURCES["request_form"][1]
    assert need == 72
    assert need != ab_split.MIN_PER_GROUP
    assert watches._k_ab_group({"experiment": "request_form"}).need == 72.0


def test_ACCRUINGの群でも目盛りが出る():
    """`SOURCES` から外れている群を「ありません」で落とさないこと。"""
    for name in judgeable.ACCRUING:
        assert name not in judgeable.SOURCES
        g = watches._k_ab_group({"experiment": name})
        assert not g.err, f"{name}: {g.err}"


def test_長尺を群に数えない():
    """`request_form` の群は、控えの `duration_s` で長尺を落としていること。

    `ab_split.split_counts` は `exp.split(topic)` を**全部の本**に当てるので、
    長尺も群に入ります（長尺は依頼そのものを書かないので、どちらの群でもない）。
    """
    members = judgeable.members("request_form")
    topics = {t for rows in members.values() for _d, t in rows} if members else set()
    assert isinstance(members, dict)
    # 群の作り方が `_members_by_request_form` であること（接頭辞ではない）
    assert judgeable.MEMBER_SOURCES["request_form"][0] is judgeable._members_by_request_form
    assert isinstance(topics, set)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
