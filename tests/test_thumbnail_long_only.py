"""**毎周の自動の押し直しは、長尺だけであること**（2026-08-28）。

## なぜこの検査が要るか

`scripts/batch_build._push_thumbnails_first()` は長らく
`refresh_thumbnail.push_missing()` を**素で**呼んでいました。
ショートを止めていたのは `upload_cap.thumbnail_yield_to_schedule()` の
**「予約に0本の日があるあいだは押さない」門だけ**です。

**あれは代理の理由です。** 言っているのは「同じ50単位の行き先が他に在る」で、
「ショートにサムネイルは効かない」ではありません。実測 2026-08-28:

    予約の穴          10/11 の **1日だけ** ＝ 埋めるのに要るのは `--move` 1回
    門の文面          「同じ単位で**詰め直しが 70本**できます」
    `--spread` の答え 「1日 10本を超えている日はありません」  ← **70本 の行き先が無い**

つまり**穴が1つ埋まった瞬間に門は開き、ショート 58本 ＝ 2,900単位**が
毎周の自動の口から黙って出ていきます。単位は投稿（`videos.insert`）と
詰め直し（`videos.update`）と分け合うので、**投稿が止まりえます。**

本当の理由は面のほうです（`scripts/refresh_thumbnail.LONG_FORM_SEC` の上の註）——
再生の 99.9% は `SHORTS_FEED`（サムネイルの出ない面）で、
門2a（4,000時間）に入る長尺だけが **CTR で縛られている**（実測 1.44% / 要る 19.2%）。

**この検査が赤いときは、その門がまた穴の有無に依存しています。**

**覆る条件**: `SHORTS_FEED` 以外の面が再生の1割を超えたら、この検査ごと畳むこと。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import batch_build  # noqa: E402


class _Spy:
    """`push_missing` の呼ばれ方だけを覚える。API は1回も叩きません。"""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def push_missing(self, *args, **kwargs) -> int:
        self.calls.append({"args": args, "kwargs": kwargs})
        return 0


def _run(monkeypatch, spy: _Spy) -> None:
    monkeypatch.setitem(sys.modules, "refresh_thumbnail", spy)
    monkeypatch.setattr(batch_build.upload_cap, "day_quota",
                        lambda *a, **k: type("Q", (), {"open": True})())
    batch_build._push_thumbnails_first()


def test_毎周の押し直しは長尺だけ(monkeypatch):
    spy = _Spy()
    _run(monkeypatch, spy)
    assert len(spy.calls) == 1, "1回だけ呼ぶこと"
    call = spy.calls[0]
    only_long = call["kwargs"].get("only_long")
    if only_long is None and call["args"]:
        # 位置引数で渡す形になったら、3番目が only_long（署名どおり）
        only_long = call["args"][2] if len(call["args"]) > 2 else None
    assert only_long is True, (
        "毎周の自動の口は長尺だけ。素の push_missing() に戻すと、"
        "穴が1つ埋まった回にショート数十本ぶんの単位が黙って出ていきます"
    )


def test_日枠が閉じていれば押さない(monkeypatch):
    """**元からある門は壊していないこと。** 観測ずみで閉じている窓では撃たない。"""
    spy = _Spy()
    monkeypatch.setitem(sys.modules, "refresh_thumbnail", spy)
    monkeypatch.setattr(batch_build.upload_cap, "day_quota",
                        lambda *a, **k: type("Q", (), {"open": False})())
    monkeypatch.setattr(batch_build.upload_cap, "worth_a_try", lambda *a, **k: False)
    batch_build._push_thumbnails_first()
    assert spy.calls == [], "閉じている窓では1回も呼ばないこと"
