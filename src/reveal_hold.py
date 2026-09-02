"""**「完成した図を説明のあいだ画面に残すと engaged が上がる」を、比べられる本で数える。**（API 0単位）

## この道具が在る理由（2026-08-31 に測って作った）

`config/hypotheses.yaml` のこの前提は、`needs:` にこう書いてありました:

    count_expr: "sum(1 for r in rows('uploaded.jsonl')
                     if (r.get('uploaded_at') or '') >= '2026-08-27T12:00'
                     and (r.get('at') or '9') <= str(date.today()))"
    need: 16

**`data/uploaded.jsonl` は1本につき1行ではありません。** 予約を動かすたびに
行が増えます（実測 2026-08-31: **850行 / 735本**）。この式は**行を数えていて**、
同じ本を何度も数えます。実測（2026-08-31 12:1x）:

    式の答え                                    **17**  → 「要 16 ／ いま 17 → 足りています」
    重複を畳んだ本数                            **11**  （`KfQeYEJwL7Q` だけで 4行）
    うちショート（尺 180秒以下）                  **8**  ← 長尺3本は `reveal_variants` を通らない
    うち齢48時間を過ぎた本（`falsified_if` の帯） **1**  ← **これが比べられる本**

そして `falsified_if` は「**必ず、同じ日の中で比べること**」と書いています。
処置と対照の**両方が居る公開日は 1日**（08/28・処置1本 対 対照1本）です。

**要る 16本 に対して、比べられるのは 1本でした。**

## それが何を壊していたか

`scripts/deadline_check._ans_accrual()` は `have >= want` で
`ready = 今日` を返します（その関数自身が「**ここには門がありません。
`count_expr` を丸ごと信じています**」と書いています）。そこから

    deadline_check.ready_by_claim()  → `src/arm_speed.next_close()`
    → `scripts/eta.py` の頭3行  「**この回は `verdict` で日付が動かせます**
       —— **いま判定できるのは**: 完成した図を説明のあいだ画面に残すと…」

**頭3行しか読まない手順**（この repo の既定の読み方）に従った回は、
**処置1本 対 対照189本**で中央値を比べ、`falsified_if`（同点も外れ）に当てて
**この前提を閉じます。** 閉じた前提は `eta.py` の軌跡の腕を動かすので、
**到達日が、在りもしないデータで動きます。**

**同じ形の穴が 2026-08-29 に1度 塞がれています** ——
`scripts/deadline_check.deep_short_arm()` の
「門は『作った／公開した』を、手順は『**比べられる**』を数えています」。
**あのときは前提1件ぶんを直しました。ここは2件目です。**

## 数え方（`falsified_if` の本文そのまま）

    処置   `uploaded_at` が 2026-08-27T12:00（UTC）以降に**作られた**本
    対照   それより前に作られた本
    共通   ショート（尺 180秒以下）／ 公開済み ／ **齢48時間**を過ぎている
           ／ **本で数える**（`video_id` で畳む）

**尺で絞るのは `config/watches.yaml` の「完成形の保持-16本」と同じ理由**です ——
長尺は `pipeline.reveal_variants` を1度も通らないので、混ぜると
**「対照と同じ中身の処置群」**で判定することになります。

**尺の分からない本は数えません**（`data/uploaded.jsonl` の古い行には
`duration_s` がありません）。満ちていないものを満ちたと言うより、
**遅れて満ちるほうが安全**です（`src/watches._k_published_count` と同じ向き）。

## 読むファイル（**API を1単位も使いません**）

    data/uploaded.jsonl   video_id → 作った時刻 `uploaded_at` ／ 公開時刻 `at` ／ 尺

engaged の比を実際に取るのは `verdict()` で、そこだけ **Analytics**（Data API の
日枠とは別枠）を1回 叩きます。**数えるほう（`arm_n`）は 0単位**です。

## 覆る条件

- `data/uploaded.jsonl` が1本1行になったら、重複を畳む必要はなくなります
  （`_uploads()` の畳みは残しても害はありません）
- 前提が判定されたら、この道具は `config/hypotheses.yaml` から外れます。
  **そのときも消さないこと** —— 同じ形の穴（門は行を、手順は本を数える）は
  これで2件目で、次に立てる前提が3件目になります
"""
from __future__ import annotations

import json
import statistics
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent.parent
JST = timezone(timedelta(hours=9))

#: **処置群の入口**（`pipeline.reveal_durations` が入った時刻）。
#: `data/uploaded.jsonl` の `uploaded_at` は UTC の ISO 文字列なので、
#: **文字列のまま比べます**（`config/hypotheses.yaml` の元の式と同じ切り方）。
LANDED = "2026-08-27T12:00"

