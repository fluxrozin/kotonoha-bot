# Troubleshooting Guide - Kotonoha Discord Bot

Kotonoha Discord ボットの問題解決ガイド

## 目次

1. [起動・接続の問題](#1-起動接続の問題)
2. [AI 応答の問題](#2-ai-応答の問題)
3. [データベースの問題](#3-データベースの問題)
4. [パフォーマンスの問題](#4-パフォーマンスの問題)
5. [デプロイメントの問題](#5-デプロイメントの問題)
   - [ディレクトリのパーミッションエラー](#問題-ディレクトリのパーミッションエラー)

---

## 1. 起動・接続の問題

### 問題: Bot が Discord に接続できない

**症状**:

```txt
ERROR: discord.errors.LoginFailure: Improper token has been passed.
```

または

```txt
ERROR: discord.errors.HTTPException: 401 Unauthorized
```

**原因**:

- Discord Bot Token が正しく設定されていない
- Token が無効または期限切れ
- `.env` ファイルが読み込まれていない

**解決方法**:

1. **環境変数の確認**

   ```bash
   # .env ファイルの確認
   cat .env | grep DISCORD_TOKEN

   # コンテナ内の環境変数を確認
   docker exec kotonoha-bot env | grep DISCORD_TOKEN
   ```

2. **Token の再取得**

   - [Discord Developer Portal](https://discord.com/developers/applications) にアクセス
   - アプリケーションを選択
   - "Bot" タブで Token を Reset して再取得
   - `.env` ファイルを更新

3. **Bot の再起動**

   ```bash
   docker compose restart kotonoha-bot
   ```

   **注意**: `.env` ファイルを更新した後は、コンテナを再起動する必要があります。

---

### 問題: Bot がサーバーに参加できない

**症状**:

- Bot をサーバーに招待しても参加しない
- 招待リンクが無効

**原因**:

- 招待リンクの権限設定が不正
- Bot の Privileged Gateway Intents が有効化されていない

**解決方法**:

1. **Privileged Gateway Intents の有効化**

   - [Discord Developer Portal](https://discord.com/developers/applications) にアクセス
   - "Bot" タブを開く
   - 以下の Intents を有効化:
     - **MESSAGE CONTENT INTENT**（必須）
     - PRESENCE INTENT（オプション）
     - SERVER MEMBERS INTENT（オプション）

   **実装箇所**: `src/kotonoha_bot/bot/client.py` (17-20 行目)

   ```python
   intents = discord.Intents.default()
   intents.message_content = True  # メッセージ内容を読み取る権限
   intents.messages = True
   intents.guilds = True
   ```

2. **招待リンクの再生成**

   ```txt
   https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=8&scope=bot%20applications.commands
   ```

   - `YOUR_CLIENT_ID` を実際の Client ID に置き換える
   - `permissions=8` は管理者権限（必要に応じて変更）

---

### 問題: Bot は起動しているがメッセージに反応しない

**症状**:

- Bot のステータスはオンライン
- メンションしても応答がない

**原因**:

- `on_message` イベントが正しく実装されていない
- Bot 自身のメッセージに反応してしまっている
- メッセージ権限が不足している

**解決方法**:

1. **ログの確認**

   ```bash
   docker logs kotonoha-bot --tail 50
   ```

2. **Bot の権限確認**

   - サーバー設定 → 役割 → Bot の役割を確認
   - 以下の権限が必要:
     - メッセージを読む
     - メッセージを送信
     - スレッドを作成
     - メッセージ履歴を読む

3. **コードの確認**

   **実装箇所**: `src/kotonoha_bot/router/message_router.py`

   Bot 自身のメッセージは自動的に無視されます：

   ```python
   if message.author.bot:
       return "none"
   ```

---

## 2. AI 応答の問題

### 問題: Claude API エラーが発生する

**症状**:

```txt
ERROR: anthropic.AuthenticationError: 401 Invalid API key
```

または LiteLLM 経由の場合:

```txt
ERROR: litellm.exceptions.AuthenticationError: Invalid API Key
```

**原因**:

- Anthropic API Key が正しく設定されていない
- API Key が無効または期限切れ
- `.env` ファイルが読み込まれていない

**解決方法**:

1. **API Key の確認**

   ```bash
   # .env ファイルの確認
   cat .env | grep ANTHROPIC_API_KEY

   # コンテナ内の環境変数を確認
   docker exec kotonoha-bot env | grep ANTHROPIC_API_KEY
   ```

2. **API Key の再取得**

   - [Anthropic Console](https://console.anthropic.com/) にアクセス
   - 新しい API Key を作成
   - `.env` ファイルを更新

3. **Bot の再起動**

   ```bash
   docker compose restart kotonoha-bot
   ```

   **注意**: `.env` ファイルを更新した後は、コンテナを再起動する必要があります。

---

### 問題: レート制限エラーが発生する

**症状**:

```txt
ERROR: anthropic.RateLimitError: 429 Rate limit exceeded
```

または LiteLLM 経由の場合:

```txt
ERROR: litellm.RateLimitError: Rate limit exceeded
```

**原因**:

- Claude API のレート制限に達した
- 短時間に大量のリクエストを送信した

**解決方法**:

1. **レート制限の確認**

   ```bash
   docker logs kotonoha-bot | grep -i "rate limit"
   ```

2. **一時的な対処**

   - しばらく待ってからリトライ（Bot は自動的にリトライします）
   - 聞き耳型を無効化して負荷を軽減

3. **恒久的な対処**

   - レート制限対応の実装を確認（トークンバケットアルゴリズム）
   - 優先度管理の実装（メンション > スレッド > 聞き耳型）
   - フォールバックモデルの設定（`LLM_FALLBACK_MODEL` 環境変数）

   **実装箇所**: `src/kotonoha_bot/rate_limit/`

---

### 問題: AI の応答が不適切または期待と異なる

**症状**:

- AI の応答が文脈に合わない
- 不適切な内容を返す
- トンチンカンな発言をする

**原因**:

- システムプロンプトが不適切
- 会話履歴が正しく渡されていない
- 聞き耳型で会話の文脈を誤解している

**解決方法**:

1. **システムプロンプトの確認**

   - `prompts/` ディレクトリのプロンプトファイルを確認
   - 場面緘黙支援に適した表現になっているか確認

2. **会話履歴の確認**

   ```bash
   # ログで会話履歴を確認
   docker logs kotonoha-bot | grep -i "会話履歴"
   ```

3. **聞き耳型の判定プロンプトを最適化**

   - `prompts/eavesdrop_judge_prompt.md` の判定プロンプトを調整
   - より厳格な判定基準を設定

---

## 3. データベースの問題

### 問題: データベースファイルが見つからない

**症状**:

```txt
ERROR: sqlite3.OperationalError: unable to open database file
```

または

```txt
ERROR: Cannot write to database directory: /app/data
```

**原因**:

- `data/` ディレクトリが存在しない
- ファイルの書き込み権限がない
- Docker ボリュームマウントの問題

**解決方法**:

1. **ディレクトリの作成**

   ```bash
   mkdir -p /volume1/docker/kotonoha/data
   chmod 755 /volume1/docker/kotonoha/data
   ```

2. **権限の確認**

   ```bash
   ls -la /volume1/docker/kotonoha/data
   # 所有者が正しいか確認（通常は1000:1000）
   ```

3. **ボリュームマウントの確認**

   ```bash
   docker inspect kotonoha-bot | grep Mounts -A 10
   ```

4. **データベースパスの確認**

   **実装箇所**: `src/kotonoha_bot/config.py` (31-32 行目)

   - デフォルト: `./data/sessions.db`
   - 環境変数 `DATABASE_NAME` で変更可能（デフォルト: `sessions.db`）

---

### 問題: データベースが破損している

**症状**:

```txt
ERROR: sqlite3.DatabaseError: database disk image is malformed
```

**原因**:

- データベースファイルが破損
- 不正な終了によるファイル破損

**解決方法**:

1. **データベースの整合性チェック**

   ```bash
   docker exec kotonoha-bot sqlite3 /app/data/sessions.db \
     "PRAGMA integrity_check;"
   ```

2. **バックアップからリストア**

   ```bash
   # 最新のバックアップを確認
   ls -lt /volume1/docker/kotonoha/backups/

   # バックアップからリストア
   cp /volume1/docker/kotonoha/backups/sessions_YYYYMMDD_HHMMSS.db \
      /volume1/docker/kotonoha/data/sessions.db

   # コンテナ再起動
   docker compose restart kotonoha-bot
   ```

3. **リストアできない場合**

   ```bash
   # データベースを削除して再作成
   rm /volume1/docker/kotonoha/data/sessions.db
   docker compose restart kotonoha-bot
   # 注意: 会話履歴は失われます
   ```

---

### 問題: セッションが復元されない

**症状**:

- Bot を再起動すると会話履歴が失われる
- 以前の会話が続かない

**原因**:

- セッションの同期機能が動作していない
- SQLite への保存が失敗している

**解決方法**:

1. **ログの確認**

   ```bash
   docker logs kotonoha-bot | grep -i "session"
   docker logs kotonoha-bot | grep -i "save"
   ```

2. **データベースの確認**

   ```bash
   docker exec kotonoha-bot sqlite3 /app/data/sessions.db \
     "SELECT * FROM sessions LIMIT 5;"
   ```

3. **同期機能の確認**

   - `src/kotonoha_bot/session/manager.py` の同期ロジックを確認
   - バッチ同期タスクが動作しているか確認

   **実装箇所**: `src/kotonoha_bot/session/manager.py`

---

## 4. パフォーマンスの問題

### 問題: 応答が遅い（3 秒以上かかる）

**症状**:

- メッセージを送信してから応答まで 10 秒以上かかる
- Bot が応答しないように見える

**原因**:

- Claude API の応答が遅い
- レート制限で待機している
- データベースクエリが遅い
- メモリ不足

**解決方法**:

1. **レスポンスタイムの測定**

   ```bash
   docker logs kotonoha-bot | grep -i "response time"
   ```

2. **リソース使用状況の確認**

   ```bash
   docker stats kotonoha-bot
   ```

3. **最適化**

   - Flash モデルを優先的に使用
   - セッション数を制限（最大 100、`MAX_SESSIONS` 環境変数）
   - データベースクエリを最適化

---

### 問題: メモリ使用量が多い

**症状**:

```txt
WARNING: Memory usage: 800MB (limit: 1G)
```

**原因**:

- セッション数が多すぎる
- 会話履歴が肥大化している
- メモリリークの可能性

**解決方法**:

1. **セッション数の確認**

   ```bash
   docker exec kotonoha-bot sqlite3 /app/data/sessions.db \
     "SELECT COUNT(*) FROM sessions WHERE is_archived = 0;"
   ```

2. **クリーンアップの実行**

   - 非アクティブセッションは自動的にクリーンアップされます
   - `SESSION_TIMEOUT_HOURS` 環境変数でタイムアウト時間を調整可能

3. **メモリ制限の調整**

   ```yaml
   # docker-compose.ymlで調整
   resources:
     limits:
       memory: 2G # 1G → 2Gに増やす
   ```

---

## 5. デプロイメントの問題

### 問題: Docker イメージのビルドが失敗する

**症状**:

```txt
ERROR: failed to solve: process "/bin/sh -c uv sync" did not complete successfully
```

**原因**:

- 依存関係の解決に失敗
- `pyproject.toml` の記述エラー
- ネットワークエラー

**解決方法**:

1. **ローカルでビルドテスト**

   ```bash
   docker build -t kotonoha-bot:test .
   ```

2. **依存関係の確認**

   ```bash
   uv sync --dry-run
   ```

3. **キャッシュのクリア**

   ```bash
   docker builder prune -a
   ```

---

### 問題: Watchtower で `~/.docker/config.json` が存在しないエラーが発生する

**症状**:

```txt
Error response from daemon: Bind mount failed: '/.docker/config.json' does not exist
watchtower exited with code 1
```

**原因**:

- `~/.docker/config.json` ファイルが存在しない
- このファイルは GHCR 認証用で、プライベートイメージをプルする場合に必要
- ファイルが存在しない場合、ボリュームマウントに失敗する

**`~/.docker/config.json` について**:

**どこにある**:

- パス: `~/.docker/config.json`（ホームディレクトリの `.docker` フォルダ内）
- 例: `/home/admin/.docker/config.json`（SSH でログインしたユーザーのホームディレクトリ）
- Synology NAS の場合: `/root/.docker/config.json` または `/home/admin/.docker/config.json`

**どう作る**:

`docker login` コマンドを実行すると、自動的に作成されます：

```bash
# 方法1: 環境変数を使用（推奨）
echo $GITHUB_TOKEN | docker login ghcr.io -u $GITHUB_USERNAME --password-stdin

# 方法2: 直接指定
docker login ghcr.io -u YOUR_GITHUB_USERNAME -p YOUR_GITHUB_TOKEN

# 方法3: 対話的に入力
docker login ghcr.io
# Username: YOUR_GITHUB_USERNAME
# Password: YOUR_GITHUB_TOKEN
```

**どう入手**:

- **自動作成**: `docker login` コマンドを実行すると自動的に作成されます（推奨）
- **手動作成**: 以下の内容でファイルを作成することも可能ですが、通常は不要です

  ```bash
  # ディレクトリを作成（存在しない場合）
  mkdir -p ~/.docker

  # ファイルを作成（通常は docker login で自動作成されるため、
  # この方法は推奨されません）
  cat > ~/.docker/config.json << EOF
  {
    "auths": {
      "ghcr.io": {
        "auth": "$(echo -n 'YOUR_GITHUB_USERNAME:YOUR_GITHUB_TOKEN' | base64)"
      }
    }
  }
  EOF
  ```

**解決方法**:

1. **GHCR 認証が必要な場合（プライベートイメージを使用）**:

   SSH で NAS にログインして、GHCR にログインします：

   ```bash
   # SSH で NAS にログイン
   ssh admin@nas-ip-address

   # プロジェクトディレクトリに移動
   cd /volume1/docker/kotonoha-bot

   # .env ファイルから環境変数を読み込む
   eval $(grep '^[A-Z_].*=' .env | sed 's/#.*$//' | \
     sed 's/[[:space:]]*$//' | sed 's/^/export /')

   # GHCR にログイン（認証情報が ~/.docker/config.json に自動的に保存される）
   echo $GITHUB_TOKEN | docker login ghcr.io -u $GITHUB_USERNAME --password-stdin

   # ファイルが作成されたか確認
   cat ~/.docker/config.json

   # ファイルの場所を確認
   ls -la ~/.docker/config.json
   ```

   ログインが成功すると、`~/.docker/config.json` が自動的に作成されます。

   その後、`docker-compose.yml` でコメントアウトを解除：

   ```yaml
   volumes:
     - /var/run/docker.sock:/var/run/docker.sock
     - ~/.docker/config.json:/config.json:ro # コメントアウトを解除
   ```

   詳細は [Phase 3 実装ガイド](../implementation/phases/phase03.md) の「4.3 GHCR 認証の設定」を参照してください。

2. **GHCR 認証が不要な場合（パブリックイメージを使用）**:

   `docker-compose.yml` で `~/.docker/config.json` のマウント行をコメントアウトします：

   ```yaml
   volumes:
     - /var/run/docker.sock:/var/run/docker.sock
     # - ~/.docker/config.json:/config.json:ro  # コメントアウト
   ```

---

### 問題: Watchtower で Docker API バージョンエラーが発生する

**症状**:

```txt
watchtower | time="..." level=error msg="Error response from daemon: \
  client version 1.25 is too old. Minimum supported API version is 1.44, \
  please upgrade your client to a newer version"
watchtower exited with code 1 (restarting)
```

**原因**:

- Docker API バージョンが古い（1.25）
- Watchtower の最新版は API 1.44 以上を要求
- Synology NAS などの古い Docker 環境でよく発生

**解決方法**:

1. **Docker をアップグレードする（推奨）**

   - Synology NAS の場合は、DSM を最新版にアップグレード
   - Container Manager を最新版に更新

2. **Watchtower を無効化する**

   `docker-compose.yml` で Watchtower サービス全体をコメントアウト:

   ```yaml
   # watchtower:
   #   image: containrrr/watchtower:latest
   #   ...
   ```

   手動でコンテナを更新する場合は、Watchtower は不要です。

3. **古いバージョンの Watchtower を使用する**

   `docker-compose.yml` でイメージのバージョンを指定:

   ```yaml
   watchtower:
     image: containrrr/watchtower:v1.5.3 # 古いバージョンを指定
   ```

   **注意**: 古いバージョンはセキュリティ更新が提供されない可能性があります。

---

### 問題: Watchtower が新しいイメージを取得しない

**症状**:

- GitHub にプッシュしてもコンテナが更新されない
- Watchtower のログにエラーがない

**原因**:

- イメージタグが変わっていない
- Watchtower の設定ミス
- GHCR の認証エラー

**解決方法**:

1. **Watchtower のログ確認**

   ```bash
   docker logs watchtower --tail 50
   ```

2. **手動でイメージを更新**

   ```bash
   docker pull ghcr.io/your-org/kotonoha-bot:latest
   docker compose up -d kotonoha-bot
   ```

3. **Watchtower の再起動**

   ```bash
   docker compose restart watchtower
   ```

---

### 問題: コンテナが起動直後に停止する

**症状**:

```bash
docker ps  # kotonoha-botが表示されない
docker ps -a  # Exitedステータスで表示される
```

**原因**:

- 起動時のエラー
- 環境変数の設定ミス
- ヘルスチェックの失敗

**解決方法**:

1. **ログの確認**

   ```bash
   docker logs kotonoha-bot
   ```

2. **環境変数の確認**

   ```bash
   docker inspect kotonoha-bot | grep -A 20 Env
   ```

3. **ヘルスチェックの無効化（テスト用）**

   ```yaml
   # docker-compose.ymlで一時的に無効化
   # healthcheck:
   #   disable: true
   ```

---

### 問題: ディレクトリのパーミッションエラー

**症状**:

```txt
ERROR: Required directory /app/data is not writable by current user (1000)
Directory info:
drwxr-xr-x 1 1026 users 16 Jan 14 13:38 /app/data
```

または

```txt
ERROR: Cannot fix permissions automatically (not running as root).
```

**原因**:

- マウントされたボリューム（`data`、`logs`、`backups`）のディレクトリに書き込み権限がない
- コンテナ内のユーザー（UID 1000）がディレクトリの所有者（例: UID 1026）と異なる
- コンテナが root で起動されていない（`docker run`で`--user`オプションを使用した場合など）

**解決方法**:

#### 方法 1: 自動パーミッション修正（推奨）

このボットは起動時に自動的にパーミッションを修正する機能を搭載しています。
`docker-compose.yml`を使用する場合、自動的に root で起動され、パーミッションが修正されます。

1. **`docker-compose.yml`の確認**

   ```yaml
   # docker-compose.ymlに以下が設定されていることを確認
   user: root
   ```

2. **コンテナの再起動**

   ```bash
   docker compose down --remove-orphans
   docker compose up -d
   ```

3. **ログの確認**

   ```bash
   docker compose logs -f
   ```

   以下のようなメッセージが表示されれば成功です:

   ```txt
   Running as root - will fix permissions and switch to botuser
   Successfully fixed permissions for /app/data (chmod 775) ✓
   Switching to botuser (UID 1000) and starting application...
   ```

#### 方法 2: 手動でパーミッションを修正

自動修正が機能しない場合、ホスト側で手動でパーミッションを修正します。

1. **パーミッションの確認**

   ```bash
   ls -ld data logs backups
   ```

2. **パーミッションの修正**

   ```bash
   # 方法A: グループ書き込み権限を付与（推奨）
   chmod 775 data logs backups

   # 方法B: 全員に書き込み権限を付与
   # （セキュリティ上は推奨されないが、動作確認用）
   chmod 777 data logs backups
   ```

3. **確認**

   ```bash
   ls -ld data logs backups
   # drwxrwxr-x または drwxrwxrwx と表示されればOK
   ```

4. **コンテナの再起動**

   ```bash
   docker compose restart kotonoha-bot
   ```

#### 方法 3: 所有者を変更（UID 1000 のユーザーが存在する場合）

Synology NAS などで UID 1000 のユーザーが存在する場合:

```bash
sudo chown -R 1000:1000 data logs backups
```

#### 方法 4: `docker run`で直接起動する場合

`docker run`で直接起動する場合は、`--user root`を指定してください:

```bash
docker run --user root \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/backups:/app/backups \
  kotonoha-bot:latest
```

**注意**: `docker-compose.yml`を使用する場合は、`user: root`が既に設定されているため、この方法は不要です。

---

### トラブルシューティングの詳細

#### 自動パーミッション修正の仕組み

1. コンテナが root で起動される（`docker-compose.yml`の`user: root`設定）
2. `entrypoint.sh`が root で実行される
3. 書き込み不可能なディレクトリを検出
4. まず`chmod 775`を試行（グループ書き込み、より安全）
5. `775`で失敗した場合、`chmod 777`を試行（全員書き込み、フォールバック）
6. `gosu`で botuser（UID 1000）に切り替え
7. botuser でアプリケーションを実行

#### パーミッション修正が失敗する場合

以下のエラーメッセージが表示される場合:

```txt
ERROR: Cannot fix permissions automatically (not running as root).
```

**対処方法**:

1. **`docker-compose.yml`を使用している場合**

   ```yaml
   # docker-compose.ymlに以下が設定されていることを確認
   user: root
   ```

2. **`docker run`を使用している場合**

   ```bash
   # --user rootを指定
   docker run --user root ...
   ```

3. **手動でパーミッションを修正**

   ```bash
   chmod 775 data logs backups
   ```

#### 任意のユーザーで起動した場合の動作

- **`docker-compose.yml`を使用**: 常に root で起動されるため、問題なく動作します
- **`docker run --user root`**: root で起動されるため、問題なく動作します
- **`docker run`で root 以外**: 必須ディレクトリが書き込み可能であれば動作しますが、不可能な場合はエラーメッセージで対処方法を提示します

**推奨事項**: `docker-compose.yml`を使用するか、`docker run`で`--user root`を指定してください。

---

## 6. よくある質問

### Q: Bot が突然応答しなくなった

**A**: 以下を順番に確認してください:

1. Bot のステータス（オンラインか）
2. ログにエラーがないか
3. API のレート制限に達していないか
4. データベース接続が正常か

詳細は各セクションを参照してください。

---

### Q: エラーメッセージが表示されない

**A**: ログレベルを DEBUG に変更してください:

```bash
# .env ファイルで設定
LOG_LEVEL=DEBUG

# コンテナ再起動
docker compose restart kotonoha-bot
```

---

### Q: バックアップから復元した後、データが古い

**A**: バックアップのタイムスタンプを確認してください:

```bash
ls -lt /volume1/docker/kotonoha/backups/
```

最新のバックアップを使用していることを確認してください。

---

## 7. サポート

### 7.1 ログの収集

問題を報告する際は、以下の情報を含めてください:

```bash
# ログの収集
docker logs kotonoha-bot --since 1h > kotonoha_logs.txt

# システム情報
docker info > system_info.txt
docker inspect kotonoha-bot > container_info.txt

# 環境変数（機密情報を削除）
cat .env | sed 's/=.*/=***/' > env_info.txt
```

### 7.2 連絡先

- **GitHub Issues**: GitHub リポジトリの Issues ページ（注: URL は実際の組織名に置き換えてください）
- **ドキュメント**: [docs/](../README.md)

---

**作成日**: 2026 年 1 月 14 日  
**最終更新日**: 2026 年 1 月（現在の実装に基づいて改訂）  
**バージョン**: 2.0  
**作成者**: kotonoha-bot 開発チーム

### 更新履歴

- **v2.0** (2026-01): 現在の実装に基づいて改訂
  - コンテナ名を `kotonoha-bot` に統一
  - データベース名を `sessions.db` に修正
  - `docker compose` コマンドに統一
  - エラーメッセージを実装に合わせて更新
  - 実装箇所の参照を追加
- **v1.1** (2026-01-14): ディレクトリのパーミッションエラーのトラブルシューティングセクションを追加
- **v1.0** (2026-01-14): 初版リリース
