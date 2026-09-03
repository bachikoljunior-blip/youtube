"""**登録の依頼を、最後まで見た人以外にも届ける**（`sub_rate` の腕）。

## なぜ在るか（2026-09-03 19:4x に足した。`scripts/eta.py` が名指しした所）

`eta.py` は毎周こう印字しています ——

    最初に落ちる門は **門1'（登録者 500人・あと 475人）** で **532日後**。
    その門を動かす腕は `views/day × sub_rate` の2本。
      `per_video` を天井まで → 門1' は 119日後
      `sub_rate`  を天井まで → 門1' は  81日後
      2本とも天井まで      →         19日後（**積**）
    直近 7日 の ship: `per_video` 115件 ／ `sub_rate` 7件
      ← **門を動かす2本のうち、片方しか引かれていません。**

そして、引かれていないほうの理由も同じ画面に在りました ——
**「登録の依頼はいま最後のセグメントの音声1文だけ（`src/script_writer.py`）
＝ 最後まで見た人にしか届きません」。**

実測すると、そのとおりでした（この回に数えた）:

* 説明欄  `src/pipeline.build_description()` が組む中身は
  `description_body` → 目次 → footer → `[t:題材]` の印。
  **footer は注意書き（合成音声・一般的な情報提供）だけで、依頼は1文字もありません。**
* コメント `VideoScript.first_comment` の欄の説明は
  **「宣伝や依頼は書かない」** と、はっきり禁じていました。

つまり **依頼が置いてあるのは「動画を最後まで見た人」の耳だけ**で、
**説明欄を開いた人・コメントを読んだ人には 1度も出していませんでした。**
長尺は平均視聴率 12.57%（`data/shorts_subs.json`）なので、
**依頼が届いていたのは、たどり着いた1割**です。

## どちら側の手か

`config/hypotheses.yaml` の 2026-08-30 の直しが、範囲をこう決めています ——
**「中身の側（動画の中の文言）で `sub_rate` の次の1件を立てないこと。
配信の側（長尺・面・配信の広さ）は塞ぎません」**（外れ 2件 はどちらも中身の側）。
ここが触るのは**説明欄とコメント ＝ 動画の外側**なので、塞がれていません。
そして**維持率を1秒も使いません** —— `src/script_writer.ROLE` の
「長尺では登録の依頼も書かない（維持率が落ちる）」と衝突しないのは、そのためです。

## 何をしているか（全部この1ファイル）

    HEAD            説明欄の**先頭**に置く2行（`もっと見る` を開く前に出る所）
    COMMENT_TAIL    `first_comment` の**末尾**に足す1文
    with_head()     説明欄に HEAD を足す（**何度掛けても増えません**）
    with_comment_ask()  コメントに COMMENT_TAIL を足す（同じく冪等・上限つき）
    apply_to_video()    **すでに上がっている本**の説明欄に足す（`videos.update` 50単位）
    rank_by_traffic()   **いま再生が付いている順**に並べる（`data/views.jsonl`・0単位）
    sweep()             その順で、まだ入っていない本へ置いていく（予算つき）

**焼き直しは要りません。** 台本（`sha`）は変わらないので
`scripts/ahead_sweep.py` の焼き直しは起きず、
`apply_to_video()` が既にある下書きへ後から足せます。

## `--sweep` を足した理由（2026-09-04 に数えた）

上の `apply_to_video()` は **動画IDを手で1本ずつ渡す形**でしか呼べず、
**repo のどこからも呼ばれていませんでした**（`grep apply_to_video` の当たりは
この1ファイルの中だけ）。**上がっている本を数え上げる手が無かった**からです。

その間に何が起きていたかを、この回に実測しました（`data/views.jsonl`・0単位）:

    上がっている本 249本のうち、いま再生が動いているのは **36本だけ**。
    上位 17本 で、いまの再生/日 の **92%**。
    そして**その1位（全体の 42.9%）の説明欄に、依頼は1文字も入っていませんでした**
    （`videos.list` で実際に読んで確かめた）。

つまり `sub_ask` は **これから作る本**にだけ効いていて、
**いまの再生のほぼ全部を運んでいる既存の本には、一度も掛かっていませんでした。**
`sub_rate` は「再生 × 率」なので、**掛かっていない側にこそ再生が在ります。**

`--sweep` は `rank_by_traffic()` の順（＝再生/日 の降順）に置いていきます。
**尽きるまで舐めません** —— 再生が動いていない 213本 に 50単位ずつ払っても
登録は1人も増えないので、**既定は再生が動いている本だけ**（`--min-per-day`）です。

## 覆る条件（数字で1つ）

`config/hypotheses.yaml` の「説明欄の先頭とコメントに登録の依頼を置くと、登録率が上がる」。
**外れたら、この2か所は消すこと**（`HEAD` と `COMMENT_TAIL` を空にすれば
呼び出し側は全部そのまま通ります —— `with_*()` は空なら何もしません）。

**このリポジトリの存在は書きません**（A2）。リンクも名前も入れないこと。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src import upload_cap

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

#: 説明欄の先頭に置く見出し。**`descriptions.body()` がここで定型を切ります**
#: （定型文を「本文」として数えさせないため。検査は `tests/test_sub_ask.py`）。
HEAD_MARK = "▼ 次の数字を受け取る"

#: 説明欄の先頭（`もっと見る` を開く前に見える所）。**2行まで。**
HEAD = (
    f"{HEAD_MARK}\n"
    "この計算は毎日1本ずつ出しています。チャンネル登録で次の数字が届きます。"
)

#: `first_comment` の末尾に足す1文。**コメントを読んだ人にだけ出ます。**
COMMENT_TAIL = "この計算は毎日1本ずつ出しています。次の数字はチャンネル登録で受け取れます。"

#: `commentThreads.insert` の本文上限（`src/uploader.py` が切っている値と同じ）。
COMMENT_LIMIT = 9000


def with_head(description: str) -> str:
    """説明欄の**先頭**に依頼を置く。**何度掛けても増えません。**

    既に `HEAD_MARK` が入っていれば、そのまま返します（`apply_to_video()` を
    2回 撃っても、焼き直しの後にもう一度 掛けても、増えません）。
    """
    text = str(description or "")
    if not HEAD.strip():
        return text
    if HEAD_MARK in text:
        return text
    if not text.strip():
        return HEAD
    return f"{HEAD}\n\n{text.lstrip()}"


def with_comment_ask(comment: str, *, limit: int = COMMENT_LIMIT) -> str:
    """`first_comment` の**末尾**に依頼を足す。**冪等・上限つき。**

    上限を越えるなら**足しません**（本編の要点のほうを削らない）。
    """
    text = str(comment or "").strip()
    tail = COMMENT_TAIL.strip()
    if not tail or not text:
        return text
    if tail in text:
        return text
    out = f"{text}\n\n{tail}"
    return out if len(out) <= limit else text


def apply_to_video(video_id: str, *, service=None, dry_run: bool = False) -> int:
    """**すでに上がっている本**の説明欄の先頭へ依頼を置く（`videos.update` 50単位）。

    既に入っていれば **0単位で戻ります**（`videos.list` の 1単位だけ）。
    """
    from src import upload_cap
    from src.uploader import _service

    youtube = service or _service()
    items = youtube.videos().list(part="snippet", id=video_id).execute().get("items") or []
    if not items:
        print(f"[sub_ask] {video_id} が見つかりません")
        return 1
    snippet = items[0]["snippet"]
    before = snippet.get("description", "")
    after = with_head(before)
    if after == before:
        print(f"[sub_ask] {video_id} には既に入っています（0単位）")
        return 0
    print(f"[sub_ask] {video_id} 『{snippet.get('title','')}』の説明欄の先頭に置きます:")
    for ln in HEAD.splitlines():
        print(f"           {ln}")
    if dry_run:
        print("[sub_ask] --dry-run なので書きません")
        return 0
    hold = upload_cap.reserve_hold()
    if hold:
        print(f"[sub_ask] 見送ります: {hold}")
        return 1
    snippet["description"] = after[:4900]
    youtube.videos().update(part="snippet",
                            body={"id": video_id, "snippet": snippet}).execute()
    upload_cap.note_quota_ok(detail=f"videos.update {video_id}")
    print(f"[sub_ask] 置きました（50単位）: {video_id}")
    return 0


#: `data/views.jsonl`（この repo が撮っている再生の控え）。
VIEWS = Path(__file__).resolve().parents[1] / "data" / "views.jsonl"

#: 掃いた記録。**1本 1行**（何をどう変えたかを、次に来た側が数えられるように）。
SWEEP_LOG = Path(__file__).resolve().parents[1] / "data" / "sub_ask_sweep.jsonl"

#: `videos.list` は 1回に 50本まで（1単位）。`videos.update` は 1本 50単位。
LIST_CHUNK = 50
LIST_UNITS = 1
UPDATE_UNITS = 50


def rank_by_traffic(path: Path | None = None, *, window_h: float = 24.0):
    """**いま再生が付いている順**に `(再生/日, 動画ID)` を返す（**API 0単位**）。

    `data/views.jsonl` の各本の最後の点と、そこから `window_h` 以上 前の点との
    差を、日あたりへ直したものです。**点が2つ無い本は入りません**（測れないので）。

    **なぜ総再生ではなく「いまの再生/日」で並べるのか。** 置く先の値打ちは
    **これから来る人の数**であって、過去に来た人の数ではありません。実測（2026-09-04）
    では総再生 1,441回 の本が 0.9回/日、136回 の本が 67.0回/日 で、順が逆でした。

    **覆る条件**: `data/views.jsonl` の撮る間隔が 24時間 より粗くなったら、
    この窓では差が出ません（`window_h` を伸ばすこと）。
    """
    import collections
    import datetime as _dt

    src = Path(path) if path else VIEWS
    if not src.exists():
        return []
    snaps: dict[str, list[tuple[str, int]]] = collections.defaultdict(list)
    for line in src.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        vid, at, views = d.get("id"), d.get("at"), d.get("views")
        if vid and at and views is not None:
            try:
                snaps[str(vid)].append((str(at), int(views)))
            except Exception:
                continue

    def _t(a: str):
        return _dt.datetime.fromisoformat(a.replace("Z", "+00:00"))

    out: list[tuple[float, str]] = []
    for vid, pts in snaps.items():
        pts.sort()
        last_at, last_v = pts[-1]
        t1 = _t(last_at)
        base = None
        for a, v in reversed(pts):
            if (t1 - _t(a)).total_seconds() >= window_h * 3600:
                base = (a, v)
                break
        if base is None:
            continue
        hrs = (t1 - _t(base[0])).total_seconds() / 3600
        if hrs <= 0:
            continue
        out.append(((last_v - base[1]) / hrs * 24, vid))
    out.sort(reverse=True)
    return out


def sweep(*, top: int = 40, min_per_day: float = 0.5, budget: int = 3000,
          service=None, dry_run: bool = False) -> int:
    """再生の付いている順に、説明欄の先頭へ依頼を置いていく。

    **読みは束ねます**（`videos.list` は 50本で 1単位）。書くのは
    **入っていない本だけ**（`videos.update` 50単位）。`budget` は**単位**で、
    使い切ったらそこで止めます（他の仕事の枠を食い潰さないため）。
    """
    ranked = [(d, v) for d, v in rank_by_traffic() if d >= min_per_day][:top]
    if not ranked:
        print("[sub_ask] 掃く本がありません（再生が動いている本が 0本）")
        return 0
    per_day = {v: d for d, v in ranked}
    ids = [v for _, v in ranked]
    print(f"[sub_ask] 対象 {len(ids)}本（再生/日 {min_per_day} 以上・"
          f"合計 {sum(per_day.values()):.1f}回/日）・予算 {budget}単位")

    if not HEAD.strip():
        print("[sub_ask] HEAD が空なので、何もしません（前提が外れた後の姿）")
        return 0

    youtube = service
    if youtube is None:
        from src.uploader import _service
        youtube = _service()

    used = 0
    snippets: dict[str, dict] = {}
    for i in range(0, len(ids), LIST_CHUNK):
        chunk = ids[i:i + LIST_CHUNK]
        if used + LIST_UNITS > budget:
            print("[sub_ask] 予算が尽きたので、読みをここで止めます")
            break
        res = youtube.videos().list(part="snippet", id=",".join(chunk)).execute()
        used += LIST_UNITS
        for it in res.get("items") or []:
            snippets[it["id"]] = it["snippet"]

    missing = [v for v in ids if v in snippets and HEAD_MARK not in
               (snippets[v].get("description") or "")]
    already = len(snippets) - len(missing)
    print(f"[sub_ask] 読めた {len(snippets)}本 ／ 既に入っている {already}本 ／ "
          f"置く先 {len(missing)}本（{used}単位 使用）")

    done = 0
    covered = 0.0
    for vid in missing:
        if used + UPDATE_UNITS > budget:
            print(f"[sub_ask] 予算 {budget}単位 に当たったので止めます"
                  f"（残り {len(missing) - done}本 は次の回）")
            break
        snippet = snippets[vid]
        before = snippet.get("description") or ""
        after = with_head(before)
        if after == before:
            continue
        title = (snippet.get("title") or "")[:36]
        print(f"[sub_ask] {vid} {per_day[vid]:6.1f}回/日 『{title}』")
        if dry_run:
            done += 1
            covered += per_day[vid]
            continue
        hold = upload_cap.reserve_hold()
        if hold:
            print(f"[sub_ask] 見送ります: {hold}")
            break
        snippet["description"] = after[:4900]
        try:
            youtube.videos().update(part="snippet",
                                    body={"id": vid, "snippet": snippet}).execute()
        except Exception as exc:                                    # noqa: BLE001
            print(f"[sub_ask] {vid} で落ちました: {type(exc).__name__} {str(exc)[:160]}")
            break
        used += UPDATE_UNITS
        upload_cap.note_quota_ok(detail=f"videos.update {vid}")
        done += 1
        covered += per_day[vid]
        _note_sweep(vid, per_day[vid])

    total = sum(d for d, _ in rank_by_traffic() if d > 0) or 1.0
    print(f"[sub_ask] 置いた {done}本 ／ {used}単位 ／ "
          f"いまの再生/日 の {100 * covered / total:.0f}% を覆いました"
          + ("（--dry-run なので書いていません）" if dry_run else ""))
    return 0


def _note_sweep(video_id: str, per_day: float) -> None:
    """掃いた1本を控えへ（**次の回が「いつ掛かったか」を数えられるように**）。"""
    import datetime as _dt
    try:
        SWEEP_LOG.parent.mkdir(parents=True, exist_ok=True)
        with SWEEP_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "id": video_id,
                "views_per_day": round(float(per_day), 2),
                "where": "description_head",
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="説明欄とコメントに登録の依頼を置く")
    ap.add_argument("--apply", metavar="動画ID", action="append", default=[],
                    help="すでに上がっている本の説明欄の先頭に依頼を置く（50単位・冪等）")
    ap.add_argument("--sweep", action="store_true",
                    help="いま再生が付いている順に、まだ入っていない本へ置いていく")
    ap.add_argument("--top", type=int, default=40, help="--sweep が見る本数（既定 40）")
    ap.add_argument("--min-per-day", type=float, default=0.5,
                    help="--sweep が相手にする最低の再生/日（既定 0.5）")
    ap.add_argument("--budget", type=int, default=3000,
                    help="--sweep が使ってよい単位（既定 3000 ＝ 約58本）")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    if args.sweep:
        return sweep(top=args.top, min_per_day=args.min_per_day,
                     budget=args.budget, dry_run=args.dry_run)
    if not args.apply:
        print(HEAD)
        print()
        print(COMMENT_TAIL)
        return 0
    rc = 0
    for vid in args.apply:
        rc |= apply_to_video(vid, dry_run=args.dry_run)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
