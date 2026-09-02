"""**オーナーが固定した運転規則**（2026-08-31）。**API 0単位・読むのは自分だけ。**

この repo で「1日に何本 置いてよいか」を**決めている唯一の場所**です。
`scripts/batch_build.density_cap()` と `scripts/eta.PLAN_PUBLISH_PER_DAY` は
どちらもここを読みます（検査 `tests/test_house_rule.py` / `tests/test_density_cap.py`）。

## 原文（**一字も変えないこと**）

    「動画は1日一本作り置きはなしにして。次の投稿予定までにそこで投稿する動画を
      改善し続ける。それは固定にして。その上で目標を目指す」

**「それは固定にして」と言っています。** 目標の本文と並ぶ**固定**で、
`A14` の「この9件以外はすべてあなたの考えで変えてよい」の**外側**です。
次に来た回が「より速い道が見つかったから」で外してよい対象では**ありません**。

## 規則の中身（4つ）

    1. 公開は **1日に1本**。それ以上 出さない
    2. **作り置きをしない** —— 先に何十本も作って予約に積むのをやめる
    3. 次の投稿の枠までの時間は、**その枠で出す1本を改善し続けることに使う**
    4. その上で、目標（YouTube の収益で月20万を最短で）を目指す

**3が、この規則のいちばんの中身です。** いままでは「本数を積む」に時間が流れていました。
これからは「**次に出る1本を、出る瞬間まで良くし続ける**」に流れます。

## なぜ機械の側に置くか

この repo でいちばん多い壊れ方は「**言っている所と、している所が別**」です
（`tests/test_density_cap.py` の冒頭に、文書が「10本/日」と書いている裏で
機械が 19本・22本 置いた実例があります）。**文書に書くだけにしないこと。**
だから上限の出どころを**ここ1か所**にして、規則の側が勝つ形にしてあります。

## 上限と「測れている帯」は別ものです

`src.density_verdict.HOUR_HI = 13` は**測れている帯の上端**であって、
出してよい本数ではありません。**帯は観測、ここは規則**です。
規則が 13 より小さいので、規則が勝ちます（`density_verdict` は
そのまま観測の道具として置いておくこと ―― 帯を消すと判定が撃てなくなります）。

## 覆る条件

**ありません。** オーナーが自分の言葉で外すまで固定です
（外れたら、そのときの原文をここに書き足して `PUBLISH_PER_DAY` を動かすこと）。
"""
from __future__ import annotations

import math as _math
import re as _re
from datetime import date as _date, timedelta as _timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: **1日に公開してよい本数。** 規則1。ここが上限の唯一の出どころです。
PUBLISH_PER_DAY = 1

#: **作り置きをしてよいか。** 規則2。`False` のあいだ、
#: `batch_build` は1回の走りで複数本を予約まで持っていきません。
STOCKPILE_ALLOWED = False

#: オーナー原文（**一字も変えないこと**）。`CLAUDE.md` と `docs/GOAL.md` に
#: 同じ文字列が在ることを `tests/test_house_rule.py` が見ています。
OWNER_VERBATIM = (
    "動画は1日一本作り置きはなしにして。"
    "次の投稿予定までにそこで投稿する動画を改善し続ける。"
    "それは固定にして。その上で目標を目指す"
)

#: 原文を置いてある場所（**両方に在ること**。片方が消えたら検査が赤くなります）。
#: **オーナー原文（2026-09-02・固定の与件に追加）。** 一字も変えないこと。
#:
#: 08/16 に「額」が「ひたい」と読まれたのをオーナーが耳で見つけ、6日 気づけなかった。
#: そのとき直したのは**裸の「額」1語だけ**（`src/yomi.py`）。この指示は
#: **語を1つずつ直す形をやめて、台本の全部の漢字の読みを検算してから出す**という意味。
#:
#: 2つ目は中身の側。**数字と制度名が正しくても、聞いて分からなければ届いていない。**
#: 検査に「合っている」しか無いなら、それは**人に分かるかを誰も見ていない**ということ。
OWNER_VERBATIM_YOMI = "ナレーションの漢字の読み方全部正しくして"
OWNER_VERBATIM_PLAIN = "動画内の説明は人間にわかるようにして"

VERBATIM_HOMES = ("CLAUDE.md", "docs/GOAL.md")


def verbatim_missing_from(root: Path | None = None) -> list[str]:
    """**原文が repo から消えた場所**を返す（空なら全部 在る）。API 0単位。"""
    base = ROOT if root is None else Path(root)
    gone: list[str] = []
    for rel in VERBATIM_HOMES:
        path = base / rel
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            gone.append(rel)
            continue
        if OWNER_VERBATIM not in text:
            gone.append(rel)
    return gone


