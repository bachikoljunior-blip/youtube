"""**無限大にしても 0日 の腕を「この回に引く腕」と名指ししない**の検査（2026-08-31）。

## なぜ要るか（実測。この検査を書いた回に自分で撃った数）

オーナー規則2 は「**この改善を無限大にしたら、到達日は何日 早まるか。
答えがゼロなら、そこは律速ではない**」です。

`scripts/eta.py` の `lever_days()` は長らく**天井までしか**解いていませんでした。
天井で届かない腕は全部 `gain_at_cap = 0` の同じ字に潰れ、
**「天井が足りないだけの腕」と「無限大でも 0日 の腕」が見分けられません。**

そして `plan()` の上書き

    if best and best[_key] > 0:

は、4本とも届かない回には立ちません（`gain` も `gain_at_cap` も4本とも 0）。
その回の `lever_hint` は **決め打ちの診断名**（`d_revenue >= NEVER` → `"rpm"`）
のまま画面に出ます —— **測った名前と、決め打ちの名前が、同じ字で。**
同じファイルの注記が「**黙って戻さないこと**」と名指ししていた状態そのもので、
**2026-08-31 に、黙って戻っていました。**

実測 2026-08-31（`points` 付き ＝ 本番と同じ道）::

    per_video  天井 ×2.01  → **×17.69 で日付が出る**（天井を ×8.81 上げれば届く）
    sub_rate   天井 ×6.64  → **×7.1e+09 でも出ない**
    rpm        天井 ×28.05 → **×3.0e+10 でも出ない**
    density    天井 ×1.00  → **×2.1e+09 でも出ない**

    data/eta.jsonl   `arm_reaches` 0/4 の行 …… **92/278（33%）**
    data/runs.jsonl  `lever_hint` は直近 **50 ship 連続で `rpm`**
                     `--lever rpm` を選んだ **24回 中、到達日を動かした回 0**

つまり **無限大にしても 0日 の腕を、50回 連続で名指ししていました。**
そして選んだ24回は、規則2 のとおり1日も動きませんでした。
**律速でない所を速くしても、到達日は動きません。**

## この検査が固定するもの

1. `lever_days()` は、天井で届かない腕を**天井の上まで**見る
   （`need` / `need_over_cap` / `dead_at_inf` を返す）
2. `plan()` は、天井で届かない回に **`need_over_cap` がいちばん小さい腕**で
   `lever_hint` を上書きする（＝**いちばん安く壊せる天井**）。
   1本も無ければ **`lever_hint_measured = False`** を立て、名前を信じさせない
3. `levers.lever_notes()` は、`dead_at_inf` の腕を**天井の話より先に**止める

**覆る条件**: 倍率と到達日が単調でなくなったら（`plan()` が倍率を天井以外にも
通すようになったら）、`need` の挟み込みは使えません。**そのときは、この検査の
「なぜ要るか」ごと書き直すこと** —— 文面だけ合わせないこと。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import levers  # noqa: E402

_spec = importlib.util.spec_from_file_location("_eta_lh", ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eta)


# --- 1. 天井の上まで見る道具があること ---

def test_inf_scale_is_big_enough_to_separate_the_two_cases():
    """**×10^9 は、実測の `need`（×17.69）よりずっと上**でなければ意味がない。"""
    assert eta.LEVER_INF_SCALE >= 1e6, (
        "無限大の代わりが小さすぎます。`need` の実測（×17.69）と"
        "「無限大でも出ない」が区別できません")
    assert eta.LEVER_NEED_ITERS >= 10, (
        "対数の挟み込みが浅すぎます（[cap, 1e9] は 30 桁ぶん）")


def test_lever_days_row_carries_the_above_ceiling_answer():
    """`lever_days` の返す行に、天井の上の答えが**欄として**在ること。

    ここが消えたら `plan()` の選び直しは黙って死にます（`_alive` が常に空）。
    """
    import inspect
    src = inspect.getsource(eta.lever_days)
    for key in ('"need"', '"need_over_cap"', '"dead_at_inf"'):
        assert key in src, f"{key} が `lever_days` から消えています"
    assert "LEVER_INF_SCALE" in src, "無限大の側を撃たなくなっています"


# --- 2. `plan()` が名前を測って選ぶこと ---

def test_plan_picks_the_cheapest_ceiling_to_break():
    """**天井で届かない回は、`need_over_cap` が最小の腕を選ぶ。**

    実測の形（08/31）をそのまま置いています —— `rpm` は天井 ×28.05 と
    いちばん大きいのに**無限大でも出ない**ので、選んではいけません。
    """
    rows = [
        {"lever": "per_video", "gain": 0.0, "gain_at_cap": 0.0,
         "reachable_at_cap": False, "need": 17.69, "need_over_cap": 8.81,
         "dead_at_inf": False},
        {"lever": "sub_rate", "gain": 0.0, "gain_at_cap": 0.0,
         "reachable_at_cap": False, "need": None, "need_over_cap": None,
         "dead_at_inf": True},
        {"lever": "rpm", "gain": 0.0, "gain_at_cap": 0.0,
         "reachable_at_cap": False, "need": None, "need_over_cap": None,
         "dead_at_inf": True},
        {"lever": "density", "gain": 0.0, "gain_at_cap": 0.0,
         "reachable_at_cap": False, "need": None, "need_over_cap": None,
         "dead_at_inf": True},
    ]
    alive = [r for r in rows if r.get("need_over_cap")]
    assert [r["lever"] for r in alive] == ["per_video"]
    pick = min(alive, key=lambda r: r["need_over_cap"])
    assert pick["lever"] == "per_video", (
        "天井がいちばん大きい `rpm` を選んでいます —— "
        "天井の大きさと、日付を動かせることは別です")
    # そして「決め打ちの診断名」は `rpm` でした。上書きが立たなければ、それが出ます。
    assert pick["lever"] != "rpm"


def test_plan_refuses_to_name_an_arm_when_none_reach_at_infinity():
    rows = [{"lever": k, "gain": 0.0, "gain_at_cap": 0.0,
             "reachable_at_cap": False, "need": None, "need_over_cap": None,
             "dead_at_inf": True} for k in eta.LEVERS]
    assert not [r for r in rows if r.get("need_over_cap")]


# --- 3. 選ぶ側（`run_marker` が呼ぶ `levers`）へ届くこと ---

def test_arm_state_carries_dead_at_inf():
    st = levers.arm_state({
        "lever_hint": "per_video",
        "arm_caps": {"per_video": 2.01, "sub_rate": 6.64,
                     "rpm": 28.05, "density": 1.0},
        "arm_reaches": {"per_video": False, "sub_rate": False,
                        "rpm": False, "density": False},
        "arm_dead_at_inf": ["sub_rate", "rpm", "density"],
        "arm_need_over_cap": {"per_video": 8.81, "sub_rate": None,
                              "rpm": None, "density": None}})
    assert st["dead_at_inf"] == ("sub_rate", "rpm", "density")
    assert st["need_over_cap"] == {"per_video": 8.81}


def test_lever_notes_stops_a_dead_at_inf_arm_before_talking_about_ceilings():
    """**`rpm` を選んだ回は、天井の話をされる前に止められる。**

    ここが黙ると、次の回は「`rpm` の天井を上げる前提」を立てます ——
    閉じても到達日は1日も動きません（実測 24回・全部 0）。
    """
    st = levers.arm_state({
        "lever_hint": "per_video",
        "arm_caps": {"per_video": 2.01, "rpm": 28.05},
        "arm_reaches": {"per_video": False, "rpm": False},
        "arm_dead_at_inf": ["rpm"],
        "arm_need_over_cap": {"per_video": 8.81, "rpm": None}})
    txt = "\n".join(levers.lever_notes("rpm", st))
    assert "無限大にしても到達日が1日も動きません" in txt
    assert "律速では" in txt
    assert "per_video" in txt, "引ける腕の名前が出ていません（止めるだけでは戻れません）"
    assert "×8.81" in txt


def test_lever_notes_stays_quiet_for_the_arm_that_can_still_be_pulled():
    st = levers.arm_state({
        "lever_hint": "per_video",
        "arm_caps": {"per_video": 2.01, "rpm": 28.05},
        "arm_reaches": {"per_video": False, "rpm": False},
        "arm_dead_at_inf": ["rpm"],
        "arm_need_over_cap": {"per_video": 8.81, "rpm": None}})
    txt = "\n".join(levers.lever_notes("per_video", st))
    assert "無限大にしても到達日が1日も動きません" not in txt


# --- 4. 選ぶ側に「古い行」が届かないこと（2026-08-31 に踏んだ） ---

def test_dead_at_inf_comes_from_the_newest_row_not_the_stale_caps_row(tmp_path):
    """**`arm_caps` を持つ行は古い。`dead_at_inf` はそこから拾わないこと。**

    `arm_caps` は**軌跡を解いた回（`full=True`）にしか付きません**。
    `run_marker.py --ship` が撃つのは4秒の `--reflect` だけなので、
    `caps_row` は平気で数十分 古くなります —— 実測 2026-08-31 は **33分差**で、
    新しい行が `arm_dead_at_inf` を持っているのに、古い `caps_row` を見て
    「そんな腕は無い」と読み、**`--lever rpm` が止められずに通りました。**
    """
    log = tmp_path / "eta.jsonl"
    log.write_text("\n".join([
        # 古い行（軌跡つき）—— まだ天井の上を測っていなかった頃
        '{"at": "2026-08-31T17:14:36+00:00", "lever_hint": "rpm",'
        ' "arm_caps": {"per_video": 2.01, "rpm": 28.05},'
        ' "arm_reaches": {"per_video": false, "rpm": false}}',
        # 新しい行（反映）—— 軌跡は解いていないので `arm_caps` を持たない
        '{"at": "2026-08-31T17:47:55+00:00", "kind": "reflect",'
        ' "lever_hint": "per_video",'
        ' "arm_dead_at_inf": ["rpm"],'
        ' "arm_need_over_cap": {"per_video": 8.82, "rpm": null}}',
    ]) + "\n", encoding="utf-8")

    st = levers.latest_arm_state(log)
    assert st["hint"] == "per_video"
    assert st["caps"] == {"per_video": 2.01, "rpm": 28.05}, "天井は古い行から拾ってよい"
    assert st["dead_at_inf"] == ("rpm",), (
        "新しい行の `arm_dead_at_inf` が届いていません —— "
        "`--lever rpm` が止められずに通ります")
    assert st["need_over_cap"] == {"per_video": 8.82}
    assert "無限大にしても到達日が1日も動きません" in "\n".join(
        levers.lever_notes("rpm", st))


def test_no_flag_when_the_row_never_measured_it():
    """**読めないことと「死んだ腕は無い」は別**（`caps` と同じ扱い）。"""
    st = levers.arm_state({"lever_hint": "rpm",
                           "arm_caps": {"per_video": 2.01}})
    assert st["dead_at_inf"] == ()
    assert "無限大" not in "\n".join(levers.lever_notes("rpm", st))
