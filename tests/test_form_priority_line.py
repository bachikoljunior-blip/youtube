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
    """**枠の数と 上げられる本数が別の数であること**（この検査が、この行の存在理由そのもの）。

    **【2026-09-19 12:xx】数を字で持つのをやめました** —— 同じ日に天井が **5 → 6** に動き、
    この検査が **古い 5 を守って赤くなりました**（上の 01:5x が「字で持つと、下の関数が直っても
    検査が古い数を守る」と書いた、その型をこの検査自身が踏んだ）。守るのは**関係**です。
    """
    assert cli.day_upload_cap() == (budget.DAY_UNITS - budget.RESERVE) // budget.UPLOAD_UNITS_SHORT
    # **枠 ＞ 上げられる本数** ＝ 毎日 1枠 が必ず余る（長尺 1枠 ＋ ショート全部 ＞ 日枠の本数）
    assert len(cli.LONG_SLOTS) + len(cli.SHORT_SLOTS) > cli.day_upload_cap()


def test_ショートが上限ぶん在る日は_選ぶ日だと言い_命令しない():
    n = cli.day_upload_cap()
    ok = [f"s{i}" for i in range(n)] + ["L1"]
    forms = {f"s{i}": "short" for i in range(n)} | {"L1": "long"}
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


def test_ショートが足りない日は埋め方を2つとも名指しする():
    """**残りの本数を字で持たない**（天井は `budget` から動く・2026-09-19 12:xx）。

    **【2026-09-19 23:0x】題と中身を直しました**（optimizer・Opus 5・ultracode・1周 1体）——
    この検査は「**N本 は長尺でしか埋まりません**」という字を固定していましたが、
    **その字は 2026-09-19 18:xx に「嘘でした」として外されています**
    （`cli.form_priority_line` の註: 足りない口は (a) 長尺 ／ (b) その周でショートを書く の
    **2通り** で埋まり、同じ行の下半分が 102倍 の値段の差を既に印字していた）。
    **検査だけが古い字に残り、09/19 18:xx から毎周 落ちていました。**

    ＝ **決めが動いたのに、その決めを守る検査が前の字のままだった**形です。
    **いまの決め（埋め方を 2つ とも名指しし、命令の字には戻さない）を固定し直します。**

    **覆る条件**: (b) の口（`studio/series_*.py` の生成器）が無い題材しか残らない周が来たら、
    `cli.form_priority_line` の覆る条件のほうが先に引かれます（`trend.lap_value` の `周/本`）。
    """
    ok = ["s0", "s1", "L1"]
    forms = {"s0": "short", "s1": "short", "L1": "long"}
    line = cli.form_priority_line(ok, forms)
    need = cli.day_upload_cap() - 2
    # **足りない本数は字で持たず、天井から出ること**（もとの検査の狙いはそのまま）
    assert f"足りない **{need}本**" in line
    # **埋め方は 2つ とも名指しすること**（18:xx の決め）
    assert "(a) 長尺を座らせる" in line
    assert f"(b) この周でショートを {need}本 書く" in line
    # **命令の字には戻さないこと**（02:3x の決め・オーナー 09/06 14:0x「サブが判断する」）
    assert "座らせないこと" not in line
    assert "でしか埋まりません" not in line


def test_長尺の在庫が無い日は1字も出さない():
    """**選ぶ所が無い日に行を出さないこと** —— `status` は毎周 読む側（§5 の字の値段）。"""
    ok = ["s0", "s1"]
    assert cli.form_priority_line(ok, {"s0": "short", "s1": "short"}) == ""


def test_在庫が空なら1字も出さない():
    assert cli.form_priority_line([], {}) == ""


def test_form_を持たない古い台本はショートとして数える():
    """`script.form_of` と同じ既定（**古い台本は `form` を持ちません**）。"""
    ok = [f"old{i}" for i in range(cli.day_upload_cap())] + ["L1"]
    line = cli.form_priority_line(ok, {"L1": "long"})     # old* は forms に無い
    assert "どちらで埋めるかを選ぶ日です" in line
