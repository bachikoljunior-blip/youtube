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

## 2026-08-26 —— **既定の密度を 25 から実測へ移した（最適化の回）**

**上の冒頭は「`eta.py` が 25 を持っている」と書いていますが、`eta.py` は
とっくにそこから離れています。** 段1 は `solve_gate1()` の実測で解いていて、
`_report_supply` は 25 で呼んだうえで
「**上の 25本/日 は詰め方の上限です**」と註を付けて打ち消しています。

**打ち消しが片方にしか無いのが問題でした。** `python -m src.supply` を
単体で撃つと（そしてそれが、最適化の回に「撃て」と名指しされている撃ち方です）、
**その註は1行も出ません。** 出るのは割り算の結果だけです。

**実測（2026-08-26）。** 25 は 2.5倍 外れていました。独立に2つ:

    `day_cap.cap()`            **10本/日**（08/22・08/23・08/25 とも、
                               11本目から先は 0再生）
    予約が実際に減る速さ        **中央値 10本/日**（平均 9.94。
                               328本 / 33日。`queue_lag.scheduled()`）

**この 2.5倍が、どちらへ効くか。** 25 で割ると在庫は
「**1.8日ぶん・08/31 に尽きる**」と出ます。10 で割ると
「**4.5日ぶん・09/08**」です。前者は「**急いで作れ**」と読めます。
**そして「もっと作る」は、この機械では逆向きです** ——
作る速さは実測 13.6本/日、予約が減るのは 10本/日 なので、
**作れば作るほど順番待ちが伸び、`arm_speed` の θ（＝待ちの逆数）が下がります**
（`scripts/queue_lag.py` の冒頭）。**存在しない飢餓が、到達日を押していました。**

**だから既定はもう書き写しません。** `--density` の既定は
`day_cap.cap()` を読みます。25 が要るときは `--density 25` と明示すること
（`lines()` が、どちらを使ったかを毎回 1行目に印字します）。

