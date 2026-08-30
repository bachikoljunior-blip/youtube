"""**説明欄**を測る —— 停止の理由（解除条件1・2・3・5）が、最後に残っていた面。

    python -m src.descriptions            # 測る（キャッシュがあれば **API 0単位**）
    python -m src.descriptions --refresh  # Data API から取り直す（**約15単位**）

## なぜ要るか（2026-08-30 夜に足した）

`src/legacy_corpus.py` は控え694本を測って、解除条件1・2・5 を閉じました。
その出力の末尾には、**自分が見ていないものが3つ**書いてあります:

    **見ていないもの: 説明欄（正本は Data API）・控えの無い41本・画面の読めない 39本。**
    「無かった」ではありません。

**このうち「説明欄」は、いちばん大きい穴でした。**

  * `data/critique_queue/<id>.json` に `description_body` が入っていないので、
    **控えからは1文字も読めません**（`legacy_corpus._as_script()` の註）。
  * ところが `src/verify._check_no_human_expert_claim()` は、
    **`description_body` を第2の欄として当てています**（`fields` の2行目）——
    つまり**これから作る本では見ている面を、既にある685本では一度も見ていない。**
  * そして審査する側から見ると、説明欄は**動画を再生しなくても読める**面です。
    名乗り（「元・事業会社の経理」）が本文から消えていても、
    説明欄に残っていれば、解除条件1・2 は閉じていません。

**だから、ここを測るまで「0件」は言えません。**

## どこから読むか（**`search.list` を使わないこと**）

動画IDは **`data/uploaded.jsonl`（自分が上げたときに書いた行）**から取ります。
`src/history.channel_video_ids()` は `playlistItems` と `search` の和ですが、
**`search.list` は1回100単位**で、700本ぶんだと 1,400単位 かかります。
台帳は **API 0単位**で、しかも**外の口の都合では欠けません**
（`history._scan` の末尾が、同じ理由で台帳を使っています）。

    台帳から video_id     0単位
    videos.list × 15束    **15単位**（1束50本・`part=snippet,status`）

**覆る条件**: 台帳に無い本（手で上げた本・別の口で上げた本）は、この測定から
丸ごと落ちます。落ちた本があるかは `videos.list` の返り本数と台帳の差で出しており、
**差が出たら `history.channel_video_ids()` の側へ切り替えること**（そのときは単位を払う）。

## 何を測るか —— **`legacy_corpus` と同じ3つを、説明欄に当てる**

    1) 人間の専門家を装っているか   `verify._check_no_human_expert_claim()`（同じ関数）
    2) 行動を指図しているか         `legacy_corpus._ADVICE_PATTERNS`（同じ表）
    3) 枠が同じか                   本文の3か所の実効の型数（`frames.effective()`）

**同じ関数・同じ表を使うのは、新旧を同じ物差しに載せるためです。**
ここで別のパターンを書くと、「説明欄だけ厳しい／緩い」が測定の側から生まれます。

**定型文は分母から外します** —— `channel.yaml` の `publish.footer` と
`▼ 目次` 以降は、`src/pipeline.build_description()` が**全本に同じものを足す**ので、
そこを数えると 694本 が 1つの型に見えます。測るのは **`description_body`**、
すなわち `▼ 目次` の手前だけです。
"""
from __future__ import annotations

import argparse
import collections
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from src import frames

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "data" / "uploaded.jsonl"
CACHE = ROOT / "data" / "descriptions.json"

#: `build_description()` が本文の後ろに足す見出し。ここから先は全本 同じ形。
TOC_MARK = "▼ 目次"
#: 本文の頭を何文字で見るか（`frames.OPEN_HEAD` と同じ理由・同じ数）。
HEAD = frames.OPEN_HEAD
#: `channel.yaml` の footer が始まる罫線。ここから先は全本 同じ形。
RULE_RE = re.compile(r"^[─―—\-=_]{5,}$")


def ledger_ids(path: Path | None = None) -> list[str]:
    """台帳の `video_id` を、出てきた順で重複なく。API 0単位。"""
    p = LEDGER if path is None else path
    out: list[str] = []
    seen: set[str] = set()
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
        if vid and vid not in seen:
            seen.add(vid)
            out.append(vid)
    return out


