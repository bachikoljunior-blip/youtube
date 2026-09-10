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