#: ショートとみなす上限（秒）。`config/watches.yaml` の `max_duration_s` と同じ数。
MAX_SHORT_S = 180.0

#: `falsified_if` の「齢48時間でそろえた」。この時間を過ぎていない本は比べません。
AGE_HOURS = 48

SIDES = ("処置", "対照")


def _rows(name: str = "uploaded.jsonl") -> list[dict]:
    path = ROOT / "data" / name
    try:
        import json
        return [json.loads(x) for x in
                path.read_text(encoding="utf-8").splitlines() if x.strip()]
    except Exception:                                          # noqa: BLE001
        return []


def _uploads(rows: list[dict] | None = None) -> dict[str, dict]:
    """**`video_id` → 1本ぶんに畳んだ控え**（後の行の値が勝つ／`None` は上書きしない）。

    畳まないと、予約を動かした本ほど重く数えられます
    （実測 2026-08-31: 850行 / 735本・1本で最大4行）。
    """
    out: dict[str, dict] = {}
    for r in (_rows() if rows is None else rows):
        vid = r.get("video_id")
        if not vid:
            continue
        cur = out.setdefault(str(vid), {})
        cur.update({k: v for k, v in r.items() if v is not None})
    return out


def _is_stockpile(rec: dict, now: datetime | None = None) -> bool:
    """**その控えは「作り置き」か**（規則2・`src/house_rule.is_stockpile`）。

    ## なぜ要るか（2026-09-01・最適化の回に、実物で踏んだ）

    `next_ready()` は「予約表から」その群が `need` 本 そろう日を出します。
    **予約表は、規則2 が外す本でできていました。** 実測 2026-09-01 ——
    控えの未来の予約 **293本 は 293本 とも作り置き**（作り置きでない未来の予約は 0本）。
    それでも `scripts/status.py` はこう印字していました:

        あと **10本**  完成形の保持-16本（いま 6 / 要る 16）
            … ／ **予約表では 2026-09-02 にそろう**

    **09/02 には そろいません。** その 10本 は `pool_drain --apply` が外すので
    1本も公開されません。**「明日そろう」と読んだ回は、何もしないのが正解だと読みます。**

    `src/judgeable.members()` は 2026-08-31 に同じ絞りを入れています
    （「作り置きの予約は、床に数えません」）。**同じ台帳を読む2つ目の入口が、
    その絞りを持っていませんでした。**

    `src/house_rule.py` の警告どおりの形です ——
    **「これから出る本」として数えると、在りもしない供給で日付が早く出ます。**

    **覆る条件**: オーナーが規則2 を外したら（`house_rule.STOCKPILE_IS_SUPPLY`）、
    `is_stockpile()` が全部 `False` を返すので、この絞りは自然に消えます。
    **読めない回は `False`**（＝落とさない）—— 測っていないことを落とす側に倒さない。
    """
    try:
        from src import house_rule                              # noqa: PLC0415

        today = (now or datetime.now(timezone.utc)).astimezone(JST).strftime("%Y-%m-%d")
        return bool(house_rule.is_stockpile(rec, today))
    except Exception:                                           # noqa: BLE001
        return False


def _parse(value: Any) -> datetime | None:
    try:
        when = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def side_of(rec: dict) -> str:
    """**作った時刻**で処置／対照を決める（公開時刻ではありません）。"""
    return "処置" if str(rec.get("uploaded_at") or "") >= LANDED else "対照"


def comparable(now: datetime | None = None,
               rows: list[dict] | None = None) -> dict[str, list[str]]:
    """**比べられる本**を群べつに返す（`falsified_if` の帯そのまま・API 0単位）。

    返りは `{"処置": [video_id...], "対照": [...]}`。並びは公開の早い順。
    """
    now = now or datetime.now(timezone.utc)
    out: dict[str, list[str]] = {s: [] for s in SIDES}
    ranked: list[tuple[datetime, str, str]] = []
    for vid, rec in _uploads(rows).items():
        sec = rec.get("duration_s")
        if sec is None:
            continue                                # 尺が読めない本は数えない（安全側）
        try:
            if float(sec) > MAX_SHORT_S:
                continue
        except (TypeError, ValueError):
            continue
        pub = _parse(rec.get("at"))
        if pub is None or pub > now - timedelta(hours=AGE_HOURS):
            continue
        ranked.append((pub, side_of(rec), vid))
    for pub, side, vid in sorted(ranked):
        out[side].append(vid)
    return out


