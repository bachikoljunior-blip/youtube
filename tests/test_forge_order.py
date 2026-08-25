"""新しい節を書く先を、**実績で選ぶ**（`topic_forge.assign`）。

## なぜ（2026-08-16 に実物で踏んでから直しています）

M15 で `pick` は「作る題材の順番を実績で決める」ようになりました。**ところが
その手前 —— どの族に在庫を作るか —— は『未使用の節が多い順』のままでした。**

**この2つは逆を向きます。** 節をよく使っている族ほど余りが減るので、
**当たっている族ほど後ろに回されます。** 実測（同日 09:5x）:

    実績上位3族  nenkin 45.5% / shitsugyo 45.6% / furusato 38.7%  → 未使用 0〜1件
    未測定       yukyu 4件・jikangai 2件                          → 余りを独占

3回まわして**3件とも yukyu・jikangai** に行き、この回に足した `shitsugyo` の節は
1件も取れませんでした。**M15 は、順番を付ける相手が全部未測定なら何も選べません。**

**「片方だけ直す」の7回目**です（順番を付ける側は直り、材料を作る側は前のまま）。
"""
from __future__ import annotations

import importlib.util

import pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("topic_forge",
                                              ROOT / "scripts" / "topic_forge.py")
forge = importlib.util.module_from_spec(spec)
sys.modules["topic_forge"] = forge
spec.loader.exec_module(forge)

from src import family_perf


@pytest.fixture
def 実績(monkeypatch):
    """**族べつの実績を、この検査のあいだだけ止める。**

    ## なぜ止めるのか（2026-08-25。**2件とも赤のまま何日も置かれていました**）

    ここは長く、実物の `family_perf.scorer()` をそのまま呼んで
    `shitsugyo` が先に来ることを期待していました。**それは実装ではなく
    「いまのデータ」を書いた検査です。** 実測が動けば、実装が正しいまま赤くなります。

        2026-08-16（この検査を書いた日）  shitsugyo 45.6% ／ yukyu 未測定＝全体平均
        2026-08-25（いま）               shitsugyo **0.355** ／ yukyu **0.422**

    `yukyu` に再生が付いて、**本当に上に来ました。** つまり `assign` は正しく
    `yukyu` を選んでおり、**落ちているのは検査の思い込みのほうです。**

    赤が居すわると、**全体の検査そのものが読まれなくなります**（実際
    「前からの赤6件」として何日も素通りされていました）。だから
    **実績は差し替え、この検査は「順番の付け方」だけを見ます。**
    """
    from src import family_perf
    scores = {"shitsugyo": 0.9, "yukyu": 0.1}
    monkeypatch.setattr(family_perf, "scorer",
                        lambda *a, **k: (lambda calc: scores.get(calc, 0.5)))
    return scores


def test_余りの多い族より実績の高い族が先(実績):
    """**これが本体。** 余り1件の高実績を、余り4件の低実績より先に取ること。"""
    free = {"shitsugyo": ["=== A ==="],
            "yukyu": ["=== B ===", "=== C ===", "=== D ===", "=== E ==="]}
    picked = forge.assign(free, 1)
    assert picked == [("shitsugyo", "=== A ===")], picked


def test_在庫が尽きた族は回り番から落ちる(実績):
    """順番は実績で決めますが、**無い在庫からは取れません。**"""
    free = {"shitsugyo": ["=== A ==="], "yukyu": ["=== B ===", "=== C ==="]}
    picked = forge.assign(free, 3)
    assert len(picked) == 3
    assert picked[0][0] == "shitsugyo"
    # 尽きた後は残っている族から取る（件数が減らないこと）
    assert [m for m, _ in picked].count("yukyu") == 2


def test_実績の高い族が先という向きは実物でも保たれる():
    """**実物では、どの族が上かを書かないこと**（上の fixture の理由）。

    見るのは向きだけ ——「`assign` が返す順は `scorer` の降順」。
    これなら実測が動いても落ちません。
    """
    from src import family_perf
    score = family_perf.scorer()
    free = {"shitsugyo": ["=== A ==="], "yukyu": ["=== B ==="],
            "nenkin": ["=== C ==="], "jikangai": ["=== D ==="]}
    mods = [m for m, _ in forge.assign(free, len(free))]
    got = [score(m) for m in mods]
    assert got == sorted(got, reverse=True), list(zip(mods, got))


def test_calc_をばらして取る():
    """まとめ取りすると同じ計算が並び、量産判定に当たります。"""
    free = {"shitsugyo": ["=== A1 ===", "=== A2 ==="],
            "yukyu": ["=== B1 ===", "=== B2 ==="]}
    mods = [m for m, _ in forge.assign(free, 4)]
    assert mods[0] != mods[1], mods


def test_未知の族は全体平均で入る():
    """**探索を殺さないこと。** 実績の無い calc が最下位固定になると、
    新しい族は永久に試されません。"""
    score = family_perf.scorer()
    base = score("この名前の calc は存在しない")
    known = [score(m) for m in ("shitsugyo", "nenkin", "kojo")]
    assert min(known) <= base <= max(known), (base, known)


def test_実績が読めなくても止まらない(monkeypatch):
    """**故障注入。** 在庫づくりは、計器が落ちても続くこと（投稿が途切れるほうが高い）。"""
    def boom():
        raise RuntimeError("実績が読めない")
    monkeypatch.setattr(family_perf, "scorer", boom)
    free = {"shitsugyo": ["=== A ==="], "yukyu": ["=== B ===", "=== C ==="]}
    picked = forge.assign(free, 1)
    # 落ちた回は前の並び（余りの多い順）に戻る
    assert picked == [("yukyu", "=== B ===")], picked
