"""**規則の密度（1日1本）で、公開時刻ごとの1本あたり再生を測る。**（**API 0単位**）

## なぜ要るか（2026-09-01・最適化の回）

`scripts/eta.py` は毎周こう印字します —— **引ける腕は `per_video` だけ**。
そして `docs/trigger_main.md` §4 の `improve` の定義は、**5つの道が全部
「中身の側」**（台本・図/サムネ・題名/説明・計算・落とす）でした。
ところが同じ画面が **配信の側は中身の側の 10.3倍 当たる**と印字しています
（`src/arm_speed.sides()`・27% 対 8%）。**10.3倍のほうが、選択肢に無かった。**

規則1 が公開を **1日1本** に固定した以上、配信の側で残っている変数は
**形式・公開時刻・面**の3つです。**そのうち公開時刻は、機械が既定値を1つ
持っているだけで、一度も測られていませんでした。**

    config/channel.yaml  publish_hour_jst: 19    ← 既定。**規則の密度での観測 0本**

## 実測（この回に数えた・`data/views.jsonl` 22,667点・齢48時間 以上のショート）

**その日に 1〜2本 しか出していない日**（＝ 規則の密度の帯。`rule_per_video`
と同じ `RULE_BAND_MULT`）だけを採ると、**17本 / 14日** しか在りません:

    公開時刻(JST)   本数   生涯再生の中央値
        8時          1        1,510
        9時         12          940     ← `rule_per_video` の 942 は、ほぼこの帯です
       18時          2          444
       21時          2          873

    **残る 20時刻 は、規則の密度で一度も試していません**（0本）。

**混ぜた全体（全密度・160本）で時刻ごとに並べると 15〜22時 が壊滅に見えます**
（中央値 1〜8回）。**それは時刻の効果ではありません** —— その帯の本は
全部「その日 13〜21本 出した日」の後ろのほうの本で、`src/day_cap.py` が
`view_cap`（1日に再生が付く本数）で説明ずみの落ち方です。
**規則の密度に絞ると、18時 444回・21時 873回 で、死んでいません。**

## この道具が言えること・言えないこと

- **言える**: 「規則と同じ密度で測った本が在る時刻」は 4つだけで、
  そのうち **n が二桁なのは 9時 だけ**。既定の 19時 は **0本**。
- **言えない**: どの時刻が一番よいか。n=1〜2 の帯で順位を付けないこと。
  **`best_hour()` は `MIN_N` 本 に満たない帯を候補にしません。**
- **交絡**: 9時 の 12本 は 08/26〜08/31 に固まっており、時期と共線です。
  **「9時 だから 940回」ではなく「940回 を出した本は 9時 に出ていた」**。

## なぜ、それでも既定を動かす価値があるか

`scripts/eta.py` の到達日は **`per_video` × 1本/日** の上に立っており、
その `per_video`（942回）は**ほぼ 9時 の 12本で出来ています**
（`src/rule_per_video.estimate()` の `at_rule`）。
**機械の既定は 19時 で、模型の数は 9時 の本から来ています** ——
この repo でいちばん多い壊れ方（「**言っている所と、している所が別**」）です。

**これは「9時 が最適だ」という主張ではありません。**
**模型が乗っている帯と、機械が実際に置く帯を、揃えるだけです。**

## 覆る条件

- **規則の密度の日が 10日 たまったら、時刻ごとに数え直すこと。**
  そのとき 19時 や 22時 に本が入っていれば、この関数は自動でそちらも並べます
  （定数を持たず、毎回 `data/views.jsonl` から数え直します）。
- **`best_hour()` が n=`MIN_N` 未満で選び始めたら、この道具は黙るべきです。**
  順位を付けられるだけの本が無い、という意味だからです。
- **オーナーが 1日1本 を外したら**、`house_rule.PUBLISH_PER_DAY` が動き、
  採る帯もそれに合わせて動きます。**ここに数は書いていません。**
- **`src/day_cap.py` の「生きる窓 08:59〜13:30」が、規則の密度でも成り立つと
  出たら**（＝ 18時/21時 の本が薄い密度でも死ぬと分かったら）、
  候補は窓の中だけに絞ること。**いまの実測はそう言っていません**（444/873回）。
"""
from __future__ import annotations

