"""**同じ表を別の見出しで出す2本を、選ぶ前に外す。**

## なぜ要るか（2026-08-29 に踏んだ。**2本 作って 0本**）

`--per-calc 2` は「同じ制度が並びすぎないように」の上限で、
**選んだ2本が同じ数を出すかどうかを1文字も見ていません。**
`used_sections` は節が違うことしか見ず、**節が違っても数は被ります。**

実測（`shogaku` の2本・09/17 へ入れようとした回）:

    shogaku-years-total-repay    RuntimeError: 台本の時点で過去の図と重なっています
    shogaku-murishi-sa-1458282   VerificationError: 投稿前の検査に落ちました
    どちらも「図の棒が … と 2本 共通（447万4969円・894万9938円…）」

**2本とも落ちました。** しかも `--jobs 2` で同時に作るので、
`script_writer.used_bars()` が読む `build/*/script.json` に
**相手の台本がまだ存在しません** —— 書き手には避けようがありません。
そして `--no-retry` を付けない回は**同じ2本を作り直し**、落ち方は決まっているので
**作り直しも必ず落ちます**（実測 約13分 × 2 を捨てた）。

## 線の引き方は実測です

最初は「共通が `verify.REPEAT_BARS`（2）以上」で書いて外しました ——
**実際に通って予約に入っている 23組 のうち 15組**がその線に当たります。
予約の実物で測り直した結果:

    通った 23組     Jaccard の最大 **0.31** ／ 共通の本数の最大 **11本**
    落ちた  1組     Jaccard **0.67**（共通12・片方が丸ごと部分集合）

だから見るのは**共通の本数ではなく重なりの割合**で、線は 0.45。
**包含率では引けません** —— 数を2つしか持たない節は必ず 1.00 になり、
実際 `mishikyu` の1組が 1.00 のまま通っています。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import batch_build as B  # noqa: E402
from src import config, verify  # noqa: E402


def _topics() -> dict[str, dict]:
    return {t["id"]: t for t in config.load_topics()["topics"]}


def test_落ちた実物の組を選ぶ前に外す() -> None:
    """**この2本が同じ回に選ばれたら、また 0/2 になります。**"""
    t = _topics()
    a, b = t.get("shogaku-murishi-sa-1458282"), t.get("shogaku-years-total-repay")
    if not a or not b:
        return                      # テーマが消えたら、この実物での検査は終わり
    assert B._bars_clash(a, b), (
        "2026-08-29 に 2本とも落ちた組を、この門が通しています。"
        f"共通 {len(B._section_numbers(a) & B._section_numbers(b))}個")


def test_別のcalcは見ない() -> None:
    """calc をまたぐ重なりは `_queue_tail_calcs` の担当。**二重に見ない。**"""
    a = {"id": "x", "calc": "ribo", "calc_sections": []}
    b = {"id": "y", "calc": "shogaku", "calc_sections": []}
    assert not B._bars_clash(a, b)


def test_読めないcalcで投稿を止めない() -> None:
    """表が落ちても pick は進むこと（**この門で投稿を止めない**）。"""
    a = {"id": "x", "calc": "そんな計算はない", "calc_sections": []}
    b = {"id": "y", "calc": "そんな計算はない", "calc_sections": []}
    assert B._section_numbers(a) == set()
    assert not B._bars_clash(a, b)


def test_線は実測の外側にある() -> None:
    """**通った 0.31 と 落ちた 0.67 のあいだ**に線があること。

    どちらかへ寄せたら、この検査が落ちます ——
    **寄せるなら、寄せる理由になった実測を docstring に足すこと。**
    """
    assert 0.31 < B.BARS_CLASH_JACCARD < 0.67


def test_4桁未満は数えない() -> None:
    """年数・率・段の番号はどの表にも出るので、拾うと当たり前に被ります。"""
    hits = {m.group(0) for m in B._BIG_NUMBER.finditer("3年 12% 999 1,000 4474969")}
    assert hits == {"1,000", "4474969"}, hits


def test_verifyの門と同じ語を持っている() -> None:
    """**この門は `verify` の代わりではありません。** 先回りするだけ。

    `verify.REPEAT_BARS` が消えたら、先回りする理由もありません。
    """
    assert verify.REPEAT_BARS >= 1
