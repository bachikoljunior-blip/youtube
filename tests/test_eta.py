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
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("eta_mod", ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eta)

# --- **この file の合成データは、1日の再生の天井より前に書かれています**（2026-08-21 16:2x） ---
#
# `src/day_cap.py` の実測 —— 08/20 は 25本 公開して **#11から先の15本が 0〜3再生**。
# `solve_gate1` はそれ以来「出した本数」ではなく**再生が付いた本数**で門を解きます。
#
# ここの合成データ（`_measured()` 系）はその天井より前に置かれていて、
# 天井をかぶせると**どの帯にも届かなくなり**、この file の主題
# （**段取りが空で返らないこと・段4 が20万の日付であること**）が測れません。
# **`view_cap` を明示して縛らせません。** 天井そのものは
# `tests/test_eta_day_cap.py` が持ちます（**隠さず、置き場所を分けています**）。
_UNCAPPED = eta.UPLOAD_CAP_PER_DAY

# --- **2026-08-22: 同じことが RPM の側でも起きました** ---
#
# `plan()` は `src/rpm_mix.last()`（実効 RPM の天井）も実測から直に読みます。
# 08/20 の初測で 帯¥400 → 実効¥253 に落ち、合格点（月に要る再生）が 1.58倍に。
# **形は1行も変わっていないのに** `days_to_target` が `NEVER` へ潰れました。
# 天井は2つあるので、**2つとも止めます**（理由と置き場所は `tests/_eta_pin.py`）。
import _eta_pin  # noqa: E402  （pytest が tests/ を sys.path に入れます）


@pytest.fixture(autouse=True)
def _天井は主題ではない(monkeypatch):
    _eta_pin.pin_mix(monkeypatch)



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
    # **要る回数 ÷ 実測 2回**（ショートの 1,092 で割ると、桁が2つ下がって見える）。
    # **要る回数そのものを定数で書かないこと**（2026-08-25）——
    # ここは長らく `72` で、それは**天井の分母が 92本/日 だった頃の数**でした。
    # 分母は `day_cap.cap()` へ移っています（実測10本/日）。定数で書くと、
    # **この検査が、直したはずの分母を裏から固定し直します。**
    need = a["per_video_needed"]["長尺 お金 中"]
    assert a["per_video_ratio"]["長尺 お金 中"] == pytest.approx(need / 2)
    assert a["per_video_ratio"]["長尺 お金 中"] != pytest.approx(need / 1_092), \
        "ショートの実測で割っています（**混ぜると桁が2つ変わります**）"
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
    # ここが「どの帯がいちばん近いか」を決めます。
    # **倍率そのものを定数で書かないこと**（2026-08-25）—— 昔の `1.33` は
    # **天井の分母が 92本/日 だった頃の数**でした。この検査の主題は
    # 「平均か中央値か」なので、**2つの比だけを見ます**（分母は約分で消えます）。
    assert a_mean["per_video_ratio"]["ショート 高"] > a_median["per_video_ratio"]["ショート 高"]
    assert (a_mean["per_video_ratio"]["ショート 高"]
            / a_median["per_video_ratio"]["ショート 高"]) == pytest.approx(1_092 / 909)


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

from datetime import date as _date, datetime, timedelta, timezone  # noqa: E402

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


# ======================================================================
# **段取り**（オーナー指示 2026-08-20 06:2x）
#
# > 「予測は達成できないで終わらせず、達成できるまでのプランを決めるようにして」
#
# ここが守っているのは「良い計画が出ること」ではありません。守っているのは
# **どんな入力でも、日付の入った段取りが必ず1つ返ること**と、
# **その段取りが上振れ側の数字に乗っていないこと**の2つです。
#
# **既知の当たりは、実データではなく手で作った行に置いています**
# （`docs/trigger_main.md` §4「その既知の当たりを、実データの偶然に置かないこと」）。
# 実測が動いても意味が変わらないのは、この2つが**算術の不変量**だからです。
# ======================================================================


def _analysed(**over):
    m = _measured(**over)
    return m, eta.analyse(m)


