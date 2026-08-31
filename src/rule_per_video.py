"""**1本あたり再生を、規則が固定した公開密度で測る。**（2026-08-31・最適化の回）**API 0単位。**

## この道具が答える1つの問い

> `scripts/eta.py` の天井も、門1 の日数も、分子は全部 **`per_video`（1本あたり再生）**です。
> その `per_video` は **566回**（`live_band_views` の平均）。
> **では、その 566回 は「1日に何本 出した日」の本で測った数か。**

**実測（この回に数えた・`data/views.jsonl` 22,601点）**: 標本 156本 のうち **90% が
「同じ日に 3〜21本 出した日」の本**です。**オーナーの規則は 1日1本**（`src/house_rule.py`）。

**つまり天井の分子は、規則がもう禁じている密度で測った数の上に立っています。**

## 実測（**日を単位に数え直した**。2026-08-31。この関数がそのまま出す数）

**動画ではなく「公開日」を単位にします。** 同じ日に出した本は同じ日のゆらぎを共有するので、
本を独立と数えると p が偽って小さく出ます（最初にそう数えて **×0.38・p=0.0001** と出しました。
**その数は使っていません** —— 日で数え直すと下の値になります）:

    その日の本数   日数   1本あたり再生（中央値）   （平均）
    1〜2本/日      12日        **1,070回**          942.1回
    3本以上/日     13日          **212回**
    混ぜた全体     25日          **288回**          499.0回

    1本あたり再生の弾力性（log-log・日が単位・n=25日）:
        **b = -0.604**   t = **-4.00**   95% [-0.900, -0.308]   ← **0 も -1 も含みません**

**齢の門を 96時間 に上げて数え直しても向きは同じ**でした（n=137本・23日・
`b = -0.575`・t=-3.45・95% [-0.901, -0.249]／1〜8本/日 の中央値 1,070回 対 9本以上 195回）。
**2つの門で符号も桁も動きません。**

**読み方は3つあり、どれも要ります**:

1. **1本あたりは、その日の本数で落ちます**（b が 0 と有意に違う）。
2. **合計は、それでも増えます**（`count^(1+b) = count^+0.40`。区間は -1 を含まないので、
   **この向きも有意**）。**「出すほど損」ではありません** ——
   出すほど**1本あたり**が薄まるだけです。
   （最初に本を単位に数えて `-1.40` と出し、「合計が減る」と読みかけました。
     **日で数え直したら外れです。** 合計/日 の中央値は 1,256 → 6,116 で、
     **増えています**。消さずに残します）
3. **天井に掛けてよいのは平均のほう**です（天井は N本ぶんの合計 ＝ N × 平均。
   `eta.py` の `_per_video` の註と同じ理由）。**中央値は帯の比較にだけ使います。**

## なぜこれが天井を動かすか

**規則が 1日1本 に固定されている以上、掛けてよいのは「1本/日 のときの1本あたり」だけ**です。
混ぜた 566回 は、**3〜21本/日 で薄まった本を 90% 含む平均**で、
`house_rule.PUBLISH_PER_DAY = 1` と**単位が合っていません**。

    門1（登録者1,000人）＝ 977人 ÷（per_video × 1本/日 × 登録率 0.0315%）

        per_video 566.0回（いまの印字・`live_band_views` の平均）
                            →  0.178人/日  →  **5,480日（15.0年）**
        per_video 942.1回（**規則の密度の日の平均**）
                            →  0.297人/日  →  **3,292日（ 9.0年）**

**同じ実測を、規則と同じ密度で読み直すだけで 2,188日（6.0年）手前に出ます。**
**新しく1本も出していません。API も 0単位です。**

**これは「良くなった」ではありません** —— **測り方が規則と揃っただけ**です。
到達日が動くのは、いままでの分子が**規則の外の密度で薄まっていた**からで、
チャンネルは1つも変わっていません。

## この道具が言えないこと

- **因果ではありません。** 「本数を減らせば1本あたりが上がる」とは限りません
  —— 密度の高い日は 08/20〜08/27 に固まっており、**時期と共線**です。
  日を単位にした回帰に時期を足すと、点は 15日 と 8日 に割れて力が出ません。
  **言えるのは「規則と同じ密度の日で測ると、この数だった」**という1点です。
- **`1,070回`（中央値）／`942.1回`（平均）は 1〜2本/日 の日の数**で、**n=12日**です。区間は広い。
- **長尺には当てていません**（長尺は n=22 で、密度の帯が立ちません）。

## 覆る条件

- **規則 1本/日 の下で公開した日が 10日 たまったら、その日だけで測り直すこと。**
  そのとき `at_rule` は推定ではなく**そのままの実測**になります（この関数は自動で
  そちらへ寄ります —— 規則の密度に一致する日を先に採るので、定数を持ちません）。
- **弾力性の区間が 0 をまたいだら**、この道具は分子を動かしてはいけません。
  `significant` が False を返すので、`eta.py` は混ぜた平均へ落ちます。
- **オーナーが 1日1本 を外したら**、`house_rule.PUBLISH_PER_DAY` が動き、
  採る帯もそれに合わせて動きます。**ここに数は書いていません。**
"""
from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
VIEWS = ROOT / "data" / "views.jsonl"
FORMS = ROOT / "data" / "video_forms.json"

