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


def test_growth_is_not_significant_and_that_is_said_out_loud(m):
    """**有意でないなら「有意ではありません」と印字すること。**

    もし将来これが有意になったら、この検査は落ちます。**そのときは
    落ちたこと自体が「複利の項を軌跡に入れてよくなった」という報せ**なので、
    検査を直すのではなく、軌跡のほうを設計し直してください。
    """
    tr = m["trend"]
    text = "\n".join(traj.render(m, TODAY))
    if tr["significant"]:
        pytest.fail("日次再生の傾きが有意になりました。軌跡の設計を見直すこと")
    assert "有意ではありません" in text


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
