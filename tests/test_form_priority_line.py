"""`cli.form_priority_line` —— **在庫のうち、きょうの口をどちらの形で埋めるか**。

**2026-09-19 00:3x・optimizer・opus。** 決めと覆る条件は `docs/METHOD.md` §5 の同じ刻の段。

**この行が在る理由**（検査が守っている当のもの）:
`LONG_SLOTS` 1 ＋ `SHORT_SLOTS` 5 ＝ **枠 6** に対し、日枠で上げられるのは **5本**
＝ 毎日 1枠 が必ず余るのに、**どの枠が余るかを決めていたのは `schedule` を撃った順だけ**でした。
実測は ショート 719回/本 対 長尺 1回/本 ＝ **長尺が 1本 座るたび 718回/日 を捨てます。**
"""
from studio import budget, cli


def test_日枠の上限は枠の数ではなく日枠から出る():
    """**枠 6 と 上げられる 5 が別の数であること**（この検査が、この行の存在理由そのもの）。"""
    assert cli.day_upload_cap() == (budget.DAY_UNITS - budget.RESERVE) // budget.UPLOAD_UNITS
    assert cli.day_upload_cap() == 5
    assert len(cli.LONG_SLOTS) + len(cli.SHORT_SLOTS) == 6
    # **枠 ＞ 上げられる本数** ＝ 毎日 1枠 が必ず余る
    assert len(cli.LONG_SLOTS) + len(cli.SHORT_SLOTS) > cli.day_upload_cap()


def test_ショートが上限ぶん在れば長尺を座らせないと言う():
    ok = [f"s{i}" for i in range(5)] + ["L1"]
    forms = {f"s{i}": "short" for i in range(5)} | {"L1": "long"}
    line = cli.form_priority_line(ok, forms)
    assert "ともショートで埋まります" in line
    assert "座らせないこと" in line
    assert "718回/日" in line


def test_ショートが足りない日は余りが長尺の口だと言う():
    ok = ["s0", "s1", "L1"]
    forms = {"s0": "short", "s1": "short", "L1": "long"}
    line = cli.form_priority_line(ok, forms)
    assert "余る 3本 が長尺の口" in line
    assert "座らせないこと" not in line


def test_長尺の在庫が無い日は1字も出さない():
    """**選ぶ所が無い日に行を出さないこと** —— `status` は毎周 読む側（§5 の字の値段）。"""
    ok = ["s0", "s1"]
    assert cli.form_priority_line(ok, {"s0": "short", "s1": "short"}) == ""


def test_在庫が空なら1字も出さない():
    assert cli.form_priority_line([], {}) == ""


def test_form_を持たない古い台本はショートとして数える():
    """`script.form_of` と同じ既定（**古い台本は `form` を持ちません**）。"""
    ok = ["old0", "old1", "old2", "old3", "old4", "L1"]
    line = cli.form_priority_line(ok, {"L1": "long"})     # old* は forms に無い
    assert "ともショートで埋まります" in line
