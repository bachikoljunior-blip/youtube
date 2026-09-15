"""形（form）—— 縦のショートと、横の長尺（2026-09-14 14:2x・optimizer・Opus）。

`docs/GOAL.md` (4-g) 2 の申し送り（**長尺の型を `studio/` に足すのは `optimizer` の持ち場**）で足した枠。
理由: 収益化の門は 2つ あり、**ショートの再生は「4,000時間」の側に 1秒も数えられません**
（(a) 10,000,000回 対 (b) 4,000時間 ＝ 10分・維持 40% で約 60,000回 ＝ **(a) の 1/167**）。

**この検査のいちばんの仕事は陰性対照のほうです** —— 既定（`short`）の答えが 1つも動いていないこと。
公開ずみ 9本 ＋ 予約前 1本 の `build_sig` / `loop_sig` / `problems()` は、この回に撃って
**10本 とも同じ**でした（JOURNAL 2026-09-14 14:2x）。ここではその性質を、道具の側で挟みます。

**2か所に同じ数を置かないこと** —— 画面の寸法は `script.Form.size` と `slides.Geom` の両方に出るので、
下の `test_形と幾何は同じ数を指す` がずれた瞬間に落ちます。
"""
from pathlib import Path

from PIL import Image

from studio import cli, render, script, slides


def _script(form="short", n_segs=6, say="あ" * 40, title=None) -> script.Script:
    if title is None:
        title = "t #Shorts" if form == "short" else "t"
    return script.Script(id="t-form", date="2026-09-15", title=title, takeaway="t",
                         form=form, segments=[script.Segment(say=say, show="x") for _ in range(n_segs)])


# ---- 既定は short（陰性対照。ここが落ちたら公開ずみの本の答えが動いています） ----------------

def test_形を書かない台本はshort():
    s = script.Script(id="t", date="2026-09-15", title="t #Shorts", takeaway="t",
                      segments=[script.Segment(say="あ") for _ in range(5)])
    assert s.form == "short"
    assert script.form_of(s.form) is script.SHORT


def test_形だけが違う2本は別の指紋():
    """`build_sig` へ形を足しても `short` の指紋は 1字も変わらないこと（足し方を変えると
    公開ずみ 9本 の焼き直し待ちが**偽で**立つ）。そして `long` は必ず別の指紋。"""
    assert _script("short", 6).build_sig() != _script("long", 30).build_sig()


def test_shortの門は前のまま():
    assert script.SHORT.max_seconds == script.MAX_SECONDS == 95.0
    assert script.SHORT.min_seconds == 0.0          # ショートに下限は無い
    assert script.SHORT.chars_proxy == script.MAX_TOTAL_CHARS == 480
    assert script.SHORT.segments == (5, 16)
    assert script.chars_gate("まだ焼いていない本")[0] == script.MAX_TOTAL_CHARS


# ---- 長尺の門 -------------------------------------------------------------------------

def test_longの秒数は4分から10分():
    assert script.LONG.min_seconds == script.LONG_MIN_SECONDS == 240.0
    assert script.LONG.max_seconds == script.LONG_MAX_SECONDS == 1800.0


def test_字数の代理は秒数から引く():
    """**2度 書かないこと** —— 代理は `MAX_TOTAL_CHARS`（95秒 の代理）を秒で伸ばしたもの。"""
    assert script.LONG.chars_proxy == int(script.MAX_TOTAL_CHARS * 1800.0 / 95.0)
    assert script.chars_gate("まだ焼いていない本", form="long")[0] == script.LONG.chars_proxy
    # 助言文は、その形の秒数を言う（`short` の 95秒 を言い残さない）
    assert "1800秒" in script.chars_gate("まだ焼いていない本", form="long")[1]


def test_longの字数の門はその本の実測から引く():
    rows = [{"event": "built", "id": "t-form", "chars": 9000, "seconds": 1800.0}]   # 5.0字/秒
    gate, why = script.chars_gate("t-form", rows, form="long")
    assert gate == int(5.0 * 1800.0 * (1 - script.BUILD_JITTER))
    assert "実測" in why


def test_longに_Shorts_を付けると鳴る():
    """陽性対照 —— 長尺に #Shorts を付けると、YouTube はショートの棚へ入れ、
    4,000時間 の扉に 1秒も数えられません（この形を足した当の理由）。"""
    bad = [p for p in _script("long", 30, title="t #Shorts").problems() if "#Shorts" in p]
    assert len(bad) == 1, bad
    assert "ショートの棚" in bad[0]


def test_longは_Shorts_が無くても鳴らない():
    assert not [p for p in _script("long", 30).problems() if "#Shorts" in p]


def test_shortは_Shorts_が無いと鳴る():
    assert [p for p in _script("short", 6, title="t").problems() if "#Shorts" in p]


def test_コマ数の範囲は形ごと():
    assert [p for p in _script("short", 20).problems() if "コマ数" in p]      # short は 16 まで
    assert not [p for p in _script("long", 20).problems() if "コマ数" in p]   # long は 20 から
    assert [p for p in _script("long", 10).problems() if "コマ数" in p]


