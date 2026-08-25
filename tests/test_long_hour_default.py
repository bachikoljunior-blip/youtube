"""**長尺を、ショートで埋まった時刻に並ばせないこと。**（2026-08-26）

`batch_build` の `--hour` は長らく **ショートも長尺も既定 9時**でした。
9時はショートで埋まっているので、`uploader.next_publish_at()` は
**その時刻が空いている最初の日**まで後ろへ流します。

実測（2026-08-26 07:0x・控え462本で解いた。API 0単位）:

    09:00 JST → **2026-09-28**（32日先）   ← それまでの既定
    14:00 JST → 2026-08-28（2日後）
    18:00 / 20:00 / 22:00 JST → **2026-08-26（当日）**

**同じ本が、時刻を変えるだけで 33日 早く出ます。作る手間は1秒も増えません。**
そしてこの差は素通りします —— **予約は成功し、検査も緑**で、
違うのは「いつ公開されるか」だけだからです。

**なぜ目標に効くか**: 4,000時間の門に入るのは長尺だけで、実測は
**365日で 1.0時間**（要 3,999時間）。32日 眠っている本は、その間 1分も積みません。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import batch_build as B  # noqa: E402


def test_長尺の既定は_ショートで埋まっていない時刻():
    """**既定が 9時 に戻ったら、長尺はまた32日 後ろに入ります。**"""
    assert B.LONG_HOUR_JST != 9, (
        "長尺の既定を、ショートと同じ 9時 に戻さないこと。"
        "実測で 09:00 は 32日先・20:00 は当日でした"
    )
    assert 14 <= B.LONG_HOUR_JST <= 23, (
        f"長尺の既定 {B.LONG_HOUR_JST}時。"
        "ショートの帯（05:00〜13:30・`src/day_cap.py`）の外に置くこと"
    )


def test_ショートの既定は動かさない():
    """**この直しは長尺だけの話です。**

    ショートは1日10本の上限の内側で争っており、`src/day_cap.py` が
    「13:30 までに出した本は生きる」という**まだ切り分けていない枝**を持っています。
    **そちらを夜へ動かすのは、別の実測が要ります。**
    """
    src = (ROOT / "scripts" / "batch_build.py").read_text(encoding="utf-8")
    assert "args.hour = LONG_HOUR_JST if args.long else 9" in src, (
        "ショートの既定 9時 を、長尺と一緒に動かさないこと"
    )


def test_明示した_hour_のほうが勝つ():
    """**既定は既定です。** `--hour` を渡した回は、そちらが通ること。"""
    src = (ROOT / "scripts" / "batch_build.py").read_text(encoding="utf-8")
    assert 'ap.add_argument("--hour", type=int, default=None,' in src, (
        "`--hour` の既定は `None` にしておくこと —— "
        "数を既定に置くと「渡されたのか、既定なのか」が区別できず、"
        "長尺の既定を当てる場所が無くなります"
    )
    assert "if args.hour is None:" in src


def test_なぜその時刻かが_根拠つきで書いてある():
    """**理由の書いていない定数は、次に来た側が判断できず惰性で残ります**（`CLAUDE.md`）。"""
    src = (ROOT / "scripts" / "batch_build.py").read_text(encoding="utf-8")
    i = src.index("LONG_HOUR_JST = ")
    註 = src[max(0, i - 1800):i]
    for 語 in ("2026-09-28", "2026-08-26", "覆る条件"):
        assert 語 in 註, f"`LONG_HOUR_JST` の註に {語} がありません"
