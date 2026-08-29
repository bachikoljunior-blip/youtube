"""**`--plan` が、この窓では撃てない本を組まないこと**（2026-08-29 に測って足した）。

## なぜ要るか（**3周 続けて、同じ 29日 が約束されて 0日 で着いていました**）

`scripts/queue_lag.py` の入れ替えは、`src.upload_cap.MOVE_CAP`（1本 2回/窓）に
当たった本を**撃てません**。`scripts/reschedule.py` は当たると `RC_NOT_MOVED` を返し、
`apply_moves` はその組を捨てます —— **そこまでは正しい。壊れません。**

**壊れているのは、約束のほうでした。** 実測（2026-08-29 15:2x・`--plan`）:

    入れ替え 10手（20回の `--move`）・**合計 34日** と印字
      → そのうち **8回 が `move_hold` で止まる本**（**10手 中 7手 が落ちる**）
      → `opening_motion` の対照は 8本ちょうど なので
        （`Plan.potential()` の註「4本を全部 前へ出すまで 1日も縮みません」）、
        **1本 落ちれば その 29日 は丸ごと 0日**

そして `data/queue_lag.jsonl` の `after` は毎回 `before` と違うので、道具は
「**手は当たっている ＝ きょうだいが書き戻した側だ**」と診断していました。
**診断のほうが外れています** —— 当たったのは残りの3手で、落ちた7手は
最初から撃たれていません。

## 直し方（**組む前に篩う。撃つ直前に止めるのでは遅い**）

`Plan.__init__` が `upload_cap.move_blocked()` を**1回だけ**読み、
`_pull()` が **早める側と後ろへ送る側の両方**から外します。
実測（同じ回・直した直後）:

    直す前  10手／約束 34日／**そのうち 8回 が止まる本**
    直した後 9手／約束 30日／**止まる本 0回**（`opening_motion` 27日）

**日数が 34 → 30 に減ったのは、悪化ではありません。**
34 は着かない数で、30 は着く数です。しかも入れ替え先を選び直したので、
**`opening_motion` は 29日 → 27日 しか落ちていません**（残り8本の中から
別の本が見つかった）。**「候補を狭めたら手が消える」ではありませんでした。**

## 覆る条件

- `MOVE_CAP` を上げるか、掃きが収束して `moves_in_window` が 2 に張り付かなく
  なったら、`move_blocked()` は空を返し、この検査は**素通り**します（無害）
- `YT_NO_MOVE_CAP=1` / `YT_FORCE_UPDATE` のときも空です（`move_blocked` の註）
"""
from __future__ import annotations

import ast
import json
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import upload_cap  # noqa: E402


def _ledger(tmp_path, details):
    """窓の中に「通った」行を並べた帳面を作り、`_root()` をそこへ向ける。

    本物の repo を指しているあいだ、`moves_in_window` は検査から 0 を返します
    （`_write_path` の対）。差し替え先は `_REPO` と違うので普通に数えます。
    """
    (tmp_path / "data").mkdir(exist_ok=True)
    mid = upload_cap.window_start() + timedelta(hours=1)
    rows = [{"at": (mid + timedelta(minutes=i)).isoformat(), "ok": True, "detail": d}
            for i, d in enumerate(details)]
    (tmp_path / upload_cap.DAY_QUOTA_HITS).write_text(
        "\n".join(json.dumps(r) for r in rows), encoding="utf-8")


def test_move_blocked_は_move_hold_と同じ本を指すこと(tmp_path, monkeypatch):
    """**2つの門が食い違ったら、篩と実物がずれます。**

    `_pull()` は `move_blocked()` で篩い、`reschedule` は `move_hold()` で止めます。
    片方だけ直すと、篩を通った本が撃つ直前で止まります（＝直す前に戻ります）。
    """
    monkeypatch.setattr(upload_cap, "_root", lambda: tmp_path)
    monkeypatch.delenv("YT_NO_MOVE_CAP", raising=False)
    monkeypatch.delenv("YT_FORCE_UPDATE", raising=False)
    _ledger(tmp_path, [
        "videos.update hitCap", "videos.update hitCap",   # 2回 ＝ 上限
        "videos.update once",                              # 1回 ＝ まだ撃てる
        "videos.update thrice", "videos.update thrice", "videos.update thrice",
    ])
    blocked = upload_cap.move_blocked()
    for vid in ("hitCap", "once", "thrice", "never"):
        assert (vid in blocked) == bool(upload_cap.move_hold(vid)), (
            f"`move_blocked()` と `move_hold()` が {vid} で食い違っています。"
            "篩と、撃つ直前の門は同じ本を指すこと")
    assert blocked == {"hitCap", "thrice"}


