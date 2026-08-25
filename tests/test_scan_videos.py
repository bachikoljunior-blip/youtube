"""走査の横並び（動画どうしの比較）の検査。

**入れた理由は、作った直後に1回外したから。**
再生1回の本を率の計算に入れてしまい、`engaged／再生` の向きが
+0.77 から −0.25「無関係」に反転した。分母1の率が2件混ざっただけで、
中身は何も変わっていない。**同じ壊れ方を黙って再発させないための検査。**

    python -m tests.test_scan_videos
"""
from __future__ import annotations

import io
import contextlib

from src import scan


def _run(rows: dict[str, dict]) -> str:
    flat = {}
    for vid, r in rows.items():
        for k, v in r.items():
            flat[f"動画.{vid}.{k}"] = v
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        scan._videos(flat)
    return buf.getvalue()


def test_iso_seconds():
    assert scan._iso_seconds("PT52S") == 52
    assert scan._iso_seconds("PT11M5S") == 665
    assert scan._iso_seconds("PT1H2M3S") == 3723
    assert scan._iso_seconds("PT2M") == 120
    assert scan._iso_seconds("") == 0            # 壊れた入力で落ちないこと


def test_spearman_direction():
    assert abs(scan._spearman([1, 2, 3, 4], [1, 2, 3, 4]) - 1.0) < 1e-9
    assert abs(scan._spearman([1, 2, 3, 4], [4, 3, 2, 1]) + 1.0) < 1e-9
    assert scan._spearman([1, 1, 1, 1], [1, 2, 3, 4]) is None   # 分散0
    assert scan._spearman([1, 2, 3], [1, 2, 3]) is None         # 少なすぎる


# 実データ（2026-08-10）。6本は素直に並び、下2本が再生1。
REAL = {
    "a": {"views": 1512, "engagedViews": 525, "averageViewPercentage": 32,
          "averageViewDuration": 16, "尺": 52, "題": "年末調整"},
    "b": {"views": 1254, "engagedViews": 557, "averageViewPercentage": 51,
          "averageViewDuration": 28, "尺": 55, "題": "年金の繰下げ"},
    "c": {"views": 782, "engagedViews": 282, "averageViewPercentage": 30,
          "averageViewDuration": 14, "尺": 47, "題": "残業代の時給"},
    "d": {"views": 537, "engagedViews": 93, "averageViewPercentage": 69,
          "averageViewDuration": 36, "尺": 52, "題": "控除の還付額"},
    "e": {"views": 437, "engagedViews": 83, "averageViewPercentage": 42,
          "averageViewDuration": 23, "尺": 56, "題": "住宅ローン控除"},
    "f": {"views": 311, "engagedViews": 37, "averageViewPercentage": 102,
          "averageViewDuration": 56, "尺": 55, "題": "家族手当"},
    "g": {"views": 1, "engagedViews": 1, "averageViewPercentage": 98,
          "averageViewDuration": 51, "尺": 53, "題": "失業給付"},
    "h": {"views": 1, "engagedViews": 1, "averageViewPercentage": 17,
          "averageViewDuration": 113, "尺": 665, "題": "長尺"},
}


def test_thin_rows_excluded_from_direction():
    """**分母1の率で向きが反転しないこと。**"""
    out = _run(REAL)
    assert "engagedViews／再生" in out
    line = [ln for ln in out.splitlines() if "engagedViews／再生" in ln][0]
    assert "同じ向き" in line, line
    assert "+0." in line, line
    # 除外したことを黙らない
    assert "2本は除外" in out, out


def test_thin_rows_still_listed():
    """**表からは消さない。** 再生1本も事実で、消すと本数が合わなくなる。"""
    out = _run(REAL)
    assert "8本" in out
    assert "失業給付" in out and "長尺" in out


def test_completion_is_inverse():
    """完視率と再生数は逆向き（8/10 の実測）。**ここが順になったら何か変わった合図。**"""
    out = _run(REAL)
    line = [ln for ln in out.splitlines() if "averageViewPercentage" in ln][0]
    assert "逆向き" in line, line


def test_too_few_rows_says_so():
    thin = {k: REAL[k] for k in ("a", "b", "g", "h")}
    out = _run(thin)
    assert "向きは出せません" in out, out


def test_no_rows_is_silent():
    assert _run({}) == ""
    assert _run({"x": {"views": 0}}) == ""


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("すべて通りました")
