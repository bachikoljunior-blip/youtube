#!/usr/bin/env python3
"""チャンネルのいまの状態を1画面に出す。

    python scripts/status.py [日数]

なぜ要るか。**判断の側の間違いも、被覆の問題だった。**

この日、2つ間違えかけた。ひとつは `statistics.viewCount` が 5634 なのを見て
ショートが伸びたと思ったこと。実際には動画ごとに数えると合計2回で、5634 は
このチャンネルの前身のものだった。**チャンネル単位の数字は前身を含む。**

もうひとつは、予約公開のはずの動画が private のまま publishAt を持っていない、
という状態を見落としかけたこと。これは黙って永久に公開されない。

どちらも「毎回いくつも API を叩いて頭の中で組み立てる」からこそ起きる。
組み立てを機械にやらせて、危ない状態には印を付ける。

`scripts/inspect_build.py` が目視に対してやったことを、判断に対してやる。
面倒だから飛ばされる、という同じ原因を、同じやり方で潰している。
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.uploader import _service  # noqa: E402

JST = timezone(timedelta(hours=9))
LOOKAHEAD_DAYS = 3      # 何日先まで予約の空きを見るか
def _is_short(video: dict) -> bool:
    """ショートかどうか。**尺で見る。** 題の #Shorts は付け忘れがある。"""
    dur = video["contentDetails"]["duration"]
    m = re.fullmatch(r"PT(?:(\d+)M)?(?:(\d+)S)?", dur)
    if not m:
        return False
    return int(m.group(1) or 0) * 60 + int(m.group(2) or 0) <= 180


def _fmt(iso: str) -> str:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(JST).strftime("%m/%d %H:%M")


def print_hypotheses() -> None:
    """検証していない前提と、その期限を毎回出す。

    **推測は、期限を切らないと永久に推測のまま残る。** JOURNAL に書くだけでは
    読み飛ばされるので、状態を見るたびに目に入る場所に出す。
    期限を過ぎたものは目立たせる。そこで必ず判定させる。
    """
    import yaml

    path = Path(__file__).resolve().parent.parent / "config" / "hypotheses.yaml"
    if not path.exists():
        return
    items = yaml.safe_load(path.read_text(encoding="utf-8")).get("hypotheses", [])
    if not items:
        return

    today = datetime.now(JST).date()

    # **判定済みのものを「まだ検証していない」に混ぜない。**
    # `verdict` が書かれた時点でその問いは終わっている。混ぜると、
    # 期限切れの表示が毎回出続けて**本当に期限が来たものが埋もれる。**
    open_, judged = [], []
    for h in items:
        (judged if h.get("verdict") else open_).append(h)

    print("\n=== まだ検証していない前提 ===")
    if not open_:
        print("  （ありません）")
    for h in open_:
        try:
            due = datetime.strptime(str(h["deadline"]), "%Y-%m-%d").date()
            left = (due - today).days
            mark = ("[!] 期限切れ" if left < 0
                    else "[!] 今日が期限" if left == 0 else f"あと{left}日")
        except (KeyError, ValueError):
            left, mark = 0, "[!] 期限が読めない"
        print(f"  {mark}  {h.get('claim', '(claim なし)')}")
        # **鍵が欠けても落とさない。** 2026-08-08、判定を書いたときに
        # `falsified_if` を消してしまい、status.py 全体が
        # KeyError で止まった。**状態を見る道具が、状態のせいで死んではいけない。**
        cond = h.get("falsified_if")
        print(f"        外れとみなす条件: {cond}" if cond
              else "        [!] 外れとみなす条件が書かれていません。**書くこと。**")
        if left <= 0:
            print("        → いま判定すること。外れていたら次を順に試す:")
            for nxt in h.get("next_if_false", []):
                print(f"           - {nxt}")

    if judged:
        print(f"\n  判定済み {len(judged)}件（config/hypotheses.yaml の verdict）")



# 使用量の正本。**実メーターを読んでいる唯一の場所**（2026-08-08）。
# チェックアウトが無ければ GitHub 経由で `state/claude-usage.json` を読む。
USAGE_REPO = Path("/workspace/-chatgpt-usage-monitorprivate")
# 使用量がこれより古かったら取り直す（時間）。向こうの Actions は毎時なので、
# **pull だけでは最大1時間古い。** 5時間枠は数時間で 29%→77% と動くので、
# 30分を超えたら判断に効く。
STALE_USAGE_HOURS = 0.5