def test_段取りは_どの帯も届かない入力でも空で返らない():
    """**これがこの節の本体です。**

    2026-08-20 まで、この道具は `data/eta.jsonl` の29点すべてで
    「どの帯でも届きません」で終わっていて、**日付が1つも出ていませんでした。**
    """
    # 2026-08-20 の実測と同じ側に置く: 長尺は n=5・1本 2回（登録者9人の頃の標本）。
    # これが入ると天井の表は**6行とも「届かない」**になります。
    m, a = _analysed(long_per_video=2.2, long_videos_28d=5, long_views_28d=11)
    # 前提: この入力は「どの帯でも届かない」側（ここが変わったら検査の意味が変わる）
    assert all(a["ceiling"][k] < eta.TARGET_YEN for k in eta.RPM_SCENARIOS)

    pl = eta.plan(m, a, view_cap=_UNCAPPED)
    assert pl["stages"], "段取りが空で返った"
    assert pl["stages"][-1]["when"] < eta.NEVER, "最後の段に日付が入っていない"
    assert pl["blocking"]["what"], "止めている入力が名指しされていない"


def test_段取りは_出せる密度で解く_APIの日枠では解かない():
    """92本/日 は API の日枠であって、出せる本数ではありません。

    ここが 92 に戻ると、要る1本あたり再生が 1/3.7 になって
    **実際には出せない計画が「届く」に見えます。**
    """
    m, a = _analysed()
    pl = eta.plan(m, a)
    assert pl["density"] == eta.PLAN_PUBLISH_PER_DAY
    assert pl["density"] < eta.UPLOAD_CAP_PER_DAY
    # **割るのは「再生が付く本数」のほう**（2026-08-21 16:2x に分けた）。
    #     `density` は詰め方、`density_month` は**そのうち再生が付くぶん**で、
    #     上に `src/day_cap.py` の実測（08/20 は #11から先の15本が 0〜3再生）が
    #     もう1枚かぶります。**92本/日 で割らないこと**が、この検査の主題です。
    assert pl["density_month"] <= pl["density"]

    # **要る月間再生は、帯（`views_needed_month`）そのものではありません**
    #     （2026-08-20 23:2x）。段4 の RPM は**実測の混ざり方の天井**で頭打ちに
    #     なるので、帯 ¥400 のときは ¥313 が当たります（`test_eta_surface_cap.py`）。
    #     **この検査が守っているのは分母のほう** ——「92本/日 で割っていないか」です。
    spine = pl["forms"][pl["spine"]]
    need_month = spine["views_needed_month"]
    assert spine["per_video_needed"] == pytest.approx(
        need_month / (pl["density_month"] * 30))
    assert spine["per_video_needed"] != pytest.approx(
        need_month / (eta.UPLOAD_CAP_PER_DAY * 30)
    ), "API の日枠 92本/日 で割っています（**出せる本数ではありません**）"
    # 帯そのものは残っていること（頭打ちの相手が消えると、甘さを測れません）
    assert spine["rpm_band"] == eta.RPM_SCENARIOS[pl["spine_band"]]


def test_段取りは_その形のいちばん低いRPMで立てる():
    """低/中/高 は「別の道」ではなく**同じニッチの幅**です。

    倍率の小さい帯を選ぶ論法をそのまま当てると、**必ず「高」が出ます** ——
    計画そのものが上振れ側に乗ります。
    """
    m, a = _analysed()
    pl = eta.plan(m, a)
    for form, f in pl["forms"].items():
        same_form = [k for k in eta.RPM_SCENARIOS if k.startswith(form)]
        low = min(eta.RPM_SCENARIOS[k] for k in same_form)
        # **選ぶ帯は「低」のまま。** 実際に当てる RPM は、そこから
        #     実測の混ざり方の天井で**下へ**頭打ちになります（2026-08-20 23:2x）。
        #     **上へ動いていたら、それは上振れ側なので落とすこと。**
        assert f["rpm_band"] == low, form
        assert f["rpm"] <= low, form


