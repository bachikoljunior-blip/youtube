"""**配りの向き**（`trend.channel_trajectory`）—— `trend` が 180行 を印字して、
**そのどれも「先週より増えたか減ったか」を言っていなかった**穴を塞ぐ行の検査
（2026-09-18 05:xx JST・optimizer・Fable 5.1・ultracode・**API 0単位**）。

ここで止めるのは 4つ:

  (1) **向きが出ること** —— 再生/日 が落ちて 1回あたり秒 が伸びた台帳で、
      落ちた側も伸びた側も両方 印字されること（**この 2つ が逆向きなのが、この行の言い分**）
  (2) **陰性対照** —— 同じ形のまま横ばいの台帳では、倍率が 1.0 付近に出ること
      （＝ この行は「必ず落ちていると言う」行ではない）
  (3) **引きが埋まらなかった日（再生 0）を平均に入れないこと**
      —— 実測 2026-09-13 が 0回 で、両隣は 240回・292回 だった
  (4) **日が足りないうちは倍率を出さないこと**（`TRAJ_EDGE_DAYS × 2` 未満）
      ＝ 両端が同じ日を食べて 1.00 が必ず出る穴
"""
from studio import trend


def _day(d, views, minutes):
    return {"event": "analytics_day", "id": d, "views": views,
            "minutes": minutes, "at": f"{d}T12:00:00+09:00"}


def _falling():
    """再生は 10分の1 へ・1回あたり秒 は 3倍 へ（実測 08/27→09/14 と同じ向き）。"""
    rows = []
    for i in range(5):                      # 頭 5日: 3,000回 / 300分 ＝ 6.0秒
        rows.append(_day(f"2026-08-{27 + i:02d}", 3000, 300))
    for i in range(5):                      # 尻 5日: 300回 / 90分 ＝ 18.0秒
        rows.append(_day(f"2026-09-{10 + i:02d}", 300, 90))
    return rows


def test_落ちた側と伸びた側が両方出る():
    t = trend.channel_trajectory(_falling())
    assert t["views_ratio"] is not None
    assert round(t["views_ratio"], 2) == 0.1          # 再生は 10分の1
    assert round(t["sec_ratio"], 1) == 3.0            # 1回あたり秒 は 3倍
    line = trend.channel_trajectory_line(_falling())
    assert "配りの向き" in line
    assert "10.0分の1" in line
    assert "3.0倍" in line
    # **扉(b) までの日数**が出ること（4,000時間 ÷ いまの視聴分/日）
    assert t["door_b_days"] is not None
    assert round(t["door_b_days"]) == round(trend.REV_LONG_HOURS * 60 / 90)


def test_陰性対照_横ばいなら倍率は1付近():
    rows = [_day(f"2026-09-{1 + i:02d}", 500, 150) for i in range(10)]
    t = trend.channel_trajectory(rows)
    assert round(t["views_ratio"], 2) == 1.0
    assert round(t["sec_ratio"], 2) == 1.0
    assert round(t["min_ratio"], 2) == 1.0


def test_引きが埋まらなかった日は平均に入れない():
    rows = [_day(f"2026-09-{1 + i:02d}", 500, 150) for i in range(10)]
    rows.append(_day("2026-09-11", 0, 0))            # 実測 09/13 と同じ形
    t = trend.channel_trajectory(rows)
    assert t["zero_days"] == 1
    assert all(v > 0 for _, v, _, _ in t["days"])
    # 0 の日を尻に入れてしまうと、尻の平均は 500 → 416 に落ちて「配りが落ちた」に見える
    assert round(t["tail"][2]) == 500


def test_日が足りないうちは倍率を出さない():
    rows = [_day(f"2026-09-{1 + i:02d}", 500, 150)
            for i in range(trend.TRAJ_EDGE_DAYS * 2 - 1)]
    t = trend.channel_trajectory(rows)
    assert t["views_ratio"] is None
    assert "まだ向きを出しません" in trend.channel_trajectory_line(rows)


