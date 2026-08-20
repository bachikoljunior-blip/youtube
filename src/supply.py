"""**その密度を、在庫が支えられるか。**（API は 0 単位。読むのは手元のファイルだけ）

## なぜ要るか（2026-08-20 13:4x に測って足した）

`scripts/eta.py` は **`PLAN_PUBLISH_PER_DAY = 25`** を定数で持っていて、
段1（登録者1,000人の門）の日付を `a["days_subs_at"][25]` から取ります。
段1 が段3（審査）を、段3 が段4（月20万）を押すので、**到達予測の日付は
まるごとこの 25 の上に乗っています。**

**そして、その 25本/日 を出せるかを、どこも確かめていませんでした。**

    定数の脇の註は「受け取り帳 3c7e12a3 の詰め直しが着地する所」——
    つまり **予約を詰め直したときの置き方**であって、**作れる本数ではありません。**

実測（この回）:

    テーマ在庫（未投稿）        28本  ＝ 25本/日 なら **1.1日ぶん**
    未使用の節                   0件  （`status.py`。402節が全部テーマになっている）
    `config/topics.yaml`  08/19 16:34 UTC を最後に **20時間 増えていません**

到達予測は **157日後**（2027-01-24）です。25本/日 × 157日 ＝ **3,925本**。
在庫は 28本。**桁が2つちがいます。**

## 何を supply と数えるか

テーマは `topic_forge` が「まだテーマになっていない節」から作ります
（`scripts/topic_forge.py`。**新しい計算は1つも足しません**）。
その節がもう 0件なので、**次のテーマは `src/calc/` に節を書かないと出ません。**

節を書く材料は `src/section_sweep` が機械で拾っています ——
**906件の候補、うち「まだどの節も言っていない」もの**が supply の本体です。

    supply ＝ 未投稿テーマ（在庫） ＋ まだ節が言っていない掃引の候補

**候補は節そのものではありません**（意味と正しさは人が決める）。
だから supply は**上限側の見積り**です。**下限ではありません** ——
「これだけあれば足りる」の証拠には使えず、**「これしか無い」の証拠**にだけ使えます。

## この道具が言えないこと

- **新しい表（(A)）は数えていません。** `src/calc/` に表を1本書けば節が +5前後
  増えるので、supply は人が書けばいくらでも伸びます。ここが数えているのは
  **「いま在るものだけで何日もつか」**です
- 掃引の候補が節になる歩留りは **0.156**（2026-08-20 に 32件を目で見て付けた1点。
  それまでは 1.0 ＝ 測らずに上限側へ置いていました）。**根拠と覆る条件は
  `SWEEP_YIELD` の註**。無作為標本ではないので、**さらに低い側**にも動きえます
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "supply.jsonl"

#: 掃引の候補のうち、**実際に節になる割合**。
#:
#: **2026-08-20 15:5x に、初めて目で見て1点入れました**（それまで 1.0）。
#: `python -m src.section_sweep` の一覧から、**族ごとの先頭6件**（＝形の
#: 優先順に並んだ頭）を 32件ぶん読んで「節になる／ならない」を付けた結果:
#:
#:     nenkin 1/6 ・ iryohi 2/6 ・ zangyo 0/6 ・ fukugyo 0/2
#:     jutaku 1/2 ・ tedori 1/6 ・ furusato 0/4   → **5/32 = 0.156**
#:
#: 落ちた27件の内訳は、ほぼ3種類しかありません:
#:
#:   1. **引数の振れ幅の作りごと**（いちばん多い）——`social_rate` を 0.7〜0.9
#:      まで振って住民税が 0、`role_allowance` 1〜9円、`monthly_pay` 1,200万円。
#:      `_grid` は「率」を一律 0.1〜0.9 で振るので、**実在しない世界の崖**が出ます
#:   2. **自明な片効き・不変** —— 「倍率は額に依らない」「まとめた側は分割数に依らない」
#:   3. **道具自身が「書けない」と言っているもの**（`[並 N点]` の同値並び）
#:
#: **割り引いて読むこと。無作為標本ではありません** —— 各族の先頭は形の
#: 優先順で並んでいるので、**良いほうに寄っている可能性があります**（＝真の
#: 歩留りはさらに低いかもしれない）。**覆る条件**: 1で挙げた「率の格子」を
#: 引数ごとに実在する幅へ直したら、測り直すこと。**そこが最大の落ち先**なので、
#: 直せば歩留りは上がります。
SWEEP_YIELD = 0.156

JST = timezone(timedelta(hours=9))


def today_jst() -> date:
    """**UTC の `date.today()` を使わないこと**（JST 00〜09時に前日を返します）。"""
    return datetime.now(JST).date()


# ---------------------------------------------------------------- 在庫

def stock() -> int:
    """未投稿のテーマ数。**API は叩きません**（`data/uploaded.jsonl` の控えだけ）。

    `scripts/batch_build.pick` はチャンネルと控えの**和**で投稿済みを数えますが、
    チャンネル側は日枠が閉じると 403 で落ちます。ここは控えだけで数えるので、
    **投稿済みを取りこぼす側**＝**在庫を多めに言う側**に倒れます（上限側）。
    """
    from src import config, dupes

    pool = config.load_topics()["topics"]
    used = {r["topic"] for r in dupes.ledger_rows() if r.get("topic")}
    return sum(1 for t in pool if t.get("id") not in used and t.get("calc"))


# ---------------------------------------------------------------- 掃引の余地

def topics_total() -> int:
    """`config/topics.yaml` のテーマ総数。**作る速さの正本**（在庫は出せば減る）。"""
    from src import config

    return len(config.load_topics()["topics"])


def sweep_novel(*, compute: bool = False, max_age_hours: float = 24.0) -> dict:
    """「まだどの節も言っていない」掃引の候補の数。

    **全表の掃引は約47秒**かかるので、既定では `data/supply.jsonl` の
    いちばん新しい点を読みます。`compute=True` で測り直して積みます。

    返り: `{"novel": int, "total": int, "at": iso文字列 or None, "age_hours": float or None}`
    `novel` が `None` のときは「一度も測っていない」——
    **0 と取り違えないこと**（0 は「余地が尽きた」という別の意味です）。
    """
    if not compute:
        point = last_point()
        if point and point.get("sweep_novel") is not None:
            age = _age_hours(point.get("at"))
            if age is not None and age <= max_age_hours:
                return {"novel": point["sweep_novel"], "total": point.get("sweep_total"),
                        "at": point.get("at"), "age_hours": age}
            # 古くても、無いよりは読める。**年齢を添えて返す**（黙って捨てない）
            return {"novel": point["sweep_novel"], "total": point.get("sweep_total"),
                    "at": point.get("at"), "age_hours": age}
        return {"novel": None, "total": None, "at": None, "age_hours": None}

    from src import section_sweep as ss

    hits = ss.sweep_all()
    total_by, novel_by = ss.novel_counts(hits, _all_sections())
    return {"novel": sum(novel_by.values()), "total": sum(total_by.values()),
            "at": datetime.now(JST).isoformat(timespec="seconds"), "age_hours": 0.0}


def _all_sections() -> dict[str, dict[str, str]] | None:
    """表ごとの「いまの節」。`section_sweep.is_covered` の被覆判定に渡します。

    出どころは `scripts/topic_forge.survey()` —— `status.py` が
    `novel_counts` に渡しているのと**同じもの**です（別々に数えると食い違います）。
    """
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    import topic_forge  # noqa: E402

    all_sections, _free, _known = topic_forge.survey()
    return all_sections


def free_sections() -> int:
    """まだテーマになっていない節の数（`status.py` の「未使用の節」と同じ）。"""
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    import topic_forge  # noqa: E402

    _all, free, _known = topic_forge.survey()
    return sum(len(v) for v in free.values())


# ---------------------------------------------------------------- 台帳

def _age_hours(at: str | None) -> float | None:
    if not at:
        return None
    try:
        t = datetime.fromisoformat(at)
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=JST)
    return (datetime.now(JST) - t).total_seconds() / 3600.0


def points() -> list[dict]:
    if not CACHE.exists():
        return []
    out = []
    for line in CACHE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def last_point() -> dict | None:
    ps = points()
    return ps[-1] if ps else None


def record(row: dict) -> dict:
    """1点積む。**`at` は必ず入れること**（速さは点の差からしか出ません）。"""
    row = dict(row)
    if row.get("at") is None:
        row.pop("at", None)
    row.setdefault("at", datetime.now(JST).isoformat(timespec="seconds"))
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    with CACHE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


# ---------------------------------------------------------------- 本体

def supply(density: int, *, stock_n: int | None = None,
           novel: int | None = None, horizon_days: float | None = None,
           run_minutes: float = 60.0, today: date | None = None) -> dict:
    """**その密度を、何日ぶん supply できるか。**

    `density` は 1日に公開する本数（`eta.PLAN_PUBLISH_PER_DAY`）。
    `horizon_days` を渡すと、そこまで保つかどうかも返します。

    **足りない側にしか使えません**（上の docstring）。
    """
    d0 = today or today_jst()
    s = stock() if stock_n is None else stock_n
    n = 0 if novel is None else int(novel * SWEEP_YIELD)
    total = s + n

    if density <= 0:
        days = float("inf")
    else:
        days = total / density

    out = {
        "density": density,
        "stock": s,
        "sweep_novel": novel,
        "supply_total": total,
        "days_covered": days,
        "dry_date": (d0 + timedelta(days=int(days))) if days != float("inf") else None,
        "measured": novel is not None,
    }
    if horizon_days is not None:
        need = density * horizon_days
        out["horizon_days"] = horizon_days
        out["need_total"] = need
        out["shortfall"] = max(0.0, need - total)
        out["holds"] = total >= need
        # 期日まで保たせるのに、**1日あたり何本の節を新しく書く必要があるか**
        out["sections_per_day_needed"] = (
            (need - total) / horizon_days if horizon_days > 0 and need > total else 0.0
        )
        # **1周あたり何本か**。ここが、この回に持って帰る数です ——
        # 「1日 21.6本」は誰の仕事でもありませんが、「1周 0.9本」はこの回の仕事です。
        runs_per_day = (24 * 60 / run_minutes) if run_minutes > 0 else 0.0
        out["run_minutes"] = run_minutes
        out["sections_per_run_needed"] = (
            out["sections_per_day_needed"] / runs_per_day if runs_per_day > 0 else float("inf")
        )
        # supply が尽きた後に出せる密度（在庫だけで割った実効密度）
        out["density_supported"] = total / horizon_days if horizon_days > 0 else float("inf")
    return out


def lines(sp: dict) -> list[str]:
    """`eta.py` が印字する行。**数字だけ。判断は書かない。**"""
    L: list[str] = []
    L.append(f"--- **その密度（{sp['density']:g}本/日）を、在庫が支えられるか** ---")
    if not sp["measured"]:
        L.append("    掃引の余地を**一度も測っていません**（`python -m src.supply --measure` で1点入ります）。")
    L.append(f"    未投稿のテーマ（在庫）      {sp['stock']:>6,} 本"
             f"  ＝ **{sp['stock'] / sp['density']:.1f}日ぶん**"
             if sp["density"] > 0 else f"    未投稿のテーマ（在庫） {sp['stock']:,} 本")
    if sp["sweep_novel"] is not None:
        L.append(f"    まだ節が言っていない候補    {sp['sweep_novel']:>6,} 件"
                 f"  （`src.section_sweep`。**節そのものではない ＝ 上限側**）")
    L.append(f"    合わせて                    {sp['supply_total']:>6,} 本"
             f"  ＝ **{sp['days_covered']:.0f}日ぶん**"
             + (f"（{sp['dry_date']} に尽きる）" if sp.get("dry_date") else ""))
    if "horizon_days" in sp:
        L.append(f"    到達予測まで                {sp['horizon_days']:>6,.0f} 日"
                 f"  ＝ 要る本数 **{sp['need_total']:,.0f}本**")
        if sp["holds"]:
            L.append("    → **保ちます。** この密度は在庫の側からは縛られていません")
        else:
            L.append(f"    [!] **保ちません。** 足りないのは **{sp['shortfall']:,.0f}本** ——"
                     f" 期日まで {sp['density']}本/日 を続けるには、"
                     f"**1日あたり 節を {sp['sections_per_day_needed']:.1f}本** 新しく書くこと")
            L.append(f"        いま在るものだけで割ると、実効の密度は"
                     f" **{sp['density_supported']:.1f}本/日**（{sp['density']}本/日 ではありません）")
            L.append(f"        → **1周（{sp['run_minutes']:.0f}分）あたり 節 "
                     f"{sp['sections_per_run_needed']:.1f}本。**"
                     f" これが `density` の腕の、この回ぶんの仕事です")
    return L


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="密度を在庫が支えられるかを出す（API 0単位）")
    p.add_argument("--density", type=int, default=25, help="1日に公開する本数")
    p.add_argument("--horizon", type=float, default=None, help="到達予測までの日数")
    p.add_argument("--run-minutes", type=float, default=60.0,
                   help="1周の間隔（分）。`quota.py --pace` の「持続できる間隔」")
    p.add_argument("--measure", action="store_true",
                   help="掃引をやり直して1点積む（約47秒）")
    p.add_argument("--record", action="store_true",
                   help="掃引はやり直さず、在庫とテーマ総数だけ1点積む（1秒未満）。"
                        "**作る速さ（make_rate）は点の差からしか出ません**")
    args = p.parse_args()

    sw = sweep_novel(compute=args.measure)
    s = stock()
    if args.measure or args.record:
        record({"at": sw["at"] if args.measure else None, "stock": s,
                "topics_total": topics_total(),
                "sweep_total": sw["total"], "sweep_novel": sw["novel"]})
        print(f"[supply] 積みました: {CACHE}")
    elif sw["age_hours"] is not None:
        print(f"[supply] 掃引の点は {sw['age_hours']:.1f}時間前のものです"
              f"（測り直しは --measure）")

    sp = supply(args.density, stock_n=s, novel=sw["novel"], horizon_days=args.horizon,
                run_minutes=args.run_minutes)
    for line in lines(sp):
        print(line)


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------- 作る速さ
#
# **ここから下は 2026-08-20 16:0x に足しました。** オーナー指示（原文）:
#
#   > 25は物理的に不可ならそれを予測に使うのはどうなの？
#   > 分析して制作に活かして視聴回数などを上げることが予測に使えることじゃない？
#
# そのとおりでした。`scripts/eta.py` の `PLAN_PUBLISH_PER_DAY = 25` は
# **予約の詰め方**であって、**作れる本数ではありません。** 上の `supply()` は
# それを「保ちません」と印字するだけで、**日付そのものは 25 の上に乗ったまま**でした
# （`_report_supply` の註に「この節は日付を動かしません」と書いてあります）。
#
# **満たせない前提を入力にした日付は、予測ではありません。**
#
# ではなにを入力にするか。**測れるもの**です —— テーマが1日に何本増えているか。
# これは「人が節を書けば伸びる」ので固定値ではありませんが、**書いているのは
# この回そのもの**なので、その速さは実測できます（下の `make_rate`）。
#
# **材料（掃引の候補）を壁として扱わないこと。** 壁にすると「新しい表を1本も
# 書かない未来」を予測として印字します。材料は**尽きる日**として出し、
# 直線そのものは実測の速さで引きます。

def uploads_before(ts: datetime, rows: list[dict] | None = None) -> int:
    """`ts` までに**作った**本数（`data/uploaded.jsonl` の `uploaded_at`）。

    在庫は作れば増え、出せば減ります。**累計で作った数**を出すには、
    そのときの在庫に、そこまでに出した本数を足し戻す必要があります。
    """
    if rows is None:
        rows = _ledger_rows()
    n = 0
    for r in rows:
        u = r.get("uploaded_at")
        if not u:
            continue
        try:
            t = datetime.fromisoformat(str(u).replace("Z", "+00:00"))
        except ValueError:
            continue
        if t.tzinfo is None:
            t = t.replace(tzinfo=JST)
        if t <= ts:
            n += 1
    return n


def _ledger_rows() -> list[dict]:
    path = ROOT / "data" / "uploaded.jsonl"
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def created_series(ps: list[dict] | None = None) -> tuple[list[tuple[datetime, int]], str]:
    """**累計で作ったテーマ数**の並びと、その出どころ。`(時刻, 本数)` を古い順に。

    出どころは2つあり、**混ぜてはいけません**（2026-08-20 16:1x に実測で踏んだ）。

        topics_total  `config/topics.yaml` の総数。**正本**
        復元          `在庫 + そこまでに出した本数`。古い点用

    **この2つは同じ数になりません。** `stock()` は「`calc` を持つ・まだ出していない」
    テーマだけを数え、控えの側にも topics.yaml に無い行が混じります ——
    実測で **417（復元）と 437（正本）で 20本ちがいました。** 1つの並びに混ぜると、
    **物差しの差が「2.7時間で +21本」＝ 1日183本という速さ**として出ます
    （実際に増えたのは 0本）。**だから、どちらか片方だけで並びを作ります。**

    返り: `(並び, 出どころ)`。`topics_total` の点が2つ以上あればそちらへ、
    無ければ復元へ落ちます（**正本の点が貯まれば自動で切り替わる**）。
    """
    ps = points() if ps is None else ps
    parsed: list[tuple[datetime, dict]] = []
    for p in ps:
        at = p.get("at")
        if not at:
            continue
        try:
            t = datetime.fromisoformat(at)
        except ValueError:
            continue
        if t.tzinfo is None:
            t = t.replace(tzinfo=JST)
        parsed.append((t, p))
    parsed.sort(key=lambda r: r[0])

    exact = [(t, int(p["topics_total"])) for t, p in parsed
             if p.get("topics_total") is not None]
    if len(exact) >= 2:
        return exact, "topics_total"

    rows = _ledger_rows()
    approx = [(t, int(p["stock"]) + uploads_before(t, rows)) for t, p in parsed
              if p.get("stock") is not None and p.get("topics_total") is None]
    return approx, "復元（在庫＋投稿済み）"


#: この時間より短い窓では、速さを名乗らない（1本の増減で桁が変わるため）
MIN_RATE_HOURS = 1.0


def make_rate(ps: list[dict] | None = None,
              min_hours: float = MIN_RATE_HOURS) -> dict:
    """**テーマが1日に何本増えているか。実測。**

    返り: `{"per_day": float|None, "hours": float, "delta": int, "n": int,
            "thin": bool}`

    - `per_day` が `None` なら「**まだ測っていない**」。0 と取り違えないこと
      （0 は「増えていない」という別の意味です）
    - `thin` は「窓が 6時間 未満」＝ 1本の増減で桁が動く帯。
      **数は返しますが、断りを付けて印字すること**
    - `basis` は出どころ（`created_series`）。**物差しが切り替わった回は、
      その差を「速くなった」と読まないこと**
    """
    s, basis = created_series(ps)
    if len(s) < 2:
        return {"per_day": None, "hours": 0.0, "delta": 0, "n": len(s),
                "thin": True, "basis": basis}
    (t0, v0), (t1, v1) = s[0], s[-1]
    hours = (t1 - t0).total_seconds() / 3600.0
    if hours < min_hours:
        return {"per_day": None, "hours": hours, "delta": v1 - v0,
                "n": len(s), "thin": True, "basis": basis}
    return {"per_day": (v1 - v0) / (hours / 24.0), "hours": hours,
            "delta": v1 - v0, "n": len(s), "thin": hours < 6.0, "basis": basis}


def published_by(t: float, *, stock: int, rate_per_day: float,
                 plan_density: float) -> float:
    """**t日後までに公開できる本数の累計。**

    2本の直線の**低いほう**です。どちらも単調なので、min も単調:

        予約の詰め方   plan_density × t          （在庫が足りているあいだの上限）
        作る速さ       stock + rate_per_day × t  （在庫を食い終わった先の上限）

    材料（掃引の候補）は**ここでは壁にしません** —— 壁にすると
    「新しい表を1本も書かない未来」を予測として印字することになります。
    尽きる日は `material_dry_days` が別に出します。
    """
    if t <= 0:
        return 0.0
    return min(plan_density * t, stock + max(0.0, rate_per_day) * t)


def days_for(need: float, *, stock: int, rate_per_day: float,
             plan_density: float, never: float = 36_500.0) -> float:
    """`published_by` が `need` 本に届く最初の日。**届かないなら `never`。**

    `published_by` は単調なので、2本の直線それぞれを解いて**遅いほう**を取れば
    厳密です（探索は要りません）。
    """
    if need <= 0:
        return 0.0
    if plan_density <= 0:
        return never
    t_plan = need / plan_density
    if need <= stock:
        t_make = 0.0
    elif rate_per_day <= 0:
        return never
    else:
        t_make = (need - stock) / rate_per_day
    t = max(t_plan, t_make)
    return never if t > never else t


def material_dry_days(*, novel: int | None, rate_per_day: float) -> float | None:
    """掃引の候補を使い切るまでの日数。**その先は新しい表が要ります。**"""
    if novel is None or rate_per_day is None or rate_per_day <= 0:
        return None
    return (novel * SWEEP_YIELD) / rate_per_day


def state(*, stock_n: int | None = None, ps: list[dict] | None = None) -> dict:
    """**予測に渡す1つの塊**（API 0単位。読めなくても例外を出さない）。"""
    ps = points() if ps is None else ps
    r = make_rate(ps)
    sw = sweep_novel()
    try:
        s = stock() if stock_n is None else stock_n
    except Exception:                                          # noqa: BLE001
        last = ps[-1] if ps else {}
        s = int(last.get("stock") or 0)
    return {
        "stock": s,
        "novel": sw.get("novel"),
        "rate_per_day": r["per_day"],
        "rate": r,
        "measured": r["per_day"] is not None,
        "sweep_age_hours": sw.get("age_hours"),
    }
