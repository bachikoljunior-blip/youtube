"""音と絵を mp4 に組む。ffmpeg の concat demuxer（1コマ 1枚の静止画 + そのコマの wav）。"""
from __future__ import annotations

from pathlib import Path

from . import narration, viz as _viz
from .common import probe_duration, run, workdir
from .script import Script, part_images
from .slides import contact_sheet, is_transient_frame, slide, slide_frames
from .tts import concat, synth_script


def build(s: Script, image: Path | None = None, parts: dict[str, Path] | None = None) -> dict:
    """`image` は本ぜんたいの背景・`parts` は**部の名 → その部の絵**（オーナー 09/16 12:1x `751f4947`）。

    `parts` に無い部（絵がまだ届いていない）は、本の背景へ落ちます ＝ **止まりません**
    （`docs/IMAGE_ORDERS.md`「来ていなければ待たずに焼く」と同じ扱い）。
    """
    d = workdir(s.id)
    audio = synth_script(s, d)
    wavs = [w for w, _ in audio]
    durs = [t for _, t in audio]
    full = concat(wavs, d / "voice.wav")
    n = len(s.segments)
    # **形は台本が持ちます**（既定 `short` ＝ 縦 1080x1920。`script.Script.form`・`docs/GOAL.md` (4-g) 2）。
    # ここで渡し忘れると横の本が縦の絵で焼けるので、`slide()` の既定値ではなく **必ず渡す**。
    parts = parts or {}
    names = part_images(s.segments)
    # **図の在るコマは動く数枚**（オーナー 2026-09-17 20:4x `d699098f`・`studio/viz.py`）。
    # 無いコマは今までどおり 1枚。`pngs` は sheet 用（コマごとに最後の 1枚）・`entries` は ffmpeg に渡す全部。
    pngs: list[Path] = []
    entries: list[tuple[Path, float]] = []
    # **前のコマで もう動いた歩**（積み上がる表・棒は、コマが進むごとに 1行 増える）。
    # ここに在る歩は、次のコマでは**頭から出ていて動きません**（`narration.cue_windows(carry=)`）。
    # 在庫 42本 の実測（2026-09-19 14:3x）: 当たらない歩 476 のうち **172（36%）が この形**で、
    # **声が新しい行を言っている間に、前の行が湧いて**いました。
    seen: set[tuple[str, ...]] = set()
    for i, (seg, nm, t) in enumerate(zip(s.segments, names, durs), 1):
        bg = parts.get(nm) or image
        # **声の時計**（`studio/narration.py`・オーナー 2026-09-19 12:3x `9155fe09`
        # 「ナレーションとアニメーションの表現をリンクさせたりしないとわかりやすくなんないでしょ？」）。
        # 図の 1歩 は**その数を声が言う瞬間**に動き、字幕は**いま言っている句**が光る。
        tl = narration.timeline(seg.say, t, s.yomi)
        sigs = [tuple(c) for c in _viz.step_keys(seg.viz)] if seg.viz else []
        carry = 0
        while carry < len(sigs) and sigs[carry] and sigs[carry] in seen:
            carry += 1
        wins = (narration.cue_windows(seg.say, t, _viz.step_keys(seg.viz), s.yomi, carry=carry)
                if seg.viz else [])
        seen.update(x for x in sigs if x)
        plan = narration.frame_plan(t, tl, wins, _viz.steps(seg.viz) if seg.viz else 0)
        if len(plan) <= 1 and not seg.viz:
            # 句が 1つ しか無いコマ（光りが動かない）は、今までどおり 1枚。焼きを増やさない
            p = slide(seg.show, seg.sub, seg.say, i, n, bg, d / f"slide-{i:02d}.png",
                      tag=seg.tag, board=seg.board, form=s.form)
            entries.append((p, t))
            pngs.append(p)
            continue
        fr = slide_frames(seg.show, seg.sub, seg.say, i, n, bg, d, t, seg.viz or None,
                          tag=seg.tag, board=seg.board, form=s.form, plan=plan)
        entries += fr
        pngs.append(fr[-1][0])
    lst = d / "slides.txt"
    lines = []
    for p, t in entries:
        lines.append(f"file '{p.resolve()}'\nduration {t:.4f}\n")
    lines.append(f"file '{pngs[-1].resolve()}'\n")   # concat demuxer の仕様: 最後の1枚は duration 無しで繰り返す
    lst.write_text("".join(lines), encoding="utf-8")
    mp4 = d / f"{s.id}.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
         "-i", str(full), "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-r", "30", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(mp4)])
    # **動く途中の絵は消す**（`slides.slide` の `fast` の註 —— 圧縮を最小にした 1枚 4MB を数百枚 残さない）。
    # 最後の 1枚（sheet に出る物）は残す。
    for p, _t in entries:
        if is_transient_frame(p):
            p.unlink(missing_ok=True)
    sheet = contact_sheet(pngs, d / "sheet.png")
    # **焼いた mp4 の指紋をその場で刻む**（2026-09-11 20:5x・hourly・Opus。`script.build_sig` の註）。
    # ここに置く理由: mp4 を書くのはこの関数だけなので、**刻み忘れる道がありません**
    # （呼ぶ側に置くと、次に別の口から焼いた回が黙って古い刻印を残します）。
    # `work/` は git に入らないので、**刻印は台帳の `built` の側にも要ります**（`cli.cmd_build`）。
    sig = s.build_sig(image)
    (d / "build.sig").write_text(sig, encoding="utf-8")
    # **焼いた台本そのものも、隣に写します**（2026-09-20 00:xx・optimizer・Opus 5・ultracode）。
    # **なぜ**（この周が踏んだ実測）: `2026-09-20-nenkin-tedori-hayamihyou` の mp4 は
    # `3:0ff130dd52b0` を刻んでいるのに、**commit された台本から引くと `3:0653fadbdbec`** でした。
    # 焼いたのは前の周の worktree に在った**まだ commit されていない台本**で、
    # **その台本は worktree ごと消えました** ＝ **その mp4 を「新しい」と言える台本が、どこにも無い。**
    # `status` は永久に「焼き直しが要る」と言い、次の回は毎回 **19分** を払い直します
    # （長尺の焼きは 1,180秒 ＝ 落ちる時間が周より長い所が、他の焼き直しと違います）。
    # **指紋だけでは足りません** —— 指紋は「違う」としか言えず、**何が違うか**は台本が要ります。
    # ここに置く理由は `build.sig` と同じ: **mp4 を書くのはこの関数だけなので、写し忘れる道がありません。**
    # `work/` は git に入らないので**これは記録ではなく証拠**です（掃かれます・`WORK_KEEP_DAYS`）。
    # **覆る条件**: (1) `git status --porcelain` を `cmd_build` の前に鳴らす手を足したら、
    #     こちらは「消えた台本を読む」側だけに残ること（**鳴らす側と読む側は別の問い**）。
    # (2) 台本が大きくなって写しが重くなったら（いまは 1本 数十KB）、`segments` だけに絞ってよい ——
    #     **指紋に入る物は全部 残すこと**（`build_sig` が読む 4つ: voice・rate・yomi・kana_in_voice）。
    try:
        (d / "script.json").write_text(s.model_dump_json(indent=1), encoding="utf-8")
    except OSError:
        pass   # 写しは証拠であって、焼きの成否ではありません ＝ **止めません**
    return {"mp4": mp4, "wavs": wavs, "durations": durs, "total": probe_duration(mp4),
            "sheet": sheet, "slides": pngs, "sig": sig,
            "frames": len(entries), "viz": sum(1 for g in s.segments if g.viz)}


def built_sig(vid: str) -> str | None:
    """**いま `work/` に在る mp4 が、どの本文で焼かれたか**（無ければ None ＝ 焼いていないか、刻む前の版で焼いた）。"""
    p = workdir(vid) / "build.sig"
    return p.read_text(encoding="utf-8").strip() if p.exists() else None


def built_script(vid: str) -> "Script | None":
    """**その mp4 を焼いた台本そのもの**（無ければ None ＝ 写す前の版で焼いた）。

    `built_sig` は「いまの台本と違う」としか言えません。**何が違うか**を読むのはこちらです。
    使い所は 2つ: **(1)** 消えた worktree で焼かれた mp4 の中身を見る（この関数が在る理由）。
    **(2)** `stale_why` が「台本が動いた」と言ったとき、**どのコマが動いたか**を出す。

    **壊れていたら None を返します**（写しは証拠であって台帳ではない ＝ 読めないより嘘が高い）。
    """
    p = workdir(vid) / "script.json"
    if not p.exists():
        return None
    try:
        return Script.model_validate_json(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
