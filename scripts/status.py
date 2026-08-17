#!/usr/bin/env python3
"""チャンネルのいまの状態を1画面に出す。

    python scripts/status.py [日数]

なぜ要るか。**判断の側の間違いも、被覆の問題だった。**

この日、2つ間違えかけた。ひとつは `statistics.viewCount` が 5634 なのを見て
ショートが伸びたと思ったこと。実際には動画ごとに数えると合計2回だった。
**チャンネル単位の数字と動画ごとの数字は別物**なので、片方をもう片方の代わりに読まないこと。

**このとき「5634 は前身の動画のものだ」と説明をつけた。それは推測で、誤りだった**
（2026-08-10 に uploads を全部引いて確認。35本すべてこの企画のもので、前身は0本）。
数字が合わない理由を、確かめずに名前で埋めた例です。**齟齬には名前をつけないこと。**

もうひとつは、予約公開のはずの動画が private のまま publishAt を持っていない、
という状態を見落としかけたこと。これは黙って永久に公開されない。

どちらも「毎回いくつも API を叩いて頭の中で組み立てる」からこそ起きる。
組み立てを機械にやらせて、危ない状態には印を付ける。

`scripts/inspect_build.py` が目視に対してやったことを、判断に対してやる。
面倒だから飛ばされる、という同じ原因を、同じやり方で潰している。
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import alerts as _alerts  # noqa: E402
from src import inbox as _inbox  # noqa: E402
from src.uploader import _service  # noqa: E402

JST = timezone(timedelta(hours=9))

# **外れたときの次の手を、期限の何日前から出すか。**
# 期限が来てから探すと、その回が丸ごと分析で終わります（2026-08-17）。
NEXT_MOVE_WINDOW = 14
# 何日先まで予約の空きを見るか。
# **3 では短すぎました**（2026-08-15 23:0x）。M14 の比較の窓は 8/16〜8/23 の8日で、
# 3日先までしか見ないと**窓の内側の穴が、3日前になるまで見えません。**
# 実際 8/18・8/19・8/20 のうち報告されたのは 8/18 だけでした。
# 1周30分で回っているので、7日先まで出しても「まだ埋めなくてよい日」が
# 並ぶだけで害はありません。**見えない穴のほうが高い。**
LOOKAHEAD_DAYS = 7
def _is_short(video: dict) -> bool:
    """ショートかどうか。**尺で見る。** 題の #Shorts は付け忘れがある。"""
    dur = video["contentDetails"]["duration"]
    m = re.fullmatch(r"PT(?:(\d+)M)?(?:(\d+)S)?", dur)
    if not m:
        return False
    return int(m.group(1) or 0) * 60 + int(m.group(2) or 0) <= 180


def _fmt(iso: str) -> str:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(JST).strftime("%m/%d %H:%M")


# === 8本の日（M11 の段）====================================================
#
# **これは警告ではないので `alerts.ring()` を通していません**（2026-08-16 に足した）。
# `alerts` が畳むのは「鳴り続けて当たりを含まない一覧」で、判定は
# `run_marker.py --closes` の宣言で入ります。ここが出すのは**毎回使う計器**——
# 「次にどの日へ何本入れれば段が1日ふえるか」——で、**閉じる対象がありません。**
# 畳まれると、次の回がまた予約一覧を目で数えることになります。
#
# なぜ足したか。前の回（8/16 21:0x）の設計の見直し（§6 (a2) 問い3）がこう残しました:
#
#   > `pick(8)` が8件返るのに、5件で1日を閉じて3件を余らせています。
#   > 次の1手: **`status.py` に「あと何本で8本の日が1日増えるか」を日ごとに出させる。**
#   > いまは毎回、予約一覧を目で数えていて、**3回続けて同じ数え方をしています。**
#
# 実際、8/16 の 19:0x・19:5x・21:0x の3回とも、**70本超の `[予約中]` を目で数えて**
# 「次に安い日」を決めていました。数え間違えれば `--hours` が既存の予約とぶつかります。
STEP_SIZE = 8            # M14「8本の日」の1日ぶん
STEP_TARGET_DAYS = 14    # M11 の覆る条件（8本/日 の段に14日乗る）
STEP_SLOT_HOURS = tuple(range(9, 20))   # 実績のある置き場所（JST 9時〜19時）


def print_step_days(short_hours: dict[str, set[int]], top: int = 4) -> None:
    """日ごとに「あと何本で8本になるか」と、**空いている時刻**を出す。

    `short_hours` は `YYYY-MM-DD`（JST）→ 予約済みショートが埋めている時（JST）。
    """
    if not short_hours:
        return
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from batch_build import M14_WINDOW
    except Exception:
        M14_WINDOW = ("", "")

    today = datetime.now(JST).strftime("%Y-%m-%d")
    future = {d: h for d, h in short_hours.items() if d >= today}
    full = sorted(d for d, h in future.items() if len(h) >= STEP_SIZE)

    print(f"\n=== 8本の日（M11 の段。**あと何本で1日ふえるか**）===")
    shown = " ".join(d[5:] for d in full) if full else "（まだありません）"
    print(f"  いま **{len(full)}日** / {STEP_TARGET_DAYS}日: {shown}")
    print(f"  **あと {max(0, STEP_TARGET_DAYS - len(full))}日**"
          f"（M11 の覆る条件。`docs/MEANS.md`）")

    partial = sorted((d for d, h in future.items() if 0 < len(h) < STEP_SIZE),
                     key=lambda d: (STEP_SIZE - len(future[d]), d))
    if not partial:
        print("  **足せる日がありません**（未来の予約が全部8本）。新しい日を立てること。")
        return

    print("  --- 安い順（**この表の `空き` をそのまま `--hours` に渡せます**）---")
    lo, hi = M14_WINDOW
    for d in partial[:top]:
        have = len(future[d])
        free = [h for h in STEP_SLOT_HOURS if h not in future[d]]
        need = STEP_SIZE - have
        # **窓の中の日は候補から外さず、印を付ける。** 外すと理由が見えなくなり、
        # 窓が終わったあとも「なぜかこの日だけ出ない」に見えます。
        warn = "  ← **M14 の比較の窓。置かないこと**" if lo <= d <= hi else ""
        print(f"    {d[5:]}  {have}本 → **あと{need}本**"
              f"  空き {','.join(str(h) for h in free[:need])}{warn}")

    best = partial[0]
    if not (lo <= best <= hi):
        need = STEP_SIZE - len(future[best])
        free = [h for h in STEP_SLOT_HOURS if h not in future[best]][:need]
        print(f"  そのまま打てます（在庫が {need}本 あるとき）:")
        print(f"    python scripts/batch_build.py --count {need} --date {best} "
              f"--hours {','.join(str(h) for h in free)} --jobs 3 --per-calc 1")


def print_hypotheses() -> None:
    """検証していない前提と、その期限を毎回出す。

    **推測は、期限を切らないと永久に推測のまま残る。** JOURNAL に書くだけでは
    読み飛ばされるので、状態を見るたびに目に入る場所に出す。
    期限を過ぎたものは目立たせる。そこで必ず判定させる。
    """
    import yaml

    path = Path(__file__).resolve().parent.parent / "config" / "hypotheses.yaml"
    if not path.exists():
        return
    items = yaml.safe_load(path.read_text(encoding="utf-8")).get("hypotheses", [])
    if not items:
        return

    today = datetime.now(JST).date()

    # **判定済みのものを「まだ検証していない」に混ぜない。**
    # `verdict` が書かれた時点でその問いは終わっている。混ぜると、
    # 期限切れの表示が毎回出続けて**本当に期限が来たものが埋もれる。**
    open_, judged = [], []
    for h in items:
        (judged if h.get("verdict") else open_).append(h)

    print("\n=== まだ検証していない前提 ===")
    if not open_:
        print("  （ありません）")
    no_next: list[tuple[int, str]] = []
    for h in open_:
        try:
            due = datetime.strptime(str(h["deadline"]), "%Y-%m-%d").date()
            left = (due - today).days
            mark = ("[!] 期限切れ" if left < 0
                    else "[!] 今日が期限" if left == 0 else f"あと{left}日")
        except (KeyError, ValueError):
            left, mark = 0, "[!] 期限が読めない"
        print(f"  {mark}  {h.get('claim', '(claim なし)')}")
        # **鍵が欠けても落とさない。** 2026-08-08、判定を書いたときに
        # `falsified_if` を消してしまい、status.py 全体が
        # KeyError で止まった。**状態を見る道具が、状態のせいで死んではいけない。**
        cond = h.get("falsified_if")
        print(f"        外れとみなす条件: {cond}" if cond
              else "        [!] 外れとみなす条件が書かれていません。**書くこと。**")

        # **次の手は、期限が来る前から見えていること**（2026-08-17 に直した）。
        #
        # ここは長らく `if left <= 0:` でした。つまり**期限が来るまで
        # `next_if_false` は一度も印字されません。** 15件が全部「あと N日」なので、
        # **実際には一度も出ていませんでした。**
        #
        # そのあいだ「**M11 が外れたときの次の手が台帳に無い**」という申し送りが
        # **4回**運ばれ、4回とも未着手のまま持ち越されています。
        # **書いてありました。**`hypotheses.yaml` の `next_if_false` に、
        # 「長尺が1,000再生に届かなければ M4 ごと外れ、M3 へ移る」まで含めて。
        # **道具が、期限が来るまで隠していただけです。**
        #
        # これは `bake_slides.py --resplit` と同じ形（`docs/trigger_main.md` §5）——
        # **無いものを作れという申し送りの、実物は既にある。**
        # ちがうのは、あちらが「手順の文言が実装に追いついていない」だったのに対し、
        # こちらは **実装のほうが、持っているものを見せていない**ことです。
        #
        # **準備が要るのは期限の前**なので、近いものは先に出します。
        # 全部出すと15件ぶんで埋まるので、`NEXT_MOVE_WINDOW` 日で切ります。
        nexts = h.get("next_if_false") or []
        if left <= 0:
            print("        → いま判定すること。外れていたら次を順に試す:")
            for nxt in nexts:
                print(f"           - {nxt}")
        elif left <= NEXT_MOVE_WINDOW:
            if nexts:
                print(f"        → **外れたときの次の手**（あと{left}日。"
                      "期限が来てから探さないこと）:")
                for nxt in nexts:
                    print(f"           - {nxt}")
            else:
                no_next.append((left, h.get("claim", "(claim なし)")))

    # **期限が近いのに、外れたときの次の手が書かれていない前提。**
    # 判定日に「で、どうする」を考え始めることになるので、その回が丸ごと分析で終わります。
    if no_next:
        r = _alerts.ring("no_next_move", len(no_next))
        if r.folded:
            print(f"\n  {r.line}")
        else:
            print(f"\n  --- [!] 次の手が書かれていない前提 {len(no_next)}件"
                  f"（期限まで{NEXT_MOVE_WINDOW}日以内）---")
            print("  **判定日に考え始めると、その回は分析だけで終わります。**"
                  "`next_if_false` を先に書くこと。")
            for left, claim in sorted(no_next):
                print(f"    あと{left}日  {claim}")

    # **判定済みも中身を出す（2026-08-10 に直した）。**
    # ここは長らく件数だけだった。その結果、**もう外れたと分かっている手を
    # 何度でも提案できる状態**になっていた。実際この日の回で、
    # 「ショートの登録率を上げる手段が台帳に無い」と考えて M11 を書きかけ、
    # `hypotheses.yaml` を直接開いて初めて、**同じものが2回試されて
    # 2回とも0人だった**ことに気づいている（3,576再生で登録0人）。
    #
    # `MEANS.md` と `status.py` だけを読む回は、この否定結果に一度も触れません。
    # **却下の理由は、未検証の前提と同じくらい毎回目に入る必要があります。**
    if judged:
        print(f"\n  --- 判定済み {len(judged)}件 ---")
        print("  **ここはもう試した手です。同じものを「未着手の手段」として出し直さないこと。**")
        for h in judged:
            verdict = " ".join(str(h.get("verdict", "")).split())
            if len(verdict) > 140:
                verdict = verdict[:140] + "…"
            print(f"    {h.get('claim', '(claim なし)')}")
            print(f"      → {verdict}")



