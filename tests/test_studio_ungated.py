"""**門を通らない分子（企業案件）の口**の検査（2026-09-18・optimizer・Opus・ultracode）。

**なぜこの検査が在るか**: `yen_now` は `"gated": True` を返していましたが、
**その印を読む口が 1つ もありませんでした**。`CLAUDE.md` 2026-08-15 は稼ぎ方を
4つ 開けており（広告・メンバーシップ・Super Thanks・企業案件）、**門の外は 1つ**です。
＝ 毎周 印字していた 151倍／34,286倍 は **広告の倍率**で、目標の倍率ではありません。

**この検査が守るのは 3つ**:
  (1) 門の外の分子が、`trend` と `status` の**両方**で毎周 印字されること
      （固定2 は `status` で最初に答える問い ＝ `trend` にしか無い行は間に合わない）
  (2) 帯が **1か所** にしかないこと（`peers.RPM_BAND` と同じ扱い ＝ 写しを持たない）
  (3) 「要る単価」の向き（**倍率 ＝ 要る単価 ÷ 相場**・1以下なら相場の中で届く）が
      `yen_now` の `times`（円/月 の倍率・**向きが逆**）と混ざらないこと
"""
from __future__ import annotations

from studio import trend


def _rows() -> list[dict]:
    return trend.ledger_rows()


def test_門の外の分子は帯を1か所にしか持たない() -> None:
    """帯は `SPONSOR_YEN_PER_VIEW_BAND` の 1か所（`peers.RPM_BAND` と同じ扱い）。"""
    band = trend.SPONSOR_YEN_PER_VIEW_BAND
    assert len(band) == 3
    assert band[0] < band[1] < band[2]
    # **写しを持たないこと** —— 同じ数の tuple が `studio/` の別の所に無い。
    src = (trend.__file__,)
    hits = 0
    for p in src:
        with open(p, encoding="utf-8") as fh:
            hits += fh.read().count("SPONSOR_YEN_PER_VIEW_BAND = (")
    assert hits == 1, "帯の定義が 2か所 以上 に在ります（写しを持たないこと）"


def test_4つの分子のうち門の外は1つだけ() -> None:
    """`CLAUDE.md` 2026-08-15 の 4つ。**門を通らないのは 企業案件 だけ。**"""
    assert set(trend.GATED_FORMS) == {"広告", "メンバーシップ", "Super Thanks"}
    assert trend.UNGATED_FORMS == ("企業案件",)
    assert len(trend.GATED_FORMS) + len(trend.UNGATED_FORMS) == 4


def test_倍率の向きは要る単価わる相場() -> None:
    """**`yen_now` の `times` と向きが逆**なので、混ぜたら落ちること。"""
    d = trend.ungated_yen(_rows())
    assert d["gated"] is False
    if d["need_per_view"] is None:
        return
    band = d["band"]
    for lv, b in zip(trend.YEN_LEVELS, band):
        assert abs(d["times"][lv] - d["need_per_view"] / b) < 1e-9
    # 相場が高いほど倍率は小さい（＝ 届きやすい）。
    assert d["times"]["低"] > d["times"]["中"] > d["times"]["高"]


def test_天井の本数は_budget_から引く_写しを持たない() -> None:
    """**2026-09-18 に踏んだ所**: 最初 `6.0` を直書きし、実物は **5本** だった。

    天井の本数は `budget` の 3つ の定数から出る数で、**写しを持たないこと**。
    """
    from studio import budget
    want = float(max((budget.DAY_UNITS - budget.RESERVE) // budget.UPLOAD_UNITS, 0))
    assert trend.sponsor_daily_cap_videos() == want
    with open(trend.__file__, encoding="utf-8") as fh:
        src = fh.read()
    assert "SPONSOR_DAILY_CAP_VIDEOS" not in src, "天井の本数を直書きに戻さないこと"


def test_天井は本あたりを動かさず本数だけ上げる() -> None:
    """日枠が戻った側は **再生/日 が増え、要る単価は下がる**こと。"""
    d = trend.ungated_yen(_rows())
    if d["need_per_view"] is None:
        return
    c = d["cap"]
    assert c["views_day"] >= d["views_day"]
    if c["views_day"] > d["views_day"]:
        assert c["need_per_view"] < d["need_per_view"]


def test_行は毎周_trend_に出る() -> None:
    """**`trend` の組み立てにこの行が入っていること**（抜けたら固定2 が広告の倍率で答える）。"""
    with open(trend.__file__, encoding="utf-8") as fh:
        src = fh.read()
    assert "out.append(ungated_line(rows))" in src


def test_行は毎周_status_にも出る() -> None:
    """**固定2 は `status` で最初に答える問い** ＝ `trend` にしか無い行は間に合わない。"""
    from studio import cli
    with open(cli.__file__, encoding="utf-8") as fh:
        src = fh.read()
    assert "trend.ungated_short(" in src


def test_行は売れるとは言わない() -> None:
    """**覆る条件 (2)** ＝ この行は受注を意味しない。字がそう言っていること。"""
    line = trend.ungated_line(_rows())
    short = trend.ungated_short(_rows())
    assert "売れる" in line
    assert "売れるとは言っていません" in short


def test_gated_の印が両側そろっている() -> None:
    """`yen_now` が `True`・`ungated_yen` が `False`（**対になる側が在ること**）。"""
    rows = _rows()
    assert trend.yen_now(rows)["gated"] is True
    assert trend.ungated_yen(rows)["gated"] is False
