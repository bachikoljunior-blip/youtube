"""**空きディスクの行**の検査（2026-09-18 15:0x・optimizer・Opus 5）。

**なぜこの検査が在るか**（この回に踏んだ実測）: 直した長尺の `build` が **exit 1** で、
**1行も出さずに**落ちました。台本は `lint` [!] 0、`critique` は「輪を閉じてよい」まで来ていて、
道具も壊れていません。原因は **`/` が 100%（空き 89MB）** ——
`.claude/worktrees/` に**サブの作業場が 55個・16GB**（いちばん古いのは 09/03 ＝ **15日ぶん**）
溜まっていたためです。**1周に 1つ 増えて、誰も消しません。**

**どの門もこれを見ていませんでした。** ＝ 次に来た回が「台本が悪いのか、道具が壊れたのか」を
探す形でした。**この行は、その数時間 を 1行 に変えます。**

守るのは 3つ:
  (1) 空きが門を切ったら鳴ること（**数を出すこと** ＝ 「足りない」だけでは次の回が動けない）
  (2) 足りているときは **1字も出さないこと**（`status` は毎周 2体 が読む側）
  (3) **掃く相手を名指しすること**（サブは自分の作業場の外を消せない ＝ 手は親の側に在る）
"""
from __future__ import annotations

import collections

import pytest

from studio import cli


@pytest.fixture
def usage(monkeypatch):
    """`shutil.disk_usage` を差し替える（本物の空きに検査を依存させない）。"""
    U = collections.namedtuple("U", "total used free")

    def set_free(gb: float):
        import shutil
        monkeypatch.setattr(shutil, "disk_usage", lambda p: U(252 * 2**30, 0, int(gb * 2**30)))

    return set_free


def test_足りていれば1字も出さない(usage):
    usage(cli.DISK_FLOOR_GB + 0.5)
    assert cli.disk_line() == ""


def test_門のちょうど上でも黙る(usage):
    usage(cli.DISK_FLOOR_GB)
    assert cli.disk_line() == ""


def test_切ったら鳴る(usage):
    usage(0.09)
    out = cli.disk_line()
    assert out, "空き 0.09GB で黙ってはいけない"
    assert "0.09GB" in out, "数を出すこと（『足りない』だけでは次の回が動けない）"


def test_buildが黙って落ちることを名指しする(usage):
    """この回に踏んだ形そのもの ＝ 次の回が台本を疑いに行かないための行。"""
    usage(0.09)
    out = cli.disk_line()
    assert "build" in out and "exit 1" in out


def test_掃く相手と相手の側を名指しする(usage):
    """サブは自分の作業場の外を消せない（この回に permission で止まった）＝ 手は親の側。"""
    usage(0.09)
    out = cli.disk_line()
    assert "worktrees" in out
    assert "親" in out and "24時間" in out


def test_ディスクが読めない回は黙る(monkeypatch):
    """`status` を落とさないこと（止めない行）。"""
    import shutil

    def boom(p):
        raise OSError("no such")

    monkeypatch.setattr(shutil, "disk_usage", boom)
    assert cli.disk_line() == ""
