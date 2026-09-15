# -*- coding: utf-8 -*-
"""`cli.drift_fields` —— **YouTube は題と説明欄の前後の空白を落として返す**。

2026-09-16 00:5x（optimizer・Fable・ultracode）に足した。実測: 長尺 8本目 `avMVePkF758` で
渡した説明欄 1,677字 → 返り 1,676字（**差は末尾の改行 1字 だけ**）。それまで生の文字列で
比べていたので、`verify_meta` が `update_meta` を **2回（100単位）撃って 120秒 待ち**、
それでも「まだ食い違う」と書き残していた ＝ **直せない差を直しに行っていた**。

**陽性対照つき**（正規化が効きすぎていないこと ＝ 中身の違いは今も拾うこと）。
"""
from __future__ import annotations

import studio.cli as cli


class _S:
    def __init__(self, title="題です", description="説明です\n", tags=("あ", "い")):
        self.title, self.description, self.tags = title, description, list(tags)


def _rd(s, *, title=None, description=None, tags=None):
    return {
        "title": s.title if title is None else title,
        "description": s.description if description is None else description,
        "tags": [t[:30] for t in s.tags[:15]] if tags is None else tags,
    }


def test_末尾の改行だけの差は食い違いにしない():
    s = _S(description="本文\n※ 註\n")
    assert cli.drift_fields(_rd(s, description="本文\n※ 註"), s) == []


def test_題の前後の空白も落とす():
    s = _S(title="  題です  ")
    assert cli.drift_fields(_rd(s, title="題です"), s) == []


def test_一致している本は0件():
    s = _S()
    assert cli.drift_fields(_rd(s), s) == []


def test_陽性対照_中身が違えば今も拾う():
    """**正規化が効きすぎていないこと。** ここが空で返ったら、門は死んでいる。"""
    s = _S(description="本文A\n")
    assert cli.drift_fields(_rd(s, description="本文B\n"), s) == ["説明欄"]
    assert cli.drift_fields(_rd(s, title="別の題"), s) == ["題"]
    assert cli.drift_fields(_rd(s, tags=[]), s) == ["tags"]


def test_陽性対照_真ん中の改行は落とさない():
    """前後だけを落とす。**間の改行を潰したら、別の食い違いが見えなくなる。**"""
    s = _S(description="上\n\n下\n")
    assert cli.drift_fields(_rd(s, description="上\n下"), s) == ["説明欄"]


def test_欠けた欄は空として比べる():
    s = _S(description="")
    assert cli.drift_fields(_rd(s, description=None), s) == []
