# Phase 3 実装計画 - CI/CD と運用機能

Phase 2 の次のフェーズとして、CI/CD パイプラインと運用に必要な機能を実装する計画書。

## 目次

1. [Phase 3 の目標](#phase-3-の目標)
2. [前提条件](#前提条件)
3. [実装ステップ](#実装ステップ)
4. [完了基準](#完了基準)
5. [トラブルシューティング](#トラブルシューティング)
6. [次のフェーズへ](#次のフェーズへ)

---

## Phase 3 の目標

### CI/CD と運用機能の目的

**目標**: GitHub へのプッシュをトリガーに、自動でビルド・テスト・デプロイを行い、NAS 上の Bot を自動更新する

**達成すべきこと**:

- GitHub Actions による CI/CD パイプライン
- Docker イメージのビルドと GHCR へのプッシュ
- Watchtower による NAS 上のコンテナ自動更新
- テストの自動実行
- コード品質チェック（lint、format、type-check）

**スコープ外（将来のフェーズ）**:

- Kubernetes へのデプロイ
- Blue/Green デプロイメント
- カナリアリリース
- 高度なモニタリング（Prometheus、Grafana）

---

## 前提条件

### 必要な環境

1. **GitHub リポジトリ**

   - プライベートまたはパブリックリポジトリ
   - GitHub Actions が有効
   - GitHub Packages（GHCR）への書き込み権限

2. **NAS 環境**

   - Phase 2 が完了済み ✅
   - Docker コンテナが稼働中
   - インターネット接続（GHCR からのプル用）

3. **開発環境**
   - Python 3.14
   - uv（推奨）または pip
   - Git

### 必要な権限

- GitHub リポジトリの管理者権限
- GitHub Packages（GHCR）への書き込み権限
- NAS への SSH アクセス（オプション）

### 必要な認証情報

- GitHub Personal Access Token（GHCR 用、オプション）
- Discord Token（シークレット、テスト用）
- Anthropic API Key（シークレット、テスト用）

**注意**: `GITHUB_TOKEN` は GitHub Actions で自動的に提供されるため、通常は設定不要です。

---

## 実装ステップ

### Step 1: テストフレームワークの設定

#### 1.1 pytest 設定（`pyproject.toml`）

`pyproject.toml` に pytest の設定を追加します。

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
addopts = "-v --tb=short"
asyncio_mode = "auto"

[tool.coverage.run]
source = ["src/kotonoha_bot"]
branch = true

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
]
```

#### 1.2 テストディレクトリ構造の作成

```txt
tests/
├── __init__.py
├── conftest.py              # pytest フィクスチャ
├── unit/                    # 単体テスト
│   ├── __init__.py
│   ├── test_session.py
│   ├── test_ai.py
│   └── test_db.py
└── integration/             # 統合テスト（オプション）
    ├── __init__.py
    └── test_bot.py
```

#### 1.3 基本的なフィクスチャの実装

`tests/conftest.py` を作成します。

```python
"""pytest フィクスチャ"""
import pytest
import tempfile
from pathlib import Path

from kotonoha_bot.session.manager import SessionManager
from kotonoha_bot.db.sqlite import SQLiteDatabase


@pytest.fixture
def temp_db_path():
    """一時的なデータベースパス"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    yield db_path
    db_path.unlink(missing_ok=True)


@pytest.fixture
def db(temp_db_path):
    """SQLite データベースのフィクスチャ"""
    return SQLiteDatabase(db_path=temp_db_path)


@pytest.fixture
def session_manager(temp_db_path):
    """SessionManager のフィクスチャ"""
    # 一時的なデータベースを使用
    manager = SessionManager()
    manager.db.db_path = temp_db_path
    return manager
```

#### 1.4 基本的なテストの実装

`tests/unit/test_session.py` の例:

```python
"""セッション管理のテスト"""
import pytest
from kotonoha_bot.session.models import MessageRole

from .conftest import session_manager


def test_create_session(session_manager):
    """セッションが作成できることを確認"""
    session = session_manager.create_session(
        session_key="test:123",
        session_type="mention",
        user_id=123,
    )

    assert session is not None
    assert session.session_key == "test:123"
    assert session.session_type == "mention"
    assert session.user_id == 123


def test_get_session(session_manager):
    """セッションが取得できることを確認"""
    # セッションを作成
    session_manager.create_session("test:123", "mention")

    # 取得
    session = session_manager.get_session("test:123")
    assert session is not None
    assert session.session_key == "test:123"


def test_add_message(session_manager):
    """メッセージが追加できることを確認"""
    session_manager.create_session("test:123", "mention")
    session_manager.add_message("test:123", MessageRole.USER, "こんにちは")

    session = session_manager.get_session("test:123")
    assert len(session.messages) == 1
    assert session.messages[0].content == "こんにちは"
```

#### Step 1 完了チェックリスト

- [ ] `pyproject.toml` に pytest 設定が追加されている
- [ ] テストディレクトリ構造が作成されている
- [ ] `conftest.py` が作成されている
- [ ] 基本的なテストが実装されている
- [ ] ローカルで `pytest` が実行できる

---

### Step 2: コード品質ツールの設定

#### 2.1 Ruff 設定（`pyproject.toml`）

`pyproject.toml` に Ruff の設定を追加します。

```toml
[tool.ruff]
target-version = "py314"
line-length = 88
src = ["src"]

[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # pyflakes
    "I",      # isort
    "B",      # flake8-bugbear
    "C4",     # flake8-comprehensions
    "UP",     # pyupgrade
    "ARG",    # flake8-unused-arguments
    "SIM",    # flake8-simplify
]
ignore = [
    "E501",   # line too long (handled by formatter)
]

[tool.ruff.lint.isort]
known-first-party = ["kotonoha_bot"]
```

#### 2.2 ty 設定（`pyproject.toml`）

`ty` は Rust 製の高速な型チェッカーで、mypy の代替として使用できます。`pyproject.toml` に `ty` の設定を追加します。

```toml
[tool.ty]
# ty は pyproject.toml が存在する場合、自動的にソースディレクトリを検出します
# 追加の設定はコマンドライン引数で指定可能です
```

#### 2.3 依存関係の追加

`pyproject.toml` の `[dependency-groups]` セクションに追加します。

```toml
[dependency-groups]
dev = [
    "pytest>=9.0.2",
    "pytest-cov>=6.0.0",
    "pytest-asyncio>=0.25.0",
    "ruff>=0.14.11",
    "ty>=0.1.0",
]
```

または、`uv add` コマンドで直接追加することもできます:

```bash
uv add --dev ty
```

#### 2.4 ローカルでの実行確認

```bash
# Ruff (lint)
uv run ruff check .

# Ruff (format check)
uv run ruff format --check .

# ty (type check)
uv run ty src/

# pytest (test)
uv run pytest tests/ -v
```

#### Step 2 完了チェックリスト

- [ ] Ruff が設定されている
- [ ] `ty` がインストールされている
- [ ] 依存関係が追加されている
- [ ] ローカルで各ツールが動作する

---

### Step 3: GitHub Actions ワークフローの作成

#### 3.1 ディレクトリ構造

```txt
.github/
└── workflows/
    ├── ci.yml          # CI（テスト、lint）
    ├── build.yml       # Docker ビルド・プッシュ
    └── release.yml     # リリース時の処理（オプション）
```

#### 3.2 CI ワークフロー（`.github/workflows/ci.yml`）

```yaml
# CI ワークフロー - テストとコード品質チェック
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  lint:
    name: Lint & Format Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install 3.14

      - name: Install dependencies
        run: uv sync --frozen

      - name: Run Ruff (lint)
        run: uv run ruff check .

      - name: Run Ruff (format check)
        run: uv run ruff format --check .

  type-check:
    name: Type Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install 3.14

      - name: Install dependencies
        run: uv sync --frozen

      - name: Run ty
        run: uv run ty src/

  test:
    name: Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install 3.14

      - name: Install dependencies
        run: uv sync --frozen

      - name: Run tests
        run: uv run pytest tests/ -v --cov=src/kotonoha_bot --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml
          fail_ci_if_error: false
```

#### 3.3 ビルドワークフロー（`.github/workflows/build.yml`）

```yaml
# Docker ビルド・プッシュワークフロー
name: Build and Push Docker Image

on:
  push:
    branches: [main]
    tags: ["v*"]
  workflow_dispatch:

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build:
    name: Build and Push
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
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=ref,event=pr
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=sha,prefix=
            type=raw,value=latest,enable={{is_default_branch}}

      - name: Set up QEMU
        uses: docker/setup-qemu-action@v3

      - name: Build and push Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          platforms: linux/amd64,linux/arm64
```

#### Step 3 完了チェックリスト

- [ ] `.github/workflows/ci.yml` が作成されている
- [ ] `.github/workflows/build.yml` が作成されている
- [ ] GitHub Actions が正常に動作する
- [ ] プルリクエスト時に CI が実行される
- [ ] main ブランチへのプッシュで Docker イメージがビルドされる

---

### Step 4: Watchtower の設定

#### 4.1 Watchtower とは

Watchtower は、Docker コンテナを自動的に更新するツールです。GHCR から新しいイメージがプッシュされると、自動的にコンテナを更新します。

#### 4.2 `docker-compose.yml` への Watchtower 追加

`docker-compose.yml` に Watchtower サービスを追加します。

```yaml
# Kotonoha Discord Bot - Docker Compose (with Watchtower)
services:
  kotonoha-bot:
    image: ghcr.io/${GITHUB_REPOSITORY:-your-username/kotonoha-bot}:latest
    container_name: kotonoha-bot
    restart: unless-stopped
    user: root
    env_file:
      - .env
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./backups:/app/backups
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
          "import urllib.request; urllib.request.urlopen('http://localhost:8080/health', timeout=5).read()",
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
      - "com.centurylinklabs.watchtower.enable=true"

  watchtower:
    image: containrrr/watchtower
    container_name: watchtower
    restart: unless-stopped
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ~/.docker/config.json:/config.json:ro
    environment:
      - WATCHTOWER_CLEANUP=true
      - WATCHTOWER_POLL_INTERVAL=300
      - WATCHTOWER_LABEL_ENABLE=true
      - WATCHTOWER_NOTIFICATIONS=shoutrrr
      - WATCHTOWER_NOTIFICATION_URL=${WATCHTOWER_NOTIFICATION_URL:-}
    networks:
      - kotonoha-network

networks:
  kotonoha-network:
    driver: bridge
```

#### 4.3 GHCR 認証の設定（NAS 上）

NAS 上で GHCR にログインします。

```bash
# NAS 上で実行
# GitHub Personal Access Token を使用して GHCR にログイン
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin

# または、docker config.json を直接編集
# ~/.docker/config.json に認証情報が保存される
```

**GitHub Personal Access Token の作成方法**:

1. GitHub の「Settings」→「Developer settings」→「Personal access tokens」→「Tokens (classic)」を開く
2. 「Generate new token (classic)」をクリック
3. スコープで `write:packages` と `read:packages` を選択
4. トークンを生成して保存（再表示されないため注意）

#### 4.4 Watchtower の環境変数

| 変数                          | 説明                               | デフォルト |
| ----------------------------- | ---------------------------------- | ---------- |
| `WATCHTOWER_POLL_INTERVAL`    | イメージ更新チェック間隔（秒）     | 86400      |
| `WATCHTOWER_CLEANUP`          | 古いイメージを自動削除             | false      |
| `WATCHTOWER_LABEL_ENABLE`     | ラベルで対象コンテナを制限         | false      |
| `WATCHTOWER_NOTIFICATIONS`    | 通知方法（shoutrrr）               | -          |
| `WATCHTOWER_NOTIFICATION_URL` | 通知先 URL（Discord Webhook など） | -          |
| `WATCHTOWER_SCHEDULE`         | cron 形式でのスケジュール          | -          |
| `WATCHTOWER_ROLLING_RESTART`  | 一度に 1 コンテナずつ更新          | false      |

#### Step 4 完了チェックリスト

- [ ] Watchtower が `docker-compose.yml` に追加されている
- [ ] GHCR 認証が設定されている
- [ ] Watchtower が正常に動作する
- [ ] イメージ更新時に自動でコンテナが更新される

---

### Step 5: GitHub Secrets の設定

#### 5.1 必要なシークレット

| シークレット名      | 説明                 | 用途                   |
| ------------------- | -------------------- | ---------------------- |
| `DISCORD_TOKEN`     | Discord Bot トークン | テスト用（オプション） |
| `ANTHROPIC_API_KEY` | Anthropic API キー   | テスト用（オプション） |

**注意**: `GITHUB_TOKEN` は自動的に提供されるため、設定不要です。

#### 5.2 シークレットの設定方法

1. GitHub リポジトリの「Settings」を開く
2. 「Secrets and variables」→「Actions」を選択
3. 「New repository secret」をクリック
4. シークレット名と値を入力して保存

#### Step 5 完了チェックリスト

- [ ] 必要なシークレットが設定されている（オプション）
- [ ] シークレットが GitHub Actions で正しく参照できる

---

### Step 6: 通知の設定（オプション）

#### 6.1 Discord Webhook 通知

Watchtower から Discord に更新通知を送信できます。

```bash
# .env に追加
WATCHTOWER_NOTIFICATION_URL=discord://WEBHOOK_TOKEN@WEBHOOK_ID
```

**Discord Webhook の作成方法**:

1. Discord サーバーの「設定」→「連携サービス」→「ウェブフック」を開く
2. 「新しいウェブフック」をクリック
3. ウェブフック URL をコピー（`https://discord.com/api/webhooks/WEBHOOK_ID/WEBHOOK_TOKEN`）
4. `WATCHTOWER_NOTIFICATION_URL` に設定

#### 6.2 GitHub Actions の通知

GitHub Actions の結果を Discord に通知する場合は、CI ワークフローに以下を追加：

```yaml
- name: Notify Discord
  if: failure()
  uses: sarisia/actions-status-discord@v1
  with:
    webhook: ${{ secrets.DISCORD_WEBHOOK }}
    status: ${{ job.status }}
    title: "CI Failed"
```

#### Step 6 完了チェックリスト

- [ ] 通知先が設定されている（オプション）
- [ ] 通知が正常に送信される（オプション）

---

### Step 7: 動作確認とテスト

#### 7.1 CI の動作確認

1. ブランチを作成してプルリクエストを作成
2. GitHub Actions が自動実行されることを確認
3. テスト、lint、type-check が成功することを確認

#### 7.2 ビルドの動作確認

1. main ブランチにマージ
2. Docker イメージがビルドされることを確認
3. GHCR にイメージがプッシュされることを確認

#### 7.3 自動更新の動作確認

1. GHCR に新しいイメージがプッシュされる
2. Watchtower がイメージを検出することを確認
3. コンテナが自動更新されることを確認
4. Bot が正常に動作することを確認

#### Step 7 完了チェックリスト

- [ ] CI が正常に動作する
- [ ] ビルドが正常に動作する
- [ ] GHCR にイメージがプッシュされる
- [ ] Watchtower が自動更新を実行する
- [ ] Bot が正常に動作する

---

## 完了基準

### Phase 3 完了の定義

以下の全ての条件を満たした時、Phase 3 が完了とする:

1. **CI/CD パイプライン**

   - [ ] GitHub Actions が設定されている
   - [ ] プルリクエスト時にテストが自動実行される
   - [ ] main ブランチへのプッシュで Docker イメージがビルドされる

2. **Docker イメージ管理**

   - [ ] GHCR にイメージがプッシュされる
   - [ ] タグ付けが適切に行われる（latest、バージョン、SHA）
   - [ ] マルチプラットフォームビルド（amd64、arm64）

3. **自動更新**

   - [ ] Watchtower が設定されている
   - [ ] イメージ更新時に自動でコンテナが更新される
   - [ ] 更新後も Bot が正常に動作する

4. **コード品質**
   - [ ] テストが実装されている
   - [ ] lint チェックが通る
   - [ ] type チェックが通る

---

## トラブルシューティング

### 問題 1: GitHub Actions が失敗する

**症状**:

- ワークフローがエラーで終了する

**解決方法**:

1. エラーログを確認
2. 依存関係のバージョンを確認
3. シークレットが正しく設定されているか確認

---

### 問題 2: GHCR へのプッシュが失敗する

**症状**:

- `denied: permission_denied` エラー

**解決方法**:

1. リポジトリの「Settings」→「Actions」→「General」を確認
2. 「Workflow permissions」で「Read and write permissions」を選択
3. 「Allow GitHub Actions to create and approve pull requests」にチェック

---

### 問題 3: Watchtower がイメージを更新しない

**症状**:

- 新しいイメージがプッシュされてもコンテナが更新されない

**解決方法**:

1. GHCR 認証を確認：

   ```bash
   docker pull ghcr.io/your-username/kotonoha-bot:latest
   ```

2. Watchtower のログを確認：

   ```bash
   docker logs watchtower
   ```

3. ラベルを確認：

   ```bash
   docker inspect kotonoha-bot | grep -A 10 Labels
   ```

---

### 問題 4: マルチプラットフォームビルドが失敗する

**症状**:

- arm64 ビルドでエラーが発生する

**解決方法**:

1. QEMU エミュレーションを追加（`build.yml` に既に含まれています）:

   ```yaml
   - name: Set up QEMU
     uses: docker/setup-qemu-action@v3
   ```

2. `platforms` を単一プラットフォームに変更してテスト

---

## セキュリティ考慮事項

### シークレットの管理

- **GitHub Secrets**: API キー、トークンは GitHub Secrets で管理
- **環境変数ファイル**: `.env` ファイルは Git にコミットしない
- **GHCR 認証**: Personal Access Token は最小限の権限で作成

### イメージのセキュリティ

- **ベースイメージ**: 公式イメージを使用し、定期的に更新
- **脆弱性スキャン**: Trivy などでイメージをスキャン（オプション）
- **署名**: Cosign でイメージに署名（オプション）

---

## 次のフェーズへ

### Phase 4 の準備

Phase 3 が完了したら、以下の機能拡張を検討:

1. **機能改善**

   - メッセージ長制限対応（2000 文字超の場合は分割）
   - バッチ同期の定期実行タスク

2. **会話の契機拡張（Phase 5）**

   - スレッド型の実装
   - 聞き耳型の実装

3. **高度な機能（Phase 6）**
   - レート制限対応
   - スラッシュコマンド
   - エラーハンドリングの強化

---

## 参考資料

- [GitHub Actions ドキュメント](https://docs.github.com/en/actions)
- [GitHub Container Registry ドキュメント](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Watchtower ドキュメント](https://containrrr.dev/watchtower/)
- [Docker Build Push Action](https://github.com/docker/build-push-action)
- [Ruff ドキュメント](https://docs.astral.sh/ruff/)
- [pytest ドキュメント](https://docs.pytest.org/)
- [ty ドキュメント](https://github.com/astral-sh/ty)（Rust 製の高速型チェッカー）
- [実装ロードマップ](./../roadmap.md)
- [Phase 1 実装完了報告](./phase1.md)
- [Phase 2 実装完了報告](./phase2.md)

---

**作成日**: 2026 年 1 月 15 日
**最終更新日**: 2026 年 1 月 15 日（v2.0）
**対象フェーズ**: Phase 3（CI/CD と運用機能）
**前提条件**: Phase 2 完了済み ✅
**バージョン**: 2.0

### 更新履歴

- **v2.0** (2026-01-15): `roadmap.md` を基に再生成、実装ステップを整理、テストフレームワークとコード品質ツールの設定を追加
- **v1.0** (2026-01-15): 初版リリース
