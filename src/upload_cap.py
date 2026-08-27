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
#: `note_day_quota` は **403 のときだけ**書きます。`note_quota_ok` を呼ぶのは
#: `videos.update` と `thumbnails.set` の2か所だけで、**`videos.insert` は
#: 1度も書きません** —— 実測: 4,360行 のうち `videos.insert` の行は **0件**。
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


def spend_in_window(now: datetime | None = None) -> dict:
    """**この窓で、単位を使う書き込みを誰が何回 通したか。**（API 0単位）

    ## なぜ要るか（2026-08-27 の実測）

    窓 08/27 07:00Z 〜 の `data/day_quota.jsonl`:

        通った `videos.update`   **273回**（13,650単位・日枠は 1万）
        撃たれた本の数            **58本**
        → 同じ本の2回目以降      **215回 ＝ 10,750単位**（**79%**）

    **枠が尽きた理由が「同じ値の書き直し」だと、数えて初めて分かりました。**
    それまでの読み方は「403 が N回」だけで、**尽きた原因を1つも言っていません。**
    `scripts/reschedule._update` が同じ値を飛ばすようになったので、
    次の窓の `repeats` は **0 に近づくはず**です —— **そう出なければ、
    飛ばし損ねか、2つの道具が同じ本を別々の時刻へ取り合っています**
    （後者なら `by` の並びに2つの名前が出ます）。

    返り: `{"ok", "videos", "repeats", "hits", "by"}`。
    `by` は `<ファイル名>:<関数>` → 回数（`caller_label`。古い行には無いので
    `"(不明)"` に落とします）。
    """
    rows = _in_window(DAY_QUOTA_HITS, now)
    ok = [r for r in rows if r.get("ok")]
    seen: dict[str, int] = {}
    by: dict[str, int] = {}
    for r in ok:
        parts = str(r.get("detail") or "").split(" ")
        vid = parts[1] if len(parts) > 1 else ""
        if vid:
            seen[vid] = seen.get(vid, 0) + 1
        label = str(r.get("by") or "(不明)")
        by[label] = by.get(label, 0) + 1
    return {"ok": len(ok),
            "videos": len(seen),
            "repeats": sum(n - 1 for n in seen.values()),
            "units": sum(unit_cost(r.get("detail")) for r in ok),
            "hits": len([r for r in rows if not r.get("ok")]),
            "by": dict(sorted(by.items(), key=lambda kv: -kv[1]))}


#: **呼び出し1回の値段**（YouTube Data API v3 の公表値）。
#:
#: **回数ではなく単位で数えること**（2026-08-27 の最適化の回に足した）。
#: それまで、この repo は `videos.update` を**回数**でしか数えておらず、
#: 「273回 通った」とは言えても「**それが1日ぶんの予算だった**」とは
#: 言えませんでした。値段を掛けると、その窓の姿は一行で出ます:
#:
#:     videos.update  269回 × 50 = **13,450単位**
#:     thumbnails.set  10回 × 50 =     500単位
#:     ------------------------------------------
#:                                 **13,950単位 で 403**
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

    実測（2026-08-27 時点）: 08/27 の窓は **13,950単位** で 403。
    **既定の 10,000 ではありません。**

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
        spent = sum(unit_cost(r.get("detail")) for r in rows
                    if r.get("ok") and (not first_hit or str(r.get("at")) < first_hit))
        if start != here and spent > floor:
            floor, came_from = spent, start
    spent_here = sum(unit_cost(r.get("detail"))
                     for r in by_window.get(here, []) if r.get("ok"))
    return {"floor": floor, "spent": spent_here,
            "left": max(0, floor - spent_here),
            "from": came_from.astimezone(JST).strftime("%m/%d") if came_from else None}


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
    # 食っていたのは `videos.update` 269回 ＝ **13,450単位**（うち 215回が
    # 同じ本の撃ち直し ＝ 10,750単位）。**名指しを間違えると、止める先も間違えます。**
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
    return False, (
        f"**押しません。** 予約に0本の日が {len(holes)}日あります（{head}{more}）。"
        f" サムネイル {queued}本 ＝ **{units:,}単位** で、"
        f"同じ単位で**詰め直しが {queued}本**できます。"
        " 再生の 99.9% は SHORTS_FEED（サムネイルの出ない面）で、"
        "0本の日を埋めるほうが `eta.py` の日付を動かします。"
        " **穴が無くなったら自動で押します**（`--force` で今すぐ押せます）"
    )
