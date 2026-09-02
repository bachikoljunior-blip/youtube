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


def writable_from(now: datetime | None = None) -> datetime | None:
    """**いま `videos.update` が撃てないなら、撃てるようになる時刻**（**API 0単位**）。

    撃てるなら `None`。帳面が読めなくても `None`（**推測しません**）。

    ## なぜ要るか（2026-09-02 01:0x に測って足した。**15時間後に効く欠陥でした**）

    `window_reaches()` は「**この本が出る前に枠は戻るか**」を答えます。
    足りなかったのは、その裏返し ——
    **「枠が戻ったとき、その置き先はまだ未来か」**のほうです。

    実測（2026-09-02 01:0x・`scripts/reschedule.py --compact`）:

        いま（01:07 JST）の割り当ての1行目
            09/02 13:00 → 09/02 09:00  a63FzIUV2wI
        枠が戻るのは **09/02 16:00 JST**

    **置き先の 09:00 も、動かす本の公開 13:00 も、枠が戻る 3時間 前です。**
    ＝ **この行は、撃てる時刻には1つも残っていません。**

    `compact_plan()` は `now + lead_min` しか床にしておらず、
    **枠が戻る時刻を1つも見ていませんでした。** 0単位で案を印字する回と、
    枠の戻った回に撃つ回が**別の回**である以上、
    **床は「いま」ではなく「撃てるようになる時刻」でなければ、案は腐ります。**

    **覆る条件**: `reschedule` が `videos.update` を使わない道を持ったら
    （＝ 差し替えが日枠の外に出たら）、この関数は要りません
    （`window_reaches()` の覆る条件と同じ日に発火します）。
    """
    t = now or datetime.now(timezone.utc)
    try:
        from src import quota_ledger, upload_cap                # noqa: PLC0415
        used = int(quota_ledger.spent(t).get("data") or 0)
        cap = int(quota_ledger.DAY_UNITS)
        back = upload_cap.window_end(t)
    except Exception:                                           # noqa: BLE001
        return None
    if used < cap:
        return None
    return back if back > t else None


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


#: **予約の暦を規則と突き合わせる窓の上限**（日）。
#: これより先は、まだ作っていない本のほうが多いので数えません。
CALENDAR_DAYS = 120


