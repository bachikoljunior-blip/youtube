"""読み上げが、あとから直った calc とずれたことを、機械が言えること。

## 実物の当たり（2026-08-31）

`src/calc/hendo.py` の未払利息の二重取りを直した瞬間（commit `6ac53d4b`）、
**その calc に乗って既に投稿ずみだった `J67vEIw_VRE` の読み上げ19文のうち
5文が誤りになりました。** 見つけたのは人で、**機械は何も言っていません。**

`src/verify.py` が数字の出どころを見るのは `_check_headline_from_calc`
（**冒頭の stat 1つだけ**・呼ぶ側が `if portrait:` の中なので**ショート限定**）で、
**長尺の読み上げ全文を calc と突き合わせる目はどこにもありませんでした。**

この検査は、**その1本を実データで拾えること**を留めます。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import narration_drift  # noqa: E402


def test_金額の読み取り():
    """『661万1976円』も『5,716,767円』も同じ整数になること。"""
    assert narration_drift.yen("差は、661万1976円でした。") == {6_611_976}
    assert narration_drift.yen("差は5,716,767円。") == {5_716_767}
    assert narration_drift.yen("1億2000万円です") == {120_000_000}
    # 3桁以下の裸の数字は拾わない（回数・年齢と見分けが付かない）
    assert narration_drift.yen("108回 続きます") == set()


def test_二重取りの本を拾える():
    """**この検査の本体。** 直した calc に対して、古い読み上げが赤くなること。

    `J67vEIw_VRE` の誤った5文が引いていた数字:

        6,611,976   ルールあり／なしの総支払額の差（正しくは 5,716,767）
        70,108,284  ルールありの総支払額（正しくは 69,212,032）
        63,496,308  ルールなしの総支払額（正しくは 63,495,265）
        14,013,192  5.0% のときの差（正しくは 9,402,882）
        54,362      6年目に足りない額（正しくは 49,148）
        24,327      16年目に足りない額（正しくは 17,694）
    """
    rows = narration_drift.scan("J67vEIw_VRE")
    assert len(rows) == 1, (
        "二重取りに乗った本を拾えていません。"
        "**calc が直っても、その calc に乗った本は誰も見直しません**"
    )
    miss = set(rows[0]["missing"])
    for wrong in (54_362, 24_327, 14_013_192, 70_108_284, 63_496_308):
        assert wrong in miss, (
            f"{wrong:,} を拾えていません（未払利息の二重取りに乗った額）"
        )


def test_直した本は赤くならない():
    """**正しい本を落とさないこと。**

    同じ calc・同じテーマで、直した数字に乗って作り直した本があれば、
    それは赤くなってはいけません。無ければこの検査は飛ばします
    （**控えは投稿の回にしか作れない**ので、無いこと自体は異常ではない）。
    """
    import json
    stash = ROOT / "data" / "critique_queue"
    for meta_path in stash.glob("*.json"):
        if meta_path.name.endswith(".plan.json"):
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if meta.get("topic") != "hendo-mibarai-risoku":
            continue
        if meta_path.stem == "J67vEIw_VRE":
            continue
        rows = narration_drift.scan(meta_path.stem)
        assert not rows, (
            f"{meta_path.stem} は直した calc で作り直した本のはずですが、"
            f"出どころの無い額が出ています: {rows[0]['missing'] if rows else ''}"
        )


def test_門になっていない():
    """**投稿を止める仕掛けにしないこと**（`docs/trigger_main.md`）。

    実測で 14% が引っかかり、そこには言い換えも混ざります。
    `src/verify.py` から呼ばれていないことを留めます。
    """
    verify_src = (ROOT / "src" / "verify.py").read_text(encoding="utf-8")
    assert "narration_drift" not in verify_src, (
        "narration_drift を verify に繋いでいます。"
        "言い換えを引くので、正しい本まで作り直しに回ります"
    )
