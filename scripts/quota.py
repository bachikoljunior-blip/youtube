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
#
# ## **上の歯止めが 90分 だったあいだ、この計器は「測った」と言えていませんでした**
# ##（2026-09-01・最適化の回に撃って直した）
#
# `pace()` は `per_lap / forward_rate` で間隔を出しますが、**その答えが
# 歯止めより大きいときは、返るのは歯止めの定数のほう**です。それでも
# `next_round.py` は `間隔 90分（quota.py の実測）` と印字していました ——
# **90 は実測ではなく、`FLOOR_MAX_CLAMP` そのもの**です。
# **`density` の ×10^9 が `view_cap = 10` で切られていたのと同じ形**
# （`scripts/eta.py` の `LEVER_EFFECT_KEY`）——**倍率が腕に届く前に切られ、
# 切られたことが呼ぶ側に伝わっていませんでした。**
#
# この回に撃って出た数（本番と同じ道）::
#
#     per_lap 36.500%  forward_rate 0.126 %/時
#       → 生の間隔 **17,382分（289.7時間）** …… 歯止めで **90分**（**×193 切られた**）
#
# 生のほうが桁違いなのは、**誕生が数え落とされていた**からです
# （`_births_between()` の註）。**2つの欠陥が打ち消し合って、
# たまたま「速すぎる側」に着地していました。**
#
# **上を 720分（12時間）へ動かします。** 歯止めの役目は「計器が壊れても
# 鎖を止めない」ことなので、**止まらない条件のほうから決めること** ——
# オーナーの固定規則は **1日1本**（`src/house_rule.py`）なので、
# 鎖は**1日に最低2回 起きれば規則を守れます**。720分 はその線です。
# **90分 には、そういう根拠がありませんでした。**
#
# **覆る条件**: 1日1本 の規則が変わったら、この 720 も測り直すこと。
FLOOR_MIN_CLAMP, FLOOR_MAX_CLAMP = 10.0, 720.0

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


#: 目盛りの `resets_at_iso` は**手で写されます。** 同じ枠なのに 21:59 と 22:00 が
#: 混ざっており（実測 `data/usage.jsonl` 09/01〜09/02）、`==` で比べると
#: **同じ枠の2点が「別の枠」に化けて区間が引けなくなります。** 分だけ許す。
WINDOW_MATCH_TOL = timedelta(minutes=15)


def _same_window(r1: datetime | None, r2: datetime | None) -> bool:
    """2つの `resets_at` が同じ枠を指しているか（写し違いの分は許す）。"""
    return bool(r1 and r2 and abs(r1 - r2) <= WINDOW_MATCH_TOL)


def _gauge_reset(anchors: list[dict]) -> tuple[datetime, float] | None:
    """**枠が動かないまま、目盛りだけが戻された時刻の下限**を返す。

    2026-09-02 10:43 JST に踏みました。同じ `resets_at`（09/05 07:00 JST）のまま、
    目盛りが **73% → 3%** に戻っています（オーナーの画面でリセットされた）。
    `pace()` は枠の頭を `resets - 7日` ＝ **08/29 06:59** から取るので、

        分子  リセット後の **3%**（＝ 09/01 11:55 以降のぶんだけ）
        分母  08/29 から数えた **99.7時間・58周**

    と**窓が食い違い**、1周 **0.052%** ＝ 持続できる間隔 **10分** に潰れました。
    通算 0.030 %/時・尽きるのは 01/14、も同じ食い違いから出ています。
    **09/01 に直した「歯止めが実測を潰す」と同じ形です**（あちらは `clip`、
    こちらは**窓**）。

    返すのは `(下限, リセット前の%)`。リセットの瞬間は
    **(1つ前の点, いまの点] の間**にあり、どこかは測れません。
    **下限を返すのは、窓をいちばん広く ＝ 周をいちばん多く取る側**で、
    `per_lap` は**最小**に出ます ＝ **速すぎる側**。だから `pace()` は
    これを**下限としてだけ**使い、リセット前に測れていた `per_lap` と
    **大きいほうを採ります**（1周の重さは、枠が戻っても軽くなりません）。

    **覆る条件**: 目盛りが機械から読めるようになったら（`rate_limit_info` に
    % が入る）、下限ではなくリセットの時刻そのものが取れます。
    """
    if len(anchors) < 2:
        return None
    a = anchors[0]
    resets = _parse_iso(a.get("resets_at_iso"))
    if not _parse_iso(a.get("fetched_at")) or not resets:
        return None

    # **いちばん新しい1組だけを見ないこと**（2026-09-02 に自分で踏みかけた）。
    #     直前の点だけを見て「増えている ＝ 普通の区間」で打ち切ると、
    #     **リセット後に2点目が入った瞬間に、窓が枠の頭へ戻ります** ——
    #     09/02 の実物で言えば、次に 18:00 の 10% が貼られた回で
    #     `(3% → 10%)` は増えているので `None` になり、分母がまた
    #     08/29 からの 60周 に戻る。**同じ食い違いが黙って再発します。**
    #     枠の中を**いちばん新しい落ち込みまで**さかのぼること。
    same = []
    for row in anchors:
        r_at = _parse_iso(row.get("fetched_at"))
        r_reset = _parse_iso(row.get("resets_at_iso"))
        if not r_at or not _same_window(r_reset, resets):
            continue
        same.append((r_at, float(row["used_percent"])))
    same.sort(key=lambda x: x[0], reverse=True)     # 新しい順

    for (newer_at, newer_used), (older_at, older_used) in zip(same, same[1:]):
        if older_at >= newer_at:
            continue                          # 同時刻の点は使えない
        if older_used > newer_used:           # 枠は同じ。なのに%が減った ＝ 戻された
            return older_at, older_used
    return None


