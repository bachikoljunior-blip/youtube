#!/usr/bin/env python3
"""`retro.py` が **§6 (a2) の節を拾えること**（2026-08-15）。

**なぜこの検査が要るか。** 拾えなくなっても、`retro.py` は落ちません。
**「0 件」と静かに出るだけ**です。そして 0 件は「見直しを書いていない回が
続いている」とも読めるので、**壊れていることに気づけません。**
8/15 に (a2) の答えが6件積まれたまま誰にも読まれていなかったのと、同じ形です。

拾えなくなる道は2つあって、どちらも現実に起きています。

1. **見出しの揺れ。** 6件のうち実際に3通りありました ——
   「この回の設計の見直し（§6 (a2)）」「この回の見直し（§6 a2）」
   「設計の見直し（§6 (a2)）」。見出しは 2026-08-15 に1行へ固定しましたが、
   **過去のぶんが読めなくなると、縦に並べる意味そのものが消えます**
   （1回ぶんの (a2) には値打ちがなく、並べて初めて癖が出る）
2. **問い4の印。** `[道筋]` を見落とすと、いつまでも「まだ1度もない」と言い続け、
   毎回「道筋を見ろ」と出ます。**毎回出る指示は読まれなくなります。**
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import retro  # noqa: E402

# 実際に日誌にあった3通り＋固定後の1行。
HEADINGS = [
    "### この回の設計の見直し（§6 (a2)）",
    "### この回の見直し（§6 a2）",
    "### 設計の見直し（§6 (a2)）",
]


def _doc(heading: str, body: str) -> str:
    return f"## 2026-08-15 19:0x〜 — 題\n\n{heading}\n\n{body}\n\n### 次の回へ\n\n1. 何か\n"


def test_拾える見出しは3通りとも():
    for h in HEADINGS:
        blocks = retro.blocks_under(_doc(h, "1. **生成の待ち**ですが、手順のせい"), retro.REVIEW_RE)
        assert len(blocks) == 1, h
        assert blocks[0][0].startswith("2026-08-15"), h


def test_問い1の1行目だけを返す():
    body = [
        "1. **いちばん時間を食ったのは生成の80分**（7本ぶん）。**対象のせい**",
        "   1本あたり約11分で、内訳は台本のLLM・音声合成。",
        "2. **手順どおりにやって間違ったところが1つ。**",
    ]
    got = retro.first_lines(body, "1")
    assert got.startswith("**いちばん時間を食ったのは生成の80分**")
    # 続きの行（字下げされた説明）を巻き込まない。
    assert "1本あたり約11分" not in got
    assert retro.first_lines(body, "2").startswith("**手順どおりに")
    assert retro.first_lines(body, "4") == ""


def test_次の回へと取り違えない():
    """(a2) の節を数えるつもりで「次の回へ」を数えていたら、道筋の間隔が狂います。"""
    doc = _doc(HEADINGS[0], "1. 何か")
    assert len(retro.blocks_under(doc, retro.REVIEW_RE)) == 1
    assert len(retro.handoff_blocks(doc)) == 1
    assert retro.REVIEW_RE.match("### 次の回へ") is None
    assert retro.HANDOFF_RE.match(HEADINGS[0]) is None


def test_道筋の印を見つける():
    doc = _doc(HEADINGS[2], "1. 何か\n4. いまの道筋は最短ではない。 `[道筋]`")
    (_, body, _s), = retro.blocks_under(doc, retro.REVIEW_RE)
    assert any(retro.ROUTE_MARK in line for line in body)
    plain = _doc(HEADINGS[2], "1. 何か")
    (_, body2, _s2), = retro.blocks_under(plain, retro.REVIEW_RE)
    assert not any(retro.ROUTE_MARK in line for line in body2)


# ---------------------------------------------------------------------------
# **太字の始まる位置で項目を落とさないこと**（2026-08-18。申し送り9）
#
# 日誌の項目は2通りで書かれています。`ITEM_RE` は長らく後者を
# 項目として認識せず、前の回を「問い1に答えていない回」と数えました。
# **中身ではなく、`**` が番号の前か後かだけの違いです。**
# ---------------------------------------------------------------------------


def test_item_re_reads_bold_before_the_number() -> None:
    body = ["**1. いちばん重かったのは題材決め**", "つづき"]
    # **`*` は落としません。** 落とすと、既に通っている `1. **…**` の側の
    # 表示が変わります（`test_問い1の1行目だけを返す` が固定している形）。
    # 直したいのは「項目として見えるか」だけで、見た目はそのまま。
    assert retro.first_lines(body, "1") == "いちばん重かったのは題材決め**"


def test_item_re_reads_bold_after_the_number() -> None:
    """**こちらは前から通っていました。** 直した回が壊していないこと。"""
    body = ["1. **いちばん重かったのは検査**"]
    assert retro.first_lines(body, "1") == "**いちばん重かったのは検査**"


def test_item_re_keeps_plain_items() -> None:
    assert retro.first_lines(["3. ただの文"], "3") == "ただの文"
    assert retro.first_lines(["3. ただの文"], "1") == ""


def test_bold_item_starts_a_new_item() -> None:
    """切り出しの側も同じ穴です —— **前の項目の続きとして飲み込みます。**"""
    body = ["1. さいしょ", "  つづき", "**2. つぎ**", "3. みっつめ"]
    got = retro._items(body) if hasattr(retro, "_items") else None
    if got is None:                      # 名前が変わったら、拾える形だけ見る
        assert retro.first_lines(body, "2") == "つぎ**"
    else:
        assert len(got) == 3
