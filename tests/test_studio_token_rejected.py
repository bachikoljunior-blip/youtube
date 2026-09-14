"""`yt.svc` —— **口（`YT_REFRESH_TOKEN`）を Google が拒んだら、23か所 の呼び手ではなく `svc()` が 3行 で止める**。

2026-09-14 18:5x・`hourly`・Fable。入れ物の立て直しのあと最初のサブで `status` が
`RefreshError: invalid_grant: Bad Request` の traceback 40行 で落ちた（`docs/GOAL.md` (4-f) 18:5x・JOURNAL 18:5x）。

**陽性対照**（撃って落とした）: `svc()` の try/except を外すと `test_拒まれたら_SystemExit_で_3行` が
`RefreshError` のまま抜けて落ちる。`token_rejected_words` の `expired or revoked` の枝を外すと
`test_失効の文言は取り直しを言う` が落ちる。
"""
import pytest
from google.auth.exceptions import RefreshError

from studio import yt


def _env(monkeypatch):
    for k in ("YT_REFRESH_TOKEN", "YT_CLIENT_ID", "YT_CLIENT_SECRET"):
        monkeypatch.setenv(k, "x")
    monkeypatch.setattr(yt, "_svc", None)


def test_拒まれたら_SystemExit_で_3行(monkeypatch):
    _env(monkeypatch)

    def boom(self, request):
        raise RefreshError("invalid_grant: Bad Request", {"error": "invalid_grant"})

    monkeypatch.setattr(yt.Credentials, "refresh", boom)
    with pytest.raises(SystemExit) as ex:
        yt.svc()
    words = str(ex.value)
    assert words.startswith("!! 口が拒まれました")
    assert "YT_REFRESH_TOKEN_2" in words and "API 0単位" in words
    assert yt._svc is None  # 拒まれた口を持ち回らない


def test_受けたら_build_まで進む(monkeypatch):
    _env(monkeypatch)
    monkeypatch.setattr(yt.Credentials, "refresh", lambda self, request: None)
    monkeypatch.setattr(yt, "build", lambda *a, **k: "SVC")
    assert yt.svc() == "SVC"


def test_失効の文言は取り直しを言う():
    w = yt.token_rejected_words(RefreshError("invalid_grant: Token has been expired or revoked."))
    assert "失効" in w and "取り直す" in w


def test_BadRequest_は別クライアントの側を言う():
    w = yt.token_rejected_words(RefreshError("invalid_grant: Bad Request"))
    assert "別の OAuth クライアント" in w and "YT_CLIENT_ID_2" in w


def test_未知の文言は覆る条件を名指しする():
    w = yt.token_rejected_words(RefreshError("invalid_client: Unauthorized"))
    assert "覆る条件 (2)" in w