def cap() -> int:
    """**1日の上限**（規則1）。呼ぶ側は定数を書かず、ここを読むこと。"""
    return max(0, int(PUBLISH_PER_DAY))


# ---------------------------------------------------------------- 規則2の実装
#
# **オーナー原文（2026-08-31・追加）**:
#
#     「使わなければ良いだけ前提にも再利用もしない」
#
# 中身は3つで、**そのうち2つ目がここです**。
#
#     1. 使わない      予約を外して非公開のまま置く（**削除はしない**）
#     2. 前提にしない  **予測の計算から、作り置きを全部 外す**  ← ここ
#     3. 再利用しない  新しい本の材料に、作り置きの台本・図・題材を使わない
#
# **作り置きは、もう供給ではありません。** 供給は **1日1本、これから作る分だけ**です。
# 予約に在る 400本超は、外して非公開のまま置きます ＝ **1本も公開されません。**
# だから「これから出る本」として数えると、**在りもしない供給で日付が早く出ます。**
#
# **外した結果、到達日は後ろへ動きます。それが正しい姿です。隠さないこと。**

#: **作り置き（予約済み・未公開）を供給として数えてよいか。** 規則2。
#: **`False` から動かさないこと** —— 動かすと、公開しない本で日付が早く出ます。
STOCKPILE_IS_SUPPLY = False

# ---------------------------------------------------------------- 規則5（固定その4）
#
# **オーナー原文（2026-09-02）**:
#
#     「現在の日付にしか予約しないってことだからね？」
#     「その日の投稿の後は次の日の作成になるってわかってるよな？」
#
# 規則2の「作り置きなし」の**意味が、ここで確定しました**。
#
#     その日の1本を、**その日に**予約する。**先の日付には1本も置かない。**
#     先の日付が空であることが、**正しい状態**です。
#
# そして1日の回り方はこうです ——
#
#     公開したら → **すぐ次の日の1本を作り始める**（前の日のうちに作る）
#                 → 次の枠まで改善し続ける（規則3）
#                 → **その日になったら、その日で予約して出す**（規則5）
#
# **「その日に予約する」は「その日まで何もしない」ではありません。**
# 作るのは前の日の公開直後から。**当日なのは予約だけ**です。
#
# ## これで意味が反転したもの（**呼ぶ側は必ずここを読むこと**）
#
# `src/next_slot.calendar` / `scripts/pool_drain.py` / `scripts/slot_gate.py` /
# `scripts/deadline_check.py` / `scripts/queue_lag.py` / `scripts/live_slots.py` は
# **「先の日付に予約が在るのが正常」**という前提で書かれていました。
# **この規則の下では、逆です** ——
#
#     先の日付が空          **正常**（欠陥ではない。警告しないこと）
#     先の日付に予約が在る  **これが欠陥**（＝ 外すべき作り置き）
#
# **`reschedule.py --compact --apply`（先の日付へ並べ直す手）は撃たないこと。**
# 直す手は逆向きで、`python scripts/pool_drain.py --apply --keep 0` です。

#: **予約してよいのは「今日（JST）」だけか。** 規則5。
#: ここが「先の日付に置いてよいか」の唯一の出どころです。
SAME_DAY_SCHEDULING_ONLY = True

#: オーナー原文（**一字も変えないこと**）。`CLAUDE.md` に在ります。
OWNER_VERBATIM_SAME_DAY = "現在の日付にしか予約しないってことだからね？"
OWNER_VERBATIM_NEXT_DAY = "その日の投稿の後は次の日の作成になるってわかってるよな？"


def same_day_only() -> bool:
    """**先の日付への予約を禁じているか**（規則5）。定数を写さず、ここを読むこと。"""
    return bool(SAME_DAY_SCHEDULING_ONLY)


def ahead_of_today(rows, now=None) -> list:
    """**「明日以降に予約が入っている」行**を返す（規則5の下では、これが欠陥）。

    `rows` は `data/uploaded.jsonl` 形（`video_id` / `at`）でも
    `queue_lag.scheduled()` 形でも通ります —— 見るのは `at`（ISO・UTC 可）だけ。

    **空リストが正常**です。1件でも返ったら、それは外す対象（`pool_drain`）。
    今日ぶんの1本は**含みません**（当日の予約は規則どおり）。
    """
    from datetime import datetime, timedelta, timezone
    jst = timezone(timedelta(hours=9))
    t = now or datetime.now(timezone.utc)
    today = t.astimezone(jst).date()
    out = []
    for r in rows or ():
        raw = r.get("at") or r.get("publish_at") or r.get("scheduled_at")
        at = _instant(raw)
        if at is None:
            continue
        if at.astimezone(jst).date() > today:
            out.append(r)
    return out


