"""落ちた本の**理由**が、台帳に残ることを固定する。

## なぜ要るか（2026-08-24 に実測）

`build_one` は `code, _ = run(cmd, ...)` で、**生成の出力をまるごと捨てて**
いました。残るのは `data/batch_runs.jsonl` の

    "error": "生成が失敗（exit 1）"

の1行だけです。出力そのものは `run()` が端末へ流しますが、
**その端末はその回のコンテナと一緒に消えます。**

実測の損: **2026-08-24 18:58 の回は 8本すべて exit 1** で落ちました
（`s-tokurou-danjo-240man` / `s-ideco-riri-5-deguchi-zei` / `s-zasson-…` ほか）。
台帳に理由が1文字も無いので、**次の回は同じ本をもう一度撃って理由を取り直す**
ところからしか始められません（長尺1本 ≒ 4分）。

そして長尺の歩留りは直近 **15/31 本（48%）** で、`config/hypotheses.yaml` の
08-31 の判定（「長尺は1日4本 作れる」＝ `rpm` の腕）は、**この歩留りに
そのまま乗っています。** 理由が分からないままでは、外れたときの
`next_if_false`（「なぜ4本作れないか」を材料側と時間側に分ける）も引けません。

## なぜ「文言の一覧」で書かないか

同じ輪で **手で持った名前が腐る**のを何度も踏んでいます
（`src/queue_mix.py`、2026-08-23 は書いた1時間後に腐った）。
落ちる文言はこちらが書き換えるたびに変わるので、拾うのは
**例外の名前**のほう —— `RuntimeError: …` は言語が出す形で、
本文を書き換えても綴りが変わりません。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import batch_build  # noqa: E402


def test_例外の行から名前と中身を取る():
    out = "[script] 題の形: 断定\nTraceback (most recent call last):\n" \
          "RuntimeError: 台本のセグメントが空でした。テーマを変えて再実行してください。\n"
    got = batch_build._failure_reason(out)
    assert got.startswith("RuntimeError: ")
    assert "台本のセグメントが空" in got


def test_モジュール名がついていても名前だけ取る():
    got = batch_build._failure_reason("foo\nsrc.verify.VerifyError: 4分を下回りました\n")
    assert got == "VerifyError: 4分を下回りました"


def test_いちばん後ろの例外を取る():
    """**途中で握りつぶした例外を理由にしない。** 落ちたのは最後の1つ。"""
    out = ("ValueError: これは途中で拾われた\n"
           "…\n"
           "RuntimeError: これが本当に落ちた理由\n")
    assert batch_build._failure_reason(out) == "RuntimeError: これが本当に落ちた理由"


def test_例外が見つからなければ最後の非空行を返す():
    """**「不明」と書かないこと。** 中身を捨てるのが、そもそもの欠陥です。"""
    out = "[batch] 何かをしています\nKilled\n\n\n"
    assert batch_build._failure_reason(out) == "Killed"


def test_出力が空でも殺された可能性を言う():
    got = batch_build._failure_reason("")
    assert "空" in got and "exit" in got


def test_理由は長すぎない():
    """台帳は1回に何十行も積みます。**1行が読める長さで止めること。**"""
    got = batch_build._failure_reason("RuntimeError: " + "あ" * 5000)
    assert len(got) <= 300


def test_落ちた行に理由と末尾が入る(monkeypatch, tmp_path):
    """**台帳に残る行そのもの**を見る。`_failure_reason` が正しくても、
    `build_one` が呼ばなければ `data/batch_runs.jsonl` には何も残りません
    （それが 2026-08-24 18:58 に 8本ぶん起きたことです）。"""
    out = ("[script] 初稿: 14セグメント\n"
           "Traceback (most recent call last):\n"
           "  File \"/home/user/youtube/src/pipeline.py\", line 287, in main\n"
           "RuntimeError: 台本の時点で過去の図と重なっています"
           "（レンダリング前に止めました）: 図の棒が `s-nisa-growth-only-1200（公開済み）` と"
           " 2本 共通（120万円・240万円…）。\n")
    monkeypatch.setattr(batch_build, "run", lambda *a, **k: (1, out))
    row = batch_build.build_one({"id": "s-x", "calc": "tokurou"}, True)

    assert row["built"] is False
    assert row["error"] == "生成が失敗（exit 1）"
    # **理由がある。**「exit 1」だけで終わらない
    assert row["error_reason"].startswith("RuntimeError: ")
    assert "過去の図と重なっています" in row["error_reason"]
    # **相手のテーマIDも残る**（次の回が「どの図とぶつかったか」を数えられる）
    assert "s-nisa-growth-only-1200" in row["error_tail"]


def test_通った本には理由の欄をつけない(monkeypatch):
    """**通った行を汚さないこと。** 台帳は1周ごとに増えます。"""
    monkeypatch.setattr(batch_build, "run", lambda *a, **k: (0, "ok"))
    monkeypatch.setattr(batch_build, "_flag_line", lambda tid, motion=None: None)
    row = batch_build.build_one({"id": "s-y", "calc": "nenkin"}, True)
    assert row["built"] is True
    assert "error_reason" not in row and "error_tail" not in row
