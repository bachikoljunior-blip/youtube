"""**閉じた前提が earn した「次の手」を、落とさせない。**

## なぜ要るか（2026-08-25・最適化の回）

`eta.py` は毎回こう印字しています ——
**「軌跡の腕が動くのは、`config/hypotheses.yaml` の前提を1件閉じたときだけ」**。
つまり**実験を閉じることが、この輪の唯一の出力**です。

では、閉じたときに何が手に入るのか。**`next_if_false` です。**
16本作って2週間待って、その代金として受け取るのは
「外れた。だから次はこれをやれ」という1行 —— **それだけ**です。

**その1行を、誰も読み返していませんでした。**

    `outcome` が外れ／半々の前提            **14件**
    その `next_if_false`                   **31手**
    実行された／却下されたと記録された手     **0件**（2026-08-25 実測）

`next_if_false` を読む機械は既にあります（`status.py` は**開いている**前提について
「次の手が書かれているか」を見て、書かれていなければ鳴らす）。
**書かれているかは見て、実行されたかは誰も見ていない。**
だから手は書かれた瞬間に満たされ、閉じた瞬間に消えます。

## 実際に落ちたもの（**これが発見の元です**）

**5件の外れた前提が、16日かけて同じ方向を指しています**（うち4件は名指し）。

    2026-08-07  「1245再生は『年金』という題の効果ではない」→ **外れ**
                → next2: 「それでも駄目なら、切り口ではなく**形式**（音声・画・冒頭2秒）を疑う」
    2026-08-08  「ショートの最後で場所を言うと登録につながる」→ **外れ**
                → next1: 「**やめた。** 当たっても3.4年。**桁が足りない**」
    2026-08-15  「1本あたりの再生が300〜1500なのは中身のせいで、天井ではない」→ **外れ**
                → next1: **「この形式では桁が足りないと確定させる。中身の調整をやめる」**
    2026-08-20  「尺を30秒に縮めると engaged が上がる」→ **外れ**
                → next2: **「静止画スライド＋合成音声という形式そのものを疑う」**
    2026-08-23  「engaged を決めているのは冒頭で画面が変わらないこと」→ **外れ**
                → next: **「形式そのものを疑う」「この機械の改善はここで打ち切る」**

**そして 8/19 に、中身の調整の実験が2件 新しく開かれています**
（`題を問いの形に` / `冒頭1枚目の主役を問いかけに`）——
**8/15 の「中身の調整をやめる」の4日後**です。
2026-08-25 時点で、engaged を上げにいく開いた前提は **5件**あり、
**3つの外れが「やめろ」と言った当のもの**です。

**算数も同じ側です。ただし「engaged は効かない」ではありません** ——
`build_perf.py` の実測で **engagedViews／再生 と再生の相関は +0.62**（n≈19）。
**proxy としては本物です。足りないのは幅のほう**です:

    engaged の実測幅       **12.2%〜46.8% ＝ ×3.8**（観測された最悪→最良）
    `per_video` の引き代   **×2.96**（`drift.py`。腕を天井まで引いたときの倍率）
    20万に要る倍率         **×17.0**（RPM ¥60・上限 ¥11,754／月）

**振り切っても 3.8 < 17.0 で届きません。**

**5件の実験が悪かったのではありません。** 設計した 2026-08-19 の的は
**1.4倍**（869回 → 1,208回）で、**3.8 > 1.4。当時は正しい賭け**でした。
**2026-08-25 23:00 に天井の分母が直り**（API の日枠 92本/日 → 実測 10本/日 ＝
**9.2倍 悲観側へ**）、的が 17.0倍 になりました。
**その夜、台帳を誰も読み直していません。**

天井を直した回と、その天井に乗っている実験を持っている台帳が**別々の場所**にあり、
**片方しか直らなかった** —— このリポジトリで通算10回目の形です。

## この道具がやること

**判断はしません。** 「形式を変えろ」とは言いません ——
それは実際に作っている側が決めることです。
やるのは**決着を強制すること**だけ:

> 外れた前提の `next_if_false` は、**採用したか却下したか**を記録するまで、
> 毎周ここに出続ける。**「見た」では消えない。**

却下は正しい答えになり得ます（「データが薄い」「別の手が速い」）。
**書かれていないことだけが問題**です。書かれていなければ、
次に来た側は「その手は試したのか」を知る方法がありません。

## 書き方（`config/hypotheses.yaml`）

`next_done` を `next_if_false` と**同じ並び**で置きます。

    next_if_false:
      - 静止画スライド＋合成音声という形式そのものを疑う
      - M5（RPM の高いニッチ）へ
    next_done:
      - "2026-08-26 採用: --real で実画面の収録を1本作った（…）"
      - "2026-08-26 却下: RPM の帯は測っていないので、先に…"

**日付と、採用／却下のどちらかが要ります。** 足りない行は
「書きかけ」として鳴り続けます —— **黙って通す行は、門ではありません**
（`src/verify.py` の `_check_narrated_shown` が同じ形で3本 通しました）。
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
HYPOTHESES = ROOT / "config" / "hypotheses.yaml"

JST = timezone(timedelta(hours=9))

#: 記録するまでに許す日数。**0 だと閉じたその回で必ず止まる。**
#: 1 にしたのは、閉じる回と手を打つ回が別でよいからです（判定は夜、実装は翌朝でよい）。
#: **これ以上長くしません** —— 現状の速さで1日 ≒ 20周あり、
#: 20周も「あとで決める」が続けば、それは決めないのと同じです。
GRACE_DAYS = 1

#: 採用／却下として読む語。**日本語と英語の両方**（散文で書かれた実物に合わせる）。
_TAKEN = ("採用", "実施", "着手", "done", "adopted", "taken")
_REJECTED = ("却下", "見送", "棄却", "rejected", "declined", "skip")

_DATE_RE = re.compile(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})")


def today_jst() -> date:
    return datetime.now(JST).date()


def load(path: Path | None = None) -> dict:
    p = HYPOTHESES if path is None else path
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def next_steps(h: dict) -> list[str]:
    """`next_if_false` を、**書かれ方によらず**「手の一覧」にして返す。

    **欄は2つの形で書かれています。** 一覧（YAML の `- ...`）と、
    まるごとの文字列（`|` のブロック）です。文字列をそのまま `for` に渡すと
    **1字ずつ回る** —— 2026-08-17 に `status.py` の出力 644行のうち 480行が
    1字になり、前提も警告も使用量も埋まりました。

    **正本はここです。** `scripts/status.py` の `_next_steps` はこれを呼びます
    （同じ規則を2か所に置くと、片方だけ直す形になります。通算9回出ています）。
    """
    raw = h.get("next_if_false")
    if not raw:
        return []
    if isinstance(raw, str):
        # **段落は割らない。** ブロックで書かれた1件は1件です
        # （空行で区切られていれば、そこだけ割る）。
        return [p.strip() for p in raw.split("\n\n") if p.strip()]
    return [str(x) for x in raw]


def _dispositions(h: dict) -> list[str]:
    """`next_done` を一覧にする。**`next_if_false` と同じ並び**で読みます。"""
    raw = h.get("next_done")
    if not raw:
        return []
    if isinstance(raw, str):
        return [p.strip() for p in raw.split("\n\n") if p.strip()]
    return [str(x) for x in raw]


def parse_disposition(text: str) -> dict | None:
    """1行の記録を読む。**日付と、採用／却下のどちらかが揃って初めて有効。**

    片方しか無い行を有効にすると、「2026-08-26 見た」で消せてしまいます。
    **消せる形にしたら、この道具は最初から要りません。**
    """
    if not text or not text.strip():
        return None
    m = _DATE_RE.search(text)
    if not m:
        return None
    try:
        when = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None
    low = text.lower()
    if any(k in text or k in low for k in _TAKEN):
        choice = "採用"
    elif any(k in text or k in low for k in _REJECTED):
        choice = "却下"
    else:
        return None
    return {"on": when, "choice": choice, "text": text.strip()}


def _closed_on(h: dict) -> date | None:
    raw = h.get("closed_on") or h.get("confirmed_on")
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str):
        m = _DATE_RE.search(raw)
        if m:
            try:
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                return None
    return None


def _is_falsified(h: dict) -> bool:
    """**外れた前提だけを見ます。**

    `survived` の前提の `next_if_false` は、条件が満たされなかったので
    **実行してはいけない手**です。ここに混ぜると、やるべきでないものを
    「未実行」として鳴らし続けることになります。
    `mixed`（半々）は**含めます** —— 半分外れているなら、その半分の手は生きています。
    """
    out = str(h.get("outcome") or "")
    return out.startswith("fals") or out.startswith("mixed") or "外れ" in out


def pending(doc: dict | None = None, today: date | None = None) -> list[dict]:
    """**記録されていない「次の手」**を、閉じた日の古い順に返す。"""
    doc = load() if doc is None else doc
    now = today or today_jst()
    out: list[dict] = []
    for h in doc.get("hypotheses") or []:
        if not isinstance(h, dict) or not _is_falsified(h):
            continue
        steps = next_steps(h)
        if not steps:
            continue
        marks = _dispositions(h)
        closed = _closed_on(h)
        age = (now - closed).days if closed else None
        for i, step in enumerate(steps):
            rec = parse_disposition(marks[i]) if i < len(marks) else None
            if rec is not None:
                continue
            out.append({
                "claim": str(h.get("claim") or "").strip(),
                "lever": h.get("lever"),
                "closed_on": closed,
                "age_days": age,
                "index": i,
                "n_steps": len(steps),
                "step": step,
                # 書きかけ（日付や採用/却下が欠けている行）は、そう言う
                "partial": (marks[i].strip() if i < len(marks) and marks[i].strip() else None),
            })
    out.sort(key=lambda r: (r["closed_on"] or date.min, r["index"]))
    return out


def open_on_lever(doc: dict, lever: str | None) -> list[str]:
    """**同じ腕を狙って、まだ開いている前提**の claim を返す。

    外れた前提の手が「その方向をやめろ」だったとき、**やめる対象は
    たいてい同じ腕の開いた前提**です。意味までは機械に分からないので、
    **候補を並べるところまで**にします（判断は読む側）。
    """
    if not lever:
        return []
    out = []
    for h in doc.get("hypotheses") or []:
        if not isinstance(h, dict) or h.get("outcome") or h.get("closed_on"):
            continue
        if h.get("lever") == lever:
            out.append(str(h.get("claim") or "").strip())
    return out


def report(doc: dict | None = None, today: date | None = None,
           limit: int = 3) -> tuple[str, bool]:
    """印字と、**止めるべきか**を返す。

    止めるのは `GRACE_DAYS` を超えた手が1件でもあるとき。
    **一度に出すのは古い順に `limit` 件まで** —— 31手を一度に並べても、
    どれから手を付けるか決まりません（`docs/JOURNAL.md` の「台帳が長いと読まれない」）。
    """
    doc = load() if doc is None else doc
    now = today or today_jst()
    rows = pending(doc, now)
    lines = ["", "=== 外れた前提の「次の手」が、記録されないまま残っています ==="]
    if not rows:
        lines.append("  （全部 記録済み。**閉じた実験の代金は回収できています**）")
        return "\n".join(lines), False

    overdue = [r for r in rows if (r["age_days"] or 0) > GRACE_DAYS]
    lines.append(f"  未記録の手: **{len(rows)}手**"
                 f"（{GRACE_DAYS}日を超えたもの: **{len(overdue)}手**）")
    lines.append("  **実験を閉じて手に入るのは、この1行だけです。**"
                 "採用か却下かを書くまで、毎周ここに出ます。")
    lines.append("")
    for r in (overdue or rows)[:limit]:
        age = f"{r['age_days']}日前" if r["age_days"] is not None else "日付なし"
        lines.append(f"  ── {r['closed_on']}（{age}）に外れた前提"
                     f"／腕 `{r['lever'] or '-'}`")
        lines.append(f"     前提: {r['claim'][:78]}")
        step = " ".join(str(r["step"]).split())
        lines.append(f"     手 {r['index'] + 1}/{r['n_steps']}: {step[:150]}")
        if r["partial"]:
            lines.append(f"     [!] 書きかけ: 「{r['partial'][:60]}」"
                         " —— **日付と、採用／却下のどちらか**が要ります")
        others = open_on_lever(doc, r["lever"])
        if others:
            lines.append(f"     同じ腕 `{r['lever']}` で、まだ開いている前提 {len(others)}件"
                         " —— **この手が「やめろ」なら、当たるのはここです**:")
            for c in others[:3]:
                lines.append(f"       ・{c[:70]}")
        lines.append("")
    if len(rows) > limit:
        lines.append(f"  （ほか {len(rows) - limit}手。`--all` で全部出ます）")
    lines.append("  書き方: `config/hypotheses.yaml` の その前提に `next_done:` を"
                 "`next_if_false` と**同じ並び**で。")
    lines.append("    例) \"2026-08-26 却下: 実画面の収録は1本30分かかり、"
                 "08/27 の対照を壊すため見送る\"")
    lines.append("  **却下は正しい答えになり得ます。** 書かれていないことだけが問題です。")
    return "\n".join(lines), bool(overdue)