def refuse_future_publish(publish_at, now=None) -> str:
    """**先の日付への予約を、書く直前に断る理由**（断らないなら空文字）。規則5。

    ## なぜ「外す側」だけでは足りないか（2026-09-02・オーナー原文）

    > **「1日一本になってないんだけど、今後こういうことが一切ないようにしろ」**

    `scripts/pool_drain.py` も `scripts/ahead_gate.py` も、**もう置かれたものを
    外す側**です。**置く側が開いたままなら、外した先から積み直せます** ——
    そして置く側は実際に開いていました:

        `src.uploader.next_publish_at()` の自動探索は、きょうの枠が
        過去／埋まっていると **`target += timedelta(days=1)` で翌日以降へ歩きます**
        （最大60日先まで）。**規則5 の下では、この1行が違反そのものです。**

    459本 の作り置きは、この歩きが積んだものです。**外し切っても、
    この道が開いていれば同じ山が戻ります。**

    ## ここに置く理由（**入口ごとに書かないこと**）

    `videos.update` の関門は `scripts/reschedule._update()` **1か所**
    （あの docstring:「入口が6つあり、塞いでも7つ目が同じ穴を作る。
    **関門はここ1か所なので、ここで止めます**」）。
    `videos.insert` の予約時刻を決めるのは `uploader.next_publish_at()` **1か所**
    （あの docstring:「予約時刻を決めているのは、この関数だけです」）。
    **判定の本文はここ1つで、その2か所が呼ぶだけ**にします ——
    写すと、この repo が通算12回 踏んだ「片方だけ直す」に戻ります。

    ## 断らないもの

        `publish_at` が `None`            **予約を外す手**（＝ 池化。これは通す）
        きょう（JST）以前の時刻          規則どおり
        `same_day_only()` が `False`      規則5 が外れている

    **読めない時刻は断りません**（推測で投稿を止めないこと ——
    `CLAUDE.md`「投稿が途切れるのが最大の損失」）。

    ## 覆る条件

    - オーナーが「先の日付にも置いてよい」と言ったら `SAME_DAY_SCHEDULING_ONLY`
      が `False` になり、ここは全部 空文字を返します
    - **抜け道を作らないこと。** 「この回だけ」の環境変数を足したくなったら、
      それは 08/31 からの2日で 459本 → 107本 にしか減らなかったのと同じ形です

    検査は `tests/test_no_future_schedule.py`。
    """
    if not same_day_only():
        return ""
    at = _instant(publish_at) if publish_at is not None else None
    if at is None:
        return ""
    from datetime import datetime, timedelta, timezone
    jst = timezone(timedelta(hours=9))
    t = now or datetime.now(timezone.utc)
    day = at.astimezone(jst).date()
    today = t.astimezone(jst).date()
    if day <= today:
        return ""
    return (
        f"**{day} は「先の日付」です。予約できません**"
        f"（規則5・固定その4「{OWNER_VERBATIM_SAME_DAY}」）。\n"
        f"  きょうは {today}（JST）。**その日の1本を、その日に予約する** ——"
        " 先の日付が空であることが正しい状態です。\n"
        "  作った本は `--draft` で private のまま上げて置き、"
        "**その日になってから** `scripts/reschedule.py --move <id> <時刻>`。\n"
        "  いま先の日付に在るぶんは `python scripts/ahead_gate.py` が数えます"
        "（外すのは `python scripts/pool_drain.py --apply --keep 0`）。"
    )


#: **この日より前に作った本が「作り置き」です**（規則が入った日）。
#: この日以降に作る本は、1日1本の規則の下で作った本なので、**供給です**。
#: 日付を写さないこと —— 判定は下の `is_stockpile()` の1か所です。
STOCKPILE_SINCE = "2026-08-31"


def planned_publishes_per_day() -> int:
    """**これから1日に公開する本数。** 作り置きは1本も数えません（規則2）。

    予測の「これから」の側は、**必ずここを読むこと。**
    `data/uploaded.jsonl` の未来の `at` を数えて「これから N本/日 出る」と
    するのは、**外して非公開にする本を供給に数える**ことです。
    """
    return cap()


def _jst_today() -> str:
    from datetime import datetime, timedelta, timezone
    return datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")


