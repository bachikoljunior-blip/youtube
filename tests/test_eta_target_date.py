"""`scripts/eta.py` —— **月20万に届く日そのものを解いているか。**

## この検査が守っているもの（2026-08-20 08:0x・オーナー指示3回目）

> 「20万達成までのプランを作って**達成日時を予測**して、
>   毎回達成日時を早めることを考えてから進めるようにして」

同じ趣旨の指示は 08-19（33699957）・08-20 06:2x に続いて**3回目**でした。
**3回言われている ＝ まだ形になっていない。** 実際、`plan()` の段4 は

    d_target = d_monetized     # 段3 の写し

の1行で、印字されていた「125日後（2026-12-22）」は
**収益化の審査が終わる見込みの日**でした。**20万に届く日ではありません。**
写しである以上、per_video を10倍にしても RPM を5倍にしても、
**印字される日付は1日も動きません** —— 「早めることを考えてから進めろ」という
指示が、**構造上動かない数字**に向かって出されていたことになります。

**だから、ここで固定するのは「日付が出ること」ではありません。**
固定するのは次の3つです。

1. **段4 の期日が、段3 と独立に動くこと**（写しに戻ったら落ちる）
2. **到達日が、収益化の門と再生数の「遅いほう」であること**（片方だけ見ない）
3. **天井が足りない帯は「届かない」と言い、そのとき何倍要るかを出すこと**
   （予測を「届きません」で終わらせない）
"""
from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("eta_target_mod", ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eta)


def _measured(**over):
    """2026-08-19〜20 の実測（`data/eta.jsonl` の最後の点）。"""
    base = dict(
        at="2026-08-19T22:21:32+00:00",
        subs_net=9,
        views_all=27_806,
        views_7d=11_324,
        views_28d=20_332,
        views_90d=22_563,
        subs_gained_28d=9,
        subs_gained_90d=11,
        long_hours_365=0.1,
        shorts_views_90d=22_515,
        views_per_video=952,
        median_views_per_video=1_041,
        videos_with_views_28d=21,
        long_per_video=2,
        long_videos_28d=5,
        long_views_28d=11,
    )
    base.update(over)
    return base


# --- 1. 段4 は段3 の写しではない -------------------------------------------------

def test_段4の期日は段3の写しではない():
    """**この検査が本体です。** 写しに戻ったら、ここで落ちること。"""
    m = _measured()
    pl = eta.plan(m, eta.analyse(m))
    stage3 = next(s for s in pl["stages"] if s["no"] == 3)
    stage4 = next(s for s in pl["stages"] if s["no"] == 4)
    assert stage4["when"] != stage3["when"], (
        "段4 の期日が段3 と同じです。**解かずに写している疑い**"
        "（2026-08-20 まで `d_target = d_monetized` の1行でした）"
    )


def test_1本あたり再生を上げると段4の期日が動く():
    """**写しだと、ここが動きません。** 動かない数字に向かって「早めろ」は成立しない。"""
    m = _measured()
    slow = eta.plan(m, eta.analyse(m))["days_revenue"]
    m2 = _measured(views_per_video=952 * 4, views_7d=11_324 * 4, views_28d=20_332 * 4)
    fast = eta.plan(m2, eta.analyse(m2))["days_revenue"]
    assert fast < slow, "1本あたり再生を4倍にしても段4 が動きません"


# --- 2. 到達日は「遅いほう」 ------------------------------------------------------

def test_到達日は3つの床のいちばん遅いもの():
    """**(a) 再生・(b) 収益化＋30日・(c) 確かめ終わり＋30日 の、いちばん遅いもの。**

    (b) は 2026-08-20 08:3x の回が入れた床です（`REVENUE_WINDOW_DAYS`）——
    月20万は水準なので、**収益化してから30日ぶん積んだ合計**でしか名乗れない。
    **(a) にそれを足さないこと。** (a) は直近30日の合計で見ているので、
    足すと1か月ぶん二重に数えます。
    """
    m = _measured()
    pl = eta.plan(m, eta.analyse(m))
    tg = pl["target"]
    assert pl["days_to_target"] == max(pl["days_revenue"], tg["gate_floor"], tg["verify_floor"])
    assert tg["gate_floor"] == pl["days_monetized"] + eta.REVENUE_WINDOW_DAYS
    # **二重に数えていないこと**（(a) + 30日 になっていたら落ちる）
    assert pl["days_to_target"] != pl["days_revenue"] + eta.REVENUE_WINDOW_DAYS
    # **縛っている側の名指しと、引く腕が食い違わないこと**
    if pl["days_revenue"] >= tg["floor"]:
        assert pl["lever_hint"] in ("per_video", "rpm")
    else:
        assert pl["lever_hint"] in ("density", "rpm")


def test_再生数が届かないなら到達日も出ない():
    """**門だけ見て「収益化したから届く」と言わないこと。**"""
    # 1本あたり 1回 まで落とすと、密度25本/日の天井は 月 750回。届きようがない
    m = _measured(views_per_video=1, views_7d=21, views_28d=84)
    pl = eta.plan(m, eta.analyse(m))
    assert pl["days_revenue"] >= eta.NEVER
    assert pl["days_to_target"] >= eta.NEVER
    assert pl["target_date"] is None
    assert pl["ceiling_short"] > 1


