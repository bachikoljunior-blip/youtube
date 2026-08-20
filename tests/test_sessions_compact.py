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


def test_session_を付けたまま渡しても二重にならない():
    """**手順は「省いてよい」と書いています ＝ 省かない形も来ます**（2026-08-17 に踏んだ）。

    付いたまま渡すと `session_session_01...` を組み立てていました。
    **落ち方が静かなほうへ倒れます** —— `sibling_check` は
    「返りの中に自分がいません」と言い（**ファイルが古い、と誤診させる**）、
    `quota.py` は**何も言わずに積みます**（偽の点が25件入りました）。
    """
    got = sc.full_id("session_01CCcGxNatooVnbDCXDJvn4K")
    assert got == "session_01CCcGxNatooVnbDCXDJvn4K"
    assert not got.startswith("session_session_")
    # 省いた形と、省かない形が、同じ1つに落ちること（両方が来るので）
    assert sc.full_id("CCcGxNatooVnbDCXDJvn4K") == got


def test_形の違うIDは黙って通さない():
    """**黙って組み立てるほうが高くつきます**（計器が汚れ、次の回が引き継ぐ）。"""
    import pytest
    for bad in ["session_session_01CCcGxNatooVnbDCXDJvn4K", "01CCcGxNatooVnbDCXDJvn4K@"]:
        with pytest.raises(SystemExit):
            sc.full_id(bad)


def test_行から組み立てても二重にならない():
    """`full_id` 単体ではなく、**実際に渡す道**（`parse`）で見ること。"""
    row = ("session_01CCcGxNatooVnbDCXDJvn4K RUNNING 22:46:52 22:49:12 "
           "session_01PHh5iD1HcBzMUxG6kPj3gt 1786925400 allowed")
    (got,) = sc.parse(row, "2026-08-16", sc.TAG)
    assert got["id"] == "session_01CCcGxNatooVnbDCXDJvn4K"
    assert got["parent_session_id"] == "session_01PHh5iD1HcBzMUxG6kPj3gt"


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


# ---- **まるごとの ISO を渡されたとき**（2026-08-17 11:3x に踏んだ）--------
#
# 手順（§2）は「日付も省いてよい」と書いています。**省かない形も来る**のに、
# `stamp()` は `HH:MM:SS` しか想定しておらず、
# **`2026-08-17T2026-08-16T22:46:52Z.000000Z`** を黙って返していました。
#
# 落ちる先は2つで、**どちらも黙ります**:
#   sibling_check --phase spawn → `born` が None ＝ **間隔の下限が効かない**
#   quota.py --ingest           → 日付だけ拾われ、**1日ずれた点**が積まれる（実測23件）
#
# **同じ道具の、同じ形の2度目です**（8/17 07:4x は `session_` の無条件の前置）。
# **受けるか落とすかの2つにすること。読めない字を作らない。**

def test_まるごとのISOをそのまま受ける():
    from datetime import datetime, timezone

    got = sc.stamp("2026-08-16T22:46:52Z", "2026-08-17")
    when = datetime.fromisoformat(got.replace("Z", "+00:00"))
    assert when == datetime(2026, 8, 16, 22, 46, 52, tzinfo=timezone.utc)
    # **`--date` に引きずられないこと。** ここがずれると1日ずれた点が積まれます
    assert got.startswith("2026-08-16")


def test_まるごとのISOでも行として組み立つ():
    from datetime import datetime

    rows = ("017ntNgwXa7YLwyDR36eVvHG RUNNING 2026-08-17T02:07:34Z "
            "2026-08-17T02:31:42Z 016jWC8S3TD6BVafqJJ12cxC 1786943400 allowed\n")
    data = sc.parse(rows, "2026-08-17", "youtube-hourly")
    # **読める字であること**（`born` が None になると間隔の下限が丸ごと外れます）
    datetime.fromisoformat(data[0]["created_at"].replace("Z", "+00:00"))
    datetime.fromisoformat(data[0]["updated_at"].replace("Z", "+00:00"))


