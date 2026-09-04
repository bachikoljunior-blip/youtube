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
    # **完成音声を聞いて誤読を直し、音を焼き直す**（2026-09-03）。
    # 直った読みは `src/yomi.to_speech()` に載るので、**出来上がりの音が変わります。**
    "src/yomi_hear.py",
    # **分かりやすさの輪は、読み上げ本文そのものを書き換えます**（2026-09-03）。
    # 台本の narration が変われば、音も字幕も尺も変わる ＝ **出来上がりが変わります。**
    "src/clarity_loop.py",
    # **登録の依頼は、説明文の先頭に入ります**（2026-09-03 夜）。
    # `pipeline` は `sub_ask.with_head(description_body)` を通してから目次を組むので、
    # **上がる本の説明文そのものが変わります** ＝ 出来上がりを変える側。
    "src/sub_ask.py",
    # **絵の注文は、動画に入る絵を決めます**（2026-09-03 夜）。
    # `pipeline` が `image_orders.place()` で注文を置き、届いた絵が本に入る
    # （`docs/IMAGE_ORDERS.md`）。**入る絵が変われば出来上がりが変わります。**
    "src/image_orders.py",
)

#: **出来上がりを変えないので、上から外してあるもの**（検査が突き合わせます）。
#: `src/uploader.py` は**焼いたあとの運び方**で、出来上がりを作りません。
#: `src/analytics.py` は `pipeline._refill_topics()` の**題材の補充**だけ
#: （`analytics.optimize(posted)`）。**題材が決まったあとの中身は変えません。**
_NOT_MAKERS = ("src/analytics.py", "src/history.py",
               "src/uploader.py", "src/verify.py")


def _ahead_ok() -> bool:
    """**先の日付へ「いま」置けるか**（規則5）。**この文言を写さないこと。**

    出どころは `house_rule.may_schedule_ahead()` **1か所**です。ここまで、この
    ファイルは規則5 の本文を日本語で **4か所** 写していました（「明日になってから」
    「先の日付を書かないこと」…）。オーナーが床を外した 2026-09-04 17:3x のあとも
    写しは条件を持たないので **「待て」と言い続け**、`scripts/slot_gate.py` の
    「その日は投稿が途切れます ＝ いま置け」と正面から食い違っていました
    （実測 2026-09-05 05:2x・09/06 と 09/07 の予約が 0本）。
    """
    from src import house_rule                                  # noqa: PLC0415
    return house_rule.may_schedule_ahead()


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
    # **題は、上げた後に差し替わっていることがあります**（2026-09-05 00:2x に踏んだ）。
    # 帳面（`data/uploaded.jsonl`）の `title` は**上げたときの字**で、
    # `scripts/retitle.py` はそこへ書きません。重ねないと `[次の枠]` が古い題を刷ります
    # （実測 `GFvAcxvDmYM`: 23:03 に差し替えたのに、00:2x の `--write` は前の題を出していた）。
    # 実測と覆る条件は `src/retitles.py` の docstring。
    from src import retitles                                   # noqa: PLC0415

    return retitles.overlay(out)


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    s = str(ts).replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def latest_rows(path: Path | None = None) -> dict[str, dict]:
    """**1本の動画は1行**にたたむ（`{video_id: 勝った行}`）。**API 0単位。**

    ## なぜ「最後の行」ではいけないか（2026-09-02 に、撃って踏んだ）

    ここは長らく `latest[video_id] = r` の**素通し**でした ＝ **ファイルの最後の行が勝つ**。
    控えは1本につき1行ではありません（実測 854行 / 739本）—— `retime()` が行を足し、
    **きょうだいの回の merge が両方の行を残します。**

    **ファイルの並びは、時刻の順ではありません。** 実物 `DyEcaMK5ZU8`:

        508行目  at = 2026-10-10T00:00:00Z   retimed_at = 2026-08-26T07:**10**:57  ← 本物
        511行目  at = 2026-09-04T04:00:00Z   retimed_at = 2026-08-26T07:**08**:07

    **後ろの行のほうが、2分 古い。** 最後の行を採ると **09/04** を拾います ——
    そんな予約はありません（本物は 10/10）。実測でこう割れていました:

        python -m src.next_slot   [次の枠] **09/04 13:00 JST（あと 45時間）に出る1本**
        scripts/ahead_gate.py     先の日付の予約は **2026-09-24 〜 2026-10-10**（09/04 は無い）

    **`src/dupes._collapse()` は 2026-08-25 からこれを正しく解いています** ——
    「勝つ行は `retimed_at` がいちばん新しい行、無ければ最後の行」。
    `retimed_at` は **`videos.update` を通った側を言う唯一の手がかり**だからです。
    `scripts/status.py` / `scripts/slot_gate.py` / `scripts/ahead_gate.py` /
    `scripts/pool_drain.py` は全部そちらを読んでいて、**この file だけが別でした。**

    ## 何が壊れていたか

    `[次の枠]` は **`improve` の当てどころ**です（`lines()` の最後の行が
    「規則3 が言っているのはこの1本のことです」と書いています）。
    **主実行は、在りもしない枠に向かって規則3 を回していました** ——
    「あと 45時間」も、`swap_cost_lines()` の見積りも、その幻の上に乗ります。

    ## なぜ `dupes.ledger_rows()` を呼ばないか

    あちらは**読む先が固定**で、`path=` を受けません（検査が控えを差し替えます）。
    **目盛りだけ** `dupes._retime_key` から借りて、**規則の出どころは1か所**に保ちます。

    ## 覆る条件

    `retime()` が印を押さなくなったら、この関数は「最後の行」へ落ちます
    （`_retime_key` が両方 `(0, "")` を返すため）＝ **いまの素通しと同じ**。
    そのときは**印のほうを直すこと。**
    """
    try:
        from src.dupes import _retime_key                       # noqa: PLC0415
    except Exception:                                           # noqa: BLE001
        def _retime_key(row: dict) -> tuple:                    # noqa: ANN202
            stamp = row.get("retimed_at") or ""
            return (1 if stamp else 0, stamp)
    best: dict[str, dict] = {}
    for r in _rows(path):
        vid = r.get("video_id")
        if not vid:
            continue
        vid = str(vid)
        cur = best.get(vid)
        if cur is None or _retime_key(r) >= _retime_key(cur):
            best[vid] = r
    return best


