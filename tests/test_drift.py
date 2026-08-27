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


# --- 2026-08-26（最適化の回）に足した「期限が来た ≠ 判定できる」の検査 ---
#
# **見つけたズレ**: この日、2つの道具が同じ前提について正反対を言っていました。
#
#     scripts/deadline_check.py  「[..] まだ数えはじめたところです。
#                                  **この回は何もしないのが正解**です」
#     scripts/drift.py --gate    exit 2 →「**この回は verdict を出すこと**」
#
# 対象は「深い題のショート」1件で、台帳自身の `falsified_if` が
# **「どちらも 8本 に満たなければ判定できません。期限を延ばすこと。
# 『まだ分からない』で閉じないこと」**と書いています（実測 要8／いま7、
# 使える日 要3／いま0）。**門が、台帳の禁じている行為を要求していました。**
#
# **`[!]` が嘘をつくのは、`[!]` が無いより高い**（`scripts/drift.py` の長い註）。
# だから下の検査は「鳴らないこと」も「鳴ること」も両方 縛ります ——
# 片側だけ縛ると、次の回が門ごと黙らせて緑にできます。

NOW_OVERDUE = ("- claim: 手元だけで判定できるやつ\n"
               "  deadline: '2026-08-20'\n"
               "  needs:\n"
               "    - kind: now\n")


def test_いま判定できる期限切れなら_これまでどおり鳴る(tmp_path, monkeypatch):
    """**片側だけ緩めないための検査。**

    `needs: [kind: now]` は「手元のデータだけで判定できます」＝
    `ready` が今日。**この回に verdict を出せるので、止めるのは正しい。**

    **日付を固定しないこと。** `_ans_now()` が返すのは
    `deadline_check.today_jst()` ＝ **本物の今日**で、検査だけ 2026-08-24 に
    すると `ready > today` になり「期限のほうが手前」に落ちます
    （最初に書いたときそれで落ちました。**道具ではなく検査の側の誤り**）。
    """
    from datetime import date as _d, timedelta as _td
    today = drift.today_jst()
    dl = (_d.fromisoformat(today) - _td(days=4)).isoformat()
    at = (_d.fromisoformat(today) - _td(days=1)).isoformat() + "T10:00"
    _seed(tmp_path, monkeypatch, [_ship(at, "fix: 直した")] * 3,
          f"- claim: 手元だけで判定できるやつ\n  deadline: '{dl}'\n"
          "  needs:\n    - kind: now\n")
    text, drifting = drift.report(today)
    assert drifting is True
    assert "外れています" in text


def test_まだ判定できない期限切れでは門を鳴らさない(tmp_path, monkeypatch):
    """`deadline_check` が `warming`（まだ数えはじめたところ）と言う前提。

    **その回にできることが1つも無いので、止めても損しかしません。**
    """
    _seed(tmp_path, monkeypatch,
          [_ship("2026-08-23T10:00", "fix: 直した")] * 3, OPEN_OVERDUE)
    monkeypatch.setattr(drift, "_judge_state_by_claim",
                        lambda: {"冒頭が engaged を決める": ("warming", None)})
    text, drifting = drift.report("2026-08-24")
    assert drifting is False
    # **理由と、その回にやることが、同じ行の並びに出ること。**
    assert "まだ判定できない前提" in text
    assert "何もしないのが正解" in text


def test_判定できる日が期限より後なら_延ばせと言う(tmp_path, monkeypatch):
    """`ready > deadline`（期限のほうが手前）。

    **`falsified_if` は触らせないこと** —— 動かすのは期限だけです。
    """
    from datetime import date as _d
    _seed(tmp_path, monkeypatch,
          [_ship("2026-08-23T10:00", "fix: 直した")] * 3, OPEN_OVERDUE)
    monkeypatch.setattr(drift, "_judge_state_by_claim",
                        lambda: {"冒頭が engaged を決める": ("ready", _d(2026, 9, 10))})
    text, drifting = drift.report("2026-08-24")
    assert drifting is False
    assert "2026-09-10" in text
    assert "期限を延ばすこと" in text


