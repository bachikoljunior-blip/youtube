"""**1日に投稿できる本数の枠**を、撃つ前に見る（API を 1単位も使わない）。

## なぜ要るか（2026-08-17 10:5x に踏み、11:0x に測って足した）

投稿を止める枠は2つあります。**片方しか数えていませんでした。**

    Data API の日枠   10,000単位   403 quotaExceeded     読み・`thumbnails.set` が落ちる
    投稿の本数枠      **1日92本**   429 rateLimitExceeded  **`videos.insert` そのものが落ちる**

`src/auth.is_upload_cap` は**当たったこと**を見分けます。この本文が足すのは
**当たる前に言うこと**です。10:5x の回はこう終わりました ——

    1本目  通った
    2〜7本目  **6本とも 429**（作った6本は `build/` ごと消えた）

`batch_build` は 429 を見てから止まるので、**止まるのは「作り終えたあと」**です。
その回の (a2) 問い3 がそのまま次の1手を書いていました ——

> **控え（`data/uploaded.jsonl`）に投稿した時刻を持たせる。**
> いま控えが持っているのは `at`（公開予定時刻）だけで、**いつ投稿したかを
> 持っていません。** だから「この枠の日に、あと何本撃てるか」を撃つ前に言えません。

**`--date` が空き時刻を控えから読むのと同じ形**で、材料だけが欠けていました。

## 2つの目盛りがあり、**確かさが違います**

1. **観測した 429**（`data/upload_cap.jsonl`）。**これは確実です。**
   当たった時点でその窓は閉じており、**残りは必ず全部落ちます**（実測 6/6）。
2. **控えの本数**（`uploaded_at` を持つ行）。**下限しか言えません** ——
   この欄を足す前に上げた行は数えられず、口の外（手や別の道具）で上げた本も入りません。

だから **`remaining` は上限側の見積り**です。**外す向きは「まだ撃てる」と言うほう**で、
そのときは今までどおり 429 を見て止まります（**悪化しません**）。
逆に閉じているのに「撃てる」と言うことは 1 では起きません。

**`status.py` と `batch_build` の両方がこの1か所を読むこと。**
この repo で通算9回出ている「**片方だけ**」を避けるため、窓の計算も本数の数えも
呼ぶ側に書かないこと。
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

# **観測した最大です。上限そのものではありません**（2026-08-17 11:4x に直した）。
#
# 10:5x の回は「92本目までは通り、93本目で 429」と書きました。ところが控えに
# `uploaded_at` を埋め戻したら、**同じ窓で成功した insert が 97本**ありました。
# **2つは食い違っています。** 控えの1行＝成功した `videos.insert` 1回なので
# （失敗した回は `remember()` まで来ない）、**少なくとも97本は通っています。**
#
# **食い違いを、投稿を止める側へ倒さないこと。**
#
#     低く置きすぎる → まだ撃てるのに作らない → **毎日その差だけ投稿が減る**
#     高く置きすぎる → 撃って 429 → 作った1本を捨てる（**今までの振る舞い**）
#
# 前者のほうが高い（**投稿が途切れるのが最大の損失**）ので、
# **観測した最大に合わせます。** 本当の上限を決めているのは、いつも
# **観測した 429 のほう**です（`hits_in_window`）。ここは目安にすぎません。
#
# **次に 429 を観測した回は、その窓の `counted()` を日誌に残すこと。**
# 点が増えれば、本当の上限が挟めます。
#
# **2点目**（2026-08-19 19:5x）: **`counted()` は 28 で当たりました。**
#   ＝ この枠は**固定ではありません。** 08/17 の窓は 97本まで通り、
#   08/19 の窓は **28本で閉じました**（3.5分の1）。**平均も上限も知りません。**
#   だから `CAP_PER_DAY` は**上限の目安であって、残量の根拠ではありません** ——
#   `state()` の「あと N本」は「まだ撃てるかもしれない」の意味で、
#   **「あと N本は撃てる」ではありません。**
#   **数字を下げないのは上の理由のまま**です（低く置くと、通る日に投稿が減る）。
#   当たったときに**その場で止まって観測を残す**ほうで受けます
#   （`src/auth.is_upload_cap`。2026-08-19 に**2つ目の形**を足しました ——
#   **400 `uploadLimitExceeded`**。これが素通りしていたので、この2点目は
#   **危うく残らないところ**でした）。
CAP_PER_DAY = 97

# 枠の頭は**太平洋時間の0時**です。JST 16:00 と書いてある文書が多いのは、
# 夏（PDT ＝ UTC-7）にそう見えるからで、**冬は JST 17:00 になります。**
# だから固定の時差ではなく tz 名で持ちます（`zoneinfo` は動作を確認済み）。
PT = ZoneInfo("America/Los_Angeles")
JST = timezone(timedelta(hours=9))

HITS = "data/upload_cap.jsonl"

#: **Data API の日枠（10,000単位）を使う道具**（2026-08-27 に、ここへ集めた）。
#:
#: 申し送りや前提の `refresh:` がこの道具を名指ししているなら、
#: **日枠が尽きている窓では、その手はその時刻に打てません。**
#: 撃ちに行った回は 403 を1つ買って帰るだけです。
#:
#: ## なぜ `upload_cap` に置くか
#:
#: **日枠という事実の持ち主がここだから**です（`day_quota()` / `quota_hits_in_window()`）。
#: この一覧は 2026-08-27 に `scripts/deadline_check.py` の中で
#: `_DATA_API_REFRESH` として生まれ、**同じ日のうちに読み手が3つになりました**
#: （`deadline_check` の門・`src/day_cap.readable_at()`・`scripts/retro.py` の持ち越し）。
#: **写しを3つ作らないため**に、事実の側へ寄せています。
#:
#: ## 足すときは、中身を確かめること
#:
#: **Analytics API と Reporting API は別の枠**です。ここに入れると、
#: 読めるのに「読めません」と言う側に外れます。入れてよいのは
#: `youtube.googleapis.com/youtube/v3` を叩く道具だけ:
#:
#:     scripts/snapshot.py          videos.list
#:     scripts/refresh_thumbnail.py thumbnails.set / videos.list
#:     scripts/reschedule.py        videos.update / videos.list
#:     src/channel_page.py          channels.update（`python -m src.channel_page`）
#:     scripts/live_slots.py        `reschedule.main(["--move", …])` 越し
#:     scripts/queue_lag.py         同上（`--apply`）
#:
#: **`videos.insert`（投稿そのもの）はここに入りません** ——
#: 日枠が尽きていても通ります（2026-08-17 に実測・以後3度)。
DATA_API_TOOLS = (
    "scripts/snapshot.py",
    "scripts/refresh_thumbnail.py",
    "scripts/reschedule.py",
    "src.channel_page",
    "src/channel_page.py",
    "scripts/live_slots.py",
    "scripts/queue_lag.py",
)

# **Data API の単位枠（10,000単位）を観測した記録**（2026-08-17 22:4x に足した）。
#
# 本数枠（上）と**同じ窓・同じ形**ですが、**別々に閉じます**。だから帳面も別です。
#
# ## なぜ要るか（この回に実際に踏んだ）
#
# `retro.py` の `quota_is_back()` は **「JST 16時を回っていれば戻っている」**
# という**時計だけの模型**でした。ところが単位枠は、**こちらの投稿そのものが
# 使い切ります** —— `videos.insert` は 1回 1,600単位なので、**7本で 11,200単位**。
# **窓の中で誰が使うかを、模型が持っていませんでした。**
# 1周ごとに7〜8本上げているので、**窓が開いた直後の1周で使い切ります。**
#
# この回の実測（22:41 JST ＝ 窓が開いて 6.7時間後）:
#
#     quota_is_back()                    → True（「いまなら潰せます」と出た）
#     refresh_thumbnail.py --missing      → **5本とも 403**
#
# 時計は「戻っている」と言い、実物は閉じていました。`missing_thumbnail` が
# **15回鳴って当たり2回**なのはこれで、一覧が悪いのではなく
# **「潰せる」と言う側が、確かめずに言っていた**わけです。
# （`docs/trigger_main.md` の「一覧が当たりを含まないまま育つ」の7件目。
# ただし向きが逆で、**育っているのではなく、潰せない回に潰せと言っていた**。）
#
# もう1つ、`retro.py` は窓の頭を **`QUOTA_BACK_HOUR = 16` と固定で**持っていました。
# 枠の頭は太平洋時間の0時なので、**冬は JST 17:00 です。** 上の `PT` が
# 「固定の時差で書き直さないこと」と書いているのに、**呼ぶ側が書き直していた** ——
# この repo で通算9回出ている「**片方だけ**」の10件目です。
#: **この帳面は失敗しか載らない帳面です。成功の記録として読まないこと**（2026-08-27）。
#:
#: `note_day_quota` は **403 のときだけ**書きます。**`videos.insert` は
#: 1度も書きません** —— 実測: 4,360行 のうち `videos.insert` の行は **0件**。
#:
#: **【2026-08-29 に数え直しました】** ここには「`note_quota_ok` を呼ぶのは
#: `videos.update` と `thumbnails.set` の**2か所だけ**」と書いてあり、
#: 同じ file の `dedupe_ok` は「呼ぶ場所は**現在3つ**」と書いていました ——
#: **同じ事実を2か所が別々の数で言っていた**（この repo の通算12件目）。
#: **実測は6か所**です: `uploader.py` の `playlists.insert` /
#: `playlistItems.insert` / `commentThreads.insert` / `thumbnails.set`、
#: `scripts/reschedule.py` の `videos.update`、
#: `scripts/post_pending_comments.py` の `commentThreads.insert`。
#:
#: **数を覚えるより、境目を覚えること** —— **6つとも書き込みで、
#: 通った読みは1件も載りません。** 読みは 1〜100単位（`search.list` は 100）で、
#: 尽きた窓では読みのほうが先に 403 を返します（実測 窓 08/28 の 403 の出どころ:
#: `uploader.taken_publish_times` 30回・`status.py:main` 16回・
#: `history.channel_video_ids` 6回 —— **どれも読み**）。
#:
#: **だから `measured_budget()["spent"]` は、窓ごとに違う量だけ低く出ます**:
#:
#:     窓 08/27  403 の前に通った単位 **9,050**（403 は 07:47Z）
#:     窓 08/28  403 の前に通った単位 **3,700**（403 は 12:37Z・以後 110回）
#:
#: `RESERVE_UNITS` の覆る条件「**関門が止めていないのに 403**」は、
#: **08/28 の窓で既に成立しています**（`reserve_hold()` はこの窓 1度も
#: 止めていません）。直す先は同じ註が名指ししているとおり
#: 「`note_quota_ok` をその呼び出しにも足す」で、
#: **`videos.insert` にだけは足さないこと**（`tests/test_insert_never_marked_ok.py`）。
#:
#: > **【2026-08-29 15:4x。その「直す先」を、そのまま撃たないこと】**
#: >
#: > 上の2行は 08/29 14:0x の回が「**次にここへ来た回がやること**」として
#: > 置いたものです。**そのとおりに撃つと、1窓ぶん 逆を踏みます。**
#: >
#: > `measured_budget()` の `floor` は **`if start != here` で、いまの窓を
#: > 数えません** —— 過去の窓の最大です。読みを `spent` に足した瞬間、
#: >
#: >     floor  = 過去の窓の最大（**書き込みだけで積んだ古い値**。9,050）
#: >     spent  = いまの窓（**読み込み込みの新しい値**）
#: >
#: > と**別々の物差しの引き算**になります。`reserve_hold()` の門は
#: > `spent < floor - RESERVE_UNITS` なので、**新しい窓の頭から
#: > 止まりっぱなし**になります（`floor` が新しい物差しで積み直るのは、
#: > 窓が1つ 閉じたあと）。
#: >
#: > **止まる先が問題です** —— `reserve_hold()` を呼んでいるのは
#: > `scripts/reschedule.py:434`、**`queue_lag.py --apply` が通る道そのもの**です。
#: > いまその道には `opening_motion` の判定日を **10/07 → 09/07（30日）**
#: > 倒す手が乗っており、**08/27 から一度も当たっていません**
#: > （`data/queue_lag.jsonl` は全4行 08/27・`after` なし）。
#: > **「帳面を正直にする fix」が、その 30日 を1窓 消します。**
#: >
#: > しかも門の文面は「残しているのは、**前提を閉じる読み**のためです」と
#: > 言っています —— **読みを数えると、読みを守るための門が、読みで閉じます。**
#: > 円環です。
#: >
#: > **撃つなら、順番はこう**（どちらか先に済ませること）:
#: >   (1) `floor` を**同じ物差しで**積み直せるようにする ——
#: >       読みを数え始めた最初の窓は `floor` を採らない（印を付ける）か、
#: >       `RESERVE_UNITS` をその窓だけ 0 にする
#: >   (2) 先に `--apply` を当てて `after` を帳面に入れ、
#: >       **30日 を回収してから**帳面を直す
#: >
#: > **覆る条件**: `measured_budget()` が `floor` と `spent` を
#: > **同じ物差しで**返すようになったら（＝ 読みを数え始めた窓に印が付いたら）、
#: > この註は古い。そのときは上の2行のとおりに撃ってよい。
#:
#: 2026-08-27 の回は、その 0 を「今日は1本も投稿できなかった」と読み、
#: **その回の いちばん大きい発見**として日誌に残しました。**逆です** ——
#: `data/uploaded.jsonl` の `uploaded_at` で数えると同じ日の投稿は **25本**、
#: うち **3本**は枠が尽きた 16:47 JST より**後**（18:05・18:20・18:40）に通っています。
#:
#: **投稿の本数は `data/uploaded.jsonl` で数えること。** そして
#: **`videos.insert` を `note_quota_ok` に足さないこと** ——
#: insert は日枠が尽きていても通るので、`ok` に書くと
#: `quota_ok_after_hits` が本当に尽きた窓を「開いている」と答えます
#: （`tests/test_insert_never_marked_ok.py` が、その両方を見ています）。
DAY_QUOTA_HITS = "data/day_quota.jsonl"


def _root():
    from . import config
    return config.ROOT


def window_start(now: datetime | None = None) -> datetime:
    """いま効いている枠の頭（＝直近の太平洋時間0時）を UTC で返す。"""
    now = (now or datetime.now(timezone.utc)).astimezone(PT)
    head = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return head.astimezone(timezone.utc)


def window_end(now: datetime | None = None) -> datetime:
    """いま効いている枠の尻（＝次の太平洋時間0時）を UTC で返す。

    `window_start` に24時間を足しません。**夏時間の切り替わる日は23時間・25時間**に
    なるので、足すのは暦の1日のほうです。
    """
    head = window_start(now).astimezone(PT)
    return (head + timedelta(days=1, hours=1)).replace(
        hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)


def _parse(value) -> datetime | None:
    try:
        when = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        return when.replace(tzinfo=timezone.utc)
    return when


#: **この repo の本物の場所**（`config.ROOT` を差し替えても動きません）。
#: 下の `_write_path` だけが使います。
_REPO = Path(__file__).resolve().parent.parent


def _write_path(name: str) -> Path | None:
    """書き込み先。**検査が本物の帳面を指していたら `None`**（＝1行も書かない）。

    ## なぜ要るか（2026-08-27 に実測して足した。**`tests/conftest.py` の8件目**）

    `tests/conftest.py` の冒頭は 2026-08-17 にこう書かれています ——
    **「検査は、本物の台帳に書かないこと」**、そして
    **「検査では `ledger=` を渡す」を約束にすると、一覧を足した回が必ず片方だけ
    忘れます（通算7回）。`conftest.py` は全部の検査に自動で掛かります。**

    **`data/day_quota.jsonl` は、その自動の掛かりに入っていませんでした。**
    実測（2026-08-27 に数えた）:

        本物の `data/day_quota.jsonl` 4,338行 のうち **97行** が検査の書いた行
        （08/26 に 37行・08/27 に 60行。`videos.update vid1` ＝
         `tests/test_unschedule_ledger.py` が偽の service で `_update` を呼ぶ）

    **これは統計の汚れでは済みません。** `note_quota_ok` が書く行は
    `{"ok": true}` で、`day_quota()` はそれを見て

        **「403 のあとに通っている ＝ あの 403 は日枠ではない。押してよい」**

    と答えます（`quota_ok_after_hits`）。つまり **`pytest` を1回 走らせるたびに、
    本当に尽きている日枠が「開いている」に化けます。** そこから
    `queue_lag`・`live_slots`・`refresh_thumbnail`・`batch_build` が
    いっせいに撃ち、**全部 403 で落ちて、また閉じる** ——
    この窓で 403 を **29回** 観測しているのは、その往復です
    （尽きた時点で降りていれば 1回 で済みます）。

    ## なぜ「呼ぶ側で気をつける」ではないのか

    `tests/test_day_quota.py` は `config.ROOT` を tmp へ差し替えていて、正しい。
    **忘れたのは、日枠とは関係のない検査のほう**です ——
    予約を動かす検査が、たまたま `_update` を通ったので帳面に載りました。
    **関係のない検査に「日枠の帳面に気をつけろ」と約束させるのは無理**なので、
    書く側を機械で閉じます。`config.ROOT` を差し替えた検査は今までどおり通ります
    （差し替え先は `_REPO` と違うので）。

    ## 覆る条件

    本物の帳面へ**わざと**書く検査が要るようになったら、
    `YT_QUOTA_LEDGER_WRITE=1` を立てること（そのときは理由を JOURNAL に）。
    """
    root = _root()
    if os.environ.get("PYTEST_CURRENT_TEST") and not os.environ.get(
            "YT_QUOTA_LEDGER_WRITE"):
        try:
            if Path(root).resolve() == _REPO:
                return None
        except OSError:                                        # noqa: BLE001
            return None
    return Path(root) / name


#: `by` を決めるとき**飛ばす**ファイル（帳面を書く側そのもの）。
_NOTE_SELF = ("upload_cap.py", "auth.py")


def caller_label(depth: int = 20) -> str:
    """**この行を書かせたのは誰か**を `<ファイル名>:<関数>` で返す。

    ## なぜ要るか（2026-08-27 に実測して足した）

    `data/day_quota.jsonl` は「何が・いつ・どの本に当たったか」しか持っておらず、
    **どの道具が撃ったかを1文字も持っていません。** そのせいで
    08/27 の回は「`videos.update` 489回 / 58本、1本が 140回」まで数えたのに、
    **撃ち手を名指しできず**、次の回への申し送りが
    「**残りの撃ち手を名指しすること**」で終わりました。

    入口は6つあります（`--move`・`--compact`・`--spread`・`long_pack`・
    `live_slots`・`queue_lag`）。**推測で1つずつ潰すより、帳面に書かせるほうが速い。**

    `detail` に足さないのは、読み手が `detail.split(' ')[1]` で本のIDを
    取っているからです（別の欄にすれば、既存の読み手は1つも壊れません）。
    """
    try:
        frame = sys._getframe(1)
    except (AttributeError, ValueError):                       # pragma: no cover
        return ""
    for _ in range(depth):
        if frame is None:
            break
        name = os.path.basename(frame.f_code.co_filename)
        if name not in _NOTE_SELF:
            return f"{name}:{frame.f_code.co_name}"[:80]
        frame = frame.f_back
    return ""


def _note(name: str, now: datetime | None, detail: str) -> None:
    now = now or datetime.now(timezone.utc)
    path = _write_path(name)
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {"at": now.astimezone(timezone.utc).isoformat(timespec="seconds"),
           "detail": detail[:200]}
    by = caller_label()
    if by:
        rec["by"] = by
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _in_window(name: str, now: datetime | None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    head, tail = window_start(now), window_end(now)
    path = _root() / name
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        when = _parse(rec.get("at"))
        if when and head <= when < tail:
            out.append(rec)
    return out


def note_hit(now: datetime | None = None, detail: str = "") -> None:
    """**429 に当たったことを残す**（次の回が、撃つ前に確実に知るため）。

    残さないと、次の回に伝わる経路が**日誌の散文しかありません。**
    10:5x の回はそう書きましたが、11:0x の回はそれを読んで
    「たぶん今も閉じている」と**推測する**しかありませんでした。
    """
    _note(HITS, now, detail)


def hits_in_window(now: datetime | None = None) -> list[dict]:
    """いまの枠の中で観測した 429 を返す。**あれば、その窓はもう閉じています。**"""
    return _in_window(HITS, now)


def note_quota_hit(now: datetime | None = None, detail: str = "") -> None:
    """**403 quotaExceeded に当たったことを残す**（Data API の単位枠）。

    `note_hit`（429・本数枠）と**同じ形・同じ窓**です。別の帳面にするのは、
    2つが**別々に閉じる**からです（8/17 05:2x の実測 —— `insert` が通るのに
    `update` が 403）。混ぜると、片方の観測がもう片方を閉じたことにします。
    """
    _note(DAY_QUOTA_HITS, now, detail)


#: **窓が開いた直後の何分を「前の窓の尻尾」とみなすか**（2026-08-26 に足した）。
#: 実測では最初の403が 0.1h/0.2h の2件と、6.6h 以降の7件に割れています
#: （`day_quota()` の註）。**30分 は、その隔たりの左側だけを拾う値**です。
#: 大きくしすぎると本当に尽きた窓を開いていると読みますが、
#: **403 は単位を使わない**ので、外した側の損は失敗した呼び出し1回ぶんです。
GRACE_MIN = 30


def quota_hits_in_window(now: datetime | None = None) -> list[dict]:
    """いまの枠の中で観測した 403 quotaExceeded。**あれば単位枠は尽きています。**

    **`ok` の行は数えません** —— あれは「403 のあとに通った」ことの記録で、
    403 そのものではありません（`note_quota_ok`）。
    """
    return [r for r in _in_window(DAY_QUOTA_HITS, now) if not r.get("ok")]


def dedupe_ok(rows: list[dict]) -> list[dict]:
    """**同じ秒に同じ `detail` で載った成功の行を、1回にまとめる。**（API 0単位）

    ## なぜ要るか（2026-08-28 に実測して足した）

    `scripts/batch_build.py` の長尺の詰め直しは、`reschedule._update`（**通ったら
    自分で1行 書く**）を呼んだ**あとにもう1行**書いていました。実測（窓 08/27）:

        `videos.update` の ok 行      **273行**
        うち (時刻, 本) が同じ行       **100行**
        → 実際に通ったのは            **173回 ＝ 8,650単位**

    **これは統計の汚れでは済みません。** `measured_budget()` は
    「403 の前に通った単位の最大」を**枠の実測**として返すので、幻の 100行 は
    枠を **9,150 → 14,150単位** に見せます。08/27 の回はその数を読んで
    **「日枠は既定の 10,000 ではない」**と結論し、コードの註に残しました。
    **二重に数えた側の誤りです。**

    呼び出し側は直しましたが（`batch_build`）、**入口は増えます** ——
    `note_quota_ok` を呼ぶ場所は **6か所**（一覧は `DAY_QUOTA_HITS` の註）で、
    次に7つ目ができたときに同じ穴が開きます。**だから数える側で潰します**
    （この repo が通算11回 踏んでいる「片方だけ」の形）。

    （**ここは 2026-08-29 まで「現在3つ」と書いていました。**同じ file の
    `DAY_QUOTA_HITS` の註は「2か所だけ」で、**実測は6か所** ——
    同じ事実を2か所が別々の数で言っていた形そのものです。
    **一覧は1か所にだけ置き、ここからは指すだけにしました。**）

    ## 覆る条件

    **同じ秒に、同じ本へ `videos.update` を2回 撃つのが正しい**ようになったら
    （いまは意味がありません —— 2回目は1回目と同じ値を書きます）。
    書き込みの入口はどれも 1.0〜1.2秒 待つので、**同じ秒の2行は二重書きだけ**です。
    `tests/test_quota_ok_dedupe.py` が、この2つを見ています。
    """
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for r in rows:
        key = (str(r.get("at") or ""), str(r.get("detail") or ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def spend_in_window(now: datetime | None = None) -> dict:
    """**この窓で、単位を使う書き込みを誰が何回 通したか。**（API 0単位）

    ## なぜ要るか（2026-08-27 の実測）

    窓 08/27 07:00Z 〜 の `data/day_quota.jsonl`:

        通った `videos.update`   **173回**（8,650単位・日枠は 1万）
        撃たれた本の数            **58本**
        → 同じ本の2回目以降      **115回 ＝ 5,750単位**（**66%**）

    **枠が尽きた理由が「同じ値の書き直し」だと、数えて初めて分かりました。**
    それまでの読み方は「403 が N回」だけで、**尽きた原因を1つも言っていません。**
    `scripts/reschedule._update` が同じ値を飛ばすようになったので、
    次の窓の `repeats` は **0 に近づくはず**です —— **そう出なければ、
    飛ばし損ねか、2つの道具が同じ本を別々の時刻へ取り合っています**
    （後者なら `by` の並びに2つの名前が出ます）。

    **この数は 2026-08-28 に数え直したものです。** それまでここには
    「273回・13,650単位・同じ本の2回目以降 215回」と書いてありました ——
    **うち 100回 は同じ呼び出しの二重書き**で、実際に通ったのは 173回 です
    （`dedupe_ok` の註）。**枠が「1万ではない」ように見えていたのは、これです。**

    返り: `{"ok", "videos", "repeats", "hits", "by", "ops"}`。
    `by` は `<ファイル名>:<関数>` → 回数（`caller_label`。古い行には無いので
    `"(不明)"` に落とします）。

    ## `ops`（2026-08-29 の最適化の回に足した。**「尽きた」と「先に使った」を分ける**）

    `ops` は `<呼び出し名>` → `{"n": 回数, "units": 単位}`。
    **`by`（誰が）だけでは、`--apply` を止めてよいかが決まりません** ——
    知りたいのは「**この窓で、入れ替えと同じ通貨（`videos.update`）が
    いくら通ったか**」のほうだからです。

    実測 2026-08-29（窓 08/28 07:00Z〜）:

        通った `videos.update`  **62回 ＝ 3,100単位**
        この窓の `--apply`      **0回**（`data/queue_lag.jsonl` に行が無い）
        その `--apply` の値段   **1,300単位**（26手・`opening_motion` だけで **30日**）

    **3,100 は在ったのに、1,300 の 30日 は撃たれていません。**
    そのあと 12:37Z に枠が尽き、`queue_lag` は
    「**撃たないこと。枠は本当に尽きています**」だけを印字しました ——
    正しいのですが、**その窓に金が無かったのではなく、先に別の所へ
    撃たれた**ことは1行も言っていません。`_spent_elsewhere_lines` が言います。
    """
    rows = _in_window(DAY_QUOTA_HITS, now)
    ok = dedupe_ok([r for r in rows if r.get("ok")])
    seen: dict[str, int] = {}
    by: dict[str, int] = {}
    ops: dict[str, dict] = {}
    for r in ok:
        parts = str(r.get("detail") or "").split(" ")
        vid = parts[1] if len(parts) > 1 else ""
        if vid:
            seen[vid] = seen.get(vid, 0) + 1
        label = str(r.get("by") or "(不明)")
        by[label] = by.get(label, 0) + 1
        op = parts[0] if parts and parts[0] else "(不明)"
        slot = ops.setdefault(op, {"n": 0, "units": 0})
        slot["n"] += 1
        slot["units"] += unit_cost(r.get("detail"))
    return {"ok": len(ok),
            "videos": len(seen),
            "repeats": sum(n - 1 for n in seen.values()),
            "units": sum(unit_cost(r.get("detail")) for r in ok),
            "hits": len([r for r in rows if not r.get("ok")]),
            "by": dict(sorted(by.items(), key=lambda kv: -kv[1])),
            "ops": dict(sorted(ops.items(), key=lambda kv: -kv[1]["units"]))}


#: **呼び出し1回の値段**（YouTube Data API v3 の公表値）。
#:
#: **回数ではなく単位で数えること**（2026-08-27 の最適化の回に足した）。
#: それまで、この repo は `videos.update` を**回数**でしか数えておらず、
#: 「273回 通った」とは言えても「**それが1日ぶんの予算だった**」とは
#: 言えませんでした。値段を掛けると、その窓の姿は一行で出ます:
#:
#:     videos.update  173回 × 50 = **8,650単位**
#:     thumbnails.set  10回 × 50 =    500単位
#:     ------------------------------------------
#:                                 **9,150単位 で 403**
#:
#: **【2026-08-28 に、この表の数を直しました】** ここには
#: 「`videos.update` 269回 × 50 ＝ 13,450単位／**13,950単位 で 403**」と
#: 書いてありました。**同じ呼び出しが同じ秒に2行 載っていたぶん**（100行）を
#: 二重に数えた数です（`dedupe_ok` の註）。**実測は 9,150単位**で、
#: **公表の既定 10,000 とよく合います**（帳面に載らない
#: `playlistItems.insert` と読みが、残りを埋めます）。
#:
#: そして `videos.insert` は**この予算に入っていません** —— 実測 08/27、
#: 最初の 403 は 07:47Z なのに、**10:33Z と 10:37Z の投稿は通っています**
#: （`data/uploaded.jsonl` の 8本）。同じ秒の `thumbnails.set` は 403 です。
#: **投稿は別の枠から出ています。** だから「投稿を止めて単位を空ける」は
#: 効きません —— 空けたいなら `videos.update` を減らすしかない。
#:
#: **覆る条件**: Google が値段表を変えたとき、または `videos.insert` の 403 が
#: `videos.update` と同じ窓で同時に始まったのを観測したとき（＝枠が1つに統合された）。
UNIT_COST = {
    "videos.insert": 1600,
    "videos.update": 50,
    "thumbnails.set": 50,
    "playlistItems.insert": 50,
    "commentThreads.insert": 50,
    "playlists.insert": 50,
    "videos.list": 1,
    "channels.list": 1,
    "playlistItems.list": 1,
    "search.list": 100,
}


def unit_cost(detail) -> int:
    """`detail`（例 `videos.update abc123`）から、その呼び出しの単位を返す。

    表に無いものは **1単位**（読みの既定値）に落とします。**0 にしないこと** ——
    知らない呼び出しを0円にすると、使った量を必ず低く見ます。
    """
    text = str(detail or "")
    for name, cost in UNIT_COST.items():
        if text.startswith(name):
            return cost
    return 1


def measured_budget(now: datetime | None = None) -> dict:
    """**1日の単位枠を、推測ではなく帳面から出す。**（API 0単位）

    ## なぜ要るか（2026-08-27 の最適化の回）

    このファイルは長らく「**日枠の実測は、この機械にはありません**」と
    書いていました（`scripts/queue_lag.py` の註）。だから
    `day_quota()` が言えたのは「403 を N回 見た」だけで、
    **あと何単位 使えるのかを、どの回も1度も知りませんでした。**

    ところが帳面には答えが入っています。**ある窓で 403 より前に通った
    呼び出しの値段を足すと、その日 API が確かに渡した単位**になります。
    窓をまたいでその最大を取れば、**枠の下限が実測で出ます**（上限ではない ——
    使い切らずに終わった窓は、それより低い数しか見せません）。

    実測（**2026-08-28 に数え直した**）: 08/27 の窓は **9,150単位** で 403。
    **既定の 10,000 とよく合います。**

    **ここには「13,950単位。既定の 10,000 ではありません」と書いてありました。**
    `scripts/batch_build.py` が `reschedule._update`（通ったら自分で書く）の
    **あとにもう1行**書いていたので、**同じ呼び出しが同じ秒に2行**（100行 ＝
    5,000単位）載っていました。**枠を 55% 高く見せていたのは、その幻です。**
    数える側で `dedupe_ok()` に通すよう直してあります（入口は増えるので、
    呼び出し側だけ直しても次の4つ目で同じ穴が開きます）。

    返り: `{"floor", "spent", "left", "from"}`
      floor  過去の窓で 403 の前に通った単位の**最大**（＝枠の下限・実測）
      spent  **この窓で**すでに使った単位
      left   `floor - spent`（負にはしません。**「確実に残っている」ではなく
             「ここまでは前例がある」**）

    **`left` を残量として読まないこと。** これは「同じ枠なら、少なくとも
    ここまでは通った前例がある」という意味です。**外す向きは、押して 403 を
    受ける側**（403 は単位を使わないので、外した損は失敗1回ぶん）。
    """
    now = now or datetime.now(timezone.utc)
    path = _root() / DAY_QUOTA_HITS
    by_window: dict[datetime, list[dict]] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            when = _parse(rec.get("at"))
            if not when:
                continue
            by_window.setdefault(window_start(when), []).append(rec)

    here = window_start(now)
    floor, came_from = 0, None
    for start, rows in by_window.items():
        rows = sorted(rows, key=lambda r: str(r.get("at")))
        first_hit = next((str(r.get("at")) for r in rows if not r.get("ok")), None)
        # **二重書きを1回にまとめてから足すこと**（2026-08-28。`dedupe_ok` の註）。
        # まとめないと、08/27 の窓は 9,150 ではなく **14,150単位** に見え、
        # **枠の実測が 55% 高く出ます**（＝ この上に立つ `reserve_hold` は
        # 一度も止まりません）。
        spent = sum(unit_cost(r.get("detail")) for r in dedupe_ok(
            [r for r in rows
             if r.get("ok") and (not first_hit or str(r.get("at")) < first_hit)]))
        if start != here and spent > floor:
            floor, came_from = spent, start
    spent_here = sum(unit_cost(r.get("detail")) for r in dedupe_ok(
        [r for r in by_window.get(here, []) if r.get("ok")]))
    return {"floor": floor, "spent": spent_here,
            "left": max(0, floor - spent_here),
            "from": came_from.astimezone(JST).strftime("%m/%d") if came_from else None}


#: **計測のために、窓の単位を必ず残す量**（2026-08-28 の最適化の回に足した）。
#:
#: ## なぜ要るか（実測。この数は帳面から出ています）
#:
#: 窓 08/27 07:00Z（＝ **16:00 JST**）〜 の `data/day_quota.jsonl`:
#:
#:     16:11 JST  最初の `videos.update`
#:     16:47 JST  **最初の 403**（通った 183回 ＝ **9,150単位**・枠は 10,000）
#:     ↓
#:     **残りの 23.2時間、読みも書きも 403**（この窓で 403 を **194回** 観測）
#:
#: **枠は「1日ぶん」ですが、実際に使えるのは窓が開いてからの 47分 だけ**でした。
#: そして `config/hypotheses.yaml` の 08-28 の前提が要る読みは
#: **「22:00 JST 以降に `python scripts/snapshot.py` を1回」** ——
#: **4単位**です。**9,150単位 を 47分 で焼いて、そのあと 4単位 が撃てません。**
#:
#: `eta.py` は毎回「**軌跡の腕が動くのは、前提を1件閉じたときだけ**」と印字します。
#: つまり **到達日を動かす唯一の操作が、到達日を 0日 しか動かさない操作に
#: 先を越されて、毎日 23時間 不可能になっていました。**
#: 実際にこれで **2回 続けて**（08/27 夕・08/28 未明）前提が閉じていません。
#:
#: ## 何を止めるか
#:
#: 止めるのは**書き込みだけ**（`videos.update` / `thumbnails.set`）。
#: **読みは止めません** —— 読みは 1単位 で、ここが守ろうとしている当のものです。
#: `videos.insert`（投稿）は**この枠を1単位も使わない**ので、
#: **投稿は1本も減りません**（`UNIT_COST` の註・実測 08/17 以後3度）。
#:
#: ## 大きさ（400単位 ＝ 書き込み 8回 ＝ 実測の窓 9,150 の **4.4%**）
#:
#: 読みは 1単位 なので、400単位 ＝ **読み 400回**。
#: 窓の残り 23時間・1周 1.56時間 ＝ 15周 で、**1周あたり 26回**の読み。
#: `snapshot.py` 1回（5呼び出し）を毎周 撃っても余ります。
#:
#: **この 400 は「帳面に載る通貨」での 400 です。**`note_quota_ok` を呼ぶのは
#: `videos.update` と `thumbnails.set` の2か所だけなので、`playlistItems.insert`
#: （50単位）と通った読みは `spent` に**1単位も載りません。** `floor` も同じ
#: 数え方なので比は保たれ（実測 9,150／公表 10,000 ＝ 0.92）、止めた時点の
#: 本当の残りは **400 ÷ 0.92 ≒ 435単位**です。
#:
#: ## 覆る条件
#:
#: - `measured_budget()["floor"]` が 0（＝ 過去の窓に 403 の前の成功が1行も無い）
#:   なら、**何も止めません。** 推測で書き込みを止めないため
#: - この窓の 403 が「窓が開いて 47分」ではなく**窓の終わりに寄る**ようになったら、
#:   ＝ 焼き方が変わったので、この数を測り直すこと
#: - `videos.insert` が同じ 403 で落ちるようになったら（＝枠が1つに統合された）、
#:   **投稿が減る側に効きはじめます。**そのときは大きさを測り直すこと
#: - **`data/day_quota.jsonl` を古い窓ごと捨てるようになったら、この関門は
#:   じりじり下がります。** `floor` は「403 の前に通った単位の**最大**」で、
#:   関門が効いた窓は 403 まで行かず `floor - 400` で止まります ——
#:   **その窓しか残っていなければ、次の `floor` はその数**になり、
#:   また 400 引かれます（8,750 → 8,350 → 7,950 …）。
#:   **症状は「`measured_budget()["from"]` の日が毎回いちばん新しい窓になる」。**
#:   いま帳面は 4,500行 を1行も捨てていないので、これは起きていません。
#:   捨てるようにするなら、**403 を実際に観測した窓の行だけは残すこと。**
#: - **帳面に載らない消費（`playlistItems.insert` の連打など）が増えたら、
#:   `spent` が 400 を残していても本当は 0 になりえます。** 症状は
#:   「関門が止めていないのに 403」。そのときは `note_quota_ok` を
#:   その呼び出しにも足すこと（**`videos.insert` にだけは足さない** ——
#:   `tests/test_insert_never_marked_ok.py` が理由ごと見ています）
RESERVE_UNITS = 400


#: **もう1つの門。こちらは「帳面の側」で、読みも数えます**（2026-09-01 に足した）。
#:
#: ## なぜ要るか —— **上の門は、この窓を 3,959単位 低く見ていました**
#:
#: 実測 2026-09-01 の窓（07:00Z 起点）を、2つの計器で同時に読むと:
#:
#:     `measured_budget()["spent"]`          **9,400単位**  ← 書き込みだけ
#:     `src.quota_ledger.spent()["data"]`   **13,359単位**  ← `HttpRequest.execute` を1点で包む
#:                                           差 **3,959単位**（本当の 30%）
#:
#: 差の中身は**読み**です: `search.list` 3,300（33回・単価 100）／
#: `videos.list` 392 ／ `playlistItems.list` 110 ／ `channels.list` 53 ／
#: `playlists.list` 4 ＝ **3,859単位**。**取り置き 400 の 9.6倍**です。
#:
#: `RESERVE_UNITS` の註は「**読みは 1単位**なので、400単位 ＝ 読み 400回」と
#: 書いています。**`search.list` は 100単位**です。`history.channel_video_ids` の
#: 1掃引（33回）だけで **3,300単位 ＝ 取り置き 8.25個ぶん**が、
#: 上の門からは**1単位も見えずに**消えます。
#:
#: そして註の「覆る条件」——「**関門が止めていないのに 403**」—— は
#: **この窓で成立しました**: 403 を **45回** 観測。枠が戻るのは 09/01 16:00 JST で、
#: **残り 11.2時間、読みも書きも通りません。**
#:
#: ## なぜ「読みを数えると円環になる」を踏まないか
#:
#: 上に 2026-08-29 の註があり、**読みを `measured_budget()["spent"]` に足すな**と
#: 言っています。理由は2つとも正しく、**こちらはどちらにも当たりません**:
#:
#:   (a) **別々の物差しの引き算になる** ——`floor` は過去の窓・書き込みだけで
#:       積んだ値。→ **`floor` を触りません。** この門は
#:       `quota_ledger.DAY_UNITS`（公表 10,000）と帳面の単位を比べます。
#:       **両辺とも同じ通貨**（本当に使った単位）です。
#:   (b) **読みを守る門が読みで閉じる（円環）** →
#:       **`reserve_hold()` を呼ぶのは書き込みの入口だけ**です
#:       （`tests/test_quota_reserve.py` が数え上げで見ています）。
#:       読みは**数えますが、止めません。** 数えるのは「いまどこに居るか」、
#:       止めるのは「何を止めるか」で、**別の問い**です。
#:       前の註は、その2つを1つに読んでいました。
#:
#: 08/29 の註が「先に済ませろ」と書いていた **(2) `queue_lag --apply` を当てて
#: `after` を帳面に入れる** は、**済んでいます**（`data/queue_lag.jsonl` の
#: 08/31 08:32 の行に `after` あり・`opening_motion` は `null`）。
#:
#: ## 覆る条件
#:
#: - **帳面が包まれていない回では、何も止めません**（`spent()["n"] == 0`）。
#:   推測で書き込みを止めないため —— 上の門と同じ規則です
#: - 帳面は 2026-08-31 に置いたので、**それ以前の窓は空**です。
#:   空の窓を「使っていない」と読まないこと（この門は黙ります）
#: - 単価（`quota_ledger.COST`）は**公表値**で、Google の実数ではありません。
#:   403 が **9,600単位 より手前**で出るようになったら、この 10,000 が高すぎます ——
#:   そのときは `quota_ledger.DAY_UNITS` を実測で下げること
#: - `videos.insert`（1,600単位）は**この枠から出ていません**（実測 08/17 以後3度）。
#:   帳面は insert も数えるので、**insert が枠を焼き始めた日**は
#:   この門が投稿を減らす側に効きます。そのときは大きさを測り直すこと
def _ledger_hold(now: datetime | None = None) -> str | None:
    """**帳面（漏れない側）で見た取り置き**（API 0単位）。止めてよければ理由の文字列。

    `src/quota_ledger` は `HttpRequest.execute` を1点で包むので、
    **読みも書きも漏れません。** `measured_budget()` は書き込みしか数えないので、
    こちらのほうが必ず**同じか、多く**出ます（＝ 門は緩みません）。
    """
    try:
        from . import quota_ledger as _ql                      # noqa: PLC0415
    except Exception:                                          # noqa: BLE001
        return None
    try:
        s = _ql.spent(now)
        if not int(s.get("n") or 0):
            return None            # 帳面に行が無い窓では止めない（推測で止めない）
        used = int(s.get("data") or 0)
        cap = int(_ql.DAY_UNITS)
    except Exception:                                          # noqa: BLE001
        return None
    room = cap - RESERVE_UNITS
    if used < room:
        return None
    top = sorted((s.get("by") or {}).items(), key=lambda kv: -kv[1])[:2]
    who = "／".join(f"{k} {v:,}単位" for k, v in top) or "（名前なし）"
    tail = window_end(now or datetime.now(timezone.utc))
    back = tail.astimezone(JST).strftime("%m/%d %H:%M JST")
    return (f"**この窓の単位は、帳面の側で止めています**"
            f"（使った {used:,} ／ 公表の枠 {cap:,} ／ 残す {RESERVE_UNITS}）。"
            f" **こちらは読みも数えます**（`measured_budget()` は書き込みだけ）。"
            f" いちばん食っているのは {who}。"
            f" 残しているのは、**前提を閉じる読み**と"
            f"**次の1本を良くする書き込み**（`improve`・50単位）のためです"
            f"（`eta.py`: 軌跡の腕が動くのは前提を1件 閉じたときだけ）。"
            f" 窓が変わるのは {back}。"
            f" **投稿（`videos.insert`）はこの枠を使わないので、止まりません。**"
            f" どうしても書くなら `YT_NO_RESERVE=1`（理由を JOURNAL に）")


def reserve_hold(now: datetime | None = None) -> str | None:
    """**この窓の単位が、計測のぶんまで減っていないか**（API 0単位）。

    書き込み（`videos.update` / `thumbnails.set`）を撃つ**前**に呼ぶこと。
    返りが文字列なら、それが「止めた理由」です。`None` なら撃ってよい。

    **推測では止めません** —— 枠の実測（`measured_budget()["floor"]`）が
    無い窓では必ず `None` を返します。`RESERVE_UNITS` の註に理由。

    `YT_NO_RESERVE=1` で外せます（**外した回は理由を JOURNAL に**）。
    """
    if os.environ.get("YT_NO_RESERVE"):
        return None
    # **帳面の側を先に見ること**（2026-09-01）。下の `measured_budget()` は
    # **書き込みしか数えない**ので、読みで焼けた窓を「まだ余っている」と答えます
    # （実測 2026-09-01: 9,400 と答えた窓の本当の消費は 13,359単位・403 を45回）。
    # こちらは `HttpRequest.execute` を1点で包む帳面なので漏れません。
    # **緩める向きには効きません** —— 帳面が黙る窓（行が0）では `None` を返し、
    # 判断はそのまま下の門へ落ちます。`_ledger_hold` の註に「なぜ円環でないか」。
    held = _ledger_hold(now)
    if held:
        return held
    try:
        b = measured_budget(now)
    except Exception:                                          # noqa: BLE001
        return None
    floor = int(b.get("floor") or 0)
    if not floor:
        return None                    # 実測が無い窓では止めない（推測で止めない）
    spent = int(b.get("spent") or 0)
    if spent < floor - RESERVE_UNITS:
        return None
    tail = window_end(now or datetime.now(timezone.utc))
    back = tail.astimezone(JST).strftime("%m/%d %H:%M JST")
    return (f"**この窓の単位は、計測のぶんを残して止めています**"
            f"（使った {spent:,} ／ 実測の枠 {floor:,} ／ 残す {RESERVE_UNITS}）。"
            f" 残しているのは、**前提を閉じる読み**のためです"
            f"（`videos.list` は 1単位。`eta.py`: 軌跡の腕が動くのは前提を1件"
            f"閉じたときだけ）。窓が変わるのは {back}。"
            f" **投稿（`videos.insert`）はこの枠を使わないので、止まりません。**"
            f" どうしても書くなら `YT_NO_RESERVE=1`（理由を JOURNAL に）")


#: **1本を、1つの窓で撃ってよい回数**（2026-08-28 の最適化の回に足した）。
#:
#: ## なぜ要るか —— **同じ値の書き直しではありません。値が違うのに撃ち合っています**
#:
#: 08/27 10:22Z の `reschedule._update` の関門は「**もうその値なら撃たない**」で、
#: これは正しく効きます。**ただし捕まえるのは、値が同じ回だけです。**
#: 窓 08/27 の再撃ちを `data/uploaded.jsonl` の `retimed_at` で割ると:
#:
#:     2回以上 撃たれた本                  **29本**
#:       うち 毎回おなじ時刻へ（関門が捕まえる）  **14本**
#:       うち **違う時刻へ**（関門を素通りする）  **15本**
#:
#: そして 15本 の散らばり方が、食い違いではなく**振動**です（中央値 **30日**・最大 31日）:
#:
#:     lIli_5r0YSY   16:24 → 10/01     16:44 → 08/31
#:     SLeIwUJa36A   16:25 → 10/03     16:44 → 09/03
#:     pvN0_4zZleo   16:25 → 10/02     16:44 → 09/02
#:     qlQnJwwwaZs   16:24 → 10/01     16:44 → 08/31
#:
#: **1つの掃きが1か月 先へ置き、19分後の掃きが1か月 手前へ引き戻しています。**
#: 書き込みを1本ずつ数えると、窓はこう割れます（`videos.update` は 50単位）:
#:
#:     窓 08/26   65回 /  **2本** ＝ 1本あたり **32.5回**   → 捨てた **3,150単位**
#:     窓 08/27  173回 / **58本** ＝ 1本あたり  **2.98回**  → 捨てた **5,750単位**
#:
#: **合わせて 8,900単位 ＝ ほぼ1日ぶんの枠**が、
#: 「同じ窓の後の書き込みが上書きした書き込み」に消えています。
#: **窓に効いたのは、その本の最後の1回だけ**です。残りは定義上むだです。
#:
#: ## なぜ 2 か（1 ではなく）
#:
#: 1 にすると最大（08/27 で 5,750単位）を取り戻せますが、**その窓で最初に
#: 置いた掃きが必ず勝ちます。** 上の実測では最初の掃きが**1か月 後ろ**の側なので、
#: 1 は「公開を1か月 遅らせる側を毎回 採用する」意味になりかねません。
#: **公開が遅れると、データが遅れ、前提が閉じるのが遅れます**
#: （`eta.py`: 軌跡の腕が動くのは前提を1件 閉じたときだけ）。
#: **2 は「置く＋1回だけ直す」を通し、3つ目以降の意見だけを落とします** ——
#: 08/26 の 32.5回/本 と、08/27 の3つ目の掃きは、これで止まります。
#:
#: ## 覆る条件
#:
#: - **どちらの掃きが正しいかが分かったら、この関門ではなく掃きのほうを直すこと。**
#:   これは「撃ち合いを安くする」関門で、**撃ち合いそのものは直していません。**
#:   `by`（`caller_label`。08/27 10:28Z 以後の行が持っています）で
#:   2つの掃きを名指しできます —— **次の窓の帳面には入っています**
#: - 1本を1つの窓で3回以上 動かす**正当な**筋道が出てきたら、この数を上げること
#: - 掃きが振動をやめて**収束**するようになったら（＝ 2回目の値が1回目に近い）、
#:   この関門は要らなくなります。**症状は「`moves_in_window` が 2 に張り付かない」**
MOVE_CAP = 2


def moves_in_window(video_id: str, now: datetime | None = None) -> int:
    """**この窓で、その本に通った `videos.update` の回数**（API 0単位）。

    帳面（`data/day_quota.jsonl`）の成功の行だけを数えます。`dedupe_ok` に
    通すのは、**同じ秒の二重書きを1回と数える**ためです（あれを数えると
    枠が 55% 高く見えたのと同じ幻が、ここでは「もう撃った」の側に出ます）。

    **数えるのは `moves_by_video()` ひとつです**（2026-08-29）。それまで
    ここは同じ数え方を**別に書いて**いて、篩の側（`move_blocked`）とは
    「たまたま同じ」でした。**片方だけ直せばずれる形**なので、1か所にしました。
    """
    vid = str(video_id or "").strip()
    if not vid:
        return 0
    # **本物の帳面には、検査の書いた行が残っています**（`_write_path` の註。
    # 08/27 の実測で 97行 —— その多くが `videos.update vid1`）。書く側は
    # 08/27 に機械で閉じましたが、**過去の行は残ったまま**です。
    # 読む側で閉じないと、`config.ROOT` を差し替えていない検査
    # （`test_reschedule_noop` / `test_unschedule_ledger` の 8件）が、
    # **その残骸を「もう4回 動かした」と読んで**赤くなります。
    # **関係のない検査に「日枠の帳面に気をつけろ」と約束させないこと** ——
    # `_write_path` がそう書いてある通りで、こちらはその読み側の対です。
    # `config.ROOT` を差し替えた検査は今までどおり数えます（差し替え先は `_REPO`
    # と違うので）。**覆る条件**は `_write_path` と同じ（`YT_QUOTA_LEDGER_WRITE=1`）。
    if os.environ.get("PYTEST_CURRENT_TEST") and not os.environ.get(
            "YT_QUOTA_LEDGER_WRITE"):
        try:
            if Path(_root()).resolve() == _REPO:
                return 0
        except OSError:                                        # noqa: BLE001
            return 0
    return moves_by_video(now).get(vid, 0)


def moves_by_video(now: datetime | None = None) -> dict[str, int]:
    """**この窓で `videos.update` が通った回数を、本ごとに1回で数える**（API 0単位）。

    ## なぜ要るか（2026-08-29 に測って足した）

    `moves_in_window()` は**1本 数えるたびに帳面を丸ごと読み直します。**
    1本ずつ聞く側にはそれで足りますが、**組む前に候補を篩う側**
    （`scripts/queue_lag.Plan._pull`）は 1周で何百回も聞くので、
    そこから呼ぶと帳面を何百回 読むことになります。**同じ答えを、1回で返します。**

    返りは `video_id → 回数`。**0回 の本は入りません**（呼ぶ側は `.get(v, 0)`）。
    数え方（成功の行だけ・`dedupe_ok` で同じ秒の二重書きを1回）と、
    検査の残骸を読まない門は `moves_in_window()` と**同じもの**です ——
    **片方だけ直すと食い違います。両方 直すこと。**
    """
    if os.environ.get("PYTEST_CURRENT_TEST") and not os.environ.get(
            "YT_QUOTA_LEDGER_WRITE"):
        try:
            if Path(_root()).resolve() == _REPO:
                return {}
        except OSError:                                        # noqa: BLE001
            return {}
    out: dict[str, int] = {}
    rows = [r for r in _in_window(DAY_QUOTA_HITS, now) if r.get("ok")]
    for r in dedupe_ok(rows):
        parts = str(r.get("detail", "")).split()
        # **`videos.update <vid>` ちょうど 2語 だけ**を数えます。
        # 印の付いた行（`… <vid> link` / `… <vid> retitle`）は
        # **予約を動かしていない**ので除きます（`tests/test_move_cap_scope.py`）。
        #
        # 除き方を「末尾の1語を見る」でやると、`videos.update b link` が
        # **`link` という名の本を1回 動かした**と数えられます。前の版が
        # そうで、`moves_in_window("link")` は 1 を返していました ——
        # 無害だったのは、動画IDが 11文字 で `link` になり得ないからだけです。
        # **印が1つ増えるたびに、その幻も1つ増える形**なので、ここで閉じます。
        if len(parts) != 2 or parts[0] != "videos.update":
            continue
        out[parts[1]] = out.get(parts[1], 0) + 1
    return out


def move_blocked(now: datetime | None = None) -> frozenset[str]:
    """**この窓で、もう動かせない本の集合**（API 0単位・帳面は1回だけ読みます）。

    `move_hold()` が「止めた理由」を返す本と**同じ集合**です。
    違うのは向きだけ —— あちらは**撃つ直前に1本を止める**門で、
    こちらは**組む前に候補から外す**ための集合です。

    ## なぜ両方 要るか（2026-08-29 に、3周ぶん 実測して足した）

    `move_hold()` だけだと、**組んでから止まります。**
    実測（2026-08-29 15:2x・`scripts/queue_lag.py --plan`）:

        入れ替え 10手（20回の `--move`）・**約束 34日**
        → そのうち **8回 が `move_hold` で止まる**本（**7手 が落ちる**）
        → `opening_motion` は対照が 8本ちょうどなので
          （`Plan.potential()` の註「4本を全部 前へ出すまで 1日も縮みません」）、
          **その 29日 は丸ごと 0日**

    **止めるのは正しい。約束するのが間違いです。** 止まると分かっている手を
    数に入れた「34日」は、そのまま `--moves` の宣言へ写され、
    次の回が「外れ」として記録します（`src/levers.reconcile`）。
    **落ちる手を最初から組まなければ、印字がそのまま実物になります。**

    **`YT_NO_MOVE_CAP=1` / `YT_FORCE_UPDATE` のときは空**です
    （`move_hold()` と同じ逃げ道。外した回は理由を JOURNAL に）。

    **覆る条件**: `MOVE_CAP` が上がるか、掃きが収束して
    `moves_in_window` が 2 に張り付かなくなったら、この集合は自然に空になります。
    """
    if os.environ.get("YT_NO_MOVE_CAP") or os.environ.get("YT_FORCE_UPDATE"):
        return frozenset()
    return frozenset(v for v, n in moves_by_video(now).items() if n >= MOVE_CAP)


def move_hold(video_id: str, now: datetime | None = None) -> str | None:
    """**この本は、この窓でもう動かしたか**（API 0単位）。

    返りが文字列なら「止めた理由」。`None` なら撃ってよい。
    **止めるのはその1本だけ**です —— 呼ぶ側は次の本へ進むこと
    （`reserve_hold` と違って、窓ぜんぶを止める話ではありません）。

    `YT_NO_MOVE_CAP=1` で外せます（**外した回は理由を JOURNAL に**）。
    """
    if os.environ.get("YT_NO_MOVE_CAP") or os.environ.get("YT_FORCE_UPDATE"):
        return None
    n = moves_in_window(video_id, now)
    if n < MOVE_CAP:
        return None
    tail = window_end(now or datetime.now(timezone.utc))
    back = tail.astimezone(JST).strftime("%m/%d %H:%M JST")
    return (f"{video_id} は**この窓でもう {n}回 動かしています**（上限 {MOVE_CAP}）。"
            f" 撃ちません（{n * 50}単位 は使用済み・この1回で 50単位 節約）。"
            f" **効くのはその本の最後の1回だけ**なので、"
            f"3つ目以降の置き直しは定義上むだです"
            f"（実測: 窓 08/26 は 1本あたり 32.5回・08/27 は 2.98回 ＝ 合わせて"
            f" 8,900単位）。窓が変わるのは {back}。"
            f" どうしても動かすなら `YT_NO_MOVE_CAP=1`（理由を JOURNAL に）")


def note_quota_ok(now: datetime | None = None, detail: str = "") -> None:
    """**単位を使う呼び出しが通ったことを残す**（2026-08-26 に実測して足した）。

    ## なぜ要るか（**この窓の作業を、1回のまぐれ 403 が丸ごと止めていました**）

    `day_quota()` は「この窓で 403 を1回でも観測したら閉じている」と答えます。
    **窓の中で単位が戻ることは無いので、これは正しい形に見えます。**
    ところが 2026-08-26 16:12 JST（枠が戻った 12分後）の実測:

        [live_slots] videos.update h35ot6MqYso → **403**（帳面に載った）
        その 1分後、同じ本を手で --move   → **通った**

    **日枠は1分では戻りません。** つまりあの 403 は日枠ではなく、
    短い間に 120本 撃ったことによる一過性のものでした。
    それでも帳面に載った瞬間、`day_quota().open` が **False** になり、
    `queue_lag` ・`live_slots` ・`refresh_thumbnail` ・
    `batch_build._pull_verdicts_first()` が**そこから 24時間 まるごと降ります。**

    **これが、受け取り帳が 14件 たまり、`missing_thumbnail` が 29件 になり、
    `queue_lag` の 77日 が3周 止まっていた形そのものです** ——
    毎日 16:00 に窓が開き、最初のまぐれ 403 で全部が閉じていました。

    ## 直し方（**「実測だけの門」を崩さない**）

    枠を推測しません。**足すのは、同じくらい確かな実測のほうです** ——
    **その 403 より後に、単位を使う呼び出しが通ったなら、日枠は尽きていません。**
    日枠は窓の中で戻らないので、**後の成功は、前の 403 を反証します。**

    外す向きは今までどおり「押してみて 403 が返れば分かる」側です。
    """
    now = now or datetime.now(timezone.utc)
    path = _write_path(DAY_QUOTA_HITS)      # **検査は本物の帳面に書きません**（その註）
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {"at": now.astimezone(timezone.utc).isoformat(timespec="seconds"),
           "ok": True, "detail": detail[:200]}
    by = caller_label()
    if by:
        rec["by"] = by
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def quota_ok_after_hits(now: datetime | None = None) -> dict | None:
    """**この窓の最後の 403 より後に通った呼び出し**（あれば、日枠は尽きていない）。

    無ければ `None`。`day_quota()` だけが読みます。
    """
    rows = _in_window(DAY_QUOTA_HITS, now)
    last_hit = None
    for rec in rows:
        if not rec.get("ok"):
            when = _parse(rec.get("at"))
            if when and (last_hit is None or when > last_hit):
                last_hit = when
    if last_hit is None:
        return None
    best = None
    for rec in rows:
        if rec.get("ok"):
            when = _parse(rec.get("at"))
            if when and when > last_hit:
                if best is None or when > _parse(best.get("at")):
                    best = rec
    return best


def counted(now: datetime | None = None) -> int:
    """いまの枠の中で**控えに載っている**投稿の本数（**下限**）。

    `uploaded_at` を持つ行だけを数えます。**この欄を足す前の行は数えられません。**
    数え落としは「まだ撃てる」側に外れるので、そのときは今までどおり 429 で止まります。
    """
    from . import dupes

    now = now or datetime.now(timezone.utc)
    head, tail = window_start(now), window_end(now)
    n = 0
    for row in dupes.ledger_rows():
        when = _parse(row.get("uploaded_at"))
        if when and head <= when < tail:
            n += 1
    return n


@dataclass
class State:
    closed: bool          # **確実に閉じている**（429 を観測した）
    counted: int          # 控えで数えられた本数（下限）
    remaining: int        # あと何本撃てるか（**上限側の見積り**。closed なら 0）
    resets_at: datetime   # 枠が戻る時刻（UTC）
    line: str             # そのまま印字して読める1行


def state(now: datetime | None = None) -> State:
    """**撃つ前に読む1か所。** `batch_build` と `status.py` の両方がここを見ます。"""
    now = now or datetime.now(timezone.utc)
    tail = window_end(now)
    back = tail.astimezone(JST).strftime("%m/%d %H:%M JST")
    hours = (tail - now).total_seconds() / 3600

    # **読めなかったことを理由に、この回を止めないこと**（CLAUDE.md）。
    # 読めない側へ倒すと「撃てる」と言うことになりますが、**それは今までの
    # 振る舞いそのもの**です（429 を見て止まる）。**悪化しません。**
    # 逆に読めないことを「閉じている」と読むと、**投稿が丸ごと止まります。**
    try:
        hits = hits_in_window(now)
        n = counted(now)
    except Exception as exc:                                   # noqa: BLE001
        return State(False, 0, CAP_PER_DAY, tail,
                     f"投稿の本数枠: **数えられませんでした**（{str(exc)[:60]}）。"
                     f" 撃ってみて 429 が返れば、そこで止まります。")

    if hits:
        line = (f"**投稿の本数枠は、この窓ではもう閉じています**"
                f"（{len(hits)}回、枠に当たったのを観測。控えで数えた投稿 {n}本）。"
                f" 戻るのは **{back}**（あと {hours:.1f}時間）。"
                f" **この窓で撃っても全部落ちるので、作らないこと。**")
        return State(True, n, 0, tail, line)

    rest = max(0, CAP_PER_DAY - n)
    if rest == 0:
        line = (f"**控えだけで {n}本を数えました（上限 {CAP_PER_DAY}本）。**"
                f" 戻るのは **{back}**（あと {hours:.1f}時間）。"
                f" 429 はまだ観測していませんが、**撃てば当たります。**")
        return State(False, n, 0, tail, line)

    line = (f"投稿の本数枠: この窓で **{n}本**（上限 {CAP_PER_DAY}本・"
            f"**あと {rest}本**）。窓が変わるのは {back}。"
            f" **控えは下限**なので、残りは上限側の見積りです。")
    return State(False, n, rest, tail, line)


@dataclass
class DayQuota:
    """**Data API の単位枠（10,000単位）**の、いまの姿。

    `State`（本数枠）と対になります。**2つは別々に閉じるので、混ぜないこと。**
    """
    open: bool            # 押してよいか（**観測した 403 が無い**）
    observed: bool        # この窓で 403 を観測したか（**確実な事実**）
    hits: int             # 観測した回数
    resets_at: datetime   # 窓が変わる時刻（UTC）
    line: str             # そのまま印字して読める1行


def worth_a_try(now: datetime | None = None) -> bool:
    """**閉じているが、一度は撃ってみる価値があるか**（2026-08-26 に足した）。

    `day_quota().open` は変えません —— あちらは「日枠が尽きたと**言い切れるか**」で、
    **外す向きは保守的なままが正しい**（`note_quota_ok` の節）。
    ここが答えるのは別の問いです: **その `False` は、証拠で閉じたのか。**

    ## なぜ要るか —— **反証の材料が、永久に出ません**

    `note_quota_ok` は「**403 のあとに通った呼び出しがあれば、あの403は日枠ではない**」
    という、実測にもとづく反証の道です。**正しい。ただし材料が要ります** ——
    誰かが実際に `videos.update` を撃って、通らなければ何も記録されません。

    ところが**撃つ側は全部この門の下にいます**（2026-08-26 に数えた）:

        scripts/batch_build.py  `_pull_verdicts_first()` / `_push_thumbnails_first()`
        scripts/refresh_thumbnail.py

    門が閉じている ＝ 撃たない ＝ 成功が記録されない ＝ **門は閉じたまま。**
    自分で自分を閉じ込めます。**開くのは、人が手で `reschedule.py --move` を
    撃った回だけ** —— この輪が何度も踏んでいる「人の操作が要る道」です
    （`docs/GOAL.md`「人の操作が要る道を、計画の柱にしないこと」）。

    実測 2026-08-26: 16:12 の 403 ひとつで門が閉じ、**その窓の残り 23.7時間**
    ぶんの `videos.update` が全部降りました。その 403 は日枠ではありません
    （16:13 に同じ本が手で動いています ＝ 短い間に撃ちすぎた側）。

    ## 何を見るか

    **窓が開いて `GRACE_MIN` 以内の 403 しか無い**なら True。
    実測（`data/day_quota.jsonl` 2946件・9つの窓。窓が開いてから最初の403まで）:

        0.1h  0.2h │ 6.6h  7.4h  7.6h  8.1h  10.6h  12.2h  14.4h
        ↑2件        │ ↑7件      **6.4時間の隔たりで、きれいに2つに割れています**

    左の2件はどちらも**直前の窓が重く尽きていた日**で、しかも 08/26 は
    その窓の `videos.insert` が **0本**でした。**何も使っていない窓は尽きません。**

    **試すのはタダです。** 403 は単位を消費しません（消費するのは通った呼び出し
    だけ）。外した損は失敗した1回ぶん、撃たない損は 23.7時間ぶん全部。
    **賭けが非対称なので、一度だけ撃つ側へ倒します。**

    ## 覆る条件

    - 猶予の外に 403 が1つでも出たら **False**（本当に尽きた窓なので、今までどおり降りる）
    - 撃った結果が通れば `note_quota_ok` が記録し、**次からは `open` が True**
      になるので、ここは読まれなくなります。**こちらは呼び水だけ**です
    - 「窓が開いた直後の403だけで閉じていた回」が実測から消えたら、この関数は消してよい
    """
    now = now or datetime.now(timezone.utc)
    try:
        hits = quota_hits_in_window(now)
    except Exception:                                          # noqa: BLE001
        return False
    if not hits:
        return False                       # 閉じていない。ここの出番ではない
    try:
        if quota_ok_after_hits(now):
            return False                   # 既に反証済み ＝ `open` が True 側で拾う
    except Exception:                                          # noqa: BLE001
        pass
    head = window_start(now)
    late = [h for h in hits
            if (_parse(h.get("at")) or head) >= head + timedelta(minutes=GRACE_MIN)]
    return not late


def day_quota(now: datetime | None = None) -> DayQuota:
    """**`thumbnails.set` / `videos.update` を押す前に読む1か所。**

    `retro.py` と `status.py` の両方がここを見ます。**時計で判断しないこと** ——
    窓が開いていることと、単位が残っていることは**別の事実**です
    （窓の中でこちらの `videos.insert` が使い切ります）。

    **読めなかったときは「開いている」と答えます。** 読めないことを
    「閉じている」と読むと、押せる回まで押さなくなります。外す向きは
    今までどおり 403 を見るだけで、**悪化しません**（`state()` と同じ考え方）。
    """
    now = now or datetime.now(timezone.utc)
    tail = window_end(now)
    back = tail.astimezone(JST).strftime("%m/%d %H:%M JST")
    hours = (tail - now).total_seconds() / 3600

    try:
        hits = quota_hits_in_window(now)
    except Exception as exc:                                   # noqa: BLE001
        return DayQuota(True, False, 0, tail,
                        f"日枠（単位）: **読めませんでした**（{str(exc)[:60]}）。"
                        f" 押してみて 403 が返れば、そこで分かります。")

    if hits:
        # **後の成功は、前の 403 を反証します**（`note_quota_ok` に理由）。
        # 日枠は窓の中で戻らないので、**403 のあとに通ったなら、それは日枠ではない。**
        try:
            later = quota_ok_after_hits(now)
        except Exception:                                      # noqa: BLE001
            later = None
        if later:
            when = _parse(later.get("at"))
            stamp = when.astimezone(JST).strftime("%m/%d %H:%M JST") if when else "?"
            line = (f"日枠（単位）: この窓で 403 を {len(hits)}回 観測していますが、"
                    f"**そのあと {stamp} に `{later.get('detail') or '呼び出し'}` が通っています。**"
                    f" 日枠は窓の中で戻らないので、**あの 403 は日枠ではありません**"
                    f"（短い間に撃ちすぎた側）。**押してよい。**"
                    f" 窓が変わるのは {back}（あと {hours:.1f}時間）。")
            return DayQuota(True, False, len(hits), tail, line)
        line = (f"**日枠（単位）は、この窓ではもう尽きています**"
                f"（{len(hits)}回の 403 を観測）。戻るのは **{back}**"
                f"（あと {hours:.1f}時間）。"
                f" **`thumbnails.set` も `videos.update` も、この窓では通りません。**")
        return DayQuota(False, True, len(hits), tail, line)

    # **「観測していない」で終えないこと**（2026-08-27 の最適化の回）。
    # ここは長らく「`videos.insert` 1本 1,600単位なので、7本上げた後はまず
    # 尽きています」と書いていました。**実測でそうではありません** ——
    # 08/27 は最初の 403 が 07:47Z、投稿は 10:33Z と 10:37Z で**通っています**。
    # **投稿は別の枠から出ていて、この枠を1単位も食いません。**
    # 食っていたのは `videos.update` **173回 ＝ 8,650単位**（うち 115回が
    # 同じ本の撃ち直し ＝ 5,750単位）。**名指しを間違えると、止める先も間違えます。**
    # （**2026-08-28 に数え直した** —— それまでここは 269回／13,450単位。
    #   `batch_build` の二重書き 100行 を数えていました。`dedupe_ok` の註）
    try:
        b = measured_budget(now)
    except Exception:                                          # noqa: BLE001
        b = None
    if b and b["floor"]:
        gauge = (f" この窓で使った単位 **{b['spent']:,}** ／"
                 f" 前例のある枠 **{b['floor']:,}**（{b['from']} の実測）→"
                 f" **あと {b['left']:,}**。"
                 f"**残量ではなく前例です** —— `videos.update` は1回 50単位で、"
                 f"**この枠を使い切るのはいつもこれ**です（投稿は別枠）。")
    else:
        gauge = (" **観測していないだけで、残量を見たわけではありません。**"
                 " 使い切るのは `videos.update`（1回 50単位）で、投稿ではありません。")
    line = (f"日枠（単位）: この窓ではまだ 403 を観測していません（窓が変わるのは {back}）。"
            + gauge)
    return DayQuota(True, False, 0, tail, line)


# ---------------------------------------------------------------------------
# **同じ50単位を、2つの用途が取り合っています**（2026-08-19 18:3x に測って足した）
#
#     thumbnails.set   50単位/本   サムネイルを載せる（待ち行列 107本）
#     videos.update    50単位/本   予約を詰め直す（`reschedule --compact`）
#
# **値段は同じです。効きが違います。**
#
#   - `status.py` の実測: 再生の **99.9%** が `SHORTS_FEED`（19,993 / 20,006）。
#     **ショートはフィードで自動再生され、サムネイルは出ません。**
#     サムネイルが効く面（検索・チャンネルのタナ・視聴ページ）は合わせて 0.1% です
#   - 詰め直しは `eta.py` が名指しした律速そのものです。
#     公開 1日4本なら門1は 634日、**1日25本なら 102日**。
#     0本の日を1日埋めるのは、いまの再生/日（1,572）の**十数日ぶん**にあたります
#
# 08/19 16:0x の回は、窓が開いた最初の1周で `--compact` に **9,602単位**を使い、
# その窓の残りは 400単位でした。**サムネイルは1本も押せていません。**
# 逆に、待ち行列 107本を先に押すと **5,350単位** ＝ **107本の詰め直しが消えます。**
#
# `batch_build._push_thumbnails_first` は「投稿より先に押す」ための門で、
# **`reschedule` のことを知りません**（このリポジトリが何度も見つけている
# 「同じ穴が片方にだけ居る」形です）。だから門は**押す側の中**に置きます ——
# 呼び手が増えても落ちません。
_THUMB_UNITS = 50


def schedule_holes(ahead, *, today=None) -> list:
    """予約の**暦を歩いて**、1本も予約の無い日を返す（API 0単位）。

    `ahead` は**これから公開される予定時刻**（UTC aware）の並び。
    `data/uploaded.jsonl` から作れるので、日枠が切れていても出せます。

    **鍵ではなく暦を歩くこと。** `Counter` の鍵には 0本の日が最初から
    入っていないので、そこから「無い日」は永久に出てきません
    （`docs/trigger_main.md` の同名の節）。

    明日から数えます —— 今日は既に半分公開済みのことがあり、
    入れると毎回「今日が断絶」と鳴って誤検知になります。
    """
    ahead = [t for t in ahead]
    if not ahead:
        return []
    today = today or datetime.now(JST).date()
    per = {}
    for t in ahead:
        d = t.astimezone(JST).date()
        per[d] = per.get(d, 0) + 1
    last = max(per)
    out = []
    d = today + timedelta(days=1)
    while d <= last:
        if per.get(d, 0) == 0:
            out.append(d)
        d += timedelta(days=1)
    return out


def thumbnail_yield_to_schedule(ahead, queued: int, *, today=None):
    """**サムネイルを押してよいか**を、予約の穴と突き合わせて決める。

    返りは `(押してよいか, 理由の1行)`。**穴がある間は押しません。**
    50単位は詰め直し1本ぶんと同じ値段で、そちらは律速に効きます。

    **これは「サムネイルは要らない」ではありません。** 穴が無くなったら押します
    （覆る条件: `SHORTS_FEED` 以外の面が再生の1割を超えたら、測り直すこと）。
    """
    holes = schedule_holes(ahead, today=today)
    if not holes:
        return True, f"予約に0本の日はありません。サムネイル {queued}本を押します"
    units = queued * _THUMB_UNITS
    head = " ".join(f"{d:%m/%d}" for d in holes[:5])
    more = f" ほか{len(holes) - 5}日" if len(holes) > 5 else ""
    # **代替案の大きさは、穴の数で言うこと**（2026-08-28 に踏んだ）。
    #
    # ここは長らく「同じ単位で**詰め直しが {queued}本**できます」と言っていました。
    # `queued` は**サムネイルの溜まり数**で、詰め直しに要る本数ではありません。
    # 実測 2026-08-28: 穴は 10/11 の **1日だけ**、埋めるのに要るのは
    # **`--move` 1回**。それでも文面は「70本 できます」と言い、
    # `reschedule --spread` は「1日 10本を超えている日はありません」と答えました
    # —— **勧めている代替案が、その大きさでは存在しません。**
    #
    # 読む側は「70本ぶんの詰め直しがある」と読んで `--spread` / `--compact` を
    # 撃ち、空振りして戻ってきます（この回で実際に起きた）。**撃つ行を書くこと。**
    fix = " ".join(f"{d:%Y-%m-%d}" for d in holes[:3])
    return False, (
        f"**押しません。** 予約に0本の日が {len(holes)}日あります（{head}{more}）。"
        f" サムネイル {queued}本 ＝ **{units:,}単位**。"
        f" **埋めるのに要るのは {len(holes)}本の移動**"
        f"（{len(holes) * _THUMB_UNITS:,}単位）です ——"
        f" `python scripts/reschedule.py --move <動画ID> {fix.split()[0]}T09:00`。"
        " 再生の 99.9% は SHORTS_FEED（サムネイルの出ない面）で、"
        "0本の日を埋めるほうが `eta.py` の日付を動かします。"
        " **`--spread` は当てにしないこと** —— あれは1日の上限を超えた日だけを見るので、"
        "上限内に収まっている穴には何も返しません。"
        " **穴が無くなったら自動で押します**（`--force` で今すぐ押せます）"
    )