def next_video(now: datetime | None = None,
               path: Path | None = None) -> dict | None:
    """**次に公開される1本**（`at` が未来で最小）。無ければ `None`。

    同じ `video_id` が控えに何度も出ます（`retimed_at` の書き戻し）。
    **`video_id` ごとにいちばん後ろの行**を採ること —— 前の行を採ると、
    予約を外した本（`at` が `null` に変わった本）を「次の1本」に出します。
    """
    t = now or datetime.now(timezone.utc)
    latest = latest_rows(path)
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


def legs_under_current_code(video_id: str, *, legs_call=None) -> list[str]:
    """**その本は、いまのコードでも脚を通るか。**（**API 0単位**・控えの台本だけ）

    ## なぜ要るか（2026-09-05 01:5x に、この回が実物で踏んだ）

    上の `[!]` は「焼いたあと、この本を焼くコードに N件 入っています ——
    **その直しは、この本に入っていません**」と言い、下は
    「→ **焼き直すのが `improve` の1手です**」と勧めます（**55〜90分**）。

    **その勧めは、コミットが在ることしか見ていません。** `_MAKERS` には
    `src/script_writer.py` が入っていて、そこには**焼く関数**と**脚を数える関数**が
    同居しています。**数える側だけが変わった回**は、焼き直しても1フレームも変わりません。

    実測（2026-09-05 01:2x にこの回が撃った数）::

        57bb8b84 09/04 22:42  外の型の脚 (4d) を帯 335本 で測り直した   ← 数える側
        daily_pick.pick_legs('GFvAcxvDmYM')  →  ([], None)             ← **新しい定義でも全通**

    ＝ **この本を焼き直して得られる脚は 0本**です。それでも画面は
    「その直しは、この本に入っていません」→「焼き直すのが `improve` の1手です」と
    並べていました。**55〜90分 と、枠の本の差し替え 100単位 の勧めです。**

    ここは**禁じません**（脚のほかにも焼き直す理由は在り得ます）——
    **数を1つ足すだけ**です。「入っていない」の下に「**で、いま通るのか**」を置きます。

    ## 覆る条件

    - `pick_legs` が読めない回は**1行も出しません**（推測で埋めない）。
    - 脚が落ちていれば、それはそのまま焼き直しの理由なので、そう印字します。
    - `_MAKERS` から `src/script_writer.py` が外れる（数える側が別 file へ出る）と、
      上の `[!]` はもう脚の話で鳴らなくなるので、**この行ごと畳むこと。**
    """
    vid = str(video_id or "").strip()
    if not vid:
        return []
    if legs_call is None:
        try:
            from . import daily_pick as _dp                      # noqa: PLC0415

            legs_call = _dp.pick_legs
        except Exception:                                        # noqa: BLE001
            return []
    try:
        bad, why = legs_call(vid)
    except Exception:                                            # noqa: BLE001
        return []
    if why:
        return []
    if bad:
        return [f"       [数] **いまのコードで数え直すと、この本は {len(bad)}脚 落ちています**"
                f"（{'・'.join(bad)}）—— **焼き直す理由が在ります。**"]
    return ["       [数] **ただし、いまのコードで数え直しても、この本は外の型の4脚を"
            "全部 通っています**（`daily_pick.pick_legs` ＝ `[]`）—— "
            "**焼き直して得られる脚は 0本**です。"
            "`_MAKERS` の `src/script_writer.py` には**焼く関数**と**脚を数える関数**が"
            "同居していて、上の N件 は**数える側だけ**かもしれません。"
            "**脚のほかに焼き直す理由を1つ持って来ること**（55〜90分・差し替え 100単位）。"]


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
        used = int(quota_ledger.used_units(now))
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
        used = int(quota_ledger.used_units(t))
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
        used = int(quota_ledger.used_units(t))
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
    latest = latest_rows(path)
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
        used = int(quota_ledger.used_units(t))
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
    latest = latest_rows(path)
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
    latest = latest_rows(path)
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


def _picked(day) -> dict | None:
    """`[きょうの1本]` で決めた本（`src/daily_pick.py`）。動画IDの無い決定は `None`。"""
    try:
        from . import daily_pick                                 # noqa: PLC0415
        cur = daily_pick.current(day)
    except Exception:                                            # noqa: BLE001
        return None
    return cur if cur and cur.get("video_id") else None


def picked_row(now: datetime | None = None,
               path: Path | None = None) -> dict | None:
    """`[きょうの1本]` で決めた本の控え（`data/uploaded.jsonl` の最後の行）。
    動画IDの無い決定・控えに無い本は `None`。**API 0単位。**"""
    try:
        from . import daily_pick                                 # noqa: PLC0415
        cur = _picked(daily_pick.for_day(now))
    except Exception:                                            # noqa: BLE001
        return None
    if not cur:
        return None
    row = latest_rows(path).get(str(cur.get("video_id")))
    if not row:
        return None
    return {**row, "_picked": cur}


def _config_hour() -> int:
    """機械が実際に置く時刻（`config/channel.yaml`）。**20 の直書きをやめた**（2026-09-02 夜）——
    同じ画面の `[きょうの1本]` が 09:00、ここが 20:00 と出て食い違っていた。"""
    try:
        from . import publish_hour                               # noqa: PLC0415
        h = publish_hour.config_hour()
        return int(h) if h is not None else 20
    except Exception:                                            # noqa: BLE001
        return 20