def _instant(raw: object):
    """控えの `at` を**時刻**として読む（読めなければ `None`）。

    控えは UTC の `Z` 表記（`2026-09-02T04:00:00Z`）で書かれますが、
    **`+09:00` の行も混ざっています**（`data/uploaded.jsonl` の実測）。
    帯の無い行は UTC と読みます（`scripts/pool_drain._parse` と同じ）。
    """
    from datetime import datetime, timezone
    try:
        at = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return at.replace(tzinfo=timezone.utc) if at.tzinfo is None else at


def _published_before(now=None, today: str | None = None):
    """**「もう公開になっている」の境**を、時刻で返す。

    ## なぜ日付ではなく時刻か（2026-09-01 に、オーナーが画面で踏んだ）

    ここは長らく `str(at)[:10] <= today` の**日付の文字列比べ**でした。
    2026-09-01 16:33 JST、オーナーの YouTube Studio に **09/01 の
    18:00 / 19:00 / 20:00 / 21:00 の予約が4本**出ていたのに、
    `scripts/pool_drain.py` の一覧は **09/02 から**しか出ませんでした ——
    **まだ来ていない当日の予約が「もう公開になっている ＝ 実績」に倒れ、
    作り置きから外れて、外す一覧から丸ごと落ちていた**からです。
    外す順は「公開の早い順」なのに、**その日に出てしまう本だけが見えない。**
    放っておけば当日5本 公開され、**規則1（1日1本）が破れます。**

    しかも物差しが2つ混ざっていました —— `at` は **UTC**、`today` は
    **JST の日付**。09/02 00:30 JST（＝ 09/01 15:30Z）の予約は
    `at[:10] == "2026-09-01"` なので、**翌日の未明ぶんまで同じ穴**に落ちます。

    ## 何を境にするか

        `now` が来た      …… それを使う（呼ぶ側が時刻を持っている ＝ いちばん正確）
        `today` だけ来た  …… その日が**実際の今日**なら「いま」、
                              違う日（＝日付で固定したい回・検査）なら
                              **その日の 00:00 JST**
        どちらも無い      …… `_jst_today()` に聞いて、同じ規則で決める
                              （**この関数を飛ばさないこと** —— 検査は
                                そこを差し替えて日付を固定しています）

    **日付だけを渡された回に、その日の 00:00 JST を境にするのはわざと**です。
    同じ日の予約は「まだ来ていない」側へ倒れます ——
    **落とす側（＝ 実績とみなして一覧から消す側）に倒すのが、この穴の正体**でした。
    `is_stockpile` の姿勢（測っていないことを落とす側に倒さない）と同じ向きです。

    **覆る条件**: 控えが `at` を持たない形に変わったら、この関数は意味を失います。
    検査は `tests/test_pool_drain_today_first.py`。
    """
    from datetime import datetime, timedelta, timezone
    jst = timezone(timedelta(hours=9))
    if now is not None:
        return now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    real = datetime.now(timezone.utc)
    day = str(today or _jst_today())[:10]
    if not day or day == real.astimezone(jst).strftime("%Y-%m-%d"):
        return real
    try:
        return datetime.fromisoformat(day + "T00:00:00").replace(tzinfo=jst)
    except ValueError:
        return real


def is_stockpile(row: dict, today: str | None = None, now=None) -> bool:
    """**その控えの行は「作り置き」か。**（`data/uploaded.jsonl` の1行）

    作り置きの条件は**2つとも**満たすことです:

        1. まだ公開されていない（`at` が**いまより先**。日付ではなく**時刻**で
           比べます —— 理由は `_published_before()` の註。当日ぶんが
           丸ごと見えなくなる穴を、2026-09-01 に実物で踏んでいます）
        2. **規則より前に作った**（`uploaded_at` が `STOCKPILE_SINCE` より前）

    2 が要ります。**規則の下で作った本まで落とすと、これから出す1本が
    供給から消えます** —— そうなると「1日1本 作っても面は 0回/日」と
    印字することになり、実物と食い違います。

    `now` は**呼ぶ側が持っている時刻**（`scripts/pool_drain.pool()` が渡します）。
    無ければ `today` から、それも無ければ「いま」から境を作ります。

    読めない行（`at` が無い・形が違う）は **False**（＝落とさない）。
    **測っていないことを、落とす側に倒さないこと。**
    """
    if STOCKPILE_IS_SUPPLY:
        return False
    raw = row.get("at")
    if not raw:
        return False
    at = _instant(raw)
    if at is None:
        # **時刻として読めない行**だけ、これまでどおり日付で比べます
        # （読めないものを落とす側に倒さない、の同じ姿勢）。
        if str(raw)[:10] <= (today or _jst_today()):
            return False
    elif at <= _published_before(now, today):
        return False                      # もう公開になっている ＝ 実績
    made = str(row.get("uploaded_at") or "")[:10]
    if not made:
        return True                       # 作った日が分からない未来の予約 ＝ 作り置き
    return made < STOCKPILE_SINCE


