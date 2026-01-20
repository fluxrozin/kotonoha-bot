# Discord Bot KOTONOHA（コトノハ）

## 概要

KOTONOHA は、場面緘黙で困っている人々が安心してコミュニケーションできる環境を提供することを目的とした Discord ボットです。AI（Claude）を使用して、優しく思いやりのある応答を生成します。メンションされた時だけでなく、スレッド内での会話や、自然な会話への参加など、様々な形で会話をサポートします。会話の内容は記録され、過去の会話を検索して参照できるため、会話の流れを理解し、継続的な対話が可能です。

## 主な機能

### 会話機能（3つの契機）

- **メンション応答型**: Bot をメンションすると AI が応答
- **スレッド型**: メンション時に自動スレッド作成、スレッド内で会話継続（メンション不要）
- **聞き耳型**: LLM 判断による自然な会話参加（チャンネルごとに有効/無効設定可能）

### AI・LLM 統合

- **Anthropic SDK 統合**: Claude API を直接使用（高パフォーマンス、セキュア）
- **OpenAI Embedding**: text-embedding-3-small によるベクトル化（1536次元）

### データベース・検索

- **PostgreSQL 永続化**: セッション管理により会話の文脈を維持・復元
- **ベクトル検索**: pgvector によるセマンティック検索機能
- **ハイブリッド検索**: ベクトル検索と pg_bigm キーワード検索の組み合わせ（固有名詞の検索精度向上）
- **知識ベース**: セッションアーカイブとベクトル検索による長期記憶機能

### 運用・管理機能

- **レート制限**: リクエストキューとトークンバケットによるレート制限管理
- **スラッシュコマンド**: `/chat reset`（会話履歴リセット）、`/chat status`（セッション状態表示）
- **エラーハンドリング**: ユーザーフレンドリーなエラーメッセージ
- **メッセージ分割**: 2000 文字超の応答を自動分割
- **バッチ同期**: 5 分ごとにアイドル状態のセッションを自動保存
- **Docker 化**: Docker Compose によるコンテナ化と 24 時間稼働対応
- **自動更新**: Watchtower によるコンテナ自動更新
- **CI/CD**: GitHub Actions による自動ビルド・デプロイ

## 技術スタック

### コア技術

- **Python**: 3.14
- **パッケージマネージャー**: uv
- **Discord**: discord.py >=2.6.4

### AI・LLM

- **LLM**: Claude API（Anthropic SDK >=0.76.0 直接使用）
  - 開発用: Claude Haiku 4.5（最速・低コスト）
  - 本番用: Claude Opus 4.5（最高品質）
  - バランス型: Claude Sonnet 4.5
- **Embedding**: OpenAI text-embedding-3-small（OpenAI SDK >=2.15.0、ベクトル化用、1536次元）

### データベース

- **PostgreSQL**: 18
- **拡張機能**:
  - pgvector 0.8.1（ベクトル検索）
  - pg_bigm 1.2-20250903（キーワード検索）
- **Python ライブラリ**:
  - asyncpg >=0.31.0（非同期 PostgreSQL ドライバ）
  - SQLAlchemy >=2.0.45（ORM）
  - Alembic >=1.18.1（データベースマイグレーション）
  - pgvector >=0.4.2（Python クライアント）

### その他の主要ライブラリ

- **ログ**: structlog >=25.5.0
- **設定管理**: pydantic-settings >=2.12.0
- **テキスト処理**:
  - langchain-text-splitters >=1.1.0（チャンク分割）
  - tiktoken >=0.12.0（トークンカウント）
- **リトライ**: tenacity >=9.1.2
- **JSON**: orjson >=3.11.5（高速 JSON 処理）

### インフラ・デプロイ

- **コンテナ**: Docker 24.0.2+、Docker Compose v2.20.1+
- **自動更新**: Watchtower latest
- **CI/CD**: GitHub Actions → GHCR（GitHub Container Registry）→ Watchtower

## クイックスタート

### 前提条件

**システム要件**:

- **OS**: WSL2 Ubuntu 22.04+ (Windows) または Linux/macOS
- **Python**: 3.14
- **Docker**: Docker Engine 24.0.2+ および Docker Compose（PostgreSQL のセットアップに必要）
- **Git**: リポジトリのクローンに必要
- **uv**: パッケージマネージャー

**API キー**:

