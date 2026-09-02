"""**毎周いちばん最初に撃つ道具を、落とさないこと。**

## 実物（2026-09-02・最適化の回。**撃って落ちた**）

    TypeError: unsupported format string passed to NoneType.__format__
      scripts/eta.py:8309 in headline
        f"{bar}   → [!] **その天井 ×{_need:.2f} を、{_f2}の中に探さないこと ——"

落ちたのは `_need` ではありません（実測 21.61）。**`_esc['over']` が `None`** で、
それを刷る行が同じ f-string の中（`f" **×{_esc['over']:.2f}** です"`）に居ました ——
`out.append(...)` の引数が 20行 以上の連結なので、traceback は**先頭の行**を指します。

そのときの実測:

    _esc = {'form': 'ショート', 'cap': 0.0, 'top': 1891.0, 'over': None, 'escapes': False}

`_escape_form()` は**正しく守っています** —— `settled`（伸びきったと言える形）が
1つも無い回は `cap = 0.0` になり、`"over": (top / cap) if cap else None`。
**守っていなかったのは刷る側**で、`_esc["form"]` が真かどうかしか見ていませんでした。

## なぜ「落ちてもいい道具」ではないか

`scripts/eta.py` は **§4（この回で何をやるか）を決める前**に撃つ道具です
（`docs/trigger_main.md` §2.6）。落ちると、その回は**到達日も、引く腕も見ないまま**
§4 を選びます。**この repo でいちばん高い1つの計器**が、黙って消える形でした。

## 黙って行を消さないこと

`over` が無い回にこの段ごと落とすと、次の回は「**逃げ先は無い**」と読みます。
本当は「**まだ比べられない**」だけです。だから代わりに、そう言う1行を刷ります。

## 覆る条件

`settle` がどれか1つの形を「伸びきった」と言えるようになったら `cap` が正になり、
この枝は自分で消えます。**定数は持ちません。**
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location("eta_for_escape", ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eta)

#: **実物**（2026-09-02 に落ちたときの `_escape_form()` の返り）。
UNMEASURED = {"form": "ショート", "cap": 0.0, "top": 1891.0,
              "over": None, "escapes": False}
MEASURED = {"form": "長尺", "cap": 1891.0, "top": 312.0,
            "over": 312.0 / 1891.0, "escapes": False}


def _pl() -> dict:
    return {"days_to_target": 124.0, "target_date": date(2026, 12, 28),
            "lever_hint": "per_video", "lever_from": "床",
            "lever_need": 98.17, "lever_need_over_cap": 21.61,
            "binding": "再生数が天井に当たっている", "lever_days": []}


def _tr() -> dict:
    arms = {"per_video": {"share": 0.6, "focus_rate": 0.1, "rate": 0.06, "cap": 3.0,
                          "throughput": 0.95, "n": 12, "p": 0.17, "source": "自前"}}
    return {"arms": arms, "choice": [], "planned": None,
            "base": {"days": 124.0, "date": date(2026, 12, 28),
                     "t_work": 50, "plan_days": 73.0, "blocking": []}}


def _lines(esc: dict, monkeypatch) -> str:
    monkeypatch.setattr(eta, "_escape_form", lambda *a, **k: esc)
    monkeypatch.setattr(eta.arm_speed, "next_close",
                        lambda *a, **k: {"on": date(2026, 8, 27), "days": 1,
                                         "open": 16, "source": "ready"})
    monkeypatch.setattr(eta, "_ready_by_claim", lambda *a, **k: {})
    return "\n".join(eta.headline(_pl(), tr=_tr()))


def test_cap_が測れていない回に落ちないこと(monkeypatch):
    """**発火。** これが 2026-09-02 に `main()` ごと落とした形そのもの。"""
    out = _lines(UNMEASURED, monkeypatch)      # 例外が出たらここで落ちます
    assert out, "1行も出ていません"


def test_落とす代わりに_まだ比べられないと言うこと(monkeypatch):
    """**黙って消さないこと** —— 消すと「逃げ先が無い」と読まれます。"""
    out = _lines(UNMEASURED, monkeypatch)
    assert "比べられません" in out, f"何も言わずに段を落としています: {out[:400]}"
    assert "「逃げ先が無い」ではありません" in out


def test_測れている回は_これまでどおり刷ること(monkeypatch):
    """**常に「比べられません」と言う実装を落とすため。**"""
    out = _lines(MEASURED, monkeypatch)
    assert "比べられません" not in out
    assert "長尺" in out


def test_escape_form_は_cap_が_0_なら_over_を_None_にする():
    """**守っているのは `_escape_form()` のほう**（そこを緩めて直さないこと）。"""
    got = eta._escape_form({})
    assert set(got) >= {"form", "cap", "top", "over", "escapes"}
    if not got.get("cap"):
        assert got.get("over") is None, \
            "`cap` が 0 なのに `over` が数です（0除算を隠しています）"
        assert got.get("escapes") is False