#: 「その日の本数が規則と同じ」と見なす上限の緩さ。規則 1本/日 に対して
#: そのまま 1本 だけで採ると n=9日 になるので、**規則の 2倍まで**を同じ帯とします。
#: （実測: 1〜2本/日 の 12日 は中央値 1,070回、3本以上/日 の 13日 は 212回。
#:   齢の門を 96時間 にすると折れ目は 9本/日 に寄りますが、**向きは同じ**です）
RULE_BAND_MULT = 2


def _forms(path: Path | None = None) -> dict[str, str]:
    p = path or FORMS
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    f = raw.get("forms")
    return f if isinstance(f, dict) else {}


def _settled(views_path: Path | None = None, forms: dict[str, str] | None = None,
             form: str = "ショート") -> list[tuple[Any, str, int]]:
    """**伸びきった本だけ**を `(公開日, id, 生涯再生)` で返す。API 0単位。"""
    fm = forms if forms is not None else _forms()
    if not fm:
        return []
    try:
        from . import settle as _settle
        ripe = _settle.mature_hours(form)
    except Exception:
        ripe = 48
    series: dict[str, list[tuple[float, int, str]]] = {}
    p = views_path or VIEWS
    try:
        text = p.read_text(encoding="utf-8")
    except Exception:
        return []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        vid = r.get("id")
        if fm.get(vid) != form:
            continue
        h, v, at = r.get("hours"), r.get("views"), r.get("at")
        if h is None or v is None or at is None:
            continue
        series.setdefault(vid, []).append((float(h), int(v), at))
    out = []
    for vid, s in series.items():
        s.sort()
        if s[-1][0] < ripe:
            continue
        # 生涯 ＝ **観測した最大**。`ripe` を過ぎた本しか採らないので、
        # ショートはここで平ら（この回の実測: 96時間→600時間 で ×1.000）。
        # **`ripe` 時点の値を採ってはいけません** —— 控えが粗い本では
        # 「齢0時間・0再生」しか `ripe` の手前に無く、生涯を 0 と数えます
        # （2026-08-31 に検査で踏んだ）。
        life = max(v for _, v, _ in s)
        h0, _, at0 = s[0]
        try:
            pub = datetime.fromisoformat(at0.replace("Z", "+00:00")) - timedelta(hours=h0)
        except Exception:
            continue
        out.append((pub.date(), vid, life))
    return out


