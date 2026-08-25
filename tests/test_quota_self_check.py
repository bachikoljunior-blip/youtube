"""`quota.py --ingest` は、飲む前に「自分がその中にいるか」を見ること。

**3回運ばれて3回とも未着手だった申し送りの検査です。**

8/17 07:4x の回は、`sessions_compact` が `session_` を二重に付けた
**偽のIDを25件そのまま積みました。** 落ち方が2つに割れています ——

    sibling_check   「返りの中に自分がいません」と**言った**（誤診だが、鳴った）
    quota.py        **何も言わずに積んだ**

**気づけたのは、片方が exit 1 したからで偶然です。**
黙って積んだ点は `--pace` の「1周いくら」を薄め、**次の回が間隔を詰める**方向に効きます。
計器の汚れは次の回が引き継ぐので、**気づけないほうの落ち方**でした。

**止めないこと**も検査します。自分のIDが環境から取れない回（人との会話の回）で
積めなくなるほうが損なので、**言うだけ**が正しい振る舞いです。
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import quota  # noqa: E402
import sibling_check  # noqa: E402

ME = "session_01CXnkpaJgCCjDnQJzv6Nd37"


@pytest.fixture
def env_me(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_REMOTE_SESSION_ID", ME)


def test_absent_self_rings(env_me):
    """**これが本体。** 偽のIDしか無いファイルは鳴る。"""
    text = '{"data": [{"id": "session_session_01CXnkpaJgCCjDnQJzv6Nd37"}]}'
    warn = quota.self_check(text)
    assert warn and ME in warn, warn


def test_present_self_is_silent(env_me):
    assert quota.self_check(f'{{"data": [{{"id": "{ME}"}}]}}') == ""


def test_no_id_in_env_is_silent(monkeypatch):
    """**IDが取れない回では黙ること。** 積めなくなるほうが損。"""
    monkeypatch.delenv("CLAUDE_CODE_REMOTE_SESSION_ID", raising=False)
    assert quota.self_check('{"data": []}') == ""


def test_cse_prefix_is_normalised(monkeypatch):
    """`cse_` 形で渡ってくる回でも、同じ判定になること。"""
    monkeypatch.setenv("CLAUDE_CODE_REMOTE_SESSION_ID",
                       "cse_01CXnkpaJgCCjDnQJzv6Nd37")
    assert sibling_check.my_session_id() == ME
    assert quota.self_check(f'{{"id": "{ME}"}}') == ""
    assert quota.self_check('{"id": "session_017oGhqDbHPHwhkLAHVevM4r"}') != ""


def test_ingest_still_stores_when_it_rings(env_me, tmp_path, monkeypatch):
    """**鳴っても止めないこと。** 警告と保存は独立です。"""
    monkeypatch.setattr(quota, "LOG", tmp_path / "quota.jsonl")
    text = ('{"data": [{"id": "session_017oGhqDbHPHwhkLAHVevM4r",'
            ' "created_at": "2026-08-17T02:49:01Z",'
            ' "updated_at": "2026-08-17T03:30:55Z",'
            ' "tags": ["youtube-hourly"],'
            ' "external_metadata": {"rate_limit_info":'
            ' {"rateLimitType": "five_hour", "resetsAt": 1786943400,'
            ' "status": "allowed"}}}]}')
    assert quota.self_check(text) != ""
    added, _ = quota.ingest(text)
    assert added == 1
    assert (tmp_path / "quota.jsonl").exists()
