"""台帳（data/studio/ledger.jsonl）だけを読んで、本ごとの「齢 → 再生」の並びを出す。API 0単位。

**なぜ要るか（2026-09-07 18:3x JST・optimizer・Opus が実測して足した）**:
§7 は「その回に見た1点」で書かれ続け、2回 続けて外れた。

  1本目 EkNqtkK49Bw   9.6h 127 → 28.4h 122 まで **19時間 平ら** → 30.6h 129 → 32.6h **139**
  2本目 nQbVxuWpWw8   4.4h 28 → 6.6h 28 で平ら → 8.6h **68**（2時間で +40 ＝ 2.4倍）

09/07 16:3x の §7 は「1本目は 6時間で 100%」「2本目が 28回 で止まった」と書いたが、
**どちらも平らな区間の中で見た点**だった。同じ日の旧作りと並べた「38%」も同じで、
2時間 あとには 68 対 73 ＝ **93%** になっている（旧作りのほうは 7.6h 73 → 9.6h 73 で平ら）。
＝ **平らは「止まった」ではない。** 数え直しの間隔なのか配信の波なのかは台帳からは決められないが、
どちらでも **齢の浅い1点で本と本を比べてはいけない** ことは決まる。

だからこの道具は、1本につき**並び全部**と、直近の伸び（+N回/時）を出す。
**覆る条件**: 平らな区間のあとに一度も伸びない本が 3本 続いたら、平らは本当に止まりで、
そのときは「最後の点」で比べてよい（この註と §7 の警告を消す）。
"""
from __future__ import annotations

import datetime as dt
import json

from .common import JST, ROOT, ledger_rows, now_jst


def _at(row: dict) -> dt.datetime:
    return dt.datetime.fromisoformat(row["at"]).astimezone(JST)


def ours(rows: list[dict]) -> set[str]:
    """こちらの作りの本（scheduled 行が持つ video_id）。旧作りと分けて並べるため。"""
    return {r["video_id"] for r in rows if r.get("event") == "scheduled" and r.get("video_id")}


def series(rows: list[dict]) -> dict[str, list[dict]]:
    """id → measured の点（齢の順）。同じ齢の重複は後の行を採る。"""
    out: dict[str, dict[float, dict]] = {}
    for r in rows:
        if r.get("event") != "measured" or "age_h" not in r:
            continue
        out.setdefault(r["id"], {})[round(float(r["age_h"]), 1)] = r
    return {vid: [pts[k] for k in sorted(pts)] for vid, pts in out.items()}


def returned_private(rows: list[dict]) -> dict[str, dict]:
    """id → 最後の `unscheduled` 行。**公開されたあと private へ戻した本**だけを採る。

    **なぜ日ごとの本数から抜くか**（2026-09-09 08:5x JST・optimizer・Opus が踏んだ）:
    旧 `reschedule.py` が 09/02 に打った publishAt が **09/08 23:00 JST** に発火して
    `Yy7GmcGoQ6I` が public になり、**7分後**（23:0x）に前の回が private へ戻して
    台帳に `unscheduled` を書いた。だが `lines()` は `measured` の点を持つ本を全部 数えるので、
    見出しは **10時間 たっても「09/08（2本）」**のままで、行は **「0.1h 0回」で凍った**まま
    `within_h`（72時間）ぶん 並び続ける —— private の本は `measure` が二度と見ないので、
    この点は**永久に更新されない**。

    **凍った 0回 の点が読み違えられる形**: §7 は「お試し配信は毎回 来るか」を
    浅い齢の再生で見ている（§7 の 4〜5h の行）。**7分だけ public だった本の 0回** は
    その問いの答えではないのに、並びの上では「0回 の本」と同じ形をしている。
    §7 が 09/07 16:3x に踏んだ穴（**その日に出た本を1本も見ていなかった**）と同じ型で、
    向きだけが逆 —— あちらは数え落とし、こちらは**数えすぎ**。

    **消さない**（オーナー 08/31・§8）。**行は印字するが、日の本数には入れない。**

    **覆る条件**: 戻した本がもう一度 公開されたら、その `measured` は `unscheduled` より
    後の刻で付くので、ここは自動で外れる（`_at` で比べているのはそのため）。
    「7分」を閾にはしていない —— **どれだけ長く public だったかではなく、
    いま private かどうか**で決めている。public のまま置くと決めた本が出たら、
    その本には `unscheduled` を書かないこと。
    """
    out: dict[str, dict] = {}
    for r in rows:
        if r.get("event") == "unscheduled" and r.get("id"):
            out[r["id"]] = r
    ser = series(rows)
    return {vid: r for vid, r in out.items()
            if vid in ser and _at(ser[vid][-1]) <= _at(r)}


def pending(rows: list[dict]) -> dict[str, tuple[dt.datetime, str]]:
    """id → （公開予定の刻, 題）。`measure` が毎回 書く `pending` 行から（最後の行を採る）。

    **なぜ日ごとの本数に「予約」を足すか**（2026-09-08 23:0x JST・optimizer・Opus が踏んだ）:
    この道具は `measured`（＝**公開ずみ**）だけを数えるので、**その日に出る予定の本は 1本 も数に入らない。**
    実測 09/08: 旧作りの `Yy7GmcGoQ6I` が 08/19 に上げられ 09/02 に `reschedule.py` で
    **09/08 23:00 JST** の publishAt を打たれたまま private で待っていた。`status` の「きょうの枠」には
    private として出ていたが、**この道具の日の見出しは 22時間 ずっと「09/08（1本）」**で、
    §7 は 15:0x〜21:4x の **5回 続けて**「3本目は **1本 だけの日** に出た」と書き、
    「同じ条件の 2点目」を 09/09 に期待していた。23:00 にその本が出て、**09/08 は 2本 の日になった。**
    ＝ §1 の「量は毒」がそのまま効く軸（その日の本数）が、**判定を書いている当の数から抜けていた。**
    **覆る条件**: 予約が「その日に本当に出る」ことの確からしさが崩れたら（予約のまま出なかった本が出たら）、
    見出しは「＋予約」ではなく別の印を使う（`pending` 行は残るので数え直せる）。
    """
    out: dict[str, tuple[dt.datetime, str]] = {}
    for r in rows:
        if r.get("event") != "pending" or not r.get("publish_at"):
            continue
        out[r["id"]] = (dt.datetime.fromisoformat(r["publish_at"]).astimezone(JST), r.get("title", ""))
    return out


