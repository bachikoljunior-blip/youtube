r"""**止まっていたら、床を待たずに動かす**（2026-09-14 22:0x・optimizer-sub・Opus）。

オーナー原文（2026-09-14 19:44 JST・受け取り帳 `6df66dd7`・**一字も変えないこと**）:

> **「3分ごとに停止を確認していたら原因を全て潰してから再実行するようにして出せるまでやって」**
> **「停止を確認したら、ね」**

言われた当の停止は **09/14 17:16 → 20:07 JST の 2.85時間**（口 `YT_REFRESH_TOKEN` が Google に
拒まれ、`status`／`measure`／`schedule` が全部 止まった）。**戻したのはオーナーの手**
（「いれたよ」20:1x）で、こちら側には「止まっている」と言う口も、床を待たずに立て直す口も
1つもありませんでした。

## **何をもって停止とするか（数で決めた）**

**印は全部 台帳から数えます（API 0単位）。** 数えた分母と、越えた数:

    (A) `mouth_gap`   口が開いた印（`channel`。`status` が毎周 いちばん先に書く）が空いた窓。
                      **分母 142窓**（3分 以上・`data/studio/ledger.jsonl` の 259行）:
                      時間は 中央値 **0.61h**・p90 **0.93h**・最大 **2.85h**、
                      窓の中に始まった周は **1周 が 123窓・0周 が 17窓・2周 が 2窓**。
                      門は **2つ のどちらか**（`STALL_MOUTH_H = 2.0h`・`STALL_MOUTH_LAPS = 2周`）:
                      時間の門は p90 の 2.15倍 で **越えたのは 1窓**（09/14 の当の停止）、
                      周の門に当たるのは **2窓**（09/11・09/13 ＝ どちらも (C) の盲の周）。
                      ＝ **142窓 中 3窓（2.1%）で、その 3つ が知っている停止の全部**
                      （**それ以外に 1つも立ちません** ＝ 陽性対照）。
                      **時間だけで持たない**のは、周そのものが伸びれば（床は枠から決まる）
                      時間の門は毎周 鳴るからです —— 周は実測 中央値 0.92h・p90 2.02h。
                      潰すのはオーナーの手（環境変数）＝ `owner=True`
    (B) `token_rejected` いちばん新しい `token_rejected` が いちばん新しい `channel` より後
                      （`trend.mouth_closed_line` と同じ数え方）。実測 **1行**（09/14 19:12）。
                      `owner=True`
    (C) `blind_lap`   **終わった周**の窓に台帳の行が **0行**。分母 **127周**（最初の `channel` 以降）で
                      **2周（1.6%）**—— 09/11 18:00 と 09/13 23:49 で、どちらも入れ物の
                      立て直しでサブが落ちた周（`cli.empty_slot_mark` の註が名指ししている当の周）。
                      潰すのは立て直し ＝ **機械の側**（`owner=False`）
    (D) `slot_missed` きょうの日付の `publish_at` を持つ `pending`／`scheduled` が台帳に 1行も無く、
                      いま `SLOT_AT`（10:00）を過ぎている ＝ **その日は 1本も出ません**。
                      実測 09/08〜09/15 の **8日 とも 0件**（この印はまだ 1度も立っていない）。
                      潰すのは `build` → `schedule` ＝ **機械の側**（`owner=False`）

**停止 ＝ (A)(B)(C)(D) のどれかが立っている周。**

## **「原因を全て潰してから再実行」の読み（決めた読みと、覆る条件）**

オーナーの「3分ごと」は**確認**の間隔です（確認は台帳だけ ＝ 0単位・いつでも撃てる）。
だからこの機構は:

    確認   毎周・0単位。`cli.main()` が**どの cmd でも、口を撃つ前に**印を全部 並べる
           （口が閉じている周でも読めます ＝ `cmd_status` の中に置くと `yt.channel()` で死ぬ）
    再実行 停止を確認した周は、通常の間隔（床 91分）を待たずに **`RETRY_MIN = 3分` 後**に
           起こしを置く（`next_round.decide()` が `floor` を下げる）。**上げる側には動きません。**
    輪の出口 `shippable()` ＝ 口が開いていて（`channel` が 2.0h 以内）、かつ
           **次の公開の枠に本が在る**（未来の `publish_at` を持つ `pending`／`scheduled`）。
           これが「出せる」です（オーナー「出せるまでやって」）。

**3分 を使うのは「機械が潰せる原因」が 1つでも在る周だけです**（`owner=False` の印）。
口（(A)(B)）しか立っていない周は、**3分 で立て直しても 1ミリも潰せません**
—— 実測の 2.85時間 は最後までオーナーの手でしか開かず、そこへ 3分 ごとに周を立てれば
枠を食って **31時間 止まる**側（`next_round.decide()` の 09/03 の節）へ倒れます。
だからその周は**床のまま**で、置くのは訊き（`python scripts/owner_ask.py`）です。
**これは「止める仕掛け」ではありません** —— 周は床で立ち続けます（`CLAUDE.md` 2026-08-31）。

**`RETRY_LAPS_CAP = 8周`**（＝ 3分 × 8 ＝ 24分）で 3分 は床へ戻ります。実測の盲の周は
**2周 とも 1周 で戻っている**ので、8周 かけて戻らないなら**潰せる原因だという読みが
間違っています**（オーナー 09/14 20:3x「できる以外の判断をしたなら やり方が間違ってることを
疑え」の当の形）。そのときは印字が「読みが外れました」と名指しします。

**覆る条件**:
 (1) `mouth_gap` が**停止でない周**で立ったら（＝ 口は開いているのに門に当たった）、
     当たった側を見ること。時間の側なら **`STALL_MOUTH_H` を捨てて周の数だけで持つ**
     （周の p90 は 2.02h なので、床が伸びれば時間の門は毎周 鳴ります ——
      そのときに残るのは周の側です）。周の側なら `STALL_MOUTH_LAPS` を 3 へ。
 (2) `slot_missed` が 1度も立たないまま 30日 過ぎたら、その印は分母 0 のまま育っています
     ＝ 落とすか、立つ条件を数え直すこと（`src/alerts.py` の「当たりを含まないまま育つ」）。
 (3) 3分 の周が **8周 の上限に 2回 当たったら**、足りないのは速さではなく潰し方の側
     ＝ その原因の潰し手を `crush` の文言ではなく**機械**にすること。
 (4) `channel` を書く口が `status` 以外にも増えたら (A) の分母が変わります ＝ 数え直すこと。

derivation は `docs/JOURNAL.md` 2026-09-14 22:xx JST。
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from . import budget
from .common import JST, ROOT, ledger_rows, now_jst

ROUNDS_JSONL = ROOT / "data" / "rounds.jsonl"

#: 口が開いた印（`channel`）が空いてよい時間。p90 0.93h の 2.15倍（上の (A)）。
STALL_MOUTH_H = 2.0
#: その窓の中に始まってよい周の数。**2周 に当たるのは実測 2窓 だけ**（上の (A)）。
STALL_MOUTH_LAPS = 2
#: 停止を確認した周が、次の周までに待つ分（オーナーが観察した確認の間隔）。
RETRY_MIN = 3.0
#: 3分 を使い続けてよい周の数。越えたら床へ戻る（読みが外れた合図・上の (3)）。
RETRY_LAPS_CAP = 8
#: きょうの枠の刻。**`cli.SLOT_AT` の写しを持たないこと** —— 読めなければこの既定。
_SLOT_FALLBACK = "10:00"


def _at(row: dict) -> dt.datetime | None:
    s = row.get("at")
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s).astimezone(JST)
    except Exception:                                          # noqa: BLE001
        return None


def _rows_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except Exception:                                  # noqa: BLE001
                pass
    return out


def _slot_at() -> str:
    """枠の刻を `cli.SLOT_AT` から 1か所で読む（写しを持たない・§5 の教訓 7つ目）。"""
    try:
        from . import cli                                      # noqa: PLC0415
        return str(cli.SLOT_AT)
    except Exception:                                          # noqa: BLE001
        return _SLOT_FALLBACK


def lap_starts(rounds: list[dict] | None = None) -> list[dt.datetime]:
    """記録された周の始まり（`data/rounds.jsonl` の `round` を重複なく・古い順）。

    **役では数えません**（1周に何体 立っても 1周）——`trend.mouth_closed_line` と同じ数え方。
    """
    rounds = _rows_jsonl(ROUNDS_JSONL) if rounds is None else rounds
    keys = {r.get("round") or r.get("at") for r in rounds if (r.get("round") or r.get("at"))}
    out = []
    for k in keys:
        try:
            out.append(dt.datetime.fromisoformat(k).astimezone(JST))
        except Exception:                                      # noqa: BLE001
            pass
    return sorted(out)


def _future_slot(rows: list[dict], now: dt.datetime) -> dt.datetime | None:
    """台帳が知っている「次の公開」（未来の `publish_at` のいちばん早いもの）。"""
    out = []
    for r in rows:
        if r.get("event") not in ("pending", "scheduled"):
            continue
        p = r.get("publish_at")
        if not p:
            continue
        try:
            at = dt.datetime.fromisoformat(p).astimezone(JST)
        except Exception:                                      # noqa: BLE001
            continue
        if at > now:
            out.append(at)
    return min(out) if out else None


def _todays_slot_filled(rows: list[dict], now: dt.datetime) -> bool:
    """きょうの日付の `publish_at` を持つ行が 1つでも在るか（(D) の分子）。"""
    today = now.date()
    for r in rows:
        if r.get("event") not in ("pending", "scheduled"):
            continue
        p = r.get("publish_at")
        if not p:
            continue
        try:
            if dt.datetime.fromisoformat(p).astimezone(JST).date() == today:
                return True
        except Exception:                                      # noqa: BLE001
            pass
    return False


def signs(rows: list[dict] | None = None, rounds: list[dict] | None = None,
          now: dt.datetime | None = None) -> list[dict]:
    """**停止の印を、数と一緒に全部 返す**（API 0単位・台帳だけ）。

    1つの印 ＝ `{code, words, crush, owner, since}`。`owner=True` は
    「**その周に 3分 を使わない**」側（上の読み）。**「オーナーの手が要る」とは同じではありません** ——
    `mouth_gap` は `dry`（きょうの日枠を使い切った）のとき `owner=True` のまま
    **「オーナーの手は要りません・16:00 JST に戻ります」**と言います（2026-09-16 04:3x・`dry` の枝の註）。
    """
    rows = ledger_rows() if rows is None else rows
    now = now or now_jst()
    laps = lap_starts(rounds)
    out: list[dict] = []

    ch = sorted(x for x in (_at(r) for r in rows if r.get("event") == "channel") if x)
    rej = sorted(x for x in (_at(r) for r in rows if r.get("event") == "token_rejected") if x)

    # (A) 口が開いた印が空いた（**時間 か 周の数 のどちらか**・上の (A)）
    if ch:
        gap = (now - ch[-1]).total_seconds() / 3600.0
        inside = len([x for x in laps if x > ch[-1]])
        if gap >= STALL_MOUTH_H or inside >= STALL_MOUTH_LAPS:
            # **日枠を先に見る**（2026-09-16 04:2x・optimizer・Fable 5.1・ultracode）。
            #   `channel` を書くのは `status` だけで、`status` は **日枠が尽きた周には撃てません**（403）。
            #   ＝ この印は「口が壊れた」と「きょうのぶんを使い切った」を**同じ字**で出していました。
            #   実際この周（09/16 03:3x）に立ち、潰し手として **`YT_REFRESH_TOKEN` の取り直し ＝ オーナーの手**
            #   を名指しました。**口は壊れていません**（台帳に 09/15 16:00 から 8,979/10,000）。
            #   オーナーへの訊きは数が限られている側なので、**偽の 1件 の値段が高い**（GOAL (4-a)）。
            #   **印は消しません**（口は実際に閉じている）—— 変えるのは **owner** と **潰し手**だけ。
            #   **覆る条件**: (1) 日枠が余っているのに `status` が 403 で落ちる周が出たら、
            #   分けているものが違う ＝ そのときは `budget` ではなく `token_rejected` の側で読むこと。
            #   (2) `budget.spent` は**過小**（`budget` の覆る条件 (1)）なので、
            #   「余っている」と言われても落ちることがあります ＝ この枝は「尽きている」側にしか効かせないこと。
            # **推計ではなく、落ちた事実で読む**（`cli.quota_exceeded` の註）——
            #   この周の `budget.spent` は 1,021単位 余っていると言い、それでも `status` は 403 でした
            #   ＝ 台帳に `units` を書かない口の分だけ過小（`budget` の覆る条件 (1)）。
            #   見るのは「いまの日枠の窓の中で、いちばん新しい `channel` より後に `quota_exceeded` が在るか」。
            spent = budget.spent(rows, now)
            head = budget.window_start(now)
            qx = sorted(x for x in (_at(r) for r in rows if r.get("event") == "quota_exceeded") if x)
            dry = bool(qx) and qx[-1] >= head and qx[-1] > ch[-1]
            if dry:
                nxt = budget.window_start(now) + dt.timedelta(days=1)
                crush = (f"**口は壊れていません** —— きょうの日枠を使い切っています"
                         f"（{spent['total']:,}/{budget.DAY_UNITS:,}・残り {spent['left']:,}）。"
                         f"戻るのは **{nxt:%m/%d %H:%M} JST**。**オーナーの手は要りません**（訊きを置かないこと）。"
                         f"それまでは台帳だけで撃てる仕事（`trend`・`critique`・`build`・`hear`・`demand`）へ回すこと")
            else:
                crush = ("`YT_REFRESH_TOKEN` を取り直す ＝ **オーナーの手**"
                         "（`python scripts/owner_ask.py` に訊きを置く）。"
                         "こちらは台帳だけで撃てる仕事（`trend`・`critique`・`build`）へ回すこと")
            out.append({
                # **`owner` は `True` のまま**（2026-09-16 04:3x に踏んで戻した）——
                #   `owner=False` にしたら `crushable` に入り、印字が
                #   「床を待たずに **3分** 後に再実行（上限 8周）」へ変わりました。
                #   **日枠は 3分 では戻りません（16:00 JST まで 12時間）** ＝ 8周 撃っても 1ミリも潰せず、
                #   この module の冒頭が警告している当の形（「枠を食って 31時間 止まる側へ倒れます」）。
                #   ＝ **`owner` が持っているのは「その周に 3分 を使うか」**で、
                #   **「オーナーに訊きを置くか」は `dry` が持ちます**（`crush` の文がそう言う）。
                #   **覆る条件**: 3つ目の状態（潰せるが、いますぐではない）を持つ印が 2つ目 出たら、
                #   `owner` の bool を捨てて `when`（`now`／`later`／`owner`）にすること。
                "code": "mouth_gap", "since": ch[-1], "owner": True, "dry": dry,
                "words": (f"口が開いた印（`channel`）が **{gap:.2f}h・その間に始まった周 {inside}周** "
                          f"空いています（門 {STALL_MOUTH_H:.1f}h か {STALL_MOUTH_LAPS}周 ＝ "
                          f"実測 142窓 中 3窓 だけが当たり、その 3つ が知っている停止の全部）"
                          + ("・**ただし日枠が尽きています**（下）" if dry else "")),
                "crush": crush,
            })

    # (B) 口が拒まれた（`channel` より後ろに `token_rejected` が在る）
    if rej and (not ch or rej[-1] > ch[-1]):
        first = min(r for r in rej if not ch or r > ch[-1])
        out.append({
            "code": "token_rejected", "since": first, "owner": True,
            "words": (f"口（`YT_REFRESH_TOKEN`）が拒まれた行が、いちばん新しい `channel` より"
                      f"後ろに在ります（{first:%m/%d %H:%M} JST・"
                      f"{(now - first).total_seconds() / 3600.0:.2f}h 前）"),
            "crush": ("同上（口の取り直し ＝ オーナーの手）。"
                      "`trend.mouth_closed_line` が門 3周 を数えています"),
        })

    # (C) 盲の周（終わった周の窓に台帳の行が 0行）
    led = sorted(x for x in (_at(r) for r in rows) if x)
    if len(laps) >= 2 and led:
        start, end = laps[-2], laps[-1]
        if start >= led[0] and not [x for x in led if start <= x < end]:
            out.append({
                "code": "blind_lap", "since": start, "owner": False,
                "words": (f"直前に終わった周（{start:%m/%d %H:%M} → {end:%m/%d %H:%M} JST）の窓に、"
                          f"台帳の行が **0行** ＝ その周は 1つも撃てていません"
                          f"（実測 127周 中 2周・1.6%）"),
                "crush": ("**その周を立て直す**（入れ物の立て直しでサブが落ちた側 ＝ 実測 2周 とも"
                          "次の 1周 で戻っている）。3分 後に起こしを置くこと"),
            })

    # (D) きょうの枠が空のまま刻を過ぎた
    hh, mm = (int(x) for x in _slot_at().split(":"))
    slot = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if now > slot and not _todays_slot_filled(rows, now):
        out.append({
            "code": "slot_missed", "since": slot, "owner": False,
            "words": (f"きょう（{now:%m/%d}）の `publish_at` を持つ行が台帳に 1つも無いまま "
                      f"{_slot_at()} を過ぎました（いま {now:%H:%M}）＝ **きょうは 1本も出ません**"
                      f"（実測 8日 とも 0件 ＝ この印は 1度目です）"),
            "crush": "`build` → `schedule --at <次の枠>`（当日だけ・§5 の表）",
        })
    return out


def shippable(rows: list[dict] | None = None, now: dt.datetime | None = None,
              rounds: list[dict] | None = None) -> tuple[bool, str]:
    """**「出せる」の判定**（オーナー「出せるまでやって」の出口）。API 0単位。

    口が開いていて（(A) の門 —— 時間も周の数も越えていない）、かつ
    次の公開の枠に本が在る（未来の `publish_at` を持つ `pending`／`scheduled`）。
    **門は (A) と同じ 1か所を読みます**（写しを持たない ＝ 片方だけ動くと輪が閉じません）。
    """
    rows = ledger_rows() if rows is None else rows
    now = now or now_jst()
    ch = sorted(x for x in (_at(r) for r in rows if r.get("event") == "channel") if x)
    gap = None if not ch else (now - ch[-1]).total_seconds() / 3600.0
    inside = 0 if not ch else len([x for x in lap_starts(rounds) if x > ch[-1]])
    nxt = _future_slot(rows, now)
    if gap is None or gap >= STALL_MOUTH_H or inside >= STALL_MOUTH_LAPS:
        return False, ("口が開いていません"
                       + ("（`channel` の行が 1つもありません）" if gap is None
                          else f"（`channel` から {gap:.2f}h・その間の周 {inside}周）"))
    if nxt is None:
        return False, "次の公開の枠が空です（未来の `publish_at` を持つ行が台帳にありません）"
    return True, (f"口は開いていて（`channel` から {gap:.2f}h）、"
                  f"次の公開は {nxt:%m/%d %H:%M} JST ＝ **出せます**")


def state(rows: list[dict] | None = None, rounds: list[dict] | None = None,
          now: dt.datetime | None = None) -> dict:
    """**停止の姿と、この周の再実行の間隔**（API 0単位）。

    返り:
        stalled     印が 1つ以上 立っているか
        signs       `signs()` の返り
        since       いちばん古い印の刻（＝ 停止が始まった刻）
        laps        その刻より後に立った周の数（3分 を使った周の数）
        retry_min   この周が待つ分（`RETRY_MIN` か None ＝ 床のまま）
        why         なぜその間隔か（1行）
        shippable   「出せる」か（`shippable()`）
    """
    rows = ledger_rows() if rows is None else rows
    now = now or now_jst()
    sg = signs(rows, rounds, now)
    ok, words = shippable(rows, now, rounds)
    out: dict = {"stalled": bool(sg), "signs": sg, "since": None, "laps": 0,
                 "retry_min": None, "why": "", "shippable": ok, "ship_words": words}
    if not sg:
        out["why"] = "停止の印はありません（床のまま）"
        return out
    since = min(s["since"] for s in sg)
    out["since"] = since
    out["laps"] = len([x for x in lap_starts(rounds) if x > since])
    crushable = [s for s in sg if not s["owner"]]
    if not crushable:
        # **`dry`（日枠を使い切った）の印が在る周は、「訊きを置く」と言わないこと**
        #   （2026-09-16 04:3x）—— `crush` の行が「オーナーの手は要りません」と言っている隣で
        #   この行が「訊きを置く」と言えば、**同じ周が自分と食い違います**（撃って踏んだ）。
        #   3分 を使わない点は同じなので、変えるのは文だけです。
        if any(s.get("dry") for s in sg):
            out["why"] = ("潰せる原因が機械の側に 1つもありません（**きょうの日枠を使い切っています**）"
                          " ＝ **床のまま・訊きは置かない**（戻るのは 16:00 JST。3分 で撃ち直しても"
                          "日枠は 1単位 も戻らず、枠を食って 31時間 止まる側へ倒れます）")
            return out
        out["why"] = ("潰せる原因が機械の側に 1つもありません（口はオーナーの手）"
                      " ＝ **床のまま・訊きを置く**（3分 で立て直しても 1ミリも潰せず、"
                      "枠を食って 31時間 止まる側へ倒れます）")
        return out
    if out["laps"] >= RETRY_LAPS_CAP:
        out["why"] = (f"3分 の周が **{out['laps']}周**（上限 {RETRY_LAPS_CAP}周）＝ **床へ戻します**。"
                      "実測の盲の周は 2周 とも 1周 で戻っているので、"
                      "**「潰せる原因だ」という読みが外れています**"
                      "（`stall.py` の覆る条件 (3)・オーナー 09/14 20:3x）")
        return out
    out["retry_min"] = RETRY_MIN
    out["why"] = (f"潰せる原因が {len(crushable)}件 在ります"
                  f"（{'・'.join(s['code'] for s in crushable)}）"
                  f" ＝ 床を待たずに **{RETRY_MIN:.0f}分** 後に再実行"
                  f"（停止から {out['laps']}周・上限 {RETRY_LAPS_CAP}周）")
    return out


def lines(rows: list[dict] | None = None, rounds: list[dict] | None = None,
          now: dt.datetime | None = None) -> list[str]:
    """**印字する行**（停止していなければ空 ＝ 立たない回は 1字も足さない）。"""
    st = state(rows, rounds, now)
    if not st["stalled"]:
        return []
    out = [f"!! **停止を確認しました**（印 {len(st['signs'])}件・"
           f"{st['since']:%m/%d %H:%M} JST から {st['laps']}周）"
           f" —— オーナー `6df66dd7`「3分ごとに停止を確認していたら原因を全て潰してから"
           f"再実行するようにして出せるまでやって」"]
    for i, s in enumerate(st["signs"], 1):
        out.append(f"   ({i}) [{s['code']}] {s['words']}")
        out.append(f"       潰す: {s['crush']}")
    out.append(f"   間隔: {st['why']}")
    out.append(f"   出せるか: {st['ship_words']}")
    return out