def test_longには字数の下限が在る():
    """4分 の代理（1,010字）を下回ったら鳴る。**足りないのは尺**。"""
    floor = int(script.MAX_TOTAL_CHARS * 240.0 / 95.0)      # 1,212字 ＝ 240秒 × 5.05字/秒
    low = [p for p in _script("long", 20, say="あ" * 40).problems() if "下限" in p]   # 800字
    assert len(low) == 1 and str(floor) in low[0]
    assert not [p for p in _script("long", 35, say="あ" * 40).problems() if "下限" in p]   # 1,400字


def test_知らない形は鳴る():
    assert [p for p in _script("tate").problems() if "form" in p]
    assert script.form_of("tate") is script.SHORT      # 黙って落とさず、縦で焼く


# ---- 画面の幾何 -----------------------------------------------------------------------

def test_形と幾何は同じ数を指す():
    """`script.Form.size` と `slides.Geom` に同じ寸法が 2度 出るので、ずれたら落とす。"""
    for name, f in script.FORMS.items():
        g = slides.geom_of(name)
        assert f.size == (g.w, g.h), (name, f.size, (g.w, g.h))


def test_縦の数は動いていない():
    """陰性対照 —— `SHORT` は module の定数そのもの（写しがずれたら落ちる）。"""
    assert (slides.SHORT.w, slides.SHORT.h) == (slides.W, slides.H) == (1080, 1920)
    assert slides.SHORT.sub_bottom == slides.SUB_BOTTOM
    assert slides.SHORT.board_top_min == slides.BOARD_TOP_MIN
    assert slides.SHORT.board_bottom == slides.BOARD_BOTTOM
    assert slides.SHORT.show_top_with_board == slides.SHOW_TOP_WITH_BOARD
    assert slides.SHORT.sub_ladder[0][0] == slides.SUB_CHARS


def test_長尺は横():
    assert slides.LONG.w > slides.LONG.h == 1080
    # 下の余白は Shorts の UI ぶん（420px）を空けない
    assert slides.LONG.h - slides.LONG.sub_bottom < 100
    # 幅が広いので 1行の字数も多い
    assert slides.LONG.sub_ladder[0][0] > slides.SHORT.sub_ladder[0][0]


def test_板は横でも字幕の上に収まる():
    for n in (1, 3, 5):
        px, lh, top = slides.board_layout(n, show_bottom=300, g=slides.LONG)
        assert top + 60 + lh * n <= slides.LONG.sub_bottom, (n, top, lh)


def test_焼いた絵の大きさは形のとおり(tmp_path: Path):
    a = slides.slide("10万円", "上限", "医療費が10万円をこえたぶん。", 1, 3, None, tmp_path / "s.png",
                     tag="決まり", board=["年収400万円"])
    b = slides.slide("10万円", "上限", "医療費が10万円をこえたぶん。", 1, 3, None, tmp_path / "l.png",
                     tag="決まり", board=["年収400万円"], form="long")
    assert Image.open(a).size == (1080, 1920)
    assert Image.open(b).size == (1920, 1080)
    # 目で見る1枚（contact_sheet）は、渡された絵の縦横から決める（形を渡し忘れる道を作らない）
    assert Image.open(slides.contact_sheet([a, a], tmp_path / "ss.png", cols=2)).size == (270 * 2, 480)
    assert Image.open(slides.contact_sheet([b, b], tmp_path / "ls.png", cols=2)).size == (480 * 2, 270)


def test_render_は形を渡す():
    """`render.build` が `slide()` の既定値に頼っていないこと（渡し忘れると横が縦で焼ける）。"""
    import inspect
    assert "form=s.form" in inspect.getsource(render.build)


def test_cmd_build_の秒数の門は形から引く():
    import inspect
    src = inspect.getsource(cli.cmd_build)
    assert "form.max_seconds" in src and "form.min_seconds" in src
    assert 'r["total"] <= MAX_SECONDS' not in src      # 写しへ戻っていないこと


def test_狙い15分に届かない長尺は_止めずに注意だけ():
    """**`problems()` へ入れないこと** —— `cli.cmd_build` は `problems()` が 1行でも在ると焼く前に止まり、
    既に焼いた長尺 7本（320〜487秒）が全部 焼き直せなくなります（2026-09-15 21:0x に 1度 そこへ入れて移した）。

    **陽性対照**: `LONG_TARGET_SECONDS` を 0 にすると、この検査の 3行目（注意が出ること）が落ちます。
    """
    from studio import script as sc
    short_long = sc.Script(id="t-aim", date="2026-09-20", title="t", takeaway="t",
                           description="d", tags=[], form="long",
                           segments=[sc.Segment(say="あ" * 40, board=["い"]) for _ in range(20)])
    aim = int(sc.MAX_TOTAL_CHARS * sc.LONG_TARGET_SECONDS / sc.SHORT_MAX_SECONDS)
    assert short_long.total_chars() < aim
    assert any("狙い" in w for w in short_long.warnings())            # 言う
    assert not any("狙い" in p for p in short_long.problems())        # **止めない**
