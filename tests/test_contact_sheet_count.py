"""**contact sheet の枚数が、動画のコマ数に届いていること**を固定する。

## なぜ要るか（2026-08-16）

`inspect_build.py` は長らく **8枚固定**でした。1本のコマ数は8ではありません ——
`9hqzUxqBjBE` の `slides_plan.json` は **13コマ**で、
**8枚の等間隔サンプルは5コマを飛ばしていました。**

飛ばされた中に**最後のコマ**が入ります。実測:

    計画の12番目  「あなたはどちら側　2/2」  A と B の両方
    sheet の最後  「あなたはどちら側」      **A だけ**

そして独立評価の2体が、別々の本について
**「最後のコマは選択肢Aだけで、Bが出ないまま終わる」**と書いて減点しました。
**動画には B が出ています。** 評価者が見ていたのは、
**終わりのコマを落とした sheet** です。

8/15 の「左上がサムネイルで、動画の一部ですらなかった」・
8/16 の「余った枠を最後のコマと読ませていた」と**同じ種類**で、
**3件とも『計器が、動画に無いものを見せた／あるものを隠した』**です。
独立評価の点は `config/hypotheses.yaml` の反証にかかっているので、
**計器のうそで引かれた点は、その予測をそのまま濁します。**

## ここで固定すること

1. 計画のコマ数を枚数に使うこと（**この直しの目的そのもの**）
2. 上限で頭打ちにすること（無限に大きい sheet は Read できない）
3. **明示した枚数を、こちらで上書きしないこと**
4. `slides_plan.json` が無くても落ちないこと（過去の build・長尺）
5. **足りないときに、足りないと言うこと** ——
   黙って足りない sheet は「全部見た」として読まれます
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import inspect_build  # noqa: E402


def _plan(tmp_path: Path, n: int) -> Path:
    work = tmp_path / "s-test"
    work.mkdir()
    (work / "slides_plan.json").write_text(
        json.dumps([{"kind": "stat", "headline": f"{i}"} for i in range(n)]),
        encoding="utf-8")
    return work


def test_計画のコマ数を読む(tmp_path):
    assert inspect_build.planned_frames(_plan(tmp_path, 13)) == 13


def test_計画が無ければ0(tmp_path):
    work = tmp_path / "s-none"
    work.mkdir()
    assert inspect_build.planned_frames(work) == 0


def test_壊れた計画で落ちない(tmp_path):
    work = tmp_path / "s-broken"
    work.mkdir()
    (work / "slides_plan.json").write_text("{ではない", encoding="utf-8")
    assert inspect_build.planned_frames(work) == 0
    (work / "slides_plan.json").write_text('{"list":"でない"}', encoding="utf-8")
    assert inspect_build.planned_frames(work) == 0


# **式を書き写さないこと。** 写すと、片方だけ直したときに検査は緑のまま通ります。
_chosen = inspect_build.tile_count


def test_実物の13コマで13枚になる():
    """`9hqzUxqBjBE` が実際に踏んだ形。**8枚では5コマ落ちる。**"""
    assert _chosen(13) == 13
    assert _chosen(13) > 8


def test_上限で頭打ちにする():
    assert _chosen(40) == 18


def test_下限を割らない():
    assert _chosen(2) == 6


def test_明示した枚数を上書きしない():
    assert _chosen(13, given=8) == 8


def test_計画が無ければ元の8枚():
    assert _chosen(0) == 8
