"""`scripts/eta.py` —— **到達日の入力が、満たせない前提になっていないか。**

## この検査が守っているもの（2026-08-20 16:0x・オーナー指示 原文）

> 25は物理的に不可ならそれを予測に使うのはどうなの？
> 分析して制作に活かして視聴回数などを上げることが予測に使えることじゃない？

そのとおりでした。直す前の `plan()` は、段1（登録者1,000人の門）を
**`a["days_subs_at"][25]`** の1行で解いていました。この `25` は
`PLAN_PUBLISH_PER_DAY` ——「**予約を詰め直したらこうなる**」という置き方で、
定数の脇の註にもそう書いてあります。**作れる本数ではありません。**
実測は在庫37本・未使用の節0件で、**25本/日 は 1.5日で尽きます。**
段1 が段3 を、段3 が段4 を押すので、**到達予測の日付は、まるごと
「満たせない前提」の上に乗っていました。**

そして `_report_supply` は「保ちません」と印字するだけで、その節の註に
「**この節は日付を動かしません**」と書いてありました ——
**足りないと分かっていて、日付には反映していなかった**わけです。

**ここで固定するのは3つです。**

1. **段1 が「作る速さの実測」から解かれること**（`25` の写しに戻ったら落ちる）
2. **段4（月20万）が、在庫を食い終わった先の密度で立つこと**
   （1.5日ぶんの在庫で、1か月ぶんの収入を数えない）
3. **1本あたり再生を上げる腕が、到達日を動かすこと**
   （動かないなら、それは「予測に使える」形になっていない）
"""
from __future__ import annotations

import importlib.util
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from src import supply

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("eta_supply_mod", ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eta)

from src import day_cap  # noqa: E402


# --- **この file は「供給 vs 詰め方」を測っています。天井は主題ではありません** ---
#
# 2026-08-21 16:2x に、段1 へもう1枚 天井が入りました —— **1日に再生が付く本数の
# 上限**（`src/day_cap.py`。08/20 は 25本 公開して #11から先の15本が 0〜3再生）。
# 実測の 10本/日 はここの合成データ（作る速さ 13〜400本/日）より**下**なので、
# かぶせると**どの筋も上限10に潰れ**、「作る速さから出ているか／詰め方が効くか」
# という**この file の discriminator そのものが消えます。**
#
# **隠しているのではありません。** 天井は `tests/test_eta_day_cap.py` が持ちます。
# ここでは縛らせない、と**書いてから**外します。
@pytest.fixture(autouse=True)
def _天井は主題ではない(monkeypatch):
    monkeypatch.setattr(day_cap, "cap", lambda *a, **k: eta.UPLOAD_CAP_PER_DAY)


JST = timezone(timedelta(hours=9))


def _metrics(**kw) -> dict:
    """**手で作った1点。** 実データに寄りかからないこと（`test_supply.py` の教訓）。"""
    m = {
        "views_7d": 8_800, "views_28d": 20_300,
        "subs_gained_28d": 9, "subs_net": 9,
        "long_hours_365": 0.1, "shorts_views_90d": 22_515,
        "views_per_video": 923, "median_views_per_video": 1_041,
        "long_per_video": 2, "long_videos_28d": 5, "long_views_28d": 11,
    }
    m.update(kw)
    return m


def _supply(rate: float, stock: int = 37, novel: int = 494, thin: bool = False) -> dict:
    return {"stock": stock, "novel": novel, "rate_per_day": rate,
            "rate": {"per_day": rate, "thin": thin}, "measured": True,
            "sweep_age_hours": 1.0}


# ------------------------------------------------- 供給の側（src/supply.py）

def test_出せる本数は2本の直線の低いほう():
    """在庫があるうちは詰め方が上限、食い終わったら作る速さが上限。

        在庫 37本・作る速さ 13本/日・詰め方 25本/日
        t=1日:  min(25, 37+13) = 25    ← 詰め方が上限
        t=10日: min(250, 167)  = 167   ← 作る速さが上限
    """
    kw = dict(stock=37, rate_per_day=13.0, plan_density=25.0)
    assert supply.published_by(1, **kw) == pytest.approx(25)
    assert supply.published_by(10, **kw) == pytest.approx(167)
    assert supply.published_by(0, **kw) == 0.0


def test_要る本数から日を解く():
    """`days_for` は2本の直線それぞれを解いて**遅いほう**（探索は要らない）。

        need=2,422本・在庫37・速さ13本/日・詰め方25本/日
        詰め方の側 2422/25 = 96.9日 ／ 作る速さの側 (2422-37)/13 = 183.5日
        → **183.5日**（遅いほう）
    """
    d = supply.days_for(2_422, stock=37, rate_per_day=13.0, plan_density=25.0)
    assert d == pytest.approx((2_422 - 37) / 13.0)
    assert d > 2_422 / 25.0
    # 在庫だけで足りるなら、詰め方の側しか効かない
    assert supply.days_for(20, stock=37, rate_per_day=13.0,
                           plan_density=25.0) == pytest.approx(20 / 25.0)


