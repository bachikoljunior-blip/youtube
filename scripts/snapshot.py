#!/usr/bin/env python3
"""公開済み動画の再生数を、公開からの経過時間つきで1行ずつ残す。

なぜ要るか。**「いつ伸びたか」を一度も記録していなかった。**

2026-08-06、m74wgCTi2n0 が 1245（公開12時間後）→ 1257（24時間後）で止まった。
バーストが一度きりなのは分かったが、**FSAN9tjIX10 が同じ形かを比べる基準が無い。**
公開13分後の0回が良いのか悪いのかも判断できない。総再生数だけ見ていると、
**当たり外れが決まる最初の数時間が丸ごと抜ける。**

律速は「1本あたりの当たり率」なので、そこが見えないのは致命的。
`status.py` から毎回自動で呼ぶ。人が思い出す前提にしない。
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

LOG = Path(__file__).resolve().parent.parent / "data" / "views.jsonl"

#: **本物の当て先**（`LOG` を差し替えた検査と見分けるために、別名で持つ）。
_LOG_REAL = LOG


def _log_blocked() -> bool:
    """**検査からは、本物の `data/views.jsonl` に書かない・API も撃たない**
    （2026-09-13 17:0x JST・optimizer・Opus が踏んで足した。
    `run_marker._marks_blocked()` / `next_round.log_wake()` と**同じ理由・同じ形**）。

    **実測（この回に踏んだ）**: `python -m pytest tests/test_status_blind_path.py` を撃つだけで、
    本物の `data/views.jsonl` に **526行**（2026-09-13T07:55:30Z と 07:55:37Z に **263行 ずつ**）
    入り、`videos.list` を **12単位 × 2回** 使いました。

    **経路**（`status.py` の中を通る ＝ `snapshot.py` を名指しで撃った回は 1度もありません）:
    `test_main_は例外を握って手元の節を出す` と `test_日枠が落ちた回でも_Analytics_の節を出す` は
    `status._service` を動画の無い偽の口へ差し替え、`status.main()` を**例外の枝へ落として**
    「手元の節を出すこと」を見ています。ところが `status.main()` のその枝は
    **`import snapshot as _snap; _snap.main()`**（2026-08-31 に足した「θ の計器だけ取りに行く」）を撃つので、
    **落とした先で本物の API と本物の控えに届いていました。**
    ＝ **検査が差し替えたのは「落ちる所」で、「落ちた先」ではありません。**

    **値段は 2つ**（§8 06:5x の 4例目は副作用だけ・こちらは**両方**）:
    1. **`videos.list` 12単位／1件**。日枠 10,000単位/日 は 16:00 JST に戻るので、
       枯れた窓に当たると本が出せません。
    2. **`data/views.jsonl` は「凍結した下敷き」**（`scripts/zero_start.py` の前提・
       検査 `tests/test_zero_start.py::test_実物の下敷き_旧データは凍結なので数は動かない`）。
       行が入ると **§1 の下敷きが黙って動きます** —— この回の実測で
       B群の最大が **275 → 382回**・初点の並びも変わり、**その検査が赤になりました**
       （＝ 親が毎周 撃つ `scripts/checks.py` が赤で戻り、次の回が別の欠陥を探しに行きます）。

    **守りは「呼ぶ側」ではなく「書く側」に置くこと**（§8 09/09 09:5x の決め）——
    呼ぶ側（`status.main()` の枝・各検査の `monkeypatch`）で 1つずつ塞ぐ形は、
    枝が増えるたびに漏れます。**書く直前に「いま向いている先が本物か」を見る。**

    **差し替えた検査は書いてよい**（`LOG` が tmp を向いていれば通す ——
    そこを止めると、この控えを読む検査そのものが書けなくなる）。

    **覆る条件**: (1) `status.py` の「θ の計器だけ取りに行く」枝が消えたら、
    この門は `record()` 側だけで足ります（`main()` 側は外してよい）。
    (2) 検査以外の所から `snapshot.main()` を撃つ手順が METHOD に書かれたら、
    そのときは `PYTEST_CURRENT_TEST` ではなく**呼ぶ側の名**で見分けること。
    (3) 旧道具の `status.py` を撃つ口が repo から全部 消えたら、この門は外してよい。
    """
    return bool(os.environ.get("PYTEST_CURRENT_TEST")) and LOG == _LOG_REAL


def record(videos: list[dict]) -> int:
    """公開済み動画の現在値を追記する。追記した本数を返す。"""
    if _log_blocked():
        return 0                                   # **検査からは書かない**（`_log_blocked` の註）
    LOG.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    rows = []
    for v in videos:
        if v["status"]["privacyStatus"] != "public":
            continue
        published = datetime.fromisoformat(v["snippet"]["publishedAt"].replace("Z", "+00:00"))
        rows.append({
            "at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "id": v["id"],
            "hours": round((now - published).total_seconds() / 3600, 2),
            "views": int(v["statistics"].get("viewCount", 0)),
            "likes": int(v["statistics"].get("likeCount", 0)),
        })
    with LOG.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(rows)


def history(video_id: str) -> list[dict]:
    """1本の時系列を古い順に返す。"""
    if not LOG.exists():
        return []
    out = []
    for line in LOG.read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("id") == video_id:
            out.append(d)
    return sorted(out, key=lambda d: d["hours"])


def print_curves(ids: list[str], titles: dict[str, str]) -> None:
    """公開から48時間以内の動画について、伸び方を並べる。

    **横に並べないと比べられない。** 1本ずつ見ていると「多いか少ないか」の
    感覚だけが残り、前の1本と比較できない。
    """
    rows = [(i, history(i)) for i in ids]
    rows = [(i, h) for i, h in rows if h and h[-1]["hours"] <= 48]
    if not rows:
        return
    print("\n=== 公開後の伸び方（48時間以内）===")
    for vid, h in sorted(rows, key=lambda r: r[1][-1]["hours"]):
        点 = "  ".join(f"{d['hours']:.0f}h:{d['views']}" for d in h[-6:])
        print(f"  {titles.get(vid, vid)[:26]:28s} {点}")


# --- **単体で撃てるようにする**（2026-08-27 に足した） ----------------------
#
# `config/hypotheses.yaml` の `needs[].refresh` は **`python scripts/snapshot.py`**
# と書いてありました（`scripts/deadline_check.py` が「判定できない前提」に対して
# **そのまま印字する**行です）。**このファイルには `__main__` がありませんでした** ——
# 撃っても**黙って何もせず終了コード0**を返し、次の回はもう1度
# 「読みが足りない」を見ます。**手順が名指ししている道具が、無いのと同じ**でした。
#
# `scripts/status.py` は同じことをしていますが、あれは Analytics も棚卸しも回すので
# **40〜60秒**かかります。ここは `videos.list` だけで、
# **571本 なら 12組 ＝ 12単位**（日枠は10,000単位）。
#
# **切り分けの日（`src/day_cap.booked_split_day()`）を読むのに要るのはこれだけ**です ——
# その日の最後の本が 齢 `MIN_AGE_H`（6時間）を過ぎた後に1回 撃てば、
# `day_cap.window()` が (A)/(B) を決めます。
def _ids_from_ledger() -> list[str]:
    """`data/uploaded.jsonl` の video_id（**Data API 0単位**）。**新しい本から順**。

    ## なぜ新しい順か（2026-09-05 13:xx JST・最適化の回。**実物で踏んだ**）

    ここは長らく台帳の順（＝ 古い順）でした。`main()` は 50本 ずつ `videos.list`
    を撃ち、**日枠が尽きた日は 1組目で 403 → break** します。実測 09/05 03:59Z:
    「50本 読んだ / 33本 積んだ」——**その 33本 は 8月中旬の本**で、
    きょう出した本（a23e696j0f8・3gZ38lfsJpY・kzefG44_APU）は
    **`data/views.jsonl` に 1行 も在りません**。回が出した本ほど測れない向きです。
    **1組目が取れるなら、それは新しい 50本 であるべき**です
    （`src/live_views.py` の「いま出ている再生/日」もこの順に依ります）。
    **覆る条件**: 日枠に余裕が在る回は全組 取れるので、順は結果に効きません。
    """
    led = LOG.parent / "uploaded.jsonl"
    if not led.exists():
        return []
    out: list[str] = []
    seen: set[str] = set()
    for line in reversed(led.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        try:
            vid = str(json.loads(line).get("video_id") or "")
        except json.JSONDecodeError:
            continue
        if vid and vid not in seen:
            seen.add(vid)
            out.append(vid)
    return out


def main() -> int:
    import sys
    from pathlib import Path as _P

    # **値段の側も、書く側で止める**（`_log_blocked` の註・覆る条件 (1)）——
    # `record()` だけを塞ぐと、行は入らないのに `videos.list` 12単位 は毎回 出ていきます。
    if _log_blocked():
        print("[snapshot] 検査からは撃ちません（`snapshot._log_blocked`）")
        return 0

    sys.path.insert(0, str(_P(__file__).resolve().parent.parent))
    from googleapiclient.discovery import build

    from src import auth

    ids = _ids_from_ledger()
    if not ids:
        print("[snapshot] `data/uploaded.jsonl` に video_id がありません")
        return 1
    youtube = build("youtube", "v3", credentials=auth.credentials())
    videos: list[dict] = []
    for i in range(0, len(ids), 50):
        try:
            videos += youtube.videos().list(
                part="snippet,status,statistics",
                id=",".join(ids[i:i + 50]),
            ).execute()["items"]
        except Exception as exc:                     # noqa: BLE001
            auth.note_day_quota(exc, "videos.list snapshot")
            print(f"[snapshot] {i // 50 + 1}組目が取れませんでした: {str(exc)[:90]}")
            break
    if not videos:
        print("[snapshot] 1本も読めませんでした（日枠は JST 16:00 に戻ります）")
        return 1
    n = record(videos)
    newest = max((json.loads(x)["at"] for x in
                  LOG.read_text(encoding="utf-8").splitlines() if x.strip()),
                 default="?")
    print(f"[snapshot] {n}本 積みました（{len(videos)}本 読んだ / いちばん新しい点 {newest}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
