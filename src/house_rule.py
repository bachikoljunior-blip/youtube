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