def drop_stockpile(rows, today: str | None = None, now=None) -> list:
    """**控えの行から、作り置きを落とす。** 残るのが供給です（規則2）。"""
    return [r for r in rows if not is_stockpile(r, today, now)]


# --- **規則の下で、その前提はまだ満ちうるか**（2026-08-31 に足した） ---------------
#
# `config/hypotheses.yaml` の `needs[].what` には、**未来の日に何本 公開しているか**を
# 前提にした要件がいくつも入っています（実測 2026-08-31・開いた26件のうち **6件**）:
#
#     「2026-09-02 の**12本すべて**の、公開から6時間 以上の読み」
#     「09/10（16本 公開）の、公開から6時間たった読み」
#     「`data/reach.jsonl` の 08/26〜09/07（長尺の予約 26本 ＝ 2.0本/日）」
#     「`data/views.jsonl` の長尺 30本ぶんの、齢をそろえた読み」
#
# **どれも 2026-08-31 の規則より前に書かれています。** 規則1（公開は1日1本）と
# 規則2（作り置きをしない ＝ 予約を池へ戻す）の下では、**その日は来ません。**
# ところが `scripts/deadline_check.py` はそれを `[OK] …09/10 に出ます` と印字します
# —— **永久に来ないデータを「その日に出ます」と言っている**状態です。
#
# **これは小さい話ではありません。** `scripts/eta.py` は
# 「**軌跡の腕が動くのは、前提を1件 閉じたときだけ**」と自分で印字しています。
# 満ちない要件を持った前提は閉じられないので、**到達日はそこで止まります。**
#
# **判定は本文を読まずに、数で行います** —— 今日から期日までに規則が許す公開は
# `(期日 − 今日) × PUBLISH_PER_DAY` 本。要件が名指ししている本数がそれを超えたら、
# **規則の下では満ちません。** 本数の読み取りは `_COUNT` の1つだけ（`N本`）で、
# 「N本/日」は日数を掛けずにそのまま比べます。
#
# **止める仕掛けではありません。** 何も止めず、**印字するだけ**です
# （`CLAUDE.md`「作りに問題を見つけたら、止めるのではなく直すこと」）。
# 直し方は2つ ——(1) 要件を、1日1本で届く形に書き直す
#              (2) すでに公開ずみの日で判定できるなら、いま閉じる
#
# **覆る条件**: オーナーが規則を外したら、許す本数が増えてこの関数は自然に黙ります。
# 検査は `tests/test_house_rule_reach.py`。

_COUNT_PER_DAY = _re.compile(r"(\d+(?:\.\d+)?)\s*本\s*/\s*日")
_COUNT = _re.compile(r"(\d+)\s*本")


def needs_beyond_rule(what: str, on_date: str, today: str | None = None) -> dict | None:
    """**その要件は、規則の下でまだ満ちうるか。** 満ちないなら理由を返す。

    返すのは `{"named": 名指しされた本数, "allowed": 規則が許す本数, "kind": …}`。
    満ちうる（または読み取れない）ときは `None`。**読めないものは通します** ——
    測っていないことを、落とす側に倒さないこと（`is_stockpile` と同じ姿勢）。
    """
    if not what or not on_date:
        return None
    t = today or _jst_today()
    try:
        d0 = _date.fromisoformat(t[:10])
        d1 = _date.fromisoformat(str(on_date)[:10])
    except ValueError:
        return None
    if d1 <= d0:
        return None                      # 過去の日は、もう起きたことなので触らない

    # (1) 「N本/日」—— 日数を掛けずに、そのまま規則と比べる
    per_day = [float(x) for x in _COUNT_PER_DAY.findall(what)]
    over = [n for n in per_day if n > PUBLISH_PER_DAY]
    if over:
        return {"named": max(over), "allowed": float(PUBLISH_PER_DAY),
                "kind": "per_day", "on_date": str(on_date)[:10]}

    # (2) 「N本」—— 今日から期日までに、規則が何本 許すかと比べる
    allowed = (d1 - d0).days * PUBLISH_PER_DAY
    text = _COUNT_PER_DAY.sub("", what)          # 上で見た形は取り除く
    counts = [int(x) for x in _COUNT.findall(text)]
    named = [n for n in counts if n > allowed]
    if named:
        want = max(named)
        # **「届きません」で止めないこと。** どこまで動かせば届くかを、
        # 同じ返りに入れます（2026-09-02 に足した）—— これが無いと、
        # 次に来た回が毎周 同じ引き算をやり直します（実測: 09/01 と 09/02 の
        # 2回が、同じ2件で同じ計算をしています）。
        #
        # **規則は 1日 N本 なので、`want` 本 積むのに要るのは
        # `ceil(want / PUBLISH_PER_DAY)` 日**。それを今日に足したのが、
        # 要件が満ちる最初の日（`need_on_date`）です。
        # **期限そのものは、そこへ実データの遅れを足した日より後**に置くこと
        # —— 遅れの日数はここでは測れないので（`src/settle.py` の持ち物）、
        # **足す前の日を返します。呼ぶ側が遅れを足すこと。**
        need_days = int(_math.ceil(want / float(PUBLISH_PER_DAY)))
        return {"named": want, "allowed": float(allowed),
                "kind": "total", "on_date": str(on_date)[:10],
                "need_days": need_days,
                "need_on_date": str(d0 + _timedelta(days=need_days)),
                "short_days": need_days - (d1 - d0).days}
    return None


