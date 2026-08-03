# セットアップ — あなたがやること

所要時間は **合計40〜60分**。上から順にやれば終わります。
各ステップのリンクは、押せばそのページに直接飛びます。

---

## STEP 1. YouTube チャンネルを用意する（10分）

| | やること | リンク |
|---|---|---|
| 1-1 | 投稿用の Google アカウントでログイン | [Google にログイン](https://accounts.google.com/) |
| 1-2 | チャンネルを作る（既にあれば飛ばす） | [チャンネルを作成](https://www.youtube.com/channel_switcher) |
| 1-3 | **電話番号で確認する**（必須：これがないと15分超の動画とカスタムサムネが使えません） | [チャンネルを確認](https://www.youtube.com/verify) |
| 1-4 | アップロードのデフォルト設定を開き、「収益受け取り」を既定でオンにしておく | [YouTube Studio → 設定](https://studio.youtube.com/) |

> 1-3 は本当に必須です。ここを飛ばすとサムネイル設定だけ静かに失敗します。

---

## STEP 2. Google Cloud（YouTube API と音声合成）（20分）

すべて**同じプロジェクト**で作業してください。

| | やること | リンク |
|---|---|---|
| 2-1 | プロジェクトを新規作成（名前は何でも可、例: `yt-auto`） | [プロジェクトを作成](https://console.cloud.google.com/projectcreate) |
| 2-2 | 請求先アカウントを紐づける（**音声合成に必要**。月12万文字程度なら無料枠内で $0 です） | [お支払い](https://console.cloud.google.com/billing) |
| 2-3 | YouTube Data API v3 を「有効にする」 | [有効化](https://console.cloud.google.com/apis/library/youtube.googleapis.com) |
| 2-4 | YouTube Analytics API を「有効にする」 | [有効化](https://console.cloud.google.com/apis/library/youtubeanalytics.googleapis.com) |
| 2-5 | Cloud Text-to-Speech API を「有効にする」 | [有効化](https://console.cloud.google.com/apis/library/texttospeech.googleapis.com) |
| 2-6 | OAuth 同意画面を設定（User Type = **外部** / 公開ステータスは「テスト」のままでOK / **テストユーザーに 1-1 のメールアドレスを追加**） | [OAuth 同意画面](https://console.cloud.google.com/apis/credentials/consent) |
| 2-7 | 認証情報 → 「認証情報を作成」→ **OAuth クライアント ID** → 種類は **デスクトップアプリ**。表示される **クライアントID / クライアントシークレット** を控える | [認証情報](https://console.cloud.google.com/apis/credentials) |
| 2-8 | 同じ画面で「認証情報を作成」→ **API キー**。これが `GOOGLE_TTS_API_KEY`。作成後に「キーを制限」→ Cloud Text-to-Speech API のみに制限しておく | [認証情報](https://console.cloud.google.com/apis/credentials) |

> 2-6 で「テスト」のままだと**リフレッシュトークンが7日で失効します**。
> 毎週取り直すのが嫌なら、同じ画面で「アプリを公開」（本番環境に push）してください。
> 自分専用の用途なので審査は不要で、そのまま公開ステータスにできます。

---

## STEP 3. Claude Code のサブスク認証トークン（5分）

台本生成は **API 従量課金を使いません**。あなたの Claude サブスクリプション
（Pro / Max）の枠内で、Claude Code のセッションとして動きます。追加課金は発生しません。

あなたのPCで、Claude Code にログイン済みの状態で以下を実行します。

```bash
npm install -g @anthropic-ai/claude-code   # 未インストールなら
claude setup-token
```

ブラウザで認証すると `sk-ant-oat01-...` で始まる長期トークンが表示されます。
これが `CLAUDE_CODE_OAUTH_TOKEN` です。控えてください。

> このトークンはサブスクの利用枠を消費します。1日1本の台本生成なら
> 通常の利用上限に対してごく僅かですが、普段の Claude Code 作業と同じ枠を共有します。
> 上限に当たりやすいなら `config/channel.yaml` の `generation.model` を `sonnet` に変えてください。

---

## STEP 4. Pexels の API キー（3分）— 映像素材用・無料

| | やること | リンク |
|---|---|---|
| 4-1 | 無料アカウントを作り、API キーを発行 | [Pexels API キー発行](https://www.pexels.com/api/new/) |

---

## STEP 5. リフレッシュトークンを取る（5分・あなたのPCで1回だけ）

ブラウザが開くので、STEP 1 のアカウントで許可してください。

```bash
git clone https://github.com/bachikoljunior-blip/youtube.git
cd youtube
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/get_refresh_token.py
```

STEP 2-7 のクライアントID / シークレットを聞かれるので貼り付けます。
最後に `YT_REFRESH_TOKEN=...` が出るので控えてください。

> 「このアプリは確認されていません」と警告が出ますが、自分で作ったアプリなので
> 「詳細」→「（アプリ名）に移動」で進めて大丈夫です。

---

## STEP 6. GitHub に鍵を登録する（5分）

[**→ Secrets の登録ページを開く**](https://github.com/bachikoljunior-blip/youtube/settings/secrets/actions)

「New repository secret」で、以下の **6つ** を1つずつ登録します。

| Name | 値の出どころ |
|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | STEP 3 |
| `YT_CLIENT_ID` | STEP 2-7 |
| `YT_CLIENT_SECRET` | STEP 2-7 |
| `YT_REFRESH_TOKEN` | STEP 5 |
| `GOOGLE_TTS_API_KEY` | STEP 2-8 |
| `PEXELS_API_KEY` | STEP 4-1 |

あわせて、Actions がコミットを push できるようにします。

[**→ Actions の権限設定を開く**](https://github.com/bachikoljunior-blip/youtube/settings/actions)
→ 「Workflow permissions」を **Read and write permissions** に変更して Save。

---

## STEP 7. 動作確認（10分）

1. [**→ 0. 設定をチェックする**](https://github.com/bachikoljunior-blip/youtube/actions/workflows/0-check.yml)
   → 「Run workflow」。足りないものが一覧で出るので全部潰す
2. [**→ 1. 動画をつくる（投稿しない）**](https://github.com/bachikoljunior-blip/youtube/actions/workflows/1-preview.yml)
   → 実行し、終わったら **Artifacts** から中身を落として確認
3. [**→ 2. 動画をつくって投稿する**](https://github.com/bachikoljunior-blip/youtube/actions/workflows/2-publish.yml)
   → visibility を `private` のまま実行
4. [YouTube Studio のコンテンツ](https://studio.youtube.com/) に **非公開** で1本上がっているのを確認

**スケジュール実行はしません。** 毎日「2」を押すのが運用です。
日々の押し方と調整方法は [RUNBOOK.md](RUNBOOK.md) にまとめてあります。

---

## STEP 8. 収益化の申請（条件を満たしてから）

先に作っておくもの:

| | やること | リンク |
|---|---|---|
| 8-1 | AdSense アカウントを作る（審査に時間がかかるので先に） | [AdSense](https://www.google.com/adsense/start/) |
| 8-2 | 条件を満たしたら YouTube パートナープログラムに申請 | [YouTube Studio → 収益化](https://studio.youtube.com/) |

**申請の条件**（長尺の広告収益コース）:
- チャンネル登録者 **1,000人**
- 直近12か月の公開動画の総再生時間 **4,000時間**

申請が通ったら、Studio の「収益受け取り」で **ミッドロール広告を自動配置** に設定してください。
8分超の動画に複数の広告が入るようになり、ここで RPM が跳ねます。
（この設定は API から変更できないため、手作業が必要な唯一の項目です）

---

## トラブル時

まず手元でこれを実行すると、何が足りないか一覧で出ます。

```bash
python scripts/preflight.py
```

| 症状 | 原因 |
|---|---|
| サムネだけ設定されない | STEP 1-3 の電話番号確認が未了 |
| `invalid_grant` | OAuth 同意画面が「テスト」のまま7日経過。STEP 5 をやり直すか、アプリを公開する |
| TTS が 403 | STEP 2-2 の請求先未設定、または 2-5 の API 未有効化 |
| `claude が異常終了しました` | `CLAUDE_CODE_OAUTH_TOKEN` の期限切れ。`claude setup-token` を再実行して secret を更新 |
| 利用上限に当たる | `config/channel.yaml` の `generation.model` を `sonnet` に、または cron を隔日に |
| 動画が8分未満になる | `config/channel.yaml` の `target_minutes` を上げる |
