"""**`OUTSIDE_LONG_RULE` は3つ命じているのに、数えていたのは (1) だけでした。**

`src/script_writer.OUTSIDE_LONG_RULE` は「外の同じ帯で今年いちばん見られている
長尺の形を写す」ために3つを命じています:

    (1) 冒頭 90秒（最初の 4コマ）を外の上位4本の順で
    (2) 章を5〜7つ・章ごとに判断を1つ・章ごとに**別の**表を chart か table で
    (3) 締めは「自分の場合の数字を出す手順」を3つ、順に

**数えていたのは (1) だけ**（`outside_opening_problems`）。(2)(3) は文章の指示のまま
`generate()` に渡って終わりでした。ところが `outside_opening_problems` の docstring 自身が
なぜ数えるかを書いています —— **「文章の指示は守られない（`generate()` の実測
2026-08-09）ので、数える」**。**同じ理由が (2)(3) にもそのまま当たります。**
片方だけ数えたのは、(1) が外れた本（`6PKux5HNnUE`）を実際に見たからで、
(2)(3) が守られている証拠が在ったからではありません。

## この検査は「いま在る本を落とすため」ではありません

実測（2026-09-04・`style: outside_long` の3本すべて）:

    Ec-j1-W4nqw（09/05 に出る本）  (1) [] ／ (2)(3) []
    1huadpEk6HY（09/04 に公開ずみ） (2)(3) []
    6PKux5HNnUE                    (2)(3) []

**次の本が黙って落とすのを止めるための検査です。**

## 踏んだ所（**最後の章に表を求めない**）

最初に書いた形は、`1huadpEk6HY` / `6PKux5HNnUE` の末尾の章
「自分の数字に置き換える」を「chart も table も無い」で鳴らしました。
**あれは規則 (3) の締めの章**で、手順だけなのが正しい形です。
冒頭の章（`outside_opening_problems` の持ち場）と末尾の章は、表を求めません。
"""
from __future__ import annotations

import json

from src import script_writer as sw


def _seg(narration: str, kind: str | None = None, headline: str = ""):
    v = {"kind": kind, "headline": headline} if kind else {"kind": "stat", "headline": headline}
    return {"narration": narration, "visual": v}


def _script(n_body: int = 6, *, tables: bool = True, closing: bool = True,
            dup: bool = False):
    """章ごとに 2コマ の台本を組む（先頭＝冒頭の章・末尾＝締めの章）。"""
    segs = [_seg("こんにちは。"), _seg("皆さん、どうでしょうか。")]
    chapters = [{"segment_index": 0, "label": "冒頭"}]
    for i in range(n_body):
        chapters.append({"segment_index": len(segs), "label": f"章{i}"})
        head = "同じ表" if dup else f"表{i}"
        segs.append(_seg(f"{i}章の話です。", "table" if tables else None, head))
        segs.append(_seg(f"{i}章の判断です。"))
    chapters.append({"segment_index": len(segs), "label": "締め"})
    segs.append(_seg("自分の場合の数字を出す手順は三つです。順に読んでください。"
                     if closing else "おわりです。"))
    return {"segments": segs, "chapters": chapters}


def test_規則どおりなら何も言わない():
    assert sw.outside_body_problems(_script(6)) == []


def test_本題の章が少なければ鳴る():
    # `_script(3)` は 冒頭 ＋ 本題3 ＋ 締め ＝ 数えるのは 4つ（冒頭の章だけを除く）
    hits = sw.outside_body_problems(_script(3))
    assert any("冒頭を除く章が 4つ" in h for h in hits)


def test_本題の章が多すぎても鳴る():
    hits = sw.outside_body_problems(_script(9))
    assert any("冒頭を除く章が 10つ" in h for h in hits)


def test_表の無い章で鳴る():
    hits = sw.outside_body_problems(_script(6, tables=False))
    assert sum("chart も table も無い" in h for h in hits) == 6


def test_同じ表を2つの章で使うと鳴る():
    hits = sw.outside_body_problems(_script(6, dup=True))
    assert any("2つで使っている" in h for h in hits)


def test_締めの手順が無ければ鳴る():
    hits = sw.outside_body_problems(_script(6, closing=False))
    assert any("締めの手順が無い" in h for h in hits)


def test_冒頭の章と締めの章には表を求めない():
    """**踏んだ所。** 末尾の章は規則 (3) の手順だけで、表が無いのが正しい。"""
    s = _script(6)
    # 冒頭・締めのコマから visual の種類を落としても、その2章では鳴らない。
    for seg in (s["segments"][0], s["segments"][-1]):
        seg["visual"] = {"kind": "stat", "headline": ""}
    hits = sw.outside_body_problems(s)
    assert not any("冒頭" in h or "締め" in h for h in hits if "chart" in h)


def test_章が書かれていない台本には何も言わない():
    """読めないものは通す（`house_rule.needs_beyond_rule()` と同じ姿勢）。"""
    s = _script(6)
    s.pop("chapters")
    hits = sw.outside_body_problems(s)
    assert all("章" not in h or "末尾" in h for h in hits)


def test_実物の_outside_long_3本が全部通る():
    """**実物で撃つこと。** 落とすために足したのではないと、ここで言えます。"""
    from src import config

    tops = {str(t.get("id")): t.get("style")
            for t in (config.load_topics().get("topics") or [])}
    root = config.ROOT / "data" / "critique_queue"
    seen = 0
    for meta in sorted(root.glob("*.json")):
        if meta.name.endswith(".script.json") or meta.name.endswith(".plan.json"):
            continue
        try:
            m = json.loads(meta.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if tops.get(str(m.get("topic") or "")) != "outside_long":
            continue
        script = root / f"{meta.stem}.script.json"
        if not script.is_file():
            continue
        d = json.loads(script.read_text(encoding="utf-8"))
        seen += 1
        assert sw.outside_body_problems(d) == [], f"{meta.stem} で鳴りました"
    assert seen >= 1, "outside_long の控えが1本も見つかりません"
