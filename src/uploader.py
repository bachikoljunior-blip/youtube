"""YouTube Data API v3 へのアップロード。"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from . import measure_window, upload_cap
from .auth import credentials, explain, is_upload_cap, note_day_quota

JST = timezone(timedelta(hours=9))
RETRYABLE = {500, 502, 503, 504}


def scheduled_publish_times(youtube) -> set[str]:
    """すでに予約済みの公開時刻を集める。RFC3339(UTC) の文字列で返す。"""
    channel = youtube.channels().list(part="contentDetails", mine=True).execute()["items"][0]
    uploads = channel["contentDetails"]["relatedPlaylists"]["uploads"]
    items = youtube.playlistItems().list(
        part="contentDetails", playlistId=uploads, maxResults=50
    ).execute().get("items", [])
    ids = [i["contentDetails"]["videoId"] for i in items]
    if not ids:
        return set()
    videos = youtube.videos().list(part="status", id=",".join(ids)).execute().get("items", [])
    return {v["status"]["publishAt"] for v in videos if v["status"].get("publishAt")}


def ledger_publish_times() -> set[str]:
    """予約済みの公開時刻を、**手元の控えから**返す（RFC3339(UTC) の文字列）。

    `scheduled_publish_times()` と同じ形を返しますが、**API を1単位も使いません。**
    使う先は下の `taken_publish_times()` ——「口が読めない回の代わり」です。

    **上限側の見積りです。** 取り消した本の行も残るので、空いている枠を
    「埋まっている」と読むことがあります。**外す向きは安全**で、
    日付を釘づけしている回は1本ぶん置けずに止まるだけ、
    釘づけしていない回は1日後ろへ送られるだけです。
    """
    from . import dupes

    return {str(r["at"]) for r in dupes.ledger_rows() if r.get("at")}


def taken_publish_times(youtube) -> set[str]:
    """予約済みの時刻を口から読み、**日枠切れなら控えに落ちる**（2026-08-17）。

    ## なぜ要るか（**この形で1件、実際に止まっていました**）

    Data API の1日枠（10,000単位）が切れると、`scheduled_publish_times()` の
    `channels.list` が 403 で落ちます。ここは `upload()` の中から素通しで
    呼ばれていたので、**例外がそのまま上がって投稿ごと死にます。**

    ところが**枯れているのは読みだけかもしれません。** 申し送りはこう言っています ——
    「枯れているのは `search` と `videos.list` で観測しただけで、
    **`videos.insert` を実際に叩いた回は1つも無い**」。3回運ばれて、
    3回とも確かめられていません。**確かめる道が塞がっていたから**です。

    `taken` の使い道は2つしかありません。日付を釘づけした回は
    「その時刻が埋まっていないか」、していない回は「何日ぶん後ろへ送るか」。
    **どちらも控え（`data/uploaded.jsonl`）で答えが出ます** ——
    控えは投稿した本人が書くので、**置いた本が落ちることはありません。**

    だから、読めない回は控えで代えて**先へ進みます。**
    そこで `videos.insert` が 403 なら、**それは初めて測った事実**です。
    通れば、日枠が戻る JST 16:00 までの十数周が投稿できるようになります。
    """
    try:
        return scheduled_publish_times(youtube)
    except HttpError as exc:
        note_day_quota(exc, "scheduled_publish_times")
        if getattr(exc, "resp", None) is not None and exc.resp.status not in (403, 429):
            raise
        rows = ledger_publish_times()
        print(f"[upload] **予約一覧が口から読めません**（HTTP "
              f"{getattr(exc.resp, 'status', '?')}）。手元の控え {len(rows)}本で代えます。"
              " **上限側の見積り**なので、空きを1つ余計に飛ばすことがあります。")
        return rows


def _parse_date_jst(date_jst: str) -> datetime:
    """予約日を読む。**`MM/DD` も受けます**（2026-08-19 08:1x に9本ぶん捨てて足した）。

    ここは長らく `%Y-%m-%d` だけで、それ以外は `ValueError` でした。
    **落ちる場所が悪い** —— この関数は `videos.insert` の直前にあるので、
    `batch_build.py --date 08/23` は**9本ぶんの生成（約20分）を全部やってから**
    予約の段で9本とも落ちました（`予約できたのは 0 / 9 本`）。
    しかも `batch_build` は自分の表示では `08/23` をそのまま受けて
    「**08/23 の1日に入れます**」と印字するので、**渡した側からは正しく見えます。**

    **形を増やすのが直しの本体ではありません。** 本体は
    `batch_build` が**撃つ前にこれを通すこと**（`normalize_date_jst`）。
    ここだけ直しても、次に別の形を渡した回はまた20分を捨てます。

    年の無い `MM/DD` は**今年**として読みます。過ぎていても来年へは送りません
    （打ち間違いが11か月先の予約に化けるので、下の「過去か直近すぎます」に任せる）。
    """
    text = date_jst.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    for fmt in ("%m/%d", "%m-%d"):
        try:
            bare = datetime.strptime(text, fmt)
        except ValueError:
            continue
        # **年は今年に固定します。過ぎていても来年へ送らないこと**（2026-08-19）。
        # 送ると `--date 07/23` のような打ち間違いが**11か月先の予約**に化けて、
        # 静かに通ります。過ぎた日は下の「過去か直近すぎます」で落ちるほうが安全。
        return datetime(datetime.now(JST).year, bare.month, bare.day)
    raise ValueError(
        f"日付は YYYY-MM-DD か MM/DD で渡すこと: {date_jst!r}")


def normalize_date_jst(date_jst: str) -> str:
    """`--date` を `YYYY-MM-DD` に直す。**撃つ前に、入口で通すこと。**

    空文字はそのまま返します（`--date` を渡さない道は従来どおり）。
    """
    if not date_jst:
        return ""
    return _parse_date_jst(date_jst).strftime("%Y-%m-%d")


def next_publish_at(hour_jst: int, minute_jst: int, taken: set[str] | None = None,
                    date_jst: str | None = None, force_window: bool = False) -> str:
    """次に空いている指定時刻（JST）を RFC3339(UTC) で返す。

    taken にすでに予約済みの時刻を渡すと、その日を飛ばして次の日を返す。

    これが無いと、作り置きを続けたときに**同じ時刻へ2本重なる**。
    重なると2本が食い合ううえ、翌日が空になる。投稿が途切れるのが最大の損失
    なので、間隔を空けるほうが常に良い。実際に P5yRTOMRulc の予約がある状態で
    次の1本を積もうとして、同じ 8/5 19:00 に当たった。

    ## `date_jst` を足した理由（2026-08-15）

    **日を飛ばす既定の動きは、「1日にN本」を作れません。**
    M14（`docs/MEANS.md`）は本数の段を 2 → 4 → 8 と上げて1本あたりが崩れる点を
    探す手ですが、**同じ日に8本置く道が無い**ので 8 の段に上がれませんでした。
    `--hour 10` は「10:00 で最初に空いている**日**」を返すので、
    8本ぶん呼ぶと**8日にばらけます**（それは1日1本の実験です）。

    `date_jst`（`YYYY-MM-DD`）を渡すと**その日に釘づけ**します。
    埋まっていたら**翌日へ送らずに例外**を上げます —— 送ってしまうと
    「1日8本のつもりが7本＋翌日1本」になり、**測っている数字のほうが壊れる**ためです。

    ## 測定の窓（2026-08-18 に足した）

    **予約時刻を決めているのは、この関数だけです。** `batch_build.py` も
    `upload_only.py` も `pipeline` も、最後はここへ来ます。だから
    `src/measure_window.py` の門はここに置いてあります（入口ごとに置くと、
    **次に入口を足した回が書き忘れます** —— 実際 `batch_build.py` にしか
    無く、しかも `--date` を渡した時だけ呼ばれていました）。

    **2つの道で、止め方が違います**（理由は `measure_window` の docstring）:

        自動で探す（`date_jst` なし） → **窓の日を飛ばす。** 投稿は止めない
        釘づけ（`date_jst` あり）     → **例外。** `force_window=True` で通せる
    """
    now = datetime.now(JST)

    if date_jst:
        day = _parse_date_jst(date_jst)
        target = datetime(day.year, day.month, day.day,
                          hour_jst, minute_jst, tzinfo=JST)
        if target <= now + timedelta(minutes=20):
            raise ValueError(
                f"{date_jst} {hour_jst:02d}:{minute_jst:02d} JST は過去か直近すぎます"
                "（予約は20分先から）"
            )
        # **窓を見るのは、形と過去を弾いたあと。** 窓は「置けるが置きたくない日」で、
        # 形の誤りや過去の日は「そもそも置けない日」です。**先に窓で止めると、
        # 直し方が違うものに同じ札が付きます** —— 実際 `--date <昨日>` が
        # 「M14 の窓です」と答えました（昨日はたまたま窓の中だった）。
        measure_window.check(date_jst, force=force_window,
                             tool="uploader.next_publish_at(date_jst=…)")
        stamp = target.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if stamp in (taken or set()):
            raise ValueError(
                f"{date_jst} {hour_jst:02d}:{minute_jst:02d} JST はすでに埋まっています。"
                "**翌日へは送りません**（1日あたりの本数を測っているため）"
            )
        return stamp

    target = now.replace(hour=hour_jst, minute=minute_jst, second=0, microsecond=0)
    if target <= now + timedelta(minutes=20):
        target += timedelta(days=1)

    taken = taken or set()
    skipped: list[str] = []
    for _ in range(60):     # 2か月ぶんまで探せば十分。無限には回さない。
        stamp = target.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        day_jst = target.strftime("%Y-%m-%d")
        # **窓の中は飛ばす（止めない）。** ここで例外を上げると、窓のあいだ
        # 投稿が丸ごと止まります。**投稿が途切れるのが最大の損失**なので、
        # 測定を守る安いほうの手（先へ送る）を取ります。
        if not force_window and measure_window.inside(day_jst):
            skipped.append(day_jst)
            target += timedelta(days=1)
            continue
        if stamp not in taken:
            if skipped:
                print(f"[window] M14 の比較の窓を飛ばしました: {', '.join(skipped)}"
                      f" → {day_jst} {hour_jst:02d}:00 JST", flush=True)
            return stamp
        target += timedelta(days=1)
    raise RuntimeError("空いている公開枠が2か月先まで見つかりませんでした")


def _service():
    return build("youtube", "v3", credentials=credentials(), cache_discovery=False)


def _find_or_create_playlist(youtube, title: str) -> str:
    """同名の再生リストを探し、無ければ作る。"""
    page_token = ""
    while True:
        response = youtube.playlists().list(
            part="snippet", mine=True, maxResults=50, pageToken=page_token or None
        ).execute()
        for item in response.get("items", []):
            if item["snippet"]["title"] == title:
                return item["id"]
        page_token = response.get("nextPageToken", "")
        if not page_token:
            break

    # **ここも 50単位**。`_post_actions` から呼ばれますが、木を歩く検査は
    # **いちばん内側の関数**を入口と数えるので、ここにも要ります
    # （別の呼び元ができた日に、この門だけが残ります）。
    hold = upload_cap.reserve_hold()
    if hold:
        raise RuntimeError(f"再生リストを作りません: {hold}")
    created = youtube.playlists().insert(
        part="snippet,status",
        body={
            "snippet": {"title": title, "description": ""},
            "status": {"privacyStatus": "public"},
        },
    ).execute()
    upload_cap.note_quota_ok(detail="playlists.insert")
    print(f"[upload] 再生リストを新規作成: {title}")
    return created["id"]


def _post_actions(youtube, video_id: str, publish_cfg: dict) -> None:
    """投稿後の付随処理。ここで失敗しても動画は既に上がっているので落とさない。

    **1本あたり 150単位**（再生リスト作成 50 ＋ 項目 50 ＋ コメント 50）。
    実測 08/27 の窓は 37本 を上げているので **5,550単位** ——
    残してある `RESERVE_UNITS` 400 の **13.9倍**を、
    2026-08-28 の2周目まで**数えも止めもせず**に使っていました。

    **止めてよい理由**: ここは元々「失敗しても落とさない」設計で、
    やり残しを後から拾う道具が両方あります
    （`scripts/playlists.py` / `scripts/post_pending_comments.py`）。
    **動画は上がっています。** 一方、残している 400単位 が守るのは
    「前提を閉じる読み」で、`eta.py` が毎回「軌跡の腕が動くのは
    前提を1件 閉じたときだけ」と言う、その唯一の操作です。

    **覆る条件**: 拾い直す道具のどちらかが無くなったら、
    ここで止めたぶんは永久に埋まりません。そのときは止めないこと。
    """
    hold = upload_cap.reserve_hold()
    if hold:
        print(f"[upload] {hold}")
        print("[upload] **再生リストと最初のコメントは後回しにします**"
              "（動画は投稿済み）。窓が変わった回に"
              " `python scripts/playlists.py` と"
              " `python scripts/post_pending_comments.py` が拾います。")
        return
    playlist = (publish_cfg.get("playlist") or "").strip()
    if playlist:
        try:
            playlist_id = _find_or_create_playlist(youtube, playlist)
            youtube.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {"kind": "youtube#video", "videoId": video_id},
                    }
                },
            ).execute()
            upload_cap.note_quota_ok(detail=f"playlistItems.insert {video_id}")
            print(f"[upload] 再生リストに追加: {playlist}")
        except HttpError as exc:
            note_day_quota(exc, "playlistItems.insert")
            print(f"[upload] 再生リストへの追加に失敗（動画は投稿済み）: {exc}")

    comment = (publish_cfg.get("first_comment") or "").strip()
    if comment:
        try:
            youtube.commentThreads().insert(
                part="snippet",
                body={
                    "snippet": {
                        "videoId": video_id,
                        "topLevelComment": {"snippet": {"textOriginal": comment[:9000]}},
                    }
                },
            ).execute()
            upload_cap.note_quota_ok(detail=f"commentThreads.insert {video_id}")
            # 固定だけは API に無い。Studio で1タップしてもらう。
            print("[upload] 最初のコメントを投稿しました。"
                  "固定はAPIでできないので、Studioで「固定」を押してください:")
            print(f"         https://studio.youtube.com/video/{video_id}/comments")
        except HttpError as exc:
            note_day_quota(exc, "commentThreads.insert")
            print(f"[upload] コメント投稿に失敗（動画は投稿済み）: {exc}")


def _set_thumbnail(youtube, video_id: str, path: Path, tries: int = 4) -> bool:
    """サムネイルを設定する。**失敗したら待って撃ち直す。**

    2026-08-05、`SsUYduA1dpg` で 403 forbidden が返った。直前の4本は成功して
    いたので権限の問題ではなく、**アップロード直後で動画側の処理が終わって
    いなかった**のが原因。手で撃ち直したら一発で通った。

    これまでは失敗を print するだけで先へ進んでいた。**黙って通す**のと同じで、
    サムネイルの無い動画がそのまま公開予約に入る。ショートでも検索結果や
    関連動画には出るので、自動生成のフレームのままにする理由が無い。

    権限（チャンネル未確認）なら何度撃っても通らないので、回数で打ち切る。
    """
    # **計測のぶんを残して止める**（2026-08-28 の最適化の回に足した）。
    # `thumbnails.set` は **50単位**。実測の窓（08/27 16:00 JST）は
    # **47分 で 9,150単位** を焼き、そのあと 23.2時間、**4単位 の
    # `videos.list` が撃てません**（`src/upload_cap.RESERVE_UNITS`）。
    #
    # **この数は 2026-08-28 に直しました。** ここには 14,150 と書いてありました ——
    # `dedupe_ok()` を通す前の、二重書きを数えた幻の数です。
    # `upload_cap.measured_budget()` の註で 9,150 に直った側だけが直り、
    # **写しであるこちらは古いまま**でした。この数を読んで `RESERVE_UNITS` を
    # 決め直す回があると、枠を 55% 高く見積もります。
    # **ここは投げません** —— 投稿そのものは日枠を1単位も使わないので、
    # 止めるのはサムネだけ。控えに bytes が残り、窓が変わった回に
    # `refresh_thumbnail.py --missing` で押せます（下の枠切れと同じ扱い）。
    try:
        from . import upload_cap as _cap
        _hold = _cap.reserve_hold()
    except Exception:                                          # noqa: BLE001
        _hold = None
    if _hold:
        print(f"[upload] **サムネイルは載せません**: {_hold}")
        print("[upload] **投稿は続けます。** 控えに bytes は残るので、"
              "窓が変わった回に `refresh_thumbnail.py --missing` で押せます。")
        return False
    for attempt in range(1, tries + 1):
        try:
            youtube.thumbnails().set(
                videoId=video_id, media_body=MediaFileUpload(str(path))
            ).execute()
            upload_cap.note_quota_ok(detail=f"thumbnails.set {video_id}")
            print(f"[upload] サムネイル設定完了{'（%d回目）' % attempt if attempt > 1 else ''}")
            return True
        except HttpError as exc:
            # **単位枠の 403 は、待っても戻りません**（2026-08-17 22:4x に足した）。
            # この関数が想定していた 403 は「投稿直後で動画側の処理が未了」で、
            # そちらは待てば通ります。**枠切れは窓が変わるまで通りません。**
            # 見分けずに撃ち直すと、1本あたり 30秒（5+10+15）を捨てます ——
            # 8本の回で **4分**、しかも4回とも同じ理由で落ちます。
            if note_day_quota(exc, f"thumbnails.set {video_id}"):
                print(f"[upload] **サムネイルは日枠（単位）切れで載りません**: {str(exc)[:120]}")
                print("[upload] **投稿は続けます。** 控えに bytes は残るので、"
                      "窓が変わった回に `refresh_thumbnail.py --missing` で押せます。")
                return False
            if attempt == tries:
                print(f"[upload] **サムネイルを設定できませんでした**（{tries}回試行）: {exc}")
                print("[upload] 自動生成のフレームのまま公開されます。"
                      "チャンネルの電話番号確認が済んでいるか確かめること。")
                return False
            wait = 5 * attempt
            print(f"[upload] サムネイル設定に失敗。{wait}秒待って撃ち直します（{attempt}/{tries}）")
            time.sleep(wait)
    return False


def base_status(publish_cfg: dict | None = None) -> dict:
    """**投稿のときにこちらが立てる `status` の欄**（`publishAt` は含みません）。

    2026-08-17 に切り出しました。理由は `videos().update` の側にあります ——
    あれは部分更新ではないので、**書き込む前に現状を読む**必要があり、
    日枠が切れている13時間は `reschedule._update` ごと落ちていました。

    **ここに出てくる4つは、全部こちらが投稿のときに決めた値です。**
    自分で立てた値なら、外の口が落ちていても分かります
    （`src/history.py`・`src/dupes.py` と同じ切り分け。
    **読めないときに困るのは「他人が変えたかもしれない欄」だけ**）。
    """
    cfg = publish_cfg or {}
    return {
        "privacyStatus": cfg.get("visibility", "private"),
        "selfDeclaredMadeForKids": bool(cfg.get("made_for_kids", False)),
        "license": "youtube",
        "embeddable": True,
    }


def _note_cap(exc: Exception) -> None:
    """**1日の投稿本数の枠に当たったら、その観測を残す**（2026-08-17）。

    置き場所を `videos.insert` が落ちるこの1か所にしているのは、**呼ぶ側が
    2つある**からです（`scripts/upload_only.py` と、それを叩く
    `scripts/batch_build.py`）。呼ぶ側に書くと、この repo で通算9回出ている
    **「片方だけ」**になります —— 実際 `upload_only.py` を手で叩いた回は、
    どこにも記録が残りませんでした。

    **残さないと、次の回に伝わる経路は日誌の散文だけです。**
    11:0x の回は 10:5x の日誌を読んで「たぶん今も閉じている」と**推測**しました。
    残せば `src/upload_cap.state()` が**確実に**「閉じている」と言えます。

    **ここで例外を出さないこと。** 記録できないことより、投稿の失敗の理由が
    呼ぶ側に返らないほうが高くつきます。
    """
    note_day_quota(exc, "videos.insert")
    if not is_upload_cap(exc):
        return
    try:
        from . import upload_cap
        upload_cap.note_hit(detail=str(exc)[:160])
    except Exception as note_exc:                              # noqa: BLE001
        print(f"[upload] 枠の観測を残せませんでした（続行）: {str(note_exc)[:80]}")


def upload(
    video_path: Path,
    thumbnail_path: Path,
    title: str,
    description: str,
    tags: list[str],
    publish_cfg: dict,
) -> str:
    youtube = _service()

    visibility = publish_cfg.get("visibility", "private")
    status: dict = base_status(publish_cfg)
    # private のときだけ予約公開できる。public 指定なら即時公開。
    if visibility == "private":
        # すでに埋まっている枠は飛ばす。作り置きを積むと同じ時刻に重なるため。
        status["publishAt"] = next_publish_at(
            int(publish_cfg.get("publish_hour_jst", 19)),
            int(publish_cfg.get("publish_minute_jst", 0)),
            taken=taken_publish_times(youtube),
            date_jst=publish_cfg.get("publish_date_jst") or None,
        )
        print(f"[upload] 公開予定: {status['publishAt']}")
        # **決めた時刻を、呼んだ側にも返すこと**（2026-08-16）。
        # `scripts/upload_only.py` は `channel["publish"]["publish_at"]` を読んで
        # `data/uploaded.jsonl` に控えます。ところがこの時刻は**ここで初めて決まる**ので、
        # 書き戻さないと控えの `at` が**必ず null** になります。
        # 実測: 控えを入れた 8/16 02:5x 以降に上げた予約7本が、**7本とも null**。
        # 埋め戻した48本には時刻が入っていたので、**壊れて見えませんでした**
        # （新しい行だけが空で、一覧の見た目は変わらない）。
        # これが効く先は2つ —— `dupes.ledger_rows()` の `scheduled` と、
        # `sibling_check` の在庫（＝予約が何日先まで埋まっているか）。
        publish_cfg["publish_at"] = status["publishAt"]

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:4900],
            "tags": [t[:30] for t in tags][:15],
            "categoryId": str(publish_cfg.get("category_id", "27")),
            "defaultLanguage": "ja",
            "defaultAudioLanguage": "ja",
        },
        "status": status,
    }

    # 分割アップロード。20MB超を一発で送ると、途中で切れたときに
    # 上がったのかどうかも分からなくなる。
    media = MediaFileUpload(str(video_path), chunksize=8 * 1024 * 1024, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    attempt = 0
    while response is None:
        try:
            progress, response = request.next_chunk()
            if progress:
                print(f"[upload] {int(progress.progress() * 100)}%")
        except HttpError as exc:
            if exc.resp.status in RETRYABLE and attempt < 5:
                wait = 2 ** attempt
                attempt += 1
                print(f"[upload] {exc.resp.status} のため {wait}s 後に再試行")
                time.sleep(wait)
                continue
            _note_cap(exc)
            raise RuntimeError(explain(exc)) from exc
        except Exception as exc:
            _note_cap(exc)
            raise RuntimeError(explain(exc)) from exc

    video_id = response["id"]
    print(f"[upload] 完了: https://youtu.be/{video_id}")

    _post_actions(youtube, video_id, publish_cfg)

    if thumbnail_path.exists():
        # **載ったかどうかを、呼んだ側にも返すこと**（2026-08-17）。
        # `publish_at` と同じ書き戻しです。理由も同じで、**ここでしか分からない**。
        #
        # 日枠が切れている13時間は `thumbnails.set` だけが 403 になり、
        # **投稿は成功してサムネイルだけ無い予約**が積まれます。この結果を
        # 落とすと、あとから「どの本が載っていないか」を言えるのは
        # **日誌の散文だけ**になり、実際に3回持ち越されました
        # （`scripts/critique_queue.missing_thumbnail`）。
        publish_cfg["thumbnail_set"] = _set_thumbnail(
            youtube, video_id, thumbnail_path)

    return video_id
