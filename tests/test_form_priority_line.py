"""`cli.form_priority_line` —— **在庫のうち、きょうの口をどちらの形で埋めるか**。

**2026-09-19 00:3x・optimizer・opus。** 決めと覆る条件は `docs/METHOD.md` §5 の同じ刻の段。

**この行が在る理由**（検査が守っている当のもの）:
`LONG_SLOTS` 1 ＋ `SHORT_SLOTS` 5 ＝ **枠 6** に対し、日枠で上げられるのは **5本**
＝ 毎日 1枠 が必ず余るのに、**どの枠が余るかを決めていたのは `schedule` を撃った順だけ**でした。
実測は ショート 719回/本 対 長尺 1回/本 ＝ **長尺が 1本 座るたび 718回/日 を捨てます。**

**【2026-09-19 01:5x・optimizer・Opus 5・1周1体】上の 719 / 718 / 1 は、この file からも外しました。**
`trend.form_yield` の齢の門に**上端が無く**、形ごとに測った刻が違っても同じ表に並んでいたためです
（同じ台帳を `measure` の前後で引いて **719倍 → 357倍**・本も再生も変わっていない）。
**決めは変わっていません**（ショートが上限ぶん在る日は長尺を座らせない）。変えたのは**数の出どころ**で、
`cli._form_gap_phrase()` が**そのつど `trend.form_yield` から引きます**。
**だから、この検査は数を字で持ちません** —— 字で持つと、下の関数が直っても検査が古い数を守ってしまいます
（それがこの回に踏んだ欠陥そのもの）。守るのは「**`form_yield` から来ていること**」です。
derivation は `docs/JOURNAL.md` 2026-09-19 01:5x。

**【2026-09-19 02:3x・optimizer・Opus 5・1周1体】「座らせないこと」という命令を、この行からも外しました。**
その命令が乗っていた数は **中央の差**で、同じ台帳の**平均**では 357倍 → **18.7倍**、
**円/枠 では long ¥31.1 対 short ¥20.4 ＝ 向きが逆**でした（`trend.slot_value` の註・METHOD §5 同刻）。
**再生はどちらの扉の通貨でもありません**（扉(a) はショートの再生・扉(b) は時間と登録・収益は円）。
だから この行は**選択肢と数を出すだけ**にし、配りの決めは `trend.slot_value_line` へ送ります。
**検査が守るのは、いまも「数が `form_yield` から来ていること」**です（字で持たない）。
derivation は `docs/JOURNAL.md` 2026-09-19 02:3x。
"""
from studio import budget, cli, trend


def test_日枠の上限は枠の数ではなく日枠から出る():
    """**枠 6 と 上げられる 5 が別の数であること**（この検査が、この行の存在理由そのもの）。"""
    assert cli.day_upload_cap() == (budget.DAY_UNITS - budget.RESERVE) // budget.UPLOAD_UNITS
    assert cli.day_upload_cap() == 5
    assert len(cli.LONG_SLOTS) + len(cli.SHORT_SLOTS) == 6
    # **枠 ＞ 上げられる本数** ＝ 毎日 1枠 が必ず余る
    assert len(cli.LONG_SLOTS) + len(cli.SHORT_SLOTS) > cli.day_upload_cap()


def test_ショートが上限ぶん在る日は_選ぶ日だと言い_命令しない():
    ok = [f"s{i}" for i in range(5)] + ["L1"]
    forms = {f"s{i}": "short" for i in range(5)} | {"L1": "long"}
    line = cli.form_priority_line(ok, forms)
    assert "どちらで埋めるかを選ぶ日です" in line
    # **命令の字に戻さないこと**（判断はサブ・オーナー 2026-09-06 14:0x）。
    assert "座らせないこと" not in line, line
    # **数は字で持たず、`form_yield` から来ていることを挟む**（上の註）。
    d = trend.form_yield(cli.ledger_rows())
    s_, l_ = d.get("short"), d.get("long")
    if (s_ and l_ and s_["n_measured"] >= trend.FORM_MIN_N
            and l_["n_measured"] >= trend.FORM_MIN_N
            and s_["median"] is not None and l_["median"] is not None
            and s_["mean"] is not None and l_["mean"] is not None):
        # **中央と平均を両方 出すこと** —— 片方だけだと、この回の欠陥に戻ります。
        assert f"中央 {s_['median']:,.0f}回 対 {l_['median']:,.0f}回" in line, line
        assert f"平均 {s_['mean']:,.0f}回 対 {l_['mean']:,.0f}回" in line, line
        # **扉(b) の通貨の札**（ショートの再生はそこへ 1秒も入らない）。
        assert "扉(b) を 1秒も進めません" in line, line
    else:
        # **齢をそろえた比べが台帳に無い回は、数を出さないこと**（`form_yield` の覆る条件）。
        assert "いま引けません" in line, line


def test_ショートが足りない日は余りが長尺の口だと言う():
    ok = ["s0", "s1", "L1"]
    forms = {"s0": "short", "s1": "short", "L1": "long"}
    line = cli.form_priority_line(ok, forms)
    assert "3本 は長尺でしか埋まりません" in line
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
    assert "どちらで埋めるかを選ぶ日です" in line
