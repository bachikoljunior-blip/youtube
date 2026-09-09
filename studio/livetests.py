r"""**どの検査が「生きている道具」の信号か**を、1か所で決める（2026-09-08 06:5x・optimizer・Opus）。

## なぜ要るか（前の回が「数を見てから決めろ」と残した所・`docs/JOURNAL.md` 09/07 20:1x の 5.）

`pytest tests/` は **741ファイル・約9分** かかり、**旧道具の検査 3件 が赤のまま**です:

    tests/test_bake_stage.py::test_枠までの線は実測より長いこと      線 150分 対 実測 210分（ahead_sweep）
    tests/test_kinds_allowed.py::test_止まるなら枠の本を名指しする    `vmAll8GDkU8` を名指しできない
    tests/test_live_ids_long_form.py::test_尺の分布は二山のまま       65〜175秒 の本が 2本 出て二山が割れた

どれも §8（`src/`・`scripts/` は使わない・**消さない**）の側で、**3つとも 09/05 の旧作りの本の状態を
当てにしています**（前の2つは private へ戻した本・3つ目は旧 `uploader.py` が上げた 153〜156秒 の 2本）。
直しようが無いのではなく、**当てにしている前提のほうを捨てた**ので赤い。

> **【2026-09-08 20:4x・optimizer・Opus】3つ目は、この註が「2件」と書いた時点で既に赤でした。**
> `3gZ38lfsJpY`（156.2秒）・`vmAll8GDkU8`（153.0秒）は **09/05 に旧 `uploader.py` が上げた本**なので、
> この文書が書かれた 09/08 06:5x には赤かったはずです ＝ **数えたのではなく、目に付いた2件を写していました。**
> 「上の2件は xfail なので（`pytest tests/` は）赤くない」も、そのぶん**本当ではありませんでした。**
> → 3つ目にも strict xfail を付け、この数を撃って数え直しました（`-m live` は 176件・7.6秒 で緑）。
> **教訓は この文書自身が書いていること**: **数は写しを持たない。撃って読む。**
> **覆る条件**: 4件目が赤になったら、それは旧道具の前提がまた1つ落ちた合図 ——
> xfail を足す前に、**`studio/` がその帳面を読んでいないこと**を先に確かめる
> （3つ目は `grep -rn 'uploaded.jsonl\|day_cap' studio/*.py` が 0件 なのを見てから xfail にした）。

**問題は「消すかどうか」ではありません** —— 赤が既定になると、**次の回は自分が壊したのかを見分けられません。**
9分 待って赤を見る検査は、撃たれなくなります。

## どう分けるか

**時間でも名前の見た目でもなく、「何を import しているか」で分けます。**
名前で分けると腐ります —— 実測: `tests/test_script_yomi_ignored.py` は `studio` を import しているのに
`test_studio_*` に当たらず、**`pytest tests/test_studio_*.py` という自然な近道から黙って落ちていました。**

    規則A（腐らない側）  `studio` を import している検査は、全部 live
    規則C（腐らない側）  **親の手続き**（`scripts/next_round.py`・`next_round_owner.py`・
                         `spawn_prompt.py`）を **import** している検査は、全部 live
    規則B（名指し）      import でも引けない側（本文や `docs/` を**読む**検査）だけ、名指し

規則B を「本文に `spawn_prompt` と書いてあれば live」に広げると **31ファイル** が当たります
（大半は散文で名前に触れているだけの旧道具の検査）。**広げないこと。**
**規則C は「本文への言及」ではなく import で引くので、当たるのは 7ファイル**（2026-09-08 19:2x に数えた）。

> **【2026-09-08 19:2x】規則B は、この註が予言したとおりに忘れられました**（optimizer・Opus）。
> 09/08 17:3x の回が `data/parent_wakes.jsonl` と検査 `tests/test_parent_wake_log.py`（**9件**）を
> 足しましたが、**`EXTRA` に名前を足していません** ＝ `-m live` はその 9件 を **1度も撃っていませんでした。**
> **規則B が書かれた次の回に、規則B が拾えない検査が生まれています** ——
> 「14個目を書いた回が忘れます」と下に書いてあるのと**同じ形**が、名簿の側で起きました。
> → 規則C（import で引く）を足し、`-m live` は **111件 → 174件**（8.3秒）になりました。
> **覆る条件**: 親の手続きの本体が増えたら `PARENT_MODULES` に足す
> （`tests/test_live_marker.py` が**自前の写しで**突き合わせるので、片方だけ直すと落ちます）。

## 使い方

    python -m pytest -m live -q      生きている信号（実測 23ファイル・174件・**8.3秒**）
    python -m pytest tests/ -q       旧道具ごと全部（約9分。上の2件は xfail なので赤くない）

**この数を写して引かないこと。撃って読むこと**（増えるのが正しい方向です）。

印を付けるのは `conftest.py` の `pytest_collection_modifyitems` で、**検査の側には1行も書きません**
（13ファイルに `pytestmark` を書く形にすると、14個目を書いた回が忘れます）。

**覆る条件**: (1) 規則A にも C にも当たらないのに生きている道具の検査が出たら、規則B に名指しで足す
（`tests/test_live_marker.py` が「名指しした名前が実在すること」を見ているので、改名では黙って落ちない）。
**足す前に、import で引けないかを先に見ること** —— 名簿は忘れられます（上の 19:2x）。
(2) 旧道具を使う判断が `docs/METHOD.md` に書かれたら（§8 の覆る条件）、この分け方ごと要らなくなる。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"

#: 規則A —— `from studio …` / `import studio…`（行頭の空白は許す ＝ 関数の中の import も拾う）
IMPORTS_STUDIO = re.compile(r"^[ \t]*(?:from|import)[ \t]+studio\b", re.M)

#: 規則C —— **親の手続きを import している検査**（2026-09-08 19:2x・optimizer・Opus が足した）。
#:
#: **なぜ足したか（実測）**: 規則B は手で書く名簿なので、**その註が予言したとおりに忘れられました。**
#: 09/08 17:3x の回が親の起きの台帳（`data/parent_wakes.jsonl`）と検査 `tests/test_parent_wake_log.py`
#: **9件** を足しましたが、**`EXTRA` に名前を足していません** ——
#: ＝ `pytest -m live` はその 9件 を **1度も撃っていませんでした**（この回に `is_live()` を撃って確かめた）。
#: **規則B が作られた次の回に、規則B が拾えない検査が生まれています。**
#:
#: **規則A と同じ形（import で引く）にすれば腐りません。** 親の手続きの本体は
#: `scripts/next_round.py`・`scripts/next_round_owner.py`・`scripts/spawn_prompt.py` の3つで、
#: **それを import する検査は、親の手続きの検査です。**
#: 註が警戒していたのは「**本文に名前が出てくれば live**」に広げる形（31ファイル 当たる）で、
#: **import に限れば 7ファイル**（この回に数えた。全部 緑・1.53秒）。**本文への言及では引かないこと。**
PARENT_MODULES = ("next_round", "next_round_owner", "spawn_prompt")
IMPORTS_PARENT = re.compile(
    r"^[ \t]*(?:from|import)[ \t]+scripts[ \t.].*?\b(?:%s)\b" % "|".join(PARENT_MODULES),
    re.M)

#: 規則B —— import でも引けない、親の手続きの検査（本文や `docs/` を**読む**側）。
#: **名指し。広げないこと**（上の註）。規則C が引けるものは、ここに足さないこと。
EXTRA = frozenset({
    "test_spawn_prompt_main_gap.py",
    "test_spawn_siblings_touched.py",
    "test_parent_record_before_spawn.py",
    # 第1節の git と「親がやらないこと」の禁止が食い違わないこと（`docs/` を読むだけ ＝ A も C も引けない）
    "test_parent_git_allowlist.py",
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
        text = p.read_text(encoding="utf-8")
    except OSError:
        return False
    return bool(IMPORTS_STUDIO.search(text) or IMPORTS_PARENT.search(text))


def live_files() -> list[Path]:
    """live な検査ファイルを、名前の順で。"""
    return sorted((p for p in TESTS.glob("test_*.py") if is_live(p)),
                  key=lambda p: p.name)
