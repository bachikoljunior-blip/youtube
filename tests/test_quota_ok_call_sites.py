"""**通った単位を数える口の一覧を、註と実物で食い違わせない。**

2026-08-29 の実測。`src/upload_cap.py` の中で、同じ事実を2か所が
**別々の数**で言っていました:

    `DAY_QUOTA_HITS` の註   「`videos.update` と `thumbnails.set` の2か所だけ」
    `dedupe_ok` の docstring 「呼ぶ場所は現在3つ」
    実測                     **7つの file**（`note_quota_ok(` の行で 14）

これは「片方だけ」の形（この repo の通算12件目）で、**害があります** ——
「2か所だけ」を読んだ回は帳面をほぼ盲だと見積もり、「3つ」を読んだ回は
別の見積りをします。**`measured_budget()["spent"]` をどこまで信じるかが、
その数で変わります。**（そして**この検査を書いた回自身が、`grep` の
頭を切って「6か所」と誤りました** —— 数えるのは機械の仕事です。）

**数より境目のほうが大事です** —— 載っているのは**書き込みだけ**で、
**通った読みは1件も載りません。** 尽きた窓で先に 403 を返すのは読みのほうです
（実測 窓 08/28 の 403: `uploader.taken_publish_times` 30 ／
`status.py:main` 16 ／ `history.channel_video_ids` 6 —— **どれも読み**）。
だから `spent` は窓ごとに違う量だけ低く出ます:

    窓 08/27  403 の前に通った単位 **9,050**（403 は 07:47Z）
    窓 08/28  403 の前に通った単位 **3,700**（403 は 12:37Z・以後 110回）

`RESERVE_UNITS` の覆る条件「**関門が止めていないのに 403**」は、
**08/28 の窓で既に成立しています**（`reserve_hold()` はこの窓 1度も
止めていません）。

**覆る条件**: `note_quota_ok` を読みにも足したら（`RESERVE_UNITS` の
覆る条件が指している直し方）、`_WRITES_ONLY` は成り立たなくなります。
**そのときは `_FILES` と `_WRITES_ONLY` を同じ回のうちに直すこと** ——
外せるのは、`measured_budget()["spent"]` が読みまで数えるようになった証拠です。
**`videos.insert` にだけは足さないこと**（`tests/test_insert_never_marked_ok.py`）。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: 実測 2026-08-29。**通った単位を帳面へ載せる口を持つ file**（呼び出し回数つき）。
#: `scripts/playlists.py` は自前の薄い包み（`_note_quota_ok`）越しに呼びます。
_FILES = {
    "src/uploader.py": 4,
    "scripts/reschedule.py": 1,
    "scripts/post_pending_comments.py": 1,
    "scripts/link_longform.py": 1,
    "scripts/playlists.py": 4,          # 包みの定義・中身・その呼び出し2
    "scripts/refresh_thumbnail.py": 2,
    "scripts/retitle.py": 1,
}

#: 帳面に載るのは**書き込みだけ**、という境目（上の docstring）。
_WRITES_ONLY = {"insert", "update", "set"}

_ANY = re.compile(r"note_quota_ok\s*\(")
_WITH_LITERAL = re.compile(r"note_quota_ok\s*\(\s*(?:detail\s*=\s*)?f?\"([^\"{]*)")


def _sites() -> dict[str, int]:
    out: dict[str, int] = {}
    for rel in ("src", "scripts"):
        for path in sorted((ROOT / rel).rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            n = len([m for m in _ANY.finditer(text)])
            if path.name == "upload_cap.py":
                continue                      # 定義そのもの
            if n:
                out[str(path.relative_to(ROOT))] = n
    return out


def _ops() -> set[tuple[str, str]]:
    """読める範囲の `<file>, <呼び出し名>`（変数で渡す口は拾えません）。"""
    out: set[tuple[str, str]] = set()
    for rel in ("src", "scripts"):
        for path in sorted((ROOT / rel).rglob("*.py")):
            if path.name == "upload_cap.py":
                continue
            for m in _WITH_LITERAL.finditer(path.read_text(encoding="utf-8")):
                op = m.group(1).strip().split(" ")[0]
                if op:
                    out.add((str(path.relative_to(ROOT)), op))
    return out


def test_the_call_sites_are_the_ones_the_note_lists() -> None:
    found = _sites()
    assert found == _FILES, (
        "通った単位を数える口が変わりました。"
        f"\n  いま: {found}"
        f"\n  註:   {_FILES}"
        "\n**`src/upload_cap.py` の `DAY_QUOTA_HITS` の註（一覧の正本）と"
        " `dedupe_ok` の docstring（数だけ）を、同じ回のうちに直すこと。**"
        " 増えたのが**読み**なら、下の `_WRITES_ONLY` も直すこと。")


def test_every_recorded_call_is_a_write() -> None:
    """**通った読みは1件も載りません。** ここが `spent` の効く範囲です。"""
    for path, op in _ops():
        tail = op.rsplit(".", 1)[-1]
        assert tail in _WRITES_ONLY, (
            f"{path} が読み（`{op}`）を `note_quota_ok` に載せています。"
            " **これ自体は正しい直し方**です（`RESERVE_UNITS` の覆る条件）——"
            "そのときは `measured_budget()` の註と、この検査の"
            " `_WRITES_ONLY` を同じ回のうちに直すこと。")


def test_insert_is_still_never_recorded() -> None:
    """`videos.insert` は日枠が尽きても通るので、載せると門が誤って開きます。"""
    assert not [x for x in _ops() if x[1] == "videos.insert"], (
        "`videos.insert` が `note_quota_ok` に載っています。"
        " `quota_ok_after_hits` が、尽きた窓を『開いている』と答えます"
        "（`tests/test_insert_never_marked_ok.py`）")
