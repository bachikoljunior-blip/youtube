"""代の深さ（`sibling_check.lineage_depth` / `report_depth`）の検査。

## なぜ要るか（2026-08-17 に実測して足した）

鎖は8代で必ず切れます（`create_session: lineage depth 8 (limit 8)`）。
**それ自体は異常ではありません。** 問題は**気づく時刻**でした ——
深さが分かるのが §6 (f)、つまり1周の終わりぎわなので、
分かったところで手の打ちようがありません。

実測（8/16 16:04〜8/17 20:12 の25件。**深さ8以外の間隔は全部 41〜43分**）:

    深さ8が終わった   次の子が生まれた   空き
    23:28            00:13             45分
    04:18            05:10             52分
    10:16            11:12             56分

親は毎時 9分に撃ちますが、**走っている子がいると立てません。**
1周が42分なので :09 は7割の確率で「まだ走っている最中」に当たり、
見送られると**まるまる1時間**あきます。**7周に1回、ほぼ1周ぶんが消えていました。**

深さは `list_sessions` の返りだけで求まります（API も追加の呼び出しも不要）。
**§2 で出せば、締切に間に合わせられます。**
"""
from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "sibling_check_for_test",
    Path(__file__).resolve().parent.parent / "scripts" / "sibling_check.py")
sc = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(sc)

ROOT = "session_root_parent"


def chain(n: int, root: str = ROOT, extra: int = 0) -> list[dict]:
    """根から `n` 代ぶんの鎖を作る（返るのは行の一覧）。

    `extra` は「同じ根から立った別の鎖の先頭」の本数。
    **根の自動判定は「2件以上の行の親になっていること」**なので、
    1本しか鎖が無い窓では根が見つからない（＝下限で答える）。
    """
    rows = []
    parent = root
    for i in range(n - 1):                       # 根は行として現れない
        sid = f"session_c{i}"
        rows.append({"id": sid, "created_at": f"2026-08-17T{i:02d}:00:00Z",
                     "parent_session_id": parent, "tags": [sc.TAG]})
        parent = sid
    for j in range(extra):
        rows.append({"id": f"session_other{j}", "created_at": "2026-08-16T00:00:00Z",
                     "parent_session_id": root, "tags": [sc.TAG]})
    return rows


def test_根から立った子は深さ2():
    rows = chain(2, extra=1)
    assert sc.lineage_depth(rows, "session_c0") == (2, True)


def test_8代目は上限ちょうどで正確に出る():
    rows = chain(8, extra=1)
    depth, exact = sc.lineage_depth(rows, "session_c6")
    assert (depth, exact) == (8, True)
    assert depth >= sc.DEPTH_LIMIT


def test_鎖が一覧の外へ出たら下限として返す():
    """**ここを「深さ」と言い切ると、8代目を7代目と読みます。**"""
    rows = chain(4, extra=1)
    rows = [r for r in rows if r["id"] != "session_c0"]   # 途中の1件を落とす
    depth, exact = sc.lineage_depth(rows, "session_c2")
    assert exact is False
    assert depth <= 4                                     # 下限なので本当の値以下


def test_根が1件しか親になっていなければ根と読まない():
    """25件の窓からこぼれ落ちただけの、ふつうの子を根と読まないこと。

    実データで踏んだ形（8/16 16:04 の行の親 `session_016Gas…`）。
    根と読むと、**深さが4代ぶん過小に出ます。**
    """
    rows = chain(3)                                       # extra=0 ＝ 鎖は1本だけ
    assert sc.spawn_roots(rows) == set()
    depth, exact = sc.lineage_depth(rows, "session_c1")
    assert exact is False


def test_根を明示すれば1本の鎖でも正確に出る():
    rows = chain(3)
    assert sc.lineage_depth(rows, "session_c1", root=ROOT) == (3, True)


def test_環になっていても止まる():
    rows = [{"id": "session_a", "parent_session_id": "session_b", "tags": [sc.TAG]},
            {"id": "session_b", "parent_session_id": "session_a", "tags": [sc.TAG]}]
    depth, exact = sc.lineage_depth(rows, "session_a")
    assert exact is False and depth <= 3


@pytest.mark.parametrize("now_min, want_hour", [
    (0, 9),       # :00 → **同じ時**の :09（まだ来ていない）
    (9, 10),      # ちょうど :09 → もう撃った後なので次の時
    (30, 10),     # :30 → 次の時
])
def test_次の発火は必ず未来の09分(now_min, want_hour):
    """**「同じ時の :09」と「次の時の :09」を取り違えないこと。**

    取り違えると締切が1時間ずれ、この直しがそのまま逆に効きます。
    """
    now = datetime(2026, 8, 17, 9, now_min, tzinfo=timezone.utc)
    fire = sc.next_parent_fire(now, 9)
    assert fire > now
    assert (fire.hour, fire.minute) == (want_hour, 9)
    assert fire - now <= timedelta(hours=1)


def test_発火の直前に呼ばれたら次の時に送る():
    """**残り1分で「1分で畳め」と言わないこと。** 言えるのは次の発火です。"""
    rows = chain(8, extra=1)
    now = datetime(2026, 8, 17, 9, 8, tzinfo=timezone.utc)   # 発火まで1分
    fire = sc.next_parent_fire(now, 9)
    deadline = fire - timedelta(minutes=sc.ARCHIVE_MARGIN_MIN)
    assert deadline <= now                                   # ← 間に合わない
    # `report_depth` はこの場合、次の発火（+1時間）に送る
    assert sc.report_depth(rows, "session_c6", now, 9) is True


def test_壁の手前では壁だと言わない(capsys):
    rows = chain(7, extra=1)
    now = datetime(2026, 8, 17, 9, 0, tzinfo=timezone.utc)
    assert sc.report_depth(rows, "session_c5", now, 9) is False
    out = capsys.readouterr().out
    assert "7 / 8" in out
    assert "立てられません" not in out


def test_壁では締切を必ず印字する(capsys):
    rows = chain(8, extra=1)
    now = datetime(2026, 8, 17, 9, 30, tzinfo=timezone.utc)  # JST 18:30
    assert sc.report_depth(rows, "session_c6", now, 9) is True
    out = capsys.readouterr().out
    assert "8 / 8" in out
    assert "archive" in out
    assert "19:07" in out          # 次の発火 19:09 JST の2分前
    assert "残り" in out
