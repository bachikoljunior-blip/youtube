"""**題材の段**（2026-09-17 17:4x・optimizer・Fable 5.1・ultracode）。**API 0単位。**

`data/niche_corpus.jsonl`（もう disk に在る 659行・`id` で重複を落として長尺 335本）を
**検索語ごと**に割ると、**中央値が 3桁 違います**:

    最大        本   中央      検索語
    5,124,861  38   605,548   年金 手取り いくら
    2,023,357  36   325,807   退職金 税金 いくら
    4,422,714  34    78,823   加給年金 いくら
    1,501,667  39    68,276   所得税 控除 節税
      548,720  21    59,469   遺族年金 いくら 計算
    ------------------------------------------------
      228,855  14     4,585   再就職手当 計算
      129,557  31     3,387   変動金利 5年ルール 未払利息
       54,238  26     1,588   標準報酬月額 計算
      185,938  31     1,332   ふるさと納税 上限 計算
      180,901  40     1,093   不動産取得税 計算
      457,339  25       190   医療費控除 いくら戻る

**＝ 上の段と下の段で、中央が 100〜3,000倍 違います。**
この repo がこれまでに測ったどの腕（題の形 1.5倍・透かし・固定コメント・転換率 最良で 3.8倍）よりも
**2桁 大きく、そして 0単位・0秒 で選べます** —— 変わるのは「どの台本を書くか」だけ。

**なぜ中央で見るか（最大で見ないこと）**: 同じ表の `医療費控除 いくら戻る` は
**最大 457,339・中央 190** です。＝ その段は「当たりが 1本 在る」だけで、**面が無い**。
対して `年金 手取り いくら` は **38本 の中央が 605,548** ＝ **半分 が 60万回 を越えている ＝ 面が在る。**
`dense`（面が在る）と `lottery`（当たりだけ）を分けるのはこの比（`median / max`）です。

**この数の読み方（**上限**であって、期待値ではありません）**:
corpus は**検索の結果**から集めています。検索は人気の順に並ぶので、**どの語の数も上振れします。**
＝ 中央 605,548 は「この題材で書けば 60万回 来る」ではありません。
**言えるのは「段どうしの比べ」だけ** —— 同じ集め方をした 2つ の語で、
一方の上位の中央が 190 なら、**その語には面が無い**（上振れした数でさえ 190）。

**覆る条件**:
 (1) **うちの長尺が、段の高い語で 3本 続けて 25回 以下**なら、段は原因ではない
     ＝ そのときは GOAL (4-i) の枝（口・中身）へ戻すこと。**この段は「題材を外している」までしか言いません。**
 (2) corpus を引き直して（`niche_ceiling` / `peers`）**同じ語の中央が 1桁 動いたら**、
     この表ではなくそのときの数が正本（この module は毎回 disk から数え直すので、引き直せば自動で直ります）。
 (3) **`q` は「その本を見つけた検索語」であって「その本の題材」ではありません。**
     1本 が 2つ の語から出てくることが在ります（`id` で重複は落としてありますが `q` は最初の 1つ になる）。
     段の順が入れ替わるほどの取りこぼしが出たら、`q` ではなく題の語で割り直すこと。
"""
from __future__ import annotations

import datetime as dt
import json
import statistics
from collections import defaultdict

from .common import ROOT

#: corpus の置き場（`niche_ceiling` / `peers` が書く）。
#: **`common.DATA`（`data/studio/`）ではありません** —— corpus は `data/` の直下です。
CORPUS = ROOT / "data" / "niche_corpus.jsonl"

#: `median / max` がこれ以上なら **面が在る**（`dense`）。下なら **当たりだけ**（`lottery`）。
#: 0.10 は上の表で段が割れる所（`遺族年金` 0.108 が `dense` の下端・`加給年金` 0.018 が `lottery`）。
DENSE_RATIO = 0.10
#: この本数に満たない語は段を言わない（中央が 1〜2本 で決まってしまう）。
MIN_BOOKS = 5


