r"""**停止を確認したら、床を待たずに立て直す**（2026-09-14 22:0x・optimizer-sub・Opus）。

オーナー原文（2026-09-14 19:44 JST・受け取り帳 `6df66dd7`）:

> **「3分ごとに停止を確認していたら原因を全て潰してから再実行するようにして出せるまでやって」**
> **「停止を確認したら、ね」**

見張るのは 4つ:

    (1) **陽性対照** —— 09/14 17:16〜20:07 の当の停止（口が拒まれた 2.85時間）を、
        この機構が「停止」と読むこと。**読めない形に直したら、ここが落ちます。**
    (2) **陰性対照** —— ふつうの周（口が開いていて、枠に本が在る）では 1字も出ないこと。
        ここが無いと、`src/alerts.py` の「一覧が当たりを含まないまま育つ」側へ倒れます。
    (3) **3分 を使う先** —— 潰せる原因（`owner=False`）が在る周だけ・`live == 0` の周だけ。
        口しか閉じていない周に 3分 を使うと、枠を食って 31時間 止まる側へ倒れます。
    (4) **下げる側にしか動かないこと** —— 停止の判定は「止める仕掛け」になりえない
        （`CLAUDE.md` 2026-08-31「勝手にそれで止まるのなし」）。

**数の出どころは `studio/stall.py` の docstring 1か所**（写しを持たないこと）。
"""
from __future__ import annotations

import datetime as dt
import importlib.util
from pathlib import Path

import pytest

from studio import stall

ROOT = Path(__file__).resolve().parent.parent
JST = dt.timezone(dt.timedelta(hours=9))


