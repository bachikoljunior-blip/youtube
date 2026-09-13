"""`cli.empty_slot_mark` —— **きょうの枠が空の回に、名指しで「予約しろ」と言う印**。

`cmd_status` の「きょうの枠:」は `today_lineup()` を回すだけで、**空の回は 1字も印字しません**。
`lineup_mark`（§12 23:0x）は *並んでいる本* に印を付ける物で、**1本も並んでいない側は見ていません**。
実測 2026-09-14 00:53: 09/14 の本は焼いてあるのに枠は空のまま（この回が予約して `-bSkulqONhI`）で、
その blank は **00:49 でも 09:49 でも同じ字**でした。

**陽性対照**（撃って落とした）:
`empty_slot_mark` の `if lineup: return ""` を外すと `test_枠に本が並んでいれば何も言わない` が落ち、
余りを「時間」だけにして周を落とすと `test_残りの周を実測の中央値で言う` が落ち、
`left <= 0` の枝を消すと `test_10時を過ぎた回は予約しろと言わない` が落ちる。
"""
import datetime as dt
import json

from studio import cli

JST = dt.timezone(dt.timedelta(hours=9))


def _rounds(tmp_path, first: dt.datetime, n: int, gap_h: float):
    p = tmp_path / "rounds.jsonl"
    lines = []
    for i in range(n):
        at = (first + dt.timedelta(hours=gap_h * i)).isoformat()
        for role in ("hourly", "optimizer"):
            lines.append(json.dumps({"at": at, "role": role, "round": at}))
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def _scripts(tmp_path, names):
    d = tmp_path / "scripts"
    d.mkdir()
    for n in names:
        (d / f"{n}.json").write_text("{}", encoding="utf-8")
    return d


def test_枠に本が並んでいれば何も言わない(tmp_path):
    now = dt.datetime(2026, 9, 14, 0, 49, tzinfo=JST)
    d = _scripts(tmp_path, ["2026-09-14-menjo-2bunno1"])
    assert cli.empty_slot_mark([{"id": "x"}], now, scripts_dir=d) == ""


def test_台本が在って枠が空なら予約しろと言う(tmp_path):
    now = dt.datetime(2026, 9, 14, 0, 49, tzinfo=JST)
    d = _scripts(tmp_path, ["2026-09-14-menjo-2bunno1"])
    out = cli.empty_slot_mark([], now, scripts_dir=d)
    assert "!!" in out
    assert "2026-09-14-menjo-2bunno1" in out
    assert cli.SLOT_AT in out


def test_残りの周を実測の中央値で言う(tmp_path):
    now = dt.datetime(2026, 9, 14, 0, 0, tzinfo=JST)
    d = _scripts(tmp_path, ["2026-09-14-menjo-2bunno1"])
    r = _rounds(tmp_path, dt.datetime(2026, 9, 13, 0, 0, tzinfo=JST), 12, 1.0)
    out = cli.empty_slot_mark([], now, scripts_dir=d, rounds_path=r)
    # 10:00 まで 10.0h・周 1.00h ＝ 残り およそ 10周
    assert "10周" in out
    assert "10.0h" in out


def test_余りが小さい回と大きい回で字が変わる(tmp_path):
    """**この印の当のもの** —— blank は 00:49 と 09:49 で同じ字だった。"""
    d = _scripts(tmp_path, ["2026-09-14-menjo-2bunno1"])
    r = _rounds(tmp_path, dt.datetime(2026, 9, 13, 0, 0, tzinfo=JST), 12, 1.0)
    early = cli.empty_slot_mark([], dt.datetime(2026, 9, 14, 0, 49, tzinfo=JST), scripts_dir=d, rounds_path=r)
    late = cli.empty_slot_mark([], dt.datetime(2026, 9, 14, 9, 49, tzinfo=JST), scripts_dir=d, rounds_path=r)
    assert early != late
    assert "0.2h" in late


def test_10時を過ぎた回は予約しろと言わない(tmp_path):
    now = dt.datetime(2026, 9, 14, 10, 30, tzinfo=JST)
    d = _scripts(tmp_path, ["2026-09-14-menjo-2bunno1"])
    out = cli.empty_slot_mark([], now, scripts_dir=d)
    assert "過ぎました" in out
    assert "`build`" not in out


def test_きょうの日付の台本が無ければ表の1行目へ送る(tmp_path):
    now = dt.datetime(2026, 9, 14, 0, 49, tzinfo=JST)
    d = _scripts(tmp_path, ["2026-09-13-fuka-nenkin-400en"])
    out = cli.empty_slot_mark([], now, scripts_dir=d)
    assert "台本もありません" in out
    assert "§5" in out


def test_周が数えられなければ時間だけ言う(tmp_path):
    now = dt.datetime(2026, 9, 14, 0, 0, tzinfo=JST)
    d = _scripts(tmp_path, ["2026-09-14-menjo-2bunno1"])
    r = tmp_path / "none.jsonl"
    out = cli.empty_slot_mark([], now, scripts_dir=d, rounds_path=r)
    assert "10.0h" in out
    assert "周" not in out


def test_実物の周の並びから中央値が出る():
    """`data/rounds.jsonl`（実物）で `lap_hours` が立つこと。"""
    gap = cli.lap_hours()
    assert gap is not None
    assert 0.1 < gap < 6.0
