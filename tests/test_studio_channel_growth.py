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


def test_a_lower_middle_point_does_not_move_the_ends():
    """**低いほうの途中の点は使わない**（遅れた複製・`channel_replicas` の註）。"""
    rows = [_row("2026-09-10T09:00:00+09:00", 27, 84000),
            _row("2026-09-10T12:00:00+09:00", 27, 83000),   # 途中の低い読み ＝ 遅れた複製
            _row("2026-09-10T15:00:00+09:00", 29, 84781)]
    g = trend.channel_growth(rows)
    assert g["d_subs"] == 2 and g["d_views"] == 781


def test_a_higher_middle_point_raises_the_last_end():
    """**高いほうの途中の点は端を上げる**（2026-09-11 04:0x に向きを変えた）。

    もとの形（`test_ends_use_only_first_and_last`）は「途中の点は使わない」で、
    **跳ねを雑音として捨てて**いた。**この回に実物で外れた** ——
    チャンネルの `viewCount` は遅れの違う複製から返り（02:12:18 **84,781** →
    02:12:43 **86,406**・03:24 **84,781** → 03:27 に直に 5回 撃つと **5回 とも 86,406**）、
    **低いほうが古い**。＝ 途中の高い読みは雑音ではなく、**その時刻に真の値がそこに在った証拠**で、
    そのあとの低い読みは複製。単調な数なので、端は包絡で読む。
    **本当の取り消し**（6時間 を越えて戻らない峰）は下の検査が分けている。
    """
    rows = [_row("2026-09-10T09:00:00+09:00", 27, 84000),
            _row("2026-09-10T12:00:00+09:00", 27, 86406),   # 新しい複製
            _row("2026-09-10T15:00:00+09:00", 29, 84781)]   # また遅れた複製に当たった
    g = trend.channel_growth(rows)
    assert g["d_views"] == 86406 - 84000
    assert g["views"] == 86406


def test_a_peak_that_never_comes_back_falls_out_of_the_ceiling():
    """**6時間 を越えて戻らない峰は天井にしない**（`ceiling()` と同じ規則 ＝ 数え直し・取り消し）。"""
    rows = [_row("2026-09-10T00:00:00+09:00", 27, 84000),
            _row("2026-09-10T01:00:00+09:00", 27, 99999),   # 戻らない峰
            _row("2026-09-10T09:00:00+09:00", 27, 84500),
            _row("2026-09-10T15:00:00+09:00", 29, 84781)]
    g = trend.channel_growth(rows)
    assert g["views"] == 84781 and g["d_views"] == 781


def test_replicas_are_counted_and_named():
    """同じ周に割れた読みと、周の max の下がりを数える（**1点で「動いた」を読まないため**）。"""
    rows = [_row("2026-09-11T02:12:18+09:00", 28, 84781),
            _row("2026-09-11T02:12:43+09:00", 28, 86406),   # 25秒 差で +1,625
            _row("2026-09-11T03:24:53+09:00", 28, 84781)]   # 72分 後に -1,625
    r = trend.channel_replicas(rows)
    assert r["split_laps"] == 1 and r["max_split"] == 1625
    assert r["drops"] == 1 and r["max_drop"] == 1625
    assert r["proved"] is True and r["env"] == 86406 and r["raw_last"] == 84781
    line = trend.channel_replica_line(rows)
    assert "複製" in line and "86406" in line


