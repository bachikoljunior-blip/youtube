#!/usr/bin/env python3
"""**読み上げの金額が、いまの calc から出るものか**を、控えぜんぶで照合する。

    python scripts/narration_drift.py              # 予約を持ったまま、ずれている本
    python scripts/narration_drift.py --all        # 公開ずみも含めて全部
    python scripts/narration_drift.py --video <ID> # 1本だけ

## なぜ要るか（2026-08-31 22:xx に足した。**実物で踏んでいる**）

`src/calc/` は**動画を作ったあとも直ります。** 2026-08-31 に
`src/calc/hendo.py` の未払利息の二重取りを直したとき（commit `6ac53d4b`）、
**その calc に乗って既に投稿ずみだった `J67vEIw_VRE` の読み上げ19文のうち
5文が、その瞬間に誤りになりました。**

見つけたのは人です。**機械は何も言いませんでした。**
`src/verify.py` が数字の出どころを見るのは
`_check_headline_from_calc`（**冒頭の stat 1つだけ**、しかも
呼ぶ側が `if portrait:` の中なので**ショート限定**）で、
**長尺の読み上げ全文を calc と突き合わせる目はどこにもありません。**

そして**作ってから出るまでが長い。** 規則は1日1本、予約は先まで積まれており、
**calc を直した回と、その calc に乗った本が公開される日は、何週間も離れます。**
その間、誤った数字を読み上げる本が予約に座り続けます。

## 何を見ているか

読み上げの中の金額（「661万1976円」「5,716,767円」）を整数にして、

    src.calc.<名前> の**出力**（実行する）  ＋  src/calc/<名前>.py の**原文**

のどちらにも無ければ「出どころが無い」と数えます。**原文も見るのは、
基礎控除43万円のような法定の定数が計算の入力で、出力に出ないことがあるため。**

## この道具が言えないこと（**投稿を止める門にしないこと**）

**言い換えは拾えません。** 台本は計算結果を言い換えます（「ずれ 31か月」→
「最大2年7か月」）し、途中の合計を口で足すこともあります。
`_check_headline_from_calc` が `stat_source` の申告を要求しているのは、
まさに「**数字の見た目からは出どころを判定できない**」からです。

**実測 2026-08-31**: 長尺の控え 135本 のうち **20本（14%）**が引っかかり、
その筆頭が `J67vEIw_VRE`（6件）でした。**残りには本当の当たりも
言い換えも混ざっています。** だから**一覧を出すだけ**にしてあり、
`src/verify.py` には**繋いでいません**（繋ぐと、正しい本が
14% 落ちて作り直しに回ります —— `docs/trigger_main.md`
「止める仕掛けを足さないこと」）。

**覆る条件**: 台本に「この金額はどの行から取ったか」を全部 申告させる形
（`stat_source` を読み上げの文ごとに持たせる）にできたら、
言い換えを引かずに済むので、**そのときは門にしてよい。**
そこまでは、**人が読む一覧**です。
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

STASH = ROOT / "data" / "critique_queue"


def _topics() -> dict[str, str]:
    import yaml
    data = yaml.safe_load((ROOT / "config" / "topics.yaml").read_text(encoding="utf-8"))
    return {str(t["id"]): str(t.get("calc") or "") for t in data["topics"]}


def yen(text: str) -> set[int]:
    """文中の金額を整数にする。『661万1976円』『5,716,767円』を同じ土俵へ。"""
    out: set[int] = set()
    t = text.replace(",", "")
    for m in re.finditer(r"(?:(\d+)\s*億)?\s*(\d+)\s*万\s*(\d+)?\s*円", t):
        out.add(int(m.group(1) or 0) * 100_000_000
                + int(m.group(2)) * 10_000 + int(m.group(3) or 0))
    for m in re.finditer(r"(?<![万億\d])(\d{4,})\s*円", t):
        out.add(int(m.group(1)))
    return out


_CACHE: dict[str, str | None] = {}


def haystack(name: str) -> str | None:
    """`src.calc.<name>` の出力と原文を1本の字にする。**桁区切りは潰す。**"""
    if name in _CACHE:
        return _CACHE[name]
    src_path = ROOT / "src" / "calc" / f"{name}.py"
    if not src_path.exists():
        _CACHE[name] = None
        return None
    try:
        proc = subprocess.run([sys.executable, "-m", f"src.calc.{name}"],
                              capture_output=True, text=True, timeout=300,
                              cwd=str(ROOT))
        out = proc.stdout if proc.returncode == 0 else ""
    except Exception:
        out = ""
    if not out:                       # 走らない calc は判定しない（黙って通す）
        _CACHE[name] = None
        return None
    _CACHE[name] = re.sub(r"[\s,、　_]", "",
                          out + "\n" + src_path.read_text(encoding="utf-8"))
    return _CACHE[name]


def scan(only_video: str = "") -> list[dict]:
    calc_of = _topics()
    rows = []
    for meta_path in sorted(STASH.glob("*.json")):
        if meta_path.name.endswith(".plan.json"):
            continue
        if only_video and meta_path.stem != only_video:
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if meta.get("orientation") != "横":       # 長尺だけ（ショートは冒頭の門が見ている）
            continue
        name = calc_of.get(str(meta.get("topic")) or "", "")
        if not name:
            continue
        hay = haystack(name)
        if hay is None:
            continue
        miss = sorted({v for line in (meta.get("narration") or [])
                       for v in yen(line) if str(v) not in hay})
        if miss:
            rows.append({"video_id": meta_path.stem, "topic": meta.get("topic"),
                         "calc": name, "missing": miss})
    return rows


def _uploaded() -> dict[str, dict]:
    out = {}
    for line in (ROOT / "data" / "uploaded.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                d = json.loads(line)
                out[d.get("video_id")] = d
            except ValueError:
                pass
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true",
                    help="公開ずみも含めて全部（既定は、まだ出ていない本だけ）")
    ap.add_argument("--video", default="", help="1本だけ見る")
    args = ap.parse_args(argv)

    rows = scan(args.video)
    up = _uploaded()
    now = datetime.datetime.now(datetime.timezone.utc)

    def when(vid: str):
        at = (up.get(vid) or {}).get("at")
        if not at:
            return None
        try:
            return datetime.datetime.fromisoformat(str(at).replace("Z", "+00:00"))
        except ValueError:
            return None

    if not rows:
        print("[drift] 読み上げと calc のずれは見つかりませんでした")
        return 0

    ahead = [r for r in rows if (when(r["video_id"]) or now) > now]
    print(f"[drift] 読み上げの金額が、いまの calc の出力にも原文にも無い長尺: "
          f"**{len(rows)}本**")
    print(f"[drift] うち **まだ公開されていない（引き上げられる）: {len(ahead)}本**")
    print("[drift] **一覧です。門ではありません** —— 言い換えも混ざります"
          "（この file の冒頭「この道具が言えないこと」）。")

    show = rows if args.all else ahead
    for r in sorted(show, key=lambda d: str(when(d["video_id"]) or "")):
        t = when(r["video_id"])
        stamp = t.isoformat()[:16] if t else "予約なし"
        print(f"  {stamp}  {r['video_id']}  {r['topic']}  "
              f"（calc {r['calc']}・{len(r['missing'])}件）")
        print(f"      出どころの無い額: {r['missing'][:8]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
