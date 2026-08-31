#!/usr/bin/env python3
"""**次の周を、いま立ててよいか。立てるならどの役か。**

    python scripts/next_round.py --live <N>            → GO <役> <役> か WAIT <分>
    python scripts/next_round.py --record <役>[,<役>]   → 立てたことを記録する
    python scripts/next_round.py --live-set <N>        → 走っているサブの数を置く

**`--live` を必ず付けること**（`list_sessions` の数）。**0 なら間隔に関係なく GO** ——
間隔は「二重に立てない」ためのもので、**遊ばせるためではありません**
（2026-08-31・オーナー「何で止まってんだよ！」。理由は `decide()` の docstring）。

## なぜこれが要るのか（2026-08-25・オーナー指示）

> **「2種類の子の代替としてサブを使用。親はサブがやることについて判断しない」**

親が「何をやらせるか」を考え始めると、**その判断が周ごとにぶれます。**
実測でぶれていました —— 8/18以降の ship 240件のうち `verdict` はわずか14件で、
**その回のうちに終わる `fix` に寄っていました**（急いでいる側に、自分の急がせ方は直せない）。

だから親の仕事を**手続き**に落とします。親が答えるのは2つだけ:

    いま立ててよいか   ← この道具が答える（枠の速さから）
    どの役か           ← この道具が答える（**2種類とも**。欠けていれば欠けたぶん）

**中身は渡す本文（`docs/spawn_prompt.rendered.md`）が決めます。親は写すだけ。**

## 間隔をどこから取るか

`scripts/quota.py` の `recommended_floor_minutes()`。
**固定値を持ちません** —— 枠の残りと消費の速さで毎回変わるからです
（実測: 3.3日ぶん 22% のまま走って実際は 75%、**41分 → 65分**にずれていた）。

**取れない回は立てます。** 止めるより出すほうが目標に近い
（`CLAUDE.md`「投稿を途切れさせないこと」）。ただし**その旨を印字**して、
黙って速く走らないようにします。

## 1周は「2種類そろって1周」です（2026-08-25 に交互をやめた）

オーナー指示（原文）: **「親が判断せずサブで2種類の実行走らせんだよわかってっか？」**

**それまでは交互でした** —— 2つの役を1周に1つずつ、2周で1組。
**これは設計の劣化でした。** 元の形は子セッション2枚（`youtube-hourly` /
`youtube-optimizer`）が**並行して走り続ける**もので、片方だけが走る時間帯は
ありませんでした。交互にした時点で、**最適化はどの瞬間も半分止まっています。**

実測でその穴を踏んでいます —— **2026-08-25 12:37Z の周は `hourly` だけが立ち、
`optimizer` は33分間どこにも走っていませんでした。**
`--both` は docstring が約束しているだけで**実装されていませんでした。**

だからこの道具は **`ROLES` を全部返します。**

**欠けを埋めるほうは、間隔を待ちません。** いまの周に片方しか記録が無ければ、
残りは**即 GO** です（待つと、その周は片肺のまま終わります）。
1周に立つ数は `len(ROLES)` で頭打ちなので、これで暴走はしません。

**覆る条件**: 枠が尽きかけたら、`quota.py` の間隔が開いて周そのものが減ります。
**役を減らすのではなく、周を減らすこと** —— 減らすと、また片肺に戻ります。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ROUNDS = ROOT / "data" / "rounds.jsonl"

#: **いま走っているサブの数**を、親が置いていく台帳（`--live-set` で書く）。
#: `--live` を渡さなかった回は、ここを読みます。
LIVE = ROOT / "data" / "live_subs.json"

#: 台帳が古くなったら「読めなかった」と同じ扱いにする（分）。
#: **親が落ちたあとの 0 を、いつまでも信じないため**です。
LIVE_STALE_MIN = 30.0

#: 役。`docs/spawn_prompt.rendered.md` の `kind:` と同じ名前にすること。
#: **1周でこれを全部立てます。**（交互ではありません。上の節）
ROLES = ("hourly", "optimizer")

#: 同じ周とみなす幅の上限（分）。実際の幅は `round_span(floor)` が決めます。
#:
#: **固定の30分で1回落ちています**（2026-08-25、入れたその場で検算に出た）。
#: 実データは `hourly` 12:37Z / `optimizer` 13:10Z の **33.6分差**でした。
#: 30分だと別の周に割れ、**「`hourly` が欠けている」と出ます** ——
#: 主実行はそのとき走っているので、**従うと2枚目が立ちます。**
#: それは 2026-08-15 に「2人の子が同じ日の予約を取り合い、片方の生成が
#: 丸ごと無駄になった」形そのものです。
#:
#: だから幅は**間隔の半分**にします。間隔90分なら45分。
#: 次の周の1件目は前の周の開始から `floor` 以上あとなので、
#: 前の周の最後の記録との差は `floor - 幅` 以上 ＝ 幅より大きく、吸い込みません。
ROUND_SPAN_MAX_MIN = 45.0


def round_span(floor_min: float) -> float:
    """同じ周とみなす幅（分）。**絶対値で締める。間隔に比例させない。**

    **比例させて2回とも外しました**（2026-08-26）。

    1周の2件は `--record hourly,optimizer` の**1回の呼び**で書かれるので、
    実際の差は**マイクロ秒**です。隣の周までは `floor`（最低35分）離れます。
    **必要な幅は、その2つのあいだのどこか** —— `floor` に比例させる理由が
    ありません。比例させると `floor` が伸びたとき幅が隣の周に届きます。

        幅 = floor/2 のとき   間隔 36分 → 90分 で幅が45分になり、
                              **40分おきの周が数珠つなぎ**（「前の周から185分」・
                              実際は21分前。従えば二重に立つ）
        幅 = 45分 のとき      片肺の周が、前の周の1件を吸って
                              **「そろっている」に見える**（欠けが消える）

    **上限10分**は、親が1回のターンで `--record` を2回に分けても入る幅です。
    """
    return min(10.0, max(1.0, float(floor_min) / 4.0))

#: 間隔が取れなかった回に使う下限（分）。**推定ではなく、止めないための安全弁**です。
#: `quota.py` が答えられない回にゼロ間隔で回すと、枠を先に使い切ります。
FALLBACK_MIN = 90.0


def live_write(n: int, now: datetime | None = None) -> dict:
    """**いま走っているサブの数**を残す（親が `--live-set` で書く）。"""
    now = now or datetime.now(timezone.utc)
    row = {"at": now.isoformat(), "live": int(n)}
    LIVE.parent.mkdir(parents=True, exist_ok=True)
    LIVE.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    return row


def live_read(now: datetime | None = None) -> tuple[int | None, str]:
    """台帳から「いま走っているサブの数」を読む。**読めなければ `None`。**

    古い台帳（`LIVE_STALE_MIN` より前）は **読めなかった扱い**にします ——
    親が落ちたあとの `0` をいつまでも信じると、**間隔を無視して立て続ける**
    側に倒れます。**測っていないことを、どちらの側にも倒さないこと。**
    """
    now = now or datetime.now(timezone.utc)
    if not LIVE.exists():
        return None, "台帳がありません（`--live` も渡されていません）"
    try:
        row = json.loads(LIVE.read_text(encoding="utf-8").strip() or "{}")
        at = datetime.fromisoformat(str(row["at"]))
        n = int(row["live"])
    except Exception:                                          # noqa: BLE001
        return None, "台帳が読めません"
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    age = (now - at).total_seconds() / 60.0
    if age > LIVE_STALE_MIN:
        return None, f"台帳が古い（{age:.0f}分前・上限 {LIVE_STALE_MIN:.0f}分）"
    return n, f"台帳（{age:.0f}分前）"

def rows() -> list[dict]:
    if not ROUNDS.exists():
        return []
    out = []
    for line in ROUNDS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def last_round() -> dict | None:
    got = rows()
    return got[-1] if got else None


def _at(row: dict) -> datetime | None:
    """記録の時刻。読めなければ `None`（**捨てずに、無い扱い**）。"""
    try:
        got = datetime.fromisoformat(str(row["at"]))
    except Exception:                                          # noqa: BLE001
        return None
    return got if got.tzinfo else got.replace(tzinfo=timezone.utc)


def current_round(got: list[dict] | None = None,
                  span_min: float | None = None) -> list[dict]:
    """**いまの周に属する記録**（`span_min` 以内で連なるひと塊）。

    2種類そろって1周なので、**周は行ではなく塊**です。
    最後の1行だけを見ると、「`hourly` を記録した直後」と
    「`hourly` だけで終わった周」を区別できません。
    **区別できないと、片肺の周を完成扱いで見送ります**（8/25 12:37Z に実測）。
    """
    got = rows() if got is None else got
    span = round_span(floor_minutes()[0]) if span_min is None else float(span_min)
    parsed = sorted(((at, r) for r in got if (at := _at(r))), key=lambda x: x[0])
    if not parsed:
        return []

    # **識別子があるなら、それが答えです。窓を当てません**（2026-08-26）。
    # 窓は「離れていたら別の周」を推測するしかなく、比例させれば隣に届き、
    # 締めれば穴埋めの回が割れます。**幅をいくつにしても消えない誤りです。**
    # 古い行（`round` の無い行）だけが、下の窓へ落ちます。
    if str(parsed[-1][1].get("round") or ""):
        rid = str(parsed[-1][1]["round"])
        return [r for _, r in parsed if str(r.get("round") or "") == rid]

    # **最後の行を軸にする。塊の先頭を軸にしない**（2026-08-26 に踏んだ）。
    #
    # 先頭を軸にすると、**周が数珠つなぎになります** —— 入れるたびに先頭が
    # 過去へ動くので、幅が「隣どうしの間隔」を上回った瞬間、いくらでも遡ります。
    # 実測: 間隔が 36分 → 90分 になって幅が45分に広がり、
    # **40分おきに刻まれていた周が全部1つに繋がって「前の周の開始から185分」**
    # と出ました。実際の前の周は **21分前**で、従えば二重に立ちます。
    #
    # **1周の記録は `len(ROLES)` 件ちょうど**なので、件数でも止めます。
    # 幅と件数の両方 —— 幅だけだと上のように伸び、件数だけだと
    # 片肺の周に前の周の1件を吸わせます。
    group = [parsed[-1]]
    newest = parsed[-1][0]
    for at, r in reversed(parsed[:-1]):
        if len(group) >= len(ROLES):
            break
        if (newest - at).total_seconds() / 60.0 > span:
            break
        group.insert(0, (at, r))
    return [r for _, r in group]


def missing_roles(group: list[dict]) -> list[str]:
    """**いまの周で、まだ立っていない役。** 並びは `ROLES` のまま。"""
    have = {str(r.get("role") or "") for r in group}
    return [r for r in ROLES if r not in have]


def floor_minutes() -> tuple[float, str]:
    """`(間隔, どこから来たか)`。取れなければ `FALLBACK_MIN`。"""
    try:
        from scripts.quota import recommended_floor_minutes
    except Exception:                                          # noqa: BLE001
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "quota", ROOT / "scripts" / "quota.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            recommended_floor_minutes = mod.recommended_floor_minutes
        except Exception as exc:                               # noqa: BLE001
            return FALLBACK_MIN, f"quota.py を読めませんでした（{str(exc)[:60]}）"
    try:
        got = recommended_floor_minutes()
    except Exception as exc:                                   # noqa: BLE001
        return FALLBACK_MIN, f"quota.py が答えませんでした（{str(exc)[:60]}）"
    if got is None:
        return _floor_from_gauge()
    return float(got), "quota.py の実測"


def _floor_from_gauge() -> tuple[float, str]:
    """**誕生が数えられない回に、オーナーの画面の%から間隔を出す。**

    比の計算そのものは `quota.gauge_floor_minutes()` にあります
    （`sibling_check.py` も同じ口を見るので、**2か所に書かない**）。
    ここがやるのは、`FALLBACK_MIN` を基準として渡すことと、
    **なぜその数になったかを1行で言うこと**だけです。

    2026-08-30 の実測: 週 42%・いま 1.286 %/時 ÷ 許される 0.428 = ×3.0 → **270分**。
    **覆る条件は `quota.gauge_floor_minutes()` の docstring にあります**
    （速さが線の内側に戻れば `None` が返り、ここは自分で `FALLBACK_MIN` に戻ります）。
    """
    try:
        from scripts.quota import gauge_floor_minutes
    except Exception:                                          # noqa: BLE001
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "quota", ROOT / "scripts" / "quota.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            gauge_floor_minutes = mod.gauge_floor_minutes
        except Exception:                                      # noqa: BLE001
            return FALLBACK_MIN, "quota.py を読めませんでした（目盛りも見られません）"
    try:
        got = gauge_floor_minutes(FALLBACK_MIN)
    except Exception as exc:                                   # noqa: BLE001
        return FALLBACK_MIN, f"quota.py の目盛りが答えませんでした（{str(exc)[:60]}）"
    if not got:
        return FALLBACK_MIN, "目盛りが無いか、いまの速さは許される速さの内側です"
    minutes, ratio = got
    return float(minutes), (f"目盛りから（誕生が数えられないので速さの比で伸ばした。"
                            f"×{ratio:.1f}）")


def decide(now: datetime | None = None, live: int | None = None) -> dict:
    """**次の周を立ててよいか。**

    ## **間隔は「二重に立てない」ためのものです。遊ばせるためではありません**
    ## （2026-08-31・オーナー指示。**この節は消さないこと**）

    オーナー原文:

        **「何で止まってんだよ！」**
        **「だったら良いに決まってんだろ！顔色伺ってんじゃねえよ！」**

    **何が起きたか**: 親がこの道具の出す間隔（週の使用量から伸ばした **191分**）を
    **手を止める理由に使い、サブが1体も走っていない状態で待ちました。**
    この関数は経過時間しか見ていなかったので、**空いている時間が丸ごと落ちます。**

    **だから `live`（いま走っているサブの数）を先に見ます。**

        live == 0   → **GO。間隔に関係なく。**（空きを作らない）
        live > 0    → これまでどおり（欠けの穴埋め → 間隔）
        live is None → これまでどおり。**ただし「数が渡されていない」と印字する**

    `live` は `--live N` で渡すか、親が `--live-set N` で置いた台帳から読みます
    （出どころは `list_sessions`）。**渡されない回を GO に倒さないのは、
    「測っていないことを、落とす側にも立てる側にも倒さない」ため**です ——
    そこを GO に倒すと、`--live` を付け忘れた親が**毎回 二重に立てます**。
    **付け忘れが起きないよう、印字が毎回それを言います。**

    `scripts/quota.py` の間隔の伸ばしは**残します**（枠を使い切ると本当に止まる）。
    ただしそれは「**1周の重さ**」に効かせるものであって、
    **空きを作る側に使わないこと。**

    **覆る条件**: サブが 0体 でも立ててはいけない状態が見つかったとき
    （例: 立てた先が必ず即死する）。そのときは**間隔ではなく、
    その原因のほうを直すこと** —— 止める仕掛けを足さない（`CLAUDE.md` 2026-08-31）。
    **検査は `tests/test_next_round_live.py`。戻すには検査を消すしかありません。**
    """
    now = now or datetime.now(timezone.utc)
    floor, src = floor_minutes()
    live_src = "引数 --live"
    if live is None:
        live, live_src = live_read(now)
    base = {"floor_min": floor, "source": src,
            "live": live, "live_source": live_src}
    group = current_round(span_min=round_span(floor))

    # **いちばん先に見ます。** 1体も走っていない時間は、間隔で埋めるものでは
    #     ありません（オーナー 2026-08-31「何で止まってんだよ！」）。
    if live == 0:
        return {**base, "go": True, "roles": list(ROLES), "idle": True,
                "why": ("**走っているサブが0体です。間隔は見ません**"
                        f"（間隔 {floor:.0f}分・出どころ {live_src}）——"
                        "間隔は二重に立てないためのもので、遊ばせるためではありません")}

    if not group:
        return {**base, "go": True, "roles": list(ROLES),
                "why": "前の周の記録がありません（最初の1周）"}

    starts = [at for at in (_at(r) for r in group) if at]
    if not starts:
        return {**base, "go": True, "roles": list(ROLES),
                "why": "前の周の時刻を読めませんでした（止めるより出す）"}
    started = min(starts)
    passed = (now - started).total_seconds() / 60.0

    # **欠けは間隔を待ちません。** 待つと、その周は片肺のまま終わります。
    # 1周に立つ数は `len(ROLES)` で頭打ちなので、これで暴走はしません。
    missing = missing_roles(group)
    if missing:
        return {**base, "go": True, "roles": missing, "patch": True,
                "passed_min": passed,
                "why": ("いまの周に " + "・".join(missing) + " が立っていません"
                        "（**穴埋め。間隔は待ちません**）")}

    if passed >= floor:
        return {**base, "go": True, "roles": list(ROLES), "passed_min": passed,
                "why": f"前の周の開始から {passed:.0f}分（間隔 {floor:.0f}分）"}
    return {**base, "go": False, "roles": list(ROLES), "passed_min": passed,
            "wait_min": floor - passed,
            "why": f"前の周の開始から {passed:.0f}分。あと {floor - passed:.0f}分"}


def record(role: str, now: datetime | None = None) -> dict:
    """立てたことを1行残す。**周の識別子（`round`）も一緒に書きます。**

    **なぜ識別子が要るのか**（2026-08-26。時刻の窓で2回外したあと）:

    窓は「どれくらい離れていたら別の周か」を**当てる**しかありません。
    比例させれば隣に届き（数珠つなぎ）、締めれば穴埋めの回が割れます。
    **どちらも当て推量の失敗で、幅をいくつにしても消えません。**

        幅 = floor/2 → 40分おきの周が全部つながり「前の周から185分」
        幅 = 10分    → 33.6分 空けて穴埋めした周が2つに割れる

    **識別子なら当てる必要がありません。** 同じ呼びで書いた行は同じ `round`、
    穴埋めは**埋める先の `round`** を継ぎます（下の `_join_round`）。
    古い行に `round` が無い場合だけ、窓へ落ちます。
    """
    now = now or datetime.now(timezone.utc)
    row = {"at": now.isoformat(), "role": role, "round": _join_round(role, now)}
    ROUNDS.parent.mkdir(parents=True, exist_ok=True)
    with ROUNDS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def _join_round(role: str, now: datetime) -> str:
    """この行が属する周の識別子。

    **いちばん新しい周にその役がまだ無く、周が `floor` の内側にいるなら、
    その周を継ぎます**（＝穴埋め）。そうでなければ新しい周を始めます。
    **時刻の幅を当てません** —— 見るのは「その役が埋まっているか」だけ。
    """
    got = rows()
    latest = [r for r in got if r.get("round")]
    if not latest:
        return now.isoformat()
    rid = str(latest[-1]["round"])
    same = [r for r in latest if str(r.get("round")) == rid]
    if role in {str(r.get("role") or "") for r in same}:
        return now.isoformat()                      # もう埋まっている ＝ 次の周
    starts = [at for at in (_at(r) for r in same) if at]
    if starts and (now - min(starts)).total_seconds() / 60.0 > floor_minutes()[0]:
        return now.isoformat()                      # 古すぎる ＝ 次の周
    return rid                                      # 穴埋め


def main() -> int:
    ap = argparse.ArgumentParser(description="次の周を立ててよいか／どの役か")
    ap.add_argument("--record", metavar="ROLE[,ROLE]",
                    help="立てたことを記録する（役の名前。カンマ区切りで複数）")
    ap.add_argument("--live", type=int, default=None, metavar="N",
                    help="いま走っているサブの数（`list_sessions` から）。"
                         "**0 なら間隔に関係なく GO**")
    ap.add_argument("--live-set", type=int, default=None, metavar="N",
                    help="その数を台帳（data/live_subs.json）へ置くだけ")
    args = ap.parse_args()

    if args.live_set is not None:
        row = live_write(args.live_set)
        print(f"[next_round] 走っているサブ: {row['live']}体 と記録しました"
              f"（{row['at']}）")
        return 0

    if args.record:
        want = [s.strip() for s in args.record.split(",") if s.strip()]
        bad = [r for r in want if r not in ROLES]
        if bad:
            print(f"役は {ROLES} のどれかです: {', '.join(bad)}", file=sys.stderr)
            return 2
        for role in want:
            row = record(role)
            print(f"[next_round] 記録しました: {row['role']} at {row['at']}")
        return 0

    d = decide(live=args.live)
    print(f"[next_round] 間隔 {d['floor_min']:.0f}分（{d['source']}）")
    if d.get("live") is None:
        print("  [!] **走っているサブの数が渡されていません。**"
              " `--live <N>`（`list_sessions` の数）を付けること ——"
              " 付けないと、**1体も走っていない時間を間隔で埋めます**"
              "（2026-08-31 にオーナーが叱った止まり方そのものです）")
    else:
        print(f"  走っているサブ: **{d['live']}体**（{d['live_source']}）")
    roles = d["roles"]
    if d["go"]:
        print("GO " + " ".join(roles))
        print(f"  理由: {d['why']}")
        print(f"  **この{len(roles)}つを立てること。** 1周は"
              f"{len(ROLES)}種類そろって1周です"
              "（片方だけで終わると、その周は片肺）")
        for role in roles:
            print(f"  本文: docs/spawn_prompt.rendered.md の `kind: {role}` を"
                  "**そのまま**渡すこと（親が中身を考えないこと）")
        print("  **isolation: \"worktree\" と run_in_background: true を"
              "必ず付けること**（衝突を避ける／親を塞がない）")
        print(f"  立てたら: python scripts/next_round.py --record {','.join(roles)}")
        return 0
    print(f"WAIT {d['wait_min']:.0f}")
    print(f"  理由: {d['why']}")
    print(f"  いまの周は {'・'.join(roles)} がそろっています（片肺ではありません）")
    if d.get("live"):
        print(f"  **待つ理由は「二重に立てないため」です** —— いま {d['live']}体 が"
              "走っています。**間隔そのものではありません**")
    print("  **何もしないこと。** 次のトリガーか、走っているサブの完了が拾います")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