def test_positive_control_envelope_ends_are_load_bearing():
    """**陽性対照**: 端を生の読みに戻すと、上の 2件 の答えが変わること。"""
    rows = [_row("2026-09-10T15:24:00+09:00", 28, 84781),   # 窓の頭（この回の実物と同じ形）
            _row("2026-09-11T02:12:18+09:00", 28, 84781),
            _row("2026-09-11T02:12:43+09:00", 28, 86406),   # 25秒 差の新しい複製
            _row("2026-09-11T03:24:53+09:00", 28, 84781)]   # 端が遅れた複製
    cs = trend._channel_rows(rows)
    assert trend._pt_row(trend._channel_env_points(cs)[-1], end=True)["views"] == 86406
    assert cs[-1]["views"] == 84781            # ＝ 生で読めば +0（門が偽で引かれる側）
    assert trend.channel_growth(rows)["d_views"] == 1625


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
    assert abs(g["flat_h"] - 2.0) < 1e-9                      # 10:00 → 12:00
    line = trend.channel_line(rows)
    assert "3周（**2.0時間**）続けて同じ読み" in line          # **周と一緒に時間を言う**（04:0x）
    assert "引かれました" in line


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
    """**合計 ＞ チャンネル** ＝ 触っている本の増えを総再生が受け取っていない側だけ引く。

    **2026-09-10 19:3x に点を1つ足した**（`REPLICA_LAG_H` の門）—— 窓の両端 2点 だけでは、
    頭の 100 が遅れた複製だった目を外せないので、門は引けません（下の検査がその形）。
    12:00 の読み（＝ 09:00 + 2.8時間 より後）が、頭の真の値を上から抑えます。
    """
    rows = [_row("2026-09-10T09:00:00+09:00", 27, 84000),
            _row("2026-09-10T15:00:00+09:00", 27, 84010),   # +10
            _m("2026-09-10T09:00:00+09:00", "aaa", 100, 10.0),
            _m("2026-09-10T12:00:00+09:00", "aaa", 110, 13.0),  # 遅れの外の読み
            _m("2026-09-10T15:00:00+09:00", "aaa", 600, 16.0)]  # +500
    g = trend.channel_growth(rows)
    assert g["vid_sum"] == 500 and g["vid_confirmed"] == 490   # 600 - 110
    assert g["over"] is True
    assert "覆る条件 (1) が引かれます" in trend.channel_line(rows)


# ---- 遅れた複製で説明が付く伸びで門を引かない（2026-09-10 19:3x・optimizer・Opus） ----
# **踏んだ形**: 窓 15:24→19:14（3.8時間）の合計 +4回 は `lQHX9LJ80Sg` 1本（683→687）だけで、
# その本の生の読みは同じ 1時間 に **671 と 687** に割れていた ＝ 窓の頭の真の値が 683 か 687 かは
# その時点の台帳では分けられない。それでも (m) の門は **3周 続けて**引かれていた。

def test_遅れの外に読みが無ければ伸びは確かめられない():
    """窓の両端 2点 だけ ＝ 頭の値が遅れた複製だった目を外せない ＝ 門は引かない。"""
    rows = [_row("2026-09-10T09:00:00+09:00", 27, 84000),
            _row("2026-09-10T15:00:00+09:00", 27, 84010),
            _m("2026-09-10T09:00:00+09:00", "aaa", 100, 10.0),
            _m("2026-09-10T15:00:00+09:00", "aaa", 600, 16.0)]
    g = trend.channel_growth(rows)
    assert g["vid_sum"] == 500                 # 見えるようになった再生は +500
    assert g["vid_confirmed"] == 0             # 遅れの外で確かめられるのは 0
    assert g["vid_unconfirmable"] == 0         # 抑えの読みは在る（＝ 最後の点）
    assert g["over"] is False


def test_窓が遅れより短ければ測れていないと言う():
    """窓 ＜ `REPLICA_LAG_H` ＝ 抑えの読みが 1つも無い ＝ `None`（0 と言わない）。"""
    rows = [_row("2026-09-10T15:24:00+09:00", 27, 84781),
            _row("2026-09-10T16:41:00+09:00", 27, 84781),
            _row("2026-09-10T17:26:00+09:00", 27, 84781),
            _m("2026-09-10T15:24:00+09:00", "aaa", 100, 10.0),
            _m("2026-09-10T17:26:00+09:00", "aaa", 600, 12.0)]
    g = trend.channel_growth(rows)
    assert g["span_h"] < trend.REPLICA_LAG_H
    assert g["vid_confirmed"] is None and g["over"] is False
    assert "この窓では伸びを確かめられません" in trend.channel_line(rows)


