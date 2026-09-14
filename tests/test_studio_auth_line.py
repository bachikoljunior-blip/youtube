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
    assert out.startswith("!! 口が拒まれました")          # 文言は `yt.token_rejected_words` の 1か所
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
