"""`cli.auth_line` と `cli.main` の門 —— **口（`YT_REFRESH_TOKEN`）が死んだ周に、生のトレースバックを出さない**。

2026-09-14 19:0x・optimizer・Opus。**この回に踏んだ**: 親のコンテナが 18:2x に立ち直り、
そこから立ったサブ（18:45 起動）の `status` が `RefreshError: ('invalid_grant: Bad Request', ...)` で落ちた
（17:16 の周までは同じ口で `measure` が通っている）。

**陽性対照**（撃って落とした）:
 (1) `auth_line` の `invalid_grant` の判定を常に真にすると `test_別の失敗は空を返す` が落ちる。
 (2) `main()` の `if not line: raise` を外すと `test_口と関係ない失敗は握りつぶさない` が落ちる。
 (3) 読み分け（`expired or revoked`）を外すと `test_取り消された側と_クライアント違いの側を読み分ける` が落ちる。
"""
import pytest

from studio import cli


class _Refresh(Exception):
    """`google.auth.exceptions.RefreshError` の形だけを真似る（本物を import しない ＝ 検査は口を開かない）。"""


_Refresh.__name__ = "RefreshError"


def test_取り消された側と_クライアント違いの側を読み分ける():
    revoked = cli.auth_line(_Refresh("('invalid_grant: Token has been expired or revoked.', {})"))
    mismatch = cli.auth_line(_Refresh("('invalid_grant: Bad Request', {'error': 'invalid_grant'})"))
    assert "テスト" in revoked and "取り消した" in revoked
    assert "YT_CLIENT_ID" in mismatch and "取り消した" not in mismatch


def test_どちらの側もオーナーの手と訊きの名を出す():
    for e in (_Refresh("('invalid_grant: Bad Request', {})"),
              _Refresh("('invalid_grant: Token has been expired or revoked.', {})")):
        line = cli.auth_line(e)
        assert line.startswith("!! **YouTube の口が開きません**")
        assert "docs/SETUP.md" in line and "yt_token_dead" in line
        assert "trend" in line          # 口が死んだ周でも §7 は読める、と言うこと


def test_別の失敗は空を返す():
    assert cli.auth_line(ValueError("台本が無い")) == ""
    assert cli.auth_line(KeyError("viewCount")) == ""


def test_main_は口の失敗を_1行_と返り_2_にする(capsys, monkeypatch):
    monkeypatch.setattr(cli, "cmd_trend", lambda a: (_ for _ in ()).throw(
        _Refresh("('invalid_grant: Bad Request', {})")))
    assert cli.main(["trend"]) == 2
    assert "YouTube の口が開きません" in capsys.readouterr().out


def test_口と関係ない失敗は握りつぶさない(monkeypatch):
    monkeypatch.setattr(cli, "cmd_trend", lambda a: (_ for _ in ()).throw(ValueError("壊れている")))
    with pytest.raises(ValueError):
        cli.main(["trend"])
