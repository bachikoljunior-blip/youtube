"""`cli.channel_switch_line` —— **口（`YT_REFRESH_TOKEN`）が見せるチャンネルが替わったら `status` が名指しする**。

2026-09-14 09:4x・`hourly`・Fable。オーナー 09:3x「上書き後のはクッキーストラテジャーというチャンネルの方のトークン」
（`docs/GOAL.md` (4-f)）。`yt.channel()` は `mine=True` の先頭 1件 で、どのチャンネルかを誰も見ていなかった。

**陽性対照**（撃って落とした）: `prev[-1]["id"] == ch.get("id")` の比べを外すと
`test_同じチャンネルなら何も言わない` が落ち、`prev` を空で返すと `test_替わったら両方の_id_を名指しする` が落ちる。
"""
from studio import cli

MAIN = "UChTXZzwkIJHqyL7L_fEtuqQ"
OTHER = "UCxxxxxxxxxxxxxxxxxxxxxx"


def _rows(*ids):
    return [{"event": "channel", "id": i, "at": f"2026-09-14T0{n}:00:00+09:00"} for n, i in enumerate(ids)] + \
           [{"event": "built", "id": "-bSkulqONhI"}]


def test_同じチャンネルなら何も言わない():
    assert cli.channel_switch_line({"id": MAIN, "title": "お金と仕事の教科書"}, _rows(MAIN, MAIN)) == ""


def test_台帳に前の周が無ければ何も言わない():
    assert cli.channel_switch_line({"id": MAIN, "title": "x"}, [{"event": "built", "id": "v"}]) == ""


def test_替わったら両方の_id_を名指しする():
    line = cli.channel_switch_line({"id": OTHER, "title": "クッキーストラテジャー"}, _rows(MAIN, MAIN))
    assert line.startswith("!! チャンネルが変わりました")
    assert MAIN in line and OTHER in line and "クッキーストラテジャー" in line


def test_比べる相手はいちばん新しい_channel_の行():
    # 古い周が別の id でも、直前の周と同じなら鳴らない（比べるのは prev[-1]）。
    assert cli.channel_switch_line({"id": OTHER, "title": "x"}, _rows(MAIN, OTHER)) == ""