# 使用量の正本。**2026-08-14 に読む先を丸ごと変えた。**
#
# 8/12 まで、ここは `-chatgpt-usage-monitorPrivate` の
# `state/claude-usage.json` を読んでいた。あれは唯一「残り何%」を返す口だった。
# **もう返さない。** 8/11 に OAuth が切れ（`reauthentication_required`）、
# 8/12 09:39 JST には向こうの GitHub Actions ごと止まった。
# **直すにはオーナーがブラウザで認証し直すしかない。**
# A1 は「私側への指示をしてもいいが、必ず読むとは限らない」と言っている。
# **人待ちの計器は計器ではない。**
#
# それでも `docs/trigger_main.md` §2 は毎回 `add_repo` → Actions → clone を
# 踏ませ続けた。**3つとも失敗する経路に、毎回3〜4分と数千トークンを捨てていた。**
#
# 代わりに読むのは **CCR の MCP の返りそのもの**。`list_sessions` の
# `external_metadata` に `rate_limit_info`（効いている枠・状態・リセット時刻）と
# `usage`（実トークン数）が入っている。**`add_repo` も Actions も要らず、遅れもない。**
#
# **%は返ってこない。** だから `scripts/quota.py` が状態の遷移を積んで、
# 目盛りを後から決める。読み方はあちらの docstring にある。
QUOTA_LOG = Path(__file__).resolve().parent.parent / "data" / "quota.jsonl"


def print_budget() -> None:
    """使用量を出す。**正本は `data/quota.jsonl`（CCR の MCP の返り）。**

    2026-08-08 に予算制限は無くなった。
    「どちらの使用量もチャットgptsparkの使用量も全てあなたが使っていい」。
    だから**残量は「使い切りそうか」を見るためだけ**に読む。絞る理由にはしない。

    **`scripts/usage.py` の換算はここに出さない。** あれが数えているのは
    **このコンテナのセッション記録だけ**で、枠はアカウント単位で効く。
    別セッションが動けば、自分のぶんが少なくても枠は減る。
    並べて出すと、どちらを信じるか迷う分だけ判断が鈍る。**正本だけ出す。**
    """
    print("\n=== 使用量（CCR の枠情報）===")
    ok = False
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import quota                                    # noqa: PLC0415
        quota.report()
        ok = QUOTA_LOG.exists()
    except Exception as exc:
        # **失敗を「実測」と同じ字面で出さないこと**（2026-08-12 に踏んだ）。
        # 数を出す口では、失敗を必ず別の字面にする。
        print(f"  **計器が動きませんでした（これは実測ではありません）: "
              f"{str(exc)[:70]}**")

    # **取り直し方を、読めた回にも出す。** 積むのは呼び出し側（MCP を持つ側）に
    # しかできない。ここに書いておかないと、誰も積まないまま古い点を読み続ける。
    print("\n  **取り直す・積み増す**（シェルからは資格情報に届かない。MCP が要る）:")
    print("    1. `list_sessions` を叩く（limit=25。**1回で25点ぶん返る**）")
    print("    2. 返りをそのまま保存して "
          "`python scripts/quota.py --ingest <file>`")
    print("    **毎回やること。** 点が増えるほど「いつ閉じるか」が絞れる。")

    # **A15 は、計器が読めない回ほど要る**（2026-08-12 に順序を直した）。
    # 以前は `return` の向こう側にあったので、**読めなかった回だけ消えていました。**
    # 数字が出ない回に「全部使ってよい」まで消えると、
    # 子は空欄を見て勝手に絞ります（8/12 09:45 の日誌が同じことを書いている）。
    print("\n  **全部使ってよい。** 残すこと自体に価値は無い。")
    print("  絞る理由にしないこと。使い切りそうなときだけ、短く切る。")
    if not ok:
        print("  **計器が読めないことは、絞る理由になりません。**"
              "見えないだけで、枠が減ったわけではない。")


def reversal_conditions(body: str, width: int = 110, limit: int = 1) -> list[str]:
    """却下・待ちの項から「覆る条件」を抜く（2026-08-16 に足した）。

    **取り消し線（`~~...~~`）の中は落とします。** M11 の条件1 は
    「1本あたりの再生が1桁上がる」で、8/15 に取り消し線つきで閉じられ、
    その下に「**その閉じ方が間違っていました（取り消し）**」が続いています。
    取り消された本文をそのまま出すと、**もう死んだ条件のほうが先に目に入ります。**

    見出しの行に条件が書いていない項（M11 の「2つ。どちらでもよい」）は、
    **続く番号つきの行**を条件として拾います。
    """
    import re

    out: list[str] = []
    lines = body.splitlines()
    for i, line in enumerate(lines):
        if not re.match(r"^- \*\*(これが)?覆る条件", line):
            continue
        chunk = [line]
        for nxt in lines[i + 1:]:
            if re.match(r"^- \*\*", nxt) or nxt.startswith("#"):
                break
            chunk.append(nxt)
        text = "\n".join(chunk)
        # 取り消し線の中身は落とす（**死んだ条件を先に見せない**）
        text = re.sub(r"~~.*?~~", "", text, flags=re.S)
        text = re.sub(r"\*\*|`", "", text)
        # 見出しの行の後ろに本文があればそれ、無ければ続きの行から
        head, _, rest = text.partition("\n")
        head = re.sub(r"^- (これが)?覆る条件", "", head).strip()
        # 見出しの「（いつ書き直したか）」は註であって条件ではないので落とす。
        # **落としたあとに本文が続くことがあります**（同じ行に書かれた回）。
        # 2026-08-16 の最初の実装は註を見つけた時点で行ごと捨てており、
        # **同じ行に条件を書いた項が黙りました**（検査で落ちて気づいた）。
        head = re.sub(r"^（[^）]*）", "", head).lstrip(":： ").strip()
        pieces = [head] if head else []
        for raw in rest.splitlines():
            s = raw.strip(" →")
            if not s or s.startswith("→"):
                continue
            pieces.append(s)
        joined = " ".join(pieces)
        joined = re.sub(r"\s+", " ", joined).strip()
        if joined:
            out.append(joined[:width])
    # **後ろのものを採ります。** この台帳は追記式で、訂正は必ず下に足されます
    # （M11 の条件1 は 8/15 に閉じられ、同日 16:0x にその閉じ方ごと取り消された）。
    # **上から採ると、取り消された側が先に出ます。**
    return out[-limit:]