**覆る条件**: `day_cap.cap()` が上がったら、既定も黙って追随します
（それが狙いです）。**ただし `day_cap` の 10 は「ショートの面」の数**で、
長尺には掛かりません（`day_cap.lines()` がそう言っています）。
**長尺が予約の主になった日には、この既定は過少になります** ——
そのときは予約が減る実速（上の2つ目）と食い違うので、
`queue_lag` の「予約に入っている本 / いちばん後ろ」と突き合わせて測り直すこと。
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
#: 歩留りはさらに低いかもしれない）。
#:
#: ## 2点目（2026-08-20 17:4x）—— **「直せば上がる」は外れました**
#:
#: 上の註は「1（率の格子）を直せば歩留りは上がります」と言っていました。
#: **直して、同じ32枠を測り直したところ 5/32 のままでした。**
#:
#: 直したのは2つ（`calc_axes.RATE_BAND` と `PARAM_FILL` の月額）:
#:
#:     実在しない率を名指しする候補   13件 → **0件**（`social_rate` 0.7〜0.9 ほか）
#:     候補の総数                    964件 → **954件**（新しい 524 → 502）
#:     「不変」                       51件 → 47件 ／ 「頭打ち」 46件 → **52件**
#:
#: **消えたのは分母のほうで、書ける候補は増えていません。** 月額の引数を
#: 年収の桁（3,000,000）で埋めていた6件は、`1,500,000→11,999,999 と動かしても
#: …のまま`という**死んだ「不変」**から、`713,524 から上は 650,000 で止まる`
#: （＝標準報酬月額の上限）という**実在する上限を名指しする「頭打ち」**へ
#: 変わりました。**質は上がったが、件数としては相殺**しています。
#:
#: **いちばんの落ち先は、率ではありませんでした。** 32枠の内訳を数え直すと:
#:
#:     片効き 10件 ＋ 不変 4件 = **14/32（44%）**  ← どれも「Xは Y に依らない」の自明
#:     [並 N点]（道具自身が「書けない」と言っている）  3件
#:     [既]（もう節が言っている）                    6件
#:     書ける                                        5件
#:
#: **覆る条件 / 次に測ること**: `片効き` と `不変` は、いまも他の形と同じ重みで
#: 族の先頭に並びます。**この2つを候補から落とすか、順番を最後に回せば、
#: 族の先頭6件の歩留りは机上で 5/18 ≒ 0.28 まで上がります**（14件が抜けるので）。
#: そこを直したら、また同じ32枠で測り直すこと。**「直せば上がる」を
#: 二度目も信じないこと** —— 上の1回で外れています。
#:
#: ## 2026-08-24 —— **順番のほうを直した。値はまだ動かしていません**
#:
#: 上の「覆る条件」を実行しました。`src/section_sweep.SHAPE_LAST` を足し、
#: **`片効き` と `不変` を族ごとの一覧の最後へ回した**（落とさない ——
#: `不変` は本物の節になったことがあり、落とすと形ごと消えます）。
#:
#: **`SWEEP_YIELD` は 0.156 のままです。** 上の註が「直せば上がる」を
#: 二度目も信じるなと言っているので、**机上の 5/18 ≒ 0.28 を書きません。**
#: 順番を変えても**全体の歩留りは1件も動きません** —— 動くのは
#: 「族の先頭6件を人が読んだときの当たり率」だけで、この定数が掛かるのは
#: 全体の件数のほうです。**次に測り直すときは、同じ32枠を
#: `python -m src.section_sweep --calc <族>` の新しい先頭6件で読むこと。**
#:
#: ## 同じ日に測った、もう1つの幅 —— **「新しい」の36%は分かっていません**
#:
#: `section_sweep.undecided()` を足して数えたところ:
#:
#:     候補 1,059件 ／ 既出 491 ／ **新しい 568**
#:     そのうち **203件（36%）は「印字されていないと分かった」のではなく
#:     「照合できる点が無い」** —— 不変79・頭打ち48・逆転34・片効き24・崖9・帯9
#:
#: 理由は `_LONE_NUMBER_MIN`（1000）です。結果が **1000未満の裸の数**しか
#: 持たない候補（倍率・年齢・パーセント）は `_point_printed` が `None` を返し、
#: `is_covered` はそこで `False` ＝「まだ誰も言っていない」を返します。
#: 実例: `nenkin.birth_gap_ratio … 1.25 のまま` は「新しい」と出るのに、
#: 節は「0.5% ÷ 0.4% ＝ 1.25倍で、1か月でも60か月でも同じです」と印字済み。
#: **`--calc nenkin` は 16件が16件とも「判定できていない」**でした。
#:
#: **この 203件を、ここでは引いていません。** 引かない理由は1つ:
#: **上の 0.156 は、その 568件を分母にして目で読んだ数**だからです。
#: 分子（書ける5件）は分母の作り方を知りません —— 分母だけ 363件に縮めると、
#: **同じ標本から取った比を、別の分母に掛ける**ことになります。
#: **引くなら、引いた分母で 32枠を読み直してから。**
#: 一覧には `[未]` の印と件数が出ます（黙って在庫に積まないため）。
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
            # 古くても、無いよりは読める。**年齢を添えて返す**（黙って捨てない）
            return {"novel": point["sweep_novel"], "total": point.get("sweep_total"),
                    "undecided": point.get("sweep_undecided"),
                    "at": point.get("at"), "age_hours": age}
        return {"novel": None, "total": None, "undecided": None,
                "at": None, "age_hours": None}

    from src import section_sweep as ss

    hits = ss.sweep_all()
    sections = _all_sections()
    total_by, novel_by = ss.novel_counts(hits, sections)
    # **「新しい」の中身を割ること**（2026-08-24。`SWEEP_YIELD` の註）。
    # 「印字されていないと分かった」と「照合できる点が無い」は別のものです。
    und = sum(1 for h in ss.dedupe(hits)
              if ss.undecided(h, (sections or {}).get(h.get("表", "?"))))
    return {"novel": sum(novel_by.values()), "total": sum(total_by.values()),
            "undecided": und,
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
           run_minutes: float = 60.0, today: date | None = None,
           undecided: int | None = None, density_source: str = "") -> dict:
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
        "density_source": density_source,
        "stock": s,
        "sweep_novel": novel,
        "sweep_undecided": undecided,
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


