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


# ---------------------------------------------------------------- 折れ線（2026-09-19 13:3x）
# オーナー `9155fe09`「ナレーションとアニメーションの表現をリンクさせたりしないとわかりやすく
# なんないでしょ？**画面がある意味が文字だけになってんのどうにかしろよ**」——
# 在庫 42本 で図 302 のうち `table` が 173（57%）＝ **画面の半分以上が字を並べた絵**でした。
# `lines` は `viz.py` 冒頭の覆る条件 (2) が名指しで待っていた 4つ目 の形です。

LINES = {"kind": "lines", "title": "合計が並ぶのはいつか", "unit": "円",
         "x": {"unit": "歳", "from": 63, "to": 90},
         "series": [{"label": "63歳から", "at": 63, "per_month": 135600, "color": "orange"},
                    {"label": "65歳から", "at": 65, "per_month": 150000, "color": "blue"}],
         "cross": {"at": "83歳10か月"}}


def test_折れ線は通り交わる齢を自分で解く():
    assert viz.check(LINES) == []
    assert "83歳10か月" in viz.describe(LINES)
    assert abs(viz._cross_x(LINES["series"][0], LINES["series"][1]) - (65 + 226 / 12)) < 1e-6


def test_交わる齢が台本と合わなければ止める():
    """**本物の算数の門**（`waterfall` の start − steps ＝ end と同じ族）。
    ここが緩むと、声の言う齢と画面の点が別の所を指したまま焼けます。"""
    bad = {**LINES, "cross": {"at": "84歳10か月"}}
    assert any("計算では 83歳10か月" in m for m in viz.check(bad))
    assert any("cross.at が無い" in m for m in viz.check({**LINES, "cross": {}}))
    # 交わる所が横の端の外（＝ 画面に出ない）のも止める
    assert any("外" in m for m in viz.check({**LINES, "x": {"unit": "歳", "from": 63, "to": 70}}))
    # 同じ額なら追い越しません
    flat = {**LINES, "series": [dict(LINES["series"][0]), {**LINES["series"][1], "per_month": 135600}]}
    assert any("追い越しません" in m for m in viz.check(flat))


def test_歩は線の数ぷらす交わる所で手がかりは齢が先():
    assert viz.steps(LINES) == 3 == len(viz.step_keys(LINES))
    keys = viz.step_keys(LINES)
    assert keys[0][0] == "63歳から" and keys[1][0] == "65歳から"
    assert keys[2] == ["83歳10か月"]


def test_交わる所は最後の歩でだけ現れる():
    """**声が齢を言うまで、答えの点を出さないこと。** ここが崩れると、
    `frames_cued` が刻んでも「先に答えが出ている」絵に戻ります。"""
    size = (900, 460)
    two = viz.draw(LINES, size, 2 / 3 - 1e-6)     # 線 2本 まで
    one = viz.draw(LINES, size, 1 / 3 - 1e-6)     # 線 1本 だけ
    full = viz.draw(LINES, size, 1.0)
    assert list(one.getdata()) != list(two.getdata()) != list(full.getdata())

    # 交わる所（点・点線・齢の字）は**黄**。線は橙(220,150,40)と青なので、緑で分かれます。
    # 箱の背景まで数えないよう、色で拾うこと（帯で数えると黒い箱が 4万画素 入ります）。
    def marker(im):
        return sum(1 for p in im.getdata()
                   if p[3] > 60 and p[0] > 230 and p[1] > 195 and p[2] < 190)

    assert marker(one) == marker(two) == 0 < marker(full)


def test_前に出ている側は並び順ではなく数で決まる():
    """`series` を逆に書いても、塗りの色は**先に受け取っている側**のまま。"""
    size = (900, 460)
    a = viz.draw(LINES, size, 1.0)
    rev = {**LINES, "series": [LINES["series"][1], LINES["series"][0]]}
    b = viz.draw(rev, size, 1.0)

    # 交わる所より左の塗りは、どちらの書き方でも橙のほうが多い
    def hue(im):
        px = [p for p in im.crop((120, 200, 420, 420)).getdata() if p[3] > 60]
        return sum(1 for p in px if p[0] > p[2]) - sum(1 for p in px if p[2] > p[0])

    assert hue(a) > 0 and hue(b) > 0


def test_繰り上げの連作は山場に折れ線を持つ():
    """**このコマは 09/19 まで画面が字だけでした**（`show` と `board` だけ）。"""
    from studio import series_kuriage as k
    for fn in k.ALL:
        b = fn()
        res = [g for g in b["segments"] if g.get("tag") == "結論"][0]
        assert res["viz"]["kind"] == "lines"
        assert viz.check(res["viz"]) == []
        # 交わる齢の字が、声の中にそのまま在る（＝ `cue_windows` が当てられる）
        assert res["viz"]["cross"]["at"] in res["say"]