def print_means() -> None:
    """**手段の台帳（docs/MEANS.md）の未着手を毎回出す。**

    2026-08-09、オーナーに「あらゆる手段を使ってが効いていない」と指摘された。
    確かめると `config/hypotheses.yaml` の9件が**全部「ショートの改善」**で、
    **乗り物そのものを問うものが1つも無かった。**

    つまりループが「いまの機械を磨く」ことしかできない形になっていた。
    A13 は文書にあっても、**実行に移す仕組みが無ければ効かない。**
    だからここで毎回、未着手の手段を目に入れる。
    """
    path = Path(__file__).resolve().parent.parent / "docs" / "MEANS.md"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    # 「### M1. 名前」と、その節の「- **状態**: ...」を拾う
    import re

    entries = re.findall(r"^### (M\d+)\. (.+?)$\n(.*?)(?=^### |\Z)",
                         text, re.M | re.S)
    untried = []
    held = []
    rejected = []
    for code, name, body in entries:
        m = re.search(r"\*\*状態\*\*: (.+)", body)
        state = m.group(1).strip() if m else "?"
        if "未着手" in state or "未検討" in state:
            untried.append((code, name, state))
        elif "保留" in state:
            # **保留は「消えた手」ではありません。**
            # 着手条件を数字で書いてあるのに、その条件を毎回出していなかったので
            # M3 が3日間だれの目にも入らなかった（2026-08-10）。
            held.append((code, name, state))
        elif "却下" in state or "待ち" in state:
            # **却下も「消えた手」ではありません**（2026-08-16 に足した）。
            #
            # 却下した項には全部「これが覆る条件」が書いてあります。
            # ところがこの節は 未着手 と 保留 しか出しておらず、
            # **却下した4件（M5・M7・M10・M11）は毎回どこにも出ていませんでした。**
            #
            # 実害が出ています。**M11 は「ショートの登録率そのものを上げる」**で、
            # 登録率 0.038% は 1,000人の門に **259万再生**を要求している律速そのもの。
            # M11 の本文はその乗数を「**単独で M1 を不可能から1年台に動かしうる
            # 唯一の乗数**」と書き、覆る条件も「**M14 の8の段に乗ること**」まで
            # 特定されています。**それが目に入らないので、**
            # 8/16 11:4x と 12:2x の回は申し送りにこう書きました ——
            #
            #     「`docs/MEANS.md` に、登録率を直接動かす手段を足すこと。
            #       未着手0件・保留2件で、**台帳が律速を1つも持っていません**」
            #
            # **台帳は持っていました。この節が見せていなかっただけです。**
            # 2回とも、次の回が M11 を書き直すところだった（M11 自身が
            # 「この却下は毎回もう一度提案されかけます」と警告しているとおり）。
            #
            # **覆る条件のほうを出します。** 状態の一行ではなく、
            # 「何が起きたら復活するか」が判断に要る側だからです。
            rejected.append((code, name, state, body))
    # 棚卸しからの経過。**視界の外は、定期的に数え直さないと戻る。**
    import json as _json
    st = Path(__file__).resolve().parent.parent / "data" / "audit.json"
    if st.exists():
        try:
            d = _json.loads(st.read_text(encoding="utf-8"))
            last = datetime.fromisoformat(d["last_run"])
            days = (datetime.now(JST) - last).days
            mark = "  **[!] 7日以上たっています。走らせること**" if days >= 7 else ""
            print(f"\n=== 棚卸し（scripts/audit.py）===")
            print(f"  前回 {last:%m/%d %H:%M}（{days}日前）"
                  f" / 見つかった見落とし {d.get('last_gap_count', '?')}件{mark}")
        except Exception:
            pass
    else:
        print("\n=== 棚卸し（scripts/audit.py）===")
        print("  **一度も走らせていません。** `python scripts/audit.py`")

    print(f"\n=== 手段の台帳（docs/MEANS.md）===")
    print(f"  未着手 {len(untried)}件 / 全{len(entries)}件")
    for code, name, state in untried:
        mark = " ←★" if "見落とし" in state else ""
        print(f"    {code} {name}{mark}")
    if held:
        print(f"  --- 保留 {len(held)}件（**着手条件を毎回見ること。条件は数字で書いてあります**）---")
        for code, name, state in held:
            cond = state.split("着手条件")[-1].lstrip("はがのを:： ") if "着手条件" in state else state
            print(f"    {code} {name}")
            print(f"        条件: {cond[:90]}")
    if rejected:
        print(f"  --- 却下・待ち {len(rejected)}件"
              f"（**覆る条件を毎回見ること。ここに律速そのものが入っています**）---")
        for code, name, state, body in rejected:
            print(f"    {code} {name}")
            for line in reversal_conditions(body):
                print(f"        覆る条件: {line}")
    if untried:
        print("  **目標の数字が2週間動いていないなら、いまの機械の改善ではなく")
        print("  ここから1つ選ぶこと。** それが A13 を実行に移す唯一の経路です。")
    else:
        # **0件のときに何も言わないのは、いちばん危ないふるまい。**
        #
        # 2026-08-10 に M8 へ着手して未着手が0件になったら、
        # この節が**丸ごと黙った。** 「全部やった」に見えるが、
        # 実際は**候補の出し方が尽きただけ**かもしれない。
        # そしてこの日、実際にそうだった: 7件を掛け終えて0件になった直後に
        # 疑ったら、**詰まり（WATCH=2）を直接狙う手段が1つも無かった。**
        # そこで足したのが M8。**0件は「探し終えた」の合図ではなく、
        # 「探し方が尽きた」の合図として扱うこと。**
        print("  **未着手が0件です。これは達成ではありません。**")
        print("  候補リストが短いことを疑うこと。"
              "**いま止まっている数字を1つ選び、")
        print("  それを直接動かす手段が台帳にあるかを見る。"
              "無ければ足す**（M8 はそうやって出た）。")
        print("  無いまま「全部やった」にすると、"
              "`hypotheses.yaml` が9件ぜんぶショート改善だったのと同じ壊れ方をします。")


def print_topic_stock() -> None:
    """**この回に `upload` が選べるか**を、掛け算した1つの数で出す（2026-08-16 に足した）。

    ## なぜ要るか（**尽きてから気づいていた**）

    前の回の (a2) 問い3 がこう書き残しています ——

    > 在庫が0になったのは**この回に分かった**ことで、`status.py` は
    > 「手段の台帳 未着手0件」としか言っていませんでした。
    > **在庫の底は、尽きてから気づくとその回の `upload` が選べなくなります。**

    実際そのとおりで、`status.py` の出力は**73行ぶんの動画一覧と、予約の一覧と、
    重なり66組と、前提と、門の掛け算**を出しますが、
    **「次に何本作れるか」だけがどこにも出ていませんでした。**
    `python scripts/topic_forge.py --list` も `pick` も、手で叩かないと出ません。

    ## 出すのは在庫そのものではなく、**律速のほう**

    在庫は2段になっていて、**細いほうでしか作れません。**

        (1) 未投稿テーマ  … `config/topics.yaml` にあって、まだ上げていない本
        (2) 未使用の節    … `src/calc/` の `=== 見出し ===` のうち、
                             どのテーマも指していないもの ＝ (1) を**増やせる余地**

    そして **`pick` が返す本数は (1) より小さい**（同じ節・同じ calc を並べない規則が
    上から掛かる）。**judgement に要るのはその最終値**なので、`pick` を実際に呼びます。
    8/16 03:4x の実測で **未投稿7件 → `pick` は6件**でした（1件が規則で落ちる）。

    (2) が 0 のときは `topic_forge` を回しても1件も増えません
    （**あれは節を掘る道具で、節を作りません**）。だから
    **`src/calc/` に表を足す以外に道が無い**ことを、ここで名指しします。

    ## しきい値は掛け算してから置く

    1周あたり `upload` は最低1本、出せる回は複数。**1日の周回数は 24h ÷ 41分 ≒ 35** ですが、
    実際に生成に入る回は半分もありません。**`pick` が 8 を割ったら
    `batch_build --count 8`（M14 の8の段）が測れなくなる**ので、そこを警告線にします。
    """
    root = Path(__file__).resolve().parent.parent
    print("\n=== テーマ在庫（次に何本作れるか）===")
    try:
        sys.path.insert(0, str(root / "scripts"))
        import topic_forge  # noqa: E402
        import batch_build  # noqa: E402

        _all, free, _known = topic_forge.survey()
        n_sections = sum(len(v) for v in _all.values())
        n_free = sum(len(v) for v in free.values())
        got = batch_build.pick(8, [])
        n_pick = len(got)
    except (Exception, SystemExit) as exc:
        # **`SystemExit` を明示して捕まえること**（2026-08-16、この検査が見つけた）。
        # `topic_forge.sections()` は calc が落ちたとき `raise SystemExit(...)` します。
        # `SystemExit` は `BaseException` 側なので **`except Exception` を素通りします** ——
        # つまり **`src/calc/` を1本壊すと `status.py` が丸ごと止まる**形でした。
        # そのとき登録者も予約も重なりも見えなくなるので、明らかに割に合いません。
        print(f"  読めませんでした（続行）: {str(exc)[:160]}")
        return

    # **律速は `pick` の返り**。ここが 0 なら、この回は upload を選べません。
    mark = ""
    if n_pick == 0:
        mark = "  ← **[!] この回は `upload` を選べません**"
    elif n_pick < 8:
        mark = "  ← **[!] 8本の日（M14 の段）が作れません**"
    print(f"  `pick(8)` が返す本数: **{n_pick}本**{mark}")
    print(f"  未使用の節: {n_free}件 / 全{n_sections}件"
          f"（`src/calc/` {len(_all)}本）")

    if n_free == 0:
        print("  **未使用の節が0件 ＝ テーマを増やす余地がありません。**")
        print("  `topic_forge` は節を掘る道具で、**節そのものは作りません。**")
        print("  増やす道は1つだけ: **`src/calc/` に新しい表を足す**"
              "（`src/calc/_template.py` から。実測3.1分/本）。")
    elif n_free < 5:
        print(f"  **未使用の節が残り{n_free}件です。** 次の `topic_forge` で尽きます。")
        print("  **尽きてから気づくと、その回の `upload` が空振りします。**"
              "先に `src/calc/` へ表を足すこと。")
    else:
        per = {m: len(v) for m, v in free.items() if v}
        print("  余地のある calc: "
              + " ".join(f"{m}:{n}" for m, n in sorted(per.items(), key=lambda x: -x[1])))

    if n_pick < 8 and n_free > 0:
        print(f"  → いま打つ手: `python scripts/topic_forge.py`"
              f"（未使用の節 {n_free}件からテーマを起こす）")

    # **どの族を作るかを、実績で並べる**（2026-08-16 に足した）。
    # ここが無かったあいだ、`pick` は手書きの `score` だけで選んでいました ——
    # **公開した実績が、次に何を作るかに一度も戻っていなかった。**
    print("\n=== 族べつの実績（`pick` の順番はこれで決まる）===")
    try:
        from src import family_perf

        unused = {m: len(v) for m, v in free.items()}
        for line in family_perf.report_lines(unused=unused):
            print(line)
        print("  **交絡は残ります**（公開時刻・尺・配信の広さ）。これは因果ではなく"
              "**事前分布**で、外れたら `hypotheses.yaml`（2026-08-30）で戻します。")
    except Exception as exc:
        print(f"  読めませんでした（続行）: {str(exc)[:160]}")