def surfaces(long_min_s: float = 180.0) -> dict:
    """**面べつの滑走路**（長尺／ショート）。API 0単位・控えだけを読みます。

    ## なぜ要るか（2026-08-27 に測って足した）

    上の `supply()` は在庫を **`day_cap.cap()`（＝ショートの 10本/日）**で割ります。
    そして「**足ります**」と印字します。**その面は天井です** ——
    `eta.py` の `density_surfaces` が実測でこう言っています:

        ショート  at_ceiling=True  measured=True   （超えたぶんは 0再生）
        長尺      at_ceiling=False measured=False  （崩れる所を一度も見ていない）

    そして **4,000時間の門に入るのは長尺だけ**です（`src/levers.py` /
    `src/day_cap.py` / `src/verify.py` / `scripts/batch_build.py` が同じことを
    書いています。実測 08/26・直近28日: `SHORTS_FEED` 64,283再生 ／
    `WATCH` **67再生**）。

    **つまり「足ります」は、いま開いている唯一の門とは別の面についての合格でした。**
    実測（2026-08-27・控えを畳んで数えた）:

        長尺の予約    36本  08/28〜09/04 の **8日**（09/05 以降は **0本**）
        ショートの予約 347本  10/12 まで ＝ **46日**

    **6倍 ちがいます。そして長い側が、門に1分も積まない面です。**

    ## この道具が言えないこと

    ここが数えるのは**予約に入っている本**だけです。長尺を何本 作れるかは
    `scripts/topic_forge.py --list` の「7日ぶんで取れるのは最大 N本」
    （族 × `--per-calc`）。**そちらが本当の天井**で、ここは滑走路の残りです。

    ## 覆る条件

    長尺の面が天井に当たったら（`day_cap.long_form()['collapsed']`）、
    「長い側が短い」は「詰め方が悪い」ではなく「その面が満杯」になります。
    そのときは本数ではなく**面そのもの**を疑うこと。
    """
    import json as _json

    from . import config, dupes

    dur: dict[str, float] = {}
    path = config.ROOT / "data" / "uploaded.jsonl"
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = _json.loads(line)
                dur[row.get("video_id")] = float(row.get("duration_s") or 0)
    except OSError:
        return {}

    today = today_jst()
    days: dict[str, set] = {"long": set(), "short": set()}
    n = {"long": 0, "short": 0}
    for row in dupes.ledger_rows():
        at = row.get("at")
        if not at:
            continue
        try:
            when = datetime.fromisoformat(str(at).replace("Z", "+00:00")).astimezone(JST)
        except (TypeError, ValueError):
            continue
        if when.date() < today:
            continue
        key = "long" if dur.get(row.get("id"), 0.0) >= long_min_s else "short"
        n[key] += 1
        days[key].add(when.date())

    out = {}
    for key in ("long", "short"):
        last = max(days[key]) if days[key] else None
        out[key] = {"booked": n[key], "last": last,
                    "runway_days": (last - today).days + 1 if last else 0}
    # **長尺の在庫は `s-` で始まらない題**（`batch_build.pick` の「長尺は長尺向けに
    # 書かれた題からしか取らない」と同じ数え方。片方だけ直すとずれます）。
    try:
        pool = config.load_topics()["topics"]
        used = {r["topic"] for r in dupes.ledger_rows() if r.get("topic")}
        out["long"]["stock"] = sum(
            1 for t in pool
            if t.get("id") not in used and t.get("calc")
            and not str(t.get("id", "")).startswith("s-"))
    except Exception:                                          # noqa: BLE001
        out["long"]["stock"] = None
    return out


