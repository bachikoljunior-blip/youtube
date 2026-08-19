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

## 「既知の当たり」を1つ固定してあります（**2026-08-20 に取り替えました**）

新しい特徴を足すたびに、**配線が落ちても件数は減らない**ので気づけません。
ここは長らく **尺 × 再生 = -0.33**（n=20）を物差しにしていました。

**あれは尺の効きではありませんでした。** 実測を最初に観測した順に並べると:

    08/06〜08/15 02:12   47〜69秒（13本）
    08/15 12:18〜08/17   27〜30秒（**6本**）

**境目で完全に割れています。** 08/15 にパイプラインが短いショートへ一斉に
切り替わっているので、尺は「切替の前か後か」の言い換えでしかなく、
-0.33 は**切替の前後で再生が違ったこと**しか言っていません
（同じ切替で `数字までの幅` 99%・`題の数字の個数` 96% も割れています）。
**この道具の唯一の物差しが、時期の別名でした。**

いまの物差しは**手で作った行**です（`tests/test_build_perf.py` の
`test_既知の当たり_単調な特徴は向きが出る`）。実データの偶然に寄りかからず、
**「特徴 → 順位相関」の配線だけ**を見ます。そして実データ側には、
**尺が時期と分けられないこと自体**を固定してあります（`_time_split`）。
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
VIEWS = ROOT / "data" / "views.jsonl"
BARS = ROOT / "data" / "published_bars.json"
QUEUE = ROOT / "data" / "critique_queue"

# 率の分母の下限。**これ未満は向きの計算に入れない**（分母が小さいと率が壊れる）。
MIN_VIEWS = 30

# 特徴ごとの本数の下限。**これ未満の特徴は、向きを出さずに件数だけ言う。**
# `_spearman` は 4本から数を返しますが、n=5 の順位相関は雑音です
# （そして印字すると、次の回がそれを設計に使います）。
MIN_N = 10

# **その特徴が「時期」と分けられないと見なす線**（`_time_split` の値。1.0 が完全に割れる）。
# 作りをパイプライン全体で切り替えると、切替日の前後で値が丸ごと入れ替わります。
# そのとき特徴は「切替の前か後か」の言い換えになるので、
# **再生との向きは、特徴の効きではなく時期の効きです**（2026-08-20 に実測）。
# 0.95 は「割れ方が 95% 以上そろっている」＝ 1本か2本の食い違いは許す線です。
TIME_CONFOUND = 0.95

_SHORTS = re.compile(r"\s*#Shorts?\s*$", re.I)
_NUM = re.compile(r"[0-9０-９]+")
#: **数字の「個数」は連なりで数える。**`_NUM` は1桁ずつ当たるのではなく
#: 連なりに当たりますが、区切り（`1,234` の `,`・`3.67` の `.`）で切れると
#: 1つの数を2つに数えます。個数を出すのはこちら。
_NUM_RUN = re.compile(r"[0-9０-９]+(?:[.,][0-9０-９]+)*")
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

    結果、`尺（秒）` の特徴が **n=0** になりました
    （当時はそれが**唯一の物差し**でした。2026-08-20 に取り替えています —— 冒頭）。
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


