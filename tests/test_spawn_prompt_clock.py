"""**申し送りに写された時刻を、子が信じないようにする段**（2026-09-02 11:4x に踏んだ）。

申し送り（`--note`）は**原文のまま**通ります —— 要約しない、数字は桁もそのまま。
**それは正しい。** ですが原文には「いま何時の窓か」が書かれていることがあり、
**それは書いた時点の写しです。**

実測 —— 申し送りの1行目:

    **この回は 09/02 16:00 JST の窓に当たります（日枠が戻る回）**

受け取った子が最初に撃った `run_marker.py --write` の時刻は **11:41 JST**。
**枠が戻る 4時間19分 前**で、その本文が名指ししていた 1,250単位 と 100単位 の
2手は、その回には**撃てません**でした。

`_gate_state_block()` が同じ形の穴を先に塞いでいます ——
「べた書きのままだと、次に立つ子は全員『6件とも開いている』と読みます。
**本文の先頭は、いちばん強く効く場所です。**」

**申し送りは直せません（原文だから）。だから、すぐ下に実物を置きます。**
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location("_sp", ROOT / "scripts" / "spawn_prompt.py")
sp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sp)

JST = timezone(timedelta(hours=9))


def test_型に差し込み口が在る():
    """**消さないこと。** 消えても型は組み上がるので、赤で気づくしかありません。"""
    tpl = (ROOT / "docs" / "spawn_prompt.md").read_text(encoding="utf-8")
    assert "<<clock_block>>" in tpl
    body = tpl.split("## kind: hourly", 1)[1]
    assert body.index("<<note_block>>") < body.index("<<clock_block>>"), \
        "申し送りの**すぐ下**に置くこと（上に置くと、原文がこの行を上書きして読まれます）"


def test_組み立てた本文に時刻が入る():
    out = sp.build("hourly", note="この回は 09/02 16:00 JST の窓に当たります")
    assert "JST です" in out, "組み立てた時刻が本文に入っていません"
    assert "写し" in out, "申し送りの時刻が写しであることを言っていません"
    # 申し送りそのものは1字も変えないこと
    assert "この回は 09/02 16:00 JST の窓に当たります" in out


def test_枠の時刻を_JST_で刷る(monkeypatch):
    """**`writable_from()` は UTC で返します。** 直さずに刷ると 9時間 ずれます。

    実際に一度そう出ました（**09/02 07:00 JST** と印字・実物は 16:00）。
    「あと N時間」だけが正しく、時刻のほうがずれる —— **この段が塞ごうとしている
    穴（写した時刻を信じる）そのもの**の形です。

    ## **暦を焼き込まないこと**（2026-09-02 16:2x に直した。**同じ形で3件目**）

    ここは長らく `datetime(2026, 9, 2, 7, 0, UTC)`（＝ 16:00 JST）を
    べた書きしていました。`_clock_block()` は `w <= now` で枝が割れるので、
    **実時刻が 09/02 16:00 JST を過ぎた瞬間に「いま撃てます」の枝へ落ち、
    時刻を1つも刷らなくなります** —— この検査は**その日のうちに赤くなりました**
    （実測 16:20 JST）。**検査が「毎日 動く結果」を写していた**形で、
    同じ日に既に2件 直しています（`test_parent_first_move` /
    `test_queue_lag_publish_cap`・`data/runs.jsonl` 08:33 の `fix_gate`）。

    いまは**いまの時刻からの相対**で置きます。**結果ではなく差を見ること。**
    """
    from src import next_slot
    JST = timezone(timedelta(hours=9))
    # **未来側に置くこと** —— `w <= now` だと「いま撃てます」の枝で時刻を刷りません。
    ahead = datetime.now(timezone.utc) + timedelta(hours=3)
    monkeypatch.setattr(next_slot, "writable_from", lambda *a, **k: ahead)
    block = sp._clock_block()
    want = f"{ahead.astimezone(JST):%m/%d %H:%M} JST"
    utc_face = f"{ahead:%m/%d %H:%M} JST"        # 直し忘れるとこちらが出ます
    assert want in block, f"JST へ直していません: {block!r}"
    assert utc_face not in block, f"UTC の顔のまま刷っています: {block!r}"


def test_撃てる回はそう言う(monkeypatch):
    from src import next_slot
    past = datetime.now(timezone.utc) - timedelta(hours=2)
    monkeypatch.setattr(next_slot, "writable_from", lambda *a, **k: past)
    block = sp._clock_block()
    assert "いま撃てます" in block
    assert "403" not in block


def test_読めない回は黙る(monkeypatch):
    """**読めないことを「いつでも撃てます」として印字しないこと**（`_gate_state_block` と同じ）。"""
    from src import next_slot

    def boom(*a, **k):
        raise RuntimeError("読めません")

    monkeypatch.setattr(next_slot, "writable_from", boom)
    block = sp._clock_block()
    assert "いま撃てます" not in block
    assert "403" not in block
    # 時刻の行そのものは残ってよい（あれは道具を要りません）
    assert "JST です" in block


def test_写しに時刻を焼き込まない():
    """**`docs/spawn_prompt.rendered.md` は commit される静的な生成物です。**

    時刻を入れると、書き出した**次の分から永久に赤**になります
    （`test_rendered_copy_for_the_parent_is_current` が1字でも違えば落とすため）。
    実測: 入れた直後の1回は同じ分だったので緑、**次の分で赤**。
    ＝ **この段が塞ごうとしている穴（写した時刻が古くなる）を、写しの側で自分が作る。**
    """
    got = (ROOT / "docs" / "spawn_prompt.rendered.md").read_text(encoding="utf-8")
    assert "JST です" not in got, "写しに組み立て時刻が焼き込まれています"
    assert "ここに入ります" in got, "写しに差し込み口の説明が残っていません"
    # 立てる瞬間の本文には、ちゃんと入ること（口だけで終わらせない）
    assert "JST です" in sp.build("hourly")