def published_at(points: list[dict]) -> dt.datetime:
    """公開の刻 ＝ 最初の点の「いつ測ったか」から齢を引く（API を撃たずに日で束ねるため）。"""
    p = points[0]
    return _at(p) - dt.timedelta(hours=float(p["age_h"]))


def envelope(pts: list[dict]) -> list[int]:
    """齢の順の点を、**それまでの最大**（単調な包絡）に直した再生の並びを返す。API 0単位。

    **なぜ（2026-09-09 20:0x JST・optimizer・Opus。この回に撃って確かめた）**:
    `videos.list` は伸びている本を **遅れの違う複数の複製**から返す（`yt.settle_stats` の註 ＝ 19:1x の実測 2つ）。
    19:1x は「複製は2つ・低いほうは 2時間 前の値」と書きましたが、**この回に 10回 撃つと 3つ**出ました:

        gv1u7n_pCAQ（齢 10h・伸び中）  **886 が 6回・637 が 3回・823 が 1回**
          637 ＝ **17:16 の台帳の行そのもの（2.8時間 前）**・823 ＝ 19:08 の `status` の値（1時間 前）
        lQHX9LJ80Sg（34h）             **501 が 8回・493 が 2回**
        nQbVxuWpWw8（58h）・PhQ2KvuQASQ（59h）  差 0（10回 とも同じ）

    ＝ **1点の台帳の値は、真の再生を最大 28%（886 に対し 637 ＝ -249回）下に外します。**

    **読み直しを増やす手では埋まりません**（19:1x が 12回 撃って測ってある）: 同じ `lQHX9LJ80Sg` を
    19:14 に **3回 とも 468**・12回 とも 468 と読んだ回に、別の 3回 の当てでは 499 が 1度 出ています。
    ＝ **遅れている複製が「多数派」になる回が在る**ので、`settle_stats` の `max` でも救えません
    （実測: 19:14 の台帳の行は **468**、その 47分後 の 20:01 は **501**・10回 撃つと 501 が 8回）。

    **救えるのは、次の回です** —— 再生は減らないので、**それまでの最大**が、その齢での下限として
    いちばん良い推定になります。1点で救えないものを、並びで救う形。

    **効く先**: (1) `lines()` の並びと `_growth()` が、複製の取り違えで **偽の減り**（09/09 19:09 の
    711 → 637 ＝ **-74回**）と **偽の平ら**を出さなくなる。(2) §7 が 09/09 15:0x〜19:1x の 5周 にわたり
    「3本目は 3回 続けて +0 ＝ 500回 を越えない側」と書いた当のものが、**遅れている複製を 5回 読んでいた**
    ことが並びに出る（30.3h〜33.2h の 468 が 5点 続き、34.0h で 501）。

    **生の値は消しません** —— 台帳は足すだけで、`drops()` は生の組を数え続けます（§7 が引いている数なので）。
    `lines()` は上げた点に **`(生 N)`** を添えて、どこを上げたかが読めるようにします。

    **覆る条件**: (1) 再生が**本当に**減る道が出たら（本を非公開に戻す・YouTube が数を取り消す）、
    包絡はその減りを隠します —— `drops()` の生の減りが **-5回 より大きい**組で、
    同じ本の次の点が戻らなかった回が出たら、そこは包絡ではなく生で読むこと。
    (2) 伸びている本で 10回 読んで差が 0 の回が 1週間 続いたら、複製が揃った ＝ 包絡ごと要らない
    （`settle_stats` の覆る条件 (2) と同じ刻に外す）。
    """
    out: list[int] = []
    hi = None
    for p in pts:
        v = int(p["views"])
        hi = v if hi is None else max(hi, v)
        out.append(hi)
    return out

def _growth(pts: list[dict], vals: list[int] | None = None) -> str:
    """直近の2点の伸び。平らな区間の中で「止まった」と読まないための目印。"""
    if len(pts) < 2:
        return ""
    vals = vals or [int(p["views"]) for p in pts]
    a, b = pts[-2], pts[-1]
    dh = float(b["age_h"]) - float(a["age_h"])
    dv = vals[-1] - vals[-2]
    if dh <= 0:
        return ""
    return f"   [直近 {dv:+d}回 / {dh:.1f}h]"