def test_計器が読めないときは鳴らす側へ倒す(tmp_path, monkeypatch):
    """**黙るより鳴らす。**

    `deadline_check` が1本 読めないことは、「外れていない」ことの証拠では
    ありません。ここを逆に倒すと、**計器を壊すだけで門が緑になります。**
    """
    _seed(tmp_path, monkeypatch,
          [_ship("2026-08-23T10:00", "fix: 直した")] * 3, OPEN_OVERDUE)
    monkeypatch.setattr(drift, "_judge_state_by_claim", lambda: None)
    _, drifting = drift.report("2026-08-24")
    assert drifting is True


def test_台帳に在るのに突き合わせできない前提も鳴らす(tmp_path, monkeypatch):
    """claim が `deadline_check` の返りに無い ＝ 突き合わせ不能。

    **黙って通さないこと**（同上）。
    """
    _seed(tmp_path, monkeypatch,
          [_ship("2026-08-23T10:00", "fix: 直した")] * 3, OPEN_OVERDUE)
    monkeypatch.setattr(drift, "_judge_state_by_claim",
                        lambda: {"別の前提": ("warming", None)})
    _, drifting = drift.report("2026-08-24")
    assert drifting is True


def test_門と_deadline_check_が同じ前提について逆を言っていないこと():
    """**本物の台帳で、2つの道具が食い違っていないこと。**

    上の検査は合成の台帳で配線を縛ります。これは**実物**を縛ります ——
    2026-08-26 に実際に起きたのがこれで、合成だけでは捕まりません。

    落ちたときの直し方: `scripts/drift.py` の `split_overdue` が
    `deadline_check` の `warming` / `unreachable` を読めていません。
    **`overdue()` だけに戻さないこと**（戻した結果が、この検査の由来です）。
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "test_dc", Path(__file__).resolve().parent.parent / "scripts" / "deadline_check.py")
    dc = importlib.util.module_from_spec(spec)
    sys.modules["test_dc"] = dc
    spec.loader.exec_module(dc)

    today = drift.today_jst()
    warming = {v.claim for v in dc.check(dc.load()) if v.warming}
    od_now, _blocked = drift.split_overdue(drift.overdue(today), today)
    clash = [str(h.get("claim") or "") for h in od_now
             if str(h.get("claim") or "") in warming]
    assert not clash, (
        "`drift.py` が「この回は verdict を出せ」と言っている前提を、"
        "`deadline_check.py` は「まだ数えはじめたところ・何もしないのが正解」と"
        f"言っています: {clash}"
    )


def test_帯の中の期限に_延ばせと言わないこと(tmp_path, monkeypatch):
    """`deadline_check` が「帯の中。**書き換えないこと**」と言う前提。

    **`drift.py` は同じ `deadline_check` を根拠に挙げながら、
    「期限を延ばすこと」と指示していました**（実測 2026-08-27・
    「長尺の生成が落ちる主因は…」期限 08-27 / 判定日 08-28 / 帯 ±1日）。

    `Answer.slack` の註が名指ししている churn そのものです ——
    「3回とも『期限がずれています』と言われ、3回とも期限だけを書き換えた。
    **到達日は1日も動いていない。**」
    """
    from datetime import date as _d
    _seed(tmp_path, monkeypatch,
          [_ship("2026-08-23T10:00", "fix: 直した")] * 3, OPEN_OVERDUE)
    monkeypatch.setattr(
        drift, "_judge_state_by_claim",
        lambda: {"冒頭が engaged を決める": ("ready", _d(2026, 8, 25), False, 1)})
    text, drifting = drift.report("2026-08-24")
    assert drifting is False
    assert "期限を延ばすこと" not in text
    assert "書き換えないこと" in text


def test_帯の外なら今までどおり延ばせと言う(tmp_path, monkeypatch):
    """**帯を理由に黙らせないこと。** 本当にずれているものは、今までどおり言う。"""
    from datetime import date as _d
    _seed(tmp_path, monkeypatch,
          [_ship("2026-08-23T10:00", "fix: 直した")] * 3, OPEN_OVERDUE)
    monkeypatch.setattr(
        drift, "_judge_state_by_claim",
        lambda: {"冒頭が engaged を決める": ("ready", _d(2026, 9, 10), True, 1)})
    text, _ = drift.report("2026-08-24")
    assert "期限を延ばすこと" in text


def test_門と_deadline_check_が期限の書き換えについても逆を言っていないこと():
    """**実物**で縛る。`slips` が False の前提に「延ばせ」と言っていないこと。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "test_dc2", Path(__file__).resolve().parent.parent / "scripts" / "deadline_check.py")
    dc = importlib.util.module_from_spec(spec)
    sys.modules["test_dc2"] = dc
    spec.loader.exec_module(dc)

    today = drift.today_jst()
    stable = {v.claim for v in dc.check(dc.load()) if v.ready is not None and not v.slips}
    _now, blocked = drift.split_overdue(drift.overdue(today), today)
    clash = [str(h.get("claim") or "") for h, _why, todo in blocked
             if "期限を延ばすこと" in todo and str(h.get("claim") or "") in stable]
    assert not clash, (
        "`drift.py` が「期限を延ばせ」と言っている前提を、"
        "`deadline_check.py` は「帯の中。書き換えないこと」と言っています: "
        f"{clash}"
    )


