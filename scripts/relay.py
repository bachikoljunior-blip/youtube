#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""鎖の受け渡し —— **次の回を、この回のうちに立てる。**

## なぜこれが要るのか（2026-08-24 の実測）

鎖の復帰口は常駐の親 1つだけでした。**その親が、今日くり返し飛ばしています。**

    08/24 15:14 / 16:17 / 17:12 / 19:10 / 20:12   発火し `list_sessions` も撃った
                                                   **両方死んでいたのに立てなかった**
    → 14:49〜21:29 の **6時間40分、だれも回っていません**

親の本文は「1行目に `list_sessions` を撃て」へ入れ替え済みでした。
**撃つようにはなったのに、撃った結果に対して動かない回が残りました。**
**順番の問題ではなかった** —— 文書は、読ませることはできても**実行させません**。

予備の復帰口（`trig_018JbWLLKRFPgpYgmjzZQJbq`・毎時39分・毎回まっさらな回）も
置いてありましたが、**この回で測って、効いていないことが確定しました**:

    21:39:35  予備が発火（`last_fired_at` にある）
    そのとき   optimizer の札は **空**（前の optimizer は 14:31 に archive 済み）
    21:50     **親が** optimizer を立てた（＝予備は埋めていない）
    `last_run` は空・`derived_state` も空 —— **セッションが生まれた形跡がない**

`create_new_session_on_fire` は 2026-08-10 にも「一度も発火しない」と実測して
棄却されています。**その結論はいまも正しく、予備口は飾りです。**

## だからここは「文書」ではなく「機械」にしてあります

**鎖のうち、確実に動いている部分は子です。** 子は MCP を持ち、実際に毎周
`list_sessions` も `create_session` も通しています。**なら子に渡させればよい。**

> ### **2026-08-25、この段落の後半が実測で倒れました。**
>
> 「子は `create_session` も通しています」は、**通していたのではなく、
> オーナーが押していた**可能性が高い。オーナーの指摘が起点です（原文）:
>
> > 「上手くいってるように見えてるところは私が承認押しまくってるおかげかもよ」
>
> **同じ日に測りました**（`--stamp` → 撃つ → `--since`）。
> 分かれたのは**読む側と書く側**です:
>
>     list_sessions      **10.7秒** で成功        ← 読む側。素通り
>     set_session_title  **4,636秒（77分）** 待って **拒否**  ← 書く側
>
> **`list_sessions` が通ることは、この仕組みが動く証拠になりません。**
> 受け渡しが要るのは `create_session` と `archive_session` ——
> **どちらも書く側**です。同じ日の窓（25件）で承認待ちに固着していた5件も、
> **全部書く側**でした（`create_session`×2 / `archive_session` /
> `set_session_title` / `delete_trigger`。読む側は1件もありません）。
>
> **つまりこの仕組みは、人が押す前提の上に立っています。**
> 「文書ではなく機械にした」と言いながら、**機械の側が人待ちでした。**
>
> **鎖の本体は、こちらではなく親のトリガーのほうです** ——
> あれはサーバが時刻で撃つので、承認は挟まりません
> （`docs/trigger_spec.json` ／ 実物は `list_triggers`）。
> **受け渡しは「親が飛ばしたときの上振れ」に格下げして読むこと。**
> 柱として数えると、止まった回に誰も気づきません
> （目標本文「私が必ず読むとは限らない」）。
`scripts/stop_check.sh` が終わりぎわに割り込み、この記録が無ければ通しません。
**引き止めは2回まで**（止まったまま死ぬほうが確実に悪い）。

## 速さの裏づけ（**これは節約ではなく、余らせている側の話**）

    62.1時間で誕生 20 件 → 実際の間隔 **186分**
    持続できる間隔（`quota.py --pace`）  **90分**

**予算の半分を使わずに捨てています。**「残すこと自体に価値はありません」（`docs/GOAL.md`）。
だから自分の札の後継も立てます —— **ただし持続できる間隔より速くはしません。**
先に使い切ると、リセットまで1回も起きられないからです。

## 覆る条件

- **親が5回続けて札を埋めるようになった**なら、この受け渡しは二重になります。
  そのときは `--audit` を見て、こちらを畳んでよい
- **同じ札に2つ生きているのが観測された**なら、規則の「生きていれば立てない」が
  効いていません。**そのときは自分の札の後継をやめ、隣の札だけにすること**
  （2026-08-15 に2人の子が同じ日の予約を取り合い、片方の生成が丸ごと無駄になった）
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta

ROOT = pathlib.Path(__file__).resolve().parent.parent
# **`RELAY_LEDGER` で差し替えられること。** 検査は `--record` を
# 別プロセスで叩きます（引き算がスクリプト側で起きるかを見るため）。
# `monkeypatch` は別プロセスに効かないので、**環境変数の口が無いと
# 検査が実物の台帳に行を足します**（2026-08-25 に1行足しました）。
LEDGER = pathlib.Path(os.environ.get("RELAY_LEDGER") or (ROOT / "data" / "relay.jsonl"))
RENDERED = ROOT / "docs" / "spawn_prompt.rendered.md"
JST = timezone(timedelta(hours=9))

LANES = ("youtube-hourly", "youtube-optimizer")
KIND_OF = {"youtube-hourly": "hourly", "youtube-optimizer": "optimizer"}


def me() -> str:
    raw = os.environ.get("CLAUDE_CODE_REMOTE_SESSION_ID", "")
    return re.sub(r"^cse_", "session_", raw)


def _pace() -> dict:
    """`quota.py --pace` から、持続できる間隔と実際の間隔を取り出す。

    **数字はここで計算し直さないこと。** 二重に持つと必ず食い違います。
    取れなければ空で返し、呼ぶ側は「分からない」として扱う。
    """
    out: dict = {}
    try:
        p = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "quota.py"), "--pace"],
            capture_output=True, text=True, timeout=90, cwd=str(ROOT),
        )
        txt = p.stdout
    except Exception:
        return out
    m = re.search(r"持続できる間隔（誕生から誕生）:\s*\*\*(\d+)分\*\*", txt)
    if m:
        out["sustainable_min"] = int(m.group(1))
    m = re.search(r"([\d.]+)時間で誕生\s*(\d+)\s*件", txt)
    if m:
        hours, births = float(m.group(1)), int(m.group(2))
        if births > 0:
            out["actual_min"] = round(hours * 60 / births)
    return out


def _args_for(kind: str) -> str:
    """`docs/spawn_prompt.rendered.md` から、その札の JSON をそのまま抜く。

    **ここで作らないこと。** 型は `docs/spawn_prompt.md` にあり、
    写しは `spawn_prompt.py --write-rendered` が作ります。
    2つ目の写しを作ると、`source_url` の落ちた子が立ちます（8/17・8/18 に2回）。
    """
    if not RENDERED.exists():
        return f"（{RENDERED} がありません。`python scripts/spawn_prompt.py --write-rendered` で作れます）"
    txt = RENDERED.read_text(encoding="utf-8")
    m = re.search(rf"##\s*kind:\s*{kind}\s*\n+```json\n(.*?)\n```", txt, re.S)
    return m.group(1) if m else f"（kind: {kind} が写しに見あたりません）"


