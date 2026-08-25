"""`pick(N)` の N を、作りの通過率で割り引いて出すこと。

**3回運ばれて3回とも未着手だった申し送りの検査です**（`retro.py` 09:1x の3）。
`pick(8)` はテーマの数であって、`verify` を通る本数ではありません。
上振れしたまま「8本の日が作れます」と読むと、8本を狙って6本で終わり、
**M14 の8の段が1日ぶん立ちません。**

**そして落ち方を2つに分けること**が、この検査の本体です。

    生成が失敗   台本が verify に落ちた。**テーマ1件を消費して0本**
    予約が失敗   本は出来ている。**枠（403/429）や重なりで置けなかっただけ**

8/17 10:4x の1回は7本中5本が「予約が失敗」＝投稿の本数枠 429 でした。
混ぜて数えると通過率が 86 → 62パーセントに落ち、
**「8本の日には13本を作れ」と言い出します**（正しくは10本）。
枠のせいで作る量を増やすのは、1本あたり 12,800単位と約11分の、まっすぐな無駄です。
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import status  # noqa: E402


def _write(tmp_path: Path, runs: list[list[dict]]) -> Path:
    (tmp_path / "data").mkdir(exist_ok=True)
    p = tmp_path / "data" / "batch_runs.jsonl"
    p.write_text(
        "\n".join(json.dumps({"at": "2026-08-17T00:00:00+09:00", "results": r},
                             ensure_ascii=False) for r in runs) + "\n",
        encoding="utf-8")
    return p


def _ok(vid="abc"):
    return {"topic": "t", "video_id": vid, "error": ""}


def _build_failed():
    return {"topic": "t", "video_id": "", "error": "生成が失敗（exit 1）"}


def _schedule_failed():
    return {"topic": "t", "video_id": "", "error": "予約が失敗（exit 1）"}


def test_quota_failures_do_not_lower_the_build_rate(tmp_path, capsys):
    """**これが本体。** 枠で予約に落ちた本は、作りは通っています。"""
    _write(tmp_path, [[_ok(), _schedule_failed(), _schedule_failed(),
                       _schedule_failed(), _schedule_failed(), _schedule_failed(),
                       _build_failed()]])
    status._print_pass_rate(tmp_path, 8)
    out = capsys.readouterr().out
    assert "6/7" in out, out
    assert "86パーセント" in out, out
    # 混ぜて数えたときの 62パーセント・13本 が出てはいけない
    assert "62パーセント" not in out
    assert "13本**を作りに入れる" not in out


def test_scheduled_count_is_reported_separately(tmp_path, capsys):
    _write(tmp_path, [[_ok(), _schedule_failed()]])
    status._print_pass_rate(tmp_path, 8)
    out = capsys.readouterr().out
    assert "うち予約まで入ったのは 1本" in out, out
    assert "テーマの数とは無関係" in out


def test_build_failures_do_lower_the_rate(tmp_path, capsys):
    """**逆向きも見ること。** verify 落ちは、そのまま効く。"""
    _write(tmp_path, [[_ok(), _ok(), _build_failed(), _build_failed()]])
    status._print_pass_rate(tmp_path, 8)
    out = capsys.readouterr().out
    assert "2/4" in out and "50パーセント" in out, out
    assert "16本**を作りに入れる" in out, out


def test_all_passing_asks_for_exactly_eight(tmp_path, capsys):
    _write(tmp_path, [[_ok(), _ok(), _ok(), _ok()]])
    status._print_pass_rate(tmp_path, 8)
    out = capsys.readouterr().out
    assert "100パーセント" in out
    assert "8本**を作りに入れる" in out, out
    # 全部通っているときに「うち予約まで」の行は出さない
    assert "うち予約まで" not in out


def test_only_the_last_runs_are_counted(tmp_path, capsys):
    """**古い回を引きずらないこと。** 直近 PASS_RATE_RUNS 回だけ見る。"""
    old = [[_build_failed()] for _ in range(10)]
    _write(tmp_path, old + [[_ok()] for _ in range(status.PASS_RATE_RUNS)])
    status._print_pass_rate(tmp_path, 8)
    out = capsys.readouterr().out
    assert "100パーセント" in out, out


def test_missing_file_is_silent(tmp_path, capsys):
    status._print_pass_rate(tmp_path, 8)
    assert capsys.readouterr().out == ""


def test_broken_line_does_not_kill_the_reader(tmp_path, capsys):
    """**状態を見る道具が、状態のせいで死んではいけない。**"""
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "batch_runs.jsonl").write_text(
        '{"results": [{"video_id": "a", "error": ""}]}\nこれは JSON ではない\n',
        encoding="utf-8")
    status._print_pass_rate(tmp_path, 8)
    assert "100パーセント" in capsys.readouterr().out


@pytest.mark.parametrize("runs", [[], [[]]])
def test_empty_gives_nothing(tmp_path, capsys, runs):
    _write(tmp_path, runs) if runs else (tmp_path / "data").mkdir()
    if not runs:
        (tmp_path / "data" / "batch_runs.jsonl").write_text("", encoding="utf-8")
    status._print_pass_rate(tmp_path, 8)
    assert capsys.readouterr().out == ""


def test_real_ledger_has_both_kinds_of_failure():
    """**実物で見ること。** 2つの落ち方が実際に混ざっている台帳です。

    片方しか無くなったら、この検査は空回りします
    （`docs/trigger_main.md` §4「足した検査は、緑のまま0件で通る」）。
    """
    rows = [json.loads(l) for l in
            (ROOT / "data" / "batch_runs.jsonl").read_text(encoding="utf-8").splitlines()
            if l.strip()]
    errs = [str(x.get("error", "")) for r in rows for x in r.get("results", [])]
    assert any("生成" in e for e in errs)
    assert any("予約" in e for e in errs)