#: **再生が1度も増えていない時間帯**（2026-09-08 04:4x JST・optimizer・Opus に台帳から数えた）。
#:
#: §7 は 10:2x・14:2x・16:3x・00:5x と、平らな点から「止まった／絞られている」を繰り返し引いてきた。
#: `_growth()` は「直近の2点」を出すだけなので、**その2点がどの時間帯に落ちたか**は見えていない。
#: 台帳の `measured` の連続する2点 549組 を刻で分けた実測:
#:
#:     02:00〜10:00 JST に落ちた2点目   伸びた **0組** ／ 平ら 178組（**178/178**）
#:     それ以外                          伸びた 15組 ／ 平ら 356組
#:
#: **＝ この帯で測った回は、何を見ても平らです。** 04:4x のこの回も 15本 全部 +0 だった。
#:
#: **交絡を先に書く（これを書かずに引くのが §7 の踏んだ形そのもの）**: このチャンネルは
#: **10:00 JST に公開する**ので、「2点目が 02〜10時」は「その本の齢が 16〜19h か 40〜43h か 64〜67h」と
#: **完全に重なっています**。齢 10h 未満の本がこの帯で測られたことは1度も無い ＝
#: **刻のせいなのか齢のせいなのかは、この台帳からは分けられません。**
#: 分けるには公開の刻を変えた本が要る（§7 の「時刻 10:00」の行）。
#:
#: > **【2026-09-09 00:2x・optimizer・Opus】この「分けられません」は、半分だけ本当でした。**
#: > **新しい作りは 10:00 JST 固定ですが、旧作りは 06:59〜18:59 のいろいろな刻に公開されています。**
#: > 実測: 帯に落ちる2点組は **42本 ぶん・齢は 9h〜191h に散っている**（`band_vs_age`）。
#: > ＝ **齢を揃えたうえで帯と外を比べられます。** 齢の束ごとに「帯の外の伸び率 × 帯の組数」を足すと、
#: > **齢だけで説明できるなら帯の中に 7.33組 の伸びが在るはず**で、実際は **0組**。
#: > 伸びの札を本の中で並べ替える検定（相関を殺さない形）で **p = 0.012**、
#: > 本ごと×齢の束ごとの、いちばん厳しい並べ替えでも **p = 0.031**。
#: > ＝ **帯の 0 は、齢だけでは説明できません。刻の側に何かが残ります。**
#: > **ただし「視聴者が寝ている」と「YouTube の数え直しが夜は回らない」は、まだ分けられません**
#: > （どちらも同じ形に出る）。**手は変わりません** —— この帯の回は伸びを読まないこと。
#:
#: > **【2026-09-09 02:5x・optimizer・Opus】その覆る条件が引かれ、00:2x の p も一緒に覆りました。**
#: > **この回の `measure`（02:59 JST ＝ 帯の中）で、帯は初めて破れました** ——
#: > `lQHX9LJ80Sg` **372 → 389（+17・齢 17.0h）**と `1huadpEk6HY` **3 → 4（+1・齢 114h）**で **2/228**。
#: > 同じ台帳で `band_vs_age` を撃ち直すと **p_video 0.011 → 0.0655・p_va 0.034 → 0.261** ＝
#: > **00:2x の覆る条件 (1)「p_va が 0.05 を越えたら、帯の 0 は齢で説明できる範囲に戻る」も、同じ回に引かれています。**
#: > **上の p = 0.012／0.031 は 00:2x の写しです。引かないこと**（`band_vs_age` を撃って読む）。
#: >
#: > **なぜ 2件 で p が 8倍 動いたか —— 分母が試行の数ではなかったからです**（`informative` の註）。
#: > 帯の **228組 のうち 221組（97%）は、その本が同じ齢で帯の外でも平ら**な組 ＝ **検出する物が無い**。
#: > さらに `measured` は1回の `measure` で全部の本を書くので、228組 は **9回の測り**から出ています。
#: > ＝ 「0/203」は「0 が 203回」ではなく、**「伸びている本が帯に居た回が、8回とも無かった」**。
#: > **9回目に初めて伸びている本が帯へ入り（`lQHX9LJ80Sg`・直前まで +30回/時）、その回に破れました。**
#: > 揃えて数えると 帯 **1/7** 対 外 **16/61**（Fisher 片側 **p = 0.40**。生の 2/228 対 22/566 なら 0.015）。
#: > **＝ 生の分母で出ていた差は、97% が「何も測っていない組」から来ていました。**
#:
#: **それでも手は決まります**: **この帯の回は伸びを読めない** ——
#: 帯が本物だからではなく、**帯に伸びる本が入る回がめったに無く、n が 7組 しか無いから**です。
#: だから数を並べるだけにして、「止まった」と書かないこと（**「帯は無い」とも書かないこと**。n=7 では、在っても見えません）。
#: **覆る条件**: (1) 帯の「検出できた組」（`informative`）が **20組** を越えても帯の伸び率が外の半分以下なら、
#: そのときは n が足りたので帯は本物として扱ってよい（いま 7組）。
#: (2) 公開の刻を変えた本が出たら、交絡が解けるので分けて数え直すこと。
#: **数は写しを持ちません** —— 上の 2/228・1/7・9回 は、この回に撃って出た数です。**引く前に撃つこと。**
DEAD_START, DEAD_END = 2, 10

#: **長さの違う2点組を、同じ分母に入れないための閾**
#: （2026-09-09 00:2x JST・optimizer・Opus が数えて足した）。
#:
#: 同じ回に `measure` を2回 撃つと、数分しか離れていない2点組が台帳に入ります。実測:
#: 台帳の 818組 のうち **74組 が 10分 未満**（23:03/23:08/23:10 のように、道具を直した回が
#: 確かめのために撃ち直したぶん）。**74組 は全部 帯の外**に落ちており、`dead_window` の
#: 「それ以外」の分母だけを 541 → 615 に膨らませていました（伸びの率 4.1% → 3.7%）
#: ＝ 帯との差を**小さく見せる**向き。帯の側（203組）は中央値 151分・最小 119.6分 で 1組も混ざっていません。
#:
#: **足すときに「構造的に平ら（数え直しは分では動かない）」と書きかけて、撃ったら外れました。**
#: 74組 のうち **2組 は動いています**:
#:
#:     EkNqtkK49Bw  09/07 16:30 **122** → 16:35 **129**   5.2分 で **+7**
#:     nQbVxuWpWw8  09/08 23:08  **68** → 23:10  **66**   1.6分 で **-2**
#:
#: ＝ **YouTube の数え直しは分の粒度でも動きます。** 落とす理由は「情報が無いから」ではなく、
#: **`dead_window` が「組あたりの率」を数えているから**です —— 2分の組と 2時間の組を同じ分母に
#: 入れると、短い組は「伸びなかった」側にばかり積まれます（短い組の伸びは 1/74 ＝ 1.4%、
#: 10分 以上の組は 22/541 ＝ 4.1%。**時間が短いぶんだけ低い**、それだけのこと）。
#: **23:0x の回が「数え直しの揺れ」と呼んだ -2 は、この 1.6分 の組です**（本が減ったのではない）。
#:
#: **覆る条件**: (1) `dead_window` を「組あたり」から「組×時間あたり」に変えたら、
#: 長さを揃える必要が無くなるので、この閾ごと要らなくなる（`band_vs_age` の `per_hour` が既にその形）。
#: (2) 数え直しの間隔が 10分 より短い回り方に変えたら、閾はその間隔まで下げること。
MIN_PAIR_MIN = 10.0

#: 齢の帯（`band_vs_age` が「同じ齢どうし」で突き合わせるときの束）。
AGE_BUCKETS = ((0, 12), (12, 24), (24, 36), (36, 48), (48, 72), (72, 10_000))


