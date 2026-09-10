"""**生きている検査が `-m live` から黙って落ちないこと**（2026-09-08 06:5x・optimizer・Opus）。

## なぜ要るか（実測で1件 落ちていた）

`pytest tests/` は 735ファイル・約9分 で、**旧道具の 2件 が赤**です（`studio/livetests.py` の docstring）。
そこで「生きている道具の検査だけ」を `-m live` で撃てるようにしましたが、
**その選び方が腐ると、緑は「壊れていない」を意味しなくなります**（撃った気になれるぶん、撃たないより悪い）。

腐り方は実測で分かっています: **名前で選ぶと落ちます。**
`tests/test_script_yomi_ignored.py` は `studio` を import しているのに `test_studio_*` に当たらず、
`pytest tests/test_studio_*.py` という自然な近道から**黙って落ちていました**（3件）。

だからこの検査は、**選び方そのもの**を見ます。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from studio import livetests as L  # noqa: E402


def _imports_studio(p: Path) -> bool:
    """**`livetests.IMPORTS_STUDIO` とは別に、ここで数え直します。**

    2026-09-08 06:5x に、この見張りの最初の形は `L.IMPORTS_STUDIO` を**両側**で使っており、
    **陽性対照で通り抜けました**（正規表現を壊すと候補も 0件 になり、差が空のまま緑）。
    `docs/METHOD.md` §5 の「必ず一致する2つ目の意見に、確かめる力は無い」の当のものです。
    だから**別の実装**（行ごとの素の突き合わせ）で候補を出し、規則Aの答えと突き合わせます。
    """
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.strip()
        if s.startswith(("from studio ", "from studio.", "import studio ",
                         "import studio.", "from studio\t", "import studio\t")):
            return True
        if s in {"import studio", "from studio import"}:
            return True
    return False


def test_studio_を_import_する検査は全部_live() -> None:
    """**規則A が本体です。** 新しい `studio` の検査を書いた回が、印を忘れても落ちない。"""
    missed = [p.name for p in L.TESTS.glob("test_*.py")
              if _imports_studio(p) and not L.is_live(p)]
    assert not missed, (
        f"`studio` を import しているのに live でない検査があります: {missed}。"
        "`studio/livetests.py` の規則A が効いていません")


#: **`livetests.PARENT_MODULES` を読まずに、ここに書き下す。**
#: 最初の形は `L.PARENT_MODULES` を借りていて、**陽性対照で通り抜けました**
#: （名前を壊すと候補も 0件 になり、差が空のまま緑 —— 06:5x に規則A で踏んだのと同じ穴を、
#:  同じファイルの中でもう一度 踏みました）。**借りると、見張りは規則と一緒に死にます。**
#:
#: **2026-09-10 12:1x（optimizer・Opus）に 2つ 足しました** —— `quota`（22:2x に
#: `PARENT_MODULES` へ入ったが、**この写しの側だけ据え置かれていた**）と `method_growth`。
#: 写しが片方だけ古いと、**規則C からその名前が落ちても、この見張りは黙ります**
#: （＝ 借りると死ぬのを避けて別実装にした意味が、名前の側で半分 消えていた）。
_PARENT_MODULES_HERE = ("next_round", "next_round_owner", "spawn_prompt", "quota", "method_growth")


def _imports_parent(p: Path) -> bool:
    """**規則C を、`livetests.IMPORTS_PARENT` とは別の実装で数え直す**（上と同じ理由）。"""
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.strip()
        if not (s.startswith("from scripts") or s.startswith("import scripts")):
            continue
        if any(m in s for m in _PARENT_MODULES_HERE):
            return True
    return False


def test_親の手続きを_import_する検査は全部_live() -> None:
    """**規則C。** 規則B（手で書く名簿）は、作られた次の回に忘れられました ——
    09/08 17:3x が足した `tests/test_parent_wake_log.py`（9件）は `EXTRA` に無く、
    `-m live` から**黙って落ちて**いました。import で引けば、忘れても落ちません。
    """
    missed = [p.name for p in L.TESTS.glob("test_*.py")
              if _imports_parent(p) and not L.is_live(p)]
    assert not missed, (
        f"親の手続きを import しているのに live でない検査があります: {missed}。"
        "`studio/livetests.py` の規則C が効いていません")


def test_忘れられていた_親の起きの台帳の検査が_live_であること() -> None:
    """**実際に落ちていた1件を名指しで見張る**（規則C が消えたら、ここが教える）。"""
    p = L.TESTS / "test_parent_wake_log.py"
    if not p.exists():           # 消したのなら、この検査は役目を終えている
        return
    assert L.is_live(p), "親の起きの台帳の検査が live から外れています"


def test_名指しした検査が実在すること() -> None:
    """**規則B は名指しなので、改名すると黙って落ちます。** ここで落とす。"""
    gone = sorted(n for n in L.EXTRA if not (L.TESTS / n).exists())
    assert not gone, (
        f"`studio/livetests.py` の EXTRA が実在しない名前を指しています: {gone}。"
        "改名したのなら EXTRA も直すこと（消したのなら EXTRA から外すこと）")


def test_この検査自身が_live_であること() -> None:
    """自分が選ばれていなければ、`-m live` の回はこの見張りごと撃っていない。"""
    assert L.is_live(Path(__file__)), "見張り自身が live から外れています"


def test_規則_B_を広げていないこと() -> None:
    """**「本文に `spawn_prompt` と書いてあれば live」に広げると 31ファイル 当たります**
    （大半は散文で名前に触れているだけの旧道具の検査）。広げた回をここで止める。"""
    assert len(L.EXTRA) <= 6, (
        f"規則B の名指しが {len(L.EXTRA)}件 に増えています。"
        "import で引けるなら規則A へ寄せること（`studio/livetests.py` の註）")


def test_live_が空でないこと() -> None:
    """規則が壊れて 0件 になったら、`-m live` は**必ず緑**になります（いちばん危ない壊れ方）。"""
    files = L.live_files()
    assert len(files) >= 10, f"live な検査が {len(files)}件 しかありません: {[p.name for p in files]}"
