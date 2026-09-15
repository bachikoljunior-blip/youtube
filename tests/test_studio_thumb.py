"""長尺のサムネ（`studio/thumb.py`・2026-09-15・optimizer・Fable）。

**いちばんの仕事は陰性対照**: `short` のサムネは 1コマ目の画面のまま（`cmd_schedule` の答えを 1つも変えない）。
`thumb` の欄は `build_sig` に入らない（mp4 に渡らない ＝ 焼き直し待ちが偽で立たない）。
"""
from pathlib import Path

from PIL import Image

from studio import cli, script, thumb


def _s(form, thumb_lines=None, show="70歳まで遅らせると\n失うお金3つ"):
    return script.Script(id="t-thumb", date="2026-09-15", title="t" + (" #Shorts" if form == "short" else ""),
                         takeaway="t", form=form, thumb=thumb_lines or [],
                         segments=[script.Segment(say="あ" * 40, show=show) for _ in range(6)])


def test_long_は1280x720の絵を描く(tmp_path: Path):
    out = thumb.render(_s("long", ["70歳まで遅らせると", "失うお金3つ", "127万円"]), None, tmp_path / "t.png")
    im = Image.open(out)
    assert im.size == (thumb.THUMB_W, thumb.THUMB_H) == (1280, 720)


def test_行は_thumb_が無ければ1コマ目のshow():
    assert thumb.lines_for(_s("long")) == ["70歳まで遅らせると", "失うお金3つ"]
    assert thumb.lines_for(_s("long", ["a", "b", "c", "d"])) == ["a", "b", "c"]


# --- peers の形（2026-09-16 02:0x・optimizer・Fable・ultracode） ---
#
# 速い 6チャンネルの上位 6枚 は、どれも チップ（対象）／巨大な白と黄／赤帯（結果）の 4つ。
# (4-j) が写したのは題だけで、絵は手もとの理屈のままでした。ここはその当て直しの検査。

def _peer(thumb_lines=None):
    s = _s("long", thumb_lines or ["ねんきん定期便に", "載っていないお金6つ", "382万7800円"])
    s.title = "【60代の夫婦へ】ねんきん定期便に載っていないお金6つ｜申請しないと382万円が来ません"
    return s


def test_チップは題の鍵かっこから引く():
    assert thumb.chip_of(_peer()) == "60代の夫婦へ"


def test_赤帯は題の縦棒の後ろから引く():
    assert thumb.band_of(_peer()) == "申請しないと382万円が来ません"


def test_4行_渡せば_台本の側が勝つ():
    s = _peer(["50歳以上へ", "定期便に載っていない", "24万3800円", "届出だけで変わります"])
    assert thumb.chip_of(s) == "50歳以上へ"
    assert thumb.big_lines(s) == ["定期便に載っていない", "24万3800円"]
    assert thumb.band_of(s) == "届出だけで変わります"


def test_黄になるのは_数がいちばん濃い行():
    """陽性対照つき: 最初の当たりで選ぶと「お金6つ」の 6 が勝ち、金額の行が白のままになる。"""
    lines = ["ねんきん定期便に", "載っていないお金6つ", "382万7800円"]
    assert thumb._accent_of(lines) == 2
    assert thumb._NUM.search(lines[1])          # ← 最初の当たりはここ（＝ 素朴な実装は 1 を返す）
    assert thumb._accent_of(["あ", "い"]) == 1  # 数が 1つも無ければ最後の行


def test_題に鍵かっこも縦棒も無ければ_チップも帯も描かない():
    """陰性対照。判定の 3本（旧の題）はこちら側 ＝ 無い物を作らない。"""
    s = _s("long", ["70歳まで遅らせると", "失うお金3つ"])
    assert thumb.chip_of(s) is None and thumb.band_of(s) is None


def test_長い帯は描かない():
    s = _peer()
    s.title = "【対象】" + "あ" * 10 + "｜" + "い" * 30
    assert thumb.band_of(s) is None


def test_peers_の形でも1280x720のまま(tmp_path: Path):
    out = thumb.render(_peer(), None, tmp_path / "t.png")
    assert Image.open(out).size == (1280, 720)


def test_short_のサムネは1コマ目の画面のまま(monkeypatch, tmp_path: Path):
    """陰性対照。`short` はここを通っても `slide-01.png` を指す（描かない）。"""
    monkeypatch.setattr(cli, "workdir", lambda vid: tmp_path)
    assert cli.thumbnail_for(_s("short"), "t-thumb") == tmp_path / "slide-01.png"
    assert not (tmp_path / "thumb.png").exists()


def test_long_のサムネは_thumb_png(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(cli, "workdir", lambda vid: tmp_path)
    monkeypatch.setattr(cli, "image_for", lambda vid: None)
    p = cli.thumbnail_for(_s("long"), "t-thumb")
    assert p == tmp_path / "thumb.png" and p.exists()


def test_thumb_の欄は指紋に入らない():
    a, b = _s("long"), _s("long", ["x", "y"])
    assert a.build_sig() == b.build_sig()
    assert a.loop_sig() == b.loop_sig()
    s, t = _s("short"), _s("short", ["x"])
    assert s.build_sig() == t.build_sig()


def test_schedule_は_thumbnail_for_を通る():
    src = Path(cli.__file__).read_text(encoding="utf-8")
    body = src[src.index("def cmd_schedule("):src.index("def verify_meta(")]
    assert "thumbnail_for(s, a.id)" in body
    assert 'workdir(a.id) / "slide-01.png"' not in body
