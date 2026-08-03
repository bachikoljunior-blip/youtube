# 運用手順（スケジュール実行なし・全部手押し）

cron は使いません。GitHub の画面から番号順にボタンを押すだけです。
PC は不要で、スマホのブラウザからでも全部できます。

ワークフローは4つ。**普段使うのは「2」だけ**です。

| | ワークフロー | いつ押すか | リンク |
|---|---|---|---|
| 0 | 設定をチェックする | 初回と、失敗したとき | [開く](https://github.com/bachikoljunior-blip/youtube/actions/workflows/0-check.yml) |
| 1 | 動画をつくる（投稿しない） | 中身を先に見たいとき | [開く](https://github.com/bachikoljunior-blip/youtube/actions/workflows/1-preview.yml) |
| 2 | 動画をつくって投稿する | **毎日これ** | [開く](https://github.com/bachikoljunior-blip/youtube/actions/workflows/2-publish.yml) |
| 3 | テーマを実績から入れ替える | 週1回・4本たまってから | [開く](https://github.com/bachikoljunior-blip/youtube/actions/workflows/3-optimize.yml) |

押し方はどれも同じです。リンクを開く → 右上の **Run workflow** → 内容を選ぶ → 緑の **Run workflow**。

---

## 毎日やること（30秒）

1. [**2. 動画をつくって投稿する**](https://github.com/bachikoljunior-blip/youtube/actions/workflows/2-publish.yml) を開く
2. **Run workflow** → visibility は `private` のまま → **Run workflow**
3. 終わり。40〜60分後にアップロードが完了し、その日の19時（JST）に自動公開されます

進み具合は同じページで見られます。緑のチェックが付けば成功です。
できた動画は [YouTube Studio のコンテンツ](https://studio.youtube.com/) に並びます。

> `private` は「非公開でアップして19時に自動公開」です。放っておけば公開されます。
> やめたくなったら19時までに Studio から削除するか、下書きに戻してください。
> 確認せずすぐ出したくなったら visibility を `public` にします。

---

## 初回だけやること

### 1. 鍵を登録する

[**→ Secrets の登録ページ**](https://github.com/bachikoljunior-blip/youtube/settings/secrets/actions)

`New repository secret` から5つ登録します。取り方は [SETUP.md](SETUP.md) を見てください。

| Name | 出どころ |
|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | 手元で `claude setup-token` |
| `YT_CLIENT_ID` | Google Cloud の OAuth クライアント |
| `YT_CLIENT_SECRET` | 同上 |
| `YT_REFRESH_TOKEN` | `python scripts/get_refresh_token.py` の出力 |
| `GOOGLE_TTS_API_KEY` | Google Cloud の API キー |
| `PEXELS_API_KEY` | [Pexels](https://www.pexels.com/api/new/) |

### 2. Actions に書き込み権限を与える

[**→ Actions の設定ページ**](https://github.com/bachikoljunior-blip/youtube/settings/actions)

一番下の **Workflow permissions** を **Read and write permissions** にして Save。
これがないと「投稿済みテーマの記録」で失敗します。

### 3. チェックを通す

[**→ 0. 設定をチェックする**](https://github.com/bachikoljunior-blip/youtube/actions/workflows/0-check.yml) を実行。
全部 OK になるまで、出てきた項目を潰します。

### 4. 1本つくって中身を見る

[**→ 1. 動画をつくる（投稿しない）**](https://github.com/bachikoljunior-blip/youtube/actions/workflows/1-preview.yml) を実行。

終わったら実行結果ページの一番下の **Artifacts → preview** をダウンロードします。
zip の中に入っているもの:

| ファイル | 見るところ |
|---|---|
| `final.mp4` | 長さが8分半を超えているか。字幕がズレていないか |
| `thumbnail.jpg` | スマホサイズに縮めても文字が読めるか |
| `title.txt` | タイトルと別案2つ |
| `description.txt` | 説明欄。チャプターの時刻が合っているか |
| `script.json` | 台本の全文。**制度や数字の間違いはここで見つける** |

納得できたら「2」で本番投稿に進みます。

---

## テーマを自分で足す

[**→ config/topics.yaml を編集する**](https://github.com/bachikoljunior-blip/youtube/edit/main/config/topics.yaml)

一番下に同じ形で足すだけです。`score` が大きいものから先に使われます。

```yaml
  - id: kakutei-shinkoku-freelance
    title_seed: "確定申告、freeeとやよいでどちらが早いか"
    angle: "入力項目数と連携できる口座の違い。乗り換え時のデータ移行の手順まで"
    score: 2.0      # 先に使いたいので高めにする
    used: false
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
| 声を変える | 同 `generation.tts.voice` |
| 利用枠を節約する | 同 `generation.model` を `opus` → `sonnet` |

---

## 手押しにした代償と、戻し方

手動なので、**押し忘れた日は動画が増えません**。伸びるかどうかは投稿を切らさないことで
だいたい決まるので、ここだけは自分で担保する必要があります。
スマホのリマインダーを毎朝8時にセットしておくのが現実的です。

あとで自動に戻したくなったら、
[2-publish.yml](https://github.com/bachikoljunior-blip/youtube/edit/main/.github/workflows/2-publish.yml)
の `on:` の下に3行足すだけです。

```yaml
on:
  schedule:
    - cron: "0 23 * * *"   # 毎朝8時(JST)。UTC で書く点に注意
  workflow_dispatch:
    ...
```

ただし **スケジュール実行はデフォルトブランチ（main）にあるファイルしか動きません**。
手押しのままなら関係ありませんが、自動に戻すときは main にマージされているか確認してください。
