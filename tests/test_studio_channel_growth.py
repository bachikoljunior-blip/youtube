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


# ---- 2026-09-10 16:4x（optimizer・Opus）: 行の順・周の数え・覆る条件 (1) の当て ----
# **なぜ足したか**: (1) 台帳は追記なので行の順は**書いた順**で、同じ周の 2体 が数十秒 差で書くと
# 入れ替わる（実物で踏んだ: `15:59:33` の行が `15:58:58` の行より前）。両端しか使わないので、
# 入れ替わりが端に来た周は窓が負になる。(2) §7 (m) の門は「**3周**」だが、
# 同じ周に 2体 が `status` を撃つので行は周の 2倍 入り、**行を数えると門に速く着く**。
# (3) `cli.record_channel` の覆る条件 (1)（10% の食い違い）を、どこも数えていなかった。


def test_rows_are_sorted_by_time_not_by_file_order():
    """**実物で踏んだ形**: 同じ周の 2行 が書いた順で入れ替わっている台帳。"""
    rows = [_row("2026-09-10T15:24:42+09:00", 27, 84781),
            _row("2026-09-10T15:59:33+09:00", 27, 84781),
            _row("2026-09-10T15:58:58+09:00", 27, 84781),   # ← 前の行より**古い**
            _row("2026-09-10T16:40:59+09:00", 27, 84781)]
    g = trend.channel_growth(rows)
    assert g["span_h"] > 0
    assert abs(g["span_h"] - 76.28 / 60) < 0.01


def test_positive_control_file_order_would_flip_the_window():
    """**陽性対照**: 並べ直しを外して**書いた順の両端**で数えると、窓が負になる。"""
    rows = [_row("2026-09-10T16:40:59+09:00", 27, 84781),   # 書いた順では最初
            _row("2026-09-10T15:24:42+09:00", 27, 84781)]
    assert trend.channel_growth(rows)["span_h"] > 0          # 道具は正
    a, b = rows[0], rows[-1]                                  # 門を外した数え方
    naive = (dt.datetime.fromisoformat(b["at"]) - dt.datetime.fromisoformat(a["at"])).total_seconds()
    assert naive < 0                                          # ＝ 外すと負


def test_two_rows_in_the_same_round_are_one_lap():
    """同じ周の 2体（`hourly`／`optimizer`）の行は **1周** に畳む。"""
    rows = [_row("2026-09-10T15:24:42+09:00", 27, 84781),
            _row("2026-09-10T15:58:58+09:00", 27, 84781),
            _row("2026-09-10T15:59:33+09:00", 27, 84781),
            _row("2026-09-10T16:40:59+09:00", 27, 84781)]
    g = trend.channel_growth(rows)
    assert g["n"] == 4 and g["laps"] == 3


def test_positive_control_counting_rows_hits_the_gate_early():
    """**陽性対照**: 行を周として数えると、門（3周）に **1周 早く**着く。"""
    rows = [_row("2026-09-10T15:24:42+09:00", 27, 84781),
            _row("2026-09-10T15:58:58+09:00", 27, 84781),
            _row("2026-09-10T15:59:33+09:00", 27, 84781)]
    g = trend.channel_growth(rows)
    assert g["laps"] == 2 and g["flat_laps"] == 2            # ＝ まだ引かれない
    assert g["n"] == 3                                        # 行を数えると 3 ＝ 引けてしまう
    assert "まだ引かれません" in trend.channel_line(rows)


def test_flat_laps_counts_readings_and_draws_the_gate_at_three():
    rows = [_row("2026-09-10T09:00:00+09:00", 27, 84000),
            _row("2026-09-10T10:00:00+09:00", 27, 84781),
            _row("2026-09-10T11:00:00+09:00", 27, 84781),
            _row("2026-09-10T12:00:00+09:00", 27, 84781)]
    g = trend.channel_growth(rows)
    assert g["flat_laps"] == 3                                # 84781 が 3周 続いた
    assert "3周 続けて同じ読み" in trend.channel_line(rows)
    assert "引かれました" in trend.channel_line(rows)