def test_moves_by_video_は_moves_in_window_と同じ数を返すこと(tmp_path, monkeypatch):
    """**1本ずつ数える版と、まとめて数える版が同じであること。**

    まとめる版を足したのは速さのためだけです（実測 11ms/本 → 21ms/回）。
    数え方（`ok` の行だけ・`dedupe_ok`・印の付いた行を除く）が
    ずれたら、篩が別のものを篩います。
    """
    monkeypatch.setattr(upload_cap, "_root", lambda: tmp_path)
    _ledger(tmp_path, [
        "videos.update a", "videos.update a", "videos.update b",
        "videos.update b link",          # 印つき ＝ 予約を動かしていない
        "videos.update c retitle",       # 同上
        "videos.insert d",               # そもそも update ではない
    ])
    counts = upload_cap.moves_by_video()
    for vid in ("a", "b", "c", "d", "zzz", "link", "retitle"):
        assert counts.get(vid, 0) == upload_cap.moves_in_window(vid), (
            f"{vid} の数が2つの版で食い違っています")
    assert counts == {"a": 2, "b": 1}, (
        "**印の付いた行の末尾を、本の名前として数えていませんか。**\n"
        "`videos.update b link` の末尾は `link` です —— 末尾の1語で数えると"
        "『`link` という本を1回 動かした』が生まれます。無害に見えるのは"
        "動画IDが 11文字 で `link` になり得ないからだけで、"
        "**印が1つ増えるたびに幻も1つ増えます**")


def test_YT_NO_MOVE_CAP_のときは篩が空であること(tmp_path, monkeypatch):
    """逃げ道は `move_hold()` と同じ形であること（外した回は理由を JOURNAL に）。"""
    monkeypatch.setattr(upload_cap, "_root", lambda: tmp_path)
    _ledger(tmp_path, ["videos.update x", "videos.update x"])
    assert upload_cap.move_blocked() == {"x"}
    monkeypatch.setenv("YT_NO_MOVE_CAP", "1")
    assert upload_cap.move_blocked() == frozenset(), (
        "`YT_NO_MOVE_CAP=1` で篩が空になりません。"
        "`move_hold()` は空けているので、篩だけが止め続けます")


def test_pull_が両側とも_blocked_を外していること():
    """**早める側だけ外して安心しない。** 後ろへ送る側も `--move` を1回 使います。

    ソースを読むのは、`Plan()` が本物の予約（`scheduled()`）を要るからです ——
    検査の中で組むと、その日の口の中身に依存して落ちます。
    **見るのは「両方の内包表記に門があるか」だけ**なので、
    `_pull()` の書き方が変わっても、門が残っていれば通ります。
    """
    src = (ROOT / "scripts" / "queue_lag.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "_pull"), None)
    assert fn is not None, "`Plan._pull` が見つかりません"
    comps = [n for n in ast.walk(fn) if isinstance(n, ast.GeneratorExp)]
    assert len(comps) >= 2, (
        "`_pull` の候補づくりが2つありません（早める側／後ろへ送る側）")
    guarded = 0
    for c in comps:
        text = ast.unparse(c)
        if "self.blocked" in text:
            guarded += 1
    assert guarded >= 2, (
        "**`_pull` の候補のうち、`self.blocked` の門が付いていない側があります。**\n"
        "早める側と後ろへ送る側の両方が `--move` を1回ずつ使うので、"
        "片側だけ篩っても組は落ちます（実測 2026-08-29: 20回中 8回 が止まる本で、"
        "10手 中 7手 が落ちていました）")


def test_blocked_lines_が窓の変わる時刻を出すこと():
    """**「動きません」と「この窓では撃てない」を分けること。**

    篩を足したことで、`opening_motion` のように**手が実在するのに
    この窓では撃てない**前提が「（動きません）」と出るようになりました。
    そのまま出すと、次に来た側は「もう縮まない」と読みます。
    `blocked_lines()` が**窓の変わる時刻**を出すのは、そのためです。
    """
    src = (ROOT / "scripts" / "queue_lag.py").read_text(encoding="utf-8")
    assert "def blocked_lines" in src and "def blocked_held" in src, (
        "`blocked_lines` / `blocked_held` が消えています")
    tree = ast.parse(src)
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "gain_lines"), None)
    assert fn is not None and "self.blocked_lines()" in ast.unparse(fn), (
        "**`gain_lines()` が `blocked_lines()` を呼んでいません。**\n"
        "呼ばないと、『この窓では撃てないだけ』が『動きません』に化けて、"
        "次の回が実在する手を捨てます")
    assert "window_end" in ast.unparse(
        next(n for n in ast.walk(tree)
             if isinstance(n, ast.FunctionDef) and n.name == "blocked_lines")), (
        "`blocked_lines()` が窓の変わる時刻を出していません —— "
        "その時刻が無いと、いつ撃ち直せばよいか誰にも分かりません")
