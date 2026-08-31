"""**作る段は並列・予約の段は直列**、そして順番が崩れないことを検査する。

## なぜ要るか（2026-08-15）

`batch_build.py` は1本ずつ直列に作っていました。8/15 に7本を通したとき **80分＝1本11分**。
その11分の中身を `ps` で見たら、**生成中の python は CPU を 2〜4% しか使っていません** ——
ほぼ全部が `claude -p`（`src/claude_cli.py`）の**待ち時間**でした。
**待ち時間は重ねられます。** M14（1日あたりの本数）の律速はここでした。

並列にすると、直列では起きなかった壊れ方が2つ出ます。**どちらも黙って壊れます。**

1. **予約時刻の取り違え。** `when[n-1]` は `topics` の並び順に対応しています。
   完了順に結果を積むと、**速く出来た本が他の本の枠を取ります。**
   画面には「予約できました」としか出ないので、**一覧を見るまで気づきません**
2. **予約の同時実行。** `upload_only.py` は `next_publish_at` と待ち行列という
   **共有の状態**を触るので、同時に走らせると同じ時刻を2本に割り当てます
   （8/15 03:48 の二重起動と同じ壊れ方）

だから検査するのは「速くなったか」ではなく、**この2つが起きないこと**です。
"""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts import batch_build  # noqa: E402


class _Recorder:
    """`run()` の代わり。誰がいつ呼ばれたかと、**同時に何本走ったか**を残す。"""

    def __init__(self, delays: dict[str, float] | None = None,
                 fail_build: set[str] | None = None):
        self.delays = delays or {}
        self.fail_build = fail_build or set()
        self.calls: list[tuple[str, str]] = []      # (種類, テーマID)
        self.max_concurrent_upload = 0
        self._uploads_now = 0
        self._lock = threading.Lock()

    def __call__(self, cmd, timeout, label="", env=None):
        kind = ("build" if "src.pipeline" in cmd else
                "inspect" if "inspect_build.py" in " ".join(cmd) else "upload")
        tid = label or "?"
        if kind == "upload":
            with self._lock:
                self._uploads_now += 1
                self.max_concurrent_upload = max(
                    self.max_concurrent_upload, self._uploads_now)
        with self._lock:
            self.calls.append((kind, tid))
        time.sleep(self.delays.get(tid, 0.0) if kind == "build" else 0.0)
        if kind == "upload":
            with self._lock:
                self._uploads_now -= 1
            # 予約時刻をそのまま動画IDに焼き込んで返す（対応を検査で読むため）
            return 0, f"VIDEO_ID vid-{tid}-{cmd[-1]}\n"
        if kind == "build" and tid in self.fail_build:
            return 1, "生成に失敗しました"
        return 0, ""


def _topics(ids):
    return [{"id": i, "calc": "dummy", "title_seed": i} for i in ids]


def _pin_rule(monkeypatch, per_day: int = 25) -> None:
    """**オーナーの規則（1日1本）は、この file の主題ではありません。**（2026-08-31）

    `src/house_rule.PUBLISH_PER_DAY = 1` は 2026-08-31 にオーナーが固定した
    運転の規則で、`batch_build.density_cap()` と `--count` の門がそこを読みます。
    **それは正しい振る舞いです。**

    ただしこの file が測っているのは **並列の仕掛け**（3本を同時に走らせたら
    直列より速いか・失敗した1本が他を巻き込まないか・再試行が題材を食わないか）で、
    **1本しか通らないと、その形そのものが観測できなくなります**
    （実測 2026-08-31: `jobs` が `3` ではなく `1` になり、`serial_sec > wall_sec` が
    `0.2 > 0.2` に潰れて **11件 赤**）。

    **形は1行も壊れていません。** 落ちたのは「標本が、並列が効く帯に居るか」だけで、
    `tests/_eta_pin.py` の冒頭が記録している day_cap / rpm_mix / subs_cap /
    house_rule と**まったく同じ壊れ方**です。上の `_open_window()`
    （本数枠の門を実物の控えから切り離す）と、**同じ理由・同じ扱い**にします。

    **規則そのものは `tests/test_house_rule.py` と `tests/test_density_cap.py` が
    主題として持ちます**（**隠さず、置き場所を分けています**）。
    """
    from src import house_rule
    monkeypatch.setattr(house_rule, "PUBLISH_PER_DAY", per_day)
    # **`density_cap()` は `functools.cache` です。**（2026-08-31 に踏んだ）
    #     `house_rule` だけ差し替えると、**この file が先に走った回だけ
    #     `density_cap()` に 25 が焼き付き**、あとから走る
    #     `tests/test_house_rule.py` が `assert 25 == 1` で落ちます
    #     （実測: 単体では緑、`test_batch_parallel` の後だと4件 赤）。
    #     **キャッシュを触らず、関数そのものを差し替えます** ——
    #     `monkeypatch` が終わりに戻すので、本物のキャッシュは汚れません。
    monkeypatch.setattr(batch_build, "density_cap", lambda: int(per_day))

