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


def test_timingは渡す_durationは0にしない():
    """**2026-09-17 16:0x に、日枠が戻った窓で 4通り 撃って、通る形を 1つ 見つけました。**

    この検査は **`test_timingは渡さない` を置き換えたもの**です。前の名前と中身は
    「空の body ＝ ずっと出す」という読みの上に立っていましたが、**その読みは撃たれていません**
    （09/16 15:4x は日枠が尽きた窓で、`timing` の 400 を見て `{}` に替えただけ）。

        `{"timing": {..., "durationMs": "0"}}`   400 `Invalid Value`
        `{}`（空の body）                         400 `No filter selected. Expected one of: resource`
        `{"position": ...}` のみ                  400 `Required`
        **`timing`（durationMs > 0）＋ `position`   通った**

    ＝ **要るのは `timing` で、`durationMs` は 0 にできません。**
    「出しっぱなし」は**長い `durationMs`** で作ります（既定 30分 ＝ 長尺の狙い 15〜30分 を覆う）。

    **覆る条件**: `channels`／`watermarks` の口が変わって `{}` や `durationMs: 0` が通るように
    なったら、**撃って確かめてから**この検査を書き直すこと（**撃たずに書き替えないこと** ——
    この検査が置き換えた側が、まさにそれでした）。
    """
    import inspect
    src = inspect.getsource(yt.set_watermark)
    assert "position" in src, "`position` を渡すこと（body が空だと 400）"
    assert '"timing"' in src, "`timing` を渡すこと（無いと 400 `Required`）"
    d = yt.set_watermark.__defaults__[2]
    assert d and d > 0, f"duration_ms の既定は 0 より大きいこと（いま {d}・0 は 400 `Invalid Value`）"


def test_透かしの長さは長尺の狙いを覆う():
    """**陽性対照**: 既定の `duration_ms` が、長尺の狙い（`script.LONG_TARGET_SECONDS`）より短いと、
    本の途中で登録の口が消えます。**狙いを伸ばした回が、ここも一緒に見るための行。**"""
    from studio import script
    d_ms = yt.set_watermark.__defaults__[2]
    assert d_ms / 1000.0 >= script.LONG_TARGET_SECONDS, \
        f"透かし {d_ms / 60000:.0f}分 が長尺の狙い {script.LONG_TARGET_SECONDS / 60:.0f}分 を覆っていません"


def test_絵の出どころは1か所():
    import inspect
    from studio import cli
    assert "yt.WATERMARK" in inspect.getsource(cli.cmd_watermark), "写しを持たないこと"


def test_置く前に大きさを見る():
    """`watermarks.set` は 50単位。**撃つ前に形を見て落とすこと**（無駄な 50単位 を出さない）。"""
    import inspect
    src = inspect.getsource(__import__("studio.cli", fromlist=["cli"]).cmd_watermark)
    assert "dry_run" in src and "1_000_000" in src
