# -*- coding: utf-8 -*-
"""`cli.retitled_title` —— **台本の外で変えた題は、焼き直しで消える**。

2026-09-16 01:0x（optimizer・Fable・ultracode）に足した。**実物で踏んだ**:
09/15 21:0x の回が題の A/B で `videos.update` を 4本 に撃ったが、**台本の `title` は旧のまま**。
09/16 の `schedule --replace`（絵の差し替え）は `s.title` を渡すので、
`uyHgqwwtQvw`（→ `ukEFxTt1PEY`）の新しい題が**黙って旧の題に戻った**
＝ 判定 09/17 の A/B が 4本 → 3本 に欠けるところだった。

**陽性対照つき**（門が本当に効いているか・効きすぎていないか）。
"""
from __future__ import annotations

import studio.cli as cli

ROWS = [
    {"event": "scheduled", "id": "aaa", "title": "べつの事"},
    {"event": "retitled", "id": "vid1", "old_title": "ふるい題", "new_title": "【新】あたらしい題"},
    {"event": "retitled", "id": "vid1", "old_title": "【新】あたらしい題", "new_title": "【新2】さらに新しい題"},
    {"event": "retitled", "id": "vid2", "old_title": "ふるい題2", "new_title": "【新】題2"},
]


def test_台帳に在れば新しい題を返す():
    assert cli.retitled_title("vid2", ROWS) == "【新】題2"


def test_同じ本に2行あれば最後の題を返す():
    assert cli.retitled_title("vid1", ROWS) == "【新2】さらに新しい題"


def test_台帳に無ければNoneを返す():
    assert cli.retitled_title("しらない本", ROWS) is None


def test_陽性対照_retitled以外の行は拾わない():
    """`event` を見ずに `id` だけで拾ったら、`scheduled` の行を題として返してしまう。"""
    assert cli.retitled_title("aaa", ROWS) is None


def test_陽性対照_門の比べはtrimを通る():
    """末尾の改行だけの差で `schedule --replace` が止まったら、上の `_trim` と同じ偽陽性になる。"""
    assert cli._trim("【新】題2\n") == cli._trim("【新】題2")


def test_cmd_scheduleがこの門を持っている():
    """**門を外したら落ちる**（この検査が守っている当のもの）。"""
    src = open(cli.__file__, encoding="utf-8").read()
    assert "retitled_title(a.replace)" in src
    assert "A/B が黙って戻ります" in src