def _logreg(xs: list[float], ys: list[float]) -> dict:
    n = len(xs)
    if n < 3:
        return {"ok": False, "n": n}
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        return {"ok": False, "n": n}
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    resid = [y - (a + b * x) for x, y in zip(xs, ys)]
    s2 = sum(r * r for r in resid) / (n - 2)
    se = math.sqrt(s2 / sxx) if s2 > 0 else 0.0
    t = b / se if se > 0 else 0.0
    return {"ok": True, "n": n, "b": b, "se": se, "t": t,
            "lo": b - 1.96 * se, "hi": b + 1.96 * se}


def estimate(views_path: Path | None = None, forms: dict[str, str] | None = None,
             per_day: int | None = None, form: str = "ショート") -> dict:
    """**規則の公開密度で測った1本あたり再生。**API 0単位。

    返り::

        at_rule      規則と同じ密度の日の、1本あたり再生の**中央値**（無ければ None）
        pooled       密度を混ぜた中央値（いま `eta.py` が使っている側に相当）
        ratio        at_rule ÷ pooled
        elasticity   その日の本数に対する弾力性（`b`・`t`・95%区間）
        significant  弾力性の区間が 0 をまたがないか（**またぐなら分子を動かさない**）
        rule_days    規則の密度で公開した日の数
        why          1行の説明
    """
    if per_day is None:
        try:
            from . import house_rule
            per_day = int(house_rule.PUBLISH_PER_DAY)
        except Exception:
            per_day = 1
    rows = _settled(views_path, forms, form)
    if not rows:
        return {"ok": False, "why": "伸びきった本が 0本 です"}
    byday: dict[Any, list[int]] = defaultdict(list)
    for d, vid, v in rows:
        byday[d].append(v)
    days = [(d, len(vs), statistics.median(vs), sum(vs)) for d, vs in sorted(byday.items())]

    band = max(1, per_day * RULE_BAND_MULT)
    in_rule = [m for _, c, m, _ in days if c <= band]
    hi = [m for _, c, m, _ in days if c > band]
    el = _logreg([math.log(c) for _, c, _, _ in days],
                 [math.log(m + 1) for _, c, m, _ in days])
    # **se が 0 の点を「有意」と読まないこと。** 残差が 0（どの日も同じ回数）だと
    # 区間が幅 0 になり、`lo < 0 < hi` が False になって**情報が無いのに通ります**
    # （2026-08-31 に検査で踏んだ）。幅の無い区間は、狭いのではなく**空**です。
    sig = (bool(el.get("ok")) and el.get("se", 0.0) > 0
           and not (el["lo"] < 0 < el["hi"]))

    all_v = [v for _, _, v in rows]
    pooled = statistics.median(all_v)
    at_rule = statistics.median(in_rule) if in_rule else None
    over_videos = sum(len(byday[d]) for d, c, _, _ in days if c > band)
    out = {
        "ok": True,
        "form": form,
        "per_day": per_day,
        "band": band,
        "n_videos": len(rows),
        "n_days": len(days),
        "rule_days": len(in_rule),
        "over_days": len(hi),
        "at_rule": at_rule,
        "at_rule_mean": (statistics.mean(in_rule) if in_rule else None),
        "over_median": (statistics.median(hi) if hi else None),
        "pooled": pooled,
        "pooled_mean": statistics.mean(all_v),
        "ratio": (at_rule / pooled) if (at_rule and pooled) else None,
        "elasticity": el,
        "significant": sig,
        "share_over_band": (over_videos / len(rows)) if rows else 0.0,
    }
    b = el.get("b")
    out["why"] = (
        (f"規則 {per_day}本/日 に対し、{band}本/日 までの日 {len(in_rule)}日 の中央値 "
         f"{at_rule:.0f}回 ／ 混ぜた中央値 {pooled:.0f}回"
         + (f"（弾力性 {b:+.3f}・t={el['t']:+.2f}）" if b is not None else ""))
        if at_rule else "規則の密度で公開した日がありません"
    )
    return out


