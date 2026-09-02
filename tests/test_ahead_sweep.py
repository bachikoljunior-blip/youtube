"""**回が何もしなくても、先の日付の予約が掃かれること。**

## なぜ門だけでは足りないか（2026-09-02・オーナー原文）

> **「1日一本になってないんだけど、今後こういうことが一切ないようにしろ」**

門（`scripts/stop_check.sh` (1.45)）は「その回が終わろうとしたとき」に効きます。
ところが **09/01 07:0x に再起動で 39分ぶんが消え、11:5x には3つ まとめて
殺されています** —— **終わらなかった回に、終わりの門は当たりません。**

`scripts/ahead_sweep.py` は、`SessionStart` フックから**背景で**起きて、
回が何も選ばなくても掃きます。**この検査が見るのは「撃たない条件」のほう**です
—— 撃つ側は `pool_drain` / `ahead_gate` の検査が持っています。

**撃たない条件を、回の裁量にしないこと。** 裁量にした2日で、
459本 → 107本 にしかなりませんでした。

## 覆る条件

- `house_rule.same_day_only()` が `False` になったら、掃きはまるごと黙ります
- `.owner-pause`（**人だけが置ける印**）が在る間も黙ります。
  **機械がその印を作らないこと**（`tests/test_pause_needs_owner.py`）
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

_gspec = importlib.util.spec_from_file_location(
    "ahead_gate_for_sweep", ROOT / "scripts" / "ahead_gate.py")
ahead_gate = importlib.util.module_from_spec(_gspec)
sys.modules["ahead_gate"] = ahead_gate          # `ahead_sweep` が import する名前
_gspec.loader.exec_module(ahead_gate)

_sspec = importlib.util.spec_from_file_location(
    "ahead_sweep_mod", ROOT / "scripts" / "ahead_sweep.py")
ahead_sweep = importlib.util.module_from_spec(_sspec)
_sspec.loader.exec_module(ahead_sweep)

NOW = datetime(2026, 9, 2, 5, 0, tzinfo=timezone.utc)


def _verdict(ahead: int, quota_open: bool, seen: dict | None) -> dict:
    return {"block": ahead > 0, "why": "", "lines": [], "ahead": ahead,
            "quota_open": quota_open, "seen": seen}


@pytest.fixture()
def 砂場(monkeypatch, tmp_path):
    monkeypatch.setattr(ahead_sweep, "_lock_path", lambda: tmp_path / "sweep.lock")
    monkeypatch.setattr(ahead_sweep, "_paused", lambda: "")
    return tmp_path


# ---------------------------------------------------------------- 撃つ／撃たない
def test_先の日付に在れば掃く(砂場, monkeypatch):
    monkeypatch.setattr(ahead_gate, "verdict",
                        lambda now=None, rows=None: _verdict(107, True, None))
    assert ahead_sweep.reasons_to_skip(NOW) == ""


def test_日枠が尽きていれば掃かない(砂場, monkeypatch):
    """**撃てないものを撃ちに行かないこと。** 403 を買うだけで、外れません。"""
    monkeypatch.setattr(ahead_gate, "verdict",
                        lambda now=None, rows=None: _verdict(107, False, None))
    assert "日枠" in ahead_sweep.reasons_to_skip(NOW)


def test_0本で実物も見ていれば掃かない(砂場, monkeypatch):
    monkeypatch.setattr(ahead_gate, "verdict",
                        lambda now=None, rows=None: _verdict(0, True, {"count": 0}))
    assert "0本" in ahead_sweep.reasons_to_skip(NOW)


def test_控えが0本でも実物を見ていなければ掃く(砂場, monkeypatch):
    """**2026-09-01 16:33 の形**（控え 0本／Studio に4本）。読みは安いので見に行く。"""
    monkeypatch.setattr(ahead_gate, "verdict",
                        lambda now=None, rows=None: _verdict(0, True, None))
    assert ahead_sweep.reasons_to_skip(NOW) == ""


def test_一時停止の印が在れば掃かない(砂場, monkeypatch):
    monkeypatch.setattr(ahead_sweep, "_paused", lambda: "/repo/.owner-pause")
    monkeypatch.setattr(ahead_gate, "verdict",
                        lambda now=None, rows=None: _verdict(107, True, None))
    assert "一時停止" in ahead_sweep.reasons_to_skip(NOW)


def test_規則5_が外れたら掃かない(砂場, monkeypatch):
    monkeypatch.setattr(ahead_sweep.house_rule, "same_day_only", lambda: False)
    monkeypatch.setattr(ahead_gate, "verdict",
                        lambda now=None, rows=None: _verdict(107, True, None))
    assert "規則5" in ahead_sweep.reasons_to_skip(NOW)


# ---------------------------------------------------------------- ロック
def test_二重には走らない(砂場):
    assert ahead_sweep.take_lock(NOW) is True
    assert ahead_sweep.take_lock(NOW + timedelta(minutes=1)) is False


def test_死んだ印は奪う(砂場):
    """**奪わないと、一度 落ちた回のあと二度と掃けません。**

    この輪はコンテナごと消える回があります（09/01 07:0x・11:5x）。
    **必ず起きる形なので、検査に入れてあります。**
    """
    assert ahead_sweep.take_lock(NOW) is True
    later = NOW + ahead_sweep.STALE + timedelta(minutes=1)
    assert ahead_sweep.take_lock(later) is True


def test_印を落とせば次が取れる(砂場):
    assert ahead_sweep.take_lock(NOW) is True
    ahead_sweep.drop_lock()
    assert ahead_sweep.take_lock(NOW) is True


# ---------------------------------------------------------------- 配線
def test_SessionStart_に配線されていること():
    """**外したら、ここで分かること。** 消すと「その回が選べば撃つ」形に戻ります。"""
    cfg = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    cmds = [h.get("command") for group in cfg["hooks"]["SessionStart"]
            for h in group["hooks"]]
    assert "bash scripts/ahead_sweep.sh" in cmds


def test_起こす側は背景で走ること():
    """前で待つと、フックの制限時間で**毎回 途中で死にます**（107本 ＝ 数分）。"""
    text = (ROOT / "scripts" / "ahead_sweep.sh").read_text(encoding="utf-8")
    assert "nohup" in text and "&" in text
    assert "YOUTUBE_PIPELINE_CHILD" in text, "台本生成の子プロセスで撃たないこと"


def test_掃く順番が固定されていること():
    """オーナーがこの順で名指ししています。**実物を先に引くこと。**"""
    text = (ROOT / "scripts" / "ahead_sweep.py").read_text(encoding="utf-8")
    live = text.index('"scripts/ahead_gate.py", "--live"')
    truth = text.index('"-m", "src.ledger_truth"')
    drain = text.index('"scripts/pool_drain.py", "--apply", "--keep", "0"')
    assert live < truth < drain


# ---------------------------------------------------------------- その日のぶん
def test_窓が空なら_107本ぶん以上_掃ける(monkeypatch):
    """**掃きが1回では終わらない形にしないこと。** いまの残り 107本 は1窓で入ります。"""
    from src import quota_ledger
    monkeypatch.setattr(quota_ledger, "spent", lambda now=None: {"data": 0})
    assert ahead_sweep.budget_max() >= 107


def test_その日の1本のぶんを残す(monkeypatch):
    """**この掃きは回の意思と関係なく走ります。手加減する人がいません。**

    実測 2026-09-01 16:0x: `pool_drain --apply` が 160本 で
    **12,258 / 10,000単位** を焼き、次の枠の本が「焼いたあとに入った 6件」を
    1つも入れずに出ました（`pool_drain.SWAP_UNITS` の註）。
    """
    from src import quota_ledger
    cap = quota_ledger.DAY_UNITS
    monkeypatch.setattr(quota_ledger, "spent",
                        lambda now=None: {"data": cap - ahead_sweep.RESERVE_UNITS})
    assert ahead_sweep.budget_max() == 1


def test_帳面が読めない回は上限を置かない(monkeypatch):
    """**推測で締切を遅らせないこと**（`pool_drain._trim_for_swap` と同じ）。"""
    from src import quota_ledger

    def boom(now=None):
        raise OSError("帳面が読めない")

    monkeypatch.setattr(quota_ledger, "spent", boom)
    assert ahead_sweep.budget_max() == 0


def test_上限は_pool_drain_の_max_へ渡ること():
    """**渡していなければ、取り置きは効きません。**"""
    text = (ROOT / "scripts" / "ahead_sweep.py").read_text(encoding="utf-8")
    assert '"--max", str(cap)' in text
