"""余裕（`ceiling_rate()` ÷ 要る速さ）の列は、**手で送らず台帳から読む**。

2026-09-11 07:5x・optimizer・Opus。

**なぜ足したか**: §7「いまの数」が「3.07 → 3.07 → 3.07 → 3.08 → 3.08 → 3.09」を
**周ごとに手で送って**いました。**`pace(過去の刻)` で数え直しても、その列は出ません** ——
`per_lap` も遅れも**いまの台帳**から引き直されるので、過去の点まで「いまの基準」で塗り替わります
（実測 09/10 17:45〜21:58 の 8周 を数え直すと **3.094〜3.098**・手の列は 3.07〜3.09）。
＝ **その周が見た数は、その周に書くしかありません**（`quota.record_model_choice`）。

**陽性対照**（壊したら落ちるまで撃つ・METHOD §5 の教訓の形3つ目）:
畳みを外すと同じ周が 2回 出る／門の定数を別々に持たせると片方だけ動く／
`reach_ceiling_margin` を書かない行だけの台帳で「まだ 1点も無い」と言えること。
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import quota  # noqa: E402


def _write(tmp_path, rows):
    f = tmp_path / "model_choice.jsonl"
    f.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return f


def _row(at, margin=None, role="hourly"):
    r = {"at": at, "work_kind": f"{role}:leverage", "model": "fable"}
    if margin is not None:
        r["reach_ceiling_margin"] = margin
    return r


@pytest.fixture(autouse=True)
def _no_rounds(tmp_path, monkeypatch):
    """**既定では周の台帳を空にする**（2026-09-11 11:2x）。

    `margin_series` は周を `data/rounds.jsonl` の刻へ寄せて数えます。
    ここを塞がないと、検査の作り話の刻が**実物の周**へ寄ってしまい、
    検査が「きょうの台帳」に依ります（この回に 3件 踏んだ・METHOD §5 教訓の形 6つ目）。
    周の刻を要る検査は、下の `_rounds()` で自分の分を置きます。
    """
    monkeypatch.setattr(quota, "ROUNDS_LOG", tmp_path / "no-rounds.jsonl")


def _rounds(tmp_path, monkeypatch, ats):
    """周の台帳（`rounds.jsonl`）を置く —— 親は 1周に 2行（役ごと）積む。"""
    f = tmp_path / "rounds.jsonl"
    f.write_text("".join(
        json.dumps({"at": a, "role": r, "round": a}, ensure_ascii=False) + "\n"
        for a in ats for r in ("hourly", "optimizer")), encoding="utf-8")
    monkeypatch.setattr(quota, "ROUNDS_LOG", f)
    return f


def test_周は_rounds_jsonl_の刻へ寄せて数えること(tmp_path, monkeypatch):
    """**周の印は `rounds.jsonl` が持っています**（2026-09-11 11:2x・optimizer・Opus）。

    親は**周を記録する 10秒 前に模型を選ぶ**ので（実測 10:00:39 の行 対 10:00:49 の周）、
    「その行より前のいちばん新しい周」では **1つ 前の周**に付きます。
    だから**いちばん近い周**（前でも後でもよい）へ寄せます。
    """
    _rounds(tmp_path, monkeypatch, ["2026-09-11T09:25:23+09:00", "2026-09-11T10:00:49+09:00"])
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", _write(tmp_path, [
        _row("2026-09-11T09:25:13+09:00", 3.011, "hourly"),
        _row("2026-09-11T09:25:14+09:00", 3.011, "optimizer"),
        _row("2026-09-11T10:00:39+09:00", 3.011, "hourly"),
        _row("2026-09-11T10:00:40+09:00", 3.011, "optimizer"),
    ]))
    assert len(quota.margin_series()) == 2, "2周 ＝ 2点（周の刻より 10秒 手前の行も、その周へ寄る）"


def test_同じ周に同じ役が立て直されても_1点(tmp_path, monkeypatch):
    """**実物で踏んだ形**（2026-09-11 10:17 JST）。

    親は `hourly` を **fable が 429（月の上限）を返したので opus で立て直し**、
    **同じ周の 17分 後に 3行目**（役は hourly）を積みました。
    ＝ **同じ周かどうかは、刻の近さでも役でも決まりません** ——
    11:0x に「役がちがう ＋ 5秒 以内」へ直した 30分 後に、その手は外れています。

    **陽性対照**: 周の刻を 2つ にして 10:17 を別の周にすると、この検査は 2点 を見て赤くなる。
    """
    _rounds(tmp_path, monkeypatch, ["2026-09-11T10:00:49+09:00"])
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", _write(tmp_path, [
        _row("2026-09-11T10:00:39+09:00", 3.011, "hourly"),
        _row("2026-09-11T10:00:40+09:00", 3.011, "optimizer"),
        _row("2026-09-11T10:17:17+09:00", 3.057, "hourly"),   # 429 で立て直した回
    ]))
    assert quota.margin_series() == [("2026-09-11T10:00:39+09:00", 3.011)], \
        "同じ周の 3行 ＝ 1点（その周が最初に見た数）"


def test_同じ周の_2行_は_1つ_に畳むこと(tmp_path, monkeypatch):
    """親は 1周に 2行（`hourly` と `optimizer`）積みます。畳まないと周の数が倍に出ます。"""
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", _write(tmp_path, [
        _row("2026-09-11T06:58:40+09:00", 3.09, "hourly"),
        _row("2026-09-11T06:58:40+09:00", 3.09, "optimizer"),
        _row("2026-09-11T07:34:00+09:00", 3.05, "hourly"),
        _row("2026-09-11T07:34:00+09:00", 3.05, "optimizer"),
    ]))
    assert quota.margin_series() == [("2026-09-11T06:58:40+09:00", 3.09),
                                     ("2026-09-11T07:34:00+09:00", 3.05)]


def test_同じ周の_2行_は_1秒_ずれていても畳むこと(tmp_path, monkeypatch):
    """**実物の形**（2026-09-11 10:5x・optimizer・Opus）。

    上の検査は**同じ刻の 2行**で書いてあり、畳みも `at` の文字列一致でやっていました。
    ところが**実物の親は 2行 を 1秒 ずらして書きます** ——
    `10:00:39 hourly` / `10:00:40 optimizer`（`data/model_choice.jsonl` の実測:
    いまの形の 5周 とも **1秒**）。**検査は緑のまま、実物の形だけが抜けていた**
    （METHOD §5「教訓の形 4つ目」）。

    この回の列は `3.022 → 3.015 → 3.014 → 3.011 → 3.011 → 3.011`（**6周**）と出ていました。
    本当は **5周**で、最後の `+0.000` は**同じ周を 2度 数えた偽の 1周**です ——
    `margin_step` の「1周ぶんの動き」「振れ幅」「門まで あと N周」は、全部この列が分母です。

    **陽性対照**: 畳みを `at` の一致へ戻すと、この検査が赤くなる（撃って落とした）。
    """
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", _write(tmp_path, [
        _row("2026-09-11T10:00:39+09:00", 3.011, "hourly"),
        _row("2026-09-11T10:00:40+09:00", 3.011, "optimizer"),
    ]))
    assert quota.margin_series() == [("2026-09-11T10:00:39+09:00", 3.011)], \
        "1周 に 2行（役ちがい・1秒 差）＝ 1点"


def test_同じ役が続いたら_近くても別の周_穴埋め(tmp_path, monkeypatch):
    """**時刻だけで畳まないこと**（`rounds.jsonl` が読めない回の**控え**の側）。

    親は**前の周の同じ役がまだ走っていると、穴埋めで片方だけを立てます**（METHOD §5）——
    そのとき前の周と **1分 しか離れません**。時刻の窓だけで畳むと、その周が消えます。
    **周は役ごとに 1行** なので、役が同じならいくら近くても別の周です。

    台帳の実測でも、**同じ役が続く（＝ 別の周）いちばん短い差は 14秒**で、
    同じ周の 2行（0〜1秒）とは重なりません。
    """
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", _write(tmp_path, [
        _row("2026-09-11T10:00:39+09:00", 3.011, "hourly"),
        _row("2026-09-11T10:00:41+09:00", 3.008, "hourly"),
    ]))
    assert quota.margin_series() == [("2026-09-11T10:00:39+09:00", 3.011),
                                     ("2026-09-11T10:00:41+09:00", 3.008)], \
        "同じ役 ＝ 別の周（`MARGIN_SAME_SEC` の内側でも畳まない）"


def test_穴埋めの周は_役がちがっても_1分_で別の周(tmp_path, monkeypatch):
    """**窓の上を押さえるのは、穴埋めの周**（2026-09-11 10:5x・**控え**の側）。

    前の周の同じ役がまだ走っていると、親は**穴埋めで片方だけを立て、間隔を待ちません**
    （METHOD §5・`data/parent_wakes.jsonl` の `patch: true`）——
    そのとき**役はちがい、前の周との差は 1分**です。
    ＝ **窓を 1分 以上 に広げると、その周が黙って消えます。**

    **陽性対照**（撃って落とした）: `MARGIN_SAME_SEC` を 120秒 に広げると、この検査が赤くなる。
    **最初に書いた窓の検査は 36分 差で、広げても落ちませんでした**
    —— §5「教訓の形 3つ目」（陽性対照は、壊したら落ちるまで撃つ）。
    """
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", _write(tmp_path, [
        _row("2026-09-11T10:00:39+09:00", 3.011, "hourly"),
        _row("2026-09-11T10:01:39+09:00", 3.008, "optimizer"),
    ]))
    assert len(quota.margin_series()) == 2, \
        f"穴埋めの周（1分・役ちがい）は別の周。`MARGIN_SAME_SEC`={quota.MARGIN_SAME_SEC}"


def test_古い順に返し_窓の外は落とすこと(tmp_path, monkeypatch):
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", _write(tmp_path, [
        _row(f"2026-09-11T0{i}:00:00+09:00", 3.0 + i / 100) for i in range(1, 8)
    ]))
    xs = quota.margin_series(3)
    assert [v for _, v in xs] == [pytest.approx(3.05), pytest.approx(3.06), pytest.approx(3.07)]


def test_書いていない行しか無ければ_黙って_0_を返さず言うこと(tmp_path, monkeypatch):
    """**この列が在る前の行を「0点」と読ませないこと**（覆る条件 (1)）。"""
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", _write(tmp_path, [
        _row("2026-09-11T06:00:00+09:00"), _row("2026-09-11T06:36:00+09:00")]))
    assert quota.margin_series() == []
    assert "まだ 1点も積まれていません" in quota.margin_line()


def test_門を切った周は名指しすること(tmp_path, monkeypatch):
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", _write(tmp_path, [
        _row("2026-09-11T07:00:00+09:00", 3.05),
        _row("2026-09-11T07:36:00+09:00", 2.98)]))
    line = quota.margin_line()
    assert "**切った周: 09-11T07:36 2.980**" in line and "掃き直すこと" in line
    assert "門の上" not in line


def test_門の上なら切った周を名指ししないこと(tmp_path, monkeypatch):
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", _write(tmp_path, [
        _row("2026-09-11T07:00:00+09:00", 3.05),
        _row("2026-09-11T07:36:00+09:00", 3.01)]))
    line = quota.margin_line()
    assert "＝ **門の上**" in line and "切った周" not in line


def test_門の出どころは_1か所(tmp_path, monkeypatch):
    """**片方だけ動かせる形にしないこと** —— `pace_report` と `margin_line` が
    3.0 を別々に持っていました（2026-09-11 07:5x に定数へ寄せた）。"""
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", _write(tmp_path, [
        _row("2026-09-11T07:00:00+09:00", 3.05)]))
    monkeypatch.setattr(quota, "CEILING_MARGIN_GATE", 4.0)
    assert "**切った周: 09-11T07:00 3.050**" in quota.margin_line()
    src = (Path(__file__).resolve().parents[1] / "scripts" / "quota.py").read_text(encoding="utf-8")
    assert src.count('"（門 3.0倍）"') == 0        # 生の 3.0 を印字に残さないこと


def test_親が周ごとに余裕を積むこと(tmp_path, monkeypatch):
    """**この列は親が書きます** —— `record_model_choice` が実際に欄を足すこと
    （`pace()` が落ちても行は書く ＝ そのときは `None`・覆る条件 (1)）。"""
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", tmp_path / "model_choice.jsonl")
    monkeypatch.setattr(quota, "pace", lambda now=None: {"used_now": 78.1, "reach_ceiling_margin": 3.0462})
    row = quota.record_model_choice("optimizer", "opus", "検査")
    assert row["reach_ceiling_margin"] == 3.046          # 3桁 に丸めて積む
    assert [v for _, v in quota.margin_series()] == [3.046]

    def boom(now=None):
        raise RuntimeError("目盛りが無い")

    monkeypatch.setattr(quota, "pace", boom)
    row = quota.record_model_choice("hourly", "fable", "検査")
    assert row["reach_ceiling_margin"] is None
    assert [v for _, v in quota.margin_series()] == [3.046]   # 空の周は列に入れない


def test_壊れた行は落として続けること(tmp_path, monkeypatch):
    f = tmp_path / "model_choice.jsonl"
    f.write_text('{"at": "2026-09-11T07:00:00+09:00", "reach_ceiling_margin": 3.05}\n'
                 "{ここは JSON ではない\n"
                 '{"at": "2026-09-11T07:36:00+09:00", "reach_ceiling_margin": 3.02}\n',
                 encoding="utf-8")
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", f)
    assert [v for _, v in quota.margin_series()] == [3.05, 3.02]


# ---------------------------------------------------------------------------
# **1周ぶんの動きを、印字が落とさないこと**（2026-09-11 08:4x・optimizer・Opus）
#
# 台帳は **3桁** で積んでいます（`record_model_choice` の `round(..., 3)`）。
# 印字だけが 2桁 で、**実測の 1周 -0.007 がそこで消えていました**
# （3.022 → 3.015 が「3.02 → 3.02」＝ 読む側には平らに見える）。
# ＝ **道具が持っている桁を、印字が捨てていた**形です。
# ---------------------------------------------------------------------------


def _series(tmp_path, monkeypatch, vals, start_h=7, step_min=36):
    rows = []
    for i, v in enumerate(vals):
        m = start_h * 60 + i * step_min
        at = f"2026-09-11T{m // 60:02d}:{m % 60:02d}:00+09:00"
        rows += [_row(at, v, "hourly"), _row(at, v, "optimizer")]
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", _write(tmp_path, rows))


def test_1周ぶんの動きが印字に出ること(tmp_path, monkeypatch):
    """**陽性対照つき**: 桁を 2 に戻すと、同じ列が「3.02 → 3.02」になって動きが消える。"""
    _series(tmp_path, monkeypatch, [3.022, 3.015])
    line = quota.margin_line()
    assert "3.022 → 3.015" in line
    assert "-0.007" in line

    monkeypatch.setattr(quota, "MARGIN_DIGITS", 2)          # ← 陽性対照（前の形）
    assert "3.02 → 3.02" in quota.margin_line()


def test_門までの残り周を数えること(tmp_path, monkeypatch):
    """3.015 から 1周 -0.007 なら、門 3.0 を切るのは **3周 後**（3.008・3.001・2.994）。"""
    _series(tmp_path, monkeypatch, [3.022, 3.015])
    st = quota.margin_step()
    assert st["step"] == pytest.approx(-0.007)
    assert st["laps_to_gate"] == 3
    assert st["gap_min"] == pytest.approx(36.0)
    assert st["eta_min"] == pytest.approx(108.0)
    assert "あと 3周" in quota.margin_line()


def test_上がっている列に門の周を言わないこと(tmp_path, monkeypatch):
    """**下がっていない列で「あと N周」と言わないこと** —— 外挿の向きが逆になる。"""
    _series(tmp_path, monkeypatch, [3.015, 3.022])
    st = quota.margin_step()
    assert st["step"] == pytest.approx(0.007)
    assert st["laps_to_gate"] is None
    line = quota.margin_line()
    assert "あと" not in line
    assert "下がっていません" in line


def test_点が1つなら速さを言わないこと(tmp_path, monkeypatch):
    """**1点から傾きを作らないこと**（列が始まった周に踏む形）。"""
    _series(tmp_path, monkeypatch, [3.022])
    assert quota.margin_step() is None
    assert "1周 **" not in quota.margin_line()      # 「（1周・門…）」の 1周 とは別


def test_門を切っていれば残り周ではなく切った周を言うこと(tmp_path, monkeypatch):
    """切ったあとは外挿ではなく **掃き直す** 側（`ceiling_rate()` の覆る条件 (1)）。"""
    _series(tmp_path, monkeypatch, [3.004, 2.997])
    line = quota.margin_line()
    assert "切った周" in line and "2.997" in line
    assert quota.margin_step()["laps_to_gate"] is None


# ---------------------------------------------------------------------------
# **速さも、1周ぶんの点では読めない**（2026-09-11 09:1x・optimizer・Opus）
#
# 08:4x は台帳の直近2点から 1周 -0.007 を読み、「門まで あと 3周（10:0x ごろ）」を
# §7「いまの数」に書きました。**次の周の点は 3.014 ＝ 1周 -0.001** で、同じ口が
# 「あと 14周」と言います。**列は 1つも書き換わっていません** —— 直近2点の差が
# 周ごとに **7倍** 振れるだけです。`gate_span` が 帯の比 に当てたのと同じ形。
# ---------------------------------------------------------------------------


def test_振れ幅を出し_門までを帯で言うこと(tmp_path, monkeypatch):
    """**陽性対照つき**: 帯の片端（速い側 3周／遅い側 14周）だけになったら落ちる。"""
    _series(tmp_path, monkeypatch, [3.022, 3.015, 3.014])
    st = quota.margin_step()
    assert st["steps"] == [pytest.approx(-0.007), pytest.approx(-0.001)]
    assert st["step_lo"] == pytest.approx(-0.007) and st["step_hi"] == pytest.approx(-0.001)
    assert (st["laps_few"], st["laps_many"]) == (3, 14)
    line = quota.margin_line()
    assert "**振れ幅 -0.007〜-0.001**" in line
    assert "あと 3〜14周" in line                      # ← 片端だけを点で書かないこと
    assert "あと 14周**" not in line and "あと 3周**" not in line


def test_動きが1つしか無い周は振れ幅を言わないこと(tmp_path, monkeypatch):
    """**2点 から振れ幅を作らないこと**（08:4x が踏んだ形そのもの）。"""
    _series(tmp_path, monkeypatch, [3.022, 3.015])
    st = quota.margin_step()
    assert st["step_lo"] is None and st["laps_few"] is None
    line = quota.margin_line()
    assert "振れ幅はまだ読めません" in line
    assert "あと 3周" in line                          # 1つしか無いので点のまま


def test_上がった周が在れば上端を作らないこと(tmp_path, monkeypatch):
    """上がった周から外挿した上端は「永遠に切らない」になる ＝ 出さないこと。"""
    _series(tmp_path, monkeypatch, [3.010, 3.020, 3.013])
    st = quota.margin_step()
    assert st["open_top"] is True and st["laps_many"] is None and st["laps_few"] == 2
    line = quota.margin_line()
    assert "早くて あと 2周" in line and "上端は無し" in line


def test_刻が空いた対は落として言うこと(tmp_path, monkeypatch):
    """周が抜けた対は **何周ぶんか分けられません** —— 混ぜると振れ幅の上端が伸びる。

    **陽性対照**: 落とさずに混ぜると、この列の上端は 14周 ではなく **68周** に伸びます
    （2.4時間 空いた対の -0.0002 を 1周ぶんとして読むため。撃って確かめた）。
    """
    rows = []
    for at, v in [("07:00", 3.022), ("07:36", 3.015), ("10:00", 3.0148), ("10:36", 3.0135)]:
        rows += [_row(f"2026-09-11T{at}:00+09:00", v, "hourly"),
                 _row(f"2026-09-11T{at}:00+09:00", v, "optimizer")]
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", _write(tmp_path, rows))
    st = quota.margin_step()
    assert st["skipped"] == 1
    assert st["steps"] == [pytest.approx(-0.007), pytest.approx(-0.0013)]
    assert st["laps_many"] == 11                      # 混ぜていれば 68周 になる
    assert "刻が空いた対 1つ は落とした" in quota.margin_line()


def test_門を切ったあとは帯も言わないこと(tmp_path, monkeypatch):
    """切ったあとは外挿ではなく掃き直す側（`ceiling_rate()` の覆る条件 (1)）。"""
    _series(tmp_path, monkeypatch, [3.010, 3.004, 2.997])
    st = quota.margin_step()
    assert st["laps_few"] is None and st["laps_many"] is None
    line = quota.margin_line()
    assert "切った周" in line and "あと" not in line
