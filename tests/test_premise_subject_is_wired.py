"""`premise_subject` を毎周 印字する `run_marker --write` の検査（2026-09-01）。

## なぜ要るか

`scripts/premise_subject.py` は `retro.py` が名指しした
**「どこからも呼ばれない」道具**の1本で、**3周 続けて申し送りに出ています**
（2026-08-31 16:5x ／ 2026-09-01 01:3x ／ 01:4x）。
`doc_usage` ／ `stale_scheduled` ／ `endcard_check` ／ `pool_drain` と同じ形 ——
**道具は在り、答えを出し、撃つ側がどこにも居ませんでした。**

**なぜ §1 なのか。** `eta.py` が毎周 印字しているとおり、
**到達日が動くのは前提を1件 閉じたときだけ**です。その1件を選ぶ前に
「反証条件が、主張の主語を数えているか」が見えていないと、
**閉じた腕と、実際に動いた腕が別物**になります
（`eta.py --alloc` は `lever:` の分布で次の1件の置き場を出す）。

## ここで固定している「既知の当たり」

1. **食い違う行が在るときだけ出す**（無い回は1行も出さない）
2. **`[!]`／`[?]` の行だけ**を出す（24件を毎周 貼らない）
3. **`run_marker --write` が毎周 呼ぶ**（配線が外れたら、この検査が落ちる）
4. **道具が落ちても回は止めない**（印が本体・これは付け足し）
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import premise_subject  # noqa: E402
import run_marker  # noqa: E402


def test_writeが毎周呼んでいる():
    """**配線そのもの。** `write()` の本体から名前で呼ばれていること。"""
    src = (ROOT / "scripts" / "run_marker.py").read_text(encoding="utf-8")
    body = src.split("def write() -> int:", 1)[1].split("\nSEEN_KIND", 1)[0]
    assert "_premise_subject_lines()" in body, (
        "`run_marker --write` が `premise_subject` を呼んでいません。"
        "**呼ぶ側が居ない道具は、在らないのと同じです**"
        "（`retro.py` の「どこからも呼ばれない」）")


def _row(claim, *, mismatch=False, lever_off=False, lever="rpm",
         subject=("density",), measured=("density",), deadline="2026-09-02"):
    return {"claim": claim, "deadline": deadline, "lever": lever, "side": "dist",
            "subject": set(subject), "measured": set(measured),
            "mismatch": mismatch, "lever_off": lever_off}


def test_食い違いが無ければ1行も出さない(monkeypatch):
    monkeypatch.setattr(premise_subject, "audit",
                        lambda *a, **k: [_row("鳴らない行")])
    assert run_marker._premise_subject_lines() == []


def test_食い違う行だけを出す(monkeypatch):
    rows = [
        _row("鳴らない行"),
        _row("主語が交わらない行", mismatch=True, lever="per_video",
             subject=("per_video",), measured=("sub_rate",)),
        _row("札が値と合っていない行", lever_off=True),
    ]
    monkeypatch.setattr(premise_subject, "audit", lambda *a, **k: rows)
    out = "\n".join(run_marker._premise_subject_lines())
    assert "主語が交わらない行" in out
    assert "札が値と合っていない行" in out
    assert "鳴らない行" not in out          # **24件を毎周 貼らない**
    assert "主語と交わらない 0件" not in out
    assert "合っていない 1件" in out


def test_noteの鎖で外れた行は印に出さない(monkeypatch):
    """**2026-09-01。** `[n]`（`note:` に腕への鎖がある行）は**決まった行**なので、
    毎周 §1 に貼りません —— 貼る対象は「**この回に決めるもの**」だけです
    （`retro.py` の「(c) に倒しずみ」を未決と分けたのと同じ形）。
    全文は `python scripts/premise_subject.py` に `[n]` で出ます。
    """
    rows = [_row("鎖が本文にある行", lever_off=False)]
    rows[0]["note_backed"] = True
    rows[0]["note_line"] = "実効RPM ＝ Σ_形（再生の割合 × その形の帯）"
    monkeypatch.setattr(premise_subject, "audit", lambda *a, **k: rows)
    assert run_marker._premise_subject_lines() == []


def test_多い回は打ち切って全文の撃ち方を出す(monkeypatch):
    rows = [_row(f"行{i}", lever_off=True) for i in range(9)]
    monkeypatch.setattr(premise_subject, "audit", lambda *a, **k: rows)
    out = run_marker._premise_subject_lines(cap=4)
    assert sum(1 for ln in out if "[?]" in ln) == 4
    assert "ほか 5件" in "\n".join(out)
    assert "scripts/premise_subject.py" in "\n".join(out)


def test_道具が落ちても回は止めない(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("台帳が読めません")

    monkeypatch.setattr(premise_subject, "audit", boom)
    out = run_marker._premise_subject_lines()
    assert len(out) == 1
    assert "手で撃つこと" in out[0]         # **印は本体・これは付け足し**