def _print_real_usage() -> bool:
    """**本物の使用量**を出す。出せたら True。

    `-chatgpt-usage-monitorPrivate` が Anthropic の OAuth usage を実際に叩いて
    `state/claude-usage.json` に保存している。**これが正本。**

    **`scripts/usage.py` は枠の判断に使えない。** 見ている範囲が違うため。

        実メーター … **アカウント全体**（別セッションの消費も含む）
        usage.py  … **このコンテナのセッション記録**だけ

    2026-08-08、換算が「今週0.8%」のとき実メーターは26%だった。
    最初これを「換算が30倍外れている」と書いたが**誤り**で、
    オーナーの指摘どおり**別セッションが動いていたぶん**だった。

    **枠はアカウント単位で効く。** 自分のぶんだけ数えても残量は分からない。
    """
    import json
    import subprocess

    # **読む前に取り直す。** 2026-08-09 まで、ここはローカルのクローンを
    # そのまま読んでいた。**更新しているのは向こうの GitHub Actions**（毎時22分）で、
    # こちらが `git pull` しない限りローカルは古いまま。
    # 「実測」と書いてあるのに何時間も前の値を出していた。
    # `show-usage.mjs` も同じで、**表示するだけで取り直さない**（8/8 に確認）。
    try:
        subprocess.run(["git", "-C", str(USAGE_REPO), "pull", "-q", "--ff-only"],
                       capture_output=True, text=True, timeout=120)
    except Exception:
        pass                          # 取り直せなくても、あるものを読む

    path = USAGE_REPO / "state" / "claude-usage.json"
    if not path.exists():
        return False
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        fetched = datetime.fromisoformat(d["fetched_at"].replace("Z", "+00:00")).astimezone(JST)
        windows = d["quota_windows"]
    except Exception as exc:
        print(f"  使用量の正本が読めません: {str(exc)[:60]}")
        return False

    age = (datetime.now(JST) - fetched).total_seconds() / 3600
    print(f"  **実測（{fetched:%m/%d %H:%M} 時点"
          f"{'／%.0f時間前' % age if age >= 1 else '／さきほど'}）**")
    for w in windows:
        hrs = (datetime.fromisoformat(w["resets_at_iso"].replace("Z", "+00:00")).astimezone(JST)
               - datetime.now(JST)).total_seconds() / 3600
        print(f"    {w['window_name']}: **{w['used_percent']}% 使用"
              f"（残り {w['remaining_percent']}%）**"
              f"／リセットまで {hrs:.0f} 時間")
    gov = d.get("governing_window") or {}
    if gov.get("remaining_percent") is not None:
        print(f"  **いま効いている枠: {gov.get('window_name')} "
              f"／残り {gov['remaining_percent']}%**")
    # **pull しても、向こうの毎時更新より新しくはならない。**
    # 5時間枠は数時間で 29%→77% と動くので、1時間の遅れは判断に効く。
    # 本当に「いまの値」が要るときは workflow_dispatch を投げる（約1分で反映）。
    # 2026-08-09 に実測: dispatch → 1分後にコミット → pull で最新になった。
    #
    # **この判定はスクリプトからは叩けない**（資格情報は GitHub の secret 側にあり、
    # ローカルで `read-claude-usage.mjs` を実行すると token_missing で落ちる）。
    # MCP を持っているのは呼び出し側なので、ここでは指示を出すだけ。
    if age > STALE_USAGE_HOURS:
        print(f"    [!] {age * 60:.0f}分前の値です。**取り直してください:**")
        print("        mcp__github__actions_run_trigger / run_workflow")
        print("        owner=bachikoljunior-blip repo=-chatgpt-usage-monitorPrivate")
        print("        workflow_id=claude-usage-monitor.yml ref=main")
        print("        → 約1分で反映。もう一度 status.py を実行する")
    return True


def print_budget() -> None:
    """使用量を出す。**正本は実メーターだけ。**

    2026-08-08 に恒久指示が変わり、**予算制限は無くなった**（A15）。
    「どちらの使用量もチャットgptsparkの使用量も全てあなたが使っていい」。
    だから**残量は「使い切りそうか」を見るためだけ**に読む。絞る理由にはしない。

    **`scripts/usage.py` の換算はここから外した。** あれが数えているのは
    **このコンテナのセッション記録だけ**で、枠はアカウント単位で効く。
    別セッションが動けば、自分のぶんが少なくても枠は減る。
    並べて出すと、どちらを信じるか迷う分だけ判断が鈍る。**正本だけ出す。**
    """
    print("\n=== 使用量（実メーター）===")
    if not _print_real_usage():
        return
    print("  **全部使ってよい**（恒久指示 A15）。残すこと自体に価値は無い。")
    print("  絞る理由にしないこと。使い切りそうなときだけ、短く切る。")


