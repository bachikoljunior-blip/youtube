#!/usr/bin/env python3
"""**積んである点に `imp_day_recent` が有っても、面は測り直す。**（2026-08-27）

## なぜこの検査が要るか（**足した門が、足した日から一度も効いていなかった**）

`scripts/eta.py` の `plan()` は、点を積んでいない窓でも段2 が読めるように
`_with_recent_surface()` で面だけ測り直します（`data/reach.jsonl` を読むだけ・
**API 0単位**）。その呼び出しに、こういう門が付いていました:

    if mix and not mix.get("imp_day_recent"):
        mix = _with_recent_surface(mix)

書いた当時、`_with_recent_surface()` が足す欄は `imp_day_recent` の**1つだけ**で、
「入っているなら測り直す必要はない」は正しかった。**その後この関数は欄を6つ足しました**
（`imp_day_recent_basis` / `imp_day_planned` / `imp_day_planned_pubs` /
`imp_day_per_publish` / `imp_day_dry_span` / `imp_ctr_long`）。
**`rpm_mix` の点は必ず `imp_day_recent` を持つので、門はいつも閉じ**、
**6つとも一度も入りませんでした。**

いちばん効いたのは `imp_ctr_long` です。`_gate2_surface_note()` は
2026-08-26 に「**面は足りていますを裸で出さないこと**」として
「実測の CTR は N% ＝ 合格点に M倍 足りません」を足しましたが、
あれは `others["ctr"]` が有るときだけ出ます。**空だったので、足した日から
1文字も出ていません。**

実測（2026-08-27・積んである点は 08-26 のもの・同じ `data/reach.jsonl`）:

    scripts/eta.py 段2      面 318.9回/日 → 「**面は足りています（1.8倍）**
                            —— 効くのは CTR のほう」（CTR の実測は出ない）
    src/reach_split.render() 「**足りないのはインプレッションで、
                            サムネと題（CTR）では動きません**」

**同じ帳面の読み手2つが、次に引く腕まで正反対に名指ししていました**（この形は5件目）。

もう1つ、`imp_day_recent` は 2026-08-26 に**定義そのものが変わっています**
（直近7日の平均 → 立ち上がりを外した中央値）。**古い点の値は「欠けている」のではなく
「違う」**ので、有無で測り直しを止める門は、そもそも成り立ちません。

## この検査が守ること

1. `_with_recent_surface()` は、`imp_day_recent` が**既に入っていても**
   帳面から測り直して上書きする（＝ 呼べば効く）
2. `_with_recent_surface()` が足す欄は `imp_day_recent` だけではない
   （**欄を足したときに、この検査が門の作り直しを止める**）
3. `_gate2_surface_note()` は、`ctr` が渡っていれば
   「面は足りています」と一緒に**実測の CTR と、合格点までの倍率**を必ず並べる
4. `plan()` の中に「`imp_day_recent` が有るなら測り直さない」形が復活していない

**覆る条件**: `_recent_surface()` が重くなって1周を目立って延ばすようになったら、
止めるのは呼び出しではなく**あの関数の中身**のほう（いまは `lru_cache` 付きで
実測 0.1秒・API 0単位）。そのときは、この検査の 4 だけを外すこと ——
1〜3 は速さと関係ありません。
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _eta():
    """`scripts/eta.py` はパッケージ外なので、直に読む。"""
    spec = importlib.util.spec_from_file_location("eta_mod_surface", ROOT / "scripts" / "eta.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_点に面が入っていても測り直す():
    """**`imp_day_recent` が有ることを、測り直さない理由にしない。**"""
    eta = _eta()
    if eta._recent_surface() is None:
        return  # 帳面が読めない環境では、この検査は何も言わない
    stale = {"imp_day": 1368.0, "imp_day_recent": 318.85714285714283,
             "imp_day_recent_days": 7}
    out = eta._with_recent_surface(stale)
    assert out is not stale, "呼んでも元の辞書を返している"
    assert out.get("imp_day_recent") is not None
    # **上書きされていること。** 08-26 に定義が変わっているので、
    #     古い点の値をそのまま残すと「平均」と「中央値」が混ざります。
    assert out["imp_day_recent"] != stale["imp_day_recent"] or \
        out.get("imp_day_recent_basis"), "測り直した跡が1つも無い"


def test_足す欄は面の1つだけではない():
    """**欄が増えたときに、`imp_day_recent` の有無で門を作り直させない。**"""
    eta = _eta()
    if eta._recent_surface() is None:
        return
    out = eta._with_recent_surface({"imp_day": 1368.0})
    added = set(out) - {"imp_day"}
    assert len(added) > 1, f"足した欄が1つしかない: {added}"
    # **CTR は、この検査の主眼です**（`_gate2_surface_note()` の `gap_ctr` の入力）。
    assert "imp_ctr_long" in added, f"CTR が入っていない: {sorted(added)}"


def test_面は足りていますを裸で出さない():
    """**CTR が渡っていれば、実測と倍率を同じ行に並べる。**"""
    eta = _eta()
    note = eta._gate2_surface_note(
        876.9, 178.0, basis="これからの予約から",
        others={"ctr": 1.44, "recent": 17.0})
    assert "面は足りています" in note
    assert "実測の CTR" in note, "面が足りている側で、CTR の実測が出ていない"
    assert re.search(r"倍 足りません", note), "合格点までの倍率が出ていない"


def test_面が足りない側はインプレッションを名指しする():
    """**逆の側も守る**（`reach_split.render()` と同じ向きであること）。"""
    eta = _eta()
    note = eta._gate2_surface_note(
        17.0, 178.0, basis="直近7日の中央値", others={"ctr": 1.44})
    assert "足りないのはインプレッション" in note
    assert "面は足りています" not in note


def test_古い門が復活していない():
    """**`imp_day_recent` の有無で測り直しを止める形を、二度と書かない。**"""
    src = (ROOT / "scripts" / "eta.py").read_text(encoding="utf-8")
    # コメント（`#` で始まる行）は、なぜやめたかの記録なので数えない。
    code = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
    bad = re.search(r"if\s+mix\s+and\s+not\s+mix\.get\(\s*[\"']imp_day_recent[\"']\s*\)", code)
    assert bad is None, (
        "`imp_day_recent` が入っているかで `_with_recent_surface()` を止めています。"
        "あの門は 2026-08-26〜08-27 のあいだ、CTR の実測を1文字も出させませんでした")
