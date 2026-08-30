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
`origin/main` は枝の先頭まで進めてあるので、**もう `CLAUDE.md` では衝突しません。**
それでも撃つのは、空振りが数秒なのに対し、**外していたときは読む手順そのものが古くなる**から ——
実測 2026-08-26 06:02 のサブは、`docs/trigger_main.md` が**無い**所から始まっています
（`main` を進めたのは、その45分 後）。競合したら **merge で相手の作業を残すこと。捨てないこと。**
"""


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
           "（正本は `AUTOMATION_PAUSED.md`・根拠は `data/resume_gate.jsonl`。"
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
                   " **正本の `AUTOMATION_PAUSED.md` はまだ在ります** ——"
                   "つまり生成も投稿も塞がったままです。"
                   " **消して再開するかどうかは、この機械の判断で決めないこと**"
                   "（理由3つは `AUTOMATION_PAUSED.md` の"
                   "「6件とも記録されました」の節と `CLAUDE.md`）。")
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


def _pause_block(root: Path) -> str:
    doc = root / "AUTOMATION_PAUSED.md"
    if not doc.exists():
        return ""
    return """# **【停止中】この回は、動画を作らない・出さない・予約を触らない**

**オーナーが 2026-08-30 に、いまのやり方を止めました**（`AUTOMATION_PAUSED.md`・
`origin/main` へ直接 push した8件。作者もコミッタも bachikoljunior-blip）。
**推測ではありません。止まっているのは「いまのやり方」であって、目標ではありません。**

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
                "push 前に必ず `git fetch`。競合したら merge で"
                "**相手の作業を残すこと。捨てないこと。**")
    return head + AUTHORITY


def build(kind: str, note: str = "", siblings: list[str] | None = None,
          only: str = "", root: Path = ROOT) -> str:
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
        "first_move": FIRST_MOVE.strip(),
        "siblings_block": _siblings_block(list(siblings or [])),
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
    text = text.replace("<<first_move>>", FIRST_MOVE.strip())
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
        args = create_session_args(kind, note=note, siblings=[], only="",
                                   root=root)
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
    kw = {"note": args.note, "siblings": sibs, "only": args.only}
    if args.json:
        print(json.dumps(create_session_args(args.kind, **kw),
                         ensure_ascii=False, indent=2))
    else:
        print(build(args.kind, **kw), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
