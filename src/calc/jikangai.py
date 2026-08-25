"""**「月100時間未満」は、2か月続けて置けない。3か月なら合計240時間が上限。**

一般の解説はここで止まります ——「特別条項をつければ、年720時間まで。
単月は100時間未満、複数月の平均は80時間以内、月45時間を超えられるのは年6回まで」。

**4つの数字が並んでいるだけでは、どれが先に効くかが分かりません。**
実際にはこの4つは互いを潰し合っていて、**「月100時間未満」が単独で成り立つ月は、
1年に何回あっても、前後の月を削らないと置けません。**

- 2か月平均80時間 ＝ **隣り合う2か月の合計が160時間**。
  99時間を置いたら、**翌月は61時間が上限**です。99時間を2か月続けることはできません。
- 繁忙期を3か月と見るなら、置ける上限は **240時間**（80×3）。
  「月100時間未満」から素直に足した297時間とは、**57時間ちがいます。**
- 年720時間を上限まで使うには、**45時間以下の6か月にも合計126時間が要ります。**
  6回ぶんを99時間で埋めても594時間にしかならないので、
  **「忙しい6か月だけで年720時間」は算術的に不可能です。**

**そして、特別条項をつけない年も同じ形をしています**（2026-08-18 に足した）。
「月45時間・年360時間」も並べて説明されますが、**同時には成り立ちません** ——
月45時間を12か月続けると年540時間で、年の上限を **180時間** こえます。
**上限まで置ける月は8か月まで**（45×8＝360）。年360時間を12か月でならすと
**月30.0時間**で、これは月の上限45時間の **66.6667%** にすぎません。
特別条項をつけると月の上限は45→99時間の **2.2000倍** に伸びますが、
年ならしは30→60時間の **2.0000倍** どまりです。**同じ倍率ではありません。**

## この計算で見ないもの（前提として画面に出す）

- 休日労働は入れていません。単月100時間未満と複数月平均80時間は
  **休日労働を含めて**判定するので、休日労働がある月は、ここより早く上限に当たります。
- 建設業・自動車運転・医師などの適用除外や猶予は入れていません。
- 「複数月平均」は前年から続けて見ますが、ここでは**その年の12か月だけ**で見ています。
"""
from __future__ import annotations

from itertools import combinations

from . import _checks

ASSUMPTIONS = [
    "休日労働はゼロとして計算しています。単月100時間未満と複数月平均80時間は休日労働を含めて判定するので、休日労働がある月はここより早く上限に当たります",
    "労働基準法36条の一般則です。建設業や自動車の運転、医師などの適用除外や猶予は入れていません",
    "1年単位の変形労働時間制ではない場合の数字です。その制度だと原則は月42時間、年320時間になります",
    "複数月の平均は前の年から続けて見ますが、ここでは1年を12か月で区切って見ています",
    "月45時間を超えられるのは年6回までという制限は、その年に何回使ったかで数えています",
    "時間は1時間きざみで置いています。分の端数は入れていません",
]

# ---- 制度の値。労働基準法36条3項〜6項。2019年4月（中小企業は2020年4月）から不変 ----
LIMIT_MONTH_PLAIN = 45      # 原則の月の上限（36条4項）
LIMIT_YEAR_PLAIN = 360      # 原則の年の上限（36条4項）
LIMIT_YEAR_SPECIAL = 720    # 特別条項をつけたときの年の上限（36条5項）
MONTH_HARD = 100            # 単月の上限。**未満**なので置ける最大は99（36条6項2号）
MULTI_MONTH_AVG = 80        # 2〜6か月の平均の上限（36条6項3号）
MULTI_MONTH_SPAN = (2, 3, 4, 5, 6)
SPECIAL_MONTHS_MAX = 6      # 月45時間を超えられる回数（36条5項）
MONTHS = 12

MONTH_MAX = MONTH_HARD - 1  # 100時間「未満」＝ 1時間きざみなら 99


