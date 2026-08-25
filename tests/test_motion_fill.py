"""**作った本を、足りている腕ではなく足りない腕へ入れる。**

## なぜ要るか（2026-08-26・最適化の回に実測して作った）

`config/hypotheses.yaml` の「冒頭0.9秒の動き」の対照群は、
**`YT_OPENING_MOTION=0` で作らないかぎり永久に増えません**
（`src/renderer.opening_motion_on` / `scripts/deadline_check.py` の `zero_means_never`）。

機械は、足りない側を**既に2か所で印字していました**:

    src/motion_groups.py   「足りない側を `YT_OPENING_MOTION` を明示して作り足すこと」
    scripts/queue_lag.py   「opening_motion **判定できる日が出ません** ← 本が足りない」

**その2つを読む口が、作る側にありませんでした。** 実測 2026-08-26:

    処置(動きあり)  **20本** ／ 床 8   ← 250%。ここへ足しても判定は1日も早まらない
    対照(動きなし)  ** 3本** ／ 床 8   ← あと5本。**ここだけが期限を動かす**

`batch_build` は既定（動きあり）で作り続けるので、**作った本は全部 飽和側**へ入り、
`eta.py` が言う唯一の動かし方（**前提を1件閉じる**）に1本も寄与しませんでした。
そして `scripts/queue_lag.py` は「予約の順番待ちが律速で、**作る本数を増やすと悪化する**」
と言っています —— つまり**本数ではなく行き先**を直す以外に道がありません。

## いちばん危ないのは、混ざった回の台帳です

`src/motion_groups.motion_by_topic()` は、**回の旗をその回の全テーマに貼ります。**
1本ごとの旗と食い違うと `len(flags) == 1` に落ちないので、
**そのテーマは両群から捨てられます。** 腕を混ぜたまま回の旗を1個 書くと、
**その回の本が全部 標本から消えます。** ここを最後の3件で縛ります。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import batch_build                                   # noqa: E402
from src import motion_groups                        # noqa: E402


# --- 何本を、どちらの腕で作るか -------------------------------------------

def test_足りていれば既定のまま(monkeypatch):
    """**満ちた腕を、いつまでも埋め続けないこと。**"""
    monkeypatch.delenv("YT_OPENING_MOTION", raising=False)
    monkeypatch.setattr(batch_build, "motion_shortfall", lambda: (0, ""))
    assert batch_build.motion_plan(6) == [True] * 6


def test_足りない側へ寄せる(monkeypatch):
    monkeypatch.delenv("YT_OPENING_MOTION", raising=False)
    monkeypatch.setattr(batch_build, "motion_shortfall", lambda: (5, ""))
    plan = batch_build.motion_plan(8)
    assert plan.count(False) == 4          # 半分まで
    assert plan.count(True) == 4


def test_半分を超えて対照にしない(monkeypatch):
    """**共有日が要ります。** 1回ぶんを全部 対照にすると、その日が片群だけの日に
    なりかねません（`src/motion_groups.paired` は共有日しか標本に数えません）。"""
    monkeypatch.delenv("YT_OPENING_MOTION", raising=False)
    monkeypatch.setattr(batch_build, "motion_shortfall", lambda: (99, ""))
    plan = batch_build.motion_plan(10)
    assert plan.count(False) <= 5
    assert plan.count(True) >= 5


def test_先頭に固めない(monkeypatch):
    """落ちた本は先頭から撃ち直されます。固めると撃ち直しが片群だけになります。"""
    monkeypatch.delenv("YT_OPENING_MOTION", raising=False)
    monkeypatch.setattr(batch_build, "motion_shortfall", lambda: (3, ""))
    plan = batch_build.motion_plan(8)
    assert plan[:3] != [False, False, False]


def test_明示された指示を上書きしない(monkeypatch):
    """**人（や別の回）が `YT_OPENING_MOTION` を明示した回は、こちらが決めない。**"""
    monkeypatch.setenv("YT_OPENING_MOTION", "0")
    monkeypatch.setattr(batch_build, "motion_shortfall", lambda: (5, ""))
    assert batch_build.motion_plan(4) == [None] * 4


def _stock(monkeypatch, live: int, pending_off: int, room):
    from src import judgeable
    monkeypatch.delenv("YT_OPENING_MOTION", raising=False)
    monkeypatch.setattr(judgeable, "members",
                        lambda k: {"対照(動きなし)": [("d", "v")] * live})
    flags = {f"t{i}": False for i in range(pending_off)}
    flags["t-on"] = True
    monkeypatch.setattr(motion_groups, "motion_by_topic", lambda *a, **k: flags)
    monkeypatch.setattr(motion_groups, "topic_by_video", lambda *a, **k: {})
    monkeypatch.setattr(batch_build, "_live_room", lambda: room)


def test_作り置きも数える(monkeypatch):
    """**まだ投稿していない対照を数えないと、判定に入るまでの数日で作り過ぎます。**"""
    _stock(monkeypatch, live=2, pending_off=2, room=99)
    need, why = batch_build.motion_shortfall()
    # 床 8 ／ 判定に入る 2 ／ 作り置き 2 → あと 4
    assert need == 4, why


def test_置き先が無ければ作らない(monkeypatch):
    """**これを入れないと、automation が「生成を捨てる回」を自動化します。**

    `docs/trigger_main.md` に、この手を**撃って外した回**が残っています ——
    申し送りは3回続けて「対照を2本 作り足すこと」と書き、実物の
    `live_slots.py --plan` は「期限までに空いた生きた枠は 0本。作った本は
    その日の 11本目 ＝ 死に枠」でした。**2本ぶんの生成を 0再生の枠に捨てる**手です。
    """
    _stock(monkeypatch, live=2, pending_off=0, room=0)
    need, why = batch_build.motion_shortfall()
    assert need == 0, why
    assert "足りないのは本ではなく、置き先です" in why


def test_置き先のぶんだけ作る(monkeypatch):
    """床まで 6本 要っても、置ける枠が 2本 なら 2本だけ作ること。"""
    _stock(monkeypatch, live=2, pending_off=0, room=2)
    need, _why = batch_build.motion_shortfall()
    assert need == 2


def test_置き先を数えられなければ絞らない(monkeypatch):
    """**観測できないことを「無い」にしないこと。**読めない回は今までどおり。"""
    _stock(monkeypatch, live=2, pending_off=0, room=None)
    need, why = batch_build.motion_shortfall()
    assert need == 6, why


# --- 作った値が、そのまま子プロセスと台帳へ行くか -------------------------

def test_腕は子プロセスの環境で渡す(monkeypatch):
    """**`os.environ` を書き換えないこと。** 生成はスレッドで並列に走るので、
    書き換えると**同時に走っている別の本の腕まで変わります。**"""
    seen: list = []

    def fake_run(cmd, timeout, label="", env=None):
        seen.append((cmd, env))
        return 0, "ok"

    monkeypatch.setattr(batch_build, "run", fake_run)
    monkeypatch.setattr(batch_build, "_flag_line", lambda tid, motion=None: None)
    row = batch_build.build_one({"id": "s-z", "calc": "nenkin"}, True, motion=False)
    # **生成そのものの1回目**（このあと contact sheet でもう1回 呼ばれます）
    built = [env for cmd, env in seen if "src.pipeline" in cmd]
    assert built == [{"YT_OPENING_MOTION": "0"}]
    # **行のラベルは、親の既定ではなく、その本を作った値**
    assert row["opening_motion"] is False


def test_ラベルは親の既定を読み直さない(monkeypatch):
    """親は既定（動きあり）のままでも、対照として作った本は対照と書くこと。"""
    monkeypatch.delenv("YT_OPENING_MOTION", raising=False)
    monkeypatch.setattr(batch_build, "run", lambda *a, **k: (0, "ok"))
    labelled: list = []
    monkeypatch.setattr(batch_build, "_flag_line",
                        lambda tid, motion=None: labelled.append(motion))
    batch_build.build_one({"id": "s-w", "calc": "nenkin"}, True, motion=False)
    assert labelled == [False]


# --- 混ざった回の台帳（**ここが壊れると回ぶん全部 消えます**）-------------

def test_1本ごとの旗が回の旗より強い(tmp_path):
    runs = tmp_path / "batch_runs.jsonl"
    runs.write_text(json.dumps({
        "opening_motion": True,                       # 回の旗（古い形）
        "results": [{"topic": "t-off", "opening_motion": False},
                    {"topic": "t-on", "opening_motion": True}],
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    got = motion_groups.motion_by_topic(runs=runs, flags=tmp_path / "none.jsonl")
    assert got == {"t-off": False, "t-on": True}


def test_混ざった回は回の旗を書かない(tmp_path):
    """**回の旗を1個 書くと、その回の本が全部 標本から消えます。**
    （`motion_by_topic` は食い違ったテーマを両群から落とすので）"""
    runs = tmp_path / "batch_runs.jsonl"
    runs.write_text(json.dumps({
        # 混ざった回は `opening_motion` の欄そのものが無い
        "results": [{"topic": "t-off", "opening_motion": False},
                    {"topic": "t-on", "opening_motion": True}],
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    got = motion_groups.motion_by_topic(runs=runs, flags=tmp_path / "none.jsonl")
    assert got == {"t-off": False, "t-on": True}


def test_旗の無い古い行は今までどおり(tmp_path):
    """**既存の 400本ぶんを読めなくしないこと。**"""
    runs = tmp_path / "batch_runs.jsonl"
    runs.write_text(json.dumps({
        "opening_motion": True,
        "results": [{"topic": "t-old"}],              # 1本ごとの旗が無い古い形
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    got = motion_groups.motion_by_topic(runs=runs, flags=tmp_path / "none.jsonl")
    assert got == {"t-old": True}
