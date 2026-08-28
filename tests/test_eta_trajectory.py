"""**軌跡**（`scripts/eta.trajectory`）—— 腕が動く速さを含んだ、1本の到達予測。

## 何を守っているか（2026-08-20 18:xx・オーナー指示）

> 腕とやらをそう設定した時に達成がいつになるって予測じゃなくて、じゃあその腕を
> そうなるまでにどれくらい時間がかかるのかとか予測しないとダメだよ。**特定条件の
> 予測じゃなくて、実際にどういう軌跡を辿るか予測して、いつ達成かを予測するんだよ。**

**写しに戻ったら落ちます。** 具体的には、次の3つが同時に成り立つこと:

1. 印字する日付が `plan()["target_date"]` の写しではないこと
   （＝ 腕の速さを変えたら、印字される日付が動くこと）
2. 「腕を何日動かすか」が答えに入っていること（`t_work`）
3. 出ないときは、**塞いでいるものを名指し**すること（`blocking`）

**この3つは、直前の `lever_days`（×2 の表）には1つもありませんでした。**
"""
from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location("eta_traj", ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eta)

import _eta_pin  # noqa: E402  （pytest が tests/ を sys.path に入れます）

TODAY = date(2026, 8, 20)


# --- **天井2つは、この file の主題ではありません**（2026-08-22 に足した）---
#
# ここが測るのは「腕が動く速さを含んだ軌跡が出るか」で、天井の値ではありません。
# `plan()` は `src/day_cap.cap()` と `src/rpm_mix.last()` を実測から直に読むため、
# **こちらが1回測るたびに、合成データが「届く帯」から外れます** ——
# 08/20 の RPM 初測（帯¥400 → 実効¥253）と 08/21 の day_cap 実測（25→17本/日）で、
# **腕を伸ばしても1本も届かなくなり、この file の3件が赤**になりました。
# 天井そのものは `tests/test_eta_surface_cap.py` / `test_eta_day_cap.py` が持ちます。
@pytest.fixture(autouse=True)
def _天井は主題ではない(monkeypatch):
    _eta_pin.pin_ceilings(monkeypatch, eta.PLAN_PUBLISH_PER_DAY)


def _measured(**over):
    """2026-08-20 の実測に近い標本。**手元のファイルは読みません。**"""
    m = {
        "subs_net": 9, "views_all": 27_777, "views_7d": 8_802, "views_28d": 20_303,
        "views_90d": 22_534, "subs_gained_28d": 9, "subs_gained_90d": 11,
        "long_hours_365": 0.1, "shorts_views_90d": 22_515,
        "views_per_video": 923, "median_views_per_video": 1_041,
        "videos_with_views_28d": 22,
        "long_per_video": 2.0, "long_median_per_video": 2, "long_videos_28d": 5,
        "long_views_28d": 11,
    }
    m.update(over)
    return m


def _arms(**over):
    """**速さを手で置いた腕**（実測の読み取りとは切り離して、解き方だけを見る）。"""
    base = {k: {"lever": k, "n": 3, "hits": 1, "p": 0.3, "gain": 1.8,
                "share": 0.25, "rate": 0.05, "focus_rate": 0.2, "cap": None,
                "ceiling": None, "source": "自前", "throughput": 0.9, "missing": []}
            for k in ("per_video", "sub_rate", "rpm", "density")}
    for k, v in over.items():
        base[k] = {**base[k], **v}
    return base


def _solve(arms, **kw):
    m = _measured()
    a = eta.analyse(m)
    m["per_video_now"] = a["per_video_now"]
    return eta.trajectory(m, a, today=TODAY, arms=arms, **kw)


# --- 1. 写しに戻っていないこと -------------------------------------------------------

def test_腕が速いほど到達が早い_写しなら動かない():
    """**ここが要です。** `plan()["target_date"]` の写しなら、速さを変えても動きません。"""
    slow = _solve(_arms(**{k: {"rate": 0.01} for k in ("per_video", "sub_rate", "rpm", "density")}))
    fast = _solve(_arms(**{k: {"rate": 0.20} for k in ("per_video", "sub_rate", "rpm", "density")}))
    assert fast["days"] < slow["days"], "腕の速さが到達日に効いていません（写しに戻っています）"


def test_腕が1つも動かない世界は_据え置きの線と同じ():
    """**速さ 0 のときだけ**、軌跡は「腕を据え置いた線」に一致すること。

    一致しないなら、軌跡はどこかで**実測に無い下駄**を履かせています。
    """
    m = _measured()
    a = eta.analyse(m)
    m["per_video_now"] = a["per_video_now"]
    pl = eta.plan(m, a, today=TODAY)
    tr = eta.trajectory(m, a, today=TODAY,
                        arms=_arms(**{k: {"rate": 0.0, "focus_rate": 0.0}
                                      for k in ("per_video", "sub_rate", "rpm", "density")}))
    assert tr["days"] == pytest.approx(pl["days_to_target"])
    assert tr["t_work"] in (0, None)


