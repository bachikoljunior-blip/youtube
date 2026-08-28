"""**本数を増やすと、その日の再生の合計は増えるのか。**（2026-08-28 に足した）

`day_cap.measure()` が答えているのは「その日の**何本に**再生が付くか」で、
**「その日いくつ付くか」ではありません。** 上限 10本 は「11本目から 0」と
言うだけで、**その 10本の合計が本数で動くかどうかについては何も言っていません。**

`scripts/eta.py` の段1 は「1日 n本 × 1本あたり再生」で解いており、
**`density` の腕が効くのは、ここが正のときだけ**です。

**この検査が守っているのは2つ**:

  1. 立ち上がり（1〜2本/日）を混ぜた `rho` を、そのまま density の根拠に
     しないこと。**実測 08/28 で符号が逆になります**（全24日 +0.75 ／
     上限まで出した8日 -0.01 ／ 08/19〜08/24 の6日 -0.76）
  2. 合計の段差（08/25 に 2.9倍 落ちた）が印字から消えないこと ——
     段差があるあいだ、相関は2つの群を混ぜています
"""
from __future__ import annotations

import datetime as dt
import json

from src import day_cap


def _views(tmp_path, rows):
    p = tmp_path / "views.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return p


def _forms(tmp_path, mapping):
    p = tmp_path / "video_forms.json"
    p.write_text(json.dumps({"forms": mapping}), encoding="utf-8")
    return p


def _row(vid, day, hour, views, age_h=24.0):
    pub = dt.datetime.fromisoformat(f"{day}T{hour:02d}:00:00+09:00")
    at = (pub + dt.timedelta(hours=age_h)).astimezone(dt.timezone.utc)
    return {"id": vid, "at": at.isoformat().replace("+00:00", "Z"),
            "hours": age_h, "views": views}


