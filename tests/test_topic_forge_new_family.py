"""**「いちばん速い道」だけが、機械から撃てませんでした。**（2026-08-29）

`scripts/topic_forge.py --list` は 2026-08-29 15:5x から、長尺の族を増やす道を
3つ印字します。ところが機械が撃てるのは (1) と (2) だけでした ——
`assign()` は `free`（**未使用の節**）からしか取らないためです。

    (1) `src/calc/` に新しい表を書く              実測 20〜25分
    (2) 既にある表に**節を足して** `--long`        実測 15分
    (3) **既にある節**に、長尺の題を書く          実測 5分・**いちばん速い**

## 実測（2026-08-29 16:5x・この検査を書いた回）

    全620節のうち **未使用は 10件**
    その10件が乗っている族は genjokaifuku / shogaku / teiji
    → **3つとも、もう長尺の族**（`long_form_families()` に入っている）

つまり **`--long` を何回 撃っても、族は1つも増えません。**
`yoteinozei`（節7・未使用0）のような族は、`free` が空なので永久に選ばれない。

そして `scripts/eta.py` は長尺の律速をこう名指ししています ——
**「長尺の律速は族の数: あと 68族（要る 77 ／ いま 9）」**。
7日ぶんの上限は `min(長尺の在庫, 族の数 × 2)` なので、
**族が増えないかぎり上限は動きません。**

## なぜ目標の話なのか

収益化の門2a（直近12か月 4,000時間）に入るのは**長尺だけ**です
（ショートの視聴時間は1分も入りません）。その長尺の本数を縛っているのが
族の数で、族を増やすいちばん速い道が**手作業のまま**でした。

## この検査が固定していること

  1. `assign_new_families` は **`long_form_families()` に入っていない族**しか返さない
  2. **未使用の節が1件も無い族でも取れる**（(3) の要点。`free` が空でも返る）
  3. 既定は **1族1件**（族を横に増やすため）。`--per-family` で厚くできる
  4. 実績（`family_perf.scorer()`）の高い族が先に来る

**覆る条件**: `batch_build` の `--per-calc` が族あたり2本の上限を外したら、
族の数は律速でなくなるので、この道と検査は要りません
（`src/section_depth.long_form_families()` の覆る条件と同じ）。
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location(
    "topic_forge", ROOT / "scripts" / "topic_forge.py")
forge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(forge)


SECTIONS = {
    # 未使用が1件も無い族。**(2) では永久に選ばれない側**
    "yoteinozei": {"=== A ===": "1", "=== B ===": "2"},
    "kokuho": {"=== C ===": "3", "=== D ===": "4"},
    "taishoku": {"=== E ===": "5"},
    # もう長尺のテーマを持っている族（除かれる側）
    "nenkin": {"=== F ===": "6", "=== G ===": "7"},
    # 未使用が残っている族
    "kaigo": {"=== H ===": "8", "=== I ===": "9"},
}
FREE = {"yoteinozei": [], "kokuho": [], "taishoku": [],
        "nenkin": ["=== G ==="], "kaigo": ["=== I ==="]}


def test_未使用が0件の族からも取れる():
    """(3) の要点。`assign()` はここで1件も返しません。"""
    got = forge.assign_new_families(SECTIONS, FREE, 3,
                                    long_families={"nenkin"})
    mods = [m for m, _ in got]
    assert len(got) == 3, got
    # 未使用が0件の族が、少なくとも1つは入っていること
    assert {"yoteinozei", "kokuho", "taishoku"} & set(mods), mods
    # 比較: 既定の道は、未使用のある族しか返さない
    old = forge.assign(FREE, 3)
    assert {m for m, _ in old} <= {"nenkin", "kaigo"}, old


def test_長尺の族は返さない():
    got = forge.assign_new_families(SECTIONS, FREE, 5,
                                    long_families={"nenkin", "kaigo"})
    mods = {m for m, _ in got}
    assert "nenkin" not in mods, got
    assert "kaigo" not in mods, got
    assert mods == {"yoteinozei", "kokuho", "taishoku"}, got


def test_既定は1族1件():
    """族を横に増やすため。上限は `族の数 × 2` なので、厚みは後回し。"""
    got = forge.assign_new_families(SECTIONS, FREE, 4,
                                    long_families={"nenkin"})
    mods = [m for m, _ in got]
    assert len(mods) == len(set(mods)), mods


def test_per_family_で厚くできる():
    got = forge.assign_new_families(SECTIONS, FREE, 6,
                                    long_families={"nenkin"}, per_family=2)
    mods = [m for m, _ in got]
    assert len(got) == 6, got
    # **1周目で族を全部 出してから、2周目に入ること。**
    # （count が族の数より多いときだけ2件目が出る）
    assert len(set(mods[:4])) == 4, got
    assert max(mods.count(m) for m in set(mods)) == 2, got
    # 同じ (族, 節) を2回 返さないこと（`realign()` が後を落とすため）
    assert len(set(got)) == len(got), got


def test_節は未使用を先に取る():
    """使用済みでよいが、**残っている未使用を先に使うほうが安い**
    （使用済みの節から書くと `dupes.blocking` の `same-yen` に当たりやすい）。"""
    got = forge.assign_new_families(SECTIONS, {"kaigo": ["=== I ==="]}, 1,
                                    long_families=set())
    # kaigo だけを候補にすると、未使用の `I` が先に出る
    got = [p for p in forge.assign_new_families(
        {"kaigo": SECTIONS["kaigo"]}, {"kaigo": ["=== I ==="]}, 1,
        long_families=set())]
    assert got == [("kaigo", "=== I ===")], got


def test_実物の族でも1件は返る():
    """**実物の `config/topics.yaml` と `src/calc/` で撃って、空にならないこと。**

    ここが空を返すなら、族はもう増やせない（＝ 全族が長尺を持っている）ので、
    そのときは `long_form_families()` 側の覆る条件を読むこと。
    """
    all_sections, free, _ = forge.survey()
    got = forge.assign_new_families(all_sections, free, 4)
    assert got, "長尺のテーマを持っていない族が1つも無い"
    from src import section_depth
    have = section_depth.long_form_families() or set()
    assert not ({m for m, _ in got} & have), (got, sorted(have))
