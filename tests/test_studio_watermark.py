"""透かし（登録ボタンの重ね）＝ **公開ずみの本にも後から載る、ただ 1つ の腕**。

**2026-09-16 15:3x に足した**（optimizer・Fable 5.1・ultracode）。

縛っているのは再生ではなく**登録**で、扉(b) が要るのは **1.62%**・いま **0.041%**
（`trend.rev_deadline` ＝ **39倍**）。台本の直しは**これから出る本**にしか効きませんが、
透かしは**いま在る本にも同じ日から出ます** ＝ 1回 50単位 でいちばん安い腕。
**この repo は 09/16 まで 1度も撃っていませんでした**（`watermark` の字が `studio/` にも
`src/` にも 0件 で、「絵の注文で避ける物」として出てくるだけだった）。
"""
from pathlib import Path

from PIL import Image

from studio import yt

ROOT = Path(__file__).resolve().parents[1]


def test_透かしの絵が在って_YouTubeの決めに合っている():
    p = ROOT / yt.WATERMARK
    assert p.exists(), f"透かしの絵が無い: {p}"
    with Image.open(p) as im:
        w, h = im.size
    assert w == h, f"正方形であること（いま {w}x{h}）"
    assert p.stat().st_size <= 1_000_000, "1MB まで"


def test_timingは渡さない():
    """**渡すと 400 `Invalid Value` が返ります**（2026-09-16 15:4x に撃って確かめた）。

    `{"type": "offsetFromStart", "offsetMs": "15000", "durationMs": "0"}` で落ちた。
    **空の body ＝ 本のあいだ ずっと出す**で通します。
    次に触る回へ: 渡すなら `durationMs` を 0 以外にしてから、1回 撃って確かめること。
    """
    import inspect
    src = inspect.getsource(yt.set_watermark)
    assert "if offset_ms and duration_ms:" in src, \
        "既定（duration_ms=0）で `timing` を渡さないこと ＝ 400 になります"
    assert yt.set_watermark.__defaults__[2] == 0, "duration_ms の既定は 0（＝ timing を渡さない）"


def test_絵の出どころは1か所():
    import inspect
    from studio import cli
    assert "yt.WATERMARK" in inspect.getsource(cli.cmd_watermark), "写しを持たないこと"


def test_置く前に大きさを見る():
    """`watermarks.set` は 50単位。**撃つ前に形を見て落とすこと**（無駄な 50単位 を出さない）。"""
    import inspect
    src = inspect.getsource(__import__("studio.cli", fromlist=["cli"]).cmd_watermark)
    assert "dry_run" in src and "1_000_000" in src
