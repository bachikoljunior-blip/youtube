"""`python -m studio.cli trend` が**毎周 印字する字数**の伸びを数える（API 0単位・git だけ）。

    python scripts/output_growth.py                    # いちばん新しい窓
    python scripts/output_growth.py --lines            # いまの出力を、長い行から並べる（吸った所を名指しする）
    python scripts/output_growth.py --laps 6 --points 3

**なぜ道具にしたか**（2026-09-10 22:5x JST・optimizer・Opus）:
`scripts/method_growth.py` は **`docs/METHOD.md` の「毎回 読む」側**に門を置いています
（行 +20行/周・本文の字 +300字/周）。**毎周 読む物は、それだけではありません** ——
`trend` の**出力**は、`optimizer` が毎周 頭から読むもので、**そこには門が 1つもありませんでした。**

**この回に撃った実測**（**同じ台帳**に、その刻の `studio/` の**コードだけ**を当てて数えた
＝ 台帳が伸びたぶんは入っていません）:

    09/10 10:17 → 14:27 JST（6周）   3,310 → 4,996字   ＝ 1周 **+281字**
    09/10 14:27 → 18:35 JST（6周）   4,996 → 6,893字   ＝ 1周 **+316字**
    09/10 18:35 → 22:32 JST（6周）   6,893 → 8,088字   ＝ 1周 **+199字**

**この 4点 を撃ったときの台帳の刻: 2026-09-10 22:55 JST**（2026-09-10 23:2x に足した）。
**点を書くときは、台帳の刻も一緒に書くこと** —— 台帳は毎周 伸びるので、刻の無い点は
**次の周には 1字も合いません**（実測 23:1x: 3,836 / 5,178 / 7,256 / 8,107 ＝ コードは 1行も
触っていない）。刻を渡せば何周 経っても再現します（`output_at(sha, ledger_cut=…)`）。

＝ **18周（約12時間）で 2.44倍**。**同じ 3窓 の METHOD の本文は -388 / +316 / +32字/周**
（`method_growth.py`）＝ **いちばん新しい窓では、METHOD の本文（+32）より 6倍 速く伸びています。**
12:1x が §6 の表に当てた形（**決めは残す・derivation は外へ**）は、
**`print` の中の文には当たっていません**でした。

**吸った所**（この回の `--lines`。**1行が段落になっています**）:

    `shakes_line`          **1,587字**（10:17 には 0字 ＝ 18周 で足された）
    `channel_growth` の行   **1,035字**（同上）
    `gate_span` の行          870字
    ＝ この 3行 で **3,492字 ＝ 出力の 43%**

**字は `len()` で数えること。`wc -m` を使わないこと** —— この環境の locale は `C` なので
`wc -m` は `wc -c`（バイト）と同じ値を返し、**日本語の出力を 1.97倍 に見せます**
（この回に踏んだ: 8,088字 を 15,912 と読み、門を「引かれた」側に誤って置きかけた）。

**門**（METHOD の字の門と**同じ数**を使います —— 読むのは同じ 1体・同じ枠なので、
物差しを 2つ 持たないため。覆る条件 (2) で選び直せます）:

    1周 **+300字** を越えた窓が **2つ 続いたら**、`--lines` で吸った行を名指しして、
    §5／§6 の形を **`print` の文にも**当てること
    ＝ **印字は「何が起きたか」と「その数」まで。derivation と覆る条件は 註 と JOURNAL に置き、
      印字からは日付で指す。**

**数え方**（変えるときは点を 1点目から取り直すこと）:

    測る物   `python -m studio.cli trend` の標準出力の字数（`wc -m` と同じ）
    コード   その刻**より前**の最後の `studio/` の commit（`git archive`）
    台帳     **いまの `data/studio/ledger.jsonl` を、どの点にも同じだけ当てる**
             —— 台帳の伸びを混ぜないため。**書き込みは届きません**（写しを渡している）
    窓の端   `data/rounds.jsonl` の周の刻（`method_growth.rounds()` と同じ物を使う）

**`status` は測れません** —— `cmd_status` は `channels.list`/`videos.list` を撃つので、
古いコードで走らせると **Data API を 1点につき数単位** 使います。
`trend` は API 0単位（台帳だけ）なので、ここは `trend` だけを測ります。

**覆る条件**:
(1) 古いコードが**いまの台帳で落ちる**ようになったら（欄が増えた・形が変わった）、
    その点は例外で止まります。**0字 として並べないこと** —— 落ちた点は窓から外し、`--after` で頭をずらす。
(2) 門 +300字 は METHOD の字の門の借り物です。**`trend` の出力が 3窓 続けて +300字 を下回っても
    出力が 20,000字 を越え続けるなら**、伸びではなく**総量**が問題 ＝ 門を「総量」に置き換えること。
(3) `status` にも同じ形の伸びが在るのに、この道具はそれを 1字も見ていません。
    `cmd_status` の印字が API を撃たない形（台帳から）に分かれたら、そちらも測ること。
    **2026-09-10 23:2x に、そこの重なりを 1つ 閉じました** —— `cmd_status` は
    `trend.channel_line`（1,035字）を `trend` と**同じ周に、1字も違わずに**印字していました
    （いまは `trend.channel_line_short`・228字）。**この道具はその 807字 を 1字も見ていません。**
(4) 台帳に `at` の無い行が出たら、`_copy_ledger_until` の「落とさずに残す」を決め直すこと
    （いまは 2,693/2,693 行に `at` が在る）。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import method_growth as mg  # noqa: E402  （周の刻は同じ物を使う）

JST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
CHAR_GATE = 300  # 1周ぶんの字（METHOD の字の門と同じ数・註の覆る条件 (2)）


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def sha_at(when: datetime) -> str | None:
    """その刻**より前**の最後の `studio/` の commit（`method_growth.blob_at` と同じ挟み方）。"""
    return _git("log", "-1", f"--before={when.isoformat()}", "--format=%H", "--", "studio/").strip() or None


def _copy_ledger_until(src: Path, dst: Path, cut: datetime) -> None:
    """台帳を `cut` **以前**の行だけ写す（`at` は全行に在る ＝ 実測 2,693/2,693 行）。

    `at` を読めない行は**落とさずに残します** —— 落とすと「切った」ではなく「間引いた」になり、
    再現の意味が変わります（そういう行が出たら、註の覆る条件 (4) の側）。
    """
    keep = []
    for line in src.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            at = datetime.fromisoformat(json.loads(line)["at"])
        except Exception:
            keep.append(line)
            continue
        if at <= cut:
            keep.append(line)
    dst.write_text("\n".join(keep) + "\n", encoding="utf-8")


_SITECUSTOMIZE = """import datetime as _dt, os
_v = os.environ.get("STUDIO_FAKE_NOW")
if _v:
    _fixed = _dt.datetime.fromisoformat(_v)

    class _D(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return _fixed.astimezone(tz) if tz is not None else _fixed.replace(tzinfo=None)

        @classmethod
        def utcnow(cls):
            return _fixed.astimezone(_dt.timezone.utc).replace(tzinfo=None)

        @classmethod
        def today(cls):
            return _fixed.replace(tzinfo=None)

    _dt.datetime = _D
"""


def output_at(sha: str, ledger_cut: datetime | None = None,
               now: datetime | None = None) -> str:
    """その commit の `studio/` を、**いまの台帳の写し**に当てて `trend` を走らせ、出力を返す。

    台帳は写しなので、古いコードが書いても本物には届きません（`trend` は読むだけですが、
    「届かないこと」を仕組みで担保しておく ＝ 陽性対照が要らない側）。

    **`ledger_cut`**（2026-09-10 23:2x・optimizer・Opus）: 台帳を**その刻までの行に切って**渡す。
    既定（`None`）はいまの台帳ぜんぶ ＝ 道具の測り方は変わりません
    （どの点にも同じ台帳を当てる ＝ 台帳の伸びを混ぜない）。

    **なぜ足したか**: 22:5x が書いた 3点（3,310 / 4,996 / 6,893 / 8,088字）は
    **その回の台帳**の上の数で、台帳は毎周 伸びます。＝ **次の周には、コードを 1行も
    触っていなくても 1字も合いません**（実測: 23:1x の周で 3,836 / 5,178 / 7,256 / 8,107）。
    検査 `test_この回が撃った_3点_と_1字も違わないこと` は、**その次の周に必ず赤くなる形**でした。
    **点を書くときは、その台帳の刻も一緒に書くこと** —— 刻が在れば、あとから何周 経っても再現できます。
    （§6 の「赤が既定になると、次の回は自分が壊したのかを見分けられません」の族）

    **【2026-09-11 02:3x・optimizer・Opus】台帳を切るだけでは再現しませんでした。**
    23:2x の「刻が在れば何周 経っても再現できます」は**偽**で、**3周 もちませんでした** ——
    `trend` は齢と「引いたのは N時間 前」を**実時計**（`common.now_jst`）から出すので、
    台帳を切っても**走らせた時刻**で字数が動きます。
    実測: 同じ sha・同じ台帳の刻で **8,088 → 8,089字**。増えた 1字 は
    `analytics_line` の **「引いたのは 9時間 前」→「10時間 前」**でした
    （**桁が変わる所を跨いだ瞬間に赤くなる** ＝ 23:2x が閉じたつもりの穴と同じ形）。
    **いまは `ledger_cut` を渡すと `now` も同じ刻に凍らせます**（`_SITECUSTOMIZE` を
    写しの側にだけ置き、`PYTHONPATH` で当てる ＝ `studio/` は 1行も触らない）。
    ＝ **その刻に印字されたはずの物**を再現します。**古いコードにも効きます**（起動時に当てるので）。
    **`now`** は既定で `ledger_cut` と同じ刻です。**別に渡せるのは陽性対照のため**
    （台帳を 1行も動かさずに時計だけ動かして、凍らせが本当に届いているかを見る）。
    **覆る条件**: (5) 実時計を `datetime.datetime.now` 以外（`time.time`・OS の日付）から
    取る印字が出たら、この凍らせ方では止まりません —— そのときは差だけを見て、絶対の字数の点は捨てること。
    """
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        tar = subprocess.run(["git", "archive", sha, "studio"], cwd=ROOT, capture_output=True)
        if tar.returncode != 0:
            raise RuntimeError(
                f"{sha[:8]} の studio/ を取り出せません（註の覆る条件 (1)）:\n{tar.stderr.decode()[-400:]}")
        subprocess.run(["tar", "-x", "-C", str(d)], input=tar.stdout, check=True)
        (d / "data" / "studio").mkdir(parents=True)
        for f in (ROOT / "data").iterdir():
            if f.name != "studio":
                os.symlink(f, d / "data" / f.name)
        for f in (ROOT / "data" / "studio").iterdir():
            if f.name == "ledger.jsonl":
                if ledger_cut is None:
                    shutil.copy2(f, d / "data" / "studio" / f.name)
                else:
                    _copy_ledger_until(f, d / "data" / "studio" / f.name, ledger_cut)
            else:
                os.symlink(f, d / "data" / "studio" / f.name)
        envv = dict(os.environ)
        clock = now if now is not None else ledger_cut
        if clock is not None:
            # **台帳を切るだけでは再現しません**（註の 02:3x）—— 実時計も同じ刻に凍らせる。
            # `now` を別に渡せるのは**陽性対照のため**（台帳を動かさずに時計だけ動かす）。
            (d / "sitecustomize.py").write_text(_SITECUSTOMIZE, encoding="utf-8")
            envv["PYTHONPATH"] = os.pathsep.join([str(d), envv.get("PYTHONPATH", "")]).rstrip(os.pathsep)
            envv["STUDIO_FAKE_NOW"] = clock.isoformat()
        r = subprocess.run([sys.executable, "-m", "studio.cli", "trend"],
                           cwd=d, capture_output=True, text=True, env=envv)
        if r.returncode != 0:
            raise RuntimeError(
                f"{sha[:8]} の studio/ が いまの台帳で落ちました（註の覆る条件 (1)）:\n{r.stderr[-400:]}")
        return r.stdout


def output_now() -> str:
    """**いま作業ツリーに在る** `studio/` を、いまの台帳に当てた `trend` の出力。

    **なぜ blob ではないか**（2026-09-11 05:2x JST・optimizer・Opus。`method_growth.worktree_text`
    と同じ族）: `report()` の「いま **N字**」は `points()` の最後の窓の `b`
    （＝ **周の刻より前の最後の commit の `studio/`**）から取っていました。
    **窓の差はそれで正しい**（コードだけを当てて数える ＝ この道具の定義そのもの）——
    **ですが「いま」は窓の端ではなく、この回が触ったコードが印字する字です。**
    ＝ `trend.py` の印字を足した／削った回は、**自分がやったことが「いま」に出ません**
    （足した回ほど小さく、削った回ほど大きく出る ＝ 門を引いた回が自分の直しを確かめられない）。

    **凍らせません**（`ledger_cut` も `STUDIO_FAKE_NOW` も渡さない）——「いま」は
    **いまの台帳・いまの時計**の数だからです。窓の点とは 1字 単位では比べられません
    （実時計で「N時間 前」の桁が動く・`output_at` の註 02:3x）。**比べるのは窓の差のほう。**

    **覆る条件**: (1) 作業ツリーの `studio/` が落ちる回が出たら、そのまま止まること
    （黙って blob の数を配らない ＝ `output_at` の覆る条件 (1) と同じ扱い）。
    (2) 「いま」と窓の端の差を、**コードの差として読んだ回が 1度でも出たら**、
    印字を 2行 に分ける（いまは台帳と時計も一緒に動いているので、その引き算は意味を持ちません）。
    """
    r = subprocess.run([sys.executable, "-m", "studio.cli", "trend"],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("いまの `studio/` が落ちました（註の覆る条件 (1)）:\n" + r.stderr[-400:])
    return r.stdout


def points(laps: int = 6, n: int = 3, after: datetime | None = None) -> list[dict]:
    rs = [r for r in mg.rounds() if after is None or r >= after]
    edges = rs[len(rs) - 1 - laps * n:: laps] if len(rs) > laps * n else rs[::laps]
    out: list[dict] = []
    cache: dict[str, int] = {}
    for head, tail in zip(edges, edges[1:]):
        a, b = sha_at(head), sha_at(tail)
        if not a or not b:
            continue
        for s in (a, b):
            if s not in cache:
                cache[s] = len(output_at(s))
        out.append({"from": head, "to": tail, "laps": laps,
                    "a": cache[a], "b": cache[b], "d": cache[b] - cache[a],
                    "per_lap": (cache[b] - cache[a]) / laps})
    return out


def verdict(ps: list[dict]) -> list[str]:
    """門を引くのは道具。**次の回は覚えていなくてよい。**"""
    if not ps:
        return ["点が 1つも取れません（`data/rounds.jsonl` が窓ぶん無い ＝ まだ測れていない）"]
    tail2 = ps[-2:]
    over2 = [p for p in tail2 if p["per_lap"] > CHAR_GATE]
    if len(tail2) == 2 and len(over2) == 2:
        return [f"字の門 1周 +{CHAR_GATE}字: **引かれました** —— 直近 2窓 とも越えています"
                f"（{tail2[0]['per_lap']:+.0f} / {tail2[1]['per_lap']:+.0f}）。"
                "**`--lines` で吸った行を名指しし、印字から derivation を外すこと**"
                "（決めと数は残す・覆る条件は 註 と JOURNAL へ）"]
    return [f"字の門 1周 +{CHAR_GATE}字: 引かれません（直近 2窓 で越えたのは {len(over2)} つ ＝ 2つ 続いていない）"]


def line_sizes(text: str, top: int = 8) -> list[tuple[int, str]]:
    """いまの出力を、長い行から並べる。**吸った所を名指しするための口。**"""
    return sorted(((len(l), l[:38]) for l in text.split("\n") if l.strip()), reverse=True)[:top]


def report(laps: int = 6, n: int = 3, after: datetime | None = None, lines: bool = False) -> str:
    ps = points(laps, n, after)
    out = [f"`studio.cli trend` が毎周 印字する字数の伸び —— 窓は {laps}周・"
           "**同じ台帳にコードだけを当てて数えます**（台帳の伸びは入りません）"]
    for p in ps:
        out.append(f"  {p['from'].astimezone(JST):%m/%d %H:%M} → {p['to'].astimezone(JST):%m/%d %H:%M} JST"
                   f"   {p['a']:,} → {p['b']:,}字（{p['d']:+,}）  ＝ 1周 **{p['per_lap']:+.0f}字**")
    if ps:
        # **窓の端の blob ではなく、いま作業ツリーに在る `studio/`**（`output_now` の註）。
        out.append(f"  いま **{len(output_now()):,}字**（`status` は API を撃つので測れません・註。"
                   "**この行だけは作業ツリー・凍らせていない** ＝ 窓の点と 1字 単位で比べないこと）")
    out += ["  " + v for v in verdict(ps)]
    if lines and ps:
        out.append("  長い行から（吸った所の名指し）:")
        for n_, head in line_sizes(output_at(sha_at(ps[-1]["to"]))):
            out.append(f"    {n_:>6,}字  {head}…")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--laps", type=int, default=6, help="1つの窓の周の数（既定 6）")
    ap.add_argument("--points", type=int, default=3, help="並べる窓の数（既定 3）")
    ap.add_argument("--after", default=None, help='窓の頭をこの JST の刻より後に固定（例 "2026-09-10 22:32"）')
    ap.add_argument("--lines", action="store_true", help="いまの出力を長い行から並べる")
    a = ap.parse_args()
    after = datetime.strptime(a.after, "%Y-%m-%d %H:%M").replace(tzinfo=JST) if a.after else None
    print(report(a.laps, a.points, after, a.lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
