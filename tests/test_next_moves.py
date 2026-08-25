"""`next_if_false` は、一覧でも文字列でも「手の一覧」になること。

**2026-08-17 12:3x に踏んだ穴の検査です。**

`status.py` は `h.get("next_if_false") or []` をそのまま `for` に渡していました。
実物の `config/hypotheses.yaml` は 20件中 4件が**まるごとの文字列**（YAML の `|`）で、
**Python の文字列は1字ずつ回ります。** 結果、1件の手が「- あ」「- な」…と散り、
**出力 644行のうち 480行が1字**になりました。埋もれたのは前提・警告の当たり率・
使用量で、`docs/trigger_main.md` §3「全部に目を通すこと」が**読めない状態**でした。

**緑のまま壊れます** —— 例外は出ず、件数も減らず、ただ読めなくなるだけなので、
検査が無ければ次の回も同じものを見ます。
"""
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import status  # noqa: E402


def test_string_stays_one_move():
    """**これが本体。** 文字列は1件であって、1字ずつではない。"""
    moves = status.next_moves({"next_if_false": "倍率を外して engaged だけに戻す"})
    assert moves == ["倍率を外して engaged だけに戻す"]


def test_string_is_not_split_into_characters():
    """1字の手が出たら、それは `for` が文字列を回った跡です。"""
    moves = status.next_moves({"next_if_false": "やめる"})
    assert not any(len(m) == 1 for m in moves), moves


def test_list_is_unchanged():
    moves = status.next_moves({"next_if_false": ["A を試す", "B を試す"]})
    assert moves == ["A を試す", "B を試す"]


@pytest.mark.parametrize("raw", [None, "", [], "   "])
def test_empty_forms_give_nothing(raw):
    assert status.next_moves({"next_if_false": raw}) == []


def test_missing_key_gives_nothing():
    assert status.next_moves({}) == []


def test_blank_line_splits_paragraphs():
    """**段落は割るが、改行だけでは割らない。**

    ブロックで書かれた1件の手は、途中で折り返されているだけのことがあります
    （実物の4件がそう）。**改行で割ると、1件が4件に見えて件数が嘘になります。**
    """
    raw = "戻すのではなく、割るのをやめる。\n2026-08-15 に実測したとおり。\n\nそれでも動かなければ形式を疑う。"
    moves = status.next_moves({"next_if_false": raw})
    assert len(moves) == 2
    assert moves[0].startswith("戻すのではなく")
    assert moves[1] == "それでも動かなければ形式を疑う。"


def test_real_config_has_no_single_character_move():
    """**実物で見ること。** 手が1字なら、どこかで文字列が回っています。"""
    items = yaml.safe_load(
        (ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8")
    )["hypotheses"]
    for h in items:
        for m in status.next_moves(h):
            assert len(m) > 1, (h.get("claim"), m)


def test_real_config_string_forms_exist():
    """**文字列の形が実物から消えたら、この検査は空回りします。**

    「実物が全部一覧になったから緑」を「直った」と読み違えないための1件です
    （`docs/trigger_main.md` §4「足した検査は、緑のまま0件で通る」）。
    """
    items = yaml.safe_load(
        (ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8")
    )["hypotheses"]
    assert any(isinstance(h.get("next_if_false"), str) for h in items)


def test_status_output_is_not_flooded_by_characters():
    """故障注入ではなく**実物を通す**：1字だけの行が並んでいないこと。

    `status.py` は外の口が落ちても手元だけで出し切ります（`[!]` を頭に付けて）。
    だから API の有無によらず、この検査は走ります。
    """
    out = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "status.py")],
        capture_output=True, text=True, timeout=900,
    ).stdout
    lines = out.splitlines()
    splat = [ln for ln in lines if ln.strip().startswith("- ") and len(ln.strip()) == 3]
    assert len(splat) == 0, f"1字の手が {len(splat)} 行（全 {len(lines)} 行）"
