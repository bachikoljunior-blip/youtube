"""**成果報酬のリンク（ASP）を、出す本の説明欄に入れる一点**（**API 0単位**）。

**2026-09-18 20:3x・optimizer・1周 1体 が書いた**（JOURNAL 同刻）。

**なぜ在るか（固定2 の答えの、ただ 1本 の道）**:
期限（12/13）までに 月20万 に届く道は、測った範囲で **門（YPP）の外の 2つ だけ**です
（広告は登録 37人 → 1,000人 が要り、登録/日 の中央 1.6人 では約600日 ＝ 期限の外）。
その 2つ のうち **企業案件は相手の yes が要り**、**成果報酬だけが こちらの台本と説明欄で動きます**
（`docs/FOR_OWNER.md` §3・`studio/trend.perf_need_rate`）。
**2026-09-18 15:4x の訊き `asp_link` は 20:2x に返りました**（`data/studio/asp_links.json`）。
**それまで、こちらの側の率は構造的に 0 でした** —— 説明欄の行き先は 国税庁・区役所・年金機構 だけで、
**こちらの取り分になるリンクが 1本 もなかった** ＝ 再生が何回 来ても分子は 0 のまま。
**この file が、その 0 を 0 でなくします。**

**門は 1か所 です**: `compose()` だけが説明欄に足します。撃つ所は 2つ（`yt.upload` と `yt.update_meta`）で、
**どちらも API の口そのもの** ＝ 「足し忘れた本」が構造として出ません。
比べる側（`cli.drift_fields` / `cli.desc_appended`）も同じ `compose()` を通した字と比べます
（通さないと、上げた本が毎周「食い違い」に見えて 50単位 の直しが空撃ちされます）。

**置き場所は 説明欄の いちばん上**（2026-09-18 20:3x の決め）。理由: スマホの説明欄は
**「…もっと見る」より上の 2行 しか出ません**。下に置くと、開いた人にしか届かない。
**覆る条件（この決めが覆る数）**:
 (1) 上に置いた本の 24h 中央が、置いていない本（09/18 の年金連作 5本・中央 369回）の **半分 未満**なら、
     題材の差ではなく**この塊が配りを削っている** ＝ 下（末尾）へ移すこと。`compose(top=False)` で足りる。
 (2) **成果が 30日 で 0件 なら**、リンクの置き場所ではなく**当てている案件**を疑うこと
     （いまは FP・保険の無料相談 2本。楽天は入れていない —— 成果 2%（購入完了）は
      1件あたり 数十円で、月20万 の分子に数えられる大きさではないため。
      数えられるのは `hoken_total_professional` ¥13,800 と `fp_no_madoguchi` ¥5,000 の 2本 だけで、
      **月20万 ＝ ¥13,800 なら 15件/月・¥5,000 なら 40件/月**）。
 (3) **`youtube_ok` が false の案件が来たら**、その案件は `OFFERS` に入れないこと（規約違反は口ごと失います）。

**表示の決まり（景表法・ステマ規制 2023-10〜）**: 広告であることを、平の人が分かる字で、
リンクと同じ塊に書くこと。**`【PR】` と「アフィリエイト」の 2語 を必ず出します**（検査 `tests/test_studio_asp.py`）。
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINKS = ROOT / "data/studio/asp_links.json"

#: この塊が在るかを見分ける印（**足し直しを 1度 に保つ**）。字を変えると、
#: 既に上げた本が「まだ入っていない」側に見えます —— 変えるときは retrofit を撃ち直すこと。
MARK = "【PR】"
#: リンクの見分け（印の字を変えた回でも、二重に足さないための 2つ目の目）。
HOST = "af.moshimo.com"

#: 説明欄に出す案件（**順は 1件あたりの額の高い順** ＝ 上の行ほど押される）。
#: `data/studio/asp_links.json` の `id` で引く。**ここに無い id は出しません**（上の覆る条件 (2)）。
OFFERS = [
    ("hoken_total_professional", "老後のお金と保険を、専門家（FP）に無料で相談できます"),
    ("fp_no_madoguchi", "保険を売らない中立のFPに相談したい方はこちら（無料）"),
]

DISCLOSURE = ("※上の2つは広告（アフィリエイト）です。相談は無料で、申し込みがあると"
              "このチャンネルに紹介料が入ります。動画の数字は公的な資料だけで計算していて、"
              "紹介料とは関係ありません。")


def links() -> dict[str, dict]:
    """`data/studio/asp_links.json` の `id` → 行。**無ければ空**（この file は止めません）。"""
    try:
        raw = json.loads(LINKS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {r["id"]: r for r in raw.get("links", []) if r.get("url")}


def offers() -> list[tuple[str, str]]:
    """出せる案件（`OFFERS` の順・`youtube_ok` が false の物は落とす）→ [(url, 一行)]。"""
    have = links()
    out = []
    for oid, line in OFFERS:
        r = have.get(oid)
        if not r or r.get("youtube_ok") is False:
            continue
        out.append((r["url"], line))
    return out


def block() -> str:
    """説明欄に入れる塊。**案件が 1本 も無ければ空**（＝ `compose` は素通し）。"""
    got = offers()
    if not got:
        return ""
    head = f"{MARK}この動画は一般的な例です。自分の場合いくらになるかを相談したい方へ"
    body = "\n".join(f"・{line}\n{url}" for url, line in got)
    return f"{head}\n{body}\n{DISCLOSURE}"


def has_block(desc: str | None) -> bool:
    """もう入っているか（印か、リンクの host のどちらかが在れば入っている）。"""
    d = desc or ""
    return MARK in d or HOST in d


#: YouTube の説明欄の上限（字）。**越えると `videos.insert` / `videos.update` が 400 で落ちます**
#: ＝ **落ちるのは塊ではなく、その本の予約そのもの**（1,650単位 が無駄になる）。
#: いまいちばん長い台本は 3,459字（`2026-09-18-minou-ushinau-3tsu`）＋ 塊 345字 ＝ 3,804字 で、
#: **余りは 1,200字** あります。この蓋は「まだ踏んでいない所に置いた門」です（`docs/GOAL.md` の教訓 1つ目）。
LIMIT = 5000


def compose(desc: str | None, top: bool = True) -> str:
    """説明欄に成果報酬の塊を入れた字を返す。**冪等**（2度 呼んでも 1つ）。

    `top=True`（既定）＝ いちばん上（スマホで「もっと見る」より上に出る側）。
    **上限を越えるときは、塊ではなく台本の側の尻を行の切れ目で落とします** ——
    塊を落とすと、その本だけ分子が 0 になるため（落とした時は末尾に `…`）。
    """
    d = (desc or "").strip()
    b = block()
    if not b or has_block(d):
        return d[:LIMIT]
    if not d:
        return b
    room = LIMIT - len(b) - 2
    if len(d) > room:
        cut = d[:max(0, room - 1)]
        nl = cut.rfind("\n")
        d = (cut[:nl] if nl > room // 2 else cut).rstrip() + "…"
    return f"{b}\n\n{d}" if top else f"{d}\n\n{b}"
