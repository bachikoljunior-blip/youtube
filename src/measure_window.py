"""**測っている最中の日を、1か所で持つ。**

    from src import measure_window
    measure_window.inside("2026-08-20")           # True
    measure_window.check("2026-08-20", tool="…")  # SystemExit

## なぜ要るか（2026-08-18）

窓そのものは 2026-08-15 に `scripts/batch_build.py` へ入りました。理由も
そこに書いてあります —— **「文書には『実験の窓を踏まないこと』と3か所に
書いてあったが、守るのは毎回こちらの記憶だった」**ので、窓を機械に持たせた。

**その機械が、3つある入口の1つにしか付いていませんでした。**
2026-08-18 07:5x に実物を数えて分かったことです:

    scripts/batch_build.py --date <窓の中>    → 止まる（`check_window`）
    scripts/batch_build.py --hour 11          → **素通り**（`--date` が無いと呼ばれない）
    scripts/upload_only.py <題> "" 11         → **素通り**
    scripts/reschedule.py --move <id> <窓の中> → **素通り**

しかも `batch_build.py` の呼び出しは `if args.date:` の中にあり、
**日付を釘づけしない既定の道は一度も見ていません。**

いまそれが効いていないのは偶然です。窓の6日（08/18〜08/23）は
**たまたま6日とも 09:00 の1本だけ**で埋まっているので、
`next_publish_at(9)` が「埋まっている」と読んで飛ばします。
**`--hour 11` なら 08/18 11:00 が返ります**（`--hour` は
`batch_build.py` の使い方の2行目に載っている旗です）。

そして**この回の申し送りが、まさにその道を通れと言っていました** ——
「`reschedule.py` で予約の一部を前に詰めるだけで、公開ペースを
6.4 → 20本/日 に上げられます（追加の生成は0）」。
**前に詰める先は、いちばん空いている日** ＝ 08/18〜08/23 ＝ 窓の中です。
そのとおりに動くと、**測定を壊したことに誰も気づきません**
（`reschedule.py` は何も言わずに成功します）。

## 直す先を「入口」ではなく「合流点」にした理由

入口は3つですが、**予約時刻を決めているのは1か所**です
（`src.uploader.next_publish_at`）。入口ごとに門を足すと、
**次に入口を足した回が書き忘れます** —— このリポジトリでは
その形の落ち方が通算8件あり（`src/alerts.py` の「一覧が当たりを含まないまま育つ」、
`scripts/status.py` の「片方だけ」3件、`_covered_map` の import 漏れ）、
**毎回「規則を足す」ではなく「構造を1つにする」で直しています。**

`reschedule.py` だけは合流点を通りません（`publishAt` を直接書く）ので、
そこには明示的に置いてあります。**入口が2つになったのは、
道具の性質が違うから**です（作って予約する／既にある予約を動かす）。

## 止め方が2通りあるのは、投稿を止めないためです

**投稿が途切れるのが最大の損失**（`CLAUDE.md`）なので、
**自動で日を選ぶ道では例外を上げません。窓を飛ばして先へ進みます。**
止めるのは「その日だ」と名指ししたときだけ ——
名指しは意図なので、意図を確かめる価値があります。

    自動で探す（`--hour` だけ）      → **窓を飛ばす。** 投稿は続く
    日を釘づけ（`--date` / `--move`） → **止める。** `force` で通せる

## 窓が終わったら

**`until` を過ぎた窓は、自分で外れます**（2026-08-21 22:4x）。手で消さないこと。
`until` は**その窓が支えている前提の期限**なので、期限を書けば掃除が要りません。
判定は `docs/MEANS.md` M14 へ。

## 窓が **1本しか持てなかった**（2026-08-21 22:4x に直した）

`WINDOW` は文字列2つ ＝ **連続した1区間**でした。ところが実物は
**離れた2日**です（08/22 と 09/10）。区間で持つと、間の18日まで窓になります。
だから**窓は一覧で持ちます**（`WINDOWS`）。`WINDOW` は残しますが、
それは**いま効いている窓をまとめた幅**で、判定には使いません
（判定は必ず `inside()` ＝ 一覧を1つずつ見る側）。

## **なぜこの回に足したか**（近道ではなく、実際に踏みかけた）

`WINDOW` は 2026-08-19 に空にされ、そのまま**2つの測定日が機械の外**に出ました。
守っていたのは `reschedule.py --spread --since 2026-08-23` の
**`--since` を毎回手で打つ記憶**だけです。2026-08-21 22:3x に、
既定のまま素直に打った結果がこれです（**撃つ前の割り当てで見えた**）:

    python scripts/reschedule.py --spread --per-day 10 --since 2026-08-22
      → 08/22 = 25本 → **10本**   （`予約の間隔を1時間より詰めても…` 期限 09/05 の3日目）
      → 09/10 = 16本 → **10本**   （`1日に再生が付く本数の上限は上がらない` 期限 09/16）

**どちらも、その前提を測るために置いた日です。** 均せば前提は
「survived」になりますが、それは**測っていないだけ**です
（09/16 の前提は自分の反証条件の中でそう書いています ——
「数えられる日が1日も無ければ、それは survived ではなく **測っていない**」）。

**これは「気をつける」で直る形ではありません。** `--since` を打ち忘れる／
別の日を打つ／`--compact` を使う、で同じ所へ落ちます。**窓を機械に戻します。**
"""
from __future__ import annotations

