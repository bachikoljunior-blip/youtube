"""`run_marker.py --write` —— **撃ち直しても、数える側が動かないこと。**

2026-09-05 05:1x に踏みました。この印の出力は **30.3KB・250行 超**で、回は
`| tail -120` で読みます。すると頭（`_premise_subject_lines` / `_m4_lines` /
`_unreachable_premise_lines` / `ledger_holes` / §4 の表）が丸ごと消えます。
末尾の「頭の写し」（2026-09-03）は**一時置き場と読む順しか写していません**。

撃ち直すと `data/runs.jsonl` に2行目の `start` が載り、
`docs/spawn_prompt.md` の「立ってから 60分」の線が撃ち直した時刻へ動きます
（＝ 回が自分で延命できてしまう）。だから:

  (1) 全文を `<一時置き場>/marker.txt` へ落とす（`sed` で頭が読める）
  (2) 同じ俳優の `start` が直近 12時間 に在れば、2行目を載せない
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

JST = timezone(timedelta(hours=9))


def _mod():
    spec = importlib.util.spec_from_file_location(
        "run_marker_rewrite_under_test", ROOT / "scripts" / "run_marker.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["run_marker_rewrite_under_test"] = mod
    spec.loader.exec_module(mod)                    # type: ignore[union-attr]
    return mod


@pytest.fixture()
def rm(tmp_path, monkeypatch):
    mod = _mod()
    monkeypatch.setattr(mod, "MARKS", tmp_path / "runs.jsonl")
    return mod


def _write(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                    encoding="utf-8")


def test_印が無ければ_空を返す(rm, tmp_path):
    assert rm.start_row("私") == {}


def test_直近の印は_拾う(rm, tmp_path):
    now = datetime(2026, 9, 5, 5, 0, tzinfo=JST)
    _write(tmp_path / "runs.jsonl", [
        {"at": (now - timedelta(minutes=40)).isoformat(timespec="seconds"),
         "session": "私", "kind": "start"},
    ])
    assert rm.start_row("私", now=now).get("session") == "私"


def test_窓の外の印は_拾わない(rm, tmp_path):
    """**推測で古い行を拾わないこと** —— 別の回が同じIDを名乗る道が残っています。"""
    now = datetime(2026, 9, 5, 5, 0, tzinfo=JST)
    _write(tmp_path / "runs.jsonl", [
        {"at": (now - timedelta(hours=rm.RESTART_WINDOW_H + 1)).isoformat(timespec="seconds"),
         "session": "私", "kind": "start"},
    ])
    assert rm.start_row("私", now=now) == {}


def test_ほかの俳優の印は_自分のぶんにしない(rm, tmp_path):
    now = datetime(2026, 9, 5, 5, 0, tzinfo=JST)
    _write(tmp_path / "runs.jsonl", [
        {"at": now.isoformat(timespec="seconds"), "session": "きょうだい", "kind": "start"},
    ])
    assert rm.start_row("私", now=now) == {}


def test_shipの行は_startとして数えない(rm, tmp_path):
    now = datetime(2026, 9, 5, 5, 0, tzinfo=JST)
    _write(tmp_path / "runs.jsonl", [
        {"at": now.isoformat(timespec="seconds"), "session": "私", "kind": "ship",
         "what": "なにか"},
    ])
    assert rm.start_row("私", now=now) == {}


def test_2度目のwriteは_startを2行にしない(rm, tmp_path, monkeypatch, capsys):
    """**これが本体です。** 画面は出るが、台帳は1行のまま。"""
    monkeypatch.setattr(rm, "actor_id", lambda: "私")
    monkeypatch.setattr(rm, "is_parent", lambda: False)
    monkeypatch.setattr(rm, "scratch_dir", lambda make=True: "")
    # 画面の中身は別の検査のもの。ここでは台帳だけを見ます
    monkeypatch.setattr(rm, "_doc_index_lines", lambda: [])
    monkeypatch.setattr(rm, "_doc_decision_lines", lambda: [])
    monkeypatch.setattr(rm, "_premise_subject_lines", lambda: [])
    monkeypatch.setattr(rm, "_m4_lines", lambda: [])
    monkeypatch.setattr(rm, "_unreachable_premise_lines", lambda: [])
    monkeypatch.setattr(rm, "_next_slot_lines", lambda: [])
    monkeypatch.setattr(rm, "_claim_lines", lambda: [])

    rm.write()
    rows = [json.loads(x) for x in
            (tmp_path / "runs.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    assert [r["kind"] for r in rows] == ["start"]

    rm.write()
    rows2 = [json.loads(x) for x in
             (tmp_path / "runs.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    assert [r["kind"] for r in rows2] == ["start"]      # **2行目が載っていない**
    assert "もう付いています" in capsys.readouterr().out


def test_全文が一時置き場に落ちる(rm, tmp_path, monkeypatch):
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    monkeypatch.setattr(rm, "actor_id", lambda: "私")
    monkeypatch.setattr(rm, "is_parent", lambda: False)
    monkeypatch.setattr(rm, "scratch_dir", lambda make=True: str(scratch))
    monkeypatch.setattr(rm, "_doc_index_lines", lambda: ["[marker] 読む順"])
    monkeypatch.setattr(rm, "_doc_decision_lines", lambda: [])
    monkeypatch.setattr(rm, "_premise_subject_lines", lambda: ["[marker] 頭の1行"])
    monkeypatch.setattr(rm, "_m4_lines", lambda: [])
    monkeypatch.setattr(rm, "_unreachable_premise_lines", lambda: [])
    monkeypatch.setattr(rm, "_next_slot_lines", lambda: [])
    monkeypatch.setattr(rm, "_claim_lines", lambda: [])

    rm.write()
    out = (scratch / "marker.txt").read_text(encoding="utf-8")
    assert "頭の1行" in out          # **`tail` で消える側が、ここに残っている**
    assert "この画面の全文" in out


def test_撃ち直しでは_背景の起こしを走らせない(rm, tmp_path, monkeypatch, capsys):
    """**2026-09-08 に、これは「撃ち直しでは」から「1度も」へ強くなりました。**

    元の形（2026-09-05）はこう書いていました:

        **`ahead_sweep.kick()` は焼き直しの上限（1日 2回）を減らします。**
        錠（`flock`）が2本目を `skip` で落としても、その回は「焼いた」と数えられます
        （`docs/spawn_prompt.md` の註）。＝ 頭を読み直すためのもう1回で、その日の
        焼き直しの枠が1つ消えていました。

    ＝ **1周目は起こすのが正しい**という前提でした。**その前提が落ちています。**
    `docs/METHOD.md` §8 は旧道具を「使わない」と決め、`ahead_sweep` は
    09/06 00:01 に**旧作りの本 8本 に publishAt を打った**当のものです。
    実測 2026-09-08 06:57:51: **`pytest tests/` を撃っただけ**で `niche_ceiling.kick()` が
    背景で走り、外の本を漁って data/ の 3ファイルに 477行 を足し、`videos.list` を 1単位 使いました。

    → `run_marker.py` の kick を 2つとも外しました（**関数は消していない** —— §8）。
    **いまは 1周目でも起こしません。** 見張りの本体は `tests/test_no_background_kick.py`。
    **覆る条件**: 旧道具を使う判断が METHOD に書かれたら、kick ではなく手順から呼ぶこと。
    """
    monkeypatch.setattr(rm, "actor_id", lambda: "私")
    monkeypatch.setattr(rm, "is_parent", lambda: False)
    monkeypatch.setattr(rm, "scratch_dir", lambda make=True: "")
    for name in ("_doc_index_lines", "_doc_decision_lines", "_premise_subject_lines",
                 "_m4_lines", "_unreachable_premise_lines", "_next_slot_lines",
                 "_claim_lines"):
        monkeypatch.setattr(rm, name, lambda: [])

    kicked: list[str] = []

    class _Fake:
        @staticmethod
        def kick():
            kicked.append("x")
            return "起こしました"

    monkeypatch.setitem(sys.modules, "ahead_sweep", _Fake)
    monkeypatch.setitem(sys.modules, "niche_ceiling", _Fake)

    rm.write()
    assert kicked == [], "1周目で背景の kick が走っています（`docs/METHOD.md` §8）"
    rm.write()
    assert kicked == [], "撃ち直しで背景の kick が走っています"
    assert "背景の kick は 2026-09-08 に外しました" in capsys.readouterr().out