def arm_n(side: str = "処置", now: datetime | None = None) -> int:
    """**その群で比べられる本の数**（`count_expr` から呼びます）。

        count_expr: "reveal_hold_arm('処置')"

    `scripts/deadline_check.EXPR_NS` に載せてあります。
    """
    return len(comparable(now).get(side, []))


def paired_days(now: datetime | None = None,
                rows: list[dict] | None = None) -> dict[date, dict[str, list[str]]]:
    """**処置と対照が両方 居る公開日**（JST の暦日）。

    `falsified_if` の「**【必ず、同じ日の中で比べること】**」がこれです ——
    1本あたりの数字を動かしている最大の要因は「その日に何本 出したか」で
    （`src/day_cap.py`）、処置は新しく対照は古いので、**日で割らないと
    「新しい日は本数が少なかっただけ」が差として残ります。**
    """
    now = now or datetime.now(timezone.utc)
    ups = _uploads(rows)
    days: dict[date, dict[str, list[str]]] = {}
    for side, ids in comparable(now, rows).items():
        for vid in ids:
            pub = _parse(ups.get(vid, {}).get("at"))
            if pub is None:
                continue
            day = pub.astimezone(JST).date()
            days.setdefault(day, {s: [] for s in SIDES})[side].append(vid)
    return {d: v for d, v in sorted(days.items()) if v["処置"] and v["対照"]}


def next_ready(need: int = 16, now: datetime | None = None,
               rows: list[dict] | None = None, side: str = "処置") -> date | None:
    """**その群が `need` 本 そろう最早の日**（予約表から。伸び率の推定ではありません）。

    予約に入っているその群のショートを公開の早い順に並べ、`need` 本目の公開日に
    **齢48時間**を足した日を返します。届かなければ `None`（＝ 在庫が足りない）。

    **`falsified_if` は「どちらも 16本 に満たなければ判定できない」**と書いて
    いるので、判定日は**両群の遅いほう**です（`render()` がそう出します）。
    """
    now = now or datetime.now(timezone.utc)
    have = comparable(now, rows)[side]
    if len(have) >= need:
        return now.astimezone(JST).date()
    ahead: list[datetime] = []
    for _vid, rec in _uploads(rows).items():
        if side_of(rec) != side:
            continue
        if _is_stockpile(rec, now):
            continue                       # 規則2 ＝ 公開されない本（下の註）
        sec = rec.get("duration_s")
        pub = _parse(rec.get("at"))
        if sec is None or pub is None:
            continue
        try:
            if float(sec) > MAX_SHORT_S:
                continue
        except (TypeError, ValueError):
            continue
        if pub > now - timedelta(hours=AGE_HOURS):
            ahead.append(pub)
    ahead.sort()
    want = need - len(have)
    if len(ahead) < want:
        return None
    return (ahead[want - 1] + timedelta(hours=AGE_HOURS)).astimezone(JST).date()


# ---------------------------------------------------------------- 判定の側

def ratios_by_day(ratios: dict[str, float], now: datetime | None = None,
                  rows: list[dict] | None = None) -> list[tuple[date, float, float]]:
    """**公開日ごとの（対照の中央値, 処置の中央値）**。両群が居る日だけ返します。"""
    out: list[tuple[date, float, float]] = []
    for day, sides in paired_days(now, rows).items():
        new = [ratios[v] for v in sides["処置"] if v in ratios]
        old = [ratios[v] for v in sides["対照"] if v in ratios]
        if new and old:
            out.append((day, statistics.median(old), statistics.median(new)))
    return out


def verdict(pairs: Iterable[tuple[date, float, float]], need_days: int = 3) -> dict:
    """**日ごとに対にして、処置が上回った日を数える。**（`falsified_if`＝同点も外れ）

    1日ぶんでは、その日の題材の当たり外れと区別が付きません
    （`config/hypotheses.yaml` の density の `falsified_if` と同じ理由）。
    **`need_days` に満たなければ判定しません。**
    """
    pairs = list(pairs)
    if len(pairs) < need_days:
        return {"decided": False,
                "why": f"両群がそろう公開日が {len(pairs)}日（要 {need_days}日）",
                "days": len(pairs)}
    up = sum(1 for _d, old, new in pairs if new > old)
    return {"decided": True, "upheld": up * 2 > len(pairs),
            "days": len(pairs), "days_up": up,
            "verdict": "survived" if up * 2 > len(pairs) else "falsified"}


ATTEMPTS = ROOT / "data" / "reveal_hold_attempts.jsonl"