def violations(schedule: list[int]) -> list[str]:
    """月べつの残業時間の並びが、上限規制のどこに当たるかを全部返す。

    **空のリストが返れば、その置き方は通ります。** 1つでも返れば置けません。
    """
    out: list[str] = []
    if len(schedule) != MONTHS:
        raise ValueError(f"12か月ぶんで渡すこと: {len(schedule)}")

    total = sum(schedule)
    if total > LIMIT_YEAR_SPECIAL:
        out.append(f"年の合計 {total}時間 が {LIMIT_YEAR_SPECIAL}時間 を超えている")
    for i, h in enumerate(schedule, 1):
        if h >= MONTH_HARD:
            out.append(f"{i}月 {h}時間 が単月{MONTH_HARD}時間未満に収まっていない")
    over = [i for i, h in enumerate(schedule, 1) if h > LIMIT_MONTH_PLAIN]
    if len(over) > SPECIAL_MONTHS_MAX:
        out.append(f"月{LIMIT_MONTH_PLAIN}時間を超えた月が {len(over)}回。"
                   f"{SPECIAL_MONTHS_MAX}回まで")
    for span in MULTI_MONTH_SPAN:
        for start in range(MONTHS - span + 1):
            window = schedule[start:start + span]
            if sum(window) > MULTI_MONTH_AVG * span:
                out.append(f"{start + 1}月からの{span}か月平均が "
                           f"{sum(window) / span:.1f}時間（上限{MULTI_MONTH_AVG}時間）")
    return out


def window_caps() -> list[dict]:
    """連続する n か月に置ける合計の上限。**「月100時間未満」から足した値との差。**

    **n は 1〜6 と 12 だけです。** 複数月平均の規制がかかるのは
    2〜6か月なので（36条6項3号）、**7〜11か月の上限は条文から直接は出ません。**
    6か月ぶんの480時間に7か月目の99時間を足した579時間より小さいことは言えても、
    そこから先は探索で詰めるしかないので、**言えない範囲は表に出しません。**
    12か月は年の上限そのもの（36条5項）なので確かです。
    """
    out: list[dict] = []
    for n in (1, 2, 3, 4, 5, 6, MONTHS):
        if n == 1:
            cap = MONTH_MAX
        elif n in MULTI_MONTH_SPAN:
            cap = MULTI_MONTH_AVG * n
        else:
            cap = LIMIT_YEAR_SPECIAL
        naive = MONTH_MAX * n
        out.append({
            "か月": n,
            "実際の上限": cap,
            "月99時間で足した値": naive,
            "差": naive - cap,
            "月あたり": cap / n,
        })
    return out


def next_month_cap(this_month: int) -> int:
    """ある月に `this_month` 時間置いたとき、翌月に置ける上限。

    **2か月平均80時間 ＝ 隣り合う2か月の合計160時間**。ここから引くだけです。
    """
    if this_month > MONTH_MAX:
        raise ValueError(f"{this_month}時間は単月の上限を超えている")
    return min(MONTH_MAX, MULTI_MONTH_AVG * 2 - this_month)


def peak_pairs() -> list[dict]:
    """繁忙月に置いた時間ごとの、翌月の上限と2か月の合計。"""
    return [{"繁忙月": h, "翌月の上限": next_month_cap(h),
             "2か月の合計": h + next_month_cap(h)}
            for h in (99, 90, 80, 70, 60, 45)]


def quiet_months_floor() -> dict:
    """年720時間を使い切るとき、**45時間以下の6か月**が負う最低の合計。

    月45時間を超えられるのは6回まで、その6回も1回99時間が上限なので、
    **6回ぶんで運べるのは594時間**。残りは、ふつうの月が持つしかありません。
    """
    ceiling_from_special = SPECIAL_MONTHS_MAX * MONTH_MAX
    floor = LIMIT_YEAR_SPECIAL - ceiling_from_special
    quiet = MONTHS - SPECIAL_MONTHS_MAX
    return {
        "年の上限": LIMIT_YEAR_SPECIAL,
        "45時間超の月で運べる最大": ceiling_from_special,
        "ふつうの月が負う最低": floor,
        "ふつうの月の数": quiet,
        "1か月あたり": floor / quiet,
    }


def extreme_schedule() -> list[int]:
    """「99時間を6回」を置いたときの、年720時間ぴったりの並び。

    99時間どうしは隣り合えない（2か月合計160時間）ので、**1か月おき**に置きます。
    残りの6か月は `quiet_months_floor()` が出した最低の合計をならしたものです。
    """
    floor = quiet_months_floor()
    low = floor["ふつうの月が負う最低"] // floor["ふつうの月の数"]
    rest = floor["ふつうの月が負う最低"] - low * floor["ふつうの月の数"]
    out: list[int] = []
    for i in range(MONTHS):
        if i % 2 == 0:
            out.append(MONTH_MAX)
        else:
            out.append(low + (1 if rest > 0 else 0))
            rest -= 1
    return out