def _nr():
    """`scripts/next_round.py` を道から読む（`scripts.` で引けない回もあるため）。"""
    spec = importlib.util.spec_from_file_location(
        "next_round_for_stall", ROOT / "scripts" / "next_round.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _t(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s).astimezone(JST)


def _lap(s: str) -> dict:
    return {"round": s, "role": "optimizer", "at": s}


# ---- (1) 陽性対照: 09/14 の当の停止 ------------------------------------------------
#
# 実物（`data/studio/ledger.jsonl`）: 最後の `channel` が 17:16、`token_rejected` が 19:12、
# 口が戻った `channel` が 20:07。**この窓が、142窓 のうち 2.0h を越えた唯一の 1窓**です。
REAL_ROWS = [
    {"event": "channel", "id": "UChTXZzwkIJHqyL7L_fEtuqQ", "at": "2026-09-14T17:16:04+09:00"},
    {"event": "pending", "id": "-bSkulqONhI", "at": "2026-09-14T09:28:00+09:00",
     "publish_at": "2026-09-14T10:00:00+09:00"},
    {"event": "token_rejected", "id": "-", "cmd": "status", "at": "2026-09-14T19:12:51+09:00"},
]
REAL_ROUNDS = [_lap("2026-09-14T17:13:00+09:00"), _lap("2026-09-14T18:46:00+09:00")]


def test_当の停止を停止と読む():
    """19:30 JST（停止のただ中）で、印が 2つ 立つこと。"""
    st = stall.state(REAL_ROWS, REAL_ROUNDS, _t("2026-09-14T19:30:00+09:00"))
    assert st["stalled"] is True, (
        "09/14 17:16〜20:07 の 2.85時間（口が Google に拒まれ status/measure/schedule が"
        f"全部 止まった当の停止）を、停止と読めていません: {st['why']}")
    codes = {s["code"] for s in st["signs"]}
    assert "token_rejected" in codes, f"口が拒まれた行を読めていません: {codes}"
    assert "mouth_gap" in codes, f"口が開いた印が 2.23h 空いたのを読めていません: {codes}"
    assert st["shippable"] is False, "口が閉じているのに「出せる」と言っています"


def test_拒まれた行はその場で立つ():
    """`token_rejected` が入った 3分後 には、もう停止と読めること（時間の門を待たない）。"""
    st = stall.state(REAL_ROWS, REAL_ROUNDS, _t("2026-09-14T19:15:00+09:00"))
    assert st["stalled"] is True, "拒まれた行が在るのに、時間の門が明けるまで黙っています"
    assert [s["code"] for s in st["signs"]] == ["token_rejected"]


def test_口が戻れば印は消える():
    """20:07 の `channel` が入ったら、印は 1つも立たないこと（引かれた側も数える）。"""
    rows = REAL_ROWS + [{"event": "channel", "id": "UChTXZzwkIJHqyL7L_fEtuqQ",
                         "at": "2026-09-14T20:07:17+09:00"}]
    st = stall.state(rows, REAL_ROUNDS, _t("2026-09-14T20:10:00+09:00"))
    assert st["stalled"] is False, f"口が戻ったのに停止と言い続けています: {st['signs']}"


# ---- (2) 陰性対照: ふつうの周 -------------------------------------------------------

def _healthy(now: dt.datetime) -> tuple[list[dict], list[dict]]:
    return ([{"event": "channel", "id": "C", "at": (now - dt.timedelta(minutes=5)).isoformat()},
             {"event": "measured", "id": "v", "at": (now - dt.timedelta(minutes=4)).isoformat()},
             {"event": "scheduled", "id": "s", "at": (now - dt.timedelta(hours=3)).isoformat(),
              "publish_at": (now + dt.timedelta(hours=6)).isoformat()},
             {"event": "pending", "id": "p", "at": (now - dt.timedelta(minutes=4)).isoformat(),
              "publish_at": (now + dt.timedelta(hours=6)).isoformat()}],
            [_lap((now - dt.timedelta(hours=3)).isoformat()),
             _lap((now - dt.timedelta(minutes=6)).isoformat())])


def test_ふつうの周では一字も出ない():
    """**立たない回は 1行も印字しないこと**（当たりを含まないまま育つ側へ倒さない）。"""
    now = _t("2026-09-14T14:00:00+09:00")
    rows, rounds = _healthy(now)
    st = stall.state(rows, rounds, now)
    assert st["stalled"] is False, f"ふつうの周で停止と言っています: {st['signs']}"
    assert stall.lines(rows, rounds, now) == [], "停止していないのに印字しています"
    assert st["shippable"] is True, st["ship_words"]


def test_枠が埋まっていれば刻を過ぎても停止ではない():
    """公開の 10:00 を過ぎた昼でも、きょうの枠が埋まっていれば停止ではないこと。

    **ここが無いと (D) は毎日 14時間 鳴ります** —— 実測（09/08〜09/14）では、次の日の予約は
    毎日 00:0x〜00:5x に入っており、10:00 の公開から そこまでの **約 14時間** は
    「未来の `publish_at` が無い」状態がふつうです。
    """
    now = _t("2026-09-14T15:00:00+09:00")
    rows = [{"event": "channel", "id": "C", "at": (now - dt.timedelta(minutes=5)).isoformat()},
            {"event": "pending", "id": "p", "at": "2026-09-14T09:28:00+09:00",
             "publish_at": "2026-09-14T10:00:00+09:00"}]
    rounds = [_lap((now - dt.timedelta(hours=2)).isoformat()),
              _lap((now - dt.timedelta(minutes=6)).isoformat())]
    codes = {s["code"] for s in stall.signs(rows, rounds, now)}
    assert "slot_missed" not in codes, (
        "きょうの枠は埋まっている（10:00 に出た）のに `slot_missed` が立っています "
        f"＝ 毎日 14時間 鳴る形です: {codes}")


def test_きょうの枠が空のまま刻を過ぎたら停止():
    """**陽性対照の片方**（この印は実測 8日 とも 0件 ＝ まだ 1度も立っていない）。"""
    now = _t("2026-09-14T15:00:00+09:00")
    rows = [{"event": "channel", "id": "C", "at": (now - dt.timedelta(minutes=5)).isoformat()},
            {"event": "pending", "id": "p", "at": "2026-09-13T09:28:00+09:00",
             "publish_at": "2026-09-13T10:00:00+09:00"}]
    rounds = [_lap((now - dt.timedelta(hours=2)).isoformat()),
              _lap((now - dt.timedelta(minutes=6)).isoformat())]
    sg = stall.signs(rows, rounds, now)
    slot = [s for s in sg if s["code"] == "slot_missed"]
    assert slot, f"きょうの枠が空のまま 10:00 を過ぎたのに立ちません: {[s['code'] for s in sg]}"
    assert slot[0]["owner"] is False, "枠は機械が潰せる側です（build → schedule）"


# ---- (3) 3分 を使う先 ---------------------------------------------------------------

def test_盲の周は三分で立て直す():
    """終わった周の窓に台帳の行が 0行（実測 127周 中 2周）＝ 機械が潰せる側。"""
    now = _t("2026-09-11T19:13:00+09:00")
    rows = [{"event": "channel", "id": "C", "at": "2026-09-11T17:27:00+09:00"},
            {"event": "pending", "id": "p", "at": "2026-09-11T09:28:00+09:00",
             "publish_at": "2026-09-11T10:00:00+09:00"}]
    rounds = [_lap("2026-09-11T17:27:00+09:00"), _lap("2026-09-11T18:00:00+09:00"),
              _lap("2026-09-11T18:41:00+09:00")]
    st = stall.state(rows, rounds, now)
    codes = {s["code"] for s in st["signs"]}
    assert "blind_lap" in codes, f"盲の周（09/11 18:00）を読めていません: {codes}"
    assert st["retry_min"] == stall.RETRY_MIN, (
        f"潰せる原因（blind_lap）が在るのに 3分 を使いません: {st['why']}")


def test_口だけの停止に三分を使わない():
    """口（オーナーの手）しか立っていない周は**床のまま**（3分 で立て直しても潰せない）。

    実測の 2.85時間 は最後までオーナーの手でしか開かず、そこへ 3分 ごとに周を立てれば
    枠を食って **31時間 止まる**側（`next_round.decide()` の 09/03 の節）へ倒れます。
    """
    st = stall.state(REAL_ROWS, REAL_ROUNDS, _t("2026-09-14T19:30:00+09:00"))
    assert st["stalled"] is True
    assert st["retry_min"] is None, (
        "口しか閉じていない周に 3分 を使っています ＝ 枠を食って 31時間 止まる側です")
    assert "オーナー" in st["why"], st["why"]


def test_上限に当たったら床へ戻り読みが外れたと言う():
    """3分 の周が `RETRY_LAPS_CAP` に届いたら床へ戻ること（オーナー 09/14 20:3x）。"""
    now = _t("2026-09-11T23:00:00+09:00")
    rows = [{"event": "channel", "id": "C", "at": "2026-09-11T17:27:00+09:00"},
            {"event": "pending", "id": "p", "at": "2026-09-11T09:28:00+09:00",
             "publish_at": "2026-09-11T10:00:00+09:00"}]
    rounds = ([_lap("2026-09-11T17:27:00+09:00"), _lap("2026-09-11T18:00:00+09:00")]
              + [_lap(f"2026-09-11T18:{41 + i:02d}:00+09:00")
                 for i in range(stall.RETRY_LAPS_CAP + 1)])
    st = stall.state(rows, rounds, now)
    assert st["laps"] >= stall.RETRY_LAPS_CAP, st["laps"]
    assert st["retry_min"] is None, f"上限を越えても 3分 を使い続けています: {st['why']}"
    assert "外れて" in st["why"], st["why"]


# ---- 親の手続き（`next_round.decide`）----------------------------------------------

_STALL_CRUSHABLE = {"stalled": True, "signs": [{"code": "blind_lap", "crush": "立て直す",
                                                "owner": False}],
                    "since": None, "laps": 1, "retry_min": stall.RETRY_MIN,
                    "why": "潰せる原因が 1件", "shippable": False, "ship_words": "枠が空"}
_STALL_OWNER = {"stalled": True, "signs": [{"code": "token_rejected", "crush": "口の取り直し",
                                            "owner": True}],
                "since": None, "laps": 1, "retry_min": None,
                "why": "潰せる原因が機械の側に 1つもありません", "shippable": False,
                "ship_words": "口が開いていません"}


@pytest.fixture(scope="module")
def nr():
    return _nr()


def test_停止した周は床を待たずに三分で立つ(nr):
    d = nr.decide(live=0, stall=_STALL_CRUSHABLE)
    assert d["floor_min"] == pytest.approx(stall.RETRY_MIN), (
        f"停止を確認したのに床のままです（{d['floor_min']:.0f}分・{d['source']}）")
    assert d["go"] is True, f"停止しているのに立てません: {d['why']}"
    assert d["stall"] is True and d["stall_retry_applied"] is True


def test_サブが走っている周は縮めない(nr):
    """`live >= 1` の間隔は「二重に立てない」ための物 —— 縮めると隣にもう1体 立ちます。"""
    base = nr.decide(live=1, stall={"stalled": False, "signs": [], "retry_min": None,
                                    "laps": 0, "since": None, "why": "",
                                    "shippable": True, "ship_words": ""})
    got = nr.decide(live=1, stall=_STALL_CRUSHABLE)
    assert got["floor_min"] == pytest.approx(base["floor_min"], abs=0.05), (
        "走っているサブが 1体 在るのに床を縮めています ＝ 二重に立てる形です")
    assert got["stall_retry_applied"] is False
    assert "走っているサブ" in got["stall_why"], got["stall_why"]


def test_口だけの停止では親も床のまま(nr):
    base = nr.decide(live=0, stall={"stalled": False, "signs": [], "retry_min": None,
                                   "laps": 0, "since": None, "why": "",
                                   "shippable": True, "ship_words": ""})
    got = nr.decide(live=0, stall=_STALL_OWNER)
    assert got["floor_min"] == pytest.approx(base["floor_min"], abs=0.05), (
        "潰せる原因が機械の側に無いのに床を縮めています（枠を食う側）")
    assert got["stall"] is True, "印そのものは立てておくこと（読める所に残す）"


def test_停止の判定は床を上げない(nr):
    """**これは「止める仕掛け」ではありません**（`CLAUDE.md` 2026-08-31）。"""
    base = nr.decide(live=0, stall={"stalled": False, "signs": [], "retry_min": None,
                                   "laps": 0, "since": None, "why": "",
                                   "shippable": True, "ship_words": ""})
    for st in (_STALL_CRUSHABLE, _STALL_OWNER):
        got = nr.decide(live=0, stall=st)
        assert got["floor_min"] <= base["floor_min"] + 1e-9, (
            f"停止の判定が床を**上げて**います（{base['floor_min']:.1f} → "
            f"{got['floor_min']:.1f}分）＝ 止める仕掛けです")


def test_立たない回は親も一字も出さない(nr):
    d = nr.decide(live=0, stall={"stalled": False, "signs": [], "retry_min": None,
                                "laps": 0, "since": None, "why": "",
                                "shippable": True, "ship_words": ""})
    assert nr.stall_lines(d) == []


def test_親の印字は潰し方を全部並べる(nr):
    d = nr.decide(live=0, stall=_STALL_CRUSHABLE)
    text = "\n".join(nr.stall_lines(d))
    assert "立て直す" in text, "潰し方が印字に出ていません（原因を全て潰す側が読めません）"
    assert "6df66dd7" in text, "オーナーの言葉の札が印字に出ていません"


# ---- サブの側（`studio/cli.py`）----------------------------------------------------

def test_確認は口を撃つ前に置かれている():
    """**`cmd_status` の中に置かないこと** —— あの関数は 1行目が `yt.channel()` なので、
    口が閉じている周は印にたどり着く前に死にます（09/14 18:2x〜20:2x の当の停止）。

    ＝ 呼びは `cli.main()` の中で、`fn(a)`（cmd の本体）より**前**に在ること。
    """
    src = (ROOT / "studio" / "cli.py").read_text(encoding="utf-8")
    head = src.index("def main(")
    body = src[head:]
    i_check = body.index("stall.lines()")
    i_call = body.index("return fn(a)")
    assert i_check < i_call, (
        "`stall.lines()` が cmd の本体より後ろで呼ばれています ＝ 口が閉じている周は読めません")
    status = src[src.index("def cmd_status("):src.index("def cmd_status(") + 3000]
    assert "stall.lines()" not in status, (
        "`cmd_status` の中に置かれています ＝ `yt.channel()` で死ぬ周には届きません")


# ---- オーナーの言葉そのもの --------------------------------------------------------

def test_オーナーの原文が道具に残っている():
    """**一字も変えないこと**（`CLAUDE.md` の形）。消すには検査を消すしかありません。"""
    words = "3分ごとに停止を確認していたら原因を全て潰してから再実行するようにして出せるまでやって"
    text = (ROOT / "studio" / "stall.py").read_text(encoding="utf-8")
    assert words in text, "オーナー原文（受け取り帳 `6df66dd7`）が `studio/stall.py` にありません"
    assert "「停止を確認したら、ね」" in text, "2つ目の原文がありません"
