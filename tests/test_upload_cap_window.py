"""`src/upload_cap.py` の検査（**撃つ前に、あと何本かを言う側**）。

**`tests/test_upload_cap.py` とは別物です。** あちらは `src/auth.is_upload_cap`
＝**当たったことを見分ける**側で、こちらは**当たる前に止める**側です。
名前が近いので、片方を書き換えるときは**もう片方を先に開くこと**
（この節を足した回は、実際に同名で上書きしかけました）。

**故障注入つき。** この道具の値打ちは「まだ撃てる」と言うことではなく、
**閉じているときに作らせないこと**なので、両向きを同じだけ調べます。

- 数えすぎ（まだ撃てるのに「もう無い」）→ **投稿が止まります。最大の損失**
- 数え足りない（閉じているのに「撃てる」）→ 今までどおり 429 を見て止まる。**悪化しない**

**下限しか言えないことを、検査でも明示しておくこと**（`uploaded_at` を持たない
古い行は数えられません）。ここを「正確」と読み替えると、次の回が
`remaining` を根拠に別の判断をします。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import dupes, upload_cap  # noqa: E402

JST = timezone(timedelta(hours=9))


def _jst(text: str) -> datetime:
    """JST の '2026-08-17 11:00' を aware な datetime に。"""
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=JST)


def _root(tmp_path, monkeypatch):
    from src import config

    monkeypatch.setattr(config, "ROOT", tmp_path)
    (tmp_path / "data").mkdir(exist_ok=True)
    return tmp_path


# ---- 窓の境目（**夏時間で動きます**）------------------------------------

def test_window_boundary_is_jst_1600_in_summer():
    """夏（PDT ＝ UTC-7）は **JST 16:00** が境目。"""
    before = upload_cap.window_end(_jst("2026-08-17 15:59"))
    assert before.astimezone(JST).strftime("%m-%d %H:%M") == "08-17 16:00"
    # 16:00 ちょうどは**次の窓**。1本目からやり直せます。
    after = upload_cap.window_start(_jst("2026-08-17 16:00"))
    assert after.astimezone(JST).strftime("%m-%d %H:%M") == "08-17 16:00"


def test_window_boundary_is_jst_1700_in_winter():
    """冬（PST ＝ UTC-8）は **JST 17:00**。

    **固定の時差で書かないこと。** 文書に「JST 16:00」と何度も書いてあるのは
    夏に測ったからで、11月には1時間ずれます。
    """
    assert upload_cap.window_start(
        _jst("2026-01-15 12:00")).astimezone(JST).strftime("%H:%M") == "17:00"


def test_window_length_is_a_calendar_day_not_24h():
    """夏時間の切り替わる日は23時間・25時間になります（`+timedelta(days=1)` は嘘）。"""
    # 2026-11-01 に PDT → PST（PT の1日が25時間）
    head = upload_cap.window_start(_jst("2026-11-01 20:00"))
    tail = upload_cap.window_end(_jst("2026-11-01 20:00"))
    assert (tail - head).total_seconds() / 3600 == 25


# ---- 控えから数える -------------------------------------------------------

def _remember(topic: str, uploaded_at: str | None) -> None:
    dupes.remember(f"v-{topic}", topic, f"題 {topic}", "2026-09-01T00:00:00Z",
                   uploaded_at=uploaded_at)


def test_counts_only_this_window(tmp_path, monkeypatch):
    _root(tmp_path, monkeypatch)
    now = _jst("2026-08-17 11:00")          # 窓は 08-16 16:00 〜 08-17 16:00 JST
    _remember("in1", "2026-08-16T07:30:00+00:00")   # 16:30 JST = 窓の中
    _remember("in2", "2026-08-17T01:00:00+00:00")   # 10:00 JST = 窓の中
    _remember("out", "2026-08-16T06:30:00+00:00")   # 15:30 JST = **前の窓**
    assert upload_cap.counted(now) == 2


def test_old_rows_without_the_field_are_a_lower_bound(tmp_path, monkeypatch):
    """**`uploaded_at` の無い行は数えられません。** これは仕様です。

    数え落としは「まだ撃てる」側に外れるので、そのときは今までどおり
    429 を見て止まります。**逆向き（閉じているのに撃てる、を数えすぎで作る）は
    起きない**ことのほうが大事です。
    """
    _root(tmp_path, monkeypatch)
    _remember("new", "2026-08-17T01:00:00+00:00")
    dupes.remember("old", "t-old", "古い行", "2026-09-01T00:00:00Z", uploaded_at="")
    assert upload_cap.counted(_jst("2026-08-17 11:00")) == 1


def test_remember_stamps_now_by_default(tmp_path, monkeypatch):
    """**既定で「いま」を書くこと。** 呼ぶ側は投稿の直後にしか呼びません。

    ここが空のままだと、次の回は**1本も数えられません**（＝この道具が丸ごと死ぬ）。
    """
    _root(tmp_path, monkeypatch)
    dupes.remember("v1", "t1", "題", "2026-09-01T00:00:00Z")
    rec = json.loads((tmp_path / dupes.LEDGER).read_text(encoding="utf-8").strip())
    assert rec["uploaded_at"]
    when = datetime.fromisoformat(rec["uploaded_at"])
    assert abs((datetime.now(timezone.utc) - when).total_seconds()) < 120
    # **`at` を潰していないこと**（`batch_build --date` の空き時刻はこちらを読む）
    assert rec["at"] == "2026-09-01T00:00:00Z"


def test_ledger_rows_exposes_uploaded_at(tmp_path, monkeypatch):
    """`ledger_rows` から欄が落ちたら、数える側は黙って 0 になります。"""
    _root(tmp_path, monkeypatch)
    _remember("t1", "2026-08-17T01:00:00+00:00")
    assert dupes.ledger_rows()[0]["uploaded_at"] == "2026-08-17T01:00:00+00:00"


# ---- 観測した 429（**こちらは確実**）--------------------------------------

def test_hit_closes_the_window(tmp_path, monkeypatch):
    _root(tmp_path, monkeypatch)
    now = _jst("2026-08-17 11:00")
    upload_cap.note_hit(_jst("2026-08-17 10:45"))
    st = upload_cap.state(now)
    assert st.closed and st.remaining == 0
    assert "閉じています" in st.line


def test_hit_from_the_previous_window_does_not_close(tmp_path, monkeypatch):
    """**前の窓の 429 で止めないこと。** 止めると、枠が戻っても投稿が再開しません。

    ここを間違えると `data/upload_cap.jsonl` が育つほど投稿が止まります
    （`src/alerts.py` の「一覧が当たりを含まないまま育つ」と同じ形の、最悪版）。
    """
    _root(tmp_path, monkeypatch)
    upload_cap.note_hit(_jst("2026-08-17 10:45"))
    st = upload_cap.state(_jst("2026-08-17 16:30"))   # 窓が変わった直後
    assert not st.closed
    assert st.remaining == upload_cap.CAP_PER_DAY


def test_state_counts_down_from_the_cap(tmp_path, monkeypatch):
    _root(tmp_path, monkeypatch)
    for i in range(5):
        _remember(f"t{i}", "2026-08-17T01:00:00+00:00")
    st = upload_cap.state(_jst("2026-08-17 11:00"))
    assert (st.counted, st.remaining, st.closed) == (5, upload_cap.CAP_PER_DAY - 5, False)


def test_full_ledger_leaves_no_room(tmp_path, monkeypatch):
    """**92本を数えたら、429 を見ていなくても撃たないこと。**"""
    _root(tmp_path, monkeypatch)
    for i in range(upload_cap.CAP_PER_DAY):
        _remember(f"t{i}", "2026-08-17T01:00:00+00:00")
    st = upload_cap.state(_jst("2026-08-17 11:00"))
    assert st.remaining == 0 and not st.closed


def test_broken_hit_lines_do_not_stop_the_round(tmp_path, monkeypatch):
    """**壊れた行でこの回を止めないこと**（控えと同じ扱い）。"""
    root = _root(tmp_path, monkeypatch)
    (root / upload_cap.HITS).write_text(
        'こわれた行\n{"at":"2026-08-17T01:45:00+00:00"}\n\n', encoding="utf-8")
    assert len(upload_cap.hits_in_window(_jst("2026-08-17 11:00"))) == 1


def test_no_records_at_all_means_full_room(tmp_path, monkeypatch):
    """**読めなかったことを「閉じている」と読まないこと**（CLAUDE.md）。"""
    _root(tmp_path, monkeypatch)
    st = upload_cap.state(_jst("2026-08-17 11:00"))
    assert st.remaining == upload_cap.CAP_PER_DAY and not st.closed


# ---- 故障注入（**当たったことを残す側**）----------------------------------

def test_note_cap_records_only_the_upload_cap(tmp_path, monkeypatch):
    """429 の本数枠だけを残すこと。**403 の日枠を混ぜると窓が誤って閉じます。**"""
    from src import uploader

    _root(tmp_path, monkeypatch)
    uploader._note_cap(RuntimeError(
        "<HttpError 403 ... quotaExceeded ... youtube.googleapis.com>"))
    assert not (tmp_path / upload_cap.HITS).exists()

    uploader._note_cap(RuntimeError(
        "<HttpError 429 ... rateLimitExceeded ... 'Video Uploads per day'>"))
    assert upload_cap.hits_in_window()


def test_note_cap_never_raises(tmp_path, monkeypatch):
    """**記録できないことで投稿の失敗理由を握り潰さないこと。**"""
    from src import config, uploader

    monkeypatch.setattr(config, "ROOT", tmp_path / "書けない場所")
    monkeypatch.setattr(upload_cap, "note_hit",
                        lambda **kw: (_ for _ in ()).throw(OSError("読み取り専用")))
    uploader._note_cap(RuntimeError("429 'Video Uploads per day'"))   # 例外を出さない


# ---- 門そのもの（**この fix の値打ちはここ**）------------------------------

def test_batch_build_refuses_to_generate_when_the_window_is_closed(monkeypatch, capsys):
    """**閉じている窓では、1本も作らないこと。**

    ここが効かないと 10:5x の回がそのまま再演します —— 作ってから 429 に当たり、
    `build/` はコンテナごと消えるので**まるごと捨て**になります。
    **`pick` に到達しないこと**まで見ます（到達したら生成が始まります）。
    """
    from scripts import batch_build

    called: list = []
    monkeypatch.setattr(batch_build, "pick", lambda *a, **k: called.append(a) or [])
    monkeypatch.setattr(batch_build.upload_cap, "state", lambda: upload_cap.State(
        True, 92, 0, datetime.now(timezone.utc), "閉じています"))
    assert batch_build.main(["--count", "3"]) == 1
    assert called == []
    assert "作りません" in capsys.readouterr().out


def test_batch_build_shrinks_to_what_is_left(monkeypatch):
    """残り2本のときに6本を作らないこと（**4本ぶんが捨て札になります**）。"""
    from scripts import batch_build

    asked: list = []

    def _pick(count, explicit=None, per_calc=2):
        asked.append(count)
        return []

    monkeypatch.setattr(batch_build, "pick", _pick)
    monkeypatch.setattr(batch_build.upload_cap, "state", lambda: upload_cap.State(
        False, 90, 2, datetime.now(timezone.utc), "あと2本"))
    batch_build.main(["--count", "6"])
    assert asked == [2]


def test_batch_build_skip_upload_ignores_the_cap(monkeypatch):
    """**`--skip-upload` は撃たないので、枠と関係ありません。**

    ここを止めると「枠が戻る回のために先に作っておく」道が塞がります。
    """
    from scripts import batch_build

    asked: list = []
    monkeypatch.setattr(batch_build, "pick",
                        lambda count, *a, **k: asked.append(count) or [])
    monkeypatch.setattr(batch_build.upload_cap, "state", lambda: (_ for _ in ()).throw(
        AssertionError("--skip-upload では枠を見にいかないこと")))
    batch_build.main(["--count", "6", "--skip-upload"])
    assert asked == [6]
