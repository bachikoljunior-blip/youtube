"""`cli.token_rejected` と `cli.main` の門 —— **`analytics`／`reporting` が生のトレースバックで落ちない**。

2026-09-14 19:1x・optimizer・Opus。**8回目の二重**（§5 の取り分）: 同じ周の `hourly`（18:5x）が
`yt.svc()` の側で同じ欠陥を直しました（`yt.token_rejected_words`・検査 `tests/test_studio_token_rejected.py`）。
**文言の読み分けはそちらが正本で、ここでは読み分けません。** 残る口は 2つ ——
`studio/analytics.py` と `studio/reporting.py` は**自分の `svc()`** で `Credentials` を組むので
`yt.svc()` の `SystemExit` を通らない（＝ 18:5x の直しのあとも 40行 の traceback で落ちる）。

**陽性対照**（撃って落とした）:
 (1) `main()` の `if not token_rejected(e): raise` を外すと `test_口と関係ない失敗は握りつぶさない` が落ちる。
 (2) `token_rejected` を常に真にすると同じ検査が落ちる。
 (3) `main()` の `print` を消すと `test_analytics_が拒まれたら_3行_と返り_2_になる` が落ちる。
 (4) `main()` の前置き（`stall`／`budget`）が増えても落ちないこと ＝ 中身で見る
     （2026-09-16 04:2x。`startswith` は**停止の印が在る周だけ**赤くなり、それは口が閉じている周でした）。
"""
import pytest

from studio import cli


class _Refresh(Exception):
    """`google.auth.exceptions.RefreshError` の形だけを真似る（本物を import しない ＝ 検査は口を開かない）。"""


_Refresh.__name__ = "RefreshError"


def test_口が拒まれた例外を型でも文言でも引く():
    assert cli.token_rejected(_Refresh("('invalid_grant: Bad Request', {})"))
    assert cli.token_rejected(Exception("invalid_grant: Token has been expired or revoked."))


def test_別の失敗は引かない():
    assert not cli.token_rejected(ValueError("台本が無い"))
    assert not cli.token_rejected(KeyError("viewCount"))


def test_analytics_が拒まれたら_3行_と返り_2_になる(capsys, monkeypatch):
    monkeypatch.setattr(cli, "cmd_analytics", lambda a: (_ for _ in ()).throw(
        _Refresh("('invalid_grant: Bad Request', {})")))
    assert cli.main(["analytics"]) == 2
    out = capsys.readouterr().out
    # **`startswith` で見ないこと**（2026-09-16 04:2x に踏んで直した）——
    #   `main()` は口を撃つ前に `stall.lines()`（09/14 22:0x）と `budget.lines()`（09/16 03:4x）を
    #   印字するので、**台帳に停止の印が在る周だけ**この検査が赤くなっていました
    #   ＝ **口が閉じている周（この検査が守っている当の周）に限って落ちる**形。
    #   見るのは「その段落が出たか」であって「先頭に出たか」ではありません。
    assert "!! 口が拒まれました" in out                   # 文言は `yt.token_rejected_words` の 1か所
    assert "YT_REFRESH_TOKEN_2" in out                   # 置く物（オーナーの手）まで出ていること
    assert out.count("!! 口が拒まれました") == 1          # 同じ段落を 2度 印字しない


def test_reporting_も同じ門を通る(capsys, monkeypatch):
    monkeypatch.setattr(cli, "cmd_reporting", lambda a: (_ for _ in ()).throw(
        _Refresh("('invalid_grant: Token has been expired or revoked.', {})")))
    assert cli.main(["reporting"]) == 2
    assert "失効" in capsys.readouterr().out


def test_口と関係ない失敗は握りつぶさない(monkeypatch):
    monkeypatch.setattr(cli, "cmd_trend", lambda a: (_ for _ in ()).throw(ValueError("壊れている")))
    with pytest.raises(ValueError):
        cli.main(["trend"])
def test_svc_が_SystemExit_で止めた回も台帳に_1行_残る(monkeypatch):
    """`yt.svc()` の 3行（`hourly` 18:5x）は印字だけで、周を数える口が無かった。

    **陽性対照**: `main()` の `except SystemExit` の枝を外すと、この検査が落ちる。
    """
    wrote = []
    monkeypatch.setattr(cli, "ledger", lambda ev, vid, **d: wrote.append((ev, vid, d)))
    monkeypatch.setattr(cli, "cmd_status", lambda a: (_ for _ in ()).throw(
        SystemExit("!! 口が拒まれました: YT_REFRESH_TOKEN を Google が受けません（invalid_grant: Bad Request）")))
    try:
        cli.main(["status"])
    except SystemExit:
        pass
    assert wrote and wrote[0][0] == "token_rejected"
    assert wrote[0][2]["cmd"] == "status" and wrote[0][2]["how"] == "svc"


def test_口と関係ない_SystemExit_は台帳に残さない(monkeypatch):
    wrote = []
    monkeypatch.setattr(cli, "ledger", lambda ev, vid, **d: wrote.append(ev))
    monkeypatch.setattr(cli, "cmd_status", lambda a: (_ for _ in ()).throw(SystemExit("環境変数 X が無い")))
    try:
        cli.main(["status"])
    except SystemExit:
        pass
    assert wrote == []
