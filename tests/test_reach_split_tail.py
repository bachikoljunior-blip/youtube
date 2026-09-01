"""**公開1本あたりの面に、減衰の尾を入れる**（`src/reach_split`）。

`summary()["長尺"]["per_publish"]` は「窓の面 ÷ 窓の中の公開 本数」で、
**窓の右端で公開した本も丸ごと1本**と数えます。その本の尾はまだ積んでいないので、
**1本あたりは下振れします。** この数は `rpm_mix.rule_capped()` を通って
`scripts/eta.py` の面の天井に直に入るので、下振れはそのまま
「面が足りない → 到達日が出ない」になります。

守るのは3つ:

1. **齢の曲線は均衡パネルで測る**（齢 `TAIL_DAYS` 日まで観測できた本だけ）。
   混ぜると齢の大きい所ほど本数が減り、尾が短く見えます
2. **窓の右端の本は 1本 未満、窓より前の本は 0本 ではない**
3. **測れないときは `None`**（推測の曲線で分母を割らないこと）

**覆る条件**: `data/reach.jsonl` が本べつの `date` を持たなくなったら、
`accrual_curve()` ごと畳むこと（この検査も一緒に消す）。
"""
from __future__ import annotations

import pytest

from src import reach_split as R


def _row(vid: str, day: str, imp: float) -> dict:
    return {"video_id": vid, "date": day,
            "video_thumbnail_impressions": imp,
            "video_thumbnail_impressions_ctr": 0.0}


def _panel(n: int = 6, horizon: int = 7,
           daily: tuple[float, ...] = (40, 10, 10, 10, 10, 10, 5, 5)):
    """齢 `horizon` 日まで観測できた本を n 本。全部 20260801 公開。"""
    rows, pub = [], {}
    for i in range(n):
        vid = f"v{i}"
        pub[vid] = "20260801"
        for age, imp in enumerate(daily[:horizon + 1]):
            d = 1 + age
            rows.append(_row(vid, f"202608{d:02d}", imp))
    # 窓の右端を伸ばすためのダミー（面 0 の日は齢の合計に効かない）
    rows.append(_row("v0", "20260810", 0.0))
    return rows, pub


def test_曲線は単調で最後が1になる() -> None:
    rows, pub = _panel()
    curve = R.accrual_curve(rows, pub)
    assert curve is not None
    assert curve[-1] == pytest.approx(1.0)
    assert all(curve[i] >= curve[i - 1] for i in range(1, len(curve)))
    # 40/100 が初日
    assert curve[0] == pytest.approx(0.4, abs=1e-9)


def test_パネルが薄いと曲線を返さない() -> None:
    """**推測の曲線で分母を割らないこと。** 分母は面の天井に直に効きます。"""
    rows, pub = _panel(n=R.TAIL_MIN_PANEL - 1)
    assert R.accrual_curve(rows, pub) is None


def test_齢horizon日まで観測できていない本はパネルに入らない() -> None:
    """混ぜると齢の大きい所ほど本数が減り、**尾が短く見えます。**"""
    rows, pub = _panel(n=R.TAIL_MIN_PANEL)
    # 窓の最終日に公開した本を1本 足す（齢0日 しか観測できていない）
    rows.append(_row("late", "20260810", 9_999.0))
    pub["late"] = "20260810"
    curve = R.accrual_curve(rows, pub)
    assert curve is not None
    # 9,999回 は齢0日 に入るが、パネルに入らないので曲線は動かない
    assert curve[0] == pytest.approx(0.4, abs=1e-9)


def test_窓の右端で公開した本は1本未満に数える() -> None:
    curve = [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0]
    window = [f"202608{d:02d}" for d in range(14, 21)]      # 08/14〜08/20
    eff = R.settled_publishes(window, {"a": "20260820"}, curve)   # 最終日に公開
    assert eff == pytest.approx(0.4)


def test_窓より前に公開した本も0本ではない() -> None:
    """**尾の一部が窓に落ちています。** いまの数え方はこれを 0本 にしています。"""
    curve = [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0]
    window = [f"202608{d:02d}" for d in range(14, 21)]      # 08/14〜08/20
    # 08/12 公開 ＝ 窓の始まりで齢2日・窓の終わりで齢8日（>= horizon なので 1.0）
    eff = R.settled_publishes(window, {"a": "20260812"}, curve)
    assert eff == pytest.approx(1.0 - 0.5)                 # W(8) - W(1)


def test_曲線が無ければ分母も返さない() -> None:
    window = [f"202608{d:02d}" for d in range(14, 21)]
    assert R.settled_publishes(window, {"a": "20260820"}, None) is None


def _spread(n: int = 6, horizon: int = 7,
            daily: tuple[float, ...] = (40, 10, 10, 10, 10, 10, 5, 5)):
    """パネル 6本（08/01 公開）＋ **窓の右端で公開した本 1本**。

    窓は `RECENT_DAYS` 日ぶんの最後 ＝ この並びでは 08/09〜08/15。
    """
    rows, pub = _panel(n=n, horizon=horizon, daily=daily)
    pub["late"] = "20260815"
    for age, imp in enumerate(daily[:1]):
        rows.append(_row("late", f"202608{15 + age:02d}", imp))
    # 窓を 08/09〜08/15 にするための、面 0 の日
    for d in range(9, 16):
        rows.append(_row("v0", f"202608{d:02d}", 0.0))
    return rows, pub


def test_summaryが尾を入れた1本あたりを一緒に返す() -> None:
    """**上の `per_publish` は変えていません**（保存済みの点と比べられなくなる）。"""
    rows, pub = _spread()
    sm = R.summary(rows, set(pub), publishes={"20260815": 1},
                   pub_days=pub)
    v = sm["長尺"]
    assert v["per_publish"] is not None
    assert v["tail_curve"] is not None
    assert v["settled_publishes"] is not None
    assert v["per_publish_settled"] is not None
    # 窓の右端の1本は 1本 未満に数えるので、**分母は 1本 を下回る**
    assert v["settled_publishes"] < v["recent_publishes"]
    assert v["per_publish_settled"] > v["per_publish"]
    assert "×" in v["per_publish_settled_basis"]


def test_窓の中の公開が0本でも尾は落ちている() -> None:
    """いまの `per_publish` はここで **None** になり、面の天井が丸ごと落ちます。"""
    rows, pub = _panel()
    sm = R.summary(rows, set(pub), publishes={"20260801": len(pub)},
                   pub_days=pub)
    v = sm["長尺"]
    assert v["recent_publishes"] == 0
    assert v["per_publish"] is None
    assert v["per_publish_settled"] is not None
    assert "0本" in v["per_publish_settled_basis"]


def test_尾を測れない回は理由を書いて元の数に落ちる() -> None:
    rows, pub = _panel(n=R.TAIL_MIN_PANEL - 1)
    sm = R.summary(rows, set(pub), publishes={"20260801": len(pub)},
                   pub_days=pub)
    v = sm["長尺"]
    assert v["tail_curve"] is None
    assert v["per_publish_settled"] is None
    assert "測れていません" in v["per_publish_settled_basis"]


def test_地平は窓と同じ長さにしてある() -> None:
    """窓と地平がずれると、**窓の外の尾を数える**か、割合が 1.0 を超えます。"""
    assert R.TAIL_DAYS == R.RECENT_DAYS


def test_公開日の一覧は作り置きを落とす() -> None:
    """規則を写していないこと ——判定は `house_rule.is_stockpile()` の1か所。"""
    import inspect
    src = inspect.getsource(R.publish_day_by_id)
    assert "house_rule.is_stockpile(" in src