def calendar(now: datetime | None = None,
             path: Path | None = None) -> dict:
    """**予約の実物が、模型の前提（1日1本）を守っているか。**（**API 0単位**）

    ## なぜ要るか（2026-09-01 夜・最適化の回。**この穴には名前がありませんでした**）

    `scripts/eta.py` の到達日は **`PLAN_PUBLISH_PER_DAY = 1`（規則1）で解いています。**
    そして `physical_caps()` は `density` の腕をこう止めます ——
    「**規則 1本/日 ÷ いま続けられる 1.0本/日 ＝ ×1.00 ＝ 引き代なし**」。

    **その分母は「続けられるか」（供給の能力・`sustained_density()`）であって、
    「実際に予約に入っているか」ではありません。** 実測 2026-09-01 20:0x
    （`data/uploaded.jsonl` を `video_id` ごとに畳んで JST の日で数えた）:

        09/01  1本      09/03  **0本**
        09/02  1本      **09/05 〜 09/23 の 19日、1本も予約が入っていません**
        09/04  1本      09/24 から先は 1日 7〜13本（規則の 7〜13倍）

    **今後23日のうち20日が空**で、実際の密度は **0.13本/日**。
    模型は 1.0本/日 で解いているので、**到達日はその差のぶん早すぎます。**
    そして腕の側は「規則に張り付いている＝引き代なし」と名乗ります ——
    **張り付いているのは模型の前提のほうで、機械はその 1/7 しか出していません。**

    `src/house_rule.py` が名指ししている、この repo でいちばん多い壊れ方
    （「**言っている所と、している所が別**」）の、暦の側の実例です。

    **`scripts/queue_lag.py` は見つけられません** —— あちらの入れ替えは
    **(日,時刻) の集合を1つも変えない**ので（自分でそう書いています）、
    **空いている日は最初から視野の外**です。実測: 同じ時刻に撃った
    `queue_lag.py --plan` は「合計 **0日**／入れ替え **0手**」でした。

    ## 直す手（**新しい本は1本も要りません。もう予約に在る本を前へ倒すだけ**）

        python scripts/reschedule.py --compact          # 割り当てだけ・**0単位**
        python scripts/reschedule.py --compact --apply  # 1本 50単位（`videos.update`）

    `--compact` の `--per-day` は `_measured_per_day()` が
    `src/house_rule.py` から 1 を読むので、**詰めた先は自動で 1本/日**です
    （実測 2026-09-01: 26本 を 09/03〜09/27 へ 1日1本 で並べる案が出ました）。

    ## 覆る条件

    - **控えは実物とずれることがあります**（`src/ledger_truth.py`・2026-09-01 に
      「実物に予約が在るのに控えは無い」口が4つ 見つかっています）。
      **空だと出たら、撃つ前に `scripts/reschedule.py --list`（50単位）で確かめること。**
    - オーナーが 1日1本 を自分の言葉で外したら、`house_rule` 経由で自動に緩みます
    - 予約が1本も無い回は何も言いません（`total` が 0 なら `calendar_lines()` は空）
    """
    t = now or datetime.now(timezone.utc)
    try:
        from src import house_rule                            # noqa: PLC0415
        rule = max(1, int(house_rule.PUBLISH_PER_DAY))
    except Exception:                                          # noqa: BLE001
        rule = 1
    latest: dict[str, dict] = {}
    for r in _rows(path):
        vid = r.get("video_id")
        if vid:
            latest[str(vid)] = r
    per_day: dict[str, int] = {}
    for r in latest.values():
        at = _parse(r.get("at"))
        if at and at > t:
            key = at.astimezone(JST).strftime("%Y-%m-%d")
            per_day[key] = per_day.get(key, 0) + 1
    out: dict = {"rule": rule, "total": sum(per_day.values()), "per_day": per_day,
                 "empty": 0, "run": 0, "run_from": None, "over": [],
                 "days": 0, "last": None, "density": 0.0}
    # ---- 規則5（固定その4・2026-09-02）。**ここが、いまの欠陥の定義です** ----
    #     下の `empty` / `run` / `over` は「先の日付に予約が在るのが正常」という
    #     前提の数です。オーナーが 2026-09-02 に **「現在の日付にしか予約しない」**
    #     と固定したので、**先の日付が空であることが正しい状態**になりました。
    #     下の数え方は残します（他の道具が読んでいる・過去のログと並べられる）が、
    #     **画面が名指しするのは、この `ahead` のほう**です。
    #
    #     **`if not per_day` より前で数えること**（2026-09-02 に踏んだ）——
    #     下には早い戻りが2つ在り（予約が無い回・今日ぶんだけの回）、
    #     **正しい姿の回ほどそこで返る**ので、後ろに置くと `ahead` が
    #     「いちばん健全な回にだけ無い」鍵になります。
    try:
        from src import house_rule                            # noqa: PLC0415
        out["same_day_only"] = bool(house_rule.same_day_only())
    except Exception:                                          # noqa: BLE001
        out["same_day_only"] = False
    _today = t.astimezone(JST).date()
    _ahead = {d: n for d, n in per_day.items()
              if datetime.strptime(d, "%Y-%m-%d").date() > _today}
    out["ahead"] = sum(_ahead.values())
    out["ahead_days"] = len(_ahead)
    out["ahead_top"] = max(_ahead.items(), key=lambda kv: kv[1]) if _ahead else None
    out["ahead_first"] = min(_ahead) if _ahead else None
    out["ahead_last"] = max(_ahead) if _ahead else None
    if not per_day:
        return out
    out["last"] = max(per_day)
    # **今日は数えません**（2026-09-01 に踏んだ）。控えは `at` が未来の行しか
    #     残さないので、**今日ぶんが公開されたあとの今日は、必ず「空」に見えます。**
    #     偽陽性で毎周 鳴る画面は、次に来た側が読み飛ばします。数えるのは明日から。
    start = t.astimezone(JST).date() + timedelta(days=1)
    end = datetime.strptime(out["last"], "%Y-%m-%d").date()
    span = min((end - start).days + 1, CALENDAR_DAYS)
    if span <= 0:
        return out
    run = 0
    got = 0
    for i in range(span):
        key = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        n = per_day.get(key, 0)
        got += n
        out["days"] += 1
        if n == 0:
            out["empty"] += 1
            run += 1
            if run > out["run"]:
                out["run"] = run
                out["run_from"] = (start + timedelta(days=i - run + 1)).strftime("%Y-%m-%d")
        else:
            run = 0
            if n > rule:
                out["over"].append((key, n))
    out["density"] = got / float(out["days"]) if out["days"] else 0.0
    # **平均は、後ろの作り置きに持ち上げられます**（2026-09-01 に踏んだ）。
    #     実測の1発目は「39日の平均 2.77本/日 ＝ 規則の 277%」と出ました ——
    #     **19日 連続で空なのに「規則より多い」と読める形**です。
    #     縛っているのは**空白が終わるまでの窓**なので、そこを別に出します。
    if out["run"] and out["run_from"]:
        near_end = (datetime.strptime(out["run_from"], "%Y-%m-%d").date()
                    + timedelta(days=out["run"] - 1))
        near_days = (near_end - start).days + 1
        if near_days > 0:
            near_got = sum(per_day.get((start + timedelta(days=i)).strftime("%Y-%m-%d"), 0)
                           for i in range(near_days))
            out["near_days"] = near_days
            out["near_density"] = near_got / float(near_days)
            out["near_until"] = near_end.strftime("%Y-%m-%d")
    return out