def fetch(ids: list[str] | None = None, cache: Path | None = None,
          force: bool = False) -> dict:
    """`videos.list` で説明欄を取り、キャッシュへ落とす。**約15単位**。

    落ちても止めません —— **取れたところまでを書きます**（`partial` に印が付く）。
    """
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    from src import auth

    vids = ids if ids is not None else ledger_ids()
    youtube = build("youtube", "v3", credentials=auth.credentials(),
                    cache_discovery=False)
    got: list[dict] = []
    partial = False
    for i in range(0, len(vids), 50):
        chunk = vids[i:i + 50]
        try:
            res = youtube.videos().list(
                part="snippet,status", id=",".join(chunk)).execute()
        except HttpError as exc:
            auth.note_day_quota(exc, "videos.list snippet (descriptions)")
            print(f"[descriptions] {i}本まで読んで止まりました（続行）: {str(exc)[:90]}")
            partial = True
            break
        for v in res.get("items", []):
            sn = v.get("snippet") or {}
            st = v.get("status") or {}
            got.append({
                "video_id": v.get("id"),
                "title": sn.get("title") or "",
                "description": sn.get("description") or "",
                "published_at": sn.get("publishedAt"),
                "privacy": st.get("privacyStatus"),
                "publish_at": st.get("publishAt"),
            })
    out = {
        "at": datetime.now(timezone.utc).isoformat(),
        "asked": len(vids),
        "got": len(got),
        "partial": partial,
        "videos": got,
    }
    p = CACHE if cache is None else cache
    # **前より少ない回は、書かないこと**（2026-08-30 に踏んだ）。
    #
    # 最初に撃った回が日枠の 403 で **0本** を持ち帰り、それをそのまま書きました。
    # 一度でも成功していたら、**測れていた 735本 が 0本 に化けていた**ところです。
    # `partial` の印は残りますが、**中身はもう戻りません**（正本は API 側なので、
    # 取り直せるのは日枠が戻る JST 16:00 以降）。
    #
    # **覆る条件**: チャンネルから本当に本が減った回は、ここが邪魔をします。
    # そのときは `--refresh --force` で上書きすること（減ったことを確かめてから）。
    prev = load(p)
    if should_write(out, prev, force=force):
        p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    else:
        out["kept"] = len(prev.get("videos") or [])
        print(f"[descriptions] **書きませんでした** —— 取れたのは {len(got)}本 で、"
              f"手元には {out['kept']}本 在ります（少ないほうで上書きしない）")
    return out


def should_write(out: dict, prev: dict, force: bool = False) -> bool:
    """**取れたほうが少ない回は書かない。** 上の註の判断を、1か所に出したもの。"""
    if force:
        return True
    if not (prev.get("videos") or []):
        return True
    return len(out.get("videos") or []) >= len(prev.get("videos") or [])


def load(cache: Path | None = None) -> dict:
    p = CACHE if cache is None else cache
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def body(description: str) -> str:
    """**定型を落とした本文**（`build_description()` が足す前の `description_body`）。

    `▼ 目次` から先は目次・footer・`[t:テーマID]` の印で、**全本に同じ形が入ります。**
    見出しが無い本（古い形）は、`[t:` の印より手前までを本文と見ます。

    **footer だけの本も落とします**（2026-08-30 に検査で踏んだ）——
    目次も印も無く footer だけが入った説明欄は、上の2つでは切れず、
    **定型文がまるごと「本文」として数えられます。** `channel.yaml` の footer は
    罫線（`─` の並び）で始まるので、その行から先も落とします。
    """
    text = str(description or "")
    for mark in (TOC_MARK, "\n[t:"):
        i = text.find(mark)
        if i >= 0:
            text = text[:i]
    lines: list[str] = []
    for ln in text.splitlines():
        if RULE_RE.match(ln.strip()):
            break
        lines.append(ln)
    return "\n".join(lines).strip()


def as_script(rec: dict) -> dict:
    """`verify` が読む形へ。**説明欄だけ**を入れます（本文と画面は別の道具の担当）。"""
    return {"title": rec.get("title") or "",
            "description_body": body(rec.get("description"))}


