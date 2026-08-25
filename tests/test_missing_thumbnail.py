"""**サムネイルの載っていない予約を、控えの側が数えられること**（2026-08-17）。

## なぜこの検査が要るか

日枠が切れている13時間は `thumbnails.set` だけが 403 になり、
`videos.insert` は通ります。**投稿は済んでサムネイルだけ無い予約**が積まれる。

この事実を持っていたのは**日誌の散文だけ**でした。散文は次の回の
「次の回へ」数行にしか残らないので、**3回運ばれて3回とも実行されていません。**
しかも頼まれていた手順（`refresh_thumbnail.py <テーマID> <動画ID> <配色>`）は
`build/<テーマID>/` を読みますが、**`build/` は .gitignore で毎周消えます。**
枠が戻る JST 16:00 には、03時台に上げた本の `build/` はもうありません。
**不可能なことを3回頼み続けていました。**

だから印を控えの側（`data/critique_queue/<動画ID>.json`）に持たせました。
ここが赤いときは、**その印がまた散文に戻っています。**
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import critique_queue  # noqa: E402


@pytest.fixture
def stash(tmp_path, monkeypatch):
    monkeypatch.setattr(critique_queue, "STASH", tmp_path)
    return tmp_path


def _write(stash: Path, video_id: str, *, thumbnail_set, with_bytes: bool = True):
    (stash / f"{video_id}.json").write_text(
        json.dumps({"video_id": video_id, "topic": f"s-{video_id}",
                    "stashed_at": "2026-08-17T05:00:00+09:00",
                    "narration": ["あ"], "thumbnail_set": thumbnail_set},
                   ensure_ascii=False),
        encoding="utf-8")
    if with_bytes:
        (stash / f"{video_id}.thumb.jpg").write_bytes(b"\xff\xd8\xff")


def test_載っていない本だけを返す(stash):
    _write(stash, "aaa", thumbnail_set=False)
    _write(stash, "bbb", thumbnail_set=True)
    got = [r["video_id"] for r in critique_queue.missing_thumbnail()]
    assert got == ["aaa"], "載っている本まで押し直しにいこうとしています"


def test_分からない本は返さない(stash):
    """**`None` を `False` と混ぜないこと。**

    この印より前に上げた本は `thumbnail_set` を持ちません。
    「分からない」を「載っていない」と読むと、**控えにある全部を押しにいきます。**
    """
    _write(stash, "aaa", thumbnail_set=None)
    (stash / "ccc.json").write_text(
        json.dumps({"video_id": "ccc", "narration": ["あ"]}), encoding="utf-8")
    (stash / "ccc.thumb.jpg").write_bytes(b"\xff\xd8\xff")
    assert critique_queue.missing_thumbnail() == []


def test_bytesの無い本は返さない(stash):
    """押すものが無いのに一覧に出すと、**毎回鳴って毎回何もできません。**"""
    _write(stash, "aaa", thumbnail_set=False, with_bytes=False)
    assert critique_queue.missing_thumbnail() == []


def test_plan_jsonを本体と読み違えない(stash):
    """`*.plan.json` は `*.json` の glob に当たります（実際に踏んだ形）。"""
    _write(stash, "aaa", thumbnail_set=False)
    (stash / "aaa.plan.json").write_text("[]", encoding="utf-8")
    assert [r["video_id"] for r in critique_queue.missing_thumbnail()] == ["aaa"]


def test_押せたら印が消える(stash):
    _write(stash, "aaa", thumbnail_set=False)
    assert critique_queue.mark_thumbnail_set("aaa") is True
    assert critique_queue.missing_thumbnail() == []


def test_知らない動画IDでは落ちない(stash):
    """`--missing` は1本落ちても止まりません。ここで例外を上げると止まります。"""
    assert critique_queue.mark_thumbnail_set("zzz") is False


def test_壊れた_json_で落ちない(stash):
    """1本の壊れで残り全部を数えられなくなるのが、いちばん高い壊れ方です。"""
    _write(stash, "aaa", thumbnail_set=False)
    (stash / "bad.json").write_text("{ not json", encoding="utf-8")
    assert [r["video_id"] for r in critique_queue.missing_thumbnail()] == ["aaa"]


def test_stash_が印を受け取って書くこと(tmp_path, monkeypatch):
    """**故障注入。** `upload_only.py` からの `thumbnail_set` が届かなくなったら赤。

    ここが素通りすると、印は全部 `None` になり、
    `missing_thumbnail()` は**永久に空を返します**（気づけないほうの落ち方）。
    """
    monkeypatch.setattr(critique_queue, "STASH", tmp_path)
    work = tmp_path / "work"
    (work / "slides").mkdir(parents=True)
    (work / "inspect.jpg").write_bytes(b"\xff\xd8\xff")
    (work / "thumbnail.jpg").write_bytes(b"\xff\xd8\xff")
    monkeypatch.setattr(critique_queue, "_change_ratios", lambda w: None)

    critique_queue.stash("s-t", "vid1", {"segments": [{"narration": "あ"}]},
                         work, thumbnail_set=False)

    meta = json.loads((tmp_path / "vid1.json").read_text(encoding="utf-8"))
    assert meta["thumbnail_set"] is False, "印が控えに届いていません"
    assert meta["thumbnail_stashed"] is True
    assert (tmp_path / "vid1.thumb.jpg").exists(), (
        "bytes を残していません。**焼き直す道はありません**（build/ は毎周消えます）")
    assert [r["video_id"] for r in critique_queue.missing_thumbnail()] == ["vid1"]


def test_uploader_が結果を書き戻していること():
    """**書き戻しを消したら赤。** `publish_at` と同じ形で、ここでしか分かりません。"""
    src = (ROOT / "src" / "uploader.py").read_text(encoding="utf-8")
    assert 'publish_cfg["thumbnail_set"] = _set_thumbnail(' in src, (
        "uploader.upload() が `_set_thumbnail` の結果を書き戻していません。"
        "呼ぶ側は載ったかどうかを知る手立てがなくなります")


def test_upload_only_が印を渡していること():
    """**渡し忘れると全部 `None` になり、一覧が永久に空になります。**"""
    src = (ROOT / "scripts" / "upload_only.py").read_text(encoding="utf-8")
    assert "thumbnail_set=channel[\"publish\"].get(\"thumbnail_set\")" in src, (
        "upload_only.py が critique_queue.stash に thumbnail_set を渡していません")


def test_refresh_thumbnail_に_missing_の入口があること():
    """**手順に書いたコマンドが実在すること**（`--resplit` の3回目を繰り返さない）。"""
    src = (ROOT / "scripts" / "refresh_thumbnail.py").read_text(encoding="utf-8")
    assert '"--missing" in sys.argv' in src
    assert "def push_missing(" in src
    assert "mark_thumbnail_set" in src, (
        "押したあとに印を消していません。次の回も同じ本を押しにいきます")
