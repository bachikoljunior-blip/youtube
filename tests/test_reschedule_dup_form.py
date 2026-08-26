"""**「二重予約」の判定に、形式を入れる**（受け取り帳 `c23c90a9`・親の申し送り 08/24）。

`reschedule.py --list` はテーマIDだけで数えていて、実物にこう出ました:

    08/26 14:00  cFZd55jRxAw  長尺    65歳で年180万円 繰下げで元が取れる最後は何歳か
    09/05 12:00  rRYgdX9GFJA  ショート 85歳まで生きるなら繰下げは何歳まで得か #Shorts

**10日 離れ・形式ちがい・切り口ちがい。** `CLAUDE.md` が明記している
「長尺1本から何本も切り出せる」の形そのものです。
ところが `--list` は「**片方を外すこと**」と印字していました ——
**その指示に従うと、正しい在庫を捨てます。**

ここで固定するのは3つ:

1. **同じ形式で2本** → 今までどおり「二重」と言い、片方を外せと言う
2. **形式がちがう2本** → 「形式ちがい」と言い、**外すなとはっきり書く**
3. 形式は `src.forms.classify()` に任せる（実測 → 秒数 → `#Shorts` の札）
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

from scripts import reschedule  # noqa: E402


def _row(vid: str, topic: str, title: str, at: str) -> dict:
    return {"id": vid, "topic": topic, "title": title, "at": at}


def _no_ledger(monkeypatch) -> None:
    from src import dupes, forms

    monkeypatch.setattr(dupes, "ledger_rows", lambda: [])
    monkeypatch.setattr(forms, "measured_forms", lambda: {})


def test_形式がちがう組は_外すなと言う(monkeypatch, capsys):
    """**この検査が、この直しの理由そのものです。**"""
    _no_ledger(monkeypatch)
    reschedule._show([
        _row("cFZd55jRxAw", "s-nenkin-1",
             "65歳で年180万円 繰下げで元が取れる最後は何歳か", "2026-08-26T05:00:00Z"),
        _row("rRYgdX9GFJA", "s-nenkin-1",
             "85歳まで生きるなら繰下げは何歳まで得か #Shorts", "2026-09-05T03:00:00Z"),
    ])
    out = capsys.readouterr().out
    assert "形式がちがいます" in out
    assert "**外さないこと。**" in out
    # **「片方を外すこと」を言わないこと** —— 正しい在庫を捨てさせる
    assert "片方を外すこと" not in out


def test_同じ形式で2本なら_今までどおり二重と言う(monkeypatch, capsys):
    _no_ledger(monkeypatch)
    reschedule._show([
        _row("aaaaaaaaaaa", "s-nenkin-1", "繰下げの損得 #Shorts", "2026-08-26T05:00:00Z"),
        _row("bbbbbbbbbbb", "s-nenkin-1", "繰下げの分かれ目 #Shorts", "2026-09-05T03:00:00Z"),
    ])
    out = capsys.readouterr().out
    assert "同じテーマ・同じ形式が2本以上" in out
    assert "片方を外すこと" in out
    assert "形式がちがいます" not in out


def test_重なりが無ければ何も言わない(monkeypatch, capsys):
    _no_ledger(monkeypatch)
    reschedule._show([
        _row("aaaaaaaaaaa", "s-nenkin-1", "繰下げの損得 #Shorts", "2026-08-26T05:00:00Z"),
        _row("bbbbbbbbbbb", "s-iryohi-1", "医療費の分かれ目 #Shorts", "2026-09-05T03:00:00Z"),
    ])
    out = capsys.readouterr().out
    assert "二重予約はありません。" in out


def test_形式は秒数からも決まる(monkeypatch, capsys):
    """題名に `#Shorts` が無い本でも、控えの秒数で分かれること。"""
    from src import dupes, forms

    monkeypatch.setattr(forms, "measured_forms", lambda: {})
    monkeypatch.setattr(dupes, "ledger_rows", lambda: [
        {"video_id": "aaaaaaaaaaa", "duration_s": 310.0},   # 長尺
        {"video_id": "bbbbbbbbbbb", "duration_s": 42.0},    # ショート
    ])
    reschedule._show([
        _row("aaaaaaaaaaa", "s-nenkin-1", "繰下げの損得", "2026-08-26T05:00:00Z"),
        _row("bbbbbbbbbbb", "s-nenkin-1", "繰下げの分かれ目", "2026-09-05T03:00:00Z"),
    ])
    out = capsys.readouterr().out
    assert "形式がちがいます" in out, out
    assert "片方を外すこと" not in out
