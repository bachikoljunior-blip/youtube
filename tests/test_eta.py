"""`scripts/eta.py` —— 月20万に届く日の予測。

**この検査が守っているのは「予測が出ること」ではありません。**
守っているのは、**天井の判定が本数では動かないこと**です。

2026-08-19 の実測で、`1本1,092回 × 92本/日` の上限が
ショート RPM ¥35 で月10.5万円にしかならないことが分かりました。
**本数を増やしても、在庫を増やしても、この数字は動きません。**
ここが逆向きに壊れると（本数を増やせば届くと出ると）、
**また15周ぶん在庫の作業に戻ります。**
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("eta_mod", ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eta)


def _measured(**over):
    """2026-08-19 の実測をそのまま置く（数字を変える検査は over で上書きする）。"""
    base = dict(
        at="2026-08-19T02:30:00+00:00",
        subs_net=9,
        views_all=27_484,
        views_7d=11_002,
        views_28d=20_010,
        views_90d=22_241,
        subs_gained_28d=9,
        subs_gained_90d=11,
        long_hours_365=0.1,
        shorts_views_90d=22_222,
        median_views_per_video=1_092,
        videos_with_views_28d=20,
    )
    base.update(over)
    return base


def test_門の順は_登録者ではなく視聴時間のほうが遠い():
    """**門1より門2のほうが遠い。** ここを取り違えると「登録者を増やせば通る」になる。"""
    a = eta.analyse(_measured())
    assert a["days_subs"] < a["days_long_hours"]
    assert a["days_shorts_gate"] >= eta.NEVER
    # 収益化は「門1 と 門2の速いほう」の両方が要る＝遅いほうで決まる
    assert a["days_monetized"] == a["days_long_hours"]


def test_登録率は実測から出る():
    a = eta.analyse(_measured())
    assert a["sub_rate"] == pytest.approx(9 / 20_010)
    # 予測には速いほう（直近7日）を使う。伸びている最中に遅いほうで測ると悲観に倒れる
    assert a["views_per_day"] == pytest.approx(11_002 / 7)


def test_天井は本数では動かない():
    """**この検査が本体です。** 在庫や本数の作業は、天井を1円も上げません。"""
    a = eta.analyse(_measured())
    ceiling_short = a["ceiling"]["ショート 中"]
    assert ceiling_short < eta.TARGET_YEN, "ショートの上限が目標に届くなら、前提が変わっている"
    # 1本あたりの再生を据え置いたまま「本数が2倍出せるようになった」としても、
    # 上限は UPLOAD_CAP_PER_DAY で頭打ちなので、天井は同じ数字のまま
    a2 = eta.analyse(_measured(views_7d=22_004, views_28d=40_020))
    assert a2["ceiling"]["ショート 中"] == ceiling_short


def test_天井を動かすのは1本あたり再生と_RPM_の2つだけ():
    base = eta.analyse(_measured())["ceiling"]["ショート 中"]
    より上 = eta.analyse(_measured(median_views_per_video=2_184))["ceiling"]["ショート 中"]
    assert より上 == pytest.approx(base * 2)
    # RPM は表そのもの。長尺の帯なら同じ再生数で桁が変わる
    a = eta.analyse(_measured())
    assert a["ceiling"]["長尺 お金 中"] > eta.TARGET_YEN


def test_増えていない数字は_届かない_と出る():
    """0 で割って例外にしないこと。**予測で回を止めない。**"""
    a = eta.analyse(_measured(subs_gained_28d=0, long_hours_365=0.0))
    assert a["days_subs"] >= eta.NEVER
    assert a["days_long_hours"] >= eta.NEVER
    assert "届きません" in eta._fmt_days(a["days_subs"])


def test_門を通り越した数字は_通過済み_と出る():
    a = eta.analyse(_measured(subs_net=1_200))
    assert a["subs_remaining"] == 0
    assert a["days_subs"] == 0
    assert "通過済み" in eta._fmt_days(a["days_subs"])


def test_報告は例外を出さずに全部の行を出す():
    m = _measured()
    a = eta.analyse(m)
    m["per_video_now"] = a["per_video_now"]
    lines = eta.report(m, a)
    text = "\n".join(lines)
    assert "月20万円に、いつ届くか" in text
    # **ショートの帯は必ず「届かない」側に名指しされること。** ここが本体
    assert "ショート 中" in text
    assert "1日の上限まで出しても月20万に届かない帯" in text
    assert "ショート 低" in text.split("届かない帯")[1].split("\n")[0]


def test_百年より先は日付を書かない():
    """`date` の上限を超えると例外になる。**予測で回を止めない**（8/19 に踏んだ）。"""
    assert "年後" in eta._fmt_days(40_000 * 365)


# --- 門2a を長尺で開ける側（2026-08-19 12:0x に足した）---------------------
#
# **足した理由。** この道具は 8/19 の初回から門2について「届きません」しか
# 言えず、段2（M20）が要求している数字を一度も出していませんでした。
# `days_long_hours` は「直近365日の長尺の伸び」をそのまま延ばした数なので、
# 長尺を1本も出していない限り**必ず無限**になります。
# それは「長尺では開かない」ではなく「**まだ試していない**」で、別の命題です。
# ここが混ざったままだと、段1（登録者）を縮める作業ごと無意味に見えます。


def test_門2aの合格点は_長尺を1本も出していなくても出る():
    """**「届かない」と「合格点が無い」は別**。ここが混ざると段2 が判定できない。"""
    a = eta.analyse(_measured(long_hours_365=0.0))
    assert a["days_long_hours"] >= eta.NEVER          # 伸びていないので、延ばせば無限
    rows = a["long_break_even"]
    assert rows, "形ごとの行が出ていない"
    for r in rows:                                    # それでも合格点は有限
        for per_day, views in r["views"].items():
            assert 0 < views < float("inf"), (r["label"], per_day, views)


def test_合格点は_1日に足す長尺の本数に反比例する():
    """本数はこちらで決められる。決められないのは1本あたり再生のほう。"""
    a = eta.analyse(_measured())
    for r in a["long_break_even"]:
        assert r["views"][1] == pytest.approx(r["views"][2] * 2, rel=1e-9)
        assert r["views"][2] == pytest.approx(r["views"][4] * 2, rel=1e-9)


def test_合格点は_残り視聴分と門1の日数の両方から出る():
    """**門1 が遠いほど埋める時間があるので、合格点は下がる。**

    ここが逆向き（門1 が遠いほど厳しくなる）に壊れると、
    「登録者を増やすと長尺の門が閉じる」という有りえない読みになります。
    """
    ゆるい = eta.analyse(_measured(subs_gained_28d=1))    # 登録率が低い＝門1 が遠い
    きつい = eta.analyse(_measured(subs_gained_28d=90))   # 登録率が高い＝門1 が近い
    assert ゆるい["days_subs_at"][eta.PLAN_PUBLISH_PER_DAY] > きつい["days_subs_at"][eta.PLAN_PUBLISH_PER_DAY]
    assert ゆるい["long_break_even"][0]["views"][4] < きつい["long_break_even"][0]["views"][4]


def test_残り視聴分は実測の長尺時間を引いている():
    a = eta.analyse(_measured(long_hours_365=1_000.0))
    assert a["long_minutes_needed"] == pytest.approx((4_000 - 1_000) * 60)


def test_公開密度の行は_門2aの逆算と同じ日数を使う():
    """**2か所で別々に計算すると、必ずずれます。**（report が手で計算していた）"""
    a = eta.analyse(_measured())
    for n in eta.PUBLISH_SCENARIOS:
        assert n in a["days_subs_at"]
    assert eta.PLAN_PUBLISH_PER_DAY in a["days_subs_at"]
    行 = [l for l in eta.report(_measured(), a) if f"1日 {eta.PLAN_PUBLISH_PER_DAY:>3}本 公開" in l]
    assert len(行) == 1
    assert eta._fmt_days(a["days_subs_at"][eta.PLAN_PUBLISH_PER_DAY]) in 行[0]


def test_門2aの節は例外を出さずに出る():
    for over in ({}, {"long_hours_365": 0.0}, {"subs_gained_28d": 0}, {"median_views_per_video": 0}):
        m = _measured(**over)
        lines = eta.report(m, eta.analyse(m))
        assert any("門2a" in l for l in lines), over


def test_測定になっていない無限と_遠いだけの無限を見分ける():
    """**同じ「届きません」でも意味が正反対**。返り値だけでは区別がつかない。

    しきい値は手で決めていません。**延ばした先が100年より遠い＝伸び率が0と
    区別がつかない**、を境にしています（`_days_to` が畳む線と同じ）。
    """
    for h in (0.0, 0.1, 10.0):                            # 実測は 0.1 時間/365日
        a = eta.analyse(_measured(long_hours_365=h))
        assert a["long_untried"] is True, h
    伸びている = eta.analyse(_measured(long_hours_365=400.0))   # 400h/365日
    assert 伸びている["days_long_hours"] < eta.NEVER
    assert 伸びている["long_untried"] is False


def test_未着手のときだけ_長尺の実力ではないと断る():
    出た = eta.report(_measured(long_hours_365=0.0), eta.analyse(_measured(long_hours_365=0.0)))
    assert any("長尺の実力ではありません" in l for l in 出た)
    m = _measured(long_hours_365=400.0)
    出た2 = eta.report(m, eta.analyse(m))
    assert not any("長尺の実力ではありません" in l for l in 出た2)


def test_30再生の床は長尺に当てない():
    """**この検査が、この回の本体です**（2026-08-19 14:2x）。

    `>= 30` の1行が長尺を5本とも落とし、天井の表が
    **ショートの中央値を長尺の帯に当てて「届く」と印字していました。**
    """
    rows = [
        ["short_a", 1_092, 22, 45.0],   # 尺 ~49秒
        ["short_b", 821, 20, 40.0],     # 尺 ~50秒
        ["short_c", 29, 20, 40.0],      # 30未満。**床を外したので残ります**（15:0x）
        ["long_a", 4, 16, 4.6],         # 尺 ~348秒
        ["long_b", 1, 113, 17.0],       # 尺 ~665秒
    ]
    shorts, longs = eta.split_per_video(rows)
    assert shorts == [29, 821, 1_092], "ショートの床は外した（合計を本数で割るため）"
    assert longs == [1, 4], "**長尺に30の床を当てると1本も残らない**"


def test_平均視聴率が0の行は長尺に入れない():
    """尺が割り出せない行を長尺に入れると、測れていない本が中央値を下げます。"""
    shorts, longs = eta.split_per_video([["x", 500, 20, 0.0]])
    assert longs == []
    assert shorts == [500]


def test_長尺の帯は長尺の実測で割る():
    """**混ぜると 36倍 が 0.1倍 に見えます。**"""
    a = eta.analyse(_measured(long_per_video=2, long_videos_28d=5, long_views_28d=11))
    assert a["per_video_by_band"]["長尺 お金 中"] == 2
    assert a["per_video_by_band"]["ショート 中"] == 1_092
    assert a["band_measured"]["長尺 お金 中"] == "長尺"
    # 要る 72回 ÷ 実測 2回 = 36倍（ショートの 1,092 で割ると 0.07倍 に見える）
    assert a["per_video_ratio"]["長尺 お金 中"] == pytest.approx(72 / 2, rel=0.02)
    assert a["ceiling"]["長尺 お金 中"] < eta.TARGET_YEN, \
        "長尺の実測を当てたら、長尺の帯も上限は目標の下"


def test_長尺の実測が無いときはショートで代用したと断る():
    """**代用したことを黙らないこと。** 黙ると、次の回が実測だと読みます。"""
    a = eta.analyse(_measured())          # long_per_video が無い
    assert a["long_per_video"] is None
    assert a["band_measured"]["長尺 お金 中"] == "ショート"
    assert a["ceiling"]["長尺 お金 中"] > eta.TARGET_YEN
    line = "\n".join(eta.report(_measured(), a))
    assert "測れていません" in line and "代用" in line


def test_長尺の実測があるときは_合格点と突き合わせて出す():
    m = _measured(long_per_video=2, long_videos_28d=5, long_views_28d=11)
    a = eta.analyse(m)
    m["per_video_now"] = a["per_video_now"]
    line = "\n".join(eta.report(m, a))
    assert "測れています" in line, "**「未測定」と書き続けると、誰とも突き合わせません**"
    assert "未測定" not in line.split("--- **門2a")[1]
    assert "133倍" in line or "倍**" in line


# ---------------------------------------------------------------------------
# **天井は中央値ではなく平均で出す**（2026-08-19 15:0x）
#
# 天井は「N本ぶんの**合計**」なので、合計 ＝ N × **平均**。
# 中央値を掛けてよいのは分布が対称なときだけで、ショートの再生は必ず右に歪みます。
# ---------------------------------------------------------------------------


def test_ショートの床は外れている_落ちた本も本数に数えるから():
    """`>= 30` は標本からは落とすが、天井の 92本 からは落とさない。

    **落ちた本まで「通った本と同じだけ回る」ことになっていた**のが穴です。
    """
    rows = [
        ["a", 1_000, 20, 40.0],
        ["b", 1, 20, 40.0],      # 伸びなかった本。**天井の92本には入っている**
    ]
    shorts, longs = eta.split_per_video(rows)
    assert shorts == [1, 1_000]
    assert longs == []


def test_天井は平均で出す_中央値だと歪んだぶんだけ上振れする():
    a_mean = eta.analyse(_measured(views_per_video=909, median_views_per_video=1_092))
    a_median = eta.analyse(_measured(views_per_video=1_092, median_views_per_video=1_092))
    assert a_mean["per_video_now"] == 909
    assert a_mean["ceiling"]["ショート 高"] < a_median["ceiling"]["ショート 高"]
    # **倍率は 1.1倍 → 1.33倍**。ここが「どの帯がいちばん近いか」を決めます。
    assert a_mean["per_video_ratio"]["ショート 高"] > a_median["per_video_ratio"]["ショート 高"]
    assert round(a_mean["per_video_ratio"]["ショート 高"], 2) == 1.33


def test_公開密度の段も平均で出す_門1の日付が変わる():
    """`days_subs_at` が中央値のままだと、門1だけ上振れした日付になります。"""
    a_mean = eta.analyse(_measured(views_per_video=909, median_views_per_video=1_092))
    a_median = eta.analyse(_measured(views_per_video=1_092, median_views_per_video=1_092))
    assert a_mean["days_subs_at"][25] > a_median["days_subs_at"][25]


def test_古い点には平均が無い_中央値へ落ちる():
    """`data/eta.jsonl` の8点目までに `views_per_video` はありません。

    **無い点を 0 と読むと、差の節が -100% と印字します。**
    """
    old_point = _measured()
    old_point.pop("views_per_video", None)
    assert eta._per_video(old_point) == old_point["median_views_per_video"]
    a = eta.analyse(old_point)
    assert a["per_video_now"] == 1_092


def test_物差しを取り替えた点は_差の節が実績と読ませない(tmp_path, monkeypatch):
    """9点目までは「床つきの中央値」、10点目からは「床なしの平均」。

    **チャンネルが何も変わっていないのに 1,092 → 869 と出ます。**
    差の節は「作業が効いたか」を見る所なので、断らないと
    **物差しの取り替えが、実績の悪化として次の回の判断に入ります。**
    """
    log = tmp_path / "eta.jsonl"
    old = _measured(median_views_per_video=1_092)
    old.pop("views_per_video", None)
    old["per_video_now"] = 1_092
    old["days_subs"] = 1_402
    old["days_monetized"] = eta.NEVER
    log.write_text(json.dumps(old, ensure_ascii=False) + "\n", encoding="utf-8")
    monkeypatch.setattr(eta, "LOG", log)

    cur = _measured(views_per_video=869, median_views_per_video=821)
    cur["per_video_now"] = 869
    cur["days_subs"] = 1_402
    cur["days_monetized"] = eta.NEVER
    lines = "\n".join(eta._drift(cur))
    assert "物差しが、この点から変わりました" in lines
    assert "上の変化は実績ではありません" in lines

    # 物差しが揃っている2点では、断りは出ません（毎回出ると意味が薄れます）
    log.write_text(json.dumps(cur, ensure_ascii=False) + "\n", encoding="utf-8")
    lines2 = "\n".join(eta._drift(cur))
    assert "物差しが、この点から変わりました" not in lines2


def test_実データが動いていない回は_効いていないと言わない(tmp_path, monkeypatch):
    """**18周ぶんの実測から直した**（2026-08-19 21:2x）。

    Analytics は日次で3日遅れ、回は約41分ごと。**1日のうち入力は1度も動きません。**
    `data/eta.jsonl` の18点は `views_7d` も `subs_net` も全部同値でした。
    それでもここは毎回「**作業で縮んだぶん -0.0日 ← 効いていません**」と印字し、
    **その回が何をしたかと無関係に、常に同じ字**を出していました。

    「効いていません」は**判定**です。**測れていないものを判定にしないこと。**
    """
    log = tmp_path / "eta.jsonl"
    same = _measured()
    same["per_video_now"] = 869
    same["days_subs"] = 1_402
    same["days_monetized"] = eta.NEVER
    log.write_text(json.dumps(same, ensure_ascii=False) + "\n", encoding="utf-8")
    monkeypatch.setattr(eta, "LOG", log)

    cur = dict(same, at="2026-08-19T03:10:00+00:00")
    lines = "\n".join(eta._drift(cur))
    assert "実データがまだ動いていません" in lines
    assert "ここでは測れません" in lines
    assert "効いていません" not in lines, "測れていないものを判定にしています"


def test_実データが動いた回は_これまでどおり差を出す(tmp_path, monkeypatch):
    """**黙らせすぎないこと。** 入力が動いた回では、差は今までどおり出ます。"""
    log = tmp_path / "eta.jsonl"
    old = _measured()
    old["per_video_now"] = 869
    old["days_subs"] = 1_402
    old["days_monetized"] = eta.NEVER
    log.write_text(json.dumps(old, ensure_ascii=False) + "\n", encoding="utf-8")
    monkeypatch.setattr(eta, "LOG", log)

    cur = _measured(at="2026-08-20T03:10:00+00:00", views_7d=22_004, subs_net=18)
    cur["per_video_now"] = 869
    cur["days_subs"] = 700
    cur["days_monetized"] = eta.NEVER
    lines = "\n".join(eta._drift(cur))
    assert "実データがまだ動いていません" not in lines
    assert "門1（登録者1,000人）" in lines


def test_同値の点が続いても_入力が違う最後の点と比べる(tmp_path, monkeypatch):
    """**同じ値どうしを引いても 0 しか出ません。**

    18点が同値のまま積まれる形（実物）で、比べる相手が
    「1つ前」だと永久に 0 です。**入力が実際に違う最後の点**を選ぶこと。
    """
    log = tmp_path / "eta.jsonl"
    older = _measured(at="2026-08-18T02:30:00+00:00", views_7d=5_000)
    older.update(per_video_now=869, days_subs=2_000, days_monetized=eta.NEVER)
    same = _measured(at="2026-08-19T02:30:00+00:00")
    same.update(per_video_now=869, days_subs=1_402, days_monetized=eta.NEVER)
    log.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in (older, same)) + "\n",
                   encoding="utf-8")
    monkeypatch.setattr(eta, "LOG", log)

    cur = dict(same, at="2026-08-19T03:10:00+00:00")
    lines = "\n".join(eta._drift(cur))
    assert "実データがまだ動いていません" in lines
    # 比べる相手は older（2,000日）なので、門1の行が出る
    assert "2,000日 → 1,402日" in lines


# ======================================================================
# **1本あたり再生の標本に、入れてよい本の条件**（2026-08-20 03:1x に足した）
#
# 天井は `1本あたり再生 × 92本 × 30日`。この「1本あたり再生」が
# **一生ぶんの再生数**でなければ、掛け算そのものが意味を持ちません。
# 実測では、まだ公開していない予約の本が **1再生の行**で標本に入っていました。
# **予約は 359本**あるので、放っておくと**本数を増やすほど天井が下がります。**
# ======================================================================

from datetime import datetime, timedelta, timezone  # noqa: E402

_NOW = datetime(2026, 8, 20, 3, 0, tzinfo=timezone.utc)


def _pub(**kw):
    return {k: _NOW - timedelta(hours=v) for k, v in kw.items()}


def test_まだ公開していない本は標本から落ちる():
    """**この検査が、この回の本体です。**

    実測 `KdlvGxloIg4` は `uploaded.jsonl` の `at` が **08/24**（予約）なのに、
    Analytics には **1再生**の行が立っていました。予約は 359本あります。
    """
    rows = [["done", 1_000, 20, 40.0], ["yoyaku", 1, 20, 40.0]]
    pub = {"done": _NOW - timedelta(days=5), "yoyaku": _NOW + timedelta(days=4)}
    kept, dropped = eta.drop_unripe(rows, pub, _NOW)
    assert [r[0] for r in kept] == ["done"]
    assert dropped["未公開"] == ["yoyaku"]


def test_年齢の引けない本も未公開に入れる():
    """**一度も観測されていない本は、公開されたことを示すものが何もありません。**"""
    kept, dropped = eta.drop_unripe([["nazo", 1, 20, 40.0], ["ok", 900, 20, 40.0]],
                                    {"ok": _NOW - timedelta(days=5)}, _NOW)
    assert [r[0] for r in kept] == ["ok"]
    assert dropped["未公開"] == ["nazo"]


def test_48時間経っていない本は落ちる_伸びが終わっていないから():
    """実測（`data/views.jsonl` n=9）: 24時間で中央値 99.1%・48時間で 100%。

    **それより若い本は、一生ぶんではなく数時間ぶんを持って平均に入ります。**
    """
    rows = [["wakai", 200, 20, 40.0], ["jukusi", 1_000, 20, 40.0]]
    kept, dropped = eta.drop_unripe(rows, _pub(wakai=10, jukusi=120), _NOW)
    assert [r[0] for r in kept] == ["jukusi"]
    assert dropped["未熟"] == ["wakai"]
    assert eta.MATURE_HOURS == 48


def test_ちょうど48時間の本は残る():
    kept, _ = eta.drop_unripe([["x", 900, 20, 40.0]], _pub(x=48), _NOW)
    assert [r[0] for r in kept] == ["x"]


def test_28日の窓より前に公開した本は落ちる():
    """**チャンネルが古くなるだけで天井が下がる**のを止める検査。

    伸びは48時間で終わるので、窓に落ちているのは**尻尾だけ**です。
    それを「1本あたり」として平均に入れると、**時間が経つほど下がり続けます。**
    """
    rows = [["furui", 3, 20, 40.0], ["mado", 1_000, 20, 40.0]]
    kept, dropped = eta.drop_unripe(rows, _pub(furui=24 * 40, mado=24 * 5), _NOW,
                                    window_days=28)
    assert [r[0] for r in kept] == ["mado"]
    assert dropped["窓の外"] == ["furui"]


def test_落とし先が無くなったら落とさない():
    """`views.jsonl` は Data API の読みで作るので、**日枠が閉じると更新が止まります**
    （実測 08/18 09:08 で 1.7日）。**年齢が全部欠けたときに標本を空にすると、
    天井が黙って 0 になります。**
    """
    rows = [["a", 900, 20, 40.0], ["b", 1_000, 20, 40.0]]
    kept, dropped = eta.drop_unripe(rows, {}, _NOW)
    assert len(kept) == 2, "**全部落ちるくらいなら、落とさない**"
    assert dropped["落とし先なし"] == ["a", "b"]
    assert "未公開" not in dropped


def test_落とした本数は測定の返りに載る_黙って消えないため():
    m = _measured(per_video_dropped={"未公開": 2})
    出た = eta.report(m, eta.analyse(m))
    assert any("未公開" in l and "2本" in l for l in 出た)


def test_落とした本が0件でもその旨を出す():
    m = _measured(per_video_dropped={})
    出た = eta.report(m, eta.analyse(m))
    assert any("落とした本はありません" in l for l in 出た)


def test_落とし先なしは下振れ側で読めと断る():
    m = _measured(per_video_dropped={"落とし先なし": 21})
    出た = eta.report(m, eta.analyse(m))
    assert any("年齢が1本も引けませんでした" in l for l in 出た)


def test_公開時刻は観測の時刻ではない(tmp_path):
    """`build_perf.first_seen()` は**最初に観測した時刻**で、公開より必ず後です
    （実測で最大 38.7時間の遅れ）。**年齢の門に遅れるほうを使ってはいけません。**
    """
    views = tmp_path / "views.jsonl"
    views.write_text(
        json.dumps({"at": "2026-08-08T00:00:00Z", "id": "v", "hours": 38.7, "views": 500}) + "\n"
        + json.dumps({"at": "2026-08-09T00:00:00Z", "id": "v", "hours": 62.7, "views": 520}) + "\n",
        encoding="utf-8")
    pub = eta.published_at(views_path=views, uploaded_path=tmp_path / "nai.jsonl")
    assert pub["v"] == datetime(2026, 8, 6, 9, 18, tzinfo=timezone.utc), \
        "**at - hours**（観測の時刻ではなく、そこから遡った公開時刻）"


def test_控えは観測を上書きしない_観測のほうが正確():
    """`uploaded.jsonl` の `at` は**予約した時刻**で、実際の公開とはずれます。"""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "views.jsonl").write_text(
            json.dumps({"at": "2026-08-08T00:00:00Z", "id": "v", "hours": 24.0, "views": 5}) + "\n",
            encoding="utf-8")
        (d / "uploaded.jsonl").write_text(
            json.dumps({"video_id": "v", "at": "2026-08-01T00:00:00Z"}) + "\n"
            + json.dumps({"video_id": "w", "at": "2026-08-24T00:00:00Z"}) + "\n",
            encoding="utf-8")
        pub = eta.published_at(views_path=d / "views.jsonl", uploaded_path=d / "uploaded.jsonl")
    assert pub["v"] == datetime(2026, 8, 7, 0, 0, tzinfo=timezone.utc)
    assert pub["w"] == datetime(2026, 8, 24, 0, 0, tzinfo=timezone.utc), \
        "観測に無い本は、控えの予約時刻でしか年齢が分からない"


def test_標本を取り替えた点も_差を実績と読ませない(tmp_path, monkeypatch):
    """**取り替えは良くなる側にも出ます**（869 → 952 ＝ +9.6%）。

    断らないと、次の回が**この回の作業が効いた**と読みます。
    `views_per_day` も `sub_rate` も1つも動いていないのに、です。
    """
    log = tmp_path / "eta.jsonl"
    prev = _measured(views_per_video=869, median_views_per_video=821)
    prev["per_video_now"] = 869
    prev["days_subs"] = 1_402
    prev["days_monetized"] = eta.NEVER
    log.write_text(json.dumps(prev, ensure_ascii=False) + "\n", encoding="utf-8")
    monkeypatch.setattr(eta, "LOG", log)

    cur = _measured(views_per_video=952, median_views_per_video=1_035,
                    per_video_dropped={"未公開": 2})
    cur["per_video_now"] = 952
    cur["days_subs"] = 1_402
    cur["days_monetized"] = eta.NEVER
    lines = "\n".join(eta._drift(cur))
    assert "標本が、この点から変わりました" in lines
    assert "上の変化は実績ではありません" in lines

    # 揃った2点では出ません（毎回出ると意味が薄れます）
    log.write_text(json.dumps(cur, ensure_ascii=False) + "\n", encoding="utf-8")
    assert "標本が、この点から変わりました" not in "\n".join(eta._drift(cur))
