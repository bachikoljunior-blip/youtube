"""`status.py` の出力そのものに目盛りを置く。

**2026-08-17 12:3x の穴に対する、2枚目の網です。**
1枚目（`test_next_moves`）は「1字の行が無いこと」しか見ていません。
**次に別の形で膨らんだら、また人が気づくまで通ります。**

あの回、出力 644行のうち 480行が1字でした。**検査は 855件あり、全部通っていました。**
増やしてきたのが「中身が正しいか」の検査だけで、
**「出したものが読めるか」を見るものが1つも無かった**からです。

中身の正しさは行数では分かりません。**この形の壊れ方だけが必ず行数に出ます** ——
1件が数百行に散る／同じ節が繰り返される／一覧が畳まれずに育つ。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import status  # noqa: E402


def _ledger(tmp_path: Path, lines: list[int]) -> Path:
    (tmp_path / "data").mkdir(exist_ok=True)
    p = tmp_path / "data" / "status_lines.jsonl"
    p.write_text("\n".join(
        json.dumps({"at": "2026-08-17T00:00:00+09:00", "lines": n})
        for n in lines) + "\n", encoding="utf-8")
    return p


def test_the_actual_break_would_have_rung(tmp_path):
    """**これが本体。** 210行が続いたあとの 644行は鳴る。"""
    _ledger(tmp_path, [208, 210, 212, 209, 210])
    msg = status.check_output_length(644, tmp_path)
    assert msg and "644行" in msg, msg


def test_adding_a_section_does_not_ring(tmp_path):
    """**節を1つ足したくらいでは鳴らないこと。** 鳴りっぱなしは沈黙と同じ。"""
    _ledger(tmp_path, [208, 210, 212, 209, 210])
    assert status.check_output_length(225, tmp_path) == ""


def test_boundary_is_the_ratio(tmp_path):
    _ledger(tmp_path, [100, 100, 100])
    assert status.check_output_length(150, tmp_path) == ""   # ちょうどは鳴らさない
    assert status.check_output_length(151, tmp_path) != ""


def test_shrinking_never_rings(tmp_path):
    """**縮んだほうは鳴らしません。** 落ちた回（外の口が403）は短くなります。"""
    _ledger(tmp_path, [600, 600, 600])
    assert status.check_output_length(210, tmp_path) == ""


def test_first_run_is_silent(tmp_path):
    (tmp_path / "data").mkdir()
    assert status.check_output_length(9999, tmp_path) == ""


def test_the_point_is_recorded_even_when_silent(tmp_path):
    """**読めた回は必ず積むこと。** 積まないと次の回が古い目盛りを見ます。"""
    (tmp_path / "data").mkdir()
    status.check_output_length(210, tmp_path)
    rows = [json.loads(x) for x in
            (tmp_path / "data" / "status_lines.jsonl").read_text(
                encoding="utf-8").splitlines()]
    assert [r["lines"] for r in rows] == [210]


def test_median_not_mean(tmp_path):
    """**中央値で見ること。** 1回の異常値が、次の回の目盛りを壊さない。

    644行の回が積まれた直後でも、210行の並びのほうが基準であってほしい。
    """
    _ledger(tmp_path, [210, 210, 644, 210, 210])
    assert status.check_output_length(400, tmp_path) != ""


def test_broken_ledger_does_not_kill_the_reader(tmp_path):
    """**状態を見る道具が、状態のせいで死んではいけない。**"""
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "status_lines.jsonl").write_text(
        'これは JSON ではない\n{"lines": "abc"}\n{"lines": 210}\n', encoding="utf-8")
    assert status.check_output_length(644, tmp_path) != ""


def test_counter_counts_newlines(capsys):
    """皮が行数を数えていること（数えていなければ、目盛りは永久に 0 のまま）。"""
    c = status._LineCounter(sys.stdout)
    c.write("あ\nい\n")
    c.write("う")
    capsys.readouterr()
    assert c.lines == 2


def test_real_ledger_exists_and_is_readable():
    """**実物が積まれていること。** 積まれていなければ、この目盛りは空回りです。"""
    p = ROOT / "data" / "status_lines.jsonl"
    assert p.exists(), "status.py を一度も走らせていないか、書き込みが落ちています"
    rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert rows and all(isinstance(r["lines"], int) for r in rows)
