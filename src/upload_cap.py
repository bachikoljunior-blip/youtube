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


def _note(name: str, now: datetime | None, detail: str) -> None:
    now = now or datetime.now(timezone.utc)
    path = _root() / name
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {"at": now.astimezone(timezone.utc).isoformat(timespec="seconds"),
           "detail": detail[:200]}
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


def quota_hits_in_window(now: datetime | None = None) -> list[dict]:
    """いまの枠の中で観測した 403 quotaExceeded。**あれば単位枠は尽きています。**"""
    return _in_window(DAY_QUOTA_HITS, now)


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
        line = (f"**日枠（単位）は、この窓ではもう尽きています**"
                f"（{len(hits)}回の 403 を観測）。戻るのは **{back}**"
                f"（あと {hours:.1f}時間）。"
                f" **`thumbnails.set` も `videos.update` も、この窓では通りません。**")
        return DayQuota(False, True, len(hits), tail, line)

    line = (f"日枠（単位）: この窓ではまだ 403 を観測していません（窓が変わるのは {back}）。"
            f" **観測していないだけで、残量を見たわけではありません** ——"
            f" `videos.insert` 1本 1,600単位なので、7本上げた後はまず尽きています。")
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
    return False, (
        f"**押しません。** 予約に0本の日が {len(holes)}日あります（{head}{more}）。"
        f" サムネイル {queued}本 ＝ **{units:,}単位** で、"
        f"同じ単位で**詰め直しが {queued}本**できます。"
        " 再生の 99.9% は SHORTS_FEED（サムネイルの出ない面）で、"
        "0本の日を埋めるほうが `eta.py` の日付を動かします。"
        " **穴が無くなったら自動で押します**（`--force` で今すぐ押せます）"
    )