def test_段取りの物差しは_ショートの実測であって長尺の古い標本ではない():
    """長尺の実測 2回 は「登録者9人の頃に出した5本」で、長尺の実力ではありません（M20）。

    ここで割ると、**長尺の段が必ず数十倍に見えて、計画から落ちます。**
    """
    m, a = _analysed()
    pl = eta.plan(m, a)
    per_video = a["per_video_now"]
    for f in pl["forms"].values():
        assert f["ratio_vs_shorts"] == pytest.approx(f["per_video_needed"] / per_video)


# --- **段4 は「20万の日付」でなければならない**（2026-08-20 08:1x・オーナー追記） ---
#
#   > 勝手に20万達成以外の日時の予測だけにしないで
#
# ここは `d_target = d_monetized` の1行で、**段3（収益化の審査が終わる日）を
# 段4の期日として印字**していました。下の検査は、その1行が戻ったら落ちます。

def test_段4は_段3の日付の写しではない():
    """**同じ日にならないこと。** 収益化した日に入るのはその日ぶんの収入です。"""
    m, a = _analysed()
    pl = eta.plan(m, a)
    d3 = next(s for s in pl["stages"] if s["no"] == 3)["when"]
    d4 = next(s for s in pl["stages"] if s["no"] == 4)["when"]
    assert d4 != d3, "段4 の期日に、段3（収益化）の日付をそのまま代入している"
    assert pl["days_to_target"] == d4


def test_段4は_収益の30日窓のぶんだけ段3より後ろ():
    """月20万は**30日ぶんの合計**。収益化前の再生は1円も生まないので前借りできません。"""
    m, a = _analysed()
    pl = eta.plan(m, a, view_cap=_UNCAPPED)
    d3 = next(s for s in pl["stages"] if s["no"] == 3)["when"]
    assert pl["days_to_target"] == pytest.approx(d3 + eta.REVENUE_WINDOW_DAYS)


def test_段4の合格点は_20万の条件で動く_門の日付では動かない(monkeypatch):
    """**目標額を動かすと、段4の合格点だけが動く。** 段1〜段3 は1日も動きません。

    段3の写しなら、目標額を10倍にしても**何も動きません** —— 門の日付は
    20万がいくらかを知らないからです。ここが「20万の予測になっているか」の芯。

    **日数そのものは動きません**（動かないのが正しい）。要る倍率が 0.70 → 7.00 に
    なっても、この機械は**1本あたり再生の伸び率を持っていない**ので、
    「7倍に何日かかるか」は出せません。出せるのは**最早**のほうだけで、
    だから道具は `conditional` を立てて「見込みではない」と断ります。
    **伸び率を測ったら、ここに日数が入ります。**
    """
    m, a = _analysed()
    pl = eta.plan(m, a)

    monkeypatch.setattr(eta, "TARGET_YEN", eta.TARGET_YEN * 10)
    m2, a2 = _analysed()
    pl2 = eta.plan(m2, a2)

    for no in (1, 2, 3):
        before = next(s for s in pl["stages"] if s["no"] == no)["when"]
        after = next(s for s in pl2["stages"] if s["no"] == no)["when"]
        assert before == pytest.approx(after), f"段{no} が目標額で動いている"

    # 段4 の合格点は、目標額に**比例して**上がる（門の日付は素通り）
    assert pl2["target"]["need_per_video"] == pytest.approx(
        pl["target"]["need_per_video"] * 10)
    assert pl2["target"]["ratio"] == pytest.approx(pl["target"]["ratio"] * 10)
    assert pl2["days_to_target"] >= pl["days_to_target"]
    assert pl2["target"]["conditional"] is True


