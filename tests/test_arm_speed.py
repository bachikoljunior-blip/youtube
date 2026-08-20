"""**腕が動く速さ**（`src/arm_speed`）と、**軌跡**（`scripts/eta.trajectory`）の検査。

## この検査が守っているもの（2026-08-20 18:xx・オーナー指示）

> 腕とやらをそう設定した時に達成がいつになるって予測じゃなくて、じゃあその腕を
> そうなるまでにどれくらい時間がかかるのかとか予測しないとダメだよ。**特定条件の
> 予測じゃなくて、実際にどういう軌跡を辿るか予測して、いつ達成かを予測するんだよ。**

**写しに戻ったら落ちる形**にしてあります。具体的には次の3つ:

1. 印字する日付が `plan()["target_date"]`（＝腕が1ミリも動かない未来）の写しに
   戻ったら落ちる
2. 腕の速さを、実測ではなく定数で置いたら落ちる
3. 天井を外して、実在しない倍率まで腕を伸ばしたら落ちる（**1日25本と同じ穴**）
"""
from __future__ import annotations

import importlib.util
import math
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location("eta_mod", ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eta)

from src import arm_speed  # noqa: E402


# --- 標本（**手元のファイルを読まないこと**。読むと回ごとに答えが変わります）-------

def _doc(rows: list[dict], confirmed: list[dict] | None = None) -> dict:
    return {"hypotheses": rows, "confirmed": confirmed or []}


def _h(lever: str, effect: float, day: str, outcome: str = "falsified") -> dict:
    return {"claim": f"{lever} を動かす", "closed_on": day, "outcome": outcome,
            "lever": lever, "effect": effect, "verdict": "…"}


# --- 1. 当たりの数え方 -------------------------------------------------------------

def test_当たりは_outcome_ではなく_effect_で数える():
    """**反証条件を満たさなかっただけの前提は、1日の再生を1倍も増やしていません。**

    実例: 「ショートを固めて出すと後から出したものに露出が回らない」は
    `survived` ですが、**増産が効かないと確かめた**だけで、倍率は 1.0 です。
    `outcome` で数えると、ここが「当たり」に化けます。
    """
    rows = arm_speed.closed(_doc([
        _h("density", 1.0, "2026-08-05", outcome="survived"),
        _h("per_video", 1.85, "2026-08-07", outcome="mixed"),
    ]))
    assert [r["hit"] for r in rows] == [False, True]


def test_伸び幅は平均ではなく中央値():
    """**創業時の1件が桁で外れています**（形をショートへ替えて 256倍）。

    平均だと、その1件だけで全部の腕の速さが決まります。
    """
    rows = arm_speed.closed(_doc([
        _h("rpm", 256.0, "2026-08-04", outcome="survived"),
        _h("per_video", 1.85, "2026-08-07", outcome="mixed"),
        _h("density", 1.75, "2026-08-15", outcome="survived"),
    ]))
    a = arm_speed.arm("per_video", rows, today=date(2026, 8, 20))
    assert a["gain"] == pytest.approx(1.85), "平均（86.5倍）になっています"


def test_回転の速さは_閉じた日の間隔ではない():
    """**実験は同時に走ります。** 08/20 に4件が閉じても、間隔は 0日 ではありません。"""
    rows = arm_speed.closed(_doc([
        _h("per_video", 1.0, "2026-08-04"),
        _h("per_video", 1.0, "2026-08-20"),
        _h("per_video", 1.0, "2026-08-20"),
        _h("per_video", 1.0, "2026-08-20"),
    ]))
    th = arm_speed.throughput(rows, today=date(2026, 8, 20))
    assert th["days"] == 16.0 and th["per_day"] == pytest.approx(4 / 16)


# --- 2. 速さの形 --------------------------------------------------------------------