def rows(path=None) -> list[dict]:
    """corpus の**長尺だけ**を、`id` で重複を落として返す（**API 0単位**・disk だけ）。

    重複は本物です —— 同じ本が引くたびに 1行 入ります（実測: `年金・給付金完全攻略` の
    4,402,748 / 4,415,973 / 4,422,714 は**同じ 1本**の 3回 の引き）。
    落とさずに数えると、**引き直した本ほど重く**なります。
    """
    p = path or CORPUS
    if not p.exists():
        return []
    seen: dict[str, dict] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("form") == "short" or not r.get("id"):
            continue
        # あとの行ほど新しい ＝ 再生は増える側なので、あとの行で上書きする。
        seen[r["id"]] = r
    return list(seen.values())


def by_query(path=None) -> list[dict]:
    """検索語ごとの段。**中央の大きい順**。

    返り 1件: `{"q", "n", "median", "max", "ratio", "dense"}`。
    """
    out = []
    groups: dict[str, list[int]] = defaultdict(list)
    for r in rows(path):
        groups[r.get("q") or "?"].append(int(r.get("views") or 0))
    for q, vs in groups.items():
        if len(vs) < MIN_BOOKS:
            continue
        mx = max(vs)
        md = int(statistics.median(vs))
        ratio = (md / mx) if mx else 0.0
        out.append({"q": q, "n": len(vs), "median": md, "max": mx,
                    "ratio": round(ratio, 4), "dense": ratio >= DENSE_RATIO})
    out.sort(key=lambda d: -d["median"])
    return out


def tier_of(text: str, path=None) -> dict | None:
    """**その題が、どの段に居るか。** `text` には題＋tags を渡してよい（つないだ 1本の字で見ます）。

    当て方は **`q` の頭の語（題材の名）が字のまま在ること**。それが在る段だけを候補にし、
    残りの語の重なりが多い順、同じなら中央の大きい順で選ぶ。
    返りに **`hits`**（重なった語の数・頭を含む）と **`strong`**（`hits >= 2`）を足して返す。

    **`strong` が False の答えを、段の判定に使わないこと**（2026-09-17 18:0x に、
    道具を配線した直後の実物で踏んだ）: うちの長尺 **11本 が 11本 とも
    `年金 手取り いくら`（中央 605,548・面）に当たりました。
    **`年金` は、この族のほとんどの題に入っている語**なので、
    頭の錨だけでは `扶養親族等申告書`（年金148万円以上の方へ）も `高年齢求職者給付金` も
    `繰上げ` も、全部いちばん高い段に化けます。
    **＝ 頭 1語 だけの一致は「その段に居る」ではなく「否定できない」までです。**

    **頭の錨そのものは要ります**（`hits` だけで選ぶと外れる。同じ回に踏んだ実物:
    `【退職金2000万円】…の手取り` が `退職金 税金 いくら` ではなく `年金 手取り いくら` に当たった
    —— どちらも 1語 の重なりで、中央の大きいほうが勝つ）。**2つ を両方 置くこと。**

    **`None` は「段が低い」ではなく「この corpus では測っていない」**です
    （実測: `医療費が1年で10万円をこえたら` は `医療費控除` を字として持たないので `None`）。

    **覆る条件**: `strong` が True の本が **10本 たまっても、段の高い側と低い側で
    実測の再生が分かれない**なら、割り方（`q` の語）がこの族に対して粗すぎる
    ＝ そのときは題の語で corpus を割り直すこと（module の註 (3)）。
    """
    best, best_key = None, ()
    for t in by_query(path):
        words = t["q"].split()
        if not words or words[0] not in text:
            continue
        hits = 1 + sum(1 for w in words[1:] if w in text)
        # **頭の錨は、長いほうが勝ちます**（2026-09-19 21:xx に足した）。
        # `hits` だけで並べると、**同じ hits の中では corpus の中央が大きい段が勝ちます** ——
        # この docstring が「踏んだ」と書いている 2件 は、どちらもその形でした:
        #   `【退職金2000万円】…の手取り` → 頭 `退職金`(hits 2) と 頭 `年金`(hits 2) が並び、中央の大きい
        #     `年金 手取り いくら` が勝っていた
        #   `夫が亡くなると妻の年金はいくら減るか 遺族厚生年金は4分の3` ＋ tags(`遺族年金`) →
        #     `遺族年金 いくら 計算`(hits 2) と `年金 手取り いくら`(hits 2) が並び、同じく後者が勝つ
        # **頭の語の長さを hits の次に置くと、両方とも正しい段に落ちます**
        # （`遺族年金`(4字) > `年金`(2字)・`退職金`(3字) > `年金`(2字)）。
        # **覆る条件**: 頭が同じ長さで hits も同じ段が 2つ 出て、実測で分かれたら、
        # 3つ目 の物差し（題の語で corpus を割り直す・module の註 (3)）が要ります。
        key = (hits, len(words[0]), t["median"])
        if best is None or key > best_key:
            best, best_key = t, key
    if best is None:
        return None
    # `head` ＝ 当たった段の**頭の語**（`mine_by_query` が「頭がどれだけ specific か」で拾うのに要る）。
    return dict(best, hits=best_key[0], head=best["q"].split()[0], strong=best_key[0] >= 2)


