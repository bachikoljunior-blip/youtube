"""`scripts/owner_words.py` の見張り（オーナーの「分かりにくい」の連）。

**陽性対照で測ってあります** —— どの検査も、規則を 1つ 外すと落ちます
（§5 教訓の形 3つ目: 「在るか」で見る形は、畳んでも通ってしまう）。

**きょうの状態を不変条件に書かないこと**（§5 教訓の形 6つ目）——
実物の `data/inbox.jsonl` に当てる検査は「連が何日か」を書かず、
**門の定数から引く**か、**その場で作った台帳**で測ります。
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

ow = importlib.import_module("scripts.owner_words")


def _ledger(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "inbox.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    return p


def _row(at: str, rid: str, source: str = "owner", text: str = "x") -> dict:
    return {"at": at, "id": rid, "source": source, "text": text}


def test_オーナー以外の行は数えない(tmp_path: Path) -> None:
    """親の申し送りや道具の行が混ざっても、数えるのは `source == "owner"` だけ。"""
    rows = [
        _row("2026-09-13T10:00:00+09:00", "dd918e3f", source="parent"),
        _row("2026-09-13T11:00:00+09:00", "zzzz0001"),
    ]
    got = ow.owner_rows(_ledger(tmp_path, rows))
    assert [r["id"] for r in got] == ["zzzz0001"]
    # 陽性対照: 札の在る id でも、オーナーの行でなければ連に入らないこと
    assert ow.run(days_back=999, path=_ledger(tmp_path, rows))["run"] == 0


def test_沈黙の日は連を伸ばしも切りもしない(tmp_path: Path) -> None:
    """09/10・09/13 に族の言葉・その間はオーナーが 1言も言っていない ＝ 連は 2日。"""
    rows = [
        _row("2026-09-10T12:00:00+09:00", "552fadf1"),
        _row("2026-09-13T12:00:00+09:00", "2e87f87e"),
    ]
    res = ow.run(days_back=999, path=_ledger(tmp_path, rows))
    assert res["run"] == 2
    assert res["silent_in_run"] == 2  # 09/11・09/12 は沈黙


def test_言った日に族が無ければ連が切れる_陽性対照(tmp_path: Path) -> None:
    rows = [
        _row("2026-09-10T12:00:00+09:00", "552fadf1"),
        _row("2026-09-11T12:00:00+09:00", "f3edb61f"),
        _row("2026-09-12T12:00:00+09:00", "b8dab27b"),
    ]
    assert ow.run(days_back=999, path=_ledger(tmp_path, rows))["run"] == 3
    # まん中の日を「族でない言葉」に差し替えると、連は 1日 に落ちること
    rows[1] = _row("2026-09-11T12:00:00+09:00", "notaclarityid")
    assert ow.run(days_back=999, path=_ledger(tmp_path, rows))["run"] == 1


def test_門は定数から引く(tmp_path: Path) -> None:
    rows = [
        _row(f"2026-09-{9 + i:02d}T12:00:00+09:00", rid)
        for i, rid in enumerate(list(ow.CLARITY_IDS)[: ow.GATE])
    ]
    res = ow.run(days_back=999, path=_ledger(tmp_path, rows))
    assert res["run"] == ow.GATE and res["drawn"] is True
    # 1日 減らすと引かれないこと（陽性対照）
    res2 = ow.run(days_back=999, path=_ledger(tmp_path, rows[1:]))
    assert res2["run"] == ow.GATE - 1 and res2["drawn"] is False


def test_同じ日に族が2件でも連は1日(tmp_path: Path) -> None:
    """09/10 は 2件（`552fadf1`・`52f141fa`）—— 日で数えること。"""
    rows = [
        _row("2026-09-10T12:38:00+09:00", "552fadf1"),
        _row("2026-09-10T12:40:00+09:00", "52f141fa"),
    ]
    assert ow.run(days_back=999, path=_ledger(tmp_path, rows))["run"] == 1


def test_札の無い新しい言葉は必ず印字される(tmp_path: Path) -> None:
    """新しい言葉が黙って連を古くしないこと（§5 教訓の形 7つ目・17つ目）。"""
    rows = [
        _row("2026-09-13T12:00:00+09:00", "2e87f87e"),
        _row("2026-09-13T20:00:00+09:00", "newword1", text="まだ札の無い言葉"),
    ]
    res = ow.run(days_back=999, path=_ledger(tmp_path, rows))
    assert [r["id"] for r in res["unclassified"]] == ["newword1"]
    assert "newword1" in ow.line(res)


def test_族の言葉は全部_受け取り帳に在る() -> None:
    """`CLARITY_IDS` の id が実物の台帳から消えたら、この連は空を数えている。"""
    have = {r.get("id") for r in ow.owner_rows()}
    missing = [i for i in ow.CLARITY_IDS if i not in have]
    assert missing == [], f"受け取り帳に無い id: {missing}"
    assert ow.LOOP_ID in have


def test_印字は判定しないと言う() -> None:
    """optimizer は数を並べるまで（METHOD §5）—— 印字がそれを言い続けること。"""
    out = ow.line()
    assert "この道具は判定しません" in out
    assert "`hourly` とオーナー" in out


# ---- 読みの族（単位は「本」）と、申し送りの落とし（2026-09-13 15:0x に足した）----


def _ledger_books(tmp_path: Path, rows: list[dict]) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    p = tmp_path / "ledger.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    return p


def _sched(book: str, publish_at: str, *, old_shape: bool = False) -> dict:
    """`scheduled` の行。**古い形は `at` が公開の刻**・新しい形は `publish_at`。"""
    if old_shape:
        return {"at": publish_at, "id": book, "event": "scheduled", "video_id": "v" + book}
    return {"at": "2026-09-01T00:00:00+09:00", "publish_at": publish_at, "id": book,
            "event": "scheduled", "video_id": "v" + book}


def test_申し送りの日を_オーナーが言った日に数えない(tmp_path: Path) -> None:
    """`source: "owner"` の欄には親やサブの申し送りも入る —— 落とさないと連が偽で切れる。"""
    handoff = next(iter(ow.NOT_OWNER_IDS))
    rows = [
        _row("2026-09-10T12:00:00+09:00", "552fadf1"),
        _row("2026-09-11T12:00:00+09:00", handoff, text="【親からの申し送り】"),
        _row("2026-09-12T12:00:00+09:00", "b8dab27b"),
    ]
    assert ow.run(days_back=999, path=_ledger(tmp_path, rows))["run"] == 2
    # 陽性対照: 落とす側を外すと、申し送りだけの日が連を切る（1日 に落ちる）
    saved = dict(ow.NOT_OWNER_IDS)
    try:
        ow.NOT_OWNER_IDS.clear()
        assert ow.run(days_back=999, path=_ledger(tmp_path, rows))["run"] == 1
    finally:
        ow.NOT_OWNER_IDS.update(saved)


def test_読みの連は指摘のあとに公開した本だけを数える(tmp_path: Path) -> None:
    yomi = list(ow.YOMI_IDS)[-1]
    rows = [_row("2026-09-11T12:38:00+09:00", yomi)]
    led = _ledger_books(tmp_path / "led", [
        _sched("before-1", "2026-09-10T10:00+09:00"),
        _sched("before-2", "2026-09-11T10:00+09:00"),   # 指摘より前（同じ日でも刻で分ける）
        _sched("after-1", "2026-09-12T10:00+09:00"),
        _sched("after-2", "2026-09-13T10:00+09:00"),
    ])
    y = ow.run(days_back=999, path=_ledger(tmp_path, rows), ledger=led)["yomi"]
    assert [i for _t, i in y["after"]] == ["after-1", "after-2"]
    assert y["run"] == 2 and y["drawn"] is False


def test_読みの門は定数から引く(tmp_path: Path) -> None:
    yomi = list(ow.YOMI_IDS)[-1]
    rows = [_row("2026-09-01T12:00:00+09:00", yomi)]
    made = [_sched(f"b{i}", f"2026-09-{2 + i:02d}T10:00+09:00") for i in range(ow.YOMI_GATE_BOOKS)]
    y = ow.run(days_back=999, path=_ledger(tmp_path, rows),
               ledger=_ledger_books(tmp_path / "full", made))["yomi"]
    assert y["run"] == ow.YOMI_GATE_BOOKS and y["drawn"] is True
    # 陽性対照: 1本 減らすと引かれない
    y2 = ow.run(days_back=999, path=_ledger(tmp_path, rows),
                ledger=_ledger_books(tmp_path / "short", made[:-1]))["yomi"]
    assert y2["run"] == ow.YOMI_GATE_BOOKS - 1 and y2["drawn"] is False


def test_本の数えは_2つの形と差し替えと未来を扱う(tmp_path: Path) -> None:
    led = _ledger_books(tmp_path / "led", [
        _sched("old", "2026-09-06T10:00+09:00", old_shape=True),   # 古い形（`at` が公開の刻）
        _sched("dup", "2026-09-07T10:00+09:00"),
        _sched("dup", "2026-09-07T10:00+09:00"),                   # 差し替え ＝ 同じ本
        _sched("future", "2099-01-01T10:00+09:00"),                # まだ公開していない
    ])
    assert [i for _t, i in ow.books(led)] == ["old", "dup"]


def test_前の連は指摘と指摘のあいだの本を数える(tmp_path: Path) -> None:
    a, b = list(ow.YOMI_IDS)[0], list(ow.YOMI_IDS)[1]
    rows = [_row("2026-09-06T13:41:00+09:00", a), _row("2026-09-11T12:38:00+09:00", b)]
    led = _ledger_books(tmp_path / "led", [
        _sched(f"b{i}", f"2026-09-{7 + i:02d}T10:00+09:00") for i in range(5)  # 09/07〜09/11
    ])
    y = ow.run(days_back=999, path=_ledger(tmp_path, rows), ledger=led)["yomi"]
    assert [p["books"] for p in y["prev_runs"]] == [5]
    assert y["run"] == 0  # いちばん新しい指摘のあとは 0本


def test_2つの族に載る言葉は_もう片方の未分類に出ない(tmp_path: Path) -> None:
    """`3f4ef885` は 分かりにくさ と 読み の両方 —— 札の無い側にだけ並べること。"""
    both = [i for i in ow.YOMI_IDS if i in ow.CLARITY_IDS]
    assert both, "2つの族に載る言葉が 1つも無ければ、この検査は空を見ている"
    rows = [_row("2026-09-11T12:38:00+09:00", both[0]),
            _row("2026-09-12T12:00:00+09:00", "b8dab27b"),
            _row("2026-09-13T20:00:00+09:00", "newword9", text="まだ札の無い言葉")]
    res = ow.run(days_back=999, path=_ledger(tmp_path, rows))
    assert [r["id"] for r in res["yomi_unclassified"]] == ["newword9"]
    assert [r["id"] for r in res["unclassified"]] == ["newword9"]


def test_読みの印字も判定しないと言う() -> None:
    out = ow.line()
    assert "この道具は判定しません" in out
    assert "「読みが変」の連" in out


def test_読みの族の言葉は全部_受け取り帳に在る() -> None:
    have = {r.get("id") for r in ow.owner_rows()}
    missing = [i for i in ow.YOMI_IDS if i not in have]
    assert missing == [], f"受け取り帳に無い id: {missing}"