import collections
import json
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIEWS = ROOT / "data" / "views.jsonl"
FORMS = ROOT / "data" / "video_forms.json"
CHANNEL = ROOT / "config" / "channel.yaml"
JST = timezone(timedelta(hours=9))

#: **順位を付けてよい最低の本数。** これに満たない帯は `best_hour()` の候補外。
#: 実測 2026-09-01 では、これを満たすのは **9時（12本）だけ**です。
MIN_N = 5

#: 齢の門（時間）。`src/settle.mature_hours("ショート")` が読めればそちらを使う。
RIPE_HOURS = 48


def _forms() -> dict:
    try:
        raw = json.loads(FORMS.read_text(encoding="utf-8"))
    except Exception:                                          # noqa: BLE001
        return {}
    f = raw.get("forms")
    return f if isinstance(f, dict) else {}


def settled(form: str = "ショート", views_path: Path | None = None) -> list[tuple]:
    """**伸びきった本**を `(公開日時JST, id, 生涯再生)` で返す。API 0単位。

    生涯 ＝ **観測した最大**（`src/rule_per_video._settled` と同じ数え方。
    `ripe` 時点の値を採ると、控えの粗い本で 0 と数えます）。
    """
    fm = _forms()
    try:
        from . import settle as _settle                        # noqa: PLC0415
        ripe = _settle.mature_hours(form)
    except Exception:                                          # noqa: BLE001
        ripe = RIPE_HOURS
    series: dict[str, list[tuple[float, int, str]]] = collections.defaultdict(list)
    try:
        text = (views_path or VIEWS).read_text(encoding="utf-8")
    except OSError:
        return []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except Exception:                                      # noqa: BLE001
            continue
        vid = r.get("id")
        if fm and fm.get(vid) != form:
            continue
        h, v, at = r.get("hours"), r.get("views"), r.get("at")
        if h is None or v is None or not at:
            continue
        series[vid].append((float(h), int(v), at))
    out = []
    for vid, s in series.items():
        s.sort()
        if s[-1][0] < ripe:
            continue
        try:
            pub = (datetime.fromisoformat(s[0][2].replace("Z", "+00:00"))
                   - timedelta(hours=s[0][0])).astimezone(JST)
        except Exception:                                      # noqa: BLE001
            continue
        out.append((pub, vid, max(v for _, v, _ in s)))
    return out


def rule_band(rows: list[tuple] | None = None, per_day: int | None = None,
              mult: int | None = None) -> list[tuple]:
    """**規則と同じ密度の日**の本だけを残す（`rule_per_video` と同じ帯の採り方）。"""
    rows = settled() if rows is None else rows
    if per_day is None:
        try:
            from . import house_rule                           # noqa: PLC0415
            per_day = int(house_rule.PUBLISH_PER_DAY)
        except Exception:                                      # noqa: BLE001
            per_day = 1
    if mult is None:
        try:
            from . import rule_per_video                       # noqa: PLC0415
            mult = int(rule_per_video.RULE_BAND_MULT)
        except Exception:                                      # noqa: BLE001
            mult = 2
    per = collections.Counter(p.date() for p, _, _ in rows)
    lim = max(1, per_day * mult)
    return [r for r in rows if per[r[0].date()] <= lim]


def by_hour(rows: list[tuple] | None = None) -> dict[int, dict]:
    """**公開時刻（JST の時）ごとの生涯再生。** 規則の密度の帯だけ。"""
    band = rule_band(rows)
    acc: dict[int, list[int]] = collections.defaultdict(list)
    for p, _, life in band:
        acc[p.hour].append(life)
    return {h: {"n": len(v), "median": statistics.median(v),
                "mean": statistics.mean(v), "max": max(v)}
            for h, v in sorted(acc.items())}


def untested(rows: list[tuple] | None = None) -> list[int]:
    """**規則の密度で一度も試していない時刻**（0〜23 の JST の時）。"""
    seen = set(by_hour(rows))
    return [h for h in range(24) if h not in seen]


