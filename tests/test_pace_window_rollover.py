"""**目盛りの枠が閉じたあと、鎖が自分で自分を止めていた**（2026-08-22 07:2x に踏んだ）。

`pace()` は「目盛りの枠 ＝ いまの枠」を前提にしていました。%はこの機械からは
読めず（`rate_limit_info` は `allowed`/`warning`/`rejected` だけ）、
**目盛りはオーナーが画面を貼ったときにしか入りません。** だから枠のリセットは
必ず目盛りより先に来ます。またいだ瞬間、実物はこう出ていました ——

    枠: 08/15 07:00 → 08/22 07:00 JST      ← **07:00 に閉じ終わっている**
    いま（推定）: 97.3%
    この先に許される速さ: 0.000 %/時（残り 2.7% ÷ 残り **-0.3時間**）
    持続できる間隔（誕生から誕生）: **90分**   ← `FLOOR_MAX_CLAMP`

`forward_rate <= 0` の枝は `floor = FLOOR_MAX_CLAMP` を返します。
**枠の中で使い切ったときは、それが正しい**（閉じた枠に鎖を突っ込まない）。
**またいだ後は、まるごと逆です** —— 新しい枠は 0% から始まっているのに、
鎖は**いちばん広い間隔まで開かれ**、`sibling_check --phase spawn` が次の子を
止めます。そして直る条件は「オーナーが新しい%を貼ること」だけでした。

**人の操作を待つ形が、計器そのものに埋まっていた**わけです
（CLAUDE.md「人間の作業に依存する計画を立てないこと」）。しかも壊れ方は
**投稿が薄くなる側**に出ます —— 週が変わるたびに、いちばん budget がある回で
いちばん間隔が開く。

固定するのは4つ:

  1. **またいだら枠を送ること**（`window_start` / `window_reset` が現在の枠）
  2. **古い%を持ち越さないこと** —— 新しい枠の使用済みは1点も測れていないので、
     **頭 0% から直近の速さで運んだ推定**に置く（凍らせて 0 とも言わない）
  3. **`floor_min` が天井に貼りつかないこと** —— 90分（`FLOOR_MAX_CLAMP`）ではなく、
     枠が空いているぶんだけ詰められること
  4. **またいでいない回は、1つも変わらないこと**（この直しの巻き添えを塞ぐ）
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
JST = timezone(timedelta(hours=9))

# 実物と同じ形。週枠 08/15 07:00 → **08/22 07:00 JST**（= 08/21 22:00Z）。
RESET_ISO = "2026-08-21T22:00:00Z"
RESET = datetime(2026, 8, 21, 22, 0, tzinfo=UTC)
START = RESET - timedelta(days=7)


@pytest.fixture(autouse=True)
def _restore():
    usage, log = quota.USAGE_LOG, quota.LOG
    yield
    quota.USAGE_LOG, quota.LOG = usage, log


def _write(tmp_path, anchors, births=200):
    """`anchors` は `(fetched_at_iso, used_percent)` の並び。誕生は枠の頭から10分おき。"""
    usage = tmp_path / "usage.jsonl"
    usage.write_text("".join(json.dumps({
        "fetched_at": at, "window_id": "seven_day",
        "used_percent": used, "resets_at_iso": RESET_ISO,
    }) + "\n" for at, used in anchors), encoding="utf-8")

    rows = []
    for i in range(births):
        born = START + timedelta(minutes=10 * i)
        rows.append({"seen_at": born.isoformat(), "born_at": born.isoformat(),
                     "session_id": f"session_{i:03d}", "tags": ["youtube-hourly"]})
    log = tmp_path / "quota.jsonl"
    log.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    quota.USAGE_LOG, quota.LOG = usage, log


# 実物（08/22 07:2x）と同じ2点。95% で閉じた枠。
ANCHORS = [("2026-08-21T08:07:00+09:00", 92), ("2026-08-21T21:10:00+09:00", 95)]


def test_枠をまたいだら枠のほうを送る(tmp_path):
    """**閉じた枠を「いまの枠」として出さないこと。** ここが全部の起点。"""
    _write(tmp_path, ANCHORS)
    p = quota.pace(RESET + timedelta(minutes=22))      # 08/22 07:22 JST

    assert p["rolled"] == 1
    assert p["window_start"] == RESET                  # 新しい枠の頭 ＝ 古い枠のリセット
    assert p["window_reset"] == RESET + timedelta(days=7)
    # 目盛りが属していた枠も、消さずに残すこと（報告が「どの枠の%か」を言えなくなる）
    assert p["gauge_window_reset"] == RESET
    assert p["gauge_window_start"] == START


def test_残り時間が負にならない(tmp_path):
    """**`-0.3時間` が `0.000 %/時` を作り、それが天井の間隔を作っていた。**"""
    _write(tmp_path, ANCHORS)
    p = quota.pace(RESET + timedelta(minutes=22))

    assert p["left_hours"] > 0
    assert p["left_hours"] == pytest.approx(168 - 22 / 60, abs=0.05)
    assert p["forward_rate"] > 0
    # 枠が空いているので、基準線（0.595 %/時）とほぼ同じところまで戻ること
    assert p["forward_rate"] == pytest.approx(quota.SUSTAIN_PCT_PER_HOUR, abs=0.01)


def test_古い目盛りを持ち越さない(tmp_path):
    """**新しい枠の使用済みは1点も測れていない。** 95% を持ち越すのは嘘。

    かといって「0%」と凍らせるのも嘘です（回は現に走っている）。
    **頭 0% から直近の速さで運んだ推定**に置くこと ——
    `eta.py` が「凍らせた企画の恒真式を出すな」と言われたのと同じ形です。
    """
    _write(tmp_path, ANCHORS)
    p = quota.pace(RESET + timedelta(minutes=22))

    assert p["anchor_used"] == 95                      # 目盛りそのものは 95% のまま
    assert p["used_now"] < 1.0                         # **持ち越していない**
    # 直近の区間 0.230 %/時 を 0.37時間ぶん運んだもの
    assert p["used_now"] == pytest.approx(p["carry_rate"] * 22 / 60, rel=0.02)
    assert p["carried_hours"] == pytest.approx(22 / 60, abs=0.02)


def test_間隔が天井に貼りつかない(tmp_path):
    """**壊れ方は「投稿が薄くなる」側に出ていた。** 90分は `FLOOR_MAX_CLAMP` そのもの。"""
    _write(tmp_path, ANCHORS)
    p = quota.pace(RESET + timedelta(minutes=22))

    assert p["floor_min"] < quota.FLOOR_MAX_CLAMP
    # 1周いくら ÷ 許される速さ × 60。枠が丸ごと空いているので、素直な算術に戻る
    assert p["floor_min"] == pytest.approx(p["per_lap"] / p["forward_rate"] * 60, abs=0.5)
    assert quota.recommended_floor_minutes(RESET + timedelta(minutes=22)) == p["floor_min"]


def test_何枠ぶんまたいでも現在の枠を出す(tmp_path):
    """目盛りが2週間入らないこともある（オーナーが画面を貼らなければ入らない）。"""
    _write(tmp_path, ANCHORS)
    p = quota.pace(RESET + timedelta(days=15))

    assert p["rolled"] == 3
    assert p["window_start"] == RESET + timedelta(days=14)
    assert p["window_reset"] == RESET + timedelta(days=21)
    assert 0 < p["left_hours"] <= 168


def test_またいでいない回は何も変わらない(tmp_path):
    """**この直しの巻き添えを塞ぐ。** 枠の中では、これまでと同じ式であること。"""
    _write(tmp_path, ANCHORS)
    now = RESET - timedelta(hours=5)                   # まだ枠の中（08/22 02:00 JST）
    p = quota.pace(now)

    assert p["rolled"] == 0
    assert p["window_start"] == START and p["window_reset"] == RESET
    # 目盛り 95% を、目盛りの時刻から `now` まで運んだもの（従来どおり）
    carried = (now - datetime.fromisoformat(ANCHORS[-1][0])).total_seconds() / 3600
    assert p["used_now"] == pytest.approx(95 + carried * p["carry_rate"], rel=1e-6)
    assert p["left_hours"] == pytest.approx(5.0, abs=0.01)


def test_枠の中で使い切った回は今も天井まで開く(tmp_path):
    """**またいだ後と、使い切ったのとを取り違えないこと。**

    `forward_rate <= 0` → `FLOOR_MAX_CLAMP` の枝は**残すのが正しい**。
    閉じかけの枠に鎖を突っ込み続ければ、リセットまで1回も起きられません。
    ここが消えていないことを固定します。
    """
    _write(tmp_path, [("2026-08-21T08:07:00+09:00", 92),
                      ("2026-08-21T21:10:00+09:00", 100)])
    p = quota.pace(RESET - timedelta(minutes=30))      # 枠の中・使い切っている

    assert p["rolled"] == 0
    assert p["used_now"] >= 100.0
    assert p["forward_rate"] == 0.0
    assert p["floor_min"] == quota.FLOOR_MAX_CLAMP


def test_報告が閉じた枠だと言う(tmp_path, capsys):
    """**黙って直さないこと。** 読む側が「なぜ%が落ちたか」を追えなくなる。"""
    _write(tmp_path, ANCHORS)
    quota.pace_report(RESET + timedelta(minutes=22))
    out = capsys.readouterr().out

    assert "閉じた枠のもの" in out
    assert "1点も測れていません" in out
    assert "残り%を理由に作業を見送らないこと" in out
    assert "いまの枠" in out
    assert "残り -" not in out          # 残り時間が負のまま出ていた行