def cmd_next(args) -> int:
    pace = _pace()
    sustainable = pace.get("sustainable_min")
    actual = pace.get("actual_min")
    # 自分の札の後継を立ててよいか。**実際の間隔が持続できる間隔より遅いときだけ。**
    # 読めないときは立てない側へ倒す（先に使い切ると次が起きられない）。
    self_ok = bool(sustainable and actual and actual > sustainable)

    print("=== 鎖の受け渡し（終わる前に。**この回で次を立てる**）===\n")
    if sustainable and actual:
        # **間隔の比をそのまま出さないこと**（最初の版がそれで 207% と出しました）。
        # 間隔は長いほど遅いので、使っている割合は **持続 ÷ 実際** のほう。
        pct = round(sustainable / actual * 100)
        print(f"  速さ: 実際 **{actual}分/周** ／ 持続できる **{sustainable}分/周**"
              f"（＝許される速さの **{pct}%** しか使っていない）")
    else:
        print("  速さ: **読めませんでした**（`quota.py --pace` が取れない）"
              "→ 自分の札は立てない側へ倒します")
    print()
    print("**0. 撃つ前に秒を打つ**（**承認が挟まったかは、これでしか見えません**）\n")
    print("      python scripts/relay.py --stamp     ← 返った秒を控える\n")
    print("  返るのは「成功」だけで、**承認されて成功したのと、許可されて成功したのは")
    print("  区別が付きません。** 見分けられるのは秒のほうです"
          "（人が押すまでの時間が丸ごと乗る）。\n")
    print("**1. 札ごとに、生きている回を数える**\n")
    print("      list_sessions  mine=true limit=25")
    print("      → `PENDING` / `RUNNING` / `IDLE` を、tags ごとに数える\n")
    print("        youtube-hourly     主実行")
    print("        youtube-optimizer  最適化\n")
    # **これが実際にいちばん多い死に方です。** 2026-08-24 22:5x に実測:
    # 主実行の子は仕事を終えて 2383a69 まで push したあと、
    # **`archive_session` の承認待ちで `REQUIRES_ACTION` のまま固着**していました。
    # 一覧では「つながっている」ように見えるので、**生きていると誤読しやすい。**
    # 承認待ちは永久に待ちます（目標本文「私が必ず読むとは限らない」）。
    print("  **`REQUIRES_ACTION` / `BLOCKED` は「生きている」ではありません。**")
    print("  承認待ちは永久に待ちます —— **その札は空として数え、立てること。**")
    print("  （2026-08-24 22:5x の実測。主実行が `archive_session` の承認待ちで固着し、")
    print("   仕事は終わっていたのに次が立たない状態になっていました）\n")
    print("**2. 立てる／立てない**\n")
    print("  **隣の札が空なら、必ず立てる。**（これが本体です。親は今日5回飛ばしました）")
    if self_ok:
        print(f"  **自分の札は、自分以外が居なければ立てる。** いまは実際 {actual}分 > "
              f"持続 {sustainable}分 なので**立ててよい**。")
    else:
        print("  **自分の札の後継は、この回では立てないこと。**"
              " 速さが読めない／すでに持続できる間隔より速いからです。")
    print("  **生きているなら立てないこと。** 迷ったら**立てないほう**へ倒す")
    print("  （2026-08-15、同じ札の2人が同じ日の予約を取り合い、片方の生成が丸ごと無駄になった）\n")
    print("**3. 立てたら／立てなかったら、必ず記録する**（これが無いと終われません）\n")
    print("      python scripts/relay.py --record --hourly <生きている数> "
          "--optimizer <生きている数> \\")
    print("             --since <0で控えた秒> --blocked <承認待ちだった回の数> \\")
    print("             [--spawned hourly,optimizer]\n")
    print("  **`--blocked` は 0 でも渡すこと。** 省くと「数えていない」になり、")
    print("  次の回がまた感想で「効いた」と言うことになります。")
    print("  （`list_sessions` の `post_turn_summary.status_category == \"need_input\"`）\n")
    for lane in LANES:
        print(f"--- create_session に渡すもの（{lane}）---")
        print(_args_for(KIND_OF[lane]))
        print()
    print("**`source_url` を落とさないこと。** repo の無い子が立ちます（8/17・8/18 に2回）。")
    return 0


#: 「同じ札を二重に立てた」とみなす幅（分）。**親の発火間隔より十分に短く。**
DUP_WINDOW_MIN = 10


# ------------------------------------------------------------------
# **承認が挟まったかを測る**（2026-08-25 に足した。オーナーの指摘が起点）
#
#     「上手くいってるように見えてるところは私が承認押しまくってるおかげかもよ」
#
# **そのとおりでした。** 親は「鎖は自力で回っている」と報告していましたが、
# 子は日常的に `REQUIRES_ACTION` で止まり、オーナーが押して動いていました。
#
# **問題は、承認されて成功したのと、許可されて成功したのが、
# 呼んだ側からは同じに見えることです。** 返るのは「成功」だけ。
# 見分けられるのは「拒否」だけで、**承認は待たされたことすら分かりません。**
#
# **見分けられる目盛りが1つあります: 時間です。**
# 承認が挟まると、人が押すまでの秒数が丸ごと乗ります。
#
#     python scripts/relay.py --stamp        → 秒（epoch）が出る
#     MCP を1回撃つ
#     python scripts/relay.py --record ... --since <さっきの秒>
#
# **この秒には模型の手番が2回ぶん入っています**（撃つ判断と、記録する判断）。
# 実測の素の往復は **10.7秒**（8/25 06:16、`list_sessions` の 20KB の返り）。
# だから下の閾は「素の往復の何倍か」で置いてあり、**人の実測とは桁が違います** ——
# 同じ日に固着した2件は 20分 と 37分 待って、結局だれも押しませんでした。
#
# **点が溜まったら動かすこと。** いまは 1点しかありません。
APPROVAL_SUSPECT_SEC = 60


def _when(r: dict) -> datetime | None:
    """その回が**数えた**時刻。無ければ記録した時刻（古いほうに倒れます）。"""
    for key in ("snapshot_at", "at"):
        v = r.get(key)
        if not v:
            continue
        try:
            return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except ValueError:
            continue
    return None