def _run(monkeypatch, ids, delays=None, fail_build=None, jobs=3):
    rec = _Recorder(delays, fail_build)
    monkeypatch.setattr(batch_build, "run", rec)
    monkeypatch.setattr(batch_build, "pick",
                        lambda c, e, per_calc=None, **k: _topics(ids))
    monkeypatch.setattr(batch_build, "check_window", lambda d, f: None)
    # **本数枠の門を、実物の控えから切り離す**（2026-08-17 に足した）。
    # `batch_build` は撃つ前に `src/upload_cap.state()` を見ます。素通しにすると
    # **`data/uploaded.jsonl` の中身で検査の答えが変わり**、いつか
    # 「今日はもう92本上げた」だけで並列の検査が赤くなります
    # （`test_batch_slots.py` が `taken=` で同じことを塞いでいます）。
    monkeypatch.setattr(batch_build.upload_cap, "state", lambda: _open_window())
    _pin_rule(monkeypatch)          # 規則（1日1本）は主題ではない（上の註）
    written: list[dict] = []
    monkeypatch.setattr(batch_build.Path, "open",
                        lambda self, *a, **k: _Sink(written))
    code = batch_build.main([
        "--count", str(len(ids)), "--date", "2026-08-30", "--jobs", str(jobs),
    ])
    return code, rec, written


class _Sink:
    """`data/batch_runs.jsonl` を実際には書かない（検査で本番の記録を汚さない）。"""

    def __init__(self, sink):
        self.sink = sink

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def write(self, text):
        self.sink.append(text)



def _ledger(written: list[str]) -> str:
    """**記録の行**（`data/batch_runs.jsonl` に積まれるほうの1行）を拾う。

    **`written[0]` ではありません**（2026-08-23 に直した）。8/22 の A/B が
    同じ sink に `{"at": …, "topic": …, "opening_motion": …}` を**本数ぶん先に**
    書くようになったので、`written[0]` はその行になり、**この4件の検査が
    「予約時刻の並び」ではなく「先頭が何の行か」を見て**落ちていました。

    A/B の行と記録の行は **どちらも `opening_motion` を持ちます**（記録の行は
    その回の旗を丸ごと残すため）。**持っていないほうで分けられません。**
    記録の行だけが持つのは `results` です。
    """
    for row in written:
        if '"results"' in row:
            return row
    raise AssertionError(f"記録の行が1つも書かれていません: {written!r}")


def _slots(written: list[str]) -> list[str]:
    """**その回が実際に使った枠**を、記録の行から読む（2026-08-30 に足した）。

    ここには長らく `assert "vid-a-2026-08-30@9" in row` と**時刻がべた書き**して
    ありました。**枠の並べ方は 08/30 00:17 に「添字」から「時刻」へ変わり**
    （`live_ring()` が返すのは埋め順 13:30, 13:30, 9:30 …）、
    **この3件だけが古い語彙のまま赤くなりました。**

    この3件が守りたいのは「枠が 9時・10時・11時 であること」ではありません ——
    **`n` 番目のテーマが `n` 番目の枠に載ること**（完了順に積むとずれる）です。
    だから**その回の `slots` と突き合わせます。** 次に枠の作り方が変わっても、
    この3件は意味のほうを見つづけます。

    **覆る条件**: 記録の行が `slots` を持たなくなったら、ここで落ちます
    （そのときは、何を突き合わせるかを決め直すこと）。
    """
    row = json.loads(_ledger(written))
    slots = row.get("slots")
    assert slots, f"記録の行に `slots` がありません: {row!r}"
    return list(slots)


def _vid(topic: str, slot: str) -> str:
    """検査の偽 uploader が返す動画ID（`vid-{topic}-{slot}`。同ファイル上部）。"""
    return f"vid-{topic}-{slot}"


# --- 1. 順番が崩れないこと -------------------------------------------------

def test_slow_first_video_does_not_lose_its_slot(monkeypatch):
    """**1本目がいちばん遅くても、1本目の枠は1本目のもの。**

    完了順に積む実装だと、ここで `a` が `c` の 12:00 を取ります。
    """
    _, rec, _ = _run(
        monkeypatch, ["a", "b", "c"],
        delays={"a": 0.25, "b": 0.05, "c": 0.0},
    )
    uploads = [(t, ) for k, t in rec.calls if k == "upload"]
    assert uploads == [("a",), ("b",), ("c",)]