def _calendar_quota_lines(t: datetime, empty: int = 0) -> list[str]:
    """暦を直す手が**この窓で撃てるか**。枠が読めない回は黙ります（推測で止めないため）。

    ## **撃てる回のほうを、大きく書くこと**（2026-09-02 12:3x に測って直した）

    **ここは長らく、向きが逆でした。**

        403 の回（＝ **撃てない**回）   `[!] **この窓では 403 です** …
                                       **そこで最初に撃つのがこれです**`  ← 強い
        枠の在る回（＝ **撃てる**回）   `枠は在ります（0 / 10,000単位）`    ← 弱い

    **撃てない回にだけ号令が出て、撃てる回には出ていませんでした。**
    実測（`scripts/retro.py` の「次の回へ」）—— **`reschedule --compact --apply` を
    「枠が戻る 16:00 に撃つこと」と書いた回が 3件 並んでおり、3件とも撃たれていません。**
    暦の空きは 20日 のまま、いちばん長い空白は 19日 連続です。

    枠が戻ったあとの回が読むのは、**この関数の `used < cap` の枝**です。
    そこに「枠は在ります」としか書いていなければ、**申し送りの側にどれだけ
    大きく書いても、その回の画面では 403 の回より静かになります。**

    **覆る条件**: 暦が規則どおりになれば `calendar_lines()` がこの節ごと出しません
    （＝ 鳴っていない回には、この号令も出ません）。

    ## **黙らせる4つ目の口が、まだ空いていました**（2026-09-02 12:4x に測って塞いだ）

    上の直しは枝の**中身**を入れ替えただけで、**どちらの枝へ入るかは
    `quota_ledger.spent() >= DAY_UNITS`（＝ 帳面の見積り）のまま**でした。
    **repo の判定はそこではありません** —— `docs/trigger_main.md` §2433 と
    `scripts/run_marker.py` が「**判定は観測した 403 です
    （`upload_cap.day_quota().open`）**」と書いています。**2つの出どころが在り、
    食い違ったときに黙るのは、また撃てる回のほうでした。**

    実測（2026-09-02 12:4x・`spent()=16,043` のまま `day_quota()` だけ開かせた）:

        upload_cap.day_quota().line   「**あの 403 は日枠ではありません。押してよい。**」
        _calendar_quota_lines()       「**この窓では 403 です**（16,043 / 10,000単位）」

    **同じ回の画面で、片方が「押してよい」、片方が「403 です」。**
    `day_quota()` が開くのは実際に起きる2つの場合です ——
    **403 のあとに呼び出しが通った**とき（`quota_ok_after_hits`。日枠は窓の中で
    戻らないので、あれは日枠ではなかった ＝ 短い間に撃ちすぎた側）と、
    **枠が読めなかった**とき（あちらは「読めない」を「閉じている」と読みません）。
    どちらも `spent()` は cap を超えたままなので、**この関数だけが黙り続けます。**

    そして `spent()` は超えます —— **単価は公表値で Google の実数ではなく**
    （`quota_ledger.DAY_UNITS` の註）、いまの実測は **16,043 / 10,000 ＝ 160%** です。

    **いまは `day_quota().open` で分岐し、`spent()` は但し書きにだけ使います。**
    外す向きは撃ってみれば分かります（403 が返ったらそこまでは動いている ＝
    次の窓で `--compact` をもう一度）。**黙る側は、窓を丸ごと1つ落とします。**

    **覆る条件**: `quota_ledger.spent()` が公表値ではなく Google の実数を
    読めるようになったら、`day_quota()` と二重に持つ意味がなくなります
    （そのときは `upload_cap.day_quota()` の側をこの見積りで作ること）。
    """
    try:
        from src import quota_ledger, upload_cap              # noqa: PLC0415
        used = int(quota_ledger.spent(t).get("data") or 0)
        cap = int(quota_ledger.DAY_UNITS)
        back = upload_cap.window_end(t)
    except Exception:                                          # noqa: BLE001
        return []
    # **判定は観測した 403**（`docs/trigger_main.md` §2433）。帳面の見積りは
    #     但し書きにだけ使うこと —— 食い違ったときに黙ると、窓を1つ落とします。
    try:
        shut = upload_cap.day_quota(t).open is False
    except Exception:                                          # noqa: BLE001
        shut = False                                           # 読めない＝押してみる
    if not shut:
        got = [f"       [!] **いま撃てます**（403 は観測していません）—— "
               "**この回の最初の1手が、すぐ上の `--apply` です。**"]
        if used >= cap:
            got.append(f"           （帳面の見積りは {used:,} / {cap:,}単位 ですが、"
                       "**単価は公表値で Google の実数ではありません**。"
                       "**判定は観測した 403 のほうです。** 途中で 403 が返っても、"
                       "**そこまでは動いています** —— 次の窓で `--compact` を"
                       "もう一度 撃つこと）")
        if empty:
            got.append(f"           撃たなければ、空の {empty}日 はそのまま次の回へ"
                       "持ち越します。**「次の回へ」に書いて渡した回が 3件 あり、"
                       "3件とも撃たれていません**（枠の在る回のほうが、"
                       "403 の回より静かな画面を見ていたためです）")
        return got
    return [f"       [!] **この窓では 403 です**（{used:,} / {cap:,}単位）。"
            f"戻るのは {back.astimezone(JST):%m/%d %H:%M} JST —— "
            "**そこで最初に撃つのがこれです**（`videos.insert` は枠を使わないので、"
            "投稿そのものは止まりません）"]


