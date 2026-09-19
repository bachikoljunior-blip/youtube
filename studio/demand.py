"""**人が実際に打っている語**を数える（2026-09-16 04:0x・optimizer・Fable 5.1・ultracode）。**API 0単位**。

**なぜ要るか（この口で、いま開いている扉は 1つ しかない）**:
`analytics_traffic` の直近（09/05〜09/12・7日・`data/studio/ledger.jsonl`）:

    SHORTS          6,003回   ← 97%
    YT_SEARCH         182回
    SUBSCRIBER        161回
    YT_OTHER_PAGE      57回
    RELATED_VIDEO       3回   ← **7日 で 3回**（09/07 の窓では 38回 ＝ 落ちている）

＝ **この口は、いま browse／suggested の扉をほとんど持っていません。** 開いているのは検索の側です。
**ただし この窓はチャンネル全体で、長尺は 1本 も入っていません**（長尺の 1本目 は 09/15 19:00 公開）——
言えるのは「口ぜんたいの配りの上限」までで、「長尺だけが受け取らない」ではありません。
本ごとの内訳は `analytics_traffic` を本の id で引く側（GOAL (4-i) (p3)・遅れ 3日 ＝ 09/18 以降）。
`peers`（GOAL (4-j)）が測った速い 6チャンネルは登録 1.8〜18.4万人 で、**向こうには browse が在ります** ——
だから向こうの題（`【対象】＋損＋数`）は「一覧に出たときに押させる」形で足ります。
**うちには一覧が来ないので、押させる前に『出る』必要があり、出る所は検索の結果だけです。**
`peers` の上位 36本 でも、いちばん上の 5本 のうち **2本 は `【】` を持たない検索の形**でした
（`2026年6月最新版の年金通知書の読み方…` 105万回・`失敗しない失業保険のもらい方｜申請〜受給の流れ…` 69万回）。

**この道具が返すもの**: YouTube の検索窓の補完（`suggestqueries.google.com` ＝ **YouTube Data API ではない**・
日枠 10,000単位 を 1単位 も使わない）を、種の語から広げて集めたもの。
補完は**人気の順**に並ぶので、**順位と、何個の親から出てきたか**が需要の代わりになります。

**この数を「再生数」と読まないこと。**
補完は *並び* であって *量* ではありません。返せるのは「A は B より上」までで、「A は月 N回」ではありません。
使い方は 2つ だけ:
  (1) **題材を選ぶ**（上位に在って、うちが 1本 も持っていない語）
  (2) **題と説明欄に、その語を字のまま入れる**（検索の結果に出る所は、字が合っている所）

**覆る条件**:
 (1) 補完の並びは地域と時期で動きます。**同じ語を 2週 あけて 2度 引いて順が入れ替わったら、
     この並びは題材を選ぶ根拠には弱い** ＝ そのときは `analytics` の `YT_SEARCH` の実測（どの語で来たか）に替えること。
 (2) 検索から入った長尺が **3本 続けて 48h に 25回 以下**なら、扉は検索でもない ＝ GOAL (4-i) の枝 B（口の側）へ。
 (3) `hl`／`gl` を日本語・日本以外にした回が出たら、この註の数は使えません（引き直すこと）。
 (4) **口が 429／403 を返したら、間隔を空けること**（`SLEEP_S`）。撃つ数は `seeds × len(TAILS)` 回 です。
"""
from __future__ import annotations

import concurrent.futures as _cf
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict

from .common import DATA, now_jst

#: YouTube の検索窓の補完（`ds=yt`）。**YouTube Data API ではない ＝ 日枠 0単位**。
SUGGEST = "https://suggestqueries.google.com/complete/search"
#: 1回 引くごとに空ける秒（覆る条件 (4)）。**並列にした後は「働き手 1つ あたり」の間隔です。**
SLEEP_S = 0.25

