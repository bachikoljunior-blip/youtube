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
    before = str(snippet.get("title") or "")
    print(f"  前: {before}")

    from src import retitles                                    # noqa: PLC0415

    # **実物ともう同じ字なら、撃たないこと**（2026-09-05 04:4x に数えて足した）。
    #
    # 50単位 を撃つ道具は4つあり、**3つは「もう同じ値か」を必ず見ています** ——
    # `reschedule._update`（`report["reason"] == "same"`・2026-08-27 に足して
    # **その日の枠の 6割**＝ 5,750単位 が同じ値の書き直しだったと数えている）、
    # `sub_ask.apply_to_video`（`after == before` → 「既に入っています（0単位）」）、
    # `refresh_thumbnail`（絵は控えから作り直してから押す）。
    # **ここだけが、読んだ字と書く字を1度も比べていませんでした** ——
    # `videos.list` で `before` を読んでいるのに、そのまま `update` を撃っています。
    #
    # **これは机上の穴ではありません。** `src/retitles.py` の註が実測を残しています ——
    # 同じ本の題を **3つの回（23:04・00:07・00:2x）が追いかけた**。追いかけた側が
    # 先の回と同じ字を打てば、その 50単位 は**1文字も変えずに**消えます。
    #
    # 止めても失うものがありません（**望んだ字は、もう実物に載っています**）。
    if before == title:
        print("[retitle] **実物はもうその字です。書きません**（`videos.update` 0単位）。")
        # **控えのほうが古いなら、そこだけ直します**（`reschedule._update` の `"same"` の枝と
        # `sub_ask` の `description_head/already` と同じ考え —— **実物が正本で、控えはその写し**）。
        if retitles.latest().get(video_id) != before:
            retitles.record(video_id, before, prev=retitles.latest().get(video_id) or "")
            print("[retitle] 控え（`data/retitled.jsonl`）を実物へ寄せました（API 0単位）。")
        return 0

    # **前に名乗っていた字へ戻すのは、止めません。印字だけします**（`retitles.seen_before` の註）。
    # `retitle.py` の存在理由は「誤解を与えるタイトルを今すぐ直す」ことなので、
    # **戻す道を塞ぐと、この道具自身が塞がります。**
    for row in retitles.seen_before(video_id, title):
        print(f"[!] この字は {row.get('at')} にも名乗っています ——"
              f" 戻すなら 50単位 です。**数を1つ持って来ること**")

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
    # **帳面にも書くこと**（2026-09-05 00:2x に踏んだ・`src/retitles.py` の註に実測）。
    # `data/uploaded.jsonl` は「上げたときの行」で、ここを差し替えても**1文字も変わりません**。
    # `[次の枠]`（`src/next_slot.py`）はその帳面の `title` を刷るので、
    # **書かないと、その回がいちばん先に読む1行が古い題のままになります。**
    # 帳面は追記専用（`merge=union`）なので、行は書き換えず、別の帳面へ足して重ねます。
    retitles.record(video_id, title, prev=before)
    print(f"  後: {title}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
