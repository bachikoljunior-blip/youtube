#!/usr/bin/env python3
"""**子に渡すプロンプトを組み立てる**（2026-08-20 に作った）。

型の正本は `docs/spawn_prompt.md`、識別子の正本は `docs/trigger_spec.json`。
**この道具は組み立てるだけで、文言をここに持ちません** —— 持つと2か所になり、
片方だけ直った回に、また 8/12 の「3か所とも別の値」に戻ります。

## なぜ要ったか

渡し方が**親のターンの中にしかありませんでした。** 毎時走るので回数が効き、
実測で3つ壊れています（理由の全文は `docs/spawn_prompt.md`）:

    source_url の付け忘れ    8/17 04:1x・8/18 23:5x（repo の無い子が立つ）
    親が要約して条件を落とす  8/10
    申し送りが親と一緒に消える 8/15・8/16

**上2つは、道具が組み立てれば起きません。** `--json` は `source_url` と
`source_revision` を**必ず**入れるので、付け忘れる余地がありません。

## 使い方

    python scripts/spawn_prompt.py --kind hourly
    python scripts/spawn_prompt.py --kind owner-full --note "<原文>"
    python scripts/spawn_prompt.py --kind hourly --siblings 016bZbYd,01Cja6DK
    python scripts/spawn_prompt.py --kind hourly --only "eta.py の _drift だけ" --json

## この設計が覆る条件

- **枝が1本でなくなったら** —— `--branch` を足して、既定を spec から取ること
- **`create_session` の引数が変わったら** —— `--json` の欄を合わせること
  （`tests/test_spawn_prompt.py` が `source_url` / `source_revision` を見ています）
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "docs" / "spawn_prompt.md"
SPEC = ROOT / "docs" / "trigger_spec.json"

KINDS = ("hourly", "optimizer", "owner-full", "owner-record")

_BLOCK = re.compile(
    r"^## (?:kind|block):\s*(?P<name>[\w-]+)\s*$\n+```text\n(?P<body>.*?)^```",
    re.M | re.S)

# 型のほかに要る段。**`lead-only` が欠けると、`--only` の回に
# 「1周してください」が残り、受け取った子が両方やろうとします。**
NEEDED = KINDS + ("lead-round", "lead-only")


def templates(path: Path = TEMPLATE) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    out = {m.group("name"): m.group("body").rstrip() for m in _BLOCK.finditer(text)}
    missing = [k for k in NEEDED if not out.get(k, "").strip()]
    if missing:
        raise SystemExit(f"[!] `{path}` に型がありません: {', '.join(missing)}")
    return out


#: **どの役にも必ず付く段。** 立てられる側が、立てる側の手続きを直せるようにする。
#:
#: 2026-08-10 のオーナー指摘: 「目標以外のことは子の改善ループで変えられるように
#: したほうが良くない？ 作業の途中で設計の欠陥に気づくこともあるだろうから」。
#: あのとき親の手順はトリガー本文にあり、**子は気づいても直せませんでした。**
#: repo へ移して解いたのですが、**2026-08-25 夜に同じ穴を新しい場所に開け直しています**
#: —— サブへ渡す本文に「親の手順も変えてよい」と一度も書いていませんでした
#: （オーナー「サブの判断で変更できない箇所はない？」で気づいた）。
AUTHORITY = """

## **親の手順も、あなたが書き換えてよい**

**あなたを立てている側の手続きは、全部 repo にあります:**

    docs/trigger_parent.md 第1節     親が起きたら何をするか
    scripts/next_round.py            いつ立てるか・どの役か
    docs/spawn_prompt.md             あなたに渡される本文の**型**
                                     （`docs/spawn_prompt.rendered.md` は**生成物**。
                                       手で直すと戻されます —— 2026-08-25 に踏んだ）

**欠陥に気づいたら直してください。** 親は毎回この3つを読み直します。
**理由と「覆る条件」を `docs/JOURNAL.md` に書くこと** —— 書かないと、
次に来た側が判断できず惰性で戻します。

**変えられないのは目標の本文だけです**（`CLAUDE.md` 冒頭・`docs/GOAL.md`）。
**それ以外に聖域はありません。**"""


#: **合流したとき `CLAUDE.md` で必ず止まる、その1点だけ。**（2026-08-25）
#
# **枝の合わせ方そのものは、ここには書きません** —— 型の
# 「最初の1手は、枝を合わせることです」が `<<branch>>`（＝`docs/trigger_spec.json`）
# から本物の枝名を入れて渡しています。**2か所で言うと、片方が古びます。**
#
# 実際に8/25 にそうなりかけました: この段の最初の版は
# 「いちばん新しい `worktree-agent-*` が幹」と書いていて、**spec が名指しする
# `branch` と食い違っていました。** 同じ問いに2つの答えがある状態で、
# **このリポジトリが何度も踏んでいる形そのもの**です。消してあります。
#
# **`CLAUDE.md` の衝突を予告する段は、2026-08-26 に畳みました。**
#
# ここには長らく「合流すると `CLAUDE.md` で必ず衝突します（幹は恒久指示9件の枠を
# 外した版、`main` は入れた版 ＝ `4114f7b`）。サブはそのファイルを書き換えられません」
# と書いてありました。**その前提は、もうありません** —— 親が同じ日に
# `origin/main` を枝の先頭まで進めたので、`main` と幹が同じものになりました。
#
# **消しきらずに1行だけ残すのは、実測がまだ両方あるからです**（2026-08-26 06:0x）:
#
#     06:02 に立ったサブ  `main`(4114f7b) から切られており、
#                         `docs/trigger_main.md` が**無い**状態で始まった
#     06:47 に親が        `origin/main` を枝の先頭へ進めた
#
# **同じ日の中で切り替わっています。** だから「必ず衝突する」でも
# 「もう何もしなくていい」でもなく、**早送りで終わるはずの1手**として残します。
# 空振りなら数秒で、外れていたときの損（読む手順そのものが古い）は1周ぶんです。
FIRST_MOVE = """

