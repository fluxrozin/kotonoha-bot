# PostgreSQLカスタムイメージ作成・デプロイ完全ガイド

## 概要

このドキュメントでは、`Dockerfile.postgres`を使用してPostgreSQLカスタムイメージを作成し、`docker-compose.yml`で直接ビルドする方式を中心に説明する。このプロジェクトでは、開発環境・本番環境ともに`docker-compose.yml`で直接ビルドする方式を使用する。

**対象読者**: 開発者、DevOpsエンジニア

**前提条件**:
- Dockerがインストールされていること
- プロジェクトのルートディレクトリに`Dockerfile.postgres`が存在すること

---

## 目次

1. [カスタムイメージを作る必要性](#1-カスタムイメージを作る必要性)
2. [Dockerfile.postgresの概要](#2-dockerfilepostgresの概要)
3. [docker-compose.ymlでの直接ビルド方式（メイン）](#3-docker-composeymlでの直接ビルド方式メイン)
   - [3.1 基本的な設定](#31-基本的な設定)
   - [3.2 開発環境への導入](#32-開発環境への導入)
   - [3.3 本番環境へのデプロイ](#33-本番環境へのデプロイ)
   - [3.4 ビルドの最適化](#34-ビルドの最適化)
4. [参考: GHCRからプルする方式](#4-参考ghcrからプルする方式)
   - [4.1 GHCRへのプッシュ（手動）](#41-ghcrへのプッシュ手動)
   - [4.2 GitHub Actionsでの自動化](#42-github-actionsでの自動化)
   - [4.3 GHCRからプルする設定](#43-ghcrからプルする設定)
5. [トラブルシューティング](#5-トラブルシューティング)
6. [まとめ](#6-まとめ)

---

## 1. カスタムイメージを作る必要性

### 1.1 既存イメージの状況

PostgreSQL 18 + pgvector + pg_bigmの組み合わせは、**公式・コミュニティイメージが存在しない**。

- pgvector単体のイメージは存在するが、pg_bigmは含まれていない
- コミュニティイメージは古い（3-7年前）またはメンテナンスされていない
- PostgreSQL 18に対応したpg_bigmを含むイメージは存在しない

### 1.2 このプロジェクトでの方針

このプロジェクトでは、**開発環境・本番環境ともに`docker-compose.yml`で直接ビルドする方式**を採用している。

**理由**:
- セットアップが簡単（外部レジストリ不要）
- ビルド時間は1-2分程度で許容範囲内
- Dockerキャッシュにより、2回目以降のビルドは高速化される
- 環境ごとの設定の違いを最小化できる

**ビルド時間について**:
- 典型的な開発マシン（4コア、SSD）: 初回ビルドは通常**1-2分程度**
  - ベースイメージ（pgvector/pgvector）のプル: 10-30秒
  - ビルド依存関係のインストール: 20-60秒
  - pg_bigmのダウンロード: 数秒
  - pg_bigmのコンパイル: 10-30秒
- 環境による変動:
  - キャッシュが効いている場合: より高速（数十秒程度）
  - 低スペックマシンやネットワークが遅い場合: 2-4分程度かかる場合もある
  - マルチステージビルドにより、ビルド依存関係が最終イメージに含まれないため、比較的高速

---

## 2. Dockerfile.postgresの概要

### 2.1 目的

`Dockerfile.postgres`は、PostgreSQL 18 + pgvector 0.8.1 + pg_bigm 1.2を組み合わせたカスタムイメージを作成するためのDockerfileである。

**含まれる拡張機能**:
- **pgvector**: ベクトル検索用拡張（ベースイメージに含まれる）
- **pg_bigm**: 日本語全文検索用拡張（カスタムビルド）

### 2.2 構造

`Dockerfile.postgres`はマルチステージビルドを使用している:

```dockerfile
# Stage 1: ビルド環境
FROM pgvector/pgvector:0.8.1-pg18 AS builder
# pg_bigmのビルド処理

# Stage 2: 実行環境（軽量）
FROM pgvector/pgvector:0.8.1-pg18
# ビルド済みのpg_bigmをコピー
```

**マルチステージビルドのメリット**:
- ビルド依存関係（build-essential等）を最終イメージに含めない
- イメージサイズを最小化
- セキュリティ向上（不要なツールを含めない）

### 2.3 ファイルの確認

**重要**: `docker-compose.yml`で直接ビルドする方式でも、`Dockerfile.postgres`は必須である。`build:`セクションで`dockerfile: Dockerfile.postgres`を指定しているため、このファイルが存在しないとビルドできない。

プロジェクトルートに`Dockerfile.postgres`が存在することを確認する:

```bash
# プロジェクトルートで実行
ls -la Dockerfile.postgres
```

存在しない場合は、[Phase 11の実装手順](../../00_planning/phases/phase11.md#step-1-dockerfilepostgresの作成)を参照して作成する。

**よくある質問: `Dockerfile.kotonoha`にマージできないか？**

`Dockerfile.postgres`を既存の`Dockerfile.kotonoha`（kotonoha-bot用）にマージすることは**技術的に不可能**である。理由:

1. **別々のサービス**: `Dockerfile.kotonoha`はkotonoha-bot（Pythonアプリケーション）用、`Dockerfile.postgres`はPostgreSQL用で、docker-compose.ymlで別々のコンテナとして起動する
2. **異なるベースイメージ**: `Dockerfile.kotonoha`は`python:3.14-slim`、`Dockerfile.postgres`は`pgvector/pgvector:0.8.1-pg18`を使用する
3. **docker-compose.ymlの制約**: `build:`セクションにインラインでDockerfileの内容を書くことはできない。`dockerfile:`でファイルを指定する必要がある

したがって、`Dockerfile.postgres`は別ファイルとして維持する必要がある。

**命名規則**:
このプロジェクトでは、サービス名をポストフィックスとして付ける命名規則を採用している:
- `Dockerfile.kotonoha`: kotonoha-botサービス用
- `Dockerfile.postgres`: postgresサービス用

これにより、どのサービス用のDockerfileかが一目で分かる。

---

## 3. docker-compose.ymlでの直接ビルド方式（メイン）

### 3.1 基本的な設定

`docker-compose.yml`でカスタムイメージを直接ビルドする設定:

```yaml
services:
  postgres:
    build:
      context: .
      dockerfile: Dockerfile.postgres
    image: kotonoha-postgres:pg18-pgvector0.8.1-pgbigm1.2
    container_name: kotonoha-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-kotonoha}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-password}
      POSTGRES_DB: ${POSTGRES_DB:-kotonoha}
    volumes:
      - postgres_data:/var/lib/postgresql
    networks:
      - kotonoha-network
    ports:
      - "127.0.0.1:5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-kotonoha}"]
      interval: 10s
      timeout: 5s
      retries: 5
```

**重要な前提条件**:
- **`Dockerfile.postgres`は必須**である。`docker-compose.yml`で直接ビルドする場合でも、`build:`セクションの`dockerfile: Dockerfile.postgres`で指定しているため、このファイルが存在する必要がある。
- `Dockerfile.postgres`が存在しない場合、ビルドは失敗する。

**設定のポイント**:
- `build:`セクションで`Dockerfile.postgres`を指定（このファイルが存在する必要がある）
- `image:`でイメージ名とタグを指定（ビルド後のイメージ名として使用される）
- 環境変数は`.env`ファイルから読み込む（デフォルト値も設定可能）

### 3.2 開発環境への導入

#### 3.2.1 初回セットアップ

1. **環境変数の設定**

`.env`ファイルを作成し、必要な環境変数を設定する:

```bash
# .envファイルの例
POSTGRES_USER=kotonoha
POSTGRES_PASSWORD=password
POSTGRES_DB=kotonoha
```

2. **コンテナの起動**

```bash
# プロジェクトルートで実行
# 初回はビルドが実行される（1-2分程度）
docker compose up -d

# ビルドの進行状況を確認
docker compose logs -f postgres
```

3. **動作確認**

```bash
# コンテナが起動しているか確認
docker compose ps

# pg_bigm拡張が利用可能か確認
docker compose exec postgres psql -U kotonoha -d kotonoha -c "SELECT * FROM pg_available_extensions WHERE name = 'pg_bigm';"

# 期待される出力:
#   name   | default_version | installed_version | comment
# ---------+-----------------+-------------------+---------
#  pg_bigm | 1.2             |                   | ...
```

#### 3.2.2 日常的な操作

**コンテナの起動・停止**:

```bash
# 起動
docker compose up -d

# 停止
docker compose down

# 停止（ボリュームも削除する場合）
docker compose down -v
```

**ログの確認**:

```bash
# リアルタイムでログを確認
docker compose logs -f postgres

# 最新の100行を表示
docker compose logs --tail=100 postgres
```

**イメージの再ビルド**:

```bash
# Dockerfile.postgresを変更した場合、再ビルドが必要
docker compose build postgres

# キャッシュを使わずに再ビルド
docker compose build --no-cache postgres

# 再ビルドして起動
docker compose up -d --build postgres
```

### 3.3 本番環境へのデプロイ

#### 3.3.1 前提条件

- 本番環境サーバーにDockerとDocker Composeがインストールされていること
- `docker-compose.yml`が本番環境サーバーに配置されていること
- `.env`ファイルが本番環境サーバーに配置されていること（適切な値が設定されていること）

#### 3.3.2 docker-compose.ymlの設定

開発環境と同様に、`docker-compose.yml`で直接ビルドする設定を使用する。ただし、本番環境では以下の点に注意する:

```yaml
services:
  postgres:
    build:
      context: .
      dockerfile: Dockerfile.postgres
    image: kotonoha-postgres:pg18-pgvector0.8.1-pgbigm1.2
    container_name: kotonoha-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql
    networks:
      - kotonoha-network
    # 本番環境ではポートを公開しない（内部ネットワークのみ）
    # ports:
    #   - "127.0.0.1:5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5
```

**本番環境での注意点**:
- ポートを公開しない（内部ネットワークのみでアクセス可能にする）
- 環境変数は`.env`ファイルから読み込む（ハードコードしない）
- 強力なパスワードを設定する

#### 3.3.3 環境変数の設定

本番環境サーバーの`.env`ファイルに以下を設定する:

```bash
# データベース設定（本番環境用の強力なパスワードを設定）
POSTGRES_USER=kotonoha
POSTGRES_PASSWORD=<strong-password>
POSTGRES_DB=kotonoha
```

**セキュリティ上の注意**:
- `.env`ファイルの権限を適切に設定する（例: `chmod 600 .env`）
- `.env`ファイルをGitにコミットしない（`.gitignore`に含まれていることを確認）

#### 3.3.4 デプロイ手順

```bash
# 1. 本番環境サーバーにSSH接続
ssh user@production-server

# 2. プロジェクトディレクトリに移動
cd /path/to/kotonoha-bot

# 3. 最新のコードを取得（Gitを使用している場合）
git pull origin main

# 4. 既存のコンテナを停止（データベースのダウンタイムを最小化）
docker compose stop postgres

# 5. 新しいイメージをビルド（Dockerfile.postgresが変更された場合）
docker compose build postgres

# 6. コンテナを再起動
docker compose up -d postgres

# 7. ヘルスチェックを確認
docker compose ps
docker compose logs postgres
```

#### 3.3.5 データベースマイグレーション

カスタムイメージをデプロイした後、必要に応じてマイグレーションを実行する:

```bash
# Alembicマイグレーションを実行
docker compose exec kotonoha-bot alembic upgrade head

# または、直接実行
docker compose exec kotonoha-bot python -m alembic upgrade head
```

### 3.4 ビルドの最適化

#### 3.4.1 Dockerキャッシュの活用

Dockerは、`Dockerfile.postgres`の各レイヤーをキャッシュする。2回目以降のビルドは、変更のないレイヤーをキャッシュから再利用するため、高速化される。

**キャッシュが無効になる場合**:
- `Dockerfile.postgres`の内容を変更した場合
- ベースイメージが更新された場合
- `--no-cache`オプションを使用した場合

#### 3.4.2 ビルド時間の短縮

**推奨事項**:
- 初回ビルド後は、`Dockerfile.postgres`を変更しない限り、再ビルドは不要
- ベースイメージの更新が必要な場合のみ、再ビルドを実行する
- 開発中は、コンテナを再起動するだけで十分（`docker compose restart postgres`）

---

## 4. 参考: GHCRからプルする方式

このプロジェクトでは使用しないが、参考としてGHCRからプルする方式の手順を記載する。

### 4.1 GHCRへのプッシュ（手動）

#### 4.1.1 前提条件

GHCRにプッシュするには、以下の準備が必要である:

1. **GitHub Personal Access Token (PAT)の作成**
   - GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
   - 必要な権限: `write:packages`, `read:packages`, `delete:packages`
   - トークン名: `GHCR_PUSH_TOKEN`（任意）

2. **環境変数の設定**
   - `.env`ファイルに以下を設定する

```bash
# GHCR認証用
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GITHUB_USERNAME=your-github-username
GITHUB_REPOSITORY=your-username/kotonoha-bot
```

#### 4.1.2 手動プッシュの手順

**実行環境**: 以下のコマンドは、ホストマシン（開発環境やCI/CD環境）から実行する。コンテナ内から実行するものではない。

```bash
# 0. プロジェクトルートに移動
cd /path/to/kotonoha-bot

# 1. .envファイルから環境変数を読み込む（ホストマシンから実行）
export $(grep -v '^#' .env | xargs)

# 2. GitHub Container Registryにログイン（ホストマシンから実行）
echo $GITHUB_TOKEN | docker login ghcr.io -u $GITHUB_USERNAME --password-stdin

# ログイン成功時の出力例:
# Login Succeeded

# 3. イメージをビルド（ホストマシンから実行）
docker build -f Dockerfile.postgres -t ghcr.io/${GITHUB_REPOSITORY}/kotonoha-postgres:latest .

# 4. レジストリにプッシュ（ホストマシンから実行）
docker push ghcr.io/${GITHUB_REPOSITORY}/kotonoha-postgres:latest

# プッシュ成功時の出力例:
# The push refers to repository [ghcr.io/your-username/kotonoha-bot/kotonoha-postgres]
# latest: digest: sha256:abc123... size: 1234
```

### 4.2 GitHub Actionsでの自動化

GitHub Actionsを使用して、コードをプッシュした際に自動的にカスタムイメージをビルド・プッシュする。

#### 4.2.1 ワークフローファイルの作成

`.github/workflows/build-postgres.yml`を作成する:

```yaml
name: Build and Push PostgreSQL Custom Image

on:
  push:
    branches: [main, develop]
    paths:
      - 'Dockerfile.postgres'
      - '.github/workflows/build-postgres.yml'
  pull_request:
    branches: [main, develop]
    paths:
      - 'Dockerfile.postgres'
  workflow_dispatch:  # 手動実行も可能

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: kotonoha-postgres

jobs:
  build:
    name: Build and Push PostgreSQL Image
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ github.repository }}/${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=sha,prefix=
            type=raw,value=latest,enable={{is_default_branch}}

      - name: Build and push Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ./Dockerfile.postgres
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          platforms: linux/amd64,linux/arm64
```

#### 4.2.2 ワークフローの説明

**トリガー**:
- `push`: `main`または`develop`ブランチに`Dockerfile.postgres`が変更された場合
- `pull_request`: PRで`Dockerfile.postgres`が変更された場合
- `workflow_dispatch`: 手動実行

**認証**:
- `secrets.GITHUB_TOKEN`を使用（自動的に提供される）
- 追加のシークレット設定は不要

**ビルドキャッシュ**:
- `cache-from: type=gha`と`cache-to: type=gha`でGitHub Actionsのキャッシュを活用
- 2回目以降のビルドが高速化される

### 4.3 GHCRからプルする設定

#### 4.3.1 docker-compose.ymlの設定

GHCRからプルする場合の設定例:

```yaml
services:
  postgres:
    # GHCRからプル（ビルド時間不要）
    image: ghcr.io/${GITHUB_REPOSITORY}/kotonoha-postgres:latest
    container_name: kotonoha-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-kotonoha}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-password}
      POSTGRES_DB: ${POSTGRES_DB:-kotonoha}
    volumes:
      - postgres_data:/var/lib/postgresql
    networks:
      - kotonoha-network
    ports:
      - "127.0.0.1:5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-kotonoha}"]
      interval: 10s
      timeout: 5s
      retries: 5
```

**注意**: `build:`セクションは削除する（`image:`を使用する場合、`build:`は不要）。

#### 4.3.2 GHCR認証の設定（プライベートパッケージの場合）

プライベートパッケージをプルする場合は、認証情報を設定する必要がある。

**方法1: docker loginを使用（推奨）**

```bash
# GitHub Personal Access Tokenを使用してログイン
echo $GITHUB_TOKEN | docker login ghcr.io -u $GITHUB_USERNAME --password-stdin

# 認証情報は ~/.docker/config.json に保存される
```

#### 4.3.3 コンテナの起動

```bash
# 既存のコンテナを停止・削除
docker compose down

# 新しいイメージをプルして起動
docker compose pull postgres
docker compose up -d

# ログを確認
docker compose logs postgres
```

---

## 5. トラブルシューティング

### 5.1 ビルドエラー

**問題**: `docker compose build`が失敗する

**原因と解決策**:

1. **ネットワークエラー**

   ```bash
   # インターネット接続を確認
   ping github.com
   
   # プロキシ設定が必要な場合
   export HTTP_PROXY=http://proxy.example.com:8080
   export HTTPS_PROXY=http://proxy.example.com:8080
   ```

2. **ディスク容量不足**

   ```bash
   # ディスク使用量を確認
   df -h
   
   # 不要なイメージを削除
   docker system prune -a
   ```

3. **pg_bigmのダウンロードエラー**
   - GitHubリリースページを確認: <https://github.com/pgbigm/pg_bigm/releases>
   - `Dockerfile.postgres`の`PG_BIGM_VERSION`が正しいか確認

### 5.2 コンテナ起動エラー

**問題**: コンテナが起動しない

**原因と解決策**:

1. **ポート競合**

   ```bash
   # ポート5432が使用中か確認
   sudo lsof -i :5432
   
   # 別のポートを使用する
   # docker-compose.ymlで:
   # ports:
   #   - "127.0.0.1:5433:5432"
   ```

2. **ボリュームの権限エラー**

   ```bash
   # ボリュームの権限を確認
   docker volume inspect kotonoha-bot_postgres_data
   
   # 必要に応じて権限を修正
   sudo chown -R 999:999 /var/lib/docker/volumes/kotonoha-bot_postgres_data/_data
   ```

3. **環境変数の未設定**

   ```bash
   # .envファイルが存在するか確認
   ls -la .env
   
   # 環境変数が正しく設定されているか確認
   cat .env | grep POSTGRES
   ```

### 5.3 pg_bigm拡張が利用できない

**問題**: `CREATE EXTENSION pg_bigm;`が失敗する

**原因と解決策**:

1. **カスタムイメージが使用されていない**

   ```bash
   # 使用中のイメージを確認
   docker compose ps postgres
   docker compose exec postgres psql -U kotonoha -d kotonoha -c "SELECT version();"
   
   # docker-compose.ymlでカスタムイメージが指定されているか確認
   ```

2. **拡張ファイルが存在しない**

   ```bash
   # コンテナ内で拡張ファイルを確認
   docker compose exec postgres ls -la /usr/share/postgresql/18/extension/ | grep pg_bigm
   docker compose exec postgres ls -la /usr/lib/postgresql/18/lib/ | grep pg_bigm
   ```

3. **PostgreSQLのバージョン不一致**

   ```bash
   # PostgreSQLのバージョンを確認
   docker compose exec postgres psql -U kotonoha -d kotonoha -c "SELECT version();"
   
   # 期待されるバージョン: PostgreSQL 18.x
   ```

### 5.4 ビルド時間が長い

**問題**: ビルドに時間がかかりすぎる

**原因と解決策**:

1. **初回ビルドは時間がかかる**
   - ベースイメージのダウンロードに時間がかかる
   - 2回目以降はキャッシュが効くため、高速化される

2. **ネットワークが遅い**
   - プロキシ設定を確認
   - ベースイメージのダウンロードに時間がかかる場合がある

3. **ディスクI/Oが遅い**
   - SSDの使用を推奨
   - Dockerのストレージドライバーを確認

---

## 6. まとめ

このドキュメントでは、以下の手順を説明した:

1. **カスタムイメージの必要性**: PostgreSQL 18 + pgvector + pg_bigmの組み合わせは既存イメージが存在しないため、カスタムイメージが必要
2. **docker-compose.ymlでの直接ビルド方式**: 開発環境・本番環境ともに使用する方式
3. **開発環境への導入**: 初回セットアップから日常的な操作まで
4. **本番環境へのデプロイ**: デプロイ手順と注意点
5. **参考: GHCRからプルする方式**: 別の方式として参考情報を提供

**このプロジェクトでの推奨ワークフロー**:

1. **開発環境**:
   - `docker-compose.yml`で直接ビルド
   - 初回ビルド後は、`Dockerfile.postgres`を変更しない限り再ビルド不要
   - コンテナの再起動は`docker compose restart postgres`で十分

2. **本番環境**:
   - `docker-compose.yml`で直接ビルド
   - デプロイ時は`docker compose build postgres`で再ビルド
   - ポートを公開しない（内部ネットワークのみ）

**ビルド時間について**:
- 初回ビルド: 1-2分程度（許容範囲内）
- 2回目以降: キャッシュにより高速化（数十秒程度）
- `Dockerfile.postgres`を変更した場合のみ再ビルドが必要

---

## 参考資料

- [Phase 11実装計画](../../00_planning/phases/phase11.md)
- [PostgreSQL実装ガイド](../51_guides/postgresql-implementation-guide.md)
- [GitHub Container Registry ドキュメント](https://docs.github.com/ja/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Docker公式ドキュメント](https://docs.docker.com/)
