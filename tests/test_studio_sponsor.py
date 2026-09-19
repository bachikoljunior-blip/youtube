"""`studio/sponsor.py` の検査（**API 0単位**・台帳だけ）。

**この file が守るのは 3つ**:
 (1) **写しを持たないこと** —— 単価の帯も 本/日 の天井も `studio/trend` の 1か所から来る。
     写した日に、帯が動いても追わなくなる（`trend.sponsor_daily_cap_videos` が
     2026-09-18 に踏んだ穴と同じ形）。**規則の数を検査に写さないこと**も同じ向きで、
     ここは値ではなく **`trend` と一致するか** だけを見る（JOURNAL 2026-09-20 §11）。
 (2) **測っていない物を売りにしないこと** —— 相手の齢が `measured: False` の周は、
     媒体資料から年齢の行が落ちる（`sponsor` の覆る条件 (3)）。**陽性対照つき**。
 (3) **口を読んでいない相手を、読んだ側に混ぜないこと**（`checked_targets`）。
"""
from __future__ import annotations

import pytest

from studio import sponsor, trend


# --- (1) 写しを持たない -------------------------------------------------------

def _rows():
    from studio.cli import ledger_rows
    return ledger_rows()


def test_帯は_trend_の_1か所から来る():
    k = sponsor.kit(_rows())
    assert tuple(k["band"]) == tuple(trend.SPONSOR_YEN_PER_VIEW_BAND)


def test_本日の天井は_trend_の_1か所から来る():
    k = sponsor.kit(_rows())
    assert k["per_day_cap"] == trend.sponsor_daily_cap_videos()


def test_月額は_再生月_かける_帯_そのもの():
    """**式を写さない**: 3段 とも `views_month × band` と一致すること。"""
    k = sponsor.kit(_rows())
    for lv, b in zip(trend.YEN_LEVELS, k["band"]):
        assert k["price"][lv]["now"] == pytest.approx(k["views_month"] * b)
        assert k["price"][lv]["cap"] == pytest.approx(k["views_month_cap"] * b)


def test_帯が動いたら月額も動く_陽性対照(monkeypatch):
    """**写しを持っていたら、ここで止まります。**"""
    before = sponsor.kit(_rows())["price"]["中"]["cap"]
    monkeypatch.setattr(trend, "SPONSOR_YEN_PER_VIEW_BAND", (1.0, 3.0, 6.0))
    after = sponsor.kit(_rows())["price"]["中"]["cap"]
    assert after == pytest.approx(before * 2.0)


def test_再生月と天井は_ungated_yen_と同じ数():
    rows = _rows()
    d = trend.ungated_yen(rows)
    k = sponsor.kit(rows)
    assert k["views_month"] == pytest.approx(d["views_month"])
    assert k["views_month_cap"] == pytest.approx(d["cap"]["views_month"])


# --- (2) 測っていない物を売りにしない ------------------------------------------

def test_齢が測れていない周は媒体資料から年齢の行が落ちる(monkeypatch):
    monkeypatch.setattr(trend, "audience_split", lambda *a, **k: {"measured": False})
    s = sponsor.sheet(_rows())
    assert "65歳以上" not in s
    assert "載せていません" in s


def test_齢が測れている周は年齢の行が出る_陽性対照():
    """上の検査が『いつも落ちる』で通っていないことを確かめる側。"""
    a = trend.audience_split(_rows()) or {}
    if not a.get("measured"):
        pytest.skip("この台帳では齢が測れていない（陽性対照は張れない）")
    s = sponsor.sheet(_rows())
    assert "65歳以上" in s


def test_文面はmdではなくメールの本文(monkeypatch):
    """`**` が混じると、貼った先でそのまま字として出ます。"""
    body = sponsor.letter(_rows())
    assert "**" not in body


def test_文面は値段を書かない():
    """1通目に値段を出さない（`letter` の註）。"""
    k = sponsor.kit(_rows())
    body = sponsor.letter(_rows())
    for lv in trend.YEN_LEVELS:
        assert f"{k['price'][lv]['cap']:,.0f}" not in body


