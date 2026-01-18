# システム構成図・技術スタック定義

## 1. システム構成図

### 1.1 全体システム構成

```mermaid
graph TB
    subgraph "Development Environment"
        Dev[Developer PC]
        WSL[WSL2 Ubuntu]
        Dev --> WSL
    end

    subgraph "CI/CD Pipeline"
        GitHub[GitHub Repository]
        GHA[GitHub Actions]
        DockerBuild[Docker Build]
        GHCR[GitHub Container Registry]

        WSL -->|git push| GitHub
        GitHub -->|Trigger| GHA
        GHA -->|Build| DockerBuild
        DockerBuild -->|Push| GHCR
    end

    subgraph "Production: Synology DS1823xs+"
        Watchtower[Watchtower]
        Container[KOTONOHA Container]
        SQLite[(SQLite Database)]

        Watchtower -->|Check Update| GHCR
        Watchtower -->|Restart| Container
        Container <-->|R/W| SQLite
    end

    subgraph "External Services"
        Discord[Discord API]
        LiteLLM[LiteLLM]
        ClaudeHaiku[Claude 3 Haiku<br/>Legacy for Dev]
        ClaudeSonnet[Claude Sonnet 4.5<br/>Default/Balanced]
        ClaudeOpus[Claude Opus 4.5<br/>Production]

        Container <-->|WebSocket/HTTP| Discord
        Container -->|API Call| LiteLLM
        LiteLLM -->|Dev| ClaudeHaiku
        LiteLLM -->|Default| ClaudeSonnet
        LiteLLM -->|Production| ClaudeOpus
    end
```

### 1.2 アプリケーション構成

```mermaid
graph TB
    subgraph "KOTONOHA Bot Application"
        Bot[Bot Client]
        Handler[Message Handler]
        Router[Message Router]
        SessionMgr[Session Manager]
        AIService[AI Service]
        DBService[Database Service]
        Queue[Request Queue]

        Bot --> Handler
        Handler --> Router
        Handler --> Queue
        Router --> SessionMgr
        Router --> AIService
        SessionMgr --> DBService
        AIService --> SessionMgr
    end

    subgraph "Session Management"
        MemSession[ChatSession<br/>Memory]
        SQLiteDB[(SQLite<br/>Persistent)]
        SessionMgr --> MemSession
        SessionMgr --> SQLiteDB
    end

    subgraph "AI Services"
        LiteLLM[LiteLLM<br/>Unified Interface]
        ClaudeHaiku[Claude 3 Haiku<br/>Legacy for Dev]
        ClaudeSonnet[Claude Sonnet 4.5<br/>Default/Balanced]
        ClaudeOpus[Claude Opus 4.5<br/>Production]
        AIService --> LiteLLM
        LiteLLM --> ClaudeHaiku
        LiteLLM -->|Default| ClaudeSonnet
        LiteLLM --> ClaudeOpus
    end
```

## 2. 技術スタック定義

