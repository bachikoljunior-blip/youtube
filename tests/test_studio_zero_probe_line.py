"""`trend.zero_probes` / `zero_probe_line` —— 台帳 `zero_probe` を **`trend` が毎周 印字する**。

2026-09-10 15:2x・optimizer・Opus。`cli.zero_probe_target` を足した同じ回に足した。
`cli.over_ledger`（12:4x に印字だけ足し、13:2x に数える口を足した）と同じ族の穴を
**同じ回のうちに**塞ぐため —— 覆る条件が「7本 過ぎて 1度も出なければ外す」＝ 周をまたぐので、
印字して捨てるだけでは次の回が引けない。

**陽性対照つき**（§5 の教訓の形 3つ目）。2026-09-10 15:2x に動かして確かめた:
  * `bad` を `ok` で数えない（`not r.get("ok")` を `r.get("ok")` に）→ **3件** 落ちる
    （`test_okでない行を名指しする`・`test_okだけなら口を外す条件を名指しする`・
     `test_同じ本を何周撃っても本の数は1本` —— `ok` の数え方は 3つ の行に出るので、
     **1件しか落ちないと書いたら、それは対照を撃っていない印**）
  * `zero_probe_line` を `trend` の並びから外す → `test_trendの並びに出る` が落ちる
  * 0件 のときの文から「0回 の本がこの窓に無かった」を消す → `test_0件は落ちた本が無いと読ませない` が落ちる
"""
from studio import trend


OK = {"event": "zero_probe", "id": "a", "ok": True, "upload": "processed",
      "processing": "succeeded", "failure": None, "at": "2026-09-10T14:37:10+09:00"}
BAD = {"event": "zero_probe", "id": "b", "ok": False, "upload": "rejected",
       "processing": "failed", "failure": "copyright", "at": "2026-09-10T15:20:00+09:00"}


def test_印が無ければ0件():
    z = trend.zero_probes([{"event": "measured", "id": "a", "views": 1}])
    assert (z["n"], z["books"], z["ok"], z["bad"]) == (0, 0, 0, [])


def test_0件は落ちた本が無いと読ませない():
    """`§4 (0-b)` の「0件 を『大丈夫』と読まない」の族。この 0 は分母の 0。"""
    s = trend.zero_probe_line([])
    assert "0件" in s and "0回 の本がこの窓に無かった" in s


def test_同じ本を何周撃っても本の数は1本():
    z = trend.zero_probes([OK, dict(OK, at="2026-09-10T15:19:00+09:00")])
    assert (z["n"], z["books"], z["ok"]) == (2, 1, 2)


def test_okだけなら口を外す条件を名指しする():
    s = trend.zero_probe_line([OK])
    assert "0回 は本物" in s and "7本" in s


def test_okでない行を名指しする():
    z = trend.zero_probes([OK, BAD])
    assert len(z["bad"]) == 1 and z["ok"] == 1
    s = trend.zero_probe_line([OK, BAD])
    assert "!!" in s and "copyright" in s and "配りが来ていない" in s


def test_trendの並びに出る():
    """毎周 印字されること —— 次の回が前の回の端末の出力を覚えていなくてよい。"""
    body = "\n".join(trend.lines([OK]))
    assert "公開ずみで 0回 の本の処理" in body


# --- 門が齢で閉じたことを言う行（2026-09-12 19:3x・optimizer・Opus） ---------
#
# **陽性対照つき**（§5 の教訓の形 3つ目）。この回に動かして確かめた（`.pyc` を消してから・11つ目）:
#   * `zero_probes` の `closed` を常に `[]` にする → **2件**
#     （`test_門を越えた0回の本を名指しする`・`test_最後の印の刻を出す`）
#   * `ZERO_PROBE_MAX_H` を 48.0 に戻す → **3件**
#     （`test_門は下敷きの上端を覆う`・`test_下敷きの窓の中の0回の本はまだ診られる`・
#      **`test_門の中の0回の本は名指ししない`** —— 齢 57.4h が門の外へ出るので、
#      「まだ診られる」と「名指ししない」は**同じ 1つ の門**を裏表から見ている）
#   * `cli.ZERO_PROBE_MAX_H` を自前の数（48.0）に戻す → **2件**
#     （`test_門は道具に1つ`・`test_下敷きの窓の中の0回の本はまだ診られる`）
# **この回はファイル単独でも撃った**（13件・§5 教訓の形 11つ目）。

import datetime as dt

from studio import cli
from studio.common import JST


def _series(vid: str, ages: list[float], views: int = 0) -> list[dict]:
    """`ours` と `series` が要る最小の行（`scheduled` ＋ `measured`）。"""
    rows = [{"event": "scheduled", "video_id": vid, "at": "2026-09-10T10:00:00+09:00"}]
    for a in ages:
        rows.append({"event": "measured", "id": vid, "age_h": a, "views": views,
                     "at": "2026-09-12T19:00:00+09:00"})
    return rows


def test_門は道具に1つ():
    """`cli` は自前の数を持たない —— 註と印字が食い違えば、読まれるのは印字のほう。"""
    assert cli.ZERO_PROBE_MAX_H == trend.ZERO_PROBE_MAX_H
    assert cli.ZERO_PROBE_MIN_H == trend.ZERO_PROBE_MIN_H


def test_門は下敷きの上端を覆う():
    """`zero_start` の B の初点の最も遅い1本は 齢 77.6h（§7 (c) の 09/13 16:00）。"""
    assert trend.ZERO_PROBE_MAX_H >= 77.6


def test_下敷きの窓の中の0回の本はまだ診られる():
    """齢 57.4h の 5本目 は、下敷きの窓の中 ＝ 門は開いていること。"""
    now = dt.datetime.now(JST)
    at = (now - dt.timedelta(hours=57.4)).astimezone(dt.timezone.utc)
    v = {"id": "z", "views": 0, "views_absent": False, "privacy": "public",
         "publish_at": None,
         "published_at": at.isoformat().replace("+00:00", "Z")}
    assert cli.zero_probe_target([v], {"z"}, now) == "z"


def test_門の中の0回の本は名指ししない():
    s = trend.zero_probe_line([OK] + _series("z", [10.0, 57.4]))
    assert "印はもう増えません" not in s


def test_門を越えた0回の本を名指しする():
    """**この口は齢で黙ります** —— 黙ったことを言わないと、件数がいまの齢の話に読まれる。"""
    s = trend.zero_probe_line([OK] + _series("z", [10.0, 80.2]))
    assert "!!" in s and "印はもう増えません" in s and "z 齢 80.2h" in s


def test_最後の印の刻を出す():
    """「いつまで見ていたか」が無いと、件数だけが残る。"""
    s = trend.zero_probe_line([OK] + _series("z", [80.2]))
    assert "09/10 14:37" in s


def test_再生が付いた本は門の外でも名指ししない():
    s = trend.zero_probe_line([OK] + _series("z", [80.2], views=5))
    assert "印はもう増えません" not in s
