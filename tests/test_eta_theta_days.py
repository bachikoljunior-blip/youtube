"""`headline()` —— **θ（前提が閉じる速さ）に、日数の値札が付いているか。**

## なぜ要るか（2026-08-30・最適化の回に測った）

`scripts/eta.py` の出力は、日数の値札を**腕**と**配分**にだけ付けていました ——
「次の1件をどの腕に立てるか」で数日、「台帳の配分」で +10日。
θ は 200行目 あたりに**値だけ**（「1日 0.77件 が閉じている」）出ていて、
**それが到達日を何日 動かすかは、どこにも書いてありませんでした。**

同じ日に `rate_scale` を振って解き直した実測（`data/eta.jsonl` の最後の点）::

    θ×0.5   2027-02-25   t_work 85日   **+46日**
    θ×1.0   2027-01-10   t_work 47日     ——（印字している線）
    θ×2.0   2026-12-17   t_work 24日   **-24日**
    θ→∞     2026-11-24   t_work  1日   **-47日**

**-47日 は、この機械が1周で選べるどの手より大きい数です**（同じ回の
「台帳の配分との差」は +10日、「次の1件をどの腕に立てるか」は 3日）。
値札が無いと、大きいほうが小さいほうに負けます —— 実測 `data/runs.jsonl`
直近 500回: `fix` 203件 ／ `upload` 45件 に対し **`verdict` 6件**、
そのあいだ到達予測は **+22日 遠のいて** います（12-19 → 01-10）。

## ここで固定するもの

1. **θ の行が出ること**（値だけでなく、**日数**と**日付**が両方 出る）
2. **上げ方を同じ行で名指しすること** —— 在庫（開いた前提）が余っている回は
   「前提を増やすこと」ではないと言い、`queue_lag.py` を名指しする。
   名前の無い所は「やれること」で埋まります
   （`tests/test_eta_covered_substitute.py` が一度 直した形）
3. **`t_work == 0` の回は、黙って消えないこと** —— 消えたのが
   「解けなかった」なのか「効かない」なのか、読む側から区別が付きません
4. **`--reflect`（`full=False`）は θ を解かないこと** ——
   `_row()` は `theta` を1つも読まないので、解くと 8秒 の道が重くなるだけです
   （`trajectory_all()` の `full` の註と同じ理由）

## 覆る条件

`t_work` が恒常的に 0日 になったら（＝いつ撃っても「いま走らせるのが最短」）、
1 の行は 3 の形に落ちます。**そのときはこの検査ごと畳んでよい** ——
θ が到達日を動かさない世界では、値札に意味がありません。
"""
from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "eta_theta_days_mod", ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eta)


def _traj(days: float, d: date, t_work: int = 47) -> dict:
    return {"days": days, "date": d, "t_work": t_work, "plan_days": days - t_work,
            "blocking": [], "factors": {}, "binding": "収益化の門＋その後の30日"}


def _tr(theta: dict | None, alloc_days: float | None = 142.2) -> dict:
    base = _traj(132.2, date(2027, 1, 10))
    tr = {"base": base, "fast": None, "slow": None, "theta": theta,
          "planned": (None if alloc_days is None
                      else _traj(alloc_days, date(2027, 1, 20)))}
    return tr


def _theta(**kw) -> dict:
    """**2026-08-30 の実測をそのまま写した `theta`。**"""
    th = {"per_day": 0.7692, "n": 20, "days": 26.0, "t_work": 47, "open": 28,
          "x2": _traj(108.7, date(2026, 12, 17), 24),
          "inf": _traj(85.7, date(2026, 11, 24), 1),
          # **実測をそのまま**（2026-08-30 の点）。`.5` ちょうどに丸めないこと ——
          # `format` は偶数丸めなので `-46.5` は **-46** と出て、
          # 「実測は -47 なのに検査は -46」というずれが固定されます。
          "x2_delta": -23.52, "inf_delta": -46.52}
    th.update(kw)
    return th


def test_θの行に日付と日数が両方出る():
    out = "\n".join(eta._theta_line(_tr(_theta()), _tr(_theta())["base"]))
    assert "θ" in out
    assert "0.77件/日" in out, "θ の値そのものが出ていない"
    assert "2026-12-17" in out and "2026-11-24" in out, "日付が出ていない"
    # **日数が要ります。** 日付だけだと、他の手（配分 +10日・腕 3日）と
    # 同じ物差しに乗りません。
    assert "-24日" in out and "-47日" in out