def unreachable_needs(rows, today: str | None = None) -> list[dict]:
    """開いている前提の `needs` から、**規則の下では満ちないもの**を並べる。

    `rows` は `config/hypotheses.yaml` の `hypotheses`（そのままの list）。
    """
    out: list[dict] = []
    for r in rows or []:
        if r.get("closed_on"):
            continue
        for n in (r.get("needs") or []):
            hit = needs_beyond_rule(str(n.get("what") or ""),
                                    str(n.get("on_date") or ""), today)
            if hit:
                # **`lever` も一緒に返します**（2026-09-01 に足した）。
                # `scripts/run_marker._unreachable_premise_lines()` が
                # 「**どの腕が止まるか**」を §1 で出すため —— 呼ぶ側に
                # `hypotheses.yaml` を引き直させると、そこがまた台帳の道を写します。
                out.append(dict(hit, claim=str(r.get("claim") or ""),
                                deadline=str(r.get("deadline") or ""),
                                lever=str(r.get("lever") or ""),
                                what=str(n.get("what") or "")))
    return out


#: 前提の置き場。**呼ぶ側に道を書かせないこと** —— 写した道は古くなります。
HYPOTHESES = ROOT / "config" / "hypotheses.yaml"


def unreachable_claims(today: str | None = None, path: Path | None = None) -> list[str]:
    """**来ない日を待っている前提**の claim を、期日の順に（重複なし）。

    `unreachable_needs()` は `rows` を受け取りますが、**呼ぶ側の大半は
    yaml を読むところから書く必要があります**（`scripts/eta.py` は
    `yaml` を import していません）。**読むところまでここに置きます。**

    読めない回は空を返します —— **測っていないことを、止める側に倒さないこと。**
    """
    try:
        import yaml                                    # noqa: PLC0415
        doc = yaml.safe_load((path or HYPOTHESES).read_text(encoding="utf-8")) or {}
        rows = list(doc.get("hypotheses") or [])
    except Exception:                                   # noqa: BLE001
        return []
    out: list[str] = []
    for hit in sorted(unreachable_needs(rows, today),
                      key=lambda x: str(x.get("deadline") or "")):
        claim = str(hit.get("claim") or "")
        if claim and claim not in out:
            out.append(claim)
    return out


