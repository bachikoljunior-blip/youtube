"""**段2 の面を、カレンダーではなく「公開の予定」で読む。**（2026-08-26 に足した）

## この検査が守っているもの

`data/reach.jsonl` の実測（2026-08-26）:

    08/17  5 ／ 08/18  7 ／ 08/19  8 ／ 08/20 17 ／ 08/21 1,368 ／ 08/22 335 ／ 08/23 492

`per_day_sustained` は直近7日の**中央値 17.0回/日**を返し、`scripts/eta.py` の段2 は
それを読んで「**10.5倍 足りません。足りないのはインプレッションで、サムネと題では
動きません**」と印字していました。**その7日のうち5日は、長尺の公開が0本です。**

公開が0本の日の面を「続いている量」と呼ぶと、測っているのは
**「公開を止めたら面はいくつか」**であって、段2 の問い
（門2a を 450日 かけて開けられるか）の答えではありません。

**予定はこちらの手元にあります**（`data/uploaded.jsonl` の `at`）。だから
「これから7日で長尺を何本 公開するか」は API を1単位も使わずに数えられ、
面は `公開1本あたり × 本/日` で出ます（実測 279.0 × 2.43 ＝ **677.6回/日**）。

**中央値のほうは消していません** —— どちらも正しく、**問いが別**だからです。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import reach_split as R  # noqa: E402


def _ledger(tmp_path, rows):
    p = tmp_path / "uploaded.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows),
                 encoding="utf-8")
    return p


def _batch(tmp_path, rows):
    p = tmp_path / "batch_runs.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows),
                 encoding="utf-8")
    return p


def test_作った帳面から長尺のIDを拾う(tmp_path):
    """**`long: true` の回の `results[].video_id` が長尺。**

    `data/video_forms.json` は「YouTube が分類し終えた本」しか持たないので、
    **これから公開する本が1本も入りません。**
    """
    p = _batch(tmp_path, [
        {"long": True, "results": [{"video_id": "L1"}, {"video_id": "L2"}]},
        {"long": False, "results": [{"video_id": "S1"}]},
        {"long": True, "results": [{"video_id": None}, {"video_id": "L3"}]},
    ])
    assert R.built_long_ids(p) == {"L1", "L2", "L3"}


def test_帳面が無ければ空_いままでと同じ答え(tmp_path):
    assert R.built_long_ids(tmp_path / "no-such.jsonl") == set()


def test_公開本数の取り違えが直る(tmp_path):
    """**分母が小さいほど「1本あたりよく回っている」と出ます。**

    測り漏らすほど面は足りているように見えるので、向きが悪い側の誤りです。
    """
    batch = _batch(tmp_path, [{"long": True, "results": [
        {"video_id": "L1"}, {"video_id": "L2"}]}])
    ledger = _ledger(tmp_path, [
        {"video_id": "L1", "at": "2026-08-21T00:00:00Z"},
        {"video_id": "L2", "at": "2026-08-21T01:00:00Z"},
    ])
    # 測った控えには L1 しか載っていない（L2 はまだ再生0）
    forms = tmp_path / "video_forms.json"
    forms.write_text(json.dumps({"forms": {"L1": "長尺"}}), encoding="utf-8")
    pairs = tmp_path / "pairs.yaml"
    pairs.write_text("pairs: {}\n", encoding="utf-8")

    only_measured = R.publishes_per_day({"L1"}, ledger)
    both = R.publishes_per_day(R.long_ids(pairs, forms, batch), ledger)
    assert only_measured["20260821"] == 1
    assert both["20260821"] == 2


def test_予定から面を出す_穴も名指しする(tmp_path):
    """**これが本体。** 面は「公開1本あたり × これからの本/日」。

    そして**予定表の穴**（長尺 0本の連なり）を名指しすること ——
    面が公開で立つ以上、そこで面は保ちません。
    """
    sm = {"長尺": {"per_publish": 200.0}}
    pubs = {"20260826": 2, "20260827": 2, "20260828": 0, "20260829": 0,
            "20260830": 0, "20260831": 1, "20260901": 2}
    ledger = _ledger(tmp_path, [{"video_id": "x", "at": "2026-09-01T00:00:00Z"}])
    keep = R.LEDGER
    try:
        R.LEDGER = ledger
        got = R.surface_forecast(sm, pubs, days=7, today="2026-08-26")
    finally:
        R.LEDGER = keep
    assert got is not None
    # 7本 ÷ 7日 ＝ 1.0本/日 × 200回 ＝ 200回/日
    assert round(got["pubs_per_day"], 3) == 1.0
    assert round(got["per_day_planned"], 1) == 200.0
    # 穴は 08/28〜08/30 の3日（予定表の続いている範囲の中だけを見る）
    assert R.last_scheduled_day(ledger) == "20260901"
    assert got["dry_span"] == ("20260828", "20260830", 3)


def test_予約の切れた先を穴と呼ばない(tmp_path):
    """**控えの最後より先は「長尺0本」ではなく「まだ何も置いていない」。**

    混ぜると、いちばん長い連なりは必ずそこになります
    （実測 2026-08-26: 10/06〜10/24 の19日 ＝ 控えの終わり 10/13 の先）。
    予約が切れていること自体は `status.py`「予約の先」が別に鳴らします。
    """
    sm = {"長尺": {"per_publish": 100.0}}
    pubs = {"20260826": 1, "20260827": 1}
    ledger = _ledger(tmp_path, [{"video_id": "x", "at": "2026-08-27T00:00:00Z"}])
    monkey = R.LEDGER
    try:
        R.LEDGER = ledger
        got = R.surface_forecast(sm, pubs, days=2, today="2026-08-26")
    finally:
        R.LEDGER = monkey
    assert got is not None
    assert got["last_scheduled"] == "20260827"
    # 08/26・08/27 は両方とも長尺があるので、穴は無い
    assert got["dry_days"] == []
    assert got["dry_span"] is None


def test_公開1本あたりが無ければ出さない():
    """**推測で埋めない。** 測れていないときは `None`（回は止めない）。"""
    assert R.surface_forecast({"長尺": {}}, {}, days=7, today="2026-08-26") is None