#: うちの台帳（`scheduled` の行 ＝ 出した本）。**corpus ではありません。**
LEDGER = ROOT / "data" / "studio" / "ledger.jsonl"
SCRIPTS_DIR = ROOT / "data" / "studio" / "scripts"
#: 族ごとに、この本数 未満なら「うちの数」を出さない（1〜2本 で中央が決まってしまう）。
MINE_MIN = 1
#: **出てから この時間 たっていない本は数えない。** 予約ずみ・公開直後の本は **0回** なので、
#: 入れると「きょう 6本 置いた族」の中央が 0回 になります（2026-09-19 21:xx に踏んだ ——
#: `退職金 税金 いくら` が **n=12・中央 0回** で出て、実物の 879回 が中央から消えた）。
MINE_MIN_AGE_H = 24.0
#: **頭の語がこれ以上の長さなら、`hits` が 1 でも族に採る。**
#: `strong`（`hits >= 2`）だけだと、**うちの題は落ちます** —— 実物
#: `配偶者が年下だと年金が年42万3700円ふえる 加給年金`（970回）は `いくら` も `計算` も字に持たないので
#: `加給年金 いくら` も `年金 手取り いくら` も `hits` 1 ＝ **両方 落ちて 族なし**になりました。
#: `strong` は **corpus の段どうしを分ける**ための門で、**頭が `年金`（2字）のような総称でなければ、
#: 1語 の一致でも段は 1つ に決まります**（`tier_of` の並べ替えが頭の長さを見るようになったので）。
MINE_HEAD_MIN = 3


def mine(ledger=None, scripts=None, _now=None) -> list[dict]:
    """**うちが出した本**を `{"id", "title", "views", "age_h", "aged"}` で返す（**API 0単位**・disk だけ）。

    台帳の `scheduled` が `video_id → (台本の id, 題)` を持ち、再生は `views` を持つ どの行からでも拾う。
    **1つ の台本が 2つ 以上の `video_id` を持つことが在ります**（`schedule --replace` で置き直した本・
    非公開へ戻した本）。片方は 0回 のまま残るので、**台本ごとに いちばん大きい再生を採ります** ——
    `min` や平均で採ると、置き直した本が全部 0回 の族に見えます（実測: 09/15〜09/17 の 11本）。
    """
    led = ledger or LEDGER
    if not led.exists():
        return []
    sched: dict[str, tuple[str, str]] = {}
    best: dict[str, int] = {}
    for ln in led.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if r.get("event") == "scheduled" and r.get("video_id"):
            sched[r["video_id"]] = (r.get("id") or "", r.get("title") or "", r.get("publish_at") or "")
        vid = r.get("video_id") or r.get("id")
        v = r.get("views")
        if isinstance(v, int) and not isinstance(v, bool) and vid:
            best[vid] = max(best.get(vid, 0), v)
    now = _now or dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
    by_script: dict[str, dict] = {}
    for vid, (sid, title, pub) in sched.items():
        key = sid or vid
        cur = by_script.get(key)
        views = best.get(vid, 0)
        age = _age_h(pub, now)
        row = {"id": sid, "title": title, "views": views, "age_h": age,
               "aged": age is not None and age >= MINE_MIN_AGE_H}
        # **台本ごとに いちばん大きい再生を採る**（置き直した本の 0回 を採らない）。
        # 齢は「その台本がいちばん早く出た刻」で見る ＝ どれか 1つ が門を越えていれば越えている。
        if cur is None or views > cur["views"]:
            row["aged"] = row["aged"] or bool(cur and cur.get("aged"))
            by_script[key] = row
        elif row["aged"]:
            cur["aged"] = True
    return list(by_script.values())


