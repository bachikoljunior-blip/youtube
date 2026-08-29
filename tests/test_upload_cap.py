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


# **2つ目の形**（2026-08-19 19:5x に実際に踏んだ生の本文）。
# `videos.insert` の再開可能アップロードの途中で返るので、**429 でも 403 でもなく 400** です。
REAL_400 = (
    "<HttpError 400 when requesting None returned "
    "\"The user has exceeded the number of videos they may upload.\". "
    "Details: \"[{'message': 'The user has exceeded the number of videos they "
    "may upload.', 'domain': 'youtube.video', 'reason': 'uploadLimitExceeded'}]\">"
)


def test_400のuploadLimitExceededも枠として見分ける():
    """**番号で絞ると、この形が丸ごと素通りします**（09/01 の回で2本捨てた）。

    素通りすると2つの計器が同時に黙ります —— `batch_build` の
    「当たったら止まる」門と、`upload_cap` の観測（＝`status.py` の「あと N本」）。
    """
    assert auth.is_upload_cap(RuntimeError(REAL_400))


def test_400の側でもexplainが戻る時刻を言う():
    got = auth.explain(RuntimeError(REAL_400))
    assert "JST 16:00" in got


def test_故障注入_429を先に要求すると400を落とす(monkeypatch):
    """**直す前の実装をそのまま置いて、この検査が効くことを見る。**

    ここが赤くならない書き方に戻したら、9/01 と同じ捨て方をまたやります。
    """
    def old(error):
        text = str(error)
        if "rateLimitExceeded" not in text and "429" not in text:
            return False
        return "Video Uploads" in text or "uploadLimitExceeded" in text

    monkeypatch.setattr(auth, "is_upload_cap", old)
    assert not auth.is_upload_cap(RuntimeError(REAL_400))   # ← これが元の穴


def test_uploadLimitExceededの語は他の枠に出ない():
    """語を先に見る形にした根拠。**403（単位枠）と取り違えないこと。**"""
    assert "uploadLimitExceeded" not in REAL_403
    assert not auth.is_upload_cap(RuntimeError(REAL_403))


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


# ---------------------------------------------------------------------------
# **サムネイルと詰め直しは、同じ50単位を取り合っています**（2026-08-19）
#
# 既知の当たりを1件、先に固定してあります（`docs/trigger_main.md` §4）——
# **08/19 の実測**: 控えの穴は 08/30〜09/03 の5日、サムネイル待ちは 107本。
# この状態で押すと 5,350単位（＝詰め直し107本ぶん）が消えます。
# **ここが「押してよい」に戻ったら赤くなります。**
import datetime as _dt

from src import upload_cap as _uc


def _at(y, m, d, h=9):
    return _dt.datetime(y, m, d, h, tzinfo=_uc.JST)


def test_schedule_holes_walks_the_calendar_not_the_keys():
    """**鍵ではなく暦を歩くこと。** 0本の日は `Counter` の鍵に居ません。"""
    ahead = [_at(2026, 8, 20), _at(2026, 8, 21), _at(2026, 8, 24)]
    holes = _uc.schedule_holes(ahead, today=_dt.date(2026, 8, 19))
    assert holes == [_dt.date(2026, 8, 22), _dt.date(2026, 8, 23)]


def test_schedule_holes_skips_today():
    """今日は半分公開済みのことがある。入れると毎回「断絶」と鳴る（誤検知）。"""
    ahead = [_at(2026, 8, 20)]
    assert _uc.schedule_holes(ahead, today=_dt.date(2026, 8, 19)) == []


def test_schedule_holes_empty_ledger():
    assert _uc.schedule_holes([], today=_dt.date(2026, 8, 19)) == []


def test_thumbnails_yield_while_a_day_is_empty():
    """**08/19 の実測そのもの**（穴5日・待ち行列107本）。押さないのが正。"""
    ahead = [_at(2026, 8, 20), _at(2026, 8, 29), _at(2026, 9, 4)]
    okay, line = _uc.thumbnail_yield_to_schedule(
        ahead, 107, today=_dt.date(2026, 8, 19))
    assert okay is False
    assert "5,350単位" in line          # 107本 × 50単位


def test_thumbnails_yield_names_the_real_size_of_the_alternative():
    """**代替案の大きさは、穴の数で言うこと**（2026-08-28 に踏んだ）。

    ここは長らく「同じ単位で**詰め直しが {queued}本**できます」と言っていました。
    `queued` は**サムネイルの溜まり数**で、詰め直しに要る本数ではありません。
    実測 2026-08-28: 穴は 1日 だけ・要るのは `--move` 1回 なのに、
    文面は「70本 できます」と言い、`--spread` は「超えている日はありません」。
    **勧めている代替案が、その大きさでは存在しませんでした。**
    """
    ahead = [_at(2026, 8, 20), _at(2026, 8, 22)]     # 穴は 08/21 の1日だけ
    okay, line = _uc.thumbnail_yield_to_schedule(
        ahead, 70, today=_dt.date(2026, 8, 19))
    assert okay is False
    assert "1日あります" in line
    assert "1本の移動" in line, "要る本数は穴の数。queued を書かないこと"
    assert "70本の移動" not in line
    assert "--move" in line, "撃つ行を書くこと（読む側が --spread で空振りする）"


def test_thumbnails_go_when_there_is_no_hole():
    """**「サムネイルは要らない」ではありません。** 穴が消えたら押します。"""
    ahead = [_at(2026, 8, 20), _at(2026, 8, 21)]
    okay, line = _uc.thumbnail_yield_to_schedule(
        ahead, 107, today=_dt.date(2026, 8, 19))
    assert okay is True
    assert "107本を押します" in line
