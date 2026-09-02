"""週枠を均して使い切るための「速さ」を固定する（2026-08-15）。

**なぜ要るか。** 8/12〜8/14 に**58時間、鎖が丸ごと止まりました**。枠を先に
使い切ったからです。8/15 に自走（`docs/trigger_main.md` §6 (f)）を入れて空転を
消したぶん、**回転が上がって同じ穴に近づきました** —— オーナーの実測で
0.758 %/時、持続できる速さの **+27%**。このままなら 8/20 19:00 に 100% に達し、
リセットまで36時間止まります。

**この計算が静かに壊れると、壊れたことに気づけません。** `quota.py --pace` が
None を返せば `sibling_check.py` は待たなくなり、鎖は元の速さに戻り、
**次に気づくのは枠が閉じたとき**です。だから機械に見張らせます。

固定するのは4つ:

  1. **目盛りの算術**（%÷誕生数 → 1周いくら → 持続できる間隔）
  2. **目盛りが無いとき None を返すこと** —— **止めないこと。**
     測れないことを理由に鎖を止めるのは、58時間と同じ損失
  3. **上下の歯止め** —— 計器が暴れても間隔が0分にも1日にもならない
  4. **`sibling_check --phase spawn` が実際に待たせること**（終了コード5）
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import quota  # noqa: E402

JST = timezone(timedelta(hours=9))
UTC = timezone.utc

# 8/15 の実物と同じ形。リセット 8/15 07:00 JST → 8/22 07:00 JST。
RESET = "2026-08-21T22:00:00Z"
START = datetime(2026, 8, 14, 22, 0, tzinfo=UTC)
ANCHOR_AT = "2026-08-15T20:12:00+09:00"


def _now(iso: str) -> datetime:
    """その目盛りを取った瞬間を `now` として渡す。

    **2026-08-21 まで、`pace()` は `now` を見ずに目盛りの時刻で
    「残り ÷ 残り時間」を割っていました。** 目盛りは人手でしか入らないので
    必ず古くなり、そのぶん**必ず「速すぎてよい」側へ外れます**（実測で 9%）。
    いまは `now` から数えるので、**古い前提の検査は `now` を明示すること。**
    """
    return datetime.fromisoformat(iso).astimezone(UTC)


def _write(tmp_path, used_percent, births, *, window="seven_day", anchor_at=ANCHOR_AT,
           extra_anchors=(), extra_births=()):
    """%の点と、誕生を持つ計器を作る。

    `births` は枠の頭から10分おきに並べる。`extra_anchors` は
    `(fetched_at, used_percent[, window])` の並びで、2点目以降を足す。
    `extra_births` は `(born_at, 件数)` の並びで、区間の中の誕生を足す。
    """
    lines = [json.dumps({
        "fetched_at": anchor_at, "window_id": window,
        "used_percent": used_percent, "resets_at_iso": RESET,
    })]
    for spec in extra_anchors:
        at, used = spec[0], spec[1]
        win = spec[2] if len(spec) > 2 else "seven_day"
        lines.append(json.dumps({
            "fetched_at": at, "window_id": win,
            "used_percent": used, "resets_at_iso": RESET,
        }))
    usage = tmp_path / "usage.jsonl"
    usage.write_text("\n".join(lines) + "\n", encoding="utf-8")

    rows = []
    for i in range(births):
        born = START + timedelta(minutes=10 * i)
        rows.append({
            "seen_at": born.isoformat(), "born_at": born.isoformat(),
            "session_id": f"session_{i:03d}", "tags": ["youtube-hourly"],
        })
    for j, (at, count) in enumerate(extra_births):
        base = datetime.fromisoformat(at)
        for i in range(count):
            born = base + timedelta(minutes=i)
            rows.append({
                "seen_at": born.isoformat(), "born_at": born.isoformat(),
                "session_id": f"session_x{j}_{i:03d}", "tags": ["youtube-hourly"],
            })
    log = tmp_path / "quota.jsonl"
    log.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    quota.USAGE_LOG, quota.LOG = usage, log
    return usage, log


@pytest.fixture(autouse=True)
def _restore():
    usage, log = quota.USAGE_LOG, quota.LOG
    yield
    quota.USAGE_LOG, quota.LOG = usage, log


def test_算術は実測を再現する(tmp_path):
    """オーナーの実測（13.2時間で10%・誕生33件）から出る数字を固定する。"""
    _write(tmp_path, 10, 33)
    p = quota.pace(_now(ANCHOR_AT))          # **目盛りを取ったその瞬間に読む**

    assert p["births"] == 33
    assert p["hours"] == pytest.approx(13.2, abs=0.05)
    assert p["rate"] == pytest.approx(0.758, abs=0.005)      # %/時
    assert p["per_lap"] == pytest.approx(0.303, abs=0.005)   # 1周いくら
    assert p["over_flat"] == pytest.approx(0.27, abs=0.02)   # 枠の頭から見れば +27%
    assert p["seg"] is None                                  # 点が1つ ＝ 区間は引けない

    # 100% は 8/20 19時ごろ。リセット（8/22 07:00）まで36時間死ぬ。
    assert p["exhaust_at"].astimezone(JST).strftime("%m/%d %H") == "08/20 19"
    assert p["dead_hours"] == pytest.approx(36, abs=1)


def test_基準線は残りを残り時間で割ったもの(tmp_path):
    """**すでに使ったぶんを引いてから割ること**（2026-08-15 夜に直した）。

    枠の頭から見た 0.595 %/時 は「いま 0% から始めるなら」の値で、
    **追い越したぶんを見ていない。** 13.2時間で 10% は基準線（7.9%）を
    2.1% 追い越しており、**この先に許されるのは 0.595 ではなく 0.581 %/時。**
    ここを直さないと、先行しているのに「ほぼ基準どおり」と読めてしまう。
    """
    _write(tmp_path, 10, 33)
    p = quota.pace(_now(ANCHOR_AT))          # **目盛りを取ったその瞬間に読む**
    assert p["left_hours"] == pytest.approx(154.8, abs=0.1)
    assert p["forward_rate"] == pytest.approx(90 / 154.8, abs=0.001)   # 0.581
    assert p["forward_rate"] < quota.SUSTAIN_PCT_PER_HOUR              # 先行 → 厳しくなる
    assert p["over"] == pytest.approx(0.304, abs=0.01)                 # +30%（+27% ではない）
    assert p["floor_min"] == pytest.approx(31.3, abs=0.6)


def test_遅れているときは基準線がゆるむ(tmp_path):
    """**逆向きにも効くこと。** 締めるだけの仕掛けなら、いずれ枠を余らせる。

    余らせるのは「安全」ではありません。**回せたはずの周を捨てています。**
    """
    _write(tmp_path, 4, 33)                    # 13.2時間で4% ＝ 基準線より遅い
    p = quota.pace(_now(ANCHOR_AT))            # **枠の中の時刻を渡すこと**（下の註）
    assert p["forward_rate"] > quota.SUSTAIN_PCT_PER_HOUR
    assert p["over"] < 0
    assert p["floor_min"] < 31                 # 遅れているぶん、詰めてよい


def test_持続できる速さなら死なない(tmp_path):
    """**均して使い切れているときは「止まります」と言わせない。**

    ここが逆に出ると、間に合っているのに間隔を延ばし続けることになる。
    """
    # 13.2時間で7.5% ＝ 0.568 %/時。持続線（0.595）より**下**。
    # 境目は薄い: 8% だと 0.606 %/時 で、これはもう3時間ぶん足りない。
    _write(tmp_path, 7.5, 33)
    p = quota.pace(_now(ANCHOR_AT))            # **枠の中の時刻を渡すこと**（下の註）
    assert p["rate"] == pytest.approx(0.568, abs=0.005)
    assert p["over"] < 0                     # 持続線より遅い
    assert p["dead_hours"] == 0              # リセットまで届く


# --------------------------------------------------------------------------
# 2点目が入ってから（2026-08-15 23:33、オーナーの実測）
# --------------------------------------------------------------------------

SECOND_AT = "2026-08-15T23:33:00+09:00"


def _two_point(tmp_path):
    """実物と同じ形: 20:12 で10%（誕生33件）→ 23:33 で13%（区間に6件）。"""
    return _write(tmp_path, 13, 33, anchor_at=SECOND_AT,
                  extra_anchors=[(ANCHOR_AT, 10)],
                  extra_births=[("2026-08-15T11:20:00+00:00", 6)])


def test_2点目で区間が引ける(tmp_path):
    """**通算は「ならした値」で、これから先を決めるには鈍い。**

    枠の頭からの通算には、鎖が止まっていた3.8時間と、記録だけの軽い回が
    全部ならして入っています。**次の1周がいくらかを言っていません。**
    """
    _two_point(tmp_path)
    p = quota.pace()

    assert p["rate"] == pytest.approx(0.785, abs=0.005)          # 通算
    seg = p["seg"]
    assert seg is not None
    assert seg["used"] == pytest.approx(3.0)
    assert seg["hours"] == pytest.approx(3.35, abs=0.02)
    assert seg["rate"] == pytest.approx(0.896, abs=0.005)        # 区間
    assert seg["births"] == 6
    assert seg["per_lap"] == pytest.approx(0.500, abs=0.005)     # 1周は通算の1.5倍


def test_区間の幅は通算を含む(tmp_path):
    """**「区間のほうが速い」は、この2点からは言えません。**

    オーナーが読めるのは整数の%だけなので、**2点の差は ±1%** です。
    3% の差は [2%, 4%] のどこでもよく、区間の速さは [0.597, 1.194] %/時。
    **通算 0.785 はその中に入っており、区別がつきません。**
    ここを「速くなった」と読むと、無い変化を追いかけて間隔を動かし続けます。
    """
    _two_point(tmp_path)
    seg = quota.pace()["seg"]

    assert seg["rate_lo"] == pytest.approx(0.597, abs=0.005)
    assert seg["rate_hi"] == pytest.approx(1.194, abs=0.005)
    assert seg["rate_lo"] <= 0.785 <= seg["rate_hi"]     # 通算と区別がつかない


def test_区間が短いほど通算へ寄せる(tmp_path):
    """**細い区間に全部を賭けないこと。** Δ% が量子化幅（±1%）の何倍あるか
    で寄せる量を決める。3% なら 3/8 ＝ 38% だけ区間へ。

    全部を区間に賭けると、**1周ぶんの読み取り誤差で間隔が倍半分に振れます。**
    """
    _two_point(tmp_path)
    p = quota.pace(_now(SECOND_AT))          # **目盛りを取ったその瞬間に読む**

    assert p["per_lap_cum"] == pytest.approx(13 / 39, abs=0.005)   # 0.333
    assert p["seg_weight"] == pytest.approx(3.0 / quota.QUANT_FULL_PCT, abs=0.01)
    assert p["per_lap"] == pytest.approx(0.396, abs=0.005)         # 0.333 と 0.500 の間
    assert p["per_lap_cum"] < p["per_lap"] < p["seg"]["per_lap"]
    # **オーナーの上限（2026-09-02「最高速度の二分の一」）が先に効くと 53分 になる。**
    #     ここで見たいのは「寄せ」の側なので、上限を外して 41分 を確かめる。
    #     上限そのものは `test_オーナーの上限は最高速度の半分` が見る。
    assert p["forward_capped"] is True
    assert p["floor_min"] == pytest.approx(
        p["per_lap"] / p["rate_cap"] * 60, abs=1)                 # 上限で頭打ち
    assert p["per_lap"] / p["forward_rate_raw"] * 60 == pytest.approx(41, abs=1)  # 31分 → 41分


def test_オーナーの上限は最高速度の半分(tmp_path):
    """**「今までの最高速度の二分の一の速度でやって」**（2026-09-02・原文）。

    最高速度は目盛りの隣り合う2点の %/時 の最大。上限はその半分で、
    枠の残りから出る「許される速さ」より厳しければ、そちらが効く。
    """
    _two_point(tmp_path)
    mx = quota.max_measured_rate()
    assert mx is not None and mx["rate"] == pytest.approx(0.896, abs=0.005)
    assert quota.owner_rate_cap() == pytest.approx(0.896 / quota.OWNER_SPEED_DIVISOR, abs=0.005)
    p = quota.pace(_now(SECOND_AT))
    assert p["rate_cap"] == pytest.approx(quota.owner_rate_cap(), abs=1e-9)
    assert p["forward_rate"] <= p["rate_cap"] + 1e-9


def test_区間が太れば区間だけで決める(tmp_path):
    """Δ% が量子化幅に対して十分大きくなったら、通算はもう混ぜない。

    **通算は古い区間を引きずるので、混ぜ続けると変化に追随できません。**
    """
    _write(tmp_path, 20, 33, anchor_at=SECOND_AT,
           extra_anchors=[(ANCHOR_AT, 10)],
           extra_births=[("2026-08-15T11:20:00+00:00", 6)])
    p = quota.pace()
    assert p["seg"]["used"] == pytest.approx(10.0)      # 8% を超えた
    assert p["seg_weight"] == pytest.approx(1.0)
    assert p["per_lap"] == pytest.approx(p["seg"]["per_lap"])


def test_別の枠の点では区間を引かない(tmp_path):
    """**リセットをまたいだ2点の差は、消費量ではありません。**

    またいだ先で%は0へ戻るので、差を取ると符号ごと無意味になります。
    """
    _write(tmp_path, 13, 33, anchor_at=SECOND_AT,
           extra_anchors=[(ANCHOR_AT, 10, "five_hour")])   # 5時間枠は拾わない
    p = quota.pace()
    assert p["seg"] is None
    assert p["per_lap"] == pytest.approx(p["per_lap_cum"])


def test_枠を使い切っていたら天井まで空ける(tmp_path):
    """**閉じた枠に鎖を突っ込み続けないこと。**

    ここで None（＝待たない）を返すと、`sibling_check` は素通りさせます。
    """
    _write(tmp_path, 100, 33)
    p = quota.pace(_now(ANCHOR_AT))            # **枠の中の時刻を渡すこと**（下の註）
    assert p["forward_rate"] == 0
    assert p["floor_min"] == quota.FLOOR_MAX_CLAMP


def test_目盛りが無ければ止めない(tmp_path):
    """**%の点が1つも無いとき、`None` を返すこと（0分でも上限でもなく）。**

    `sibling_check` は None を「待ちなし」と読む。**測れないことを理由に
    鎖を止めない** —— 止めれば 8/12 の58時間と同じ損失になる。
    """
    (tmp_path / "usage.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "quota.jsonl").write_text("", encoding="utf-8")
    quota.USAGE_LOG = tmp_path / "usage.jsonl"
    quota.LOG = tmp_path / "quota.jsonl"

    assert quota.pace() is None
    assert quota.recommended_floor_minutes() is None


def test_5時間枠の点は目盛りに使わない(tmp_path):
    """**混ぜると桁が狂う。** 週枠の話をしているので `seven_day` だけ拾う。"""
    _write(tmp_path, 10, 33, window="five_hour")
    assert quota.pace() is None


def test_誕生が0件でも落ちない(tmp_path):
    """`quota.jsonl` が空でも、速さ（%/時）までは言えること。

    **間隔は言えない**ので None のまま —— 分からないのに数字を出さない。
    """
    _write(tmp_path, 10, 0)
    p = quota.pace()
    assert p is not None
    assert p["births"] == 0
    assert p["per_lap"] is None and p["floor_min"] is None
    assert quota.recommended_floor_minutes() is None


@pytest.mark.parametrize("used,births,expect", [
    (100, 1, quota.FLOOR_MAX_CLAMP),   # 1周100% → 天井で止める
    (0.01, 500, quota.FLOOR_MIN_CLAMP),  # ほぼ0 → 床で止める
])
def test_歯止めが効く(tmp_path, used, births, expect):
    """**計器が暴れても、間隔が0分にも1日にもならないこと。**

    上が無いと1周で鎖が死に、下が無いと歯止めそのものが消える。
    """
    _write(tmp_path, used, births)
    assert quota.recommended_floor_minutes(_now(ANCHOR_AT)) == pytest.approx(expect)



# --------------------------------------------------------------------------
# **`now` を渡さない検査は、実時刻が RESET を追い越した日に化けます**
# （2026-08-22 07:2x に踏んだ）
#
# この束の RESET は **08/22 07:00 JST**。そこを過ぎた回で `quota.pace()` を
# 引数なしで呼ぶと、`pace()` は**枠を次へ送り**（それが正しい振る舞いです。
# `tests/test_pace_window_rollover.py`）、`used_now` は 0% 近くに戻ります。
# その日、`test_枠を使い切っていたら天井まで空ける` が落ちました ——
# **直すべきは `pace()` ではなく、時刻を固定していないこの側**です。
#
# 落ちたのは1件ですが、**同じ形は4件ありました。** 残り3件は
# `forward_rate` が偶然 0.596 ≈ 0.595 の境目に着地して**通っていただけ**です
# （`docs/JOURNAL.md` 08/22 01:2x「実測で動く値に、検査が乗っていた」の5件目）。
# **`forward_rate` / `floor_min` / `over` / `dead_hours` / `used_now` を見る検査は、
# 必ず `_now(...)` で枠の中の時刻を渡すこと。**
# `rate` / `seg` / `per_lap` は目盛りだけから出るので、渡さなくても動きません。
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# 門が実際に閉まるか（ここが本体。上の算術が正しくても、門が読まなければ無意味）
# --------------------------------------------------------------------------

def _sessions_file(tmp_path, born_minutes_ago):
    now = datetime.now(UTC)
    blob = {"ccr": {"data": [
        {"id": "session_ME",
         "created_at": (now - timedelta(minutes=born_minutes_ago)).isoformat(),
         "updated_at": now.isoformat(), "session_status": "RUNNING",
         "tags": ["youtube-hourly"], "parent_session_id": "session_SPAWNER",
         "external_metadata": {"rate_limit_info": {
             "rateLimitType": "seven_day",
             "resetsAt": int((now + timedelta(days=6)).timestamp()),
             "status": "allowed"}}},
        {"id": "session_SPAWNER",
         "created_at": (now - timedelta(minutes=born_minutes_ago + 20)).isoformat(),
         "updated_at": now.isoformat(), "session_status": "ARCHIVED",
         "tags": ["youtube-hourly"],
         "external_metadata": {"rate_limit_info": {
             "rateLimitType": "five_hour",
             "resetsAt": int((now + timedelta(hours=2)).timestamp()),
             "status": "allowed"}}},
    ]}}
    path = tmp_path / f"sessions_{born_minutes_ago}.json"
    path.write_text(json.dumps(blob), encoding="utf-8")
    return path


def _spawn_check(path, cron_minute: int | None = None):
    cmd = [sys.executable, str(ROOT / "scripts" / "sibling_check.py"),
           "--sessions", str(path), "--me", "session_ME", "--phase", "spawn"]
    if cron_minute is not None:
        cmd += ["--cron-minute", str(cron_minute)]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)


def _cron_minute_in(minutes: int) -> int:
    """**いまから `minutes` 分後に親が撃つ**ような cron の分を返す（1時間未満）。"""
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).minute


def test_早すぎる子は待たされる(tmp_path):
    """**兄弟0件・枠 allowed でも、早ければ立てさせないこと。**

    `allowed` は「まだ閉じていない」としか言っていない。
    ここを素通りさせると、閉じるまで気づけない。

    **親の発火を明示的に遠くへ置いています**（2026-08-19 23:1x）。
    下限が明けるのが親の発火より後なら、いまの道具は「待つ」ではなく
    **「待たずに畳む」（6）**を返すからです（`test_早すぎても親が先に来るなら畳む`）。
    ここが見ているのは**待つ側の枝**なので、親を遠ざけて分岐を固定します。
    """
    # **「60分」と書かないこと**（2026-08-22 07:2x に直した）。
    # 子は本物の `data/usage.jsonl` を読むので、**下限は実測で動きます** ——
    # 書いた日は 36分、08/22 は **50分**。固定の 60 は、下限がそこを越えた日にだけ
    # 「早すぎる子」でなくなり、**この枝ごと測られなくなります**（実際そうなりました）。
    # 見たいのは分数ではなく**枝**なので、いまの下限から作ること。
    floor = quota.recommended_floor_minutes()
    if floor is None:
        pytest.skip("目盛りが無い ＝ 下限そのものが無い（`pace()` は None を返す）")
    born = max(1, int(floor) - 15)                  # **下限の内側**＝必ず早すぎる
    r = _spawn_check(_sessions_file(tmp_path, born), cron_minute=_cron_minute_in(50))
    assert r.returncode == 5, r.stdout
    assert "まだ立てないこと" in r.stdout
    assert "sleep " in r.stdout          # 待ち方まで出すこと（人が計算しない）


def test_早すぎても親が先に来るなら畳む(tmp_path):
    """**待ちが親の発火をまたぐなら、その待ちは成立していない。**

    8/19 に2周続けて、この待ちの最中に IDLE になって親に畳まれました
    （`awaiting sleep timer (~35 min); next: spawn child & archive`）。
    待って切れると1時間まるごと失い、待たずに畳めば親が60分周期で立てます。
    """
    # **「8分」と書かないこと**（2026-08-30 に直した。すぐ上の
    # `test_早すぎる子は待たされる` が 08/22 に学んだのと同じ話です）。
    # 子は本物の `data/usage.jsonl` を読むので**下限は実測で動き**、
    # 固定の年齢は下限が動いた日に別の枝へ落ちます。
    # 実際に落ちました —— 08/30 にオーナーの画面を積んで下限が 90 → 275分 になり、
    # `recommended_floor_minutes()` が `None` を返す状態も重なって、
    # **この2件だけが赤のまま残りました。** 見たいのは分数ではなく**枝**です。
    floor = quota.effective_floor_minutes()
    if floor is None:
        pytest.skip("目盛りが無い ＝ 下限そのものが無い（`pace()` は None を返す）")
    r = _spawn_check(_sessions_file(tmp_path, max(1, int(floor) // 2)),
                     cron_minute=_cron_minute_in(3))
    assert r.returncode == 6, r.stdout
    assert "待たずに畳むこと" in r.stdout
    assert "sleep " not in r.stdout      # **両方やろうとさせない**


def test_十分あいた子はそのまま立てられる(tmp_path):
    """**1周が長かった回を、さらに待たせないこと。**

    待ちは「間隔の下限」であって上乗せではない。
    """
    # **「90分」と書かないこと**（2026-08-30 に直した。理由は1つ上と同じ ——
    # 下限が 275分 になった日に、90分の子は「十分あいた子」ではなくなりました）。
    floor = quota.effective_floor_minutes()
    if floor is None:
        pytest.skip("目盛りが無い ＝ 下限そのものが無い（`pace()` は None を返す）")
    r = _spawn_check(_sessions_file(tmp_path, int(floor) + 30))
    assert r.returncode == 0, r.stdout
    assert "待ち不要" in r.stdout
    assert "立ててよい" in r.stdout


# --------------------------------------------------------------------------
# 目盛りが古いとき（2026-08-21 に直した。**間違いは必ず「速すぎてよい」側に出る**）
# --------------------------------------------------------------------------


def test_目盛りが古いぶんを運んでから割る(tmp_path):
    """**残りは目盛りの時刻からではなく、いまから数えること。**

    実測 08/21 13:0x —— 目盛りは 08:07 の 92%。古い式は「8% ÷ 23時間 = 0.350 %/時」
    と言い、持続できる間隔を **69分** と出していました。5時間ぶん進めて数え直すと
    **6.3% ÷ 19.4時間 = 0.325 %/時 → 75分**。**9% 速く走らせていた。**
    """
    _write(tmp_path, 10, 33)
    at = _now(ANCHOR_AT)
    now = at + timedelta(hours=10)

    fresh = quota.pace(at)
    stale = quota.pace(now)

    # 運んだぶんだけ「使った%」が増え、「残り時間」は減る
    assert fresh["used_now"] == pytest.approx(10.0, abs=0.01)
    assert stale["used_now"] == pytest.approx(10 + 10 * fresh["rate"], abs=0.05)
    assert stale["left_hours"] == pytest.approx(fresh["left_hours"] - 10, abs=0.05)

    # **どちらの向きにも外れない**: 許される速さは必ず厳しくなる
    assert stale["forward_rate"] < fresh["forward_rate"]
    assert stale["floor_min"] > fresh["floor_min"]


def test_運ぶ速さは区間があれば区間のほう(tmp_path):
    """通算は鎖が止まっていた時間までならしている。**運ぶのは直近の速さで。**"""
    _two_point(tmp_path)
    at = _now(SECOND_AT)
    p = quota.pace(at + timedelta(hours=5))
    assert p["carry_rate"] == pytest.approx(p["seg"]["rate"], abs=1e-9)
    assert p["carry_rate"] != pytest.approx(p["rate"], abs=1e-9)


def test_運ぶ速さは区間が無ければ通算(tmp_path):
    _write(tmp_path, 10, 33)
    p = quota.pace(_now(ANCHOR_AT) + timedelta(hours=5))
    assert p["seg"] is None
    assert p["carry_rate"] == pytest.approx(p["rate"], abs=1e-9)


def test_運びきって満杯に届いていたら天井まで空ける(tmp_path):
    """**尽きているのに「まだ行ける」と言わないこと。** 閉じた枠に鎖を突っ込む形。"""
    _write(tmp_path, 90, 33)
    p = quota.pace(_now(ANCHOR_AT) + timedelta(hours=100))
    assert p["used_now"] == pytest.approx(100.0)
    assert p["forward_rate"] == 0.0
    assert p["floor_min"] == quota.FLOOR_MAX_CLAMP


def test_尽きる時刻もいまから数える(tmp_path):
    """`exhaust_at` を枠の頭から引くと、**運んだぶんが二重に効きます。**"""
    _write(tmp_path, 10, 33)
    at = _now(ANCHOR_AT)
    p = quota.pace(at + timedelta(hours=10))
    want = at + timedelta(hours=10) + timedelta(
        hours=(100 - p["used_now"]) / p["carry_rate"])
    assert abs((p["exhaust_at"] - want).total_seconds()) < 60


def test_尽きる時刻は直近の速さのままだと断る(tmp_path, capsys):
    """**間隔を変えた直後、この行はまだ前の速さを見ています。**

    `exhaust_at` は「このままなら」＝ 直近の区間の速さのまま、という条件つきです。
    間隔を緩めた回がここだけを読むと「効いていない」と誤読して、
    **同じ回でもう一度緩める**ことになります（緩めすぎは回を捨てる側の損失）。
    """
    _write(tmp_path, 10, 33)
    quota.pace_report(_now(ANCHOR_AT))
    out = capsys.readouterr().out
    assert "鎖が止まります" in out
    assert "直近の速さ" in out
    assert "まだ前の速さを見ています" in out
