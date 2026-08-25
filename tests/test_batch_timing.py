"""**かかった時間が台帳に残ること**を検査する。

## なぜ要るか（2026-08-15 22:3x）

`retro.py` の持ち越しに **`--jobs` が4回**（19:0x / 19:2x / 20:5x / 22:0x）出ています。
4回とも「次の回で測る」と書かれ、**4回とも測られませんでした。**

理由は忙しさではありません。**測れなかったからです。**
`data/batch_runs.jsonl` に入っていたのは `at / hour / date / slots / results` だけで、
**`jobs` も、かかった秒数も入っていませんでした。** 台帳を後から読んでも
「何本ずつ走らせたのか」すら分かりません。19:0x の「6本を4.7分」は
**その回の画面にしか無く**、次の回には残っていない。

だから毎回「まず測り直すところから」になり、生成に10分かかるので後回しになる。
**それが4回くり返されました。**

検査するのは「速くなったか」ではありません（それは題材と本数で動きます）。
**次の回が読める形で残っているか**です。残っていなければ、また持ち越されます。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts import batch_build  # noqa: E402
from tests.test_batch_parallel import _Recorder, _Sink, _topics  # noqa: E402


def _run(monkeypatch, ids, delays=None, fail_build=None, jobs=3):
    """`test_batch_parallel` と同じ仕掛けだが、**書いた行を JSON で返す**。"""
    rec = _Recorder(delays, fail_build)
    monkeypatch.setattr(batch_build, "run", rec)
    monkeypatch.setattr(batch_build, "pick",
                        lambda c, e, per_calc=None: _topics(ids))
    monkeypatch.setattr(batch_build, "check_window", lambda d, f: None)
    # **本数枠の門を、実物の控えから切り離す**（2026-08-17 に足した）。
    # `batch_build` は撃つ前に `src/upload_cap.state()` を見ます。素通しにすると
    # **`data/uploaded.jsonl` の中身で検査の答えが変わり**、いつか
    # 「今日はもう92本上げた」だけで並列の検査が赤くなります
    # （`test_batch_slots.py` が `taken=` で同じことを塞いでいます）。
    monkeypatch.setattr(batch_build.upload_cap, "state", lambda: _open_window())
    written: list[str] = []
    monkeypatch.setattr(batch_build.Path, "open",
                        lambda self, *a, **k: _Sink(written))
    batch_build.main([
        "--count", str(len(ids)), "--date", "2026-08-30", "--jobs", str(jobs),
    ])
    return json.loads(_ledger(written))


def _ledger(written: list[str]) -> str:
    """**記録の行**（`data/batch_runs.jsonl` に積まれるほうの1行）を拾う。

    **`written[0]` ではありません**（2026-08-24 に直した。5件が赤かった）。
    8/22 の A/B が同じ sink へ `{"at": …, "topic": …, "opening_motion": …}` を
    **本数ぶん先に**書くようになったので、`written[0]` はその行になり、
    `jobs` / `wall_sec` / `results` が `KeyError` で落ちていました。

    **同じ欠陥を 8/23 に `tests/test_batch_parallel.py` で直しています。**
    直したのは片方だけで、**こちらは名前が違うだけの双子**でした ——
    `pytest -x` が先に `test_batch_parallel` を通していたので、
    赤はそのぶん遅れて出ます。**直す回は、同じ sink を読む検査を全部見ること。**

    A/B の行と記録の行は **どちらも `opening_motion` を持ちます**。
    記録の行だけが持つのは `results` です。
    """
    for row in written:
        if '"results"' in row:
            return row
    raise AssertionError(f"記録の行が1つも書かれていません: {written!r}")


# --- 1. 台帳に、次の回が読めるものが残ること -------------------------------

def test_ledger_records_jobs(monkeypatch):
    """**`jobs` が残ること。** これが無いと、後から条件を復元できません。"""
    row = _run(monkeypatch, ["a", "b", "c"], jobs=3)
    assert row["jobs"] == 3


def test_ledger_records_wall_and_serial_time(monkeypatch):
    """壁時計と「直列なら」の両方。**片方だけでは倍率が出ません。**"""
    row = _run(monkeypatch, ["a", "b", "c"],
               delays={"a": 0.2, "b": 0.2, "c": 0.2}, jobs=3)
    assert row["wall_sec"] > 0
    assert row["serial_sec"] > 0
    # 3本を同時に走らせたので、直列の合計のほうが必ず長い。
    assert row["serial_sec"] > row["wall_sec"]
    assert row["speedup"] > 1.0


def test_ledger_records_seconds_per_topic(monkeypatch):
    """**1本ずつの秒数。** jobs 別に「1本あたりが太ったか」を見るのはこの値です。

    合計しか残さないと、**本数の違う走りを比べられません。**
    """
    row = _run(monkeypatch, ["a", "b"], delays={"a": 0.2, "b": 0.05}, jobs=2)
    per = {r["topic"]: r["build_sec"] for r in row["results"]}
    assert per["a"] >= 0.2
    assert per["b"] < per["a"]


def test_failed_build_still_records_its_seconds(monkeypatch):
    """**落ちた本も測る。** 落ちるまでの時間も、他の本を待たせています。

    ここを飛ばすと、落ちた回ほど「速かった」ことになって読み違えます。
    """
    row = _run(monkeypatch, ["a", "b"], delays={"a": 0.15}, fail_build={"a"})
    per = {r["topic"]: r.get("build_sec") for r in row["results"]}
    assert per["a"] is not None and per["a"] >= 0.15


def test_jobs_1_speedup_is_about_one(monkeypatch):
    """直列で走らせたら、倍率はほぼ1。**目盛りの校正**です。"""
    row = _run(monkeypatch, ["a", "b"],
               delays={"a": 0.1, "b": 0.1}, jobs=1)
    assert row["jobs"] == 1
    assert 0.8 <= row["speedup"] <= 1.2


# --- 2. 読む側（--report）------------------------------------------------

def test_report_says_it_cannot_tell_from_one_jobs_value(tmp_path, monkeypatch,
                                                        capsys):
    """**1種類の `jobs` しか無いときに、上限を言わないこと。**

    ここで黙って結論を出すと、**4回持ち越された問いに嘘の答えが付きます。**
    """
    log = tmp_path / "batch_runs.jsonl"
    log.write_text(json.dumps({
        "at": "2026-08-15T22:40:00+09:00", "jobs": 3, "count": 2,
        "wall_sec": 600.0, "serial_sec": 1100.0, "speedup": 1.83,
        "results": [{"topic": "a", "build_sec": 560.0},
                    {"topic": "b", "build_sec": 540.0}],
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    monkeypatch.setattr(batch_build, "LOG", log)
    assert batch_build.report() == 0
    out = capsys.readouterr().out
    assert "まだ1種類の `jobs` しか走っていません" in out


def test_report_flags_the_ceiling_when_per_video_swells(tmp_path, monkeypatch,
                                                        capsys):
    """**1本あたりが太ったら、そこが上限**と言うこと。

    倍率ではなく太り方で見るのは、倍率が本数と題材で動くからです。
    """
    log = tmp_path / "batch_runs.jsonl"
    rows = [
        {"at": "2026-08-15T22:00:00+09:00", "jobs": 3, "count": 2,
         "wall_sec": 600.0, "serial_sec": 1100.0, "speedup": 1.83,
         "results": [{"topic": "a", "build_sec": 600.0},
                     {"topic": "b", "build_sec": 600.0}]},
        {"at": "2026-08-15T23:00:00+09:00", "jobs": 8, "count": 2,
         "wall_sec": 900.0, "serial_sec": 1800.0, "speedup": 2.0,
         "results": [{"topic": "c", "build_sec": 1200.0},
                     {"topic": "d", "build_sec": 1200.0}]},
    ]
    log.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                           for r in rows), encoding="utf-8")
    monkeypatch.setattr(batch_build, "LOG", log)
    assert batch_build.report() == 0
    out = capsys.readouterr().out
    assert "同時 8 で1本あたりが 2.00倍に太っています" in out


def test_swelling_alone_is_not_called_the_ceiling(tmp_path, monkeypatch, capsys):
    """**1本あたりが太っても、出る本数が増えているうちは上限ではありません。**

    8/15 22:3x の実測がこれでした —— 同時6で1本あたり 1.55倍に太りましたが、
    **1時間あたりに出る本数は 2.66倍**でした。ここで「上限」と書いて止めると、
    **まだ2倍以上ある伸びを捨てます。**
    """
    log = tmp_path / "batch_runs.jsonl"
    rows = [
        {"at": "2026-08-15T22:27:00+09:00", "jobs": 1, "count": 1,
         "wall_sec": 108.0, "serial_sec": 108.0, "speedup": 1.0,
         "results": [{"topic": "a", "build_sec": 104.0}]},
        {"at": "2026-08-15T22:32:00+09:00", "jobs": 6, "count": 6,
         "wall_sec": 239.0, "serial_sec": 1002.0, "speedup": 4.2,
         "results": [{"topic": f"t{i}", "build_sec": 161.0} for i in range(6)]},
    ]
    log.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                           for r in rows), encoding="utf-8")
    monkeypatch.setattr(batch_build, "LOG", log)
    assert batch_build.report() == 0
    out = capsys.readouterr().out
    assert "太り始めた点は上限ではありません" in out
    assert "まだ上げられます" in out


def test_report_calls_the_ceiling_when_throughput_drops(tmp_path, monkeypatch,
                                                        capsys):
    """**出る本数が減ったら、そこは上限**と言うこと。"""
    log = tmp_path / "batch_runs.jsonl"
    rows = [
        {"at": "2026-08-15T22:00:00+09:00", "jobs": 4, "count": 4,
         "wall_sec": 240.0, "serial_sec": 800.0, "speedup": 3.3,
         "results": [{"topic": f"a{i}", "build_sec": 200.0} for i in range(4)]},
        {"at": "2026-08-15T23:00:00+09:00", "jobs": 16, "count": 4,
         "wall_sec": 900.0, "serial_sec": 3400.0, "speedup": 3.8,
         "results": [{"topic": f"b{i}", "build_sec": 850.0} for i in range(4)]},
    ]
    log.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                           for r in rows), encoding="utf-8")
    monkeypatch.setattr(batch_build, "LOG", log)
    assert batch_build.report() == 0
    out = capsys.readouterr().out
    assert "出る本数がいちばん多いのは同時 4" in out
    assert "そこが上限です" in out


def test_report_says_not_yet_when_flat(tmp_path, monkeypatch, capsys):
    """太っていなければ「まだ上げられる」と言うこと（**止めないため**）。"""
    log = tmp_path / "batch_runs.jsonl"
    rows = [
        {"at": "2026-08-15T22:00:00+09:00", "jobs": 3, "count": 2,
         "wall_sec": 600.0, "serial_sec": 1200.0, "speedup": 2.0,
         "results": [{"topic": "a", "build_sec": 600.0},
                     {"topic": "b", "build_sec": 600.0}]},
        {"at": "2026-08-15T23:00:00+09:00", "jobs": 6, "count": 2,
         "wall_sec": 620.0, "serial_sec": 1240.0, "speedup": 2.0,
         "results": [{"topic": "c", "build_sec": 620.0},
                     {"topic": "d", "build_sec": 620.0}]},
    ]
    log.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                           for r in rows), encoding="utf-8")
    monkeypatch.setattr(batch_build, "LOG", log)
    assert batch_build.report() == 0
    out = capsys.readouterr().out
    assert "まだ太っていません" in out


def test_report_is_honest_about_old_rows(tmp_path, monkeypatch, capsys):
    """**時間の入っていない古い行を、混ぜて数えないこと。**

    13回ぶんの古い走りがあります。あれを「測った」に数えると、
    **測っていないのに測ったことになります。**
    """
    log = tmp_path / "batch_runs.jsonl"
    log.write_text(json.dumps({
        "at": "2026-08-15T21:00:00+09:00", "hour": 9, "date": None,
        "slots": ["9"], "results": [{"topic": "a", "video_id": "x"}],
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    monkeypatch.setattr(batch_build, "LOG", log)
    assert batch_build.report() == 1
    out = capsys.readouterr().out
    assert "時間の入った走りがまだありません" in out


def test_report_does_not_build_anything(monkeypatch, capsys):
    """`--report` が生成にも予約にも触らないこと（**数秒で終わる約束**）。"""
    called: list[str] = []
    monkeypatch.setattr(batch_build, "run",
                        lambda *a, **k: called.append("ran") or (0, ""))
    monkeypatch.setattr(batch_build, "pick",
                        lambda *a, **k: called.append("picked") or [])
    began = time.monotonic()
    batch_build.main(["--report"])
    assert called == []
    assert time.monotonic() - began < 2.0


def _open_window():
    """「まだ 92本ぶん撃てる」＝門を素通り。**枠そのものの検査は
    `tests/test_upload_cap.py`** にあります。"""
    from datetime import datetime, timezone

    from src import upload_cap

    return upload_cap.State(False, 0, upload_cap.CAP_PER_DAY,
                            datetime.now(timezone.utc), "検査（枠は開いている）")
