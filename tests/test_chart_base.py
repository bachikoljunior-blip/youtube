#!/usr/bin/env python3
"""棒グラフの目盛りの起点（2026-08-15）。

**なぜこの検査が要るか。** 8/15 の `s-tedori-2` の3コマ目で、
率13% の棒が 244px、率15% が 240px で出ました。**長さの差 1.6%。**
目視には「同じ長さの棒が2本並んでいる」だけに見え、
**読み上げが言っている差が図から読み取れませんでした。**

原因は棒が必ず0から始まっていたことです。35万9318円と35万3000円を
0起点で描けば、当然ほぼ同じ長さになります。

直したのは「近い値どうしのときだけ起点をずらす」ことですが、
**黙ってずらすと、縮めた棒が0起点に見えて誤解を与えます**
（収益化ポリシーの側。CLAUDE.md の6）。だから、ずらしたときは必ず

    (1) 棒の頭に斜線の帯（`broken`）を出す
    (2) 起点の数字を画面に書く（`chart-base`）

の2つが付きます。**ここが落ちたら、図が嘘をつきます。**
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.visuals import (  # noqa: E402
    _chart_html, _fmt_axis, chart_base, reveal_variants,
)

BAD = 0


def check(name: str, got, want) -> None:
    global BAD
    if got == want:
        print(f"ok  {name}")
    else:
        BAD += 1
        print(f"NG  {name}\n    期待 {want!r}\n    実際 {got!r}")


def render(values: list[float], displays: list[str]) -> str:
    bars = [
        {"label": f"l{i}", "value": v, "display": d}
        for i, (v, d) in enumerate(zip(values, displays))
    ]
    return _chart_html({"kind": "chart", "bars": bars}, portrait=True)


def widths(html: str) -> list[float]:
    return [float(x) for x in re.findall(r"width:([0-9.]+)%", html)]


# --- 起点を決めるところ ---------------------------------------------------

check("近い2値はずらす", chart_base([359318, 353000]), 350000.0)
check("率でもずらす", chart_base([73.5, 70.3]), 68.0)
check("差が大きければ触らない", chart_base([136.8, 180.0, 255.6]), 0.0)
check("棒1本ならずらさない", chart_base([5000]), 0.0)
check("全部同じ値ならずらさない", chart_base([100, 100]), 0.0)
check("0を含むならずらさない", chart_base([0, 62185]), 0.0)
check("負を含むならずらさない", chart_base([-100, 100]), 0.0)
# 桁は問わない。**近ければ小さい数でもずらす**（9 と 10 は0起点だと差が9%）
check("小さい数でも近ければずらす", chart_base([9, 10]), 8.0)

# --- 描いたところ ---------------------------------------------------------

html = render([359318, 353000], ["35万9318円", "35万3000円"])
w = widths(html)
# **これがこの直しの本体。** 0起点なら 98.2% 対 100% で差が見えない。
check("近い2値は棒の長さがはっきり割れる", round(w[1] / w[0], 2) <= 0.5, True)
check("斜線の帯が出る", html.count("broken"), 2)
check("起点を画面に書く", "棒の起点は0ではなく 35万円" in html, True)

html = render([136.8, 180.0, 255.6], ["136万8千円", "180万円", "255万6千円"])
check("差が大きいときは帯を出さない", "broken" in html, False)
check("差が大きいときは注記も出さない", "chart-base" in html, False)

# **めくり（reveal）で1枚目に棒が1本しか来ないとき、そこから起点を決めると
# 枚ごとに目盛りが動いて図が嘘になる。** 全体から決めた起点が渡ること。
full = {"kind": "chart",
        "bars": [{"label": "料率13%", "value": 359318, "display": "35万9318円"},
                 {"label": "料率15%", "value": 353000, "display": "35万3000円"}]}
frames = reveal_variants(full, 2)
check("めくりの全枚に起点が渡る",
      [f.get("scale_base") for f in frames], [350000.0, 350000.0])
w0 = widths(_chart_html(frames[0], portrait=True))
w1 = widths(_chart_html(frames[1], portrait=True))
# 1本目の棒が枚をまたいで伸び縮みしないこと（目盛りが動いていない証拠）
check("めくりで1本目の長さが動かない", w0[0], w1[0])

# 0起点のまま（差が大きい）ときも、めくりで長さが動かないこと。
# **こちらのほうが本数が多く、実際の動画で通る道です。**
wide = {"kind": "chart",
        "bars": [{"label": "65歳", "value": 136.8, "display": "136万8千円"},
                 {"label": "70歳", "value": 180.0, "display": "180万円"},
                 {"label": "75歳", "value": 255.6, "display": "255万6千円"},
                 {"label": "80歳", "value": 331.2, "display": "331万2千円"}]}
ws = [widths(_chart_html(f, portrait=True)) for f in reveal_variants(wide, 4)]
check("0起点のめくりでも長さが動かない",
      [w[0] for w in ws], [ws[-1][0]] * len(ws))
check("0起点のめくりでは帯を出さない",
      any("broken" in _chart_html(f, portrait=True) for f in reveal_variants(wide, 4)),
      False)

one = {"kind": "chart", "scale_max": 359318, "scale_base": 350000.0,
       "bars": [{"label": "料率13%", "value": 359318, "display": "35万9318円"}]}
h1 = _chart_html(one, portrait=True)
check("めくり1枚目でも渡した起点を使う", "棒の起点は0ではなく 35万円" in h1, True)

zero = dict(one, scale_base=0.0)
check("渡した起点が0なら0起点のまま", "broken" in _chart_html(zero, portrait=True), False)

# 目盛りが壊れる渡し方（起点 >= 最大値）は0起点に戻す。**落とさない。**
broken_scale = dict(one, scale_base=999999.0)
check("起点が最大値以上なら0起点へ戻す",
      "broken" in _chart_html(broken_scale, portrait=True), False)

# --- 起点の書き方 ---------------------------------------------------------

check("円は万で丸める", _fmt_axis(350000, "35万9318円"), "35万円")
check("端数のある円はそのまま", _fmt_axis(352000, "35万9318円"), "352,000円")
check("率はそのまま", _fmt_axis(68, "73.5%"), "68%")
check("人も単位を引き継ぐ", _fmt_axis(1200, "1350人"), "1,200人")

print(f"\n{'すべて通りました' if not BAD else f'{BAD}件の問題'}")


def test_chart_base():
    """pytest から呼ばれたときの入口。

    ここが無いと、**`sys.exit()` が import の途中で飛んで `pytest tests/` が
    ディレクトリごと収集に失敗します**（2026-08-15 に踏んだ）。
    この1本が落ちるだけで済むように、終了は `__main__` のときだけにしてあります。
    """
    assert not BAD, f"{BAD}件の問題"


if __name__ == "__main__":
    sys.exit(1 if BAD else 0)
