"""**上げる mp4 が、いまの本文で焼かれた物か**の門（2026-09-11 20:5x・hourly・Opus）。

`cmd_schedule` は `work/<id>.mp4` が**在るか**しか見ていませんでした。題・説明欄・tags は
**上げる瞬間の台本**から読むので（`yt.upload(mp4, s.title, s.description, s.tags, at)`）、
焼いたあとに台本を直して予約すると、**新しい題と説明欄に古い声と絵が付いた本が出ます**。
印字は「上げた」だけで、どこにも「古い」と出ません ＝ §4 (0-b)・`loop_sig` と同じ族の、
**いちばん最後（直す機会がもう無い所）**。

この検査が押さえるのは 2つ:
  (A) `build_sig` が**焼きの入力だけ**で動くこと —— とくに `loop_sig` が見ない 4つ
      （voice/rate・yomi/kana_in_voice・板の行の割り方・背景の絵）で動き、
      焼きに渡らない物（題・説明欄・tags・notes）では**動かない**こと（鳴らない印字＝狼少年にしない）
  (B) `cmd_schedule` が、刻印の無い／食い違う mp4 を**上げないこと**（陽性対照つき）

**「きょうの状態」を書かないこと**（§5 教訓 6つ目）—— 下は全部その場で作った台本で、
日付も枠も齢も見ていません。
"""
import datetime as dt
import types

import pytest

from studio import cli, render, script


def _seg(say="ためしの文です。", show="", sub="", tag="", board=None):
    return script.Segment(say=say, show=show, sub=sub, tag=tag, board=list(board or []))


def _script(**kw) -> script.Script:
    base = dict(id="test-build-sig", date="2026-01-02", title="ためし #Shorts",
                takeaway="ためし", description="ためしの説明欄", tags=["ためし"],
                yomi={"退職所得控除": "たいしょくしょとくこうじょ"}, kana_in_voice=[],
                segments=[_seg(board=["1行目", "2行目"]), _seg(say="2つ目の文です。")])
    base.update(kw)
    return script.Script(**base)


# ---- (A) 指紋の範囲 ------------------------------------------------------

def test_同じ本文なら同じ指紋():
    assert _script().build_sig(None) == _script().build_sig(None)


def test_版が頭に付く():
    assert _script().build_sig(None).startswith(f"{script.BUILD_SIG_VERSION}:")


@pytest.mark.parametrize("kw", [
    {"yomi": {"退職所得控除": "たいしょくしょとくこうじょです"}},   # 読みの直し ＝ 声だけが変わる
    {"kana_in_voice": ["退職所得控除"]},
    {"voice": "ja-JP-Chirp3-HD-Charon"},
    {"rate": 1.12},
])
def test_輪が見ない入力で動く_loop_sigは動かない(kw):
    """**ここがこの門の要**: `loop_sig` では代われないことの実証。"""
    a, b = _script(), _script(**kw)
    assert a.build_sig(None) != b.build_sig(None), kw
    assert a.loop_sig() == b.loop_sig(), f"{kw} で loop_sig まで動くなら、この検査の前提が外れている"


def test_板の行の割り方で動く_loop_sigは動かない():
    """`loop_sig` は板を**継いでから**署名する（13:1x の覆る条件 (1)）。絵の上では割り方が見える。"""
    a = _script(segments=[_seg(board=["1年にとどかない日数", "も1年ぶんになる"])])
    b = _script(segments=[_seg(board=["1年にとどかない日数も", "1年ぶんになる"])])
    assert a.build_sig(None) != b.build_sig(None)
    assert a.loop_sig() == b.loop_sig()


def test_声の字が変われば動く():
    assert _script().build_sig(None) != _script(segments=[_seg(say="ちがう文です。")]).build_sig(None)


@pytest.mark.parametrize("kw", [
    {"title": "ちがう題 #Shorts"},
    {"description": "ちがう説明欄"},
    {"tags": ["ちがう"]},
    {"notes": "出どころを書き足した"},
])
def test_焼きに渡らない物では動かない(kw):
    """上げる瞬間に台本から読み直される物 ＝ 直しても mp4 は古くならない（狼少年にしない）。"""
    assert _script().build_sig(None) == _script(**kw).build_sig(None), kw


def test_背景の絵で動く(tmp_path):
    """注文が届く前に焼くと単色。届いたあと焼き直さずに予約すると**単色のまま出る**。"""
    img = tmp_path / "test-build-sig-bg.jpg"
    img.write_bytes(b"x" * 100)
    s = _script()
    mono = s.build_sig(None)
    with_img = s.build_sig(img)
    assert mono != with_img
    img.write_bytes(b"x" * 200)          # 同じ名で中身が入れ替わった（焼き直しの注文が届いた形）
    assert s.build_sig(img) != with_img


