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

    next_video()        次に公開される1本（`data/uploaded.jsonl` の `at` が未来で最小）
    stale_commits()     その本を焼いたあとに、生成側へ入ったコミット
    pending_thumbnail() サムネイルが控えに在るのに、まだ載っていないか
    quota_note()        枠が戻るのは何時で、公開まで何時間 残っているか
    window_reaches()    **枠が戻るのは、この本が出る前か**（`False` なら もう直せません）
    lines()             画面へ出す行（`scripts/run_marker.py --write` が呼びます）

**行き先が「分類」で終わらないようにしてあります。** 1件目の実装は最後の行が
「**improve するなら中身のほう**（題・サムネ・台本・計算）」で止まっていました ——
それは分類であって当てどころではありません。いまは**その本の具体的な欠陥**と、
**値段（単位）**と、**いつまでに撃てば間に合うか**まで出します。

## 覆る条件

- **`at` は控えの側の値です。** 予約を動かすと（`scripts/reschedule.py`）控えにも
  書き戻りますが、**手で YouTube Studio を触ると食い違います。**
  食い違いが起きたら、ここではなく `scripts/reschedule.py --list` が正です。
- `_MAKERS` は**手で並べた一覧**です。`src/pipeline.py` の import から取りました。
  **新しい生成側の module が増えたら、ここに足さないと黙って見落とします**
  （`tests/test_next_slot.py` が pipeline の import と突き合わせます）。
- 「コミットが在る ＝ その本に効く」ではありません（同じ族の別の題材だけを
  直したコミットも数えます）。**上振れ側に外れる計器です。**
  **0件 のときだけ「入っている」と言えます。** 引いてあるのは2種類だけ ——
  出来上がりを作らない module（`_NOT_MAKERS`）と、
  **その本へ当て直したコミット**（`_applied_to()`）です。
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


