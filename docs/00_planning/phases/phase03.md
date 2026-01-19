# Phase 3 実装完了報告 - CI/CD と運用機能

Kotonoha Discord Bot の Phase 3（CI/CD と運用機能）の実装完了報告書

## 目次

1. [Phase 3 の目標](#phase-3-の目標)
2. [実装状況](#実装状況)
3. [前提条件](#前提条件)
4. [実装ステップ（参考情報）](#実装ステップ参考情報)
5. [完了基準](#完了基準)
6. [トラブルシューティング](#トラブルシューティング)
7. [次のフェーズへ](#次のフェーズへ)

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

## 実装状況

### ✅ 実装完了（2026 年 1 月）

Phase 3 の実装は完了しています。以下の機能が実装されています:

**実装済み機能**:

- ✅ テストフレームワーク（pytest）の設定
- ✅ コード品質ツールの設定（Ruff、ty）
- ✅ GitHub Actions CI ワークフロー（lint、format、type-check、test）
- ✅ GitHub Actions ビルドワークフロー（Docker イメージのビルド・プッシュ）
- ✅ GHCR への自動プッシュ（マルチプラットフォーム: amd64、arm64）
- ✅ Watchtower による自動更新機能
- ✅ 通知機能（Discord Webhook、オプション）

**実装されたファイル構造**:

```txt
.github/
└── workflows/
    ├── ci.yml          # ✅ 実装済み（lint、format、type-check、test）
    └── build.yml       # ✅ 実装済み（Docker ビルド・プッシュ）

pyproject.toml          # ✅ pytest、Ruff、ty の設定追加済み
docker-compose.yml      # ✅ Watchtower サービス追加済み
.env.example            # ✅ Watchtower 設定追加済み
```

**CI/CD パイプライン**:

- ✅ **CI ワークフロー**: プルリクエスト時に自動実行
  - Lint チェック（Ruff）
  - フォーマットチェック（Ruff）
  - 型チェック（ty）
  - テスト実行（pytest、カバレッジ付き）
- ✅ **ビルドワークフロー**: main ブランチへのプッシュ時に自動実行
  - Docker イメージのビルド
  - GHCR へのプッシュ
  - マルチプラットフォームビルド（amd64、arm64）
  - タグ付け（latest、バージョン、SHA）

**自動更新機能**:

- ✅ Watchtower コンテナの設定
- ✅ ラベルベースの更新制御
- ✅ 古いイメージの自動削除
- ✅ 通知機能（Discord Webhook、オプション）

**Phase 3 完了後の確認事項**:

- ✅ GitHub Actions が正常に動作する
- ✅ プルリクエスト時に CI が自動実行される
- ✅ main ブランチへのプッシュで Docker イメージがビルドされる
- ✅ GHCR にイメージがプッシュされる
- ✅ Watchtower がイメージを検出して自動更新する
- ✅ 更新後も Bot が正常に動作する
- ✅ Phase 4（機能改善）の実装準備が整っている

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
- NAS への SSH アクセス（GHCR 認証設定時）

### 必要な認証情報

- GitHub Personal Access Token（GHCR 用、NAS 上で `docker login` する場合に必要）
- Discord Webhook URL（通知機能を使用する場合、オプション）

**注意**:

- **GitHub Actions 内**: `GITHUB_TOKEN` は GitHub Actions で自動的に提供されるため、GitHub Actions のワークフロー内では設定不要です。
- **NAS 上**: NAS 上で GHCR からイメージをプルする場合は、Personal Access Token を手動で作成して `docker login` する必要があります（詳細は [デプロイメント・運用ガイド](../../90_90_operations/deployment-operations.md) を参照）。

---

## 実装ステップ（参考情報）

> **注意**: 以下の実装ステップは既に完了しています。参考情報として記載しています。

このセクションでは、Phase 3 で実装した各ステップの詳細を記載しています。実装は完了しているため、新規実装時の参考としてご利用ください。

### Step 1: テストフレームワークの設定 (30 分) ✅ 完了

#### 1.1 pytest 設定（`pyproject.toml`）

`pyproject.toml` に pytest の設定を追加しました。

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

#### 1.2 テストディレクトリ構造

```txt
tests/
├── __init__.py
├── test_basic.py        # ✅ 実装済み
├── unit/                # 単体テスト
│   ├── __init__.py
│   ├── test_session.py
│   ├── test_ai.py
│   └── test_db.py
└── integration/         # 統合テスト（オプション）
    ├── __init__.py
    └── test_bot.py
```

#### Step 1 完了チェックリスト

- [x] `pyproject.toml` に pytest 設定が追加されている
- [x] テストディレクトリ構造が作成されている
- [x] 基本的なテストが実装されている
- [x] ローカルで `pytest` が実行できる

---

### Step 2: コード品質ツールの設定 (30 分) ✅ 完了

#### 2.1 Ruff 設定（`pyproject.toml`）

`pyproject.toml` に Ruff の設定を追加しました。

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

`ty` は Rust 製の高速な型チェッカーで、mypy の代替として使用できます。

```toml
[tool.ty]
# ty は pyproject.toml が存在する場合、自動的にソースディレクトリを検出します
# 追加の設定はコマンドライン引数で指定可能です
```

#### 2.3 依存関係の追加

`pyproject.toml` の `[dependency-groups]` セクションに追加しました。

```toml
[dependency-groups]
dev = [
    "pytest>=9.0.2",
    "pytest-asyncio>=1.3.0",
    "pytest-cov>=7.0.0",
    "ruff>=0.14.11",
    "ty>=0.0.11",
]
```

#### Step 2 完了チェックリスト

- [x] Ruff が設定されている
- [x] `ty` がインストールされている
- [x] 依存関係が追加されている
- [x] ローカルで各ツールが動作する

---

### Step 3: GitHub Actions ワークフローの作成 (2 時間) ✅ 完了

#### 3.1 ディレクトリ構造

```txt
.github/
└── workflows/
    ├── ci.yml          # ✅ 実装済み
    └── build.yml       # ✅ 実装済み
```

#### 3.2 CI ワークフロー（`.github/workflows/ci.yml`）

プルリクエスト時に自動実行される CI ワークフローを実装しました。

**主な機能**:

- Lint チェック（Ruff）
- フォーマットチェック（Ruff）
- 型チェック（ty）
- テスト実行（pytest、カバレッジ付き）

**トリガー**:

- `push` イベント（main、develop ブランチ）
- `pull_request` イベント（main ブランチへの PR）

#### 3.3 ビルドワークフロー（`.github/workflows/build.yml`）

main ブランチへのプッシュ時に自動実行されるビルドワークフローを実装しました。

**主な機能**:

- Docker イメージのビルド
- GHCR へのプッシュ
- マルチプラットフォームビルド（amd64、arm64）
- タグ付け（latest、バージョン、SHA）

**トリガー**:

- `push` イベント（main ブランチ）
- `tags` イベント（v\* タグ）
- `workflow_dispatch`（手動実行）

#### Step 3 完了チェックリスト

- [x] `.github/workflows/ci.yml` が作成されている
- [x] `.github/workflows/build.yml` が作成されている
- [x] GitHub Actions が正常に動作する
- [x] プルリクエスト時に CI が実行される
- [x] main ブランチへのプッシュで Docker イメージがビルドされる

---

### Step 4: Watchtower の設定 (1 時間) ✅ 完了

#### 4.1 Watchtower とは

Watchtower は、Docker コンテナの自動更新ツールです。GitHub Container Registry (GHCR) から新しいイメージを定期的にチェックし、更新があれば自動的にコンテナを再起動して最新版に更新します。

**詳細**: <https://containrrr.dev/watchtower/>

**動作の仕組み**:

1. `kotonoha-bot` コンテナに `com.centurylinklabs.watchtower.enable=true` ラベルが付いている
2. Watchtower がこのラベルを検出し、定期的にイメージをチェック（デフォルト: 5 分ごと）
3. 新しいイメージがあれば自動的にコンテナを更新
4. 古いイメージを削除（`WATCHTOWER_CLEANUP=true` の場合）

#### 4.2 `docker-compose.yml` への Watchtower 追加

`docker-compose.yml` に Watchtower サービスを追加しました。

**主な設定**:

- イメージ: `containrrr/watchtower:latest`
- 環境変数: `.env` ファイルから読み込み
- ボリューム: Docker ソケットをマウント
- ネットワーク: `kotonoha-network` に接続

#### 4.3 GHCR 認証の設定（NAS 上）

**重要**: 詳細な手順は [デプロイメント・運用ガイド](../../90_90_operations/deployment-operations.md#ghcr-認証の設定方法) を参照してください。

**簡易手順**:

1. **GitHub Personal Access Token の作成**

   - GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
   - スコープ: `write:packages`、`read:packages`
   - トークンをコピーして保存（`ghp_` で始まる文字列）

2. **`.env` ファイルの設定**

   ```bash
   # .env.example から .env を作成（初回のみ）
   cp .env.example .env

   # .env ファイルを編集
   nano .env

   # 以下の行を設定:
   GITHUB_USERNAME=your-github-username
   GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

   # ファイルの権限を設定
   chmod 600 .env
   ```

3. **GHCR へのログイン**

   ```bash
   # SSH で NAS にログイン
   ssh admin@nas-ip-address
   cd /volume1/docker/kotonoha-bot

   # .env から環境変数を読み込んでログイン
   GITHUB_USERNAME=$(grep '^GITHUB_USERNAME=' .env | cut -d= -f2)
   GITHUB_TOKEN=$(grep '^GITHUB_TOKEN=' .env | cut -d= -f2)
   echo $GITHUB_TOKEN | docker login ghcr.io -u $GITHUB_USERNAME --password-stdin
   ```

4. **`docker-compose.yml` の設定**

   - `~/.docker/config.json:/config.json:ro` のコメントアウトを解除（ファイルが存在する場合のみ）

5. **Watchtower の再起動**

   ```bash
   docker-compose restart watchtower
   ```

**注意**:

- `.env` ファイルは Git リポジトリに含まれていないため、初回セットアップ時に `.env.example` から `.env` を作成する必要があります
- パブリックイメージを使用する場合は、この手順は不要です
- 詳細な手順やトラブルシューティングは [デプロイメント・運用ガイド](../../90_90_operations/deployment-operations.md#ghcr-認証の設定方法) を参照してください

#### 4.4 Watchtower の環境変数

`.env.example` に以下の環境変数が追加されています:

| 変数                          | 説明                               | デフォルト |
| ----------------------------- | ---------------------------------- | ---------- |
| `WATCHTOWER_POLL_INTERVAL`    | イメージ更新チェック間隔（秒）     | 300        |
| `WATCHTOWER_CLEANUP`          | 古いイメージを自動削除             | true       |
| `WATCHTOWER_LABEL_ENABLE`     | ラベルで対象コンテナを制限         | true       |
| `WATCHTOWER_NOTIFICATIONS`    | 通知方法（shoutrrr）               | shoutrrr   |
| `WATCHTOWER_NOTIFICATION_URL` | 通知先 URL（Discord Webhook など） | -          |
| `WATCHTOWER_SCHEDULE`         | cron 形式でのスケジュール          | -          |
| `WATCHTOWER_ROLLING_RESTART`  | 一度に 1 コンテナずつ更新          | false      |

#### Step 4 完了チェックリスト

- [x] Watchtower が `docker-compose.yml` に追加されている
- [x] GHCR 認証が設定されている（必要に応じて）
- [x] Watchtower が正常に動作する
- [x] イメージ更新時に自動でコンテナが更新される

**自動更新の確認方法**:

1. **Watchtower のログを確認**:

   ```bash
   docker logs watchtower --tail 100
   # 更新が検出された場合、以下のようなログが表示されます:
   # time="2026-01-15T02:30:00Z" level=info msg="Found new image: ghcr.io/your-username/kotonoha-bot:latest"
   # time="2026-01-15T02:30:01Z" level=info msg="Stopping /kotonoha-bot (abc123def456) with SIGTERM"
   ```

2. **コンテナの作成日時を確認**:

   ```bash
   docker ps -a --format "table {{.Names}}\t{{.Image}}\t{{.CreatedAt}}"
   ```

3. **手動で更新をトリガーしてテスト**:

   ```bash
   docker exec watchtower watchtower --run-once
   ```

詳細な確認方法は [デプロイメント・運用ガイド](../../90_90_operations/deployment-operations.md) を参照してください。

---

### Step 5: 通知の設定（オプション） (30 分) ✅ 完了

#### 5.1 Discord Webhook 通知

Watchtower から Discord に更新通知を送信できます。

**設定方法**:

1. Discord サーバーで Webhook を作成
2. Webhook URL から ID とトークンを抽出
3. `.env` ファイルに `WATCHTOWER_NOTIFICATION_URL` を設定

**形式**:

```env
WATCHTOWER_NOTIFICATIONS=shoutrrr
WATCHTOWER_NOTIFICATION_URL=discord://WEBHOOK_TOKEN@WEBHOOK_ID
```

**詳細な手順**: [デプロイメント・運用ガイド](../../90_90_operations/deployment-operations.md) を参照してください。

#### Step 5 完了チェックリスト

- [x] 通知先が設定されている（オプション）
- [x] 通知が正常に送信される（オプション）

---

### Step 6: 動作確認とテスト (1 時間) ✅ 完了

#### 6.1 CI の動作確認

1. ブランチを作成してプルリクエストを作成
2. GitHub Actions が自動実行されることを確認
3. テスト、lint、type-check が成功することを確認

#### 6.2 ビルドの動作確認

1. main ブランチにマージ
2. Docker イメージがビルドされることを確認
3. GHCR にイメージがプッシュされることを確認

#### 6.3 自動更新の動作確認

1. GHCR に新しいイメージがプッシュされる
2. Watchtower がイメージを検出することを確認
3. コンテナが自動更新されることを確認
4. Bot が正常に動作することを確認

#### Step 6 完了チェックリスト

- [x] CI が正常に動作する
- [x] ビルドが正常に動作する
- [x] GHCR にイメージがプッシュされる
- [x] Watchtower が自動更新を実行する
- [x] Bot が正常に動作する

---

## 完了基準

### Phase 3 完了の定義

以下の全ての条件を満たした時、Phase 3 が完了とする:

1. **CI/CD パイプライン**

   - [x] GitHub Actions が設定されている（実装済み）
   - [x] プルリクエスト時にテストが自動実行される（実装済み）
   - [x] main ブランチへのプッシュで Docker イメージがビルドされる（実装済み）

2. **Docker イメージ管理**

   - [x] GHCR にイメージがプッシュされる（実装済み）
   - [x] タグ付けが適切に行われる（latest、バージョン、SHA）（実装済み）
   - [x] マルチプラットフォームビルド（amd64、arm64）（実装済み）

3. **自動更新**

   - [x] Watchtower が設定されている（実装済み）
   - [x] イメージ更新時に自動でコンテナが更新される（実装済み）
   - [x] 更新後も Bot が正常に動作する（実装済み）

4. **コード品質**
   - [x] テストが実装されている（実装済み）
   - [x] lint チェックが通る（実装済み）
   - [x] type チェックが通る（実装済み）

---

## Phase 3 完了報告

**完了日**: 2026 年 1 月 15 日

### 実装サマリー

Phase 3（CI/CD と運用機能）のすべての目標を達成しました。

| カテゴリ             | 状態    | 備考                                                      |
| -------------------- | ------- | --------------------------------------------------------- |
| テストフレームワーク | ✅ 完了 | pytest 設定、カバレッジ設定                               |
| コード品質ツール     | ✅ 完了 | Ruff（lint、format）、ty（type-check）                    |
| CI ワークフロー      | ✅ 完了 | lint、format、type-check、test の自動実行                 |
| ビルドワークフロー   | ✅ 完了 | Docker イメージのビルド・プッシュ、マルチプラットフォーム |
| Watchtower 設定      | ✅ 完了 | 自動更新機能、通知機能（オプション）                      |
| GHCR 認証            | ✅ 完了 | Personal Access Token による認証                          |

### Phase 3 完了時のアクション

```bash
# 全ての変更をコミット
git add .
git commit -m "feat: Phase 3 CI/CD・運用機能完了

- テストフレームワーク設定（pytest）
- コード品質ツール設定（Ruff、ty）
- GitHub Actions CIワークフロー（lint、format、type-check、test）
- GitHub Actions ビルドワークフロー（Dockerイメージのビルド・プッシュ）
- GHCRへの自動プッシュ（マルチプラットフォーム: amd64、arm64）
- Watchtowerによる自動更新機能
- 通知機能（Discord Webhook、オプション）

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

# タグを作成
git tag -a v0.3.0-phase3 -m "Phase 3 CI/CD・運用機能完了"

# リモートにプッシュ
git push origin main
git push origin v0.3.0-phase3
```

### 次のフェーズ

Phase 3 が完了したため、Phase 4（機能改善）に進むことができます。

詳細は [実装ロードマップ](../roadmap.md) を参照してください。

---

## トラブルシューティング

### 問題 1: GitHub Actions が失敗する

**症状**:

- ワークフローがエラーで終了する

**解決方法**:

1. エラーログを確認（GitHub Actions のログを確認）
2. 依存関係のバージョンを確認（`pyproject.toml`、`uv.lock`）
3. ローカルで同じコマンドを実行して再現する

**よくあるエラー**:

- **型チェックエラー**: `ty` のエラーを修正
- **Lint エラー**: `ruff check .` を実行して修正
- **フォーマットエラー**: `ruff format .` を実行して修正

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

4. 環境変数を確認：

   ```bash
   docker exec watchtower env | grep WATCHTOWER
   ```

**詳細**: [トラブルシューティングガイド](../../90_90_operations/troubleshooting.md) を参照してください。

---

### 問題 4: マルチプラットフォームビルドが失敗する

**症状**:

- arm64 ビルドでエラーが発生する

**解決方法**:

1. QEMU エミュレーションが正しく設定されているか確認（`build.yml` に既に含まれています）
2. `platforms` を単一プラットフォームに変更してテスト
3. ビルドログを確認してエラーの詳細を確認

---

### 問題 5: Docker API バージョンの問題（Watchtower）

**症状**:

- エラー `"client version 1.25 is too old. Minimum supported API version is 1.44"`

**解決方法**:

1. **Docker をアップグレードする（推奨）**
2. **Watchtower を無効化する**（このサービス全体をコメントアウト）
3. **古いバージョンの Watchtower を使用する**（例: `containrrr/watchtower:v1.5.3`）

詳細は [トラブルシューティングガイド](../../90_90_operations/troubleshooting.md) を参照してください。

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
- [実装ロードマップ](../roadmap.md)
- [Phase 1 実装完了報告](./phase01.md)
- [Phase 2 実装完了報告](./phase02.md)
- [デプロイメント・運用ガイド](../../90_90_operations/deployment-operations.md)
- [トラブルシューティングガイド](../../90_90_operations/troubleshooting.md)

---

**作成日**: 2026 年 1 月 15 日
**最終更新日**: 2026 年 1 月 15 日
**対象フェーズ**: Phase 3（CI/CD と運用機能）
**実装状況**: ✅ 実装完了（2026 年 1 月）
**前提条件**: Phase 2 完了済み ✅
**次のフェーズ**: Phase 4（機能改善）
**バージョン**: 3.0

### 更新履歴

- **v3.0** (2026-01-15): 実装完了報告書として再構成、実装状況セクションを追加、詳細手順は別ドキュメントへの参照に整理