# ---- (B) 予約の門（陽性対照つき） ----------------------------------------

class _Args:
    def __init__(self, vid):
        self.id = vid
        self.at = "10:00"
        self.replace = None
        self.force = False
        self.dry_run = True          # 本番へは行かない。門はこれより手前に在る


@pytest.fixture()
def _stage(tmp_path, monkeypatch):
    """台本・`work/`・背景の絵を tmp に置き、`cmd_schedule` をそこへ向ける。"""
    vid = "test-build-sig"
    scripts, work, images = tmp_path / "scripts", tmp_path / "work", tmp_path / "images"
    for d in (scripts, work, images):
        d.mkdir()
    # **刻を止める**（§5 教訓 6つ目: 検査に「きょうの状態」を書かない）—— `--at 10:00` は
    # 実時刻が 10:00 を過ぎた周では「もう過ぎている」で落ち、門より手前で答えが変わります
    # （この検査を書いた回に 1度 踏んだ。門は緑のまま、陽性対照だけが赤くなった）。
    monkeypatch.setattr(cli, "now_jst", lambda: dt.datetime(2026, 1, 2, 9, 0, tzinfo=cli.JST))
    monkeypatch.setattr(script, "SCRIPTS", scripts)
    monkeypatch.setattr("studio.common.WORK", work)
    monkeypatch.setattr(cli, "IMAGES", images)
    s = _script(id=vid)
    script.save(s)
    (work / vid).mkdir()
    (work / vid / f"{vid}.mp4").write_bytes(b"mp4")
    # `yt` は 1単位 も撃たせない —— 門を抜けたら必ずここで落ちる
    monkeypatch.setattr(cli.yt, "today_lineup", lambda *a, **k: pytest.fail("門を抜けた"))
    return types.SimpleNamespace(vid=vid, s=s, work=work / vid, images=images)


def test_刻印が無い_mp4は上げない(_stage, capsys):
    assert cli.cmd_schedule(_Args(_stage.vid)) == 1
    assert "焼かれていない" in capsys.readouterr().out


def test_刻印がいまの本文と合えば門を抜ける(_stage):
    """**陽性対照**: 合っていれば通る（合わない側だけを見て「門が効いた」と読まないため）。"""
    (_stage.work / "build.sig").write_text(_stage.s.build_sig(None), encoding="utf-8")
    with pytest.raises(BaseException):      # 門を抜けた先の `today_lineup` が必ず落とす
        cli.cmd_schedule(_Args(_stage.vid))


def test_焼いたあとに台本が動いたら上げない(_stage, capsys):
    """**実際に踏みうる形**: 焼く → 読みを直す（声だけが変わる）→ 予約。"""
    (_stage.work / "build.sig").write_text(_stage.s.build_sig(None), encoding="utf-8")
    after = _script(id=_stage.vid, yomi={"退職所得控除": "たいしょくしょとくこうじょです"})
    script.save(after)
    assert cli.cmd_schedule(_Args(_stage.vid)) == 1
    assert "台本か背景の絵が動いた" in capsys.readouterr().out


def test_焼いたあとに絵が届いたら上げない(_stage, capsys):
    """単色で焼いた mp4 を、絵が届いたあとに上げない（`trend.image_orders` が名指しする形）。"""
    (_stage.work / "build.sig").write_text(_stage.s.build_sig(None), encoding="utf-8")
    (_stage.images / f"{_stage.vid}-bg.jpg").write_bytes(b"x" * 100)
    assert cli.cmd_schedule(_Args(_stage.vid)) == 1
    assert "焼かれていない" in capsys.readouterr().out


def test_forceでは通らない(_stage, capsys):
    """`--force` は「1日1本」の門の鍵 ＝ 別の問い。"""
    a = _Args(_stage.vid)
    a.force = True
    assert cli.cmd_schedule(a) == 1
    assert "焼かれていない" in capsys.readouterr().out


def test_焼けば刻印が残る(monkeypatch, tmp_path):
    """`render.build` が mp4 を書くのと同じ所で刻むこと（呼ぶ側に置くと刻み忘れる道が出る）。"""
    vid = "test-build-sig"
    work = tmp_path / "work"
    monkeypatch.setattr("studio.common.WORK", work)
    (work / vid).mkdir(parents=True)
    assert render.built_sig(vid) is None
    (work / vid / "build.sig").write_text("1:deadbeef", encoding="utf-8")
    assert render.built_sig(vid) == "1:deadbeef"
