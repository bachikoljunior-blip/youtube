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


def quota_lines(now=None) -> list[str]:
    """**いま、どの道が開いているか。**（**API 0単位**）

    ## なぜ要るか（2026-09-05 未明・最適化の回。**この回に撃って踏んだ**）

    この門の最後の行は、長らくこうでした ——

        **撃てないなら**（Data API の日枠 ＝ JST 16:00 に戻る）、
        **その理由を `docs/JOURNAL.md` に書いてから終わること。**

    **「撃てないなら」は、回に判定を任せています。** そして回はそれを
    判定できませんでした（`next_slot.writable_from()` が、403 を見た窓で
    **None ＝「撃てる」**を返していたため。同じ回に直した）。

    **そして、日枠は道ごとに別々に閉じます** —— `videos.update`（50単位）が
    403 でも、`videos.insert`（1600単位）は通ります
    （`reschedule._update` の 403 の本文が、そう名指ししています。
      実測 8/17 05:2x にも同じ割れ方）。**安いほうが先に閉じます。**

    ＝ **枠が 0本 の日に「撃てない」と読んで終わるのは、たいてい誤りです。**
    閉じているのは差し替えの側で、**新しく上げて予約を付ける道は開いています。**

    この回の実物: 09/05 の枠を空けたあと `--move` が 403。
    **`upload_only.py`（insert）なら、その同じ窓で埋められます。**

    ## 覆る条件

    差し替えが日枠の外に出たら（`next_slot.writable_from` の覆る条件と同じ日）、
    この関数は1行も出しません。
    """
    try:
        from src import next_slot                              # noqa: PLC0415
        back = next_slot.writable_from(now)
    except Exception:                                          # noqa: BLE001
        return []
    if back is None:
        return []
    return [
        f"  [!] **`videos.update`（差し替え・50単位）は、いま 403 です** —— "
        f"戻るのは **{back.astimezone(JST):%m/%d %H:%M} JST**"
        "（`src/next_slot.writable_from`・**403 の観測で答えています**）。"
        "＝ **`reschedule.py --move` / `--unschedule` は、いま通りません。**",
        "  **それでも枠は埋められます** —— `videos.insert`（`upload_only.py`・1600単位）は"
        "**日枠が切れていても通ります**（`scripts/reschedule.py` の 403 の本文。"
        "**安いほうが先に閉じます**）。**「日枠だから何もできない」と読まないこと。**",
    ]