def print_means() -> None:
    """**手段の台帳（docs/MEANS.md）の未着手を毎回出す。**

    2026-08-09、オーナーに「あらゆる手段を使ってが効いていない」と指摘された。
    確かめると `config/hypotheses.yaml` の9件が**全部「ショートの改善」**で、
    **乗り物そのものを問うものが1つも無かった。**

    つまりループが「いまの機械を磨く」ことしかできない形になっていた。
    A13 は文書にあっても、**実行に移す仕組みが無ければ効かない。**
    だからここで毎回、未着手の手段を目に入れる。
    """
    path = Path(__file__).resolve().parent.parent / "docs" / "MEANS.md"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    # 「### M1. 名前」と、その節の「- **状態**: ...」を拾う
    import re

    entries = re.findall(r"^### (M\d+)\. (.+?)$\n(.*?)(?=^### |\Z)",
                         text, re.M | re.S)
    untried = []
    for code, name, body in entries:
        m = re.search(r"\*\*状態\*\*: (.+)", body)
        state = m.group(1).strip() if m else "?"
        if "未着手" in state or "未検討" in state:
            untried.append((code, name, state))
    # 棚卸しからの経過。**視界の外は、定期的に数え直さないと戻る。**
    import json as _json
    st = Path(__file__).resolve().parent.parent / "data" / "audit.json"
    if st.exists():
        try:
            d = _json.loads(st.read_text(encoding="utf-8"))
            last = datetime.fromisoformat(d["last_run"])
            days = (datetime.now(JST) - last).days
            mark = "  **[!] 7日以上たっています。走らせること**" if days >= 7 else ""
            print(f"\n=== 棚卸し（scripts/audit.py）===")
            print(f"  前回 {last:%m/%d %H:%M}（{days}日前）"
                  f" / 見つかった見落とし {d.get('last_gap_count', '?')}件{mark}")
        except Exception:
            pass
    else:
        print("\n=== 棚卸し（scripts/audit.py）===")
        print("  **一度も走らせていません。** `python scripts/audit.py`")

    print(f"\n=== 手段の台帳（docs/MEANS.md）===")
    print(f"  未着手 {len(untried)}件 / 全{len(entries)}件")
    for code, name, state in untried:
        mark = " ←★" if "見落とし" in state else ""
        print(f"    {code} {name}{mark}")
    if untried:
        print("  **目標の数字が2週間動いていないなら、いまの機械の改善ではなく")
        print("  ここから1つ選ぶこと。** それが A13 を実行に移す唯一の経路です。")
    else:
        # **0件のときに何も言わないのは、いちばん危ないふるまい。**
        #
        # 2026-08-10 に M8 へ着手して未着手が0件になったら、
        # この節が**丸ごと黙った。** 「全部やった」に見えるが、
        # 実際は**候補の出し方が尽きただけ**かもしれない。
        # そしてこの日、実際にそうだった: 7件を掛け終えて0件になった直後に
        # 疑ったら、**詰まり（WATCH=2）を直接狙う手段が1つも無かった。**
        # そこで足したのが M8。**0件は「探し終えた」の合図ではなく、
        # 「探し方が尽きた」の合図として扱うこと。**
        print("  **未着手が0件です。これは達成ではありません。**")
        print("  候補リストが短いことを疑うこと。"
              "**いま止まっている数字を1つ選び、")
        print("  それを直接動かす手段が台帳にあるかを見る。"
              "無ければ足す**（M8 はそうやって出た）。")
        print("  無いまま「全部やった」にすると、"
              "`hypotheses.yaml` が9件ぜんぶショート改善だったのと同じ壊れ方をします。")