def _pairs(rows: list[dict]) -> list[dict]:
    """`measured` の連続する2点を、判定に要る形だけにして並べる。

    **`MIN_PAIR_MIN` より短い組は落とします**（上の註）。
    """
    out: list[dict] = []
    for vid, pts in series(rows).items():
        for a, b in zip(pts, pts[1:]):
            va, vb = a.get("views"), b.get("views")
            if va is None or vb is None:
                continue
            ta, tb = _at(a), _at(b)
            if (tb - ta).total_seconds() / 60.0 < MIN_PAIR_MIN:
                continue
            age = b.get("age_h")
            bucket = next(((lo, hi) for lo, hi in AGE_BUCKETS
                           if age is not None and lo <= age < hi), None)
            out.append({"vid": vid, "age": age, "bucket": bucket,
                        "gap_min": (tb - ta).total_seconds() / 60.0,
                        "band": DEAD_START <= tb.hour < DEAD_END,
                        "delta": int(vb) - int(va),
                        "a": int(va), "b": int(vb), "at": tb,
                        "grew": int(vb) - int(va) > 0})
    return out


def dead_window(rows: list[dict]) -> tuple[int, int, int, int]:
    """`measured` の連続する2点を、2点目の刻で「02〜10時 JST」と「それ以外」に分け、
    それぞれ（伸びた組, 全体の組）を数える。**写しを持たず、毎回 台帳から数える。**"""
    nm = nt = om = ot = 0
    for p in _pairs(rows):
        if p["band"]:
            nt += 1
            nm += p["grew"]
        else:
            ot += 1
            om += p["grew"]
    return nm, nt, om, ot


def drops(rows: list[dict]) -> tuple[int, int, int, str]:
    """再生が**減った**2点組を数える（組数, 減った組, いちばん大きい減り, その組の説明）。

    **`dead_window` とまったく同じ `_pairs` から数えます。ここが要点です** ——
    §7 は 17:0x（2026-09-08）から毎周この数を手で数え直しており、
    **同じ段落の中で分母が2つ**になっていました:

        帯の率      `dead_window` ＝ **`MIN_PAIR_MIN` で短い組を落としたあと**の組
        減りの数    手で書いた script ＝ **落とす前**の組（00:2x の「818組」）

    実測 2026-09-09 01:5x: 落とす前 **854組・減り 7組**／落としたあと **769組・減り 6組**。
    差の1組は `nQbVxuWpWw8` の **1.6分** の組（68 → 66）で、
    **00:2x の回が「これは数え直しの揺れで、本が減ったのではない」と名指しした当のもの**です。
    ＝ 落とす理由を書いた回自身が、**減りのほうは落とさずに数えていました。**
    手で数えるかぎり、次の回もどちらの分母を使ったか分かりません。→ 道具の側に置く。

    **何に使うか**: §7 17:0x は「床（旧作りの中央値）を越えたか」を、
    **「ここから床まで落ちるには、この台帳に1度も無い大きさの減りが要る」**という形で読んでいます。
    その「1度も無い大きさ」がこの関数の3つ目の返り値で、**覆る条件はそこに掛かっています**
    （減りが -5回 を越えた組が出たら、余裕の倍率を数え直すこと）。

    **覆る条件**: `MIN_PAIR_MIN` を変えたら、ここの数も一緒に動きます（同じ `_pairs` なので自動）。
    減りが「数え直しの揺れ」ではなく本当の取り下げ（本が消える・非公開に戻る）で出るようになったら、
    その組は別に数えること —— いまは `unscheduled` の本が measured から落ちるだけなので、組にならない。
    """
    ps = _pairs(rows)
    dec = [p for p in ps if p["delta"] < 0]
    if not dec:
        return len(ps), 0, 0, ""
    worst = min(dec, key=lambda p: p["delta"])
    where = (f"{worst['vid']} {worst['at']:%m/%d %H:%M} {worst['a']}→{worst['b']}")
    return len(ps), len(dec), worst["delta"], where


#: **「伸びを検出できた組」だけを数えるときの、齢の窓**
#: （2026-09-09 02:5x JST・optimizer・Opus が足した。下の `informative` の註）。
INFORMATIVE_AGE_H = 6.0


def informative(rows: list[dict], window_h: float = INFORMATIVE_AGE_H) -> dict:
    """**帯の分母のうち、「伸びを検出できた組」がいくつか**を数える
    （2026-09-09 02:5x JST・optimizer・Opus が足した）。

    **なぜ要るか —— §7 は 7周、この分母を「独立な試行の数」として読んできました。**
    04:4x が「帯 0/178」と書いてから、16:0x 0/203・19:1x 0/203・20:4x 0/203・
    21:4x 0/203・23:0x 0/203・00:2x 0/203 と、**毎周この 203 を分母に置いています。**
    00:2x はそこへ並べ替え検定まで足し、`p_va = 0.034` を出しました。

    **203 は、試行の数ではありませんでした。** 実測（2026-09-09 02:5x・API 0単位）:

        帯に落ちる 228組 のうち、**同じ本が 齢±6h の帯の外でも伸びていた**組   **7組**
        残り                                                                   **221組**
          ＝ その本はその齢で**どこで測っても平ら**（帯の外でも +0）
            ＝ **帯が伸びを止めたのかどうかを、この組は何も言っていません**

    **221/228（97%）は、検出する物が無い組です。** さらに `measured` は1回の `measure` で
    **全部の本を一度に**書くので、228組 は**9回の測り**から出ています（1回 25組）。
    ＝ 「0/203」は「0 が 203回」ではなく、**実質「伸びる本がその帯に居た回が、8回とも無かった」**。

    **9回目（2026-09-09 02:59 JST）に、初めて伸びている本が帯に入りました** ——
    `lQHX9LJ80Sg`（17.0h・直前まで +30回/時 で伸びていた）が **372 → 389（+17）**。
    **その回に帯は破れました**（`dead_window` が 2/228 を印字）。
    ＝ **帯が破れるのに要ったのは 203組 ではなく、「伸びている本が1本 入ること」でした。**

    出すもの: `band`/`out` は (伸びた, 伸びを検出できた組) の対、`band_all`/`out_all` は元の分母。

    **数え方**: ある組が「検出できた」＝ **同じ本の、齢が ±`window_h` の別の組が、1つでも伸びている**。
    帯と外で**同じ定義**を使い（自分自身は数えない）、片側だけ甘い分母にならないようにしてあります。
    窓を動かしても向きは変わりません（実測 ±4h: 帯 1/2・外 11/41／±6h: 1/7・16/61／±8h: 1/15・16/70）。

    **これで何が言えるか**: 帯 **1/7 (14%)** 対 外 **16/61 (26%)** ——
    Fisher の片側 **p = 0.40**（生の 2/228 対 22/566 なら p = 0.015）。
    ＝ **生の分母で出ていた差は、97% が「何も測っていない組」から来ていました。**
    `band_vs_age` の `p_va` が 0.034 → 0.261 に動いたのと**同じことを、別の道で**言っています
    （あちらは齢の束で揃え、こちらは「伸びる余地が在ったか」で揃える）。

    **これは「帯は無い」の証明ではありません。** n=7 では、在っても見えません。
    言えるのは **「まだ測れていない」**ことだけで、`dead_window` の印字はそう読むこと。

    **覆る条件**: (1) 帯の「検出できた組」が **20組** を越えても帯の伸び率が外の半分以下なら、
    そのときは n が足りたので、帯は本物として扱ってよい（いまは 7組）。
    (2) 公開の刻を変えた本が出たら、帯と齢の交絡そのものが解ける（`band_vs_age` の覆る条件 (2) と同じ）。
    (3) `MIN_PAIR_MIN` を変えたら、ここの分母も一緒に動く（同じ `_pairs` なので自動）。
    """
    pairs = [p for p in _pairs(rows) if p["age"] is not None]
    by_vid: dict[str, list[dict]] = {}
    for p in pairs:
        by_vid.setdefault(p["vid"], []).append(p)
    out: dict[str, object] = {"window_h": window_h}
    for key, want_band in (("band", True), ("out", False)):
        grew = n = 0
        for p in pairs:
            if p["band"] is not want_band:
                continue
            # 同じ本・齢が近い「別の」組が伸びていれば、この組は伸びを検出できた
            if any(q["grew"] for q in by_vid[p["vid"]]
                   if q is not p and abs(q["age"] - p["age"]) <= window_h):
                n += 1
                grew += p["grew"]
        out[key] = (grew, n)
    out["band_all"] = sum(1 for p in pairs if p["band"])
    out["out_all"] = sum(1 for p in pairs if not p["band"])
    out["occasions"] = len({p["at"] for p in pairs if p["band"]})
    return out


