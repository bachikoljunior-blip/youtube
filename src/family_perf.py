"""**公開ずみの実績を「制度の族」ごとに集め、次に何を作るかの順番に使う。**

## なぜ要るか（2026-08-16 に測って足した）

`scripts/batch_build.pick()` は、これまで **`config/topics.yaml` の手書きの
`score`** だけで順番を決めていました（実測: 91件中64件が `1.0` のまま）。
**実績を1つも見ていません。** つまり、どれだけ公開しても、次に何を作るかは
最初に書いた見立てのままです。

実物を集めると、族ごとの engaged 比率は **4倍ちがいます**（2026-08-16、
`data/scan.jsonl` の最新点・再生30以上の13本）:

    shitsugyo 45.6% ／ nenkin 45.5% ／ furusato 38.7% ／ zangyo 33.6%
    iryohi 27.9% ／ jutaku 19.1% ／ kojo 17.6%

`scripts/status.py` の実測で **engaged／再生 の順位相関は +0.51**（再生数と
同じ向きに動く唯一の率）で、**登録も engaged の高い族からしか入っていません**
（5人中4人が nenkin・shitsugyo・iryohi）。**上位と下位を同じ確率で作り続ける
理由は、どこにもありませんでした。**

## 割り引いて読むこと（**ここを外すと n=1 の雑音に固定されます**）

- **族あたり1〜3本しかありません。** 生の比率をそのまま順番にすると、
  たまたま伸びた1本で族が決まります。だから**全体平均へ縮めて**から使います
  （`SHRINK_VIEWS` 再生ぶんの事前分布。族の再生がこれと同じなら半々）
- **測っていない族は「悪い」ではありません。** 縮めた結果は全体平均そのもの
  になるので、**真ん中の順位から試されます**（探索を殺さない）
- **交絡は残ります。** 公開時刻・尺・配信の広さ・題の言い回しが混ざっています。
  これは「因果」ではなく**事前分布**で、外れたら下の覆る条件で戻します

**覆る条件**: この順番で作った本の engaged 比率の中央値が、
`config/hypotheses.yaml` の期限（2026-08-30）に、それ以前の中央値を
**下回っていたら、`pick` を手書き `score` だけに戻すこと。**
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN = ROOT / "data" / "scan.jsonl"
UPLOADED = ROOT / "data" / "uploaded.jsonl"

#: 事前分布（全体平均）へ寄せる強さ。族の再生数がこれと等しいとき、生の比率と
#: 全体平均が半々になる。**1本ぶんの再生（約1,300）より大きく取っています** ——
#: 1本しか無い族が、その1本だけで順番を決めないようにするため。
SHRINK_VIEWS = 1500

#: 率が壊れるので、分母の小さい本は数えない（`status.py` の全走査と同じ線）
MIN_VIEWS = 30


@dataclass(frozen=True)
class Family:
    calc: str
    videos: int
    views: int
    engaged: int
    subs: int

    @property
    def raw_rate(self) -> float:
        return self.engaged / self.views if self.views else 0.0


def _latest_scan(path: Path | None = None) -> dict[str, dict]:
    """`data/scan.jsonl` の**最後の点**から、動画ごとの数字を取り出す。"""
    path = path or SCAN
    if not path.exists():
        return {}
    last = None
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                last = line
    if not last:
        return {}
    values = json.loads(last).get("values", {})
    out: dict[str, dict] = {}
    for key, value in values.items():
        if not key.startswith("動画."):
            continue
        rest = key[len("動画."):]
        cut = rest.rfind(".")
        if cut < 0:
            continue
        out.setdefault(rest[:cut], {})[rest[cut + 1:]] = value
    return out


def _calc_of_topic(topic_id: str, by_id: dict[str, str], known: set[str]) -> str:
    """テーマID → calc。**台帳に無い古いテーマも拾う。**

    `config/topics.yaml` から消えたテーマ（公開ずみで役目の終わったもの）が
    実績の側には残ります。**そこを落とすと、いちばん古い＝いちばん実績のある
    本が数から消えます。** 先頭の `s-` を外した最初の語で当てにいく。
    """
    if topic_id in by_id:
        return by_id[topic_id]
    stem = re.sub(r"^s-", "", topic_id or "")
    head = re.split(r"[-_]", stem)[0] if stem else ""
    return head if head in known else ""


def _video_calc(known: set[str]) -> dict[str, str]:
    by_id: dict[str, str] = {}
    try:
        from . import config

        for topic in config.load_topics()["topics"]:
            if topic.get("calc"):
                by_id[topic["id"]] = topic["calc"]
    except Exception:                     # 台帳が読めなくても実績は出す
        pass

    out: dict[str, str] = {}
    if UPLOADED.exists():
        with UPLOADED.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                calc = _calc_of_topic(row.get("topic", ""), by_id, known)
                if row.get("video_id") and calc:
                    out[row["video_id"]] = calc
    return out


def known_calcs() -> set[str]:
    return {
        p.stem for p in (ROOT / "src" / "calc").glob("*.py")
        if not p.stem.startswith("_") and p.stem != "__init__"
    }


def families(scan: dict[str, dict] | None = None,
             video_calc: dict[str, str] | None = None,
             min_views: int = MIN_VIEWS) -> list[Family]:
    known = known_calcs()
    scan = _latest_scan() if scan is None else scan
    video_calc = _video_calc(known) if video_calc is None else video_calc

    agg: dict[str, list[int]] = {}
    for vid, m in scan.items():
        views = int(m.get("views") or 0)
        if views < min_views:
            continue
        calc = video_calc.get(vid, "")
        if not calc:
            continue
        row = agg.setdefault(calc, [0, 0, 0, 0])
        row[0] += 1
        row[1] += views
        row[2] += int(m.get("engagedViews") or 0)
        row[3] += int(m.get("subscribersGained") or 0)
    out = [Family(c, v[0], v[1], v[2], v[3]) for c, v in agg.items()]
    out.sort(key=lambda f: -f.raw_rate)
    return out


def baseline(rows: list[Family]) -> float:
    """全体の engaged 比率。**測った本が1つも無いときだけ 0.35 を置く。**"""
    views = sum(f.views for f in rows)
    engaged = sum(f.engaged for f in rows)
    return engaged / views if views else 0.35


def score_map(rows: list[Family] | None = None,
              shrink_views: int = SHRINK_VIEWS) -> dict[str, float]:
    """calc → **縮めた engaged 比率**。台帳に無い族は `base` を使うこと。

    `(engaged + base * shrink) / (views + shrink)`。
    **測っていない族は base そのもの**になるので、真ん中から試されます。
    """
    rows = families() if rows is None else rows
    base = baseline(rows)
    return {
        f.calc: (f.engaged + base * shrink_views) / (f.views + shrink_views)
        for f in rows
    }


def scorer(rows: list[Family] | None = None,
           shrink_views: int = SHRINK_VIEWS):
    """`pick` が使う関数を返す。**未知の calc は全体平均**（探索を殺さない）。"""
    rows = families() if rows is None else rows
    base = baseline(rows)
    table = score_map(rows, shrink_views)

    def score(calc: str) -> float:
        return table.get(calc, base)

    return score


def report_lines(rows: list[Family] | None = None,
                 unused: dict[str, int] | None = None) -> list[str]:
    """`status.py` に出す行。**「次に節を書くならどの calc か」まで言う。**"""
    rows = families() if rows is None else rows
    if not rows:
        return ["  （実績が取れていません。`data/scan.jsonl` が空か、"
                "テーマと動画の対応が付いていません）"]
    table = score_map(rows)
    base = baseline(rows)
    out = [f"  全体 {base * 100:.1f}%（縮め方: 族の再生が {SHRINK_VIEWS} で半々）",
           f"  {'calc':10} {'本':>2} {'再生':>6} {'engaged':>8} "
           f"{'縮めた値':>8} {'登録':>4}"]
    for f in sorted(rows, key=lambda f: -table[f.calc]):
        out.append(f"  {f.calc:10} {f.videos:2d} {f.views:6d} "
                   f"{f.raw_rate * 100:7.1f}% {table[f.calc] * 100:7.1f}% "
                   f"{f.subs:4d}")
    if unused is not None:
        starved = [f.calc for f in sorted(rows, key=lambda f: -table[f.calc])
                   if table[f.calc] > base and not unused.get(f.calc)]
        if starved:
            out.append("  **次に節を書くならここ**（実績が上位なのに未使用の節が0）: "
                       + " ".join(starved))
    return out
