#!/usr/bin/env python3
"""独立評価（M13）の材料を、コンテナが消えても残す。

    残す    scripts/upload_only.py が投稿の直後に self.stash() を呼ぶ
    探す    python scripts/critique_queue.py            ← 未評価のものを出す
    見る    python scripts/critique_queue.py <動画ID>   ← 材料の置き場所を出す

**なぜ要るか（2026-08-15 に実測で見つけた穴）。**

`docs/CRITIQUE.md` は「contact sheet ができた後、投稿の前」に評価しろと言い、
`docs/trigger_main.md` は「回せなかった回は次の回に回させる」と言っています。
**この2つは両立しません。**

`build/` は `.gitignore` で、いまは1周ごとにセッションを畳みます。
**畳んだ瞬間にコンテナごと消えるので、「次の回に回す」先には何も残っていません。**
台本はその回のセッションが書いたもので、作り直しても同じ文にはなりません
（`src.script_writer` は схема を出すだけで、本文は毎回書き下ろし）。
だから**投稿済みの動画は、あとから評価できませんでした。**

8/15 の3回は「サブエージェントが使えないから回せなかった」と書いて終えましたが、
**仮に使えても回せませんでした。** 材料のほうが先に消えているからです。
`src/bars.py` が「公開した棒」を同じ理由で残しているのと、まったく同じ穴です。

**投稿の時点で材料を確定させて、リポジトリに残す。** そうすれば評価は
「投稿の前」に縛られず、次の回でもその次でもできます。
評価が基準未満なら、**予約は外せます**（公開までの猶予がそのまま持ち時間）。
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    # **`deadlines()` が `src.uploader` / `src.dupes` を読みます。**
    # 入れずに呼ぶと `No module named 'src'` で控えにも落ちられず、
    # 並びが**黙って動画ID順のまま**になります（2026-08-16 に実際に踏んだ）。
    sys.path.insert(0, str(ROOT))
STASH = ROOT / "data" / "critique_queue"
LEDGER = ROOT / "data" / "critique.jsonl"
JST = timezone(timedelta(hours=9))


def _change_ratios(work: Path) -> list[float] | None:
    """隣り合うコマが画面のどれだけを塗り替えているか、**焼いた実物**から測る。

    ## なぜここで測るのか（2026-08-16 22:3x。**同じ空振りが3回続いてから**）

    独立評価と目視は、**contact sheet（縮んだタイル）しか見ていません。**
    そして3回続けて「画面が変わっていない」と報告し、**3回とも誤報**でした:

        08/16 21:5x  目視3体中2体「最終コマが描画失敗＝作り直し」   正体はこちらが描いた余り枠
        08/16 22:0x  独立評価3体「前提表 11→12 が完全に同一」      実測 **16.10%** が違う
        08/16 22:3x  独立評価3体「冒頭2コマが完全に同一」          実測 **12.24%** が違う

    **後の2件は、この回が `bake_slides.py --plan` で焼き直して初めて分かりました。**
    1本あたり 30秒〜1分、読み解きを入れると**毎回10〜25分**が、
    「起きていないこと」の確認に消えています。**種類が同じなので、次も出ます。**

    塞ぐ先は報告のほうではありません。**測った数字が、報告のとなりに無いこと**です。
    `verify.slide_change_ratios` は投稿の時点で既に走れる状態にあり
    （`work/slides/*.png` がまだある）、**値を捨てていただけ**でした。

    ここで積んでおけば、次の回は `critique_run.py` の出力で
    **その場で突き合わせられます**（焼き直し 0回・追加費用 0）。

    **測れなくても止めません。** これは材料の付録で、本体（sheet と読み上げ文）
    ではありません。長尺や、slides を消したあとの再投稿でも stash は通すこと。
    """
    slides = sorted((work / "slides").glob("*.png"))
    if len(slides) < 2:
        return None
    try:
        from src import verify

        return [round(r, 4) for r in verify.slide_change_ratios(slides)]
    except Exception as exc:                       # 付録なので、落ちても投稿は通す
        print(f"[queue] 隣との差を測れませんでした（続行）: {exc}")
        return None


def stash(topic: str, video_id: str, script: dict, work: Path,
          thumbnail_set: bool | None = None) -> Path | None:
    """contact sheet と読み上げ文を、動画IDで引ける場所へ写す。

    **contact sheet が無ければ何もしません。** `inspect_build.py` を通していない
    投稿は評価の材料が無く、無い材料の空箱を積んでも次の回を惑わせるだけです。
    """
    sheet = work / "inspect.jpg"
    if not sheet.exists():
        print("[queue] inspect.jpg が無いので材料を残せません（inspect_build.py を通してください）")
        return None

    # 読み上げ文だけを取る。**題材も狙いも渡さない**のが独立評価の条件なので、
    # ここで topic 名や calc の種類まで書くと、次の回がそのまま子に渡してしまう。
    #
    # **鍵は `segments` です。`scenes` ではありません**（2026-08-15 に直した）。
    # 8/15 に材料を残す仕組みを入れたとき、ここを `scenes` と書いていました。
    # 台本にその鍵は無いので **`.get()` が黙って空を返し、読み上げ文が
    # 毎回0行で積まれていました**（`NHKylqsNfTw` `CdX2oIb7BG8` の2本が実際にそれ）。
    # `docs/CRITIQUE.md` は「渡してよいものは contact sheet と読み上げ文の2つ」と
    # 書いているので、**材料が半分だけ残る = 検査が半分死ぬ**形でした。
    # 落ちずに空で通るのが最悪なので、**取れなかったら声を上げます。**
    segments = script.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError(
            "台本に `segments` がありません（読み上げ文を残せません）。"
            f" 実際の鍵: {sorted(script)}"
        )
    lines = [str(s.get("narration", "")).strip() for s in segments]
    if not any(lines):
        raise ValueError("`segments` はありますが `narration` が全部空です。")

    # **確かめてから写す。** 先に写すと、上で上げたときに
    # 相方の json が無い .jpg だけが残ります。
    STASH.mkdir(parents=True, exist_ok=True)
    shutil.copy2(sheet, STASH / f"{video_id}.jpg")

    # **`slides_plan.json` も一緒に残します**（2026-08-15。5回持ち越された項目）。
    #
    # ここには contact sheet と読み上げ文しか入っていませんでした。
    # **どちらも焼き上がった絵で、焼き直せません。** 描画を直したときに
    # 「直る前と後で絵がどう変わったか」を測るには、`visuals.render` に
    # 食わせられる入力そのもの（＝**割った後のコマの列**）が要ります。
    #
    # 実際に詰まりました。8/15 22:0x の回は「実質同じ絵か」を測るために
    # **動画を2本生成しています**（11分×2）。`slides_plan.json` さえあれば
    # `scripts/bake_slides.py --plan` で **30秒**、生成0回で済みました。
    # 材料が21本ぶん積んであったのに、**測れる形で積んでいなかった**ということです。
    #
    # **1本あたり数KB。** 独立評価の子には渡しません（渡してよいのは
    # contact sheet と読み上げ文の2つ＝`docs/CRITIQUE.md`）。これは
    # **こちら側が過去の本を焼き直すための入力**で、用途が別です。
    plan_src = work / "slides_plan.json"
    plan_kept = False
    if plan_src.exists():
        shutil.copy2(plan_src, STASH / f"{video_id}.plan.json")
        plan_kept = True

    # **サムネイルそのものを残します**（2026-08-17。**3回持ち越された項目**）。
    #
    # 日枠が切れている13時間、`thumbnails.set` は 403 で落ちます
    # （`videos.insert` は通るので、投稿だけが済んで**サムネイルの無い予約**が積まれる）。
    # 申し送りは3回とも「枠が戻った回に `scripts/refresh_thumbnail.py` を回すこと」
    # と書いていました。**その手順は実行できません。**
    #
    # `refresh_thumbnail.py` が読むのは `build/<テーマID>/` ですが、
    # **`build/` は .gitignore で、1周ごとにコンテナごと消えます。**
    # 枠が戻る JST 16:00 には、03時台に上げた本の `build/` はとっくにありません。
    # **3回の申し送りは、構造として不可能なことを頼み続けていました**
    # （`docs/trigger_main.md` §2.7「申し送りの『なぜか』は一度疑う」）。
    #
    # 焼き直す必要はありません。**サムネイルは投稿の時点でもう出来ています。**
    # YouTube に載らなかっただけなので、**bytes を残せば、後の回が押すだけで済みます。**
    # 1本 約70KB —— 同じ場所に既にある contact sheet の 10分の1 です。
    thumb_src = work / "thumbnail.jpg"
    thumb_kept = False
    if thumb_src.exists():
        shutil.copy2(thumb_src, STASH / f"{video_id}.thumb.jpg")
        thumb_kept = True

    (STASH / f"{video_id}.json").write_text(
        json.dumps(
            {
                "video_id": video_id,
                "topic": topic,
                "stashed_at": datetime.now(JST).isoformat(timespec="seconds"),
                "orientation": "縦" if script.get("short", True) else "横",
                "narration": [ln for ln in lines if ln],
                "slides_plan": plan_kept,
                "change_ratios": _change_ratios(work),
                "thumbnail_stashed": thumb_kept,
                # **投稿の時点で YouTube に載ったかどうか。**
                # `None` は「呼ぶ側が渡さなかった」＝分からない、です。
                # **`False` と混ぜないこと** —— 分からないものを「載っていない」と
                # 読むと、載っている本にも押し直しにいきます（無害だが枠を食う）。
                "thumbnail_set": thumbnail_set,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"[queue] 独立評価の材料を残しました: {STASH / f'{video_id}.jpg'}")
    if plan_kept:
        print(f"[queue] 焼き直せる入力も残しました: {STASH / f'{video_id}.plan.json'}")
    else:
        # **黙って落とさない。** 無いことに気づけないのが、この項目が5回持ち越された理由です。
        print(f"[queue] **{plan_src} がありません** —— この本は後から焼き直せません")
    if thumbnail_set is False:
        if thumb_kept:
            print("[queue] **サムネイルが YouTube に載っていません。** "
                  f"bytes は残したので、枠の戻った回に "
                  f"`python scripts/refresh_thumbnail.py --missing` で押し直せます")
        else:
            print(f"[queue] **{thumb_src} がありません** —— "
                  "この本のサムネイルは後から載せ直せません")
    return STASH / f"{video_id}.jpg"


def missing_thumbnail() -> list[dict]:
    """**サムネイルが載っていないまま予約に入っている本**（2026-08-17）。

    `thumbnail_set is False` かつ bytes が残っているものだけを返します。
    **`None`（分からない）は返しません** —— この印より前に上げた本は
    区別がつかないので、押し直しの対象にすると全部を押しにいきます。
    """
    out = []
    for meta_path in sorted(STASH.glob("*.json")):
        if meta_path.name.endswith(".plan.json"):
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if meta.get("thumbnail_set") is not False:
            continue
        video_id = meta.get("video_id") or meta_path.stem
        thumb = STASH / f"{video_id}.thumb.jpg"
        if not thumb.exists():
            continue
        out.append({"video_id": video_id, "topic": meta.get("topic"),
                    "thumb": thumb, "stashed_at": meta.get("stashed_at")})
    return out


def mark_thumbnail_set(video_id: str) -> bool:
    """**押せた本の印を消す。** 消さないと、次の回も同じ本を押しにいきます。

    呼ぶのは `scripts/refresh_thumbnail.py --missing` が**実際に載せたあと**だけ。
    先に消すと、落ちた本が一覧から消えて**二度と拾われません。**
    """
    meta_path = STASH / f"{video_id}.json"
    if not meta_path.exists():
        return False
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    meta["thumbnail_set"] = True
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1),
                         encoding="utf-8")
    return True


def _scored() -> set[str]:
    """点の付いたもの（テーマID・動画IDのどちらでも）。

    **2026-08-15 まで、この関数は常に空集合と同じものを返していました。**
    `critique_record.py` が積む行のキーは **`video`** で、ここは `video_id` を
    読んでいました。**綴りが違うだけで、どの行にも当たりません。**

    結果、**一度点を付けたものが待ち行列から消えませんでした。**
    `data/critique.jsonl` に `s-kojo-4` と `s-iryohi-2` が2回ずつ入っているのは
    これです（同じ動画を2回評価して2回積んだ）。**待ちは減らないので、
    毎回おなじ動画に3体を投げ続け、点が二重に積まれます。**
    順位相関を出す側から見ると、同じ動画が2票ぶん効きます。

    **落ちも警告も出ません。**「待ちが3件ある」は正しく見えていました。
    `.get()` が黙って空を返す形で踏むのは、8/15 に入れた `stash()` の
    `scenes`/`segments` に続いて2回目です。**両方のキーを読むようにします。**
    """
    if not LEDGER.exists():
        return set()
    out = set()
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        for key in ("video", "video_id", "topic"):
            if row.get(key):
                out.add(row[key])
    return out


def deadlines(offline_only: bool = False) -> tuple[dict[str, tuple[int, float]], str]:
    """各動画の**締切**（＝直せる猶予）を返す。`{動画ID: (段, 時間)}` と、取れた口の名前。

    段は小さいほど先に評価すべきもの:

        0  予約あり  → 公開まで**あと何時間**。**ここだけが「評価して直せる」窓**です
        1  公開済み  → もう直せませんが engaged が付くので M13 の較正には使えます
        2  予約なし  → **直す先も較正の材料も無い。**既定では待ち行列に出しません

    口が落ちても止まりません（`data/uploaded.jsonl` の控えへ落ちる）。
    **控えは「上げたときの予約時刻」なので、あとから外した本を予約ありと読みます。**
    どちらの口で読んだかを返すのは、そのためです。
    """
    if not offline_only:
        try:
            from src.uploader import _service
            from src.history import channel_video_ids

            yt = _service()
            ch = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
            ids = channel_video_ids(yt, ch["contentDetails"]["relatedPlaylists"]["uploads"])
            # **口は同時に欠けます**（uploads は予約中を落とし、search は 429）。
            # `status.py` と同じく、手元の控えで埋め戻す。
            try:
                from src import dupes as _dupes
                ids += [r["id"] for r in _dupes.ledger_rows() if r["id"] not in set(ids)]
            except Exception:
                pass
            items = []
            for i in range(0, len(ids), 50):
                items += yt.videos().list(
                    part="status", id=",".join(ids[i:i + 50])).execute()["items"]
            now = datetime.now(timezone.utc)
            out: dict[str, tuple[int, float]] = {}
            for v in items:
                st = v["status"]
                if st["privacyStatus"] == "public":
                    out[v["id"]] = (1, 0.0)
                elif st.get("publishAt"):
                    hours = (datetime.fromisoformat(st["publishAt"].replace("Z", "+00:00"))
                             - now).total_seconds() / 3600
                    out[v["id"]] = (0, hours)
                else:
                    out[v["id"]] = (2, 0.0)
            return out, "API"
        except Exception as exc:  # 口が落ちても待ち行列は出す
            print(f"[queue] 締切を口から取れませんでした（控えへ落ちます）: {str(exc)[:90]}")

    try:
        from src import dupes as _dupes
        now = datetime.now(timezone.utc)
        out = {}
        for r in _dupes.ledger_rows():
            at = r.get("at")
            if not at:
                out[r["id"]] = (2, 0.0)
                continue
            hours = (datetime.fromisoformat(str(at).replace("Z", "+00:00"))
                     - now).total_seconds() / 3600
            out[r["id"]] = (0, hours) if hours >= 0 else (1, 0.0)
        return out, "控え（data/uploaded.jsonl・外した本を予約ありと読みます）"
    except Exception as exc:
        print(f"[queue] 控えも読めませんでした（並びは動画ID順のまま）: {str(exc)[:90]}")
        return {}, "なし"


def pending(include_stranded: bool = False,
            order: bool = True,
            deadline: dict[str, tuple[int, float]] | None = None) -> list[dict]:
    """未評価の材料を、**締切の近い順**に返す。

    ## なぜ並べ替えるのか（2026-08-16 に実測して直した。**持ち越し7回目**）

    ここは長らく `sorted(STASH.glob("*.json"))` ＝ **動画IDのアルファベット順**でした。
    **その順番は、評価の値打ちと何の関係もありません。**

    1周で回せるのは1〜3本、待ちは38本。**つまり順番が選択そのものです。**
    実測（2026-08-16 11:2x、待ち38本）:

        `--next` が選ぶ先頭   J0QK59pUg-4 ＝ 公開まで **あと244時間**
        いちばん近い本       crO3FUvL2NI ＝ あと **22時間** なのに **24番目**
        上位10件のうち4件    **予約なし**（重なりで外した本。**二度と公開されません**）

    **予約なしの本を評価しても、直す先がありません**（もう外してある）。
    engaged も付かないので M13 の較正にも入りません。**`claude -p` 3体ぶんが丸ごと捨てです。**
    そして公開24時間前の本には、`--next` を何回叩いても当たりません ——
    **評価が間に合った本だけが「予約を外す」判断に使える**のに、
    そこへ一度も届かない並びでした。

    前の回（09:1x）が直したのは「先頭で止まる」＝空振りのほうで、
    **先頭が何であるべきかは誰も見ていませんでした。**

    ## 割り引いて読むこと

    - 締切は外の口から取ります。**落ちたら控えへ落ち、控えは外した本を予約ありと読みます**
      （`deadlines()`）。並びが少し鈍るだけで、止まりはしません
    - **口にも控えにも無い本は、段0の末尾**（＝予約ありの一番後ろ）に置きます。
      「分からない」を「捨ててよい」と読まないため
    """
    if not STASH.exists():
        return []
    done = _scored()
    out = []
    for meta in sorted(STASH.glob("*.json")):
        # **`*.plan.json` を拾わないこと**（2026-08-15）。焼き直し用の入力を
        # 隣に置いた瞬間、この glob が**1本につき2件**返すようになります。
        # 中身は台本ではないので `video_id` が無く、`meta.stem` から
        # **`"<ID>.plan"` という架空の待ち**が生えます（点の付けようが無いので
        # 永久に消えない）。
        #
        # 名前と型の**両方**で弾いています。いま実際に効いているのは型のほう
        # （`slides_plan.json` は配列なので `isinstance` で落ちる）ですが、
        # **中身の形が変わった日に、名前のほうだけが残ります。**
        if meta.name.endswith(".plan.json"):
            continue
        try:
            d = json.loads(meta.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(d, dict):
            continue
        vid = d.get("video_id", meta.stem)
        # `critique_record.py` は topic でも動画IDでも積めるので、両方で照合する。
        if vid in done or d.get("topic", "") in done:
            continue
        if not (STASH / f"{vid}.jpg").exists():
            continue
        out.append(d)

    if not order:
        return out

    if deadline is None:
        deadline, _ = deadlines()
    # **口にも控えにも無い本は段0の末尾**（`inf`）。「分からない」を「捨ててよい」と読まない。
    ranked = [(deadline.get(d["video_id"], (0, float("inf"))), d) for d in out]
    if not include_stranded:
        ranked = [(k, d) for k, d in ranked if k[0] != 2]
    ranked.sort(key=lambda kd: (kd[0][0], kd[0][1], kd[1]["video_id"]))
    return [d for _, d in ranked]


def main(argv: list[str]) -> int:
    include_stranded = "--include-stranded" in argv
    argv = [a for a in argv if a != "--include-stranded"]
    if argv:
        vid = argv[0]
        sheet, meta = STASH / f"{vid}.jpg", STASH / f"{vid}.json"
        if not sheet.exists():
            print(f"{vid} の材料はありません（投稿より前に投稿したものは残っていません）")
            return 1
        d = json.loads(meta.read_text(encoding="utf-8"))
        print(f"contact sheet : {sheet}")
        print(f"動画の向き    : {d['orientation']}")
        plan = STASH / f"{vid}.plan.json"
        if plan.exists():
            # **独立評価の子に渡すものではありません**（渡してよいのは
            # contact sheet と読み上げ文の2つ）。こちらが絵を焼き直すための入力です。
            print(f"焼き直す入力  : {plan}")
            print(f"  python scripts/bake_slides.py --plan {plan}"
                  f"{' --short' if d['orientation'] == '縦' else ''}")
        else:
            print("焼き直す入力  : **ありません**（この本は絵を測り直せません）")
        print("読み上げ文:")
        for ln in d["narration"]:
            print(f"  {ln}")
        return 0

    dl, source = deadlines()
    rows = pending(include_stranded=include_stranded, deadline=dl)
    hidden = [] if include_stranded else [
        d for d in pending(include_stranded=True, deadline=dl)
        if dl.get(d["video_id"], (0, 0.0))[0] == 2]
    print(f"=== 独立評価の待ち（data/critique_queue）===")
    print(f"  **締切の近い順**（＝直せる猶予が短い順）。締切の口: {source}")
    if not rows:
        print("  待ちはありません。")
        print("  **これは「全部評価した」とは限りません。**材料が残る前に投稿したものは、")
        print("  ここに出ません（2026-08-15 より前の投稿が全部そうです）。")
        return 0
    for d in rows:
        # **焼き直せるかを一覧に出す。** 出さないと、次の回は「材料はある」と読み、
        # 焼き直せない本を測ろうとして**生成（11分）に戻ります。**
        bakeable = "焼直可" if (STASH / f"{d['video_id']}.plan.json").exists() else "焼直不可"
        rank, hours = dl.get(d["video_id"], (0, float("inf")))
        if rank == 1:
            when = "公開済み  "
        elif hours == float("inf"):
            when = "締切不明  "
        else:
            when = f"あと{hours:5.0f}h"
        print(f"  {d['video_id']}  {when}  {d['orientation']}  {len(d['narration'])}行  "
              f"{bakeable}  投稿 {d['stashed_at'][:16]}")
    n_bakeable = sum(1 for d in rows if (STASH / f"{d['video_id']}.plan.json").exists())
    print()
    if hidden:
        # **黙って減らさないこと。** 数だけ減ると「評価が進んだ」に見えます。
        print(f"  出していない {len(hidden)}本: **予約なし**（重なりで外した本）。"
              f"直す先も engaged も無いので評価しても捨てになります")
        print(f"    {' '.join(d['video_id'] for d in hidden)}")
        print("    見るなら `python scripts/critique_queue.py --include-stranded`")
    print(f"  焼き直せるのは {n_bakeable}/{len(rows)} 本"
          f"（`slides_plan.json` を残し始めたのは 2026-08-15 23:xx から）")
    print("  手順は docs/CRITIQUE.md。材料の中身は:")
    print("    python scripts/critique_queue.py <動画ID>")
    print("  積むのは:")
    print("    python scripts/critique_record.py <動画ID> <s1> <s2> <s3>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
