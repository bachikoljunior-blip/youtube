"""**腕の名前を出したら、その腕が何で動くのかも同じ3行に出す**（`headline`）。

## なぜ検査で留めるか（2026-08-21 05:xx の実測）

`docs/trigger_main.md` は「読むのは3行だけ」と言い、その3行が
**この回に引く腕**を名指しします。この回は名指しどおり `density` を選び、
その入力（`supply.make_rate`）を**実際に2倍にしました**。

    make_rate_per_day: 22.85 → 46.7   （テーマの表を2本書き、在庫 12 → 28本）
    到達日（軌跡）: 2026-12-02 → 2026-12-02（**+0日**）

前の回（`tests/test_eta_how_to_pull.py`）は「在庫から**出す**だけでは
`make_rate` が動かない」を留めました。**この回は、その `make_rate` を
動かしても到達日が動かないことを測っています。**

理由は `src/arm_speed.py` にあります —— 軌跡の腕は
`config/hypotheses.yaml` の**閉じた前提**（回転の速さ・当たる確率・伸び幅）
だけで動きます。**テーマを作る／在庫から出す／道具を直すは、そのどれにも
入りません。** 段の側（`--reflect` が測る入力）は動きますが、
**印字される到達日は動きません。**

**その区別が3行の中に無いと、次の回も同じ所へ来ます**（実測で2回続けて来ました）。
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location("eta_mod", ROOT / "scripts" / "eta.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _plan(lever="density"):
    return {
        "target_date": None,
        "days_to_target": 103.0,
        "binding": "再生数が天井に当たっている",
        "lever_hint": lever,
        "lever_from": "軌跡",
        "lever_hint_binding": "rpm",
        "lever_days": [],
    }


def _traj(lever="density", throughput=0.9, p=0.33):
    return {
        "choice": [{"lever": lever, "reachable": True, "days": 102.0,
                    "date": __import__("datetime").date(2026, 12, 1),
                    "t_work": 15}],
        "arms": {lever: {"lever": lever, "throughput": throughput, "p": p,
                         "n": 3, "hits": 1, "source": "自前"}},
    }


def test_腕を名指ししたら何で動くかも同じ3行に出る():
    eta = _load()
    lines = eta.headline(_plan(), None, _traj())
    hit = [ln for ln in lines if _SPEED_MARK in ln]
    assert hit, (
        "3行の中に「軌跡の腕は前提を1件閉じたときだけ動く」が出ていません。"
        "**腕の名前だけを出すと、作る・出す・直すのどれかで動くと読めます** ——"
        "実測では make_rate を2倍にしても到達日は +0日 でした。"
    )
    line = hit[0]
    assert "density" in line, "名指しした腕そのものの速さを出していません"
    assert "作る" in line and "出す" in line, (
        "**何が入力に入らないか**を書いていません。"
        "入らないものの名前が無いと、次の回は同じ道を選びます。"
    )


def test_回転の速さと当たる確率が実測から出る():
    eta = _load()
    line = next(ln for ln in eta.headline(_plan(), None, _traj(throughput=0.5, p=0.5))
                if _SPEED_MARK in ln)
    # 1 / 0.5 = 2.0日に1件
    assert "2.0日に1件" in line, f"回転の速さが実測から出ていません: {line}"
    assert "50%" in line, f"当たる確率が実測から出ていません: {line}"


def test_閉じた前提が0件なら実測なしと言う():
    eta = _load()
    line = next(ln for ln in eta.headline(_plan(), None, _traj(throughput=None, p=None))
                if _SPEED_MARK in ln)
    assert "実測なし" in line, (
        "閉じた前提が0件のときに、速さを推測で埋めています。"
        "**無いものは無いと言うこと**（`src/arm_speed.py` の註）。"
    )


#: **速さの行を引き当てる目印**（2026-08-31 に狭めた）。
#:
#: ここは長らく `"hypotheses.yaml"` でした。**台帳の道は、他の行にも書かれます** ——
#: 2026-08-31 に `headline()` へ「来ない日を待っている前提」の行を足したとき、
#: その行が同じ字を含んだので、**`test_腕が軌跡に無ければ黙る` が
#: 正しい変更で落ちました**（速さの行は出ていないのに「出ている」と読んだ）。
#:
#: **目印は、その行だけが持つ字にすること。** 速さの行の主語は「軌跡の腕」です。
_SPEED_MARK = "軌跡の腕が動くのは"


def test_腕が軌跡に無ければ黙る():
    eta = _load()
    lines = eta.headline(_plan(lever="rpm"), None, _traj(lever="density"))
    assert not [ln for ln in lines if _SPEED_MARK in ln], (
        "名指しした腕が軌跡の表に無いのに、速さの行を出しています。"
    )


# ---- 「いつなら動くのか」（`arm_speed.next_close`）--------------------------
#
# **期日の来た前提が1件も無い回は、何をしても到達日は動きません。**
# それを先に言わないと、その回は外れる `--moves` を立てるだけで終わります
# （2026-08-21 の回がそうでした ―― 開いていた13件のいちばん早い期日は
# 08/26 で、**日付を動かす道はそもそも1本もありませんでした**）。

import datetime as _dt


def _hyp(*settle):
    return {"hypotheses": [{"id": f"h{i}", "settle_by": s}
                           for i, s in enumerate(settle)]}


def test_次に閉じられる日と件数を返す():
    from src import arm_speed
    got = arm_speed.next_close(_hyp("2026-09-05", "2026-08-26", "2026-09-12"),
                               today=_dt.date(2026, 8, 21))
    assert got["on"] == _dt.date(2026, 8, 26)
    assert got["days"] == 5
    assert got["open"] == 3


def test_閉じた前提は数えない():
    from src import arm_speed
    doc = _hyp("2026-08-26", "2026-09-05")
    doc["hypotheses"][0]["closed_on"] = "2026-08-20"
    got = arm_speed.next_close(doc, today=_dt.date(2026, 8, 21))
    assert got["open"] == 1, "閉じた前提を開いている側で数えています"
    assert got["on"] == _dt.date(2026, 9, 5)


def test_開いている前提が無ければ日付を作らない():
    from src import arm_speed
    got = arm_speed.next_close({"hypotheses": []}, today=_dt.date(2026, 8, 21))
    assert got["on"] is None and got["open"] == 0, "無いものを埋めています"


def test_期日が来ていない回はmoves0が正しいと言う(monkeypatch):
    eta = _load()
    monkeypatch.setattr(eta.arm_speed, "next_close",
                        lambda *a, **k: {"on": _dt.date(2026, 8, 26),
                                         "days": 5, "open": 13})
    line = next(ln for ln in eta.headline(_plan(), None, _traj())
                if "閉じられる前提はありません" in ln)
    assert "2026-08-26" in line and "`--moves 0` が正しい回です" in line, (
        "**動かせない回だと分かる字**が出ていません。"
        "これが無いと、その回は外れる宣言を立てるだけで終わります。"
    )


def test_期日が来ている回はverdictと言う(monkeypatch):
    eta = _load()
    monkeypatch.setattr(eta.arm_speed, "next_close",
                        lambda *a, **k: {"on": _dt.date(2026, 8, 21),
                                         "days": 0, "open": 13})
    line = next(ln for ln in eta.headline(_plan(), None, _traj())
                if "期日の来た前提があります" in ln)
    assert "verdict" in line, "閉じられる回に、その手の名前を出していません"


# ---- **`deadline` ではなく「データが揃う日」で聞くこと**（2026-08-25 22:5x）
#
# `deadline` は置いた回の勘で、**データが実際に揃う日**（`deadline_check` の
# `ready`）とは別物です。実測（2026-08-25・開いている16件）:
#
#     ready <= deadline が **10件・合計 46日**（平均 4.6日・最大 14日）
#
# **軌跡の腕は前提を1件閉じたときだけ動く**ので、その 46日 は
# **到達日がまるごと止まっている日数**です。


def test_データが揃う日のほうが早ければ_そちらを返す():
    """**待たないこと。** 期限が先でも、判定できるならその日が答えです。"""
    from src import arm_speed
    doc = {"hypotheses": [{"id": "h0", "claim": "A", "deadline": "2026-09-12"}]}
    got = arm_speed.next_close(doc, today=_dt.date(2026, 8, 25),
                               ready={"A": _dt.date(2026, 8, 29)})
    assert got["on"] == _dt.date(2026, 8, 29), \
        "`deadline` を読んでいます（**データはもう揃っています**）"
    assert got["days"] == 4
    assert got["source"] == "ready"


def test_データが遅れる側でも_揃う日が答え():
    """`ready > deadline` は「期限が守れない」だけ。**判定できる日は動きません。**"""
    from src import arm_speed
    doc = {"hypotheses": [{"id": "h0", "claim": "A", "deadline": "2026-08-26"}]}
    got = arm_speed.next_close(doc, today=_dt.date(2026, 8, 25),
                               ready={"A": _dt.date(2026, 9, 6)})
    assert got["on"] == _dt.date(2026, 9, 6), "守れない期限を答えにしています"


def test_揃う日が分からない前提は_期限のまま():
    """**埋めないこと。** `ready` の無い前提は従来どおり `deadline` で読みます。"""
    from src import arm_speed
    doc = {"hypotheses": [{"id": "h0", "claim": "A", "deadline": "2026-09-12"},
                          {"id": "h1", "claim": "B", "deadline": "2026-08-30"}]}
    got = arm_speed.next_close(doc, today=_dt.date(2026, 8, 25),
                               ready={"A": _dt.date(2026, 9, 9)})
    assert got["on"] == _dt.date(2026, 8, 30)
    assert got["source"] == "deadline"


def test_渡さなければ_昔と同じに読む():
    """**既定は変えていません。** 呼び手が渡したときだけ切り替わります。"""
    from src import arm_speed
    doc = {"hypotheses": [{"id": "h0", "claim": "A", "deadline": "2026-09-12"}]}
    got = arm_speed.next_close(doc, today=_dt.date(2026, 8, 25))
    assert got["on"] == _dt.date(2026, 9, 12)
