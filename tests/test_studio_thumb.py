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
