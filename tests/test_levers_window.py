"""**「宣言と実際」の合計を、印字する10行と同じ窓で採らないこと。**

## なぜ要るか（2026-08-29・最適化の回の実測）

`levers.report()` は `recent(path, 10)` の 10件 に、行と**合計と門**を全部
載せていました。**その 10件 は、いまの回転では 1.4〜5.2時間**です
（ship は 7日 で 342件 ＝ 1時間に 2件 前後）。

そして `eta_target` は Analytics 由来で**1日に1度しか動きません**
（`src/levers.py` の冒頭が、その裏取り）。
**つまりその窓の「実際」は、構造上ほぼ 0 です。**

実測（`data/runs.jsonl` の末尾 60件 を 3件ずつずらして 21箇所）::

    実際が 0 か −1                        21箇所 中 **18箇所**
    `[!] 言ったより遠のいています` が出た    **11箇所（52%）**
    そのほとんどが 宣言が負・実際が 0

**`--moves` に負を書く ＝ 腕を引いて日付を早めると宣言する**ことなので、
**手順どおりに宣言した回ほど、この門が鳴っていました。**
`src/arm_speed.forward()` が「前提を閉じると下がる」だったのと同じ形の符号違い
（`scripts/drift.py` の註・2026-08-27 の実測）。

## 7日 で採ると

    宣言の合計 **−915日** ／ 実際の合計 **+33日**（329件）

**これは本物の赤字**で、同じ 7日 の `data/eta.jsonl` の累計（**+33日**）と
一致します（`scripts/eta.py` の `traj_trend`）。**別々の台帳から同じ数が出た**ので、
どちらも読み方が合っています。

## 覆る条件

- `eta_target` が1日に何度も動くようになったら、窓を短くしてよい。
  **そのときは上の「10件 ＝ 1.4〜5.2時間」を測り直すこと**（回転の速さで変わります）
- `reconcile()` が `totals` を受け取らなくなったら、合計は再び 10件 の窓に戻ります。
  **この検査が落ちて、そう教えます**
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src import levers

NOW = datetime(2026, 8, 29, 0, 0, tzinfo=timezone.utc)


def _ship(minutes_ago: float, moves: int, target: str, lever="density"):
    return {"kind": "ship", "at": (NOW - timedelta(minutes=minutes_ago)).isoformat(),
            "lever": lever, "moves": moves, "eta_target": target,
            "eta_basis": "軌跡", "what": "x"}


def _write(tmp_path: Path, rows) -> Path:
    p = tmp_path / "runs.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                 encoding="utf-8")
    return p


def test_since_は日で切る(tmp_path):
    rows = [_ship(60 * 24 * 9, 0, "2027-01-01"), _ship(60, 0, "2027-01-01")]
    p = _write(tmp_path, rows)
    got = levers.since(p, days=7, now=NOW)
    assert len(got) == 1, "7日 より古い ship を合計に入れています"


def test_合計は10行の窓ではなく渡された窓から採る(tmp_path):
    """**行は直近10件・合計は 7日。** 混ぜると門が窓の当たりはずれで鳴ります。"""
    # 直近10件は「宣言 0 ／ 実際 0」に見えるが、7日 ぜんぶでは大きく外している。
    older = [_ship(60 * 24 * 3 + i, -5, "2026-12-01") for i in range(6)]
    older.append(_ship(60 * 24 * 3, -5, "2027-01-01"))    # ← ここで +31日 動く
    recent_rows = [_ship(10 - i * 0.5, 0, "2027-01-01") for i in range(10)]
    span = list(reversed(older + recent_rows))            # 新しい順
    lines = levers.reconcile(span[:10], list(reversed(span)))
    total = [ln for ln in lines if "宣言の合計" in ln]
    assert total, "合計の行が出ていません"
    assert "件" in total[0] and "日" in total[0]
    assert "直近 7日" in total[0] or "件" in total[0]
    assert "-30日" in total[0] or "-35日" in total[0], (
        f"合計が 10行 の窓から採られています（{total[0]}）。"
        "10行 は 1.4〜5.2時間 しかなく、その窓の「実際」は構造上ほぼ 0 です"
    )


def test_門が鳴ったら窓が違うことを同じ行で言う(tmp_path):
    """**裸の「遠のいています」を出さないこと**（`CLAUDE.md`）。

    上の10行を見た読み手は「実際 0 ばかりなのに、なぜ遠のいたと言われるのか」で
    止まります。**窓が別だと、その場に書いてあること。**
    """
    older = [_ship(60 * 24 * 3 + i, -5, "2026-12-01") for i in range(6)]
    older.append(_ship(60 * 24 * 3, -5, "2027-01-01"))
    recent_rows = [_ship(10 - i * 0.5, 0, "2027-01-01") for i in range(10)]
    span = list(reversed(older + recent_rows))
    lines = levers.reconcile(span[:10], list(reversed(span)))
    hit = [ln for ln in lines if "[!]" in ln]
    if hit:
        assert "上の10行の窓ではありません" in hit[0], (
            "門は鳴るのに、上の10行と窓が別であることを言っていません"
        )


def test_totals_を渡さない回も落ちない(tmp_path):
    """道具を単体で呼ぶ回を落とさないこと（**ただし窓は名乗る**）。"""
    rows = [_ship(10 - i, 0, "2027-01-01") for i in range(4)]
    lines = levers.reconcile(list(reversed(rows)))
    assert any("宣言の合計" in ln for ln in lines)
    assert any("直近 4件" in ln for ln in lines), (
        "窓を名乗っていません。**どれだけの窓で見た合計かが書いていないと、"
        "次の回はまた同じ取り違えをします**"
    )


def test_report_は7日の合計を渡す():
    """**実物の台帳で**、合計が 10件 の窓から採られていないこと。"""
    lines = levers.report(Path(__file__).resolve().parent.parent / "data" / "runs.jsonl")
    total = [ln for ln in lines if "宣言の合計" in ln]
    assert total, "合計の行が出ていません"
    assert "直近 7日" in total[0], (
        f"合計が 7日 の窓から採られていません（{total[0]}）"
    )
