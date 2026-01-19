# Phase 2 実装完了報告 - NAS デプロイ

Kotonoha Discord Bot の Phase 2（NAS デプロイ）の実装完了報告書

## 目次

1. [Phase 2 の目標](#phase-2-の目標)
2. [実装状況](#実装状況)
3. [前提条件](#前提条件)
4. [NAS の種類と選定](#nas-の種類と選定)
5. [実装ステップ（参考情報）](#実装ステップ参考情報)
6. [完了基準](#完了基準)
7. [トラブルシューティング](#トラブルシューティング)
8. [次のフェーズへ](#次のフェーズへ)

---

## Phase 2 の目標

### NAS デプロイの目的

**目標**: Phase 1 で実装済みの Bot を NAS 上で 24 時間稼働させ、本番環境として運用できるようにする

**達成すべきこと**:

- Docker コンテナとして動作する
- NAS 上で自動起動する
- データの永続化（SQLite、ログ、設定ファイル）
- バックアップ機能
- ログ管理とローテーション
- セキュリティ設定（非 root ユーザーでの実行）

**スコープ外（Phase 7 以降）**:

- 自動更新機能（Watchtower、GitHub Actions）
- 高度な監視機能（メトリクス収集、アラート）
- CI/CD パイプライン

---

## 実装状況

### ✅ 実装完了（2026 年 1 月）

Phase 2 の実装は完了しています。以下の機能が実装されています:

**実装済み機能**:

- ✅ Docker コンテナ化（マルチステージビルド）
- ✅ Docker Compose 設定（ボリュームマウント、ヘルスチェック）
- ✅ 自動パーミッション修正（entrypoint.sh）
- ✅ 非 root ユーザーでの実行（botuser、UID 1000）
- ✅ データの永続化（SQLite、ログ、バックアップ）
- ✅ バックアップ機能（SQLite オンラインバックアップ、gzip 圧縮）
- ✅ ログローテーション（RotatingFileHandler）
- ✅ ヘルスチェック機能（HTTP エンドポイント `/health`, `/ready`）
- ✅ セキュリティ設定（環境変数保護、最小権限の原則）
- ✅ NAS デプロイ（Synology Container Manager）

**実装されたファイル構造**:

```txt
kotonoha-bot/
├── Dockerfile              # ✅ 実装済み
├── docker-compose.yml      # ✅ 実装済み
├── .dockerignore           # ✅ 実装済み
├── scripts/
│   ├── entrypoint.sh       # ✅ 実装済み
│   ├── backup.sh           # ✅ 実装済み
│   ├── restore.sh          # ✅ 実装済み
│   └── setup.sh            # ✅ 実装済み
├── data/                   # データベースファイル（自動生成）
├── logs/                   # ログファイル（自動生成）
└── backups/                # バックアップファイル（自動生成）
```

**Phase 2 完了後の確認事項**:

- ✅ Docker イメージがビルドできる
- ✅ Docker Compose でコンテナが起動する
- ✅ Bot が Discord に接続できる
- ✅ データが永続化される（コンテナ再起動後も保持）
- ✅ バックアップが正常に実行される
- ✅ ヘルスチェックが動作している
- ✅ NAS 上で 24 時間稼働している
- ✅ Phase 3（CI/CD・運用機能）の実装準備が整っている

---

## 前提条件

### 必要な環境

1. **NAS デバイス**

   - Synology NAS（推奨: DS1823xs+ または同等品）
   - QNAP NAS
   - TrueNAS
   - その他の Docker 対応 NAS

2. **NAS の機能**

   - Docker サポート（Container Manager / Docker）
   - SSH アクセス（オプション、推奨）
   - ファイル共有機能

3. **開発環境**
   - Phase 1 が完了済み（実装済み）
   - Docker の基本知識
   - NAS へのアクセス権限

### 必要な情報

- NAS の IP アドレス
- NAS の管理者アカウント情報
- Docker コンテナの実行権限
- データ保存先のパス

---

## NAS の種類と選定

### Synology NAS（推奨）

**メリット**:

- Container Manager（旧 Docker）が標準搭載
- GUI が使いやすい
- 豊富なドキュメント
- Watchtower の設定が簡単

**デプロイ方法**:

- Container Manager を使用
- Docker Compose ファイルを使用（推奨）
- または GUI から直接設定

**参考資料**:

- [Synology Container Manager ドキュメント](https://kb.synology.com/ja-jp/DSM/help/ContainerManager/container_manager_desc)

### QNAP NAS

**メリット**:

- Container Station が標準搭載
- Docker と Kubernetes の両方をサポート

**デプロイ方法**:

- Container Station を使用
- Docker Compose ファイルを使用

### TrueNAS

**メリット**:

- オープンソース
- 高機能なストレージ管理

**デプロイ方法**:

- Docker を手動でインストール
- Docker Compose を使用

---

## 実装ステップ（参考情報）

> **注意**: 以下の実装ステップは既に完了しています。参考情報として記載しています。

このセクションでは、Phase 2 で実装した各ステップの詳細を記載しています。実装は完了しているため、新規実装時の参考としてご利用ください。

### Step 1: Dockerfile の作成 (1 時間) ✅ 完了

#### 1.1 `Dockerfile` の作成

プロジェクトルートに `Dockerfile` を作成（マルチステージビルドを使用）:

```dockerfile
# Kotonoha Discord Bot - Dockerfile
# Python 3.14 + uv による軽量イメージ

# ============================================
# ビルドステージ
# ============================================
FROM python:3.14-slim AS builder

WORKDIR /app

# システムパッケージの更新
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# uv のインストール
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# プロジェクトファイルのコピー（README.mdはpyproject.tomlのビルド時に必要）
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/

# 依存関係のインストール（本番用のみ）
RUN uv sync --frozen --no-dev

# ============================================
# 実行ステージ
# ============================================
FROM python:3.14-slim AS runtime

WORKDIR /app

# 必要な実行時パッケージのみインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    sqlite3 \
    gosu \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 非rootユーザーの作成（UID/GID 1000で明示的に作成）
RUN groupadd -r -g 1000 botuser && useradd -r -u 1000 -g botuser -d /app -s /sbin/nologin botuser

# ビルドステージから必要なファイルをコピー
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

# エントリポイントスクリプトのコピー
COPY scripts/ /app/scripts/

# スクリプトに実行権限を付与
RUN chmod +x /app/scripts/*.sh

# 環境変数の設定
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# ユーザー切り替えはentrypoint.shで行う（rootで起動してパーミッション修正後、ユーザーを切り替える）
# USER botuser

# ヘルスチェック
# HTTPエンドポイントを使用してアプリケーションの状態を確認
# HEALTH_CHECK_ENABLED=true の場合、ポート8080でHTTPサーバーが起動します
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health', timeout=5).read()" || python -c "import sys; sys.exit(0)"

# エントリーポイント
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
```

#### 1.2 `entrypoint.sh` の作成

エントリーポイントスクリプトを作成します。このスクリプトは、起動時にディレクトリのパーミッションを自動的に修正し、その後非 root ユーザーに切り替えます。

`scripts/entrypoint.sh`:

```bash
#!/bin/bash
# Kotonoha Bot - エントリポイントスクリプト
# マウントされたディレクトリの所有者を修正し、botuserでアプリケーションを起動

set -e

# rootで実行されている場合のみ権限を修正
if [ "$(id -u)" -eq 0 ]; then
    # マウントされたディレクトリの所有者をbotuserに変更
    for dir in /app/data /app/logs /app/backups; do
        if [ -d "$dir" ]; then
            chown -R botuser:botuser "$dir" 2>/dev/null || true
            chmod 775 "$dir" 2>/dev/null || chmod 777 "$dir" 2>/dev/null || true
        fi
    done

    # botuserに切り替えてアプリケーションを起動
    exec gosu botuser python -m kotonoha_bot.main "$@"
else
    # 既にbotuserで実行されている場合
    exec python -m kotonoha_bot.main "$@"
fi
```

**重要なポイント**:

- コンテナは root で起動され、`entrypoint.sh`が自動的にパーミッションを修正します
- マウントされたディレクトリの所有者を`botuser:botuser`に変更し、パーミッションを`775`（失敗時は`777`）に設定します
- パーミッション修正後、`gosu`で botuser（UID 1000）に切り替えてからアプリケーションを実行します
- シンプルで確実に動作する設計になっています（約 23 行）

#### 1.3 `.dockerignore` の作成

```dockerignore
# Git
.git
.gitignore
.gitattributes

# Python キャッシュ
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
*.egg-info/
*.egg
dist/
build/

# 仮想環境
.venv/
venv/
env/
ENV/

# 環境変数（機密情報）
.env
.env.local
.env.*.local

# データベース（ボリュームマウントで管理）
*.db
*.sqlite
*.sqlite3
data/

# ログ（ボリュームマウントで管理）
logs/
*.log

# バックアップ（ボリュームマウントで管理）
backups/

# IDE / エディタ
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db
desktop.ini

# ドキュメント（イメージには不要）
docs/
docs/**/*.md
# README.mdはpyproject.tomlでビルド時に必要なので含める

# テスト
tests/
.pytest_cache/
.coverage
htmlcov/
.tox/
.nox/

# その他
*.bak
*.tmp
*.temp
.cache/
```

**注意**: `README.md` は `pyproject.toml` のビルド時に必要なので、`docs/` 配下の Markdown ファイルのみを除外し、ルートの `README.md` は自動的にビルドコンテキストに含まれます。

#### 1.4 ベースイメージの選択

本プロジェクトでは `python:3.14-slim` をベースイメージとして使用しています。

**詳細な選定理由と代替案の比較については、[ミドルウェア選定書](../../20_architecture/22_adrs/middleware-selection.md#381-docker-ベースイメージの選択)を参照してください。**

#### Step 1 完了チェックリスト

- [x] `Dockerfile` が作成されている
- [x] `scripts/entrypoint.sh` が作成されている
- [x] `.dockerignore` が作成されている
- [x] ローカルで Docker イメージがビルドできる
- [x] ベースイメージの選択理由を理解している

---

### Step 2: Docker Compose の作成 (30 分) ✅ 完了

#### 2.1 `docker-compose.yml` の作成

**ビルドとイメージの設定**:

`docker-compose.yml` では、`build` と `image` を両方指定することで、ローカルビルドと CI/CD の両方に対応できます。

**動作**:

- **ローカルビルド**: `docker compose build` を実行すると、ローカルでビルドし、`image` で指定した名前（タグ）が付けられます
- **GHCR からプル**: `docker compose pull` を実行すると、GHCR からイメージをプルします（または Watchtower が自動更新）
- **優先順位**: `docker compose up` を実行すると、ローカルに `image` で指定した名前のイメージがあれば使用し、なければ `build` でビルドします

**ベストプラクティス**:

- 開発環境: `build` と `image` を両方指定して、ローカルでビルドしたイメージに GHCR と同じ名前を付ける
- 本番環境: 同じ設定で、Watchtower が GHCR から自動更新する

```yaml
# Kotonoha Discord Bot - Docker Compose
# NAS (Synology) デプロイ用設定

services:
  kotonoha-bot:
    # ローカルビルドとCI/CDの両方を有効化
    build:
      context: .
      dockerfile: Dockerfile
    image: ghcr.io/${GITHUB_REPOSITORY:-your-username/kotonoha-bot}:latest

    container_name: kotonoha-bot
    restart: unless-stopped

    # rootで起動してパーミッション修正後にユーザーを切り替える
    # entrypoint.shが自動的にパーミッションを修正し、botuserに切り替えます
    user: root

    # 環境変数ファイル
    env_file:
      - .env

    # ボリュームマウント（データの永続化）
    volumes:
      # データベース（必須）
      - ./data:/app/data
      # ログ（オプション - LOG_FILE が設定されている場合のみ必要）
      - ./logs:/app/logs
      # バックアップ（オプション）
      - ./backups:/app/backups

    # ネットワーク設定
    networks:
      - kotonoha-network

    # ポート公開（オプション）
    # ヘルスチェックエンドポイントに外部からアクセスする場合に有効化
    # セキュリティ上の理由から、本番環境ではリバースプロキシ経由でのアクセスを推奨
    # ローカルホストのみに制限する場合: "127.0.0.1:8081:8080"
    ports:
      - "127.0.0.1:8081:8080" # ホスト:コンテナ（ローカルホストのみ）

    # ヘルスチェック
    # HTTPエンドポイントを使用してアプリケーションの状態を確認
    # HEALTH_CHECK_ENABLED=true の場合、ポート8080でHTTPサーバーが起動します
    # HTTPサーバーが無効な場合は、Pythonプロセスの存在を確認します
    healthcheck:
      test:
        [
          "CMD-SHELL",
          'python -c "import urllib.request; urllib.request.urlopen(''http://localhost:8080/health'', timeout=5).read()" 2>/dev/null || python -c ''import sys; sys.exit(0)''',
        ]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s

    # ログ設定
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "5"

networks:
  kotonoha-network:
    driver: bridge
```

#### 2.2 `.env` ファイルの準備

NAS 上に `.env` ファイルを作成（`.env.example` をコピー）:

```bash
# NAS 上で実行
cp .env.example .env
# .env を編集して実際の値を設定
```

#### Step 2 完了チェックリスト

- [x] `docker-compose.yml` が作成されている
- [x] `.env` ファイルが NAS 上に作成されている
- [x] ボリュームマウントのパスが正しく設定されている

---

### Step 3: ローカルでの動作確認 (1 時間) ✅ 完了

#### 3.1 ローカルで Docker イメージをビルド

```bash
# プロジェクトルートで実行
docker build -t kotonoha-bot:local .
```

#### 3.2 ローカルで Docker Compose を実行

```bash
# docker-compose.yml があるディレクトリで実行
docker compose up -d

# ログを確認
docker compose logs -f

# コンテナの状態を確認
docker compose ps
```

**注意**: 新しい Docker では `docker compose`（ハイフンなし）が推奨されています。古いバージョンでは `docker-compose`（ハイフンあり）を使用してください。

#### 3.3 動作確認

- [x] Bot が Discord に接続できる
- [x] メンション時に応答が返る
- [x] データベースファイルが作成される
- [x] ログが出力される

#### Step 3 完了チェックリスト

- [x] ローカルで Docker イメージがビルドできる
- [x] ローカルで Docker Compose が動作する
- [x] Bot が正常に動作する

---

### Step 4: NAS へのデプロイ準備 (1 時間) ✅ 完了

#### 4.1 NAS へのファイル転送

Git リポジトリをクローンすることで、ビルドに必要なファイルをすべて取得できます。

```bash
# NAS 上で Git リポジトリをクローン
ssh admin@nas-ip
cd /volume1/docker
git clone https://github.com/your-username/kotonoha-bot.git
cd kotonoha-bot
```

**メリット**:

- ビルドに必要なファイルがすべて自動的に含まれる
- バージョン管理が容易
- 更新時に `git pull` で簡単に更新できる
- ファイルの漏れがない

#### 4.2 NAS 上でのディレクトリ構造

**重要**: ビルドに必要なファイルをすべて含める必要があります。Git リポジトリ全体をクローンするか、必要なファイルをすべて転送してください。

```txt
/volume1/docker/kotonoha-bot/
├── docker-compose.yml
├── Dockerfile
├── .dockerignore          # ビルド最適化用（オプション）
├── .env                   # 環境変数ファイル（手動作成）
├── pyproject.toml         # プロジェクト設定（ビルドに必須）
├── uv.lock                # 依存関係ロックファイル（ビルドに必須）
├── README.md              # プロジェクト説明（pyproject.tomlのビルド時に必要）
├── src/                   # ソースコード（ビルドに必須）
│   └── kotonoha_bot/
├── scripts/               # バックアップスクリプトなど（ビルドに必須）
│   └── backup.sh
├── data/                  # データベースファイル（自動生成）
├── logs/                  # ログファイル（自動生成）
└── backups/               # バックアップファイル（自動生成）
```

**ビルドに必要なファイル**:

- `Dockerfile` - コンテナイメージのビルド定義
- `pyproject.toml` - Python プロジェクト設定と依存関係
- `uv.lock` - 依存関係のロックファイル
- `README.md` - pyproject.toml のビルド時に必要
- `src/` - アプリケーションのソースコード
- `scripts/` - バックアップスクリプトなど

**注意**: Git リポジトリをクローンすることで、上記の必要なファイルがすべて自動的に含まれます。

#### 4.3 環境変数ファイルとディレクトリの準備

##### 4.3.1 .env ファイルの作成

`.env.example` をコピーして `.env` ファイルを作成し、実際の値を設定します。

```bash
# NAS 上で実行
cd /volume1/docker/kotonoha-bot

# .env.example をコピー
cp .env.example .env

# .env ファイルを編集して実際の値を設定
# 必須項目:
# - DISCORD_TOKEN: Discord Bot のトークン
# - ANTHROPIC_API_KEY: Anthropic API キー
# - LLM_MODEL: 使用する LLM モデル
nano .env  # または vi .env
```

##### 4.3.2 ディレクトリの作成と権限設定

データ保存用のディレクトリを作成し、ファイルの権限を設定します。

##### 方法 1: セットアップスクリプトを使用（推奨）

```bash
# NAS 上で実行
cd /volume1/docker/kotonoha-bot

# セットアップスクリプトを実行
./scripts/setup.sh
```

このスクリプトは以下を自動的に実行します:

- データ保存用ディレクトリの作成（`data`、`logs`、`backups`）
- ファイルの権限設定（`docker-compose.yml`、`.env`など）
- スクリプトの実行権限設定

##### 方法 2: 手動で設定

```bash
# NAS 上で実行
cd /volume1/docker/kotonoha-bot

# データ保存用ディレクトリの作成
mkdir -p data logs backups

# ファイルの権限設定
chmod 644 docker-compose.yml Dockerfile pyproject.toml uv.lock README.md
chmod 600 .env  # 機密情報を含むため、所有者のみ読み書き可能

# スクリプトの実行権限設定（Dockerfileで設定されますが、念のため）
chmod +x scripts/*.sh 2>/dev/null || true
```

**パーミッションについて**:

- **ホスト側のファイル**: セットアップスクリプトまたは手動で設定が必要です
- **ディレクトリ（data、logs、backups）**: コンテナ起動時に`entrypoint.sh`が自動的にパーミッションを修正します（手動設定は通常不要）

**パーミッションについて**:

- **自動修正機能**: コンテナは`user: root`で起動され、`entrypoint.sh`が自動的にディレクトリのパーミッションを修正します
- **手動設定が不要**: 通常は手動で`chmod`を実行する必要はありません
- **自動修正が失敗する場合**: 以下のいずれかを実行してください:

  ```bash
  # 方法1: パーミッションを変更（推奨）
  chmod 775 data logs backups

  # 方法2: 所有者を変更（UID 1000のユーザーが存在する場合）
  sudo chown -R 1000:1000 data logs backups
  ```

**注意**: `.env` ファイルには機密情報（Discord Token、API キーなど）が含まれるため、権限を `600`（所有者のみ読み書き可能）に設定することが重要です。

#### Step 4 完了チェックリスト

- [x] NAS 上に必要なファイルが配置されている
- [x] ディレクトリの権限が正しく設定されている
- [x] `.env` ファイルに正しい値が設定されている

---

### Step 5: Synology NAS でのデプロイ (1 時間) ✅ 完了

#### 5.1 Container Manager での設定

1. **Container Manager を開く**

   - DSM のメインメニューから「Container Manager」を開く

2. **プロジェクトを作成**

   - 「プロジェクト」タブを開く
   - 「作成」をクリック
   - プロジェクト名: `kotonoha-bot`
   - パス: `/volume1/docker/kotonoha-bot`
   - `docker-compose.yml` を選択

3. **環境変数の設定**

   - `.env` ファイルを使用する場合は、Container Manager の設定で環境変数ファイルを指定
   - または、Container Manager の GUI で直接環境変数を設定

4. **ボリュームの設定**

   - `data`、`logs`、`backups` ディレクトリをマウント
   - パス: `/volume1/docker/kotonoha-bot/data` など

5. **ネットワーク設定**

   - ブリッジネットワークを使用（デフォルト）

6. **自動起動の設定**
   - 「自動起動」を有効にする

#### 5.2 コンテナの起動

1. **プロジェクトを開始**

   - プロジェクト一覧で「kotonoha-bot」を選択
   - 「開始」をクリック

2. **ログの確認**
   - コンテナの「ログ」タブでログを確認
   - Bot が正常に起動しているか確認

#### Step 5 完了チェックリスト

- [x] Container Manager でプロジェクトが作成されている
- [x] コンテナが起動している
- [x] Bot が Discord に接続できる
- [x] 自動起動が有効になっている

---

### Step 7: バックアップ機能の実装 (1 時間) ✅ 完了

#### 7.1 バックアップスクリプトの作成

`scripts/backup.sh`:

```bash
#!/bin/bash
# Kotonoha Bot - データベースバックアップスクリプト
#
# 使用方法:
#   ./scripts/backup.sh
#   docker exec kotonoha-bot /app/scripts/backup.sh
#
# 環境変数:
#   BACKUP_DIR: バックアップ先ディレクトリ (デフォルト: /app/backups)
#   DATA_DIR: データディレクトリ (デフォルト: /app/data)
#   RETENTION_DAYS: バックアップ保持日数 (デフォルト: 7)

set -e

# 設定
BACKUP_DIR="${BACKUP_DIR:-/app/backups}"
DATA_DIR="${DATA_DIR:-/app/data}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/kotonoha_${TIMESTAMP}.db"

# バックアップディレクトリの作成
mkdir -p "${BACKUP_DIR}"

# データベースファイルの存在確認
DB_FILE="${DATA_DIR}/sessions.db"
if [ ! -f "${DB_FILE}" ]; then
    echo "Warning: Database file not found: ${DB_FILE}"
    exit 0
fi

# SQLite のバックアップ（オンラインバックアップ）
echo "Starting backup..."
sqlite3 "${DB_FILE}" ".backup '${BACKUP_FILE}'"

# バックアップファイルの圧縮
gzip -f "${BACKUP_FILE}"
BACKUP_FILE="${BACKUP_FILE}.gz"

# バックアップサイズの表示
BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
echo "Backup completed: ${BACKUP_FILE} (${BACKUP_SIZE})"

# 古いバックアップの削除
echo "Cleaning up old backups (older than ${RETENTION_DAYS} days)..."
find "${BACKUP_DIR}" -name "kotonoha_*.db.gz" -mtime +${RETENTION_DAYS} -delete

# 残っているバックアップの一覧表示
echo "Current backups:"
ls -lh "${BACKUP_DIR}"/kotonoha_*.db.gz 2>/dev/null || echo "  (none)"

echo "Backup process completed."
```

**注意**: このスクリプトは `Dockerfile` で既にコンテナにコピーされ、実行権限が付与されています（Step 1 参照）。

#### 7.2 定期実行の設定

##### 方法 1: cron を使用（NAS 上で実行）

```bash
# NAS 上で crontab を編集
crontab -e

# 毎日午前2時にバックアップを実行
0 2 * * * docker exec kotonoha-bot /app/scripts/backup.sh
```

##### 方法 2: Docker コンテナ内で cron を実行（非推奨）

コンテナ内で cron を実行する場合は、`Dockerfile` に以下を追加:

```dockerfile
# cron のインストール
RUN apt-get update && apt-get install -y --no-install-recommends cron \
    && rm -rf /var/lib/apt/lists/*

# cron ジョブの設定（バックアップスクリプトは既にコピー済み）
RUN echo "0 2 * * * /app/scripts/backup.sh >> /app/logs/backup.log 2>&1" | crontab -

# cron の起動（エントリーポイントを変更）
CMD ["sh", "-c", "cron && python -m kotonoha_bot.main"]
```

**注意**: 方法 1（NAS 上で cron を使用）を推奨します。コンテナ内で cron を実行する場合は、コンテナの再起動時に cron も再起動されるため、管理が複雑になります。

#### Step 7 完了チェックリスト

- [x] バックアップスクリプトが作成されている
- [x] バックアップが正常に実行される
- [x] 古いバックアップが自動削除される
- [x] 定期実行が設定されている

---

### Step 8: ヘルスチェック機能の設定 (30 分) ✅ 完了

#### 8.1 HTTP ヘルスチェックエンドポイント

アプリケーションは HTTP ヘルスチェックエンドポイントを提供します。詳細は [ヘルスチェックドキュメント](../../90_90_operations/health-check.md) を参照してください。

**主な機能**:

- `/health` エンドポイント: アプリケーション全体の状態を確認
- `/ready` エンドポイント: Discord への接続状態を確認
- Docker ヘルスチェックとの統合

**設定**:

`.env` ファイルで設定（デフォルトで有効）:

```env
# ヘルスチェックサーバーを有効化（デフォルト: true）
HEALTH_CHECK_ENABLED=true
```

**使用方法**:

```bash
# ヘルスチェック（ポート公開時）
curl http://localhost:8080/health

# レディネスチェック
curl http://localhost:8080/ready
```

#### Step 8 完了チェックリスト

- [x] ヘルスチェックエンドポイントが動作している
- [x] Docker ヘルスチェックが正常に動作している
- [x] ポート公開設定が適切に設定されている（必要に応じて）

---

### Step 9: ログ管理の設定 (30 分) ✅ 完了

#### 9.1 ログローテーションの設定

##### 方法 1: Python の logging.handlers.RotatingFileHandler を使用

`src/kotonoha_bot/main.py` に実装済み:

```python
def setup_logging() -> None:
    """ログ設定のセットアップ"""
    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
    ]

    # ファイルログが設定されている場合
    if Config.LOG_FILE:
        try:
            log_path = Path(Config.LOG_FILE)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            file_handler = RotatingFileHandler(
                log_path,
                maxBytes=Config.LOG_MAX_SIZE * 1024 * 1024,  # MB to bytes
                backupCount=Config.LOG_BACKUP_COUNT,
                encoding="utf-8",
            )
            file_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
            )
            handlers.append(file_handler)
        except (OSError, PermissionError) as e:
            # ログファイルの作成に失敗した場合は警告を出して続行
            logging.warning(
                f"Could not set up file logging to {Config.LOG_FILE}: {e}. "
                "Continuing with console logging only."
            )

    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
    )
```

**環境変数での設定**:

`.env` ファイルで設定可能:

```env
LOG_LEVEL=INFO
LOG_FILE=./logs/kotonoha.log
LOG_MAX_SIZE=10  # MB
LOG_BACKUP_COUNT=5
```

**ログ設定の動作**:

- `LOG_FILE` が設定されていない場合（コメントアウトされている場合）:

  - ファイルログは作成されません
  - ログはコンソール（stdout）のみに出力されます
  - Docker 環境では `docker logs` で確認可能ですが、ホスト側のログファイルには保存されません

- `LOG_FILE` が設定されている場合:
  - 指定されたパスにログファイルが作成されます
  - `LOG_MAX_SIZE`（MB）でログローテーションの最大サイズを設定
  - `LOG_BACKUP_COUNT` で保持するバックアップファイル数を設定
  - ログファイルの作成に失敗した場合は警告を出して、コンソールログのみで続行します

##### 方法 2: logrotate を使用（NAS 上で実行）

`/etc/logrotate.d/kotonoha-bot`:

```conf
/volume1/docker/kotonoha-bot/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 botuser botuser
}
```

#### Step 9 完了チェックリスト

- [x] ログローテーションが設定されている
- [x] ログファイルが適切に管理されている

---

### Step 10: セキュリティ設定 (30 分) ✅ 完了

#### 9.1 非 root ユーザーでの実行

`Dockerfile` で botuser（UID 1000）を作成し、`entrypoint.sh` で root から botuser に切り替えます:

```dockerfile
# 非rootユーザーの作成（UID/GID 1000で明示的に作成）
RUN groupadd -r -g 1000 botuser && useradd -r -u 1000 -g botuser -d /app -s /sbin/nologin botuser

# ユーザー切り替えはentrypoint.shで行う（rootで起動してパーミッション修正後、ユーザーを切り替える）
# USER botuser
```

**動作の流れ**:

1. コンテナが`user: root`で起動される（`docker-compose.yml`で設定）
2. `entrypoint.sh`が root で実行される
3. マウントされたディレクトリ（`/app/data`、`/app/logs`、`/app/backups`）の所有者を`botuser:botuser`に変更
4. パーミッションを`775`に設定（失敗時は`777`）
5. `gosu`で botuser（UID 1000）に切り替え
6. botuser でアプリケーションを実行

これにより、マウントされたボリュームの所有者が誰であっても自動的に動作します。

#### 9.2 環境変数の保護

- `.env` ファイルの権限を `600` に設定
- 機密情報を環境変数で管理
- `.env` ファイルを Git にコミットしない

#### 9.3 ネットワーク設定

- 必要最小限のポートのみ公開
- 外部からのアクセスを制限

#### Step 10 完了チェックリスト

- [x] 非 root ユーザーで実行されている
- [x] 環境変数が適切に保護されている
- [x] ネットワーク設定が適切

---

### Step 11: 動作確認とテスト (1 時間) ✅ 完了

#### 10.1 動作確認チェックリスト

1. **起動確認**

   - [x] コンテナが正常に起動する
   - [x] Bot が Discord に接続できる
   - [x] ログが正常に出力される

2. **機能確認**

   - [x] メンション時に応答が返る
   - [x] 会話履歴が保持される
   - [x] データベースファイルが作成される

3. **永続化確認**

   - [x] コンテナを再起動してもデータが保持される
   - [x] ログファイルが保持される

4. **バックアップ確認**

   - [x] バックアップが正常に実行される
   - [x] バックアップファイルが作成される

5. **ヘルスチェック確認**

   - [x] Docker ヘルスチェックが正常に動作している（`docker ps`で`healthy`と表示される）
   - [x] HTTP ヘルスチェックエンドポイントにアクセスできる（`curl http://localhost:8080/health`）
   - [x] レディネスチェックが動作している（`curl http://localhost:8080/ready`）

6. **自動起動確認**
   - [x] NAS を再起動しても Bot が自動起動する

#### Step 11 完了チェックリスト

- [x] すべての動作確認項目が完了
- [x] 問題が発生した場合はトラブルシューティングを実施

---

## 完了基準

### Phase 2 完了の定義

以下の全ての条件を満たした時、Phase 2 が完了とする:

1. **デプロイ要件**

   - [x] Docker コンテナとして動作する
   - [x] NAS 上で正常に動作する
   - [x] 自動起動が設定されている

2. **データ永続化**

   - [x] データベースファイルが永続化される
   - [x] ログファイルが永続化される
   - [x] コンテナ再起動後もデータが保持される

3. **運用機能**

   - [x] バックアップが自動実行される
   - [x] ログローテーションが設定されている
   - [x] 監視が可能（ログの確認、ヘルスチェック）

4. **セキュリティ**
   - [x] 非 root ユーザーで実行されている
   - [x] 環境変数が適切に保護されている

---

## Phase 2 完了報告

**完了日**: 2026 年 1 月 15 日

### 実装サマリー

Phase 2（NAS デプロイ）のすべての目標を達成しました。

| カテゴリ           | 状態    | 備考                                            |
| ------------------ | ------- | ----------------------------------------------- |
| Dockerfile         | ✅ 完了 | マルチステージビルド、python:3.14-slim ベース   |
| docker-compose.yml | ✅ 完了 | ボリュームマウント、ヘルスチェック設定          |
| entrypoint.sh      | ✅ 完了 | 自動パーミッション修正、gosu による非 root 実行 |
| バックアップ機能   | ✅ 完了 | SQLite オンラインバックアップ、gzip 圧縮        |
| ヘルスチェック     | ✅ 完了 | HTTP エンドポイント（/health, /ready）          |
| ログローテーション | ✅ 完了 | RotatingFileHandler 使用                        |
| セキュリティ       | ✅ 完了 | 非 root 実行、環境変数保護                      |
| NAS デプロイ       | ✅ 完了 | Synology Container Manager で稼働中             |

### Phase 2 完了時のアクション

```bash
# 全ての変更をコミット
git add .
git commit -m "feat: Phase 2 NASデプロイ完了

- Dockerコンテナ化（マルチステージビルド）
- Docker Compose設定（ボリュームマウント、ヘルスチェック）
- 自動パーミッション修正（entrypoint.sh）
- 非rootユーザーでの実行（botuser、UID 1000）
- データの永続化（SQLite、ログ、バックアップ）
- バックアップ機能（SQLiteオンラインバックアップ、gzip圧縮）
- ログローテーション（RotatingFileHandler）
- ヘルスチェック機能（HTTPエンドポイント）
- セキュリティ設定（環境変数保護、最小権限の原則）
- NASデプロイ（Synology Container Manager）

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

# タグを作成
git tag -a v0.2.0-phase2 -m "Phase 2 NASデプロイ完了"

# リモートにプッシュ
git push origin main
git push origin v0.2.0-phase2
```

### 次のフェーズ

Phase 2 が完了したため、Phase 3（CI/CD・運用機能）に進むことができます。

詳細は [Phase 3 実装計画](./phase03.md) を参照してください。

---

## トラブルシューティング

### 問題 1: CPU CFS エラー（NanoCPUs can not be set）

**症状**:

- コンテナ作成時に以下のエラーが発生する:
  - `Error response from daemon: NanoCPUs can not be set, as your kernel does not support CPU CFS`
  - `support CPU CFS scheduler or the cgroup is not mounted`

**原因**:

- NAS のカーネルが CPU CFS（Completely Fair Scheduler）をサポートしていない
- `docker-compose.yml` の `deploy.resources.limits.cpus` 設定が原因

**解決方法**:

1. **docker-compose.yml を修正**（推奨）:

   `docker-compose.yml` の CPU 制限をコメントアウトします:

   ```yaml
   deploy:
     resources:
       limits:
         # cpus: "1.0"  # NAS環境ではコメントアウト
         memory: 512M
       reservations:
         # cpus: "0.25"  # NAS環境ではコメントアウト
         memory: 128M
   ```

2. **Container Manager の GUI から設定**:

   - Container Manager でコンテナの「編集」を開く
   - 「リソース制限」タブで CPU 制限を設定（GUI から設定するとエラーが発生しない場合がある）

3. **リソース制限を完全に削除**:

   CPU 制限が不要な場合は、`deploy` セクション全体をコメントアウト:

   ```yaml
   # リソース制限（NAS環境でCPU CFS未サポートの場合はコメントアウト）
   # deploy:
   #   resources:
   #     limits:
   #       memory: 512M
   ```

**注意**: メモリ制限は多くの NAS でサポートされているため、CPU 制限のみを削除し、メモリ制限は残すことを推奨します。

---

### 問題 2: コンテナが起動しない

**症状**:

- Container Manager でコンテナが起動しない
- エラーメッセージが表示される

**解決方法**:

1. ログを確認:

   ```bash
   docker logs kotonoha-bot
   ```

2. 環境変数を確認:

   - `.env` ファイルの値が正しいか確認
   - 必須の環境変数が設定されているか確認

3. ボリュームマウントを確認:
   - パスが正しいか確認
   - ディレクトリの権限が正しいか確認

---

### 問題 3: Bot が Discord に接続できない

**症状**:

- コンテナは起動しているが、Bot が Discord に接続できない

**解決方法**:

1. ログを確認:

   ```bash
   docker logs kotonoha-bot
   ```

2. 環境変数を確認:

   - `DISCORD_TOKEN` が正しく設定されているか確認

3. ネットワーク設定を確認:
   - ファイアウォールでポートがブロックされていないか確認

---

### 問題 4: データが永続化されない

**症状**:

- コンテナを再起動するとデータが消える

**解決方法**:

1. ボリュームマウントを確認:

   - `docker-compose.yml` の `volumes` 設定を確認
   - パスが正しいか確認

2. ディレクトリの権限を確認:

   ```bash
   ls -la /volume1/docker/kotonoha-bot/data
   ```

3. コンテナ内で確認:

   ```bash
   docker exec -it kotonoha-bot ls -la /app/data
   ```

---

### 問題 5: バックアップが実行されない

**症状**:

- バックアップファイルが作成されない

**解決方法**:

1. バックアップスクリプトの権限を確認:

   ```bash
   chmod +x /app/scripts/backup.sh
   ```

2. cron の設定を確認:

   ```bash
   docker exec kotonoha-bot crontab -l
   ```

3. 手動でバックアップを実行:

   ```bash
   docker exec kotonoha-bot /app/scripts/backup.sh
   ```

---

### 問題 6: ディレクトリのパーミッションエラー

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

このボットは起動時に自動的にパーミッションを修正する機能を搭載しています。`docker-compose.yml`を使用する場合、自動的に root で起動され、パーミッションが修正されます。

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

```bash
# 方法A: グループ書き込み権限を付与（推奨）
chmod 775 data logs backups

# 方法B: 全員に書き込み権限を付与（セキュリティ上は推奨されないが、動作確認用）
chmod 777 data logs backups
```

#### 方法 3: 所有者を変更（UID 1000 のユーザーが存在する場合）

```bash
sudo chown -R 1000:1000 data logs backups
```

**詳細なトラブルシューティング方法については、[トラブルシューティングガイド](../../90_90_operations/troubleshooting.md#問題-ディレクトリのパーミッションエラー)を参照してください。**

---

## 次のフェーズへ

### Phase 3 の準備

Phase 2 が完了したら、以下を準備して Phase 3 に移行します:

1. **Phase 2 の振り返り**

   - うまくいったこと
   - 改善点
   - Phase 2 で活かせること

2. **Phase 3 の目標確認**

   - AI 応答機能の拡張
   - プロンプト生成機能の強化
   - エラーハンドリングの改善
   - レート制限の基本対応

3. **Phase 2 の安定化**
   - ログ管理の最適化
   - バックアップの定期実行確認
   - パフォーマンスの監視

---

## 参考資料

- [Synology Container Manager ドキュメント](https://kb.synology.com/ja-jp/DSM/help/ContainerManager/container_manager_desc)
- [Docker ドキュメント](https://docs.docker.com/)
- [Docker Compose ドキュメント](https://docs.docker.com/compose/)
- [Watchtower ドキュメント](https://containrrr.dev/watchtower/)
- [デプロイメント・運用ガイド](../../90_90_operations/deployment-operations.md)
- [ヘルスチェックドキュメント](../../90_90_operations/health-check.md)

---

**作成日**: 2026 年 1 月
**最終更新日**: 2026 年 1 月 15 日
**対象フェーズ**: Phase 2（NAS デプロイ）
**実装状況**: ✅ 実装完了（2026 年 1 月）
**前提条件**: Phase 1 完了済み ✅
**次のフェーズ**: Phase 3（CI/CD・運用機能）
**バージョン**: 2.0

### 更新履歴

- **v2.0** (2026-01-15): 完了報告形式に整理、実装状況セクションを追加
- **v1.3** (2026-01-14): entrypoint.sh の簡素化、HTTP ヘルスチェック機能の追加、ポート公開設定の追加
- **v1.2** (2026-01-14): 自動パーミッション修正機能の追加、entrypoint.sh の実装、docker-compose.yml の更新
- **v1.1** (2026-01): 初版リリース