#: **`verdict()` が要る「比の取れた日」の数。** 出どころはここ1か所。
NEED_DAYS = 3


def record_attempt(res: dict, pairs_n: int, now: datetime | None = None,
                   path: Path | None = None) -> None:
    """**判定を撃った跡を1行 残す。**（`data/reveal_hold_attempts.jsonl`）

    ## なぜ要るか（2026-09-02・最適化の回。**この回に撃って踏んだ**）

    この道具は、**同じ回の中で2つのことを言っていました**:

        render()   両群がそろう公開日: **4日** → **判定できます**
        --judge    比の取れた本 17本 ／ 対にできた日 **2日**
                   → {'decided': False, 'why': '両群がそろう公開日が 2日（要 3日）'}

    `paired_days()` は**控えだけ**で数えます（その日に両群の本が居るか）。
    `ratios_by_day()` は、そこへ **Analytics の engaged 比**を join します ——
    **比の付かない本が落ちて、4日 が 2日 に減りました**（08/28・08/29 が消えた）。
    `verdict()` が見ているのは後者で、**前者では一度も判定できません。**

    そして `config/hypotheses.yaml` の `needs` は

        count_expr: "min(reveal_hold_arm('処置'), reveal_hold_arm('対照'))"
        need: 16

    ＝ **本の数**しか数えていません。16本 は満ちているので
    `scripts/deadline_check.py` は「満ちた」と言い、`scripts/eta.py` は頭の3行で
    **「この回は `verdict` で日付が動かせます」**と、この前提を名指しします。
    **撃つと判定できません。** 毎周 その往復を1回ぶん捨てています。

    **この前提の註が、同じ形の穴を自分で2回 数えています** ——
    「門は『作った／公開した』を、手順は『**比べられる**』を数えている」
    （`deep_short_arm()` 2026-08-29 が1件目、`arm_n` の行／本 が2件目）。
    **これが3件目です。** 違いは、今度は 0単位 では見えないこと ——
    **比が付くかは Analytics を撃つまで分かりません。**
    だから**撃った結果のほうを控えに残します。**

    ## 覆る条件

    比の付かなかった本に、あとから Analytics が比を付けたら（遅れは 2〜3日）、
    同じ日が生き返ります。**だから跡は「最後の1回」ではなく積みます** ——
    `last_attempt()` は新しい行を読み、古い行は履歴として残ります。
    """
    path = path or ATTEMPTS
    rec = {"ts": (now or datetime.now(timezone.utc)).isoformat(),
           "pairs": int(pairs_n), "need_days": int(NEED_DAYS),
           "decided": bool(res.get("decided")),
           "why": str(res.get("why") or ""),
           "verdict": str(res.get("verdict") or "")}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def last_attempt(path: Path | None = None) -> dict | None:
    """**最後に判定を撃った跡**（無ければ `None`）。**API 0単位。**"""
    path = path or ATTEMPTS
    if not path.exists():
        return None
    out = None
    for ln in path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out = json.loads(ln)
        except json.JSONDecodeError:
            continue
    return out


def judgeable_days(now: datetime | None = None,
                   rows: list[dict] | None = None,
                   path: Path | None = None) -> int:
    """**`verdict()` に実際に渡せる日の数**（**API 0単位**）。

    一度でも撃っていれば、**その実測**（比の取れた日）を返します ——
    控えだけで数えた `paired_days()` は**上限**であって、
    `verdict()` が見る数ではありません（`record_attempt` の註）。

    まだ一度も撃っていない回は `paired_days()` を返します
    （＝ 上限。**最初の1回は撃ってみないと分かりません**）。
    """
    got = last_attempt(path)
    if got is None:
        return len(paired_days(now, rows))
    # **控えが撃った時より増えていたら、上限のほうも一緒に下がれないこと** ——
    # 新しい本が出れば比の取れる日は増えうるので、`max` は取りません。
    # 撃った跡が「足りない」と言っている以上、**次に撃つまでは足りない**が正しい。
    return int(got.get("pairs") or 0)


