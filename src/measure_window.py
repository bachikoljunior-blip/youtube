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
#     claim      **その期限の持ち主**（`config/hypotheses.yaml` の `claim` の全文）
#     label      止めるときに出す札（`M14` など）
#     why        **なぜ空けているか。**これが無いと、次の回が「なぜか出ない日」に見る
#
# **足すときは `config/hypotheses.yaml` の期限を写すこと。**
# 期限より短い `until` を書くと、前提が閉じる前に窓が開いて測定が壊れます。
#
# ## `claim` は 2026-08-28 に足しました（**この形の4件目と5件目を踏んで**）
#
# それまで検査は「`until` が**開いている前提のどれかの期限**と一致するか」しか
# 見ていませんでした。**日付が合っていれば、持ち主が誰でも通ります。**
# このファイルの註は、その穴を3回 記録しています ——
# 08-29 が「WATCH の伸びは複利」の期限と**たまたま**一致して通っていた件、
# 09-05 が「長尺の面」の期限と**たまたま**一致して通っていた件、
# そして 09-16 → 09-10 が**動かされなかった**件。
# 註自身が「検査が『どの前提の期限か』まで見ていないので、
# **この形はまた起きます**」と書いており、**そのとおり 08-28 に2件 同時に出ました**:
#
#     day_cap          前提 08-28 ／ 窓 08-27  ← 答えが読める 16:00 JST の 16時間 前に外れる
#     density_engaged  前提 10-03 ／ 窓 10-02  ← **08-27 の陰に隠れていた**（検査は最初の1件で止まる）
#
# **`claim` を書けば、一致は偶然では起きません。**
# `tests/test_measure_window.py` が「その `claim` の前提が在るか・開いているか・
# その期限と `until` が同じか」の3つを見ます。**`claim` を消さないこと。**
JST = _dt.timezone(_dt.timedelta(hours=9))

