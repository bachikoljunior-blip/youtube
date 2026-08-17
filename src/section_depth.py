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
               limit: int = 5) -> list[tuple[str, int, int, float]]:
    """掘り甲斐の順に (モジュール, いまの節数, 中央値まであと何節, 値) を返す。

    `scores` は `family_perf.combined_map()`。無ければ全部 `base` で並べます
    （＝ 浅い順そのもの）。**中央値に届いている表は返りません。**
    """
    scores = scores or {}
    tgt = target_depth(all_sections)
    out = []
    for mod, n in depths(all_sections).items():
        room = tgt - n
        if room <= 0:
            continue
        out.append((mod, n, room, room * scores.get(mod, base)))
    out.sort(key=lambda r: (-r[3], r[0]))
    return out[:limit]


def report_lines(all_sections: dict[str, dict[str, str]],
                 scores: dict[str, float] | None = None,
                 base: float = 1.0,
                 limit: int = 5) -> list[str]:
    """`status.py` がそのまま印刷する行。**空のリストを返すことがあります。**"""
    med = median_depth(all_sections)
    tgt = target_depth(all_sections)
    # **`max()` を素で呼ばないこと**（検査が見つけた。`src/calc/` が読めない回は空で来る）。
    got = depths(all_sections)
    deep = max(got.items(), key=lambda kv: kv[1]) if got else ("—", 0)
    rows = candidates(all_sections, scores, base, limit)
    whole = candidates(all_sections, scores, base, limit=len(all_sections))
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
    for mod, n, gap, val in rows:
        out.append(f"       {mod:<12} いま{n:2d}節 → **あと{gap}節**（掘り甲斐 {val:.1f}）")
    out.append("    **掘って出なければ (A) に戻る合図です。**"
               "そのときは「この族は尽きた」と `docs/JOURNAL.md` に書くこと"
               "（書かないと次の回が同じ表を掘ります）。")
    return out
