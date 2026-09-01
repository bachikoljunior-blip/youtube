"""**joint に効いていない腕を、画面が名指しすること。**

## なぜ要るか（2026-09-01・最適化の回に測って作った）

`src/joint_cap.lines()` は、毎周の頭の3行の下に

    **すぐ上の ×24.31 は「その1本だけを動かしたとき」の数で、残りの距離では
    ありません。`rpm` は分母を下げ、`per_video` は分子を上げます ——
    掛かる向きが別なので、1本ずつ測るともう片方の効き目が毎回 捨てられます。**

を**無条件で**添えていました。実測（2026-09-01・`_measure()` の本番の道）::

    据え置き                       目標の  5.73%
    `per_video` だけ天井（×4.16）  目標の 16.52%
    `rpm`       だけ天井（×36.72） 目標の 10.42%
    3本とも同時に天井             目標の **16.52%**  ← `per_video` だけと同じ

**積になっていません。** 1本ずつ抜くと `rpm` / `sub_rate` は
**ちょうど ×1.0000**（`plan()` の `rpm_plan = min(band_rpm, rpm_cap)` が、
`per_video` を引くほど下がる `rpm_cap` でピン留めする）。
それでも画面は「掛かる向きが別なので掛かります」と言い続け、
`deadline_check --fit` は `rpm` を『生きている腕』に数えていました。
**台帳の 19% が `rpm` に配られています** —— 通る道の上では 0 の腕にです。

この検査が守るのは2つ:

1. `idle` な腕がある回は、**その腕を名指しする行が出ること**
2. その回は、**「掛かる向きが別」の文を出さないこと**（今日は偽なので）

**覆る条件**: `plan()` が `min()` をやめる（帯が物理の天井を越えられる）か、
`rpm_mix.coupled()` が長尺の面もこの模型の密度で伸ばすようになったら、
`idle` は空になり、2 の文が自分で戻ります。**そのときこの検査は
`idle` 空の枝（`test_積になっている回は元の文が出る`）だけが残ります。**
"""
from __future__ import annotations

from src import joint_cap

# 2026-09-01 の実物と同じ形。**数字は撃って読むこと** —— ここは形の検査です。
CAPS = [
    {"lever": "per_video", "cap": 4.16},
    {"lever": "sub_rate", "cap": 6.64},
    {"lever": "rpm", "cap": 36.72},
    {"lever": "density", "cap": 1.0},        # 引き代なし ＝ `joint_scale` が落とす
]


def _resolve_pinned(scale: dict[str, float]) -> tuple[float, float]:
    """**`per_video` だけが効く模型**（2026-09-01 の実物と同じ振る舞い）。

    `rpm` / `sub_rate` をいくつにしても答えが変わりません。
    """
    pv = float(scale.get("per_video", 1.0))
    return 500000.0 * (1.0 + 0.44 * (pv - 1.0) / 3.16), 942.1 * pv


def _resolve_multiplying(scale: dict[str, float]) -> tuple[float, float]:
    """**3本とも効く模型**（`rpm` が分母を、`per_video` / `sub_rate` が分子を）。"""
    pv = float(scale.get("per_video", 1.0))
    rp = float(scale.get("rpm", 1.0))
    sr = float(scale.get("sub_rate", 1.0))
    return 500000.0 / min(rp, 1.82), 942.1 * pv * min(sr, 1.3)


def test_ピン留めされた腕は_idle_に出る() -> None:
    res = joint_cap.solve(CAPS, _resolve_pinned)
    assert res is not None
    assert set(res["idle"]) == {"rpm", "sub_rate"}, res["idle"]
    assert res["live"] == ["per_video"], res["live"]
    assert res["marginal"]["rpm"]["factor"] == 1.0
    assert res["marginal"]["per_video"]["factor"] > 1.0


def test_idle_の回は_名指しの行が出る() -> None:
    res = joint_cap.solve(CAPS, _resolve_pinned)
    out = "\n".join(joint_cap.lines(res, 24.31))
    assert "`rpm`" in out and "`sub_rate`" in out
    assert "積になっていません" in out
    assert "前提を立てないこと" in out


def test_idle_の回は_掛かる向きが別_を出さない() -> None:
    """**この1行がこの検査の本体です。** 偽だと分かっている文を出さないこと。"""
    res = joint_cap.solve(CAPS, _resolve_pinned)
    out = "\n".join(joint_cap.lines(res, 24.31))
    assert "掛かる向きが別" not in out


def test_名指しは_solo_の値が無い回にも出る() -> None:
    """`lever_need_over_cap` が `None` の道がある（実測 2026-09-01）。

    警告を注釈の有無に括り付けると、そこで黙ります。
    """
    res = joint_cap.solve(CAPS, _resolve_pinned)
    out = "\n".join(joint_cap.lines(res, None))
    assert "積になっていません" in out


def test_積になっている回は元の文が出る() -> None:
    res = joint_cap.solve(CAPS, _resolve_multiplying)
    assert res["idle"] == [], res["idle"]
    out = "\n".join(joint_cap.lines(res, 24.31))
    assert "掛かる向きが別" in out
    assert "積になっていません" not in out


def test_腕が1本の回は抜かない() -> None:
    """1本しか無ければ「抜く」に意味がありません（**余分な resolve を呼ばない**）。"""
    calls: list[dict] = []

    def _count(scale: dict[str, float]) -> tuple[float, float]:
        calls.append(dict(scale))
        return _resolve_pinned(scale)

    res = joint_cap.solve([{"lever": "per_video", "cap": 4.16}], _count)
    assert res is not None
    assert res["idle"] == []
    assert len(calls) == 1, calls
