#!/usr/bin/env python3
"""`list_sessions` の返りを、**道具が読む列だけ**写して組み立てる。

    python scripts/sessions_compact.py <出力file> < <compact.txt>
    python scripts/sessions_compact.py <出力file> --rows <compact.txt>

出したファイルは、そのまま両方に渡せます（`docs/trigger_main.md` §2 と §6 (f)）:

    python scripts/quota.py --ingest <出力file>
    python scripts/sibling_check.py --sessions <出力file>

## なぜ要るか（2026-08-16。**測ってから足しています**）

前の回の設計の見直し（§6 (a2) 問い1）が、この回の**いちばんの時間食い**として
こう書き残しました ——

> **いちばん時間を食ったのは、`list_sessions` の返りをファイルに落とすところ**（約6分）。

手順は「**返りをまるごと保存する**」です。ところが MCP の返りはこちらの文脈の中にしか
無いので、**保存する ＝ 全部を手で書き写す**ことになります。25件ぶんの返りには
`title`（1件が数百字あります）や `task_summary` や `post_turn_summary` が入っていて、
**そのどれも `quota.py` と `sibling_check.py` は読みません。**

実際に読まれる列は、両方あわせて次だけです（2026-08-16 に実物で確かめました）:

    id / created_at / updated_at / session_status / tags / parent_session_id
    external_metadata.rate_limit_info{rateLimitType, resetsAt, status}
    external_metadata.usage{cache_read, cache_write, input, output}

`title` は `quota.py` が行に持つだけで、**判断にも計算にも使われません。**

**毎周6分は、1日にすると2時間以上です。** 1周の下限が41分（`quota.py --pace`）
なので、**6分は1周の15%**にあたります。

## 書き方

1行1セッション。空白区切り。**`#` から行末は註**。

    <id> <status> <created> <updated> <parent> <resetsAt> <rlstatus> [<cr>,<cw>,<in>,<out>] [<tag>]

- **週枠の行には `seven_day` と書くこと**（2026-08-20 09:4x に**この回が書き落とした**）。
  書かない行は `five_hour` になります。**書き落としても、リセットが5時間より先なら
  こちらで直して鳴らします** —— 5時間枠のリセットが窓の中の観測より5時間も先に
  来ることはないからです。**鳴ったら、写した側を直すこと**
- **タグの違う行は、そのタグを書くこと**（2026-08-20 09:2x に踏んだ。下の節）。
  `youtube-owner-request` のように**そのまま**書くか、`tag:a,b` と書く。
  書かなかった行は `--tag`（既定 `youtube-hourly`）になります
- `<id>` `<parent>` は `session_` を外した接尾辞。**頭の `0` は省いてよい**
  （接尾辞は必ず24字で `01` 始まりなので、こちらで補います）
- `<created>` `<updated>` は `HH:MM:SS` だけ。日付は `--date`（既定は今日 UTC）
  **日をまたいだ行だけ** `MM-DD/HH:MM:SS` と書く
- `<status>` は `RUNNING` / `ARCHIVED` / `PENDING` / `IDLE` …（`SESSION_STATUS_` は不要）
- **`rate_limit_info` が丸ごと無い行は、`<resetsAt>` と `<rlstatus>` を `-` と書く**
  （2026-08-21 02:1x に足した）。1ターン目で `API Error: 529` に当たって死んだ回が
  それです。**行ごと落とさないこと** —— `sibling_check` が「印を1つも残していない回」
  として名指しするのは、まさにその回です。**適当な `resetsAt` も書かないこと** ——
  枠の観測が1点でっち上がります
- 最後の4つ組は `external_metadata.usage` がある行だけ。**無い行は省く**
  （**省くことと 0 は違います。** `usage` は全部の行には入らないので、
  0 と書くと「使っていない」という嘘の点が積まれます）

## **タグを全行に同じものとして写すと、その回が丸ごと消えます**（2026-08-20 09:2x に踏んだ）

`--tag` は長らく**全行に同じ1つ**を付けるだけで、行ごとに書く道がありませんでした。
**読む側は行ごとに見ています** —— `sibling_check.py` は
`tags` に `youtube-hourly` を含む行だけを兄弟に数えます。

09:2x の回の実物には、オーナー指示で走っている `youtube-owner-request` の
セッションが**2件**入っていました。それが `youtube-hourly` として積まれ、
`sibling_check` は**「自分より古い兄弟が2件走っている」→ 終了コード 2
＝ この場で畳め**と答えました。§2 の指示どおりなら、**その回は
§6 (a)〜(e) を飛ばして、1件も出さずに終わります**（1周まるごと）。

**片方だけの形です**（このファイルで4度目）—— 読む側は行ごとに見るのに、
書く側が行ごとに書けない。**足りないのは判断ではなく、書ける列**でした。

## 割り引いて読むこと

**これは返りの完全な写しではありません。** `title` などを落としています。
`quota.py` の行の `title` が空になりますが、**あれは表示だけの列**です。
**新しい列を読む道具を足したら、ここも足すこと**（落ちていることに気づけません）。
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone

TAG = "youtube-hourly"


def full_id(s: str) -> str:
    """接尾辞は24字で必ず `01` 始まり。省いた頭を補う。

    **`session_` を付けたまま渡してもよい**（2026-08-17 に踏んで足した）。
    手順（§2）は「`session_` と頭の `0` は**省いてよい**」と書いています ——
    つまり**省かない形も来ます。** ところがここは接尾辞だけを前提にしていて、
    付いたまま渡すと `session_session_01...` を組み立てていました。

    **壊れ方が静かなほうへ倒れます。**
      `sibling_check` → 「返りの中に自分がいません」（**ファイルが古い、と誤診させる**）
      `quota.py`      → **何も言わずに積みます。** 25件ぶんの偽の点が
                        `data/quota.jsonl` に入り、`--pace` の「1周いくら」を薄めます
    計器の汚れは次の回が引き継ぐので、**気づけないほうの落ち方**です。
    """
    s = s.strip()
    if s.startswith("session_"):
        s = s[len("session_"):]
    if len(s) < 24:
        s = ("01" if len(s) == 22 else "0" * (24 - len(s))) + s
    if not re.fullmatch(r"[0-9A-Za-z]{24}", s):
        raise SystemExit(
            f"セッションIDの形が違います: {s!r}（24字の英数字。`session_` は付いていても外します）")
    return "session_" + s


def stamp(text: str, base: str) -> str:
    """`14:21:56` / `08-15/14:21:56` / **まるごとの ISO** を ISO へ。

    ## 3つめを足した理由（2026-08-17 11:3x。**この道具の2度目の同じ壊れ方**）

    ここは `HH:MM:SS` だけを想定していて、**`2026-08-17T02:07:34Z` を渡すと
    黙って `2026-08-17T2026-08-17T02:07:34Z.000000Z` を返していました。**
    形が違うと言わず、**読めない字を作って通します。**

    落ちる先は2つで、**どちらも黙ります**:

        `sibling_check --phase spawn`  `born` が None になり、
                                      **間隔の下限（41分）が丸ごと効かない**
        `quota.py --ingest`           読めない時刻の点を25件積む

    実際この回は、誕生から25分で `立ててよい` と言われました（下限は41分）。
    **速く回すほど枠を先に使い切るので、これは鎖を止める向きの故障です。**

    **8/17 07:4x に、同じ道具が同じ形で壊れていました** ——
    あのときは `session_` を無条件に前置していて、**手順が「省いてよい」と
    書いている＝省かない形も来る**のに、片方しか受けていなかった。
    ここも同じで、手順は「日付も省いてよい」＝**省かない形も来ます。**

    **だから、受けるか落とすかの2つにします。読めない字を作らないこと。**
    """
    text = text.strip()
    if "T" in text or text.count("-") >= 2:
        # まるごとの ISO。**そのまま通す**（`Z` は UTC のまま）
        try:
            when = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            raise SystemExit(
                f"時刻が読めません: {text!r}\n"
                "  受けるのは `HH:MM:SS` / `MM-DD/HH:MM:SS` / まるごとの ISO の3つです。")
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        return when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"
    if "/" in text:
        day, clock = text.split("/", 1)
        base = f"{base[:4]}-{day}"
    else:
        clock = text
    out = f"{base}T{clock}.000000Z"
    # **作った字が読めることを、その場で確かめる。**
    # 黙って壊れた字を返すのが、この関数のいちばん高い故障でした。
    try:
        datetime.fromisoformat(out.replace("Z", "+00:00"))
    except ValueError:
        raise SystemExit(
            f"時刻が読めません: {text!r} → {out!r}\n"
            "  受けるのは `HH:MM:SS` / `MM-DD/HH:MM:SS` / まるごとの ISO の3つです。")
    return out


#: **終わり方の印**（2026-08-17 に足した。**足すのは「1行も残さずに死んだ回」だけ**）。
#:
#: 25件ぶん写す手を増やさないため、**普通の回には1語も要りません。**
#: 書くのは `sibling_check` が名指しする回、つまり
#: **`run_marker` の印を1つも残していない回**についてだけです。
#: その1件を返りから読むとき、次のどちらかを最後に足します:
#:
#:     nosrc    `session_context.sources` が**空**だった
#:              ＝ repo が渡らなかった回（2026-08-17 04:1x）
#:     apifail  `sources` は入っているのに `post_turn_summary.status_detail` が
#:              API 側の一時失敗（`API Error: 529 Overloaded` など。2026-08-17 23:0x）
#:
#: **この2つは、次の子のやることが正反対です**（`sibling_check.report_silent`）。
#: 印が無いと道具は「`sources` が渡らなかった疑い」と**断定して**しまい、
#: 既定のままの題名（中身ゼロ）を読みにいかせます。
ENDINGS = {"nosrc", "apifail"}

#: 行に書けるタグ。**`youtube-hourly` 以外の行があるから要ります**（2026-08-20 09:2x）。
#: `sibling_check.py` は行ごとに `tags` を見るので、**全行に同じものを付けると
#: 別の目的で走っているセッションが「兄弟」に化けます**（終了コード 2 ＝ その回は畳む）。
#: 受ける形は2つ:
#:
#:     youtube-owner-request     そのまま書く（`-` を含む小文字の語）
#:     tag:youtube-hourly,foo    複数付けたいとき
#:
#: **数字の4つ組（`usage`）にも `seven_day` にも `-` は入りません**ので、ぶつかりません。
TAG_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)+$")


def row_tags(fields: list[str], default: str) -> list[str]:
    """行の末尾から、その行のタグを読む。**書いていなければ `default`。**"""
    out: list[str] = []
    for f in fields:
        if f.startswith("tag:"):
            out += [t for t in f[4:].split(",") if t]
        elif f not in ENDINGS and TAG_RE.match(f):
            out.append(f)
    return out or [default]


#: 5時間枠の長さ（秒）。**この枠のリセットは、窓の中の観測から5時間より先には来ません。**
FIVE_HOUR_SEC = 5 * 3600


def parse(rows: str, base: str, tag: str) -> list[dict]:
    out: list[dict] = []
    fixed: list[str] = []
    for raw in rows.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        f = line.split()
        if len(f) < 7:
            raise SystemExit(f"列が足りません（7つ以上要ります）: {raw!r}")
        sid, status, born, seen, parent, resets, rls = f[:7]
        # **位置ではなく中身で見ること**（2026-08-17 23:2x）。`f[7]` 決め打ちだと、
        # 落ち方の印を先に書いた行で `seven_day` が黙って `five_hour` に化けます
        # （このファイルが3度目の「片方だけ」です）。
        kind = "seven_day" if "seven_day" in f[7:] else "five_hour"
        # **`rate_limit_info` が丸ごと無い行がある**（2026-08-21 02:1x に踏んだ）。
        # 1ターン目で `API Error: 529` に当たって死んだ回は `external_metadata` に
        # `rate_limit_info` を持ちません。ここは長らく `resets` と `rls` を必須にしていて、
        # **書けない行**でした。逃げ道は2つとも台帳を汚します ——
        # 行ごと落とせば `sibling_check` から**その回だけ**消え（印を1つも残していない回を
        # 名指しするのは、まさにその道具です）、適当な `resetsAt` を書けば
        # **枠の観測が1点でっち上がります**。読む側（`quota.py:510` と
        # `sibling_check.py:552`）はどちらも `or {}` で欠落を織り込み済みなので、
        # **書く側に「無い」と言う字を足すのが正しい**。`-` で省きます。
        if resets == "-" or rls == "-":
            meta: dict = {}
        else:
            meta = {"rate_limit_info": {
                "rateLimitType": kind, "resetsAt": int(resets), "status": rls}}
        tokens = [x for x in f[7:] if re.fullmatch(r"\d+(,\d+){3}", x)]
        if tokens:
            cr, cw, i, o = (int(x) for x in tokens[0].split(","))
            meta["usage"] = {"cache_read_tokens": cr, "cache_write_tokens": cw,
                             "input_tokens": i, "output_tokens": o}
        row = {
            "id": full_id(sid),
            "session_status": status if status.startswith("SESSION_STATUS_")
            else "SESSION_STATUS_" + status,
            "created_at": stamp(born, base),
            "updated_at": stamp(seen, base),
            "tags": row_tags(f[7:], tag),
            "parent_session_id": full_id(parent),
            "external_metadata": meta,
        }
        # **書き忘れを、書いた側に頼らず捕まえる**（2026-08-20 09:4x に自分で踏んだ）。
        # 5時間枠のリセットは、その窓の中の観測から**5時間より先には来ません**。
        # 先にあるなら、それは週枠の行に `seven_day` を書き落としたものです。
        if kind == "five_hour" and meta:
            ahead = int(resets) - int(datetime.fromisoformat(
                row["updated_at"].replace("Z", "+00:00")).timestamp())
            if ahead > FIVE_HOUR_SEC:
                meta["rate_limit_info"]["rateLimitType"] = "seven_day"
                fixed.append(row["id"])
        ending = [x for x in f[7:] if x in ENDINGS]
        if ending:
            # **書かれていないことを「無かった」と読まないため**、印のある行にだけ
            # 欄を作ります（`sources` の欄そのものが無い ＝ 見ていない、です）。
            row["ending"] = ending[0]
            if ending[0] == "nosrc":
                row["session_context"] = {"sources": []}
        out.append(row)
    if fixed:
        # **黙って直さないこと。** 直したこと自体が、写し方の欠けの合図です。
        print(f"[compact] `seven_day` の書き落としを {len(fixed)} 行ぶん補いました"
              f"（リセットが5時間より先だったので、5時間枠ではありえません）。"
              f"**次からは行の末尾に `seven_day` と書くこと。**", file=sys.stderr)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", help="組み立てた JSON の書き出し先")
    ap.add_argument("--rows", help="compact な行を書いたファイル（既定は標準入力）")
    ap.add_argument("--date", help="時刻に付ける日付（UTC の YYYY-MM-DD）。既定は今日")
    ap.add_argument("--tag", default=TAG,
                    help=f"**タグを書かなかった行**に付ける既定（既定 {TAG}）。"
                         "行ごとに違うときは、その行に `youtube-owner-request` の"
                         "ように書くこと（全行を同じにすると兄弟の数が狂います）")
    args = ap.parse_args()

    base = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = open(args.rows, encoding="utf-8").read() if args.rows else sys.stdin.read()
    data = parse(rows, base, args.tag)
    if not data:
        raise SystemExit("1件も読めませんでした")
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"ccr": {"data": data}}, fh, ensure_ascii=False)

    has_usage = sum(1 for r in data if "usage" in r["external_metadata"])
    print(f"{len(data)} 件を {args.out} へ（うち usage あり {has_usage} 件）")
    print("  python scripts/quota.py --ingest " + args.out)
    print("  python scripts/sibling_check.py --sessions " + args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