def _age_h(pub: str, now) -> "float | None":
    """`publish_at`（`2026-09-10T10:00+09:00`）から、いま何時間たったか。読めなければ `None`。"""
    if not pub:
        return None
    try:
        t = dt.datetime.fromisoformat(pub)
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=now.tzinfo)
    return (now - t).total_seconds() / 3600.0


def _text_of(b: dict, scripts=None) -> str:
    """題 ＋ tags（`tier_of` は「題＋tags を渡してよい」と書いてある）。

    **tags が要ります** —— 実物 `夫が亡くなると妻の年金はいくら減るか 遺族厚生年金は4分の3` は
    題の字に `遺族年金` を **持ちません**（持っているのは `遺族厚生年金`）。
    tags の側に `遺族年金` が在るので、そこまで読まないと この本は族に当たりません。
    """
    d = scripts or SCRIPTS_DIR
    text = b.get("title") or ""
    f = d / f"{b.get('id')}.json"
    if f.exists():
        try:
            text += " " + " ".join(json.load(open(f)).get("tags") or [])
        except (ValueError, OSError):
            pass
    return text


def _form_of(b: dict, scripts=None) -> str:
    """その本が `short` か `long` か。

    **台本の `form` は、古い本には入っていません**（2026-09-10 までの本は `None`）。
    そのときは**題の `#Shorts`** で見ます —— この repo のショートの題は 1本 残らずこれで終わります
    （`cmd_schedule` が付ける）。実測 2026-09-19 21:xx: `form` が `None` の本 2本 とも `#Shorts` 在り。
    """
    d = scripts or SCRIPTS_DIR
    f = d / f"{b.get('id')}.json"
    if f.exists():
        try:
            v = json.load(open(f)).get("form")
            if v:
                return str(v)
        except (ValueError, OSError):
            pass
    return "short" if "#Shorts" in (b.get("title") or "") else "long"