def test_合格点が立っていないなら_確かめる日より前には到達しない():
    """**立っていない合格点の上に期日を置かない。**

    要るのが ×N なら、その N が本当かを確かめられる最短の日（公開の翌日 →
    伸びきる48時間 → Analytics 3日遅れ）より前に、到達日は来ません。
    """
    m, a = _analysed()
    a["per_video_now"] = 1.0          # 合格点が立たない側へ倒す
    pl = eta.plan(m, a, today=_date(2026, 8, 20))
    t = pl["target"]
    assert not t["met"]
    assert t["ratio"] > 1
    assert t["conditional"] is True
    # 1日後に公開 → 伸びきる（`MATURE_HOURS`）→ 読める（`ANALYTICS_LAG_DAYS`・**実測**）
    # **日数も日付も焼き込まないこと（2026-08-26）** —— 遅れは `src/settle.py` の実測で動きます
    _lag = math.ceil(eta.MATURE_HOURS / 24) + eta.ANALYTICS_LAG_DAYS
    assert t["verify_day"] == 1 + _lag
    # **日付そのものを持つこと**（`_fmt_days` は UTC に足すので JST 早朝に1日ずれる）
    assert t["verify_on"] == _date(2026, 8, 21) + timedelta(days=_lag)
    assert t["bar_day"] >= t["verify_day"]
    assert pl["days_to_target"] == pytest.approx(t["bar_day"] + eta.REVENUE_WINDOW_DAYS)


def test_倍率が1を切っていても_別の形の実測なら合格点は立っていない():
    """**段4 が立てているのは長尺で、割っているのはショートの実測です。**

    ここを「立っている」と言うと、20万の期日がまた
    **測っていない数字の写し**になります（追記が名指ししている穴と同じ形）。
    """
    m, a = _analysed()                       # 長尺の実測は無い＝物差しはショート
    pl = eta.plan(m, a, view_cap=_UNCAPPED)
    assert pl["spine"].startswith("長尺")
    assert pl["target"]["ratio"] < 1.0, "前提: 倍率は1を切っている側"
    assert pl["target"]["proxy"] is True
    assert pl["target"]["met"] is False, "別の形の実測で「立っている」と言っている"
    assert pl["target"]["conditional"] is True

    # 長尺を十分に測ったら、推測ではなくなる
    a2 = dict(a, long_per_video=800.0, long_videos_28d=25)
    pl2 = eta.plan(m, a2, view_cap=_UNCAPPED)
    assert pl2["target"]["proxy"] is False
    assert pl2["target"]["met"] is True


def test_門が届かない側でも_日付を1つ出す():
    """**「届きません」で終わらせない**（追記の後半）。

    登録が28日で0件なら、倍率では出ません（0を何倍しても0）。出るのは
    「1人でも出れば」のほうなので、その線で日付を引きます。
    """
    m, a = _analysed(subs_gained_28d=0)
    assert a["days_subs_at"][eta.PLAN_PUBLISH_PER_DAY] >= eta.NEVER
    pl = eta.plan(m, a, view_cap=_UNCAPPED)
    assert pl["days_to_target"] < eta.NEVER, "段4 が「届きません」で畳まれている"
    assert pl["target"]["fallback"] is not None
    assert pl["target"]["conditional"] is True


def test_段4の日付は画面に出る_道具が知っているのに黙らない():
    m, a = _analysed()
    lines = eta._report_plan(m, a)
    assert any("その日付は、どこから出ているか" in l for l in lines)
    assert any("日ぶん積んだ合計" in l for l in lines)


def test_段取りは例外を出さずに全部の行を出す():
    m, a = _analysed()
    lines = eta._report_plan(m, a)
    assert lines
    assert any("段取り" in l for l in lines)
    assert any("この回の一手" in l for l in lines)


def test_長尺の実測が十分に増えたら_止めている入力が入れ替わる():
    """**未知が消えたのに同じ1手を言い続けないこと。**

    `long_videos_28d` が 20本を超えたら、長尺の1本あたりはもう推測ではありません。
    """
    m, a = _analysed()
    a["long_per_video"] = 800.0
    a["long_videos_28d"] = 25
    pl = eta.plan(m, a)
    assert pl["blocking"]["what"] != "長尺の1本あたり再生"