#: **同時に引く数**（2026-09-20 02:4x・optimizer・Opus 5・ultracode が足した）。
#:
#: **なぜ足したか**: 既定は 種 16語 × 尾 48 ＝ **768回** で、直列 ＋ `SLEEP_S` 0.25秒 だと
#: 待つだけで 192秒、引く時間を足すと **7分 前後**。**周の中では返りません** ——
#: 2026-09-19 の 2周 が既定のまま撃って、**2度 とも 120秒 で落ちました**（JOURNAL §6）。
#: 落ちた側は「道具が壊れている」と読みましたが、壊れていません。**数が合っていないだけ**です。
#: 6 並列で 768回 は **70秒 前後** ＝ 周の中に入ります。
#:
#: **絞りを外したので、代わりに 2つ 足してあります**:
#:  (a) `fetch` の引き直し（`RETRY_SLEEP_S`）—— 直列のころは 0.25秒 の間隔そのものが絞りでした。
#:  (b) `harvest(stats=…)` が **本当に引けた数**を返すこと —— 下の「黙って落とす」の註。
#:
#: **覆る条件**: 引けなかった数（`stats["fail"]`）が 1割 を越える回が出たら、429 の側が勝っています
#: ＝ ここを下げるか `SLEEP_S` を上げること。**上げずに数だけ読むと、並びが偏ります**
#: （欠けるのは遅い尾 ＝ 後ろの種に偏るため）。
WORKERS = 6

#: 429／403／5xx が返ったときに空ける秒（この順で引き直す）。
#: **黙って落とさないため**です —— 前の形は `except Exception: continue` で、
#: こけた引きが `pulls` の数に出ませんでした（＝ 768回 引いたと台帳に書いて、
#: 実際は 300回 かもしれない）。**この module の註が「化けた語は『持っていない』側に全部 倒れる」と
#: 書いているのと同じ形の嘘**で、落ちるのは遅い尾 ＝ 後ろの種に偏ります。
RETRY_SLEEP_S = (1.0, 3.0, 8.0)
#: 種の語のうしろに継ぐもの。空 ＝ 種そのもの。かな 1字 を継ぐと補完の枝が割れて広がる。
TAILS = ["", " ", " あ", " い", " う", " え", " お", " か", " き", " く", " け", " こ",
         " さ", " し", " す", " せ", " そ", " た", " ち", " つ", " て", " と",
         " な", " に", " ぬ", " ね", " の", " は", " ひ", " ふ", " へ", " ほ",
         " ま", " み", " む", " め", " も", " や", " ゆ", " よ",
         " ら", " り", " る", " れ", " ろ", " わ", " ん"]

#: 既定の種。**うちが持っている族（年金）と、`peers` の上位に在ってうちが 1本 も持っていない族**を混ぜてあります
#: —— 混ぜる理由は、持っている族の中の取りこぼしと、族そのものの取りこぼしは別の探し方だからです。
#: `peers` の上位 36本 のうち **9本 が 失業保険／ハローワーク**（69万・37万・35万・32万・31万・29万・11万・6.7万・6.2万回）で、
#: うちは **0本**（`data/studio/scripts/` の 20本 は全部 年金・税）。
SEEDS = ["年金", "失業保険", "失業手当", "ハローワーク", "退職", "退職金",
         "繰り上げ受給", "遺族年金", "加給年金", "国民健康保険", "住民税",
         "ねんきん定期便", "高年齢求職者給付金", "在職老齢年金",
         # **床のいちばん高い 2族**（2026-09-16 14:5x に足した・`peers.FAMILY_FLOOR_Q` の註）。
         # 種に 1語（「年金」「退職金」）しか無かったあいだ、補完は族の**外側**へ広がり、
         # 床 117,006回 / 99,851回 の 2族 の中の語が 1つ も出ていませんでした。
         # 実測（この回・94回 引いた・0単位）: `年金 手取り額` n=46 best 0・`退職金税金` n=46 best 0。
         "年金 手取り", "退職金 税金"]

DEMAND = DATA / "demand.jsonl"


