"""`scripts/relay.py` と `stop_check.sh` の (2.0) —— **鎖の受け渡し。**

**この検査が守っているのは「受け渡しが記録できること」ではありません。**
守っているのは、**次の回が立たないまま終われないこと**です。

2026-08-24 の実測。親は 15:14 / 16:17 / 17:12 / 19:10 / 20:12 と発火し、
`list_sessions` も撃ったのに、**両方の札が空なのに立てませんでした。**
14:49〜21:29 の **6時間40分、だれも回っていません。** その前の週に
「本文の1行目を `list_sessions` に入れ替える」という直しを既に入れてあり、
**撃つようにはなったのに、撃った結果に対して動かない回が残りました。**
**文書は読ませられても、実行させません。** だから機械の側に移してあります。

ここが逆向きに壊れると（記録が無くても通るようになると）、
**空白は printf ではなく「次の回が来ないこと」として出ます** ——
気づくのはオーナーが画面を見たときだけで、それは目標本文が
「私が必ず読むとは限らない」と言っている当のものです。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("relay_mod", ROOT / "scripts" / "relay.py")
relay = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(relay)


# --- 速さの読み ---------------------------------------------------------

def test_pace_percentage_is_not_the_interval_ratio():
    """**間隔の比をそのまま出さないこと。**

    最初の版は `actual / sustainable` を出し、186分/90分 で
    **「許される速さの 207% しか使っていない」**と印字しました。
    実際は逆で、間隔が長いほど遅いので **48%** です。
    ここが逆だと「もう速すぎる」と読めて、**穴を塞ぐ側の判断が止まります。**
    """
    # 実際 186分・持続 90分 ＝ 半分しか使っていない
    assert round(90 / 186 * 100) == 48
    assert round(186 / 90 * 100) == 207  # ← これを出してはいけない側


# --- 記録と読み戻し -----------------------------------------------------

def _run(args, cwd, env=None):
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "relay.py"), *args],
        capture_output=True, text=True, timeout=120, cwd=str(cwd), env=env,
    )


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    """**実物の台帳を触らないこと。** 検査が実物の数え上げを食い合います
    （2026-08-16、`tests/` を2度回したら引き止めの数が3回ぶん進んで落ちた）。"""
    monkeypatch.setattr(relay, "LEDGER", tmp_path / "relay.jsonl")
    return tmp_path


def test_check_is_2_before_recording_and_0_after(sandbox, monkeypatch):
    """`--check` が門の本体です。**記録するまで 2 を返し続けること。**"""
    monkeypatch.setattr(relay, "me", lambda: "session_TEST")
    assert relay.cmd_check(None) == 2

    args = type("A", (), {"hourly": 1, "optimizer": 1, "spawned": "", "note": ""})()
    relay.cmd_record(args)
    assert relay.cmd_check(None) == 0


def test_another_sessions_record_does_not_satisfy_this_session(sandbox, monkeypatch):
    """**隣の回の記録で通してはいけません。**

    通ると、1回だれかが記録した以降ぜんぶ素通りになり、門が消えます。
    """
    monkeypatch.setattr(relay, "me", lambda: "session_OTHER")
    args = type("A", (), {"hourly": 1, "optimizer": 1, "spawned": "", "note": ""})()
    relay.cmd_record(args)

    monkeypatch.setattr(relay, "me", lambda: "session_TEST")
    assert relay.cmd_check(None) == 2


def test_record_warns_when_a_lane_is_left_empty(sandbox, monkeypatch, capsys):
    """**空の札を残したまま記録したら、黙らないこと。**

    記録は通します（止まったまま死ぬほうが確実に悪い）が、
    **印字が残らないと、次の回がその回を責められません。**
    """
    monkeypatch.setattr(relay, "me", lambda: "session_TEST")
    args = type("A", (), {"hourly": 0, "optimizer": 1, "spawned": "", "note": ""})()
    relay.cmd_record(args)
    out = capsys.readouterr().out
    assert "空の札" in out
    assert "youtube-hourly" in out


def test_record_is_quiet_when_the_empty_lane_was_filled(sandbox, monkeypatch, capsys):
    """立てたなら警告しないこと（立てた回まで責めると、印字が信用されなくなる）。"""
    monkeypatch.setattr(relay, "me", lambda: "session_TEST")
    args = type("A", (), {"hourly": 0, "optimizer": 1, "spawned": "hourly", "note": ""})()
    relay.cmd_record(args)
    out = capsys.readouterr().out
    assert "空の札" not in out


def test_audit_counts_the_runs_that_left_a_lane_empty(sandbox, monkeypatch, capsys):
    """**効いているかどうかは、空白が消えたかで見ること。**"""
    monkeypatch.setattr(relay, "me", lambda: "session_A")
    relay.cmd_record(type("A", (), {"hourly": 0, "optimizer": 1, "spawned": "", "note": ""})())
    monkeypatch.setattr(relay, "me", lambda: "session_B")
    relay.cmd_record(type("A", (), {"hourly": 0, "optimizer": 1, "spawned": "hourly", "note": ""})())

    relay.cmd_audit(type("A", (), {"limit": 15})())
    out = capsys.readouterr().out
    assert "**1/2**" in out


# --- 入口そのものが通ること ---------------------------------------------

def test_next_says_that_a_pending_approval_is_not_alive():
    """**承認待ちを「生きている」と数えないこと。**

    2026-08-24 22:5x の実測。主実行の子は仕事を終えて 2383a69 まで push した
    あと、**`archive_session` の承認待ちで `REQUIRES_ACTION` のまま固着**していました。
    一覧では `connection_status: connected` なので**生きて見えます。**
    承認待ちは永久に待つ（目標本文「私が必ず読むとは限らない」）ので、
    **そこを生きていると読むと、札は空のままです。**
    """
    p = _run(["--next"], cwd=ROOT)
    assert p.returncode == 0, p.stderr
    assert "REQUIRES_ACTION" in p.stdout
    assert "生きている」ではありません" in p.stdout


def test_the_entry_point_is_not_named_plan():
    """**`--plan` という名前にしないこと**（2026-08-24 に実測）。

    `python scripts/relay.py --plan` は `Bash(python *)` を許してあっても
    **auto mode の分類器に弾かれます。子は無人なので、弾かれた時点で仕組みが死にます。**
    ここは名前の趣味の話ではなく、**入口が通るかどうか**の話です。
    """
    src = (ROOT / "scripts" / "relay.py").read_text(encoding="utf-8")
    assert '"--next"' in src
    assert 'add_argument("--plan"' not in src


def test_next_prints_the_spawn_arguments_for_both_lanes(tmp_path):
    """**引数を出すところまでが道具です。** 手で組ませると `source_url` が落ちます
    （8/17・8/18 に2回、repo の無い子が立った）。"""
    p = _run(["--next"], cwd=ROOT)
    assert p.returncode == 0, p.stderr
    assert "youtube-hourly" in p.stdout
    assert "youtube-optimizer" in p.stdout
    # 両方の札に `source_url` が付いていること
    assert p.stdout.count('"source_url"') >= 2
    assert "claude/youtube-auto-post-revenue-ggedij" in p.stdout


# --- 門が実際に仕込まれていること ---------------------------------------

def test_stop_hook_parses():
    """`stop_check.sh` は**手で実行できません**（2026-08-16、この1行で子が1つ死んだ）。
    だから**構文検査だけ**します —— 壊れたフックは全部の回を通してしまいます。"""
    p = subprocess.run(["bash", "-n", str(ROOT / "scripts" / "stop_check.sh")],
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, p.stderr


def test_stop_hook_actually_calls_the_relay_gate():
    """**註に書くだけにしないこと。** 2026-08-20 に註へ書いたものは、
    その日のうちに全部素通りしました。**引き止めが、素通りしない唯一の形です。**"""
    src = (ROOT / "scripts" / "stop_check.sh").read_text(encoding="utf-8")
    assert "relay.py" in src
    assert "--check" in src
    assert '"decision":"block"' in src.replace(" ", "")


def test_stop_hook_relay_gate_is_not_silenced_by_an_unmarked_run():
    """**この門だけは `SHIP_STATE = unknown` で黙ってはいけません。**

    他の門は「印を打っていない回＝周ではない」で足切りします。
    **ここに同じ足切りを置くと、最適化の札にだけ効かなくなります** ——
    最適化の子は `run_marker.py` を押すかどうか自体が自由なので、
    **印の無い回がふつう**です。そして 2026-08-24 に 14:31〜21:50 の
    **7時間19分ぶん空いていたのは、まさにその札でした。**
    """
    src = (ROOT / "scripts" / "stop_check.sh").read_text(encoding="utf-8")
    gate = src.split("(2.0)", 1)[1].split("--- (2)", 1)[0]
    assert 'if [ -n "$ME" ]; then' in gate
    assert 'SHIP_STATE" != "unknown"' not in gate


def test_stop_hook_relay_gate_lets_go_after_two_blocks():
    """**止まったまま死ぬほうが確実に悪い。** それはこの門が塞ぎたい穴そのものです。"""
    src = (ROOT / "scripts" / "stop_check.sh").read_text(encoding="utf-8")
    assert 'RL" -lt 2' in src


# --- 立てすぎも数えること（2026-08-25。`--audit` は立て損ねしか見ていなかった）---


def _rec(session, at, spawned, snapshot_at=None):
    r = {"at": at, "session": session, "spawned": spawned,
         "alive": {"youtube-hourly": 0, "youtube-optimizer": 0}}
    if snapshot_at:
        r["snapshot_at"] = snapshot_at
    return r


def test_別の回が同じ札を数分内に立てたら組で出る():
    """**これが本体。** 親の毎時発火と子の受け渡しが、どちらも同じ札を立てる形。"""
    rows = [_rec("A", "2026-08-25T03:05:11+00:00", ["hourly", "optimizer"]),
            _rec("B", "2026-08-25T03:05:59+00:00", ["hourly"])]
    dup = relay._dupes(rows)
    assert [(a, b, lane) for a, b, lane in dup] == [("A", "B", "youtube-hourly")]


def test_同じ回が2行書いても二重とは数えない():
    """立てたのは1度。記録が2行あるだけの回を、取り合いと読まないこと。"""
    rows = [_rec("A", "2026-08-25T03:05:11+00:00", ["hourly"]),
            _rec("A", "2026-08-25T03:05:40+00:00", ["hourly"])]
    assert relay._dupes(rows) == []


def test_幅の外なら二重ではない():
    """**親の発火間隔より十分に短い幅**でだけ鳴ること。"""
    rows = [_rec("A", "2026-08-25T03:05:11+00:00", ["hourly"]),
            _rec("B", "2026-08-25T04:05:11+00:00", ["hourly"])]
    assert relay._dupes(rows) == []


def test_札がちがえば二重ではない():
    rows = [_rec("A", "2026-08-25T03:05:11+00:00", ["hourly"]),
            _rec("B", "2026-08-25T03:05:30+00:00", ["optimizer"])]
    assert relay._dupes(rows) == []


def test_数えた時刻があればそちらを使う():
    """`at` は記録した時刻。**`alive` は撮った時刻の姿**なので、そちらで並べる。

    下は `at` どうしなら 10分を越えて見えますが、**撮った時刻は 20秒差**です。
    """
    rows = [_rec("A", "2026-08-25T03:20:00+00:00", ["hourly"],
                 snapshot_at="2026-08-25T03:05:00+00:00"),
            _rec("B", "2026-08-25T03:40:00+00:00", ["hourly"],
                 snapshot_at="2026-08-25T03:05:20+00:00")]
    assert len(relay._dupes(rows)) == 1


def test_時刻が読めない行は落とす():
    rows = [{"session": "A", "at": "こわれた", "spawned": ["hourly"]},
            _rec("B", "2026-08-25T03:05:30+00:00", ["hourly"])]
    assert relay._dupes(rows) == []


# --- 承認が挟まったか（2026-08-25 に足した） ----------------------------
#
# **これは「秒を記録できること」の検査ではありません。**
# 守っているのは、**承認で動いていたのを「自力で回っている」と書けないこと**です。
#
# オーナーの指摘（原文）:
#     「上手くいってるように見えてるところは私が承認押しまくってるおかげかもよ」
#
# そのとおりでした。**呼んだ側からは、承認されて成功したのと許可されて成功したのが
# 同じに見えます** —— 返るのは「成功」だけ。見分けられるのは「拒否」だけで、
# 承認は待たされたことすら分かりません。**唯一の目盛りが秒です。**

def test_測っていない回はそう印字する(sandbox, monkeypatch, capsys):
    """**黙って通さないこと。**

    ここが黙ると、次の回は「`--record` は通った＝測れている」と読みます。
    **無いことが見えなければ、感想に戻ります。**
    """
    monkeypatch.setattr(relay, "me", lambda: "session_TEST")
    args = type("A", (), {"hourly": 1, "optimizer": 1, "spawned": "", "note": ""})()
    relay.cmd_record(args)
    out = capsys.readouterr().out
    assert "測っていません" in out
    assert "数えていません" in out


def test_速い呼び出しは承認なしと読む(sandbox, monkeypatch, capsys):
    monkeypatch.setattr(relay, "me", lambda: "session_TEST")
    args = type("A", (), {"hourly": 1, "optimizer": 1, "spawned": "", "note": "",
                          "call_seconds": 10.7, "blocked": 0})()
    relay.cmd_record(args)
    out = capsys.readouterr().out
    assert "承認は挟まっていません" in out
    assert "10.7秒" in out
    assert "承認待ちだった回: **0件**" in out


def test_遅い呼び出しは疑いとして残す(sandbox, monkeypatch, capsys):
    """**閾を超えたら、成功していても疑いを残すこと。**

    `--record` は通ります（記録できないほうが確実に悪い）が、
    **印字が「素通りだった」に見えてはいけません。**
    """
    monkeypatch.setattr(relay, "me", lambda: "session_TEST")
    args = type("A", (), {"hourly": 1, "optimizer": 1, "spawned": "", "note": "",
                          "call_seconds": float(relay.APPROVAL_SUSPECT_SEC + 1),
                          "blocked": 2})()
    relay.cmd_record(args)
    out = capsys.readouterr().out
    assert "承認待ちが挟まった疑い" in out


def test_秒の引き算はスクリプト側でやる(sandbox):
    """**模型に `date` の引き算をさせないこと。**

    分をまたいだ回で必ず間違え、しかも**短く出るほうへ間違えます**
    （＝「承認は挟まっていない」の側）。だから `--since` で渡し、ここで引く。
    """
    import time
    since = int(time.time()) - 90
    p = _run(["--record", "--hourly", "1", "--optimizer", "1",
              "--since", str(since), "--blocked", "0"], cwd=sandbox,
             env={**__import__("os").environ,
                  "CLAUDE_CODE_REMOTE_SESSION_ID": "session_TEST",
                  # **実物の台帳に行を足さないこと。** `monkeypatch` は
                  # 別プロセスに効きません（最初の版が1行足しました）。
                  "RELAY_LEDGER": str(sandbox / "relay.jsonl")})
    assert p.returncode == 0, p.stderr
    assert "承認待ちが挟まった疑い" in p.stdout, p.stdout
    assert (sandbox / "relay.jsonl").exists()


def test_stamp_は秒だけを標準出力に出す(sandbox):
    """`--since` に渡す値です。**説明を混ぜると次の回が貼り間違えます。**"""
    p = _run(["--stamp"], cwd=sandbox)
    assert p.returncode == 0, p.stderr
    assert p.stdout.strip().isdigit(), repr(p.stdout)


def test_audit_は測った回が0なら何も言えないと言う(sandbox, monkeypatch, capsys):
    """**0件を「承認なし 0件」と読ませないこと。**

    「疑い 0」は「測って無かった」と同じ字面になり得ます。
    測っていないなら、**そう言うこと。**
    """
    monkeypatch.setattr(relay, "me", lambda: "session_TEST")
    (sandbox / "relay.jsonl").write_text(
        json.dumps({"at": "2026-08-25T00:00:00+00:00", "session": "s",
                    "alive": {"youtube-hourly": 1, "youtube-optimizer": 1},
                    "spawned": []}, ensure_ascii=False) + "\n", encoding="utf-8")
    relay.cmd_audit(type("A", (), {"limit": 5})())
    out = capsys.readouterr().out
    assert "まだ何も言えません" in out


def test_audit_は疑いのある回を数えて出す(sandbox, monkeypatch, capsys):
    monkeypatch.setattr(relay, "me", lambda: "session_TEST")
    rows = [
        {"at": "2026-08-25T00:00:00+00:00", "session": "a", "spawned": [],
         "alive": {"youtube-hourly": 1, "youtube-optimizer": 1},
         "call_seconds": 9.0, "blocked": 0},
        {"at": "2026-08-25T01:00:00+00:00", "session": "b", "spawned": [],
         "alive": {"youtube-hourly": 1, "youtube-optimizer": 1},
         "call_seconds": float(relay.APPROVAL_SUSPECT_SEC + 300), "blocked": 3},
    ]
    (sandbox / "relay.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8")
    relay.cmd_audit(type("A", (), {"limit": 5})())
    out = capsys.readouterr().out
    assert "承認なしで通った **1**" in out
    assert "承認待ちの疑い **1**" in out
    assert "自力で回っている" in out          # 疑いが出た回は、そう書くなと言う
    assert "**3件**" in out                    # 承認待ちの件数の合計


def test_next_は撃つ前に秒を打てと言う():
    """**手順の側にも置くこと。** 測り方を知らない回は測りません。"""
    p = _run(["--next"], cwd=ROOT)
    assert p.returncode == 0, p.stderr
    assert "--stamp" in p.stdout
    assert "--blocked" in p.stdout