# --- **測定が返ってくる日**（2026-08-20 07:1x に足した） -----------------------
#
# **既知の当たりを先に固定します**（`docs/trigger_main.md` §4）。
# 手で数えた1件: `data/uploaded.jsonl` の実物（2026-08-20 時点）は
# 08/20〜08/27 が埋まり、08/28〜09/01 に薄く入り、**09/02 と 09/03 が0本**。
# 08/19 の申し送りは3回続けて `--date 2026-09-02` を指しており、
# **それは「いちばん近い穴」であって「いちばん早く測れる日」ではありません。**

def _uploaded(tmp_path, days):
    """`{日付: 本数}` から控えを1本作る（`at` だけ見ています）。"""
    p = tmp_path / "uploaded.jsonl"
    rows = []
    for d, n in days.items():
        for i in range(n):
            rows.append(json.dumps({"at": f"{d}T{9 + i:02d}:00:00+09:00"}))
    p.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return p


def test_答えが返る日は_伸びきる48時間とAnalyticsの3日遅れの和():
    """公開から **5日**。どちらか片方を落とすと、次の回が早すぎる日に測ります。"""
    # **日付を焼き込まないこと（2026-08-26）** —— 遅れは実測で動きます（`src/settle.py`）
    assert eta.answer_day(_date(2026, 8, 21)) == _date(2026, 8, 21) + timedelta(
        days=math.ceil(eta.MATURE_HOURS / 24) + eta.ANALYTICS_LAG_DAYS)


def test_いちばん近い穴は_いちばん早く測れる日ではない(tmp_path):
    """**手で数えた当たり**: 明日は 08/21、いちばん近い穴は 09/02 で **12日** 差。"""
    up = _uploaded(tmp_path, {
        "2026-08-20": 2, "2026-08-21": 2, "2026-08-22": 2, "2026-08-23": 2,
        "2026-08-24": 2, "2026-08-25": 2, "2026-08-26": 2, "2026-08-27": 2,
        "2026-08-28": 1, "2026-08-29": 1, "2026-08-30": 1, "2026-08-31": 1,
        "2026-09-01": 1, "2026-09-04": 1, "2026-09-05": 1,
    })
    t = eta.measure_targets(_date(2026, 8, 20), uploaded_path=up)
    assert t["soonest"] == _date(2026, 8, 21)
    assert t["hole"] == _date(2026, 9, 2)
    assert t["days_lost"] == 12
    assert t["answer_soonest"] == eta.answer_day(t["soonest"])
    assert t["answer_hole"] == eta.answer_day(t["hole"])


def test_穴が無ければ失うものも無い(tmp_path):
    up = _uploaded(tmp_path, {"2026-08-20": 1, "2026-08-21": 1, "2026-08-22": 1})
    t = eta.measure_targets(_date(2026, 8, 20), uploaded_path=up)
    assert t["hole"] is None
    assert t["days_lost"] == 0


def test_控えが空でも落ちない(tmp_path):
    up = tmp_path / "uploaded.jsonl"
    up.write_text("", encoding="utf-8")
    t = eta.measure_targets(_date(2026, 8, 20), uploaded_path=up)
    assert t["soonest"] == _date(2026, 8, 21)
    assert t["hole"] is None


def test_止めている入力に_いつ答えが返るかが載る():
    """**「どう測るか」だけでは、いつ測るかを決められません。**

    ここが空いていた間、測定の日は「穴埋めの都合」で選ばれていました。
    """
    m, a = _analysed()
    pl = eta.plan(m, a, today=_date(2026, 8, 20))
    b = pl["blocking"]
    assert b["what"] == "長尺の1本あたり再生"
    assert b["targets"]["soonest"] == _date(2026, 8, 21)
    assert b["targets"]["answer_soonest"] == eta.answer_day(b["targets"]["soonest"])


def test_未知が消えたら_返る日の欄も消える():
    """測るものが無い回に「いつ測るか」を出さない（読み手が的を探し始めます）。"""
    m, a = _analysed()
    a["long_per_video"] = 800.0
    a["long_videos_28d"] = 25
    pl = eta.plan(m, a, today=_date(2026, 8, 20))
    assert pl["blocking"]["targets"] is None


