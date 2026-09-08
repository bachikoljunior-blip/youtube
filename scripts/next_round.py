#!/usr/bin/env python3
"""**次の周を、いま立ててよいか。立てるならどの役か。**

    python scripts/next_round.py --live <N>            → GO <役> <役> か WAIT <分>
    python scripts/next_round.py                       → **COUNT**（数えて撃ち直せ。WAIT は出ません・2026-09-02）
    python scripts/next_round.py --record <役>[,<役>]   → 立てたことを記録する
    python scripts/next_round.py --live-set <N>        → 走っているサブの数を置く

**`--live` を必ず付けること**（`list_sessions` の数）。

**0体 でも、間隔（`quota.py` の「持続できる間隔」）は守ります**（2026-09-03・オーナー
「サブで判断して」で optimizer が決めた。理由は `decide()` の docstring）。
間隔の途中なら **WAIT と一緒に「起こし」の撃ち方を印字する**（`send_later`）ので、
**親は遊びません** —— 間隔が明けた分に自分で起きます。
2026-08-31 の「何で止まってんだよ！」は、**起こしを置かずに 191分 待った**ことへの叱りで、
「間隔を無視しろ」ではありません（原文は `decide()` に残してあります）。

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
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ROUNDS = ROOT / "data" / "rounds.jsonl"

#: **親が起きて決めたことを、GO でも WAIT でも1行 残す**
#: （2026-09-08 17:0x JST・optimizer・Opus が実測して足した）。
#:
#: それまで `data/rounds.jsonl` に載るのは **GO で立てた周だけ**だった。
#: **＝ 周が立たなかった時間は、あとから読むと 3つ が同じ顔をする**:
#:
#:     (1) 親が起きて「間隔の途中」で待った        ＝ 設計どおり
#:     (2) 親が起きたが「サブが走っている」で待った ＝ サブが詰まっている
#:     (3) 親がそもそも起きなかった                ＝ 心拍の側の壊れ
#:
#: **実測 2026-09-08: 08:41 → 14:59 JST に 378分 の穴が開きました**（その前後は 119〜124分 の等間隔）。
#: この穴について分かったのは:
#:   ・`list_triggers` の `last_fired_at` は 16:59 JST で、cron（`59 * * * *`）は毎時 撃てている
#:   ・**親は穴の中で生きていた** —— 12:41 JST に「使用状況を積む」commit を押している（`e6cae5b8`）
#: **＝ (3) ではない。しかし (1) なのか (2) なのかは、この台帳からは決められませんでした**
#: （間隔は当時 120分 なので、(1) だけでは 378分 を説明できない）。
#: §5 16:0x の回は「周は 60分 間隔・親は最大の速さで回っている」と書いていますが、
#: それは**穴の後の 2区間**だけを見た読みで、同じ窓の中に 378分 の穴が在ります。
#:
#: **原因を当てにいかず、次に同じ穴が開いたら読めるようにしました。** 親は毎周
#: `next_round_owner.py --live N` を撃つので、**その呼びの中で必ず1行 残ります**
#: ——親が覚えている必要はありません（覚えていないと残らない形は、08-24 に踏んだ形そのもの）。
#: **覆る条件**: この台帳が 1週間 ぶん たまって、穴の中が全部 (1) だったら、
#: 穴は間隔そのものなので `pace()` の側を見る。全部 (2) だったら、見るのはサブの終わり方
#: （長く走るサブ・完了通知の取りこぼし）。**1行も無い穴が出たら、そのとき初めて心拍を疑う。**
WAKES = ROOT / "data" / "parent_wakes.jsonl"
_WAKES_REAL = WAKES   # 本物の控え。検査が差し替えたかどうかを、これで見分ける


def _who() -> str:
    """**誰が撃ったか。** 親は必ず `next_round_owner.py` を通す（`docs/trigger_parent.md` 第1節）。

    これが無いと、道具を確かめただけの回が「親が起きて待った」に化けます ——
    足した回自身が、押す直前の動作確認で本物の控えに 1行 入れて気づきました（2026-09-08 17:3x）。
    **穴を読むときは `who` が `owner` の行だけ数えること。**

    **`sys.modules` だけでは足りません**（同じ回に撃って分かった）——
    親は `python scripts/next_round_owner.py` と**直に**走らせるので、
    あれは `__main__` に入り、`scripts.next_round_owner` という名前では載りません。
    実測: `next_round_owner.py --live 2` を撃っても `direct` と出た。だから argv も見ます。
    """
    # **サブの作業木から撃った回は、絶対に `owner` ではありません**
    # （2026-09-08 19:2x・optimizer・Opus が、押す直前の動作確認で**実際に false な行を1つ入れて**足した）。
    #
    # 17:3x の形は「`next_round_owner.py` を通ったか」だけを見ていました。ところが
    # **サブも確かめるときは同じ本物の呼びを撃つ**（17:3x 自身が「本物の呼びで1回 撃って確かめること」と
    # 書いている）ので、その行は `who: "owner"` で入り、**親が起きた行と1文字も違いません。**
    # ＝ `who` は「親の入口を通ったか」を見ており、「親か」を見ていませんでした。
    #
    # **親は必ず `/home/user/youtube` から走ります**（心拍の本文の1行目が `cd /home/user/youtube`）。
    # **サブは必ず `.claude/worktrees/agent-*` の作業木**（`isolation: "worktree"`）。
    # ＝ 作業木の中から撃たれた回は、入口が何であれ親ではありません。
    # **穴を読むときは、いまも `who == "owner"` の行だけ数えれば足ります。**
    if ".claude/worktrees/" in ROOT.as_posix():
        return "sub"
    if "scripts.next_round_owner" in sys.modules:
        return "owner"
    if sys.argv and Path(sys.argv[0]).name == "next_round_owner.py":
        return "owner"
    return "direct"


def log_wake(d: dict, now: datetime | None = None) -> dict:
    """親が起きて `decide()` が答えを出すたびに、その答えを1行 足す。**GO も WAIT も。**

    **検査からは本物の控えへ書かない**（2026-09-08 17:2x に、足した回自身が踏んだ）——
    `python -m pytest tests/` を撃っただけで、`main()` を呼ぶ既存の検査から
    **本物の `data/parent_wakes.jsonl` に 2行** 入った。§8 の「検査を撃つことに副作用が
    付いていた」（`niche_ceiling.kick()`・06:5x）と**同じ形**で、そちらは API の値段まで
    付いていた。ここは値段こそ 0 だが、**穴を読むための台帳に、親が起きていない行が混ざる**
    ＝ 台帳の意味そのものが壊れる。差し替えた検査（`WAKES` を tmp に向けた回）は書いてよい。
    """
    if os.environ.get("PYTEST_CURRENT_TEST") and WAKES == _WAKES_REAL:
        return dict(d)
    now = now or datetime.now(timezone.utc)
    row = {
        "at": now.isoformat(),
        # **誰が撃ったか**。親は必ず `next_round_owner.py` を通す（`docs/trigger_parent.md` 第1節）ので、
        # それが読み込まれていない回は**サブや人が手で撃った回**です。
        # これが無いと、道具を確かめただけの回が「親が起きて待った」に化けます
        # ——足した回自身が、押す直前の動作確認で本物の控えに 1行 入れて気づきました（2026-09-08 17:3x）。
        # **穴を読むときは `who` が `owner` の行だけ数えること。**
        "who": _who(),
        "go": bool(d.get("go")),
        "live": d.get("live"),
        "live_source": d.get("live_source"),
        "wait_min": round(float(d.get("wait_min") or 0.0), 1),
        "roles": list(d.get("roles") or []),
        "why": str(d.get("why") or "")[:300],
    }
    # **決めるのに使った数も残す**（2026-09-08 21:4x・optimizer・Opus が実測して足した。§5）。
    #
    # 17:0x はこの台帳を「間隔の途中／サブが走っている／起きなかった」を分けるために足し、
    # 19:1x は `decide()` に**丸め**（`target = floor - 心拍/2`）を足しました。
    # ところが `log_wake` は `why` の**日本語の文**しか残しておらず、
    # **その丸めが効いた回かどうかを、次の回が数で読めませんでした。**
    #
    # 実測（この回が踏んだ）: 19:1x の直し以降の GO は 2件 とも `idle`（0体）で、
    # **丸めの枝は1度も通っていません**。それを確かめるのに、
    # `why` の「走っているサブは 0体」という**文字列を探す**しかありませんでした
    # ——「数で見る」ための台帳が、数の側を捨てていた形です。
    #
    # `decide()` は既に全部 数で返しているので、**足すのは書き写しだけ**（API 0単位・新しい判断なし）。
    # `None` は落とします（古い行と混ぜても「無い」と読める。列を増やさない）。
    # `gap_median_min`／`gap_over_floor` は §7 21:4x の覆る条件 (1) が名指しで呼んでいる数
    # （2026-09-09 00:2x に足した。手で数えると 1周 2行 のせいで半分に出る ——`round_gaps` の註）。
    for key in ("floor_min", "passed_min", "target_min", "idle",
                "heartbeat_min", "heartbeat_source", "patch",
                "gap_median_min", "gap_over_floor"):
        got = d.get(key)
        if got is None:
            continue
        row[key] = round(got, 1) if isinstance(got, float) else got
    try:
        WAKES.parent.mkdir(parents=True, exist_ok=True)
        with WAKES.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        # 記録に失敗しても周は止めない（止める仕掛けを足さないこと・`CLAUDE.md`）。
        pass
    return row

def wake_rows() -> list[dict]:
    """親の起きの台帳を読む（壊れた行は捨てる。**止めない**）。"""
    if not WAKES.exists():
        return []
    out = []
    try:
        lines = WAKES.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _wake_at(row: dict) -> datetime | None:
    """起きの時刻。読めなければ `None`（**捨てずに、無い扱い**。`_at()` と同じ形）。"""
    try:
        got = datetime.fromisoformat(str(row.get("at")))
    except (TypeError, ValueError):
        return None
    return got if got.tzinfo else got.replace(tzinfo=timezone.utc)


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

#: **0体 のときに待つ上限（分）**（2026-09-03）。`quota.py` は「使い切った」と読むと
#: 720分 を返しますが、その推定は外れることがある（08-21 に 9%・08-30 に 3.3日ぶん）。
#: 6時間 に1回は立てて実物で確かめる —— 立てた先が 429 で落ちても、失うのは1周ぶん。
IDLE_WAIT_MAX_MIN = 360.0

#: 印字に使う、上限の言葉（数は `quota.owner_rate_cap()` が毎回 目盛りから出す。写さない）。
OWNER_CAP_WORDS = "「今までの最高速度の二分の一」"

#: **親の心拍の周期（分）。** 親が起きられるのは、この刻みの上だけです
#: （Routine `trig_01GM4wKqD8aCfrQzsQbRoA4r`・cron `59 * * * *` ＝ 毎時1回。
#:  2026-09-08 19:1x に `list_triggers` で撃って確かめた）。
#: **写しなので、`heartbeat_minutes()` が台帳から数え直せるときはそちらが勝ちます。**
HEARTBEAT_FALLBACK_MIN = 60.0

#: 心拍を数え直すのに要る、最低の間隔の数（これ未満なら上の写しを使う）。
HEARTBEAT_MIN_GAPS = 3

#: 時計の揺れ（分）。親の起きは `:59` ちょうどではなく `:59:1x`〜`:59:5x` に来るので、
#: 「1心拍 空けた」を 60.0 で締めると、0.5分 足りない回が落ちます（実測 59.8分）。
HEARTBEAT_SLACK_MIN = 2.0


def heartbeat_minutes(rows: list[dict] | None = None) -> tuple[float, str]:
    """**親が起きられる刻み（分）と、どこから来たか。**

    **なぜ要るのか**（2026-09-08 19:1x・optimizer・Opus が実測して足した。§5）:

    `decide()` は `passed >= floor` で GO を出しますが、**親は毎時1回しか起きません。**
    ＝ `floor` が 60分 をほんの少しでも越えると、**その周は次の心拍まで飛びます。**

        pace() の求める間隔 77分  → 実際の周から周は **119.3分**（60分 の刻みへ切り上がる）
        pace() の求める間隔 48分  → 実際の周から周は **59.8分**

    実測（`data/rounds.jsonl`・09/07 10:18〜09/08 18:59 の 15区間）:
    **120±5分 が 12区間・60±5分 が 2区間**（残り1つは 378分 の穴）。
    `floor` が 48分 だった 2区間 だけが 60分 で、77分 になった直後から 119.3分 に戻っています。
    ＝ **29分 の求めの差が、実際の間隔を 2倍 にしていました。**

    §5 17:0x は「77分 > 60分 なので、いまは cron（毎時）が上限ではありません」と書きましたが、
    **逆でした** —— 60分 の心拍では、60分 を越える求めは全部 120分 になります。
    実測の効き目: 許される 0.775 %/時 に対し、区間の実測は **0.443 %/時**（57%）。

    **数は写しを持ちません。** 心拍が変われば（オーナーが cron を触る・別の親になる）、
    `data/parent_wakes.jsonl` の `who == "owner"` の行の間隔が先に変わります。
    間隔が `HEARTBEAT_MIN_GAPS` 本 たまるまでは `HEARTBEAT_FALLBACK_MIN`（cron の写し）。

    **【2026-09-08 21:4x・optimizer・Opus】上の「親は毎時1回しか起きません」は、
    この関数が読む台帳自身に 1日 で覆されました。** `who == "owner"` の 9行・間隔 8本 は
    **15.2・15.8・16.7・22.5・25.6・25.7・39.1・60.0分 ＝ 中央値 24.1分**で、
    **60分 は 8本 中 1本 だけ**（`:59` に来ているのは最初の 2行 だけ）。
    親は `decide()` の idle の枝で **自分に `send_later` の起こしを置く**ので、
    cron の刻みに縛られず**分の粒度で起きています。**
    **直す所はここにありません** —— 写しを持たない形に書いてあるので、間隔が 3本 たまった時点で
    この関数は 60 → 24.1 へ自分で乗り換えました（本物の呼びで `heartbeat_min: 24.1` と出た）。
    **古いのは上の 289〜299行 の説明のほうで、あれは 19:1x の時点の読みとして残してあります。**
    **いまの 24.1分 は間隔 8本 と薄い**ので、20本 たまったら数え直すこと（§5 の覆る条件 (4)）。

    **中央値で取るのは、送り込みの起こし（`send_later`）や穴が混ざるから**です
    （平均だと 378分 の穴が1つ入るだけで倍になる）。
    """
    got = rows if rows is not None else wake_rows()
    at = sorted(t for r in got if r.get("who") == "owner"
                and (t := _wake_at(r)) is not None)
    gaps = [(b - a).total_seconds() / 60.0 for a, b in zip(at, at[1:])]
    gaps = [g for g in gaps if g > 0]
    if len(gaps) < HEARTBEAT_MIN_GAPS:
        return HEARTBEAT_FALLBACK_MIN, (
            f"cron の写し（間隔 {len(gaps)}本 < {HEARTBEAT_MIN_GAPS}本）")
    got_med = median(gaps)
    # 歯止め。台帳が壊れた回に、心拍を 0 や 1日 と読ませない。
    got_med = min(180.0, max(10.0, got_med))
    return got_med, f"`data/parent_wakes.jsonl` の実測（間隔 {len(gaps)}本 の中央値）"

#: **親が置いた起こし**の台帳（`decide()` が WAIT を印字したときに書く）。
#: 同じ周のあいだに親が何度 起きても（サブの完了通知は何度も来る）、
#: `send_later` を撃つのは1回にするため。**親が撃ったかどうかは、ここには入りません**
#: （撃たなかった回は、心拍 :59 が拾います）。
WAKE = ROOT / "data" / "parent_wake.json"


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

def wake_read(now: datetime | None = None) -> datetime | None:
    """台帳にある、**まだ来ていない**起こしの時刻。無ければ `None`。"""
    now = now or datetime.now(timezone.utc)
    if not WAKE.exists():
        return None
    try:
        row = json.loads(WAKE.read_text(encoding="utf-8").strip() or "{}")
        at = datetime.fromisoformat(str(row["wake_at"]))
    except Exception:                                          # noqa: BLE001
        return None
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    return at if at > now else None


def wake_write(wake_at: datetime, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    row = {"at": now.isoformat(), "wake_at": wake_at.isoformat()}
    WAKE.parent.mkdir(parents=True, exist_ok=True)
    WAKE.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    return row


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


def round_gaps(limit: int | None = None) -> list[float]:
    """**周から周の間隔（分）**。`data/rounds.jsonl` を `round` で畳んでから数えます。

    **なぜ畳むのか**（2026-09-09 00:2x JST・optimizer・Opus が踏んで足した）:
    `rounds.jsonl` は **1周につき役の数だけ行を書きます**（いまは `hourly` と `optimizer` で 2行、
    同じ時刻・同じ `round`）。素朴に「行から行」を数えると **0分 が1つおきに挟まり**、
    中央値が **半分**になります。実測（この回・直近10区間）:

        素朴に行から行   **39.6分**      ← 0.0 が交互に入る
        `round` で畳む   **80.4分**      ← 本当の周から周

    **これは §7 21:4x の覆る条件 (1) が名指しで呼んでいる数です** ——
    「周から周の中央値が `floor` の 1.25倍 を越えていたら、上限は丸めではない」。
    素朴に数えると 39.6分 ＝ `floor`（76分）の **0.52倍** になるので、
    **その条件は永久に引かれません**（＝ 鳴らない見張り。§5「必ず一致する2つ目の意見に、
    確かめる力は無い」の親戚で、こちらは「**必ず通る門**」）。
    だから、この数は手で数えずに、ここから引くこと。

    `round` を持たない古い行（36/441）は、時刻そのものを識別子に使います
    （同じ時刻の行だけが畳まれる ＝ 畳みすぎない側に倒す）。
    """
    starts: dict[str, datetime] = {}
    for row in rows():
        at = _at(row)
        if at is None:
            continue
        key = str(row.get("round") or row.get("at"))
        starts[key] = min(starts.get(key, at), at)
    got = sorted(starts.values())
    gaps = [(b - a).total_seconds() / 60.0 for a, b in zip(got, got[1:])]
    return gaps[-limit:] if limit else gaps


def gap_median(limit: int = 10) -> float | None:
    """直近 `limit` 区間の**周から周**の中央値（分）。無ければ `None`。"""
    got = round_gaps(limit=limit)
    return median(got) if got else None


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
    # **「実測」と名乗ってよいのは、歯止めで切られていないときだけ**（2026-09-01）。
    #     長らくここは無条件に `quota.py の実測` と印字していました。
    #     実測 09/01: 測って出たのは 289.7時間 で、返っていたのは
    #     `FLOOR_MAX_CLAMP` の **90分**（×193 切られた）。**90 は定数です。**
    try:
        from scripts.quota import pace as _pace
    except Exception:                                          # noqa: BLE001
        try:
            _pace = mod.pace                                   # type: ignore[name-defined]
        except Exception:                                      # noqa: BLE001
            _pace = None
    if _pace is not None:
        try:
            pc = _pace() or {}
        except Exception:                                      # noqa: BLE001
            pc = {}
        if pc.get("floor_clipped") == "max" and pc.get("floor_raw"):
            return float(got), (
                f"**歯止めで切られた数です（実測ではありません）** —— "
                f"測って出たのは {pc['floor_raw'] / 60:.1f}時間 で、"
                f"`quota.FLOOR_MAX_CLAMP` が {got:.0f}分 に切りました。"
                f"**そのぶん鎖は速すぎる側で回ります**")
        if pc.get("floor_clipped") == "spent":
            return float(got), "**枠を使い切っています**（歯止めの上限。実測ではありません）"
        # **下側で切られた回も「実測」ではありません**（2026-09-02 に踏んだ）。
        #     上の枝は `max` しか見ておらず、`min` は素通りで「実測」と名乗って
        #     いました。実測 09/02: 測って出たのは **2分**（窓が食い違っていた）で、
        #     返っていたのは `FLOOR_MIN_CLAMP` の **10分**。**10 は定数です。**
        #     下側で貼りついたら、**まず窓と分母を疑うこと**（`quota._gauge_reset`）。
        if pc.get("floor_clipped") == "min" and pc.get("floor_raw"):
            return float(got), (
                f"**歯止めで切られた数です（実測ではありません）** —— "
                f"測って出たのは {pc['floor_raw']:.0f}分 で、"
                f"`quota.FLOOR_MIN_CLAMP` が {got:.0f}分 に持ち上げました。"
                f"**下側に貼りついているときは、まず1周の分母を疑うこと**")
        # **枠が戻った直後は、1周が「床」で立っています**（2026-09-02）。
        #     リセットの瞬間は測れないので、`pace()` は窓の下限を採り、
        #     リセット前に測れていた数を床に当てています。**それは実測ですが、
        #     いまの枠で測った数ではありません。** 名乗りを分けること。
        if pc.get("per_lap_floored") and pc.get("births"):
            return float(got), (
                f"**いまの枠で測った数ではありません** —— 枠が戻った直後で、"
                f"いまの枠から出るのは 1周 {pc.get('per_lap_raw', 0):.3f}%（下限・"
                f"周 {pc['births']}件）だけ。リセット前の実測 "
                f"{pc.get('per_lap', 0):.3f}% を床にしています")
        if pc.get("births"):
            return float(got), (f"quota.py の実測（1周 {pc.get('per_lap', 0):.3f}%"
                                f"・**周 {pc['births']}件**"
                                + (f"／サブ {pc['subs']}体" if pc.get("subs") else "")
                                + "）")
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

    ## **0体 でも間隔は守る。ただし遊ばない —— 起こしを置いて待つ**（2026-09-03）

    オーナー原文（09/02 18:4x）: **「使用量は定期的に画面送るからとりあえず最初は
    今までの最高速度の二分の一の速度でやって」**、09/03 06:3x: **「サブで判断して」**
    （親が 03:3x・06:2x に伝えた食い違いへの答え。判断は optimizer の回）。

    **食い違い**: `quota.py --pace` は「上限 0.743 %/時・持続できる間隔 140分」と言い、
    この関数は「0体 なら間隔を見ずに GO」と言っていた。サブは背景で ~25分 で終わり、
    終わると親が起きて 0体 を見る → 即 GO。**実物は 2体 を 17〜30分 ごと**
    （`data/rounds.jsonl` 09/03 00:04〜06:39・15周）。

    **実測 09/02 22:01 → 09/03 06:21 JST**: 週「すべてのモデル」19→45%・「Fable のみ」
    21→71%（3.12 %/時 ＝ 上限の 4.2倍）。**このままなら すべてのモデルは 09/03 23:58 JST
    に 100%、土曜 07:00 のリセットまで 31時間 鎖が止まる。** 06:0x には 5時間枠の 429 で
    サブ2体が落ちた。**「0体 → 即 GO」は、止まらないためのつもりで、31時間 止める側でした。**

    **決めたこと**:

        live == 0 ・ 前の周の開始から floor 以上   → GO（間隔が明けている）
        live == 0 ・ floor の途中                    → **WAIT。ただし親は起こしを置く**
                                                       （`send_later` を印字どおりに撃つ。
                                                         起きたら間隔が明けている ＝ GO）
        live == 0 ・ 片方だけ欠けている              → 欠けを GO（これまでどおり）
        live > 0                                     → これまでどおり（二重に立てない）
        live is None                                 → COUNT（これまでどおり）

    **なぜ「起こし」なら 08-31 の叱りに反しないか**: あのとき親は 191分 を
    **何も置かずに**待った（次に起きるのは心拍の :59 か、居ないサブの完了）。
    起こしを置けば **間隔が明けた分に必ず起きる**ので、空きは「持続できる間隔」ぶんだけ ——
    それは枠を使い切って 31時間 空けるより短い。**「止めない」を守るのは、こちらです。**
    `send_later` は即返り（承認待ちにならない・`docs/trigger_parent.md` §5 実測）。

    待ちの上限は `IDLE_WAIT_MAX_MIN`（6時間）。`quota.py` が「使い切った」と言って
    720分 を返しても、6時間 に1回は立てて**実物で確かめる**（推定は外れる。
    2026-08-21 に 9%・08-30 に 3.3日ぶん ずれた）。

    **覆る条件**: (1) オーナーが速さの上限を外したら（`quota.OWNER_SPEED_DIVISOR`）
    間隔は自然に縮む —— この関数は触らない。(2) 実測で「起こしが届かない」が出たら
    （`data/parent_wake.json` の `wake_at` を 15分 過ぎても `rounds.jsonl` に周が無い）、
    そのときは起こしの口を直す。**0体 即 GO に戻すのではなく。**

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
    # **周から周の中央値を、毎行 残します**（2026-09-09 00:2x・§7 21:4x の覆る条件 (1)）。
    # あの条件は「中央値が `floor` の 1.25倍 を越えていたら」で判定するのに、数の出どころが
    # `data/rounds.jsonl` の**手数え**でした —— そこは 1周 2行 なので、素朴に数えると半分に出ます。
    # 台帳に入れておけば、次の回は撃つだけで読めます（`round_gaps` の註）。
    gm = gap_median()
    if gm is not None:
        base["gap_median_min"] = round(gm, 1)
        base["gap_over_floor"] = round(gm / floor, 2) if floor else None
    group = current_round(span_min=round_span(floor))

    # **0体 は「間隔を見ない」ではなく「起こしを置いて待つ」**（2026-09-03・上の節）。
    #     09/03 00:04〜06:39 の 15周（17〜30分 ごと）が、上限 0.743 %/時 の 4.2倍 で
    #     枠を食い、23:58 JST に尽きる線に乗っていた。
    idle = (live == 0)
    if idle:
        floor = min(floor, IDLE_WAIT_MAX_MIN)
        base["floor_min"] = floor

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

    # **心拍の刻みへ「近いほうへ」丸める**（2026-09-08 19:1x・optimizer・Opus。§5）。
    #
    # `passed >= floor` だけで見ると、**間隔は必ず心拍の刻みへ切り上がります** ——
    # 親が起きられるのは毎時1回なので、`floor` 77分 は 119.3分 になり、48分 は 59.8分 になる。
    # 実測（`data/rounds.jsonl` 15区間）: **120±5分 が 12区間・60±5分 が 2区間**。
    # 60分 の 2区間 は `floor` が 48分 だった回で、77分 に変わった直後に 119.3分 へ戻っています。
    # ＝ **求めの 29分 の差が、実際の間隔を 2倍 にしていました**（許される 0.775 %/時 に対し実測 0.443 %/時）。
    #
    # 直しは「切り上げ」を「近いほうへ」に変えるだけです:
    #     いま出す      → 間隔は passed（floor に足りない ぶんだけ短い）
    #     次の心拍まで待つ → 間隔は passed + 心拍（floor を越えた ぶんだけ長い）
    #   **どちらが floor に近いか**で決める ＝ `passed >= floor - 心拍/2`。
    #
    # **速さの上限は変わりません** —— 親は1心拍に1回しか起きないので、
    # これで増えるのは「刻みを1つ飛ばさなくなる」ぶんだけ（＝ §5 16:0x が「毎時が上限」と
    # 呼んだ線そのもの）。`docs/FOR_OWNER.md` の窓は1時間 なので、依頼が2回 出る側にも動きません。
    # **上振れは pace() が次の周で引き戻します**（目盛りを読み直して `floor` を伸ばす ＝
    # そのとき `floor - 心拍/2` が 60分 を越え、また 120分 に戻る）。切り上げだけが、
    # 引き戻しの利かない片側の偏りでした。
    beat, beat_src = heartbeat_minutes()
    base["heartbeat_min"] = beat
    base["heartbeat_source"] = beat_src
    # **0体 の回は丸めません。** そのときは親が `send_later` で**分の粒度**の起こしを
    # 置けるので（下）、心拍の刻みに縛られていません ＝ 丸める理由がない。
    #
    # 丸めても **1心拍に2周は立てない**: 心拍の外から起こされた回（`send_later`・手で撃った回）に
    # `floor` が心拍より短いと、`floor - 心拍/2` が小さくなりすぎるので、下限で締めます。
    target = floor
    if not idle:
        target = max(floor - beat / 2.0, beat - HEARTBEAT_SLACK_MIN)
        target = min(target, floor)
    if passed >= target:
        early = floor - passed
        return {**base, "go": True, "roles": list(ROLES), "passed_min": passed,
                "idle": idle, "target_min": target,
                "why": (f"前の周の開始から {passed:.0f}分（間隔 {floor:.0f}分）"
                        + ("・走っているサブは 0体" if idle else "")
                        + (f"・**次の心拍（{beat:.0f}分 後）まで待つと "
                           f"{passed + beat:.0f}分 になり、間隔から {passed + beat - floor:.0f}分 "
                           f"外れます。いまなら {early:.0f}分**（心拍は {beat_src}）"
                           if early > 0 else ""))}
    wait = target - passed
    out = {**base, "go": False, "roles": list(ROLES), "passed_min": passed,
           "wait_min": wait, "idle": idle, "target_min": target,
           "why": f"前の周の開始から {passed:.0f}分。あと {wait:.0f}分"}
    if idle:
        # **起こしの時刻**（間隔が明ける瞬間 ＋ 1分。起きたとき `passed >= floor` に
        #     なっているように。`send_later` は分の粒度）。
        out["wake_at"] = started + timedelta(minutes=floor + 1.0)
        out["wake_min"] = max(1, int(wait) + 1)
        out["why"] = (f"**0体・間隔の途中**（前の周の開始から {passed:.0f}分・間隔 {floor:.0f}分）。"
                      f"**起こしを置いて待つ** —— 立てると上限 "
                      f"{OWNER_CAP_WORDS} を越え、枠を使い切った先で 31時間 止まる"
                      "（09/03 06:3x「サブで判断して」）")
    return out


def record(role: str, now: datetime | None = None,
           round_id: str | None = None) -> dict:
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
    rid = round_id or _join_round(role, now)
    row = {"at": now.isoformat(), "role": role, "round": rid}
    ROUNDS.parent.mkdir(parents=True, exist_ok=True)
    with ROUNDS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def record_many(roles: list[str], now: datetime | None = None) -> list[dict]:
    """**1回の呼びで書く行は、全部 同じ周**（2026-09-02 夜・親が実物で踏んだ）。

    ## 何が起きていたか（`data/rounds.jsonl` の実物）

        09:19:45 optimizer  round=09:19:45     ← 前の周が片肺で終わっていた
        09:53:37 hourly     round=09:19:45     ← `--record hourly,optimizer` の1行目が
                                                  **前の周の穴埋め**に吸われる
        09:53:37 optimizer  round=09:53:37     ← 2行目は「もう埋まっている」で**新しい周**
        11:26:29 hourly     round=09:53:37     ← 以下、周ごとに1つずつ ずれ続ける
        11:26:29 optimizer  round=11:26:29

    `_join_round` は**1行ずつ**「その役が最新の周に無ければ継ぐ」と決めるので、
    2つの役を同時に立てた呼びの1行目が、前の片肺の周を埋めに行きます。
    すると `current_round()` はいつも **optimizer だけの周**を見て、
    **hourly が終わった直後でも「GO hourly（穴埋め）」** と出します。
    親がそれに従えば、走ったばかりの役を二重に立てる ＝ 「二分の一の速度」に反します。

    **同時に立てた役は、同じ周です。** `ROLES` をぜんぶ含む呼びは**必ず新しい周**を
    始めます（穴埋めは、役を1つだけ渡した呼びのときだけ）。
    検査は `tests/test_next_round.py::test_2種類そろった呼びは前の片肺を埋めない`。
    """
    now = now or datetime.now(timezone.utc)
    want = [r for r in roles if r]
    rid = now.isoformat() if set(want) >= set(ROLES) else None
    return [record(role, now=now, round_id=rid) for role in want]


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


def refresh_rendered() -> list[str]:
    """**親が読む写しを、親の周のたびに焼き直す**（API 0単位・数十ミリ秒）。

    ## なぜ足したか（2026-09-01）

    **親が実際に読むのは `docs/trigger_body.rendered.md` です**（写し）。
    正本は `docs/trigger_body.md` で、焼き直すのは
    `scripts/trigger_sync.py --write-rendered` の1手 ——
    **その1手を、誰も打っていませんでした。**

    実測 2026-09-01: 写しは**64行ぶん古く**、次のものが**全部 入っていません**でした:

        「**止めないこと**」（オーナー 2026-08-31「何で止まってんだよ！」）
        「サブが1体も走っていないなら、WAIT でも立てること」
        固定の与件4件（1日1本・作り置きなし・サブ二台・消さない）
        `model: "opus"` の指定／`isolation: "worktree"`

    **親は、その古い写しを毎周 当てていました。**
    `tests/test_trigger_sync.py::test_rendered_copy_is_current` は赤で立っており、
    文面は「`--write-rendered` を打つこと」でした ——
    **打つ側が居ない検査**です（`deadline_check`・`pool_drain` と同じ形の3件目）。

    **だから、打つ側をここに置きます。** `next_round.py` は親が毎周
    いちばん最初に撃つ道具で、**写しを読む直前**に走ります。

    **止める仕掛けではありません** —— 焼けなくても親は進みます
    （返り値は「何を焼いたか」の行だけで、例外は外へ出しません）。

    **覆る条件**: 親が正本（`docs/trigger_body.md`）を直に読むようになったら、
    写しごと要らなくなります。そのときは、この関数と
    `--write-rendered` の両方を消すこと（**片方だけ消さないこと**）。
    """
    out: list[str] = []
    for mod, flag in (("trigger_sync", "--write-rendered"),
                      ("spawn_prompt", "--write-rendered")):
        try:
            import subprocess
            r = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / f"{mod}.py"), flag],
                capture_output=True, text=True, timeout=90, cwd=str(ROOT))
            if r.returncode == 0:
                out.append(f"  写しを焼き直しました: scripts/{mod}.py {flag}")
            else:
                out.append(f"  [!] 写しが焼けません（{mod}）: "
                           f"{(r.stderr or r.stdout).strip()[:120]}")
        except Exception as exc:                               # noqa: BLE001
            # **ここで止めないこと。** 写しが古いのは損ですが、
            # 親が動かないほうがもっと損です（A10）。
            out.append(f"  [!] 写しが焼けません（{mod}）: {str(exc)[:120]}")
    return out


def kinds_allowed() -> dict:
    """**この周が ship してよい種別を、作りはじめる前に出す**（API 0単位・約9秒）。

    ## なぜ足したか（2026-09-04 深夜・最適化の回。実測は下）

    `run_marker.py` の `fix` の門は **2026-09-01 から在り**、以後4日 ぶん
    締め直されています。**それでも `fix` の比は 78% → 60% で止まり**、
    到達日は動いていません。**この回に数えた実物**（`data/runs.jsonl`）::

        ship 241件（09/01〜09/04）／ `eta_days` は **241件 すべて 10^9**
        `gate1p_days` は在る 6件 が **全部 511.538**（＝ 4日で 0.0日 も動いていない）
        `fix_gate` の発火 **106回** —— **waived 50回（47%）**
        止めた 56回 のうち **12回（21%）が、同じ文面を 45分以内に ship**
          （中央 +6分・1件は sim=1.00 の丸写し・**10件は種別も `fix` のまま**）
        ＝ 発火 106回 のうち **62回（58%）は、何も変えていません**

    **門が効かない理由は、締め方ではなく置き場所です。** あの門は
    **周の終わり（`--ship`）に立っています** —— そこへ着いた時点で、
    その周の時間はもう使い切っています。残る道は3つ:

        1. 免除する（50回）  2. 言い換えて通す（12回）  3. 周を捨てる（0回）

    **誰も 3 を選びません。** だから門は「何を選ぶか」を変えられず、
    **「何と呼ぶか」だけを変えて**きました。これが、近づかない周が
    選ばれ続けた口です（`--moves` の自己申告ではなく、ここ）。

    **だからこの読み出しを、周の頭に置きます。** `next_round.py` は親と
    サブが毎周いちばん最初に撃つ道具で、**まだ何も作っていない時点**で走ります。
    同じ述語（`untreated_slot` / `fix_run_len` / `fix_since_move` /
    `judgeable_today`）を、**40分 早く**渡すだけです ——
    門の定数は1つも変えていません（変えると、また言い換えが増えるだけ）。

    **止める仕掛けではありません。** 返すのは行だけで、例外は外へ出しません。

    **覆る条件**: `data/runs.jsonl` の `fix_gate` の
    「止めた直後45分以内の同文 ship」が **30日 0件** で、かつ waived の比が
    2割 を切ったら、頭で渡す意味は消えています（門だけで足ります）。
    そのときは、この関数と `main()` の呼びの**両方**を消すこと。
    """
    out: dict = {"lines": [], "blocked": [], "ok": True}
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        import run_marker as rm                                # noqa: PLC0415
    except Exception as exc:                                   # noqa: BLE001
        out["lines"].append(f"  [!] 種別の下読みが出せません: {str(exc)[:100]}")
        return out

    def _safe(fn, default):
        try:
            return fn()
        except Exception:                                      # noqa: BLE001
            return default

    slot = _safe(rm.untreated_slot, {"fired": False, "why": "", "video_id": "", "topic": ""})
    run_len = _safe(rm.fix_run_len, 0)
    since = _safe(rm.fix_since_move, 0)
    ready = _safe(rm.judgeable_today, [])
    cap_run = getattr(rm, "FIX_RUN_CAP", 2)
    cap_since = getattr(rm, "FIX_SINCE_MOVE_CAP", 5)

    why: list[str] = []
    if slot.get("fired"):
        why.append(f"きょうの枠の本が前提の脚を通っていない（{slot.get('why', '')[:90]}）")
    over = (run_len >= cap_run) or (since >= cap_since)
    if over and ready:
        why.append(f"`fix` の連 {run_len}/{cap_run}・動いた ship から {since}/{cap_since}"
                   f"、かつ きょう判定できる前提が {len(ready)}件")

    out["lines"].append(
        f"  種別の下読み: `fix` 連 {run_len}/{cap_run}・動いた ship から {since}/{cap_since}"
        f"・きょう判定できる前提 {len(ready)}件"
        f"・枠の本 {'✗ 脚が残っている' if slot.get('fired') else '✓ 脚は全部 通っている'}")

    if why:
        out["ok"] = False
        out["blocked"] = ["fix"]
        out["lines"].append("  [!] **この周は `fix` では ship できません** —— " + "／".join(why))
        if slot.get("fired") and slot.get("topic"):
            out["lines"].append(
                f"      通る手: `python scripts/inspect_build.py {slot['topic']}` → "
                f"`upload_only.py {slot['topic']} --draft --replaces {slot.get('video_id', '')}`")
        if over and ready:
            out["lines"].append(f"      きょう判定できる前提: {', '.join(map(str, ready[:4]))}")
        out["lines"].append(
            "      **いま決めること**（作りはじめる前に）: "
            "`improve` / `upload` / `verdict` / `premise` / `means` のどれで出すか。"
            "**終わってから言い換えないこと** —— 止めた 56回のうち 12回が"
            "同じ文面を +6分 で通しています（`kinds_allowed` の註）")
    elif over:
        # **台帳が空の日でも、門は立ちます。** ここを「立ちません」と印字した版を
        # 2026-09-04 23:5x に出し、**その回の `--ship` が自分の印字どおりに撃って
        # 止められました**（この関数を足したのと同じ回）。免除は 09-04 19:xx に
        # **枠の本を名乗る `fix` だけ**へ絞られています（`run_marker.dry_ledger_gate`）。
        # **述語を写さずに、その純関数へ空の `--ship` を渡して訊くこと** ——
        # 頭の時点では本文がまだ無いので、空 ＝「名乗っていない場合」の答えが返ります。
        dg = _safe(lambda: rm.dry_ledger_gate("", ready, slot, over),
                   {"trip": False, "target": slot.get("topic") or ""})
        if dg.get("trip"):
            out["ok"] = False
            out["blocked"] = ["fix"]
            tgt = dg.get("target") or slot.get("topic") or ""
            # **その「枠の本」が、いまの門に落ちているなら、行き先はそこではありません**
            # （2026-09-05 05:xx・最適化の回。`daily_pick.standing_form_stale` の註）。
            # 前の版は、`path_form_hold` が形ごと止めている本を
            # **`fix` の唯一の行き先として名指し**していました。
            _sf = _safe(lambda: __import__(
                "src.daily_pick", fromlist=["x"]).standing_form_stale_now(), "")
            if _sf:
                out["blocked"] = ["fix", "improve"]
                out["lines"].append(
                    f"  [!] {_sf}\n"
                    "      **だから `fix` も `improve` も、差し替えるまで通りません**"
                    "（`run_marker` が止めます・`verdict`/`upload`/`premise`/`means` は通る）。"
                    "**いま決めること**: `python -m src.daily_pick --pick <門の指す形> <題材> "
                    "--expected <回> --why \"<数字で1行>\"`")
                return out
            out["lines"].append(
                f"  [!] **`fix` は、きょうの枠の本 `{tgt}` を名乗らないかぎり通りません**"
                f"（上限 連 {run_len}/{cap_run}・動いた ship から {since}/{cap_since}、"
                "きょう判定できる前提 0件 の日の免除は**規則3 に絞られています**"
                "・`run_marker.dry_ledger_gate`）。\n"
                f"      **いま決めること**（作りはじめる前に）: `--ship` に `{tgt}` を書いて"
                " `improve` か `fix` で出すか、`premise` / `verdict` / `upload` / `means` にするか。"
                "**計器だけを直す `fix` は、終わってから言い換えても通りません**")
        else:
            out["lines"].append(
                f"  [!] `fix` は上限（連 {run_len}/{cap_run}・{since}/{cap_since}）に着いています。"
                "**通るからといって、`fix` が近づける手だという意味ではありません** ——"
                "実測の歩留りは `fix` 0.6%（157回→1件）対 `verdict` 44.4%（9回→4件）")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="次の周を立ててよいか／どの役か")
    ap.add_argument("--record", metavar="ROLE[,ROLE]",
                    help="立てたことを記録する（役の名前。カンマ区切りで複数）")
    ap.add_argument("--live", type=int, default=None, metavar="N",
                    help="いま走っているサブの数（`list_sessions` から）。"
                         "**0 でも間隔は守る（途中なら起こしを置いて WAIT）**")
    ap.add_argument("--live-set", type=int, default=None, metavar="N",
                    help="その数を台帳（data/live_subs.json）へ置くだけ")
    args = ap.parse_args()

    # **親が読む写しを、読む直前に焼き直す**（`refresh_rendered()` に理由）。
    # 記録だけの呼び（`--record` / `--live-set`）でも焼きます ——
    # そちらは立てた**あと**に走るので、次の周の写しが新しくなります。
    for line in refresh_rendered():
        print(line)

    # **きょうの1本を置く手（＋先の日付の掃き）を、親の周から起こす**（2026-09-02 夜）。
    #     SessionStart フックは、このコンテナでは一度も起きていません（`ahead_sweep.kick()`
    #     の註）。親が毎周 撃つのはこの道具だけなので、ここから起こします。
    #     背景・数秒・親の画面には1行も出しません（白名簿）。
    #     **2026-09-06 02:1x JST に外した**（optimizer・Fable）。手法は 09/05 に `studio/` で
    #     ゼロから組み直し（`docs/METHOD.md`）、旧 `ahead_sweep.py` は「使わない・前提にしない」
    #     （§8）のはずが、**ここから毎周 起きていた**。実測: 09/06 00:01 JST に `place_today()` が
    #     08/16〜08/19 上げの旧作りの本 8本 に 06:00〜14:00 JST の publishAt を打った
    #     （`data/uploaded.jsonl` の diff・`139506ee`〜`724af5af`）。`studio.cli status` は新しい 60本
    #     しか見ておらず 0本 に見えた。02:1x に 2本 を private へ戻した（台帳 `unscheduled`）。
    #     **覆る条件**: 旧道具を使う判断が METHOD に書かれたとき（そのときは kick ではなく METHOD の手順で）。
    #     `.claude/settings.json` の SessionStart `ahead_sweep.sh` も同じ理由で外した。

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
        # **同じ呼びの役は同じ周**（`record_many` の註 —— 1行ずつ継がせると、
        #     1行目が前の片肺の周へ吸われ、周が1つずつ ずれ続けます）。
        for row in record_many(want):
            print(f"[next_round] 記録しました: {row['role']} at {row['at']}"
                  f"（周 {row['round']}）")
        return 0

    d = decide(live=args.live)
    print(f"[next_round] 間隔 {d['floor_min']:.0f}分（{d['source']}）")
    # **旧道具の読み出し（種別の下読み・枠の機会費用・立っている決め）は、ここから出さない**
    #     （2026-09-06 17:xx JST・optimizer・Fable）。09/04〜05 にここへ足した3つの塊は
    #     `src/run_marker`・`src/slot_cost`・`src/daily_pick` を読んで印字していた。手法は 09/05 に
    #     `studio/` でゼロから組み直し（`docs/METHOD.md` §8「使わないもの」）、旧道具は「使わない・
    #     前提にしない」のはずが、**親が毎周 撃つこの道具が、旧道具の判定を毎周 印字していた**。
    #     実測 09/06 17:02 JST の印字: 「**2026-09-06 の枠はもう決まっています**: ショート /
    #     s-teikibin-todoita-kakyu-ni-nai / 3gZ38lfsJpY」「2026-09-07 … PhQ2KvuQASQ」「2026-09-08 …
    #     vmAll8GDkU8」—— どれも 09/05 17:1x に private へ戻した旧作りの本で、いまの枠は
    #     `EkNqtkK49Bw`（`studio.cli status`）。「`fix` は `qyVdpAoT_40` を名乗らないかぎり通りません」も
    #     `run_marker` の門で、いまの回は `run_marker` を撃たない。**親は印字を写すだけ**なので、
    #     嘘の決めがそのままサブの本文の土台になる口だった。
    #     関数 `kinds_allowed` 自体は残す（消さない・オーナー 08/31）。呼ばないだけ。
    #     **覆る条件**: METHOD に旧道具を使う判断が書かれたとき（そのときも「読み出し」ではなく手順から）。
    if d.get("live") is None:
        # **WAIT を印字しません。** 2026-09-02 21:2x、親は 0体 と数えたうえで
        #     `--live` を付けずに撃ち、出た WAIT をそのまま「（0体・WAIT 74分）」と
        #     出しました（オーナー「てめえほんとバカだな」）。08-31 と同じ止まり方の
        #     2回目です。数が無い回に WAIT を見せる限り、親はそれを読みます ——
        #     だから見せません。**答えは COUNT（数えて撃ち直せ）の1つだけ。**
        #     GO にも倒しません（付け忘れた親が毎回 二重に立てる・`decide()` の註）。
        #     検査: tests/test_next_round_live.py「数が無い回は WAIT を印字しない」
        print("COUNT")
        print("  [!] **走っているサブの数が渡されていません。WAIT も GO も出しません。**")
        print("  `list_sessions limit=25 mine=true` で数えて、"
              "**`python scripts/next_round.py --live <その数>`** を撃ち直すこと")
        print("  （0体 なら「間隔が明けていれば GO・途中なら起こしを置いて WAIT」・"
              "1体 以上なら間隔。2026-08-31・09-02 に数を渡さずに2回 叱られています）")
        return 2
    print(f"  走っているサブ: **{d['live']}体**（{d['live_source']}）")
    log_wake(d)   # **GO も WAIT も1行 残す**（上の註 —— 立たなかった時間を読めるように）
    roles = d["roles"]
    if d["go"]:
        print("GO " + " ".join(roles))
        print(f"  理由: {d['why']}")
        # **記録と押しは、立てるより先**（2026-09-07 22:4x・optimizer・Opus が入れ替えた）。
        #     それまでは最後に「立てたら: --record」と印字しており、親は
        #     「立てる → 記録 → 押す」の順で回していた。**その順は2つ壊していた**:
        #     (1) サブの最初の fetch/merge が、親のこの周の押しに間に合わず
        #         `Already up to date.` と出る（実測 09/07 10:19 と 22:39 の2回）。
        #         サブは「追いついた」と読めないので、確かめの手を足しては外す回が続いた
        #         （01:3x に merge-base を足し、12:4x に撃って外した）。
        #     (2) **周が押されない窓が、サブを立てているあいだ丸ごと開く。**
        #         その窓で別の親が起きると rounds.jsonl は空のままなので、両方が GO を読む
        #         ——「なんでサブ増えてんの？」（08-25）の当のもの。
        #     先に記録して押せば、窓は「記録 → 押す」の数秒だけになり、
        #     サブの worktree は最初から周を含む（＝ 最初の merge が本当のことを言う）。
        #     覆る条件: 記録したのに立てられなかった回（429 など）が続いたら、
        #     失うのは1周ぶんなので、そのときは順を戻すのではなく **立て直す**こと。
        print(f"  **先に記録して押すこと（立てる前）**: "
              f"python scripts/next_round.py --record {','.join(roles)}"
              " → 周の台帳を commit して push")
        print("  （この順でないと、サブの最初の fetch がこの周の押しに間に合わず、"
              "立てているあいだ 周が押されない窓が開きます）")
        print(f"  **そのあと、この{len(roles)}つを立てること。** 1周は"
              f"{len(ROLES)}種類そろって1周です"
              "（片方だけで終わると、その周は片肺）")
        for role in roles:
            print(f"  本文: docs/spawn_prompt.rendered.md の `kind: {role}` を"
                  "**そのまま**渡すこと（親が中身を考えないこと）")
        print("  **isolation: \"worktree\" と run_in_background: true を"
              "必ず付けること**（衝突を避ける／親を塞がない）")
        # **役ごとに模型を選ぶ**（オーナー原文 09/03 07:3x「仕事ごとに Fable・Opus・
        # Sonnet・Haiku を選ぶ」「Fable のみは 100% 到達になって使えなくならないほうが
        # 良くない？」）。09/03 09:4x まではここが 1行 で、全役へ同じ模型を返していた。
        # 段と予備の線は `quota.ROLE_TIER` / `quota.FABLE_RESERVE_PCT`、
        # 選んだ理由は `data/model_choice.jsonl` に積む（`quota.record_model_choice`・
        # `docs/OWNER_INSTRUCTION_GATE.md` の 6）。
        import scripts.quota as _quota
        for role in roles:
            try:
                _m, _why = _quota.sub_model(role=role)
            except Exception as exc:                           # noqa: BLE001
                _m, _why = "fable", f"quota.sub_model が答えません（{str(exc)[:60]}）"
            try:
                _quota.record_model_choice(role, _m, _why)
            except Exception:                                  # noqa: BLE001
                pass
            print(f"  **model（`kind: {role}`）: \"{_m}\"**（{_why}。"
                  "上限は `quota.FABLE_CAP_PCT`・予備は `quota.FABLE_RESERVE_PCT`）")
        return 0
    print(f"WAIT {d['wait_min']:.0f}")
    print(f"  理由: {d['why']}")
    print(f"  いまの周は {'・'.join(roles)} がそろっています（片肺ではありません）")
    if d.get("live"):
        print(f"  **待つ理由は「二重に立てないため」です** —— いま {d['live']}体 が"
              "走っています。**間隔そのものではありません**")
        print("  **何もしないこと。** 次のトリガーか、走っているサブの完了が拾います")
        return 0
    # **0体 の WAIT ＝ 起こしを置く**（`decide()` の節 2026-09-03）。
    #     置かずに待つと 08-31 の形（191分 の空き）。置けば空きは間隔ぶんだけ。
    now = datetime.now(timezone.utc)
    wake_at = d["wake_at"]
    try:
        from scripts.quota import JST as _JST
    except Exception:                                          # noqa: BLE001
        _JST = timezone(timedelta(hours=9))
    hhmm = wake_at.astimezone(_JST).strftime("%H:%M")
    pending = wake_read(now)
    if pending is not None and abs((pending - wake_at).total_seconds()) <= 120:
        print(f"  起こしは **{pending.astimezone(_JST):%H:%M} JST** に置いてあります"
              "（`send_later` は撃たない。同じ周で親が何度 起きても 1回）")
    else:
        wake_write(wake_at, now=now)
        print(f"  **起こしを置くこと**（承認待ちにならない・即返り）:")
        print(f"    send_later  delay_minutes={d['wake_min']}  "
              f"name=\"親の周（起こし {hhmm}）\"  "
              "message=\"親の周です（起こし）。docs/trigger_body.rendered.md のとおりに。\"")
    print(f"  出す文字: **（0体・次 {hhmm}）**  ← 白名簿の 2（それ以外は出さない）")
    print("  **サブを立てないこと。** 立てると上限（今までの最高速度の二分の一）を越えます")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