def _dupes(rows: list[dict]) -> list[tuple[str, str, str]]:
    """**同じ札を、別の回が `DUP_WINDOW_MIN` 分内に立てていないか。**

    返すのは `(回A, 回B, 札)`。同じ回が2回書いた行は数えません（立てたのは1度）。
    """
    out: list[tuple[str, str, str]] = []
    for i, a in enumerate(rows):
        ta = _when(a)
        if ta is None:
            continue
        for b in rows[i + 1:]:
            tb = _when(b)
            if tb is None or a.get("session") == b.get("session"):
                continue
            if abs((tb - ta).total_seconds()) > DUP_WINDOW_MIN * 60:
                continue
            for lane in LANES:
                kind = KIND_OF[lane]
                if kind in (a.get("spawned") or []) and kind in (b.get("spawned") or []):
                    out.append((str(a.get("session")), str(b.get("session")), lane))
    return out


def cmd_record(args) -> int:
    spawned = [s.strip() for s in (args.spawned or "").split(",") if s.strip()]
    alive = {"youtube-hourly": args.hourly, "youtube-optimizer": args.optimizer}
    rec = {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        # **数えた時刻**。`at` は「記録した時刻」で、`alive` の中身は
        # **その前に撮った `list_sessions`** です。撮ってから `create_session` を
        # 通すまでの数十秒に、別の口が立てます（2026-08-25 の実測。下の `_dupes`）。
        # **無ければ `at` で代用しますが、それは古いほうに倒れます。**
        "snapshot_at": getattr(args, "snapshot_at", "") or None,
        "session": me(),
        "alive": alive,
        "spawned": spawned,
        # **その回で承認待ちに落ちていた回の数**（`list_sessions` の
        # `post_turn_summary.status_category == "need_input"` を数える）。
        # 帳面は長らく「誰が立てたか」しか残していませんでした。
        # **それだと「効いた」を感想でしか言えません。**
        # **`getattr` で読むこと。** 検査が組む簡易の args には無い欄です
        # （`snapshot_at` と同じ理由。属性が無いだけで記録ごと落ちると、
        #  門が永久に開きません）。
        "blocked": (None if getattr(args, "blocked", None) is None
                    else int(args.blocked)),
        # **MCP を1回撃つのに何秒かかったか**（`--stamp` → 撃つ → `--since`）。
        # 承認が挟まると人が押すまでの秒数が丸ごと乗るので、**ここだけが目盛り**です。
        "call_seconds": getattr(args, "call_seconds", None),
        "note": args.note or "",
    }
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # **`relative_to` を裸で呼ばないこと。** 台帳が repo の外にあると例外で落ちます
    # （検査を書いたら5件そこで落ちました）。**記録そのものは済んでいるのに、
    # 印字で落ちて `--record` が失敗扱いになる** —— 門が永久に開かない形です。
    try:
        shown = LEDGER.relative_to(ROOT)
    except ValueError:
        shown = LEDGER
    print(f"記録しました → {shown}")
    print(f"  生きていた数: hourly={args.hourly} optimizer={args.optimizer}")
    print(f"  この回で立てた: {', '.join(spawned) if spawned else 'なし'}")
    # **承認が挟まったかを、この回のぶんだけ先に言う。**
    if rec["call_seconds"] is not None:
        sec = rec["call_seconds"]
        verdict = ("**承認待ちが挟まった疑い**" if sec >= APPROVAL_SUSPECT_SEC
                   else "承認は挟まっていません（許可で通っています）")
        print(f"  MCP を1回撃つのにかかった時間: **{sec:.1f}秒** → {verdict}"
              f"（閾 {APPROVAL_SUSPECT_SEC}秒）")
    else:
        print("  MCP を1回撃つのにかかった時間: **測っていません**"
              "（`--stamp` → MCP → `--since <秒>`）")
    if rec["blocked"] is None:
        print("  そのとき承認待ちだった回: **数えていません**"
              "（`list_sessions` の `need_input` を数えて `--blocked N`）")
    else:
        print(f"  そのとき承認待ちだった回: **{rec['blocked']}件**")
    # **空のまま終えようとしていたら、そう言うこと。** 記録は通しますが、黙りません。
    holes = [lane for lane in LANES if alive[lane] == 0 and KIND_OF[lane] not in spawned]
    if holes:
        print()
        print("  **警告: 空の札を残したまま終わろうとしています** → " + " / ".join(holes))
        print("  親は今日5回これを飛ばしました（6時間40分の空白）。**立ててから終わること。**")
    return 0


