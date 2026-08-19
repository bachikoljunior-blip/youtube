"""**動画の「作り」の特徴と、engaged／再生 を突き合わせる。**

## なぜ要るか（2026-08-19 15:5x）

`scripts/eta.py` が名指しする律速は **1本あたりの再生**です。天井の行は
「ショート 高（RPM ¥60）＝ 1本あたりを **1.4倍**（869回 → 1,208回）」で、
**本数を増やしても在庫を増やしても、この倍率は1ミリも動きません**（`docs/MEANS.md` M20/M21）。

そして `scripts/status.py` の実測では、再生数と同じ向きに動く率は
**engagedViews／再生 が +0.62 で最大**、平均視聴率（+0.13）と平均視聴秒（+0.03）は
無関係でした。**engaged の実測幅は 12.2%〜46.8% ＝ 3.8倍**で、
**要る 1.4倍より幅のほうが大きい。**

**足りなかったのは「どの作りが engaged 側に寄るか」で、これを測る道具が
このリポジトリに1つもありませんでした**（2026-08-19 15:1x の設計の見直し）。

## 鍵は手元にあります（**Data API は要りません**）

15:1x の回は「鍵（`video_id` → テーマID）を `data/uploaded.jsonl` から作る道は
**使えません** —— 直近28日に再生のあった28本のうち ledger に居たのは6本だけ」と
書き残しました。**測り直したら違いました** —— `data/scan.jsonl` の最新点で
**再生のある20本のうち19本が ledger にいます**（`tests/test_build_perf.py`）。

だから、この道具は**API を1単位も使いません**。読むのは3つとも手元のファイルです:

    data/scan.jsonl          動画べつの views / engagedViews（Analytics の写し）
    data/uploaded.jsonl      video_id → テーマID → 題
    data/published_bars.json テーマID → 図の枚数と棒の本数

## 割り引いて読むこと（**ここを外すと n=19 の雑音を設計にします**）

- **n は 20 前後です。** 出るのは仮説までで、当たりではありません
- **交絡が全部残っています** —— 公開時刻・族・配信の広さ・題材の人気。
  この道具が言えるのは「向き」だけで、**理由は言えません**
- **率の分母**: 再生 `MIN_VIEWS` 未満は落とします。ただし
  **落とした側が答えである可能性**は消えません（15:1x の床の件と同じ形）。
  だから落とした本数と、その内訳を必ず印字します

## 「最初の1〜2秒」を測れる本は、いま **5本しかありません**（2026-08-19 16:1x に数え直した）

16:0x の申し送りは、足す特徴の材料として **`data/critique_queue/<id>.json` の
`narration` の1行目（352本ぶんある）** と `change_ratios`（画素差）を名指ししました。
**352本あるのは本当ですが、`engaged` と突き合わせられる本は 19本しかなく、
その 19本のうち控えが残っているのは 5本だけ**でした（実測 5/19）。

理由は時期です。`critique_queue` に控えを取り始めたのは **08/17** で、
**再生の付いている 19本は 08/04〜08/15 に公開したもの**です。
`data/critique.jsonl`（106行）も、この 19本を **1本も** 含みません。
**声も画素差も、この 19本については二度と手に入りません。**

だから、この道具は特徴を2段に分けます。

- **全部の本で測れるもの**（題と図と尺）… いま向きを出せる
- **控えのある本だけで測れるもの**（冒頭の声・冒頭の画素差）… **本数が足りるまで出さない**

後者は 08/17 以降に公開した本に再生が付けば自動で増えます（1日25本の公開が始まっているので、
**待つのは日数だけ**）。`MIN_N` に届くまでは、**件数だけを出して黙ります** ——
n=5 の順位相関を印字すると、次の回がそれを設計に使うからです。

## 「既知の当たり」を1つ固定してあります

新しい特徴を足すたびに、**配線が落ちても件数は減らない**ので気づけません。
`scripts/status.py` が別の道で出している **尺 × 再生 = -0.33**（n=20）を、
この道具でも特徴として持ち、`tests/test_build_perf.py` が符号ごと見ています。
**ここが緑なら、少なくとも「特徴 → 順位相関」の配線は生きています。**
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from src.scan import _spearman

ROOT = Path(__file__).resolve().parent.parent
SCAN = ROOT / "data" / "scan.jsonl"
LEDGER = ROOT / "data" / "uploaded.jsonl"
BARS = ROOT / "data" / "published_bars.json"
QUEUE = ROOT / "data" / "critique_queue"

# 率の分母の下限。**これ未満は向きの計算に入れない**（分母が小さいと率が壊れる）。
MIN_VIEWS = 30

# 特徴ごとの本数の下限。**これ未満の特徴は、向きを出さずに件数だけ言う。**
# `_spearman` は 4本から数を返しますが、n=5 の順位相関は雑音です
# （そして印字すると、次の回がそれを設計に使います）。
MIN_N = 10

_SHORTS = re.compile(r"\s*#Shorts?\s*$", re.I)
_NUM = re.compile(r"[0-9０-９]+")
# 題が問いの形か。**末尾の「か」だけでは足りません**（「〜ですか」以外の問いを落とす）。
_ASK = re.compile(r"[?？]|(?:か|かも|のか|ですか|ますか)$|いくら|どっち|どちら|何[円日歳月年%％]|なぜ")


def _scans() -> list[dict[str, Any]]:
    """`data/scan.jsonl` の点を**古い順に全部**返す。"""
    out = []
    for line in SCAN.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    if not out:
        raise RuntimeError(f"{SCAN} が空です")
    return out


def _latest_scan() -> dict[str, Any]:
    return _scans()[-1]


def per_video(snap: dict[str, Any] | None = None) -> dict[str, dict[str, float]]:
    """動画べつの数字。**鍵ごとに、その鍵が入っている最新の点**から取ります。

    ## なぜ最新の1点ではないのか（2026-08-19 17:2x に、赤い検査から見つけた）

    ここは長らく**最新の1点だけ**を読んでいました。**Data API の日枠が切れている
    13時間のあいだ、その1点には `尺` も `題` も入りません**（`videos.list` が 403。
    `views` / `engagedViews` は Analytics ＝ **別枠**なので入ります）。

    実測（08/19 17:03 / 17:11 / 17:15 の3点とも）:

        動画キー 253 ／ **尺 0** ／ views 28

    結果、`尺（秒）` の特徴が **n=0** になり、この道具の**唯一の物差し**
    （既知の当たり 尺 × 再生 = -0.33）が落ちました。
    **特徴が消えても件数は減らない**ので、口は「本数不足」と印字します ——
    **「まだ待て」と読めますが、待っても入りません。**枠が戻るまで永久に0です。

    **`尺` は動画の長さなので、時間で変わりません。** 古い点の値は今も正しい。
    **落ちているのは事実ではなく、その回の読みだけ**です。

    ## 混ぜても嘘にならない理由

    **鍵ごとに独立して「最後に観測された値」を取ります**（点をまたいで混ぜます）。
    伸びる数（`views`）も同じ扱いですが、**それが古くなるのは
    「その回に読めなかったとき」だけ**で、そのとき代わりに入る値はありません。
    **0 で埋めるのでも、`None` にするのでもなく、最後に見えた値を使う** ——
    これは「無い」と「0」を分ける方針（`features()` の docstring）と同じ側です。

    `snap` を渡したときは、**その1点だけ**を読みます（検査が形を固定するため）。
    """
    snaps = [snap] if snap is not None else _scans()
    out: dict[str, dict[str, float]] = {}
    for one in snaps:                      # 古い順。**後の点が上書きする**
        for key, val in (one.get("values") or {}).items():
            parts = key.split(".")
            if len(parts) != 3 or parts[0] != "動画":
                continue
            if val is None:
                continue
            out.setdefault(parts[1], {})[parts[2]] = val
    return out


def stale_keys(snap: dict[str, Any] | None = None) -> int:
    """**最新の点に無くて、古い点から拾った鍵**の数（＝いま読めていない量）。

    0 でないときは、その回に日枠が切れています。**黙って古い値を使わないこと。**
    """
    if snap is not None:
        return 0
    latest = {k for k, v in (_scans()[-1].get("values") or {}).items() if v is not None}
    return sum(1 for vid, m in per_video().items()
               for name in m if f"動画.{vid}.{name}" not in latest)


def ledger() -> dict[str, dict[str, Any]]:
    """`video_id` → 投稿の控え。**同じIDが複数行にあるときは後の行が勝ちます。**"""
    out: dict[str, dict[str, Any]] = {}
    if not LEDGER.exists():
        return out
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("video_id"):
            out[row["video_id"]] = row
    return out


def _width(s: str) -> int:
    """全角を2、半角を1で数える。**字数は見た目の幅で効くはず**なので。"""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def first_seconds(video_id: str) -> dict[str, float] | None:
    """**最初の1〜2秒**の特徴。控えが無い本には `None` を返す（0 で埋めない）。

    出どころは `data/critique_queue/<video_id>.json`（`narration` と `change_ratios`）。
    **控えを取り始めたのは 08/17** なので、それより前に公開した本には存在しません。
    **0 で埋めないこと** —— 「冒頭に数字が無い本」と区別がつかなくなります。
    """
    path = QUEUE / f"{video_id}.json"
    if not path.exists():
        return None
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    lines = rec.get("narration") or []
    ratios = rec.get("change_ratios") or []
    if not lines:
        return None
    head = str(lines[0])
    out = {
        "冒頭の声の幅": float(_width(head)),
        "冒頭に数字": 1.0 if _NUM.search(head) else 0.0,
    }
    if ratios:
        # 1コマ目 → 2コマ目の画素差。**engaged は「スワイプされなかった割合」**なので、
        # 効くとすればここです（`verify.slide_change_ratios` が出している値の写し）。
        out["冒頭の絵の変化"] = float(ratios[0])
    return out


def first_slide(video_id: str) -> dict[str, float] | None:
    """**1枚目の見出し**の特徴。控えが無い本には `None`（0 で埋めない）。

    出どころは `data/critique_queue/<video_id>.plan.json` の先頭のコマです。

    ## なぜ `first_seconds` と分けるのか（2026-08-19 19:4x）

    `<id>.json`（`narration`）と `<id>.plan.json` は**別々に欠けます。**
    同じ辞書に入れると、片方が無い本で丸ごと `None` になり、
    **もう片方まで一緒に落ちます**（この repo で通算10回出ている
    「片方が欠けると両方消える」形）。だから受け口を2つに分けています。

    **在庫の数と、測れる数は別です**（2026-08-19 19:4x に、この docstring 自身で
    踏んで直した）。最初こう書きました ——「`plan.json` は **341本ぶん**あるので
    `narration`（3本）より2桁広い」。**数え直したら、再生の付いている本との
    重なりは 0本**でした（`narration` は5本）。**341 は在庫の数**で、
    `plan.json` を残し始めたのが新しいので、**再生の付いた古い本には1つも無い。**
    §2.7 が「申し送りの件数は最初に数え直すこと」と言っているのと同じ穴です。

        再生30以上の本 20本 ∩ plan.json = **0本**  ／ ∩ narration = **5本**

    **それでもこの特徴を入れます。** 理由は「広いから」ではなく、
    **1〜2秒の画面を占めている当のものを、誰も測っていなかったから**です
    （下）。08/17 以降の本に再生が付けば、`narration` と同じ速さで増えます。

    ## なぜこの2つを測るのか

    engaged（＝すぐスワイプされなかった割合）は `status.py` の実測で
    **1本あたり再生に最も強く効く率（+0.62）**で、決まるのは最初の1〜2秒 ——
    **1枚目の見出しは、その1〜2秒に画面を占めているものそのもの**です。
    ところが `features()` はそこから、**棒の本数しか見ていませんでした**
    （`1枚目の棒`）。**字のほうは誰も測っていません。**

    実測（2026-08-19・**在庫 341本**。上のとおり、まだ再生とは突き合わせられません）:

        1枚目の幅     中央値 12字・最大 17字（上限は台本側で22字）
        1枚目に数字   **174/341 = 51%**   ← 半々に割れている＝**向きが出せる幅がある**

    台本の指示は「**1枚目は結論の数字だけ**」ですが、**半分は数字を出していません。**
    どちらが良いのかは、この repo が一度も測っていません。**まず測ります。**
    """
    path = QUEUE / f"{video_id}.plan.json"
    if not path.exists():
        return None
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(plan, list) or not plan or not isinstance(plan[0], dict):
        return None
    head = str(plan[0].get("headline") or "")
    if not head:
        return None
    return {
        "1枚目の幅": float(_width(head)),
        "1枚目に数字": 1.0 if _NUM.search(head) else 0.0,
    }


def features(
    topic: str,
    title: str,
    bars: dict[str, Any],
    *,
    seconds: float | None = None,
    head: dict[str, float] | None = None,
    slide: dict[str, float] | None = None,
) -> dict[str, float | None]:
    """1本ぶんの「作り」の特徴。**全部、公開前に決まっているものだけ。**

    公開後にしか分からないもの（再生・engaged）は特徴に入れません。
    入れると「よく回った本はよく回る」という同義反復が出ます。

    **測れない特徴は `None` を入れます。0 で埋めないこと** ——
    「無い」と「0だった」を混ぜると、向きが静かに薄まります
    （2026-08-19 の `usage` の 4つ組と同じ形）。
    """
    plain = _SHORTS.sub("", title)
    nums = _NUM.findall(plain)
    charts = (bars.get(topic) or {}).get("charts") or []
    m = _NUM.search(plain)
    out: dict[str, float | None] = {
        # **既知の当たり**（`status.py` が別の道で -0.33 と出している）。
        # ここが緑なら「特徴 → 順位相関」の配線は生きています。
        "尺（秒）": None if seconds is None else float(seconds),
        "図の枚数": float(len(charts)),
        "1枚目の棒": float(len(charts[0])) if charts else 0.0,
        "棒の本数": float(sum(len(c) for c in charts)),
        "題の幅": float(_width(plain)),
        # **数字が出るまでの幅。**題は最初の1秒に丸ごと見えるので、
        # 「何字読んだら数字に当たるか」は冒頭の作りそのものです。
        "数字までの幅": float(_width(plain[: m.start()]) if m else _width(plain)),
        "題の数字の桁": float(max((len(n) for n in nums), default=0)),
        "題の数字の個数": float(len(nums)),
        "題が問いか": 1.0 if _ASK.search(plain) else 0.0,
    }
    for name in ("冒頭の声の幅", "冒頭に数字", "冒頭の絵の変化"):
        out[name] = (head or {}).get(name)
    # **控えが別なので、辞書も別に受ける**（`first_slide` の docstring）。
    for name in ("1枚目の幅", "1枚目に数字"):
        out[name] = (slide or {}).get(name)
    return out


def collect() -> tuple[list[dict[str, Any]], list[tuple[str, str]]]:
    """測れた本と、落とした本（理由つき）を返す。"""
    stats = per_video()
    led = ledger()
    bars = json.loads(BARS.read_text(encoding="utf-8")) if BARS.exists() else {}

    rows: list[dict[str, Any]] = []
    dropped: list[tuple[str, str]] = []
    for vid, s in stats.items():
        views = s.get("views", 0)
        if not views:
            dropped.append((vid, "再生0"))
            continue
        entry = led.get(vid)
        if entry is None:
            dropped.append((vid, "控えに無い（鍵が引けない）"))
            continue
        if views < MIN_VIEWS:
            dropped.append((vid, f"再生{MIN_VIEWS}未満（分母が小さい）"))
            continue
        topic = entry.get("topic", "")
        f = features(
            topic,
            entry.get("title", ""),
            bars,
            seconds=s.get("尺"),
            head=first_seconds(vid),
            slide=first_slide(vid),
        )
        rows.append(
            {
                "video_id": vid,
                "topic": topic,
                "title": entry.get("title", ""),
                "views": float(views),
                "engaged": float(s.get("engagedViews", 0)) / float(views),
                "subs": float(s.get("subscribersGained", 0)),
                "features": f,
            }
        )
    rows.sort(key=lambda r: -r["views"])
    return rows, dropped


def correlations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """特徴ごとに、engaged との向きと 再生 との向き。**向きだけを読むこと。**

    返るのは1特徴1件の辞書で、`why` が空でないときは **向きを出していません**:

        "本数不足"  測れた本が `MIN_N` 未満（＝ まだ待つ。控えが増えれば出ます）
        "変化なし"  全部の本が同じ値（＝ **まだ一度も試していない**。待っても出ません）

    **2つを混ぜないこと。** 前の版は両方 `None` を返していたので、
    口が「本数が足りない」と印字し、**「1本も試していない」が待てば出るものに見えていました。**
    """
    if not rows:
        return []
    names = list(rows[0]["features"])
    out: list[dict[str, Any]] = []
    for name in names:
        pairs = [
            (r["features"][name], r["engaged"], r["views"])
            for r in rows
            if r["features"][name] is not None
        ]
        n = len(pairs)
        if n < MIN_N:
            out.append({"name": name, "eng": None, "views": None, "n": n, "why": "本数不足"})
            continue
        xs = [a for a, _, _ in pairs]
        if len(set(xs)) < 2:
            out.append({"name": name, "eng": None, "views": None, "n": n, "why": "変化なし"})
            continue
        out.append(
            {
                "name": name,
                "eng": _spearman(xs, [b for _, b, _ in pairs]),
                "views": _spearman(xs, [c for _, _, c in pairs]),
                "n": n,
                "why": "",
            }
        )
    out.sort(key=lambda d: -(abs(d["eng"]) if d["eng"] is not None else -1))
    return out
