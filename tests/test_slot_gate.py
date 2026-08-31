"""**「投稿が途切れる日」の門が、鳴るべきときに鳴り、鳴らないときに黙ること。**

## なぜ要るか（2026-09-01・最適化の回）

`CLAUDE.md` は「**投稿が途切れるのが最大の損失**」と言い、
`scripts/status.py` は 09/03〜09/11 の 9日 が0本だと**正しく印字していました。**
それでも `upload` は 2日で1件（要るのは2件）しか出ていません。

**印字は読まずに終われます**（`scripts/stop_check.sh` 271行目に同じ教訓）。
だから `scripts/slot_gate.py` を門にしました。**この検査は、その門が
「発火したことのない検査」にならないよう、故障を注入して発火を確かめます**
（`CLAUDE.md`「**発火したことのない検査は検査ではない**」）。

## 覆る条件

- `slot_gate.LEAD_DAYS` を変えたら、下の暦の組み方も一緒に動かすこと。
- **控えは上限側の見積り**なので、この門は空を見落とす側に外れます。
  「鳴らない ＝ 埋まっている」を、この検査から読まないこと。
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JST = timezone(timedelta(hours=9))

_spec = importlib.util.spec_from_file_location("slot_gate_mod", ROOT / "scripts" / "slot_gate.py")
slot_gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(slot_gate)


def _row(d: date, hour: int = 22) -> dict:
    """JST の `d` 日 `hour` 時に予約が1本ある、という控えの行。"""
    t = datetime(d.year, d.month, d.day, hour, 0, tzinfo=JST)
    return {"video_id": "x", "at": t.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")}


def _full(today: date) -> list[dict]:
    """今日から `LEAD_DAYS` 日ぶん、毎日1本ずつ埋まっている控え。"""
    return [_row(today + timedelta(days=i)) for i in range(slot_gate.LEAD_DAYS + 1)]


def test_埋まっている日には黙る():
    today = date(2026, 9, 1)
    assert slot_gate.empty_days(_full(today), today) == []
    assert slot_gate.lines(_full(today), today) == []


def test_故障を注入すると発火する_穴が1日():
    """**注入する故障**: 明後日の1本を控えから抜く。"""
    today = date(2026, 9, 1)
    rows = _full(today)
    hole = today + timedelta(days=slot_gate.LEAD_DAYS)
    rows = [r for r in rows if not r["at"].startswith(
        datetime(hole.year, hole.month, hole.day, 22, tzinfo=JST)
        .astimezone(timezone.utc).strftime("%Y-%m-%dT%H"))]
    assert slot_gate.empty_days(rows, today) == [hole]
    out = "\n".join(slot_gate.lines(rows, today))
    assert f"{hole:%m/%d}" in out
    assert "予約まで入れる" in out


def test_控えが空なら_今日から全部が穴():
    today = date(2026, 9, 1)
    assert slot_gate.empty_days([], today) == [
        today + timedelta(days=i) for i in range(slot_gate.LEAD_DAYS + 1)]


def test_穴の先に作り置きが在れば_そう言う():
    """**「まだ作っていない」と「作ってあるのに出さない」は別のことです。**

    先に予約が並んでいるのに手前が0本なら、後者。文面が変わります。
    """
    today = date(2026, 9, 1)
    far = [_row(today + timedelta(days=n)) for n in (20, 21, 22)]
    out = "\n".join(slot_gate.lines(far, today))
    assert "作ってあるのに出さない" in out
    assert slot_gate.tail_days(far, today) == 3
    # 穴の先に何も無ければ、その文は出ない
    assert "作ってあるのに出さない" not in "\n".join(slot_gate.lines([], today))


def test_詰めろとは一度も言わない():
    """規則2（作り置きなし）の下で `--compact` を案内すると、`pool_drain` が
    同じ本を外します。**この門が言うのは「1本 作って入れろ」だけ**です。"""
    today = date(2026, 9, 1)
    out = "\n".join(slot_gate.lines([], today))
    assert "--compact" not in out or "それでも詰めないこと" in out
    assert "reschedule.py --compact" not in out


def test_gate_の終了コード():
    """`--gate` は、穴があるとき **2** で返ること（`stop_check.sh` がこれを見ます）。"""
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "slot_gate.py"), "--gate"],
                       cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert r.returncode in (0, 2), r.stderr[-400:]
    if r.returncode == 2:
        assert "予約が0本の日" in r.stdout


def test_門が_stop_check_に配線されている():
    """**撃たれない道具の効果はゼロ。** 配線が外れたら、ここが赤くなります。"""
    hook = (ROOT / "scripts" / "stop_check.sh").read_text(encoding="utf-8")
    assert "scripts/slot_gate.py --gate" in hook
    assert "SLOTGATE" in hook
    # 3回で通すこと（日枠が尽きて撃てない回を、永久に止めないため）
    assert 'SN" -lt 3' in hook


def test_stop_check_のメニューに_improve_が在る():
    """オーナー規則3（2026-08-31）で §4 は5つになりました。
    **実際に回を止めている側のメニューが4つのままだと、規則3 は選ばれません。**"""
    hook = (ROOT / "scripts" / "stop_check.sh").read_text(encoding="utf-8")
    menu = hook.split("この回はまだ何も出していません】")[1][:1200]
    for kind in ("upload", "improve", "means", "verdict", "fix"):
        assert f"  {kind}" in menu, kind
