"""**長尺の中央値の上限**（`src/long_ceiling.py`）が、判定と同じ数を見ていること。

## なぜ要るか（2026-08-31）

`config/hypotheses.yaml` の `長尺1本あたり-30本` は **中央値 80回** で判定します。
`scripts/eta.py` は 8/19 から `long_median_per_video` を測って
`data/eta.jsonl` に積んでいましたが、**印字は平均のほうだけ**でした ——
実測 2026-08-31 は 平均 16回 に対し **中央値 4回（4倍）**。

そして `scripts/deadline_check.py` は毎回「要 30 ／ いま 14 → あと 3日」と出し、
**「あと3日 待てば分かる」に読めます。** 実測の分布は

    1 1 1 1 1 2 2 3 3 3 4 4 4 4 6 7 8 15 48 82 133   （21本・中央値 4）

で、**残り9本 を、このチャンネルの最良の長尺（133回）で埋めても
30本の中央値は 6.5** です。**待っても、この標本のままでは覆りません。**

## ここで固定するもの（5つ）

1. 上限が、**無限ではなく実測の最大値**で埋めた数であること
   （`inf` を入れると上限が `inf` になり「まだ分からない」に化けます）
2. 実測の分布で、上限が **門 80 の下**に出ること
3. **覆る道（窓からの入れ替わり）が数で出る**こと ——「待つ」と別物だと言えること
4. `long_values_28d` が無い点で **「測っていない」と出る**こと
   （**「0本だった」ではありません**。`data/descriptions.json` で同じ形を踏んでいます）
5. **門の数（80）と本数（30）が、仮説の本文と同じ**であること
   —— 2か所に書いてあるので、片方だけ動いたら落とします

## 覆る条件

- `falsified_if` の門が 80回 から動いたら、`MEDIAN_GATE` を合わせること
  （**この検査が落ちて教えます**）
- 判定が読む窓（28日）が変わったら、`WINDOW_DAYS` と
  `scripts/eta.py::_measure()` の `q(28, ...)` を**一緒に**動かすこと
"""
from __future__ import annotations

import json
from pathlib import Path

from src import long_ceiling as lc

ROOT = Path(__file__).resolve().parent.parent

#: 実測 2026-08-31（`long_values_28d`・直近28日・昇順）。
MEASURED = [1, 1, 1, 1, 1, 2, 2, 3, 3, 3, 4, 4, 4, 4, 6, 7, 8, 15, 48, 82, 133]


def test_中央値():
    assert lc.median([]) == 0.0
    assert lc.median([5]) == 5
    assert lc.median([1, 3]) == 2
    assert lc.median([3, 1, 2]) == 2
    assert lc.median(MEASURED) == 4


def test_上限は実測の最大値で埋める():
    """**無限で埋めないこと。** 埋めると上限が `inf` になり、判定不能に化けます。"""
    bound = lc.best_case_median(MEASURED, n_target=30)
    assert bound == 6.5, bound
    # 明示的に最大値を渡しても同じ（既定が「標本の最大値」であることの固定）
    assert lc.best_case_median(MEASURED, 30, optimistic=max(MEASURED)) == bound


def test_実測の上限は門の下に出る():
    assert lc.best_case_median(MEASURED, 30) < lc.MEDIAN_GATE


def test_標本が足りていれば上限はそのままの中央値():
    vals = list(range(31))
    assert lc.best_case_median(vals, 30) == lc.median(vals)


def test_空の標本では0を返す():
    assert lc.best_case_median([], 30) == 0.0
    assert lc.share_at_or_above([]) == 0.0


def test_門に届いた割合():
    assert lc.share_at_or_above(MEASURED) == 2 / 21
    assert lc.share_at_or_above([80, 80, 1, 1]) == 0.5


def test_覆る道は入れ替わりで_数で出る():
    """**「待つ」では覆りません。** 何本 落ちれば届きうるかを数で出すこと。"""
    need = lc.rescue_needed(MEASURED, n_target=30)
    assert need > 0, "0 なら『待てば届く』ことになり、上限の意味が消えます"
    kept = sorted(MEASURED)[need:]
    assert lc.best_case_median(kept, 30, optimistic=lc.MEDIAN_GATE) >= lc.MEDIAN_GATE
    # **1本 少ないと届かない**（最小であることの固定）
    kept_少ない = sorted(MEASURED)[need - 1:]
    assert lc.best_case_median(kept_少ない, 30, optimistic=lc.MEDIAN_GATE) < lc.MEDIAN_GATE


def test_落とせば必ず届く標本では0を返す():
    assert lc.rescue_needed([90, 91, 92], n_target=4) == 0


def test_分布が無い点は測っていないと出る():
    """**「0本だった」と読ませないこと。**"""
    out = "\n".join(lc.lines({"long_videos_28d": 21}))
    assert "測っていません" in out
    assert "0本だった" in out or "ではありません" in out
    assert "21" in out


def test_印字に判定の数が出る():
    out = "\n".join(lc.lines({"long_values_28d": MEASURED,
                             "long_videos_28d": len(MEASURED)}))
    assert "中央値 **4回**" in out
    assert "6.5" in out
    assert str(lc.MEDIAN_GATE) in out
    assert "判定ではありません" in out


def test_門の数は仮説と同じ():
    """**2か所に書いてある数**。片方だけ動いたら、ここで落とします。"""
    text = (ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8")
    assert "長尺1本あたり-30本" in text
    i = text.index("長尺1本あたり-30本")
    section = text[i:i + 4000]
    assert f"中央値が {lc.MEDIAN_GATE}回 に届かない" in section, \
        "`falsified_if` の門が動いています。`MEDIAN_GATE` を合わせること"
    assert f"need: {lc.N_TARGET}" in section, \
        "`needs` の本数が動いています。`N_TARGET` を合わせること"


def test_eta_が分布を積む鍵を持っている():
    """`scripts/eta.py::_measure()` が `long_values_28d` を返すこと。

    **`data/eta.jsonl` に積まれないと、この道具は 0単位 で走れません。**
    """
    src = (ROOT / "scripts" / "eta.py").read_text(encoding="utf-8")
    assert '"long_values_28d": list(long_sorted)' in src


def test_積まれた点があれば読める():
    """`data/eta.jsonl` が在るなら、壊れずに読めること（無ければ飛ばす）。"""
    p = ROOT / "data" / "eta.jsonl"
    if not p.is_file():
        return
    row = lc.latest(p)
    assert isinstance(row, dict)
    out = "\n".join(lc.lines(row))
    assert out.strip()
    vals = row.get("long_values_28d")
    if isinstance(vals, list) and vals:
        # 積まれているなら、判定に使う本数と長さが合っていること
        assert len(vals) == row.get("long_videos_28d")


def test_壊れた行は飛ばす(tmp_path):
    p = tmp_path / "eta.jsonl"
    p.write_text('{"a": 1}\nこわれた行\n{"long_values_28d": [1, 2], "long_videos_28d": 2}\n',
                 encoding="utf-8")
    row = lc.latest(p)
    assert row["long_videos_28d"] == 2


def test_ファイルが無くても止まらない(tmp_path):
    row = lc.latest(tmp_path / "ない.jsonl")
    assert row == {}
    assert "測っていません" in "\n".join(lc.lines(row))


def test_json_で読める形のまま積める():
    """`list(long_sorted)` が JSON にできること（`_row()` は素の dict を書きます）。"""
    assert json.loads(json.dumps({"long_values_28d": MEASURED}))["long_values_28d"] == MEASURED
