#!/usr/bin/env python3
"""**画面を見ないと指示対象が分からない語**を、控えの台本から数える（2026-08-28）。

    python scripts/deixis_count.py        # API 0単位・数秒

## なぜ repo に置くか

2026-08-27 の調査（オーナー指摘「説明を理解するにはかなり視聴者側の推論が必要」）は
**この形を実例で示しましたが、数は出しませんでした** ——
「語彙の取り方で 24〜118回 に散る」ので再現しなかったからです。
残した宿題は **「語彙一覧を全部 書き出したうえで『この語彙で N回』と言うこと」**。

**語彙をコードに置けば、次の回は数え直しではなく比較から始められます。**
道具ごと消えると、また「散るから数えない」に戻ります。

## 2026-08-28 の実測（控え 555本・3,984コマ）

    狭い  1個以上 ** 95コマ（2.4%）／ 52本（ 9.4%）**  0個の本 503本
    広い  1個以上 **359コマ（9.0%）／125本（22.5%）**  0個の本 430本

**同じ物差しで並べた3つの説明**（`src/verify._check_ear_load` の docstring に全文）:

    コマが読み切れない   ショート 2.27秒/コマ → **88.5%**
    耳の負荷            5個以上 **13.4%** のコマ
    画面ごしの指示語     **2.4〜9.0%** のコマ   ← いちばん小さい

**だから検査は足していません**（`src/alerts.py`「一覧が当たりを含まないまま育つ」）。
覆る条件は `_check_ear_load` の docstring —— `slide_pace` が閉じても
1本あたり再生が動かず、耳の負荷でも動かないなら、残るのはここです。
そのときは**広い語彙で門を作ること**（語彙はここにあるので、数え直しは要りません）。

## 数え方の限界（**先に書いておく**）

- **控えは narration の文だけ**です（`data/critique_queue/*.json`）。
  画面に何が出ていたかは見ていないので、
  **「その語が実際に画面を要求していたか」は判定していません。**
  「一時停止して自分の行を見てください」のような**意図した指示**も数に入ります
  （実測の上位にそれが混ざっています）
- **語彙で数は動きます。** 狭い／広いの2本を出しているのはそのためで、
  **1本だけの数を引用しないこと**（2026-08-27 が踏んだのがそこです）
"""
from __future__ import annotations

import collections
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
QUEUE = ROOT / "data" / "critique_queue"

#: **画面の位置・見た目でしか指せない語。**耳だけでは指示対象が決まりません。
NARROW = (
    r"左端|右端|左側|右側|左から|右から|上の(?:ほう|方)|下の(?:ほう|方)"
    r"|真ん中|中央の|上から\d+|下から\d+|一番上|一番下|いちばん上|いちばん下"
    r"|(?:この|その|あの|こちらの)(?:線|棒|帯|矢印|枠|列|行|欄|軸|点|グラフ|図|表|色|部分|ところ)"
    r"|2つの線|2本の棒"
    r"|画面の|(?:図|表|グラフ)の(?:ように|とおり)|ご覧のとおり|見てのとおり"
    r"|(?:青|赤|緑|黄色|オレンジ|灰色|グレー)(?:い)?(?:の|い)?(?:線|棒|帯|部分|ところ|ほう|方)"
)

#: 狭いほうに、**図の部品を裸で指す語**を足したもの。
#: 「帯」「棒」は文脈しだいで抽象語にもなるので、**上ぶれ側の見積り**です。
WIDE = NARROW + r"|帯|棒グラフ|棒|グラフ|この表|その表|縦軸|横軸|凡例|矢印|色分け|ハイライト|太字|囲み"


def scripts() -> list[tuple[str, list[str]]]:
    """(動画ID, 読み上げの文の列)。控えが読めない回は空で返します。"""
    out: list[tuple[str, list[str]]] = []
    if not QUEUE.is_dir():
        return out
    for p in sorted(QUEUE.glob("*.json")):
        try:
            d = json.loads(p.read_text())
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        nar = [t for t in (d.get("narration") or []) if isinstance(t, str) and t.strip()]
        if nar:
            out.append((p.stem, nar))
    return out


def count(pattern: str, books: list[tuple[str, list[str]]]) -> dict:
    rx = re.compile(pattern)
    per_slide: list[int] = []
    per_book: dict[str, int] = {}
    words: collections.Counter = collections.Counter()
    for stem, nar in books:
        tot = 0
        for line in nar:
            hits = rx.findall(line)
            per_slide.append(len(hits))
            tot += len(hits)
            words.update(hits)
        per_book[stem] = tot
    return {"per_slide": per_slide, "per_book": per_book, "words": words}


def report_lines() -> list[str]:
    books = scripts()
    if not books:
        return ["  控えが1本も読めませんでした（`data/critique_queue/`）"]
    out = [f"控え {len(books)}本 / {sum(len(n) for _s, n in books)}コマ"]
    for name, pat in (("狭い", NARROW), ("広い", WIDE)):
        r = count(pat, books)
        sl, bk = r["per_slide"], r["per_book"]
        n = len(sl)
        srt = sorted(sl)
        out.append(f"[{name}] 中央値 {srt[n // 2]} / 平均 {sum(sl) / n:.2f} / 最大 {max(sl)}")
        for k in (1, 2, 3):
            ge = sum(1 for x in sl if x >= k)
            gb = sum(1 for v in bk.values() if v >= k)
            out.append(f"    {k}個以上: {ge:5d}コマ（{ge / n:5.1%}） / "
                       f"{gb:4d}本（{gb / len(bk):5.1%}）")
        out.append(f"    0個の本: {sum(1 for v in bk.values() if v == 0)}本"
                   f"   多い語: {r['words'].most_common(6)}")
    out.append("  **1本だけの数を引用しないこと**（語彙で動きます。docstring の「限界」）。")
    return out


if __name__ == "__main__":
    for line in report_lines():
        print(line)