def test_遅れる日数は画面に出る_道具が知っているのに黙らない():
    """**この repo で通算9件ある「片方だけ」**を避けます —— 計算しても出さないなら同じ。

    **段取りは、この検査の中で立てること**（2026-08-20 18:xx に直した）。
    `_report_plan(m, a)` は第3引数を省くと `supply_state()` ——
    つまり **`data/supply.jsonl` の実物**を読みます。作る速さが 0本/日 に
    落ちている回は `blocking` が「段1の登録率」に変わり、そこに `targets` は
    付きません。**この検査は赤くなりますが、道具は黙っていません** ——
    別の入力を止めていると正しく言っているだけです。
    **手元のファイルで結果が変わる検査は、何も守っていません。**
    """
    m, a = _analysed()
    lines = eta._report_plan(m, a, eta.plan(m, a))
    assert any("いつ答えが返るか" in l for l in lines)


def test_今日はJSTで読む_UTCの日付ではない(monkeypatch):
    """**JST の 00:00〜09:00 は、UTC ではまだ前日です。**

    最初の版は `date.today()`（＝コンテナの TZ・UTC）を読み、
    2026-08-20 07:1x（JST）に **「いちばん早く予約できる日 ＝ 08/20」** と出しました。
    08/20 はその時点で**今日**で、しかも 25本 予約済みです。
    """
    assert eta.today_jst() == datetime.now(eta.JST).date()
    # UTC で 2026-08-19T22:30 ＝ JST では 2026-08-20T07:30
    utc = datetime(2026, 8, 19, 22, 30, tzinfo=timezone.utc)
    assert utc.astimezone(eta.JST).date() == _date(2026, 8, 20)


# ---- 腕の「引き方」（2026-08-20 14:2x に足した）--------------------------
# **腕の名前だけでは足りません。** `density` には「出す」と「作る」の2つの道が
# あり、どちらが通るかは `upload_cap` にしかありませんでした。
#
# **2026-08-21 04:0x に、分岐そのものを直しました。** ここは本数枠だけを見て
# いましたが、**本数枠は「今この窓で何本 API に通せるか」しか言っていません。**
# `density` の腕が読む入力は `supply.make_rate`（テーマが1日に何本増えるか）で、
# **在庫から出しても、そちらは動きません**（実測: 10本 予約して **+0日**・
# `make_rate` は 22.85 → 21.2 と**下がった**）。
# 在庫が密度を支えていない（`holds=False`）なら、答えは**本数枠と関係なく「作る」**。
# その側の検査は `tests/test_eta_how_to_pull.py` にあります。
#
# **ここの検査は `supply` も止めます。** 止めないと、この分岐の検査が
# **その日の在庫の実物**で通ったり落ちたりします（この直しで実際に落ちました）。

def _fake_state(monkeypatch, *, closed: bool, remaining: int, holds: bool = True):
    from datetime import datetime, timedelta, timezone

    from src import supply as supply_mod
    from src import upload_cap

    tail = datetime(2026, 8, 20, 7, 0, tzinfo=timezone.utc)   # 08/20 16:00 JST
    st = upload_cap.State(closed, 0, remaining, tail, "")
    monkeypatch.setattr(upload_cap, "state", lambda *a, **k: st)
    monkeypatch.setattr(supply_mod, "sweep_novel", lambda *a, **k: {"novel": 502})
    monkeypatch.setattr(supply_mod, "supply", lambda *a, **k: {
        "measured": True, "holds": holds,
        "days_covered": 40.0 if holds else 3.6,
        "sections_per_run_needed": 1.0})


def test_本数枠が閉なら引き方は作るになる(monkeypatch):
    _fake_state(monkeypatch, closed=True, remaining=0)
    got = eta._how_to_pull({"lever_hint": "density", "density": 25,
                            "days_to_target": 157.0})
    assert got is not None
    assert "作る" in got and "16:00 JST" in got
    assert "出す" not in got


def test_本数枠が開いていて在庫も足りていれば引き方は出すになる(monkeypatch):
    _fake_state(monkeypatch, closed=False, remaining=12, holds=True)
    got = eta._how_to_pull({"lever_hint": "density", "density": 25,
                            "days_to_target": 157.0})
    assert got is not None
    assert "出す" in got and "あと 12本" in got