**最初の1手: `git fetch origin` → `git merge origin/<<branch>>`**（早送りで終わるはずです・数秒）。
<<main_gap>>
競合したら **merge で相手の作業を残すこと。捨てないこと。**
**親は 2026-09-07 22:4x から、サブを立てる前に周を記録して押します**（`docs/trigger_parent.md` 第1節・
`scripts/next_round.py` の GO の枝・検査 `tests/test_parent_record_before_spawn.py`）。
だから、この最初の `Already up to date.` は**親のこの周の押しについては本当のこと**です。
それまでは順が逆で、最初の fetch がその押しに間に合わず、2日で2回 踏んでいます
（09/07 10:19 と 22:39・どちらも 2度目の fetch で早送りになった）。
**この段落を読んで、確かめる手を足さないこと** —— 01:3x の回が `git merge-base --is-ancestor` を足し、
12:4x の回が撃って外しました。それは merge と**同じ問い**を**同じ古い `origin/<<branch>>`** に訊き直すだけで、
merge と必ず同じ答えを返します（`git merge X` の `Already up to date.` は「X は HEAD の祖先」そのもの ＝ 同じ述語）。
**それでも「窓」は2回 撃つこと**（下）——2回目が見ているのは**相手のサブ**の押しで、
そちらは周の 3分後 に来るので、親の順とは関係がありません（API 0単位・数秒）。
"""


#: **写し（`docs/spawn_prompt.rendered.md`）に入れる側**（2026-09-07 03:3x・optimizer）。
#: `main_gap()` の数を写しに焼くと commit のたびに写しが変わり、`test_rendered_copy_for_the_parent_is_current` が
#: 永久に赤・親の周ごとに「写しを焼き直し」の commit が積まれた（09/06 13:40〜09/07 03:1x で 7件）。
#: `_clock_block()` を写しから外したのと同じ理由。数えるのは、fetch した直後のサブ本人（親の origin の写しより新しい）。
MAIN_GAP_STATIC = (
    "merge のあと `git rev-list --count origin/main..HEAD` で `origin/main` が何 commit 後ろかを数えること。"
    " 0 でなければ早送り1回 `git push origin origin/<<branch>>:main`（09/06 22:5x 実測: 237 commit ぶんで数秒。"
    "`docs/trigger_parent.md`「承認を求めないこと」の当のもの）。数えずに「進めてある」と思わないこと（08/26 の決め打ちが 12日 残った）。")


def main_gap(root: Path | None, branch: str) -> str:
    """`origin/main` が枝の先頭から何 commit 後ろかを、この checkout の origin の写しで数えて1行にする。

    09/06 22:5x（optimizer）まで、ここは「`origin/main` は枝の先頭まで進めてあるので、もう `CLAUDE.md` では
    衝突しません」と**決め打ちで**言っていた。実物は 09/05 07:17 JST の `91842f55` で、枝の先頭から **237 commit** 後ろ
    （1.5日）。08/26 の1回の実測を 12日 そのまま渡していた。親が渡すのは撃って出た数だけ（`docs/trigger_parent.md`）なので、
    数えて渡す。数えられなければ「数えられなかった」と言う（無言で古い断定に戻さない）。"""
    import os
    import subprocess
    try:
        kw = {"cwd": str(root)} if root else {}
        n = subprocess.run(["git", "rev-list", "--count", f"origin/main..origin/{branch}"],
                           capture_output=True, text=True, check=True, timeout=20, **kw).stdout.strip()
        when = subprocess.run(["git", "log", "-1", "--format=%cd", "--date=format-local:%m/%d %H:%M", "origin/main"],
                              capture_output=True, text=True, check=True, timeout=20,
                              env={**os.environ, "TZ": "Asia/Tokyo"}, **kw).stdout.strip()
    except Exception:  # noqa: BLE001
        return ("`origin/main` が枝の先頭から何 commit 後ろかは、この checkout では数えられなかった"
                "（`git rev-list --count origin/main..origin/<<branch>>` が失敗）。")
    n = int(n or 0)
    if n == 0:
        # **0 は「この回のあいだ 0 のまま」ではありません**（2026-09-11 15:5x・optimizer・Opus。この回に踏んだ）——
        # **あなたの押しで 0 でなくなります。** n>0 の枝には「押すこと」が書いてあるのに、
        # **0 の枝には 1字 も無い**ので、0 で立った回は自分の押したぶんを main へ送らずに終わります
        # （実測: この回は 3 commit 押して main を 3 後ろにし、数えに行って初めて気づいた。
        #  次の回が n>0 で拾うので**自己修復はします** —— 直したのは「1周 遅れる」ぶんだけ）。
        # **覆る条件**: main を進める側が親かサブかを決め直したら、この行も一緒に書き直すこと。
        return (f"`origin/main` は枝の先頭と同じ（main の先頭 {when} JST・この checkout の origin の写しで数えた）。"
                f" **ただし、あなたが押したら 0 ではなくなります** —— "
                f"**この回の最後の push のあとにもう一度 `git rev-list --count origin/main..HEAD` を数え、"
                f"0 でなければ早送り1回**（数秒・承認は要りません）。")
    return (f"`origin/main` は枝の先頭から **{n} commit** 後ろ（main の先頭 {when} JST・この checkout の origin の写しで数えた）。"
            f" **この数は「立てた瞬間」のもので、あなたが読むころには古いことがあります** —— "
            f"実測 2026-09-08 04:4x: 親は **1** と数えて渡したが、サブが最初の merge のあとに数え直したら **0** だった"
            f"（相手のサブが周の 3分後 に main まで押していた）。"
            f" → **merge のあと `git rev-list --count origin/main..HEAD` で数え直すこと。0 でなければ** "
            f"早送り1回 `git push origin origin/<<branch>>:main`（09/06 22:5x 実測: 237 commit ぶんで数秒。"
            f"`docs/trigger_parent.md`「承認を求めないこと」の当のもの）。**0 なら押さない。**"
            f" これは 12:4x に外した `merge-base --is-ancestor` とは**別**で、あちらは同じ古い ref に同じ問いを訊き直す"
            f"（必ず同じ答え）のに対し、こちらは**あなたが fetch した後の `origin/main`** ＝ 親の写しより新しい別の物を見ます"
            f"（実際に 1 対 0 と答えが割れました）。")


#: **停止中に渡す先頭の段**（2026-08-30。オーナーが `origin/main` へ直接 push した8件）。
#:
#: `AUTOMATION_PAUSED.md` が**在るあいだだけ**入ります。オーナーが消せば自動で消えるので、
#: 解除のときに**この関数を触る必要はありません**（触ると、消し忘れが次の回を止めます）。
#:
#: **なぜ本文の先頭か**: 型の途中に置くと、受け取った側が
#: 「1周してください」を先に読んで生成へ向かいます。**先に読まれる側が勝ちます。**
def _gate_state_block() -> str:
    """**解除条件の「いまの姿」を、写しではなく台帳から出す**（2026-08-30 に足した）。

    ここには 6件が**べた書き**されていました。書いた時点では正しく、
    **その日のうちに 1・2 が閉じました**（`config/channel.yaml` から実務経歴が落ち、
    `src/verify._check_no_human_expert_claim()` が出口にも門を置いた）。
    べた書きのままだと、**次に立つ子は全員「6件とも開いている」と読みます** ——
    `CLAUDE.md` が「**1・2 をもう一度やらないこと**」とわざわざ書いているのは、
    この形が実際に起きるからです。**本文の先頭は、いちばん強く効く場所です。**

    **覆る条件**: `data/resume_gate.jsonl` と `AUTOMATION_PAUSED.md` が
    正本なので、あちらが動けばここは自動で追随します。読めなければ黙ります
    （**読めないことを「全部 閉じた」として印字しないこと**）。
    """
    # **`sys.path` を自分で通すこと**（2026-08-30 に踏んだ）。この script は
    # `python scripts/spawn_prompt.py` で走るので `sys.path[0]` は `scripts/` ——
    # リポジトリの根は入っていません。通さないと `from src import ...` が静かに
    # 失敗し、**この段まるごとが空で出ます**（下の `except` が飲み込む）。
    # 実測: 入れた直後の1回目が、それで空でした。
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    try:
        from src import resume_gate
    except Exception:  # noqa: BLE001 — 型の生成で回を止めない
        return ""
    try:
        g = resume_gate.summary()
        q = resume_gate.queue()
    except Exception:  # noqa: BLE001
        return ""
    if not g.get("total"):
        return ""
    out = [f"**いまの姿: {g['closed']}/{g['total']} 件 が閉じています**"
           "（条件の本文は `docs/RESUME_GATE.md`・根拠は `data/resume_gate.jsonl`。"
           "`python scripts/eta.py --gate` で、その場で読めます）。"]
    closed = [r for r in resume_gate.state() if r["closed"]]
    if closed:
        out.append("")
        out.append("    閉じている（**もう一度やらないこと**）: "
                   + "／".join(f"{r['n']} {r['text'][:36]}" for r in closed))
    if g["open_items"]:
        out.append("    開いている（**ここが、いまの最短です**）: "
                   + "／".join(f"**{r['n']}** {r['text'][:44]}" for r in g["open_items"]))
    out.append("")
    if not g["open_items"]:
        # **開いている件が 0 の回に、やることが1つも書かれない形だった**
        #     （2026-08-30 15:4x に 6/6 になって踏んだ）。上の段は
        #     「解除条件を1つ進めること」と言い、下は「閉じるときは…」と言うので、
        #     **閉じ切った回の子は、出すものを名指しされないまま立ちます。**
        #     `AUTOMATION_PAUSED.md` が在る＝生成も投稿もできないので、
        #     **その回は何も出せずに終わります。**
        #
        #     **覆る条件**: `AUTOMATION_PAUSED.md` が消えたら `_pause_block()` ごと
        #     出なくなるので、この段も自動で消えます。
        out.append("**6件とも閉じています。だから、この回に閉じるものはありません。**"
                   " **いま止まっているのは、オーナーが手で `.owner-pause` を"
                   "置いているからです**（`src/pause_guard`）。"
                   " **その印を、この機械の判断で外さないこと。**"
                   " 作りに問題を見つけたなら、**止めるのではなく直すこと**"
                   "（`CLAUDE.md` 冒頭・`tests/test_pause_needs_owner.py`）。")
        out.append("")
        out.append("**この回に出せるもの**（`--lever gate` で積むこと。上から順に見る）:")
        out.append("")
        out.append("    - 閉じた6件の根拠を、**実測で当て直す**"
                   "（`python -m src.frames` ／ `python -m src.density_verdict` ／"
                   " `python -m src.legacy_corpus`）。"
                   "**閉じた根拠は上限であって、出来上がりの実測ではありません** ——"
                   "外れていたら、その件を開き直すこと"
                   "（`python scripts/eta.py --open-gate <番号> "
                   '--evidence "<何を測って、どこと食い違ったか>"`。'
                   "**2026-08-30 夜まで、ここには「`--close-gate` の逆」とだけ書いてあり、"
                   "その逆は実装にありませんでした**）")
        out.append("    - **停止中でも動く道**を1つ進める（`docs/MEANS.md` の未着手・"
                   "収益化できる別の形の調査・チャンネルを変えない試算）")
        out.append("    - 実測で見つかった欠陥を1つ塞ぐ（`fix`）")
        out.append("")
    out.append("閉じるときは、根拠の1行を添えて撃つこと（**印は記録ではありません**）:")
    out.append("")
    out.append('    python scripts/eta.py --close-gate <番号> --evidence "<どこに何を記録したか>"')
    out.append("")
    out.append("そして ship は **`--lever gate`** で積むこと ——"
               "停止中は4本の腕がどれも引けないので、`none` で積むと"
               "**律速を進めた回が「予測日を動かさない回」として数えられます**。")
    if q.get("upcoming"):
        # **本数と時刻をここに焼き込まないこと**（2026-08-30 に踏んで直した）。
        #     この段は `docs/spawn_prompt.rendered.md` に**写し**として保存され、
        #     親はそれを読んで子を立てます（`scripts/next_round.py`「親は写すだけ」）。
        #     予約は**毎時 公開されて減る**ので、焼き込むと
        #     `test_rendered_copy_for_the_parent_is_current` が **1時間で赤**になります
        #     —— 中身と関係のない理由で毎時 赤くなる検査は、次の回に外されます。
        #     **動くものは、動かない指示に置き換えること。**
        out.append("")
        out.append("**[!] 止まっていても、予約済みの本は公開され続けます** ——"
                   " 機械が1回も起きなくても公開され、その全部が停止の理由になった作りのままです"
                   " ＝ **`p_pass` は、何もしなくても毎日 下がりうる。**"
                   " **本数と時刻は `python scripts/eta.py --gate` が出します**"
                   "（**ここには焼き込みません。写した瞬間に古くなります**）。"
                   " 引っ込める `reschedule.py` は停止の対象なので、"
                   "**この機械からは止められません**（迂回しないこと）。"
                   " **門には時計が回っています。**")
    return "\n".join(out) + "\n"


def _why_writes_stop(now: datetime) -> str:
    """**何が書き込みを止めているのかを、名前で言う。**（2026-09-02 に踏んで足した）

    ここは長らく「**いまは 403 です**」と刷っていました。**嘘のことがあります。**

    `writable_from()` が見ているのは **帳面の見積り**（`quota_ledger.spent` が
    `DAY_UNITS` に達したか）で、**観測した 403 ではありません。**
    実測 2026-09-02 17:3x に受け取った回は、本文が「いまは 403 です」と言い、
    同じ回の `upload_cap.day_quota()` は

        この窓ではまだ 403 を観測していません（… 使った 6,550 ／ 前例のある枠 9,400）

    と印字しました。**同じ回の中で、本文と道具が別のことを言っています。**
    しかも `run_marker.py --write` のほうは `--move` と `refresh_thumbnail`
    （どちらも 50単位）を**撃てる手として名指し**します。
    受け取った側は、どちらを信じるかを毎回 自分で決めることになります。

    **この repo は、同じ穴をこの日にもう1つ塞いでいます** ——
    09/02 12:45 の `fix`「暦の号令を黙らせる4つ目の口」が、まさに
    「判定が**帳面の見積り**で、repo の正本は**観測した 403**だ」でした。
    **親の本文が、その5つ目の口です。**

    **止めているものは本物です**（実測: この窓の `refresh_thumbnail` は
    「**この窓の単位は、帳面の側で止めています**（使った 12,168 ／ 公表の枠 10,000）」
    で断られました）。**変えるのは、止めている物の名前のほうだけ。**

    **覆る条件**: `writable_from()` が観測した 403 も見るようになったら、
    この関数は「403」と「帳面」を区別せずに1行で言ってよい。
    """
    try:
        from src import quota_ledger, upload_cap                # noqa: PLC0415
        q = upload_cap.day_quota(now)
        used = int(quota_ledger.used_units(now))
        cap = int(quota_ledger.DAY_UNITS)
    except Exception:                                           # noqa: BLE001
        return "帳面の側で止めています"
    seen = "**403 を観測ずみ**" if not q.open else "**403 はまだ観測していません**"
    return f"{seen}／帳面 使った {used:,} ／ 枠 {cap:,}"


def _clock_block(live: bool = True) -> str:
    """**いまの時刻と、日枠が戻る時刻を、写しではなく道具から出す**（2026-09-02）。

    ## なぜ要るか（**この回に踏んだ**）

    申し送り（`--note`）は**原文のまま**通します —— 要約しない、数字は桁もそのまま。
    **それは正しい。** ですが原文には「**いま何時の窓か**」が書かれていることがあり、
    **それは書いた時点の写しです。**

    実測 2026-09-02 11:4x —— 申し送りの1行目:

        **この回は 09/02 16:00 JST の窓に当たります（日枠が戻る回）**

    受け取った子が最初に撃った `run_marker.py --write` の時刻は **11:41 JST**。
    **枠が戻る 4時間19分 前**でした。その本文が名指ししていた3手のうち

        reschedule.py --compact --apply   1,250単位  → **403**
        差し替えの2手（videos.update ×2）    100単位  → **403**

    は、**その回には撃てません**。`docs/trigger_main.md` は
    「**順番は道具が印字します。本文に写された順を信じないこと**」と書いていますが、
    **その註は「親の本文」には向いていませんでした。**

    `_gate_state_block()` の docstring と同じ形です ——
    「べた書きのままだと、次に立つ子は全員『6件とも開いている』と読みます。
    **本文の先頭は、いちばん強く効く場所です。**」

    **申し送りは直せません（原文だから）。だから、すぐ下に実物を置きます。**

    ## 覆る条件

    `writable_from()` が読めなければ**黙ります**（読めないことを
    「いつでも撃てます」として印字しないこと —— `_gate_state_block()` と同じ）。
    子の側は `run_marker.py --write` が同じ数を毎周 出すので、
    **ここが消えても、当てどころは失われません。**
    """
    # **`--write-rendered` の写しには、時刻を焼き込まないこと**（2026-09-02 に踏んだ）。
    #   写しは `docs/spawn_prompt.rendered.md` に**コミットされる静的な生成物**で、
    #   `tests/test_spawn_prompt.py::test_rendered_copy_for_the_parent_is_current`
    #   が「いま組み立てた本文と1字でも違えば赤」で見ています。
    #   **時刻を入れると、書き出した次の分から永久に赤**になります
    #   （実測: 入れた直後の1回は同じ分だったので緑、次の分で赤）。
    #   ＝ **この段が塞ごうとしている穴（写した時刻が古くなる）を、
    #      写しの側で自分が作る**ことになります。だから写しでは口だけ残します。
    if not live:
        return ("**いまの時刻と日枠の状態が、ここに入ります**"
                "（`scripts/spawn_prompt._clock_block()` が**立てる瞬間に**組み立てます）。"
                "\n\n    **上の申し送りに書かれた時刻は写しです。**"
                "食い違ったら `python scripts/run_marker.py --write` が印字するほうを採ること")
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    try:
        from datetime import datetime, timedelta, timezone
        from src import next_slot
    except Exception:  # noqa: BLE001 — 型の生成で回を止めない
        return ""
    JST = timezone(timedelta(hours=9))
    now = datetime.now(JST)
    out = [f"**いまは {now:%m/%d %H:%M} JST です**"
           "（**この行は組み立てた時刻。上の申し送りに書かれた時刻は写しです** ——"
           "食い違ったら、こちらでもなく **`python scripts/run_marker.py --write`**"
           "が印字するほうを採ること）。"]
    try:
        w = next_slot.writable_from(now)
    except Exception:  # noqa: BLE001
        w = None
    if w is not None:
        # **JST へ直すこと。** `writable_from()` は UTC で返します ——
        # 直さずに `%H:%M` で刷ると **09/02 07:00 JST** と出ます（実物は 16:00）。
        # 「あと N時間」だけが正しく、時刻のほうが 9時間 ずれる形で、
        # **この段が塞ごうとしている穴（写した時刻を信じる）そのもの**でした。
        w = w.astimezone(JST)
        if w <= now:
            out.append("")
            # **`--compact --apply` を名指ししないこと**（2026-09-02・規則5）。
            #   固定その4「現在の日付にしか予約しない」の下では、あれは
            #   **先の日付へ並べ直す禁じ手**です（道具の側も撃たなくしてあります）。
            #   `videos.update` の要る手として名指しするのは、**外す側**のほう。
            out.append("    日枠: **いま撃てます**"
                       "（`videos.update` の要る手 —— `pool_drain --apply --keep 0`"
                       "（**先の日付の予約を外す**）/ 次の枠の1本の差し替えの2手 /"
                       " その日の枠への `reschedule --move` —— が、この回に通ります）")
        else:
            hrs = (w - now).total_seconds() / 3600.0
            out.append("")
            out.append(f"    日枠: **書き込みは、いま止まっています**（{_why_writes_stop(now)}）"
                       f"。**戻るのは {w:%m/%d %H:%M} JST（あと {hrs:.1f}時間）** ——"
                       " それより前に `videos.update` の要る手（`pool_drain --apply`・"
                       "差し替え・`--move`）を名指しされていても、**この回では撃てません。**"
                       " 0単位 の手（`premise` / 台本の側 /"
                       " **次の日の1本を `upload_only.py <ID> --draft` で上げる**"
                       " —— `videos.insert` は日枠を使いません）へ振ること。"
                       " **きょうの1本がまだ置かれていなければ、それも insert で置けます**"
                       "（`ahead_sweep.place_today` が自分で倒れます —— 台本の控え"
                       " `data/critique_queue/<ID>.script.json` から焼き直して"
                       " `upload_only.py <題材> \"\" \"<きょう>@<時>\" --replaces <ID>`。"
                       " 実測 2026-09-03 00:08 JST・`data/ahead_sweep.log` の `[today]` で確かめること）")
    return "\n".join(out)


def _pause_block(root: Path) -> str:
    """**停止中に、サブへ配る本文の先頭に入る段。**

    **判定はここに持ちません**（2026-08-31）。2026-08-30 まで、この関数は
    停止の文書が根の下に在るかどうかを**独立に**見ていました ——
    `src/pause_guard` とは別の答えを出せる形です。**親は動くのに、子だけが
    「止まっている」と読んで1周を捨てる**、いちばん気づきにくい壊れ方でした。
    いまは `src/pause_guard.is_paused()`（＝ オーナーが手で置いた `.owner-pause`）
    にだけ従います。読めなければ「止まっていない」側に倒します。
    """
    import sys
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        from src import pause_guard
    except Exception:  # noqa: BLE001 — 型の生成で回を止めない
        return ""
    if not pause_guard.is_paused():
        return ""
    return """# **【停止中】この回は、動画を作らない・出さない・予約を触らない**

