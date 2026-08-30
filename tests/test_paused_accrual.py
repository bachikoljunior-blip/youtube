"""**停止中は、`kind: accrual` の伸び率も 0 になる。**（`_ans_accrual` の側）

## この検査が守っているもの（2026-08-30・最適化の回に実測して足した）

`tests/test_paused_supply.py` は、同じ穴を **`_project_nth()` の側**（`group_key`）
だけで塞ぎました。**`_ans_accrual` は素通りでした。** あちらもこちらも
「**いまの伸び率が続いたら**」で日を出しますが、`count_expr` が
`data/batch_runs.jsonl`（＝ **作った本**の台帳）を数えているとき、
その伸び率を作っているのは**本を作る速さ**で、`src/pause_guard` はそれを 0 にしています。

**実測（この検査を足した回・`slot_half`／腕 `density`）**::

    count_expr が数える 作った本   **7本**
    そのうち 既に公開済み          **0本**
    齢4日以上（`falsified_if` が要る「落ち着き」）  **0本**
    予約に入ったまま未公開         **7本**

    → `since` からの平均で「**2日で 3.50/日 → あと 8日**」
    → `deadline_check --shrink` が **2026-11-10 → 2026-09-08（63日）** 縮めろと出す

**その 3.50/日 は、停止が入る前の 2日ぶん**です。停止後は 0 なので 32本 には
永久に届きません。それでも機械は日付を出し、`src/arm_speed.forward()` の θ に
**閉じる見込みとして数えられます。**

## **同じ回に `--fit` を主実行へ配線しています**（`docs/trigger_main.md` §2.6）

`docs/JOURNAL.md` 2026-08-26 が `--shrink` について残した1行:

> **判断を抜くと、入力の質がそのまま結果になります。**
> 印字だけの頃は誰も従わなかったので、悪い入力は無害でした。
> **従わせる仕組みを入れた瞬間、入力の誤りが「機械が実行した誤り」に変わります。**

**配線だけを入れると、速くなるのは間違いのほうです。** だから同じ回に、
その入力を止める門（`_ledger_frozen`）を置きました。**片方だけ入れないこと。**

## 固定するのは4つ

1. 停止中、**作った本の台帳で数えている `accrual`** は日付を出さない（`unreachable`）
2. その `Answer` は**あと何本 要るか**を持つ（`paused_short` ＝ 解除の値段）
3. **式が何を数えているかは、式に聞くこと** —— 台帳のいちばん新しい行では
   ありません。停止の 52分 後に `long: True` の回が1件 積まれており
   （停止を merge していない作業コピーから走った回）、
   **`slot_half` の式は `not r.get('long')` でそれを外します。**
   台帳全体で見ると「伸びている」に化け、**この門は素通りしました**（実測してここへ落ちた）
4. **平時は何もしない**（`is_paused()` が False なら、今までどおり推定の日付が出る）

## 覆る条件

- `AUTOMATION_PAUSED.md` が消えたら 1・2 は自分で黙ります
- **停止のあとにも台帳が伸びていたら黙ります** —— 「止まっているはず」ではなく
  「実際に増えたか」で見ているからです。これは弱めではなく、**実測を文書より
  強く採る**ということです
- git が読めない木では `_pause_started()` が `None` を返し、門は **False**
  （＝ 何も言わない）へ倒れます。**黙るほうへ倒すこと** —— 誤って True に倒れると、
  動いている前提まで `arm_speed` から消えます
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load(name: str, path: Path):
    import sys

    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


D = _load("paused_accrual_deadline_check", ROOT / "scripts" / "deadline_check.py")

#: 台帳を数える式（`config/hypotheses.yaml` の `slot_half` と同じ形）。
LEDGER_EXPR = ("len({x['topic'] for r in rows('batch_runs.jsonl') "
               "if str(r.get('at', '')) >= '2026-08-01' and not r.get('long') "
               "for x in r.get('results', []) or [] if x.get('video_id')})")

PAUSE_AT = "2026-08-30T08:54:08+09:00"


def _row(at: str, topic: str, *, long: bool = False) -> dict:
    return {"at": at, "long": long,
            "results": [{"topic": topic, "video_id": "v-" + topic}]}


def _wire(monkeypatch, rows: list[dict], *, paused: bool = True,
          started: str | None = PAUSE_AT) -> None:
    import src.pause_guard as PG

    monkeypatch.setattr(PG, "is_paused", lambda: paused)
    monkeypatch.setattr(D, "_pause_started", lambda: started)
    monkeypatch.setattr(D, "_rows",
                        lambda name: list(rows) if name == "batch_runs.jsonl" else [])
    ns = dict(D.EXPR_NS)
    ns["rows"] = lambda name: list(rows) if name == "batch_runs.jsonl" else []
    monkeypatch.setattr(D, "EXPR_NS", ns)


# --- 1・2: 停止のあと1件も増えていない台帳は、日付を出さない -------------------

def test_停止後に伸びていない台帳は判定日を出さない(monkeypatch):
    """**全部 停止より前に作った本。** 伸び率を未来へ延ばしてはいけない。"""
    _wire(monkeypatch, [_row("2026-08-30T08:40:51+09:00", "a"),
                        _row("2026-08-30T08:51:58+09:00", "b")])
    assert D._ledger_frozen(LEDGER_EXPR) is True, "停止で凍っているのに、凍っていないと言っている"


def test_凍っているときは値段つきで打ち切る(monkeypatch):
    """`_ans_accrual` が `unreachable` を返し、**あと何本**を持つこと。"""
    _wire(monkeypatch, [_row("2026-08-30T08:40:51+09:00", "a"),
                        _row("2026-08-30T08:51:58+09:00", "b")])
    ans = D._ans_accrual({"count_expr": LEDGER_EXPR, "need": 32,
                          "since": "2026-08-29"}, D.date(2026, 8, 31))
    assert ans.ready is None, "停止中なのに、判定できる日を出している"
    assert ans.unreachable is True, "`warming`（待てば来る）に見えてはいけない"
    assert ans.paused_short == 30, "あと何本 要るかを持っていない（解除の値段が言えません）"
    assert "1本も増えません" in ans.why


# --- 3: 式が外す行で「伸びている」に化けないこと（実測してここへ落ちた） --------

def test_式が外す行では黙らない(monkeypatch):
    """停止後に積まれたのが **`long: True`** だけなら、`slot_half` の式は凍ったまま。

    **台帳のいちばん新しい行で見ると、ここが素通りします。**
    実測 2026-08-30: 停止（08:54:08）の **52分 後** に `long: True` の回が1件。
    """
    rows = [_row("2026-08-30T08:51:58+09:00", "b"),
            _row("2026-08-30T09:46:32+09:00", "L", long=True)]
    _wire(monkeypatch, rows)
    assert D._ledger_frozen(LEDGER_EXPR) is True, \
        "式が外す行（long）を見て「伸びている」に化けている"


def test_式が数える行が増えていれば黙る(monkeypatch):
    """**実測を文書より強く採る。** 停止後にも作れているなら、何も言わない。"""
    rows = [_row("2026-08-30T08:51:58+09:00", "b"),
            _row("2026-08-30T09:46:32+09:00", "c")]
    _wire(monkeypatch, rows)
    assert D._ledger_frozen(LEDGER_EXPR) is False, \
        "停止後にも台帳が伸びているのに、凍っていると言っている"


# --- 4: 平時と、判断できないときは黙る ---------------------------------------

def test_平時は何もしない(monkeypatch):
    _wire(monkeypatch, [_row("2026-08-30T08:51:58+09:00", "b")], paused=False)
    assert D._ledger_frozen(LEDGER_EXPR) is False


def test_停止の時刻が読めなければ黙る(monkeypatch):
    """git が読めない木では **False へ倒すこと**（動いている前提を消さない）。"""
    _wire(monkeypatch, [_row("2026-08-30T08:51:58+09:00", "b")], started=None)
    assert D._ledger_frozen(LEDGER_EXPR) is False


def test_台帳を数えていない式は素通り(monkeypatch):
    """再生の積み上げ（`latest_views`）は、予約が公開されるので**停止中も動きます**。"""
    _wire(monkeypatch, [_row("2026-08-30T08:51:58+09:00", "b")])
    assert D._ledger_frozen("sum(v for v in latest_views().values() if v < 342)") is False
