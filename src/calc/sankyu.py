"""産休・育休で社会保険料が免除される「月」を、日付から数える。

一般の解説はここで止まります ——「産休・育休の期間中は社会保険料が免除されます」。

**免除されるのは期間ではなく、月です。** そして月に入るかどうかを決めているのは、
休んだ長さではなく**月末を含んだかどうか**でした（産休はいまもそれだけです）。

この計算で出した数字（`__main__` を実行すると全部出ます）:

- **同じ1か月ぶんの免除に、必要な日数が 1日 と 14日 で 14倍ちがいます。**
  月末を含めれば**育休1日**で1か月ぶん免除され、月末を含まなければ
  **14日**取らないと免除されません（令和4年10月からの「同一月内14日以上」）。
  どちらも生きている規則なので、**同じ月の中に14倍の差が同居しています**
- **産休には14日の道がありません。** 同じ日付で同じ長さ休んでも、
  それが産休なら免除されず、育休なら免除されます。
  標準報酬月額 300,000円 なら、**厚生年金の本人負担だけで 27,450円**の差
- **出産日が1日ちがうだけで、免除される月数が変わります。**
  産前産後は単胎なら98日（42＋56）で、出産日をどこに置いても**1日も変わりません。**
  それでも 2026年9月なら、**9月5日〜10日に産んだ人だけが4か月**免除され、
  **残りの24日に産んだ人は3か月**です（差 27,450円）
- **多胎（産前98日・合計154日）だと、当たりは30日のうち1日だけ**でした。
  9月5日だけが6か月、ほかの29日は5か月です。
  **休んだ日数は154日で全部同じ**なのに、**1日ずれると 27,450円 消えます**
- 効いているのは「産休の末日が、ちょうど月末かどうか」です。
  **長い休みほど当たりが狭くなります**（単胎6日 → 多胎1日）

**厚生年金保険料だけを扱います。** 健康保険料と介護保険料は都道府県と年度で
料率が動くので、混ぜると段差の額が「いつの・どこの」話か言えなくなります
（`shahoken.py` と同じ切り方です。等級表もそちらから引いています）。

## 裏を取った先

- 産前産後休業の期間と免除期間の書き方: 日本年金機構
  「厚生年金保険料等の免除（産前産後休業・育児休業等期間）」
  —— 出産日以前42日（多胎98日）から出産日後56日まで。
  免除は**開始月から、終了日の翌日が属する月の前月まで**
  （終了日が月末なら終了月まで）
- 育児休業の「同一月内に14日以上」: 日本年金機構
  「令和4年10月から 同月内に14日以上育児休業等を取得した場合も免除されます」
- 厚生年金保険料率 18.3%（本人負担 9.15%）と標準報酬月額32等級: `shahoken.py`

**「終了日の翌日が属する月の前月まで」は、月末を含む月だけが入る、と同じ意味です。**
このモジュールはそれを日付から直接数え、両方の書き方が一致することを検査しています
（`check_tables` の往復検査）。
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta

from . import _checks
from .shahoken import GRADES, HALF

ASSUMPTIONS = [
    "厚生年金保険料だけの計算です。健康保険料と介護保険料は入れていません",
    "外した理由は、健康保険の料率が都道府県と年度で変わるためです。厚生年金の保険料率は"
    "2017年9月から18.3パーセントで固定されていて、本人負担はその半分の9.15パーセントです",
    "標準報酬月額は32の等級に分かれ、1等級が8万8千円、32等級が65万円です",
    "産前産後休業は、出産の日以前42日、多胎妊娠なら98日から、出産の日の後56日までです",
    "保険料が免除される月は、休業を開始した月から、終了した日の翌日が属する月の"
    "前月までです。終了した日が月の末日のときは、終了した月までです",
    "育児休業は、これに加えて、同じ月の中で14日以上休んだ月も免除されます。"
    "令和4年10月からの取り扱いです",
    "賞与にかかる保険料は入れていません。賞与は、支払った月の末日を含む"
    "連続した1か月を超える育児休業のときだけ免除になり、月給とは別の判定だからです",
    "就業した日がある場合は数えていません。休んだ日だけを数えています",
    "代表として使う標準報酬月額は300,000円です。本人負担は月27,450円になります",
]

# ---- 制度の値。**長く動いていないものだけをここに置く** ----------------
BEFORE_DAYS = 42        # 産前（単胎）
BEFORE_MULTI = 98       # 産前（多胎）
AFTER_DAYS = 56         # 産後
IKUJI_DAYS = 14         # 育休の「同一月内に14日以上」（令和4年10月から）

REF_STD = 300_000       # 説明に使う標準報酬月額


def premium(std: int) -> int:
    """標準報酬月額に対する、本人負担の厚生年金保険料（月額・円）。切り捨て。"""
    return int(std * HALF)


# ---- 日付から「免除される月」を数える -------------------------------------


def _month_end(y: int, m: int) -> date:
    return date(y, m, monthrange(y, m)[1])


def _months_between(start: date, end: date) -> list[tuple[int, int]]:
    """`start` から `end` までに触れる月を、(年, 月) で並べる。"""
    out: list[tuple[int, int]] = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def days_in_month(start: date, end: date, y: int, m: int) -> int:
    """休業期間のうち、その月に入っている日数。"""
    lo = max(start, date(y, m, 1))
    hi = min(end, _month_end(y, m))
    return (hi - lo).days + 1 if hi >= lo else 0


def covers_month_end(start: date, end: date, y: int, m: int) -> bool:
    """その月の末日が、休業期間の中にあるか。**産休はこれだけで決まります。**"""
    e = _month_end(y, m)
    return start <= e <= end


def exempt_months(start: date, end: date, *, ikuji: bool) -> list[tuple[int, int]]:
    """免除される月を並べる。

    産休は**月末を含む月**だけ。育休はそれに加えて**同じ月に14日以上**の月。
    """
    out = []
    for y, m in _months_between(start, end):
        if covers_month_end(start, end, y, m):
            out.append((y, m))
        elif ikuji and days_in_month(start, end, y, m) >= IKUJI_DAYS:
            out.append((y, m))
    return out


def exempt_by_notice(start: date, end: date) -> list[tuple[int, int]]:
    """**公表資料の書き方のほう**で数える（往復検査の相手）。

    「開始した月から、終了した日の翌日が属する月の前月まで。
    終了日が月末なら終了月まで」。
    """
    nxt = end + timedelta(days=1)
    if end == _month_end(end.year, end.month):
        last = (end.year, end.month)
    else:
        last = (nxt.year - 1, 12) if nxt.month == 1 else (nxt.year, nxt.month - 1)
    if (start.year, start.month) > last:
        return []
    return [ym for ym in _months_between(start, date(*last, 1))]


# ---- 産休の日付を、出産日から組み立てる -----------------------------------


def sankyu_range(birth: date, *, multi: bool = False) -> tuple[date, date]:
    """出産日から、産前産後休業の初日と末日を出す。"""
    before = BEFORE_MULTI if multi else BEFORE_DAYS
    return birth - timedelta(days=before - 1), birth + timedelta(days=AFTER_DAYS)


# ---- 表 -------------------------------------------------------------------


def need_days_grid() -> list[dict]:
    """**同じ1か月の免除に、何日休めば足りるか。** 月末を含むかどうかだけで決まる。"""
    y, m = 2026, 9                       # 30日の月
    last = _month_end(y, m)
    rows = []
    for name, start, end in [
        ("月末の1日だけ休む", last, last),
        ("月末を含む2日", last - timedelta(days=1), last),
        ("月のはじめに13日", date(y, m, 1), date(y, m, 13)),
        ("月のはじめに14日", date(y, m, 1), date(y, m, 14)),
        ("月のはじめに29日", date(y, m, 1), date(y, m, 29)),
    ]:
        d = (end - start).days + 1
        rows.append({
            "休み方": name,
            "休んだ日数": d,
            "月末を含む": covers_month_end(start, end, y, m),
            "産休なら免除": bool(exempt_months(start, end, ikuji=False)),
            "育休なら免除": bool(exempt_months(start, end, ikuji=True)),
        })
    return rows


def sankyu_vs_ikuji() -> list[dict]:
    """**同じ日付・同じ長さで、産休と育休の免除月数を並べる。**"""
    y, m = 2026, 9
    rows = []
    for d in (7, 14, 20, 25, 29):
        start, end = date(y, m, 1), date(y, m, d)
        s = len(exempt_months(start, end, ikuji=False))
        i = len(exempt_months(start, end, ikuji=True))
        rows.append({
            "月初からの日数": d,
            "産休の免除月数": s,
            "育休の免除月数": i,
            "差(月)": i - s,
            "差の額(円)": (i - s) * premium(REF_STD),
        })
    return rows


def birth_day_grid(*, multi: bool = False) -> list[dict]:
    """**出産日を1日ずつ動かすと、免除される月数が変わる。** 期間の長さは同じ。"""
    rows = []
    for day in range(1, 31):
        birth = date(2026, 9, day)
        start, end = sankyu_range(birth, multi=multi)
        months = exempt_months(start, end, ikuji=False)
        rows.append({
            "出産日": birth.isoformat(),
            "産休の初日": start.isoformat(),
            "産休の末日": end.isoformat(),
            "休んだ日数": (end - start).days + 1,
            "免除される月数": len(months),
            "免除される額(円)": len(months) * premium(REF_STD),
        })
    return rows


def grade_grid() -> list[dict]:
    """**等級ごとに、免除1か月あたりいくらか。**"""
    rows = []
    for std in GRADES[::4] + [GRADES[-1]]:
        rows.append({
            "標準報酬月額": std,
            "本人負担(月)": premium(std),
            "1か月ずれたときの差": premium(std),
            "産休4か月ぶん": premium(std) * 4,
        })
    _checks.unique_by(rows, lambda r: r["標準報酬月額"], "等級ごとの表")
    return rows


def grid() -> list[dict]:
    return need_days_grid()


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。**壊れた数字で台本を書かせない。**"""
    # 1. 法令・公表資料が名指ししている値
    _checks.statutory(BEFORE_DAYS, 42, "産前の日数（単胎）",
                      source="日本年金機構「厚生年金保険料等の免除」")
    _checks.statutory(BEFORE_MULTI, 98, "産前の日数（多胎）",
                      source="同上")
    _checks.statutory(AFTER_DAYS, 56, "産後の日数", source="同上")
    _checks.statutory(IKUJI_DAYS, 14, "育休の同一月内の日数",
                      source="日本年金機構（令和4年10月から）")
    _checks.ratio(HALF, "厚生年金保険料の本人負担率")
    _checks.rounding(premium(REF_STD), 27_450, "標準報酬月額30万円の本人負担")

    # 2. **往復検査。** 日付から数えたものと、公表資料の書き方が一致すること。
    #    **産休には14日の道が無いので、こちらは `ikuji=False` としか比べられません。**
    #    ここが割れたら、割れているのは「月末を含む月」という読み替えのほうです。
    for y in (2026, 2027):
        for m in range(1, 13):
            for d0 in (1, 12, 15, 27, monthrange(y, m)[1]):
                start = date(y, m, d0)
                for span in (0, 1, 13, 14, 29, 41, 97):
                    end = start + timedelta(days=span)
                    got = exempt_months(start, end, ikuji=False)
                    want = exempt_by_notice(start, end)
                    if got != want:
                        raise _checks.TableError(
                            "月末で数えた結果と、公表資料の書き方が一致しません: "
                            f"{start}〜{end} 日付から={got} 資料の書き方={want}")

    # 3. この計算の主題そのもの
    y, m = 2026, 9
    last = _month_end(y, m)
    # **月末1日**で1か月免除される（育休でも産休でも）
    _checks.greater(len(exempt_months(last, last, ikuji=False)), 0,
                    "月末1日の休業で免除される月数が0（月末判定が効いていない）")
    # **月末を含まない13日**は、産休では免除されず、育休では免除されない
    a, b = date(y, m, 1), date(y, m, 13)
    if exempt_months(a, b, ikuji=False) or exempt_months(a, b, ikuji=True):
        raise _checks.TableError("13日・月末なしで免除が出ています（14日の境目が壊れている）")
    # **月末を含まない14日**は、育休だけ免除される
    b14 = date(y, m, 14)
    if exempt_months(a, b14, ikuji=False):
        raise _checks.TableError("産休に14日の道はありません（産休で免除が出ています）")
    if not exempt_months(a, b14, ikuji=True):
        raise _checks.TableError("育休の14日で免除が出ていません")

    # 育休の免除月数は、産休のそれを下回らない（道が1本多いので）
    for d in range(1, 30):
        s, e = date(y, m, 1), date(y, m, d)
        _checks.greater(len(exempt_months(s, e, ikuji=True)) + 1,
                        len(exempt_months(s, e, ikuji=False)),
                        f"育休の免除月数が産休を下回りました（{d}日）")

    # 産前産後の日数は、出産日をどこに置いても同じ（変わるのは免除月数だけ）
    lens = {r["休んだ日数"] for r in birth_day_grid()}
    if len(lens) != 1:
        raise _checks.TableError(f"産休の長さが出産日で変わっています: {sorted(lens)}")
    _checks.rounding(lens.pop(), BEFORE_DAYS + AFTER_DAYS, "産前産後休業の日数")

    # 免除月数は、出産日によって本当に振れる（振れないなら題材が成立しない）
    ms = {r["免除される月数"] for r in birth_day_grid()}
    if len(ms) < 2:
        raise _checks.TableError(f"出産日を動かしても免除月数が変わりません: {ms}")

    _checks.increases_with(premium, [88_000, 300_000, 650_000],
                           "標準報酬月額が上がったのに保険料が上がっていない")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 同じ1か月の免除に、1日で足りる場合と14日要る場合がある ===")
    for row in need_days_grid():
        print(row)

    print("\n=== 産休には「14日以上」の道が無い（同じ休みでも免除が変わる）===")
    for row in sankyu_vs_ikuji():
        print(row)

    print("\n=== 98日は1日も変わらないのに、出産日で免除が3か月と4か月に割れる ===")
    for row in birth_day_grid():
        print(row)

    print("\n=== 多胎（154日）だと、6か月になる出産日は30日のうち1日だけ ===")
    for row in birth_day_grid(multi=True):
        print(row)

    print("\n=== 1日ずれて消える額は、等級で8,052円から59,475円まで開く ===")
    for row in grade_grid():
        print(row)
