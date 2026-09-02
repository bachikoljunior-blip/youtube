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
    """
    from src import next_slot
    # **固定の日付を書かないこと**（2026-09-02 18:0x に腐って赤くなった）。
    # ここは `writable_from()` が**未来**を返す枝を見ています。
    # `2026-09-02 07:00Z` と書いてあった行は、その日の 16:00 JST を過ぎた瞬間に
    # 「いま撃てます」の枝へ落ち、**この検査が測りたいものを1つも測らなくなりました。**
    # ＝ この段が塞ごうとしている穴（写した時刻が古くなる）を、検査の側で作った形。
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).date()
    utc_noon = datetime(tomorrow.year, tomorrow.month, tomorrow.day,
                        7, 0, tzinfo=timezone.utc)               # ＝ 16:00 JST
    monkeypatch.setattr(next_slot, "writable_from", lambda *a, **k: utc_noon)
    block = sp._clock_block()
    assert "16:00 JST" in block, f"JST へ直していません: {block!r}"
    assert "07:00 JST" not in block


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


def test_403を観測していない回に403と言わない(monkeypatch):
    """**「いまは 403 です」は嘘のことがあります**（2026-09-02 17:3x に踏んだ）。

    `writable_from()` が見ているのは**帳面の見積り**で、**観測した 403 ではありません。**
    同じ回の `upload_cap.day_quota()` は
    「この窓ではまだ 403 を観測していません」と印字していました。

    09/02 12:45 の `fix`（暦の号令の4つ目の口）と同じ穴です ——
    「判定が帳面の見積りで、repo の正本は観測した 403 だ」。
    **止まっていること自体は本物なので、消すのは「403」という名前だけ。**
    """
    from src import next_slot, upload_cap

    future = datetime.now(timezone.utc) + timedelta(hours=5)
    monkeypatch.setattr(next_slot, "writable_from", lambda *a, **k: future)

    class _Q:
        open = True          # ＝ **まだ 403 を観測していない**

    monkeypatch.setattr(upload_cap, "day_quota", lambda *a, **k: _Q())
    block = sp._clock_block()
    assert "止まっています" in block, block
    assert "403 はまだ観測していません" in block, block
    assert "いまは 403 です" not in block, "観測していない 403 を名乗っています"


def test_403を観測した回はそう言う(monkeypatch):
    from src import next_slot, upload_cap

    future = datetime.now(timezone.utc) + timedelta(hours=5)
    monkeypatch.setattr(next_slot, "writable_from", lambda *a, **k: future)

    class _Q:
        open = False         # ＝ **観測ずみ**

    monkeypatch.setattr(upload_cap, "day_quota", lambda *a, **k: _Q())
    assert "403 を観測ずみ" in sp._clock_block()
