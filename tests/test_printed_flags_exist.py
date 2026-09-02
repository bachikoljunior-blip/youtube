"""**画面に印字する手は、実際に撃てること。**

## 実物（2026-09-02・最適化の回。**撃って踏んだ**）

`scripts/slot_gate.py` は、きょうの枠が空いている回にこう印字していました:

    (a) **前の日に作った下書きが在るなら、それを今日の枠へ**（1本 50単位）:
          python scripts/reschedule.py --pool          # private の下書きを見る

**`--pool` という旗はありません。** 撃つと `usage: …` ＋ **exit 2**。

しかも**そこは、規則5（固定その4）の下で毎日 0時 JST に必ず通る道の1手目**です
（「現在の日付にしか予約しない」＝ **明日から先は必ず空**なので、
この門は毎朝 鳴り、その1行目が毎朝 読まれます）。

`src/house_rule.py` 冒頭が名指ししている「**言っている所と、している所が別**」の、
**手順の側**の実例です。文書だけを直しても同じことが起きるので、検査にしました。

## 何を見ているか

`src/` と `scripts/` の中の `scripts/<なにか>.py --<旗>` という印字を全部 拾い、
**その旗を、印字が名指ししている当のファイルが知っているか**を見ます。

## 覆る条件・見ないもの

- **`#` で始まる行は見ません** —— 註は印字ではないからです
  （`scripts/relay.py` の「`--plan` という名前にしないこと」で踏みました）。
- **旗を1つも知らない道具**（`--…` の字が1つも無い）は飛ばします。
- `argparse` に無くても、**`sys.argv` から手前で抜く旗**（`--alerts-all`・
  `--draft`）は「知っている」に数えます。**撃てるからです。**
- **木（`scripts` / `src`）まで込みで当てます** —— `inbox.py` は両方に在り、
  名前だけで引くと `src/inbox.py` の**git の旗**と突き合わせて偽陽性になります。
- 旗を消したいときは、**印字の側も一緒に消すこと。**
  この検査は「印字が古い」と「旗を消した」を区別しません ——
  **どちらも直す先は同じ**（両方を合わせる）です。
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

#: `python scripts/foo.py --bar` / `scripts/foo.py --bar` の形を拾う。
#:
#: **木（`scripts` / `src`）も一緒に捕まえること**（2026-09-02 に踏んだ）——
#: 最初は名前だけ拾い、`("src", "scripts")` の順で先に在ったほうを見ていました。
#: `inbox.py` は**両方に在ります**（`scripts/inbox.py` が口・`src/inbox.py` が中身）。
#: すると `scripts/inbox.py --close` の判定に `src/inbox.py` を当てて、
#: そこに書いてある **git の旗**（`--autostash` `--rebase` …）と突き合わせ、
#: 「そんな旗はありません」と**3件 偽陽性**を出しました。
#: **印字が名指ししている道こそが、当てる先です。**
_PRINTED = re.compile(r"(scripts|src)/([a-z_0-9]+)\.py\s+(--[a-z][a-z0-9-]*)")

#: 走査する先（**印字するのはこの2つだけ**）。
_TREES = ("src", "scripts")


def _flags_of(script: Path) -> set[str] | None:
    """その道具が**知っている**旗（1つも無ければ `None`）。

    **本文は実行しません**（`main()` を走らせると API を叩く道具が在る）。
    字面で、**引用符に囲まれた `--…`** を全部 拾います。

    ## `add_argument` だけを見ないこと（2026-09-02 に踏んだ）

    最初は `add_argument("--x")` だけを拾っていました。**2件 偽陽性**が出ます ——
    この repo には `argparse` の**手前で `sys.argv` から抜く**旗が在るからです:

        scripts/retro.py   `sys.argv = [a for a in sys.argv if a != "--alerts-all"]`
        scripts/status.py  同じ形（`--alerts-all`）
        scripts/upload_only.py  `_draft = "--draft" in _argv`

    **どれも実際に撃てます。** 「`argparse` に無い」は「撃てない」ではありません。
    引用符の中に在るかどうかが、**その道具がその字を知っているか**の印です。
    """
    text = script.read_text(encoding="utf-8", errors="replace")
    got = set(re.findall(r'["\'](--[a-z][a-z0-9-]*)["\']', text))
    return got or None


def _printed() -> dict[str, set[tuple[str, str]]]:
    """`{道具のファイル名: {(旗, 印字していた file)}}`。"""
    ## **`#` で始まる行は見ません**（2026-09-02 に踏んだ）——
    ##     `scripts/relay.py` の 479行目は
    ##     「**`--plan` という名前にしないこと**。`python scripts/relay.py --plan` は
    ##       権限判定に弾かれる」という**設計の註**で、印字ではありません。
    ##     聞いているのは「**画面に出す手**が撃てるか」なので、註は対象外です。
    out: dict[str, set[tuple[str, str]]] = {}
    for tree in _TREES:
        for src in sorted((ROOT / tree).rglob("*.py")):
            for line in src.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.lstrip().startswith("#"):
                    continue              # 註 —— 印字ではない
                for tree_of, name, flag in _PRINTED.findall(line):
                    out.setdefault(f"{tree_of}/{name}.py", set()).add(
                        (flag, str(src.relative_to(ROOT))))
    return out


def test_every_printed_flag_exists():
    """**印字した旗が、その道具に実在すること。**（`--pool` で発火した検査）"""
    bad: list[str] = []
    for rel, uses in sorted(_printed().items()):
        target = ROOT / rel
        if not target.exists():
            continue                      # そんな道具が無い ＝ 別の検査の仕事
        have = _flags_of(target)
        if have is None:
            continue                      # 旗を1つも知らない道具 —— 見ない
        for flag, where in sorted(uses):
            if flag not in have:
                bad.append(f"{where} が `{rel} {flag}` と印字していますが、"
                           f"その旗はありません（在るのは {sorted(have)}）")
    assert not bad, "撃てない手を印字しています:\n  " + "\n  ".join(bad)


def test_the_regex_actually_matches_something():
    """**常に緑になる検査を落とすため。** 拾えていること自体を見ます。"""
    got = _printed()
    assert got, "1つも拾えていません（`_PRINTED` が壊れています）"
    assert "scripts/reschedule.py" in got, \
        "`scripts/reschedule.py --…` の印字が1つも拾えていません"


def test_the_check_would_catch_the_real_defect():
    """**発火を確かめる。** 実際に踏んだ `--pool` を、この検査が捕まえること。"""
    have = _flags_of(ROOT / "scripts" / "reschedule.py")
    assert have is not None
    assert "--pool" not in have, \
        "`--pool` が実在するなら、この検査の前提（2026-09-02 の実測）が変わっています"
    assert "--move" in have and "--list" in have
