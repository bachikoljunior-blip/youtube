"""**`expected_48h` は書かれるだけで、どこも読んでいなかった** —— 2026-09-04 19:2x に足した検査。

`src/daily_pick.record()` は最初からこの欄を書いています。`grep expected` の当たりは
引数・書く行・`replace_video()` が写す行の **3か所だけ**で、実物と並べる口が1つもなく、
実測 `data/daily_pick.jsonl` 22行 の `expected_48h` は **全部 null** でした。
＝ 欄の名前だけが「見込みを立てて後で答え合わせする」と言っている状態。

いまは `expected_lines()` が並べ、`--expected` で言えます。
"""
from __future__ import annotations

from datetime import date

from src import daily_pick as dp


def _pick(p, day, vid, exp=None, form="長尺"):
    dp.record(form, "t", "数 1 で決めた", day=day, path=p, video_id=vid, expected=exp)


def test_1件も言っていなければ名指しする(tmp_path):
    p = tmp_path / "picks.jsonl"
    _pick(p, date(2026, 9, 5), "A")
    out = dp.expected_lines(picks_path=p, aged_call=lambda *a, **k: [])
    assert len(out) == 1 and "1件も言っていません" in out[0]
    assert "--expected" in out[0]


def test_見込みと実物を並べる(tmp_path):
    p = tmp_path / "picks.jsonl"
    _pick(p, date(2026, 9, 3), "A", exp=100.0)
    _pick(p, date(2026, 9, 4), "B", exp=10.0)
    aged = [{"video_id": "A", "views": 50}, {"video_id": "B", "views": 20}]
    out = dp.expected_lines(picks_path=p, aged_call=lambda *a, **k: aged)
    body = "\n".join(out)
    assert "見込み 100回 → 実物 50回" in body and "×0.50" in body
    assert "見込み 10回 → 実物 20回" in body and "×2.00" in body
    assert "中央" in body


def test_齢48hに届いていない本は待ちに出る(tmp_path):
    p = tmp_path / "picks.jsonl"
    _pick(p, date(2026, 9, 5), "A", exp=8.0)
    out = dp.expected_lines(picks_path=p, aged_call=lambda *a, **k: [])
    body = "\n".join(out)
    assert "待ち" in body and "まだ 齢48h ではありません" in body


def test_同じ日の最後の決めだけを見る(tmp_path):
    p = tmp_path / "picks.jsonl"
    _pick(p, date(2026, 9, 5), "A", exp=1000.0)
    _pick(p, date(2026, 9, 5), "A", exp=8.0)          # 決め直し
    aged = [{"video_id": "A", "views": 4}]
    body = "\n".join(dp.expected_lines(picks_path=p, aged_call=lambda *a, **k: aged))
    assert "見込み 8回" in body and "1,000回" not in body


def test_写しの行は見込みの持ち主にならない(tmp_path):
    p = tmp_path / "picks.jsonl"
    _pick(p, date(2026, 9, 5), "A", exp=8.0)
    dp.replace_video(["A"], "B", path=p)               # 焼き直しの写し
    aged = [{"video_id": "A", "views": 4}, {"video_id": "B", "views": 99}]
    body = "\n".join(dp.expected_lines(picks_path=p, aged_call=lambda *a, **k: aged))
    # 決めが名指ししているのは A。写しの B ではない
    assert "実物 4回" in body and "99回" not in body


def test_CLI_に見込みの口が在る():
    import subprocess
    import sys
    r = subprocess.run([sys.executable, "-m", "src.daily_pick", "--help"],
                       capture_output=True, text=True, timeout=120)
    assert "--expected" in r.stdout
