"""**間隔の下限を、定数ではなくオーナーの画面の%から出す**ことを固定する検査（2026-08-30）。

## なぜ入れたか

`scripts/next_round.py` の `floor_minutes()` は、`quota.py` が
「誕生から誕生」を数えられない回に **`FALLBACK_MIN`（90分）の定数**へ落ちていました。
**定数は、速すぎるか遅すぎるかを言いません。**

2026-08-30 15:40 JST にオーナーが送った画面で、それが実害として出ました:

    週 42% 使用済み（枠 08/29 07:00 → 09/05 07:00 JST）
      いまの速さ    1.286 %/時
      許される速さ  0.428 %/時（残り 58% ÷ 残り 135時間）
    このままなら 100% は 09/01 12:46 JST → **リセットまで 90時間、鎖が止まる**

**止まるのはこのループだけではありません。オーナー自身も使えなくなります。**
`quota.jsonl` は薄く（実測 `births=0`）、`floor_min` は `None` を返していたので、
**その90時間へ向かって 90分間隔のまま走り続ける形**でした。

**画面の%からは、比なら出せます。** 1周の重さが変わらないなら、
間隔を「いまの速さ ÷ 許される速さ」の分だけ伸ばせば釣り合います。

## 覆る条件（この検査が落ちてよくなる条件）

- `quota.jsonl` が誕生を数えられるようになったら、`recommended_floor_minutes()` が
  先に値を返すので、この道は**呼ばれません**。そちらが正です
- 新しい画面で「いまの速さ ≦ 許される速さ」になったら、比が1以下になり
  **自分で `FALLBACK_MIN` に戻ります**（手で戻す必要はありません）
- 1周の重さを大きく変えたら、比の前提が変わるので測り直すこと
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "next_round_gauge", ROOT / "scripts" / "next_round.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


nr = _load()


def _pace(rate, fwd):
    return {"rate": rate, "forward_rate": fwd}


def _patch(monkeypatch, *, floor, pace):
    import sys
    import types
    fake = types.ModuleType("scripts.quota")
    fake.recommended_floor_minutes = lambda: floor
    fake.pace = lambda *a, **k: pace
    pkg = sys.modules.get("scripts") or types.ModuleType("scripts")
    pkg.quota = fake
    monkeypatch.setitem(sys.modules, "scripts", pkg)
    monkeypatch.setitem(sys.modules, "scripts.quota", fake)


def test_誕生が数えられる回はそちらが勝つ(monkeypatch):
    """**`floor_min` が出ているなら、画面の比は使いません。**"""
    _patch(monkeypatch, floor=41.0, pace=_pace(9.9, 0.1))
    got, why = nr.floor_minutes()
    assert got == 41.0
    assert "実測" in why


def test_速すぎる回は比のぶんだけ間隔が伸びる(monkeypatch):
    """08/30 の実物: 1.286 ÷ 0.428 = ×3.0 → 90分 が 270分 になる。"""
    _patch(monkeypatch, floor=None, pace=_pace(1.2857142857142858, 0.4283302072178486))
    got, why = nr.floor_minutes()
    assert 265.0 <= got <= 275.0, got
    assert "比" in why


def test_内側に入ったら自分で戻る(monkeypatch):
    """**手で戻さないこと。** 速さが許される線の内側なら定数に戻ります。"""
    _patch(monkeypatch, floor=None, pace=_pace(0.30, 0.43))
    got, why = nr.floor_minutes()
    assert got == nr.FALLBACK_MIN
    assert "内側" in why


def test_伸ばしすぎない(monkeypatch):
    """**上限6時間。** これを超えると、画面のほうが先に腐ります。"""
    _patch(monkeypatch, floor=None, pace=_pace(50.0, 0.4))
    got, _ = nr.floor_minutes()
    assert got == nr.GAUGE_FLOOR_CAP == 360.0


def test_目盛りが無い回は止めない(monkeypatch):
    """**測れないことを理由に鎖を止めないこと**（`quota.py` の docstring と同じ理由）。"""
    _patch(monkeypatch, floor=None, pace=None)
    got, _ = nr.floor_minutes()
    assert got == nr.FALLBACK_MIN
