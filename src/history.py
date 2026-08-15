"""投稿履歴を YouTube 側から復元する。

ファイルに「投稿済み」を書き溜めると、動画を消したときに嘘になる。
消えた動画のテーマがいつまでも使用済みのままになり、新しいランナーでは空になる。
そこで説明欄に [t:<テーマID>] を埋めておき、毎回チャンネルから読み直す。
状態はチャンネルそのものが持ち、こちらは何も覚えない。
"""
from __future__ import annotations

import re

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .auth import credentials

MARKER = "[t:{}]"
MARKER_RE = re.compile(r"\[t:([a-z0-9\-]+)\]")


def marker(topic_id: str) -> str:
    return MARKER.format(topic_id)


def topic_video_map() -> dict[str, str]:
    """テーマID → 動画ID。**独立評価のスコアを実績に結びつけるのに要る。**

    2026-08-15 に見つけた穴。`data/critique.jsonl` はスコアを **テーマID**
    （`s-zangyo-2`）で積んでいるのに、`critique_record.py --check` が
    突き合わせる Analytics は **動画ID**（`7b2-Z6Jw5DQ`）で来ます。
    `perf.get("s-zangyo-2")` は**必ず None** なので、
    **突き合わせは1件も成立しません。**

    それでも画面には「engaged と突き合わせられたもの 0件 / 必要 6件」と出て、
    続けて「公開直後は Analytics に行が出ません。2〜3日遅れます」と説明されます。
    **待てば埋まるように見えて、構造上いつまでも埋まりません。**

    これが止めていたもの: M13 の較正は「6本たまった時点」で終わる約束で、
    その較正が終わるまで独立評価の門は宙づり、そして
    `docs/CRITIQUE.md` によればその門が **M14（唯一残っている伸ばす手）** を塞ぎます。

    テーマIDは説明欄の `[t:...]` にあるので、**チャンネル側から引き直せます。**
    記録の書き方は変えません（評価は投稿の前にやるので、その時点で動画IDはまだ無い）。
    **突き合わせる側で解決します。**
    """
    return _scan(want_map=True)


def posted_topic_ids() -> set[str]:
    """チャンネルに今ある動画の説明欄から、投稿済みのテーマIDを集める。"""
    return _scan(want_map=False)


def channel_video_ids(youtube, uploads: str, cap: int = 400) -> list[str]:
    """チャンネルにある動画IDを、**2つの口の和**で集める。

    ## なぜ和なのか（2026-08-15 23:0x に実測して分かった）

    ここは長らく **uploads プレイリストだけ**を読んでいました。
    CLAUDE.md は「投稿済みは説明欄の `[t:テーマID]` から**チャンネル越しに復元する**。
    ファイルに持たない」と言っており、その復元の唯一の入口がここです。

    **uploads プレイリストは、予約中（private）の動画を落とします。** 実測:

        uploads プレイリスト  69本
        search(forMine)      76本
        差 7本 —— **7本とも private で、publishAt が入っている**

    しかも同じ日のうちに 69 と 76 の両方を返しました（**遅れて揃う口**で、
    件数を見ても壊れているように見えません）。落ちた7本の説明欄には
    `[t:s-kojo-2]` などが入っており、**投稿済みなのに未投稿として数えられます。**

    ## 何が起きたか（この回が実際に踏んだ）

    `batch_build.pick` は `posted_topic_ids()` を引いて未投稿を選びます。
    見えていなかった `s-kojo-2` / `s-kojo-3` がもう一度選ばれ、
    **同じ計算・同じ金額のショートを作って予約しました**
    （`1万2709円` が 8/18 と 8/19 に、`7万7161円` が 8/18 と 8/20）。

    **これは見栄えの話ではありません。** YouTube は
    「同じチャンネルの動画を続けて数本視聴した後、繰り返しのように感じられる
    可能性のあるコンテンツ」を**収益化の対象外**と書いています。
    収益化されなければ収入はゼロなので、**自分で作った重複が門を閉じます。**

    同じ穴で `8/16` と `8/17` にも既に二重予約が入っていました
    （`s-tedori-1` が2本・`s-iryohi-1` が2本。8/16 は10時間後に公開されるところでした）。
    **1回の事故ではなく、予約が溜まるほど確実に増える壊れ方**です。

    ## なぜ search で置き換えないのか

    `search` は取り切れる保証がありません（結果数の上限と、反映の遅れがある）。
    **どちらの口も単独では欠けるので、和を取ります。** 片方が落としたものを
    もう片方が拾い、**両方が落としたときだけ穴が残ります。**
    費用は1回ぶんの追加呼び出しだけです。
    """
    ids: list[str] = []
    seen: set[str] = set()

    def _add(vid: str) -> None:
        if vid and vid not in seen:
            seen.add(vid)
            ids.append(vid)

    token = ""
    while len(ids) < cap:
        response = youtube.playlistItems().list(
            part="contentDetails", playlistId=uploads, maxResults=50,
            pageToken=token or None,
        ).execute()
        for item in response.get("items", []):
            _add(item["contentDetails"]["videoId"])
        token = response.get("nextPageToken", "")
        if not token:
            break

    # **予約中の動画は、こちらにしか出てこないことがある。**
    # 落ちても止めない（プレイリスト側だけで続けるほうが、何も返さないより良い）。
    try:
        token = ""
        while len(ids) < cap:
            response = youtube.search().list(
                part="id", forMine=True, type="video", maxResults=50,
                order="date", pageToken=token or None,
            ).execute()
            for item in response.get("items", []):
                _add(item["id"]["videoId"])
            token = response.get("nextPageToken", "")
            if not token:
                break
    except HttpError as exc:
        print(f"[history] 予約中の動画を search で拾えませんでした（続行）: {exc}")

    return ids


def _scan(want_map: bool):
    youtube = build("youtube", "v3", credentials=credentials(), cache_discovery=False)
    try:
        channels = youtube.channels().list(part="contentDetails", mine=True).execute()
    except HttpError as exc:
        print(f"[history] チャンネルを読めませんでした（全テーマ未使用として続行）: {exc}")
        return {} if want_map else set()

    items = channels.get("items", [])
    if not items:
        return {} if want_map else set()
    uploads = items[0]["contentDetails"]["relatedPlaylists"].get("uploads")
    if not uploads:
        return {} if want_map else set()

    video_ids = channel_video_ids(youtube, uploads)

    found: set[str] = set()
    mapping: dict[str, str] = {}
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i : i + 50]
        response = youtube.videos().list(part="snippet", id=",".join(chunk)).execute()
        for video in response.get("items", []):
            topics = MARKER_RE.findall(video["snippet"].get("description", ""))
            found.update(topics)
            for topic_id in topics:
                # uploads プレイリストは新しい順。**先に見たほうが新しい**ので、
                # 同じテーマを撮り直していたら新しい動画を残す。
                mapping.setdefault(topic_id, video["id"])

    if want_map:
        print(f"[history] チャンネルの動画 {len(video_ids)}本 / テーマ→動画 {len(mapping)}件")
        return mapping
    print(f"[history] チャンネルの動画 {len(video_ids)}本 / 投稿済みテーマ {len(found)}件")
    return found