def test_作る速さが0なら在庫の外へは出られない():
    assert supply.days_for(1_000, stock=37, rate_per_day=0.0,
                           plan_density=25.0) >= 36_500


def test_作る速さはテーマ総数の差から出す():
    t0 = datetime(2026, 8, 20, 6, 0, tzinfo=JST)
    ps = [{"at": (t0 + timedelta(hours=h)).isoformat(timespec="seconds"),
           "topics_total": 400 + h} for h in (0, 12, 24)]
    r = supply.make_rate(ps)
    assert r["per_day"] == pytest.approx(24.0)      # 24時間で +24本
    assert r["thin"] is False


def test_2つの物差しを1つの並びに混ぜない():
    """**実測で踏んだ欠陥です**（2026-08-20 16:1x）。

    復元（在庫＋投稿済み）は 417、正本（`topics_total`）は 437 で、
    **同じ瞬間なのに 20本ちがいました。** 混ぜると、実際には1本も増えていない
    2.7時間が「**1日 183本**」という速さになります。
    """
    t0 = datetime(2026, 8, 20, 13, 26, tzinfo=JST)
    ps = [
        {"at": t0.isoformat(timespec="seconds"), "stock": 36},
        {"at": (t0 + timedelta(hours=1)).isoformat(timespec="seconds"), "stock": 37},
        # ここで正本に切り替わる。**値は 20本 大きい**
        {"at": (t0 + timedelta(hours=2)).isoformat(timespec="seconds"),
         "stock": 37, "topics_total": 437},
    ]
    s, basis = supply.created_series(ps)
    assert basis.startswith("復元")
    assert len(s) == 2                          # 正本の点は混ざっていないこと
    # 復元の側は控えの本数を足し戻すので絶対値は動きます。**差のほうを見ること。**
    assert s[1][1] - s[0][1] == 1
    r = supply.make_rate(ps)
    assert r["per_day"] == pytest.approx(24.0)  # 1時間で +1本
    assert r["basis"].startswith("復元")


def test_正本の点が2つ貯まったら自動で切り替わる():
    t0 = datetime(2026, 8, 20, 13, 0, tzinfo=JST)
    ps = [
        {"at": t0.isoformat(timespec="seconds"), "stock": 36},
        {"at": (t0 + timedelta(hours=2)).isoformat(timespec="seconds"),
         "stock": 37, "topics_total": 437},
        {"at": (t0 + timedelta(hours=26)).isoformat(timespec="seconds"),
         "stock": 40, "topics_total": 461},
    ]
    s, basis = supply.created_series(ps)
    assert basis == "topics_total"
    assert [v for _, v in s] == [437, 461]
    assert supply.make_rate(ps)["per_day"] == pytest.approx(24.0)


def test_点が1つなら速さを名乗らない():
    """**None は 0 ではありません。**「測っていない」と「増えていない」は別。"""
    r = supply.make_rate([{"at": "2026-08-20T06:00:00+09:00", "topics_total": 400}])
    assert r["per_day"] is None


def test_窓が短すぎるときも速さを名乗らない():
    t0 = datetime(2026, 8, 20, 6, 0, tzinfo=JST)
    ps = [{"at": (t0 + timedelta(minutes=m)).isoformat(timespec="seconds"),
           "topics_total": 400 + m} for m in (0, 5)]
    assert supply.make_rate(ps)["per_day"] is None


# ------------------------------------------------- 予測の側（scripts/eta.py）

def test_段1は25の写しではなく作る速さから出る():
    """**これが落ちたら、到達日がまた「満たせない前提」に戻っています。**"""
    m = _metrics()
    a = eta.analyse(m)
    g1 = eta.solve_gate1(a, density=eta.PLAN_PUBLISH_PER_DAY, supply=_supply(13.0))
    assert g1["measured"] is True
    # 25本/日 で解いた日数（＝写し）と**同じであってはならない**
    assert g1["days"] != pytest.approx(a["days_subs_at"][eta.PLAN_PUBLISH_PER_DAY])
    assert g1["days"] > a["days_subs_at"][eta.PLAN_PUBLISH_PER_DAY]
    assert g1["density_sustained"] == pytest.approx(13.0)


def test_作る速さが詰め方を上回るなら詰め方が効く():
    """**供給を入れたら必ず遅くなる、ではありません。** 上限は詰め方の側。"""
    m = _metrics()
    a = eta.analyse(m)
    g1 = eta.solve_gate1(a, density=25, supply=_supply(400.0))
    assert g1["days"] == pytest.approx(a["days_subs_at"][25], rel=1e-6)
    assert g1["density_sustained"] == pytest.approx(25.0)


