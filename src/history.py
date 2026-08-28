"""投稿履歴を YouTube 側から復元する。

ファイルに「投稿済み」を書き溜めると、動画を消したときに嘘になる。
消えた動画のテーマがいつまでも使用済みのままになり、新しいランナーでは空になる。
そこで説明欄に [t:<テーマID>] を埋めておき、毎回チャンネルから読み直す。
状態はチャンネルそのものが持ち、こちらは何も覚えない。
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from . import auth, config
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
        auth.note_day_quota(exc, "playlistItems.list uploads")
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
        auth.note_day_quota(exc, "search.list forMine")
        print(f"[history] 予約中の動画を search で拾えませんでした（続行）: {exc}")

    # **上限に当たった回は、黙って古いほうを捨てています**（2026-08-28 に測って足した）。
    #
    # `cap` は 400 で、uploads プレイリストは**新しい順**です。チャンネルが
    # 400本 を超えた日から、`_scan` は**いちばん古い側を1本も見ていません。**
    # 実測（`data/uploaded.jsonl` の distinct video_id）:
    #
    #     チャンネルの本数            **608本**
    #     `cap=400` で見えない本      **208本**
    #     そのせいで「未投稿」に見えるテーマ  **188件**
    #     400本 を超えた日            **2026-08-19**（＝9日 前から効いていた）
    #
    # **落ちてもいないのに欠ける**ので、`partial` は False のままでした ——
    # 下の「控えで埋める」も、`HttpError` を捕まえる3か所も、**どれも当たりません。**
    # 印字も `チャンネルの動画 400本` で、**満杯なのか丁度なのか区別が付きません。**
    #
    # ここでは**言うだけ**にします（切るのは呼ぶ側の判断）。埋めるのは `_scan` の
    # 末尾で、そちらを**無条件**にしました（同じ回。理由はそこの註）。
    if len(ids) >= cap:
        print(f"[history] [!] **上限 {cap}本 で切りました**（チャンネルはこれより多い）。"
              "**古い側は見えていません** —— 投稿済みの復元は"
              "`_scan` の末尾で控え（`data/uploaded.jsonl`）と和を取ります")

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


#: **チャンネルの読みを、日枠の窓ごとに1回だけにする控え**（2026-08-28）。
#:
#: ## なぜ要るか —— **これが無いと `RESERVE_UNITS` が窓を越えられません**
#:
#: `src/upload_cap.py` は今朝、計測のぶんに **400単位** を残す門を足しました。
#: 残している相手は「**前提を閉じる読み**」で、`eta.py` が毎回
#: 「軌跡の腕が動くのは前提を1件 閉じたときだけ」と言う、その唯一の操作です。
#:
#: **ところが `_scan` 1回は 17単位 です**（`cap=400` のとき ——
#: `channels.list` 1 ＋ `playlistItems.list` 8ページ ＋ `videos.list` 8束。
#: `search.list`（100単位）は `len(ids) >= cap` で回りません）。
#: そして実測 `data/day_quota.jsonl` の窓 08/27 で、`_scan` は
#: **1時間あたり 15回** 呼ばれています（403 の側で数えた ＝ 下限）。
#:
#:     15回/時 × 17単位 ＝ **255単位/時**
#:     残してある 400単位 ÷ 255 ＝ **1.6時間**
#:
#: 窓は 23時間 あります。**残した 400単位 は、窓が開いて 2時間 で消えます。**
#: 今夜の例で言うと: 窓は 08/28 16:00 JST に開き、`config/hypotheses.yaml` の
#: 08-28 の前提が要る読み（`snapshot.py` ＝ **4単位**）は **22:00 JST**。
#: **18:00 には残りがありません。** これで前提が閉じないのは
#: 08/27 夕・08/28 未明に続いて **3回目**になります。
#:
#: ## なぜ控えてよいか
#:
#: `_scan` の答えが窓の途中で変わるのは、**この機械が投稿したとき**だけです
#: （動画を消す道は1本もない ——`docs/FOR_OWNER.md` 済み3）。
#: そして投稿した本は、その場で `data/uploaded.jsonl` に書かれ、
#: `_scan` の末尾で**無条件に和を取ります**（同じ回に直した。上の註）。
#: **だから「窓の頭のチャンネル ∪ いまの控え」は、いま読み直した答えと同じです。**
#:
#: ## `want_map=False`（`posted_topic_ids`）だけに掛けます
#:
#: 写像（`topic_video_map`）は「テーマ→**どの動画**」なので、
#: 撮り直しがあると古い動画IDを返しえます。集合の和は順番を持たないので
#: その問題がありません。**呼ぶ回数が多いのも集合の側**です
#: （`batch_build` / `pipeline` / `preflight` / `bars` / `analytics`。
#: 写像を使うのは `critique_record` だけ）。
#:
#: ## 覆る条件
#:
#: - 動画を消す道ができたら（`videos().delete` か private 落とし）、
#:   控えは「もう無い本」を投稿済みと言い続けます
#: - `_scan` の呼び出しが窓あたり数回まで落ちたら、この控えは要りません
#: - **`YT_NO_SCAN_CACHE=1` で外せます**（外した回は理由を JOURNAL に）
_SCAN_CACHE = "data/scan_topics.json"

#: **この repo の本物の場所**（`config.ROOT` を差し替えても動きません。
#: `src/upload_cap._REPO` と同じ作法）。下の `_scan_cache_path` だけが使います。
_REPO = Path(__file__).resolve().parent.parent

#: 作業コピーをまたいで共有する控えの名前（`.git` の中に置くので、
#: **git に載らず・衝突せず・作業コピー全部から同じ1つが見えます**）。
_SHARED_SCAN_CACHE = "yt-scan-topics.json"

_shared_cache_path: Path | None = None


def _git_common_dir() -> Path | None:
    """この作業コピーが相乗りしている `.git`（＝機械にひとつ）を返す。

    `git` は呼びません（`posted_topic_ids()` は1周に何度も呼ばれます）。
    作業コピーの `.git` は**ファイル**で、中身は
    `gitdir: <共通の .git>/worktrees/<名前>` の1行です。
    本体の作業コピーでは `.git` が**ディレクトリ**で、それがそのまま共通の場所。
    """
    dot = _REPO / ".git"
    try:
        if dot.is_dir():
            return dot
        text = dot.read_text(encoding="utf-8").strip()
    except OSError:                                            # noqa: BLE001
        return None
    if not text.startswith("gitdir:"):
        return None
    here = Path(text.split(":", 1)[1].strip())
    for parent in [here, *here.parents]:                  # …/.git/worktrees/<名前>
        if parent.name == ".git":
            return parent
    return None


def _scan_cache_path() -> Path:
    """控えの置き場。**既定は機械にひとつ**（2026-08-28 に実測して移した）。

    ## なぜ作業コピーごとではいけないか

    この控えを足した回（同じ日の 11:47 JST）は、こう見積もっていました ——
    「`_scan` は 17単位。窓ごとに1回だけ読むので、残してある **400単位** は保つ」。
    **`config.ROOT` は作業コピーの根**です（`Path(__file__).parent.parent`）。
    そして控えは `.gitignore` に入れてあるので、**配られません**（意図どおり ——
    毎周ここで衝突するため）。つまり実際の回数は「窓ごとに1回」ではなく
    **「窓ごと・作業コピーごとに1回」**です。

    実測（2026-08-28 13:1x JST・この機械）:

        作業コピー                        **48個**
        直近24時間に走ったもの（`.git` の mtime）  **30個**
        → 控えが効いても  30 × 17単位 ＝ **510単位**

    **守っている 400単位 より大きい。** 門の大きさは「1つの作業コピー」で
    測られていて、守っている枠は **Google のプロジェクトにひとつ**でした。
    （`src/upload_cap.RESERVE_UNITS` ⑦ と同じ形の外し方です ——
    測った単位と、守っている単位が違う。）

    ## なぜ `.git` の中か

    `.git`（共通のほう）は**全部の作業コピーから同じ1つが見え**、
    **git に載らず**（＝ 配ったときの衝突が起きない）、
    **窓が変われば `_cached_topics` が自分で捨てます**（`window` 違い）。
    足したときの「配りません」という判断は、そのまま生きています ——
    **配るのではなく、1つを見に行く形に変えただけ**です。

    ## 覆る条件

    - `.git` の共通の場所が読めない置かれ方（別の機械で `config.ROOT` だけを
      渡される等）では、**今までどおり作業コピーの中**に落ちます（下の `return`）
    - **検査は今までどおり `config.ROOT` の下に書きます**（`config.ROOT` を
      差し替えた検査は、差し替え先が `_REPO` と違うので自動で当たります）。
      差し替えていない検査が本物の `.git` を汚さないよう、`PYTEST_CURRENT_TEST`
      の側でも作業コピーへ落とします（`upload_cap._write_path` と同じ理屈）
    """
    global _shared_cache_path
    local = config.ROOT / _SCAN_CACHE
    if os.environ.get("YT_SCAN_CACHE_LOCAL"):
        return local
    try:
        if Path(config.ROOT).resolve() != _REPO:
            return local                    # 差し替えられている（検査・別の置かれ方）
    except OSError:                                            # noqa: BLE001
        return local
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return local
    if _shared_cache_path is None:
        common = _git_common_dir()
        _shared_cache_path = (common / _SHARED_SCAN_CACHE) if common else local
    return _shared_cache_path


def _scan_window() -> str:
    """いまの日枠の窓の頭（文字列）。読めなければ空 ＝ 控えを使わない。"""
    try:
        from . import upload_cap

        return upload_cap.window_start().isoformat()
    except Exception:                                          # noqa: BLE001
        return ""


def _cached_topics() -> set[str] | None:
    """この窓のチャンネルの読み。無ければ None。**API 0単位。**"""
    if os.environ.get("YT_NO_SCAN_CACHE"):
        return None
    window = _scan_window()
    if not window:
        return None
    try:
        rec = json.loads(_scan_cache_path().read_text(encoding="utf-8"))
    except Exception:                                          # noqa: BLE001
        return None
    if rec.get("window") != window:
        return None
    topics = rec.get("topics")
    return set(topics) if isinstance(topics, list) else None


def _put_cached_topics(topics: set[str], video_ids: int) -> None:
    """**欠けた回は書かないこと**（呼ぶ側が `partial` を見ています）。"""
    window = _scan_window()
    if not window or os.environ.get("YT_NO_SCAN_CACHE"):
        return
    body = json.dumps({"window": window, "at": datetime.now(timezone.utc).isoformat(),
                       "videos": video_ids, "topics": sorted(topics)},
                      ensure_ascii=False)
    try:
        # **置き換えは一手で**（`os.replace`）。共有の置き場には、並行して走る
        # 作業コピーが同時に書きます。素の `write_text` だと、読む側が
        # 途中の中身を見て `json.loads` で落ちます（落ちても控えを使わないだけ
        # ですが、そのぶん 17単位 が毎回 出ていきます）。
        path = _scan_cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        tmp.write_text(body, encoding="utf-8")
        os.replace(tmp, path)
    except OSError as exc:
        print(f"[history] 読みの控えを書けませんでした（続行）: {str(exc)[:80]}")


def _with_ledger(found: set[str]) -> set[str]:
    """チャンネルの答えに、手元の控えを足す。**足し算だけ**（引かない）。"""
    try:
        extra = ledger_topics()
    except Exception as exc:                                  # noqa: BLE001
        print(f"[history] 控えを読めませんでした（続行）: {str(exc)[:80]}")
        return found
    new = set(extra) - found
    if new:
        print(f"[history] 控えから {len(new)}件のテーマを足しました"
              "（チャンネルの読みと**和**を取ります。二重に作らないため）")
    return found | set(extra)


def _scan(want_map: bool):
    if not want_map:
        cached = _cached_topics()
        if cached is not None:
            out = _with_ledger(cached)
            print(f"[history] この窓のチャンネルの読みを再利用しました"
                  f"（投稿済みテーマ {len(out)}件・**API 0単位**）。"
                  " 窓ごとに1回だけ読みます（`_SCAN_CACHE` の註）。"
                  " 読み直すなら `YT_NO_SCAN_CACHE=1`")
            return out

    youtube = build("youtube", "v3", credentials=credentials(), cache_discovery=False)
    try:
        channels = youtube.channels().list(part="contentDetails", mine=True).execute()
    except HttpError as exc:
        auth.note_day_quota(exc, "channels.list mine")
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
            auth.note_day_quota(exc, "videos.list snippet")
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
    # 外の口の都合では欠けません。
    #
    # ## ここは `if partial or not video_ids:` でした（2026-08-28 に外した）
    #
    # 「効くのは口が欠けた回だけ」と書いてありました。**欠け方を1種類しか
    # 数えていません** —— `partial` が True になるのは `videos.list` が
    # `HttpError` を投げた回だけで、**`channel_video_ids` の `cap=400` で
    # 切られた回は、例外が1つも出ないので False のまま**です。
    #
    # 実測 2026-08-28（`data/uploaded.jsonl`・API 0単位）:
    #
    #     チャンネルの本数                    **608本**
    #     `cap=400` で見えない本              **208本**
    #     「未投稿」に見えるテーマ            **188件**
    #     こうなった日                        **2026-08-19**
    #
    # **9日 間、`posted_topic_ids()` は 188件 を「未投稿」と答えていました。**
    # 静かに壊れる先は3つあり、どれも門に直接 掛かります:
    #
    #   `src/bars.py:_alive()`      `published_charts()` が、見えない 188件 の
    #                               図を「チャンネルから消えた」として落とす
    #                               → **同じ絵を出さない**という守りが、
    #                                 いちばん新しい 400本 としか比べていない。
    #                                 CLAUDE.md の根幹（「同じ絵を続けないこと」）が
    #                                 効かないのは、**収益化の対象外**の側です
    #   `scripts/preflight.py`      「未投稿テーマ N件」が最大 188件 多く出る。
    #                               あそこの註は「**分からないをたくさんあると
    #                               書かないこと**」と書いていますが、
    #                               守っているのは例外の道だけでした
    #   `src/analytics.py:optimize` `unused >= 12` なら題を足さずに帰ります。
    #                               在庫が本当に 0 でも「12件 ある」と見えます
    #                               （実測 08/28 の `src.supply`: 長尺の在庫 **0本**）
    #
    # `scripts/batch_build.py:_posted_including_ledger()` は 2026-08-16 から
    # **まさにこの和**を取っており、そこには「混ぜない費用は実測で生成の 25%」
    # と書いてあります。**同じ事実を2か所が持っていて、片方だけが直っていた**形です
    # （この repo が繰り返している壊れ方）。**こちらへ寄せます。**
    #
    # **CLAUDE.md の「ファイルに持たない」は変えていません** —— 正本はチャンネルで、
    # 控えは**引き算ではなく足し算**にしか使っていません（`update` と `setdefault`）。
    # 控えが嘘になるのは動画を消したときだけで、**消す道が1本もありません**
    # （`docs/FOR_OWNER.md` 済み3。`_posted_including_ledger` の docstring に同じ議論）。
    #
    # **覆る条件**: 動画を消す道ができたら（`videos().delete` か private 落とし）、
    # 控えは「もう無い本」を投稿済みと言い続けます。そのときは
    # `_alive()` の側だけチャンネル単独に戻すこと（`pick` の側は戻さない ——
    # 二重に作るほうが高い）。**`tests/test_history_partial.py` の
    # `test_cap_truncation_is_filled_from_the_ledger` が、外したら落ちます。**
    #
    # **控えるのは、チャンネルから来たぶんだけ**（`found`。和を取る前）。
    # 和のほうを控えると、控えが控えを食べて、チャンネルの答えが
    # どれだったか二度と分からなくなります。
    # **空の読みを控えないこと。** `channel_video_ids` が1本も返さない回は
    # `partial` が立たない（例外が出ていない）ので、そのまま控えると
    # **その窓じゅう、チャンネルを1度も読み直しません。**
    # 控えとの和があるので答えは壊れませんが、**直った瞬間に気づけなくなります。**
    if not partial and video_ids:
        _put_cached_topics(found, len(video_ids))

    found = _with_ledger(found)
    try:
        for topic_id, video_id in ledger_topics().items():
            mapping.setdefault(topic_id, video_id)
    except Exception as exc:                                  # noqa: BLE001
        print(f"[history] 控えを写像に足せませんでした（続行）: {str(exc)[:80]}")

    # **欠けた回かどうかを、印字に出すこと。** 上の `cap` の註のとおり、
    # 「チャンネルの動画 400本」だけでは満杯なのか丁度なのか読めません。
    note = "（説明欄の読みが途中で落ちた回）" if partial else ""
    if want_map:
        print(f"[history] チャンネルの動画 {len(video_ids)}本 "
              f"/ テーマ→動画 {len(mapping)}件{note}")
        return mapping
    print(f"[history] チャンネルの動画 {len(video_ids)}本 "
          f"/ 投稿済みテーマ {len(found)}件{note}")
    return found
