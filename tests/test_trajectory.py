"""`scripts/trajectory.py` が、**次に来た側に前と同じ間違いをさせない**ための検査。

守っているのは3つです。どれも 2026-08-20 に実際に踏んだ形です。

1. **伸び率で日付を作らないこと。** `eta.py` は `growth_per_day` 5.38%/日 を
   100日ぶん複利で伸ばしていました。実測の区間は t=0.14 で 0 をまたぎ、
   100日ぶん伸ばすと区間が桁で9つ開きます。**軌跡が伸び率に依存していたら、
   その日付は測っていない数から出ています。**
2. **恒等式が閉じていること。** 日次再生 ＝ 供給 × V。閉じている間だけ
   「後ろカタログが無い」と言えます。**閉じなくなったら、減衰項が要ります。**
3. **代用と未測定に札が付いていること。** この回の欠陥は全部
   「代用を実測と同じ字で出した」ことでした。
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location("trajectory", ROOT / "scripts" / "trajectory.py")
traj = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(traj)

TODAY = dt.date(2026, 8, 20)


@pytest.fixture(scope="module")
def m():
    return traj.measure(TODAY)


# --- 1. 伸び率で日付を作っていないこと -------------------------------------

def test_floor_date_does_not_move_when_growth_moves(m):
    """**伸び率を 10倍にしても 0 にしても、床の日付が1日も動かないこと。**

    動いたら、その日付は「測っていない伸び率」から出ています。
    `eta.py` の 2026-08-20 以前の軌跡はここで落ちます。
    """
    base = m["stages"]["floor_date"]
    for g in (0.0, m["trend"]["g"] * 10, -0.5):
        tr = dict(m["trend"], g=g)
        st = traj.stages(None, None, m["identity"], m["decay"], m["per_video"],
                         m["supply"], tr, m["subs"], m["traffic"], m["reach"], TODAY)
        assert st["floor_date"] == base, f"伸び率 {g} で床が {st['floor_date']} に動きました"


def test_growth_is_reported_with_an_interval(m):
    """伸び率を印字するなら、**必ず区間と t 値を添えること。**"""
    tr = m["trend"]
    assert tr["ok"]
    assert tr["lo"] < tr["g"] < tr["hi"]
    assert "significant" in tr
    text = "\n".join(traj.render(m, TODAY))
    assert "95%区間" in text
    assert f"t = **{tr['t']:.2f}**" in text


def test_growth_is_always_decomposed_before_it_is_used(m):
    """**左辺の傾きは、必ず供給と V に割ってから使うこと。**

    ## この検査がここに在る経緯（2026-08-25 に書き換えた）

    前の姿はこうでした ——

        if tr["significant"]:
            pytest.fail("日次再生の傾きが有意になりました。軌跡の設計を見直すこと")

    註にこう添えてありました: **「落ちたこと自体が『複利の項を軌跡に入れて
    よくなった』という報せなので、検査を直すのではなく軌跡のほうを設計し直せ」。**

    **落ちました**（t = 0.14 → **3.20**・傾き 1日 +0.77% → **+12.30%**）。
    そこで `trajectory.trend_decompose()` を足し、この検査を**新しい不変量**に
    置き換えています。**「有意になったら複利を入れてよい」は誤り**でした ——
    恒等式 **日次再生 ＝ 供給 × V** の log を採ると傾きは足し算に割れ、
    **供給の側は軌跡がすでに天井付きで持っている**からです。
    左辺をそのまま複利にすると、**天井のある伸びを天井の無い複利として二重に数えます。**

    実測（08/16〜08/22・n=7。帳面が供給を持つのは 08/16 から）——
    **有意なのは供給だけ**（t=+3.05）で、V は t=-1.02、左辺すら t=+1.66 でした。
    **19日で採った t=3.20 は、供給が立ち上がった跡です。**
    """
    tr, td = m["trend"], m["decompose"]
    text = "\n".join(traj.render(m, TODAY))

    # 1. 左辺が有意なら、**裸で「有意ではありません」と言わないこと**
    if not tr["significant"]:
        assert "有意ではありません" in text

    # 2. **割り算が必ず印字されること**（有意かどうかに関わらず）
    assert "d log(再生) ＝ d log(供給) ＋ d log(V)" in text
    assert "trend_decompose()" in text

    # 3. 割れた回は、3つとも t 付きで出ること
    if td.get("ok"):
        for key in ("views", "supply", "v"):
            r = td[key]
            if r.get("ok"):
                assert f"t = **{r['t']:+.2f}**" in text


def test_compound_term_needs_the_V_slope_not_the_left_hand_side(m):
    """**複利の項を立ててよいのは、V の傾きが有意に正のときだけ。**

    左辺（日次再生）や供給の傾きがいくら有意でも、それは根拠になりません。
    ここが緩むと `eta.py` が 2026-08-20 まで踏んでいた `growth_per_day`
    5.38%/日 に戻ります。
    """
    td = m["decompose"]
    if not td.get("ok"):
        assert td.get("why"), "割れない回は、割れない理由を言うこと"
        return
    v = td["v"]
    if td["compound"]:
        assert v["ok"] and v["significant"] and v["b"] > 0
        assert td["n"] >= traj.DECOMPOSE_MIN_DAYS
    else:
        # **入れない回は、入れない理由が印字されること**（`CLAUDE.md` の (イ)）
        text = "\n".join(traj.render(m, TODAY))
        assert "**複利の項は入れません。** 理由:" in text
        assert "固定しているものを名前で言うと" in text
        assert "V ＝ 今日の実測のまま" in text


def test_decomposition_is_additive(m):
    """**3つの傾きが足し算で閉じること。** log(再生) = log(供給) + log(V) の帰結。

    閉じないなら、左辺と分母が別のものを見ています（供給の日の割り方が
    ずれている、など）。**そのとき V の傾きは意味を持ちません。**
    """
    td = m["decompose"]
    if not td.get("ok"):
        pytest.skip(td.get("why", "割れません"))
    assert td["additive"] is True, "3つの傾きが足し算で閉じていません"
    assert td["views"]["b"] == pytest.approx(td["supply"]["b"] + td["v"]["b"], abs=1e-9)


def test_supply_per_day_borrows_the_shared_reader(monkeypatch):
    """**`data/uploaded.jsonl` の4つ目の読み手を書かないこと**（2026-08-25 の申し送り）。

    帳面を読む規則は2つ（**後の行を採る・JST で割る**）で、これを別々に持つたびに
    同じ形の欠陥が出ています（8/19・8/23・8/25 に5件）。
    **`published_per_day()` はここを借りるだけであること。**
    """
    from src import motion_groups as mg

    calls = {"n": 0}
    real = mg.scheduled_at

    def spy(*a, **kw):
        calls["n"] += 1
        return real(*a, **kw)

    monkeypatch.setattr(mg, "scheduled_at", spy)
    out = traj.published_per_day(observed={})
    assert calls["n"] == 1, "共有の読み手を通っていません"
    assert all(len(d) == 10 and d[4] == "-" for d in out), f"日の形が違います: {list(out)[:3]}"


def test_supply_per_day_counts_videos_not_rows(tmp_path):
    """**動かした予約を2回数えないこと**（帳面は足すだけ・実測 505行 / 447本）。

    ここが1行1本だと、`reschedule.py` で前へ寄せた本の**古い予定の日**にも
    1本が立ち、その日の供給が水増しされます。`trend_decompose()` の分母が
    そのままそれを吸います。
    """
    ledger = tmp_path / "uploaded.jsonl"
    ledger.write_text(
        '{"video_id": "A", "at": "2026-09-23T03:00:00Z"}\n'
        '{"video_id": "A", "at": "2026-09-22T00:30:00Z"}\n'   # ← 前へ寄せた
        '{"video_id": "B", "at": "2026-09-22T00:30:00Z"}\n'
        '{"video_id": "C"}\n',                                 # `at` 無しは数えない
        encoding="utf-8")
    out = traj.published_per_day(ledger, observed={})
    assert out == {"2026-09-22": 2}, f"1行1本で数えています: {out}"


def test_supply_per_day_lets_the_ledger_win_over_the_observation(tmp_path):
    """**動かした予約は帳面にしか入っていないので、帳面を優先すること。**

    観測（`views.jsonl` の `at - hours`）は**公開された時刻**なので、
    まだ公開されていない本については何も言いません。一方、帳面は
    `reschedule.py` が動かした後の予定を持っています。
    **同じ本が両方に居たら帳面**（そうしないと、動かす前の日に立ちます）。
    """
    ledger = tmp_path / "uploaded.jsonl"
    ledger.write_text('{"video_id": "A", "at": "2026-09-22T00:30:00Z"}\n', encoding="utf-8")
    out = traj.published_per_day(ledger, observed={"A": "2026-08-04", "B": "2026-08-04"})
    assert out == {"2026-09-22": 1, "2026-08-04": 1}, out


def test_decomposition_window_reaches_back_before_the_ledger(m):
    """**帳面が始まる 08/16 より前も、供給が数えられていること。**

    帳面だけだと重なる窓が 7日 しか取れず、`DECOMPOSE_MIN_DAYS` に届きません ——
    **届かないまま「点が足りない」と言い続けるのは、測れるものを測っていない**
    ということです（`views.jsonl` から 08/04 まで戻れます）。
    """
    td = m["decompose"]
    if not td.get("ok"):
        pytest.skip(td.get("why", "割れません"))
    assert td["first"] < "2026-08-16", (
        f"窓が {td['first']} からです。帳面だけを見ています")
    assert td["n"] >= traj.DECOMPOSE_MIN_DAYS, (
        f"重なる窓が {td['n']}日 しかありません（下限 {traj.DECOMPOSE_MIN_DAYS}日）")


# --- 2. 恒等式 --------------------------------------------------------------

def test_identity_closes(m):
    """**日次再生 ＝ 供給 × V** が帳尻で閉じること（差 5% 未満）。

    **ただし、左辺と右辺が同じチャンネルを見ている回だけ**です
    （2026-08-21 04:3x に足した。理由は `trajectory.coverage()` に全部書いてあります）。

    ここは長らく、記録の側（`data/views.jsonl` の 65本）と
    Analytics の側（チャンネル全体・投稿済み 424件）を突き合わせて
    **-27.6%** を出し、その差を **「後ろカタログが効き始めた」** と読ませていました。
    **そのまま信じると、軌跡に要らない減衰項が入ります。**
    足りないときに言うのは「閉じない」ではなく **「測れない」**です。
    """
    ident = m["identity"]
    assert ident["ok"]
    if not ident["comparable"]:
        pytest.skip(
            f"記録が {ident['n_snapshots']}本 / チャンネル {ident['n_channel']}本"
            f"（{(ident['coverage'] or 0)*100:.0f}%）。**恒等式は測れません** ——"
            "左辺だけが記録の側を見ているので、差は後ろカタログではなく取りこぼしです")
    assert abs(ident["gap"]) < 0.05, (
        f"恒等式が {ident['gap']*100:+.1f}% ずれました。"
        "後ろカタログが効き始めた可能性があります —— 軌跡に減衰項が要ります")


def test_identity_says_when_it_cannot_measure(m):
    """**測れない回に「閉じない」と言わないこと。**

    `comparable` が無い（＝いつでも判定する）形に戻ると、この検査が落ちます。
    """
    ident = m["identity"]
    assert "comparable" in ident and "coverage" in ident
    assert "n_snapshots" in ident and "n_channel" in ident
    if ident["n_channel"]:
        # 判定してよいのは、記録がチャンネルをおおむね覆っている回だけ
        assert ident["comparable"] == (
            ident["n_snapshots"] / ident["n_channel"] >= traj.IDENTITY_MIN_COVERAGE)


def test_coverage_reads_the_ledger_not_the_api(monkeypatch):
    """**API を1単位も使わないこと**（日枠が閉じている窓でも同じ答えが要る）。"""
    from src import history

    monkeypatch.setattr(history, "ledger_topics", lambda: {str(i): str(i) for i in range(100)})
    assert traj.coverage(95)["comparable"] is True
    assert traj.coverage(65)["comparable"] is False
    assert traj.coverage(65)["ratio"] == pytest.approx(0.65)


def test_coverage_without_a_ledger_refuses_to_judge(monkeypatch):
    """台帳が読めない回は **「測れない」**。0本を「覆っている」と読まないこと。"""
    from src import history

    monkeypatch.setattr(history, "ledger_topics", lambda: {})
    cov = traj.coverage(65)
    assert cov["comparable"] is False and cov["ratio"] is None


def test_no_back_catalogue(m):
    """齢2日を超えた本が、中央値で **0回/日** のままであること。"""
    old = [c for c in m["decay"]["curve"] if c["age_days"] >= 2]
    assert old, "齢2日以上の点がありません"
    assert max(c["median"] for c in old) == 0.0, (
        "古い本が回り始めました。**後ろカタログができています** —— "
        "恒等式が成り立たなくなるので、軌跡を組み直すこと")


# --- 3. 札 ------------------------------------------------------------------

def test_rpm_is_never_printed_as_measured(m):
    """**RPM に [実測] の札を付けないこと。** 収益化前は自分の数字がありません。"""
    text = "\n".join(traj.render(m, TODAY))
    assert "[未測定] **このチャンネルの RPM。**" in text
    for line in text.splitlines():
        if "[実測]" in line and "RPM" in line:
            pytest.fail(f"RPM に [実測] の札が付いています: {line}")


def test_review_days_are_labelled_as_proxy(m):
    """審査30日は YouTube の公表値で、**このチャンネルの実測ではありません。**"""
    text = "\n".join(traj.render(m, TODAY))
    assert "[代用] 30日" in text or f"[代用] {traj.MONETIZE_REVIEW_DAYS}日" in text


def test_every_tag_is_one_of_three(m):
    """札は [実測] [代用] [未測定] の3つだけ。**増やさないこと。**"""
    import re
    text = "\n".join(traj.render(m, TODAY))
    tags = set(re.findall(r"\[([^\]]{2,4})\]", text))
    allowed = {"実測", "代用", "未測定", "!", "門1", "門2a", "門2b"}
    assert tags <= allowed, f"知らない札があります: {tags - allowed}"


# --- 4. 段が飛んでいないこと -------------------------------------------------

def test_floor_is_the_sum_of_things_that_cannot_be_prepaid(m):
    """床 ＝ 門2b の90日 ＋ 審査 ＋ 収益の30日。**足し忘れも二重計上も無いこと。**"""
    st = m["stages"]
    assert st["floor_days"] == 90 + traj.MONETIZE_REVIEW_DAYS + traj.REVENUE_WINDOW_DAYS
    assert st["floor_date"] == (TODAY + dt.timedelta(days=st["floor_days"])).isoformat()


def test_gate2b_and_target_are_the_same_level(m):
    """**門2b を通る水準と月20万は、RPM ¥60 でほぼ同じ場所**にあること。

    ここが一致しているのが、`eta.py` が「収益化の門＋30日」を縛りに出す理由です。
    ずれたら、段の組み方をやり直すこと。
    """
    st = m["stages"]
    assert abs(st["be_gate2b"] - 60) < 1, (
        f"門2b の水準の分かれ目 RPM が ¥{st['be_gate2b']:.1f} になりました")


def test_supply_ceiling_is_not_the_api_cap_alone(m):
    """**供給の天井に、題材の生成速度が効いていること。**

    API の日枠 92本/日 だけを天井に置くと、**出す材料が無い日を数えません。**
    """
    st = m["stages"]
    assert st["supply_cap"] <= traj.UPLOAD_CAP_PER_DAY
    if st["material_per_day"] and st["material_per_day"] < traj.UPLOAD_CAP_PER_DAY:
        assert st["supply_cap"] == pytest.approx(st["material_per_day"])
        assert st["supply_cap_why"] == "題材の生成速度"


def test_long_form_ceiling_is_not_borrowed_from_shorts(m):
    """**長尺の合格点を、ショートの V で立てないこと。**

    ショートの V（722回）は**ショートのフィードが配った数**です。長尺が乗る面は
    実測で 1日数十回しかありません。混ぜると「長尺なら届く」が作れてしまいます。
    """
    text = "\n".join(traj.render(m, TODAY))
    assert "『長尺は弱い』ではなく『長尺を見せる面が無い』" in text
    st = m["stages"]
    assert st["non_shorts_day"] is not None
    assert st["long_days_at_now"] > 365, "長尺の面が広がりました。門2a を立て直すこと"


# --- 5. 頭と尻が同じであること -----------------------------------------------

def test_headline_repeats_at_top_and_bottom(m):
    """**最初と最後に同じ3行が出ること。**（真ん中を読まなくても判断できるように）"""
    lines = traj.render(m, TODAY)
    heads = [i for i, ln in enumerate(lines) if ln.startswith("### **月20万の床")]
    assert len(heads) == 2, f"床の行が {len(heads)} 回しか出ていません"
    assert lines[heads[0]] == lines[heads[1]]
