"""**「verdict で動かせます」と言うなら、どの前提かを同じ行で名指しすること。**

## なぜ検査で留めるか（2026-08-31・最適化の回の実測）

`scripts/eta.py` の頭3行は長らくこう出していました ——

    **期日の来た前提があります**（2026-08-31・開いている前提 28件）→
    **この回は `verdict` で日付が動かせます**

**どの前提かが書いていないので、読んだ回はそのまま撃てません。**
撃つには `python scripts/deadline_check.py`（実測 40秒）を回して 60行 読む
必要があり、「読むのは3行だけ」の手順では読まれません。

その名前は **`src/arm_speed.next_close()` が手に持っていました** ——
`min(days)` を取るとき `h["claim"]` をその場で捨てていただけです。

同じ回の実測（`data/runs.jsonl`・直近7日）:

    ship 359件   `fix` **219件（61%）** ／ `verdict` **11件（3%）**
    到達日        2027-01-02 → 2027-01-15（**+13日 遠のいた**）
    宣言 -55日 に対し実際 +17日

`fix` は**この機械自身のモデルでは軌跡の係数 0** です（腕が動くのは前提を
1件 閉じたときだけ ——`eta.py` 自身がそう印字しています）。
そして `eta.py` は **名前の付いた欠陥を 18件** 印字します。
**名前が付いている側へ 61% が流れるのは、怠けではなく置かれ方の帰結です。**

**覆る条件**: 判定できる前提が毎回 4件 以上 出るようになったら、
名前を全部 並べると頭3行が読めません（上位2件 ＋ 件数へ変えること）。
そのときもこの検査は「**1件は名指しする**」を留めます。
"""
import datetime as _dt
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import arm_speed                                      # noqa: E402


def _load_eta():
    spec = importlib.util.spec_from_file_location("eta_mod", ROOT / "scripts" / "eta.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _doc():
    return {"hypotheses": [
        {"claim": "図を説明のあいだ残すと engaged が上がる", "deadline": "2026-08-31"},
        {"claim": "同じ日に判定できるもう1件", "deadline": "2026-08-31"},
        {"claim": "もっと先の前提", "deadline": "2026-09-30"},
        {"claim": "閉じている前提", "deadline": "2026-08-20",
         "closed_on": "2026-08-20"},
    ]}


def _plan(lever="density"):
    """`tests/test_eta_arm_source_line.py` と同じ材料。"""
    return {
        "target_date": None,
        "days_to_target": 103.0,
        "lever": lever,
        "lever_days": [],
        "levers": {},
    }


def _traj():
    return None


def test_next_closeは判定できる前提の名前を返すこと():
    got = arm_speed.next_close(_doc(), today=_dt.date(2026, 8, 31))
    assert got["on"] == _dt.date(2026, 8, 31)
    assert set(got["claims"]) == {"図を説明のあいだ残すと engaged が上がる",
                                  "同じ日に判定できるもう1件"}, (
        "**同じ日に判定できるものを全部 返していません。** 1件だけ返すと、"
        "撃った次の回に『もう1件あった』が見えません: " + repr(got))


def test_閉じた前提と先の前提は名前に混ざらないこと():
    got = arm_speed.next_close(_doc(), today=_dt.date(2026, 8, 31))
    assert "もっと先の前提" not in got["claims"]
    assert "閉じている前提" not in got["claims"], (
        "閉じた前提を名指しすると、その回は**もう終わった仕事**へ行きます"
        "（`eta.py` が『閉じた仕事を毎回 名指ししていた』のと同じ形）")


def test_判定できない前提は名前に混ざらないこと():
    """`unready` で外した前提は、`deadline` へ落として名指ししないこと。"""
    got = arm_speed.next_close(_doc(), today=_dt.date(2026, 8, 31),
                               unready={"図を説明のあいだ残すと engaged が上がる"})
    assert "図を説明のあいだ残すと engaged が上がる" not in got["claims"], (
        "**判定できない前提を名指ししています。** これを出すと、その回は"
        "データの無い前提を閉じにいきます（2026-08-26 20:4x に踏んだ形）")
    assert got["open"] == 3, "開いた件数からは落とさないこと: " + repr(got)


def test_判定できる日が無い回は空で返ること():
    got = arm_speed.next_close({"hypotheses": []}, today=_dt.date(2026, 8, 31))
    assert got["on"] is None and got["claims"] == []


def test_etaの頭3行がその名前を印字すること(monkeypatch):
    eta = _load_eta()
    monkeypatch.setattr(
        eta.arm_speed, "next_close",
        lambda *a, **k: {"on": _dt.date(2026, 8, 31), "days": 0, "open": 28,
                         "source": "ready",
                         "claims": ["図を説明のあいだ残すと engaged が上がる"]})
    line = next(ln for ln in eta.headline(_plan(), None, _traj())
                if "期日の来た前提があります" in ln)
    assert "図を説明のあいだ残すと engaged が上がる" in line, (
        "**名前が出ていません。** 日付と件数だけでは、読んだ回は"
        "`deadline_check.py` を回すまで何が判定できるのか分かりません: " + line)


def test_名前が無い返りでも頭3行が落ちないこと(monkeypatch):
    """古い形（`claims` を持たない返り）でも印字は続くこと。"""
    eta = _load_eta()
    monkeypatch.setattr(eta.arm_speed, "next_close",
                        lambda *a, **k: {"on": _dt.date(2026, 8, 31),
                                         "days": 0, "open": 28})
    line = next(ln for ln in eta.headline(_plan(), None, _traj())
                if "期日の来た前提があります" in ln)
    assert "deadline_check" in line, (
        "名前が無いときは、**どこで引けるか**を出すこと: " + line)