def _day(day, n, total, cap=10):
    """その日に n本。**上限 cap 本までに `total` を割り振り、残りは 0再生**。

    実物がこの形です（08/20 は 25本 出して 10本にしか付いていません）。
    0再生 の本が無いと `measure()` が崩れを観測できず、`cap` が
    「その日の本数」まで上がってしまうので、**そこも実物に合わせています。**
    """
    live = min(n, cap)
    per = max(1, total // live)
    return [_row(f"{day}-{i}", day, 5 + (i % 18), per if i < live else 0)
            for i in range(n)]


SCALE = [("2026-08-10", 10, 7900), ("2026-08-11", 25, 6300),
         ("2026-08-12", 25, 6600), ("2026-08-13", 12, 9800),
         ("2026-08-14", 10, 8000), ("2026-08-15", 19, 3500)]


def test_合計が本数について平らなら相関は正にならない(tmp_path):
    """**ほぼ同じ合計を、違う本数で割った日を並べる。**"""
    rows = []
    for day, n, total in [("2026-08-01", 4, 7900), ("2026-08-02", 8, 8100),
                          ("2026-08-03", 16, 8000), ("2026-08-04", 20, 7950),
                          ("2026-08-05", 10, 8050), ("2026-08-06", 12, 7980)]:
        rows += _day(day, n, total)
    v = _views(tmp_path, rows)
    m = day_cap.day_total(v, _forms(tmp_path, {}))
    assert m["n_days"] == 6
    assert m["rho"] is not None
    assert m["rho"] < 0.3, f"平らな合計を「本数が効く」と読んでいます: {m['rho']}"


def test_合計が本数に比例するなら相関は正に出る(tmp_path):
    """**逆向きも出せること。** ここが出せないと、上の検査は何も言っていない。"""
    rows = []
    for day, n in [("2026-08-01", 4), ("2026-08-02", 8), ("2026-08-03", 16),
                   ("2026-08-04", 20), ("2026-08-05", 10), ("2026-08-06", 12)]:
        rows += _day(day, n, 500 * n, cap=64)
    v = _views(tmp_path, rows)
    m = day_cap.day_total(v, _forms(tmp_path, {}))
    assert m["rho"] is not None and m["rho"] > 0.9, m["rho"]


def test_立ち上がりを混ぜた相関をそのまま出さないこと(tmp_path):
    """**実物で符号が逆になった形**（08/28 の実測）。

    面に載る前の日（1〜2本・合計 数十回）を4日 足すだけで、
    平らな合計についての相関が **正** に化けます。
    `rho_scale`（上限まで出した日だけ）は化けません。
    """
    rows = []
    for day, n in [("2026-08-01", 1), ("2026-08-02", 2), ("2026-08-03", 1),
                   ("2026-08-04", 2)]:
        rows += _day(day, n, 20 * n)
    for day, n, total in SCALE:
        rows += _day(day, n, total)
    v = _views(tmp_path, rows)
    f = _forms(tmp_path, {})
    assert day_cap.measure(v, f)["cap"] == 10, "検査の土台（上限10本）が崩れています"
    m = day_cap.day_total(v, f)
    assert m["rho"] > 0.3, "この検査の前提（混ぜると正に化ける）が崩れています"
    assert m["rho_scale"] is not None, "上限まで出した日だけの相関が出ていません"
    assert m["rho_scale"] < 0.3, f"上限まで出した日だけでも正に出ています: {m['rho_scale']}"

    out = "\n".join(day_cap.day_total_lines(v, f))
    assert f"{m['rho_scale']:+.2f}" in out, "読むべき側の数が印字に出ていません"
    assert "そちらを使わないこと" in out, "混ぜた側を使うなという註が消えています"


def test_合計の段差を見つけて印字する(tmp_path):
    """**本数を変えずに合計だけ落ちた日**を、境目として出すこと。"""
    rows = []
    for day in ["2026-08-01", "2026-08-02", "2026-08-03"]:
        rows += _day(day, 12, 8000)
    for day in ["2026-08-04", "2026-08-05", "2026-08-06"]:
        rows += _day(day, 12, 2000)
    v = _views(tmp_path, rows)
    f = _forms(tmp_path, {})
    m = day_cap.day_total(v, f)
    assert m["drop"] is not None, "段差を見つけていません"
    assert m["drop"]["at"] == dt.date(2026, 8, 4), m["drop"]
    assert m["drop"]["ratio"] > 3.5, m["drop"]
    out = "\n".join(day_cap.day_total_lines(v, f))
    assert "落ちています" in out
    assert "本数は境目で変わっていません" in out


def test_段差が無ければ何も言わない(tmp_path):
    rows = []
    for day in ["2026-08-01", "2026-08-02", "2026-08-03",
                "2026-08-04", "2026-08-05", "2026-08-06"]:
        rows += _day(day, 12, 8000)
    v = _views(tmp_path, rows)
    m = day_cap.day_total(v, _forms(tmp_path, {}))
    assert m["drop"] is None, m["drop"]


def test_長尺は既定で外れる(tmp_path):
    """`by_day` と同じ扱い。ショートの面の話なので長尺を混ぜない。"""
    rows = _day("2026-08-01", 4, 2000) + [_row("L1", "2026-08-01", 20, 3)]
    v = _views(tmp_path, rows)
    f = _forms(tmp_path, {"L1": "長尺"})
    assert day_cap.day_total(v, f)["days"][0]["n"] == 4
    assert day_cap.day_total(v, f, include_long=True)["days"][0]["n"] == 5


def test_上限の行と同じ出力に並ぶ(tmp_path):
    """`lines()` から消えないこと（消えると、誰もこの数を見ません）。"""
    rows = []
    for day in ["2026-08-01", "2026-08-02", "2026-08-03",
                "2026-08-04", "2026-08-05", "2026-08-06"]:
        rows += _day(day, 12, 4800)
    v = _views(tmp_path, rows)
    out = "\n".join(day_cap.lines(v))
    assert "本数 → その日の合計" in out
