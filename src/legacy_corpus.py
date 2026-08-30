"""**すでに列に入っている本を、停止の理由そのもので測り直す**（API 0単位・実測 1.5秒）。

    python -m src.legacy_corpus            # 要約（下の5つ）
    python -m src.legacy_corpus --verbose  # 当たった本文の実物も出す

## なぜ要るか（2026-08-30・解除条件5の回に足した）

`AUTOMATION_PAUSED.md` が止めたのは「**新しく作って足すこと**」で、
**すでに YouTube 側へ入っている列ではありません**（`resume_gate.queue()`）。
実測でその列は **479本・1日12本・10/09 まで**あり、
**機械が1回も起きなくても公開されます。**

そこまでは前の回が数えました。**数えただけでは、扱いを決められません。**
「全部 旧 persona で作られている」と書いてありましたが、
**それは作った時の設定の話で、出来上がった本文を誰も見ていませんでした。**

解除条件5（**既存動画の扱いと新旧テーマ混在リスクを決める**）は、
その本文を測らないと決められません。**引っ込めるかどうかの判断が、
実際に何が入っているかで正反対に振れる**からです。

## 測る軸は、停止の理由から採っています（勝手な軸を作らない）

`AUTOMATION_PAUSED.md` が挙げた理由は3行で、それぞれに軸が要ります。

    AI personas presenting themselves as human experts     → `persona_defects()`
    AI personas providing financial guidance               → `advice_defects()`
    mass-produced / generic / repetitive / template-based  → `frame()` と `variety()`

**`persona_defects()` は入口の設定ではなく、出来上がった台本に
`verify._check_no_human_expert_claim()` を当てます。** 同じ関数を
これから作る本にも当てているので、**新旧が同じ物差しで並びます。**

## 実測（2026-08-30・この module を書いた回。**写しです。撃ち直すこと**）

    台帳 735本 中 694本 に台本の控えがある（`data/critique_queue/*.json`・94%）
    人間の専門家を装う         **0 / 685本**（公開済み 208・予約 477）
    助言の形（べき論・推奨）    **5 / 685本**（0.7%。うち1件は法令用語の偽陽性）
    題の族                     526 / 694本
    出だしの1行のちがう形       689 / 694本（数字を N に潰しても、まだ 99.3%）
    **台本の行数**             **5行か6行が 75%**（6行ちょうどが 58%）
    **締めの1行に「あなた」**   **413 / 694本（60%）**

**「全部が停止の理由になった作り」ではありませんでした。**
名乗りの側（解除条件1・2）は**本文に1件も出ていません** ——
`persona` は台本を書かせる指示文に入っていましたが、
書き手はそこから経歴を書き起こしていませんでした。

**残っている欠陥は、名乗りではなく型のほうです**（3つ目の軸）。
中身は毎回ちがう数字を出していて（族 526・出だし 689通り）、
**枠だけが同じ**です —— 6行・同じ合成音声・同じ絵の作り・
そして **10本に6本が「あなたの◯◯はいくらですか」で終わります。**
ポリシーの原文が名指ししているのは、まさにこの形です:

> 同じチャンネルの動画を続けて数本視聴した後、繰り返しのように感じられる可能性のあるコンテンツ

## この module が**言わないこと**

**「だから安全です」とは言いません。** 当てているのは
`verify` に実装済みの語のパターンだけで、**網羅ではありません**
（`verify._PROFESSION_WORDS` の「覆る条件」2番と同じ限界を、そのまま引き継ぎます）。
そして測れるのは**台本の控えがある本だけ**です ——
控えは `data/critique_queue/` にあり、**41本には ありません**（説明欄と画面の文字も
控えていないので、この module はどちらも見ていません）。**見ていないものを
「無かった」と印字しないこと。** 出力は必ず分母を並べて出します。

## 覆る条件（4つ）

1. **`verify` の語のパターンが増えたら、ここの数字は増えます。**
   この module はパターンを持ちません（持つと新旧で物差しが割れる）。
   増やす先は `verify._HUMAN_EXPERT_PATTERNS` のほう
2. **控えの無い本（41本）で名乗りが出たら、`persona_defects()` の 0 は嘘になります。**
   控えは投稿時にしか書かれないので、**過去に遡って埋めることはできません**
3. 停止が明けて新しい型で作り始めたら、`frame()` の「6行 58%」は
   新旧が混ざった数になります。**そのときは `bucket` で切って読むこと**
4. `data/critique_queue/` を掃除したら、この module は黙ります
   （**掃除しないこと。控えは、いま唯一 本文が残っている場所です**）
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import statistics
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "data" / "uploaded.jsonl"
STASH = ROOT / "data" / "critique_queue"

_JST = timezone(timedelta(hours=9))

#: 助言の形。**「あなた」を単独では当てません** —— 実測で 633件 当たったうちの
#: ほとんどが締めの**問いかけ**（「あなたの勤続は5年を越えていますか」）で、
#: これは視聴者への呼びかけであって助言ではありません。
#: **当てるのは、こちらが行動を指図している形だけ**です。
_ADVICE_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"あなた(?:の場合|なら)[^。！？\n]{0,20}(?:べき|ましょう|してください)",
     "視聴者個人に行動を指図している"),
    (r"(?:した|やった|選んだ)ほうが(?:いい|良い)(?:です|でしょう)",
     "推奨している"),
    # **「必ずご自身で確認してください」を当てないこと。** あれは注意書きで、
    # 指図の逆です（実測 2026-08-30: この形だけで 1件 誤爆した）。
    # 当てるのは「必ず得します」のように、**結果を断定して勧めている**形だけ。
    (r"(?:絶対|必ず)[^。！？\n]{0,8}(?:得し|儲か|増えま|安くな)",
     "断定して勧めている"),
    (r"おすすめ(?:です|します|なのは)",
     "おすすめと書いている"),
)


def _rows(path: Path | None = None) -> dict[str, dict]:
    """台帳を `video_id` で畳む。**後の行が勝つ**（`retimed_at` で予定が動くため）。"""
    p = LEDGER if path is None else path
    out: dict[str, dict] = {}
    if not p.is_file():
        return out
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            continue
        vid = r.get("video_id")
        if not vid:
            continue
        prev = out.get(vid, {})
        prev.update({k: v for k, v in r.items() if v is not None})
        out[vid] = prev
    return out


def _bucket(row: dict, now: datetime) -> str:
    """`public`（もう出た） / `scheduled`（これから出る） / `undated`（`at` が無い）。"""
    at = row.get("at")
    if not at:
        return "undated"
    try:
        t = datetime.fromisoformat(str(at).replace("Z", "+00:00"))
    except ValueError:
        return "undated"
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return "scheduled" if t > now else "public"


def corpus(ledger: Path | None = None, stash: Path | None = None,
           now: datetime | None = None) -> list[dict]:
    """台帳と台本の控えを突き合わせた一覧。**控えの無い本は入りません**（分母に出します）。"""
    ref = now or datetime.now(timezone.utc)
    st = STASH if stash is None else stash
    out = []
    for vid, r in _rows(ledger).items():
        p = st / f"{vid}.json"
        if not p.is_file():
            continue
        try:
            s = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        out.append({
            "video_id": vid,
            "bucket": _bucket(r, ref),
            "title": str(r.get("title") or ""),
            "topic": str(r.get("topic") or ""),
            "at": r.get("at"),
            "narration": list(s.get("narration") or []),
            "change_ratios": list(s.get("change_ratios") or []),
            "orientation": s.get("orientation"),
        })
    return out


def coverage(ledger: Path | None = None, stash: Path | None = None) -> dict:
    """**分母**。台帳に何本あって、そのうち何本の本文が読めるか。"""
    rows = _rows(ledger)
    st = STASH if stash is None else stash
    have = sum(1 for vid in rows if (st / f"{vid}.json").is_file())
    return {"ledger": len(rows), "with_script": have, "without_script": len(rows) - have}


def _as_script(rec: dict) -> dict:
    """`verify` が読む形へ。**説明欄と画面の文字は控えに無いので入りません。**"""
    return {
        "title": rec["title"],
        "segments": [{"narration": n} for n in rec["narration"]],
    }


def persona_defects(recs: list[dict]) -> list[dict]:
    """**人間の専門家を装っている本**（解除条件1・2の物差し）。

    パターンは持たず、`verify._check_no_human_expert_claim()` を呼びます ——
    **これから作る本と同じ関数**なので、新旧が同じ物差しで並びます。
    """
    from src import verify  # 遅延 import（`verify` は重い）

    out = []
    for r in recs:
        probs = verify._check_no_human_expert_claim(_as_script(r))
        if probs:
            out.append({**r, "problems": probs})
    return out


def advice_defects(recs: list[dict]) -> list[dict]:
    """**行動を指図している本**（`channel.yaml` の `avoid` に 08/30 に足した形）。"""
    out = []
    for r in recs:
        text = r["title"] + "\n" + "\n".join(r["narration"])
        hits = []
        for pat, why in _ADVICE_PATTERNS:
            m = re.search(pat, text)
            if m:
                hits.append((why, m.group(0)))
        if hits:
            out.append({**r, "hits": hits})
    return out


def frame(recs: list[dict]) -> dict:
    """**枠がどれだけ同じか**（`mass-produced / repetitive` の側）。

    中身ではなく**形**を数えます —— 行数の集中と、締めの1行の定型。
    """
    if not recs:
        return {"n": 0}
    lines = collections.Counter(len(r["narration"]) for r in recs)
    top_n, top_c = lines.most_common(1)[0]
    five_six = sum(c for k, c in lines.items() if k in (5, 6))
    closing_anata = sum(1 for r in recs if r["narration"] and "あなた" in r["narration"][-1])
    closing_q = sum(1 for r in recs
                    if r["narration"] and re.search(r"(ですか|ますか)[。]?$",
                                                    r["narration"][-1].strip()))
    return {
        "n": len(recs),
        "lines": dict(sorted(lines.items())),
        "modal_lines": top_n,
        "modal_share": top_c / len(recs),
        "five_or_six_share": five_six / len(recs),
        "closing_anata": closing_anata,
        "closing_anata_share": closing_anata / len(recs),
        "closing_question": closing_q,
    }


def _shape(text: str) -> str:
    """数字を `N` に潰した形。**中身ではなく型が同じかを見るため。**"""
    t = re.sub(r"\s*#Shorts\s*$", "", text)
    return re.sub(r"[0-9０-９][0-9０-９,，.．]*", "N", t)


def variety(recs: list[dict]) -> dict:
    """**中身がどれだけちがうか**（型を潰しても残る差）。"""
    if not recs:
        return {"n": 0}
    fams = collections.Counter()
    for r in recs:
        base = re.sub(r"^s-", "", r["topic"])
        fams[re.split(r"-\d", base)[0]] += 1
    opens = collections.Counter(_shape(r["narration"][0]) for r in recs if r["narration"])
    titles = collections.Counter(_shape(r["title"]) for r in recs)
    per = [statistics.median(r["change_ratios"]) for r in recs if r["change_ratios"]]
    return {
        "n": len(recs),
        "topic_families": len(fams),
        "opening_shapes": len(opens),
        "title_shapes": len(titles),
        "visual_change_median": statistics.median(per) if per else None,
        "visual_change_sd": statistics.pstdev(per) if len(per) > 1 else None,
    }


def drain(recs: list[dict]) -> dict:
    """**予約が尽きる日**。混在の窓は、ここまで開いています。"""
    fut = []
    for r in recs:
        if r["bucket"] != "scheduled" or not r["at"]:
            continue
        try:
            t = datetime.fromisoformat(str(r["at"]).replace("Z", "+00:00"))
        except ValueError:
            continue
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        fut.append(t)
    if not fut:
        return {"upcoming": 0, "first": None, "last": None, "per_day": None}
    fut.sort()
    span = max((fut[-1] - fut[0]).days, 1)
    return {
        "upcoming": len(fut),
        "first": fut[0].astimezone(_JST),
        "last": fut[-1].astimezone(_JST),
        "per_day": len(fut) / span,
    }


def report(verbose: bool = False) -> str:
    recs = corpus()
    cov = coverage()
    lines: list[str] = []
    a = lines.append
    a("=== すでに列に入っている本を、停止の理由で測り直す ===")
    a(f"  台帳 {cov['ledger']}本 ／ 本文が読める {cov['with_script']}本"
      f"（**読めない {cov['without_script']}本 は、この下の全部の分母から外れています**）")
    if not recs:
        a("  **本文が1本も読めません。** `data/critique_queue/` を確かめること。")
        return "\n".join(lines)

    by = collections.Counter(r["bucket"] for r in recs)
    a(f"  内訳: 公開済み {by['public']}本 ／ 予約 {by['scheduled']}本 ／ 日付なし {by['undated']}本")

    d = drain(recs)
    if d["upcoming"]:
        a(f"  予約は {d['first']:%m/%d %H:%M} 〜 {d['last']:%m/%d %H:%M} JST・"
          f"**{d['per_day']:.1f}本/日** —— **混在の窓はここまで開いています**")

    a("")
    a("--- 1) 人間の専門家を装っているか（解除条件 1・2）---")
    pd = persona_defects(recs)
    a(f"  **{len(pd)} / {len(recs)}本**"
      + ("  ← `verify._check_no_human_expert_claim()`。**同じ関数を新しい本にも当てています**"
         if not pd else ""))
    for r in pd[:10] if verbose else pd[:3]:
        a(f"    - [{r['bucket']}] {r['video_id']} {r['title'][:40]}")
        a(f"      {r['problems'][0][:150]}")

    a("")
    a("--- 2) 行動を指図しているか（`channel.yaml` の `avoid`）---")
    ad = advice_defects(recs)
    a(f"  **{len(ad)} / {len(recs)}本**（{100.0 * len(ad) / len(recs):.1f}%）")
    for r in (ad if verbose else ad[:5]):
        a(f"    - [{r['bucket']}] {r['hits'][0][1][:40]} … {r['title'][:34]}")

    a("")
    a("--- 3) 枠が同じか（mass-produced / repetitive）---")
    f = frame(recs)
    a(f"  台本の行数: **{f['modal_lines']}行 が {f['modal_share'] * 100:.0f}%**"
      f" ／ 5行か6行で **{f['five_or_six_share'] * 100:.0f}%**")
    a(f"  締めの1行に「あなた」: **{f['closing_anata']} / {f['n']}本"
      f"（{f['closing_anata_share'] * 100:.0f}%）** ← **ここが型です**")
    a(f"  締めが疑問形: {f['closing_question']} / {f['n']}本")

    a("")
    a("--- 4) 中身がちがうか（数字を N に潰しても残る差）---")
    v = variety(recs)
    a(f"  題の族 {v['topic_families']} / {v['n']}本"
      f" ／ 出だしの1行の形 **{v['opening_shapes']} / {v['n']}本**"
      f" ／ 題の形 {v['title_shapes']} / {v['n']}本")
    if v["visual_change_median"] is not None:
        a(f"  画の変化率: 本ごとの中央値 {v['visual_change_median']:.3f}"
          f"（ばらつき {v['visual_change_sd']:.4f}）")

    a("")
    a("--- 読み方 ---")
    a("  **中身はちがい、枠が同じ**、という形です。")
    a("  名乗りの側（1）が 0 なら、**引っ込める理由はそこにはありません** ——")
    a("  残る欠陥は（3）で、これは**これから作る本の型を変えれば直り、")
    a("  すでに出た本を消しても直りません**（消しても型は変わらないため）。")
    a("  **見ていないもの: 説明欄・画面の文字・控えの無い"
      f"{cov['without_script']}本。**「無かった」ではありません。")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__ or "")
    ap.add_argument("--verbose", action="store_true", help="当たった本文の実物も出す")
    ap.add_argument("--json", action="store_true", help="機械が読む形で出す")
    args = ap.parse_args()
    if args.json:
        recs = corpus()
        print(json.dumps({
            "coverage": coverage(),
            "persona_defects": len(persona_defects(recs)),
            "advice_defects": len(advice_defects(recs)),
            "frame": frame(recs),
            "variety": variety(recs),
        }, ensure_ascii=False, indent=2))
        return
    print(report(verbose=args.verbose))


if __name__ == "__main__":
    main()