def test_答えには_腕を何日動かすかが入っている():
    """**「×2 にしたら」の表には、これが1行もありませんでした。**"""
    tr = _solve(_arms())
    assert tr["date"] is not None
    assert tr["t_work"] is not None and tr["t_work"] >= 0
    assert tr["factors"] is not None and set(tr["factors"]) == set(eta.arm_speed.ARMS)
    # **腕を動かした日数と、そこから走る日数の和が到達日**であること
    assert tr["days"] == pytest.approx(tr["t_work"] + tr["plan_days"])


def test_倍率は速さと日数から出ている():
    """`x(t) = exp(rate · t)`。**定数で置いたら落ちます。**

    **天井の無い世界でだけ、この等式です**（2026-08-21 02:1x に幅を足した）。
    天井に着いた腕からは回転を引き上げる（`_factors_at(realloc=True)`）ので、
    どれかが着いた後の残りは `rate` より**速く**なります。
    下の `test_天井に着いた腕の配分は残りに回る` が、その向きを固定しています。
    """
    import math
    no_cap = {k: {"cap": 0.0} for k in ("per_video", "sub_rate", "rpm", "density")}
    no_cap["rpm"] = {"cap": 0.0, "rate": 0.03}
    tr = _solve(_arms(**no_cap))
    if tr["t_work"]:
        assert tr["factors"]["rpm"] == pytest.approx(math.exp(0.03 * tr["t_work"]))


def test_天井に着いた腕の配分は残りに回る():
    """**回転の半分を、もう伸びない腕に注ぎ続けないこと。**（2026-08-21 02:1x）

    `rate = focus_rate × share` の `share` が固定だったので、実測では
    `per_video`（配分 57% ・天井 ×1.57）が着いた後も、そこに回転が
    回り続けていました。軌跡が「腕を全部振っても出ません」と言っていた理由の1つです。
    """
    import math
    # `per_video` だけすぐ天井。残り3本は天井なし
    arms = _arms(per_video={"cap": 1.2},
                 **{k: {"cap": 0.0} for k in ("sub_rate", "rpm", "density")})
    tr = _solve(arms)
    if not tr["t_work"]:
        pytest.skip("この標本では腕を動かさないのが最良（配り直しの向きは見られない）")
    t = tr["t_work"]
    assert tr["factors"]["per_video"] == pytest.approx(1.2)
    # 着いた後は、据え置きの配分より**速い**こと
    assert tr["factors"]["rpm"] > math.exp(0.05 * t)
    # ただし「全部振った」より速くはならないこと
    assert tr["factors"]["rpm"] <= math.exp(0.2 * t) + 1e-9


# --- 2. 天井（**実在しない世界を歩かない**）--------------------------------------------

def test_天井を超えた倍率まで腕を伸ばさない():
    """**1日110,525本を歩いた版があります。** 同じ穴を二度掘らないこと。"""
    tr = _solve(_arms(density={"cap": 2.0}, rpm={"cap": 3.0}))
    assert tr["factors"]["density"] <= 2.0 + 1e-9
    assert tr["factors"]["rpm"] <= 3.0 + 1e-9


def test_全部の腕が天井なら_そこで探索を打ち切る():
    """天井まで行き着いた先は、`t` が増えるだけ ＝ **必ず遅くなります。**"""
    tr = _solve(_arms(**{k: {"cap": 1.2, "rate": 0.5}
                         for k in ("per_video", "sub_rate", "rpm", "density")}))
    assert tr["searched_days"] < eta.TRAJECTORY_HORIZON_DAYS


# --- 3. 届かないときに、名指しすること ------------------------------------------------

def test_出ないときは塞いでいるものを名指しする():
    """**「届きません」で終えないこと**（`plan()` の `blocking` と同じ作り）。"""
    tr = _solve(_arms(**{k: {"rate": None, "focus_rate": None,
                            "missing": ["当たったときの伸び幅（この腕はまだ1件も当てていない）"]}
                         for k in ("per_video", "sub_rate", "rpm", "density")}),
                supply={"rate_per_day": 0.0, "stock": 0, "measured": True})
    if tr["date"] is None:
        assert tr["blocking"], "出ないのに、塞いでいるものを名指ししていません"
        assert any("動きません" in x for x in tr["blocking"])


def test_天井のある腕は_外す腕まで名指しする():
    """`per_video` の天井は**形の天井**です。外す腕（`rpm`）まで書くこと。"""
    arms = _arms(per_video={"cap": 1.5, "ceiling": {
        "lever": "per_video", "value": 1447, "unit": "1本あたり再生", "escape": "rpm"}})
    tr = _solve(arms)
    why = eta._trajectory_blocking(arms, {"date": None, "searched_days": 100})
    assert any("`rpm`" in x for x in why)
    assert tr is not None


# --- 4. 「全部この腕に振ったら」---------------------------------------------------------

def test_腕べつの軌跡は_早い順に並ぶ():
    m = _measured()
    a = eta.analyse(m)
    m["per_video_now"] = a["per_video_now"]
    arms = _arms()
    base = eta.trajectory(m, a, today=TODAY, arms=arms)
    rows = eta.trajectory_choice(m, a, base, today=TODAY, arms=arms)
    assert [r["lever"] for r in rows] and len(rows) == len(eta.arm_speed.ARMS)
    assert rows == sorted(rows, key=lambda r: (r["days"], r["lever"]))


