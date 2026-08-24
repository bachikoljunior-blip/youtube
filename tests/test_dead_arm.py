"""**引き代のない腕**を、選ぶ側に届けるところの検査（2026-08-24）。

`scripts/eta.py` の軌跡は、天井 ×1.00 の腕を**解く前に外します** ——
その腕をどれだけ引いても到達日は1日も動きません。**その事実は
`eta.py` の stdout にしか無く**、`run_marker.py --ship --lever` にも
`drift.py` にも届いていませんでした。実測（8/24）: 名指しは `rpm`、
`density` の天井は ×1.00、それでも同じ日の ship 12件のうち5件が
`--lever density` です。

**門にはしません。** 天井が未判定の前提に乗ることがあるためで、
ここが守るのは「**数が届くこと**」だけです。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import levers  # noqa: E402
from scripts import drift  # noqa: E402


ROW = {"lever_hint": "rpm", "binding": "再生数が天井に当たっている",
       "arm_caps": {"per_video": 2.84, "sub_rate": 3147.0, "rpm": 14.2, "density": 1.0}}


def _write(tmp_path, rows) -> Path:
    p = tmp_path / "eta.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                 encoding="utf-8")
    return p


def test_天井1倍の腕は死んでいると言う():
    st = levers.arm_state(ROW)
    assert st["dead"] == ("density",)
    notes = levers.lever_notes("density", st)
    assert any("天井に着いています" in n for n in notes)


def test_引き代のある腕には天井の警告を出さない():
    notes = levers.lever_notes("rpm", levers.arm_state(ROW))
    assert not any("天井に着いています" in n for n in notes)


def test_名指しと違う腕には理由を求める():
    notes = levers.lever_notes("per_video", levers.arm_state(ROW))
    assert any("名指しは **`rpm`**" in n for n in notes)


def test_名指しどおりなら黙る():
    assert levers.lever_notes("rpm", levers.arm_state(ROW)) == []


def test_none_は腕ではないので何も言わない():
    assert levers.lever_notes("none", levers.arm_state(ROW)) == []


def test_天井の無い行では死んだ腕を作らない():
    """**読めないことと「死んだ腕は無い」は別。** 空を返すこと。"""
    st = levers.arm_state({"lever_hint": "rpm"})
    assert st["dead"] == ()
    # 名指しの行は出てよい（読めているので）。**天井の行だけが出ないこと。**
    assert not any("天井に着いています" in n for n in levers.lever_notes("density", st))


def test_最後の行が_reflect_でも天井を拾う(tmp_path):
    """`--ship` は既定で `--reflect` を撃つので、**最後の行はたいてい reflect**。

    reflect の行は差分の記録で `arm_caps` を持ちません。最後だけ読むと
    天井は永久に読めない —— 入れた当日に踏んだ穴です。
    """
    p = _write(tmp_path, [ROW, {"kind": "reflect", "at": "2026-08-24T10:00:00",
                                "lever_hint": "rpm", "binding": "再生数が天井に当たっている"}])
    st = levers.latest_arm_state(p)
    assert st["dead"] == ("density",)
    assert st["hint"] == "rpm"


def test_壊れた行は飛ばす(tmp_path):
    p = tmp_path / "eta.jsonl"
    p.write_text("{壊れている\n" + json.dumps(ROW, ensure_ascii=False) + "\n", encoding="utf-8")
    assert levers.latest_arm_state(p)["dead"] == ("density",)


def test_無い道具でも空を返して回を止めない(tmp_path):
    assert levers.latest_arm_state(tmp_path / "無い.jsonl")["caps"] == {}


def test_drift_が死んだ腕を選んだ回を数える(tmp_path, monkeypatch):
    runs = tmp_path / "runs.jsonl"
    ships = [
        {"at": "2026-08-23T10:00:00+09:00", "kind": "ship", "what": "a", "lever": "density"},
        {"at": "2026-08-23T11:00:00+09:00", "kind": "ship", "what": "b", "lever": "density"},
        {"at": "2026-08-23T12:00:00+09:00", "kind": "ship", "what": "c", "lever": "rpm"},
        {"at": "2026-08-23T13:00:00+09:00", "kind": "ship", "what": "d"},   # 宣言なしは数えない
    ]
    runs.write_text("\n".join(json.dumps(s, ensure_ascii=False) for s in ships) + "\n",
                    encoding="utf-8")
    monkeypatch.setattr(drift, "RUNS", runs)
    monkeypatch.setattr(drift, "ROOT", tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "eta.jsonl").write_text(
        json.dumps(ROW, ensure_ascii=False) + "\n", encoding="utf-8")
    text = drift.dead_arm_report("2026-08-24")
    assert "**引き代のない腕を選んだ回: 2/3**" in text
    assert "名指し **`rpm`** に従った回: **1/3**" in text


def test_drift_は天井が読めないときそう言う(tmp_path, monkeypatch):
    """**「0件」と言わないこと。** 読めていないのだから、そう印字する。"""
    runs = tmp_path / "runs.jsonl"
    runs.write_text(json.dumps(
        {"at": "2026-08-23T10:00:00+09:00", "kind": "ship", "what": "a", "lever": "density"},
        ensure_ascii=False) + "\n", encoding="utf-8")
    monkeypatch.setattr(drift, "RUNS", runs)
    monkeypatch.setattr(drift, "ROOT", tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "eta.jsonl").write_text("", encoding="utf-8")
    assert "まだありません" in drift.dead_arm_report("2026-08-24")