def test_positive_control_遅れの門を外すと同じ並びで鳴る():
    """**陽性対照**: 分子を `sum` に戻すと、上の 2つ とも門が鳴ること
    （＝ 門を締めたのであって、鳴らない並びを選んだのではない）。"""
    rows = [_row("2026-09-10T09:00:00+09:00", 27, 84000),
            _row("2026-09-10T15:00:00+09:00", 27, 84010),
            _m("2026-09-10T09:00:00+09:00", "aaa", 100, 10.0),
            _m("2026-09-10T15:00:00+09:00", "aaa", 600, 16.0)]
    g = trend.channel_growth(rows)
    old_gate = (g["mismatch"] >= trend.CHANNEL_MISMATCH
                and g["vid_sum"] > g["d_views"])          # 19:3x より前の門
    assert old_gate is True and g["over"] is False


def test_実物の並び_遅れの外で伸びていれば引く():
    """同じ 3.8時間 の窓でも、遅れの外の読みより上へ伸びていれば門は引く。"""
    rows = [_row("2026-09-10T15:24:00+09:00", 27, 84781),
            _row("2026-09-10T19:14:00+09:00", 28, 84781),
            _m("2026-09-10T15:24:00+09:00", "lQHX9LJ80Sg", 683, 53.4),
            _m("2026-09-10T18:38:00+09:00", "lQHX9LJ80Sg", 685, 56.6),
            _m("2026-09-10T19:14:00+09:00", "lQHX9LJ80Sg", 687, 57.3)]
    g = trend.channel_growth(rows)
    assert g["vid_sum"] == 4 and g["vid_confirmed"] == 2   # 687 - 685
    assert g["over"] is True


def test_positive_control_two_sided_gate_would_fire_on_the_explainable_side():
    """**陽性対照**: 門を両側にすると、説明の付く側（チャンネル ＞ 合計）でも鳴る。"""
    rows = [_row("2026-09-10T09:00:00+09:00", 27, 84000),
            _row("2026-09-10T15:00:00+09:00", 27, 85000),
            _m("2026-09-10T09:00:00+09:00", "aaa", 100, 10.0),
            _m("2026-09-10T15:00:00+09:00", "aaa", 110, 16.0)]
    g = trend.channel_growth(rows)
    two_sided = g["mismatch"] >= trend.CHANNEL_MISMATCH        # 片側の門を外した形
    assert two_sided is True and g["over"] is False


def test_only_books_reread_inside_the_window_can_grow():
    """**窓の中で読み直した本**と、基準だけ持つ本を分ける（`measure` が触るのは 7日 以内）。"""
    rows = [_row("2026-09-10T09:00:00+09:00", 27, 84000),
            _row("2026-09-10T15:00:00+09:00", 27, 84060),
            _m("2026-09-10T09:00:00+09:00", "live", 100, 10.0),
            _m("2026-09-10T15:00:00+09:00", "live", 160, 16.0),
            _m("2026-09-09T09:00:00+09:00", "old", 500, 200.0)]   # 窓より前で止まっている
    g = trend.channel_growth(rows)
    assert g["vid_n"] == 2 and g["vid_fresh"] == 1
    assert g["vid_sum"] == 60                                     # 止まっている本は必ず +0
    assert "読み直した 1本" in trend.channel_line(rows)


def test_positive_control_stale_books_would_look_like_no_growth():
    """**陽性対照**: `fresh` を出さないと、止まっている本の +0 が「伸びなかった」に混ざる。"""
    rows = [_row("2026-09-10T09:00:00+09:00", 27, 84000),
            _row("2026-09-10T15:00:00+09:00", 27, 84000),
            _m("2026-09-09T09:00:00+09:00", "old1", 500, 200.0),
            _m("2026-09-09T10:00:00+09:00", "old2", 300, 200.0)]
    g = trend.channel_growth(rows)
    assert g["vid_n"] == 2 and g["vid_fresh"] == 0                # 読み直した本は 0本
    assert g["vid_sum"] == 0                                      # 合計 0 は「測っていない」の 0


# ---- `over` の回に §7 (m) を読ませない（2026-09-10 17:3x・optimizer・Opus。この回に実物で踏んだ） ----
# **踏んだ形**: 総再生 84781 が 4周 続けて同じ読み（門 3周 ＝ 引かれる）で、同じ窓の本ごとの合計は
# **+2回**（3本目 `lQHX9LJ80Sg` 685→687）。`record_channel` の覆る条件 (1) は「食い違ったら、この数で
# **チャンネルが止まったかを読まないこと**」なのに、行は同じ息で「チャンネルの側が止まっていないかを
# 外すこと」と言っていた ＝ **門は引けても、読みは引けません。**