def test_回転を1つに振ったら_その腕だけが動く():
    """**回転は1本しかありません。** 4本とも全力の線は実在しません。"""
    tr = _solve(_arms(), focus="rpm")
    assert tr["factors"] is not None
    for lever, f in tr["factors"].items():
        if lever != "rpm":
            assert f == pytest.approx(1.0), f"{lever} が振っていないのに動いています"


# --- 5. 出力（**日付は最初と最後の両方に出る**）------------------------------------------

def test_印字する日付は軌跡のほう():
    """オーナー指示: **最後に出る1つの日付は軌跡のほう**にすること。"""
    m = _measured()
    a = eta.analyse(m)
    m["per_video_now"] = a["per_video_now"]
    pl = eta.plan(m, a, today=TODAY)
    tr = {"base": _solve(_arms()), "fast": None, "slow": None, "choice": [],
          "streak": {"n": 0}, "band": {"k": 1, "n": 3}, "arms": _arms(), "unread": 0}
    text = "\n".join(eta.headline(pl, None, tr))
    assert "到達予測（軌跡）" in text
    assert tr["base"]["date"].isoformat() in text
    # **据え置きの線も残すこと**（比べられないと、軌跡が効いたかが読めません）
    assert "据え置いた" in text
    src = (ROOT / "scripts" / "eta.py").read_text(encoding="utf-8")
    # **閉じ括弧まで当てないこと**（2026-08-29 に3件 まとめて赤くなった）。
    # `headline()` に引数を1つ足すだけで、この検査は落ちます —— 落ちても
    # 「頭と尾で2回 呼んでいるか」は1文字も変わっていません。**守りたいのは
    # 呼ぶ回数と場所であって、引数の並びではない。**
    assert src.count("for line in headline(pl, prev, tr") == 2


def test_軌跡が解けなくても回は止まらない():
    """**予測で回を止めないこと。** 軌跡が落ちても、据え置きの線だけで出すこと。"""
    m = _measured()
    a = eta.analyse(m)
    pl = eta.plan(m, a, today=TODAY)
    text = "\n".join(eta.headline(pl, None, None))
    assert "到達予測" in text and "引く腕" in text
    src = (ROOT / "scripts" / "eta.py").read_text(encoding="utf-8")
    assert "軌跡を解けませんでした" in src, "`trajectory_all` を try で包んでいません"


def test_軌跡は記録に積まれる():
    """積まないと、次の回が「軌跡が早まったか」を測れません。"""
    src = (ROOT / "scripts" / "eta.py").read_text(encoding="utf-8")
    for key in ('row["traj_date"]', 'row["traj_days"]', 'row["traj_t_work"]'):
        assert key in src, f"{key} を積んでいません"


def test_前の回との差は同じ物差しどうしで比べる():
    """据え置きの線と軌跡を混ぜると、**1日で200日早まった**が出ます。"""
    m = _measured()
    a = eta.analyse(m)
    m["per_video_now"] = a["per_video_now"]
    pl = eta.plan(m, a, today=TODAY)
    base = _solve(_arms())
    tr = {"base": base, "fast": None, "slow": None, "choice": [],
          "streak": {"n": 0}, "band": {"k": 1, "n": 3}, "arms": _arms(), "unread": 0}
    prev = {"target_date": "2027-01-24", "traj_date": base["date"].isoformat()}
    text = "\n".join(eta.headline(pl, prev, tr))
    assert "（軌跡どうし）" in text
    assert "**+0日**" in text, "同じ軌跡どうしなら 0日 のはずです"


# --- 5. **天井 ×1.00 は「天井が無い」ではない**（2026-08-22 に踏んで足した）---------

def test_伸びしろゼロの腕を歩かない():
    """`cap == 1.00` ＝ **もう1ミリも伸びない**。いちばんきつい天井です。

    ここは `cap > 1.0` で弾いていたので、**伸びしろゼロの腕だけが野放し**になり、
    軌跡は `density` を **×3.43** まで伸ばした世界を歩いていました（実測）。
    `_capped_arms` は `physical_caps` の低いほうを当てるので、**1.00 は実際に入ります。**
    """
    tr = _solve(_arms(density={"cap": 1.0}, per_video={"cap": 1.0}))
    assert tr["factors"]["density"] == pytest.approx(1.0)
    assert tr["factors"]["per_video"] == pytest.approx(1.0)


def test_伸びしろゼロの腕は探索の地平を延ばさない():
    """**動かない腕のために3年ぶん探索していました**（`saturate` も同じ穴）。"""
    frozen = _solve(_arms(**{k: {"cap": 1.0}
                             for k in ("per_video", "sub_rate", "rpm", "density")}))
    assert frozen["searched_days"] == 0, "伸びない腕のために t を回しています"


def test_倍率1未満の天井も1倍で止まる():
    """腕はこの模型で縮みません。`cap < 1` は 1.00 と同じに扱うこと。"""
    tr = _solve(_arms(density={"cap": 0.5}))
    assert tr["factors"]["density"] == pytest.approx(1.0)