def persona_defects(recs: list[dict]) -> list[dict]:
    """**説明欄で人間の専門家を装っている本**（解除条件1・2）。"""
    from src import verify  # 遅延 import（`verify` は重い）

    out = []
    for r in recs:
        probs = verify._check_no_human_expert_claim(as_script(r))
        if probs:
            out.append({**r, "problems": probs})
    return out


def advice_defects(recs: list[dict]) -> list[dict]:
    """**説明欄で行動を指図している本**（`channel.yaml` の `avoid`）。"""
    from src import legacy_corpus

    out = []
    for r in recs:
        text = body(r.get("description"))
        hits = []
        for pat, why in legacy_corpus._ADVICE_PATTERNS:
            m = re.search(pat, text)
            if m:
                hits.append((why, m.group(0)))
        if hits:
            out.append({**r, "hits": hits})
    return out


def frame(recs: list[dict]) -> dict:
    """**説明欄の枠がどれだけ同じか**（解除条件3の側）。

    見るのは `frames` と同じ3か所 —— 本文の**1行目の頭**・**最終行の頭**・
    **最終行の末尾**。本文が空の本は分母から落とします（**「型が同じ」に化けるため**。
    `frames.axes()` が空行を落とすのと同じ理由）。
    """
    sigs = []
    empty = 0
    for r in recs:
        lines = [x for x in body(r.get("description")).splitlines() if x.strip()]
        if not lines:
            empty += 1
            continue
        first, last = frames.norm(lines[0]), frames.norm(lines[-1])
        sigs.append({
            "opening": first[:HEAD],
            "closing": last[:frames.CLOSE_HEAD],
            "closing_tail": last[-frames.CLOSE_TAIL:],
            "lines": len(lines),
        })
    out: dict = {"n": len(sigs), "empty": empty}
    for ax in ("opening", "closing", "closing_tail"):
        vals = [s[ax] for s in sigs]
        c = collections.Counter(vals)
        top, cnt = c.most_common(1)[0] if c else ("", 0)
        out[ax] = {
            "distinct": len(c),
            "top": top,
            "top_share": (cnt / len(vals)) if vals else 0.0,
            "effective": frames.effective(vals),
        }
    lines = collections.Counter(s["lines"] for s in sigs)
    out["modal_lines"] = lines.most_common(1)[0] if lines else (0, 0)
    return out


