"""**数字の出どころの検査が、作り直しの輪の中に入っていること**を固定する。

## なぜ要るか（2026-08-15 22:5x）

8/15 22:2x の batch は 6本作って**予約できたのは2本**でした。落ちた4本のうち
**3本が同じ理由**で、タイトル・サムネ・冒頭 stat の数字が
`src/calc/` の出力に無い（モデルが丸めた）というものです。

その2件（`verify._check_title_from_calc` / `verify._check_headline_from_calc`）は
**`verify` にしか無く、当たるのはレンダリングが全部終わったあと**でした。
そこには直す口がありません。**その1本は丸ごと捨て**になります。
同時6での実測が1本2.7分なので、**3本＝約8分**がここで消えていました。

`script_writer.short_script_problems` の docstring は
「**台本だけで判定できるものは、全部ここに集める**」と言っています。
この2件は calc を走らせて突き合わせるだけで、音声も画像も要りません。
**集め忘れていただけ**です。

## ここで固定すること

1. **丸めた数字を言うこと**（言わなければ、この直しは何もしていない）
2. **正しい数字を落とさないこと** —— 偽陽性が怖い側です。
   落とすと投稿が止まり、それは最大の損失にあたります
3. **`short_script_problems` を通って届くこと** ——
   関数を足しても、呼ばれていなければ**緑のまま0件で通ります**
4. **数字と関係のない事情で例外を投げないこと** ——
   ここは生成中に呼ばれるので、落ちると台本作りごと止まります
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import script_writer  # noqa: E402

# `iryohi-kojo` の計算出力に実在する値（`python -m src.calc.iryohi` の表より）。
# 202,095円 は「300,000円 の医療費・5年分」の行。
REAL = 202095

# --- **「作り話の数字」を、手で決めないこと**（2026-08-22 に2度目を踏んで直した）---
#
# ここは長らく `ROUNDED = 250000` の1行でした。**節を1本足したら実在してしまい**、
# 「計算出力にありません」が鳴らなくなって**この file の4件が赤**になりました
# （足したのは `iryohi` の入院給付金の節。その他の医療費 **250,000円** が前提の1つ）。
#
# **同じことが1回目にも起きています** —— 最初に選んだ 200,000 は、
# 医療費控除の表が「支払った医療費」の列に持っていました。
# **2回とも、選んだ人には見えない列で実在していた**わけです。
# 手で選ぶかぎり、節を足すたびに同じ目が出ます。だから**選ぶのをやめて、
# 出力を見て「実在しない値」を機械に取らせます**（節が増えても勝手に避けます）。
def _calc_text() -> str:
    """`iryohi` の計算出力（1回だけ走らせて使い回す）。"""
    global _CALC_TEXT
    if _CALC_TEXT is None:
        proc = subprocess.run([sys.executable, "-m", "src.calc.iryohi"],
                              capture_output=True, text=True, timeout=300,
                              cwd=str(Path(__file__).resolve().parent.parent))
        assert proc.returncode == 0, proc.stderr[-400:]
        _CALC_TEXT = proc.stdout
    return _CALC_TEXT


_CALC_TEXT: str | None = None


def _in_calc(n: int) -> bool:
    """その数が、計算出力に**1つの数として**出ているか（桁の一部は数えない）。"""
    text = _calc_text()
    return any(re.search(rf"(?<![\d,]){re.escape(f)}(?![\d,])", text)
               for f in (f"{n:,}", str(n)))


def _absent_round_number(start: int = 250_000, step: int = 1_000) -> int:
    """**モデルが丸めがちな形**のまま、出力に無い値まで動かす。"""
    n = start
    for _ in range(1_000):
        if not _in_calc(n):
            return n
        n += step
    raise AssertionError("実在しない丸め値が見つかりません（step を変えること）")


ROUNDED = _absent_round_number()


def _script(title: str, stat: str = "20万2095円", source: str = "202,095円") -> dict:
    return {
        "title": title,
        "thumbnail_line1": "",
        "thumbnail_line2": "",
        "segments": [
            {
                "narration": "医療費控除で戻る額を計算しました。",
                "visual": {"kind": "stat", "headline": "5年分で戻る額",
                           "stat": stat, "stat_source": source,
                           "note": "総所得300万・税率10%",
                           "formula": "20万2095円 ＝ 4万419円 × 5年",
                           "items": [], "rows": [], "headers": [], "bars": []},
            },
        ],
    }


def test_丸めた数字は落ちる():
    problems = script_writer._calc_source_problems(
        "iryohi-kojo", _script(f"医療費控除 5年分で{ROUNDED:,}円戻る"))
    assert any("計算出力にありません" in p for p in problems), problems


def test_実在する数字は通る():
    problems = script_writer._calc_source_problems(
        "iryohi-kojo", _script(f"医療費控除 5年分で{REAL:,}円戻る"))
    assert problems == [], problems


def test_サムネの数字も見る():
    data = _script("医療費控除で戻る額を計算した")
    data["thumbnail_line1"] = f"{ROUNDED:,}円"
    problems = script_writer._calc_source_problems("iryohi-kojo", data)
    assert any("サムネ" in p for p in problems), problems


def test_冒頭statの出どころも見る():
    """`stat_source` が計算出力に無ければ落ちること（`_check_headline_from_calc`）。"""
    problems = script_writer._calc_source_problems(
        "iryohi-kojo",
        # **ここも `250,000円` の直書きでした**（上の `ROUNDED` と同じ穴。
        #   節を1本足したら実在してしまい、この1件だけ別の理由で赤くなります）。
        _script(f"医療費控除 5年分で{REAL:,}円戻る",
                stat=f"約{ROUNDED // 10_000}万円", source=f"{ROUNDED:,}円"))
    assert problems, "計算出力に無い stat_source が素通りしています"


def test_short_script_problems_を通って届く():
    """**関数を足しても、呼ばれていなければ緑のまま0件で通ります。**

    `short_script_problems` は Pydantic のモデルを取るので、
    `model_dump()` だけ持つ最小の身代わりを通す。
    """
    data = _script(f"医療費控除 5年分で{ROUNDED:,}円戻る")

    class _V:
        def __init__(self, d):
            self._d = d
            self.headline = d["headline"]

        def model_dump(self):
            return dict(self._d)

    class _S:
        def __init__(self, seg):
            self.narration = seg["narration"]
            self.visual = _V(seg["visual"])

    class _Script:
        def __init__(self, d):
            self.segments = [_S(s) for s in d["segments"]]
            self._d = d

        def model_dump(self):
            return dict(self._d)

    problems = script_writer.short_script_problems(_Script(data), "iryohi-kojo")
    assert any("計算出力にありません" in p for p in problems), problems


def test_引けないテーマでも例外にしない():
    """**生成中に呼ばれるので、落ちると台本作りごと止まります。**"""
    assert script_writer._calc_source_problems(
        "no-such-topic-id", _script("題")) is not None


def test_この検査の作り話が_本当に作り話であること():
    """**土台の点検**（2026-08-22）。ここが崩れると、上の4件は静かに偽の合格になります。

    `ROUNDED` は「計算出力に無い値」であることだけが取り柄で、
    **節を1本足すと実在しうる**（実際に2回なった）。だから毎回そこから確かめます。
    """
    assert _in_calc(REAL), "REAL が計算出力から消えています（表を変えたなら選び直すこと）"
    assert not _in_calc(ROUNDED), f"{ROUNDED:,} は、もう作り話ではありません"
    assert ROUNDED % 1_000 == 0, "丸めがちな形のままであること"
