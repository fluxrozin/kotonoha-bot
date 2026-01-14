# Phase 2 実装計画 - NAS デプロイ

Phase 1 の次のフェーズとして、NAS（Network Attached Storage）へのデプロイを実装する計画書。

## 目次

1. [Phase 2 の目標](#phase-2-の目標)
2. [前提条件](#前提条件)
3. [NAS の種類と選定](#nas-の種類と選定)
4. [実装ステップ](#実装ステップ)
5. [完了基準](#完了基準)
6. [トラブルシューティング](#トラブルシューティング)
7. [次のフェーズへ](#次のフェーズへ)

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

## 実装ステップ

### Step 1: Dockerfile の作成 (1 時間)

#### 1.1 `Dockerfile` の作成

プロジェクトルートに `Dockerfile` を作成:

```dockerfile
# Python 3.14 slim ベースイメージ
FROM python:3.14-slim

# 作業ディレクトリを設定
WORKDIR /app

# システムパッケージの更新と必要なツールのインストール
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# uv のインストール
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:${PATH}"

# プロジェクトファイルのコピー
COPY pyproject.toml uv.lock ./
COPY src/ ./src/

# 依存関係のインストール
RUN uv sync --frozen

# 非 root ユーザーの作成
RUN useradd -m -u 1000 botuser && \
    chown -R botuser:botuser /app
USER botuser

# 環境変数の設定
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# ヘルスチェック
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# エントリーポイント
CMD ["python", "-m", "src.kotonoha_bot.main"]
```

#### 1.2 `.dockerignore` の作成

```dockerignore
# Git
.git
.gitignore

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
.venv/

# Environment
.env
.env.local

# Database
*.db
*.sqlite
*.sqlite3
data/

# Logs
logs/
*.log

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Documentation
docs/
README.md

# Tests
tests/
```

#### Step 1 完了チェックリスト

- [ ] `Dockerfile` が作成されている
- [ ] `.dockerignore` が作成されている
- [ ] ローカルで Docker イメージがビルドできる

---

### Step 2: Docker Compose の作成 (30 分)

#### 2.1 `docker-compose.yml` の作成

```yaml
version: "3.8"

services:
  kotonoha-bot:
    image: ghcr.io/your-username/kotonoha-bot:latest
    container_name: kotonoha-bot
    restart: unless-stopped

    # 環境変数ファイル
    env_file:
      - .env

    # ボリュームマウント（データの永続化）
    volumes:
      # データベース
      - ./data:/app/data
      # ログ
      - ./logs:/app/logs
      # バックアップ
      - ./backups:/app/backups

    # ネットワーク設定
    network_mode: bridge

    # リソース制限（オプション）
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 512M
        reservations:
          cpus: "0.5"
          memory: 256M

    # ヘルスチェック
    healthcheck:
      test: ["CMD", "python", "-c", "import sys; sys.exit(0)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
```

#### 2.2 `.env` ファイルの準備

NAS 上に `.env` ファイルを作成（`.env.example` をコピー）:

```bash
# NAS 上で実行
cp .env.example .env
# .env を編集して実際の値を設定
```

#### Step 2 完了チェックリスト

- [ ] `docker-compose.yml` が作成されている
- [ ] `.env` ファイルが NAS 上に作成されている
- [ ] ボリュームマウントのパスが正しく設定されている

---

### Step 3: ローカルでの動作確認 (1 時間)

#### 3.1 ローカルで Docker イメージをビルド

```bash
# プロジェクトルートで実行
docker build -t kotonoha-bot:local .
```

#### 3.2 ローカルで Docker Compose を実行

```bash
# docker-compose.yml があるディレクトリで実行
docker-compose up -d

# ログを確認
docker-compose logs -f

# コンテナの状態を確認
docker-compose ps
```

#### 3.3 動作確認

- [ ] Bot が Discord に接続できる
- [ ] メンション時に応答が返る
- [ ] データベースファイルが作成される
- [ ] ログが出力される

#### Step 3 完了チェックリスト

- [ ] ローカルで Docker イメージがビルドできる
- [ ] ローカルで Docker Compose が動作する
- [ ] Bot が正常に動作する

---

### Step 4: NAS へのデプロイ準備 (1 時間)

#### 4.1 NAS へのファイル転送

##### 方法 1: SMB/CIFS 共有を使用

```bash
# Windows/Mac から NAS の共有フォルダにアクセス
# 以下のファイルをコピー:
# - docker-compose.yml
# - .env
# - Dockerfile（オプション、ローカルビルドする場合）
```

##### 方法 2: SCP を使用

```bash
# SSH で NAS に接続してファイルを転送
scp docker-compose.yml admin@nas-ip:/volume1/docker/kotonoha-bot/
scp .env admin@nas-ip:/volume1/docker/kotonoha-bot/
```

##### 方法 3: Git を使用（推奨）

```bash
# NAS 上で Git リポジトリをクローン
ssh admin@nas-ip
cd /volume1/docker
git clone https://github.com/your-username/kotonoha-bot.git
cd kotonoha-bot
```

#### 4.2 NAS 上でのディレクトリ構造

```txt
/volume1/docker/kotonoha-bot/
├── docker-compose.yml
├── .env
├── Dockerfile
├── data/          # データベースファイル（自動生成）
├── logs/          # ログファイル（自動生成）
└── backups/      # バックアップファイル（自動生成）
```

#### 4.3 ディレクトリの権限設定

```bash
# NAS 上で実行
chmod 755 /volume1/docker/kotonoha-bot
chmod 644 /volume1/docker/kotonoha-bot/docker-compose.yml
chmod 600 /volume1/docker/kotonoha-bot/.env
```

#### Step 4 完了チェックリスト

- [ ] NAS 上に必要なファイルが配置されている
- [ ] ディレクトリの権限が正しく設定されている
- [ ] `.env` ファイルに正しい値が設定されている

---

### Step 5: Synology NAS でのデプロイ (1 時間)

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

- [ ] Container Manager でプロジェクトが作成されている
- [ ] コンテナが起動している
- [ ] Bot が Discord に接続できる
- [ ] 自動起動が有効になっている

---

### Step 7: バックアップ機能の実装 (1 時間)

#### 7.1 バックアップスクリプトの作成

`scripts/backup.sh`:

```bash
#!/bin/bash

# バックアップ設定
BACKUP_DIR="/app/backups"
DATA_DIR="/app/data"
LOG_DIR="/app/logs"
RETENTION_DAYS=7

# バックアップファイル名（タイムスタンプ付き）
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/backup_${TIMESTAMP}.tar.gz"

# バックアップディレクトリの作成
mkdir -p "${BACKUP_DIR}"

# データベースとログをバックアップ
tar -czf "${BACKUP_FILE}" \
    -C /app \
    data/ \
    logs/

# 古いバックアップの削除（7日分保持）
find "${BACKUP_DIR}" -name "backup_*.tar.gz" -mtime +${RETENTION_DAYS} -delete

echo "Backup completed: ${BACKUP_FILE}"
```

#### 7.2 定期実行の設定

##### 方法 1: cron を使用（NAS 上で実行）

```bash
# NAS 上で crontab を編集
crontab -e

# 毎日午前2時にバックアップを実行
0 2 * * * docker exec kotonoha-bot /app/scripts/backup.sh
```

##### 方法 2: Docker コンテナ内で cron を実行

`Dockerfile` に cron を追加:

```dockerfile
# cron のインストール
RUN apt-get update && apt-get install -y cron

# バックアップスクリプトのコピー
COPY scripts/backup.sh /app/scripts/backup.sh
RUN chmod +x /app/scripts/backup.sh

# cron ジョブの設定
RUN echo "0 2 * * * /app/scripts/backup.sh >> /app/logs/backup.log 2>&1" | crontab -

# cron の起動
CMD cron && python -m src.kotonoha_bot.main
```

#### Step 7 完了チェックリスト

- [ ] バックアップスクリプトが作成されている
- [ ] バックアップが正常に実行される
- [ ] 古いバックアップが自動削除される
- [ ] 定期実行が設定されている

---

### Step 8: ログ管理の設定 (30 分)

#### 8.1 ログローテーションの設定

##### 方法 1: Python の logging.handlers.RotatingFileHandler を使用

`src/kotonoha_bot/main.py` を更新:

```python
import logging
from logging.handlers import RotatingFileHandler

# ログファイルの設定
log_file = Path("./logs/kotonoha.log")
log_file.parent.mkdir(parents=True, exist_ok=True)

# ローテーションハンドラー
file_handler = RotatingFileHandler(
    log_file,
    maxBytes=10 * 1024 * 1024,  # 10MB
    backupCount=5
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)

logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    handlers=[
        logging.StreamHandler(sys.stdout),
        file_handler,
    ]
)
```

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

#### Step 8 完了チェックリスト

- [ ] ログローテーションが設定されている
- [ ] ログファイルが適切に管理されている

---

### Step 9: セキュリティ設定 (30 分)

#### 9.1 非 root ユーザーでの実行

`Dockerfile` で既に設定済み:

```dockerfile
RUN useradd -m -u 1000 botuser
USER botuser
```

#### 9.2 環境変数の保護

- `.env` ファイルの権限を `600` に設定
- 機密情報を環境変数で管理
- `.env` ファイルを Git にコミットしない

#### 9.3 ネットワーク設定

- 必要最小限のポートのみ公開
- 外部からのアクセスを制限

#### Step 9 完了チェックリスト

- [ ] 非 root ユーザーで実行されている
- [ ] 環境変数が適切に保護されている
- [ ] ネットワーク設定が適切

---

### Step 10: 動作確認とテスト (1 時間)

#### 10.1 動作確認チェックリスト

1. **起動確認**

   - [ ] コンテナが正常に起動する
   - [ ] Bot が Discord に接続できる
   - [ ] ログが正常に出力される

2. **機能確認**

   - [ ] メンション時に応答が返る
   - [ ] 会話履歴が保持される
   - [ ] データベースファイルが作成される

3. **永続化確認**

   - [ ] コンテナを再起動してもデータが保持される
   - [ ] ログファイルが保持される

4. **バックアップ確認**

   - [ ] バックアップが正常に実行される
   - [ ] バックアップファイルが作成される

5. **自動起動確認**
   - [ ] NAS を再起動しても Bot が自動起動する

#### Step 10 完了チェックリスト

- [ ] すべての動作確認項目が完了
- [ ] 問題が発生した場合はトラブルシューティングを実施

---

## 完了基準

### Phase 2 完了の定義

以下の全ての条件を満たした時、Phase 2 が完了とする:

1. **デプロイ要件**

   - [ ] Docker コンテナとして動作する
   - [ ] NAS 上で正常に動作する
   - [ ] 自動起動が設定されている

2. **データ永続化**

   - [ ] データベースファイルが永続化される
   - [ ] ログファイルが永続化される
   - [ ] コンテナ再起動後もデータが保持される

3. **運用機能**

   - [ ] バックアップが自動実行される
   - [ ] ログローテーションが設定されている
   - [ ] 監視が可能（ログの確認）

4. **セキュリティ**
   - [ ] 非 root ユーザーで実行されている
   - [ ] 環境変数が適切に保護されている

---

## トラブルシューティング

### 問題 1: コンテナが起動しない

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

### 問題 2: Bot が Discord に接続できない

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

### 問題 3: データが永続化されない

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

### 問題 4: バックアップが実行されない

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
- [operations/deployment-operations.md](../../operations/deployment-operations.md)

---

**作成日**: 2026 年 1 月
**最終更新日**: 2026 年 1 月
**対象フェーズ**: Phase 2（NAS デプロイ）
**前提条件**: Phase 1 完了済み ✅
**想定期間**: 1-2 週間
**バージョン**: 1.1
