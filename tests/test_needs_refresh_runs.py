"""**`refresh:` に書いた手は、実際に撃てるか**（2026-08-29 06:0x・最適化の回）。

`config/hypotheses.yaml` の `needs.refresh:` は、`deadline_check` が
「時計は来ています。足りないのはデータのほうです」と言うときに、**そのまま
渡す手**です。渡された回はそれを撃ちます。**撃てなければ、その要件は
そこで止まります。**

## この検査を書いた理由（**同じ穴を2回 踏んでいます**）

**1回目**（台帳の 972行・2026-08-27）:

    最初 `python scripts/snapshot.py` と書いて、その30分後に踏みました ——
    当時あれは `record()` を持つだけの部品で `__main__` が無く、
    直に走らせると **exit 0 で1行も書かずに終わりました。**

**2回目**（この検査を書いた回・2026-08-29）: 台帳へ 8件 転記したうちの1件に
`python -m src.rpm_mix` と書き、**その5分後に実際に撃ったら**——

    `main()` の `if args.show or not args.record: print(render(last())); return 0`
    → **67時間 前の点をそのまま印字して exit 0。**
    しかも印字の中身は「**この日に撃ち直すこと**」。
    **撃ち直した回に、撃ち直せと出ていました。**（正しくは `--record` 付き）

**どちらも「読めば分かった」ものです。** 1回目は同じファイルの 972行 に
書いてあり、2回目はその 972行 を読んだうえで踏んでいます。
**読んで防ぐのは、もう2回 失敗しました。**

## ここで確かめること／確かめないこと

**確かめる**: 入口が在るか（`__main__` / スクリプトの実体）と、
コマンドに書いた**旗が、その入口の `--help` に在るか**。
`--help` は API を1単位も使いません（実測 0.06秒）。

**確かめない**: 撃ったら本当に点が増えるか。**それには API の単位が要り**、
枠が尽きている回に検査で捨てるのは目標に反します
（`CLAUDE.md`「先に使い切ると、リセットまで1回も起きられない」）。
**だから「`--record` を書き忘れた」形は、ここでは捕まりません。**

**覆る条件**: 「撃ったのに点が増えなかった」がもう一度 起きたら、
ここではなく **`deadline_check` の側**で捕まえること —— 渡した `refresh:` を
撃った回が、その前後で `newest_point` を比べて記録する。
そこまでやれば、この検査は入口の有無だけに戻してよい。
"""
from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def _needs() -> list[tuple[str, dict]]:
    doc = yaml.safe_load((ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
    out: list[tuple[str, dict]] = []
    for h in doc["hypotheses"]:
        if any(k in h for k in ("verdict", "closed_on", "outcome")):
            continue
        for need in h.get("needs") or []:
            if isinstance(need, dict):
                out.append((str(h.get("claim", ""))[:40], need))
    return out


def test_data_file_に書いたパスが実在すること():
    """**在らないパスを申告すると、門は「1点も読めません」を毎周 出します。**

    それは「取り直せ」と同じ向きなので害は小さいのですが、**取り直しても
    直りません**（そのファイルは誰も書かない）。
    """
    for claim, need in _needs():
        src = str(need.get("data_file") or "").strip()
        if not src:
            continue
        assert (ROOT / src).exists(), (
            f"**`data_file:` が実在しないパスです**: {src}（{claim}）")


def test_refresh_に書いた手が実際に撃てること():
    """入口が在り、書いた旗をその入口が受け取ること。**API は使いません。**"""
    seen: set[str] = set()
    for claim, need in _needs():
        cmd = str(need.get("refresh") or "").strip()
        if not cmd or cmd in seen:
            continue
        seen.add(cmd)
        parts = shlex.split(cmd)
        assert parts and parts[0] in ("python", "python3"), (
            f"**`refresh:` は python の呼び出しに限っています**: {cmd}（{claim}）")

        # 入口が在るか
        if parts[1] == "-m":
            mod = parts[2]
            path = ROOT / (mod.replace(".", "/") + ".py")
            assert path.exists(), f"**モジュールが在りません**: {mod}（{claim}）"
            src = path.read_text(encoding="utf-8")
            assert '__main__' in src, (
                f"**`{mod}` に `__main__` がありません** ——"
                f" `python -m` で撃つと何も起きずに終わります（{claim}）")
            head = parts[:3]
        else:
            path = ROOT / parts[1]
            assert path.exists(), f"**スクリプトが在りません**: {parts[1]}（{claim}）"
            src = path.read_text(encoding="utf-8")
            assert '__main__' in src, (
                f"**`{parts[1]}` に `__main__` がありません** ——"
                " 直に走らせても1行も書かずに終わります"
                f"（2026-08-27 に `snapshot.py` で踏んだ形。{claim}）")
            head = parts[:2]

        flags = [p for p in parts[len(head):] if p.startswith("--")]
        if not flags:
            continue
        got = subprocess.run([sys.executable, *head[1:], "--help"],
                             cwd=ROOT, capture_output=True, text=True, timeout=120)
        assert got.returncode == 0, (
            f"**`--help` が落ちます**: {cmd}\n{got.stderr[-600:]}")
        for flag in flags:
            assert flag in got.stdout, (
                f"**`{flag}` を受け取らない入口です**: {cmd}（{claim}）\n"
                f"{got.stdout[:400]}")