import datetime as _dt

# **測っている最中の日**（JST・両端を含む）。`docs/MEANS.md` M14。
#
# **一覧で持ちます**（区間1本では足りなかった理由は上の docstring）。
# 1件は5つの字だけです:
#
#     from / to  守る日（両端を含む・JST）
#     until      **この日を過ぎたら自分で外れる。**支えている前提の期限を書くこと
#     label      止めるときに出す札（`M14` など）
#     why        **なぜ空けているか。**これが無いと、次の回が「なぜか出ない日」に見る
#
# **足すときは `config/hypotheses.yaml` の期限を写すこと。**
# 期限より短い `until` を書くと、前提が閉じる前に窓が開いて測定が壊れます。
JST = _dt.timezone(_dt.timedelta(hours=9))

WINDOWS: tuple[dict[str, str], ...] = (
    {
        "from": "2026-08-22", "to": "2026-08-22",
        "until": "2026-09-05",
        "label": "M14",
        "why": ("30分きざみ（1日16本以上）の**3日目**。前提"
                "「予約の間隔を1時間より詰めても、1本あたりの再生は落ちない」"
                "（期限 2026-09-05）は**3日そろわないと判定しない**と書いてあり、"
                "いま そろっているのは 08/20（25本）だけ ——"
                "08/21 は 15本 で 16 に1本届いていません。"
                "**ここを10本に均すと、判定できる日が1日も無くなります。**"),
    },
    {
        "from": "2026-09-10", "to": "2026-09-10",
        "until": "2026-09-16",
        "label": "M14",
        "why": ("上限（いま10本）を**上から**測り直す日（16本）。前提"
                "「1日に再生が付く本数の上限は、チャンネルが育っても上がらない」"
                "（期限 2026-09-16）の反証条件は**2026-09-11 までに 11本以上 出した日**"
                "を要求します。08/21 に予約を1日10本へ均したので、"
                "**この日を均すと、そういう日が二度と来ません。**"
                "そのとき出る「survived」は、前提自身の字で**「測っていない」**です。"),
    },
)


def _today_jst() -> str:
    return _dt.datetime.now(JST).strftime("%Y-%m-%d")


def active(today: str | None = None) -> tuple[dict[str, str], ...]:
    """**いま効いている窓だけ**を返す（`until` を過ぎたものは落ちる）。

    **手で消す作業を残さないため**です。窓を消す作業は「投稿を増やす作業」より
    いつも後回しになり、**残った窓は静かに予約を追い出し続けます**
    （このリポジトリでは、手で持つ一覧が腐る形の落ち方が通算8件）。
    """
    day = today or _today_jst()
    return tuple(w for w in WINDOWS if day <= w["until"])