def surface_lines(su: dict | None = None) -> list[str]:
    """`surfaces()` を読む行。**数字だけ。判断は書かない。**"""
    su = surfaces() if su is None else su
    if not su:
        return []
    lo, sh = su.get("long", {}), su.get("short", {})
    L = ["--- **4,000時間の門に入るのは長尺だけです。その面だけを別に数えます** ---"]
    L.append(f"    長尺の予約                  {lo.get('booked', 0):>6,} 本"
             f"  ＝ **{lo.get('runway_days', 0)}日ぶん**"
             + (f"（最後は {lo['last']:%m/%d}）" if lo.get("last") else "（**0本**）"))
    if lo.get("stock") is not None:
        L.append(f"    長尺向けの在庫              {lo['stock']:>6,} 本"
                 "  （`s-` で始まらない題。**天井は `topic_forge --list` の"
                 "「7日ぶんで取れるのは最大 N本」**）")
    L.append(f"    ショートの予約              {sh.get('booked', 0):>6,} 本"
             f"  ＝ **{sh.get('runway_days', 0)}日ぶん**"
             + (f"（最後は {sh['last']:%m/%d}）" if sh.get("last") else ""))
    a, b = lo.get("runway_days", 0), sh.get("runway_days", 0)
    if b > a:
        L.append(f"    → **短いのは長尺の側です（{a}日 対 {b}日）。**"
                 " ショートの面は天井（`eta.py` の `density_surfaces`）なので、"
                 "**そこを伸ばしても門は1分も動きません**")
    elif a and b:
        L.append(f"    → 長尺の側のほうが長い（{a}日 対 {b}日）。"
                 "**この向きなら、律速は滑走路ではありません**")
    return L


def lines(sp: dict) -> list[str]:
    """`eta.py` が印字する行。**数字だけ。判断は書かない。**"""
    L: list[str] = []
    src_note = f"・{sp['density_source']}" if sp.get("density_source") else ""
    L.append(f"--- **その密度（{sp['density']:g}本/日{src_note}）を、在庫が支えられるか** ---")
    if not sp["measured"]:
        L.append("    掃引の余地を**一度も測っていません**（`python -m src.supply --measure` で1点入ります）。")
    L.append(f"    未投稿のテーマ（在庫）      {sp['stock']:>6,} 本"
             f"  ＝ **{sp['stock'] / sp['density']:.1f}日ぶん**"
             if sp["density"] > 0 else f"    未投稿のテーマ（在庫） {sp['stock']:,} 本")
    if sp["sweep_novel"] is not None:
        L.append(f"    まだ節が言っていない候補    {sp['sweep_novel']:>6,} 件"
                 f"  （`src.section_sweep`。**節そのものではない ＝ 上限側**）")
        # **黙って在庫に積まないこと**（2026-08-24。`SWEEP_YIELD` の註）。
        # この件数は「印字されていないと分かった」ものと「照合できる点が無い」
        # ものの合計です。後者は結果が1000未満の裸の数だけを持つ候補で、
        # **本文に書いてあっても必ずここへ入ります。**
        und = sp.get("sweep_undecided")
        if und:
            pct = 100.0 * und / sp["sweep_novel"] if sp["sweep_novel"] else 0.0
            L.append(f"      うち **判定できていない**       {und:>6,} 件"
                     f"  （{pct:.0f}%。照合できる点が無いだけで、"
                     f"**無いと分かったのではない**）")
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
    p.add_argument("--density", type=int, default=None,
                   help="1日に公開する本数。**既定は `src/day_cap.py` の実測**"
                        "（べた書きしないこと。下の註を読むこと）")
    p.add_argument("--horizon", type=float, default=None, help="到達予測までの日数")
    p.add_argument("--run-minutes", type=float, default=60.0,
                   help="1周の間隔（分）。`quota.py --pace` の「持続できる間隔」")
    p.add_argument("--measure", action="store_true",
                   help="掃引をやり直して1点積む（約47秒）")
    p.add_argument("--record", action="store_true",
                   help="掃引はやり直さず、在庫とテーマ総数だけ1点積む（1秒未満）。"
                        "**作る速さ（make_rate）は点の差からしか出ません**")
    args = p.parse_args()

    # **既定の密度は、書き写さずに測ったものを読むこと**（2026-08-26）。
    # ここは長らく `default=25` でした。理由は下の 2026-08-26 の註にあります。
    if args.density is None:
        from src import day_cap
        density = day_cap.cap()
        density_source = "実測 `src/day_cap.py`"
    else:
        density = args.density
        density_source = "`--density` で指定"

    sw = sweep_novel(compute=args.measure)
    s = stock()
    if args.measure or args.record:
        record({"at": sw["at"] if args.measure else None, "stock": s,
                "topics_total": topics_total(),
                "sweep_total": sw["total"], "sweep_novel": sw["novel"],
                "sweep_undecided": sw.get("undecided")})
        print(f"[supply] 積みました: {CACHE}")
    elif sw["age_hours"] is not None:
        print(f"[supply] 掃引の点は {sw['age_hours']:.1f}時間前のものです"
              f"（測り直しは --measure）")

    sp = supply(density, stock_n=s, novel=sw["novel"],
                undecided=sw.get("undecided"), horizon_days=args.horizon,
                run_minutes=args.run_minutes, density_source=density_source)
    for line in lines(sp):
        print(line)
    # **上の「足ります」は、ショートの密度で割った答えです**（`surfaces()` の註）。
    #     門はショートでは開かないので、面べつも必ず並べて出すこと。
    try:
        for line in surface_lines():
            print(line)
    except Exception as exc:                                   # noqa: BLE001
        print(f"    （面べつは出せませんでした: {str(exc)[:80]}）")


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