def flat_schedule() -> list[int]:
    """同じ年720時間を、**凸凹を最小にして**置いた並び（6か月75時間・6か月45時間）。"""
    high = (LIMIT_YEAR_SPECIAL - LIMIT_MONTH_PLAIN * 6) // 6
    return [high if i % 2 == 0 else LIMIT_MONTH_PLAIN for i in range(MONTHS)]


def concentrated_max(months: int) -> int:
    """繁忙期を `months` か月と決めたとき、そこに置ける合計の最大。"""
    return next(r["実際の上限"] for r in window_caps() if r["か月"] == months)


def busy_season_shortfall() -> list[dict]:
    """「繁忙期に集中させたい」時間と、実際に置ける上限の差。"""
    out = []
    for n in (1, 2, 3, 4, 5, 6):
        cap = concentrated_max(n)
        out.append({
            "繁忙期の長さ": n,
            "置ける上限": cap,
            "月100時間未満から足した値": MONTH_MAX * n,
            "足りない分": MONTH_MAX * n - cap,
            "年720時間のうち残る分": LIMIT_YEAR_SPECIAL - cap,
        })
    return out


def plain_year_grid() -> list[dict]:
    """**特別条項をつけない年**に、月45時間を何か月置けるか（2026-08-18 に足した）。

    `LIMIT_YEAR_PLAIN`（原則の年360時間）は、**この表のどの節も一度も
    印字していませんでした。** 5節は全部、特別条項をつけた側
    （720・100・80・6回）の話です。**原則の側は、定数として書いてあるのに
    画面に一度も出ていない**ので、ここで出します。

    「月45時間・年360時間」は並べて説明されますが、**同時には成り立ちません** ——
    月45時間を12か月続けると年540時間で、年の上限を180時間こえます。
    **上限まで置けるのは8か月まで**（45×8＝360）。
    """
    out = []
    for n in range(MONTHS + 1):
        total = LIMIT_MONTH_PLAIN * n
        out.append({
            "45時間の月数": n,
            "年の合計": total,
            "年360時間との差": total - LIMIT_YEAR_PLAIN,
            "通るか": total <= LIMIT_YEAR_PLAIN,
        })
    return out