def report(cache: Path | None = None, show: int = 5) -> str:
    d = load(cache)
    if not d:
        return ("=== 説明欄 ===\n  **まだ1度も取っていません。**"
                " `python -m src.descriptions --refresh`（約15単位）")
    recs = d.get("videos") or []
    a: list[str] = []
    ap = a.append
    ap("=== 説明欄を、停止の理由で測る（解除条件1・2・3・5 の最後の面）===")
    asked = d.get("asked", 0)
    miss = asked - len(recs)
    # **「返らなかった」を「無い」と言わないこと**（2026-08-30 夜に踏んだ）。
    # `fetch()` は日枠に当たると **その束で break** します。0本 で止まった回に
    # 「差 735本 はチャンネルに無い本」と書くと、**台帳が実際より小さいという
    # 嘘**になり、解除条件5（既存の扱い）の判断がその嘘の上に乗ります。
    # 実測 2026-08-30 22:31Z: `quotaExceeded` で 0/735。**1本も問い合わせて
    # いません。** 分けるのは `partial`（＝途中で落ちた）です。
    partial = bool(d.get("partial"))
    if partial:
        ap(f"  台帳 {asked}本 ／ 説明欄が返った {len(recs)}本"
           f"（**残り {miss}本 は、まだ問い合わせていません**）")
        ap("  [!] **途中で止まっています**（日枠 `quotaExceeded`。JST 16:00 に戻る）。"
           "取れたところまでの数です —— **返らなかった本を「チャンネルに無い」と"
           "読まないこと。** 取り直しは `python -m src.descriptions --refresh`")
    else:
        ap(f"  台帳 {asked}本 ／ 説明欄が返った {len(recs)}本"
           f"（差 {miss}本 は**チャンネルに無い本**）")
    priv = collections.Counter(r.get("privacy") for r in recs)
    ap("  内訳: " + " ／ ".join(f"{k} {v}本" for k, v in priv.most_common()))
    bodies = sum(1 for r in recs if body(r.get("description")))
    ap(f"  本文（`▼ 目次` の手前）が在る {bodies}本"
       f"（空 {len(recs) - bodies}本 は下の 3) の分母から外れます）")

    pd = persona_defects(recs)
    ap("")
    ap("--- 1) 説明欄で人間の専門家を装っているか（解除条件 1・2）---")
    if not recs:
        # **`0 / 0本` を「0件でした」と読ませないこと。** 分母が 0 の回に
        # 「**0 / 0本**」とだけ出すと、解除条件1・2 の根拠に見えます。
        # ここで言えるのは「**まだ測っていない**」だけです。
        ap("  **測っていません**（説明欄が1本も返っていない）。"
           "**「0件」ではありません** —— 解除条件1・2 の根拠にしないこと")
    else:
        ap(f"  **{len(pd)} / {len(recs)}本**  ← `verify._check_no_human_expert_claim()`"
           "（**本文に当てているのと同じ関数**）")
    for r in pd[:show]:
        ap(f"    - [{r.get('privacy')}] {r.get('title', '')[:34]}"
           f" … {r['problems'][0][:60]}")
    if len(pd) > show:
        ap(f"    …ほか {len(pd) - show}本")

    ad = advice_defects(recs)
    ap("")
    ap("--- 2) 説明欄で行動を指図しているか（`channel.yaml` の `avoid`）---")
    if not recs:
        ap("  **測っていません**（説明欄が1本も返っていない）")
    else:
        share = f"（{len(ad) / len(recs) * 100:.1f}%）"
        ap(f"  **{len(ad)} / {len(recs)}本**{share}")
    for r in ad[:show]:
        ap(f"    - [{r.get('privacy')}] {r['hits'][0][1][:24]}"
           f" … {r.get('title', '')[:32]}")
    if len(ad) > show:
        ap(f"    …ほか {len(ad) - show}本")

    f = frame(recs)
    ap("")
    ap("--- 3) 説明欄の枠が同じか（mass-produced / repetitive）---")
    if f["n"]:
        for ax, label in (("opening", "本文の1行目の頭"),
                          ("closing", "本文の最終行の頭"),
                          ("closing_tail", "本文の最終行の末尾")):
            v = f[ax]
            ap(f"  {label:<16} 実効 **{v['effective']:6.1f}本ぶん**（{f['n']}本中）"
               f"  いちばん多い型 {v['top']!r} が {v['top_share'] * 100:.0f}%"
               f" ／ 種類 {v['distinct']}")
        ap(f"  本文の行数: いちばん多いのは {f['modal_lines'][0]}行"
           f"（{f['modal_lines'][1] / f['n'] * 100:.0f}%）")
    ap("")
    ap("--- 読み方 ---")
    ap("  **実効の型数が本数に近ければ散っています。1に近いほど同じ型です**"
       "（`src/frames.py` と同じ尺度なので、そのまま並べられます）。")
    ap("  **定型文（`▼ 目次`・footer・`[t:` の印）は分母から外してあります** ——"
       "あれは `pipeline.build_description()` が全本に足すもので、"
       "数えると 100% が1つの型に見えます。")
    if miss and not partial:
        ap(f"  **{miss}本 はチャンネルに返りませんでした** ——"
           "消したか、台帳にしか無い本です。**この測定の穴です。**")
    elif miss:
        ap(f"  **{miss}本 は、まだ問い合わせていません**（日枠で途中で止まった）。"
           "**消えたのではありません** —— この節の数は、"
           f"取れた {len(recs)}本 についてだけのものです。")
    ap(f"  取った時刻: {d.get('at')}（`--refresh` で取り直し・約15単位）")
    return "\n".join(a)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__ or "")
    p.add_argument("--refresh", action="store_true",
                   help="Data API から取り直す（約15単位）")
    p.add_argument("--force", action="store_true",
                   help="取れた本数が手元より少なくても上書きする（本当に減った回だけ）")
    p.add_argument("--show", type=int, default=5, help="当たった本を何本まで出すか")
    args = p.parse_args()
    if args.refresh:
        d = fetch(force=args.force)
        print(f"[descriptions] {d['got']} / {d['asked']}本 を書きました → {CACHE}")
    print(report(show=args.show))


if __name__ == "__main__":
    main()
