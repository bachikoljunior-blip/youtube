"""**焼き直しの log が 20分 止まって見えていました**（2026-09-04 22:0x に実測）。

`_run_out()` は「子の出力を**1行ずつ その場で**流す」と書いてあり、そこから3つ取れると
言っています —— **生きているか／どこで死んだか／どの段が遅いか。**

**どれも取れていませんでした。** `bufsize=1` は**こちらの読み口**の話で、
子の `stdout` は tty でないので **Python が既定で 8KB ずつためます。**

実測: 09/04 06:22 に起きた焼きは、`data/rebake.log` の末尾が
**20分 のあいだ「分かりやすさの輪 2周目」のまま**でした。実物はその間に

    clarity 3周目 281.9秒 → 4周目 235.2秒 → 輪おわり（1478.3秒・上限 4周）
    音 62本 を焼き終え、読み照合の輪へ

まで進んでいます（`build/<題材>/clarity_loop.json` の mtime と `audio/` の本数で分かった）。
**待つ側は、それを「固まった」と読みます** —— この回がまさに読みかけ、
`ps` の CPU 時間（25分）と `build/` の mtime を見て、初めて生きていると分かりました。

**待てと言う手順（`docs/spawn_prompt.md`）と、待つための計器は、対で要ります。**
片方だけだと、待っている側が「死んでいる」と誤読して降ります。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from scripts import ahead_sweep


def test_子に_PYTHONUNBUFFERED_を渡す(tmp_path, capsys) -> None:
    """**子が「ためる」設定のままだと、この検査は落ちます。**"""
    prog = tmp_path / "chatty.py"
    # `flush=True` を**書かない**こと —— 書くと、この検査は
    # 「子が行儀よく flush している」だけを見て、環境変数を見なくなります。
    prog.write_text(
        "import os, sys\n"
        "print('BUF=' + os.environ.get('PYTHONUNBUFFERED', ''))\n",
        encoding="utf-8")
    rc, out = ahead_sweep._run_out([sys.executable, str(prog)], "chatty", 60)
    assert rc == 0
    assert "BUF=1" in out


def test_親の環境を消さない(tmp_path) -> None:
    """**`env=` を渡すと、既定では親の環境がまるごと消えます。**

    この repo の子は `YOUTUBE_*` の資格情報を環境から読みます
    （`CLAUDE.md`「認証情報は環境『Youtube』の環境変数から読む」）——
    `env={"PYTHONUNBUFFERED": "1"}` と書いた瞬間に、**上げる手が全部 落ちます。**
    """
    key = "AHEAD_SWEEP_ENV_PROBE"
    os.environ[key] = "keep-me"
    try:
        prog = tmp_path / "echo_env.py"
        prog.write_text(
            f"import os\nprint('GOT=' + os.environ.get({key!r}, 'MISSING'))\n",
            encoding="utf-8")
        rc, out = ahead_sweep._run_out([sys.executable, str(prog)], "env", 60)
        assert rc == 0
        assert "GOT=keep-me" in out
    finally:
        os.environ.pop(key, None)
