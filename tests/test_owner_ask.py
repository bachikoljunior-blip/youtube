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


def test_実物の台帳が読めて_答えの出た問いは引かれない():
    """**実物の台帳**に当てる。**「きょうの状態」は書かない**（§5 教訓の形 6つ目）。

    **2026-09-14 06:2x に踏んで直した**（optimizer・Opus）——
    ここには「09/13 21:0x の訊きは 09/13 23:49 の周で引かれた」と、
    **その日の状態が不変条件として**書いてありました。
    オーナーが 06:15 に `fix2_lift` へ答えた瞬間に `drawn` は False になり、
    **道具は正しく動いているのに検査だけが赤くなりました**（答えが来たら門は消える ＝ 道具の註のとおり）。
    **齢も枠も日が経てば門を渡る** ＝ 実物に当てるなら、**日が経っても向きの変わらない不変条件**だけ:

      (1) 台帳が読めて、問いが 1件 以上 在る
      (2) `answered` の在る問いは **決して `drawn` にならない**（答えが来たら引くのではなく、その言葉が正本）
      (3) `answered` の無い問いは「まだ引けない／言葉が出ている／引かれた」の **どれか 1つ**
      (4) 印字の側: `answered` の在る問いは **返事ずみ**と出て、**返事待ちの件数に入らない**
          （**陽性対照はここ** —— `lines()` が `answered` を見なくなると、実物の台帳で落ちます）
    """
    root = Path(__file__).resolve().parent.parent
    asks = owner_ask._rows(root / "data/owner_ask.jsonl")
    rounds = owner_ask._rows(root / "data/rounds.jsonl")
    inbox = owner_ask._rows(root / "data/inbox.jsonl")
    st = owner_ask.state(asks, rounds, inbox)
    assert st, "実物の台帳に問いが 1件 も無い"
    for s in st:
        if s["answered"]:
            assert s["drawn"] is False, f"{s['id']}: 答えの出た問いが引かれている"
        else:
            states = [s["laps"] < owner_ask.GATE_LAPS, bool(s["replies"]), s["drawn"]]
            assert sum(1 for x in states if x) >= 1, f"{s['id']}: どの状態でもない"
    body = owner_ask.lines(asks, rounds, inbox)
    answered = [s for s in st if s["answered"]]
    assert answered, "実物の台帳に答えの出た問いが 1件 も無い（(4) を測れない）"
    for s in answered:
        line = next(x for x in body if f"`{s['id']}`" in x)
        assert "返事ずみ" in line, f"{s['id']}: 印字が 返事ずみ になっていない"
    assert f"返事待ち {len(st) - len(answered)}件" in body[0]


def test_FOR_OWNER_に書かれていない問いは_届いていないと言う():
    """**この道具が 8周 数えていたのは、返事ではなく自分が出し忘れた文でした**
    （2026-09-18 05:xx・`undelivered` の註）。

    `data/owner_ask.jsonl` は**子しか読まない台帳**で、オーナーへ届く道は
    `docs/FOR_OWNER.md` の「出す」の窓 1つ だけです。
    **陽性対照つき** —— 置いたら黙り、外したら鳴ること。
    """
    st = owner_ask.state([_ask("2026-09-17T16:06:00+09:00", "channel_rename_studio")],
                         _laps("2026-09-17T17:00:00+09:00"), [])
    # 置いていない ＝ 鳴る
    assert owner_ask.undelivered(st, "（この列に窓はありません）") == ["channel_rename_studio"]
    # 置いた ＝ 黙る（**陽性対照**）
    assert owner_ask.undelivered(st, "### 出す … channel_rename_studio の窓") == []
    # 印字にも出ること
    out = "\n".join(owner_ask.lines([_ask("2026-09-17T16:06:00+09:00", "channel_rename_studio")],
                                    _laps("2026-09-17T17:00:00+09:00"), [],
                                    for_owner="（窓はありません）"))
    assert "オーナーに届いていない問い 1件" in out


def test_オーナーが言葉を出した問いは_届いていないとは言わない():
    """返事の側は `lines` が別の行で扱います —— **2つ を同じ行で鳴らさないこと**。"""
    inbox = [{"at": "2026-09-17T20:54:00+09:00", "id": "d699098f", "source": "owner",
              "text": "アニメーションの話"}]
    st = owner_ask.state([_ask("2026-09-17T16:06:00+09:00", "q9")],
                         _laps("2026-09-17T17:00:00+09:00"), inbox)
    assert owner_ask.undelivered(st, "（窓はありません）") == []


def test_実物_返事待ちの問いは全部_FOR_OWNER_に在る():
    """**実物で撃つ** —— 開いている問いが 1件でも `docs/FOR_OWNER.md` に無ければ、
    それは「返事が来ない」ではなく「**出していない**」側です。"""
    st = owner_ask.state(owner_ask._rows(owner_ask.ROOT / "data/owner_ask.jsonl"),
                         owner_ask._rows(owner_ask.ROOT / "data/rounds.jsonl"),
                         owner_ask._rows(owner_ask.ROOT / "data/inbox.jsonl"))
    assert owner_ask.undelivered(st) == []
