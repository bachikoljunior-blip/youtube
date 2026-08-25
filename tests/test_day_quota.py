"""**Data API の単位枠（10,000単位）**の検査（2026-08-17 22:4x に足した）。

`test_upload_cap_window.py`（**本数枠・429**）と対です。**混ぜないこと** ——
2つは同じ窓を使いますが、**別々に閉じます**（8/17 05:2x の実測: `insert`(1600) が
通るのに `update`(50) が 403。**安いほうが先に閉じます**）。

## 何を守っているか

直したのは `retro.quota_is_back()` で、そこは長らく

    now.astimezone(JST).hour >= 16      # ← **時計だけの模型**

でした。**窓が開いていること**と**単位が残っていること**は別の事実です ——
単位は窓の中で**こちらの `videos.insert` が使い切ります**（1本 1,600単位・
1周 7〜8本）。だから「16時を回った」は「押せる」の根拠になりません。

**この回の実測**（22:41 JST ＝ 窓が開いて 6.7時間後）:

    quota_is_back()                → True（「いまなら潰せます」と出た）
    refresh_thumbnail.py --missing  → **5本とも 403**

`missing_thumbnail` が **15回鳴って当たり2回**なのはこれです。一覧が悪いのではなく、
**「潰せる」と言う側が、確かめずに言っていました。**

## 両向きを同じだけ調べる（`test_upload_cap_window.py` と同じ考え方）

- 閉じているのに「押せる」と言う → **毎回 403 を撃ち、一覧が永久に減りません**
- 開いているのに「押せない」と言う → 押せる回を1回落とす。**次の窓で拾えます**

前者のほうが高い（**待ち行列が増え続ける**）ので、**観測した 403 は必ず効かせます。**
逆に、観測していないことを「残っている」の証拠にはしません（`line` がそう言います）。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import auth, upload_cap  # noqa: E402

JST = timezone(timedelta(hours=9))


def _jst(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=JST)


def _root(tmp_path, monkeypatch):
    from src import config

    monkeypatch.setattr(config, "ROOT", tmp_path)
    return tmp_path


# --- 見分ける側（`auth.is_day_quota`）--------------------------------------

def test_403_quota_exceeded_is_day_quota():
    exc = Exception(
        '<HttpError 403 when requesting .../thumbnails/set returned '
        '"The request cannot be completed because you have exceeded your quota.". '
        'Details: "[{\'message\': \'quotaExceeded\'}]">')
    assert auth.is_day_quota(exc)


def test_429_upload_cap_is_not_day_quota():
    """**本数枠と単位枠を取り違えないこと。** 止め方が逆です。

    429 は投稿そのものを止めますが、403 は**読みと thumbnails.set だけ**を止め、
    **投稿は続けます**（`docs/trigger_main.md` §5）。
    """
    exc = Exception("<HttpError 429 ... 'rateLimitExceeded' ... 'Video Uploads per day'>")
    assert auth.is_upload_cap(exc)
    assert not auth.is_day_quota(exc)


def test_plain_403_is_not_day_quota():
    """**枠と無関係な 403 を枠と読まないこと。**

    `_set_thumbnail` の元々の 403 は「投稿直後で動画側の処理が未了」で、
    **そちらは待てば通ります。** ここで取り違えると、待てば通るものを
    「窓が変わるまで無理」と諦めます。
    """
    assert not auth.is_day_quota(
        Exception("<HttpError 403 ... 'forbidden' ... The caller does not have permission>"))


# --- 積む側（`upload_cap`）-------------------------------------------------

def test_no_observation_means_open(tmp_path, monkeypatch):
    _root(tmp_path, monkeypatch)
    q = upload_cap.day_quota(_jst("2026-08-17 22:41"))
    assert q.open and not q.observed and q.hits == 0


def test_observed_403_closes_the_window(tmp_path, monkeypatch):
    """**この回が実際に踏んだ形。** 16時を回っていても、観測があれば閉じています。"""
    _root(tmp_path, monkeypatch)
    upload_cap.note_quota_hit(_jst("2026-08-17 21:52"), detail="thumbnails.set X")

    q = upload_cap.day_quota(_jst("2026-08-17 22:41"))
    assert not q.open and q.observed and q.hits == 1
    assert "尽きて" in q.line


def test_observation_expires_with_the_window(tmp_path, monkeypatch):
    """**次の窓へ持ち越さないこと。** 持ち越すと、押せる回を落とし続けます。"""
    _root(tmp_path, monkeypatch)
    upload_cap.note_quota_hit(_jst("2026-08-17 22:41"), detail="thumbnails.set X")

    # 枠の頭は太平洋時間の0時 ＝ この季節は JST 16:00。
    assert not upload_cap.day_quota(_jst("2026-08-18 15:59")).open
    assert upload_cap.day_quota(_jst("2026-08-18 16:01")).open


def test_day_quota_does_not_read_the_upload_cap_ledger(tmp_path, monkeypatch):
    """**2つの帳面を混ぜないこと。** 429 の観測で単位枠を閉じてはいけません。

    混ぜると、本数枠に当たった回が**サムネイルも押せなくなります**
    （実際には 50単位しか要らないので押せます）。
    """
    _root(tmp_path, monkeypatch)
    upload_cap.note_hit(_jst("2026-08-17 22:00"), detail="videos.insert")

    assert upload_cap.day_quota(_jst("2026-08-17 22:41")).open
    assert upload_cap.state(_jst("2026-08-17 22:41")).closed


def test_unreadable_ledger_does_not_close_the_window(tmp_path, monkeypatch):
    """**読めなかったことを理由に止めないこと**（CLAUDE.md）。

    読めない側を「閉じている」と読むと、押せる回まで押さなくなります。
    外す向きは今までどおり 403 を見るだけで、**悪化しません。**
    """
    _root(tmp_path, monkeypatch)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / upload_cap.DAY_QUOTA_HITS).write_text("これはJSONではありません\n",
                                                      encoding="utf-8")
    assert upload_cap.day_quota(_jst("2026-08-17 22:41")).open


def test_note_quota_hit_writes_one_line(tmp_path, monkeypatch):
    _root(tmp_path, monkeypatch)
    upload_cap.note_quota_hit(_jst("2026-08-17 22:41"), detail="thumbnails.set abc")

    rows = [json.loads(x) for x in
            (tmp_path / upload_cap.DAY_QUOTA_HITS).read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["detail"] == "thumbnails.set abc"


# --- 読む側（`retro.quota_is_back`）----------------------------------------

def _retro():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import retro

    return retro


def test_retro_follows_the_observation_not_the_clock(tmp_path, monkeypatch):
    """**この検査が、直した本体です。**

    22:41 JST は「16時を回っている」ので、古い実装は True を返しました。
    **実物は閉じていました。**
    """
    _root(tmp_path, monkeypatch)
    retro = _retro()

    late = _jst("2026-08-17 22:41")
    assert retro.quota_is_back(late)                    # まだ観測なし → 押してよい

    upload_cap.note_quota_hit(_jst("2026-08-17 21:52"), detail="thumbnails.set X")
    assert not retro.quota_is_back(late)                # 観測あり → **時計より観測**
    assert retro.hours_to_quota(late) > 0


def test_retro_window_head_is_not_hardcoded_16():
    """**窓の頭を、固定の時差で持たないこと**（冬は JST 17:00）。

    `upload_cap.PT` が tz 名で持っているのに、`retro.py` が `16` を書き直して
    いました。**この repo の「片方だけ」の10件目**です。
    """
    retro = _retro()
    assert not hasattr(retro, "QUOTA_BACK_HOUR")
    src = (Path(__file__).resolve().parent.parent / "scripts" / "retro.py").read_text(
        encoding="utf-8")
    # 本文（註）に出るのはよいが、**判定の式**に 16 が出てはいけない。
    body = [ln for ln in src.splitlines()
            if not ln.lstrip().startswith("#") and "hour" in ln and "16" in ln]
    assert body == [], body
