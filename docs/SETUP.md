# セットアップ — あなたがやること

**所要 30〜40分。PC は要りません。スマホのブラウザだけで最後まで行けます。**
登録する秘密情報は4つです（5つ目は任意）。

各ステップのリンクは、押せばそのページに直接飛びます。

---

## STEP 1. YouTube チャンネルを用意する（10分）

| | やること | リンク |
|---|---|---|
| 1-1 | 投稿用の Google アカウントでログイン | [Google にログイン](https://accounts.google.com/) |
| 1-2 | チャンネルを作る（既にあれば飛ばす） | [チャンネルを作成](https://www.youtube.com/channel_switcher) |
| 1-3 | **電話番号で確認する** | [チャンネルを確認](https://www.youtube.com/verify) |

> 1-3 は必須です。ここを飛ばすと**15分を超える動画とカスタムサムネイルが使えず**、
> サムネイルの設定だけが静かに失敗します。

---

## STEP 2. Google Cloud（10分）

有効にする API は**2つだけ**です。

| | やること | リンク |
|---|---|---|
| 2-1 | プロジェクトを新規作成（名前は何でも可） | [プロジェクトを作成](https://console.cloud.google.com/projectcreate) |
| 2-2 | **YouTube Data API v3** を有効にする（投稿に使う） | [有効化](https://console.cloud.google.com/apis/library/youtube.googleapis.com) |
| 2-3 | **YouTube Analytics API** を有効にする（実績の読み取りに使う） | [有効化](https://console.cloud.google.com/apis/library/youtubeanalytics.googleapis.com) |
| 2-4 | OAuth 同意画面（User Type = **外部**／テストユーザーに 1-1 のアドレスを追加） | [OAuth 同意画面](https://console.cloud.google.com/apis/credentials/consent) |

> **同意画面は「本番環境に公開」しておいてください。**
> 「テスト」のままだと **refresh token が7日で失効**し、毎週取り直すことになります。
> 審査は不要で、その場で公開できます。

---

## STEP 3. OAuth クライアントを作る（5分）

[**→ 認証情報のページを開く**](https://console.cloud.google.com/apis/credentials)

「認証情報を作成」→「OAuth クライアント ID」

- アプリケーションの種類：**ウェブ アプリケーション**
  > ⚠️ **「デスクトップ」ではありません。** デスクトップ型にはリダイレクト URI の欄が無く、
  > 次のステップが使えません。ここを間違えると STEP 4 で詰まります。
- 「承認済みのリダイレクト URI」に、次を**そのまま**貼って追加：
  ```
  https://developers.google.com/oauthplayground
  ```

作成すると **クライアント ID** と **クライアント シークレット** が出ます。控えてください。

---

## STEP 4. refresh token を取る（5分・ブラウザだけ）

[**→ OAuth 2.0 Playground を開く**](https://developers.google.com/oauthplayground/)

1. 右上の**歯車アイコン** →「**Use your own OAuth credentials**」にチェック
   → STEP 3 の Client ID / Client secret を貼る
2. 左の「Step 1」の入力欄に、次の3つを**改行区切りで**貼る
   ```
   https://www.googleapis.com/auth/youtube.upload
   https://www.googleapis.com/auth/youtube.readonly
   https://www.googleapis.com/auth/yt-analytics.readonly
   https://www.googleapis.com/auth/youtube.force-ssl
   ```

   > 4つ目の `force-ssl` は**再生リストへの追加**と**コメントの投稿**に要ります。
   > スコープは refresh token に焼き込まれるので、後から足すとこの STEP をやり直しに
   > なります。使わないつもりでも入れておくのが安全です。
   > （なお**コメントの「固定」は API に存在せず**、Studio での手作業になります）
3. **Authorize APIs** → 1-1 のアカウントでログイン → 許可
   （「確認されていないアプリ」と出たら「詳細」→「（アプリ名）に移動」）
4. 「Step 2」の **Exchange authorization code for tokens** を押す
5. **Refresh token**（`1//` で始まる長い文字列）をコピー

> 一緒に出る **Access token** は1時間で切れます。使うのは **Refresh token** のほうです。

---

## STEP 5. 台本生成用のトークン（3分）

台本は **API 従量課金ではなく、あなたの Claude サブスクの枠内**で生成します。
Claude Code にログイン済みの端末で、次を1回だけ実行してください。

```bash
npm install -g @anthropic-ai/claude-code
claude setup-token
```

`sk-ant-oat01-...` が出ます。これが `CLAUDE_CODE_OAUTH_TOKEN` です。

---

## STEP 6. GitHub に登録する（5分）

[**→ Secrets の登録ページを開く**](https://github.com/bachikoljunior-blip/youtube/settings/secrets/actions)

`New repository secret` から**4つ**登録します。

| Name | 値の出どころ |
|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | STEP 5 |
| `YT_CLIENT_ID` | STEP 3 |
| `YT_CLIENT_SECRET` | STEP 3 |
| `YT_REFRESH_TOKEN` | STEP 4 |

**任意（5つ目）**：`GOOGLE_TTS_API_KEY` を足すとナレーションの声が明確に自然になります。
無ければ無料の open-jtalk を使うので、動作はします。声は視聴維持率を通して収益に効くので、
続ける気があるなら後から足す価値があります（取り方は末尾の「補足」）。

続けて、Actions がコミットを push できるようにします。

[**→ Actions の権限設定を開く**](https://github.com/bachikoljunior-blip/youtube/settings/actions)
→ 「Workflow permissions」を **Read and write permissions** にして Save。

---

## STEP 7. 動かす（10分）

| | やること | リンク |
|---|---|---|
| 7-1 | 設定チェック。足りないものが一覧で出る | [**0. 設定をチェックする**](https://github.com/bachikoljunior-blip/youtube/actions/workflows/0-check.yml) |
| 7-2 | 投稿せず1本作る。終わったら **Artifacts** から中身を確認 | [**1. 動画をつくる（投稿しない）**](https://github.com/bachikoljunior-blip/youtube/actions/workflows/1-preview.yml) |
| 7-3 | 本番投稿。visibility は `private` のまま | [**2. 動画をつくって投稿する**](https://github.com/bachikoljunior-blip/youtube/actions/workflows/2-publish.yml) |
| 7-4 | 非公開で1本上がっているのを確認 | [YouTube Studio](https://studio.youtube.com/) |

どのワークフローも、リンクを開く → 右上の **Run workflow** → 緑の **Run workflow** です。

ここまで通れば、以降は **毎日 05:17（JST）に自動で1本**作られ、その日の19時に公開されます。

---

## STEP 8. 収益化の申請（条件を満たしてから）

| | やること | リンク |
|---|---|---|
| 8-1 | AdSense を作る（審査に時間がかかるので先に） | [AdSense](https://www.google.com/adsense/start/) |
| 8-2 | 条件達成後に申請 | [YouTube Studio → 収益化](https://studio.youtube.com/) |

**条件**：チャンネル登録者 1,000人 ＋ 直近12か月の総再生時間 4,000時間。

承認されたら Studio で **ミッドロール広告を自動配置** をオンにしてください。
8分超の動画に複数の広告が入るようになります。**API から設定できない唯一の項目**です。

---

## トラブル時

まず [**0. 設定をチェックする**](https://github.com/bachikoljunior-blip/youtube/actions/workflows/0-check.yml) を実行してください。

| 症状 | 原因 |
|---|---|
| サムネイルだけ設定されない | STEP 1-3 の電話番号確認が未了 |
| `invalid_grant` | 同意画面が「テスト」のまま7日経過。STEP 2-4 で公開してから STEP 4 をやり直す |
| `invalid_client` | クライアントIDの貼り間違い。値が二重になっていないか確認（前後の空白と二重ペーストは自動で直します） |
| STEP 4 で Playground が使えない | STEP 3 で「デスクトップ」を選んでいる。ウェブアプリケーションで作り直す |
| 動画が8分未満で投稿されない | 検査ゲートが正しく止めています。`config/channel.yaml` の `target_minutes` を上げる |

---

## 補足：音声の質を上げる（任意）

`GOOGLE_TTS_API_KEY` を足すと、機械的な合成音声から自然な読み上げに変わります。

1. [Cloud Text-to-Speech API を有効化](https://console.cloud.google.com/apis/library/texttospeech.googleapis.com)
2. [お支払い情報を登録](https://console.cloud.google.com/billing)（月100万文字まで無料。使用量は約12万文字なので **$0** ですが、登録自体は必要です）
3. [認証情報](https://console.cloud.google.com/apis/credentials) →「認証情報を作成」→ **API キー**
   → 作成後「キーを制限」で Cloud Text-to-Speech API のみに絞る
4. [Secrets](https://github.com/bachikoljunior-blip/youtube/settings/secrets/actions) に `GOOGLE_TTS_API_KEY` として登録
