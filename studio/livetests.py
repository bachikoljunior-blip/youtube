"""**どの検査が「生きている道具」の信号か**を、1か所で決める（2026-09-08 06:5x・optimizer・Opus）。

## なぜ要るか（前の回が「数を見てから決めろ」と残した所・`docs/JOURNAL.md` 09/07 20:1x の 5.）

`pytest tests/` は **735ファイル・約9分** かかり、**旧道具の検査 2件 が赤のまま**です:

    tests/test_bake_stage.py::test_枠までの線は実測より長いこと     線 150分 対 実測 210分（ahead_sweep）
    tests/test_kinds_allowed.py::test_止まるなら枠の本を名指しする   `vmAll8GDkU8` を名指しできない

どちらも §8（`src/`・`scripts/` は使わない・**消さない**）の側で、**2つとも 09/05 に private へ戻した
旧作りの本の状態を当てにしています**。直しようが無いのではなく、**当てにしている前提のほうを捨てた**ので赤い。

**問題は「消すかどうか」ではありません** —— 赤が既定になると、**次の回は自分が壊したのかを見分けられません。**
9分 待って赤を見る検査は、撃たれなくなります。

## どう分けるか

**時間でも名前の見た目でもなく、「何を import しているか」で分けます。**
名前で分けると腐ります —— 実測: `tests/test_script_yomi_ignored.py` は `studio` を import しているのに
`test_studio_*` に当たらず、**`pytest tests/test_studio_*.py` という自然な近道から黙って落ちていました。**

    規則A（腐らない側）  `studio` を import している検査は、全部 live
    規則B（名指し）      親の手続き（`scripts/spawn_prompt.py`・`scripts/next_round.py` の GO の枝・
                         `docs/trigger_parent.md`）を見る検査 —— import では引けないので名指し

規則B を「本文に `spawn_prompt` と書いてあれば live」に広げると **31ファイル** が当たります
（大半は散文で名前に触れているだけの旧道具の検査）。**広げないこと。**

## 使い方

    python -m pytest -m live -q      生きている信号（実測 13ファイル・85件・**15秒**）
    python -m pytest tests/ -q       旧道具ごと全部（約9分。上の2件は xfail なので赤くない）

印を付けるのは `conftest.py` の `pytest_collection_modifyitems` で、**検査の側には1行も書きません**
（13ファイルに `pytestmark` を書く形にすると、14個目を書いた回が忘れます）。

**覆る条件**: (1) `studio` を import しないのに生きている道具の検査が出たら、規則B に名指しで足す
（`tests/test_live_marker.py` が「名指しした名前が実在すること」を見ているので、改名では黙って落ちない）。
(2) 旧道具を使う判断が `docs/METHOD.md` に書かれたら（§8 の覆る条件）、この分け方ごと要らなくなる。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"

#: 規則A —— `from studio …` / `import studio…`（行頭の空白は許す ＝ 関数の中の import も拾う）
IMPORTS_STUDIO = re.compile(r"^[ \t]*(?:from|import)[ \t]+studio\b", re.M)

#: 規則B —— import では引けない、親の手続きの検査。**名指し。広げないこと**（上の註）。
EXTRA = frozenset({
    "test_spawn_prompt_main_gap.py",
    "test_spawn_siblings_touched.py",
    "test_parent_record_before_spawn.py",
    # 旧道具を背景で起こす口が塞がっていること（§8「起こす口を全部 外すこと」の見張り・3回目）
    "test_no_background_kick.py",
})


def is_live(path: Path | str) -> bool:
    """その検査ファイルが「生きている道具」の信号か。"""
    p = Path(path)
    if p.name in EXTRA:
        return True
    if not p.name.startswith("test_") or p.suffix != ".py":
        return False
    try:
        return bool(IMPORTS_STUDIO.search(p.read_text(encoding="utf-8")))
    except OSError:
        return False


def live_files() -> list[Path]:
    """live な検査ファイルを、名前の順で。"""
    return sorted((p for p in TESTS.glob("test_*.py") if is_live(p)),
                  key=lambda p: p.name)