def print_retention(top: int = 4) -> None:
    """**維持率を毎回出す。** 2026-08-09 まで一度も見ていなかった。

    `averageViewPercentage` は `fetch_report` が**ずっと取っていたのに、
    どこにも表示していなかった。** そのため「平均視聴率51〜102%で最後まで
    見られている＝動画の問題ではない」という **8/7 時点の数字にもとづく判断を、
    何日も持ち越していた。** 実際にはいまの主力は約30%まで落ちている。

    **取っているのに見ていない数字は、無いのと同じどころか害になる。**
    古い結論が更新されないまま生き残るため。だから毎回出す。
    """
    print("\n=== 視聴の維持（相対 0.5 が同種の動画の中央値）===")
    try:
        from src.analytics import fetch_report, fetch_retention

        rows = [r for r in fetch_report(28) if r.get("views", 0) >= 100][:top]
        if not rows:
            print("  100再生を超えた動画がまだありません")
            return
        for r in rows:
            curve = fetch_retention(r["video"])
            title = r["title"][:22]
            avg = r.get("averageViewPercentage", 0)
            if not curve:
                print(f"  {title:<22} {r['views']:>5}再生  平均{avg:5.1f}%"
                      f"  共有{r.get('shares',0)} コメント{r.get('comments',0)}")
                continue
            # 冒頭・4分の1・半分の3点で十分。全部出すと読まない。
            def at(pos: float) -> tuple[float, float]:
                i = min(range(len(curve)), key=lambda k: abs(curve[k][0] - pos))
                return curve[i][1], curve[i][2]
            (w1, r1), (w25, r25), (w50, r50) = at(0.05), at(0.25), at(0.50)
            ev = r.get("engagedViews", 0)
            rate = ev / r["views"] * 100 if r.get("views") else 0
            print(f"  {title:<22} {r['views']:>5}再生  "
                  f"**engaged {rate:4.1f}%**  平均{avg:5.1f}%"
                  f"  共有{r.get('shares',0)} 高評価{r.get('likes',0)}"
                  f" コメント{r.get('comments',0)}")
            print(f"      5%地点 維持{w1:.2f} 相対{r1:.2f}"
                  f" │ 25%地点 維持{w25:.2f} 相対{r25:.2f}"
                  f" │ 50%地点 維持{w50:.2f} 相対{r50:.2f}")
    except Exception as exc:
        print(f"  読めませんでした: {str(exc)[:120]}")
    print("  **維持率と再生数は逆相関することがある**（配信が広がるほど"
          "狙いから外れた視聴者に当たる）。")
    print("  実測 8/9: 537再生で相対0.50、1506再生で相対0.25。"
          "**因果を決めつけないこと。**")
    print("  **engaged はすぐスワイプされなかった再生の割合。**")
    print("  平均視聴率は配信が広がると下がる（交絡）が、**engaged は再生数と同じ向きに動く。**")
    print("  実測 8/9: 43.9%→1263再生、11.8%→313再生。**ここが配信の駆動輪。**")
    print("  共有とコメントも配信に効くが、4,383再生に対し共有1・コメント0。")
    print("  **動画が視聴者に何も問いかけていない。**")


def print_channel_signals(days: int = 28) -> None:
    """**チャンネル日次でしか取れない指標。**

    `videosAddedToPlaylists`（保存）・`dislikes`・`redViews` は
    **`dimensions=video` では 400 になる**（2026-08-09 に確認）。
    動画べつには比べられないが、**チャンネル全体で0かどうかは分かる。**
    棚卸しが12件ぶん「使っていない」と言い続けていたのはこれらのこと。

    保存を見る理由: 8/22 の仮説（問いかけでコメントを取りにいく）を立てたとき、
    **「コメントより保存のほうが取りやすいのでは」を確かめていなかった。**
    """
    from datetime import date, timedelta

    from googleapiclient.discovery import build

    from src.auth import credentials

    print(f"\n=== チャンネル日次の信号（直近{days}日・動画べつには取れない）===")
    try:
        api = build("youtubeAnalytics", "v2", credentials=credentials(), cache_discovery=False)
        end, start = date.today(), date.today() - timedelta(days=days)
        r = api.reports().query(
            ids="channel==MINE", startDate=start.isoformat(), endDate=end.isoformat(),
            metrics="views,videosAddedToPlaylists,shares,comments,likes,dislikes,redViews",
            dimensions="day", maxResults=90,
        ).execute()
    except Exception as exc:
        print(f"  読めませんでした: {str(exc)[:120]}")
        return

    head = [h["name"] for h in r.get("columnHeaders", [])]
    rows = [dict(zip(head, x)) for x in r.get("rows", [])]
    if not rows:
        print("  データがありません")
        return
    tot = {k: sum(row[k] for row in rows) for k in head if k != "day"}
    v = tot["views"] or 1
    print(f"  再生 {tot['views']}  保存 {tot['videosAddedToPlaylists']}"
          f"  共有 {tot['shares']}  コメント {tot['comments']}"
          f"  高評価 {tot['likes']}  低評価 {tot['dislikes']}")
    print(f"  Premium 再生 {tot['redViews']}（全体の {tot['redViews'] / v:.0%}）")
    print("  **保存も共有もコメントも、ほぼ0。** 取りやすい信号がある、という話ではない。")
    print("  問いかけでコメントを取りにいく実験（8/22）は、**低いところから始まる。**")

    # **鮮度。** ここが古いと「24時間で何再生」の判定に使えない。
    last = rows[-1]["day"]
    lag = (date.today() - date.fromisoformat(last)).days
    print(f"  日次データの最終日 {last}（{lag}日前）")
    if lag >= 2:
        print("  **この表は当日ぶんを含みません。** 「24時間で〇再生」の反証条件は"
              "ここでは判定できないので、`data/views.jsonl` か動画べつの数字を使うこと。")


WATCH_LOG = Path(__file__).resolve().parent.parent / "data" / "watch.jsonl"


def _record_watch(days: int, watch: int, total: int, search: int) -> None:
    """**WATCH の推移を積む。** 1点では「動いたか」が言えないから。

    2026-08-10 に足した。理由は `docs/MEANS.md` の M3 と M12 で、
    **どちらも着手条件が「WATCH が2桁になったら」**なのに、
    その数字を時系列で持っていなかった。
    **条件を書いても、発火を見る手が無ければ発火しません。**
    """
    import json

    row = {"at": datetime.now(JST).isoformat(timespec="seconds"), "days": days,
           "watch": watch, "total": total, "yt_search": search}
    try:
        WATCH_LOG.parent.mkdir(parents=True, exist_ok=True)
        with WATCH_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _print_watch_trend(days: int) -> None:
    """同じ窓（days）の過去の読みと比べて、WATCH が動いたかを出す。"""
    import json

    try:
        lines = [json.loads(x) for x in WATCH_LOG.read_text(encoding="utf-8").splitlines() if x.strip()]
    except Exception:
        return
    same = [r for r in lines if r.get("days") == days]
    if len(same) < 2:
        print("  推移: **まだ出せません**（同じ窓の読みが1件。2件たまると出ます）")
        return
    first, last = same[0], same[-1]
    d = last["watch"] - first["watch"]
    print(f"  推移: {first['at'][:16]} の {first['watch']} → いま {last['watch']}"
          f"（**{d:+d}** / 読み {len(same)}件）")
    if last["watch"] < 10:
        print("  **WATCH が2桁になるまで M3（AdSense以外の収益）も M12（推薦面）も着手できません。**")
        print("  ここを動かせるのは M4（検索→長尺）と M8（フィードから出口）だけです。")


