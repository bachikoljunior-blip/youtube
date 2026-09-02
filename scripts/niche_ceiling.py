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


#: **`--source free` の検索フィルタ**（YouTube の `sp=` ＝ protobuf の base64。2026-09-03 に実測）。
#:   `short` : 再生数順 × 動画 × 4分未満（日付なし）      → ショートの帯
#:   `year`  : 再生数順 × 動画 × 今年                      → 長尺の帯（**今年 伸びた本**）
#: 「今年 × 4分未満」の組み合わせは 5本 しか返らなかった（同じ回に実測）ので使いません。
SP_FILTERS = {"short": "CAMSBBABGAE%3D", "year": "CAMSBAgFEAE%3D"}
#: 1語 1フィルタで読む本数（検索結果の1ページ ≈ 20本）。
FREE_PER_QUERY = 30


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
    a = ap.parse_args(argv)
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
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "queries": qs, "days": a.days, "n": len(res["rows"]), "form": a.form,
            "source": a.source,
            "summary": summarize(res["rows"]), "own_ceiling": own_ceiling(),
            "top": top_rows(res["rows"]),
        }, ensure_ascii=False) + "\n")
    if a.thumbs > 0:
        got = fetch_thumbs(top_rows(res["rows"]), keep=a.thumbs,
                           form=None if a.form == "any" else a.form)
        print(f"[niche] 絵 {len(got)}枚 → {THUMBS}（0単位）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
