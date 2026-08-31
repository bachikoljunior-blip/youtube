"""**開いている前提の床が、題材の接頭辞で決まっているとき、それを埋める側へ渡す。**

（API は 0 単位。読むのは `config/hypotheses.yaml` と `data/uploaded.jsonl` と
`config/topics.yaml` だけ）

## なぜ要るか（2026-08-29・最適化の回。**実測から**）

`config/hypotheses.yaml` の「題材の族を税・年金・社会保険の外へ出しても、
1本あたり再生は変わらない」（期限 2026-09-19・腕 `rpm`）は、判定に
**`s-ribo-` で始まるショートを 8本 公開していること**を要求します。

その日の実物:

    config/topics.yaml   `s-ribo-` の題      **8件**（足りている）
    data/uploaded.jsonl  作って予約に入った  **2件**
    公開済み                                **0件**

つまり**題材は在るのに、6件が一度も作られていない**。そして
`scripts/batch_build.py` の `pick()` は `score × family_perf` で並べ、
`--per-calc 2` で切るだけで、**台帳の床を1文字も見ていません。**
`ribo` は実績のまだ無い族なので `family_perf` は全体平均 ＝ **真ん中の順位**。
60族が並ぶ中で真ん中に居るかぎり、6件が揃う保証はどこにもありません。

**そのあいだ `scripts/deadline_check.py` はこう印字していました**:

    [..] 09-19  …… 要 8 ／ いま 0（`since` から 1日）
         → **まだ数えはじめたところです。**伸び率が出れば日が出ます ——
           **この回は何もしないのが正解です**（畳まないこと・条件を緩めないこと）

**「伸び率が出れば」は来ません。** 伸び率の元になる本を作る側が、
この床の存在を知らないからです。**「何もしないのが正解」は、
この形のときだけ偽になります** —— 待っていても埋まらない床について、
待てと言っていたことになります。

## この前提が、なぜ他より高くつくか

`next_if_false` の1が言っています ——
族が効いているなら、`eta.py` の `per_video` の天井（実測の最大 1,891）は
**税・年金・社会保険の中での最大**でしかなく、外の族では引き直せます。

`eta.py` は毎回「ショートは ×16.5 要る／この腕のいちばん良い一手を当てても
まだ 8.9倍 足りない ＝ **開いている `per_video` の前提を全部 閉じても、
この帯には届きません**」と印字しています。**その天井を引き直せる可能性を
持っている、ただ1つの開いた前提**が、6本の未着手で止まっていました。

## 何を返すか

`starved()` が、**開いている前提のうち、`accrual` の `count_expr` が
題材の接頭辞で数えているもの**を返します。数えるのは3つ:

    need    床（`need`）
    built   `data/uploaded.jsonl` に在る同じ接頭辞の本（＝作って予約まで入った）
    stock   `config/topics.yaml` に在って、まだ作っていない同じ接頭辞の題

**`built` で見るのは、公開ではなく「作った」ほう**です。予約の順番待ちは
実測 8〜11日（`scripts/queue_lag.py`）あるので、公開で見ると
「まだ足りない」と分かるのが10日 遅れます。**間に合わせる側が動けるのは、
作る時点だけ**です。

## 使う側（`scripts/batch_build.pick()`）

並べ替えの**最後**に、床の足りない接頭辞の題を先頭へ持ち上げます。
**`per_calc` は迂回しません** —— あれは「同じ制度の本が1日に何本も並ぶと
繰り返しと判定される」という収益化の側の事実で（`CLAUDE.md`）、
床のために崩してよいものではありません。持ち上げるのは順番だけで、
1回に取れるのは変わらず `per_calc` 本です。

## 覆る条件

- `count_expr` が `startswith('...')` 以外の書き方で題材を絞りはじめたら、
  `_prefixes_of()` は**黙って空を返します**（＝ 何も持ち上げません）。
  そのときは、こちらを足すのではなく **`needs` に接頭辞の欄を作る**こと
  —— 式を正規表現で読むのは、式が短いあいだだけ成り立ちます。
- 床のある接頭辞が3つ以上 同時に開いたら、先頭は取り合いになります。
  いまは**期限の近い順**に並べていますが、これは根拠のある順ではありません。
  そのときは「期限までに間に合う本数」で割ること。
- `tests/test_floor_topics.py` が、`s-ribo-` の実物で床と数え方を押さえています。
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HYPOTHESES = ROOT / "config" / "hypotheses.yaml"
TOPICS = ROOT / "config" / "topics.yaml"
LEDGER = ROOT / "data" / "uploaded.jsonl"

#: `count_expr` の中の `startswith('<接頭辞>')`。**題材の id にしか使いません**
_PREFIX_RE = re.compile(r"startswith\(\s*'([^']+)'\s*\)")


def _prefixes_of(count_expr: str) -> list[str]:
    """`count_expr` が題材の接頭辞で数えているなら、その接頭辞。

    **`topic` を見ている式だけ**を拾います。`uploaded_at` や `at` を
    `startswith` している式は題材の話ではないので、外します。
    """
    if "topic" not in (count_expr or ""):
        return []
    return [p for p in _PREFIX_RE.findall(count_expr or "") if p]


def _ledger_topics(path: Path | None = None) -> list[str]:
    """`data/uploaded.jsonl` の `topic`（＝ 作って予約まで入った本）。"""
    out: list[str] = []
    p = path or LEDGER
    if not p.exists():
        return out
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            continue
        t = r.get("topic")
        if t:
            out.append(str(t))
    return out


def _topic_ids(path: Path | None = None) -> list[str]:
    """`config/topics.yaml` の題の id（`calc` の在るものだけ）。

    `calc` の無い題は `pick()` が永久に選びません（あちらが要求します）。
    **在庫として数えると、埋まらない床が「埋まる」に見えます。**
    """
    import yaml

    p = path or TOPICS
    if not p.exists():
        return []
    doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    rows = doc.get("topics") or []
    return [str(t["id"]) for t in rows
            if isinstance(t, dict) and t.get("id") and t.get("calc")]


def starved(today: date | None = None,
            hyp_path: Path | None = None,
            ledger_path: Path | None = None,
            topics_path: Path | None = None) -> list[dict]:
    """**床の足りない接頭辞**を、期限の近い順に返す。

    返りの1件::

        prefix    題材の接頭辞（例 `s-ribo-`）
        need      床（前提の `need`）
        built     作って予約まで入った本（`data/uploaded.jsonl`）
        short     あと何本 作れば床に届くか（`need - built`・0以上）
        stock     まだ作っていない同じ接頭辞の題（`config/topics.yaml`）
        makeable  この回から実際に作れる本数（`min(short, stock)`）
        deadline / claim / lever   その前提の欄

    **期限を過ぎた前提は返しません**（もう間に合わないので、順番を
    取り合う理由がない）。**`short` が 0 の前提も返しません。**
    """
    import yaml

    p = hyp_path or HYPOTHESES
    if not p.exists():
        return []
    doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    t = today or date.today()
    led = _ledger_topics(ledger_path)
    ids = _topic_ids(topics_path)
    in_led = set(led)

    out: list[dict] = []
    for h in (doc.get("hypotheses") or []):
        if not isinstance(h, dict) or h.get("closed_on"):
            continue
        dl = str(h.get("deadline") or "")
        if dl and dl < t.isoformat():
            continue
        for n in (h.get("needs") or []):
            if not isinstance(n, dict) or n.get("kind") != "accrual":
                continue
            need = n.get("need")
            if not isinstance(need, int) or need <= 0:
                continue
            for prefix in _prefixes_of(str(n.get("count_expr") or "")):
                built = sum(1 for x in led if x.startswith(prefix))
                short = max(0, need - built)
                if short <= 0:
                    continue
                stock = sum(1 for i in ids
                            if i.startswith(prefix) and i not in in_led)
                out.append({
                    "prefix": prefix, "need": need, "built": built,
                    "short": short, "stock": stock,
                    "makeable": min(short, stock),
                    "deadline": dl or None,
                    "claim": str(h.get("claim") or "")[:60],
                    "lever": h.get("lever"),
                })
    out.sort(key=lambda r: (r["deadline"] or "9999-99-99", r["prefix"]))
    return out


def lines(rows: list[dict] | None = None, today: date | None = None) -> list[str]:
    """画面へ出す行（`batch_build` と `deadline_check` が同じ字を出すため）。"""
    rows = starved(today=today) if rows is None else rows
    out: list[str] = []
    for r in rows:
        head = (f"[床] **{r['prefix']}** 開いた前提の床 {r['need']}本 に対し、"
                f"作ってあるのは {r['built']}本 ＝ **あと {r['short']}本**"
                f"（期限 {r['deadline']}・腕 {r['lever']}）")
        if r["stock"] <= 0:
            head += ("　[!] **題材の在庫が0件です。**`config/topics.yaml` に"
                     f" `{r['prefix']}` の題を足さないかぎり、この床は永久に埋まりません")
        elif r["stock"] < r["short"]:
            head += (f"　[!] **在庫は {r['stock']}件 しかありません**"
                     f"（あと {r['short'] - r['stock']}件 は題から作ること）")
        else:
            head += f"　題材の在庫 {r['stock']}件 ＝ **作るだけで埋まります**"
        out.append(head)
    return out
