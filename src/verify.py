"""投稿前の検査。

無人で本番チャンネルに出すので、生成物が壊れていないかを確認してから投稿する。
1つでも外れたら投稿しない。壊れた動画が上がるより、その日1本落ちるほうがいい。

**ここに何を足すかの基準。** 実際に壊れて、しかも機械が素通りしたものを足す。
思いつきの網羅ではない。これまでの故障はすべて「誰も見ていなかったもの」で、
フレームを抜いて目で見たときにだけ見つかっている。目視が抜けるのは注意力の
問題ではなく手間の問題なので、**手間のかからない側（機械）に寄せる**のが筋。

機械で見られないものは `scripts/inspect_build.py` が1枚にまとめる。そちらは最後の砦で、
ここに書けるものをそちらに残さないこと。
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

from .subtitles import _NUM_TOKEN
from .util import require, run

# サムネイルの上限（YouTube）と、いつも作っている寸法
THUMB_MAX_BYTES = 2_000_000
THUMB_SIZE = (1280, 720)
# 実測: 公開済み7本は 39.8 以上、単色は 0.0。あいだに置く。
THUMB_MIN_STDDEV = 12.0
# 量産テンプレート判定を避けるための下限。CLAUDE.md「この作りの根幹」より。
MIN_CHARTS = 3


class VerificationError(RuntimeError):
    pass


def _probe(path: Path) -> dict:
    require("ffprobe")
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise VerificationError(f"ffprobe が読めませんでした: {proc.stderr[:300]}")
    return json.loads(proc.stdout)


def _check_thumbnail(work: Path) -> list[str]:
    """サムネイルは一度も検査されておらず、一度も見られないまま2本壊れて公開された。"""
    thumb = work / "thumbnail.jpg"
    if not thumb.exists():
        return ["サムネイルが作られていない"]

    problems = []
    size = thumb.stat().st_size
    if size > THUMB_MAX_BYTES:
        problems.append(f"サムネイルが {size} バイトで上限の {THUMB_MAX_BYTES} を超えている")
    try:
        from PIL import Image, ImageStat

        with Image.open(thumb) as img:
            if img.size != THUMB_SIZE:
                problems.append(f"サムネイルが {img.size} で、期待は {THUMB_SIZE}")
            spread = min(ImageStat.Stat(img.convert("RGB")).stddev)
        # バイト数ではなく画素のばらつきで見る。バイト数は圧縮率の話で、
        # 中身が空かどうかの話ではない。実測では本物が 39.8 以上、単色が 0。
        if spread < THUMB_MIN_STDDEV:
            problems.append(
                f"サムネイルの画素のばらつきが {spread:.1f} しかなく、ほぼ単色に見える"
            )
    except Exception as exc:
        problems.append(f"サムネイルを開けない: {exc}")
    return problems


def _check_subtitles(work: Path) -> list[str]:
    """字幕は「。」だけの行と、数字の途中での改行で壊れた。どちらも機械で見える。"""
    ass = work / "subtitles.ass"
    if not ass.exists():
        return []

    # Dialogue の書式は Layer..Effect の9項目のあとに本文。本文にも読点が入るので
    # カンマで9回だけ割る。`,,` を目印にすると Name と Effect の両方に当たる。
    rows = [
        row[len("Dialogue:"):].split(",", 9)
        for row in ass.read_text(encoding="utf-8").splitlines()
        if row.startswith("Dialogue:")
    ]
    lines = [r[9].strip() for r in rows if len(r) == 10]
    if not lines:
        return ["字幕に1行も入っていない"]

    problems = []
    orphans = [t for t in lines if t and not re.search(r"[^\s。、！？…・]", t)]
    if orphans:
        problems.append(f"記号だけの字幕行が {len(orphans)} 行ある（例『{orphans[0]}』）")

    # 行末と次の行頭が両方とも数字・単位なら、かたまりの途中で割れている。
    split_nums = [
        (a, b) for a, b in zip(lines, lines[1:])
        if a and b and a[-1] in _NUM_TOKEN and b[0] in _NUM_TOKEN
    ]
    if split_nums:
        a, b = split_nums[0]
        problems.append(f"数字の途中で改行している箇所が {len(split_nums)} 件（『{a}』→『{b}』）")
    return problems


def _check_headline_from_calc(work: Path, script: dict | None) -> list[str]:
    """**冒頭に出す数字が、こちらの計算から出たものであること。**

    この作りの根幹は「制度を解説するのではなく、自分で計算した結果を発表する」。
    制度のまとめ直しは、どれだけ丁寧でも「自分で作成していない資料の読み上げ」の側に
    落ち、収益化されない。**収益化されなければ収入はゼロ**なので、これは
    見栄えではなく到達可能性の話。

    ところが 2026-08-05 の残業代ショートは、冒頭が「除外できる手当は7つだけ」だった。
    7 は労基法37条5項の列挙の数であって、`src/calc/` が計算した数字ではない。
    **機械の検査は全部通った。** `_check_short_opening` は「1枚目が stat か」しか
    見ておらず、**その数字の出どころは誰も見ていなかった。**

    ここで見る。計算をもう一度走らせ、冒頭 stat の数字が出力に含まれるか確かめる。
    キャッシュではなく実行するのは、保存した値と台本がずれる余地を作らないため。

    数字が1つも入っていない stat（「7つだけ」の「7」も拾う）も落とす。
    **落ちたら作り直し。** ショートの作り直しは数分で済む。
    """
    if not script:
        return []
    segments = script.get("segments") or []
    if not segments:
        return []
    visual = segments[0].get("visual") or {}
    stat = str(visual.get("stat") or "")
    source = str(visual.get("stat_source") or "")
    if not re.search(r"\d", stat):
        return [f"冒頭の数字に数値が入っていない（『{stat}』）。"
                "ショートの冒頭は計算結果の数字1つにする"]

    # テーマ ID は build ディレクトリ名。そこから calc モジュールを引く。
    try:
        import yaml
        topics = yaml.safe_load(
            (Path(__file__).resolve().parent.parent / "config" / "topics.yaml").read_text(encoding="utf-8")
        )["topics"]
    except Exception as exc:                       # 設定が読めないだけで投稿を止めない
        return [f"topics.yaml が読めず、冒頭の数字の出どころを確かめられません: {str(exc)[:60]}"]

    name = ""
    for t in topics:
        if str(t.get("id")) == work.name:
            name = str(t.get("calc") or "").strip()
            break
    if not name:
        return []                                  # calc の無いテーマは対象外

    import subprocess
    import sys as _sys

    try:
        proc = subprocess.run([_sys.executable, "-m", f"src.calc.{name}"],
                              capture_output=True, text=True, timeout=300,
                              cwd=str(Path(__file__).resolve().parent.parent))
    except Exception as exc:
        return [f"src.calc.{name} を実行できず、冒頭の数字を確かめられません: {str(exc)[:60]}"]
    if proc.returncode != 0:
        return [f"src.calc.{name} が失敗して、冒頭の数字を確かめられません"]

    # **申告された出どころを、計算の出力と突き合わせる。**
    #
    # 最初は stat の数字そのものを出力から探した。**それでは効かない。**
    # 台本は計算結果を言い換える（「ずれ 31か月」→「最大2年7か月」）ので、
    # 正しい動画まで落ちた。逆に「7つだけ」の 7 は1桁なので、どんな出力にも
    # たまたま現れる。**桁数でしきいを置いたのも勘だった。**
    #
    # 数字の見た目からは出どころを判定できない。だから**台本に申告させる**。
    # 言い換える前の値を写させて、それが出力にあるかを見る。
    # 写せない＝計算に無い数字、ということになる。
    if not source:
        return [f"冒頭の数字『{stat}』に出どころ（stat_source）の申告が無い。"
                "計算結果のどの行から取ったのかを写させること"]

    def norm(s: str) -> str:
        return re.sub(r"[\s,、　]", "", s)

    if norm(source) not in norm(proc.stdout):
        return [f"冒頭の数字の出どころ『{source}』が src.calc.{name} の出力に無い。"
                "**計算していない数字を冒頭に出している。** 制度の項目数や条文番号を"
                "大きく出していないか確かめること"]
    return []


def _check_short_opening(script: dict | None) -> list[str]:
    """ショートの1枚目は stat（大きい数字1つ）であること。

    ショートは最初の1画面で離脱が決まるので、GOAL.md は「冒頭2秒で数字を出す」と
    決めてある。ところが自動生成した1本は chart で始まっていた。棒グラフは
    読むのに時間がかかるので、2秒では入ってこない。

    これは「壊れてはいないが、決めたことを黙って外している」たぐいの外れ方で、
    いちばん見つけにくい。だから機械に見せる。ショートの作り直しは5分で済み、
    毎日の投稿義務は長尺のほうなので、ここは落として作り直させてよい。
    """
    if not script:
        return []
    segments = script.get("segments") or []
    if not segments:
        return ["台本にセグメントがない"]
    kind = (segments[0].get("visual") or {}).get("kind")
    if kind != "stat":
        return [
            f"ショートの1枚目が {kind} になっている（stat であること）。"
            "最初の1画面で離脱が決まるので、冒頭は大きい数字1つにする"
        ]
    return []


def _check_slides(work: Path, script: dict | None) -> list[str]:
    """同じ絵が続くこと自体がポリシー上の risk。chart の枚数もここで数える。

    「テンプレートを使用して作成されたと思われるコンテンツ」に当たると
    収益化されない。収益化されなければ RPM がいくつでも収入はゼロなので、
    これは見栄えの話ではなく到達可能性の話。
    """
    problems = []
    slides = sorted((work / "slides").glob("*.png"))
    if slides:
        digests = [hashlib.sha1(p.read_bytes()).hexdigest() for p in slides]
        dupes = sum(1 for a, b in zip(digests, digests[1:]) if a == b)
        if dupes:
            problems.append(f"隣り合う図解が同じ画像になっている箇所が {dupes} 件")

    if script:
        kinds = [s.get("visual", {}).get("kind") for s in script.get("segments", [])]
        charts = kinds.count("chart")
        if charts < MIN_CHARTS:
            problems.append(
                f"chart が {charts} 枚しかない（下限 {MIN_CHARTS} 枚）。"
                "計算結果で図の形を変えるのが量産テンプレート判定との分かれ目"
            )
    return problems


def check(path: Path, video_cfg: dict, min_minutes: float, work: Path) -> float:
    """問題があれば VerificationError。無ければ尺（秒）を返す。"""
    probe = _probe(path)
    streams = probe.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    duration = float(probe.get("format", {}).get("duration") or 0)
    width, height = video_cfg["resolution"]

    problems: list[str] = []
    if not video:
        problems.append("映像トラックが無い")
    if not audio:
        problems.append("音声トラックが無い")
    if duration < min_minutes * 60:
        problems.append(
            f"尺が {duration / 60:.1f}分 で下限の {min_minutes}分 未満"
            "（8分を切るとミッドロール広告を入れられない）"
        )
    if video and (int(video.get("width", 0)) != width or int(video.get("height", 0)) != height):
        problems.append(f"{video.get('width')}x{video.get('height')} で、期待は {width}x{height}")

    # 先頭が真っ黒なら、素材の生成か合成のどこかが黙って失敗している。
    # 一様な画は PNG にするとほとんど圧縮されるので、バイト数で判定できる。
    if video:
        frame = work / "_first.png"
        run(["ffmpeg", "-y", "-v", "error", "-ss", "0.4", "-i", str(path),
             "-frames:v", "1", "-vf", "scale=160:90", str(frame)])
        size = frame.stat().st_size if frame.exists() else 0
        frame.unlink(missing_ok=True)
        if size < 1200:
            problems.append(f"冒頭のフレームが真っ白か真っ黒に見える（{size} バイト）")

    problems += _check_thumbnail(work)
    problems += _check_subtitles(work)

    script = None
    script_path = work / "script.json"
    if script_path.exists():
        try:
            script = json.loads(script_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"script.json が読めない: {exc}")
    # ショート（縦画面）は1本＝1つの計算結果なので chart の下限は当てない。
    # 代わりに、冒頭が大きい数字1つで始まっているかを見る。
    portrait = height > width
    problems += _check_slides(work, None if portrait else script)
    if portrait:
        problems += _check_short_opening(script)
        problems += _check_headline_from_calc(work, script)

    if problems:
        raise VerificationError("投稿前の検査に落ちました: " + " / ".join(problems))

    codec = audio.get("codec_name") if audio else "?"
    charts = 0
    if script:
        charts = [s.get("visual", {}).get("kind") for s in script.get("segments", [])].count("chart")
    print(
        f"[verify] 合格: {duration / 60:.1f}分, {video.get('width')}x{video.get('height')}, "
        f"音声 {codec}, chart {charts}枚, サムネ・字幕とも異常なし"
    )
    return duration
