"""`list_sessions` の返りを写す手間を削る道具（`scripts/sessions_compact.py`）。

**測ってから足しています。** 前の回の設計の見直し（§6 (a2) 問い1）が
「いちばん時間を食ったのは `list_sessions` の返りをファイルに落とすところ（**約6分**）」
と書き残しました。1周の下限が41分なので、**6分は1周の15%**です。

ここで見るのは「短く書けるか」ではなく、
**短く書いたものを、受け取る2つの道具が同じように読めるか**です。
"""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location(
    "sessions_compact", ROOT / "scripts" / "sessions_compact.py")
sc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sc)


def test_頭の0を省いても実物のIDに戻る():
    """**接尾辞は24字で必ず `01` 始まり。** そこを毎回2字ずつ写す理由が無い。"""
    assert sc.full_id("V8pXxeMp4GXXCB1A6949Sg") == "session_01V8pXxeMp4GXXCB1A6949Sg"
    assert sc.full_id("17JrLva2qCRyMJGeWbourqN") == "session_017JrLva2qCRyMJGeWbourqN"
    assert sc.full_id("01WDiJ3WSwCDkHTyWTG7Dnbc") == "session_01WDiJ3WSwCDkHTyWTG7Dnbc"


def test_日付は既定で補い_またいだ行だけ書く():
    assert sc.stamp("14:21:56", "2026-08-15") == "2026-08-15T14:21:56.000000Z"
    assert sc.stamp("08-14/23:59:00", "2026-08-15") == "2026-08-14T23:59:00.000000Z"


def _rows():
    return (
        "# 註は落ちること\n"
        "V8pXxeMp4GXXCB1A6949Sg RUNNING  16:37:26 16:38:05 WDiJ3WSwCDkHTyWTG7Dnbc 1786817400 allowed\n"
        "\n"
        "WDiJ3WSwCDkHTyWTG7Dnbc ARCHIVED 15:54:23 16:37:40 Cox9GMhpv6ag9qgg9ggKK7 1786817400 allowed 8355581,247119,610,40735\n"
    )


def test_組み立てた形が返りと同じ形をしている():
    data = sc.parse(_rows(), "2026-08-15", "youtube-hourly")
    assert len(data) == 2
    me = data[0]
    assert me["id"] == "session_01V8pXxeMp4GXXCB1A6949Sg"
    assert me["session_status"] == "SESSION_STATUS_RUNNING"
    assert me["parent_session_id"] == "session_01WDiJ3WSwCDkHTyWTG7Dnbc"
    assert me["tags"] == ["youtube-hourly"]
    rli = me["external_metadata"]["rate_limit_info"]
    assert rli["rateLimitType"] == "five_hour"
    assert rli["resetsAt"] == 1786817400
    assert rli["status"] == "allowed"


def test_usage_は書いた行だけに入る():
    """**省くことと 0 は違います。**

    `usage` は全部の行には入りません（`quota.py` の「割り引いて読むこと」）。
    0 と書くと「使っていない」という**嘘の点**が積まれます。
    """
    data = sc.parse(_rows(), "2026-08-15", "youtube-hourly")
    assert "usage" not in data[0]["external_metadata"]
    assert data[1]["external_metadata"]["usage"]["output_tokens"] == 40735
    assert data[1]["external_metadata"]["usage"]["cache_read_tokens"] == 8355581


def test_受け取る2つの道具が読める(tmp_path):
    """**ここが本番。** 短く書けても、読む側が読めなければ意味が無い。"""
    from scripts import quota  # noqa: F401  （import できることも確かめる）
    data = sc.parse(_rows(), "2026-08-15", "youtube-hourly")
    path = tmp_path / "sessions.json"
    path.write_text(json.dumps({"ccr": {"data": data}}, ensure_ascii=False), encoding="utf-8")

    blob = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for sess in blob["ccr"]["data"]:
        rows.append(quota._row(sess) if hasattr(quota, "_row") else sess)
    assert len(rows) == 2

    # sibling_check が見る列（判断に使うもの）が全部あること
    for sess in blob["ccr"]["data"]:
        for key in ("id", "session_status", "created_at", "updated_at",
                    "tags", "parent_session_id", "external_metadata"):
            assert key in sess, key


def test_列が足りない行は黙って通さない():
    """**黙って落ちるほうが高い。** 1行足りないだけで兄弟判定が変わります。"""
    import pytest
    with pytest.raises(SystemExit):
        sc.parse("V8pXxeMp4GXXCB1A6949Sg RUNNING 16:37:26\n", "2026-08-15", "t")


def test_七日枠も書ける():
    rows = ("Uo6kT6yQiyiLcFTvRxvHJT ARCHIVED 11:20:33 11:32:22 "
            "016PyeT6Afj5KzKQ9xkKE3Kx 1786744800 rejected seven_day\n")
    data = sc.parse(rows, "2026-08-15", "youtube-hourly")
    rli = data[0]["external_metadata"]["rate_limit_info"]
    assert rli["rateLimitType"] == "seven_day"
    assert rli["status"] == "rejected"
