"""潰した宣言を、**散文ではなく構造で**残すこと（`--closes`）。

# **`--lever "none"` と `--moves 0` は、この検査が見ているものではありません**
# （2026-08-19 21:2x ／ 2026-08-20 08:5x）。`run_marker.py --ship` は
# **腕の宣言と、予測日を何日動かす見込みか**を必須にしたので、`--closes` を試すにも要ります
# （`src/levers.py`）。**ここで `none` / `0` を選んでいるのは「別軸だ」という意味**で、
# 腕と見込みそのものの検査は `tests/test_levers.py` にあります。
#
# **旗を増やした回へ**: ここは14件まとめて落ちます（`--lever` を足した回も同じ形で
# 落としています）。**必須の旗を足したら、この行を探すこと。**

## なぜ要るか（4回運ばれた申し送り。2026-08-16 に閉じた）

`retro.py` の持ち越しは「潰したと宣言された語」を落とします。
**その宣言は散文でした** ——「〜はこの回で閉じました」と日誌に手で書く約束。
**約束は3回破れ、そのたびに読む側を継ぎ足しています:**

    09:5x  「**一度閉じた後の再発**」を宣言と誤読        → `REOPEN_RE` を足した
    10:3x  引用符の中の「`閉じました`」を宣言と誤読      → `CODE_SPAN_RE` を足した
    06:3x  `_template.py` は閉じたのに**宣言が書かれず** → 4回運ばれた

**前2つは「書きすぎ」、3つめは「書き忘れ」で向きが逆なのに、原因は1つ**です ——
**宣言が人の散文の中にしかなく、機械が文意を当てにいっていた。**
語彙を足す限り、日誌が新しい言い回しをすれば戻ります（実際3回戻りました）。

だから**読む場所を増やしました。** 構造の側（`data/runs.jsonl` の `closes`）には
解釈が要りません。**散文の側は消していません**（過去の日誌はそれでしか読めない）。

## 検査が押さえているもの

- 書く側が、**出したものと対で**残すこと（`--closes` 単独は受けない）
- **散文が読めない形でも**、記録があれば黙ること（上の3つの再現）
- **宣言より後の言及は残ること**（「一度閉じた後の再発」は潰れていない証拠）
- 古い行（`journal_lines` の無い ship）を**壊れた宣言として読まないこと**
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


retro = _load("retro")
run_marker = _load("run_marker")


@pytest.fixture
def paths(tmp_path, monkeypatch):
    """書く側と読む側が、**同じ1本のファイル**を見ていることまで検査する。"""
    runs = tmp_path / "runs.jsonl"
    journal = tmp_path / "JOURNAL.md"
    journal.write_text("x\n" * 40, encoding="utf-8")
    monkeypatch.setattr(run_marker, "MARKS", runs)
    monkeypatch.setattr(run_marker, "JOURNAL", journal)
    monkeypatch.setattr(retro, "RUNS", runs)
    return runs, journal


def rows(runs: Path) -> list[dict]:
    return [json.loads(x) for x in runs.read_text(encoding="utf-8").splitlines() if x.strip()]


def test_書く側が語と日誌の行数を残す(paths):
    runs, journal = paths
    assert run_marker.main(["--ship", "fix: なにか", "--closes", "critique_queue", "--lever", "none", "--moves", "0"]) == 0
    (rec,) = rows(runs)
    assert rec["kind"] == "ship"
    assert rec["closes"] == ["critique_queue"]
    # **行数は「宣言した時点の日誌の長さ」。** これが `retro` の行番号の目盛りになる
    assert rec["journal_lines"] == len(journal.read_text(encoding="utf-8").split("\n"))


def test_closes_は何度でも書ける(paths):
    runs, _ = paths
    run_marker.main(["--ship", "fix: 2件", "--closes", "aaa", "--closes", "bbb", "--lever", "none", "--moves", "0"])
    assert rows(runs)[0]["closes"] == ["aaa", "bbb"]


def test_closes_だけでは受けない(paths):
    """**宣言は「何を出して閉じたか」と対でなければ、散文の約束と同じ**です。"""
    with pytest.raises(SystemExit):
        run_marker.main(["--closes", "critique_queue"])


def test_closes_を書かない_ship_は今までどおり(paths):
    """**既存の呼び方の挙動を変えないこと**（毎周これを叩いています）。"""
    runs, _ = paths
    run_marker.main(["--ship", "means: なにか", "--lever", "none", "--moves", "0"])
    rec = rows(runs)[0]
    assert "closes" not in rec and "journal_lines" not in rec


def test_読む側が記録から拾う(paths):
    runs, _ = paths
    run_marker.main(["--ship", "fix: x", "--closes", "critique_queue", "--lever", "none", "--moves", "0"])
    assert retro.recorded_closures() == {"critique_queue": 41}


def test_同じ語が二度なら後のほうを採る(paths):
    runs, journal = paths
    run_marker.main(["--ship", "fix: 1回目", "--closes", "abc", "--lever", "none", "--moves", "0"])
    journal.write_text("x\n" * 100, encoding="utf-8")
    run_marker.main(["--ship", "fix: 2回目", "--closes", "abc", "--lever", "none", "--moves", "0"])
    assert retro.recorded_closures()["abc"] == 101


def test_journal_lines_の無い行は読まない(paths):
    """**古い ship が全部「0行目の宣言」になると、何も黙らせません**（無害側）。

    それでも読まないのは、**`closes` だけ手で足した行を宣言に数えないため**です。
    """
    runs, _ = paths
    runs.write_text(json.dumps({"kind": "ship", "closes": ["abc"]}) + "\n", encoding="utf-8")
    assert retro.recorded_closures() == {}


def test_ship_以外の行は読まない(paths):
    runs, _ = paths
    runs.write_text(
        json.dumps({"kind": "start", "closes": ["abc"], "journal_lines": 9}) + "\n",
        encoding="utf-8")
    assert retro.recorded_closures() == {}


def test_壊れた行で落ちない(paths):
    runs, _ = paths
    runs.write_text("{壊れた\n\n" + json.dumps(
        {"kind": "ship", "closes": ["abc"], "journal_lines": 9}) + "\n", encoding="utf-8")
    assert retro.recorded_closures() == {"abc": 9}


# --- ここからが本体。**散文が読めない3つの形を、記録が越えること** ---

def _muted(journal_text: str, tok: str) -> list[str]:
    """`retro.main` と同じ数え方で、**残った言及の日付**を返す。"""
    closed, _src = retro.all_closures(journal_text)
    return [d for d, body, start in retro.handoff_blocks(journal_text)
            if tok in retro.tokens(body)
            and not (tok in closed and start <= closed[tok])]


def test_散文が書き忘れても記録があれば黙る(paths):
    """`_template.py` の形。**閉じたのに宣言が書かれず、4回運ばれました。**"""
    runs, journal = paths
    doc = "\n".join([
        "## 2026-08-16 01:0x — 題",
        "### 次の回へ",
        "1. `_template.py` の埋める順番",
        "",
        "## 2026-08-16 02:0x — 題",
        "### 次の回へ",
        "1. `_template.py` の埋める順番（まだ）",
    ])
    assert len(_muted(doc, "_template.py")) == 2      # 記録が無ければ持ち越し
    journal.write_text(doc + "\n", encoding="utf-8")
    run_marker.main(["--ship", "fix: ひな型", "--closes", "_template.py", "--lever", "none", "--moves", "0"])
    assert _muted(doc, "_template.py") == []          # **散文は1字も変えていない**


def test_散文が閉じていないと言う行でも記録が勝つ(paths):
    """09:5x の形。「**一度閉じた後の再発**」は散文では宣言に読めません（正しい）。

    **記録は解釈しないので、その行があっても黙ります。**
    """
    runs, journal = paths
    doc = "\n".join([
        "## 2026-08-16 01:0x — 題",
        "### 次の回へ",
        "1. 持ち越し: `critique_queue` の待ち（**一度閉じた後の再発**・35本）",
    ])
    assert retro.closures(doc) == {}
    journal.write_text(doc + "\n", encoding="utf-8")
    run_marker.main(["--ship", "fix: 待ち行列", "--closes", "critique_queue", "--lever", "none", "--moves", "0"])
    assert _muted(doc, "critique_queue") == []


def test_引用符の中の宣言でも記録が勝つ(paths):
    """10:3x の形（**同じ穴の3枚目**）。散文は引用の中を動詞として読みません。"""
    runs, journal = paths
    doc = "\n".join([
        "## 2026-08-16 01:0x — 題",
        "### 次の回へ",
        "1. `closures()` を「`閉じました`」で書いたら `critique_queue` が黙った",
    ])
    assert retro.closures(doc) == {}
    journal.write_text(doc + "\n", encoding="utf-8")
    run_marker.main(["--ship", "fix: 読む場所", "--closes", "critique_queue", "--lever", "none", "--moves", "0"])
    assert _muted(doc, "critique_queue") == []


def test_宣言より後の言及は残る(paths):
    """**これを落とすと、再発が見えなくなります**（`critique_queue` は実際に戻った）。

    行数を一緒に残しているのは、まさにこの一線を引くためです。
    """
    runs, journal = paths
    before = "\n".join([
        "## 2026-08-16 01:0x — 題",
        "### 次の回へ",
        "1. `critique_queue` の待ち",
    ])
    journal.write_text(before + "\n", encoding="utf-8")
    run_marker.main(["--ship", "fix: x", "--closes", "critique_queue", "--lever", "none", "--moves", "0"])
    after = before + "\n" + "\n".join([
        "",
        "## 2026-08-16 02:0x — 題",
        "### 次の回へ",
        "1. `critique_queue` がまた詰まった",
    ])
    kept = _muted(after, "critique_queue")
    assert len(kept) == 1 and "02:0x" in kept[0], kept


def test_散文の宣言は消えていない(paths):
    """**片方だけにしないこと。** 8/16 以前の日誌は散文でしか読めません。"""
    runs, _ = paths
    doc = "**`nenkin` はこの回で閉じました**\n"
    closed, from_record = retro.all_closures(doc)
    assert "nenkin" in closed and from_record == set()


def test_出どころが分かれて返る(paths):
    """出す側が［記録］と［日誌の文］を分けて見せられること。"""
    runs, journal = paths
    journal.write_text("x\n" * 5, encoding="utf-8")
    run_marker.main(["--ship", "fix: x", "--closes", "kikai", "--lever", "none", "--moves", "0"])
    closed, from_record = retro.all_closures("**`sanbun` はこの回で閉じました**\n")
    assert from_record == {"kikai"}
    assert set(closed) == {"kikai", "sanbun"}


# ---------------------------------------------------------------------------
# **直し方のほうが帳簿を壊していた**（2026-08-18。`undeclared_close` 鳴った4回・当たり0）
#
# `_suggest_undeclared` は正しく「語そのものも宣言せよ」と言いますが、
# 直し方として **`--ship` をもう一度打て**と案内していました。`--ship` は追記なので
# **同じ成果が2行**入り、`retro.py` の種類別も `status.py` の件数も二重に数えます。
# **従うと悪くなるので、4回とも従われていません。**畳んでも直らない側でした。
# ---------------------------------------------------------------------------

def test_closes_add_は_ship_を増やさない(paths):
    runs, _ = paths
    run_marker.main(["--ship", "fix: なにか", "--closes", "carry_over", "--lever", "none", "--moves", "0"])
    assert run_marker.main(["--closes-add", "critique_queue"]) == 0
    recs = rows(runs)
    assert len([r for r in recs if r["kind"] == "ship"]) == 1, \
        "**同じ成果が2行**入っています（帳簿が二重に数えます）"
    assert recs[-1]["closes"] == ["carry_over", "critique_queue"]


def test_closes_add_は同じ語を二重に足さない(paths):
    runs, _ = paths
    run_marker.main(["--ship", "fix: なにか", "--closes", "aaa", "--lever", "none", "--moves", "0"])
    run_marker.main(["--closes-add", "aaa"])
    assert rows(runs)[-1]["closes"] == ["aaa"]


def test_closes_add_は前の回の記録を触らない(paths, monkeypatch):
    """前の回の宣言は、**その回の判断の記録**です。足す先はこの回だけ。"""
    runs, _ = paths
    monkeypatch.setattr(run_marker, "session_id", lambda: "前の回")
    run_marker.main(["--ship", "fix: 前の回", "--closes", "aaa", "--lever", "none", "--moves", "0"])
    monkeypatch.setattr(run_marker, "session_id", lambda: "この回")
    run_marker.main(["--ship", "fix: この回", "--lever", "none", "--moves", "0"])
    run_marker.main(["--closes-add", "bbb"])
    old, new = rows(runs)
    assert old["closes"] == ["aaa"], "前の回の記録が書き換わっています"
    assert new["closes"] == ["bbb"]


def test_ship_が無いまま_closes_add_しても壊さない(paths):
    runs, _ = paths
    assert run_marker.main(["--closes-add", "aaa"]) == 1
    assert not runs.exists() or rows(runs) == []


def test_closes_add_は_ship_と一緒には使わない(paths):
    with pytest.raises(SystemExit):
        run_marker.main(["--ship", "fix: x", "--closes-add", "aaa", "--lever", "none", "--moves", "0"])


def test_closes_add_の語彙は書き込む前に読む(paths, capsys, monkeypatch):
    """**足した宣言が、その語を一覧から消してから読む**と、
    **正しい語を足した回にかぎって「一覧に無い」**と言われます
    （`ship()` には註があるのに、新しく足した道には無かった —— **片方だけ**）。
    """
    runs, journal = paths
    # `_known_vocab()` は `from retro import carry_over` で**そのとき**の
    # `sys.modules["retro"]` を引きます。他の検査が同じ名前で別の実体を
    # 積み直すので、**この1本だけ実体を留めます**（単独では通り、
    # 全体で走らせると落ちる、という形で1度踏みました）。
    monkeypatch.setitem(sys.modules, "retro", retro)
    monkeypatch.setattr(retro, "JOURNAL", journal)
    journal.write_text(
        "\n".join(f"## 2026-08-1{i} の回\n\n### 次の回へ\n\n"
                  f"1. **`critique_queue` が残っています。**\n" for i in range(3)),
        encoding="utf-8")
    assert "critique_queue" in retro.carry_over()[0], "検査の前提が崩れています"
    run_marker.main(["--ship", "fix: なにか", "--lever", "none", "--moves", "0"])
    capsys.readouterr()
    run_marker.main(["--closes-add", "critique_queue"])
    out = capsys.readouterr().out
    assert "一覧に無い語" not in out, f"正しい語が「一覧に無い」と言われています:\n{out}"