def _flat_over_rows() -> list[dict]:
    """実物の形: 総再生が 3周 動かず・同じ窓で本だけ +2回。

    **2026-09-10 19:3x に窓を伸ばした**（`REPLICA_LAG_H` の門）—— 遅れ 2.8時間 より短い窓では
    伸びを確かめられないので、`over` の側の実物は窓 3.8時間・遅れの外に読み 2点 の形になる。
    """
    return [_row("2026-09-10T15:24:00+09:00", 27, 84781),
            _row("2026-09-10T16:41:00+09:00", 27, 84781),
            _row("2026-09-10T18:00:00+09:00", 27, 84781),
            _row("2026-09-10T19:14:00+09:00", 27, 84781),
            _m("2026-09-10T15:24:00+09:00", "lQHX9LJ80Sg", 685, 53.3),
            _m("2026-09-10T18:38:00+09:00", "lQHX9LJ80Sg", 685, 56.6),
            _m("2026-09-10T19:14:00+09:00", "lQHX9LJ80Sg", 687, 57.3)]


def test_over_の回は門を引いても止まったとは読ませない():
    rows = _flat_over_rows()
    g = trend.channel_growth(rows)
    assert g["flat_laps"] >= trend.CHANNEL_FLAT_LAPS and g["over"] is True
    line = trend.channel_line(rows)
    assert "引かれましたが、この窓では「チャンネルが止まった」と読めません" in line
    assert "チャンネルの側が止まっていないかを外すこと" not in line
    assert "動いていなければ、本ではなくチャンネルの側を疑う" not in line


def test_positive_control_over_でなければ元の読みが出る():
    """**陽性対照**: 食い違いが無ければ、同じ 3周 の平らで元の (m) の読みが出ること
    （消したのではなく、`over` の回にだけ差し替えていること）。"""
    rows = [r for r in _flat_over_rows() if r["event"] != "measured"]
    rows += [_m("2026-09-10T15:24:00+09:00", "lQHX9LJ80Sg", 685, 53.3),
             _m("2026-09-10T18:38:00+09:00", "lQHX9LJ80Sg", 685, 56.6),
             _m("2026-09-10T19:14:00+09:00", "lQHX9LJ80Sg", 685, 57.3)]
    g = trend.channel_growth(rows)
    assert g["flat_laps"] >= trend.CHANNEL_FLAT_LAPS and g["over"] is False
    line = trend.channel_line(rows)
    assert "チャンネルの側が止まっていないかを外すこと" in line


def test_総再生が動かない窓で登録だけ動いたら応答が丸ごと古いのではないと言う():
    """2026-09-10 21:1x —— 実測（`viewCount` 84,781 のまま・`subscriberCount` 27→28）。

    陽性対照: `channel_line` の `if g["d_views"] == 0 and g["d_subs"]:` を外すと落ちる。
    """
    rows = [_row("2026-09-10T15:24:00+09:00", 27, 84781),
            _row("2026-09-10T18:38:00+09:00", 28, 84781),
            _row("2026-09-10T20:27:00+09:00", 28, 84781)]
    g = trend.channel_growth(rows)
    assert g["d_views"] == 0 and g["d_subs"] == 1
    line = trend.channel_line(rows)
    assert "同じ窓で登録は +1 動いています" in line
    assert "丸ごと古いのではありません" in line
    assert "証拠になりません" in line, "外せるのは『総再生の数がこの窓で読めない』まで"


def test_登録も総再生も動かない窓では言わない():
    """覆る条件 (4) の側 —— 両方 動かない窓は、この文を出さないこと。"""
    rows = [_row("2026-09-10T15:24:00+09:00", 28, 84781),
            _row("2026-09-10T18:38:00+09:00", 28, 84781),
            _row("2026-09-10T20:27:00+09:00", 28, 84781)]
    assert "同じ窓で登録は" not in trend.channel_line(rows)