def _same_day_lines(c: dict, t: datetime) -> list[str]:
    """**規則5（固定その4）の下での暦の画面。** 意味が下の版と逆です。

    ## なぜ逆になったか（2026-09-02・オーナーが固定した）

    オーナー原文（`src/house_rule.OWNER_VERBATIM_SAME_DAY`）:

        「現在の日付にしか予約しないってことだからね？」

    **その日の1本を、その日に予約する。先の日付には1本も置かない。**
    だから ——

        先の日付が空          **正常**（この関数は静かな1行だけ出します）
        先の日付に予約が在る  **これが欠陥**（＝ 外すべき作り置き）

    **この節の前の版は、まっすぐ逆のことを言っていました** ——
    「今後 N日 のうち M日 が空」を `[!]` で鳴らし、
    **`reschedule.py --compact --apply`（先の日付へ並べ直す手）を名指し**して
    いました。規則5 の下では、それは**欠陥を増やす手**です。
    実際に、直前の3回の申し送りが揃ってその手を名指ししています
    （撃たれる前にオーナーが止めました）。

    直す手は逆向きで、**`python scripts/pool_drain.py --apply --keep 0`**
    （予約を外して private の下書きへ戻す。**削除はしません**）。

    ## 覆る条件

    オーナーが「先の日付にも置いてよい」と言って
    `house_rule.SAME_DAY_SCHEDULING_ONLY` が `False` になったら、
    `calendar_lines()` は下の（穴を欠陥と読む）枝へ自動で戻ります。
    **枝を消していないのは、そのためです。**
    """
    ahead = int(c.get("ahead") or 0)
    days = int(c.get("ahead_days") or 0)
    if not ahead:
        return ["[暦] **先の日付に予約はありません**（規則5・固定その4）。"
                "**これが正しい状態です。**"
                "　今日ぶんの1本を今日 予約し、公開したら次の日の1本を作り始めること"]
    out = [f"[!] [暦] **先の日付に予約が {ahead}本 残っています**"
           f"（{days}日 ぶん・規則5「現在の日付にしか予約しない」に反します）"]
    if c.get("ahead_first"):
        out.append(f"     いちばん手前は **{c['ahead_first']}**"
                   f"／いちばん先は **{c['ahead_last']}**")
    top = c.get("ahead_top")
    if top:
        out.append(f"     いちばん多い日は **{top[0]} の {top[1]}本**"
                   " —— 規則が固定される前に積んだ作り置きです")
    out.append("     **空いている日は欠陥ではありません。** 先の日付が空であることが"
               "正しい状態です（`src/house_rule.SAME_DAY_SCHEDULING_ONLY`）。"
               "**`scripts/reschedule.py --compact --apply` は撃たないこと** ——"
               "あれは先の日付へ並べ直す手で、この規則に反します")
    out.append("     → **外す手**（**削除はしません**・private の下書きへ戻すだけ）:")
    out.append("       python scripts/pool_drain.py --keep 0          # 案だけ・**0単位**")
    out.append(f"       python scripts/pool_drain.py --apply --keep 0  # 1本 50単位"
               f"（{ahead}本 なら およそ **{ahead * 50:,}単位**）")
    out.append("       **今日ぶんの未公開の1本は外さないこと**"
               "（`ahead` が見ているのは明日以降だけ）")
    out.extend(_calendar_quota_lines(t, empty=0))
    out.append("     **控えは実物とずれることがあります**（`python -m src.ledger_truth`）。"
               "一覧に出ない本が別に在ります —— そちらは "
               "`python scripts/reschedule.py --unschedule <videoId>` で個別に外すこと")
    return out