def _place_hour(day) -> int:
    """機械が実際に置く時刻 —— **正本は `publish_hour.place_hour`**（掃く側が先・次に既定）。

    2026-09-03 02:5x に踏んだ: ここが `_config_hour()`（9時）を直に読み、同じ画面の
    `[きょうの1本]`（`daily_pick._hour_default`）と機械（`ahead_sweep.place_hour`）は
    `sweep_hour()`（09/04 は 17時）を読んでいた。**同じ本の同じ `--move` が 09:00 と 17:00 で
    2回 刷られる形。** 順を3か所に書くのをやめ、ここは正本を呼ぶだけ。
    """
    try:
        from . import publish_hour                               # noqa: PLC0415
        return int(publish_hour.place_hour(day))
    except Exception:                                            # noqa: BLE001
        return _config_hour()


def _move_lines(got: list[dict], day, hour: int | None = None, note: str = "") -> list[str]:
    """その日の枠へ入れる `--move` の1行。**`[きょうの1本]` で別の本を決めてあれば、そちら**
    （2026-09-02 夜・最適化の回）—— 同じ画面が2つの本を名指しすると、次の回はどちらか
    を惰性で撃ちます。決めた本が下書きと違うとき、下書きは消さずに池へ残します。
    時刻は `_place_hour(day)`（機械が置く側と同じ数。9時 と 17時 が同じ画面に並んだ 09/03 の跡）。"""
    picked = _picked(day)
    hour = _place_hour(day) if hour is None else hour
    vid = str(got[0].get("video_id")) if got else ""
    # **置くのは機械です**（2026-09-02 夜・`scripts/ahead_sweep.place_today`）——
    # その日になった最初の SessionStart が、この本を その日の枠へ置きます。
    # 回が撃つのは「機械より先に置きたい」ときだけ（2度目は規則1 の関門で止まる・0単位）。
    auto = ("     　 **その日になれば機械が置きます**（`scripts/ahead_sweep.py` の `place_today`・"
            "SessionStart から背景で）。回が撃つ必要はありません —— 置かれていなければ"
            " `data/ahead_sweep.log` の `[today]` の行を見ること。")
    if picked and picked.get("video_id") != vid:
        pv = picked.get("video_id")
        return [
            f"     **{day:%m/%d} の1本は `[きょうの1本]` で {picked.get('form')} `{pv}` に"
            f"決めてあります**（理由: {str(picked.get('why'))[:60]}）:",
            f"       python scripts/reschedule.py --move {pv} {day:%Y-%m-%d}T{hour:02d}:00{note}",
            f"     　 下書き `{vid}` は**消さない**（private のまま池に残す）。",
            auto,
        ]
    return [f"       python scripts/reschedule.py --move {vid} {day:%Y-%m-%d}T{hour:02d}:00{note}",
            auto]


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
            # **規則5 の写しを持たないこと**（2026-09-05 05:3x に直した）。
            #     出どころは `house_rule.may_schedule_ahead()` 1か所。
            #     オーナーが床を外した（`OWNER_FLOORS_LIFTED`）あとも、ここは
            #     「明日になってから」と言い続けていました（`slot_gate.py` の
            #     「その日は投稿が途切れます」と正面から食い違う）。
            (f"     そして**明日（{(t + timedelta(days=1)):%m/%d}）の枠へ**"
             " `reschedule.py --move`。**いま置けます**"
             "（規則5 は外れています・`house_rule.may_schedule_ahead()`）。"
             if _ahead_ok() else
             f"     そして**明日（{(t + timedelta(days=1)):%m/%d}）になってから**"
             "、その日の枠へ `reschedule.py --move`。"
             "**先の日付には置かないこと**（規則5）。"),
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
        if _ahead_ok():
            out.append("     **きょうは予約しないこと**（規則1 ＝ 1日1本）。"
                       "**明日の枠へは、いま置けます**（規則5 は外れています・"
                       "`house_rule.may_schedule_ahead()`）—— "
                       "置いたら残りは規則3「次の枠で出る1本を、出る瞬間まで良くし続ける」。")
            out.append(f"     **明日（{(t.astimezone(JST) + timedelta(days=1)):%m/%d} JST）"
                       "の枠へ**（1本 50単位）:")
            out.extend(_move_lines(got, (t.astimezone(JST) + timedelta(days=1)).date()))
        else:
            out.append("     **きょうは予約しないこと。** 先の日付にも置かないこと（規則5）。"
                       "**きょうやるのは `improve` のほう**です —— "
                       "規則3「次の枠で出る1本を、出る瞬間まで良くし続ける」。")
            out.append(f"     **明日（{(t.astimezone(JST) + timedelta(days=1)):%m/%d} JST）に"
                       "なってから**、その日の枠へ（1本 50単位）:")
            out.extend(_move_lines(got, (t.astimezone(JST) + timedelta(days=1)).date(),
                                   note="   # **明日になってから撃つこと**"))
        return out
    out.append("     **その日の枠へ入れること**（1本 50単位）:")
    out.extend(_move_lines(got, t.date()))
    out.append("     **先の日付を書かないこと。** それまでは規則3 の対象です"
               "（次の枠で出る1本を、出る瞬間まで良くし続ける）"
               if not _ahead_ok() else
               "     残りは規則3 の対象です"
               "（次の枠で出る1本を、出る瞬間まで良くし続ける）。"
               "**先の日付にも置けます**（規則5 は外れています・"
               "`house_rule.may_schedule_ahead()`）")
    return out


