"""`script_writer._subject_missing` を回帰で固定する。

**なぜ要るか。2026-08-15、意図を知らない3体が3体とも「何の動画か言えない」
と答え、3体とも 0〜10 の 3 を付けました**（`b3ZewNvalXc` / `data/critique.jsonl`）。
理由も3体で一致していて、**「ふるさと納税」という語が8コマのどこにも
出ていなかった**からです。同じ回に作った `H28qfOxuJF0`（住宅ローン控除）も
**同じ欠け方**をしていたので、1本の事故ではなく生成の癖です。

    見出し: 目安表どおりだと / 上限額のずれ / 自分の率で出した上限 ...

タイトルには制度名が入っているので、**作った側からは主語があるように見えます。**
**フィードでタイトルは読まれません。** 金額だけが並ぶと、
数字は読めるのに主語が無い動画になります。

この検査で怖いのは**偽陽性**のほうです（正しい台本を落とすと投稿が止まる）。
だから2方向を固定します——**出ていないときに言うこと**と、
**見出し以外（表の行・棒の名前）に出ていれば通すこと。**
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import script_writer  # noqa: E402


class _Visual:
    def __init__(self, **kw):
        self._d = {"kind": "stat", "headline": "", "bars": [], "rows": [], "items": []}
        self._d.update(kw)

    def model_dump(self):
        return dict(self._d)


class _Seg:
    def __init__(self, narration: str, **visual):
        self.narration = narration
        self.visual = _Visual(**visual)


class _Script:
    def __init__(self, segments):
        self.segments = segments


def fires(segments, topic_id: str) -> bool:
    return bool(script_writer._subject_missing(_Script(segments), topic_id))


# (説明, セグメント, テーマID, 言うべきか)
CASES = [
    (
        "見出しに制度名が無い（実物 s-furusato-5 の並び）",
        [_Seg("目安表どおりだと8623円損します。", headline="目安表どおりだと"),
         _Seg("上限が16万9289円まで下がるからです。", headline="上限額のずれ"),
         _Seg("差の8623円は控除されません。", headline="自分の率で出した上限")],
        "s-furusato-5", True,
    ),
    (
        "見出しに制度名がある",
        [_Seg("目安表どおりだと8623円損します。", headline="ふるさと納税の上限"),
         _Seg("上限が16万9289円まで下がるからです。", headline="上限額のずれ"),
         _Seg("差の8623円は控除されません。", headline="内訳")],
        "s-furusato-5", False,
    ),
    (
        "**見出し以外**（棒の名前）に出ていれば通す",
        [_Seg("目安表どおりだと8623円損します。", headline="目安表どおりだと"),
         _Seg("上限が16万9289円まで下がるからです。", kind="chart",
              bars=[{"label": "ふるさと納税", "value": "16万9289円"}]),
         _Seg("差の8623円は控除されません。", headline="内訳")],
        "s-furusato-5", False,
    ),
    (
        "**4枚目**に出ても遅い（離脱は4.7〜5.7秒）",
        [_Seg("目安表どおりだと8623円損します。", headline="目安表どおりだと"),
         _Seg("上限が16万9289円まで下がるからです。", headline="上限額のずれ"),
         _Seg("差の8623円は控除されません。", headline="内訳"),
         _Seg("以上です。", headline="ふるさと納税のまとめ")],
        "s-furusato-5", True,
    ),
    (
        "住宅ローン控除（実物 s-jutaku-3 と同じ欠け方）",
        [_Seg("課税所得で戻る額が変わります。", headline="残高3000万円"),
         _Seg("差は6万円です。", headline="課税所得べつ"),
         _Seg("前提は次のとおりです。", headline="計算の前提")],
        "s-jutaku-3", True,
    ),
    (
        "**語を持っていないテーマは黙って通す**（投稿を止めないため）",
        [_Seg("なにかの数字です。", headline="見出し")],
        "ideco-vs-nisa", False,
    ),
    (
        "テーマIDが空なら見ない",
        [_Seg("なにかの数字です。", headline="見出し")],
        "", False,
    ),
]


def main() -> int:
    bad = 0
    for label, segments, topic_id, want in CASES:
        got = fires(segments, topic_id)
        mark = "ok " if got == want else "NG "
        if got != want:
            bad += 1
        verdict = "言う" if got else "通す"
        print(f"{mark} {label} -> {verdict}")
    print(f"\n{len(CASES)}件中 {bad}件の問題")
    return 1 if bad else 0


def test_subject():
    """pytest から呼ばれたときの入口。

    これが無いと、`pytest tests/` はこのファイルを import するだけで
    **0件のまま黙って通ります**（`def test_` が1つも無いため）。
    検査があるのに数に入らない、という形は素通りと同じです。
    """
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())


def test_calc_を足したら_SUBJECT_WORDS_にも足していること():
    """**足し忘れは、通算4件起きています**（taishoku・shobyo・souzoku・ikuji）。

    `_subject_missing` は語を持たない calc を**黙って通します**。
    その設計は変えません（投稿が止まるほうが損なので正しい）。
    ただし、**素通りしていることに誰も気づけない**のが問題でした。
    ここで数えれば、calc を足した回の `pytest` が落ちます。
    """
    import re
    from pathlib import Path

    from src.script_writer import SUBJECT_WORDS

    calc_dir = Path(__file__).resolve().parent.parent / "src" / "calc"
    modules = {p.stem for p in calc_dir.glob("*.py")
               if not p.stem.startswith("_")}
    missing = sorted(modules - set(SUBJECT_WORDS))
    assert not missing, (
        f"src/calc/ にあるのに SUBJECT_WORDS に無い: {missing}。"
        "冒頭で主語が立たない動画が、検査を素通りして出ます")

    stale = sorted(set(SUBJECT_WORDS) - modules)
    assert not stale, f"SUBJECT_WORDS にあるのに src/calc/ に無い: {stale}"
