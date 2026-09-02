#!/usr/bin/env python3
"""**今日から数日のうちに「予約が0本の日」が在るなら、その回を引き止める。**（**API 0単位**）

    python scripts/slot_gate.py          # いま何日 空いているか（人が読む）
    python scripts/slot_gate.py --gate   # 空いていたら exit 2 ＋ 理由を印字（フック用）

読むのは `data/uploaded.jsonl`（`src.dupes.ledger_rows()`）だけです。
**`scripts/status.py` と同じ関数から数えます** —— 同じ与件で2つの道具が
別のことを言うのが、この repo でいちばん多い壊れ方だからです。

## なぜ要るか（2026-09-01・最適化の回。**実測でここが律速でした**）

オーナー規則1は「公開は1日1本」（`src/house_rule.py`）。
規則が入ってから、**主実行が `upload` を出した回は 2日で1件**でした
（`status._upload_pace()`・要るのは 2件）。そして控えには

    2026-09-03 〜 2026-09-11 の **9日 が0本**（その先 09/12 以降に 267本）

が並んでいます。**この9日は投稿が途切れます**（`CLAUDE.md`「途切れるのが最大の損失」）。

### なぜ主実行はそれを選ばなかったのか（**印字の問題ではありません**）

`docs/trigger_main.md` §4「何を選ぶか」の1番目は、こう書いてありました:

    1. **予約が5日先を切っている → `upload`**

この判定が見ているのは **`ahead[-1]`（予約のいちばん後ろ）** です。
いま控えのいちばん後ろは **10/10（39日 先）**。だから条件は**偽**で、
**9日 が真っ暗でも、この規則は `upload` を選ばせません。**

**「どこまで届いているか」と「明日は埋まっているか」は別の問いです。**
作り置き 267本 が先のほうに固まっていると、前者だけが満たされます ——
規則2（作り置きなし）が入った日から、**この判定は構造的に外れています。**

### なぜ印字ではなく門か

`scripts/status.py` は 2026-09-01 06:1x に、この穴と「埋める道は
その日の回が `upload` を1本 出すことだけ」まで**正しく印字していました。**
それでも `upload` は増えていません。**700行の本文の 340行目**に在るからです
（`scripts/stop_check.sh` の 271行目に同じ教訓:
「**印字に格上げしただけでは、同じ穴です —— 出ていても、読まずに終われる**」）。

この repo は既に7つの門を持っています（何も出していない／予測へ入れ直す／
満ちた待ち／期限のずれ／次の回を立てる…）。**そのどれもが帳面の話で、
`CLAUDE.md` が「最大の損失」と呼んでいるものだけが門になっていませんでした。**

## 先読みの日数（`LEAD_DAYS`）を、なぜ 2日 にするか

- `scripts/queue_lag.py` の実測「**いま作った本が予約されるのは 1〜1日後**」
- Data API の日枠が戻るのは **JST 16:00**（尽きた回は次の窓まで撃てない）

**1日 では、日枠が尽きた回に取り返す余地がありません。** 2日 あれば、
枠が戻る窓を1回またげます。逆に長くすると、**穴の先の作り置きを
「詰めろ」と言い出すのと同じ形**になり、規則2 とぶつかります
（この門は *詰めろ* とは一度も言いません。言うのは **1本 作って入れろ** だけです）。

## 規則2 とぶつからないこと

この門が要求するのは **1回に1本**で、埋めるのは **`LEAD_DAYS` 先の1日**だけです。
9日 ぶんをいま作らせません（それが作り置きです）。
**毎日 1本ずつ、2日 先の枠を埋め続ける**のが、この門の定常状態です。

## 覆る条件

- **オーナーが規則1を外したら**、分母（1日1本）の意味が変わります。
  そのときは「0本の日」ではなく「上限に足りない日」を数えること。
- `data/uploaded.jsonl` は**上限側の見積り**です（取り消した本も残る）。
  つまりこの門は**空を見落とす側**に外れます —— 鳴ったら本物です。
  逆に「鳴っていないから埋まっている」は言えません。
- 予約を**手で** YouTube Studio から動かすと控えと食い違います。
  そのときは `scripts/reschedule.py --list` が正。
- **3回で通します**（`scripts/stop_check.sh` 側）。日枠が尽きていて
  本当に撃てない回を、永久に止めないため。
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

JST = timezone(timedelta(hours=9))

def _same_day_only() -> bool:
    """**規則5（固定その4）が効いているか。** 読めない回は「効いていない」側へ。"""
    try:
        from src import house_rule                             # noqa: PLC0415
        return bool(house_rule.same_day_only())
    except Exception:                                          # noqa: BLE001
        return False


#: **何日 先まで見るか。** 0 ＝ 今日だけ。2 ＝ 今日・明日・明後日。
#:
#: **2026-09-02 に、規則5（固定その4）で 0 になりました。** オーナー原文:
#: 「**現在の日付にしか予約しないってことだからね？**」
#: ＝ **先の日付が空であることが正しい状態**なので、明日・明後日が 0本 でも
#: 鳴らしてはいけません（鳴らすと、この門は**毎周 必ず**鳴ります ——
#: そして `scripts/stop_check.sh` がその回を止めます）。
#:
#: 見るのは**今日 1日だけ**です。今日の1本が予約にも実績にも無ければ、
#: それは本物の途切れ（`CLAUDE.md`「途切れるのが最大の損失」）。
#:
#: **上の「2日 にする理由」の節は、規則5 が外れたときのために残してあります。**
LEAD_DAYS = 0 if _same_day_only() else 2


def per_day(rows: list[dict] | None = None, now: datetime | None = None) -> dict | None:
    """**JST の暦日ごとの予約本数。** `{date: 本数}`（予約のある日だけ）。

    `scripts/status.py::per_day_counts()` と**同じ数え方**にしてあります
    （`now` より後の `at` だけ・JST へ直してから日で数える）。

    ## `now` は 2026-09-02 に足しました（**日付をまたいだ瞬間に赤くなっていた**）

    ここは `datetime.now()` を直に読み、**`empty_days(rows, today)` のほうは
    渡された `today` を使っていました。** 2つの時計が別だったということです。

    実測 —— `tests/test_slot_gate.py` は `today = date(2026, 9, 1)` を渡して
    「その日から毎日1本ずつ埋まっている控え」を作りますが、
    **その 09/01 22:00 の1本は、本物の時計では既に過ぎています**（いまは 09/02）。
    だから `per_day` は 09/01 を数えず、`empty_days` は「09/01 が空」と答えます。
    検査は 09/01 に書かれ、**09/02 00:00 JST に、誰も何も触っていないのに赤へ**。

    **引数で `today` を受けるのに、中で `now()` を読む関数は純ではありません。**
    `today` が明示された回は、その日の JST 0時 を床にします
    （＝ **きょう既に公開ずみの本も、きょうを埋めているものとして数える** ——
    「投稿が途切れるか」を聞いているので、そちらが正しい向きです）。

    **覆る条件**: 「まだ出ていない本だけ数えたい」呼び手が出てきたら、
    `now` を明示して渡すこと（この引数はそのために在ります）。
    """
    if rows is None:
        # **控えそのものが読めない回は、鳴らしません。**
        # 「測っていないことを、落とす側に倒さないこと」（`src/house_rule.is_stockpile`
        # の註と同じ判断）。**行が在って未来が0本**なら、それは本物の空です。
        if not (ROOT / "data" / "uploaded.jsonl").exists():
            return None
        try:
            from src import dupes                               # noqa: PLC0415
            rows = [r for r in dupes.ledger_rows() if r.get("at")]
        except Exception:                                       # noqa: BLE001
            return None
        if not rows:
            return None
    now = now or datetime.now(timezone.utc)
    out: dict = {}
    for r in rows:
        at = str(r.get("at") or "")
        if not at:
            continue
        try:
            t = datetime.fromisoformat(at.replace("Z", "+00:00"))
        except ValueError:
            continue
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        if t <= now:
            continue
        d = t.astimezone(JST).date()
        out[d] = out.get(d, 0) + 1
    return out


def _floor(today) -> datetime | None:
    """`today` が明示された回の床（その日の JST 0時）。**純にするため**。

    渡されていなければ `None` ＝ 本物の時計（`per_day` の註）。
    """
    if today is None:
        return None
    return datetime(today.year, today.month, today.day, tzinfo=JST)


def empty_days(rows: list[dict] | None = None, today=None, lead: int | None = None) -> list:
    """**今日から `lead` 日ぶんのうち、予約が0本の暦日**（早い順）。

    **0本の日は `per_day` の鍵に入っていません。** だから暦を歩いて数えます
    （鍵を一覧の元にしたのが `status.py` 側の元の欠陥でした）。

    **`today` を渡した回は、その日の JST 0時 を床にします**（`per_day` の `now` の註）。
    """
    per = per_day(rows, now=_floor(today))
    if per is None:
        return []
    today = today or datetime.now(JST).date()
    n = LEAD_DAYS if lead is None else lead
    return [today + timedelta(days=i) for i in range(n + 1)
            if per.get(today + timedelta(days=i), 0) == 0]


def tail_days(rows: list[dict] | None = None, today=None) -> int:
    """**穴の先に、まだ何日ぶん 予約が並んでいるか**（＝作り置きの厚み）。

    これが 0 なら「まだ作っていない」、正なら「**作ってあるのに出さない**」です。
    門の文面がその2つで変わるので、ここで数えます。
    """
    per = per_day(rows, now=_floor(today))
    if not per:
        return 0
    today = today or datetime.now(JST).date()
    return sum(1 for d in per if d > today + timedelta(days=LEAD_DAYS))


# --- **`<時>` を空欄で渡さない**（2026-09-01・最適化の回に足した） -------------
#
# ここが出す3行のうち、真ん中の `upload_only.py s-<名前> "" <時>` の `<時>` は
# **空欄でした。** 空欄は「自分で決めろ」なので、読む側は既定
# （`config/channel.yaml` の `publish_hour_jst`）に落ちます。
#
# その既定は 2026-09-01 まで **19時** で、根拠は立ち上げ時の推測
# 「日本の視聴ピークは 19-22時」だけ ——**規則の密度（1日1本）での観測は 0本**でした。
# 一方 `scripts/eta.py` の到達日が乗っている `per_video`（942回）は、
# **ほぼ 9時 の 12本**で出来ています（`src/rule_per_video` の at_rule）。
#
# **`improve` の当てどころと同じ穴です** —— 「同じ5択に並べても、探す手間が
# 違えば選ばれません」（`src/next_slot.py` 冒頭）。ここは**時刻を空欄にしない**。
#
# 覆る条件: `publish_hour.best_hour()` が `None`（どの時刻も `MIN_N` に届かない）
# なら、この関数は**何も足しません** —— 推測で時刻を名指ししないため。


def _hour_for(day) -> int | None:
    """その日に置くべき時刻（`publish_hour.sweep_hour`）。**根拠が無ければ None。**"""
    try:
        from src import publish_hour                           # noqa: PLC0415
        return publish_hour.sweep_hour(day)
    except Exception:                                          # noqa: BLE001
        return None


def _hour_arg(day=None) -> str:
    """`upload_only.py` の第3引数（予約時刻・JST の時）。**空欄にしない。**"""
    h = _hour_for(day)
    if h is None:
        return "<時>    # 第3引数が予約時刻（JST）"
    return f"{h}     # 予約時刻（JST）＝ `python -m src.publish_hour` の実測"


def _hour_lines(day=None) -> list[str]:
    """時刻を名指しした理由。**名指しできない回は1行も出しません。**"""
    h = _hour_for(day)
    if h is None:
        return []
    try:
        from src import publish_hour                           # noqa: PLC0415
        base, cfg = publish_hour.best_hour(), publish_hour.config_hour()
        tab, un = publish_hour.by_hour(), publish_hour.untested()
    except Exception:                                          # noqa: BLE001
        return []
    if h == base and h in tab:
        v = tab[h]
        out = [f"  **時刻は {h}時（対照）**（規則の密度の日で n={v['n']}・中央値 "
               f"{v['median']:,.0f}回。`python -m src.publish_hour`・API 0単位）。"
               "**「この時刻が最適だ」ではありません** —— `eta.py` の `per_video` が"
               "乗っている帯と、機械が置く帯を揃えているだけです。"]
    else:
        out = [f"  **時刻は {h}時（掃く側）**。この時刻は規則の密度で"
               f"**一度も試していません**（対照は {base}時）。"
               "**偶数日は対照・奇数日は未試行**で交互に置きます —— "
               "まとめて寄せると時期の効果と混ざるからです"
               "（`src/publish_hour.sweep_hour`）。"]
    if cfg is not None and base is not None and cfg != base:
        out.append(f"  [!] `config/channel.yaml` の既定は {cfg}時、対照は {base}時 です"
                   "（揃えるなら、そちらも直すこと）。")
    if un:
        out.append(f"  **規則の密度で一度も試していない時刻が {len(un)}／24 あります。**"
                   "1日1本 ＝ 1日に1点しか増えません。判定は"
                   "`config/hypotheses.yaml`「公開時刻は 1本あたり再生に効かない」。")
    return out + [""]


def lines(rows: list[dict] | None = None, today=None) -> list[str]:
    """門が印字する行。**空いていなければ空リスト。**"""
    today = today or datetime.now(JST).date()
    gap = empty_days(rows, today)
    if not gap:
        return []
    per = per_day(rows) or {}
    cells = " ".join(
        f"{(today + timedelta(days=i)):%m/%d}={per.get(today + timedelta(days=i), 0)}"
        for i in range(LEAD_DAYS + 1))
    if _same_day_only():
        out = [
            f"**きょう（{gap[0]:%m/%d} JST）の1本が、予約にも実績にもありません。**"
            "（規則5・固定その4「現在の日付にしか予約しない」）",
            f"  きょう: {cells}   （規則1 ＝ **1日1本**・`src/house_rule.py`）",
            "  **きょうは投稿が途切れます。**「途切れるのが最大の損失」（`CLAUDE.md`）。",
            "  **明日から先が空なのは正常です** —— この門は今日しか見ていません",
        ]
    else:
        out = [
            f"**予約が0本の日が、今日から{LEAD_DAYS}日 のうちに {len(gap)}日 あります: "
            + " ".join(f"{d:%m/%d}" for d in gap) + "**",
            f"  今日から{LEAD_DAYS + 1}日: {cells}   （規則1 ＝ **1日1本**・`src/house_rule.py`）",
            "  **その日は投稿が途切れます。**「途切れるのが最大の損失」（`CLAUDE.md`）。",
        ]
    tail = tail_days(rows, today)
    if tail and _same_day_only():
        out.append(
            f"  **先の日付に、まだ {tail}日 ぶんの予約が並んでいます** —— "
            "**それも規則5 に反しています**（先の日付は空が正しい）。"
            "外す手は `python scripts/pool_drain.py --apply --keep 0`"
            "（**削除はしません**・private の下書きへ戻すだけ）。"
            "**手前へ倒さないこと** —— `--compact` は先の日付へ並べ直す手で、"
            "規則5 に反します。")
    elif tail:
        out.append(
            f"  **その先には、まだ {tail}日 ぶんの予約が並んでいます** ——"
            "つまりこの穴は「まだ作っていない」ではなく**「作ってあるのに出さない」**です。"
            "**それでも詰めないこと** —— `--compact` は `at` しか動かさないので、"
            "詰めた本は作り置きのままで `pool_drain` が同じ本を外します"
            "（`src/house_rule.is_stockpile`）。")
    if _same_day_only():
        out += [
            "",
            f"**この回でやること: きょう（{gap[0]:%m/%d}）の枠へ1本 入れること。**"
            "**先の日付には置かないこと**（規則5）:",
            "",
            "  (a) **前の日に作った下書きが在るなら、それを今日の枠へ**（1本 50単位）:",
            "        python scripts/reschedule.py --pool          # private の下書きを見る",
            f"        python scripts/reschedule.py --move <videoId> {today:%Y-%m-%d}"
            f"T{(_hour_for(gap[0]) or 20):02d}:00",
            "  (b) 下書きが無いなら、作ってから同じ日へ:",
            "",
            "    python -m src.pipeline --topic <名前> --dry-run",
            "    python scripts/inspect_build.py <名前>            # **投稿前に必ず目で見る**",
            f"    python scripts/upload_only.py <名前> \"\" {_hour_arg(gap[0])}",
            "",
            "**そして、出したら次の日の1本を作り始めること**（固定その4「1日の回り方」）——"
            "作るのは前の日から、**予約だけが当日**です"
            "（`python scripts/upload_only.py <名前> --draft` で予約を付けずに上げられます）。",
            "",
        ] + _hour_lines(gap[0]) + [
            "**撃てないなら**（Data API の日枠 ＝ JST 16:00 に戻る）、"
            "**その理由を `docs/JOURNAL.md` に書いてから終わること。**",
        ]
        return out
    out += [
        "",
        f"**この回でやること: {gap[0]:%m/%d} の枠に入る1本を、予約まで入れること**"
        "（`docs/trigger_main.md` §5）。**1本だけです**（9日ぶん作るのが作り置きです）:",
        "",
        "    python -m src.pipeline --script build/short.json --topic s-<名前> --short",
        f"    python scripts/upload_only.py s-<名前> \"\" {_hour_arg(gap[0])}",
        "    python scripts/inspect_build.py s-<名前>          # **投稿前に必ず目で見る**",
        "",
    ] + _hour_lines(gap[0]) + [
        "**撃てないなら**（Data API の日枠 ＝ JST 16:00 に戻る／`AUTOMATION_PAUSED.md`）、"
        "**その理由を `docs/JOURNAL.md` に書いてから終わること。**",
    ]
    return out


def main(argv: list[str]) -> int:
    gate = "--gate" in argv
    out = lines()
    if not out:
        if not gate:
            print(f"予約が0本の日は、今日から{LEAD_DAYS}日 のうちにありません。")
        return 0
    print("\n".join(out))
    return 2 if gate else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
