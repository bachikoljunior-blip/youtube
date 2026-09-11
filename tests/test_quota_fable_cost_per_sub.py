"""**「100% を越える形では立てない」門の分母が、死んだ台帳を読んでいた**。

2026-09-11 09:4x・optimizer・Opus。

`quota.role_model()` には「役 `hourly`（高レバレッジ）でも、**1体ぶんを足すと
`FABLE_CAP_PCT` を越えるなら Opus へ倒す**」という枝が在ります（越えた後に立てたサブは
その日ぜんぶ落ちる —— `fable_rate()` の註・A10）。その 1体ぶんは
`fable_cost_per_sub()` が測りますが、分母は **`data/runs.jsonl`**（旧 `run_marker.py` の帳簿）で、
**2026-09-05 16:46 を最後に 1行も増えていません**（METHOD §8 ＝ 使わないもの）。

    実測（この回）  `_births_from_runs(09/09 21:13 → 09/10 17:24)` …… **0体**
                    → `fable_cost_per_sub()` …… **None**
                    → `role_model()` の枝は **一度も通らない**（組み直しの 09/05 から 6日）

**分母の口は `data/model_choice.jsonl`**（親がサブを立てる**直前**に 1行ずつ積む・
`record_model_choice`）。**陽性対照**は `quota.ROLE_TIER` の註が持っている実測::

    09/06 16:41 → 09/07 08:04   註「fable **14体** で「Fable のみ」+13 ＝ 0.93%/体」
    `_subs_from_choices(model="fable")`  **14**  ＝ 註と一致
    `_births_from_runs()`                **0**  ＝ 死んだ台帳

**分母は「Fable で立てたサブ」だけ**です（同じ周の `optimizer` は Opus ＝ Fable の目盛りを食わない）。
全部を分母にすると 1体ぶんが半分に見え、切り替えが 1周 遅れます —— それも下で撃ちます。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import quota  # noqa: E402

JST = timezone(timedelta(hours=9))


def _write(tmp_path, rows):
    f = tmp_path / "model_choice.jsonl"
    f.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                 encoding="utf-8")
    return f


def _lap(at: datetime) -> list[dict]:
    """親が 1周に積む 2行（`hourly` ＝ fable・`optimizer` ＝ opus）。"""
    return [
        {"at": at.isoformat(), "work_kind": "hourly:leverage", "model": "fable"},
        {"at": at.isoformat(), "work_kind": "optimizer:other", "model": "opus"},
    ]


def _ledger(tmp_path, laps: int, start: datetime):
    rows: list[dict] = []
    for i in range(laps):
        rows += _lap(start + timedelta(minutes=36 * i))
    return _write(tmp_path, rows)


def test_サブを数える口は_model_choice_であること(tmp_path, monkeypatch):
    t0 = datetime(2026, 9, 9, 21, 13, tzinfo=JST)
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", _ledger(tmp_path, 10, t0))
    got = quota._subs_from_choices(t0 - timedelta(hours=1), t0 + timedelta(hours=12))
    assert got == 20, f"1周 2行 × 10周 ＝ 20体 のはずが {got}"


def test_模型で絞れること_Fable_だけ数える(tmp_path, monkeypatch):
    """**Opus のサブは「Fable のみ」の目盛りを 1%も食いません。**"""
    t0 = datetime(2026, 9, 9, 21, 13, tzinfo=JST)
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", _ledger(tmp_path, 10, t0))
    got = quota._subs_from_choices(t0 - timedelta(hours=1), t0 + timedelta(hours=12),
                                   model="fable")
    assert got == 10, f"Fable のサブは 10体 のはずが {got}"


def test_窓の外の行は数えないこと(tmp_path, monkeypatch):
    t0 = datetime(2026, 9, 9, 21, 13, tzinfo=JST)
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", _ledger(tmp_path, 10, t0))
    got = quota._subs_from_choices(t0 + timedelta(hours=1), t0 + timedelta(hours=2),
                                   model="fable")
    assert got == 2, f"窓 1時間（36分 間隔）は 2体 のはずが {got}"


def test_1体ぶんの費用は_Fable_のサブで割ること(tmp_path, monkeypatch):
    """**陽性対照つき**: 全部のサブで割ると 1体ぶんが半分に見え、切り替えが遅れる。"""
    t0 = datetime(2026, 9, 9, 21, 13, tzinfo=JST)
    t1 = t0 + timedelta(hours=6)
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", _ledger(tmp_path, 10, t0))
    monkeypatch.setattr(quota, "fable_rate", lambda now=None: {
        "source": "measured", "from_at": t0, "to_at": t1 + timedelta(hours=1),
        "from_pct": 70.0, "to_pct": 80.0, "rate": 1.0})
    got = quota.fable_cost_per_sub()
    assert got is not None, "measured の区間が在るのに測れないと言っている"
    assert abs(got - 1.0) < 1e-9, f"10% ÷ Fable 10体 ＝ 1.0%/体 のはずが {got}"
    # 陽性対照: 模型で絞らずに数えると 20体 ＝ 0.5%/体（**半分**）になる
    loose = (80.0 - 70.0) / quota._subs_from_choices(t0, t1 + timedelta(hours=1))
    assert abs(loose - 0.5) < 1e-9, "絞らない分母が半分にならない ＝ この検査が効いていない"


def test_死んだ_runs_jsonl_では測れないこと(tmp_path, monkeypatch):
    """**これが 09/05 から起きていた形**（陽性対照 ＝ 旧の口に戻すと None）。"""
    t0 = datetime(2026, 9, 9, 21, 13, tzinfo=JST)
    t1 = t0 + timedelta(hours=6)
    monkeypatch.setattr(quota, "RUNS_LOG", tmp_path / "runs.jsonl")   # 空 ＝ 増えていない
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", _ledger(tmp_path, 10, t0))
    monkeypatch.setattr(quota, "fable_rate", lambda now=None: {
        "source": "measured", "from_at": t0, "to_at": t1 + timedelta(hours=1),
        "from_pct": 70.0, "to_pct": 80.0, "rate": 1.0})
    assert quota._births_from_runs(t0, t1) == 0, "旧台帳が空でないと、この対照は効かない"
    assert quota.fable_cost_per_sub() is not None, \
        "生きている口（model_choice）へ移したのに、まだ測れないと言っている"


def test_100パーセントを越える形では立てないこと(tmp_path, monkeypatch):
    """`role_model()` の枝が**実際に通る**こと（門の当のもの）。"""
    t0 = datetime(2026, 9, 9, 21, 13, tzinfo=JST)
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", _ledger(tmp_path, 10, t0))
    monkeypatch.setattr(quota, "fable_rate", lambda now=None: {
        "source": "measured", "from_at": t0, "to_at": t0 + timedelta(hours=7),
        "from_pct": 70.0, "to_pct": 80.0, "rate": 1.0})     # 1.0%/体
    # 99.5% ＋ 1体 1.0% ＝ 100.5% ≧ 100 → Opus
    m, why = quota.role_model("fable", "枠の門は通った", 99.5, "hourly")
    assert m == "opus", f"越える形なのに {m} を返した（{why}）"
    assert "1体ぶん" in why, "理由に 1体ぶんの数が出ていない"
    # 98.0% ＋ 1.0% ＝ 99.0% ＜ 100 → まだ Fable（**早く切り替えすぎない**）
    m2, _ = quota.role_model("fable", "枠の門は通った", 98.0, "hourly")
    assert m2 == "fable", f"まだ越えないのに {m2} へ倒した"


def test_pace_のサブの診断も生きている口から出ること():
    """印字「1周に N体」は、旧台帳では **0.16体**（1周に 1体も立っていない）でした。"""
    p = quota.pace()
    assert p and p.get("subs_per_lap") is not None, "pace が サブの診断を出していない"
    assert p["subs_per_lap"] >= 1.0, \
        (f"1周に {p['subs_per_lap']:.2f}体 ＝ 死んだ台帳を読んでいる"
         f"（親は 1周に {len(quota.sub_roles())}体 立てる）")
