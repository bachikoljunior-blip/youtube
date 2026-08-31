"""**閉じた判定を開け直すかどうかを、量の伸びと切り分けて決める。**（2026-08-31）

    python -m src.reversal          # 実測の2件を並べて出す（API 0単位）

## なぜ要るか（**同じ日に、同じ形の条件が2件 発火しました**）

`config/hypotheses.yaml` には「覆る条件」が 40件 あります。そのうち
**件数の絶対値で書かれたもの**は、**分母が伸びれば、効果が無くても必ず発火します。**
2026-08-31 に、その形の2件が同時に発火しました:

    endcard        「チャンネル全体のコメントが、28日窓で**1件でも**付いたとき」
    RELATED_VIDEO  「90日窓の RELATED_VIDEO が **10 以上**になったとき」

**どちらも、閉じたときは 0件／6再生 でした。** そして 2026-08-31 の実測は
コメント 1件・RELATED_VIDEO 47再生 —— **条件の字面はどちらも満たしています。**

## それでも答えは同じではありません。**そこが要点です**

**量だけで伸びたのか、占有そのものが動いたのか**を分けると、逆の答えが出ます:

    endcard        コメント 0/20,332 → 1/56,751
                   量だけなら 0.0 のはず → 実測 1件。**占有 0.0018%
                   ＝ 判定文の目安 0.2% の 1/114**   → **覆らない**

    RELATED_VIDEO  6/21,823 → 47/78,505
                   量だけなら 21.6 のはず → 実測 **47（2.18倍）**
                   直近7日は 25/11,928 ＝ **7.62倍**       → **覆る**

**「件数の条件を全部 率に直す」ではありません。** それをやると
RELATED_VIDEO の側を取り逃がします（占有 0.06% は、率だけ見れば小さい）。
**見るのは「閉じたときの占有と比べて、いま何倍か」**です。

## 使い方

    from src import reversal
    reversal.volume_ratio(before=(6, 21823), now=(47, 78505))   # → 2.18

`before` は**閉じた回の実測**（そのとき数えた件数と、その窓の分母）。
`now` は同じ形で数え直したもの。**分母は同じ種類のものを渡すこと** ——
片方をチャンネル全体、片方を群の合計にすると、比は意味を失います。

## これが覆る条件（**この道具そのものの**）

- `RATIO_GATE`（2.0倍）は**実測から引いた線ではありません。** 「量の2倍」を
  超えたものだけを見る、という取り決めです。**外れた側を2件 数えたら引き直すこと。**
- 閉じたときの分母が小さいと（`before` の分母が3桁など）、比は跳ねます。
  **`MIN_BEFORE_TOTAL` を下回る `before` では、比を返さず `None` を返します。**
- **占有が動いても、それが目標に効くとは限りません。** この道具が言うのは
  「開け直して測り直す値打ちがあるか」までで、**効くかどうかは判定のほうの仕事**です。
"""
from __future__ import annotations

#: 量だけで説明できる分の何倍を超えたら「占有が動いた」と見るか。
#: **実測ではなく取り決めです**（上の「覆る条件」）。
RATIO_GATE = 2.0

#: `before` の分母がこれを下回ると、比が跳ねるので返しません。
MIN_BEFORE_TOTAL = 1000


def volume_ratio(before: tuple[int, int], now: tuple[int, int]) -> float | None:
    """**量だけで伸びた場合の予測に対して、実測は何倍か。**

    `before` / `now` はどちらも `(件数, 分母)`。**同じ種類の分母を渡すこと。**

    返り 1.0 ＝ 量どおり（占有は動いていない）。2.18 ＝ 量の 2.18倍。
    `before` の件数が 0 のときは、予測が 0 になって比が定義できないので
    `None` を返します（**そこは率で見ること** —— `endcard` がその形です）。
    """
    b_count, b_total = before
    n_count, n_total = now
    if b_total < MIN_BEFORE_TOTAL or b_count <= 0 or n_total <= 0:
        return None
    predicted = b_count / b_total * n_total
    if predicted <= 0:
        return None
    return n_count / predicted


def share_moved(before: tuple[int, int], now: tuple[int, int]) -> dict:
    """`volume_ratio` を、そのまま印字できる形にして返す。

    `moved` が真なら「**量では説明できない**」＝ 開け直して測り直す値打ちがある。
    """
    ratio = volume_ratio(before, now)
    b_count, b_total = before
    n_count, n_total = now
    b_share = (b_count / b_total) if b_total else 0.0
    n_share = (n_count / n_total) if n_total else 0.0
    if ratio is None:
        return {
            "moved": False, "ratio": None, "before_share": b_share, "now_share": n_share,
            "line": (f"比が出せません（閉じたときが {b_count}/{b_total:,}）。"
                     f"**率で見ること** —— いま {n_share*100:.4f}%"),
        }
    return {
        "moved": ratio >= RATIO_GATE, "ratio": ratio,
        "before_share": b_share, "now_share": n_share,
        "line": (f"閉じたとき {b_count}/{b_total:,}（{b_share*100:.4f}%）→ "
                 f"いま {n_count}/{n_total:,}（{n_share*100:.4f}%）＝ "
                 f"量だけなら {b_count/b_total*n_total:.1f} のはず → **{ratio:.2f}倍**"
                 + ("  → **覆る（測り直すこと）**" if ratio >= RATIO_GATE
                    else f"  → 覆らない（門は {RATIO_GATE:.1f}倍）")),
    }


#: **2026-08-31 の実測。** 数え直したら、ここも直すこと。
#: どちらも `config/hypotheses.yaml` の閉じた前提で、**同じ日に条件が発火**しています。
MEASURED = {
    "endcard（末尾の問いかけ → コメント）": {
        "before": (0, 20332),   # 2026-08-20 の判定時・28日窓
        "now": (1, 56751),      # 2026-08-31・問いかけ型 472本
    },
    "RELATED_VIDEO（推薦面は自力で伸びるか）": {
        "before": (6, 21823),   # 2026-08-20 の判定時・90日窓
        "now": (47, 78505),     # 2026-08-31・90日窓
    },
    "RELATED_VIDEO（直近7日で見ると）": {
        "before": (6, 21823),
        "now": (25, 11928),     # 2026-08-31・7日窓
    },
}


def main() -> int:
    print("=== 閉じた前提の『覆る条件』を、量の伸びと切り分ける（API 0単位）===")
    for name, m in MEASURED.items():
        r = share_moved(m["before"], m["now"])
        print(f"\n  {name}")
        print(f"    {r['line']}")
    print("\n  **同じ日に、同じ字面の条件が2件 発火して、答えは逆になりました。**")
    print("  件数の条件を一律に率へ直すと、RELATED_VIDEO の側を取り逃がします"
          "（占有 0.06% は率だけ見れば小さい）。**比べるのは、閉じたときの占有です。**")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