def test_本数枠が開いていても在庫が支えないなら作るになる(monkeypatch):
    """**この回（08/21 03:1x）が実際に踏んだ形です。** 本数枠は開・在庫は 0.9日ぶん。"""
    _fake_state(monkeypatch, closed=False, remaining=12, holds=False)
    got = eta._how_to_pull({"lever_hint": "density", "density": 25,
                            "days_to_target": 157.0})
    assert got is not None
    assert "「作る」" in got and "「出す」" not in got


def test_density以外の腕では何も足さない(monkeypatch):
    _fake_state(monkeypatch, closed=True, remaining=0)
    for lever in ("per_video", "rpm", "sub_rate", "none"):
        assert eta._how_to_pull({"lever_hint": lever, "density": 25,
                                 "days_to_target": 157.0}) is None


def test_読めなくても予測を止めない(monkeypatch):
    from src import upload_cap

    def boom(*a, **k):
        raise RuntimeError("控えが読めない")

    monkeypatch.setattr(upload_cap, "state", boom)
    assert eta._how_to_pull({"lever_hint": "density", "density": 25,
                             "days_to_target": 157.0}) is None


def test_控えに同じ本が2行あるとき_後の行を採る():
    """**帳面は1行1件ではなく、1本1件**（この family の5件目・2026-08-25）。

    `uploaded.jsonl` は足すだけの帳面で、予約を動かすと**同じ `video_id` の行が
    もう1行足されます**（実測 505行 / 実物 491本）。最初の行は
    「投稿したときの予約」＝**すでに動かされた過去の予定**なので、採るのは後の行。

    `published_at()` は `setdefault` で最初の行を採っており、実測でその14本が
    **全部 `views.jsonl` に無い**＝この控えが唯一の出どころでした。JST の日で
    数えた本数が 09/20 7→9・09/21 8→10・09/23 8→7・09/24 8→5 とずれ、
    **09/21 は上限（10本/日）ちょうど**なのに空きが2つ見えていました。

    群の分母が条件と食い違う形は 8/19・8/23・8/25（2件）に続いて**これが5件目**で、
    `src/ab_split.published()` と `src/motion_groups.scheduled_at()` は同じ規則です。
    **3つが同じ帳面を別々に読んでいるので、直すときは3つとも見ること。**
    """
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "views.jsonl").write_text("", encoding="utf-8")
        (d / "uploaded.jsonl").write_text(
            # 後の行のほうが**早い**（詰め直すと前へ動く。実測の14本はすべてこの向き）
            json.dumps({"video_id": "v", "at": "2026-09-22T04:30:00Z"}) + "\n"
            + json.dumps({"video_id": "v", "at": "2026-09-20T02:30:00Z"}) + "\n",
            encoding="utf-8")
        pub = eta.published_at(views_path=d / "views.jsonl",
                               uploaded_path=d / "uploaded.jsonl")
    assert pub["v"] == datetime(2026, 9, 20, 2, 30, tzinfo=timezone.utc), \
        "**後の行**が、いま効いている予約。最初の行は動かされた過去の予定"


# --- **「薄い標本」を「測っていない」と言わないこと**（2026-08-25 に足した） ---
#
# `eta.py` は同じ1回の出力の中で、長尺の1本あたり再生について
# 「**測れています: 1本 4.0回（直近28日・n=14・合計 59回）**」と印字しながら、
# `blocking` では「**まだ一度も測り直していない**」「登録者が9人だった頃の標本」と
# **固定文字列**で出していました。**後者が「次の回が何をするか」を決める欄**なので、
# もう予約済みの測定（実測 2026-08-25 時点で長尺10本が予約済み）に
# 1回ぶんの ship を使わせます。

