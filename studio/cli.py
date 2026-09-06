"""1日1本の運転。手順の正本は docs/METHOD.md。

    python -m studio.cli status                 # きょうの枠・次の枠・最近の本の再生（API 数単位）
    python -m studio.cli lint <id>              # 台本の形
    python -m studio.cli build <id>             # 声 → 絵 → mp4 → sheet.png（目で見る）
    python -m studio.cli hear <id> [--medium]   # 完成音声を聞き取り、予定の読みと照合
    python -m studio.cli read <id>              # 冷読（Haiku）: 1文で言い返せるか
    python -m studio.cli critique <id>          # 分かりやすさの批判（Sonnet）
    python -m studio.cli order-image <id>       # 背景画像を注文（外の ChatGPT セッションが焼く）
    python -m studio.cli schedule <id> --at 10:00 [--replace <videoId>]   # きょうの枠へ予約（当日だけ）
    python -m studio.cli measure                # 公開ずみの本の再生・高評価を台帳へ
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from . import critic, hear, render, script, yt
from .common import JST, ROOT, ledger, ledger_rows, now_jst, today_jst, workdir

IMAGES = ROOT / "assets" / "images"
ORDERS = ROOT / "data" / "image_orders"
MAX_SECONDS = 95.0   # Shorts は 3分 まで。分かる説明に要る長さを優先し、実測で締める（docs/METHOD.md）


def image_for(vid: str) -> Path | None:
    for ext in ("jpg", "png"):
        p = IMAGES / f"{vid}-bg.{ext}"
        if p.exists():
            return p
    return None


def cmd_status(a):
    ch = yt.channel()
    vids = yt.recent_videos(60)
    print(f"チャンネル: 登録 {ch['subscriberCount']}・総再生 {ch['viewCount']}・本数 {ch['videoCount']}")
    print(f"いま {now_jst():%m/%d %H:%M} JST")
    print("きょうの枠:")
    for v in yt.today_lineup(vids):
        print(f"  {yt.when(v):%H:%M} {v['privacy']:8s} {v['id']} {v['views']:5d}回 {v['title'][:40]}")
    print("予約（あす以降）:")
    for v in yt.scheduled_all():
        if yt.when(v).date() > now_jst().date():
            print(f"  {yt.when(v):%m/%d %H:%M} {v['id']} {v['title'][:40]}")
    print("直近 公開 10本:")
    pub = [v for v in vids if v["privacy"] == "public"][:10]
    for v in pub:
        age = (now_jst() - yt.when(v)).total_seconds() / 3600
        print(f"  {yt.when(v):%m/%d %H:%M} {v['id']} {v['views']:5d}回 いいね{v['likes']:3d} 齢{age:5.0f}h {v['title'][:36]}")
    print("台帳 直近 5行:")
    for r in ledger_rows()[-5:]:
        print("  " + json.dumps(r, ensure_ascii=False)[:160])


def cmd_lint(a):
    s = script.load(a.id)
    ps = s.problems()
    print(f"{s.id}: {len(s.segments)}コマ・{s.total_chars()}字")
    for p in ps:
        print("  [!]", p)
    for w in s.warnings():
        print("  [?]", w)
    return 1 if ps else 0


def cmd_build(a):
    s = script.load(a.id)
    ps = s.problems()
    if ps:
        print("台本の形が通らない:", *ps, sep="\n  ")
        return 1
    for w in s.warnings():
        print("  [?]", w)
    img = image_for(a.id)
    r = render.build(s, img)
    print(f"mp4: {r['mp4']}  {r['total']:.1f}秒  背景: {img.name if img else '無し（単色）'}")
    print("コマの秒数:", " ".join(f"{d:.1f}" for d in r["durations"]))
    print(f"目で見る: {r['sheet']}")
    ok = r["total"] <= MAX_SECONDS
    if not ok:
        print(f"  [!] {r['total']:.1f}秒 > {MAX_SECONDS}秒。say を削ること")
    ledger("built", a.id, seconds=round(r["total"], 1), image=bool(img), chars=s.total_chars(),
           scenes=[round(d, 1) for d in r["durations"]])   # 同じ本文でも焼くたびに ±3% 揺れる（09/06 22:1x 実測）。コマ単位で比べるため
    return 0 if ok else 1


def cmd_hear(a):
    s = script.load(a.id)
    d = workdir(a.id)
    from .tts import synth_script
    wavs = [w for w, _ in synth_script(s, d)]
    rows = hear.check(s, wavs, "medium" if a.medium else "small")
    bad = [r for r in rows if r["diffs"]]
    for r in rows:
        mark = "OK " if not r["diffs"] else "!! "
        print(f"{mark}コマ{r['i']} ({r['how']}): {r['heard']}")
        if r["diffs"]:
            print(f"      台本: {r['say']}")
            print(f"      予定: {r['exp']}")
            print(f"      音  : {r['got']}")
            for e, g in r["diffs"]:
                print(f"      予定「{e}」 聞こえた「{g}」")
    print(f"一致 {len(rows) - len(bad)}/{len(rows)}")
    if bad:
        print("差の読み方: TTS の誤読なら yomi か言い換え（yomi は効かない語がある → 直したら hear をやり直す）。"
              "whisper の聞き違い（ねんきん→めんきん・4がつ→4かつ 型）なら通してよい。決めるのは Fable。")
    ledger("heard", a.id, mismatched=len(bad), model="medium" if a.medium else "small", mode="kana",
           diffs=[{"i": r["i"], "d": r["diffs"]} for r in bad],
           escalated=[r["i"] for r in rows if "→" in r["how"]],   # small で差が出て medium が予定どおりに聞いたコマ
           how=hear.escalations(rows))   # どの段で通ったか（medium／medium+prompt）。§7 の「prompt の段が採られたか」を台帳で数えるため
    return 1 if bad else 0


def cmd_read(a):
    s = script.load(a.id)
    r = critic.cold_read(s)
    print("正解 :", s.takeaway)
    print("言い返し:", r.get("takeaway"))
    for u in r.get("unclear") or []:
        print("  分からない:", u)
    ledger("cold_read", a.id, takeaway=r.get("takeaway"), unclear=r.get("unclear"))
    return 0


def cmd_critique(a):
    s = script.load(a.id)
    c = critic.critique(s)
    print("理解度:", c.get("understand"), "/5 ", "言い返し:", c.get("takeaway"))
    for it in c.get("items") or []:
        print(f"  [{it.get('severity')}] {it.get('where')}: {it.get('why')}\n        → {it.get('fix')}")
    done = critic.loop_done(c)
    print("輪:", "閉じてよい（1番目が言いがかり）" if done else "まだ（1番目が real）")
    ledger("critique", a.id, understand=c.get("understand"), n_real=sum(1 for i in c.get("items") or [] if i.get("severity") == "real"), done=done)
    return 0 if done else 1


def cmd_order_image(a):
    s = script.load(a.id)
    ORDERS.mkdir(parents=True, exist_ok=True)
    oid = f"{a.id}-bg"
    p = ORDERS / f"{oid}.json"
    if p.exists():
        print("注文ずみ:", p, json.loads(p.read_text(encoding="utf-8")).get("status"))
        return 0
    order = {"id": oid, "asked_at": now_jst().isoformat(timespec="seconds"),
             "for": f"{s.date} の本（{s.id}）の背景",
             "prompt": s.image_prompt or "落ち着いた紺色の背景に、机の上の書類と電卓。写実的。文字は入れない。",
             "avoid": "文字・ロゴ・実在の人物・透かし", "size": "1080x1920", "format": "jpg",
             "out": f"assets/images/{oid}.jpg", "status": "pending"}
    p.write_text(json.dumps(order, ensure_ascii=False, indent=1), encoding="utf-8")
    print("注文を置いた:", p, "（外の毎時セッションが焼く。届いたら build し直す）")
    ledger("image_ordered", a.id, order=oid)
    return 0


def cmd_schedule(a):
    s = script.load(a.id)
    mp4 = workdir(a.id) / f"{a.id}.mp4"
    if not mp4.exists():
        print("mp4 が無い。先に build")
        return 1
    hh, mm = map(int, a.at.split(":"))
    at = now_jst().replace(hour=hh, minute=mm, second=0, microsecond=0)
    if at.date() != now_jst().date():
        print("当日以外には予約しない")
        return 1
    if at <= now_jst() + dt.timedelta(minutes=5):
        print(f"{a.at} はもう過ぎている（いま {now_jst():%H:%M}）。--at を後ろへ")
        return 1
    lineup = yt.today_lineup()
    others = [v for v in lineup if v["id"] != a.replace]
    if others and not a.force:
        print("きょうの枠にはもう本がある（1日1本）。差し替えなら --replace <videoId>:")
        for v in others:
            print(f"  {yt.when(v):%H:%M} {v['privacy']} {v['id']} {v['title'][:40]}")
        return 1
    if a.dry_run:
        print(f"[dry-run] 上げる: {mp4.name} → 公開 {at:%m/%d %H:%M} JST・差し替え {a.replace or '無し'}・題「{s.title}」")
        return 0
    vid = yt.upload(mp4, s.title, s.description, s.tags, at)
    print("上げた:", vid, f"公開 {at:%m/%d %H:%M} JST")
    first = workdir(a.id) / "slide-01.png"
    try:
        yt.set_thumbnail(vid, first)
    except Exception as e:  # noqa: BLE001
        print("サムネは付かなかった:", str(e)[:120])
    if a.replace:
        yt.make_private(a.replace)
        print("差し替え: 前の", a.replace, "を private に戻した（消していない）")
    ledger("scheduled", a.id, video_id=vid, at=at.isoformat(timespec="minutes"), replaced=a.replace or None,
           title=s.title)
    return 0


def cmd_measure(a):
    vids = yt.recent_videos(40)
    for v in vids:
        if v["privacy"] == "public":
            age = (now_jst() - yt.when(v)).total_seconds() / 3600
            ledger("measured", v["id"], views=v["views"], likes=v["likes"], age_h=round(age, 1), title=v["title"][:40])
    print("記した:", sum(1 for v in vids if v["privacy"] == "public"), "本")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    for c in ("lint", "build", "read", "critique", "order-image"):
        sub.add_parser(c).add_argument("id")
    h = sub.add_parser("hear"); h.add_argument("id"); h.add_argument("--medium", action="store_true")
    sc = sub.add_parser("schedule"); sc.add_argument("id"); sc.add_argument("--at", required=True)
    sc.add_argument("--replace", default=""); sc.add_argument("--force", action="store_true")
    sc.add_argument("--dry-run", action="store_true")
    sub.add_parser("measure")
    a = ap.parse_args(argv)
    fn = globals()["cmd_" + a.cmd.replace("-", "_")]
    return fn(a) or 0


if __name__ == "__main__":
    sys.exit(main())
