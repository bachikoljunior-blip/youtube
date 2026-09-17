from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _shared_root(root: Path) -> Path:
    """worktree で走っていても、**本体の checkout** を指す（`work/` を周で分けないため）。

    サブは `<本体>/.claude/worktrees/agent-xxxx` で走ります。`ROOT` をそのまま使うと、
    `work/` が **周ごとに別**になり、次の 3つ が起きます（2026-09-16 15:5x に数えた）:

      1. **焼いた物が、その周で上げられなければ捨てられます。**
         この回は日枠が尽きていて（戻るのは 16:00 JST）、焼いた 3本 を 1本も上げられません。
         次の周は、**同じ本を最初から焼き直します**（1本 6〜10分・Google TTS の代金つき）。
      2. **`seg-<sha>.wav` の憶えが効きません。** TTS は本文の sha で憶えますが、
         憶えている場所が周ごとに別なので、**1コマも当たりません** ——
         「1文だけ直して焼き直す」が、毎回 全コマの合成になります。
      3. **貯まります。** この回に数えたら worktree **42個・うち `work/` を持つ 12個・合計 11GB**。

    `.claude/worktrees/<名>` の手前が本体です。その形でなければ `root` をそのまま返します
    （検査・本体での実行・別の置き方で壊れない）。**環境変数 `STUDIO_WORK` があればそれが勝ちます。**

    **覆る条件**: (1) 1周に 2体 以上 立てる形へ戻したら、同じ本を同時に焼く道が開きます ——
    そのときは `work/<id>` に周の印を足すか、この共有をやめること
    （いまは **1周 1体**・オーナー 2026-09-14 20:4x）。
    (2) 古い周の mp4 を「新しい」と読んだ回が出たら、それは共有のせいではなく
    `script.build_sig` の穴です（`cmd_schedule` は `built_sig` と突き合わせてから上げます）——
    直すのは指紋のほう。
    """
    parts = root.parts
    if ".claude" in parts and "worktrees" in parts:
        i = parts.index(".claude")
        if parts[i + 1:i + 2] == ("worktrees",):
            return Path(*parts[:i])
    return root


#: 生成物（gitignore）。**周をまたいで共有します**（`_shared_root` の註）。
WORK = Path(os.environ.get("STUDIO_WORK") or (_shared_root(ROOT) / "work"))

#: **本の中で名乗る名**（2026-09-18 00:3x・optimizer・Fable 5.1・ultracode）。**1か所**。
#: `cli.RENAME_TARGET`（チャンネルの題を打ち直す先）・`slides.brand_strip`（毎コマ 左上の札）・
#: `script.default_cta`（出口の名乗り）の 3つ が **ここ**を読みます。
#: **なぜ本の中に置くか（数）**: 登録/1,000再生 は **0.35**（corpus 中央 5.29・下から 3/215）で、
#: 縛っているのは再生ではなく登録（`trend.rev_deadline`・`peers.conversion`）。09/17 12:5x の回は
#: 「名前 ＋ 制度名」の升（登録/日 78.8 対 うち 1.6）へ題を変える手を `catchup` に置きましたが、
#: **`channels.update` は題を黙って無視し（09/17 16:1x・`channel_rename_refused`）、手はオーナーの Studio に移りました。**
#: 題は視聴者の 100% に見えますが、**本の中の名乗りも 100% に見えます** —— そして 253本 の公開ずみに
#: 名乗りは 1つも在りませんでした（画面にも声にも。`sheet.png` で確かめた ＝ 進み具合の線・札・show・板・字幕だけ）。
#: 登録は「誰に」登録するかで、いまの本は「誰」を 1度も出していません。**題が変わるのを待たずに、本の側で名乗る。**
#: **覆る条件**: (1) オーナーが別の名を出したら、その名が正本 ＝ ここを書き換えれば 3つ とも動く。
#: (2) 名乗りを入れた本 5本 の登録率（`trend.sub_rate_cohorts`）が、入れていない 09/18 の 5本 を下回ったら、
#:     札を消す側ではなく **置き場**（左上 → 出口だけ）を疑うこと。(3) 題が Studio で変わったら
#:     `config/channel.yaml` の `name` をここと同じ字にする（`cli.rename_pending` が見る）。
BRAND_NAME = "カワウソの年金計算室"

#: `work/<id>` を何日 残すか。**共有にした以上、掃く物が要ります**（2026-09-16 16:5x に足した）。
#: 共有へ直した直後に数えたら **7本 で 992MB**（1本 約140MB ＝ mp4・wav・150枚の png）で、
#: **空きは 9.1GB** でした ＝ **1週間 で埋まります。**
#: 3日 にしたのは、いちばん先の枠が **公開の 2〜3日 前**に焼かれるから
#: （この回の実物: 09/16 に焼いた `2026-09-19-...`）。**公開ずみの本の焼きは、二度と要りません。**
#: **覆る条件**: (1) 焼き直しを求められた本が「掃かれていて無い」回が出たら、日数を伸ばすこと
#: （`build_sig` が食い違えば焼き直すだけなので、**落ちるのは時間だけで、本は落ちません**）。
#: (2) 先の枠へ 4日 以上 前から置く形にしたら、この日数もそこへ合わせること。
WORK_KEEP_DAYS = 3


