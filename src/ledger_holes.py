"""**帳面の「入っているはずの列が空のまま」を、毎周 数える**（API 0単位・純関数寄り）。

## なぜ要るか（2026-09-04 に、3周ぶん運んでから気づいた）

`data/niche_ceiling.jsonl` の `top[].published` は **30本 中 30本 が空**でした。
気づいたのは 09/03 の回で、そこから **3周ぶん申し送りで運ばれ**、
その間ずっと `daily_pick` の「理論値の在りか」は
**外の生涯の累計 ÷ 自分の 48時間**という比を出し続けていました。
（埋めて数えたら、外の上位の齢は 長尺 中央 203日・ショート 1,729日 ＝ 4.7年。
　1日あたりに直すと、ショートは向きが変わります）

**誰も「何本 空か」を数えていませんでした。** 申し送りは「空だ」と書きますが、
**空の列は、その列ぶんの損ではなく、それを使う判断ぜんぶの損**です。
この repo の判断は帳面の上に乗っているので、**列が1つ欠けると、その列を読む画面が
全部 静かに嘘をつきます**（`niche_ceiling` の例では、形をどちらにするか）。

## 何を数えるか

**「在るはずの列」だけ**（`WATCH`）。全部の列を数えると、
**任意の列（あってもなくてもよい欄）が毎周 鳴って、読み飛ばされます** ——
この repo が `alerts.py` で一度 踏んだ形（一覧が当たりを含まないまま育つ）。

**門は 20%** です。1件 空いただけで鳴らすと、**書き始めの行**（まだ埋まっていない）で
毎周 鳴ります。**逆に 100% 空（＝ 誰も書いていない）は、必ず鳴らします** ——
それは「たまたま欠けた」ではなく **「その列を書く道が無い」**という意味だからです。

**覆る条件**: 3周 続けて 1件も鳴らなければ、`WATCH` が実物より狭いということなので、
**列を足すこと**（黙る計器は、壊れた計器と見分けが付きません）。
逆に、同じ列が 5周 鳴り続けたら、**それは「空でよい列」**なので `WATCH` から外すこと。

## **その列が「在るはずの行」だけを数えること**（2026-09-04 14:5x に踏んだ）

初版は **帳面の直近5行を、行の種類にかまわず**数えていました。
`data/runs.jsonl` には `ship` のほかに `start`（走った印）・`fix_gate`・`claim` が
混ざっていて、**そちらには `lever` がそもそも在りません**（書く道が無いのではなく、
**書く意味が無い**）。結果、画面は毎周

    data/runs.jsonl の `lever`: 2/5本 が空（**40%**）
    ＝ **書く道を先に直すこと。**

と鳴っていました。実際に数えると **`ship` 257本 の `lever` 欠けは 0本**です。
＝ **鳴っていたのは計器のほうで、直す先はどこにもありませんでした。**
この行は「先に直せ」と命じるので、**読んだ回はまず存在しない穴を探しに行きます**
（この回もそこから始めています）。

**だから `SCOPE` で行の種類を絞ります。** 絞った上で「直近5**本**」を数えるので、
`ship` が 5本 たまるまで遡ります —— **種類の混ざり具合で分母が動きません。**

**覆る条件**: `runs.jsonl` に `lever` を持つべき種類が増えたら `SCOPE` に足すこと。
逆に、ある列が「どの種類の行にも在るはず」なら `SCOPE` に書かないこと（既定は全部）。
"""
from __future__ import annotations

import json
from pathlib import Path

from . import config

#: 空を鳴らす割合の門。これ未満は「書き始め」と読んで黙る。
HOLE_PCT = 20.0

#: **在るはずの列**（帳面 → 行の中の道）。`a.b[].c` は「`a.b` の各要素の `c`」。
#: **在ってもなくてもよい欄を足さないこと**（毎周 鳴って読み飛ばされます）。
WATCH: dict[str, tuple[str, ...]] = {
    "data/niche_ceiling.jsonl": ("top[].published", "top[].views", "top[].secs"),
    "data/runs.jsonl": ("kind", "lever"),
    "data/rebake.jsonl": ("topic", "video_id"),
}