def print_where_watched(days: int = 28) -> None:
    """**どこで・何秒見られているか。**

    2026-08-09 にオーナーから「毎回取得できる情報の全て踏まえて分析してる?」と
    聞かれて確かめたら、**していなかった。** 棚卸しが「使っていない次元が8個」と
    出し続けていたのに、一度も中身を見ていなかった。引いたら設計に関わる事実が出た。

    **目に入らないものは無くなる。** だから毎回出す。
    """
    from datetime import date, timedelta

    from googleapiclient.discovery import build

    from src.auth import credentials

    print(f"\n=== どこで・何秒見られているか（直近{days}日）===")
    try:
        api = build("youtubeAnalytics", "v2", credentials=credentials(), cache_discovery=False)
        end, start = date.today(), date.today() - timedelta(days=days)

        def pull(dim):
            r = api.reports().query(
                ids="channel==MINE", startDate=start.isoformat(), endDate=end.isoformat(),
                metrics="views,estimatedMinutesWatched", dimensions=dim,
                sort="-views", maxResults=10,
            ).execute()
            return r.get("rows", [])
    except Exception as exc:
        print(f"  読めませんでした: {str(exc)[:120]}")
        return

    try:
        loc = pull("insightPlaybackLocationType")
        total_v = sum(x[1] for x in loc) or 1
        shorts = next((x[1] for x in loc if x[0] == "SHORTS_FEED"), 0)
        watch = next((x[1] for x in loc if x[0] == "WATCH"), 0)
        print(f"  再生場所: SHORTS_FEED {shorts}（{shorts / total_v:.1%}） / WATCH {watch}")
        _search = 0
        try:
            _search = next((x[1] for x in pull("insightTrafficSourceType")
                            if x[0] == "YT_SEARCH"), 0)
        except Exception:
            pass
        _record_watch(days, watch, total_v, _search)
        _print_watch_trend(days)
        if watch < total_v * 0.05:
            print("  **視聴ページにはほぼ誰も来ていない。**")
            print("  説明欄・目次・裏取りの手順・再生リストは**ほぼ読まれていない。**")
            print("  長尺（M4）はこの WATCH をゼロから作る賭けだと理解すること。")

        # **1再生あたりの秒数は、API が直接返すものを使う。**
        # 2026-08-09、`estimatedMinutesWatched ÷ views` で 8.5秒と出して
        # 「大半が1〜2枚で離れている」と報告した。**誤り。**
        # 同じ期間で API の `averageViewDuration` は **22秒**。
        # 627分 × 60 ÷ 4432 = 8.5 だが、views × 22秒 = 1,625分 で**合わない**
        # （`estimatedMinutesWatched` は総視聴時間そのものではない）。
        # **直接その問いに答える指標があるのに、割り算で別の数字を作っていた。**
        dev = pull("deviceType")
        print("  端末べつ:")
        for name, v, m in dev:
            print(f"    {name:9} {v:>5}再生")

        r = api.reports().query(
            ids="channel==MINE", startDate=start.isoformat(), endDate=end.isoformat(),
            metrics="views,averageViewDuration,averageViewPercentage",
        ).execute()
        head = [h["name"] for h in r.get("columnHeaders", [])]
        d = dict(zip(head, r.get("rows", [[0, 0, 0]])[0]))
        print(f"  **1再生あたり {d['averageViewDuration']}秒"
              f"（尺の {d['averageViewPercentage']:.0f}%）**  ← API の averageViewDuration")
        print("  **`estimatedMinutesWatched ÷ 再生数` で出さないこと。**"
              "2.6倍ずれる（8/9 に間違えた）。")
    except Exception as exc:
        print(f"  途中で読めませんでした: {str(exc)[:120]}")