def rebake_input_lines(video_id: str, topic: str) -> list[str]:
    """**同じ本を、1か所だけ変えて焼き直せるか。**（**API 0単位**）

    ## なぜ要るか（2026-09-02 に踏んだ）

    「焼き直す」には2つあり、**値段が桁で違います**:

        台本が控えに在る   `pipeline --script <台本> --topic <ID>`
                          → **同じ本**の、直した所だけが変わる
        台本が無い         `pipeline --topic <ID>`
                          → `claude -p` が**別の本を書き下ろす**（6〜11分）。
                            題も説明も一次コメントも入れ替わります

    `scripts/critique_queue.py` の画面は「焼直可」と出しますが、
    **あれは絵（`slides_plan.json`）のこと**で、本のことではありません。
    2026-09-02、09/03 に出す本の読みを2件 直したあと、
    **その直しを本へ入れる道がありませんでした。**

    台本を残す口は同じ日に足してあります（`critique_queue.stash()`）。
    **それより前に焼いた本には在りません** —— ここはそれを黙らせないためです。

    ## **控えの台本そのものが脚を落としているときは、`--script` は撃ってはいけません**

    （2026-09-05 04:5x に踏んだ。**この行が指すとおりに撃つと 90分 を捨てます**）

    `--script` は「**その台本のまま**焼き直す」ので、**台本の中身が原因の脚は1本も直りません。**
    2026-09-05 の実物: 09/05 09:00 の枠の `GFvAcxvDmYM` は控えの台本が
    **7,699字 ＝ 22.8分** で、外の帯の切れ目 25分 を **731字 割っています**
    （`pick_legs` → `['尺']`）。ここが刷っていたのは::

        python -m src.pipeline --script data/critique_queue/GFvAcxvDmYM.script.json --topic ...

    **その台本をそのまま焼くので、出てくるのは同じ 22.8分 の本です。**
    焼きは 55〜90分・差し替えは 100単位 かかって、脚は 1本も減りません。

    だから、**控えの脚が「台本の中身」で落ちているときは `--topic` だけの形**を刷ります
    （`claude -p` が書き下ろす ＝ 題・説明・一次コメントごと入れ替わる。
    上の表のとおり値段は桁で違いますが、**直らない焼き直しの値段は 100%** です）。

    **「台本の中身の脚」と「metadata の脚」の区別は既に在ります** ——
    `daily_pick.METADATA_LEGS` / `metadata_only()`。metadata だけが落ちているなら
    焼き直し自体が要らない（`METADATA_FIX_HOWTO`）ので、ここは
    **metadata 以外の脚が落ちているか**だけを見ます。

    ## 覆る条件

    - `--script` が欠けた欄を自分で埋めるようになったら、この行は要らなくなります。
    - 台本の一部だけを差し替えて焼き直す口（章を1つ足す等）ができたら、
      落ちた脚に応じてそちらを刷ること。**いまは「全部書き直す」しか在りません。**
    """
    if not video_id:
        return []
    path = ROOT / "data" / "critique_queue" / f"{video_id}.script.json"
    if path.exists():
        # **控えの台本そのものが落としている脚が在るか**（docstring の理由）。
        # 数えられなかった回（`why` が立つ回）は**黙って `--script` を刷らないこと** ——
        # 読めていない控えを「直す所は無い」と読むのが、この repo が何度も踏んだ形です。
        try:
            from . import daily_pick as _dp                        # noqa: PLC0415
            bad, why = _dp.pick_legs(video_id)
            body = [b for b in bad if b not in _dp.METADATA_LEGS]
        except Exception as exc:                                   # noqa: BLE001
            bad, why, body = [], f"脚を数えられませんでした（{str(exc)[:60]}）", []
        if body:
            return ["  [!] **`--script` で焼き直しても、この脚は1本も減りません** —— "
                    f"控えの台本そのものが落としています: **{'・'.join(body)}**。"
                    "`--script` は『**その台本のまま**焼き直す』ので、出てくるのは同じ本です"
                    "（焼き 55〜90分・差し替え 100単位 が、脚 0本 のために消えます）。",
                    "  **台本ごと書き下ろす焼き直し**（`claude -p`・6〜11分。"
                    "題・説明・一次コメントごと入れ替わります）:",
                    f"       python -m src.pipeline --topic {topic}"]
        if why:
            return [f"  [!] **控えの脚を数えられませんでした** —— {why}。"
                    "**数えられていない控えを『直す所は無い』と読まないこと。**"
                    "焼き直す前に、まず数えられるようにすること"]
        return [f"  **同じ本を焼き直せます**（控えに台本が在る・"
                f"**控えの脚は全通**なので `--script` で直せる所は台本の外に在ります）:",
                f"       python -m src.pipeline --script {path} --topic {topic}"]
    return ["  [!] **この本の台本は控えにありません** —— "
            "`python -m src.pipeline --topic ...` は**別の本を書き下ろします**"
            "（題・説明・一次コメントごと入れ替わる）。"
            "**「1か所だけ直して焼き直す」はできません。**",
            "       台本を残す口は 2026-09-02 に足してあります"
            "（`critique_queue.stash()`）—— **次に焼く本からは在ります。**"]


#: 段の内訳を数えるのに読む log の末尾の行数（`data/rebake.log` は追記だけ）。
#: いまの焼き 1本ぶんは 83コマ × 数行 ＝ 400行 前後なので、2,000行 あれば足ります。
BAKE_LOG_TAIL_LINES = 2000


