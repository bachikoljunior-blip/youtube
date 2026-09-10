"""`cli.record_channel` / `trend.channel_growth` の検査（2026-09-10 15:5x・optimizer・Opus）。

**なぜ足したか**: `cmd_status` は 09/05 から毎周 `yt.channel()` を撃って登録・総再生を
印字していたが、**残す口が無く**、§7 の収益の節の覆る条件 (1)（登録率 0.5%）も
「チャンネルの総再生が動いているか」も、道具の側から 1度も数えられていなかった。

**陽性対照つき** —— 下の `test_positive_control_*` は、道具の門を外すと落ちる形で書いてある。
"""
from __future__ import annotations

import datetime as dt

from studio import trend


def _row(at: str, subs: int, views: int, videos: int = 269) -> dict:
    return {"at": at, "id": "UCxxx", "event": "channel",
            "subs": subs, "views": views, "videos": videos}


def test_no_rows_says_so():
    g = trend.channel_growth([])
    assert g["n"] == 0 and g["d_subs"] is None
    assert "2点" in trend.channel_line([])


def test_one_row_is_not_a_delta():
    rows = [_row("2026-09-10T15:00:00+09:00", 27, 84781)]
    g = trend.channel_growth(rows)
    assert g["n"] == 1 and g["d_views"] is None
    assert g["subs"] == 27 and g["views"] == 84781


def test_two_rows_give_the_delta():
    rows = [_row("2026-09-10T09:00:00+09:00", 27, 84000),
            _row("2026-09-10T15:00:00+09:00", 29, 84781)]
    g = trend.channel_growth(rows)
    assert g["n"] == 2
    assert abs(g["span_h"] - 6.0) < 1e-9
    assert g["d_subs"] == 2 and g["d_views"] == 781
    assert abs(g["views_per_h"] - 781 / 6.0) < 1e-9


def test_ends_use_only_first_and_last():
    """途中の点は使わない（チャンネルの `viewCount` は刻みで動く）。"""
    rows = [_row("2026-09-10T09:00:00+09:00", 27, 84000),
            _row("2026-09-10T12:00:00+09:00", 99, 99999),   # 途中の跳ね
            _row("2026-09-10T15:00:00+09:00", 29, 84781)]
    g = trend.channel_growth(rows)
    assert g["d_subs"] == 2 and g["d_views"] == 781


def test_subs_per_view_is_none_when_views_did_not_move():
    """**分母が 0 のときに 0% と言わないこと**（「まだ測れていない」と「0%」は別）。"""
    rows = [_row("2026-09-10T09:00:00+09:00", 27, 84781),
            _row("2026-09-10T15:00:00+09:00", 27, 84781)]
    g = trend.channel_growth(rows)
    assert g["subs_per_view"] is None
    assert g["views_per_h"] == 0.0
    assert "測れていません" in trend.channel_line(rows)


def test_line_prints_the_gate():
    rows = [_row("2026-09-10T09:00:00+09:00", 27, 84000),
            _row("2026-09-10T15:00:00+09:00", 29, 84781)]
    line = trend.channel_line(rows)
    assert "0.5%" in line and "登録率" in line
    assert "+781" in line and "+2" in line


def test_short_window_is_not_read():
    rows = [_row("2026-09-10T15:00:00+09:00", 27, 84781),
            _row("2026-09-10T15:10:00+09:00", 27, 84800)]
    g = trend.channel_growth(rows)
    assert g["views_per_h"] is None
    assert "まだ読まないこと" in trend.channel_line(rows)


def test_rows_without_numbers_are_skipped():
    """欄が無い行（旧い形・書き損じ）は数に入れない。"""
    rows = [{"at": "2026-09-10T09:00:00+09:00", "id": "UCxxx", "event": "channel"},
            _row("2026-09-10T15:00:00+09:00", 29, 84781)]
    assert trend.channel_growth(rows)["n"] == 1


def test_other_events_are_not_counted():
    rows = [{"at": "2026-09-10T09:00:00+09:00", "id": "x", "event": "measured",
             "subs": 1, "views": 2},
            _row("2026-09-10T15:00:00+09:00", 29, 84781)]
    assert trend.channel_growth(rows)["n"] == 1


def test_record_channel_writes_a_row(tmp_path, monkeypatch):
    """`record_channel` が台帳に 1行 足す（**追加 0単位** ＝ `status` がすでに引いてある数）。"""
    from studio import cli, common
    led = tmp_path / "ledger.jsonl"
    monkeypatch.setattr(common, "LEDGER", led)
    monkeypatch.setattr(common, "DATA", tmp_path)
    cli.record_channel({"id": "UCxxx", "subscriberCount": 27,
                        "viewCount": 84781, "videoCount": 269})
    txt = led.read_text(encoding="utf-8")
    assert '"event": "channel"' in txt and '"subs": 27' in txt and '"views": 84781' in txt


def test_line_is_in_the_trend_report():
    """毎周 印字されること（**次の回は覚えていなくてよい** の当のもの）。"""
    rows = [_row("2026-09-10T09:00:00+09:00", 27, 84000),
            _row("2026-09-10T15:00:00+09:00", 29, 84781)]
    out = trend.lines(rows, within_h=24 * 3,
                      now=dt.datetime.fromisoformat("2026-09-10T15:20:00+09:00"))
    assert any("登録率" in l for l in out)


def test_positive_control_first_last():
    """**陽性対照**: 両端ではなく「最後の2点」で数えると違う答えになる ＝ 端の門は効いている。"""
    rows = [_row("2026-09-10T09:00:00+09:00", 27, 84000),
            _row("2026-09-10T12:00:00+09:00", 99, 99999),
            _row("2026-09-10T15:00:00+09:00", 29, 84781)]
    assert trend.channel_growth(rows)["d_subs"] == 2
    assert trend.channel_growth(rows[1:])["d_subs"] == -70


def test_positive_control_zero_denominator():
    """**陽性対照**: 分母 0 で 0% を返す形にすると、`None` の枝が消える。"""
    rows = [_row("2026-09-10T09:00:00+09:00", 27, 84781),
            _row("2026-09-10T15:00:00+09:00", 30, 84781)]
    g = trend.channel_growth(rows)
    assert g["d_subs"] == 3            # 登録は動いた
    assert g["subs_per_view"] is None  # それでも率は出せない（0 ではない）