- **Discord Bot Token**: [Discord Developer Portal](https://discord.com/developers/applications) から取得
- **Anthropic API Key**: [Anthropic Console](https://console.anthropic.com/) から取得（LLM 応答生成用）
- **OpenAI API Key**: [OpenAI Platform](https://platform.openai.com/) から取得（ベクトル化用）

### 開発環境のセットアップ

1. **リポジトリのクローン**

   ```bash
   git clone https://github.com/your-org/kotonoha-bot.git
   cd kotonoha-bot
   ```

2. **環境変数の設定**

   ```bash
   cp .env.example .env
   ```

   `.env` ファイルを編集して、以下の必須項目を設定してください:

   - **`DISCORD_TOKEN`**: Discord Bot Token
   - **`ANTHROPIC_API_KEY`**: Anthropic API Key
   - **`OPENAI_API_KEY`**: OpenAI API Key
   - **`LLM_MODEL`**: 使用する Claude モデル
     - 開発用（最速・低コスト）: `claude-haiku-4-5`
     - 本番用（最高品質）: `claude-opus-4-5`
     - バランス型: `claude-sonnet-4-5`
   - **`DATABASE_URL`**: PostgreSQL 接続文字列
     - Docker Compose を使用する場合: `postgresql://kotonoha:password@postgres:5432/kotonoha`
     - ローカルの場合: `postgresql://user:pass@localhost:5432/kotonoha`

3. **依存関係のインストール**

   ```bash
   # uv をインストール（未インストールの場合）
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # 依存関係をインストール
   uv sync
   ```

4. **データベースのセットアップ**

   開発環境では、以下の2つの方法から選択できます:

   **方法1: PostgreSQL のみ Docker で起動、Bot はローカルで実行（推奨）**

   - **メリット**: コード変更がすぐ反映されるため、開発効率が高い
   - **デメリット**: ローカル環境のセットアップが必要
   - **用途**: 日常的な開発・デバッグ

   ```bash
   # PostgreSQL コンテナの起動
   docker compose up -d postgres
   
   # マイグレーションの適用
   uv run alembic upgrade head
   
   # Bot をローカルで起動
   uv run python -m kotonoha_bot.main
   ```

   **方法2: PostgreSQL と Bot の両方を Docker で起動**

   - **メリット**: 本番環境に近い環境で動作確認できる
   - **デメリット**: コード変更時はコンテナの再ビルドが必要
   - **用途**: 本番環境に近い状態での動作確認・統合テスト

   ```bash
   # PostgreSQL コンテナの起動
   docker compose up -d postgres
   
   # Bot コンテナの起動
   docker compose up -d kotonoha-bot
   
   # または、全体を起動（PostgreSQL + Bot + Watchtower）
   # docker compose up -d
   
   # ログの確認
   docker compose logs -f kotonoha-bot
   ```

詳細なセットアップ手順は [Getting Started ガイド](./docs/getting-started.md) を参照してください。

## プロジェクト構成

```txt
kotonoha-bot/
├── src/kotonoha_bot/                    # ソースコード
│   ├── main.py                          # Bot エントリーポイント
│   ├── config.py                        # 設定管理（Pydantic V2）
│   ├── constants.py                     # 定数定義
│   ├── health.py                        # ヘルスチェック
│   ├── bot/                             # Discord Bot 関連
│   │   ├── client.py                   # Bot クライアント
│   │   ├── router.py                    # メッセージルーティング
│   │   ├── commands.py                  # スラッシュコマンド
│   │   └── handlers/                    # イベントハンドラー（Phase 10で分割）
│   │       ├── __init__.py              # MessageHandler（Facade）
│   │       ├── mention.py               # メンション型ハンドラー
│   │       ├── thread.py                # スレッド型ハンドラー
│   │       └── eavesdrop.py             # 聞き耳型ハンドラー
│   ├── services/                        # サービス層（ビジネスロジック）
│   │   ├── ai.py                        # AI プロバイダー（Anthropic SDK）
│   │   ├── session.py                   # セッション管理
│   │   └── eavesdrop.py                 # 聞き耳型サービス
│   ├── db/                              # データベース層
│   │   ├── base.py                      # データベース抽象化レイヤー（Protocol）
│   │   ├── models.py                    # データモデル
│   │   └── postgres.py                  # PostgreSQL 実装（pgvector + pg_bigm）
│   ├── features/                        # 機能別モジュール
│   │   └── knowledge_base/              # 知識ベース機能
│   │       ├── embedding_processor.py   # Embedding処理
│   │       ├── session_archiver.py      # セッションアーカイブ
│   │       └── metrics.py               # メトリクス
│   ├── external/                        # 外部サービス統合
│   │   └── embedding/                  # Embedding プロバイダー
│   │       └── openai_embedding.py      # OpenAI Embedding API
│   ├── errors/                          # エラーハンドリング
│   │   ├── ai.py                        # AI関連エラー
│   │   ├── database.py                 # データベース関連エラー
│   │   ├── discord.py                  # Discord関連エラー
│   │   └── messages.py                  # エラーメッセージ（一元管理）
│   ├── rate_limit/                      # レート制限
│   │   ├── monitor.py                  # レート制限モニタリング
│   │   ├── request_queue.py             # リクエストキュー
│   │   └── token_bucket.py              # トークンバケット
│   ├── utils/                           # ユーティリティ
│   │   ├── datetime.py                 # 日時処理
│   │   ├── message.py                  # メッセージ処理
│   │   └── prompts.py                  # プロンプト読み込み
│   └── prompts/                         # プロンプトファイル
├── tests/                               # テスト
│   ├── unit/                            # 単体テスト
│   │   ├── bot/                         # Bot関連テスト
│   │   ├── db/                          # データベース関連テスト
│   │   ├── services/                    # サービス層テスト
│   │   ├── errors/                      # エラーハンドリングテスト
│   │   ├── rate_limit/                  # レート制限テスト
│   │   └── utils/                       # ユーティリティテスト
│   ├── integration/                     # 統合テスト
│   └── performance/                     # パフォーマンステスト
├── docs/                                # ドキュメント
├── alembic/                             # データベースマイグレーション
│   └── versions/                        # マイグレーションファイル
│       ├── 202601182039_initial_schema.py
│       └── 202601201940_add_pg_bigm_extension.py
├── scripts/                             # スクリプト
│   ├── entrypoint.sh                    # エントリーポイント
│   ├── backup.sh                        # バックアップ
│   └── restore.sh                       # リストア
├── logs/                                # ログファイル（自動生成）
├── backups/                             # バックアップファイル（自動生成）
├── Dockerfile                           # Bot コンテナイメージ
├── Dockerfile.postgres                  # PostgreSQL カスタムイメージ（pg_bigm 対応）
├── docker-compose.yml                   # Docker Compose 設定
└── pyproject.toml                       # プロジェクト設定
```

### プロンプトファイルの管理

プロンプトファイルは `src/kotonoha_bot/prompts/` フォルダに集約されています（Phase 10で移動）。Docker を使用している場合、コンテナイメージに含まれるため、変更時はコンテナの再ビルドが必要です。

詳細は [プロンプト管理ガイド](./docs/50_implementation/51_guides/) を参照してください。

## ドキュメント

詳細なドキュメントは [`docs/`](./docs/) ディレクトリを参照してください。

### 主要ドキュメント

- **[Getting Started](./docs/getting-started.md)**: 開発環境のセットアップガイド
- **[実装ロードマップ](./docs/00_planning/roadmap.md)**: 段階的な実装計画
- **[システムアーキテクチャ](./docs/20_architecture/)**: システム構成と技術スタック
- **[フェーズ別実装計画](./docs/00_planning/phases/)**: 各 Phase の実装詳細

### ドキュメント一覧

- [要件定義](./docs/10_requirements/)
- [アーキテクチャ設計](./docs/20_architecture/)
- [基本設計](./docs/30_design_basic/)
- [詳細設計](./docs/40_design_detailed/)
- [実装ガイド](./docs/50_implementation/)
- [テスト計画](./docs/60_testing/)
- [運用ガイド](./docs/90_operations/)

## Docker デプロイ

### 初回セットアップ

```bash
# ディレクトリの作成（ログとバックアップ用）
mkdir -p logs backups
sudo chown -R 1000:1000 logs backups

# 環境変数の設定
cp .env.example .env
# .env を編集して必要な値を設定（DISCORD_TOKEN、ANTHROPIC_API_KEY、OPENAI_API_KEY など）
```

### コンテナの起動

**方法1: ローカルでビルドして起動**

```bash
# PostgreSQL カスタムイメージのビルド（pg_bigm 対応）
docker compose build postgres

# Bot イメージのビルド
docker compose build kotonoha-bot

# 全体を起動（PostgreSQL + Bot + Watchtower）
docker compose up -d
```

**方法2: GHCR からイメージをプルして起動（推奨）**

```bash
# GHCR からイメージをプル
docker compose pull

# 全体を起動
docker compose up -d
```

### 動作確認

```bash
# コンテナの状態確認
docker compose ps

# ログの確認
docker compose logs -f kotonoha-bot

# マイグレーションの確認（Bot 起動時に自動適用されますが、手動でも実行可能）
docker compose exec kotonoha-bot alembic upgrade head
```

### 重要な注意事項

- **PostgreSQL データ**: Docker ボリューム（`postgres_data`）で管理されます
- **カスタム PostgreSQL イメージ**: `Dockerfile.postgres` でビルドされるか、GHCR からプルされます（pg_bigm 対応）
- **Watchtower**: 自動更新機能（`.env` で `WATCHTOWER_ENABLED=false` に設定すると無効化）
- **ボリュームマウント**: `logs/`、`backups/` はホスト側にマウントされます

詳細は [Phase 2 実装完了報告](./docs/00_planning/phases/phase02.md) および [開発環境ガイド](./docs/50_implementation/51_guides/development-environment-guide.md) を参照してください。

## 開発

### 開発環境のセットアップ

```bash
# 開発用依存関係を含めてインストール
uv sync --group dev

# コードフォーマットとリント
uv run ruff format .
uv run ruff check .

# 型チェック
uv run ty check src/

# テストの実行
uv run pytest

# カバレッジ付きでテスト実行
uv run pytest --cov=src/kotonoha_bot --cov-report=html
```

## ライセンス

MIT License

Copyright (c) 2026 fluxrozin

詳細は [LICENSE](./LICENSE) ファイルを参照してください。

## 作者

- fluxrozin ([fluxrozin@gmail.com](mailto:fluxrozin@gmail.com))

## リンク

詳細なドキュメントは [docs/README.md](./docs/README.md) を参照してください。

---

**注意**: このプロジェクトは開発中です。本番環境で使用する前に、適切なセキュリティ設定とテストを実施してください。