def test_供給が読めない回は未検証だと言う():
    """読めなくても回は止めない。ただし**黙って 25 を使わない**。"""
    m = _metrics()
    a = eta.analyse(m)
    g1 = eta.solve_gate1(a, density=25, supply=None)
    assert g1["measured"] is False
    pl = eta.plan(m, a, supply=None)
    assert pl["gate1"]["measured"] is False
    行 = [l for l in eta._report_plan(m, a, pl) if "未検証の前提" in l]
    assert 行, "供給が読めない回に、断りが出ていません"


def test_段4は在庫を食い終わった先の密度で立つ():
    """月20万は**1か月ぶんの合計**なので、1.5日ぶんの在庫では数えない。"""
    m = _metrics()
    a = eta.analyse(m)
    pl = eta.plan(m, a, supply=_supply(13.0))
    assert pl["density_month"] == pytest.approx(13.0)
    # 天井も持続する密度のほうで立っていること
    assert pl["ceiling_day"] == pytest.approx(a["per_video_now"] * 13.0)


def test_供給を入れると到達日が動く():
    """**入れても入れなくても同じなら、入れた意味がありません。**"""
    m = _metrics()
    a = eta.analyse(m)
    なし = eta.plan(m, a, supply=None)
    あり = eta.plan(m, a, supply=_supply(13.0))
    assert あり["days_to_target"] != pytest.approx(なし["days_to_target"])
    assert あり["gate1"]["days"] > なし["gate1"]["days"]


# ------------------------------------------------- 腕が予測を動かすか

def test_1本あたり再生の腕が到達日を動かす():
    """オーナー指示の後半 ——「分析して制作に活かして視聴回数を上げる」が
    **予測に使える形になっているか。** 動かないなら使えていません。"""
    m = _metrics()
    a = eta.analyse(m)
    pl = eta.plan(m, a, supply=_supply(13.0), sensitivity=True)
    rows = {r["lever"]: r for r in pl["lever_days"]}
    assert set(rows) == set(eta.LEVERS)
    assert rows["per_video"]["gain"] > 0
    # 2倍にしたら、いまより早い日付が出ること
    assert rows["per_video"]["reachable"]
    if pl["days_to_target"] < eta.NEVER:
        assert rows["per_video"]["days"] < pl["days_to_target"]


def test_引く腕は床の名前ではなく差の大きさで決まる():
    m = _metrics()
    a = eta.analyse(m)
    pl = eta.plan(m, a, supply=_supply(13.0), sensitivity=True)
    best = max(pl["lever_days"], key=lambda r: r["gain"])
    assert pl["lever_hint"] == best["lever"]
    assert pl["lever_hint_binding"]      # 診断のほうも残っていること


def test_届かない帯でも早い腕が上に来る():
    """**同点にしないこと。** 「届かない → 届く」を一律に最大 gain と書くと、
    届く腕が全部同点になり、**並び順は `LEVERS` に書いた順**で決まります
    （＝こちらの都合。実測ではない）。`NEVER - 日数` のままなら、
    **早く出る腕ほど上**に来ます。
    """
    m = _metrics()
    a = eta.analyse(m)
    pl = eta.plan(m, a, supply=_supply(13.0), sensitivity=True)
    assert pl["days_to_target"] >= eta.NEVER, "この物差しでは、いま日付は出ない前提"
    reach = [r for r in pl["lever_days"] if r["reachable"]]
    assert len(reach) >= 2
    # gain の降順 ＝ 日数の昇順 になっていること
    assert [r["days"] for r in reach] == sorted(r["days"] for r in reach)
    assert len({r["gain"] for r in reach}) == len(reach), "同点になっています"


def test_感度は既定では測らない():
    """`lever_days` が `plan()` を呼び直すので、既定で走ると潜り続けます。"""
    m = _metrics()
    a = eta.analyse(m)
    assert "lever_days" not in eta.plan(m, a, supply=_supply(13.0))


def test_腕の倍率は知らない名前を撥ねる():
    with pytest.raises(KeyError):
        eta.analyse(_metrics(), scale={"unknown_lever": 2.0})


def test_倍率1はいまの実測とまったく同じ():
    """**倍率の入口が、既定の数字を汚していないこと。**"""
    m = _metrics()
    a0 = eta.analyse(m)
    a1 = eta.analyse(m, scale={"per_video": 1.0, "rpm": 1.0})
    assert a1["per_video_now"] == pytest.approx(a0["per_video_now"])
    assert a1["views_needed_month"] == pytest.approx(a0["views_needed_month"])
    assert a1["days_subs_at"] == pytest.approx(a0["days_subs_at"])


def test_いま出ている再生には倍率を掛けない():
    """1本あたり再生を上げても、**過去に公開した本の再生は遡って増えません。**"""
    m = _metrics()
    assert (eta.analyse(m, scale={"per_video": 5.0})["views_day_now"]
            == pytest.approx(eta.analyse(m)["views_day_now"]))