def _channel_main(days: int = 7) -> int:
    """**外の口（YouTube Data API / Analytics）に依存する側。**

    ここは 2026-08-16 まで `main` そのものでした。**分けたのは、この関数の
    1行目が落ちると出力が丸ごと消えるから**です（下の `main` の註）。
    """
    youtube = _service()
    channel = youtube.channels().list(part="snippet,contentDetails,statistics", mine=True).execute()["items"][0]
    stats = channel["statistics"]

    print(f"=== {channel['snippet']['title']} ===")
    print(f"登録者 {stats.get('subscriberCount', '?')}人")
    print(
        f"チャンネル総再生 {stats.get('viewCount', '?')}回"
        "  ← **全部こちらの成果です。**「前身の動画も含む」は誤り（2026-08-10 に実測で否定）。\n"
        "     アップロード35本＝すべてこの企画のもので、前身の動画は1本も存在しません。\n"
        "     公開14本と `videoCount` が一致します。動画ごとの合計より小さいのは無効再生の除外で、\n"
        "     **他人のぶんが混ざっているからではありません**\n"
    )

    uploads = channel["contentDetails"]["relatedPlaylists"]["uploads"]
    # **1ページ50本で切っていました。** チャンネルは既に76本あるので、
    # この表も、下の「予約が入っていない日」も、**古いほうから黙って欠けます。**
    # さらに uploads プレイリストは**予約中（private）の動画を落とす**ので、
    # 欠けるのは「これから公開されるぶん」のほうでした（`src/history.py` の実測）。
    #
    # 2026-08-15 23:0x、この2つが重なって **「08/18 はショートの予約が無い」と
    # 誤報**しました。8/18 には `SbZjiakY--g` が入っており、それを信じて3本作った
    # 結果、8/18 が3本になっています。**空きの誤報は、投稿の欠けと同じくらい高い**
    # （同じ計算の重複を自分で作る）。**取り口は `history` と1つにします。**
    from src.history import channel_video_ids

    ids = channel_video_ids(youtube, uploads)

    # **手元の控えに載っているのに、口から返らなかった本を足す**（2026-08-16）。
    # `channel_video_ids` は2つの口の和ですが、**両方が同時に欠けることがあります** ——
    # uploads プレイリストは予約中を落とし、`search` は API の1日枠を使い切ると
    # 429 で落ちます（この回がそう。8/22 に予約済みの `iTrogWVf4Eg` が消え、
    # **この表からも「予約が入っていない日」からも落ちていました**）。
    #
    # **空きの誤報は、投稿の欠けと同じくらい高い**（8/15 23:0x に同じ形で
    # 3本を余計に作っています）。控えは自分が上げたときに書いた行なので、
    # 外の口の都合では欠けません（`src/dupes.ledger_rows`）。
    try:
        from src import dupes as _dupes
        _missing = [r["id"] for r in _dupes.ledger_rows() if r["id"] not in set(ids)]
        if _missing:
            print(f"[控え] 口から返らなかった {len(_missing)}本を足しました"
                  f"（{' '.join(_missing[:6])}{' …' if len(_missing) > 6 else ''}）")
            ids += _missing
    except Exception as exc:
        print(f"[控え] 読めませんでした（続行）: {str(exc)[:80]}")

    # **この判定は、控えを足した「後」でなければ意味がありません**（2026-08-17 に踏んだ）。
    #
    # ここは長らく `channel_video_ids` の直後にあり、`if not ids: print("動画が
    # ありません"); return 0` でした。**控えを足す上のブロックは、その1行下**です ——
    # つまり **`ids` が空のとき、控えは構造上いちど も走れませんでした。**
    # 控えを足した理由が「両方の口が同時に欠けることがある」なのに、
    # **本当に両方欠けた回だけ、その控えに手が届かない**という向きです。
    #
    # そして落ちるのは表だけではありません。`print_local_sections()` は
    # この関数の**下のほう**で呼ばれるので、`return 0` は
    # **手段の台帳・期限の来た前提・テーマ在庫・警告の当たり率・消費の速さを
    # 丸ごと道連れにします**（手順 §3「`status.py` が出すものに全部目を通すこと」の
    # 達成率が 0 になる）。2026-08-16 11:5x の回が `main` 側の `try` で塞いだのは
    # **例外で落ちる道だけ**で、**「空で正常に返る道」は塞がっていませんでした** ——
    # 同じ節の中で片方だけ、の9回目です。
    #
    # 実測（2026-08-17 06:4x）: `playlistItems` が 403、`search` が 429 で
    # `ids` が空になり、**`status.py` の出力が10行で終わりました。**
    # 控えには 182本 入っています。
    #
    # 例外にするのは、`main` 側が既に「外の口が落ちた」経路を持っているからです
    # （手元の節を全部出して 0 を返す）。**新しい道を増やさないこと。**
    if not ids:
        raise RuntimeError(
            "動画IDが1件も取れませんでした（playlistItems も search も控えも空）。"
        )

    videos = []
    for i in range(0, len(ids), 50):
        videos += youtube.videos().list(
            part="snippet,status,statistics,contentDetails", id=",".join(ids[i:i + 50])
        ).execute()["items"]

    now = datetime.now(timezone.utc)
    ours = 0
    stranded: list[str] = []
    scheduled: list[str] = []
    short_days: set[str] = set()      # ショートが予約されている日（MM/DD）
    # 日ごとの「予約済みショートが埋めている時刻（JST の時）」。
    # 鍵は `YYYY-MM-DD`（`batch_build.py --date` にそのまま渡せる形）。
    short_hours: dict[str, set[int]] = {}
    # **公開済みショートの再生（Data API・遅れなし）。** 門の先の掛け算に使う。
    short_views: list[int] = []

    print(f"{'ID':13s} {'状態':16s} {'尺':>7s} {'再生':>5s} {'高評価':>4s}  題")
    for v in videos:
        st, sn = v["status"], v["snippet"]
        vs = v["statistics"]
        views = int(vs.get("viewCount", 0))
        ours += views

        publish_at = st.get("publishAt")
        if st["privacyStatus"] == "public":
            state = f"公開 {_fmt(sn['publishedAt'])}"
            if _is_short(v):
                short_views.append(views)
        elif publish_at:
            hours = (datetime.fromisoformat(publish_at.replace("Z", "+00:00")) - now).total_seconds() / 3600
            state = f"予約 {_fmt(publish_at)}"
            scheduled.append(f"{v['id']} {_fmt(publish_at)}（あと{hours:.1f}時間）")
            if _is_short(v):
                short_days.add(_fmt(publish_at).split()[0])
                _jst = datetime.fromisoformat(publish_at.replace("Z", "+00:00")).astimezone(JST)
                short_hours.setdefault(_jst.strftime("%Y-%m-%d"), set()).add(_jst.hour)
        else:
            state = f"{st['privacyStatus']} 予約なし"
            stranded.append(f"{v['id']} {sn['title'][:34]}")

        dur = v["contentDetails"]["duration"].replace("PT", "").lower()
        print(f"{v['id']:13s} {state:16s} {dur:>7s} {views:5d} {vs.get('likeCount', 0):>4s}  {sn['title'][:34]}")

    print(f"\nこちらの動画の再生 合計 {ours}回（{len(videos)}本）")

    # **公開後の伸び方を毎回残す。** 総再生数だけ見ていると、当たり外れが
    # 決まる最初の数時間が抜ける（2026-08-06）。人が思い出す前提にしない。
    try:
        from snapshot import print_curves, record
        record(videos)
        print_curves([v["id"] for v in videos],
                     {v["id"]: v["snippet"]["title"] for v in videos})
    except Exception as exc:
        print(f"  伸び方を記録できませんでした: {str(exc)[:70]}")

    if scheduled:
        print("\n[予約中]")
        for s in scheduled:
            print("  " + s)

    print_step_days(short_hours)

    # 予約が埋まっていない日を出す。**背後の生成はコンテナ再起動で消える**ので、
    # 「走らせたはず」は当てにならない。実際に 8/7 が空になっていたのを見落としかけた。
    # 投稿が途切れるのが最大の損失なので、空きは目立たせる。
    # **日付だけ見てはいけない。形式ごとに見る。**
    # 2026-08-05、8/6 と 8/7 は「予約あり」と出ていたが、どちらも長尺だった。
    # 長尺は4本すべて0〜1回で、**露出が出ているのはショートだけ。**
    # 「予約が入っている日」を空きでないと数えたせいで、唯一効いている形式が
    # 翌日から途切れる状態を見落としかけた。**効いている形式で数える。**
    gaps = []
    for ahead in range(1, LOOKAHEAD_DAYS + 1):
        day = (datetime.now(JST) + timedelta(days=ahead)).strftime("%m/%d")
        if day not in short_days:
            gaps.append(day)
    if gaps:
        _r = _alerts.ring("schedule_gaps", len(gaps))
        if _r.folded:
            print("\n" + _r.line)
        else:
            print(f"\n[!] **ショート**の予約が入っていない日: {', '.join(gaps)}")
            print("    投稿が途切れるのが最大の損失。生成を撃ち直すこと。")
            print("    長尺が入っていても空きとみなす。露出が出ているのはショートだけだから。")
            print("    背後の生成はコンテナ再起動で消えるので、ログが残っていてもプロセスは死んでいる。")

    # **意図して伏せたものは警告しない。** 毎回鳴る警告は無視されるようになり、
    # 本当に予約し忘れたときに効かなくなる（2026-08-05）。理由は withheld.yaml に。
    withheld = {}
    wpath = Path(__file__).resolve().parent.parent / "config" / "withheld.yaml"
    if wpath.exists():
        import yaml
        withheld = {w["id"]: w.get("why", "") for w in
                    (yaml.safe_load(wpath.read_text(encoding="utf-8")) or {}).get("withheld", [])}

    # **理由は機械に出させる**（2026-08-16。**この警告はもう腐っていました**）。
    #
    # ここは長く「`withheld.yaml` に書いてあれば黙る、無ければ鳴る」でした。
    # **理由は手で書きます。** ところが予約を外す側（`reschedule.py`）は
    # **外すだけで理由を書かない**ので、外した本はそのまま警告に積まれます。
    #
    # この回の実測: **暗い18本のうち、理由が書いてあるのは6本。残り12本**が
    # 毎回並んでいて、**12本とも公開済み・予約済みと強く重なっていました**
    # （＝出さないのが正しい本。当たりは0件）。上の 2026-08-05 の註が
    # 「毎回鳴る警告は無視されるようになる」と言っている状態に、既に入っています。
    #
    # **欄を増やしても次の回がまた書き忘れます**（6回そうなった）。
    # `dupes.why_stranded` に理由を出させ、**出せなかったものだけ鳴らす。**
    try:
        from src import config as _cfg
        from src import dupes as _dp
        _topics = {t["id"]: t.get("calc", "") for t in _cfg.load_topics()["topics"]}
        _by_id = {v["id"]: v for v in videos}
        _live = [v for v in videos
                 if v["status"]["privacyStatus"] == "public" or v["status"].get("publishAt")]
        _found = {}
        for s in stranded:
            vid = s.split()[0]
            if vid in withheld or vid not in _by_id:
                continue
            r = _dp.why_stranded(_by_id[vid], _live, _topics)
            if r:
                _found[vid] = r
    except Exception as exc:
        _found = {}
        print(f"\n  重なりから理由を出せませんでした（続行）: {str(exc)[:90]}")

    unexpected = [s for s in stranded
                  if s.split()[0] not in withheld and s.split()[0] not in _found]
    if unexpected:
        _r = _alerts.ring("stranded", len(unexpected))
        if _r.folded:
            print("\n" + _r.line)
        else:
            print("\n[!] 公開されないまま止まっている動画があります:")
            for s in unexpected:
                print("  " + s)
            print("  **重なる相手は見つかりませんでした。** 予約し忘れならこのまま永久に出ません。")
            print("  出せるなら scripts/upload_only.py で予約を入れること（生成の要らない在庫です）。")
    if _found:
        print(f"\n（重なりがあるので出さない動画 {len(_found)}本。**機械が突き合わせた結果**）")
        for vid, r in _found.items():
            print(f"  {vid} ← {r['other']['id']} {r['other']['title'][:30]}（{r['why'][:44]}）")
    on_purpose = [s for s in stranded if s.split()[0] in withheld]
    if on_purpose:
        print(f"\n（意図して伏せている動画 {len(on_purpose)}本。理由は config/withheld.yaml）")

    # **自分で作った「繰り返し」を毎回ここで見る**（2026-08-16 に足した）。
    # 申し送りに **6回**「`status.py` に二重予約の検出を入れる」と書かれ、
    # 6回とも潰れていませんでした。**溜まる側の欠陥**で、いまは
    # `scripts/reschedule.py --list` を**手で叩かないと出ません。**
    #
    # そして、そちらが見ているのは**テーマIDの一致だけ**です。
    # この回に実物76本を突き合わせると、**テーマIDが違うのに中身が重なる組**が
    # 予約の中に残っていました（`35万9318円` が2本、`61万9千円` が公開済と2本目）。
    # **視聴者が見るのはテーマIDではなく、画面に出る金額**です。
    try:
        from src import config as _config
        from src import dupes as _dupes
        _dupes.report(videos, {t["id"]: t.get("calc", "")
                               for t in _config.load_topics()["topics"]})
    except Exception as exc:
        print(f"\n=== 自分で作った「繰り返し」===\n  [!] 見られませんでした: {str(exc)[:120]}")

    # 流入経路。表示されているのかどうかが、他の全部の前提になる。
    print(f"\n=== 流入経路（直近{days}日） ===")
    try:
        from src.analytics import fetch_traffic

        rows = fetch_traffic(days)
        if not rows or sum(r.get("views", 0) for r in rows) == 0:
            print("  まだ数字が返りません（Analytics は当日ぶんが遅れます）")
        for r in rows:
            print(f"  {r.get('insightTrafficSourceType', '?'):18s} 再生{r.get('views', 0):5d}"
                  f"  視聴{r.get('estimatedMinutesWatched', 0):5d}分")
    except Exception as exc:
        print(f"  読めませんでした: {str(exc)[:120]}")

    print_retention()
    print_channel_signals()
    print_where_watched()
    # **取れるものを全部引いて、前回との差を出す。**
    # ここを「毎回」にしたのが要点。手で選んでいる限り、選ばなかったものは
    # 永久に視界に入らない（2026-08-09、8次元を何日も見落としていた）。
    try:
        from src import scan as _scan
        _snap = _scan.collect()
        _scan.report(_snap, _scan._previous())
        _scan.save(_snap)
    except Exception as exc:                 # 走査が落ちても状態表示は続ける
        print(f"\n=== 全走査 ===\n  [!] 走査に失敗: {str(exc)[:150]}")
        print("      **これを放置しないこと。** 落ちている間は見落としが数えられない")
    print_local_sections(inventory=False)

    # 収益化の門。律速がどちらかを毎回見せる（docs/GOAL.md の掛け算）。
    def _short_median() -> float | None:
        """公開済みショート1本あたりの再生（中央値）。

        **28日窓で割らないこと。** この中身を出し始めたのは 8/4 で、
        前の22日はほぼ0。28で割ると1日173再生になり、**実際の4分の1**に見える。
        到達速度は「1日1本 × 1本あたり」で測る。

        **2026-08-10 に直した。ここは Analytics を読んでいた。**
        Analytics は2〜3日遅れるので、**新しい本ほど落ちる。**
        実際この日は 8/9 の934再生が入らず、中央値が 660 になっていた。
        **同じ数字が `videos.statistics`（遅れなし）に既にあり、
        `main()` がその場で引いている。** 遅いほうを読む理由が無かった。

        気づいたのは姉妹ループ（`docs/FROM_THE_ETA_LOOP.md`）の指摘から。
        向こうは「窓は6日ではなく4日」と書いてきた。**それ自体は当たっていて**
        （`day.*` は 8/4〜8/7 の4件しか無い）、こちらは日数で割っていないので
        直接は効かなかったが、**同じ遅れがこちらの別の場所を汚していた。**
        **指摘の結論ではなく、指摘の原因のほうが効くことがある。**
        """
        ns = sorted(v for v in short_views if v >= 30)
        if not ns:
            return None
        h = len(ns) // 2
        return ns[h] if len(ns) % 2 else (ns[h - 1] + ns[h]) / 2


    subs = int(stats.get("subscriberCount", 0) or 0)
    print("\n=== 収益化の門まで ===")
    print(f"  登録者     {subs:6d} / 1000   あと {max(0, 1000 - subs)}人")

    # **仮定の登録率で割らないこと。実測がある。**
    #
    # 2026-08-10 まで、ここは「登録率0.3%なら1000人は約33万再生」と出していた。
    # **0.3% はどこから来たのか誰も知らない数字で、実測は 14分の1 だった。**
    # 到達できるかを決める掛け算なので、仮定で置いてよい場所ではない。
    #
    # 1件しか起きていないので点推定は当てにならない。**上振れ側も出す**
    # （ポアソンで1件観測の95%上限はおよそ4.7件ぶん）。**楽観側で見ても届くか**
    # を毎回見るためで、悲観側を強調するためではない。
    try:
        from src import scan as _scan

        vals = (_scan._previous() or {}).get("values", {})
        gained = vals.get("合計.subscribersGained")
        views = vals.get("合計.views")
        if gained is not None and views:
            rate = gained / views
            hi = 4.744 / views                       # 1件観測の楽観側
            print(f"  **実測の登録率 {rate * 100:.3f}%**"
                  f"（{gained}人 / {views}再生。**仮定ではない**）")
            need = int((1000 - subs) / rate) if rate else None
            need_hi = int((1000 - subs) / hi) if hi else None
            if need:
                print(f"    あと1000人に必要な再生: **{need / 10000:.0f}万**"
                      f"（楽観側 {need_hi / 10000:.0f}万）")
            # **4000時間の門を、チャンネル合計の視聴時間で割らないこと。**
            #
            # 一度そう書いて、すぐ消した。2つ間違っている。
            #
            # 1. **ショートの視聴時間は4000時間に数えない。** 再生の99.95%が
            #    ショートのフィード内なので、合計で割ると**数えない時間で門を
            #    通る絵**が出る（174万再生で届く、と出た。届かない）
            # 2. `estimatedMinutesWatched ÷ 再生数` は `averageViewDuration` と
            #    2.6倍ずれる（走査の罠に書いてある）。**割って作らないこと**
            #
            # なので長尺だけで測る。ショート側は別の門（90日で1000万再生）。
            longs = {}
            for k, v in vals.items():
                if k.startswith("動画.") and k.count(".") >= 2:
                    _, vid, m = k.split(".", 2)
                    longs.setdefault(vid, {})[m] = v
            lf = [r for r in longs.values() if (r.get("尺") or 0) > 180]
            lf_views = sum(r.get("views", 0) for r in lf)
            lf_sec = sum(r.get("views", 0) * (r.get("averageViewDuration") or 0)
                         for r in lf)
            print(f"  長尺の視聴時間 **{lf_sec / 3600:.2f}時間** / 4000時間"
                  f"（長尺 {len(lf)}本・{lf_views}再生。"
                  "**ショートの視聴時間はこの門に数えません**）")
            if lf_views and lf_sec:
                per = lf_sec / lf_views
                print(f"    あと4000時間に必要な長尺の再生: "
                      f"**{int(4000 * 3600 / per) / 10000:.0f}万**"
                      f"（実測 1再生 {per:.0f}秒。**n={lf_views}**）")
            # **門の形を毎回書く。** 「どちらか一方」が登録者にも掛かると
            # 読めてしまうので、掛け算の形のまま出す。
            print("  門の形: **登録者1000人 かつ（4000時間 または"
                  " 90日で1000万ショート再生）**。**登録者は迂回できません**")
            print("  **この2つが数百万再生を指しているなら、"
                  "1本ずつ良くする道では届きません**（`docs/MEANS.md` を見ること）")

            # **門の先を掛ける。2026-08-10 まで一度もやっていなかった。**
            #
            # ここはずっと「門まであと何再生か」しか出していなかった。
            # **門を通ったあといくらになるのかを、誰も掛けていない。**
            # `docs/STRATEGY.md` はショートの RPM を ¥50〜150 と最初から
            # 書いていて、2026-08-04 に「収益化前は RPM の比較に意味がない」と
            # 正しく注記してある。**注記はそこで止まり、門の先に進まなかった。**
            #
            # 掛けたら **月990〜2,970円**。門が無料で消えても、この機械は
            # 月1000円台しか作らない。**20万には67〜202倍足りない。**
            # 長尺なら同じ20万円が月10〜25万再生で作れる（**40倍の差**）。
            #
            # **「門さえ通れば」という言い方をこれ以上させないための3行。**
            SHORT_RPM, LONG_RPM = (50, 150), (800, 2000)
            per = _short_median()
            if per:
                mv = per * 30                    # 1日1本
                lo, hi = (mv / 1000 * r for r in SHORT_RPM)
                print(f"\n  **門を無料で通れたとして、いまの収入: "
                      f"月 ¥{lo:,.0f}〜¥{hi:,.0f}**"
                      f"（ショート1日1本 {mv / 10000:.1f}万再生 × RPM ¥50〜150）")
                print(f"    20万に要るショート再生 "
                      f"**{200000 / SHORT_RPM[1] * 1000 / 10000:.0f}万〜"
                      f"{200000 / SHORT_RPM[0] * 1000 / 10000:.0f}万/月"
                      f"（いまの {200000 / hi:.0f}〜{200000 / lo:.0f}倍）**")
                print(f"    長尺なら同じ20万円が "
                      f"**月{200000 / LONG_RPM[1] * 1000 / 10000:.0f}〜"
                      f"{200000 / LONG_RPM[0] * 1000 / 10000:.0f}万再生**"
                      f"（RPM ¥800〜2000）。**要る再生数が40倍ちがう**")
                print("  **ショートは収入源ではありません。**登録者を取る道具です"
                      "（そちらも実測 0.021% で足りていない）")
    except Exception as exc:
        print(f"  [!] 実測の登録率が出せません: {str(exc)[:120]}")

    _print_analytics_recap()
    return 0


