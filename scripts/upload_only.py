"""検査済みの build/<テーマID>/ を、作り直さずにそのまま投稿する。

    python scripts/upload_only.py <テーマID>
    python scripts/upload_only.py <テーマID> "" <時刻>   # 第3引数で予約
    python scripts/upload_only.py <テーマID> --draft     # **予約を付けずに private で上げる**
    python scripts/upload_only.py <テーマID> --draft --replaces <videoId>[,<videoId>…]
                                                        # **焼き直し（規則3）。差し替える下書きを外す**
                                                        # （同じ題材の下書きが何本 残っていても、全部 名指しで外せる）

**`--draft` は 2026-09-02 に足しました**（規則5・固定その4）。オーナー原文:

    「その日の投稿の後は次の日の作成になるってわかってるよな？」
    「現在の日付にしか予約しないってことだからね？」

＝ **作るのは前の日の公開直後から。予約だけが当日。**
それまで、この道具には「上げるが予約しない」道が1本もありませんでした
（`--skip-upload` は上げないので、**コンテナと一緒に消えます**）。
`--draft` で上げた本は private のまま残り、その日になったら
`python scripts/reschedule.py --move <videoId> <時刻>` で予約します。
**`videos.insert` は日枠を使わないので、403 の窓でも通ります。**

なぜ要るか。--dry-run で作った final.mp4 は、本番投稿するものと完全に同一で、
verify も通っている。それをもう一度パイプラインに通すと、音声合成と38枚の
レンダリングでまた30分かかる。中身は1バイトも変わらないので、待つ意味がない。

投稿前に、タイトル・説明欄・最初のコメントにリポジトリへの言及が無いことを
確認する。ここは動画に出してはいけない（CLAUDE.md 参照）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import critique_queue  # noqa: E402  scripts/ 直下。独立評価の材料を残す

from src import bars, config, uploader  # noqa: E402

# 動画に出してはいけない語。オーナーの指示でリポジトリの存在を伏せている。
FORBIDDEN = ("github", "GitHub", "リポジトリ", "コードを公開", "ソースコード")


def split_when(when: str) -> tuple[int, int, str | None]:
    """予約時刻の指定を `(時, 分, 日付 or None)` に分ける。

        "9"                  → (9, 0, None)           最初に空いている日の 09:00
        "9:30"               → (9, 30, None)          同じく 09:30
        "2026-08-24@10"      → (10, 0, "2026-08-24")  **その日に釘づけ**
        "2026-08-24@10:30"   → (10, 30, "2026-08-24")

    日付を釘づけできないと「1日にN本」が作れません（`src/uploader.py`
    `next_publish_at` の docstring）。M14 の 8 の段はこれが無くて止まっていました。

    **分を足したのは 2026-08-18 です。** `next_publish_at` は最初から
    `minute_jst` を受け取るのに、**ここが時しか渡していませんでした。**
    そのぶん1日に置ける枠が11個で止まり（9〜19時）、投稿の本数枠 92本に対して
    **8倍以上足りていません**でした（`batch_build.slots` の `step_min`）。
    """
    text = when.strip()
    date_part: str | None = None
    if "@" in text:
        date_part, _, text = text.partition("@")
    hour_part, _, minute_part = text.partition(":")
    minute = int(minute_part) if minute_part else 0
    if not 0 <= minute <= 59:
        raise ValueError(f"分は 0〜59 で渡すこと: {when!r}")
    return int(hour_part), minute, date_part


def drop_replaced(existing: list[dict], video_id: str) -> tuple[list[dict], str]:
    """**差し替える1本を、重なりの突き合わせから外す。**（2026-09-02 に足した）

    返すのは `(外したあとの一覧, 断る理由)`。理由が空でなければ**外しません**。

    ## なぜ要るか（この回に実際に止められた）

    オーナーが固定した規則3 は「**次の枠で出る1本を、出る瞬間まで良くし続ける**」で、
    その1手は `docs/trigger_main.md` §4 が名指ししているとおり **焼き直し**です
    （`python -m src.pipeline` → `upload_only.py <題材> --draft`）。

    ところが焼き直した本は、**外そうとしているその下書きと必ず同じ題材**です。
    `src/dupes.find()` の `same-topic` は**強い**重なりなので、
    `upload_only.py` は投稿を中止します —— **規則3 の1手が、門で塞がっていました。**

        [same-topic] テーマID `gassan-kaigo-alone-155` が同じ
            これから: 介護の月額上限2万4600円は年間限度額19万円の何割か
            既にある: MqQKSnbM0OI  介護の月額上限2万4600円で年間限度額の何割が埋まるか

    **`--allow-dupe` では代わりになりません。** あれは門を**丸ごと**降ろすので、
    同じ回に `same-yen`（別の題材で金額が入れ子）まで通ります。
    規則3 は 1日1回ではなく**出る瞬間まで**なので、
    「毎回 `--allow-dupe` を撃って JOURNAL に理由を書く」は
    **人の記憶に依存する門**（`batch_build.slots()` の註）——
    このリポジトリで毎回 落ちる側です。

    ## 外してよい条件（**この2つだけ**。片方でも欠けたら断ります）

        private であること      公開の並びに入っていない
        予約が付いていないこと  `publishAt` が無い ＝ 出る予定がない

    **この2つが揃った本は「視聴者から見て存在しない」**ので、
    門が守っている「同じチャンネルの動画を続けて数本視聴したときの繰り返し」に
    そもそも当たりません。逆に**予約済みを外すのは禁じます** ——
    2026-08-16 にすり抜けた `iTrogWVf4Eg` が、まさに**予約済み**の本でした
    （`same-topic` を5分の間に止めて、そのあと通した回）。
    外したいなら `scripts/reschedule.py --unschedule` が先です。

    **覆る条件**: 規則5（`src/house_rule.SAME_DAY_SCHEDULING_ONLY`）が外れて
    下書きを何本も持てるようになったら、「private・予約なし」だけでは
    足りなくなります（同じ題材の下書きが2本 並ぶ）。
    そのときは題材ではなく**その1本を名指しした札**であることを、
    `data/uploaded.jsonl` の側でも突き合わせること。
    """
    hit = [v for v in existing if v.get("id") == video_id]
    if not hit:
        return existing, f"その本が突き合わせの一覧にありません（{video_id}）"
    v = hit[0]
    st = v.get("status", {}) or {}
    if st.get("privacyStatus") != "private":
        return existing, f"private ではありません（{st.get('privacyStatus')}）"
    if st.get("publishAt"):
        return existing, f"予約が付いています（{st.get('publishAt')}）"
    return [x for x in existing if x.get("id") != video_id], ""


def main(topic: str, visibility: str | None = None, hour: int | None = None,
         date_jst: str | None = None, skip_dupe_check: bool = False,
         minute: int | None = None, draft: bool = False,
         replaces: str | None = None) -> int:
    """hour を渡すと、その時刻（JST）で予約する。
    date_jst（`YYYY-MM-DD`）も渡すと、**その日に釘づけ**する（埋まっていれば失敗）。

    **ショートは朝のほうが強い**（2026-08-05 の実測）。09:21 公開の1本が1245回、
    18:29〜19:55 に固めて出した5本が最良で558回・後発3本は0回。
    `config/channel.yaml` の 19:00 は長尺（視聴ピーク）に合わせた値なので、
    ショートはここで上書きする。**まだ n=1 なので、時刻の効果と本数の効果は
    分離できていない。** 毎日1本を続けて確かめること。
    """
    work = Path("build") / topic
    if not (work / "final.mp4").exists():
        print(f"{work}/final.mp4 がありません。先に --dry-run で作ってください")
        return 1

    script = json.loads((work / "script.json").read_text(encoding="utf-8"))
    # title.txt は人が見る用で、A/Bテストの別案まで書いてある。
    # そのまま投稿タイトルにすると別案ごと出てしまうので、script.json を使う。
    title = script["title"].strip()
    description = (work / "description.txt").read_text(encoding="utf-8")
    channel = config.load_channel()
    if visibility:
        # ショートは即時公開のほうがフィード配信に乗りやすく、数字も早く取れる。
        # 予約公開は private のときしか効かないので、public を指定したら即時になる。
        channel["publish"] = dict(channel["publish"])
        channel["publish"]["visibility"] = visibility
        print(f"[check] 公開設定を {visibility} で上書き")
    if hour is not None:
        channel["publish"] = dict(channel["publish"])
        channel["publish"]["publish_hour_jst"] = hour
    if minute is not None:
        # **時と別に上書きすること。** `channel.yaml` の既定は :00 なので、
        # 分だけ渡された回（`"9:30"`）でここを飛ばすと、黙って :00 に戻ります。
        channel["publish"] = dict(channel["publish"])
        channel["publish"]["publish_minute_jst"] = minute
        print(f"[check] 予約時刻を {hour}:00 JST で上書き")
    if date_jst:
        channel["publish"] = dict(channel["publish"])
        channel["publish"]["publish_date_jst"] = date_jst
        print(f"[check] 予約日を {date_jst} に釘づけ（埋まっていれば翌日へ送らず失敗）")
    if draft:
        # **予約を付けずに上げる**（規則5・固定その4）。`src/uploader.upload()` の註。
        # 前の日に作った1本を private のまま置き、**その日になってから**予約します。
        channel["publish"] = dict(channel["publish"])
        channel["publish"]["visibility"] = "private"
        channel["publish"]["draft"] = True
        channel["publish"].pop("publish_date_jst", None)
        print("[check] **下書き（予約なし）で上げます** —— "
              "その日になったら `scripts/reschedule.py --move` で予約すること")

    if "[t:" not in description:
        print("説明欄にテーマ印がありません。投稿済みの記録が残らないので中止します")
        return 1
    for field, text in (
        ("タイトル", title),
        ("説明欄", description),
        ("最初のコメント", script.get("first_comment", "")),
    ):
        for word in FORBIDDEN:
            if word in text:
                print(f"{field}に「{word}」が入っています。投稿を中止します")
                return 1
    print("[check] リポジトリへの言及なし")

    # **自分で作った「繰り返し」を、公開される前に止める**（2026-08-16 に足した）。
    # ここに置くのは、**予約がこの1か所しか通らない**からです。生成の段に置くと、
    # 手で `--dry-run` してから上げる道が素通りします（`src/verify.py` と同じ考え）。
    #
    # 8/15 23:0x は「同じテーマIDが2本」を直しましたが、**それでは足りません。**
    # 8/16 に実物76本を突き合わせると、**テーマIDが違うのに同じ金額**の組が
    # 予約の中に4本残っていました（`35万9318円` `61万9千円` `136万円` `足切り8万円`）。
    # 見ているのは題の数字なので、**calc も台本も別でも、答えが同じなら鳴ります。**
    # **`--replaces` の ID は門の外でも要ります**（下の `[pick]`・決めの写し）。
    replaced_ids = [x.strip() for x in (replaces or "").split(",") if x.strip()]
    if not skip_dupe_check:
        try:
            from src import dupes, history
            svc = uploader._service()
            ch = svc.channels().list(part="contentDetails", mine=True).execute()["items"][0]
            ids = history.channel_video_ids(
                svc, ch["contentDetails"]["relatedPlaylists"]["uploads"])
            existing: list[dict] = []
            for i in range(0, len(ids), 50):
                existing += svc.videos().list(
                    part="snippet,status", id=",".join(ids[i:i + 50])).execute()["items"]
            # **手元の控えに載っているが、口から返らなかった本を引き直す。**
            # 2026-08-16 に、まさにここがすり抜けました —— 同じ `s-fukugyo-2` を
            # 5分の間に**止めて、そのあと通して**います。落ちていたのは
            # `iTrogWVf4Eg`（8/22 予約済み・実在）で、uploads プレイリストが
            # 落とし、search は当日の API 枠を使い切って 429 でした（`src/dupes.py`）。
            # **消した本で誤って止めないよう、生きているものだけを足します。**
            seen_ids = {v["id"] for v in existing}
            missing = [r["id"] for r in dupes.ledger_rows() if r["id"] not in seen_ids]
            for i in range(0, len(missing), 50):
                existing += svc.videos().list(
                    part="snippet,status", id=",".join(missing[i:i + 50])).execute()["items"]
            if missing:
                print(f"[check] 口から返らなかった控え {len(missing)}本を引き直しました")
            # **`--replaces a,b` —— 下書きは1本ずつ残るので、何本でも外せること**
            # （2026-09-02 夜。同じ日の3本目の焼き直しで、「1つ前」を外しても
            # 「2つ前」の `MqQKSnbM0OI` に `same-topic` で止められました）。
            # 1本ずつ private・予約なしを確かめます。**1本でも欠けたら全部 断る。**
            for vid in replaced_ids:
                existing, why = drop_replaced(existing, vid)
                if why:
                    print(f"\n[!] **`--replaces {vid}` は使えません** —— {why}")
                    print("  外す枠があるなら `scripts/reschedule.py --unschedule` が先です。")
                    return 1
                print(f"[check] **差し替え**: {vid} を突き合わせから外しました"
                      "（private・予約なし ＝ 公開の並びに入っていない本）")
            hits = dupes.blocking(
                title, topic, existing,
                {t["id"]: t.get("calc", "") for t in config.load_topics()["topics"]},
                exclude=set(replaced_ids) or None)
            if hits:
                print("\n[!] **既にある本と強く重なります。投稿を中止します。**")
                for h in hits:
                    other = h["b"] if h["a"]["id"].startswith("＜") else h["a"]
                    print(f"  [{h['kind']}] {h['why']}")
                    print(f"      これから: {title[:44]}")
                    print(f"      既にある: {other['id']}  {other['title'][:44]}")
                print("  「同じチャンネルの動画を続けて数本視聴した後、繰り返しのように"
                      "感じられる可能性のあるコンテンツ」は**収益化の対象外**です。")
                print("  どうしても上げるなら `--allow-dupe`。**理由を JOURNAL に書くこと。**")
                return 1
            print("[check] 既存の本との強い重なりなし")
        except Exception as exc:
            # **落ちても投稿は止めない。** 途切れるほうが高い（CLAUDE.md）。
            print(f"[check] 重なりを見られませんでした（続行）: {str(exc)[:100]}")

    video_id = uploader.upload(
        work / "final.mp4",
        work / "thumbnail.jpg",
        title,
        description,
        script["tags"],
        channel["publish"],
    )
    # 公開した棒を残す。`build/` は .gitignore なので、これをやらないと
    # 次のコンテナで「同じ図」検査の比較対象がゼロになる（`src/bars.py`）。
    bars.record(topic, video_id, script)
    # **投稿は済んでいます。ここから先で落ちても動画IDを失わないこと。**
    # 先に出しておく（2026-08-15。材料を残す処理が例外を上げるようにしたため）。
    print(f"VIDEO_ID {video_id}")

    # **自分が上げたものを、自分で控える**（2026-08-16）。上の門が見る先です。
    # 口が落としても、こちらは落ちません（理由は `src/dupes.ledger_rows`）。
    try:
        from src import dupes as _dupes
        # **秒数も控える**（2026-08-25）。無いと「ショートか長尺か」を題名の
        # `#Shorts` で推測することになり、実測で4本ずれていました（`src/forms.py`）。
        # **測れなくても投稿は止めません**（途切れるほうが高い）。
        _dur = None
        try:
            from src import verify as _verify
            _dur = float(_verify._probe(work / "final.mp4")
                         .get("format", {}).get("duration") or 0) or None
        except Exception as exc:
            print(f"[dupes] 秒数を測れませんでした（続行）: {str(exc)[:60]}")
        _dupes.remember(video_id, topic, title,
                        channel["publish"].get("publish_at") or None,
                        duration_s=_dur)
    except Exception as exc:
        print(f"[dupes] **控えを残せませんでした: {str(exc)[:80]}**")

    # **差し替えたら、`[きょうの1本]` の決めも新しい ID へ写す**（2026-09-03 05:xx）。
    # 決めは ID で本を名指しし、`ahead_sweep._today_candidate` はその ID を枠へ置きます。
    # 写さないと、置かれるのは**焼き直す前の旧 ID**（`src/daily_pick.replace_video` の註）。
    if replaced_ids:
        try:
            from src import daily_pick as _pick
            _days = _pick.replace_video(replaced_ids, video_id,
                                        why_note=f"upload_only --replaces・題材 {topic}")
            if _days:
                print(f"[pick] **[きょうの1本] の決めを写しました**: {', '.join(_days)} → {video_id}"
                      f"（旧 {', '.join(replaced_ids)}）")
            else:
                print(f"[pick] [きょうの1本] に {', '.join(replaced_ids)} を名指しした決めは無い（写す物なし）")
        except Exception as exc:
            print(f"[pick] **決めを写せませんでした: {str(exc)[:100]}** —— "
                  f"`python -m src.daily_pick --pick ... --video {video_id}` で手で写すこと")

    # **contact sheet が無ければ、ここで作る**（2026-09-01 に踏んで足した）。
    #
    # `critique_queue.stash()` は `inspect.jpg` が無いと**何もせずに帰ります**
    # （あちらの docstring:「無い材料の空箱を積んでも次の回を惑わせるだけ」）。
    # **そして `--dry-run` の `src/pipeline` は contact sheet を作りません** ——
    # あれは `scripts/inspect_build.py` という別の道具です。
    #
    # つまり **`--dry-run` で焼いて `upload_only.py` で上げる道**を通ると、
    # **その本は必ず独立評価を回せません。** 2026-09-01 に実際に踏みました
    # （`ICmIBsZRYFE`。手で `inspect_build.py` を撃ち直して残しています）。
    #
    # **この道は「たまに使う抜け道」ではありません。** 日枠が尽きた窓では
    # `pipeline` の `history.posted_topic_ids()`（約25単位）が 403 になるので、
    # `--dry-run` ＋ `upload_only.py` が**唯一 通る道**です
    # （`docs/trigger_main.md`「枠が尽きている回に選ぶのは、これです」）。
    # **枠が細い日ほど、この穴に落ちます。**
    #
    # **なぜ「作れ」と言うのではなく、ここで作るのか。** 手順の側には
    # 既に3か所 書いてありました（`inspect_build` の docstring・`critique_queue`
    # の印字・`docs/CRITIQUE.md`）。**3つとも「次に来た側が覚えていること」に
    # 頼っています** —— `batch_build.slots()`:「**人の記憶と手写しに依存する門は、
    # この輪では毎回落ちる側**」。だから門を、材料を要る側へ移します。
    #
    # **落ちても投稿は止めません**（投稿はもう済んでいる）。
    #
    # **覆る条件**: `src/pipeline` が `--dry-run` でも contact sheet を焼くように
    # なったら、この段は要りません（`tests/test_upload_only_sheet.py` が
    # 「無ければ作る」を縛っているので、消すときはその検査ごと）。
    if not (work / "inspect.jpg").exists():
        print("[queue] contact sheet が無いので、ここで作ります"
              "（--dry-run の pipeline は焼きません）")
        try:
            import inspect_build                               # noqa: PLC0415
            inspect_build.main(topic)
        except Exception as exc:                               # noqa: BLE001
            print(f"[queue] contact sheet を作れませんでした（続行）: {str(exc)[:100]}")

    # 独立評価（M13）の材料も同じ理由で残す。**残さないと、投稿した回で評価を
    # 回せなかった時点で永久に評価できません**（`scripts/critique_queue.py`）。
    #
    # **投稿そのものは終わっているので、ここで止めません。** ただし黙って
    # 素通りさせると 8/15 の再発（読み上げ文が0行のまま2本積まれた）になるので、
    # **見落とせない形で出して、終了コードにも出します。**
    try:
        critique_queue.stash(topic, video_id, script, work,
                             thumbnail_set=channel["publish"].get("thumbnail_set"))
    except Exception as exc:
        print(f"[queue] **材料を残せませんでした: {exc}**")
        print("[queue] **投稿は済んでいます。** この動画は独立評価を回せません。")
        print("[queue] 公開前なら予約を外せます（docs/CRITIQUE.md）。")
        return 1

    return 0


if __name__ == "__main__":
    _argv = sys.argv[1:]
    # **重なりの門を越える札**（`src/dupes.py`）。位置引数の数を変えないよう、
    # 先に抜いておく。**使ったら理由を JOURNAL に書くこと。**
    _allow = "--allow-dupe" in _argv
    _argv = [a for a in _argv if a != "--allow-dupe"]
    # **予約を付けずに上げる札**（規則5・固定その4）。位置引数の数を変えないよう、
    # `--allow-dupe` と同じ形で先に抜きます。
    _draft = "--draft" in _argv
    _argv = [a for a in _argv if a != "--draft"]
    # **差し替える1本を名指しする札**（規則3・`drop_replaced()` の註）。
    # `--replaces <videoId>` の2語ぶんを、位置引数の数を変えないよう先に抜きます。
    _replaces: str | None = None
    if "--replaces" in _argv:
        _i = _argv.index("--replaces")
        if _i + 1 >= len(_argv):
            print("`--replaces` には差し替える videoId を続けること")
            raise SystemExit(2)
        _replaces = _argv[_i + 1]
        del _argv[_i:_i + 2]
    if len(_argv) not in (1, 2, 3):
        print(__doc__)
        raise SystemExit(2)
    _hour, _minute, _date = (None, None, None)
    if len(_argv) == 3:
        _hour, _minute, _date = split_when(_argv[2])
    raise SystemExit(main(
        _argv[0],
        _argv[1] if len(_argv) >= 2 and _argv[1] else None,
        _hour,
        _date,
        _allow,
        _minute,
        _draft,
        _replaces,
    ))
