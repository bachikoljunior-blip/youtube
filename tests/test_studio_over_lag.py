"""`status` が印字した「台帳より高い読み」を、次の `measure` が拾ったかを数える口の検査。

2026-09-10 13:2x JST（optimizer・Opus）。**陽性対照つき** ——
道具を壊すと落ちることを撃って確かめてある（`studio/trend.over_lag` の註）。
"""
from studio import cli, trend


def _m(at, vid, views):
    return {"event": "measured", "at": at, "id": vid, "views": views, "age_h": 50.0}


def _o(at, vid, live, led):
    return {"event": "views_over", "at": at, "id": vid,
            "views_live": live, "views_ledger": led, "over": live - led, "age_h": 51.1}


ROWS = [
    _m("2026-09-10T12:32:22+09:00", "A", 613),
    _o("2026-09-10T13:06:00+09:00", "A", 671, 613),
    _m("2026-09-10T13:07:12+09:00", "A", 671),
]


def test_印が無ければ0件で_覆る条件2の分子はまだ0():
    only = [_m("2026-09-10T12:32:22+09:00", "A", 613)]
    o = trend.over_lag(only)
    assert o["n"] == 0 and o["caught"] == [] and o["late"] == []
    line = trend.over_lag_line(only)
    assert "0件" in line and "起きていない" in line


def test_次のmeasureが拾えば追いつきの回数と分を返す():
    o = trend.over_lag(ROWS)
    assert o["n"] == 1
    m = o["marks"][0]
    assert m["catch_rounds"] == 1
    assert 1.0 < m["catch_min"] < 2.0
    assert o["late"] == []


def test_低い読みで拾ったことにしない():
    """遅れた複製（613）が何回 並んでも「追いついた」にはならない。"""
    rows = ROWS[:2] + [_m("2026-09-10T13:40:00+09:00", "A", 613),
                       _m("2026-09-10T14:20:00+09:00", "A", 613)]
    o = trend.over_lag(rows)
    assert o["marks"][0]["catch_rounds"] is None
    assert o["marks"][0]["measures_since"] == 2
    assert o["late"] == []  # まだ 3回 に届いていない


def test_3回過ぎて届かなければ覆る条件1が引かれる():
    rows = ROWS[:2] + [_m(f"2026-09-10T1{h}:40:00+09:00", "A", 613) for h in (3, 4, 5)]
    o = trend.over_lag(rows)
    assert len(o["late"]) == 1
    line = trend.over_lag_line(rows)
    assert "覆る条件 (1)" in line
    assert "生671 対 台帳613" in line


def test_別の本のmeasureでは追いつかない():
    rows = ROWS[:2] + [_m("2026-09-10T13:07:12+09:00", "B", 999)]
    assert trend.over_lag(rows)["marks"][0]["catch_rounds"] is None


def test_印より前のmeasureは数えない():
    """印の**前**に高い行が在っても「拾った」ではない（順番で見る）。"""
    rows = [_m("2026-09-10T11:00:00+09:00", "A", 700)] + ROWS[:2]
    assert trend.over_lag(rows)["marks"][0]["catch_rounds"] is None


def test_台帳の値は印の時点の写しを使う():
    """後から数え直さない（`recounts` が峰を落とすとずれる・覆る条件 (4)）。"""
    rows = ROWS + [{"event": "measured", "at": "2026-09-10T14:00:00+09:00",
                    "id": "A", "views": 300, "age_h": 52.0}]
    assert trend.over_lag(rows)["marks"][0]["views_ledger"] == 613


def test_trendの毎周の印字にこの行が在る():
    out = trend.lines(ROWS, within_h=24 * 7)
    assert any("台帳より高い読みの印" in l for l in out)


def test_陽性対照_印を捨てる形に戻すと落ちる():
    """`views_over` を読まない（＝ 12:4x の印字だけの形）に戻すと、何も数えられない。"""
    rows = [r for r in ROWS if r.get("event") != "views_over"]
    assert trend.over_lag(rows)["n"] == 0


def test_陽性対照_門を1回にすると届かない側が早く鳴る():
    rows = ROWS[:2] + [_m("2026-09-10T13:40:00+09:00", "A", 613)]
    assert trend.over_lag(rows)["late"] == []
    old = trend.OVER_CATCH_ROUNDS
    try:
        trend.OVER_CATCH_ROUNDS = 1
        assert len(trend.over_lag(rows)["late"]) == 1
    finally:
        trend.OVER_CATCH_ROUNDS = old


def test_status_の印は台帳に1行_残る(monkeypatch):
    """印字だけで捨てない（`cli.record_over` ＝ `cmd_status` が撃つ当の関数）。"""
    wrote = []
    monkeypatch.setattr(cli, "ledger", lambda ev, vid, **d: wrote.append((ev, vid, d)))
    cli.record_over("A", 671, 58, 51.14)
    assert len(wrote) == 1
    ev, vid, d = wrote[0]
    assert ev == "views_over" and vid == "A"
    assert d["views_live"] == 671 and d["views_ledger"] == 613 and d["over"] == 58
    assert d["age_h"] == 51.1


def test_cmd_status_が印を撃っている():
    """**この検査が無いと、`cmd_status` から呼び出しを消しても 13件 とも緑でした**
    （この回に撃って確かめた ＝ §5 の教訓の形 3つ目「陽性対照は落ちるまで撃つ」）。
    `record_over` 単体の検査は「口が在ること」しか見ておらず、
    **その口が繋がっているか**は見ていません —— この repo でいちばん多い壊れ方
    （言っている所と、している所が別）が、直しに来た当の場所に出ました。
    `crosscheck` の「critique に説明欄が渡っていないこと」と同じ形の見張りです。
    """
    import inspect
    src = inspect.getsource(cli.cmd_status)
    assert "over_ledger(" in src, "status が高い読みを見つける口を失っています"
    assert "record_over(" in src, "status が印字だけで捨てる形に戻っています"


def test_status_の印はmeasuredでは書かない():
    """`measured` で書くと帯の2点組の分母が動く（`trend.informative` の註）。"""
    import inspect
    src = inspect.getsource(cli.record_over)
    assert '"views_over"' in src and '"measured"' not in src


def test_over_ledgerは高い側だけを印にする():
    led = [_m("2026-09-10T12:32:22+09:00", "A", 613)]
    assert cli.over_ledger("A", 671, led) == 58
    assert cli.over_ledger("A", 600, led) is None
    assert cli.over_ledger("A", 613, led) is None