#: **その列が「在るはずの行」だけに絞る**（帳面 → 列 → 行の `kind`）。
#: 書いてない列は **全部の行**が対象。`kind` の無い帳面は絞れないので書かないこと。
SCOPE: dict[str, dict[str, tuple[str, ...]]] = {
    # `lever` は「この回はどの腕を引いたか」＝ **出した回（ship）にしか無い**。
    # `start` / `fix_gate` / `claim` は出した回ではないので、数えると分母だけ増えます。
    "data/runs.jsonl": {"lever": ("ship",)},
}


def _dig(row: dict, path: str) -> list:
    """`a.b[].c` を辿って、**その列の値を全部**返す（無い所は `None`）。"""
    cur: list = [row]
    for part in path.split("."):
        nxt: list = []
        star = part.endswith("[]")
        key = part[:-2] if star else part
        for x in cur:
            v = x.get(key) if isinstance(x, dict) else None
            if star:
                nxt += list(v) if isinstance(v, list) else []
            else:
                nxt.append(v)
        cur = nxt
    return cur


def _empty(v) -> bool:
    return v is None or v == "" or v == [] or v == {}


def count(ledger: str, paths: tuple[str, ...], *, root: Path | None = None,
          rows_back: int = 5, scope: dict | None = None) -> list[dict]:
    """帳面の**新しいほうから `rows_back` 行**で、列ごとに `{path, n, empty, pct}`。

    **古い行は数えません** —— 書き方が変わる前の行で鳴っても、直す先がありません。

    **`SCOPE` に載っている列は、その `kind` の行だけを数えます**（`scope` で差し替え可）。
    絞ってから `rows_back` を取るので、**直近5「行」ではなく 直近5「本」**です ——
    `start` や `claim` が混ざっても分母が動きません。
    """
    p = Path(root or config.ROOT) / ledger
    try:
        raw = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    except OSError:
        return []
    rows: list[dict] = []
    for ln in raw:
        try:
            row = json.loads(ln)
        except Exception:                                      # noqa: BLE001
            continue
        if isinstance(row, dict):
            rows.append(row)
    kinds = (SCOPE if scope is None else scope).get(ledger, {})
    out: list[dict] = []
    for path in paths:
        want = kinds.get(path)
        here = [r for r in rows if want is None or r.get("kind") in want]
        n = empty = 0
        for row in here[-max(1, rows_back):]:
            for v in _dig(row, path):
                n += 1
                empty += int(_empty(v))
        if n:
            out.append({"path": path, "n": n, "empty": empty,
                        "pct": 100.0 * empty / n})
    return out


def lines(*, root: Path | None = None, watch: dict | None = None,
          rows_back: int = 5, scope: dict | None = None) -> list[str]:
    """画面へ出す行。**穴が無ければ 1行も出しません**（出ない行は手順を増やしません）。"""
    holes: list[tuple[str, dict]] = []
    for ledger, paths in (watch or WATCH).items():
        for c in count(ledger, paths, root=root, rows_back=rows_back, scope=scope):
            if c["pct"] >= HOLE_PCT:
                holes.append((ledger, c))
    if not holes:
        return []
    out = [f"  [!] **帳面に、在るはずの列が空のまま在ります**"
           f"（`src/ledger_holes.py`・API 0単位・**その列が在るはずの種類だけ**の直近{rows_back}本）"
           " —— **空の列は、その列ぶんの損ではなく、それを読む画面ぜんぶの損です**"]
    for ledger, c in sorted(holes, key=lambda x: -x[1]["pct"]):
        whole = " **（1件も入っていません ＝ その列を書く道がありません）**" if c["pct"] >= 99.9 else ""
        out.append(f"       {ledger} の `{c['path']}`: "
                   f"{c['empty']}/{c['n']}本 が空（**{c['pct']:.0f}%**）{whole}")
    out.append("       ＝ **書く道を先に直すこと。**申し送りに「空だ」と書いて次の回へ回すと、"
               "その間ずっと、その列を読む画面が静かに嘘をつきます"
               "（`published` は 3周 運ばれ、そのあいだ形の比べ方が壊れていました）")
    return out