def _print_analytics_recap() -> None:
    """**アナリティクスの要点を、出力のいちばん最後に置き直す**（2026-08-16）。

    ## なぜ末尾なのか（**この回のオーナー指摘が理由です**）

    手順 `docs/trigger_main.md` §3 は
    **「`status.py` が出すものに全部目を通すこと」**と書いてあります。
    ところがこの出力は **250行**あり、子は毎回 `head` と `tail` で拾います。
    **アナリティクスの節（流入経路・維持・日次・視聴位置）はちょうど真ん中**にあり、
    8/16 08:1x の回は `head -70` / `sed 70,140p` / `tail -120` で読んで、
    **その隙間に丸ごと落としました。** オーナーに
    「アナリティクスから分析しないのはなぜ？」と聞かれて気づいています。

    **「全部読め」は、覚えていれば守れる規則です。だから守られません。**
    同じ回に直した `withheld.yaml` の欠陥と**同じ型**なので、同じ直し方をします ——
    **人に頼むのをやめて、構造で当てる。**

    `tail` は必ず末尾に当たります。だから**目標に直結する数字だけ**を、
    ここでもう一度出す。上の節は消していません（詳細はそちらにあります）。
    **ここにあるのは「どれを見て決めるか」の1画面**です。

    **足す条件**: 数字を1つ足すなら、**それで手が変わるものだけ**。
    「見ておくとよい」で増やすと、この節も250行になって同じことが起きます。
    """
    try:
        from src import scan as _scan
        vals = (_scan._previous() or {}).get("values", {})
        if not vals:
            return
        v = vals.get("合計.views") or 0
        if not v:
            return

        print("\n=== アナリティクスの要点（**この節は末尾に固定**）===")
        print("  上の各節の再掲です。`tail` で拾っても落ちないように置いてあります。")

        eng = vals.get("合計.engagedViews") or 0
        print(f"  **engaged {eng / v * 100:.1f}%**（{eng} / {v}）"
              "  ← 配信の駆動輪。維持率・尺・平均視聴秒は再生数と無関係")

        shorts_feed = vals.get("insightPlaybackLocationType.SHORTS_FEED") or 0
        watch = vals.get("insightPlaybackLocationType.WATCH") or 0
        if shorts_feed or watch:
            print(f"  **視聴ページ {watch}再生（{watch / v * 100:.2f}%）**"
                  f" / ショートのフィード {shorts_feed}"
                  "  ← 説明欄・再生リスト・長尺への導線は**読まれていません**")

        sh = vals.get("合計.shares") or 0
        cm = vals.get("合計.comments") or 0
        sv = vals.get("合計.videosAddedToPlaylists") or 0
        print(f"  共有 {sh} / コメント {cm} / 保存 {sv}（{v}再生に対して）"
              "  ← **動画が視聴者に何も問いかけていない**")

        red = vals.get("合計.redViews") or 0
        if red:
            print(f"  Premium 再生 {red}（{red / v * 100:.0f}%）"
                  "  ← RPM の内訳が広告だけではないことの実測")

        print("  **この4行で手が変わらないなら、変えるのは手ではなく台帳のほう**"
              "（`docs/MEANS.md`）。")
    except Exception as exc:
        print(f"\n=== アナリティクスの要点 ===\n  [!] 出せません: {str(exc)[:100]}")


