"""`src/watches.py` と `config/watches.yaml` の検査。

**この検査の本体は最後の1件（`test_待ちを印字するファイルは台帳にあるか`）です。**
残りは台帳そのものが壊れていないことを見ています。

2026-08-20 に踏んだ壊れ方はこうでした ——
`scripts/retention.py` が「30秒設計の3本が出れば測れるようになります」と印字し、
**その3本は出たのに、10日間だれも気づかなかった。**
待ちを書いた回と、条件が満ちる回は別の回なので、**印字では繋がりません。**
だから「まだ判定できません」と印字するファイルは、
**台帳に載るか、載せない理由を書くか**のどちらかを強制します。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import watches  # noqa: E402


#: 「いまは測れない」と読める印字。**待ちがあるという合図。**
GATE_PHRASES = ("判定できません", "まだ判定しない", "測れるようになります",
                "検定は今回効きません")


def _registry():
    return watches.load()


def test_台帳が読めてidが重複していない():
    ws = _registry()
    assert ws, "待ちが1件もありません"
    ids = [w.id for w in ws]
    assert len(ids) == len(set(ids)), f"idが重複しています: {ids}"


@pytest.mark.parametrize("field", ["what", "cond", "then", "source"])
def test_どの待ちも空欄がない(field):
    for w in _registry():
        assert getattr(w, field).strip(), f"{w.id} の {field} が空です"


def test_どの待ちも実装のある種類を指している():
    for w in _registry():
        assert w.kind in watches.KINDS, f"{w.id} の kind `{w.kind}` に実装がありません"


def test_どの待ちも実際に評価できる():
    """**計器が落ちても回は止めない。ただし黙らない。**

    手元の材料が欠けている回は `err` に理由が入ります（例外は投げません）。
    ここで見るのは「例外で落ちないこと」と「数が入っていること」です。
    """
    for w in _registry():
        g = w.gauge()
        assert isinstance(g, watches.Gauge)
        assert g.need > 0, f"{w.id} の need が 0 です（満ちる条件になりません）"


def test_満ちて答えの無い待ちは大きく鳴る():
    w = watches.Watch(id="試験", what="試し", cond="0以上", then="何かする",
                      source="tests", kind="length_spread", params={"need": 0.0})
    out = watches.render([w])
    assert "満ちました" in out and "何かする" in out
    assert "answered" in out, "答えの書き方が画面に出ていません"


def test_満ちて答えのある待ちは1行に畳む():
    w = watches.Watch(id="試験", what="試し", cond="0以上", then="何かする",
                      source="tests", kind="length_spread", params={"need": 0.0},
                      answered="2026-08-20 判定済み")
    out = watches.render([w])
    assert "満ちました" not in out
    assert "済 試験: 2026-08-20 判定済み" in out


def test_まだの待ちは残りを数で出す():
    w = watches.Watch(id="試験", what="試し", cond="巨大", then="何かする",
                      source="tests", kind="length_spread", params={"need": 99.0})
    out = watches.render([w])
    assert "あと" in out and "99" in out


def test_読めない待ちも節を落とさない():
    w = watches.Watch(id="試験", what="試し", cond="?", then="?", source="tests",
                      kind="存在しない種類", params={})
    out = watches.render([w])
    assert "読めません" in out and "試験" in out


def _flagged() -> dict[str, list[str]]:
    """「いまは測れない」と**印字している**ファイルを拾う（註釈は除く）。"""
    out: dict[str, list[str]] = {}
    for path in sorted(list((ROOT / "scripts").glob("*.py"))
                       + list((ROOT / "src").rglob("*.py"))):
        for line in path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s.startswith("#") or not re.search(r"[\"']", line):
                continue
            if any(p in line for p in GATE_PHRASES):
                out.setdefault(str(path.relative_to(ROOT)), []).append(s[:70])
    return out


def test_待ちを印字するファイルは台帳にあるか免除に理由がある():
    """**この検査が、同じ壊れ方を二度させないための本体です。**

    新しく「まだ判定できません」と印字する道具を書くと、ここが落ちます。
    直し方は2つだけ:

        1. `config/watches.yaml` の `watches:` に、満ちる条件を**数で**足す
        2. 待ちではないなら `exempt:` に**理由**を書く（黙って外せません）
    """
    sources = {w.source for w in _registry()}
    allowed = watches.exempt()
    missing = {f: ls for f, ls in _flagged().items()
               if f not in sources and f not in allowed}
    assert not missing, (
        "「いまは測れない」と印字しているのに、待ちの台帳にありません:\n"
        + "\n".join(f"  {f}: {ls[0]}" for f, ls in missing.items())
        + "\n  → config/watches.yaml の watches: に数で足すか、exempt: に理由を書くこと"
    )


def test_免除には理由が書いてある():
    for path, why in watches.exempt().items():
        assert len(why.strip()) >= 20, f"{path} の免除に理由がありません"
        assert (ROOT / path).exists(), f"{path} はもうありません（免除も消すこと）"
