"""**`main()` と `render()` が、上限を外した側を同じだけ出すか。**

## なぜ要るか（2026-08-30 夜の実測）

`src/density_verdict.py` の冒頭「割り引いて読むこと」は、
**生の倍率と、上限（`day_cap`）を外した側を並べて読め**と書いています。
ところが上限の節は `render()`（`scripts/status.py` が呼ぶ側）にだけ在り、
**`python -m src.density_verdict` の `main()` には無いまま**でした。

実測（`data/views.jsonl` 2026-08-30 時点）:

    生            詰めた日 2   対 1時間きざみ 716  ＝ **×0.003**
    上限を外すと  詰めた日 217 対 1時間きざみ 850  ＝ **×0.26**

**91倍 ちがいます。** 片方だけを見た人は、**間隔のせいにできない差まで
間隔のせいにします**（`docs/MEANS.md` M14 を畳んだのも、解除条件4で
`batch_build.cap_by_density()` に上限を入れたのも、この判定の側です）。

**`AUTOMATION_PAUSED.md` と `scripts/eta.py --gate` は、解除した最初の1周で
`python -m src.density_verdict` を撃ち直せと名指ししています** ——
撃ち直しが読むのは `main()` の側なので、そこが黙っていると
**解除の直後にいちばん効く所で黙ります。**

**この検査が守るのは「1つの実装を2か所が呼ぶ」形です。**
片方だけに行を足したら、ここが赤くなります。
"""
from __future__ import annotations

import contextlib
import io

from src import density_verdict as dv


def _rep(tight_med: int, hourly_med: int,
         cap_tight: int | None, cap_hourly: int | None) -> dict:
    def _v(t: int, h: int) -> dict:
        return {"tight_median": float(t), "hourly_median": float(h),
                "ratio": t / h,
                "outcome": "falsified" if t / h < dv.RATIO_FALSIFIED else "survived",
                "tight_days": ["d1", "d2", "d3"], "hourly_days": ["d4"],
                "tight_n": 3, "hourly_n": 1}
    rep = {"counts": {}, "per_day": {}, "ripe": set(), "dropped": 0,
           "freeze": {"n": 0}, "verdict": _v(tight_med, hourly_med),
           "latest_obs": None, "tracked": 0}
    rep["cap_free"] = (_v(cap_tight, cap_hourly)
                       if cap_tight is not None and cap_hourly is not None else {})
    return rep


def test_cap_lines_names_both_medians():
    lines = dv.cap_lines(_rep(2, 716, 217, 850))
    assert lines, "上限を外した側があるのに1行も出ていません"
    joined = "\n".join(lines)
    assert "217" in joined and "850" in joined


def test_cap_lines_is_quiet_without_a_cap_side():
    """**上限を外した側が無い回は、黙ること**（作り話を出さない）。"""
    assert dv.cap_lines(_rep(2, 716, None, None)) == []


def test_cap_lines_warns_when_the_raw_ratio_is_mostly_the_cap():
    """生 ×0.003 と 外した ×0.26 —— **91倍** のときに [!] が要る。"""
    joined = "\n".join(dv.cap_lines(_rep(2, 716, 217, 850)))
    assert "ほとんどが上限のぶんです" in joined


def test_cap_lines_warns_when_the_two_sides_disagree():
    """向きが違ったら、**本数を減らすなと言うこと。**"""
    joined = "\n".join(dv.cap_lines(_rep(2, 716, 900, 850)))
    assert "何も言っていません" in joined
    assert "減らさないこと" in joined


def test_render_uses_the_same_lines():
    rep = _rep(2, 716, 217, 850)
    out = dv.render(rep)
    for line in dv.cap_lines(rep):
        assert line in out, f"render() に無い行: {line!r}"


def test_main_prints_the_cap_side_too(monkeypatch):
    """**これが本題。** `python -m src.density_verdict` が黙っていた。"""
    rep = _rep(2, 716, 217, 850)
    monkeypatch.setattr(dv, "report", lambda *a, **k: rep)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        dv.main()
    printed = buf.getvalue()
    assert "0.26" in printed, (
        "`main()` が上限を外した側を出していません。"
        "生の倍率だけを読んだ人は、間隔のせいにできない差まで間隔のせいにします。")
    for line in dv.cap_lines(rep):
        assert line in printed, f"main() に無い行: {line!r}"
