"""`catchup_grid()` の1行目が「見直し」であることを縛る。

## なぜ要るか（2026-09-01 に足した）

`simulate()` は `payments` の先頭に**当初の返済額**を必ず1件 積みます
（1回目・90,855円）。これは見直しで動いた点ではなく、輪の外で置いた種です。

`catchup_grid()` はその種をそのまま流していたので、
**表の1行目が「1回目・追いついた」**になっていました。
表の主題は「125パーセントの頭打ちが、何回目まで続くか」で、
読み上げは「4.0% は 241回目まで解けない」と言います。
**画面の1行目が、その筋に真っ向から反していました。**

`docs/JOURNAL.md` に **3周**「まだ直っていない」と書かれ、
**3周とも実物は開かれていません**（`retro.tool_suspect()` の
「実物に当たった回 0」）。この検査は、そこを機械の側へ移すためのものです。

**覆る条件**: `simulate()` が種を積まなくなったら、この検査ごと消してよい
（そのとき `test_seed_exists` が先に赤くなります）。
"""
from src.calc import hendo


def test_seed_exists():
    """種（1回目・見直しではない）は `simulate()` 側に在り続ける。"""
    seed = hendo.simulate()["payments"][0]
    assert seed["月"] == 1
    assert seed["返済額"] == seed["必要額"]
    assert seed["頭打ち"] is False


def test_catchup_grid_drops_the_seed():
    """表には見直しの点しか出さない（1回目は出さない）。"""
    rows = hendo.catchup_grid()
    assert rows, "見直しの点が1つも無い"
    assert all(r["何回目から"] >= 2 for r in rows), rows[0]
    assert rows[0]["何回目から"] == 61, rows[0]


def test_first_row_matches_the_story():
    """**1行目は「頭打ち」**。読み上げ（241回目まで解けない）と同じ向き。"""
    rows = hendo.catchup_grid()
    assert rows[0]["頭打ち"] == "頭打ち", rows[0]
    caught = [r for r in rows if r["頭打ち"] == "追いついた"]
    assert caught and caught[0]["何回目から"] == 241, caught[:1]


def test_the_seed_is_the_only_row_dropped():
    """落としたのは種の1件だけ（見直しを1つも失っていない）。"""
    payments = hendo.simulate()["payments"]
    assert len(hendo.catchup_grid()) == len(payments) - 1