**オーナーが、手で `.owner-pause` を置いています。**
**この印は、この repo のどのコードも作りません** —— つまり人が置いたものです。
**推測ではありません。止まっているのは「いまのやり方」であって、目標ではありません。**
**この印を、この回の判断で外さないこと。** 作りに問題を見つけたなら、
**止めるのではなく直すこと**（`CLAUDE.md` の冒頭）。

    止まっているもの  生成・アップロード・予約の変更・題やサムネの変更・再生リスト
                      （`src/pause_guard.py` と `src/config.py` が二重に止めます。
                        import した時点で RuntimeError になります）
    やってよいもの    分析・実測の読み取り・データの保全・
                      **収益化できる別の形の調査**・チャンネルを変えない試算

**`ALLOW_POLICY_PAUSED_AUTOMATION` を設定して迂回しないこと。**
あれは人が手で確かめるときの口で、自動運転のためのものではありません。

**「昔の型にはこう書いてあった」を根拠に生成へ向かわないこと。**
`docs/trigger_main.md` の「最低1件は出してから終わる」は、**この停止の前に書かれています。**
停止中の「出した」は、**下の解除条件を1つ進めること**です。

## 解除条件（`AUTOMATION_PAUSED.md` の6件。ここを進めるのが、いまの最短です）

    1. 扱いのむずかしい題で、人間の専門家を装う人格を使わない
    2. 人間の専門家を装わない
    3. 出来上がった動画が実際に十分ちがっていて、独自の作り手の寄与がはっきり示せる
    4. 方針に沿うチャンネルの構想を、いまの公式ポリシーと突き合わせて確かめる
    5. すでに公開した動画の扱いと、新旧のテーマが混ざる危険を決める
    6. 収益化までの道筋と、視聴者を得る採算を計算し直す

