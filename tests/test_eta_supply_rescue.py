"""**回が途中で死ぬと、作った長尺が供給の実測から消えていました**（2026-08-26）。

`scripts/batch_build.py` は `data/batch_runs.jsonl` を**回のいちばん最後に
1行だけ**書きます。だから途中で死んだ回は、`final.mp4` まで出来て予約も
通っている本ごと帳面から消えます。

実測（2026-08-26 09:xx）: `timeout 900` で殺された回の2本と、
きょうだいの回の1本（`qlQnJwwwaZs`）が、**控え（`data/uploaded.jsonl`）には
在るのに台帳に1行も無い**状態でした。`long_supply_per_day()` はそこだけを
読むので、**08/31 の前提「長尺は1日4本 作れる」が、作った本を数え落としたまま
外れに倒れます。**

`long_supply_per_day()` の docstring は、この形を
**「覆る条件: 長尺を帳面の外で作るようになったら、ここは実測ではなくなります」**
と予告していました。**その条件が来たので塞いだ**のがここです。

## 故障注入つきで書くこと

最初に書いた案は「テーマIDが `s-` で始まらなければ長尺」でした。
**`s-` は新しいショートにしか付いていません** —— 08/19 のショート9本
（`invoice-2wari-tokurei` など）が長尺に化けて、供給が
**1日 2.86本 → 4.29本** に跳ねました。**前提の合否がひっくり返る幅**です。
下の `test_故障注入_ショートを長尺に数えない` がその案で落ちます。
"""
from __future__ import annotations

import json
from datetime import date

import pytest

import scripts.eta as eta


def _write(tmp_path, batch_rows, uploaded_rows):
    b = tmp_path / "batch_runs.jsonl"
    u = tmp_path / "uploaded.jsonl"
    b.write_text("\n".join(json.dumps(r, ensure_ascii=False)
                           for r in batch_rows) + "\n", encoding="utf-8")
    u.write_text("\n".join(json.dumps(r, ensure_ascii=False)
                           for r in uploaded_rows) + "\n", encoding="utf-8")
    return b, u


@pytest.fixture
def uploaded(monkeypatch):
    def _set(path):
        monkeypatch.setattr(eta, "UPLOADED", path)
    return _set


LONG_ROW = {
    "at": "2026-08-25T09:00:00+09:00", "long": True,
    "results": [{"topic": "a-long", "video_id": "AAA"}],
}


def test_台帳に無い長尺を控えから拾う(tmp_path, uploaded):
    b, u = _write(
        tmp_path, [LONG_ROW],
        [{"video_id": "BBB", "topic": "b-long",
          "uploaded_at": "2026-08-24T09:00:00+00:00", "duration_s": 310.0}])
    uploaded(u)
    got = eta.long_supply_per_day(path=b, today=date(2026, 8, 26),
                                  window_days=7)
    assert got["rescued"] == 1
    assert got["built"] == 2, got
    assert got["attempts"] == 2, got


def test_台帳にある本は二重に数えない(tmp_path, uploaded):
    """`batch_build` は予約を `upload_only.py` で撃つので、**同じ本が両方に載ります。**"""
    b, u = _write(
        tmp_path, [LONG_ROW],
        [{"video_id": "AAA", "topic": "a-long",
          "uploaded_at": "2026-08-25T09:00:00+00:00", "duration_s": 310.0}])
    uploaded(u)
    got = eta.long_supply_per_day(path=b, today=date(2026, 8, 26),
                                  window_days=7)
    assert got["rescued"] == 0
    assert got["built"] == 1, got


def test_窓の外の回で作った本も二重に数えない(tmp_path, uploaded):
    """**作った日と予約した日は違います。** 窓の中だけで重複を外すと二重になります。"""
    old = {"at": "2026-07-01T09:00:00+09:00", "long": True,
           "results": [{"topic": "old-long", "video_id": "OLD"}]}
    b, u = _write(
        tmp_path, [old],
        [{"video_id": "OLD", "topic": "old-long",
          "uploaded_at": "2026-08-24T09:00:00+00:00", "duration_s": 310.0}])
    uploaded(u)
    got = eta.long_supply_per_day(path=b, today=date(2026, 8, 26),
                                  window_days=7)
    assert got["rescued"] == 0, got
    assert got["built"] == 0, got


def test_故障注入_ショートを長尺に数えない(tmp_path, uploaded):
    """**`s-` の付かない古いショートが 9本 あります。** 尺で分けること。"""
    b, u = _write(
        tmp_path, [LONG_ROW],
        [{"video_id": "SHORT1", "topic": "invoice-2wari-tokurei",
          "uploaded_at": "2026-08-24T09:00:00+00:00", "duration_s": 41.2},
         {"video_id": "SHORT2", "topic": "tsukin-teate-hikazei",
          "uploaded_at": "2026-08-24T09:00:00+00:00", "duration_s": 38.9}])
    uploaded(u)
    got = eta.long_supply_per_day(path=b, today=date(2026, 8, 26),
                                  window_days=7)
    assert got["rescued"] == 0, "ショートを長尺に数えている"
    assert got["built"] == 1, got


def test_尺の無い行は数えない(tmp_path, uploaded):
    """**分からないものを長尺の側へ倒さないこと**（古い控えには `duration_s` がありません）。"""
    b, u = _write(
        tmp_path, [LONG_ROW],
        [{"video_id": "NODUR", "topic": "ideco-vs-nisa",
          "uploaded_at": "2026-08-24T09:00:00+00:00"}])
    uploaded(u)
    got = eta.long_supply_per_day(path=b, today=date(2026, 8, 26),
                                  window_days=7)
    assert got["rescued"] == 0, got


def test_窓はJSTで当てる(tmp_path, uploaded):
    """`uploaded_at` は UTC。**直さないと、朝9時より前の本が前日に落ちます。**

    `2026-08-19T23:00:00+00:00` は **JST では 08-20 08:00**。
    今日を 08-26 とすると窓は 08-19〜08-25 なので、
    **UTC のまま読むと 08-19 で入り、JST で読んでも 08-20 で入る** ——
    両方入る日では違いが出ないので、**窓の端**で当てます。
    `2026-08-18T23:00:00+00:00` は JST で **08-19**（窓の先頭）。
    UTC のままだと 08-18 で**窓から落ちます。**
    """
    b, u = _write(
        tmp_path, [LONG_ROW],
        [{"video_id": "EDGE", "topic": "edge-long",
          "uploaded_at": "2026-08-18T23:00:00+00:00", "duration_s": 310.0}])
    uploaded(u)
    got = eta.long_supply_per_day(path=b, today=date(2026, 8, 26),
                                  window_days=7)
    assert got["rescued"] == 1, "UTC のまま窓に当てている（JST に直すこと）"


def test_控えが無くても落ちない(tmp_path, uploaded):
    b, u = _write(tmp_path, [LONG_ROW], [])
    uploaded(tmp_path / "no-such-file.jsonl")
    got = eta.long_supply_per_day(path=b, today=date(2026, 8, 26),
                                  window_days=7)
    assert got["rescued"] == 0
    assert got["built"] == 1


def test_実物で落ちない():
    """**実物を読む。** 形が変わっても落ちないこと。"""
    got = eta.long_supply_per_day()
    assert set(got) >= {"rate", "built", "attempts", "rescued", "measured"}
    assert got["rescued"] >= 0
    assert got["built"] >= got["rescued"]