def test_時刻の分かっている待ちは_その時刻を印字すること(tmp_path, monkeypatch):
    """**`deadline_check` と別のことを言わないこと**（2026-08-27 14:5x に踏んだ）。

    `deadline_check.py`  → 「**今日の 22:00 JST に出ます**。その時刻まで待つこと」
    `drift.py`（＝`status.py` に載る側）→ 「まだ数えはじめたところ
                                          （**伸び率が出ないので日が出せない**）」

    **同じ前提について、同じ回に、別のことを言っています。** 読んだ回は後者を
    「いつ来るか分からない待ち」と読み、**その日のうちに拾える前提を翌日以降へ流します。**
    実測: `day_cap` の対照日（08/27・19本）は 22:00 JST に読めるようになります。

    `Answer.todo` / `Answer.slips` と**同じ穴の3件目**です ——
    `deadline_check` が持っている欄を、`drift` が持って上がっていない。
    """
    _seed(tmp_path, monkeypatch,
          [_ship("2026-08-23T10:00", "fix: 直した")] * 3, OPEN_OVERDUE)
    monkeypatch.setattr(
        drift, "_judge_state_by_claim",
        lambda: {"冒頭が engaged を決める":
                 ("warming", None, None, 0, "", "…は **08/27 22:00 JST** に出ます", "22:00")})
    text, drifting = drift.report("2026-08-24")
    assert drifting is False
    assert "22:00 JST に出ます" in text, "時刻を持って上がっていません"
    assert "伸び率が出ないので日が出せない" not in text, (
        "時刻の分かっている待ちを「伸び率が出ない」で塗り潰しています")


def test_時刻の無い待ちは_これまでどおり伸び率で言うこと(tmp_path, monkeypatch):
    """**上の直しで、こちらを巻き込まないこと。**（本当に伸び率待ちの前提）"""
    _seed(tmp_path, monkeypatch,
          [_ship("2026-08-23T10:00", "fix: 直した")] * 3, OPEN_OVERDUE)
    monkeypatch.setattr(
        drift, "_judge_state_by_claim",
        lambda: {"冒頭が engaged を決める": ("warming", None, None, 0, "", "要 3 ／ いま 0", "")})
    text, _ = drift.report("2026-08-24")
    assert "まだ数えはじめたところ" in text
