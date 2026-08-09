"""`verify._to_yen` の表記ゆれの取り込みを固定する。

**なぜ要るか。1日に2回、この関数の偽陽性で正しい動画を落とした**（2026-08-09）。

  1. 「35万9318円」から 359,318 と **9,318 の両方**が出ていた。
     万の式を読んだ後、同じ数字を素の数字としてもう一度拾っていた。
  2. 「35.9万」で正規表現が **`9万` に食いついて 90,000** を返していた。
     落とす判断自体は正しかった（35.9万は359,318円の丸め）が、
     **理由が嘘**なので、直す側は存在しない 90,000 を探しに行くことになる。

検査の偽陽性は、単に間違っているより悪い。**作り直しを何回も強いたうえ、
「数字を発明した」という誤った記録が残る。** ここを回帰で固定する。

各行は「この表記から、この整数の集合が出ること」。
**期待値は実装を写したものではなく、人が読んで正しい額**にすること。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.verify import _to_yen  # noqa: E402

CASES: list[tuple[str, set[int]]] = [
    # 素の数字
    ("287,000円", {287000}),
    ("年7,275円と9,296円", {7275, 9296}),
    ("1,751円から1,641円", {1751, 1641}),
    # 万
    ("30万", {300000}),
    ("30万円", {300000}),
    ("1億円", set()),                      # 億は見ない（見るのは万と素の数字だけ）
    # 万＋端数。**ここで端数を素の数字として二重に拾わないこと**
    ("35万9318円", {359318}),
    ("1万6544円", {16544}),
    ("1万2529円", {12529}),
    ("16万9289円", {169289}),
    # 万＋千
    ("3万1千円", {31000}),
    ("2万3千円", {23000}),
    # **小数の万。`9万` に食いつかないこと**
    ("35.9万", {359000}),
    ("1.5万円", {15000}),
    ("50万昇給で 手取り35.9万", {500000, 359000}),
    # 混在
    ("一律18,000円で年7,275円の差", {18000, 7275}),
    ("35万9318円と14万682円", {359318, 140682}),
    # **桁の足りないものは拾わない。** 素の数字は3桁からで、
    # 呼ぶ側もさらに1000以上しか見ない（条番号・パーセント・年齢を
    # 金額と取り違えないため）。
    ("労基法37条5項", set()),
    ("残る割合は71.9%", set()),
    ("163.3時間", {163}),
    ("前提を全部出します", set()),
]


def _problems(text: str, want: set[int]) -> list[str]:
    got = _to_yen(text)
    out = []
    if got != want:
        missing = sorted(want - got)
        extra = sorted(got - want)
        if missing:
            out.append(f"取りこぼし {missing}")
        if extra:
            out.append(f"**余計に拾った** {extra}（偽陽性の元）")
    if any(not isinstance(x, int) for x in got):
        out.append(f"int でない値が混ざっている: {got!r}")
    return out


def test_to_yen():
    failures = []
    for text, want in CASES:
        for p in _problems(text, want):
            failures.append(f"{text!r}: {p}")
    assert not failures, "\n".join(failures)


if __name__ == "__main__":
    bad = 0
    for text, want in CASES:
        problems = _problems(text, want)
        bad += len(problems)
        print(f"{'NG' if problems else 'ok'} {text:26} -> {sorted(_to_yen(text))}")
        for p in problems:
            print(f"      {p}")
    print(f"\n{len(CASES)}件中 {bad}件の問題")
    raise SystemExit(1 if bad else 0)
