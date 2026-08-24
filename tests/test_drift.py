"""`scripts/drift.py` の検査。

**この道具が守るのは1つだけ**: 「期限の来た前提があるのに、直近で1件も
判定していない」回を、黙って通さないこと（2026-08-24。オーナー指摘
「なんで実験そんな少ないの？」に対する配線の修理）。

**`fix` を禁じる検査は書きません。** 壊れた計器で実験しても答えは出ないので、
直すこと自体は正しい。**止めるのは「期限の来た問いを置き去りにしたまま」の場合だけ。**
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import drift  # noqa: E402


def _seed(tmp_path, monkeypatch, ships, hyps_yaml):
    runs = tmp_path / "runs.jsonl"
    runs.write_text("\n".join(json.dumps(s, ensure_ascii=False) for s in ships) + "\n",
                    encoding="utf-8")
    hyps = tmp_path / "hypotheses.yaml"
    hyps.write_text(hyps_yaml, encoding="utf-8")
    monkeypatch.setattr(drift, "RUNS", runs)
    monkeypatch.setattr(drift, "HYPS", hyps)


def _ship(at, what, **kw):
    return {"at": at, "kind": "ship", "what": what, **kw}


OPEN_OVERDUE = "- claim: 冒頭が engaged を決める\n  deadline: '2026-08-20'\n"
OPEN_FUTURE = "- claim: まだ先\n  deadline: '2026-12-01'\n"
CLOSED = ("- claim: 済んだやつ\n  deadline: '2026-08-20'\n"
          "  verdict: false\n")


def test_期限切れの前提があって判定ゼロなら外れと言う(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch,
          [_ship("2026-08-23T10:00", "fix: 道具を直した")] * 3, OPEN_OVERDUE)
    text, drifting = drift.report("2026-08-24")
    assert drifting is True
    assert "外れています" in text


def test_判定が直近にあれば外れと言わない(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch,
          [_ship("2026-08-23T10:00", "fix: 直した"),
           _ship("2026-08-23T11:00", "verdict: 前提を1件閉じた")], OPEN_OVERDUE)
    _, drifting = drift.report("2026-08-24")
    assert drifting is False


def test_期限切れが無ければ判定ゼロでも外れと言わない(tmp_path, monkeypatch):
    """**fix ばかりでも、締切が来ていなければ止めません。**

    実験は16本作って2週間待つので、**待っている間に fix をやるのは正しい。**
    止めるのは「期限が来ているのに置き去り」の1点だけ。
    """
    _seed(tmp_path, monkeypatch,
          [_ship("2026-08-23T10:00", "fix: 直した")] * 9, OPEN_FUTURE)
    _, drifting = drift.report("2026-08-24")
    assert drifting is False


def test_閉じた前提は期限切れに数えない(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch,
          [_ship("2026-08-23T10:00", "fix: 直した")], CLOSED)
    _, drifting = drift.report("2026-08-24")
    assert drifting is False


def test_種別は先頭の語で読む(tmp_path, monkeypatch):
    """既存240件は `--ship "fix: ..."` の書き方しか持っていません。

    **欄を足すのが本筋ですが、足すと過去が読めなくなる**ので、
    いまある書き方から読みます。**この検査は、その約束のほうを守ります。**
    """
    assert drift._kind_of("fix: あれを直した") == "fix"
    assert drift._kind_of("verdict: 判定した") == "verdict"
    assert drift._kind_of("upload: 1本予約") == "upload"
    assert drift._kind_of("means: M8 を動かした") == "means"
    assert drift._kind_of("親を交代した") == "その他"


def test_窓の外の回は数えない(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch,
          [_ship("2026-07-01T10:00", "fix: 大昔"),
           _ship("2026-08-23T10:00", "fix: 最近")], OPEN_FUTURE)
    text, _ = drift.report("2026-08-24", window_days=7)
    assert "ship 1件" in text


def test_gateは外れているときだけ2を返す(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch,
          [_ship("2026-08-23T10:00", "fix: 直した")], OPEN_OVERDUE)
    assert drift.main(["--gate", "--today", "2026-08-24"]) == 2
    assert drift.main(["--today", "2026-08-24"]) == 0


def test_ship以外の印は数えない(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch,
          [{"at": "2026-08-23T10:00", "kind": "write", "what": "周を始めた"},
           _ship("2026-08-23T11:00", "fix: 直した")], OPEN_FUTURE)
    text, _ = drift.report("2026-08-24")
    assert "ship 1件" in text
