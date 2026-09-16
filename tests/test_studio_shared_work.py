"""焼いた物（`work/`）を、**周をまたいで共有する**（2026-09-16 15:5x・optimizer・Fable 5.1・ultracode）。

サブは `<本体>/.claude/worktrees/agent-xxxx` で走ります。`work/` を worktree の中に置くと、
**焼いた物がその周かぎり**になります。この回に数えた実物:

    worktree **42個**・うち `work/` を持つ **12個**・合計 **11GB**

そして 3つ 起きます:
 1. **焼いた物が、その周で上げられなければ捨てられる。** この回は日枠が尽きていて
    （残り 1,021単位・1本 1,650単位・戻るのは 16:00 JST）、焼いた 3本 を 1本も上げられません。
 2. **`seg-<sha>.wav` の憶えが 1コマも当たらない**（憶える場所が周ごとに別）＝
    「1文だけ直して焼き直す」が毎回 全コマの合成になります（1本 6〜10分・TTS の代金つき）。
 3. 貯まります（11GB）。
"""
import os
from pathlib import Path

from studio import common


def test_worktreeから本体を指す():
    got = common._shared_root(Path("/home/user/youtube/.claude/worktrees/agent-a136f4d0"))
    assert got == Path("/home/user/youtube")


def test_本体で走っても壊れない():
    assert common._shared_root(Path("/home/user/youtube")) == Path("/home/user/youtube")


def test_別の置き方なら触らない():
    """`.claude/worktrees` の形でなければ、そのまま返すこと（検査・別の置き方で壊れない）。"""
    for p in ("/tmp/x/y", "/srv/repo", "/a/.claude/plugins/b"):
        assert common._shared_root(Path(p)) == Path(p), p


def test_環境変数が勝つ():
    """置き場を人が決められること（`STUDIO_WORK`）。"""
    import importlib
    old = os.environ.get("STUDIO_WORK")
    os.environ["STUDIO_WORK"] = "/tmp/studio-work-test"
    try:
        importlib.reload(common)
        assert common.WORK == Path("/tmp/studio-work-test")
    finally:
        if old is None:
            os.environ.pop("STUDIO_WORK", None)
        else:
            os.environ["STUDIO_WORK"] = old
        importlib.reload(common)


def test_workはworktreeの中を指していない():
    """**この検査が、戻したときに鳴る側です。**"""
    assert ".claude" not in common.WORK.parts or os.environ.get("STUDIO_WORK"), \
        f"`work/` が worktree の中を指しています: {common.WORK}"
