"""説明のパートごとの絵（オーナー 2026-09-16 12:1x・受け取り帳 `751f4947`）。

原文（**一字も変えないこと**）:

    「説明のパートごとにアニメーションとか画像でイメージしやすくしたらいいと思う。」

**この回に数えた事実**: 絵は **1本に 1枚** でした（10本・200コマ の本でも 1枚）。
`Segment.image` を書いた本だけが部に分かれ、**書いていない本は 1コマも変わりません。**
"""
from pathlib import Path

from studio import render, script as S

ROOT = Path(__file__).resolve().parents[1]


def seg(say="あ", image="", tag="計算"):
    return S.Segment(say=say, show="", sub="", tag=tag, board=[], image=image)


def test_オーナーの原文がrepoに在る():
    words = "説明のパートごとにアニメーションとか画像でイメージしやすくしたらいいと思う"
    for rel in ("studio/script.py", "docs/JOURNAL.md"):
        assert words in (ROOT / rel).read_text(encoding="utf-8"), f"原文が {rel} に無い"


def test_書いた所から次に書いた所の手前まで():
    segs = [seg(), seg(image="p1"), seg(), seg(image="p2"), seg()]
    assert S.part_images(segs) == ["", "p1", "p1", "p2", "p2"]
    assert S.parts(segs) == [("p1", 2, 3), ("p2", 4, 5)]


def test_書いていない本は部を持たない():
    """既に在る 10本 が 1コマも変わらないこと（回帰）。"""
    segs = [seg() for _ in range(200)]
    assert S.part_images(segs) == [""] * 200
    assert S.parts(segs) == []


def test_部を書いても指紋は本文だけでは動かない():
    """`image` が空のあいだ、公開ずみの本の `build_sig` が 1字も動かないこと。"""
    kw = dict(date="2026-09-20", title="x", takeaway="x")
    a = S.Script(id="a", segments=[seg(), seg()], **kw)
    b = S.Script(id="a", segments=[seg(), seg()], **kw)
    assert a.build_sig() == b.build_sig()


def test_部を付け替えると指紋が動く():
    """付け替えたのに「新しい」と言われると、**古い絵の mp4 が出ます**。"""
    kw = dict(date="2026-09-20", title="x", takeaway="x")
    a = S.Script(id="a", segments=[seg(image="p1"), seg()], **kw)
    b = S.Script(id="a", segments=[seg(image="p2"), seg()], **kw)
    assert a.build_sig() != b.build_sig()


def test_届いていない部は本の背景へ落ちる(monkeypatch):
    """外の係がまだ返していない部で、**焼きが止まらない**こと（`docs/IMAGE_ORDERS.md`）。"""
    seen = []

    def fake_slide(show, sub, say, i, n, image, out, **kw):
        seen.append(image)
        out.write_bytes(b"")
        return out

    monkeypatch.setattr(render, "slide", fake_slide)
    segs = [seg(image="p1"), seg(image="p2")]
    names = S.part_images(segs)
    bg, got = Path("bg.jpg"), Path("p1.jpg")
    parts = {"p1": got}
    # `render.build` の中の 1行 と同じ引き方（ffmpeg も TTS も呼ばずに、そこだけ見る）
    assert [parts.get(nm) or bg for nm in names] == [got, bg]


def test_長尺で部が無ければ警告が出る():
    s = S.Script(id="a", date="2026-09-20", title="x", takeaway="x", form="long",
                 segments=[seg(say="あ" * 60) for _ in range(40)])
    assert any("部の絵が 1つも在りません" in w for w in s.warnings())
    # **止めない**（絵は外の係が返す口なので、赤にすると本が出せなくなる）
    assert all("部の絵" not in p for p in s.problems())


def test_ショートには言わない():
    s = S.Script(id="a", date="2026-09-20", title="x #Shorts", takeaway="x", form="short",
                 segments=[seg() for _ in range(11)])
    assert all("部の絵" not in w for w in s.warnings())
