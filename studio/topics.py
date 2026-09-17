"""**題材の段**（2026-09-17 17:4x・optimizer・Fable 5.1・ultracode）。**API 0単位。**

`data/niche_corpus.jsonl`（もう disk に在る 659行・`id` で重複を落として長尺 335本）を
**検索語ごと**に割ると、**中央値が 3桁 違います**:

    最大        本   中央      検索語
    5,124,861  38   605,548   年金 手取り いくら
    2,023,357  36   325,807   退職金 税金 いくら
    4,422,714  34    78,823   加給年金 いくら
    1,501,667  39    68,276   所得税 控除 節税
      548,720  21    59,469   遺族年金 いくら 計算
    ------------------------------------------------
      228,855  14     4,585   再就職手当 計算
      129,557  31     3,387   変動金利 5年ルール 未払利息
       54,238  26     1,588   標準報酬月額 計算
      185,938  31     1,332   ふるさと納税 上限 計算
      180,901  40     1,093   不動産取得税 計算
      457,339  25       190   医療費控除 いくら戻る

**＝ 上の段と下の段で、中央が 100〜3,000倍 違います。**
この repo がこれまでに測ったどの腕（題の形 1.5倍・透かし・固定コメント・転換率 最良で 3.8倍）よりも
**2桁 大きく、そして 0単位・0秒 で選べます** —— 変わるのは「どの台本を書くか」だけ。

**なぜ中央で見るか（最大で見ないこと）**: 同じ表の `医療費控除 いくら戻る` は
**最大 457,339・中央 190** です。＝ その段は「当たりが 1本 在る」だけで、**面が無い**。
対して `年金 手取り いくら` は **38本 の中央が 605,548** ＝ **半分 が 60万回 を越えている ＝ 面が在る。**
`dense`（面が在る）と `lottery`（当たりだけ）を分けるのはこの比（`median / max`）です。

**この数の読み方（**上限**であって、期待値ではありません）**:
corpus は**検索の結果**から集めています。検索は人気の順に並ぶので、**どの語の数も上振れします。**
＝ 中央 605,548 は「この題材で書けば 60万回 来る」ではありません。
**言えるのは「段どうしの比べ」だけ** —— 同じ集め方をした 2つ の語で、
一方の上位の中央が 190 なら、**その語には面が無い**（上振れした数でさえ 190）。

**覆る条件**:
 (1) **うちの長尺が、段の高い語で 3本 続けて 25回 以下**なら、段は原因ではない
     ＝ そのときは GOAL (4-i) の枝（口・中身）へ戻すこと。**この段は「題材を外している」までしか言いません。**
 (2) corpus を引き直して（`niche_ceiling` / `peers`）**同じ語の中央が 1桁 動いたら**、
     この表ではなくそのときの数が正本（この module は毎回 disk から数え直すので、引き直せば自動で直ります）。
 (3) **`q` は「その本を見つけた検索語」であって「その本の題材」ではありません。**
     1本 が 2つ の語から出てくることが在ります（`id` で重複は落としてありますが `q` は最初の 1つ になる）。
     段の順が入れ替わるほどの取りこぼしが出たら、`q` ではなく題の語で割り直すこと。
"""
from __future__ import annotations

import json
import statistics
from collections import defaultdict

from .common import ROOT

#: corpus の置き場（`niche_ceiling` / `peers` が書く）。
#: **`common.DATA`（`data/studio/`）ではありません** —— corpus は `data/` の直下です。
CORPUS = ROOT / "data" / "niche_corpus.jsonl"

#: `median / max` がこれ以上なら **面が在る**（`dense`）。下なら **当たりだけ**（`lottery`）。
#: 0.10 は上の表で段が割れる所（`遺族年金` 0.108 が `dense` の下端・`加給年金` 0.018 が `lottery`）。
DENSE_RATIO = 0.10
#: この本数に満たない語は段を言わない（中央が 1〜2本 で決まってしまう）。
MIN_BOOKS = 5


def rows(path=None) -> list[dict]:
    """corpus の**長尺だけ**を、`id` で重複を落として返す（**API 0単位**・disk だけ）。

    重複は本物です —— 同じ本が引くたびに 1行 入ります（実測: `年金・給付金完全攻略` の
    4,402,748 / 4,415,973 / 4,422,714 は**同じ 1本**の 3回 の引き）。
    落とさずに数えると、**引き直した本ほど重く**なります。
    """
    p = path or CORPUS
    if not p.exists():
        return []
    seen: dict[str, dict] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("form") == "short" or not r.get("id"):
            continue
        # あとの行ほど新しい ＝ 再生は増える側なので、あとの行で上書きする。
        seen[r["id"]] = r
    return list(seen.values())


