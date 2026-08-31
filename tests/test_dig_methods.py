"""**在庫切れの回が読む助言が、道を1つしか名指ししていなかった**（2026-08-28）。

`topic_forge --list` は「未使用が0件です」のときに
`section_sweep --calc <族>` **だけ**を名指ししていました。
実測ではその候補の当たり率は **0/23** で、直近の在庫掘りは
**5回とも「族をまたいだ比較」**を採っています。

ここが守るのは3つです。

1. **`ship` だけを数えること。** `claim`（取りかかるの宣言）を混ぜると、
   「掃引でやる」と言って別の道で出した回が、掃引の実績に化けます
2. **否定形を数えないこと。** ship の1行には
   「掃引の候補は使っていない」が実際に書かれています
3. **当たった行を出すこと。** 散文を数えているので、次の回が検算できる形で出す
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import topic_forge  # noqa: E402


def _write(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "runs.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows),
                 encoding="utf-8")
    return p


def test_否定形の掃引を実績に数えない(tmp_path: Path) -> None:
    """**ship の1行に実際に書かれている言い回し**を、そのまま置いています。"""
    p = _write(tmp_path, [
        {"kind": "ship", "what": "means shougai に節を3つ足した"
                                 "（族をまたいだ比較・掃引の候補は使っていない）"},
    ])
    out = "\n".join(topic_forge.dig_method_lines(p))
    assert "族をまたいだ比較     **出した 1回**" in out
    assert "掃引の候補から      **出した 0回**" in out


def test_claimは実績に数えない(tmp_path: Path) -> None:
    """`claim` は「取りかかる」の宣言で、**出したとは限りません。**"""
    p = _write(tmp_path, [
        {"kind": "claim", "what": "keihi の掃引から節を足して在庫を戻す"},
        {"kind": "ship", "what": "means keihi に節を足した（族をまたいだ比較）"},
    ])
    out = "\n".join(topic_forge.dig_method_lines(p))
    assert "掃引の候補から      **出した 0回**" in out
    # 宣言のほうが多いときは、そう言うこと（黙って落とすと差が見えません）
    assert "取りかかると宣言した回は 1回" in out


def test_掃引を実際に使った回は数える(tmp_path: Path) -> None:
    """**片側だけ拾う作りになっていないこと。** 0 が出続けるのは実績であって、
    正規表現が壊れているせいであってはいけません。"""
    p = _write(tmp_path, [
        {"kind": "ship", "what": "means keihi の掃引の候補から節を2つ書いた"},
    ])
    out = "\n".join(topic_forge.dig_method_lines(p))
    assert "掃引の候補から      **出した 1回**" in out


def test_当たった行を出す(tmp_path: Path) -> None:
    """散文を数えているので、**次の回が検算できる形**で出すこと。"""
    p = _write(tmp_path, [
        {"kind": "ship", "what": "means nenkin に節を3つ（族をまたいだ比較）"},
    ])
    out = "\n".join(topic_forge.dig_method_lines(p))
    assert "└ means nenkin に節を3つ（族をまたいだ比較）" in out


def test_台帳が無くても落ちない(tmp_path: Path) -> None:
    """**在庫切れの助言そのものを止めないこと**（助言は台帳より大事）。"""
    out = "\n".join(topic_forge.dig_method_lines(tmp_path / "no-such-file.jsonl"))
    assert "runs.jsonl" in out


def test_在庫切れの助言に道が2つ出る() -> None:
    """**この検査の本体。** 助言が片方だけを名指しする形に戻ったら落ちます。"""
    src = (ROOT / "scripts" / "topic_forge.py").read_text(encoding="utf-8")
    head = src.split("**未使用が0件です。**", 1)
    assert len(head) == 2, "「未使用が0件です」の助言が消えています"
    block = head[1][:400]
    assert "dig_method_lines" in block, (
        "在庫切れの助言が、道の実績を出さない形に戻っています。"
        "`section_sweep` だけを名指しすると、当たり率 0/23 の一覧から始める回が出ます")


@pytest.mark.parametrize("name", [m[0] for m in topic_forge.DIG_METHODS])
def test_道の名前と説明がそろっている(name: str) -> None:
    got = [m for m in topic_forge.DIG_METHODS if m[0] == name][0]
    assert got[1] and got[2], f"{name} に正規表現か説明がありません"