def test_flat_laps_resets_when_the_number_moves():
    rows = [_row("2026-09-10T09:00:00+09:00", 27, 84781),
            _row("2026-09-10T10:00:00+09:00", 27, 84781),
            _row("2026-09-10T11:00:00+09:00", 27, 84790)]
    assert trend.channel_growth(rows)["flat_laps"] == 1


def _m(at: str, vid: str, views: int, age_h: float) -> dict:
    return {"at": at, "id": vid, "event": "measured", "views": views, "age_h": age_h}


def test_video_delta_is_summed_over_the_same_window():
    rows = [_row("2026-09-10T09:00:00+09:00", 27, 84000),
            _row("2026-09-10T15:00:00+09:00", 27, 84100),
            _m("2026-09-10T09:00:00+09:00", "aaa", 100, 10.0),
            _m("2026-09-10T15:00:00+09:00", "aaa", 160, 16.0),
            _m("2026-09-10T09:00:00+09:00", "bbb", 50, 20.0),
            _m("2026-09-10T15:00:00+09:00", "bbb", 90, 26.0)]
    g = trend.channel_growth(rows)
    assert g["d_views"] == 100 and g["vid_sum"] == 100 and g["vid_n"] == 2
    assert g["mismatch"] == 0.0 and g["over"] is False


def test_books_without_a_base_point_are_skipped():
    """窓の頭に点を持たない本（窓の中で公開された本）は合計に入れない。"""
    rows = [_row("2026-09-10T09:00:00+09:00", 27, 84000),
            _row("2026-09-10T15:00:00+09:00", 27, 84100),
            _m("2026-09-10T12:00:00+09:00", "new", 700, 2.0),
            _m("2026-09-10T15:00:00+09:00", "new", 900, 5.0)]
    g = trend.channel_growth(rows)
    assert g["vid_n"] == 0 and g["vid_skipped"] == 1 and g["vid_sum"] == 0


def test_gate_is_one_sided_channel_over_sum_does_not_draw_it():
    """**チャンネル ＞ 合計** は、`measure` が触っていない古い本で説明が付く ＝ 引かない。"""
    rows = [_row("2026-09-10T09:00:00+09:00", 27, 84000),
            _row("2026-09-10T15:00:00+09:00", 27, 85000),   # +1000
            _m("2026-09-10T09:00:00+09:00", "aaa", 100, 10.0),
            _m("2026-09-10T15:00:00+09:00", "aaa", 110, 16.0)]  # +10
    g = trend.channel_growth(rows)
    assert g["mismatch"] > trend.CHANNEL_MISMATCH and g["over"] is False


def test_gate_draws_when_the_sum_exceeds_the_channel():
    """**合計 ＞ チャンネル** ＝ 触っている本の増えを総再生が受け取っていない側だけ引く。"""
    rows = [_row("2026-09-10T09:00:00+09:00", 27, 84000),
            _row("2026-09-10T15:00:00+09:00", 27, 84010),   # +10
            _m("2026-09-10T09:00:00+09:00", "aaa", 100, 10.0),
            _m("2026-09-10T15:00:00+09:00", "aaa", 600, 16.0)]  # +500
    g = trend.channel_growth(rows)
    assert g["over"] is True
    assert "覆る条件 (1) が引かれます" in trend.channel_line(rows)


def test_positive_control_two_sided_gate_would_fire_on_the_explainable_side():
    """**陽性対照**: 門を両側にすると、説明の付く側（チャンネル ＞ 合計）でも鳴る。"""
    rows = [_row("2026-09-10T09:00:00+09:00", 27, 84000),
            _row("2026-09-10T15:00:00+09:00", 27, 85000),
            _m("2026-09-10T09:00:00+09:00", "aaa", 100, 10.0),
            _m("2026-09-10T15:00:00+09:00", "aaa", 110, 16.0)]
    g = trend.channel_growth(rows)
    two_sided = g["mismatch"] >= trend.CHANNEL_MISMATCH        # 片側の門を外した形
    assert two_sided is True and g["over"] is False
