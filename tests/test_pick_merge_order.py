"""**併合で行が入れ替わると、その日の1本が古い本に戻っていた** —— 2026-09-04 19:3x に踏んだ検査。

`data/daily_pick.jsonl` は `merge=union` で、**同じ枝を複数の回が同時に走ります**。
併合すると行はファイルの中で時刻順に並びません。実測::

    19:30:50  carry   e6sLHLmPhrk   ← 焼き直しが差し替えた新しい本
    19:24:02  decide  XwB8nxtN5D8   ← 別の回が 6分前に書いた行（併合で後ろに来た）

`current()` は「ファイルの最後の行」を返していたので、**差し替えたはずの古い本**を
「09/05 の1本」として返していました。`ahead_sweep._today_candidate` はその ID を
そのまま枠へ置くので、**62分 かけて焼いた本は池に眠り、直す前の本が公開されます。**
`replace_video()` が塞いだはずの穴が、**併合の並びから開き直した**もの。
"""
from __future__ import annotations

import json
from datetime import date

from src import daily_pick as dp

DAY = "2026-09-05"


def _write(p, rows):
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                 encoding="utf-8")


def _row(at, vid, kind=dp.PICK_KIND_DECIDE, why="数 1", exp=None, frm=""):
    return {"at": at, "for_day": DAY, "form": "長尺", "topic": "t", "video_id": vid,
            "why": why, "expected_48h": exp, "kind": kind, "rebaked_from": frm,
            "session": ""}


def test_併合で古い行が後ろに来ても最新の決めを返す(tmp_path):
    p = tmp_path / "picks.jsonl"
    _write(p, [
        _row("2026-09-04T18:39:50+09:00", "XwB8nxtN5D8", exp=8.0),
        _row("2026-09-04T19:30:50+09:00", "e6sLHLmPhrk", kind=dp.PICK_KIND_CARRY,
             exp=8.0, frm="XwB8nxtN5D8"),
        _row("2026-09-04T19:24:02+09:00", "XwB8nxtN5D8"),   # ← 併合で最後に来た古い行
    ])
    cur = dp.current(date(2026, 9, 5), p)
    assert cur["video_id"] == "e6sLHLmPhrk", "差し替えた新しい本を返すこと"
    assert cur["at"] == "2026-09-04T19:30:50+09:00"


def test_理由は_at_のいちばん新しい決めから引く(tmp_path):
    p = tmp_path / "picks.jsonl"
    _write(p, [
        _row("2026-09-04T18:39:50+09:00", "A", why="古い理由 1件"),
        _row("2026-09-04T19:24:02+09:00", "A", why="新しい理由 2件"),
    ])
    rows = list(dp._jsonl(p))
    rows = [rows[1], rows[0]]                                # 併合で並びが逆
    assert dp.last_decided(rows)["why"] == "新しい理由 2件"


def test_見込みの実物は_at_で最新のIDから引く(tmp_path):
    p = tmp_path / "picks.jsonl"
    _write(p, [
        _row("2026-09-04T18:39:50+09:00", "OLD", exp=8.0),
        _row("2026-09-04T19:30:50+09:00", "NEW", kind=dp.PICK_KIND_CARRY,
             exp=8.0, frm="OLD"),
        _row("2026-09-04T19:24:02+09:00", "OLD"),            # 併合で最後に来た古い行
    ])
    aged = [{"video_id": "OLD", "views": 3}, {"video_id": "NEW", "views": 42}]
    body = "\n".join(dp.expected_lines(picks_path=p, aged_call=lambda *a, **k: aged))
    assert "見込み 8回 → 実物 42回" in body
    assert "実物 3回" not in body


def test_写しも_at_で並べてから当てる(tmp_path):
    """`replace_video()` は「その日の最後の決め」の ID を見る。そこも `at` 順。"""
    p = tmp_path / "picks.jsonl"
    _write(p, [
        _row("2026-09-04T19:24:02+09:00", "B"),
        _row("2026-09-04T18:39:50+09:00", "A"),              # 併合で後ろに来た古い行
    ])
    assert dp.replace_video(["A"], "C", path=p) == []        # 最新は B なので当たらない
    assert dp.replace_video(["B"], "C", path=p) == [DAY]
    assert dp.current(date(2026, 9, 5), p)["video_id"] == "C"


def test_読めない_at_の行はファイルの並びのまま後ろへ(tmp_path):
    p = tmp_path / "picks.jsonl"
    _write(p, [
        _row("2026-09-04T19:30:50+09:00", "NEW"),
        _row("こわれた日付", "BROKEN"),
    ])
    assert dp.current(date(2026, 9, 5), p)["video_id"] == "BROKEN"
    rows = dp._by_at(list(dp._jsonl(p)))
    assert [r["video_id"] for r in rows] == ["NEW", "BROKEN"]


def test_あとの決めが黙っても宣言は消えない(tmp_path):
    """**数を消せるのは、別の数だけ**（`--moves` と同じ）。

    実測 09-04: 18:39 に 8回 を宣言した決めを、19:24 の別の回が `--expected` 無しで
    上書きしました。その日のいちばん新しい決めだけを見ると、**宣言は黙って消えます**
    ＝ 宣言した回が採点を逃れられる。
    """
    p = tmp_path / "picks.jsonl"
    _write(p, [
        _row("2026-09-04T18:39:50+09:00", "A", exp=8.0),
        _row("2026-09-04T19:24:02+09:00", "A"),               # --expected 無しの決め直し
    ])
    aged = [{"video_id": "A", "views": 4}]
    body = "\n".join(dp.expected_lines(picks_path=p, aged_call=lambda *a, **k: aged))
    assert "見込み 8回 → 実物 4回" in body


def test_形を変えた決めは前の見込みを引き継がない(tmp_path):
    """形が変われば、その見込みはもう別の話。"""
    p = tmp_path / "picks.jsonl"
    rows = [
        _row("2026-09-04T18:39:50+09:00", "A", exp=8.0),
        _row("2026-09-04T19:24:02+09:00", "A"),
    ]
    rows[1]["form"] = "ショート"
    _write(p, rows)
    aged = [{"video_id": "A", "views": 4}]
    body = "\n".join(dp.expected_lines(picks_path=p, aged_call=lambda *a, **k: aged))
    assert "1件も言っていません" in body