def test_媒体資料と文面はどちらもPRの表示を持つ():
    """景表法・ステマ規制（`sponsor` の覆る条件 (5)・`studio/asp.py` と同じ向き）。"""
    rows = _rows()
    assert "【PR】" in sponsor.sheet(rows)
    assert "【PR】" in sponsor.letter(rows)


# --- (3) 口を読んでいない相手を混ぜない ----------------------------------------

def test_読んだ相手だけがchecked_targetsに入る():
    got = sponsor.checked_targets()
    assert got, "口を読んだ相手が 0社 なら、オーナーに出せる行が 1つ もありません"
    assert all(t["checked"] for t in got)
    assert len(got) <= len(sponsor.TARGETS)


def test_読んだと書いた相手は出どころに日付を持つ():
    for t in sponsor.checked_targets():
        assert t["src"] != "未読"
        assert "2026-" in t["src"], f"{t['name']} の出どころに読んだ日がありません"


def test_読んでいない相手は宛先に未確認の札を立てる():
    for t in sponsor.TARGETS:
        if not t["checked"]:
            assert "未確認" in t["route"]


def test_短い行は_まだ送っていないことを言う():
    line = sponsor.short(_rows())
    assert line
    assert "0社" in line or "まだ 1社 も送っていません" in line


# --- (4) 本数は「読んだ回数」ではない -------------------------------------------
# **2026-09-20 04:xx に踏んだ穴**（optimizer・Opus 5・ultracode）: `sponsor.kit` が
# `trend.channel_growth()["n"]`（＝ **チャンネルを読んだ台帳の行数**）を本数として拾い、
# `sheet`／`letter` が `本数 {n}本` と刷っていました ＝ **媒体資料と送り状が 359本
# （実物 293本・22% 多い側）と名乗っていた**。出す先は実在の会社なので、
# **1通目で崩れる種類の狂い**です。本数は同じ台帳行の `videos` 欄（`cli.py:890` の
# `videoCount` と同じ数・**API 0単位**）から取ること。

def test_sheet_video_count_is_not_the_lap_count():
    rows = _rows()
    g = trend.channel_growth(rows)
    k = sponsor.kit(rows)
    assert k["n"] == g["videos"], "本数は `videos`（実物）から取ること"
    if g["videos"] is not None and g["n"] != g["videos"]:
        assert k["n"] != g["n"], (
            "`channel_growth()['n']` は台帳の行数（チャンネルを読んだ回数）であって "
            "本数ではありません —— これを刷ると媒体資料が実物より多く名乗ります"
        )


def test_channel_growth_videos_matches_the_last_channel_row():
    rows = _rows()
    g = trend.channel_growth(rows)
    cs = trend._channel_rows(rows)
    assert g["videos"] == (cs[-1].get("videos") if cs else None)


def test_本数が読めない周は本数を名乗らない():
    """`videos` が無い台帳（古い周）でも落ちず、**嘘の本数を刷らない**こと。"""
    rows = [dict(r) for r in _rows()]
    for r in rows:
        if r.get("event") == "channel":
            r.pop("videos", None)
    g = trend.channel_growth(rows)
    assert g["videos"] is None, "書いていない数は None（0 と読まないこと）"
    s, l = sponsor.sheet(rows), sponsor.letter(rows)
    assert "本数" not in s, "読めない本数を名乗らないこと"
    assert "これまでに" not in l
    # 総再生と登録は残ること（落とすのは本数の 1語 だけ）
    assert "総再生" in s and "総再生" in l


# --- (5) 1通目の頼みの形 -------------------------------------------------------
# **2026-09-20 06:xx に変えた**（optimizer・Opus 5・ultracode）: 1通目 が頼むのは
# 「タイアップのご相談は可能でしょうか」（＝ 相手に**予算の決裁**をさせる頼み）ではなく、
# **「まず費用をいただかずに 1本 作って実績をご報告します」**（＝ 相手の判断が
# **掲載可否の一存**に落ちる）。**決めと覆る条件 (A)(B)(C) は `studio/sponsor.py`
# 「1通目の頼みの形」の註** ＝ ここへ写さないこと。

