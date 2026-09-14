"""コマ1（フック）の型を数える口（2026-09-14 14:3x・optimizer・Opus）。

オーナー 14:2x `d88d0dcd`「**フックが弱いと思うな。どのテーマに需要があるのかとは別に、
興味を引くような内容にしないと**」に当てる数が、どの口にも在りませんでした
（`curve_aligned` は維持率を秒で出すだけで、**コマ1 が何秒で中に何が書いてあるか**は
誰も数えていない）。**この口は判定しません** —— 強い弱いは `hourly` とオーナー（METHOD §5・§7）。

**この検査は実物の台本を読みません**（§5 の教訓 6つ目「きょうの状態を不変条件に書かない」）——
台本は毎日 増えるので、`tmp_path` に作ります。
"""
import json
from pathlib import Path

from studio import trend


def _write(d: Path, sid: str, say: str) -> None:
    (d / f"{sid}.json").write_text(json.dumps({
        "id": sid, "date": sid[:10], "title": "t #Shorts", "takeaway": "t",
        "segments": [{"say": say, "show": "x"}, {"say": "つぎ。"}],
    }, ensure_ascii=False), encoding="utf-8")


_NAMED = "65歳から年金をもらう人へ。いくら減るか計算します。"     # 名指し ＋ 予告
_HOOKY = "年金は、もらう年を1年おくらせるだけで8パーセントふえます。"   # どちらでもない


def test_型を数える(tmp_path: Path):
    _write(tmp_path, "2026-09-01-a", _NAMED)
    _write(tmp_path, "2026-09-02-b", _HOOKY)
    h = trend.hook_shape([], tmp_path)
    assert h["n"] == 2
    assert h["to_whom"] == 1 and h["herald"] == 1
    assert h["question"] == 0 and h["number"] == 2


def test_連は新しいほうから数える(tmp_path: Path):
    """`views_streak` と同じ向き。古い所に別の型が在っても、連は切れない。"""
    _write(tmp_path, "2026-09-01-a", _HOOKY)
    for k, day in enumerate(("2026-09-02-b", "2026-09-03-c", "2026-09-04-d"), 1):
        _write(tmp_path, day, _NAMED)
    assert trend.hook_shape([], tmp_path)["run"] == 3


def test_陽性対照_新しい1本が型を外すと連は0(tmp_path: Path):
    """**壊したら落ちる**（§5 の教訓の形 3つ目）—— いちばん新しい本が別の形なら、連は 0。"""
    for day in ("2026-09-01-a", "2026-09-02-b", "2026-09-03-c"):
        _write(tmp_path, day, _NAMED)
    assert trend.hook_shape([], tmp_path)["run"] == 3
    _write(tmp_path, "2026-09-04-d", _HOOKY)
    assert trend.hook_shape([], tmp_path)["run"] == 0


def test_問いと数は別に数える(tmp_path: Path):
    _write(tmp_path, "2026-09-01-a", "年金はいつからもらうのが得でしょうか？")
    h = trend.hook_shape([], tmp_path)
    assert h["question"] == 1 and h["number"] == 0
    assert h["to_whom"] == 0 and h["herald"] == 0


def test_秒数は台帳の実測から引く(tmp_path: Path):
    """コマ1 の秒は `built` の `scenes[0]`（実測）。無ければ 字数 ÷ その本の実測 字/秒。"""
    _write(tmp_path, "2026-09-01-a", _NAMED)
    _write(tmp_path, "2026-09-02-b", _NAMED)
    rows = [{"event": "built", "id": "2026-09-01-a", "scenes": [8.4, 9.0], "chars": 400, "seconds": 80.0},
            {"event": "built", "id": "2026-09-02-b", "chars": 400, "seconds": 80.0}]   # scenes なし
    got = {b["sid"]: b["sec"] for b in trend.hook_shape(rows, tmp_path)["books"]}
    assert got["2026-09-01-a"] == 8.4                       # 実測そのもの
    assert abs(got["2026-09-02-b"] - len(_NAMED) / 5.0) < 1e-9   # 400/80.0 = 5.0字/秒


def test_1行は判定を言わない(tmp_path: Path):
    """**強い弱いはこの口の仕事ではありません**（§5 ＝ 判定は `hourly` とオーナー）。"""
    _write(tmp_path, "2026-09-01-a", _NAMED)
    line = trend.hook_line([], tmp_path)
    # 「弱い」が出てよいのは、オーナーの原文を引いている所だけ（この口の判定ではない）
    assert line.count("弱い") == 1 and "「フックが弱い」" in line
    assert "良し悪しは `hourly` とオーナー" in line
    assert "`trend.hook_shape`" in line          # 数の出どころを名指しする
    # **数を写していないこと** —— 維持率の側の本数は、この行に書かず口の名で指す
    assert "`curve_aligned" in line


def test_門は形の門と同じ単位(tmp_path: Path):
    assert trend.HOOK_GATE == trend.SHAPE_GATE == 7


def test_台本が0本でも落ちない(tmp_path: Path):
    assert trend.hook_shape([], tmp_path)["n"] == 0
    assert trend.hook_line([], tmp_path)
