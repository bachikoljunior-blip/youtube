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
from studio import asp

# **2026-09-18 20:3x（optimizer）: live の説明欄は `asp.compose()` を通った字です**
# （`studio/asp.py`・成果報酬の塊を `yt.upload` / `yt.update_meta` の口で足す）。
# **比べる側（`cli.drift_fields` / `cli.desc_appended`）も同じ字と比べます** ——
# 通さないと、上がっている本が毎周「食い違い」に見えて 50単位 の直しが空撃ちされます。
# だから、この検査の「live」側も塊を通します（**陽性対照は通したまま でも拾えること**で守ります）。


class _S:
    def __init__(self, title="題です", description="説明です\n", tags=("あ", "い")):
        self.title, self.description, self.tags = title, description, list(tags)


_MISSING = object()


def _rd(s, *, title=None, description=_MISSING, tags=None):
    if description is _MISSING:
        live = asp.compose(s.description)
    elif description is None:
        live = None                      # 欄そのものが欠けている（空として比べる）
    else:
        live = asp.compose(description)
    return {
        "title": s.title if title is None else title,
        "description": live,
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


def test_欠けた欄は空として比べる(monkeypatch):
    """**欄の欠けだけを見る** —— 成果報酬の塊を外して（案件 0本）、正規化の側だけを残す。"""
    monkeypatch.setattr(asp, "OFFERS", [])
    s = _S(description="")
    assert cli.drift_fields(_rd(s, description=None), s) == []


def test_欄が欠けていれば_塊が在る限り食い違い():
    """**2026-09-18 20:3x の新しい線**（`studio/asp.py`）。

    台本の説明欄が空でも、上げるつもりの字は**塊のぶん だけ在ります** ——
    live に何も無い本は「まだ成果報酬のリンクが入っていない本」＝ **`asp` で入れ直す相手**です
    （`cli.cmd_asp --published`）。ここが `[]` に戻ったら、入れ直す相手を数える口が消えます。
    """
    s = _S(description="")
    assert cli.drift_fields(_rd(s, description=None), s) == ["説明欄"]
