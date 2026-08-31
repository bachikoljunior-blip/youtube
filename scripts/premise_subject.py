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

## **`lever:` の札は、`note:` も読んでから判定します**（2026-09-01 に足した）

**`[?]`（`lever:` が数えている値と合っていない）が、4周 持ち越されました**
（`retro.py` の持ち越し `premise_subject` 4回。2026-09-01 01:4x ／ 次の回へ ／
05:5x ／ 06:2x —— **4回とも「次の回へ」と書かれ、4回とも触られていません**）。

**当たっていたのは道具のほうでした。** 鳴っていた2件は、どちらも
`lever: rpm` への鎖を**本文に書いてあります**:

    長尺の再生シェア…（09-11）  note: 「実効RPM ＝ Σ_形（再生の割合 × その形の帯）。
                                     この前提が動かす `long_share_now` は、その式の重み」
    1本あたり再生の天井…（09-19） note: 「題材の族＝**ニッチ**（`CLAUDE.md`
                                     「rpm（ニッチ・尺・形式）」）」

**どちらも 2026-08-27〜08-29 に、YAML のインラインの註から `note:` へ写されています**
（`tests/test_eta_headline_alloc_hand.py` が「註は `yaml.safe_load` に読まれない」で
赤くなったため）。**写した先を、この道具だけが読んでいませんでした。**

**だから `lever_off` は `note:` も見ます。** `mismatch`（主語と数えている値）は
**見ません** —— `note:` は「なぜこの腕か」であって、**数えている値ではない**からです。
混ぜると、印字の「数えている＝」の欄が実物と食い違います。

**黙って消しません。** 本文で救われた行は `main()` が `[n]` で出し、
**鎖の書いてある行そのもの**を並べます（語が通りすがりに1つ出ただけの
「救い」を、次の回が目で捨てられるように）。

## 覆る条件

**`[!]` が出た行を1件ずつ当たって、3回続けて「わざとの代理指標だった」なら、
この道具は当たっていません** —— そのときは語彙ではなく `lever:` との
食い違いで並べ直すこと（`lever` は既に機械が読んでいる欄です）。
検査は `tests/test_premise_subject.py`。

**`[n]` の側にも覆る条件があります**: `[n]` の行を1件ずつ当たって、
鎖が「語が通りすがりに出ただけ」だったなら、**`note:` を読ませたのが誤り**です ——
そのときは `note:` ではなく、**機械が読む専用の欄**（`lever_chain:` など）を
立てること。**本文は人が読む所で、語彙の一致は根拠になりません。**
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


