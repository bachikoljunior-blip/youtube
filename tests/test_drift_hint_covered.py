"""**名指しを「外した回」と、`eta.py` が「外せ」と言った回を分けているか。**

2026-08-26・最適化の回。

`scripts/eta.py` は、名指しした腕の測定がもう予約済みのとき、こう印字します:

> **その `per_video` の測定は、予約済みの本が 2026-08-31 に答えます**
> → **この回は別の腕を引くこと。** `--lever` が `per_video` でなくても、
>   この回は「名指しを外した」ではありません

`scripts/run_marker.py` はそれを **`lever_hint_covered` としてその回の行に
残しています**。ところが `drift.py` は `lever == hint` だけを数えていて、
**その欄を1度も読んでいませんでした。**

**外れる向きが悪いほうです。** 読まないと「名指しに従った回 21%」と出て、
読んだ回は「instrument を8割 無視している」と受け取ります。そして直し方は
**「`per_video` の回を増やす」**になります —— `eta.py` が
「その腕はもう測定中だから別を引け」と言っている、まさにその腕を。

**門にはしません**（`test_dead_arm.py` と同じ考え方）。守るのは
**2つを別々に数えること**だけです。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import drift  # noqa: E402

ETA_ROW = {"lever_hint": "per_video",
           "binding": "再生数が天井に当たっている",
           "arm_caps": {"per_video": 3.08, "sub_rate": 3066.0,
                        "rpm": 70.2, "density": 1.0}}


def _seed(tmp_path, monkeypatch, ships):
    runs = tmp_path / "runs.jsonl"
    runs.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in ships) + "\n",
                    encoding="utf-8")
    monkeypatch.setattr(drift, "RUNS", runs)
    monkeypatch.setattr(drift, "ROOT", tmp_path)
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data" / "eta.jsonl").write_text(
        json.dumps(ETA_ROW, ensure_ascii=False) + "\n", encoding="utf-8")


def _ship(at, lever, covered=None):
    r = {"at": at, "kind": "ship", "lever": lever, "moves": 0}
    if covered:
        r["lever_hint_covered"] = covered
    return r


def test_covered_な回は外した回に数えない(tmp_path, monkeypatch):
    """`eta.py` が「別の腕を引け」と言った回を、不服従として数えないこと。"""
    _seed(tmp_path, monkeypatch, [
        _ship("2026-08-26T01:00:00+09:00", "none", covered="2026-08-31"),
        _ship("2026-08-26T02:00:00+09:00", "density", covered="2026-08-31"),
        _ship("2026-08-26T03:00:00+09:00", "per_video"),
    ])
    out = drift.dead_arm_report("2026-08-26")
    assert "`eta.py` 自身が" in out, "covered の回を別に数えていない"
    assert "2026-08-31" in out, "いつ答えが返るかを出すこと"
    assert "**1/1**" in out, "covered を除いた側の数が出ていない"


def test_covered_が1件も無ければ余計な行を出さない(tmp_path, monkeypatch):
    """欄が無い窓（この欄を足す前の回）では、今までどおりの1行だけ。"""
    _seed(tmp_path, monkeypatch, [
        _ship("2026-08-26T01:00:00+09:00", "density"),
        _ship("2026-08-26T02:00:00+09:00", "per_video"),
    ])
    out = drift.dead_arm_report("2026-08-26")
    assert "名指し" in out
    assert "`eta.py` 自身が" not in out


def test_全部_covered_なら従いようが無いと言う(tmp_path, monkeypatch):
    """**従いようが無い窓を、従わなかった窓と読ませないこと。**"""
    _seed(tmp_path, monkeypatch, [
        _ship("2026-08-26T01:00:00+09:00", "none", covered="2026-08-31"),
        _ship("2026-08-26T02:00:00+09:00", "density", covered="2026-08-31"),
    ])
    out = drift.dead_arm_report("2026-08-26")
    assert "従いようがない窓" in out


def test_run_marker_がその欄を残していること():
    """**この検査の前提**。`run_marker.py` が書かなくなったら、上は全部 空振りです。"""
    src = (Path(__file__).resolve().parent.parent / "scripts" / "run_marker.py"
           ).read_text(encoding="utf-8")
    assert 'rec["lever_hint_covered"]' in src, (
        "run_marker が lever_hint_covered を残さなくなった。"
        "drift 側の切り分けが黙って効かなくなります")