def test_slot_hour_matches_topic_order(monkeypatch):
    """予約時刻そのものが、テーマの並び順どおりに割り当たること。"""
    _, rec, written = _run(
        monkeypatch, ["a", "b", "c"], delays={"a": 0.2, "b": 0.1},
    )
    row, slots = _ledger(written), _slots(written)
    # **`zip` は黙って短いほうに合わせます。** 枠が2つしか出なかった回は、
    # ここが**素通り**になります（検査が消えたことに誰も気づかない形）。
    assert len(slots) >= 3, f"枠が3つ出ていません（検査が素通りになります）: {slots}"
    for topic, slot in zip(("a", "b", "c"), slots):
        assert _vid(topic, slot) in row, (
            f"{topic} が自分の枠（{slot}）に載っていません —— "
            f"完了順に積むと、ここでずれます。使った枠: {slots}")


# --- 2. 予約は同時に走らないこと -------------------------------------------

def test_uploads_never_overlap(monkeypatch):
    """**予約は1本ずつ。** ここが2以上になったら共有状態がぶつかります。"""
    _, rec, _ = _run(monkeypatch, ["a", "b", "c", "d"], jobs=4)
    assert rec.max_concurrent_upload == 1


# --- 3. 作る段は本当に並んでいること ---------------------------------------

def test_builds_actually_overlap(monkeypatch):
    """直列に戻っていないこと。**3本 × 0.2秒が、0.6秒かからない。**"""
    began = time.monotonic()
    _run(monkeypatch, ["a", "b", "c"],
         delays={"a": 0.2, "b": 0.2, "c": 0.2}, jobs=3)
    assert time.monotonic() - began < 0.5


def test_jobs_1_is_the_old_behaviour(monkeypatch):
    """`--jobs 1` なら直列。**逃げ道を残しておく**（並列で壊れたとき用）。"""
    began = time.monotonic()
    _run(monkeypatch, ["a", "b", "c"],
         delays={"a": 0.15, "b": 0.15, "c": 0.15}, jobs=1)
    assert time.monotonic() - began >= 0.45


# --- 4. 落ちた1本が、他の本を巻き添えにしないこと ---------------------------

def test_failed_build_is_not_uploaded_and_others_survive(monkeypatch):
    """**作れなかった本は予約しない。** 残りはそのまま出る。

    直列版は `continue` で枠を飛ばしていました。並列版でも同じであること。
    """
    _, rec, written = _run(monkeypatch, ["a", "b", "c"], fail_build={"b"})
    uploaded = [t for k, t in rec.calls if k == "upload"]
    assert uploaded == ["a", "c"]
    # **b の枠（2番目）は誰も取らない。** c は自分の3番目のまま。
    # 記録の `slots` には b の枠が残るので、見るのは**動画IDのほう**です。
    slots = _slots(written)
    assert _vid("c", slots[2]) in _ledger(written), "c が自分の枠を離れています"
    assert _vid("c", slots[1]) not in written[0], "c が b の空き枠へ繰り上がっています"
    assert _vid("a", slots[1]) not in written[0], "a が b の空き枠へずれています"


def test_failed_build_skips_its_contact_sheet(monkeypatch):
    """生成が落ちた本の contact sheet は作らない（材料が無いので）。"""
    _, rec, _ = _run(monkeypatch, ["a", "b"], fail_build={"a"})
    inspected = [t for k, t in rec.calls if k == "inspect"]
    assert inspected == ["b"]


def _open_window():
    """「まだ 92本ぶん撃てる」＝門を素通り。**枠そのものの検査は
    `tests/test_upload_cap.py`** にあります。"""
    from datetime import datetime, timezone

    from src import upload_cap

    return upload_cap.State(False, 0, upload_cap.CAP_PER_DAY,
                            datetime.now(timezone.utc), "検査（枠は開いている）")


# --- 5. 落ちた本を、その場でもう一度だけ作ること ---------------------------
#
# 2026-08-19 19:2x に `data/batch_runs.jsonl` の 449本を数えた結果:
#
#     直前が失敗 → 次の試行が成功   46/85 = **54%**（`生成が失敗` に絞っても 38/70）
#     落ち2回以上のテーマ 16件のうち **13件は最後に通って投稿済み**（成功0回は1件だけ）
#
# ＝**「必ず落ちるテーマ」はほぼ無く、失敗の半分はその回かぎりのぶれ**でした。
# だから `pick` から外す門は効きません。効くのは撃ち直しのほうです。
# そして撃ち直しは**テーマ在庫を1件も減らさない**（多めに作る手との違いはここ）。


