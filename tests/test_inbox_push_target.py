"""**受け取り帳の push 先が、誰も読まない枝になっていないこと。**（2026-08-31）

## なぜ要るか —— この道具が塞ごうとしている穴が、この道具に開いていた

`docs/trigger_main.md` §1 はこう書いています ——
「`--open` は `data/inbox.jsonl` に1行足して、**その場で commit と push まで**やります。
**押した後なら、この子が途中で死んでも、次の子が `status.py` で見つけます。**」

**ワークツリーに隔離されたサブでは、その保証が成り立っていませんでした。**

サブは `worktree-agent-<id>` という**自分だけの枝**の上に居ます。
`src/inbox._target_branch()` は `git symbolic-ref --short HEAD` の返りを
そのまま押し先にしていたので、**その名前の枝が origin に新しく作られ、
誰も読まない所へ push して「push まで済み」と印字していました。**

**実測 2026-08-31**: `git ls-remote --heads origin` に
**`worktree-agent-*` が 26本**。この道具を撃ったサブのぶんです。
同じ回に `--close` / `--open` を撃ったあと `git log origin/<本流>` を見ると、
**その2つの commit がどこにも無い**ところで気づきました。

分離 HEAD のほうは 2026-08-19 に直っています（`for-each-ref` で
「HEAD の祖先である origin の枝」を探す道）。**枝の上に居る形だけが
残っていました** —— `symbolic-ref` が成功するので、その探索に落ちない。

**直し方**: `symbolic-ref` が返した名前でも、**origin にその枝が無ければ使わない。**
探索の道はすでに在り、**そのまま正しい答えを出します。**

**残った 26本 の枝は消していません**（オーナー与件4「消さなくて良いよ時間かかるなら
わざわざ」の姿勢。他の回がまだ押している最中かもしれないので、**触らない**）。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import inbox  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "inbox.py"


def _git(*argv: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *argv],
                          capture_output=True, text=True).stdout.strip()


def test_使い捨て枝は名前の形で弾く():
    """**これがこの検査の本体です。**

    **「origin にも在るか」では止まりません** —— 1回 押した時点で
    その枝は origin に出来るので、**2回目からは「在る」ので通ります。**
    この検査を書いた回が、まさにそれを踏みました（`--close` と `--open` を
    撃ったあとに気づいたので、自分の枝はもう origin に在った）。
    **止めるのは名前の形のほうです。**
    """
    assert inbox.is_scratch_branch("worktree-agent-aebef17f0039f54be") is True
    assert inbox.is_scratch_branch("claude/youtube-auto-post-revenue-ggedij") is False
    assert inbox.is_scratch_branch("main") is False
    assert inbox.is_scratch_branch("") is False

    src = SRC.read_text(encoding="utf-8")
    # **2か所とも弾くこと** —— `symbolic-ref` の側と、祖先の探索の側。
    # 探索の側を空けると、一度 押された自分の枝が祖先になって選び直されます。
    assert src.count("is_scratch_branch(") >= 3, (
        "`symbolic-ref` の側と祖先の探索の側、**両方**で弾くこと"
    )


def test_symbolic_ref_の返りを_origin_に無いまま使わない():
    """`show-ref --verify refs/remotes/origin/<name>` を通してから返すこと。"""
    src = SRC.read_text(encoding="utf-8")
    assert "refs/remotes/origin/{name}" in src, (
        "`symbolic-ref` の返りを、origin にその枝が在るか確かめずに"
        "押し先にしています。**ワークツリーのサブは、誰も読まない枝へ押します。**"
    )
    i_sym = src.index('"symbolic-ref"')
    i_chk = src.index("refs/remotes/origin/{name}")
    assert i_sym < i_chk, "確かめが `symbolic-ref` より前にあります"


def test_押し先は_HEAD_にいちばん近い枝():
    """**名前で選ばないこと。** 祖先はたいてい何本もあります。

    実測 2026-08-31（この回・ワークツリーのサブ）: 祖先は4本で、
    アルファベット順は `agent/write-access-test-20260806`（8月6日の
    書き込み試験の枝）を選んでいました。距離で選ぶと **0** の
    `claude/youtube-auto-post-revenue-ggedij` になります。
    """
    src = SRC.read_text(encoding="utf-8")
    assert '"rev-list", "--count"' in src, "距離を測っていません"
    assert "_distance(n)" in src, "並べ替えの第1鍵が距離になっていません"


def test_分離HEADの道を消していない():
    """2026-08-19 の直しを巻き戻さないこと。**両方 要ります。**"""
    src = SRC.read_text(encoding="utf-8")
    assert "for-each-ref" in src
    assert "merge-base" in src and "--is-ancestor" in src


def test_実物の押し先が_origin_に在る枝であること():
    """**この回そのもので確かめる。** 文面ではなく、いま返る値を見ます。"""
    # `git_save` の中の私関数なので、同じ手順をここで組み直さずに撃つ ——
    # `git_save` を呼ぶと commit してしまうため、押し先だけを別に解きます。
    head = _git("symbolic-ref", "--quiet", "--short", "HEAD")
    remotes = _git("for-each-ref", "--format=%(refname:short)", "refs/remotes/origin")
    if not remotes:
        return  # origin を持たない作業コピー（この検査は言うことがない）
    names = {n.strip() for n in remotes.splitlines() if n.strip()}
    if head and not inbox.is_scratch_branch(head) and f"origin/{head}" in names:
        return  # 共有の枝の上に居る（親の形）
    # ここへ来るのは、ワークツリーのサブか分離 HEAD。
    # **押し先は「HEAD の祖先である、使い捨てでない origin の枝」でなければならない。**
    cands = []
    for full in sorted(names):
        if not full.startswith("origin/") or full == "origin/HEAD":
            continue
        short = full[len("origin/"):]
        if inbox.is_scratch_branch(short):
            continue
        r = subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor",
                            full, "HEAD"], capture_output=True)
        if r.returncode == 0:
            cands.append(short)
    assert cands, (
        "押し先になる枝が1つも見つかりません。"
        "**この形で `inbox.py --open` を撃つと、依頼が誰にも届きません。**"
    )
    assert not any(inbox.is_scratch_branch(c) for c in cands), (
        "使い捨て枝が候補に残っています。**誰も読まない所へ押します。**"
    )


def test_押せなかったときは_偽を返す():
    """**「push まで済み」を、押せていないのに印字しないこと。**

    `git_save` は失敗を握りつぶさず `(False, 理由)` を返す約束です
    （`scripts/inbox.py` はそれを見て「手で push すること」と言います）。
    """
    src = SRC.read_text(encoding="utf-8")
    assert "return False," in src, "失敗を偽で返していません"
    assert "return True," in src


def test_受け取り帳の1ファイルだけを積む():
    """他の変更を巻き込まないこと（受け取りは作業の最中に来ます）。"""
    src = SRC.read_text(encoding="utf-8")
    assert '_git("commit", "-m", message, "--", rel)' in src, (
        "パス指定の commit をやめています。**作業中の変更を巻き込みます。**"
    )
    assert inbox.LEDGER.name == "inbox.jsonl"
