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


# --------------------------------------------------- 仮説の側から見張る（穴C）
#
# **印字を見張るだけでは足りません**（2026-08-20 に足した）。
# 待ちが次に書かれる場所は、道具の print ではなく
# `config/hypotheses.yaml` の `falsified_if` です。そこには
# 「3,000再生に達した時点で」「6本たまった時点で」のような**数の門**が入ります。
# **門を書いたのに台帳に載せないと、満ちたことは誰にも届きません。**

#: `falsified_if` に「いつ測れるようになるか」が書いてある印。
GATE_IN_YAML = re.compile(
    r"(達した時点|たまった時点|溜まった時点|貯まった時点|満たなければ|"
    r"届いていなければ|届かなければ)")


def _open_hypotheses():
    import yaml

    doc = yaml.safe_load((ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
    return [h for h in doc.get("hypotheses", []) if not h.get("verdict")]


def test_数の門を持つ未判定の仮説は台帳を指している():
    """**門を書いたら、見張る先も書く。** 直し方は `watch:` を1行足すだけ。"""
    ids = {w.id for w in _registry()}
    bad = []
    for h in _open_hypotheses():
        if not GATE_IN_YAML.search(str(h.get("falsified_if", ""))):
            continue
        w = h.get("watch")
        if not w:
            bad.append(f"{h.get('deadline')} {str(h.get('claim'))[:34]} → watch: が無い")
        elif w not in ids:
            bad.append(f"{h.get('deadline')} {str(h.get('claim'))[:34]} → watch: {w} は台帳に無い")
    assert not bad, (
        "数の門を書いた未判定の仮説が、待ちの台帳を指していません:\n  "
        + "\n  ".join(bad)
        + "\n  → config/watches.yaml に待ちを足し、仮説に watch: <id> を書くこと")


def test_台帳が指されている仮説は判定済みでも壊れない():
    """判定が書かれた項の `watch:` は、あってもなくてもよい（消し忘れで落とさない）。"""
    ids = {w.id for w in _registry()}
    for h in _open_hypotheses():
        w = h.get("watch")
        assert w is None or w in ids


# --------------------------------------------------- 鳴り続けを数える（穴B）

def test_鳴った回を積んで回数を出す(tmp_path):
    ledger = tmp_path / "rings.jsonl"
    w = watches.Watch(id="試験", what="試し", cond="0以上", then="何かする",
                      source="tests", kind="length_spread", params={"need": 0.0})
    old = watches.RINGS
    try:
        watches.RINGS = ledger
        watches.note_rings([w], at="2026-08-20T10:00:00+09:00")
        watches.note_rings([w], at="2026-08-20T11:00:00+09:00")
        hist = watches.ring_history(ledger)
        assert hist["試験"][0] == 2
        assert hist["試験"][1].startswith("2026-08-20T10")
        out = watches.render([w])
        assert "2回鳴っています" in out, "放置の長さが画面に出ていません"
    finally:
        watches.RINGS = old


def test_答えを書いた待ちは鳴らない():
    w = watches.Watch(id="試験", what="試し", cond="0以上", then="何かする",
                      source="tests", kind="length_spread", params={"need": 0.0},
                      answered="2026-08-20 判定済み")
    assert watches.unanswered([w]) == []


def test_満ちて答えの無い待ちはunansweredに出る():
    w = watches.Watch(id="試験", what="試し", cond="0以上", then="何かする",
                      source="tests", kind="length_spread", params={"need": 0.0})
    assert [x.id for x in watches.unanswered([w])] == ["試験"]


def test_記録しないのが既定():
    """検査や下見で `render` を呼んでも、帳面を汚さないこと。"""
    w = watches.Watch(id="試験", what="試し", cond="0以上", then="何かする",
                      source="tests", kind="length_spread", params={"need": 0.0})
    before = watches.RINGS.read_text(encoding="utf-8") if watches.RINGS.exists() else ""
    watches.render([w])
    after = watches.RINGS.read_text(encoding="utf-8") if watches.RINGS.exists() else ""
    assert before == after