def test_1通目は無料の試しを頼む():
    body = sponsor.letter(_rows())
    assert "費用をいただかず" in body, (
        "1通目の頼みが『無料の試し』でなくなっています "
        "（戻すなら `studio/sponsor.py`「1通目の頼みの形」の覆る条件 (A) を引くこと）"
    )
    assert "ご興味があればご返信" not in body, "受け身の頼みへ戻っています"


def test_1通目はこちらが持っていない数を約束しない():
    """クリック数はこちらの口では読めません（Shorts のリンクは押せない・`studio/asp.py`）。

    約束してよいのは **再生数・視聴維持率** と、**相手の計測用URLをそのまま載せること**だけ。
    """
    body = sponsor.letter(_rows())
    assert "計測用URL" in body
    assert "クリック数" not in body, "こちらが読めない数を実績として約束しています"


def test_窓の貼る文と道具の頼みの形がそろっている():
    """**窓は手書きの写しです**（前の周の申し送り）—— 道具だけ直すと、貼られる字は古いまま。"""
    import pathlib
    md = pathlib.Path(__file__).resolve().parents[1] / "docs" / "FOR_OWNER.md"
    if not md.exists():                      # repo の外で走らせた周
        pytest.skip("docs/FOR_OWNER.md が無い")
    txt = md.read_text(encoding="utf-8")
    if "### 出す 2026-09-21 09:00" not in txt:   # 窓が畳まれた周
        pytest.skip("09/21 の窓はもう在りません")
    assert "費用をいただかず" in txt, (
        "`sponsor.letter` は無料の試しを頼むのに、09/21 の窓の貼る文が古い字のままです"
    )


# --- (6) 一覧の「社数」は、ちがう会社の数であること ------------------------------
# **2026-09-20 06:xx に踏んだ穴**（optimizer・Opus 5・ultracode）: `TARGETS` の 5番目
# （エイチームライフデザイン・ライフドット）は **1番目（鎌倉新書）と同じ相手**でした ——
# ライフドット事業は 2025-06-02 に 鎌倉新書 へ譲渡ずみ。`short()` は毎周 status に
# 「相手の一覧 5社」と刷っていて、**実際に送れる先は 4社** でした。
# **決めと覆る条件は `studio/sponsor.py` の註 ＝ ここへ写さないこと。**

def test_相手の名は重複しない():
    names = [t["name"] for t in sponsor.TARGETS]
    assert len(names) == len(set(names)), f"同じ相手が 2行 入っています: {names}"


def test_読んだ相手の宛先はURLか電話を持つ():
    """`checked` が True ＝ 口を開いた、です。開いた口は場所を持ちます。"""
    for t in sponsor.checked_targets():
        assert "http" in t["route"] or "-" in t["route"], (
            f"{t['name']} の宛先に、開ける場所がありません"
        )


def test_窓に出る宛先は口を読んだ相手だけ():
    """**窓へ URL を写すのは手作業です** —— 読んでいない相手が混ざると、その 1通 は捨て札。

    09/21 の窓に在る `https://` の URL は、`checked_targets()` の `route` の中に在ること。
    """
    import pathlib, re
    md = pathlib.Path(__file__).resolve().parents[1] / "docs" / "FOR_OWNER.md"
    if not md.exists():
        pytest.skip("docs/FOR_OWNER.md が無い")
    txt = md.read_text(encoding="utf-8")
    if "### 出す 2026-09-21 09:00" not in txt:
        pytest.skip("09/21 の窓はもう在りません")
    blk = txt.split("### 出す 2026-09-21 09:00", 1)[1].split("\n### ", 1)[0]
    urls = set(re.findall(r"https://\S+", "\n".join(
        l for l in blk.splitlines() if l.startswith("> "))))
    routes = " ".join(t["route"] for t in sponsor.checked_targets())
    for u in urls:
        assert u in routes, f"窓の宛先 {u} が、口を読んだ相手の route に在りません"