def unreachable_lines(rows, today: str | None = None) -> list[str]:
    """画面に出す形。**満ちない要件が無ければ、1行も出しません。**"""
    hits = unreachable_needs(rows, today)
    # **期日を延ばしても満ちないほう**は、上の節が黙っても出します
    # （上は期日で解いており、延ばせば黙るため。下の節の冒頭に理由）。
    win = window_unreachable_lines(rows)
    if not hits:
        return win
    out = [f"=== **規則（1日{PUBLISH_PER_DAY}本）の下では、期日までに満ちない要件: "
           f"{len(hits)}件** ===",
           "  **`[OK] …に出ます` と並んでいても、その日は来ません。**"
           " `scripts/eta.py` は「軌跡の腕が動くのは前提を1件 閉じたときだけ」と"
           "印字しているので、**ここが詰まると到達日が止まります。**",
           "  直し方は2つ ——(1) 要件を 1日1本 で届く形へ書き直す"
           " (2) すでに公開ずみの日で判定できるなら、いま閉じる。"]
    for h in sorted(hits, key=lambda x: x["deadline"]):
        if h["kind"] == "per_day":
            why = (f"要件が **{h['named']:g}本/日** を名指ししています"
                   f"（規則は {h['allowed']:g}本/日）")
        else:
            why = (f"要件が **{h['named']}本** を名指ししていますが、"
                   f"今日から {h['on_date']} までに規則が許すのは **{h['allowed']:g}本**")
        out.append(f"  [!] {h['deadline']}  {h['claim'][:52]}")
        out.append(f"        {why}")
        out.append(f"        要件: {h['what'][:100]}")
        # **どこまで動かせば届くかを、同じ所に出します**（2026-09-02 に足した）。
        # 「届きません」だけを出すのは、`CLAUDE.md` が `eta.py` について
        # 「**裸の『届きません』を出さないこと**」と書いているのと同じ形です。
        if h["kind"] == "per_day":
            out.append("        → **期日をいくら延ばしても届きません。**"
                       " 規則そのものを超える本数を名指ししているので、"
                       "**書き直すのは要件のほう**です（1日1本 で言える形へ）")
        else:
            out.append(f"        → **{h['short_days']}日 足りません。**"
                       f" `on_date` を **{h['need_on_date']}** 以降にすれば、"
                       f"規則の 1日1本 で {h['named']}本 に届きます"
                       f"（今日から {h['need_days']}日）。"
                       f"**`deadline` は、そこへ実データの遅れを足した日より後**に置くこと")
            out.append("        [!] **この日数は「規則どおり毎日1本 出た場合」です。**"
                       " 予約の暦に穴があるあいだは、この日も来ません ——"
                       " §1 の `[暦]` が鳴っていたら、**先にそちらを埋めること**"
                       "（`scripts/reschedule.py --compact`）")
    return out + win


# --- **期日を延ばしても満ちない要件**（2026-09-01 に足した） -------------------
#
# 上の `needs_beyond_rule()` は **期日までの日数**で解いています ——
# `allowed = (期日 − 今日) × PUBLISH_PER_DAY`。
# **だから期日を延ばすと、この関数は黙ります。** そして `falsified_if` の側は、
# たとえば `長尺1本あたり-30本` がこう書いています ——
#
#     **30本 に満たなければ判定せず、期限だけ延ばすこと**
#
# **指示と検査が、同じ向きに壊れています。** 延ばせば警告は消え、前提は
# 永久に開いたまま残ります。**「確かめずに済んでしまう」形**です。
#
# ここが見るのは別の軸です —— **判定が読む窓**。窓が「直近28日」なら、
# 規則（1日1本）の下でその窓に入りうる本は **28本 が上限**で、
# **期日をどこまで延ばしても 30本 にはなりません。**
#
# 実測 2026-09-01（開いた25件を走査）:
#
#     `長尺1本あたり-30本`  need 30本 ／ 窓 直近28日 ／ 規則が許す 28本 → **永久に満ちない**
#
# **`長尺-1000再生` は当たりません**（`need: 1000` は `sum(latest_views()…)` ＝
# **再生数**で、公開本数の上限には縛られない）。**単位を見ずに数だけ比べると、
# ここが偽陽性になります** —— 実際、単位を見ない版では 2件 出ました。
#
# ## なぜ、これが到達日に効くか
#
# `scripts/eta.py` は「**軌跡の腕が動くのは、前提を1件 閉じたときだけ**」と
# 印字します。そして `長尺1本あたり-30本` の腕は **`per_video`** ——
# 実測 2026-09-01 で、道具が「この腕を引け」と印字した 357回 のうち
# **298回（83%）が `per_video`** です。その腕の、**長尺の側で唯一の測定**が
# これでした。永久に閉じないので、**`per_video` は永久に測り終わりません。**
#
# ## 覆る条件
#
# オーナーが規則を外して `PUBLISH_PER_DAY` が上がれば、窓に入る本数が増えて
# 自然に黙ります。**窓のほうを広げても黙ります** —— ただしそれは
# 「判定が読む窓」を変えることなので、`falsified_if` の書き換えです。
# 検査は `tests/test_house_rule_window.py`。

#: 「直近28日」の形。**判定が読む窓**を、前提の本文から拾う。
_WINDOW_DAYS = _re.compile(r"直近\s*(\d+)\s*日")

#: `count_expr` が**本数**を数えている形（`sum(1 for …)` / `len(…)`）。
_EXPR_COUNTS_ITEMS = _re.compile(r"sum\(\s*1\s+for\b|len\(")


