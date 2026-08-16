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

    # **こちらも落ちても止めない**（2026-08-17 に足した。**片方だけ守っていた**）。
    #
    # 下の `search` には「落ちても止めない（プレイリスト側だけで続けるほうが、
    # 何も返さないより良い）」と書いてあり、**上のこちらには何もありませんでした。**
    # 同じ節の中に、守る側と素通しの側が並んでいた形です。
    #
    # 2026-08-17 03:5x に実際に踏んでいます —— Data API の1日枠が切れた回で、
    # **2ページ目**（`pageToken=EAAaBlBUOkNESQ`）が 403 で落ち、例外が
    # `posted_topic_ids()` → `pipeline.main` まで上がって**生成ごと死にました。**
    # 1ページ目は通っていたので、**手元には50本ぶんの答えが既にあった**のに、
    # 全部捨てています。
    #
    # これが塞いでいたもの: 日枠が戻るのは JST 16:00 で、それ以前の十数周は
    # **作る段にすら入れません。** `docs/trigger_main.md` §5 は
    # 「作る段は Data API を1単位も使わない」と書いていますが、**使っています。**
    try:
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
    except HttpError as exc:
        print(f"[history] uploads プレイリストを最後まで読めませんでした"
              f"（{len(ids)}本まで／続行）: {str(exc)[:90]}")

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


def ledger_topics() -> dict[str, str]:
    """**手元の控え**から テーマID → 動画ID を返す（`data/uploaded.jsonl`）。

    口が欠けた回の埋め合わせ用です。**API を1単位も使いません。**
    理由は `_scan` の中の註にあります（要約すると、投稿済みが「未投稿」に見えると
    同じ計算のショートをもう一度作ってしまい、それは**収益化の対象外**そのもの）。
    """
    from . import dupes

    return {r["topic"]: r["id"] for r in dupes.ledger_rows() if r.get("topic")}


def _only_ledger(want_map: bool, why: str):
    """口がまったく読めなかった回の答え。**「全テーマ未使用」で返さないこと。**

    ここは長らく `{}` / `set()` を返していました（「全テーマ未使用として続行」）。
    **それは、投稿済みのテーマを全部もう一度作ってよいと言うのと同じ**です。
    控えがあるなら、空より控えのほうが必ず近い。
    """
    try:
        extra = ledger_topics()
    except Exception as exc:                                  # noqa: BLE001
        print(f"[history] {why}／控えも読めませんでした: {str(exc)[:80]}")
        return {} if want_map else set()
    print(f"[history] {why}／**控えの {len(extra)}件だけで続けます**"
          "（口が欠けた回。二重に作らないため）")
    return extra if want_map else set(extra)


def _scan(want_map: bool):
    youtube = build("youtube", "v3", credentials=credentials(), cache_discovery=False)
    try:
        channels = youtube.channels().list(part="contentDetails", mine=True).execute()
    except HttpError as exc:
        return _only_ledger(want_map, f"チャンネルを読めませんでした: {str(exc)[:70]}")

    items = channels.get("items", [])
    if not items:
        return _only_ledger(want_map, "チャンネルが1件も返りませんでした")
    uploads = items[0]["contentDetails"]["relatedPlaylists"].get("uploads")
    if not uploads:
        return _only_ledger(want_map, "uploads プレイリストがありません")

    video_ids = channel_video_ids(youtube, uploads)

    found: set[str] = set()
    mapping: dict[str, str] = {}
    partial = False
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i : i + 50]
        try:
            response = youtube.videos().list(
                part="snippet", id=",".join(chunk)).execute()
        except HttpError as exc:
            # ここも素通しでした（同上）。**取れたところまでで続けます。**
            print(f"[history] 説明欄を最後まで読めませんでした"
                  f"（{i}本まで／続行）: {str(exc)[:90]}")
            partial = True
            break
        for video in response.get("items", []):
            topics = MARKER_RE.findall(video["snippet"].get("description", ""))
            found.update(topics)
            for topic_id in topics:
                # uploads プレイリストは新しい順。**先に見たほうが新しい**ので、
                # 同じテーマを撮り直していたら新しい動画を残す。
                mapping.setdefault(topic_id, video["id"])

    # **欠けた回は、手元の控えで埋める**（2026-08-17）。
    #
    # 上の3か所は「落ちても続行」になりましたが、**続行した先が危ない**のは
    # ここです —— 投稿済みのテーマが「未投稿」に見えると、`batch_build.pick` が
    # 同じ計算・同じ金額のショートをもう一度作ります。それは
    # 「繰り返しのように感じられるコンテンツ」＝**収益化の対象外**そのものです
    # （`channel_video_ids` の「何が起きたか」が、まさにその事故の記録）。
    #
    # 控え（`data/uploaded.jsonl`）は**自分が上げたときに書いた行**なので、
    # 外の口の都合では欠けません。**CLAUDE.md の「ファイルに持たない」は
    # 変えていません** —— 健全な回はこれまでどおりチャンネルから復元し、
    # ここが効くのは**口が欠けた回だけ**です（`src/dupes.py` と同じ切り分け）。
    if partial or not video_ids:
        try:
            extra = ledger_topics()
            new = set(extra) - found
            if new:
                print(f"[history] 控えから {len(new)}件のテーマを足しました"
                      "（口が欠けた回だけ。二重に作らないため）")
            found.update(extra)
            for topic_id, video_id in extra.items():
                mapping.setdefault(topic_id, video_id)
        except Exception as exc:                              # noqa: BLE001
            print(f"[history] 控えを読めませんでした（続行）: {str(exc)[:80]}")

    if want_map:
        print(f"[history] チャンネルの動画 {len(video_ids)}本 / テーマ→動画 {len(mapping)}件")
        return mapping
    print(f"[history] チャンネルの動画 {len(video_ids)}本 / 投稿済みテーマ {len(found)}件")
    return found
