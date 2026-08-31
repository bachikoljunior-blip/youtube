"""持ち越しの各行に付く「**実物に当たった回**」の数（`retro.worked_on()`）。

## なぜ要るか（2026-09-01 に実測してから足しています）

持ち越しの一覧は **言及の回数**で並んでいます。**言及は、実物に当たった証拠では
ありません** —— `retro.py` は閉じた側にはそう書いていました
（「［日誌の文］は散文から読み取ったもの。**言及の回数は証拠になりません**」）。
**開いている側に、その札がありませんでした。**

実測 `premise_subject`（4周・2026-09-01 01:4x〜06:2x）——
**4回とも「次の回へ」と書かれ、4回とも `--claim` が 0件。**
5周目に実物を開いたら、**申し送りの後半が事実と違って**いました
（「片方は YAML のコメントにしかありません」→ 実際は 2件とも `note:` に写しずみ）。
**直す先は台帳ではなく道具の側**で、`scripts/premise_subject.py` の 1関数・14行。

**「4回 言及・0回 実物」が1行に並んでいれば、4周 待たずに1周目で目立ちます。**

## 故障注入は両向き

**当たりを見つけることと、当たっていないものを鳴らさないことは別の性質**です
（`docs/JOURNAL.md` 2026-08-16）。ここでは
「当たった回を 0 と数えないこと」と「当たっていない語を 1 以上にしないこと」の
両方を固定します。
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("retro", ROOT / "scripts" / "retro.py")
retro = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(retro)


def _runs(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "runs.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                 encoding="utf-8")
    return p


def _use(monkeypatch, path: Path) -> None:
    monkeypatch.setattr(retro, "RUNS", path)


ROWS = [
    {"at": "2026-09-01T01:40:00+09:00", "session": "s#a", "kind": "start"},
    {"at": "2026-09-01T02:00:00+09:00", "session": "s#a", "kind": "claim",
     "what": "fix: premise_subject の [?] 2件。scripts/premise_subject.py"},
    {"at": "2026-09-01T02:30:00+09:00", "session": "s#a", "kind": "ship",
     "what": "fix: premise_subject が note: を読んでいなかった"},
    {"at": "2026-09-01T03:00:00+09:00", "session": "s#b", "kind": "ship",
     "what": "fix: pool_drain の順番"},
]


def test_同じ回のclaimとshipを二重に数えない(tmp_path, monkeypatch):
    """**行で数えると倍になります。** 1つの回が claim と ship を両方 出すので。"""
    _use(monkeypatch, _runs(tmp_path, ROWS))
    assert retro.worked_on(["premise_subject"]) == {"premise_subject": 1}


def test_触られていない語は0(tmp_path, monkeypatch):
    """**故障注入の逆向き。** 在るだけの語を 1 以上にしないこと。"""
    _use(monkeypatch, _runs(tmp_path, ROWS))
    assert retro.worked_on(["deixis_count"]) == {"deixis_count": 0}


def test_別々の回は別に数える(tmp_path, monkeypatch):
    rows = ROWS + [
        {"at": "2026-09-01T04:00:00+09:00", "session": "s#c", "kind": "claim",
         "what": "fix: premise_subject をもう一度"},
    ]
    _use(monkeypatch, _runs(tmp_path, rows))
    assert retro.worked_on(["premise_subject"]) == {"premise_subject": 2}


def test_start_の行は数えない(tmp_path, monkeypatch):
    """**印（`kind="start"`）は「走った」であって「当たった」ではありません。**"""
    rows = [{"at": "2026-09-01T01:00:00+09:00", "session": "s#z", "kind": "start",
             "what": "premise_subject"}]
    _use(monkeypatch, _runs(tmp_path, rows))
    assert retro.worked_on(["premise_subject"]) == {"premise_subject": 0}


def test_since_より前は数えない(tmp_path, monkeypatch):
    """**窓を渡さないと、半年前に一度 触った語まで「当たっている」に見えます。**"""
    _use(monkeypatch, _runs(tmp_path, ROWS))
    assert retro.worked_on(["premise_subject"], since="2026-09-01")["premise_subject"] == 1
    assert retro.worked_on(["premise_subject"], since="2026-09-02")["premise_subject"] == 0


def test_壊れた行と無い帳面で落ちない(tmp_path, monkeypatch):
    """**落ちても回は止めない。** 持ち越しの一覧は付け足しです。"""
    p = tmp_path / "runs.jsonl"
    p.write_text('{"kind": "ship", "what": "premise_subject", "session": "s#a"}\n'
                 "これは JSON ではありません\n\n", encoding="utf-8")
    _use(monkeypatch, p)
    assert retro.worked_on(["premise_subject"]) == {"premise_subject": 1}
    _use(monkeypatch, tmp_path / "no-such-file.jsonl")
    assert retro.worked_on(["premise_subject"]) == {"premise_subject": 0}
    assert retro.worked_on([]) == {}


def test_実物の帳面で走る():
    """**数は固定しません**（帳面は毎周 増えます）。固定するのは振る舞いだけ。"""
    carried, _ = retro.carry_over()
    got = retro.worked_on(list(carried))
    assert set(got) == set(carried)
    assert all(isinstance(v, int) and v >= 0 for v in got.values())
