"""`levers._pairs()` / `reconcile()` —— **軌跡が出ない回でも、宣言と実際を突き合わせる。**

## なぜ要るか（2026-09-05 05:xx JST・最適化の回に実物で数えた）

`reconcile()` は「`--moves` で先に言った日数」と「実際に動いた日数」を並べる、
**この repo で唯一の突き合わせ**です。オーナー指示（原文3回目）——

> 「20万達成までのプランを作って達成日時を予測して、
>   **毎回達成日時を早めることを考えてから進める**ようにして」

「考えてから進めた」は外から見えないので、**先に言って、後で突き合わせる**しかない。
その突き合わせが**沈黙していました**。

`_pairs()` は「実際」を `eta_target`（その回に出ていた予測日）の差から作ります。
ところが **`target_date` は 2026-08-20 を最後に1度も出ていません**（15日）。
実測 `data/runs.jsonl`: **ship 242件 のうち `eta_target` を持つのは 0件**。
＝ `act` は全件 None、合計は `hits == 0` で落ち、行も全部
「実際 —（次の ship がまだ）」。**`tests/test_levers_window.py::
test_report_は7日の合計を渡す` はその間ずっと赤**でした
（**赤いまま置かれた検査は、消えた機能と同じです**）。

`run_marker.py` は同じ行に **`gate1p_days`（門1'・登録者500人まで）** と
**`moves_measured`（前の ship からの差）** を既に積んでいます。
**在るのに読んでいませんでした。**

直したあとの実測（`levers.report(data/runs.jsonl)`）::

    → **直近 7日・242件**の 宣言の合計 **-160日** ／ **実際の合計 +0日**
      （51件・**物差しは 門1'**（軌跡が出ない回））

**51件 が合わせて -160日 を宣言し、記録している唯一の物差しには 1つも出ていない。**

## ここで固定するもの

1. 軌跡が出ない回は **門1'（`moves_measured`）**で測る
2. **物差しを混ぜない** —— 行にも合計にも物差しの名前が付き、合計は物差しごと
3. `moves_measured` は「**すぐ前の ship** からの差」なので、
   **飛ばさずに `chrono[i+1]` だけ**を見る（間に ship を挟むと、その回のぶんまで付く）
4. 門1' の側の警告は「遠のいた」と**言わない** ——
   段の高さ 約36日 の階段なので、言えるのは「この物差しには現れていない」だけ
5. 階段の断りに `[!]` を付けない（`eta.flagged()` の尾が断りで埋まる）

## 覆る条件

軌跡が日付を出すようになったら `eta_target` の側が先に通り、ここは自分で黙ります。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import levers  # noqa: E402


def _rows_of(lines: list[str]) -> list[str]:
    """**明細の行だけ**（見出しにも「宣言」の字が入るので、字で拾わないこと）。"""
    return [ln for ln in lines if ln.startswith("    2026-") or ln.startswith("    09-")]


def _ship(i: int, moves: int, *, measured=None, target=None, basis="軌跡") -> dict:
    r = {"at": f"2026-09-0{1 + i // 10}T0{i % 10}:00:00+09:00",
         "kind": "ship", "ship_kind": "fix", "lever": "per_video", "moves": moves}
    if measured is not None:
        r["moves_measured"] = measured
    if target is not None:
        r["eta_target"] = target
        r["eta_basis"] = basis
    return r


def test_軌跡が無い回は門1の物差しで実際が出る():
    # 新しい順（`reconcile` は `reversed` して古い順にします）
    rows = [_ship(2, 0, measured=0.0), _ship(1, -3, measured=0.0), _ship(0, -5)]
    lines = "\n".join(levers.reconcile(rows))
    assert "実際 —（次の ship がまだ）" not in lines.split("\n")[3], lines
    assert "門1'" in lines, "門1' の物差しで測っていない"
    assert "宣言の合計" in lines, "合計の行が出ていない"


def test_物差しの名前が行にも合計にも付く():
    rows = [_ship(2, 0, measured=0.0), _ship(1, -3, measured=0.0), _ship(0, -5)]
    lines = levers.reconcile(rows)
    body = _rows_of(lines)
    assert any("（門1'）" in ln for ln in body), (
        "行に物差しが書いていない。書かないと軌跡の日数と足される")
    total = [ln for ln in lines if "宣言の合計" in ln]
    assert total and "門1'" in total[0], total


def test_門1の側は遠のいたと言わない():
    """**段の高さ 約36日 の階段では「遠のいた」と言えません。**"""
    rows = [_ship(2, 0, measured=0.0), _ship(1, -30, measured=0.0), _ship(0, -30)]
    lines = "\n".join(levers.reconcile(rows))
    assert "遠のいています" not in lines, lines
    assert "この物差しには1つも現れていません" in lines


def test_階段の断りに感嘆符を付けない():
    """`eta.flagged()` は `[!]` の行だけを尾へ運びます。**毎周 必ず出る断りに
    付けると、尾が断りで埋まって本当の警告が押し出されます。**"""
    rows = [_ship(2, 0, measured=0.0), _ship(1, -3, measured=0.0), _ship(0, -5)]
    step = [ln for ln in levers.reconcile(rows) if "この物差しは階段です" in ln]
    assert step, "階段の断りが出ていない"
    assert "[!]" not in step[0], step[0]


def test_軌跡が出ている回は今までどおり軌跡で測る():
    rows = [_ship(2, 0, measured=0.0, target="2027-01-10"),
            _ship(1, -3, measured=0.0, target="2027-01-05"),
            _ship(0, -5, measured=0.0, target="2027-01-01")]
    lines = levers.reconcile(rows)
    body = _rows_of(lines)
    assert not any("（門1'）" in ln for ln in body), (
        "軌跡が出ているのに門1' へ落ちている")


def test_moves_measured_はすぐ前の_ship_の分だけを使う():
    """**飛ばさないこと。** 間に `moves_measured` の無い ship を挟んだら、
    その回のぶんまでこの行に付きます。"""
    rows = [_ship(2, 0, measured=-40.0), _ship(1, 0), _ship(0, -5)]
    lines = levers.reconcile(rows)
    first = _rows_of(lines)[0]
    assert "実際 —" in first, (
        f"すぐ前ではない ship の `moves_measured` を拾っている: {first}")