def band_vs_age(rows: list[dict], iters: int = 2000, seed: int = 20260909) -> dict:
    """**帯の 0 は「刻」なのか「齢」なのかを、台帳の中だけで分けにいく**
    （2026-09-09 00:2x JST・optimizer・Opus が足した）。

    上の註は「公開が 10:00 JST なので、帯は齢 16〜19h／40〜43h と重なっており、
    **刻と齢を分けられません**」と書いていた。**それは半分だけ本当でした** ——
    旧作りは 06:59〜18:59 JST のいろいろな刻に公開されているので、
    **帯に落ちる2点組の齢は 9h〜191h に散っています**（42本・実測）。
    ＝ 齢を揃えたうえで帯と外を比べる余地が、台帳の中に在ります。

    出すもの:

      `expected`  齢の束ごとに「帯の外の伸び率 × 帯の組数」を足したもの
                  ＝ **齢だけで説明できるなら、帯の中でこれだけ伸びているはず**の数
      `observed`  帯の中で実際に伸びた組（いまは 0）
      `p_video`   伸びの札を**本ごとに**並べ替えて、帯に落ちる数が observed 以下になる率
      `p_va`      同じ並べ替えを**本ごと×齢の束ごと**にしたもの（いちばん厳しい）

    **並べ替えを使う理由**: 2点組は本ごとに強く相関する（伸びる本は続けて伸びる）ので、
    ポアソンや χ² は「独立な 818組」と読んで p を小さく出しすぎます。
    札を本の中でだけ入れ替えれば、**本ごとの伸びの回数はそのまま**で、
    「その伸びが帯を避けたのは偶然か」だけを訊けます。

    **これは §5 の「教訓の形」（確かめる手を足すときは、それが元の手と違う物を見ているかを先に撃つ）
    を通してあります**: 生の 0/203 は齢で全部 説明できてしまう見込みが在り、
    齢を揃えると `expected` が 7.33 → p_va 0.031 と**別の答え**になりました（足した回の実測）。

    **覆る条件**: (1) `p_va` が 0.05 を越えたら、帯の 0 は齢で説明できる範囲に戻る
    （そのときは §7 の「帯の回は伸びを読めない」を、齢の帯の話に書き直すこと）。
    (2) 公開の刻を変えた本が出たら交絡そのものが解けるので、並べ替えは要らなくなる。
    """
    import random

    pairs = _pairs(rows)
    observed = sum(1 for p in pairs if p["band"] and p["grew"])
    per_bucket: list[tuple[tuple[int, int] | None, int, int, int, int]] = []
    expected = 0.0
    for lo, hi in AGE_BUCKETS:
        bi = [p for p in pairs if p["bucket"] == (lo, hi) and p["band"]]
        ou = [p for p in pairs if p["bucket"] == (lo, hi) and not p["band"]]
        rate = (sum(p["grew"] for p in ou) / len(ou)) if ou else 0.0
        expected += rate * len(bi)
        per_bucket.append(((lo, hi), sum(p["grew"] for p in bi), len(bi),
                           sum(p["grew"] for p in ou), len(ou)))

    rng = random.Random(seed)

    def _perm(by_bucket: bool) -> float:
        groups: dict[tuple, list[dict]] = {}
        for p in pairs:
            groups.setdefault((p["vid"], p["bucket"]) if by_bucket else (p["vid"],), []).append(p)
        live = [(g, sum(x["grew"] for x in g)) for g in groups.values()]
        live = [(g, k) for g, k in live if k]
        if not live:
            return 1.0
        hits = 0
        for _ in range(iters):
            tot = 0
            for g, k in live:
                tot += sum(rng.sample([x["band"] for x in g], k))
            if tot <= observed:
                hits += 1
        return hits / iters

    # **長さで揃える**（齢で揃えるより素直な対照）。
    # 帯の組は**外の組より長い**（中央 151分 対 123分・平均 189分 対 144分）ので、
    # 帯は伸びる機会を**多く**持っていて 0 です ＝ 長さの偏りは、この結論と**逆向き**に効いています。
    band_h = sum(p["gap_min"] for p in pairs if p["band"]) / 60.0
    out_h = sum(p["gap_min"] for p in pairs if not p["band"]) / 60.0
    out_grew = sum(1 for p in pairs if not p["band"] and p["grew"])
    per_hour = (out_grew / out_h) if out_h else 0.0
    matched = [p for p in pairs if 100 <= p["gap_min"] <= 200]
    mb = [p for p in matched if p["band"]]
    mo = [p for p in matched if not p["band"]]

    return {"observed": observed, "expected": expected,
            "p_video": _perm(False), "p_va": _perm(True),
            "buckets": per_bucket, "pairs": len(pairs),
            # 帯が外と同じ「組×時間あたり」で伸びていたら、帯の中に在るはずの伸びの数
            "expected_per_hour": per_hour * band_h,
            "band_hours": band_h, "out_hours": out_h,
            # 100〜200分 の組だけで揃えたもの（伸びた/全体）
            "matched": (sum(p["grew"] for p in mb), len(mb),
                        sum(p["grew"] for p in mo), len(mo))}