# --- 3. 解き方そのもの -------------------------------------------------------------

def test_天井が足りなければ何日待っても届かない():
    """**そこは伸び率の問題ではなく形の問題です。** 待たせないこと。"""
    d = eta.solve_revenue_day(views_day_now=1_000, growth=0.5,
                              ceiling_views_day=2_000, need_month=500_000)
    assert d >= eta.NEVER
    # 天井を上げれば、同じ伸び率で届く
    d2 = eta.solve_revenue_day(views_day_now=1_000, growth=0.5,
                               ceiling_views_day=50_000, need_month=500_000)
    assert 0 < d2 < eta.NEVER


def test_月20万は_その日の再生ではなく直近30日の合計で判定する():
    """日次が達した日を到達日にすると、**数日から数週間ぶん早く出ます。**"""
    need = 300_000                      # 月30万回 ＝ 1日1万回が30日続くこと
    # いきなり1日1万回に達しても、**その日には直近30日が埋まっていない**
    d = eta.solve_revenue_day(views_day_now=9_999, growth=0.5,
                              ceiling_views_day=10_000, need_month=need)
    assert d > 1, "日次が達した瞬間を到達日にしています（合計で見ていない）"


def test_伸びていなければ届かないと言う():
    assert eta.solve_revenue_day(1_000, 0.0, 100_000, 500_000) >= eta.NEVER
    assert eta.solve_revenue_day(1_000, None, 100_000, 500_000) >= eta.NEVER
    # すでに満たしているなら 0日
    assert eta.solve_revenue_day(20_000, 0.0, 100_000, 500_000) == 0.0


def test_要る伸び率は逆算できて_その伸びなら本当に届く():
    """**「何を何倍にすれば何日後」を出すための逆算。** 往復で確かめる。"""
    g = eta.required_growth(views_day_now=1_600, ceiling_views_day=23_800,
                            need_month=500_000, days=90)
    assert g is not None and 0 < g < 1
    assert eta.solve_revenue_day(1_600, g, 23_800, 500_000) <= 90
    # 天井が足りない帯では、逆算しても None（伸び率をいくら上げても届かない）
    assert eta.required_growth(1_600, 2_000, 500_000, 90) is None


def test_伸び率は2つの窓の比から出る():
    m = _measured()
    g = eta.growth_per_day(m)
    v7, v28 = 11_324 / 7, 20_332 / 28
    assert g["g"] == pytest.approx((v7 / v28) ** (1 / eta.WINDOW_CENTROID_GAP_DAYS) - 1)
    assert "窓" in g["basis"]


def test_履歴が7日ぶん貯まったら履歴のほうで測る():
    """**短い履歴で測らないこと。** Analytics の3日遅れが伸び率に化けます。"""
    m = _measured()
    short = [{"at": "2026-08-19T00:00:00+00:00", "views_per_day": 800},
             {"at": "2026-08-20T00:00:00+00:00", "views_per_day": 1_600}]
    assert "窓" in eta.growth_per_day(m, short)["basis"], "1日の履歴で測っています"
    long_ = [{"at": "2026-08-01T00:00:00+00:00", "views_per_day": 800},
             {"at": "2026-08-20T00:00:00+00:00", "views_per_day": 1_600}]
    g = eta.growth_per_day(m, long_)
    assert "履歴" in g["basis"]
    assert g["g"] == pytest.approx(2 ** (1 / 19) - 1)


# --- 4. 予測日が、最初と最後の両方に出る ---------------------------------------------

def test_到達予測は出力の最初と最後に出る():
    """**200行の真ん中に置いたら読まれません**（§3 が飛ばされた記録があります）。"""
    m = _measured()
    a = eta.analyse(m)
    pl = eta.plan(m, a)
    text = "\n".join(eta.headline(pl))
    assert "到達予測" in text
    assert "引く腕" in text
    src = (ROOT / "scripts" / "eta.py").read_text(encoding="utf-8")
    assert src.count("for line in headline(pl, prev, tr):") == 2, (
        "`headline` は最初と最後の2回出すこと（片方だけになっています）"
    )


def test_予測日は記録に積まれる():
    """積まないと、次の回が「早まったか」を測れません（`--moves` の突き合わせ）。"""
    src = (ROOT / "scripts" / "eta.py").read_text(encoding="utf-8")
    assert 'row["target_date"]' in src and 'row["days_to_target"]' in src


def test_日付はJSTで数える():
    """器は UTC。`date.today()` を使うと、日本時間の朝まで**1日ずれます**。"""
    # Analytics の窓（`_measure` の `end`）は UTC のままでよい —— あちらは
    # **まだ来ていない日を問い合わせない**ための下限で、先へ進めると空が返ります。
    # 揃えるのは**予測の日付を作る所**です（`_fmt_days` と `plan`）。
    src = (ROOT / "scripts" / "eta.py").read_text(encoding="utf-8")
    assert "when = today_jst() + timedelta(days=math.ceil(days))" in src, (
        "`_fmt_days` が UTC の today で日付を作っています（`headline` は JST なので1日ずれます）"
    )
    m = _measured()
    pl = eta.plan(m, eta.analyse(m), today=date(2026, 8, 20))
    assert pl["target_date"] is not None and pl["target_date"] > date(2026, 8, 20)
