"""動く図（`studio/viz.py`・オーナー 2026-09-17 20:4x・受け取り帳 `d699098f`）。

原文（**一字も変えないこと**）:

    「アニメーションとか画像でイメージしやすくって言ったのはさ、わかりにくい仕組みとか計算とかを
     動く表とかいろんなグラフとかあるいは何かを表したアニメーションとかにしないと意味ないでしょ。」

**この回に数えた事実**: それまで動く物は 1つも無く（16本・全部 1コマ 1枚 の静止画）、
09/16 の「部ごとの絵」は写真の背景でした。`Segment.viz` を書いた本だけが動き、
**書いていない本は 1コマも・指紋も 動きません**（陰性対照）。
"""
from pathlib import Path

from PIL import Image

from studio import critic, script as S, slides, viz

ROOT = Path(__file__).resolve().parents[1]

WF = {"kind": "waterfall", "title": "所得の出し方", "start": {"label": "年金", "value": 1800000},
      "steps": [{"label": "控除", "value": 1100000}], "end": {"label": "所得", "value": 700000}}
BARS = {"kind": "bars", "items": [{"label": "介護", "value": 75500}, {"label": "国保", "value": 62100}],
        "total": {"label": "あわせて", "value": 137600}}
TBL = {"kind": "table", "head": ["", "かかる所"], "rows": [["所得税", "残り"], ["国保", "ひとりいくら"]]}


def seg(say="あ", viz=None, board=()):
    return S.Segment(say=say, show="", sub="", tag="計算", board=list(board), viz=viz or {})


def test_オーナーの原文がrepoに在る():
    words = "動く表とかいろんなグラフとかあるいは何かを表したアニメーションとかにしないと意味ないでしょ"
    for rel in ("studio/viz.py", "docs/JOURNAL.md"):
        assert words in (ROOT / rel).read_text(encoding="utf-8"), f"原文が {rel} に無い"


def test_数の字():
    assert viz.fmt_num(1800000) == "180万円"
    assert viz.fmt_num(75500) == "7万5500円"
    assert viz.fmt_num(153300) == "15万3300円"
    assert viz.fmt_num(-12800) == "−1万2800円"
    assert viz.fmt_num(5000) == "5000円"
    assert viz.fmt_num(30, "%") == "30%"


def test_形の検査():
    assert viz.check(WF) == [] and viz.check(BARS) == [] and viz.check(TBL) == []
    assert any("kind" in p for p in viz.check({"kind": "pie"}))
    bad = dict(WF, end={"label": "所得", "value": 600000})
    assert any("合わない" in p for p in viz.check(bad)), "start − steps ≠ end を止めること"
    ten = dict(BARS, items=[{"label": "1.5倍", "value": 1}])
    assert any("点・小数" in p for p in viz.check(ten))
    # `Script.problems()` が同じ検査を呼ぶ（**止める**）
    s = S.Script(id="a", date="2026-09-20", title="x", takeaway="x", segments=[seg(viz={"kind": "pie"})] * 5)
    assert any("viz" in p for p in s.problems())


def test_動く絵の秒の合計はコマの秒数():
    fr = viz.frames(WF, 8.0, (980, 430))
    assert len(fr) > 5 and abs(sum(t for _, t in fr) - 8.0) < 1e-6
    # 1秒 に満たないコマは動かない（最後の絵 1枚）
    assert len(viz.frames(WF, 0.8, (980, 430))) == 1
    for sp in (WF, BARS, TBL):
        im = viz.draw(sp, (980, 430), 1.0)
        assert im.size == (980, 430) and im.mode == "RGBA"


def test_図の無い本は指紋も絵も動かない():
    kw = dict(date="2026-09-20", title="x", takeaway="x")
    a = S.Script(id="a", segments=[seg(), seg()], **kw)
    b = S.Script(id="a", segments=[seg(), seg()], **kw)
    assert a.build_sig() == b.build_sig() and a.loop_sig() == b.loop_sig()
    # 図を書くと、焼きの指紋も輪の指紋も動く（古い図の mp4 を「新しい」と言わないため）
    c = S.Script(id="a", segments=[seg(viz=WF), seg()], **kw)
    assert c.build_sig() != a.build_sig() and c.loop_sig() != a.loop_sig()
    d = S.Script(id="a", segments=[seg(viz=dict(WF, title="別の題")), seg()], **kw)
    assert d.build_sig() != c.build_sig()


def test_critiqueに図の字と数が渡る():
    s = S.Script(id="a", date="2026-09-20", title="x", takeaway="x", segments=[seg(viz=WF, board=["板の行"])])
    out = critic.critique_screen(s)
    assert "図（画面のまん中で動く）" in out and "180万円" in out and "70万円" in out
    # 図が在るコマは板の代わりに図が出る（画面と同じ）
    assert "板の行" not in out


def test_図はまん中に描かれ_無ければ前の絵のまま(tmp_path: Path):
    ov = viz.draw(BARS, (980, 430), 1.0)
    p = slides.slide("見出し", "", "字幕の文です。", 1, 3, None, tmp_path / "v.png", tag="計算", viz=ov)
    q = slides.slide("見出し", "", "字幕の文です。", 1, 3, None, tmp_path / "n.png", tag="計算")
    im, base = Image.open(p), Image.open(q)
    assert im.size == (1080, 1920)
    # 図の箱（y 600〜1080）の中は背景と違う色（黒い箱）・図の無い絵は背景のまま
    x, y = 540, 850
    assert im.getpixel((x, y))[:3] != base.getpixel((x, y))[:3]
    bg = slides.background(None).getpixel((x, y))
    assert all(abs(base.getpixel((x, y))[k] - bg[k]) <= 2 for k in range(3))


def test_動くコマは数枚になり最後の名は静止画と同じ(tmp_path: Path):
    fr = slides.slide_frames("所得 70万円", "", "計算すると。", 3, 10, None, tmp_path, 6.0, WF, tag="計算")
    assert len(fr) > 5
    assert fr[-1][0].name == "slide-03.png"
    assert abs(sum(t for _, t in fr) - 6.0) < 1e-6
    # 横でも描ける
    fr2 = slides.slide_frames("所得 70万円", "", "計算すると。", 3, 10, None, tmp_path / "l", 6.0, TBL, form="long") \
        if (tmp_path / "l").mkdir() is None else None
    assert fr2 and Image.open(fr2[-1][0]).size == (1920, 1080)
