"""**旧道具を背景で起こす口が、どこにも繋がっていないこと**（2026-09-08 06:5x・optimizer・Opus）。

## なぜ要るか（**3回目**です）

`docs/METHOD.md` §8:

> **「使わない」は文書に書くだけでは止まらない —— 起こす口を全部 外すこと。**

その「全部」から漏れが 2回 出ています:

    2026-09-06 02:1x   `next_round.py main()` の `ahead_sweep.kick()` と
                       SessionStart の `ahead_sweep.sh` を外した
                       —— 旧道具が 09/06 00:01 に **旧作りの本 8本 に publishAt を打った**あと
    2026-09-06 17:xx   `next_round.py main()` の旧道具の読み出し3つを外した
    2026-09-08 06:5x   **`run_marker.py` の `ahead_sweep.kick()` と `niche_ceiling.kick()`**（この検査）

3回目の実測: **`python -m pytest tests/ -q` を撃っただけ**で、06:57:51 JST に
`niche_ceiling.kick()` が背景（`start_new_session=True`）で走り、yt-dlp で外の本を漁って
`data/niche_corpus.jsonl` に **468行**・`data/niche_ceiling.jsonl` に 1行・
`data/sub_ask_sweep.jsonl` に 8行 を足し、絵 16枚 と字幕 4本 を落とし、`videos.list` を **1単位** 使いました。
生きた引き直しである証拠: `J6i7L0QSRSQ` の再生が 09/04 の 5,124,861回 → この回 5,379,678回。

**＝ 検査を撃つことに、副作用と API の値段が付いていました。**
`ahead_sweep` の側は 09/06 に旧作りの本 8本 を公開させた当のものなので、
**検査を撃っただけで動く口に繋いだままにはできません。**

**関数は消しません**（§8）。**呼ぶ所だけ**を見張ります。

**覆る条件**: 旧道具を使う判断が `docs/METHOD.md` に書かれたら、そのときは
**kick（背景・回の意思と関係なく走る）ではなく、手順から呼ぶこと** —— この検査はその形なら通ります
（`kick()` の呼び出しだけを見ており、関数の存在も、手順からの呼び出しも咎めません）。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: 背景で旧道具を起こす関数を持つもの。**関数は在ってよい。呼ばれていないことを見る。**
KICKERS = ("ahead_sweep", "niche_ceiling")

#: 毎周 必ず撃たれる口。ここから kick が生えると、回の意思と関係なく走る。
WATCHED = (
    Path("scripts") / "run_marker.py",
    Path("scripts") / "next_round.py",
    Path("scripts") / "next_round_owner.py",
    Path("scripts") / "spawn_prompt.py",
)


def _live_lines(path: Path) -> list[tuple[int, str]]:
    """註（`#` で始まる行）と docstring らしき行を落として、生きている行だけ返す。"""
    out: list[tuple[int, str]] = []
    in_doc = False
    for i, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        s = raw.strip()
        # 素朴でよい: 三重引用符の開閉を数えるだけ（この4ファイルの形で足りる）
        if s.count('"""') == 1 or s.count("'''") == 1:
            in_doc = not in_doc
            continue
        if in_doc or s.startswith("#") or not s:
            continue
        out.append((i, raw))
    return out


def test_毎周撃たれる口から_kick_が生えていないこと() -> None:
    """**本体の1件。** `<旧道具>.kick(` の呼び出しが、生きている行に無いこと。"""
    bad: list[str] = []
    for rel in WATCHED:
        p = ROOT / rel
        if not p.exists():
            continue
        for lineno, line in _live_lines(p):
            for mod in KICKERS:
                # `_sweep.kick()` のような別名も拾うため、import の別名を先に集める
                if re.search(r"\.kick\s*\(", line):
                    src = p.read_text(encoding="utf-8")
                    aliases = set(re.findall(rf"import\s+{mod}\s+as\s+(\w+)", src)) | {mod}
                    for a in aliases:
                        if re.search(rf"\b{re.escape(a)}\s*\.\s*kick\s*\(", line):
                            bad.append(f"{rel}:{lineno}: {line.strip()[:90]}")
    assert not bad, (
        "毎周 撃たれる口から旧道具の背景 kick が生えています（`docs/METHOD.md` §8"
        "「起こす口を全部 外すこと」）:\n  " + "\n  ".join(sorted(set(bad))))


def test_kick_の関数そのものは消していないこと() -> None:
    """**§8「消さない」。** 塞いだのは呼ぶ所だけで、道具を壊してはいないこと。"""
    missing = [m for m in KICKERS
               if not re.search(r"^def kick\(", (ROOT / "scripts" / f"{m}.py")
                                .read_text(encoding="utf-8"), re.M)]
    assert not missing, (
        f"{missing} の `kick()` そのものが消えています。§8 は「使わないが消さない」です")


def test_見張っている_file_が実在すること() -> None:
    """名指しなので、改名すると黙って見張りが外れます。ここで落とす。"""
    gone = [str(r) for r in WATCHED if not (ROOT / r).exists()]
    assert len(gone) < len(WATCHED), f"見張り先が全部 消えています: {gone}"