def lines(rows: list[dict], within_h: float = 24 * 3, now: dt.datetime | None = None) -> list[str]:
    now = now or now_jst()
    mine = ours(rows)
    ser = series(rows)
    gone = returned_private(rows)
    days: dict[str, list[tuple[dt.datetime, str, list[dict]]]] = {}
    # 公開されたあと private へ戻した本は、行は出すが**日の本数に入れない**（`returned_private` の註）。
    back_days: dict[str, list[tuple[dt.datetime, str, list[dict]]]] = {}
    for vid, pts in ser.items():
        pub = published_at(pts)
        if (now - pub).total_seconds() / 3600 > within_h:
            continue
        bucket = back_days if vid in gone else days
        bucket.setdefault(pub.strftime("%m/%d"), []).append((pub, vid, pts))
    # まだ公開前の本（予約）も日ごとに束ねる —— 見出しの本数から抜けると §7 が「1本 だけの日」と読む（`pending` の註）。
    waiting_days: dict[str, list[tuple[dt.datetime, str, str]]] = {}
    for vid, (pub, title) in pending(rows).items():
        if vid in ser:  # もう公開されて measured が付いた本は「予約」ではない
            continue
        if (now - pub).total_seconds() / 3600 > within_h:
            continue
        waiting_days.setdefault(pub.strftime("%m/%d"), []).append((pub, vid, title))
    # **日の見出しの本数は、窓で切らずに台帳ぜんぶから数える**（2026-09-09 10:4x に直した。下の註）。
    all_day_count: dict[str, int] = {}
    day_newest: dict[str, dt.datetime] = {}
    for vid, pts in ser.items():
        if vid in gone:
            continue
        pub = published_at(pts)
        key = pub.strftime("%m/%d")
        all_day_count[key] = all_day_count.get(key, 0) + 1
        if key not in day_newest or pub > day_newest[key]:
            day_newest[key] = pub
    out: list[str] = []
    for day in sorted(set(days) | set(waiting_days) | set(back_days), reverse=True):
        cohort = sorted(days.get(day, []))
        waiting = sorted(waiting_days.get(day, []))
        back = sorted(back_days.get(day, []))
        whole = all_day_count.get(day, len(cohort))
        head = f"{day}（{len(cohort)}本" + (f"＋予約 {len(waiting)}本" if waiting else "") + "）"
        if whole > len(cohort):
            head = (f"{day}（この日は {whole}本・**この窓に出るのは {len(cohort)}本**"
                    + (f"＋予約 {len(waiting)}本" if waiting else "")
                    + "。窓の縁で切れている ——`--days` を伸ばすこと）")
        out.append(head)
        for pub, vid, pts in cohort:
            mark = "新" if vid in mine else "旧"
            env = envelope(pts)
            trail = " → ".join(
                f"{p['age_h']:.1f}h {v}" + (f"(生 {p['views']})" if v != int(p["views"]) else "")
                for p, v in list(zip(pts, env))[-6:])
            out.append(f"  {pub:%H:%M} {mark} {vid:12s} {trail}{_growth(pts, env)}")
        for pub, vid, title in waiting:
            out.append(f"  {pub:%H:%M} 予 {vid:12s} まだ公開前（この日の本数に入る） {title[:30]}")
        for pub, vid, pts in back:
            last = pts[-1]
            out.append(
                f"  {pub:%H:%M} 戻 {vid:12s} {last['age_h']:.1f}h {last['views']}回 で private へ戻した"
                "（**この日の本数に入れない**・この点は更新されない）")
    if not out:
        out.append("（台帳に、この日数のうちに公開された本の measured がありません）")
    # **窓より前の日は、丸ごと消えるのではなく「切れている」と言う**
    # （2026-09-09 15:2x・optimizer・Opus が踏んだ）。10:4x の直しは
    # **一部だけ**が窓に入る日に「窓の縁で切れている」を付けたが、
    # **その日の本が1本も入らない日は `days` に入らないので、見出しごと出ない**。
    # 実測 09/09 15:2x: `--days 3`（既定）で **09/06 が丸ごと消えた** ——
    # いちばん若い本が 73.3h ＝ 72h の窓の外に出たため。
    # 09/06 は 8本 の日で、**§7 の「天井 437回」も「中央値 196回」もこの日から引いています**。
    # ＝ **§7 が毎周 引く対照が、道具の既定の窓から黙って落ちた。**
    # 読む側は「09/06 は無かった」と「09/06 は切れた」を区別できない。
    # **覆る条件**: `--days` の既定が窓の外の日を持たない長さに変わったら、この行は出なくなる（害は無い）。
    shown = set(days) | set(waiting_days) | set(back_days)
    cut = sorted((d for d in all_day_count if d not in shown),
                 key=lambda d: day_newest[d], reverse=True)
    if cut:
        head = "・".join(f"{d}（{all_day_count[d]}本）" for d in cut[:3])
        more = f" ほか {len(cut) - 3}日" if len(cut) > 3 else ""
        out.append(
            f"窓（`--days {within_h / 24:g}`）より前の日は、この並びに**出ていません**: "
            f"{head}{more}。**「その日は無かった」ではありません** —— 引くなら `--days` を伸ばすこと。")
    # **帯の数は、帯の中に居る回だけでなく毎回 印字する** —— §7 は毎周この数を書き写しており、
    # 手で数え直すたびに数え方が揺れていた（2026-09-09 00:2x）。
    nm, nt, om, ot = dead_window(rows)
    out.append(
        f"帯 {DEAD_START:02d}:00〜{DEAD_END:02d}:00 JST の2点組 **{nm}/{nt}** が伸びた"
        f"（それ以外は {om}/{ot}）。**{MIN_PAIR_MIN:.0f}分 未満の2点組は数えていません**"
        "（長さの違う組を同じ分母に入れないため —— studio/trend.py の `MIN_PAIR_MIN` の註）。")
    # **§7 の覆る条件 (2) の物差し（`informative`）も、帯の外の回に印字する**
    # （2026-09-09 10:4x・optimizer・Opus が足した。この回に踏んだ ——
    #  measure が 10:36 JST ＝ 帯の外に落ち、下の帯の中の段落が出なかったので、
    #  条件 (2) の「検出できた組」を **手で数え直した**。§7 が 7周 踏んだ「分母を手で数える」形そのもの。
    #  生の分母（上の行）は 04:4x に「帯の外でも毎回 印字する」に直っているのに、
    #  **判定に使う分母のほうが帯の中でしか出ていなかった**）。
    _inf = informative(rows)
    _bg, _bn = _inf["band"]
    _og, _on = _inf["out"]
    out.append(
        f"うち**伸びを検出できた組**は 帯 **{_bg}/{_bn}** 対 外 **{_og}/{_on}**"
        f"（同じ本が齢±{_inf['window_h']:.0f}h の逆側でも伸びていた組だけ。`informative` の註）。"
        f"**§7 の覆る条件 (2) はこの分母で読むこと** —— 20組 を越えるまでは「まだ測れていない」。"
        f"**この分母は帯の中で measure を撃った回にしか増えません**（帯の組は "
        f"{_inf['occasions']}回 の測りから）。")
    np_, nd, worst, where = drops(rows)
    out.append(
        f"同じ {np_}組 のうち、再生が**減った**組 **{nd}**"
        + (f"・いちばん大きい減り **{worst}回**（{where}）" if nd else "")
        + "。**帯の率と同じ分母です**（手で数え直すと分母が2つになる —— studio/trend.py の `drops` の註）。")
    # **この一文は最後に置くこと**（`tests/test_studio_trend.py` が末尾で止めている）。
    out.append(
        "並びの再生は **それまでの最大（単調な包絡）** です（`trend.envelope` の註・2026-09-09 20:0x）"
        "—— `videos.list` は伸びている本を **遅れの違う 3つ の複製**から返し、"
        "1点は真の値を **最大 28%（-249回）** 下に外します。**上げた点には `(生 N)` が付きます。**"
        "生の減りは下の行（`drops`）で数え続けています。")
    out.append("平らは「止まった」ではない —— 実測は studio/trend.py の註。齢の浅い1点で本を比べないこと。")
    if DEAD_START <= now.hour < DEAD_END:
        # **この一文は、数に追随させること**（2026-09-09 02:5x に直した）。
        # ここは長らく「**この台帳で再生が伸びたことのない帯です**」と、括弧の中の数と別に
        # **claim を直書き**していた。04:4x は「数は写しを持ちません —— 帯の中で1組でも伸びたら、
        # 印字はその日から変わります」と書いていたが、**変わったのは括弧の中の数だけ**で、
        # 文のほうは 02:59 に 2/228 になっても「伸びたことのない帯です」と言い続けた
        # （＝ 印字が自分の数と矛盾した）。**§7 が繰り返している「写しを持たない」の、この行ぶん。**
        nm, nt, om, ot = dead_window(rows)
        inf = informative(rows)
        bg, bn = inf["band"]
        og, on = inf["out"]
        if nm == 0:
            head = (f"**いまは {DEAD_START:02d}:00〜{DEAD_END:02d}:00 JST ＝ この台帳で"
                    f"再生が伸びたことのない帯です**（この帯の2点組 {nm}/{nt}・"
                    f"それ以外は {om}/{ot}）。")
        else:
            head = (f"**いまは {DEAD_START:02d}:00〜{DEAD_END:02d}:00 JST の帯の中です。"
                    f"この帯でも伸びた2点組が {nm}件 出ています**"
                    f"（{nm}/{nt}・それ以外は {om}/{ot}）。")
        out.append(
            head
            + f"**ただし分母のほとんどは「伸びを検出できない組」です** —— 帯の {inf['band_all']}組 のうち、"
            + f"同じ本が齢±{inf['window_h']:.0f}h の帯の外でも伸びていた組は **{bn}組** だけ"
            + f"（そこでの伸びは 帯 {bg}/{bn} 対 外 {og}/{on}）。"
            + f"帯の組は {inf['occasions']}回 の測りから出ています（1回で全部の本を測るので、"
            + "同じ回の組は独立ではありません）。**この回の「平ら」からは、止まったかどうかを読めません** ——"
            + "数を並べるだけにして、判定は帯の外の回へ渡すこと。"
            + "齢との交絡（この帯は齢 16〜19h／40〜43h と重なる）は `band_vs_age` が齢の束で揃えて見ますが、"
            + "**その p は、この回が いま撃った measure だけで動きます** ——"
            + "帯の中で測るたびに平らな組が分母へ入るので、**新しい伸びが1つも無くても p は小さくなります**"
            + "（実測 2026-09-09 05:5x: この回の measure を台帳から抜くと p_va 0.2015 → 0.3165・p_video 0.0245 → 0.05 に戻り、"
            + "動いたぶんは 25組 の平らだけ・うち 23組 は上の「検出できない組」でした）。"
            + f"**p を引くなら、上の {bg}/{bn} 対 {og}/{on}（検出できた組）と一緒にしか読めません。**")
    return out


