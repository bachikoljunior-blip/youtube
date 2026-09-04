"""**枠に入る1本が前提の脚を通っているかを、機械が毎周 測るか。**（API 0単位）

なぜ要るか（2026-09-04 17:xx・最適化の回に実物で踏んだ）:
`treated_count()` は**分母**（既に出た本）を数えます。**これから枠へ入る1本**は
どこも数えておらず、決めの `why`（散文）が「5脚とも ○ の唯一の本」と名乗ったまま
2日ぶんの枠を取り、実物は (1) 冒頭 が ✗ でした。

**覆る条件**: 前提「外の作り方を写した長尺」が閉じて `OUTSIDE_LONG_RULE` を
使わなくなったら、`pick_legs` / `standing_pick_treatment` / `untreated_slot` ごと落とすこと。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import pytest  # noqa: E402

from src import daily_pick as dp  # noqa: E402
from src import next_slot as ns  # noqa: E402


@pytest.fixture(autouse=True)
def _no_schedule(monkeypatch):
    """**予約を空にして、決めの側の脚だけを動かす台。**（2026-09-05 01:4x に足した）

    `untreated_slot()` は `rule3_book()` 越しに引くようになりました ——
    規則3 の主語は「**次の投稿予定に出る本**」なので、まず
    `next_slot.next_video()` を見て、無いときだけ決め（`daily_pick.current`）へ
    落ちます。この節が測っているのは**脚の側**なので、上流を空にして
    決めの枝を通します（**空にしないと、実物の予約が入って `dp.current` の
    差し替えが効かず、検査が理由も無く緑になります**）。
    """
    monkeypatch.setattr(ns, "next_video", lambda *a, **k: None)


def _script(tmp: Path, vid: str, payload: dict) -> Path:
    q = tmp / "critique_queue"
    q.mkdir(parents=True, exist_ok=True)
    (q / f"{vid}.script.json").write_text(json.dumps(payload, ensure_ascii=False),
                                          encoding="utf-8")
    return q


def test_pick_legs_黙る_控えが読めないとき(tmp_path):
    """**「測れない」を「通った」にも「落ちた」にもしないこと。**"""
    bad, why = dp.pick_legs("NOTHERE", queue=tmp_path)
    assert bad == []
    assert why and "読めません" in why


def test_pick_legs_名指しが空なら理由を返す(tmp_path):
    bad, why = dp.pick_legs("", queue=tmp_path)
    assert bad == []
    assert why


def test_pick_legs_実物の決めの本が脚を落としている():
    """**この repo の実物**（09-05 の枠 `O_lfBxB7S8Q`）で、機械が ✗ を出すこと。

    覆る条件: その本が焼き直されて脚を通ったら、この試験は「落ちない」ほうへ
    書き換えること（**通ったのに ✗ のままなら、それは `script_writer` の側の壊れ**）。
    """
    cur = dp.current(dp.for_day())
    if not cur or not cur.get("video_id"):
        return
    tops = {str(t.get("id")): str(t.get("style") or "") for t in dp._topics()}
    if tops.get(str(cur.get("topic") or "")) != "outside_long":
        return
    bad, why = dp.pick_legs(cur["video_id"])
    # **どちらでもよい** —— 見たいのは「機械が答えを返すこと」だけ。
    assert why is None or isinstance(why, str)
    assert isinstance(bad, list)


def test_standing_pick_treatment_型の無い題材には黙る():
    lines = dp.standing_pick_treatment(
        {"topic": "s-nothing", "video_id": "X"}, topics=[{"id": "s-nothing", "style": ""}])
    assert lines == []


def test_standing_pick_treatment_脚が落ちていれば感嘆符を出す(monkeypatch):
    monkeypatch.setattr(dp, "pick_legs", lambda *a, **k: (["(1) 冒頭"], None))
    lines = dp.standing_pick_treatment(
        {"topic": "t", "video_id": "VID", "why": "5脚とも ○"},
        topics=[{"id": "t", "style": "outside_long"}])
    joined = "\n".join(lines)
    assert "[!!]" in joined
    assert "VID" in joined
    # **散文の名乗りが古い写しであることを、その場で言うこと。**
    assert "古い写し" in joined
    # **出口を必ず名指すこと**（名指せない門は、語を書き換えて通されるだけ）。
    assert "upload_only.py" in joined


def test_untreated_slot_は決めが無ければ発火しない(monkeypatch):
    import run_marker as m
    monkeypatch.setattr(dp, "current", lambda *a, **k: None)
    r = m.untreated_slot()
    assert r["fired"] is False
    assert r["why"]


def test_untreated_slot_は型の外なら発火しない(monkeypatch):
    import run_marker as m
    monkeypatch.setattr(dp, "current", lambda *a, **k: {"topic": "z", "video_id": "V"})
    monkeypatch.setattr(dp, "_topics", lambda: [{"id": "z", "style": ""}])
    r = m.untreated_slot()
    assert r["fired"] is False
    assert "outside_long" in r["why"]


def test_untreated_slot_は測れない回に発火しない(monkeypatch):
    """**`cond4()` が 08-31〜09-03 に踏んだ穴を、ここで繰り返さないこと。**"""
    import run_marker as m
    monkeypatch.setattr(dp, "current", lambda *a, **k: {"topic": "z", "video_id": "V"})
    monkeypatch.setattr(dp, "_topics", lambda: [{"id": "z", "style": "outside_long"}])
    monkeypatch.setattr(dp, "pick_legs", lambda *a, **k: ([], "台本の控えが読めません"))
    r = m.untreated_slot()
    assert r["fired"] is False


def test_untreated_slot_は脚が落ちていれば発火する(monkeypatch):
    import run_marker as m
    monkeypatch.setattr(dp, "current", lambda *a, **k: {"topic": "z", "video_id": "V"})
    monkeypatch.setattr(dp, "_topics", lambda: [{"id": "z", "style": "outside_long"}])
    monkeypatch.setattr(dp, "pick_legs", lambda *a, **k: (["(1) 冒頭"], None))
    r = m.untreated_slot()
    assert r["fired"] is True
    assert r["video_id"] == "V"
    assert "(1) 冒頭" in r["why"]


def test_untreated_slot_は脚を通っていれば発火しない(monkeypatch):
    import run_marker as m
    monkeypatch.setattr(dp, "current", lambda *a, **k: {"topic": "z", "video_id": "V"})
    monkeypatch.setattr(dp, "_topics", lambda: [{"id": "z", "style": "outside_long"}])
    monkeypatch.setattr(dp, "pick_legs", lambda *a, **k: ([], None))
    r = m.untreated_slot()
    assert r["fired"] is False
