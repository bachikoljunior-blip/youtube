"""**見分けた 403 が、帳面に残るか**（2026-08-19 に足した）。

`test_day_quota.py` は「見分けられるか」と「残っていれば効くか」を調べています。
**そのあいだが抜けていました** —— 見分けた側が、残す側を呼んでいるか。

## 実測（この検査を書いた回の入口）

窓は 2026-08-18 07:00Z → 08-19 07:00Z。この窓の中で:

    status.py が channels.list / videos.list で **403 quotaExceeded**（4回）
    前の回の `videos.update` も **403**（受け取り帳 556dd42d が開いたまま）

それでも `data/day_quota.jsonl` の**この窓の行は 0件**で、
`upload_cap.day_quota()` は **open=True**（＝「まだ押してよい」）と答えました。
**`retro.py` と `status.py` が読む「単位が残っているか」が、事実と逆でした。**

理由は1つで、`auth.is_day_quota` の docstring が
「当たったら `note_quota_hit()` に残すこと」と**約束の形**で書いてあったこと。
残していたのは `thumbnails.set` の2か所だけで、
`history` 4件・`uploader` 5件・`reschedule` 1件・`status` 1件は素通しでした。

**この repo が通算10回踏んでいる「片方だけ」の11件目です。**
だから約束をやめて、**見分けと記録を1つにした**（`auth.note_day_quota`）うえで、
**忘れた呼び出し側を、この検査が名指しします。**
"""
from __future__ import annotations

import ast
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import auth, upload_cap  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
JST = timezone(timedelta(hours=9))

# **Data API（10,000単位）を叩くファイル**だけを見ます。
# `src/analytics.py` と `scripts/search_terms.py` / `scripts/watch_source.py` は
# **YouTube Analytics（別枠）**なので入れません —— あちらの 403 をこの帳面に
# 書くと、**尽きていない窓を「尽きた」と誤らせます**（外す向きが逆）。
DATA_API_FILES = [
    "src/history.py",
    "src/uploader.py",
    "scripts/reschedule.py",
]


def _jst(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=JST)


def _root(tmp_path, monkeypatch):
    from src import config

    monkeypatch.setattr(config, "ROOT", tmp_path)
    return tmp_path


class _Resp:
    def __init__(self, status):
        self.status = status


class _FakeHttpError(Exception):
    def __init__(self, status, text):
        super().__init__(text)
        self.resp = _Resp(status)
        self.content = text.encode("utf-8")


_QUOTA = ("<HttpError 403 when requesting https://youtube.googleapis.com/youtube/v3/"
          'videos returned "The request cannot be completed because you have exceeded '
          'your <a href=\\"/youtube/v3/getting-started#quota\\">quota</a>.". '
          'Details: "[{\'message\': \'...\', \'reason\': \'quotaExceeded\'}]"')


# --- 記録する側 -------------------------------------------------------------

def test_note_day_quota_records_and_reports(tmp_path, monkeypatch):
    _root(tmp_path, monkeypatch)
    assert upload_cap.quota_hits_in_window(_jst("2026-08-18 22:00")) == []

    assert auth.note_day_quota(_FakeHttpError(403, _QUOTA), "videos.update X") is True

    hits = upload_cap.quota_hits_in_window()
    assert len(hits) == 1
    assert "videos.update X" in hits[0]["detail"]


def test_note_day_quota_ignores_other_errors(tmp_path, monkeypatch):
    _root(tmp_path, monkeypatch)
    # 権限の 403 は**待っても直らない別物**。混ぜると窓を誤って閉じます。
    assert auth.note_day_quota(_FakeHttpError(403, "403 insufficientPermissions")) is False
    assert auth.note_day_quota(_FakeHttpError(429, "429 rateLimitExceeded Video Uploads")) is False
    assert upload_cap.quota_hits_in_window() == []


def test_note_day_quota_survives_a_broken_ledger(tmp_path, monkeypatch):
    """**帳面に書けなくても、判定は返すこと。**

    書けないことを理由に呼ぶ側の分岐を変えると、
    `upload_cap.state()` の考え方と食い違います（読めない＝止めない）。
    """
    _root(tmp_path, monkeypatch)
    monkeypatch.setattr(upload_cap, "note_quota_hit",
                        lambda **kw: (_ for _ in ()).throw(OSError("read-only")))
    assert auth.note_day_quota(_FakeHttpError(403, _QUOTA), "x") is True


def test_recorded_hit_closes_the_window(tmp_path, monkeypatch):
    """記録が `day_quota()` にそのまま効くこと（**入口と出口を繋ぐ1本**）。"""
    _root(tmp_path, monkeypatch)
    assert upload_cap.day_quota().open is True
    auth.note_day_quota(_FakeHttpError(403, _QUOTA), "videos.update X")
    state = upload_cap.day_quota()
    assert state.open is False and state.observed is True


# --- 忘れた呼び出し側を名指しする（**約束ではなく検査で持たせる**）----------

def _handlers(path: Path):
    """`except HttpError ...` の受け口を全部返す。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler) or node.type is None:
            continue
        names = {n.id for n in ast.walk(node.type) if isinstance(n, ast.Name)}
        if "HttpError" in names:
            out.append(node)
    return out


# `_note_cap` は `videos.insert` が落ちる**唯一の口**（`src/uploader.py`）で、
# 中で両方の枠を残します。**間に1枚だけ挟まる形を許すので、
# その1枚が本当に残しているかは、下の検査が別に見ています。**
RECORDERS = {"note_day_quota", "_note_cap"}


def _mentions_note(node: ast.AST) -> bool:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            fn = sub.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            if name in RECORDERS:
                return True
    return False


def test_note_cap_itself_records_the_403():
    """**間に挟まる1枚のほうも確かめる**（許した抜け道を、開けっ放しにしない）。"""
    from src import uploader

    tree = ast.parse(Path(uploader.__file__).read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_note_cap")
    assert _mentions_note(fn), "`_note_cap` が日枠の 403 を残していません"


def _only_reraises(node: ast.ExceptHandler) -> bool:
    """中身が `raise`（素通し）だけの受け口は、上で見てもらえば足ります。"""
    return all(isinstance(st, ast.Raise) for st in node.body)


def test_every_data_api_handler_records_the_403():
    missed = []
    for rel in DATA_API_FILES:
        path = ROOT / rel
        for node in _handlers(path):
            if _mentions_note(node) or _only_reraises(node):
                continue
            missed.append(f"{rel}:{node.lineno}")
    assert not missed, (
        "**Data API の 403 を受けているのに、帳面に残していない受け口があります**: "
        + ", ".join(missed)
        + "\n  → その `except HttpError as exc:` の先頭で "
          "`auth.note_day_quota(exc, \"<呼んだAPI>\")` を呼ぶこと。"
          "\n  残さないと `upload_cap.day_quota()` が「まだ押せる」と答え続け、"
          "次の回が同じ 403 をもう一度買います（2026-08-19 の実測）。"
    )
