#!/usr/bin/env python3
"""**使用量の計器。** CCR の MCP の返りに入っている枠情報を、時系列に積む。

## なぜ作り直したか（2026-08-14）

これまでの正本は `-chatgpt-usage-monitorPrivate` の `state/claude-usage.json` で、
あれは唯一「%」を返してくれる口だった。**もう死んでいる。**

- 8/11 から OAuth が切れて `reauthentication_required` しか返さない
- 8/12 09:39 JST から向こうの GitHub Actions ごと止まっている
- **直すにはオーナーがブラウザで認証し直すしかない。** A1 は「私側への指示を
  してもいいが、必ず読むとは限らない」と言っている。**人待ちの計器は計器ではない**

そのあいだ `docs/trigger_main.md` §2 は毎回 `add_repo` → Actions → clone を
踏ませていた。**3つとも失敗する経路に、毎回3〜4分と数千トークンを捨てていた。**

## 代わりに読むもの

**CCR の MCP の返りそのもの。** `list_sessions` / `get_session` /
`create_session` の `external_metadata` に、2種類の値が入っている。

    "rate_limit_info": {"rateLimitType":"seven_day",
                        "resetsAt":1786744800, "status":"rejected"}

    "usage": {"cache_read_tokens":767141, "cache_write_tokens":142437,
              "input_tokens":19, "output_tokens":3072}

`add_repo` も Actions も要らない。**遅れもない。**

## この計器が答えられること・答えられないこと

**答えられる。** いまどちらの枠が効いているか。警告帯に入っているか。
枠が閉じているか。いつリセットされるか。**判断に要るのはほぼこれで足りる。**

**答えられない。** 「残り何%か」。**返り値に%は入っていない。**
分母（何トークンで閉じるか）も返ってこない。

**だから積む。** `status` が切り替わった時刻と、そこまでに見えた消費量を
枠ごとに記録し続ければ、目盛りは後から決まる。**1点では決まらない。
積み始めなければ永久に決まらない。**

## 分かっている穴（読むときに割り引くこと）

- **`usage` は全部の行には入らない。** だから消費量の合計は**必ず過小**で、
  この計器は「少なくともこれだけは使った」しか言わない。下限として読むこと

  **`usage` が入る条件は、9回の申し送りに載り続けた最後の1件でした。
  2026-08-16 に 159点で測って閉じます。以後この問いを運ばないこと。**

  積まれていた説は **「42分説」**（1周が42分を超えたセッションに入る）でした。
  **外れです。** 67セッションを年齢で並べると、**範囲が完全に重なります**:

      入っている  最初に見えた年齢の最小 **13.0分**
      入っていない 最も遅い観測の年齢が **44.2分・46.8分**

  **なぜ42分に見えたか。** 観測しているのは毎回「自分を立てた親」で、
  親が立つ時刻は §6 (f) の門が決めます。だから**見えた年齢は門と一緒に動きます**:

      門が31分だった時期   最初に見えた年齢 31.0 / 32.1分
      門を41分にした後     41.5 / 41.5 / 41.6 / 41.6 / 41.6 / 41.7 / 41.7分

  **自分の時計を読み返していただけで、本当のしきい値は一度も挟んでいません。**

  分かったのは**時刻ではなく形**が2つ、それだけです。

  1. **片方向。** 2回以上見た42セッションで **「無 → 有」11件・「有 → 無」0件。**
     **「入っていない」は「使っていない」ではなく「まだ無い」**と読むこと
  2. **待っても入らないものがある。** ただの遅れではありません。
     **4〜5回・13時間にわたって見続けても最後まで入らない子が多数**います
     （直近25件でも15件が「無」）。**規則は依然として不明です。**

  **それでも測るのをやめるのは、答えが行動を1つも変えないからです。**
  `_tokens_upto()` は**セッションごとに最大値**を採り、欠けた行は
  `blind` として別に数えるので、遅れて入っても二重に数えず、
  欠けたぶんを0とも読みません（下の `_merge` も情報が増える向きにしか動かない）。
  **覆る条件**: 1周より若いセッションの消費量そのものが要る判断が出てきたとき
  （いまは無い。間隔の判断は枠全体の速さで決めており、1セッション単位では見ていない）
- **5時間枠と7日枠は別物。** 混ぜないこと。`rateLimitType` は
  「いま効いている（先に閉じそうな）ほうの枠」を指しているらしい
- **消費の時刻は、そのセッションが最後に動いた時刻で代表させている。**
  長く走ったセッションのぶんは、実際より後ろに寄る

## 使い方

    # MCP の返り（list_sessions か get_session）を保存してから食わせる
    python scripts/quota.py --ingest <file.json>
    python scripts/quota.py --ingest -        # 標準入力でもよい

    python scripts/quota.py                   # いまの姿を出す

**`--ingest` は MCP を叩けない。** シェルからは資格情報に届かないので、
呼び出し側（あなた）が `list_sessions` を叩いて、その返りをここに渡すこと。
`list_sessions` は1回で25件ぶん返す。**その25行がそのまま25点の時系列になる。**
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "data" / "quota.jsonl"

# 枠の長さ。`resetsAt` から逆算して「枠のどのへんにいるか」を出すのに使う。
WINDOW_SPAN = {"five_hour": timedelta(hours=5), "seven_day": timedelta(days=7)}

# **外から入る「%」の置き場**（2026-08-15）。
# `rate_limit_info` に % は入らないので、この計器だけでは「速すぎるか」を言えない。
# オーナーが手で測った値をここに積み、**誕生数で割って目盛りにする。**
USAGE_LOG = ROOT / "data" / "usage.jsonl"

# 週枠を均して使い切る速さ。**枠の頭から見たときの基準線。**
WEEK_HOURS = 168.0
SUSTAIN_PCT_PER_HOUR = 100.0 / WEEK_HOURS      # ＝ 0.595 %/時

# **判断に使うのはこちらではなく「残りを残り時間で割った速さ」（2026-08-15 夜）。**
# 上の 0.595 は「いま 0% から始めるなら」の値で、**すでに使ったぶんを見ていない。**
# 8/15 23:33 の時点で 16.6時間・13% ＝ 基準線（9.9%）を 3.1% 追い越しており、
# **この先に許される速さは 0.595 ではなく (100-13)/151.45 = 0.574 %/時。**
# 先行しているのに 0.595 を基準にすると、**追い越したぶんを取り返せないまま
# 「ほぼ基準どおり」と読めてしまう。** 遅れているときは逆に締めすぎる。

# %は整数でしか読めない（オーナーが画面を見て報告する）。1点あたり ±0.5%、
# **2点の差では ±1.0%。** 区間の Δ% がこの何倍あるかが、区間推定の信頼度そのもの。
# Δ% がこの値に達したら区間だけで決める。足りないぶんは通算のほうへ寄せる。
QUANT_FULL_PCT = 8.0

# 間隔の下限に置く上下の歯止め。**計器が壊れても鎖を止めない／暴走させない。**
FLOOR_MIN_CLAMP, FLOOR_MAX_CLAMP = 10.0, 90.0

# 弱いほうから順に。遷移の向きを判定するのに使う。
STATUS_ORDER = ["allowed", "allowed_warning", "rejected"]

STATUS_JA = {
    "allowed": "余裕あり",
    "allowed_warning": "**警告帯**",
    "rejected": "**閉じている**",
}


# --------------------------------------------------------------------------
# 取り込み
# --------------------------------------------------------------------------

def _iter_sessions(blob):
    """MCP の返りから、セッションの dict を1件ずつ取り出す。

    `list_sessions` は `{"ccr":{"data":[...]}}`、`get_session` と
    `create_session` は `{"ccr":{...}}`。**どちらも黙って受ける。**
    """
    if isinstance(blob, list):
        for item in blob:
            yield from _iter_sessions(item)
        return
    if not isinstance(blob, dict):
        return
    inner = blob.get("ccr", blob)
    if isinstance(inner, dict) and isinstance(inner.get("data"), list):
        for row in inner["data"]:
            if isinstance(row, dict):
                yield row
    elif isinstance(inner, dict) and inner.get("id"):
        yield inner


def _parse_iso(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _normalize(sess: dict):
    """セッション1件を、記録する形にする。読める情報が無ければ None。"""
    meta = sess.get("external_metadata") or {}
    rli = meta.get("rate_limit_info") or {}
    usage = meta.get("usage") or {}
    seen = _parse_iso(sess.get("updated_at"))
    if not seen:
        return None
    window = rli.get("rateLimitType")
    resets = rli.get("resetsAt")
    if not window and not usage:
        # 枠も消費量も無い行は、積んでも何も言わない。
        return None
    born = _parse_iso(sess.get("created_at"))
    row = {
        "seen_at": seen.astimezone(timezone.utc).isoformat(),
        "born_at": born.astimezone(timezone.utc).isoformat() if born else None,
        "session_id": sess.get("id"),
        "title": sess.get("title") or "",
        "tags": sess.get("tags") or [],
        "window": window,
        "status": rli.get("status"),
        "resets_at": (datetime.fromtimestamp(resets, timezone.utc).isoformat()
                      if isinstance(resets, (int, float)) else None),
    }
    if usage:
        row["tokens"] = {k: usage.get(k, 0) for k in
                         ("input_tokens", "output_tokens",
                          "cache_read_tokens", "cache_write_tokens")}
    return row


#: **未来の観測は「あり得ない点」です**（2026-08-17 11:3x に23件見つけた）。
#: 少しの時計ずれで落とさないよう、余裕を持たせています。
FUTURE_SLACK_MIN = 30


def _load(*, keep_impossible: bool = False) -> list[dict]:
    """積んだ点を読む。**未来の点は落とします。**

    ## なぜ落とすか（2026-08-17 11:3x）

    `sessions_compact.stamp()` が、まるごとの ISO を渡されたときに
    **`2026-08-17T2026-08-16T22:46:52Z.000000Z`** を作っていました。
    ここはそれを読んで**日付だけ拾う**ので、**8/16 の観測が 8/17 として積まれます。**
    実測23件。**1日ずれた点は、`--pace` の「いつ尽きるか」を丸ごと狂わせます。**

    この回の `status.py` は、その症状を出していました ——
    **「この読みは -21時間前の観測（08/18 08:28 JST）」**。
    **負の「〜前」と、明日の日付**が並んでいたのに、素通りしていました。

    **作った側は直しました**（`scripts/sessions_compact.py`）。ここで落とすのは、
    **既に積んだぶんと、次に別の道から入るぶん**のためです。
    **ファイルからは消しません** —— 追記のみの台帳なので、
    読む側で外すほうが安全です（`docs/trigger_main.md` §6 (b)）。
    """
    if not LOG.exists():
        return []
    out = []
    limit = (datetime.now(timezone.utc) + timedelta(minutes=FUTURE_SLACK_MIN)).isoformat()
    for line in LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue                  # 壊れた行は捨てる。積むほうを止めない
        seen = str(rec.get("seen_at") or "")
        if not keep_impossible and seen and seen > limit:
            continue                  # **未来の点。** 上の註のとおり読み飛ばす
        out.append(rec)
    return out


def impossible_rows() -> list[dict]:
    """未来の点だけを返す（**落としたことを目で見るため**）。"""
    kept = {(r.get("session_id"), r.get("seen_at")) for r in _load()}
    return [r for r in _load(keep_impossible=True)
            if (r.get("session_id"), r.get("seen_at")) not in kept]


def _key(row: dict):
    """同じ観測かどうかの鍵。**セッションと、その最終更新時刻。**

    同じセッションが後で `usage` を持って出てくることがある（消費量は
    あとから入る行がある）。そのときは**上書きして埋める**。
    """
    return (row.get("session_id"), row.get("seen_at"))


def _merge(old: dict, new: dict) -> dict:
    """同じ鍵の2行を1行にする。**情報が増える方向にだけ動かす。**"""
    merged = dict(old)
    for k, v in new.items():
        if v in (None, "", [], {}):
            continue
        merged[k] = v
    if old.get("tokens") and not new.get("tokens"):
        merged["tokens"] = old["tokens"]
    return merged


def _all_ids(blob) -> set[str]:
    """入れ子のどこにあっても `id` を集める。**丸ごと一致で比べるため。**"""
    found: set[str] = set()
    if isinstance(blob, dict):
        v = blob.get("id")
        if isinstance(v, str):
            found.add(v)
        for value in blob.values():
            found |= _all_ids(value)
    elif isinstance(blob, list):
        for item in blob:
            found |= _all_ids(item)
    return found


def self_check(text: str) -> str:
    """**飲む前に、自分がその中にいるかを見る**（2026-08-17 12:5x に足した）。

    3回運ばれて3回とも未着手だった申し送りです。

    8/17 07:4x の回は、`sessions_compact` が `session_` を二重に付けた
    **偽のIDを25件そのまま積みました。** 落ち方が2つに割れています ——

        `sibling_check`  「返りの中に自分がいません」と**言った**（誤診だが、鳴った）
        `quota.py`       **何も言わずに積んだ**

    **気づけたのは、片方が exit 1 したからで偶然です。** こちらが黙るのは、
    積んだ点が `--pace` の「1周いくら」を薄め、**次の回が間隔を詰める**方向に効きます。
    計器の汚れは次の回が引き継ぐので、**気づけないほうの落ち方**です。

    判定は `sibling_check` にもう書いてあるので、そちらを使い回します。
    **止めません。** 自分のIDが環境から取れない回（人との会話の回など）もあり、
    そこで積めなくなるほうが損だからです。**言うだけ。**

    **文字列として探さないこと**（2026-08-17、書いた直後に検査が捕まえました）。
    `"session_" in text` で書くと、**この穴そのものを見逃します** ——
    二重に付いた `session_session_01CX...` は、正しいIDを**部分文字列として含む**ので、
    素の `in` では「いる」と答えます。**IDに割ってから、丸ごと一致で比べること。**
    """
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import sibling_check  # noqa: PLC0415
    except Exception:
        return ""
    me = sibling_check.my_session_id()
    if not me:
        return ""
    try:
        blob = json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            return ""
        try:
            blob = json.loads(m.group(0))
        except Exception:
            return ""
    # **`sibling_check.iter_sessions` は使いません。** あれは `created_at` を
    # 持つ dict しか拾わないので（生死を測る道具なので正しい）、
    # 欄の欠けた返りでは**「いない」に倒れます**。ここが見たいのはIDだけです。
    if me in _all_ids(blob):
        return ""
    return (f"[!] **この返りの中に自分（{me}）がいません。**\n"
            "    ファイルが古いか、IDの写し方が壊れています。"
            "**積んだ点は次の回の間隔を決めます**（`--pace`）。\n"
            "    `list_sessions` を取り直して、`sessions_compact.py` からやり直すこと。")


def _is_impossible(row: dict) -> bool:
    """**リセット時刻が観測時刻より前の点は、積まないこと**（2026-08-18 に足した）。

    枠は「まだ来ていないリセット」までの残りを言うので、`resets_at < seen_at` は
    **時間の向きとして起こりえません。** 起きるのは写し違いだけです。

    ## 何が起きたか

    `sessions_compact.py` は `HH:MM:SS` だけの行を **その日（既定は今日 UTC）** として読み、
    **日をまたいだ行にだけ `MM-DD/` を付けろ**と言っています（あちらの docstring）。
    **付け忘れると、前日の25件が丸ごと今日として積まれます。**

    実測: 2026-08-18 09:1x の回が **24件**、08-16 の回が **14件**。通算38件。
    **どちらも静かに通り**、`--pace`（1周いくらか・持続できる間隔）の分母を汚しました。
    **この計器が決めているのは、次の子を立てる間隔そのもの**です。

    捨てるだけで直しません。**正しい日付はこちらには分からない**ので、
    直せるのは写した側だけです（だから件数と直し方を印字します）。
    """
    seen, resets = row.get("seen_at"), row.get("resets_at")
    return bool(seen and resets and resets < seen)


def _total(row: dict) -> int:
    """その行が言っている**通算の消費量**。入っていなければ 0。"""
    tok = row.get("tokens") or {}
    return sum(v for v in tok.values() if isinstance(v, (int, float)))


def backward(rows: list[dict]) -> list[tuple[str, str, int, int]]:
    """**消費量が時間をさかのぼって減っている組**を返す。空なら健全。

    `usage` はそのセッションの**通算値**なので、`seen_at` の順に並べたとき
    **減ることはありません**（`tests/test_quota_usage_lag.py`。実測 42セッションで
    「無→有」11件・「有→無」0件）。減っていたら、**消費量ではなく時刻のほうが
    壊れています。**

    ## なぜ `--ingest` の側で見るのか（2026-08-20 12:4x に踏んだ）

    この不変量を見張る検査は前からありましたが、**見張っていたのは全体 `pytest`**で、
    そこに着くのは**回の終わりごろ**です。この回は §2 で汚し、**20分あとに**
    赤で知りました。**その間の判断は、汚れた台帳の上でしています** ——
    `--pace` の「1周いくら」と「持続できる間隔」は `seen_at` の差で出るので、
    **間隔の判断がそのぶん狂います。**

    踏み方はこうでした。**§2 は「返りをまるごと保存する」と言っていますが、
    まるごと写すと 15,000トークンかかる**ので、`quota.py` と `sibling_check.py` が
    読む列だけに削って渡しました。そのとき **`updated_at` を `created_at` で埋めた** ——
    `_normalize()` は `updated_at` を `seen_at` にするので、
    **25行が最大40分ぶん過去に倒れて**積まれ、既にあった行と順序が入れ替わりました。

    **削って渡すこと自体は間違いではありません**（写すだけで1周の1割を使う）。
    間違いなのは、**削ってよい列と、削ると時間軸が壊れる列を、機械が区別していなかった**
    ことです。ここで見れば、削り方を間違えた回が**その場で**分かります。
    """
    by: dict[str, list[dict]] = {}
    for r in rows:
        sid = r.get("session_id")
        if sid:
            by.setdefault(sid, []).append(r)
    out = []
    for sid, group in by.items():
        group.sort(key=lambda r: str(r.get("seen_at") or ""))
        high = 0
        for r in group:
            t = _total(r)
            if t and t < high:
                out.append((sid, str(r.get("seen_at") or ""), high, t))
            high = max(high, t)
    return out


def ingest(text: str) -> tuple[int, int]:
    """MCP の返りを読んで `data/quota.jsonl` に足す。(新規, 更新) を返す。

    **時間軸を壊す行は書きません**（`backward()`）。積むほうは止めません ——
    弾くのは、入れると順序が壊れる行**だけ**です。
    """
    blob = None
    try:
        blob = json.loads(text)
    except Exception:
        # ツールの返りが前後に文字を連れてくることがある。JSON の塊を拾う。
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                blob = json.loads(m.group(0))
            except Exception:
                blob = None
    if blob is None:
        raise SystemExit("JSON として読めませんでした。MCP の返りをそのまま渡すこと。")

    table = {_key(r): r for r in _load()}
    added = updated = skipped = 0
    for sess in _iter_sessions(blob):
        row = _normalize(sess)
        if not row:
            continue
        if _is_impossible(row):
            skipped += 1
            continue
        k = _key(row)
        if k in table:
            before = json.dumps(table[k], sort_keys=True)
            table[k] = _merge(table[k], row)
            if json.dumps(table[k], sort_keys=True) != before:
                updated += 1
        else:
            table[k] = row
            added += 1

    if skipped:
        print(f"[quota] **{skipped}件を捨てました**（リセット時刻が観測時刻より前）。"
              "日をまたいだ行に `MM-DD/` を付け忘れていないか、"
              "`sessions_compact.py --date` を確かめること。")
    rows = sorted(table.values(), key=lambda r: (r.get("seen_at") or ""))

    # **時間軸を壊す行だけ、書く前に落とす**（`backward()` の節）。
    bad = backward(rows)
    if bad:
        drop = {(sid, seen) for sid, seen, _, _ in bad}
        rows = [r for r in rows
                if (r.get("session_id"), str(r.get("seen_at") or "")) not in drop]
        added = max(0, added - len(drop))
        print(f"[quota] **{len(drop)}件を書きませんでした**（消費量が時間をさかのぼって減る行）。")
        for sid, seen, high, low in bad[:5]:
            print(f"    {sid}  {seen}  {high:,} → {low:,}")
        print("    **`usage` は通算値なので減りません。壊れているのは時刻のほうです。**")
        print("    渡した返りで **`updated_at` を落としていないか**を見ること"
              "（`_normalize()` はそこを `seen_at` にします）。")

    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                   encoding="utf-8")
    return added, updated


# --------------------------------------------------------------------------
# 読み出し
# --------------------------------------------------------------------------

def _periods(rows: list[dict]) -> dict:
    """`(枠, リセット時刻)` ごとにまとめる。**これが「枠1回ぶん」の単位。**"""
    out = {}
    for r in rows:
        if not r.get("window") or not r.get("resets_at"):
            continue
        out.setdefault((r["window"], r["resets_at"]), []).append(r)
    for v in out.values():
        v.sort(key=lambda r: r["seen_at"])
    return out


def _tokens_upto(rows: list[dict], start: datetime | None, until_iso: str):
    """枠の始まりから `until_iso` までに見えた消費量。

    `(出力, 総計, 消費量が読めなかった行数, 枠をまたぐので除いたセッション数)`。

    **枠に属するかは、その行自身の `window` ではなく時刻で決める**（2026-08-14）。
    `rate_limit_info` が付いていない行にも `usage` は入っていることがあり、
    枠で絞ると**そのぶんが丸ごと落ちる**。落ちれば合計はさらに過小になる。

    **セッションごとに最大値を採る。** 同じセッションが何度も出てくるが、
    `usage` は**そのセッションの通算値**なので、足すと二重に数える。

    同じ理由で、**枠の始まりより前に生まれたセッションは除く。**
    親セッションは 8/3 から生きていて 8,400万トークンを抱えている。
    これを1つの枠に押し込むと、枠の消費量が桁で狂う。
    除いたことは呼び出し側に返して、必ず表に出すこと。
    """
    best, blind, spanning = {}, 0, set()
    for r in rows:
        if r["seen_at"] > until_iso:
            continue
        if start and r["seen_at"] < start.isoformat():
            continue
        tok = r.get("tokens")
        if not tok:
            blind += 1
            continue
        sid = r.get("session_id")
        born = _parse_iso(r.get("born_at"))
        if start and born and born < start:
            spanning.add(sid)         # 枠をまたぐ。**どこまでが今回ぶんか分からない**
            continue
        total = sum(tok.values())
        if total > sum(best.get(sid, {}).values() or [0]):
            best[sid] = tok
    out_tok = sum(t.get("output_tokens", 0) for t in best.values())
    all_tok = sum(sum(t.values()) for t in best.values())
    return out_tok, all_tok, blind, len(spanning)


def _fmt_span(delta: timedelta) -> str:
    hrs = delta.total_seconds() / 3600
    if abs(hrs) >= 24:
        return f"{hrs / 24:.1f}日"
    if abs(hrs) >= 1:
        return f"{hrs:.0f}時間"
    return f"{hrs * 60:.0f}分"


# --------------------------------------------------------------------------
# 速さ（2026-08-15）
# --------------------------------------------------------------------------
# **なぜ要るか。** `rate_limit_info` は「閉じたか」しか言わない。閉じてから
# 気づくのでは遅い —— 8/12〜8/14 はそれで58時間止まった。**先に使い切ると、
# リセットまで1回も起きられない。** 読むのは残量ではなく「尽きる時刻」。
#
# **どう測るか。** %は外からしか入らない（`data/usage.jsonl`）。だが
# **誕生数はこちらで数えられる。** 1点でも%が入れば `% ÷ 誕生数` で
# 「1周いくら」が出て、そこから**持続できる間隔**が決まる。
#
# **穴**（読むときに割り引くこと）:
#   - 1周の重さは一定ではない。記録だけの回と、生成まで回した回が混ざる。
#     **出るのは平均**で、生成回だけを見れば1周はもっと高い
#   - `quota.jsonl` に積んでいない誕生は数に入らない。数え落とせば
#     「1周いくら」は**過大**に出て、間隔は**安全側（長め）**に振れる
#   - 他のループ（eta改善・クッキー）が混ざれば、その消費もこちらの
#     誕生数で割られる。**「ほぼこの作業だけ」と言える日の点だけを使うこと**


def _anchors() -> list[dict]:
    """外から入った「%」の点。新しい順。"""
    if not USAGE_LOG.exists():
        return []
    out = []
    for line in USAGE_LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if row.get("used_percent") is None or not row.get("fetched_at"):
            continue
        if row.get("window_id") != "seven_day":
            continue
        out.append(row)
    out.sort(key=lambda r: r.get("fetched_at") or "", reverse=True)
    return out


def _births_between(rows: list[dict], start: datetime, end: datetime) -> int:
    """`start`〜`end` に生まれたセッションの数。**セッションごとに1回だけ数える。**"""
    seen = {}
    for r in rows:
        sid, born = r.get("session_id"), _parse_iso(r.get("born_at"))
        if sid and born and sid not in seen:
            seen[sid] = born
    return sum(1 for b in seen.values() if start <= b <= end)


def pace(now: datetime | None = None) -> dict | None:
    """いまの速さと、持続できる1周の間隔。目盛りが無ければ None。

    **2点以上あれば「区間」を見る**（2026-08-15 夜）。枠の頭からの通算は、
    鎖が止まっていた時間と、軽い回と重い回を全部ならしてしまう。
    **これから先を決めるのに要るのは、直近の1周がいくらか**のほう。
    ただし%は整数でしか読めないので、区間が短いと差の誤差が大きい
    （`QUANT_FULL_PCT`）。**信頼できるぶんだけ区間へ寄せ、残りは通算に置く。**
    """
    now = now or datetime.now(timezone.utc)
    anchors = _anchors()
    if not anchors:
        return None
    a = anchors[0]
    resets = _parse_iso(a.get("resets_at_iso"))
    at = _parse_iso(a.get("fetched_at"))
    if not resets or not at:
        return None
    start = resets - WINDOW_SPAN["seven_day"]
    hours = (at - start).total_seconds() / 3600
    if hours <= 0:
        return None
    used = float(a["used_percent"])
    rows = _load()
    births = _births_between(rows, start, at)

    rate = used / hours                       # %/時（枠の頭からの通算）
    per_lap_cum = used / births if births else None

    # --- 直近の区間（同じ枠の中の、1つ前の点との差） --------------------
    seg = None
    for prev in anchors[1:]:
        p_at, p_reset = _parse_iso(prev.get("fetched_at")), _parse_iso(prev.get("resets_at_iso"))
        if not p_at or p_reset != resets or p_at >= at:
            continue                          # 別の枠／同時刻の点は使えない
        s_hours = (at - p_at).total_seconds() / 3600
        s_used = used - float(prev["used_percent"])
        s_births = _births_between(rows, p_at, at)
        if s_hours <= 0 or s_used < 0:
            continue
        seg = {
            "from_at": p_at, "from_used": float(prev["used_percent"]),
            "hours": s_hours, "used": s_used, "births": s_births,
            "rate": s_used / s_hours,
            "per_lap": (s_used / s_births) if s_births else None,
            # %が整数 ＝ 2点の差は ±1.0%。区間の見立てが取りうる幅。
            "rate_lo": max(0.0, s_used - 1.0) / s_hours,
            "rate_hi": (s_used + 1.0) / s_hours,
        }
        break

    # --- この先に許される速さ（残りを残り時間で割る） --------------------
    # **ここが基準線。** 0.595（枠の頭から見た値）ではない。
    #
    # **そして「残り」は目盛りの時刻ではなく `now` から数えること**（2026-08-21）。
    # 長らく `at`（目盛りを取った時刻）で割っていました。目盛りは人手でしか
    # 入らないので**必ず古くなり**、そのぶん「残り%」を多く・「残り時間」も
    # 多く見積もります。**間違いは必ず「速すぎてよい」の側に出ます。**
    #   実測 08/21 13:0x: 目盛りは 08:07 の 92%。古い式は 8% ÷ 23時間 = 0.350 %/時
    #   → 持続できる間隔 **69分**。5時間ぶん進めて数え直すと
    #   6.3% ÷ 19.4時間 = 0.325 %/時 → **75分**。**9% 速く走らせていた。**
    # CLAUDE.md は「目盛りが古くなる」と警告していましたが、
    # **古い目盛りから出した『許される速さ』も同じだけ古い**とは書いていません。
    elapsed = max(0.0, (now - at).total_seconds() / 3600)
    carry_rate = seg["rate"] if seg else rate      # 区間があれば直近の速さで運ぶ
    used_now = min(100.0, used + elapsed * carry_rate)
    left_hours = (resets - now).total_seconds() / 3600
    forward_rate = ((100.0 - used_now) / left_hours) if left_hours > 0 else 0.0

    # --- 1周いくらか（区間へ寄せる。寄せる量は Δ% の大きさで決める） -----
    weight, per_lap = 0.0, per_lap_cum
    if seg and seg["per_lap"] and per_lap_cum:
        weight = max(0.0, min(1.0, seg["used"] / QUANT_FULL_PCT))
        per_lap = weight * seg["per_lap"] + (1.0 - weight) * per_lap_cum

    floor = None
    if per_lap:
        if forward_rate <= 0:
            # **枠を使い切っている。** ここで None（＝待たない）を返すと、
            # 閉じた枠に鎖を突っ込み続けることになる。天井まで空ける。
            floor = FLOOR_MAX_CLAMP
        else:
            floor = max(FLOOR_MIN_CLAMP,
                        min(FLOOR_MAX_CLAMP, per_lap / forward_rate * 60))

    # 尽きる時刻も `now` から。ここも目盛りの時刻から引いていました。
    exhaust = (now + timedelta(hours=(100.0 - used_now) / carry_rate)
               if carry_rate > 0 and used_now < 100.0
               else (now if used_now >= 100.0 else None))
    return {
        "anchor_at": at, "anchor_used": used, "anchor_source": a.get("source", ""),
        "window_start": start, "window_reset": resets,
        "hours": hours, "births": births,
        "rate": rate, "per_lap": per_lap, "per_lap_cum": per_lap_cum,
        "seg": seg, "seg_weight": weight,
        "forward_rate": forward_rate, "left_hours": left_hours,
        "used_now": used_now, "carry_rate": carry_rate, "carried_hours": elapsed,
        "floor_min": floor,
        "exhaust_at": exhaust,
        "dead_hours": ((resets - exhaust).total_seconds() / 3600
                       if exhaust and exhaust < resets else 0.0),
        "over": (rate / forward_rate - 1.0) if forward_rate > 0 else 0.0,
        "over_flat": rate / SUSTAIN_PCT_PER_HOUR - 1.0,
        "stale_hours": (now - at).total_seconds() / 3600,
    }


def recommended_floor_minutes(now: datetime | None = None) -> float | None:
    """次の子を立ててよくなるまでの、誕生から誕生までの最短間隔（分）。

    **`sibling_check.py` がこれを読んで §6 (f) を止める。**
    目盛りが無ければ None を返す —— **そのときは止めない。**
    測れないことを理由に鎖を止めるのは、8/12 の58時間と同じ損失になる。
    """
    p = pace(now)
    return p["floor_min"] if p else None


def pace_report(now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    p = pace(now)
    print("  **速さ**（尽きる時刻で読む。残量では読まない）")
    if not p:
        print("    **目盛りがありません。** `data/usage.jsonl` に %の点が要ります。")
        print("    `rate_limit_info` に % は入らないので、**外から入れるしかない**。")
        print("    形式: {\"fetched_at\":ISO,\"window_id\":\"seven_day\","
              "\"used_percent\":N,\"resets_at_iso\":ISO}")
        return
    print(f"    目盛り: {p['anchor_at'].astimezone(JST):%m/%d %H:%M} JST で "
          f"**{p['anchor_used']:.0f}%**"
          f"{'（' + p['anchor_source'] + '）' if p['anchor_source'] else ''}")
    if p["stale_hours"] > 24:
        print(f"    [!] **この目盛りは {p['stale_hours'] / 24:.1f}日前です。**"
              "新しい%が入るまで、下の数字は古い前提で動いています")
    print(f"    枠: {p['window_start'].astimezone(JST):%m/%d %H:%M} → "
          f"{p['window_reset'].astimezone(JST):%m/%d %H:%M} JST")
    print(f"    通算 {p['rate']:.3f} %/時（{p['hours']:.1f}時間で {p['anchor_used']:.0f}%）")
    seg = p["seg"]
    if seg:
        print(f"    直近の区間 {seg['from_at'].astimezone(JST):%m/%d %H:%M}→"
              f"{p['anchor_at'].astimezone(JST):%H:%M}: "
              f"{seg['used']:+.0f}% / {seg['hours']:.2f}時間 = "
              f"**{seg['rate']:.3f} %/時**")
        print(f"      **%は整数でしか読めないので差は ±1%** → 区間の幅は "
              f"[{seg['rate_lo']:.3f}, {seg['rate_hi']:.3f}] %/時。"
              f"{'**この幅では通算と区別がつきません**' if seg['rate_lo'] <= p['rate'] <= seg['rate_hi'] else '通算とは別の値です'}")
    else:
        print("    **区間が引けません**（同じ枠の中に2点目がない）。通算だけで決めています")
    if p["carried_hours"] >= 0.1:
        print(f"    いま（推定）: **{p['used_now']:.1f}%** "
              f"＝ 目盛りの {p['anchor_used']:.0f}% を {p['carry_rate']:.3f} %/時で "
              f"{p['carried_hours']:.1f}時間ぶん運んだもの")
        print(f"      **残りは目盛りの時刻からではなく、いまから数えること。**"
              f"目盛りは人手でしか入らないので必ず古くなり、"
              f"**古いまま割ると必ず「速すぎてよい」側に外れます**（2026-08-21 に 9% ずれた）")
    print(f"    この先に許される速さ: **{p['forward_rate']:.3f} %/時**"
          f"（残り {100 - p['used_now']:.1f}% ÷ 残り {p['left_hours']:.1f}時間）"
          f"   → 通算は **{p['over']:+.0%}**")
    print(f"      ＊枠の頭から見た 0.595 %/時ではなく、**すでに使ったぶんを引いた線**を"
          f"基準にしています（追い越したぶんは取り返せない）")
    if p["births"]:
        if seg and seg["per_lap"]:
            print(f"    1周いくらか: 通算 {p['per_lap_cum']:.3f}%（{p['births']}周）／"
                  f"区間 {seg['per_lap']:.3f}%（{seg['births']}周）"
                  f" → 区間に **{p['seg_weight']:.0%}** 寄せて **{p['per_lap']:.3f}%**")
        else:
            print(f"    {p['hours']:.1f}時間で誕生 {p['births']} 件 "
                  f"→ **1周 {p['per_lap']:.3f}%**")
        print(f"    持続できる間隔（誕生から誕生）: **{p['floor_min']:.0f}分**")
    else:
        print("    **誕生を1件も数えられていません。**`quota.jsonl` が薄すぎます")
    if p["exhaust_at"]:
        if p["dead_hours"] > 0:
            print(f"    このままなら 100% は "
                  f"{p['exhaust_at'].astimezone(JST):%m/%d %H:%M} JST"
                  f" → **リセットまで {p['dead_hours']:.0f}時間、鎖が止まります**")
            print(f"      ＊**「このまま」＝ 直近の速さ {p['carry_rate']:.3f} %/時 のまま**、"
                  "という意味です。**間隔を変えた直後のこの行は、まだ前の速さを見ています** ——"
                  "新しい点が積まれるまで動きません。"
                  "**変えた効きを見るのは、1つ上の『持続できる間隔』のほう。**")
        else:
            print(f"    このままならリセットまで届きます"
                  f"（100% 到達は {p['exhaust_at'].astimezone(JST):%m/%d %H:%M} JST）")


def report(now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    rows = _load()
    if not rows:
        print("  **まだ1点も積んでいません。** 使用量は見えていません。")
        print("  取り方: `list_sessions` を叩いて、返りを保存してから")
        print("          `python scripts/quota.py --ingest <file>`")
        print("  **空欄を「余裕がある」と読まないこと。**")
        return

    periods = _periods(rows)

    # --- いまの姿 -------------------------------------------------------
    live = [r for r in rows if r.get("status")]
    latest = max(live, key=lambda r: r["seen_at"]) if live else None
    if latest:
        seen = _parse_iso(latest["seen_at"])
        age = now - seen
        resets = _parse_iso(latest.get("resets_at"))
        print(f"  **いま効いている枠: {latest['window']} "
              f"／ {STATUS_JA.get(latest['status'], latest['status'])}**")
        if resets:
            left = resets - now
            if left.total_seconds() > 0:
                print(f"    リセットまで {_fmt_span(left)}"
                      f"（{resets.astimezone(JST):%m/%d %H:%M} JST）")
            else:
                print(f"    **この読みの枠はもうリセット済み**"
                      f"（{resets.astimezone(JST):%m/%d %H:%M} JST）。取り直すこと")
        print(f"    この読みは {_fmt_span(age)}前の観測"
              f"（{seen.astimezone(JST):%m/%d %H:%M} JST）")
        if age > timedelta(hours=2):
            print("    [!] **古い読みです。**`list_sessions` を叩いて取り直すこと")

    # --- 枠ごとの遷移 ---------------------------------------------------
    # **残量%が取れない以上、目盛りはここにしかない。**
    # 「いつ警告帯に入り、いつ閉じたか」を枠1回ぶんずつ残す。
    print("\n  **枠ごとの遷移**（%が取れないので、これが目盛りになる）")
    shown = 0
    for (window, resets_iso), items in sorted(
            periods.items(), key=lambda kv: kv[0][1], reverse=True):
        if shown >= 6:
            break
        shown += 1
        resets = _parse_iso(resets_iso)
        span = WINDOW_SPAN.get(window)
        start = resets - span if (resets and span) else None
        tail = "（進行中）" if resets and resets > now else ""
        print(f"    {window} → {resets.astimezone(JST):%m/%d %H:%M} JST{tail}")

        first_seen = {}
        for r in items:
            st = r.get("status")
            if st and st not in first_seen:
                first_seen[st] = r["seen_at"]
        if not first_seen:
            print("      （状態の読みなし）")
            continue
        for st in STATUS_ORDER:
            if st not in first_seen:
                continue
            at_iso = first_seen[st]
            at = _parse_iso(at_iso)
            frac = ""
            if start and span:
                pct = (at - start).total_seconds() / span.total_seconds() * 100
                frac = f" ／ 枠の {pct:.0f}% 経過時点"
            print(f"      {STATUS_JA.get(st, st)} 初出 "
                  f"{at.astimezone(JST):%m/%d %H:%M}{frac}")
            out_tok, all_tok, blind, spanning = _tokens_upto(rows, start, at_iso)
            if all_tok:
                note = []
                if blind:
                    note.append(f"{blind}行は消費量なし")
                if spanning:
                    note.append(f"{spanning}セッションは枠をまたぐので除外")
                tail = f"（{'／'.join(note)}）" if note else ""
                print(f"        そこまでに見えた消費: 出力 {out_tok:,} "
                      f"／ 総計 {all_tok:,}{tail}")

    # --- 目盛りが決まったか ---------------------------------------------
    closed = [(w, r) for (w, r), items in periods.items()
              if any(i.get("status") == "rejected" for i in items)]
    print()
    if closed:
        print(f"  **閉じた枠を {len(closed)} 回ぶん観測しています。**")
        print("    ここが増えるほど「どれだけ使うと閉じるか」の下限が絞れる。")
    else:
        print("  **まだ閉じた枠を観測していません。** 分母は不明のまま。")
        print("    `rejected` を1回でも捕まえるまで、目盛りは決まりません。")

    blind_rows = sum(1 for r in rows if not r.get("tokens"))
    print(f"  積んだ点: {len(rows)} 件"
          f"（うち消費量が入っていない行 {blind_rows} 件）")
    if blind_rows:
        print("    **`usage` は全部の行には入りません。**"
              "消費量の合計は必ず過小。下限として読むこと。")

    print()
    pace_report(now)


#: 週枠のリセット曜日と時刻（JST）。**画面の「リセット: 土 7:00」がこれ。**
#: 変わったら、ここではなく画面のほうが正です（`--resets` で上書きできます）。
WEEKLY_RESET_WEEKDAY = 5   # 月=0 … 土=5
WEEKLY_RESET_HOUR = 7


def _next_weekly_reset(at: datetime) -> datetime:
    """`at` の後に来る、最初の土曜 07:00 JST。"""
    day = at.replace(hour=WEEKLY_RESET_HOUR, minute=0, second=0, microsecond=0)
    ahead = (WEEKLY_RESET_WEEKDAY - at.weekday()) % 7
    if ahead == 0 and at >= day:
        ahead = 7
    return day + timedelta(days=ahead)


def record_gauge(week_pct: int, at_text: str, session_pct: int | None = None,
                 session_in_min: int | None = None, resets_text: str | None = None,
                 note: str = "") -> int:
    """**オーナーの画面の%を、1行で積む**（2026-08-19 21:2x にオーナー指示で足した）。

    ## なぜ要るか

    **%はこの機械からは読めません。** `list_sessions` の `rate_limit_info` は
    `allowed` / `warning` / `rejected` しか返さず、残り%も分母も入っていません
    （このファイルの冒頭）。**唯一の目盛りは、オーナーの画面の数字**です。

    ところがその1点を積む手は、**`data/usage.jsonl` に手で JSONL を書くこと**でした。
    結果、**目盛りは 08/16 13:00 の 22% で 3.3日ぶん止まり**、そのあいだ機械は
    「22%＋外挿」で間隔を決めていました。実測が入ったら **75%** で、
    **持続できる間隔は 41分 → 65分**（この差のぶんだけ速く走っていた）。

    **書き写す手が重いと、正しい手順でも運用が落ちます。** だから1行にします。

        python scripts/quota.py --gauge 75 --at "08/19 21:21" --session 2 --session-in 288

    ## 何を渡すか（**画面の字をそのまま**）

        --gauge       「週間の制限 / すべてのモデル」の**使用済み%**
        --at          画面の時刻（`MM/DD HH:MM` か `YYYY-MM-DD HH:MM`。JST）
        --session     「現在のセッション」の%（**5時間枠**。週の判断には使いません）
        --session-in  「N時間M分後にリセット」を**分に直した数**
        --resets      週枠のリセット時刻を明示したいとき（既定は次の土 07:00 JST）

    **`--session` を週枠と混ぜないこと。** 分母が別です（このファイルの冒頭）。
    """
    at_text = at_text.strip()
    for fmt in ("%Y-%m-%d %H:%M", "%m/%d %H:%M", "%Y/%m/%d %H:%M"):
        try:
            at = datetime.strptime(at_text, fmt)
            break
        except ValueError:
            continue
    else:
        print(f"[gauge] 時刻を読めません: {at_text!r}（例: '08/19 21:21' / '2026-08-19 21:21'）")
        return 1
    if at.year == 1900:
        # `MM/DD` だけのときは、いまの年を当てる。**年を跨いだ回はフルで書くこと。**
        at = at.replace(year=datetime.now(JST).year)
    at = at.replace(tzinfo=JST)

    if resets_text:
        try:
            resets = datetime.strptime(resets_text, "%Y-%m-%d %H:%M").replace(tzinfo=JST)
        except ValueError:
            print(f"[gauge] --resets は 'YYYY-MM-DD HH:MM' で: {resets_text!r}")
            return 1
    else:
        resets = _next_weekly_reset(at)

    rows = [{
        "fetched_at": at.isoformat(timespec="seconds"),
        "window_id": "seven_day",
        "used_percent": int(week_pct),
        "remaining_percent": 100 - int(week_pct),
        "resets_at_iso": resets.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": "owner-manual",
        "note": note or "オーナーの画面から（`quota.py --gauge`）",
    }]
    if session_pct is not None:
        row = {
            "fetched_at": at.isoformat(timespec="seconds"),
            "window_id": "five_hour",
            "used_percent": int(session_pct),
            "remaining_percent": 100 - int(session_pct),
            "source": "owner-manual",
            "note": "同じ画面の『現在のセッション』。**週枠の判断には使わない**（分母が別）",
        }
        if session_in_min is not None:
            r5 = at + timedelta(minutes=int(session_in_min))
            row["resets_at_iso"] = r5.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        rows.append(row)

    USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with USAGE_LOG.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[gauge] 積みました: {at:%m/%d %H:%M} JST で **{week_pct}%**"
          + (f"（5時間枠 {session_pct}%）" if session_pct is not None else "")
          + f" → {USAGE_LOG}")
    print()
    pace_report()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ingest", metavar="FILE",
                    help="MCP の返り（list_sessions / get_session）を読んで積む。- で標準入力")
    ap.add_argument("--pace", action="store_true",
                    help="速さだけを出す（§6 (f) の間隔を決めるとき）")
    ap.add_argument("--gauge", metavar="週%", type=int,
                    help="**オーナーの画面の%%を1行で積む**（`--at` と対）。"
                         "『週間の制限／すべてのモデル』の使用済み%%")
    ap.add_argument("--at", metavar="時刻", help="画面の時刻（`MM/DD HH:MM` か `YYYY-MM-DD HH:MM`・JST）")
    ap.add_argument("--session", metavar="%", type=int, help="『現在のセッション』の%%（5時間枠）")
    ap.add_argument("--session-in", metavar="分", type=int, help="『N時間M分後にリセット』を分に直した数")
    ap.add_argument("--resets", metavar="時刻", help="週枠のリセットを明示（既定は次の土 07:00 JST）")
    ap.add_argument("--note", metavar="文", default="", help="その点に添える1行")
    args = ap.parse_args()

    if args.gauge is not None:
        if not args.at:
            ap.error("--gauge には --at が要ります（画面の時刻。あとから積むと速さが狂います）")
        return record_gauge(args.gauge, args.at, args.session, args.session_in,
                            args.resets, args.note)
    if args.at or args.session is not None:
        ap.error("--at / --session は --gauge と一緒に使ってください")

    if args.pace and not args.ingest:
        pace_report()
        return 0

    if args.ingest:
        text = (sys.stdin.read() if args.ingest == "-"
                else Path(args.ingest).read_text(encoding="utf-8"))
        warn = self_check(text)
        added, updated = ingest(text)
        print(f"積みました: 新規 {added} 件 / 更新 {updated} 件 → {LOG}")
        if warn:
            print(warn)
        print()

    report()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