def first_seen() -> dict[str, str]:
    """`video_id` → **その本が最初に観測された時刻**（`data/views.jsonl`）。

    **公開時刻の控えは、古い本には入っていません**（`uploaded.jsonl` の
    `at` / `uploaded_at` は 19本中5本にしかなく、その5本は全部
    08/15 以降に作った本です）。`uploaded.jsonl` の**行の順番も使えません**
    —— 控えは後から埋め直されていて、古い本のほうが先頭に来ています
    （実測: 行の順 × 尺 = +0.48。時間の順なら -1.0 になるはず）。

    `views.jsonl` は**毎回の観測を追記するだけ**なので、
    「最初に載った時刻」＝ おおよその公開時刻です。**全部の本にあります。**
    """
    out: dict[str, str] = {}
    if not VIEWS.exists():
        return out
    for line in VIEWS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        at = row.get("at")
        vid = row.get("id") or row.get("video_id")
        if vid and at:
            out.setdefault(vid, at)
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
    """**1枚目の画面**の特徴。控えが無い本には `None`（0 で埋めない）。

    出どころは `data/critique_queue/<video_id>.plan.json` の先頭のコマです。
    **割った後のコマ**なので、これは視聴者が最初の1〜2秒に見ている画面そのものです。

    ## なぜ `first_seconds` と分けるのか（2026-08-19 19:4x）

    `<id>.json`（`narration`）と `<id>.plan.json` は**別々に欠けます。**
    同じ辞書に入れると、片方が無い本で丸ごと `None` になり、
    **もう片方まで一緒に落ちます**（この repo で通算10回出ている
    「片方が欠けると両方消える」形）。だから受け口を2つに分けています。

    **在庫の数と、測れる数は別です**（2026-08-19 19:4x）。

        再生30以上の本 20本 ∩ plan.json = **0本**  ／ ∩ narration = **5本**

    ## **「見出しだけ」を見ていました**（2026-08-20 に測って直した）

    ここには 2026-08-19 19:4x にこう書きました ——

        1枚目に数字   **174/341 = 51%**   ← 半々に割れている＝**向きが出せる幅がある**
        台本の指示は「**1枚目は結論の数字だけ**」ですが、**半分は数字を出していません。**

    **2つとも違いました。数え直した結果です。**

    **(1) 台本が書いた「結論の数字」は、1枚目には出ません。**
    `visuals.reveal_variants` が、冒頭の `kind=stat` を**2枚に割って
    1枚目の `stat` と `formula` を空にします**（2026-08-15 22:0x に、
    「冒頭の2枚が画素で 7.06% しか違わない」を実測して入れた作りです）。
    実測 **332/341 = 97%** の本で、1枚目の `stat` は空でした。
    だから「指示が半分守られていない」ではなく、**指示どおり書かれた数字を
    描画側が意図して消している**のが実物です。**台本側を直す話ではありません。**

    **(2) そして 1枚目の主役は、見出しではなく `note`（補足）です。**
    `stat` が空のとき `note_lead` が立ち、CSS 側で**補足が主役の大きさ**になります
    （`visuals.py` の `.note--lead`）。実測 **332/341 = 97%** がその形です。
    見出しは画面上部の小さい札のほうで、**古い「1枚目に数字」はそこだけを見ていました。**

    **画面ぜんぶで数え直すと、こうなります**（在庫 341本）:

        見出しに数字         174/341 = 51%    ← 古い値。**小さい札だけの割合**
        補足(note)に数字     307/341 = 90%
        **画面のどこかに数字   328/341 = 96%**  ← 実物。**幅がありません**

    **「半々に割れている＝向きが出せる」は、測る場所を間違えたことによる見かけです。**
    だから `1枚目に数字` は画面ぜんぶで数える形に直したうえで、
    **向きはここからは出ません**（96対4）。口は「変化なし」と印字します。
    それでよく、**嘘の 51% で A/B を設計しないことのほうが大きい**です。

    ## 代わりに何を測るか（**幅のあるものだけ足す。在庫341本で測ってから**）

        1枚目の主役の幅     中央 26 ・ 4〜58 ＝ **14.5倍** ・ 異なり42通り  ← いちばん広い
        1枚目の数字の個数   中央  2 ・ 0〜 6 ＝ **12倍**   ・ 異なり 7通り
        1枚目の幅（見出し） 中央 22 ・14〜33 ＝  2.4倍   ・ 異なり18通り

    **主役の幅は、1〜2秒の画面を占めている当のものの量**です。engaged（＝すぐ
    スワイプされなかった割合）は `status.py` の実測で1本あたり再生に最も強く効く率
    （+0.61）で、決まるのがその1〜2秒なので、**量そのものに幅があるのは
    ここでした**（`1枚目の棒` は棒の本数しか見ていません）。
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
    slide = plan[0]
    head = str(slide.get("headline") or "")
    note = str(slide.get("note") or "")
    stat = str(slide.get("stat") or "")
    if not (head or note or stat):
        return None
    # **主役はどれか。** `reveal_variants` が数字を伏せた1枚目では `note_lead` が
    # 立ち、補足が主役の大きさで出ます（実測 97%）。伏せていない本では `stat`、
    # それも無ければ見出しだけが画面に残ります。
    if slide.get("note_lead") and not stat:
        hero = note
    else:
        hero = stat or head
    screen = f"{head} {note} {stat}"
    return {
        "1枚目の幅": float(_width(head)),
        "1枚目の主役の幅": float(_width(hero)),
        # **画面ぜんぶで数えること**（上の (2)）。見出しだけだと 51%、実物は 96%。
        "1枚目に数字": 1.0 if _NUM.search(screen) else 0.0,
        "1枚目の数字の個数": float(len(_NUM_RUN.findall(screen))),
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
        # **08/15 の切替で 47〜69秒 → 27〜30秒 と完全に割れています。**
        # `correlations` が「時期と分けられない」として向きを伏せます（冒頭）。
        # 向きを読みたければ、**同じ時期の本を2群に割ってから**。
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
    for name in ("1枚目の幅", "1枚目の主役の幅",
                 "1枚目に数字", "1枚目の数字の個数"):
        out[name] = (slide or {}).get(name)
    return out


def collect() -> tuple[list[dict[str, Any]], list[tuple[str, str]]]:
    """測れた本と、落とした本（理由つき）を返す。"""
    stats = per_video()
    led = ledger()
    seen = first_seen()
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
                # **いつ作ったか**（`first_seen`）。特徴と時期が分けられるかを
                # `correlations` がこれで見ます。**無い本は None**（0 で埋めない）。
                "first_seen": seen.get(vid),
                "features": f,
            }
        )
    rows.sort(key=lambda r: -r["views"])
    return rows, dropped


# 時期で切ったときの両側の下限。**これ未満の側では割れたと言わない**
# （端の1本を切り出せば、どんな特徴でも「きれいに割れた」ことにできます）。
MIN_SIDE = 3


def _time_split(name: str, rows: list[dict[str, Any]]) -> float | None:
    """**時期を1点で切ったとき、その特徴がどれだけきれいに割れるか**（0.5〜1.0）。

    1.0 ＝ 完全に割れている。その特徴は「切替の前か後か」の言い換えでしかなく、
    **再生との向きは時期の効きと区別がつきません。**

    **順位相関では検出できません**（2026-08-20 に実測して差し替えた）。
    尺は 08/15 の切替で 47〜69秒 → 27〜30秒 と完全に割れているのに、
    切替より前の13本の中では尺が上下するので、**全体の順位相関は -0.48** にしかならず、
    どんな線を引いても「無関係」の側と見分けられません。
    見たいのは順位の一致ではなく、**1点で切れるかどうか**のほうです。

    **時刻の分かる本が `MIN_N` に届かなければ `None`**（判定しない）。
    ここで 0.5 を返すと「時期とは無関係」という嘘の点になります。
    """
    pairs = sorted(
        (r["first_seen"], r["features"][name])
        for r in rows
        if r.get("first_seen") and r["features"][name] is not None
    )
    n = len(pairs)
    if n < MIN_N:
        return None
    ys = [b for _, b in pairs]
    if len(set(ys)) < 2:
        return None
    best = 0.5
    for k in range(MIN_SIDE, n - MIN_SIDE + 1):
        # **同じ時刻をまたいで切らない**（順番の付けようがないので）。
        if pairs[k - 1][0] == pairs[k][0]:
            continue
        early, late = ys[:k], ys[k:]
        wins = sum((x < y) + 0.5 * (x == y) for x in early for y in late)
        auc = wins / (len(early) * len(late))
        best = max(best, auc, 1.0 - auc)
    return best


def correlations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """特徴ごとに、engaged との向きと 再生 との向き。**向きだけを読むこと。**

    返るのは1特徴1件の辞書で、`why` が空でないときは **向きを出していません**:

        "本数不足"        測れた本が `MIN_N` 未満（＝ まだ待つ。控えが増えれば出ます）
        "変化なし"        全部の本が同じ値（＝ **まだ一度も試していない**。待っても出ません）
        "時期と分けられない"  時期を1点で切ると特徴がきれいに割れる（`_time_split` ≥ `TIME_CONFOUND`）

    **3つを混ぜないこと。** 前の版は最初の2つを両方 `None` で返していたので、
    口が「本数が足りない」と印字し、**「1本も試していない」が待てば出るものに見えていました。**

    ## 3つ目を 2026-08-20 に足した理由（**この道具の唯一の物差しが、時期の別名でした**）

    ここは長らく **尺 × 再生 = -0.32** を「既知の当たり」として持ち、
    `tests/test_build_perf.py` が符号ごと固定していました。実測を並べると:

        最初に観測した順   尺
        08/06〜08/15 02:12   47〜69秒（13本）
        08/15 12:18〜08/17   27〜30秒（**6本**）

    **境目で完全に割れています。** 08/15 にパイプラインが短いショートへ
    切り替わっているので、**尺の順位は「いつ作ったか」の順位そのもの**です。
    -0.32 は尺の効きではなく、**切替の前後で再生が違ったこと**しか言っていません。

    **パイプライン全体で一斉に変えた作りは、全部この形になります。**
    向きを出すには、**同じ時期の本を2つの群に割る**しかありません
    （`script_writer.title_form` / `hook_form` がやっている、IDのハッシュで
    半々にする形。あちらは時期と直交するので、この判定に当たりません）。
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
            out.append({"name": name, "eng": None, "views": None, "n": n,
                        "time": None, "why": "本数不足"})
            continue
        xs = [a for a, _, _ in pairs]
        if len(set(xs)) < 2:
            out.append({"name": name, "eng": None, "views": None, "n": n,
                        "time": None, "why": "変化なし"})
            continue
        rho_t = _time_split(name, rows)
        if rho_t is not None and rho_t >= TIME_CONFOUND:
            out.append({"name": name, "eng": None, "views": None, "n": n,
                        "time": rho_t, "why": "時期と分けられない"})
            continue
        out.append(
            {
                "name": name,
                "eng": _spearman(xs, [b for _, b, _ in pairs]),
                "views": _spearman(xs, [c for _, _, c in pairs]),
                "n": n,
                "time": rho_t,
                "why": "",
            }
        )
    out.sort(key=lambda d: -(abs(d["eng"]) if d["eng"] is not None else -1))
    return out