def best_hour(rows: list[tuple] | None = None) -> int | None:
    """**順位を付けてよい帯の中で、いちばん中央値が高い時刻。**

    `MIN_N` 本 に満たない帯は候補にしません。**候補が無ければ `None`** ——
    そのときは既定を動かす根拠がない、という意味です（黙ること）。
    """
    tab = by_hour(rows)
    ok = [(v["median"], v["n"], h) for h, v in tab.items() if v["n"] >= MIN_N]
    if not ok:
        return None
    return max(ok)[2]


# --- **掃く**（2026-09-01 に足した） -----------------------------------------
#
# 上の `best_hour()` は「**いま根拠のある時刻**」を返します。それだけを使うと、
# **20時刻 は永久に 0本 のまま**です —— 既定を 9時 に揃えた瞬間、機械は
# 二度と別の時刻に置かなくなり、**この道具は自分で自分の標本を殺します。**
#
# 規則1 は 1日1本なので、**1日に増える点は1つ**です。だから掃き方は
# 「たまに別の時刻」ではなく **対照と交互**にします ——
#
#     偶数日  `best_hour()`（対照。いま 9時）
#     奇数日  未試行の時刻を1つ（掃く側。日付で順に回す）
#
# **なぜ交互か。** 1本あたり再生は 8月後半に大きく動いており（`rule_per_video`
# の「時期と共線」）、**まとめて片方に寄せると時期の効果と混ざります。**
# 日ごとに入れ替えれば、対照と処置が同じ期間に散ります。
#
# **候補を 6〜23時 に絞る理由**: 0〜5時 JST は視聴者が寝ている帯で、
# **この repo は一度も置いたことがありません**（全密度 160本 でも 0本）。
# 掃く価値はありますが、**先に 6〜23 を埋めてからです** —— 1日1点しか
# 増えないので、**当たりそうな順に使うこと**。
#
# **覆る条件**: 未試行の時刻が無くなったら `sweep_hour()` は常に `best_hour()`
# を返します（掃き終わり）。**前提が閉じたら、この交互をやめること** ——
# 効かないと出たなら 9時 に固定、効くと出たならその時刻へ既定を移すだけです。

#: 掃く候補にしてよい時刻の帯（JST）。**0〜5時 は後回し**（上の註）。
SWEEP_LO, SWEEP_HI = 6, 23


def sweep_candidates(rows: list[tuple] | None = None) -> list[int]:
    """**掃く先**（未試行のうち `SWEEP_LO`〜`SWEEP_HI`）。無ければ空。"""
    return [h for h in untested(rows) if SWEEP_LO <= h <= SWEEP_HI]


