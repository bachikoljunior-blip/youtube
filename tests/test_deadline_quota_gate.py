"""**その時刻に、計器がそもそも読めるか**（`deadline_check._quota_gate`）。

## なぜ要るか（2026-08-27 に踏んだ。**同じ日の3件目**）

この門は同じ日のうちに2段 直っています ——
朝に `at_time_jst`（日 → 時刻）、昼に `data_file:`（時計 → **点が在るか**）。
**3段目が抜けていました: その点を、取り直せるのか。**

実測 2026-08-27 18:5x JST、前提「1日に再生が付く本数の上限は
その日の本数（10本）であって、時刻の窓ではない」:

    門の言い分   **今日の 22:00 JST に出ます。その時刻を過ぎた回が拾うこと**
    取り直す道具  `python scripts/snapshot.py` ＝ `videos.list`（**Data API**）
    Data API 日枠 **この窓で 403 を 29回 観測**。戻るのは **08/28 16:00 JST**

**22:00 JST に撃っても 403 です。** 読めるのはその 18時間 後 ——
つまり門は**偽の判定日**を出し、しかも「その時刻を過ぎた回が拾うこと」と
名指しで指示していました。拾いに行った回は 403 を1つ買って帰ります。

## ここが壊れたと分かる形

`data_file:` は「点が在るか」しか見ません。在りません、とは正しく言えますが、
その次の行で**撃てない手**を出します。
**在るかどうかと、取れるかどうかは別の事実**です。
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import deadline_check as dc  # noqa: E402

JST = timezone(timedelta(hours=9))
WHEN = datetime(2026, 8, 27, 22, 0, tzinfo=JST)


class _Q:
    def __init__(self, open_: bool, back: datetime, hits: int = 29) -> None:
        self.open = open_
        self.resets_at = back
        self.hits = hits


def _quota(monkeypatch, open_: bool, back: datetime, hits: int = 29):
    """**窓の頭も一緒に差し替えること。** 本物の `window_start()` は毎日 動くので、
    差し替えないと**この検査は明日 落ちます**（中身は1行も変わらないのに）。
    """
    from src import upload_cap
    monkeypatch.setattr(upload_cap, "day_quota", lambda *a, **k: _Q(open_, back, hits))
    monkeypatch.setattr(upload_cap, "window_start",
                        lambda *a, **k: back - timedelta(days=1))


BACK = datetime(2026, 8, 28, 16, 0, tzinfo=JST)
NEED = {"kind": "after", "on_date": "2026-08-27", "at_time_jst": "22:00",
        "data_file": "data/views.jsonl", "refresh": "python scripts/snapshot.py"}


def test_枠が閉じていれば戻る日を返す(monkeypatch):
    _quota(monkeypatch, False, BACK)
    a = dc._quota_gate(NEED, WHEN, "この日の読み")
    assert a is not None, "**偽の判定日をそのまま出しています**"
    assert a.ready == BACK.date()
    assert "403" in a.why
    assert "08/28 16:00 JST" in a.why


def test_拾いに行くなと名指しする(monkeypatch):
    _quota(monkeypatch, False, BACK)
    a = dc._quota_gate(NEED, WHEN, "この日の読み")
    assert "拾いに行かないこと" in a.todo
    assert "条件は緩めないこと" in a.todo


def test_枠が開いていれば黙る(monkeypatch):
    _quota(monkeypatch, True, BACK)
    assert dc._quota_gate(NEED, WHEN, "x") is None


def test_枠のほうが先に戻るなら黙る(monkeypatch):
    """時計より前に枠が戻るなら、**時計だけの話**です。"""
    _quota(monkeypatch, False, datetime(2026, 8, 27, 16, 0, tzinfo=JST))
    assert dc._quota_gate(NEED, WHEN, "x") is None


def test_日枠を使わない取り直しには掛からない(monkeypatch):
    """**Analytics API と Reporting API は別の枠**です。掛けると逆に外れます。"""
    _quota(monkeypatch, False, BACK)
    need = dict(NEED, refresh="python -m src.rpm_mix --forms")
    assert dc._quota_gate(need, WHEN, "x") is None


def test_quotaの明示が一覧より優先する(monkeypatch):
    _quota(monkeypatch, False, BACK)
    assert dc._quota_gate(dict(NEED, quota="none"), WHEN, "x") is None
    need = {"refresh": "python -m src.rpm_mix --forms", "quota": "data_api"}
    assert dc._quota_gate(need, WHEN, "x") is not None


def test_読めないときは黙る(monkeypatch):
    """**門を増やさないこと。** 読めないことを「閉じている」と読まない。"""
    from src import upload_cap

    def _boom(*a, **k):
        raise RuntimeError("読めません")

    monkeypatch.setattr(upload_cap, "day_quota", _boom)
    assert dc._quota_gate(NEED, WHEN, "x") is None


def test_本物の台帳のday_cap要件が門を持っている():
    """**実物を1件 縛ること。** 差し替えた盤面だけで緑になる形を避けます。

    `scripts/snapshot.py` で取り直す要件が、`_DATA_API_REFRESH` から
    外れていないこと。外れたら、また 22:00 に 403 を買いに行きます。
    """
    import yaml
    d = yaml.safe_load((ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
    hs = d["hypotheses"] if isinstance(d, dict) else d
    hit = [n for h in hs for n in (h.get("needs") or [])
           if "snapshot.py" in str(n.get("refresh") or "")]
    assert hit, "`scripts/snapshot.py` で取り直す要件が台帳から消えました"
    for need in hit:
        assert (str(need.get("quota") or "") == "data_api"
                or any(t in str(need.get("refresh")) for t in dc._DATA_API_REFRESH)), (
            "`snapshot.py` が `_DATA_API_REFRESH` から外れています")


# --- **時刻がそこで落ちていた**（2026-08-28 03:1x に踏んだ。`not_open_yet`）---


def test_門は戻る時刻そのものも返す(monkeypatch):
    """`Answer.ready` は**日付**なので、`16:00` はそこで落ちます。

    落ちたぶん、その日の 00:00〜16:00 に走る回は全部
    `arm_speed.next_close()` から「今日が判定できる日」を受け取り、
    `eta.py` の頭3行に「**この回は `verdict` で日付が動かせます**」と出ました
    （**16時間ぶん**）。同じ回に `status.py` は
    「期限が来ていて、**いま判定できる前提: なし**」と正しく出しています。
    """
    _quota(monkeypatch, False, BACK)
    a = dc._quota_gate(NEED, WHEN, "この日の読み")
    assert a.ready_at == BACK, "戻る**時刻**が落ちています（日付だけでは 16時間 嘘をつきます）"


def test_その日のうちでも時刻が来ていなければ外す(monkeypatch):
    """`not_open_yet`。**`unready_claims` の1段 深いところ**です。

    あちらは「日が出せない」を捕まえます。ここは
    「**日は出た。今日だ。ただし読めるのは 16:00 から**」を捕まえます。
    """
    v = dc.Verdict(claim="c", deadline=BACK.date(), ready=BACK.date(),
                   answers=[dc.Answer(BACK.date(), why="x", ready_at=BACK)])
    monkeypatch.setattr(dc, "check", lambda *a, **k: [v])
    monkeypatch.setattr(dc, "load", lambda *a, **k: [])
    before = datetime(2026, 8, 28, 3, 17, tzinfo=JST)
    after = datetime(2026, 8, 28, 16, 30, tzinfo=JST)
    assert dc.not_open_yet(now=before) == {"c"}, "16:00 の前なのに通しています"
    assert dc.not_open_yet(now=after) == set(), "16:00 を過ぎたのに止めています"


def test_時刻を持たない要件は外さない(monkeypatch):
    """**門を増やさないこと。** `ready_at` が無い ＝ その日なら一日じゅう読める。"""
    v = dc.Verdict(claim="c", deadline=BACK.date(), ready=BACK.date(),
                   answers=[dc.Answer(BACK.date(), why="x")])
    monkeypatch.setattr(dc, "check", lambda *a, **k: [v])
    monkeypatch.setattr(dc, "load", lambda *a, **k: [])
    assert dc.not_open_yet(now=datetime(2026, 8, 28, 3, 17, tzinfo=JST)) == set()


def test_etaはそのclaimをnext_closeから外す():
    """**繋がっているところまでが1件です。** 道具を足しても、呼ばれなければ 0。

    `scripts/eta.py` の `_unready_claims()` が `not_open_yet()` を
    足し込んでいること。**外すと、また 16時間ぶん嘘が出ます。**
    """
    src = (ROOT / "scripts" / "eta.py").read_text(encoding="utf-8")
    assert "not_open_yet" in src, (
        "`eta.py` が `not_open_yet()` を読んでいません —— "
        "`unready_claims()` だけでは『今日だが 16:00 から』を外せません")