def test_速さは_確率と伸び幅と回転の掛け算():
    """**定数で置いたら落ちます。** 3つのどれを動かしても、速さが動くこと。"""
    base = [_h("density", 1.0, "2026-08-04"), _h("density", 1.0, "2026-08-06"),
            _h("density", 2.0, "2026-08-08", outcome="survived")]
    a = arm_speed.arm("density", arm_speed.closed(_doc(base)), today=date(2026, 8, 20))
    # p = 1/3、gain = 2.0、回転 = 3/16、配分 = 1.0
    assert a["p"] == pytest.approx(1 / 3)
    assert a["gain"] == pytest.approx(2.0)
    assert a["focus_rate"] == pytest.approx((1 / 3) * math.log(2) * (3 / 16))
    assert a["rate"] == pytest.approx(a["focus_rate"] * 1.0)


def test_当たりが増えたら速くなる():
    slow = arm_speed.arm("density", arm_speed.closed(_doc(
        [_h("density", 1.0, "2026-08-04"), _h("density", 1.0, "2026-08-06"),
         _h("density", 2.0, "2026-08-08", outcome="survived")])), today=date(2026, 8, 20))
    fast = arm_speed.arm("density", arm_speed.closed(_doc(
        [_h("density", 2.0, "2026-08-04", outcome="survived"),
         _h("density", 2.0, "2026-08-06", outcome="survived"),
         _h("density", 2.0, "2026-08-08", outcome="survived")])), today=date(2026, 8, 20))
    assert fast["rate"] > slow["rate"] * 2


def test_1件も当てていない腕は_全体で代用したと言う():
    """**黙って埋めないこと。** 薄い腕ほど、自信ありげに見えます。"""
    rows = arm_speed.closed(_doc([
        _h("per_video", 1.85, "2026-08-07", outcome="mixed"),
        _h("per_video", 1.0, "2026-08-10"), _h("per_video", 1.0, "2026-08-12"),
        _h("sub_rate", 1.0, "2026-08-08"), _h("sub_rate", 1.0, "2026-08-20"),
    ]))
    a = arm_speed.arm("sub_rate", rows, today=date(2026, 8, 20))
    assert a["source"] == "全体で代用"
    assert a["n"] == 2 and a["hits"] == 0
    assert any("この腕だけの実績" in x for x in a["missing"])


def test_速さが出ない腕は_無いと言う():
    """**無い数を 0 や既定値で埋めないこと**（`blocking` と同じ作り）。"""
    rows = arm_speed.closed(_doc([_h("per_video", 1.0, "2026-08-04"),
                                  _h("per_video", 1.0, "2026-08-06"),
                                  _h("per_video", 1.0, "2026-08-08")]))
    a = arm_speed.arm("per_video", rows, today=date(2026, 8, 20))
    assert a["rate"] is None
    assert any("当たったときの伸び幅" in x for x in a["missing"])
    assert arm_speed.days_to_factor(a, 2.0) == math.inf


# --- 3. 天井（**1日25本と同じ穴**）----------------------------------------------------

def test_天井のある腕は_それ以上伸びない():
    a = {"rate": 0.1, "cap": 1.5}
    assert arm_speed.factor_at(a, 1_000) == pytest.approx(1.5)
    assert arm_speed.days_to_factor(a, 2.0) == math.inf
    assert arm_speed.days_to_factor(a, 1.5) == pytest.approx(math.log(1.5) / 0.1)


def test_実在する幅で腕を止める_1日110525本を歩かない():
    """**最初の版は、実測の速さのまま 224日ぶん外挿していました。**

    `density` を **×4,421**（＝1日 110,525本）まで伸ばして、その上に日付を
    乗せていた —— **同じ回に外した「1日25本」と、まったく同じ欠陥**です。
    """
    a0 = {"per_video_now": 923.0, "sub_rate": 0.000443}
    caps = eta.physical_caps(a0, density=25)
    assert caps["density"]["factor"] == pytest.approx(eta.UPLOAD_CAP_PER_DAY / 25)
    assert caps["density"]["measured"] is True
    # 登録率は**測った天井ではありません**。そう言うこと
    assert caps["sub_rate"]["measured"] is False
    # `rpm` は 2026-08-20 22:4x に**実測へ入れ替えました**（`src/rpm_mix.py`）。
    # ここには `assert caps["rpm"]["measured"] is False` と書いてあり、
    # **据え置きの ×100（¥2,000 ÷ ¥20）を「そう言えていれば正しい」としていました。**
    # 言えているだけでは足りません —— 測った点があれば measured、
    # **無いときだけ据え置きへ落ち、`why` に「まだ測っていません」と出る**こと。
    if eta.rpm_mix.last():
        assert caps["rpm"]["measured"] is True
    else:
        assert caps["rpm"]["measured"] is False
        assert "まだ測っていません" in caps["rpm"]["why"]
    arms = eta._capped_arms(a0)
    assert arms["density"]["cap"] <= eta.UPLOAD_CAP_PER_DAY / 25 + 1e-9
    for lever, a in arms.items():
        assert a["cap"] is None or a["cap"] > 1.0, lever