def sweep_hour(target_date=None, rows: list[tuple] | None = None) -> int | None:
    """**その日に置くべき時刻。** 対照（`best_hour`）と未試行を**交互**に。

    `best_hour()` が `None`（根拠なし）なら **`None`** を返します ——
    対照が立っていない段階で掃いても、比べる先がありません。
    """
    base = best_hour(rows)
    if base is None:
        return None
    if target_date is None:
        target_date = datetime.now(JST).date()
    cand = sweep_candidates(rows)
    if not cand or target_date.toordinal() % 2 == 0:
        return base
    return cand[(target_date.toordinal() // 2) % len(cand)]


def config_hour(path: Path | None = None) -> int | None:
    """`config/channel.yaml` の `publish_hour_jst`（機械が実際に置く時刻）。"""
    try:
        import yaml                                            # noqa: PLC0415
        doc = yaml.safe_load((path or CHANNEL).read_text(encoding="utf-8")) or {}
        return int((doc.get("publish") or {}).get("publish_hour_jst"))
    except Exception:                                          # noqa: BLE001
        return None


def place_hour(day=None, *, sweep=None, config=None) -> int:
    """**その日に置く時刻（JST の時）—— 正本はここ1つ。** 掃く側（`sweep_hour(その日)`）が先、
    根拠が無ければ `config/channel.yaml` の既定、それも無ければ 9。**API 0単位。**

    ## なぜ1つに寄せたか（2026-09-03 02:5x に踏んだ）

    同じ `run_marker.py --write` の画面が、同じ本 `6PKux5HNnUE` の同じ手（09/04 の枠へ
    `--move`）を **2つの時刻**で刷っていました:

        [下書き]     python scripts/reschedule.py --move 6PKux5HNnUE 2026-09-04T09:00
        [きょうの1本] python scripts/reschedule.py --move 6PKux5HNnUE 2026-09-04T17:00

    9時 は `next_slot._move_lines` が `config_hour()` を読んだ数、17時 は
    `daily_pick._hour_default` と `ahead_sweep.place_hour`（機械が実際に置く側）が
    `sweep_hour()` を読んだ数です。**同じ判断が3か所に書かれていて、1か所だけ古い**
    —— 「言っている所と、している所が別」（この module の冒頭）の、もう1つの形。
    09/03 00:4x に `place_today` を直した回は、置く側と `daily_pick` を揃えましたが、
    `next_slot` は `config_hour()` を直に読んだままでした。**3か所に同じ順を書く限り、
    次に順を変えた回がまた1つ書き忘れます。** だから順はここに1回だけ書き、
    3か所はこれを呼びます。

    `sweep`／`config` は検査のための差し替え口（省略時はこの module の実物）。

    ## 覆る条件

    - 前提「公開時刻は per_video に効かない」（`config/hypotheses.yaml`）が閉じたら、
      `sweep_hour()` 自身が対照だけを返すようになります。ここは変えなくてよい
    - `sweep_hour()` が `None`（対照が `MIN_N` に届かない）のあいだは、既定に倒れます
    """
    if day is None:
        day = datetime.now(JST).date()
    h = None
    try:
        fn = sweep or sweep_hour
        h = fn(day)
    except Exception:                                          # noqa: BLE001
        h = None
    if h is None:
        try:
            fn = config or config_hour
            h = fn()
        except Exception:                                      # noqa: BLE001
            h = None
    return 9 if h is None else int(h)


def lines(rows: list[tuple] | None = None) -> list[str]:
    """画面に出す形。**帯が1つも無ければ、1行も出しません。**"""
    tab = by_hour(rows)
    if not tab:
        return []
    band_n = sum(v["n"] for v in tab.values())
    out = [f"=== **公開時刻べつの1本あたり再生**（規則の密度の日だけ・"
           f"{band_n}本 / {len(tab)}時刻・`src/publish_hour.py`）===",
           "  **全密度で並べた表は使わないこと** —— 15〜22時 が壊滅に見えるのは"
           "`src/day_cap.py` の本数の効果で、時刻の効果ではありません。"]
    for h, v in tab.items():
        mark = "  ←**順位を付けてよい**" if v["n"] >= MIN_N else "（n が足りない）"
        out.append(f"    {h:>2}時  n={v['n']:>2}  中央値 {v['median']:>7,.0f}"
                   f"  平均 {v['mean']:>8,.0f}  最大 {v['max']:>6,}{mark}")
    un = untested()
    out.append(f"  **規則の密度で一度も試していない時刻: {len(un)}／24**"
               f"（{' '.join(str(h) for h in un)}）")
    cfg, best = config_hour(), best_hour()
    if cfg is not None:
        got = tab.get(cfg)
        if got is None:
            out.append(f"  [!] **機械の既定は {cfg}時**（`config/channel.yaml`"
                       "の `publish_hour_jst`）で、**規則の密度での観測は 0本**です。")
        else:
            out.append(f"  機械の既定は {cfg}時（n={got['n']}・中央値 "
                       f"{got['median']:,.0f}）。")
    if best is not None and best != cfg:
        b = tab[best]
        out.append(f"  → **既定を {best}時 へ揃えること**（n={b['n']}・中央値 "
                   f"{b['median']:,.0f}）。`scripts/eta.py` の `per_video` は"
                   "**ほぼこの帯で出来ています**（`src/rule_per_video` の `at_rule`）——"
                   "**模型が乗っている帯と、機械が置く帯を揃えるだけ**です。"
                   "「この時刻が最適だ」ではありません。")
    elif best is None:
        out.append("  → **既定を動かす根拠はまだありません**"
                   f"（どの時刻も {MIN_N}本 に届いていない）。")
    return out


def main(argv: list[str] | None = None) -> int:
    got = lines()
    print("\n".join(got) if got else
          "規則の密度で伸びきった本がまだありません（`data/views.jsonl`）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