def plain_vs_special() -> dict:
    """原則と特別条項を、**月の上限と年ならしの2つで**比べる。

    **伸び方が同じではありません** —— 月の上限は45→99時間で 2.2倍ですが、
    年をならした1か月あたりは 30→60時間で **2.0倍**にしかなりません。
    """
    return {
        "原則の月上限": LIMIT_MONTH_PLAIN,
        "特別条項の月上限": MONTH_MAX,
        "月上限の倍率": MONTH_MAX / LIMIT_MONTH_PLAIN,
        "原則の年上限": LIMIT_YEAR_PLAIN,
        "特別条項の年上限": LIMIT_YEAR_SPECIAL,
        "年上限の倍率": LIMIT_YEAR_SPECIAL / LIMIT_YEAR_PLAIN,
        "原則の月ならし": LIMIT_YEAR_PLAIN / MONTHS,
        "特別条項の月ならし": LIMIT_YEAR_SPECIAL / MONTHS,
        "月ならしの倍率": LIMIT_YEAR_SPECIAL / LIMIT_YEAR_PLAIN,
        "原則の月ならしが月上限に占める割合": LIMIT_YEAR_PLAIN / MONTHS / LIMIT_MONTH_PLAIN,
    }


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。**壊れた数字で台本を書かせない。**"""
    # 1. 法令が名指ししている値
    _checks.statutory(LIMIT_MONTH_PLAIN, 45, "原則の月の上限", source="労働基準法36条4項")
    _checks.statutory(LIMIT_YEAR_PLAIN, 360, "原則の年の上限", source="労働基準法36条4項")
    _checks.statutory(LIMIT_YEAR_SPECIAL, 720, "特別条項の年の上限", source="労働基準法36条5項")
    _checks.statutory(MONTH_HARD, 100, "単月の上限", source="労働基準法36条6項2号")
    _checks.statutory(MULTI_MONTH_AVG, 80, "複数月平均の上限", source="労働基準法36条6項3号")
    _checks.statutory(SPECIAL_MONTHS_MAX, 6, "月45時間を超えられる回数", source="労働基準法36条5項")

    # 2. 数字どうしの大小（写し間違いで入れ替わると、主題が反転する）
    _checks.greater(LIMIT_YEAR_SPECIAL, LIMIT_YEAR_PLAIN, "特別条項の年上限が原則の年上限")
    _checks.greater(MONTH_HARD, MULTI_MONTH_AVG, "単月の上限が複数月平均の上限")
    _checks.greater(MULTI_MONTH_AVG, LIMIT_MONTH_PLAIN, "複数月平均の上限が原則の月上限")

    # 3. 判定そのものが働くこと。**通らない並びを通したら、この動画は嘘になります**
    if violations([MONTH_MAX] * 2 + [0] * 10):
        pass
    else:
        raise _checks.TableError("99時間を2か月続けた並びが通ってしまった（2か月平均80時間）")
    if not violations([60] * MONTHS):
        raise _checks.TableError("月60時間×12か月＝720時間だが、45時間超が12回。通してはいけない")
    if not violations([MONTH_HARD] + [0] * 11):
        raise _checks.TableError("単月100時間ちょうどを通してはいけない（『未満』）")

    # 4. 構成した並びは、実際に全部の条件を通ること（**主題の裏づけ**）
    for name, sched in (("凸凹を最大にした並び", extreme_schedule()),
                        ("凸凹を最小にした並び", flat_schedule())):
        bad = violations(sched)
        if bad:
            raise _checks.TableError(f"{name} が通らない: {bad}")
        _checks.rounding(sum(sched), LIMIT_YEAR_SPECIAL, f"{name} の年の合計")

    # 5. 計算の向き —— この計算の主題そのもの
    #    (a) 繁忙月を厚くするほど、翌月に置ける時間は減る。
    #        **ただし当月61時間までは、翌月は単月の上限99時間で頭打ちのまま**
    #        （160 − 61 = 99）。ここを「減っていない」と読むと表の意味が反転するので、
    #        頭打ちの側と、効き始めてからの側を分けて確かめます
    for h in (0, 45, 61):
        _checks.rounding(next_month_cap(h), MONTH_MAX,
                         f"当月{h}時間のときの翌月の上限（まだ単月の上限で頭打ち）")
    _checks.decreases_with(next_month_cap, (62, 70, 80, 90, 99),
                           "繁忙月を厚くしたのに、翌月の上限が減っていない")
    _checks.rounding(next_month_cap(MONTH_MAX), 61, "99時間の翌月の上限")
    #    (b) 窓が長くなるほど、置ける合計は減らない／月あたりは増えない
    caps = {r["か月"]: r for r in window_caps()}
    _checks.never_decreases(lambda n: caps[n]["実際の上限"], sorted(caps),
                            "窓を延ばしたのに、置ける合計が減っている")
    _checks.decreases_with(lambda n: caps[n]["月あたり"], (1, 2, MONTHS),
                           "窓を延ばしたのに、1か月あたりの上限が増えている")
    #    (c) **主題**: 3か月の上限は240時間で、月99時間から足した297時間とは57時間ちがう
    _checks.rounding(concentrated_max(3), 240, "3か月に置ける合計の上限")
    _checks.rounding(MONTH_MAX * 3 - concentrated_max(3), 57, "3か月ぶんの差")
    #    (d) **主題**: 忙しい6か月だけでは年720時間に届かない
    floor = quiet_months_floor()
    _checks.greater(floor["ふつうの月が負う最低"], 0,
                    "ふつうの月が負う最低が0（忙しい月だけで年上限まで届いてしまう）")
    #    (d2) **主題（2026-08-18 に足した節）**: 原則の月45時間と年360時間は同時に成り立たない
    grid = {r["45時間の月数"]: r for r in plain_year_grid()}
    _checks.rounding(grid[MONTHS]["年の合計"], 540, "月45時間を12か月置いた年の合計")
    _checks.rounding(grid[MONTHS]["年360時間との差"], 180, "12か月続けたときのはみ出し")
    _checks.rounding(grid[8]["年の合計"], LIMIT_YEAR_PLAIN, "45時間を8か月置いた年の合計")
    if not grid[8]["通るか"]:
        raise _checks.TableError("45時間×8か月＝360時間は原則の年上限ちょうどで、通らねばならない")
    if grid[9]["通るか"]:
        raise _checks.TableError("45時間×9か月＝405時間が原則の年上限を通ってしまった")
    _checks.never_decreases(lambda n: grid[n]["年の合計"], sorted(grid),
                            "45時間の月数を増やしたのに、年の合計が減っている")
    #    (d3) **主題**: 伸び方が月の上限と年ならしで違う（2.2倍と2.0倍）
    v = plain_vs_special()
    _checks.rounding(v["月上限の倍率"], 2.2, "月の上限の倍率（45→99時間）")
    _checks.rounding(v["月ならしの倍率"], 2.0, "年をならした1か月あたりの倍率（30→60時間）")
    _checks.greater(v["月上限の倍率"], v["月ならしの倍率"],
                    "月の上限の倍率が、年ならしの倍率")
    _checks.rounding(v["原則の月ならし"], 30, "原則の年上限を12か月でならした値")
    _checks.rounding(v["特別条項の月ならし"], 60, "特別条項の年上限を12か月でならした値")
    #    (e) 99時間を隣り合わせに置ける組み合わせは1つも無いこと
    for a, b in combinations(range(MONTHS), 2):
        if b - a == 1:
            sched = [0] * MONTHS
            sched[a] = sched[b] = MONTH_MAX
            if not violations(sched):
                raise _checks.TableError(f"{a + 1}月と{b + 1}月に99時間を並べた形が通った")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 繁忙期に置ける合計は「月100時間未満」から足した値にならない ===")
    for row in busy_season_shortfall():
        print(f"  繁忙期{row['繁忙期の長さ']}か月  置ける上限 {row['置ける上限']:>4}時間"
              f"  月99時間で足すと {row['月100時間未満から足した値']:>4}時間"
              f"  差 {row['足りない分']:>3}時間")

    print("\n=== 99時間を置いた翌月の上限（2か月の合計は160時間） ===")
    for row in peak_pairs():
        print(f"  繁忙月 {row['繁忙月']:>3}時間 → 翌月 {row['翌月の上限']:>3}時間"
              f"（2か月で {row['2か月の合計']:>3}時間）")

    print("\n=== 年720時間を使い切るには、ふつうの月にも残業が要る ===")
    f = quiet_months_floor()
    print(f"  年の上限                    {f['年の上限']:>4}時間")
    print(f"  45時間超の6か月で運べる最大  {f['45時間超の月で運べる最大']:>4}時間"
          f"（99時間×{SPECIAL_MONTHS_MAX}回）")
    print(f"  ふつうの6か月が負う最低      {f['ふつうの月が負う最低']:>4}時間"
          f"（月{f['1か月あたり']:.0f}時間）")

    print("\n=== 年720時間ぴったりの置き方を2通り（どちらも全条件を通る） ===")
    for name, sched in (("凸凹を最大に", extreme_schedule()),
                        ("凸凹を最小に", flat_schedule())):
        print(f"  {name}: " + " ".join(f"{h:>2}" for h in sched)
              + f"  計{sum(sched)}時間")

    print("\n=== 原則の「月45時間」は、12か月続けると年360時間を180時間こえる ===")
    for row in plain_year_grid():
        if row["45時間の月数"] in (0, 6, 7, 8, 9, 10, 11, 12):
            mark = "通る  " if row["通るか"] else "通らない"
            print(f"  45時間の月 {row['45時間の月数']:>2}か月  年の合計 {row['年の合計']:>3}時間"
                  f"  年360時間との差 {row['年360時間との差']:>+4}時間  {mark}")
    v = plain_vs_special()
    print(f"  原則      月の上限 {v['原則の月上限']:>3}時間  年の上限 {v['原則の年上限']:>3}時間"
          f"  12か月でならすと {v['原則の月ならし']:>4.1f}時間"
          f"（月の上限の {v['原則の月ならしが月上限に占める割合'] * 100:.4f}%）")
    print(f"  特別条項  月の上限 {v['特別条項の月上限']:>3}時間  年の上限 {v['特別条項の年上限']:>3}時間"
          f"  12か月でならすと {v['特別条項の月ならし']:>4.1f}時間")
    print(f"  倍率      月の上限 {v['月上限の倍率']:.4f}倍  年ならし {v['月ならしの倍率']:.4f}倍"
          f"  ← **同じ倍率ではありません**")

    print("\n=== 連続する月数ごとの上限と、1か月あたりの平均 ===")
    for row in window_caps():
        print(f"  {row['か月']:>2}か月  上限 {row['実際の上限']:>4}時間"
              f"  月あたり {row['月あたり']:>5.1f}時間"
              f"  月99時間で足した値との差 {row['差']:>4}時間")
