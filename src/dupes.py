"""**自分で作った「繰り返し」を、公開される前に見つける。**

    from src import dupes
    dupes.report(videos)        # scripts/status.py が毎回叩く

## なぜ要るか（2026-08-16。**申し送りに6回出て、6回とも潰れていない項目です**）

YouTube のチャンネル収益化ポリシーは、これを**収益化の対象外**と書いています。

> テンプレートを使用して作成されたと思われるコンテンツや、**同じチャンネルの動画を
> 続けて数本視聴した後、繰り返しのように感じられる**可能性のあるコンテンツ

**収益化されなければ RPM がいくつでも収入はゼロ**なので、これは見栄えではなく
到達可能性そのものの条件です（`CLAUDE.md`「この作りの根幹」）。

8/15 23:0x に**同じテーマIDが2本ずつ予約に入る**事故があり、
`scripts/reschedule.py --list` が「同じテーマID」を印で出すようになりました。
**しかし、それでは足りません。** この回に実物46本を突き合わせると、
**テーマIDが違うのに中身が重なっている組が、予約の中に残っていました** ——

    _4zhMy-VIyg 08/16 09:00  年収500万から50万アップで手取りは35万9318円
    a1b2Nm6jN_0 08/24 09:00  社会保険料率で手取り増は**35万9318円**      ← 同じ金額
    8Yb181bZvU4 （予約なし）  年収50万アップで手取りは**35万9318円**増

    crO3FUvL2NI 08/17 09:00  医療費控除の足切りは10万円ではない 総所得160万で8万円
    LpgNOanBc-k 08/24 13:00  医療費控除 総所得160万なら**足切りは8万円**  ← 同じ前提・同じ答え

**テーマIDが違うので、既存の検出は1件も鳴りません。** そして
**視聴者が見るのはテーマIDではなく、画面に出る金額**です。

## 何を「重なり」と呼ぶか（**しきい値は掛け算してから置く**）

    強い  同じテーマID
    強い  同じ calc ＋ 片方の金額が**もう片方に全部入っている**（下の「包含」）
    弱い  同じ calc ＋ 金額が1つ以上ぶつかる（包含にはならない）
    弱い  同じ calc ＋ 同じ「答えの数」（日・か月・%・倍）が一致
    弱い  同じ calc の本が、**同じ日**に予約されている

### なぜ「1つでもぶつかったら強い」ではないのか（**最初そう書いて、実物で外れた**）

金額の一致だけを強いことにすると、**制度の名前に入っている数**で全部つながります。
実測では `fukugyo` の6本が、**全部 `20万円`**（＝「副業20万円ルール」という制度名）
で結ばれ、**32組のうち15組がこれ**でした。**本当の重なりが埋もれます。**

見たいのは「金額がぶつかったか」ではなく、
**「この本の数字は、もう一方の本が言っていないことを何か言っているか」**です。
だから**包含**で見ます —— 少ないほうの金額が全部、多いほうにも入っているとき。

    _4zhMy-VIyg  年収500万から50万アップで手取りは35万9318円   {500万, 50万, 35万9318}
    a1b2Nm6jN_0  社会保険料率で手取り増は35万9318円             {35万9318}   ← 全部入っている

    nK2SRMIqEF8  副業20万円 1円こえて手取り139,161円            {20万, 139161}
    IkGaQv1fQQA  副業20万1円で手取り15万9581円                  {20万1, 159581} ← 入っていない

包含でも、**共通が「丸い数1つだけ」なら弱いほうへ落とします**（有効数字2桁以下）。
`YHiigJ3Zpj4`（題の数字が `20万円` だけの長尺）が、`20万` を含む全部の本と
組になってしまうためです。**丸い数1つは、制度の名前でしかありません。**

### 相対差 0.5% を許す理由（実測）

    Vpjbt0XofmQ 一律手当と残業代 3年で **61万9898円**
    drkKm9fHW2M 残業代 一律手当の除外 3年で **61万9千円**   ← 差 0.14%
    8PMLfjjCe4w 失業給付 離職理由で **136万6500円** の差
    SsUYduA1dpg 失業給付 離職理由だけで **136万円** 差       ← 差 0.48%

**厳密一致だけにすると、この2組は永久に見つかりません。**
逆に 0.5% より広げると、同じ calc の中の別の事例まで巻き込みます
（傷病手当金の 286万7592円 と 46.8% のように、**本当に別の計算**が並ぶため）。

## 分かっている穴

- **題に出ていない重なりは見えません。** 見ているのは題の数字だけで、
  画面の中身は見ていません。**題は「その本の答え」なので、いちばん濃い1点**
  ではありますが、**全部ではありません**
- **calc が同じでも中身が別**の組は、弱いほうで鳴ります（傷病手当金の5本など）。
  **弱いほうは「止める」ではなく「並べて見る」ためのもの**です
- 数の読み取りは**題の書き方に依存します**（`35万9318円` は読めますが、
  `三十五万` は読めません）。実物の題は全部アラビア数字なので、いまは足ります
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
MARKER_RE = re.compile(r"\[t:([a-z0-9\-]+)\]")

# 数字＋桁（`35万9318` のように続けて書かれる）。小数も読む（`46.8%`）。
_TOKEN = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(億|万|千)?")
_SCALE = {"億": 10 ** 8, "万": 10 ** 4, "千": 10 ** 3, None: 1}
# **単位は長いものから見ること。** `か月` より先に `月` を見ると `31か月` を取り逃す。
_UNITS = ("円", "か月", "ヶ月", "カ月", "箇月", "%", "％", "日", "年", "歳", "人", "倍", "回", "割")

# 「答えの数」として突き合わせる単位。**歳と年は前提のほうなので入れません**
# （`45歳` `勤続10年` は条件であって、その本が出した答えではない）。
ANSWER_UNITS = {"か月", "%", "日", "倍"}

# 金額をこの額から下は見ない。**下を見ると `1円` `3日で1万` のような
# 前提側の端数が全部ぶつかります**（`20万1円` の `1` など）。
MIN_YEN = 10_000
# 丸めて書かれた題を拾うための相対差（上の docstring に実測がある）。
YEN_TOLERANCE = 0.005
# 有効数字がこれ以下の金額は「制度の名前に入っている丸い数」として扱う
# （`20万` `10万` `160万`）。**計算の答えは実測で6桁前後**（`35万9318`）。
ROUND_SIGDIGITS = 2


def numbers(text: str) -> list[tuple[float, str]]:
    """題から `(値, 単位)` を全部取り出す。単位が無ければ空文字。

    `35万9318円` は **1つの数**として読みます（`35` と `9318` ではない）。
    続けて書かれた桁は、**桁が小さくなる方向にだけ**つながります ——
    `年収500万から50万アップ` は 500万 と 50万 の2つで、5,500,000 ではありません。
    """
    out: list[tuple[float, str]] = []
    i = 0
    while i < len(text):
        if not _TOKEN.match(text, i):
            i += 1
            continue
        total = 0.0
        end = i
        last: float | None = None
        while True:
            m = _TOKEN.match(text, end)
            if not m:
                break
            scale = _SCALE[m.group(2)]
            if last is not None and scale >= last:
                break
            total += float(m.group(1).replace(",", "")) * scale
            last = scale
            end = m.end()
            if m.group(2) is None:
                break
        unit = ""
        for u in _UNITS:
            if text.startswith(u, end):
                unit, end = u, end + len(u)
                break
        out.append((total, {"ヶ月": "か月", "カ月": "か月", "箇月": "か月",
                            "％": "%"}.get(unit, unit)))
        i = max(end, i + 1)
    return out


def _yen(text: str) -> set[float]:
    """金額とみなす数。**`円` が付いていないものも数えます。**

    実物の題は `総所得160万で8万円` `年収500万から50万アップ` のように
    **途中の金額から `円` を落とします。** `円` を必須にすると、
    `crO3FUvL2NI` と `LpgNOanBc-k`（総所得160万・足切り8万円が両方一致）が
    **共通1つに見えて弱いほうへ落ちました。**
    単位が付いているもの（`日` `歳` `%` …）は金額ではないので除きます。
    """
    return {v for v, u in numbers(text) if u in ("円", "") and v >= MIN_YEN}


def _answers(text: str) -> set[tuple[float, str]]:
    return {(v, u) for v, u in numbers(text) if u in ANSWER_UNITS}


def _yen_close(a: float, b: float) -> bool:
    return abs(a - b) <= max(a, b) * YEN_TOLERANCE


def sigdigits(v: float) -> int:
    """末尾の 0 を落とした桁数。`200000` は 1、`1600000` は 2、`359318` は 6。"""
    n = int(round(v))
    if n == 0:
        return 0
    s = str(abs(n)).rstrip("0")
    return len(s) or 1


def _contained(small: set[float], big: set[float]) -> list[tuple[float, float]]:
    """`small` の全部が `big` に入っていれば、当たった組を返す（無ければ空）。

    **「1つでもぶつかったら」ではありません。** 少ないほうが**何も足していない**
    ときだけを重なりと呼びます（docstring の `fukugyo` 15組が理由）。

    **組で返すのは、丸さを両側で見るため**です。`20万円` と `20万1円` は
    0.5% の中に入りますが、**片方が丸ければ制度側の数**とみなします
    （`YHiigJ3Zpj4` の題の数字は `20万円` だけで、これを答えと読むと
    `20万1円` の本すべてと組になります）。
    """
    hits = []
    for a in small:
        m = [b for b in big if _yen_close(a, b)]
        if not m:
            return []
        hits.append((a, min(m)))
    return hits


def _calc_of(topic_id: str, topics: dict[str, str]) -> str:
    return topics.get(topic_id, "")


def rows_from_videos(videos: list[dict], topics: dict[str, str] | None = None) -> list[dict]:
    """`videos.list` の返り（または同じ形の dict）を、突き合わせる形に直す。"""
    topics = topics or {}
    rows = []
    for v in videos:
        sn = v.get("snippet", v)
        st = v.get("status", v)
        desc = sn.get("description", "") or ""
        m = MARKER_RE.search(desc)
        topic = m.group(1) if m else ""
        at = st.get("publishAt") or (
            sn.get("publishedAt") if st.get("privacyStatus") == "public" else None)
        rows.append({
            "id": v.get("id", ""),
            "title": sn.get("title", ""),
            "topic": topic,
            "calc": _calc_of(topic, topics),
            "at": at,
            "scheduled": bool(st.get("publishAt")),
        })
    return rows


def find(rows: list[dict]) -> list[dict]:
    """重なりの組を返す。**強いほうを先に**、それぞれ `kind` と理由つき。"""
    issues: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    def add(kind: str, strong: bool, a: dict, b: dict, why: str) -> None:
        key = (kind, *sorted((a["id"], b["id"])))
        if key in seen:
            return
        seen.add(key)
        issues.append({"kind": kind, "strong": strong, "a": a, "b": b, "why": why})

    by_topic: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r["topic"]:
            by_topic[r["topic"]].append(r)
    for topic, group in by_topic.items():
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                add("same-topic", True, a, b, f"テーマID `{topic}` が同じ")

    by_calc: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r["calc"]:
            by_calc[r["calc"]].append(r)

    for calc, group in by_calc.items():
        cache = [(r, _yen(r["title"]), _answers(r["title"])) for r in group]
        for i, (a, ay, aa) in enumerate(cache):
            for b, by, ba in cache[i + 1:]:
                small, big = (ay, by) if len(ay) <= len(by) else (by, ay)
                hit = _contained(small, big) if small else []
                # 共通が「丸い数1つだけ」なら制度の名前でしかない（`20万円ルール`）。
                if hit and (len(hit) > 1 or
                            min(sigdigits(x) for x in hit[0]) > ROUND_SIGDIGITS):
                    shown = '・'.join(f"{int(min(p)):,}円" for p in sorted(hit))
                    add("same-yen", True, a, b, f"`{calc}` で金額が入れ子（{shown}）")
                    continue
                loose = [x for x in ay for y in by if _yen_close(x, y)]
                if loose:
                    add("same-yen-loose", False, a, b,
                        f"`{calc}` で金額が1つぶつかる（{int(min(loose)):,}円ほど）")
                    continue
                shared = aa & ba
                if shared:
                    v, u = sorted(shared)[0]
                    add("same-answer", False, a, b,
                        f"`{calc}` で答えの数が同じ（{v:g}{u}）")

        by_day: dict[str, list[dict]] = defaultdict(list)
        for r in group:
            if r["scheduled"] and r["at"]:
                day = datetime.fromisoformat(
                    r["at"].replace("Z", "+00:00")).astimezone(JST).strftime("%m/%d")
                by_day[day].append(r)
        for day, same in by_day.items():
            for i, a in enumerate(same):
                for b in same[i + 1:]:
                    add("same-day", False, a, b, f"`{calc}` が {day} に2本")

    issues.sort(key=lambda x: (not x["strong"], x["kind"]))
    return issues


LEDGER = "data/uploaded.jsonl"


def ledger_rows(topics: dict[str, str] | None = None) -> list[dict]:
    """**手元の控え**（`data/uploaded.jsonl`）を、突き合わせる形で返す。

    ## なぜ手元に持つのか（2026-08-16 に、この門が実際にすり抜けられた）

    CLAUDE.md は「投稿済みは説明欄の `[t:テーマID]` から**チャンネル越しに
    復元する。ファイルに持たない**」と言っています。**そこは変えていません** ——
    どのテーマを次に作るか（`pick`）は今もチャンネルから決めます。理由も同じで、
    動画を消したときにファイルが嘘になるからです。

    **変えたのは、投稿の直前の門が見る先だけ**です。この回の実測:

        1本目  s-fukugyo-2 を止めた（既にある iTrogWVf4Eg と同じテーマID・同じ15万2100円）
        5分後  同じ s-fukugyo-2 が**通ってしまい**、Prw6AB9hOsY として予約に入った

    `iTrogWVf4Eg` は 8/22 09:00 に予約済みで**確かに存在します**。それでも
    通ったのは、この門が見ている口が**その5分のあいだに落としたから**です ——
    uploads プレイリストは予約中の動画を落とすことがあり（`src/history.py` の実測）、
    もう一方の `search` は **この日 API の1日枠を使い切っていました**（HTTP 429）。
    **両方の口が同時に欠けると、門は何も知らない状態で「重なりなし」と言います。**

    **自分が上げたものを自分で忘れるのは、外の口の都合とは関係ありません。**
    だから上げた瞬間に1行足します。**消えた動画で誤って止めないよう、
    使う側は必ず生存を確かめること**（`upload_only.py` が `videos.list` で引き直す）。
    """
    from . import config

    path = config.ROOT / LEDGER
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        topic = rec.get("topic", "")
        rows.append({"id": rec.get("video_id", ""), "title": rec.get("title", ""),
                     "topic": topic, "calc": (topics or {}).get(topic, ""),
                     "at": rec.get("at"), "scheduled": bool(rec.get("at")),
                     # **`at` は公開予定、`uploaded_at` は投稿した時刻**（別物です）。
                     # 前者しか無かったので「この枠の日にあと何本撃てるか」を
                     # 撃つ前に言えず、6本を作ってから捨てました（`src/upload_cap.py`）。
                     "uploaded_at": rec.get("uploaded_at"),
                     # **`retime()` が押した印**。同じ本の行が2つ残ったとき、
                     # どちらが `videos.update` を通った側かを言う唯一の手がかりです
                     "retimed_at": rec.get("retimed_at"),
                     # **上げた実物の秒数**（2026-08-25 から）。ショートか長尺かを
                     # 題名の `#Shorts` で推測せずに済む唯一の欄です（`src/forms.py`）
                     "duration_s": rec.get("duration_s")})
    return _collapse([r for r in rows if r["id"] and r["title"]])


def _collapse(rows: list[dict]) -> list[dict]:
    """**1本の動画は1行**にたたむ。余分な `at` は `at_others` に残す。

    ## なぜ要るか（2026-08-25 に実測）

    `retime()` の本文は「同じ `video_id` の行が2つあると幻の埋まりが残る」と
    書いていて、**書く側**（足さずに書き換える）だけを直していました。
    **読む側は素通しのまま**です。ところが行が増える口は `retime()` の他にもあります ——

      **控えは `data/uploaded.jsonl` で、git で配られます。** 同時に走っている
      きょうだいの回が別々に足し、**merge が両方の行を残します。**
      片方だけが `retime()` を通っていれば、`at` の違う2行がそのまま残ります。

    2026-08-25 の実測（518行）: **27本が2行ずつ**（13本は同じ `at`・14本は違う `at`）。
    これから公開する行は **355。実物は 328本** ＝ **幻が 27個**。

    **害は「置き場所」ではなく「数」のほうに出ます。**
    `batch_build.ledger_minutes()` は集合を作るので二重でも同じ答えですが、
    本数を数える側は全部ふくれます。同じ日の実測:

        09/05  控え 12本 → 実際 10本      09/06  控え 14本 → 実際 10本
        09/24  控え 11本 → 実際  8本      09/23  控え 14本 → 実際 11本

    `config/hypotheses.yaml` は次の回に
    `reschedule.py --spread --per-day 10 --apply` を撃てと言っています。
    **今日の控えで撃つと、上限に達していない日から実物を 11本 動かします**
    （1本50単位・**動かした先で上限を割るので、再生は減ります**）。
    08/24 の `f6db033`「自分で空にした 08/27 を守り、死んだ枠の11本を戻した」が
    同じ事故の領収書です。

    **`at` が食い違うときは、どちらが本物かをここでは決められません**
    （どちらの回が `videos.update` を通したかは行に書いてありません）。
    だから **数えるのは1本**、**置き場所を避けるのは両方**に分けます ——
    外す向き（空きを1つ余計に飛ばす）は安全で、
    逆向き（埋まっているのに空きと読む）は1本捨てるからです
    （`batch_build.ledger_hours` の本文と同じ理由）。

    勝つ行は「`retimed_at` がいちばん新しい行」、無ければ**最後の行**です。
    """
    best: dict[str, dict] = {}
    others: dict[str, list] = {}
    # **秒数は、勝った行に入っているとは限りません**（2026-08-25）。
    # `retime()` は行を足しますが、その行は `duration_s` を持ちません。
    # 秒数は本ごとに1つしかない事実なので、**同じ本のどの行から拾っても同じ**です。
    dur: dict[str, float] = {}
    for r in rows:
        vid = r["id"]
        others.setdefault(vid, [])
        if r.get("at"):
            others[vid].append(r["at"])
        if r.get("duration_s") is not None and vid not in dur:
            dur[vid] = r["duration_s"]
        cur = best.get(vid)
        if cur is None or _retime_key(r) >= _retime_key(cur):
            best[vid] = dict(r)
    out = []
    for r in rows:
        vid = r["id"]
        if vid not in best:
            continue
        win = best.pop(vid)
        win["at_others"] = [a for a in dict.fromkeys(others[vid]) if a != win.get("at")]
        if win.get("duration_s") is None and vid in dur:
            win["duration_s"] = dur[vid]
        out.append(win)
    return out


def _retime_key(row: dict) -> tuple:
    """勝ち負けの目盛り。`retimed_at` を持つ行が、持たない行に勝つ。

    **同じ強さなら「あとの行」が勝ちます**（この関数は `>=` で比べられるので、
    走査の順番がそのまま最後の行を残します）。
    """
    stamp = row.get("retimed_at") or ""
    return (1 if stamp else 0, stamp)


def remember(video_id: str, topic_id: str, title: str, at: str | None,
             uploaded_at: str | None = None,
             duration_s: float | None = None) -> None:
    """上げた1本を手元に控える。**`upload_only.py` が投稿の直後に呼ぶ。**

    `at` は**公開予定時刻**、`uploaded_at` は**投稿した時刻**です。**別物で、
    どちらも要ります** —— 前者は「その日の何時が埋まっているか」（`batch_build --date`）、
    後者は「**1日の投稿本数の枠**を、この窓であと何本残しているか」（`src/upload_cap.py`）。

    後者が無かったので、10:5x の回は**6本を作ってから 429 に当たり、6本とも捨てました。**
    既定は「いま」です（呼ぶ側は、投稿の直後にしか呼びません）。

    `duration_s` は**上げた実物の秒数**です（2026-08-25 から控えます）。
    無くても通りますが、**無い本は「ショートか長尺か」を題名の `#Shorts` で
    推測するしかなくなります** —— その札は実測で4本ずれていました
    （`src/forms.py` の冒頭。長尺に付いていた本が1本、ショートで欠けていた本が3本）。
    `--spread` が1日のショートの本数に上限をかけるので、
    **ずれた本はその日の枠を食うか、上限から漏れます。**
    """
    from datetime import datetime, timezone

    from . import config

    if uploaded_at is None:
        uploaded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    path = config.ROOT / LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        rec = {"video_id": video_id, "topic": topic_id,
               "title": title, "at": at, "uploaded_at": uploaded_at}
        if duration_s is not None:
            rec["duration_s"] = round(float(duration_s), 1)
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def why_stranded(video: dict, videos: list[dict],
                 topics: dict[str, str] | None = None) -> dict | None:
    """**暗いまま止まっている1本に、機械が言える理由があるか**（2026-08-16）。

    `blocking` と向きが逆です。あちらは「これから上げる本」を止めますが、
    こちらは**既に上がっていて公開されない本**に、後から理由を付けます。

    ## なぜ要るか（**この回に実測しています**）

    `scripts/status.py` は publishAt を持たない private を
    「**公開されないまま止まっている**」と鳴らし、`config/withheld.yaml` に
    理由が書いてある本だけを黙らせます。**理由は手で書きます。**

    ところが、重なりを外す側（`scripts/reschedule.py`）は
    **予約を外すだけで、理由をどこにも書きません。** 8/15 02:5x の回が
    重なり7本を private に戻していますが、`withheld.yaml` は6件のままです。

    この回の実測: **暗い18本のうち、理由が書いてあるのは6本。残り12本**が
    毎回この警告に並んでいました。そして12本を突き合わせると
    **12本とも、公開済みか予約済みの本と強く重なっています**（0本が誤検出）。
    つまり**全部「出さないのが正しい」本**で、警告は1件も当たっていません。

    `status.py` 自身がその危険をこう書いています ——
    **「毎回鳴る警告は無視されるようになり、本当に予約し忘れたときに効かなくなる」**。
    12件まで育っていたので、**その状態にもう入っていました。**

    **手で書く欄を増やしても、次の回がまた書き忘れます**（6回そうなった）。
    だから理由のほうを**機械に出させます。** 重なりが見つかればそれが理由で、
    見つからないときだけ「予約し忘れ」として鳴らす。**警告は腐りません。**

    自分自身とは突き合わせません（控えにも載っているので、
    除かないと「テーマIDが同じ」で必ず自分と重なります）。
    """
    vid = video.get("id", "")
    rows = [r for r in rows_from_videos(videos, topics) if r["id"] != vid]
    have = {r["id"] for r in rows}
    rows += [r for r in ledger_rows(topics)
             if r["id"] not in have and r["id"] != vid]
    me = rows_from_videos([video], topics)
    if not me:
        return None
    hits = [i for i in find(rows + [me[0]])
            if i["strong"] and vid in (i["a"]["id"], i["b"]["id"])]
    if not hits:
        return None
    it = hits[0]
    other = it["b"] if it["a"]["id"] == vid else it["a"]
    return {"kind": it["kind"], "why": it["why"], "other": other}


def used_amounts(topics: dict[str, str] | None = None) -> dict[str, list[float]]:
    """calc ごとに、**もう題に出してしまった金額**を返す（2026-08-18 に足した）。

    `blocking()` は「作った1本」を止めます。**止めるのは正しいのですが、
    そこまでに作る費用は全部払ったあと**です。この関数は同じ判定の材料を
    **作る前**に渡すためのもので、`scripts/topic_forge.py` が題を書かせる
    プロンプトに「この数を主役にするな」と貼ります。

    出すのは `same-yen`（強い重なり）が実際に見る数だけです:

    - `_yen()` が金額とみなしたもの（`円` が付いていないものも入る）
    - **丸い数は外す。** `sigdigits <= ROUND_SIGDIGITS` は制度の名前でしかなく
      （`20万円ルール`）、それ1つでは `find()` も止めません

    **これは門ではありません。** 門は `blocking()` の側で、こちらを
    すり抜けた種はそちらが受けます（台本が別の数字を主役にした場合など）。
    """
    rows = ledger_rows(topics)
    out: dict[str, set[float]] = defaultdict(set)
    for r in rows:
        calc = r.get("calc") or ""
        if not calc:
            continue
        for v in _yen(r["title"]):
            if sigdigits(v) > ROUND_SIGDIGITS:
                out[calc].add(v)
    return {k: sorted(v) for k, v in sorted(out.items())}


def blocking(title: str, topic_id: str, videos: list[dict],
             topics: dict[str, str] | None = None) -> list[dict]:
    """**投稿の直前に呼ぶ。** これから上げる1本が、既にある本と強く重なるか。

    重なっていれば、その組を返します（**空なら通してよい**）。

    ここに置く理由: **予約は `scripts/upload_only.py` の1か所しか通りません。**
    生成の段に置くと、`batch_build` 以外の道（手で `--dry-run` してから上げる）が
    素通りします。**投稿前の検査は、迂回できない場所に置くこと**（`src/verify.py` と同じ）。

    **作ったあとに止めるので、その1本は捨てになります。** それでも
    **公開してしまうより安い** —— 収益化の対象外になると収入はゼロなので。
    """
    rows = rows_from_videos(videos, topics)
    have = {r["id"] for r in rows}
    rows += [r for r in ledger_rows(topics) if r["id"] not in have]
    me = {"id": "＜これから上げる本＞", "title": title, "topic": topic_id,
          "calc": (topics or {}).get(topic_id, ""), "at": None, "scheduled": False}
    return [i for i in find(rows + [me])
            if i["strong"] and me["id"] in (i["a"]["id"], i["b"]["id"])]


def _when(r: dict) -> str:
    if not r["at"]:
        return "予約なし"
    at = datetime.fromisoformat(r["at"].replace("Z", "+00:00")).astimezone(JST)
    return ("予約 " if r["scheduled"] else "公開 ") + at.strftime("%m/%d %H:%M")


def reaches(r: dict) -> str:
    """**この1本は、これから視聴者に届くのか。**

    - `予約` … まだ届いていない。**外せる**
    - `公開` … もう届いた。**取り消せない**
    - `外し` … 予約が無い private。**もう届かない**
    """
    if r["scheduled"]:
        return "予約"
    return "公開" if r["at"] else "外し"


def triage(issues: list[dict]) -> dict[str, list[dict]]:
    """強い組を、**いま手が打てるか**で3つに分ける（2026-08-16 に足した）。

    ## なぜ要るか（**この回に実測してから足しています**）

    `report` は強い組を全部 **「片方を外すこと」** として並べ、
    `scripts/reschedule.py --unschedule <id>` を添えていました。
    ところが実物22組を数えると:

        予約 + 外し    11組   相手はもう外れている ＝ **外すものが無い**
        公開 + 外し     6組   同上
        公開 + 公開     3組   両方とも公開済み ＝ **取り消せない**
        外し + 外し     2組   どちらも届かない
        **予約 + 予約    0組**
        **予約 + 公開    0組**

    **22組すべてが「打つ手なし」で、当たりは0件**でした。60行を毎回並べて、
    そのどれにも `--unschedule` できる相手がいません。

    `status.py` 自身がこの危険を書いています ——
    **「毎回鳴る警告は無視されるようになり、本当に予約し忘れたときに効かなくなる」**。
    8/16 08:2x が「予約し忘れ」の警告を同じ理由で作り直しており（12件まで育って
    当たり0件）、**これはその2件目**です。塞ぐ場所が違うだけで、穴の種類は同じ。

    ## 見つける側は一切変えていません

    `find()` はそのままです。**組は全部本物**で、消したのは「並べ方」だけ。
    だから `blocking()`（これから上げる本を止める）と
    `why_stranded()`（暗い本に理由を付ける）は影響を受けません
    —— どちらも `find()` を直に読み、`report` を通りません。

    **黙らせたぶんは件数で残します。** 外した側がうっかり予約し直されたら、
    その組は `actionable` に**移って鳴ります**（`tests/test_dupes_triage.py`
    の故障注入がそこを見ています）。数を消すと、その復活に気づけません。
    """
    out: dict[str, list[dict]] = {"actionable": [], "already": [], "parked": []}
    for it in issues:
        pair = {reaches(it["a"]), reaches(it["b"])}
        if "外し" in pair:
            out["parked"].append(it)      # 片方（か両方）がもう届かない
        elif "予約" in pair:
            out["actionable"].append(it)  # 予約+予約 か 予約+公開 ＝ **外せる**
        else:
            out["already"].append(it)     # 公開+公開 ＝ 取り消せない
    return out


def report(videos: list[dict], topics: dict[str, str] | None = None) -> list[dict]:
    """`status.py` から毎回呼ぶ。**印刷して、見つけた組を返す。**"""
    issues = find(rows_from_videos(videos, topics))
    strong = [i for i in issues if i["strong"]]
    weak = [i for i in issues if not i["strong"]]

    print("\n=== 自分で作った「繰り返し」（src/dupes.py）===")
    if not issues:
        print("  重なりは見つかりませんでした。")
        return issues

    print(f"  **強い {len(strong)}組** ／ 弱い {len(weak)}組")

    # **強いほうを、いま手が打てるかで割ります**（2026-08-16。理由は `triage`）。
    # 実測22組すべてが「相手はもう外れている／もう公開済み」で、
    # **`--unschedule` できる組は0件**でした。全部並べると、当たった1件が埋もれます。
    tri = triage(strong)
    if tri["actionable"]:
        # **この一覧にも自分の当たり率を測らせます**（`src/alerts.py`）。
        # 22組が当たり0件だったのは「triage が無かった」からですが、
        # triage を通した後の一覧も、当たらないまま育ちうる（同じ形の4件目）。
        from src import alerts as _alerts
        _r = _alerts.ring("dupes_actionable", len(tri["actionable"]))
        if _r.folded:
            print("\n" + _r.line)
        else:
            print(f"\n  --- **止められる {len(tri['actionable'])}組（片方を外すこと）** ---")
            for it in tri["actionable"]:
                a, b = it["a"], it["b"]
                print(f"  [{it['kind']}] {it['why']}")
                print(f"      {a['id']}  {_when(a):<14s} {a['title'][:38]}")
                print(f"      {b['id']}  {_when(b):<14s} {b['title'][:38]}")
            print("    `scripts/reschedule.py --unschedule <id>`。"
                  "**先に代わりを作ってから外すこと** —— 投稿が途切れるほうが高い。")
    elif strong:
        print("\n  --- 止められる 0組 ---")
        print("    **強い組はありますが、どれも外す相手がいません。**"
              "手を打つことは何もありません。")

    # **黙らせたぶんは、件数だけ残します。** 消すと、外した側が予約し直された
    # ときに気づけません（そのときは上の「止められる」に移って鳴ります）。
    if tri["parked"]:
        ids = sorted({r["id"] for it in tri["parked"] for r in (it["a"], it["b"])
                      if reaches(r) == "外し"})
        print(f"  片方が既に外れている {len(tri['parked'])}組"
              f"（外れているのは {len(ids)}本: {' '.join(ids)}）"
              " ← **処理済み。手を打つ必要はありません**")
    if tri["already"]:
        ids = sorted({r["id"] for it in tri["already"] for r in (it["a"], it["b"])})
        print(f"  両方とも公開済み {len(tri['already'])}組"
              f"（{' '.join(ids)}） ← **取り消せません。**"
              "同じ組み合わせを次に作らないためだけの記録")

    # **弱いほうは1組ずつ出しません。** 実測で「答えの数が同じ」だけで20組出て、
    # そのうち16組が `shitsugyo` の `90日`（給付日数は制度側の刻みなので、
    # 別の事例でも必ず一致する）。**組を並べると強いほうが埋もれます。**
    # 見たいのは「どの calc に、どれだけ固まっているか」なので、束ねて出します。
    if weak:
        print(f"\n  --- 弱い {len(weak)}組（**止めるためではなく、並べて見るため**）---")
        bundles: dict[tuple[str, str], set[str]] = defaultdict(set)
        for it in weak:
            calc = it["a"]["calc"] or it["b"]["calc"]
            bundles[(calc, it["kind"])].update((it["a"]["id"], it["b"]["id"]))
        for (calc, kind), ids in sorted(bundles.items(),
                                        key=lambda kv: -len(kv[1])):
            print(f"  [{kind}] `{calc}` に {len(ids)}本: {' '.join(sorted(ids))}")
        print("    続けて見たときに繰り返しに映るかは、**自分で判断すること。**")

    print("\n  **これは収益化の条件です。**「同じチャンネルの動画を続けて数本視聴した後、"
          "繰り返しのように感じられる可能性のあるコンテンツ」は収益化の対象外と"
          "明記されています。**収益化されなければ収入はゼロ**なので、"
          "見栄えの話ではありません。")
    return issues


def retime(video_id: str, at: str | None) -> bool:
    """控えの1行の `at`（公開予定）を書き換える。**足すのではなく、書き換える。**

    ## なぜ足してはいけないか（2026-08-18）

    `ledger_rows()` は**行を全部返します**。同じ `video_id` の行が2つあると、
    `batch_build.ledger_minutes()` は**古いほうの時刻も「埋まっている」と読みます。**
    予約を前に詰める道具（`reschedule.py --compact`）は 251本を動かすので、
    足す作りだと**251個の幻の埋まり**を残し、次の回が置き場所を失います。

    **控えが上限側の見積りなのは「外した本が残る」からで、
    それは取り消しに書き戻す口が無かったからです。**ここは口があります ——
    `videos().update` が通った本だけを書き換えるので、**控えは実物に近づきます。**

    書き換えるのは `at` だけです（`uploaded_at` は投稿した時刻なので動きません）。
    同じ `video_id` が複数行あれば**全部**書き換えます（そのほうが幻が残らない）。

    返り値は「1行でも書き換えたか」。**書き込みは一時ファイル経由で入れ替えます**
    （途中で落ちても控えが半分になりません）。

    ## `retimed_at` を押す理由（2026-08-25）

    ここで書き換えても、**同時に走っているきょうだいの回が持っている古い行は
    消せません** —— 控えは git で配られるので、merge が両方を残します。
    そのとき「どちらが `videos.update` を通した側か」を行から言えないと、
    読む側（`_collapse`）は最後の行を選ぶしかありません。**それは順番の運です。**

    だから通った側に印を押します。**押されている行が、押されていない行に勝ちます。**
    """
    from . import config

    path = config.ROOT / LEDGER
    if not path.exists():
        return False
    stamp = _now_iso()
    lines = path.read_text(encoding="utf-8").splitlines()
    out, hit = [], False
    for line in lines:
        stripped = line.strip()
        if stripped:
            try:
                rec = json.loads(stripped)
            except Exception:
                out.append(line)
                continue
            if rec.get("video_id") == video_id and rec.get("at") != at:
                rec["at"] = at
                rec["retimed_at"] = stamp
                out.append(json.dumps(rec, ensure_ascii=False))
                hit = True
                continue
        out.append(line)
    if not hit:
        return False
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("\n".join(out) + "\n", encoding="utf-8")
    tmp.replace(path)
    return True


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def compact_ledger(path=None) -> dict:
    """**同じ行が2つある**ぶんだけを、控えから物理的に落とす（API 0単位）。

    落とすのは **`video_id` も `at` も同じ行**だけです。`at` が食い違う組は
    **残します** —— どちらが本物かはここでは決められず、置き場所を避ける側は
    「両方が埋まっている」と読むほうが安全だからです（`_collapse` の本文）。
    数えるほうは `ledger_rows()` が1本にたたむので、残っていても膨らみません。

    返り: removed（落とした行数）／conflicts（`at` が食い違う video_id と、その候補）
    """
    from . import config

    p = config.ROOT / LEDGER if path is None else path
    if not p.exists():
        return {"removed": 0, "conflicts": {}}
    lines = p.read_text(encoding="utf-8").splitlines()
    seen: set[tuple] = set()
    ats: dict[str, list] = {}
    out, removed = [], 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            rec = json.loads(stripped)
        except Exception:
            out.append(line)
            continue
        vid = rec.get("video_id", "")
        key = (vid, rec.get("at"), rec.get("title", ""))
        if vid and key in seen:
            removed += 1
            continue
        seen.add(key)
        if vid and rec.get("at"):
            ats.setdefault(vid, []).append(rec["at"])
        out.append(line)
    conflicts = {v: a for v, a in ats.items() if len(set(a)) > 1}
    if removed:
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text("\n".join(out) + "\n", encoding="utf-8")
        tmp.replace(p)
    return {"removed": removed, "conflicts": conflicts}
