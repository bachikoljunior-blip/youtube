"""**チャンネルのホームを、登録に変える面にする**（腕 `sub_rate`）。

## なぜここか（2026-08-20 20:1x。**測ってから足しています**）

`scripts/eta.py` が名指しする腕は `sub_rate` です。ところが `config/hypotheses.yaml`
には、この腕で**3回続けて外れた実験**が入っています ——
「次に何の数字が得られるか」856再生で登録0人／「この場所の性格を言う」2,720再生で
登録0人／「最後の1枚の問いかけ」3,325再生でコメント0件。

**3回とも、動画の中の文言です。** 動画の外側 —— **視聴者がチャンネル名を押した先** ——
は、一度も触っていませんでした。実物を見ると、こうでした（2026-08-20 20:2x）:

    unsubscribedTrailer : None      ← 未登録者に流れる紹介動画が**無い**
    brandingSettings.image: {}      ← バナー画像が**無い**
    playlists           : 9件       ← 並びはある

そして Analytics は、**その面から登録が入っている**ことを言っています:

    creatorContentType = shorts                       22,549再生 → 8人（0.0355%）
    creatorContentType = videoOnDemand                    11再生 → 1人
    creatorContentType = creatorContentTypeUnspecified      0再生 → **2人**

**11人のうち2人（18%）が、再生に紐づかない面から入っています。**
ホームには紹介動画もバナーも無いのに、です。**ここは測って空だった面ではなく、
一度も作っていない面**でした。

## 何を置くか（**選ぶのは実測。好みではない**）

紹介動画は「**実際にいちばん登録に変えた本**」を選びます。

    CdX2oIb7BG8  1,451再生 → **3人**（0.207%）  ← チャンネル平均の 4.7倍
    gPusj-Y2404  1,740再生 → 1人（0.057%）

**床を置く理由**: 登録率 0.0443% では、100再生の期待値は 0.04人です。
1再生1人のような行が勝たないよう、**再生 500以上・登録 2人以上**を要求します
（500再生の期待値は 0.22人なので、2人は偶然では出にくい）。
`config/hypotheses.yaml` 冒頭の「しきい値は必ず掛け算してから置くこと」と同じ形です。
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

from .thumbnail import _font

#: 紹介動画に選ぶ床。**この2つは掛け算から出しています**（上の docstring）。
MIN_VIEWS = 500
MIN_SUBS = 2

#: バナーの寸法。YouTube の推奨は 2048×1152 で、**どの端末でも必ず見える帯**は
#: 中央 1235×338 だけ。字はそこから出さないこと。
BANNER_SIZE = (2048, 1152)
SAFE_SIZE = (1235, 338)

BANNER_BG = (14, 26, 24)
BANNER_ACCENT = (77, 216, 160)
BANNER_FG = (245, 248, 246)
BANNER_SUB = (150, 168, 162)

BANNER_HEAD = "自分で計算した結果を出す"
BANNER_LINES = ("制度の解説ではなく、条文から式を組んで数字を出す", "前提と計算式は、全部画面に出しています")


def pick_trailer(rows: list[tuple[str, int, int]]) -> str | None:
    """`(video_id, views, subs)` から、**登録に変えた率がいちばん高い本**を返す。

    床（`MIN_VIEWS` / `MIN_SUBS`）に届く行が1つも無ければ `None`。
    **そのときは紹介動画を置きません** —— 置く先を勘で選ぶと、
    「何を置いたら登録が増えたか」が次に測れなくなります。
    """
    best: tuple[float, str] | None = None
    for video_id, views, subs in rows:
        if views < MIN_VIEWS or subs < MIN_SUBS:
            continue
        rate = subs / views
        if best is None or rate > best[0]:
            best = (rate, video_id)
    return best[1] if best else None


def render_banner(out_path: Path) -> Path:
    """バナーを1枚描いて返す。**外に出ません**（API も画像も使わない）。"""
    img = Image.new("RGB", BANNER_SIZE, BANNER_BG)
    draw = ImageDraw.Draw(img)

    # 安全帯の左端に細い縦線。**この線が、字を置いてよい範囲の目印**でもある。
    sx = (BANNER_SIZE[0] - SAFE_SIZE[0]) // 2
    sy = (BANNER_SIZE[1] - SAFE_SIZE[1]) // 2
    draw.rectangle([sx, sy + 24, sx + 8, sy + SAFE_SIZE[1] - 24], fill=BANNER_ACCENT)

    head_font = _font(84)
    draw.text((sx + 44, sy + 30), BANNER_HEAD, font=head_font, fill=BANNER_FG)

    body_font = _font(38)
    y = sy + 168
    for line in BANNER_LINES:
        draw.text((sx + 46, y), line, font=body_font, fill=BANNER_SUB)
        y += 58

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")
    return out_path


def _rows_from_analytics(start: str, end: str) -> list[tuple[str, int, int]]:
    from googleapiclient.discovery import build

    from .auth import credentials

    an = build("youtubeAnalytics", "v2", credentials=credentials(), cache_discovery=False)
    res = an.reports().query(
        ids="channel==MINE", startDate=start, endDate=end,
        metrics="views,subscribersGained", dimensions="video",
        sort="-views", maxResults=50,
    ).execute()
    return [(r[0], int(r[1]), int(r[2])) for r in res.get("rows", []) or []]


def apply(start: str, end: str, banner: Path | None, dry_run: bool = False) -> dict:
    """紹介動画とバナーを、チャンネルへ実際に置く。

    **`channels.update` は 50単位**、`channelBanners.insert` は 50単位です
    （`videos.insert` の 1,600単位に比べれば無視できる）。
    """
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    from .auth import credentials

    creds = credentials()
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)

    rows = _rows_from_analytics(start, end)
    trailer = pick_trailer(rows)
    got = yt.channels().list(part="brandingSettings", mine=True).execute()["items"][0]
    branding = got.get("brandingSettings", {})
    channel = dict(branding.get("channel", {}))
    image = dict(branding.get("image", {}))

    out: dict = {"channel_id": got["id"], "trailer": trailer, "banner_url": None,
                 "before_trailer": channel.get("unsubscribedTrailer"),
                 "before_banner": image.get("bannerExternalUrl")}

    if banner is not None and not dry_run:
        media = MediaFileUpload(str(banner), mimetype="image/png", resumable=False)
        up = yt.channelBanners().insert(media_body=media).execute()
        image["bannerExternalUrl"] = up["url"]
        out["banner_url"] = up["url"]

    if trailer:
        channel["unsubscribedTrailer"] = trailer

    if dry_run:
        return out

    body = {"id": got["id"], "brandingSettings": {"channel": channel, "image": image}}
    yt.channels().update(part="brandingSettings", body=body).execute()
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="チャンネルのホームに、紹介動画とバナーを置く（腕 sub_rate）")
    ap.add_argument("--start", default="2026-05-01", help="Analytics の開始日")
    ap.add_argument("--end", default="2026-08-17", help="Analytics の終了日（実データは3日遅れ）")
    ap.add_argument("--banner", default="build/banner.png", help="バナーの書き出し先")
    ap.add_argument("--no-banner", action="store_true", help="バナーは置かない（紹介動画だけ）")
    ap.add_argument("--dry-run", action="store_true", help="外へ書かない。選んだ本だけ出す")
    args = ap.parse_args(argv)

    banner = None
    if not args.no_banner:
        banner = render_banner(Path(args.banner))
        print(f"[banner] 描きました: {banner}")

    res = apply(args.start, args.end, banner, dry_run=args.dry_run)
    print(f"[channel] {res['channel_id']}")
    print(f"  紹介動画: {res['before_trailer']} → {res['trailer']}")
    print(f"  バナー  : {res['before_banner']} → {res['banner_url']}")
    if res["trailer"] is None:
        print("  [!] 床（再生500・登録2人）に届く本がありません。**紹介動画は置いていません**")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
