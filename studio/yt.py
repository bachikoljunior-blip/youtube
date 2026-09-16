"""YouTube Data API の最小限。認証は環境変数 3つ（YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN）。

日枠（10,000単位/日・16:00 JST に戻る）: videos.insert 1,600・videos.update 50・thumbnails.set 50・
videos.list 1・playlistItems.list 1。
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import google_auth_httplib2
import httplib2
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from . import meter
from .common import JST, env, now_jst

_svc = None


def token_rejected_words(err: Exception) -> str:
    """口（`YT_REFRESH_TOKEN`）を Google が拒んだときの 3行（2026-09-14 18:5x・`hourly`・Fable）。

    **実測**: 入れ物の立て直し（09/14 18:2x JST）のあと最初に立ったサブ（18:45 起動）で、`status` が
    `google.auth.exceptions.RefreshError: invalid_grant: Bad Request` で落ちた（traceback 40行）。
    17:16 JST の `channel` の行までは同じ変数名で読めていた ＝ **値が替わって届いた周に、その値が拒まれた**
    （オーナー 09:3x `efc96bd9`「上書き後のはクッキーストラテジャーというチャンネルの方のトークン」・`docs/GOAL.md` (4-f)）。
    `invalid_grant` の文言で分かれる: **`Bad Request` ＝ token が この `YT_CLIENT_ID`／`YT_CLIENT_SECRET` の物ではない**
    （別の OAuth クライアント／別の GCP プロジェクトで取った token）か、値の形が崩れている。
    **`Token has been expired or revoked.` ＝ 同じクライアントの token が失効**（取り消し・テスト中アプリの 7日）。
    どちらも **API 0単位**（token の口は日枠の外）。**この関数は判定しません** —— 文言を読み分けて、
    次に置く物（3つ）を言うだけ。**止めるのは `svc()`**（口が無いのに 23か所 の呼び手がそれぞれ traceback を出す形をやめた）。
    **覆る条件**: (1) 口が 2つ（環境変数名が 2つ）になったら、どの名の口が拒まれたかを行に持たせること
    （`cli.channel_switch_line` の覆る条件 (2) と同じ刻）。(2) `invalid_grant` 以外（`invalid_client` ＝ secret 違い）が出たら、
    その文言の枝をここに足すこと。(3) 拒まれた周が 3周 続いたら、この行ではなく親の【枠】の段に出す側（`quota` の印字）。
    """
    msg = str(err)
    if "expired or revoked" in msg:
        why = "同じクライアントの token が失効（取り消し・テスト中アプリの 7日）＝ 同じ YT_CLIENT_ID で取り直す"
    elif "invalid_grant" in msg:
        why = ("この YT_CLIENT_ID／YT_CLIENT_SECRET で取った token ではない（別の OAuth クライアントで取った物）か、"
               "値の形が崩れている ＝ その token を取ったクライアントの id/secret も一緒に置くか、この id で取り直す")
    else:
        why = "文言が既知の 2つ のどちらでもない（`yt.token_rejected_words` の覆る条件 (2)）"
    a0 = err.args[0] if getattr(err, "args", None) else msg
    head = (a0 if isinstance(a0, str) else msg).splitlines()[0][:80] or "?"
    return ("!! 口が拒まれました: YT_REFRESH_TOKEN を Google が受けません（" + head + "）\n"
            "   なぜ: " + why + "\n"
            "   置く物（オーナーの手・GOAL (4-f) 18:5x）: (1) お金と仕事の教科書 の token を YT_REFRESH_TOKEN に戻す"
            "（台帳の 9本 と 09/15 の予約はこの口）・(2) クッキーストラテジャー の token は別の名（YT_REFRESH_TOKEN_2）に置く・"
            "(3) それを取ったクライアントが別なら YT_CLIENT_ID_2／YT_CLIENT_SECRET_2 も。API 0単位 ＝ 日枠は減っていません")


def svc():
    global _svc
    if _svc is None:
        # **撃った物を、撃った所で数える**（`studio/meter.py` 冒頭・**API 0単位**）。
        # ここに置くのは、Data API の口がここ 1つ しかないからです（`svc()` を通らない呼びは無い）。
        meter.install()
        creds = Credentials(token=None, refresh_token=env("YT_REFRESH_TOKEN"),
                            token_uri="https://oauth2.googleapis.com/token",
                            client_id=env("YT_CLIENT_ID"), client_secret=env("YT_CLIENT_SECRET"))
        # **口を先に 1回 開けて、拒まれたら 3行 で止める**（2026-09-14 18:5x・`hourly`・Fable）。
        # 遅延の refresh は最初の API 呼びの中で落ち、23か所 の呼び手がそれぞれ traceback 40行 を出す
        # （実測: `cmd_status` の `yt.channel()`）。refresh は最初の呼びが必ず撃つ物なので、ここで撃っても
        # 回数は増えない（API 0単位・token の口は日枠の外）。文言の読み分けは `token_rejected_words` の註。
        try:
            creds.refresh(google_auth_httplib2.Request(httplib2.Http()))
        except RefreshError as e:
            raise SystemExit(token_rejected_words(e)) from e
        _svc = build("youtube", "v3", credentials=creds, cache_discovery=False)
    return _svc


def channel() -> dict:
    """チャンネルの数（登録・総再生・本数）を 1回 読む（**1単位**）。

    **この 1点 を「いまの総再生」と読まないこと**（2026-09-11 04:0x・optimizer・Opus）——
    `viewCount` は **遅れの違う複製から返ります**（`videos.list` と同じ族）。
    実測: `hourly` の 03:23:59 が **86,406**・`optimizer` の 03:24:53 が **84,781**（**54秒 差で 1,625 違う**）・
    02:12:18 と 02:12:43 も同じ 2値。直に 5回 撃つと 5回 とも 86,406 ＝ **低いほうが遅れた複製**。
    読むのは `trend.channel_growth`（周ごとの max → 包絡）と `trend.channel_replicas`（割れと下がりを毎周 印字）。
    **覆る条件はそちらの註**（3つ目の値が出たら 3回 読みを `cli.record_channel` に足す）。
    """
    ch = svc().channels().list(part="id,snippet,statistics,contentDetails", mine=True).execute()["items"][0]
    return {"id": ch["id"], "title": ch["snippet"]["title"],
            "uploads": ch["contentDetails"]["relatedPlaylists"]["uploads"],
            **{k: int(v) for k, v in ch["statistics"].items() if isinstance(v, str) and v.isdigit()}}


def views_of(st: dict) -> tuple[int, bool]:
    """`statistics.viewCount` を読む。**欄が無いのと 0回 は別**（2026-09-10 14:2x・optimizer・Opus）。

    `videos.list` の `statistics` は、統計を止めた本・処理の終わっていない本・
    埋め込みだけの本では **欄そのものを返しません**。`.get("viewCount", 0)` はそれを
    **本当の 0回 と同じ形**にします ＝ 台帳には「0回」と書かれ、`trend` は
    「配りが来ていない」と読み、§7 は齢の割合と `first_view` をその 0 で数えます。
    **§4 (0-b) の「0件 を『事実は大丈夫』と読まないこと」の族の 3つ目の型**
    （1つ目 ＝ 見つけた上で別の札を貼る・2つ目 ＝ 両側がそろってまちがえて食い違いが 0件・
      **3つ目 ＝ 欄が無いのを 0 と読む**）。

    **この回に測りました**（2026-09-10 14:0x・`videos.list` **1単位**）: 5本目 `2YZ_4FXC-XI` が
    齢 3.9h で 0回 だったので、「欄が無い」のか「本当に 0」のかを直に見た ——
    **3本 とも欄は在り、5本目 の値は文字列 `"0"`**
    （`viewCount`/`likeCount`/`dislikeCount`/`favoriteCount`/`commentCount` がそろっている）。
    ＝ **いま踏んではいません。踏んだときに黙って通る口だけを塞いであります。**

    **落とさずに印だけ立てます** —— 行を落とすと分母が黙って減り、
    「読んでいない本」と「0回 の本」がまた同じ形になります（`cmd_measure` の `n_values` の註と同じ形）。

    **覆る条件**: (1) `views_absent` が **1度でも立ったら**、その本の台帳の 0回 を
    「配りが来ていない」と読まないこと ＝ そのとき `trend.first_view` の `zero` から外し、
    別の札（「読めていない」）を作る。(2) **7本 過ぎて 1度も立たなければ**この口は外してよい
    （`cli.over_ledger` の (2) と同じ形 —— 一度きりの心配に道具を残さない）。
    """
    return int(st.get("viewCount", 0)), "viewCount" not in st


def _row(v: dict) -> dict:
    st = v["status"]
    stats = v.get("statistics", {})
    views, absent = views_of(stats)
    return {"id": v["id"], "title": v["snippet"]["title"], "privacy": st["privacyStatus"],
            "publish_at": st.get("publishAt"), "published_at": v["snippet"]["publishedAt"],
            "duration": v.get("contentDetails", {}).get("duration", ""),
            "views": views,
            # **欄が無いのと 0回 は別**（`views_of` の註）。立った回だけ持ち回る。
            "views_absent": absent,
            "likes": int(stats.get("likeCount", 0)),
            # コメント数。2026-09-07 20:4x まで、道具はこれを1度も見ていなかった（`viewer_comments()` の註）。
            "comments": int(stats.get("commentCount", 0))}


_ALL: list[dict] | None = None


def all_videos(refresh: bool = False) -> list[dict]:
    """**チャンネルの全本**（新しく上げた順・ID で重複を落とす）。同じ回では1度だけ引く。

    755本 で playlistItems 16 + videos.list 16 ＝ **約 32単位**（日枠 10,000）。

    **なぜ「上げた順の先頭 N本」では駄目か**（2026-09-07 16:4x・optimizer・Opus が実測）:
    uploads の並びは**上げた順**で、**公開した順ではない**。08/16〜08/19 に上げて private のまま
    置いてあった旧作りの本に、あとから publishAt が付いて公開されると、その本は
    uploads の 690番目あたりに居るので `recent_videos(60)` には**永久に入らない**。
    実測: 09/05 に 5本・09/06 に 8本・09/07 に 1本（`PhQ2KvuQASQ` 09:00・73回）が
    こうして公開されていたのに、`status` の「きょうの枠」にも「直近 公開 10本」にも
    出ず、`measure` は 1行も台帳に書いていなかった（6本 とも measured 0行）。
    §6 の `scheduled_all()` は 09/06 02:1x に同じ穴を private 側だけ塞いだもので、
    **public 側は空いたままだった。**
    """
    global _ALL
    if _ALL is not None and not refresh:
        return _ALL
    up = channel()["uploads"]
    ids, seen, tok = [], set(), None
    while True:
        r = svc().playlistItems().list(part="contentDetails", playlistId=up, maxResults=50, pageToken=tok).execute()
        for i in r["items"]:
            vid = i["contentDetails"]["videoId"]
            if vid not in seen:
                seen.add(vid)
                ids.append(vid)
        tok = r.get("nextPageToken")
        if not tok:
            break
    out = []
    for i in range(0, len(ids), 50):
        r = svc().videos().list(part="snippet,status,statistics,contentDetails", id=",".join(ids[i:i + 50])).execute()
        out += [_row(v) for v in r["items"]]
    _ALL = out
    return out


def published(within_h: float | None = None) -> list[dict]:
    """**公開ずみの本を、公開した順（新しい順）に**。`within_h` を渡すと その齢までに絞る。

    「直近 公開 N本」も `measure` も、**上げた順ではなくこの順で選ぶこと**（上の註）。
    """
    rows = [v for v in all_videos() if v["privacy"] == "public"]
    rows.sort(key=when, reverse=True)
    if within_h is None:
        return rows
    return [v for v in rows if (now_jst() - when(v)).total_seconds() / 3600 <= within_h]


def when(v: dict) -> dt.datetime:
    s = v["publish_at"] or v["published_at"]
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(JST)


def scheduled_all() -> list[dict]:
    """**チャンネルの全本**のうち、publishAt が付いていて まだ public でない本（＝予約）。新しい順。

    上げた順の先頭 N本 だけを見ていると見えない: 実測 2026-09-06 00:01 JST、旧 `ahead_sweep.py` が
    08/16〜08/19 に上げた private の本 8本（uploads の 690番目あたり）に きょうの publishAt を打ち、
    `status` は「きょうの枠: 空」と印字した。→ `all_videos()`（全本・約 32単位・同じ回では1度だけ）。
    """
    return [v for v in all_videos() if v["publish_at"] and v["privacy"] != "public"]


def today_lineup(videos: list[dict] | None = None, date: dt.date | None = None) -> list[dict]:
    """きょう（JST）に公開ずみ・公開予定の本。**公開ずみも予約も、全本から拾う。**
    `date` を渡せばその日（2026-09-14 20:3x・hourly: `schedule --at "YYYY-MM-DD HH:MM"` の「1日1本」の門がこれで数える）。

    2026-09-07 16:4x（optimizer・Opus）に public 側を全本に変えた。それまで公開ずみは
    「上げた順の先頭 60本」から拾っていたので、08月に上げて きょう公開された旧作りの本が
    **1本も見えなかった** —— 実測 09/07 09:00 の `PhQ2KvuQASQ`（73回）は「きょうの枠」に出ず、
    その1時間あとに `schedule` の「1日1本」の門（`cmd_schedule` が この関数で数える）も
    素通りして、きょうは 2本 出ている。`all_videos()` は1度しか引かないので単位は増えない。
    """
    videos = videos if videos is not None else all_videos()
    d = date or now_jst().date()
    rows = [v for v in videos if v["privacy"] == "public" and when(v).date() == d]
    seen = {v["id"] for v in rows}
    rows += [v for v in scheduled_all() if v["id"] not in seen and when(v).date() == d]
    return sorted(rows, key=when)


def upload(path: Path, title: str, description: str, tags: list[str], publish_at: dt.datetime | None) -> str:
    status = {"privacyStatus": "private", "selfDeclaredMadeForKids": False, "license": "youtube", "embeddable": True}
    if publish_at:
        status["publishAt"] = publish_at.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = {"snippet": {"title": title, "description": description, "tags": [t[:30] for t in tags][:15],
                        "categoryId": "27", "defaultLanguage": "ja", "defaultAudioLanguage": "ja"},
            "status": status}
    media = MediaFileUpload(str(path), mimetype="video/mp4", resumable=True, chunksize=8 * 1024 * 1024)
    req = svc().videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    return resp["id"]


def set_thumbnail(video_id: str, png: Path) -> None:
    svc().thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(png), mimetype="image/png")).execute()


#: 透かし（登録ボタンの重ね）の絵。**150x150 の PNG・1MB まで**（YouTube の決め）。
WATERMARK = Path("assets/images/watermark-subscribe.png")


def set_watermark(png: Path | None = None, offset_ms: int = 15000,
                  duration_ms: int = 0) -> None:
    """**チャンネルに透かし（登録ボタンの重ね）を 1度 置く。`watermarks.set`（50単位）。**

    **2026-09-16 15:3x に足した**（optimizer・Fable 5.1・ultracode）。**この回は撃っていません**
    （日枠が尽きていて、戻るのは 16:00 JST）。

    **なぜ ここが大きいか**: 縛っているのは再生ではなく**登録**で、扉(b) が要るのは **1.62%**、
    いま **0.041%**（`trend.rev_deadline` ＝ **39倍**）。
    **透かしは、いま在る本の全部に、後から載ります** ——
    台本を直すのは**これから出る本だけ**ですが、これは**公開ずみの本にも同じ日から出ます。**
    ＝ **1回 50単位 で、在庫の側にも登録の口が 1つ 増える、いちばん安い腕。**
    そして **この repo は 1度も撃っていません**（この回に grep した ＝ `watermark` の字は
    `studio/` にも `src/` にも 0件で、「絵の注文で避ける物」として出てくるだけでした）。

    `offset_ms` は本の頭から出るまでの時間・`duration_ms` は 0 で**出しっぱなし**。
    **15秒 に置いた理由**: 長尺の維持率は 5% の所で 75.8%・10% で 38.5%
    （`script.default_early_cta` の註の実測）＝ **頭の近くほど多くの人に届く**。

    **覆る条件**:
     (1) 置いた後の `trend.sub_rate_cohorts` が **3本** たまって、置く前の 0.041% を
         **越えなかったら**、絵か位置（`offset_ms`）を疑うこと。
     (2) **ショートの再生面には出ません** ＝ この腕が効くのは**長尺だけ**で、
         「公開ずみ全部」は上限です。置いた後は長尺／ショートで分けて読むこと。
     (3) 絵を変えたら `WATERMARK` の 1か所 を直すこと（写しを持たない）。
    """
    png = png or WATERMARK
    # **`timing` を渡すと 400 `Invalid Value` が返ります**（2026-09-16 15:4x に撃って確かめた）——
    # `{"type": "offsetFromStart", "offsetMs": "15000", "durationMs": "0"}` で落ちました。
    # **空の body ＝ 本のあいだ ずっと出す**（いまの YouTube の既定）で通ります。
    # `offset_ms` / `duration_ms` の欄は**残してありますが、いまは渡していません** ——
    # 次に触る回へ: 渡すなら `durationMs` を 0 以外にしてから、1回 撃って確かめること。
    body: dict = {}
    if offset_ms and duration_ms:
        body = {"timing": {"type": "offsetFromStart", "offsetMs": str(offset_ms),
                           "durationMs": str(duration_ms)}}
    svc().watermarks().set(channelId=channel()["id"], body=body,
                           media_body=MediaFileUpload(str(png), mimetype="image/png")).execute()


def set_channel_title(title: str) -> dict:
    """**チャンネルの題を変える**（`channels.list` **1単位** ＋ `channels.update` **50単位**）。

    **2026-09-17 02:xx に足した**（optimizer・Fable 5.1・ultracode）。**この回は撃っていません**
    —— 日枠が尽きていて、戻るのは 09/17 16:00 JST。

    **なぜ ここが大きいか**: 扉(b) が要るのは **11.1人/日**（`trend.rev_deadline`）。
    corpus（肩書きを外した 161口・齢<1000日）を **名前 × 制度名** で割ると、
    **うちの升（名前なし ＋ 制度名なし・46口）の中央は 1.6人/日**、隣の 2升 は **9.7／11.9**、
    両方の升は **78.8** です（`peers.title_identity`）。
    **＝ 題は「配りの腕」ではなく、門の分母そのものに乗っています。**
    **50単位 ＝ 本 1本 の 1/33** で、**公開ずみの在庫 全部の「終わった後に見える身元」**が変わります。

    **`brandingSettings` は読んでから書くこと** —— `channels.update` は渡した部を
    **丸ごと置き換えます**。読まずに `{"channel": {"title": ...}}` だけ書くと、
    `keywords`・`description`・`unsubscribedTrailer` が**黙って消えます**（紹介動画 `CdX2oIb7BG8` は
    転換 2.07/1,000 ＝ チャンネル全体の 6.5倍 を出している面・GOAL (4-p) 3 (a)）。

    **返すのは `{"before", "after", "ok"}`** ——**打った題を読み返します**（`reschedule` と同じ形・
    2026-09-16 23:3x に 2本 が黙って落ちた側の型）。`ok` が False なら台帳に書かないこと。

    **覆る条件**:
     (1) YouTube は題の変更を **14日 に 3回** までしか通しません。
         **外したら 14日 戻せません** ＝ 撃つ前に `peers.title_identity_line` の升を読むこと。
     (2) 変えたら `config/channel.yaml` の `channel.name` を**同じ回に**直すこと ——
         `trend._channel_name` はそちらを読むので、ずれると**うちではない題**を judge します。
     (3) 変えた日を `docs/GOAL.md` (4-r) に刻み、**前後 14日 の 登録/日** を並べること
         （`peers.title_identity` の覆る条件 (1) ＝ 相関を因果に変える唯一の手）。
    """
    ch = svc().channels().list(part="brandingSettings", mine=True).execute()["items"][0]
    bs = ch.get("brandingSettings") or {}
    before = (bs.get("channel") or {}).get("title", "")
    bs.setdefault("channel", {})["title"] = title
    svc().channels().update(part="brandingSettings",
                            body={"id": ch["id"], "brandingSettings": bs}).execute()
    back = svc().channels().list(part="brandingSettings", mine=True).execute()["items"][0]
    after = ((back.get("brandingSettings") or {}).get("channel") or {}).get("title", "")
    return {"before": before, "after": after, "ok": after == title}


def update_meta(video_id: str, title: str, description: str, tags: list[str]) -> None:
    """題・説明欄・tags だけを直す（videos.update 50単位。本は上げ直さない・予約もそのまま）。
    09/07 05:5x（hourly）: 予約ずみの本の説明欄の1文（実の誤り）を、ID を変えずに直すために足した。"""
    svc().videos().update(part="snippet", body={"id": video_id, "snippet": {
        "title": title, "description": description, "tags": [t[:30] for t in tags][:15],
        "categoryId": "27", "defaultLanguage": "ja", "defaultAudioLanguage": "ja"}}).execute()


def make_private(video_id: str) -> None:
    """予約を外して private のまま残す（消さない。オーナー「消さなくて良いよ」）。"""
    svc().videos().update(part="status", body={"id": video_id, "status": {
        "privacyStatus": "private", "selfDeclaredMadeForKids": False}}).execute()


def reschedule(video_id: str, publish_at: dt.datetime) -> dict:
    """予約の刻だけ動かす（`videos.update` 50単位）。**返した刻を読み返す**（+1単位）。

    **2026-09-16 23:3x（optimizer・Fable 5.1・ultracode）に読み返しを足した。実測で 2本 落ちています**:

        09/15 14:27  `FLLHpj27v7s`  09/18 19:00 → **09/15 21:00**   26.6時間 過ぎても public にならず
        09/15 14:27  `4MpH3QliNi4`  09/19 19:00 → **09/16 12:00**   11.6時間 過ぎても public にならず

    **どちらの呼びも例外を投げていません**（台帳に `scheduled` の行が残っている ＝ `cmd_reschedule` は
    「動かした」と印字して終わっている）。同じ 2日 に `reschedule` を通していない 5本 は
    **5本 とも刻どおりに出ています** ＝ 落ちているのはこの口です。

    `videos.update` は **part で指した塊を丸ごと置き換えます**。返る `status` がこちらの打った刻を
    持っていない周がある以上、**打ちっぱなしにしないこと** —— `resp["status"]` は同じ呼びが返すので、
    確かめるだけなら **0単位**。返りに刻が無いときだけ `videos.list`（1単位）で引き直して、
    それでも無ければ呼び手へ「入らなかった」を返します（判定は呼び手・ここでは投げない）。

    **覆る条件**: (1) 「返りには刻が在るのに、その刻に出ない」形が出たら、原因はこの口ではなく
    YouTube の予約そのもの ＝ そのときは `pubcheck` の鳴りを見て `schedule --replace` の側へ倒すこと。
    (2) 読み返しの 1単位 すら惜しい形になったら、落とすのは `videos.list` のほうだけ
    （返りの `status` を見る側は 0単位 なので残す）。
    """
    want = publish_at.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    resp = svc().videos().update(part="status", body={"id": video_id, "status": {
        "privacyStatus": "private", "selfDeclaredMadeForKids": False,
        "publishAt": want}}).execute()
    got = (resp.get("status") or {}).get("publishAt")
    if not got:      # 返りが持っていない周だけ、1単位 で引き直す
        r = svc().videos().list(part="status", id=video_id).execute()
        got = ((r.get("items") or [{}])[0].get("status") or {}).get("publishAt")
    stuck = bool(got) and abs(_rfc3339(got) - publish_at) <= dt.timedelta(minutes=1)
    return {"want": want, "got": got, "stuck": stuck}


def _rfc3339(s: str) -> dt.datetime:
    """YouTube が返す publishAt を datetime に（末尾 Z も読む）。"""
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def readiness(video_id: str) -> dict:
    """予約ずみの本が **10:00 に本当に出る状態か**（2026-09-08 02:5x・hourly・Fable）。

    `status` の「きょうの枠」は privacy しか見ていなかった。YouTube 側の処理
    （uploadStatus / processingStatus）が失敗していても private のまま黙って出ないので、
    公開前の周がそれを見られるように 1単位 で引く。
    実測 09/08 02:4x `lQHX9LJ80Sg`: upload=processed・processing=succeeded・失敗 None。

    **2026-09-09 01:5x（hourly・Fable）**: 同じ 1単位 に `snippet` を足し、上がっている題・説明欄・tags も返す。
    処理が通っていても、**上がっている説明欄が台本と違えば古いまま出る**（説明欄だけ直す回 ＝ 09/07 05:5x・09/08 19:1x
    が、予約の後に来たら `update_meta` を撃たない限り誰にも見えない）。突き合わせは `cli.meta_drift`。
    実測 09/09 01:4x `gv1u7n_pCAQ`: 題・説明欄 815字 一致。tags は同じ 9語 だが **YouTube は並べ替えて返す**
    （['65歳', 'シニア', …] の順）ので、比べるときは集合で。

    **2026-09-16 23:3x（optimizer・Fable 5.1・ultracode）: `publishAt` を返し、`ok` の条件に入れた。**
    この関数は「処理が終わったか」だけを見ていて、**予約の刻そのものを 1度も読んでいませんでした。**
    実測: `FLLHpj27v7s`（09/15 21:00 の枠）・`4MpH3QliNi4`（09/16 12:00 の枠）は、
    `reschedule` で刻を前へ動かしたあと **public にならないまま** 26.6時間／11.6時間 経っており、
    その間 `ready_checked` は **8周 とも `ok: true`** を書いています
    （`upload=processed`・`processing=succeeded` は本当だった ＝ **本は無事で、刻だけが消えていた**）。
    **`private` なのに `publishAt` が無い ＝ その本は永久に出ません。**
    **追加 0単位** —— `status` は同じ 1回 の `videos.list` で既に返ってきていました。
    **覆る条件**: (1) 意図して `publishAt` を外して private に置く手（`make_private`）が
    「出す予定の本」に使われる形が出たら、この `ok` は誤って赤くなる ＝ そのときは
    `cli.record_ready` の側で「台帳に生きた予約が在る本だけ」に絞ること
    （いまは `pubcheck.live_schedule` がその名簿を持っています）。
    (2) 刻が過ぎた本の検出そのものは **`pubcheck`（API 0単位）が上位の口**です ——
    こちらは日枠が尽きた周には撃てないので、**この関数を `pubcheck` の代わりにしないこと。**
    """
    r = svc().videos().list(part="snippet,status,processingDetails", id=video_id).execute()
    if not r.get("items"):
        return {"upload": "missing", "processing": "missing", "failure": None, "rejection": None, "ok": False,
                "title": None, "description": None, "tags": None, "publish_at": None, "privacy": None,
                "no_publish_at": True}
    v = r["items"][0]
    sn, st, pd = v.get("snippet", {}), v.get("status", {}), v.get("processingDetails", {})
    up, pr = st.get("uploadStatus"), pd.get("processingStatus")
    fail, rej = st.get("failureReason"), st.get("rejectionReason")
    priv, pub_at = st.get("privacyStatus"), st.get("publishAt")
    # **private なのに刻が無い ＝ 出ない本**（上の註）。public はもう出ているので刻を持たない側。
    no_at = priv == "private" and not pub_at
    ok = up == "processed" and pr in ("succeeded", None) and not fail and not rej and not no_at
    return {"upload": up, "processing": pr, "failure": fail, "rejection": rej, "ok": ok,
            "title": sn.get("title"), "description": sn.get("description"), "tags": sn.get("tags"),
            "publish_at": pub_at, "privacy": priv, "no_publish_at": no_at}


def stats(video_ids: list[str]) -> dict[str, dict]:
    out = {}
    for i in range(0, len(video_ids), 50):
        r = svc().videos().list(part="statistics", id=",".join(video_ids[i:i + 50])).execute()
        for v in r["items"]:
            out[v["id"]] = {k: int(x) for k, x in v["statistics"].items() if str(x).isdigit()}
    return out


def _comment_row(cid_: str, video_id: str, sn: dict, status: str, parent_id: str, is_reply: bool) -> dict:
    """`viewer_comments()` の1行。最上位コメントと返信で同じ形にする（読む側が分けなくてよい）。"""
    return {"id": cid_, "video_id": video_id,
            "author": sn.get("authorDisplayName", ""),
            "at": sn.get("publishedAt", ""), "likes": int(sn.get("likeCount", 0)),
            "status": status, "parent_id": parent_id, "reply": is_reply,
            "text": (sn.get("textDisplay") or "").strip()}


def _replies(thread: dict, cid: str) -> list[dict]:
    """スレッド1つの返信を全部。`commentThreads` は最大 5件 しか載せないので、足りなければ足で引く。

    `comments.list` は 1単位／スレッド。**5件 を越えるスレッドが在るときだけ**撃つ
    （2026-09-09 現在 0件 ＝ 実際の追加は 0単位）。
    """
    got = thread.get("replies", {}).get("comments", [])
    total = int(thread["snippet"].get("totalReplyCount", 0) or 0)
    if total <= len(got):
        return got
    out, tok = [], None
    while True:
        try:
            r = svc().comments().list(part="snippet", parentId=thread["id"], maxResults=100,
                                      pageToken=tok, textFormat="plainText").execute()
        except Exception:  # noqa: BLE001
            # 足で引けなくても、載っていた 5件 は失わない（退化させない）。
            return got
        out.extend(r.get("items", []))
        tok = r.get("nextPageToken")
        if not tok:
            return out or got


def _mark_answered(row: dict, ours: list[str]) -> dict:
    """その1行に **こちらが答えたか** を書き込む（`answered` / `answered_at`）。

    2026-09-09 17:2x JST（optimizer・Opus）に足した。**実物で1度 払った値段**:
    `viewer_comments()` は自分の行を落とすので、`comments`／`status` は
    **「答えた」を1度も出せません**。この回は `status` の
    「うちスレッドの返信 1件」を見て「未返信の質問が 30時間 放置されている」と読み、
    API を別に 1単位 撃って初めて **答えは 09/08 17:10 JST に出ていた**と分かりました。
    **台帳では埋まりません** —— 実測: このスレッドに こちらの返信は **2件**（08:10Z・11:29Z）
    在るのに、台帳 `replied` は **1件** だけ（`cli reply` を通らずに出た 1件が落ちている）。
    ＝ 「答えたか」の唯一の正本は API の側で、それは毎回もう引けています（追加 0単位）。

    **時刻で見ること**（数では見ない）: 答えたあとに視聴者が次を書けば、それは未返信です。
    だから「この行より**後**に こちらの返信が在るか」で決める（実測 09/08:
    03:38 の問い → 08:10 に答え → 09:41 に次の問い → 11:29 に答え ＝ どちらも返信ずみ）。

    **覆る条件**: こちらの返信が視聴者の行と**同じ秒**に並ぶ回が出たら（`>` が効かない）、
    ID の順で見ること。`cli reply` を通らない返信が 1か月 出なくなったら、
    台帳 `replied` だけで足りるので、この関数は消してよい（そのときは上の 2件/1件 も数え直す）。
    """
    later = [t for t in ours if t > (row.get("at") or "")]
    row["answered"] = bool(later)
    row["answered_at"] = later[0] if later else None
    return row


def viewer_comments(with_moderation: bool = True) -> list[dict]:
    """**視聴者が書いたコメント**を、新しい順に。自分のチャンネルが書いた分は落とす。

    返す各行に `status` が付く: `published` / `heldForReview` / `likelySpam`。

    `commentThreads.list(allThreadsRelatedToChannelId=...)` は**チャンネル全部**を1度に引く
    （1ページ 100件・実測 21件 ＝ **1単位**。本ごとに引くと 227単位 かかる）。

    **なぜ要るか（2026-09-07 20:4x JST・optimizer・Opus が実測して足した）**:
    §1 は「高評価 1,441回の本で 0」、§7 は「likes 合計 0・登録 +0 なら…」と、
    **押された数だけ**で視聴者の反応を測ってきた。**コメントは1度も数えていない。**
    実測（この回に初めて引いた）: チャンネル全部で 21スレッド。うち **18 は自分**
    （旧 `src/` の pipeline が上げる時に自動で置いていた「この計算は毎日1本ずつ出しています」）。
    **視聴者が書いたのは 3件だけ**で、そのうち中身のある1件は:

        2026-08-29 10:08  DSZfGUQ_NyQ（962回）  「ＡＩナレーショングダグダ」（同じ人が2回）

    ＝ **このチャンネルが受け取った唯一の批評は「ナレーションがグダグダ」で、9日間 誰も読んでいなかった。**
    オーナーの 09/07 13:3x「ナレーション前の音声の方が良かった」と**同じ所**を指している
    （別々の人が、別々の日に、声について言っている ＝ n=2 の一致）。
    likes は 0/1 しか動かないので分解能が無いが、コメントは文で来る。**数えること。**

    自分の分を落とすのは `authorChannelId` == 自分のチャンネル ID（表示名では見ない）。
    **保留と迷惑の列も引くこと（2026-09-08 15:0x JST・optimizer・Opus が足した）**:
    `commentThreads.list` は `moderationStatus` を省くと **`published` だけ**を返す。
    上の 20:4x の実装はそれを省いていたので、**保留（`heldForReview`）と迷惑（`likelySpam`）に
    落ちたコメントは、道具からは1件も見えなかった** —— 見えないだけでなく、
    「新着 0件」と**published と同じ顔で**印字されていた。

    これを引いた事の起こり: 09/08 12:39 JST、`lQHX9LJ80Sg`（新しい作りの3本目）に
    視聴者 `@sakimura5257` が **「コメントしたのに消えた」**と書いた（その 70秒前に
    「65歳までに死んだら丸々損したことにならないの？そこが知りたい」＝ このチャンネルが
    受け取った**初めての中身のある質問**）。**道具にはこの問いに答える口が無く**、
    その回は使い捨ての script を書いて API を直に叩くことになった。

    そのとき実測した数（2026-09-08 15:0x JST）:

        published      23スレッド（うち自分 18 ＝ 旧 pipeline の自動コメント）
        heldForReview  **0**
        likelySpam     **0**

    ＝ **消えたコメントは、こちらの保留にも迷惑にも入っていない**（YouTube 側が黙って
    消したか、投稿が届いていない）。**この回については「こちらが握り潰した」ではないと言える。**
    値打ちは、次にこれを訊かれたときに **`comments` を撃つだけで答えが出る**こと。

    API は列ごとに 1単位 ＝ **3単位**（前は 1単位）。1日の枠 10,000 に対して無視できる。

    **スレッドの中の返信も引くこと（2026-09-09 04:2x JST・optimizer・Opus が足した）**:
    `commentThreads.list` は `part="snippet"` だけだと **最上位コメントしか返しません**。
    ＝ **こちらが返信したあとに視聴者が同じスレッドへ書いた続きは、道具から1件も見えない。**

    実測（この回に API を直に撃って確かめた。スレッド `Ugxalw5necUowSfrP1t4AaABAg`）:

        09/08 03:38Z  @sakimura5257  「65歳までに死んだら丸々損したことにならないの？」  ← 最上位・**見えていた**
        09/08 08:10Z  こちら          返信1
        09/08 09:41Z  @sakimura5257  **「遺族年金は必ず受給できますか？」**              ← 返信・**見えていなかった**
        09/08 11:29Z  こちら          返信2

    台帳には **2問目の `viewer_comment` 行が1行も無く**、`replied` 行だけが在ります
    （`grep '遺族年金は必ず' data/studio/ledger.jsonl` ＝ 0件）——
    **答えは残っているのに、問いは残っていない。** 20:2x の回が使い捨ての script で API を直に見て
    気づいたから答えられただけで、道具は「新着 0件」と言い続けていました
    （§7 は 20:4x・21:4x・23:0x・00:2x・01:5x・02:5x の 6周 それを書き写しています）。
    **`status` の「新着 0件」は、いちばん濃い反応（会話の続き）を構造的に見ていませんでした。**

    **もう1つ、同じ穴の大きいほう**: 最上位が**自分**のスレッド（旧 pipeline の自動コメント **18本**）は
    `continue` でスレッドごと落としていたので、**そこに視聴者が返信しても永久に見えません**。
    いまは「自分の**行**を落とす」だけにし、返信は必ず見ます。

    API: `part="snippet,replies"` は `commentThreads.list` の単位を増やしません（列ごと 1単位 ＝ 3単位のまま）。
    `replies` は**最大 5件**しか返らないので、`totalReplyCount` がそれより多いスレッドだけ
    `comments.list(parentId=...)` を足で引きます（そのスレッド 1つにつき 1単位。いまは 0件）。

    返る行: `parent_id`（スレッド ID ＝ 返信先）と `reply`（True なら返信）が付きます。
    `cli reply` は `parent_id` へ撃つこと（返信の ID は `parentId` に渡せない）。

    **覆る条件**: スパムや無関係なコメントが視聴者側に混ざり始めたら、ここで選り分けず
    そのまま出して、読む側（次の回）が判断する（いまは 5件なので選り分けは要らない）。
    保留・迷惑が常に 0 のまま 1か月 続いたら、その2列は引かずに `published` だけへ戻してよい
    （そのときは、この註と `with_moderation` を消すこと）。
    返信を1件も持たないスレッドしか 1か月 出なくなったら…では**戻さないこと**:
    返信が来ない証拠は、返信を引いて初めて得られる（引くのをやめると、また見えなくなる）。
    """
    cid = channel()["id"]
    cols = ("published", "heldForReview", "likelySpam") if with_moderation else ("published",)
    out = []
    for col in cols:
        tok = None
        while True:
            try:
                r = svc().commentThreads().list(
                    part="snippet,replies", allThreadsRelatedToChannelId=cid, moderationStatus=col,
                    maxResults=100, pageToken=tok, textFormat="plainText").execute()
            except Exception:  # noqa: BLE001
                # 保留・迷惑の列は権限や仕様で落ちることがある。published を落とさない。
                if col == "published":
                    raise
                break
            for t in r.get("items", []):
                vid = t["snippet"].get("videoId", "")
                tls = t["snippet"]["topLevelComment"]["snippet"]
                reps = _replies(t, cid)
                # **こちらが書いた返信の時刻**（行は返さないが、「答えたか」はここでしか分からない）。
                ours = sorted(c["snippet"].get("publishedAt", "") for c in reps
                              if c["snippet"].get("authorChannelId", {}).get("value") == cid)
                rows = []
                # 最上位が自分でも **スレッドは落とさない**（返信に視聴者が居る）。落とすのはこの行だけ。
                if tls.get("authorChannelId", {}).get("value") != cid:
                    rows.append(_comment_row(t["id"], vid, tls, col, t["id"], False))
                for c in reps:
                    cs = c["snippet"]
                    if cs.get("authorChannelId", {}).get("value") == cid:
                        continue
                    rows.append(_comment_row(c["id"], vid or cs.get("videoId", ""), cs, col, t["id"], True))
                for row in rows:
                    _mark_answered(row, ours)
                out.extend(rows)
            tok = r.get("nextPageToken")
            if not tok:
                break
    return sorted(out, key=lambda c: c["at"], reverse=True)


def reply(comment_id: str, text: str) -> str:
    """視聴者のコメント1件に、**手で書いた**返信を1つ付ける（`comments.insert`・**50単位**）。

    2026-09-08 15:1x JST（hourly・Fable）に足した。新しい作りの本 `lQHX9LJ80Sg` に付いた最初の
    視聴者の問い「65歳までに死んだら丸々損したことにならないの？そこが知りたい」に答えるため。
    §7 20:4x の「唯一の批評が 9日間 未読」は読む側の穴だったが、読んだあと**答える口が無い**のも同じ穴。
    旧 `scripts/post_pending_comments.py` の自動投稿（全本に同じ1文を機械で置く ＝ §8 で止めた口）とは違う:
    **文はサブ本人が書き、`cli reply` から1件ずつ・台帳に `replied` を残して**撃つ。背景から呼ぶ口は作らない。
    `comment_id` は `viewer_comments()` の `id`（スレッド ID ＝ 最上位コメントの ID。`parentId` に渡せる）。
    スコープは旧 `src/auth.py` と同じ refresh token（`youtube.force-ssl` 込み）。
    """
    r = svc().comments().insert(part="snippet", body={"snippet": {
        "parentId": comment_id, "textOriginal": text[:9000]}}).execute()
    return r.get("id", "")


# 伸びている本の再生は、**同じ瞬間に 2つの値が返る**（2026-09-09 19:1x・optimizer・Opus が実測）。
SETTLE_READS = 3


def settle_stats(ids: list[str], reads: int = SETTLE_READS) -> dict[str, dict]:
    """同じ本を `reads` 回 読み、**最大**（＝いちばん新しい複製）と最小・値の数を返す。**1回 1単位**。

    **なぜ**（2026-09-09 19:1x JST・optimizer・Opus。撃って確かめた）: `videos.list` は
    **伸びている本を、遅れの違う複数の複製から返す**。実測 12回（3秒 おき・4本 同時）:

        gv1u7n_pCAQ（公開 9h・伸び中）  **637 が 6回・823 が 6回**（差 **186回 ＝ 29%**）
        lQHX9LJ80Sg（33h・平ら）        468 が 12回（差 0）
        nQbVxuWpWw8（57h）・PhQ2KvuQASQ（58h）  差 0

    ＝ **揺れるのは伸びている本だけ**で、落ち着いた本は複製が揃う。低いほうの 637 は
    **2時間 前（17:16 の台帳の行）の値そのもの**なので、低い側が「遅れている複製」。
    真の再生は減らないので、**複数回 読んだ最大が いちばん新しい**（最小はその時刻の下限）。

    この揺れは 09/09 19:09 の `measure` に **711 → 637（-74回）** と書かせ、その 1分前の
    `status` は同じ本を **823回** と印字した（同じ `videos.list`・同じ道）。
    §7 が 4か所で使っていた「再生は最大 -5回 しか減らない ＝ 下限で比べてよい」は、
    **その -5 が複製の揺れの下端**だった（本物の下限は「複数回 読んだ最小」）。

    **【2026-09-12 13:3x・optimizer・Opus】この覆る条件が初めて引かれ、最大のまま据え置きました。**
    引いたのは `trend.shakes` の `over_max`（`EkNqtkK49Bw` 4行・**145 対 水準 145+1**）。
    **本物の掘り起こしですが、大きさが釣り合いません**: 掘り起こし **1回** 対、
    この関数が直している遅れの割れ **249回**（`gv1u7n_pCAQ` 齢 10.0h・637 対 886）＝ **0.4%**。
    しかも 09/09 19:1x の実測は **637 が 6回・823 が 6回** ＝ **5回 読みの中央値は五分五分で低い側**
    ＝ **中央値へ移すと、1回 を直すために 249回 を落としうる。**
    **2つとも一過性**でもあります —— 低く書いた点は次の周の包絡（単調な最大）が上書きし、
    高く書いた点は `recounts()` が `ENVELOPE_LAG_H`（6時間）で落とします。
    **決め: `reads` は 3・戻すのは最大のまま。門は回数ではなく大きさ**
    （`trend.OVER_SIZE_GATE` ＝ 掘り起こしの最大 ÷ 割れの最大 が 10%。
     **毎周 `trend` の「割れた読み」の行が印字する ＝ 手で数えないこと**）。
    **新しい覆る条件 4つ は `trend.over_verdict` の註**・derivation は JOURNAL 13:3x。

    **覆る条件**: 落ち着いた本（48h 超）でも差が出たら、遅れではなく数え直しの側 ——
    そのときは最大ではなく中央値へ（`reads` を 5 に上げてから）。
    **ただし引くのは `trend.over_verdict()["drawn"]` が立った回だけ**（上の 13:3x）。
    **この条件は 2026-09-10 06:3x まで引けませんでした** —— 呼ぶ側（`cli.cmd_measure`）が
    齢 48h までの本しか渡しておらず、48h 超の行に `n_values` の欄が作られなかった。
    門を束の大きさへ移して（`cli.SETTLE_MAX_IDS`・単位は同じ）、**いまは出られます**。
    初回の実測（06:2x・48h 超 17本・3回 読み）は **`n_values > 1` が 0本**。伸びている本で
    3回 とも同じ値しか出ない回が 1週間 続いたら、複製が揃った ＝ この読み直しは外してよい。
    """
    seen: dict[str, list[int]] = {}
    gone: set[str] = set()
    for _ in range(max(1, reads)):
        for i in range(0, len(ids), 50):
            r = svc().videos().list(part="statistics", id=",".join(ids[i:i + 50])).execute()
            for v in r["items"]:
                st = v.get("statistics", {})
                views, absent = views_of(st)
                seen.setdefault(v["id"], []).append(views)
                if absent:
                    # 欄が無い読みが 1回 でも在れば印を立てる（`views_of` の註）。
                    gone.add(v["id"])
    return {k: {"views": max(vs), "views_min": min(vs), "n_values": len(set(vs)),
                "views_absent": k in gone}
            for k, vs in seen.items() if vs}
