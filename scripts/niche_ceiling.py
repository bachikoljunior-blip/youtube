#!/usr/bin/env python3
"""**1本あたり再生の天井を、このチャンネルの外で測る。**（2026-09-02・最適化の回）

    python scripts/niche_ceiling.py            # 既定 `--source free`（yt-dlp・**API 0単位**・両方の形）
    python scripts/niche_ceiling.py --source api --form short   # Data API（search.list 100単位/語）
    python scripts/niche_ceiling.py --dry-run  # 撃たずに、何を撃つかだけ出す
    python scripts/niche_ceiling.py --queries 6

## `--source free`（2026-09-03 02:xx JST・最適化の回。**「最適化されてんの？」→ いいえ の理由を1つ潰した**）

この道具は 09/02 に2回 撃たれて、**1回目は長尺 25本／ショート 0本、2回目は 5語 全部 429**
でした。外の数が主実行に届いた回は **0回**。原因は値段です —— `search.list` は 100単位/語 で、
日枠（10,000）はきょうの1本の upload（1,600）と `improve`（50）が先に使うので、
**外を見る手は毎日 最後に回って、毎日 429 で終わっていました**（`data/niche_ceiling.log`）。

**外を見ない限り、天井は鏡のままです**（下の「なぜ要るか」）。だから外を撃つ手は
**日枠の外**に置きます: `yt-dlp` の検索（`https://www.youtube.com/results?search_query=…&sp=…`）
は Data API を通らず、1語 2秒・**0単位**で、再生数・尺・チャンネル・題が返ります
（この回の実測: 「年金 手取り いくら」 ショート帯 19本／最大 36,066回、
**今年の長尺 最大 1,355,670回**）。`kick()` もこちらで起こすので、**毎周 429 で空振りしていた
背景の1手が、毎日 実際に外の数を持って帰ります。**

**覆る条件**: `yt-dlp` の検索が YouTube 側で止められたら（`entries` が連日 0 件）、
`--source api` に戻すこと（`kick()` の `source`）。**その日は 429 の窓を避けて 16:00 JST 直後に**。

## なぜ要るか（**この回に数えて分かったこと**）

`scripts/eta.py` は毎回こう言います ——

> `per_video` は **×4.49 が天井**（実測 4,229）…… 日付が出はじめるのは **×98.16**、
> つまり **天井そのものを ×21.88 上げないと、この腕でも出ません。**
> ＝ この回に立てるべき前提は「**その天井は天井ではない**」

**その 4,229 は、どこから来ているか。** `src/rule_per_video.ceiling_at_rule()` ——
**このチャンネルが出した 600本 の最大（1,891回・NHKylqsNfTw）**を、
公開密度で1段 外挿した数です。**外の数は1つも入っていません。**

**＝ 天井は鏡です。** 自分が作った本の最大を自分の上限と呼んでいるので、
**同じ作り方を続けるかぎり、この天井は原理的に超えられません**
（超えた本が出たときだけ天井が上がる ＝ 定義上いつも「いま届かない」）。

目標の本文はこう言っています ——

> **最短とは、原理的に最大の理論値で、その理論値は空想のものであり、
> つねに発見、達成はできていないものと考えられます。**

**自分の記録は「原理的に最大の理論値」ではありません。** 同じニッチ・同じ形で
**外の誰かが実際に取っている数**のほうが、理論値にずっと近い下限です。
この道具は、それを撃って取ります。

## 何を返すか

同じ帯（日本語・お金／年金／税／住宅ローンの計算）の本を `search.list` で
再生数順に引き、**自分のチャンネルを除いて**、`videos.list` で実数を取ります。
尺で `short`（60秒以下）と `long` に分け、それぞれの **最大・p90・中央値**を返し、
`ceiling_at_rule()` の 4,229 と比べた**倍率**を出します。

    倍率 ≥ 21.88  → **天井は鏡だった。** `eta.py` の「出ません」は形のせいではない
    倍率 < 1      → **ニッチのほうが天井。** 変えるのは本の作り方ではなくニッチ
                    （`CLAUDE.md`「ニッチも尺も形式も頻度もチャンネルも、変えてよい対象です」）

## 覆る条件

- `search.list order=viewCount` は**関連度で絞ったうえでの再生数順**なので、
  帯の真の最大ではなく**下限**です。倍率が小さく出たときに「ニッチの天井だ」と
  読むには、**語を変えて2回以上**撃つこと（`--queries` を増やす）。
- 語が外れていれば帯が違います。`QUERIES` は `data/uploaded.jsonl` の実題から
  採ってあります。**題の傾向が変わったら、ここも変えること。**
- 外の本は**公開からの齢がばらばら**です。`--days` で窓を切っていますが、
  伸びきりの補正はしていません（自分の側の 4,229 は伸びきり補正ずみ）。
  **つまりこの比較は、外の側に不利**（少なく出る）側に倒れています。
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

#: **帯の語**（`data/uploaded.jsonl` の実題から採った。推測ではない）。
QUERIES = [
    "遺族年金 いくら 計算",
    "変動金利 5年ルール 未払利息",
    "再就職手当 計算",
    "不動産取得税 計算",
    "加給年金 いくら",
    "標準報酬月額 計算",
]

#: **ショートの帯の語**（2026-09-02 夜・最適化の回に足した）。
#:
#: 上の `QUERIES` は 09/02 昼に撃って **長尺 25本／ショート 0本** でした ——
#: つまり「天井は鏡か」の判定は、**毎日 出している形（ショート）の外の数を1つも
#: 見ていません**（`src/daily_pick.py`: ショート 48h 中央値 173回 対 長尺 1回）。
#: 語は `data/uploaded.jsonl` のショートで 48時間 1,000回 を超えた題（`kojo` / `nenkin` /
#: `iryohi` / `furusato` / `taishoku` / `kakyu`）から採り、`videoDuration=short` で引きます。
SHORT_QUERIES = [
    "年金 手取り いくら",
    "医療費控除 いくら戻る",
    "ふるさと納税 上限 計算",
    "退職金 税金 いくら",
    "所得税 控除 節税",
    "加給年金 いくら",
]

#: ショートと見なす秒数。YouTube の定義は 2024-10 から **3分以下**です
#: （それまでは 60秒）。09/02 昼の帳面の1件は ≤60秒 で分けています（その日は
#: ショートが 0本 だったので、比べる数は変わりません）。
SHORT_MAX_SECS = 180

#: 帳面に残す「外の上位」の本数（題・再生・尺・チャンネル）。
#: **数だけ残すと、次の回は「何が取れていたか」を撃ち直さないと読めません**（100単位/語）。
TOP_KEEP = 15

LEDGER = ROOT / "data" / "niche_ceiling.jsonl"

#: **帯そのもの**（撃った本を1本残らず）。`LEDGER` の `top` とは別の file です。
#:
#: ## なぜ要るか（2026-09-04 22:4x に測って足した）
#:
#: `[きょうの1本]` の readout は、中身の側に残った**唯一の**手をこう名指しします ——
#: 「**外の帯の上位（`niche_ceiling.py --form long`）と作りが違う点を1つ、次の1本に入れる**」。
#: その手を実際に撃つには「上位」と「残り」を**比べる**必要がありますが、
#: 比べる相手は書き出す所で捨てていました:
#:
#:     撃って測った本      long **334本** / short **131本**（`summary.n`・2026-09-03 の1発）
#:     帳面に残った本      `top_rows()` の **形ごと 15本**
#:     手元に在る実物      long **16本** / short **15本**（重複を除いた実数）
#:
#: **実測（2026-09-04 22:4x・この 16本 で撃った）**: 題に損得の方向語
#: （損・得・失う・増える・上乗せ…）が在る本の中央値 2,265,650回 対 無い本 1,596,753回
#: ＝ **×1.42（n=9 対 7）**。**この n では何も言えません** —— 帯は 334本 測ってあり、
#: そのうち 318本 を、題ごと捨てていました。**捨てているのは「上位と残りの差」そのものです。**
#:
#: 残す代金は 0単位・約 70KB/発（`fill_published` は今までどおり `top` にしか当てないので、
#: `videos.list` の単位も増えません）。**読む側は `corpus_rows()`。**
#:
#: **覆る条件**: この file が読まれないまま 30日 育ったら（`corpus_rows()` の呼び手が
#: `retro._CALL_RE` で 0件のまま）、書くのをやめること。
CORPUS = ROOT / "data" / "niche_corpus.jsonl"

#: `CORPUS` に残す欄。**`top_rows()` と同じ**（読む側が形を覚え直さなくて済む）。
CORPUS_FIELDS = ("id", "views", "secs", "form", "channel", "title", "published", "q")

#: **外の上位の絵**（`https://i.ytimg.com/vi/<id>/hqdefault.jpg`・API 0単位・1枚 約50KB）。
#: 2026-09-03 02:4x の回が「外の帯の上位と**作りが違う点**を1つ、次の1本に入れる」を
#: やろうとして、**題と尺は帳面に在るのに、絵はどこにも無かった**（curl で4枚 取って
#: 初めて型が見えた —— 黄色い箱の題材・赤字に白縁の主語・黄色の結論・人の顔）。
#: `[きょうの1本]` が毎周「作りが違う点」と言う以上、その絵は毎周 手元に在ること。
#: 置き場は git に入れる（`*.jpg` は `.gitignore` の外。控えのサムネと同じ扱い）。
THUMBS = ROOT / "data" / "niche_thumbs"
THUMB_URL = "https://i.ytimg.com/vi/{id}/hqdefault.jpg"
THUMBS_KEEP = 8

#: `scripts/eta.py` の `lever_need_over_cap`（天井をいくつ上げれば日付が出るか）。
#: **この数は動きます。** 判定に使う前に `data/eta.jsonl` の最後の行を見ること。
NEED_OVER_CAP = 21.88


def _iso8601_seconds(text: str) -> int:
    """`PT1M30S` → 90。**尺で short/long を分けるのに要る。**"""
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", text or "")
    if not m:
        return 0
    d, h, mi, s = (int(x) if x else 0 for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def _own_channel(youtube) -> str:
    try:
        r = youtube.channels().list(part="id", mine=True).execute()
        return (r.get("items") or [{}])[0].get("id", "")
    except Exception:                                          # noqa: BLE001
        return ""


def probe(queries: list[str], days: int = 365, per_query: int = 25,
          form: str = "any") -> dict:
    """撃って、外の本の再生数を返す。**`search.list` は1回100単位。**

    `form="short"` は `videoDuration=short`（4分未満）で引きます（既定 `any` は尺で分けるだけ）。
    """
    from googleapiclient.discovery import build

    from src import quota_ledger
    from src.auth import credentials

    try:
        quota_ledger.install()
    except Exception:                                          # noqa: BLE001
        pass
    youtube = build("youtube", "v3", credentials=credentials(), cache_discovery=False)
    own = _own_channel(youtube)

    after = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(
        timespec="seconds").replace("+00:00", "Z")

    ids: dict[str, str] = {}                    # video_id -> 引いた語
    denied = 0                                  # search.list が 429/403 で返った語の数
    for q in queries:
        try:
            kw = {"videoDuration": "short"} if form == "short" else {}
            r = youtube.search().list(
                part="id", q=q, type="video", order="viewCount",
                maxResults=per_query, regionCode="JP", relevanceLanguage="ja",
                publishedAfter=after, **kw).execute()
        except Exception as exc:                               # noqa: BLE001
            msg = str(exc)
            if "429" in msg or "quotaExceeded" in msg or "rateLimitExceeded" in msg:
                denied += 1
                print(f"[niche] search.list 429（{q}）: search の日枠が尽きています", file=sys.stderr)
            else:
                print(f"[niche] search.list 失敗（{q}）: {exc}", file=sys.stderr)
            continue
        for it in r.get("items", []):
            vid = (it.get("id") or {}).get("videoId")
            if vid:
                ids.setdefault(vid, q)

    rows: list[dict] = []
    keys = list(ids)
    for i in range(0, len(keys), 50):
        chunk = keys[i:i + 50]
        try:
            r = youtube.videos().list(
                part="statistics,contentDetails,snippet",
                id=",".join(chunk)).execute()
        except Exception as exc:                               # noqa: BLE001
            print(f"[niche] videos.list 失敗: {exc}", file=sys.stderr)
            continue
        for it in r.get("items", []):
            sn = it.get("snippet", {})
            st = it.get("statistics", {})
            cd = it.get("contentDetails", {})
            ch = sn.get("channelId", "")
            if own and ch == own:
                continue                        # **自分は数えない**（鏡を外すのが目的）
            secs = _iso8601_seconds(cd.get("duration", ""))
            rows.append({
                "id": it.get("id"), "views": int(st.get("viewCount", 0) or 0),
                "secs": secs, "form": "short" if 0 < secs <= SHORT_MAX_SECS else "long",
                "channel": ch, "title": sn.get("title", ""),
                "published": sn.get("publishedAt", ""),
                "q": ids.get(it.get("id"), ""),
            })
    return {"rows": rows, "own": own, "queries": queries, "days": days, "form": form,
            "denied": denied}


#: **`--source free` の検索フィルタ**（YouTube の `sp=` ＝ protobuf の base64）。
#:
#:     `short`       再生数順 × 動画 × 4分未満（**日付の絞りなし ＝ 全期間**） → いまのショートの帯
#:     `year`        再生数順 × 動画 × 今年（**尺の絞りなし**）                 → いまの長尺の帯
#:     `short_year`  再生数順 × 動画 × 今年 × 4分未満                          → **窓を揃えた**ショートの帯
#:
#: ## **形ごとに窓が違います。これが結論を作っていました**（2026-09-04 に測り直した）
#:
#: いまの2つは **ショート＝全期間 ／ 長尺＝今年**で、**別々の窓で測った2つを
#: 横に並べて形を決めています**（`daily_pick.theory_lines`）。公開日を埋めて数えたら、
#: ショートの上位の齢は **中央 1,729日（4.7年）**・長尺は **203日**でした。
#:
#: **ここには「『今年 × 4分未満』の組み合わせは 5本 しか返らなかった」と書いてありました。
#: 撃ち直したら 79本 返りました**（3語・1語あたり 26本・2026-09-04・下の `--windows`）。
#: **前の数がどう出たのかは分かりません**（語が違ったか、その日の応答か）が、
#: **いまは足ります。** 窓を揃えると帯そのものが変わります:
#:
#:     いまの short（全期間 × 4分未満）  n=90  中央 **6,779回**  最大 1,546,432回
#:     今年 × 4分未満                    n=79  中央 **69回**     最大   327,023回   ← **×98 違う**
#:     今月 × 4分未満                    n= 9  中央 3回          （**窓が狭すぎます**）
#:     今週 × 4分未満                    n= 2  （同上）
#:
#: **＝ いまのショートの帯の中央 865回 は、4.7年 積んだ本の累計です。**
#:
#: ## **それでも、窓は揃えません**（同じ回に、この repo の語で撃ち直した）
#:
#: 上の 79本 は**広い3語**（「年金 いくら」「ideco 節税」「ふるさと納税 上限」）で出た数です。
#: **この repo が実際に使う `SHORT_QUERIES` で撃つと 16本 でした**（4語・`--windows --form short`）:
#:
#:     いまの short（全期間 × 4分未満）  n=66  中央 948回
#:     今年 × 4分未満                    n=**16**  中央 204回   ← **30本 の線を割っています**
#:     今月 × 4分未満                    n= 6 ／ 今週 n= 2
#:
#: **＝ 揃えた窓では、この帯の標本が足りません。** 中央値が 16本 で決まる帯から
#: 形の結論を出すのは、いま直したばかりの誤り（窓の差が結論を作る）と同じ形です。
#: **だから既定は替えず、`daily_pick.theory_lines` の「1日あたり」の行のほうで読みます**
#: （そちらは齢で割るので、窓が違っても比べられます）。
#:
#: **覆る条件**: `--windows --form short` の「今年 × 4分未満」が **30本 以上**になったら
#: （語を増やす・`SHORT_QUERIES` を広げる・その帯が育つ）、
#: `probe_free()` の `filters` を `["short_year"] if form == "short" else ["year"]` にして
#: 窓を揃えること。**そのとき `daily_pick` の「理論値の在りか」は総取っ替えになります**
#: （ショートの中央 865回 → 200回 台）ので、同じ回に他の画面を替えないこと。
SP_FILTERS = {"short": "CAMSBBABGAE%3D", "year": "CAMSBAgFEAE%3D",
              "short_year": "CAMSBggFEAEYAQ%3D%3D"}
#: 1語 1フィルタで読む本数（検索結果の1ページ ≈ 20本）。
FREE_PER_QUERY = 30


def sp_param(upload_date: int | None, duration: int | None, sort_by: int = 3) -> str:
    """`sp=` を組む（**撃ちません**・純関数）。`SP_FILTERS` の値はこれで作れます。

        SearchParams { int32 sort_by = 1; SearchFilter filter = 2; }
        SearchFilter { int32 upload_date = 1; int32 type = 2; int32 duration = 3; }
          upload_date 1=1時間 2=今日 3=今週 4=今月 5=今年
          type        1=動画      duration 1=4分未満 2=20分超 3=4〜20分
          sort_by     0=関連 1=評価 2=新着 3=再生数

    **手で base64 を書き写さないこと** —— `SP_FILTERS` の3つは、この関数の返りと
    一致するかを `tests/test_niche_windows.py` が見ます。
    """
    import base64                                              # noqa: PLC0415
    import urllib.parse                                        # noqa: PLC0415
    f = b""
    if upload_date:
        f += bytes([0x08, upload_date])
    f += bytes([0x10, 0x01])                                   # type = 動画
    if duration:
        f += bytes([0x18, duration])
    raw = bytes([0x08, sort_by]) + bytes([0x12, len(f)]) + f
    return urllib.parse.quote(base64.b64encode(raw).decode(), safe="")


def window_counts(queries: list[str], cases: list[tuple[str, int | None, int | None]] | None = None,
                  per_query: int = 30) -> list[dict]:
    """**窓ごとに、何本 返って中央がいくつかを数える**（yt-dlp・**API 0単位**）。

    形ごとに違う窓（`SP_FILTERS` の註）を揃えられるかは、**撃たないと分かりません** ——
    09/03 の註は「今年 × 4分未満 は 5本」でしたが、09/04 に撃ち直すと **79本**でした。
    **写した数で決めないこと。この関数を撃つこと。**
    """
    import urllib.parse                                        # noqa: PLC0415
    try:
        import yt_dlp                                          # noqa: PLC0415
    except Exception as exc:                                   # noqa: BLE001
        print(f"[niche] yt-dlp が無い: {exc}", file=sys.stderr)
        return []
    cases = cases or [("いまの short（全期間 × 4分未満）", None, 1),
                      ("今年 × 4分未満", 5, 1),
                      ("今月 × 4分未満", 4, 1),
                      ("今週 × 4分未満", 3, 1),
                      ("いまの year（今年・尺なし）", 5, None)]
    opts = {"quiet": True, "extract_flat": True, "skip_download": True,
            "playlistend": per_query, "no_warnings": True}
    out: list[dict] = []
    for label, ud, dur in cases:
        views: list[int] = []
        n = 0
        for q in queries:
            url = ("https://www.youtube.com/results?search_query="
                   + urllib.parse.quote(q) + "&sp=" + sp_param(ud, dur))
            try:
                with yt_dlp.YoutubeDL(opts) as y:
                    info = y.extract_info(url, download=False)
                ents = (info or {}).get("entries") or []
            except Exception as exc:                           # noqa: BLE001
                print(f"[niche] [!] {q}: {str(exc)[:100]}", file=sys.stderr)
                ents = []
            n += len(ents)
            views += [int(e.get("view_count") or 0) for e in ents]
        views.sort()
        out.append({"label": label, "sp": sp_param(ud, dur), "n": n,
                    "median": (views[len(views) // 2] if views else 0),
                    "max": (views[-1] if views else 0)})
    return out


def _own_video_ids() -> set[str]:
    """自分の本の ID（`data/uploaded.jsonl`）。**外の数に自分を混ぜないため**（チャンネル ID は
    Data API 1単位なので、0単位のこちらは ID で外す）。"""
    out: set[str] = set()
    try:
        with (ROOT / "data" / "uploaded.jsonl").open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    v = json.loads(line).get("video_id")
                except Exception:                              # noqa: BLE001
                    continue
                if v:
                    out.add(str(v))
    except OSError:
        pass
    return out


def free_rows(entries: list[dict], q: str, own_ids: set[str] | None = None) -> list[dict]:
    """yt-dlp の flat な `entries` を、`probe()` と同じ行の形に（純関数・撃たない）。"""
    own_ids = own_ids or set()
    rows: list[dict] = []
    for e in entries or []:
        vid = str(e.get("id") or "")
        if not vid or vid in own_ids:
            continue
        secs = int(e.get("duration") or 0)
        rows.append({
            "id": vid, "views": int(e.get("view_count") or 0), "secs": secs,
            "form": "short" if 0 < secs <= SHORT_MAX_SECS else "long",
            "channel": str(e.get("channel_id") or e.get("channel") or ""),
            "title": str(e.get("title") or ""), "published": "", "q": q,
        })
    return rows


def probe_free(queries: list[str], days: int = 365, per_query: int = FREE_PER_QUERY,
               form: str = "any") -> dict:
    """**Data API を通らずに**（yt-dlp・0単位）外の本の再生数を返す。返りは `probe()` と同じ形。

    `form="short"` は `short` のフィルタだけ、`any` は `short` と `year` の両方を撃ちます
    （長尺の帯は「今年 伸びた本」で読む —— 日付なしの再生数順は 5年前の本が上に来る）。
    `days` は帳面に書き残すだけです（`year` フィルタ ＝ 今年 1月から）。
    """
    import urllib.parse

    try:
        import yt_dlp
    except Exception as exc:                                   # noqa: BLE001
        print(f"[niche] yt-dlp が無い（`pip install yt-dlp`）: {exc}", file=sys.stderr)
        return {"rows": [], "own": "", "queries": queries, "days": days, "form": form,
                "denied": len(queries), "source": "free"}
    own_ids = _own_video_ids()
    filters = ["short"] if form == "short" else ["year", "short"]
    opts = {"quiet": True, "extract_flat": True, "skip_download": True,
            "playlistend": per_query, "no_warnings": True}
    seen: dict[str, dict] = {}
    denied = 0
    for q in queries:
        got_any = False
        for f in filters:
            url = ("https://www.youtube.com/results?search_query="
                   + urllib.parse.quote(q) + "&sp=" + SP_FILTERS[f])
            try:
                with yt_dlp.YoutubeDL(opts) as y:
                    info = y.extract_info(url, download=False)
                ents = (info or {}).get("entries") or []
            except Exception as exc:                           # noqa: BLE001
                print(f"[niche] yt-dlp 検索 失敗（{q}／{f}）: {str(exc)[:120]}", file=sys.stderr)
                ents = []
            for r in free_rows(list(ents), q, own_ids):
                got_any = True
                if r["id"] not in seen or seen[r["id"]]["views"] < r["views"]:
                    seen[r["id"]] = r
        if not got_any:
            denied += 1
    return {"rows": list(seen.values()), "own": "", "queries": queries, "days": days,
            "form": form, "denied": denied, "source": "free"}


#: `search.list` の日枠（"Search Queries per day"）が戻る時刻。**Data API の日枠と同じ
#: 太平洋時間 0:00 ＝ 16:00 JST（夏時間）**。`src/upload_cap.day_quota()` の窓と同じ。
SEARCH_RESET_JST = "16:00 JST"


def denied_lines(res: dict) -> list[str]:
    """**全語 429 の回に出す行。帳面には書きません**（0本 は「帯が無い」ではなく「撃てていない」）。

    2026-09-02 23:1x に踏んだ: 5語とも 429 で、`render()` が「**帯そのものが天井です。
    ニッチを変えること**」と印字し、帳面に n=0 の1件が**書かれました**。
    `eta_line()` は best=0 で黙るので画面には出ませんが、`latest()` の答えは
    その嘘の1件になっていました。**撃てていない回は、帳面に触らないこと。**
    """
    return [
        f"[!] **{res.get('denied', 0)}語 全部が 429 ＝ `search.list` の日枠が尽きています。"
        f"0本 は「帯が無い」ではなく「撃てていない」です。** 帳面には書きません。",
        f"    戻るのは {SEARCH_RESET_JST}（`Search Queries per day`・Data API の日枠と同じ窓）。"
        f" そのあとに同じコマンドを撃ち直すこと。",
    ]


def top_rows(rows: list[dict], keep: int = TOP_KEEP) -> list[dict]:
    """帳面に残す上位（**題つき・形ごとに `keep` 本**）。

    2026-09-03: 形を分けずに 15本 だと、今年の長尺（100万回）が全部を占めて
    ショートの題が1本も残らず、`top_lines("short")` が空になる。形ごとに残す。
    """
    out: list[dict] = []
    for form in ("short", "long"):
        top = sorted((r for r in rows if r.get("form") == form),
                     key=lambda r: -int(r.get("views") or 0))[:keep]
        out.extend({k: r.get(k) for k in ("id", "views", "secs", "form", "channel", "title",
                                          "published", "q")} for r in top)
    return out


def corpus_write(rows: list[dict], at: str, *, path: Path | None = None) -> int:
    """撃った本を**1本残らず** `CORPUS` へ足す。**API 0単位。**足した行数を返す。

    `top_rows()` が形ごと 15本 しか残さないので、「上位と残りの差」を後から
    測れませんでした（`CORPUS` の註に実測）。ここは**測った全部**を残します。

    重複は**この file の中では取りません** —— 同じ本が別の日に別の再生数で
    入るのは、その本の伸びの記録です。読む側（`corpus_rows()`）が畳みます。
    """
    p = path or CORPUS
    keep = [r for r in rows if r.get("id")]
    if not keep:
        return 0
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        for r in keep:
            fh.write(json.dumps({"at": at, **{k: r.get(k) for k in CORPUS_FIELDS}},
                                ensure_ascii=False) + "\n")
    return len(keep)


def corpus_rows(form: str | None = None, *, path: Path | None = None) -> list[dict]:
    """`CORPUS` の本を**1本1行**で返す（**撃ちません・API 0単位**）。

    同じ `id` が何度も入っていたら、**いちばん新しい `at` の行**を残します
    （再生は増える一方なので、古い行で中央値を出すと帯が実物より低く出ます）。
    `form` を渡すとその形だけ。

    **この関数が、上の readout の「上位と作りが違う点」を測る所です。**
    `top` （形ごと 15本）で測らないこと —— 上位どうしを比べても差は出ません。
    """
    p = path or CORPUS
    best: dict[str, dict] = {}
    try:
        with p.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                vid = str(r.get("id") or "")
                if not vid or (form and r.get("form") != form):
                    continue
                prev = best.get(vid)
                if prev is None or str(r.get("at") or "") >= str(prev.get("at") or ""):
                    best[vid] = r
    except OSError:
        return []
    return sorted(best.values(), key=lambda r: -int(r.get("views") or 0))


def corpus_published_cover(*, path: Path | None = None) -> dict:
    """帯の `published` の被覆（**撃ちません・API 0単位**）。形ごとに `{有り, 全体}`。

    **この数を見ないと、下の `corpus_fill_published` が要るかどうかが分かりません。**
    """
    out: dict[str, dict] = {}
    for r in corpus_rows(path=path):
        form = str(r.get("form") or "?")
        d = out.setdefault(form, {"have": 0, "all": 0})
        d["all"] += 1
        if r.get("published"):
            d["have"] += 1
    return out


def corpus_fill_published(*, path: Path | None = None, fetch_many=None,
                          limit: int = 0) -> dict:
    """`CORPUS` の空の `published` を埋める（**`videos.list` 50本で 1単位**）。

    ## なぜ要るか（2026-09-04 22:5x に撃って数えた）

    `fill_published()` は **帳面に残す 形ごと 15本 だけ**を埋めます
    （「読まれない行に単位を使わないこと」）。その註は **`CORPUS` が無かった頃**の
    ものです。いまは `corpus_rows()` が帯の全部（長尺 337本）を読み、
    readout が唯一 名指しする中身の手（「外の上位と**作りが違う点**を1つ入れる」）は
    そこで測られます。**その帯の `published` は 337本中 16本（4.7%）しか入っていません。**

    **齢で割らないと、この帯の数は読めません。** 同じ帯で同じ語を当てて測った実測:

        語            生涯の累計（n=337）   1日あたり（n=16）
        相手の名指し      ×40.15              **×0.79**
        場面            ×17.97              **×0.82**
        括弧見出し        ×19.88              **×0.95**
        煽り            ×8.08               **×1.36**
        疑問形          ×0.62                ×0.71

    **累計で ×40 に見えるものが、齢で割ると ×0.79 —— 符号ごと裏返ります。**
    累計の大きい本は「古い本」でもあるので、当たり前です
    （readout 自身が「その数は**生涯の累計**です（1日あたりに直すと別の話になります）」
    と毎周 印字しています）。**それでも 1日あたりの側は n=16 で、何も言えません。**
    ＝ **どちらが正しいかを決められないのは、`published` が 4.7% しか無いからです。**

    ## 値段

    `videos.list` は id を 50本 まで並べて **1回 1単位**。帯 467本 なら **10単位**
    （1本の `--move` が 50単位。**帯を丸ごと齢で割れるようにする値段が、予約の1/5です**）。

    ## 何をするか

    行は**足しません**（`corpus_write` の「同じ本が別の日に別の再生数で入るのは
    その本の伸びの記録」を壊さない）。**同じ行の `published` の空だけ**を埋めて
    書き戻します。返りは `{"asked": 引きに行った本数, "filled": 埋まった本数,
    "lines": 書き換えた行数, "units": 使った単位}`。

    **覆る条件**: 引けなければ `filled` 0 で、file は1文字も変わりません。
    """
    p = path or CORPUS
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {"asked": 0, "filled": 0, "lines": 0, "units": 0}
    need: list[str] = []
    seen: set[str] = set()
    for ln in lines:
        if not ln.strip():
            continue
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        vid = str(r.get("id") or "")
        if vid and not r.get("published") and vid not in seen:
            seen.add(vid)
            need.append(vid)
    if limit > 0:
        need = need[:limit]
    if not need:
        return {"asked": 0, "filled": 0, "lines": 0, "units": 0}
    getter = fetch_many or _fetch_upload_dates
    got = getter(need) or {}
    if not got:
        return {"asked": len(need), "filled": 0, "lines": 0,
                "units": (len(need) + 49) // 50}
    changed = 0
    for i, ln in enumerate(lines):
        if not ln.strip():
            continue
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        vid = str(r.get("id") or "")
        val = got.get(vid) or ""
        if not val or r.get("published"):
            continue
        r["published"] = val
        lines[i] = json.dumps(r, ensure_ascii=False)
        changed += 1
    if changed:
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"asked": len(need), "filled": len(got), "lines": changed,
            "units": (len(need) + 49) // 50}


def summarize(rows: list[dict]) -> dict:
    out: dict[str, dict] = {}
    for form in ("short", "long"):
        vals = sorted(r["views"] for r in rows if r["form"] == form)
        if not vals:
            out[form] = {"n": 0}
            continue
        out[form] = {
            "n": len(vals), "max": vals[-1],
            "p90": vals[int(0.9 * (len(vals) - 1))],
            "median": int(statistics.median(vals)),
            "channels": len({r["channel"] for r in rows if r["form"] == form}),
        }
    return out


def own_ceiling() -> float | None:
    """`src/rule_per_video.ceiling_at_rule()` の値（**比べる相手**）。"""
    try:
        from src import rule_per_video
        c = rule_per_video.ceiling_at_rule()
        return float(c.get("value")) if c else None
    except Exception:                                          # noqa: BLE001
        return None


def verdict(best: float, own: float, need: float = NEED_OVER_CAP) -> tuple[str, str]:
    """**外の最大と自分の天井から、次の手を1つに決める。**（純関数・撃たない）

    返り `(code, line)`。`code` は `mirror` / `niche_short` / `niche_wall`。
    """
    ratio = (best / own) if own else 0.0
    if ratio >= need:
        return "mirror", (
            f"[!] **外の最大は自分の天井の ×{ratio:.1f} で、要る ×{need:.2f} を超えています。**"
            f" ＝ **{own:,.0f}回 は帯の天井ではなく、この作り方の天井です。**"
            " `eta.py` の「出ません」は、形ではなく**作り方**のせい ——"
            " 次の手は `improve`（1本の作り方を変える）です")
    if ratio >= 1.0:
        return "niche_short", (
            f"[!] **外の最大は自分の天井の ×{ratio:.1f}。要る ×{need:.2f} には届きません。**"
            " ＝ 作り方で天井を上げても足りない。**帯（ニッチ）を変える手が要ります**"
            "（`CLAUDE.md`「ニッチも尺も形式も頻度もチャンネルも、変えてよい対象です」）")
    return "niche_wall", (
        f"[!] **外の最大でも自分の天井の ×{ratio:.1f} —— 帯そのものが天井です。**"
        " **本の作り方をいくら直しても届きません。ニッチを変えること。**")


def _rows(path: Path | None = None) -> list[dict]:
    p = path or LEDGER
    out: list[dict] = []
    try:
        with p.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:                              # noqa: BLE001
                    continue
    except FileNotFoundError:
        return []
    return out


def _get_bytes(url: str, timeout: int = 20) -> bytes:
    """1枚 取る（proxy は環境変数のまま。`urllib` が落ちたら `curl` へ倒れる）。"""
    try:
        import urllib.request                                  # noqa: PLC0415
        with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310
            return r.read()
    except Exception:                                          # noqa: BLE001
        import subprocess                                      # noqa: PLC0415
        cp = subprocess.run(["curl", "-sS", "--max-time", str(timeout), url],
                            capture_output=True, check=False)
        return cp.stdout if cp.returncode == 0 else b""


def thumb_path(video_id: str, root: Path | None = None) -> Path:
    return (root or THUMBS) / f"{video_id}.jpg"


def fetch_thumbs(rows: list[dict], *, keep: int = THUMBS_KEEP, form: str | None = None,
                 root: Path | None = None, fetch=None) -> list[Path]:
    """**外の上位の絵を `data/niche_thumbs/<id>.jpg` に落とす**（API 0単位・在るものは撃たない）。

    `rows` は帳面の `top`（`top_rows()` の形）。形ごとに再生の多い順 `keep` 枚。
    `fetch` は検査の差し替え口（`url -> bytes`）。返り: 手元に在る（新旧とも）道の一覧。

    **覆る条件**: `i.ytimg.com` が proxy の外なら 0枚 で黙って返る（`[!]` を1行 出す）。
    """
    root = root or THUMBS
    fetch = fetch or _get_bytes
    forms = [form] if form else ["short", "long"]
    got: list[Path] = []
    for f in forms:
        top = sorted((r for r in rows if r.get("form") == f and r.get("id")),
                     key=lambda r: -int(r.get("views") or 0))[:keep]
        for r in top:
            dst = thumb_path(str(r["id"]), root)
            if dst.exists() and dst.stat().st_size > 0:
                got.append(dst)
                continue
            try:
                data = fetch(THUMB_URL.format(id=r["id"]))
            except Exception:                                  # noqa: BLE001
                data = b""
            if not data:
                print(f"[niche] [!] 絵が取れませんでした: {r['id']}（{THUMB_URL.format(id=r['id'])}）")
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
            got.append(dst)
    return got



OPENING_SECS = 90


def opening_path(video_id: str, root: Path | None = None) -> Path:
    return (root or THUMBS) / f"{video_id}.opening.txt"


def vtt_to_text(vtt: str, upto: float = OPENING_SECS) -> str:
    """自動字幕（vtt）の先頭 `upto` 秒ぶんを、重複を落として1本の文字列に（純関数）。"""
    import re                                                  # noqa: PLC0415
    out: list[str] = []
    seen: set[str] = set()
    for blk in vtt.split("\n\n"):
        m = re.search(r"(\d+):(\d+):(\d+)\.(\d+) --> ", blk)
        if not m:
            continue
        t = int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3])
        if t > upto:
            break
        for line in blk.split("\n")[1:]:
            line = re.sub(r"<[^>]+>", "", line).strip()
            if line and line not in seen and not line.startswith("align"):
                seen.add(line)
                out.append(line)
    return "".join(out)


def _fetch_vtt(video_id: str, timeout: int = 120) -> str:
    """yt-dlp で自動字幕（ja）だけ落として文字列で返す（動画は落とさない・API 0単位）。"""
    import subprocess                                          # noqa: PLC0415
    import tempfile                                            # noqa: PLC0415
    with tempfile.TemporaryDirectory() as td:
        cp = subprocess.run(
            ["yt-dlp", "--skip-download", "--write-auto-sub", "--sub-lang", "ja",
             "--sub-format", "vtt", "-o", str(Path(td) / "cap"),
             f"https://www.youtube.com/watch?v={video_id}"],
            capture_output=True, text=True, timeout=timeout, check=False)
        for f in Path(td).glob("cap*.vtt"):
            return f.read_text(encoding="utf-8", errors="replace")
        if cp.returncode != 0:
            print(f"[niche] [!] 字幕が取れませんでした: {video_id}（{(cp.stderr or '')[-160:]}）")
    return ""


def fetch_openings(rows: list[dict], *, keep: int = THUMBS_KEEP, form: str = "long",
                   root: Path | None = None, fetch=None, secs: float = OPENING_SECS) -> list[Path]:
    """**外の上位の長尺の「冒頭 90秒 に何を言っているか」を `data/niche_thumbs/<id>.opening.txt` に落とす**
    （yt-dlp の自動字幕・API 0単位・在るものは撃たない）。

    ## なぜ要るか（2026-09-03 05:xx・最適化の回）

    「外の作り方を写した長尺」（`config/hypotheses.yaml`）は、外の上位の**題・尺・絵**を写した。
    **冒頭 90秒 の話し方は写していなかった** —— 写す材料が手元に無かったから。
    実際に落として並べると（`J6i7L0QSRSQ` 5.0M・`D9BI69GFWvs` 4.4M・`mL0bwzi8KFM` 3.3M・`YRFTmhCp4Fk` 2.9M）、
    4本とも同じ順で入っている:

        1文目   結論か損の額を1文で（「2026年から年収516万円でも非課税世帯になれるようになったんです」）
        2文目   「この改正を知らないと皆さん損します」＝ 知らない側の損
        次      「こんにちは。〇〇です」＝ 名乗り → 「今回は…について解説します」
        次      視聴者への問い 2〜3回（「〜と感じませんか？」「〜ではないでしょうか？」「ご存知でしょうか？」）
        次      「今日の動画を最後まで見れば…」＝ 見続ける約束 → 「それでは本題へ」＋ 目次

    自分の 09/04 の本（`6PKux5HNnUE`）の冒頭 4コマは 名乗り 0・問い 0・約束 0・「皆さん／あなた」0 で、
    3人称の解説から始まっていた。長尺は 15〜30% で去る（`daily_pick` の中央カーブ）ので、
    **写していない所のうち、いちばん先に見られる所がここ**。写す材料を毎周 手元に置く。

    **覆る条件**: yt-dlp の字幕が取れなくなったら（`[!]` が続く）この口は黙って空を返す。
    `script_writer.outside_opening_problems` が読むのは**型**（上の5つ）で、この文面ではない。
    """
    root = root or THUMBS
    fetch = fetch or _fetch_vtt
    top = sorted((r for r in rows if r.get("form") == form and r.get("id")),
                 key=lambda r: -int(r.get("views") or 0))[:keep]
    got: list[Path] = []
    for r in top:
        dst = opening_path(str(r["id"]), root)
        if dst.exists() and dst.stat().st_size > 0:
            got.append(dst)
            continue
        try:
            text = vtt_to_text(fetch(str(r["id"])) or "", upto=secs)
        except Exception:                                      # noqa: BLE001
            text = ""
        if not text:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(f"# {r.get('title') or ''}\n# {int(r.get('views') or 0)}回・{int(r.get('secs') or 0)}秒・"
                       f"先頭 {int(secs)}秒 の自動字幕（yt-dlp・0単位）\n{text}\n", encoding="utf-8")
        got.append(dst)
    return got


def _fetch_upload_date(video_id: str, timeout: int = 60) -> str:
    """1本の公開日を `YYYYMMDD` で返す（yt-dlp・**API 0単位**）。**いまは通りません** ——
    2026-09-04 の実測で、1本ずつの取り出しは
    「Sign in to confirm you're not a bot」で断られます（検索の flat な取り出しは通る）。
    `_fetch_upload_dates` が落ちたときの控えとして残してあります。"""
    import subprocess                                          # noqa: PLC0415
    try:
        cp = subprocess.run(
            ["yt-dlp", "--skip-download", "--no-warnings", "--print", "%(upload_date)s",
             f"https://www.youtube.com/watch?v={video_id}"],
            capture_output=True, text=True, timeout=timeout, check=False)
    except Exception:                                          # noqa: BLE001
        return ""
    out = (cp.stdout or "").strip().splitlines()
    val = out[-1].strip() if out else ""
    return val if (len(val) == 8 and val.isdigit()) else ""


def _fetch_upload_dates(ids: list[str]) -> dict[str, str]:
    """公開日をまとめて引く（`videos.list`・**50本で 1単位**）。返りは `{id: publishedAt}`。

    **1本ずつの yt-dlp より、こちらのほうが安いです。** `videos.list` は
    `id` をカンマで 50本 まで並べられて **1回 1単位**なので、帳面へ入る 30本 は **1単位**。
    0単位ではありませんが、1本ずつ数秒 待つ道より速く、いまは**そちらが通りません**
    （bot 判定・`_fetch_upload_date` の註）。
    """
    if not ids:
        return {}
    from googleapiclient.discovery import build                # noqa: PLC0415

    from src import quota_ledger                               # noqa: PLC0415
    from src.auth import credentials                           # noqa: PLC0415
    try:
        quota_ledger.install()
    except Exception:                                          # noqa: BLE001
        pass
    out: dict[str, str] = {}
    try:
        youtube = build("youtube", "v3", credentials=credentials(), cache_discovery=False)
    except Exception as exc:                                   # noqa: BLE001
        print(f"[niche] 公開日が引けません（認証）: {str(exc)[:120]}", file=sys.stderr)
        return {}
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        try:
            r = youtube.videos().list(part="snippet", id=",".join(chunk)).execute()
        except Exception as exc:                               # noqa: BLE001
            print(f"[niche] videos.list 失敗（公開日）: {str(exc)[:160]}", file=sys.stderr)
            continue
        for it in r.get("items", []):
            at = (it.get("snippet") or {}).get("publishedAt") or ""
            if it.get("id") and at:
                out[str(it["id"])] = str(at)
    return out


def fill_published(rows: list[dict], *, fetch=None, fetch_many=None,
                   limit: int = 2 * TOP_KEEP) -> int:
    """**帳面に残す行だけ**、空の `published` を埋める。返りは埋めた本数。

    ## なぜ要るか（2026-09-04・申し送りが3周 運んでいた）

    `data/niche_ceiling.jsonl` の `top[].published` は **`--source free` の側だけ空**でした
    （`free_rows()`）。API 側（`videos.list`）は `publishedAt` を保存ずみです。
    yt-dlp の **flat な `entries` に日付が無い**のが原因で、撃ち方の問題ではありません
    （2026-09-04 に実測 —— 返る欄は `timestamp` / `release_timestamp` とも **全部 None**）。

    日付が無いと、**外の上位が「いつ出た本か」が読めません。** これが要るのは1つの問いのためです ——
    **「外の上位は、初動で取っているのか、何年もかけて積んだのか」。**
    この repo の形の判定（ショート／長尺）は **48時間 で 100回** の門ひとつに乗っており、
    その門は**外の帯の数**と並べて読まれます。**外の数が生涯の累計なら、並びません。**

    ## 何で引くか

    既定は **`videos.list`（50本で 1単位）**。1本ずつの yt-dlp は、いま
    「Sign in to confirm you're not a bot」で断られます（`_fetch_upload_date` の註）。
    `fetch`（1本ずつ）を渡せばそちらを使います —— 検査と、API が使えない回のため。

    ## なぜ「帳面に残す行だけ」か

    拾った行は 130〜330本 ありますが、帳面へ入るのは `top_rows()` の
    **形ごと 15本 ＝ 最大 30本**。**読まれない行に単位を使わないこと。**

    **覆る条件**: 日付が引けなければ、この関数は黙って 0 を返します
    （空のままなので、前と同じ状態に戻るだけ）。
    """
    todo = [r for r in rows[:max(0, limit)] if not r.get("published") and r.get("id")]
    if not todo:
        return 0
    if fetch is None and fetch_many is None:
        fetch_many = _fetch_upload_dates
    n = 0
    if fetch_many is not None:
        got = fetch_many([str(r["id"]) for r in todo]) or {}
        for r in todo:
            val = got.get(str(r["id"])) or ""
            if val:
                r["published"] = val
                n += 1
        return n
    for r in todo:
        val = fetch(str(r["id"]))
        if val:
            r["published"] = val
            n += 1
    return n


def backfill_published(rows_back: int, path: Path | None = None) -> int:
    """帳面の**新しいほうから `rows_back` 件**の `top[].published` の空を埋め直す。

    `--source free` で撃った過去の行は `published` が空です（`fill_published` の註）。
    撃ち直すと**別の帯**（検索結果は毎日 変わる）になってしまうので、
    **同じ行のまま**日付だけ入れます。**行の並びは変えません。**
    """
    p = path or LEDGER
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError:
        print("[niche] 帳面が読めません")
        return 2
    idxs = [i for i, ln in enumerate(lines) if ln.strip()][-max(1, rows_back):]
    total = 0
    for i in idxs:
        try:
            row = json.loads(lines[i])
        except Exception:                                      # noqa: BLE001
            continue
        top = row.get("top") or []
        got = fill_published(top, limit=len(top))
        if not got:
            continue
        row["top"] = top
        lines[i] = json.dumps(row, ensure_ascii=False)
        total += got
        print(f"[niche] {str(row.get('at'))[:16]} の行: {got}本 埋めました")
    if total:
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[niche] 公開日を 合計 {total}本 埋めました（`videos.list` 50本で 1単位）")
    return 0


def latest(path: Path | None = None, form: str | None = None) -> dict | None:
    """**帳面の最後の1件**（`data/niche_ceiling.jsonl`）。**撃ちません・API 0単位。**

    `scripts/eta.py` が毎回これを読みます —— **撃った数が主実行に届く口**です。
    `form="short"` なら、**その形が 1本以上 拾えた**最後の1件（ショート 0本 の
    昼の1件は飛ばす）。
    """
    rows = _rows(path)
    if form:
        rows = [r for r in rows if ((r.get("summary") or {}).get(form) or {}).get("n")]
    return rows[-1] if rows else None


def age_days(row: dict, now: datetime | None = None) -> float | None:
    """1本の齢（日）。`published` が空／読めなければ `None`。**撃ちません。**"""
    at = str(row.get("published") or "")
    if not at:
        return None
    try:
        d = datetime.fromisoformat(at.replace("Z", "+00:00"))
    except Exception:                                          # noqa: BLE001
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    secs = ((now or datetime.now(timezone.utc)) - d).total_seconds()
    return secs / 86400.0 if secs > 0 else None


def per_day_lines(row: dict, form: str, *, own_median_48h: float | None = None,
                  now: datetime | None = None) -> list[str]:
    """**外の帯を「1日あたり」で読み直す行**（API 0単位）。

    ## なぜ要るか（2026-09-04 に、公開日を埋めて初めて見えた）

    上の行（`top_lines`）が出している「外の帯 ÷ 自分」は、
    **外の生涯の累計 ÷ 自分の 48時間**です。公開日を埋めて数えたら、
    外の上位に **48時間 以内の本は 1本もありません**でした:

        長尺    齢 中央 **203日** ／ 最小 128日
        ショート  齢 中央 **1,729日（4.7年）** ／ 最小 274日

    しかも `SP_FILTERS` は**形ごとに窓が違います**（ショートは日付なし ＝ 全期間、
    長尺は `year` ＝ 今年）。**別々の窓で測った2つを、横に並べて形を決めていました。**

    1日あたりに直すと向きが変わります —— 自分のショートの中央値 1,049回/48h
    （＝ 約 525回/日）は、**外のショートの上位（14〜186回/日）より上**で、
    外の長尺（6,000〜29,000回/日）より下。**「外の帯が上」は、形によっては齢の産物です。**

    **これは「累計を見るな」ではありません。** 累計は「その題でどこまで積めるか」を
    言っていて、それはそれで要る数です。**並べて読むこと** ——
    片方だけだと、**窓の差が結論を作ります**（`daily_pick` の門の註と同じ形）。

    **覆る条件**: `published` の埋まっている本が 3本 未満なら、1行も出しません
    （中央値が1本で決まる帯から、形の結論を出さないこと）。
    """
    top = [r for r in (row.get("top") or []) if r.get("form") == form]
    pairs = []
    for r in top:
        a = age_days(r, now)
        v = int(r.get("views") or 0)
        if a and v > 0:
            pairs.append((a, v))
    if len(pairs) < 3:
        return []
    ages = sorted(a for a, _ in pairs)
    rates = sorted(v / a for a, v in pairs)
    med_age = ages[len(ages) // 2]
    med_rate = rates[len(rates) // 2]
    hi_rate = rates[-1]
    fresh = sum(1 for a in ages if a <= 2)
    label = "ショート" if form == "short" else "長尺"
    win = "全期間（日付の絞りなし）" if form == "short" else "今年（`year`）"
    out = [f"     ↑ その数は**生涯の累計**です（1日あたりに直すと別の話になります・"
           f"`niche_ceiling.per_day_lines`・n={len(pairs)}本）:"
           f" 齢 中央 **{med_age:,.0f}日**／最小 {ages[0]:,.0f}日・"
           f"**48時間 以内に出た本 {fresh}本**"
           f" → 1日あたり 中央 **{med_rate:,.0f}回/日**・最大 {hi_rate:,.0f}回/日"
           f"（撃った窓は {win}）"]
    if own_median_48h:
        mine = own_median_48h / 2.0
        shown = f"{mine:,.1f}" if mine < 10 else f"{mine:,.0f}"
        out.append(f"       自分の{label}は 48時間 中央値 {own_median_48h:,.0f}回 ＝ "
                   f"**{shown}回/日** → 外の中央の **×{med_rate / mine:,.2f}**・"
                   f"最大の ×{hi_rate / mine:.1f}。"
                   f"**上の『×N』は累計どうしではありません** —— "
                   f"形を決めるときは、この行と上の行の両方を見ること")
    return out


def top_lines(form: str = "short", path: Path | None = None,
              now: datetime | None = None, own_median: float | None = None,
              need: float | None = None) -> list[str]:
    """**`src/daily_pick.lines()` の `[きょうの1本]` に出す、外の帯の同じ形の数。**（API 0単位）

    ## なぜ要るか（2026-09-02 夜・最適化の回）

    `[きょうの1本]` は 09/02 夜から「形と族を、いまの数で決める」画面ですが、
    並ぶ数は**全部 自分の控え**（族の中央値は n=2〜6）でした。同じ日の昼に外を撃った
    帳面は `eta.py` の1行にしか届かず、しかも**長尺 25本／ショート 0本** ——
    毎日 出している形の外の数は、主実行のどの画面にも無かった。

    ここは、帳面に残した**外の上位の題**をそのまま並べます。族の中央値（n=4）より、
    **外で実際に取れている題**のほうが、次の1本の題材を決める根拠として強い。

    **覆る条件**: 帳面が空／その形が 0本／30日超なら 1行も出しません。
    """
    row = latest(path, form=form)
    if not row:
        return []
    try:
        d = ((now or datetime.now(timezone.utc))
             - datetime.fromisoformat(str(row["at"]))).days
    except Exception:                                          # noqa: BLE001
        d = 0
    if d > 30:
        return []
    s = (row.get("summary") or {}).get(form) or {}
    label = "ショート" if form == "short" else "長尺"
    ln = (f"     外の帯の{label}（`scripts/niche_ceiling.py`・{d}日前・"
          f"{len(row.get('queries') or [])}語・n={s.get('n', 0)}／{s.get('channels', 0)}ch）: "
          f"最大 **{int(s.get('max', 0)):,}回** ／ p90 {int(s.get('p90', 0)):,}回 ／ "
          f"中央 {int(s.get('median', 0)):,}回")
    if own_median:
        ln += (f"　← 自分の{label}の中央値 {own_median:,.0f}回 の "
               f"**中央で ×{(s.get('median') or 0) / own_median:.1f}・"
               f"最大で ×{(s.get('max') or 0) / own_median:.1f}**")
    if need:
        ln += f"（日付が出るのは ×{need:.1f}）"
    out = [ln]
    top = [r for r in (row.get("top") or []) if r.get("form") == form][:5]
    if top:
        out.append(f"       外で取れている題（上位{len(top)}・**題材を決める根拠はこちらのほうが強い**"
                   "。族の中央値は n=2〜6）:")
        have = 0
        for r in top:
            has = thumb_path(str(r.get("id") or "")).exists()
            have += int(has)
            out.append(f"         {int(r.get('views') or 0):>10,}回  {int(r.get('secs') or 0):>3}s  "
                       f"{str(r.get('title') or '')[:46]}"
                       f"{'  絵 `data/niche_thumbs/' + str(r.get('id')) + '.jpg`' if has else ''}")
        # **作りが違う点は、題と尺だけでは見えません**（2026-09-03 02:4x の回が curl で4枚
        # 取って初めて「黄色い箱・赤字に白縁・人の顔」が見えた）。絵の在りかをここに出す。
        if have < len(top):
            out.append(f"       絵が手元に無い本 {len(top) - have}本 —— "
                       "`python scripts/niche_ceiling.py --thumbs-only`（API 0単位・`i.ytimg.com`）"
                       "で `data/niche_thumbs/<id>.jpg` に落ちます。**題と尺だけで「作りが違う点」を決めないこと**")
        else:
            out.append("       絵は全部 `data/niche_thumbs/<id>.jpg` に在ります（`Read` で見ること・API 0単位）")
    # **累計と1日あたりを、必ず並べて出すこと**（`per_day_lines` の註・2026-09-04）。
    #     上の「×N」は 外の生涯の累計 ÷ 自分の 48時間 で、外の上位に 48時間 以内の本は
    #     1本もありません（長尺 齢 中央 203日／ショート 1,729日）。
    out += per_day_lines(row, form, own_median_48h=own_median, now=now)
    return out


def eta_line(need_over_cap: float | None = None, path: Path | None = None,
             now: datetime | None = None) -> str | None:
    """**`eta.py` の「天井そのものを ×N 上げないと」の直後に出す1行。**

    ## なぜ要るか（2026-09-02・最適化の回）

    `eta.py` はずっと「**この回に立てるべき前提は『その天井は天井ではない』**」
    と書いていました。**書いてあるだけで、確かめる口がありませんでした** ——
    天井 4,229 は `ceiling_at_rule()` ＝ **自分の記録**から作った数で、
    「天井ではない」と言うための**外の数**がどこにも無かったからです。

    この行は、`niche_ceiling.py` が実際に撃って取った**外の最大**を、
    要る倍率（`lever_need_over_cap`）と**同じ画面**に並べます。
    **並ばないかぎり、撃った数は主実行に届きません。**

    **覆る条件**: 帳面が空／古い（30日超）なら `None` を返して1行も出しません
    —— **出ない行は、読む側の手順を増やしません。**
    """
    row = latest(path)
    if not row:
        return None
    own = row.get("own_ceiling")
    s = row.get("summary") or {}
    best = max((int((s.get(f) or {}).get("max", 0) or 0) for f in ("short", "long")),
               default=0)
    if not own or not best:
        return None
    age = ""
    try:
        at = datetime.fromisoformat(str(row["at"]))
        d = ((now or datetime.now(timezone.utc)) - at).days
        if d > 30:
            return None
        age = f"{d}日前"
    except Exception:                                          # noqa: BLE001
        pass
    need = need_over_cap if isinstance(need_over_cap, (int, float)) and need_over_cap \
        else NEED_OVER_CAP
    code, line = verdict(best, own, need)
    forms = " ／ ".join(
        f"{'ショート' if f == 'short' else '長尺'} 最大 {int(d['max']):,}回（n={d['n']}）"
        for f, d in s.items() if (d or {}).get("n"))
    return (f"   {line} —— **外の実測**（`scripts/niche_ceiling.py`・{age}）: {forms}。"
            f" 自分の天井 {own:,.0f}回 は `ceiling_at_rule()` ＝ **自分の記録**から作った数です。"
            " **取り直す手**: `python scripts/niche_ceiling.py`"
            "（`search.list` 100単位/語。**日枠が尽きていたら 429 で 0本**）")


#: `kick()` の印と log。印が `KICK_EVERY` の内なら二度 起こさない。
KICK_MARK = ROOT / "data" / "niche_ceiling.kick"
KICK_LOG = ROOT / "data" / "niche_ceiling.log"
KICK_EVERY = timedelta(hours=6)
#: 帳面のその形が、これより若ければ撃ち直さない。**0単位（`--source free`）になったので 1日**
#: （API 版のときは 7日 ＝ 500単位/週。外の帯は日ごとに動くので、毎日 取り直す）。
KICK_FRESH = timedelta(days=1)


def kick(form: str = "short", now: datetime | None = None, *, root: Path | None = None,
         mark: Path | None = None, ledger: Path | None = None,
         every: timedelta | None = None, fresh: timedelta | None = None,
         spawn=None) -> str:
    """**毎日 出している形（ショート）の外の数を、回の意思と関係なく撃つ。** 返りは1行の理由。

    ## なぜ要るか（2026-09-02 深夜・最適化の回）

    `[きょうの1本]` は「撃つこと: `niche_ceiling.py --form short`」と印字しますが、
    **この repo で印字された手は、選ばれなければ撃たれません**（09/01 の実測: fix 82%・
    印字された `reschedule --pool` は毎朝 出て 0回）。`ahead_sweep.kick()` と同じ形で、
    **実際に毎周 撃たれる口（`run_marker.py --write`）から背景で起こします。**

    起こす条件（3つとも）:
      - 帳面にその形が **`KICK_FRESH`（7日）より若い件が無い**
      - 印 `KICK_MARK` が **`KICK_EVERY`（6時間）より古い**（429 の窓で毎周 撃たない）
      - 台本生成の子プロセスではない

    429 の回は帳面に書かず 2 で終わるので（`denied_lines()`）、印だけが進み、
    次の窓（16:00 JST 以降）の周で撃ち直します。**成功すれば 7日 黙ります**（500単位/週）。

    **覆る条件**: `search.list` の日枠が毎周 尽きているなら（`data/api_calls.jsonl` の
    429 が連日）、`KICK_EVERY` を 24時間 にして 16:00 JST 直後に寄せること。
    """
    import os
    import subprocess

    now = now or datetime.now(timezone.utc)
    root = Path(root or ROOT)
    mark = Path(mark or KICK_MARK)
    every = KICK_EVERY if every is None else every
    fresh = KICK_FRESH if fresh is None else fresh
    if os.environ.get("YOUTUBE_PIPELINE_CHILD"):
        return "台本生成の子プロセスなので起こしません"
    row = latest(ledger, form=form)
    if row:
        try:
            age = now - datetime.fromisoformat(str(row["at"]))
            if age < fresh:
                return f"帳面に {form} が {age.days}日前 の件で在ります（{fresh.days}日 は撃ち直しません）"
        except Exception:                                      # noqa: BLE001
            pass
    try:
        raw = mark.read_text(encoding="utf-8").strip()
        at = datetime.fromisoformat(raw) if raw else None
        if at is not None and now - at < every:
            return f"{(now - at).total_seconds() / 60:.0f}分 前に起こしてあります（`{mark.name}`）"
    except (OSError, ValueError):
        pass
    try:
        mark.parent.mkdir(parents=True, exist_ok=True)
        mark.write_text(now.isoformat() + "\n", encoding="utf-8")
        # 2026-09-03: `--source free`（yt-dlp・0単位）で**両方の形**を撃つ。API 版は 09/02 に
        # 2回とも 429 で、背景の1手は一度も帳面を進めていなかった（`data/niche_ceiling.log`）。
        cmd = [sys.executable or "python3", "scripts/niche_ceiling.py", "--source", "free",
               "--form", "any", "--queries", "6"]
        if spawn is not None:
            spawn(cmd)
        else:
            log = open(root / KICK_LOG.name if root != ROOT else KICK_LOG, "ab")   # noqa: SIM115
            log.write(f"\n=== {now.isoformat(timespec='seconds')} {' '.join(cmd[1:])}\n".encode())
            subprocess.Popen(cmd, cwd=str(root), stdout=log, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, start_new_session=True)
    except Exception as exc:                                   # noqa: BLE001
        return f"起こせませんでした: {str(exc)[:120]}"
    return f"背景で起こしました（`--source free --form any --queries 6`・0単位・log は `data/{KICK_LOG.name}`）"


def render(res: dict) -> list[str]:
    rows = res["rows"]
    s = summarize(rows)
    own = own_ceiling()
    L = ["=== 帯の天井を、チャンネルの外で測る（`search.list`・外の本だけ）===",
         f"  語 {len(res['queries'])}件 ／ 窓 {res['days']}日 ／ 拾えた外の本 **{len(rows)}本**"]
    if own:
        L.append(f"  自分の天井（`ceiling_at_rule()`）: **{own:,.0f}回**"
                 "　← これは**自分の記録**から作った数です")
    for form, label in (("short", "ショート"), ("long", "長尺")):
        d = s.get(form) or {"n": 0}
        if not d["n"]:
            L.append(f"  {label}: 拾えませんでした（語か窓を変えること）")
            continue
        line = (f"  {label}: n={d['n']}本／{d['channels']}チャンネル　"
                f"最大 **{d['max']:,}回** ／ p90 {d['p90']:,}回 ／ 中央 {d['median']:,}回")
        if own:
            line += (f"　→ 自分の天井の **×{d['max'] / own:.1f}**"
                     f"（p90 で ×{d['p90'] / own:.1f}）")
        L.append(line)
    if own:
        best = max((s[f].get("max", 0) for f in ("short", "long")), default=0)
        L.append("  " + verdict(best, own)[1])
    top = sorted(rows, key=lambda r: -r["views"])[:8]
    if top:
        L.append("  外の上位8本（**この帯で実際に取れている数**）:")
        for r in top:
            L.append(f"    {r['views']:>9,}回  {r['form']:<5} {r['title'][:44]}")
    return L


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queries", type=int, default=4)
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--form", choices=("any", "short"), default="any",
                    help="short: `videoDuration=short` と SHORT_QUERIES で、毎日 出している形の外を撃つ")
    ap.add_argument("--source", choices=("free", "api"), default="free",
                    help="free: yt-dlp の検索（0単位・既定）／ api: Data API の search.list（100単位/語）")
    ap.add_argument("--thumbs", type=int, default=THUMBS_KEEP,
                    help=f"撃った後に、形ごと上位 N枚 の絵を data/niche_thumbs/ に落とす（0単位・既定 {THUMBS_KEEP}・0 で落とさない）")
    ap.add_argument("--thumbs-only", action="store_true",
                    help="撃たずに、帳面の最後の1件の上位の絵だけ落とす（0単位）")
    ap.add_argument("--openings", type=int, default=4,
                    help="撃った後に、長尺の上位 N本 の冒頭 90秒（自動字幕）を data/niche_thumbs/<id>.opening.txt に落とす（0単位・既定 4）")
    ap.add_argument("--openings-only", action="store_true",
                    help="撃たずに、帳面の最後の1件の長尺の上位の冒頭だけ落とす（0単位・yt-dlp）")
    ap.add_argument("--windows", action="store_true",
                    help="窓ごとに何本 返って中央がいくつかを数えるだけ（yt-dlp・0単位）。"
                         "形ごとに違う窓（`SP_FILTERS` の註）を揃えられるかは、これで見ること")
    ap.add_argument("--backfill-published", type=int, default=0, metavar="N",
                    help="撃たずに、帳面の**新しいほうから N件**の `top[].published` の空を埋め直す"
                         "（`videos.list` 50本で 1単位。`--source free` で撃った過去の行のため）")
    ap.add_argument("--fill-corpus-published", action="store_true",
                    help="撃たずに、帯（`data/niche_corpus.jsonl`）の空の `published` を埋める"
                         "（`videos.list` 50本で 1単位）。**齢で割った数は、これが無いと n=16 です**")
    a = ap.parse_args(argv)
    if a.fill_corpus_published:
        before = corpus_published_cover()
        for form, d in sorted(before.items()):
            print(f"[niche] 前: {form:6s} published {d['have']}/{d['all']}"
                  f"（{100.0 * d['have'] / max(1, d['all']):.1f}%）")
        res = corpus_fill_published()
        print(f"[niche] {res['asked']}本 引きに行って {res['filled']}本 埋まりました"
              f"（{res['lines']}行 書き換え・約 {res['units']}単位）")
        for form, d in sorted(corpus_published_cover().items()):
            print(f"[niche] 後: {form:6s} published {d['have']}/{d['all']}"
                  f"（{100.0 * d['have'] / max(1, d['all']):.1f}%）")
        return 0
    if a.windows:
        qs = (SHORT_QUERIES if a.form == "short" else QUERIES)[:max(1, a.queries)]
        print(f"[niche] 窓を数えます（{len(qs)}語・yt-dlp・0単位）")
        for r in window_counts(qs):
            print(f"    {r['label']:32s} sp={r['sp']:24s} n={r['n']:4d} "
                  f"中央 {r['median']:>9,}回 ／ 最大 {r['max']:>10,}回")
        print("    → **揃えた窓（今年 × 4分未満）で n が 30本 を割ったら、窓は揃えないこと**"
              "（`SP_FILTERS` の註の「覆る条件」）")
        return 0
    if a.backfill_published > 0:
        return backfill_published(a.backfill_published)
    if a.openings_only:
        row = latest(form=None)
        if not row:
            print("[niche] 帳面が空です（先に撃つこと）")
            return 2
        got = fetch_openings(row.get("top") or [], keep=max(0, a.openings))
        print(f"[niche] 冒頭 {len(got)}本 が手元に在ります: {THUMBS}")
        for pth in got:
            print(f"    {pth.name}")
        return 0
    if a.thumbs_only:
        row = latest(form=None if a.form == "any" else a.form)
        if not row:
            print("[niche] 帳面が空です（先に撃つこと）")
            return 2
        got = fetch_thumbs(row.get("top") or [], keep=max(0, a.thumbs),
                           form=None if a.form == "any" else a.form)
        print(f"[niche] 絵 {len(got)}枚 が手元に在ります: {THUMBS}")
        for pth in got:
            print(f"    {pth.name}")
        return 0
    if a.source == "free" and a.form == "any":
        # 0単位なので、ショートの語と長尺の語を**両方**撃つ（形ごとの帯が同じ帳面に入る）。
        qs = SHORT_QUERIES[:max(1, a.queries)] + QUERIES[:max(1, a.queries)]
    else:
        qs = (SHORT_QUERIES if a.form == "short" else QUERIES)[:max(1, a.queries)]
    if a.dry_run:
        if a.source == "free":
            print(f"[niche] 撃つ語 {len(qs)}件（{a.form}・yt-dlp・0単位）")
        else:
            print(f"[niche] 撃つ語 {len(qs)}件（{a.form}）＝ search.list {len(qs)}回 ＝ {100 * len(qs)}単位")
        for q in qs:
            print("   ", q)
        return 0
    res = (probe_free if a.source == "free" else probe)(qs, days=a.days, form=a.form)
    if not res["rows"] and res.get("denied"):
        for line in denied_lines(res):
            print(line)
        return 2
    for line in render(res):
        print(line)
    # **帳面へ入る行にだけ公開日を入れる**（`fill_published` の註・`videos.list` 1単位）。
    #     `--source free` は flat な `entries` から作るので `published` が空のまま入り、
    #     「外の上位は初動で取ったのか、何年もかけて積んだのか」が読めませんでした。
    top = top_rows(res["rows"])
    filled = fill_published(top)
    if filled:
        print(f"[niche] 公開日を {filled}本 埋めました（`videos.list` 50本で 1単位）")
    at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "at": at,
            "queries": qs, "days": a.days, "n": len(res["rows"]), "form": a.form,
            "source": a.source,
            "summary": summarize(res["rows"]), "own_ceiling": own_ceiling(),
            "top": top,
        }, ensure_ascii=False) + "\n")
    # **帯そのものを残す**（`CORPUS` の註・**API 0単位**）。`top` は形ごと 15本 なので、
    # 「上位と残りで作りがどう違うか」は `top` からは測れません。
    wrote = corpus_write(res["rows"], at)
    print(f"[niche] 帯を {wrote}本 残しました → {CORPUS.name}（0単位・読む側は `corpus_rows()`）")
    if a.thumbs > 0:
        got = fetch_thumbs(top, keep=a.thumbs,
                           form=None if a.form == "any" else a.form)
        print(f"[niche] 絵 {len(got)}枚 → {THUMBS}（0単位）")
    if a.openings > 0 and a.form == "any":
        got = fetch_openings(top, keep=a.openings)
        print(f"[niche] 長尺の冒頭 {len(got)}本 → {THUMBS}（0単位・yt-dlp の字幕）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