def per_video(m: dict | None = None, **kw) -> float | None:
    """**`eta.py` が分子に使ってよい数**（＝規則の密度の日の**平均**）。

    **平均を返します。中央値ではありません。** 天井も門1 も
    「N本ぶんの合計 ＝ N × 平均」で解くので、`eta.py` の `_per_video` と
    同じ単位でなければ差し替えられません（中央値は `estimate()["at_rule"]`）。

    規則の密度で測れないとき・弾力性の区間が 0 をまたぐときは `None`。
    `None` を返したときは、呼び手は**いままでどおり混ぜた平均へ落ちること**。
    ここで勝手に混ぜた平均を返すと、**落ちたことが印字から消えます。**
    """
    e = estimate(**kw)
    if not e.get("ok") or not e.get("significant") or e.get("at_rule_mean") is None:
        return None
    return float(e["at_rule_mean"])


def lines(e: dict | None = None) -> list[str]:
    """印字用（`scripts/eta.py` が1節として出す）。"""
    e = e if e is not None else estimate()
    if not e.get("ok"):
        return [f"  1本あたり再生（規則の密度）: 測れません —— {e.get('why','')}"]
    el = e["elasticity"]
    out = [
        "--- **1本あたり再生を、規則と同じ公開密度で測り直す**（`src/rule_per_video.py`・API 0単位）---",
        f"    規則は **{e['per_day']}本/日**（`src/house_rule.py`）。"
        f"標本 {e['n_videos']}本 ／ 公開日 {e['n_days']}日 ／ "
        f"**そのうち {e['share_over_band']:.0%} は規則が禁じた密度の日の本**",
    ]
    if e.get("at_rule") is not None:
        out.append(f"    **{e['band']}本/日 までの日（{e['rule_days']}日）**: "
                   f"1本あたり **{e['at_rule']:.0f}回**（中央値）／ "
                   f"**{e['at_rule_mean']:.0f}回**（平均・**天井に掛けるのはこちら**）")
    if e.get("over_median") is not None:
        out.append(f"    **{e['band']}本/日 を超えた日（{e['over_days']}日）**: "
                   f"1本あたり **{e['over_median']:.0f}回**（中央値）")
    if e.get("ratio"):
        out.append(f"    混ぜた数（いままでの測り方）: 中央値 **{e['pooled']:.0f}回** ／ "
                   f"平均 **{e['pooled_mean']:.0f}回** → 中央値どうしで **×{e['ratio']:.2f}** のずれ")
    if el.get("ok"):
        out.append(
            f"    その日の本数に対する弾力性 **{el['b']:+.3f}**（t={el['t']:+.2f}・"
            f"95% [{el['lo']:+.3f}, {el['hi']:+.3f}]・**日が単位**・n={el['n']}日）"
            + ("  ← **0 をまたぎません**" if e["significant"]
               else "  ← **0 をまたぎます（分子は動かしません）**")
        )
        out.append(
            f"    **合計/日 は `本数^{1 + el['b']:+.2f}` で増えます** —— "
            "「出すほど損」ではありません。**薄まるのは1本あたりだけ**です。"
        )
    out.append(
        "    **これは因果ではありません** —— 密度の高い日は時期と共線です。"
        "言えるのは「**規則と同じ密度の日で測ると、この数だった**」の1点。"
    )
    return out


#: **天井を「規則の密度」へ直すとき、どこまでの日を素材にしてよいか。**
#:
#: 弾力性は「日が単位」の回帰なので、**n=18本/日 の本を n=1 へ引き伸ばすと
#: 18倍 の外挿**になります（実測でそれをやると 10,585回 が出ます —— 使いません）。
#: 規則そのもの（1本/日）から遠すぎる日は素材にしないこと。
#: **3本/日 までなら、`data/views.jsonl` に 21本 の実測があり、外挿は1段です。**
CEILING_MAX_PER_DAY = 3


