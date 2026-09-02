"""**contact sheet が「全部 見えている」と言うなら、本当に1コマ1枚であること。**

## 何が起きたか（2026-09-02・出す本の sheet を目で見て踏んだ）

`scripts/inspect_build.py` は **等間隔**でコマを抜いていました。枚数は
`slides_plan.json` のコマ数に合わせてあるので、**枚数は合います。**
**合っていなかったのは中身のほうです。**

クリップの長さはナレーションの長さで決まるので揃っていません。等間隔だと

    長いコマ  **2回** 抜かれる
    短いコマ  **1回も** 抜かれない

が普通に起きます。実測（`gassan-kaigo-alone-155`・18コマ・18枚）——
**最後のコマが2枚**並び、**15番目（「合算に入らない負担」）が1枚も出ていません**でした。
それでも印字は:

    [inspect] 計画は 18コマ。18枚で**全部に届いています**

**枚数だけを見て「全部に届いています」と言っていた**わけです。
この sheet は `docs/CRITIQUE.md` の独立評価にそのまま渡るので、
**見せていないコマに点が付き、見せすぎたコマが二重に効きます** ——
`scripts/inspect_build.py` の docstring が3件 並べている
「**計器が、動画に無いものを見せた／あるものを隠した**」の**4件目**です。

## この検査が押さえているもの

    1. 抜きどころは**クリップ1本につき1点**
    2. 先頭だけは真ん中ではなく `head` 秒（独立評価が聞くのは「最初の1.5秒」——
       2026-08-15 の「冒頭を必ず1枚入れること」を壊さないため）
    3. 2本目から先は、**そのクリップの内側**に落ちること
       （＝ 隣のコマを2回 抜かない）
    4. **等間隔だと、この形の並びで実際に取りこぼす**こと
       ＝ 直す前の姿を再現して、直しが効いていることを見ます
    5. クリップが読めない回は `None`（呼ぶ側が等間隔へ落ち、
       「届いています」とは言わなくなる）

**戻すにはこの検査を消すしかありません。**
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location(
    "inspect_build_mod", ROOT / "scripts" / "inspect_build.py")
inspect_build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(inspect_build)

#: **長さの揃っていない18本**（実物と同じ形 —— 短いコマと長いコマが混ざる）。
DURS = [2.0, 9.0, 7.5, 6.0, 11.0, 5.0, 8.0, 4.0,
        12.0, 6.5, 9.5, 3.0, 7.0, 10.0, 4.5, 3.5, 13.0, 6.0]


def _work(tmp_path, n: int = len(DURS)) -> Path:
    clips = tmp_path / "clips"
    clips.mkdir(parents=True)
    for i in range(n):
        (clips / f"clip_{i:03d}.mp4").write_bytes(b"")
    return tmp_path


def _spans() -> list[tuple[float, float]]:
    out, at = [], 0.0
    for d in DURS:
        out.append((at, at + d))
        at += d
    return out


def test_1コマ1枚で_各クリップの内側に落ちる(tmp_path, monkeypatch):
    """**1・2・3**。"""
    monkeypatch.setattr(inspect_build, "_duration",
                        lambda p: DURS[int(p.stem.split("_")[1])])
    marks = inspect_build.clip_marks(_work(tmp_path), head=0.25)
    assert marks is not None
    assert len(marks) == len(DURS), marks
    assert marks[0] == 0.25, "先頭は真ん中ではなく head 秒（冒頭の1.5秒を渡すため）"
    for i, (lo, hi) in enumerate(_spans()):
        assert lo <= marks[i] < hi, (i, marks[i], lo, hi)


def test_等間隔だと本当に取りこぼす(tmp_path, monkeypatch):
    """**4**: 直す前の姿を再現して、**取りこぼしが実在した**ことを見ます。

    **「発火したことのない検査は検査ではない」**（`CLAUDE.md`）——
    等間隔で本当に 0回 のコマが出ることを、ここで確かめておきます。
    """
    total = sum(DURS)
    n = len(DURS)
    head = 0.25
    old = [min(head + (total - head) * i / max(n - 1, 1), max(total - 0.2, 0.0))
           for i in range(n)]
    spans = _spans()
    hits = [0] * n
    for at in old:
        for i, (lo, hi) in enumerate(spans):
            if lo <= at < hi:
                hits[i] += 1
                break
    assert 0 in hits, f"等間隔で取りこぼしが出ません（並びを見直すこと）: {hits}"
    assert max(hits) >= 2, f"等間隔で二重に抜かれるコマが出ません: {hits}"

    # **新しいほうは、どのコマもきっかり1回**
    monkeypatch.setattr(inspect_build, "_duration",
                        lambda p: DURS[int(p.stem.split("_")[1])])
    marks = inspect_build.clip_marks(_work(tmp_path), head=head)
    new_hits = [0] * n
    for at in marks:
        for i, (lo, hi) in enumerate(spans):
            if lo <= at < hi:
                new_hits[i] += 1
                break
    assert new_hits == [1] * n, new_hits


def test_クリップが無ければ黙って_None(tmp_path):
    """**5**: 投稿後に `clips/` が消えた回で落ちないこと（等間隔へ落ちます）。"""
    assert inspect_build.clip_marks(tmp_path) is None


def test_1本でも長さが読めなければ_None(tmp_path, monkeypatch):
    """**5 の裏**: 半端な marks を返さないこと（返すと、そこだけ穴が空きます）。"""
    def _boom(p):
        if p.stem.endswith("003"):
            raise OSError("ffprobe が落ちました")
        return 5.0

    monkeypatch.setattr(inspect_build, "_duration", _boom)
    assert inspect_build.clip_marks(_work(tmp_path)) is None