def test_読めない時刻は黙って通さない():
    """**壊れた字を作って返さないこと。** これが本体の故障でした。"""
    import pytest
    with pytest.raises(SystemExit):
        sc.stamp("25:99:99", "2026-08-17")


def test_省いた形は今までどおり():
    """**両方受けること。** 片方だけにすると、これまでの書き方が落ちます。"""
    assert sc.stamp("16:37:26", "2026-08-15") == "2026-08-15T16:37:26.000000Z"
    assert sc.stamp("08-14/16:37:26", "2026-08-15") == "2026-08-14T16:37:26.000000Z"


# ---- 読む側の受け（**積んでしまった点は、読むときに外す**）----------------

def test_quota_は未来の点を読まない(tmp_path, monkeypatch):
    """未来の観測は**あり得ない点**です。1日ずれた点が `--pace` を狂わせます。"""
    import json
    import sys
    from datetime import datetime, timedelta, timezone
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import quota

    now = datetime.now(timezone.utc)
    log = tmp_path / "quota.jsonl"
    log.write_text("".join(json.dumps(r) + "\n" for r in [
        {"session_id": "a", "seen_at": (now - timedelta(hours=1)).isoformat()},
        {"session_id": "b", "seen_at": (now + timedelta(days=1)).isoformat()},
    ]), encoding="utf-8")
    monkeypatch.setattr(quota, "LOG", log)
    assert [r["session_id"] for r in quota._load()] == ["a"]
    assert [r["session_id"] for r in quota.impossible_rows()] == ["b"]


def test_quota_は少しの時計ずれで落とさない(tmp_path, monkeypatch):
    """**外す向きに寄せすぎないこと。** 直近の点は判断のいちばん重い材料です。"""
    import json
    import sys
    from datetime import datetime, timedelta, timezone
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import quota

    now = datetime.now(timezone.utc)
    log = tmp_path / "quota.jsonl"
    log.write_text(json.dumps(
        {"session_id": "a", "seen_at": (now + timedelta(minutes=5)).isoformat()}) + "\n",
        encoding="utf-8")
    monkeypatch.setattr(quota, "LOG", log)
    assert len(quota._load()) == 1


def test_落ち方の印は普通の行には要らない():
    """**25件ぶん写す手を増やさないこと。** 足すのは名指しされた1件だけです。"""
    rows = "a AR 2026-08-17T01:00:00 2026-08-17T02:00:00 p 1786979400 allowed"
    got = sc.parse(rows, "2026-08-17", "youtube-hourly")[0]
    assert "ending" not in got, "普通の行に欄ができています"
    assert "session_context" not in got, "見ていないものを「空」と書いています"


def test_apifail_は_sources_を空と書かない():
    """**`apifail` の回は `sources` が入っていた回**です。混ぜると次の子が誤診します。"""
    rows = "a AR 2026-08-17T01:00:00 2026-08-17T02:00:00 p 1786979400 allowed apifail"
    got = sc.parse(rows, "2026-08-17", "youtube-hourly")[0]
    assert got["ending"] == "apifail"
    assert "session_context" not in got


def test_nosrc_は_sources_を空にする():
    rows = "a AR 2026-08-17T01:00:00 2026-08-17T02:00:00 p 1786979400 allowed nosrc"
    got = sc.parse(rows, "2026-08-17", "youtube-hourly")[0]
    assert got["ending"] == "nosrc"
    assert got["session_context"] == {"sources": []}


def test_落ち方の印と使用量は同じ行に並べられる():
    """**4つ組の走査に食われないこと**（`f[7:]` を2つの規則が見ています）。"""
    rows = ("a AR 2026-08-17T01:00:00 2026-08-17T02:00:00 p 1786979400 allowed "
            "apifail 0,44911,2,202")
    got = sc.parse(rows, "2026-08-17", "youtube-hourly")[0]
    assert got["ending"] == "apifail"
    assert got["external_metadata"]["usage"]["cache_write_tokens"] == 44911