def by_query(path=None) -> list[dict]:
    """検索語ごとの段。**中央の大きい順**。

    返り 1件: `{"q", "n", "median", "max", "ratio", "dense"}`。
    """
    out = []
    groups: dict[str, list[int]] = defaultdict(list)
    for r in rows(path):
        groups[r.get("q") or "?"].append(int(r.get("views") or 0))
    for q, vs in groups.items():
        if len(vs) < MIN_BOOKS:
            continue
        mx = max(vs)
        md = int(statistics.median(vs))
        ratio = (md / mx) if mx else 0.0
        out.append({"q": q, "n": len(vs), "median": md, "max": mx,
                    "ratio": round(ratio, 4), "dense": ratio >= DENSE_RATIO})
    out.sort(key=lambda d: -d["median"])
    return out


def tier_of(text: str, path=None) -> dict | None:
    """**その題が、どの段に居るか。** `text` には題＋tags を渡してよい（つないだ 1本の字で見ます）。

    当て方は **`q` の頭の語（題材の名）が字のまま在ること**。それが在る段だけを候補にし、
    残りの語の重なりが多い順、同じなら中央の大きい順で選ぶ。
    返りに **`hits`**（重なった語の数・頭を含む）と **`strong`**（`hits >= 2`）を足して返す。

    **`strong` が False の答えを、段の判定に使わないこと**（2026-09-17 18:0x に、
    道具を配線した直後の実物で踏んだ）: うちの長尺 **11本 が 11本 とも
    `年金 手取り いくら`（中央 605,548・面）に当たりました。
    **`年金` は、この族のほとんどの題に入っている語**なので、
    頭の錨だけでは `扶養親族等申告書`（年金148万円以上の方へ）も `高年齢求職者給付金` も
    `繰上げ` も、全部いちばん高い段に化けます。
    **＝ 頭 1語 だけの一致は「その段に居る」ではなく「否定できない」までです。**

    **頭の錨そのものは要ります**（`hits` だけで選ぶと外れる。同じ回に踏んだ実物:
    `【退職金2000万円】…の手取り` が `退職金 税金 いくら` ではなく `年金 手取り いくら` に当たった
    —— どちらも 1語 の重なりで、中央の大きいほうが勝つ）。**2つ を両方 置くこと。**

    **`None` は「段が低い」ではなく「この corpus では測っていない」**です
    （実測: `医療費が1年で10万円をこえたら` は `医療費控除` を字として持たないので `None`）。

    **覆る条件**: `strong` が True の本が **10本 たまっても、段の高い側と低い側で
    実測の再生が分かれない**なら、割り方（`q` の語）がこの族に対して粗すぎる
    ＝ そのときは題の語で corpus を割り直すこと（module の註 (3)）。
    """
    best, best_key = None, ()
    for t in by_query(path):
        words = t["q"].split()
        if not words or words[0] not in text:
            continue
        hits = 1 + sum(1 for w in words[1:] if w in text)
        key = (hits, t["median"])
        if best is None or key > best_key:
            best, best_key = t, key
    if best is None:
        return None
    return dict(best, hits=best_key[0], strong=best_key[0] >= 2)


def line(path=None) -> str:
    """毎周の 1行（**API 0単位**）。上の 3段 と、下の 1段 を出す。"""
    ts = by_query(path)
    if not ts:
        return "題材の段: corpus が無い（`peers --force` で引くこと・`studio/topics.py`）"
    dense = [t for t in ts if t["dense"]]
    head = "／".join(f"{t['q']} **{t['median']:,}**" for t in ts[:3])
    dead = ts[-1]
    return (f"**題材の段**（corpus {sum(t['n'] for t in ts)}本・長尺・中央・**API 0単位**）: "
            f"上位 {head} ／ いちばん下 {dead['q']} {dead['median']:,} "
            f"＝ **{ts[0]['median'] // max(dead['median'], 1):,}倍**。"
            f"面が在る段（`dense`）は {len(dense)}/{len(ts)}語。"
            f"**次の台本の題材は、ここの上から採ること**（`studio/topics.py`）")