def _per_lap_before(anchors: list[dict], at_or_before: datetime) -> dict | None:
    """**リセット前に測れていた「1周いくら」と「%/時」。**

    1周の重さは枠の残量とは無関係なので、枠が戻っても**この数は残ります。**
    リセット直後は新しい枠に点が1つしか無く、そこから出る `per_lap` は
    **下限**にしかなりません。**その下限より、直前に測れていた数のほうが大きければ
    そちらを採る** —— 枠が戻ったことを「1周が軽くなった」と読まないため。
    """
    for i, prev in enumerate(anchors):
        p_at = _parse_iso(prev.get("fetched_at"))
        p_reset = _parse_iso(prev.get("resets_at_iso"))
        if not p_at or p_at > at_or_before or not p_reset:
            continue
        p_used = float(prev["used_percent"])
        p_start = p_reset - WINDOW_SPAN["seven_day"]
        p_births = _laps_between(p_start, p_at)
        p_hours = (p_at - p_start).total_seconds() / 3600
        if not p_births or p_hours <= 0:
            return None
        cum, cum_rate = p_used / p_births, p_used / p_hours
        # リセット前の枠の中の、さらに1つ前の点との区間（あれば寄せる）
        for older in anchors[i + 1:]:
            o_at = _parse_iso(older.get("fetched_at"))
            o_reset = _parse_iso(older.get("resets_at_iso"))
            if not o_at or o_at >= p_at or not _same_window(o_reset, p_reset):
                continue
            o_used = float(older["used_percent"])
            s_used, s_births = p_used - o_used, _laps_between(o_at, p_at)
            s_hours = (p_at - o_at).total_seconds() / 3600
            if s_used < 0 or not s_births or s_hours <= 0:
                break
            w = max(0.0, min(1.0, s_used / QUANT_FULL_PCT))
            return {"at": p_at, "used": p_used,
                    "per_lap": w * (s_used / s_births) + (1.0 - w) * cum,
                    "rate": w * (s_used / s_hours) + (1.0 - w) * cum_rate}
        return {"at": p_at, "used": p_used, "per_lap": cum, "rate": cum_rate}
    return None


#: **実際に走った回が1行ずつ残る台帳**（`scripts/run_marker.py` が書く）。
#: 1行ごとの `session` は**サブ1体**で、**1周ではありません**（下の註）。
RUNS_LOG = ROOT / "data" / "runs.jsonl"

#: **親が「1周 立てた」と記録する台帳**（`scripts/next_round.py --record` が書く）。
#: `decide()` が待ち時間を測る単位はこの `round` なので、**間隔の分母もこれ**。
ROUNDS_LOG = ROOT / "data" / "rounds.jsonl"