def find(date_jst: str, today: str | None = None) -> dict[str, str] | None:
    """その日を守っている窓（無ければ `None`）。**理由ごと返します。**"""
    for w in active(today):
        if w["from"] <= date_jst <= w["to"]:
            return w
    return None


def _span(today: str | None = None) -> tuple[str, str]:
    """効いている窓**全部をまたぐ幅**。**判定には使わないこと**（間の日が入ります）。"""
    ws = active(today)
    if not ws:
        return ("", "")
    return (min(w["from"] for w in ws), max(w["to"] for w in ws))


# **後方互換**。`WINDOW` を読んでいる所（`batch_build.M14_WINDOW`・検査）が
# ありますが、**幅であって窓ではありません。**当たり判定は `inside()` を使うこと。
# **取り込んだ時刻で固まります**（走りっぱなしの手元では古くなる）。
WINDOW = _span()


def inside(date_jst: str, window: tuple[str, str] | None = None,
           today: str | None = None) -> bool:
    """`YYYY-MM-DD`（JST）が測定の窓の中か。

    **`window` を渡さなければ `WINDOWS` の一覧を1つずつ見ます**（`until` で
    切れたものは落ちています）。渡したときだけ、その区間1本で見ます ——
    検査と `batch_build.M14_WINDOW` がその形で呼びます。

    **空の窓 `("", "")` はどの日にも当たりません。** 窓が終わったときに
    片側だけ空にされても崩れないよう、ここで吸収しています
    （呼ぶ側に `if WINDOW:` を書かせると、**次に呼ぶ側を足した回が書き忘れます**）。
    """
    if window is None:
        return find(date_jst, today) is not None
    lo, hi = window
    if not lo or not hi:
        return False
    return lo <= date_jst <= hi


def _why(date_jst: str, window: tuple[str, str] | None,
         today: str | None = None) -> tuple[str, str, str]:
    """止めるときに出す（札・幅・理由）。区間で呼ばれたら理由は空。"""
    if window is None:
        w = find(date_jst, today)
        if w is None:
            return ("", "", "")
        return (w["label"], f'{w["from"]}〜{w["to"]}', w["why"])
    lo, hi = window
    return ("M14", f"{lo}〜{hi}", "")


def check(date_jst: str, *, force: bool = False, tool: str = "",
          window: tuple[str, str] | None = None,
          today: str | None = None) -> None:
    """**その日だと名指しした**ときだけ止める。`force` なら通す（言い残す）。

    自動で日を選ぶ道は、ここではなく `inside()` で**飛ばして**ください。
    止めると投稿が途切れます（module docstring）。

    **理由を必ず本文に出します**（2026-08-21 22:4x）。前は
    「M14 の比較の窓です」だけで、**なぜ空けているかは文書にしかありません**でした。
    止められた側は理由を探しに行かず、`force` を付けます。
    """
    if not inside(date_jst, window, today):
        return
    label, span, why = _why(date_jst, window, today)
    where = f"{tool} " if tool else ""
    if force:
        print(f"[window] **{date_jst} は {label} の測定日（{span}）です。**"
              f" {where}は force が付いているので続けます。"
              " **理由を docs/JOURNAL.md に書くこと。**", flush=True)
        return
    raise SystemExit(
        f"[window] **{date_jst} は {label} の測定日（{span}）です。**\n"
        f"        {where}で触ると、測定そのものが壊れます。\n"
        + (f"        {why}\n" if why else "")
        + "        窓の外の日へ置くか、支えている前提を閉じてから\n"
        "        src/measure_window.py の WINDOWS から外すこと\n"
        "        （`until` を過ぎた窓は自分で外れます）。\n"
        "        どうしても触るなら force（旗の名前は道具ごとに違います）。"
    )