def calendar_lines(now: datetime | None = None,
                   path: Path | None = None) -> list[str]:
    """`calendar()` を画面へ。**守れている回は1行、破れている回は当てどころまで。**

    **規則5（固定その4・2026-09-02）が効いている間は `_same_day_lines()` です。**
    下の枝（「暦の穴が欠陥」）は、その規則が外れたときのために残してあります。
    """
    c = calendar(now=now, path=path)
    if not c["total"]:
        return []
    # **規則5 の枝を、`days` より先に見ること**（2026-09-02 に踏んだ）——
    #     `days` は「明日以降 いくつの日を見たか」なので、
    #     **今日ぶんの1本だけが在る＝いちばん正しい姿の回で 0** になります。
    #     後ろに置くと、その回だけ画面が黙りました。
    if c.get("same_day_only"):
        return _same_day_lines(c, now or datetime.now(timezone.utc))
    if not c["days"]:
        return []
    rule = c["rule"]
    if not c["empty"] and not c["over"]:
        return [f"[暦] 予約 {c['total']}本／今後 {c['days']}日 は"
                f"**規則どおり {rule}本/日**（空きなし・超過なし）"]
    out = [f"[!] [暦] **予約の実物が規則（{rule}本/日）と別です** —— "
           f"今後 {c['days']}日 のうち **{c['empty']}日 が空**"]
    if c["run"] >= 2:
        out.append(f"     いちばん長い空白は **{c['run']}日 連続**"
                   f"（{c['run_from']} 〜・**その間 1本も公開されません**）")
    if c.get("near_days"):
        out.append(f"     **その空白が終わるまでの {c['near_days']}日（〜{c['near_until']}）の"
                   f"実際の密度は {c['near_density']:.2f}本/日 ＝ 規則の "
                   f"{c['near_density'] / rule:.0%}**"
                   f"　（今後 {c['days']}日 の平均は {c['density']:.2f}本/日 ですが、"
                   "**平均は後ろの作り置きに持ち上げられます。縛っているのは手前です**）")
    if c["over"]:
        top = max(c["over"], key=lambda x: x[1])
        out.append(f"     一方 **{len(c['over'])}日 が規則を超えています**"
                   f"（いちばん多い日 {top[0]} の **{top[1]}本** ＝ 規則の {top[1] // rule}倍）"
                   " —— 規則が固定される前に積んだ作り置きです")
    out.append(f"     **`scripts/eta.py` の到達日は {rule}本/日 で解いています。**"
               "　実物がその下にある間、**その日付は早すぎます**"
               "（`eta.physical_caps` の分母は「続けられるか」＝供給の能力で、"
               "**暦を1日も見ていません**）")
    out.append("     → **新しい本は1本も要りません。もう予約に在る本を前へ倒すだけです**:")
    out.append("       python scripts/reschedule.py --compact          # 割り当てだけ・**0単位**")
    out.append(f"       python scripts/reschedule.py --compact --apply  # 1本 50単位"
               f"（空き {c['empty']}日 なら およそ **{c['empty'] * 50:,}単位**）")
    # **順番を書くこと**（2026-09-01 夜）。実測 2026-09-01 の日枠 13,966単位 の内訳は
    #     `reschedule.py:_update` 8,212 ／ `history.py:channel_video_ids` 5,412 で、
    #     **`status.py` を先に撃つと、この手のぶんが残りません。**
    #     枠は 09/02 16:00 JST に戻りますが、戻った枠を先に読みへ使うと、
    #     **同じ穴のまま次の窓へ持ち越します。**
    out.append("       **`status.py` より先に撃つこと** —— あちらは読みだけで"
               "実測 5,000単位 超（`history.py:channel_video_ids`）。"
               "後回しにすると、戻った枠がこの手に残りません")
    out.extend(_calendar_quota_lines(now or datetime.now(timezone.utc),
                                     empty=int(c.get("empty") or 0)))
    out.append("     **控えは実物とずれることがあります**（`src/ledger_truth.py`）。"
               "撃って 0本 しか動かない回は `scripts/reschedule.py --list`（50単位）で"
               "実物を見ること")
    return out