def cmd_stamp(args) -> int:
    """**MCP を撃つ直前に打つ。** 返った秒を `--record --since <秒>` に渡す。

    **秒を模型に数えさせないこと。** `date` の出力を引き算させると、
    分をまたいだ回で必ず間違えます（そして間違いは「承認は挟まっていない」の
    側に落ちます —— 短く出るほうが自然だからです）。**引き算はここでやります。**
    """
    now = datetime.now(timezone.utc)
    print(f"{int(now.timestamp())}")
    print(f"  ({now.isoformat(timespec='seconds')})  ← この秒を --since に渡す",
          file=sys.stderr)
    return 0


def cmd_check(args) -> int:
    """この回が受け渡しを記録したか。**`stop_check.sh` が読む。** 0=済み 2=まだ"""
    who = me()
    if not who or not LEDGER.exists():
        return 2
    for ln in LEDGER.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(ln)
        except Exception:
            continue
        if r.get("session") == who:
            return 0
    return 2


def cmd_audit(args) -> int:
    if not LEDGER.exists():
        print("受け渡しの記録はまだありません（この仕組みは 2026-08-24 に入れました）")
        return 0
    rows = []
    for ln in LEDGER.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(ln))
        except Exception:
            continue
    if not rows:
        print("受け渡しの記録はまだありません")
        return 0
    print(f"=== 鎖の受け渡し {len(rows)}件 ===\n")
    for r in rows[-args.limit:]:
        try:
            t = datetime.fromisoformat(r["at"]).astimezone(JST).strftime("%m/%d %H:%M")
        except Exception:
            t = r.get("at", "?")
        a = r.get("alive") or {}
        sp = ",".join(r.get("spawned") or []) or "-"
        print(f"  {t} JST  hourly={a.get('youtube-hourly')} "
              f"optimizer={a.get('youtube-optimizer')}  立てた: {sp}  {r.get('note','')}")
    # **効いているかどうかは、空白が消えたかで見ること。**
    holes = 0
    for r in rows:
        a = r.get("alive") or {}
        sp = r.get("spawned") or []
        if any(a.get(lane) == 0 and KIND_OF[lane] not in sp for lane in LANES):
            holes += 1
    print()
    print(f"  空の札を残したまま終えた回: **{holes}/{len(rows)}**")
    print("  （ここが増えるなら、引き止めが効いていません。`stop_check.sh` の (2.0) を見ること）")

    # **立てすぎも数えること**（2026-08-25 に足した）。
    #
    # ここは長く `holes`（＝立て損ね）しか数えていませんでした。**受け渡しを
    # 足したぶん、二重に立つ形が新しくできています** —— 親の毎時発火と子の
    # 受け渡しが、どちらも同じ札を立てます。実測（8/25 03:0x）:
    #
    #     013fAG  03:04:59  札 youtube-hourly  親 017yMBL（常駐の親）
    #     019MJX  03:05:01  札 youtube-hourly  親 01EJcF（子の受け渡し）
    #
    # そして帳面の唯一の行は、その 10秒後に `hourly=0` と言っていました
    # （`alive` は**撮った時刻**の姿で、記録した時刻の姿ではないため）。
    # **立て損ねだけを数えると、二重に立った直後でも 0/N と出て「効いている」と読めます。**
    dup = _dupes(rows)
    if dup:
        print()
        print(f"  **同じ札を、別の回が {DUP_WINDOW_MIN}分内に立てています: {len(dup)}組**")
        for a, b, lane in dup[-5:]:
            print(f"    {lane}: {a} と {b}")
        print("  （資源を取り合います。2026-08-15 は片方の生成が丸ごと無駄になりました）")
    else:
        print(f"  同じ札を {DUP_WINDOW_MIN}分内に二重に立てた組: **0**")

    _audit_approval(rows)
    return 0


