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
    hit = [ln for ln in lines if "hypotheses.yaml" in ln]
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
                if "hypotheses.yaml" in ln)
    # 1 / 0.5 = 2.0日に1件
    assert "2.0日に1件" in line, f"回転の速さが実測から出ていません: {line}"
    assert "50%" in line, f"当たる確率が実測から出ていません: {line}"


def test_閉じた前提が0件なら実測なしと言う():
    eta = _load()
    line = next(ln for ln in eta.headline(_plan(), None, _traj(throughput=None, p=None))
                if "hypotheses.yaml" in ln)
    assert "実測なし" in line, (
        "閉じた前提が0件のときに、速さを推測で埋めています。"
        "**無いものは無いと言うこと**（`src/arm_speed.py` の註）。"
    )


def test_腕が軌跡に無ければ黙る():
    eta = _load()
    lines = eta.headline(_plan(lever="rpm"), None, _traj(lever="density"))
    assert not [ln for ln in lines if "hypotheses.yaml" in ln], (
        "名指しした腕が軌跡の表に無いのに、速さの行を出しています。"
    )
