"""`quota.py --pace` は **役ごとに**模型を印字すること（2026-09-10 05:2x・optimizer・Opus）。

09/07 08:1x から親は1周に **2体** を違う模型で立てる（`ROLE_TIER`: hourly ＝ Fable・
optimizer ＝ Opus）。ところが `--pace` は `sub_model(now)` を**役なし**で呼んでおり、
**どの回も「fable」1つ**しか出ていなかった —— Opus で走っている optimizer が、
自分の模型を「fable」と読む行。`docs/spawn_prompt.md` はサブに
「実物は `quota.py --pace`」と言うので、**サブが自分について読む行**である。
§8 の「嘘の印字がサブの本文の土台になる」と同じ族。
"""
import sys
from datetime import datetime, timedelta, timezone
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


def _fake_fable(monkeypatch, est):
    """「Fable のみ」の推定を **その場で決める**（台帳と、きょうの枠に依らせない）。

    **2026-09-11 11:0x（optimizer・Opus）にこの形へ変えた理由**は、下の 2件 の docstring。
    """
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(quota, "fable_estimate", lambda *a, **kw: {
        "gauge": {"pct": 86.0, "at": now, "resets": now + timedelta(hours=21)},
        "rate": 0.79, "rate_source": "measured", "est": est,
        "exhaust_at": now + timedelta(hours=1), "stale_hours": 0.5})


def test_役ごとに模型が分かれる_Fableの枠がまだ在るとき(monkeypatch):
    """**これが本体** —— 2つの役が同じ模型に潰れていたら、印字は嘘になる。

    **枠を引数で決めること**（2026-09-11 11:0x）: もとは `quota.sub_model(None, role)` を
    **台帳のいまの数で**呼び、「2つ が同じ模型なら赤」と書いてありました。
    ところが **2つ が opus に揃うのは、この形が最初から狙っている着地**です
    （METHOD の枠の行・`FABLE_CAP_PCT`：「Fable のみ」が 100% に着いたら `hourly` も Opus）。
    **09/11 10:3x にその着地が実際に来て、この検査が赤くなりました** ——
    道具は 1行 も壊れていません。**「きょうの枠」を不変条件として書いた検査**だった、
    という 1点だけが欠陥です（同じ周の `tests/test_studio_settle_views.py` の
    焼き込んだ日付と**同じ族**・§5「教訓の形 4つ目」）。
    """
    _fake_fable(monkeypatch, est=50.0)              # Fable の枠はまだ半分
    got = {r: quota.sub_model(None, r)[0] for r in quota.sub_roles()}
    assert got == {"hourly": "fable", "optimizer": "opus"}, got


def test_Fableが上限に着いたら_2つとも_opus(monkeypatch):
    """**着地のほう**（`FABLE_CAP_PCT`・METHOD の枠の行）。

    「Fable のみ」が上限に着いたら `hourly` も Opus ＝ **2つ が揃うのが正しい**。
    ここを「潰れている」と読まないこと —— 上の検査と対で置いてあります。

    **陽性対照を撃った結果（正直に書く・§5 教訓の形 3つ目）**: この着地は門が **2つ** 守っており
    （`sub_model` の `est >= FABLE_CAP_PCT` と `role_model` の `est + per_sub >= FABLE_CAP_PCT`）、
    **片方だけ殺してもこの検査は落ちません**。**2つ とも殺すと落ちます**（撃って確かめた）。
    ＝ この 1件 は「片方の門が消えた」を捕まえません。その 1つ ずつは
    `tests/test_role_model.py` と `tests/test_quota_fable_cost_per_sub.py` が持っています。
    """
    _fake_fable(monkeypatch, est=quota.FABLE_CAP_PCT)
    got = {r: quota.sub_model(None, r)[0] for r in quota.sub_roles()}
    assert set(got.values()) == {"opus"}, got


def test_役が読まれていること(monkeypatch):
    """**「役なしの1つに潰れていない」を、枠に依らせずに言う。**

    上の 2件 は枠の両端を見ますが、`sub_model` が `role` を**そもそも読んでいるか**は
    枠が真ん中のときにしか出ません。ここが 1点 ぶんの本体です。
    """
    _fake_fable(monkeypatch, est=50.0)
    assert quota.sub_model(None, "hourly")[0] != quota.sub_model(None, "optimizer")[0]


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