def _bake_stage_span_lines(root=None) -> list[str]:
    """**いま焼いている本の、段ごとの分。**（`data/rebake.log` の `[+MM:SS]` から）

    **時刻の付いていない行しか無ければ、何も出しません** ——
    2026-09-04 17:1x より前の log は全部そうです（**推測で埋めないこと**）。
    """
    try:
        from scripts import ahead_sweep                        # noqa: PLC0415
    except Exception:                                          # noqa: BLE001
        return []
    raw: list[str] = []
    try:
        # **log が無い回もあります**（`data/rebake.log` は `.gitignore` 済みなので、
        #     枝を clone しただけの作業場には在りません）。**そこで黙らないこと** ——
        #     黙ると、この行が「出す作りになっているのに何も出ない」形になり、
        #     次の回は配線が死んでいるのか、まだ焼いていないのかを区別できません。
        path = Path(root or ROOT) / ahead_sweep.REBAKE_LOG
        raw = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        raw = []
    try:
        spans = ahead_sweep.stage_spans(raw[-BAKE_LOG_TAIL_LINES:])
    except Exception:                                          # noqa: BLE001
        spans = []
    if not spans:
        return ["       段ごとの分は**まだ出せません**（`data/rebake.log` の行に"
                " `[+MM:SS]` が付くのは 09/04 17:1x 以降の焼きから）"]
    body = " ／ ".join(f"**{k}** {v:.1f}分" for k, v in spans[:5])
    head = spans[0]
    # **その分の何割が「1行も刷っていない空き」かを、並べて言います**（2026-09-04 21:1x）。
    #
    # `stage_spans()` は空きを**直前の段**に付けます（そう決めてあり、正しい ——
    # 黙って働く段が在るため）。**その結果、黙っている別の段の時間も同じ所に乗ります。**
    # 実測（09/04 20:02 の焼き）: 「音声合成 28.0分（いちばん長い）」の **25.9分 ×2** は
    # 読み照合の聞き取り（whisper）で、**実物の音声合成は 2.0分**（82コマ・64は控えから）。
    # この行が無いと、**読んだ回は もう速い段を速くしようとします。**
    # 出どころと覆る条件は `ahead_sweep.SILENT_GAP_SEC` の註に。
    gap_lines: list[str] = []
    try:
        gaps = ahead_sweep.silent_gaps(raw[-BAKE_LOG_TAIL_LINES:])
    except Exception:                                          # noqa: BLE001
        gaps = []
    if gaps:
        tot = sum(g for g, _, _ in gaps)
        top = gaps[0]
        gap_lines = [
            f"       [!] **うち {tot:.1f}分 は「1行も刷っていない空き」です**"
            f"（{len(gaps)}件・{int(ahead_sweep.SILENT_GAP_SEC / 60)}分 超）。"
            f"**その分は、直前に喋った段の手柄ではありません** —— log には、"
            f"どの段の仕事か書いてありません。"
            f"いちばん長いのは {top[0]:.1f}分: `{top[1][:32]}` → `{top[2][:32]}`",
            "       → **速くする先をこの表から選ぶ前に、空きの側に刻を刷らせること**"
            "（刷れば、この行は自然に消えます）"]
    return [f"       段ごとの分（log の `[+MM:SS]` の差・API 0単位）: {body}",
            *gap_lines,
            f"       → **いちばん長いのは「{head[0]}」{head[1]:.1f}分**。"
            "**次に何を速くするかは、勘ではなくこの行で選ぶこと**"
            "（この 55〜90分 が、規則3 の焼き直しが 25回 中 1回 しか本にならない直の理由）"]