def same_topic_twice(rows: list[dict], today=None, picked=None,
                     days: int | None = None) -> list[dict]:
    """**同じ題材の本が、同じ日の枠に 2本 以上 入っている日**（0単位・控えだけ）。

    返り: `[{"day": date, "topic": str, "keep": id, "drop": [id, …]}, …]`。
    残すのは **その日の決めが名指す本**、決めが無ければ**いちばん早い時刻の本**。

    ## なぜ要るか（2026-09-05 09:0x に実測で踏んだ）

    09/05 は `kzefG44_APU`（09:00）と `a23e696j0f8`（10:00）が**同じ台本・同じ題**で
    両方 枠に入っていた。07:20 の置く手が `--move` を帳面の取り置きで止められ、
    同じ台本を焼き直して `videos.insert` で置いた（旧 ID を外す `videos.update` も同じ窓で
    撃てない）。**同じ字の本が 1時間 差で 2本 公開される** ＝ 再生は割れ、
    「繰り返し／量産」の判定材料をこちらから出す形（`CLAUDE.md` の根幹の節）。
    `mismatch_lines()` の「公開ずみの題材」の枝は**その日より前に公開された題材**しか
    見ないので、**同じ日の 2本 は見えていなかった。**

    **覆る条件**: `place_by_insert` が旧 ID を外せない窓では置かなくなったら、ここは空振りしかしない。
    """
    today = today or datetime.now(JST).date()
    horizon = LEAD_DAYS if days is None else max(0, int(days) - 1)
    held: dict = {}
    for r in rows:
        if not r.get("at") or not r.get("topic"):
            continue
        try:
            at = datetime.fromisoformat(str(r["at"]).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        d = at.astimezone(JST).date()
        if d < today or d > today + timedelta(days=horizon):
            continue
        held.setdefault((d, str(r["topic"])), []).append((at, str(r.get("id") or "")))
    out: list[dict] = []
    for (d, topic), items in sorted(held.items()):
        ids = [i for _, i in sorted(items) if i]
        if len(ids) < 2:
            continue
        want = str(((picked or {}).get(d) or {}).get("video_id") or "")
        keep = want if want in ids else ids[0]
        out.append({"day": d, "topic": topic, "keep": keep,
                    "drop": [i for i in ids if i != keep]})
    return out


def mismatch_lines(rows: list[dict] | None = None, today=None,
                   picked=None, published=None, days: int | None = None) -> list[str]:
    """**枠に入っている本と、その日の決めが食い違っていたら、その行**（合っていれば空）。

    ## なぜ要るか（2026-09-05 05:4x・最適化の回。**実物で踏んだ**）

    `data/daily_pick.jsonl` は**書く先で、押す先ではありません。** 09/05 のあいだに
    決めは **6回** 書き換わり（00:38 長尺 → 01:17 → 01:48 → 05:09 ショート → 05:11 →
    この回 05:37）、**チャンネルの予約は1度も変わりませんでした** ——
    09/05 09:00 は 00:38 より前から `GFvAcxvDmYM`（長尺・見込み 齢48h **1回**）のままで、
    決めのほうは ショート（同 **164回**）です。

    押されない理由は `ahead_sweep.today_plan()` の1行で::

        if count >= max(1, cap):   →  「きょうの枠は埋まっています（1本／規則 1本）」

    **どの本が入っているかを見ていません。** `place_today()` はその手前で
    `if count < house_rule.cap()` のときしか候補を読まないので、
    **食い違いは構造上 見えません。**

    この門は 0単位 で見えるようにします（読むのは控えと `data/daily_pick.jsonl` だけ）。
    もう1つ、**公開ずみの題材の本が枠に入っている**回もここで鳴らします ——
    その日の取り分は 0 になるからです（`scripts/reschedule._rule_blocks_move` の註）。

    **覆る条件**: `today_plan()` が枠の中身まで見て入れ替えるようになったら、
    この門は空振りしかしません（そのとき外してよい）。**先に外さないこと。**
    """
    today = today or datetime.now(JST).date()
    if rows is None:
        try:
            from src import dupes                              # noqa: PLC0415
            rows = dupes.ledger_rows()
        except Exception:                                      # noqa: BLE001
            return []
    if picked is None:
        try:
            from src import daily_pick as _dp                  # noqa: PLC0415
            picked = {}
            for i in range(LEAD_DAYS + 1):
                d = today + timedelta(days=i)
                cur = _dp.current(d)
                if cur and cur.get("video_id"):
                    picked[d] = cur
        except Exception:                                      # noqa: BLE001
            picked = {}
    if published is None:
        try:
            from src import daily_pick as _dp                  # noqa: PLC0415
            published = _dp.published_topics()
        except Exception:                                      # noqa: BLE001
            published = set()
    horizon = LEAD_DAYS if days is None else max(0, int(days) - 1)
    held: dict = {}
    for r in rows:
        if not r.get("at"):
            continue
        try:
            d = datetime.fromisoformat(str(r["at"]).replace("Z", "+00:00")).astimezone(JST).date()
        except (TypeError, ValueError):
            continue
        held.setdefault(d, []).append(r)
    out: list[str] = []
    for dup in same_topic_twice(rows, today=today, picked=picked, days=days):
        out += [
            f"**{dup['day']:%m/%d}（JST）の枠に、同じ題材 `{dup['topic']}` の本が "
            f"{1 + len(dup['drop'])}本 入っています**（残す `{dup['keep']}`・"
            f"外す {' '.join('`' + i + '`' for i in dup['drop'])}）",
            "  同じ字の本が同じ日に並びます ＝ 再生が割れ、「繰り返し／量産」の材料をこちらから出す形。",
            "  外すこと（公開ずみでも private に戻ります・1本 50単位）: "
            + " → ".join(f"`python scripts/reschedule.py --unschedule {i}`" for i in dup["drop"]),
            "  （日枠が閉じている窓では `ahead_sweep.dedupe_today()` が、窓が戻った掃きで同じ手を撃ちます）",
        ]
    for i in range(horizon + 1):
        d = today + timedelta(days=i)
        here = held.get(d) or []
        if not here:
            continue                                           # 空の日は `lines()` の担当
        cur = picked.get(d) or {}
        want = str(cur.get("video_id") or "")
        for r in here:
            if r.get("topic") and r["topic"] in published:
                out += [
                    f"**{d:%m/%d}（JST）の枠に、公開ずみの題材の本が入っています: "
                    f"`{r['id']}`（`{r['topic']}`）**",
                    f"  題: {r.get('title') or ''}",
                    "  規則1 は1日1本なので、**その日の取り分は 0** です"
                    "（同じ字の本が2本 並びます）。",
                    f"  外して決めの本を入れること: `python scripts/reschedule.py "
                    f"--unschedule {r['id']}`",
                ]
        if want and all(str(r["id"]) != want for r in here):
            got = " ".join(str(r["id"]) for r in here[:3])
            exp = cur.get("expected_48h")
            out += [
                f"**{d:%m/%d}（JST）は、決めと枠が食い違っています** —— "
                f"決め `{want}`（{cur.get('form') or '?'}"
                + (f"・見込み 齢48h {exp:.0f}回" if isinstance(exp, (int, float)) else "")
                + f"） ／ 枠に居るのは `{got}`",
                "  `data/daily_pick.jsonl` は**書く先で、押す先ではありません** ——"
                "決めを書いても、押さなければチャンネルは変わりません。",
                f"  入れ替え: `python scripts/reschedule.py --unschedule {here[0]['id']}` "
                f"→ `python scripts/reschedule.py --move {want} {d}T"
                + f"{(_hour_for(d) or 9):02d}:00`",
            ]
    return out


#: **`--ship` の本文に書けば、`today_block()` を1回だけ越えられる印。**
#: `run_marker.HINT_MISS_MARK` と同じ口 —— **禁止ではなく、理由を残させる門**です。
SLOT_MISS_MARK = "枠そのまま"


def today_block(rows: list[dict] | None = None, today=None,
                picked=None, published=None) -> list[str]:
    """**きょう公開される1本が、きょうの決めと違うなら、その行**（合っていれば空）。

    ## なぜ要るか（2026-09-05 06:0x・最適化の回。**この回に実測した**）

    `mismatch_lines()` は 05:4x に**印字**として入りました。その 12分後、
    この回が `python scripts/slot_gate.py` を撃つと、こう出ています::

        09/05（JST）は、決めと枠が食い違っています ——
        決め `TfetZ_qhS-E`（ショート・見込み 齢48h 164回） ／ 枠に居るのは `GFvAcxvDmYM`

    枠の `GFvAcxvDmYM` は **22分42秒 の長尺**で、同じ控えが付けた見込みは **齢48h 1回**。
    公開まで **3時間8分**でした。**164 対 1** —— きょうチャンネルが出す唯一の1本です。

    そして決めのほうは、同じ日のうちに **6回** 書き換わっています
    （00:38 長尺 → 01:17 → 01:48 → 05:09 ショート → 05:11 → 05:37）。
    **枠は 0回。** 決めを書く側には門が6つ 立っているのに
    （`daily_pick.record()` の `slot_cost` / `probe_hold` / `path_form_hold` /
    `anyway_pays_hold` / `restated_pick_block` / `day_guard`）、
    **押す側には1つも立っていませんでした。**

    書くほうは API 0単位・自分の手だけで終わり・commit になります。
    押すほうは 100単位 掛かり、チャンネルという相手が居ます。
    **門が片側にだけ生えたのは、その非対称のとおりです** ——
    だから「食い違いを印字する」を6回 通過して、枠は 1度も動きませんでした。

    この関数は `mismatch_lines(days=1)` そのもの（**判定の写しを持ちません**）。
    違うのは**きょうの日だけ**を見ることです —— 明日ぶんで回を止めると、
    まだ押せる時間が残っている日の回まで全部 止まります。

    ## 覆る条件（**この門を外してよい日**）

    1. `ahead_sweep.today_plan()` が枠の中身まで見て入れ替えるようになったら
       （`mismatch_lines()` の覆る条件と同じ）。**先に外さないこと。**
    2. `data/runs.jsonl` の `slot_miss` が 7日 続けて 0件 なら、
       この門は空振りしかしていません（そのとき外してよい）。
    """
    return mismatch_lines(rows, today, picked, published, days=1)


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
            # **`reschedule.py --pool` と書いてありました。そんな旗はありません**
            #     （2026-09-02 に撃って踏んだ: `usage: …` ＋ **exit 2**）。
            #     しかもここは、規則5 の下で**毎日 0時 JST に必ず通る道の1手目**です。
            #     下書きを一覧するのは `python -m src.next_slot`（**API 0単位**）——
            #     `src/next_slot.draft_lines()` が video_id と `--move` の1行まで出します。
            #     検査は `tests/test_printed_flags_exist.py`（repo ぜんぶを見ます）。
            "        python -m src.next_slot                      # private の下書きを見る（**0単位**）",
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
        ] + _hour_lines(gap[0]) + quota_lines() + [
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
    ] + _hour_lines(gap[0]) + quota_lines() + [
        "**撃てないなら**（Data API の日枠 ＝ JST 16:00 に戻る／`AUTOMATION_PAUSED.md`）、"
        "**その理由を `docs/JOURNAL.md` に書いてから終わること。**",
    ]
    return out


def main(argv: list[str]) -> int:
    gate = "--gate" in argv
    out = lines()
    # **食い違いも同じ門で鳴らすこと**（`mismatch_lines()` の註）。
    #     空の日（`lines()`）と食い違い（`mismatch_lines()`）は別の壊れ方で、
    #     **後者は「埋まっている」ので前者からは見えません。**
    try:
        mis = mismatch_lines()
    except Exception as exc:                                   # noqa: BLE001
        mis = []
        print(f"[slot_gate] 食い違いを読めませんでした（門は止めません）: "
              f"{str(exc)[:120]}")
    if not out and not mis:
        if not gate:
            print(f"予約が0本の日は、今日から{LEAD_DAYS}日 のうちにありません。"
                  "決めと枠の食い違いもありません。")
        return 0
    print("\n".join(out + (["", *mis] if out and mis else mis)))
    return 2 if gate else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
