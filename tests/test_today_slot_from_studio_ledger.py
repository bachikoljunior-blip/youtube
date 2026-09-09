"""「きょうの枠が空か」を、**生きている台帳**から数えているか。

実測 2026-09-09 09:0x JST（optimizer・Opus）: `sibling_check.today_slot_empty()` は
`src/next_slot.today_count()` ＝ `data/uploaded.jsonl` を読んでいた。**その控えは
2026-09-05 15:01 を最後に1行も増えていない** —— 同じ日にオーナーの
「今の手法全てまっさらにして」で道具が `studio/` へ組み直され、新しい道具は
この控えを書かないため。＝ 分子が**毎日 0** になり、この関数は **4日間ずっと
「まだ空です」**と答え、`--phase spawn` は**間隔の下限を毎周 外し続けて**いた。

`tests/test_spawn_gate_overrun.py` の2件は、その **4日間ずっと赤**だった
（畳む枝を測るはずが、下限が外れて「立ててよい」に落ちていた）。
**検査は鳴っていた。読む側が居なかった。**

ここで止めるのは「**読めなかったのに『空です』と答える**」形そのもの。
"""
import datetime as dt
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 9, 9, 8, 44, tzinfo=JST)


def _mod():
    spec = importlib.util.spec_from_file_location(
        "sibling_check_for_slot", ROOT / "scripts" / "sibling_check.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _ledger(tmp_path, rows):
    p = tmp_path / "ledger.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                 encoding="utf-8")
    return p


SCHEDULED_TODAY = {
    "event": "scheduled", "id": "2026-09-09-kakyu", "video_id": "TODAY1",
    "publish_at": "2026-09-09T10:00+09:00", "at": "2026-09-09T00:33:27+09:00",
    "title": "きょうの本",
}


def test_きょうの本が置かれていれば空ではない(tmp_path, monkeypatch):
    m = _mod()
    monkeypatch.setattr(m, "STUDIO_LEDGER", _ledger(tmp_path, [SCHEDULED_TODAY]))
    assert m.today_slot_empty(NOW) is False


def test_きのうの本しか無ければ空(tmp_path, monkeypatch):
    m = _mod()
    row = dict(SCHEDULED_TODAY, video_id="YDAY", publish_at="2026-09-08T10:00+09:00")
    monkeypatch.setattr(m, "STUDIO_LEDGER", _ledger(tmp_path, [row]))
    assert m.today_slot_empty(NOW) is True


def test_置いたあと_privateへ戻した本は枠を埋めていない(tmp_path, monkeypatch):
    m = _mod()
    rows = [SCHEDULED_TODAY,
            {"event": "unscheduled", "id": "TODAY1", "at": "2026-09-09T01:00:00+09:00",
             "reason": "旧 publishAt が発火したので戻した"}]
    monkeypatch.setattr(m, "STUDIO_LEDGER", _ledger(tmp_path, rows))
    assert m.today_slot_empty(NOW) is True


def test_読めなければ_空ですと答えない(tmp_path, monkeypatch):
    """**これがこの回に踏んだ形。** 読めないときは `None`（＝ 呼び手は下限を効かせる）。"""
    m = _mod()
    monkeypatch.setattr(m, "STUDIO_LEDGER", tmp_path / "no-such-file.jsonl")
    assert m.today_slot_empty(NOW) is None


def test_死んだ控えを読んでいないこと():
    """`data/uploaded.jsonl` は 09/05 で止まっている。**そこを見に行かないこと。**"""
    import ast

    src = (ROOT / "scripts" / "sibling_check.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    code = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in (
                # `_studio_ledger` は 2026-09-10 00:0x に割った口（環境変数で台帳の道を
                # 上書きできる ＝ 子プロセスの検査が「きょうの枠」を固定できる）。
                # **割った先も、この検査の中に入れておくこと** —— でないと
                # 「死んだ控えへ戻っていないか」を見ている面が、割った側で抜けます。
                "today_slot_empty", "_studio_today_slot_empty", "_studio_ledger"):
            body = list(node.body)
            # **註で名前を出すのは良い**（なぜやめたかの説明）。見るのは**動く側**だけ。
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                body = body[1:]
            code += [ast.unparse(n) for n in body]
    code = "\n".join(code)
    assert code, "関数が見つかりません"
    for banned in ("next_slot", "uploaded"):
        assert banned not in code, f"死んだ控えへ戻っています: {banned}"
    assert "STUDIO_LEDGER" in code


def test_本物の台帳で読める():
    """実物の `data/studio/ledger.jsonl` で、`None` ではない答えが出ること。"""
    m = _mod()
    got = m.today_slot_empty()
    if not m.STUDIO_LEDGER.exists():
        pytest.skip("台帳がまだ無い")
    assert got in (True, False), got
