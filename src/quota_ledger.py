"""**API の枠を、何が・いくつ 消費したかの帳面**（`data/api_calls.jsonl`）。

## なぜ要るか（2026-08-31 に踏んだ）

**投稿0本の日に `python -m src.descriptions --refresh` が `quotaExceeded` で
0/735本 でした。** 何が枠を使ったのかを知る手立てが、この repo に
**1つもありませんでした。**

`data/day_quota.jsonl` は帳面の名前をしていますが、書いているのは2つだけです
（`src/upload_cap.note_quota_hit` / `note_quota_ok`）:

    403 に**当たった**とき                    …… 尽きた**後**の記録
    `videos.update` が**通った**とき（`ok`）  …… `reschedule.py` の1経路だけ

**通った読み取りは1行も残りません。** 実測（2026-08-30 と 08-31 の2日ぶん）:
**`ok` の行は 0件**。つまり「何も使っていないのに尽きた」ように見えます。
**見えていないだけです。**

そして単価は同じではありません（YouTube Data API v3 の公表値）:

    list 系            **1**      videos / playlistItems / channels / playlists …
    **search.list**  **100**      ← `src/history._scan` が予約中の本を拾うのに使う
    書き込み          **50**      update / insert / delete / thumbnails.set
    **videos.insert** **1600**

`src/history._scan(cap=400)` は `search.list` を **8ページ**めくります ＝
**800単位／1回**。1日の枠は 10,000 なので、**12回で尽きます。**
`posted_topic_ids()` は `pipeline` と `batch_build` から**1周に何度も**呼ばれます。
**これが「投稿0本の日に枠が消える」の候補の筆頭ですが、
帳面が無いので候補のままです。だから帳面を先に置きます。**

## どこに置くか ——「呼ぶ側で気をつける」にしない

Data API を叩く場所は `src/` と `scripts/` に **30か所以上**あり、
`build("youtube", "v3", …)` がそのつど別に立っています。
**一覧に足す約束は、この輪では毎回どこかが落ちます**
（`upload_cap._write_path` の「**人の記憶と手写しに依存する門は落ちる側**」）。

**全部が通る1点は `googleapiclient.http.HttpRequest.execute` です。**
そこを1回だけ包みます。包むのは `install()` で、呼ぶのは
`src/auth.credentials()` —— **API を叩く側は全員そこを通ります**
（30か所の `build(...)` が例外なく `credentials=credentials()` を渡している）。

**落ちても本体を止めません。** 包みの中は全部 `try` で、
記録に失敗しても API 呼び出しはそのまま通します。

## 何を書くか

    {"at": …, "api": "data"|"analytics"|"other", "method": "search.list",
     "units": 100, "ok": true, "by": "history.py:_scan"}

`units` は**公表の単価**であって、Google が実際に引いた数ではありません
（あちらの実数を読む API はありません）。**符合するかは、尽きた時刻と
この帳面の累計を突き合わせて確かめること。** ずれたら単価表のほうを直します。

## 読み方

    python -m src.quota_ledger           いまの窓の消費を、単価つきで多い順に

## 覆る条件

- Google が単価を変えたら `COST` を直すこと（出典: Data API v3 の Quota calculator）
- `googleapiclient` の内部で `execute` の名前が変わったら `install()` は
  **黙って何もしません**（`installed()` が False を返し続けます）。
  **`python -m src.quota_ledger` の頭がそれを印字します**
- 実測が「`search.list` ではなかった」と言ったら、この docstring の候補を消すこと
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from src import upload_cap

LEDGER = "data/api_calls.jsonl"

#: **公表の単価**（YouTube Data API v3）。鍵は `<資源>.<動作>`。
#: 載っていないものは `_DEFAULT_*` で埋めます（**0 にしないこと** ——
#: 0 で埋めると、知らない呼び出しほど安く見えます）。
COST: dict[str, int] = {
    "videos.insert": 1600,
    "search.list": 100,
    "thumbnails.set": 50,
    "videos.update": 50,
    "videos.delete": 50,
    "videos.rate": 50,
    "playlists.insert": 50,
    "playlists.update": 50,
    "playlists.delete": 50,
    "playlistItems.insert": 50,
    "playlistItems.update": 50,
    "playlistItems.delete": 50,
    "commentThreads.insert": 50,
    "comments.insert": 50,
    "channels.update": 50,
    "channelBanners.insert": 50,
    "captions.insert": 400,
    "captions.update": 450,
    "captions.delete": 50,
}

#: 読み取りの既定（`videos.list` / `playlistItems.list` / `channels.list` …）
_DEFAULT_READ = 1
#: 書き込みの既定（表に無い POST/PUT/PATCH/DELETE）
_DEFAULT_WRITE = 50

#: HTTP の動作 → API の動作
_VERB = {"GET": "list", "POST": "insert", "PUT": "update",
         "PATCH": "update", "DELETE": "delete"}

#: `by` を決めるとき飛ばすファイル（包みの側そのもの）
_SKIP = ("quota_ledger.py", "auth.py")

_installed = False


def installed() -> bool:
    """**包みが実際に掛かったか。**（掛かっていなければ帳面は空のままです）"""
    return _installed


def method_of(uri: str, http_verb: str) -> tuple[str, str]:
    """`(api, method)` を返す。`api` は `data` / `analytics` / `other`。

    `https://youtube.googleapis.com/youtube/v3/videos?part=…` ＋ `GET`
    → `("data", "videos.list")`

    **`analytics` は Data API とは別枠**です（日枠が閉じていても通る）。
    混ぜて数えると、尽きた理由が読めなくなります。
    """
    try:
        parts = urlsplit(str(uri))
    except ValueError:                                         # pragma: no cover
        return "other", "?"
    host, path = parts.netloc, parts.path
    segs = [s for s in path.split("/") if s]
    verb = _VERB.get(str(http_verb or "GET").upper(), "?")
    if "youtubeanalytics" in host or "youtubeAnalytics" in path:
        return "analytics", "reports.query"
    if "youtubereporting" in host:
        return "reporting", (segs[-1] if segs else "?")
    if "youtube/v3" in path:
        # `youtube/v3/videos` / `youtube/v3/thumbnails/set` / `youtube/v3/playlistItems`
        tail = segs[segs.index("v3") + 1:] if "v3" in segs else segs[-1:]
        if not tail:
            return "data", "?"
        if len(tail) >= 2:                       # `thumbnails/set` のような形
            return "data", f"{tail[0]}.{tail[1]}"
        return "data", f"{tail[0]}.{verb}"
    return "other", (segs[-1] if segs else host)


def cost_of(api: str, method: str, http_verb: str = "GET") -> int:
    """**単価**。表に無ければ動作から既定を当てます（0 では埋めません）。"""
    if api != "data":
        return 0                                  # 別枠。日枠の数には足さない
    if method in COST:
        return COST[method]
    return _DEFAULT_READ if str(http_verb or "GET").upper() == "GET" else _DEFAULT_WRITE


def _by() -> str:
    """**この呼び出しを出したのは誰か**（repo の中で最初に見つかるフレーム）。

    `upload_cap.caller_label()` はファイル名の一覧で飛ばしますが、ここは
    `googleapiclient` の中を何段も通ってから来るので、**repo の外を飛ばします。**
    """
    root = str(Path(__file__).resolve().parent.parent)
    try:
        frame: Any = sys._getframe(1)
    except (AttributeError, ValueError):                       # pragma: no cover
        return ""
    for _ in range(40):
        if frame is None:
            break
        name = frame.f_code.co_filename
        base = os.path.basename(name)
        if name.startswith(root) and base not in _SKIP:
            return f"{base}:{frame.f_code.co_name}"[:80]
        frame = frame.f_back
    return ""


def note(api: str, method: str, units: int, ok: bool = True,
         by: str = "", now: datetime | None = None) -> None:
    """1回ぶんを帳面に足す。**検査は本物の帳面に書きません**（`_write_path` の門）。"""
    path = upload_cap._write_path(LEDGER)                      # noqa: SLF001
    if path is None:
        return
    now = now or datetime.now(timezone.utc)
    rec = {"at": now.astimezone(timezone.utc).isoformat(timespec="seconds"),
           "api": api, "method": method, "units": int(units), "ok": bool(ok)}
    if by:
        rec["by"] = by
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:                                            # pragma: no cover
        return


def install() -> bool:
    """`HttpRequest.execute` を1回だけ包む。**掛かったら True。**

    **本体は絶対に止めません** —— 記録の側で何が起きても、
    元の `execute` の返り（と例外）をそのまま通します。
    """
    global _installed                                          # noqa: PLW0603
    if _installed:
        return True
    if os.environ.get("YT_NO_QUOTA_LEDGER"):
        return False
    try:
        from googleapiclient.http import HttpRequest           # noqa: PLC0415
    except Exception:                                          # noqa: BLE001
        return False
    if getattr(HttpRequest.execute, "_quota_ledger", False):
        _installed = True
        return True
    original = HttpRequest.execute

    def execute(self, *args, **kwargs):                        # noqa: ANN001
        api = method = ""
        units = 0
        by = ""
        try:
            api, method = method_of(getattr(self, "uri", ""),
                                    getattr(self, "method", "GET"))
            units = cost_of(api, method, getattr(self, "method", "GET"))
            by = _by()
        except Exception:                                      # noqa: BLE001
            pass
        try:
            out = original(self, *args, **kwargs)
        except Exception:
            try:
                note(api or "other", method or "?", units, ok=False, by=by)
            except Exception:                                  # noqa: BLE001
                pass
            raise
        try:
            note(api or "other", method or "?", units, ok=True, by=by)
        except Exception:                                      # noqa: BLE001
            pass
        return out

    execute._quota_ledger = True                               # noqa: SLF001
    HttpRequest.execute = execute
    _installed = True
    return True


# ---------------------------------------------------------------- 読む側

def rows(now: datetime | None = None) -> list[dict]:
    """**いま効いている枠の中**の行（窓は `upload_cap.window_start/end` と同じ）。"""
    return upload_cap._in_window(LEDGER, now)                  # noqa: SLF001


def spent(now: datetime | None = None) -> dict[str, Any]:
    """いまの窓の消費。`{"data": 単位, "by": {...}, "method": {...}, "n": 件数}`。"""
    out: dict[str, Any] = {"data": 0, "n": 0, "by": {}, "method": {}, "other": 0}
    for r in rows(now):
        units = int(r.get("units") or 0)
        api = str(r.get("api") or "")
        out["n"] += 1
        if api == "data":
            out["data"] += units
        else:
            out["other"] += 1
        key = str(r.get("method") or "?")
        out["method"][key] = out["method"].get(key, 0) + units
        who = str(r.get("by") or "（名前なし）")
        out["by"][who] = out["by"].get(who, 0) + units
    return out


#: 1日の枠（公表値）。**この機械から実数は読めません**（尽きた時刻で確かめること）
DAY_UNITS = 10_000


def render(now: datetime | None = None) -> str:
    """画面に出す本文（**API 0単位**）。"""
    q = upload_cap.day_quota(now)
    s = spent(now)
    head = upload_cap.window_start(now).astimezone(upload_cap.PT)
    lines = [
        "=== Data API の日枠を、何が消費したか（`data/api_calls.jsonl`・API 0単位）===",
        f"  窓の頭: {head:%Y-%m-%d %H:%M} PT ／ 帳面の行: **{s['n']}件**",
        f"  積んだ消費: **{s['data']:,}単位** / 公表の枠 {DAY_UNITS:,}"
        f"（**単価は公表値。Google の実数ではありません**）",
        f"  403 の観測: {getattr(q, 'hits', 0)}回"
        + ("（**尽きています**）" if not getattr(q, "open", True) else ""),
    ]
    if not installed():
        lines.append("  [!] **包みが掛かっていません**（`install()` が False）。"
                     "この回の消費は1行も残りません —— `src/auth.credentials()` が"
                     "呼んでいるか、`YT_NO_QUOTA_LEDGER` が立っていないかを見ること")
    if not s["n"]:
        lines.append("  [!] **この窓の行は 0件です。** 帳面は 2026-08-31 に置いたので、"
                     "**それ以前の窓は空です**（過去に遡っては数えられません）。"
                     "**尽きているのに 0件 なら、枠を使っているのはこの機械の外です**")
        return "\n".join(lines)
    lines.append("  --- 撃った側（多い順）---")
    for who, units in sorted(s["by"].items(), key=lambda kv: -kv[1])[:12]:
        lines.append(f"    {units:>7,}単位  {who}")
    lines.append("  --- 手（多い順）---")
    for m, units in sorted(s["method"].items(), key=lambda kv: -kv[1])[:12]:
        n = sum(1 for r in rows(now) if r.get("method") == m)
        lines.append(f"    {units:>7,}単位  {m}（{n}回・単価 {COST.get(m, '既定')}）")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:  # pragma: no cover - 画面出力だけ
    install()
    print(render())


if __name__ == "__main__":                                     # pragma: no cover
    main()
