#!/usr/bin/env python3
"""公開済み動画のタイトルを直す。

    python scripts/retitle.py <動画ID> "新しいタイトル"

なぜ要るか。**2026-08-05、公開済み2本のタイトルが中身と食い違っていた。**

`boeJXYdqW88` は「勤続20年の直前で辞めると失業給付が最大163万円減る」。
だが 163万9800円は**離職理由**（自己都合150日 vs 倒産・解雇330日）の差であって、
勤続20年の境界の差ではない（そちらは最大27万3300円）。
**台本の中身は正確だった。ずれていたのはタイトルだけ。**

タイトルは動画の中でいちばん読まれる部分で、YouTube のポリシーは
「誤解を与える内容」を名指ししている。収益化されなければ収入はゼロなので、
これは体裁の話ではなく到達可能性の話。

**なぜ起きたか。** 投稿前の検査（`src/verify.py`）は、尺・画・字幕・冒頭は見るが、
**タイトルが台本の主張と合っているかは誰も見ていない。** 数字が台本に実在する
だけでは足りず、**その数字が何の差なのか**まで一致している必要がある。
機械で見るのは難しいので、いまは人（＝こちら）が見るしかない。
**作ったら必ずタイトルを台本と突き合わせること。**

カテゴリなどを消さないよう、既存の snippet を読んでから title だけ差し替える。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.uploader import _service  # noqa: E402

# **A2**: このリポジトリの存在を出さない。タイトルにも入れない。
FORBIDDEN = ("github", "リポジトリ", "repository", "claude", "ソースコード")


def main(video_id: str, title: str) -> int:
    if len(title) > 100:
        print(f"[!] タイトルが{len(title)}文字。YouTube の上限は100文字です")
        return 1
    low = title.lower()
    for word in FORBIDDEN:
        if word in low:
            print(f"[!] タイトルに『{word}』が入っています。伏せる決まりです")
            return 1

    youtube = _service()
    items = youtube.videos().list(part="snippet", id=video_id).execute()["items"]
    if not items:
        print(f"[!] {video_id} が見つかりません")
        return 1

    snippet = items[0]["snippet"]
    print(f"  前: {snippet['title']}")
    snippet["title"] = title
    # **計測のぶんを残して止める**（2026-08-28 の最適化の回・2枚目）。
    # `videos.update` は **50単位**。1本だけの道具ですが、門を外しておくと
    # 「1本ずつなら安い」で最後の 400単位 が8回で消えます。
    # **誤ったタイトルを直す道は塞ぎません** —— `YT_NO_RESERVE=1` で通ります
    # （ポリシー違反を直す回は、それを使うこと。理由を JOURNAL に）。
    from src import upload_cap                                 # noqa: PLC0415

    hold = upload_cap.reserve_hold()
    if hold:
        print(f"[retitle] {hold}")
        print("[retitle] **書きません。** 誤解を与えるタイトルを今すぐ直す回は"
              " `YT_NO_RESERVE=1` を付けること（理由を JOURNAL に）。")
        return 1
    youtube.videos().update(part="snippet", body={"id": video_id, "snippet": snippet}).execute()
    # **通ったら数えること**（2026-08-28）。門（`reserve_hold`）は `spent` を読み、
    # `spent` を作るのは `note_quota_ok` だけです。**門だけ付けて数えないと、
    # 門は自分が通した 50単位 を1つも知りません。**
    # **末尾に印**（`link_longform` と同じ理由）。タイトルの書き換えは
    # 予約を動かしていないので、`MOVE_CAP` の持ち手を奪わないこと。
    upload_cap.note_quota_ok(detail=f"videos.update {video_id} retitle")
    print(f"  後: {title}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
