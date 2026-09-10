"""`cli.record_ready` / `trend.ready_checks` の検査（2026-09-10 16:2x・optimizer・Opus）。

**なぜ足したか**: `yt.readiness` は 09/08 02:5x に「10:00 に本当に出る状態か」を見るために足され、
`cmd_status` は予約ずみの本を持つ周は**毎周**（実測 1日 約14周）その結果を印字してきたのに、
台帳 `ready_checked` は **09/08 02:46 に手の script が書いた 1行 だけ**だった
＝ 「予約から公開までの窓で 1度でも `ok` でなかったか」に答えられない。
印字だけにしない族の 4つ目（`record_over`・`zero_probe`・`record_channel` に続く）。

**陽性対照つき**。
"""
from __future__ import annotations

import datetime as dt

from studio import trend

NOW = dt.datetime.fromisoformat("2026-09-10T16:30:00+09:00")


def _row(at: str, ok: bool = True, drift=None, vid: str = "vvv") -> dict:
    return {"event": "ready_checked", "id": vid, "at": at, "ok": ok,
            "upload": "processed" if ok else "failed",
            "processing": "succeeded" if ok else "failed",
            "failure": None if ok else "uploadFailed", "meta_drift": drift}


def test_no_rows_says_which_zero_it_is():
    line = trend.ready_line([], now=NOW)
    assert "0件" in line and "落ちた本が無い" in line


def test_counts_ok_and_bad():
    rows = [_row("2026-09-10T09:00:00+09:00"), _row("2026-09-10T10:00:00+09:00", ok=False)]
    q = trend.ready_checks(rows, now=NOW)
    assert q["n"] == 2 and q["ok"] == 1 and len(q["bad"]) == 1


def test_bad_is_named_in_the_line():
    rows = [_row("2026-09-10T10:00:00+09:00", ok=False)]
    line = trend.ready_line(rows, now=NOW)
    assert "`ok` でない 1件" in line and "公開の刻を疑う前に" in line


def test_old_rows_fall_out_of_the_window():
    rows = [_row("2026-09-05T09:00:00+09:00", ok=False), _row("2026-09-10T09:00:00+09:00")]
    q = trend.ready_checks(rows, now=NOW)
    assert q["n"] == 1 and q["bad"] == []


def test_drift_is_counted_separately():
    rows = [_row("2026-09-10T09:00:00+09:00", drift=["説明欄"])]
    q = trend.ready_checks(rows, now=NOW)
    assert q["ok"] == 1 and len(q["drift"]) == 1
    assert "台本と食い違ったまま" in trend.ready_line(rows, now=NOW)


def test_drift_none_is_not_drift():
    """`meta_drift` の `None` は「比べる物が無い」で、食い違いではない（`cli.meta_drift` の註）。"""
    rows = [_row("2026-09-10T09:00:00+09:00", drift=None),
            _row("2026-09-10T09:40:00+09:00", drift=[])]
    assert trend.ready_checks(rows, now=NOW)["drift"] == []


def test_other_events_are_not_counted():
    rows = [{"event": "measured", "id": "v", "at": "2026-09-10T09:00:00+09:00", "ok": False},
            _row("2026-09-10T09:00:00+09:00")]
    assert trend.ready_checks(rows, now=NOW)["n"] == 1


def test_rows_without_ok_field_are_skipped():
    """09/08 02:46 の手書きの 1行 は `ok` の欄を持たない ＝ 数に入れない。"""
    rows = [{"event": "ready_checked", "id": "x", "at": "2026-09-10T09:00:00+09:00",
             "upload": "processed"},
            _row("2026-09-10T09:00:00+09:00")]
    assert trend.ready_checks(rows, now=NOW)["n"] == 1


def test_record_ready_writes_a_row(tmp_path, monkeypatch):
    from studio import cli, common
    led = tmp_path / "ledger.jsonl"
    monkeypatch.setattr(common, "LEDGER", led)
    monkeypatch.setattr(common, "DATA", tmp_path)
    cli.record_ready("vid1", {"ok": False, "upload": "processed", "processing": "failed",
                              "failure": None, "rejection": "duplicate"}, ["説明欄"])
    txt = led.read_text(encoding="utf-8")
    assert '"event": "ready_checked"' in txt and '"ok": false' in txt
    assert '"failure": "duplicate"' in txt and '"説明欄"' in txt


def test_line_is_in_the_trend_report():
    rows = [_row("2026-09-10T09:00:00+09:00", ok=False)]
    out = trend.lines(rows, within_h=24 * 3, now=NOW)
    assert any("公開前の本の処理の印" in l for l in out)


def test_positive_control_bad_counted_as_ok():
    """**陽性対照**: `ok` でない行を `ok` で数えると、名指しの行が消える。"""
    rows = [_row("2026-09-10T09:00:00+09:00", ok=False)]
    q = trend.ready_checks(rows, now=NOW)
    assert len(q["bad"]) == 1 and q["ok"] == 0


def test_positive_control_window():
    """**陽性対照**: 窓を外すと、5日 前の落ちた行まで「いまの数」に混ざる。"""
    rows = [_row("2026-09-05T09:00:00+09:00", ok=False)]
    assert trend.ready_checks(rows, now=NOW)["n"] == 0
    assert trend.ready_checks(rows, within_h=1000, now=NOW)["n"] == 1


def test_call_site_is_wired_into_status():
    """**呼び口の検査**（陽性対照が 1つ 素通りしたので足した）。

    上の 11件 は全部 `record_ready` を**直に**呼んでおり、`cmd_status` から
    その行を消しても 1件も落ちなかった ＝ **「印字だけにしない」を守っているのは
    呼び口だけ**なのに、そこを見る検査が無かった（この穴そのものの再発の形）。
    `cmd_status` は API を撃つので実行では回せない。**源を見る。**
    """
    import inspect

    from studio import cli
    src = inspect.getsource(cli.cmd_status)
    assert "record_ready(" in src, "cmd_status が readiness を印字だけにしている"
    assert "record_channel(" in src, "cmd_status がチャンネルの数を印字だけにしている"


def test_comments_call_site_records_gone():
    """同じ形（`cmd_comments` が「消えたコメント」を印字だけにしていないか）。"""
    import inspect

    from studio import cli
    src = inspect.getsource(cli.cmd_comments)
    assert 'ledger("comment_gone"' in src