def test_seven_day_は並び順で消えない():
    """**位置で見ていた**（`f[7]` 決め打ち）ので、印を先に書くと枠の種類が化けました。

    5時間枠と7日枠は別物で、混ぜると `quota.py` の目盛りが狂います
    （`docs/trigger_main.md` §2「割り引いて読むこと」）。**黙って化けるほうの壊れ方**です。
    """
    base = "a AR 2026-08-17T01:00:00 2026-08-17T02:00:00 p 1786979400 allowed"
    for tail in ("seven_day", "apifail seven_day", "seven_day apifail"):
        got = sc.parse(f"{base} {tail}", "2026-08-17", "youtube-hourly")[0]
        kind = got["external_metadata"]["rate_limit_info"]["rateLimitType"]
        assert kind == "seven_day", f"{tail!r} で {kind} に化けています"
    # **書かない行は `five_hour`。ただしリセットが5時間の中にあるときだけ**
    # （2026-08-20 09:4x に足した算数の門。上の `1786979400` は更新の13.2時間先で、
    #  **5時間枠ではありえない** ＝ 書き落としとして直されます）。
    near = "a AR 2026-08-17T01:00:00 2026-08-17T02:00:00 p 1786936000 allowed"
    got = sc.parse(near, "2026-08-17", "youtube-hourly")[0]
    assert got["external_metadata"]["rate_limit_info"]["rateLimitType"] == "five_hour"


# --- タグは行ごと（2026-08-20 09:2x に踏んだ。**1周まるごと消えるところでした**）---
#
# `--tag` は全行に同じ1つを付けるだけでした。**読む側は行ごとに見ています** ——
# `sibling_check.py` は `tags` に `youtube-hourly` を含む行だけを兄弟に数えます。
# 09:2x の実物には `youtube-owner-request` の回が2件入っていて、それが
# `youtube-hourly` として積まれ、**終了コード 2（この場で畳め）**が返りました。
# §2 の指示どおりなら、その回は1件も出さずに終わります。

def test_タグを書いた行は_その行だけそのタグになる():
    rows = "\n".join([
        "a01 RUNNING 01:00:00 01:10:00 p01 1787349600 allowed_warning",
        "b01 RUNNING 02:00:00 02:10:00 p01 1787349600 allowed_warning youtube-owner-request",
    ])
    hourly, owner = sc.parse(rows, "2026-08-20", "youtube-hourly")
    assert hourly["tags"] == ["youtube-hourly"], "書かなかった行は既定のまま"
    assert owner["tags"] == ["youtube-owner-request"], "書いた行だけが変わること"


def test_タグは複数書ける():
    rows = ("a01 RUNNING 01:00:00 01:10:00 p01 1787349600 allowed "
            "tag:youtube-hourly,cowork-remote")
    (got,) = sc.parse(rows, "2026-08-20", "youtube-hourly")
    assert got["tags"] == ["youtube-hourly", "cowork-remote"]


def test_タグの走査は使用量も枠の種類も落ち方の印も食わない():
    """**`f[7:]` を4つの規則が見ています**（このファイルで4度目の「片方だけ」）。"""
    rows = ("a01 ARCHIVED 01:00:00 01:10:00 p01 1787349600 allowed_warning "
            "seven_day apifail 8861380,190452,130,47841 youtube-owner-request")
    (got,) = sc.parse(rows, "2026-08-20", "youtube-hourly")
    assert got["tags"] == ["youtube-owner-request"]
    assert got["ending"] == "apifail"
    assert got["external_metadata"]["rate_limit_info"]["rateLimitType"] == "seven_day"
    assert got["external_metadata"]["usage"]["output_tokens"] == 47841