def print_retention(top: int = 4) -> None:
    """**維持率を毎回出す。** 2026-08-09 まで一度も見ていなかった。

    `averageViewPercentage` は `fetch_report` が**ずっと取っていたのに、
    どこにも表示していなかった。** そのため「平均視聴率51〜102%で最後まで
    見られている＝動画の問題ではない」という **8/7 時点の数字にもとづく判断を、
    何日も持ち越していた。** 実際にはいまの主力は約30%まで落ちている。

    **取っているのに見ていない数字は、無いのと同じどころか害になる。**
    古い結論が更新されないまま生き残るため。だから毎回出す。
    """
    print("\n=== 視聴の維持（相対 0.5 が同種の動画の中央値）===")
    try:
        from src.analytics import fetch_report, fetch_retention

        rows = [r for r in fetch_report(28) if r.get("views", 0) >= 100][:top]
        if not rows:
            print("  100再生を超えた動画がまだありません")
            return
        for r in rows:
            curve = fetch_retention(r["video"])
            title = r["title"][:22]
            avg = r.get("averageViewPercentage", 0)
            if not curve:
                print(f"  {title:<22} {r['views']:>5}再生  平均{avg:5.1f}%"
                      f"  共有{r.get('shares',0)} コメント{r.get('comments',0)}")
                continue
            # 冒頭・4分の1・半分の3点で十分。全部出すと読まない。
            def at(pos: float) -> tuple[float, float]:
                i = min(range(len(curve)), key=lambda k: abs(curve[k][0] - pos))
                return curve[i][1], curve[i][2]
            (w1, r1), (w25, r25), (w50, r50) = at(0.05), at(0.25), at(0.50)
            ev = r.get("engagedViews", 0)
            rate = ev / r["views"] * 100 if r.get("views") else 0
            print(f"  {title:<22} {r['views']:>5}再生  "
                  f"**engaged {rate:4.1f}%**  平均{avg:5.1f}%"
                  f"  共有{r.get('shares',0)} 高評価{r.get('likes',0)}"
                  f" コメント{r.get('comments',0)}")
            print(f"      5%地点 維持{w1:.2f} 相対{r1:.2f}"
                  f" │ 25%地点 維持{w25:.2f} 相対{r25:.2f}"
                  f" │ 50%地点 維持{w50:.2f} 相対{r50:.2f}")
    except Exception as exc:
        print(f"  読めませんでした: {str(exc)[:120]}")
    print("  **維持率と再生数は逆相関することがある**（配信が広がるほど"
          "狙いから外れた視聴者に当たる）。")
    print("  実測 8/9: 537再生で相対0.50、1506再生で相対0.25。"
          "**因果を決めつけないこと。**")
    print("  **engaged はすぐスワイプされなかった再生の割合。**")
    print("  平均視聴率は配信が広がると下がる（交絡）が、**engaged は再生数と同じ向きに動く。**")
    print("  実測 8/9: 43.9%→1263再生、11.8%→313再生。**ここが配信の駆動輪。**")
    print("  共有とコメントも配信に効くが、4,383再生に対し共有1・コメント0。")
    print("  **動画が視聴者に何も問いかけていない。**")


def print_channel_signals(days: int = 28) -> None:
    """**チャンネル日次でしか取れない指標。**

    `videosAddedToPlaylists`（保存）・`dislikes`・`redViews` は
    **`dimensions=video` では 400 になる**（2026-08-09 に確認）。
    動画べつには比べられないが、**チャンネル全体で0かどうかは分かる。**
    棚卸しが12件ぶん「使っていない」と言い続けていたのはこれらのこと。

    保存を見る理由: 8/22 の仮説（問いかけでコメントを取りにいく）を立てたとき、
    **「コメントより保存のほうが取りやすいのでは」を確かめていなかった。**
    """
    from datetime import date, timedelta

    from googleapiclient.discovery import build

    from src.auth import credentials

    print(f"\n=== チャンネル日次の信号（直近{days}日・動画べつには取れない）===")
    try:
        api = build("youtubeAnalytics", "v2", credentials=credentials(), cache_discovery=False)
        end, start = date.today(), date.today() - timedelta(days=days)
        r = api.reports().query(
            ids="channel==MINE", startDate=start.isoformat(), endDate=end.isoformat(),
            metrics="views,videosAddedToPlaylists,shares,comments,likes,dislikes,redViews",
            dimensions="day", maxResults=90,
        ).execute()
    except Exception as exc:
        print(f"  読めませんでした: {str(exc)[:120]}")
        return

    head = [h["name"] for h in r.get("columnHeaders", [])]
    rows = [dict(zip(head, x)) for x in r.get("rows", [])]
    if not rows:
        print("  データがありません")
        return
    tot = {k: sum(row[k] for row in rows) for k in head if k != "day"}
    v = tot["views"] or 1
    print(f"  再生 {tot['views']}  保存 {tot['videosAddedToPlaylists']}"
          f"  共有 {tot['shares']}  コメント {tot['comments']}"
          f"  高評価 {tot['likes']}  低評価 {tot['dislikes']}")
    print(f"  Premium 再生 {tot['redViews']}（全体の {tot['redViews'] / v:.0%}）")
    print("  **保存も共有もコメントも、ほぼ0。** 取りやすい信号がある、という話ではない。")
    print("  問いかけでコメントを取りにいく実験（8/22）は、**低いところから始まる。**")

    # **鮮度。** ここが古いと「24時間で何再生」の判定に使えない。
    last = rows[-1]["day"]
    lag = (date.today() - date.fromisoformat(last)).days
    print(f"  日次データの最終日 {last}（{lag}日前）")
    if lag >= 2:
        print("  **この表は当日ぶんを含みません。** 「24時間で〇再生」の反証条件は"
              "ここでは判定できないので、`data/views.jsonl` か動画べつの数字を使うこと。")