def fetch(q: str, *, hl: str = "ja", gl: str = "jp", timeout: float = 20.0,
          retries: "tuple[float, ...] | None" = None) -> list[str]:
    """補完を 1回 引く（**0単位**）。返るのは語の並び（人気の順）。

    **口は既定では UTF-8 を返しません**（2026-09-16 03:4x に踏んだ）——
    `oe` を渡さないと **Shift_JIS** が返り、`utf-8` で読むと 1語 残らず化けます
    （最初の 658回 の引きが丸ごとそれで、`gaps` の重なりが**全部 0.0** になりました
    ＝ **化けた語は、うちの題と 1文字も重ならないので「持っていない」側に全部 倒れます**）。
    **`oe=utf-8` を渡し、そのうえで返ってきた charset を見ること**（片方だけでは足りない
    —— 渡しても口が別の charset で返す日は、header のほうが本当のことを言う）。
    """
    url = f"{SUGGEST}?{urllib.parse.urlencode({'client': 'firefox', 'ds': 'yt', 'hl': hl, 'gl': gl, 'oe': 'utf-8', 'ie': 'utf-8', 'q': q})}"
    waits = RETRY_SLEEP_S if retries is None else tuple(retries)
    for i in range(len(waits) + 1):
        try:
            r = urllib.request.urlopen(url, timeout=timeout)
            enc = r.headers.get_content_charset() or "utf-8"
            d = json.loads(r.read().decode(enc, "replace"))
            return [s for s in (d[1] if len(d) > 1 else []) if isinstance(s, str)]
        except urllib.error.HTTPError as e:
            # **429／403／5xx だけ引き直します**（400 や 404 は待っても同じ字が返る）。
            if e.code not in (403, 429, 500, 502, 503, 504) or i >= len(waits):
                raise
            time.sleep(waits[i])
    raise RuntimeError("unreachable")


def harvest(seeds: list[str], *, tails: list[str] | None = None,
            get=None, sleep: float | None = None,
            workers: int | None = None,
            stats: dict | None = None) -> dict[str, list[tuple[str, int]]]:
    """種の語を広げて集める。返りは `語 → [(引いた親, その中での順位), …]`（**0単位**）。

    `get` は検査が差し替える口（既定は `fetch`）。
    `workers` は同時に引く数（既定 `WORKERS`・1 なら直列）。

    **`stats` を渡すと、本当に引けた数がそこへ入ります**
    （`planned` 予定した数・`ok` 引けた数・`fail` こけた数・`errors` 例外の名前ごとの数・`workers`）。
    **渡さないと、こけた引きはどこにも出ません** —— 台帳の `pulls` が嘘になるので、
    `cli` の口は必ず渡します。

    **並びは決まります**（並列でも）: 親は「種 × 尾」の順に番号をふってあり、
    最後にその番号で並べ直すので、**同じ入力なら同じ返りです**（検査が順を見ています）。
    """
    get = get or fetch
    tails = TAILS if tails is None else tails
    sleep = SLEEP_S if sleep is None else sleep
    workers = WORKERS if workers is None else max(1, int(workers))

    jobs: list[tuple[int, str]] = []
    for s in seeds:
        for t in tails:
            jobs.append((len(jobs), s + t))

    def one(job: tuple[int, str]):
        idx, q = job
        try:
            got = get(q)
        except Exception as e:         # 1回 こけても全体は止めない（覆る条件 (4)）。
            return idx, q, None, type(e).__name__   # **ただし黙っては落としません**（下で数えます）
        if sleep:
            time.sleep(sleep)
        return idx, q, got, None

    if workers > 1 and len(jobs) > 1:
        with _cf.ThreadPoolExecutor(max_workers=min(workers, len(jobs))) as ex:
            done = list(ex.map(one, jobs))
    else:
        done = [one(j) for j in jobs]

    ok = 0
    errs: dict[str, int] = defaultdict(int)
    seen: dict[str, list[tuple[int, str, int]]] = defaultdict(list)
    for idx, q, got, err in done:
        if err is not None:
            errs[err] += 1
            continue
        ok += 1
        for i, w in enumerate(got):
            if w.strip() and w.strip() != q.strip():
                seen[w.strip()].append((idx, q, i))

    hits: dict[str, list[tuple[str, int]]] = {}
    for w, ps in seen.items():
        ps.sort()
        hits[w] = [(q, i) for _, q, i in ps]

    if stats is not None:
        stats.update({"planned": len(jobs), "ok": ok, "fail": len(jobs) - ok,
                      "errors": dict(errs), "workers": workers})
    return hits


def score(hits: dict[str, list[tuple[str, int]]]) -> list[dict]:
    """並べ替える（**この関数が順の唯一の出どころ**）。

    `n` ＝ 何個の親から出てきたか（広さ）・`best` ＝ いちばん上に出たときの順位・
    `mean` ＝ 順位の平均。**上ほど需要が大きい側**（ただし量ではない ＝ この module の註）。
    """
    out = []
    for w, ps in hits.items():
        ranks = [i for _, i in ps]
        out.append({"q": w, "n": len(ps), "best": min(ranks),
                    "mean": round(sum(ranks) / len(ranks), 2)})
    out.sort(key=lambda r: (-r["n"], r["best"], r["mean"], r["q"]))
    return out