def test_別の目的で走っている回は兄弟に数えられない(tmp_path):
    """**実際に踏んだ形をそのまま**（08/20 09:2x）。

    ここは `parse` の中だけを見てもわかりません —— 壊れていたのは
    **書く側と読む側のあいだ**なので、`sibling_check` の終了コードまで通すこと。
    """
    import subprocess
    me = "session_01TwzHNxY2W2p1V4iLCDBZAx"
    rows = "\n".join([
        f"{me[8:]} RUNNING 09:00:00 09:10:00 p01 1787349600 allowed_warning",
        "b01LMZGoWyqyZxSEdtSUcQR RUNNING 08:00:00 09:10:00 p01 1787349600 "
        "allowed_warning youtube-owner-request",
    ])
    out = tmp_path / "sessions.json"
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "sessions_compact.py"),
         str(out), "--rows", str(_write(tmp_path, rows))],
        capture_output=True, text=True, check=True)
    got = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "sibling_check.py"),
         "--sessions", str(out), "--me", me],
        capture_output=True, text=True)
    assert got.returncode == 0, (
        f"別の目的の回を兄弟に数えて畳んでいます（{got.returncode}）:\n{got.stdout}")


def _write(tmp_path, rows: str):
    p = tmp_path / "compact.txt"
    p.write_text(rows, encoding="utf-8")
    return p


# --- 枠の種類の書き落とし（2026-08-20 09:4x に**自分で踏んだ**）---
#
# `seven_day` は行の末尾に書くと効きますが、**書き方のどこにも書いてありません**
# （§2 の並びにも、この道具の「## 書き方」にも）。書かなければ既定は `five_hour` で、
# **黙って通ります。** §6 (f) は「枠は five_hour と seven_day の両方を、
# 窓ごとに一番新しい観測で見る」ので、週枠の観測が5時間枠の窓へ入ります。
#
# **書いた側に頼らずに捕まえます** —— 5時間枠のリセットは、
# その窓の中の観測から**5時間より先には来ません**。

def test_リセットが5時間より先なら5時間枠ではない(capsys):
    """**書き落としを、算数で捕まえる。** 週枠のリセットは何十時間も先にあります。"""
    row = ("01TwzHNxY2W2p1V4iLCDBZAx RUNNING 00:10:26 00:11:41 "
           "016PyeT6Afj5KzKQ9xkKE3Kx 1787349600 allowed_warning")   # 08-22 07:00 JST
    (got,) = sc.parse(row, "2026-08-20", "youtube-hourly")
    assert got["external_metadata"]["rate_limit_info"]["rateLimitType"] == "seven_day"
    assert "seven_day" in capsys.readouterr().err, "黙って直さないこと"


def test_本物の5時間枠は直さない(capsys):
    """**両向きに掛けること。** 全部を `seven_day` にする道具では役に立ちません。"""
    row = ("01TwzHNxY2W2p1V4iLCDBZAx RUNNING 00:10:26 00:11:41 "
           "016PyeT6Afj5KzKQ9xkKE3Kx 1787188000 allowed")   # 更新の 1.2時間後
    (got,) = sc.parse(row, "2026-08-20", "youtube-hourly")
    assert got["external_metadata"]["rate_limit_info"]["rateLimitType"] == "five_hour"
    assert capsys.readouterr().err == ""


def test_書いてある行はそのまま通る(capsys):
    row = ("01TwzHNxY2W2p1V4iLCDBZAx RUNNING 00:10:26 00:11:41 "
           "016PyeT6Afj5KzKQ9xkKE3Kx 1787349600 allowed_warning seven_day")
    (got,) = sc.parse(row, "2026-08-20", "youtube-hourly")
    assert got["external_metadata"]["rate_limit_info"]["rateLimitType"] == "seven_day"
    assert capsys.readouterr().err == "", "書いてある行で鳴らさないこと"
