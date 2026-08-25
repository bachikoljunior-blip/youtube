"""**呼んでいる名前が、実在するか**（2026-08-16 18:5x に実物で踏んだ）。

`scripts/unschedule.py` は `auth.youtube()` を呼んでいました。
**`src/auth.py` にそんな関数はありません**（あるのは `credentials()` だけ）。
道具は `AttributeError` で即死しますが、**呼ぶまで誰も気づきません** ——

    AttributeError: module 'src.auth' has no attribute 'youtube'

気づいたのは、この回が**作り直した本を差し替えようとして実際に叩いたとき**です。
それまで何日ぶんか、**「予約を外す」道具が死んだまま手順に載っていました。**

これは `pytest` が構造上いちばん拾いにくい形です ——
import は通る（呼び出しは `main()` の中）、検査も無い、
そして**その道具を呼ぶ回が来るまで緑のまま**。

だから静的に見ます。`<module>.<attr>` の形で書かれた参照のうち、
**その module が実在しない属性を指しているもの**を落とす。

**この検査は「呼ばれた道具」ではなく「書かれた行」を見るので、
一度も実行されていない道具でも拾えます。**
"""
from __future__ import annotations

import ast
import importlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 見にいく module。**`from src import X` で入ってくる、こちらが書いたものだけ。**
# 外部ライブラリを入れないのは、属性を動的に生やすものがあるためです
# （`googleapiclient` のように、実物を叩かないと形が決まらないものが混ざる）。
WATCHED = ("auth", "uploader", "visuals", "verify", "history", "alerts")


def _refs(path: pathlib.Path) -> list[tuple[int, str, str]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
    except SyntaxError:
        return []
    # その file が実際に import している名前だけを見る（同名の別物を拾わないため）
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("src"):
            for alias in node.names:
                imported.add(alias.asname or alias.name)
    out = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id in imported
                and node.value.id in WATCHED):
            out.append((node.lineno, node.value.id, node.attr))
    return out


def test_書かれている属性がすべて実在する():
    """**一度も実行されていない道具でも拾えること**が、この検査の値打ちです。"""
    mods = {name: importlib.import_module(f"src.{name}") for name in WATCHED}
    missing = []
    files = sorted(ROOT.glob("scripts/*.py")) + sorted(ROOT.glob("src/**/*.py"))
    assert files, "見にいく file が1つもありません（緑のまま0件で通る形）"
    seen = 0
    for path in files:
        for lineno, mod, attr in _refs(path):
            seen += 1
            if not hasattr(mods[mod], attr):
                missing.append(f"{path.relative_to(ROOT)}:{lineno} {mod}.{attr}")
    # **参照を1つも見つけられていないなら、この検査は何も見ていません。**
    # 0件で緑になる形を先に塞ぐ（`docs/trigger_main.md` §4）。
    assert seen > 0, "監視対象への参照が1件も見つかりません。抽出が壊れています"
    assert not missing, "実在しない属性を呼んでいます:\n  " + "\n  ".join(missing)


def test_unschedule_は生きている():
    """実物の再発そのもの。**import できることと、呼ぶ名前があること**は別です。"""
    sys.path.insert(0, str(ROOT / "scripts"))
    import unschedule  # noqa: E402

    assert hasattr(unschedule, "main")
    # 書き込みは1か所（`reschedule._update`）に寄せてあること。
    # ここに独自の `videos().update` が戻ったら、「片方だけ直す」形の再発です。
    src = (ROOT / "scripts" / "unschedule.py").read_text(encoding="utf-8")
    body = src.split('"""', 2)[-1]          # 冒頭の説明文は数えない
    assert "reschedule._update" in body
    assert 'update(part="status"' not in body, "書き込みの実装が2つに戻っています"
