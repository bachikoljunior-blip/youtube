"""機械が出す一覧に、**自分の当たり率を測らせる**。

    from src import alerts
    r = alerts.ring("stranded", len(items))
    if r.folded:
        print(r.line)          # 1行だけ。全文は `--alerts-all`
    else:
        ...全文を出す...

## なぜ要るか（2026-08-16。**同じ形の欠陥が3件出てから足しています**）

    8/16 09:5x  持ち越しの上位が「既に潰れたもの」で埋まっていた   当たり率 低
    8/16 08:2x  「予約し忘れ」警告が12件まで育ち               **当たり0件**
    8/16 13:0x  「強い重なり」警告が22組まで育ち               **当たり0件**（3件目）

**3件とも「機械が出す一覧が、当たりを含まないまま育っていた」**です。
1件ずつ潰しても `status.py` は一覧を増やし続けるので、**同じ形が4件目に出ます。**
前の回の申し送りがそう書いています ——

> **次に要るのは個別の潰しではなく、一覧を出す側に「当たり率」を自分で測らせること**
> —— 鳴らした件数と、そのうち実際に手が打たれた件数を残し、
> **当たり0が続く一覧は、機械のほうから畳ませる。**

**畳むのは消すことではありません。** 件数の1行は必ず残り、`--alerts-all` で全文が出ます。
**間違って畳んでも失うのは1コマンドぶんで、見落としではない** —— この非対称が、
下のしきい値を低めに置ける理由です。

## 「当たり」の数え方（**散文から読まないこと**）

当たり ＝ `data/runs.jsonl` の ship 行の `closes` に、この一覧の鍵が載っていること。

    python scripts/run_marker.py --ship "fix: ..." --closes stranded

**日誌の文からは読みません。** 宣言を散文に置いた結果、同じ穴を3回踏んでいます
（書きすぎ2回・書き忘れ1回。`scripts/run_marker.py` の `--closes` の節）。
**ここは最初から構造だけです。**

## 鳴った回数は「回」で数える（**行数ではありません**）

1回の中で `status.py` を3回叩いても、鳴ったのは1回です。
だから ledger には `session` を書き、**同じセッションの同じ鍵は1回に畳みます。**
セッションIDが取れない環境（手元での実行）では日付＋鍵で畳みます。

## しきい値（**掛け算してから置いています**）

`FOLD_AFTER = 8`。**8回続けて鳴って、当たりが0回なら畳む。**

- **8回の 0/8 は、当たり率の 95% 上限が 31%** です（1 − 0.05^(1/8)）。
  単独では弱い証拠です。**それでも畳むのは、外したときの損が「1行 vs 20行」だから**
  （上の非対称）。ここを 20回にすると上限は 14% まで締まりますが、
  **その間ずっと惰性の一覧を全文で読むことになります。**
- 1周は 41分（`quota.py --pace`）なので **8回 ≒ 5.5時間**。
  実際に出た3件は、どれもこれよりずっと長く鳴り続けていました。
- **当たりが1回でも出れば数え直しです**（`rings_since` が 0 に戻る）。
  効いている一覧は畳まれません。

**覆る条件**: 畳んだ一覧を `--alerts-all` で開いて、**当たりが実際に入っていた**ことが
2回あったら、この数を倍にすること（そのときは `docs/JOURNAL.md` に実物を書く）。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))

ROOT = Path(__file__).resolve().parent.parent

# **検査から呼ばれたときに、本物の台帳へ書かないこと**（2026-08-17 に踏んだ）。
#
# `status_lines` は 8回鳴って当たり0で畳まれ、`status.py` の表にもそう出ていました。
# **8回とも、鳴らしたのは `pytest` です。**（`data/alerts.jsonl` の実物を数えた。
# `_dedupe_token()` はセッションIDなので、1周につき1行きっかり積まれる）
# **`status.py` の出力が中央値の1.5倍を超えたことは、一度もありません。**
#
# つまり **当たり率という計器が、測っていたのは検査の実行回数**でした。
# しかも8回目で畳まれた瞬間、**その畳みを見た検査そのものが赤くなります**
# （`tests/test_status_lines.py`）。次の回は毎回、赤い pytest で始まることになる。
#
# `tests/conftest.py` がここを tmp へ向けます。**呼ぶ側には何も書かせません** ——
# 一覧を足した回が「検査では ledger= を渡す」を忘れる形（通算7回の「片方だけ」）を、
# 構造で外すためです。
LEDGER = Path(os.environ.get("YT_ALERTS_LEDGER") or (ROOT / "data" / "alerts.jsonl"))
RUNS = Path(os.environ.get("YT_ALERTS_RUNS") or (ROOT / "data" / "runs.jsonl"))

# 8回続けて鳴って当たり0なら畳む。理由と覆る条件は上の docstring。
FOLD_AFTER = 8

# `--alerts-all` が立つと、畳まずに全文を出す。**呼ぶ側に条件を書かせないため**に
# ここに置いています（call site が `if r.folded and not FLAG` だと、
# 新しい一覧を足した人が片方だけ書き忘れます —— 通算7回踏んだ「片方だけ直す」形）。
_SHOW_ALL = False


def set_show_all(on: bool) -> None:
    global _SHOW_ALL
    _SHOW_ALL = bool(on)


def show_all() -> bool:
    return _SHOW_ALL


def session_id() -> str:
    """自分のセッションID。**推測しないこと**（`scripts/run_marker.py` と同じ規則）。"""
    raw = os.environ.get("CLAUDE_CODE_REMOTE_SESSION_ID", "")
    return ("session_" + raw[4:]) if raw.startswith("cse_") else raw


def _read(path: Path) -> list[dict]:
    out: list[dict] = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def rings(key: str | None = None, *, path: Path | None = None) -> list[dict]:
    rows = _read(path or LEDGER)
    return [r for r in rows if key is None or r.get("key") == key]


def acts(key: str, *, path: Path | None = None) -> list[dict]:
    """当たり ＝ ship 行の `closes` にこの鍵が載っているもの。**散文は読みません。**"""
    out = []
    for r in _read(path or RUNS):
        if r.get("kind") != "ship":
            continue
        if key in (r.get("closes") or []):
            out.append(r)
    return out


@dataclass
class Ring:
    key: str
    n: int
    rings_total: int = 0
    rings_since: int = 0          # 最後の当たりから何回鳴ったか（当たりが無ければ通算）
    acts_total: int = 0
    last_act: str = ""
    folded: bool = False
    foldable: bool = True
    line: str = ""
    fold_after: int = FOLD_AFTER

    @property
    def hit_rate(self) -> float:
        return (self.acts_total / self.rings_total) if self.rings_total else 0.0

    @property
    def would_fold(self) -> bool:
        """`--alerts-all` を無視した判定。**表はこちらを出します** ——
        全文を見にきた回にも「畳む条件に入っている」ことが見えないと、
        `--alerts-all` を1回付けただけで状態が消えて見えます。"""
        return bool(self.foldable and self.rings_since >= self.fold_after)


def _stamp(rec: dict) -> str:
    return str(rec.get("at") or "")


def state(key: str, *, ledger: Path | None = None, runs: Path | None = None,
          n: int = 0, foldable: bool = True, fold_after: int = FOLD_AFTER) -> Ring:
    """**記録せずに**いまの姿だけを出す（表示・検査用）。"""
    rs = rings(key, path=ledger)
    ac = acts(key, path=runs)
    last = max((_stamp(a) for a in ac), default="")
    since = [r for r in rs if not last or _stamp(r) > last]
    r = Ring(key=key, n=n, rings_total=len(rs), rings_since=len(since),
             acts_total=len(ac), last_act=last, foldable=foldable,
             fold_after=fold_after)
    r.folded = bool(foldable and r.rings_since >= fold_after and not _SHOW_ALL)
    r.line = _fold_line(r)
    return r


def _fold_line(r: Ring) -> str:
    if not r.folded:
        return ""
    # **「通算0回」と「最後の当たり以降0回」を混ぜないこと。**
    # 一度当たった一覧が再び惰性に落ちる形は普通に起きるので、
    # そのとき「当たり0件」と書くと、実際にはあった当たりを消して見せます。
    since = (f"通算 {r.rings_since}回" if not r.last_act
             else f"最後に手が打たれてから {r.rings_since}回")
    return (f"  （{r.key}: {r.n}件。**{since}続けて鳴って、"
            f"その間に手が打たれていないので畳んでいます** —— 全文は `--alerts-all`。"
            f"当たったら `run_marker.py --ship ... --closes {r.key}`）")


def _dedupe_token() -> str:
    """同じ回の中で何度叩いても、鳴ったのは1回。"""
    sid = session_id()
    if sid:
        return sid
    return "local:" + datetime.now(JST).strftime("%Y-%m-%d")


def ring(key: str, n: int, *, foldable: bool = True, record: bool = True,
         ledger: Path | None = None, runs: Path | None = None,
         fold_after: int = FOLD_AFTER) -> Ring:
    """一覧が鳴ったことを1行残し、**畳むかどうかを返す。**

    `n == 0`（出すものが無かった）ときは**鳴っていない**ので記録しません。
    「見にいったが空だった」を鳴った回数に混ぜると、当たり率が薄まります。
    """
    path = ledger or LEDGER
    if record and n > 0:
        token = _dedupe_token()
        already = any(r.get("key") == key and r.get("session") == token
                      for r in rings(key, path=path))
        if not already:
            path.parent.mkdir(parents=True, exist_ok=True)
            rec = {"at": datetime.now(JST).isoformat(timespec="seconds"),
                   "key": key, "n": int(n), "session": token}
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return state(key, ledger=path, runs=runs, n=n, foldable=foldable,
                 fold_after=fold_after)


def table(*, ledger: Path | None = None, runs: Path | None = None,
          fold_after: int = FOLD_AFTER) -> list[Ring]:
    """鍵ごとの当たり率。**鳴った順**（古い一覧が上に来るように、初出の順）。"""
    seen: list[str] = []
    for r in rings(path=ledger):
        k = r.get("key")
        if isinstance(k, str) and k not in seen:
            seen.append(k)
    return [state(k, ledger=ledger, runs=runs, fold_after=fold_after) for k in seen]


def render_table(rows: list[Ring]) -> str:
    if not rows:
        return ("=== 警告の当たり率（一覧が自分で測っています）===\n"
                "  まだ1件も鳴っていません。")
    out = ["=== 警告の当たり率（一覧が自分で測っています）===",
           "  鍵                    鳴った  当たり  当たりから  状態"]
    for r in rows:
        mark = ("**畳んだ**" if r.would_fold
                else f"あと{r.fold_after - r.rings_since}回で畳む"
                if r.foldable and r.rings_since >= r.fold_after - 2
                else "出す")
        out.append(f"  {r.key:<20}  {r.rings_total:>5}  {r.acts_total:>5}  "
                   f"{r.rings_since:>9}  {mark}")
    out.append("  **当たり ＝ `run_marker.py --ship ... --closes <鍵>`。**"
               "日誌の文からは数えません。")
    out.append(f"  **{FOLD_AFTER}回続けて当たり0なら、機械のほうから畳みます**"
               "（消しません。`--alerts-all` で全文）。")
    return "\n".join(out)
