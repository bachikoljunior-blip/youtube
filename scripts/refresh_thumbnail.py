"""投稿済みの動画に、サムネイルを載せ直す。**入口は2つあります。**

    python scripts/refresh_thumbnail.py --missing [--long] [--force]
        **控えに残した bytes を、載っていない本すべてに押す**（2026-08-17 に追加）。
        `build/` は要りません。ふつうはこちらです

    python scripts/refresh_thumbnail.py --missing --video <動画ID> [--replace]
        **その1本だけ押す**（50単位。2026-08-31 に追加）。
        **`--replace` は「絵が既に載っている本」を差し替える**（2026-09-05 に追加）——
        `--missing` の一覧は `thumbnail_set is False` の本しか返さないので、
        **焼き上がって絵まで載った本（＝規則3 が良くし続けろと言う次の枠の1本）は
        `--replace` 無しでは押せません。**
        `--missing` は実測 158本 ＝ 7,900単位 で、1日の枠のほとんどを持っていき、
        **池化（`pool_drain`）と取り合います。** いちばん急ぐのはいつも1本
        ——**次に公開される本**——なので、そこだけ押せる道を分けてあります

    python scripts/refresh_thumbnail.py <テーマID> <動画ID> <配色の番号>
        `build/<テーマID>/` から**作り直して**差し替える。
        サムネイルの作りそのものを変えたときだけ（**`build/` が要る ＝ 同じ回だけ**）

    python scripts/refresh_thumbnail.py --rebuild <動画ID>
        **控えだけから作り直して、控えの `<ID>.thumb.jpg` を差し替える**（API 0単位・
        2026-09-03 に追加）。`build/` の無い後の回で、絵の作り（`src/thumbnail.py`）を
        直したときはこちら。載せるのは窓が戻った回の `--missing --video <ID>`

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

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from googleapiclient.discovery import build  # noqa: E402
from googleapiclient.http import MediaFileUpload  # noqa: E402

from src import auth, thumbnail, upload_cap, visuals  # noqa: E402
from src.auth import credentials  # noqa: E402


def topic_style(topic_id: str) -> str:
    """`config/topics.yaml` の `style:`（`outside_long` など）。無ければ空。**API 0単位。**"""
    try:
        from src import config as _config                        # noqa: PLC0415
        for t in _config.load_topics().get("topics") or []:
            if str(t.get("id")) == topic_id:
                return str(t.get("style") or "")
    except Exception:                                          # noqa: BLE001
        pass
    return ""


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
        style=topic_style(topic),
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


#: 控えに公開時刻の無い本を、いちばん後ろへ送るための番兵（秒）。
_FAR_SECONDS = float("inf")


def publish_times() -> dict:
    """**本ID → 予定の公開時刻**（控えだけ・**API 0単位**）。

    `_ledger_ahead()` は時刻の一覧しか返しません（門が本数だけ見るので足りていた）。
    **どの本がいつ出るか**が要るのは `order_by_publish()` です。
    """
    from datetime import datetime, timezone

    from src import dupes as _dupes

    out: dict = {}
    for r in _dupes.ledger_rows():
        at, vid = r.get("at"), r.get("id")
        if not at or not vid:
            continue
        try:
            t = datetime.fromisoformat(str(at).replace("Z", "+00:00"))
        except ValueError:
            continue
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        out[vid] = t
    return out


def order_by_publish(rows: list[dict], times: dict | None = None,
                    now=None) -> list[dict]:
    """**まだ出ていない本を先に、公開の早い順**に並べ替える（API 0単位）。

    ## なぜ足したか（2026-09-01）

    `critique_queue.missing_thumbnail()` は `sorted(STASH.glob("*.json"))` ——
    **本IDのアルファベット順**です。公開時刻とは何の関係もありません。

    **押しきれずに止まる回のほうが、押しきる回より多い**（この輪には
    `day_quota()` ／ `thumbnail_yield_to_schedule()` ／ `reserve_hold()` の
    3つの門があり、輪の**中**でも毎本 訊きます）。
    **途中で止まる前提の輪が、順番を持っていませんでした。**

    実測 2026-09-01: 控えに **158本**（7,900単位）。日枠は 10,000単位/日 で、
    同じ枠を池化（`scripts/pool_drain.py`・残り 13,617単位）と取り合っています。
    **どこで切れても、次に公開される本から順に載っている**のが正しい形です。

    **これは止める仕掛けではありません。** 押す本数も、押す条件も変えません
    —— **順番だけ**です（`CLAUDE.md`「作りに問題を見つけたら、止めるのではなく
    直すこと」）。

    **`--video` の1本絞りは、この上に残ります。** あちらは
    「いちばん急ぐ1本を、取り合いに負けさせない」ための手で、
    **こちらは絞らなかった回のための順番**です。片方だけでは足りません ——
    `--video` は**撃つ側が思い出したときにしか効かない**からです
    （`batch_build.slots()`「人の記憶と手写しに依存する門は、この輪では毎回落ちる側」）。

    ## **順は3段です。「公開の早い順」ひとつでは足りません**

        1. **まだ出ていない本**  …… 公開の**早い順**
        2. **もう出た本**        …… 公開の**新しい順**
        3. 控えに時刻の無い本    …… 最後

    **1 と 2 を1本の物差しで並べると、2 が先に来ます**（過去のほうが早い）。
    それは逆です —— **サムネイルは、公開の山が来る前に載っていないと効きません。**

    `src/settle.py` の実測: ショートは **48時間で伸びきり**（96.2%）、
    長尺も 96時間で 62.5%。**3日前に出た本の山は、もう終わっています。**
    まだ出ていない本は**一生ぶんが丸ごと先**にあり、
    出た本は**残りだけ**です。だから 2 の中も**新しい順**（山が残っている順）。

    実測 2026-09-01: 控えの 158本 のうち、**130本 は控えに時刻があり、
    そのほとんどが未来**（09/14〜09/28）。**古い順に並べると、
    もう山の終わった 08/28 の本から押し始めます。**

    **覆る条件**: `missing_thumbnail()` 自身が公開時刻を持つようになったら、
    並べ替えはあちらへ移すこと（**2か所で並べないこと**）。
    そして `settle` が「長尺は何日たっても伸びる」と出し直したら、
    2段目の向きを見直すこと（そのときは古い本にもまだ山が残っている）。
    """
    import datetime as _dt

    times = publish_times() if times is None else times
    now = now or _dt.datetime.now(_dt.timezone.utc)

    def key(r: dict):
        t = times.get(r.get("video_id"))
        if t is None:
            return (2, _FAR_SECONDS)
        d = (t - now).total_seconds()
        if d > 0:
            return (0, d)          # まだ出ていない → 早い順
        return (1, -d)             # もう出た → 新しい順（-d が小さいほど新しい）

    return sorted(rows, key=key)


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


def stash_row(video_id: str) -> dict | None:
    """**控えに在る絵を、`missing_thumbnail()` を通さずに1本ぶん返す**（**API 0単位**）。
    無ければ `None`。返す形は `missing_thumbnail()` の1行と同じ。

    `missing_thumbnail()` は `thumbnail_set is False` の本しか返しません
    ——「まだ載っていない本を押す」ための一覧だからです。
    **既に載っている本の絵を差し替える道が、そこには在りません。**
    """
    import critique_queue                                       # noqa: PLC0415
    vid = str(video_id or "").strip()
    if not vid:
        return None
    thumb = critique_queue.STASH / f"{vid}.thumb.jpg"
    if not thumb.exists():
        return None
    meta = {}
    meta_path = critique_queue.STASH / f"{vid}.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            meta = {}
    return {"video_id": vid, "topic": meta.get("topic"),
            "thumb": thumb, "stashed_at": meta.get("stashed_at")}


def push_missing(dry_run: bool = False, force: bool = False,
                 only_long: bool = False, only_video: str = "",
                 replace: bool = False) -> int:
    """控えに残した bytes を、載っていない本すべてに押す。**`build/` は要りません。**

    **予約に0本の日があるあいだは押しません**（2026-08-19。理由は
    `src/upload_cap.thumbnail_yield_to_schedule` の本文）。同じ50単位で
    詰め直しが1本できて、そちらのほうが `eta.py` の日付を動かすからです。
    `force=True` で今すぐ押せます。

    `only_long=True` は**長尺だけ**に絞り、その門を通しません
    （理由は `LONG_FORM_SEC` の上の註 —— あの門はショートの理屈です）。

    `only_video=<動画ID>` も**その門を通しません**（2026-09-01）。
    門は値段の比べで、1本（50単位）は門が勧める代替（穴の数 × 50単位）より
    安いので、比べが逆さまになります。**門の呼び出しの上の註**に実測。
    """
    import critique_queue

    rows = critique_queue.missing_thumbnail()
    # **既に載っている絵を、控えの新しい絵で差し替える道**（2026-09-05 に足した）。
    #
    # `rebuild_stash()`（`--rebuild`）の註は「載せるのは窓が戻った回の
    # `--missing --video <ID>`」と名指ししています。**その1行は、絵が既に
    # 載っている本には効きません** —— `missing_thumbnail()` が返すのは
    # `thumbnail_set is False` の本だけなので、**焼き上がって絵まで載った本
    # （＝ まさに規則3 が「次の枠まで良くし続けろ」と言っている本）は
    # 一覧に出ず、`--missing --video <ID>` は「控えにありません」で 1 を返します。**
    # 実測 2026-09-05 00:5x: 09/05 09:00 に出る `GFvAcxvDmYM` の 2行目を
    # 帯の実測（相手の名指し ×54〜68・n=32〜34）に合わせて差し替え、
    # `--rebuild` で控えの絵を焼き直したところで、載せる道が無かった。
    #
    # ＝ **手順が名指ししている1行が、その相手には実行できない。**
    # この repo でいちばん多い壊れ方（言っている所と、している所が別）です。
    #
    # `--replace --video <ID>` は `missing_thumbnail()` を通さず、控えの
    # `<ID>.thumb.jpg` を1本ぶん押します。**門は1つも外しません**
    # （`day_quota` / `reserve_hold`・`only_video` の枝をそのまま通る）。
    # **束には渡しません** —— `--video` が要ります。
    #
    # **覆る条件**: `missing_thumbnail()` が「載っているが控えのほうが新しい」を
    # 返すようになったら、この枝は要りません（そのとき `--replace` を消すこと）。
    if replace:
        if not only_video:
            print("[thumb] `--replace` には `--video <動画ID>` が要ります"
                  "（束には渡しません）")
            return 2
        if not any(r["video_id"] == only_video for r in rows):
            row = stash_row(only_video)
            if row is None:
                print(f"[thumb] **{only_video} の絵が控えにありません**"
                      f"（`data/critique_queue/{only_video}.thumb.jpg`）。"
                      " 先に `--rebuild` で焼き直すこと")
                return 1
            print(f"[thumb] **{only_video} は既に絵が載っています** —— "
                  "控えの新しい絵で**差し替え**ます（50単位）")
            rows = rows + [row]
    if not rows:
        # **`--video` を指して空だったときは、そう言うこと**（2026-09-05）。
        # 「載っていない本はありません」と 0 を返すと、**押せたのか押していないのかが
        # 呼んだ側から区別できません**（`--replace` を忘れた回がここに落ちます）。
        if only_video:
            print(f"[thumb] **{only_video} は控えにありません**"
                  "（サムネイルは載っている／控えが在庫に無い、のどちらか）。"
                  " **既に載っている絵を差し替えるなら `--replace` を付けること**")
            return 1
        print("[thumb] サムネイルの載っていない本はありません")
        return 0

    # **公開が早い順に押すこと**（2026-09-01 に足した。`order_by_publish()` に理由）。
    # この輪は**途中で止まる前提**（門が3つ・輪の中でも毎本 訊く）なのに、
    # 一覧は**本IDのアルファベット順**でした。どこで切れても、
    # **次に公開される本から順に載っている**のが正しい。
    rows = order_by_publish(rows)

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
    # **`--video` の1本は、この門を通しません**（2026-09-01 に踏んだ。**実測**）。
    #
    # この門は「7,900単位（158本）を、450単位（穴9本の移動）に譲れ」という
    # **値段の比べ**です。**1本だけの道では、その比べが逆さまになります** ——
    # `--video` は **50単位**で、門が代わりに勧める移動は **450単位**。
    # 止めているほうが 9分の1 安く、譲る先は存在しません。
    #
    # 実測 2026-09-01 05:5x（`schedule_holes()` を撃った）: 穴は **9日**
    # （09/03〜09/11）。§1 の印が「枠の戻る 16:00 に、これを撃つこと」と
    # 名指しで印字している1行
    #
    #     python scripts/refresh_thumbnail.py --missing --video UIWHsypOPPg
    #
    # は、**この門で必ず 3 を返して1本も押しません。** その本は同じ日の
    # 22:00 JST に公開されます —— **印字された手順が、そのままでは効かない。**
    #
    # **穴には締切がありません**（いちばん早い 09/03 でも2日先）。
    # **この1本には 16時間 しかありません。** 門は値段しか見ないので、
    # 締切の差はどこにも入りませんでした。
    #
    # `only_long` を通していたのと同じ形です（あちらは「ショートの理屈だから」、
    # こちらは「比べが逆さまだから」）。**`--force` で外せ、とは書きません** ——
    # `batch_build.slots()`「**人の記憶と手写しに依存する門は、この輪では
    # 毎回落ちる側**」。同じ理由で `order_by_publish()` も入れてあります。
    #
    # **覆る条件**: `--video` が2本以上を受けるようになったら、
    # ここも `len(rows) * 50 < 穴の数 * 50` の比べに直すこと
    # （1本のあいだは、その比べは必ず通ります）。
    if not force and not only_long and not only_video:
        okay, line = upload_cap.thumbnail_yield_to_schedule(_ledger_ahead(), len(rows))
        if not okay:
            print(f"[thumb] {line}")
            return 3
        print(f"[thumb] {line}")
    elif only_video and not force and not only_long:
        _holes = upload_cap.schedule_holes(_ledger_ahead())
        if _holes:
            print(f"[thumb] 予約に0本の日が {len(_holes)}日 ありますが、"
                  f"**この1本（50単位）は通します** —— 埋めるのに要るのは"
                  f" {len(_holes)}本の移動（{len(_holes) * 50:,}単位）で、"
                  "**止めているほうが安い**。穴に締切はありませんが、"
                  "次に公開される本にはあります")

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
    # --- **次に出る1本の 50単位 は、取り置きの中から通す**（2026-09-02 に踏んだ）---
    #
    #     この門の返り文は、自分でこう名指しします ——
    #     「残しているのは、前提を閉じる読みと**次の1本を良くする書き込み**
    #       （`improve`・50単位）のためです」。
    #     そして同じ回に、**まさにその 50単位** を止めました。
    #     取り置きはただの床で、**誰が撃つかを1文字も見ていません。**
    #
    #     渡すのは「`--video` で1本だけ」かつ「その1本が**次に出る本**」のときだけ。
    #     束（`--missing` の全本・実測 158本 ＝ 7,900単位）には渡しません。
    #     見分けは `src.next_slot`（**API 0単位**）——
    #     予約ずみなら `next_video()`、規則5 で予約がまだ無ければ `drafts()` の先頭。
    _improve_one = False
    if only_video and not only_long:
        try:
            from src import next_slot as _ns                    # noqa: PLC0415
            _nxt = _ns.next_video()
            _ids = {str((_nxt or {}).get("video_id") or "")}
            _ids |= {str(r.get("video_id") or "") for r in _ns.drafts()[:1]}
            _improve_one = only_video in (_ids - {""})
        except Exception as exc:                                # noqa: BLE001 — 止めない
            print(f"[thumb] 次に出る1本を見分けられませんでした: {str(exc)[:80]}")
    if _improve_one:
        print("[thumb] **これは「次に出る1本」です** —— "
              "取り置き（`RESERVE_UNITS`）から 50単位 だけ通します"
              "（`upload_cap.IMPROVE_UNITS`）。束には渡しません")
    hold = upload_cap.reserve_hold(improve_one=_improve_one)
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


def _thumb_text(video_id: str, topic: str, stash: Path) -> tuple[dict | None, str]:
    """**サムネの2行と kicker を、在る所から拾う。**（`(字, 出どころ)`・**API 0単位**）

    ## なぜ要るか（2026-09-05 07:xx に、きょうの枠の本で踏んだ）

    `rebuild_stash()` は `<ID>.script.json` **だけ**を読んでいました。その控えを
    残すようになったのは **2026-09-02**（`scripts/critique_queue.stash()` の註）で、
    それより前に上げた本には在りません。**この回に数えた実物**::

        控えの本            712本
        `<ID>.script.json`   **14本**（2.0%）
        `<ID>.plan.json`    672本
        絵は在るのに焼き直せない本  **566本**

    ＝ **`--rebuild` は、控えの 98% に対して「控えが足りません」と言って
    何もしない道具**でした。`scripts/run_marker.py --write` が毎周 印字している

        サムネは `refresh_thumbnail.py --rebuild <ID>` → `--missing --video <ID> --replace`

    は、**ほとんどの本で1手目から落ちます。**

    実際に踏んだ形（きょうの枠の本 `qyVdpAoT_40`・題材 `s-shokibo-241kagetsu-9man4500`）:
    05:58 にきょうだいの回が題を「【小規模企業共済】240か月と241か月で税額はいくら違う？」へ
    入れ替えました（帯でいちばん厚い特徴 `【】`×5.52・`？`×2.39）。**絵のほうは
    2026-08-19 の控えのままで、`--rebuild` は「控えが足りません」で止まります。**
    ＝ **題だけが動いて、絵が置いていかれる形が、道具の側で塞がっていませんでした。**

    ## 拾う順（**上から、在った所で止まる**）

        1. `data/critique_queue/<ID>.script.json`   ← 09-02 以降の本。**いちばん強い**
        2. `data/scripts/<題材>.script.json`        ← 焼き直しが書き戻す所（`ahead_sweep`）
        3. `data/critique_queue/<ID>.plan.json`     ← **08-17 以降の 672本**。下の組み立て

    3 の組み立ては、**コマの実物からしか採りません**（推測を混ぜない）:

        line1  最初の「数が入っているコマ」の `stat`（例 `9万4500円`）
        line2  そのコマの `headline`（`　2/2` のような枝番は落とす）
        kicker そのコマの `note`（前提。無ければ空）

    **`stat` が1つも無い本は `None` を返します** —— 数の出ない絵を作るくらいなら、
    **焼き直さないほうが正しい**（`thumbnail.create` は空の行でも絵を作ってしまう）。

    ## 覆る条件

    - `<ID>.script.json` が全部の本に揃ったら（＝ 09-02 より前の本を上げ直したら）、
      2 と 3 は要らなくなります。**そのときは数を見て落とすこと**
      （`ls data/critique_queue/*.script.json | wc -l` が控えの本数に届いたら）。
    - `thumbnail.create` の引数（2行 ＋ kicker）が変わったら、3 の組み立ても一緒に。
    - **3 で焼いた絵は、`<ID>.script.json` から焼いた絵と同じではありません** ——
      元の絵の字は控えに残っていないので、**戻せません**。載せる前に
      `data/critique_queue/<ID>.thumb.jpg` を目で見ること（`Read` で開ける）。
    """
    p = stash / f"{video_id}.script.json"
    if p.exists():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:                   # noqa: PERF203
            return None, f"`{p.name}` が読めません（{str(exc)[:40]}）"
        if d.get("thumbnail_line1"):
            return d, f"`{p.name}`（台本の控え）"
    if topic:
        p2 = ROOT / "data" / "scripts" / f"{topic}.script.json"
        if p2.exists():
            try:
                d = json.loads(p2.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                d = {}
            if d.get("thumbnail_line1"):
                return d, f"`data/scripts/{topic}.script.json`（手元の台本）"
    p3 = stash / f"{video_id}.plan.json"
    if not p3.exists():
        return None, f"`{video_id}.script.json` も `{video_id}.plan.json` も在りません"
    try:
        plan = json.loads(p3.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"`{p3.name}` が読めません（{str(exc)[:40]}）"
    if not isinstance(plan, list):
        return None, f"`{p3.name}` がコマの並びではありません"
    for slide in plan:
        if not isinstance(slide, dict):
            continue
        stat = str(slide.get("stat") or "").strip()
        if not stat:
            continue
        head = str(slide.get("headline") or "").strip()
        # `小規模企業共済 241か月目　2/2` のような枝番は、絵に入れない
        head = head.split("　")[0].strip()
        return ({"thumbnail_line1": stat,
                 "thumbnail_line2": head,
                 "thumbnail_kicker": str(slide.get("note") or "").strip() or None},
                f"`{p3.name}`（コマの実物から組み立て・**元の字とは違います**）")
    return None, f"`{p3.name}` に数の入ったコマが1枚もありません"


def rebuild_stash(video_id: str, topic: str | None = None) -> int:
    """控えだけから絵を焼き直して、控えの `<ID>.thumb.jpg` を差し替える（**API 0単位**）。

    `main()` は `build/<テーマID>/slides` を読みますが、あれは .gitignore で
    まっさらな容器には在りません（2026-09-03 に踏んだ）。控えには
    `<ID>.jpg`（コマの一覧・背景の素材にはこれで足りる —— `_base_image` は
    80px まで潰すので字形は残らない）と `<ID>.script.json`（2行と kicker）が在るので、
    **絵の作り（`src/thumbnail.py`）を直した回は、焼き直さずにこれで控えを更新できます。**
    載せるのは、窓が戻った回の `--missing --video <ID>`（50単位）。
    """
    stash = ROOT / "data" / "critique_queue"
    src_img, script_path = stash / f"{video_id}.jpg", stash / f"{video_id}.script.json"
    meta_path = stash / f"{video_id}.json"
    if not src_img.exists():
        print(f"[thumb] 控えのコマがありません: {src_img.name}")
        return 1
    if topic is None and meta_path.exists():
        topic = str(json.loads(meta_path.read_text(encoding="utf-8")).get("topic") or "")
    topic = topic or ""
    script, where = _thumb_text(video_id, topic, stash)
    if script is None:
        print(f"[thumb] 絵の字が、どこからも取れません（{where}）")
        return 1
    print(f"[thumb] 絵の字の出どころ: {where}")
    work = ROOT / "build" / "_rebuild" / video_id
    work.mkdir(parents=True, exist_ok=True)
    theme = visuals.theme_for(topic, None)
    accent = tuple(int(theme["accent"].lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    out = thumbnail.create(
        src_img, script["thumbnail_line1"], script["thumbnail_line2"],
        work / "thumbnail.jpg", work, accent=accent,
        kicker=script.get("thumbnail_kicker"), style=topic_style(topic),
    )
    dest = stash / f"{video_id}.thumb.jpg"
    dest.write_bytes(out.read_bytes())
    print(f"[thumb] 控えの絵を焼き直しました: {dest}（{dest.stat().st_size:,} bytes・"
          f"style={topic_style(topic) or '既定'}）。載せるのは窓が戻った回の "
          f"`--missing --video {video_id}`（50単位）")
    return 0


if __name__ == "__main__":
    if "--rebuild" in sys.argv:
        _i = sys.argv.index("--rebuild")
        if _i + 1 >= len(sys.argv):
            print("--rebuild のあとに動画IDを書くこと")
            raise SystemExit(2)
        raise SystemExit(rebuild_stash(sys.argv[_i + 1]))
    if "--missing" in sys.argv:
        _only = ""
        if "--video" in sys.argv:
            _i = sys.argv.index("--video")
            if _i + 1 >= len(sys.argv):
                print("--video のあとに動画IDを書くこと")
                raise SystemExit(2)
            _only = sys.argv[_i + 1]
        raise SystemExit(push_missing(dry_run="--dry-run" in sys.argv,
                                      replace="--replace" in sys.argv,
                                      force="--force" in sys.argv,
                                      only_long="--long" in sys.argv,
                                      only_video=_only))
    if len(sys.argv) != 4:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1], sys.argv[2], int(sys.argv[3])))