def ceiling_at_rule(e: dict | None = None, **kw) -> dict | None:
    """**`per_video` の天井を、規則と同じ公開密度で読み直す。**（API 0単位）

    ## なぜ要るか（2026-09-01・最適化の回に測って足した）

    `config/hypotheses.yaml` の `per_video` の天井は **1,891回**
    （`NHKylqsNfTw`）で、`scripts/eta.py` の腕の天井 **×2.01** はここから来ます。
    **その 1,891 は「全部の日の最大」です。**

    ところが**同じ `eta.py` の分子のほうは、規則の密度へ揃えてあります** ——
    `per_video()` が返す **942回** は「1〜2本/日 の日だけ」の平均で、
    混ぜた平均 572回 の **×1.65**。頭3行にも
    「掛ける本数が 1本/日 なら、掛けられる1本あたりも 1本/日 の日の数でなければ
    **単位が合いません**」と印字されています。

    **その註が、分母（天井）には当たっていませんでした。**
    ×2.01 ＝ 1,891（全密度の最大）÷ 942（規則の密度の平均）で、
    **分子と分母が別の母集団**です。

    ## 実測（2026-09-01・`data/views.jsonl` の伸びきった 160本・API 0単位）

        その日の本数   本数   最大    中央値   平均   **1,500回以上の率**
        1〜2本/日       15   1,777   1,049    964    **13.3%**
        3本/日           6   1,891   1,364  1,010    **16.7%**
        8本以上/日      139   1,857     212    412    ** 1.4%**

    **記録 1,891 は「3本/日 の日」の本です**（2026-08-16・同じ日に3本）。
    **1本/日 の日の本ではありません。**

    ## **`config/hypotheses.yaml` に書いてあった結論は、これで覆ります**

    そこにはこう書いてありました（2026-09-01）——

    > 同じ帯で数えると **n=39 → 169本**。**130本 増えて、最大は同じ1本のまま**。
    > ＝ この天井は、標本が小さいせいの下振れ（順序統計量）ではなく、
    > **いまの形（ショート・このニッチ）の天井です。次の回は、もう数え直さなくてよい。**

    **その 130本 は、ほぼ全部が 8本以上/日 の日の本です**（上の表の 139本）。
    密度で薄まる母集団を 130本 足して記録が動かなかったことは、
    **「形の天井だ」の証拠になりません。** 同じ機械が測った弾力性
    （**b = -0.66・t = -3.96・95% [-0.99, -0.34]**）が、まさにそう予測します。

    **裏取り**: 1,500回以上を出した率は **低密度 3/21（14.3%）対 高密度 2/139（1.4%）**、
    フィッシャー片側 **p = 0.0166**。**15本しかない低密度側の最大 1,777 が、
    139本ある高密度側の最大 1,857 とほぼ並びます**（順列検定 p = 0.098 ——
    **単独では有意ではないので、根拠に使うのは率のほう**）。

    ## 返す数

    素材は **`CEILING_MAX_PER_DAY` 本/日 までの日**に限り、その日の本数 `n` で
    `views × n^(-b)` として 1本/日 へ直し、その最大を返します。
    **外挿は1段（3 → 1）だけ**です。

        弱（CI の下端 -0.335）   1,891 × 3^0.335 = **2,733**
        点推定（-0.663）         1,891 × 3^0.663 = **3,918**
        強（CI の上端 -0.991）   1,891 × 3^0.991 = **5,617**

    `value` は**点推定**を返します（天井は上振れ側で読む、というこの repo の
    既定に合わせる）。**幅は捨てずに `lo` / `hi` で返す**ので、
    呼び手はどちらでも解けます。

    ## これがどこまで動かすか（**日付は出ません。そこは正直に**）

    腕 `per_video` の天井は **×2.01 → ×4.16**。
    `src/joint_cap.py` の「4本とも天井」は **35.5% → 73.5%**、
    残りの隔たりは **×2.82 → ×1.36**。
    **それでも 100% には届かないので、この直しで到達日は出ません。**
    言えるのは「**残りが半分以下になった**」までです。

    ## 覆る条件（**規則そのものが、これを2〜3週間で判定します**）

    - オーナーの規則（1日1本・2026-08-31）で、**これから出る本は全部 1本/日 の日の本**です。
      **1本/日 の日が 15日 たまって、どれも 1,900回 を超えないなら、この直しは外れ** ——
      そのとき `value` は 1,891 へ戻すこと。
    - **弾力性の区間が 0 をまたいだら**、`per_video()` と同じく `None` を返します。
      またいだ区間で天井を持ち上げないこと。
    - `CEILING_MAX_PER_DAY` を 3 より上げたくなったら、**外挿の段数が増えます。**
      上げるなら、その密度の日が何日あるかを同じ行に出すこと。

    >>> ceiling_at_rule(e={"ok": False})            # 測れなければ黙って None
    """
    e = e if e is not None else estimate(**kw)
    if not e.get("ok") or not e.get("significant"):
        return None
    el = e.get("elasticity") or {}
    if not el.get("ok") or el.get("b") is None:
        return None
    b = float(el["b"])
    if b >= 0:                     # 密度で**増える**なら、この直しは向きが逆
        return None
    rows = _settled(**{k: v for k, v in kw.items()
                       if k in ("views_path", "forms", "form")})
    if not rows:
        return None
    by: dict[Any, list[tuple[str, int]]] = {}
    for d, vid, life in rows:
        by.setdefault(d, []).append((vid, life))

    def _best(expo: float):
        out = None
        for d, items in by.items():
            n = len(items)
            if n > CEILING_MAX_PER_DAY:
                continue
            for vid, life in items:
                c = life * (n ** expo)
                if out is None or c > out[0]:
                    out = (c, vid, d, n, life)
        return out

    mid = _best(-b)
    if mid is None:
        return None
    lo = _best(-float(el["hi"])) if el.get("hi") is not None else None
    hi = _best(-float(el["lo"])) if el.get("lo") is not None else None
    raw = max((life for items in by.values() for _, life in items), default=0)
    n_src = sum(1 for items in by.values() if len(items) <= CEILING_MAX_PER_DAY
                for _ in items)
    return {
        "value": float(mid[0]), "id": mid[1], "day": mid[2],
        "day_count": mid[3], "raw": int(mid[4]),
        "lo": float(lo[0]) if lo else None,
        "hi": float(hi[0]) if hi else None,
        "b": b, "b_lo": el.get("lo"), "b_hi": el.get("hi"),
        "raw_max_all": int(raw),
        "n_source": n_src,
        "max_per_day": CEILING_MAX_PER_DAY,
        "why": (f"記録 {mid[4]:,}回（{mid[1]}・{mid[2]}）は "
                f"**{mid[3]}本/日 の日**の本。弾力性 {b:+.3f} で 1本/日 へ直すと "
                f"**{mid[0]:,.0f}回**（全密度の最大 {raw:,} の ×{mid[0] / raw:.2f}）"),
    }


def ceiling_lines(c: dict | None = None) -> list[str]:
    """`ceiling_at_rule()` を、`lines()` に続けて出す数行。**測れなければ空。**"""
    c = c if c is not None else ceiling_at_rule()
    if not c:
        return []
    span = ""
    if c.get("lo") and c.get("hi"):
        span = f"（弾力性の 95% で **{c['lo']:,.0f}〜{c['hi']:,.0f}回**）"
    return [
        f"    [!] **天井のほうも、規則の密度で読み直しました**（2026-09-01）。"
        f"全密度の最大 **{c['raw_max_all']:,}回** は、"
        f"分子（{c['max_per_day']}本/日 までの平均）と**母集団が別**でした",
        f"        → {c['why']}{span}。素材は {c['max_per_day']}本/日 までの "
        f"{c['n_source']}本・**外挿は1段**。"
        f"**規則が 1本/日 に固定された今、これは 2〜3週間で自分で判定されます**",
    ]
