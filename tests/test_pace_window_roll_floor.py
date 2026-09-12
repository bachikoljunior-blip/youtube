"""**枠が「本当に回った」直後に、床がまるごと消えていた回**（2026-09-12 08:1x に踏んだ）。

`_gauge_reset()` が見つけるのは「**同じ枠の中で**%が戻された」回だけです
（2026-09-02 の実物 ＝ `resets_at_iso` が動かないまま 73% → 3%）。
**`resets_at_iso` が 7日 進んだ回 ＝ 本当のリセットは、そこに引っかかりません。**

実物（`data/usage.jsonl`）::

    09/11 19:23 JST  88%   resets 09/11 22:00Z（＝ 09/12 07:00 JST）
    09/12 07:20 JST   0%   resets 09/18 22:00Z   ← **枠ごと回った**

この回の `pace()` は

    used   = 0%（新しい枠の目盛り）
    births = 0（枠の頭 07:00 から目盛りの 07:20 までに周は立っていない）
    pre    = None（`_gauge_reset()` が None ＝ 床が当たらない）

となり、`per_lap` も `floor_min` も None。**下流が 4つ とも黙りました**::

    next_round.floor_minutes()     → FALLBACK_MIN（90分）。実測できていた床は 54.6分
    spawn_prompt._quota_block()    → 【枠】の段を**まるごと落とす**
    quota.pace_report()            → 「誕生を1件も数えられていません」だけ
    short_words / margin_line / sweep_verdict / clamp_eta → 何も言わない

＝ **枠が戻った回は、新しい目盛りが貼られるほうが、貼られないより悪い**という形でした
（貼られなければ `pace()` の `rolled` の枝が、前の枠の `per_lap` でそのまま運びます）。
親は実際に **90分**（`data/parent_wakes.jsonl` の `source` が「目盛りが無いか…」）で回り、
**枠がいちばん空いている刻に、鎖がいちばん遅く**なっていました（オーナー 09/11 19:4x
「フェイブルずっと使えるように調整するよな？」＝ 枠は配って使い切る側）。

固定するのは4つ:

  1. 枠ごと回った回も、**前の枠で測れていた `per_lap` を床に当てる**
     （1周の重さは枠が戻っても軽くならない ＝ `_per_lap_before` の註）
  2. **`rate` には当てない** —— 新しい枠は本当に 0% から始まっている
  3. `--pace` は、`births` が 0 でも**床が在れば印字する**
  4. 「いまの間隔のまま」が読めない回も、**「床に従えば」と門の判定は印字する**
     （§5 15:1x の門 98% が当てるのは床の側・13:1x）
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import quota  # noqa: E402

UTC = timezone.utc

OLD_RESET = "2026-09-11T22:00:00Z"                        # 09/12 07:00 JST
NEW_RESET = "2026-09-18T22:00:00Z"                        # 09/19 07:00 JST
OLD_START = datetime(2026, 9, 4, 22, 0, tzinfo=UTC)       # 09/05 07:00 JST
OLD_AT_1 = "2026-09-11T12:38:00+09:00"
OLD_AT_2 = "2026-09-11T19:23:00+09:00"
NEW_AT = "2026-09-12T07:20:00+09:00"
NOW_AT = "2026-09-12T08:15:00+09:00"


@pytest.fixture(autouse=True)
def _restore():
    usage, log, rounds = quota.USAGE_LOG, quota.LOG, quota.ROUNDS_LOG
    yield
    quota.USAGE_LOG, quota.LOG, quota.ROUNDS_LOG = usage, log, rounds


def _write(tmp_path, anchors, *, laps_per_hour=1.0):
    usage = tmp_path / "usage.jsonl"
    usage.write_text("".join(json.dumps({
        "fetched_at": at, "window_id": "seven_day",
        "used_percent": used, "resets_at_iso": rst,
    }) + "\n" for at, used, rst in anchors), encoding="utf-8")

    # **周は枠の頭ちょうどには立ちません**（実物の 09/12 の枠も、頭 07:00 から
    # 目盛りの 07:20 までに 1周も立っていない ＝ `births` 0）。30分 ずらして並べる。
    step = timedelta(hours=1 / laps_per_hour)
    rows, born = [], OLD_START + timedelta(minutes=30)
    end = datetime.fromisoformat(NOW_AT).astimezone(UTC)
    while born <= end:
        rows.append({"at": born.isoformat(), "role": "hourly", "round": born.isoformat()})
        born += step
    log = tmp_path / "quota.jsonl"
    log.write_text("", encoding="utf-8")
    rounds = tmp_path / "rounds.jsonl"
    rounds.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    quota.USAGE_LOG, quota.LOG, quota.ROUNDS_LOG = usage, log, rounds


def _now():
    return datetime.fromisoformat(NOW_AT).astimezone(UTC)


def _rolled(tmp_path):
    _write(tmp_path, [(OLD_AT_1, 83, OLD_RESET),
                      (OLD_AT_2, 88, OLD_RESET),
                      (NEW_AT, 0, NEW_RESET)])
    return quota.pace(_now())


def test_枠ごと回った回は_gauge_reset_では見つからない(tmp_path):
    """**この前提が崩れたら、下の 3件 は別の理由で通ります。**"""
    p = _rolled(tmp_path)
    assert p["reset_at"] is None, "同じ枠の中の戻しではない ＝ ここは None が正しい"
    assert p["births"] == 0, "新しい枠の頭から目盛りまでに周は立っていない"


def test_枠ごと回っても1周の重さは前の枠から床が当たる(tmp_path):
    p = _rolled(tmp_path)
    assert p["per_lap"], "床が当たらないと `floor_min` ごと消える（この回に踏んだ形）"
    assert p["per_lap_floored"] is True
    assert p["pre"] is not None
    assert p["pre"]["at"] == datetime.fromisoformat(OLD_AT_2)
    assert p["per_lap"] == pytest.approx(p["pre"]["per_lap"], rel=1e-9)


def test_床が出れば持続できる間隔も出る(tmp_path):
    p = _rolled(tmp_path)
    assert p["floor_min"] is not None
    assert p["floor_min"] == pytest.approx(p["per_lap"] / p["forward_rate"] * 60, rel=1e-6)
    assert p["floor_min"] < 90.0, "FALLBACK_MIN（90分）より速い側でなければ、直した意味がない"


def test_速さの側には床を当てない(tmp_path):
    """**新しい枠は本当に 0% から始まっています。** ここに前の枠の %/時 を当てると、
    推定が上に外れ、`used_now` が実測でないぶんだけ膨らみます。

    **2026-09-12 12:3x に `used_now == 0.0` を外しました**（optimizer・Opus）——
    あれは「速さを当てていない」ではなく、**周で運ぶ門が借りた床に来ていなかった**
    せいで出ていた数でした（`carry_rate` が 0.000 %/時 ＝ 同じ枠に2点目が無い）。
    **当てないのは `rate` のほうだけ**で、**立った周のぶんは運びます**
    （`quota.pace` の 12:3x の註・検査 `tests/test_pace_carry_by_laps.py`）。
    ここで 0.0 を不変条件として書くと、**何周 立っても 0% と言う側**を固定します
    （METHOD §5 教訓の形 6つ目）。
    """
    p = _rolled(tmp_path)
    assert p["rate_floored"] is False
    # **速さは当たっていない**: 借りた `rate` はどこにも入っていない
    assert p["pre"] is not None and p["pre"]["rate"] > 0
    assert p["carry_rate"] != pytest.approx(p["pre"]["rate"], rel=1e-9)
    # **周のぶんは運ぶ**: 借りた 1周の重さ × 目盛りの後に立った周
    assert p["carry_mode"] == "laps"
    assert p["used_now"] == pytest.approx(p["carried_laps"] * p["per_lap"], rel=1e-9)


def test_普通の枠は1つも動かない(tmp_path):
    """**陽性対照の裏側** —— 枠が回っていない回で床を当ててしまうと、
    測れている `per_lap` が前の枠の数に押し上げられます。"""
    _write(tmp_path, [(OLD_AT_1, 83, OLD_RESET), (OLD_AT_2, 88, OLD_RESET)])
    p = quota.pace(datetime.fromisoformat(OLD_AT_2).astimezone(UTC))
    assert p["per_lap_floored"] is False
    assert p["pre"] is None


def test_pace_report_は床を印字する(tmp_path, capsys):
    """**METHOD が指している口はこちら**（「空欄を『余裕がある』と読まないこと —— `--pace`」）。"""
    _rolled(tmp_path)
    quota.pace_report(_now())
    out = capsys.readouterr().out
    assert "誕生を1件も数えられていません" not in out
    assert "持続できる間隔" in out
    assert "床に従えば" in out, "§5 15:1x の門（98%）が当てるのは床の側"
    assert "いまの間隔のまま **読めません**" in out, "空欄で出さないこと"


# --- **値は戻ったのに、名乗りだけが送られていなかった側**（2026-09-12 09:3x に踏んだ） ---
#
# 08:1x の直しは `pace()` に `_per_lap_before()` を足して **値**（床 54.3分）を戻しましたが、
# **その床が「借りた床」だと言う口**は 3つ のうち **1つ**（`--pace`）しか送られていません
# でした。残る 2つ は、毎周 かならず読まれる側です:
#
#     next_round.floor_minutes()[1]    親が `data/parent_wakes.jsonl` の `source` に書く
#     spawn_prompt._quota_block()      サブの本文の【枠】の段（毎周 2体 が読む）
#
# `floor_minutes()` の枝は `per_lap_floored` **かつ** `births` で見ており、
# **枠が本当に回った直後は `births` が 0** なので素通りして、裸の
# **「quota.py の実測」**を返していました（実物 09/12 08:43〜09:05 の 3件）。
# ＝ **値は正しく、名乗りだけが「いまの枠で測れた」と読める側の嘘**で、
# §7 (e-1c) が次の回に見張らせている `per_lap_floored` を打ち消す向きに出ます。
# METHOD §5 の教訓の形 **10つ目**（枠を送る直しをしたら、その枠を分母に使っている行を
# 全部 数えること）と **7つ目**（覆る条件を註に書いたら、それを読む印字も一緒に作ること）。


def test_借りた床は句を返し_測れている枠は空(tmp_path):
    """**句の出どころは `quota.per_lap_words()` 1か所**（覆る条件 (2)）。"""
    p = _rolled(tmp_path)
    words = quota.per_lap_words(p)
    assert words, "借りた床の回に空を返すと、下の 2つ の口が黙る"
    assert "この枠で測った数ではありません" in words
    assert "0件" in words, "`births` 0 の回は、その 0 を言うこと"
    assert "09/11 19:23" in words, "どこまでの実測を借りたかを言うこと"

    # **陽性対照の裏側** —— 測れている枠では空でなければならない
    # （空でないと、普通の枠が毎周「借りた床」と名乗ります）
    _write(tmp_path, [(OLD_AT_1, 83, OLD_RESET), (OLD_AT_2, 88, OLD_RESET)])
    ok = quota.pace(datetime.fromisoformat(OLD_AT_2).astimezone(UTC))
    assert quota.per_lap_words(ok) == ""
    assert quota.per_lap_words({}) == ""
    assert quota.per_lap_words(None) == ""


def _patched_quota(tmp_path, monkeypatch):
    """**借りた床の `pace()` を返す `quota` を、`scripts.quota` としても見せる。**

    `next_round` / `spawn_prompt` は `from scripts.quota import ...` で引くので、
    **同じファイルでも `quota`（裸）と `scripts.quota` は別の module object**です
    （§5 の教訓の形 11つ目）。`monkeypatch` が `sys.modules` を終わりに戻します。
    `pace` は**定数の返り**に差し替えます —— `_rolled()` を返り値の中で呼ぶと、
    差し替えた `pace` を自分で呼び直して回ります。
    """
    import importlib

    rolled = _rolled(tmp_path)
    monkeypatch.setattr(quota, "pace", lambda *a, **k: rolled)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    scripts_pkg = importlib.import_module("scripts")
    monkeypatch.setitem(sys.modules, "scripts.quota", quota)
    monkeypatch.setattr(scripts_pkg, "quota", quota, raising=False)
    return rolled


def test_floor_minutes_は借りた床を実測と名乗らない(tmp_path, monkeypatch):
    """**この回に踏んだ当のもの** —— `births` 0 で 2つ の枝を素通りし、
    親は `data/parent_wakes.jsonl` に裸の「quota.py の実測」を書いていた。"""
    import importlib

    rolled = _patched_quota(tmp_path, monkeypatch)
    sys.path.insert(0, str(ROOT / "scripts"))
    nr = importlib.import_module("next_round")

    got, source = nr.floor_minutes()
    assert got == pytest.approx(rolled["floor_min"], rel=1e-6), "床は戻っている（08:1x の直し）"
    assert got < 90.0
    assert source != "quota.py の実測", "借りた床を『実測』と名乗らないこと（この回の欠陥）"
    assert "この枠で測った数ではありません" in source
    assert source == quota.per_lap_words(rolled), "句は 1か所 から引くこと"


def test_サブの本文の枠の段も借りた床だと言う(tmp_path, monkeypatch):
    """**毎周 2体 が読むのはこちら**（`--pace` は撃った回しか読まない）。"""
    import importlib

    rolled = _patched_quota(tmp_path, monkeypatch)
    sys.path.insert(0, str(ROOT / "scripts"))
    sp = importlib.import_module("spawn_prompt")

    block = sp._quota_block()
    floor_line = [ln for ln in block.splitlines() if ln.strip().startswith("床")]
    assert floor_line, "【枠】の段に床の行が出ていること"
    assert "この枠で測った数ではありません" in floor_line[0]
    assert quota.per_lap_words(rolled) in floor_line[0], "句は 1か所 から引くこと"