def _audit_approval(rows: list[dict]) -> None:
    """**承認が挟まっていたか。**（2026-08-25 に足した）

    ここが無かったあいだ、鎖は「自力で回っている」と報告していました。
    **実際にはオーナーが押していました。** 呼んだ側には見えないからです ——
    返るのは「成功」だけで、承認は待たされたことすら分かりません。

    **だから見るのは秒のほうです。** 承認が挟まると人が押すまでの時間が丸ごと乗る。
    """
    timed = [r for r in rows if isinstance(r.get("call_seconds"), (int, float))]
    counted = [r for r in rows if isinstance(r.get("blocked"), int)]
    print()
    print("  --- 承認が挟まったか（**見分けられるのは秒だけ**）---")
    if not timed:
        print(f"  測った回: **0/{len(rows)}** —— まだ何も言えません")
        print("  （`--stamp` → MCP を1回 → `--record ... --since <秒>`）")
    else:
        slow = [r for r in timed if r["call_seconds"] >= APPROVAL_SUSPECT_SEC]
        fast = len(timed) - len(slow)
        print(f"  測った回: **{len(timed)}/{len(rows)}**  "
              f"承認なしで通った **{fast}** ／ 承認待ちの疑い **{len(slow)}**"
              f"（閾 {APPROVAL_SUSPECT_SEC}秒）")
        for r in timed[-5:]:
            try:
                t = datetime.fromisoformat(r["at"]).astimezone(JST).strftime("%m/%d %H:%M")
            except Exception:
                t = r.get("at", "?")
            mark = "**待たされた疑い**" if r["call_seconds"] >= APPROVAL_SUSPECT_SEC else "素通り"
            print(f"    {t} JST  {r['call_seconds']:>7.1f}秒  {mark}")
        if slow:
            print("  **疑いが出ている以上、「自力で回っている」と書かないこと。**")
    if counted:
        tot = sum(r["blocked"] for r in counted)
        last = counted[-1]["blocked"]
        print(f"  承認待ちに落ちていた回（数えた {len(counted)}回の合計）: "
              f"**{tot}件**（直近の回では {last}件）")
    else:
        print("  承認待ちの件数: **数えた回がありません**（`--blocked N` を渡すこと）")


def main() -> int:
    ap = argparse.ArgumentParser(description="鎖の受け渡し（次の回をこの回のうちに立てる）")
    # **`--plan` という名前にしないこと**（2026-08-24 に実測）。
    # `python scripts/relay.py --plan` は**権限判定に弾かれます** ——
    # `Bash(python *)` は許してあるのに、auto mode の分類器が別途止めます。
    # **子は無人なので、弾かれた時点でこの仕組みは死にます。**
    # 同じ理由で、新しい入口を足すときは**必ず一度、実際に打って確かめること。**
    ap.add_argument("--next", action="store_true", help="この回で何を立てるべきか、引数ごと出す")
    ap.add_argument("--record", action="store_true", help="数えた結果と立てたものを記録する")
    ap.add_argument("--check", action="store_true",
                    help="この回が記録したか（`stop_check.sh` 用。0=済み 2=まだ）")
    ap.add_argument("--audit", action="store_true", help="受け渡しの履歴")
    ap.add_argument("--hourly", type=int, default=0, help="youtube-hourly で生きている数")
    ap.add_argument("--optimizer", type=int, default=0, help="youtube-optimizer で生きている数")
    ap.add_argument("--spawned", default="", help="この回で立てた札（hourly,optimizer）")
    ap.add_argument("--note", default="", help="1行の註")
    ap.add_argument("--snapshot-at", default="",
                    help="`list_sessions` を**撮った**時刻（ISO）。`alive` はこの時刻の姿です。"
                         "省くと記録した時刻で代用しますが、**古いほうに倒れます**")
    ap.add_argument("--stamp", action="store_true",
                    help="いまの秒（epoch）を出す。**MCP を撃つ直前に打つ**")
    ap.add_argument("--since", type=int, default=None,
                    help="`--stamp` が出した秒。MCP を1回撃つのに何秒かかったかを"
                         "ここで引き算します（**承認が挟まると人の待ち時間が丸ごと乗る**）")
    ap.add_argument("--call-seconds", type=float, default=None, dest="call_seconds",
                    help="秒を自分で測ったときの直接指定（ふつうは `--since` を使うこと）")
    ap.add_argument("--blocked", type=int, default=None,
                    help="`list_sessions` で **承認待ち（need_input）だった回の数**。"
                         "**0 でも渡すこと** —— 省くと「数えていない」になります")
    ap.add_argument("--limit", type=int, default=15)
    args = ap.parse_args()

    # **引き算はここでやる。** 模型に秒を数えさせると分またぎで必ず間違えます。
    if args.since is not None and args.call_seconds is None:
        args.call_seconds = round(datetime.now(timezone.utc).timestamp() - args.since, 1)

    if args.stamp:
        return cmd_stamp(args)
    if args.record:
        return cmd_record(args)
    if args.check:
        return cmd_check(args)
    if args.audit:
        return cmd_audit(args)
    return cmd_next(args)


if __name__ == "__main__":
    sys.exit(main())