def test_実測の天井のほうが低ければ_そちらを採る():
    """`config/hypotheses.yaml` の `ceiling`（1本あたり再生）が効いていること。

    **値は台帳から読みます。写さないこと**（2026-08-21 03:2x）—— ここには
    `1447` が直に書いてあり、天井を n=7 の最大から測り直した回に落ちました。
    **守りたいのは「台帳の天井が効いていること」で、その日の数字ではありません。**
    """
    recorded = eta.arm_speed.ceilings()["per_video"]["value"]
    arms = eta._capped_arms({"per_video_now": 923.0, "sub_rate": 0.000443})
    pv = arms["per_video"]
    assert pv["cap"] == pytest.approx(recorded / 923.0)
    assert pv["cap_measured"] is True
    assert pv["cap"] < 3.0, "ショートのままで「1本あたり3倍」を歩いています"


# --- 4. 連敗 --------------------------------------------------------------------------

def test_連敗は数えるが_それだけで確率を書き換えない():
    """**3連続で外している最中に「次は当たる」前提の軌跡を出したら嘘になります。**

    それでも、当たりの間隔の実測（1/p）の中に収まっているうちは
    「外れすぎ」とは言わないこと —— 言えば、こんどは逆向きの嘘になります。
    """
    rows = arm_speed.closed(_doc(
        [_h("density", 2.0, "2026-08-04", outcome="survived")]
        + [_h("per_video", 1.0, f"2026-08-{d:02d}") for d in (6, 8, 10, 12)]))
    st = arm_speed.miss_streak(rows)
    assert st["n"] == 4
    assert st["expected_gap"] == pytest.approx(5.0)
    assert st["unusual"] is False
    # **連敗を数えるだけでは「外れすぎ」になりません。** 外れを足すと p も下がり、
    # 当たりの間隔もその場で伸びるからです（20連敗・1当たりでも p=1/21 ＝ 間隔21件）。
    # 「外れすぎ」と言えるのは、**よく当たってきた腕が急に黙ったとき**だけです。
    lucky = arm_speed.closed(_doc(
        [_h("density", 2.0, f"2026-08-{d:02d}", outcome="survived") for d in range(4, 14)]
        + [_h("per_video", 1.0, "2026-08-15") for _ in range(8)]))
    st2 = arm_speed.miss_streak(lucky)
    assert st2["n"] == 8 and st2["expected_gap"] == pytest.approx(18 / 10)
    assert st2["unusual"] is True


def test_欄の無い閉じた前提は_取りこぼしとして数える():
    doc = _doc([_h("per_video", 1.0, "2026-08-04"),
                {"claim": "古い行", "verdict": "外れ"}])
    assert arm_speed.unreadable(doc) == 1


# --- 5. 実物（`config/hypotheses.yaml`）---------------------------------------------

def test_閉じた前提には4つの欄が入っている():
    """**散文の verdict からは、機械が確率も伸び幅も読めません。**"""
    import yaml

    doc = yaml.safe_load((ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
    missing = [h["claim"][:24] for h in doc["hypotheses"]
               if h.get("verdict") is not None
               and not all(h.get(k) is not None for k in ("closed_on", "outcome", "lever", "effect"))]
    assert not missing, f"閉じているのに欄の無い前提: {missing}"
    assert arm_speed.unreadable(doc) == 0
    rows = arm_speed.closed(doc)
    assert len(rows) >= 15, "閉じた前提が減っています（欄を消していませんか）"
    assert any(r["hit"] for r in rows), "当たりが1件も無い ＝ 速さが出ません"
