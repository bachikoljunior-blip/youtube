"""外の作りを写す長尺の**冒頭 4コマ**が、外の上位4本の冒頭の型（結論の額 → 知らない側の損 → 名乗り →
視聴者への問い 2つ → 「最後まで」の約束）になっているかを数える検査と、[きょうの1本] の行
（2026-09-03 05:xx・最適化の回）。API 0単位。"""
from __future__ import annotations

import json
from pathlib import Path

from src import daily_pick, script_writer as sw

OLD = [
    "月給を下げなくても、止まっていた年金が年54万円ぶん止まらなくなります。止める側の線が動くだけで、この額です。",
    "いまは月4万5000円が止まっています。2026年4月からは0円です。",
    "対象は、働きながら厚生年金を受け取っていて、年金と給与の合計が51万円を超えている人です。",
    "この先の順番です。まず月給べつ、次に年金の額べつ、賞与がある人、繰下げをして待っている人です。",
]
NEW = [
    "2026年4月から、働きながら受け取る年金が、年54万円ぶん止まらなくなります。この変更を知らないままだと、月給を抑える働き方を続けてしまいます。",
    "こんにちは。お金と仕事の教科書です。今回は在職老齢年金の線について計算で出します。皆さん、年金の一部が止まっている通知を見たことはありませんか？",
    "いまは月4万5000円が止まっています。あなたの年金と給与の合計は、51万円のどちら側でしょうか？",
    "最後まで見れば、あなたの月給と年金の額で、4月からいくら止まらなくなるかを自分で出せます。それでは本題です。",
]


def _script(narrs: list[str]) -> dict:
    return {"segments": [{"narration": n, "visual": {"kind": "stat"}} for n in narrs]}


def test_前の冒頭は4件とも外れる():
    ps = sw.outside_opening_problems(_script(OLD))
    assert len(ps) == 4
    assert any("名乗り" in p for p in ps) and any("最後まで" in p for p in ps)


def test_外の型の冒頭は通る():
    assert sw.outside_opening_problems(_script(NEW)) == []


def test_問いが1つでは落ちる():
    narrs = list(NEW)
    narrs[2] = "いまは月4万5000円が止まっています。あなたの合計は51万円のどちら側かで変わります。"
    ps = sw.outside_opening_problems(_script(narrs))
    assert len(ps) == 1 and "問い" in ps[0]


def test_5コマ目以降は見ない():
    assert sw.outside_opening_problems(_script(OLD + NEW))
    assert sw.outside_opening_problems(_script(NEW + OLD)) == []


def test_outside_long_以外の題材には掛からない():
    assert sw._topic_style("no-such-topic-xyz") == ""


def _full(narrs: list[str]) -> str:
    segs = [{"narration": n, "visual": {"kind": "stat", "headline": "h", "stat": "", "note": "", "stat_source": "",
                                         "formula": "", "items": [], "headers": [], "rows": [], "bars": []}}
            for n in narrs]
    return json.dumps({"title": "t", "title_alternatives": [], "description_body": "d", "tags": [],
                       "thumbnail_line1": "a", "thumbnail_line2": "b", "first_comment": "c",
                       "segments": segs, "chapters": []}, ensure_ascii=False)


def test_控えが型の外で台本が型の中なら焼き直す手が出る(tmp_path: Path):
    (tmp_path / "data" / "critique_queue").mkdir(parents=True)
    (tmp_path / "data" / "scripts").mkdir(parents=True)
    (tmp_path / "data" / "critique_queue" / "VID00000001.script.json").write_text(_full(OLD), encoding="utf-8")
    (tmp_path / "data" / "scripts" / "topic-x.script.json").write_text(_full(NEW), encoding="utf-8")
    out = daily_pick.outside_opening_lines("VID00000001", "topic-x", root=tmp_path)
    joined = "\n".join(out)
    assert "型の外" in joined and "もう型の中" in joined
    assert "python -m src.pipeline --script data/scripts/topic-x.script.json --topic topic-x --dry-run" in joined
    assert "upload_only.py topic-x --draft --replaces VID00000001" in joined


def test_控えが型の中なら1行で済む(tmp_path: Path):
    (tmp_path / "data" / "critique_queue").mkdir(parents=True)
    (tmp_path / "data" / "critique_queue" / "VID00000002.script.json").write_text(_full(NEW), encoding="utf-8")
    out = daily_pick.outside_opening_lines("VID00000002", "topic-y", root=tmp_path)
    assert len(out) == 1 and "型の中" in out[0]


def test_両方型の外なら台本を直す手(tmp_path: Path):
    (tmp_path / "data" / "critique_queue").mkdir(parents=True)
    (tmp_path / "data" / "scripts").mkdir(parents=True)
    (tmp_path / "data" / "critique_queue" / "VID00000003.script.json").write_text(_full(OLD), encoding="utf-8")
    (tmp_path / "data" / "scripts" / "topic-z.script.json").write_text(_full(OLD), encoding="utf-8")
    out = daily_pick.outside_opening_lines("VID00000003", "topic-z", root=tmp_path)
    assert any("先に台本の冒頭 4コマ を直す" in x for x in out)


def test_何も無ければ空(tmp_path: Path):
    assert daily_pick.outside_opening_lines("VID00000004", "topic-w", root=tmp_path) == []


def test_実物の09_04の台本は型の中():
    f = Path("data/scripts/zaishoku-2026-62man.script.json")
    if not f.exists():
        return
    from src.script_writer import VideoScript
    assert sw.outside_opening_problems(VideoScript.model_validate_json(f.read_text(encoding="utf-8"))) == []
