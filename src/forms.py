"""**その1本がショートか長尺か**を、1か所で決める（2026-08-25）。

## なぜ要るか —— **同じ帳面を読む2つが、逆のことを言っていた**

    scripts/status.py:150     「ショートかどうか。**尺で見る。** 題の #Shorts は付け忘れがある」
    scripts/reschedule.py:296 「**題名の `#Shorts` だけで見ます**」

この回（08/25）に突き合わせたら、**食い違う本が実在しました**:

    CfzcVmRncPg   予約 08/27 09:00   **5分9秒**   … #Shorts
    WuTf0Z-tRJc   公開 08/21 10:15   **5分51秒**  … #Shorts   ← 公開済み・**1再生**

`data/video_forms.json`（Analytics の `creatorContentType`。**実測**）は
`WuTf0Z-tRJc` を **`長尺`** と言っています。**題名の札が嘘です。**

## 何が壊れるか

`reschedule.py --spread` は**1日に置くショートの本数に上限**をかけます。
長尺をショートと数えると、その日のショート枠が1本ぶん不当に減り、
**本物のショートが後ろの日へ押し出されます**（＝密度の損）。
`reschedule.py` 自身が「長尺をショートに数えると、上限がその日のショートを
不当に減らします」と書いてあり、**そのとおりの事故が起きていました。**

さらに `CfzcVmRncPg` は **08/27** に載っています。08/27 は
**day_cap（1日の本数の上限があるか）の切り分けの日**で、
`--spread` がその日の本を動かすと**対照が壊れます。**

## 決め方（**測ったものが、書いてある札に勝ちます**）

    1. data/video_forms.json     Analytics の実測。**公開済みだけ**。いちばん強い
    2. 控えの duration_s         投稿の直前に final.mp4 を測った秒数（2026-08-25 から records）
    3. 題名の #Shorts            **推測**。上の2つが何も言わないときだけ

3 に落ちたことは `inferred()` で数えられます。**札だけで決めた本が何本あるか**が
見えていないと、次の回がまた「札は正しい」前提で読みます。

## 覆る条件

**1 と 2 が全部埋まったら、3 は消してよい**（`inferred()` が 0 を返し続けたら）。
それまでは残すこと —— 予約中の古い本には秒数がありません。
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORMS = ROOT / "data" / "video_forms.json"

#: ショートの上限。YouTube の区切りは **3分**（2026-01 以降）。
#: `verify.MAX_SHORT_SECONDS`（70秒）は**こちらの作り方の上限**で、別物です。
SHORT_MAX_SECONDS = 180.0

_TAG = "#Shorts"


def measured_forms() -> dict[str, str]:
    """`data/video_forms.json` の実測（動画ID → `ショート` / `長尺`）。"""
    if not FORMS.exists():
        return {}
    try:
        data = json.loads(FORMS.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    forms = data.get("forms")
    return forms if isinstance(forms, dict) else {}


def classify(row: dict, forms: dict[str, str] | None = None) -> tuple[bool, str]:
    """`(ショートか, どこで決めたか)` を返す。

    `row` は `id`/`video_id`・`title`・`duration_s` を見ます
    （`src.dupes.ledger_rows()` の行と `data/uploaded.jsonl` の行の両方が通ります）。
    """
    if forms is None:
        forms = measured_forms()

    vid = str(row.get("id") or row.get("video_id") or "")
    form = forms.get(vid)
    if form in ("ショート", "長尺"):
        return form == "ショート", "measured"

    dur = row.get("duration_s")
    try:
        if dur is not None and float(dur) > 0:
            return float(dur) <= SHORT_MAX_SECONDS, "duration"
    except (TypeError, ValueError):
        pass

    return _TAG in str(row.get("title") or ""), "tag"


def is_short(row: dict, forms: dict[str, str] | None = None) -> bool:
    """その本がショートか。**決め方の内訳が要るなら `classify()`。**"""
    return classify(row, forms)[0]


def inferred(rows: list[dict]) -> list[dict]:
    """**題名の札だけで決めた本**（＝まだ測っていない本）を返す。"""
    forms = measured_forms()
    return [r for r in rows if classify(r, forms)[1] == "tag"]


def mislabelled(rows: list[dict]) -> list[dict]:
    """**測った形と、題名の札が食い違う本**を返す。

    返るのは `{"id","title","form","tagged"}`。**この一覧が空でない限り、
    札で決めている読み手はどこかで間違えます。**
    """
    forms = measured_forms()
    out = []
    for r in rows:
        short, how = classify(r, forms)
        if how == "tag":
            continue
        tagged = _TAG in str(r.get("title") or "")
        if tagged != short:
            out.append({"id": str(r.get("id") or r.get("video_id") or ""),
                        "title": str(r.get("title") or ""),
                        "form": "ショート" if short else "長尺",
                        "tagged": tagged, "how": how})
    return out


def strip_tag(title: str) -> str:
    """題名から `#Shorts` を落とす（長尺に付いてしまった札を外すときに使う）。"""
    import re
    return re.sub(r"\s*#Shorts?\b", "", title, flags=re.I).strip()
