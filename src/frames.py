"""**枠がどれだけ同じか**を1つの数にする —— 「何本ぶんの型があるか」。

    python -m src.frames            # いまの控えを測る（API 0単位・実測 1.4秒）
    python -m src.frames --forms    # 振り分けが実際に何割に散るかを、台帳のIDで数える

## なぜ要るか（2026-08-30・解除条件3の回に足した）

`AUTOMATION_PAUSED.md` の解除条件は6件あり、閉じたのは 1・2・5・6 です。
残る **3（final videos are materially varied ...）が本当の関門**だと、
同じ日の回が `CLAUDE.md` と `AUTOMATION_PAUSED.md` の両方に書きました ——
いま縛っているのは (A) AI ペルソナではなく **(B) 汎用・反復** のほうで、
原文はこうです:

    AI-generated content made with generic or unoriginal templates
    giving the impression of mass production

そして申し送りは、こうでした:

    **3番は「差がある」と言うのではなく、数で示すこと。**
    足りないのは、それを1つの尺度にまとめて「**何本ぶん違うか**」を出す道具のほう。

**ここがその道具です。**

## 何を数えるか —— **中身ではなく、決まった位置に来る決まった文字**

`src/legacy_corpus.variety()` は既に「中身がちがうこと」を数えていて、
実測は **題の族 526 / 出だしの形 689（694本中）** です。**中身は毎回ちがいます。**
それでも量産に見えるのは、**同じ場所に同じ文句が来る**からです。

だから見るのは、1本の中の**3か所だけ**にします（数字は `N` に潰します）。

    opening      読み上げ1行目の**頭4文字**       ← 「計算しま」
    closing      読み上げ最終行の**頭4文字**       ← 「明日やる」「あなたの」
    closing_tail 読み上げ最終行の**末尾6文字**     ← 「てください。」

**4文字・6文字なのは、実測でそこが台形の底だからです**（`--verbose` に表が出ます）。
頭を8文字まで伸ばすと長尺の集中は 84% → 9% に落ちますが、
それは**文句が同じまま、次の語が題材で変わっている**だけで、
視聴者が「また同じ入り方だ」と感じる単位ではありません。

## 尺度: **実効の型数**（`effective()`）

その軸の値の分布に対する `exp(シャノンエントロピー)` です。
**「この N本は、実質 何本ぶんの型でできているか」**を返します。

- 全部ちがえば n（本数そのもの）
- 全部同じなら 1.0
- 8割が1つの型なら、残りが何通りあっても 2 前後にしかなりません

**実測（2026-08-30。写しです。撃ち直すこと）**

    長尺 134本   opening 実効 **2.4**（「計算しま」が 84%）
                 closing 実効 **3.8**（「明日やる」61% ＋「最後に、」19%）
                 closing_tail 実効 **9.0**（「てください。」57%）
    ショート 558本 opening 実効 283.8（**ここは散っています**）
                 closing 実効 **24.4**（「あなたの」45% ＋「あなたは」9%）
                 closing_tail 実効 **22.6**（「てください。」40%）

**134本の長尺は、入り方で言えば 2.4本ぶんしかありません。**
これが「giving the impression of mass production」の中身です。

## **これは書き手の癖ではありません。指示文に直書きされていました**

    src/script_writer.py   「調べてみました」ではなく「計算しました」
    src/script_writer.py   **長尺のみ**: 最後のセグメントは「明日やること」を…
    src/script_writer.py   「あなたの手当は全員同額ですか。コメントで教えてください」

**上の3つの割合は、この3行の写しです。** だから直す場所も、そこです
（`script_writer.opening_form()` / `closing_form()` が本ごとに振り分け、
`verify._check_frame_repeat()` が崩れを投稿前に落とします）。

## この道具が**言わないこと**

**「だから審査に通ります」とは言いません。** 実効の型数が上がることは、
**同じ入り方が並ばない**ことしか意味しません。絵・声・尺・題材は別の軸で、
ここでは1つも見ていません（`legacy_corpus.variety()` の画の変化率が近いだけ）。
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STASH = ROOT / "data" / "critique_queue"

#: 見る場所。**増やすときは、実測で台形の底を確かめてから**（docstring の「何を数えるか」）。
OPEN_HEAD = 4
CLOSE_HEAD = 4
CLOSE_TAIL = 6

AXES = ("opening", "closing", "closing_tail")


def norm(text: str) -> str:
    """数字を `N` に潰す。**中身ではなく型を見るため**（`legacy_corpus._shape` と同じ考え）。"""
    return re.sub(r"[0-9０-９][0-9０-９,，.．]*", "N", str(text or ""))


def axes(narration: list[str]) -> dict[str, str]:
    """1本の**枠の署名**。読み上げの3か所だけを返します。

    **空の行は落とします** —— 控えに `""` が混ざると、頭4文字が全部 `""` になって
    「型が同じ」と誤って出ます（実測で 2本）。
    """
    lines = [str(x) for x in (narration or []) if str(x).strip()]
    if not lines:
        return {}
    first, last = norm(lines[0]), norm(lines[-1])
    return {
        "opening": first[:OPEN_HEAD],
        "closing": last[:CLOSE_HEAD],
        "closing_tail": last[-CLOSE_TAIL:],
    }


def effective(values) -> float:
    """**実効の型数** ＝ `exp(H)`。「この一群は、実質 何本ぶんの型でできているか」。

    全部ちがえば本数そのもの、全部同じなら 1.0。
    **中央値や最頻値では代わりになりません** —— 「8割が1つの型で、残りの2割が
    100通り」を、最頻値は 0.8 としか言わず、**残りの厚みを捨てます。**
    """
    c = collections.Counter(v for v in values if v is not None)
    n = sum(c.values())
    if not n:
        return 0.0
    h = -sum((v / n) * math.log(v / n) for v in c.values())
    return math.exp(h)


def concentration(rows: list[dict]) -> dict:
    """一群の枠を軸ごとに数える。`rows` は `{"narration": [...]}` を持つ辞書の列。"""
    sigs = [axes(r.get("narration") or []) for r in rows]
    sigs = [s for s in sigs if s]
    out: dict = {"n": len(sigs)}
    for ax in AXES:
        vals = [s[ax] for s in sigs]
        c = collections.Counter(vals)
        top, cnt = c.most_common(1)[0] if c else ("", 0)
        out[ax] = {
            "distinct": len(c),
            "top": top,
            "top_share": (cnt / len(vals)) if vals else 0.0,
            "effective": effective(vals),
        }
    return out


def recent(k: int = 20, portrait: bool | None = None,
           stash: Path | None = None, exclude: str = "") -> list[dict]:
    """**直近 k本**の控え（新しい順）。`verify` の門はここだけを見ます。

    **全部を見ないのは、ポリシーの原文がそう言っているから**です ——
    「同じチャンネルの動画を**続けて数本視聴した後**、繰り返しのように感じられる」。
    見るのは並びであって、生涯の平均ではありません。

    `exclude` は自分のテーマID。**撃ち直した自分の前の案を相手にしない**
    （`script_writer.used_bars()` が同じ理由で同じことをしています）。
    """
    st = STASH if stash is None else stash
    if not st.is_dir():
        return []
    rows = []
    for p in st.glob("*.json"):
        if p.name.endswith(".plan.json"):
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            continue
        if not d.get("narration"):
            continue
        if exclude and str(d.get("topic") or "") == exclude:
            continue
        if portrait is not None:
            o = d.get("orientation")
            # **控えは「縦」「横」で入っています。** 印字の都合ではなく、
            # `pipeline` がそのまま書いた値です（`legacy_corpus.corpus()` と同じ読み方）。
            if o is not None and (o == "縦") != bool(portrait):
                continue
        rows.append(d)
    rows.sort(key=lambda d: str(d.get("stashed_at") or ""), reverse=True)
    return rows[:k]


def report(verbose: bool = False) -> str:
    """いまの控えを測って出す。**API を1単位も使いません。**"""
    from . import legacy_corpus as lc

    recs = [r for r in lc.corpus() if r["narration"]]
    out = ["=== 枠は何本ぶんに散っているか（解除条件3の物差し）==="]
    for label, want in (("長尺", "横"), ("ショート", "縦")):
        sub = [r for r in recs if r["orientation"] == want]
        if not sub:
            continue
        c = concentration(sub)
        out.append(f"\n--- {label} {c['n']}本 ---")
        for ax in AXES:
            a = c[ax]
            out.append(
                f"  {ax:<13} 実効 **{a['effective']:6.1f}本ぶん**"
                f"（{c['n']}本中）  いちばん多い型 {a['top']!r} が {a['top_share']:.0%}"
                f" ／ 種類 {a['distinct']}"
            )
        if verbose:
            for ax, idx in (("opening", 0), ("closing", -1)):
                out.append(f"  [{ax}] 頭を何文字で切るか:")
                for k in (3, 4, 5, 6, 8, 10):
                    vals = [norm(r["narration"][idx])[:k] for r in sub]
                    cc = collections.Counter(vals)
                    out.append(f"      {k:>2}文字: 実効 {effective(vals):7.1f}"
                               f" ／ 最頻 {cc.most_common(1)[0][1] / len(vals):.0%}")
    out.append(
        "\n--- 読み方 ---\n"
        "  **実効の型数が本数に近ければ散っています。1に近いほど同じ型です。**\n"
        "  この3つが低いのは書き手の癖ではなく、`src/script_writer.py` の\n"
        "  指示文に文句が直書きされていたためです。\n"
        "  振り分けが実際に何割に散るかは `python -m src.frames --forms`。"
    )
    return "\n".join(out)


def forms_report() -> str:
    """**振り分けが実際に何割に散るか**を、台帳の実在のテーマIDで数える。

    生成は止まっているので新しい本は作れません。**が、振り分けはハッシュなので、
    出来上がりを待たずに今日 数えられます** —— これが解除条件3の証拠です。
    """
    from . import legacy_corpus as lc
    from . import script_writer as sw

    ids = sorted({str(r.get("topic") or "") for r in lc._rows().values() if r.get("topic")})
    out = [f"=== 振り分けは何割に散るか（台帳の実在テーマID {len(ids)}件）===",
           "  **出来上がりではなく、割り当てそのものを数えています。**"]
    for name, fn, kinds in (("opening", sw.opening_form, sw.OPENING_FORMS),
                            ("closing_long", lambda t: sw.closing_form(t, portrait=False),
                             sw.CLOSING_FORMS_LONG),
                            ("closing_short", lambda t: sw.closing_form(t, portrait=True),
                             sw.CLOSING_FORMS_SHORT)):
        vals = [fn(i) for i in ids]
        c = collections.Counter(vals)
        top = c.most_common(1)[0]
        out.append(f"\n  {name}（{len(kinds)}通り）: 実効 **{effective(vals):.2f}通り**"
                   f" ／ いちばん多い {top[0]!r} が {top[1] / len(vals):.0%}")
        for k, v in sorted(c.items()):
            out.append(f"      {k:<8} {v:5d}本 {v / len(vals):5.1%}")
    out.append(
        "\n  **比較**: いまの控えの実効は 長尺 opening 2.4通り・closing 3.8通り"
        "（`python -m src.frames`）。\n"
        "  振り分けの実効がそれを上回っていなければ、この回の直しは効いていません。"
    )
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--verbose", action="store_true", help="頭を何文字で切るかの表も出す")
    ap.add_argument("--forms", action="store_true", help="振り分けが何割に散るかを数える")
    args = ap.parse_args()
    print(forms_report() if args.forms else report(args.verbose))


if __name__ == "__main__":
    main()
