"""**独立評価の待ち行列の選び方**と、**N本を同時に回す形**を固定する。

## なぜ要るか（2026-08-16）

### 1. `*.plan.json` が偽物の待ちとして数えられていた

待ち行列には1本につき2つのファイルが入ります ——
`<ID>.json`（読み上げ文）と `<ID>.plan.json`（コマの列）。
`glob("*.json")` は**両方**返し、`Path.stem` は後者から
**`<ID>.plan` という、点の付けようがない名前**を作ります。

8/15 23:4x の回がこれを見つけて `scripts/critique_queue.py`（一覧）を直しましたが、
**点を付ける側（`critique_run.py`）は直っていませんでした。**
実測で **52件中13件**が偽物。`<ID>.plan` は `<ID>` のすぐ後ろに並ぶので、
**本物に点が付いた次の回で必ず先頭に来て、`load()` が SystemExit で止まります**
＝ 待ち行列がそこで永久に詰まります。

**片方だけ直す形は、このリポジトリで通算5回目です。**

### 2. 1回1本では、積まれるほうが速い

前の回の (a2) 問い3 が「待ち行列37本に対して `--next` は1回1本。
`--jobs` の実測（生成側は同時6で2.66倍）を評価の段では取っていない」と残しました。
材料はディスクにあるので**生成は0回**です。

## ここで固定すること

1. `.plan.json` を待ちに数えないこと（**この直しの目的そのもの**）
2. 点の付いた本を数えないこと（元からの動き。壊さない）
3. `--count N` が N本ぶんを積むこと。**訊く段は並列・記録は1本ずつ**
   （`critique_record.py` は共有の台帳に書くので、並列にすると行が壊れる）
4. 1本の材料が欠けても、**残りを落とさないこと**
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import critique_run  # noqa: E402


def _queue(tmp_path: Path, ids: list[str], plans: list[str] = ()) -> Path:
    q = tmp_path / "critique_queue"
    q.mkdir()
    for vid in ids:
        (q / f"{vid}.json").write_text(
            json.dumps({"video_id": vid, "narration": ["あ"], "orientation": "縦"}),
            encoding="utf-8")
        (q / f"{vid}.jpg").write_bytes(b"\xff\xd8\xff")
    for vid in plans:
        (q / f"{vid}.plan.json").write_text("[]", encoding="utf-8")
    return q


def _log(tmp_path: Path, scored: list[str]) -> Path:
    d = tmp_path / "data"
    d.mkdir(exist_ok=True)
    log = d / "critique.jsonl"
    log.write_text("".join(json.dumps({"video": v, "scores": [5, 5, 5]}) + "\n"
                           for v in scored), encoding="utf-8")
    return log


def _patch(monkeypatch, tmp_path, ids, plans=(), scored=()):
    q = _queue(tmp_path, ids, plans)
    _log(tmp_path, list(scored))
    monkeypatch.setattr(critique_run, "QUEUE", q)
    monkeypatch.setattr(critique_run, "ROOT", tmp_path)
    return q


def test_planjsonを待ちに数えない(monkeypatch, tmp_path):
    _patch(monkeypatch, tmp_path, ids=["aaa", "bbb"], plans=["aaa", "bbb"])
    assert critique_run.pending_ids() == ["aaa", "bbb"]


def test_点の付いた本を数えない(monkeypatch, tmp_path):
    _patch(monkeypatch, tmp_path, ids=["aaa", "bbb"], plans=["aaa"], scored=["aaa"])
    assert critique_run.pending_ids() == ["bbb"]


def test_本物に点が付いても偽物が先頭に来ない(monkeypatch, tmp_path):
    """**これが実際に詰まる形。** `aaa` を評価した次の回に `aaa.plan` が先頭へ来る。"""
    _patch(monkeypatch, tmp_path, ids=["aaa", "zzz"], plans=["aaa"], scored=["aaa"])
    first = critique_run.pending_ids()[:1]
    assert first == ["zzz"], f"偽物を選んだ: {first}"


def test_countNがN本ぶんを積む(monkeypatch, tmp_path, capsys):
    """**訊く段だけ並列。** ここでは `claude -p` を呼ばずに点を返させる。"""
    _patch(monkeypatch, tmp_path, ids=["aaa", "bbb", "ccc"], plans=["aaa"])
    seen: list[Path] = []

    def fake_ask(n, prompt, workdir):
        seen.append(Path(workdir))
        return n, "見ました。\nSCORE: 7"

    recorded: list[list[str]] = []
    monkeypatch.setattr(critique_run, "ask_one", fake_ask)
    monkeypatch.setattr(critique_run.subprocess, "run",
                        lambda cmd, **kw: recorded.append(cmd) or type("P", (), {"returncode": 0})())

    rc = critique_run.main(["--count", "2", "--jobs", "2"])
    assert rc == 0
    # 2本 × 3体
    assert len(seen) == 2 * critique_run.CRITICS
    # **作業場は本ごとに別。** 同じ場所に置くと隣の本の画像が開ける
    assert len({p.name for p in seen}) == 2
    # 記録は1本ずつ、順に
    assert [c[2] for c in recorded] == ["aaa", "bbb"]
    assert all(c[3:] == ["7.0", "7.0", "7.0"] for c in recorded)


def test_材料の欠けた1本で残りを落とさない(monkeypatch, tmp_path):
    q = _patch(monkeypatch, tmp_path, ids=["aaa", "bbb"])
    (q / "aaa.jpg").unlink()          # contact sheet が無い ＝ load() が SystemExit

    monkeypatch.setattr(critique_run, "ask_one",
                        lambda n, prompt, workdir: (n, "SCORE: 6"))
    recorded: list[list[str]] = []
    monkeypatch.setattr(critique_run.subprocess, "run",
                        lambda cmd, **kw: recorded.append(cmd) or type("P", (), {"returncode": 0})())

    critique_run.main(["--count", "2"])
    assert [c[2] for c in recorded] == ["bbb"], "欠けた1本で残りごと止まった"


def test_材料の欠けた本は枠を食わない(monkeypatch, tmp_path):
    """**`--count 2` は「先頭2本」ではなく「2本回す」。**

    永久に評価できない本（実測で未評価36本のうち2本）が先頭にいると、
    先頭を切り取る形では**毎回その本が1枠ずつ食い続けます。**
    """
    q = _patch(monkeypatch, tmp_path, ids=["aaa", "bbb", "ccc"])
    (q / "aaa.jpg").unlink()

    monkeypatch.setattr(critique_run, "ask_one",
                        lambda n, prompt, workdir: (n, "SCORE: 6"))
    recorded: list[list[str]] = []
    monkeypatch.setattr(critique_run.subprocess, "run",
                        lambda cmd, **kw: recorded.append(cmd) or type("P", (), {"returncode": 0})())

    critique_run.main(["--count", "2"])
    assert [c[2] for c in recorded] == ["bbb", "ccc"], "欠けた本が枠を食った"


def test_3体そろわなければ記録しない(monkeypatch, tmp_path):
    _patch(monkeypatch, tmp_path, ids=["aaa"])
    monkeypatch.setattr(critique_run, "ask_one",
                        lambda n, prompt, workdir: (n, "SCORE: 6" if n < 3 else ""))
    recorded: list[list[str]] = []
    monkeypatch.setattr(critique_run.subprocess, "run",
                        lambda cmd, **kw: recorded.append(cmd) or type("P", (), {"returncode": 0})())

    assert critique_run.main(["--count", "1"]) == 1
    assert not recorded, "嘘の点を記録した。**検査そのものが死にます**"


def test_dryは記録しない(monkeypatch, tmp_path):
    _patch(monkeypatch, tmp_path, ids=["aaa", "bbb"])
    monkeypatch.setattr(critique_run, "ask_one",
                        lambda n, prompt, workdir: (n, "SCORE: 8"))
    recorded: list[list[str]] = []
    monkeypatch.setattr(critique_run.subprocess, "run",
                        lambda cmd, **kw: recorded.append(cmd) or type("P", (), {"returncode": 0})())
    assert critique_run.main(["--count", "2", "--dry"]) == 0
    assert not recorded
