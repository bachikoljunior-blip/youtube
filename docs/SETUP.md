# セットアップ — あなたがやること

**所要 30〜40分。PC は要りません。スマホのブラウザだけで最後まで行けます。**
登録する秘密情報は**3つだけ**です（4つ目は任意）。
GitHub の Secrets は使いません。Claude Code の環境変数に置きます。

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

## STEP 5. 認証情報を環境変数に入れる

**GitHub の Secrets ではありません。** 投稿は GitHub Actions ではなく、Claude Code の
常駐セッションから行うので、値は**環境**に置きます。リポジトリにも会話にも残りません。

Claude Code の **Environments → 「Youtube」→ Environment variables** を開き、
次の3つを登録します。

```
YT_CLIENT_ID
```
```
YT_CLIENT_SECRET
```
```
YT_REFRESH_TOKEN
```

**任意（4つ目）**：`GOOGLE_TTS_API_KEY` を足すとナレーションの声が機械的なものから
自然な読み上げに変わります。無ければ無料の open-jtalk を使うので動作はします。
取り方は末尾の「補足」。

> ⚠️ **環境変数は、設定したあとに始まるセッションにしか入りません。**
> 既に動いているセッションには反映されないので、登録してから新しいセッションを作ります。

---

## STEP 6. 常駐セッションを立ち上げる

[`KICKOFF.md`](KICKOFF.md) の手順どおりに進めます。要点だけ:

1. 「+ 新規セッション」→ リポジトリ `youtube` → **環境に「Youtube」を選ぶ**
2. KICKOFF.md の中のコードブロックをそのまま貼る
3. セッションが疎通確認 → 1本目の生成 → 投稿 → 自分を定期実行に登録、まで自分で行います

以降は毎日 12:10（JST）に定期実行が撃ち込まれ、その日のぶんが作られて
19時（JST）に公開されます。

---

## STEP 7. 収益化の申請（条件を満たしてから）

| | やること | リンク |
|---|---|---|
| 7-1 | AdSense を作る（審査に時間がかかるので先に） | [AdSense](https://www.google.com/adsense/start/) |
| 7-2 | 条件達成後に申請 | [YouTube Studio → 収益化](https://studio.youtube.com/) |

**条件**：チャンネル登録者 1,000人 ＋ 直近12か月の総再生時間 4,000時間。

承認されたら Studio で **ミッドロール広告を自動配置** をオンにしてください。
8分超の動画に複数の広告が入るようになります。**API から設定できない唯一の項目**です。

---

## トラブル時

| 症状 | 原因 |
|---|---|
| 認証が通らない | 環境を間違えている。セッションで `echo $CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE` が `cloud_default` なら「Youtube」環境で作り直す |
| サムネイルだけ設定されない | STEP 1-3 の電話番号確認が未了 |
| `invalid_grant` | 同意画面が「テスト」のまま7日経過。STEP 2-4 で公開してから STEP 4 をやり直す |
| `invalid_client` | クライアントIDの貼り間違い。値が二重になっていないか確認 |
| STEP 4 で Playground が使えない | STEP 3 で「デスクトップ」を選んでいる。ウェブアプリケーションで作り直す |
| 動画が8分未満で投稿されない | 投稿前の検査が正しく止めています。台本の文字数を増やす |

---

## 補足：音声の質を上げる（任意）

`GOOGLE_TTS_API_KEY` を足すと、機械的な合成音声から自然な読み上げに変わります。

1. [Cloud Text-to-Speech API を有効化](https://console.cloud.google.com/apis/library/texttospeech.googleapis.com)
2. [お支払い情報を登録](https://console.cloud.google.com/billing)（月100万文字まで無料。使用量は約12万文字なので **$0** ですが、登録自体は必要です）
3. [認証情報](https://console.cloud.google.com/apis/credentials) →「認証情報を作成」→ **API キー**
   → 作成後「キーを制限」で Cloud Text-to-Speech API のみに絞る
4. 環境「Youtube」の Environment variables に `GOOGLE_TTS_API_KEY` として登録
   （反映にはセッションの作り直しが要ります）
