"""**枠切れは「飛ばす」ではなく「止める」**（2026-08-27 に見つけた）。

## なぜ要るか

`scripts/reschedule._update` は日枠の 403 を **`SystemExit`** に変えて投げます。
**`SystemExit` は `Exception` の子ではありません。**

`scripts/live_slots.apply_moves` には、こう書いてありました:

    except SystemExit as e:
        if e.code:
            skipped.append(...)      # ← 日枠の 403 も、ここへ来ます
            continue                 # ← **残りの手を、ぜんぶ撃ち続けます**
    except Exception as e:
        if "quotaExceeded" in text:
            # **枠が尽きたら、そこで止めること。** 撃つほど悪くなります
            return 1                 # ← **ここへは永久に来ません**

**「止める」と書いてある所と、実際に通る所が別**でした
（この repo が通算11回 踏んでいる「片方だけ」の形）。
実害は 403 の回数で見えます —— 08/27 の窓で **29回 → 60回** に育っています。
尽きた時点で降りていれば **1回** です。

**混ぜないこと**: ほかの `SystemExit`（過去の時刻・見つからない本・公開済み）は
**1本ずつ飛ばして進んでよい** ものです。飛ばしてよいものを止めると残りが
当たらず（08/27 16:xx に `kH-2eghxy2w` の 400 で 43手 が死んだ形）、
止めるべきものを飛ばすと 403 を人数ぶん買います。

**覆る条件**: `_update` が日枠切れを `SystemExit` 以外で伝えるようになったとき。
そのときは `is_quota_exit` の中身を変えること（呼ぶ側は触らなくて済みます）。
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import live_slots  # noqa: E402
from scripts import reschedule  # noqa: E402

# **`live_slots.apply_moves` は `from scripts import reschedule` で引きます。**
# 素の `import reschedule`（`sys.path` 経由）は**別のモジュール実体**なので、
# そちらに monkeypatch を当てても実物の口を叩きにいきます（この検査を
# 書いた回に、本当に 403 を1回 買いました）。**同じ実体に当てること。**

JST = timezone(timedelta(hours=9))


# ------------------------------------------------ 見分けるところ

def test_日枠切れのSystemExitを見分ける():
    got = None
    try:
        raise SystemExit(f"[reschedule] **abc の予約は、いま外せません"
                         f"{reschedule.QUOTA_MARK}。**\n  つづき")
    except SystemExit as exc:
        got = exc
    assert reschedule.is_quota_exit(got)


def test_ほかのSystemExitは止めない():
    """飛ばして進んでよいものです。**止めると、残りの手が1つも当たりません。**"""
    for msg in ("過去の時刻です: 2026-08-01T09:00 JST",
                "動画が見つかりません: abc",
                "invalidPublishAt"):
        assert not reschedule.is_quota_exit(SystemExit(msg)), msg
    assert not reschedule.is_quota_exit(SystemExit(0))
    assert not reschedule.is_quota_exit(SystemExit())
    assert not reschedule.is_quota_exit(RuntimeError(reschedule.QUOTA_MARK))


def test_印が_update_の文言から消えていないこと():
    """**この語を消すと、上の見分けが黙って効かなくなります。**"""
    text = (Path(__file__).resolve().parent.parent
            / "scripts" / "reschedule.py").read_text(encoding="utf-8")
    assert text.count("QUOTA_MARK") >= 3, (
        "`_update` の SystemExit の文言が `QUOTA_MARK` を使っていません。"
        "べた書きに戻すと、`live_slots` が日枠の 403 を『飛ばして続ける』に戻ります")


# ------------------------------------------------ 止まるところ

class _Board:
    def __init__(self, moves):
        self.moves = moves


def _moves(n: int):
    at = datetime(2026, 9, 4, 9, 0, tzinfo=JST)
    return [(f"vid{i}", at + timedelta(days=i)) for i in range(n)]


def test_日枠切れなら_残りを撃たずに止まる(monkeypatch, capsys):
    """**この回の実害そのもの。** 5本 の手で 403 を 5回 買っていました。"""
    shot: list[str] = []

    def _fake_main(argv):
        shot.append(argv[1])
        raise SystemExit(f"いま外せません{reschedule.QUOTA_MARK}。")

    monkeypatch.setattr(reschedule, "main", _fake_main)

    rc = live_slots.apply_moves(_Board(_moves(5)))

    assert rc == 1
    assert shot == ["vid0"], f"尽きたあとも撃っています: {shot}"
    assert "日枠が尽きました" in capsys.readouterr().out


def test_飛ばしてよい落ち方は_残りを当てにいく(monkeypatch, capsys):
    """**止めすぎないこと。** 公開済みの本1つで 43手 が死んだ回があります。"""
    shot: list[str] = []

    def _fake_main(argv):
        shot.append(argv[1])
        if argv[1] == "vid1":
            raise SystemExit("動画が見つかりません: vid1")
        return 0

    monkeypatch.setattr(reschedule, "main", _fake_main)

    live_slots.apply_moves(_Board(_moves(4)))

    assert shot == ["vid0", "vid1", "vid2", "vid3"]
    assert "飛ばした 1本" in capsys.readouterr().out


def test_全部通れば全部撃つ(monkeypatch, capsys):
    monkeypatch.setattr(reschedule, "main", lambda argv: 0)

    assert live_slots.apply_moves(_Board(_moves(3))) in (0, None)
    assert "3回 動かしました" in capsys.readouterr().out
