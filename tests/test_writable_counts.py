"""**「新しい候補」と「この回に書ける候補」は別の数**（2026-08-28）。

`status.py` の「(B) の候補」は長らく `novel_counts` の**生の数**だけを出し、
それを同点破りの第1キーにしていました。ところがその数には

    `[未]`     照合できる点が無い（`undecided()`。**新しいと分かっていない**）
    `片効き`   `SHAPE_LAST`。実測 32枠中14枠を占めて、書けた節は **0件**
    `不変`     同上
    `[並 N点]` `[坂]`  `unnameable()`。**その x を名指しできません**
    `[未刻]`   `_unrefined()`。印字が「そのまま節に書かないこと」と言っている側

が混ざっています。実測（2026-08-28・同じ回。**手で開けて確かめた4族**）:

    kafunenkin     新しい 8件 → **書けた 2件**（この回に2節 書いたので、いまは 0）
    furusato       新しい 5件 → **書けた 0件**（4件が「不変」）
    shitsugyo      新しい 0件 ← 印字も正しい
    ideco_deguchi  新しい 18件 → **0件**（最初の版は「8件」と出していた。**全部 `[未刻]` の崖**）

**見えないので、選ぶ側は撃って確かめていました**（3族・20分）。
ここが守るのは「引く対象がこの4つであること」と、
**`novel_counts` を1件も動かしていないこと**（在庫の数え方 `supply.SWEEP_YIELD`
がそちらを見ているので、同じ回に2つ動かすと切り分けられません）。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import section_depth, section_sweep  # noqa: E402


def _hit(calc: str, shape: str, value: float) -> dict:
    """`is_covered` / `undecided` が読める最小の候補。"""
    return {
        "表": calc,
        "関数": f"f_{shape}_{int(value)}",
        "形": shape,
        "見た値": "返り値",
        "動かした引数": "x",
        "x の幅": (1, 9),
        "詳しく": {"止まる x": 5, "止まった値": value},
    }


def test_片効きと不変は書ける数に入らない():
    hits = [_hit("a", "頭打ち", 123_456), _hit("a", "片効き", 234_567),
            _hit("a", "不変", 345_678)]
    got = section_sweep.writable_counts(hits, {"a": {}})
    assert got["a"] == 1, got


def test_節がもう言っている候補は書ける数に入らない():
    hits = [_hit("a", "頭打ち", 123_456)]
    # 節が x も値も印字していれば `is_covered`
    sections = {"a": {"見出し": "x が 5 から上は 123,456 で止まる"}}
    assert section_sweep.writable_counts(hits, sections)["a"] == 0


def test_書ける数は新しい数を超えない():
    hits = [_hit("a", "頭打ち", 123_456), _hit("a", "片効き", 234_567),
            _hit("b", "崖", 999_999)]
    _total, novel = section_sweep.novel_counts(hits, {})
    writable = section_sweep.writable_counts(hits, {})
    for name in novel:
        assert writable.get(name, 0) <= novel[name], (name, writable, novel)


def test_表が1つも無ければ空():
    assert section_sweep.writable_counts([], {}) == {}


def test_同点は書ける数で破る():
    """掘り甲斐が同じ2族なら、**書ける数の多いほうが先**。"""
    all_sections = {"a": {f"s{i}": "" for i in range(3)},
                    "b": {f"s{i}": "" for i in range(3)}}
    rows = section_depth.candidates(
        all_sections, scores={"a": 1.0, "b": 1.0}, limit=2,
        sweep_counts={"a": 10, "b": 10},
        novel_counts={"a": 9, "b": 9},        # **新しい数は同点**
        writable_counts={"a": 0, "b": 4},     # 書ける数だけが違う
    )
    assert [r[0] for r in rows] == ["b", "a"], rows


def test_書ける数を渡さなければ今までどおり新しい数で破る():
    all_sections = {"a": {f"s{i}": "" for i in range(3)},
                    "b": {f"s{i}": "" for i in range(3)}}
    rows = section_depth.candidates(
        all_sections, scores={"a": 1.0, "b": 1.0}, limit=2,
        sweep_counts={"a": 10, "b": 10},
        novel_counts={"a": 9, "b": 1},
    )
    assert [r[0] for r in rows] == ["a", "b"], rows


def test_報告の行に書ける数が出る():
    all_sections = {"a": {f"s{i}": "" for i in range(3)}}
    lines = section_depth.report_lines(
        all_sections, scores={"a": 1.0},
        sweep_counts={"a": 10}, novel_counts={"a": 6},
        writable_counts={"a": 2})
    body = "\n".join(lines)
    assert "書ける 2件" in body, body


def test_未刻の崖は書ける数に入らない():
    """`[未刻]` は印字が「崖かどうかは未判定です」と言っている側。

    実測 2026-08-28: `ideco_deguchi` は最初の版で「書ける 8件」と出ましたが、
    中身は **`years` を 20→22 と振って残高が 17億円 跳ぶ**ような格子の点で、
    節にできるものは残りませんでした（この引き算を入れて 8 → **0**）。
    """
    hit = _hit("a", "崖", 123_456)
    hit["詳しく"] = {"x の手前": 20, "x の先": 22, "跳ぶ幅": 1_704_745_251,
                     "中央の段差": 281_083_242.5, "細かく刻めなかった": "段が3つ未満"}
    assert section_sweep.writable_counts([hit], {"a": {}})["a"] == 0


def test_未刻の頭打ちも入らない():
    hit = _hit("a", "頭打ち", 123_456)
    hit["詳しく"] = {"止まる x": 5, "止まった値": 123_456,
                     "止まり際を刻めなかった": "TypeError"}
    assert section_sweep.writable_counts([hit], {"a": {}})["a"] == 0


def test_並ぶ点のある逆転は書ける数に入らない():
    """`unnameable()` の側（`[並 N点]`）。**その x を名指しできません。**"""
    hit = _hit("a", "逆転", 123_456)
    hit["詳しく"] = {"どこ": "いちばん高い", "x": 240, "値": 123_456,
                     "端では": 100, "並ぶ点": 3}
    assert section_sweep.writable_counts([hit], {"a": {}})["a"] == 0


def test_数え上げの同点は沈めない():
    """`unnameable()` の註どおり —— 行が数え上げなら、同点でも節になります。"""
    hit = _hit("a", "逆転", 123_456)
    hit["詳しく"] = {"どこ": "いちばん高い", "x": 240, "値": 123_456,
                     "端では": 100, "並ぶ点": 3, "数え上げ": True}
    assert section_sweep.writable_counts([hit], {"a": {}})["a"] == 1


def test_書けるものが0件なら_そう言う():
    all_sections = {"a": {f"s{i}": "" for i in range(3)}}
    lines = section_depth.report_lines(
        all_sections, scores={"a": 1.0},
        sweep_counts={"a": 10}, novel_counts={"a": 5},
        writable_counts={"a": 0})
    assert "書けるものは0件" in "\n".join(lines)