def prune_work(keep_days: int | None = None, now: float | None = None) -> list[str]:
    """**古い `work/<id>` を掃く。**掃いた id を返す（`cmd_build` が毎回 呼ぶ ＝ 誰も憶えなくてよい）。

    見るのは**その中の mp4 の刻**（無ければディレクトリの刻）。**触られた物は残ります。**
    """
    import shutil
    import time
    keep = WORK_KEEP_DAYS if keep_days is None else keep_days
    now = time.time() if now is None else now
    if not WORK.is_dir():
        return []
    gone = []
    for d in sorted(WORK.iterdir()):
        if not d.is_dir():
            continue
        mp4 = d / f"{d.name}.mp4"
        try:
            age = now - (mp4 if mp4.exists() else d).stat().st_mtime
        except OSError:
            continue
        if age > keep * 86400:
            try:
                shutil.rmtree(d)
                gone.append(d.name)
            except OSError:
                pass
    return gone
DATA = ROOT / "data" / "studio"  # 台帳（commit する）
LEDGER = DATA / "ledger.jsonl"
#: **本物の台帳の道を、読み込みのときに凍らせる**（`_ledger_blocked` の註）。
#: `LEDGER` は検査が tmp へ差し替えるので、比べる相手に使えません。
_REAL_LEDGER = LEDGER
JST = dt.timezone(dt.timedelta(hours=9))


def now_jst() -> dt.datetime:
    return dt.datetime.now(JST)


def today_jst() -> str:
    return now_jst().strftime("%Y-%m-%d")


def env(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        raise SystemExit(f"環境変数 {name} が無い")
    return v


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def probe_duration(path: Path) -> float:
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "csv=p=0", str(path)]).stdout.strip()
    return float(out)


def _ledger_blocked() -> bool:
    """**検査を撃つだけで本物の台帳に行が入る口を、書く側で塞ぐ**（2026-09-14 19:5x・optimizer・Opus）。

    **この回に踏んだ**: 19:1x に足した `cli.main()` の門が `ledger("token_rejected", …)` を書くようになり、
    `tests/test_studio_auth_line.py` を撃っただけで **本物の `data/studio/ledger.jsonl` に 6行**
    （`cmd: analytics` / `reporting`）入りました。**その 2件 は `cli.ledger` を差し替えていなかった**だけで、
    差し替え忘れは**書き口が増えるたびに起きます** —— §8 の 4つ目（`run_marker._marks_blocked()`・
    `next_round.log_wake()`）と**同じ形**で、あちらの決めは
    「**守りは『呼ぶ側』ではなく『書く側』に置くこと**」でした。`studio` の側にはその門がありませんでした
    （`conftest.py` は `scripts/` の台帳しか tmp へ向けていない ＝ 撃って確かめた）。

    **門**: `PYTEST_CURRENT_TEST` が立っていて、**かつ `LEDGER` が本物を指している**ときだけ書かない。
    **`LEDGER` を tmp へ差し替えた検査は書けます**（`monkeypatch.setattr(common, "LEDGER", tmp)` ＝
    台帳の中身を読む検査はそのまま通る）。

    **覆る条件**: (1) `conftest.py` が `studio` の `LEDGER` も毎回 tmp へ向けるようになったら、この門は外してよい
    （見張りがその日に落ちて教える）。(2) 本物の台帳へ**わざと**書く検査が要る回が出たら、`LEDGER` を
    差し替えるのではなく、その検査をここに名指しで書くこと（黙って門を外さない）。
    見張りは `tests/test_studio_no_real_ledger.py`（**陽性対照つき** ＝ 門を外すと本物の md5 が動く）。
    derivation は `docs/JOURNAL.md` 2026-09-14 19:2x。
    """
    return bool(os.environ.get("PYTEST_CURRENT_TEST")) and LEDGER == _REAL_LEDGER


def ledger(event: str, vid: str, **detail) -> None:
    """何をしたかを1行 足す。「出した」の定義はこの台帳の event 名で決まる（docs/METHOD.md §記録）。"""
    if _ledger_blocked():   # 検査から本物の台帳へは書かない（`_ledger_blocked` の註・§8）
        return
    DATA.mkdir(parents=True, exist_ok=True)
    # 予約は "at" を「公開の時刻」の意味で渡していたので、**detail が「いつやったか」を上書きしていた
    # （09/07 12:3x・optimizer が実測。3行とも公開時刻・09/06 の2行は元と差し替えが同じ刻で見分けられない）。
    # 予約された "at"/"id"/"event" は行の骨なので、detail に同じ名前が来ても骨を勝たせる。
    row = {**detail, "at": now_jst().isoformat(timespec="seconds"), "id": vid, "event": event}
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def ledger_rows() -> list[dict]:
    if not LEDGER.exists():
        return []
    return [json.loads(l) for l in LEDGER.read_text(encoding="utf-8").splitlines() if l.strip()]


def workdir(vid: str) -> Path:
    d = WORK / vid
    d.mkdir(parents=True, exist_ok=True)
    return d