""" + _gate_state_block() + """
**目標は1文字も変わっていません**（YouTube の収益で月20万を最短で）。
変わったのは、そこへ行く道が「いまの人格・いまの作り方」では通らないと分かったことです。
**別の道を探すことが、いまの仕事です。**

"""

#: **相手が何を触ったかを、その場で見る手**（2026-08-31・最適化の回に足した）。
#:
#: `%s` に枝の名前が入ります。**`build()` の末尾が `<<branch>>` を当て直す**ので、
#: ここには枝名を写さないこと（写すと `docs/trigger_spec.json` と食い違います）。
#: **API 0単位・数秒**。
TOUCHED_CMD = ("git fetch origin && git log origin/%s --since=\"12 hours ago\" "
               "--name-only --pretty=format:'%%h %%ad %%s' --date=format:'%%m/%%d %%H:%%M'")


#: 写し（`docs/spawn_prompt.rendered.md`）に入れる側。**数は焼かない**
#: （焼くと周ごとに写しが変わり、`test_rendered_copy_for_the_parent_is_current` が毎周 赤くなる）。
QUOTA_BLOCK_STATIC = (
    "【枠 —— この回に使ってよい速さ】**この段は、サブを立てる瞬間に `spawn_prompt._quota_block()` が"
    "数で埋めます**（API 0単位）。すべて／Fable のみ の目盛り・床（間隔）・"
    "**リセット時にどこへ着くか**（床に従えば／いまの間隔のまま）・"
    "**Fable のみ が尽きるのはリセットの何時間 前か**。"
    "**写しには数を焼きません** —— 焼くと周ごとに写しが変わります。"
    "実物は `python scripts/quota.py --pace`。")


def _quota_mod():
    """`_quota_block()` が読み込んだ `quota`（検査の差し替えも同じ物を拾う）。無ければ None。

    **`import` を増やさないこと** —— `_quota_block()` は関数の中で import しており、
    決まるのは**呼んだ瞬間の `sys.modules`** です（`tests/test_spawn_quota_block._stub_quota` の註）。
    ここで別に import すると、差し替えた検査と**別の物**を見ます。
    """
    import sys  # noqa: PLC0415
    return sys.modules.get("scripts.quota") or sys.modules.get("quota")


def _fable_cap() -> float | None:
    """「Fable のみ」の上限（`quota.FABLE_CAP_PCT`）。読めなければ None。

    **写さないこと** —— 親は `next_round_owner.py` から走り、そこが
    `quota.FABLE_CAP_PCT` を**実行時に書き換えます**（公式仕様の 100%）。
    """
    v = getattr(_quota_mod(), "FABLE_CAP_PCT", None)
    return float(v) if isinstance(v, (int, float)) else None


def _gauge_words(fe: dict) -> str:
    """目盛りの刻を「（目盛り 09/11 12:38 JST）」の形で。読めなければ空。"""
    q = _quota_mod()
    at = ((fe or {}).get("gauge") or {}).get("at")
    jst = getattr(q, "JST", None)
    if at is None or jst is None:
        return ""
    try:
        return f"（目盛り {at.astimezone(jst):%m/%d %H:%M} JST）"
    except Exception:                                          # noqa: BLE001
        return ""


def _standing_models() -> str:
    """**この周に、役ごとに実際に立つ模型**（`quota.sub_model`）。読めなければ空。

    **役の名前から引かないこと**（METHOD §5 の 2026-09-11 10:3x）——
    §5 15:1x の「短く終わるか」は**役ごと**に書かれていますが、判定するのは
    **その周に実際に立った模型**です。Fable が尽きた枠では `hourly` も opus で立ち、
    そのとき「Fable を台本の回に残す」という `hourly` 側の理由は消えています。
    """
    q = _quota_mod()
    fn = getattr(q, "sub_model", None)
    if not callable(fn):
        return ""
    roles_fn = getattr(q, "sub_roles", None)
    try:
        names = tuple(roles_fn()) if callable(roles_fn) else ("hourly", "optimizer")
    except Exception:                                          # noqa: BLE001
        names = ("hourly", "optimizer")
    out = []
    for r in names:
        try:
            out.append(f"{r} {fn(role=r)[0]}")
        except Exception:                                      # noqa: BLE001
            return ""
    return "・".join(out)


def _fable_ration() -> dict | None:
    """**Fable の配りの数**（`quota.fable_ration()` の返り）。読めなければ None。

    `_fable_ration_words()` と**同じ物**を返します —— 枠が戻った回の
    「いま Fable のみ 何%」は、目盛り（前の枠の数）ではなく **この `est`** です
    （`quota.fable_rolled` の註）。
    """
    q = _quota_mod()
    fn = getattr(q, "fable_ration", None)
    if not callable(fn):
        return None
    try:
        r = fn()
    except Exception:                                          # noqa: BLE001
        return None
    return r if isinstance(r, dict) else None


def _fable_rolled(fe: dict) -> bool:
    """**「Fable のみ」の枠が戻っているか** ——門は `quota.fable_rolled`（1か所）。

    読めない古い `quota` では False（＝ 前と同じ字を出す・`_short_lines()` と同じ構え）。
    """
    q = _quota_mod()
    fn = getattr(q, "fable_rolled", None)
    if not callable(fn):
        return False
    try:
        return bool(fn(fe))
    except Exception:                                          # noqa: BLE001
        return False


def _fable_ration_words() -> str:
    """**Fable の配りの 1行**（`quota.fable_ration` / `fable_ration_words`）。読めなければ空。

    2026-09-11 19:5x・optimizer・Opus。オーナー原文（受け取り帳 `c2d075b2`・`06fec2ad`）:
    「リセットされたらfableにするよな？フェイブルずっと使えるように調整するよな？」

    **この段は線を引き直しません** —— 道具が印字した字をそのまま運びます
    （§5 教訓の形 7つ目「覆る条件を註に書いたら、その条件を読む印字も一緒に作ること」。
    註と印字が食い違えば、**読まれるのは印字のほう**）。
    `_quota_mod()` から引くのは `_short_lines()` と同じ理由（検査が差し替えた `quota` を見るため）。
    """
    q = _quota_mod()
    fn = getattr(q, "fable_ration", None)
    words = getattr(q, "fable_ration_words", None)
    if not callable(fn) or not callable(words):
        return ""
    try:
        return words(fn()) or ""
    except Exception:                                          # noqa: BLE001
        return ""


def _short_lines(reach_floor: float | None, p: dict) -> list[str]:
    """**「短く終わってよいか」の判定は、`quota.short_words()` の1行をそのまま運ぶ**
    （2026-09-11 17:0x・optimizer・Opus。**API 0単位**）。

    **踏んだ形**: 【枠】の段は「床に従えば **99.4%**・いまの間隔のまま **99.4%**
    （§5 15:1x の覆る条件 (1) の門は **98%**・当てるのは「床に従えば」の側）」と
    **数と門と側**を並べていましたが、**判定（引かれたか）は1文字も印字していません**でした。
    ＝ サブは毎周、99.4 と 98 を**手で引き比べます**。
    ところが 13:1x の決めは、その逆です ——「引き比べは `quota.short_verdict` が毎周 印字する
    ＝ **手で当てないこと**」（門 98% は 40周 のあいだ METHOD の字の中にしか無く、
    40周 とも手で引かれていた・§5 教訓の形 7つ目）。
    **この段は、サブが METHOD を読むより先に目に入る印字です**（同じ教訓の形の当のもの）。

    **2か所に持っていた物が 2つ**（どちらもこの回に畳んだ）:

        門 98%        `SHORT_LANDING_GATE` と、この段の **literal**（`short_verdict` の覆る条件 (3)
                      は「2か所に持たないこと」と書いてある側）
        `blind`       「区間の窓 ＞ 残り」の述語を、この段が別に書き直していた
                      （`short_verdict` は同じ述語を `blind` で返す）

    **`short_words` は `_quota_mod()` から引きます**（`from` で縛らない）——
    呼んだ瞬間の `sys.modules` を見るため（検査が差し替えた `quota` と別の物を見ない）と、
    **口が無い回にこの段ごと落とさないため**です（`from` 側に足すと、
    `short_words` を持たない差し替えで【枠】が丸ごと空になり、
    **空欄が「余裕がある」に読まれます** —— この段の註の当のもの）。

    **覆る条件**: (1) `--pace` の印字の字数が増えて、この段に載せるには長すぎる回が来たら、
    運ぶのは1行目（判定の行）だけにすること —— **判定を落とすのではなく、註のほうを落とす**。
    (2) `short_words` が 2行 より増えたら、この関数は畳まずに全部 運ぶ（判定と註は対で意味を持つ）
    —— **2026-09-12 00:5x に 3行目 が出る回ができました**（床が歯止めに当たった回・下の `floor_clipped`）。
    この関数は全部 運びます（畳んでいません）。
    (3) 門の数（98%）が動くのは `SHORT_LANDING_GATE` の 1か所 だけ ＝
    この段に数を書き戻さないこと（検査 `tests/test_spawn_quota_gate_side.py`）。
    """
    if reach_floor is None and p.get("reach_carry") is None:
        return []
    fn = getattr(_quota_mod(), "short_words", None)
    miss = ["    **短く終わってよいかが読めません**（`quota.short_words` が落ちたか、無い）"
            " —— **空欄を「短く終わってよい」と読まないこと**・`python scripts/quota.py --pace`"]
    if not callable(fn):
        return miss
    try:
        # **床が歯止めに当たったかも渡すこと**（2026-09-12 00:5x・`short_verdict` の
        # 覆る条件 (1)）—— 当たった回の「床に従えば」は平らではなくなり、
        # **側そのものを引き直す回**になります。渡さないと、この段は
        # 引かれた覆る条件を持たない古い字のまま出ます（§5 教訓の形 7つ目）。
        # 口を持たない `quota` に差し替えられた回は、**4引数の形へ落として運ぶ**
        # （この 1行 のために段を丸ごと落とさない —— 上の `miss` の註）。
        try:
            line = fn(reach_floor, p.get("reach_carry"),
                      (p.get("seg") or {}).get("hours"), p.get("left_hours"),
                      p.get("floor_clipped"))
        except TypeError:
            line = fn(reach_floor, p.get("reach_carry"),
                      (p.get("seg") or {}).get("hours"), p.get("left_hours"))
    except Exception:                                          # noqa: BLE001
        return miss
    if not line:
        return miss
    # `--pace` は 6文字 下げて印字する。【枠】の段は 4文字 なので、そこだけ揃える
    # （**字は変えない** —— 2つの口が違うことを言わないため）。
    return [("    " + ln.strip()) for ln in line.splitlines() if ln.strip()]


def _quota_block() -> str:
    """**枠の視点を、サブ本人に渡す段**（2026-09-09 22:1x・optimizer・Opus。**API 0単位**）。

    オーナー原文（2026-09-09。`CLAUDE.md` 冒頭）:
    21:13「**全てのモデル100％いきそう？**」／21:1x「**どうすんの？**」／
    21:5x「**その視点ないんだったら視点だけ与えなよ**」。

    **その視点は、本文のどこにも在りませんでした。** サブに渡っていたのは
    模型の名前（`hourly`＝Fable・`optimizer`＝Opus）だけで、
    **枠がいま余る側なのか足りない側なのかは、1文字も書いていません。**
    そしてサブの側には、それで変わる決めが在ります ——
    METHOD §5 の「**持ち場に何も無ければ短く終わってよい（Fable の枠を使わない）**」は
    **枠を使いすぎていた頃**に書かれた行で、**余る側では向きが逆**です。
    ＝ **サブは、逆向きの既定を、根拠を見ずに引いていました。**

    **【2026-09-10 20:4x・optimizer・Opus】その問いは、もう決着しています。**
    §5 は **09/10 15:1x に `hourly` が役ごとの着地で決めました**（覆る条件 3つ つき）。
    この段が「**どちらかはあなたが決めること**」と言い続けると、**サブは毎周 決着ずみの問いを
    開け直します** ＝ 親の本文が METHOD の決めと食い違う側（**言っている所と、している所が別**）。
    いま置くのは**数と、決めの指し先**だけ ——「その決めが、この数でまだ成り立つか」を見せる形です。
    **覆る条件**: §5 がこの決めを外したら、この段も指し先ごと書き直すこと
    （検査 `tests/test_spawn_quota_block.py::test_短く終わるかは_METHOD_5_の決めを指すこと`）。

    **親は判断しません**（09/06 14:0x「お前が判断すんじゃなくて、サブが判断すんだよ」）。
    だからここに置くのは**数だけ**で、「こうしろ」は書きません。

    **目盛りは 2つ、絞りは 1つ**（`quota.landing()` の註・METHOD §5 の 22:0x）——
    床（間隔）は「すべてのモデル」の残りから引かれるので、
    **Fable のみ の着地は床では選べません**。実測 21:13 の目盛りで、床 41分 なら
    「すべて」はリセット時 99.8%・**Fable のみ はリセットの 28時間 前に尽きます**
    （`hourly` が §5 に置いた数と、この道具が別々に出して一致した）。

    **落ちても段ごと落とすだけ**（親を止めない）。数が読めない回は「読めていない」と書きます
    —— **空欄を「余裕がある」と読ませないこと**（`CLAUDE.md` の使用量の節）。

    **【2026-09-11 15:4x・optimizer・Opus】段の頭の「**API 0単位**」を外しました。**
    あれは**この段を作る値段**（数を埋めるのに API を撃たない）で、
    **この回に使ってよい API の量ではありません。** ところが字は
    「【枠 —— **この回に使ってよい速さ**】**API 0単位**。」と並んでおり、
    **その並びの読み方は 1つ しかありません** ＝ 「この回は API を 0単位 しか使えない」。
    **その読みは偽です** —— 同じ本文が (a) で `measure` と `status` を毎周 撃てと言い
    （どちらも Data API の単位を使う）、METHOD §7 (o-4) は
    「09/11 18:00 JST 以降に `cli reporting` を 1回」と言っています。
    **この回に踏みました**: 未返信のコメント（`cli reply` **50単位**）に触ってよいかを、
    この段のせいで 1度 決めかねた。
    **【2026-09-11 16:3x・optimizer・Opus】Fable が 100% に着いたあと、この段は
    「これから着く」と未来形で言い続けていました。**
    実測（この回の本文・`quota` の同じ数）: 目盛りは **09/11 12:38 JST で「Fable のみ」100%**、
    `sub_model` は **2役 とも opus** を返しているのに、この段は
    「Fable のみ  床に従うと **リセットの 14時間 前に 100%** → そこから `hourly` も opus」＝
    **これから 09/11 17:00 に切り替わる**と読める字を渡していました
    （しかも `landing()` の見込みは**実際の到達より 4時間 遅い**）。
    **効く所**: METHOD §5 の 15:1x は「短く終わるか」を**役ごと**に書き、
    **10:3x がそれを「その周に実際に立った模型で読むこと」と直しています** ——
    **その模型が、この段のどこにも無かった**（サブは `quota.py` を別に撃つまで、
    自分が fable なのか opus なのかを枠の段から読めません）。
    ＝ **「立てた瞬間／見込みの事実を、いまの事実として渡す」型**の 3件目
    （15:4x の `API 0単位`・06:5x の `main_gap` の 0 の枝）。
    **いまは尽きている回には、`sub_model` が返す模型を名前で並べます**（`_standing_models`）。
    **覆る条件**: (1) 役が増えたら `sub_roles()` から引くので、この段は直さなくてよい
    （既定の 2役 は `sub_roles` が読めない回のためだけ）。(2) `sub_model` が
    役ごとに違う模型を返す回（Fable が戻った枠）では、そちらの字がそのまま出ます ——
    **並びが「hourly **fable**・optimizer **opus**」になったら、§5 15:1x の役ごとの形が
    そのまま効きます**（§5 の覆る条件 (4)）。(3) この行が「もう 100%」と言っているのに
    サブが fable で立った回が出たら、見る先は `next_round_owner.corrected_sub_model`
    （親はそちらで走る）と、この段が読む `quota.sub_model` の食い違いです。

    **数**: Data API の日枠は **10,000単位/日**（16:00 JST に戻る・`studio/yt.py` 冒頭）で、
    1周が撃つのは `status`＋`measure`＋`zero_probe` ＝ **その 1% の桁**。
    ＝ **この段が作っていたのは、実在しない絞り**でした（絞りは模型の枠の側だけ・`quota.landing()`）。
    **同じ字は `TOUCHED_CMD` の註にも在りますが、あちらは命令の後ろ**（「この命令は 0単位」）＝
    アンカーが在るので直していません（**2つ目の口を撃って確かめた** ＝ §5 の教訓の形 2つ目）。
    **覆る条件**: (1) Data API の単位を周ごとに数える口が付いたら、その数をこの段へ置くこと
    （**いま数える口はどこにも無い** ＝ 「使いすぎ」を言える側が居ません）。
    (2) 日枠が 1度でも尽きたら（`quotaExceeded`）、模型の枠だけでは足りない ＝ この段に 2行目 を足すこと。
    (3) オーナーが Data API の値段に触れたら、その言葉が正本。
    """
    try:
        from scripts.quota import (JST, fable_estimate, fable_rate, landing,  # noqa: PLC0415
                                   pace)
    except Exception:                                          # noqa: BLE001
        try:
            from quota import (JST, fable_estimate, fable_rate,  # noqa: PLC0415
                               landing, pace)
        except Exception:                                      # noqa: BLE001
            return ""
    try:
        p = pace()
        if not p or not p.get("per_lap") or not p.get("floor_min"):
            return ("【枠】**読めていません**（目盛りが無いか、周が数えられていない）。"
                    "**空欄を「余裕がある」と読まないこと** —— `python scripts/quota.py --pace`。")
        fe = fable_estimate() or {}
        # **枠が戻ったかは、ここで書き直さないこと**（門は `quota.fable_rolled`・1か所）。
        # 戻っていれば `fe["est"]` は**前の枠の目盛りのまま**（`quota.fable_estimate` の註）
        # ＝ そのまま運ぶと「Fable のみ **もう 100%**」と「この周は hourly **fable**」を
        # 同じ段が並べて言います（JOURNAL 2026-09-11 20:5x・14:0x/16:3x と同じ族）。
        ration = _fable_ration()
        rolled = _fable_rolled(fe)
        fable_now = (ration.get("est") if (rolled and ration) else fe.get("est"))
        fr = fable_rate() or {}
        ratio = ((fr.get("rate") or 0.0) / p["carry_rate"]) if p.get("carry_rate") else 0.0
        land = landing(p["used_now"], p["left_hours"], p["per_lap"],
                       fable_now, p["per_lap"] * ratio,
                       lag_min=p.get("reach_lag_min") or 0.0)
        lines = [
            "【枠 —— この回に使ってよい速さ】**模型の枠の話です**"
            "（**YouTube Data API の単位はこの段に出ません** —— そちらは別の枠で、"
            "日枠 10,000単位/日・16:00 JST に戻る・`studio/yt.py` 冒頭）。"
            "オーナー 21:13「全てのモデル100％いきそう？」21:5x「その視点ないんだったら視点だけ与えなよ」",
            f"    いま      すべて **{p['used_now']:.0f}%**"
            + (f"・Fable のみ **{fable_now:.0f}%**"
               + ("（**戻った枠**の数 ＝ 前の枠の目盛りではありません）" if rolled else "")
               if fable_now is not None else "")
            + f"（リセット {p['window_reset'].astimezone(JST):%m/%d %H:%M} JST まで"
              f" {p['left_hours']:.0f}時間）",
            f"    床        **{p['floor_min']:.0f}分**（周から周。1周 {p['per_lap']:.3f}%）",
        ]
        if land.get("all") is not None:
            # **着地は小数第1位まで**（2026-09-11 11:4x・optimizer・Opus）——
            # この 2つ は METHOD §5 15:1x の覆る条件 (1)（門 98%）が読む数で、
            # `:.0f` は **門ちょうどの字**（97.5 → 「98%」）を出していた。
            # `quota.py --pace` は同じ数を 1桁 で印字するので、**2つの口が違うことを言う**形
            # （`trend.channel_line_short` の覆る条件 (2) と同じ族）。
            # **門と同じ桁で丸めないこと**（derivation は JOURNAL 09/11 11:4x）。
            # **門に当てる側を名指しすること**（2026-09-11 13:2x・optimizer・Opus）——
            # それまで この行は 2つ の数と門 98% を並べるだけで、**どちらに当てるかを言っていません**
            # でした。2つ は `per_lap` が動くと大きく割れます（床は 0.20 まで平ら・間隔は比例して落ちる）
            # ＝ **サブが読む側を選べてしまう**形です。決めは `quota.short_verdict` の註（13:1x）。
            lines.append(
                f"    リセット時  床に従えば **すべて {land['all']:.1f}%**"
                f"・いまの間隔のまま **{p['reach_carry']:.1f}%**"
                if p.get("reach_carry") is not None else
                f"    リセット時  床に従えば **すべて {land['all']:.1f}%**")
            # **門も、当てる側も、`blind` も、ここで書き直さないこと**
            # （2026-09-11 17:0x・optimizer・Opus）—— 引き比べは `quota.short_words()` が
            # `--pace` に印字する1行で、それを**そのまま**運びます。
            # 前の字はこの段の中で 門 98% を**literal で**持ち（`SHORT_LANDING_GATE` と2か所）、
            # `blind` の述語（区間の窓 ＞ 残り）も別に書き直したうえで、
            # **判定そのもの（引かれたか）は印字していません**でした ＝ サブが手で当てる形。
            # derivation と覆る条件は `_short_lines()` の註。
            lines += _short_lines(land.get("all"), p)
        spent = land.get("fable_spent_h_before_reset")
        est = fe.get("est")
        cap = _fable_cap()
        # **もう尽きた枠について、これから尽きる話を渡さないこと**
        # （2026-09-11 16:3x・optimizer・Opus。derivation は下の註と JOURNAL 16:3x）。
        if rolled:
            # **戻った枠について、尽きた枠の話を渡さないこと**（2026-09-11 20:5x・optimizer・Opus）。
            # 16:3x は逆向き（尽きた枠に「これから尽きる」）を直した回で、これはその鏡です。
            # **§5 の模型の段の覆る条件 (4) を読む印字は、ここにしかありません。**
            who = _standing_models()
            head = ""
            try:
                if ration and ration.get("start") is not None:
                    head = f"{ration['start'].astimezone(JST):%m/%d %H:%M} JST"
            except Exception:                                  # noqa: BLE001
                head = ""
            gw = _gauge_words(fe).strip("（）")           # 「目盛り 09/11 12:38 JST」
            lines.append(
                "    Fable のみ  **枠は戻りました**"
                + (f"（新しい枠の頭 {head} から **0%**" if head else "（**0%** から数え直し")
                + (f"・{gw} は**前の枠**の数）" if gw else "）")
                + (f" ＝ **この周は {who}**（`quota.sub_model`）。" if who
                   else " ＝ **この周の模型は `quota.sub_model` が決めます**（撃って読むこと）。")
                + "**§5 15:1x の `hourly` 側の形は、覆る条件 (4) で戻ります**"
                  "（§5 10:3x ＝ 役ではなく、**その周に実際に立った模型**で読むこと ——"
                  "`hourly` が fable で立つ周なら、その理由はまた在ります）")
        elif est is not None and cap is not None and est >= cap:
            who = _standing_models()
            lines.append(
                f"    Fable のみ  **もう {est:.0f}%**{_gauge_words(fe)}"
                + (f" ＝ **この周は {who}**（`quota.sub_model`）。" if who
                   else " ＝ **この周の模型は `quota.sub_model` が決めます**（撃って読むこと）。")
                + "**§5 15:1x の `hourly` 側の理由（Fable を台本を書く回に残す）は、"
                  "この周には在りません**（§5 10:3x ＝ 役ではなく、"
                  "**その周に実際に立った模型**で読むこと）")
        elif spent is not None:
            lines.append(
                f"    Fable のみ  床に従うと **リセットの {spent:.0f}時間 前に 100%**"
                f" → そこから `hourly` も opus（`quota.ROLE_TIER`）")
        elif land.get("fable") is not None:
            lines.append(f"    Fable のみ  床に従うと リセット時 **{land['fable']:.0f}%**（尽きない）")
        # **Fable の配り**（`quota.fable_ration` の註・2026-09-11 19:5x。オーナー 19:4x
        # 「フェイブルずっと使えるように調整するよな？」）。**判定は道具の 1行 をそのまま運ぶ**
        # ——この段で線を引き直さないこと（§5 教訓の形 7つ目・`_short_lines()` の註と同じ形）。
        ration_words = _fable_ration_words()
        if ration_words:
            lines.append(f"    Fable の配り  {ration_words}")
        lines += [
            "    **目盛りは 2つ・絞り（床）は 1つ** —— 床は「すべて」の残りから引かれるので、"
            "Fable の着地は床では選べません（`quota.landing()` の註・METHOD §5）。",
            "    **この数で決まる行が 1つ あります**: 「持ち場に何も無ければ短く終わるか」は、"
            "**METHOD §5 が 2026-09-10 15:1x に役ごとの着地で決めました**"
            "（覆る条件 3つ も §5。09/09 22:1x のこの段は、まだ決まっていなかった頃の字でした）。"
            "**上の判定の行は、その決めの門を `quota.short_words()` が引いた印字です** ——"
            "**親は判断しません**（09/06 14:0x）。決めのほうが動いたら、直すのはこの段ではなく "
            "**§5 と `quota.SHORT_LANDING_GATE`（門は 1か所）**。",
        ]
        return "\n".join(lines)
    except Exception:                                          # noqa: BLE001
        return ("【枠】**読めていません**（`quota` が落ちた）。"
                "**空欄を「余裕がある」と読まないこと** —— `python scripts/quota.py --pace`。")


def _siblings_block(siblings: list[str]) -> str:
    """**同じ枝で走っている相手を名指しする段。**

    空でも段を落としません —— 「いない」と書いてあることに意味があります
    （書いていないと、受け取った子は「調べていないだけ」と区別できません）。

    **枝の合わせ方はここには入りません**（2026-08-26）。
    それは `FIRST_MOVE` が1か所で持ち、型が `<<first_move>>` で**置き場所を決めます** ——
    「最初の1手」と名乗るものが本文の最後に出ていては、名前が嘘になるからです。
    **文言は1か所・位置は型の側**。どちらも重ねて書かないこと。

    ## **「別のファイルのはずです」をやめました**（2026-08-31 に踏んだ）

    ここには長らくこう書いてありました:

        **あなたの担当は、上のどれとも別のファイルのはずです。**

    **確かめようがありません。** 受け取った側は相手の名前しか渡されておらず、
    相手が何を触っているかを知る手が**1つも書かれていません**。
    だからこの行は、規則ではなく**願い**です。

    2026-08-31 の最適化の回が、そのとおり衝突しました。**実測**:

        22:34  hourly が `d2c4cae2 fix: 説明欄の測定が、日枠で止まった回を
               「チャンネルに無い」と印字していた` を push
        22:40  こちらが `a89ab889 fix: 測れていない説明欄を「0件」と印字しない`
               を commit —— **同じファイル・同じ欠陥・6分 差**
        22:42  併合で3か所が衝突。両方を残すのに、さらに1手

    **見つけた欠陥は本物でしたが、2人で見つけました。** この回の前半は、
    **相手が9分前に閉じ終えた穴を、もう一度 見つけ直すのに使われています。**

    **これは並列の税です。** `eta.py` が解いている速さは
    `rate = p·log(g)·θ` で、`θ` は**回転の数**です。2人が同じ所を掘れば
    θ は2倍ではなく1倍にしかならず、**律速そのものが半分になります。**

    ## 直し方 —— **主張を、手に替える**

    相手の作業は git に在ります。**名前ではなく、触った所を渡すこと。**
    `TOUCHED_CMD` は API 0単位・数秒で、上の衝突は**そこに出ていました**
    （`d2c4cae2` の `--name-only` に `src/descriptions.py` が並んでいる）。

    **覆る条件**: 相手が commit する前の作業は、ここに出ません
    （こちらの `a89ab889` も、撃った時点では相手に見えていない）。
    **12時間の窓は「押した所」しか見せない**ので、**押していない相手とは
    まだ衝突します。** そこを詰めるなら、次は「取ったファイルを先に宣言する」形
    —— ただしそれには**押す前に見える置き場**が要り、この枝には在りません。

    ## **窓は 3分 で古くなります**（2026-09-07 10:2x・optimizer が数えた）

    「押していない相手とはまだ衝突する」の**大半は、押していないのではなく、
    こちらが早く見すぎている**だけでした。実測（周の記録 → 相手のその回の最初の押し）:

        10:18 → 10:21   08:17 → 08:20   05:44 → 05:47   03:13 → 03:16   （00:42 → 00:50）

    **直近5周のうち4周で 3分。** サブが窓を撃つのは周の 0〜1分 なので、
    **開始時の窓には、相手のその回の押しが構造的に出ません。**
    この回も 10:19 の窓に hourly の 10:21（`docs/METHOD.md`）は出ておらず、
    その窓だけで「METHOD は空いている」と読んでいれば §11 でぶつかっていました。

    だから渡す手は1回ではなく2回です —— **担当を決めるとき**と、
    **共有ファイルに書き始める直前**。同じ命令・API 0単位・数秒。

    **覆る条件**: 2回目の窓で相手の押しが見えたのに、それでも同じファイルを
    2体が直した回が出たら、足りないのは窓ではなく**取り分の決め方**
    （`docs/METHOD.md` §5 の表）。そのときは表のほうを直すこと。
    """
    if not siblings:
        head = ("**同じ枝で他に走っている相手は、立てた時点ではいません。**\n"
                "それでも push 前に必ず `git fetch`。競合したら merge で"
                "**相手の作業を残すこと。捨てないこと。**")
    else:
        named = "／".join(siblings)
        head = ("**いま同じ枝で走っています: " + named + "**\n"
                "**どこを担当するかを決める前に、相手が触った所を見ること**"
                "（API 0単位・数秒）:\n\n"
                "    " + (TOUCHED_CMD % "<<branch>>") + "\n\n"
                "**ここに出たファイルは、取られていると読むこと。**\n"
                "**「別のファイルのはずです」とだけ書いてあった型で、"
                "2026-08-31 に実際にぶつかりました** —— 同じファイルの同じ欠陥を、"
                "6分 差で2人が直しています（`src/descriptions.py`・`d2c4cae2` と "
                "`a89ab889`）。**見つけた欠陥は本物でしたが、2人で見つけました。**\n"
                "**押す前の作業は、この窓に出ません。** それでも、"
                "**押し終わった所を避けるだけで、この回の衝突は防げていました。**\n"
                "**この窓は 3分 で古くなります**（2026-09-07 10:2x・optimizer が数えた）。"
                "相手のその回の最初の押しは、周の記録の **3分後**でした"
                "（直近5周のうち4周: 10:18→10:21・08:17→08:20・05:44→05:47・03:13→03:16）。"
                "サブが窓を撃つのは周の 0〜1分 なので、**開始時の窓には相手のその回の押しが出ていません** ——"
                "この回も 10:19 の窓に hourly の 10:21（`docs/METHOD.md`）は出ていませんでした。"
                "**共有ファイル（`docs/METHOD.md`・`studio/`・台帳）に書き始める直前**に同じ命令を"
                "もう一度 撃つと、そこは見えます（API 0単位・数秒）。\n"
                "push 前に必ず `git fetch`。競合したら merge で"
                "**相手の作業を残すこと。捨てないこと。**")
    return head + AUTHORITY


def build(kind: str, note: str = "", siblings: list[str] | None = None,
          only: str = "", root: Path = ROOT, live_clock: bool = True) -> str:
    if kind not in KINDS:
        raise SystemExit(f"[!] --kind は {'/'.join(KINDS)} のどれか（受け取った: {kind}）")
    tpl = templates(root / "docs" / "spawn_prompt.md")
    body = tpl[kind]
    note, only = (note or "").strip(), (only or "").strip()
    if kind.startswith("owner") and not note:
        raise SystemExit("[!] `--kind owner-*` には `--note \"<原文>\"` が要ります。"
                         "**要約しないこと。** 数字は桁もそのまま写すこと")
    note_block = ("**申し送り（原文のまま。要約されていません）:**\n\n> "
                  + note.replace("\n", "\n> ")) if note else ""
    # **枝の名前は spec から。型に書き写さないこと**（2026-08-25 夜に足した）。
    # サブへ移してから `source_revision` の口が無くなり、**ワークツリーが
    # `main` から切られる**ようになりました（実測: 8/25 夜のサブ3枚が3枚とも）。
    # 型の「最初の1手」がこの名前を使うので、**spec と食い違わせないこと。**
    try:
        branch = json.loads(
            (root / "docs" / "trigger_spec.json").read_text(encoding="utf-8"))["branch"]
    except Exception:
        branch = ""            # spec が読めない回でも、型そのものは組み立てる
    filled = {
        "branch": branch,
        "note": note,
        "only": only,
        "note_block": note_block,
        # 写し（live_clock=False）には数を焼かない: MAIN_GAP_STATIC の註
        "first_move": FIRST_MOVE.strip().replace(
            "<<main_gap>>", main_gap(root, branch) if live_clock else MAIN_GAP_STATIC),
        "siblings_block": _siblings_block(list(siblings or [])),
        # 写し（live_clock=False）には数を焼かない: MAIN_GAP_STATIC の註と同じ。
        # **ただし段ごと落とさないこと** —— 型の側が「下の【枠】の段」を指しているので、
        # 空にすると写しの中でその指し先が消えます（この repo の「言っている所と
        # している所が別」の、いちばん小さい形）。静的な1行を置く。
        "quota_block": _quota_block() if live_clock else QUOTA_BLOCK_STATIC,
        "clock_block": _clock_block(live=live_clock),
        "lead": (tpl["lead-only"].replace("<<only>>", only) if only
                 else tpl["lead-round"]),
    }
    out: list[str] = []
    for line in body.splitlines():
        key = line.strip()
        if key.startswith("<<") and key.endswith(">>"):
            value = filled.get(key[2:-2], "")
            if value:                        # 空の差し込み口は、行ごと落とす
                out.append(value)
            continue
        for name, value in filled.items():
            line = line.replace(f"<<{name}>>", value)
        out.append(line)
    text = "\n".join(out)
    # **差し込み口の中の差し込み口**（2026-08-25 夜に踏んだ）。
    # `<<lead>>` は段まるごと差し込むので、**その中の `<<branch>>` は
    # 上の行ごとの置換を通りません。** 組み上げたあとで、もう一度当てること。
    # ここを飛ばすと、子は `git merge origin/<<branch>>` を**そのまま読みます。**
    #
    # **2026-08-26 に `<<first_move>>` で同じ穴を踏みました。** 「最初の1手」を
    # `<<lead>>` の中へ置いた瞬間、上の行ごとの置換を通らなくなり、
    # 出来上がった本文に `<<first_move>>` の6文字がそのまま残りました。
    # **段まるごと差し込む口の中に置いた差し込み口は、全部ここで当て直すこと。**
    text = text.replace("<<first_move>>", filled["first_move"])
    text = text.replace("<<branch>>", branch)      # FIRST_MOVE の中にも枝名がある
    # **停止中は、それを本文のいちばん先頭へ。** 型の途中だと後ろ回しになります。
    text = _pause_block(root) + text
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


def create_session_args(kind: str, root: Path = ROOT, **kw) -> dict:
    """`create_session` にそのまま渡せる一式。

    **`source_url` と `source_revision` は省略できません**（2026-08-18 に踏んだ）。
    `environment_id` は継がれますが `sources` は継がれないので、**継がれる側から
    「repo も継がれる」と読めてしまう**のがこの穴の正体です。ここでは常に入れます。
    """
    spec = json.loads((root / "docs" / "trigger_spec.json").read_text(encoding="utf-8"))
    return {
        "source_url": spec["repo_url"],
        "source_revision": spec["branch"],
        "environment_id": spec["environment_id"],
        # **役ごとに札を分けます**（2026-08-24。オーナー提案「並行して、主実行を
        # 目標に最適化し続ける子を動かしたら？」）。**親は札で子の生死を見る**ので、
        # 分けないと「最適化の子が走っている」を「主実行が走っている」と読み、
        # **主実行が立たなくなります。**
        "tags": ["youtube-optimizer" if kind == "optimizer" else "youtube-hourly"],
        "prompt": build(kind, root=root, **kw),
    }


RENDERED = ROOT / "docs" / "spawn_prompt.rendered.md"

# 親向けの写しに残す差し込み口。**親は repo を触れないので、この道具を回せません。**
# テンプレートだけ置くと、親は組み立てを暗算することになり、**そこが「要約して
# 条件を落とす」（8/10）の入口**です。だから **1ファイル取って、2か所だけ
# 埋めて貼る**形にします。埋めるのは、repo からは絶対に求まらない2つだけ。
_NOTE_SLOT = "<<オーナーの言葉を、ここに原文のまま。要約しない。数字は桁もそのまま>>"

# **差し込み口は1つだけにします**（2026-08-25 に減らした）。
#
# それまで siblings 側にも `<<いま走っている子の識別子。いなければこの行ごと消す>>`
# を置いていました。ところが親の手順は「`prompt` を **1字も変えずに**渡す」です。
# **両方を守ると、サブはプレースホルダの文字列を、走っている相手の名前として
# 受け取ります。** `_siblings_block()` は「**いないと明記してある**ことに意味がある」
# （調べていないだけと区別できない）ために作った段なので、
# **逐語コピーの規則が、その段の意味をちょうど壊していました。**
#
# だから写しでは **`siblings=[]`（「いません」と書いてある側）を既定**にします。
# 走っている相手を親が知っている回だけ、その1文を差し替えること。
#
# **覆る条件**: 親が走っているサブを承認なしで数えられるようになったら
# （`ListAgents` が前の親のサブまで見えるなら）、写しではなく `next_round.py` に
# 数えさせて埋めること。**親に暗算させないこと**が、この節の要点です。


#: **写しの既定で名指しする相手**（2026-09-03 05:xx・最適化の回に足した）。
#:
#: 上の註は「走っている相手を親が知っている回だけ、その1文を差し替えること」と書いていましたが、
#: 親は `prompt` を1字も変えずに渡す（`docs/trigger_parent.md`）ので、差し替える手は**一度も起きません**。
#: いっぽう `next_round.py` は「2種類そろって1周」で、**hourly と optimizer は毎周 同じ瞬間に立ちます** ——
#: ＝ 「立てた時点ではいません」は、写しの既定として**毎周 偽**でした。
#: 実測 2026-09-03 04:5x〜05:0x: hourly（`d2f7fe05`）とこの最適化の回が、同じ台本
#: （`data/scripts/nenkin-uketorikata-65-70-75-handan.script.json`）の同じ 4コマ を 10分差で書き直し、併合で `AA` 衝突。
#: 08-31 22:3x（`src/descriptions.py`・6分差）と同じ形の**並列の税**が、写しの1文で隠れていました。
#: 役の名で名指しすれば、受け取った側は `TOUCHED_CMD` を撃って相手の押した所を避けられます。
#:
#: **覆る条件**: `next_round.py` が役を1つずつ立てる形に戻ったら（交互）、ここは空に戻すこと。
#: `owner-*` は親が単独で立てる（`next_round_owner.py`）ので名指ししません。
SAME_ROUND_SIBLINGS: dict[str, list[str]] = {
    "hourly": ["optimizer（同じ周に親が一緒に立てる役。`next_round.py` は2種類そろって1周）"],
    "optimizer": ["hourly（同じ周に親が一緒に立てる役。`next_round.py` は2種類そろって1周）"],
}


def write_rendered(root: Path = ROOT) -> Path:
    """**親がそのまま貼れる形**を1ファイルに書き出す。"""
    parts = ["# 子に渡すプロンプト（**親向けの写し。そのまま貼れます**）",
             "",
             "**この写しは `scripts/spawn_prompt.py --write-rendered` が作ります。"
             "手で直さないこと** —— 直すのは `docs/spawn_prompt.md` の型のほうです。",
             "",
             f"差し込み口は `owner-*` の1つだけ: `{_NOTE_SLOT}`。",
             "**`hourly` / `optimizer` は差し込み口がありません。"
             "1字も変えずにそのまま渡せます。**",
             "**それ以外は1字も変えないこと**（`source_url` を落とすと、"
             "repo の無い子が立ちます。8/17・8/18 に2回）。",
             ""]
    for kind in KINDS:
        note = _NOTE_SLOT if kind.startswith("owner") else ""
        # **`live_clock=False`**: 写しは commit される静的な生成物なので、
        # 時刻を焼き込むと書き出した次の分から永久に赤になります
        # （`_clock_block()` の註）。**立てる瞬間の本文には入ります。**
        args = create_session_args(kind, note=note, siblings=list(SAME_ROUND_SIBLINGS.get(kind, [])),
                                   only="", root=root, live_clock=False)
        parts += [f"## kind: {kind}", "", "```json",
                  json.dumps(args, ensure_ascii=False, indent=2), "```", ""]
    RENDERED.write_text("\n".join(parts), encoding="utf-8")
    return RENDERED


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="子に渡すプロンプトを組み立てる")
    ap.add_argument("--kind", default="hourly", choices=list(KINDS))
    ap.add_argument("--note", default="", help="オーナーの言葉を**原文のまま**")
    ap.add_argument("--siblings", default="", help="同じ枝で走っている相手（カンマ区切り）")
    ap.add_argument("--only", default="", help="「この回はこれだけ」の中身")
    ap.add_argument("--json", action="store_true",
                    help="create_session の引数一式で出す")
    ap.add_argument("--write-rendered", action="store_true",
                    help="親向けの写し（docs/spawn_prompt.rendered.md）を書き直す")
    args = ap.parse_args(argv)
    if args.write_rendered:
        print(f"書きました: {write_rendered().relative_to(ROOT)}")
        return 0
    sibs = [s.strip() for s in args.siblings.split(",") if s.strip()]
    if not args.siblings.strip():
        # **`--siblings` を省いた CLI も、写しと同じ既定で名指しする**（2026-09-06 22:3x・hourly）。
        # `docs/trigger_body.md` は親に「`spawn_prompt.py --kind hourly` で出し、一字一句そのまま」と
        # 言っていて、この口の既定が `[]` だったので、`--write-rendered` が 09/03 から名指ししていても
        # 親が実際に渡す本文は毎周「立てた時点ではいません」だった（実測 09/06 22:10 JST: `rounds.jsonl` に
        # hourly と optimizer が同じ秒で立っているのに、hourly の本文は「いません」）。
        # 「いない」と明示したいときは `--siblings ""` ではなく `--siblings -` を渡す。
        sibs = list(SAME_ROUND_SIBLINGS.get(args.kind, []))
    elif args.siblings.strip() == "-":
        sibs = []
    kw = {"note": args.note, "siblings": sibs, "only": args.only}
    if args.json:
        print(json.dumps(create_session_args(args.kind, **kw),
                         ensure_ascii=False, indent=2))
    else:
        print(build(args.kind, **kw), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
