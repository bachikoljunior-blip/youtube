"""`scripts/trajectory.py` は、周の判断に使われていないと自分で言うこと。

## なぜ要るか（2026-08-31 23:xx に測って足した）

2026-08-31 の申し送りが、こう名指ししました ——

> `scripts/trajectory.py` が `house_rule` を1行も読んでいません
> （`UPLOAD_CAP_PER_DAY = 92` ＝ 規則の92倍の供給の上に「床 2027-01-17」が立っている）

**事実です。** ただし、**この道具の出す日付は、どの回の判断にも入っていません** ——
`grep -rn "trajectory" docs/ CLAUDE.md scripts/ src/` で数えると、
`scripts/trajectory.py` を呼ぶものは**1つもありません**（手順にも、親の手順にも、
`spawn_prompt` にも、`CLAUDE.md` にも、フックにも、他のコードにも名前が無い）。
`src/levers.py` と `src/arm_speed.py` が言う `trajectory()` は
**`scripts/eta.py` の中の同名の関数**で、この file ではありません。

**危ないのは「死んでいること」ではなく、「生きているように見えること」です。**
手で撃つと、規則の92倍の供給を前提にした床の日付が、`eta.py` と
そっくりな字で出ます。**だから、そう言わせます。**

**消しません** —— 恒等式（供給 × 1本あたり生涯再生）の導出と実測は
ここにしか無いからです（`docs/trigger_main.md`「節は1つも消しません」）。

**覆る条件**: 周のどこかがこの道具を呼ぶようになったら、この検査は
**逆向きに**なります（そのときは註ではなく**供給の側**を直すこと）。
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SRC = ROOT / "scripts" / "trajectory.py"


def test_規則を読んでいる():
    """**突き合わせるために読むこと**（供給に使うかは別の話）。"""
    src = SRC.read_text(encoding="utf-8")
    assert "house_rule" in src, (
        "`house_rule` を1行も読んでいません。**規則との差を言えません**"
    )
    assert "_HOUSE_RULE_PER_DAY" in src


def test_周が呼んでいないことは本当か():
    """**この検査が、註の根拠そのものです。**

    呼ぶ側が現れたら、ここが赤くなって註のほうを直させます。
    """
    hits = []
    for path in list(ROOT.glob("*.md")) + list((ROOT / "docs").glob("*.md")) \
            + list((ROOT / "scripts").glob("*.py")) + list((ROOT / "src").glob("*.py")):
        if path.name in ("trajectory.py", "JOURNAL.md"):
            continue          # 自分自身と、過去の記録は数えない
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        # **「撃つ書き方」だけを数える。** ただの言及は数えない ——
        # `src/settle.py` は註の中で「同じ日に `scripts/trajectory.py` でも
        # 同じ形を1つ直しました」と**歴史を書いている**だけで、呼んでいません。
        # **文中に名前が出ること と 呼ぶこと は別**です（ここで1回 踏んだ）。
        for line in text.splitlines():
            body = line.split("#", 1)[0]          # 註は落とす
            if "scripts/trajectory.py" not in body:
                continue
            if re.search(r"(python|subprocess|run|call|import)\b", body) or \
                    body.strip().startswith(("python", "$", "    python")):
                hits.append(f"{path.relative_to(ROOT)}: {line.strip()[:80]}")
    assert not hits, (
        f"`scripts/trajectory.py` を呼ぶ所ができています: {hits}。"
        "**註が古くなりました** —— 供給（UPLOAD_CAP_PER_DAY）を "
        "`house_rule` と突き合わせて直すこと"
    )


def test_出力の頭で_周の予測ではないと言う():
    """**手で撃った人が、そのまま読まないこと。**"""
    proc = subprocess.run([sys.executable, str(SRC)], capture_output=True,
                          text=True, timeout=900, cwd=str(ROOT))
    assert proc.returncode == 0, proc.stderr[-500:]
    head = "\n".join(proc.stdout.splitlines()[:8])
    assert "周が読んでいる予測ではありません" in head, (
        "出力の頭で「これは周の予測ではない」と言っていません"
    )
    assert "scripts/eta.py" in head, "本物（eta.py）を名指ししていません"
    assert "92倍" in head, (
        "規則との倍率を出していません。**床の日付が、規則の92倍の供給の上に"
        "立っていることが読み取れません**"
    )