def drafts(now: datetime | None = None,
           path: Path | None = None, days: int = 7) -> list[dict]:
    """**予約を付けずに上げた private の下書き**（新しい順）。**API 0単位。**

    ## なぜ要るか（2026-09-02・規則5「1日の回り方」）

    オーナー原文:「**その日の投稿の後は次の日の作成になるってわかってるよな？**」

        公開したら → **すぐ次の日の1本を作り始める**（`upload_only.py <ID> --draft`）
                   → 次の枠まで改善し続ける
                   → **その日になったら、その日で予約して出す**

    **真ん中の「作ってあるが、まだ予約していない本」を、どの道具も出していません**
    でした。`next_video()` は `at` が未来の行しか見ないので、**下書きは
    どの画面にも出ません** —— つまり次に来た回は、**もう在る本をもう一度 作ります。**

    見分け方は3つ揃うこと ——

        `at` が空          まだ予約が入っていない
        `uploaded_at` が在る 上がってはいる（`--skip-upload` の本と分かれる）
        **`retimed_at` が無い** ＝ **一度も予約されたことがない**

    ## **3つ目が本体です**（2026-09-02 に、撃って踏んだ）

    最初は `days`（新しさ）だけで切りました。**実物で撃つと 136本** ——
    `pool_drain` で外した本も `at` が `None` になるので、
    **池化したばかりの本が全部 混ざりました**（`UIWHsypOPPg` `J67vEIw_VRE` …）。
    「作ってあるが、まだ予約していない本」とは**逆の意味の本**です。

    `dupes.retime(id, None)` は `retimed_at` を残します。**`--draft` で上げた本は
    予約を一度も触っていないので、この印がありません。** そこで分かれます。
    `days` は保険として残してあります（古い控えの取りこぼし避け）。

    ## 覆る条件

    `retime()` が印を残さなくなったら、ここは池化した本を全部 拾い直します
    （＝ また 136本 に戻ります）。**そのときは印のほうを直すこと。**
    """
    t = now or datetime.now(timezone.utc)
    latest: dict[str, dict] = {}
    for r in _rows(path):
        vid = r.get("video_id")
        if vid:
            latest[str(vid)] = r
    out = []
    for r in latest.values():
        if r.get("at") or r.get("retimed_at"):
            continue                      # 予約ずみ／**一度 予約して外した本**（池化）
        made = _parse(r.get("uploaded_at"))
        if made is None or (t - made).days > days:
            continue
        out.append({**r, "_made": made})
    out.sort(key=lambda r: r["_made"], reverse=True)
    return out


def today_count(now: datetime | None = None,
                path: Path | None = None) -> int:
    """**きょう（JST）の枠が、もう何本 埋まっているか。**（**API 0単位**）

    ## なぜ `calendar()` の `per_day` を使わないか（2026-09-02 に踏んだ）

    `calendar()` の `per_day` は **`at > t`（これから出る本）だけ**を数えます。
    だから **きょう 13:00 に公開ずみの1本は、そこに入っていません。**
    「きょうの枠は空いているか」を聞くと、公開した直後の回ほど「空いている」と
    答えます —— **いちばん埋まっている瞬間に、いちばん空いて見える**数え方です。

    ここは `scripts/slot_gate.per_day(now=<JST 0時>)` と**同じ床**にします
    （＝ **きょう既に公開した本も、きょうを埋めているものとして数える**）。
    聞いているのは「規則1（1日1本）の枠が残っているか」なので、そちらが正しい向きです。

    ## 覆る条件

    控えは**上限側の見積り**です（取り消した本も残る）ので、この数は
    **多めに出る側**に外れます ＝ 「埋まっている」と答えたら本物、
    「空いている」は言い切れません（`scripts/slot_gate.py` の註と同じ）。
    """
    t = now or datetime.now(timezone.utc)
    day = t.astimezone(JST).date()
    floor = datetime(day.year, day.month, day.day, tzinfo=JST)
    latest: dict[str, dict] = {}
    for r in _rows(path):
        vid = r.get("video_id")
        if vid:
            latest[str(vid)] = r
    n = 0
    for r in latest.values():
        at = _parse(r.get("at"))
        if at and at >= floor and at.astimezone(JST).date() == day:
            n += 1
    return n


