"""`scripts/owner_ask.py` —— **オーナーの手が要る問いが、何周 待っているか**。

2026-09-14 02:5x JST・`hourly`・Opus。

`docs/GOAL.md` の達成期限の節・覆る条件 (4)（「3周 返事が無かったら」）を数える口。
**陽性対照つき**（§5 教訓の形 3つ目 ＝ 落ちるまで撃つ）。
"""
import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "owner_ask", Path(__file__).resolve().parent.parent / "scripts/owner_ask.py")
owner_ask = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(owner_ask)


def _laps(*stamps: str) -> list[dict]:
    return [{"at": s, "round": s, "role": r} for s in stamps for r in ("hourly", "optimizer")]


def _ask(at: str, ident: str = "q1", **kw) -> dict:
    return {"at": at, "id": ident, "asked_by": "hourly", "where": "docs/GOAL.md",
            "text": "外してよいですか", **kw}


def test_周は役ではなく周で数える():
    """2体 で 1周 —— 役ごとに数えると門に 2倍 速く届きます。"""
    st = owner_ask.state([_ask("2026-09-13T21:00:00+09:00")],
                         _laps("2026-09-13T21:59:00+09:00", "2026-09-13T22:54:00+09:00"), [])
    assert st[0]["laps"] == 2
    assert st[0]["drawn"] is False


def test_門に届いて返事が無ければ引かれる():
    st = owner_ask.state([_ask("2026-09-13T21:00:00+09:00")],
                         _laps("2026-09-13T21:59:00+09:00", "2026-09-13T22:54:00+09:00",
                               "2026-09-13T23:49:00+09:00", "2026-09-14T00:46:00+09:00"), [])
    assert st[0]["laps"] == 4
    assert st[0]["drawn"] is True
    assert st[0]["drawn_at"].strftime("%m/%d %H:%M") == "09/13 23:49"   # 3周目 の刻


def test_返事が_1件でも来たら門は消える():
    """**陽性対照** —— 引くのではなく、**オーナーの言葉のほうが正本**（§5）。"""
    inbox = [{"at": "2026-09-14T01:00:00+09:00", "id": "abc123", "source": "owner", "text": "外していいよ"}]
    st = owner_ask.state([_ask("2026-09-13T21:00:00+09:00")],
                         _laps("2026-09-13T21:59:00+09:00", "2026-09-13T22:54:00+09:00",
                               "2026-09-13T23:49:00+09:00", "2026-09-14T00:46:00+09:00"), inbox)
    assert st[0]["replies"] == ["abc123"]
    assert st[0]["drawn"] is False
    assert "その言葉が正本" in "\n".join(owner_ask.lines([_ask("2026-09-13T21:00:00+09:00")],
                                                   _laps("2026-09-13T21:59:00+09:00",
                                                         "2026-09-13T22:54:00+09:00",
                                                         "2026-09-13T23:49:00+09:00",
                                                         "2026-09-14T00:46:00+09:00"), inbox))


def test_訊きより前のオーナーの言葉は返事ではない():
    """達成期限の言葉（20:0x／20:5x）は、21:0x の訊きの**前**です。"""
    inbox = [{"at": "2026-09-13T20:49:26+09:00", "id": "95e92b1e", "source": "owner", "text": "達成期限3ヶ月だよ"}]
    st = owner_ask.state([_ask("2026-09-13T21:00:00+09:00")],
                         _laps("2026-09-13T21:59:00+09:00", "2026-09-13T22:54:00+09:00",
                               "2026-09-13T23:49:00+09:00"), inbox)
    assert st[0]["replies"] == []
    assert st[0]["drawn"] is True


def test_answered_を追記したら黙る():
    """台帳は追記だけ —— 同じ `id` の新しい行が勝つ。"""
    asks = [_ask("2026-09-13T21:00:00+09:00"),
            _ask("2026-09-13T21:00:00+09:00", answered="abc123")]
    st = owner_ask.state(asks, _laps("2026-09-13T21:59:00+09:00", "2026-09-13T22:54:00+09:00",
                                     "2026-09-13T23:49:00+09:00"), [])
    assert st[0]["answered"] == "abc123"
    assert st[0]["drawn"] is False
    body = "\n".join(owner_ask.lines(asks, _laps("2026-09-13T21:59:00+09:00"), []))
    assert "返事待ちは 0件" in body and "畳んでよい" in body


def test_実物の台帳で_fix2_lift_が引かれている():
    """**この回の実物** —— 09/13 21:0x の訊きは 09/13 23:49 の周で引かれた。"""
    root = Path(__file__).resolve().parent.parent
    st = owner_ask.state(owner_ask._rows(root / "data/owner_ask.jsonl"),
                         owner_ask._rows(root / "data/rounds.jsonl"),
                         owner_ask._rows(root / "data/inbox.jsonl"))
    fix2 = next(s for s in st if s["id"] == "fix2_lift")
    assert fix2["drawn"] is True
    assert fix2["replies"] == []
