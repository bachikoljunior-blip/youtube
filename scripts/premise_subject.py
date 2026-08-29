"""**開いた前提の「主語」と「反証条件が数えている値」を、1行ずつ並べる。**

（API は 0 単位。読むのは `config/hypotheses.yaml` だけ・実測 1秒未満）

なぜ要るか。**2026-08-29 20:0x と 08-30 02:3x の申し送りが、同じことを2回 書いています**
（`retro.py` の持ち越し `falsified_if` 2回）。原文:

> 「反証条件が、その主張を検出できるか」を、他の開いた前提でも1回 見ること。
> **共通の形は「条件が数えているものが、主張の主語と違う」** ——
> ここでは主語が「族」なのに、数えているのは「公開本数」だった。
> 開いた28件を `claim` の主語と `falsified_if` の数えている値で1行ずつ並べれば出る。

**手で並べないこと。** 08-29 20:0x の回は1件を手で見つけ、
「他でも1回 見ること」と書いて渡しました。次の回（21:5x）も、その次（02:3x）も
**並べていません** —— 28件を手で読むのが1周ぶんの仕事だからです。

**この道具がやるのは「並べる」ところまで**です。判定はしません ——
主語と値が食い違って**いてよい**前提があります（代理指標をわざと使っている形）。
機械が決めると、その1件を黙って書き換えることになります。

## 何を「主語」と呼ぶか

`claim` の文から、**この輪が実際に数えている 4種類の量**を拾います
（`config/hypotheses.yaml` 冒頭の「選び方」と同じ語彙）:

    per_video  再生・engaged・視聴・維持・インプレッション
    density    本数・公開・枠・面の本数・族
    sub_rate   登録
    rpm        収益・単価・RPM・面（インプレッション）

`falsified_if` と `needs`（`count_expr` / `watch`）からも同じ語彙を拾い、
**両者が交わらない行を `[!]` で出します。**

## 覆る条件

**`[!]` が出た行を1件ずつ当たって、3回続けて「わざとの代理指標だった」なら、
この道具は当たっていません** —— そのときは語彙ではなく `lever:` との
食い違いで並べ直すこと（`lever` は既に機械が読んでいる欄です）。
検査は `tests/test_premise_subject.py`。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
HYPOTHESES = ROOT / "config" / "hypotheses.yaml"

#: 量の語彙。**腕の名前と同じ札にしてあります**（`config/hypotheses.yaml` 冒頭）。
#: 語は「実物から引く」ことができません（日本語の散文なので）。**手で並べています** ——
#: 足りないと `[!]` が増える側に外れるので、**安全側**です（見落としではなく空振り）。
VOCAB: dict[str, tuple[str, ...]] = {
    "per_video": (
        "再生", "engaged", "エンゲージ", "視聴", "維持", "完視", "スワイプ",
        "平均秒", "CTR", "クリック",
    ),
    "density": (
        "本数", "公開", "枠", "本/日", "族", "在庫", "テーマ", "予約", "投稿",
        "密度", "日あたり",
    ),
    "sub_rate": ("登録", "subscribersGained", "チャンネル登録"),
    "rpm": ("収益", "単価", "RPM", "面", "インプレッション", "広告", "月収"),
}


def measures(text: str) -> set[str]:
    """文の中に出てくる**量**を、上の語彙で拾う。

    **語が1つも当たらなければ空集合**です（`[!]` は出しません ——
    「拾えなかった」と「食い違っている」は別物なので）。
    """
    if not text:
        return set()
    found: set[str] = set()
    for arm, words in VOCAB.items():
        if any(w in text for w in words):
            found.add(arm)
    return found


def needs_text(h: dict) -> str:
    """`needs` / `watch` から、数えている値の字面を1つの文にまとめる。"""
    parts: list[str] = []
    w = h.get("watch")
    if w:
        parts.append(str(w))
    for n in h.get("needs") or []:
        if not isinstance(n, dict):
            continue
        for k in ("count_expr", "kind", "group_key", "metric"):
            v = n.get(k)
            if v:
                parts.append(str(v))
    return " ".join(parts)


def open_rows(path: Path | None = None) -> list[dict]:
    """**開いている前提だけ**（`effect` も `closed` も書かれていないもの）。"""
    p = path or HYPOTHESES
    items = yaml.safe_load(p.read_text(encoding="utf-8")).get("hypotheses", [])
    return [h for h in items
            if isinstance(h, dict) and h.get("effect") is None and not h.get("closed")]


def audit(path: Path | None = None) -> list[dict]:
    """1件ずつ「主語」「数えている値」「食い違っているか」を返す。

    `mismatch` が `True` になるのは、**両方とも拾えていて、かつ交わらない**とき
    だけです（片方が空なら `False` —— 拾えなかっただけかもしれないので）。
    """
    out: list[dict] = []
    for h in open_rows(path):
        claim = str(h.get("claim") or "")
        cond = " ".join([str(h.get("falsified_if") or ""), needs_text(h)])
        subj, meas = measures(claim), measures(cond)
        out.append({
            "claim": claim,
            "deadline": str(h.get("deadline") or ""),
            "lever": str(h.get("lever") or ""),
            "side": str(h.get("side") or ""),
            "subject": subj,
            "measured": meas,
            "mismatch": bool(subj and meas and not (subj & meas)),
            "lever_off": bool(meas and h.get("lever") and str(h["lever"]) != "none"
                              and str(h["lever"]) not in meas),
        })
    return out


def _fmt(s: set[str]) -> str:
    return "/".join(sorted(s)) if s else "—"


def main(argv: list[str]) -> int:
    rows = audit()
    rows.sort(key=lambda r: (not r["mismatch"], not r["lever_off"], r["deadline"]))
    bad = [r for r in rows if r["mismatch"]]
    off = [r for r in rows if r["lever_off"] and not r["mismatch"]]

    print("=== 開いた前提の「主語」と「反証条件が数えている値」 ===")
    print(f"  開いているのは **{len(rows)}件**。"
          f"**主語と値が交わらない: {len(bad)}件** ／ "
          f"**`lever:` が値と合っていない: {len(off)}件**")
    print("  **判定はしません。** わざと代理指標を使っている前提があります —— "
          "1件ずつ当たること（この道具の docstring の「覆る条件」）。")
    print()
    for r in rows:
        mark = "[!]" if r["mismatch"] else ("[?]" if r["lever_off"] else "   ")
        print(f"{mark} {r['deadline']}  lever={r['lever'] or '—':<9} "
              f"side={r['side'] or '—':<7} "
              f"主語={_fmt(r['subject']):<24} 数えている={_fmt(r['measured'])}")
        print(f"      {r['claim'][:96]}")
    if not bad and not off:
        print("\n  **食い違いはありません。**")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
