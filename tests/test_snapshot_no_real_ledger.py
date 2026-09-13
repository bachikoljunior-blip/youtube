"""**検査を撃つだけで、本物の `data/views.jsonl` と Data API に手が届いていた。**

2026-09-13 17:0x・optimizer・Opus。§8「起こす口を全部 外すこと」の **5例目**
（09/06 `ahead_sweep.kick()`／09/06 親の印字 3つ／09/08 `run_marker` の kick 2つ／
09/09 `run_marker` の本物の控え）。**この 1件だけが、値段と副作用の両方を持っています。**

**実測（この回に踏んだ）**: `python -m pytest tests/test_status_blind_path.py` を撃つだけで
本物の `data/views.jsonl` に **526行**（07:55:30Z と 07:55:37Z に **263行 ずつ**）入り、
`videos.list` を **12単位 × 2回** 使った。経路は `status.main()` の例外の枝の
`import snapshot as _snap; _snap.main()`（2026-08-31 の「θ の計器だけ取りに行く」）——
**検査が差し替えたのは「落ちる所」で、「落ちた先」ではありませんでした。**

**何が壊れるか**: `data/views.jsonl` は `scripts/zero_start.py` の**凍結した下敷き**で、
行が入ると §1 の下敷きが黙って動く（実測 B群の最大 **275 → 382回**）＝
`tests/test_zero_start.py::test_実物の下敷き_旧データは凍結なので数は動かない` が赤になり、
**親が毎周 撃つ `scripts/checks.py` が赤で戻ります**。

**必ず裸の `import snapshot` で撃つこと** —— `status.py` がそう読むからです
（`scripts.snapshot` で撃つと別のモジュールになり、門を外しても通ってしまう ——
§8 09/09 09:5x の `run_marker` で実際に踏んだ形）。

**陽性対照**（壊したら落ちるまで撃つ・§5 教訓の形 3つ目。`__pycache__` を消してから撃った）:
`record()` の門を外すと **1件**／`main()` の門を外すと **1件**／
門を `LOG` ではなく常に True にすると **1件**（差し替えた検査が書けなくなる側）。
**3つ とも別の検査が落ちます** ＝ 門は 2か所 とも要ります（片方だけでは、行か単位の片方が漏れる）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import snapshot  # noqa: E402  **裸で読むこと**（`status.py` と同じ当て先にするため）


def _video(vid: str) -> dict:
    return {"id": vid,
            "status": {"privacyStatus": "public"},
            "snippet": {"publishedAt": "2026-09-01T01:00:00Z"},
            "statistics": {"viewCount": "12", "likeCount": "1"}}


def test_検査の中では門が立つ() -> None:
    assert snapshot.LOG == snapshot._LOG_REAL
    assert snapshot._log_blocked() is True


def test_record_は本物の控えに書かない() -> None:
    """**書く側の門**（`run_marker._marks_blocked()` と同じ形）。"""
    before = snapshot.LOG.read_bytes() if snapshot.LOG.exists() else b""
    assert snapshot.record([_video("aaa"), _video("bbb")]) == 0
    after = snapshot.LOG.read_bytes() if snapshot.LOG.exists() else b""
    assert after == before, "本物の data/views.jsonl が動いた"


def test_main_は_API_を撃たずに降りる(capsys) -> None:
    """**値段の側も止めること** —— `record()` だけ塞ぐと 12単位 は毎回 出ていきます。"""
    before = snapshot.LOG.read_bytes() if snapshot.LOG.exists() else b""
    assert snapshot.main() == 0
    assert "検査からは撃ちません" in capsys.readouterr().out
    after = snapshot.LOG.read_bytes() if snapshot.LOG.exists() else b""
    assert after == before


def test_差し替えた検査は書いてよい(tmp_path, monkeypatch) -> None:
    """`LOG` が tmp を向いていれば通す —— そこを止めると、この控えを読む検査が書けない。"""
    tmp = tmp_path / "views.jsonl"
    monkeypatch.setattr(snapshot, "LOG", tmp)
    assert snapshot._log_blocked() is False
    assert snapshot.record([_video("ccc")]) == 1
    row = json.loads(tmp.read_text(encoding="utf-8").splitlines()[0])
    assert row["id"] == "ccc" and row["views"] == 12


def test_status_の例外の枝が_snapshot_を撃つことを押さえる() -> None:
    """**門を外した回に、どこから届くか**を 1行 で見せる（この検査の起点）。

    枝が消えたら `_log_blocked` の覆る条件 (1) ＝ `main()` 側の門は外してよい。
    """
    src = (ROOT / "scripts" / "status.py").read_text(encoding="utf-8")
    assert "import snapshot as _snap" in src and "_snap.main()" in src
