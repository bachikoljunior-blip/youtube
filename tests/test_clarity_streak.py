"""**「2回 続けて門を越えた」を、目ではなく数で決める所**（2026-09-02 11:4x）。

`docs/JOURNAL.md`「次の回へ」2. の原文:

> **`文字/コマ` が 2回 続けて門を越えたら**（別々の回・**n が増えた状態で**）、
> `script_writer.{long,short}_script_problems` に入れること。**1回では入れないこと**

**この条件は、この回まで散文にしか無く、道具は1文字も見ていませんでした。**
`src/clarity.py` の表は ★ を出しますが、**★ は n が動かなくても同じ字で出ます。**

踏みかけた実物（2026-09-02 11:4x）:

    scripts/retention.py  → `[analytics] …: 500` が1行 出たきり **0本 しか足さず**、
                            それでも 130行 の表を出して**正常終了**
    python -m src.clarity → n は **113本 のまま**、rho も前の回と **1桁も違わず**
                            `文字/コマ -0.200 ★`

**前の回の日誌にも同じ `-0.200 ★` が「初めて越えた」として載っています。**
この2つを並べれば「2回 続けて越えた」に見えますが、**観測は1つです。**
そのまま昇格すると、`script_writer` の門が **n=113 の1点**で立ちます。

**だから連は控え（`data/clarity.jsonl`）の n で数えます。**
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import clarity  # noqa: E402


def _ledger(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "clarity.jsonl"
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                 encoding="utf-8")
    return p


def _row(n: int, rho: float, gate: float = 0.185, ok: bool = True) -> dict:
    return {"at": f"2026-09-0{n % 9 + 1}T00:00:00+00:00", "n": n, "門": gate,
            "対照": -0.45, "対照ok": ok, "rho": {"文字/コマ": rho}}


def test_同じ_n_の読みは控えへ足さない(tmp_path, monkeypatch):
    """**同じ観測を2回 数えないこと。** これが本体の1件です。"""
    led = _ledger(tmp_path, [_row(113, -0.200)])
    monkeypatch.setattr(clarity, "LEDGER", led)
    t = {"n": 113, "門": 0.185, "行": {"文字/コマ": {"最大": -0.200}}}
    _row_out, added = clarity.record(t, -0.45)
    assert added is False, "n が動いていないのに控えへ足しています"
    assert len(clarity.readings()) == 1


def test_n_が増えた回だけ連が進む(tmp_path, monkeypatch):
    led = _ledger(tmp_path, [_row(113, -0.200)])
    monkeypatch.setattr(clarity, "LEDGER", led)
    assert clarity.streak("文字/コマ") == 1

    # 同じ n で撃ち直しても 1 のまま（＝ 昇格しない）
    clarity.record({"n": 113, "門": 0.185, "行": {"文字/コマ": {"最大": -0.200}}}, -0.45)
    assert clarity.streak("文字/コマ") == 1, "同じ n の撃ち直しで連が進んでいます"

    # n が増えて、なお門を越えたら 2（＝ 昇格）
    clarity.record({"n": 140, "門": 0.166, "行": {"文字/コマ": {"最大": -0.210}}}, -0.45)
    assert clarity.streak("文字/コマ") == 2
    assert clarity.streak("文字/コマ") >= clarity.PROMOTE_STREAK


def test_門を割った回は連が切れる(tmp_path, monkeypatch):
    led = _ledger(tmp_path, [_row(113, -0.200), _row(140, -0.100, gate=0.166)])
    monkeypatch.setattr(clarity, "LEDGER", led)
    assert clarity.streak("文字/コマ") == 0


def test_対照が死んでいる回は連に数えない(tmp_path, monkeypatch):
    """**計器が死んでいる回の ★ は読めません**（`control()` の註）。"""
    led = _ledger(tmp_path, [_row(113, -0.200), _row(140, -0.210, gate=0.166, ok=False)])
    monkeypatch.setattr(clarity, "LEDGER", led)
    assert clarity.streak("文字/コマ") == 0


def test_報告が連を必ず印字する():
    """**散文に戻さないこと。** 昇格の条件は毎周 画面に出ること。"""
    src = (ROOT / "src" / "clarity.py").read_text(encoding="utf-8")
    assert "PROMOTE_STREAK" in src
    assert "streak(" in src
    # `report_lines()` が連を出していること（`record`/`streak` を呼んでいる）
    body = src.split("def report_lines(")[1]
    assert "record(" in body and "streak(" in body, \
        "報告が控えを見ていません —— ★ を目で2回 見る形に戻っています"