def today_full(now: datetime | None = None,
               path: Path | None = None) -> bool:
    """**きょうの枠が規則1（1日1本）で埋まっているか。**"""
    try:
        from src import house_rule                             # noqa: PLC0415
        rule = max(1, int(house_rule.PUBLISH_PER_DAY))
    except Exception:                                          # noqa: BLE001
        rule = 1
    return today_count(now=now, path=path) >= rule


def draft_lines(now: datetime | None = None,
                path: Path | None = None) -> list[str]:
    """`drafts()` を画面へ。**規則5 が効いている回だけ出します**（無ければ空）。

    ## **きょうの枠が埋まっている回に `--move <きょう>` を出さないこと**

    **2026-09-02 に、この関数は実際にそれを出していました。** 実物:

        きょう 09/02 13:00 JST に1本 公開ずみ（規則1 の枠は埋まっている）
        13:57 JST に次の日のぶんを `--draft` で上げた（**規則5 の正しい回り方**）
        → この関数の印字: `reschedule.py --move MqQKSnbM0OI 2026-09-02T20:00`

    **撃つと 09/02 が 2本 になります** —— オーナーが固定した規則1
    （`src/house_rule.py`「動画は1日一本」）に正面から反します。
    日付は `{t:%Y-%m-%d}`（＝ **いつ撃っても「きょう」**）を書いていて、
    **きょうの枠が空いているかを一度も見ていませんでした。**

    そして **その下書きは、きょうのぶんではありません** —— 規則5 の回り方は
    「公開したら → すぐ**次の日**の1本を作り始める → **その日になったら**予約」
    なので、公開直後に立っている下書きは**明日のぶん**です。
    きょう やることは予約ではなく、**規則3（出る瞬間まで良くし続ける）**のほうです。

    `calendar()` の `per_day` では判定できません（`at > t` しか数えないので、
    **公開した直後の回ほど「きょうは空いている」と答えます**）。`today_count()` を見ること。

    ## 覆る条件

    - オーナーが規則1（1日1本）を外したら、`house_rule.PUBLISH_PER_DAY` 経由で
      枠の本数が変わります（この関数は読むだけなので、1行も直りません）。
    - `today_count()` は**多めに出る側**に外れます（控えは上限側の見積り）。
      「埋まっている」と言われて実物が空だった回は、`scripts/reschedule.py --list`
      （50単位）で実物を見てから手で `--move` すること。
    """
    try:
        from src import house_rule                             # noqa: PLC0415
        if not house_rule.same_day_only():
            return []
    except Exception:                                          # noqa: BLE001
        return []
    got = drafts(now=now, path=path)
    t = (now or datetime.now(timezone.utc)).astimezone(JST)
    if not got:
        # ---- **0本 のほうが欠陥です**（2026-09-02 に足した） ----------------
        #
        # ここは長らく「下書きが在れば出す・無ければ黙る」でした。
        # **固定その4「1日の回り方」の下では、向きが逆です**（オーナー原文）:
        #
        #     公開したら → **すぐ次の日の1本を作り始める**
        #                → 次の枠まで改善し続ける → その日になったら予約
        #
        # ＝ **公開したあとに下書きが 0本 なのが、名指しされた欠陥そのもの**です。
        # `CLAUDE.md` 冒頭が実物でそう書いています ——「2026-09-02 時点で、
        # これが出来ていませんでした —— 09/02 13:00 に公開したあと、09/03 のぶんが
        # **1本も作られていない**まま数時間が流れています」。
        #
        # **鳴る側と黙る側が入れ替わっていました** ——
        # 回っている回だけが画面に出て、**止まっている回は何も出ない。**
        # `scripts/slot_gate.py` も塞ぎません（`LEAD_DAYS = 0` ＝ **きょうしか見ない**
        # ので、きょうの1本が出た瞬間に黙ります）。**公開直後から翌 0時 までの間、
        # 「次の日のぶんを作れ」と言う口が1つもありませんでした。**
        #
        # **きょうの枠が埋まっている回にだけ言うこと。** まだ埋まっていない回の
        # 仕事は「きょうの1本」で、それは `slot_gate` が言います
        # （両方が同時に鳴ると、どちらを先にやるか分からなくなります）。
        if not today_full(now=now, path=path):
            return []
        return [
            "[!] [下書き] **次の日のぶんの下書きが 0本 です**"
            "（規則5「1日の回り方」・固定その4）",
            f"     きょう（{t:%m/%d} JST）の枠は埋まっています。"
            "オーナー原文「**その日の投稿の後は次の日の作成になるってわかってるよな？**」",
            "     → **公開したら、すぐ次の日の1本を作り始めること。**"
            "「その日に予約する」は「その日まで何もしない」ではありません ——"
            "**作るのは前の日から、予約だけが当日**です（`CLAUDE.md`「1日の回り方」）。",
            "",
            "  python -m src.pipeline --topic <名前> --dry-run",
            "  python scripts/inspect_build.py <名前>          # **投稿前に必ず目で見る**",
            "  python scripts/upload_only.py <名前> --draft    # **予約は付けない**"
            "（`videos.insert` は日枠を使わないので 403 の窓でも通ります）",
            "",
            f"     そして**明日（{(t + timedelta(days=1)):%m/%d}）になってから**"
            "、その日の枠へ `reschedule.py --move`。"
            "**先の日付には置かないこと**（規則5）。",
            "     それまでの時間は規則3 の対象です —— 次の枠で出る1本を、"
            "出る瞬間まで良くし続けること。",
        ]
    out = [f"[下書き] **予約を付けずに上げてある本が {len(got)}本 あります**"
           "（規則5「1日の回り方」—— 作るのは前の日から、**予約だけが当日**）"]
    for r in got[:3]:
        made = r["_made"].astimezone(JST)
        out.append(f"     `{r.get('video_id')}`　{str(r.get('title') or '')[:40]}"
                   f"　焼いたのは {made:%m/%d %H:%M} JST")
    if today_full(now=now, path=path):
        # **きょうの枠は埋まっています**（規則1 ＝ 1日1本）。
        #     この下書きは**明日のぶん**で、きょう予約すると 2本 になります。
        out.append(f"     **きょう（{t:%m/%d} JST）の枠は、もう埋まっています**"
                   f"（{today_count(now=now, path=path)}本／規則1 ＝ **1日1本**・"
                   "`src/house_rule.py`）。")
        out.append("     → **この下書きは、きょうのぶんではありません。**"
                   "公開したら次の日の1本を作り始める（規則5「1日の回り方」）ので、"
                   "**これは明日のぶん**です。")
        out.append("     **きょうは予約しないこと。** 先の日付にも置かないこと（規則5）。"
                   "**きょうやるのは `improve` のほう**です —— "
                   "規則3「次の枠で出る1本を、出る瞬間まで良くし続ける」。")
        out.append(f"     **明日（{(t.astimezone(JST) + timedelta(days=1)):%m/%d} JST）に"
                   "なってから**、その日の枠へ（1本 50単位）:")
        out.append(f"       python scripts/reschedule.py --move {got[0].get('video_id')}"
                   f" {(t.astimezone(JST) + timedelta(days=1)):%Y-%m-%d}T20:00"
                   "   # **明日になってから撃つこと**")
        return out
    out.append("     **その日になったら、その日の枠へ入れること**（1本 50単位）:")
    out.append(f"       python scripts/reschedule.py --move {got[0].get('video_id')}"
               f" {t:%Y-%m-%d}T20:00")
    out.append("     **先の日付を書かないこと。** それまでは規則3 の対象です"
               "（次の枠で出る1本を、出る瞬間まで良くし続ける）")
    return out


def lines(now: datetime | None = None) -> list[str]:
    """画面へ出す行。**`improve` の当てどころを、fix と同じ形で毎周 出します。**"""
    # **暦を先に出すこと**（2026-09-01 夜）。下の `[次の枠]` は「次の1本」しか
    #     見ないので、**その1本の後ろが19日 空でも、この画面には一度も出ませんでした。**
    #     `improve` の当てどころより先に、**そもそも出る本が在るか**を見ます。
    cal = calendar_lines(now=now)
    cal = list(cal) + draft_lines(now=now)
    v = next_video(now=now)
    if not v:
        return cal + ["[次の枠] **予約が1本もありません。** `improve` は当てどころが無い回です"
                "（`python scripts/batch_build.py` で1本 作るか、"
                "池から戻すこと ＝ `python scripts/reschedule.py --move <videoId> <時刻>`）"]
    at = v["_at"].astimezone(JST)
    t = now or datetime.now(timezone.utc)
    hours = (v["_at"] - t).total_seconds() / 3600.0
    out = list(cal) + [
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