def report(within_h: float = 24 * 3) -> list[str]:
    return lines(ledger_rows(), within_h=within_h)


#: **「その日に何本 出したか」を軸にして 48時間 の再生を並べ直す**
#: （2026-09-08 17:0x JST・optimizer・Opus が §7 の覆る条件に呼ばれて足した）。
#:
#: §7 15:0x/16:0x の覆る条件は「`lQHX9LJ80Sg` が 48h で 214回（09/06 の旧作りの中央値）を越えたら、
#: **日ごとの本数を軸に入れて数え直すこと**」と書いていた。17:0x に 7.1h 236回 で越えたので数え直した結果、
#: **この軸は、この台帳では日付と同じ物でした**:
#:
#:     4本/日 → 08/16 だけ    5本/日 → 09/05 だけ    13本/日 → 08/23 だけ    25本/日 → 08/22 だけ
#:     ＝ ほとんどの「本数」の値は **1日 にしか出ていない**ので、
#:       「本数ごとの中央値」は「その日の中央値」を書き写したものになる。
#:
#: 2日以上に出ている値で比べると、**同じ本数でも日が違えば桁が変わります**:
#:
#:     8本/日   08/19 中央値 1094  ／  09/06 中央値 196    （5.6倍）
#:     10本/日  08/24 中央値 1146  ／  08/31 中央値 121    （9.5倍）
#:     1本/日   08/14 の 1451 から 09/01 の 3 まで（同じ「1本/日」で 480倍）
#:
#: **＝ 本数を軸にしても、日付のぶんが丸ごと混ざったままです。** 04:4x の「刻 と 齢 が
#: 完全に重なっていて分けられない」と同じ形で、分けるには**同じ日に本数だけ変えた実測**が要る
#: （＝ 本数を変えた日を作らないと出ない。いまは 1本/日 に収束しているので、この軸は当分 埋まらない）。
#:
#: だからこの関数は**中央値を1つ出して終わりにせず**、値ごとに「何日ぶんか」を必ず一緒に印字する。
#: **数は毎回 台帳と `data/views.jsonl` から数え直す（写しを持たない）。**
#: **覆る条件**: 同じ本数の日が 3日 以上そろった値が出たら、そこで初めて日付と本数を分けられる
#: （そのときはこの註を数え直して書き換える）。1本/日 の日が増えるのが最短の道。
VIEWS_JSONL = ROOT / "data" / "views.jsonl"