def machine_rebake_lines(video_id: str, now: datetime | None = None) -> list[str]:
    """**機械の側が、この本を焼き直すつもりか**（`ahead_sweep.rebake_plan_for()` の判定を写す）。

    ## なぜ要るか（2026-09-03 13:1x に実測。**朝から止まっていて、誰も気づきませんでした**）

    この画面は「焼いたのは 04:37 JST。そのあと 6件 入っています」と正しく言い、
    **手で撃つ1行**まで出していました。出していなかったのは
    **「機械はどうするつもりか」**です。実物はこうでした:

        [rebake] 2026-09-04 は焼き直しません —— 同じ台本（sha …）は一度 焼いた
        [rebake] 2026-09-05 は焼き直しません —— きょう既に 2回 焼いた（上限 2）

    **どちらも嘘**で（帳面に `done` は 0件・11:41 の `skip` が印と上限を食っていた）、
    **09/03 の焼き直しは 05:02 から 8時間 止まっていました。**
    掃きの `[rebake]` は `data/ahead_sweep.log` にしか出ないので、
    **`--write` だけを読む回（＝ 普通の回）からは見えません。**

    **「手で撃てます」と「機械が撃ちます」は別**です。前者だけを出していると、
    回は「機械がやるだろう」と読んで見送り、機械は黙って止まっています。

    **覆る条件**: `rebake_plan_for()` が重くなったら（いまは読むだけ・API 0単位）、
    掃きが最後に書いた判定を `data/rebake.jsonl` から読む形へ移すこと。
    """
    if not video_id:
        return []
    try:
        from scripts import ahead_sweep                        # noqa: PLC0415
    except Exception:                                          # noqa: BLE001
        return []
    t = (now or datetime.now(JST)).astimezone(JST)
    for day in (t.date(), t.date() + timedelta(days=1), t.date() + timedelta(days=2)):
        try:
            plan = ahead_sweep.rebake_plan_for(day, t)
        except Exception:                                      # noqa: BLE001
            continue
        if str(plan.get("video_id") or "") != video_id:
            continue
        if plan.get("do"):
            return ["  **機械も焼き直します**（次の掃きが背景で起こします・"
                    "`scripts/ahead_sweep.py`）—— 手で撃つと**同じ本が2本 上がります**"]
        # **「いま焼いている」を「もう焼いた」と混ぜないこと**（この註の実測がまさにそれ）。
        #     `rebake_attempted()` はどちらも True を返すので、帳面の最後の行で分けます。
        last = None
        for r in ahead_sweep._rebake_rows(None):
            if r.get("video_id") == video_id and r.get("sha") == plan.get("sha"):
                last = r
        # `beat` ＝ 焼く側が**錠を取った**印（`start` は決める側が spawn の前に書くだけ）。
        #     手で `--rebake-run` を撃った回は `start` を残さないので、`beat` が
        #     無いと、この行は前の回の時刻を出し続けます（2026-09-03 16:2x に実測）。
        if last is not None and last.get("kind") in ("start", "beat"):
            # **「起きた」と「まだ生きている」は別**（2026-09-03 15:5x に踏んだ）。
            #     `start` は決める側が spawn の前に書くので、器が回収されると
            #     **帳面には `start` だけが残り、この行は永久に「いま焼いています」と言い続けます。**
            #     錠（`flock`）は焼く側が死ねば OS が外すので、それが直接の証拠です。
            try:
                died = ahead_sweep.rebake_died(video_id, str(plan.get("sha") or ""), now=t)
            except Exception:                                  # noqa: BLE001
                died = False
            if died:
                # **ここに来た時点で `plan["do"]` は False です** —— `rebake_attempted()` が
                #     `rebake_died()` を先に見るので、「死んだから焼き直す」なら
                #     上の `plan.get("do")` で返っています（2026-09-04 に読み直した）。
                #     ＝ 焼き直しを止めているのは**死んだこと以外**（予約が付いている・
                #     きょうの上限・同じ sha）。**それを「機械は次の掃きで焼き直します」と
                #     言ってはいけません。** 言った回は、また見送ります。
                return [f"  [!] **前の焼きは {str(last.get('at'))[11:16]} JST に起きて、"
                        "`done` を残さずに終わっています**（器の回収）。"
                        "**いま走っているのは、この本ではありません**",
                        f"  [!] **機械は焼き直しません** —— {plan.get('why', '')}",
                        "       ＝ 直すか、手で撃つかは**この回が決めること**。"
                        "「機械がやるだろう」で見送らないこと（09/03 は 8時間 止まっていた）",
                        f"       python scripts/ahead_sweep.py --rebake-run {video_id} "
                        f"{plan.get('topic', '')} {plan.get('sha', '')}"]
            # **「走っている」と「終わる」は別**（2026-09-04 06:4x に数えて足した）。
            #     この行は長らく「いま焼いています → 手で撃たないこと」だけを出し、
            #     回はそれを読んで**その場で終わって**いました。器はその瞬間に
            #     回収され、焼く側も道連れです（`ahead_sweep.rebake_tally` の註）。
            #     実測 **start 21件 / done 0件** ＝ **一度も終わったことがありません。**
            #     待つ側にそれを言わないと、この形は永久に回り続けます。
            try:
                starts, dones = ahead_sweep.rebake_tally()
            except Exception:                                  # noqa: BLE001
                starts, dones = 0, 0
            out = [f"  **いま焼いています**（{str(last.get('at'))[11:16]} JST に起きた・"
                   "背景・log は `data/rebake.log`・帳面は `data/rebake.jsonl`）"
                   " —— **手で撃たないこと。同じ本が2本 上がります**"]
            # **log の末尾は 20分 古いことがあります**（`ahead_sweep.bake_stage` の註）。
            #     生きているかは `build/<題材>/` の mtime で見ること。
            try:
                stage = ahead_sweep.bake_stage(str(plan.get("topic") or ""))
            except Exception:                                  # noqa: BLE001
                stage = ""
            if stage:
                out += [f"       いまの段: {stage}",
                        "       **`data/rebake.log` が動いていないのを「死んだ」と読まないこと** ——"
                        " 子は 8KB ためるので末尾は最大 20分 古い。生死は `ps -o time= -p <pid>`（CPU 時間）で"]
            # **段ごとの分を出すこと**（2026-09-04 17:1x に足した）。
            #     `_run_out` の docstring は 09-03 から「**どの段が遅いか** …… いま誰も
            #     測れていません」と書いており、**25回 焼いても内訳を言えた回は 0回**でした。
            #     いま log の1行には `[+MM:SS]` が付くので、差を引けば段が出ます。
            #     **ここに出さないと、また誰も見ません**（この repo の
            #     「どこからも撃たれていない道具」の形）。
            out += _bake_stage_span_lines()
            # **待つ長さは、`done` が出たあとも出し続けること**（2026-09-04 08:2x に踏んだ）。
            #     この枝は長らく `dones == 0` の間だけ「何分 待てばいいか」を出し、
            #     `done` が 1件 出た瞬間に**一行の脚註へ落ちて**いました。
            #     ところが待つ側が要るのは「終わったことがあるか」ではなく
            #     **「あと何分 居ればいいか」**で、それは `done` が出てから初めて
            #     本物の数（78.2分）になります。**いちばん要る回で消える**作りでした。
            try:
                mins, n = ahead_sweep.bake_minutes()
            except Exception:                                  # noqa: BLE001
                mins, n = None, 0
            if mins and dones:
                how = f"**{mins:.0f}分 は要ります**（`data/rebake.jsonl` の `done` の実測 n={n}）"
            elif mins:
                how = (f"**{mins:.0f}分 は要ります**（**下限** ——"
                       f" 分かりやすさの輪の実測 n={n} ＋ 焼き。実測は 2.1倍 でした）")
            else:
                how = "何分かかるかは、まだ 1件も測れていません"
            if starts and dones == 0:
                out += [f"  [!] **焼き直しは これまで {starts}回 起きて、{dones}回 しか終わっていません。**"
                        "焼く側は**この器の中**の背景プロセスなので、"
                        "**この回が終わると道連れで死にます**（`ahead_sweep.rebake_tally` の註）",
                        f"       ＝ **この回は、終わるまで待つこと。**{how}。"
                        "`tail -3 data/rebake.log` を数分おきに見て、"
                        "`**差し替えました**` か `[!] 焼き直せませんでした` が出るまで居ること"]
            elif starts:
                out += [f"  [!] **焼き直しは これまで {starts}回 起きて、{dones}回 終わっています。**"
                        "焼く側は**この器の中**の背景プロセスなので、"
                        "**この回が終わると道連れで死にます**（`ahead_sweep.rebake_tally` の註）",
                        f"       ＝ **この回は、終わるまで待つこと。**{how}。"
                        "`tail -3 data/rebake.log` を数分おきに見て、"
                        "`**差し替えました**` か `[!] 焼き直せませんでした` が出るまで居ること"]
            return out
        return [f"  [!] **機械は焼き直しません** —— {plan.get('why', '')}",
                "       ＝ 直すか、手で撃つかは**この回が決めること**。"
                "「機械がやるだろう」で見送らないこと（09/03 は 8時間 止まっていた）"]
    return []