#: **この時間より短い窓の速さを「持続する速さ」と呼ばないこと。**
#:
#: 2026-08-20 20:0x に実測で踏みました。`data/supply.jsonl` の点は
#: **3.3時間で +5本**しかなく、そこから割ると **1日 36.5本**が出ます。
#: この数は `min(25, 36.5) = 25` を通して `density_month` に入り、
#: **オーナーが同じ日に「物理的に不可なら予測に使うな」と言って外させた 25 が、
#: 別の入口から戻っていました**（`data/eta.jsonl` 18:1x の点 0.0 → 最新 25.0。
#: 到達予測が 306日 → 100日 に縮んだ大半がこれです）。
#:
#: 36.5本/日 は「節をまとめて書いた3時間」の**瞬間の速さ**であって、
#: 1か月続く速さではありません。**在庫は26本**なので、25本/日 なら1日で尽きます。
#: 段4（月20万）が数えるのは**収益化の後の30日ぶん**——在庫を食い終わった
#: ずっと先なので、そこに置いてよいのは「1日続けられる速さ」だけです。
#:
#: **覆る条件**: `data/supply.jsonl` に 24時間 をまたぐ点が貯まれば、
#: `make_rate` がそのまま `sustained` を名乗ります（下の `state`）。
#: **測るほど、この迂回は自動で外れます。**
MIN_SUSTAINED_HOURS = 24.0


def make_rate(ps: list[dict] | None = None,
              min_hours: float = MIN_RATE_HOURS) -> dict:
    """**テーマが1日に何本増えているか。実測。**

    返り: `{"per_day": float|None, "hours": float, "delta": int, "n": int,
            "thin": bool}`

    - `per_day` が `None` なら「**まだ測っていない**」。0 と取り違えないこと
      （0 は「増えていない」という別の意味です）
    - `thin` は「窓が 6時間 未満」＝ 1本の増減で桁が動く帯。
      **数は返しますが、断りを付けて印字すること**
    - `sustained` は「窓が 24時間 以上」＝ **1日続く速さとして使ってよい**か。
      `False` の数を `density_month` に入れないこと（`MIN_SUSTAINED_HOURS`）
    - `basis` は出どころ（`created_series`）。**物差しが切り替わった回は、
      その差を「速くなった」と読まないこと**
    """
    s, basis = created_series(ps)
    if len(s) < 2:
        return {"per_day": None, "hours": 0.0, "delta": 0, "n": len(s),
                "thin": True, "sustained": False, "basis": basis}
    (t0, v0), (t1, v1) = s[0], s[-1]
    hours = (t1 - t0).total_seconds() / 3600.0
    if hours < min_hours:
        return {"per_day": None, "hours": hours, "delta": v1 - v0,
                "n": len(s), "thin": True, "sustained": False, "basis": basis}
    return {"per_day": (v1 - v0) / (hours / 24.0), "hours": hours,
            "delta": v1 - v0, "n": len(s), "thin": hours < 6.0,
            "sustained": hours >= MIN_SUSTAINED_HOURS, "basis": basis}


