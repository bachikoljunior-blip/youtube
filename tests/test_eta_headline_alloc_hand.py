"""**「この回は何をしても動かない」と言い切る前に、配分を見ているか。**

2026-08-26・最適化の回。

`headline()` は、期日の来た前提が1件も無い回に、こう印字していました::

    **この回に閉じられる前提はありません** —— いちばん早い期日は 2026-08-27。
    **それまでは、どんな作業をしても上の日付は動きません**（`--moves 0` が正しい回です）

**嘘でした。** 同じ出力の**数行 上**に、閉じなくても動くものが印字されています ——
**配分**です（`_planned_lines`）。上の日付は「過去にどう振ってきたか」で解かれ、
これから閉じるのは**台帳に開いている分だけ**なので、2つが食い違っているぶん、
日付はそのまま後ろへずれます。**台帳は書き換えられます。閉じるのを待つ必要がありません。**

実測 2026-08-26（同じ回に実際にやった。API 0単位）::

    過去の配分     2026-12-28
    台帳のまま     2027-01-19（+22日）   ← `rpm` が 33% で台帳いちばん
    `lever: rpm` の開いた5件のうち **2件が RPM を測っていなかった**
      「長尺の生成が落ちる主因は…門で」  `falsified_if` は error_reason の分布
      「長尺は1日4本 作れる」            主張そのものが1日に出る本数
    → `density` へ直して   2027-01-07（+10日）  ＝ **12日**

**その回に閉じられる前提は0件**でした。それでも 12日 動いています。
古い行は、その手を**名指しで打ち消していました。**

これは「サブが怠けていた」話ではありません。実測で、到達日が動きえない回は
**146/211（69%）**・直近20回の `verdict` は **0件**。
**読んだ側は正しく読んで、正しく手を止めています。**

## ここで固定するもの

1. 配分の差が1日 以上ある回は、**「どんな作業をしても動きません」と言わないこと**
2. その回は、**動かせるもの（配分）を名指しすること**
3. 差が1日 未満の回は、**言い切ってよい**（本当に動かせるものが無い）
"""
from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("eta_headline_mod", ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eta)

FROZEN = "どんな作業をしても"


def _pl(days: float = 124.0) -> dict:
    return {"days_to_target": days, "target_date": date(2026, 12, 28),
            "lever_hint": "per_video", "lever_from": "床",
            "binding": "再生数が天井に当たっている", "lever_days": []}


def _tr(gap_days: float | None) -> dict:
    """`gap_days` ぶん、台帳の配分が過去の配分より遅い `tr` を作る。

    `None` なら台帳の線そのものが出ていない回（`planned` が `None`）。
    """
    arms = {"per_video": {"share": 0.6, "focus_rate": 0.1, "rate": 0.06, "cap": 3.0,
                          "throughput": 0.95, "n": 12, "p": 0.17, "source": "自前"},
            "rpm": {"share": 0.05, "focus_rate": 0.1, "rate": 0.005, "cap": 70.0,
                    "throughput": 0.95, "n": 1, "p": 0.17, "source": "全体で代用"}}
    tr: dict = {"arms": arms, "choice": [], "planned": None}
    if gap_days is not None:
        tr["planned"] = {
            "days": 124.0 + gap_days, "date": date(2027, 1, 19),
            "planned": {"share": {"per_video": 0.27, "sub_rate": 0.20,
                                  "rpm": 0.33, "density": 0.20},
                        "n": 15, "total": 16, "unassigned": 0},
        }
    return tr


def _lines(gap_days: float | None, monkeypatch) -> str:
    """`headline()` を、**期日の来た前提が1件も無い回**として撃つ。"""
    monkeypatch.setattr(eta.arm_speed, "next_close",
                        lambda *a, **k: {"on": date(2026, 8, 27), "days": 1,
                                         "open": 16, "source": "ready"})
    monkeypatch.setattr(eta, "_ready_by_claim", lambda *a, **k: {})
    base = {"days": 124.0, "date": date(2026, 12, 28),
            "t_work": 50, "plan_days": 73.0, "blocking": []}
    return "\n".join(eta.headline(_pl(), tr={**_tr(gap_days), "base": base}))


def test_配分が動かせる回に何をしても動かないと言わないこと(monkeypatch):
    """**この検査がいちばん守りたい1行。**"""
    out = _lines(22.0, monkeypatch)
    assert "この回に閉じられる前提はありません" in out
    assert FROZEN not in out, (
        "配分が 22日 ぶん食い違っているのに「どんな作業をしても動きません」と"
        "印字しています。**その回に実際にできる手を、名指しで打ち消しています。**\n" + out)


