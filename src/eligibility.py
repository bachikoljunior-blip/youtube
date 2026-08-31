"""**収益化の審査は「待つだけの段」ではありません。** そこが落ちると、全部の腕が0倍になります。

## なぜ要るか（2026-08-31・最適化の回）

`scripts/eta.py` の段3 は、この1行で立っていました:

    {"no": 3, "lever": "none", "when": d_gate1 + MONETIZE_REVIEW_DAYS,
     "bar": "門1・門2a の両方を満たしたら申請。**待つだけの段**"}

**`grep -c 'policy' scripts/eta.py` は 0 でした。** つまり到達日は
**「門1と門2aの数字さえ揃えば審査は必ず通る」（P(承認)=1.0）** を置いて解かれていました。
YPP の審査は本数と時間の検算ではなく、**中身がポリシーに合うかの合否判定**です。
ここに合否が無いので、`eta.py` の印字する日付は**上振れ側にしか外れません。**

**この差は、どの腕よりも大きい。** 同じ回の実測（`eta.py --offline`）で:

    per_video を ∞ にする  → 段4の床②（収益化後の30日）は動かない → **0日 早まる**
    rpm を ∞ にする        → 同上（収益化前の再生は1円も生まない）  → **0日 早まる**
    density を ∞ にする    → `day_cap` = 10本/日 で頭打ち            → **0日 早まる**
    審査に落ちる           → 到達日は「遅れる」ではなく **来ない**

**腕が4本とも0日なのに、ここだけが日付を持っています。** だから律速はここです。

## 何日ぶんか（**勘で置かない**。掛け算してから置く）

落ちたときに戻ってくるまでの日数は、公表値だけで組めます。

    30日  審査そのもの（YouTube 公表「通常1か月以内」＝ `MONETIZE_REVIEW_DAYS`）
    30日  **却下されると、再申請できるのは30日後**（YPP の公表規則）
    30日  2回目の審査
    ────
    60日  ＝ 落ちて初めて増える分（1回目の30日は落ちても通っても払う）

`REAPPLY_COST_DAYS = 60`。期待値は `p_deny × 60` 日。

**`p_deny` は実測ではありません。** ここだけは掛け算で出せない（審査は1回しか撃てず、
撃つのは門1が通った後）。なので **推測だと印字し、`config/hypotheses.yaml` に期限付きで置きます。**
検出できない条件を反証条件にしないこと（`docs/GOAL.md`）——
ここは**申請の結果そのもの**が判定材料なので、期限は申請日に紐づきます。

## 何を見ているか

`config/channel.yaml` だけを読みます。**「この構成で申請したら落ちる材料」**を
数え上げる係で、生成も投稿も止めません（**止める仕掛けではなく、日付に値を入れる係**です）。
構成を直すと `p_deny` が下がり、**到達日がそのぶん早まります。**

## 08-30 に閉じた分との関係（**やり直さないこと**）

**名乗りのほうは 2026-08-30 に閉じています** —— `config/channel.yaml` の `persona` から
経歴を落とし、`src/verify._check_no_human_expert_claim()` が**出来上がった台本の側**でも
塞いでいます（`tests/test_no_human_expert_claim.py`・20件）。**そこは触っていません。**

ここが足すのは2つだけです。

1. **`scripts/eta.py` の式に、合否そのものを入れる。** `CLAUDE.md` は 08-30 の時点で
   「この審査に受かる確率を 1.0 に置いたまま出ています」と**書いてありました**が、
   **書いてあるだけで、式は直っていませんでした**（`grep -c 'policy' scripts/eta.py` が 0）。
   **この repo で一番よくある壊れ方（言っている所と、している所が別）が、ここにも在りました。**
2. **開示。** 「名乗らない」と「何であるかを言う」は別のことです。前者は閉じていましたが、
   **説明欄のどこにも合成音声だと書いていませんでした**（2026-08-31 に足した）。

`_CREDENTIAL_PAT` は `verify` の重複ではなく、**入口の逆戻り検知**です ——
`persona` に経歴が戻ったら、台本1本が落ちる前に**到達日のほうが動きます。**
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHANNEL_YAML = ROOT / "config" / "channel.yaml"

#: 却下されてから2回目の審査が終わるまで（公表値のみ。30日の再申請待ち + 30日の審査）
REAPPLY_COST_DAYS = 60

#: 「実務家/専門家として名乗る」形。**人間の経歴を主張する語**だけを見る。
_CREDENTIAL_PAT = re.compile(
    r"元[・\s]*(事業会社|会社|企業)|"
    r"(経理|人事|税理士|会計士|社労士|FP|ファイナンシャル)[^\n]{0,8}(出身|経験|として|でした|です)|"
    r"実務で回してきた立場|"
    r"現役の?(税理士|会計士|社労士)"
)

#: 合成音声・AI生成であることの開示。**どれか1つでも入っていれば立つ。**
_DISCLOSURE_PAT = re.compile(r"AI|合成音声|音声合成|自動生成|機械が|生成AI")

#: 落ちやすい題材（金融・税・法務・健康）。**それ自体は違反ではない**が、
#: 「人間の専門家を装う」と組み合わさったときだけ、審査の落ち方が変わる。
_SENSITIVE_PAT = re.compile(r"税金|税|お金|金融|投資|年金|保険|法律|医療|健康|給与|社会保険")


def _read() -> dict:
    import yaml
    with CHANNEL_YAML.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def findings(cfg: dict | None = None) -> list[dict]:
    """**この構成で申請したときに、審査が拾う材料**を列挙する。

    返すのは事実の列だけ。**判断も停止もしない。**
    """
    cfg = cfg if cfg is not None else _read()
    ch = cfg.get("channel", {}) or {}
    pub = cfg.get("publish", {}) or {}

    persona = str(ch.get("persona", "") or "")
    niche = str(ch.get("niche", "") or "")
    name = str(ch.get("name", "") or "")
    footer = str(pub.get("footer", "") or "")

    sensitive = bool(_SENSITIVE_PAT.search(niche + name))
    out: list[dict] = []

    if _CREDENTIAL_PAT.search(persona):
        out.append({
            "id": "human_credential_claim",
            "weight": 0.45 if sensitive else 0.20,
            "what": "台本の書き手が、**人間の職歴／資格を持つ実務家として名乗っている**",
            "where": "config/channel.yaml: channel.persona",
            "why": ("YPP は『人間の専門家を装った合成人格が、金銭・税・法・健康を解説する』形を "
                    "収益化不可の例に挙げている。**視聴者に対しても、居ない経歴を名乗っていることになる。**"),
            "fix": "経歴の主張を外し、**何に基づいて話しているか（自前の計算）**で信用を立てる",
        })

    if not _DISCLOSURE_PAT.search(footer):
        out.append({
            "id": "no_synthetic_disclosure",
            "weight": 0.25 if sensitive else 0.10,
            "what": "**合成音声・自動生成であることが、説明欄のどこにも書かれていない**",
            "where": "config/channel.yaml: publish.footer",
            "why": "合成メディアの開示は YouTube の要求事項。無開示は審査で不利にしか働かない",
            "fix": "footer に1行入れる。**尺も維持率も1秒も削らない**（説明欄は再生に入らない）",
        })

    return out


def p_deny(cfg: dict | None = None) -> float:
    """**推測です。** 未解決の材料を足し合わせ、0〜0.9 で止める。"""
    total = sum(f["weight"] for f in findings(cfg))
    return min(0.9, round(total, 3))


def cost_days(cfg: dict | None = None) -> float:
    """審査の段に足す**期待日数** ＝ `p_deny × REAPPLY_COST_DAYS`。"""
    return round(p_deny(cfg) * REAPPLY_COST_DAYS, 1)


def state(cfg: dict | None = None) -> dict:
    """`eta.py` の段3 が読む形。**`measured` は常に False**（審査は1回しか撃てない）。"""
    cfg = cfg if cfg is not None else _read()
    fs = findings(cfg)
    return {
        "findings": fs,
        "p_deny": p_deny(cfg),
        "cost_days": cost_days(cfg),
        "reapply_cost_days": REAPPLY_COST_DAYS,
        "clean": not fs,
        "measured": False,
    }
