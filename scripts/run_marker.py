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
    # **この回だけの一時置き場を、ここで掘って見せること**（2026-08-29 に足した）。
    # 共有の直下へ書くと、きょうだいが同じ名前で上書きします
    # （実測: `status.py` の出力 266行 → 24行）。`scratch_dir()` の註。
    scratch = scratch_dir()
    if scratch:
        print(f"[marker] **この回の一時置き場: {scratch}**"
              "（きょうだいと共有の直下へ書かないこと。"
              "`status.txt` `eta.txt` `build.log` は全員が同じ名前を使います）")
    # **ここで出すこと。** §1 はその回のいちばん最初のコマンドで、
    # **何をやるか決める前**です。決めた後に見せても、払った時間は戻りません。
    for ln in _claim_lines():
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


#: `CLAUDE.md` §「毎回の実行で必ずやること」が「出した」と呼ぶ4つ。
#: **`scripts/drift.py` の `KINDS` と同じ並びです**（片方だけ変えないこと）。
SHIP_KINDS = ("upload", "means", "verdict", "fix")


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
            # この回の `--reflect` は **330秒** かかった（`eta.py` 全体は約9分）。
            # `CLAUDE.md` は「約4秒」と書いているが、それは段が増える前の数字。
            # 180 のままだと `TimeoutExpired` で毎回落ち、**反映が1度も残らない** ——
            # しかも「回は止めません」と出るので、**落ちたことに気づかないまま次へ行く。**
            # 上げすぎても害は小さい（反映が終われば即座に返る）。
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
