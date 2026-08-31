#!/usr/bin/env python3
"""検索語べつの流入を出す。**M4（検索流入）の判定に使う唯一の計器。**

`docs/MEANS.md` M4 の基準値は **「お金に関係する検索からの流入 = 1再生/7日」**です。
`status.py` の流入経路が出す `YT_SEARCH 42` と**比べてはいけません。**
あの42には「絶望ビリー カラオケ」「草川兄弟」のような**無関係な語**が入っており、
こちらのショートが知らない検索面に差し込まれただけのぶんです。
**中身を見ないと、無関係な語の増減を「検索に載った」と読み違えます**（8/9 に一度やった）。

2026-08-12 まで、この分解は**毎回その場で手打ちしていました。** M4 は9/15 を期限に
「長尺の登録率はショートの1桁以上」を判定する、いま唯一の実行中の手段です。
**判定に要る計器が台帳になく、回ごとに作り直されていたら、判定は続きません。**

    python scripts/search_terms.py            # 直近7日（基準値と同じ窓）
    python scripts/search_terms.py --days 28

**お金の語かどうかは `MONEY` の部分一致で決めています。推測ではなく分類です。**
外れたら足すこと。分類を変えたら、その回の JOURNAL に書くこと
（**基準値と違う物差しで比べると、差が物差しのぶんなのか分かりません**）。

## 語だけ見ても足りません（2026-08-12 に踏んだ）

最初の版は語しか出さず、**「お金の語 8再生 / 基準値 1」＝ M4 が8倍**に見えました。
**違いました。** 動画べつに引き直すと、8のうち9件（窓の差）は**ショート**
`8rXlUhkfMEU`（住宅ローン控除・56秒）で、**M4 が出した長尺3本は行すら無い。**

    8rXlUhkfMEU  ショート  SHORTS 428 / YT_SEARCH 9 / YT_OTHER_PAGE 8
    YHiigJ3Zpj4  長尺      （行なし）
    m_q1G_GNgY8  長尺      （行なし）
    G3VqIFpBwKo  長尺      （行なし）

**M4 は「長尺が検索に載るか」の手段です。** ショートが検索面に差し込まれたぶんを
足すと、**手段が動いていないのに動いたことになります。**
無関係な語を弾くだけでは足りない —— **関係のある語で、形式が違う**からです。
だからこの計器は **長尺ぶんとショートぶんを分けて出します。M4 の判定は長尺の行だけ。**
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.auth import credentials

# お金・制度に関係する語。**この企画が狙っている面かどうか**だけを分ける。
MONEY = (
    "税", "控除", "年金", "保険", "給付", "手当", "残業", "給与", "年収", "手取り",
    "収入", "副業", "確定申告", "申告", "還付", "ふるさと納税", "扶養", "失業",
    "退職", "住民税", "所得", "医療費", "住宅ローン", "社会保険", "賞与", "ボーナス",
    "円", "万円", "いくら", "計算", "上限", "分岐点", "節税", "経費",
)


def is_money(term: str) -> bool:
    return any(w in term for w in MONEY)


class FetchFailed(Exception):
    """取れなかった。**「0件だった」と混ぜないこと。**

    最初の版はこれを空リストで返し、`main` が「検索からの流入が1件もありません。
    これが基準値の状態です」と出しました。**失敗と基準値が同じ字面になっていました。**
    M4 は「基準値の1から動いたか」で判定するので、
    **エラーを基準値として読むと、動いていないという判定が勝手に立ちます。**
    """


def fetch(days: int) -> list[tuple[str, int, int]]:
    analytics = build("youtubeAnalytics", "v2", credentials=credentials(), cache_discovery=False)
    end = date.today()
    start = end - timedelta(days=days)
    try:
        response = analytics.reports().query(
            ids="channel==MINE",
            startDate=start.isoformat(),
            endDate=end.isoformat(),
            metrics="views,estimatedMinutesWatched",
            dimensions="insightTrafficSourceDetail",
            filters="insightTrafficSourceType==YT_SEARCH",
            sort="-views",
            # **25 を超えると 500 FIELD_UNKNOWN_VALUE (max-results) が返ります**
            # （2026-08-12 に 200 で踏んだ）。400 ではなく 500 で返るので、
            # 「API が一時的に不調」と読み違えないこと。
            maxResults=25,
        ).execute()
    except HttpError as exc:
        raise FetchFailed(f"{exc.resp.status} {exc}") from exc
    rows = response.get("rows", []) or []
    return [(r[0], int(r[1]), int(r[2])) for r in rows]


def candidate_ids(days: int) -> list[str]:
    """**この窓で1再生でも付いた動画ID**を、Analytics から1回で引く（**日枠 0単位**）。

    検索からの再生は総再生の内側なので、**総再生が 0 の本に `YT_SEARCH` の行は立ちません。**
    だから下の1本ずつの照会は、この集合に絞って構いません
    （2026-09-01 実測: 直近7日で **121本**・1回 1.2秒）。

    **`dimensions="video"` に `insightTrafficSourceType` の filter は掛けられません**
    —— 2026-09-01 に撃ち直して確かめました（400 `The query is not supported`）。
    **だから「1回で全部」にはできません。** ここで縮められるのは候補までです。
    """
    analytics = build("youtubeAnalytics", "v2", credentials=credentials(), cache_discovery=False)
    end = date.today()
    start = end - timedelta(days=days)
    try:
        rows = analytics.reports().query(
            ids="channel==MINE",
            startDate=start.isoformat(),
            endDate=end.isoformat(),
            metrics="views",
            dimensions="video",
            sort="-views",
            maxResults=200,
        ).execute().get("rows", []) or []
    except HttpError as exc:
        raise FetchFailed(f"候補の動画: {exc.resp.status} {exc}") from exc
    return [str(r[0]) for r in rows if int(r[1]) > 0]


def local_meta(ids: list[str]) -> dict[str, tuple[str, bool]]:
    """動画ID → (題, ショートか) を**手元の帳面から**組む（**API を1回も叩きません**）。

    形は `src.forms.classify()` に決めさせます —— あれが
    「実測（`data/video_forms.json`）→ 控えの秒数 → 題名の札」の順で決める**1か所**で、
    「同じ帳面を読む2つが逆のことを言っていた」を潰すために置かれたものです。
    ここで別の規則（秒数だけ、札だけ）を書くと、その1か所がまた2か所になります。

    2026-09-01 実測: 候補 121本は **121本とも「実測」**で決まりました（札に落ちた本は 0）。
    題の取れなかった本は 1本で、そこは動画IDをそのまま出します
    （**題が無いことより、行ごと消えるほうが悪い** —— 長尺かどうかは別に決まっています）。
    """
    from src import dupes, forms

    ledger: dict[str, dict] = {}
    for row in dupes.ledger_rows():
        vid = str(row.get("id") or "")
        if vid:
            ledger[vid] = row      # 同じIDが複数行あるときは後の行が勝ち
    measured = forms.measured_forms()
    out: dict[str, tuple[str, bool]] = {}
    for vid in ids:
        row = ledger.get(vid) or {"id": vid}
        out[vid] = (str(row.get("title") or "") or vid, forms.is_short(row, measured))
    return out


def by_video(days: int) -> list[tuple[str, str, bool, int, int]]:
    """検索からの再生を**動画べつ**に出す。返りは (id, 題, ショートか, 再生, 分)。

    **`dimensions='video'` に `insightTrafficSourceType` の filter は掛けられません**
    （400 `The query is not supported`）。逆向き —— 動画で filter して
    流入経路を dimension にする —— は通るので、候補を1本ずつ引きます。

    ## **Data API を1回も叩きません**（2026-09-01 に直した）

    前の版は、公開ぶんの一覧を **Data API** から作っていました
    （`channels.list` → `playlistItems.list` → `videos.list`）。**あれは日枠を使う口**です。

    **枠が尽きた回に、この節ごと落ちていました。** しかも落ち方が悪い ——
    その3本は `HttpError` をそのまま投げ、**`FetchFailed` に包んでいませんでした。**
    `main()` には「**動画べつが取れませんでした。この回は M4 を判定できません**」という
    断りが**ちゃんと在ります**が、あれが待っているのは `FetchFailed` だけなので、
    **素の `HttpError` はその横をすり抜けて traceback で死にます。**

    残るのは、直前に印字ずみの**語べつの節だけ**です ——
    「**この数字だけで M4 を判定しないこと。下の動画べつを見ること**」と
    書いた直後に、その下が消える。`FetchFailed` の docstring が
    「**失敗と基準値を混ぜるな**」と言っているのと同じ穴が、**包み忘れ**で開いていました。

    いまは候補を Analytics（**日枠 0単位**）から、題と形を**手元の帳面**から取ります。
    **枠が尽きている回でも M4 は判定できます** —— M4 の期限は 9/15 で、
    枠は毎日 尽きます（2026-09-01 実測: 13,352単位 / 枠 10,000・403 を 43回）。
    """
    ids = candidate_ids(days)
    meta = local_meta(ids)

    analytics = build("youtubeAnalytics", "v2", credentials=credentials(), cache_discovery=False)
    end = date.today()
    start = end - timedelta(days=days)
    out: list[tuple[str, str, bool, int, int]] = []
    for vid in ids:
        title, short = meta[vid]
        try:
            rows = analytics.reports().query(
                ids="channel==MINE",
                startDate=start.isoformat(),
                endDate=end.isoformat(),
                metrics="views,estimatedMinutesWatched",
                dimensions="insightTrafficSourceType",
                filters=f"video=={vid}",
                sort="-views",
            ).execute().get("rows", []) or []
        except HttpError as exc:
            raise FetchFailed(f"{vid}: {exc.resp.status}") from exc
        for source, views, minutes in rows:
            if source == "YT_SEARCH":
                out.append((vid, title, short, int(views), int(minutes)))
    out.sort(key=lambda r: -r[3])
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()

    try:
        rows = fetch(args.days)
    except FetchFailed as exc:
        print(f"=== 検索語（直近{args.days}日）===")
        print(f"  **取れませんでした: {exc}**")
        print("  **これは「0再生」ではありません。この回は M4 を判定できません。**")
        return 1

    if not rows:
        print(f"=== 検索語（直近{args.days}日）===")
        print("  検索からの流入が1件もありません（**取得は成功しています**）。")
        return 0

    money = [r for r in rows if is_money(r[0])]
    other = [r for r in rows if not is_money(r[0])]
    money_views = sum(r[1] for r in money)
    total_views = sum(r[1] for r in rows)

    print(f"=== 検索語（直近{args.days}日）===")
    print(f"  お金・制度の語 **{money_views}再生**（{len(money)}語） / 上位{len(rows)}語の和 {total_views}再生")
    if len(rows) >= 25:
        # **API 側の上限が25行**。1再生の語が並ぶので、ここは必ず切れます。
        # 実測 8/12: 語の和 23 に対し、動画べつの和は 42。**この差は欠測です。**
        print("  [!] **25語で切れています。上の和は検索の合計ではありません**（下の動画べつが合計）")
    print("  **この数字だけで M4 を判定しないこと。** 下の動画べつを見ること。")
    print("  --- お金・制度の語 ---")
    for term, views, minutes in money[:40]:
        print(f"    {views:5d}再生 {minutes:4d}分  {term}")
    if not money:
        print("    （なし）")
    print("  --- 無関係な語（ショートが差し込まれただけ。**M4 の判定に使わない**）---")
    for term, views, minutes in other[:20]:
        print(f"    {views:5d}再生 {minutes:4d}分  {term}")
    if len(other) > 20:
        print(f"    …ほか {len(other) - 20}語")

    try:
        vids = by_video(args.days)
    except FetchFailed as exc:
        print(f"  **動画べつが取れませんでした: {exc}。この回は M4 を判定できません。**")
        return 1

    long_views = sum(v[3] for v in vids if not v[2])
    short_views = sum(v[3] for v in vids if v[2])
    print(f"  --- 動画べつ（**M4 の判定はここ**）---")
    for _vid, title, short, views, minutes in vids:
        kind = "ショート" if short else "**長尺**"
        print(f"    {views:5d}再生 {minutes:4d}分  {kind}  {title[:38]}")
    if not vids:
        print("    （検索から入った公開動画はありません）")
    print(f"  **長尺 {long_views}再生 / ショート {short_views}再生**")
    print(f"  **M4 の基準値は 1再生/7日。比べるのは長尺の {long_views} です。**")
    print("  ショートぶんは M4 の成否と無関係です（検索面に差し込まれただけ）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