def covered(rows: list[dict]) -> list[str]:
    """うちが**もう出した／予約した**本の題と id（`data/studio/ledger.jsonl`）。比べる相手。"""
    out = []
    for r in rows:
        if r.get("event") in ("scheduled", "retitled", "built"):
            for k in ("title", "new_title", "old_title", "id", "script"):
                v = r.get(k)
                if isinstance(v, str) and v:
                    out.append(v)
    return out


def _grams(s: str) -> set[str]:
    """語を 2字 の並びに割る（日本語は空白で割れないので、重なりはこれで見る）。"""
    s = "".join(s.split())
    return {s[i:i + 2] for i in range(len(s) - 1)} or {s}


def gaps(ranked: list[dict], mine: list[str], *, need: float = 0.6, top: int = 60) -> list[dict]:
    """上位の語のうち、**うちが 1本 も持っていない側**（覆る条件 (1) の使い道 (1)）。

    `need` ＝ 語の 2字 の並びのうち、どれだけ うちの題に在れば「持っている」とみなすか。
    **この門は粗い側に倒してあります**（持っているのに「無い」と言うより、無いのに「在る」と言うほうが高い
    —— 同じ題材を 2本 書くのは時間の損で、取りこぼしは次の周が拾える）。
    """
    pool = set()
    for m in mine:
        pool |= _grams(m)
    out = []
    for r in ranked[:top]:
        g = _grams(r["q"])
        share = len(g & pool) / len(g)
        if share < need:
            out.append({**r, "share": round(share, 2)})
    return out


def record(seeds: list[str], ranked: list[dict], gap: list[dict], *, pulls: int,
           stats: dict | None = None) -> dict:
    """台帳へ 1行（**0単位**。`units: 0` を字で残すこと ＝ 次の回が日枠と混ぜないため）。

    **`pulls` は「本当に引けた数」を渡すこと**（予定した数ではありません）。
    `stats`（`harvest` が埋めたもの）を渡すと、予定・こけた数・例外の名前も同じ行に残ります ——
    **欠けた引きは後ろの種に偏る**ので、次の回がこの並びをどこまで信じてよいかは この 2数 で決まります。
    """
    row = {"at": now_jst().isoformat(timespec="seconds"), "units": 0, "api": "suggest",
           "seeds": seeds, "pulls": pulls,
           "top": ranked[:80], "gaps": gap[:40], "event": "demand"}
    if stats:
        row["planned"] = stats.get("planned", pulls)
        row["fail"] = stats.get("fail", 0)
        row["workers"] = stats.get("workers")
        if stats.get("errors"):
            row["errors"] = stats["errors"]
    DEMAND.parent.mkdir(parents=True, exist_ok=True)
    with DEMAND.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def lines(row: dict, *, top: int = 25) -> list[str]:
    """印字（**判定はしない** ＝ 数を並べるだけ。GOAL (4-j-5) と同じ扱い）。"""
    planned, fail = row.get("planned"), row.get("fail") or 0
    miss = ""
    if planned and fail:
        miss = (f"・**引けなかった {fail}回／{planned}回（{fail / planned:.0%}）** ＝ "
                "**欠けるのは遅い尾 ＝ 後ろの種に偏ります**（`demand.WORKERS` の覆る条件）")
    elif planned:
        miss = f"・予定 {planned}回 を全部 引けた"
    out = [f"**検索の需要**（`demand`・{row['at'][:16]}・**{row.get('units', 0)}単位**・"
           f"{row.get('pulls', 0)}回 引いた・種 {len(row.get('seeds', []))}語{miss}）"
           "  ※ 補完は**並び**であって**量ではありません**（`studio/demand.py` の註）"]
    out.append("  -- 需要の上位（n ＝ 何個の親から出たか／best ＝ いちばん上の順位）--")
    for r in row.get("top", [])[:top]:
        out.append(f"    n{r['n']:>3} best{r['best']:>2} 平均{r['mean']:>5}  {r['q']}")
    g = row.get("gaps", [])
    out.append(f"  -- うちが 1本 も持っていない側（{len(g)}語・題材の候補）--")
    for r in g[:top]:
        out.append(f"    n{r['n']:>3} best{r['best']:>2} 重なり{r['share']:>4}  {r['q']}")
    return out
