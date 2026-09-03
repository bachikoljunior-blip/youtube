"""**到達日が出ない回は、頭の3行が腕を門1'（登録者 500人）の日数で測ること。**（2026-09-03）

## なぜ要るか

頭の3行は「無限大にしても到達日が 0日 しか動かない腕: `sub_rate`。引かないこと」と
出していた。その 0日 は、到達日そのものが『出ません』の回に測った 0日 で、
律速でないことの証拠ではない。同じ出力の 60行 下で、最初に落ちる門は
門1'（500人・いま 25人）で 532日 と印字されていた。直近 5日 の ship 275件 のうち
`--lever sub_rate` は 7件（`per_video` 108件）。**頭が『引かないこと』と書いた腕は、
実際に引かれていなかった。**

これは印字1つ。止める仕掛けではない。
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import eta  # noqa: E402


def _pl(target_date=None, remaining=475, spd=0.89, caps=(4.49, 6.59)):
    return {
        "target_date": target_date,
        "gates": {"fan_subs_remaining": remaining, "subs_per_day": spd,
                  "subs_remaining": remaining + 500, "days_fan_subs": remaining / spd},
        "lever_days": [
            {"lever": "per_video", "cap": caps[0]},
            {"lever": "sub_rate", "cap": caps[1]},
            {"lever": "rpm", "cap": 40.0},
        ],
    }


def test_到達日が出ない回は門1で腕を測る(tmp_path):
    runs = tmp_path / "runs.jsonl"
    now = datetime.now(timezone.utc).isoformat()
    runs.write_text("\n".join(
        json.dumps({"at": now, "kind": "ship", "lever": "per_video"}) for _ in range(10))
        + "\n" + json.dumps({"at": now, "kind": "ship", "lever": "sub_rate"}) + "\n",
        encoding="utf-8")
    lines = eta.gate_arm_lines(_pl(), runs_path=runs)
    text = "\n".join(lines)
    assert "門1'" in text and "500人" in text
    assert "`sub_rate` を天井 ×6.59" in text
    assert "`per_video` を天井 ×4.49" in text
    assert "2本とも天井まで" in text
    assert "`per_video` 10件 ／ `sub_rate` 1件" in text
    assert "片方しか引かれていません" in text
    base = 475 / 0.89
    assert eta._fmt_days(base / (4.49 * 6.59)) in text


def test_到達日が出る回は出さない(tmp_path):
    assert eta.gate_arm_lines(_pl(target_date=date(2027, 1, 1)),
                              runs_path=tmp_path / "x") == []


def test_門が開いていれば出さない(tmp_path):
    assert eta.gate_arm_lines(_pl(remaining=0), runs_path=tmp_path / "x") == []


def test_headlineが実際にこの行を出す(monkeypatch):
    """**字が在ることと、描かれることは別です。** 呼ばれているかを描かせて見ます。"""
    pl = {"target_date": None, "days_to_target": None,
          "binding": "再生数が天井に当たっている", "lever_hint": "per_video",
          "lever_hint_binding": "per_video", "lever_from": "軌跡",
          "lever_hint_covered": None}
    seen = {}

    def stub(p, **k):
        seen["pl"] = p
        return ["### GATE-ARM-SENTINEL"]

    monkeypatch.setattr(eta, "gate_arm_lines", stub)
    text = "\n".join(eta.headline(pl, None, {"choice": [], "arms": {}}))
    assert "GATE-ARM-SENTINEL" in text and seen["pl"] is pl


def test_到達日が出ない回は門を動かす腕を殺さない():
    """`levers.blocked()` が `--lever sub_rate` を断る根拠（`dead_at_inf`）は、
    全腕が天井で届かない回には立てない。届く腕が1本でも在れば、そのまま。"""
    assert eta.revive_gate_arms(["sub_rate", "rpm"], all_dead=True,
                                fan_subs_remaining=475) == (["rpm"], ["sub_rate"])
    assert eta.revive_gate_arms(["sub_rate"], all_dead=False,
                                fan_subs_remaining=475) == (["sub_rate"], [])
    assert eta.revive_gate_arms(["sub_rate"], all_dead=True,
                                fan_subs_remaining=0) == (["sub_rate"], [])


def test_空のdead_at_infも行に積む():
    """**鍵を落とすと古い行が生き返る**（`levers.latest_arm_state` は
    `arm_dead_at_inf` を持つ最後の行を拾う）。空でも積むこと。"""
    src = (Path(__file__).resolve().parent.parent / "scripts" / "eta.py").read_text(encoding="utf-8")
    assert 'if "lever_dead_at_inf" in pl:' in src
    assert 'if pl.get("lever_dead_at_inf"):\n        row["arm_dead_at_inf"]' not in src


def test_生き返らせた腕は頭に出る():
    pl = _pl()
    pl["lever_gate_revived"] = ("sub_rate",)
    text = "\n".join(eta.gate_arm_lines(pl, runs_path=Path("/nonexistent")))
    assert "`--lever sub_rate` は台帳に書けます" in text