def print_where_watched(days: int = 28) -> None:
    """**どこで・何秒見られているか。**

    2026-08-09 にオーナーから「毎回取得できる情報の全て踏まえて分析してる?」と
    聞かれて確かめたら、**していなかった。** 棚卸しが「使っていない次元が8個」と
    出し続けていたのに、一度も中身を見ていなかった。引いたら設計に関わる事実が出た。

    **目に入らないものは無くなる。** だから毎回出す。
    """
    from datetime import date, timedelta

    from googleapiclient.discovery import build

    from src.auth import credentials

    print(f"\n=== どこで・何秒見られているか（直近{days}日）===")
    try:
        api = build("youtubeAnalytics", "v2", credentials=credentials(), cache_discovery=False)
        end, start = date.today(), date.today() - timedelta(days=days)

        def pull(dim):
            r = api.reports().query(
                ids="channel==MINE", startDate=start.isoformat(), endDate=end.isoformat(),
                metrics="views,estimatedMinutesWatched", dimensions=dim,
                sort="-views", maxResults=10,
            ).execute()
            return r.get("rows", [])
    except Exception as exc:
        print(f"  読めませんでした: {str(exc)[:120]}")
        return

    try:
        loc = pull("insightPlaybackLocationType")
        total_v = sum(x[1] for x in loc) or 1
        shorts = next((x[1] for x in loc if x[0] == "SHORTS_FEED"), 0)
        watch = next((x[1] for x in loc if x[0] == "WATCH"), 0)
        print(f"  再生場所: SHORTS_FEED {shorts}（{shorts / total_v:.1%}） / WATCH {watch}")
        if watch < total_v * 0.05:
            print("  **視聴ページにはほぼ誰も来ていない。**")
            print("  説明欄・目次・裏取りの手順・再生リストは**ほぼ読まれていない。**")
            print("  長尺（M4）はこの WATCH をゼロから作る賭けだと理解すること。")

        # **1再生あたりの秒数は、API が直接返すものを使う。**
        # 2026-08-09、`estimatedMinutesWatched ÷ views` で 8.5秒と出して
        # 「大半が1〜2枚で離れている」と報告した。**誤り。**
        # 同じ期間で API の `averageViewDuration` は **22秒**。
        # 627分 × 60 ÷ 4432 = 8.5 だが、views × 22秒 = 1,625分 で**合わない**
        # （`estimatedMinutesWatched` は総視聴時間そのものではない）。
        # **直接その問いに答える指標があるのに、割り算で別の数字を作っていた。**
        dev = pull("deviceType")
        print("  端末べつ:")
        for name, v, m in dev:
            print(f"    {name:9} {v:>5}再生")

        r = api.reports().query(
            ids="channel==MINE", startDate=start.isoformat(), endDate=end.isoformat(),
            metrics="views,averageViewDuration,averageViewPercentage",
        ).execute()
        head = [h["name"] for h in r.get("columnHeaders", [])]
        d = dict(zip(head, r.get("rows", [[0, 0, 0]])[0]))
        print(f"  **1再生あたり {d['averageViewDuration']}秒"
              f"（尺の {d['averageViewPercentage']:.0f}%）**  ← API の averageViewDuration")
        print("  **`estimatedMinutesWatched ÷ 再生数` で出さないこと。**"
              "2.6倍ずれる（8/9 に間違えた）。")
    except Exception as exc:
        print(f"  途中で読めませんでした: {str(exc)[:120]}")


