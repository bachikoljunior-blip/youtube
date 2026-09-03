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

**焼き直しは要りません。** 台本（`sha`）は変わらないので
`scripts/ahead_sweep.py` の焼き直しは起きず、
`apply_to_video()` が既にある下書きへ後から足せます。

## 覆る条件（数字で1つ）

`config/hypotheses.yaml` の「説明欄の先頭とコメントに登録の依頼を置くと、登録率が上がる」。
**外れたら、この2か所は消すこと**（`HEAD` と `COMMENT_TAIL` を空にすれば
呼び出し側は全部そのまま通ります —— `with_*()` は空なら何もしません）。

**このリポジトリの存在は書きません**（A2）。リンクも名前も入れないこと。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="説明欄とコメントに登録の依頼を置く")
    ap.add_argument("--apply", metavar="動画ID", action="append", default=[],
                    help="すでに上がっている本の説明欄の先頭に依頼を置く（50単位・冪等）")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
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
