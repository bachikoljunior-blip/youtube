"""**押したぶんが見えなくなる問題**に、錨を打ってあること。

## なぜ要るか（2026-08-29 に実測で踏んだ）

`scripts/fast_tests.py` の `DEFAULT_BASE` は幹（`origin/claude/...`）です。
ところが**サブに渡される本文は「節目ごとに commit して push すること。
最後にまとめないこと」を要求します**（`docs/spawn_prompt.md`）。

**この2つは正面から食い違います** —— 押した瞬間にその変更は幹に入るので、
`git diff origin/<幹>` は**指示どおりに働いた回ほど空になります。**

実測（4件 ship した回・5ファイルを変更）:

    [fast_tests] この回が触った .py: 0件（無し）
    494 passed in 561.55s

**9分21秒 かけて 494件 緑を出し、その回の変更を1件も見ていません。**
印字は緑なので、**撃たないより悪い**（撃った気になれる）。

直しは `round_start()` —— `data/runs.jsonl` の `kind="start"` を錨にして、
**この回の頭から後の commit** を名前だけ拾い直します。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import fast_tests as F  # noqa: E402


def test_押したぶんを拾う源が在ること() -> None:
    """**`git log --since` の源が消えたら、また 0件 に戻ります。**"""
    src = (ROOT / "scripts" / "fast_tests.py").read_text(encoding="utf-8")
    assert "--since=" in src, (
        "`changed_files` から `git log --since=` の源が消えています。"
        "幹との diff だけに戻ると、押した回は『触った 0件』になります")
    assert "round_start" in src


def test_印がなければ空を返す() -> None:
    """印を打たない回（親・オーナーとの会話）では錨を作らないこと。"""
    at = F.round_start()
    assert isinstance(at, str)          # 例外で落ちないことが本体


def test_錨は走った印の形と合っている() -> None:
    """`data/runs.jsonl` の `kind="start"` に `at` と `session` があること。

    **この2つが欄ごと変わったら `round_start()` は黙って空を返します** ——
    黙って空になると、症状は「また 0件」に戻るだけで気づけません。
    """
    runs = ROOT / "data" / "runs.jsonl"
    if not runs.exists():
        return
    starts = []
    for line in runs.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("kind") == "start":
            starts.append(row)
    if not starts:
        return                          # まだ1件も無い環境では何も言わない
    last = starts[-1]
    assert last.get("at"), f"start の印に `at` がありません: {last}"
    assert last.get("session"), f"start の印に `session` がありません: {last}"


def test_0件のときの文が原因を名指ししている() -> None:
    """**「`--base` が正しいか見ること」だけでは足りません。**

    読む側は自分の設定を疑い、**「指示どおり押した回は必ずこうなる」**という
    道具の作りのほうを疑いません。実際 08-29 の回がそう読み違えました。
    """
    src = (ROOT / "scripts" / "fast_tests.py").read_text(encoding="utf-8")
    assert "指示どおり働いた回ほどここが 0件 になります" in src, (
        "0件 のときの文から、原因の名指しが消えています")