def _old_series(path=None) -> dict[str, list[tuple[float, int, dt.datetime]]]:
    """旧道具が残した測り `data/views.jsonl` を読む（**過去のデータ** ＝ §8 の「使わない道具」ではない）。
    id → [(齢, 再生, 測った刻)]。無ければ空。"""
    path = VIEWS_JSONL if path is None else path
    out: dict[str, list[tuple[float, int, dt.datetime]]] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("hours") is None or r.get("views") is None:
            continue
        at = dt.datetime.fromisoformat(str(r["at"]).replace("Z", "+00:00")).astimezone(JST)
        out.setdefault(r["id"], []).append((float(r["hours"]), int(r["views"]), at))
    return out


def cohorts(rows: list[dict], old_path=None, lo: float = 40.0, hi: float = 60.0):
    """本ごとに（公開日, 公開の刻, 48時間 に最も近い点）を出す。台帳と旧データの両方から。

    返すのは (48h の点が取れた本, 公開日ごとの「その日に出た本の数」)。
    **本数は「48h の点が取れた本」ではなく、刻が分かる本 全部 で数える** ——
    そうしないと軸そのものが狂う（実測 08/24 は 10本/日 だが 48h の点は 2本 しか無い）。
    48h の点が `lo`〜`hi` の外にしか無い本は、比べられないので中央値からは落とす。
    """
    pts: dict[str, list[tuple[float, int, dt.datetime]]] = {}
    for vid, ps in _old_series(old_path).items():
        pts.setdefault(vid, []).extend(ps)
    for vid, ps in series(rows).items():
        pts.setdefault(vid, []).extend(
            (float(p["age_h"]), int(p["views"]), _at(p)) for p in ps if p.get("views") is not None)
    mine = ours(rows)
    per_day_total: dict[dt.date, int] = {}
    out = []
    for vid, ps in pts.items():
        ps.sort()
        pub = min(at - dt.timedelta(hours=h) for h, _, at in ps)
        per_day_total[pub.date()] = per_day_total.get(pub.date(), 0) + 1
        near = [(abs(h - 48.0), h, v) for h, v, _ in ps if lo <= h <= hi]
        if not near:
            continue
        near.sort()
        out.append((pub.date(), pub, vid, near[0][1], near[0][2], vid in mine))
    out.sort()
    return out, per_day_total


def _median(xs: list[int]) -> float:
    xs = sorted(xs)
    n = len(xs)
    return float(xs[n // 2]) if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def by_day_count(rows: list[dict], old_path=None) -> list[str]:
    """「その日に何本 出したか」ごとに 48時間 の再生を並べる。**値ごとに「何日ぶんか」を必ず出す。**"""
    co, total = cohorts(rows, old_path)
    if not co:
        return ["（48時間 の点が取れた本が、台帳にも data/views.jsonl にもありません）"]
    per_day: dict[dt.date, list[tuple[int, str, bool]]] = {}
    for day, pub, vid, _h, v, isnew in co:
        per_day.setdefault(day, []).append((v, vid, isnew))
    out = ["== 公開日ごとの 48時間 再生 =="]
    for day in sorted(per_day):
        vs = [v for v, _, _ in per_day[day]]
        n_new = sum(1 for _, _, isnew in per_day[day] if isnew)
        got = f"（48h の点 {len(vs)}本）" if len(vs) != total[day] else ""
        out.append(f"  {day}  {total[day]:2d}本/日{got}  中央値 {_median(vs):7.1f}  範囲 {min(vs)}〜{max(vs)}"
                   f"{f'  ← 新しい作り {n_new}本' if n_new else ''}")
    by_n: dict[int, list[dt.date]] = {}
    for day in per_day:
        by_n.setdefault(total[day], []).append(day)
    out.append("")
    out.append("== 「その日の本数」ごと ——「何日ぶんか」を必ず見ること ==")
    for n in sorted(by_n):
        days = sorted(by_n[n])
        meds = [_median([v for v, _, _ in per_day[d]]) for d in days]
        spread = (f"  同じ本数の日どうしで {max(meds) / max(min(meds), 1):.1f}倍 ちがう"
                  if len(days) > 1 else "")
        out.append(f"  {n:2d}本/日  {len(days)}日ぶん（{', '.join(d.strftime('%m/%d') for d in days)}）"
                   f"  中央値 {' / '.join(f'{m:.0f}' for m in meds)}{spread}")
    multi = [n for n, d in by_n.items() if len(d) > 1]
    out.append("")
    out.append(f"**「本数」の値 {len(by_n)}個 のうち、2日以上に出ているのは {len(multi)}個** —— "
               "残りは 1日 しか無いので、その中央値は「その日の中央値」の書き写しです。"
               "**本数を軸にしても、日付のぶんは分けられません**（studio/trend.py の註。"
               "分けるには、同じ日に本数だけ変えた実測が要る）。")
    return out
