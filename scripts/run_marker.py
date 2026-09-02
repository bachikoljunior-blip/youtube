#!/usr/bin/env python3
"""子（毎時の回）が「実際に走った」ことを1行残す。

    python scripts/run_marker.py --write   # 子が最初に打つ
    python scripts/run_marker.py           # 直近の回がいつだったかを見る

## なぜ要るか

2026-08-10、オーナーの指示で定期実行を親子方式にした。

    親（毎時 :09・常駐）  **子を1つ立てて、終わった子を畳むだけ。他は何もしない**
    子（毎回あたらしい）  **その回の仕事を全部やって、自分を archive する**

> 毎回新しいセッション立ててそこで実行、終わったらアーカイブ
> **ここでしてた作業を全部子セッションにやらせる**

長いセッションで判断が雑になるのを避けるため。

**このファイルは「回が本当に周っているか」の記録です。**
親は使いません（親はリポジトリを触らない）。**読むのは子と、人。**

## 親の重複防止に使わないこと（**一度そう作って外した**）

最初は「子が印を打ち、親がそれを読んで二重に立てない」形にしていた。**穴があった。**

    11:27  親が子を立てる。子は**自分の器の中で**印を打つ
    12:09  親が発火。**その印はまだ push されていないので見えない**
           → 「子は走っていない」と読んで **2人目を立てる**

**子の印はリポジトリ経由なので、子が最後に push するまで親に届かない。**
走っている最中がちょうど見えない。

そのあと「親が立てた側で書く」形にしたが、**それも外した。**
親がリポジトリに commit/push する時点で、**親が働いている**。
オーナーの指示は「全部子にやらせる」なので、親は repo を触らない。

**いまの重複防止は `list_sessions` の `parent_session_id`。**
親は自分の子だけを正確に絞れるので、記録が要らない。

## だから、この記録の用途は1つだけ

**立ってはいるが、どの子も走り終えていない**という状態を見つけること。
親から見ると子は立っているので正常に見える。**周が回っているかは、
子が自分で残した印でしか分からない。**
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# **`src/` を読めるようにする**（`retro.py` と同じ形）。`levers` は腕の語彙だけを持つ
# 純粋な module で、API も設定も見ません。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import levers, resume_gate  # noqa: E402

JST = timezone(timedelta(hours=9))

# 定期実行の間隔（分）。**実物は `list_triggers` で見ること。**
# ここは空きを警告するしきい値を出すためだけに持っています。
# 2026-08-15: 親が毎時（cron `9 * * * *`）になったので 60。
INTERVAL_MIN = 60
MARKS = Path(__file__).resolve().parent.parent / "data" / "runs.jsonl"
KEEP = 500
# **潰した宣言の位置合わせに使う目盛り。**（2026-08-16 に足した。理由は `ship()`）
# 宣言した時点で日誌が何行あったかを一緒に残すと、`retro.py` の
# 「宣言より前の言及だけ落とす」がそのまま効きます（あちらは行番号で見ています）。
JOURNAL = Path(__file__).resolve().parent.parent / "docs" / "JOURNAL.md"

# **常駐の親。ここからの印は数えない。**
#
# 親は普段リポジトリを触らないので打つ機会が無いはずだが、
# 打てば「周が回っている」に見えてしまう。**異常を隠す方向の間違いなので、
# 規律ではなく機械で外す。**
#
# **親は交代します**（重くなったら新しい親に移す）。古いIDを消さずに足すこと。
# 名簿は `config/parents.txt`（`stop_check.sh` と `goal_reminder.sh` も同じものを読む）。
# **1か所にしてあるのは、増えたときに片方だけ直す事故を避けるため**です。
_PARENTS_FILE = Path(__file__).resolve().parent.parent / "config" / "parents.txt"


def _parents() -> set[str]:
    if not _PARENTS_FILE.exists():
        return set()
    return {
        ln.strip() for ln in _PARENTS_FILE.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.startswith("#")
    }


PARENT_SESSIONS = _parents()


def session_id() -> str:
    """自分のセッションID。**推測しないこと。**

    `list_sessions` から名前で探すと、似た名前の別セッションを掴む事故になる
    （姉妹ループが同じ注意を書いている）。環境変数が正本。
    """
    raw = os.environ.get("CLAUDE_CODE_REMOTE_SESSION_ID", "")
    return ("session_" + raw[4:]) if raw.startswith("cse_") else raw


def worktree_tag() -> str:
    """作業コピー（worktree）で走っているなら、その名前。走っていなければ空。

    **2026-08-25 の夜に、毎時の回は「親が立てる子セッション」から
    「親セッションの中のサブエージェント」へ移りました**（`docs/trigger_parent.md`）。
    `create_session` が人のタップを待つので、夜のあいだ鎖が止まったためです。

    **サブエージェントは、親と同じ `CLAUDE_CODE_REMOTE_SESSION_ID` を持ちます。**
    環境変数は1つのコンテナに1つしかなく、サブエージェントはその中の
    別スレッドだからです。つまり `session_id()` だけで見ると、
    **周を回している当人が「親」に見えます。**

    実測（2026-08-25 22:0x、この関数を足した回）——
    `data/runs.jsonl` の 378件の ship のうち **14件が親IDで書かれており**、
    `_records()` の親フィルタが**丸ごと落としていました**。落ちた中には
    「在庫の穴(08/30)へ長尺2本を予約」「長尺2本追加＋同calc連続4本を組み替え」
    という **upload 2件**が入っています。`run_marker.py`（引数なし）は
    それを1行も出さないまま「**周は回っています**」と印字しました。
    **8/25 夜以降は全部の回が親IDになるので、放っておくと 100% 落ちます。**

    そして `--write` のほうは、そもそも「親からは印を付けません」で
    **拒否されます** —— 印が無い回は `stop_check.sh` が黙って通し、
    `sessions_compact.py` は「印を1つも残していない回」として数えます。
    **周は回っているのに、機械からは1つも見えない**のがいまの姿です。

    直し方は、名簿を触ることでも環境変数を増やすことでもありません ——
    **サブエージェントは必ず自分専用の作業コピーで走る**ので、
    その道に名前が書いてあります:

        /home/user/youtube/.claude/worktrees/agent-a06c647462c3c1fb0
                                   ~~~~~~~~~ ここ

    **親は共有チェックアウト（`/home/user/youtube`）で走る**ので空になり、
    親の足切りはそのまま効きます。**IDの直書きより腐りません。**
    """
    # **`MARKS` から辿らないこと。** あちらは検査が tmp へ差し替えます ——
    # 差し替えられた瞬間に「作業コピーではない」に化けて、判定が検査ごと嘘になります。
    parts = Path(__file__).resolve().parent.parent.parts
    for i in range(len(parts) - 2):
        if parts[i] == ".claude" and parts[i + 1] == "worktrees":
            return parts[i + 2]
    return ""


# 一時置き場の親。**検査が差し替えるので定数にしてあります**（`/tmp` 直書きだと
# 検査が本物の `/tmp` を掘りに行き、きょうだいの置き場に触ります）。
_TMP = Path("/tmp")


def scratch_dir(make: bool = True) -> str:
    """**この回だけの一時置き場**を掘って、その道を返す。無ければ空。

    ## なぜ道具の側に置くか（2026-08-29 23:xx に踏んだ。**これで3回目**）

    `docs/trigger_main.md` の §「サブの回は、scratchpad をきょうだいと
    共有しています」は 2026-08-26 から**正しい逃げ方をそのまま書いています**:

        mkdir -p <scratch>/<自分のID の末尾6文字>

    **それでも踏みます。** この回は `status.py`（40〜60秒）の出力を
    共有の `<scratch>/status.txt` へ落とし、**読んでいる途中で
    きょうだいに上書きされました**（266行 → 24行）。
    一時置き場を覗くと、`a04186` `a50d3c` … と**きょうだいの掘った
    ディレクトリが40個 並んでいる隣に**、`JOURNAL_live.md`
    `177d27b0.html` のような**共有の直下に書かれたファイル**が残っています
    —— つまり**掘った回と掘らなかった回が混ざっています。**

    この repo の他の場所が同じ形について既に答を出しています ——
    **「人の記憶と手写しに依存する門は、この輪では毎回落ちる側」**
    （`batch_build.slots()` の註）。だから**手順ではなく道具に持たせます。**
    `--write` は §1 でその回のいちばん最初に撃たれるので、
    **何かを書く前に道が出ます。**

    道の作り: 一時置き場は `CLAUDE_CODE_SESSION_ID` から作られていて、
    **同じ親から立ったサブは全員 同じ ID を持ちます**（`worktree_tag()` の註と
    同じ理由 —— 環境変数はコンテナに1つ）。だから**セッションIDでは分かれません。**
    分かれるのは作業コピーの名前のほうなので、その末尾6文字で掘ります。

    **覆る条件**: 一時置き場の場所が環境変数で降ってくるようになったら、
    glob をやめてそれを読むこと。glob が1件も当たらない置き方（検査・親）では
    **空を返して黙ります** —— ここで落ちると、印そのものが打てなくなります。
    検査は `tests/test_run_marker_scratch.py`。
    """
    tag = worktree_tag()
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if not tag or not sid:
        return ""
    hits = sorted(_TMP.glob(f"claude-*/*/{sid}/scratchpad"))
    if not hits:
        return ""
    out = hits[0] / tag[-6:]
    if make:
        try:
            out.mkdir(parents=True, exist_ok=True)
        except OSError:
            return ""
    return str(out)


def actor_id() -> str:
    """**この回を回している当人**の識別子。印に残すのはこちら。

    素のセッションIDではなく、作業コピーで走っているならその名前を足します
    （`session_017yMB…#agent-a06c647462c3c1fb0`）。理由は2つ:

    1. **親IDのまま書くと、親フィルタに落とされます**（`worktree_tag()` の実測）
    2. **同じ親から2つのサブエージェントが同時に走ります。**
       素のIDだと2人が同一人物になり、`--closes-add` の
       「この回の最後の ship」が**隣の回の ship を掴みます**

    素のセッションIDが要る側（`list_sessions` と突き合わせるなど）は
    `session_id()` を使うこと。**`#` から前がそれです。**
    """
    sid = session_id()
    tag = worktree_tag()
    if not tag:
        return sid
    return f"{sid}#{tag}" if sid else tag


def is_parent() -> bool:
    """**常駐の親そのものか。** 作業コピーで走っている回は親ではありません。

    親が repo を触る回（引き継ぎ・手直し）は共有チェックアウトなので、
    ここは今までどおり真になります。
    """
    return not worktree_tag() and session_id() in PARENT_SESSIONS


def _records() -> list[dict]:
    out = []
    if not MARKS.exists():
        return out
    for ln in MARKS.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        try:
            rec = json.loads(ln)
        except json.JSONDecodeError:
            continue
        # **親の足切りは「心音」にだけ効かせます**（2026-08-25 22:0x に狭めた）。
        #
        # ここが落としていたのは `kind` を問わない全部でした。落とす狙いは
        # 「親が居るだけで**周が回っているように見える**」を潰すことなので、
        # 効かせる先は `start`（心音）です。
        #
        # **`ship` まで落とすと、出したものが消えます。** 実測：8/25 夜に
        # サブエージェントへ移ってから、回は親と同じIDを持つようになり、
        # **14件の ship が丸ごと見えなくなっていました** —— そのうち2件は
        # 「在庫の穴(08/30)へ長尺2本を予約」「長尺2本追加」で、**upload です。**
        # そして `src/levers.py` の `recent()` は元から `ship` を落としていません ——
        # **同じ台帳を読む2つが、違うものを見ていました。** 揃えるほうを取ります。
        #
        # **覆る条件**: 親が `--ship` を打つようになったら（`config/parents.txt` は
        # 打つなと書いています）、ここは嘘を通します。そのときは
        # `actor_id()` に `#` が無い親IDの ship だけを落とすこと。
        if rec.get("kind") == "start" and rec.get("session") in PARENT_SESSIONS:
            continue
        out.append(rec)
    return out


def _append(rec: dict) -> str:
    MARKS.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(rec, ensure_ascii=False)
    old = [x for x in (MARKS.read_text(encoding="utf-8").splitlines()
                       if MARKS.exists() else []) if x.strip()]
    MARKS.write_text("\n".join((old + [line])[-KEEP:]) + "\n", encoding="utf-8")
    return line


CLAIM_KIND = "claim"

#: **「いま取りかかっている」が新鮮だと見なす分数。**
#: 1周は 15〜30分（`docs/trigger_main.md`）。倍に取って、直前の回のぶんまで見せます。
CLAIM_WINDOW_MIN = 60


def claims(window_min: int = CLAIM_WINDOW_MIN, me: str | None = None) -> list[dict]:
    """**直近 window_min 分に、自分以外が「取りかかる」と書いたもの。**

    ## なぜ要るか（2026-08-26 21:xx に、この回が 30分 払った）

    この回は `scripts/drift.py` を 30分 かけて直し、push の直前に
    **きょうだいが同じ 20分間に同じ所を直していた**ことを知りました
    （merge conflict）。あちらのほうが広かったので**こちらのぶんを捨てています。**

    **fetch では防げません。** 着手前に fetch は撃っていて、
    そのとき向こうはまだ push していませんでした。**同時に走っています。**

    そして**当たるべくして当たっています** —— `retro.py` の持ち越し1位と
    `status.py` の「[!] 外れています」は**どの回にも同じ形で見えている**ので、
    **上位の1件は複数の回が同時に取りにいきます。** 直近7日の周は 115、
    そのうち ship は 305件。**重なりは事故ではなく、既定の状態です。**

    **`data/runs.jsonl` に置くのは、口が既に在るからです**
    （`.gitattributes` の `merge=union` で、追記どうしは黙って両方残ります）。
    読む場所を `--write`（§1・**その回のいちばん最初のコマンド**）にしたのは、
    **何をやるか決める前**でないと意味がないからです。

    **これは予約ではありません。** 見て、避けるか、重ねるかを決めるのはこちらです
    （同じ所を2つの回が直すのが正しい場面もあります —— 08-26 の
    `--shrink` は、きょうだいが見つけなければ間違ったまま走っていました）。
    """
    me = me if me is not None else (actor_id() or "")
    cut = datetime.now(JST) - timedelta(minutes=window_min)
    out = []
    for r in _records():
        if r.get("kind") != CLAIM_KIND:
            continue
        if str(r.get("session") or "") == me:
            continue
        try:
            at = datetime.fromisoformat(str(r.get("at")))
        except ValueError:
            continue
        if at.tzinfo is None:
            at = at.replace(tzinfo=JST)
        if at >= cut:
            out.append(r)
    return out


def recent_ships(window_min: int = CLAIM_WINDOW_MIN, me: str | None = None) -> list[dict]:
    """**直近 window_min 分に、自分以外が実際に出したもの。**

    ## なぜ `claims()` だけでは足りないか（2026-08-27 19:0x に踏んだ）

    `--claim` は**任意**です。`--ship` は**必須**です（§4 の最低ライン）。
    だから「claim を打たずに走っているきょうだい」は、`claims()` から
    **1件も見えません。**

    実測（この回）: `run_marker.py --write` は
    **「直近60分の claim: 0件」**を返しました。同じ時刻の `data/runs.jsonl` には、
    **18:0x〜18:4x にきょうだいの ship が4件**（長尺の在庫を掘る回）ありました。
    この回はそれを見ずに「在庫の底」を claim し、**中身を捨てています。**

    **`claims()` が見ているのは意図で、ここが見ているのは実物です。**
    重なりを避けるのに効くのは、**実際に触られた所**のほう。

    **覆る条件**: `--claim` が全部の回で打たれるようになったら、この2つは
    同じものを指します（そのときは `claims()` だけで足ります）。
    **数え方は写していません** —— どちらも `_records()` の同じ行を読み、
    `kind` だけが違います。
    """
    me = me if me is not None else (actor_id() or "")
    cut = datetime.now(JST) - timedelta(minutes=window_min)
    out = []
    for r in _records():
        if r.get("kind") != "ship":
            continue
        if str(r.get("session") or "") == me:
            continue
        try:
            at = datetime.fromisoformat(str(r.get("at")))
        except ValueError:
            continue
        if at.tzinfo is None:
            at = at.replace(tzinfo=JST)
        if at >= cut:
            out.append(r)
    return out


DOC_FOR_INDEX = "docs/trigger_main.md"


def _doc_index_lines(doc: str = DOC_FOR_INDEX) -> list[str]:
    """**手順書の当てどころ**（節の名前 → 行番号）を、読む前に出す。

    ## なぜ §1 で出すのか（2026-09-01 に足した）

    `retro.py` の (a2) 問い1（この回でいちばん時間を食ったのはどこか）を縦に読むと、
    **直近9件のうち6件、直近5件は5件とも「手順の読み」か「何を出すか決めるところ」**
    でした。`docs/trigger_main.md` は **1日 約190行**増え、**名前から場所は引けません。**

    あちらの「読む前に、この1行を撃つこと」は、**行番号の表を手で貼ろうとして
    2回 失敗した跡**です —— 貼った瞬間に、貼ったぶんだけ全部ズレました。
    そこの **覆る条件がこれ**です:「`scripts/doc_usage.py` が毎周この一覧を
    印字するようになったら、`grep` を手で撃つ必要もなくなります」。

    **`--write` に置く理由**: §1 は**その回のいちばん最初のコマンド**で、
    かつ**手順を読む前**に撃たれる唯一のものです。ここ以外に置くと、
    「読む前に要るもの」が読んだ後に出ます（`_claim_lines` を §1 に置いたのと同じ理由）。

    **落ちても回は止めません。** 印は本体、これは付け足しです。
    """
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import doc_usage                                       # noqa: PLC0415
        path = Path(__file__).resolve().parent.parent / doc
        if not path.is_file():
            return []
        text = path.read_text(encoding="utf-8")
        return doc_usage.index_lines(text, doc, only_read=True, prefix="[marker] ")
    except Exception as exc:                                   # noqa: BLE001
        return [f"[marker] （手順の当てどころを出せませんでした: "
                f"{type(exc).__name__}: {exc}。`grep -n '^## ' {doc}` を手で撃つこと）"]


PREMISE_ROWS_CAP = 4


def _premise_subject_lines(cap: int = PREMISE_ROWS_CAP) -> list[str]:
    """**開いた前提の「主語」と「反証条件が数えている値」が食い違う行**を出す。

    ## なぜ §1 で出すのか（2026-09-01 に足した。**配線の3本目**）

    `scripts/premise_subject.py` は `retro.py` が名指しした
    **「どこからも呼ばれない」道具**の1本で、**3周 続けて申し送りに出ています**
    （2026-08-31 16:5x ／ 2026-09-01 01:3x ／ 01:4x）。
    `doc_usage` ／ `stale_scheduled` ／ `endcard_check` と同じ形で、
    **道具は在り、答えを出し、撃つ側がどこにも居ませんでした。**

    **なぜ「並べるだけ」の道具が §1 に要るのか。** `eta.py` が毎周
    印字しているとおり、**到達日が動くのは `config/hypotheses.yaml` の前提を
    1件 閉じたときだけ**です。その1件を選ぶとき、
    **「反証条件が、主張の主語を数えているか」を見ないまま閉じると、
    閉じた腕が実際に動いた腕と別物になります** ——
    `eta.py --alloc` はこの `lever:` の分布で「次の1件をどの腕に置くか」を出すので、
    **札が違えば配分そのものが違います。**

    **`[!]`／`[?]` が付いた行だけ**を出します（既定 4行まで）。
    **全文は `python scripts/premise_subject.py`**（API 0単位・1秒未満）。

    **落ちても回は止めません。** 印が本体で、これは付け足しです
    （`_doc_index_lines` と同じ）。
    """
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import premise_subject                                 # noqa: PLC0415
        rows = premise_subject.audit()
    except Exception as exc:                                   # noqa: BLE001
        return [f"[marker] （前提の主語を並べられませんでした: "
                f"{type(exc).__name__}: {exc}。"
                f"`python scripts/premise_subject.py` を手で撃つこと）"]
    flagged = [r for r in rows if r["mismatch"] or r["lever_off"]]
    if not flagged:
        return []
    bad = sum(1 for r in flagged if r["mismatch"])
    out = [f"[marker] **開いた前提 {len(rows)}件 のうち、条件が主語を数えていない行: "
           f"{len(flagged)}件**（主語と交わらない {bad}件 ／ "
           f"`lever:` が値と合っていない {len(flagged) - bad}件）"
           "。**閉じる前に当たること** —— 札が違うと `--alloc` の配分ごと違います"]
    for r in flagged[:cap]:
        mark = "[!]" if r["mismatch"] else "[?]"
        out.append(f"         {mark} {r['deadline']}  lever={r['lever'] or '—'}"
                   f"  主語={premise_subject._fmt(r['subject'])}"
                   f"  数えている={premise_subject._fmt(r['measured'])}"
                   f"  — {r['claim'][:56]}")
    if len(flagged) > cap:
        out.append(f"         （ほか {len(flagged) - cap}件。全文は "
                   f"`python scripts/premise_subject.py`）")
    out.append("         **わざと代理指標を使っている前提があります。"
               "機械は判定しません** —— 1件ずつ当たること")
    return out


def _unreachable_premise_lines(cap: int = PREMISE_ROWS_CAP) -> list[str]:
    """**規則2（1日1本）の下では、期限までに要件が満ちない前提**を出す。

    ## なぜ §1 で出すのか（2026-09-01 に足した。**配線の4本目**）

    `scripts/eta.py` が毎周 印字しているとおり、**到達日が動くのは
    `config/hypotheses.yaml` の前提を1件 閉じたときだけ**です。
    **その台帳に「閉じられない前提」が居座ると、到達日はそこで止まります。**

    **この計器は既に在りました** —— `src/house_rule.unreachable_needs()`。
    ただし、それを印字するのは `scripts/deadline_check.py` の**末尾**だけで、
    その道具は §1 の読む順（`_doc_index_lines()` の7節）に**1つも入っていません**。
    `grep -c deadline_check docs/trigger_main.md` は 1 以上ですが、
    **`_m4_lines()` の註と同じ罠**です —— 名前は在っても、
    **何をやるか決める前に読まれる所には無い。**

    実測 2026-09-01 04:0x の回: `eta.py` の名指しは `per_video`、
    「この回に閉じられる前提はありません」。**5つの選択肢のうち4つが枠切れで塞がり**、
    残るのは `fix` だけに見えていました。`deadline_check.py` を**末尾まで**読んで
    はじめて「規則の下では満ちない要件 1件」が出て、
    **その1件が、公開ずみの日だけで期限より 10日 早く閉じました**
    （「長尺の面は、その日の長尺の公開本数で決まる」・`outcome: mixed`）。
    **同じ回に `verdict` が撃てるかどうかが、この1行の有無で決まっていました。**

    **`eta.py` の「この回に閉じられる前提はありません」は嘘ではありません** ——
    あれは `needs` の期日で数えており、**「その期日は永久に来ない」を見ていません。**
    ここが見るのはそちらです。

    **落ちても回は止めません。** 印が本体で、これは付け足しです。
    """
    try:
        import yaml                                            # noqa: PLC0415
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from src import house_rule                             # noqa: PLC0415
        doc = yaml.safe_load(
            (Path(__file__).resolve().parents[1]
             / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
        rows = doc["hypotheses"] if isinstance(doc, dict) else doc
        bad = house_rule.unreachable_needs(rows)
    except Exception as exc:                                   # noqa: BLE001
        return [f"[marker] （規則の下で満ちない要件を数えられませんでした: "
                f"{type(exc).__name__}: {exc}。"
                f"`python scripts/deadline_check.py` の末尾を読むこと）"]
    if not bad:
        return []
    out = [f"[marker] **規則2（1日{house_rule.PUBLISH_PER_DAY}本）の下では、"
           f"期限までに要件が満ちない前提: {len(bad)}件** —— "
           "**その期日は来ません。待っても閉じません。**"
           " 到達日が動くのは前提を1件 閉じたときだけなので、"
           "**ここが詰まると到達日が止まります**"]
    for r in bad[:cap]:
        claim = str(r.get("claim") or "")
        out.append(f"         [!] {r.get('deadline') or '—'}"
                   f"  lever={r.get('lever') or '—'}"
                   f"  — {claim[:56]}")
        out.append(f"             要件: {str(r.get('what') or '')[:80]}")
    if len(bad) > cap:
        out.append(f"         （ほか {len(bad) - cap}件）")
    out.append("         **直し方は2つ**: (1) 要件を 1日1本 で届く形へ書き直す "
               "(2) **すでに公開ずみの日で判定できるなら、いま閉じる**"
               "（実測 2026-09-01: (2) で期限より 10日 早く1件 閉じました・"
               "**Data API 0単位**）。全文は `python scripts/deadline_check.py` の末尾")
    return out


#: M4 の数がこれより古かったら、撃ち直しをすすめる（時間）。
#: 判定の窓が 7日 なので、1日ぶん古い数はまだ同じことを言っています。
M4_STALE_HOURS = 24


def _m4_lines(stale_hours: int = M4_STALE_HOURS) -> list[str]:
    """**M4（検索 → 長尺）の、いまの数と齢**を出す（**API 0単位・台帳を読むだけ**）。

    ## なぜ §1 で出すのか（2026-09-01 に足した。**配線の4本目**）

    `scripts/search_terms.py` は `docs/MEANS.md` **M4 の判定に使う唯一の計器**で、
    M4 の期限は **9/15** です。それが `retro.py` の
    「どこからも呼ばれない」に **3周 続けて**載っていました
    （`doc_usage` ／ `stale_scheduled` ／ `premise_subject` と同じ形 ——
    **道具は在り、締切のある数を印字し、撃つ側がどこにも居ない**）。
    `grep -c search_terms docs/trigger_main.md` は **1** で、
    その1件は「呼ばれていない道具の一覧」そのものでした。

    **ここで道具そのものを撃ちません。** あれは 28秒 かかり、
    動画1本ずつに Analytics を引きます（実測 121本）。
    §1 は**手順を読む前の唯一のコマンド**なので、そこへ 28秒 を置くと
    **毎周 払うことになります。** だから積むのは道具の側、
    ここは**台帳の最後の1点と、その齢**だけを読みます。

    **齢を出すのが本体です。** 数だけを出すと、
    **古い数が「いまの数」に見えます** —— `status.py` の `quota_ledger` が
    「呼び出しは在る・検査も通る・出力に無い」で 101周 黙っていたのと同じ側の穴で、
    こちらは「**出てはいるが、いつの数か分からない**」ほうです。

    **落ちても回は止めません。** 印が本体で、これは付け足しです
    （`_doc_index_lines` ／ `_premise_subject_lines` と同じ）。
    """
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import search_terms                                    # noqa: PLC0415
        # **7日 の窓だけを読むこと。** M4 の基準値は「1再生/7日」で窓と対なので、
        # `--days 28` の点を並べると 4倍 の窓の数を 7日 の基準値と比べることになります。
        point = search_terms.latest(7)
    except Exception as exc:                                   # noqa: BLE001
        return [f"[marker] （M4 の台帳を読めませんでした: "
                f"{type(exc).__name__}: {exc}）"]
    if not point:
        return ["[marker] **M4（検索 → 長尺）の数が、まだ1点もありません** —— "
                "`python scripts/search_terms.py`（**日枠 0単位**・約28秒）。"
                "**M4 の期限は 9/15**、判定に使う計器はこれだけです"]
    try:
        at = datetime.fromisoformat(str(point["at"]))
        age_h = (datetime.now(timezone.utc) - at).total_seconds() / 3600.0
    except (ValueError, KeyError, TypeError):
        age_h = float("inf")
    long_v = point.get("long_views")
    short_v = point.get("short_views")
    days = point.get("days", 7)
    age = "齢 不明" if age_h == float("inf") else f"**{age_h:.0f}時間 前**の数"
    verdict = "基準値の上" if isinstance(long_v, int) and long_v > 1 else "基準値のまま"
    out = [f"[marker] **M4（検索 → 長尺）: 長尺 {long_v}再生 / {days}日**"
           f"（基準値 **1再生/7日** → {verdict}）／ ショート {short_v}再生は"
           f"**判定に使いません**（検索面に差し込まれただけ）。{age}"]
    if age_h > stale_hours:
        out.append("         **撃ち直すこと**: `python scripts/search_terms.py`"
                   "（**日枠 0単位**。枠が尽きた回でも通ります）")
    return out


def _claim_lines(window_min: int = CLAIM_WINDOW_MIN) -> list[str]:
    rows = claims(window_min)
    ships = recent_ships(window_min)
    if not rows and not ships:
        return []
    out: list[str] = []
    if rows:
        out.append(f"[marker] **直近 {window_min}分 に、他の回が取りかかると書いたもの: "
                   f"{len(rows)}件**（`--claim`）")
        for r in rows[-5:]:
            who = str(r.get("session") or "")[-8:]
            out.append(f"         {str(r.get('at'))[11:16]}  …{who}  {r.get('what')}")
    # **`--claim` は任意、`--ship` は必須。** 打たれていない claim は
    #     見えないので、**実際に出したもの**も並べます（`recent_ships` の註）。
    if ships:
        out.append(f"[marker] **直近 {window_min}分 に、他の回が実際に出したもの: "
                   f"{len(ships)}件**（`--ship`。**claim を打たない回は、上には出ません**）")
        for r in ships[-5:]:
            who = str(r.get("session") or "")[-8:]
            out.append(f"         {str(r.get('at'))[11:16]}  …{who}  "
                       f"{str(r.get('what'))[:96]}")
    out.append("         **予約ではありません。**避けるか重ねるかはこちらが決めること"
               "（同じ所を2つの回が直して、片方の誤りが見つかった例が 08-26 にあります）。"
               "**ただし、ぶつかると片方は捨てになります。**")
    return out


def claim(what: str) -> int:
    """**「いまからこれに取りかかる」を残す。**（`claims()` の註）"""
    if not (what or "").strip():
        print("[marker] `--claim` は1行の中身が要ります。")
        return 2
    if is_parent():
        print("[marker] **親からは印を付けません。**")
        return 0
    line = _append({
        "at": datetime.now(JST).isoformat(timespec="seconds"),
        "session": actor_id() or "(不明)",
        "kind": CLAIM_KIND,
        "what": what.strip(),
    })
    print(f"[marker] 取りかかる印を付けました: {line}")
    for ln in _claim_lines():
        print(ln)
    return 0


def _next_slot_lines() -> list[str]:
    """**`improve` の当てどころ**（2026-09-01・最適化の回に足した。**API 0単位**）。

    ## なぜ §1 で出すか

    オーナーが 2026-08-31 に固定した規則3（`src/house_rule.py`）は
    「次の投稿予定までにそこで投稿する動画を改善し続ける」。
    `docs/trigger_main.md` §4 と `CLAUDE.md` はそれを `improve` として
    5つの選択肢に足しました。**が、当てどころが印字されていませんでした。**

    実測（`data/runs.jsonl`・規則が固定された 2026-08-31 以降の ship **88件**）:

        fix **56件（64%）** ／ (other) 18 ／ verdict 9 ／ **improve 4件（4.5%）**

    **fix は `eta.py` が毎周 36件 名指しし、verdict は「期日の来た前提」が
    名指しします。improve だけ、どの本が次かを調べるところから始まります**
    （`scripts/reschedule.py --list` は API 50単位）。
    **同じ5択に並べても、探す手間が違えば選ばれません。**

    §1 はその回のいちばん最初のコマンドで、**何をやるか決める前**です。
    決めた後に見せても、払った時間は戻りません（すぐ上の `_claim_lines()` と同じ理由）。

    **覆る条件**: `improve` の割合が上がらないなら、原因は「見えないこと」では
    ありません（＝ 見えていても撃てない ＝ 枠か材料の側）。そのときは
    `src/next_slot.py` を足すのではなく、**`docs/trigger_main.md` §4 の
    「枠が尽きている回」の節を疑うこと。**
    """
    try:
        from src import next_slot                               # noqa: PLC0415
        return [f"[marker] {ln}" if not ln.startswith(" ") else f"[marker]{ln}"
                for ln in next_slot.lines()]
    except Exception as exc:                                    # noqa: BLE001
        return [f"[marker] （次の枠を読めませんでした: {exc}）"]


def write() -> int:
    me = actor_id() or "(不明)"
    if is_parent():
        print("[marker] **親からは印を付けません。**"
              " 親が周を回すのは設計の否定なので、平常の心音として数えません。")
        return 0
    line = _append({
        "at": datetime.now(JST).isoformat(timespec="seconds"),
        "session": me,
        "kind": "start",
    })
    print(f"[marker] 走った印を付けました: {line}")
    # **きょうの1本を置く手（＋先の日付の掃き）を、ここから起こす**（2026-09-02 夜）。
    #     ここは毎周 必ず最初に撃たれる唯一の口です（§1）。SessionStart フックは
    #     サブでは起きません（`scripts/ahead_sweep.kick()` の註）。背景・数秒。
    try:
        import ahead_sweep as _sweep                            # noqa: PLC0415
        print(f"[marker] きょうの1本: {_sweep.kick()}")
    except Exception as exc:                                   # noqa: BLE001
        print(f"[marker] きょうの1本: 起こせませんでした（{str(exc)[:80]}）")
    # **外の帯を、毎日 出している形（ショート）で撃つ手も、ここから起こす**（2026-09-02 深夜）。
    #     `[きょうの1本]` が印字する手は選ばれなければ撃たれません。帳面にショートが
    #     7日以内に無く、印が 6時間 より古い周だけ背景で撃ちます（`niche_ceiling.kick()` の註）。
    try:
        import niche_ceiling as _nc                             # noqa: PLC0415
        print(f"[marker] 外の帯: {_nc.kick()}")
    except Exception as exc:                                   # noqa: BLE001
        print(f"[marker] 外の帯: 起こせませんでした（{str(exc)[:80]}）")
    # **この回だけの一時置き場を、ここで掘って見せること**（2026-08-29 に足した）。
    # 共有の直下へ書くと、きょうだいが同じ名前で上書きします
    # （実測: `status.py` の出力 266行 → 24行）。`scratch_dir()` の註。
    scratch = scratch_dir()
    if scratch:
        print(f"[marker] **この回の一時置き場: {scratch}**"
              "（きょうだいと共有の直下へ書かないこと。"
              "`status.txt` `eta.txt` `build.log` は全員が同じ名前を使います）")
    # **手順の当てどころ**（2026-09-01 に足した）。ここで出す理由は下の
    # `_doc_index_lines()` の註。**§1 は手順を読む前の唯一のコマンド**です。
    for ln in _doc_index_lines():
        print(ln)
    # **前提の主語と、条件が数えている値の食い違い**（2026-09-01 に足した）。
    # 理由は `_premise_subject_lines()` の註 —— 到達日を動かすのは
    # 「前提を1件 閉じる」ことだけなので、**その1件を選ぶ前**に見せます。
    for ln in _premise_subject_lines():
        print(ln)
    # **M4（検索 → 長尺）の数と齢**（2026-09-01 に足した）。理由は `_m4_lines()` の註 ——
    # 期限 9/15 の手段で、判定に使う計器は `search_terms.py` の1本だけです。
    for ln in _m4_lines():
        print(ln)
    # **規則2 の下では満ちない要件**（2026-09-01 に足した）。理由は
    # `_unreachable_premise_lines()` の註 —— `eta.py` の「閉じられる前提はありません」は
    # `needs` の期日で数えており、**「その期日は永久に来ない」を見ていません。**
    for ln in _unreachable_premise_lines():
        print(ln)
    # **`improve` の当てどころ**（2026-09-01 に足した）。理由は `_next_slot_lines()`
    # の註 —— 5択のうち improve だけ、当てどころがどこにも印字されていませんでした
    # （規則が固定された 08-31 以降の ship 88件 中 **4件・4.5%**）。
    for ln in _next_slot_lines():
        print(ln)
    # **ここで出すこと。** §1 はその回のいちばん最初のコマンドで、
    # **何をやるか決める前**です。決めた後に見せても、払った時間は戻りません。
    for ln in _claim_lines():
        print(ln)
    # **頭の3つ（一時置き場・読む順）を末尾にもう一度 刷る**（2026-09-03 05:4x に足した）。
    #     この印は 100行 を超え、回は `| tail -80` で読む（05:0x・05:1x と2回 続けて実測）。
    #     末尾だけ読むと頭が消え、`_doc_index_lines()` を撃ち直す（数十秒）か
    #     共有の直下へ書いてきょうだいに上書きされる（08/29）。**同じ字で2度 出しても
    #     害はなく、消えるほうが高い。** 覆る条件: 印が 80行 を切ったら、この写しは要らない。
    print("[marker] ―― 頭の写し（`tail` で読む回のため。上と同じ字）――")
    if scratch:
        print(f"[marker] **この回の一時置き場: {scratch}**")
    for ln in _doc_index_lines():
        print(ln)
    return 0


SEEN_KIND = "seen"


def seen(target: str, why: str) -> int:
    """**「見にいった。拾うものは無かった」を残す。**（2026-08-18 に足した）

    ## なぜ要るか（この回が2回目の支払いです）

    `sibling_check.silent_runs()` は「repo に1行も残さずに終わった回」を
    名指しします。名指しされた側を**見にいって、中身がゼロだった**とき ——
    `nosrc` で題名が既定のまま、あるいは `apifail` で1ターン目に死んだ回 ——
    **その判定を残す場所がどこにもありませんでした。**

    黙らせる道は1本だけ（`data/inbox.jsonl` に本文ごと入っていること）で、
    そこへ落とすのは §0 が**禁じています**。中身がゼロの題名を受け取り帳へ
    落とすと、**次の回がそれを閉じる仕事をする**からです。

    結果、**判定済みの1件が、25件の窓から落ちるまで毎回鳴り続けます。**

        08/18 14:5x  見にいった → 「拾うものはありません」と日誌に書いた
        08/18 17:0x  同じ1件がまた鳴る → もう一度見にいった（同じ結論）
        08/18 18:2x  **また鳴った**（この回）

    **日誌は機械が読みません。** 判定は残っているのに、名指しする側からは
    見えない。だから**印の側に置きます** —— `data/runs.jsonl` は
    `silent_runs()` がもともと読んでいるファイルで、追加の口が要りません。

    ## 何を黙らせて、何を黙らせないか

    黙らせるのは**名指しそのもの**だけです。**その回が印を残していない事実は
    変わりません**（`kind` が別なので `marked` には入らない）。
    `--closes silent_run` の当たり率も動きません（あちらは ship に付く宣言）。

    `why` は必須です。**理由の書いていない黙らせ方は、次に来た側が
    判断できず惰性で残ります。**
    """
    me = actor_id() or "(不明)"
    if not target.startswith("session_"):
        print(f"[marker] **セッションIDに見えません**: {target}")
        return 2
    why = (why or "").strip()
    if not why:
        print("[marker] **理由が要ります。** 見にいって何が無かったのかを1行で。")
        return 2
    for rec in _records():
        if rec.get("kind") == SEEN_KIND and rec.get("saw") == target:
            print(f"[marker] **もう見た印が付いています**: {target}"
                  f"（{rec.get('at')} / {rec.get('why')}）")
            return 0
    line = _append({
        "at": datetime.now(JST).isoformat(timespec="seconds"),
        "session": me,
        "kind": SEEN_KIND,
        "saw": target,
        "why": why,
    })
    print(f"[marker] 見にいった印を付けました: {line}")
    print("    **この1件は、もう名指しされません**（`sibling_check`）。")
    return 0


def journal_lines() -> int:
    """いまの `docs/JOURNAL.md` の行数。**読めなければ 0**（＝何も黙らせない）。"""
    try:
        return len(JOURNAL.read_text(encoding="utf-8").split("\n"))
    except OSError:
        return 0


ETA_LOG = Path(__file__).resolve().parent.parent / "data" / "eta.jsonl"


def _eta_target() -> tuple[str | None, float | None, str]:
    """**いま出ている予測日**（`data/eta.jsonl` の最後の点）。

    読めなければ `(None, None)`。**回を止めないこと** —— この印は記録であって
    門ではありません。予測が撃てていない回でも、出したものは残します。

    **読むのは軌跡のほう**（`traj_date`。2026-08-20 18:xx に切り替えた）。
    `target_date` は「**腕が1ミリも動かない未来**」の日付で、いまは
    `None`（＝天井が足りない）が続きます。そこを読むと `--moves` の
    突き合わせ（`levers.reconcile`）が**永久に空**になり、
    「宣言と実際」が1行も並ばなくなります。
    """
    try:
        lines = [ln for ln in ETA_LOG.read_text(encoding="utf-8").splitlines() if ln.strip()]
        row = json.loads(lines[-1])
    except (OSError, IndexError, json.JSONDecodeError):
        return None, None, "無し"
    if row.get("traj_date"):
        return row["traj_date"], row.get("traj_days"), "軌跡"
    return row.get("target_date"), row.get("days_to_target"), "据え置き"


#: `CLAUDE.md` §「毎回の実行で必ずやること」が「出した」と呼ぶ5つ。
#: **`scripts/drift.py` の `KINDS` と同じ並びです**（片方だけ変えないこと）。
#:
#: **`improve` は 2026-08-31 に足しました**（オーナーが固定した規則3）——
#: 「次の投稿予定までにそこで投稿する動画を改善し続ける」。
#: `upload` は**1日1回しか撃てない**ので、そのままだと大半の回が
#: 「何も出せない回」になります。**次の枠の1本を良くした回も「出した」**です
#: （`docs/trigger_main.md` §4）。
#: **`premise` は 2026-09-01 に足しました**（最適化の回）。
#: `eta.py` は毎周こう印字しています ——
#: 「**軌跡の腕が動くのは `config/hypotheses.yaml` の前提を1件 閉じたときだけ**」
#: そして `docs/trigger_main.md` §2.6 は、その先をこう分けています ——
#:
#:     台帳を減らす手   期日の来た前提を閉じる（`verdict`）。**0日 のことがある**
#:     到達日を動かす手 **縛っている腕の天井を疑う前提を、新しく立てる**
#:
#: **後者が、5択のどこにもありませんでした。** 実測（この回・`data/runs.jsonl`）:
#: 08-25 以降の ship **326件** ＝ `fix` 248（**76%**）／`upload` 33／
#: `verdict` 20（6%）／`means` 19／`improve` 6。
#: **`fix` の 248件 のうち 232件 が自分で `--moves 0` と宣言しています。**
#: 台帳のほうは 開いている 21件・閉じる 1.86件/日 で、**2026-09-12 に空**でした
#: （`deadline_check.ledger_drain()`）。**減る一方の燃料に、注ぎ口が無かった**形です。
#:
#: **`src/premise.py` とは別物です** —— あちらは台本の前提（画面に出しようがない値）。
#: ここは `config/hypotheses.yaml` の1件（＝到達日を動かす燃料）。
SHIP_KINDS = ("upload", "improve", "means", "verdict", "fix", "premise")


#: **`fix` の連（続けて何回 `fix` で終わったか）の上限。**
#:
#: ## なぜ要るか（2026-09-01・最適化の回に足した）
#:
#: `scripts/drift.py` は 2026-08-24 から、この輪が目標から外れていることを
#: **正しく印字し続けています。** その docstring は原因まで名指ししています ——
#: **「サボりではなく、合格の定義が目標とつながっていなかっただけ」。**
#: **それでも 7日 後の実測は変わっていませんでした**（下）。
#: **印字は行動を変えません。** このファイル自身が、同じことを
#: `--kind` の門の註で書いています ——
#: **「註や警告ではなく、通さないことだけが効いています」**（2026-08-19 の `--lever`）。
#:
#: 実測 2026-09-01（直近7日・ship 358件・`data/runs.jsonl`）:
#:
#:     fix 269件（75%）／ verdict 16件（4%）／ **直近20回の verdict 0件**
#:     到達日が動きえない回 230/358（64%）／ 名指しの腕に従った回 7/71（10%）
#:
#: そして `eta.py` は毎回こう印字しています ——
#: **「軌跡の腕が動くのは、前提を1件 閉じたときだけ。作る・出す・直すは
#: 軌跡の入力に入りません」。** つまり **`fix` の回の `--moves` は定義上 0** です。
#: **75% の回が、自分で「到達日は動かない」と宣言しながら通っていました。**
#:
#: ## **しきいは「連の長さ」ではなく「比の天井」から決めること**（2026-09-01 夕・作り直した）
#:
#: 前の版は、しきいを **4** に置いて、理由をこう書いていました ——
#: 「連の長さは実測で 中央 2・平均 3.8。しきい 4 なら普通の連は触らない」。
#: **連の分布から決めていました。それが誤りです。**
#:
#: **連のしきい `N` は、`fix` 比の天井を `N/(N+1)` に固定します。**
#: 連が `N` に達したら次の1回は他の種別になるので、通せる並びの最悪は
#: `fix`×N → 他1 → `fix`×N → 他1 …… ＝ **`fix` が `N/(N+1)`**。
#:
#:     N=4 → **80%**   N=3 → 75%   **N=2 → 66.7%**   N=1 → 50%
#:
#: **門を入れる前の `fix` 比は 72.8% でした**（下の実測）。
#: **`N=4` の天井 80% は、それより高い。** つまり前の版は、
#: **完全に効いても、直そうとしていた比を下げられない設計**でした。
#:
#: ## 実測（2026-09-01 10:4x・`fix_share()` をこの回に撃って出した数）
#:
#: 門を入れたのは 2026-08-31 16:45（`bc560026`）。その前後で:
#:
#:     門の前   ship 217件 ／ `fix` 158件 ＝ **72.8%**
#:     門の後   ship 107件 ／ `fix`  89件 ＝ **83.2%**   ← **上がっています**
#:
#: 同じ窓に `kind="fix_gate"` の行が **27件**。うち **19件 が `waived`** で、
#: **連は 4 → 22 まで、途切れずに通り続けました**（04:01〜08:32）。
#: 免除の条件は `quota_is_out() and not free_alternatives()` で、
#: **`free_alternatives()` が空を返す欠陥**（10:0x に別の回が直した）が
#: そこに乗っていました。**免除の穴と、天井 80% の設計と、両方です。**
#:
#: これは、この註が自分で書いた**覆る条件 1 そのもの**です ——
#: 「`fix` 比が下がらないまま `fix_gate` の行だけが増えるなら、
#: 門が効いていない。**外すか作り直すこと**」。**作り直しました。**
#:
#: ## しきいを 2 に置いた理由
#:
#: 天井を **66.7%** にすると、門の前の 72.8% を**初めて下回ります**。
#: 連の実測（この回・n=61）は 中央 **3**・平均 4.05・**最長 23** で、
#: 長さ 1〜2 の連 **29/61（48%）は1件も触りません**。触るのは 3 以上の後ろ側だけ。
#:
#: **これは `fix` の禁止ではありません。** 直す回は要ります
#: （計器が壊れていれば、その先の判断が全部ずれる）。止めているのは**連**だけで、
#: 「2回 続けて直した」なら次の1回は**到達日を動かしうる側**
#: （`verdict` / `premise` / `upload` / `improve` / `means`）に使うこと、という門です。
#: `free_alternatives()` が **0単位 の手を毎回 名指しする**ので、逃げ場はあります。
#:
#: ## **覆る条件**（次に来た回へ。**手で数えないこと。`fix_share()` を撃つこと**）
#:
#: 1. **`fix_share()` の「門の後」が 66.7% を超えたまま**なら、
#:    種別の語を書き換えて通されているか、免除が広すぎます。**中身を見ること。**
#: 2. `fix` 比が 66.7% を**十分に**下回って（＝天井が縛っていない）30日 続いたら、
#:    この門は役目を終えています。**そのときは外すこと。**
#: 3. **しきいを上げるときは、必ず `N/(N+1)` を先に出すこと。**
#:    その比が「いまの `fix` 比」より高いなら、**その門は効きません**
#:    （`tests/test_fix_run_cap_share.py` が、その算術を止めます）。
#: 4. **`verdict` / `premise` が増えたのに到達日が動かない**なら、律速は `fix` では
#:    ありません（＝ 前提の熟す速さのほう。実測 1.14件/日 に対し、回は 15周/日）。
#:    **手で数えないこと。`cond4()` を撃つこと**（2026-09-02 に撃てる形にした）。
#:
#:    > **【2026-09-02: 4 は既に立っています。】** `cond4()` の実測 ——
#:    > `verdict`+`premise` 比 **7.8% → 30.6%**（門の前 257件 / 後 49件）、
#:    > `fix` 比 74.7% → 61.2%、`lever_followed` 18.3% → **53.1%**、
#:    > 死んだ腕を名乗った ship 36.6% → **10.2%**。**配合は全部 良くなりました。**
#:    > そして `traj_days` は 08-30 の 135.7日 から **08-31 以降ずっと「出ません」**。
#:    > **＝ 門は効いた。効いても日付は動かない。**
#:    >
#:    > **だから、この門をこれ以上きつくしないこと。** 天井まで3本とも引いても
#:    > 目標の 18.7%（`python -m src.joint_cap`）で、残りの ×5.35 は
#:    > **腕の値ではなく天井そのもの**の話です。**回の配合は、もう律速ではありません。**
FIX_RUN_CAP = 2

#: **この門を作り直した時刻**（2026-09-01 10:45 JST）。`fix_share()` の既定の境目です。
#:
#: **前の版（`bc560026`・08-31 16:45）の境目のままにしないこと。**
#: そうすると「門の後」の窓に、免除で 19件 通した壊れていた期間が入り、
#: **新しい門が、古い門の成績で判定されます。** 境目はここを動かすこと
#: （**動かすときは、動かす前の数を上の註に書き残すこと** —— そうしないと
#: 「効いたのか、境目をずらしただけか」が、次に来た側に区別できません）。
FIX_GATE_AT = "2026-09-01T10:45"


def fix_share(path: Path | None = None, since: str | None = None) -> dict:
    """**`fix` が ship の何割を占めているか。**（`data/runs.jsonl` だけ。**API 0単位**）

    ## なぜ要るか（2026-09-01 夕・最適化の回）

    `FIX_RUN_CAP` の「覆る条件 1」は
    **「`fix` 比が下がらないまま `fix_gate` の行だけが増えたら作り直せ」**
    と書いてありました。**その比を出す道具が、どこにもありませんでした。**

    だから 2026-09-01 の夕方まで、**誰も撃っていません** ——
    その間に比は 72.8% → **83.2%** へ上がり、`fix_gate` の行は **27件**
    （うち 19件 が `waived`）まで増えていました。**覆る条件は、
    撃てる形で置かないと、書いてあっても発火しません。**

    返り: `{"before": {...}, "after": {...}, "cap_share": float, "fired": bool}`。
    `fired` が真なら、覆る条件 1 が立っています（＝ 門を作り直すこと）。

    **覆る条件**: `data/runs.jsonl` の `ship_kind` が別の欄名になったら、
    ここも変えること（`SHIP_KINDS` と対）。
    """
    p = path or MARKS
    at = since or FIX_GATE_AT
    before: list[str] = []
    after: list[str] = []
    try:
        with p.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:                               # noqa: BLE001
                    continue
                if row.get("kind") != "ship":
                    continue
                k = row.get("ship_kind") or "(none)"
                (after if str(row.get("at", "")) >= at else before).append(k)
    except FileNotFoundError:
        pass

    def _one(ks: list[str]) -> dict:
        n = len(ks)
        f = sum(1 for k in ks if k == "fix")
        return {"n": n, "fix": f, "share": (f / n) if n else 0.0}

    b, a = _one(before), _one(after)
    cap_share = FIX_RUN_CAP / (FIX_RUN_CAP + 1)
    return {
        "at": at, "before": b, "after": a, "cap_share": cap_share,
        # **「効いていない」の判定**: 門の後の比が、門の天井を超えている
        # （＝ 免除か、種別の書き換えで抜けている）。
        "fired": bool(a["n"] >= 20 and a["share"] > cap_share),
    }


def fix_share_line(path: Path | None = None) -> str:
    """`fix_share()` を1行にする（門が止めたときに、その場で見せる）。"""
    r = fix_share(path)
    b, a = r["before"], r["after"]
    tail = ""
    if r["fired"]:
        tail = ("　← **門の天井を超えています。**"
                "`FIX_RUN_CAP` の覆る条件1 が立っています（作り直すこと）")
    return (f"**`fix` 比**: 門の前 {b['fix']}/{b['n']} ＝ {b['share']:.1%}"
            f" ／ 門の後 {a['fix']}/{a['n']} ＝ {a['share']:.1%}"
            f"（この門の天井 {r['cap_share']:.1%} ＝ {FIX_RUN_CAP}/{FIX_RUN_CAP + 1}）{tail}")


#: **到達日を動かしうる種別**（`FIX_RUN_CAP` の門が「そちらへ使え」と言う側）。
#: `eta.py` の定義では、**軌跡の腕が動くのは前提を1件 閉じたときだけ**なので、
#: 本当に日付を持っているのは `verdict` と `premise` の2つです
#: （`upload` / `improve` / `means` は「出した」の側で、`--moves` は定義上 0）。
MOVING_KINDS = ("verdict", "premise")


def cond4(path: Path | None = None, eta_path: Path | None = None,
          since: str | None = None) -> dict:
    """**`FIX_RUN_CAP` の「覆る条件 4」が立っているか。**（`data/` だけ・**API 0単位**）

    ## なぜ要るか（2026-09-02 夕・最適化の回に撃って作った）

    `FIX_RUN_CAP` の覆る条件は4件あり、**1 だけが撃てる形**でした
    （`fix_share()`）。4 は散文のままです ——

        4. **`verdict` / `premise` が増えたのに到達日が動かない**なら、
           律速は `fix` ではありません（＝ 前提の熟す速さのほう）

    **同じファイルが、その1つ上でこう書いています** ——
    「**覆る条件は、撃てる形で置かないと、書いてあっても発火しません**」。
    `fix_share()` はその教訓で作られました。**4 は取り残されていました。**

    そして 2026-09-02 に手で数えたら、**4 は既に立っていました**::

        門の前（〜09-01 10:45）  ship 257件  fix 74.7%  verdict+premise   7.8%
        門の後                    ship  49件  fix 61.2%  verdict+premise  30.6%
        `lever_followed`          18.3% → 53.1%
        死んだ腕を名乗った ship    36.6% → 10.2%
        —— **配合はどれも良くなりました**
        `traj_days`               08-30 135.7日 → 08-31 以降 **出ません**
        —— **到達日は動いていません**（良くなるどころか、日付が消えた）

    **＝ 門は効いた。効いたのに日付が動かない。だから律速は `fix` ではありません。**

    ## これが分かると、次の回が何をしなくて済むか

    **回の配合をこれ以上いじらないこと。** `fix` 比を 61% から 50% へ下げても、
    `lever_followed` を 53% から 90% へ上げても、**到達日は動きません** ——
    腕を3本とも天井まで引いても目標の 18.7% だからです（`python -m src.joint_cap`）。
    **残りの x5.35 は、腕の値ではなく天井そのものの話**で、
    そこは `config/hypotheses.yaml` の前提でしか動きません。

    返り: `{"fired", "before", "after", "traj_before", "traj_after", "why"}`。

    ## **覆る条件**（この関数自身の）

    - **`traj_days` が動いた回が出たら**（＝ 到達日が実際に前後した）、`fired` は
      自分で偽に戻ります。**定数を持ちません。**
    - `data/eta.jsonl` に `traj_days` が無くなったら、ここは判定できません
      （`traj_*` が `None` で返ります）。**そのときは黙って偽**にします ——
      **「測れない」を「立っている」と読ませないこと。**
    - `MOVING_KINDS` を増やすときは、その種別が**本当に軌跡の入力に入るか**を
      先に確かめること（`eta.py --reflect` の「前 → 後」が動くか）。
      入らない種別を足すと、この判定は**必ず立ちます**（分子だけ増えるので）。
    """
    p = path or MARKS
    at = since or FIX_GATE_AT
    before: list[str] = []
    after: list[str] = []
    try:
        with p.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:                               # noqa: BLE001
                    continue
                if row.get("kind") != "ship":
                    continue
                k = row.get("ship_kind") or "(none)"
                (after if str(row.get("at", "")) >= at else before).append(k)
    except FileNotFoundError:
        pass

    def _one(ks: list[str]) -> dict:
        n = len(ks)
        mv = sum(1 for k in ks if k in MOVING_KINDS)
        return {"n": n, "moving": mv, "share": (mv / n) if n else 0.0}

    b, a = _one(before), _one(after)

    # **到達日**は `traj_days` で見ます（`_eta_target()` と同じ欄）。
    #     「出ません」は `eta.py` が 10^9 で積むので、
    #     **大きい数 ＝ 遠い**の向きでそのまま比べられます。
    tb = ta = None
    try:
        rows = [json.loads(ln) for ln in
                (eta_path or ETA_LOG).read_text(encoding="utf-8").splitlines() if ln.strip()]
        for r in rows:
            d = r.get("traj_days")
            if not isinstance(d, (int, float)):
                continue
            if str(r.get("at", "")) < at:
                tb = float(d)
            else:
                ta = float(d)
    except (OSError, json.JSONDecodeError, ValueError):
        tb = ta = None

    # **測れない回は偽**（上の「覆る条件」2つ目）。
    moved = None if (tb is None or ta is None) else (ta < tb - 0.5)

    def _d(v: float | None) -> str:
        """**`10^9` を「1000000000.0日」と刷らないこと。** `eta.py` の
        「出ません」（＝ 天井が足りない）がその値で積まれています ——
        生の桁を出すと、読んだ側が「27万年 かかる」と読みます（実際に読みかけた）。
        """
        if v is None:
            return "無し"
        return "出ません" if v >= 1e8 else f"{v:.1f}日"
    rose = a["n"] >= 20 and a["share"] > b["share"]
    fired = bool(rose and moved is False)

    if fired:
        why = (f"到達日を動かしうる種別が {b['share']:.1%} -> {a['share']:.1%} に"
               f"増えたのに、到達日は {_d(tb)} -> {_d(ta)} で近づいていません")
    elif moved is None:
        why = "`traj_days` が両側に無いので判定できません（**立っているとは読まないこと**）"
    elif not rose:
        why = f"動かしうる種別が増えていません（{b['share']:.1%} -> {a['share']:.1%}）"
    else:
        why = f"到達日は近づいています（{_d(tb)} -> {_d(ta)}）"

    return {"fired": fired, "at": at, "before": b, "after": a,
            "traj_before": tb, "traj_after": ta, "moved": moved, "why": why}


def cond4_line(path: Path | None = None) -> str:
    """`cond4()` を1行にする。**立っていないときも数を出すこと** ——
    黙ると、次に来た側が「まだ立っていない」と「測っていない」を区別できません。
    """
    r = cond4(path)
    b, a = r["before"], r["after"]
    head = (f"**`verdict`+`premise` 比**: 門の前 {b['moving']}/{b['n']} ＝ {b['share']:.1%}"
            f" ／ 門の後 {a['moving']}/{a['n']} ＝ {a['share']:.1%}")
    if r["fired"]:
        return (head + f"　← [!] **`FIX_RUN_CAP` の覆る条件4 が立っています** —— {r['why']}。"
                "**律速は `fix` ではありません。回の配合をこれ以上いじらないこと** —— "
                "腕を3本とも天井まで引いても目標の 18.7%（`python -m src.joint_cap`）で、"
                "残りは**天井そのもの**の話です"
                "（`config/hypotheses.yaml` の前提でしか動きません）")
    return head + f"（覆る条件4 は立っていません: {r['why']}）"


def fix_run_len(path: Path | None = None) -> int:
    """**末尾から数えて、`fix` が何回 続いているか。**（他の種別が出たら止まる）

    `drift.py` の「直近20回の verdict」と同じ欄（`ship_kind`）を読みます。
    **`kind != "ship"` の行は数に入れません**（`--write` の印や、この門の記録）。
    """
    p = path or MARKS
    if not p.exists():
        return 0
    n = 0
    for line in reversed(p.read_text(encoding="utf-8").splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("kind") != "ship":
            continue
        if r.get("ship_kind") == "fix":
            n += 1
            continue
        break
    return n


def near_deadlines(limit: int = 3) -> list[str]:
    """**開いている前提を、期限の近い順に。**（`config/hypotheses.yaml` を読むだけ・API 0単位）

    門が「代わりに何をするか」を**名指しできないと、種別の語を書き換えて
    通されるだけ**になります。だから、その場で読んで並べます。
    読めなければ黙って空を返します（**門そのものは止めません**）。

    ## **閉じた印は `closed_on:` です**（2026-09-01 に踏んだ）

    ここは長らく `verdict` / `closed` / `result` の3つを見ていました。
    **この台帳のどれでもありません** —— 閉じた前提は `closed_on:` と `outcome:` で
    印を付けます（`src/judgeable.deadlines()` が同じ所を読んでいます）。

    実測 2026-09-01 03:5x: この関数の言う「開いている前提」は **25件**、
    実物は **23件**（`eta.py` も `deadline_check.py` も 23件 と印字）。
    そして期限の近い順に並べるので、**こぼれた2件がちょうど先頭に来ます** ——
    門が名指しした3つのうち2つが、**8日前・9日前に閉じた前提**でした:

        2026-08-26 [per_video] engaged を決めているのは…（`closed_on: 2026-08-23`）
        2026-08-27 [none]      許可の一覧に MCP サーバ名を…（閉じている）

    **この関数の docstring が警告しているとおりの形です** ——
    名指しが偽なら、止められた回は「代わりの手」を探して空振りし、
    結局 種別の語を書き換えて通します。

    **覆る条件**: 台帳が閉じ方を変えたら（`closed_on` をやめたら）、ここも変えること。
    **`judgeable.deadlines()` と同じ鍵を読むこと** —— 2か所が別々の鍵を見た結果が、上の実測です。
    """
    try:
        import yaml  # 遅延 import。この門以外では要りません
        p = Path(__file__).resolve().parent.parent / "config" / "hypotheses.yaml"
        d = yaml.safe_load(p.read_text(encoding="utf-8"))
        items = d if isinstance(d, list) else (d.get("hypotheses") or list(d.values())[0])
        op = [h for h in items if isinstance(h, dict) and h.get("claim")
              and not h.get("closed_on") and not h.get("outcome")
              and not h.get("verdict") and not h.get("closed") and not h.get("result")]
        op.sort(key=lambda h: str(h.get("deadline") or "9999"))
        return [f"{h.get('deadline')} [{h.get('lever') or '?'}] {str(h.get('claim'))[:52]}"
                for h in op[:limit]]
    except Exception:
        return []


#: **日枠が尽きていても撃てる手**（2026-09-01 に足した。**下の `quota_is_out()` の免除は、
#: これが空のときだけ効きます**）。
#:
#: ## なぜ要るか —— **免除の理由が、この repo 自身の実測と逆でした**
#:
#: `quota_is_out()` の註は `docs/trigger_main.md` §4 の表を引いて、
#: 「門が名指しする4つは**どれも枠の向こう側**」と書いていました。
#: **`upload` と `improve` について、それは誤りです。**
#:
#:   `videos.insert` は**日枠を1単位も使いません。尽きていても通ります。**
#:     実測3度 —— `src/auth.py` 8/17 05:2x（`insert` が通るのに `update` が 403）、
#:     08/27 に枠が尽きた 16:47 JST の**後**に 3本（18:05・18:20・18:40）。
#:     `tests/test_insert_never_marked_ok.py` が、その3度を理由ごと守っています。
#:     `upload_cap.reserve_hold()` の返り文も
#:     「**投稿（`videos.insert`）はこの枠を使わないので、止まりません。**」と印字します。
#:
#:   `improve` の5つの道のうち **2つ（台本を書き直す・計算を厚くする）は 0単位**です
#:     （`src/script_writer` / `src/verify` / `src/calc/` は手元のコードで、
#:     YouTube に触りません）。枠が要るのは 題名・説明（50）とサムネ（50）だけで、
#:     しかも **`upload_cap.RESERVE_UNITS = 400` は、その 50 のために残してあります** ——
#:     `_ledger_hold()` の返り文が「残しているのは…**次の1本を良くする書き込み**
#:     （`improve`・50単位）のためです」と、そのまま書いています。
#:
#: ## いちばん強い証拠は、免除を書いた関数の**隣の枝**です
#:
#: 免除しなかったときの `ap.error` は、こう言っています ——
#: 「**`improve` は、いつでも在ります**（規則3）。**この門は、そこへ戻す門です。**」
#: **同じ関数の2つの枝が、逆のことを言っていました。**
#:
#: ## 何を壊していたか（実測）
#:
#: 規則3 が固定された 2026-08-31 以降の ship **88件**: `fix` 56件（64%）／
#: **`improve` 4件（4.5%）／ `upload` 0件**。直近8件は **8件とも `fix`**
#: （`retro.py`「fix に偏っています」）。**枠が尽きるたびに門が開いていたので、
#: 偏りは構造だと説明され、そのまま続いていました。**
#:
#: ## 覆る条件
#:
#: - `videos.insert` が同じ 403 で落ちるようになったら（＝枠が1つに統合された）、
#:   `upload` の行は落とすこと（`upload_cap.RESERVE_UNITS` の覆る条件と同じ日です）
#: - 次に公開される1本が無い窓（`next_slot.next_video()` が `None`）では
#:   `improve` の行は出ません。**そのときは免除が今までどおり効きます**
#: - **読めない回は空を返します** ＝ 免除は今までどおり効く側。
#:   推測で門を締めないため（この repo の他の門と同じ姿勢）
def free_alternatives() -> list[str]:
    """**日枠が尽きていても撃てる手**を並べる（API 0単位）。空なら免除してよい。

    ## `premise` を先頭に置いた理由（2026-09-01・最適化の回）

    この一覧は **`fix` の連の門が「免除してよいか」を決める唯一の入力**です。
    そして `premise`（`config/hypotheses.yaml` に前提を1件 立てる）は
    **ファイルを1つ書くだけで、YouTube に1単位も触りません。**
    つまり **この一覧が空になる回は、もう在りません。**

    **それは骨抜きではなく、逆です。** 免除は「打てる手が本当に無い回」の
    ためのもので、**`premise` はいつでも打てます。**
    `eta.py` が毎周 名指ししている唯一の日付を動かす手を、
    **`fix` を通すために「無い」ことにしていた**のが前の姿でした。

    実測（2026-09-01・`data/runs.jsonl` 08-25 以降 326件）:
    `fix` **248件（76%）**・うち **232件が `--moves 0` 宣言** ／ `verdict` 20件（6%）。
    台帳は 開いている 21件・閉じる 1.86件/日 で **09-12 に空**（`ledger_drain()`）。

    ## **腕の一覧から、引き代の無い腕を落とすこと**（2026-09-01 夕・最適化の回）

    ここは長らく `levers.LEVERS` を**そのまま**並べていました ——
    つまり「前提を1件 立てなさい、腕はこの4つから」と言いながら、
    **その4つに `sub_rate`（この回の `arm_dead_at_inf` ＝ `×10^9` でも到達日は
    出ない）と `density`（天井 ×1.00・オーナーが固定した 1日1本）が入っていました。**

    **これが、死んだ燃料の注ぎ口です。** 実測 2026-09-01 12:4x
    （`deadline_check.dead_ledger()` を書いた回に数えた）:

        開いている 23件 のうち **10件（43%）**が、どう閉じても到達日を動かさない
        （`sub_rate` 6件 ／ `density` 2件 ／ 腕なし 2件）

    **出す瞬間に叱る `levers.lever_notes()` は既に在ります。**
    足りなかったのは**選ぶ前**で、そこがここです。

    **落とすのは腕の名前だけで、`premise` の手そのものは残します** ——
    生きた腕が0本になる回でも、この行は消えません（腕の候補が出ないだけ）。

    ## 覆る条件

    `config/hypotheses.yaml` が読めない回は、この行を出しません
    （在りもしない手を「在る」と言わないこと）。
    **`data/eta.jsonl` が読めない回は、腕を1本も落としません** ——
    **「死んだ腕は無い」ではなく「読めない」**（`levers.arm_state` と同じ約束）。
    """
    out: list[str] = []
    # **前提を立てる手は、いつでも 0単位で在ります**（上の註）。
    hypo = Path(__file__).resolve().parents[1] / "config" / "hypotheses.yaml"
    dropped: list[str] = []
    try:
        from src import levers                                   # noqa: PLC0415

        hint = [k for k in levers.LEVERS if k not in ("none", "gate", "theta")]
        # **引き代の無い腕を落とす**（上の註）。**読めない回は落としません。**
        _st = levers.latest_arm_state(
            Path(__file__).resolve().parents[1] / "data" / "eta.jsonl")
        _caps, _inf = _st.get("caps") or {}, tuple(_st.get("dead_at_inf") or ())
        if _caps or _inf:
            _dead = set(_inf) | {k for k, v in _caps.items()
                                 if isinstance(v, (int, float)) and v <= 1.0}
            dropped = [k for k in hint if k in _dead]
            hint = [k for k in hint if k not in _dead]
    except Exception:                                           # noqa: BLE001
        hint = None
    if hypo.exists():
        out.append(
            "`premise`（**0単位**）— `config/hypotheses.yaml` に前提を1件 立てる。"
            "**`eta.py` の頭の3行めが、どの腕のどの天井を疑うかを毎周 名指しします**"
            "（「立てるべき前提は『その天井は天井ではない』」）。"
            "`lever:` / `side:` / `opened_on:` の3行を忘れないこと ——"
            "空だと `arm_speed` と `ledger_drain` から黙って消えます"
            + (f"（腕は {'／'.join(hint)} のどれか）" if hint else "")
            + (f" **{'／'.join(dropped)} には立てないこと** ——"
               " 引き代がありません（`×10^9` でも 0日、または天井 ×1.00 ＝ 規則）。"
               " 閉じた日に到達日は動きません（`deadline_check.py --fit` に内訳）"
               if dropped else "")
            + (" [!] **引き代のある腕が 1本もありません。**"
               " 立てるなら『その天井は天井ではない』の側です"
               if hint == [] and dropped else ""))
    try:
        from src import next_slot                               # noqa: PLC0415

        nxt = next_slot.next_video()
    except Exception:                                           # noqa: BLE001
        nxt = None
    if nxt:
        vid = str(nxt.get("video_id") or "?")
        out.append(
            f"`improve`（**コードの側は 0単位**）— 次の枠の1本 `{vid}` の"
            "**台本を書き直す／計算を厚くする**（`src/script_writer`・`src/verify`・"
            "`src/calc/`）。枠が要るのは 題名・説明（50）とサムネ（50）だけで、"
            "その 50 は `upload_cap.RESERVE_UNITS = 400` が残しています"
            + _improve_swap_note())
        out.append(
            f"`upload`（**日枠を使いません**）— 焼き直した `{vid}` を上げ直す。"
            "`videos.insert` は日枠が尽きていても通ります"
            "（実測3度・`tests/test_insert_never_marked_ok.py`）")
    return out


def _improve_swap_note() -> str:
    """**`improve` の値札の後半**（＝ 直したコードを、実際に本へ入れる代金）。

    ## なぜ足したか（2026-09-01 11:3x。**前の回が名指しして、直せなかった1件**）

    `free_alternatives()` の `improve` の行は「**0単位**」としか書いていませんでした。
    **0単位 で買えるのは `src/calc/` や `src/script_writer` を直すところまで**で、
    **焼き直した本を同じ枠へ差し替える2手**（`reschedule.py --unschedule` →
    `--move`）は `videos.update` ×2 ＝ **`next_slot.SWAP_UNITS` 単位**、
    **日枠が要ります。**

    **実測 2026-09-01**: きょうだい2回が 09:04 と 10:08 に `src/calc/hendo.py` を
    厚くして `improve` で ship しましたが、**その2件はどちらも今夜 22:00 に出る本に
    入っていません**（`next_slot` が「焼いたのは 08/31 20:26。そのあと N件」と
    毎周 名指ししています）。この回の `split_grid` を入れて **4件**。

    **同じ repo の `next_slot.swap_cost_lines()` は、この代金を正しく印字しています。**
    ズレていたのは、**`fix` の連の門が読む唯一の一覧**（この関数）のほうでした ——
    **門は「0単位で撃てる手が在る」と言って `fix` を止め、
    止められた側が向かった先は「良くしたのに本には入らない」でした。**

    **これは `improve` を止める行ではありません**（規則3 は「出る瞬間まで良くし続けろ」）。
    **値札を最後まで書くだけ**です。枠が尽きている窓では
    「コードまでは進む。本に入れるのは枠が戻ってから」と読めます。

    ## 覆る条件

    - `reschedule` が `videos.update` を使わない道を持ったら、この後半は要りません
      （`next_slot.swap_cost_lines()` の同じ「覆る条件」と一緒に消すこと）
    - 帳面（`quota_ledger`）が読めない回は、**単位だけ**言って窓のことは言いません
      —— **推測で手を止めないため**（`swap_cost_lines()` と同じ姿勢）
    """
    try:
        from src import next_slot                              # noqa: PLC0415

        units = int(next_slot.SWAP_UNITS)
    except Exception:                                          # noqa: BLE001
        return ""
    tail = (f"。**ただし 0単位 で買えるのはコードの側だけです** ——"
            f"焼き直した本を同じ枠へ差し替える2手"
            f"（`--unschedule` → `--move`）は **{units}単位**"
            f"（`videos.update` ×2）で、**日枠が要ります**")
    out, _line = quota_is_out()
    if not out:
        return tail + "（この窓は枠が在ります）"
    try:
        from datetime import datetime, timezone               # noqa: PLC0415

        from src import upload_cap                            # noqa: PLC0415

        when = upload_cap.window_end(datetime.now(timezone.utc)).astimezone(JST)
        return tail + (f" —— **この窓では 403 です。戻るのは "
                       f"{when:%m/%d %H:%M} JST。**"
                       "**それまでに撃てるのはコードまで**"
                       "（焼き直しだけ撃って差し替えないと、古い予約が外せず"
                       "同じ枠に2本 出ます ＝ オーナー規則1 違反）")
    except Exception:                                          # noqa: BLE001
        return tail + " —— **この窓では 403 です**"

def quota_is_out() -> tuple[bool, str]:
    """**Data API の日枠が、この窓でもう尽きているか**（`(尽きているか, 1行)`）。

    ## なぜ `fix` の門がこれを読むか（2026-09-01 に踏んだ）

    `FIX_RUN_CAP` の註は、自分の逃げ場をこう書いています ——
    「**オーナーが固定した規則（1日1本）は毎日 `upload` を要求しているので、
    逃げ場のない門にはなりません。**」

    **枠が尽きている窓では、その前提が半分だけ崩れます。**

    ##### **上の表は誤りでした**（2026-09-01 に直した。**この註が最初に書いた表**）

    ここには `docs/trigger_main.md` §4 の表を引いて
    「`upload` は `videos.insert` 1,600単位 ← 枠」「**枠が尽きた回に残るのは
    事実上 `fix` だけ**」と書いてありました。**この repo が3度 実測で
    否定しているほうです** —— `videos.insert` は日枠を1単位も使わず、
    **尽きていても通ります**（`tests/test_insert_never_marked_ok.py`／
    `upload_cap.reserve_hold()` の返り文）。`improve` も、5つの道のうち
    **台本を書き直す・計算を厚くするの2つは 0単位**で、残る 50単位 は
    `upload_cap.RESERVE_UNITS = 400` が**その improve のために**残しています。

    **本当に枠の向こう側なのは `means` と、読みで閉じる `verdict` だけ**です。

    **証拠は、この門の隣の枝にありました** —— 免除しなかったときの `ap.error` が
    「**`improve` は、いつでも在ります**（規則3）。**この門は、そこへ戻す門です。**」
    と印字しています。**同じ関数の2つの枝が、逆のことを言っていました。**

    だから免除は **`free_alternatives()` が空のときだけ**にしました。
    実測 2026-09-01 03:5x（この関数を足した回）: 積んだ消費 **13,353単位** /
    枠 10,000・**403 を 43回** 観測。`scripts/reschedule.py --list` は
    `channels.list` の 403 で traceback、`eta.py` は
    「**この回に閉じられる前提はありません**（いちばん早い期日は1日後）」。
    **その回は「5つのうち4つが最初から選べなかった」と読みました。
    正しくは 2つ**（`means` と `verdict`）—— `upload` と `improve` は
    撃てました。**この誤読の代金**は `data/runs.jsonl` に出ています:
    規則3 が固定された 08-31 以降の ship 88件 で `improve` **4.5%** ／
    `upload` **0件**、直近8件は **8件とも `fix`**。

    ## **これは門の骨抜きではありません**（そのつもりで足したら、意味がない）

    - 判定は**観測した 403** です（`upload_cap.day_quota().open`）。
      **こちらの見積りではありません** —— 「尽きたことにする」ことはできません
    - **通した回は残ります**（`note_fix_gate(..., waived=True)`）。
      `kind="fix_gate"` の行に `waived` が立つので、**次に来た回は
      「止めた回数」と「枠のせいで通した回数」を別々に数えられます**
    - 枠が戻っている窓では、門はいままでどおり止めます

    ## 覆る条件

    `upload_cap.day_quota()` が読めない回は「開いている」を返します
    （あの関数の姿勢と同じ ——「読めないことを閉じていると読まない」）。
    枠が広がって 403 が出なくなれば、ここは自動で黙ります。
    **`FIX_RUN_CAP` の註の3つの覆る条件は、そのまま生きています。**
    """
    try:
        from src import upload_cap                              # noqa: PLC0415

        q = upload_cap.day_quota()
    except Exception as exc:                                    # noqa: BLE001
        return False, f"（日枠は読めませんでした: {str(exc)[:60]}）"
    if getattr(q, "open", True):
        return False, ""
    return True, str(getattr(q, "line", "") or "**日枠が尽きています**")


def note_fix_gate(what: str, run_len: int, waived: bool = False) -> None:
    """**止めたことを残す。**

    **止めた回数を数えられない門は、効いたかどうかも数えられません。**
    次に来た回は、`fix` の割合が下がったのか、それとも種別の語を
    書き換えて通しただけなのかを、この行と `drift.py` の比で見分けます
    （`kind="fix_gate"`。`drift.py` は `kind != "ship"` を読み飛ばすので、
    漂流の比そのものは汚しません）。
    """
    try:
        with MARKS.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "at": datetime.now(JST).isoformat(timespec="seconds"),
                "session": actor_id() or "(不明)",
                "kind": "fix_gate",
                "run_len": run_len,
                # **止めたのか、枠のせいで通したのか。** これが無いと、
                # 次の回は `fix_gate` の行数を「効いた回数」と読みます
                # （`quota_is_out()` の註）。
                "waived": bool(waived),
                "what": what[:200],
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass


def ship_kind_of(what: str, kind: str | None = None) -> str:
    """ship の種別。**明示された欄があればそれ。無ければ `what` の頭の語。**

    ## なぜ欄を足したか（2026-08-26・最適化の回）

    `scripts/drift.py` の `_kind_of()` は `what` の**先頭の語だけ**を見ます。
    その docstring は「**欄を足すのが本筋ですが、既存の240件を読めなくなる**ので」と
    書いて、頭の語を読むほうを選んでいました。

    **その理由は当たっていません。** 欄を足しても、欄の無い古い行は
    頭の語で読めばよいだけです（この関数がそうしています）。

    **選ばなかった代償は実測できます**（2026-08-26 18:5x）:

        ship 381件 のうち **155件（41%）が「その他」**

    中身は「その他」ではありません。同じ窓に、こういう行が入っています ——
    「**長尺1本を 09/07 20:00 JST に予約（VG6EYTKXl1M）**」（＝ `upload`）、
    「**M9（配信の上限は…）を実データで判定**」（＝ `verdict`）。
    **upload も verdict も、実数はもっと多い。**

    そして `drift.py` は `verdicts_tail == 0` を**漂流の門**に使っています
    （`drifting = bool(od_now) and verdicts_tail == 0`）。
    **門が、4割こぼす目盛りの上に乗っていました。**

    ## 覆る条件

    `data/runs.jsonl` の「その他」が 5% を下回ったら、この欄は要りません
    （＝頭の語の慣習が守られている）。**それまでは書き続けること。**
    """
    if kind:
        return kind
    head = (what or "").strip().lower()
    for k in SHIP_KINDS:
        if head.startswith(k):
            return k
    return "その他"


run_marker_ship_kind = ship_kind_of


def ship(what: str, closes: list[str] | None = None, lever: str | None = None,
         moves: int | None = None, reflect: bool = True,
         kind: str | None = None) -> int:
    """**この回が「出したもの」を1行残す。**（2026-08-15 追加）

    オーナーの指示（原文）: **「子が、少しの作業で終わるの直して」**

    分析して日誌を書いて終わる回が続いていました（8/12〜8/15 の全部）。
    **文書に「小さくてよい」と書いてあったのが原因**なので、まず文書を直し、
    そのうえで**機械で確かめられる形**にしたのがこの印です。

    `scripts/stop_check.sh` が、start はあるのに ship が無いまま終わろうと
    したときに引き止めます。**引き止めるだけで、最後は通します**
    （止まったまま死ぬほうが、目標に対して確実に悪いため）。

    **何を ship と呼ぶか**（`docs/trigger_main.md` §4 の最低ライン）:

        upload   動画を1本、予約まで入れた
        means    手段の台帳（docs/MEANS.md）の1件を、実際に動かした
        verdict  期限の来た前提を、実データで判定した
        fix      実測で見つかった欠陥を塞いだ（道具・生成・投稿のどれか）

    ## `--lever`（2026-08-19 21:2x に足した。**オーナー指示**）

    原文: **「毎回達成までの予測して。20万の達成。それ以外のやつだけしかしてない。
    それを早めるための行動考えてから進めるのは毎回の最初にやること」**

    **上の4種は「何をしたか」しか言いません。** `fix` も `means` も、
    予測日を動かす腕とは無関係に打てます —— 実際、直近10回の ship は
    **1件も日付を動かす腕を選んでいません**（`src/levers.py` の説明）。

    だから ship には**どの腕を動かしたか**を必ず添えます。語彙は
    `src.levers.LEVERS` で、**`scripts/eta.py` が印字する腕と1対1**です。
    **`none` も正しい答えです**（道具・手順の整備）。禁じると嘘の宣言が増えるだけで、
    数えたい「10回のうち何回が動かす腕だったか」が測れなくなります。

    **分析・日誌・文書の整理だけは ship ではありません。** それは前提であって、
    出したものではない。

    ## `--closes`（2026-08-16 に足した。**4回運ばれた申し送り**）

    `retro.py` の持ち越しは「潰したと日誌が宣言した語」を落とします。
    **その宣言は、いままで散文でした** ——「〜はこの回で閉じました」と手で書く約束。
    **約束は3回破れ、そのたびに読む側を直しています**:

        09:5x  「**一度閉じた後の再発**」を宣言と誤読 → `critique_queue` が黙った
        10:3x  引用符の中の「`閉じました`」を宣言と誤読 → **同じ穴の3枚目**
        06:3x  `_template.py` は閉じたのに**宣言が書かれず**、4回運ばれた

    **前2つは「書きすぎ」、3つめは「書き忘れ」で、向きが逆なのに原因は同じ**です ——
    **宣言が、人の書いた散文の中にしかありませんでした。** 語彙を足しても、
    次に日誌が新しい言い回しをすれば戻ります（実際3回戻りました）。

    だから**出したものと一緒に、機械が構造で残します。** 散文の読み取りは
    残してあります（過去の日誌はそれでしか読めないため）が、
    **これから先は、こちらが正本です。**

        python scripts/run_marker.py --ship "fix: ..." --closes critique_queue

    一緒に**そのときの日誌の行数**を残すのは、`retro.py` が
    「宣言より前の言及だけ落とす」を行番号でやっているからです。
    行数を渡せば、**そのとき既にあった申し送りだけが黙り、
    この後に書かれた言及は「一度閉じた後の再発」として残ります**（意図どおり）。
    """
    me = actor_id() or "(不明)"
    rec = {
        "at": datetime.now(JST).isoformat(timespec="seconds"),
        "session": me,
        "kind": "ship",
        "what": what,
    }
    # **種別を、書く側が残します**（2026-08-26。理由は `ship_kind_of()`）。
    rec["ship_kind"] = ship_kind_of(what, kind)
    if rec["ship_kind"] == "その他":
        print(f"[marker] [!] **種別が読めません**（`{'／'.join(SHIP_KINDS)}` のどれでもない）。"
              f"`drift.py` の「直近20回の verdict」はこの欄を数えるので、"
              f"**この1件は漂流の門から見えません。**"
              f" 直すには `--kind <種別>` を足すか、`--ship \"verdict: ...\"` の形で書くこと")
    # **腕は `what` より先に置きません**（読む側が `what` の頭で見分けているため）。
    if lever:
        rec["lever"] = lever
    # **「何日ぶん早める見込みか」を、出した時点で残す**（2026-08-20 08:0x・オーナー指示3回目）。
    # 原文: 「毎回**達成日時を早めることを考えてから**進めるようにして」
    #
    # **考えたことは、外から見えません。** 見えるようにする方法は1つで、
    # **先に言って、後で突き合わせる**ことです。だから ship には
    # 「この作業で予測日が何日動く見込みか」と、**そのとき出ていた予測日**を添えます。
    # 次の回の `levers.report()` が、宣言と実際の差を並べます ——
    # **当たっていなくてよい。** 当たらないと分かることのほうが、
    # 何も言わずに進むより速い（外した回は、その腕の効き目を1つ潰したことになる）。
    if moves is not None:
        rec["moves"] = moves
    # **そのとき出ていた「名指し」と「その腕の天井」も残す**（2026-08-24）。
    #     残さないと、あとから「名指しに従った回と、外した回で、
    #     実際に動いた日数が違ったか」を**誰も測れません。**
    #     いまは外した回が数えられていないので、`lever_hint` は
    #     **毎回計算されて、誰にも読まれない数**でした。
    _arm = levers.latest_arm_state(ETA_LOG)
    if lever and _arm.get("hint"):
        rec["lever_hint"] = _arm["hint"]
        rec["lever_followed"] = (lever == _arm["hint"])
        # **「名指しを外した」と「外せと言われて外した」を分けること**
        #     （2026-08-26 に踏んだ）。`eta.py` は、名指しした腕の測定に
        #     もう答えが返る回に **「この測定に ship を使わないこと。
        #     別の腕を引くこと」** と印字します。そのとおりに動いた回が、
        #     ここで `lever_followed=False` として残っていました。
        #     受け取り帳 `68e90017` が数え直す 12/98 は、その分だけ嘘です。
        if _arm.get("hint_covered"):
            rec["lever_hint_covered"] = _arm["hint_covered"]
    if lever and lever in _arm.get("caps", {}):
        rec["lever_cap"] = _arm["caps"][lever]
    # --- **覆らない死に方の腕だけは、書き込む前に断る**（2026-09-02・最適化の回）---
    #     `levers.lever_notes()` は既に叱っていました。**それでも 08/31 以降に
    #     20件 通り、うち 4件 は負の `--moves`**（＝早まると宣言）です
    #     （`levers.blocked()` の docstring に、この回に撃った内訳）。
    #     **註が効いていないことの、2度目の実測**です ——
    #     1度目は 2026-08-19 の `--lever` そのもの（この file の
    #     「**註や警告ではなく、通さないことだけが効いています**」）。
    #     断るのは**腕の宣言だけ**で、仕事は捨てません（文面がそう言います）。
    #     **一般の `cap <= DEAD_CAP` は断りません** —— あちらは前提が
    #     未判定なら覆るからで、`lever_notes` の判断をそのまま残します。
    if lever:
        _block = levers.blocked(lever, _arm)
        if _block:
            for _ln in _block:
                print(_ln)
            return 2
    target, days, basis = _eta_target()
    if target is not None:
        rec["eta_target"] = target
        # **物差しの名前も残すこと。** 2026-08-20 18:xx に予測日は
        # 「腕を据え置いた線」から「軌跡」へ替わりました。**替わった前後の
        # 日付を引き算すると、チャンネルは何も変わっていないのに
        # 「149日 遠のいた」が出ます**（`levers.reconcile` が飛ばします）。
        rec["eta_basis"] = basis
    if days is not None:
        rec["eta_days"] = days
    closes = [c.strip() for c in (closes or []) if c.strip()]
    # **語彙は、書き込む前に読むこと**（2026-08-17。**入れた直後に自分で踏みました**）。
    # `carry_over()` は `recorded_closures()` を読むので、先に `_append` すると
    # **たった今書いた宣言そのものがその語を黙らせ、一覧から消えます。**
    # 結果、正しい語を書いた回にかぎって「一覧に無い」と言われる ——
    # **警告が、当たりでだけ鳴らない**という向きの壊れ方でした。
    # **`--closes` が無い回でも読みます**（2026-08-17。`_suggest_undeclared` の理由）。
    known = _known_vocab()
    if closes:
        rec["closes"] = closes
        rec["journal_lines"] = journal_lines()
    line = _append(rec)
    print(f"[marker] 出したものを記録しました: {line}")
    if closes:
        print(f"[marker] **潰した宣言を {len(closes)} 件、構造で残しました**"
              f"（{' / '.join(closes)}）。")
        print("         `retro.py` の持ち越しから、この語より前の言及が落ちます。")
        _warn_unknown(closes, known)
    if lever:
        print(f"[marker] 腕: **{lever}** —— {levers.LEVERS[lever]}")
        if lever == "none":
            print("         **この回は予測日を動かしません。** 理由を docs/JOURNAL.md に1行書くこと。")
        for _ln in levers.lever_notes(lever, _arm):
            print(_ln)
    if moves is not None:
        print(f"[marker] 予測日の見込み: **{moves:+d}日**"
              + (f"（いまの予測 {rec.get('eta_target')}）" if rec.get("eta_target") else "")
              + " —— 次の回が、実際に動いた日数と突き合わせます。")
        if moves == 0 and lever in levers.MOVING:
            # **`gate` は 0日 が正しい答えです**（2026-08-30 に足した）。
            #     床(d)＝門が閉じる日＋軌跡の日数 は、閉じた実績が
            #     `resume_gate.MIN_CLOSED_FOR_RATE` 件 たまるまで**日付を出しません**。
            #     つまり門を1件 閉じても、そこまでは到達日が動きようがない。
            #     ここで叱ると、**次の回は 0 以外を作って黙らせる側**へ倒れます ——
            #     `--moves` は当てるための欄ではないので、それは台帳を汚すだけです。
            if lever == "gate":
                print("         **`gate` の 0日 は正しい答えです。**"
                      " 床(d) は、閉じた実績が"
                      f" {resume_gate.MIN_CLOSED_FOR_RATE}件 たまるまで日付を出しません"
                      "（`src/resume_gate.rate_per_day`）。"
                      " **0 以外を作って埋めないこと。**")
            else:
                print("         [!] **動かす腕を選んで 0日** と言っています。"
                      " 効くまでに時差があるなら、それを JOURNAL に1行書くこと。")
    _suggest_undeclared(what, closes, known)
    # **出したら、その場で予測へ入れ直す**（2026-08-20・オーナー指示。原文:
    # **「毎回の実行で予測するように言ったはずなので、毎回その予測に反映して」**）。
    #
    # **ここに繋いだ理由は1つ**です —— `--ship` は、この周でただ1つ
    # **飛ばせない呼び出し**だからです（`stop_check.sh` が印の無い回を引き止めます）。
    # 手順書に「周の終わりに反映すること」と書くだけでは足りません:
    # **2026-08-20 に註へ書いたものは、その日のうちに全部素通りしました。**
    #
    # 反映は API を叩きません（出発点と同じ実測で解き直すだけ）。
    # **実測 1分37秒〜5分30秒**（下の `timeout=900` の註と同じ数字にすること）。
    # **「約4秒」と書かないこと** —— その数を信じた 180秒 の門で、
    # 反映が毎回 落ちていました。2026-08-26 に3か所そろえました。
    # **失敗しても ship は成功のまま返します** —— 反映は記録であって門ではない。
    if reflect:
        _reflect_now(what)
    return 0


# **検査から呼ばれたときは撃たない**（2026-08-20。**入れた当日に自分で踏みました**）。
#
# `tests/test_closes_vocab.py` は `run_marker.ship()` を**直接**呼びます。
# 反映を既定にした瞬間、その検査が**本物の `data/eta.jsonl` に 19行**書きました
# （1回 3.3秒 × 19 ＝ 検査も1分遅くなる）。`tests/conftest.py` が
# `src/alerts.py` の台帳で同じ形を 2026-08-17 に踏んで塞いでいます —— **同じ傘に入れます。**
SKIP_REFLECT_ENV = "YT_SKIP_REFLECT"


def _record_supply() -> None:
    """**反映の前に、在庫の点を1つ積む**（`python -m src.supply --record`・1秒未満）。

    ## なぜ要るか（2026-08-26 07:4x に実測して足した）

    `eta.py --reflect` は「この回で動いた入力」を出しますが、**在庫（`stock`）と
    作る速さ（`make_rate_per_day`）は `data/supply.jsonl` の点の差からしか出ません。**
    点を積むのは `python -m src.supply --record` だけで、**`topic_forge` も
    `batch_build` も積みません。** つまり:

    - テーマを6件 forge して長尺を4本 予約した回が、
    - `--ship` を打つと **「この回で動かせる入力は、1つもありませんでした」**

    実測（この回）。`--ship` の反映は 0件。そのあと `supply --record` を撃って
    `--reflect` をもう一度撃つと、**同じ回・同じ作業のまま 2件**出ました:

        density_surfaces:   {…} → {…}
        make_rate_per_day:  18.2 → 19.3

    **「動かせる入力が1つも無い」は、この回が予測の入力に触っていないという意味だと
    書いてあります**（`eta.reflect` の印字）。**在庫を触った回では、それが嘘になります。**
    `retro.py` の申し送りが「18周のあいだ入力が1つも動いていない」と言い続けていたのは、
    **少なくとも一部はこれ**です —— 動いていたのに、測る点が積まれていなかった。

    **止めないこと。** 積めなくても反映へ進みます（記録であって門ではない）。
    """
    import subprocess
    try:
        r = subprocess.run(
            [sys.executable, "-m", "src.supply", "--record"],
            cwd=str(Path(__file__).resolve().parent.parent),
            capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"[marker] 在庫の点を積めませんでした: {type(exc).__name__}: {exc}")
        print("         **回は止めません。** 反映の『動いた入力』が"
              "在庫ぶん少なく出ます（`python -m src.supply --record`）。")
        return
    if r.returncode != 0:
        print(f"[marker] 在庫の点を積めませんでした（終了コード {r.returncode}）。"
              "**回は止めません。**")
        return
    print("[marker] 在庫の点を積みました（`supply --record`）—— "
          "**これが無いと、在庫を増やした回の反映が『0件』になります。**")


def _reflect_now(what: str) -> None:
    """`scripts/eta.py --reflect` を呼ぶ。**この回を止めないこと。**"""
    import subprocess
    if os.environ.get(SKIP_REFLECT_ENV):
        return
    print("")
    # **在庫の点は、反映より先に積むこと**（理由は `_record_supply` の docstring）。
    _record_supply()
    print("[marker] **予測へ入れ直します**（この回で動いた入力 → 日付の前後差）")
    try:
        r = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent / "eta.py"),
             "--reflect", "--note", what[:120]],
            cwd=str(Path(__file__).resolve().parent.parent),
            # **180秒では届きません**（2026-08-24 に実測して 900 へ上げた）。
            # 当時の `--reflect` は **330秒**、`eta.py` 全体は約9分。
            # `CLAUDE.md` は「約4秒」と書いているが、それは段が増える前の数字。
            # 180 のままだと `TimeoutExpired` で毎回落ち、**反映が1度も残らない** ——
            # しかも「回は止めません」と出るので、**落ちたことに気づかないまま次へ行く。**
            # 上げすぎても害は小さい（反映が終われば即座に返る）。
            #
            # **実測 2026-08-31（最適化の回）: `--reflect` は 330秒 → 28.4秒**
            # （`eta.py --offline` 全体も「300秒で未完」→ **67.7秒**）。
            #     直したのは `src/form_record.per_video_best()` の憶えです ——
            #     鍵が「既定の引数で呼んだか」だったのに、唯一の呼び手が常に引数を
            #     渡すので **一度も当たっていませんでした**。
            #     実測: 150秒 のうち **139.4秒（93%）**がその中・**623回** 呼ばれる。
            #     検査は `tests/test_form_record_memo.py`（直しを戻すと 2件 落ちます）。
            # **900 は下げません** —— 速くなったのはこの1か所で、他の段が
            #     重くなったときに黙って落ちるほうが高くつきます。
            #     **「速くなったから縮める」は、次の回の落ち方を静かにします。**
            capture_output=True, text=True, timeout=900)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"[marker] 反映を撃てませんでした: {type(exc).__name__}: {exc}")
        print("         **回は止めません。** `python scripts/eta.py --reflect` を手で撃つこと。")
        return
    out = (r.stdout or "").strip()
    if out:
        print(out)
    if r.returncode != 0:
        print(f"[marker] 反映が失敗しました（終了 {r.returncode}）。"
              f"{(r.stderr or '').strip()[-300:]}")
        print("         **回は止めません。** 理由を docs/JOURNAL.md に1行書くこと。")


def _known_vocab() -> tuple[set[str], dict[str, list[str]]] | None:
    """**いま「潰した」と言ってよい語**を、実物から集める。

    **`ship()` が `_append` する前に呼ぶこと。** あとから呼ぶと、
    たった今書いた宣言が `recorded_closures()` 経由で自分の語を黙らせ、
    **正しい語のときだけ「一覧に無い」と鳴ります**（入れた回に実際に踏みました）。

    読めなければ `None`。**その回は黙って通します**（記録は落とさない）。
    """
    root = Path(__file__).resolve().parent.parent
    try:
        for p in (str(root), str(root / "scripts")):
            if p not in sys.path:
                sys.path.insert(0, p)
        from retro import carry_over
        from src import alerts

        carried, dropped = carry_over()
        known = set(carried) | {r.key for r in alerts.table()}
        # 物の名前として沈めた語は「一覧に無い」と言わない（**外したのはこちら側の都合**）
        for toks in dropped.values():
            known.update(toks)
        return known, carried
    except Exception as exc:                      # 読めないなら黙って通す
        print(f"         （持ち越しの一覧を読めませんでした: {exc}）")
        return None


def _warn_unknown(closes: list[str],
                  known: tuple[set[str], dict[str, list[str]]] | None = None) -> None:
    """**その語が、本当に一覧に載っているか。**（2026-08-17。3回運ばれた申し送り）

    `--closes` は**どんな語でも黙って受け取ります。** 書き間違えても、
    もう潰れている語を書いても、何も言いません。**気づく口がどこにもない**ので、
    宣言だけが `data/runs.jsonl` に残り、**持ち越しは一覧に残ったまま**になります
    （散文の宣言を構造へ移した理由がこれなのに、構造の側に同じ穴がありました）。

    **止めません。** 出したものの記録が、語の綴りで落ちるほうが確実に悪い
    （投稿が途切れるのと同じ形で、記録が欠けます）。**言うだけです。**

    見る先は2つ。**どちらも実物から引きます**（手で語彙を並べない）:

    - `retro.py` の持ち越し（`carry_over()`。**同じ計算を呼びます**）
    - `src/alerts.py` の一覧の鍵（`data/alerts.jsonl` に鳴った記録があるもの）
    """
    pair = known if known is not None else _known_vocab()
    if pair is None:
        return
    vocab, carried = pair
    unknown = [c for c in closes if c not in vocab]
    if not unknown:
        return
    print(f"  [!] **一覧に無い語が {len(unknown)} 件あります**: {' / '.join(unknown)}")
    print("      `retro.py` の持ち越しにも `src/alerts.py` の鍵にも載っていません。")
    print("      **書き間違いなら、この宣言は何も黙らせません**"
          "（記録は残したので、正しい語でもう一度打ち直せます）。")
    if carried:
        print(f"      いま出ている持ち越し: {' / '.join(sorted(carried)[:8])}")


def _mentions(text: str, token: str) -> bool:
    """出したものの1行が、その語に触れているか。

    **パスの形の語だけ、見出しでも拾います。** 日誌もコミットも
    `docs/CONSTRAINTS.md` を「**CONSTRAINTS に節を足した**」と書くので、
    完全一致だけでは実際に潰した回を取りこぼします（下の実例がまさにこれ）。

    **拡げるのはここまで。** `status.py` のような語を `status` まで緩めると、
    `session_status` に当たります —— **当たりを含まないまま育つ一覧**が
    6件目になるので、`/` を含む語（＝パス）に限っています。
    """
    if token in text:
        return True
    if "/" not in token:
        return False
    stem = token.rsplit("/", 1)[-1]
    stem = stem.rsplit(".", 1)[0] if "." in stem else stem
    return len(stem) >= 4 and stem in text


def _suggest_undeclared(what: str, closes: list[str],
                        known: tuple[set[str], dict[str, list[str]]] | None) -> None:
    """**逆向きの穴**: 一覧に載っている語を潰したのに、宣言しなかった回。
    （2026-08-17 に足した。**この節を書いた回が、その実例に当たっています**）

    `_warn_unknown` は「**載っていない語を宣言した**」を見ます。
    その逆 ——「**載っている語を潰したのに、宣言しなかった**」—— は誰も見ていません。
    `docs/trigger_main.md` §4 は「`--closes carry_over` と、**潰した語そのものの両方**」と
    書いてありますが、**約束は散文なので、片方だけ書いても何も起きません。**

    実例（8/17 15:1x）:

        --ship "fix: CONSTRAINTS に「repo を触らずにできること」の節（3回持ち越し…）"
        --closes carry_over            ← **語そのものが無い**

    結果、`docs/CONSTRAINTS.md` と `repo を触らずにできること` は
    **潰れているのに一覧に残り**、次の回（15:3x）は §2.7 の
    「持ち越しから選ぶのが既定」に従って**それを選びかけました**
    （`CONSTRAINTS.md` を開いて、既に節があることに気づいた）。
    **一覧が当たりを含まないまま育つ**の、5件目と同じ形です。

    **止めません。言うだけです**（`_warn_unknown` と同じ理由。
    出したものの記録が、語の綴りで落ちるほうが確実に悪い）。
    そして**この一覧自身も当たり率で畳まれます**（鍵 `undeclared_close`）。
    """
    if known is None:
        return
    _, carried = known
    hits = [t for t in carried
            if t not in closes and _mentions(what, t)]
    if not hits:
        return
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from src import alerts
        r = alerts.ring("undeclared_close", len(hits))
    except Exception:
        r = None
    if r is not None and r.folded:
        print(r.line)
        return
    print(f"  [!] **出したものが、持ち越しの語に {len(hits)} 件触れています**"
          f"（宣言はされていません）: {' / '.join(hits)}")
    print("      潰したのなら、**語そのものも宣言すること**"
          "（`carry_over` だけでは一覧から落ちません）:")
    args = " ".join(f'--closes "{t}"' for t in hits)
    print(f"      python scripts/run_marker.py --closes-add {args}")
    print("      **触れただけで潰していないなら、何もしなくてよい。**")


def closes_add(words: list[str]) -> int:
    """**この回の直近の ship に、宣言を足す。** 新しい ship は作らない。

    ## なぜ要るか（2026-08-18。**`undeclared_close` が 4回鳴って当たり0**）

    `_suggest_undeclared` は「潰した語そのものも宣言せよ」と正しく言いますが、
    直し方として **`--ship` をもう一度打て**と案内していました。
    **`--ship` は追記なので、同じ成果が `data/runs.jsonl` に2行**入ります ——
    `retro.py` の「出したもの」の種類別も、`status.py` の件数も、二重に数える。

    **つまり、言われたとおりにすると帳簿が壊れます。** だから直前の4回は
    どれも従われず、**鳴った4回・当たり0**でこの一覧は畳まれる寸前でした。
    **当たらない理由が「気づかない」ではなく「従うと悪くなる」**なので、
    畳んでも直りません。**直すのは直し方のほうです。**

    足す先は**この回（同じ `session`）の最後の ship** に限ります。
    前の回の記録は、その回の判断の記録なので触りません。
    """
    words = [w.strip() for w in words if w.strip()]
    if not words:
        return 0
    # **`actor_id()` で見ること。** 素のIDだと、同じ親から同時に走っている
    # 隣のサブエージェントの ship を掴みます（`actor_id()` の説明の 2）。
    me = actor_id()
    lines = [x for x in (MARKS.read_text(encoding="utf-8").splitlines()
                         if MARKS.exists() else []) if x.strip()]
    target = None
    for i in range(len(lines) - 1, -1, -1):
        try:
            rec = json.loads(lines[i])
        except json.JSONDecodeError:
            continue
        if rec.get("kind") == "ship" and (not me or rec.get("session") == me):
            target = (i, rec)
            break
    if target is None:
        print("[marker] **この回の ship がまだありません。**"
              "`--ship` を先に打つこと（`--closes-add` は足すだけです）。")
        return 1
    i, rec = target
    # **語彙は、書き込む前に読むこと**（`ship()` と同じ理由。書いてから読むと
    # **たった今足した宣言が、その語を持ち越し一覧から消す** ——
    # 結果、正しい語を足した回にかぎって「一覧に無い」と言われます。
    # `ship()` にはこの註があるのに、**新しく足した道には無かった**。
    # **片方だけ**の、また1件）。
    known = _known_vocab()
    before = list(rec.get("closes") or [])
    rec["closes"] = before + [w for w in words if w not in before]
    added = [w for w in rec["closes"] if w not in before]
    rec.setdefault("journal_lines", journal_lines())
    lines[i] = json.dumps(rec, ensure_ascii=False)
    MARKS.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if not added:
        print(f"[marker] もう宣言されています（{' / '.join(words)}）。")
        return 0
    print(f"[marker] 直近の ship に宣言を {len(added)} 件足しました"
          f"（{' / '.join(added)}）。**新しい ship は作っていません。**")
    _warn_unknown(added, known)
    return 0


def show() -> int:
    """直近の回を出す。**空きが大きければ、それが一番大事な観測。**"""
    recs = _records()
    if not recs:
        print("[marker] **印が1件もありません。** 子が一度も走り終えていない。")
        print("         立て方そのものが壊れている疑い"
              "（`source_url` と `source_revision` を確かめること）。")
        return 1
    now = datetime.now(JST)
    print(f"[marker] 直近 {min(8, len(recs))}件:")
    for r in recs[-8:]:
        try:
            age = (now - datetime.fromisoformat(r["at"])).total_seconds() / 60
            kind = r.get("kind", "start")
            tail = f"  ← **出した**: {r['what']}" if kind == "ship" else ""
            print(f"    {r['at']}  {age:>5.0f}分前  {kind:<5} {r['session']}{tail}")
        except (KeyError, ValueError):
            print(f"    （読めない行）{r}")

    # **走った回のうち、何も出さずに終わった割合。**
    # ここが高いままなら、直すのは間隔ではなく1回の中身です。
    starts = [r for r in recs if r.get("kind", "start") == "start"]
    shipped = {r.get("session") for r in recs if r.get("kind") == "ship"}
    recent = starts[-10:]
    empty = [r for r in recent if r.get("session") not in shipped]
    if recent:
        print(f"  直近 {len(recent)}回のうち、**何も出さずに終わった回: {len(empty)}**")
        if len(empty) > len(recent) / 2:
            print("  [!] **半分以上が空回りです。** 分析だけで終える回が既定に"
                  "なっていないか疑うこと（`docs/trigger_main.md` §4 の最低ライン）。")

    try:
        gap = (now - datetime.fromisoformat(recs[-1]["at"])).total_seconds() / 60
    except (KeyError, ValueError):
        return 1
    # **しきい値は間隔の2周ぶん。** 1周ぶんだと、正常に動いていても毎回鳴ります
    # （2026-08-10 に毎時→6時間おきへ変えたとき、180分のままだと**必ず鳴る**状態になった）。
    # **鳴りっぱなしの警告は、無い警告と同じです。**
    # 間隔を変えたら、ここも変えること（正本は `docs/TRIGGER.md` の cron）。
    if gap > INTERVAL_MIN * 2:
        print(f"  [!] **{gap:.0f}分（{gap / 60:.1f}時間）どの子も走り終えていません。**")
        print("      親から見ると子は立っているので、ここでしか気づけません。")
        print("      **なぜ止まったかを JOURNAL に書くこと。**")
        return 1
    print(f"  直近の回は {gap:.0f}分前。**周は回っています。**")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="子: 走った印を付ける（最初に）")
    ap.add_argument("--ship", metavar="内容",
                    help="子: この回で出したものを記録する（最低ラインの1件）")
    ap.add_argument("--lever", metavar="腕", choices=sorted(levers.LEVERS),
                    help="**この成果が動かす腕**（`--ship` と対。オーナー指示 2026-08-19 21:2x）。"
                         + levers.vocab_help()
                         + "。**`none` も正しい答え**だが、理由を JOURNAL に書くこと")
    ap.add_argument("--moves", metavar="日数", type=int,
                    help="**この成果が予測日を何日動かす見込みか**（`--ship` と対。"
                         "早まるなら負、遠のくなら正、動かさないなら 0）。"
                         "オーナー指示 2026-08-20 08:0x「毎回達成日時を早めることを"
                         "考えてから進めるようにして」。**次の回が実際の差と突き合わせます**")
    ap.add_argument("--kind", metavar="種別", choices=sorted(SHIP_KINDS),
                    help="**この ship の種別**（`upload`／`means`／`verdict`／`fix`）。"
                         "省くと `--ship` の頭の語から読みます。"
                         "**読めないと `drift.py` の漂流の門から見えません**"
                         "（実測 2026-08-26: 381件 中 155件 が読めていませんでした）")
    ap.add_argument("--closes", metavar="語", action="append", default=[],
                    help="この ship で潰した持ち越しの語（`retro.py` の一覧に出る形で。"
                         "何度でも書ける）。**語が `-` で始まるときは "
                         "`--closes=--closes` と等号で書くこと**"
                         "（argparse が次の旗と読みます。持ち越しには "
                         "`--closes` `--next` のような旗の名前が実際に載ります）")
    ap.add_argument("--no-reflect", action="store_true",
                    help="**この ship の後で予測へ入れ直さない**（既定では入れ直します。"
                         "オーナー指示 2026-08-20「毎回その予測に反映して」）。"
                         "**逃げ道であって、既定ではありません** —— 使ったら理由を "
                         "JOURNAL に1行。`stop_check.sh` が終わる前にもう一度訊きます")
    ap.add_argument("--claim", metavar="内容",
                    help="**いまから取りかかるものを1行で残す**（`claims()` の註）。"
                         "`--write` が、直近60分に他の回が書いたぶんを出します —— "
                         "**何をやるか決める前**に見えるように。**予約ではありません**が、"
                         "ぶつかると片方は捨てになります（08-26 に 30分 払った）")
    ap.add_argument("--seen", metavar="ID",
                    help="**名指しされた回を見にいって、拾うものが無かった**ことを"
                         "残す（`sibling_check` がもう名指ししません）。"
                         "`--why` と対で書くこと")
    ap.add_argument("--why", metavar="理由",
                    help="`--seen` の理由（1行）。**必須**")
    ap.add_argument("--closes-add", metavar="語", action="append", default=[],
                    help="**この回の直近の ship に**宣言を足す（新しい ship は "
                         "作らない）。`--ship` を打った後で「語そのものも宣言せよ」と"
                         "言われたときの直し方。**`--ship` を打ち直すと同じ成果が"
                         "2行入り、帳簿が二重に数えます。**")
    args = ap.parse_args(argv)
    if args.claim:
        if args.ship or args.seen:
            ap.error("--claim は単独で打ちます（出したものとは別の記録です）")
        return claim(args.claim)
    if args.seen:
        if args.ship or args.write:
            ap.error("--seen は単独で打ちます（出したものとは別の記録です）")
        return seen(args.seen, args.why or "")
    if args.why:
        ap.error("--why は --seen と一緒に使ってください")
    if args.closes_add:
        if args.ship:
            ap.error("--closes-add は --ship と一緒に使いません"
                     "（--ship のほうは --closes で書けます）")
        return closes_add(args.closes_add)
    if args.ship:
        # **腕を書かせる。** 「何をしたか」だけでは、予測日を動かす作業かどうかが
        # 記録に残りません（オーナー指示 2026-08-19 21:2x・`src/levers.py`）。
        # **`none` を選ぶ道は開けてあります** —— 塞ぐと嘘の宣言が増えるだけで、
        # 数えたい「10回のうち何回が動かす腕だったか」が測れなくなります。
        if not args.lever:
            ap.error("--lever が要ります（--ship と対）。"
                     + levers.vocab_help()
                     + "。**道具・手順の整備なら `--lever none`**（理由を JOURNAL に1行）")
        # **見込みも書かせる。** 「どの腕を選んだか」だけでは、
        # **早めることを考えたかどうか**が記録に残りません
        # （オーナー指示 2026-08-20 08:0x。同じ趣旨の指示はこれで3回目）。
        # **0 は正しい答えです**（`--lever none` と対）。外れてもかまいません ——
        # 数えたいのは当たり率ではなく、**先に言ってから出したかどうか**です。
        if args.moves is None:
            ap.error("--moves が要ります（--ship と対）。"
                     "**この成果で予測日が何日動く見込みか**を、"
                     "出す前に言うこと（早まるなら負・遠のくなら正・動かさないなら 0）。"
                     "予測日は `python scripts/eta.py` の先頭3行に出ています")
        # **種別も書かせる**（2026-08-27。**この回が自分で踏んだ**）。
        #
        # `ship_kind_of()` は 2026-08-26 に `--kind` の欄を足しましたが、
        # **書かせる門はどこにも作りませんでした** —— 頭の語が種別で始まらない
        # 回は「その他」で通り、`drift.py` の漂流の門（`verdicts_tail == 0`）から
        # 消えます。実測: `ship` 381件 のうち **155件（41%）が「その他」**。
        #
        # 2026-08-27 05:0x の回は、その欄が足された **86分後**に、
        # 「jutaku に節2件 → 長尺の族 11→13 → 長尺1本を予約（vuhvrJ1CkBE）」で
        # 踏んでいます（中身は明らかに `upload`）。警告は**書いた後**に出るので、
        # 気づいた回が `data/runs.jsonl` を手で直すことになりました。
        #
        # **`--lever` と同じ形の門にします。** あちらは 2026-08-19 に
        # 「無いと通らない」にしたことで、以後の ship に必ず腕が付きました。
        # **註や警告ではなく、通さないことだけが効いています。**
        #
        # **覆る条件**: `data/runs.jsonl` の直近100件の「その他」が 0 のまま
        # 30日 続いたら、頭の語の慣習が定着したということなので、この門は要りません。
        if run_marker_ship_kind(args.ship, args.kind) == "その他":
            ap.error("--kind が要ります（--ship と対）。"
                     f"種別は `{'／'.join(sorted(SHIP_KINDS))}` のどれか —— "
                     "`what` の頭がその語で始まっていれば書かなくて通ります。"
                     "**`drift.py` の漂流の門（直近20回の verdict）がこの欄を数えます** —— "
                     "空けると、その回は門から見えません")
        # **`fix` の連を、ここで止めます**（2026-09-01。理由は `FIX_RUN_CAP` の註）。
        #
        # **`--lever` / `--kind` と同じ形の門です。** あの2つは
        # 「無いと通らない」にしたことだけが効きました（註と警告は3回 戻りました）。
        # ここも同じで、**「連が長い」と印字するだけなら `drift.py` が
        # 2026-08-24 から毎回やっていて、7日 後の比は変わっていません。**
        _fk = run_marker_ship_kind(args.ship, args.kind)
        if _fk == "fix":
            _run = fix_run_len()
            # **枠が尽きている窓でも、撃てる手が残っていれば止めます**
            # （2026-09-01 に直した。理由と実測は `free_alternatives()` の註）。
            # 前の版は「門が名指しする4つはどれも枠の向こう側」を理由に
            # **無条件で通していました** —— `videos.insert` は日枠を使わず、
            # `improve` の台本・計算の道は 0単位 なので、**その理由は誤りです。**
            # **通したことは残します。**
            _out, _qline = quota_is_out()
            _free = free_alternatives() if _out else []
            if _run >= FIX_RUN_CAP and _out and not _free:
                note_fix_gate(args.ship, _run, waived=True)
                print(f"[marker] **`fix` が {_run}回 続いています**（上限 {FIX_RUN_CAP}）が、"
                      f"**この窓は Data API の日枠が尽きているので通します** —— {_qline}")
                print("[marker]   **そして 0単位 で撃てる手も残っていません**"
                      "（`free_alternatives()` が空 ＝ 次に公開される1本がありません）。"
                      "枠を要るのは `means` と、読みで閉じる `verdict` です。")
                print("[marker]   **その回の JOURNAL に「枠が尽きていた」と書くこと** —— "
                      "書かないと、次に `retro.py` を読んだ回が"
                      "「fix に偏っている」だけを見て、偏りの理由を「選び方が悪い」と読みます。")
            elif _run >= FIX_RUN_CAP and cond4().get("fired"):
                # **門の自分の「覆る条件4」が立っているなら、門は通す**（2026-09-02 夜）。
                #     `cond4()` は 09/02 夕に「既に立っていた」と実測され、`cond4_line()` は
                #     止めた回に**毎回**「律速は `fix` ではありません。回の配合をこれ以上
                #     いじらないこと」と印字していました —— **印字しながら止めるのは、
                #     配合をいじり続けることそのもの**です（この回に実物で踏んだ:
                #     置く側の機械化と、親の周の割れの直しが、この門で2度 記録できなかった）。
                #     条件4 が偽に戻れば（`traj_days` が動いた回が出れば）門は自動で戻ります。
                #     **通したことは残します**（`waived`）。
                note_fix_gate(args.ship, _run, waived=True)
                print(f"[marker] **`fix` が {_run}回 続いています**（上限 {FIX_RUN_CAP}）が、"
                      "**この門の覆る条件4 が立っているので通します** —— "
                      f"{cond4_line()}")
            elif _run >= FIX_RUN_CAP:
                note_fix_gate(args.ship, _run)
                _alt = near_deadlines()
                _lines = "\n                     ".join(_alt) if _alt else "（`config/hypotheses.yaml` が読めませんでした）"
                # **枠が尽きていても撃てる手を、その場で名指しすること。**
                # 名指しできない門は、種別の語を書き換えて通されるだけです
                # （`near_deadlines()` の註と同じ理由）。
                _freelines = ""
                if _out:
                    _f = _free or free_alternatives()
                    if _f:
                        _joined = "\n                     ".join(_f)
                        _freelines = ("\n  **この窓は日枠が尽きていますが、"
                                      "0単位 で撃てる手が残っています**:\n"
                                      f"                     {_joined}\n")
                ap.error(
                    f"**`fix` が {_run}回 続いています**（上限 {FIX_RUN_CAP}）。"
                    "`eta.py` は毎回「作る・出す・直すは軌跡の入力に入りません」と"
                    "印字しているので、**`fix` の回の `--moves` は定義上 0** です。"
                    f"直前の {_run}回 は、どれも到達日を動かしていません。\n"
                    "  **この1回は、到達日を動かしうる側に使うこと** —— "
                    "`verdict`（前提を1件 閉じる。**腕が動く唯一の道**）／"
                    "`upload`（規則は1日1本。今日の1本は出したか）／`means`。\n"
                    "  **`improve` は、いつでも在ります** —— オーナーが固定した規則3"
                    "（`docs/GOAL.md`・`CLAUDE.md` 冒頭）が"
                    "「**次の投稿の枠までの時間は、その枠で出す1本を改善し続けることに使う**」"
                    "と言っています。**`upload` が1日1回しか撃てない以上、"
                    "大半の回の「出したもの」はこれです**（`docs/trigger_main.md` §4）。"
                    "**この門は、そこへ戻す門です。**\n"
                    f"{_freelines}"
                    "  期限の近い前提（`python scripts/deadline_check.py` に全文）:\n"
                    f"                     {_lines}\n"
                    "  **規則（1日1本）の下では永久に閉じない前提**が別に数件あります —— "
                    "`deadline_check.py` の末尾。**書き直すか、公開ずみの日で閉じるか**の"
                    "どちらかで、そこも `verdict` の回になります。\n"
                    "  **直しが本当に要るなら、それは次の回でも要ります。** "
                    "順番だけの門です（`FIX_RUN_CAP` の「覆る条件」を読むこと）\n"
                    # **止めた回に、いまの比を見せること**（2026-09-01 夕）。
                    # 前の版は、この比をどこにも出していませんでした ——
                    # だから「門が効いていない」（覆る条件1）を、
                    # **7日 のあいだ誰も判定できませんでした。**
                    f"  {fix_share_line()}\n"
                    # **覆る条件 1 だけでなく 4 も、その場で見せること**
                    #     （2026-09-02）。1 は `fix_share()` が撃てる形で置かれ、
                    #     4 は散文のままでした。**4 は既に立っています** ——
                    #     立っているなら、この門はもう律速ではありません。
                    f"  {cond4_line()}")
        return ship(args.ship, args.closes, args.lever, args.moves,
                    reflect=not args.no_reflect, kind=args.kind)
    if args.moves is not None:
        ap.error("--moves は --ship と一緒に使ってください（出したものと対で残します）")
    if args.lever:
        ap.error("--lever は --ship と一緒に使ってください（出したものと対で残します）")
    if args.closes:
        # **単独では受けない。** 宣言は「何を出して閉じたか」と一緒でなければ、
        # 散文の約束と同じで、後から裏が取れません。
        ap.error("--closes は --ship と一緒に使ってください（出したものと対で残します）")
    return write() if args.write else show()


if __name__ == "__main__":
    raise SystemExit(main())