def _applied_to(video_id: str | None, since: datetime) -> set[str]:
    """**その回のうちに、この本そのものへ当て直したコミット**の短いハッシュ。

    ## なぜ引くか（2026-09-01。**この道具の1発目が、これで空振りしました**）

    `improve` の1手は「生成側を直して、**その場でこの本に焼き直す**」形です
    （`data/runs.jsonl` の improve 4件のうち3件がそれ）。すると1つのコミットが

        `src/thumbnail.py` を変えた                        ← 生成側なので鳴る
        `data/critique_queue/<この本>.thumb.jpg` も差し替えた ← **もう入っている**

    の両方を持ちます。**引かないと「入っていません」と出続け、
    次の回が同じ手をもう一度 撃ちます。**

    **覆る条件**: 焼き直しの控えが `data/critique_queue/<videoId>.*` 以外へ
    移ったら、ここは黙って 0件 を返します（＝ また空振りが戻ります）。
    """
    if not video_id:
        return set()
    paths = [f"data/critique_queue/{video_id}{ext}"
             for ext in (".json", ".jpg", ".thumb.jpg", ".plan.json")]
    try:
        out = subprocess.run(
            ["git", "log", f"--since={since.isoformat()}",
             "--pretty=format:%h", "--", *paths],
            cwd=str(ROOT), capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return set()
    if out.returncode != 0:
        return set()
    return {ln.strip() for ln in out.stdout.splitlines() if ln.strip()}


def stale_commits(since: datetime | None = None, limit: int = 6,
                  video_id: str | None = None) -> list[str]:
    """**その本を焼いたあとに、生成側へ入ったコミット**（`%h %cd %s`）。

    `since` は本を焼いた時刻（`uploaded_at`）。**git が読めない所では空**を返します
    （＝「入っている」と同じ字面になります。上の「覆る条件」の3つ目）。

    `video_id` を渡すと、**その本へ当て直したコミットは引きます**（`_applied_to()`）。
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
    done = _applied_to(video_id, since)
    got = [ln for ln in out.stdout.splitlines()
           if ln.strip() and ln.split(" ", 1)[0] not in done]
    return got[:limit] if limit else got


def pending_thumbnail(video_id: str | None) -> bool:
    """**その本のサムネイルが、控えに在るのに YouTube へ載っていないか。**

    ## なぜここで出すか（2026-09-01。**この道具の1発目が当てました**）

    判定そのものは `scripts/critique_queue.missing_thumbnail()` が持っています
    （`thumbnail_set is False` かつ bytes が残っているものだけ）。
    **出どころは1か所**にして、ここは呼ぶだけです。

    実測 2026-09-01: **158本**が「焼いてあるのに載っていない」状態で、
    **次に公開される1本もその中に居ました。** 日枠が切れている13時間は
    `thumbnails.set` だけ 403 になり `videos.insert` は通るので、
    **サムネイルの無い予約が積まれます**（`scripts/refresh_thumbnail.py` の頭）。

    **158本 を全部 押すと 7,900単位**（`--missing`）で1日の枠のほとんどが飛び、
    `pool_drain` と取り合います。**いちばん急ぐのはいつも次に出る1本**なので、
    ここはその1本だけを名指しします（**50単位**）。

    **覆る条件**: `missing_thumbnail()` は `None`（分からない）を返しません ——
    印より前に上げた本は区別が付かないので、そもそも出ません。
    **「出ていない ＝ 載っている」ではありません。**
    """
    if not video_id:
        return False
    try:
        from scripts import critique_queue                    # noqa: PLC0415
        return any(r.get("video_id") == video_id
                   for r in critique_queue.missing_thumbnail())
    except Exception:                                          # noqa: BLE001
        return False


def quota_note(publish_at: datetime, now: datetime) -> str | None:
    """**枠が戻るのは何時で、公開まで何時間 残っているか。**（**API 0単位**）

    ## なぜ要るか（2026-09-01。**この回がその状態でした**）

    実測: 日枠は **13,365 / 10,000単位**（403 を47回）で**尽きています**。
    `thumbnails.set` は 50単位 なので、**この回には押せません。**
    `docs/trigger_main.md` §4 は、枠の尽きた回に選ぶのは
    「**次に枠が戻る回の1手を、安くするか・正しい順にする**」だと書いています。

    **そこで効くのが、残り時間です** —— 枠が戻るのは **09/01 16:00 JST**、
    この本が出るのは **22:00 JST**。**猶予は 6時間**しかありません。
    その窓の回が押さなければ、**この本はサムネイル無しで公開されます。**
    「いつか押す」と「この6時間で押す」は別の手なので、数字で出します。

    **覆る条件**: `DAY_UNITS`（10,000）は**公表値で、Google の実数ではありません**
    （`src/quota_ledger.py`）。尽きたかどうかの本当の答えは 403 の側です。
    """
    try:
        from src import quota_ledger, upload_cap              # noqa: PLC0415
        used = int(quota_ledger.spent(now).get("data") or 0)
        cap = int(quota_ledger.DAY_UNITS)
        back = upload_cap.window_end(now)
    except Exception:                                          # noqa: BLE001
        return None
    if used < cap:
        return (f"       枠はまだ在ります（**{used:,} / {cap:,}単位**）。"
                "**この回で押せます。**")
    slack = (publish_at - back).total_seconds() / 3600.0
    when = back.astimezone(JST)
    if slack <= 0:
        return (f"       [!] **枠が尽きています**（{used:,} / {cap:,}単位）。"
                f"戻るのは {when:%m/%d %H:%M} JST ＝ **公開に間に合いません。**"
                "　この本はサムネイル無しで出ます")
    return (f"       [!] **枠が尽きています**（{used:,} / {cap:,}単位）。"
            f"戻るのは {when:%m/%d %H:%M} JST ＝ **公開まで残り {slack:.0f}時間。**"
            "　**その窓の回が押さないと、この本はサムネイル無しで出ます**")


#: **差し替えの2手が要る単位**（`reschedule.py --unschedule` / `--move` ＝
#: どちらも `videos.update` 50単位）。焼き直しそのものは 0単位 です。
SWAP_UNITS = 50 * 2


def window_reaches(publish_at: datetime, now: datetime | None = None) -> bool | None:
    """**枠が戻る時刻は、この本が出る前か。**（**API 0単位**）

    `True` ＝ 戻ってから公開まで時間が在る（＝ その窓の回が撃てば間に合う）。
    `False` ＝ **戻る前に出てしまう**。`None` ＝ 帳面が読めない（**推測しない**）。

    ## なぜ要るか（2026-09-01 22:0x に踏んだ）

    この判定は `quota_note()` が既に持っていました。**呼ばれる所が
    `pending_thumbnail()` の枝の中だけ**で、**サムネイルが既に載っている本では
    一度も走りません。** そして実際に走っていたのは `swap_cost_lines()` のほうで、
    あちらは同じ `window_end()` を読みながら**公開時刻と比べていません**でした。

    実測 —— 次の枠は `a63FzIUV2wI`（**09/02 13:00 JST 公開**）、
    枠が戻るのは **09/02 16:00 JST**。**3時間 遅い。**
    それでも画面に出ていたのは

        **枠が戻ってから、外す → 入れるの順で撃つこと**

    で、**次の回に、もう出来ないことを指示していました。**
    同じ出力の 12行 上に「**公開に間に合いません**」という正しい文が在ります。

    ## これは 9時 の既定に構造で当たります

    枠の頭は**太平洋時間の0時 ＝ JST 16:00**（`upload_cap.window_start`）。
    実測（`data/api_calls.jsonl` の全窓）では、戻ってから
    **1.1時間（08/31）／3.1時間（09/01）**で焼き切れています。
    ＝ 書ける帯は **16:00〜19:00 JST** しかありません。

    `config/channel.yaml` の `publish_hour_jst` は 2026-09-01 に **19 → 9** へ
    移りました（`src/publish_hour.py`。`per_video` の実測に揃えたもので、
    それ自体は正しい）。**9時 は 16:00 の手前**なので、そこに置かれた本を
    差し替えられるのは**前日の 16:00〜19:00 の3時間だけ**です。
    規則3（「次の投稿予定まで改善し続ける」）の言う「まで」の最後の **21時間**が、
    **既定を移した日から、構造的に空になりました。**

    **覆る条件**: `reschedule` が `videos.update` を使わない道を持ったら
    （＝ 差し替えが日枠の外に出たら）、この関数は要りません。
    """
    t = now or datetime.now(timezone.utc)
    try:
        from src import upload_cap                             # noqa: PLC0415
        back = upload_cap.window_end(t)
    except Exception:                                          # noqa: BLE001
        return None
    return back < publish_at


def swap_cost_lines(now: datetime | None = None,
                    publish_at: datetime | None = None) -> list[str]:
    """**差し替えの2手は、日枠が尽きていると撃てません**（2026-09-01 に踏んだ）。

    ## なぜ要るか —— **「insert は通る」と「差し替えられる」は別です**

    すぐ上の行は「焼き直して `--unschedule` → `--move`」と言います。
    **焼き直し（`python -m src.pipeline`）は 0単位** で、
    **`videos.insert`（新しい本を上げる）も日枠を1単位も使いません**
    （`tests/test_insert_never_marked_ok.py` に実測3度）。
    **枠を要るのは、古いほうを外す `videos.update` だけ**です。

    **そこが落とし穴でした。** 枠が尽きた窓で「insert は通る」だけを読むと:

        新しい本を 22:00 に insert する  → 通る
        古い本の予約を外す              → **403**
        結果                            → **22:00 に 2本 公開される**

    **オーナー規則1（1日1本・`src/house_rule.py`）に正面から当たります。**
    2026-09-01 09:1x の回が、この一歩手前で気づいて撃たずに畳んでいます
    （`docs/JOURNAL.md`）。**気づかなければ、規則が破れていました。**

    ## 覆る条件

    - `reschedule` が `videos.update` を使わない道を持ったら、この註は要りません
    - 枠が在る窓では「在ります」とだけ言います（**止める門ではありません** ——
      判断は撃つ側がします）
    - 帳面が読めない回は**何も言いません**（推測で手を止めないため）
    """
    t = now or datetime.now(timezone.utc)
    try:
        from src import quota_ledger, upload_cap              # noqa: PLC0415
        used = int(quota_ledger.spent(t).get("data") or 0)
        cap = int(quota_ledger.DAY_UNITS)
        back = upload_cap.window_end(t)
    except Exception:                                          # noqa: BLE001
        return []
    if used < cap:
        return [f"       差し替えの2手は **{SWAP_UNITS}単位**"
                f"（`videos.update` ×2）。枠は在ります（{used:,} / {cap:,}単位）"]
    when = back.astimezone(JST)
    head = (f"       [!] **差し替えの2手（{SWAP_UNITS}単位・`videos.update` ×2）は、"
            f"この窓では 403 です**（{used:,} / {cap:,}単位）。"
            f"戻るのは {when:%m/%d %H:%M} JST")
    # **戻る時刻が公開より後なら、「戻ってから撃て」は嘘です**（2026-09-01 22:0x）。
    # `window_reaches()` の註に実測。**推測では言いません** ——
    # `publish_at` を渡されていない回・帳面が読めない回は、今までどおりの案内。
    if publish_at is not None and window_reaches(publish_at, t) is False:
        late = (back - publish_at).total_seconds() / 3600.0
        return [
            head,
            f"       [!] **この本が出るのは {publish_at.astimezone(JST):%m/%d %H:%M} JST ＝ "
            f"枠が戻る {late:.0f}時間 前です。差し替えは間に合いません。**"
            "　**この本は、いまの中身のまま出ます** —— "
            "焼き直しても載せる口が開きません（`videos.update` は日枠の内側）",
            "       → **この回に `improve` を当てるなら、その次の枠の本へ。**"
            f"　そして枠の頭は **{when:%H:%M} JST** です ——"
            "　それより前の時刻に置いた本は、**前日の窓でしか差し替えられません**"
            "（`config/channel.yaml` の `publish_hour_jst` はいま 9時・"
            "`src/next_slot.window_reaches` に実測）",
        ]
    return [
        head,
        "       **焼き直しと `videos.insert` は日枠を使わないので通ります。"
        "そこだけ撃つと、古い本の予約が外せず 同じ枠に 2本 出ます** ——"
        "　オーナー規則1（1日1本）に当たります。**枠が戻ってから、"
        "外す → 入れるの順で撃つこと**",
    ]


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
    cm = stale_commits(built, video_id=str(v.get('video_id') or '') or None)
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
        out.extend(swap_cost_lines(t, publish_at=v["_at"]))
    if pending_thumbnail(str(v.get("video_id") or "") or None):
        out.append("  [!] **サムネイルの bytes は控えに在りますが、YouTube に"
                   "載っていません**（`thumbnail_set: false`）。"
                   "**この1本だけなら 50単位**:")
        out.append("       python scripts/refresh_thumbnail.py --missing "
                   f"--video {v.get('video_id')}")
        out.append("       （`--missing` だけだと実測 158本 ＝ **7,900単位** で、"
                   "`pool_drain` と枠を取り合います）")
        qn = quota_note(v["_at"], t)
        if qn:
            out.append(qn)
    out.append("  **規則3（`src/house_rule.py`）が言っているのはこの1本のことです。**"
               "　出したら `--ship \"improve: <何を、どう変えたか>\" --lever per_video`")
    return out


def main() -> None:
    for ln in lines():
        print(ln)


if __name__ == "__main__":
    main()