def published_rate(rows: list[dict] | None = None,
                   today: date | None = None) -> dict:
    """**実際に公開になった本数／日**（`data/uploaded.jsonl` の `at`）。

    返り: `{"per_day": float|None, "days": int, "n": int, "first": date|None,
            "last": date|None}`

    `make_rate`（テーマが増える速さ）と何がちがうか —— こちらは
    **出口の実測**です。テーマを何本書いても、公開になった本数がそれを
    下回っていれば、収益の窓（30日）で数えてよいのは下回ったほうです。

    **数えるのは、終わった日だけ**（今日は途中なので入れません）。
    公開が1本も無かった日も分母に入れます —— 落とすと「出した日だけの速さ」
    になり、**止まっていた日を無かったことにします。**

    2026-08-20 の実測: 08/16 4本・08/17 1本・08/18 1本・08/19 8本
    → **3.5本/日**。同じ日の `make_rate` は 36.5本/日（窓 3.3時間）でした。
    """
    if rows is None:
        rows = _ledger_rows()
    today = today_jst() if today is None else today
    days: dict[date, int] = {}
    for r in rows:
        v = r.get("at")
        if not v or str(v) == "None":
            continue
        try:
            t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except ValueError:
            continue
        if t.tzinfo is None:
            t = t.replace(tzinfo=JST)
        d = t.astimezone(JST).date()
        if d >= today:          # 今日は途中。**未来の予約も入れない**
            continue
        days[d] = days.get(d, 0) + 1
    if not days:
        return {"per_day": None, "days": 0, "n": 0, "first": None, "last": None}
    first, last = min(days), max(days)
    # **末尾の沈黙も分母に入れます**（2026-08-27 夜・最適化の回）。
    #
    # ここは `max(days)`（＝**最後に1本でも公開した日**）で割っていました。
    # 上の docstring は「公開が1本も無かった日も分母に入れます —— 落とすと
    # **止まっていた日を無かったことにします**」と書いていますが、
    # **入っていたのは内側の 0本 の日だけ**で、**末尾は落ちていました。**
    #
    # つまり**公開が今日ぱったり止まっても、この数は1ミリも下がりません** ——
    # `last` が動かなくなるだけです。`state()` はこれを「1日 続けられる速さ」
    # として `density_month` に渡すので、**投稿が途切れた回ほど、供給の見通しが
    # 正しく見える**ことになります。`CLAUDE.md`「投稿が途切れるのが最大の損失」の、
    # ちょうどそのときに黙る計器でした。
    #
    # 実測 2026-08-27: `last` は 08/26（＝終わった最後の日）なので、
    # **この直しで今日の数は1つも動きません**（13.18本/日 のまま）。
    # 直したのは、**止まったときに下がるかどうか**です。
    #
    # **覆る条件**: 「意図して出さない日」を持つようになったら
    # （例: 対照日を空ける実験）、その日を分母から除く欄が要ります。
    # いまはそういう日が1つも無いので、**沈黙は全部 事故**として数えます。
    last = max(last, today - timedelta(days=1))
    span = (last - first).days + 1
    n = sum(days.values())
    return {"per_day": n / span, "days": span, "n": n,
            "first": first, "last": last}


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
    pr = published_rate()
    sw = sweep_novel()
    try:
        s = stock() if stock_n is None else stock_n
    except Exception:                                          # noqa: BLE001
        last = ps[-1] if ps else {}
        s = int(last.get("stock") or 0)

    # --- **1日続けられる速さ**（`density_month` に入ってよい唯一の数）---
    #     `make_rate` は窓が 24時間 をまたいで初めてここを名乗れます。
    #     またいでいない回は、**出口の実測**（実際に公開になった本数／日）に
    #     落とします —— そちらは何日ぶんもの窓で測れているので、
    #     「3時間のバースト」を1か月の速さとして印字せずに済みます。
    if r["per_day"] is not None and r.get("sustained"):
        sustained, basis = r["per_day"], f"作る速さ（{r['hours']:.1f}時間の実測）"
    elif pr["per_day"] is not None:
        sustained, basis = pr["per_day"], f"実際に公開になった本数（{pr['days']}日の実測）"
    else:
        sustained, basis = None, None

    return {
        "stock": s,
        "novel": sw.get("novel"),
        "rate_per_day": r["per_day"],
        "rate": r,
        "published": pr,
        # **在庫を食い終わった先の密度は、こちらしか使わないこと**
        "sustained_rate_per_day": sustained,
        "sustained_basis": basis,
        "measured": r["per_day"] is not None,
        "sweep_age_hours": sw.get("age_hours"),
    }
