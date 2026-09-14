"""**検査を撃つだけで本物の `data/studio/ledger.jsonl` に行が入らないこと**（見張り・§8 の 4つ目と同じ形）。

2026-09-14 19:5x・optimizer・Opus。**この回に踏んだ**: 19:1x に足した `cli.main()` の門が
`ledger("token_rejected", …)` を書くようになり、`tests/test_studio_auth_line.py` を撃っただけで
本物の台帳に **6行**（`cmd: analytics` / `reporting`）入った。差し替え忘れは**書き口が増えるたびに**起きるので、
守りを**呼ぶ側から書く側へ**移した（`common._ledger_blocked`）。

**陽性対照**（撃って落とした）: `_ledger_blocked()` を `return False` にすると
`test_検査から本物の台帳へは書けない` が落ち、**本物のファイルの md5 が動く**。
**陰性対照**: `LEDGER` を tmp へ差し替えた検査は**書けます**（`test_差し替えた台帳へは書ける`）。
"""
import hashlib

from studio import common


def _md5(p):
    return hashlib.md5(p.read_bytes()).hexdigest() if p.exists() else "なし"


def test_検査から本物の台帳へは書けない():
    before = _md5(common.LEDGER)
    common.ledger("test_marker", "-", note="この行は本物の台帳に入ってはいけない")
    assert _md5(common.LEDGER) == before
    if common.LEDGER.exists():
        assert "test_marker" not in common.LEDGER.read_text(encoding="utf-8")


def test_差し替えた台帳へは書ける(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "DATA", tmp_path)
    monkeypatch.setattr(common, "LEDGER", tmp_path / "ledger.jsonl")
    common.ledger("test_marker", "v1", note="こちらは書けること")
    assert "test_marker" in (tmp_path / "ledger.jsonl").read_text(encoding="utf-8")


def test_門は_2つ_そろったときだけ立つ(tmp_path, monkeypatch):
    assert common._ledger_blocked()                      # pytest の中・本物を指している
    monkeypatch.setattr(common, "LEDGER", tmp_path / "x.jsonl")
    assert not common._ledger_blocked()                  # 差し替えていれば立たない
    monkeypatch.setattr(common, "LEDGER", common._REAL_LEDGER)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    assert not common._ledger_blocked()                  # 検査の外では立たない
