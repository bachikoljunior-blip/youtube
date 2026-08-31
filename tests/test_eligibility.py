"""**段3 が「待つだけの段」に戻らないこと。**

2026-08-31 まで、`scripts/eta.py` の到達日は **P(承認)=1.0** で解かれていました
（`grep -c 'policy' scripts/eta.py` が 0）。門1・門2a の数字だけを見ていて、
**審査の合否そのものが式に入っていなかった**ということです。
落ちたら到達日は「遅れる」ではなく**来ない**ので、ここは上振れ側の唯一の穴でした。

**故障を注入して発火を確かめます**（`docs/GOAL.md`「発火したことのない検査は検査ではない」）。
"""
from __future__ import annotations

import copy

import pytest

from src import eligibility


@pytest.fixture()
def live() -> dict:
    return eligibility._read()


# --- いまの構成が、直したままであること -----------------------------------

def test_live_config_has_no_findings(live):
    """**いまの `config/channel.yaml` に、落ちる材料が残っていないこと。**"""
    s = eligibility.state(live)
    assert s["clean"], (
        "config/channel.yaml に収益化審査で落ちる材料が戻っています: "
        + "; ".join(f["id"] + " @ " + f["where"] for f in s["findings"])
    )
    assert s["cost_days"] == 0


# --- 故障の注入①: 人間の経歴を名乗り直す ----------------------------------

@pytest.mark.parametrize("persona", [
    "元・事業会社の経理／人事で、制度を実務で回してきた立場から解説する。",
    "元・事業会社の経理として、制度を解説します。",
    "現役の税理士が、手取りの計算を解説します。",
    "社労士として10年やってきた経験から話します。",
])
def test_credential_claim_fires(live, persona):
    """**経歴の主張が戻ったら、必ず発火すること。**"""
    cfg = copy.deepcopy(live)
    cfg["channel"]["persona"] = persona
    ids = [f["id"] for f in eligibility.findings(cfg)]
    assert "human_credential_claim" in ids, f"素通りした: {persona!r}"


def test_credential_claim_costs_days(live):
    """発火したぶんが、**日数**になって出てくること（印字だけで終わらせない）。"""
    cfg = copy.deepcopy(live)
    cfg["channel"]["persona"] = "元・事業会社の経理／人事で、実務で回してきた立場から解説する。"
    assert eligibility.cost_days(cfg) > eligibility.cost_days(live)


# --- 故障の注入②: 合成音声の開示を消す ------------------------------------

def test_missing_disclosure_fires(live):
    """**開示を消したら発火すること。**"""
    cfg = copy.deepcopy(live)
    cfg["publish"]["footer"] = "※ 一般的な情報提供です。個別の助言ではありません。"
    ids = [f["id"] for f in eligibility.findings(cfg)]
    assert "no_synthetic_disclosure" in ids


def test_disclosure_wordings_all_count(live):
    """開示の言い方を変えても、**開示は開示として通ること**（誤発火しない）。"""
    for footer in ["※ ナレーションは合成音声です。",
                   "※ 音声合成を使用しています。",
                   "※ 台本はAIが下書きしています。",
                   "※ 図表は自動生成しています。"]:
        cfg = copy.deepcopy(live)
        cfg["publish"]["footer"] = footer
        ids = [f["id"] for f in eligibility.findings(cfg)]
        assert "no_synthetic_disclosure" not in ids, f"誤発火: {footer!r}"


# --- 日数の出どころが、勘ではなく掛け算であること --------------------------

def test_cost_is_p_times_published_reapply_days(live):
    """`cost_days == p_deny × REAPPLY_COST_DAYS`。**しきい値を勘で置かないこと。**"""
    cfg = copy.deepcopy(live)
    cfg["channel"]["persona"] = "元・事業会社の経理として解説します。"
    cfg["publish"]["footer"] = "※ 個別の助言ではありません。"
    s = eligibility.state(cfg)
    assert s["cost_days"] == pytest.approx(
        s["p_deny"] * eligibility.REAPPLY_COST_DAYS, abs=0.05)
    # 60日 = 却下後30日の再申請待ち + 2回目の審査30日（どちらも公表値）
    assert eligibility.REAPPLY_COST_DAYS == 60


def test_p_deny_is_never_certain(live):
    """**推測を確信として印字しないこと。** 上限は 0.9 で止める。"""
    cfg = copy.deepcopy(live)
    cfg["channel"]["persona"] = "元・事業会社の経理として、現役の税理士として解説します。"
    cfg["publish"]["footer"] = ""
    assert eligibility.p_deny(cfg) <= 0.9
    assert eligibility.state(cfg)["measured"] is False


# --- 段3 が、この項を実際に読んでいること ---------------------------------

def test_eta_stage3_consumes_eligibility():
    """`scripts/eta.py` の段3 が `eligibility` を読み、`cost_days` を足していること。"""
    from pathlib import Path
    src = Path(__file__).resolve().parent.parent / "scripts" / "eta.py"
    text = src.read_text(encoding="utf-8")
    assert "eligibility.state()" in text, "段3 が eligibility を読んでいません"
    assert 'elig["cost_days"]' in text, "段3 が cost_days を日数に足していません"
    assert "待つだけの段**\"" not in text, "段3 が「待つだけの段」に戻っています"
