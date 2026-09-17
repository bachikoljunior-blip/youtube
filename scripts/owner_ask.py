#!/usr/bin/env python3
"""**オーナーの手が要る問いが、何周 待っているか**（API 0単位・repo の字だけ）。

    python scripts/owner_ask.py

**なぜ置いたか**（2026-09-14 02:5x JST・`hourly`・Opus）:
`docs/GOAL.md` の達成期限の節（2026-09-13 21:0x・`hourly` の判定）は、覆る条件 (4) に
**「この訊きに 3周 返事が無かったら、返事は来ない前提で 1 の側だけを進めること」**と書きました。
**その 3周 を数える口が、どこにもありませんでした** —— この repo でいちばん多い壊れ方
（「N回 続いたら」と書いて N を数える物が無い）の族で、`owner_words`・`views_streak`・
`late_run`・`blind_run`・`turf_run` と同じ形です。

**実害が出ています**: (4) は **09/13 23:49 の周で引かれていました**（訊きの 3周 後）。
そこから **3周**（00:46・01:46・02:41）、`hourly` も `optimizer` も気づかずに流れています ——
引かれた条件は、誰かが日付を手で引き算した回にしか見えません。

**数え方**:

    周        `data/rounds.jsonl` の `round`（無い古い行は `at`）を重複なく並べ、
              訊きの刻より後のものを数える。**役では数えません**（2体 で 1周）。
    返事      `data/inbox.jsonl` の `source: "owner"` のうち、訊きの刻より後のもの。
              **中身は見ません** —— オーナーが何か言ったら、それが正本（§5）＝
              **その言葉をその周が読んで、答えかどうかを判定する**。
    引かれる   周 ≧ 門（3）かつ 返事 0件。**返事が 1件でも来たら、この門は消えます**
              （引くのではなく、**その言葉のほうが正本**になる）。

**17つ目の教訓（引いたあとに残る側を数えること）**: 引かれたあとにこの道具が数えるのは
**周の数ではなく「まだ返事の無い問いが何件 あるか」**です。引かれた問いは
`**引かれました**` と 1行 で言い、**もう一度 判定しろとは言いません**。

**台帳**（`data/owner_ask.jsonl`・追記だけ）: 1行 ＝ 1つの問い。
`{"at", "id", "asked_by", "where", "text", "answered"}`。
**答えが来たら、その周が `answered` に受け取り帳の id を書いた行を足すこと**
（同じ `id` の新しい行が勝ちます ＝ 追記だけで直せる）。

**覆る条件**:
 (1) 返事が 1件 来たら、この道具は**その問いを黙らせるだけ**です（`answered`）。
     残りの問いが 0件 になったら、**この道具ごと畳んでよい**。
 (2) 問いが **3件** 並んだら、並べる場所が `docs/GOAL.md` の本文では足りない
     ＝ そのときオーナーへ渡す 1枚（`docs/FOR_OWNER.md`）へ移すこと。
 (3) 周の数え方が変わったら（親が 1周に 1体 しか立てない形になったら）、
     ここの「2体 で 1周」も一緒に直すこと。
 (4) **引かれた問いを、次の周が「まだ訊いていない」と読んだら**、足りないのは数ではなく
     **引かれたあとに何をするか**（GOAL.md の (4) の後段）＝ そちらを 1行で書くこと。

検査は `tests/test_owner_ask.py`（**陽性対照つき** ＝ §5 教訓の形 3つ目）。
derivation は `docs/JOURNAL.md` 2026-09-14 02:5x。
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JST = dt.timezone(dt.timedelta(hours=9))

GATE_LAPS = 3          # `docs/GOAL.md` の達成期限の節・覆る条件 (4)


def _rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _jst(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s).astimezone(JST)


def laps_since(at: dt.datetime, rounds: list[dict]) -> list[dt.datetime]:
    """訊きの刻より後の周（重複なし・古い順）。**役では数えない**（2体 で 1周）。"""
    keys = {r.get("round") or r.get("at") for r in rounds if r.get("round") or r.get("at")}
    return sorted(x for x in (_jst(k) for k in keys) if x > at)


def state(asks: list[dict], rounds: list[dict], inbox: list[dict]) -> list[dict]:
    """問いごとの `{"id", "at", "text", "where", "laps", "replies", "answered", "drawn"}`。

    同じ `id` は**新しい行が勝つ**（追記だけで `answered` を書ける）。
    """
    latest: dict[str, dict] = {}
    for a in sorted(asks, key=lambda a: a["at"]):
        latest[a["id"]] = {**latest.get(a["id"], {}), **a}
    owner = [r for r in inbox if r.get("source") == "owner" and r.get("at")]
    out = []
    for a in sorted(latest.values(), key=lambda a: a["at"]):
        at = _jst(a["at"])
        laps = laps_since(at, rounds)
        replies = [r for r in owner if _jst(r["at"]) > at]
        out.append({"id": a["id"], "at": at, "text": a.get("text", ""),
                    "where": a.get("where", ""), "laps": len(laps),
                    "drawn_at": laps[GATE_LAPS - 1] if len(laps) >= GATE_LAPS else None,
                    "replies": [r.get("id") for r in replies],
                    "answered": a.get("answered"),
                    "drawn": len(laps) >= GATE_LAPS and not replies and not a.get("answered")})
    return out


#: **問いがオーナーに届く唯一の道**（`docs/FOR_OWNER.md` の「出す」の窓）。
#: 親が読むのはその節だけで、**この台帳（`data/owner_ask.jsonl`）は子しか読みません。**
FOR_OWNER = ROOT / "docs" / "FOR_OWNER.md"


def undelivered(st: list[dict], text: str | None = None) -> list[str]:
    """**返事待ちなのに `docs/FOR_OWNER.md` に 1度も書かれていない問い**の id（古い順）。

    **なぜ要るか**（2026-09-18 05:xx・optimizer・Fable 5.1・ultracode が踏んだ）——
    `channel_rename_studio` は 09/17 16:0x から **8周** この台帳に在り、毎周
    「**まだ引けません / オーナーが言葉を出しています**」と印字されていました。
    **その 8周 のあいだ、オーナーには 1文字も届いていません** ——
    親が読むのは `docs/FOR_OWNER.md` の「出す」の節だけで、**この台帳は子しか読まない**からです。
    ＝ この道具は「何周 待ったか」を数えていたのに、**待っていたのは返事ではなく、自分が出し忘れた文**でした。
    **この repo でいちばん多い壊れ方**（「N回 続いたら」と書いて N を数える物が無い）の裏返しで、
    **数えていた N が、そもそも始まっていなかった**形です。

    **印は id の字**（`docs/FOR_OWNER.md` のどこかに `<id>` が在れば「置いた」と見なす）——
    窓の本文は言い換えるので、文で突き合わせると必ず外れます。**id は言い換えません。**

    **覆る条件**:
     (1) 「出す」の窓を機械が読めるようになったら（`scripts/for_owner.py --list` に id が出るなら）、
         この当てを id の grep から**窓の id** へ移すこと（門は 1か所・ここ）。
     (2) **オーナーの手が要らない問いをこの台帳に置いたら**、この行は偽で鳴ります
         ＝ そのときは台帳の側が間違い（この台帳は「オーナーの手でしかできないこと」だけ）。
    """
    if text is None:
        text = FOR_OWNER.read_text(encoding="utf-8") if FOR_OWNER.is_file() else ""
    return [s["id"] for s in st
            if not s["answered"] and not s["replies"] and s["id"] not in text]


def lines(asks: list[dict], rounds: list[dict], inbox: list[dict],
          for_owner: str | None = None) -> list[str]:
    st = state(asks, rounds, inbox)
    open_ = [s for s in st if not s["answered"]]
    out = [f"**オーナーの手が要る問い: 返事待ち {len(open_)}件**"
           f"（門 {GATE_LAPS}周・`docs/GOAL.md` の達成期限の節 覆る条件 (4)・"
           f"台帳 `data/owner_ask.jsonl`）"]
    for s in st:
        head = f"  {s['at']:%m/%d %H:%M} `{s['id']}` {s['laps']}周"
        if s["answered"]:
            out.append(f"{head} ＝ **返事ずみ**（受け取り帳 `{s['answered']}`）")
        elif s["replies"]:
            out.append(f"{head} ＝ **オーナーが言葉を出しています**（`{'`・`'.join(s['replies'])}`）"
                       " —— **その言葉が正本** ＝ この周が読んで、答えかどうかを判定すること")
        elif s["drawn"]:
            out.append(f"{head} ＝ **引かれました**（{s['drawn_at']:%m/%d %H:%M} の周から）"
                       " —— **返事は来ない前提で進む側**。**もう一度 判定しなくてよい**")
        else:
            out.append(f"{head} ＝ **まだ引けません**（あと {GATE_LAPS - s['laps']}周）")
        if s["text"]:
            out.append(f"        {s['text'][:78]}")
    if not open_:
        out.append("  **返事待ちは 0件 ＝ この道具は仕事を終えています**（覆る条件 (1) ＝ 畳んでよい）")
    miss = undelivered(st, for_owner)
    if miss:
        out.append(f"  !! **オーナーに届いていない問い {len(miss)}件**: `{'`・`'.join(miss)}`"
                   " —— **`docs/FOR_OWNER.md` の「出す」に窓を 1つ 足すまで、この問いは"
                   "オーナーの目に 1度も入りません**（親が読むのはその節だけ・`undelivered` の註）")
    return out


def main() -> None:
    print("\n".join(lines(_rows(ROOT / "data/owner_ask.jsonl"),
                          _rows(ROOT / "data/rounds.jsonl"),
                          _rows(ROOT / "data/inbox.jsonl"))))


if __name__ == "__main__":
    main()
