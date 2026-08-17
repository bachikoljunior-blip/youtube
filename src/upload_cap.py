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
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
CAP_PER_DAY = 97

# 枠の頭は**太平洋時間の0時**です。JST 16:00 と書いてある文書が多いのは、
# 夏（PDT ＝ UTC-7）にそう見えるからで、**冬は JST 17:00 になります。**
# だから固定の時差ではなく tz 名で持ちます（`zoneinfo` は動作を確認済み）。
PT = ZoneInfo("America/Los_Angeles")
JST = timezone(timedelta(hours=9))

HITS = "data/upload_cap.jsonl"


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


def note_hit(now: datetime | None = None, detail: str = "") -> None:
    """**429 に当たったことを残す**（次の回が、撃つ前に確実に知るため）。

    残さないと、次の回に伝わる経路が**日誌の散文しかありません。**
    10:5x の回はそう書きましたが、11:0x の回はそれを読んで
    「たぶん今も閉じている」と**推測する**しかありませんでした。
    """
    now = now or datetime.now(timezone.utc)
    path = _root() / HITS
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {"at": now.astimezone(timezone.utc).isoformat(timespec="seconds"),
           "detail": detail[:200]}
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def hits_in_window(now: datetime | None = None) -> list[dict]:
    """いまの枠の中で観測した 429 を返す。**あれば、その窓はもう閉じています。**"""
    now = now or datetime.now(timezone.utc)
    head, tail = window_start(now), window_end(now)
    path = _root() / HITS
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
                f"（{len(hits)}回の 429 を観測。控えで数えた投稿 {n}本）。"
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