def main(days: int = 7) -> int:
    youtube = _service()
    channel = youtube.channels().list(part="snippet,contentDetails,statistics", mine=True).execute()["items"][0]
    stats = channel["statistics"]

    print(f"=== {channel['snippet']['title']} ===")
    print(f"登録者 {stats.get('subscriberCount', '?')}人")
    print(
        f"チャンネル総再生 {stats.get('viewCount', '?')}回"
        "  ← 前身の動画も含む。こちらの成果ではない。下の動画ごとの数字で見ること\n"
    )

    uploads = channel["contentDetails"]["relatedPlaylists"]["uploads"]
    items = youtube.playlistItems().list(part="contentDetails", playlistId=uploads, maxResults=50).execute()
    ids = [i["contentDetails"]["videoId"] for i in items.get("items", [])]
    if not ids:
        print("動画がありません")
        return 0

    videos = youtube.videos().list(
        part="snippet,status,statistics,contentDetails", id=",".join(ids)
    ).execute()["items"]

    now = datetime.now(timezone.utc)
    ours = 0
    stranded: list[str] = []
    scheduled: list[str] = []
    short_days: set[str] = set()      # ショートが予約されている日（MM/DD）

    print(f"{'ID':13s} {'状態':16s} {'尺':>7s} {'再生':>5s} {'高評価':>4s}  題")
    for v in videos:
        st, sn = v["status"], v["snippet"]
        vs = v["statistics"]
        views = int(vs.get("viewCount", 0))
        ours += views

        publish_at = st.get("publishAt")
        if st["privacyStatus"] == "public":
            state = f"公開 {_fmt(sn['publishedAt'])}"
        elif publish_at:
            hours = (datetime.fromisoformat(publish_at.replace("Z", "+00:00")) - now).total_seconds() / 3600
            state = f"予約 {_fmt(publish_at)}"
            scheduled.append(f"{v['id']} {_fmt(publish_at)}（あと{hours:.1f}時間）")
            if _is_short(v):
                short_days.add(_fmt(publish_at).split()[0])
        else:
            state = f"{st['privacyStatus']} 予約なし"
            stranded.append(f"{v['id']} {sn['title'][:34]}")

        dur = v["contentDetails"]["duration"].replace("PT", "").lower()
        print(f"{v['id']:13s} {state:16s} {dur:>7s} {views:5d} {vs.get('likeCount', 0):>4s}  {sn['title'][:34]}")

    print(f"\nこちらの動画の再生 合計 {ours}回（{len(videos)}本）")

    # **公開後の伸び方を毎回残す。** 総再生数だけ見ていると、当たり外れが
    # 決まる最初の数時間が抜ける（2026-08-06）。人が思い出す前提にしない。
    try:
        from snapshot import print_curves, record
        record(videos)
        print_curves([v["id"] for v in videos],
                     {v["id"]: v["snippet"]["title"] for v in videos})
    except Exception as exc:
        print(f"  伸び方を記録できませんでした: {str(exc)[:70]}")

    if scheduled:
        print("\n[予約中]")
        for s in scheduled:
            print("  " + s)

    # 予約が埋まっていない日を出す。**背後の生成はコンテナ再起動で消える**ので、
    # 「走らせたはず」は当てにならない。実際に 8/7 が空になっていたのを見落としかけた。
    # 投稿が途切れるのが最大の損失なので、空きは目立たせる。
    # **日付だけ見てはいけない。形式ごとに見る。**
    # 2026-08-05、8/6 と 8/7 は「予約あり」と出ていたが、どちらも長尺だった。
    # 長尺は4本すべて0〜1回で、**露出が出ているのはショートだけ。**
    # 「予約が入っている日」を空きでないと数えたせいで、唯一効いている形式が
    # 翌日から途切れる状態を見落としかけた。**効いている形式で数える。**
    gaps = []
    for ahead in range(1, LOOKAHEAD_DAYS + 1):
        day = (datetime.now(JST) + timedelta(days=ahead)).strftime("%m/%d")
        if day not in short_days:
            gaps.append(day)
    if gaps:
        print(f"\n[!] **ショート**の予約が入っていない日: {', '.join(gaps)}")
        print("    投稿が途切れるのが最大の損失。生成を撃ち直すこと。")
        print("    長尺が入っていても空きとみなす。露出が出ているのはショートだけだから。")
        print("    背後の生成はコンテナ再起動で消えるので、ログが残っていてもプロセスは死んでいる。")

    # **意図して伏せたものは警告しない。** 毎回鳴る警告は無視されるようになり、
    # 本当に予約し忘れたときに効かなくなる（2026-08-05）。理由は withheld.yaml に。
    withheld = {}
    wpath = Path(__file__).resolve().parent.parent / "config" / "withheld.yaml"
    if wpath.exists():
        import yaml
        withheld = {w["id"]: w.get("why", "") for w in
                    (yaml.safe_load(wpath.read_text(encoding="utf-8")) or {}).get("withheld", [])}

    unexpected = [s for s in stranded if s.split()[0] not in withheld]
    if unexpected:
        print("\n[!] 公開されないまま止まっている動画があります:")
        for s in unexpected:
            print("  " + s)
        print("  予約し忘れならこのまま永久に出ません。意図的なら config/withheld.yaml に理由ごと書くこと。")
    on_purpose = [s for s in stranded if s.split()[0] in withheld]
    if on_purpose:
        print(f"\n（意図して伏せている動画 {len(on_purpose)}本。理由は config/withheld.yaml）")

    # 流入経路。表示されているのかどうかが、他の全部の前提になる。
    print(f"\n=== 流入経路（直近{days}日） ===")
    try:
        from src.analytics import fetch_traffic

        rows = fetch_traffic(days)
        if not rows or sum(r.get("views", 0) for r in rows) == 0:
            print("  まだ数字が返りません（Analytics は当日ぶんが遅れます）")
        for r in rows:
            print(f"  {r.get('insightTrafficSourceType', '?'):18s} 再生{r.get('views', 0):5d}"
                  f"  視聴{r.get('estimatedMinutesWatched', 0):5d}分")
    except Exception as exc:
        print(f"  読めませんでした: {str(exc)[:120]}")

    print_retention()
    print_channel_signals()
    print_where_watched()
    # **取れるものを全部引いて、前回との差を出す。**
    # ここを「毎回」にしたのが要点。手で選んでいる限り、選ばなかったものは
    # 永久に視界に入らない（2026-08-09、8次元を何日も見落としていた）。
    try:
        from src import scan as _scan
        _snap = _scan.collect()
        _scan.report(_snap, _scan._previous())
        _scan.save(_snap)
    except Exception as exc:                 # 走査が落ちても状態表示は続ける
        print(f"\n=== 全走査 ===\n  [!] 走査に失敗: {str(exc)[:150]}")
        print("      **これを放置しないこと。** 落ちている間は見落としが数えられない")
    print_means()
    print_hypotheses()
    print_budget()

    # 収益化の門。律速がどちらかを毎回見せる（docs/GOAL.md の掛け算）。
    def _short_median() -> float | None:
        """公開済みショート1本あたりの再生（中央値）。

        **28日窓で割らないこと。** この中身を出し始めたのは 8/4 で、
        前の22日はほぼ0。28で割ると1日173再生になり、**実際の4分の1**に見える。
        到達速度は「1日1本 × 1本あたり」で測る。
        """
        try:
            from src import scan as _s

            v = (_s._previous() or {}).get("values", {})
            rows: dict[str, dict] = {}
            for k, x in v.items():
                if k.startswith("動画.") and k.count(".") >= 2:
                    _, vid, m = k.split(".", 2)
                    rows.setdefault(vid, {})[m] = x
            ns = sorted(r["views"] for r in rows.values()
                        if r.get("views", 0) >= 30 and (r.get("尺") or 0) <= 180)
            if not ns:
                return None
            h = len(ns) // 2
            return ns[h] if len(ns) % 2 else (ns[h - 1] + ns[h]) / 2
        except Exception:
            return None


    subs = int(stats.get("subscriberCount", 0) or 0)
    print("\n=== 収益化の門まで ===")
    print(f"  登録者     {subs:6d} / 1000   あと {max(0, 1000 - subs)}人")

    # **仮定の登録率で割らないこと。実測がある。**
    #
    # 2026-08-10 まで、ここは「登録率0.3%なら1000人は約33万再生」と出していた。
    # **0.3% はどこから来たのか誰も知らない数字で、実測は 14分の1 だった。**
    # 到達できるかを決める掛け算なので、仮定で置いてよい場所ではない。
    #
    # 1件しか起きていないので点推定は当てにならない。**上振れ側も出す**
    # （ポアソンで1件観測の95%上限はおよそ4.7件ぶん）。**楽観側で見ても届くか**
    # を毎回見るためで、悲観側を強調するためではない。
    try:
        from src import scan as _scan

        vals = (_scan._previous() or {}).get("values", {})
        gained = vals.get("合計.subscribersGained")
        views = vals.get("合計.views")
        if gained is not None and views:
            rate = gained / views
            hi = 4.744 / views                       # 1件観測の楽観側
            print(f"  **実測の登録率 {rate * 100:.3f}%**"
                  f"（{gained}人 / {views}再生。**仮定ではない**）")
            need = int((1000 - subs) / rate) if rate else None
            need_hi = int((1000 - subs) / hi) if hi else None
            if need:
                print(f"    あと1000人に必要な再生: **{need / 10000:.0f}万**"
                      f"（楽観側 {need_hi / 10000:.0f}万）")
            # **4000時間の門を、チャンネル合計の視聴時間で割らないこと。**
            #
            # 一度そう書いて、すぐ消した。2つ間違っている。
            #
            # 1. **ショートの視聴時間は4000時間に数えない。** 再生の99.95%が
            #    ショートのフィード内なので、合計で割ると**数えない時間で門を
            #    通る絵**が出る（174万再生で届く、と出た。届かない）
            # 2. `estimatedMinutesWatched ÷ 再生数` は `averageViewDuration` と
            #    2.6倍ずれる（走査の罠に書いてある）。**割って作らないこと**
            #
            # なので長尺だけで測る。ショート側は別の門（90日で1000万再生）。
            longs = {}
            for k, v in vals.items():
                if k.startswith("動画.") and k.count(".") >= 2:
                    _, vid, m = k.split(".", 2)
                    longs.setdefault(vid, {})[m] = v
            lf = [r for r in longs.values() if (r.get("尺") or 0) > 180]
            lf_views = sum(r.get("views", 0) for r in lf)
            lf_sec = sum(r.get("views", 0) * (r.get("averageViewDuration") or 0)
                         for r in lf)
            print(f"  長尺の視聴時間 **{lf_sec / 3600:.2f}時間** / 4000時間"
                  f"（長尺 {len(lf)}本・{lf_views}再生。"
                  "**ショートの視聴時間はこの門に数えません**）")
            if lf_views and lf_sec:
                per = lf_sec / lf_views
                print(f"    あと4000時間に必要な長尺の再生: "
                      f"**{int(4000 * 3600 / per) / 10000:.0f}万**"
                      f"（実測 1再生 {per:.0f}秒。**n={lf_views}**）")
            # **門の形を毎回書く。** 「どちらか一方」が登録者にも掛かると
            # 読めてしまうので、掛け算の形のまま出す。
            print("  門の形: **登録者1000人 かつ（4000時間 または"
                  " 90日で1000万ショート再生）**。**登録者は迂回できません**")
            print("  **この2つが数百万再生を指しているなら、"
                  "1本ずつ良くする道では届きません**（`docs/MEANS.md` を見ること）")

            # **門の先を掛ける。2026-08-10 まで一度もやっていなかった。**
            #
            # ここはずっと「門まであと何再生か」しか出していなかった。
            # **門を通ったあといくらになるのかを、誰も掛けていない。**
            # `docs/STRATEGY.md` はショートの RPM を ¥50〜150 と最初から
            # 書いていて、2026-08-04 に「収益化前は RPM の比較に意味がない」と
            # 正しく注記してある。**注記はそこで止まり、門の先に進まなかった。**
            #
            # 掛けたら **月990〜2,970円**。門が無料で消えても、この機械は
            # 月1000円台しか作らない。**20万には67〜202倍足りない。**
            # 長尺なら同じ20万円が月10〜25万再生で作れる（**40倍の差**）。
            #
            # **「門さえ通れば」という言い方をこれ以上させないための3行。**
            SHORT_RPM, LONG_RPM = (50, 150), (800, 2000)
            per = _short_median()
            if per:
                mv = per * 30                    # 1日1本
                lo, hi = (mv / 1000 * r for r in SHORT_RPM)
                print(f"\n  **門を無料で通れたとして、いまの収入: "
                      f"月 ¥{lo:,.0f}〜¥{hi:,.0f}**"
                      f"（ショート1日1本 {mv / 10000:.1f}万再生 × RPM ¥50〜150）")
                print(f"    20万に要るショート再生 "
                      f"**{200000 / SHORT_RPM[1] * 1000 / 10000:.0f}万〜"
                      f"{200000 / SHORT_RPM[0] * 1000 / 10000:.0f}万/月"
                      f"（いまの {200000 / hi:.0f}〜{200000 / lo:.0f}倍）**")
                print(f"    長尺なら同じ20万円が "
                      f"**月{200000 / LONG_RPM[1] * 1000 / 10000:.0f}〜"
                      f"{200000 / LONG_RPM[0] * 1000 / 10000:.0f}万再生**"
                      f"（RPM ¥800〜2000）。**要る再生数が40倍ちがう**")
                print("  **ショートは収入源ではありません。**登録者を取る道具です"
                      "（そちらも実測 0.021% で足りていない）")
    except Exception as exc:
        print(f"  [!] 実測の登録率が出せません: {str(exc)[:120]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 7))
