"""控え（critique_queue）は、書いたら**その場で push する**こと。

## なぜ要るか（2026-08-31 22:xx に踏んだ）

09/01 22:00 に出る `UIWHsypOPPg` の控えが、**git に1バイトもありません。**

`scripts/upload_only.py` は `critique_queue.stash()` を確かに呼んでおり、
失敗すれば大きく印字して終了コード 1 を返す作りです。**落ちてはいません** ——
コンテナのディスクに書けたあと、その回の commit（`f7d3171e`）が
`data/api_calls.jsonl` `data/day_quota.jsonl` `data/published_bars.json`
`data/uploaded.jsonl` の**4本しか拾わなかった**だけです。
コンテナが畳まれて、控えは消えました。

**失ったもの**:

  - 読み上げ全文 …… 出る前に中身を確かめる唯一の材料（`docs/CRITIQUE.md`）
  - サムネイルの bytes …… `refresh_thumbnail.py --missing` が押す先

そして**控えの無い本は `missing_thumbnail()` の一覧に出ません**。
つまり受け取り帳 `e1ea4c96` の (1)
（「枠が戻ったら `refresh_thumbnail.py --missing` を撃つこと」）は、
**その本を黙って飛ばします** —— 09/01 に出る1本は、
サムネイル無しで公開されるところでした。

受け取り帳が 2026-08-15/16 に踏んだのと**同じ穴**です
（`docs/trigger_main.md` §1「押した後なら、この子が途中で死んでも、
次の子が拾えます」）。**同じ道具で塞ぎます。**

**覆る条件**: 投稿の口が控えを YouTube 側から引き直せるようになったら、
ここで押す必要はありません（いまは読み上げ文もサムネの原本も手元にしかない）。
"""
from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import critique_queue  # noqa: E402
from src import inbox  # noqa: E402


def test_git_save_はパスを受け取れる():
    """**受け取り帳だけの道具にしないこと。**

    オーナー指摘 e6d3be89「失敗したならそこだけ直すんじゃなくて応用しないの？」。
    `git_save` は分離 HEAD・ワークツリーの枝・兄弟との押し合いを全部
    面倒みています。**同じ穴を塞ぐ側が、それを書き直さないこと。**
    """
    sig = inspect.signature(inbox.git_save)
    assert "paths" in sig.parameters, (
        "git_save が paths を受け取りません。控えを押す側が"
        "commit/push を書き直すことになり、分離 HEAD と枝の判定が二重になります"
    )
    assert sig.parameters["paths"].default is None, (
        "paths の既定は None（＝受け取り帳1本）にすること。"
        "既存の呼び出しを壊さないため"
    )


def test_stash_が_git_save_を呼ぶ():
    """**書いただけで終わらせないこと。**"""
    src = inspect.getsource(critique_queue.stash)
    assert "git_save" in src, (
        "critique_queue.stash() が控えを push していません。"
        "コンテナが畳まれた時点で、読み上げ文とサムネイルの bytes が消えます"
        "（2026-08-31 の UIWHsypOPPg がそれ）"
    )


def test_押せなくても投稿は止めない():
    """**途切れるほうが高い**（CLAUDE.md）。ただし黙って通さないこと。"""
    src = inspect.getsource(critique_queue.stash)
    assert "except Exception" in src, (
        "push の失敗で stash() が例外を投げると、投稿の後始末が落ちます"
    )
    assert "push できませんでした" in src, (
        "押せなかったことを印字していません。**黙って落とすのがいちばん高い**"
    )


def test_控えの無い本は押し直しの一覧に出ない():
    """**この検査が、穴の正体そのものです。**

    `missing_thumbnail()` は控えを走査します。控えが無い本は
    「サムネイルが載っていない」とも判定されません ——
    `refresh_thumbnail.py --missing` を撃っても**黙って飛ばされます。**
    """
    rows = critique_queue.missing_thumbnail()
    ids = {r["video_id"] for r in rows}
    stash_dir = ROOT / "data" / "critique_queue"
    for vid in ids:
        assert (stash_dir / f"{vid}.json").exists(), (
            f"{vid} は控えなしで一覧に出ています（作りが変わりました）"
        )


@pytest.mark.parametrize("video_id", ["UIWHsypOPPg"])
def test_次に公開される本の控えがgitに在る(video_id: str):
    """**出る前に中身を確かめられること。**

    `data/uploaded.jsonl` に予約を持って載っている本は、
    控え（読み上げ全文）が git に在らなければなりません。
    無ければ、その本は**誰も中身を読めないまま公開されます。**
    """
    meta = ROOT / "data" / "critique_queue" / f"{video_id}.json"
    assert meta.exists(), (
        f"{video_id} の控えが git にありません。読み上げ文を誰も読めず、"
        "サムネイルの bytes も押し直せません"
    )
    d = json.loads(meta.read_text(encoding="utf-8"))

    # **読み上げが空でよいのは、出どころを申告している控えだけ。**
    #
    # `UIWHsypOPPg` の控えは 2026-08-31 22:xx に**入れ直したもの**です。
    # 投稿の回の控えは失われており、作り直した build から
    # **サムネイルの bytes だけ**を取りました。読み上げは別の生成なので、
    # **入れると「この本はこう喋っている」という嘘になります。**
    # 空のまま、`reconstructed` で出どころを申告しています。
    if not d.get("narration"):
        assert d.get("reconstructed"), (
            f"{video_id} の控えに読み上げ文が無く、出どころの申告もありません。"
            "**空の控えを黙って置かないこと** —— 次の回が本物と読みます"
        )
        assert d.get("reconstructed_note"), (
            "reconstructed の控えには、何をどう作り直したかを書くこと"
        )
        assert (ROOT / "data" / "critique_queue" / f"{video_id}.thumb.jpg").exists(), (
            f"{video_id} の控えは、せめてサムネイルの bytes を持っていること"
        )
