#!/usr/bin/env python3
"""**予約の池化。** 予約を外して private のまま残し、**下書きの池**にする。

    python scripts/pool_drain.py             # 何本 外して、何本 残るか（**API 0単位**）
    python scripts/pool_drain.py --apply     # 実際に外す（1本 51単位。日枠が尽きたら止まる）
    python scripts/pool_drain.py --keep 1    # 先頭の N本 は予約のまま残す（既定 1）

## なぜ要るか（2026-08-31・オーナーが規則を固定した日）

オーナー原文（`src/house_rule.py`・`CLAUDE.md` 冒頭・`docs/GOAL.md`）:

    「動画は1日一本作り置きはなしにして。次の投稿予定までにそこで投稿する
      動画を改善し続ける。それは固定にして。その上で目標を目指す」

**規則を機械の床に入れても、既にある予約はそのまま公開され続けます。**
実測（2026-08-31 08:0x UTC・控え `data/uploaded.jsonl`）:

    予約済み **459本** ／ 2026-08-31 〜 2026-10-10 JST ／ **約 11.5本/日**

**規則1（1日1本）とも規則2（作り置きなし）とも真っ向から反します。**
`batch_build` の上限は「これから置くもの」にしか当たらないので、
**この 459本 は縛りの外側**にあります。

## 消さないこと（**取り消せる側を選んでいます**）

**動画そのものを削除しません。** 消すのは予約であって、本ではありません。
`videos().delete` は取り消せませんが、`privacyStatus=private` ＋ `publishAt` 落としは
**時刻を入れ直すだけで戻ります**（`scripts/unschedule.py` の頭に同じ判断があります）。

外した本は private のまま残り、説明欄の `[t:テーマID]` も残るので、
**投稿済みの数え方も、在庫の数え方も変わりません。**
**そこが「下書きの池」です** —— 毎日そこから1本を選び、
その枠まで改善して出す（規則3）。

## 池は**手元の控え**から数えます（口からではなく）

`reschedule._scheduled()` は `history.channel_video_ids(cap=400)` を通るので、
**予約が 400本 を超えた日から、古い側が見えません**（実測 2026-08-31:
口からは **169本**・控えには **459本**。差の 290本 は口から見えないだけで、
時刻が来れば**公開されます**）。

だから池の一覧は控えから作ります。**`unschedule.py` と同じ示し方**です:

    控えの `at` が、いまより先 → **まだ一度も公開されていない**
    → 公開状態は private・再生は 0 → **触ってよい**

**証明できない行は触りません**（`at` が読めない／過去）。
「たぶん予約中だろう」で `videos.update` を撃たないこと ——
うっかり公開済みを private にすると、視聴者から見えなくなります。

## 先頭の1本は残します（`--keep`）

**投稿が途切れるのが最大の損失**（`docs/GOAL.md` の確認項目4）。
いちばん近い予約まで外すと、次の1本を入れ直すまでのあいだ
**公開が0本の日**ができます。だから既定で**先頭1本だけ**は予約のまま残し、
**その1本を、公開の瞬間まで改善します**（規則3そのもの）。

`--keep 0` にすれば全部 外せますが、**その回は必ず今日の1本を入れ直すこと。**

## 日枠（`quotaExceeded`）で、1回では終わりません

1本 51単位（`videos.list` 1 ＋ `videos.update` 50）・Data API の日枠は 10,000単位。
**458本 ＝ 約 23,400単位 ＝ 2〜3日ぶん**です
（同じ枠を `videos.insert`（1本 1,600単位）と分け合うので、実際はもっと掛かります）。

**だから、この道具は「尽きたら止まる」形にしてあります**:

    403 quotaExceeded を見た時点で止める（`reschedule._is_quota`）
    そこまでに外した本数と、残っている本数を印字する
    **残件を `data/inbox.jsonl` に置く**（`--no-inbox` で止められます）

**受け取り帳に置くのは、次の回のためです** —— この回が死んでも、
`status.py` が「開いている依頼」として出し続けるので、続きが引き継げます。
**同じ本文なら同じ ID に積まれる**ので、何回置いても1件のままです。

## この道具は冪等です

外した本は控えの `at` が `None` になるので（`dupes.retime(id, None)`）、
次に走ったとき**池の一覧に出ません。** だから「尽きるまで外す」を、
日枠が戻るたびに撃つだけで進みます。
**残りが `--keep` 本になったら、この道具は何もしません。**
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import reschedule  # noqa: E402  （書き込みの実装は1か所だけ）
from src import dupes, house_rule, inbox, uploader  # noqa: E402

#: 控えの予約時刻が「いまより先」と言うために要る余白
#: （`unschedule.LEDGER_MARGIN` と同じ理由・同じ幅）。
LEDGER_MARGIN = timedelta(hours=1)

#: 1本 外すのに使う単位（`videos.list` 1 ＋ `videos.update` 50）。
UNITS_PER_VIDEO = 51

#: **サムネイルを1本 載せるのに使う単位**（`thumbnails.set`）。
THUMB_UNITS = 50

#: Data API の日枠（単位／日）。**「何日ぶんの枠が要るか」を言うためだけに使います。**
#: 既定の 10,000 です —— 2026-08-27 に「日枠は 10,000 ではない」と結論した回が
#: ありますが、**あれは `videos.update` の ok 行を二重に数えた側の誤り**でした
#: （全文は `src/upload_cap.measured_budget()` の註）。
#: **実測の枠が要る判断には、この定数ではなく `upload_cap` を読むこと。**
DAY_QUOTA = 10_000


def _parse(raw: object) -> datetime | None:
    try:
        at = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return at.replace(tzinfo=timezone.utc) if at.tzinfo is None else at


def pool(now: datetime | None = None, rows: list[dict] | None = None) -> list[dict]:
    """**池に落とす作り置き**を、公開時刻の順に返す（API 0単位）。

    示せない行（`at` が無い／読めない／もう先ではない）は**落とします** ——
    落とすほうが安全です（触らなければ、公開済みを private にする事故が起きない）。

    ## **規則の下で作った本は、池に入れません**（2026-08-31 に実物で踏んだ）

    ここは長らく「未来の予約」を全部 池に入れていました。**その日に作って
    予約したばかりの1本も、同じ扱いで外れます。**

    実測（2026-08-31 08:41 UTC・この註を書いた回）:
    その回の1本 `J67vEIw_VRE`（09/05 20:00 JST に予約）は、
    前の回が 09/01〜09/11 を先に外し終えていたせいで **公開の早い順で3番目**に
    並び、**14本のうちの1本として外れました。** 同じ回が「きょうの1本を
    予約まで入れた」と commit した 90秒後です。日枠はその時点で尽きており、
    **入れ直しは次の窓（09/01 16:00 JST）まで待ち**になりました。

    **「公開が近い順」は正しい。間違っていたのは、池の中身のほうです。**
    池に入れてよいのは **作り置き**（規則より前に作った、まだ公開していない本）
    だけで、**規則の下で作った本は「きょうの1本」です**。
    判定は `src.house_rule.is_stockpile()` の1か所に置いてあります
    （`src/reach_split.publishes_per_day()` と同じ所を読みます。写さないこと）。

    **覆る条件**: `house_rule.STOCKPILE_SINCE` より後に作った本を、
    それでも池へ入れたくなったら —— そのときは規則3
    （次の枠までその1本を改善し続ける）を先に読み直すこと。
    検査は `tests/test_pool_drain_keeps_new.py`。
    """
    now = now or datetime.now(timezone.utc)
    rows = dupes.ledger_rows() if rows is None else rows
    out = []
    for row in rows:
        at = _parse(row.get("at"))
        if at is None or at <= now + LEDGER_MARGIN:
            continue
        if not row.get("id"):
            continue
        # **規則の下で作った本は、作り置きではありません**（上の註）。
        # `is_stockpile` は `video_id` と `at` を見るので、控えの `id` を写して渡します。
        # **`now` を渡すこと**（2026-09-01）—— 日付だけを渡していたころ、
        # 当日ぶんが「もう公開になっている」に倒れて一覧から丸ごと落ちていました
        # （`src.house_rule._published_before()` の註・`tests/test_pool_drain_today_first.py`）。
        if not house_rule.is_stockpile({**row, "video_id": row["id"]},
                                       today=now.astimezone(
                                           timezone(timedelta(hours=9))
                                       ).strftime("%Y-%m-%d"),
                                       now=now):
            continue
        out.append({"id": row["id"], "at": at,
                    "title": row.get("title", ""), "topic": row.get("topic", "")})
    out.sort(key=lambda r: r["at"])
    return out


def today_rows(rows: list[dict], now: datetime | None = None) -> list[dict]:
    """**きょう（JST）公開される予定の本**を、一覧の中から抜き出す（API 0単位）。

    ## なぜ数えて印字するか（2026-09-01・オーナーが画面で踏んだ）

    16:33 JST、Studio に **09/01 の 18:00〜21:00 の予約が4本**出ていたのに、
    `pool_drain` の一覧は **09/02 から**でした。**当日ぶんが1本も無いこと自体が
    画面のどこにも出ていない**ので、一覧を見ても「そういうもの」と読めます。

    **いちばん早い日は、いちばん取り返しがつきません** —— 明日ぶんは明日の窓で
    外せますが、**きょうの夕方に出る本は、いま外さなければ公開されます**。
    だから本数を1行 出して、**0本なら 0本 と言わせます**（黙って空にしない）。
    """
    now = now or datetime.now(timezone.utc)
    jst = timezone(timedelta(hours=9))
    day = now.astimezone(jst).strftime("%Y-%m-%d")
    return [r for r in rows if r["at"].astimezone(jst).strftime("%Y-%m-%d") == day]


def plan(rows: list[dict], keep: int,
         now: datetime | None = None) -> tuple[list[dict], list[dict]]:
    """**残す本と、外す本**に割る（API 0単位）。公開時刻の早い順に `keep` 本を残す。

    ## **きょうぶんは、`--keep 0` でも外しません**（2026-09-02・規則5）

    オーナー原文（固定その4）は「**現在の日付にしか予約しない**」で、
    その回の指示は「**`--keep 0` です —— 先の日付には1本も残さないので。
    ただし今日の1本が未公開で残っているなら、それは外さないこと**」でした。

    **`--keep 0` はその両方を一度に言えません** —— 早い順に 0本 残すので、
    きょうの1本が一覧の先頭に居れば**それが最初に外れます**。
    そして**きょうの1本は、いちばん取り返しがつきません**
    （明日ぶんは明日の窓で外せますが、きょうの夕方の1本は、
    外したら その日の公開が 0本 になります ＝ `CLAUDE.md`「4. 投稿を途切れさせない」）。

    だから規則5 の下では、**きょう（JST）以前の予約は `keep` の数と関係なく残します。**
    `keep` が数えるのは**明日以降のぶんだけ**です。

    **覆る条件**: `house_rule.SAME_DAY_SCHEDULING_ONLY` が `False` になったら、
    この分けは消えて、単純な「早い順に `keep` 本」に戻ります。
    検査は `tests/test_pool_drain_keep_today.py`。
    """
    keep = max(0, keep)
    if not house_rule.same_day_only():
        return rows[:keep], rows[keep:]
    now = now or datetime.now(timezone.utc)
    jst = timezone(timedelta(hours=9))
    today = now.astimezone(jst).date()
    today_side = [r for r in rows if r["at"].astimezone(jst).date() <= today]
    ahead = [r for r in rows if r["at"].astimezone(jst).date() > today]
    return today_side + ahead[:keep], ahead[keep:]


def by_day(rows: list[dict]) -> dict[str, int]:
    """日（JST）ごとの本数。**「1日 何本 公開され続けるか」を数字で残すため。**"""
    jst = timezone(timedelta(hours=9))
    out: dict[str, int] = {}
    for r in rows:
        key = r["at"].astimezone(jst).strftime("%Y-%m-%d")
        out[key] = out.get(key, 0) + 1
    return out


def first_breach(days: dict[str, int], today: str | None = None) -> tuple[str, int, int] | None:
    """**規則1（1日1本）が最初に破れる日**と、そこまでの日数・破れる日数を返す。

    ## なぜ足したか（2026-08-31）

    ここは長らく「外す **267本**（見積り 13,617単位）」までしか言いませんでした。
    **数は正しいのですが、締切がどこにも出ていません。** 13,617単位 は
    日枠（10,000）の **1.4日ぶん**で、**1回の回では終わりません** ——
    つまり「日枠が戻った回に続きを撃つ」を**何日か続けないと終わらない仕事**です。

    締切の無い仕事は後回しになります。実測 2026-08-31 23:5x、
    池化は 09/04 までしか進んでおらず、**09/12 から 27日ぶん・249本 が
    規則1 を破ったまま**でした（`data/uploaded.jsonl`）。
    **09/01・09/02・09/04 は 1本/日 で規則どおり**なので、
    数だけ見ていると「進んでいる」と読めてしまいます。

    **だから、いつ破れるかを言わせます。**

    **覆る条件**: `--apply` が最後まで通って予約が 1本 になったとき
    （そのとき、この行は自分で黙ります）。
    """
    from datetime import datetime, timedelta, timezone

    jst = timezone(timedelta(hours=9))
    today = today or datetime.now(jst).strftime("%Y-%m-%d")
    cap = house_rule.cap()
    over = sorted(d for d, n in days.items() if d >= today and n > cap)
    if not over:
        return None
    first = over[0]
    left = (datetime.strptime(first, "%Y-%m-%d").date()
            - datetime.strptime(today, "%Y-%m-%d").date()).days
    return first, left, len(over)


def _inbox_text(left: int, keep: int) -> str:
    return (
        "予約の池化が途中です（Data API の日枠）。"
        f"**まだ {left}本 が予約に残っています。**"
        " 日枠が戻ったら `python scripts/pool_drain.py --apply"
        f" --keep {keep}` を撃って続けること。"
        "（オーナーの規則 2026-08-31: 動画は1日一本・作り置きなし。"
        "外した本は private のまま残る＝下書きの池。**消さないこと。**）"
    )


#: **池化より先に押す1本**（2026-09-01 に足した。**順番の門**）。
#:
#: ## なぜ要るか（**手順に書いてあり、そのとおりに撃たれ、それでも負けた**）
#:
#: 実測 2026-08-31 の窓（`python -m src.quota_ledger`）:
#:
#:     reschedule.py:_update          **9,668単位**  ← `pool_drain --apply`
#:     history.py:channel_video_ids    3,409単位
#:     thumbnails.set                     50単位（**1回だけ**）
#:
#: 同じ窓で、**09/01 22:00 JST に公開される本（`UIWHsypOPPg`）は
#: `thumbnail_set: false` のまま**でした。要る単位は **50**、
#: 焼けた単位は **13,388**。**0.4% が取れませんでした。**
#:
#: 順番そのものは、この repo の中で3回 書かれています ——
#: `docs/trigger_main.md` §2.6、`retro.py` の申し送り
#: 「**16:00 JST 以降の窓の回は、`refresh_thumbnail --video <次の1本>` を
#: その窓の最初に撃つこと。`reschedule` より先に**」、そして
#: `scripts/refresh_thumbnail.py` の `only_video` の註。
#: **3つとも「次に来た側が覚えていること」に頼っています。**
#: `batch_build.slots()`:「**人の記憶と手写しに依存する門は、
#: この輪では毎回落ちる側**」。だから門を、単位を焼く側へ移します。
#:
#: ## なぜ「止める」ではなく「先に押す」か
#:
#: 止める形（「サムネが載るまで `--apply` を断る」）にすると、
#: **押せない事情が1つでもあると池化が永久に止まります** ——
#: そして池化には締切があります（`first_breach()`: 規則1 が
#: 最初に破れるのは 2026-09-12・238本 多い）。
#: **先に押す形なら、押せても押せなくても池化は進みます。**
#: 費用は 13,617単位 のうち **50単位（0.4%）**です。
#:
#: ## 覆る条件
#:
#: - 枠が広がって取り合いが消えたら、この門は要りません
#: - `refresh_thumbnail.push_missing()` が「次に公開される1本」を
#:   自分で先に押すようになったら、ここは呼ぶだけに縮みます
#: - **`--no-thumbnail-first` で外せます**（外した回は理由を JOURNAL に）


def thumbnail_first(now: datetime | None = None) -> str:
    """**この回、池化より先に押すべき1本の動画ID**（無ければ空文字）。**API 0単位**。

    出どころは1か所です（`src/next_slot`）—— 次に公開される本と、
    その本のサムネイルが控えに在るのに載っていないか。
    **ここでは判定を書き直しません**（書き直すと2つの答えができます）。
    """
    try:
        from src import next_slot                              # noqa: PLC0415
        row = next_slot.next_video(now)
        if not row:
            return ""
        vid = str(row.get("video_id") or "")
        if vid and next_slot.pending_thumbnail(vid):
            return vid
    except Exception:                                          # noqa: BLE001
        return ""
    return ""


#: **差し替えの2手のぶんを、池化に食わせないこと**（2026-09-01 22:2x に足した）。
#:
#: ## なぜ要るか —— **上の門は、サムネイルしか知りません**
#:
#: `thumbnail_first()` は「次に公開される本の**サムネイルが載っていない**」だけを
#: 見ます。**サムネイルが既に載っている本は、空文字で返ります。**
#: そして `improve` のもう1つの道 —— **焼き直して差し替える**（`--unschedule`
#: → `--move` ＝ `videos.update` ×2 ＝ **100単位**）—— は、この門の外でした。
#:
#: 実測 2026-09-01 の窓（16:00 JST 起点・`data/api_calls.jsonl`）:
#:
#:     16:0x  `refresh_thumbnail` 50単位（**上の門が正しく効いた**）
#:     16:0x  `pool_drain --apply` で 160本 ＝ 窓ぜんぶ（12,258 / 10,000単位）
#:     結果   次の枠 `a63FzIUV2wI`（09/02 13:00 公開）は、
#:            **焼いたあとに入った 6件 が1つも入らないまま出ます**
#:
#: **その本のサムネイルは載っていました。** だから上の門は何も言わず、
#: 100単位 が残りませんでした。**同じ形の2度目です**（1度目は 08/31 の 50単位）。
#:
#: ## なぜ「止める」ではなく「残す」か
#:
#: `thumbnail_first` の註と同じ理由です —— 止める形にすると、
#: 押せない事情が1つでもあれば池化が永久に止まり、
#: 締切（`first_breach()`）が動きません。**残す形なら池化は進みます。**
#: 費用は、この窓の **100単位（1%）**・外す本にして **2本**です。
#:
#: ## 覆る条件
#:
#: - **枠が公開に間に合わない本には、何も残しません**
#:   （`next_slot.window_reaches()` が `False` ＝ もう差し替えられない。
#:   残すと、誰にも使われない取り置きになります —— `RESERVE_UNITS` がその形）
#: - 焼き直しの要らない本（`stale_commits()` が空）にも残しません
#: - `--no-swap-reserve` で外せます（**外した回は理由を JOURNAL に**）
#: - `reschedule` が `videos.update` を使わない道を持ったら、この門ごと要りません
SWAP_UNITS = 50 * 2


def swap_reserve(now: datetime | None = None) -> tuple[str, int] | None:
    """**次の枠の本が、まだ差し替えを要るか**（要るなら `(動画ID, 件数)`）。**API 0単位**。

    判定は `src/next_slot` に1本化してあります（**ここで書き直さないこと** ——
    書き直すと2つの答えができます。`thumbnail_first` と同じ）。

    `None` を返すのは、次の1本が無い回・**焼き直しても同じ物が出る回**
    （`stale_commits()` が空）・**枠が公開に間に合わない回**
    （`window_reaches()` が `False`）です。
    """
    try:
        from src import next_slot                              # noqa: PLC0415
        row = next_slot.next_video(now)
        if not row:
            return None
        vid = str(row.get("video_id") or "")
        if not vid:
            return None
        built = next_slot._parse(row.get("uploaded_at"))
        cm = next_slot.stale_commits(built, video_id=vid)
        if not cm:
            return None
        at = row.get("_at")
        # **間に合わない本に残さないこと。** `None`（分からない）では残します ——
        # 分からないほうへ倒すと、取り置きが早く消えます。
        if at is not None and next_slot.window_reaches(at, now) is False:
            return None
        return vid, len(cm)
    except Exception:                                          # noqa: BLE001
        return None


def _trim_for_swap(drop: list, now: datetime | None = None) -> tuple[list, int]:
    """**残りの単位が差し替えのぶんを切りそうなら、外す本を減らす。**（**API 0単位**）

    返りは `(減らしたあとの drop, 残した本数)`。**帳面が読めない回は減らしません**
    （推測で締切を遅らせないため —— `first_breach()` に締切があります）。
    """
    try:
        from src import quota_ledger                           # noqa: PLC0415
        used = int(quota_ledger.spent(now).get("data") or 0)
        cap = int(quota_ledger.DAY_UNITS)
    except Exception:                                          # noqa: BLE001
        return drop, 0
    left = cap - used - SWAP_UNITS            # 差し替えのぶんを引いた残り
    if left <= 0:
        # **もう残っていません。** ここで `drop` を空にしても差し替えは撃てない
        # ので、減らしません（池化の締切だけが遅れます）。
        return drop, 0
    room = left // UNITS_PER_VIDEO
    if room >= len(drop):
        return drop, 0
    return drop[:room], len(drop) - room


def _push_thumbnail_first(video_id: str) -> int:
    """その1本を押す（**50単位**）。返りは `refresh_thumbnail.push_missing` のまま。

    **落ちても池化は止めません**（返り値で伝えるだけ）。理由は
    `thumbnail_first` の註「止める形にすると池化が永久に止まる」。
    """
    import refresh_thumbnail                                   # noqa: PLC0415
    return refresh_thumbnail.push_missing(only_video=video_id)


def _calendar_hold() -> list[str]:
    """**暦に穴が空いている間、池化は後回し**（**API 0単位**）。鳴らなければ空。

    ## **【2026-09-02】この門は、規則5 の下では黙ります。まず ここを読むこと**

    オーナー原文（`src/house_rule.OWNER_VERBATIM_SAME_DAY`・固定その4）:

        「現在の日付にしか予約しないってことだからね？」

    ＝ **先の日付には1本も置かない。先の日付が空であることが正しい状態です。**

    **下の註は、まっすぐ逆のことを言っています** ——「穴を埋める本が無くなるから、
    池化より先に `reschedule --compact --apply` で 09/03〜09/27 へ並べ直せ」。
    **その手は、いま禁じられている手そのものです。**
    そして この門は `--apply` を**止めて**いたので、
    **オーナーが名指しした `pool_drain --apply --keep 0` が、
    `--despite-gap` を付けない限り1本も外せない**状態でした。

    だから `house_rule.same_day_only()` が真のあいだ、この門は空を返します
    （＝ 池化がそのまま正しい手）。**下の枝は消していません** ——
    オーナーが「先の日付にも置いてよい」と言えば、そちらへ自動で戻ります。

    ## なぜ要るか（2026-09-02 01:0x に測って足した。**上の規則5 の下では効きません**）

    この道具と `scripts/reschedule.py --compact` は、**同じ予約の山に、逆向きの手**を
    当てます。どちらも `[暦]` の鳴っている回に候補として出てきます:

        pool_drain        規則2（作り置きなし）→ 「残す 1本／**外す 107本**」
        reschedule --compact  規則1（1日1本）  → 「**25本 を 09/03〜09/27 へ 1日1本**」

    **先に池化を撃つと、穴を埋める本がその場で無くなります。** 実測 2026-09-02 01:0x
    の控え —— 予約 108本 のうち **106本が 09/24〜10/09**、手前の **09/03〜09/23 は
    20日 まるごと 0本**。池化はその 106本 を全部 private の下書きへ戻すので、
    **穴の20日は「埋める本が1本も無い」状態で確定します**（戻すには生成ではなく
    予約の入れ直しが要り、`videos.update` は日枠の内側です）。

    ## どちらが先か —— **穴のほうが高い**

    `eta.py` の到達日が動くのは前提を1件 閉じたときだけで、前提の多くは
    **公開ずみの本が積むのを待って**います。同じ回の `eta.py` の実測:

        今後14日 の θ は **0.57/日**（過去の実測 1.10/日 の **52%**）
        「**この窓で縛っているのは公開の順番のほうです**」

    **空白の20日は、その間に閉じられたはずの前提が1件も閉じない**という意味で
    θ の側に効きます。一方、作り置きが山のまま残っても **θ は1日も遅れません**
    （遅れるのは規則2 の見た目だけで、`eta.py` の入力にありません）。
    **釣り合っていないので、穴が先です。**

    ## 覆る条件

    - 穴が埋まったら（`calendar()["run"] < 2`）この門は黙ります ——
      **そのとき池化が正になります。**「詰めてから、余りを外す」の順です
    - オーナーが 1日1本 を外したら `house_rule` 経由で `calendar()` ごと緩みます
    - 控えが実物とずれていると穴も嘘になります（`src/ledger_truth.py`）。
      **`calendar()` の覆る条件がそのまま効きます**
    """
    # **規則5（固定その4）の下では、穴は欠陥ではありません。**（2026-09-02）
    #     ここで止めると、オーナーが名指しした手が撃てません。
    if house_rule.same_day_only():
        return []
    try:
        from src import next_slot                              # noqa: PLC0415
        cal = next_slot.calendar()
    except Exception:                                          # noqa: BLE001
        return []                                              # 読めない回は黙る（推測で止めない）
    if int(cal.get("total") or 0) <= 0 or int(cal.get("run") or 0) < 2:
        return []
    run, run_from = int(cal["run"]), cal.get("run_from") or "?"
    return [
        f"[pool] [!] **暦に穴が空いています —— 池化より先に、詰めるほうです**"
        f"（今後 {cal.get('days')}日 のうち **{cal.get('empty')}日 が空**／"
        f"いちばん長い空白は **{run}日 連続**（{run_from} 〜））",
        "[pool]     **いま外すと、その穴を埋める本がその場で無くなります**"
        "（外した本は private の下書きへ戻り、入れ直しは `videos.update` ＝ 日枠の内側）",
        "[pool]     → python scripts/reschedule.py --compact          # 割り当てだけ・**0単位**",
        "[pool]     → python scripts/reschedule.py --compact --apply  # 1本 50単位",
        "[pool]     **詰めてから、余りを外すこと。**"
        "（穴は `eta.py` の θ に効き、作り置きの見た目は効きません。`_calendar_hold` の註）",
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="予約を外して private のまま残し、下書きの池にする")
    ap.add_argument("--apply", action="store_true",
                    help="実際に外す（**付けないと数えるだけ・API 0単位**）")
    # **既定は規則5 が決めます**（2026-09-02）。「現在の日付にしか予約しない」の下で
    #     **先の日付に残してよい本は 0本** です（きょうぶんは `plan()` が別に守ります）。
    #     規則5 が外れたら、規則1 の1日ぶん（＝ 1本）へ自動で戻ります。
    _keep_default = 0 if house_rule.same_day_only() else house_rule.PUBLISH_PER_DAY
    ap.add_argument("--keep", type=int, default=_keep_default,
                    help="**明日以降**の先頭 N本 は予約のまま残す"
                         f"（既定 {_keep_default}"
                         + ("　＝ 規則5「先の日付には1本も置かない」。"
                            "**きょうぶんは `--keep 0` でも外しません**"
                            if house_rule.same_day_only()
                            else " ＝ 規則1の1日ぶん") + "）")
    ap.add_argument("--max", type=int, default=0,
                    help="この回で外す上限（0 ＝ 日枠が尽きるまで）")
    ap.add_argument("--no-inbox", action="store_true",
                    help="途中で止まっても受け取り帳に置かない")
    ap.add_argument("--no-thumbnail-first", action="store_true",
                    help="次に公開される本のサムネイル（50単位）を先に押さない"
                         "（**外した回は理由を JOURNAL に**）")
    ap.add_argument("--despite-gap", action="store_true",
                    help="暦に穴が空いていても外す（**外した回は理由を JOURNAL に**）")
    ap.add_argument("--no-swap-reserve", action="store_true",
                    help=f"次に公開される本の差し替え（{SWAP_UNITS}単位）のぶんを"
                         "残さない（**外した回は理由を JOURNAL に**）")
    args = ap.parse_args(argv)

    rows = pool()
    kept, drop = plan(rows, args.keep)
    days = by_day(rows)
    if days:
        span = f"{min(days)} 〜 {max(days)}"
        per_day = len(rows) / max(1, len(days))
        print(f"[pool] 予約済み **{len(rows)}本**（控え）／{span} JST"
              f"／**{per_day:.1f}本/日**", flush=True)
    else:
        print("[pool] 予約済み **0本**（控え）", flush=True)

    # **きょうぶんを、必ず1行 出すこと**（2026-09-01 に足した。`today_rows` の註）。
    # `--apply` の前に「当日ぶんが見えているか」が分かる唯一の行です。
    mine = today_rows(rows)
    jst_today = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")
    if mine:
        print(f"[pool] **きょう {jst_today} JST に公開される予定: {len(mine)}本**"
              f"（一覧の先頭 —— いま外さなければ、その時刻に公開されます）",
              flush=True)
        jst = timezone(timedelta(hours=9))
        for r in mine[:8]:
            print(f"[pool]     {r['at'].astimezone(jst).strftime('%H:%M')} JST"
                  f"  {r['id']}  {r['title'][:36]}", flush=True)
    else:
        print(f"[pool] きょう {jst_today} JST に公開される予定: **控えでは 0本**"
              " —— **控えに無い予約は、この一覧に出ません。**"
              " 2026-09-01 16:33 に Studio へ4本 出ていて控えは 0本 でした"
              "（`src.dupes.observe_scheduled()` の註）。"
              " 枠が戻った回は `python scripts/reschedule.py --list` を先に撃つこと"
              "（読んだついでに控えを実物へ合わせます）", flush=True)

    if args.max > 0:
        drop = drop[:args.max]

    # **差し替えのぶんを、池化に食わせないこと**（2026-09-01 22:2x に足した）。
    # 上の `thumbnail_first` はサムネイルしか見ておらず、**サムネイルが載っている
    # 本の「焼き直して差し替える」（100単位）は門の外**でした。実測 09/01 16:0x の
    # 窓がそれで、次の枠 `a63FzIUV2wI` は 6件 入らないまま出ます。`swap_reserve` の註。
    swap = None if args.no_swap_reserve else swap_reserve()
    if swap:
        vid, ncm = swap
        drop, held = _trim_for_swap(drop)
        print(f"[pool] **次に公開される本 `{vid}` は、まだ差し替えが要ります**"
              f"（焼いたあとに {ncm}件・差し替えは {SWAP_UNITS}単位 ＝ "
              f"`videos.update` ×2）", flush=True)
        if held:
            print(f"[pool]     そのぶんを残すため、この回に外すのを **{held}本 減らします**"
                  f"（{held * UNITS_PER_VIDEO}単位）。"
                  " 外すには `--no-swap-reserve`（**理由を JOURNAL に**）", flush=True)
        else:
            print("[pool]     枠はこの回の池化と両方に足ります（減らしていません）",
                  flush=True)
        print(f"[pool]     → **池化より先に撃つこと**: `python -m src.pipeline` で"
              f"焼き直し → `scripts/reschedule.py --unschedule {vid}` →"
              " 新しい方を同じ枠へ `--move`", flush=True)

    print(f"[pool] 残す **{len(kept)}本**／外す **{len(drop)}本**"
          f"（見積り {len(drop) * UNITS_PER_VIDEO:,}単位）", flush=True)

    # **締切を言うこと。** 数だけでは、後回しにしてよい仕事に見えます
    # （`first_breach()` の docstring に、そう読めてしまった実測）。
    breach = first_breach(days)
    if breach:
        first, left, ndays = breach
        over_n = sum(n - house_rule.cap() for d, n in days.items()
                     if d >= first and n > house_rule.cap())
        need_days = (len(drop) * UNITS_PER_VIDEO + DAY_QUOTA - 1) // DAY_QUOTA
        print(f"[pool] [!] **規則1 が最初に破れるのは {first}**（{left}日後）。"
              f" そこから **{ndays}日ぶん・{over_n}本 多い**", flush=True)
        print(f"[pool]     日枠は {DAY_QUOTA:,}単位/日 なので、"
              f"外しきるのに **最低 {need_days}日ぶんの枠**が要ります"
              f"（他の用途と取り合います）。**1回では終わりません**", flush=True)
    else:
        print("[pool] **これから来る日は、どれも規則1 の内側です**（1日1本）",
              flush=True)
    # **上の締切も、この一覧も、控えだけで出しています**（2026-09-01 に足した）。
    # オーナーが 09/01 16:33 に画面で踏んだのは、まさにその形でした ——
    # 控えは「予約はもう 09/02 以降だけ」と言い、実物には 09/01 18:00〜21:00 に
    # 4本 残っていた。**「これから来る日は規則1 の内側です」を裸で言わないこと。**
    # 数え方は `src/ledger_truth.py`（API 0単位）。**鳴らなければ黙ります。**
    try:
        from src import ledger_truth
        ghosts = ledger_truth.phantoms()
    except Exception:                                          # noqa: BLE001
        ghosts = []
    if ghosts:
        print(f"[pool] [!] **上の数は控えだけで出しています。その控えのうち"
              f" {len(ghosts)}本 は、実物と食い違っていることが分かっています**"
              f"（`python -m src.ledger_truth`）: "
              + " ".join(g["id"] for g in ghosts), flush=True)
        print("[pool]     **この本は一覧に出ていません。**"
              " 控えの `at` が過去なら `pool()` の `at <= now` で落ちるので、"
              "実物だけが予約のまま公開されます", flush=True)
    for r in kept:
        print(f"[pool]   残す: {r['at'].isoformat()}  {r['id']}  {r['title'][:40]}",
              flush=True)
    if not drop:
        print("[pool] **外すものはありません。**（池化は済んでいます）", flush=True)
        return 0
    # **暦に穴が空いている間は、池化のほうが後です**（2026-09-02 01:0x に足した）。
    # 詳しくは `_calendar_hold()` の註。**API 0単位。数えるだけの回にも出します**
    # —— 撃つ前に順番が見えていないと、次の回がまた同じ順で撃ちます。
    hold = _calendar_hold()
    for line in hold:
        print(line, flush=True)
    if not args.apply:
        print("[pool] **数えただけです**（API 0単位）。撃つには `--apply`。", flush=True)
        return 0

    # **池化より先に、次に公開される本のサムネイルを押すこと**（2026-09-01）。
    # 13,617単位 のうち **50単位（0.4%）**です。理由は `thumbnail_first` の註 ——
    # 順番は3か所に書いてあり、そのとおりに撃たれ、それでも 08/31 の窓は
    # 9,668単位 を先に焼いて、**50単位 が残りませんでした。**
    if not args.no_thumbnail_first:
        first = thumbnail_first()
        if first:
            print(f"[pool] **池化より先に、次に公開される本のサムネイルを押します**"
                  f"（{first}・{THUMB_UNITS}単位 ＝ この回の見積りの"
                  f" {THUMB_UNITS * 100.0 / max(1, len(drop) * UNITS_PER_VIDEO):.1f}%）",
                  flush=True)
            try:
                rc = _push_thumbnail_first(first)
            except (KeyboardInterrupt, MemoryError):
                raise
            except BaseException as exc:                       # noqa: BLE001
                rc = 1
                print(f"[pool] [!] サムネイルで落ちました（池化は続けます）:"
                      f" {str(exc)[:160]}", flush=True)
            if rc:
                print("[pool] [!] **サムネイルは載りませんでした。**"
                      " 池化は続けます（止めると 09/12 の締切が動きません）"
                      " —— 単位が理由なら、窓が変わった回に"
                      f" `python scripts/refresh_thumbnail.py --missing --video {first}`",
                      flush=True)

    # **止めるのはここ ——「外す」だけです**（2026-09-02）。
    # サムネイル（50単位）はこの門より前に置いてあります。あれは §4 がいちばん高い
    # 50単位 と呼んでいる手で、**暦の穴とは関係がありません**。
    # ここで止めるのは `videos.update`（外す・107本ぶん）のほうだけです。
    if hold and not args.despite_gap:
        print("[pool] **この回は外しません。**"
              " 承知のうえで撃つなら `--despite-gap`"
              "（**理由を JOURNAL に書くこと**）。", flush=True)
        return 0

    svc = uploader._service()
    # **控えで示せた本だけがここに来ています**（`pool()`）。だから
    # 現状を読めなかった回も、投稿のときにこちらが立てた4欄で代えます
    # （`unschedule.py` と同じ扱い。`reschedule._update` の `fallback_status`）。
    fallback = uploader.base_status()

    # **`SystemExit` を `except Exception` で受けようとしないこと**（`QUOTA_MARK` の註）。
    #     `SystemExit` は `Exception` の子ではないので、そちらへは永久に来ません ——
    #     `scripts/live_slots.apply_moves` が同じ形で**尽きた窓の残り全部を
    #     撃ち続けて**いました。ここは `BaseException` で受けて、
    #     **止まるもの（日枠・計測のぶんの取り置き）と、飛ばすもの（1本ごとの失敗）**
    #     を分けます。
    done, stopped = 0, False
    for r in drop:
        try:
            # **撃たなかった回は、控えも動かさないこと**（2026-09-01。
            # `reschedule._update` は **False** を返す道が2つあり、片方
            # （`upload_cap.move_hold`）は **YouTube を1文字も変えていません**。
            # ここは長らく返りを見ずに `retime(None)` を撃っており、
            # **控えだけが「予約なし」になって、実物はそのまま公開されます。**
            # `--move` は 08-29 に直っていましたが、**ここと `--spread`/`--compact`
            # は素通りのまま**でした（この repo が通算12回 踏んでいる「片方だけ」）。
            # 実測（`src/ledger_truth.py` が 0単位 で数え直した）: **4本**。
            if not reschedule._update(svc, r["id"], None, fallback_status=fallback):
                print(f"[pool] {r['id']} は**撃っていないので、控えも直しません**"
                      "（控えだけ外すと、実物は予約のまま公開されます）", flush=True)
                continue
            dupes.retime(r["id"], None)
        except (KeyboardInterrupt, MemoryError):
            raise
        except BaseException as exc:                           # noqa: BLE001
            if reschedule.is_quota_exit(exc) or reschedule._is_quota(exc):
                print(f"[pool] **日枠が尽きました**（{done}本 外したところ）。"
                      " JST 16:00 に戻ります。", flush=True)
                stopped = True
                break
            if isinstance(exc, SystemExit):
                # **取り置き（`upload_cap.reserve_hold`）もここへ来ます。**
                # あれは「この窓ではもう書かない」という意味なので、**止まります**
                # —— 飛ばして次の本を撃つと、取り置きが取り置きになりません。
                print(f"[pool] **この窓ではもう書けません**（{done}本 外したところ）:"
                      f" {str(exc.code or exc)[:200]}", flush=True)
                stopped = True
                break
            print(f"[pool] [!] {r['id']} で落ちました（続けます）: {str(exc)[:120]}",
                  flush=True)
            continue
        done += 1
        if done % 10 == 0:
            print(f"[pool]   {done}/{len(drop)}本", flush=True)

    left = len(rows) - len(kept) - done
    print(f"[pool] **外した {done}本／まだ予約に残っている {left}本**"
          f"（残す {len(kept)}本 を入れると {left + len(kept)}本）", flush=True)
    print("[pool] **消していません。** 外した本は private のまま残っています"
          "（時刻を入れ直せば戻ります）。", flush=True)

    if left > 0 and not args.no_inbox:
        rec = inbox.add(_inbox_text(left, args.keep), source="pool_drain")
        print(f"[pool] 残件を受け取り帳に置きました: {rec['id']}"
              "（`python scripts/inbox.py` で見えます）", flush=True)
    return 1 if stopped else 0


if __name__ == "__main__":
    raise SystemExit(main())
