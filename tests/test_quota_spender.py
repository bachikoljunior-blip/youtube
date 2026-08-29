"""**枠を焼いたのは誰か**を、帳面に書かせる（2026-08-27 に実測して足した）。

## なぜ要るか

`data/day_quota.jsonl` は「何が・いつ・どの本に当たったか」しか持っておらず、
**どの道具が撃ったかを1文字も持っていませんでした。** そのせいで 08/27 の回は
「`videos.update` 489回 / 58本、1本が 140回」まで数えたのに撃ち手を名指しできず、
申し送りが「**残りの撃ち手を名指しすること**」で終わっています。

入口は6つあります（`--move`・`--compact`・`--spread`・`long_pack`・
`live_slots`・`queue_lag`）。**推測で1つずつ潰すより、帳面に書かせるほうが速い。**

あわせて `spend_in_window()` が「同じ本の撃ち直し」を数えます。実測（窓 08/27 07:00Z 〜）:

    通った `videos.update`   273回（13,650単位・日枠は 1万）
    撃たれた本の数            58本
    → 同じ本の2回目以降     215回 ＝ 10,750単位（79%）

**枠が尽きた理由が「同じ値の書き直し」だと、数えて初めて分かりました。**

**覆る条件**: `detail` の2つ目の語が本のIDでなくなったら、`repeats` の数え方が
壊れます（`test_本のIDはdetailの2語目から取る` が、そう教えます）。
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from src import upload_cap  # noqa: E402

JST = timezone(timedelta(hours=9))


def _root(tmp_path, monkeypatch):
    from src import config

    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setenv("YT_QUOTA_LEDGER_WRITE", "1")
    return tmp_path


def _read(tmp_path):
    import json

    path = tmp_path / upload_cap.DAY_QUOTA_HITS
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


# ------------------------------------------------ 名指しするところ

def test_書いた行に撃ち手が載る(tmp_path, monkeypatch):
    _root(tmp_path, monkeypatch)

    upload_cap.note_quota_ok(detail="videos.update abc")

    rows = _read(tmp_path)
    assert len(rows) == 1
    assert rows[0]["by"].startswith("test_quota_spender.py:"), rows[0]
    assert "upload_cap.py" not in rows[0]["by"], (
        "帳面を書く側そのものを名指ししている。**呼んだ側**を出すこと")


def test_403の行にも撃ち手が載る(tmp_path, monkeypatch):
    _root(tmp_path, monkeypatch)

    upload_cap.note_quota_hit(detail="videos.update abc")

    assert _read(tmp_path)[0]["by"].startswith("test_quota_spender.py:")


def test_auth経由でも_authではなく呼んだ側を名指しする(tmp_path, monkeypatch):
    """`auth.note_day_quota` は帳面の側です。**そこで止めると誰も分かりません。**"""
    from googleapiclient.errors import HttpError

    _root(tmp_path, monkeypatch)

    class _Resp:
        status = 403
        reason = "Forbidden"

    # **`auth.is_day_quota` は `str(error)` を見ます。** googleapiclient は
    # `error.message` だけを字にするので、そこに理由が要ります（`reason` は出ません）。
    body = ('{"error":{"code":403,"message":"exceeded your quota",'
            '"errors":[{"reason":"quotaExceeded","domain":"youtube.quota",'
            '"message":"exceeded your quota"}]}}')
    from src import auth

    auth.note_day_quota(HttpError(_Resp(), body.encode(), uri="https://x/"),
                        "videos.update abc")

    by = _read(tmp_path)[0]["by"]
    assert by.startswith("test_quota_spender.py:"), by
    assert "auth.py" not in by


def test_detail_は1文字も変えないこと(tmp_path, monkeypatch):
    """読み手が `detail.split(' ')[1]` で本のIDを取っています。
    **`by` は別の欄**にしてあるので、既存の読み手は1つも壊れません。"""
    _root(tmp_path, monkeypatch)

    upload_cap.note_quota_ok(detail="videos.update abc")

    assert _read(tmp_path)[0]["detail"] == "videos.update abc"


# ------------------------------------------------ 数えるところ

def _fill(tmp_path, monkeypatch, details):
    """**1行ずつ 1秒 ずらして積むこと**（2026-08-28 に直した）。

    ここは長らく全部の行を**同じ秒**で積んでいました。**実物はそうなりません** ——
    書き込みの入口はどれも 1.0〜1.2秒 待つので、同じ秒に同じ `detail` が
    2行 載るのは**帳面への二重書きのときだけ**です（実測 08/27: 273行 のうち
    100行 が二重書き ＝ 5,000単位ぶんの幻。`upload_cap.dedupe_ok` の註）。
    `spend_in_window` はその写しを1回にまとめるので、**同じ秒で積むと
    ここの撃ち直しまで消えます。**
    """
    _root(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc)
    for i, (detail, ok) in enumerate(details):
        at = now + timedelta(seconds=i)
        if ok:
            upload_cap.note_quota_ok(now=at, detail=detail)
        else:
            upload_cap.note_quota_hit(now=at, detail=detail)
    return now


def test_同じ本の撃ち直しを数える(tmp_path, monkeypatch):
    """**この回の 215回・10,750単位**が、この数え方で出ました。"""
    now = _fill(tmp_path, monkeypatch, [
        ("videos.update aaa", True),
        ("videos.update aaa", True),
        ("videos.update aaa", True),
        ("videos.update bbb", True),
        ("videos.update ccc", False),      # 403 は「通った」に数えない
    ])

    got = upload_cap.spend_in_window(now)

    assert got["ok"] == 4
    assert got["videos"] == 2
    assert got["repeats"] == 2, "aaa の2回目・3回目だけを数えること"
    assert got["hits"] == 1


def test_撃ち手ごとに数える(tmp_path, monkeypatch):
    now = _fill(tmp_path, monkeypatch, [("videos.update aaa", True)] * 3)

    by = upload_cap.spend_in_window(now)["by"]

    assert sum(by.values()) == 3
    assert all(k.startswith("test_quota_spender.py:") for k in by), by


def test_古い行に撃ち手が無くても落ちない(tmp_path, monkeypatch):
    import json

    _root(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc)
    path = tmp_path / upload_cap.DAY_QUOTA_HITS
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"at": now.isoformat(timespec="seconds"),
                                "detail": "videos.update aaa", "ok": True},
                               ensure_ascii=False) + "\n", encoding="utf-8")

    got = upload_cap.spend_in_window(now)

    assert got["ok"] == 1
    assert got["by"] == {"(不明)": 1}


def test_本のIDはdetailの2語目から取る(tmp_path, monkeypatch):
    """**覆る条件。** `detail` の形が変わったら、この検査が先に落ちます。"""
    now = _fill(tmp_path, monkeypatch, [("thumbnails.set zzz", True),
                                        ("thumbnails.set zzz", True)])

    assert upload_cap.spend_in_window(now)["repeats"] == 1


# ------------------------------------------------ 出すところ

def test_撃ち直しが本数を超えたら警告する():
    import queue_lag

    lines = queue_lag._spend_lines(
        {"ok": 273, "videos": 58, "repeats": 215, "hits": 29,
         "by": {"reschedule.py:_update": 273}})

    text = "\n".join(lines)
    assert "273" in text and "58" in text and "215" in text
    assert "10,750単位" in text, "**いくら焼いたか**を単位で言うこと"
    assert "取り合って" in text, "撃ち直しが本数を超えた回の読み方が出ていない"
    assert "reschedule.py:_update 273回" in text


def test_使っていない窓では何も出さない():
    import queue_lag

    assert queue_lag._spend_lines({"ok": 0, "videos": 0, "repeats": 0,
                                   "hits": 0, "by": {}}) == []
