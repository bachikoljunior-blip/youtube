"""**`--video` の1本が、穴の門で止められていないこと**（2026-09-01 に踏んだ）。

## 何が起きていたか（実測）

`src/next_slot.py` が §1 の印で、毎周この1行を名指しで印字します:

    python scripts/refresh_thumbnail.py --missing --video UIWHsypOPPg
    （枠が戻る 09/01 16:00 JST → 公開 22:00 JST ＝ 猶予6時間・**50単位**）

**その1行は、そのままでは1本も押しませんでした。**
`push_missing()` の門は

    if not force and not only_long:
        okay, line = upload_cap.thumbnail_yield_to_schedule(...)

で、**`only_video` が抜けています**。実測 2026-09-01 05:5x の
`upload_cap.schedule_holes()` は **9日**（09/03〜09/11）を返すので、
門は `okay=False` を返し、`push_missing()` は **3** を返して終わります。

## なぜ「穴を優先」が、この1本では逆さまになるか

門は**値段の比べ**です（`thumbnail_yield_to_schedule` の本文）——
「サムネイル 158本 ＝ 7,900単位 を、穴 9日 ＝ 450単位 の移動に譲れ」。
**`--video` は 50単位**なので、**止めているほうが 9分の1 安い。**
譲る先が、そもそも存在しません。

そして**穴には締切がありません**（いちばん早い 09/03 でも2日先）。
**この1本には 16時間 しかありません。** 門は値段しか見ないので、
締切の差は式のどこにも入っていませんでした。

## **`--force` を書き足す形では直っていません**

手順の側は既に「必ず `--video` を付けること」と書いていました。
`tests/test_thumbnail_order.py` の本文がその結末を書いています ——
**「撃つ側が思い出したときにしか効かない」**
（`batch_build.slots()`「人の記憶と手写しに依存する門は、この輪では
毎回落ちる側」）。だから**門の側**を直します。

**覆る条件**: `--video` が2本以上を受けるようになったら、
`len(rows) * 50 < 穴の数 * 50` の比べに直すこと。
1本のあいだは、その比べは必ず通ります。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import refresh_thumbnail as rt  # noqa: E402
from src import upload_cap as uc  # noqa: E402


class _Quota:
    """日枠は開いている、という返り（`upload_cap.day_quota()` の形）。"""

    open = True
    line = "（検査）"


def _stub_rows(monkeypatch, ids):
    import critique_queue

    monkeypatch.setattr(
        critique_queue, "missing_thumbnail",
        lambda: [{"video_id": v, "topic": v, "thumb": ROOT / "README.md",
                  "stashed_at": None} for v in ids],
    )


def _stub_common(monkeypatch, calls):
    """門の**手前**は全部 通し、門を数え、門の**直後**で止める。

    `reserve_hold()` に文字列を返させると `push_missing()` は **1** を返して
    抜けます —— 実際に `thumbnails.set` を撃たずに、
    「穴の門を素通りしたか」だけを見られます。
    """
    monkeypatch.setattr(rt.upload_cap, "day_quota", lambda *a, **k: _Quota())
    monkeypatch.setattr(rt, "_ledger_ahead", lambda *a, **k: [])
    monkeypatch.setattr(rt, "order_by_publish", lambda rows, *a, **k: rows)

    def _gate(ahead, queued, **kw):
        calls.append(queued)
        return False, "**押しません。** 予約に0本の日が 9日あります（検査)"

    monkeypatch.setattr(rt.upload_cap, "thumbnail_yield_to_schedule", _gate)
    monkeypatch.setattr(rt.upload_cap, "schedule_holes",
                        lambda *a, **k: ["09/03"] * 9)
    monkeypatch.setattr(rt.upload_cap, "reserve_hold",
                        lambda *a, **k: "（検査）ここで止めます")


def test_video1本は穴の門を通る(monkeypatch):
    """**印字されている1行が、実際に押す所まで進むこと。**"""
    calls: list = []
    _stub_rows(monkeypatch, ["UIWHsypOPPg", "other1", "other2"])
    _stub_common(monkeypatch, calls)

    rc = rt.push_missing(only_video="UIWHsypOPPg")

    assert calls == [], (
        "`--video` の1本が、まだ穴の門に入っています。"
        "門は 7,900単位 対 450単位 の比べで、50単位 の1本には逆さまです"
    )
    assert rc != 3, (
        "3 は「穴があるので押さなかった」の返りです。"
        "この道はそこで止まってはいけません"
    )


def test_missingの一括は今までどおり穴に譲る(monkeypatch):
    """**緩めたのは1本の道だけ**。158本（7,900単位）の側は変えていません。"""
    calls: list = []
    _stub_rows(monkeypatch, ["a", "b", "c"])
    _stub_common(monkeypatch, calls)

    rc = rt.push_missing()

    assert calls == [3], "一括の道が門を通らなくなっています"
    assert rc == 3, "穴があるとき、一括の道は 3 を返して押さないのが正"


def test_穴が無い窓では一括も通る(monkeypatch):
    """門そのものは生きていること（`--video` の枝が門を殺していない）。"""
    calls: list = []
    _stub_rows(monkeypatch, ["a", "b"])
    _stub_common(monkeypatch, calls)

    def _open(ahead, queued, **kw):
        calls.append(queued)
        return True, "予約に0本の日はありません（検査）"

    monkeypatch.setattr(rt.upload_cap, "thumbnail_yield_to_schedule", _open)
    rc = rt.push_missing()

    assert calls == [2]
    assert rc != 3


def test_穴の門は値段の比べであることを本文が持っている():
    """**この門を次に触る側が、締切の抜けを読めること。**

    数ではなく、**なぜ 1本だけ外したか**が本文に無いと、
    次の回が「一貫していない」と読んで戻します
    （`docs/JOURNAL.md` の「覆る条件を書かないと惰性で戻る」）。
    """
    src = (ROOT / "scripts" / "refresh_thumbnail.py").read_text(encoding="utf-8")
    body = src[src.index("def push_missing("):]
    assert "not only_video" in body, "門から 1本の道が外れていません"
    head = body[:body.index("if not force and not only_long")]
    assert "50単位" in head and "450単位" in head, (
        "外した理由（値段の比べが逆さま）が門の手前に書かれていません"
    )


def test_門そのものは1本でも穴を数えること():
    """**外したのは呼び手側だけ。** `upload_cap` の関数は変えていません。

    ここを緩めると、`batch_build` など**別の呼び手**からも穴が無視されます
    （このリポジトリが何度も見つけている「同じ穴が片方にだけ居る」の逆）。
    """
    import datetime as _dt

    ahead = [_dt.datetime(2026, 9, 1, tzinfo=_dt.timezone.utc),
             _dt.datetime(2026, 9, 5, tzinfo=_dt.timezone.utc)]
    okay, _line = uc.thumbnail_yield_to_schedule(
        ahead, 1, today=_dt.date(2026, 8, 31))
    assert okay is False, (
        "`thumbnail_yield_to_schedule()` 自身は、1本でも穴があれば止めるのが正。"
        "外したのは `--video` の呼び手だけです"
    )
