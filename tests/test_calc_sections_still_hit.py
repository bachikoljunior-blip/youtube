"""**`calc_sections` が、いまも実物の節に当たるか**（2026-08-27 に踏んだ）。

`config/topics.yaml` の `calc_sections` は、`src/script_writer.py` が
**画面に出す表そのものを選ぶ鍵**です。当たらないと生成がその場で落ちます:

    RuntimeError: calc_sections [...] に当たる節が src.calc.<表> の出力にありません

**書き込むときは `topic_forge.py` が確かめています。** 確かめていないのは
**あとから見出しを直したとき**で、そこが 2026-08-27 に開きました ——
`src/calc/jutaku.py` の見出しを

    === 同じペアの13年ぶんの合計（4500万円・35年・金利1.0%）===
    → === 同じペアの13年ぶんの合計（課税総所得600万と100万・4500万円・35年・金利1.0%）===

と直したところ、`jutaku-mochibun-13nen-389546` の `calc_sections` が
**当たらなくなりました**（当たり判定は部分一致で、`（4500万円` の手前に
語が入ったため）。**そのテーマは、作ろうとした回に初めて落ちます。**

さらに悪いことに、`topic_forge --list` はその節を「未使用」と数え直し、
**同じ節を指す2件目のテーマを書きました**（同じ表から2本の動画が出る形）。

**見出しを直すのは正しい**（前提を画面に出すのはこの作りの根幹）。
直したときに**当たらなくなった側が黙っていた**のが欠陥です。ここで鳴らします。

**直し方**: `calc_sections` は**短くて動かない語**にすること。
見出しの丸ごとの写しにすると、見出しに数を足すたびに切れます。
"""
from __future__ import annotations

import importlib
import io
import contextlib
import runpy
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TOPICS = yaml.safe_load((ROOT / "config" / "topics.yaml").read_text(encoding="utf-8"))["topics"]

#: `calc_sections` を持つテーマがある表だけを走らせる（全部走らせると遅い）。
WANTED: dict[str, list[tuple[str, list[str]]]] = {}
for _t in TOPICS:
    _calc = _t.get("calc")
    _sections = _t.get("calc_sections") or []
    if _calc and _sections:
        WANTED.setdefault(_calc, []).append((_t["id"], list(_sections)))


def _headings(calc: str) -> list[str]:
    """その表が実際に印字している `=== 見出し ===` の一覧。"""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        runpy.run_module(f"src.calc.{calc}", run_name="__main__")
    return [line.strip() for line in buf.getvalue().splitlines()
            if line.strip().startswith("===")]


@pytest.mark.parametrize("calc", sorted(WANTED))
def test_calc_sectionsがいまも節に当たる(calc: str):
    heads = _headings(calc)
    assert heads, f"src.calc.{calc} が `=== 見出し ===` を1つも印字していません"
    misses = []
    for topic_id, wanted in WANTED[calc]:
        # `src/script_writer.py` と同じ当たり判定（見出しに語が含まれるか）
        if not any(any(w in h for w in wanted) for h in heads):
            misses.append(f"{topic_id} → {wanted}")
    assert not misses, (
        f"src.calc.{calc} の節に当たらない calc_sections があります:\n  "
        + "\n  ".join(misses)
        + "\n**見出しを直したなら、`calc_sections` を短くて動かない語に直すこと。**"
    )


def test_同じ節を指す長尺が2件以上ない():
    """**長尺どうしだけを見ます。**

    ショートは同じ節から何本も切って構いません —— 1本で言うのは1つだけなので、
    週の日数や年収を替えれば主役の数字が変わります（実物では `yukyu` の3件、
    `saishushoku` の6件が**そう作られています**）。

    **長尺は「表を最後まで読み切る」形**なので、同じ節から2本 作ると
    **同じ表を2回 読むことになります。** `CLAUDE.md` が名指ししている
    「続けて数本 視聴した後、繰り返しのように感じられる」に直に当たるので、
    ここだけを門にします。

    2026-08-27 に実際に出ました —— 見出しを直したせいで既存の長尺が
    当たらなくなり、`topic_forge` が「未使用」と読んで**同じ節の長尺をもう1件**
    書きました。上の検査と対で、その形を2か所から塞ぎます。
    """
    seen: dict[tuple[str, str], list[str]] = {}
    for topic in TOPICS:
        calc = topic.get("calc")
        if not calc or topic["id"].startswith("s-"):
            continue
        for section in topic.get("calc_sections") or []:
            seen.setdefault((calc, section), []).append(topic["id"])
    dupes = {k: v for k, v in seen.items() if len(v) > 1}
    assert not dupes, f"同じ節を指す長尺が複数あります: {dupes}"
