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
        if not house_rule.is_stockpile({**row, "video_id": row["id"]},
                                       today=now.astimezone(
                                           timezone(timedelta(hours=9))
                                       ).strftime("%Y-%m-%d")):
            continue
        out.append({"id": row["id"], "at": at,
                    "title": row.get("title", ""), "topic": row.get("topic", "")})
    out.sort(key=lambda r: r["at"])
    return out


def plan(rows: list[dict], keep: int) -> tuple[list[dict], list[dict]]:
    """**残す本と、外す本**に割る（API 0単位）。公開時刻の早い順に `keep` 本を残す。"""
    keep = max(0, keep)
    return rows[:keep], rows[keep:]


def by_day(rows: list[dict]) -> dict[str, int]:
    """日（JST）ごとの本数。**「1日 何本 公開され続けるか」を数字で残すため。**"""
    jst = timezone(timedelta(hours=9))
    out: dict[str, int] = {}
    for r in rows:
        key = r["at"].astimezone(jst).strftime("%Y-%m-%d")
        out[key] = out.get(key, 0) + 1
    return out


def _inbox_text(left: int, keep: int) -> str:
    return (
        "予約の池化が途中です（Data API の日枠）。"
        f"**まだ {left}本 が予約に残っています。**"
        " 日枠が戻ったら `python scripts/pool_drain.py --apply"
        f" --keep {keep}` を撃って続けること。"
        "（オーナーの規則 2026-08-31: 動画は1日一本・作り置きなし。"
        "外した本は private のまま残る＝下書きの池。**消さないこと。**）"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="予約を外して private のまま残し、下書きの池にする")
    ap.add_argument("--apply", action="store_true",
                    help="実際に外す（**付けないと数えるだけ・API 0単位**）")
    ap.add_argument("--keep", type=int, default=house_rule.PUBLISH_PER_DAY,
                    help="先頭の N本 は予約のまま残す"
                         f"（既定 {house_rule.PUBLISH_PER_DAY} ＝ 規則1の1日ぶん）")
    ap.add_argument("--max", type=int, default=0,
                    help="この回で外す上限（0 ＝ 日枠が尽きるまで）")
    ap.add_argument("--no-inbox", action="store_true",
                    help="途中で止まっても受け取り帳に置かない")
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
    if args.max > 0:
        drop = drop[:args.max]
    print(f"[pool] 残す **{len(kept)}本**／外す **{len(drop)}本**"
          f"（見積り {len(drop) * UNITS_PER_VIDEO:,}単位）", flush=True)
    for r in kept:
        print(f"[pool]   残す: {r['at'].isoformat()}  {r['id']}  {r['title'][:40]}",
              flush=True)
    if not drop:
        print("[pool] **外すものはありません。**（池化は済んでいます）", flush=True)
        return 0
    if not args.apply:
        print("[pool] **数えただけです**（API 0単位）。撃つには `--apply`。", flush=True)
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
            reschedule._update(svc, r["id"], None, fallback_status=fallback)
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
