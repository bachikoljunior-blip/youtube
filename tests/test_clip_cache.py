"""**クリップの控え**（`src/renderer.CLIP_CACHE_DIR`）。

なぜ要るか（数字は `src/renderer.py` の註に。要約）:
`data/rebake.jsonl` は `start` 25件 に対して本になったのが 1件 で、
**`done` の無い `start` が 13件**。焼く側は回の器の中で死ぬのに、
`src/pipeline.py` が毎回 `rmtree(build/<題材>)` を撃つので、
**途中まで焼けたクリップが1コマも残りません。**

ここで縛るのは4つ:
  1. 同じ入力なら鍵が同じ／どれか1つでも違えば鍵が違う
  2. 焼き方（`_clip_from_slide` の中身・`V_ARGS`）が変われば鍵が変わる
  3. `build_video` は控えに在るコマを**焼かない**
  4. 控えの置き場所が `rmtree(build/<題材>)` で消えない所に在る
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from src import config, renderer


def _png(dest: Path, *, seed: int = 0) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    color = f"0x{(seed * 0x2f5b7d + 0x112233) & 0xFFFFFF:06x}"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", f"color=c={color}:size=320x180:rate=1:duration=1",
         "-frames:v", "1", str(dest)],
        check=True,
    )
    return dest


def test_鍵は入力ごとに変わる(tmp_path):
    a = _png(tmp_path / "a.png", seed=0)
    b = _png(tmp_path / "b.png", seed=1)
    k = renderer.clip_cache_key(a, 3.0, 30, 1920, 1080, False)
    assert k == renderer.clip_cache_key(a, 3.0, 30, 1920, 1080, False)
    assert k != renderer.clip_cache_key(b, 3.0, 30, 1920, 1080, False)
    assert k != renderer.clip_cache_key(a, 3.5, 30, 1920, 1080, False)
    assert k != renderer.clip_cache_key(a, 3.0, 24, 1920, 1080, False)
    assert k != renderer.clip_cache_key(a, 3.0, 30, 1280, 720, False)
    assert k != renderer.clip_cache_key(a, 3.0, 30, 1920, 1080, True)


def test_秒数の丸めは小数3桁でそろえる(tmp_path):
    """`-t` に渡すのは `f'{duration:.3f}'`。鍵もそこでそろえないと、
    **同じクリップに別の名前が付いて控えが効きません。**"""
    a = _png(tmp_path / "a.png")
    assert (renderer.clip_cache_key(a, 3.0001, 30, 1920, 1080, False)
            == renderer.clip_cache_key(a, 3.0004, 30, 1920, 1080, False))


def test_焼き方を変えたら控えは全部無効になる(tmp_path, monkeypatch):
    """**「その直しは、この本に入っていません」を控えの側で起こさないための鍵。**"""
    a = _png(tmp_path / "a.png")
    before = renderer.clip_cache_key(a, 3.0, 30, 1920, 1080, False)
    monkeypatch.setattr(renderer, "_RECIPE_SHA", None)
    monkeypatch.setattr(renderer, "V_ARGS", [*renderer.V_ARGS, "-tune", "stillimage"])
    after = renderer.clip_cache_key(a, 3.0, 30, 1920, 1080, False)
    assert before != after, "V_ARGS を変えても鍵が同じ ＝ 古いクリップが混ざります"


def test_控えは題材の作業場の外に在る():
    """`src/pipeline.py` は毎回 `rmtree(config.BUILD_DIR / topic_id)` を撃ちます。
    控えがその下に在ると、**1行目で消えます。**"""
    cache = renderer.DEFAULT_CLIP_CACHE_DIR.resolve()
    assert cache.parent == Path(config.BUILD_DIR).resolve(), \
        "控えは build/ の直下に置くこと（build/<題材>/ の中は rmtree で消えます）"
    # `build/<題材>` として使われうる名前でないこと（先頭が `.` なら題材にならない）
    assert cache.name.startswith("."), "題材 id と衝突しない名前にすること"


def test_控えに在るコマは焼かない(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    monkeypatch.setattr(renderer, "CLIP_CACHE_DIR", cache)
    slides = [_png(tmp_path / f"s{i}.png", seed=i) for i in range(3)]
    durs = [1.0, 1.0, 1.0]

    burned: list[Path] = []
    real = renderer._clip_from_slide

    def spy(src, duration, dest, fps, w, h, opening=False):
        burned.append(Path(src))
        return real(src, duration, dest, fps, w, h, opening=opening)

    monkeypatch.setattr(renderer, "_clip_from_slide", spy)
    monkeypatch.setattr(renderer, "opening_motion_on", lambda: False)

    def build(work: Path):
        work.mkdir(parents=True, exist_ok=True)
        out: list[Path] = []
        clips_dir = work / "clips"
        clips_dir.mkdir(parents=True, exist_ok=True)
        for i, (slide, d) in enumerate(zip(slides, durs)):
            dest = clips_dir / f"clip_{i:03d}.mp4"
            key = renderer.clip_cache_key(slide, d + renderer.SILENCE_SECONDS,
                                          30, 320, 180, False)
            if renderer._clip_cache_get(key, dest, cache):
                out.append(dest)
                continue
            renderer._clip_from_slide(slide, d + renderer.SILENCE_SECONDS, dest,
                                      30, 320, 180, opening=False)
            renderer._clip_cache_put(key, dest, cache)
            out.append(dest)
        return out

    first = build(tmp_path / "w1")
    assert len(burned) == 3
    assert all(p.stat().st_size > 0 for p in first)

    # 2周目 ＝ 途中で死んだ焼きの次の周。**1コマも焼かない。**
    burned.clear()
    second = build(tmp_path / "w2")
    assert burned == [], "同じ絵・同じ秒数なのに焼き直しています"
    assert all(p.stat().st_size > 0 for p in second)
    assert first[0].read_bytes() == second[0].read_bytes()

    # 1コマだけ絵を替える ＝ 規則3 の焼き直し。**替えた1コマだけ焼く。**
    burned.clear()
    _png(slides[1], seed=7)
    build(tmp_path / "w3")
    assert burned == [slides[1]], f"焼いたのは {burned}（替えた1コマだけのはず）"


def test_控えが上限を超えたら古い順に捨てる(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    made = []
    for i in range(5):
        p = cache / f"{i:064x}.mp4"
        p.write_bytes(b"x" * 100)
        import os
        os.utime(p, (1_000_000 + i, 1_000_000 + i))
        made.append(p)
    dropped = renderer.prune_clip_cache(cap=250, cache_dir=cache)
    assert dropped == 3, f"捨てたのは {dropped}件（500 → 250 なので 3件）"
    assert not made[0].exists() and not made[1].exists() and not made[2].exists()
    assert made[3].exists() and made[4].exists(), "新しいほうを残すこと"


def test_控えが壊れていても焼きは止まらない(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    empty = cache / ("a" * 64 + ".mp4")
    empty.write_bytes(b"")
    assert renderer._clip_cache_get("a" * 64, tmp_path / "out.mp4", cache) is False, \
        "0バイトの控えを「在る」と読むと、空のクリップが本に入ります"


@pytest.mark.parametrize("missing", ["nope"])
def test_控えが無いときは静かに焼く側へ倒す(tmp_path, missing):
    assert renderer._clip_cache_get(missing, tmp_path / "o.mp4", tmp_path / "no-such") is False