**注**: 詳細なデータフロー図は [詳細設計書](./detailed-design.md#41-メッセージ処理フロー) を参照してください。

### 2.1 技術スタック一覧

| カテゴリ                         | 技術                           | バージョン | 用途                                                            |
| -------------------------------- | ------------------------------ | ---------- | --------------------------------------------------------------- |
| **言語**                         | Python                         | 3.14       | アプリケーション開発                                            |
| **パッケージ管理**               | uv                             | latest     | 依存関係管理                                                    |
| **フレームワーク**               | discord.py                     | latest     | Discord Bot 開発                                                |
| **AI 統合**                      | LiteLLM                        | latest     | マルチ LLM プロバイダー統合                                     |
| **AI（デフォルト）**             | Claude Sonnet API              | 4.5        | デフォルトモデル（バランス型）、モデル: `claude-sonnet-4-5`     |
| **AI（開発）**                   | Claude 3 Haiku API（レガシー） | -          | 開発・テスト用（超低コスト）、モデル: `claude-3-haiku-20240307` |
| **AI（本番）**                   | Claude Opus API                | 4.5        | 本番用（最高品質）、モデル: `claude-opus-4-5`                   |
| **データベース**                 | SQLite                         | 3.x        | 会話履歴の永続化                                                |
| **コンテナ**                     | Docker                         | 24.0.2     | コンテナ化                                                      |
| **コンテナオーケストレーション** | Docker Compose                 | v2.20.1    | コンテナ管理                                                    |
| **CI/CD**                        | GitHub Actions                 | -          | 自動ビルド・デプロイ                                            |
| **コンテナレジストリ**           | GitHub Container Registry      | -          | イメージ保存                                                    |
| **自動更新**                     | Watchtower                     | latest     | コンテナ自動更新                                                |
| **OS**                           | Ubuntu (WSL2)                  | 22.04+     | 開発環境                                                        |
| **本番 OS**                      | DSM (Synology)                 | latest     | 本番環境                                                        |
| **本番 Docker**                  | Docker Engine                  | 24.0.2     | 本番環境のコンテナランタイム                                    |

### 2.2 主要ライブラリ

| ライブラリ     | バージョン | 用途                        |
| -------------- | ---------- | --------------------------- |
| discord.py     | latest     | Discord API クライアント    |
| litellm        | latest     | マルチ LLM プロバイダー統合 |
| python-dotenv  | latest     | 環境変数管理                |
| pytest         | latest     | テストフレームワーク        |
| pytest-asyncio | latest     | 非同期テスト                |

### 2.3 ハードウェア要件

| 項目             | 仕様                                     |
| ---------------- | ---------------------------------------- |
| **CPU**          | AMD Ryzen V1780B (AVX 対応)              |
| **メモリ**       | NAS: 8GB、コンテナ: 最小 512MB、推奨 1GB |
| **ストレージ**   | 最小 1GB（データベース用）               |
| **ネットワーク** | インターネット接続必須                   |

## 3. 環境変数一覧

### 3.0 環境変数の種類

環境変数は以下の 2 種類に分類されます:

- **必須設定**: アプリケーションを起動するために**必ず設定が必要**な項目

  - 設定しないとアプリケーションが起動しません
  - 例: `DISCORD_TOKEN`, `ANTHROPIC_API_KEY`

- **オプション**: 設定しなくても動作します（**デフォルト値が使用されます**）
  - カスタマイズしたい場合のみ設定してください
  - 例: `LLM_TEMPERATURE`（デフォルト: 0.7）、`LOG_LEVEL`（デフォルト: INFO）

### 3.1 必須環境変数

| 変数名          | 説明                 | 例                                         | 必須 |
| --------------- | -------------------- | ------------------------------------------ | ---- |
| `DISCORD_TOKEN` | Discord Bot トークン | `MTIzNDU2Nzg5MDEyMzQ1Njc4OQ.XXXXXX.XXXXXX` | 必須 |
| `LLM_MODEL`     | LLM モデル名         | `anthropic/claude-sonnet-4-5`              | 必須 |

**プロバイダー別 API キー**（使用するプロバイダーに応じて設定）:

| 変数名              | 説明               | 例                                | 必須                       |
| ------------------- | ------------------ | --------------------------------- | -------------------------- |
| `ANTHROPIC_API_KEY` | Anthropic API キー | `sk-ant-XXXXXXXXXXXXXXXXXXXXXXXX` | 開発・調整・本番環境で必須 |

### 3.2 オプション環境変数

#### 3.2.1 LLM 設定

| 変数名                 | 説明                             | デフォルト値                  | 必須       |
| ---------------------- | -------------------------------- | ----------------------------- | ---------- |
| `LLM_MODEL`            | 使用する LLM モデル              | `anthropic/claude-sonnet-4-5` | 必須       |
| `LLM_TEMPERATURE`      | 温度パラメータ                   | `0.7`                         | オプション |
| `LLM_MAX_TOKENS`       | 最大トークン数                   | `2048`                        | オプション |
| `LLM_FALLBACK_MODEL`   | フォールバックモデル             | -                             | オプション |
| `LLM_MAX_RETRIES`      | 最大リトライ回数                 | `3`                           | オプション |
| `LLM_RETRY_DELAY_BASE` | 指数バックオフのベース遅延（秒） | `1.0`                         | オプション |

**リトライ設定について**:

- `LLM_MAX_RETRIES`: 一時的なエラー（HTTP 529 Overloaded、HTTP 429 Rate Limit など）に対する最大リトライ回数
- `LLM_RETRY_DELAY_BASE`: 指数バックオフのベース遅延時間（秒）
  - リトライ間隔: 1 回目 → 1 秒、2 回目 → 2 秒、3 回目 → 4 秒
  - 例: `LLM_RETRY_DELAY_BASE=1.0` の場合、1 秒 → 2 秒 → 4 秒

**フェーズ別推奨モデル**:

| フェーズ   | `LLM_MODEL` の値                    | 説明                                                       |
| ---------- | ----------------------------------- | ---------------------------------------------------------- |
| デフォルト | `anthropic/claude-sonnet-4-5`       | バランス型（デフォルト）、\$3/input MTok, \$15/output MTok |
| 開発       | `anthropic/claude-3-haiku-20240307` | 超低コストでの開発・テスト（制限なし）                     |
| 本番       | `anthropic/claude-opus-4-5`         | 最高品質の本番運用（\$5/input MTok, \$25/output MTok）     |

**開発用モデル（Claude 3 Haiku（レガシー））のコスト**（[公式価格表](https://platform.claude.com/docs/en/about-claude/models/overview)）:

- 入力: \$0.25/100 万トークン、出力: \$1.25/100 万トークン
- 1 回あたり約 0.075 セント（入力 500 トークン、出力 500 トークンの場合）
- 月間コスト例: 1,000 回で約\$0.75（約 113 円）、5,000 回で約\$3.75（約 563 円）
- 無料枠の制限がなく、開発から本番まで同じプロバイダーで統一可能

**Claude モデル比較**（2026 年 1 月現在）:

- **Haiku 4.5**: \$1/input MTok, \$5/output MTok（最速、低コスト）
- **Sonnet 4.5**: \$3/input MTok, \$15/output MTok（バランス型、推奨）
- **Opus 4.5**: \$5/input MTok, \$25/output MTok（最高品質）

#### 3.2.2 データベース設定

| 変数名          | 説明                     | デフォルト値           | 必須       |
| --------------- | ------------------------ | ---------------------- | ---------- |
| `DATABASE_NAME` | データベースファイル名   | `sessions.db`          | オプション |
| `DATABASE_PATH` | データベースファイルパス | `./data/DATABASE_NAME` | オプション |

**注意**: `DATABASE_PATH` が設定されていない場合、`./data/DATABASE_NAME` が使用されます。

#### 3.2.3 セッション設定

| 変数名                  | 説明                           | デフォルト値 | 必須       |
| ----------------------- | ------------------------------ | ------------ | ---------- |
| `SESSION_TIMEOUT_HOURS` | セッションタイムアウト（時間） | `24`         | オプション |
| `MAX_SESSIONS`          | メモリ内最大セッション数       | `100`        | オプション |

#### 3.2.4 聞き耳型設定

| 変数名                                        | 説明                                              | デフォルト値                 | 必須       |
| --------------------------------------------- | ------------------------------------------------- | ---------------------------- | ---------- |
| `EAVESDROP_ENABLED_CHANNELS`                  | 聞き耳型を有効にするチャンネル ID（カンマ区切り） | -                            | オプション |
| `EAVESDROP_JUDGE_MODEL`                       | 判定用モデル                                      | `anthropic/claude-haiku-4-5` | オプション |
| `EAVESDROP_BUFFER_SIZE`                       | 会話ログバッファサイズ                            | `20`                         | オプション |
| `EAVESDROP_MIN_MESSAGES`                      | 判定・応答生成に必要な最低メッセージ数            | `3`                          | オプション |
| `EAVESDROP_MIN_INTERVENTION_INTERVAL_MINUTES` | 介入の最小間隔（分）                              | `10`                         | オプション |

#### 3.2.5 ログ設定

| 変数名             | 説明                                                         | デフォルト値             | 必須       |
| ------------------ | ------------------------------------------------------------ | ------------------------ | ---------- |
| `LOG_LEVEL`        | ログレベル (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) | `INFO`                   | オプション |
| `LOG_FILE`         | ログファイルパス                                             | `/app/logs/kotonoha.log` | オプション |
| `LOG_MAX_SIZE`     | ログファイル最大サイズ（MB）                                 | `10`                     | オプション |
| `LOG_BACKUP_COUNT` | ログバックアップ数                                           | `5`                      | オプション |

#### 3.2.6 レート制限設定

| 変数名                 | 説明                                | デフォルト値 | 必須       |
| ---------------------- | ----------------------------------- | ------------ | ---------- |
| `RATE_LIMIT_CAPACITY`  | レート制限の上限値（リクエスト/分） | `50`         | オプション |
| `RATE_LIMIT_REFILL`    | 補充レート（リクエスト/秒）         | `0.8`        | オプション |
| `RATE_LIMIT_WINDOW`    | 監視ウィンドウ（秒）                | `60`         | オプション |
| `RATE_LIMIT_THRESHOLD` | 警告閾値（使用率、0.0-1.0）         | `0.9`        | オプション |

#### 3.2.7 ヘルスチェック設定

| 変数名                 | 説明                      | デフォルト値 | 必須       |
| ---------------------- | ------------------------- | ------------ | ---------- |
| `HEALTH_CHECK_ENABLED` | ヘルスチェックの有効/無効 | `true`       | オプション |

#### 3.2.8 その他設定

| 変数名               | 説明                   | デフォルト値 | 必須       |
| -------------------- | ---------------------- | ------------ | ---------- |
| `BOT_PREFIX`         | コマンドプレフィックス | `!`          | オプション |
| `MESSAGE_MAX_LENGTH` | メッセージ最大長       | `2000`       | オプション |

#### 3.2.9 CI/CD 設定

| 変数名              | 説明                             | デフォルト値 | 必須       |
| ------------------- | -------------------------------- | ------------ | ---------- |
| `GITHUB_REPOSITORY` | GitHub リポジトリ名              | -            | オプション |
| `GITHUB_USERNAME`   | GitHub ユーザー名（GHCR 認証用） | -            | オプション |
| `GITHUB_TOKEN`      | GitHub Personal Access Token     | -            | オプション |

**GitHub Container Registry (GHCR) 認証について**:

- `GITHUB_TOKEN`: GitHub Personal Access Token（`ghp_` で始まる）
- GHCR からプライベートイメージをプルする場合に必要
- 詳細は [Phase 3 実装ガイド](../implementation/phases/phase03.md) を参照

#### 3.2.10 Watchtower 設定

| 変数名                        | 説明                               | デフォルト値 | 必須       |
| ----------------------------- | ---------------------------------- | ------------ | ---------- |
| `WATCHTOWER_CLEANUP`          | 古いイメージを自動削除             | `true`       | オプション |
| `WATCHTOWER_POLL_INTERVAL`    | イメージ更新チェック間隔（秒）     | `300`        | オプション |
| `WATCHTOWER_LABEL_ENABLE`     | ラベルで対象コンテナを制限         | `true`       | オプション |
| `WATCHTOWER_NOTIFICATIONS`    | 通知方法（shoutrrr）               | `shoutrrr`   | オプション |
| `WATCHTOWER_NOTIFICATION_URL` | 通知先 URL（Discord Webhook など） | -            | オプション |
| `WATCHTOWER_SCHEDULE`         | cron 形式でのスケジュール          | -            | オプション |
| `WATCHTOWER_ROLLING_RESTART`  | 一度に 1 コンテナずつ更新          | `false`      | オプション |

**Watchtower 通知 URL の設定方法**:

- **Discord Webhook**: `discord://WEBHOOK_TOKEN@WEBHOOK_ID`
  - 詳細な手順は [デプロイメント・運用フロー](../operations/deployment-operations.md) を参照
- **Slack**: `slack://TOKEN@WORKSPACE/CHANNEL`
- **Email**: `smtp://USERNAME:PASSWORD@SMTP_HOST:587/?from=FROM_EMAIL&to=TO_EMAIL`
- **Telegram**: `telegram://BOT_TOKEN@telegram?chats=CHAT_ID`

**Watchtower について**:

Watchtower は Docker コンテナの自動更新ツールです。GitHub Container Registry (GHCR) から新しいイメージを定期的にチェックし、更新があれば自動的にコンテナを再起動して最新版に更新します。

詳細は [デプロイメント・運用フロー](../operations/deployment-operations.md) の「1.3 Watchtower について」セクションを参照してください。

#### 3.2.11 Docker/NAS デプロイ設定

| 変数名                  | 説明                 | デフォルト値 | 必須       |
| ----------------------- | -------------------- | ------------ | ---------- |
| `BACKUP_RETENTION_DAYS` | バックアップ保持日数 | `7`          | オプション |

### 3.3 環境変数設定例

```bash
# .env ファイル例（開発環境）

# Discord
DISCORD_TOKEN=your_discord_bot_token_here

# LLM 設定（LiteLLM）
# デフォルト: anthropic/claude-sonnet-4-5（バランス型）
# 開発用（超低コスト）: anthropic/claude-3-haiku-20240307
LLM_MODEL=anthropic/claude-sonnet-4-5
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2048

# API キー
ANTHROPIC_API_KEY=your_anthropic_api_key_here  # 開発・調整・本番環境用

# Database
DATABASE_NAME=sessions.db

# Session
SESSION_TIMEOUT_HOURS=24
MAX_SESSIONS=100

# Eavesdrop
EAVESDROP_ENABLED_CHANNELS=123456789012345678,987654321098765432
EAVESDROP_JUDGE_MODEL=anthropic/claude-haiku-4-5
EAVESDROP_BUFFER_SIZE=20
EAVESDROP_MIN_MESSAGES=3
EAVESDROP_MIN_INTERVENTION_INTERVAL_MINUTES=10

# Rate Limit
RATE_LIMIT_CAPACITY=50
RATE_LIMIT_REFILL=0.8
RATE_LIMIT_WINDOW=60
RATE_LIMIT_THRESHOLD=0.9

# Logging
LOG_LEVEL=INFO
LOG_FILE=/app/logs/kotonoha.log
LOG_MAX_SIZE=10
LOG_BACKUP_COUNT=5

# Bot
BOT_PREFIX=!

# Health Check
HEALTH_CHECK_ENABLED=true
```

```bash
# .env ファイル例（本番環境）

# Discord
DISCORD_TOKEN=your_discord_bot_token_here

# LLM 設定（LiteLLM）- 本番は Claude Opus 4.5
LLM_MODEL=anthropic/claude-opus-4-5
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2048
LLM_FALLBACK_MODEL=anthropic/claude-3-haiku-20240307  # フォールバック用（本番でOpusがダウンした場合）

# API キー
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Database
DATABASE_NAME=sessions.db

# Session
SESSION_TIMEOUT_HOURS=24
MAX_SESSIONS=100

# Eavesdrop
EAVESDROP_ENABLED_CHANNELS=123456789012345678,987654321098765432
EAVESDROP_JUDGE_MODEL=anthropic/claude-haiku-4-5
EAVESDROP_BUFFER_SIZE=20
EAVESDROP_MIN_MESSAGES=3
EAVESDROP_MIN_INTERVENTION_INTERVAL_MINUTES=10

# Rate Limit
RATE_LIMIT_CAPACITY=50
RATE_LIMIT_REFILL=0.8
RATE_LIMIT_WINDOW=60
RATE_LIMIT_THRESHOLD=0.9

# Logging
LOG_LEVEL=INFO
LOG_FILE=/app/logs/kotonoha.log
LOG_MAX_SIZE=10
LOG_BACKUP_COUNT=5

# Bot
BOT_PREFIX=!

# Health Check
HEALTH_CHECK_ENABLED=true
```

## 4. ボリューム設計（Docker）

### 4.1 ボリューム構成

```yaml
volumes:
  kotonoha_data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /volume1/docker/kotonoha/data
  kotonoha_logs:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /volume1/docker/kotonoha/logs
  kotonoha_backups:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /volume1/docker/kotonoha/backups
```

### 4.2 マウントポイント

| ホストパス                         | コンテナパス   | 用途                 | 永続化     |
| ---------------------------------- | -------------- | -------------------- | ---------- |
| `/volume1/docker/kotonoha/data`    | `/app/data`    | SQLite データベース  | 必須       |
| `/volume1/docker/kotonoha/logs`    | `/app/logs`    | ログファイル         | オプション |
| `/volume1/docker/kotonoha/backups` | `/app/backups` | バックアップファイル | 必須       |

### 4.3 Docker Compose 設定例

```yaml
services:
  kotonoha-bot:
    build:
      context: .
      dockerfile: Dockerfile
    image: ghcr.io/${GITHUB_REPOSITORY:-your-username/kotonoha-bot}:latest
    container_name: kotonoha-bot
    restart: unless-stopped
    user: root
    stop_grace_period: 30s

    env_file:
      - .env

    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./backups:/app/backups
      - ./prompts:/app/prompts

    networks:
      - kotonoha-network

    ports:
      - "127.0.0.1:8081:8080"

    healthcheck:
      test:
        [
          "CMD",
          "python",
          "-c",
          "import urllib.request; "
          "urllib.request.urlopen('http://localhost:8080/health', "
          "timeout=5).read()",
        ]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s

    deploy:
      resources:
        limits:
          memory: 512M

    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "5"
    labels:
      - "com.centurylinklabs.watchtower.enable=${WATCHTOWER_ENABLED:-true}"

  watchtower:
    image: containrrr/watchtower:latest
    container_name: watchtower
    restart: unless-stopped
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    env_file:
      - .env
    environment:
      - DOCKER_API_VERSION=${DOCKER_API_VERSION:-}
      - WATCHTOWER_CLEANUP=${WATCHTOWER_CLEANUP:-true}
      - WATCHTOWER_POLL_INTERVAL=${WATCHTOWER_POLL_INTERVAL:-300}
      - WATCHTOWER_LABEL_ENABLE=${WATCHTOWER_LABEL_ENABLE:-true}
      - WATCHTOWER_NOTIFICATIONS=${WATCHTOWER_NOTIFICATIONS:-shoutrrr}
      - WATCHTOWER_NOTIFICATION_URL=${WATCHTOWER_NOTIFICATION_URL:-}
    networks:
      - kotonoha-network

networks:
  kotonoha-network:
    driver: bridge
```

### 4.4 ボリュームの権限設定

```bash
# データディレクトリの権限設定
chmod 755 /volume1/docker/kotonoha/data
chmod 755 /volume1/docker/kotonoha/logs
chmod 755 /volume1/docker/kotonoha/backups

# 所有者設定（コンテナ内のユーザーIDに合わせる）
chown -R 1000:1000 /volume1/docker/kotonoha/data
chown -R 1000:1000 /volume1/docker/kotonoha/logs
chown -R 1000:1000 /volume1/docker/kotonoha/backups
```

### 4.5 バックアップ戦略

| 項目                 | 設定                           |
| -------------------- | ------------------------------ |
| **バックアップ頻度** | 1 日 1 回（深夜 0 時）         |
| **保存期間**         | 7 日分                         |
| **保存場所**         | `/app/backups`                 |
| **ファイル名形式**   | `kotonoha_YYYYMMDD_HHMMSS.db`  |
| **自動削除**         | 7 日以上古いファイルを自動削除 |

## 5. ディレクトリ構造

### 5.1 プロジェクト構造

```console
kotonoha-bot/
├── .github/
│   └── workflows/
│       └── docker-build.yml      # GitHub Actionsワークフロー
├── docs/
│   ├── README.md                 # ドキュメントインデックス
│   ├── getting-started.md        # クイックスタートガイド
│   ├── requirements/             # 要件定義
│   ├── architecture/             # アーキテクチャ設計
│   ├── specifications/           # 仕様書
│   ├── implementation/           # 実装関連
│   ├── testing/                  # テスト
│   ├── operations/               # 運用
│   └── development/              # 開発者向け
├── prompts/                      # プロンプトファイル（Markdown）
│   ├── system_prompt.md                    # システムプロンプト
│   ├── eavesdrop_judge_prompt.md           # 聞き耳型判定用プロンプト
│   └── eavesdrop_response_prompt.md       # 聞き耳型応答生成用プロンプト
├── src/
│   └── kotonoha_bot/
│       ├── __init__.py
│       ├── main.py               # エントリーポイント
│       ├── config.py             # 設定管理
│       ├── health.py             # ヘルスチェック
│       ├── bot/
│       │   ├── __init__.py
│       │   ├── client.py         # Discord Bot クライアント
│       │   └── handlers.py       # メッセージハンドラー
│       ├── ai/
│       │   ├── __init__.py
│       │   ├── provider.py       # AI プロバイダー抽象クラス
│       │   ├── litellm_provider.py  # LiteLLM統合実装
│       │   └── prompts.py        # プロンプト読み込みユーティリティ
│       ├── db/
│       │   ├── __init__.py
│       │   └── sqlite.py         # SQLite管理
│       ├── session/
│       │   ├── __init__.py
│       │   ├── manager.py        # セッション管理（ハイブリッド）
│       │   └── models.py         # ChatSession, Message モデル
│       ├── router/
│       │   ├── __init__.py
│       │   └── message_router.py # 会話の契機判定
│       ├── eavesdrop/
│       │   ├── __init__.py
│       │   ├── llm_judge.py      # LLM判断
│       │   └── conversation_buffer.py  # 会話バッファ管理
│       ├── commands/
│       │   └── chat.py           # チャットコマンド
│       ├── rate_limit/
│       │   ├── __init__.py
│       │   ├── request_queue.py  # リクエストキュー
│       │   ├── monitor.py        # レート制限監視
│       │   └── token_bucket.py   # トークンバケット
│       ├── errors/
│       │   ├── __init__.py
│       │   ├── database_errors.py
│       │   └── discord_errors.py
│       └── utils/
│           ├── message_formatter.py
│           └── message_splitter.py
├── data/
│   └── kotonoha.db               # SQLiteデータベース（.gitignore）
├── Dockerfile
├── docker-compose.yml            # 開発用（オプション）
├── .env.example                  # 環境変数テンプレート
├── pyproject.toml
└── README.md
```

### 5.2 Dockerfile 構成

- **Multi-stage build**: ビルドステージとランタイムステージを分離
- **ベースイメージ**: Python 3.14 slim
- **パッケージマネージャー**: uv（依存関係管理）
- **非 root ユーザー**: `botuser` (UID/GID 1000) で実行
- **ヘルスチェック**: HTTP エンドポイント (`/health`) で監視
- **データボリュームマウントポイント**: `/app/data`, `/app/logs`, `/app/backups`
- **タイムゾーン**: Asia/Tokyo

---

**作成日**: 2026 年 1 月 14 日
**バージョン**: 1.0
**作成者**: kotonoha-bot 開発チーム