class _FlakyRecorder(_Recorder):
    """**1回目だけ落ちる**。2回目は通る ＝ 実測のぶれと同じ形。"""

    def __init__(self, flaky: set[str], **kw):
        super().__init__(**kw)
        self.seen: dict[str, int] = {}

    def __call__(self, cmd, timeout, label="", env=None):
        if "src.pipeline" in cmd:
            tid = label or "?"
            self.seen[tid] = self.seen.get(tid, 0) + 1
            if tid in self.fail_build:
                # 親も `fail_build` を見て落とすので、**ここで返しきる**こと。
                self.calls.append(("build", tid))
                return (1, "生成に失敗しました") if self.seen[tid] == 1 else (0, "")
        return super().__call__(cmd, timeout, label)


def _run_flaky(monkeypatch, ids, flaky, extra=()):
    rec = _FlakyRecorder(flaky, fail_build=flaky)
    monkeypatch.setattr(batch_build, "run", rec)
    monkeypatch.setattr(batch_build, "pick",
                        lambda c, e, per_calc=None, **k: _topics(ids))
    monkeypatch.setattr(batch_build, "check_window", lambda d, f: None)
    monkeypatch.setattr(batch_build.upload_cap, "state", lambda: _open_window())
    _pin_rule(monkeypatch)          # 規則（1日1本）は主題ではない（上の註）
    written: list[dict] = []
    monkeypatch.setattr(batch_build.Path, "open",
                        lambda self, *a, **k: _Sink(written))
    code = batch_build.main([
        "--count", str(len(ids)), "--date", "2026-08-30", "--jobs", "3", *extra,
    ])
    return code, rec, written


def test_flaky_build_is_retried_once_and_uploaded(monkeypatch):
    """**1回目で落ちた本が、作り直しで通って予約まで入る。**

    ここが無いと、ぶれで落ちた1本ぶんの枠が毎回そのまま空きます。
    """
    _, rec, _ = _run_flaky(monkeypatch, ["a", "b", "c"], flaky={"b"})
    builds = [t for k, t in rec.calls if k == "build"]
    assert builds.count("b") == 2, "落ちた本を作り直していない"
    uploaded = [t for k, t in rec.calls if k == "upload"]
    assert uploaded == ["a", "b", "c"], "作り直した本が予約に載っていない"


def test_retry_does_not_consume_another_topic(monkeypatch):
    """**作り直しはテーマを増やさない。** 在庫が律速なので、ここが肝。"""
    _, rec, _ = _run_flaky(monkeypatch, ["a", "b", "c"], flaky={"b"})
    tried = {t for k, t in rec.calls if k == "build"}
    assert tried == {"a", "b", "c"}, "作り直しで別のテーマを使っている"


def test_retry_keeps_the_slot_order(monkeypatch):
    """作り直した本が、**自分の枠**に戻ること（完了順に積むと枠がずれる）。"""
    _, _, written = _run_flaky(monkeypatch, ["a", "b", "c"], flaky={"a"})
    row, slots = _ledger(written), _slots(written)
    # **`zip` は黙って短いほうに合わせます。** 枠が2つしか出なかった回は、
    # ここが**素通り**になります（検査が消えたことに誰も気づかない形）。
    assert len(slots) >= 3, f"枠が3つ出ていません（検査が素通りになります）: {slots}"
    for topic, slot in zip(("a", "b", "c"), slots):
        assert _vid(topic, slot) in row, (
            f"作り直した本が自分の枠（{topic} → {slot}）に戻っていません。使った枠: {slots}")


def test_no_retry_flag_restores_the_old_behaviour(monkeypatch):
    """`--no-retry` で従来どおり。**逃げ道を残す**（時間が無い回のため）。"""
    _, rec, _ = _run_flaky(monkeypatch, ["a", "b", "c"], flaky={"b"},
                           extra=("--no-retry",))
    builds = [t for k, t in rec.calls if k == "build"]
    assert builds.count("b") == 1
    uploaded = [t for k, t in rec.calls if k == "upload"]
    assert uploaded == ["a", "c"]


def test_two_failures_are_marked_in_the_ledger(monkeypatch):
    """**2回とも落ちた本は、そう書く。** テーマ側を疑う材料はここにしか残らない。"""
    rec = _Recorder(fail_build={"b"})          # 何度でも落ちる
    monkeypatch.setattr(batch_build, "run", rec)
    monkeypatch.setattr(batch_build, "pick",
                        lambda c, e, per_calc=None, **k: _topics(["a", "b", "c"]))
    monkeypatch.setattr(batch_build, "check_window", lambda d, f: None)
    monkeypatch.setattr(batch_build.upload_cap, "state", lambda: _open_window())
    _pin_rule(monkeypatch)          # 規則（1日1本）は主題ではない（上の註）
    written: list[dict] = []
    monkeypatch.setattr(batch_build.Path, "open",
                        lambda self, *a, **k: _Sink(written))
    batch_build.main(["--count", "3", "--date", "2026-08-30", "--jobs", "3"])
    assert "2回とも" in _ledger(written)