def lines(now: datetime | None = None) -> list[str]:
    """画面へ出す行。**`improve` の当てどころを、fix と同じ形で毎周 出します。**"""
    # **暦を先に出すこと**（2026-09-01 夜）。下の `[次の枠]` は「次の1本」しか
    #     見ないので、**その1本の後ろが19日 空でも、この画面には一度も出ませんでした。**
    #     `improve` の当てどころより先に、**そもそも出る本が在るか**を見ます。
    cal = calendar_lines(now=now)
    cal = list(cal) + draft_lines(now=now)
    v = next_video(now=now)
    # --- **予約が無い回でも、次に出る1本は在ります**（2026-09-02 に踏んだ）---
    #
    #     ここは長らく `next_video()`（＝ `at` が未来の行）だけを見ており、
    #     予約が1本も無い回に**こう出していました**:
    #
    #         [次の枠] **予約が1本もありません。** `improve` は当てどころが無い回です
    #
    #     **同じ画面の3行 上が、正反対を言っています**（`draft_lines()`）——
    #
    #         [下書き] 予約を付けずに上げてある本が 1本 あります　`MqQKSnbM0OI`
    #                **きょうやるのは `improve` のほう**です（規則3）
    #
    #     **規則5（固定その4「1日の回り方」）の下では、これが普通の状態です** ——
    #     「作るのは前の日から、**予約だけが当日**」なので、
    #     **次に出る1本は、その日が来るまで必ず `at` が空**です。
    #     つまりこの道具は、**規則5 が効いている間ずっと**
    #     「当てどころが無い」と言い続けます。
    #
    #     下にある材料（`stale_commits()` ＝ 焼いた後に入った直し／
    #     `pending_thumbnail()` ＝ 載っていないサムネ）は**そのまま使えます。**
    #     向ける先が居なかっただけです。
    #
    #     **実測（2026-09-02 16:3x）**: `data/runs.jsonl` の ship 305件 のうち
    #     `improve` は **9件（3%）**。その9件は**全部**、下書きではなく
    #     **予約ずみの本が在った 20時間の窓**（08/31 20:1x〜09/01 16:0x）に入っており、
    #     窓の外 192件 では **0件**。**当てどころが出ない回に improve は選ばれません。**
    #
    #     **覆る条件**: オーナーが規則5 を外して先の日付に予約できるようになったら、
    #     `next_video()` が常に本を返すので、この枝は自分で黙ります。
    draft = None
    if not v:
        got = drafts(now=now)
        draft = got[0] if got else None
        v = draft
    # --- **`[きょうの1本]` で別の本を決めてあれば、次に出る本はそちらです**（2026-09-02 20:xx）---
    #
    #     実測（09/02 20:26 の `--write`）: `[次の枠]` は下書きの `6GtzWaguZhg`（長尺）を
    #     名指しして「improve の当てどころは、この本です」と言い、その 6行 下の
    #     `[きょうの1本]` は 09/03 の1本を池の `DtpnSVFDtAE`（ショート・08/19 焼き）と
    #     言っていました。**同じ画面が2本を名指しし、`stale_commits()`（焼いた後に入った
    #     直し）と `pending_thumbnail()` は、出ない側の本で数えていました** ——
    #     出るほうの本は 08/19 焼きで、生成側の直し（読みの門・固定その3）が 1件も
    #     入っていないのに、画面は「そのあと生成側のコードは変わっていません」でした。
    #     `draft_lines()` の `--move` は 19:xx に決めた本へ揃えてあります（`_move_lines`）。
    #     **ここが揃っていませんでした。** 予約が実際に在る回（`next_video()` が返す）は
    #     予約が正で、決めのほうが古いので触りません。
    picked_from = None
    if v is not None and draft is not None:
        pk = picked_row(now=now)
        if pk and str(pk.get("video_id")) != str(v.get("video_id")):
            picked_from = str(v.get("video_id") or "")
            v = pk
    if not v:
        return cal + ["[次の枠] **予約が1本もありません。** `improve` は当てどころが無い回です"
                "（`python scripts/batch_build.py` で1本 作るか、"
                "池から戻すこと ＝ `python scripts/reschedule.py --move <videoId> <時刻>`）"]
    t = now or datetime.now(timezone.utc)
    if draft is None:
        at = v["_at"].astimezone(JST)
        hours = (v["_at"] - t).total_seconds() / 3600.0
        out = list(cal) + [
            f"[次の枠] **{at:%m/%d %H:%M} JST（あと {hours:.0f}時間）に出る1本**"
            f"　`{v.get('video_id')}`　{str(v.get('title') or '')[:44]}"
            f"　題材 `{v.get('topic')}`"
        ]
    else:
        out = list(cal) + [
            f"[次の枠] **予約はまだ在りませんが、次に出る1本はこれです**"
            f"（規則5 ＝ 作るのは前の日から、**予約だけが当日**）"
            f"　`{v.get('video_id')}`　{str(v.get('title') or '')[:44]}"
            f"　題材 `{v.get('topic')}`"
            + (f"　—— **`[きょうの1本]` で決めた本**（下書き `{picked_from}` は池に残す）"
               if picked_from else ""),
            "  **`improve` の当てどころは、この本です。**"
            "「予約が無い」は「当てどころが無い」ではありません。",
        ]
    # --- **形を先に**（2026-09-02 夜・最適化の回）: `src/daily_pick.py`（API 0単位）---
    #
    #     下の行は「improve するなら中身のほう（題・サムネ・台本・計算）」と、
    #     **中身の側だけ**を名指ししていました。同じ日に控えを齢48時間でそろえると
    #     ショート 中央値 173回 ／ 長尺 1回（1/173）で、**その1本がどの形かが
    #     `per_video` を 0単位 でいちばん大きく動かす手**です。形を決めずに磨いた
    #     長尺（09/01 22:00・improve 5件）は 20時間で 1再生 でした。
    #     **選択肢に無い手は選ばれません**（この file の冒頭と同じ理由）。
    try:
        from . import daily_pick                                 # noqa: PLC0415
        out.extend(daily_pick.lines(v, now=t))
    except Exception as exc:                                     # noqa: BLE001
        out.append(f"  [?] [きょうの1本] の数が出せませんでした（{exc}）—— "
                   "`python -m src.daily_pick` を手で撃つこと")
    built = _parse(v.get("uploaded_at"))
    cm = stale_commits(built, video_id=str(v.get('video_id') or '') or None)
    if built is None:
        out.append("  [?] **焼いた時刻が控えにありません**（`uploaded_at` が空）。"
                   "古さを数えられないので、中身を見て決めること")
    elif not cm:
        out.append(f"  焼いたのは {built.astimezone(JST):%m/%d %H:%M} JST。"
                   "**そのあと生成側のコードは変わっていません** ＝ "
                   "焼き直しても同じ物が出ます。**improve するなら中身のほう**"
                   "（題・サムネ・台本・計算）—— **ただし形は上の `[きょうの1本]` が先**")
    else:
        out.append(f"  [!] **焼いたのは {built.astimezone(JST):%m/%d %H:%M} JST。"
                   f"そのあと、この本を焼くコードに {len(cm)}件 入っています"
                   f"　—— その直しは、この本に入っていません**")
        for ln in cm:
            out.append(f"       {ln[:118]}")
        out.extend(legs_under_current_code(str(v.get("video_id") or "")))
        # **機械が焼く（か、いま焼いている）なら、手で撃つ1行を出さないこと**
        #     （2026-09-03 13:2x に実物で見た。この画面は
        #      「いま焼いています —— 手で撃たないこと。同じ本が2本 上がります」の**次の行**で
        #      「→ 焼き直すのが `improve` の1手です（`python -m src.pipeline` …）」と
        #      勧めていました。**同じ画面が、同じ本について逆のことを2行 並べて言う形**で、
        #      09/03 05:1x の回はこれで手と機械が同じ sha を焼き、片方を kill しています）。
        mrl = machine_rebake_lines(str(v.get("video_id") or ""), now)
        machine_has_it = any(("いま焼いています" in ln) or ("機械も焼き直します" in ln)
                             for ln in mrl)
        if not machine_has_it:
            out.extend(rebake_input_lines(str(v.get("video_id") or ""),
                                          str(v.get("topic") or "")))
        out.extend(mrl)
        if machine_has_it:
            out.append("  → **この本の `improve` は、いま機械の側で進んでいます。**"
                       "終わったか（`**差し替えました**` の行）は `data/rebake.log` の末尾。"
                       "**触ってはいけないのは narration だけです**"
                       "（音声がもう合わせて合成ずみ）。当てどころ: "
                       "**題・説明・絵・次の日の1本・道具**")
            # **題は焼き直さずに直せます。ただし `build/` へ書くのではありません**
            # （2026-09-04 20:3x に「`build/` へ書けば入る」と書き、21:3x に実測で外れました）。
            #
            #     20:21  `build/…/script.json` の `title` を入れ替えた
            #     21:00  `ls -l` → **20:21 のまま。残っている**（ここで「効いた」と書いた）
            #     21:30  投稿。**mtime が投稿の時刻に上がっていた** ＝ 焼く側が
            #            **投稿の直前に丸ごと書き戻す**。上がったのは古い題
            #
            # ＝ **途中で見て「残っている」のは、何の証拠にもなりません。**
            # 正しい道は、焼き上がってから `scripts/metadata_fix.py <新ID>`（50単位・数秒）。
            # 手順と覆る条件は `docs/trigger_main.md` §4 の同じ見出しに。
            out.append("     **題・サムネは、焼き上がってから直せます**（焼き直し 0回・数秒）: "
                       "`data/scripts/<題材>.script.json` を直し（**ここは書き戻されません**）、"
                       "新しい ID が出たら `python scripts/metadata_fix.py <新ID>`（50単位）→ "
                       "`daily_pick.pick_legs('<新ID>')` が `[]` になることを見る。"
                       "[!] **焼いている最中の `build/…/script.json` へ書かないこと** —— "
                       "焼く側が投稿の直前に丸ごと書き戻します（09/04 21:3x に実測。"
                       "途中の `ls -l` で残っていても、証拠になりません）")
        elif draft is None:
            out.append("  → **焼き直すのが `improve` の1手です**"
                       "（`python -m src.pipeline` で焼き直し、"
                       "`scripts/reschedule.py --unschedule <古い方>` →"
                       " 新しい方を同じ枠へ `--move`）")
            out.extend(swap_cost_lines(t, publish_at=v["_at"]))
        else:
            # **下書きには外す枠がありません。** `--unschedule` は撃てません
            #     （予約が無い本に撃つと空振りします）。焼き直したら
            #     `--draft` でもう1本 上げて、**古いほうを池に残す**だけです。
            out.append("  → **焼き直すのが `improve` の1手です**"
                       "（`python -m src.pipeline` で焼き直し → "
                       "`python scripts/upload_only.py <題材> --draft`）。"
                       "**`--unschedule` は要りません**（この本には外す枠がありません）。"
                       + ("予約は `--move` で（**先の日付にも置けます** ——"
                          " 規則5 は外れています）。" if _ahead_ok()
                          else "予約は**その日になってから** `--move` で。"))
    if pending_thumbnail(str(v.get("video_id") or "") or None):
        out.append("  [!] **サムネイルの bytes は控えに在りますが、YouTube に"
                   "載っていません**（`thumbnail_set: false`）。"
                   "**この1本だけなら 50単位**:")
        out.append("       python scripts/refresh_thumbnail.py --missing "
                   f"--video {v.get('video_id')}")
        out.append("       （`--missing` だけだと実測 158本 ＝ **7,900単位** で、"
                   "`pool_drain` と枠を取り合います）")
        if draft is None:
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
