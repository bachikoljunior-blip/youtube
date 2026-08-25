"""`scripts/drift.py` の検査。

**この道具が守るのは1つだけ**: 「期限の来た前提があるのに、直近で1件も
判定していない」回を、黙って通さないこと（2026-08-24。オーナー指摘
「なんで実験そんな少ないの？」に対する配線の修理）。

**`fix` を禁じる検査は書きません。** 壊れた計器で実験しても答えは出ないので、
直すこと自体は正しい。**止めるのは「期限の来た問いを置き去りにしたまま」の場合だけ。**
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import drift  # noqa: E402


def _seed(tmp_path, monkeypatch, ships, hyps_yaml):
    runs = tmp_path / "runs.jsonl"
    runs.write_text("\n".join(json.dumps(s, ensure_ascii=False) for s in ships) + "\n",
                    encoding="utf-8")
    hyps = tmp_path / "hypotheses.yaml"
    hyps.write_text(hyps_yaml, encoding="utf-8")
    monkeypatch.setattr(drift, "RUNS", runs)
    monkeypatch.setattr(drift, "HYPS", hyps)


def _ship(at, what, **kw):
    return {"at": at, "kind": "ship", "what": what, **kw}


OPEN_OVERDUE = "- claim: 冒頭が engaged を決める\n  deadline: '2026-08-20'\n"
OPEN_FUTURE = "- claim: まだ先\n  deadline: '2026-12-01'\n"
CLOSED = ("- claim: 済んだやつ\n  deadline: '2026-08-20'\n"
          "  verdict: false\n")


def test_期限切れの前提があって判定ゼロなら外れと言う(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch,
          [_ship("2026-08-23T10:00", "fix: 道具を直した")] * 3, OPEN_OVERDUE)
    text, drifting = drift.report("2026-08-24")
    assert drifting is True
    assert "外れています" in text


def test_判定が直近にあれば外れと言わない(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch,
          [_ship("2026-08-23T10:00", "fix: 直した"),
           _ship("2026-08-23T11:00", "verdict: 前提を1件閉じた")], OPEN_OVERDUE)
    _, drifting = drift.report("2026-08-24")
    assert drifting is False


def test_期限切れが無ければ判定ゼロでも外れと言わない(tmp_path, monkeypatch):
    """**fix ばかりでも、締切が来ていなければ止めません。**

    実験は16本作って2週間待つので、**待っている間に fix をやるのは正しい。**
    止めるのは「期限が来ているのに置き去り」の1点だけ。
    """
    _seed(tmp_path, monkeypatch,
          [_ship("2026-08-23T10:00", "fix: 直した")] * 9, OPEN_FUTURE)
    _, drifting = drift.report("2026-08-24")
    assert drifting is False


def test_閉じた前提は期限切れに数えない(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch,
          [_ship("2026-08-23T10:00", "fix: 直した")], CLOSED)
    _, drifting = drift.report("2026-08-24")
    assert drifting is False


def test_種別は先頭の語で読む(tmp_path, monkeypatch):
    """既存240件は `--ship "fix: ..."` の書き方しか持っていません。

    **欄を足すのが本筋ですが、足すと過去が読めなくなる**ので、
    いまある書き方から読みます。**この検査は、その約束のほうを守ります。**
    """
    assert drift._kind_of("fix: あれを直した") == "fix"
    assert drift._kind_of("verdict: 判定した") == "verdict"
    assert drift._kind_of("upload: 1本予約") == "upload"
    assert drift._kind_of("means: M8 を動かした") == "means"
    assert drift._kind_of("親を交代した") == "その他"


def test_窓の外の回は数えない(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch,
          [_ship("2026-07-01T10:00", "fix: 大昔"),
           _ship("2026-08-23T10:00", "fix: 最近")], OPEN_FUTURE)
    text, _ = drift.report("2026-08-24", window_days=7)
    assert "ship 1件" in text


def test_gateは外れているときだけ2を返す(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch,
          [_ship("2026-08-23T10:00", "fix: 直した")], OPEN_OVERDUE)
    assert drift.main(["--gate", "--today", "2026-08-24"]) == 2
    assert drift.main(["--today", "2026-08-24"]) == 0


def test_ship以外の印は数えない(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch,
          [{"at": "2026-08-23T10:00", "kind": "write", "what": "周を始めた"},
           _ship("2026-08-23T11:00", "fix: 直した")], OPEN_FUTURE)
    text, _ = drift.report("2026-08-24")
    assert "ship 1件" in text


# --- ここから 2026-08-24（最適化の回）に足した「在庫」の検査 ---
#
# **見つけたズレ**: `eta.py` は毎回「軌跡の腕が動くのは前提を1件閉じたときだけ」と
# 印字しています。つまり**到達日が動きうる回数の上限は、その期間に閉じられる
# 前提の数**です。ところが `report()` は「到達日を動かすと宣言した回 17/341」しか
# 出しておらず、**上限をどこでも計算していませんでした。**
# 実測: 直近7日 周141 ／ 閉じた前提7件 → **20周に1回**。宣言17は上限7の2.4倍。
#
# **止めるのは在庫0のときだけ。** 薄いだけでは止めません（待ち時間が実験の本体）。


def _seed_supply(tmp_path, monkeypatch, runs_rows, hyps_yaml):
    runs = tmp_path / "runs.jsonl"
    runs.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in runs_rows) + "\n",
                    encoding="utf-8")
    hyps = tmp_path / "hypotheses.yaml"
    hyps.write_text(hyps_yaml, encoding="utf-8")
    monkeypatch.setattr(drift, "RUNS", runs)
    monkeypatch.setattr(drift, "HYPS", hyps)


def _round(at, sess):
    return {"at": at, "kind": "write", "session": sess, "what": "周を始めた"}


NEAR = "- claim: 4日後に閉じられる\n  deadline: '2026-08-28'\n"
FAR = "- claim: ずっと先\n  deadline: '2026-12-01'\n"


def test_期日が全部先なら在庫0で止める(tmp_path, monkeypatch):
    """**期限が来るまで待つ門は、期日が全部先だと一度も効きません。**

    その1週間（≒140周）は、どの回が何をしても到達日が動かないことが**確定**します。
    """
    _seed_supply(tmp_path, monkeypatch,
                 [_round("2026-08-23T10:00", "s1")], FAR)
    text, dry = drift.supply_report("2026-08-24")
    assert dry is True
    assert "在庫が尽きています" in text
    assert drift.main(["--gate", "--today", "2026-08-24"]) == 2


def test_期日が近い前提が1件でもあれば止めない(tmp_path, monkeypatch):
    _seed_supply(tmp_path, monkeypatch,
                 [_round("2026-08-23T10:00", "s1")], NEAR + FAR)
    text, dry = drift.supply_report("2026-08-24")
    assert dry is False
    assert "薄いだけでは止めません" in text
    assert drift.main(["--gate", "--today", "2026-08-24"]) == 0


def test_期限切れの前提は在庫に数える(tmp_path, monkeypatch):
    """**期日が過ぎた開いた前提は「いますぐ閉じられる」ので在庫です。**

    そこは (1.7) のもう片方の条件（期限切れ＋判定ゼロ）が見ます。
    在庫0のほうで二重に止めないこと。
    """
    _seed_supply(tmp_path, monkeypatch,
                 [_round("2026-08-23T10:00", "s1")], OPEN_OVERDUE)
    _, dry = drift.supply_report("2026-08-24")
    assert dry is False


def test_閉じた前提は在庫に数えない(tmp_path, monkeypatch):
    _seed_supply(tmp_path, monkeypatch,
                 [_round("2026-08-23T10:00", "s1")],
                 "- claim: 済んだ\n  deadline: '2026-08-26'\n  verdict: false\n")
    _, dry = drift.supply_report("2026-08-24")
    assert dry is True


def test_周速はセッションの数で数える(tmp_path, monkeypatch):
    """周＝印を打ったセッション。**同じ回の複数の印を2周と数えないこと。**

    今日（半端な日）は数えません。
    """
    rows = [_round("2026-08-23T10:00", "s1"), _round("2026-08-23T11:00", "s1"),
            _round("2026-08-23T12:00", "s2"), _round("2026-08-24T09:00", "s3")]
    _seed_supply(tmp_path, monkeypatch, rows, NEAR)
    assert drift.rounds_per_day("2026-08-24", days=7) == pytest.approx(2 / 7)


def test_閉じた件数はclosed_onの窓で数える(tmp_path, monkeypatch):
    y = ("- claim: a\n  deadline: '2026-08-20'\n  closed_on: '2026-08-20'\n  verdict: true\n"
         "- claim: b\n  deadline: '2026-07-01'\n  closed_on: '2026-07-01'\n  verdict: true\n")
    _seed_supply(tmp_path, monkeypatch, [_round("2026-08-23T10:00", "s1")], y)
    assert drift.closed_per_day("2026-08-24", days=7) == 1


def test_到達日が何周に1回動きうるかを印字する(tmp_path, monkeypatch):
    """**上限を印字しない限り、宣言が上限を超えていても誰も気づきません。**"""
    rows = [_round(f"2026-08-2{d}T0{h}:00", f"s{d}{h}")
            for d in range(1, 4) for h in range(1, 8)]
    _seed_supply(tmp_path, monkeypatch, rows, NEAR)
    text, _ = drift.supply_report("2026-08-24")
    assert "周に1回" in text
    assert "前提を1件閉じたときだけ" in text


def test_基準日はJSTで数える(monkeypatch):
    """**門が期限を見落とす時間帯を作らないこと**（2026-08-26 に踏んだ）。

    `deadline` も予約も JST なのに、ここは `datetime.now().date()`（＝ UTC）で
    数えていました。**JST の 00:00〜09:00 は「昨日」**になるので、
    その日に期限が来た前提が「来ていない」ことにされます。
    実測: 02:0x JST に「期限の来た前提: なし」と印字し、実際は1件 来ていました。
    """
    import datetime as dt

    class _Now(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            # UTC で 2026-08-25 17:00 ＝ JST で 2026-08-26 02:00
            base = dt.datetime(2026, 8, 25, 17, 0, tzinfo=dt.timezone.utc)
            return base.astimezone(tz) if tz else base.replace(tzinfo=None)

    monkeypatch.setattr(drift, "datetime", _Now)
    assert drift.today_jst() == "2026-08-26", "**UTC の日付で門を開け閉めしないこと**"


def test_noneは動きえない回として数える(tmp_path, monkeypatch):
    """**`none` を分母にだけ入れないこと**（2026-08-26・最適化の回）。

    `src/levers.LEVERS` の `none` は「この回は予測日を動かさない」そのもので、
    `MOVING` はここだけを外して作られています。ところが `dead_arm_report()` は
    `none` を**分母にだけ**入れていました ——「動かないと宣言した回」を
    「生きた腕を引いた回」と同じ側で数えていた、ということです。

    **外れる向きが悪いほうでした。** 実測 2026-08-26 の実物で
    **43/175（25%）** と出ていたものが、`none` 71回 を入れると **114/175（65%）**。
    25% は「まあ許容」に読め、65% は読めません。**判断がひっくり返ります。**
    """
    _seed(tmp_path, monkeypatch, [
        _ship("2026-08-25T10:00:00+09:00", "fix: 道具", lever="none"),
        _ship("2026-08-25T11:00:00+09:00", "fix: 手順", lever="none"),
        _ship("2026-08-25T12:00:00+09:00", "means: 実験", lever="per_video"),
    ], OPEN_FUTURE)
    monkeypatch.setattr(drift.levers, "latest_arm_state", lambda _p: {
        "caps": {"per_video": 3.0, "density": 1.0},
        "dead_why": {}, "reaches": {"per_video": True}, "hint": "per_video",
    })
    out = drift.dead_arm_report("2026-08-26")
    assert "`none`（動かさないと宣言した回）: 2/3" in out
    assert "到達日が動きえない回: 2/3" in out
    # **`fix` そのものを叱る文にしないこと**（この道具の冒頭を読むこと）
    assert "動きうるのは残りの **1回**" in out
