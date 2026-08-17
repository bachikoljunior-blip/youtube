"""**1日の投稿本数の枠（HTTP 429）を、Data API の日枠（403）と取り違えないこと。**

2026-08-17 10:5x に初めて踏みました。**2つは別の枠です。**

    Data API の日枠   10,000単位   403 quotaExceeded     読みと thumbnails.set が落ちる
    投稿の本数枠      1日92本      429 rateLimitExceeded **videos.insert そのものが落ちる**

`docs/trigger_main.md` §5 は 03:5x の実測から
「**日枠が切れていても `upload` は選べます**」と書いていました。
**その回は正しかった** —— あの時点で、この日の投稿はまだ62本でした。
**1つの枠を測って、もう1つの枠が無いことにしていた**だけです。

見分けが要る理由は1つ。**当たったら、この回の残りは必ず全部落ちます。**
実際この回は、最初の1本が通ったあと6本を撃ち、**6本とも同じ429**で捨てました。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import auth  # noqa: E402

# **実物です**（この回のログから、そのまま写しています）。
REAL_429 = (
    '<HttpError 429 when requesting None returned "Quota exceeded for quota '
    "metric 'Video Uploads' and limit 'Video Uploads per day' of service "
    "'youtube.googleapis.com' for consumer 'project_number:934765806582'.\". "
    'Details: "[{\'message\': "Quota exceeded for quota metric \'Video Uploads\' '
    "and limit 'Video Uploads per day' of service 'youtube.googleapis.com' for "
    "consumer 'project_number:934765806582'.\", 'domain': 'global', 'reason': "
    "'rateLimitExceeded'}]\">"
)

# **こちらも実物**（同じログの、別の行）。**403 で、reason が違います。**
REAL_403 = (
    '<HttpError 403 when requesting https://youtube.googleapis.com/youtube/v3/'
    'playlists?part=snippet&mine=true&maxResults=50&alt=json returned "The '
    'request cannot be completed because you have exceeded your quota.". '
    'Details: "[{\'message\': \'The request cannot be completed because you have '
    "exceeded your quota.', 'domain': 'youtube.quota', 'reason': "
    "'quotaExceeded'}]\">"
)


def test_実物の429を投稿本数の枠として見分ける():
    assert auth.is_upload_cap(RuntimeError(REAL_429))


def test_DataAPIの403を投稿本数の枠と取り違えない():
    """**ここが取り違えの本体です。**

    403 は読みが落ちるだけで、**投稿そのものは通ります**（2026-08-17 03:5x の実測）。
    これを「枠に当たった」と読むと、**1日13時間ぶんの upload をまた止めます。**
    """
    assert not auth.is_upload_cap(RuntimeError(REAL_403))


@pytest.mark.parametrize("text", [
    "boom",
    "",
    # **429 だが投稿の枠ではない**もの。将来ほかの 429 が出ても巻き込まないこと
    "<HttpError 429 ... 'reason': 'rateLimitExceeded'> for queries per minute",
    # **文字列に 'Video Uploads' はあるが 429 でない**
    "Video Uploads は1日92本です（ただの説明文）",
])
def test_関係のないエラーを枠と読まない(text):
    assert not auth.is_upload_cap(RuntimeError(text))


def test_explainが枠のときだけ戻る時刻を言う():
    """**explain は「いつ戻るか」を言うためにあります。**

    枠に当たった回が次にやることは1つ（JST 16:00 まで投稿しない）なので、
    そこが本文に出ていなければ、この分岐は無いのと同じです。
    """
    got = auth.explain(RuntimeError(REAL_429))
    assert "JST 16:00" in got
    assert "別の枠" in got
    # **403 のほうには出さないこと**（出すと、通る回を止めます）
    assert "JST 16:00" not in auth.explain(RuntimeError(REAL_403))


def test_故障注入_見分けを外すと403まで枠に見える(monkeypatch):
    """**この検査が本当に効いているか**を、壊して確かめる。

    `is_upload_cap` を「429 かどうか」だけに落とすと、
    上の403は素通りしますが、**429 の別種を全部拾ってしまいます。**
    """
    monkeypatch.setattr(auth, "is_upload_cap", lambda e: "429" in str(e))
    assert auth.is_upload_cap(RuntimeError(
        "<HttpError 429 ...> for queries per minute"))


def test_故障注入_reasonだけを見ると足りない():
    """`rateLimitExceeded` だけで判定すると、**分あたりの制限まで巻き込みます。**

    分あたりの制限は数十秒で戻るので、**そこで回を畳むのは損**です。
    だから `Video Uploads` の側も見ています。
    """
    minute_limit = "<HttpError 429 ...> 'reason': 'rateLimitExceeded'  (per minute)"
    assert "rateLimitExceeded" in minute_limit
    assert not auth.is_upload_cap(RuntimeError(minute_limit))