def counts_published_items(count_expr: str | None) -> bool | None:
    """その `count_expr` は**本数**を数えているか。

    `True`  …… `sum(1 for …)` / `len(…)` ＝ 1件ずつ数えている。
                **公開本数の上限（規則1）に縛られる**側。
    `False` …… `sum(<値> for …)` ＝ 再生数などの**量**を足している。
                本数の上限には縛られない（`長尺-1000再生` がこれ）。
    `None`  …… 読み取れない。**通します**（`is_stockpile` と同じ姿勢 ——
                測っていないことを、落とす側に倒さないこと）。
    """
    if not count_expr:
        return None
    s = str(count_expr)
    if _EXPR_COUNTS_ITEMS.search(s):
        return True
    if "sum(" in s:
        return False
    return None


def window_of(row) -> int | None:
    """その前提の**判定が読む窓**は何日か。書いていなければ `None`。

    前提の本文（`claim` / `falsified_if` / `note` / `needs[].what`）から
    「直近N日」を拾い、**いちばん狭い窓**を返します —— 狭いほうが効くので。
    """
    if not isinstance(row, dict):
        return None
    txt = " ".join(str(row.get(k) or "") for k in ("claim", "falsified_if", "note"))
    for n in (row.get("needs") or []):
        if isinstance(n, dict):
            txt += " " + str(n.get("what") or "")
    found = [int(x) for x in _WINDOW_DAYS.findall(txt)]
    return min(found) if found else None


def window_unreachable(rows, per_day: float | None = None) -> list[dict]:
    """**期日をいくら延ばしても満ちない要件**を並べる。

    条件が3つ揃ったときだけ ——
      (1) `needs[].need` が数で置いてある
      (2) その `count_expr` が**本数**を数えている（`counts_published_items`）
      (3) 前提の本文に**判定が読む窓**（「直近N日」）がある
    そのうえで `need > 窓 × PUBLISH_PER_DAY` なら、**永久に満ちません。**

    **日付を1つも見ません。** だから期日を延ばしても黙りません。
    """
    cap = float(PUBLISH_PER_DAY if per_day is None else per_day)
    out: list[dict] = []
    for r in rows or []:
        if not isinstance(r, dict) or r.get("closed_on"):
            continue
        w = window_of(r)
        if not w or w <= 0:
            continue
        for n in (r.get("needs") or []):
            if not isinstance(n, dict):
                continue
            need = n.get("need")
            if isinstance(need, bool) or not isinstance(need, (int, float)):
                continue
            if counts_published_items(n.get("count_expr")) is not True:
                continue
            allowed = w * cap
            if need > allowed:
                out.append({"claim": str(r.get("claim") or ""),
                            "deadline": str(r.get("deadline") or ""),
                            "watch": str(r.get("watch") or ""),
                            "lever": str(r.get("lever") or ""),
                            "need": need, "window_days": w, "allowed": allowed})
    return out


def window_unreachable_lines(rows, per_day: float | None = None) -> list[str]:
    """画面に出す形。**1件も無ければ、1行も出しません。**"""
    hits = window_unreachable(rows, per_day)
    if not hits:
        return []
    cap = float(PUBLISH_PER_DAY if per_day is None else per_day)
    out = [f"=== **期日を延ばしても満ちない要件: {len(hits)}件**"
           f"（規則 1日{cap:g}本 × 窓）===",
           "  **上の節とは別の軸です。** 上は「期日までに満ちるか」なので、"
           "**期日を延ばせば黙ります。** ここは**判定が読む窓**で解いているので、"
           "**延ばしても黙りません** —— 窓に入る本数のほうが足りていません。",
           "  **`falsified_if` に「満たなければ期限だけ延ばすこと」と書いてある前提は、"
           "ここに出たら永久に閉じません。**"
           " 直し方は2つ ——(1) 門の本数を、窓に入る数まで下げる（下げた分の"
           "**検出力**を `src/verdict_power.py` で示すこと）"
           " (2) 判定が読む窓を広げる（`falsified_if` の書き換え）。"]
    for h in sorted(hits, key=lambda x: str(x.get("deadline") or "")):
        out.append(f"  [!!] {h['deadline']}  {h['claim'][:52]}")
        out.append(f"        要件は **{h['need']:g}本** ／ 判定が読む窓は "
                   f"**直近{h['window_days']}日** ＝ 規則が窓に入れられるのは "
                   f"**{h['allowed']:g}本**。**{h['need']:g} > {h['allowed']:g} なので、"
                   f"待っても順番が入れ替わっても満ちません**")
        if h["lever"]:
            out.append(f"        この前提が止めている腕: **{h['lever']}**"
                       f"（`{h['watch']}`）")
    return out
