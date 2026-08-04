# 運用手順

**投稿だけ自動、あとは手押し**です。

| | ワークフロー | 実行 | リンク |
|---|---|---|---|
| 0 | 設定をチェックする | 手動（初回と、失敗したとき） | [開く](https://github.com/bachikoljunior-blip/youtube/actions/workflows/0-check.yml) |
| 1 | 動画をつくる（投稿しない） | 手動（中身を先に見たいとき） | [開く](https://github.com/bachikoljunior-blip/youtube/actions/workflows/1-preview.yml) |
| 2 | 動画をつくって投稿する | **毎日 05:17 JST に自動** | [開く](https://github.com/bachikoljunior-blip/youtube/actions/workflows/2-publish.yml) |
| 3 | テーマを実績から入れ替える | 手動（週1回・4本たまってから） | [開く](https://github.com/bachikoljunior-blip/youtube/actions/workflows/3-optimize.yml) |

手で押すときは、リンクを開く → 右上の **Run workflow** → 内容を選ぶ → 緑の **Run workflow**。

---

## 普段やること

**何もありません。** 毎朝 05:17（JST）に1本作られ、その日の19時に公開されます。

やるとしたら、週に何度か次のどれかです。

- [公開待ちの動画を見る](https://studio.youtube.com/) — 19時前なら差し替えも取り消しもできます
- **コメントを固定する** — 自動でコメントは投稿されますが、**固定だけは API に無い**ので
  Studio で「固定」を1タップしてください（実行ログに動画ごとの直リンクが出ます）
- [実行が失敗していないか見る](https://github.com/bachikoljunior-blip/youtube/actions/workflows/2-publish.yml) — 赤いバツが付いていたら下の「失敗したとき」へ
- [テーマを自分で足す](https://github.com/bachikoljunior-blip/youtube/edit/main/config/topics.yaml) — 自分で思いついたネタが一番強いです

> 公開設定は `private`（非公開でアップして19時に自動公開）が既定です。放っておけば公開されます。
> やめたくなったら19時までに Studio から削除するか、下書きに戻してください。

### 今すぐもう1本ほしいとき

[**2. 動画をつくって投稿する**](https://github.com/bachikoljunior-blip/youtube/actions/workflows/2-publish.yml)
を手で実行してください。スケジュールとは別に、その回のぶんが増えます。

### 失敗したとき

赤いバツの回を開くと、どのステップで落ちたか出ます。よくあるのは
`CLAUDE_CODE_OAUTH_TOKEN` の期限切れです。手元で `claude setup-token` を実行し直して
[Secrets](https://github.com/bachikoljunior-blip/youtube/settings/secrets/actions) を更新してください。

自動リトライはしません。直したあと、手で「2」を1回押せばその日のぶんが埋まります。

---

## 初回だけやること

### 1. 鍵を登録する

[**→ Secrets の登録ページ**](https://github.com/bachikoljunior-blip/youtube/settings/secrets/actions)

`New repository secret` から4つ登録します（5つ目は任意）。取り方は [SETUP.md](SETUP.md) を見てください。

| Name | 出どころ |
|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | 手元で `claude setup-token` |
| `YT_CLIENT_ID` | Google Cloud の OAuth クライアント |
| `YT_CLIENT_SECRET` | 同上 |
| `YT_REFRESH_TOKEN` | [OAuth 2.0 Playground](https://developers.google.com/oauthplayground/) |
| `GOOGLE_TTS_API_KEY` | 任意。無ければ無料の open-jtalk を使う |

### 2. Actions に書き込み権限を与える

[**→ Actions の設定ページ**](https://github.com/bachikoljunior-blip/youtube/settings/actions)

一番下の **Workflow permissions** を **Read and write permissions** にして Save。
これがないと「テーマの補充」で失敗します。

### 3. チェックを通す

[**→ 0. 設定をチェックする**](https://github.com/bachikoljunior-blip/youtube/actions/workflows/0-check.yml) を実行。
全部 OK になるまで、出てきた項目を潰します。

### 4. 1本つくって中身を見る

[**→ 1. 動画をつくる（投稿しない）**](https://github.com/bachikoljunior-blip/youtube/actions/workflows/1-preview.yml) を実行。

終わったら実行結果ページの一番下の **Artifacts → preview** をダウンロードします。
zip の中に入っているもの:

| ファイル | 見るところ |
|---|---|
| `final.mp4` | 図解と字幕がズレていないか（尺は投稿前の検査が自動で見ます） |
| `thumbnail.jpg` | スマホサイズに縮めても文字が読めるか |
| `title.txt` | タイトルと別案2つ |
| `description.txt` | 説明欄。チャプターの時刻が合っているか |
| `script.json` | 台本の全文。**制度や数字の間違いはここで見つける** |

納得できたら「2」で本番投稿に進みます。

---

## テーマの補充

初期プールは10件なので、日次だと10日で尽きます。
そこで **未投稿が6件を切ったら、投稿の直後に自動で5件足す** ようにしてあります。
補充に失敗しても投稿は成功扱いで、次の回にまた試します。

つまり放っておいても止まりませんが、自動生成のネタは無難になりがちです。
思いついたものは自分で足してください。

[**→ config/topics.yaml を編集する**](https://github.com/bachikoljunior-blip/youtube/edit/main/config/topics.yaml)

一番下に同じ形で足すだけです。`score` が大きいものから先に使われます。

```yaml
  - id: kakutei-shinkoku-freelance
    title_seed: "確定申告、freeeとやよいでどちらが早いか"
    angle: "入力項目数と連携できる口座の違い。乗り換え時のデータ移行の手順まで"
    score: 2.0      # 先に使いたいので高めにする
```

自分で思いついたネタのほうが強いことが多いので、遠慮なく足してください。
「3」の自動生成は、ネタが尽きたときの保険くらいに考えるのがいいです。

---

## よくある調整

| やりたいこと | 場所 |
|---|---|
| 公開時刻を19時から変える | [channel.yaml](https://github.com/bachikoljunior-blip/youtube/edit/main/config/channel.yaml) の `publish_hour_jst` |
| ジャンルを変える | 同 `channel.niche` と `persona` |
| 動画を長くする | 同 `video.target_minutes` |
| 声を変える | 同 `generation.tts`（`engine` を `google` にすると自然になる） |
| 利用枠を節約する | 同 `generation.model` を `opus` → `sonnet` |

---

## 投稿頻度を変える

[**→ 2-publish.yml を編集する**](https://github.com/bachikoljunior-blip/youtube/edit/main/.github/workflows/2-publish.yml)

`cron:` の行を書き換えるだけです。**UTC で書く**ので、JST から9時間引きます。

| したいこと | cron |
|---|---|
| 毎日 05:17 JST（既定） | `"17 20 * * *"` |
| 隔日 | `"17 20 */2 * *"` |
| 平日だけ | `"17 20 * * 1-5"` |
| 自動投稿を止める | `schedule:` と `- cron:` の2行を消す |

**上げるより下げるほうが安全です。** 1日2本にすると Actions の無料枠（private リポジトリは
月2,000分）を超えます。増やしたいなら先に1週間ぶんの実行時間を
[Billing の使用状況](https://github.com/settings/billing) で確認してください。

> **スケジュール実行はデフォルトブランチ（main）のファイルしか動きません。**
> 別ブランチで cron を書き換えても反映されないので、必ず main にマージしてください。
