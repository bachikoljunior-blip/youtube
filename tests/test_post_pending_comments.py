"""**最初のコメントが、`build/` の無いコンテナでも付くこと**（2026-09-03 04:xx）。

## なぜ要るか

`scripts/post_pending_comments.py` は `build/<題材>/script.json` だけを読んでいました。
`build/` は `.gitignore` に在り、サブの回のまっさらなコンテナには無い ——
**撃つと必ず 0本**（実測 `data/api_calls.jsonl` 08/31〜: `commentThreads` 0件）。
規則5（下書きで上げて当日に予約）の下では全部の本が private で上がるので、
`uploader._post_actions` の insert は毎本 403 で落ち、拾う口がこの道具しか無い。
＝ **09/01 から出た本に、最初のコメントは1本も付いていませんでした。**

申し送りは 6周 続けて「16:00 以降の回で `post_pending_comments.py`」と運び、
実物に当たった回は 0（`retro.py` の持ち越し）。**憶えておく形は撃たれません** ——
`ahead_sweep.comment_pending()` が `kick()` から 20分ごとに通します。

## 覆る条件

- `critique_queue.stash()` が `.script.json` を控えに写さなくなったら、控えの側の
  検査は意味を失う（そのときは `first_comment` の置き場を先に決め直すこと）
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import critique_queue  # noqa: E402

_pspec = importlib.util.spec_from_file_location(
    "post_pending_comments_mod", ROOT / "scripts" / "post_pending_comments.py")
ppc = importlib.util.module_from_spec(_pspec)
_pspec.loader.exec_module(ppc)

_gspec = importlib.util.spec_from_file_location(
    "ahead_gate_for_ppc", ROOT / "scripts" / "ahead_gate.py")
ahead_gate = importlib.util.module_from_spec(_gspec)
sys.modules.setdefault("ahead_gate", ahead_gate)
_gspec.loader.exec_module(ahead_gate)
_sspec = importlib.util.spec_from_file_location(
    "ahead_sweep_for_ppc", ROOT / "scripts" / "ahead_sweep.py")
sweep = importlib.util.module_from_spec(_sspec)
_sspec.loader.exec_module(sweep)

NOW = datetime(2026, 9, 3, 8, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------- 控え（0単位）
def _stash(tmp_path, monkeypatch, *rows):
    """rows: (video_id, first_comment, meta_extra)"""
    monkeypatch.setattr(critique_queue, "STASH", tmp_path)
    for vid, comment, extra in rows:
        (tmp_path / f"{vid}.script.json").write_text(
            json.dumps({"title": "t", "first_comment": comment}), encoding="utf-8")
        meta = {"video_id": vid, "topic": f"s-{vid}", **extra}
        (tmp_path / f"{vid}.json").write_text(json.dumps(meta), encoding="utf-8")


def test_控えから_未処理の本だけ出る(tmp_path, monkeypatch):
    _stash(tmp_path, monkeypatch,
           ("A", "一言", {}),
           ("B", "済み", {"first_comment_posted": True}),
           ("C", "", {}))                                      # コメント無し
    got = {r["video_id"]: r["comment"] for r in critique_queue.pending_first_comments()}
    assert got == {"A": "一言"}


def test_印を付けると_次から出ない(tmp_path, monkeypatch):
    _stash(tmp_path, monkeypatch, ("A", "一言", {}))
    monkeypatch.setenv("YT_LEDGER_WRITE", "1")                 # tmp なので書いてよい
    assert critique_queue.mark_first_comment_posted("A") is True
    assert critique_queue.pending_first_comments() == []
    assert critique_queue.mark_first_comment_posted("ZZZ") is False


def test_build_が無くても_控えだけで動く(tmp_path, monkeypatch, capsys):
    """**踏んだ形そのもの。** `build/` が無い ＝ `build={}`。控えに1本 在れば API を撃つ。"""
    _stash(tmp_path, monkeypatch, ("A", "一言", {}))
    assert not (ROOT / "build").exists() or True             # 実物の有無に依らない
    yt = _FakeYouTube(public={"A"}, mine=set())
    marked: list[str] = []
    rc = ppc.main(False, service=lambda: yt, reserve_hold=lambda: None,
                  note_ok=lambda d: None, mark=marked.append, build={})
    assert rc == 0
    assert yt.inserted == [("A", "一言")]
    assert marked == ["A"]
    assert "付けたコメント: 1件" in capsys.readouterr().out


def test_控えも_build_も空なら_API_を呼ばない(tmp_path, monkeypatch, capsys):
    _stash(tmp_path, monkeypatch)
    called = []
    rc = ppc.main(False, service=lambda: called.append(1), build={})
    assert rc == 0 and called == []
    assert "API は呼びません" in capsys.readouterr().out


def test_private_の本は飛ばし_印も付けない(tmp_path, monkeypatch):
    _stash(tmp_path, monkeypatch, ("A", "一言", {}))
    yt = _FakeYouTube(public=set(), mine=set())
    marked: list[str] = []
    ppc.main(False, service=lambda: yt, reserve_hold=lambda: None,
             note_ok=lambda d: None, mark=marked.append, build={})
    assert yt.inserted == [] and marked == []
    assert yt.listed_threads == []                             # private には list も撃たない


def test_自分のコメントが既に在れば_付けずに印だけ(tmp_path, monkeypatch):
    _stash(tmp_path, monkeypatch, ("A", "一言", {}))
    yt = _FakeYouTube(public={"A"}, mine={"A"})
    marked: list[str] = []
    ppc.main(False, service=lambda: yt, reserve_hold=lambda: None,
             note_ok=lambda d: None, mark=marked.append, build={})
    assert yt.inserted == [] and marked == ["A"]


def test_取り置きの門で止まる(tmp_path, monkeypatch, capsys):
    _stash(tmp_path, monkeypatch, ("A", "一言", {}), ("B", "二言", {}))
    yt = _FakeYouTube(public={"A", "B"}, mine=set())
    ppc.main(False, service=lambda: yt, reserve_hold=lambda: "残り 350単位",
             note_ok=lambda d: None, mark=lambda v: None, build={})
    assert yt.inserted == []
    assert "ここで止めます" in capsys.readouterr().out


def test_dry_run_は付けない(tmp_path, monkeypatch, capsys):
    _stash(tmp_path, monkeypatch, ("A", "一言", {}))
    yt = _FakeYouTube(public={"A"}, mine=set())
    ppc.main(True, service=lambda: yt, reserve_hold=lambda: None,
             note_ok=lambda d: None, mark=lambda v: None, build={})
    assert yt.inserted == []
    assert "[post] A" in capsys.readouterr().out


def test_禁じた語の入ったコメントは付けない(tmp_path, monkeypatch, capsys):
    _stash(tmp_path, monkeypatch, ("A", "GitHub に置いた", {}))
    yt = _FakeYouTube(public={"A"}, mine=set())
    ppc.main(False, service=lambda: yt, reserve_hold=lambda: None,
             note_ok=lambda d: None, mark=lambda v: None, build={})
    assert yt.inserted == []
    assert "[skip] A" in capsys.readouterr().out


# ---------------------------------------------------------------- 掃きからの口
def test_掃きは_未処理が無ければ_API_を呼ばない(capsys):
    ran: list[list[str]] = []
    line = sweep.comment_pending(NOW, pending=[], quota_open=True, run=ran.append)
    assert ran == [] and "0単位" in line


def test_掃きは_日枠が尽きていれば通さない():
    ran: list[list[str]] = []
    line = sweep.comment_pending(NOW, pending=[{"video_id": "A"}], quota_open=False,
                                 run=lambda a: ran.append(a) or 0)
    assert ran == [] and "日枠" in line


def test_掃きは_未処理が在れば_道具を通す():
    ran: list[list[str]] = []
    line = sweep.comment_pending(NOW, pending=[{"video_id": "A"}], quota_open=True,
                                 run=lambda a: ran.append(a) or 0)
    assert len(ran) == 1 and ran[0][-1].endswith("scripts/post_pending_comments.py")
    assert "通しました" in line


def test_掃きの_dry_run_は道具にも渡る():
    ran: list[list[str]] = []
    sweep.comment_pending(NOW, dry_run=True, pending=[{"video_id": "A"}], quota_open=True,
                          run=lambda a: ran.append(a) or 0)
    assert ran[0][-1] == "--dry-run"


def test_掃きの_main_が_thumb_today_の後に呼ぶこと():
    import inspect
    src = inspect.getsource(sweep.main)
    assert "comment_pending(" in src, "掃きの main が最初のコメントの口を呼んでいません"
    assert src.index("thumb_today(") < src.index("comment_pending("), \
        "サムネイル（きょうの1本・50単位）より先にコメントへ単位を回さないこと"


# ---------------------------------------------------------------- 偽の YouTube
class _Call:
    def __init__(self, result):
        self._r = result

    def execute(self):
        return self._r


class _FakeYouTube:
    """`videos.list`（ID指定）／`commentThreads.list`／`commentThreads.insert` だけ。"""
    CHANNEL = "UC-me"

    def __init__(self, *, public: set[str], mine: set[str]):
        self.public, self.mine = public, mine
        self.inserted: list[tuple[str, str]] = []
        self.listed_threads: list[str] = []

    def videos(self):
        fake = self

        class V:
            def list(self, part, id):
                items = [{"id": vid, "snippet": {"channelId": fake.CHANNEL, "description": ""},
                          "status": {"privacyStatus":
                                     "public" if vid in fake.public else "private"}}
                         for vid in id.split(",")]
                return _Call({"items": items})
        return V()

    def commentThreads(self):                                  # noqa: N802
        fake = self

        class C:
            def list(self, part, videoId, maxResults, textFormat):   # noqa: N803
                fake.listed_threads.append(videoId)
                items = ([{"snippet": {"topLevelComment": {"snippet": {
                    "authorChannelId": {"value": fake.CHANNEL}}}}}]
                    if videoId in fake.mine else [])
                return _Call({"items": items})

            def insert(self, part, body):
                sn = body["snippet"]
                fake.inserted.append((sn["videoId"],
                                      sn["topLevelComment"]["snippet"]["textOriginal"]))
                return _Call({})
        return C()

    def channels(self):
        raise AssertionError("控えだけの回は channels.list を撃たない")