# ---------------------------------------------------------------------------
# **尻が古い台帳**（2026-09-18 08:xx JST・optimizer・Opus・**API 0単位**）
#
# 前の形は、**視聴分/日 の倍率と無関係に**「この 2つ は打ち消し合っています ＝
# 扉(b) に積まれる量は動いていません」と印字していました。
# 実物で **1.57倍**（増えている）の回にも同じ文が出ます ＝ **数が否定しても覆らない文**。
# 原因は 2つ とも `analytics_day` の**尻**にありました:
#   (1) 09-13 が **0回** のまま（引けなかった日）・(2) 09-15 が**台帳に無い**（撃っていない）
# 撃ち直したら 09-13 は 1,154回/447分・09-15 は 1,269回/494分 で、
# 倍率は **1.01倍 → 1.57倍**、扉(b) までは **1,223日 → 790日** に変わりました。
#
# ここで止めるのは 4つ:
#   (5) **尻が古い回は「暫定」と言うこと**（陽性対照）
#   (6) **尻が新しい回は言わないこと**（陰性対照 ＝ 必ず暫定と言う行ではない）
#   (7) **遅れは台帳の `lag_days` から取ること**（前提の 3日 を決め打ちしない）
#   (8) **視聴分/日 の向きの文が、倍率から出ること**（増えた／横ばい／減った の 3つ）
# ---------------------------------------------------------------------------
import datetime as _dt

from studio.common import JST as _JST


def _now(d):
    return _dt.datetime.fromisoformat(d + "T08:00:00").replace(tzinfo=_JST)


def _flat(views=500, minutes=150, start=1, n=10):
    return [_day("2026-09-%02d" % (start + i), views, minutes) for i in range(n)]


def test_陽性対照_尻が古い回は暫定と言う():
    rows = _flat()                                   # 最後の日は 09-10
    # 遅れ 3日 なら、09-18 に引けるはずの日は 09-15 ＝ 5日 手前
    t = trend.channel_trajectory(rows, now=_now("2026-09-18"))
    assert t["last_day"] == "2026-09-10"
    assert t["stale_days"] == 5
    assert "【暫定】" in trend.channel_trajectory_line(rows, now=_now("2026-09-18"))


def test_陰性対照_尻が新しい回は暫定と言わない():
    rows = _flat()                                   # 最後の日は 09-10
    # 遅れ 3日 なら、09-13 に引けるはずの日は 09-10 ＝ ちょうど追いついている
    t = trend.channel_trajectory(rows, now=_now("2026-09-13"))
    assert t["stale_days"] == 0
    assert "【暫定】" not in trend.channel_trajectory_line(rows, now=_now("2026-09-13"))


def test_遅れは台帳のlag_daysから取る():
    rows = _flat() + [{"event": "analytics_traffic", "id": "2026-09-10",
                       "at": "2026-09-13T08:00:00+09:00", "lag_days": 6}]
    t = trend.channel_trajectory(rows, now=_now("2026-09-16"))
    assert t["lag_days"] == 6                        # 3 ではない
    assert t["stale_days"] == 0                      # 09-16 − 6日 ＝ 09-10


def test_視聴分の向きの文は倍率から出る():
    head = [_day("2026-08-%02d" % (27 + i), 3000, 300) for i in range(5)]

    def line(v, m):
        rows = head + [_day("2026-09-%02d" % (10 + i), v, m) for i in range(5)]
        return trend.channel_trajectory_line(rows, now=_now("2026-09-17"))

    # 増えた側（実測 09/18 の形: 回は落ちたが 分 は 1.57倍）
    up = line(300, 470)
    assert "積まれる量は増えています" in up
    assert "動いていません" not in up
    # 横ばい（帯の中）
    assert "打ち消し合っています" in line(300, 300)
    # 減った側
    assert "積まれる量は減っています" in line(300, 90)