WINDOWS: tuple[dict[str, str], ...] = (
    # **2026-08-27 の窓（`day_cap`）は外しました**（2026-08-29・最適化の回）。
    #
    # 支えていた前提「1日に再生が付く本数の上限は『その日の本数（10本）』であって、
    # 時刻の窓ではない」は **2026-08-28 に判定ずみ**（`closed_on: 2026-08-28`・
    # `outcome: mixed`）。`until` も 08-28 なので `active()` からは既に外れており、
    # **予約を追い出す側では、もう何もしていません。**
    # 残っていたのは `tests/test_measure_window.py::test_実物の窓は前提の期限を写している`
    # だけで、**08-28 に閉じてから 1日 赤のまま**でした
    # （**すぐ下の 2026-08-22 の窓と、まったく同じ形の3件目**）。
    #
    # **切り分けそのものは、まだ終わっていません** —— `day_cap.window()` は
    # 依然 `confounded` で、生きている前提は
    # 「1日に再生が付く本の集合は、左端つきの帯（08:59〜13:30 JST）で決まる」
    # （期限 **09-03**）のほう。**その日を守るのは `split_day_window()`** で、
    # 日付を写さず `day_cap.booked_split_day()` に毎回 聞きます。
    # **だからここに手で書き足さないこと**（この一覧が腐る形が通算8件）。
    #
    # **2026-08-22 の窓は外しました**（2026-08-25 22:5x）。
    #
    # 支えていた前提「予約の間隔を1時間より詰めても、1本あたりの再生は落ちない」は
    # **2026-08-24 に判定ずみ**（`closed_on: 2026-08-24`・verdict は mixed）。
    # 閉じた前提の窓は、`until`（09-05）まで**予約を追い出し続けるだけ**です。
    #
    # **なぜ今まで検査に映らなかったか。** 検査は「`until` が**開いている前提の
    # どれかの期限**と一致するか」しか見ません。09-05 は
    # **別の前提**（長尺の面＝サムネのインプレッション）の期限でもあったので、
    # **たまたま通っていました。** その別の前提の期限を 09-04 へ縮めた回に落ちて、
    # 初めて「閉じた前提の窓が残っている」ことが見えました ——
    # **上の 08-27 の窓が 08-29 で踏んだのと、まったく同じ形の2件目**です。
    #
    # 検査が「どの前提の期限か」まで見ていないので、この形はまた起きます。
    # **2026-09-10 の窓（M14）は外しました**（2026-09-01）。**4件目です。**
    #
    # 支えていた前提「1日に再生が付く本数の上限（いま10本）は、チャンネルが
    # 育っても上がらない」は **`closed_on: 2026-08-31`**（`config/hypotheses.yaml`）。
    # 上の 2026-08-22 の窓とまったく同じ形で、**閉じた前提の窓が残っていました。**
    #
    # **今回はもう1つ理由があります** —— この窓が空けていたのは
    # 「**16本 公開する日**」で、同じ 08/31 にオーナーが公開を **1日1本**に
    # 固定しました（`src/house_rule.PUBLISH_PER_DAY`）。
    # **その日は二度と来ません。** 前提の `needs` は同じ日に書き換えられて
    # （公開ずみ8日ぶんで判定する形へ）閉じたのに、**窓だけが残り、
    # 09/10 を空けさせ続けていました** —— 規則1（1日1本）の下では、
    # それは「その日 1本も出さない」を道具が要求している状態です。
    #
    # `tests/test_measure_window.py::test_実物の窓は前提の期限を写している` が
    # **08/31 から赤で立っており**、文面は「閉じたなら窓も外すこと」でした。
    #
    # **覆る条件**: 規則が緩んで 11本以上 出せる日が作れるようになり、かつ
    # 同じ前提を開き直したとき。そのときは `claim` を `hypotheses.yaml` から
    # **全文で写して**、`until` をその期限に合わせること（写さないと、この一覧が
    # また腐ります —— 通算8件）。
    # **2026-09-25〜26 の窓（`density_engaged`）は外しました**（2026-09-01・最適化の回）。
    #
    # 支えていた前提「engaged 比率は、その日に出した本数が増えると下がる」は
    # **2026-09-01 に判定ずみ**（`889d1f85`・`closed_on: 2026-09-01`・`survived`）。
    # **ところが窓は `until: 2026-10-03` なので `active()` にまだ乗っており、**
    # `reschedule.py --compact` と `live_plan()` は、**終わった実験のために
    # 09/25〜26 の2日を空けたまま**でした（`tests/test_measure_window.py` も
    # 11時間 赤のまま。**この形の落ち方は、これで通算9件目です**）。
    #
    # **そして規則1（1日1本・`src/house_rule.py`）の下では、
    # この窓の中身そのものが消えています** —— 守っていたのは
    # 「1〜2本/日 しか入っていない唯一の日」で、いまは**どの日もそうです。**
    # 対照として特別なところが、もう1つも残っていません。
    #
    # **覆る条件**: 同じ前提を開き直したとき。そのときは `claim` を
    # `hypotheses.yaml` から**全文で写して**、`until` をその期限に合わせること。
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


def split_day_window(today: str | None = None) -> dict[str, str] | None:
    """**`day_cap` の切り分けの日**を、窓として出す（`WINDOWS` に手で書かない側）。

    ## なぜ手の一覧に足さないのか（2026-08-27 に足した）

    `src/day_cap.py` は毎回、**自分で切り分けの日を選んで印字しています**
    （`booked_split_day()`。「`08:59` より前に出す本がある、いちばん早い予約日」）。
    そして `scripts/eta.py` の出力の中で、こう言っています:

        **その日はもう予約されています: 2026-09-02**（10本・うち 2本 が 08:59 より前）
        [!] **答えが返るまで、他の日の本数を増やさないこと** ——その日が対照です。

    **守る仕掛けは、このファイルにありました。繋がっていませんでした。**
    `reschedule.py --spread/--compact` ／ `live_slots.py --apply` ／
    `batch_build` の `live_plan()` は、どれも `measure_window.inside()` を見て
    避けます —— **`WINDOWS` に書いてある日だけを。**

    **同じことが 08/24 に起きています。** `reschedule.py --spread` が
    2026-08-27 を「14本 ＝ 上限超え」と読んで本を後ろへ送り、
    窓に残ったのは **1本だけ**でした（`WINDOWS` の 08-27 の項に実測が残っています）。
    そのときの直しは「**この一覧に入れておけば、どの旗で撃っても止まります**」
    ——**入れる作業が手だったので、次の切り分けの日には引き継がれませんでした。**

    実測 2026-08-27（**朝の回**）: 対照日 **2026-09-02** は `WINDOWS` に無く、
    予約は **10本／13:30 より前 7本／08:59 より前 2本**。
    この形は (A) 1日10本 なら **10本 生き**、(B) 13:30 の窓 なら **7本 生き**ます
    ——**3本の差でしか切り分かりません。** どれか1本が動けば消えます。

    実測 2026-08-27（**昼の回。上の 09/02 は、そもそも対照日ではありませんでした**）:
    `booked_split_day()` が `<= today` で今日を飛ばしていたので、
    **その日の朝に 09/02 へ移っていました。** 08/27 自身の予約は
    **19本・05:00 から30分きざみ・同分の組 0** で、
    (A) なら **10本**・(B) なら **18本** ——**差 8本**。守るべき日は 08/27 でした。
    （`day_cap.booked_split_day()` の docstring に、直した中身があります）

    **だから日付を写しません。** 選んでいる側（`day_cap`）に毎回 聞きます。

    ## いつ消えるか（**手で消す作業を残さない**）

    - `day_cap.window()` が **切り分け済み**を返したら、その場で消えます
    - 切り分けの日が過ぎて `booked_split_day()` が別の日を返したら、そちらへ移ります
    - `day_cap` が読めない回は **`None`**（窓を増やさない）。
      **黙って全部を守る側に倒さないこと** —— 置き先が消えると投稿が止まります

    ## 覆る条件

    **`until` は「読める日」（`answer`）です。** 生きた本数を読むまで守ります。
    読んだあとも守り続けると、対照日のぶんだけ枠が死んだままになります ——
    `day_cap.window()` が決まれば自動で消えるので、**手で消さないこと。**
    """
    if DISABLE_DYNAMIC:
        return None
    day_now = today or _today_jst()
    if day_now in _SPLIT_CACHE:
        return _SPLIT_CACHE[day_now]
    out = _split_day_window_uncached(today)
    _SPLIT_CACHE[day_now] = out
    return out


#: `split_day_window()` の覚え書き。**1周のあいだだけ**（プロセスが変われば消えます）。
#  `find()` は置き先を探すたびに呼ばれます（`live_plan()` は最大90日ぶん）。
#  中身は `data/uploaded.jsonl` を読むので、**掛け算になると1周ぶんの時間が飛びます。**
_SPLIT_CACHE: dict[str, dict[str, str] | None] = {}

#: **検査のあいだ、動的な窓を止める旗**（`tests/conftest.py` が立てます）。
#
# `WINDOWS` は手で書いた日付なので、`inside()` は純粋な関数でした。
# **動的な窓を足した瞬間、`inside()` は本物の予約（`data/uploaded.jsonl`）に
# 依ります** —— 検査が「適当な未来の日」として選んだ日付が、
# たまたまその日の対照日と一致すると、**関係のない検査が赤くなります。**
# 実測 2026-08-27: `tests/test_live_slots.py` の5件が
# `2026-09-02` を定数に使っていて、まとめて落ちました。
#
# **呼ぶ側に「その日は避けて書いてね」と約束させないこと** ——
# `tests/conftest.py` の冒頭がまさにその理由で書かれています
# （「一覧を足した回が必ず片方だけ忘れる」通算7回）。
#
# **この旗を production で立てないこと。** 立てると対照日が守られません。
DISABLE_DYNAMIC = False


def _split_day_window_uncached(today: str | None = None) -> dict[str, str] | None:
    try:
        from src import day_cap                                 # noqa: PLC0415

        w = day_cap.window()
        if isinstance(w, dict) and w.get("verdict"):
            # **もう切り分いています。** 守る理由がありません。
            return None
        first_pub = (w or {}).get("first_pub")
        # **当てはめ済みの2つのモデルの値を渡します** —— 渡さないと
        # `booked_split_day()` が `window()` をもう1度 呼び、`data/views.jsonl`
        # （2万行）を2度 読みます。
        t = str((w or {}).get("T") or "")
        b = day_cap.booked_split_day(
            first_pub,
            c=(w or {}).get("C"),
            t_min=(int(t[:2]) * 60 + int(t[3:])) if len(t) == 5 else None,
        ) if first_pub else None
    except Exception:                                           # noqa: BLE001
        return None
    if not b or not b.get("day"):
        return None
    day = str(b["day"])
    until = str(b.get("answer") or day)
    day_now = today or _today_jst()
    if day_now > until:
        return None
    return {
        "from": day, "to": day, "until": until,
        "label": "day_cap_split",
        "why": ("**`day_cap` の (A)/(B) を切り分ける対照日**です"
                f"（`src/day_cap.booked_split_day()` が選んでいます）。"
                f"予約 {b.get('total')}本・うち {b.get('before')}本 が"
                f" {first_pub} より前 → **(A) 本数なら {b.get('count')}本 生き ／"
                f" (B) 窓なら {b.get('window')}本 生き**（差 {b.get('gap')}本）。"
                "**この形でしか切り分かりません。**\n"
                f"生きた本数を読めるのは **{until} {b.get('answer_at', '')}** 以降"
                f"（その日の最後の本が 齢 {day_cap.MIN_AGE_H:.0f}時間 になる時刻。"
                "**Analytics の3日遅れは掛かりません** —— `data/views.jsonl` は"
                " Data API で積んでいます。2026-08-27 まで +5日 を足していました）。"
                "**それまで、この日の本数も時刻も動かさないこと。**\n"
                "**この窓は手の一覧（`WINDOWS`）にありません** —— "
                "選んでいるのは `day_cap` 側なので、毎回そちらに聞いています"
                "（2026-08-24 に、手の一覧へ写し忘れた 08/27 が "
                "`reschedule --spread` に 14本 → 1本 まで削られました）。"),
    }


def find(date_jst: str, today: str | None = None) -> dict[str, str] | None:
    """その日を守っている窓（無ければ `None`）。**理由ごと返します。**

    **手の一覧（`WINDOWS`）だけでは足りません。** `day_cap` が毎回 自分で選ぶ
    切り分けの対照日も、ここで守ります（`split_day_window()`）。
    """
    for w in active(today):
        if w["from"] <= date_jst <= w["to"]:
            return w
    dyn = split_day_window(today)
    if dyn is not None and dyn["from"] <= date_jst <= dyn["to"]:
        return dyn
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