def _laps_between(start: datetime, end: datetime) -> int:
    """`start`〜`end` に立った**周**の数（`rounds.jsonl` の `round` の別数）。

    ## **単位を間違えると、そのぶんまるごと速く回ります**（2026-09-01）

    `pace()` の `floor_min` を読むのは `next_round.decide()` で、あちらは
    **「前の周の開始から何分」**を `floor` と比べます ＝ **周から周**です。
    ところが `per_lap` の分母は長らく**サブの誕生数**でした。実測::

        枠 08/29 07:00 → 09/01 11:55 JST   周 **48**／サブ **109**  → 1周に 2.27体
        直近の区間 08/31 17:26 →           周 **21**／サブ  **55**  → 1周に 2.62体

    **1周は 2〜3体 立ちます**（`next_round.ROLES` が hourly と optimizer の
    2つ、そこから孫が出ることもある）。サブ単位の `per_lap` を周単位の門に
    渡していたので、**間隔は 2.6倍 短い側**に出ていました。

    実測（この回・区間 +20%）::

        サブ単位  20% ÷ 55体 = 0.364% → 174分
        周単位    20% ÷ 21周 = 0.952% → **456分**   ← `decide()` が要るのはこちら
        実際の間隔 18.5時間 ÷ 21周 = **53分**（＝ **8.6倍 速い**）

    **数え落としは安全側です。** 周を数え落とすと `per_lap` は過大 → 間隔は
    長くなります。だから足りないときは**サブ数へ落ちません**（サブ数は必ず
    周数より多く、`per_lap` を小さく ＝ **速すぎる側**に倒します）。

    **覆る条件**: `decide()` が待ちを周ではなくサブで測るようになったら、
    分母もサブへ戻すこと。検査は `tests/test_quota_births_from_runs.py`。
    """
    if not ROUNDS_LOG.exists():
        return 0
    seen: set[str] = set()
    try:
        lines = ROUNDS_LOG.read_text(encoding="utf-8").splitlines()
    except Exception:                                          # noqa: BLE001
        return 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:                                      # noqa: BLE001
            continue
        at = _parse_iso(row.get("at"))
        if not at or not (start <= at <= end):
            continue
        # `round` が無い古い行は、その行自体を1周として数える（時刻で代用）。
        seen.add(str(row.get("round") or row.get("at")))
    return len(seen)


def _births_from_runs(start: datetime, end: datetime) -> int:
    """`data/runs.jsonl` に**実際に印を残した**セッションの数。

    1行ごとの `session` は `session_XXX#agent_YYY` の形で、**回ごとに別**です。
    ここは重複を潰して数えるだけ。読めなければ 0（呼ぶ側が `max()` するので害はない）。
    """
    if not RUNS_LOG.exists():
        return 0
    seen: set[str] = set()
    try:
        lines = RUNS_LOG.read_text(encoding="utf-8").splitlines()
    except Exception:                                          # noqa: BLE001
        return 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:                                      # noqa: BLE001
            continue
        sid, at = row.get("session"), _parse_iso(row.get("at"))
        if sid and at and start <= at <= end:
            seen.add(sid)
    return len(seen)


