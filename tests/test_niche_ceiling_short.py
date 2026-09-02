"""**外の帯の「毎日 出している形（ショート）」の数が、主実行の画面に届くこと。**（2026-09-02 夜・最適化の回）

09/02 昼の `niche_ceiling.py` は長尺 25本／ショート 0本 で、「天井は鏡か」の判定は
ショートの外の数を1つも見ていなかった。同日 23:1x にショートを撃ったら 5語 全部 429 で、
道具は n=0 を帳面に書き「帯そのものが天井」と印字した。ここはその2つを検査する:

    1. 429 の回は帳面に書かない・「撃てていない」と言う
    2. 帳面にショートが無い回、`[きょうの1本]` は撃つ手（`--form short`）を出す
    3. 在る回は、外の最大／中央と上位の題が同じ画面に出る
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import niche_ceiling as nc                                      # noqa: E402
from src import daily_pick                                      # noqa: E402


def _ledger(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "niche_ceiling.jsonl"
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return p


def _row(at: str, short_n: int, top: list[dict] | None = None) -> dict:
    return {
        "at": at, "queries": ["a", "b"], "days": 365, "n": short_n + 3,
        "summary": {"short": ({"n": short_n, "max": 900000, "p90": 120000, "median": 30000,
                               "channels": 7} if short_n else {"n": 0}),
                    "long": {"n": 3, "max": 5000, "p90": 4000, "median": 3000, "channels": 3}},
        "own_ceiling": 4229.0, "top": top or [],
    }


def test_latest_by_form_skips_rows_with_none_of_that_form(tmp_path: Path) -> None:
    p = _ledger(tmp_path, [_row("2026-09-02T08:48:43+00:00", 4),
                           _row("2026-09-02T15:12:49+00:00", 0)])
    assert nc.latest(p)["at"].startswith("2026-09-02T15")
    assert nc.latest(p, form="short")["at"].startswith("2026-09-02T08")
    (tmp_path / "x").mkdir()
    assert nc.latest(_ledger(tmp_path / "x", [_row("2026-09-02T15:12:49+00:00", 0)]),
                     form="short") is None


def test_all_429_says_not_shot_and_writes_nothing(tmp_path: Path, monkeypatch) -> None:
    p = tmp_path / "ledger.jsonl"
    monkeypatch.setattr(nc, "LEDGER", p)
    monkeypatch.setattr(nc, "probe", lambda qs, days=365, form="any": {
        "rows": [], "own": "", "queries": qs, "days": days, "form": form, "denied": len(qs)})
    monkeypatch.setattr(nc, "own_ceiling", lambda: 4229.0)
    rc = nc.main(["--form", "short", "--queries", "3"])
    assert rc == 2
    assert not p.exists()
    text = "\n".join(nc.denied_lines({"denied": 3}))
    assert "撃てていない" in text and "16:00 JST" in text and "帳面には書きません" in text


def test_top_lines_show_outside_max_ratio_and_titles(tmp_path: Path) -> None:
    top = [{"id": "x1", "views": 900000, "secs": 40, "form": "short", "title": "年金の手取り"},
           {"id": "x2", "views": 5000, "secs": 600, "form": "long", "title": "長尺"},
           {"id": "x3", "views": 300000, "secs": 25, "form": "short", "title": "医療費控除"}]
    p = _ledger(tmp_path, [_row("2026-09-03T08:00:00+00:00", 30, top)])
    now = datetime(2026, 9, 4, tzinfo=timezone.utc)
    got = nc.top_lines("short", path=p, now=now, own_median=1049)
    text = "\n".join(got)
    assert "最大 **900,000回**" in text and "中央 30,000回" in text
    assert "×28.6" in text                      # 30,000 / 1,049
    assert "年金の手取り" in text and "医療費控除" in text and "長尺" not in text
    assert nc.top_lines("short", path=p, now=datetime(2026, 11, 1, tzinfo=timezone.utc)) == []


def test_daily_pick_prints_the_shot_when_the_form_is_missing(tmp_path: Path) -> None:
    p = _ledger(tmp_path, [_row("2026-09-02T08:48:43+00:00", 0)])
    cmp = {"rule": {"ショート": {"median": 1049}}, "all": {"ショート": {"median": 173}}}
    got = daily_pick.outside_lines(cmp, "ショート", ledger=p)
    text = "\n".join(got)
    assert "まだ 1本も撃てていません" in text
    assert "python scripts/niche_ceiling.py --form short" in text


def test_daily_pick_prints_the_numbers_when_the_form_is_there(tmp_path: Path) -> None:
    top = [{"id": "x1", "views": 900000, "secs": 40, "form": "short", "title": "年金の手取り"}]
    p = _ledger(tmp_path, [_row("2026-09-03T08:00:00+00:00", 30, top)])
    cmp = {"rule": {"ショート": {"median": 1049}}, "all": {"ショート": {"median": 173}}}
    got = daily_pick.outside_lines(cmp, "ショート", ledger=p,
                                   now=datetime(2026, 9, 3, 12, tzinfo=timezone.utc))
    text = "\n".join(got)
    assert "撃てていません" not in text
    assert "900,000回" in text and "年金の手取り" in text and "1,049回" in text
