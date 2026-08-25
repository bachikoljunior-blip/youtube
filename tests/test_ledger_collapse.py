"""**1本の動画は1行**。控えの二重行が「本数」をふくらませないこと。

2026-08-25 の実測（`data/uploaded.jsonl` 518行）:

    27本が2行ずつ（13本は同じ `at`・14本は違う `at`）
    これから公開する行 355 → 実物は 328本 ＝ **幻が 27個**

そのままだと `--spread --per-day 10` が、上限に達していない日から
**実物を 11本**動かします（09/05 12→10・09/06 14→10・09/24 11→8）。
`retime()` の本文は「足すのではなく書き換える」と書いて**書く側**を直しましたが、
行が増える口は他にもあります（git の merge。控えは配られるファイルです）。
**読む側をここで止めます。**
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, dupes  # noqa: E402


def _write(tmp_path, monkeypatch, recs):
    root = tmp_path
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / dupes.LEDGER).write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in recs) + "\n",
        encoding="utf-8")
    monkeypatch.setattr(config, "ROOT", root)
    return root


def _rec(vid, at, topic="t1", title="題", **kw):
    return {"video_id": vid, "topic": topic, "title": title, "at": at,
            "uploaded_at": "2026-08-16T04:13:39+09:00", **kw}


def test_同じ行が2つあっても1本として数える(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, [
        _rec("aaa", "2026-09-05T03:00:00Z"),
        _rec("aaa", "2026-09-05T03:00:00Z"),
        _rec("bbb", "2026-09-05T04:00:00Z"),
    ])
    rows = dupes.ledger_rows()
    assert [r["id"] for r in rows] == ["aaa", "bbb"]


def test_atが食い違う組も1本だが両方の時刻を残す(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, [
        _rec("aaa", "2026-09-22T02:00:00Z"),
        _rec("aaa", "2026-09-23T01:30:00Z"),
    ])
    rows = dupes.ledger_rows()
    assert len(rows) == 1, "**数えるのは1本**（幻の1本を作らない）"
    # **置き場所を避ける側は両方を見る**（どちらが本物かは行から言えない）
    assert set([rows[0]["at"], *rows[0]["at_others"]]) == {
        "2026-09-22T02:00:00Z", "2026-09-23T01:30:00Z"}


def test_retimeを通った行が勝つ(tmp_path, monkeypatch):
    """順番の運に任せない。**`videos.update` が通った側に印がある。**"""
    _write(tmp_path, monkeypatch, [
        _rec("aaa", "2026-09-22T02:00:00Z", retimed_at="2026-08-24T10:00:00+00:00"),
        _rec("aaa", "2026-09-23T01:30:00Z"),          # 印なし・あとの行
    ])
    rows = dupes.ledger_rows()
    assert rows[0]["at"] == "2026-09-22T02:00:00Z"


def test_印が無ければ最後の行が勝つ(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, [
        _rec("aaa", "2026-09-22T02:00:00Z"),
        _rec("aaa", "2026-09-23T01:30:00Z"),
    ])
    assert dupes.ledger_rows()[0]["at"] == "2026-09-23T01:30:00Z"


def test_retimeは印を押す(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, [_rec("aaa", "2026-09-22T02:00:00Z")])
    assert dupes.retime("aaa", "2026-09-20T02:00:00Z") is True
    rec = json.loads((tmp_path / dupes.LEDGER).read_text(encoding="utf-8").strip())
    assert rec["at"] == "2026-09-20T02:00:00Z"
    assert rec.get("retimed_at"), "**印が無いと、merge のあと順番の運になります**"


def test_compactは同じ行だけを落とし食い違いは残す(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, [
        _rec("aaa", "2026-09-05T03:00:00Z"),
        _rec("aaa", "2026-09-05T03:00:00Z"),          # ← これだけ落ちる
        _rec("bbb", "2026-09-22T02:00:00Z"),
        _rec("bbb", "2026-09-23T01:30:00Z"),          # ← 食い違いなので残す
    ])
    out = dupes.compact_ledger()
    assert out["removed"] == 1
    assert set(out["conflicts"]) == {"bbb"}
    left = [json.loads(x) for x in
            (tmp_path / dupes.LEDGER).read_text(encoding="utf-8").splitlines() if x.strip()]
    assert len(left) == 3


def test_置き場所は幻の枠も避ける(tmp_path, monkeypatch):
    """**外す向きは安全・逆向きは1本捨てる**（`batch_build.ledger_hours` の理由）。"""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import batch_build

    _write(tmp_path, monkeypatch, [
        _rec("aaa", "2026-09-22T00:30:00Z"),          # JST 09:30
        _rec("aaa", "2026-09-22T01:30:00Z"),          # JST 10:30（どちらかは幻）
    ])
    taken = batch_build.ledger_minutes("2026-09-22")
    assert taken == {9 * 60 + 30, 10 * 60 + 30}
