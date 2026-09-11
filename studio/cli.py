"""1日1本の運転。手順の正本は docs/METHOD.md。

    python -m studio.cli status                 # きょうの枠・次の枠・最近の本の再生（API 数単位）
    python -m studio.cli lint <id>              # 台本の形
    python -m studio.cli build <id>             # 声 → 絵 → mp4 → sheet.png（目で見る）
    python -m studio.cli hear <id> [--medium]   # 完成音声を聞き取り、予定の読みと照合
    python -m studio.cli read <id>              # 冷読（Haiku）: 1文で言い返せるか
    python -m studio.cli critique <id>          # 分かりやすさの批判（Sonnet）
    python -m studio.cli crosscheck <id>        # 声と 説明欄・notes の食い違い（Sonnet・§4 (0)）
    python -m studio.cli order-image <id>       # 背景画像を注文（外の ChatGPT セッションが焼く）
    python -m studio.cli schedule <id> --at 10:00 [--replace <videoId>]   # きょうの枠へ予約（当日だけ）
    python -m studio.cli measure                # 公開ずみの本の再生・高評価を台帳へ
    python -m studio.cli trend [--days 3]       # 台帳から「齢 → 再生」の並び（API 0単位・§7 の判定はこれで）
    python -m studio.cli trend --by-day-count   # 「その日に何本 出したか」ごとの 48時間 再生（API 0単位・§7 の覆る条件）
    python -m studio.cli comments               # 視聴者が書いたコメント（自分の自動コメントは除く。API 1単位）
    python -m studio.cli reporting [--setup]    # 一括レポート（Reporting API・Data API 0単位・Analytics より 2日 早い）
    python -m studio.cli reply <comment_id> --text "…"   # 視聴者のコメント1件に手で書いた返信（50単位・台帳 replied）
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from . import analytics, critic, hear, render, reporting, script, trend, yt
from .common import JST, ROOT, ledger, ledger_rows, now_jst, today_jst, workdir

IMAGES = ROOT / "assets" / "images"
ORDERS = ROOT / "data" / "image_orders"
MAX_SECONDS = 95.0   # Shorts は 3分 まで。分かる説明に要る長さを優先し、実測で締める（docs/METHOD.md）


def image_for(vid: str) -> Path | None:
    for ext in ("jpg", "png"):
        p = IMAGES / f"{vid}-bg.{ext}"
        if p.exists():
            return p
    return None


def studio_video_ids(rows: list[dict] | None = None) -> set[str]:
    """studio が上げた本の ID（台帳 `scheduled` の video_id）。ここに無い本は旧作り。"""
    rows = ledger_rows() if rows is None else rows
    return {r.get("video_id") for r in rows if r.get("event") == "scheduled" and r.get("video_id")}


def lineup_mark(v: dict, studio_ids: set[str]) -> str:
    """「きょうの枠」「予約」の1行に添える印。**旧作りの本が予約のまま並んでいたら、名指しで「戻せ」と言う。**

    実測 2026-09-08: 旧 `reschedule.py` が 09/02 に打った publishAt が 23:00 JST に発火し、
    `Yy7GmcGoQ6I`（自動車税・旧作り）が public になった。`status` は一日中
    「23:00 private  Yy7GmcGoQ6I」を きょうの枠に印字していたが、印が無いので
    3周の hourly が「きょうの枠は公開ずみ」とだけ読んで通り過ぎた（§12 23:0x）。
    09/05 17:1x・09/06 02:1x に private へ戻した 4本 と同じ型で、これは漏れた 1本。
    """
    if v["id"] in studio_ids:
        return ""
    if v["privacy"] != "public":
        return "  !! 旧作りの予約 → private へ戻すこと（1日1本・METHOD §5/§9・台帳 unscheduled）"
    return "  [旧作り]"


def meta_drift(video_id: str, rd: dict, rows: list[dict] | None = None) -> list[str] | None:
    """上がっている本の 題・説明欄・tags が、台帳 `scheduled` の台本と食い違っている所（2026-09-09 01:5x・hourly・Fable）。

    `status` は「処理 済」しか見ておらず、**上がった説明欄が台本と違っても黙っていた**。説明欄だけを直す回
    （09/07 05:5x・09/08 19:1x）は予約の**前**に来たから通ったが、予約の**後**に来たら `yt.update_meta` を撃たない限り
    古い説明欄のまま 10:00 に出る。同じ `videos.list` の `snippet`（0単位 増）で見えるので、判断ごと印字する。
    返り: 食い違った欄の名前（空なら一致）。台帳に無い ID（旧作り）や台本ファイルが無ければ None（比べる物が無い）。
    tags は YouTube が並べ替えて返す（実測 09/09 01:4x）ので集合で比べる。
    """
    rows = ledger_rows() if rows is None else rows
    sid = next((r.get("id") for r in reversed(rows) if r.get("event") == "scheduled" and r.get("video_id") == video_id), None)
    if not sid or rd.get("title") is None:
        return None
    try:
        s = script.load(sid)
    except FileNotFoundError:
        return None
    out = []
    if rd.get("title") != s.title:
        out.append("題")
    if rd.get("description") != s.description:
        out.append("説明欄")
    if set(rd.get("tags") or []) != {t[:30] for t in s.tags[:15]}:
        out.append("tags")
    return out


def meta_mark(drift: list[str] | None) -> str:
    if drift is None:
        return ""
    if not drift:
        return "台本と一致（題・説明欄・tags）"
    return (f"!! 台本と食い違い: {'・'.join(drift)} → `yt.update_meta(<videoId>, s.title, s.description, s.tags)`"
            "（50単位・ID も予約もそのまま）。本文（声・画面）も変えたなら `schedule --replace`")


def comments_to_show(cs: list[dict], fresh: list[dict], keep: int = 3) -> list[dict]:
    """`status` に印字する視聴者コメントの行を選ぶ。

    **必ず出す**: 台帳に無い新着（`fresh`）と、**まだこちらが答えていない行**（`answered` が偽）。
    残りは新しい順に `keep` 件まで。

    2026-09-10 01:4x JST（optimizer・Opus）に足した。**この回に踏んだ**:
    `status` は「**未返信 3件**」と数を印字しながら、行のほうは新しい順に 3件 で
    切っていたので、**その 3件 が 1行も出ませんでした**（実測 01:2x: 出た 3行 は
    どれも `[返信ずみ]`）。未返信の 3件 は **08/21・08/29×2 の古い行**で、
    その中に **このチャンネルが受け取った唯一の批評「ＡＩナレーショングダグダ」**が
    在ります（§7 の 20:4x の行が「ここに出し続けること」と書いている当のもの）。
    ＝ **新しい順の窓は、放置された行を構造的に隠します**（古いほど隠れる ＝
    放置が長いほど見えない・向きが逆）。`comments` を撃てば出ますが、
    毎周 撃たれるのは `status` のほうです。

    **覆る条件**: 未返信が 10件 を越えて `status` が読めなくなったら、ここで切るのではなく
    「未返信の古い順に 3件 ＋ 残り n件」の形にすること（数だけ残す形は、
    上と同じ隠し方になるので、**必ず何行かは出すこと**）。
    """
    must, seen_ids = [], set()
    for c in fresh + [c for c in cs if not c.get("answered")]:
        if c["id"] not in seen_ids:
            seen_ids.add(c["id"])
            must.append(c)
    rest = [c for c in cs if c["id"] not in seen_ids]
    return must + rest[:keep]


STATUS_COMMENT_CHARS = 60


def comment_line_text(text: str, limit: int = STATUS_COMMENT_CHARS, one_line: bool = True) -> str:
    """視聴者コメントを **1行** に畳む。**落とした字は必ず数で言う。**

    2026-09-10 12:0x JST（optimizer・Opus）に足した。**この回に踏んだ**:
    `status` は `c["text"][:60]` を素で印字していたので、**2つ 落としていました**。

    実測（09/09 23:49 の礼・**88字**）:

        出た   ``…年金事務所の方に聞きに行ってもたぶん有効みたいな感じ``
        落ちた ``でハッキリした回答が得られなかったので大変助かりました。``（**28字**）

    ＝ 切れ目が **文の途中**なので、出た側だけを読むと「年金事務所でも たぶん有効と
    言われた」と**逆の意味に読めます**。落ちたのは、§7 が「制度の窓口で分からなかった
    ことが、ここで分かった と視聴者が書いた最初の1件」と呼んでいる当の節でした。
    **印が無いので、読む側は切れたことを知りません。**

    2つ目: この文には **改行**が在り、素で印字すると **1件が 2行に割れます**。
    2行目には刻も ID も `[未返信]` も付かないので、**別のコメントに見えます**
    （実測: 09/08 の「そこが知りたい」も同じ形で割れていた）。

    ＝ **`comments_to_show`（01:4x）が「どの行を出すか」で塞いだ穴の、
    「その行に何が載るか」の側**です。窓を直しても、窓に載る字が黙って欠けていました。

    **覆る条件**: (1) 印つきで切れた行を見た回が、`comments` を撃たずに
    その行だけで判断した回が出たら、`limit` ではなく**未返信の行だけ全文**にすること。
    (2) 台帳の `text` は `cmd_comments` が **500字** で切っており、そちらは印が無い。
    500字 を越えるコメントが 1件でも来たら、同じ形（落とした字数を残す）にすること
    —— いまの最長は 88字 なので、まだ引けない。
    """
    one = " ⏎ ".join(text.split("\n")) if one_line else text
    if len(one) <= limit:
        return one
    return one[:limit] + f"…〔＋{len(one) - limit}字・全文は `python -m studio.cli comments`〕"


def over_ledger(vid: str, live: int, rows: list[dict] | None = None) -> int | None:
    """`status` の生の読みが、**台帳が持っている最大より高い**とき、その差を返す（でなければ None）。

    2026-09-10 12:4x JST（optimizer・Opus）に足した。**この回に踏んだ。**

    **踏んだ形**: 12:25 の `status` は 3本目 `lQHX9LJ80Sg` を **658回** と印字し、
    7分後の `measure`（`settle_stats` の **3回 読みの最大**）は **613回** を台帳へ書きました。
    **同じ `videos.list` の同じ `statistics.viewCount`** です（読む口は 1つ）。
    **再生は減らないので、真の値は 658 以上** ＝ **台帳に入った 613 は 45回（7.3%）低い。**

    **なぜ 3回 では拾えないか**（この回に撃って数えた・1読み 1単位）:

        8回 読み    613×7・**658×1**
        24回 読み   613×24（**0回**）
        ＝ 高いほうの複製は **33読み中 2回（約6%）** しか出ません

    ＝ `settle_stats(reads=3)` がこれを拾う見込みは **2割 を切ります**。
    **そして 3回 が全部そろっても、それは「落ち着いた」ではありません** ——
    この回の `measure` は「揺れた **0本**」と印字しており、`n_values` は **1** です。
    **§7 (h) の覆る条件 (3) は `n_values` で鳴る門なので、この型では構造的に鳴りません。**

    **効くのは「いまの数」ではなく「平ら」の側**（envelope は最大を取るので、
    次にどれかの読みが 658 を見た周に台帳は追いつきます）——
    **追いつくまでのあいだ、台帳には同じ値が並び、それは「本が止まった」と同じ形に見えます。**
    実測: 3本目 は 48.3h→50.5h の **4周** が 613 で並んでおり、§7 (a) はこの並びを
    「48.3h の +77 のあと 平ら」と読んで **60.4時間 の物差し**に当てています。
    **その平らの少なくとも一部は、本ではなく読みです。**

    **手**: `status` はこの読みに **1単位 も払っていません**（本の行を出すのに既に引いた数）。
    **高い側を見たら、捨てずに印字する。** 拾うのは次の `measure` の仕事（judgement は
    `hourly`・§5）。ここは「台帳がまだ持っていない数を、いま見た」と言うだけです。

    **比べる先は台帳の最大**（envelope と同じ側）で、最後の行ではありません ——
    `recounts` が峰を落とした本では、最後の行より高い値が台帳に在ります。
    **低い側は印字しません**（遅れている複製は既知で、envelope が吸います・§6）。

    **覆る条件**: (1) この印が出た次の `measure` が 3周 続けてその数に届かなければ、
    高い側は複製ではなく別の口 ＝ そのときは `settle_stats` の `reads` ではなく
    **どの読みが高いか**（時刻・順番）を数えること。
    (2) この印が 1度も出ないまま 7本 過ぎたら、12:25 の 658 は一度きりの揺れ ＝ この口を外す。
    (3) 印が毎周 出るなら、拾う側（`settle_stats` の `reads`）を上げるほうが安い。
    """
    rows = ledger_rows() if rows is None else rows
    seen = [r["views"] for r in rows
            if r.get("event") == "measured" and r.get("id") == vid
            and isinstance(r.get("views"), int)]
    if not seen:
        return None
    top = max(seen)
    return live - top if live > top else None


def record_over(vid: str, live: int, over: int, age_h: float,
                src: str = "status") -> None:
    """`over_ledger` の印を**台帳に1行 残す**（2026-09-10 13:2x・optimizer・Opus。**追加 0単位**）。

    12:4x は印字だけを足しました。その註の覆る条件は **3つ とも周をまたいで数える**もの
    （(1) 次の measure が 3周 届かない・(2) 1度も出ないまま 7本・(3) 毎周 出る）なのに、
    **印が出たことを残す口が どこにもなく**、次の回は前の回の端末の出力を覚えているしか
    ありませんでした ＝ `trend.flats` の「その 3本 を数える所が、どこにもなかった」と同じ族。
    数えるのは `trend.over_lag`（毎周 `trend` が印字する ＝ **次の回は覚えていなくてよい**）。

    **`src` は、その読みを誰が見たか**（既定 `status`）。2026-09-10 14:1x に足した ——
    この回は `status` ではなく `videos.list` を直に撃って高い読み（683 対 台帳 671）を見たので、
    印の出どころが台帳から分かるようにした。`trend.over_lag` は出どころで分けません
    （同じ現象 ＝ 生の読みが台帳の最大より高い）が、**覆る条件 (3)「印が毎周 出る」を
    数えるときは、手で撃った回を分けて見ること**（毎周 出るのが `status` の側かどうかで、
    `settle_stats` の `reads` を上げる判断が変わります）。

    **`measured` では書きません** —— 帯の2点組の分母は `measured` の刻を数えており
    （`trend.informative`/`gate_span`）、そこへ入れると**測っている物差しを測っている最中に
    取り替える**ことになります。別の event 名で残し、読むだけにしてあります。
    """
    ledger("views_over", vid, views_live=live, views_ledger=live - over,
           over=over, age_h=round(age_h, 1), src=src)


ZERO_PROBE_MIN_H = 3.0    # 台帳の中で「0回 のまま」を越えた本が 1本 も無い齢（§7「1回目が付いた齢」）
ZERO_PROBE_MAX_H = 48.0   # ここを越えたら「配りが来ていない」ほうの話 ＝ 処理は関係ない


def zero_probe_target(pubs: list[dict], studio_ids: set[str], now: dt.datetime) -> str | None:
    """**公開ずみなのに 0回 の studio の本**を 1本 だけ選ぶ（`status` が 1単位 で処理の状態を引く先）。

    2026-09-10 15:0x・optimizer・Opus。**追加 1単位**（この門が立っている周だけ・1周 1本まで）。

    **穴**: `yt.readiness()` は 09/08 02:5x から在りますが、`cmd_status` はそれを
    **`privacy != "public"` の本にしか当てていません**（公開前に「10:00 に本当に出るか」を
    見るために足された口）。**公開したあとに処理が落ちた本・拒否された本は、誰も見ません** ——
    見えるのは「0回」だけで、それは `trend` の側では「配りが来ていない」と同じ形です。

    ＝ §4 (0-b) の族の**4つ目の型**（1つ目 見つけた上で別の札／2つ目 両側がそろって間違える／
    3つ目 欄が無いのを 0回 と読む（`yt.views_of`）／**4つ目 出ていないのを 0回 と読む**）。

    **この回に手で撃って実測した**（`videos.list` 1単位・5本目 `2YZ_4FXC-XI` 齢 4.5h 0回）:
    `uploadStatus processed`・`processingStatus succeeded`・`failureReason` なし・
    `rejectionReason` なし・`privacyStatus public`・`madeForKids false`・`duration PT1M30S`
    ＝ **この本の 0回 は本物で、「出ていない」ではありません。**
    **その1単位を、次の回が手で撃たなくてよいように道具へ入れました。**

    **門**（1周 1単位 を越えないための形）:
      * studio の本だけ（旧作りの 0回 は診る先が無い ＝ §8）
      * `views == 0` かつ `views_absent` でない（欄が無い側は `yt.views_of` の口）
      * 齢 `ZERO_PROBE_MIN_H` 〜 `ZERO_PROBE_MAX_H`（台帳の 4本 は 齢 5.0h までに 1回目が付いた・§7）
      * **いちばん若い 1本 だけ**（0回 の本が 2本 並んでも 1単位 のまま）

    **同じ周に `hourly` が別の側から同じ問いを撃っています**（14:3x・§14）——
    `https://www.youtube.com/shorts/<id>` の公開ページを 5本目 と 4本目 で並べ、
    `playabilityStatus` OK・`isShortsEligible` true ほか **8項目 とも同じ・違うのは viewCount だけ**
    （**API 0単位**）。**2つは違う物を見ます**（§5 の教訓の形1つ目を先に撃った）:
    公開ページは**視聴者から見て再生できるか**、`readiness` は**持ち主から見た uploadStatus /
    processingStatus / rejectionReason**（拒否の理由・処理が途中か）。
    重なるのは「再生できない」形だけで、**「処理が途中」「拒否の理由の名前」は公開ページに出ません。**
    **ただし 0単位 の側のほうが安いので、下の (2) で 2つが 7本 一度も食い違わなければ、外すのはこちら側です。**

    **覆る条件**: (1) この門が立った本の `readiness` が **`ok` でなかった回が 1度でも出たら**、
    それは「0回」を読む前に必ず見る数 ＝ `trend` の側（`first_view`・`hold`）にも印を回すこと。
    (2) 7本 過ぎて 1度も `ok` 以外が出なければ、この口は外してよい（`yt.views_of` の (j) と同じ数え方）。
    **数えるのは台帳の `zero_probe` の行**（`ok` を毎回 残しているので、次の回は覚えていなくてよい）。
    (3) 0回 の本が 2本 以上 同時に並ぶ回が出たら、1本だけでは足りない ＝ 束で引くこと（`videos.list` は 50件で 1単位）。
    """
    best, best_age = None, None
    for v in pubs:
        if v["id"] not in studio_ids or v["views"] != 0 or v.get("views_absent"):
            continue
        age = (now - yt.when(v)).total_seconds() / 3600
        if not (ZERO_PROBE_MIN_H <= age <= ZERO_PROBE_MAX_H):
            continue
        if best_age is None or age < best_age:
            best, best_age = v["id"], age
    return best


def zero_probe_mark(rd: dict) -> str:
    """`zero_probe_target` の本に添える1行。**`ok` でも黙らない**（0回 が本物だと言うのが仕事）。"""
    if rd["ok"]:
        return ("  ** 0回 のまま ＝ **出ていない側ではありません**"
                f"（upload {rd['upload']}・processing {rd['processing']}・失敗 なし・1単位）")
    return ("  !! **0回 の出どころは処理の側です**"
            f"（upload {rd['upload']}・processing {rd['processing']}・"
            f"失敗 {rd['failure'] or rd['rejection']}）—— `zero_probe_target` の覆る条件 (1)")


def record_channel(ch: dict) -> None:
    """`status` が毎周 読んでいる**チャンネルの数**を台帳に1行 残す（2026-09-10 15:5x・optimizer・Opus。**追加 0単位**）。

    **穴**: `cmd_status` は 09/05 から毎周 `yt.channel()` を撃ち（登録・総再生・本数）、
    **1行 印字して捨てて**いました。**残す口がどこにも無い**ので、
    次の 2つ が、道具の側からは 1度も数えられていません:

      * **登録率**（§7 の収益の節の覆る条件 (1)「登録率が実測で 0.5% を越えたら」）——
        分子は登録の**増え**で、それは 2点 が要ります。METHOD §1 の「登録者 25人」は
        09/05 に手で写した 1点 で、いまの 27人 との差が**いつ付いたか**を誰も言えません。
      * **チャンネル全体の総再生が動いているか** —— 本ごとの 0回 が
        「その本の配りが来ていない」のか「チャンネルの側が止まっている」のかを分ける唯一の数。
        5本目 `2YZ_4FXC-XI` が 齢 5.3h で 0回 のまま §7 (c) の門を越えた回（この回）に、
        **その問いに答える点が台帳に 1点 も無い**ことで気づきました。

    ＝ `record_over`（12:4x は印字だけ・13:2x に残す口を足した）と**同じ族**の 3つ目です
    ——「毎周 印字しているのに、周をまたいで数える口が無い」。

    **`measured` では書きません**（`record_over` の註と同じ理由 —— 帯の2点組の分母は
    `measured` の刻を数えているので、別の event 名で残して読むだけにする）。

    数えるのは `trend.channel_growth`（毎周 `trend` が印字する ＝ **次の回は覚えていなくてよい**）。

    **覆る条件**: (1) 総再生の増えが、同じ窓の**本ごとの増えの合計と 10% 以上 食い違う**回が出たら、
    チャンネルの `viewCount` は本の合計ではない（ショートの feed 視聴の数え方が違う）＝
    そのときは「チャンネルが止まったか」をこの数で読まないこと。
    **2026-09-10 16:4x に、この (1) を道具が当てるようにしました**（`trend.channel_video_delta`。
    それまでは**どこも数えておらず**、次の回が手で数えるしかない条件でした）。
    **門は片側だけ**です —— `measure` が触るのは公開から 7日 以内の本（実測 46本）で
    チャンネルは 269本 持つので、**チャンネル ＞ 合計**の側はいつでも「触っていない本」で説明が付きます。
    引くのは**合計 ＞ チャンネル**（触っている本の増えを、総再生が受け取っていない側）だけ。
    **そして「その食い違いが 3周 続いたか」は、周では数えられません**（2026-09-10 21:4x・
    `trend.channel_over_blocks` の註）—— `channel_growth` の窓は台帳の両端なので伸びる一方で、
    `sum_confirmed` は**単調に増えるだけ**です ＝ **1度 引かれた門は、新しい証拠が 1つも無くても
    毎周 引かれ続けます**（実測: 21:20 の周に `gv1u7n_pCAQ` の +2回 だけで初めて引かれた）。
    数えるのは**重ならない塊**（1塊 ＝ 遅れの 2倍 ＝ 5.6時間・`trend.channel_over_streak`）。
    (2) 登録が 1度も動かないまま 7本 過ぎたら、登録率は「0.5% を越えたか」ではなく
    **「分子が 0 のまま何本か」**で読むこと（§7 の収益の節の覆る条件 (1) の書き方を直す）。
    (3) **この行は 1周に 2行 入ります**（`hourly` と `optimizer` が両方 `status` を撃つ）。
    **その 2行 は違う数のことがあります**（2026-09-11 04:0x の実測: 54秒 差で 1,625 違った）——
    `viewCount` は複製から返るので、**読む側は周ごとの max を取ります**（`trend.channel_replicas` の註）。
    §7 (m) の門は**周**なので、`trend` は行ではなく**周**（10分 で畳む）で数えます
    （`trend._channel_laps`）。畳みが実物と合わなくなったら（穴埋めの周で 1体 しか立たない回が続く など）、
    `data/rounds.jsonl` の側から周を引くこと。
    """
    ledger("channel", ch["id"], subs=ch.get("subscriberCount"),
           views=ch.get("viewCount"), videos=ch.get("videoCount"))


def record_ready(vid: str, rd: dict, drift) -> None:
    """公開**前**の本の `readiness` を、印字するだけでなく台帳に残す
    （2026-09-10 16:2x・optimizer・Opus。**追加 0単位** ＝ `cmd_status` がすでに引いてある 1単位）。

    **穴（同じ族の 4つ目）**: `yt.readiness` は 09/08 02:5x に「10:00 に本当に出る状態か」を
    見るために足され、`cmd_status` が**予約ずみの本を持つ周は毎周**（実測 1日 約14周）
    「処理 済／!! 処理 …」と印字してきました。**残す口は無く**、台帳の `ready_checked` は
    **09/08 02:46 に手の script が書いた 1行 だけ**です。
    ＝ **「予約から公開までの窓で、この本が 1度でも `ok` でなかったか」に答えられません** ——
    それは `readiness` が足された、その当の問いです。

    族の 1つ目 `record_over`（12:4x → 13:2x）・2つ目 `zero_probe`（05:3x → 05:4x）・
    3つ目 `record_channel`（15:5x）と同じ形。
    **見つけ方**（15:5x に出た）: **「次の回が使う」と書いてある数のうち、`ledger()` を通っていないもの。**

    `meta_drift` の結果も同じ行に入れます（説明欄が台本と違えば古いまま出る ＝ `yt.readiness` の註）。
    **`drift` は `meta_drift()` の返り**（食い違った欄の名前の並び・`None` は比べる物が無い）。

    **覆る条件**: (1) `ok` でない行が 1度でも出たら、その本の公開の刻を疑う前に**この行を先に見る**
    （どの周から落ちていたかが分かる）。(2) 7本 過ぎて 1度も `ok` 以外が出なければ、
    公開**前**の 1単位 は毎周 撃たなくてよい（`zero_probe` の (2) と同じ数え方 ＝
    そのときは予約の直後と 09:xx の周だけにする）。
    """
    ledger("ready_checked", vid, ok=bool(rd.get("ok")), upload=rd.get("upload"),
           processing=rd.get("processing"),
           failure=rd.get("failure") or rd.get("rejection"),
           meta_drift=(None if drift is None else list(drift)))


def cmd_status(a):
    ch = yt.channel()
    vids = yt.all_videos()
    sids = studio_video_ids()
    print(f"チャンネル: 登録 {ch['subscriberCount']}・総再生 {ch['viewCount']}・本数 {ch['videoCount']}")
    # 毎周 読んでいた数を台帳へ（`record_channel` の註。**追加 0単位** ＝ 上ですでに引いてある）。
    record_channel(ch)
    # **短い形で印字する**（2026-09-10 23:2x・optimizer・Opus）—— `trend` も同じ周に
    # `channel_line`（1,035字）を印字しており、`optimizer` は**同じ段落を 2度**読んでいた。
    # 決めと数はここに残し、derivation は `trend` の側（＝ `output_growth` に映る側）に置く。
    # **`trend.channel_line` をここへ戻さないこと**（覆る条件は `trend.channel_line_short` の註）。
    cl = trend.channel_line_short(ledger_rows())
    if cl:
        print("  " + cl)
    print(f"いま {now_jst():%m/%d %H:%M} JST")
    print("きょうの枠:")
    for v in yt.today_lineup(vids):
        print(f"  {yt.when(v):%H:%M} {v['privacy']:8s} {v['id']} {v['views']:5d}回 {v['title'][:40]}{lineup_mark(v, sids)}")
        if v["privacy"] != "public":
            # 公開前の本だけ、YouTube 側の処理が終わっているかを添える（1単位。`yt.readiness` の註）。
            rd = yt.readiness(v["id"])
            mark = "処理 済" if rd["ok"] else f"!! 処理 {rd['upload']}/{rd['processing']} 失敗 {rd['failure'] or rd['rejection']}"
            print(f"           {mark}（upload {rd['upload']}・processing {rd['processing']}）")
            drift = meta_drift(v["id"], rd)
            mm = meta_mark(drift)
            if mm:
                print(f"           {mm}")
            # 印字だけにしないこと（`record_ready` の註 ＝ 同じ族の 4つ目）。**追加 0単位。**
            record_ready(v["id"], rd, drift)
    print("予約（あす以降）:")
    for v in yt.scheduled_all():
        if yt.when(v).date() > now_jst().date():
            print(f"  {yt.when(v):%m/%d %H:%M} {v['id']} {v['title'][:40]}{lineup_mark(v, sids)}")
    print("直近 公開 10本:")
    lrows = ledger_rows()
    for v in yt.published()[:10]:
        age = (now_jst() - yt.when(v)).total_seconds() / 3600
        # 2026-09-10 12:4x: **台帳より高い読みを捨てない**（`over_ledger` の註。追加 0単位）。
        over = over_ledger(v["id"], v["views"], lrows)
        if over:
            record_over(v["id"], v["views"], over, age)
        mark = f"  ** 台帳の最大より +{over}回 ＝ まだ台帳に無い（次の measure で拾うこと）" if over else ""
        # 0回 と「欄が無い」を分ける（`yt.views_of` の註）。立たない回は 1字も足さない。
        if v.get("views_absent"):
            mark += "  ** `viewCount` の欄がありません ＝ この 0回 は読めていないだけ（`yt.views_of` の覆る条件 (1)）"
        print(f"  {yt.when(v):%m/%d %H:%M} {v['id']} {v['views']:5d}回 いいね{v['likes']:3d} 齢{age:5.0f}h {v['title'][:36]}{mark}")
    # 公開ずみで 0回 の studio の本があれば、処理の側かどうかを 1単位 で見る（`zero_probe_target` の註）。
    zp = zero_probe_target(yt.published(), sids, now_jst())
    if zp:
        rd = yt.readiness(zp)
        print(f"  {zp} {zero_probe_mark(rd)}")
        ledger("zero_probe", zp, ok=rd["ok"], upload=rd["upload"],
               processing=rd["processing"], failure=rd["failure"] or rd["rejection"])
    # 視聴者のコメントは 2026-09-07 20:4x まで1度も見ていなかった（`yt.viewer_comments()` の註）。
    # 唯一の批評「ＡＩナレーショングダグダ」は 9日間 読まれていない。**ここに出し続けること。**
    try:
        cs = yt.viewer_comments()
        seen = {r.get("comment_id") for r in ledger_rows() if r.get("event") == "viewer_comment"}
        fresh = [c for c in cs if c["id"] not in seen]
        held = [c for c in cs if c.get("status", "published") != "published"]
        note = f"・**保留/迷惑 {len(held)}件**" if held else "・保留/迷惑 0件"
        nrep = sum(1 for c in cs if c.get("reply"))
        # 2026-09-09 17:2x: **未返信の数**を出す（`yt._mark_answered` の註）。
        # 「返信 n件」だけでは、その問いに**こちらが答えたか**が読めない ——
        # この回は「30時間 放置」と読み違え、API を別に 1単位 撃って確かめた。
        nun = sum(1 for c in cs if not c.get("answered"))
        # **突き合わせのもう1方向**（`gone_comments` の註）。**立たない回は 1字も足さない。**
        _lrows = ledger_rows()
        gone = gone_comments(_lrows, cs)
        gmark = gone_status_mark(_lrows, gone)
        print(f"視聴者コメント: {len(cs)}件（台帳に無い新着 {len(fresh)}件{note}{gmark}"
              + (f"・うちスレッドの返信 {nrep}件" if nrep else "")
              + f"・**未返信 {nun}件**" + "）")
        # 新着は必ず出す（3件で切って隠さない）。2026-09-09 04:2x: 返信を引くようにしたので、
        # いちばん濃い反応（会話の続き）がここに来る。
        for c in comments_to_show(cs, fresh):
            mark = "★新" if c["id"] in {f["id"] for f in fresh} else "  "
            st = "" if c.get("status", "published") == "published" else f"[{c['status']}]"
            arrow = "↳" if c.get("reply") else " "
            ans = f"[返信ずみ {c['answered_at'][:16]}]" if c.get("answered") else "[未返信]"
            print(f"  {mark}{st}{arrow} {c['at'][:16]} {c['video_id']} {ans} {c['author']}: "
                  + comment_line_text(c["text"]))
    except Exception as e:  # noqa: BLE001
        print("視聴者コメントは引けなかった:", str(e)[:100])
    print("台帳 直近 5行:")
    for r in ledger_rows()[-5:]:
        print("  " + json.dumps(r, ensure_ascii=False)[:160])


def loop_stale(vid: str, sig: str, rows=None) -> str:
    """**輪（§4 (1)）の答えが、いまの本文のものか**（2026-09-11 12:3x・hourly・Opus）。
    返すのは印字する1行（古くなければ空）。derivation と覆る条件は `script.Script.loop_sig` の註。

    **印字は註より先に目に入ります**（§5 の教訓 7つ目）ので、ここで言うのは
    **次の1手だけ**にします —— 「read → critique を撃ち直す」。字数や秒数には触れません
    （それは別の門で、混ぜると書き手はどちらに従うか分かりません ＝ §3 の 9 の「年に」の族）。"""
    rows = ledger_rows() if rows is None else rows
    last = None
    for r in rows:
        if r.get("id") == vid and r.get("event") in ("cold_read", "critique"):
            last = r
    if last is None:
        return ""
    old = last.get("sig")
    if old is None:       # 指紋を書く前の回の行 —— 古いかどうかを言えないので、黙る（嘘より安い）
        return ""
    if old == sig:
        return ""
    return (f"輪は古い本文で閉じています（{last['event']} {last.get('at', '?')[:16]} は指紋 {old}・"
            f"いまは {sig}）＝ **read → critique を撃ち直すこと**（§4 (1)「直す → 最初から評価し直す」）")


def cmd_lint(a):
    s = script.load(a.id)
    ps = s.problems()
    print(f"{s.id}: {len(s.segments)}コマ・{s.total_chars()}字")
    for p in ps:
        print("  [!]", p)
    for w in s.warnings():
        print("  [?]", w)
    stale = loop_stale(s.id, s.loop_sig())
    if stale:
        print("  [?]", stale)
    return 1 if ps else 0


def cmd_build(a):
    s = script.load(a.id)
    ps = s.problems()
    if ps:
        print("台本の形が通らない:", *ps, sep="\n  ")
        return 1
    for w in s.warnings():
        print("  [?]", w)
    # **ここが、11:0x の回が見ていたはずの所**（§4 (1) の順）—— 直したあとに必ず通るのは build で、
    # lint は通らない回がある（この回の 11:0x は build → hear → sheet → crosscheck だけ撃った）。
    stale = loop_stale(s.id, s.loop_sig())
    if stale:
        print("  [?]", stale)
    img = image_for(a.id)
    r = render.build(s, img)
    print(f"mp4: {r['mp4']}  {r['total']:.1f}秒  背景: {img.name if img else '無し（単色）'}")
    print("コマの秒数:", " ".join(f"{d:.1f}" for d in r["durations"]))
    print(f"目で見る: {r['sheet']}")
    ok = r["total"] <= MAX_SECONDS
    if not ok:
        print(f"  [!] {r['total']:.1f}秒 > {MAX_SECONDS}秒。say を削ること")
    ledger("built", a.id, seconds=round(r["total"], 1), image=bool(img), chars=s.total_chars(),
           scenes=[round(d, 1) for d in r["durations"]])   # 同じ本文でも焼くたびに ±3% 揺れる（09/06 22:1x 実測）。コマ単位で比べるため
    return 0 if ok else 1


def cmd_hear(a):
    s = script.load(a.id)
    d = workdir(a.id)
    from .tts import synth_script
    wavs = [w for w, _ in synth_script(s, d)]
    rows = hear.check(s, wavs, "medium" if a.medium else "small")
    bad = [r for r in rows if r["diffs"]]
    for r in rows:
        mark = "OK " if not r["diffs"] else "!! "
        print(f"{mark}コマ{r['i']} ({r['how']}): {r['heard']}")
        if r["diffs"]:
            print(f"      台本: {r['say']}")
            print(f"      予定: {r['exp']}")
            print(f"      音  : {r['got']}")
            for e, g in r["diffs"]:
                print(f"      予定「{e}」 聞こえた「{g}」")
            t = r.get("tail")
            if t:   # 末尾が丸ごと無い型。末尾 5秒 だけを聞き直した答え（studio/hear.tail_probe の註）
                print(f"      末尾5秒: {t['heard']}")
                print("      → 音には在る（whisper が長いコマの末尾を切り落とした側）。通してよいかを決めるのは Fable"
                      if t["ok"] else
                      f"      → 末尾を聞き直しても差が残る: {t['diffs']}")
            rt = r.get("rate")
            if rt:   # 秒数の側（studio/hear.tail_rate）。聞き取りとは別の物を見る second opinion
                print(f"      秒数: {rt['rate']} 字/秒（この本の帯 {rt['band'][0]}〜{rt['band'][1]}）・"
                      f"末尾が音に無いなら {rt['without']} 字/秒")
                print("      → 秒数の側は「音には在る」（末尾を落とすと帯の外）。"
                      "**`tail_probe` と食い違うときは、両方を並べて Fable が決める**"
                      if rt["present"] else
                      "      → 秒数の側でも末尾が無い側に付く（TTS を疑う根拠が2つ）")
            v = r.get("voice")
            if v:   # 音の側（studio/hear.tail_voice）。**聞き取りを通らない片側**を持つ 3つ目
                print(f"      音の終わり {v['energy_end']}秒 − 聞き取りが止まった {v['word_end']}秒 "
                      f"＝ {v['gap']}秒 → {v['verdict']}")
                if v["verdict"] == "音は在る":
                    print("      → 切ったのは whisper（この 3つ目だけが音そのものを見ます・hear.tail_voice の註）")
                elif v["verdict"] == "分けられない":
                    print("      → 5モーラ 未満の差は、この手では分けません（在るほうへ丸めないこと）")
    print(f"一致 {len(rows) - len(bad)}/{len(rows)}")
    if bad:
        print("差の読み方: TTS の誤読なら yomi か言い換え（yomi は効かない語がある → 直したら hear をやり直す）。"
              "whisper の聞き違い（ねんきん→めんきん・4がつ→4かつ 型）なら通してよい。決めるのは Fable。")
    ledger("heard", a.id, mismatched=len(bad), model="medium" if a.medium else "small", mode="kana",
           diffs=[{"i": r["i"], "d": r["diffs"]} for r in bad],
           escalated=[r["i"] for r in rows if "→" in r["how"]],   # small で差が出て medium が予定どおりに聞いたコマ
           tail={str(r["i"]): r["tail"]["ok"] for r in rows if r.get("tail")},   # 末尾が丸ごと無いコマ → 末尾5秒に在ったか（hear.tail_probe の覆る条件を数えるため）
           voice={str(r["i"]): r["voice"]["verdict"] for r in rows if r.get("voice")},   # 音の側の答え（hear.tail_voice の覆る条件「3本 続けて当たったら寄せる」を数えるため）
           how=hear.escalations(rows))   # どの段で通ったか（medium／medium+prompt）。§7 の「prompt の段が採られたか」を台帳で数えるため
    return 1 if bad else 0


def cmd_read(a):
    s = script.load(a.id)
    r = critic.cold_read(s)
    print("正解 :", s.takeaway)
    print("言い返し:", r.get("takeaway"))
    for u in r.get("unclear") or []:
        print("  分からない:", u)
    ledger("cold_read", a.id, takeaway=r.get("takeaway"), unclear=r.get("unclear"), sig=s.loop_sig())
    return 0


def cmd_critique(a):
    s = script.load(a.id)
    c = critic.critique(s)
    print("理解度:", c.get("understand"), "/5 ", "言い返し:", c.get("takeaway"))
    for it in c.get("items") or []:
        print(f"  [{it.get('severity')}] {it.get('where')}: {it.get('why')}\n        → {it.get('fix')}")
    done = critic.loop_done(c)
    print("輪:", "閉じてよい（1番目が言いがかり）" if done else "まだ（1番目が real）")
    ledger("critique", a.id, understand=c.get("understand"), n_real=sum(1 for i in c.get("items") or [] if i.get("severity") == "real"), done=done, sig=s.loop_sig())
    return 0 if done else 1


def cmd_crosscheck(a):
    """§4 (0)。critique は say/show/sub しか読まないので、声が説明欄・notes と割れていても素通りする
    （実測 2回: 09/07 05:4x は説明欄の側が誤り・09/08 02:5x は声の側が誤り）。ここはその1点だけを見る。"""
    s = script.load(a.id)
    c = critic.crosscheck(s)
    items = c.get("items") or []
    for it in items:
        print(f"  [{it.get('kind')}] {it.get('where')}")
        print(f"        声  : {it.get('say')}")
        print(f"        文書: {it.get('doc')}")
        print(f"        → {it.get('why')}")
    print("食い違い:", len(items), "件" if items else "件（無し）")
    ledger("crosscheck", a.id, n=len(items), kinds=[it.get("kind") for it in items])
    return 0 if not items else 1


def cmd_order_image(a):
    s = script.load(a.id)
    ORDERS.mkdir(parents=True, exist_ok=True)
    oid = f"{a.id}-bg"
    p = ORDERS / f"{oid}.json"
    if p.exists():
        print("注文ずみ:", p, json.loads(p.read_text(encoding="utf-8")).get("status"))
        return 0
    order = {"id": oid, "asked_at": now_jst().isoformat(timespec="seconds"),
             "for": f"{s.date} の本（{s.id}）の背景",
             "prompt": s.image_prompt or "落ち着いた紺色の背景に、机の上の書類と電卓。写実的。文字は入れない。",
             "avoid": "文字・ロゴ・実在の人物・透かし", "size": "1080x1920", "format": "jpg",
             "out": f"assets/images/{oid}.jpg", "status": "pending"}
    p.write_text(json.dumps(order, ensure_ascii=False, indent=1), encoding="utf-8")
    print("注文を置いた:", p, "（外の毎時セッションが焼く。届いたら build し直す）")
    ledger("image_ordered", a.id, order=oid)
    return 0


def cmd_schedule(a):
    s = script.load(a.id)
    mp4 = workdir(a.id) / f"{a.id}.mp4"
    if not mp4.exists():
        print("mp4 が無い。先に build")
        return 1
    hh, mm = map(int, a.at.split(":"))
    at = now_jst().replace(hour=hh, minute=mm, second=0, microsecond=0)
    if at.date() != now_jst().date():
        print("当日以外には予約しない")
        return 1
    if at <= now_jst() + dt.timedelta(minutes=5):
        print(f"{a.at} はもう過ぎている（いま {now_jst():%H:%M}）。--at を後ろへ")
        return 1
    lineup = yt.today_lineup()
    others = [v for v in lineup if v["id"] != a.replace]
    if others and not a.force:
        print("きょうの枠にはもう本がある（1日1本）。差し替えなら --replace <videoId>:")
        for v in others:
            print(f"  {yt.when(v):%H:%M} {v['privacy']} {v['id']} {v['title'][:40]}")
        return 1
    if a.dry_run:
        print(f"[dry-run] 上げる: {mp4.name} → 公開 {at:%m/%d %H:%M} JST・差し替え {a.replace or '無し'}・題「{s.title}」")
        return 0
    vid = yt.upload(mp4, s.title, s.description, s.tags, at)
    print("上げた:", vid, f"公開 {at:%m/%d %H:%M} JST")
    first = workdir(a.id) / "slide-01.png"
    try:
        yt.set_thumbnail(vid, first)
    except Exception as e:  # noqa: BLE001
        print("サムネは付かなかった:", str(e)[:120])
    if a.replace:
        yt.make_private(a.replace)
        print("差し替え: 前の", a.replace, "を private に戻した（消していない）")
    # 公開の時刻は publish_at（"at" は「いつやったか」。unscheduled の was_at と同じ向き）
    ledger("scheduled", a.id, video_id=vid, publish_at=at.isoformat(timespec="minutes"), replaced=a.replace or None,
           title=s.title)
    return 0


# 台帳に載せる本の齢の上限（時間）。§1 は「48時間でほぼ止まる」だが、同じ日に出た本どうしを
# 並べるには数日ぶん要る（§7 の判定）。**上げた順の先頭 N本 で選ばないこと** —— 2026-09-07 16:4x に
# それで 09/05〜09/07 に公開された旧作りの本 14本 を 1行も台帳に書いていなかった（`yt.all_videos` の註）。
MEASURE_WITHIN_H = 24 * 7

# **落ち着かせる本は「齢」ではなく「1回の束に入るか」で決める**（2026-09-10 06:3x・optimizer・Opus
# が広げた）。もとは「齢 48h まで」で、その註は **覆る条件**に「48h を越えた本で `n_values > 1` の
# 行が出たら、ここを伸ばす」と書いていました。**その条件は、この門が在るかぎり永久に引かれません**
# ——48h を越えた本は `settle_stats` に1度も渡らないので、`n_values` の欄そのものが作られない。
# §4 (0-b) の「0件 を『大丈夫』と読まないこと」と同じ族で、**見えない側を「差が無い」と読む**形でした。
#
# **広げても単位は増えません**（この回に撃って確かめた）: `settle_stats` は ID を **50件ずつ**
# 束ねて `videos.list` を撃つので、**1件 でも 50件 でも 1回の読みは 1単位**です。
#
#     ids=1 → 3回 ／ ids=2 → 3回 ／ ids=19 → 3回 ／ ids=50 → 3回 ／ ids=51 → 6回（reads=3）
#
# ＝ いま測る 19本 を全部 渡しても **3単位のまま**（前と同じ）。旧註の「対象を全部に広げると
# 単位が増える」（検査 `test_読み直しは齢の浅い本だけ` の陽性対照の文）は、**束ねを数えていなかった**。
#
# **なぜ齢で切ってはいけないか**: 揺れるのは**伸びている本**で（`yt.settle_stats` の実測）、
# 齢はその代理でしかありません。**伸びたまま 48h を越える本**は、代理が外れる当のものです ——
# 実測 2026-09-10 06:1x: `lQHX9LJ80Sg` は齢 **44.2h でまだ +2回/0.7h** で伸びており、
# **48h を越えるのは 09/10 10:02 JST**。§7 の「次に見る所 (a)」が読もうとしているのは、
# まさにその 48h の点です。旧の門では、その点だけが読み直されない生の1点になり、
# 遅れている複製を引くと（実測 最大 -249回 ＝ -28%）包絡が上がらないので **「平ら」と出ます**
# ——止まっていなくても。**判定の刻に、いちばん外れやすい点を素で読む形**でした。
SETTLE_WITHIN_H = 48
#: **1回の読みで束ねられる ID の数**（`videos.list` の上限）。ここまでは齢で絞らない。
SETTLE_MAX_IDS = 50


def cmd_measure(a):
    # **この測りが2点組に入るかを、撃つ前に言う**（2026-09-10 02:2x・optimizer・Opus。
    # `trend.pair_gap` の註 —— この回に、前の周の測りの 7.1分 後に測って分母を動かせなかった）。
    print(trend.pair_gap_line(ledger_rows()))
    pub = yt.published(MEASURE_WITHIN_H)
    # **測る本は、読み直して落ち着かせてから台帳へ**（2026-09-09 19:1x・optimizer・Opus。
    # **09/10 06:3x に「齢が浅い本は」から広げた** —— 上の `SETTLE_MAX_IDS` の註）。
    # `videos.list` は伸びている本を、遅れの違う複数の複製から返す（`yt.settle_stats` の註と実測）。
    # 1回の読み直しは **1単位**（`all_videos()` の約 32単位 に対して 2単位 増える）。
    # 束に入るなら**全部**（単位は同じ・上の註）。入らない回だけ齢で絞る。
    young = [v["id"] for v in pub]
    if len(young) > SETTLE_MAX_IDS:
        young = [v["id"] for v in pub
                 if (now_jst() - yt.when(v)).total_seconds() / 3600 <= SETTLE_WITHIN_H]
    settled = yt.settle_stats(young) if young else {}
    ages = {v["id"]: (now_jst() - yt.when(v)).total_seconds() / 3600 for v in pub}
    for v in pub:
        age = ages[v["id"]]
        s = settled.get(v["id"])
        extra = {}
        if s:
            # 遅れている複製を読んだ回に「減った」と書かせないため、**最大**を採る。
            # 揺れた回だけ `views_min`（その時刻の本物の下限）を残す
            # —— §7 が「下限」で比べるときに使う数はこちら。
            #
            # **`n_values` は、読んだ行に必ず書く**（2026-09-10 07:0x・optimizer・Opus）。
            # もとは「揺れた回だけ」で、**読んで揺れなかった行と、1度も読まれていない行が
            # 台帳の上で同じ形**でした（どちらも欄が無い）。§7 の (h)
            # 「48h を越えた本で `n_values > 1` の行が出るか・3本 続けて 0件 なら
            # 落ち着いていると数えてよい」は、**その 0件 の分母を台帳から数えられません**
            # ——06:3x が門を齢から束へ移したのは、まさに「渡っていない本を『差が無い』と
            # 読む形」を外すためで、**分子だけ直して分母を見えないままにしていました**。
            # `n_values: 1` が在る行 ＝ **読んだ上で揺れなかった**。欄が無い行 ＝ **読んでいない**
            # （束 50件 を越えて齢で絞られた回・`published` の窓の外）。
            # **覆る条件**: 台帳の1行が重くて困る回が来たら、`n_values: 1` は落として
            # 代わりに `measured` とは別の1行（その回に読んだ ID の数）にすること。
            extra = {"n_values": s["n_values"]}
            if s["n_values"] > 1:
                extra["views_min"] = s["views_min"]
            v = {**v, "views": max(v["views"], s["views"]),
                 "views_absent": v.get("views_absent") or s.get("views_absent")}
        # **`viewCount` の欄が無い読みは、0回 とは別に印を立てる**（`yt.views_of` の註・
        # 2026-09-10 14:2x）。行は落としません —— 落とすと分母が黙って減り、
        # 「読んでいない本」と「0回 の本」がまた同じ形になります。
        if v.get("views_absent"):
            extra["views_absent"] = True
        ledger("measured", v["id"], views=v["views"], likes=v["likes"],
               comments=v.get("comments", 0), age_h=round(age, 1), title=v["title"][:40], **extra)
    # **まだ公開前の本も1行 残す**（API は増えない ＝ `all_videos()` は同じ回で1度きり）。
    # 09/08 23:0x: 旧作りの `Yy7GmcGoQ6I` が「きょう 23:00」の予約のまま待っていたのに、
    # 台帳には 1行 も無く、`trend` の日の見出しは 22時間「09/08（1本）」だった
    # → §7 が 5回 続けて「1本 だけの日」と書いた（`studio/trend.pending` の註）。
    sch = yt.scheduled_all()
    for v in sch:
        ledger("pending", v["id"], publish_at=yt.when(v).isoformat(), title=v["title"][:40])
    print("記した:", len(pub), f"本（公開から {MEASURE_WITHIN_H / 24:.0f}日 以内）"
          + (f"・予約 {len(sch)}本" if sch else "・予約 0本"))
    # **読み直した本数を、その回に言う**（2026-09-10 07:0x・optimizer・Opus。上の `n_values` の註）。
    # §7 の (h) を読む回が、**撃つだけで分母と分子を読めるようにする**ため
    # （`wake_placed` を毎周 台帳へ書き写したのと同じ形・§7 (d)）。
    #
    # **札を直した**（2026-09-10 09:2x・optimizer・Opus）: 07:0x はこの数を
    # 「**§7 (h) の分母と分子**」と呼びましたが、**08:0x に (h) の道は移りました** ——
    # 数え直しは**周と周のあいだ**に起き、同じ周の 3回 読みは 3回 とも新しい値を返すので、
    # **数え直しはこの道では見えません**（いっぽう `trend.recounts` には 5本 出ている）。
    # **札がそのままだと、次の回はここを読んで「数え直しは 0件」と書きます**
    # （道具が古い道を指し続ける ＝ この回に `gate_side` で直したのと同じ族）。
    #
    # **【2026-09-10 10:2x・optimizer・Opus】09:2x の「`n_values` は必ず 1・48h 超は 0行」は、
    # この回に外れました** —— `EkNqtkK49Bw`（齢 96.3h）が **142 対 141** で割れ、
    # 09:2x の札は (h) の**覆る条件 (3)**（「48h 超で 1度でも出たら第3の口」）を名乗っていたので、
    # そのままなら次の回は「第3の口が出た → 中央値へ」と読みます。**それは悪化します** ——
    # 低いほう 141 は **41分 前の台帳の行の値そのもの**で、本は 140 → 141 → 142 と伸びており、
    # 中央値はいちばん新しい値を捨てる（伸び中の本では 192〜249回）。
    # **齢 48h 超は「落ち着いた」ではない**（96.3h の本がこの周に伸びた）。
    # 分子は `trend.shakes`（推定が動かなかった周の数で分ける）で数えること。
    if settled:
        over = [i for i in settled if ages.get(i, 0) > SETTLE_WITHIN_H]
        shook = sorted(i for i, s in settled.items() if s["n_values"] > 1)
        old_shook = sorted(i for i in shook if ages.get(i, 0) > SETTLE_WITHIN_H)
        print(f"落ち着かせた: {len(settled)}本（うち齢 {SETTLE_WITHIN_H}h 超 **{len(over)}本**）"
              f"・揺れた **{len(shook)}本**" + (f"（{'・'.join(shook)}）" if shook else "")
              + f"・うち齢 {SETTLE_WITHIN_H}h 超 **{len(old_shook)}本**"
              + "。**この「齢 48h 超」を (3) の分子として読まないこと**（2026-09-10 10:2x に直した札）"
              + " —— 齢 48h 超で割れた 1本目（`EkNqtkK49Bw` 96.3h・142 対 141）は、"
              + "**低いほうが 41分 前の台帳の行の値そのもの ＝ 遅れた複製**でした"
              + "（本は 140 → 141 → 142 と伸びている）。**齢 48h 超は「落ち着いた」ではありません。**"
              + " §7 (h) の**覆る条件 (3)** の分子は `trend` の「割れた読み」の行"
              + "（`trend.shakes`。**推定が動かなかった周の数**で分ける）で見ること。"
              + "**数え直しはどちらでもなく `trend.recounts` の行です**")
    return 0


def gone_comments(rows: list[dict], live: list[dict]) -> list[dict]:
    """**台帳に在るのに、いま API から返ってこない視聴者コメント**を挙げる
    （2026-09-10 16:0x・optimizer・Opus。**追加 0単位** ＝ すでに引いてある `live` と台帳を突き合わせるだけ）。

    **穴**: `status` も `comments` も、突き合わせを **1方向しか** していませんでした ——
    「**台帳に無い新着**」は数えるのに、その裏（**台帳に在ったのに消えた**）を数える口が無い。
    ＝ §4 (0-b) の族（**0件 を「大丈夫」と読む**）の 5つ目の型: **「新着 0件・保留/迷惑 0件」は
    「何も起きていない」と読めますが、消えた側はその 2つ のどちらにも出ません。**

    **引いた実測（この回・0単位）**: `@sakimura5257` の
    **`Ugy3gdkwxAy5P3Nw_fd4AaABAg`「コメントしたのに消えた」**（`lQHX9LJ80Sg`・09/08 03:39Z 投稿）は
    **09/08 15:03 と 15:05 の 2回、台帳に `viewer_comment` として記録されている**のに、
    この回の `comments`（**チャンネル全部・published/heldForReview/likelySpam の 3列**）には
    **在りません**。同じ人の同じ本への別のコメントは 3件 とも返っています。
    ＝ **「コメントしたのに消えた」と書いたその人のコメントが、実際に消えました。**
    こちらの保留にも迷惑にも入っていない（`comments` の最後の行が 0件）ので、
    **消したのは投稿者自身か YouTube 側**で、**Data API ではどちらかを分けられません**
    （分けたいなら Studio の側。ここでは**数だけ**残します）。

    **なぜ数えるか**: コメントは likes より先に動く反応（`yt.viewer_comments` の註）で、
    **消えたコメントは「反応が無かった」と同じ顔をします**。投稿が消える人は次を書きません。

    `live` は `yt.viewer_comments()` の返り（**チャンネル全部を1度に引く**ので、
    本ごとの窓では落ちません ＝ 返ってこない ＝ 3列 のどこにも無い）。
    """
    live_ids = {c["id"] for c in live}
    out, seen = [], set()
    for r in rows:
        if r.get("event") != "viewer_comment":
            continue
        cid = r.get("comment_id")
        if not cid or cid in live_ids or cid in seen:
            continue
        seen.add(cid)
        out.append(r)
    return out


def gone_unlogged(rows: list[dict], gone: list[dict]) -> list[dict]:
    """消えたコメントのうち、**台帳の `comment_gone` にまだ無いもの**（2026-09-10 18:3x・optimizer・Opus）。

    **穴**: `gone_comments` は台帳の `viewer_comment` と いまの API を比べるので、
    **1度 消えたコメントは、以後ずっと「消えている」**。`cmd_status` はそれを毎周
    「!! 消えた N件（`comments` を撃つこと）」と印字していました ——
    **`cmd_comments` が 15:35 に `comment_gone` を台帳へ書いたあとも、同じ命令を出し続けます。**
    実測: この行が立ってから 09/10 18:0x の回まで、**中身は同じ 1件**（`Ugy3gdkwxAy5P3Nw_fd4AaABAg`）で、
    18:0x の回はその命令に従って `comments` を **1単位** 撃ち、**台帳に既に在る事実**を読み直しました。

    ＝ **「毎周 印字して捨てる」の裏返し**（`cli.record_channel` の族）: 台帳には残っているのに、
    印字の側が台帳を見ないので、**済んだ仕事の命令が消えません**。
    **数は残す**（§7 (n) は件数で数える）・**命令は未記録のぶんにだけ出す**。

    **覆る条件**: (1) 消えたコメントが**戻ってくる**回が在ったら（API にまた出る）、
    `comment_gone` は「その時点で消えていた」印にすぎないので、戻りも台帳へ残すこと。
    (2) 未記録が 0件 の窓で、それでも `comments` を撃つ理由が出たら（新着・未返信の側）、
    それは**この行ではなく新着の行が言うこと**。
    """
    logged = {r.get("comment_id") for r in rows if r.get("event") == "comment_gone"}
    return [r for r in gone if r.get("comment_id") not in logged]


def gone_status_mark(rows: list[dict], gone: list[dict]) -> str:
    """`status` の1行に足す印。**未記録が在るときだけ「撃つこと」と言う**（`gone_unlogged` の註）。"""
    if not gone:
        return ""
    new = gone_unlogged(rows, gone)
    if new:
        return f"・!! **消えた {len(gone)}件**（うち未記録 {len(new)}件 ＝ `comments` を撃つこと）"
    return f"・消えた {len(gone)}件（**台帳に記録ずみ ＝ この行のために撃たなくてよい**）"


def gone_comments_line(rows: list[dict], live: list[dict]) -> str:
    """`gone_comments` を1行にする。**0件 でも印字すること**（`comments` の保留/迷惑の行と同じ理由）。"""
    gone = gone_comments(rows, live)
    if not gone:
        return "   消えたコメント **0件**（台帳の `viewer_comment` は全部 いま API から返っています）"
    body = f"   !! **消えたコメント {len(gone)}件**（台帳に在るのに、いま API の 3列 のどこにも無い）"
    for r in gone:
        body += (f"\n      {str(r.get('posted_at'))[:16]} {r.get('id')} {r.get('author')}: "
                 + comment_line_text(str(r.get("text", "")), 60))
    return body + ("\n      **「反応が無かった」と読まないこと** —— 消したのは投稿者自身か YouTube 側で、"
                   "Data API では分けられません（`gone_comments` の註）")


def cmd_comments(a):
    """視聴者が書いたコメントを全部 出し、台帳にまだ無いものを `viewer_comment` として1行 足す。

    **コメントは「押された数」に出ない唯一の文の反応**（`yt.viewer_comments()` の註）。
    台帳へ書くのは、次の回が「もう読んだ／新着」を見分けられるようにするため
    （読んだ回が居なくなっても、台帳に残る）。
    """
    cs = yt.viewer_comments()
    seen = {r.get("comment_id") for r in ledger_rows() if r.get("event") == "viewer_comment"}
    if not cs:
        print("視聴者コメントは 0件")
        return 0
    for c in cs:
        new = c["id"] not in seen
        st = c.get("status", "published")
        # 返信は「スレッドの続き」と分かる形で出す（`parent_id` が返信先 ＝ `cli reply` が撃つ先）。
        head = f"↳返信 親 {c['parent_id']}" if c.get("reply") else c["video_id"]
        # **答えたか**は台帳では埋まらない（`cli reply` を通らない返信が在る）。`yt._mark_answered` の註。
        ans = f"返信ずみ {c['answered_at'][:16]}" if c.get("answered") else "**未返信**"
        print(f"{'★新着' if new else '     '} {c['at'][:16]} {head} いいね{c['likes']} {ans} "
              f"{'' if st == 'published' else '[' + st + '] '}{c['author']}\n       "
              + comment_line_text(c["text"], 400, one_line=False))
        if new:
            ledger("viewer_comment", c["video_id"], comment_id=c["id"], author=c["author"],
                   posted_at=c["at"], status=st, parent_id=c.get("parent_id", c["id"]),
                   reply=bool(c.get("reply")), text=c["text"][:500])
    held = [c for c in cs if c.get("status", "published") != "published"]
    print(f"—— {len(cs)}件（うち台帳に無かった新着 {sum(1 for c in cs if c['id'] not in seen)}件"
          f"・**未返信 {sum(1 for c in cs if not c.get('answered'))}件**）")
    # 保留・迷惑の列は 2026-09-08 15:0x まで1度も引かれていなかった（`yt.viewer_comments()` の註）。
    # **0件 でも印字すること** —— 「消えた」と言われたときに、こちらが握り潰したかどうかは
    # この行が 0 かどうかでしか答えられない。
    print(f"   保留 heldForReview {sum(1 for c in held if c['status'] == 'heldForReview')}件"
          f"・迷惑 likelySpam {sum(1 for c in held if c['status'] == 'likelySpam')}件"
          + ("（＝ こちらが止めているコメントは無い）" if not held else "（**読むこと**）"))
    # **突き合わせのもう1方向**（`gone_comments` の註。**追加 0単位**）。
    rows = ledger_rows()
    print(gone_comments_line(rows, cs))
    # 印字だけにしないこと（`cli.record_channel` の註と同じ族）—— 消えた事実を台帳に1度だけ残す。
    logged = {r.get("comment_id") for r in rows if r.get("event") == "comment_gone"}
    for r in gone_comments(rows, cs):
        if r.get("comment_id") not in logged:
            ledger("comment_gone", r.get("id"), comment_id=r.get("comment_id"),
                   author=r.get("author"), posted_at=r.get("posted_at"),
                   text=str(r.get("text", ""))[:200])
    return 0


def cmd_reply(a):
    """視聴者のコメント1件に、手で書いた返信を1つ付ける（`yt.reply()`・50単位）。

    門: (1) `comment_id` が台帳の `viewer_comment` に在ること（自分のコメントや存在しない ID には撃たない）
        (2) 同じ `comment_id` に同じ文の `replied` が無いこと（同じ文を2度 撃たない。別の文 ＝ 次の問いへの答えは通す）
        (3) 文が空でないこと。`--dry-run` は文を印字するだけ。
        (4) 人間だと名乗らない・AI を否定しない（`script.AI_DENIAL`・`script.HUMAN_CLAIM`）。
            オーナー 09/08 21:4x「AIですかって聞かれたら何で答えるの？」→ 答えは「はい」（`data/studio/replies/ai-desu.txt`）。
    通れば台帳に `replied`（comment_id・text）を1行。背景から呼ぶ口は無い（人が文を書いて撃つだけ）。
    """
    text = (a.text or "").strip()
    if not text:
        print("--text が空")
        return 1
    m = script.AI_DENIAL.search(text) or script.HUMAN_CLAIM.search(text)
    if m:
        print(f"「{m.group()}」— 人間だと名乗る・AI を否定する文は撃たない。AIかと聞かれたら「はい」（data/studio/replies/ai-desu.txt）")
        return 1
    rows = ledger_rows()
    src = next((r for r in rows if r.get("event") == "viewer_comment" and r.get("comment_id") == a.comment_id), None)
    if src is None:
        print("台帳の viewer_comment に無い ID。先に `comments` を撃つ")
        return 1
    # 門 (2) は「同じスレッドに同じ文を2度」だけ止める（2026-09-08 20:3x・hourly・Fable に緩めた）。
    # 会話は同じスレッドに続く —— 実測: 1問目の返信（17:10・オーナーの手）に視聴者が 18:41 に2問目を返し、
    # 2つ目の返信が要った。「同じ ID に2度 撃たない」のままだと、台帳に `replied` が1行 在るだけで 3問目に答えられない。
    # **撃つ先はスレッド ID**（`parentId` に返信の ID は渡せない）。台帳の行が返信なら親へ向け直す。
    # 2026-09-09 04:2x: `viewer_comments()` が返信も返すようになり、`--comment-id` に返信の ID が
    # 渡りうるようになった（それまでは最上位しか台帳に無かったので、必ず自分自身が親だった）。
    parent = src.get("parent_id") or a.comment_id
    threads = {r.get("comment_id") for r in rows
               if r.get("event") == "viewer_comment" and (r.get("parent_id") or r.get("comment_id")) == parent}
    threads.add(parent)
    prev = [r for r in rows if r.get("event") == "replied" and r.get("comment_id") in threads]
    if any((r.get("text") or "").strip() == text[:1000].strip() for r in prev):
        print("同じ文をもう返信ずみ（台帳 replied）。2度は撃たない")
        return 1
    if prev:
        print(f"（このスレッドには台帳の返信が {len(prev)} 件 在る。別の文なので撃つ）")
    video_id = src.get("id", "")   # 台帳の行は本の ID を `id` に持つ（`common.ledger()` の骨）
    print(f"→ {video_id} {src.get('author')}「{(src.get('text') or '')[:60]}」")
    print("返信:", text)
    if a.dry_run:
        print("[dry-run] 撃っていない")
        return 0
    rid = yt.reply(parent, text)
    ledger("replied", video_id, comment_id=a.comment_id, parent_id=parent, reply_id=rid, text=text[:1000])
    print("返信した:", rid)
    return 0


def cmd_trend(a):
    # 1点で本を比べないための道具（studio/trend.py の註）。台帳しか読まないので API は 0単位。
    if a.by_day_count:
        # §7 の「日ごとの本数を軸に入れて数え直す」（15:0x/16:0x の覆る条件）。旧データも読む。
        for line in trend.by_day_count(ledger_rows()):
            print(line)
        return 0
    for line in trend.report(within_h=24 * a.days):
        print(line)
    return 0



ANALYTICS_MIN_H = 20.0   # このAPIは日ごとにしか動かない（遅れ 3日）＝ 1日に1回で足りる
CURVE_WINDOW_D = 18      # カーブの窓。**狭いと空で返る**（`analytics.curve` の註・実測）
ANALYTICS_WINDOW_D = 7   # 本ごとに引く窓（日）。**窓の中の数で、本の通算ではありません**


def analytics_recent_ids(rows: list[dict], within_h: float = 24 * 10,
                         now: dt.datetime | None = None) -> list[str]:
    """`measured` の刻から、直近に測った本の ID を新しい順に。

    **studio の本だけに絞りません** —— §7 の「90秒の上限」は
    **60秒以内の本（旧作り）と越えた本（新しい作り）を比べる**問いなので、
    分母から旧作りを落とすと**比べる相手が 0本 になります**（§7 が 4日間 そう書いていた当のもの）。
    """
    now = now or now_jst()
    seen: dict[str, dt.datetime] = {}
    for r in rows:
        if r.get("event") != "measured" or not r.get("id"):
            continue
        at = dt.datetime.fromisoformat(r["at"])
        if (now - at).total_seconds() / 3600 > within_h:
            continue
        seen[r["id"]] = max(seen.get(r["id"], at), at)
    return [vid for vid, _ in sorted(seen.items(), key=lambda kv: kv[1], reverse=True)]


def analytics_last_at(rows: list[dict]) -> dt.datetime | None:
    ats = [dt.datetime.fromisoformat(r["at"]) for r in rows
           if r.get("event") == "analytics_day"]
    return max(ats) if ats else None


def analytics_due(rows: list[dict], now: dt.datetime | None = None) -> bool:
    """撃つ回か。**このAPIは 1日 に1度しか新しい日を持ちません**（遅れ 3日・`analytics.py` の註）
    ので、毎周 撃つのは分母を増やさずクエリだけ使います。"""
    last = analytics_last_at(rows)
    if last is None:
        return True
    return ((now or now_jst()) - last).total_seconds() / 3600 >= ANALYTICS_MIN_H


def analytics_days_to_log(rows: list[dict], d: list[dict]) -> list[dict]:
    """**台帳へ足す日だけ**を返す ＝ 台帳に無い日と、**数が動いた日**（2026-09-11 07:1x・optimizer・Opus）。

    **前の形は「1件も通れない門」でした**（§5 の教訓の形4つ目・**台帳から列挙して見つけた**）:

        known = {r.get("day") for r in rows if r.get("event") == "analytics_day"}
        if r["day"] in known: continue

    行に `day` は在りません —— **日は `id` に入ります**（`common.ledger` が骨を `id` に置く）。
    ＝ `known` は必ず `{None}` で、**1件も skip しません**。
    実測: `analytics` を 3回 撃って `analytics_day` が **12 × 3 ＝ 36行**。
    `trend.analytics_line` は `{r["id"]: r}` で畳むので**印字は正しいまま**でした
    ＝ **数は壊れず、門だけが死んでいた**（この repo で 3例目 ——
    06:3x（`n_values`）・08:4x（`flats`）と同じ族）。

    **直す向きは「id で skip する」ではありません** —— Analytics は**遅れて入った日を
    後から書き直します**（遅れ 3日）。id で skip すると **最初に引いた（まだ埋まっていない）値が凍り**、
    `trend` は古い数を印字し続けます。
    **だから同じ数のときだけ落とし、動いた日は足します** ——
    そうすると **「その日がいつ書き直されたか」が台帳に残り**、次の回が遅れを数えられます。

    **覆る条件**: (1) 同じ日に 3行 以上 積む日が続いたら、Analytics の側が毎回 揺れている ＝
    `trend` の畳み（新しいほうを採る）が正しいかを、その日の並びで確かめること。
    (2) 台帳の `analytics_day` が窓（14日）の外まで伸びて重くなったら、**古い日だけ**を畳むこと
    （新しい 3日 は書き直されるので落とさない）。
    """
    last: dict[str, dict] = {}
    for r in rows:
        if r.get("event") == "analytics_day":
            last[r.get("id")] = r
    out = []
    for r in d:
        prev = last.get(r["day"])
        if (prev and prev.get("views") == int(r["views"])
                and prev.get("minutes") == int(r["estimatedMinutesWatched"])):
            continue                      # **同じ数** ＝ 足さない（門が本当に通る側）
        out.append(r)
    return out


def cmd_analytics(a):
    rows = ledger_rows()
    if not a.force and not analytics_due(rows):
        last = analytics_last_at(rows)
        print(f"きょうのぶんは引いてあります（前は {last:%m/%d %H:%M} JST・門 {ANALYTICS_MIN_H:.0f}時間）。"
              "**数は `trend` が毎周 印字します** ——引き直すなら `--force`")
        return 0
    d = analytics.daily(days=14)
    lag = analytics.lag_days(d)
    if not d:
        print("!! Analytics API が 1行 も返しませんでした ——**0 と読まないこと**（`analytics` の覆る条件 (2)）")
        return 1
    last_day = max(r["day"] for r in d)
    start = (dt.date.fromisoformat(last_day) - dt.timedelta(days=ANALYTICS_WINDOW_D)).isoformat()
    sids = studio_video_ids(rows)
    vids = analytics.per_video(analytics_recent_ids(rows), start, last_day)
    tr = analytics.traffic(start, last_day)
    print(f"Analytics（**Data API 0単位**・別枠のクエリ 3回）: 最後の日 {last_day}・**遅れ {lag}日**")
    for r in d[-5:]:
        print(f"  {r['day']}  再生 {int(r['views']):6d}・視聴 {int(r['estimatedMinutesWatched']):5d}分")
    print(f"本ごと（窓 {start}〜{last_day}・**窓の中の数** ＝ 本の通算ではありません）:")
    for r in vids:
        mark = "新" if r["video"] in sids else "旧"
        print(f"  {mark} {r['video']}  再生 {int(r['views']):5d}・平均 {int(r['averageViewDuration']):3d}秒"
              f"・平均視聴率 {r['averageViewPercentage']:5.2f}%・登録+{int(r['subscribersGained'])}"
              f"・いいね {int(r['likes'])}")
    tot = sum(int(r["views"]) for r in tr) or 1
    print("流入: " + " / ".join(f"{r['insightTrafficSourceType']} {int(r['views'])}"
                                f"（{int(r['views']) / tot * 100:.1f}%）" for r in tr if int(r["views"])))
    # **引いた数は台帳へ**（`cli.record_channel` の族 ＝ 印字して捨てない・JOURNAL 09/10 15:5x）。
    for r in analytics_days_to_log(rows, d):
        ledger("analytics_day", r["day"], views=int(r["views"]),
               minutes=int(r["estimatedMinutesWatched"]))
    for r in vids:
        ledger("analytics_video", r["video"], day=last_day, start=start, studio=r["video"] in sids,
               views=int(r["views"]), minutes=int(r["estimatedMinutesWatched"]),
               avg_seconds=int(r["averageViewDuration"]),
               avg_percent=round(float(r["averageViewPercentage"]), 2),
               subs_gained=int(r["subscribersGained"]), likes=int(r["likes"]))
    ledger("analytics_traffic", last_day, start=start, lag_days=lag,
           sources={r["insightTrafficSourceType"]: int(r["views"]) for r in tr})
    # **維持率カーブ**（どこで落ちるか。1本 1クエリ・`analytics.curve` の註）。
    # **窓はここで広く取ること** —— 狭い窓は、データが在っても空で返ります（実測）。
    cstart = (dt.date.fromisoformat(last_day) - dt.timedelta(days=CURVE_WINDOW_D)).isoformat()
    # **新しい作りを先に取る** —— 上限で切ると、再生の多い旧作りだけが残り、
    # 比べたい側（studio の本）が 1本 しか入りませんでした（この回に踏んだ）。
    ok = [r for r in vids if int(r["views"]) >= analytics.CURVE_MIN_VIEWS]
    picked = ([r for r in ok if r["video"] in sids]
              + [r for r in ok if r["video"] not in sids])[:analytics.CURVE_MAX]
    if picked:
        print(f"維持率カーブ（窓 {cstart}〜{last_day}・**残っている率**・"
              f"`audienceWatchRatio`。1.00 より上は見直し）:")
    for r in picked:
        # **1本 の 500 で、残りのカーブを落とさないこと**（この回に `9zkfjEH48PY` で実測）。
        # **エラーと空は別**（`analytics.curve` の覆る条件 (2)）—— `marks: None` にせず、
        # `error` を残して次の回が数えられるようにする。
        try:
            mk = analytics.curve_marks(analytics.curve(r["video"], cstart, last_day))
        except Exception as e:  # noqa: BLE001
            print(f"  !! {r['video']} カーブが引けなかった: {str(e)[:80]}"
                  "（**空とは別**・`analytics.curve` の覆る条件 (2)）")
            ledger("analytics_curve", r["video"], day=last_day, start=cstart,
                   studio=r["video"] in sids, views=int(r["views"]), marks=None,
                   error=str(e)[:200])
            continue
        mark = "新" if r["video"] in sids else "旧"
        if mk is None:
            print(f"  {mark} {r['video']}  **空**（覆る条件 (1)（齢）を見ること・`analytics.curve` の註）")
            ledger("analytics_curve", r["video"], day=last_day, start=cstart,
                   studio=r["video"] in sids, views=int(r["views"]), marks=None)
            continue
        print(f"  {mark} {r['video']}  " + " ".join(f"{k[1:]}% {v:.2f}" for k, v in mk.items()))
        ledger("analytics_curve", r["video"], day=last_day, start=cstart,
               studio=r["video"] in sids, views=int(r["views"]), marks=mk)
    return 0


def cmd_reporting(a):
    """**一括レポート（Reporting API・3つ目の枠・Data API 0単位）を取り込む。**

    2026-09-10 18:0x・optimizer・Opus。**Analytics より 2日 早い口**（`studio/reporting.py` の註）。
    `--setup` はジョブが無いときだけ作る（作ってから最初の CSV まで 24〜48時間・遡りは 30日）。

    **台帳へ残すのは 型ごとに 1行**（`event: "reported"`）——
    行そのものは 型ごとの store（数千行 になるので台帳には混ぜない）。

    **【2026-09-10 23:5x・optimizer・Opus】型を 1つ しか見ていませんでした。**
    18:0x のこの関数は `reporting.REPORT_TYPE`（`channel_basic_a3`）だけを見ており、
    同じ口に **2026-08-14 から回っている `channel_reach_basic_a1`** が在ることを知りませんでした。
    その結果、**すでに置かれていた 8日ぶん（09/02〜09/09）が道具から 1行 も見えず**、
    「報告 0本」という印字だけが残っていました（**その 0 は a3 の話でしかありません**）。
    いまは `reporting.JOBS` の並びを回ります。**1つの型へ戻さないこと。**
    """
    js = reporting.jobs()
    rc = 0
    for rtype, store in reporting.JOBS:
        rc |= _reporting_one(a, js, rtype, store)
    return rc


def _reporting_one(a, js: list, rtype: str, store) -> int:
    job = reporting.job_for(rtype, js)
    if job is None:
        if not a.setup:
            print(f"!! `{rtype}` のジョブが在りません ——"
                  " `python -m studio.cli reporting --setup` で作ること（作るのは1回だけ）")
            return 1
        job = reporting.create_job(rtype)
        print(f"ジョブを作りました: {job['id']}（{job.get('createTime')}）"
              " —— **最初の CSV は 24〜48時間後**・遡りは 30日")
    reps = reporting.reports(job["id"])
    fr = reporting.freshness(reps)
    if fr is None:
        print(f"`{rtype}` 報告 **0本**（ジョブ {job.get('createTime')}）。"
              " **「数が 0」ではありません** —— まだ置かれていないだけ（次の回で見ること）")
        ledger("reported", rtype, reports=0, rows=0, last_day=None, lag_h=None)
        return 0
    print(f"`{rtype}` 報告 {len(reps)}本・最後の期間 {fr['end']:%m/%d %H:%M}Z"
          f" ＝ **遅れ {fr['lag_h']:.1f}時間**"
          f"（置かれるまで {fr['made_h']}時間{'・!! 遅い' if fr['late'] else ''}）")
    todo = reporting.unseen(reps, reporting.seen_marks(store))
    rows = []
    for r in todo:
        rows += reporting.parse(reporting.download(r), r)
    n = reporting.append(rows, store) if rows else 0
    all_rows = reporting.load_rows(store)
    print(f"  未読 {len(todo)}本 → **{n}行** 積んだ（store 累計 {len(all_rows)}行）")
    days = sorted({r.get("date", "") for r in all_rows})
    last_day = days[-1] if days else None
    if last_day:
        print(f"  報告の日 {days[0]}〜{last_day}（**太平洋時間の日** ＝ 10:00 JST の公開は前日の行）")
        for vid in studio_video_ids(ledger_rows()):
            if rtype == reporting.REACH_TYPE:
                rd = reporting.reach_by_day(all_rows, vid)
                if rd:
                    print(f"  新 {vid}  " + " → ".join(
                        f"{d[4:]} 面{i}回 CTR{c:.1f}%" for d, i, c in rd[-5:]))
            else:
                vd = reporting.views_by_day(all_rows, vid)
                if vd:
                    print(f"  新 {vid}  " + " → ".join(f"{d[4:]} {v}回" for d, v in vd[-5:]))
    ledger("reported", rtype, reports=len(reps), rows=n,
           last_day=last_day, lag_h=fr["lag_h"], made_h=fr["made_h"])
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    for c in ("lint", "build", "read", "critique", "crosscheck", "order-image"):
        sub.add_parser(c).add_argument("id")
    h = sub.add_parser("hear"); h.add_argument("id"); h.add_argument("--medium", action="store_true")
    sc = sub.add_parser("schedule"); sc.add_argument("id"); sc.add_argument("--at", required=True)
    sc.add_argument("--replace", default=""); sc.add_argument("--force", action="store_true")
    sc.add_argument("--dry-run", action="store_true")
    sub.add_parser("measure")
    tr = sub.add_parser("trend"); tr.add_argument("--days", type=float, default=3)
    tr.add_argument("--by-day-count", action="store_true")
    an = sub.add_parser("analytics"); an.add_argument("--force", action="store_true")
    sub.add_parser("comments")
    rpt = sub.add_parser("reporting"); rpt.add_argument("--setup", action="store_true")
    rp = sub.add_parser("reply"); rp.add_argument("comment_id"); rp.add_argument("--text", required=True)
    rp.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    fn = globals()["cmd_" + a.cmd.replace("-", "_")]
    return fn(a) or 0


if __name__ == "__main__":
    sys.exit(main())
