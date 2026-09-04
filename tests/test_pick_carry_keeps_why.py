"""**焼き直しの写しは「決め」ではない** —— 2026-09-04 19:0x に踏んだ穴の検査。

`src/daily_pick.replace_video()` は、焼き直しで動画IDが変わったときに
決めを新しい ID へ写します。そこが長らく `why` を

    f"焼き直し: `{old}` → `{new}`（…）。前の決め: {前の why[:140]}"

と**前置き＋140字で切って**書き直していました。実測（`data/daily_pick.jsonl` 09-04T18:06）——
16:55 に回が数で書いた約400字の理由が「…処置を落と」で切れて残り、
次の回はそれを「前の回の散文（根拠にしない）」と読んで**同じ議論をゼロからやり直しました**。

いまは:
  - `why` は1文字も変えない
  - 写したことは `kind="carry"` / `rebaked_from` に残る
  - 鎖の長さ（`_standing_chain_len`）も、印字する理由も、**写しを飛ばす**
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from src import daily_pick as dp

JST = timezone(timedelta(hours=9))


def _rows(p):
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_写しは理由を1文字も変えない(tmp_path):
    p = tmp_path / "picks.jsonl"
    long_why = "この回の数で決め直した。門の AND は ショート ×106 対 長尺 ×314 で、" + "根拠の続き。" * 40
    assert len(long_why) > 140
    dp.record("長尺", "topic-a", long_why, day=date(2026, 9, 5),
              now=datetime(2026, 9, 4, 16, 55, tzinfo=JST), path=p, video_id="OLD")
    dp.replace_video(["OLD"], "NEW", now=datetime(2026, 9, 4, 18, 6, tzinfo=JST), path=p)
    rows = _rows(p)
    assert len(rows) == 2
    assert rows[1]["video_id"] == "NEW"
    assert rows[1]["why"] == long_why          # ← 切らない・前置きしない
    assert rows[1]["kind"] == dp.PICK_KIND_CARRY
    assert rows[1]["rebaked_from"] == "OLD"


def test_決めの行は決めとして残る(tmp_path):
    p = tmp_path / "picks.jsonl"
    dp.record("ショート", "t", "数 12 で決めた", day=date(2026, 9, 5), path=p, video_id="A")
    rows = _rows(p)
    assert rows[0]["kind"] == dp.PICK_KIND_DECIDE
    assert dp.pick_kind(rows[0]) == dp.PICK_KIND_DECIDE


def test_鎖は写しを数えない(tmp_path):
    p = tmp_path / "picks.jsonl"
    for i in range(3):
        dp.record("長尺", "t", f"数 {i} で決めた", day=date(2026, 9, 3 + i), path=p, video_id=f"V{i}")
        dp.replace_video([f"V{i}"], f"W{i}", path=p)
    assert len(_rows(p)) == 6
    assert dp._standing_chain_len(p) == 3      # 決めだけ


def test_欄の無い古い写しも写しとして読む():
    # 2026-09-04 より前の行には `kind` が無い。`why` の頭で見分ける
    assert dp.pick_kind({"why": "焼き直し: `AAA` → `BBB`（1本）。前の決め: …"}) == dp.PICK_KIND_CARRY
    assert dp.pick_kind({"why": "この回の数で決めた（12本）"}) == dp.PICK_KIND_DECIDE
    assert dp.pick_kind({}) == dp.PICK_KIND_DECIDE


def test_last_decided_は写しを飛ばす(tmp_path):
    p = tmp_path / "picks.jsonl"
    dp.record("長尺", "t", "決めの理由 1件", day=date(2026, 9, 5), path=p, video_id="A")
    dp.replace_video(["A"], "B", path=p)
    dec = dp.last_decided(_rows(p))
    assert dec["video_id"] == "A" and dec["why"] == "決めの理由 1件"


def test_実物の帳面に写しが在り決めと分かれている():
    rows = list(dp._jsonl(dp.PICKS))
    assert rows, "data/daily_pick.jsonl が空"
    kinds = {dp.pick_kind(r) for r in rows}
    assert dp.PICK_KIND_CARRY in kinds, "実物に写しの行が 1件も無い（見分けが効いていない）"
    assert dp._standing_chain_len() < len(rows)
