"""投稿済みの動画に、サムネイルを載せ直す。**入口は2つあります。**

    python scripts/refresh_thumbnail.py --missing [--long] [--force]
        **控えに残した bytes を、載っていない本すべてに押す**（2026-08-17 に追加）。
        `build/` は要りません。ふつうはこちらです

    python scripts/refresh_thumbnail.py --missing --video <動画ID>
        **その1本だけ押す**（50単位。2026-08-31 に追加）。
        `--missing` は実測 158本 ＝ 7,900単位 で、1日の枠のほとんどを持っていき、
        **池化（`pool_drain`）と取り合います。** いちばん急ぐのはいつも1本
        ——**次に公開される本**——なので、そこだけ押せる道を分けてあります

    python scripts/refresh_thumbnail.py <テーマID> <動画ID> <配色の番号>
        `build/<テーマID>/` から**作り直して**差し替える。
        サムネイルの作りそのものを変えたときだけ

## `--missing` を足した理由（**3回持ち越された項目**）

日枠が切れている13時間は `thumbnails.set` だけが 403 になり、
`videos.insert` は通ります。つまり**サムネイルの無い予約**が積まれます。

申し送りは3回とも「枠が戻った回に `refresh_thumbnail.py` を回すこと」と
書いていました。**その手順は実行できません。** 下の作り直しの道が読むのは
`build/<テーマID>/` ですが、**`build/` は .gitignore で、1周ごとに
コンテナごと消えます。** 枠が戻る JST 16:00 には、03時台に上げた本の
`build/` はとっくにありません。**不可能なことを3回頼み続けていました。**

そして**焼き直す必要はありません。** サムネイルは投稿の時点でもう出来ていて、
YouTube に載らなかっただけです。`scripts/critique_queue.stash()` が
bytes を `data/critique_queue/<動画ID>.thumb.jpg` に残すので、
**後の回は押すだけで済みます**（1本 約70KB）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from googleapiclient.discovery import build  # noqa: E402
from googleapiclient.http import MediaFileUpload  # noqa: E402

from src import auth, thumbnail, upload_cap, visuals  # noqa: E402
from src.auth import credentials  # noqa: E402


def main(topic: str, video_id: str, theme_index: int) -> int:
    work = Path("build") / topic
    slides = sorted((work / "slides").glob("slide_*.png"))
    if not slides:
        print(f"{work}/slides がありません")
        return 1

    script = json.loads((work / "script.json").read_text(encoding="utf-8"))
    theme = visuals.theme_for(topic, theme_index)
    accent = tuple(int(theme["accent"].lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))

    out = thumbnail.create(
        slides[len(slides) // 2],
        script["thumbnail_line1"], script["thumbnail_line2"],
        work / "thumbnail.jpg", work, accent=accent,
        kicker=script.get("thumbnail_kicker"),
    )
    print(f"[thumb] 作り直しました: {out} accent={theme['accent']}")

    # **1本だけの道もここを通ること**（2026-08-28）。
    # この行は、手で並べた検査からは**6つ目として抜けていました** ——
    # 数え上げに変えた `tests/test_quota_reserve.py` がその場で見つけています。
    # **絵はもう作ってあります**（上で `thumbnail.create`）。捨てないので、
    # 窓が変わった回に同じ1行で押し直せます。
    hold = upload_cap.reserve_hold()
    if hold:
        print(f"[thumb] {hold}")
        print(f"[thumb] **押しません。** 絵は {out} に残っています。"
              " 窓が変わった回に同じ1行で押し直すこと（`YT_NO_RESERVE=1` で外せます）。")
        return 1

    y = build("youtube", "v3", credentials=credentials(), cache_discovery=False)
    y.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(out))).execute()
    # **通ったら数えること**（2026-08-28。下の一括の口は数えていて、こちらは数えて
    # いませんでした —— 同じファイルの中で片方だけ）。
    upload_cap.note_quota_ok(detail=f"thumbnails.set {video_id}")
    print(f"[thumb] 差し替え完了: https://youtu.be/{video_id}")
    return 0


def _ledger_ahead() -> list:
    """これから公開される予定時刻（控えだけ・**API 0単位**）。"""
    from datetime import datetime, timezone

    from src import dupes as _dupes

    now = datetime.now(timezone.utc)
    out = []
    for r in _dupes.ledger_rows():
        at = r.get("at")
        if not at:
            continue
        try:
            t = datetime.fromisoformat(at.replace("Z", "+00:00"))
        except ValueError:
            continue
        if t > now:
            out.append(t)
    return sorted(out)


#: **長尺だけを押す道**（2026-08-27 16:xx に足した）。
#:
#: 下の「穴のほうが先」の門は、**ショートについては正しい** ——
#: 再生の 99.9% は `SHORTS_FEED` で、**そこにサムネイルは出ません。**
#: だから同じ50単位なら詰め直しのほうが効きます。
#:
#: **その理屈は長尺には掛かりません。** 長尺は `SHORTS_FEED` の枠を
#: 1つも使わず、**門2a（4,000時間）に入るのは長尺だけ**です。そして
#: `status.py` は「**面ではなく CTR が縛っている**」と印字しています ——
#: 面は合格点の 5.2倍 あるのに、**実測 CTR 1.44%**（要る CTR 19.2%）。
#: **サムネイルはその CTR そのもの**です。
#:
#: 実測 2026-08-27: サムネイルの無い 40本 のうち **10本が長尺**でした。
#: `day_cap.forms()` はこれを**0本**と答えます（571本 中 130本 しか
#: 覚えていないので、残りは「不明」に落ちる）。**尺は API に訊くこと**
#: （`videos.list` の `contentDetails`。50本で1単位）。
#:
#: この10本は **6周 続けて「段2 の本体」として申し送られながら、
#: 一度も押されていません** —— 門がショートの理屈で 40本まとめて
#: 止めていたからです。**群を分ければ、門は正しいまま通ります。**
LONG_FORM_SEC = 180


def _long_form_ids(video_ids: list[str]) -> set[str]:
    """**尺を API に訊く**（50本で1単位）。`forms()` の控えは当てにしません。"""
    import re as _re

    def _secs(d: str) -> int:
        m = _re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d or "")
        if not m:
            return 0
        h, mi, s = (int(x or 0) for x in m.groups())
        return h * 3600 + mi * 60 + s

    y = build("youtube", "v3", credentials=credentials(), cache_discovery=False)
    out: set[str] = set()
    for i in range(0, len(video_ids), 50):
        try:
            got = y.videos().list(part="contentDetails",
                                  id=",".join(video_ids[i:i + 50])).execute()
        except Exception as exc:                               # noqa: BLE001
            print(f"[thumb] 尺が読めませんでした: {str(exc)[:120]}")
            return out
        for it in got.get("items", []):
            if _secs(it["contentDetails"]["duration"]) >= LONG_FORM_SEC:
                out.add(it["id"])
    return out


def push_missing(dry_run: bool = False, force: bool = False,
                 only_long: bool = False, only_video: str = "") -> int:
    """控えに残した bytes を、載っていない本すべてに押す。**`build/` は要りません。**

    **予約に0本の日があるあいだは押しません**（2026-08-19。理由は
    `src/upload_cap.thumbnail_yield_to_schedule` の本文）。同じ50単位で
    詰め直しが1本できて、そちらのほうが `eta.py` の日付を動かすからです。
    `force=True` で今すぐ押せます。

    `only_long=True` は**長尺だけ**に絞り、その門を通しません
    （理由は `LONG_FORM_SEC` の上の註 —— あの門はショートの理屈です）。
    """
    import critique_queue

    rows = critique_queue.missing_thumbnail()
    if not rows:
        print("[thumb] サムネイルの載っていない本はありません")
        return 0

    # **1本だけ押す道**（2026-08-31 22:xx に足した）。
    #
    # `--missing` は控えに溜まったぶんを**全部**押します。実測 158本 ＝ 7,900単位で、
    # 1日の枠 10,000単位 のほとんどです。**池化（`pool_drain`）と取り合います。**
    #
    # ところが、いちばん急ぐのは**いつも1本**です ——
    # **次に公開される本**。09/01 22:00 に出る `UIWHsypOPPg` は、
    # 枠が戻る 16:00 から公開まで6時間しかなく、その1本に要るのは **50単位**です。
    # **「全部押す」か「1本も押さない」しか無いと、いちばん急ぐ1本が
    # 池化に負けます。**
    #
    # **覆る条件**: 枠のほうが広くなって取り合いが消えたら、この絞りは要りません。
    if only_video:
        rows = [r for r in rows if r["video_id"] == only_video]
        if not rows:
            print(f"[thumb] **{only_video} は控えにありません**"
                  "（サムネイルは載っている／控えが git に無い、のどちらか）")
            return 1
        print(f"[thumb] **{only_video} の1本だけ押します**（50単位）")

    if only_long:
        longs = _long_form_ids([r["video_id"] for r in rows])
        skipped = len(rows) - len(longs)
        rows = [r for r in rows if r["video_id"] in longs]
        print(f"[thumb] **長尺だけに絞りました**: {len(rows)}本"
              f"（ショート {skipped}本 は押しません —— `SHORTS_FEED` に"
              "サムネイルは出ないので、同じ単位なら詰め直しのほうが効きます）")
        if not rows:
            print("[thumb] サムネイルの載っていない長尺はありません")
            return 0

    print(f"[thumb] サムネイルの載っていない本: **{len(rows)}本**")
    for row in rows:
        print(f"  {row['video_id']}  {row['topic']}  ({row['stashed_at']})")
    if dry_run:
        print("[thumb] --dry-run なので押していません")
        return 0

    # **押す前に、観測した事実のほうを見る**（2026-08-17 22:4x に足した）。
    # 時計ではありません —— 単位枠は窓の中でこちらの `videos.insert` が
    # 使い切るので、**「窓が開いている」と「単位が残っている」は別の事実**です。
    q = upload_cap.day_quota()
    if not q.open:
        print(f"[thumb] {q.line}")
        print("[thumb] **押しません**（この窓では 5本とも 403 になるだけです）。"
              " 窓が変わってから、**投稿より先に**この1行を回すこと。")
        return 1

    # **穴のほうが先です**（2026-08-19 18:3x に測って足した）。ここは長らく
    # 「窓が開いていれば押す」でした。窓の単位は**詰め直しと取り合い**で、
    # 値段は同じ50単位、効きは桁で違います（再生の 99.9% は
    # サムネイルの出ない SHORTS_FEED）。**門は押す側に置いてあります** ——
    # `batch_build` にだけ置くと、`reschedule` から見えません。
    if not force and not only_long:
        okay, line = upload_cap.thumbnail_yield_to_schedule(_ledger_ahead(), len(rows))
        if not okay:
            print(f"[thumb] {line}")
            return 3
        print(f"[thumb] {line}")

    # **計測のぶんを残して止める**（2026-08-28 の最適化の回・2枚目）。
    #
    # すぐ上の `day_quota()` は **403 を実際に観測してから**閉じます。
    # `reserve_hold()` はその手前で止める門で、**別の事実を見ています** ——
    # 「まだ 403 は出ていないが、この窓で使った単位が実測の枠まであと
    # `RESERVE_UNITS` を切った」。**片方だけでは、最後の 400単位 を
    # ここが 50単位/本 で持っていけます**（8本で使い切ります）。
    #
    # **この口は `scripts/batch_build.py` が毎周 直接 呼びます**
    # （`refresh_thumbnail.push_missing()`）。門の付いた入口は
    # `reschedule._update` と `uploader._set_thumbnail` の2つで、
    # **ここは3つ目の、いちばん熱い入口でした。**
    #
    # 残しているのは**前提を閉じる読み**です（`videos.list` は 1単位）。
    # `eta.py`: 軌跡の腕が動くのは前提を1件 閉じたときだけ。
    hold = upload_cap.reserve_hold()
    if hold:
        print(f"[thumb] {hold}")
        print("[thumb] **押しません**（`--force` ではなく `YT_NO_RESERVE=1` で外せます）。"
              " 控えは消えないので、窓が変わった回に同じ1行で押し直せます。")
        return 1

    y = build("youtube", "v3", credentials=credentials(), cache_discovery=False)
    ok = 0
    for row in rows:
        # **輪の中でも訊くこと**（2026-08-28 の2周目に直した）。
        # 上の門は輪の**手前**に1回だけです。ここは1回で何十本も押す口なので、
        # 一度 通ると残りを全部 焼けます —— 門が読む `spent` は、
        # **この輪が自分で増やしている数**です。
        # **1回だけ訊く門は、増えていく数に対しては門になりません。**
        hold_now = upload_cap.reserve_hold()
        if hold_now:
            print(f"[thumb] {hold_now}")
            print(f"[thumb] **ここで止めます**（押せた {ok}本）。"
                  " 控えは消えないので、窓が変わった回に同じ1行で続けられます。")
            break
        try:
            y.thumbnails().set(
                videoId=row["video_id"],
                media_body=MediaFileUpload(str(row["thumb"])),
            ).execute()
        except Exception as exc:
            # **1本落ちても止めない。** 日枠がまだ戻っていないだけのことがあり、
            # そこで抜けると、押せるはずの残りまで押さずに終わります。
            print(f"[thumb] ✗ {row['video_id']}: {str(exc)[:160]}")
            # **403 は残すこと**（2026-08-17 22:4x に足した）。残さないと、
            # 次の回は「JST 16時を回ったから戻っているはず」と**時計で推測**します。
            # この回はそれで「いまなら潰せます」と言われ、**5本とも 403**でした。
            if auth.is_day_quota(exc):
                upload_cap.note_quota_hit(detail=f"thumbnails.set {row['video_id']}")
            continue
        # **押せた本だけ印を消す。** 消してから押すと、落ちた本が
        # 一覧から消えて二度と拾われません
        critique_queue.mark_thumbnail_set(row["video_id"])
        # **通ったことも残すこと**（2026-08-26）。403 のあとに通った呼び出しは、
        # **その 403 が日枠でなかった証拠**です（`upload_cap.note_quota_ok`）。
        try:
            upload_cap.note_quota_ok(detail=f"thumbnails.set {row['video_id']}")
        except Exception:                                      # noqa: BLE001
            pass
        ok += 1
        print(f"[thumb] ✓ {row['video_id']}  https://youtu.be/{row['video_id']}")
    print(f"[thumb] **{ok} / {len(rows)} 本に載せました**")
    return 0 if ok == len(rows) else 1


if __name__ == "__main__":
    if "--missing" in sys.argv:
        _only = ""
        if "--video" in sys.argv:
            _i = sys.argv.index("--video")
            if _i + 1 >= len(sys.argv):
                print("--video のあとに動画IDを書くこと")
                raise SystemExit(2)
            _only = sys.argv[_i + 1]
        raise SystemExit(push_missing(dry_run="--dry-run" in sys.argv,
                                      force="--force" in sys.argv,
                                      only_long="--long" in sys.argv,
                                      only_video=_only))
    if len(sys.argv) != 4:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1], sys.argv[2], int(sys.argv[3])))
