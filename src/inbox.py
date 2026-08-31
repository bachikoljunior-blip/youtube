#!/usr/bin/env python3
"""運ばれてきた依頼を、**着いた瞬間に**リポジトリへ落とす（受け取り帳）。

    python scripts/inbox.py --open "<運ばれてきた本文>"   # 受け取った直後に打つ
    python scripts/inbox.py                               # 開いているものを見る
    python scripts/inbox.py --close <id> --note "<何をしたか>"

## なぜ要るか（2026-08-16。**同じ直しが3回運ばれ、2回は作業中の死で落ちた**）

親（常駐セッション）はリポジトリを触りません。だから**オーナーの依頼は、
親の文脈の中にしか無い状態で子へ渡ります。** 子が最後まで走れば push されて残る。
**途中で死ぬと、依頼そのものが消えます。**

実際に2回消えました。

    8/15  session_01HYRX3hhdRxUrzoGoee6sQx  `git push` の判定待ちで停止（11ファイル分）
    8/16  session_01BBk417nMz9SjYjctuxecUX  `bash scripts/stop_check.sh` の権限待ちで停止

**どちらも「作業は進んでいたが、push 前に止まった」**です。**そして次に届けられるのは、
親が覚えていた場合だけ** —— 親は同じセッションが続きますが**文脈は要約で消えます。**
3回目が来たのは偶然で、4回目が来る保証はどこにもありません。

## 形（`docs/TRIGGER.md` の「申請中」と同じ形です）

**§6 の「承認待ちで死なないこと」は、同じ穴をこう塞いでいます** ——
「投げる前に、意図を `docs/TRIGGER.md` に『申請中』と書いて push しておく。
止まっても次の回が拾えます」。**受け取りの側にそれが無かっただけ**です。

    受け取った直後   `--open` で1行足して、**その場で commit + push**（数秒）
    やり終えたら     `--close` で閉じる
    途中で死んだら   **開いたまま残る** → 次の子が `status.py` で見る

**`--open` が自分で push します。** 規律に任せると、いちばん忙しい瞬間
（＝依頼を受け取って作業を始めるところ）に「先に push」を思い出す必要があり、
**2回とも、そこを思い出せなかったから落ちました。**

## `retro.py`（持ち越し）との違い

`retro.py` は**日誌の散文**から「2回以上出てきた語」を拾います。
**書かれたものしか拾えません。** 死んだ回は日誌を1行も書いていないので、
**あちらの一覧には最初から入りません**（`src/alerts.py` の「一覧が当たりを
含まないまま育つ」と同じ形の穴。**気づけないほうの落ち方**です）。

こちらは**依頼が着いた時点**で書きます。**作業の成否と独立に残るのが要点**です。

## ID は本文から作ります（**同じ依頼が何回運ばれたかが分かる**）

`--open` を同じ本文で打つと同じ ID になり、**新しい行ではなく「N回目」として積みます。**
3回運ばれたことは、そうやって**機械の側から**言えるようにしてあります
（人が気づいて数えるのを待たない）。言い回しが変わると別 ID になるので、
**運ぶ側が原文をそのまま渡すこと**が効きます（親の手順もそう書いてあります）。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "data" / "inbox.jsonl"
_WS = re.compile(r"\s+")


def session_id() -> str:
    """自分のセッションID。**推測しない**（`run_marker.py` と同じ）。"""
    raw = os.environ.get("CLAUDE_CODE_REMOTE_SESSION_ID", "")
    return ("session_" + raw[4:]) if raw.startswith("cse_") else raw


def item_id(text: str) -> str:
    """本文から作る短い ID。**同じ依頼は同じ ID**（回数を数えるため）。"""
    return hashlib.sha1(_WS.sub(" ", text.strip()).encode("utf-8")).hexdigest()[:8]


def _records(path: Path | None = None) -> list[dict]:
    path = path or LEDGER
    out: list[dict] = []
    if not path.exists():
        return out
    for ln in path.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return out


def _append(rec: dict, path: Path | None = None) -> None:
    path = path or LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def items(path: Path | None = None) -> list[dict]:
    """ID ごとに畳んだ一覧。**新しいものが後ろ**。"""
    by_id: dict[str, dict] = {}
    for rec in _records(path):
        iid = rec.get("id")
        if not iid:
            continue
        if rec.get("kind") == "open":
            cur = by_id.get(iid)
            if cur is None:
                by_id[iid] = {
                    "id": iid,
                    "text": rec.get("text", ""),
                    "source": rec.get("source", ""),
                    "first_at": rec.get("at", ""),
                    "last_at": rec.get("at", ""),
                    "deliveries": 1,
                    "closed": False,
                    "note": "",
                    "closed_at": "",
                }
            else:
                cur["deliveries"] += 1
                cur["last_at"] = rec.get("at", cur["last_at"])
                # **一度閉じたものが再び運ばれたら、開き直す。**
                # 閉じたはずのものがまた来るのは「直っていない」ことの証拠で、
                # **黙って重複扱いにすると、いちばん見たい形が消えます。**
                if cur["closed"]:
                    cur["closed"] = False
                    cur["reopened"] = True
        elif rec.get("kind") == "close" and iid in by_id:
            by_id[iid]["closed"] = True
            by_id[iid]["note"] = rec.get("note", "")
            by_id[iid]["closed_at"] = rec.get("at", "")
    return list(by_id.values())


def open_items(path: Path | None = None) -> list[dict]:
    return [it for it in items(path) if not it["closed"]]


def add(text: str, source: str = "owner", path: Path | None = None) -> dict:
    """受け取った依頼を1行足す。**同じ本文なら同じ ID に積む。**"""
    text = text.strip()
    if not text:
        raise ValueError("本文が空です。**原文をそのまま渡すこと。**")
    rec = {
        "at": datetime.now(JST).isoformat(timespec="seconds"),
        "session": session_id(),
        "kind": "open",
        "id": item_id(text),
        "source": source,
        "text": text,
    }
    _append(rec, path)
    return rec


def close(prefix: str, note: str, path: Path | None = None) -> dict:
    """開いている依頼を閉じる。ID は先頭一致でよい。"""
    hits = [it for it in open_items(path) if it["id"].startswith(prefix)]
    if not hits:
        raise KeyError(prefix)
    if len(hits) > 1:
        raise ValueError(f"ID が絞れません: {', '.join(h['id'] for h in hits)}")
    rec = {
        "at": datetime.now(JST).isoformat(timespec="seconds"),
        "session": session_id(),
        "kind": "close",
        "id": hits[0]["id"],
        "note": note.strip(),
    }
    _append(rec, path)
    return rec


def render(path: Path | None = None, show_all: bool = False) -> str:
    """`status.py` が出す形。**開いているものが無ければ1行で終わる。**"""
    rows = items(path) if show_all else open_items(path)
    head = "\n=== 受け取り帳（**運ばれてきて、まだ閉じていない依頼**）==="
    if not rows:
        return head + "\n  開いているものはありません"
    lines = [head, f"  **{len(rows)}件。この回で閉じるか、閉じない理由を JOURNAL に書くこと。**"]
    for it in sorted(rows, key=lambda r: r["first_at"]):
        n = it["deliveries"]
        mark = f"×{n}回運ばれた" if n > 1 else "1回目"
        if it.get("reopened"):
            mark += "・**一度閉じたのに再び来た**"
        body = _WS.sub(" ", it["text"])[:120]
        state = "済" if it["closed"] else "開"
        lines.append(f"  [{state}] {it['id']}  {it['first_at'][5:16]}  {mark}")
        lines.append(f"        {body}")
    lines.append("  閉じるとき: `python scripts/inbox.py --close <id> --note \"<何をしたか>\"`")
    return "\n".join(lines)


#: **セッションごとの使い捨て枝**の名前の形（`.claude/worktrees/<名前>/`）。
#: ワークツリーに隔離されたサブは、この名前の枝の上で走ります。
#: **ここへ push しても、誰も読みません。**
SCRATCH_BRANCH_PREFIX = "worktree-agent-"


def is_scratch_branch(name: str) -> bool:
    """**そこへ押しても誰も読まない枝か。**（2026-08-31 に足した）

    実測 2026-08-31: `git ls-remote --heads origin` に
    **`worktree-agent-*` が 26本**。`inbox.py --open` を撃ったサブのぶんです。
    **「origin にも在るか」では止まりません** —— 1回 押した時点で
    その枝は origin に出来るので、**2回目からは「在る」ので通ります。**
    （この検査を書いた回が、まさにそれを踏みました。）

    **止めるのは名前の形のほうです。**
    """
    return bool(name) and name.startswith(SCRATCH_BRANCH_PREFIX)


def in_worktree(root: Path | None = None) -> bool:
    """**この作業コピーは、隔離されたワークツリーか。**

    `run_marker.worktree_tag()` と同じ見方（**環境変数ではなく置き場所**）。
    """
    return ".claude/worktrees/" in (str(root or ROOT).replace("\\", "/") + "/")


def git_save(message: str, paths: "list[Path] | None" = None) -> tuple[bool, str]:
    """指定したファイルだけを commit して push する。**ここが要点です。**

    **手元のファイルに書いただけでは、コンテナが消えた時点で無くなります。**
    他の変更を巻き込まないよう、**渡されたパスだけを指定して commit** します
    （`git commit -- <path>` は index ではなく作業ツリーのそのパスを見ます）。
    `paths` を省くと受け取り帳（`data/inbox.jsonl`）1本です。

    失敗しても例外にしません —— **依頼を受け取った直後に道具が落ちるのが
    いちばん高い**ので、**大きく警告して先へ通します。**

    ##### **なぜ受け取り帳の外にも効かせたか**（2026-08-31 22:xx に踏んだ）
    #
    # オーナー指摘 e6d3be89「**失敗したならそこだけ直すんじゃなくて応用しないの？**」。
    #
    # **実測**: 09/01 22:00 に出る `UIWHsypOPPg` の控え
    # （`data/critique_queue/UIWHsypOPPg.json` と `.thumb.jpg`）が
    # **git に1バイトも残っていません。** `scripts/upload_only.py` は
    # `critique_queue.stash()` を確かに呼んでおり、失敗すれば大きく印字して
    # 終了コード 1 を返す作りです。**落ちてはいません** —— コンテナの
    # ディスクに書けたあと、その回の commit（`f7d3171e`）が
    # `data/api_calls.jsonl` `data/day_quota.jsonl` `data/published_bars.json`
    # `data/uploaded.jsonl` の**4本しか拾わなかった**だけです。
    # コンテナが畳まれて、控えは消えました。
    #
    # **これは「押し忘れ」ではなく、受け取り帳とまったく同じ穴です** ——
    # 「書いた」と「残った」の間に、**人の記憶と手写しに依存する門**がある。
    # `docs/trigger_main.md` §1 が受け取り帳について書いていることが、
    # そのまま当てはまります: 「**押した後なら、この子が途中で死んでも、
    # 次の子が拾えます。**」
    #
    # **失ったもの**（699本中4本だけですが、当たったのが悪い）:
    #   - 読み上げ全文 …… 出る前に中身を確かめる唯一の材料（`docs/CRITIQUE.md`）
    #   - サムネイルの bytes …… `refresh_thumbnail.py --missing` が押す先。
    #     **控えが無い本は一覧に出ないので、押す手そのものが空振りします**
    #     （受け取り帳 `e1ea4c96` の (1) が、まさにこれを頼んでいました）
    #
    # **覆る条件**: 投稿の口が控えを YouTube 側から引き直せるようになったら、
    # ここで押す必要はありません（いまは読み上げ文もサムネの原本も手元にしかない）。
    # 検査は `tests/test_stash_is_pushed.py`。
    """
    targets = [LEDGER] if paths is None else list(paths)
    rels = [str(Path(p).resolve().relative_to(ROOT)) for p in targets]

    def _git(*argv: str, timeout: int = 60) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(ROOT), *argv], check=True,
                              capture_output=True, timeout=timeout)

    def _target_branch() -> str | None:
        """押す先の枝を決める。**分離 HEAD でも決まること**が要点です。

        `docs/trigger_main.md` §0 は「分離 HEAD のまま1周まわしてよい」と
        勧めています（枝名に合わせにいって3日前の作業木へ降りた事故のあと）。
        **その形だと、引数なしの `git push` は必ず落ちます** ——
        `You are not currently on a branch`。`git pull --rebase` も同じです。
        **2026-08-19 に実測**: `--open` と `--close` の両方がこれで押せず、
        「手で push すること」だけが出ていました。**依頼の受け渡し経路そのもの**なので、
        気づかずに死ぬと依頼が消えます（この道具が塞ごうとしている穴）。
        """
        ##### **枝の上に居ても、その枝が origin に無ければ使わないこと**
        #####                                       （2026-08-31 に踏んだ）
        #
        # **ワークツリーに隔離されたサブは、`worktree-agent-<id>` という
        # 自分だけの枝の上に居ます。** ここは長らく `symbolic-ref` の返りを
        # そのまま押し先にしていたので、**その名前の枝が origin に新しく作られ、
        # 誰も読まない所へ push して「push まで済み」と印字していました。**
        #
        # **実測 2026-08-31**: `git ls-remote --heads origin` に
        # **`worktree-agent-*` が 26本**。この道具を撃ったサブのぶんです。
        #
        # **これは、この道具が塞ごうとしている穴そのもの**です ——
        # `docs/trigger_main.md` §1 は「押した後なら、この子が途中で死んでも、
        # 次の子が `status.py` で見つけます」と書いていますが、
        # **ワークツリーのサブでは、その保証がずっと成り立っていませんでした。**
        # 分離 HEAD のほうは 2026-08-19 に直っており、**枝の上に居る形だけが
        # 残っていました**（`symbolic-ref` が成功するので、下の探索に落ちない）。
        #
        # **直し方**: `symbolic-ref` が返した名前でも、**origin にその枝が
        # 無ければ使わない。** 下の「HEAD の祖先である origin の枝」を探す道は
        # 分離 HEAD 用にすでに在り、**そのまま正しい答えを出します。**
        #
        # **覆る条件**: サブが自分の枝を origin にも持つ運用になったら、
        # この確かめは要りません（そのときは `--set-upstream` の有無で分けること）。
        # 検査は `tests/test_inbox_push_target.py`。
        try:
            name = (_git("symbolic-ref", "--quiet", "--short", "HEAD").stdout
                    .decode("utf-8", "replace").strip())
            if name and not is_scratch_branch(name):
                try:
                    _git("show-ref", "--verify", "--quiet",
                         f"refs/remotes/origin/{name}")
                    return name
                except subprocess.CalledProcessError:
                    pass  # origin に無い枝。下の探索へ落とす
        except subprocess.CalledProcessError:
            pass  # 分離 HEAD。origin 側から探す
        try:
            out = _git("for-each-ref", "--format=%(refname:short)", "refs/remotes/origin")
        except subprocess.CalledProcessError:
            return None
        names = [n.strip() for n in out.stdout.decode("utf-8", "replace").splitlines() if n.strip()]
        cands = []
        for full in names:
            if not full.startswith("origin/") or full == "origin/HEAD":
                continue
            short = full[len("origin/"):]
            # **使い捨て枝は候補にしない。** 一度でも押されていると
            # HEAD の祖先になるので、**ここで弾かないと自分の枝を選び直します**
            # （2026-08-31 に踏んだ。origin に 26本 溜まっていた）。
            if is_scratch_branch(short):
                continue
            try:  # その枝が HEAD の祖先なら、HEAD はその枝の続き
                _git("merge-base", "--is-ancestor", full, "HEAD")
            except subprocess.CalledProcessError:
                continue
            cands.append(short)
        if not cands:
            return None

        ##### **選ぶのは「HEAD にいちばん近い枝」です**（2026-08-31 に直した）
        #
        # ここは長らく **名前のアルファベット順**（`main` だけ最後）でした。
        # **祖先になる枝は、たいてい何本もあります** —— 古い作業枝も `main` も
        # 全部 HEAD の祖先なので、**名前で選ぶのはくじ引き**です。
        #
        # 実測 2026-08-31（この回・ワークツリーのサブ）: 祖先は4本 ——
        # `agent/write-access-test-20260806` / `claude/monthly-income-...` /
        # **`claude/youtube-auto-post-revenue-ggedij`**（いま走っている枝）/ `main`。
        # **アルファベット順は `agent/write-access-test-20260806` を選びます** ——
        # 8月6日の書き込み試験の枝で、**誰も読みません。**
        #
        # **「いちばん近い」＝ その枝から HEAD までの commit がいちばん少ない。**
        # いま走っている枝は、こちらの commit のぶんしか離れていません。
        # 古い枝や `main` は何百も離れます。**名前を知らなくても決まります。**
        #
        # **覆る条件**: 同じ距離の枝が2本 出たら、そこは名前で決めるしかない
        # （`main` を最後にする既定はそのために残してあります）。
        def _distance(short: str) -> int:
            try:
                out = _git("rev-list", "--count", f"origin/{short}..HEAD")
                return int(out.stdout.decode("utf-8", "replace").strip() or 0)
            except (subprocess.CalledProcessError, ValueError):
                return 1 << 30
        return sorted(cands, key=lambda n: (_distance(n), n == "main", n))[0]

    try:
        _git("add", "--", *rels)
        _git("commit", "-m", message, "--", *rels)
        branch = _target_branch()
        refspec = ["origin", f"HEAD:{branch}"] if branch else []
        try:
            out = _git("push", *refspec, timeout=180)
        except subprocess.CalledProcessError:
            # **兄弟が先に押していると、1回目は必ず弾かれます**（同じ枝を複数の子が使う）。
            # ここで諦めると「手で押してください」が残り、**そのまま死ねば消えます** ——
            # 塞ごうとしている穴そのものなので、**1回だけ乗せ直して押し直す。**
            # `--autostash` は作業中の変更を巻き込まないため（受け取りは作業の最中に来ます）。
            # **`pull` を使わないこと** —— 分離 HEAD では枝名を要求して落ちます。
            if branch:
                _git("fetch", "origin", branch, timeout=180)
                _git("rebase", "--autostash", "FETCH_HEAD", timeout=180)
            else:
                _git("pull", "--rebase", "--autostash", timeout=180)
            out = _git("push", *refspec, timeout=180)
        return True, out.stdout.decode("utf-8", "replace")[-400:]
    except Exception as exc:  # noqa: BLE001 —— 種類を問わず「押せなかった」で同じ
        detail = ""
        if isinstance(exc, subprocess.CalledProcessError):
            detail = exc.stderr.decode("utf-8", "replace")[-400:]
        return False, f"{type(exc).__name__}: {detail or exc}"
