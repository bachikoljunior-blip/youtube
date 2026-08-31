"""**次の枠で出る1本を名指しし、その本に何が入っていないかを出す。**（**API 0単位**）

読むのは `data/uploaded.jsonl` と `git log` だけです。YouTube には触りません。

## なぜ要るか（2026-09-01・最適化の回）

オーナーが 2026-08-31 に固定した規則3（`src/house_rule.py`）:

    「次の投稿予定までにそこで投稿する動画を改善し続ける」

`docs/trigger_main.md` §4 はそれを `improve` として5つの選択肢に足しました。
**しかし `improve` の当てどころだけが、どこにも印字されていません。**

実測（`data/runs.jsonl`・規則が固定された 2026-08-31 以降の ship **88件**）:

    fix **56件（64%）** ／ (other) 18 ／ verdict 9 ／ **improve 4件（4.5%）** ／ upload 0

**これは怠けではなく、置かれ方の帰結です。** 当てどころの在り方が違います:

    fix      `eta.py` が毎周 **36件** を名指しする（本文の `[!]`）
    verdict  「期日の来た前提」が名指しする
    improve  **どこにも出ない。** `reschedule.py --list`（API 50単位）を
             自分で撃ち、どの本が次かを調べ、何が悪いかを自分で考えるところから

**同じ5択に並べても、探す手間が違えば選ばれません。**
ここは improve の当てどころを、fix と同じ「毎周 印字される1行」にします。

## なぜ「焼いた時刻」で見るか

この機械は**コードを直しても、既に焼いた本には入りません**。
実測 2026-08-31 20:2x —— `src/calc/hendo.py` の未払利息の二重取りを直した回は、
**次の枠の本を作り直すまでを1手にしています**（`data/runs.jsonl` の improve 2件目）。
直しただけで畳んでいたら、**翌日 22:00 に出たのは誤ったままの本**でした。

だから見るのは「その本を焼いたあと、その本を焼くコードが何回 変わったか」です。
**変わっていれば、その差分はその本に入っていません。**

## 出るもの

    next_video()     次に公開される1本（`data/uploaded.jsonl` の `at` が未来で最小）
    stale_commits()  その本を焼いたあとに、生成側へ入ったコミット
    lines()          画面へ出す行（`scripts/run_marker.py --write` が呼びます）

## 覆る条件

- **`at` は控えの側の値です。** 予約を動かすと（`scripts/reschedule.py`）控えにも
  書き戻りますが、**手で YouTube Studio を触ると食い違います。**
  食い違いが起きたら、ここではなく `scripts/reschedule.py --list` が正です。
- `_MAKERS` は**手で並べた一覧**です。`src/pipeline.py` の import から取りました。
  **新しい生成側の module が増えたら、ここに足さないと黙って見落とします**
  （`tests/test_next_slot.py` が pipeline の import と突き合わせます）。
- 「コミットが在る ＝ その本に効く」ではありません（無関係な直しも数えます）。
  **上振れ側に外れる計器です。** 0件 のときだけ「入っている」と言えます。
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "data" / "uploaded.jsonl"
JST = timezone(timedelta(hours=9))

#: **焼き直すと出来上がりが変わるコードだけ。** `src/pipeline.py` の import から
#: 取り、下の2つを外しました（**入れると毎周 鳴りっぱなしになります**）。
#:
#:     src/history.py  投稿済みの復元と控え。**どの題材を選ぶか**の側で、
#:                     題材が決まったあとの出来上がりは1バイトも変えません。
#:                     実測 2026-09-01: この2件だけで誤って3件中2件が鳴っていました
#:                     （`fb421d56` `f011a66e` —— どちらも日枠の控えの話）
#:     src/verify.py   投稿前の門。**落とすか通すか**であって、中身を作りません
#:
#: 増えたらここに足すこと（`tests/test_next_slot.py` が pipeline の import と
#: 突き合わせ、**どちらの箱にも入っていない module**が出たら赤くします）。
_MAKERS = (
    "src/calc/",
    "src/bars.py",
    "src/config.py",
    "src/descriptions.py",
    "src/pipeline.py",
    "src/renderer.py",
    "src/script_writer.py",
    "src/subtitles.py",
    "src/thumbnail.py",
    "src/tts.py",
    "src/util.py",
    "src/visuals.py",
    "src/yomi.py",
)

#: **出来上がりを変えないので、上から外してあるもの**（検査が突き合わせます）。
#: `src/uploader.py` は**焼いたあとの運び方**で、出来上がりを作りません。
#: `src/analytics.py` は `pipeline._refill_topics()` の**題材の補充**だけ
#: （`analytics.optimize(posted)`）。**題材が決まったあとの中身は変えません。**
_NOT_MAKERS = ("src/analytics.py", "src/history.py",
               "src/uploader.py", "src/verify.py")


def _rows(path: Path | None = None) -> list[dict]:
    p = path or LEDGER
    if not p.exists():
        return []
    out = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return out


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    s = str(ts).replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def next_video(now: datetime | None = None,
               path: Path | None = None) -> dict | None:
    """**次に公開される1本**（`at` が未来で最小）。無ければ `None`。

    同じ `video_id` が控えに何度も出ます（`retimed_at` の書き戻し）。
    **`video_id` ごとにいちばん後ろの行**を採ること —— 前の行を採ると、
    予約を外した本（`at` が `null` に変わった本）を「次の1本」に出します。
    """
    t = now or datetime.now(timezone.utc)
    latest: dict[str, dict] = {}
    for r in _rows(path):
        vid = r.get("video_id")
        if vid:
            latest[str(vid)] = r
    fut = []
    for r in latest.values():
        at = _parse(r.get("at"))
        if at and at > t:
            fut.append((at, r))
    if not fut:
        return None
    fut.sort(key=lambda x: (x[0], str(x[1].get("video_id"))))
    at, r = fut[0]
    out = dict(r)
    out["_at"] = at
    return out


def stale_commits(since: datetime | None = None, limit: int = 6) -> list[str]:
    """**その本を焼いたあとに、生成側へ入ったコミット**（`%h %ad %s`）。

    `since` は本を焼いた時刻（`uploaded_at`）。**git が読めない所では空**を返します
    （＝「入っている」と同じ字面になります。上の「覆る条件」の3つ目）。
    """
    if since is None:
        return []
    # **`%ad`（書いた時刻）ではなく `%cd`（入った時刻）を出すこと**（2026-09-01 に踏んだ）。
    #     `--since` は既定で**入った時刻**で絞ります。`%ad` を並べると、
    #     **絞りに使った時刻と、画面に出る時刻が別物**になり、
    #     「焼いた 20:26 のあと」と書いた下に 17:53 が並びました。
    # **そして `format-local` ＋ `TZ` を渡すこと** —— 既定はコミットに記録された
    #     時差で出るので、焼いた時刻（JST 表示）と並べても比べられません。
    env = {**os.environ, "TZ": "Asia/Tokyo"}
    try:
        out = subprocess.run(
            ["git", "log", f"--since={since.isoformat()}",
             "--pretty=format:%h %cd %s", "--date=format-local:%m/%d %H:%M",
             "--", *_MAKERS],
            cwd=str(ROOT), capture_output=True, text=True, timeout=20,
            env=env)
    except (OSError, subprocess.SubprocessError):
        return []
    if out.returncode != 0:
        return []
    got = [ln for ln in out.stdout.splitlines() if ln.strip()]
    return got[:limit] if limit else got


def lines(now: datetime | None = None) -> list[str]:
    """画面へ出す行。**`improve` の当てどころを、fix と同じ形で毎周 出します。**"""
    v = next_video(now=now)
    if not v:
        return ["[次の枠] **予約が1本もありません。** `improve` は当てどころが無い回です"
                "（`python scripts/batch_build.py` で1本 作るか、"
                "池から戻すこと ＝ `python scripts/reschedule.py --move <videoId> <時刻>`）"]
    at = v["_at"].astimezone(JST)
    t = now or datetime.now(timezone.utc)
    hours = (v["_at"] - t).total_seconds() / 3600.0
    out = [
        f"[次の枠] **{at:%m/%d %H:%M} JST（あと {hours:.0f}時間）に出る1本**"
        f"　`{v.get('video_id')}`　{str(v.get('title') or '')[:44]}"
        f"　題材 `{v.get('topic')}`"
    ]
    built = _parse(v.get("uploaded_at"))
    cm = stale_commits(built)
    if built is None:
        out.append("  [?] **焼いた時刻が控えにありません**（`uploaded_at` が空）。"
                   "古さを数えられないので、中身を見て決めること")
    elif not cm:
        out.append(f"  焼いたのは {built.astimezone(JST):%m/%d %H:%M} JST。"
                   "**そのあと生成側のコードは変わっていません** ＝ "
                   "焼き直しても同じ物が出ます。**improve するなら中身のほう**"
                   "（題・サムネ・台本・計算）")
    else:
        out.append(f"  [!] **焼いたのは {built.astimezone(JST):%m/%d %H:%M} JST。"
                   f"そのあと、この本を焼くコードに {len(cm)}件 入っています"
                   f"　—— その直しは、この本に入っていません**")
        for ln in cm:
            out.append(f"       {ln[:118]}")
        out.append("  → **焼き直すのが `improve` の1手です**"
                   "（`python -m src.pipeline` で焼き直し、"
                   "`scripts/reschedule.py --unschedule <古い方>` →"
                   " 新しい方を同じ枠へ `--move`）")
    out.append("  **規則3（`src/house_rule.py`）が言っているのはこの1本のことです。**"
               "　出したら `--ship \"improve: <何を、どう変えたか>\" --lever per_video`")
    return out


def main() -> None:
    for ln in lines():
        print(ln)


if __name__ == "__main__":
    main()
