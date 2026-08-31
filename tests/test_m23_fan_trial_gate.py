"""**M23 の着手条件（登録者 50人）を、跨いだ日に機械が言うこと。**（2026-08-31・最適化の回）

`docs/MEANS.md` M23 は 2026-08-30 に着手条件を書き直しました:

    ~~登録者が 10,000人 を超えた回~~   ← 外れた判定1 の上に立っていた
    → **登録者が 50人 を超えた回**に、加入率と単価の**実測を1件 立てる**

そして M23 自身が「この機械が自分で検出できるか」の節でこう書いています ——

> 登録者数は `scripts/status.py` が毎回 出します（`subs_net`）。
> **だから 50人 は検出できます。**

**「検出できる」と「検出している」は別です。** 2026-08-31 に `grep` したら、
**`50` はコードにも `config/` にも1件もありませんでした** —— 跨いだ日に、
誰も何も言いません。`src/day_cap.py` が名指ししている
「**機構は正しく、読まれる側だけが偽**」の形です。

そのうえ `scripts/eta.py` は「**M23 の着手条件は、その外れた判定の上に立っています**」
と印字し続けていました。**M23 は前日に直っており、その一文のほうが古い**（結論より
先に根拠が腐る形）。

## この回に自分で撃った数（`data/eta.jsonl` 404点・12.5日・API 0単位）

    全期間   9 → 23人  **1.116 人/日**
    直近7日 19 → 23人  **0.593 人/日**  → 50人 まで **46日**
    直近3日 22 → 23人  **0.336 人/日**  → 50人 まで **80日**

**減速しています。** M23 の本文は「いまの伸び（0.89人/日）で **30日 以内に
満ちます**」と書いていますが、**その 0.89 はもう出ていません。**

## 覆る条件

- M23 が着手条件の数を変えたら、`eta.M23_FAN_TRIAL_SUBS` を合わせること
  （出どころは M23 の地の文で、こちらは**承知のうえの写し**です —— 写さないと
  跨いだ日に誰も何も言いません）。下の `test_the_number_matches_means_md` が、
  その2つがずれたら赤くなります。
- 登録者が 50人 を超えたら、印字は「満ちています」へ切り替わります
  （`test_says_so_when_crossed`）。**そのとき M23 の「着手しない」は期限切れです。**
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import eta  # noqa: E402


def test_the_number_matches_means_md():
    """**写しがずれたら赤くすること。** 出どころは `docs/MEANS.md` M23。"""
    means = (ROOT / "docs" / "MEANS.md").read_text(encoding="utf-8")
    body = means[means.find("### M23."):]
    assert body, "`docs/MEANS.md` に M23 の見出しがありません"
    assert re.search(rf"{eta.M23_FAN_TRIAL_SUBS}\s*人", body), (
        f"`eta.M23_FAN_TRIAL_SUBS = {eta.M23_FAN_TRIAL_SUBS}` が "
        "M23 の本文に出てきません。**どちらかが動いています。**"
        "M23 を正として合わせること")
    assert eta.M23_FAN_TRIAL_SUBS < eta.FAN_SUBS_GATE, (
        "着手条件が門より後ろにあります（M23 の理由は「門の 1/10 ＝ "
        "加入率が測れる最小の標本」）")


def test_says_how_far_and_names_the_arm():
    """まだのときは **あと何人・何日**と、引く腕を言うこと。"""
    lines = eta.m23_fan_trial_lines({"subs_net": 23}, {"subs_per_day": 0.58})
    assert lines, "何も言っていません"
    t = "\n".join(lines)
    assert f"{eta.M23_FAN_TRIAL_SUBS}人" in t
    assert "あと 27人" in t, t
    assert "MEANS.md" in t, "出どころを言っていません"


def test_says_so_when_crossed():
    """**跨いだ日に、そう言うこと。** ここが黙ると、この一式は無意味です。"""
    t = "\n".join(eta.m23_fan_trial_lines({"subs_net": eta.M23_FAN_TRIAL_SUBS},
                                          {"subs_per_day": 0.58}))
    assert "満ちています" in t, t
    assert "`rpm`" in t, "引く腕を言っていません（分子が増える手なので `per_video` ではない）"
    assert "per_video" in t, "**間違えやすい側**を名指ししていません"


def test_observed_rate_is_read_from_the_ledger_not_the_model():
    """**模型と観測を混ぜないこと。** 食い違い自体が情報です。"""
    obs = eta.observed_subs_rate()
    if obs is None:
        return  # 台帳が薄い環境
    assert obs["days"] > 0 and obs["n"] >= 2
    # 観測が模型と別の欄で出ていること（同じ数を2回 数えていない）
    t = "\n".join(eta.m23_fan_trial_lines({"subs_net": 23}, {"subs_per_day": 0.58}))
    if obs["rate"] > 0:
        assert "観測" in t and "模型" in t, t


def test_the_stale_sentence_is_gone():
    """`eta.py` が、M23 の**前日の姿**を語り続けていないこと。"""
    src = (ROOT / "scripts" / "eta.py").read_text(encoding="utf-8")
    # **註の中で引用するのは構いません**（何を直したかの記録）。
    #     見るのは「**印字される側**に残っていないか」だけ。
    live = "\n".join(ln for ln in src.splitlines()
                     if not ln.lstrip().startswith("#"))
    assert "その外れた判定の上に立っています" not in live, (
        "M23 は 2026-08-30 に着手条件を書き直しています。"
        "**この一文のほうが古い。**まだ印字しています")
