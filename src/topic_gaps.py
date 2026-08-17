"""`config/topics.yaml` の `calc:` が抜けているテーマを、**実物から**名指しする。

    from src import topic_gaps
    for row in topic_gaps.calcless(topics, modules):
        ...

## なぜ要るか（2026-08-18。**前の回が書き置いた警告が、当たっていた**）

前の回（02:0x）は `src/calc/ninikeizoku.py` を書いたあと、`topics.yaml` の
`taishoku-hoken` にこう書き残しています ——

> **ここは長らく「calc: なし ＝ このテーマはまだ使えない」でした。**
> 表を書いた回が、この行を書き換え忘れると永久に使えないままになります。

**その「書き換え忘れ」が、同じファイルの中に既に2件ありました。**

    ideco-vs-nisa    `calc: なし`  ← `src/calc/ideco.py` は **7節**ある
    fukugyo-zeikin   `calc: なし`  ← `src/calc/fukugyo.py` は **5節**ある

`scripts/batch_build.pick()` は `t.get("calc")` が空のテーマを**プールから丸ごと外します**
（`usable = [t for t in pool if ... and t.get("calc")]`）。つまりこの2件は、
**表が在るのに、在庫として一度も数えられていませんでした。**

## 気づけない形をしている

`calc: なし` の行は**コメント**（`# calc: なし。…`）で、YAML の鍵ではありません。
だから読み込んだ側から見ると「`calc` 欄が無い」だけで、
**「まだ書いていない」と「書いたのに繋いでいない」の区別が付きません。**
`status.py` は在庫を「未投稿テーマ」と「未使用の節」の2段で測っていますが、
**繋ぎ忘れたテーマは、そのどちらの段にも現れません**（テーマは在る・節も在る）。

## 突き合わせは、手書きの表を作らずにやる

`src/calc/` の実物のファイル名と、テーマIDの語を突き合わせます
（`fukugyo-zeikin` → `fukugyo`）。**語彙を手で並べないこと** ——
表を足した回が必ず書き忘れます（`retro.noise_tokens` と同じ理由で、
実物から引けるものは実物から引く）。

**「在る」と言えるのは繋ぎ先の候補までで、繋いでよいかは人が決めます。**
テーマの題が表の守備範囲を超えていることがあるからです
（`ideco-vs-nisa` は NISA 側の数字を `ideco.py` が持っていません。
繋ぐと**無い数字を発明させる**ことになるので、題のほうを直すのが先です）。
だから、この道具は**止めません。名指しするだけ**です。
"""
from __future__ import annotations

from pathlib import Path

from . import alerts

# `src/calc/` のうち、表ではないもの。実物から引くときに落とす。
_NOT_A_TABLE = {"__init__", "_checks", "_template"}


def modules(root: Path | None = None) -> set[str]:
    """`src/calc/` に**実際にある**表の名前。手で並べないこと。"""
    base = Path(root) if root else Path(__file__).resolve().parent
    return {
        p.stem
        for p in (base / "calc").glob("*.py")
        if p.stem not in _NOT_A_TABLE and not p.stem.startswith("__")
    }


def candidate_for(topic_id: str, mods: set[str]) -> str | None:
    """テーマIDの語のうち、表の名前と一致するもの（無ければ None）。

    `fukugyo-zeikin` → `fukugyo`。**IDの語だけを見ます** ——
    題や angle の全文で拾うと、言及しただけの表に当たります。
    """
    for token in str(topic_id).split("-"):
        if token in mods:
            return token
    return None


def calcless(topics: list[dict], mods: set[str] | None = None) -> list[dict]:
    """`calc:` の無いテーマを、繋ぎ先の候補つきで返す。

    返る各行:

        {"id": …, "candidate": "fukugyo" or None, "title_seed": …}

    `candidate` が入っている行が「**表は在るのに繋がっていない**」ほうです。
    """
    mods = modules() if mods is None else mods
    out = []
    for t in topics:
        if t.get("calc"):
            continue
        out.append({
            "id": t.get("id", ""),
            "candidate": candidate_for(t.get("id", ""), mods),
            "title_seed": t.get("title_seed", ""),
        })
    return out


def report_lines(topics: list[dict], posted: set[str] | None = None,
                 mods: set[str] | None = None) -> list[str]:
    """`status.py` に出す行。**繋ぎ忘れを上に、未着手を下に。**

    `posted` を渡すと、**もう上げたテーマには「（投稿済み）」を付けます** ——
    繋いでも在庫は増えないので、この回の手として選ばないため。
    """
    rows = calcless(topics, mods)
    if not rows:
        return []

    posted = posted or set()
    stale = [r for r in rows if r["candidate"]]
    todo = [r for r in rows if not r["candidate"]]

    lines: list[str] = []
    if stale:
        # **`[!]` を使わないこと**（2026-08-18）。あの印は在庫の段
        # （`pick` の返りが8を割った）に予約されていて、`tests/test_topic_stock.py`
        # が「pick が8以上なら `[!]` を出さない」を見ています。
        # **こちらは pick の多寡と無関係に鳴るので、同じ印を使うと嘘になります。**
        lines.append(f"  [gap] **表が在るのに `calc:` が繋がっていないテーマ {len(stale)}件**"
                     "（`pick` のプールから丸ごと外れています）:")
        for r in stale:
            mark = "  ← **投稿済み**（繋いでも在庫は増えません）" if r["id"] in posted else ""
            lines.append(f"      {r['id']}  → `calc: {r['candidate']}`{mark}")
        lines.append("      **繋ぐ前に、題が表の守備範囲に収まるかを見ること。**"
                     "はみ出していれば、繋ぐのではなく**題のほうを直す**"
                     "（無い数字を発明させないため）。")
    if todo:
        lines.append(f"  **まだ表の無いテーマ {len(todo)}件**"
                     "（(A) を選ぶときの題材。**題材決めが0分になります**）:")
        for r in todo:
            mark = "  ← 投稿済み" if r["id"] in posted else ""
            lines.append(f"      {r['id']}  {r['title_seed'][:38]}{mark}")
    lines += material_low(len(todo))
    return lines


# **題材が尽きると、(A) の題材決めが 0分 → 20分 に戻ります**（8/17 16:2x の実測）。
# 補充は約2分/件（8/18 06:1x の実測）で **(A) 1本より1桁安い**のに、
# **減っていることを誰も警告していませんでした**（2026-08-18 に足した）。
# 一覧そのものは前からあります。**足りないのは「残りが少ない」と言う側**でした。
MATERIAL_FLOOR = 5


def material_low(remaining: int) -> list[str]:
    """題材の残りが床を割ったら1行言う。**尽きてからでは遅い。**"""
    short = max(0, MATERIAL_FLOOR - remaining)
    r = alerts.ring("topic_material_low", short)
    if short == 0:
        return []
    if r.folded:
        return [f"  {r.line}"]
    return [
        f"  [材料] **(A) の題材が残り {remaining}件**（床は {MATERIAL_FLOOR}件）。"
        f"**尽きると題材決めが 0分 → 20分 に戻ります。**",
        "      補充は `config/topics.yaml` に `calc:` の無いテーマを足すだけ"
        "（約2分/件・**(A) 1本より1桁安い**）。"
        "潰したら `run_marker.py --ship ... --closes topic_material_low`",
    ]
