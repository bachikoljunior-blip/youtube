"""**門の外の分子、その2（成果報酬）の口**の検査（2026-09-18 15:4x・optimizer・Opus）。

**なぜこの検査が在るか**: 同じ日の 14:xx の回が `ungated_yen` を置いたとき、門の外の分子を
**企業案件 1つ** と数え、申し送りにこう書きました ——「**その道を歩く手（誰に・どう声を
掛けるか）は、1つ も置いていません**」。**置けなかったのは、あの道の距離が「相手の yes」で
決まるから**です（うちの側に腕が 1つ もない）。

成果報酬（説明欄のリンク・ASP）は**同じ門の外**に在って、**距離の形が違います** ——
「件/回（成約率）」で、動かすのは **台本と説明欄** ＝ **うちが毎日 作っている物**。

**この検査が守るのは 5つ**:
  (1) 帯が **3つ とも 1か所** にしかないこと（写しを持たない）
  (2) 成約率の帯は **押す × 成果 の掛け算**から出ること（1つ の数に畳まないこと ＝
      1件 出たときに、どちらが動いたか分けて置き換えられること）
  (3) 倍率の向きが `ungated_yen` と**同じ**（要る率 ÷ 相場・1以下なら届く）で、
      `yen_now`（円/月 の倍率・向きが逆）と混ざらないこと
  (4) `trend` と `status` の**両方**で毎周 印字されること
      （固定2 は `status` で最初に答える問い ＝ `trend` にしか無い行は間に合わない）
  (5) 再生/月 を **`ungated_yen` の 1か所から引く**こと（写しを持たない）
"""
from __future__ import annotations

from studio import trend


def _rows() -> list[dict]:
    return trend.ledger_rows()


def test_帯は3つとも1か所にしかない() -> None:
    with open(trend.__file__, encoding="utf-8") as fh:
        src = fh.read()
    for name in ("PERF_YEN_PER_ACTION_BAND", "PERF_CLICK_BAND", "PERF_CONVERT_BAND"):
        assert src.count(f"{name} = (") == 1, f"{name} の定義が 2か所 以上 に在ります"
        band = getattr(trend, name)
        assert len(band) == 3 and band[0] < band[1] < band[2]


def test_成約率の帯は押すかける成果() -> None:
    """**1つ の数に畳まないこと**（覆る条件 (1) が片側だけ置き換えられるように）。"""
    want = tuple(c * v for c, v in zip(trend.PERF_CLICK_BAND, trend.PERF_CONVERT_BAND))
    assert trend.perf_rate_band() == want
    with open(trend.__file__, encoding="utf-8") as fh:
        assert "PERF_RATE_BAND = (" not in fh.read(), "帯を掛け算の外へ畳まないこと"


def test_倍率の向きは要る率わる相場() -> None:
    """**`ungated_yen` と同じ向き・`yen_now` とは逆**。混ぜたら落ちること。"""
    d = trend.perf_need_rate(_rows())
    assert d["gated"] is False
    if d["need_rate"] is None:
        return
    for lv, b in zip(trend.YEN_LEVELS, d["band"]):
        assert abs(d["times"][lv] - d["need_rate"] / b) < 1e-12
    assert d["times"]["低"] > d["times"]["中"] > d["times"]["高"]


def test_再生月は_ungated_yen_から引く_写しを持たない() -> None:
    """**再生/月 の出どころは 1か所**（`form_yield` を 2度 引き直さないこと）。"""
    u = trend.ungated_yen(_rows())
    d = trend.perf_need_rate(_rows())
    assert d["views_month"] == u["views_month"]
    assert d["cap"]["views_month"] == u["cap"]["views_month"]


def test_天井は要る率を下げる() -> None:
    """日枠が戻った側は **再生/月 が増え、要る成約率は下がる**こと。"""
    d = trend.perf_need_rate(_rows())
    if d["need_rate"] is None:
        return
    c = d["cap"]
    if c["need_rate"] is not None and c["views_month"] > d["views_month"]:
        assert c["need_rate"] < d["need_rate"]


def test_要る件数は目標わる単価() -> None:
    """分子は「単価 × 件数」＝ **件数 は 目標 ÷ 単価**（帯の 3段 とも）。"""
    d = trend.perf_need_rate(_rows())
    if d["need_rate"] is None:
        return
    for lv, y in zip(trend.YEN_LEVELS, d["yen_band"]):
        assert abs(d["actions_month"][lv] - d["goal"] / y) < 1e-9


def test_行は毎周_trend_に出る() -> None:
    with open(trend.__file__, encoding="utf-8") as fh:
        assert "out.append(perf_line(rows))" in fh.read()


def test_行は毎周_status_にも出る() -> None:
    """**固定2 は `status` で最初に答える問い** ＝ `trend` にしか無い行は間に合わない。"""
    from studio import cli
    with open(cli.__file__, encoding="utf-8") as fh:
        assert "trend.perf_short(" in fh.read()


def test_行は成果が出るとは言わない() -> None:
    """**覆る条件 (3)** ＝ この行は 1件の発生を意味しない。字がそう言っていること。"""
    line = trend.perf_line(_rows())
    short = trend.perf_short(_rows())
    assert "『成果が出る』とは言いません" in line
    assert "成果が出るとは言っていません" in short


def test_審査を試していないと字で言う() -> None:
    """**覆る条件 (2)** ＝ 提携の審査は 1度も試していない。黙って前提にしないこと。"""
    assert "1度も試していません" in trend.perf_line(_rows())


def test_門の外は2つになった() -> None:
    """**2026-09-18 15:4x に 1つ 足した。** 14:xx の「4つ のうち門の外は 1つ」は
    **`CLAUDE.md` 2026-08-15 のオーナー原文ではなく、後の回が付けた註**でした
    （原文 615-619行／註 621-622行／同 file 633行「収益の立て方は、全部あなたが決めます」）。

    **覆る条件**: オーナーが「YouTubeの収益 ＝ YouTube から振り込まれる金だけ」と
    言葉を出したら、`成果報酬` を外して 1つ に戻すこと（`perf_need_rate` 覆る条件 (5)）。
    """
    assert set(trend.UNGATED_FORMS) == {"企業案件", "成果報酬"}
    assert set(trend.GATED_FORMS) & set(trend.UNGATED_FORMS) == set()