def render(now: datetime | None = None) -> str:
    """画面に出す本文（**API 0単位**）。"""
    now = now or datetime.now(timezone.utc)
    rows = _rows()
    ups = _uploads(rows)
    both = comparable(now, rows)
    days = paired_days(now, rows)
    ready_t = next_ready(16, now, rows, "処置")
    ready_c = next_ready(16, now, rows, "対照")
    ready = None if (ready_t is None or ready_c is None) else max(ready_t, ready_c)
    n_rows_treat = sum(1 for r in rows
                       if str(r.get("uploaded_at") or "") >= LANDED
                       and str(r.get("at") or "9") <= str(now.astimezone(JST).date()))
    n_vid_treat = sum(1 for r in ups.values()
                      if side_of(r) == "処置"
                      and str(r.get("at") or "9") <= str(now.astimezone(JST).date()))
    lines = [
        "=== 完成形の保持: **比べられる本**（API 0単位・`data/uploaded.jsonl` だけ）===",
        f"  控え {len(rows)}行 / {len(ups)}本"
        f"（**1本につき1行ではありません。行で数えると重複します**）",
        f"  公開済みの処置: 行で **{n_rows_treat}** ／ 本で **{n_vid_treat}**",
        f"  比べられる（ショート {MAX_SHORT_S:.0f}秒以下・齢{AGE_HOURS}時間 以上）:"
        f" 処置 **{len(both['処置'])}本** ／ 対照 **{len(both['対照'])}本**"
        f"（**どちらも 16本** 要る）",
        f"  両群がそろう公開日: **{len(days)}日**"
        + (f"（{', '.join(str(d) for d in days)}）" if days else ""),
    ]
    if min(len(both["処置"]), len(both["対照"])) >= 16:
        att = last_attempt()
        if att and not att.get("decided"):
            # **撃った跡が「足りない」と言っている**（`record_attempt` の註）。
            lines.append(
                f"  → **まだ判定できません。** 前に撃ったとき、**比の取れた日は"
                f" {att.get('pairs')}日**（要 {att.get('need_days', NEED_DAYS)}日）"
                f"でした（{str(att.get('ts'))[:16]}）。")
            lines.append(
                f"     **上の「そろう公開日 {len(days)}日」は控えだけの数 ＝ 上限**です ——"
                "`verdict()` が見るのは **Analytics の engaged 比が付いた日**のほうで、"
                "比の付かない本が落ちるとここまで減ります。")
            lines.append(
                "     **増えるのは公開したぶんだけ**です（規則1 ＝ 1日1本）。"
                "撃ち直すのは、両群のそろう日が増えてから:"
                " `python -m src.reveal_hold --judge`")
        else:
            lines.append("  → **判定を撃てます**（`python -m src.reveal_hold --judge`"
                         "・Analytics 1回）。**ただし「判定できる」ではありません** ——"
                         f"`verdict()` が要るのは **比の取れた日 {NEED_DAYS}日**で、"
                         f"上の {len(days)}日 は控えだけの**上限**です")
    elif ready:
        lines.append(f"  → **まだ判定できません。** 予約表で両群が 16本 そろうのは"
                     f" **{ready}**（処置 {ready_t} ／ 対照 {ready_c}・齢{AGE_HOURS}時間 込み）")
    else:
        lines.append("  → **まだ判定できません。** 予約に入っているショートでは"
                     f" どちらかが 16本 に届きません（処置 {ready_t} ／ 対照 {ready_c}"
                     "・`None` は在庫の側の話）")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:  # pragma: no cover - 画面出力だけ
    import sys

    argv = list(sys.argv[1:] if argv is None else argv)
    print(render())
    if "--judge" not in argv:
        return
    both = comparable()
    if min(len(both["処置"]), len(both["対照"])) < 16:
        print("  [!] **判定はしません**（どちらかの群が 16本 に満ちていません）。"
              "**満ちる前に閉じないこと** —— `falsified_if` は「まだ分からない」で"
              "閉じることを禁じています")
        return
    from src.length_verdict import fetch_engaged, ratios       # noqa: PLC0415

    ids = both["処置"] + both["対照"]
    start = date.today() - timedelta(days=90)
    rows = fetch_engaged(ids, start, date.today())
    got = ratios(rows)
    pairs = ratios_by_day(got)
    print(f"  比の取れた本: {len(got)}本 ／ 対にできた日: {len(pairs)}日")
    for day, old, new in pairs:
        mark = "処置" if new > old else "対照"
        print(f"    {day}  対照 {old:.3f} 対 処置 {new:.3f}  → {mark}")
    res = verdict(pairs)
    print("  ", res)
    record_attempt(res, len(pairs))
    if not res.get("decided"):
        print("  [!] **閉じないこと。** この跡は控えに残したので、"
              "次の回の `python -m src.reveal_hold`（0単位）と "
              "`scripts/deadline_check.py` は「まだ判定できない」と言います "
              "（`src/reveal_hold.record_attempt` の註）")


if __name__ == "__main__":                                     # pragma: no cover
    main()