def test_上げ方を2つとも同じ行で名指しする():
    """**名前の無い所は「やれること」で埋まります**（`test_eta_covered_substitute` の形）。

    θ を上げる手は2つ（件数／立ててから判定できるまでの日数）で、
    **どちらが縛っているかは、この機械からは読めません** ——
    前提が「いつ立ったか」の欄が台帳に無いからです。
    **読めないことを、読めたふりで片方に倒さないこと。**
    """
    out = "\n".join(eta._theta_line(_tr(_theta()), _tr(_theta())["base"]))
    assert "28件" in out
    assert "eta.py --alloc" in out, "(1) 件数の道具の名前が無い"
    assert "queue_lag.py" in out, "(2) 待ち時間を縮める道具の名前が無い"
    # **在庫の写真であることを、同じ行で言うこと。**
    assert "補充の速さを見ていません" in out


def test_配分との差と並べる():
    out = "\n".join(eta._theta_line(_tr(_theta()), _tr(_theta())["base"]))
    # **単独の「-47日」は大きく見えるだけ**で、この回に選べる他の手より
    # 大きいかを言っていません。同じ行に並べること。
    assert "台帳の配分との差" in out
    assert "倍" in out


def test_配分のほうが大きい回は_最上級を名乗らない():
    """**無条件の最上級を書かないこと。**

    `t_work` が縮んだ回は θ の天井が配分の差より小さくなり得ます。
    **比べてから、比べた結果を名乗ること** —— 無条件の最上級は、
    次に読む側が確かめずに済む形です（この repo が何度も踏んでいる形）。
    """
    tr = _tr(_theta(inf_delta=-4.0, x2_delta=-2.0), alloc_days=232.2)  # 配分は +100日
    out = "\n".join(eta._theta_line(tr, tr["base"]))
    assert "いちばん大きく動かすのは" not in out
    assert "この回は配分のほうが大きい" in out


def test_在庫が要る件数に足りるかを言う():
    """**軌跡が要る閉件数（θ × t_work）と、台帳の在庫を、同じ行で比べること。**

    実測 2026-08-30: 0.77件/日 × 47日 ＝ **36件** 要るのに、開いているのは
    **28件**。**この比較がどこにもありませんでした** —— 軌跡は
    「台帳に無い前提が閉じつづける未来」を歩いていて、そのことが
    印字されていない。
    """
    out = "\n".join(eta._theta_line(_tr(_theta()), _tr(_theta())["base"]))
    assert "36件" in out, "要る閉件数（θ × t_work）が出ていない"
    assert "足りない" in out
    # 在庫のほうが多い回は、そう言うこと（黙って同じ文を出さない）。
    tr = _tr(_theta(open=99))
    assert "足りる" in "\n".join(eta._theta_line(tr, tr["base"]))


def test_t_workが0の回は黙って消えない():
    out = "\n".join(eta._theta_line(_tr(_theta(t_work=0)), _tr(_theta())["base"]))
    assert out, "行ごと消えている（効かないのか解けなかったのか読めない）"
    assert "動かしません" in out
    assert "いま走らせるのが最短" in out


def test_解けなかった回は消える():
    assert eta._theta_line(_tr(None), _tr(None)["base"]) == []
    assert eta._theta_line(None, None) == []


def test_reflectはθを解かない():
    """`full=False` の道に `theta` を持ち込まないこと（8秒 の道が重くなる）。"""
    src = (ROOT / "scripts" / "eta.py").read_text(encoding="utf-8")
    assert '"theta": _theta_days(m, a0, base, rows, kw) if full else None' in src, (
        "`full` の門が外れている ——`--reflect` が印字しない線を解きはじめます")


def test_開いた前提の件数が台帳から読めている():
    """`_open_hypotheses()` が実物の `config/hypotheses.yaml` を読めること。

    **`None` を返しはじめたら、上げ方の名指しが黙って消えます**
    （`_theta_line` は `n_open` が偽なら、その節を丸ごと落とすので）。
    """
    n = eta._open_hypotheses()
    assert n is not None, "台帳が読めていない"
    assert n > 0