def test_値が出ている回に_測っていないと言わない():
    """**同じ画面が2つのことを言っていた。** 値が出ているなら、薄いのは標本のほう。"""
    m, a = _analysed(long_per_video=4.0, long_videos_28d=14, long_views_28d=59)
    pl = eta.plan(m, a, today=_date(2026, 8, 25))
    b = pl["blocking"]
    assert pl["target"]["proxy"] is True, "前提: 標本が薄い側に置いている"
    assert b["measured"] is True
    assert "まだ一度も測り直していない" not in b["why"]
    assert "登録者が9人だった頃" not in b["now"]
    # **値そのものは名指しで出すこと**（出ているのに隠すと、また測りに行きます）
    assert "4.0" in b["now"]
    assert str(eta.LONG_SAMPLE_MIN) in b["how"]


def test_長尺が1本も測れていない回は_測れていないと言う():
    """**逆側を潰しておく。** 値が無い回に「薄いだけ」と言うと、今度は測りに行きません。"""
    m, a = _analysed()                      # long_per_video が無い
    assert a["long_per_video"] is None
    pl = eta.plan(m, a, today=_date(2026, 8, 25))
    b = pl["blocking"]
    assert b["measured"] is False
    assert b["sample"] is None
    assert "測れていません" in b["now"]


def test_予約済みの長尺で標本が埋まるなら_その日を出す(tmp_path):
    """**この測定に ship が要るかどうかは、帳面を見れば分かります。**"""
    up = tmp_path / "uploaded.jsonl"
    rows = []
    # 長尺6本を、JST で 08/26 から1日ずつ
    for i in range(6):
        rows.append({"video_id": f"L{i}", "topic": f"nagajaku-{i}",
                     "at": f"2026-08-{26 + i:02d}T10:00:00Z"})
    # ショートは数えない（`s-` で始まるID）
    rows.append({"video_id": "S0", "topic": "s-fukugyo-1",
                 "at": "2026-08-26T00:00:00Z"})
    up.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

    fc = eta.long_sample_forecast(_date(2026, 8, 25), 14, uploaded_path=up)
    assert fc["need"] == eta.LONG_SAMPLE_MIN - 14 == 6
    assert [r["video_id"] for r in fc["booked"]] == [f"L{i}" for i in range(6)]
    assert fc["short_by"] == 0
    # 6本目は JST 08/31 公開 → 伸びきる2日 + Analytics 3日遅れ
    assert fc["reaches"] == eta.answer_day(_date(2026, 8, 31))


def test_予約が足りなければ_足りない本数を返す(tmp_path):
    up = tmp_path / "uploaded.jsonl"
    up.write_text(json.dumps({"video_id": "L0", "topic": "nagajaku",
                              "at": "2026-08-26T10:00:00Z"}), encoding="utf-8")
    fc = eta.long_sample_forecast(_date(2026, 8, 25), 14, uploaded_path=up)
    assert fc["reaches"] is None
    assert fc["short_by"] == 5


def test_もう読める本は_予約として二重に数えない(tmp_path):
    """公開して答えの返った本は、もう n の中にいます。**両方で数えないこと。**"""
    up = tmp_path / "uploaded.jsonl"
    up.write_text(json.dumps({"video_id": "L0", "topic": "nagajaku",
                              "at": "2026-08-01T10:00:00Z"}), encoding="utf-8")
    fc = eta.long_sample_forecast(_date(2026, 8, 25), 14, uploaded_path=up)
    assert fc["booked"] == []
    assert fc["short_by"] == 6


def test_控えの後の行を採る_予約を動かした本(tmp_path):
    """`uploaded.jsonl` は足すだけの帳面。**4つ目の読み手を書かないこと**の担保。"""
    up = tmp_path / "uploaded.jsonl"
    up.write_text("\n".join([
        json.dumps({"video_id": "L0", "topic": "nagajaku",
                    "at": "2026-09-23T03:00:00Z"}),
        json.dumps({"video_id": "L0", "topic": "nagajaku",
                    "at": "2026-08-26T10:00:00Z"}),   # ← 前へ寄せた
    ]), encoding="utf-8")
    fc = eta.long_sample_forecast(_date(2026, 8, 25), 19, uploaded_path=up)
    assert len(fc["booked"]) == 1
    assert fc["booked"][0]["publish"] == _date(2026, 8, 26)
