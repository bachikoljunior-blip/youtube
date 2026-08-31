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


def is_stockpile(row: dict, today: str | None = None) -> bool:
    """**その控えの行は「作り置き」か。**（`data/uploaded.jsonl` の1行）

    作り置きの条件は**2つとも**満たすことです:

        1. まだ公開されていない（`at` が今日より後）
        2. **規則より前に作った**（`uploaded_at` が `STOCKPILE_SINCE` より前）

    2 が要ります。**規則の下で作った本まで落とすと、これから出す1本が
    供給から消えます** —— そうなると「1日1本 作っても面は 0回/日」と
    印字することになり、実物と食い違います。

    読めない行（`at` が無い・形が違う）は **False**（＝落とさない）。
    **測っていないことを、落とす側に倒さないこと。**
    """
    if STOCKPILE_IS_SUPPLY:
        return False
    at = str(row.get("at") or "")[:10]
    if not at:
        return False
    if at <= (today or _jst_today()):
        return False                      # もう公開になっている ＝ 実績
    made = str(row.get("uploaded_at") or "")[:10]
    if not made:
        return True                       # 作った日が分からない未来の予約 ＝ 作り置き
    return made < STOCKPILE_SINCE


def drop_stockpile(rows, today: str | None = None) -> list:
    """**控えの行から、作り置きを落とす。** 残るのが供給です（規則2）。"""
    return [r for r in rows if not is_stockpile(r, today)]