def mine_by_query(path=None, ledger=None, scripts=None, form="short") -> dict[str, dict]:
    """**うちが出した本を、corpus と同じ族に割って中央を出す**（**API 0単位**）。

    返り: `{q: {"n", "median", "max"}}`。

    **なぜ在るか（2026-09-19 21:xx に、この道具が無くて 1周 を捨てかけた）**:
    `by_query` の段は **corpus ＝ よその本の、検索の上位**です。「その語に面が在るか」は言えますが、
    **うちに配られるか**は言いません。実物:

        `遺族年金 いくら 計算`  corpus 中央 **59,469**（21本・`dense`）
                                **うちの実測 9回**（`2YZ_4FXC-XI`・09/10 10:00）
        `加給年金 いくら`       corpus 中央 **78,824**（34本・`lottery`）
                                **うちの実測 970回**（`gv1u7n_pCAQ`・09/09 10:00）

    **同じ刻・同じ作り・同じ 1日1本 の並びで、前後の本は 723〜1,220回**でした
    ＝ 9回 は刻でも作りでも齢でもなく **族**です。**corpus の `dense` は、うちの配りを当てません。**

    **形を混ぜないこと**（2026-09-19 21:xx に踏んだ・既定は `form="short"`）:
    `加給年金 いくら` は、混ぜると **n=4・中央 8回**（ショート 970 ＋ 長尺 13／4／0）で出ます。
    **長尺とショートは、同じ齢の門で測って 中央 1回 対 719回**（`trend.form_yield`）——
    **族の数に長尺を混ぜると、族ではなく形を測ります。**

    **覆る条件**:
     (1) うちの本が 1本 しか無い族の中央は、その 1本 です。**`n` を見ないで読まないこと。**
     (2) `tier_of` が族を外すと、この数はまるごと別の族に載ります（`strong` が False の本は捨てています）。
     (3) うちの本の再生は**齢**で変わります。この数は齢をそろえていません
         （そろえた比べが要るなら `trend.form_yield` の側の形へ）。
    """
    fam: dict[str, list[int]] = defaultdict(list)
    for b in mine(ledger, scripts):
        if not b.get("aged"):
            continue
        if form and _form_of(b, scripts) != form:
            continue
        t = tier_of(_text_of(b, scripts), path)
        if not t:
            continue
        if not (t.get("strong") or len(t.get("head") or "") >= MINE_HEAD_MIN):
            continue
        fam[t["q"]].append(int(b["views"]))
    out = {}
    for q, vs in fam.items():
        if len(vs) < MINE_MIN:
            continue
        out[q] = {"n": len(vs), "median": int(statistics.median(vs)), "max": max(vs)}
    return out


def line(path=None) -> str:
    """毎周の 1行（**API 0単位**）。上の 3段 と、下の 1段 を出す。"""
    ts = by_query(path)
    if not ts:
        return "題材の段: corpus が無い（`peers --force` で引くこと・`studio/topics.py`）"
    dense = [t for t in ts if t["dense"]]
    head = "／".join(f"{t['q']} **{t['median']:,}**" for t in ts[:3])
    dead = ts[-1]
    try:
        mn = mine_by_query(path)   # 既定は **ショートだけ**（形を混ぜない・その註を読むこと）
    except Exception:                                     # noqa: BLE001 —— 台帳が読めない回は corpus だけ出す
        mn = {}
    if mn:
        best = sorted(mn.items(), key=lambda kv: -kv[1]["median"])
        top = "／".join(f"{q} **{d['median']:,}**（{d['n']}本）" for q, d in best[:3])
        worst_q, worst = best[-1]
        mine_part = (f" ‖ **うちの実測（同じ族・ショートだけ・齢24h以上・台帳・API 0単位）**: "
                     f"上位 {top} ／ いちばん下 {worst_q} **{worst['median']:,}**（{worst['n']}本）"
                     f" ＝ **{best[0][1]['median'] // max(worst['median'], 1):,}倍**。"
                     f"**corpus の段とうちの実測は別の数です** —— 実物 `遺族年金 いくら 計算` は "
                     f"corpus `dense`（中央 59,469）でうちは **9回**、`加給年金 いくら` は "
                     f"corpus `lottery`（中央 78,824）でうちは **970回**（2026-09-19 21:xx に数えた）。"
                     f"**族を選ぶ回は、段を見る前にこちらを見ること**（`topics.mine_by_query`・覆る条件はその註）")
    else:
        mine_part = (" ‖ **うちの実測は出せませんでした**（台帳に当たる本が 0本）"
                     " ＝ **段だけで族を選ばないこと**（`topics.mine_by_query` の註）")
    return (f"**題材の段**（corpus {sum(t['n'] for t in ts)}本・長尺・中央・**API 0単位**）: "
            f"上位 {head} ／ いちばん下 {dead['q']} {dead['median']:,} "
            f"＝ **{ts[0]['median'] // max(dead['median'], 1):,}倍**。"
            f"面が在る段（`dense`）は {len(dense)}/{len(ts)}語。"
            f"**この段は corpus（よその本の検索の上位）で、うちの配りではありません**"
            + mine_part)
