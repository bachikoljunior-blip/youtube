"""`quota.py --pace` は **役ごとに**模型を印字すること（2026-09-10 05:2x・optimizer・Opus）。

09/07 08:1x から親は1周に **2体** を違う模型で立てる（`ROLE_TIER`: hourly ＝ Fable・
optimizer ＝ Opus）。ところが `--pace` は `sub_model(now)` を**役なし**で呼んでおり、
**どの回も「fable」1つ**しか出ていなかった —— Opus で走っている optimizer が、
自分の模型を「fable」と読む行。`docs/spawn_prompt.md` はサブに
「実物は `quota.py --pace`」と言うので、**サブが自分について読む行**である。
§8 の「嘘の印字がサブの本文の土台になる」と同じ族。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import quota  # noqa: E402


def test_サブの役は_ROLE_TIER_から引く():
    """名簿を2か所に持たない —— 役を1つ足す日に `ROLE_TIER` だけを直せばよい。"""
    roles = quota.sub_roles()
    assert "hourly" in roles and "optimizer" in roles
    # 親自身の回（`owner-*`）はサブではない。
    assert not any(r.startswith("owner-") for r in roles)


def test_役ごとに模型が分かれる():
    """**これが本体** —— 2つの役が同じ模型に潰れていたら、印字は嘘になる。"""
    got = {r: quota.sub_model(None, r)[0] for r in quota.sub_roles()}
    assert got["optimizer"] == "opus", got          # `ROLE_TIER` の `other` は枠に依らず Opus
    assert len(set(got.values())) > 1, got          # 役なしの1つに潰れていない


def test_役を足したら印字も増える():
    """`ROLE_TIER` に1行 足すと `sub_roles()` が拾うこと（§5 の「役を1つ足す」の覆る条件）。"""
    before = len(quota.sub_roles())
    quota.ROLE_TIER["third"] = "other"
    try:
        assert "third" in quota.sub_roles()
        assert len(quota.sub_roles()) == before + 1
    finally:
        del quota.ROLE_TIER["third"]
    assert len(quota.sub_roles()) == before