def _births_between(rows: list[dict], start: datetime, end: datetime) -> int:
    """`start`〜`end` に生まれたセッションの数。**セッションごとに1回だけ数える。**

    ## **分母は「周」です。`quota.jsonl` はそれをほとんど数えていませんでした**
    ##（2026-09-01・最適化の回に撃って直した）

    `quota.jsonl` に誕生が入るのは、**誰かが `list_sessions` の返りを
    `--ingest` で写した回だけ**です。それは毎周ではありません。実測::

        枠 08/29 07:00 → 09/01 11:55 JST（76.9時間・使用 73%）
          `quota.jsonl` の誕生 …… **2件**  → 1周 36.500% → 生の間隔 289.7時間
          `rounds.jsonl` の周  …… **48件** → 1周  1.521% → 生の間隔  12.1時間

    **数え落とし自体は安全側です**（分母が小さい ＝ 1周が過大 ＝ 間隔が長い）。
    **危なかったのは、そのあと `FLOOR_MAX_CLAMP` が 289.7時間 を 90分 へ
    叩き落としていたこと**で、`next_round.py` はそれを
    `間隔 90分（quota.py の実測）` と印字していました —— **90 は定数**です。
    周単位で数え直した真値は **459分**（直近の区間・21周で +20%）なので、
    **鎖は 5.1倍 速い側で回っていました。**

    だから**周が数えられるならそれを採り、駄目なときだけ `quota.jsonl` へ
    落ちます**（`_laps_between()`）。**サブの誕生数（`runs.jsonl`・109件）へは
    落ちません** —— 1周に 2〜3体 立つので、あれを分母にすると `per_lap` が
    小さくなり、**速すぎる側**へ倒れます。

    **覆る条件**: `next_round.py` が `--record` を書かなくなったら、
    `_laps_between()` が 0 を返して元の `quota.jsonl` の数へ戻ります
    （検査は `tests/test_quota_births_from_runs.py`）。
    """
    seen = {}
    for r in rows:
        sid, born = r.get("session_id"), _parse_iso(r.get("born_at"))
        if sid and born and sid not in seen:
            seen[sid] = born
    from_quota = sum(1 for b in seen.values() if start <= b <= end)
    # **周が数えられるなら、それが分母**（`_laps_between()` の註）。
    #     数えられない回だけ `quota.jsonl` の誕生へ落ちます —— あれも数え落とし
    #     ますが、**数え落としは間隔を長くする側**なので、鎖は速くなりません。
    return _laps_between(start, end) or from_quota


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
    rows = _load()
    # **枠が動かないまま目盛りだけ戻されたら、分母もそこから数え直すこと**
    # （2026-09-02。`_gauge_reset()` に実測）。ここを `resets - 7日` のままに
    # すると、分子は**リセット後のぶんだけ**・分母は**枠の頭からの全部**になり、
    # 1周が 0.052% ＝ 間隔 10分 まで潰れます。**窓を揃える。**
    reset = _gauge_reset(anchors)
    reset_at, reset_from = (reset if reset else (None, None))
    gauge_start = resets - WINDOW_SPAN["seven_day"]
    start = max(gauge_start, reset_at) if reset_at else gauge_start
    hours = (at - start).total_seconds() / 3600
    if hours <= 0:
        return None
    used = float(a["used_percent"])
    births = _births_between(rows, start, at)
    # **1周に何体 立っているか**（診断。分母には使いません —— `_laps_between()` の註）。
    subs = _births_from_runs(start, at)

    # **リセット直後は `hours`／`births` がどちらも上限**（窓の下限を採っている）
    # なので、そこから出る `rate` も `per_lap` も**下限**にしかなりません。
    # リセット前に測れていた数を床として当てる（下の `*_floored`）。
    pre = _per_lap_before(anchors, reset_at) if reset_at else None

    rate_raw = used / hours                   # %/時（測った窓の通算）
    rate, rate_floored = rate_raw, False
    if pre and pre["rate"] > rate:
        rate, rate_floored = pre["rate"], True
    per_lap_cum = used / births if births else None

    # --- 直近の区間（同じ枠の中の、1つ前の点との差） --------------------
    seg = None
    for prev in anchors[1:]:
        p_at, p_reset = _parse_iso(prev.get("fetched_at")), _parse_iso(prev.get("resets_at_iso"))
        if not p_at or not _same_window(p_reset, resets) or p_at >= at:
            continue                          # 別の枠／同時刻の点は使えない
        if reset_at and p_at <= reset_at:
            continue                          # **リセットをまたぐ差は「使った量」ではない**
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
    carry_rate = seg["rate"] if seg else rate      # 区間があれば直近の速さで運ぶ

    # --- **目盛りの枠が、もう閉じていることがある**（2026-08-22 07:2x に踏んだ） ---
    # 目盛りは人手でしか入らないので、**枠のリセットをまたいでも古いまま残ります。**
    # ここは長らく「目盛りの枠 ＝ いまの枠」を前提にしていて、
    # またいだ瞬間に `left_hours` が**負**になり、こう出ていました:
    #
    #     枠: 08/15 07:00 → 08/22 07:00 JST     ← **07:00 に閉じ終わっている**
    #     いま（推定）: 97.3%
    #     この先に許される速さ: 0.000 %/時（残り 2.7% ÷ 残り **-0.3時間**）
    #
    # そして `forward_rate <= 0` の枝が `floor = FLOOR_MAX_CLAMP` を返します。
    # **枠の中で使い切ったときはそれが正しい**（閉じた枠に鎖を突っ込まない）。
    # **またいだ後は逆です** —— 枠は 0% から始まっているのに、
    # 鎖は**いちばん広い間隔まで開かれ**、`sibling_check` が次の子を止めます。
    # 直る条件は「オーナーが新しい%を貼ること」だけで、
    # **人の操作を待つ形が計器に埋まっていました**（CLAUDE.md はそれを禁じています）。
    #
    # **またいだら、枠のほうを送ること。** 新しい枠の使用済みは**測れていません**
    # （%はこの機械から読めない）ので、**0% から直近の速さで運んだ推定**に置きます。
    # 「凍らせて 0 と言う」でも「古い%を持ち越す」でもなく、**軌跡で埋める**。
    span = WINDOW_SPAN["seven_day"]
    win_start, win_reset, rolled = gauge_start, resets, 0
    while win_reset <= now:
        win_start, win_reset = win_reset, win_reset + span
        rolled += 1
    if rolled:
        # 新しい枠の中には目盛りが1つも無い。頭を 0% として運ぶ。
        elapsed = max(0.0, (now - win_start).total_seconds() / 3600)
        used_now = min(100.0, elapsed * carry_rate)
    else:
        elapsed = max(0.0, (now - at).total_seconds() / 3600)
        used_now = min(100.0, used + elapsed * carry_rate)
    left_hours = (win_reset - now).total_seconds() / 3600
    forward_rate = ((100.0 - used_now) / left_hours) if left_hours > 0 else 0.0

    # --- 1周いくらか（区間へ寄せる。寄せる量は Δ% の大きさで決める） -----
    weight, per_lap = 0.0, per_lap_cum
    if seg and seg["per_lap"] and per_lap_cum:
        weight = max(0.0, min(1.0, seg["used"] / QUANT_FULL_PCT))
        per_lap = weight * seg["per_lap"] + (1.0 - weight) * per_lap_cum

    # --- **枠が戻った直後は、この数は下限にしかなりません** ---------------
    # リセットの瞬間は (1つ前の点, いまの点] のどこかで、`start` はその**下限**。
    # ＝ 窓をいちばん広く取っている ＝ 周をいちばん多く数えている ＝
    # `per_lap` は**最小**に出ます。**1周の重さは枠が戻っても軽くなりません**ので、
    # リセット前に測れていた数のほうが大きければ、そちらを採ること。
    per_lap_raw, per_lap_floored = per_lap, False
    if pre and (per_lap is None or pre["per_lap"] > per_lap):
        per_lap, per_lap_floored = pre["per_lap"], True

    # **切られたことを、呼ぶ側へ渡すこと**（2026-09-01）。
    #     長らくここは歯止めを掛けた数だけを返し、`next_round.py` はそれを
    #     `（quota.py の実測）` と印字していました。**歯止めは実測ではありません。**
    floor = floor_raw = None
    floor_clipped = ""
    if per_lap:
        if forward_rate <= 0:
            # **枠を使い切っている。** ここで None（＝待たない）を返すと、
            # 閉じた枠に鎖を突っ込み続けることになる。天井まで空ける。
            floor = floor_raw = FLOOR_MAX_CLAMP
            floor_clipped = "spent"      # 枠が尽きている（測って出た数ではない）
        else:
            floor_raw = per_lap / forward_rate * 60
            floor = max(FLOOR_MIN_CLAMP, min(FLOOR_MAX_CLAMP, floor_raw))
            if floor_raw > FLOOR_MAX_CLAMP:
                floor_clipped = "max"    # 測った数のほうが大きい ＝ **速すぎる側に着地**
            elif floor_raw < FLOOR_MIN_CLAMP:
                floor_clipped = "min"

    # 尽きる時刻も `now` から。ここも目盛りの時刻から引いていました。
    exhaust = (now + timedelta(hours=(100.0 - used_now) / carry_rate)
               if carry_rate > 0 and used_now < 100.0
               else (now if used_now >= 100.0 else None))
    return {
        "anchor_at": at, "anchor_used": used, "anchor_source": a.get("source", ""),
        "window_start": win_start, "window_reset": win_reset,
        "gauge_window_start": start, "gauge_window_reset": resets,
        "rolled": rolled,
        "hours": hours, "births": births, "subs": subs,
        "subs_per_lap": (subs / births) if births else None,
        "rate": rate, "per_lap": per_lap, "per_lap_cum": per_lap_cum,
        "seg": seg, "seg_weight": weight,
        "reset_at": reset_at, "reset_from": reset_from,
        "gauge_start": gauge_start, "pre": pre,
        "rate_raw": rate_raw, "rate_floored": rate_floored,
        "per_lap_raw": per_lap_raw, "per_lap_floored": per_lap_floored,
        "forward_rate": forward_rate, "left_hours": left_hours,
        "used_now": used_now, "carry_rate": carry_rate, "carried_hours": elapsed,
        "floor_min": floor,
        # **歯止めを掛ける前の数と、掛かったかどうか。**
        #     `floor_clipped == "max"` は「この計器は、返した数より
        #     **長い間隔が要ると測っている**」の意味です（＝ いまの鎖は速すぎる）。
        "floor_raw": floor_raw, "floor_clipped": floor_clipped,
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


#: 画面の%から間隔を伸ばすときの、伸ばす前の基準（分）と上限（分）。
#: 上限を **6時間**にしてあるのは、これを超えるとオーナーが画面を送ってから
#: 次の周までが1日に2回を切り、**目盛りのほうが先に腐る**からです。
GAUGE_FLOOR_BASE = 90.0
GAUGE_FLOOR_CAP = 360.0


def gauge_floor_minutes(base_min: float = GAUGE_FLOOR_BASE,
                        now: datetime | None = None) -> tuple[float, float] | None:
    """**誕生を数えられない回に、オーナーの画面の%だけで間隔を出す。**

    返り: `(間隔の分, 何倍に伸ばしたか)`。伸ばす必要が無ければ `None`。

    `recommended_floor_minutes()` は「誕生から誕生」を数えて出すので、
    `data/quota.jsonl` が薄い回は `None` を返します（2026-08-30 の実測: `births=0`）。
    **そこで長らく、呼ぶ側がそれぞれの定数（90分）へ落ちていました。**
    `next_round.py` は `FALLBACK_MIN`、`sibling_check.py` は下限そのものを外す。
    **定数は、速すぎるか遅すぎるかを言いません。**

    **画面の%からは、比なら出せます。** `pace()` は「いまの速さ」と
    「この先に許される速さ」を両方 持っているので、1周の重さが変わらないなら、
    **間隔をその比のぶんだけ伸ばせば釣り合います。**

        2026-08-30 15:40 JST の画面: 週 42%（枠 08/29 07:00 → 09/05 07:00）
          いまの速さ 1.286 %/時 ／ 許される 0.428 %/時 → 比 3.0
          → 90分 × 3.0 = **270分**
        このままなら 100% は 09/01 12:46 JST。**リセットまで90時間 鎖が止まる** ——
        止まるのはこのループだけではなく、**オーナー自身も使えなくなります。**

    **覆る条件**: (a) 誕生が数えられるようになったら `recommended_floor_minutes()`
    が先に返るので、ここは呼ばれません（そちらが正）。(b) 新しい画面で
    「いまの速さ ≦ 許される速さ」になれば `None` を返し、**自分で元に戻ります**
    （手で戻さないこと）。(c) 1周の重さを大きく変えたら比の前提が変わるので測り直すこと。
    """
    try:
        p = pace(now)
    except Exception:                                          # noqa: BLE001
        return None
    if not p:
        return None
    rate, fwd = p.get("rate"), p.get("forward_rate")
    if not rate or not fwd or fwd <= 0 or rate <= fwd:
        return None
    ratio = float(rate) / float(fwd)
    return min(GAUGE_FLOOR_CAP, float(base_min) * ratio), ratio


def effective_floor_minutes(base_min: float = GAUGE_FLOOR_BASE,
                            now: datetime | None = None) -> float | None:
    """**呼ぶ側が見るべき下限。** 誕生が数えられればそれ、駄目なら画面の比。

    `recommended_floor_minutes()` の契約（数えられなければ `None`）は変えません ——
    あれが `None` を返すことに意味を持たせている検査があります。
    **ここは「結局いくつで回すのか」を1か所に集めるための口**です。
    """
    got = recommended_floor_minutes(now)
    if got is not None:
        return float(got)
    g = gauge_floor_minutes(base_min, now)
    return g[0] if g else None


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
    if p["rolled"]:
        print(f"    [!] **その目盛りは閉じた枠のものです**"
              f"（{p['gauge_window_start'].astimezone(JST):%m/%d %H:%M} → "
              f"{p['gauge_window_reset'].astimezone(JST):%m/%d %H:%M} JST"
              f"{'・' + str(p['rolled']) + '枠ぶん前' if p['rolled'] > 1 else ''}）。"
              f"**いまの枠の使用済みは、1点も測れていません**")
        print(f"        → **下の%は目盛りの持ち越しではなく、"
              f"新しい枠の頭 0% から直近の速さ {p['carry_rate']:.3f} %/時 で"
              f"運んだ推定**です。**残り%を理由に作業を見送らないこと**")
    print(f"    枠: {p['window_start'].astimezone(JST):%m/%d %H:%M} → "
          f"{p['window_reset'].astimezone(JST):%m/%d %H:%M} JST"
          f"{'  ← **いまの枠**（目盛りの枠ではありません）' if p['rolled'] else ''}")
    if p.get("reset_at"):
        print(f"    [!] **枠は動かないまま、目盛りだけ戻されています** —— "
              f"{p['reset_at'].astimezone(JST):%m/%d %H:%M} JST の "
              f"**{p['reset_from']:.0f}%** → いまの **{p['anchor_used']:.0f}%**。"
              f" **分母もそこから数え直しています**"
              f"（枠の頭 {p['gauge_start'].astimezone(JST):%m/%d %H:%M} から数えると "
              f"分子はリセット後・分母は枠ぜんぶ ＝ **窓が食い違います**）")
        print(f"        リセットの瞬間は "
              f"({p['reset_at'].astimezone(JST):%m/%d %H:%M}, "
              f"{p['anchor_at'].astimezone(JST):%H:%M}] のどこかで、**測れません。**"
              f" 採っているのは**下限**（窓がいちばん広い ＝ 周がいちばん多い）なので、"
              f"下の通算と1周は**どちらも下限**です")
    print(f"    通算 {p['rate']:.3f} %/時（{p['hours']:.1f}時間で {p['anchor_used']:.0f}%）"
          + (f"   ← **測って出たのは {p['rate_raw']:.3f} %/時**（下限）。"
             f"リセット前に測れていた {p['pre']['rate']:.3f} %/時 を床にしています"
             f"（**枠が戻っても1周は軽くなりません**）"
             if p.get("rate_floored") else ""))
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
        if p["rolled"]:
            print(f"    いま（推定）: **{p['used_now']:.1f}%** "
                  f"＝ **いまの枠の頭 0%** を {p['carry_rate']:.3f} %/時で "
                  f"{p['carried_hours']:.1f}時間ぶん運んだもの"
                  f"（目盛りの {p['anchor_used']:.0f}% は**持ち越しません**）")
        else:
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
            print(f"    {p['hours']:.1f}時間で **{p['births']}周** "
                  f"→ **1周 {p['per_lap']:.3f}%**"
                  + (f"   ← **測って出たのは {p['per_lap_raw']:.3f}%**（下限）。"
                     f"床は {p['pre']['per_lap']:.3f}%"
                     f"（{p['pre']['at'].astimezone(JST):%m/%d %H:%M} までの実測）"
                     if p.get("per_lap_floored") and p.get("per_lap_raw") else ""))
        print(f"    持続できる間隔（**周から周**）: **{p['floor_min']:.0f}分**"
              + (f"   ＊分母は周 {p['births']}件（サブは {p['subs']}体 ＝ "
                 f"1周に {p['subs_per_lap']:.2f}体。**サブを分母にすると "
                 f"{p['subs_per_lap']:.1f}倍 速い側へ倒れます**）"
                 if p.get("subs_per_lap") else ""))
        if p.get("floor_clipped") == "max" and p.get("floor_raw"):
            print(f"      [!] **これは測った数ではありません** —— 測って出たのは "
                  f"**{p['floor_raw']:.0f}分**（{p['floor_raw'] / 60:.1f}時間）で、"
                  f"`FLOOR_MAX_CLAMP` の {FLOOR_MAX_CLAMP:.0f}分 で切られています"
                  f"（**×{p['floor_raw'] / FLOOR_MAX_CLAMP:.1f} 切られた**）。"
                  f" **切られたぶん、鎖は速すぎる側で回ります。**"
                  f" 歯止めを動かす前に、まず 1周 {p['per_lap']:.3f}% の分母"
                  f"（誕生 {p['births']}件）を疑うこと")
        elif p.get("floor_clipped") == "spent":
            print("      [!] **枠を使い切っています。** これは測った数ではなく、"
                  "歯止めの上限そのものです（閉じた枠に鎖を突っ込まないため）")
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
