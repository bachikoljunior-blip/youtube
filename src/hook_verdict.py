"""**「engaged を決めているのは冒頭で画面が変わらないこと」の判定**（期限 2026-08-26）。

## 何を比べるか

    claim         engaged を決めているのは尺でも文言でもなく、冒頭で画面が変わらないこと
    falsified_if  新しい冒頭で作った本（8/19〜8/21）の engaged 比率の中央値が、
                  8/16〜8/18 の中央値を**上回らない**（同点も外れ）
    next_if_false 静止画スライド＋合成音声という形式そのものを疑う → M5 か YouTube 以外の面

**A も B も 30秒設計**なので、差は冒頭だけです（A の1枚目 45〜49字 → B は 18〜21字）。
尺の効果は `src/length_verdict.py` が別に測っており、**同じ3本を二度使いません。**

## `length_verdict` と同じ部品を使う理由

`fetch_engaged` / `ratios` / `MIN_VIEWS` を借ります。**線を引き直すと比較が壊れる**ため。
とくに `MIN_VIEWS=30` は、再生1〜4回の本が `engagedViews == views` で
**比率100%として中央値を持ち上げる**のを止める線です（2026-08-20 実測）。

## 本数は写さない

`falsified_if` の「3本」は書いた日の実測で、いまは合いません
（**実測 2026-08-23: A=6本 / B=65本 公開、うち 30再生以上が A=4 / B=28**）。
**条件の効いている部分は日付の範囲**なので、そちらで切り、本数は数え直して印字します。

## 読むもの

    公開時刻   scripts/eta.py の published_at()（**API 0単位**）
    engaged    YouTube Analytics の views / engagedViews（**Data API は使わない**）

**Data API の日枠が閉じている窓でも下せます**（判定に要るのは Analytics だけ）。
"""
from __future__ import annotations

import statistics
from datetime import date, timedelta, timezone

from src.length_verdict import MIN_VIEWS, _published, fetch_engaged, ratios

JST = timezone(timedelta(hours=9))

#: A ＝ 従来の冒頭（1枚目 45〜49字）／ B ＝ 冒頭を22文字に縮めた群。**JST の暦日で切る。**
A_FROM, A_TO = date(2026, 8, 16), date(2026, 8, 18)
B_FROM, B_TO = date(2026, 8, 19), date(2026, 8, 21)


def groups(published: dict | None = None) -> tuple[list[str], list[str]]:
    """公開時刻から A 群・B 群を返す。**純関数（API 0単位）。**"""
    published = published if published is not None else _published()
    a: list[str] = []
    b: list[str] = []
    for vid, born in published.items():
        d = born.astimezone(JST).date()
        if A_FROM <= d <= A_TO:
            a.append(vid)
        elif B_FROM <= d <= B_TO:
            b.append(vid)
    return sorted(a), sorted(b)


def verdict(a_ratios: list[float], b_ratios: list[float]) -> str:
    """**同点も外れ**（`falsified_if` は「上回らない」）。標本が無ければ判定不能。"""
    if not a_ratios or not b_ratios:
        return "測っていない"
    return "survived" if statistics.median(b_ratios) > statistics.median(a_ratios) else "falsified"


def main() -> None:  # pragma: no cover - 画面出力だけ
    a_ids, b_ids = groups()
    rows = fetch_engaged(a_ids + b_ids, A_FROM, date.today())
    rat = ratios(rows)
    a = [rat[v] for v in a_ids if v in rat]
    b = [rat[v] for v in b_ids if v in rat]
    print("### 冒頭で画面が変わることが engaged を決めている —— 判定")
    print(f"  A 8/16〜8/18（従来の冒頭）  公開 {len(a_ids)}本 / {MIN_VIEWS}再生以上 {len(a)}本")
    if a:
        print(f"    中央値 {statistics.median(a) * 100:.1f}%   " + " ".join(f"{x * 100:.1f}%" for x in sorted(a)))
    print(f"  B 8/19〜8/21（冒頭22文字）  公開 {len(b_ids)}本 / {MIN_VIEWS}再生以上 {len(b)}本")
    if b:
        print(f"    中央値 {statistics.median(b) * 100:.1f}%")
    v = verdict(a, b)
    print(f"  → **{v}**")
    if v == "falsified":
        print("     冒頭を縮めても engaged は上がりませんでした。")
        print("     `next_if_false`: **静止画スライド＋合成音声という形式そのものを疑う。**")


if __name__ == "__main__":  # pragma: no cover
    main()