def print_local_sections(inventory: bool = True) -> None:
    """**外の口を1つも叩かない節だけ**をまとめて出す。

    中身（手段の台帳・テーマ在庫・前提・使用量）は、以前から
    `_channel_main` の途中で呼ばれていました。**関数に括り出したのは、
    API が落ちた回にも同じものを出すため**です（下の `main` の註）。

    `inventory=True` のときだけ、**手元の控えから予約の先を数えます** ——
    普段は API 側の「[予約中]」の表が同じことを言うので、二重に出しません。
    """
    # **いちばん上に置いています。** ここに残っているのは
    # 「**運ばれてきたのに、まだ閉じていない依頼**」で、
    # 途中で死んだ回の申し送りが唯一残る場所です（`src/inbox.py`）。
    print(_inbox.render())
    if inventory:
        _print_inventory_from_ledger()
    print_means()
    # **`print_means` の隣に置いています。** あちらは「手段が尽きたか」、
    # こちらは「材料が尽きたか」で、**§4 でどれを選べるかを決めるのは両方**です。
    print_topic_stock()
    print_hypotheses()
    print_alert_hit_rate()
    print_budget()


def print_alert_hit_rate() -> None:
    """**機械が出す一覧に、自分の当たり率を出させる**（2026-08-16 に足した）。

    ## なぜ要るか（**同じ形が3件出てから足しています**）

        8/16 09:5x  持ち越しの上位が「既に潰れたもの」で埋まっていた   当たり率 低
        8/16 08:2x  「予約し忘れ」警告が12件まで育ち               **当たり0件**
        8/16 13:0x  「強い重なり」警告が22組まで育ち               **当たり0件**

    **3件とも「機械が出す一覧が、当たりを含まないまま育っていた」**です。
    1件ずつ潰しても、`status.py` は一覧を増やし続けます（4件目が出ます）。
    **だから潰す先を、個別の節から「節を出す枠組み」へ移しました。**

    ここは表を出すだけで、畳む判断は `src/alerts.py` が各一覧の中でやります。
    **表が要るのは、畳まれた一覧が黙って消えたように見えないため**です ——
    どの一覧が何回鳴って何回当たったかが、毎回1画面に出ます。
    """
    print("\n" + _alerts.render_table(_alerts.table()))


def _print_inventory_from_ledger() -> None:
    """**予約がどこまで埋まっているかを、手元の控えだけで出す**（2026-08-16）。

    §4 の選び方の1番目は「**予約が5日先を切っている → `upload`**」です。
    その判断に要る数字が、いままで **API の返りの中にしかありませんでした。**
    口が閉じた回は、いちばん最初に見るべき数字が消えます。

    控え（`data/uploaded.jsonl`）は**自分が上げたときに書いた行**なので、
    外の口の都合では欠けません。**取り消した本は載ったまま**なので、
    ここが出すのは上限側の見積りです（API が読める回はそちらが正）。
    """
    try:
        from src import dupes as _dupes
        rows = [r for r in _dupes.ledger_rows() if r.get("at")]
        if not rows:
            return
        now = datetime.now(timezone.utc)
        future = sorted(datetime.fromisoformat(r["at"].replace("Z", "+00:00")) for r in rows)
        ahead = [t for t in future if t > now]
        print("\n=== 予約の先（**手元の控えだけで数えた**）===")
        if not ahead:
            print("  [!] **先の予約が1本もありません。** この回は `upload` を選ぶこと")
            return
        days = (ahead[-1] - now).total_seconds() / 86400
        mark = "" if days >= 5 else "  ← **5日を切っています。§4 は `upload`**"
        print(f"  控えの最後 {_fmt(ahead[-1].isoformat())}"
              f"（**あと {days:.1f}日** / {len(ahead)}本）{mark}")
        print("  **上限側の見積りです**（取り消した本も控えには残ります）。"
              "API が読める回は上の「[予約中]」のほうが正。")
    except Exception as exc:
        print(f"\n=== 予約の先 ===\n  [!] 控えが読めません: {str(exc)[:100]}")

    _print_missing_thumbnails()


def _print_missing_thumbnails() -> None:
    """**サムネイルの載っていない予約**（2026-08-17 に足した。**3回持ち越された項目**）。

    日枠が切れている13時間は `thumbnails.set` だけが 403 になり、
    `videos.insert` は通ります。**投稿は済んでサムネイルだけ無い予約**が積まれる。

    ここに出す前は、どの本が載っていないかを持っていたのは**日誌の散文だけ**でした。
    散文は次の回の「次の回へ」数行にしか残らないので、3回運ばれて3回とも
    実行されていません。**しかも頼まれていた手順は実行不可能でした**
    （`refresh_thumbnail.py` は `build/` を読むが、`build/` は毎周消える）。
    **控えの側に印を持たせたので、以後は機械が数えます。**
    """
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import critique_queue

        rows = critique_queue.missing_thumbnail()
    except Exception as exc:
        print(f"\n=== サムネイル ===\n  [!] 控えが読めません: {str(exc)[:100]}")
        return
    if not rows:
        return
    _r = _alerts.ring("missing_thumbnail", len(rows))
    if _r.folded:
        print("\n" + _r.line)
        return
    print(f"\n=== サムネイルの載っていない予約（**{len(rows)}本**）===")
    for row in rows[:12]:
        print(f"  {row['video_id']}  {row['topic']}")
    if len(rows) > 12:
        print(f"  ほか {len(rows) - 12}本")
    print("  **押し直すのは1行です**（`build/` は要りません。bytes は控えにあります）:")
    print("      python scripts/refresh_thumbnail.py --missing")
    print("  **日枠が戻ってから**（JST 16:00 ごろ）。それより前は 403 で落ちます。")
    print("  潰したら `run_marker.py --ship ... --closes missing_thumbnail`。")


def main(days: int = 7) -> int:
    """**外の口が落ちても、手元で分かることは全部出す**（2026-08-16 に分けた）。

    ## なぜ分けたか（**この回が実際に踏んでいます**）

    `_channel_main` の1行目は `youtube.channels().list(...)` で、
    **`try` の外にありました。** 2026-08-16 11:5x の回はここが
    `403 quotaExceeded` で落ち、**出力が1行も出ませんでした。**

    落ちたのは外の口だけです。**手段の台帳・テーマ在庫・期限の来た前提・
    使用量の速さ・予約の先は、全部この機械の中にあって、無事でした。**
    それでも手順 §3 の「`status.py` が出すものに全部目を通すこと」は
    **達成率0**になり、その回は何も見ないまま §4 を選ぶことになります。

    **Data API の枠は太平洋時間の0時に戻ります（＝ JST 16:00〜17:00）。**
    つまり枯れた回は1回ではなく、**戻るまでの全部の子**が同じ目に遭います。

    ## 直し方を、この形にした理由

    成功する回の**出力の並びを1文字も変えていません** —— `print_local_sections`
    は元の位置（`_channel_main` の中）で呼ばれ、`_print_analytics_recap` は
    末尾に固定されたままです（あの節は `tail` で拾えることが存在理由なので、
    後ろに何かを足すと壊れます）。**落ちた回だけ、ここで拾い直します。**
    """
    try:
        return _channel_main(days)
    except Exception as exc:
        print("\n" + "=" * 66)
        print("[!] **外の口が落ちました。チャンネル側の数字はこの回では出ません。**")
        print(f"    {type(exc).__name__}: {str(exc)[:220]}")
        if "quotaExceeded" in str(exc) or "quota" in str(exc).lower():
            print("    **Data API の1日枠（10,000単位）です。**"
                  "戻るのは太平洋時間の0時＝**JST 16:00 ごろ**。")
            # **ここは「枠が戻るまで `upload` は選べません」と言っていました。嘘です。**
            # 2026-08-17 03:5x に実際に `videos.insert` を叩いて、**通りました**
            # （`fLENot-5oKM`）。落ちるのは読みの側（`videos.list` / `playlistItems` /
            # `channels.list` / `search`）と `thumbnails.set` / `playlists` だけです。
            # **この1行が、1日13時間ぶんの `upload` を止めていました。**
            print("    **それでも `upload` は選べます**（2026-08-17 に実測）。"
                  "落ちるのは**読みの側**で、`videos.insert` は通ります。")
            print("    サムネイルだけ載りません（`thumbnails.set` も 403）。"
                  "**公開前に `scripts/refresh_thumbnail.py` で載せ直すこと。**")
        print("    **この回を止めないこと。** 以下は手元だけで出しています。")
        print("=" * 66)
        print_local_sections()
        _print_analytics_recap()
        return 0


if __name__ == "__main__":
    # `--alerts-all` は、畳んだ一覧を全文で出す（`src/alerts.py`）。
    # **旗はここだけ。** 各節は `alerts.ring()` の返り値しか見ません
    # （call site に条件を書かせると、一覧を足した回が片方だけ書き忘れます）。
    _argv = [a for a in sys.argv[1:] if a != "--alerts-all"]
    _alerts.set_show_all("--alerts-all" in sys.argv[1:])
    raise SystemExit(main(int(_argv[0]) if _argv else 7))
