"""`upload_only.py` は、contact sheet が無ければ**自分で作る**。

## なぜ要るか（2026-09-01 に踏んで足した）

`critique_queue.stash()` は `inspect.jpg` が無いと**何もせずに帰ります**。
そして **`--dry-run` の `src/pipeline` は contact sheet を作りません**
（あれは `scripts/inspect_build.py` という別の道具）。

つまり **`--dry-run` で焼いて `upload_only.py` で上げる道**を通った本は、
**必ず独立評価（M13）を回せません。** 2026-09-01 に `ICmIBsZRYFE` で実際に踏み、
手で `inspect_build.py` を撃ち直して材料を残しています。

**この道は抜け道ではありません。** 日枠が尽きた窓では `pipeline` の
`history.posted_topic_ids()` が 403 になるので、`--dry-run` ＋ `upload_only.py` が
**唯一 通る道**です（`docs/trigger_main.md`「枠が尽きている回に選ぶのは、これです」）。
**枠が細い日ほど、この穴に落ちます。**

**覆る条件**: `src/pipeline` が `--dry-run` でも contact sheet を焼くようになったら、
`upload_only.py` のこの段ごと消してよい（そのときはこの検査も消すこと）。
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = (ROOT / "scripts" / "upload_only.py").read_text(encoding="utf-8")


def _at(pattern: str) -> int:
    """**その行が「実行される行」であるところ**の位置を返す。

    註のなかで同じ名前を挙げている行が先に当たるので、`str.find` は使えません
    （この検査は最初それで2件 落ちました。落ちていたのは検査の側です）。
    """
    m = re.search(pattern, SRC, re.M)
    assert m, f"実行される行が見つかりません: {pattern}"
    return m.start()


def test_sheetを作る段がstashより前にある():
    """順番が逆だと、作っても間に合わない。"""
    build = _at(r"^\s+inspect_build\.main\(")
    stash = _at(r"^\s+critique_queue\.stash\(")
    assert build < stash, "sheet を作る段が stash より後ろにあります"


def test_既にあるときは作り直さない():
    """`exists()` で守っていること（毎回 18コマ抜き直すのは高い）。"""
    head = SRC[:_at(r"^\s+inspect_build\.main\(")]
    assert re.search(r'not \(work / "inspect\.jpg"\)\.exists\(\)', head), head[-400:]


def test_落ちても投稿を止めない():
    """投稿はもう済んでいる。ここで例外を上げないこと。"""
    seg = SRC[_at(r'^\s+if not \(work / "inspect\.jpg"\)\.exists\(\):'):
              _at(r"^\s+critique_queue\.stash\(")]
    assert "try:" in seg and "except Exception" in seg, seg


def test_inspect_buildにmainがある():
    """呼び先の形が変わったら、ここで気づく。"""
    other = (ROOT / "scripts" / "inspect_build.py").read_text(encoding="utf-8")
    assert re.search(r"^def main\(topic: str", other, re.M), "呼び先の main が変わりました"
