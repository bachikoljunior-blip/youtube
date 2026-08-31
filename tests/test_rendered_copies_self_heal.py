"""**親が読む写しは、親の周のたびに焼き直されること。**

## なぜこの検査があるか（2026-09-01）

親が実際に読むのは `docs/trigger_body.rendered.md`（**写し**）です。
正本は `docs/trigger_body.md` で、焼き直すのは
`scripts/trigger_sync.py --write-rendered` の1手。

**その1手を、誰も打っていませんでした。**

実測 2026-09-01: 写しは **64行ぶん古く**、次のものが全部 入っていませんでした:

    「**止めないこと**」（オーナー 2026-08-31「何で止まってんだよ！」）
    「サブが1体も走っていないなら、WAIT でも立てること」
    固定の与件4件（1日1本・作り置きなし・サブ二台・消さない）
    `model: "opus"` の指定／`isolation: "worktree"`

**親は、その古い写しを毎周 当てていました。**

`tests/test_trigger_sync.py::test_rendered_copy_is_current` は赤で立っており、
文面は「`--write-rendered` を打つこと」でした ——
**打つ側が居ない検査**です。この repo で同じ形が **3件目**:

    2026-08-30  `deadline_check`  道具は在り、撃つ側が手順に0件（到達日が 50日 止まっていた）
    2026-09-01  `pool_drain`      同上（規則1 が 09/12 から 26日ぶん破れる）
    2026-09-01  `--write-rendered` 同上（親が 64行 古い本文を当てていた）

**だから、打つ側を `scripts/next_round.py` に置きました** ——
親が毎周いちばん最初に撃つ道具で、**写しを読む直前**に走ります。

**覆る条件**: 親が正本を直に読むようになったら、写しごと要らなくなります。
そのときは `refresh_rendered()` と `--write-rendered` の**両方**を消すこと。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import next_round  # noqa: E402


def test_親の道具が写しを焼き直す口を持っている():
    assert hasattr(next_round, "refresh_rendered"), (
        "`next_round.refresh_rendered()` がありません。"
        " **写しを焼く側が誰も居ない状態へ戻っています**"
    )


def test_その口が_main_から呼ばれている():
    """**関数を足しただけで呼ばれていない道**を塞ぐ。

    この repo で一番多い壊れ方は「言っている所と、している所が別」です。
    """
    src = (ROOT / "scripts" / "next_round.py").read_text(encoding="utf-8")
    body = src[src.index("def main() -> int:"):]
    assert "refresh_rendered()" in body, (
        "`main()` が `refresh_rendered()` を呼んでいません"
    )


def test_写しが焼けなくても親は止まらない(monkeypatch):
    """**A10: 止める仕掛けにしないこと。**

    写しが古いのは損ですが、**親が動かないほうがもっと損**です
    （オーナー 2026-08-31「勝手にそれで止まるのなし」）。
    """
    def boom(*a, **k):
        raise OSError("焼けません")

    monkeypatch.setattr(subprocess, "run", boom)
    lines = next_round.refresh_rendered()          # 例外が外へ出ないこと
    assert any("[!]" in x for x in lines), (
        "焼けなかったことを黙っています。**黙ると、次に気づくのは"
        "『古い本文で回っていた』ときです**"
    )


def test_実際に焼くと写しが正本と一致する():
    """**焼いた結果が、`test_rendered_copy_is_current` と同じ答えになること。**"""
    import trigger_sync as ts

    next_round.refresh_rendered()
    want = ts.render_body(ts.load_spec()) + "\n"
    got = ts.RENDERED.read_text(encoding="utf-8")
    assert got == want, "焼き直したのに、写しが正本と食い違っています"