def lever_chain(h: dict, lever: str) -> str:
    """`note:` の中で、**その腕の量を名指ししている行**を1つ返す（無ければ空文字）。

    **救った根拠を、その場で見せるためのもの**です。`lever_off` を `note:` で
    外すだけだと、**語が通りすがりに1つ出ただけの行**も黙って消えます ——
    そのときに次の回が目で捨てられるよう、`main()` が `[n]` の隣にこれを出します。

    引くのは**行**です（`note:` は 20行 を超えることがあり、全文を貼ると
    毎周 台帳を丸ごと印字することになります）。
    """
    words = VOCAB.get(lever, ())
    if not words:
        return ""
    for line in str(h.get("note") or "").splitlines():
        line = line.strip()
        if line and any(w in line for w in words):
            return line
    return ""


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

    ## **`lever: none` の行は、どちらの札も付けません**（2026-09-01 に足した）

    **配線した回に、いちばん最初に出た `[!]` が、これで空振りでした。**
    実物（`config/hypotheses.yaml` 2026-09-30「収益化の審査は、門1・門2a の
    数字が揃えば通る（＝段3 は待つだけの段）」）:

        主語 = rpm       ← `claim` の「**収益**化」を `rpm` の語彙が拾う
        数えている = sub_rate ← `needs` の「門1（**登録者**1,000人）」を拾う

    **どちらも、この前提が主張している量ではありません。** あの行は
    `lever: none` ／ `side: infra` ——「腕を全部 掛ける側の係数」で、
    **量そのものを主張していません**（その行自身の註がそう書いています）。
    量を持たない行に「主語と値が交わらない」と言っても、**直しようがありません。**

    `lever_off` はもともと `none` を外していました（`config/hypotheses.yaml` 冒頭で
    `none` は**正しい札**なので）。**`mismatch` だけがその除外を持っていませんでした。**

    **これを直さずに配線すると、毎周 同じ空振りの `[!]` が1件 出続けます** ——
    そして「鳴っているのに誰も直さない計器」は、次に来た側が読まなくなります
    （`docs/JOURNAL.md` に同じ壊れ方が何度も出てきます）。

    **覆る条件**: `lever: none` の行が「量の主張」を持つようになったら
    （＝ 腕の札を付け直せるようになったら）、この除外は要りません。
    そのときは `lever:` のほうを直すこと —— **除外を消すのではなく。**

    ## **`lever_off` は `note:` も読みます。`mismatch` は読みません**（2026-09-01）

    **`note:` は「なぜこの腕か」を書く欄**で、実物の 82件 のうち多くが
    そこに鎖を持っています（`tests/test_eta_headline_alloc_hand.py` が
    「註は `yaml.safe_load` に読まれない」で赤くなって以来、**註から本文へ
    写す運用**になっています）。**この道具だけが、その写し先を読んでいませんでした。**

    `mismatch` には**足しません** —— `note:` は数えている値ではないので、
    足すと印字の「数えている＝」の欄が実物と食い違います。
    **救った行は消さず、`note_backed` を立てて `main()` が `[n]` で出します。**
    """
    out: list[dict] = []
    for h in open_rows(path):
        claim = str(h.get("claim") or "")
        cond = " ".join([str(h.get("falsified_if") or ""), needs_text(h)])
        subj, meas = measures(claim), measures(cond)
        lever = str(h.get("lever") or "")
        armless = lever == "none"
        # **`note:` に鎖が書いてあるか**（`lever_off` だけがこれを見ます。上の註）。
        chain = "" if armless else lever_chain(h, lever)
        off = bool(meas and lever and not armless and lever not in meas)
        out.append({
            "claim": claim,
            "deadline": str(h.get("deadline") or ""),
            "lever": lever,
            "side": str(h.get("side") or ""),
            "subject": subj,
            "measured": meas,
            # **`lever: none` の行は鳴らしません**（2026-09-01 に足した。下の註）。
            "mismatch": bool(subj and meas and not (subj & meas)) and not armless,
            "lever_off": off and not chain,
            # **黙って消さないための欄。** `off` だったが `note:` の鎖で救われた行。
            "note_backed": off and bool(chain),
            "note_line": chain if off else "",
        })
    return out


def _fmt(s: set[str]) -> str:
    return "/".join(sorted(s)) if s else "—"


def main(argv: list[str]) -> int:
    rows = audit()
    rows.sort(key=lambda r: (not r["mismatch"], not r["lever_off"],
                             not r["note_backed"], r["deadline"]))
    bad = [r for r in rows if r["mismatch"]]
    off = [r for r in rows if r["lever_off"] and not r["mismatch"]]
    backed = [r for r in rows if r["note_backed"] and not r["mismatch"]]

    print("=== 開いた前提の「主語」と「反証条件が数えている値」 ===")
    print(f"  開いているのは **{len(rows)}件**。"
          f"**主語と値が交わらない: {len(bad)}件** ／ "
          f"**`lever:` が値と合っていない: {len(off)}件**"
          f"（うち **`note:` の鎖で外したもの: {len(backed)}件**・下の `[n]`）")
    print("  **判定はしません。** わざと代理指標を使っている前提があります —— "
          "1件ずつ当たること（この道具の docstring の「覆る条件」）。")
    print()
    for r in rows:
        if r["mismatch"]:
            mark = "[!]"
        elif r["lever_off"]:
            mark = "[?]"
        elif r["note_backed"]:
            mark = "[n]"
        else:
            mark = "   "
        print(f"{mark} {r['deadline']}  lever={r['lever'] or '—':<9} "
              f"side={r['side'] or '—':<7} "
              f"主語={_fmt(r['subject']):<24} 数えている={_fmt(r['measured'])}")
        print(f"      {r['claim'][:96]}")
        if mark == "[n]":
            # **救った根拠を、その場で見せる**（黙って消さないこと。docstring の「覆る条件」）。
            print(f"      └ note: {r['note_line'][:120]}")
    if not bad and not off:
        print("\n  **食い違いはありません。**")
    if backed:
        print(f"\n  **`[n]` の {len(backed)}件 は、`note:` に腕への鎖が書いてあるので "
              "`[?]` から外しました。** 鎖が「語が通りすがりに出ただけ」だったら、"
              "**`note:` を読ませたのが誤り**です（docstring の「覆る条件」）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
