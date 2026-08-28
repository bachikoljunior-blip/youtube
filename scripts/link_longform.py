#!/usr/bin/env python3
"""ショートの説明欄に、同じ題材の長尺への導線を入れる（M8）。

    python scripts/link_longform.py --dry-run
    python scripts/link_longform.py

## なぜ要るか

2026-08-10 に `docs/MEANS.md` の7件を全部掛けたら、**詰まりが1点に集まった。**

    M1 ショート広告   ショートのRPMが¥50〜150  → 門の先でも月1000円台
    M3 商品を売る     WATCH が28日で2人        → 置く場所に人がいない
    M7 広告を買う     通った先が月1000円台     → 甘い前提でも回収8年

**別々の理由ではない。全部「ショートのフィードから外に出られていない」。**
再生の 99.95% がフィード内で完結している。

**そして説明欄を実際に読んだら、他の動画への導線が1本も無かった。**
同じ題材の長尺が既にあるのに、繋いでいないだけだった。**追加費用ゼロ。**

## 使える経路と、使えない経路

    カード      Data API に**無い**。YouTube Studio 専用＝オーナーの操作が要る
    固定コメント コメントの投稿はできるが、**固定は API に無い**
    説明欄      **できる。これを使う**
    再生リスト   できる。ショートのフィード再生は再生リストを辿らないので効きは弱い

## どう測るか

**説明欄のクリック数は API では取れない。** だが測る必要が無い。
**長尺の再生数がほぼ0**（6本で計2再生・1週間）なので、**増分そのものが測定になる。**
`src/scan.py` が毎時 `動画.<ID>.views` を取っているので、追加の道具は要らない。

しきい値は掛け算して置いた。導線付きショート8本 × 1本あたり中央値660再生 ＝ 約5,280再生。

    転換 1.0% → 53再生   転換 0.1% → 5再生   ← **0.1% でも 0 と区別がつく**

**外れとみなす条件: 導線付きショートが計3,000再生に達した時点で、
対応する長尺の合計が5再生に届かない**（＝転換 0.17% 未満）。

## 冪等

すでに導線が入っている説明は飛ばす。何度でも回してよい。
`[t:テーマID]` は投稿済みの復元に使っているので、**絶対に落とさない。**
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402

from src import config  # noqa: E402
from src.uploader import _service  # noqa: E402

PAIRS = config.ROOT / "config" / "pairs.yaml"
MARK = "▼ 同じ題材を長い尺で計算した回"

# **数字を書かないこと。** 説明欄の数字は裏取りの対象になる。
# ここは導線なので、事実だけ（同じ題材・長い尺）にとどめる。
BLOCK = MARK + "\n{url}\n"


def _pairs() -> dict[str, str]:
    data = yaml.safe_load(PAIRS.read_text(encoding="utf-8")) or {}
    return data.get("pairs") or {}


def _insert(desc: str, url: str) -> str | None:
    """導線を差し込む。すでに入っていれば None。

    置き場所は **▼目次 の直前**。説明を開いた人が最初に当たる位置で、
    かつ計算の中身（＝この動画の値打ち）を押し下げない。
    """
    if MARK in desc or url in desc:
        return None
    block = BLOCK.format(url=url)
    idx = desc.find("▼ 目次")
    if idx == -1:
        idx = desc.find("─────")
    if idx == -1:
        return desc.rstrip() + "\n\n" + block
    return desc[:idx] + block + "\n" + desc[idx:]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    pairs = _pairs()
    y = _service()
    ch = y.channels().list(part="contentDetails", mine=True).execute()["items"][0]
    up = ch["contentDetails"]["relatedPlaylists"]["uploads"]

    ids, tok = [], None
    while True:
        r = y.playlistItems().list(part="contentDetails", playlistId=up,
                                   maxResults=50, pageToken=tok).execute()
        ids += [i["contentDetails"]["videoId"] for i in r["items"]]
        tok = r.get("nextPageToken")
        if not tok:
            break

    # **計測のぶんを残して止める**（2026-08-28 の最適化の回・2枚目）。
    # `videos.update` は **50単位**。ここは1回で何十本も書き換えうるので、
    # 門が無いと**残しておいた 400単位 を、この1コマンドで丸ごと持っていけます。**
    # 読み（`videos.list` 1単位）は止めません —— 残しているのが当のそれです。
    # `--dry-run` は書かないので通します。
    if not args.dry_run:
        from src import upload_cap                             # noqa: PLC0415

        hold = upload_cap.reserve_hold()
        if hold:
            print(f"[link] {hold}")
            print("[link] **書きません**（`YT_NO_RESERVE=1` で外せます）。"
                  " 導線は消えないので、窓が変わった回に同じ1行で入れ直せます。")
            return 1

    done = skipped = 0
    for i in range(0, len(ids), 50):
        items = y.videos().list(part="snippet",
                                id=",".join(ids[i:i + 50])).execute()["items"]
        for it in items:
            sn = it["snippet"]
            m = re.search(r"\[t:([^\]]+)\]", sn.get("description", ""))
            if not m or m.group(1) not in pairs:
                continue
            target = pairs[m.group(1)]
            if target == it["id"]:            # 自分自身に繋がない
                continue
            url = f"https://youtu.be/{target}"
            new = _insert(sn["description"], url)
            if new is None:
                skipped += 1
                continue
            # **[t:...] を落としていないことを、書き込む前に確かめる。**
            # 落とすと投稿済みの復元がチャンネル越しにできなくなる。
            if m.group(0) not in new:
                print(f"  [!] {it['id']} テーマIDが消える。書き込みません")
                continue
            print(f"  {it['id']}  {sn['title'][:30]}  → {url}")
            if args.dry_run:
                continue
            sn["description"] = new
            y.videos().update(part="snippet", body={
                "id": it["id"], "snippet": sn}).execute()
            # **通ったら数えること**（2026-08-28）。門は `spent` を読み、
            # `spent` を作るのは `note_quota_ok` だけです。ここは1回で
            # 何十本も書くので、数えないと門は**自分が通した数千単位を
            # 1つも知りません**（＝ 止めるべき回に止まりません）。
            from src import upload_cap as _cap          # noqa: PLC0415
            # **末尾に印を付けること**（2026-08-28）。`moves_in_window()` は
            # `videos.update <vid>` で**終わる**行を「その本を動かした」と
            # 数え、`MOVE_CAP`（1本 2回/窓）に効かせます。ここは説明欄の
            # 書き換えで、**予約を動かしていません** —— 印を付けないと、
            # 導線を入れただけで入れ替えの持ち手を2回ぶん奪います。
            # `unit_cost` は前方一致なので 50単位 のままです。
            _cap.note_quota_ok(detail=f"videos.update {it['id']} link")
            done += 1

    print(f"\n入れた {done}件 / すでに入っていた {skipped}件"
          + ("（--dry-run なので書き込んでいません）" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