def test_その回に動かせるものを名指しすること(monkeypatch):
    """打ち消さないだけでは足りない。**どこを触るかまで出すこと。**"""
    out = _lines(22.0, monkeypatch)
    assert "配分は、1件も閉じずに動きます" in out, out
    assert "config/hypotheses.yaml" in out and "lever" in out, out
    assert "+22日" in out, out


def test_本当に動かせない回は言い切ってよいこと(monkeypatch):
    """差が1日 未満なら、`--moves 0` が正しい回です。**そこは曖昧にしない。**"""
    out = _lines(0.0, monkeypatch)
    assert "配分の差も1日 未満" in out, out
    assert "`--moves 0` が正しい回です" in out, out


def test_台帳の線が出ていない回でも落ちないこと(monkeypatch):
    """`planned` が `None`（台帳に腕の付いた前提が無い等）でも印字は続くこと。"""
    out = _lines(None, monkeypatch)
    assert "この回に閉じられる前提はありません" in out, out


def test_台帳の付け札が実際に測っているものと合っていること():
    """**2026-08-26 に 12日 を生んだのは、この照合そのものです。**

    `src/arm_speed.arm()` は `lever` を唯一の振り分け先にしています
    （`mine = [r for r in rows if r["lever"] == lever]`）。付け札が違うと、
    配分も、閉じたときの p/gain も、丸ごと別の腕に入ります。

    **ここでは中身までは判定できません**（claim は自由文です）。
    固定するのは「**RPM に振るなら、RPM への鎖が `note` に書いてあること**」だけ。
    鎖の書けない前提は、RPM ではなく実際に測っている腕へ置くこと。
    """
    import yaml
    doc = yaml.safe_load((ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
    naked = []
    for h in doc["hypotheses"]:
        if h.get("closed_on") or h.get("lever") != "rpm":
            continue
        blob = " ".join(str(h.get(k, "")) for k in ("note", "falsified_if", "claim"))
        if "RPM" not in blob and "ニッチ" not in blob and "1再生あたり" not in blob:
            naked.append(h.get("claim"))
    assert not naked, (
        "`lever: rpm` なのに、RPM への鎖が1文字も書いていない開いた前提があります。\n"
        "**`rpm` は台帳でいちばん大きい腕になりがちで、そこに乗せた分だけ到達日が"
        "後ろへ動きます**（2026-08-26 の実測: 2件で 12日）。\n"
        "実際に測っている腕へ置き直すか、鎖を `note` に書くこと:\n  - "
        + "\n  - ".join(naked))


# --- **閉じた仕事を、道具が毎回 名指ししないこと**（2026-08-27 に足した） ---
#
# すぐ上の `test_台帳の付け札が…` が守っているのは**台帳の中身**です。
# ここで守るのは**印字のほう** —— 同じ照合を「先にやれ」と毎回 言い続けないこと。
#
# 実測 2026-08-27 07:5x のサブ: 頭の3行から
# 「**付け札が実際に測っているものと合っているかを、先に見ること** ——
#   2026-08-26 は、それだけで 12日 動きました」を読み、開いた19件を並べ直し、
# **`docs/JOURNAL.md` に「開いた21件を1件ずつ当たって付け替え0件」と
# 2回 書いてあるのを見つけて捨てました**（約8分）。
# `retro.py` の持ち越しに `eta.py` が3回 並んでいるのと同じ形です。
#
# **空欄（`unassigned`）は機械で数えられます。そこだけ名指しすること。**


def _lines_unassigned(n: int, monkeypatch) -> str:
    """`unassigned` を差し替えて、配分の差のある回を撃つ。"""
    tr = _tr(22.0)
    tr["planned"]["planned"]["unassigned"] = n
    base = {"days": 124.0, "date": date(2026, 12, 28),
            "t_work": 50, "plan_days": 73.0, "blocking": []}
    monkeypatch.setattr(eta.arm_speed, "next_close",
                        lambda *a, **k: {"on": date(2026, 8, 27), "days": 1,
                                         "open": 16, "source": "ready"})
    monkeypatch.setattr(eta, "_ready_by_claim", lambda *a, **k: {})
    return "\n".join(eta.headline(_pl(), tr={**tr, "base": base}))


def test_空欄が0なら付け札の照合を次の一手として名指ししないこと(monkeypatch):
    out = _lines_unassigned(0, monkeypatch)
    assert "一巡ずみ" in out, out
    assert "先に見ること" not in out, (
        "空欄が0件なのに、済んだ照合を『先にやれ』と名指ししています。"
        "**頭の3行しか読まない手順では、これが次の一手に見えます。**\n" + out)


def test_空欄があるならそこだけは名指しすること(monkeypatch):
    """空欄は θ にも配分にも入らないので、**これは本物の穴**です。"""
    out = _lines_unassigned(3, monkeypatch)
    assert "空欄が 3件" in out, out
    assert "一巡ずみ" not in out, out
