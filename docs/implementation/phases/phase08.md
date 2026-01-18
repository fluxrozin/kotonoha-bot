# Phase 8: PostgreSQL + pgvector 実装 詳細実装計画書

**作成日**: 2026年1月19日
**バージョン**: 1.0
**対象プロジェクト**: kotonoha-bot v0.8.0
**前提条件**: Phase 7（aiosqlite 実装）完了済み、全テスト通過
**開発体制**: 1人開発（将来的に機能は倍増予定）

---

## 目次

1. [エグゼクティブサマリー](#1-エグゼクティブサマリー)
2. [現状分析](#2-現状分析)
3. [設計方針](#3-設計方針)
4. [データベーススキーマ設計](#4-データベーススキーマ設計)
5. [詳細実装計画](#5-詳細実装計画)
6. [テスト計画](#6-テスト計画)
7. [完了基準とチェックリスト](#7-完了基準とチェックリスト)
8. [リスク管理](#8-リスク管理)
9. [スキーマバージョン管理とコスト見積もり](#9-スキーマバージョン管理とコスト見積もり)
10. [導入・デプロイ手順](#10-導入デプロイ手順)
11. [将来の改善計画](#11-将来の改善計画)

---

## 1. エグゼクティブサマリー

### 1.1 目的

PostgreSQL + pgvector を新規実装し、以下の機能を実現する：

1. **高性能なベクトル検索**: pgvector によるネイティブなベクトル検索機能
2. **知識ベース基盤**: Source-Chunk構造による統合知識ベースの実装
3. **非同期Embedding処理**: Botの応答速度を落とさないバックグラウンド処理
4. **スケーラビリティ**: 将来的なデータ増加や機能拡張に対応

### 1.2 スコープ

- **PostgreSQL 実装**: asyncpg を使用した非同期実装
- **知識ベーススキーマ**: Source-Chunk構造の実装
- **Embedding処理**: OpenAI API (text-embedding-3-small) を使用した非同期処理
- **Docker Compose**: PostgreSQL コンテナの追加

### 1.3 主要な実装項目

| 項目 | 内容 |
|------|------|
| PostgreSQL実装 | `PostgreSQLDatabase` クラスの実装 |
| 知識ベーススキーマ | `knowledge_sources` と `knowledge_chunks` テーブル |
| Embedding処理 | バックグラウンドタスクによる非同期処理 |
| ベクトル検索 | pgvector の `<=>` 演算子を使用した検索 |

### 1.4 期間

約 10-15 日

---

## 2. 現状分析

### 2.1 現在のデータベース実装

- **SQLite**: `src/kotonoha_bot/db/sqlite.py` (242行) - Phase 7で実装済み
- **aiosqlite**: 非同期実装済み
- **セッション管理**: ChatSession の保存・読み込み機能

### 2.2 課題

1. **ベクトル検索の非効率**: SQLiteではPython側で類似度計算が必要で、大規模データでの性能劣化が懸念される
2. **スケーラビリティの限界**: SQLiteでは大規模な知識ベースの管理が困難
3. **知識ベース機能の未実装**: ベクトル検索機能が未実装

### 2.3 設計方針

**重要**: このフェーズは**新規設計**です。SQLiteからの移行ツールは作成せず、既存データは破棄します。

Phase 8では、PostgreSQL + pgvector を新規導入し、以下の機能を実現します：

- **高性能なベクトル検索**: pgvector によるネイティブなベクトル検索
- **スケーラビリティ**: 大規模な知識ベースに対応
- **統合知識ベース**: Source-Chunk構造による柔軟なデータ管理

### 2.4 既存のバックグラウンドタスク

- `cleanup_task`: 1時間ごとのセッションクリーンアップ
- `batch_sync_task`: 5分ごとのバッチ同期
- `discord.ext.tasks` を使用した実装パターンが確立済み

---

## 3. 設計方針

### 3.1 PostgreSQL実装

**方針**: PostgreSQL + pgvector を専用実装として採用

PostgreSQL + pgvector による高性能なベクトル検索機能を実現します。
asyncpg を使用した非同期実装により、Botの応答速度を維持しながら、
大規模な知識ベースを効率的に管理できます。

### 3.2 知識ベーススキーマ設計

#### 設計思想：すべてのデータを「Source」と「Chunk」に抽象化する

どんなデータが来ても、以下の2段階で管理します：

- **Source (親)**: データの「出処」を管理する（ファイルメタデータ、WebのURL、Discordのスレッド情報）
- **Chunk (子)**: 検索対象となる「テキスト実体」と「ベクトル」を管理する

この設計のメリット：

1. **拡張性**: 将来「動画検索」を追加する場合、`source_type` に `video` を追加するだけで、テーブル構造を変更する必要がありません
2. **メタデータの柔軟性**: JSONB (`metadata`, `location`) を使用することで、
   ファイルの種類ごとに異なる属性（PDFのページ番号、音声の秒数など）を
   柔軟に管理できます
3. **状態管理**: `status` カラムにより、OCRやEmbeddingなどの重い処理を
   バックグラウンドワーカーに任せる設計（Producer-Consumerパターン）が
   容易に実装できます

### 3.3 非同期Embedding処理

**高速保存パターン**:

1. **即時保存**: テキストのみ保存（`embedding=NULL`）
2. **バックグラウンド処理**: 定期タスクでベクトル化して更新
3. **検索時**: `embedding IS NOT NULL` のレコードのみ検索対象

---

## 4. データベーススキーマ設計

> **参照**: 詳細なデータベーススキーマ設計については、
> [PostgreSQL スキーマ設計書](../architecture/postgresql-schema-design.md) を参照してください。

このセクションでは、実装に必要なスキーマ設計の概要を説明します。詳細なDDL、ER図、データフロー、設計のメリットなどは、上記の設計書を参照してください。

### 4.1 スキーマ設計の概要

データベーススキーマは、**「短期記憶（Sessions）」** と **「長期記憶（Knowledge）」** の2つのエリアで構成されます。

- **短期記憶（Sessions）**: Discord Botがリアルタイムに読み書きする場所。高速動作優先。
- **長期記憶（Knowledge）**: AI検索用。あらゆるデータ（会話、ファイル、Web）を「Source」と「Chunk」に抽象化して管理。

詳細なER図、テーブル定義、インデックス設計については、
[PostgreSQL スキーマ設計書 - 2. ER図](../architecture/postgresql-schema-design.md#2-er図)
および
[4. テーブル定義](../architecture/postgresql-schema-design.md#4-テーブル定義) を参照してください。

### 4.2 データフローの概要

データフローの詳細な運用イメージについては、
[PostgreSQL スキーマ設計書 - 12. データフローの運用イメージ](../architecture/postgresql-schema-design.md#12-データフローの運用イメージ)
を参照してください。

主なデータフロー：

1. **リアルタイム会話**: `sessions` テーブルにメッセージを追記（APIコストゼロ）
2. **知識化バッチ処理**: 非アクティブなセッションを `knowledge_sources` と `knowledge_chunks` に変換
3. **マルチモーダル入力**: PDF/画像などを `knowledge_sources` に登録し、バックグラウンドで処理
4. **統合検索**: pgvector によるベクトル類似度検索で、すべてのデータソースを横断検索

### 4.3 設計のメリット

設計のメリットの詳細については、
[PostgreSQL スキーマ設計書 - 1.2 設計思想](../architecture/postgresql-schema-design.md#12-設計思想)
を参照してください。

主なメリット：

- **短期記憶と長期記憶の分離**: それぞれ最適化されたインデックスで管理
- **拡張性**: 将来の機能拡張に対応可能
- **メタデータの柔軟性**: JSONBによる柔軟な属性管理
- **状態管理**: Producer-Consumerパターンが容易
- **マルチモーダル対応**: すべてのデータを同じスキーマで管理
- **統合検索**: 1つのSQLクエリで横断検索

---

## 5. 詳細実装計画

### 5.1 実装ステップ概要

| Step | 内容 | 期間 |
|------|------|------|
| 0 | 依存関係の確認と設計レビュー | 0.5日 |
| 1 | データベース抽象化レイヤーの実装 | 2-3日 |
| 2 | PostgreSQL 実装の追加 | 3-4日 |
| 3 | ベクトル検索機能の実装 | 2-3日 |
| 4 | 知識ベーススキーマの実装 | 2-3日 |
| 5 | Embedding処理の実装 | 2-3日 |
| 6 | Docker Compose の更新 | 1日 |
| 7 | テストと最適化 | 1-2日 |
| **合計** | | **10-15日** |

### Step 0: 依存関係の確認と設計レビュー (0.5日)

**目的**: 実装前に設計を最終確認し、依存関係を整理する

**実施内容**:

1. **依存関係の追加確認**:

   ```toml
   # pyproject.toml
   dependencies = [
       # ... 既存の依存関係 ...
       "asyncpg>=0.31.0",          # PostgreSQL非同期ドライバー
                                   # （必須: 0.29.0未満だと新しいPostgres機能や
                                   #  型変換でハマる可能性あり）
       "pgvector>=0.3.0",          # pgvector Pythonライブラリ（asyncpgへの型登録を簡素化）
       "asyncpg-stubs>=0.31.1",    # asyncpgの型スタブ（dev依存関係）
       "langchain-text-splitters>=1.1.0",  # テキスト分割ライブラリ
       "openai>=2.15.0",           # Embedding API用
       "pydantic-settings>=2.12.0", # 型安全な設定管理（必須）
       "tiktoken>=0.12.0",          # トークン数カウント用
       "tenacity>=9.1.2",           # リトライロジック用
       "structlog>=25.5.0",         # 構造化ログ（JSON形式、パフォーマンス向上）
       "prometheus-client>=0.24.1", # メトリクス収集（パフォーマンス監視）
       "orjson>=3.11.5",            # 高速JSON処理（JSONB操作の高速化）
       "alembic>=1.13.0",           # スキーママイグレーション管理（必須）
   ]
   ```

   **前提: pgvector Pythonライブラリの導入**:
   - `pgvector` Pythonライブラリは必須です（依存関係に含まれています）
   - `import pgvector.asyncpg; await pgvector.asyncpg.register_vector(conn)`
     とするだけで、SQL内で手動キャストやエンコード/デコードが
     不要になります
   - 実装箇所: `PostgreSQLDatabase.initialize()` メソッド（Step 2）

   **各パッケージの導入前提と実装での利用効果**:

   - **`langchain-text-splitters`**（必須）:
     - **導入前提**: テキスト分割アルゴリズムの実装に必須
     - **利用効果**:
       - `RecursiveCharacterTextSplitter` を使用して、句読点や改行を優先した意味を保持する分割が可能
       - 自前実装のメンテナンスコストを削減
       - チャンクサイズ、オーバーラップ、セパレータの優先順位などを柔軟に設定可能
     - 実装箇所: `SessionArchiver._split_content_by_tokens()` メソッド（Step 5.4）

   - **`pydantic-settings`**（必須）:
     - **導入前提**: 環境変数からの設定読み込みを型安全に行うために必須
     - **利用効果**:
       - 環境変数の型チェックとバリデーションが自動化される
       - IDEの型補完が効くため、設定値の誤りを早期発見
       - 設定クラスを定義することで、設定の一元管理が可能
       - **一箇所での管理**: `os.getenv`の呼び出しが分散しない
     - 実装箇所: **Step 0で`config.py`を実装し、すべての設定管理で使用**

   - **`asyncpg-stubs`**（必須）:
     - **導入前提**: asyncpgの型情報を提供するために必須（開発依存関係）
     - **利用効果**:
       - `mypy` や `pyright` などの型チェッカーで asyncpg の使用箇所を正確に検証可能
       - IDE（VSCode、PyCharm等）での型補完とエラー検出が向上
       - `asyncpg.Connection`、`asyncpg.Pool` などの型情報が利用可能
     - 実装箇所: `PostgreSQLDatabase` クラス全体（Step 2）で型安全性が向上

   - **`structlog`**（必須）:
     - **導入前提**: 構造化ログによるデバッグ性と運用監視の向上に必須
     - **利用効果**:
       - JSON形式の構造化ログにより、ログ解析ツール（ELK、Loki等）との連携が容易
       - コンテキスト情報（セッションID、ユーザーID、処理時間等）を自動的に付与可能
       - 標準の`logging`モジュールより高速（特に大量のログ出力時）
       - ログレベルの動的変更やフィルタリングが容易
     - 実装箇所: 全モジュールでログ出力を統一
       （`EmbeddingProcessor`、`SessionArchiver`、
       `PostgreSQLDatabase`等）
     - 実装時の便利な点:
       - `structlog.get_logger()`でロガーを取得し、
         `logger.info("message", key=value)`で構造化ログを出力
       - `structlog.configure()`で出力形式（JSON、コンソール等）を一元管理
       - バックグラウンドタスクの処理状況を構造化ログで追跡可能

   - **`prometheus-client`**（必須）:
     - **導入前提**: メトリクス収集によるパフォーマンス監視とリソース使用量の可視化に必須
     - **利用効果**:
       - `Counter`、`Histogram`、`Gauge`などのメトリクスタイプで、システムの状態を数値化
       - Embedding処理の処理時間、キュー長、エラー率などを追跡可能
       - データベース接続プールの使用状況、クエリ実行時間を監視可能
       - Prometheus + Grafanaによる可視化で、運用時の問題早期発見が可能
     - 実装箇所: `EmbeddingProcessor`（処理時間、キュー長）、
       `PostgreSQLDatabase`（接続プール使用率、クエリ時間）
     - 実装時の便利な点:
       - `from prometheus_client import Counter, Histogram, Gauge`でメトリクスを定義
       - `@Histogram.time()`デコレータで関数の実行時間を自動計測
       - バックグラウンドタスクのメトリクスを`/metrics`エンドポイントで公開可能（将来的にHTTPサーバー追加時）

   - **`orjson`**（必須）:
     - **導入前提**: 高速なJSON処理により、JSONB操作のパフォーマンス向上に必須
     - **利用効果**:
       - 標準の`json`モジュールより2-3倍高速（特に大量のJSON処理時）
       - JSONBコーデックのエンコーダー/デコーダーとして使用（高速なJSON処理）
       - `sessions.messages`（JSONB）の読み書き処理が高速化
       - `knowledge_sources.metadata`、`knowledge_chunks.location`（JSONB）の処理が高速化
     - 実装箇所: `PostgreSQLDatabase._init_connection()` でJSONBコーデックとして設定
     - 実装時の便利な点:
       - JSONBコーデックが設定されていれば、`dict`/`list`を直接渡せる（`orjson.dumps`不要）
       - 取得時も自動的に`dict`/`list`に変換される（`orjson.loads`不要）
       - 標準の`json`モジュールより2-3倍高速
       - ⚠️ **注意**: datetimeオブジェクトが含まれる場合は、
         事前にISO文字列に変換する必要がある
         （Pydanticの`model_dump(mode='json')`を使用）

   - **`alembic`**（必須）:
     - **導入前提**: スキーママイグレーション管理に必須（フェーズ8開始時から導入）
     - **利用効果**:
       - スキーマ変更の履歴管理が可能
       - 本番環境への安全なスキーマ適用が可能
       - ロールバック機能により、問題発生時の復旧が容易
       - チーム開発時のスキーマ同期が容易
     - 実装箇所: `PostgreSQLDatabase.initialize()` でマイグレーションを自動適用（Step 2）
     - 実装時の便利な点:
       - `alembic revision --autogenerate`でスキーマ変更を自動検出
       - `alembic upgrade head`で最新のマイグレーションを適用
       - `alembic downgrade -1`で前のバージョンにロールバック可能

2. **Alembicの初期化**（必須）:

   ```bash
   # Alembicの初期化（プロジェクトルートで実行）
   alembic init alembic
   ```

   **生成されるファイル**:
   - `alembic.ini`: Alembic設定ファイル
   - `alembic/`: マイグレーションスクリプトのディレクトリ
   - `alembic/env.py`: マイグレーション実行環境の設定

   **alembic.iniの設定**:

   ```ini
   # alembic.ini
   [alembic]
   script_location = alembic
   sqlalchemy.url = driver://user:pass@localhost/dbname
   # 注意: 実際の接続文字列は環境変数から読み込む（後述）

   [post_write_hooks]
   # オプション: マイグレーション適用後のフック
   ```

   **alembic/env.pyの設定**:

   ```python
   # alembic/env.py
   import os
   from logging.config import fileConfig
   from sqlalchemy import engine_from_config
   from sqlalchemy import pool
   from alembic import context
   
   # 環境変数から接続文字列を取得
   database_url = os.getenv("DATABASE_URL")
   if not database_url:
       raise ValueError("DATABASE_URL environment variable is required")
   
   config = context.config
   config.set_main_option("sqlalchemy.url", database_url)
   
   # ... その他の設定 ...
   ```

3. **初回マイグレーションの作成**:

   ```bash
   # 初回マイグレーション（スキーマ設計書のDDLをベースに作成）
   alembic revision --autogenerate -m "Initial schema"
   ```

   **注意**: `--autogenerate`は既存のテーブル構造を検出してマイグレーションを
   生成しますが、初回実装時は空のデータベースから開始するため、
   スキーマ設計書のDDLを直接マイグレーションスクリプトに記述する必要があります。

   **初回マイグレーションスクリプトの例**:

   ```python
   # alembic/versions/001_initial_schema.py
   """Initial schema

   Revision ID: 001_initial_schema
   Revises: 
   Create Date: 2026-01-19 10:00:00.000000
   """
   from alembic import op
   import sqlalchemy as sa
   from sqlalchemy.dialects import postgresql
   
   # revision identifiers, used by Alembic.
   revision = '001_initial_schema'
   down_revision = None
   branch_labels = None
   depends_on = None
   
   def upgrade():
       # 拡張機能の有効化
       op.execute("CREATE EXTENSION IF NOT EXISTS vector")
       
       # ENUM型の定義
       op.execute("""
           DO $$ BEGIN
               CREATE TYPE source_type_enum AS ENUM (
                   'discord_session',
                   'document_file',
                   'web_page',
                   'image_caption',
                   'audio_transcript'
               );
           EXCEPTION
               WHEN duplicate_object THEN null;
           END $$;
       """)
       
       # ... その他のテーブル定義 ...
       # （スキーマ設計書のDDLを参照）
   
   def downgrade():
       # テーブルの削除
       op.drop_table('knowledge_chunks')
       op.drop_table('knowledge_sources')
       op.drop_table('sessions')
       
       # ENUM型の削除
       op.execute("DROP TYPE IF EXISTS source_type_enum")
       op.execute("DROP TYPE IF EXISTS session_status_enum")
       op.execute("DROP TYPE IF EXISTS source_status_enum")
       
       # 拡張機能の削除
       op.execute("DROP EXTENSION IF EXISTS vector")
   ```

4. **`pydantic-settings`による環境変数の一元管理**（必須）:

   ⚠️ **改善（コード品質）**: 環境変数の `os.getenv` 呼び出しが分散している問題を改善
   `os.getenv()` がコード全体に散在しており、デフォルト値の重複や型変換のミスが発生しやすいため、
   Phase 8で `pydantic-settings` を**最初から使用**します。

   **実装例**:

   ```python
   # src/kotonoha_bot/config.py
   """アプリケーション設定（グローバルシングルトン）"""
   
   from pydantic_settings import BaseSettings, SettingsConfigDict
   
   class Settings(BaseSettings):
       """アプリケーション設定クラス
       
       すべての環境変数を一元管理します。
       型チェックとバリデーションが自動的に行われます。
       """
       model_config = SettingsConfigDict(
           env_file=".env",
           env_file_encoding="utf-8",
           case_sensitive=False,  # 環境変数名は大文字小文字を区別しない
           extra="ignore",  # 未定義の環境変数は無視
       )
       
       # ============================================
       # データベース設定
       # ============================================
       
       # 接続プール設定
       db_pool_min_size: int = 5
       db_pool_max_size: int = 20
       db_command_timeout: int = 60
       
       # PostgreSQL接続設定（本番環境推奨: パスワードを分離）
       postgres_host: str | None = None
       postgres_port: int = 5432
       postgres_db: str = "kotonoha"
       postgres_user: str = "kotonoha"
       postgres_password: str | None = None
       
       # 開発環境用（DATABASE_URL、後方互換性のため残す）
       database_url: str | None = None
       
       # ============================================
       # 知識ベース設定（PostgreSQL + pgvector）
       # ============================================
       
       # HNSWインデックスパラメータ
       kb_hnsw_m: int = 16
       kb_hnsw_ef_construction: int = 64
       
       # 検索設定
       kb_similarity_threshold: float = 0.7
       kb_default_top_k: int = 10
       
       # Embedding処理設定
       kb_embedding_max_retry: int = 3
       kb_embedding_batch_size: int = 100
       kb_embedding_max_concurrent: int = 5
       kb_embedding_interval_minutes: int = 1
       
       # チャンク登録・更新のバッチサイズ制御
       kb_chunk_insert_batch_size: int = 100
       kb_chunk_update_batch_size: int = 100
       
       # セッションアーカイブ設定
       kb_archive_threshold_hours: int = 1
       kb_archive_batch_size: int = 10
       kb_archive_interval_hours: int = 1
       kb_min_session_length: int = 30
       kb_archive_overlap_messages: int = 5
       
       # チャンク分割設定
       kb_chunk_max_tokens: int = 4000
       kb_chunk_overlap_ratio: float = 0.2
       
       # チャンク化戦略（message_based または token_based）
       kb_chat_chunk_strategy: str = "message_based"
       kb_chat_chunk_size_messages: int = 5
       kb_chat_chunk_overlap_messages: int = 2
       
       # ============================================
       # Discord設定
       # ============================================
       
       discord_token: str  # 必須（バリデーションエラーになる）
       
       # ============================================
       # OpenAI設定
       # ============================================
       
       openai_api_key: str  # 必須（バリデーションエラーになる）
       
       # ============================================
       # その他の設定（既存の設定）
       # ============================================
       
       # LLM設定
       llm_model: str = "anthropic/claude-opus-4-5"
       llm_temperature: float = 0.7
       llm_max_tokens: int = 2048
       
       # Bot設定
       bot_prefix: str = "!"
       
       # セッション管理設定
       session_timeout_hours: int = 72
       max_sessions: int = 100
       
       # ログ設定
       log_level: str = "INFO"
       log_file: str = "./logs/run.log"
       log_max_size: int = 10
       log_backup_count: int = 5
   
   # グローバルシングルトン（アプリケーション全体で使用）
   settings = Settings()
   ```

   **使用例**:

   ```python
   # ❌ 誤った実装（os.getenvの直接使用）
   import os
   max_size = int(os.getenv("DB_POOL_MAX_SIZE", "20"))  # 型変換が必要、デフォルト値が散在
   
   # ✅ 正しい実装（pydantic-settingsを使用）
   from ..config import settings
   max_size = settings.db_pool_max_size  # 型安全、IDE補完が効く
   ```

   **メリット**:

   - **型安全性**: 設定値の型が保証される（`int`, `float`, `str`など）
   - **バリデーション**: 不正な値の検出が自動化される（例: 負の値、範囲外の値）
   - **IDE補完**: 設定値へのアクセス時に補完が効く
   - **ドキュメント化**: 設定クラスが自動的にドキュメントになる
   - **一箇所での管理**: `os.getenv`の呼び出しが分散しない
   - **デフォルト値の一元管理**: デフォルト値が`Settings`クラスに集約される

   **注意事項**:

   - 環境変数名は大文字小文字を区別しない（`DB_POOL_MAX_SIZE`と`db_pool_max_size`は同じ）
   - 必須項目（`discord_token`, `openai_api_key`）が設定されていない場合は起動時にエラーになる
   - `.env`ファイルが存在する場合は自動的に読み込まれる
   - 本番環境では環境変数を直接設定するか、シークレットマネージャーを使用

5. **設計レビュー**:
   - Source-Chunk構造の妥当性確認
   - 非同期処理パターンの確認
   - スキーマ設計の最終確認
   - Alembicマイグレーションスクリプトの確認
   - `pydantic-settings`による設定管理の確認
   - `constants.py`による定数管理の確認
   - `constants.py`による定数管理の確認

**完了基準**:

- [ ] 依存関係が追加されている（`langchain-text-splitters`, `pydantic-settings`,
  `asyncpg-stubs`, `structlog`, `prometheus-client`, `orjson`, `alembic` を含む）
- [ ] 各パッケージの導入前提と利用効果を理解している
- [ ] ⚠️ **重要**: `src/kotonoha_bot/config.py`に`Settings`クラスが実装されている
  - すべての環境変数が`Settings`クラスで一元管理されている
  - `os.getenv`の直接使用が排除されている
  - 型安全性とバリデーションが実装されている
- [ ] ⚠️ **重要**: `src/kotonoha_bot/constants.py`にすべての定数が定義されている
  - データベース関連の定数（`DatabaseConstants`）
  - 検索関連の定数（`SearchConstants`）
  - バッチ処理関連の定数（`BatchConstants`）
  - Embedding処理関連の定数（`EmbeddingConstants`）
  - アーカイブ処理関連の定数（`ArchiveConstants`）
  - エラーコード定数（`ErrorConstants`）
  - SQL内のマジックナンバーが定数に置き換えられている
  - タイムアウト値、LIMIT値、バッチサイズなどが定数化されている
- [ ] Alembicが初期化されている（`alembic init alembic`）
- [ ] `alembic.ini`と`alembic/env.py`が適切に設定されている
- [ ] 初回マイグレーションスクリプトが作成されている（`001_initial_schema`）
- [ ] 設計レビューが完了している
- [ ] 実装方針が明確になっている

### Step 1: データベース抽象化レイヤーの実装 (2-3日)

**目的**: PostgreSQL実装のための抽象化レイヤーを定義し、将来の拡張性を確保する

**実施内容**:

#### 1.1 DatabaseProtocol インターフェースの定義

```python
# src/kotonoha_bot/db/base.py
"""データベース抽象化レイヤー"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..session.models import ChatSession

class DatabaseProtocol(ABC):
    """セッション管理のみを抽象化するプロトコル（インターフェース）
    
    ⚠️ 改善（抽象化の粒度）: セッション管理と知識ベース管理を分離することで、
    抽象化の粒度を均一にし、単一責任の原則に従います。
    
    知識ベース関連のメソッドは `KnowledgeBaseProtocol` に分離されています。
    """
    
    @abstractmethod
    async def initialize(self) -> None:
        """データベースの初期化"""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """データベース接続のクローズ"""
        pass
    
    @abstractmethod
    async def save_session(self, session: "ChatSession") -> None:
        """セッションを保存"""
        pass
    
    @abstractmethod
    async def load_session(self, session_key: str) -> "ChatSession" | None:
        """セッションを読み込み"""
        pass
    
    @abstractmethod
    async def delete_session(self, session_key: str) -> None:
        """セッションを削除"""
        pass
    
    @abstractmethod
    async def load_all_sessions(self) -> list["ChatSession"]:
        """すべてのセッションを読み込み"""
        pass


class KnowledgeBaseProtocol(ABC):
    """知識ベースを別プロトコルとして分離
    
    ⚠️ 改善（抽象化の粒度）: 知識ベース関連のメソッドを `DatabaseProtocol` から分離することで、
    抽象化の粒度を均一にし、単一責任の原則に従います。
    
    セッション管理は `DatabaseProtocol` に、知識ベース管理は `KnowledgeBaseProtocol` に分離されています。
    """
    
    @abstractmethod
    async def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[SearchResult]:
        """類似度検索を実行"""
        pass
    
    @abstractmethod
    async def save_source(
        self,
        source_type: str,
        title: str,
        uri: str | None,
        metadata: dict,
        status: str = "pending",
    ) -> int:
        """知識ソースを保存し、IDを返す"""
        pass
    
    @abstractmethod
    async def save_chunk(
        self,
        source_id: int,
        content: str,
        location: dict | None = None,
        token_count: int | None = None,
    ) -> int:
        """知識チャンクを保存し、IDを返す"""
        pass
```

#### 1.2 既存コードの更新準備

`main.py` や `handlers.py` で、データベースインスタンスの作成方法を確認し、PostgreSQL実装に置き換える準備をします。

**注意**: このフェーズでは、最初からPostgreSQLを使用するため、SQLiteからの移行や切り替え機能は実装しません。

**完了基準**:

- [ ] `DatabaseProtocol` インターフェースが定義されている
- [ ] 既存コードでデータベースを使用している箇所を特定している
- [ ] PostgreSQL実装に置き換える準備が整っている

### Step 2: PostgreSQL 実装の追加 (3-4日)

#### 2.1 PostgreSQLDatabase クラスの実装

```python
# src/kotonoha_bot/db/postgres.py
"""PostgreSQL データベース実装"""

import os
import asyncpg
import orjson
import structlog
from typing import TYPE_CHECKING
from pathlib import Path

from .base import DatabaseProtocol

if TYPE_CHECKING:
    from ..session.models import ChatSession

logger = structlog.get_logger(__name__)

# 注意: asyncpg-stubs がインストールされている場合、
# asyncpg.Connection, asyncpg.Pool などの型情報が利用可能になり、
# IDEの型補完と型チェッカー（mypy, pyright）の精度が向上します。

class PostgreSQLDatabase(DatabaseProtocol, KnowledgeBaseProtocol):
    """PostgreSQL データベース（非同期）
    
    ⚠️ 改善（抽象化の粒度）: `DatabaseProtocol` と `KnowledgeBaseProtocol` の両方を実装することで、
    セッション管理と知識ベース管理を分離し、抽象化の粒度を均一にします。
    """
    
    # ⚠️ 改善（コード品質）: マジックナンバーを定数化
    # クラス定数としてデフォルト値を定義（後方互換性のため残す）
    # 推奨: `constants.py`の定数を使用
    DEFAULT_POOL_MIN_SIZE = 5
    DEFAULT_POOL_MAX_SIZE = 20
    DEFAULT_COMMAND_TIMEOUT = 60
    
    def __init__(
        self,
        connection_string: str | None = None,
        host: str | None = None,
        port: int | None = None,
        database: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ):
        """PostgreSQL データベースの初期化
        
        ⚠️ 改善（セキュリティ）: DATABASE_URL にパスワードを含める形式への依存を改善
        asyncpg はパスワードを別パラメータで渡せるため、接続文字列にパスワードを埋め込む必要はありません。
        
        Args:
            connection_string: 接続文字列（開発環境用、後方互換性のため残す）
            host: PostgreSQL ホスト（本番環境推奨）
            port: PostgreSQL ポート（デフォルト: 5432）
            database: データベース名
            user: ユーザー名
            password: パスワード（分離して管理）
        """
        # ⚠️ 改善（セキュリティ）: 個別パラメータが指定されている場合は、それを使用
        # 接続文字列にパスワードを含める形式への依存を避ける
        if host and database and user and password:
            self.connection_string = None
            self.host = host
            self.port = port or 5432
            self.database = database
            self.user = user
            self.password = password
        elif connection_string:
            # 後方互換性のため、接続文字列もサポート（開発環境用）
            self.connection_string = connection_string
            self.host = None
            self.port = None
            self.database = None
            self.user = None
            self.password = None
        else:
            raise ValueError(
                "Either connection_string or "
                "(host, database, user, password) must be provided"
            )
        self.pool: asyncpg.Pool | None = None
    
    async def _init_connection(self, conn: asyncpg.Connection) -> None:
        """プールの各コネクション初期化時に呼ばれる
        
        ⚠️ 重要: asyncpg.create_pool() の init パラメータには単一の関数しか渡せません。
        pgvectorの型登録とJSONBコーデックの登録を両方行う場合は、このラッパー関数内で
        両方を実行する必要があります。
        """
        # 1. pgvectorの型登録
        from pgvector.asyncpg import register_vector
        await register_vector(conn)
        
        # 2. JSONBコーデックの登録（orjsonを使用）
        import orjson
        from datetime import datetime
        
        # ⚠️ 改善（堅牢性）: orjson.dumps は標準では datetime オブジェクトをシリアライズできません
        # Pydanticの .model_dump(mode='json') を通す前提であれば文字列化されているので問題ありませんが、
        # 生の dict に datetime オブジェクトが含まれているとエラーになります。
        # 対策: default オプションで datetime を ISO 文字列に変換する関数を指定
        def default(obj):
            """orjson の default オプション用の関数"""
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(
                f"Object of type {type(obj)} is not JSON serializable"
            )
        
        await conn.set_type_codec(
            'jsonb',
            encoder=lambda v: orjson.dumps(
                v, default=default
            ).decode('utf-8'),
            decoder=lambda b: orjson.loads(
                b.encode('utf-8') if isinstance(b, str) else b
            ),
            schema='pg_catalog',
            format='text'
        )
        # ⚠️ 注意: 計画書通り「Pydanticで事前にJSON化する」ルールを徹底するなら、
        # default オプションなしでも動作しますが、防御的プログラミングとして追加しています。
    
    async def initialize(self) -> None:
        """データベースの初期化
        
        ⚠️ 接続プールの分離検討:
        バックグラウンドタスク（Embedding, Archive）用の asyncpg.Pool と、
        Web/Bot応答用のプールを分ける選択肢もありますが、現状はセマフォによる
        動的制限で対応します。大規模運用時はプール分離を検討してください。
        """
        # ⚠️ 改善（コード品質）: pydantic-settings を使用
        from ..config import settings
        min_size = settings.db_pool_min_size
        max_size = settings.db_pool_max_size
        command_timeout = settings.db_command_timeout
        
        # ⚠️ 重要: init パラメータを使用して、プールから取得される各コネクションに対して
        # pgvector の型登録を自動的に行います。
        # これにより、プールのすべてのコネクションで pgvector が使用可能になります。
        # 
        # ⚠️ 接続プール分離の検討:
        # 大規模運用時は、バックグラウンドタスク用とWeb/Bot応答用のプールを分けることを検討
        # 現状はセマフォによる動的制限（DB_POOL_MAX_SIZEの20〜30%程度）で対応
        # 
        # ⚠️ 改善（セキュリティ）: asyncpg はパスワードを別パラメータで渡せるため、
        # 接続文字列にパスワードを含める形式への依存を避けます。
        if self.connection_string:
            # 後方互換性のため、接続文字列もサポート（開発環境用）
            self.pool = await asyncpg.create_pool(
                self.connection_string,
                init=self._init_connection,  # ← これが重要！
                min_size=min_size,
                max_size=max_size,
                command_timeout=command_timeout,
            )
        else:
            # ⚠️ 改善（セキュリティ）: 個別パラメータを使用（本番環境推奨）
            # パスワードを接続文字列に埋め込まない
            self.pool = await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,  # 分離して管理
                init=self._init_connection,  # ← これが重要！
                min_size=min_size,
                max_size=max_size,
                command_timeout=command_timeout,
            )
        
        # ⚠️ 重要: Alembicマイグレーションの自動適用
        # スキーマ変更は必ずAlembicマイグレーションで管理します。
        # 初回起動時やスキーマ変更時に自動的に最新のマイグレーションを適用します。
        from alembic.config import Config
        from alembic import command
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory
        
        # Alembic設定の読み込み
        alembic_cfg = Config("alembic.ini")
        
        # 接続文字列を設定（環境変数から取得）
        if self.connection_string:
            # asyncpgの接続文字列をSQLAlchemy形式に変換
            # postgresql://user:pass@host:port/db ->
            # postgresql+asyncpg://user:pass@host:port/db
            sqlalchemy_url = self.connection_string.replace(
                "postgresql://", "postgresql+asyncpg://"
            )
        else:
            # 個別パラメータから接続文字列を構築
            sqlalchemy_url = (
                f"postgresql+asyncpg://{self.user}:{self.password}@"
                f"{self.host}:{self.port}/{self.database}"
            )
        alembic_cfg.set_main_option("sqlalchemy.url", sqlalchemy_url)
        
        # マイグレーションの適用
        try:
            logger.info("Applying Alembic migrations...")
            command.upgrade(alembic_cfg, "head")
            logger.info("Alembic migrations applied successfully")
        except Exception as e:
            logger.error(
                f"Failed to apply Alembic migrations: {e}", exc_info=True
            )
            raise RuntimeError(f"Database migration failed: {e}") from e
        
        # pgvector 拡張を有効化とバージョン確認（1つのコネクションで実行）
        async with self.pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            
            # ⚠️ 推奨: pg_bigm 拡張を有効化（ハイブリッド検索の準備）
            # Phase 8.5 でハイブリッド検索を実装する予定のため、ここで拡張を有効化します。
            # pg_bigm は日本語検索において pg_trgm よりも精度が高い（2-gramによる）
            # 固有名詞（エラーコード、変数名など）の検索精度向上に効果的です。
            # 
            # ⚠️ 重要: フェーズ8では開発環境・本番環境ともにpg_bigmを含むカスタムイメージを使用します。
            # Dockerfile.postgresでpg_bigmをビルドしたカスタムイメージを
            # docker-compose.ymlで使用してください。
            try:
                await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_bigm")
                logger.info("pg_bigm extension enabled for hybrid search")
            except Exception as e:
                # pg_bigm が利用できない環境でも動作するように
                logger.warning(f"pg_bigm extension could not be enabled: {e}. "
                             f"Hybrid search will not be available.")

        # pgvector のバージョン確認（HNSWは0.5.0以降で使用可能、推奨は0.8.1）
        version_row = await conn.fetchrow(
            "SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        if version_row:
            version_str = version_row['extversion']
            version_parts = version_str.split('.')
            major = int(version_parts[0])
            minor = int(version_parts[1]) if len(version_parts) > 1 else 0

            if major < 0 or (major == 0 and minor < 5):
                raise RuntimeError(
                    f"pgvector version {version_str} is too old. "
                    "HNSW index requires pgvector 0.5.0 or later. "
                    "Please upgrade pgvector."
                )
            logger.info(
                f"pgvector version {version_str} is compatible "
                f"(HNSW supported, recommended: 0.8.1 for PostgreSQL 18)")
        else:
            logger.warning(
                "pgvector extension version could not be determined")

        # ⚠️ 重要: Alembicマイグレーションでテーブルを作成するため、
        # _create_tables メソッドは呼び出しません。
        # テーブル作成は初回マイグレーション（001_initial_schema）で行います。
        # 
        # 注意: 開発環境での手動実行やテスト時の便利さを考慮して、
        # _create_tables メソッドは残しておきますが、通常の運用では使用しません。
        # await self._create_tables(conn)
    
    async def _create_tables(self, conn: asyncpg.Connection) -> None:
        """テーブルを作成"""
        # ENUM型の作成（順序をDDL定義と統一）
        await conn.execute("""
            DO $$ BEGIN
                CREATE TYPE source_type_enum AS ENUM (
                    'discord_session',
                    'document_file',
                    'web_page',
                    'image_caption',
                    'audio_transcript'
                );
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """)
        
        # ⚠️ 重要: セッションとソースで異なるENUM型を使用
        # これにより、DBレベルで意味論的に正しい値のみが許可される
        # 
        # ⚠️ 注意: ENUM型を使用している場合、CHECK制約は冗長かつ危険です。
        # - ENUM型を拡張した際にCHECK制約の更新を忘れるとINSERT/UPDATEが失敗する
        # - 二重管理によるメンテナンスバグの温床となる
        # 推奨: CHECK制約は使用せず、ENUM型のみで制御する
        await conn.execute("""
            DO $$ BEGIN
                CREATE TYPE session_status_enum AS ENUM (
                    'active',    -- 会話中
                    'archived'   -- 知識化済み・アーカイブ
                );
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """)
        
        await conn.execute("""
            DO $$ BEGIN
                CREATE TYPE source_status_enum AS ENUM (
                    'pending',      -- 処理待ち
                    'processing',   -- ベクトル化やOCR処理中
                    'completed',    -- 検索可能（すべてのチャンクが正常に処理された）
                    'partial',  -- ⚠️ 改善（データ整合性）: 一部のチャンクがDLQに移動
                    -- （検索可能だが不完全）
                    'failed'        -- エラー
                );
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """)
        
        # 短期記憶: sessions テーブル
        # ⚠️ 改善: id BIGSERIAL PRIMARY KEY を追加し、session_key は UNIQUE NOT NULL に変更
        # 理由: 「新規設計で移行ツールを作らない」という前提であれば、最初から最適解を選ぶべき
        # - TEXT型の主キーはインデックスサイズが肥大化し、将来的に外部キー参照を行う際に
        #   パフォーマンス（JOIN速度）とストレージ効率が悪化する
        # - アプリケーション内部での参照は session_key を使いつつ、
        #   将来的なリレーション（例：session_tags テーブルなど）は id を使う余地を残す
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id BIGSERIAL PRIMARY KEY,
                session_key TEXT UNIQUE NOT NULL,  -- アプリケーション内部での参照用
                session_type TEXT NOT NULL,
                messages JSONB DEFAULT '[]'::jsonb NOT NULL,
                status session_status_enum DEFAULT 'active',  -- session_status_enumを使用
                guild_id BIGINT,        -- Discord Guild ID（Discord URL生成に必要）
                channel_id BIGINT,
                thread_id BIGINT,
                user_id BIGINT,
                version INT DEFAULT 1,  -- ⚠️ 追加: 楽観的ロック用（更新ごとにインクリメント）
                last_archived_message_index INT DEFAULT 0,
                -- ⚠️ 改善: アーカイブ済みメッセージのインデックス（0=未アーカイブ）
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                last_active_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # 知識ベーステーブル
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_sources (
                id BIGSERIAL PRIMARY KEY,
                type source_type_enum NOT NULL,
                title TEXT NOT NULL,
                uri TEXT,
                metadata JSONB DEFAULT '{}'::jsonb,
                status source_status_enum DEFAULT 'pending',  -- source_status_enumを使用
                error_code TEXT,  -- ⚠️ 改善（セキュリティ）: エラーコード
                -- （例: 'EMBEDDING_API_TIMEOUT', 'RATE_LIMIT'）
                error_message TEXT,  -- ⚠️ 改善（セキュリティ）: 一般化されたメッセージのみ
                -- （詳細なスタックトレースはログのみに出力）
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # ⚠️ 重要: halfvec(1536) を固定採用（メモリ使用量50%削減）
        # pgvector 0.7.0以降で halfvec を使用します。
        # ⚠️ 重要: embedding は NULL許容です
        # Embedding生成前のデータをINSERTし、後でUPDATEするフローを採用
        # 理由: トランザクション分離のため（FOR UPDATE SKIP LOCKED + Tx分離パターン）
        # 検索時は必ず embedding IS NOT NULL 条件を含めること（HNSWインデックス使用のため）
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS knowledge_chunks (
                id BIGSERIAL PRIMARY KEY,
                source_id BIGINT NOT NULL REFERENCES knowledge_sources(id)
                    ON DELETE CASCADE,
                content TEXT NOT NULL,
                embedding halfvec(1536),  -- ⚠️ NULL許容: Embedding生成前のデータをINSERT可能
                location JSONB DEFAULT '{}'::jsonb,
                token_count INT,
                retry_count INT DEFAULT 0,  -- ⚠️ 追加: Dead Letter Queue対応
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # ⚠️ 改善（データ整合性）: Dead Letter Queueテーブル
        # retry_countが上限に達したチャンクを保存し、手動での確認・再処理を可能にする
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_chunks_dlq (
                id BIGSERIAL PRIMARY KEY,
                original_chunk_id BIGINT,
                source_id BIGINT,  -- ⚠️ 改善: 元のソースID
                -- （外部キー制約なし、ソース削除後も追跡可能）
                source_type source_type_enum,  -- ⚠️ 改善: ソースタイプも保存
                -- （トレーサビリティ向上）
                source_title TEXT,  -- ⚠️ 改善: デバッグ用にソースのタイトルも保存
                content TEXT NOT NULL,
                error_code TEXT,  -- ⚠️ 改善: エラーコードを分離して保存
                -- （例: 'EMBEDDING_API_TIMEOUT', 'RATE_LIMIT'）
                error_message TEXT,         -- 一般化されたエラーメッセージ
                retry_count INT DEFAULT 0,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                last_retry_at TIMESTAMPTZ
            );
        """)
        
        # インデックスの作成
        await self._create_indexes(conn)
    
    async def _create_indexes(self, conn: asyncpg.Connection) -> None:
        """インデックスを作成"""
        # ⚠️ 注意: sessions.session_key は UNIQUE 制約が付いているため、
        # 自動的にユニークインデックスが作成されます。
        # 明示的なインデックス作成は不要（冗長なインデックス作成を避ける）
        
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_status 
            ON sessions(status);
        """)
        
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_last_active_at 
            ON sessions(last_active_at);
        """)
        
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_channel_id 
            ON sessions(channel_id);
        """)
        
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_archive_candidates 
            ON sessions(status, last_active_at)
            WHERE status = 'active';
        """)
        
        # 知識ベーステーブルのインデックス
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sources_metadata 
            ON knowledge_sources USING gin (metadata);
        """)
        
        # ⚠️ 重要: halfvec固定採用のため、halfvec_cosine_ops を使用
        ops_type = "halfvec_cosine_ops"
        
        # ⚠️ 重要: HNSWパラメータのバリデーション（SQLインジェクション対策）
        # pgvectorの推奨範囲内であることを確認
        # ⚠️ 改善（コード品質）: settings のインポートを明示
        from ..config import settings
        
        VALID_HNSW_M_RANGE = range(4, 65)  # pgvectorの推奨範囲
        VALID_HNSW_EF_RANGE = range(16, 513)
        
        m = settings.kb_hnsw_m
        ef_construction = settings.kb_hnsw_ef_construction
        
        if m not in VALID_HNSW_M_RANGE:
            raise ValueError(f"KB_HNSW_M must be between 4 and 64, got {m}")
        if ef_construction not in VALID_HNSW_EF_RANGE:
            raise ValueError(
                f"KB_HNSW_EF_CONSTRUCTION must be between 16 and 512, "
                f"got {ef_construction}")
        
        # ⚠️ 運用上の注意: HNSWインデックスのメモリ消費
        # 初期は問題ありませんが、データが10万件を超えたあたりで監視が必要です
        # pg_stat_activity やコンテナのメモリ使用量を監視し、
        # PostgreSQLの設定（postgresql.conf）チューニングが必要になる可能性があります
        # 特に maintenance_work_mem や work_mem の調整を検討してください
        # halfvec で容量は減りますが、HNSWは高速化のためにグラフ構造をメモリに乗せようとします
        
        # バリデーション後に文字列補間（DDLではパラメータ化クエリが使えないため）
        await conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_chunks_embedding 
            ON knowledge_chunks USING hnsw (embedding {ops_type})
            WITH (m = {m}, ef_construction = {ef_construction});
        """)
        
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_chunks_source_id 
            ON knowledge_chunks(source_id);
        """)
        
        # ⚠️ 改善（パフォーマンス）: 処理待ち行列専用の部分インデックス
        # FOR UPDATE SKIP LOCKED を使うクエリは WHERE embedding IS NULL を参照します。
        # knowledge_chunks が数百万件になった際、embedding IS NULL の行を探すのに
        # 時間がかかるとバッチ処理が遅延します。
        # 処理待ち行列専用の部分インデックスを作成することで、ワーカーはテーブル全体を
        # スキャンせず、インデックスのみを見て処理対象を即座に見つけられます。
        MAX_RETRY_COUNT = int(os.getenv("KB_EMBEDDING_MAX_RETRY", "3"))
        await conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_chunks_queue 
            ON knowledge_chunks(id)
            WHERE embedding IS NULL AND retry_count < {MAX_RETRY_COUNT};
        """)
        
        # ⚠️ 推奨: pg_bigm 拡張を有効化してハイブリッド検索の準備
        # ベクトル検索のみでは「固有名詞（エラーコード、変数名など）」の検索に弱いため、
        # 日本語の全文検索や部分一致において、ベクトル検索を補完する効果が絶大です。
        # pg_bigm は日本語検索において pg_trgm よりも精度が高い（2-gramによる）
        # Phase 8.5 でハイブリッド検索を実装する予定のため、ここでインデックスを準備します。
        # 
        # ⚠️ 重要: フェーズ8では開発環境・本番環境ともにpg_bigmを含むカスタムイメージを使用します。
        # Dockerfile.postgresでpg_bigmをビルドしたカスタムイメージをdocker-compose.ymlで使用してください。
        try:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_bigm")
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_chunks_content_bigm 
                ON knowledge_chunks USING gin (content gin_bigm_ops);
            """)
            logger.info(
                "pg_bigm extension enabled and index created for hybrid search")
        except Exception as e:
            # pg_bigm が利用できない環境でも動作するように
            logger.warning(f"pg_bigm extension could not be enabled: {e}. "
                         f"Hybrid search will not be available.")
    
    async def close(self) -> None:
        """データベース接続のクローズ"""
        if self.pool:
            await self.pool.close()
    
    # セッション管理メソッドの実装...
    # similarity_search メソッドの実装...
```

#### 2.2 ChatSession モデルの変更

**重要**: PostgreSQL実装では、`ChatSession` モデルに以下のフィールドを追加する必要があります：

```python
# src/kotonoha_bot/session/models.py（既存のChatSessionモデルに追加）
@dataclass
class ChatSession:
    session_key: str
    session_type: str
    messages: list[Message]
    status: str = "active"  # 追加: セッションの状態（'active', 'archived'など）
    guild_id: int | None = None  # 追加: Discord Guild ID
    channel_id: int | None = None
    thread_id: int | None = None
    user_id: int | None = None
    version: int = 1  # ⚠️ 追加: 楽観的ロック用（更新ごとにインクリメント）
    last_archived_message_index: int = 0
    # ⚠️ 改善: アーカイブ済みメッセージのインデックス（0=未アーカイブ）
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_active_at: datetime = field(default_factory=datetime.utcnow)
```

**変更理由**:

- `status`: セッションの状態管理（'active', 'archived'など）に必要
- `guild_id`: Discord URL生成（`/channels/{guild_id}/{channel_id}`）に必要
- `version`: 楽観的ロック用（更新ごとにインクリメント）。
  TIMESTAMPTZの精度（マイクロ秒）で競合検出に依存するのではなく、
  versionカラムを使用する方が堅牢
- `last_archived_message_index`: アーカイブ済みメッセージのインデックス
  （0=未アーカイブ）。高頻度でチャットが続く場合でも、
  確定した過去部分だけをアーカイブでき、リトライループに陥ることを防ぐ

#### 2.3 セッション管理メソッドの実装

```python
    async def save_session(self, session: "ChatSession") -> None:
        """セッションを保存（トランザクション付き）

        ⚠️ 重要: guild_id は Discord URL生成に必要です。
        handlers.py で明示的に取得・保存されていることを確認してください。
        DMの場合、guild_id は None になります。

        ⚠️ 注意: このメソッドは楽観的ロックを適用していません。
        通常のセッション更新（メッセージ追加など）では競合が稀なため、シンプルなUPSERTを使用します。
        楽観的ロックが必要な場合は `save_session_with_optimistic_lock` を使用してください。
        """
        async with self.pool.acquire() as conn:
            async with conn.transaction():  # トランザクションでラップ
                # ⚠️ 重要: guild_id の取得確認
                # Discord.pyのメッセージイベントから guild_id を取得していることを確認
                # guild_id = message.guild.id if message.guild else None
                await conn.execute("""
                    INSERT INTO sessions
                    (session_key, session_type, messages, status, guild_id,
                     channel_id, thread_id, user_id, created_at, last_active_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT (session_key)
                    DO UPDATE SET
                        messages = EXCLUDED.messages,
                        last_active_at = EXCLUDED.last_active_at,
                        status = COALESCE(EXCLUDED.status, sessions.status),
                        guild_id = COALESCE(
                            EXCLUDED.guild_id, sessions.guild_id
                        ),
                        version = sessions.version + 1,
                        -- ⚠️ 注意: last_archived_message_index は更新しない
                """,
                    session.session_key,
                    session.session_type,
                    # ⚠️ 重要: model_dump(mode='json')でdatetimeがISO文字列化される
                    # JSONBコーデックが設定されていれば、dictを直接渡せる
                    [msg.model_dump(mode='json') for msg in session.messages],
                    getattr(session, 'status', 'active'),  # デフォルトは 'active'
                    getattr(session, 'guild_id', None),  # guild_idを追加
                    session.channel_id,
                    getattr(session, 'thread_id', None),
                    session.user_id,
                    session.created_at,
                    session.last_active_at,
                    getattr(session, 'version', 1),  # versionカラム
                )

    async def save_session_with_optimistic_lock(
        self, session: "ChatSession", expected_version: int
    ) -> bool:
        """楽観的ロック付きセッション保存

        ⚠️ 改善（データ整合性）: save_session での UPSERT ロジックの改善
        - ON CONFLICT で status を COALESCE する場合、EXCLUDED.status が None の場合の挙動が不明確
        - version のインクリメントと楽観的ロックの整合性が取れていない（save時に前のversionを確認していない）

        このメソッドは、楽観的ロックを適用してセッションを保存します。
        アーカイブ処理など、競合が発生する可能性がある場合に使用してください。

        Args:
            session: 保存するセッション
            expected_version: 期待するバージョン番号（楽観的ロック用）

        Returns:
            bool: 更新が成功した場合 True、競合が発生した場合 False
        """
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # ⚠️ 改善: 楽観的ロックを適用するなら、WHERE句でversion確認が必要
                result = await conn.execute("""
                    UPDATE sessions SET
                        messages = $2,
                        last_active_at = $3,
                        version = version + 1
                    WHERE session_key = $1 AND version = $4
                """,
                    session.session_key,
                    [msg.model_dump(mode='json') for msg in session.messages],
                    session.last_active_at,
                    expected_version
                )

                # result は "UPDATE 1" のような文字列を返す
                # 成功した場合は "UPDATE 1"、競合した場合は "UPDATE 0"
                return result == "UPDATE 1"

    async def load_session(self, session_key: str) -> "ChatSession" | None:
        """セッションを読み込み"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM sessions WHERE session_key = $1
            """, session_key)

            if not row:
                return None

            # ChatSession オブジェクトに変換
            from ..session.models import ChatSession, MessageRole

            messages = [
                {
                    "role": MessageRole(msg["role"]),
                    "content": msg["content"],
                    "timestamp": msg.get("timestamp"),
                }
                # ⚠️ 注意: JSONBコーデックが設定されていれば、自動的にdictに変換される
                for msg in row["messages"]
            ]

            return ChatSession(
                session_key=row["session_key"],
                session_type=row["session_type"],
                messages=messages,
                status=row.get("status", "active"),
                guild_id=row.get("guild_id"),  # guild_idを追加
                channel_id=row["channel_id"],
                thread_id=row.get("thread_id"),
                user_id=row["user_id"],
                created_at=row["created_at"],
                last_active_at=row["last_active_at"],
                version=row.get("version", 1),  # versionカラム（デフォルト: 1）
                last_archived_message_index=row.get(
                    "last_archived_message_index", 0
                ),  # アーカイブ済みメッセージのインデックス（デフォルト: 0）
            )
```

**完了基準**:

- [ ] `PostgreSQLDatabase` クラスが実装されている
- [ ] `PostgreSQLDatabase` が `DatabaseProtocol` と
  `KnowledgeBaseProtocol` の両方に適合している
- [ ] ⚠️ **改善（抽象化の粒度）**: セッション管理と知識ベース管理が分離されている
  - `DatabaseProtocol` のメソッド（`save_session`, `load_session` 等）が実装されている
  - `KnowledgeBaseProtocol` のメソッド
    （`similarity_search`, `save_source`, `save_chunk` 等）が実装されている
- [ ] pgvector 拡張が有効化されている
- [ ] テーブルとインデックスが作成される
- [ ] セッション管理メソッドが動作する
- [ ] 既存のセッション管理機能が PostgreSQL で動作する

### Step 3: ベクトル検索機能の実装 (2-3日)

#### 3.1 similarity_search メソッドの実装

```python
# src/kotonoha_bot/db/postgres.py（追加）

# ENUM値のバリデーション（SQLインジェクション対策）
# 注意: DDL定義と順序を統一
# ('discord_session', 'document_file', 'web_page', 'image_caption', 'audio_transcript')
VALID_SOURCE_TYPES = {
    'discord_session',
    'document_file',
    'web_page',
    'image_caption',
    'audio_transcript'
}

# フィルタキーのAllow-list（SQLインジェクション対策）
# 外部入力がキー名に使われる可能性があるため、許可されたキーのみを処理
ALLOWED_FILTER_KEYS = {
    'source_type',   # VALID_SOURCE_TYPES でバリデーション済み（単一指定）
    'source_types',  # VALID_SOURCE_TYPES でバリデーション済み（複数指定、IN句使用）
    'channel_id',    # BIGINT型
    'user_id',       # BIGINT型
}

# ⚠️ 改善（コード品質）: 型アノテーションの不一致を改善
# 戻り値にTypedDictまたはdataclassを定義することで、型安全性を向上
from typing import TypedDict

class SearchResult(TypedDict):
    """検索結果の型定義"""
    chunk_id: int
    source_id: int
    content: str
    similarity: float
    source_type: str
    title: str
    uri: str | None
    source_metadata: dict | None


class PostgreSQLDatabase:
    # ... (省略: 他のメソッド)

    async def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[SearchResult]:
        """類似度検索を実行

        ⚠️ 改善（コード品質）: 戻り値の型を明確化
        list[dict] は曖昧なため、SearchResult TypedDictを使用して型安全性を向上

        Args:
            query_embedding: クエリのベクトル（1536次元）
            top_k: 取得する結果の数
            filters: フィルタ条件
                （例: {"source_type": "discord_session", "channel_id": 123}）

        Returns:
            検索結果のリスト（各要素は dict で、content, similarity, source情報を含む）

        Raises:
            ValueError: 無効なsource_typeが指定された場合
        """
        from ..constants import DatabaseConstants

        # ⚠️ 重要: halfvec固定採用（constants.pyの定数を使用）
        from ..constants import SearchConstants
        vector_cast = SearchConstants.VECTOR_CAST
        vector_dimension = SearchConstants.VECTOR_DIMENSION

        # 接続プール枯渇時のタイムアウト処理
        try:
            from asyncio import timeout

            # ⚠️ 改善（コード品質）: マジックナンバーを定数化
            async with timeout(DatabaseConstants.POOL_ACQUIRE_TIMEOUT):
                async with self.pool.acquire() as conn:
                    # ベースクエリ
                    # ⚠️ 重要: WHERE c.embedding IS NOT NULL 条件は必須です
                    query = f"""
                        SELECT
                            s.id as source_id,
                            s.type,
                            s.title,
                            s.uri,
                            s.metadata as source_metadata,
                            c.id as chunk_id,
                            c.content,
                            c.location,
                            c.token_count,
                            1 - (c.embedding <=> $1::{vector_cast}) as similarity
                        FROM knowledge_chunks c
                        JOIN knowledge_sources s ON c.source_id = s.id
                        WHERE c.embedding IS NOT NULL
                    """

                    # ⚠️ 改善（コード品質）: pydantic-settings を使用
                    similarity_threshold = settings.kb_similarity_threshold
                    top_k_limit = top_k or settings.kb_default_top_k

                    params = [query_embedding, similarity_threshold]
                    param_index = 3

                    # フィルタの適用（Allow-list チェック + ENUMバリデーション）
                    if filters:
                        # 許可されていないキーが含まれている場合はエラー
                        invalid_keys = set(filters.keys()) - ALLOWED_FILTER_KEYS
                        if invalid_keys:
                            raise ValueError(
                                f"Invalid filter keys: {invalid_keys}. "
                                f"Allowed keys: {ALLOWED_FILTER_KEYS}")

                        if "source_type" in filters:
                            source_type = filters["source_type"]
                            if source_type not in VALID_SOURCE_TYPES:
                                raise ValueError(
                                    f"Invalid source_type: {source_type}.")
                            query += f" AND s.type = ${param_index}"
                            params.append(source_type)
                            param_index += 1

                        if "source_types" in filters:
                            source_types = filters["source_types"]
                            if not isinstance(source_types, list):
                                raise ValueError(
                                    f"source_types must be a list")

                            if len(source_types) == 0:
                                raise ValueError("source_types must not be empty")

                            invalid_types = set(source_types) - VALID_SOURCE_TYPES
                            if invalid_types:
                                raise ValueError(
                                    f"Invalid source_types: {invalid_types}.")

                            query += (
                                f" AND s.type = ANY(${param_index}"
                                f"::source_type_enum[])"
                            )
                            params.append(source_types)
                            param_index += 1

                        if "channel_id" in filters:
                            try:
                                channel_id = int(filters["channel_id"])
                            except (ValueError, TypeError):
                                raise ValueError(
                                    f"Invalid channel_id: must be an integer.")
                            query += (
                                f" AND (s.metadata->>'channel_id')::bigint = "
                                f"${param_index}"
                            )
                            params.append(channel_id)
                            param_index += 1

                        if "user_id" in filters:
                            try:
                                user_id = int(filters["user_id"])
                            except (ValueError, TypeError):
                                raise ValueError(
                                    f"Invalid user_id: must be an integer.")
                            query += (
                                f" AND (s.metadata->>'author_id')::bigint = "
                                f"${param_index}"
                            )
                            params.append(user_id)
                            param_index += 1

                    # 類似度でソート
                    # ⚠️ 改善: constants.pyの定数を使用（VECTOR_CASTとVECTOR_DIMENSION）
                    query += f"""
                        AND 1 - (c.embedding <=> $1::{vector_cast}(
                            {vector_dimension})) > $2
                        ORDER BY c.embedding <=> $1::{vector_cast}(
                            {vector_dimension})
                        LIMIT ${param_index}
                    """
                    params.append(min(top_k, top_k_limit))

                    # ⚠️ 安全チェック: embedding IS NOT NULL が含まれていることを確認
                    if "embedding IS NOT NULL" not in query.upper():
                        raise ValueError(
                            "CRITICAL: embedding IS NOT NULL condition "
                            "is missing."
                        )

                    rows = await conn.fetch(query, *params)
        except asyncio.TimeoutError:
            from ..exceptions import DatabaseConnectionError
            logger.error("Failed to acquire database connection: pool exhausted")
            raise DatabaseConnectionError(
                "Database connection pool exhausted"
            ) from None
        except asyncpg.PostgresConnectionError as e:
            from ..exceptions import DatabaseConnectionError
            logger.error(f"Database connection failed: {e}")
            raise DatabaseConnectionError(
                f"Database connection failed: {e}"
            ) from e
        except Exception as e:
            from ..exceptions import DatabaseError
            logger.error(f"Error during similarity search: {e}", exc_info=True)
            raise DatabaseError(f"Error during similarity search: {e}") from e

        return [
            {
                "source_id": row["source_id"],
                "source_type": row["type"],
                "title": row["title"],
                "uri": row["uri"],
                "source_metadata": row["source_metadata"] or {},
                "chunk_id": row["chunk_id"],
                "content": row["content"],
                "location": row["location"] or {},
                "token_count": row["token_count"],
                "similarity": float(row["similarity"]),
            }
            for row in rows
        ]
```

#### 3.2 検索サービスの実装

```python
# src/kotonoha_bot/features/knowledge_base/search.py
"""統合検索機能"""

import structlog
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...db.postgres import PostgreSQLDatabase
    from ...external.embedding import EmbeddingProvider

logger = structlog.get_logger(__name__)


# ⚠️ 改善（コード品質）: 型アノテーションの不一致を改善
# 戻り値にTypedDictまたはdataclassを定義することで、型安全性を向上
from typing import TypedDict

class SearchResult(TypedDict):
    """検索結果の型定義"""
    chunk_id: int
    source_id: int
    content: str
    similarity: float
    source_type: str
    title: str
    uri: str | None
    source_metadata: dict | None

class KnowledgeBaseSearch:
    """知識ベース検索"""
    
    def __init__(
        self,
        db: "PostgreSQLDatabase",
        embedding_provider: "EmbeddingProvider",
    ):
        self.db = db
        self.embedding_provider = embedding_provider
    
    async def search(
        self,
        query: str,
        top_k: int = 5,
        source_types: list[str] | None = None,
        filters: dict | None = None,
    ) -> list[SearchResult]:
        """セマンティック検索を実行
        
        Args:
            query: 検索クエリ（テキスト）
            top_k: 取得する結果の数
            source_types: 検索対象のソースタイプ（例: ["discord_session", "document_file"]）
            filters: 追加のフィルタ条件
        
        Returns:
            検索結果のリスト
        """
        # 1. クエリをベクトル化（リアルタイムで必要）
        logger.debug(f"Generating embedding for query: {query[:50]}...")
        query_embedding = await self.embedding_provider.generate_embedding(
            query)
        
        # 2. フィルタの構築
        search_filters = filters or {}
        if source_types:
            # ⚠️ 重要: source_types は複数指定可能
            # 複数のソースタイプ（例：「WebとPDFから検索したい」）を同時に指定した場合、
            # IN句を使用してクエリを構築します
            if len(source_types) == 1:
                search_filters["source_type"] = source_types[0]
            else:
                # 複数のソースタイプを指定した場合、IN句を使用
                # 注意: similarity_search メソッドで source_types リストを処理できるように実装が必要
                search_filters["source_types"] = source_types
        
        # 3. ベクトル検索
        results = await self.db.similarity_search(
            query_embedding=query_embedding,
            top_k=top_k,
            filters=search_filters,
        )
        
        # ⚠️ 改善（データ整合性）: セッションアーカイブ時の重複検索問題への対策
        # 現状: スライディングウィンドウ方式で、アーカイブ時に「直近5件」を sessions テーブルに残しつつ、
        # それらを含めて knowledge_chunks に保存します。
        # 課題: ユーザーが直近の話題について検索した際、「短期記憶（sessions）」と「長期記憶（knowledge）」の
        # 両方から同じメッセージがヒットする可能性があります。
        # 対策: 検索結果の重複排除（Deduplication）ロジックを追加
        # - メッセージID（またはハッシュ）を見て、短期記憶と長期記憶で重複があれば短期記憶を優先する
        # - または、検索範囲の制御: 短期記憶にある範囲は、長期記憶の検索結果から除外するフィルタを入れる
        # 推奨: 実装がシンプルな「検索結果取得後の重複排除」ロジックを採用
        # 
        # 注意: 現時点では knowledge_chunks のみを検索しているため、重複は発生しません。
        # 将来的に sessions テーブルからも検索する場合は、以下のロジックを実装してください:
        # 
        # # 重複排除の例（メッセージIDベース）
        # seen_message_ids = set()
        # deduplicated_results = []
        # for result in results:
        #     message_id = result.get("location", {}).get("message_id")
        #     if message_id and message_id in seen_message_ids:
        #         continue  # 重複をスキップ
        #     seen_message_ids.add(message_id)
        #     deduplicated_results.append(result)
        # results = deduplicated_results
        
        logger.info(f"Search completed: {len(results)} results found")
        return results
    
    async def search_by_source_type(
        self,
        query: str,
        source_type: str,
        top_k: int = 5,
    ) -> list[SearchResult]:
        """特定のソースタイプで検索"""
        return await self.search(
            query=query,
            top_k=top_k,
            source_types=[source_type],
        )
```

**完了基準**:

- [ ] `similarity_search` メソッドが実装されている
- [ ] pgvector の `<=>` 演算子を使用したベクトル検索が動作する
- [ ] `KnowledgeBaseSearch` クラスが実装されている
- [ ] ベクトル検索が動作する
- [ ] メタデータフィルタリング機能が動作する（チャンネルID、ユーザーIDなど）
- [ ] ベクトルインデックスの最適化が完了している（HNSW）

### Step 4: 知識ベーススキーマの実装 (2-3日)

#### 4.1 知識ベース保存機能の実装

```python
# src/kotonoha_bot/features/knowledge_base/storage.py
"""知識ベース保存機能"""

import orjson
import structlog
from typing import TYPE_CHECKING
import tiktoken

if TYPE_CHECKING:
    from ...db.postgres import PostgreSQLDatabase

logger = structlog.get_logger(__name__)

# OpenAI text-embedding-3-small 用のエンコーダー
_encoding = None

def _get_encoding():
    """エンコーダーを取得（遅延初期化）"""
    global _encoding
    if _encoding is None:
        _encoding = tiktoken.encoding_for_model("text-embedding-3-small")
    return _encoding


class KnowledgeBaseStorage:
    """知識ベースの保存を管理"""
    
    def __init__(self, db: "PostgreSQLDatabase"):
        self.db = db
    
    async def save_message_fast(
        self,
        content: str,
        source_type: str,
        title: str,
        uri: str | None,
        metadata: dict,
        location: dict | None = None,
    ) -> tuple[int, int]:
        """メッセージを高速に保存（ベクトル化は後で）
        
        ⚠️ 重要: locationには共通インターフェース（url, label）を含めることを推奨
        - url: チャンクへの直接リンク（DiscordメッセージURL、PDFページURLなど）
        - label: ユーザーに表示するラベル（例: "メッセージ #5", "ページ 3"）
        
        Returns:
            (source_id, chunk_id) のタプル
        """
        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                # 1. Source登録（status='pending'）
                # ⚠️ 注意: JSONBコーデックが設定されていれば、dictを直接渡せる
                # datetimeが含まれる場合は、事前にISO文字列に変換する
                source_id = await conn.fetchval("""
                    INSERT INTO knowledge_sources (type, title, uri, metadata, status)
                    VALUES ($1, $2, $3, $4::jsonb, 'pending')
                    RETURNING id
                """, source_type, title, uri, metadata)
                
                # 2. チャンク登録（embedding=NULL、token_countを計算）
                encoding = _get_encoding()
                token_count = len(encoding.encode(content))
                
                # ⚠️ 重要: locationには共通インターフェース（url, label）を含めることを推奨
                # locationがNoneの場合は空のdictを使用
                location_dict = location or {}
                chunk_id = await conn.fetchval("""
                    INSERT INTO knowledge_chunks 
                    (source_id, content, embedding, location, token_count)
                    VALUES ($1, $2, NULL, $3::jsonb, $4)
                    RETURNING id
                """,
                source_id, content, location_dict, token_count)
                
                return source_id, chunk_id
    
    async def save_document_fast(
        self,
        source_type: str,
        title: str,
        uri: str,
        chunks: list[dict[str, str]],
        metadata: dict,
    ) -> int:
        """ドキュメントを高速に保存（ベクトル化は後で）
        
        ⚠️ 重要: chunks内の各dictには'content'キーが必須。
        'location'キーが含まれる場合、共通インターフェース（url, label）を含めることを推奨
        - url: チャンクへの直接リンク（PDFページURLなど）
        - label: ユーザーに表示するラベル（例: "ページ 3"）
        """
        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                # 1. Source登録
                # ⚠️ 注意: JSONBコーデックが設定されていれば、dictを直接渡せる
                source_id = await conn.fetchval("""
                    INSERT INTO knowledge_sources (type, title, uri, metadata, status)
                    VALUES ($1, $2, $3, $4::jsonb, 'pending')
                    RETURNING id
                """, source_type, title, uri, metadata)
                
                # 2. チャンク一括登録（embedding=NULL、token_countを計算）
                encoding = _get_encoding()
                chunk_data = [
                    (
                        source_id,
                        chunk["content"],
                        None,  # embeddingはNULL
                        chunk.get("location", {}),  # JSONBコーデックが設定されていれば直接渡せる
                        len(encoding.encode(chunk["content"])),  # token_count
                    )
                    for chunk in chunks
                ]
                
                # ⚠️ 改善（パフォーマンス）: executemany のバッチサイズ制御
                # チャンク一括登録時にバッチサイズを制限することで、
                # 巨大なセッション（数百チャンク）でもメモリ使用量を制御できる
                # ⚠️ 改善（コード品質）: pydantic-settings を使用
                from ..config import settings
                BATCH_SIZE = settings.kb_chunk_insert_batch_size
                
                for i in range(0, len(chunk_data), BATCH_SIZE):
                    batch = chunk_data[i:i + BATCH_SIZE]
                    await conn.executemany("""
                        INSERT INTO knowledge_chunks 
                        (source_id, content, embedding, location, token_count)
                        VALUES ($1, $2, $3, $4, $5)
                    """, batch)
                
                return source_id
```

**完了基準**:

- [ ] `KnowledgeBaseStorage` クラスが実装されている
- [ ] 高速保存機能が動作する
- [ ] Source と Chunk が正しく保存される

### Step 5: Embedding処理の実装 (2-3日)

#### 5.1 Embedding プロバイダーの実装

```python
# src/kotonoha_bot/external/embedding/__init__.py
"""Embedding プロバイダー抽象化"""

from abc import ABC, abstractmethod

class EmbeddingProvider(ABC):
    """Embedding 生成プロバイダーのインターフェース"""
    
    @abstractmethod
    async def generate_embedding(self, text: str) -> list[float]:
        """テキストからベクトルを生成"""
        pass
    
    @abstractmethod
    def get_dimension(self) -> int:
        """ベクトルの次元数を返す"""
        pass


# src/kotonoha_bot/external/embedding/openai_embedding.py
"""OpenAI Embedding API プロバイダー"""

import os
import structlog
import openai
from typing import TYPE_CHECKING
from tenacity import (
    retry, stop_after_attempt, wait_exponential, retry_if_exception_type)

if TYPE_CHECKING:
    from . import EmbeddingProvider

logger = structlog.get_logger(__name__)

class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI text-embedding-3-small を使用（リトライロジック付き）"""
    
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = "text-embedding-3-small"
        self.dimension = 1536
        self._client = openai.AsyncOpenAI(api_key=self.api_key)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type(
            (openai.RateLimitError, openai.APITimeoutError)),
        reraise=True,
    )
    async def generate_embedding(self, text: str) -> list[float]:
        """テキストからベクトルを生成（リトライロジック付き）"""
        try:
            response = await self._client.embeddings.create(
                model=self.model,
                input=text,
                dimensions=self.dimension,
            )
            return response.data[0].embedding
        except openai.RateLimitError as e:
            logger.warning(f"Rate limit hit, retrying...: {e}")
            raise
        except openai.APITimeoutError as e:
            logger.warning(f"API timeout, retrying...: {e}")
            raise
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise
        except Exception as e:
            # ⚠️ 改善（コード品質）: 具体的な例外を定義
            from ..exceptions import EmbeddingAPIError
            logger.error(
                f"Unexpected error in generate_embedding: {e}", exc_info=True)
            raise EmbeddingAPIError(f"Unexpected error: {e}") from e
    
    async def generate_embeddings_batch(
        self, texts: list[str]
    ) -> list[list[float]]:
        """複数のテキストをバッチでベクトル化（API効率化）
        
        ⚠️ 改善: OpenAI Embedding APIはバッチリクエストをサポートしているため、
        個別にAPIを呼ぶのではなく、バッチで一度に送信することで効率化します。
        API呼び出し回数を大幅に削減（100回→1回）、レート制限にかかりにくくなります。
        """
        try:
            response = await self._client.embeddings.create(
                model=self.model,
                input=texts,  # リストを直接渡せる
                dimensions=self.dimension,
            )
            return [
                data.embedding for data in response.data]
        except openai.RateLimitError as e:
            logger.warning(f"Rate limit hit in batch embedding: {e}")
            raise
        except openai.APITimeoutError as e:
            logger.warning(f"API timeout in batch embedding: {e}")
            raise
        except openai.APIError as e:
            logger.error(f"OpenAI API error in batch embedding: {e}")
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error in generate_embeddings_batch: {e}",
                exc_info=True)
            raise
    
    def get_dimension(self) -> int:
        """ベクトルの次元数（1536）"""
        return self.dimension
```

#### 5.2 バックグラウンドタスクの実装

```python
# src/kotonoha_bot/features/knowledge_base/embedding_processor.py
"""Embedding処理のバックグラウンドタスク"""

import asyncio
import structlog
from discord.ext import tasks
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...db.postgres import PostgreSQLDatabase
    from ...external.embedding import EmbeddingProvider

logger = structlog.get_logger(__name__)


class EmbeddingProcessor:
    """Embedding処理を管理するクラス"""
    
    def __init__(
        self,
        db: "PostgreSQLDatabase",
        embedding_provider: "EmbeddingProvider",
        batch_size: int | None = None,
        max_concurrent: int | None = None,
    ):
        self.db = db
        self.embedding_provider = embedding_provider
        # 環境変数から設定を読み込み（デフォルト値あり）
        # ⚠️ 改善（コード品質）: pydantic-settings を使用
        from ..config import settings
        batch_size = batch_size or settings.kb_embedding_batch_size
        max_concurrent = max_concurrent or settings.kb_embedding_max_concurrent
        
        # ⚠️ 重要: セマフォによる同時実行数制限
        # 接続プール枯渇対策: DB_POOL_MAX_SIZEの20〜30%程度に制限
        # これにより、Embedding処理だけでプールを食い尽くし、通常のチャット応答が
        # タイムアウトするリスクを防ぎます
        # 実装: _generate_embedding_with_limitメソッド内で
        # `async with self._semaphore:` を使用
        self._semaphore = asyncio.Semaphore(max_concurrent)  # レート制限用セマフォ
        self._lock = asyncio.Lock()  # 競合状態対策
        
        # ⚠️ 重要: @tasks.loop デコレータのパラメータはクラス定義時に評価されるため、
        # 環境変数の遅延読み込みが必要な場合は、__init__で間隔を保存し、
        # start()メソッドでchange_interval()を呼び出します。
        self._interval = settings.kb_embedding_interval_minutes
    
    @tasks.loop(minutes=1)  # デフォルト値（start()で動的に変更される）
    async def process_pending_embeddings(self):
        """pending状態のチャンクをバッチでベクトル化
        
        ⚠️ 重要: エラーハンドリングを実装し、例外が発生してもタスクが継続するようにする
        """
        try:
            await self._process_pending_embeddings_impl()
        except Exception as e:
            logger.exception(f"Error in embedding processing: {e}")
            # タスクは継続（次のループで再試行）
    
    @process_pending_embeddings.error
    async def process_pending_embeddings_error(self, error: Exception):
        """タスクエラー時のハンドラ"""
        logger.error(f"Embedding task error: {error}", exc_info=True)
        # 必要に応じてアラート送信など
    
    @process_pending_embeddings.before_loop
    async def before_process_embeddings(self):
        """タスク開始前の待機"""
        pass
    
    async def _process_pending_embeddings_impl(self):
        """Embedding処理の実装（エラーハンドリング分離）"""
        # 競合状態対策: asyncio.Lockを使用
        if self._lock.locked():
            logger.debug(
                "Embedding processing already in progress, skipping...")
            return
        
        async with self._lock:
            logger.debug("Starting embedding processing...")
            
            # ⚠️ 重要: Dead Letter Queue対応 - retry_countを考慮
            # ⚠️ 改善（コード品質）: pydantic-settings を使用
            from ..config import settings
            MAX_RETRY_COUNT = settings.kb_embedding_max_retry
            
            # ⚠️ 重要: トランザクション内でのAPIコールを回避するため、
            # Tx1: FOR UPDATE SKIP LOCKED で対象行を取得し、IDとcontentをメモリに保持して即コミット
            # No Tx: OpenAI API コール（時間かかる）
            # Tx2: 結果を UPDATE
            
            # Tx1: 対象チャンクを取得（FOR UPDATE SKIP LOCKEDでロック）
            async with self.db.pool.acquire() as conn:
                async with conn.transaction():
                    # FOR UPDATE SKIP LOCKED でロックを取得し、他のプロセスと競合しないようにする
                    # ⚠️ 改善（パフォーマンス）: idx_chunks_queue 部分インデックスが使用される
                    # knowledge_chunks が数百万件になった際、embedding IS NULL の行を探すのに
                    # 時間がかかるとバッチ処理が遅延します。
                    # idx_chunks_queue 部分インデックスにより、ワーカーはテーブル全体を
                    # スキャンせず、インデックスのみを見て処理対象を即座に見つけられます。
                    pending_chunks = await conn.fetch("""
                        SELECT id, content, source_id
                        FROM knowledge_chunks
                        WHERE embedding IS NULL
                        AND retry_count < $1
                        ORDER BY id ASC
                        LIMIT $2
                        FOR UPDATE SKIP LOCKED
                    """, MAX_RETRY_COUNT, self.batch_size)
                    # トランザクションを即コミット（ロックを解放）
            
            if not pending_chunks:
                logger.debug("No pending chunks to process")
                return
            
            logger.info(f"Processing {len(pending_chunks)} pending chunks...")
            
            # No Tx: OpenAI Embedding APIのバッチリクエスト（時間かかる処理）
            # ⚠️ 重要: この時点ではトランザクションを保持していないため、
            # 接続プールが枯渇したり、他のクエリをブロックしない
            texts = [chunk["content"] for chunk in pending_chunks]
            try:
                embeddings = await self._generate_embeddings_batch(texts)
            except Exception as e:
                # Embedding API全体障害時の処理: 失敗したチャンクのretry_countをインクリメント
                # ⚠️ 改善（セキュリティ）: 詳細なスタックトレースはログのみに出力（情報漏洩を防ぐ）
                error_code = self._classify_error(e)
                logger.error(
                    f"Embedding API failed for batch: {error_code}",
                    exc_info=True)  # スタックトレースはログのみ
                # Tx2: エラー時の更新（別トランザクション）
                async with self.db.pool.acquire() as conn:
                    async with conn.transaction():
                        for chunk in pending_chunks:
                            # retry_countをインクリメント
                            new_retry_count = await conn.fetchval("""
                                UPDATE knowledge_chunks
                                SET retry_count = COALESCE(retry_count, 0) + 1
                                WHERE id = $1
                                RETURNING retry_count
                            """, chunk["id"])
                            
                            # ⚠️ 改善（データ整合性）: DLQへの移動ロジックを追加
                            # retry_countが上限に達したチャンクをDLQに移動
                            # ⚠️ 改善（セキュリティ）: エラーオブジェクトを渡す
                            # （エラーコードと一般化されたメッセージのみを保存）
                            if new_retry_count >= MAX_RETRY_COUNT:
                                await self._move_to_dlq(conn, chunk, e)
                        
                        # retry_countが上限に達したソースはfailedに
                        source_ids = {
                            chunk["source_id"] for chunk in pending_chunks}
                        for source_id in source_ids:
                            failed_count = await conn.fetchval("""
                                SELECT COUNT(*)
                                FROM knowledge_chunks
                                WHERE source_id = $1
                                AND retry_count >= $2
                            """, source_id, MAX_RETRY_COUNT)
                            
                            if failed_count > 0:
                                # ⚠️ 改善（セキュリティ）: エラーコードと一般化されたメッセージのみを保存
                                error_code = 'EMBEDDING_MAX_RETRIES_EXCEEDED'
                                error_message = (
                                    f"Embedding failed after "
                                    f"{MAX_RETRY_COUNT} retries"
                                )
                                await conn.execute("""
                                    UPDATE knowledge_sources
                                    SET status = 'failed',
                                        error_code = $1,
                                        error_message = $2,
                                        updated_at = CURRENT_TIMESTAMP
                                    WHERE id = $3
                                """, error_code, error_message, source_id)
                return  # 処理を中断
            
            # ⚠️ 重要: halfvec固定採用
            vector_cast = "halfvec"
            
            # Tx2: 結果を UPDATE（別トランザクション）
            # ⚠️ 重要: APIコールが完了してからトランザクションを開始するため、
            # トランザクションの保持時間が最小限になる
            async with self.db.pool.acquire() as conn:
                async with conn.transaction():
                    # ⚠️ 改善: retry_countが上限に達したチャンクをチェック
                    # 処理前に retry_count を確認し、上限に達している場合はDLQに移動
                    for chunk in pending_chunks:
                        current_retry_count = chunk.get("retry_count", 0)
                        if current_retry_count >= MAX_RETRY_COUNT:
                            # 既に上限に達している場合はDLQに移動（通常は発生しないが、安全のため）
                            # ⚠️ 改善（セキュリティ）: エラーオブジェクトを渡す
                            # （エラーコードと一般化されたメッセージのみを保存）
                            await self._move_to_dlq(
                                conn, chunk,
                                ValueError(
                                    "Retry count already at maximum "
                                    "before processing"
                                ))
                    
                    # 正常に処理されたチャンクのみを更新
                    successful_chunks = [
                        chunk for chunk in pending_chunks
                        if chunk.get("retry_count", 0) < MAX_RETRY_COUNT
                    ]
                    
                    if successful_chunks:
                        successful_embeddings = [
                            emb for emb, chunk in zip(embeddings, pending_chunks)
                            if chunk.get("retry_count", 0) < MAX_RETRY_COUNT
                        ]
                        
                        # ⚠️ 改善（パフォーマンス）: executemany のバッチサイズ制御
                        # チャンク一括更新時にバッチサイズを制限することで、
                        # 巨大なバッチ（数百チャンク）でもメモリ使用量を制御できる
                        # ⚠️ 改善（コード品質）: pydantic-settings を使用
                        from ..config import settings
                        update_data = [
                            (emb, chunk["id"])
                            for emb, chunk in zip(successful_embeddings, successful_chunks)
                        ]
                        BATCH_SIZE = settings.kb_chunk_update_batch_size
                        
                        for i in range(0, len(update_data), BATCH_SIZE):
                            batch = update_data[i:i + BATCH_SIZE]
                            await conn.executemany(f"""
                                UPDATE knowledge_chunks
                                SET embedding = $1::{vector_cast}({vector_dimension}),
                                    retry_count = 0
                                WHERE id = $2
                            """, batch)
            
            # Sourceのステータスも更新
            await self._update_source_status(pending_chunks)
            
            logger.info(f"Successfully processed {len(pending_chunks)} chunks")
    
    async def _generate_embedding_with_limit(self, text: str) -> list[float]:
        """セマフォで制限されたEmbedding生成（レート制限対策）
        
        ⚠️ 重要: セマフォによる同時実行数制限の実装
        - EmbeddingProcessorの初期化時にセマフォを作成（max_concurrentで制限）
        - このメソッド内で `async with self._semaphore:` を使用して同時実行数を制限
        - 接続プール枯渇対策: DB_POOL_MAX_SIZEの20〜30%程度に制限
        """
        async with self._semaphore:
            result = await self.embedding_provider.generate_embedding(text)
            await asyncio.sleep(0.05)  # APIごとの間隔
            return result
    
    async def _generate_embeddings_batch(
        self, 
        texts: list[str]
    ) -> list[list[float]]:
        """複数のテキストをバッチでベクトル化
        
        ⚠️ 改善: OpenAI Embedding APIはバッチリクエストをサポートしているため、
        個別にAPIを呼ぶのではなく、バッチで一度に送信することで効率化します。
        API呼び出し回数を大幅に削減（100回→1回）、レート制限にかかりにくくなります。
        """
        # OpenAI Embedding APIはバッチリクエストをサポート
        # 注意: OpenAIEmbeddingProvider にバッチメソッドを追加する必要がある
        if hasattr(self.embedding_provider, 'generate_embeddings_batch'):
            # バッチAPIを使用（推奨）
            return await self.embedding_provider.generate_embeddings_batch(
                texts)
        else:
            # フォールバック: 個別に呼び出す（非効率だが動作する）
            logger.warning(
                "Batch embedding API not available, using individual calls")
            embeddings = await asyncio.gather(
                *[self._generate_embedding_with_limit(text) for text in texts]
            )
            return embeddings
    
    async def _move_to_dlq(
        self, conn: asyncpg.Connection, chunk: dict, error: Exception
    ) -> None:
        """チャンクをDead Letter Queueに移動
        
        ⚠️ 改善（データ整合性）: knowledge_chunks_dlqテーブルは定義されていますが、
        実際にDLQへ移動するコードが実装計画にありませんでした。
        このメソッドを追加することで、retry_countが上限に達したチャンクを
        DLQに移動し、手動での確認・再処理を可能にします。
        
        ⚠️ 改善（セキュリティ）: エラーメッセージの情報漏洩リスクを改善
        エラー内容をそのまま保存すると、APIエラーやスタックトレースが含まれる可能性があります。
        エラーコードと一般化されたメッセージのみを保存し、詳細なスタックトレースはログのみに出力します。
        
        Args:
            conn: データベース接続（トランザクション内）
            chunk: 移動するチャンク（id, source_id, content を含む）
            error: エラーオブジェクト（詳細な情報を含む）
        """
        try:
            # ⚠️ 改善（セキュリティ）: エラーコードと一般化されたメッセージのみを保存
            error_code = self._classify_error(error)
            error_message = self._generalize_error_message(error)
            
            # 詳細なスタックトレースはログのみに出力（情報漏洩を防ぐ）
            logger.error(
                f"Chunk {chunk['id']} moved to DLQ after "
                f"{chunk.get('retry_count', 0)} retries: {error_code}",
                exc_info=error  # スタックトレースはログのみ
            )
            
            # DLQに移動（エラーコードと一般化されたメッセージのみ）
            # ⚠️ 重要: トランザクション内で実行されることを前提としている（conn がトランザクション内であること）
            # ⚠️ 改善（データ整合性）: source_id、source_type、source_title、
            # error_codeを追加して追跡性を向上
            # 元のソースを追跡できるように、source_id、source_type、source_titleも保存
            source_id = chunk.get("source_id")
            
            # ⚠️ 改善: source_typeとsource_titleを取得（トレーサビリティ向上）
            source_info = None
            if source_id:
                source_info = await conn.fetchrow("""
                    SELECT type, title FROM knowledge_sources WHERE id = $1
                """, source_id)
            
            source_type = source_info["type"] if source_info else None
            source_title = source_info["title"] if source_info else None
            
            await conn.execute("""
                INSERT INTO knowledge_chunks_dlq
                (
                    original_chunk_id, source_id, source_type, source_title,
                    content, error_code, error_message, retry_count,
                    last_retry_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, CURRENT_TIMESTAMP)
            """, 
                chunk["id"], 
                source_id,
                source_type,  # ⚠️ 改善: source_typeも保存（トレーサビリティ向上）
                source_title,
                chunk["content"], 
                error_code,  # ⚠️ 改善: error_codeを分離して保存
                error_message, 
                chunk.get("retry_count", 0)
            )
            
            # ⚠️ 改善（データ整合性）: 元のチャンクを削除（DLQに移動したため、元のテーブルからは削除）
            # 注意: 削除ではなく、status カラムで管理する場合は、以下のように UPDATE することも可能
            # await conn.execute("""
            #     UPDATE knowledge_chunks SET status = 'dlq' WHERE id = $1
            # """, chunk["id"])
            await conn.execute("""
                DELETE FROM knowledge_chunks WHERE id = $1
            """, chunk["id"])
        except Exception as e:
            logger.error(
                f"Failed to move chunk {chunk['id']} to DLQ: {e}",
                exc_info=True)
    
    def _classify_error(self, error: Exception) -> str:
        """エラーを分類してエラーコードを返す
        
        ⚠️ 改善（セキュリティ）: エラーメッセージの情報漏洩リスクを改善
        エラーオブジェクトからエラーコードを抽出し、一般化されたコードを返します。
        
        Returns:
            エラーコード（例: 'EMBEDDING_API_TIMEOUT', 'RATE_LIMIT', 'UNKNOWN_ERROR'）
        """
        error_type = type(error).__name__
        error_str = str(error).lower()
        
        # エラータイプとメッセージからエラーコードを分類
        if 'timeout' in error_str or 'timed out' in error_str:
            return 'EMBEDDING_API_TIMEOUT'
        elif 'rate limit' in error_str or '429' in error_str:
            return 'RATE_LIMIT'
        elif 'authentication' in error_str or '401' in error_str:
            return 'AUTHENTICATION_ERROR'
        elif 'permission' in error_str or '403' in error_str:
            return 'PERMISSION_ERROR'
        elif 'not found' in error_str or '404' in error_str:
            return 'NOT_FOUND'
        elif 'server error' in error_str or '500' in error_str:
            return 'SERVER_ERROR'
        else:
            return 'UNKNOWN_ERROR'
    
    def _generalize_error_message(self, error: Exception) -> str:
        """エラーメッセージを一般化する
        
        ⚠️ 改善（セキュリティ）: エラーメッセージの情報漏洩リスクを改善
        詳細なスタックトレースやAPIキーなどの機密情報を含まない、一般化されたメッセージを返します。
        
        Returns:
            一般化されたエラーメッセージ
        """
        error_code = self._classify_error(error)
        
        # エラーコードに基づいて一般化されたメッセージを返す
        error_messages = {
            'EMBEDDING_API_TIMEOUT': 'Embedding API request timed out',
            'RATE_LIMIT': 'Rate limit exceeded',
            'AUTHENTICATION_ERROR': 'Authentication failed',
            'PERMISSION_ERROR': 'Permission denied',
            'NOT_FOUND': 'Resource not found',
            'SERVER_ERROR': 'Server error occurred',
            'UNKNOWN_ERROR': 'An error occurred during processing',
        }
        
        return error_messages.get(
            error_code, 'An error occurred during processing'
        )
    
    async def _update_source_status(self, processed_chunks: list[dict]):
        """Sourceのステータスを更新
        
        ⚠️ 改善（データ整合性）: knowledge_sources と knowledge_chunks の整合性リスクを改善
        - retry_count >= MAX_RETRY のチャンクが存在する場合の扱いを明確化
        - DLQに移動したチャンクがある場合は 'partial' ステータスを設定
        """
        source_ids = {chunk["source_id"] for chunk in processed_chunks}
        
        async with self.db.pool.acquire() as conn:
            for source_id in source_ids:
                # ⚠️ 改善（コード品質）: pydantic-settings を使用
                from ..config import settings
                MAX_RETRY_COUNT = settings.kb_embedding_max_retry
                
                # ⚠️ 改善: 完了判定: embedding が NULL で、かつリトライ上限未達のチャンクがないこと
                pending_count = await conn.fetchval("""
                    SELECT COUNT(*) FROM knowledge_chunks
                    WHERE source_id = $1 
                      AND embedding IS NULL 
                      AND retry_count < $2
                """, source_id, MAX_RETRY_COUNT)
                
                # ⚠️ 改善: DLQ行きのチャンク数も確認
                # ⚠️ 改善（データ整合性）: source_idで直接検索できるように改善
                dlq_count = await conn.fetchval("""
                    SELECT COUNT(*) FROM knowledge_chunks_dlq
                    WHERE source_id = $1
                """, source_id)
                
                if pending_count == 0:
                    # ⚠️ 改善: DLQに移動したチャンクがある場合は 'partial'、ない場合は 'completed'
                    new_status = 'partial' if dlq_count > 0 else 'completed'
                    await conn.execute("""
                        UPDATE knowledge_sources 
                        SET status = $1, updated_at = CURRENT_TIMESTAMP
                        WHERE id = $2
                    """, new_status, source_id)
                    logger.debug(
                        f"Source {source_id} marked as {new_status} "
                        f"(pending: {pending_count}, dlq: {dlq_count})"
                    )
    
    def start(self):
        """バックグラウンドタスクを開始（動的に間隔を設定）"""
        # 環境変数から読み込んだ間隔を設定
        self.process_pending_embeddings.change_interval(minutes=self._interval)
        self.process_pending_embeddings.start()
    
    async def graceful_shutdown(self):
        """Graceful Shutdown: 処理中のタスクが完了するまで待機"""
        logger.info("Stopping embedding processor gracefully...")
        
        # タスクをキャンセル
        self.process_pending_embeddings.cancel()
        
        # 処理中のタスクが完了するまで待機
        try:
            # タスクが存在する場合、完了を待つ
            task = getattr(self.process_pending_embeddings, '_task', None)
            if task and not task.done():
                try:
                    from asyncio import timeout
                    async with timeout(30.0):  # 最大30秒待機
                        await task
                except TimeoutError:
                    logger.warning(
                        "Embedding processing task did not complete "
                        "within timeout")
                except asyncio.CancelledError:
                    logger.debug("Embedding processing task was cancelled")
        except Exception as e:
            logger.error(f"Error during graceful shutdown: {e}", exc_info=True)
        
        logger.info("Embedding processor stopped")
```

#### 5.3 依存性注入パターンの採用

循環インポートのリスクを回避するため、`main.py` で一括初期化し、依存性を注入します。

```python
# src/kotonoha_bot/main.py（改善版）

from kotonoha_bot.db.postgres import PostgreSQLDatabase
from kotonoha_bot.external.embedding.openai_embedding import (
    OpenAIEmbeddingProvider)
from kotonoha_bot.features.knowledge_base.storage import KnowledgeBaseStorage
from kotonoha_bot.features.knowledge_base.embedding_processor import (
    EmbeddingProcessor)
from kotonoha_bot.features.knowledge_base.session_archiver import (
    SessionArchiver)

async def main():
    # データベース初期化
    # ⚠️ 改善（セキュリティ）: DATABASE_URL にパスワードを含める形式への依存を改善
    # 本番環境では個別パラメータを使用し、パスワードを接続文字列に埋め込まない
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        # 開発環境用: 接続文字列を使用（後方互換性）
        db = PostgreSQLDatabase(connection_string=database_url)
    else:
        # 本番環境推奨: 個別パラメータを使用（パスワードを分離）
        db = PostgreSQLDatabase(
            host=os.getenv("POSTGRES_HOST"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            database=os.getenv("POSTGRES_DB"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),  # 分離
        )
    await db.initialize()
    
    # Embedding プロバイダー初期化
    embedding_provider = OpenAIEmbeddingProvider()
    
    # 知識ベース関連の初期化（環境変数から設定を読み込む）
    kb_storage = KnowledgeBaseStorage(db)
    embedding_processor = EmbeddingProcessor(
        db,
        embedding_provider,
        # batch_size と max_concurrent は環境変数から読み込まれる
    )
    session_archiver = SessionArchiver(
        db,
        embedding_provider,
        # archive_threshold_hours は環境変数から読み込まれる
    )
    
    # Bot初期化（依存性を注入）
    bot = KotonohaBot(
        db=db,
        kb_storage=kb_storage,
        embedding_processor=embedding_processor,
        session_archiver=session_archiver,
    )
    
    # バックグラウンドタスクを開始
    # ⚠️ 重要: embedding_processor.start() を使用することで、
    # 環境変数から読み込んだ間隔が動的に設定されます。
    embedding_processor.start()
    session_archiver.archive_inactive_sessions.start()
    
    try:
        await bot.start(os.getenv("DISCORD_TOKEN"))
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
    finally:
        # Graceful Shutdown: 処理中のタスクが完了するまで待機
        # ⚠️ 重要: atexit は非同期では使えないため、signal ハンドリングまたは
        # Discord.py の bot.close() オーバーライドで対応します。
        await embedding_processor.graceful_shutdown()
        await session_archiver.graceful_shutdown()
        
        # データベース接続をクローズ（確実に呼ぶことを忘れないでください）
        await db.close()
        
        logger.info("Shutdown complete")
```

```python
# src/kotonoha_bot/bot/handlers.py（改善版）

class MessageHandler:
    def __init__(
        self,
        bot: KotonohaBot,
        kb_storage: "KnowledgeBaseStorage" | None = None,
        embedding_processor: "EmbeddingProcessor" | None = None,
        session_archiver: "SessionArchiver" | None = None,
    ):
        # ... 既存の初期化 ...
        
        # 依存性注入（main.pyから渡される）
        self.kb_storage = kb_storage
        self.embedding_processor = embedding_processor
        self.session_archiver = session_archiver
    
    async def cog_unload(self):
        """クリーンアップタスクを停止（Graceful Shutdown）"""
        self.cleanup_task.cancel()
        self.batch_sync_task.cancel()
        
        # Graceful Shutdown: 処理中のタスクが完了するまで待機
        if self.embedding_processor:
            await self.embedding_processor.graceful_shutdown()
        if self.session_archiver:
            await self.session_archiver.graceful_shutdown()
```

**完了基準**:

- [ ] `EmbeddingProvider` インターフェースが実装されている
- [ ] `OpenAIEmbeddingProvider` が動作する
- [ ] バックグラウンドタスクが動作する
- [ ] pendingチャンクが自動的にベクトル化される
- [ ] Graceful Shutdownが実装されている（処理中のタスクが完了するまで待機）

#### 5.4 セッション知識化バッチ処理の実装

定期的に「`last_active_at` が1時間以上前」かつ「`status = 'active'`」のセッションを検索し、知識ベースに変換します。

⚠️ **改善（会話の分断対策）**: スライディングウィンドウ（のりしろ）方式を採用します。

**アーキテクチャ上の決定事項**:

- **アーカイブのトリガー**: 「最終発言から一定時間経過（例: 1時間）」を維持する（ゾンビセッション防止）
- **分断対策**: アーカイブ時に短期記憶をゼロにせず、「直近の数メッセージ（例: 5件）」を残す処理（Pruning）を実装する
- **検索戦略**: Botは常に「現在の短期記憶（のりしろ含む）」＋「ベクトル検索結果」の両方を参照して回答を生成する

**データフロー**:

1. **READ**: 対象セッションの全メッセージを取得
2. **INSERT (長期記憶)**: 全メッセージを knowledge_sources / knowledge_chunks に保存
3. **UPDATE (短期記憶)**: messages カラムを「後ろからN件（例: 5件）」に切り詰めて更新

これにより、「時間が経てば整理されるが、ユーザーが戻ってきても直近の文脈は繋がる」という、人間にとって自然な記憶構造を実現できます。

```python
# src/kotonoha_bot/features/knowledge_base/session_archiver.py
"""セッションの知識化処理"""

import asyncio
import orjson
import structlog
from datetime import datetime, timedelta
from discord.ext import tasks
from typing import TYPE_CHECKING
import tiktoken

if TYPE_CHECKING:
    from ...db.postgres import PostgreSQLDatabase
    from ...external.embedding import EmbeddingProvider

logger = structlog.get_logger(__name__)

# ⚠️ 改善（コード品質）: 定数のハードコード散在を改善
# pydantic-settingsで一元管理（計画には含まれているが徹底されていない箇所あり）
# 以下の定数は環境変数から読み込むが、将来的にはpydantic-settingsで一元管理することを推奨
import os
MAX_EMBEDDING_TOKENS = int(os.getenv("KB_MAX_EMBEDDING_TOKENS", "8191"))
# 最小セッション長（文字数）: これ以下のセッションはアーカイブしない（環境変数から読み込み可能）
MIN_SESSION_LENGTH = int(os.getenv("KB_MIN_SESSION_LENGTH", "50"))


class SessionArchiver:
    """セッションを知識ベースに変換するクラス"""
    
    def __init__(
        self,
        db: "PostgreSQLDatabase",
        embedding_provider: "EmbeddingProvider",
        archive_threshold_hours: int | None = None,
    ):
        self.db = db
        self.embedding_provider = embedding_provider
        # 環境変数から設定を読み込み（デフォルト値あり）
        self.archive_threshold_hours = archive_threshold_hours or int(
            os.getenv("KB_ARCHIVE_THRESHOLD_HOURS", "1"))
        self._processing = False
        # ⚠️ 改善（コード品質）: Graceful Shutdownの改善
        # 処理中のアーカイブタスクを追跡するためのセット
        self._processing_sessions: set = set()
    
    # 環境変数から読み込み
    @tasks.loop(hours=int(os.getenv("KB_ARCHIVE_INTERVAL_HOURS", "1")))
    async def archive_inactive_sessions(self):
        """非アクティブなセッションを知識ベースに変換"""
        if self._processing:
            logger.debug("Session archiving already in progress, skipping...")
            return
        
        try:
            self._processing = True
            logger.debug("Starting session archiving...")
            
            # ⚠️ 改善（コード品質）: pydantic-settings を使用
            from ..config import settings
            # 設定値から閾値とバッチサイズを読み込み
            archive_threshold_hours = int(
                os.getenv("KB_ARCHIVE_THRESHOLD_HOURS",
                          str(self.archive_threshold_hours)))
            batch_size = int(os.getenv("KB_ARCHIVE_BATCH_SIZE", "10"))
            
            # 閾値時間以上非アクティブなセッションを取得
            threshold_time = datetime.now() - timedelta(
                hours=archive_threshold_hours)
            
            # 接続プール枯渇時のタイムアウト処理を追加
            try:
                from asyncio import timeout
                
                # 接続取得にタイムアウトを設定
                async with timeout(30.0):
                    conn = await self.db.pool.acquire()
                try:
                    async with conn:
                        inactive_sessions = await conn.fetch("""
                            SELECT session_key, session_type, messages,
                                   guild_id, channel_id, thread_id,
                                   user_id, last_active_at, version,
                                   last_archived_message_index
                            FROM sessions
                            WHERE status = 'active'
                            AND last_active_at < $1
                            ORDER BY last_active_at ASC
                            LIMIT $2
                        """, threshold_time, batch_size)
                finally:
                    self.db.pool.release(conn)
            except asyncio.TimeoutError:
                logger.error(
                    "Failed to acquire database connection: pool exhausted")
                return
            except asyncpg.exceptions.TooManyConnectionsError:
                logger.error("Connection pool exhausted")
                return
            
            if not inactive_sessions:
                logger.debug("No inactive sessions to archive")
                return
            
            logger.info(
                f"Archiving {len(inactive_sessions)} inactive sessions...")
            
            # ⚠️ 重要: セッションアーカイブの並列処理（高速化）
            # セマフォで同時実行数を制限しつつ並列処理（DBへの負荷に注意）
            # ⚠️ 接続枯渇対策: セマフォの上限を DB_POOL_MAX_SIZE の20〜30%程度に厳密に制限
            # これにより、Archive処理だけでプールを食い尽くし、通常のチャット応答が
            # タイムアウトするリスクを防ぎます
            import os
            # ⚠️ 改善（コード品質）: pydantic-settings を使用
            from ..config import settings
            max_pool_size = settings.db_pool_max_size
            # 20〜30%程度に制限（最小1、最大5）
            archive_concurrency = max(1, min(5, int(max_pool_size * 0.25)))
            archive_semaphore = asyncio.Semaphore(archive_concurrency)
            logger.debug(
                f"Archive semaphore limit: {archive_concurrency} "
                f"(pool max_size: {max_pool_size})")
            
            async def _archive_with_limit(session_row):
                """セマフォで制限されたアーカイブ処理"""
                async with archive_semaphore:
                    try:
                        await self._archive_session(session_row)
                    except Exception as e:
                        logger.error(
                            f"Failed to archive session "
                            f"{session_row['session_key']}: {e}",
                            exc_info=True)
            
            # 並列処理（return_exceptions=Trueで例外を返す）
            await asyncio.gather(
                *[_archive_with_limit(s) for s in inactive_sessions],
                return_exceptions=True
            )
            
            logger.info(
                f"Successfully archived {len(inactive_sessions)} sessions")
            
        except Exception as e:
            logger.error(f"Error during session archiving: {e}", exc_info=True)
        finally:
            self._processing = False
    
    @archive_inactive_sessions.before_loop
    async def before_archive_sessions(self):
        """タスク開始前の待機
        
        ⚠️ 重要: Bot再起動時のバーストを防ぐため、ランダムな遅延を追加
        現状の「最終アクティブから1時間」のみだと、Bot再起動時に大量のアーカイブ処理が走る可能性があります。
        limit 付きで処理している点は良いですが、起動直後のバーストを防ぐため、
        タスク開始時にランダムな遅延を追加して分散させます。
        """
        import random
        import asyncio
        
        # 0〜60秒のランダムな遅延を追加（起動直後のバーストを防ぐ）
        delay = random.uniform(0, 60)
        logger.debug(f"Archive task will start after {delay:.1f}s delay")
        await asyncio.sleep(delay)
    
    async def _archive_session(self, session_row: dict):
        """セッションを知識ベースに変換
        
        ⚠️ 重要: 楽観的ロックの競合時は自動リトライ（tenacity使用）
        Botが高頻度で使われている場合、アーカイブが何度も失敗し続ける可能性があるため、
        競合時のリトライ（バックオフ付き）を実装しています。
        
        ⚠️ 改善（アーカイブ中の「隙間」データの扱い）: 高頻度でチャットが続く場合、
        いつまでもアーカイブが成功しない（リトライループに陥る）可能性があります。
        
        改善案: 「ここまでアーカイブした」ポインタの更新
        セッション全体をアーカイブ済みにするのではなく、last_archived_message_index を持ち、
        それ以前のメッセージのみを知識化対象とする。
        これにより、ユーザーが喋り続けていても「確定した過去」部分だけを切り取ってアーカイブでき、
        競合頻度を下げられます。
        
        ⚠️ 改善（コード品質）: Graceful Shutdownの改善
        処理中のタスクを追跡するため、_processing_sessionsに追加します。
        """
        from tenacity import (
            retry,
            stop_after_attempt,
            wait_exponential,
            retry_if_exception_type
        )
        
        @retry(
            stop=stop_after_attempt(3),  # 最大3回リトライ
            # 指数バックオフ: 1秒、2秒、4秒
            wait=wait_exponential(multiplier=1, min=1, max=10),
            # ValueError（楽観的ロック競合）のみリトライ
            retry=retry_if_exception_type(ValueError),
            reraise=True  # 最終的に失敗した場合は例外を再発生
        )
        async def _archive_session_with_retry():
            # ⚠️ 改善: 処理中のタスクを追跡
            import asyncio
            task = asyncio.create_task(self._archive_session_impl(session_row))
            self._processing_sessions.add(task)
            try:
                return await task
            finally:
                self._processing_sessions.discard(task)
        
        return await _archive_session_with_retry()
    
    async def _archive_session_impl(self, session_row: dict):
        """セッションを知識ベースに変換（実装本体）
        
        ⚠️ 改善（アーカイブ中の「隙間」データの扱い）: 高頻度でチャットが続く場合、
        いつまでもアーカイブが成功しない（リトライループに陥る）可能性があります。
        
        改善案: 「ここまでアーカイブした」ポインタの更新
        セッション全体をアーカイブ済みにするのではなく、last_archived_message_index を持ち、
        それ以前のメッセージのみを知識化対象とする。
        
        ⚠️ 改善（会話の分断対策）: スライディングウィンドウ（のりしろ）方式
        アーカイブ処理が走り、データが長期記憶へ移動した直後にユーザーが発言すると、
        直前の文脈が短期記憶から消えているため、Botが「何の話でしたっけ？」となってしまう現象を防ぐ。
        
        改善策: アーカイブ時に短期記憶を「全消去」するのではなく、
        「直近の数メッセージ（のりしろ）」を残して更新（Prune）する設計にします。
        
        トリガー（いつやるか）: 時間経過（last_active_at < 1時間前）を採用。
        理由: 会話の「鮮度」を保ち、システムリソースを解放するため。
        
        保持ロジック（何を残すか）: スライディングウィンドウ（最新のN件）を採用。
        理由: 時間で切られても、文脈の「しっぽ」を残すことで分断を防ぐため。
        """
        session_key = session_row['session_key']
        # ⚠️ 注意: JSONBコーデックが設定されていれば、自動的にlist[dict]に変換される
        messages = session_row['messages']
        original_last_active_at = session_row['last_active_at']
        # ⚠️ 改善（データ整合性）: versionカラムを使用した楽観的ロック
        original_version = session_row.get('version', 1)
        # ⚠️ 改善: 現在のアーカイブ済み地点を取得
        current_archived_index = session_row.get(
            'last_archived_message_index', 0
        )
        
        if not messages:
            logger.debug(f"Skipping empty session: {session_key}")
            return
        
        # ⚠️ 改善: アーカイブ対象のメッセージを取得（last_archived_message_index 以降のみ）
        # ⚠️ 重要（Critical Bug Fix）: messages配列を切り詰めた場合、
        # last_archived_message_index は 0 にリセットされている
        # そのため、current_archived_index が 0 より大きい場合は、配列の長さを超えていないか確認する必要がある
        # ただし、通常は配列を切り詰めた時点で 0 にリセットされるため、このケースは稀
        if current_archived_index >= len(messages):
            # インデックスが配列の長さを超えている場合（不整合状態）、0 にリセットして全メッセージを対象とする
            logger.warning(
                f"Session {session_key}: "
                f"last_archived_message_index ({current_archived_index}) "
                f"exceeds messages length ({len(messages)}), resetting to 0")
            current_archived_index = 0
        
        messages_to_archive = messages[current_archived_index:]
        
        if not messages_to_archive:
            # アーカイブ対象がない場合（すべてアーカイブ済み）、status='archived' に更新して終了
            async with self.db.pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute("""
                        UPDATE sessions
                        SET status = 'archived',
                            version = version + 1
                        WHERE session_key = $1
                        AND version = $2
                    """, session_key, original_version)
            return
        
        # フィルタリング: 短すぎるセッションやBotのみのセッションを除外
        # ⚠️ 注意: アーカイブ対象のメッセージ（messages_to_archive）で判定
        if not self._should_archive_session(messages_to_archive):
            logger.debug(f"Skipping low-value session: {session_key}")
            # アーカイブしないが、last_archived_message_index を更新（再処理を避ける）
            # 注意: この場合は知識ベースへの登録を行わないため、単純なUPDATEのみで問題ありません
            async with self.db.pool.acquire() as conn:
                async with conn.transaction():
                    # すべてのメッセージをアーカイブ済みとしてマーク（アーカイブ対象がないため）
                    await conn.execute("""
                        UPDATE sessions
                        SET status = 'archived',
                            last_archived_message_index = $3,
                            version = version + 1
                        WHERE session_key = $1
                        AND version = $2
                    """, session_key, original_version, len(messages))
            return
        
        # ⚠️ 重要（Semantic Issues）: チャットログのチャンク化戦略
        # チャットログは「会話の流れ」が重要です。単純に文字数で切ると、
        # 「ユーザーの質問」と「Botの回答」が別々のチャンクに分断されるリスクがあります。
        # これにより、検索精度（質問に対する回答の適合率）が著しく低下します。
        # 
        # 改善案: 文字数分割ではなく、「メッセージ単位」または「会話のやり取り（ターン）単位」
        # でのグルーピングを推奨します。
        # 
        # 例: 「過去5メッセージ分を1つのチャンクとして、1メッセージずつずらしながら保存する
        # （スライディングウィンドウ）」手法がチャット検索には有効です。
        
        encoding = tiktoken.encoding_for_model("text-embedding-3-small")
        
        # 環境変数からチャンク化戦略を選択
        # KB_CHAT_CHUNK_STRATEGY: "message_based" (推奨) または "token_based" (従来方式)
        chunk_strategy = os.getenv("KB_CHAT_CHUNK_STRATEGY", "message_based")
        
        # ⚠️ 改善: アーカイブ対象のメッセージ（messages_to_archive）を使用
        if chunk_strategy == "message_based":
            # ⚠️ 推奨: メッセージ単位/会話ターン単位でのチャンク化
            chunks = self._chunk_messages_by_turns(
                messages_to_archive, MAX_EMBEDDING_TOKENS, encoding)
        else:
            # 従来方式: 文字数ベースの分割（フォールバック）
            # 注意: 生の会話ログ（「こんにちは」「了解です」など）はノイズが多く、
            #       ベクトル検索の精度（Semantic Search）が下がる可能性があります。
            #       将来的な改善案:
            #       1. LLMで「この会話のトピックと結論」を要約したテキストをcontentに入れる
            #       2. Hybrid Search: 生ログはそのまま保存しつつ、検索用の「キーワード」や
            #          「要約」を別カラム（またはMetadata）に持たせ、検索対象を工夫する
            content = self._format_messages_for_knowledge(messages_to_archive)
            token_count = len(encoding.encode(content))
            
            if token_count > MAX_EMBEDDING_TOKENS:
                logger.warning(
                    f"Session {session_key} exceeds token limit "
                    f"({token_count} > {MAX_EMBEDDING_TOKENS}), splitting...")
                chunks = self._split_content_by_tokens(
                    content, encoding, MAX_EMBEDDING_TOKENS)
            else:
                chunks = [content]
        
        # タイトルを生成（最初のユーザーメッセージから）
        # ⚠️ 改善: アーカイブ対象のメッセージ（messages_to_archive）を使用
        # ただし、タイトルはセッション全体から生成する方が適切な場合もあるため、
        # 必要に応じて messages 全体を使用することも検討可能
        title = self._generate_title(messages_to_archive)
        
        # URIを生成（Discord URL）
        uri = self._generate_discord_uri(session_row)
        
        # メタデータを構築
        # ⚠️ 改善（疎結合）: origin_session_id を外部キーではなく metadata に記録
        # 理由: 「短期記憶（Sessions）」と「長期記憶（Knowledge）」はライフサイクルが異なるため、
        # 外部キー制約による強い依存関係を避け、知識として独立した存在として扱う
        # これにより、「削除時の挙動」を設計する必要がなくなり、シンプルな設計になる
        session_id = session_row.get('id')  # sessions.id を取得
        session_key = session_row['session_key']  # session_key も記録（検索・デバッグ用）
        metadata = {
            "channel_id": session_row.get('channel_id'),
            "thread_id": session_row.get('thread_id'),
            "user_id": session_row.get('user_id'),
            "session_type": session_row['session_type'],
            "archived_at": datetime.now().isoformat(),
            # ⚠️ 改善（疎結合）: 紐付け情報を metadata に記録（外部キー制約なし）
            "origin_session_id": session_id,  # 検索・デバッグ用
            "origin_session_key": session_key,  # 検索・デバッグ用
        }
        
        # ⚠️ 重要: すべての操作を1つのアトミックなトランザクション内で実行
        # これにより、「知識化はされたがセッションはactiveのまま」という不整合を防ぎます
        async with self.db.pool.acquire() as conn:
            # ⚠️ 重要: トランザクション分離レベルを REPEATABLE READ に設定（楽観的ロックのため）
            # asyncpgでの設定方法: conn.transaction(isolation='repeatable_read') を使用
            # これにより、トランザクション開始時点のスナップショットが保持され、
            # 他のトランザクションによる更新が可視化されないため、楽観的ロックの競合検出が正確に動作します
            async with conn.transaction(isolation='repeatable_read'):
                # 1. knowledge_sources に登録（status='pending'）
                # ⚠️ 注意: JSONBコーデックが設定されていれば、dictを直接渡せる
                # datetimeが含まれる場合は、事前にISO文字列に変換する
                # ⚠️ 改善（疎結合）: origin_session_id カラムは削除し、metadata に記録
                source_id = await conn.fetchval("""
                    INSERT INTO knowledge_sources (type, title, uri, metadata, status)
                    VALUES ($1, $2, $3, $4::jsonb, 'pending')
                    RETURNING id
                """,
                'discord_session', title, uri, metadata)
                
                # 2. knowledge_chunks に登録（複数チャンクに対応）
                # ⚠️ 重要: locationには共通インターフェース（url, label）を含める
                for i, chunk_content in enumerate(chunks):
                    chunk_token_count = len(encoding.encode(chunk_content))
                    # locationの構造: 共通インターフェース（url, label）を含める
                    location = {
                        "url": uri,  # 共通インターフェース: チャンクへの直接リンク
                        "label": f"チャンク {i+1}/{len(chunks)}",
                        # 共通インターフェース: 表示ラベル
                        "session_key": session_key,
                        "chunk_index": i,
                        "total_chunks": len(chunks)
                    }
                    await conn.execute("""
                        INSERT INTO knowledge_chunks
                        (source_id, content, embedding, location, token_count)
                        VALUES ($1, $2, NULL, $3::jsonb, $4)
                    """, source_id, chunk_content, location, chunk_token_count)
                
                # 3. sessions の status を 'archived' に更新（楽観的ロック）
                # ⚠️ 重要: last_active_at が変更されていない場合のみ更新（競合状態対策）
                # ⚠️ 改善（競合状態対策）: アーカイブ処理中に新しいメッセージが来た場合の処理
                # エッジケース: アーカイブ処理が走っている最中（トランザクション中）に、
                # ユーザーから新しいメッセージが来て sessions テーブルが更新された場合、
                # 現在の設計（楽観ロック）ではアーカイブが失敗してリトライになりますが、
                # その間に新しいメッセージが追加されているため、「アーカイブ漏れ（最新メッセージが含まれない知識）」
                # が発生する可能性があります。
                # 
                # 対策: アーカイブ処理完了時は、単にステータスを変えるだけでなく、
                # 「アーカイブ済み地点（message index や timestamp）」を記録し、
                # それ以降のメッセージがあれば別セッションとして扱うか、差分アーカイブするロジックが必要です。
                # 
                # 実装方針:
                # 1. アーカイブ時に messages のインデックス（または最後のメッセージのタイムスタンプ）を記録
                # 2. アーカイブ後に新しいメッセージが追加された場合、差分を検出
                # 3. 差分がある場合は、追加分のみを別のチャンクとしてアーカイブ（差分アーカイブ）
                # または、新しいセッションとして扱う
                # 
                # 今回は初回実装のため、楽観的ロックによるリトライで対応し、
                # 将来的に差分アーカイブ機能を追加することを推奨します。
                # 
                # アーカイブ済み地点を記録（将来の差分アーカイブ用）
                archived_message_count = len(messages)
                # 最後のメッセージのタイムスタンプを取得（存在する場合）
                archived_until_timestamp = None
                if messages:
                    last_msg = messages[-1]
                    # メッセージに timestamp フィールドがある場合
                    archived_until_timestamp = last_msg.get('timestamp')
                    # timestamp がない場合は created_at を使用（フォールバック）
                    if not archived_until_timestamp:
                        archived_until_timestamp = last_msg.get('created_at')
                
                # metadata にアーカイブ済み地点を記録（将来の差分アーカイブ用）
                metadata['archived_message_count'] = archived_message_count
                if archived_until_timestamp:
                    metadata['archived_until_timestamp'] = archived_until_timestamp
                
                # knowledge_sources の metadata を更新（アーカイブ済み地点を記録）
                await conn.execute("""
                    UPDATE knowledge_sources
                    SET metadata = $1::jsonb
                    WHERE id = $2
                """, metadata, source_id)
                
                # UPDATE が 0 件の場合は、トランザクション全体がロールバックされる
                # ⚠️ 改善（データ整合性）: versionカラムを使用した楽観的ロック
                # TIMESTAMPTZの精度（マイクロ秒）で競合検出に依存していると、
                # 同一マイクロ秒内の更新で誤検知の可能性（極めて稀だが理論上あり得る）
                # versionカラム（INT、更新ごとにインクリメント）を使用する方が堅牢です
                original_version = session_row.get('version', 1)
                
                # ⚠️ 改善（会話の分断対策）: スライディングウィンドウ（のりしろ）方式
                # アーカイブ処理が走り、データが長期記憶へ移動した直後にユーザーが発言すると、
                # 直前の文脈が短期記憶から消えているため、Botが「何の話でしたっけ？」となってしまう現象を防ぐ。
                # 
                # 改善策: アーカイブ時に短期記憶を「全消去」するのではなく、
                # 「直近の数メッセージ（のりしろ）」を残して更新（Prune）する設計にします。
                # 
                # データフロー:
                # 1. READ: 対象セッションの全メッセージを取得（既に取得済み: messages_to_archive）
                # 2. INSERT (長期記憶): 全メッセージを
                # knowledge_sources / knowledge_chunks に保存（既に実行済み）
                # 3. UPDATE (短期記憶): messages カラムを「後ろからN件（例: 5件）」に切り詰めて更新
                # 
                # これにより、「時間が経てば整理されるが、ユーザーが戻ってきても直近の文脈は繋がる」
                # という、人間にとって自然な記憶構造を実現できます。
                
                # 環境変数から「のりしろ」の件数を取得（デフォルト: 5件）
                KB_ARCHIVE_OVERLAP_MESSAGES = int(
                    os.getenv("KB_ARCHIVE_OVERLAP_MESSAGES", "5"))
                
                # アーカイブ済み地点を計算
                new_archived_index = current_archived_index + len(messages_to_archive)
                
                # すべてのメッセージがアーカイブ済みかどうかを判定
                all_messages_archived = new_archived_index >= len(messages)
                
                if all_messages_archived:
                    # すべてのメッセージがアーカイブ済みの場合
                    # ⚠️ 改善: のりしろ方式を適用（最後のN件を残す）
                    # メッセージがのりしろ件数より少ない場合は、すべて残す
                    overlap_messages = (
                        messages[-KB_ARCHIVE_OVERLAP_MESSAGES:]
                        if len(messages) > KB_ARCHIVE_OVERLAP_MESSAGES
                        else messages
                    )
                    
                    # ⚠️ 重要（Critical Bug Fix）: messages配列を切り詰めたら、
                    # last_archived_message_index は 0 にリセット
                    # 理由: 配列を切り詰めるとインデックスがリセットされる（0〜N-1）ため、
                    # 通算インデックスを保持すると次回アーカイブ時に範囲外アクセスが発生する
                    # 例: 100件の配列を5件に切り詰めた場合、配列は[0,1,2,3,4]になるが、
                    # last_archived_message_index=100のままでは次回
                    # messages[100:] で範囲外アクセスになる
                    reset_index = 0
                    
                    # status='archived' に更新し、messages をのりしろ分だけ残す
                    # ⚠️ 重要（楽観的ロック）: WHERE句でversionをチェックし、競合を検出
                    result = await conn.execute("""
                        UPDATE sessions
                        SET status = 'archived',
                            messages = $3::jsonb,
                            last_archived_message_index = $4,
                            version = version + 1
                        WHERE session_key = $1
                        AND status = 'active'
                        AND version = $2
                    """,
                        session_key,
                        original_version,
                        overlap_messages,
                        reset_index
                    )
                else:
                    # 一部のみアーカイブ済みの場合
                    # ⚠️ 改善: のりしろ方式を適用（アーカイブ済み部分を除き、最後のN件を残す）
                    # アーカイブ済み部分を除いた残りのメッセージから、最後のN件を取得
                    remaining_messages = messages[new_archived_index:]
                    overlap_messages = (
                        remaining_messages[-KB_ARCHIVE_OVERLAP_MESSAGES:]
                        if len(remaining_messages) > KB_ARCHIVE_OVERLAP_MESSAGES
                        else remaining_messages
                    )
                    
                    # ⚠️ 重要（Critical Bug Fix）: messages配列を切り詰めたら、
                    # last_archived_message_index は 0 にリセット
                    # 理由: 配列を切り詰めるとインデックスがリセットされる（0〜N-1）ため、
                    # 通算インデックスを保持すると次回アーカイブ時に範囲外アクセスが発生する
                    # のりしろ分は「未アーカイブ扱い」として扱い、次回アーカイブ時に重複チェックで弾く設計
                    reset_index = 0
                    
                    # last_archived_message_index のみ更新（statusは'active'のまま）
                    # messages をのりしろ分だけ残す（アーカイブ済み部分は削除）
                    # ⚠️ 重要（楽観的ロック）: WHERE句でversionをチェックし、競合を検出
                    result = await conn.execute("""
                        UPDATE sessions
                        SET messages = $3::jsonb,
                            last_archived_message_index = $4,
                            version = version + 1
                        WHERE session_key = $1
                        AND status = 'active'
                        AND version = $2
                    """,
                        session_key,
                        original_version,
                        overlap_messages,
                        reset_index
                    )
                
                # asyncpgのexecuteは "UPDATE N" 形式の文字列を返す
                if result == "UPDATE 0":
                    # セッションが他のプロセスによって更新された場合、トランザクション全体をロールバック
                    # ⚠️ 重要: 例外を発生させることで、asyncpgのトランザクションコンテキストマネージャーが
                    # 自動的にロールバックを実行します。これにより、
                    # knowledge_sources と knowledge_chunks への INSERT も
                    # 取り消され、データの不整合を防ぎます。
                    # 
                    # ⚠️ 改善: last_archived_message_index を使用することで、
                    # 高頻度でチャットが続く場合でも、確定した過去部分だけをアーカイブでき、
                    # リトライループに陥ることを防げます。
                    logger.warning(
                        f"Session {session_key} was updated during archiving, "
                        f"rolling back transaction to prevent duplicate "
                        f"archive (will retry)")
                    # ⚠️ 重要: ValueError を発生させ、tenacity による自動リトライをトリガー
                    # これにより、Botが高頻度で使われている場合でも、アーカイブが成功する可能性が高まります
                    # ただし、last_archived_message_index を使用することで、
                    # リトライ時には新しいメッセージが追加されていても、確定した過去部分だけを
                    # アーカイブできるため、リトライループに陥る可能性が大幅に低減されます
                    raise ValueError(
                        f"Session {session_key} was concurrently updated, "
                        f"archiving aborted to prevent duplicate")
        
        # トランザクションが正常にコミットされた場合のみ、このログが出力されます
        logger.info(
            f"Archived session {session_key} as knowledge source {source_id} "
            f"({len(chunks)} chunks)")
    
    def _should_archive_session(self, messages: list[dict]) -> bool:
        """セッションをアーカイブすべきか判定（フィルタリング）"""
        # 文字数チェック
        total_length = sum(len(msg.get('content', '')) for msg in messages)
        if total_length < MIN_SESSION_LENGTH:
            return False
        
        # Botのみのセッションを除外（ユーザー発言がない）
        has_user_message = any(msg.get('role') == 'user' for msg in messages)
        if not has_user_message:
            return False
        
        return True
    
    def _format_messages_for_knowledge(
        self, messages: list[dict]
    ) -> str:
        """メッセージを知識ベース用のテキストに整形"""
        formatted = []
        for msg in messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            formatted.append(f"{role.capitalize()}: {content}")
        return "\n".join(formatted)
    
    def _chunk_messages_by_turns(
        self, messages: list[dict], max_tokens: int, encoding: tiktoken.Encoding
    ) -> list[str]:
        """メッセージを会話のターン単位でチャンク化
        
        ⚠️ 重要（Semantic Issues）: チャットログは「会話の流れ」が重要です。
        単純に文字数で切ると、「ユーザーの質問」と「Botの回答」が別々のチャンクに
        分断されるリスクがあります。これにより、検索精度（質問に対する回答の適合率）が
        著しく低下します。
        
        改善案: 文字数分割ではなく、「メッセージ単位」または「会話のやり取り（ターン）単位」
        でのグルーピングを推奨します。
        
        例: 「過去5メッセージ分を1つのチャンクとして、1メッセージずつずらしながら保存する
        （スライディングウィンドウ）」手法がチャット検索には有効です。
        
        Args:
            messages: メッセージのリスト（各要素は {'role': str, 'content': str}）
            max_tokens: 1チャンクあたりの最大トークン数
            encoding: tiktokenエンコーディング
        
        Returns:
            チャンク化されたテキストのリスト
        """
        # 環境変数からチャンクサイズ（メッセージ数）を取得
        # デフォルト: 5メッセージ（ユーザー質問 + Bot回答の1ターン + 前後の文脈）
        chunk_size_messages = int(os.getenv("KB_CHAT_CHUNK_SIZE_MESSAGES", "5"))
        # スライディングウィンドウのオーバーラップ（メッセージ数）
        # デフォルト: 2メッセージ（前のチャンクの最後2メッセージを次のチャンクの最初に含める）
        overlap_messages = int(os.getenv("KB_CHAT_CHUNK_OVERLAP_MESSAGES", "2"))
        
        chunks = []
        i = 0
        
        while i < len(messages):
            # 現在のチャンクに含めるメッセージを取得
            chunk_messages = messages[i:i + chunk_size_messages]
            
            # チャンクをテキストに整形
            chunk_text = self._format_messages_for_knowledge(chunk_messages)
            chunk_tokens = len(encoding.encode(chunk_text))
            
            # トークン数が上限を超えている場合、メッセージ数を減らす
            if chunk_tokens > max_tokens:
                # メッセージ数を減らしながら再試行
                reduced_size = max(1, chunk_size_messages - 1)
                chunk_messages = messages[i:i + reduced_size]
                chunk_text = self._format_messages_for_knowledge(chunk_messages)
                chunk_tokens = len(encoding.encode(chunk_text))
                
                # それでも超える場合は、RecursiveCharacterTextSplitterにフォールバック
                if chunk_tokens > max_tokens:
                    logger.warning(
                        f"Chunk exceeds token limit "
                        f"({chunk_tokens} > {max_tokens}), "
                        f"falling back to RecursiveCharacterTextSplitter"
                    )
                    # フォールバック: 文字数ベースの分割
                    sub_chunks = self._split_content_by_tokens(
                        chunk_text, encoding, max_tokens)
                    chunks.extend(sub_chunks)
                    # 次のチャンクへ（オーバーラップなし）
                    i += reduced_size
                    continue
            
            chunks.append(chunk_text)
            
            # スライディングウィンドウ: オーバーラップ分だけ進む
            # 例: chunk_size=5, overlap=2 の場合、3メッセージ進む
            i += max(1, chunk_size_messages - overlap_messages)
        
        return chunks
    
    def _split_content_by_tokens(
        self, content: str, encoding: tiktoken.Encoding, max_tokens: int
    ) -> list[str]:
        """コンテンツをトークン数上限に基づいて分割
        
        ⚠️ 重要: 自前実装は複雑でバグが発生しやすいため、
        langchain-text-splitters の使用を強く推奨します。
        
        このメソッドは、langchain-text-splitters が利用できない場合のフォールバック実装です。
        """
        # ⚠️ 推奨: langchain-text-splitters を使用する実装
        try:
            from langchain_text_splitters import RecursiveCharacterTextSplitter
            
            overlap_ratio = float(
                os.getenv("KB_CHUNK_OVERLAP_RATIO", "0.2"))
            
            splitter = RecursiveCharacterTextSplitter(
                # ⚠️ 重要: max_tokens=4000 は、OpenAI text-embedding-3-small の
                # 推奨入力長（8191トークン）の約半分。これにより、API呼び出しの
                # 効率と検索精度のバランスを取る
                chunk_size=max_tokens,
                chunk_overlap=int(max_tokens * overlap_ratio),
                length_function=lambda text: len(encoding.encode(text)),
                separators=['\n\n', '\n', '。', '.', '、', ',', ' ', ''],
            )
            return splitter.split_text(content)
        except ImportError:
            # フォールバック: 自前実装（簡易版）
            logger.warning(
                "langchain-text-splitters not available, "
                "using fallback implementation")
            return self._split_content_by_tokens_fallback(
                content, encoding, max_tokens)
    
    def _split_content_by_tokens_fallback(
        self, content: str, encoding: tiktoken.Encoding, max_tokens: int
    ) -> list[str]:
        """フォールバック実装（簡易版）"""
        tokens = encoding.encode(content)
        if len(tokens) <= max_tokens:
            return [content]
        
        chunks = []
        start = 0
        # ⚠️ 重要: マジックナンバーを避けるため、環境変数から読み込む
        # 理由: 0.2 (20%) は、チャンク間の文脈を保持するための適切なオーバーラップ比率
        # これにより、チャンク境界での情報の欠落を防ぐ
        overlap_ratio = float(os.getenv("KB_CHUNK_OVERLAP_RATIO", "0.2"))
        overlap_tokens = int(max_tokens * overlap_ratio)
        
        while start < len(tokens):
            end = min(start + max_tokens, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk_text = encoding.decode(chunk_tokens)
            
            if end >= len(tokens):
                chunks.append(chunk_text)
                break
            
            # 簡易分割: 改行や句読点で分割を試みる
            separators = ['\n\n', '\n', '。', '.', '、', ',']
            best_split_pos = len(chunk_text)
            
            for separator in separators:
                pos = chunk_text.rfind(separator)
                if pos > len(chunk_text) * 0.5:
                    best_split_pos = pos + len(separator)
                    break
            
            final_chunk = chunk_text[:best_split_pos].strip()
            if final_chunk:
                chunks.append(final_chunk)
            
            # オーバーラップを考慮して次の開始位置を計算
            if best_split_pos > overlap_tokens:
                # オーバーラップ分を戻る
                overlap_text = chunk_text[
                    best_split_pos - overlap_tokens:best_split_pos]
                overlap_tokens_count = len(encoding.encode(overlap_text))
                start = (
                    start + len(encoding.encode(final_chunk))
                    - overlap_tokens_count)
            else:
                start = start + len(encoding.encode(final_chunk))
        
        return chunks
    
    def _generate_title(self, messages: list[dict]) -> str:
        """セッションのタイトルを生成"""
        # 最初のユーザーメッセージから生成
        for msg in messages:
            if msg.get('role') == 'user':
                content = msg.get('content', '')
                # 最初の50文字をタイトルに
                title = content[:50].strip()
                if len(content) > 50:
                    title += "..."
                return title or "Discord Session"
        return "Discord Session"
    
    def _generate_discord_uri(self, session_row: dict) -> str | None:
        """Discord URLを生成
        （正しい形式: /channels/{guild_id}/{channel_id}/{message_id}）"""
        channel_id = session_row.get('channel_id')
        thread_id = session_row.get('thread_id')
        guild_id = session_row.get('guild_id')  # sessionsテーブルに追加済み
        
        if not channel_id:
            return None
        
        # Guild IDがない場合は、チャンネルIDのみの形式（不完全だが動作する）
        if guild_id:
            if thread_id:
                return (
                    f"https://discord.com/channels/{guild_id}/"
                    f"{channel_id}/{thread_id}")
            else:
                return f"https://discord.com/channels/{guild_id}/{channel_id}"
        else:
            # フォールバック: Guild IDがない場合（将来的に修正が必要）
            logger.warning(
                f"Guild ID not found for session, using incomplete URL")
            if thread_id:
                return f"https://discord.com/channels/{channel_id}/{thread_id}"
            else:
                return f"https://discord.com/channels/{channel_id}"
    
    async def graceful_shutdown(self):
        """Graceful Shutdown: 処理中のタスクが完了するまで待機
        
        ⚠️ 改善（コード品質）: session_archiverのGraceful Shutdownが
        embedding_processorほど詳細に定義されていませんでした。
        以下の改善を追加します:
        - 処理中のアーカイブタスクの完了待機
        - タイムアウト処理
        - エラーハンドリング
        """
        logger.info("Stopping session archiver gracefully...")
        
        # タスクをキャンセル
        self.archive_inactive_sessions.cancel()
        
        # 処理中のタスクが完了するまで待機
        try:
            # タスクが存在する場合、完了を待つ
            task = getattr(self.archive_inactive_sessions, '_task', None)
            if task and not task.done():
                try:
                    from asyncio import timeout
                    # 最大60秒待機
                    # （アーカイブ処理は時間がかかる可能性があるため）
                    async with timeout(60.0):
                        await task
                except TimeoutError:
                    logger.warning(
                        "Session archiving task did not complete "
                        "within timeout")
                except asyncio.CancelledError:
                    logger.debug("Session archiving task was cancelled")
            
            # ⚠️ 改善: 処理中のアーカイブ処理（_archive_session）の完了待機
            # 複数のセッションを並列処理している場合、すべての処理が完了するまで待機
            if hasattr(self, '_processing_sessions') and self._processing_sessions:
                logger.info(
                    f"Waiting for {len(self._processing_sessions)} "
                    f"active archive tasks to complete...")
                try:
                    from asyncio import timeout, gather
                    async with timeout(120.0):  # 最大120秒待機（並列処理の場合）
                        await gather(*self._processing_sessions, return_exceptions=True)
                except TimeoutError:
                    logger.warning(
                        "Some archive tasks did not complete within timeout")
                except Exception as e:
                    logger.error(
                        f"Error waiting for archive tasks: {e}",
                        exc_info=True)
        except Exception as e:
            logger.error(f"Error during graceful shutdown: {e}", exc_info=True)
        
        logger.info("Session archiver stopped")
```

**完了基準**:

- [ ] `SessionArchiver` クラスが実装されている
- [ ] 非アクティブなセッションが自動的に知識ベースに変換される
- [ ] セッションのstatusが'archived'に更新される
- [ ] ⚠️ **重要**: `_archive_session` メソッドで、`knowledge_sources` への
  INSERT、`knowledge_chunks` への INSERT、`sessions` の UPDATE が
  **同一のアトミックなトランザクション内**で実行されている
  （データ不整合の防止）
- [ ] トランザクション分離レベルが `REPEATABLE READ` に設定されている（楽観的ロックのため）
- [ ] セッションが同時更新された場合、トランザクション全体がロールバックされ、知識ベースへの登録も取り消される（例外処理による自動ロールバック）
- [ ] トークン数チェックと分割処理が実装されている
- [ ] Recursive Character Splitter方式によるテキスト分割が実装されている（句読点・改行を優先）
- [ ] `langchain-text-splitters` の導入前提を理解し、実装に使用している
- [ ] 楽観的ロックによる競合状態対策が実装されている（`last_active_at` のチェック）
- [ ] フィルタリングロジック（短いセッション、Botのみのセッション除外）が実装されている
- [ ] `token_count` カラムが正しく保存されている
- [ ] Graceful Shutdownが実装されている（処理中のタスクが完了するまで待機）

### Step 6: Docker Compose の更新 (1日)

#### 6.1 docker-compose.yml の更新

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
    
    depends_on:
      postgres:
        condition: service_healthy
    
    environment:
      # アプリケーション固有の設定上書きが必要なら記述
      - TZ=Asia/Tokyo
    
    volumes:
      # 注意: PostgreSQLに移行したため、SQLite用の ./data:/app/data マウントは不要になりました
      # - ./data:/app/data  # ← この行を削除またはコメントアウト
      - ./logs:/app/logs
      # backupsフォルダ: PostgreSQLのpg_dumpバックアップファイルを保存
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

  postgres:
    # ⚠️ 重要（本番環境の推奨）: PostgreSQL 18は2025年Q3（秋）リリース予定で、運用実績が限定的
    # pgvector 0.8.1 との組み合わせの本番実績が少ないため、本番環境ではPostgreSQL 17を推奨
    # 開発・検証環境: pgvector/pgvector:0.8.1-pg18
    # 本番環境推奨: pgvector/pgvector:0.8.0-pg17
    image: pgvector/pgvector:0.8.1-pg18  # 開発・検証用（本番は0.8.0-pg17を推奨）
    container_name: kotonoha-postgres
    restart: unless-stopped
    env_file:
      - .env
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-kotonoha}
      POSTGRES_USER: ${POSTGRES_USER:-kotonoha}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      # ⚠️ 改善（パフォーマンス）: HNSWのビルドコストと maintenance_work_mem
      # インデックス構築時（INSERT/UPDATE時）とリストア時にOOM Killerが発動する可能性があります。
      # NASのメモリが少ない場合、大量のデータを COPY や INSERT した直後のインデックス構築で
      # OOM Killerが発動し、Postgresプロセスが落ちる可能性があります。
      # docker-compose.yml または postgresql.conf で maintenance_work_mem を制限してください。
      # 例: NASのメモリが4GBなら、256MB〜512MB程度に抑える
      # デフォルトのままだと危険な場合があります。
      # ⚠️ 重要: maintenance_work_mem を制限（OOM Killer対策）
      # システムメモリの10〜20%程度（最小128MB、最大1GB）
      # 例: NASのメモリが4GBなら、256MB〜512MB程度に抑える
      # 注意: POSTGRES_INITDB_ARGS は初期化時のみ有効。実行時の設定変更には postgresql.conf が必要
      # 実行時の設定変更方法:
      # 1. カスタム postgresql.conf をマウント（推奨）
      # 2. docker exec で ALTER SYSTEM SET を使用
      POSTGRES_INITDB_ARGS: >
        --maintenance-work-mem=256MB
    volumes:
      # ⚠️ 重要: Synology NAS特有の権限問題対策
      # 名前付きボリューム（postgres_data）を使用することで、権限問題を回避します。
      # バインドマウント（./data:/var/lib/postgresql/data）を使用すると、
      # ホスト側のフォルダ権限とコンテナ内のユーザー（postgres: uid 999 999等）が一致せず、
      # Permission Denied エラーが頻発します。
      # バックアップは pg_dump で外部に出せば十分なので、データ領域は名前付きボリュームのままにします。
      - postgres_data:/var/lib/postgresql/data
      # バックアップスクリプト用マウント（必要に応じて）
      # ⚠️ 注意: バインドマウントを使用する場合、権限問題が発生する可能性があります。
      # 推奨: docker exec + docker cp を使用したバックアップスクリプト（権限問題を完全に回避）
      # 詳細は「6.2 データの永続化とバックアップ戦略」セクションを参照してください。
      # Synology NASのHyper Backup対象フォルダにマウントする場合の例:
      # - /volume1/docker/kotonoha/backups:/backups
    networks:
      - kotonoha-network
    deploy:
      resources:
        limits:
          # ⚠️ メモリ設定: HNSW インデックスはメモリを多く使用します。
          # pg_dump 実行時にも一時的にメモリ使用量が跳ねることがあります。
          # NAS全体のメモリによりますが、Bot本体のメモリを削ってでも
          # Postgresには余裕を持たせたほうが安定します。
          # halfvec の採用は非常に賢明です（メモリ使用量が約半分になります）。
          memory: ${POSTGRES_MEM_LIMIT:-1G}
        reservations:
          memory: ${POSTGRES_MEM_RESERVATION:-512M}
    # 注意: pgvector（特にHNSWインデックス）はメモリを多く使用します。
    # データ量が増えるとスワップが発生する可能性があるため、
    # docker stats で監視し、必要に応じてメモリ制限を調整してください。
    # 
    # ⚠️ 改善（パフォーマンス）: HNSWのビルドコストと maintenance_work_mem
    # POSTGRES_INITDB_ARGS は初期化時のみ有効です。
    # 実行時の設定変更には postgresql.conf の設定が必要です。
    # 
    # 方法1: カスタム postgresql.conf をマウント（推奨）
    # volumes:
    #   - ./postgresql.conf:/etc/postgresql/postgresql.conf
    # command: postgres -c config_file=/etc/postgresql/postgresql.conf
    # 
    # 方法2: docker exec で ALTER SYSTEM SET を使用
    # docker exec kotonoha-postgres psql -U kotonoha -c \
    #   "ALTER SYSTEM SET maintenance_work_mem = '256MB';"
    # docker exec kotonoha-postgres psql -U kotonoha -c \
    #   "SELECT pg_reload_conf();"
    # 
    # postgresql.conf の設定例:
    # maintenance_work_mem = 256MB  # システムメモリの10〜20%程度（最小128MB、最大1GB）
    healthcheck:
      test: [
        "CMD-SHELL",
        "pg_isready -U ${POSTGRES_USER:-kotonoha} "
        "-d ${POSTGRES_DB:-kotonoha}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s

  pgadmin:
    image: dpage/pgadmin4:latest
    container_name: kotonoha-pgadmin
    restart: unless-stopped
    # セキュリティ: profiles 機能を使用して、必要な時だけ起動
    # 通常は起動せず、docker-compose --profile admin up -d と打った時だけ起動
    # メモリ節約（約200-500MB）とセキュリティ向上のため強く推奨
    profiles: ["admin"]
    env_file:
      - .env
    environment:
      PGADMIN_DEFAULT_EMAIL: ${PGADMIN_EMAIL}
      PGADMIN_DEFAULT_PASSWORD: ${PGADMIN_PASSWORD}
      # ⚠️ 改善（セキュリティ）: pgAdminの常時起動リスクを改善
      # Server Mode がオフだとマルチユーザー認証が無効化されるため、本番では True にする
      # 開発環境では False でも問題ないが、本番環境では必ず True に設定すること
      PGADMIN_CONFIG_SERVER_MODE: 'True'  # 本番では True（マルチユーザー認証を有効化）
      # セキュリティ: 本番環境では必ずマスターパスワードを要求する
      PGADMIN_CONFIG_MASTER_PASSWORD_REQUIRED: 'True'
      # ⚠️ 改善（セキュリティ）: 追加のセキュリティ設定
      PGADMIN_CONFIG_ENHANCED_COOKIE_PROTECTION: 'True'  # クッキー保護を強化
      PGADMIN_CONFIG_LOGIN_BANNER: '"Authorized Access Only"'  # ログインバナーを表示
    ports:
      - "${PGADMIN_PORT:-5050}:80"
    volumes:
      - pgadmin_data:/var/lib/pgadmin
    networks:
      - kotonoha-network
    depends_on:
      - postgres
    deploy:
      resources:
        limits:
          memory: 512M

volumes:
  postgres_data:
  pgadmin_data:

networks:
  kotonoha-network:
    driver: bridge
```

**注意**: 上記の構成は**複数コンテナ構成**です（kotonoha-bot、postgres、pgadminの3つのコンテナ）。

**既存のdocker-compose.ymlを更新する際の注意点**:

**重要**: このフェーズは**新規設計**のため、SQLiteからの移行ツールは作成せず、既存のデータは破棄します。

以下の変更が必要です：

1. **`./data:/app/data` マウントの削除**: SQLiteのデータベースファイルは
   不要になったため、このマウントを削除またはコメントアウトしてください。
   - 以前: `- ./data:/app/data` （SQLite用）
   - 現在: 削除（PostgreSQLは別コンテナで管理）

2. **既存の`data`フォルダの扱い**:
   - **新規設計のため、既存のSQLiteデータベースファイル（`data/*.db`など）は破棄します。**
   - 移行ツールは作成しません。
   - `data`フォルダは削除しても問題ありません（ただし、他の用途で使用している場合は除く）。

3. **`backups`フォルダの扱い**:
   - `./backups:/app/backups`のマウントは**引き続き必要**です。
   - 用途が変更されます：
     - **以前**: SQLiteのバックアップファイル（`.db.gz`）を保存
     - **現在**: PostgreSQLの`pg_dump`バックアップファイル（`.sql`または`.dump`）を保存
   - **既存のSQLiteバックアップファイル（`kotonoha_*.db.gz`）は削除しても問題ありません。**
   - `scripts/backup.sh`はPostgreSQL用に更新する必要があります（`pg_dump`を使用）。
   - ⚠️ **重要**: バインドマウントの権限問題対策が必要です。詳細は「6.2 データの永続化とバックアップ戦略」セクションを参照してください。
     - 推奨: `docker exec` + `docker cp` を使用したバックアップスクリプト（権限問題を完全に回避）
     - 代替: ホスト側で `chmod 777 ./backups` または適切なオーナー設定

4. **PostgreSQLコンテナの追加**: `postgres`サービスと`pgadmin`サービスを追加してください。

5. **環境変数の追加**: `DATABASE_URL`と`POSTGRES_PASSWORD`を環境変数に追加してください。

**単一コンテナ構成が必要な場合**:

PostgreSQLをBotコンテナに含めることも可能ですが、以下の理由から**推奨されません**：

1. **データの永続化**: PostgreSQLのデータファイルを適切に管理する必要がある
2. **スケーラビリティ**: BotとDBを分離することで、それぞれ独立にスケールできる
3. **メンテナンス性**: コンテナの再起動や更新が容易
4. **リソース管理**: メモリやCPUのリソースを個別に制限できる

**推奨構成**: 複数コンテナ構成を維持し、必要に応じてpgAdminを削除する。

#### 6.2 データの永続化とバックアップ戦略

> **参照**: 詳細なバックアップ戦略については、
> [PostgreSQL スキーマ設計書 - 14. バックアップ戦略](../architecture/postgresql-schema-design.md#14-バックアップ戦略)
> を参照してください。

**重要**: SQLiteのように「ファイルをコピーすれば終わり」ではありません。PostgreSQLは適切なバックアップ戦略が必要です。

**推奨バックアップ方法の概要**:

1. **pg_dump による定期バックアップ**: カスタムフォーマット（圧縮済み）を使用
2. **自動バックアップスクリプト**: cron等で定期実行
3. **Synology Hyper Backup との連携**: `pg_dump`の結果をNASの別フォルダに出力

##### ⚠️ 重要: バックアップとリストアの整合性

- **pg_dump は論理バックアップです**
- **pgvector のデータは復元されますが、インデックスの再構築がリストア時に走るため、リストア時間が非常に長くなる可能性があります**
- HNSWインデックス（`idx_chunks_embedding`）は、データ量に応じて構築時間が増加します
- **10万件を超えるデータの場合、インデックス再構築に数時間かかる可能性があります**

**対策**:

1. **小規模データ（〜10万件）**:
   - `pg_dump` による論理バックアップで十分
   - リストア後のインデックス再構築時間を許容範囲として計算に入れておく

2. **大規模データ（10万件超）**:
   - **物理バックアップ（WALアーカイブなど）を検討する**
   - ファイルシステムレベルのバックアップ（`pg_basebackup`）
   - リストア時間が大幅に短縮される

詳細については、[PostgreSQL スキーマ設計書 - 14. バックアップ戦略](../architecture/postgresql-schema-design.md#14-バックアップ戦略)を参照してください。

##### ⚠️ 重要: バックアップ出力先の権限問題対策

**問題**: `./backups` ディレクトリはバインドマウント
（`./backups:/app/backups`）のため、コンテナ内の `postgres` ユーザー
（通常 UID 999）がホスト側のディレクトリに書き込めない場合があります。

**解決方法**:

###### 方法 1: ホスト側ディレクトリの権限設定（推奨）

```bash
# バックアップディレクトリを作成
mkdir -p ./backups

# 方法 1a: 全ユーザーに書き込み権限を付与（簡易だがセキュリティリスクあり）
chmod 777 ./backups

# 方法 1b: 適切なオーナー設定（より安全）
# postgres コンテナ内の UID/GID を確認
docker exec kotonoha-postgres id postgres
# 例: uid=999(postgres) gid=999(postgres) groups=999(postgres)

# ホスト側で同じ UID/GID にオーナーを変更
sudo chown -R 999:999 ./backups
chmod 755 ./backups
```

###### 方法 2: docker exec + docker cp による回避テクニック（推奨）

コンテナ内の `/tmp` に一時ファイルとして出力し、`docker cp` でホストにコピーする方法です。権限問題を完全に回避できます。

```bash
#!/bin/bash
# scripts/backup_postgres.sh
# PostgreSQL バックアップスクリプト（権限問題回避版）

set -e

CONTAINER_NAME="kotonoha-postgres"
DB_NAME="${POSTGRES_DB:-kotonoha}"
DB_USER="${POSTGRES_USER:-kotonoha}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="./backups"
BACKUP_FILE="kotonoha_${TIMESTAMP}.dump"

# バックアップディレクトリの作成（ホスト側）
mkdir -p "${BACKUP_DIR}"

# コンテナ内の /tmp にバックアップを作成（権限問題なし）
echo "Creating backup in container..."
docker exec "${CONTAINER_NAME}" pg_dump \
  -U "${DB_USER}" \
  -F c \
  -f "/tmp/${BACKUP_FILE}" \
  "${DB_NAME}"

# コンテナからホストにコピー（権限問題なし）
echo "Copying backup to host..."
docker cp "${CONTAINER_NAME}:/tmp/${BACKUP_FILE}" "${BACKUP_DIR}/${BACKUP_FILE}"

# コンテナ内の一時ファイルを削除
docker exec "${CONTAINER_NAME}" rm "/tmp/${BACKUP_FILE}"

# バックアップサイズの表示
BACKUP_SIZE=$(du -h "${BACKUP_DIR}/${BACKUP_FILE}" | cut -f1)
echo "Backup completed: ${BACKUP_DIR}/${BACKUP_FILE} (${BACKUP_SIZE}))"

# 古いバックアップの削除（7日以上前）
RETENTION_DAYS=7
echo "Cleaning up old backups (older than ${RETENTION_DAYS} days)..."
find "${BACKUP_DIR}" -name "kotonoha_*.dump" -mtime +${RETENTION_DAYS} -delete

echo "Backup process completed."
```

**この方法のメリット**:

- 権限問題を完全に回避（コンテナ内の `/tmp` は postgres ユーザーが書き込み可能）
- ホスト側のディレクトリ権限設定が不要
- `docker cp` は root 権限で実行されるため、ホスト側への書き込みも問題なし

**推奨**: 方法 2（docker exec + docker cp）を推奨します。最も確実で、権限問題を完全に回避できます。

詳細なバックアップスクリプトの実装例については、上記の設計書を参照してください。

#### 6.3 データベース・パフォーマンス設計（Synology NASへの最適化）

> **参照**: 詳細なパフォーマンス設計については、
> [PostgreSQL スキーマ設計書 - 17.3 データベース・パフォーマンス設計（Synology NASへの最適化）](../architecture/postgresql-schema-design.md#173-データベースパフォーマンス設計synology-nasへの最適化)
> を参照してください。

**halfvecの採用**:

pgvector 0.7.0以降では、`halfvec` (float16) 型がサポートされています。
これを使用するとストレージとメモリ使用量が半分になります。

**メリット**:

- **メモリ使用量の削減**: `vector(1536)`はfloat32を使用するため、
  1ベクトルあたり約6KB消費します。10万件で約600MBのインデックスサイズに
  なります。`halfvec(1536)`を使用すると約300MBに削減されます。
- **精度への影響**: OpenAIのEmbedding精度への影響は軽微です。

**使用方法**:

- `halfvec(1536)` を固定採用します（メモリ使用量50%削減）
- `pgvector/pgvector:0.8.1-pg18` イメージを使用します（PostgreSQL 18 + pgvector 0.8.1）
- NASのリソース節約のため採用します

詳細な注意事項については、上記の設計書を参照してください。

#### 6.4 環境変数とシークレット管理

**重要**: 機密情報は環境変数経由で渡されますが、適切なシークレット管理が必要です。

> **参照**: 詳細な環境変数一覧については、
> [PostgreSQL スキーマ設計書 - 付録 B. 環境変数一覧](../architecture/postgresql-schema-design.md#b-環境変数一覧)
> を参照してください。

##### 6.4.1 pydantic-settings による型安全な設定管理（必須）

⚠️ **改善（コード品質）**: 環境変数の os.getenv 呼び出しが分散している問題を改善
`os.getenv()` がコード全体に散在しており、デフォルト値の重複や型変換のミスが発生しやすいため、
Phase 8で `pydantic-settings` を**最初から使用**します（計画ではなく実装）。

**実装例**:

```python
# src/kotonoha_bot/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """アプリケーション設定（グローバルシングルトン）"""
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    
    # データベース設定
    db_pool_min_size: int = 5
    db_pool_max_size: int = 20
    db_command_timeout: int = 60
    
    # PostgreSQL接続設定（本番環境推奨）
    postgres_host: str | None = None
    postgres_port: int = 5432
    postgres_db: str = "kotonoha"
    postgres_user: str = "kotonoha"
    postgres_password: str | None = None
    
    # 開発環境用（DATABASE_URL）
    database_url: str | None = None
    
    # 知識ベース設定
    # ⚠️ 注意: halfvecは固定採用のため、kb_use_halfvec設定は削除
    kb_similarity_threshold: float = 0.7
    kb_default_top_k: int = 10
    kb_embedding_max_retry: int = 3
    kb_embedding_batch_size: int = 100
    kb_embedding_max_concurrent: int = 5
    kb_embedding_interval_minutes: int = 1
    kb_archive_threshold_hours: int = 1
    kb_archive_batch_size: int = 10
    kb_min_session_length: int = 30
    kb_archive_overlap_messages: int = 5
    kb_chunk_max_tokens: int = 4000
    kb_chunk_overlap_ratio: float = 0.2
    kb_chunk_insert_batch_size: int = 100
    kb_chunk_update_batch_size: int = 100
    kb_hnsw_m: int = 16
    kb_hnsw_ef_construction: int = 64
    
    # ハイブリッド検索設定
    # ⚠️ 注意: フェーズ8では開発環境・本番環境ともにpg_bigmを含むカスタムイメージを使用します。
    # このパラメータは将来的にハイブリッド検索機能を無効化するオプションとして使用可能ですが、
    # フェーズ8の実装では常にpg_bigm拡張を有効化します。
    enable_hybrid_search: bool = True
    
    # Discord設定
    discord_token: str
    
    # OpenAI設定
    openai_api_key: str

# グローバルシングルトン
settings = Settings()

# 使用側
async def similarity_search(...):
    # ⚠️ 重要: halfvec固定採用
    vector_cast = "halfvec"
    similarity_threshold = settings.kb_similarity_threshold
    # ...
```

**メリット**:

- 型安全性: 設定値の型が保証される
- バリデーション: 不正な値の検出が自動化される
- IDE補完: 設定値へのアクセス時に補完が効く
- ドキュメント化: 設定クラスが自動的にドキュメントになる
- **一箇所での管理**: `os.getenv`の呼び出しが分散しない

##### 6.4.2 環境変数ファイルの管理

- **`.env.sample` ファイルの作成**: すべての環境変数のサンプルを提供
  （詳細は上記の設計書を参照）
- **`.env` ファイルの扱い**:
  - `.env` ファイルは `.gitignore` に追加（既に追加済みを想定）
  - 本番環境では環境変数を直接設定するか、シークレットマネージャーを使用

##### 6.4.3 本番環境でのシークレット管理

- **Docker Secrets の使用**: Docker Swarm を使用している場合
- **外部シークレットマネージャー**: AWS Secrets Manager、HashiCorp Vault等との連携
- **シークレットローテーション**: 定期的なパスワード・APIキーの更新方針を策定

##### 6.4.4 pgAdminのセキュリティ設定

- **必須設定**: `PGADMIN_CONFIG_MASTER_PASSWORD_REQUIRED=True`
- **推奨設定**: `profiles: ["admin"]` を使用して、必要な時だけ起動
  - 通常起動: `docker-compose up -d`（pgAdminは起動しない）
  - 管理ツール起動: `docker-compose --profile admin up -d`（pgAdminも起動）
  - メモリ節約（約200-500MB）とセキュリティ向上が実現できます
- **アクセス制限**: 本番環境では、pgAdminへのアクセスをVPN経由に制限
- **パスワード管理**: 強力なパスワードを設定し、定期的にローテーション

1. **移行スクリプトについて**:
   - **重要**: このフェーズは**新規設計**のため、SQLiteからの移行ツールは作成しません
   - 既存のデータは破棄します
   - 将来的に移行が必要になった場合は、別途移行スクリプトを作成することを検討してください

**完了基準**:

- [ ] `docker-compose.yml` が更新されている（環境変数対応版）
- [ ] ⚠️ **改善（パフォーマンス）**: maintenance_work_mem の設定が追加されている
  - POSTGRES_INITDB_ARGS に `--maintenance-work-mem=256MB` が設定されている（初期化時のみ）
  - または、カスタム postgresql.conf がマウントされている（実行時も有効、推奨）
  - システムメモリの10〜20%程度（最小128MB、最大1GB）に設定されている
- [ ] PostgreSQL コンテナが起動する
- [ ] pgAdmin が起動し、PostgreSQL に接続できる
- [ ] 環境変数が正しく設定されている（`.env.example`に基づく）
- [ ] すべてのハードコードされた値が環境変数から読み込まれるようになっている
- [ ] halfvecの使用が環境変数で制御できる
- [ ] HNSWパラメータが環境変数で制御できる

### Step 7: テストと最適化 (1-2日)

#### 7.0 実装時のQ&A（よくある質問と回答）

実装中に直面しそうな疑問とその答えを用意しました。

##### Q: pgvector.asyncpg.register_vector() はどこで呼ぶべき？

A: ⚠️ **これは設計書に重大な見落としがあります**。設計書では
`initialize()` 内で1回だけ呼んでいますが、コネクションプールを使用して
いる場合、プールから取得される各コネクションに対して登録が必要です。

**❌ 設計書の現状（問題あり）**:

```python
async def initialize(self):
    self.pool = await asyncpg.create_pool(...)
    async with self.pool.acquire() as conn:
        await pgvector.asyncpg.register_vector(conn)  # この conn のみに登録される
        # プールの他のコネクションには登録されていない！
```

**✅ 正しい実装（pgvector-python公式ドキュメント推奨）**:

⚠️ **重要**: `asyncpg.create_pool()` の `init` パラメータには単一の関数しか渡せません。
pgvectorの型登録とJSONBコーデックの登録を両方行う場合は、ラッパー関数を作成する必要があります。

```python
async def _init_connection(self, conn: asyncpg.Connection):
    """コネクション初期化用ラッパー（ベクトル登録とJSONBコーデックを両方実行）"""
    # 1. pgvectorの型登録
    from pgvector.asyncpg import register_vector
    await register_vector(conn)
    
    # 2. JSONBコーデックの登録（orjsonを使用）
    import orjson
    from datetime import datetime
    
    # ⚠️ 改善（堅牢性）: orjson.dumps は標準では datetime オブジェクトをシリアライズできません
    # Pydanticの .model_dump(mode='json') を通す前提であれば文字列化されているので問題ありませんが、
    # 生の dict に datetime オブジェクトが含まれているとエラーになります。
    # 対策: default オプションで datetime を ISO 文字列に変換する関数を指定
    def default(obj):
        """orjson の default オプション用の関数"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
    
    await conn.set_type_codec(
        'jsonb',
        encoder=lambda v: orjson.dumps(
            v, default=default
        ).decode('utf-8'),
        decoder=lambda b: orjson.loads(
            b.encode('utf-8') if isinstance(b, str) else b
        ),
        schema='pg_catalog',
        format='text'
    )
    # ⚠️ 注意: 計画書通り「Pydanticで事前にJSON化する」ルールを徹底するなら、
    # default オプションなしでも動作しますが、防御的プログラミングとして追加しています。

async def initialize(self):
    self.pool = await asyncpg.create_pool(
        self.connection_string,
        init=self._init_connection,  # ← これが重要！
        min_size=min_size,
        max_size=max_size,
    )
```

**公式ドキュメントの例**:

```python
async def init(conn):
    await register_vector(conn)

pool = await asyncpg.create_pool(..., init=init)
```

⚠️ **追加の注意**: JSONBコーデックも同じ `_init_connection` 関数内で登録する必要があります。
`asyncpg.create_pool()` の `init` パラメータには単一の関数しか渡せないため、両方を1つのラッパー関数にまとめる必要があります。

これはクリティカルな修正であり、設計書の11.3項に反映済みです。

##### Q: asyncpg のコネクションプールはどこで管理すべき？

A: 設計書通り `PostgreSQLDatabase` クラス内で保持し、シングルトンとして `main.py` でインスタンス化して
各ハンドラに渡す（Dependency Injection）方式で完璧です。
ただし、Graceful Shutdown時に `await db.close()` を確実に呼ぶことを忘れないでください。
`atexit` は非同期では使えないため、signal ハンドリングまたは Discord.py の `bot.close()` オーバーライドで対応します。

##### Q: search メソッドで source_id だけでなく、元のメッセージの内容も欲しいときは？

A: 設計書のクエリは `JOIN knowledge_sources` しているので取得可能です。
SELECT 句に必要なカラムが含まれているか確認してください。
設計書では網羅されています（`s.type`, `s.title`, `s.uri`, `s.metadata`,
`c.content`, `c.location` など）。

##### Q: テストデータはどう作る？

A: PGVectorのテストは、実際にEmbedding APIを叩くとコストと時間がかかります。
設計書にある `mock_embedding_provider` で固定次元のダミーベクトル（例: `[0.1] * 1536`）を返すのが正解です。
類似度検索のロジック確認用には、pgvector に対して
「特定のIDが返ってくるか」だけを確認し、精度のテストは切り離しましょう。

##### Q: orjson と datetime のシリアライズ問題はどう解決する？

A: ⚠️ **重要**: `orjson.dumps()` は datetime オブジェクトを自動的に ISO フォーマットの文字列に変換しません。
Pydantic v2 を使用している場合、`model_dump(mode='json')` を
使用することで、datetime が ISO 文字列化されます。

**❌ 問題のある実装**:

```python
# datetimeオブジェクトが含まれる場合、エラーになる可能性がある
orjson.dumps([msg.model_dump() for msg in session.messages])
```

**✅ 正しい実装**:

```python
# model_dump(mode='json')でdatetimeがISO文字列化される
messages_json = [msg.model_dump(mode='json') for msg in session.messages]
# JSONBコーデックが設定されていれば、dictを直接渡せる
await conn.execute(..., messages_json, ...)
```

**注意**: JSONBコーデックが設定されていれば、`orjson.dumps` は不要です。
コーデックのエンコーダー内で `orjson.dumps` が使用されるため、
コード内で明示的に呼ぶ必要はありません。

##### Q: halfvec の入力型処理はどうなっている？

A: ⚠️ **重要**: SQL文では `$1::halfvec(1536)` とキャストしていますが、
Python側（asyncpg）から渡すパラメータは `list[float]` です。

**動作の仕組み**:

1. **PostgreSQL側の自動キャスト**: PostgreSQL側で `float[]` から
   `halfvec` へのキャストは自動で行われますが、
   明示的なキャストがないと曖昧さのエラーが出る場合があります。

2. **pgvector-python の register_vector の動作**:
   - `pgvector.asyncpg.register_vector()` は `vector` 型と `halfvec` 型の両方をサポートします
   - ⚠️ **重要**: `register_vector()` は通常 float32 として扱います`
   - Python側から `list[float]` を渡すと、PostgreSQL側で
     `float32[] -> halfvec` のキャストが行われるため機能はします
   - ⚠️ **注意**: ドライバ層でのオーバーヘッドが微増しますが、許容範囲内です
   - 明示的な型キャスト（`$1::halfvec(1536)`）により、PostgreSQL側で適切に変換されます

3. **明示的な型キャストの重要性**:

   ```python
   # ✅ 正しい実装（明示的なキャスト、halfvec固定）
   vector_cast = "halfvec"
   
   await conn.execute(f"""
       UPDATE knowledge_chunks
       SET embedding = $1::{vector_cast}(1536)
       WHERE id = $2
   """, embedding_list, chunk_id)
   ```

**テスト時の確認事項**:

⚠️ **重要**: 実装時には必ずhalfvec固定採用でのINSERTとSELECTが通るか確認してください。

```python
# テスト例
async def test_halfvec_insert_and_select():
    """halfvec固定採用でのINSERTとSELECTのテスト"""
    # テスト用のベクトル
    test_embedding = [0.1] * 1536
    vector_cast = "halfvec"  # 固定採用
    
    # INSERTテスト
    await conn.execute(f"""
        INSERT INTO knowledge_chunks (content, embedding)
        VALUES ($1, $2::{vector_cast}(1536))
    """, "test content", test_embedding)
    
    # SELECTテスト
    result = await conn.fetchrow(f"""
        SELECT embedding <=> $1::{vector_cast}(1536) AS distance
        FROM knowledge_chunks
        WHERE content = 'test content'
    """, test_embedding)
    
    assert result is not None
    assert result['distance'] is not None
```

**トラブルシューティング**:

- **エラー**: "operator is not unique: halfvec <=> unknown"
  - **原因**: 型キャストが不足している
  - **解決**: SQL内で `$1::halfvec(1536)` と明示的にキャストする

- **エラー**: "cannot cast type double precision[] to halfvec"
  - **原因**: pgvector-python の型マッピングの問題
  - **解決**: `register_vector()` が正しく呼ばれているか確認し、明示的なキャストを使用する

##### Q: EmbeddingProcessor でトランザクション内でAPIコールを避けるべき？

A: ⚠️ **重要**: はい、**必ず避けるべき**です。
PostgreSQLのトランザクションを長時間（API待ち時間分）保持すると、
接続プールが枯渇したり、他のクエリをブロックする原因になります。

**❌ 問題のある実装**:

```python
# トランザクション内でAPIコールを行う（長時間ロックを保持）
async with conn.transaction():
    chunks = await conn.fetch("SELECT ... FOR UPDATE SKIP LOCKED")
    embeddings = await api_call()  # 時間がかかる（トランザクションを保持したまま）
    await conn.execute("UPDATE ...")
```

**✅ 正しい実装（推奨フロー）**:

```python
# Tx1: FOR UPDATE SKIP LOCKED で対象行を取得し、IDとcontentをメモリに保持して即コミット
async with conn.transaction():
    chunks = await conn.fetch("""
        SELECT id, content, source_id
        FROM knowledge_chunks
        WHERE embedding IS NULL
        FOR UPDATE SKIP LOCKED
        LIMIT $1
    """, batch_size)
    # トランザクションを即コミット（ロックを解放）

# No Tx: OpenAI API コール（時間かかる処理、トランザクション外で実行）
embeddings = await self._generate_embeddings_batch(texts)

# Tx2: 結果を UPDATE（別トランザクション）
async with conn.transaction():
    await conn.executemany("UPDATE ... SET embedding = $1 ...", ...)
```

**メリット**:

- **接続プールの枯渇を防ぐ**: 長時間トランザクションを保持しないため、接続プールが有効活用される
- **他のクエリをブロックしない**: トランザクションの保持時間が最小限になる
- **スケーラビリティの向上**: 複数のプロセスが並行して処理できる

**注意**: `FOR UPDATE SKIP LOCKED` を使用する場合、
取得した行をロックしたまま処理するのが常套手段ですが、
APIが遅い場合は「ID取得＆メモリ保持(commit)」→「API」→
「完了更新(commit)」のパターンの方が安全です。

##### Q: テスト用のPostgreSQLはどう用意する？

A: 3つの選択肢があります：

1. **Docker Compose（推奨）**: `docker-compose -f docker-compose.test.yml up -d`
   でテスト用PostgreSQLを起動
2. **testcontainers-python**: テストコード内でコンテナを起動（自動管理）
3. **Pytest-docker**: pytestプラグインで自動管理

**testcontainers-python を使用した例**:

```python
# tests/conftest.py（追加）
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="session")
async def postgres_container():
    """テスト用PostgreSQLコンテナを起動"""
    with PostgresContainer("pgvector/pgvector:0.8.1-pg18") as postgres:
        yield postgres.get_connection_url()
```

**注意**: `testcontainers-python` を使用する場合は、`pyproject.toml` に追加が必要です：

```toml
[project.optional-dependencies]
test = [
    "testcontainers[postgres]>=4.0.0",
]
```

##### Q: Source と Chunk の関係で、1:1 のケースはどう扱う？

A: 設計上は問題ありません。1つの Source に対して1つの Chunk が存在する
ケース（短いセッションなど）も正常なパターンです。データベーススキーマは
1対多の関係を想定していますが、1対1のケースも自然に処理されます。
特に問題はありません。

#### 7.1 PostgreSQL 用テストフィクスチャ

⚠️ 改善（コード品質）: テスト計画の具体性不足を改善します。
pytest-asyncio + pytest-dockerの具体的なフィクスチャ例を追加します。

```python
# tests/conftest.py
import pytest
import asyncpg
import pytest_asyncio
from kotonoha_bot.db.postgres import PostgreSQLDatabase

# ⚠️ 改善: pytest-dockerを使用したPostgreSQLコンテナの自動起動
# pytest-dockerを使用することで、テスト時にPostgreSQLコンテナを自動的に起動・停止できます
try:
    from pytest_docker import docker_services, docker_compose_file
except ImportError:
    # pytest-dockerがインストールされていない場合は、手動でPostgreSQLを起動する必要がある
    docker_services = None
    docker_compose_file = None

async def _cleanup_test_data(db: PostgreSQLDatabase):
    """テストデータのクリーンアップ
    
    ⚠️ 注意: TRUNCATE ... CASCADE を使用していますが、並列テスト実行時に相互干渉する可能性があります。
    将来的に pytest-xdist 等で並列テストを行う場合、単一のDBをTRUNCATEし合うとテストが落ちます。
    
    ⚠️ 改善（テスト時のデータベースクリーンアップ）: 各テストケースをトランザクション内で実行し、
    最後にロールバックする方式（pytest-asyncio のフィクスチャでロールバックパターン）を採用すると、
    より高速で安全です。
    """
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            # 外部キー制約があるため、順序に注意
            await conn.execute("TRUNCATE knowledge_chunks CASCADE")
            await conn.execute("TRUNCATE knowledge_sources CASCADE")
            await conn.execute("TRUNCATE sessions CASCADE")

@pytest_asyncio.fixture
async def postgres_db():
    """PostgreSQL データベースのフィクスチャ
    
    ⚠️ 改善: pytest-asyncioを使用した非同期フィクスチャ
    pytest-asyncioを使用することで、非同期関数をフィクスチャとして使用できます
    
    ⚠️ 改善（テスト時のデータベースクリーンアップ）: 並列テスト実行時の相互干渉を防ぐため、
    ロールバックパターンを使用することを推奨します。
    """
    # テストDB接続文字列を環境変数から読み込み
    import os
    test_db_url = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql://test:test@localhost:5432/test_kotonoha"
    )
    db = PostgreSQLDatabase(test_db_url)
    await db.initialize()
    
    # テスト前のクリーンアップ
    await _cleanup_test_data(db)
    
    yield db
    
    # テスト後のクリーンアップ
    await _cleanup_test_data(db)
    await db.close()

# ⚠️ 改善（テスト時のデータベースクリーンアップ）: ロールバックパターンの実装例
@pytest_asyncio.fixture
async def postgres_db_with_rollback():
    """PostgreSQL データベースのフィクスチャ（ロールバックパターン）
    
    ⚠️ 改善: 各テストケースをトランザクション内で実行し、最後にロールバックする方式
    これにより、並列テスト実行時でも相互干渉が発生しません。
    また、TRUNCATE よりも高速で、テストデータのクリーンアップが不要です。
    
    使用方法:
    ```python
    async def test_example(postgres_db_with_rollback):
        db, conn = postgres_db_with_rollback
        # テストコード（トランザクション内で実行）
        await conn.execute("INSERT INTO sessions ...")
        # テスト終了時に自動的にロールバックされる
    ```
    """
    import os
    test_db_url = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql://test:test@localhost:5432/test_kotonoha"
    )
    db = PostgreSQLDatabase(test_db_url)
    await db.initialize()
    
    # 各テストケースごとに新しいトランザクションを開始
    conn = await db.pool.acquire()
    tx = conn.transaction()
    await tx.start()
    
    try:
        yield (db, conn)
    finally:
        # テスト終了時にロールバック（データを元に戻す）
        await tx.rollback()
        await db.pool.release(conn)
        await db.close()

# ⚠️ 改善: pytest-dockerを使用したPostgreSQLコンテナの自動起動
@pytest.fixture(scope="session")
def docker_compose_file(pytestconfig):
    """Docker Composeファイルのパスを返す"""
    import os
    return os.path.join(
        str(pytestconfig.rootdir),
        "tests",
        "docker-compose.test.yml"
    )

@pytest.fixture(scope="session")
def postgres_service(docker_services):
    """PostgreSQLサービスの起動を待機"""
    if docker_services is None:
        pytest.skip("pytest-docker not installed")
    
    # PostgreSQLが起動するまで待機
    docker_services.wait_for_service(
        "postgres",
        5432,
        check=lambda: True  # 実際の接続チェックを実装
    )
    return docker_services.docker_ip("postgres")
```

#### 7.2 モックの実装

⚠️ 改善（コード品質）: モックの具体実装例を追加します。

```python
# tests/conftest.py（追加）

from unittest.mock import AsyncMock, MagicMock
from kotonoha_bot.external.embedding import EmbeddingProvider
import pytest

@pytest.fixture
def mock_embedding_provider():
    """OpenAI API のモック（CI/CDでテストが失敗しないように）
    
    ⚠️ 改善: より詳細なモック実装例
    - バッチ処理のモック
    - エラーケースのモック
    - レート制限のモック
    """
    provider = AsyncMock(spec=EmbeddingProvider)
    
    # 基本的なメソッドのモック
    provider.generate_embedding = AsyncMock(return_value=[0.1] * 1536)
    provider.get_dimension = lambda: 1536
    
    # ⚠️ 改善: バッチ処理のモック
    if hasattr(provider, 'generate_embeddings_batch'):
        provider.generate_embeddings_batch = AsyncMock(
            side_effect=lambda texts: [[0.1] * 1536 for _ in texts]
        )
    
    # ⚠️ 改善: エラーケースのモック
    provider.generate_embedding_error = AsyncMock(
        side_effect=Exception("API Error")
    )
    
    return provider

@pytest.fixture
def mock_postgres_pool():
    """PostgreSQL接続プールのモック"""
    pool = AsyncMock()
    conn = AsyncMock()
    
    # 接続の取得をモック
    async def acquire():
        return conn
    
    pool.acquire = AsyncMock(return_value=conn)
    pool.__aenter__ = lambda self: self
    pool.__aexit__ = lambda self, *args: None
    
    # 基本的なクエリのモック
    conn.execute = AsyncMock(return_value="OK")
    conn.fetchval = AsyncMock(return_value=1)
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.transaction = MagicMock()
    
    return pool
```

#### 7.3 パフォーマンステスト

```python
# tests/performance/test_vector_search.py
"""ベクトル検索のパフォーマンステスト"""

async def test_vector_search_performance(postgres_db):
    """ベクトル検索の性能測定"""
    import time
    
    # テストデータの準備
    # ...
    
    # 検索実行
    start = time.time()
    results = await postgres_db.similarity_search(
        query_embedding=[0.1] * 1536,
        top_k=10,
    )
    elapsed = time.time() - start
    
    assert elapsed < 1.0  # 1秒以内
    assert len(results) <= 10
```

#### 7.4 メトリクス/モニタリング

**重要**: パフォーマンスメトリクスの収集方法を実装します。

**推奨メトリクス**:

1. **Embedding処理のメトリクス**:
   - 処理時間（平均、最大、最小）
   - キュー長（pendingチャンク数）
   - エラー率
   - API呼び出し回数とコスト

2. **データベースのメトリクス**:
   - 接続プールの使用状況
   - クエリ実行時間
   - インデックスの使用状況

3. **実装例（prometheus-clientを使用したメトリクス定義）**:

   ⚠️ 改善（コード品質）: prometheus-clientが依存関係にありますが、具体的なメトリクス定義が不足していました。
   以下のメトリクスを定義してください:

   ```python
   # src/kotonoha_bot/features/knowledge_base/metrics.py
   from prometheus_client import Counter, Histogram, Gauge
   
   # Embedding処理のメトリクス
   embedding_processing_duration = Histogram(
       'embedding_processing_seconds', 
       'Time spent processing embeddings',
       buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]  # バケット設定
   )
   
   pending_chunks_gauge = Gauge(
       'pending_chunks_count', 
       'Number of chunks waiting for embedding'
   )
   
   embedding_errors_counter = Counter(
       'embedding_errors_total', 
       'Total embedding errors',
       ['error_type']  # エラータイプでラベル付け
   )
   
   embedding_processed_counter = Counter(
       'embedding_processed_total',
       'Total embeddings processed successfully'
   )
   
   # データベースのメトリクス
   db_query_duration = Histogram(
       'db_query_duration_seconds',
       'Database query execution time',
       ['query_type']  # SELECT, INSERT, UPDATE等でラベル付け
   )
   
   db_pool_size = Gauge(
       'db_pool_size',
       'Database connection pool size',
       ['state']  # 'active', 'idle', 'max'等
   )
   
   # 使用例
   @embedding_processing_duration.time()
   async def process_embedding(chunk):
       # 処理時間が自動的に記録される
       ...
   
   embedding_errors_counter.labels(error_type='api_error').inc()
   pending_chunks_gauge.set(count)
   ```

   **最低限のログベースメトリクス（フォールバック）**:

   ```python
   # src/kotonoha_bot/features/knowledge_base/metrics.py
   import time
   from dataclasses import dataclass, field
   
   @dataclass
   class EmbeddingMetrics:
       total_processed: int = 0
       total_errors: int = 0
       processing_times: list[float] = field(default_factory=list)
       
       def record_processing(self, duration: float):
           self.total_processed += 1
           self.processing_times.append(duration)
           if len(self.processing_times) > 1000:
               self.processing_times = self.processing_times[-1000:]
       
       def record_error(self):
           self.total_errors += 1
       
       def get_summary(self) -> dict:
           if not self.processing_times:
               return {}
           return {
               "total_processed": self.total_processed,
               "total_errors": self.total_errors,
               "avg_duration_ms": (
                   sum(self.processing_times) / len(self.processing_times)
                   * 1000),
               "max_duration_ms": max(self.processing_times) * 1000,
           }
   
   # 使用例
   metrics = EmbeddingMetrics()
   
   async def process_embedding():
       start = time.time()
       try:
           # 処理...
           metrics.record_processing(time.time() - start)
       except Exception as e:
           metrics.record_error()
           raise
   
   # 定期的にログ出力
   logger.info(f"Embedding metrics: {metrics.get_summary()}")
   ```

4. **メトリクスエンドポイントの実装**:

   ⚠️ 改善（運用性）: prometheus-clientが依存関係にありますが、
   メトリクスを公開するHTTPエンドポイント（/metrics）の実装が
   不足していました。

   **実装方針**: 既存のヘルスチェックサーバー
   （`src/kotonoha_bot/health.py`）を拡張して、
   `/metrics`エンドポイントを追加します。
   既存の実装は標準ライブラリの `http.server` を使用しているため、同じスタイルで実装します。

   ```python
   # src/kotonoha_bot/health.py（既存のHealthCheckHandlerに追加）
   from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
   
   class HealthCheckHandler(BaseHTTPRequestHandler):
       # ... 既存のコード ...
       
       def do_GET(self) -> None:
           """GETリクエストの処理"""
           if self.path == "/health" or self.path == "/":
               self._handle_health()
           elif self.path == "/ready":
               self._handle_ready()
           elif self.path == "/metrics":
               self._handle_metrics()  # ⚠️ 追加: メトリクスエンドポイント
           else:
               self.send_error(404, "Not Found")
       
       def _handle_metrics(self) -> None:
           """Prometheusメトリクスエンドポイント"""
           try:
               self.send_response(200)
               self.send_header("Content-Type", CONTENT_TYPE_LATEST)
               self.end_headers()
               self.wfile.write(generate_latest())
           except Exception as e:
               logger.error(f"Metrics endpoint error: {e}")
               self.send_error(500, "Internal Server Error")
   ```

   **代替案（FastAPIを使用する場合）**:

   将来的にFastAPIを導入する場合は、以下の実装も可能です：

   ```python
   # src/kotonoha_bot/api/metrics.py
   from fastapi import APIRouter
   from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
   from starlette.responses import Response
   
   router = APIRouter()
   
   @router.get("/metrics")
   async def get_metrics():
       return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
   ```

   **注意**: FastAPIを使用する場合は、依存関係に `fastapi` と `uvicorn` を追加する必要があります。

5. **将来的な拡張（Prometheusメトリクス）**:

   ```python
   # Prometheusメトリクスの例（将来実装）
   from prometheus_client import Counter, Histogram, Gauge
   
   embedding_duration = Histogram(
       'embedding_duration_seconds', 'Embedding processing duration')
   pending_chunks = Gauge('pending_chunks_count', 'Number of pending chunks')
   embedding_errors = Counter(
       'embedding_errors_total', 'Total embedding errors')
   ```

**完了基準**:

- [ ] PostgreSQL 用のテストフィクスチャが追加されている
- [ ] パフォーマンステストが実装されている（ベクトル検索の性能測定）
- [ ] インデックスの最適化が完了している（HNSW パラメータの調整）
- [ ] 接続プールの調整が完了している（`min_size`, `max_size`）
- [ ] すべてのテストが通過する

---

## 6. テスト計画

### 6.1 ユニットテスト

- [ ] `DatabaseProtocol` のテスト
- [ ] `PostgreSQLDatabase` のテスト
- [ ] `KnowledgeBaseStorage` のテスト
- [ ] `EmbeddingProcessor` のテスト
- [ ] `SessionArchiver` のテスト
- [ ] `OpenAIEmbeddingProvider` のテスト

### 6.2 統合テスト

- [ ] セッション管理の動作確認
- [ ] 知識ベース保存の動作確認
- [ ] Embedding処理の動作確認
- [ ] セッション知識化処理の動作確認
- [ ] ベクトル検索の動作確認

### 6.3 パフォーマンステスト

- [ ] ベクトル検索の性能測定
- [ ] バッチ処理の性能測定
- [ ] 接続プールの性能測定

**具体的なテストケース**:

```python
# tests/test_performance.py

# 1. 接続プール枯渇テスト
async def test_connection_pool_exhaustion():
    """同時接続数がmax_sizeを超えた場合のタイムアウト動作"""
    # max_size=2 でプールを作成
    # 3つの同時接続を試行
    # 3つ目は asyncio.TimeoutError が発生することを確認
    
# 2. halfvec型の精度テスト
async def test_halfvec_similarity_accuracy():
    """halfvec使用時の検索精度がvector使用時と比較して許容範囲内"""
    # 同じデータでvectorとhalfvecの両方で検索
    # 結果の類似度スコアを比較
    # 許容誤差範囲内であることを確認（例: 0.01以内）
    
# 3. 競合状態テスト
async def test_concurrent_session_archiving():
    """複数ワーカーが同時にアーカイブ処理した場合の整合性"""
    # 複数のワーカープロセスをシミュレート
    # 同じセッションを同時にアーカイブしようとする
    # データの整合性が保たれることを確認
    
# 4. Embedding API失敗時のリトライテスト
async def test_embedding_retry_on_failure():
    """APIエラー時のリトライとDLQ投入"""
    # Embedding APIをモックして失敗をシミュレート
    # retry_countがインクリメントされることを確認
    # 最大リトライ回数に達したらDLQに投入されることを確認
```

**負荷テストシナリオ**:

1. **1万件のチャンクでの検索レイテンシ**
   - 1万件のチャンクを登録
   - 検索クエリを実行
   - レイテンシが1秒以内であることを確認

2. **100同時接続でのパフォーマンス**
   - 100の同時接続でクエリを実行
   - 接続プールの枯渇が発生しないことを確認
   - タイムアウトが適切に処理されることを確認

3. **HNSWインデックス再構築時間**
   - 大量のデータでインデックスを再構築
   - 構築時間を測定
   - パラメータ調整の効果を確認

### 6.4 テストカバレッジの目標

**目標カバレッジ**: 80%以上

```toml
# pyproject.toml
[tool.pytest.ini_options]
addopts = "--cov=src/kotonoha_bot --cov-fail-under=80"
```

---

## 7. 完了基準とチェックリスト

### 7.1 必須項目

#### データベース抽象化レイヤー（Step 1）

- [ ] データベース抽象化レイヤーが実装されている
- [ ] `DatabaseProtocol` インターフェースが定義されている（セッション管理のみを抽象化）
- [ ] `KnowledgeBaseProtocol` インターフェースが定義されている（知識ベース管理を別プロトコルとして分離）
  - `similarity_search`, `save_source`, `save_chunk` メソッドが含まれている
- [ ] 既存の `SQLiteDatabase` が `DatabaseProtocol` に適合している
- [ ] ⚠️ **改善（抽象化の粒度）**: セッション管理と知識ベース管理が分離されている
  - `DatabaseProtocol` はセッション管理のみを抽象化
  - `KnowledgeBaseProtocol` は知識ベース管理を抽象化
  - 抽象化の粒度が均一になり、単一責任の原則に従っている
- [ ] 依存性注入パターンが採用されている（循環インポート対策）
- [ ] `main.py` で一括初期化が実装されている

#### PostgreSQL実装（Step 2）

- [ ] `PostgreSQLDatabase` クラスが実装されている
- [ ] `PostgreSQLDatabase` が `DatabaseProtocol` と
  `KnowledgeBaseProtocol` の両方に適合している
- [ ] ⚠️ **改善（抽象化の粒度）**: セッション管理と知識ベース管理が分離されている
  - `DatabaseProtocol` のメソッド（`save_session`, `load_session` 等）が実装されている
  - `KnowledgeBaseProtocol` のメソッド
    （`similarity_search`, `save_source`, `save_chunk` 等）が実装されている
- [ ] ⚠️ **重要**: Alembicマイグレーションが自動適用されている
  （`PostgreSQLDatabase.initialize()`で`alembic upgrade head`を実行）
- [ ] 初回マイグレーション（`001_initial_schema`）が作成されている
- [ ] pgvector 拡張が有効化されている（`CREATE EXTENSION vector`、マイグレーションまたは手動実行）
- [ ] pgvector のバージョン確認が実装されている（HNSW対応の確認）
- [ ] ⚠️ **推奨**: pg_bigm 拡張が有効化されている（ハイブリッド検索の準備、Phase 9 で実装予定）
  - Dockerfile.postgres で pg_bigm をビルドしてカスタムイメージを作成
  - docker-compose.yml でカスタムイメージを使用
  - `idx_chunks_content_bigm` インデックスが作成されている
- [ ] ⚠️ **重要**: `pgvector.asyncpg.register_vector()` が `init` パラメータ
  経由で正しく実装されている（プールの各コネクションに対して登録される）
- [ ] ⚠️ **重要**: JSONBコーデックも同じ `_init_connection` 関数内で登録されている
  （initパラメータには単一の関数しか渡せないため、ラッパー関数で統合）
- [ ] ⚠️ **重要**: datetimeオブジェクトが含まれる場合は、`model_dump(mode='json')`を使用している
  （orjsonはdatetimeを自動的にISO文字列化しないため）
- [ ] ENUM型が正しく定義されている
  （`source_type_enum`, `session_status_enum`, `source_status_enum`）
- [ ] ⚠️ **重要**: ENUM型を使用している場合、CHECK制約は使用しない（冗長かつ危険、ENUM型拡張時に更新忘れで失敗するリスク）
- [ ] テーブルが作成される
  （`sessions`, `knowledge_sources`, `knowledge_chunks`,
  `knowledge_chunks_dlq`）
- [ ] ⚠️ **修正**: `knowledge_chunks.source_id` に `NOT NULL` 制約が付いている
  （孤立したチャンクの生成を防ぐ）
- [ ] ⚠️ **改善**: `knowledge_chunks_dlq` テーブルに `source_type` カラムが追加されている
  （トレーサビリティ向上）
- [ ] ⚠️ **重要**: sessionsテーブルに `id BIGSERIAL PRIMARY KEY` が追加されている
  - `session_key` は `TEXT UNIQUE NOT NULL` になっている
  - アプリケーション内部での参照は `session_key` を使いつつ、将来的なリレーションは `id` を使う余地を残す
- [ ] インデックスが作成される（HNSWインデックス、GINインデックス等）
- [ ] ⚠️ **修正**: `idx_sessions_session_key` インデックスは作成しない
  （UNIQUE制約で自動的にユニークインデックスが作成されるため冗長）
- [ ] ⚠️ **改善（パフォーマンス）**: `idx_chunks_queue` 部分インデックスが作成されている
  - WHERE embedding IS NULL AND retry_count < 3 の条件で作成されている
  - FOR UPDATE SKIP LOCKED を使うクエリのパフォーマンスが向上している
- [ ] ⚠️ **推奨**: `idx_chunks_content_trgm` インデックスが作成されている（Phase 9 で使用予定）
- [ ] セッション管理が動作する（`save_session`, `load_session`等）
  - アプリケーション内部での参照は `session_key` を使用（既存のコードは変更不要）
  - `id` は将来的な外部キー参照用に残しておく
- [ ] 接続プールの設定が環境変数から読み込まれる
  （`DB_POOL_MIN_SIZE`, `DB_POOL_MAX_SIZE`, `DB_COMMAND_TIMEOUT`）
- [ ] ⚠️ **推奨**: JSONBの自動変換（asyncpgカスタムコーデック）が実装されている

#### ベクトル検索機能（Step 3）

- [ ] `similarity_search` メソッドが実装されている
- [ ] pgvector の `<=>` 演算子を使用したベクトル検索が動作する
- [ ] ⚠️ **重要**: すべてのベクトル検索クエリで `WHERE embedding IS NOT NULL` 条件を含めている
  - この条件がないと、HNSWインデックスが使われずフルスキャンになるリスクがある
  - ⚠️ **改善（Strong Recommendation）**: クエリビルダーやラッパー関数（`similarity_search`）側で、
    強制的にこの条件が付与される仕組みをコードレベルで保証している
  - 実装漏れが発生すると、意図せずフルスキャンが発生し、本番環境で突然死（タイムアウト）する原因になる
  - アプリケーション実装者の注意深さに依存した設計ではなく、コードレベルで保証することで、実装漏れを防ぐ
- [ ] ⚠️ **改善（Semantic Issues）**: チャットログのチャンク化戦略が実装されている
  - メッセージ単位/会話ターン単位でのチャンク化（`KB_CHAT_CHUNK_STRATEGY=message_based`）が推奨
  - 単純な文字数分割では「ユーザーの質問」と「Botの回答」が別々のチャンクに分断されるリスクがある
  - スライディングウィンドウ方式（過去Nメッセージ分を1チャンクとして、1メッセージずつずらしながら保存）が実装されている
- [ ] ⚠️ **重要**: pg_bigm を含むカスタムイメージが使用されている
  - 開発環境・本番環境ともに、Dockerfile.postgresでビルドしたpg_bigmを含むカスタムイメージを使用
  - docker-compose.ymlでカスタムイメージをビルドして使用する設定になっている
- [ ] ⚠️ **改善（競合状態対策）**: session_status の競合状態対策が実装されている
  - アーカイブ済み地点（message count や timestamp）を記録している
  - 将来の差分アーカイブ機能の準備ができている
    （metadata に `archived_message_count` と
    `archived_until_timestamp` を保存）
- [ ] ⚠️ **運用上の注意**: HNSWインデックスのメモリ消費に関する
  監視計画が立てられている
  - データが10万件を超えたあたりで監視を開始する計画
  - `pg_stat_activity` やコンテナのメモリ使用量を監視する方法を理解している
  - PostgreSQLの設定（`postgresql.conf`）チューニングが必要になる可能性を認識している
  - `maintenance_work_mem` や `work_mem` の調整方法を理解している
- [ ] ⚠️ **運用上の注意**: バックアップとリストアの整合性に関する計画が立てられている
  - `pg_dump` は論理バックアップであり、インデックス再構築によりリストア時間が長くなる可能性を認識している
  - 小規模データ（〜10万件）では `pg_dump` で十分であることを理解している
  - 大規模データ（10万件超）では物理バックアップ（WALアーカイブなど）を検討する計画がある
- [ ] ⚠️ **改善（データ整合性）**: 楽観的ロックの実装が改善されている
  - `version`カラムが追加されている（INT、更新ごとにインクリメント）
  - TIMESTAMPTZの精度（マイクロ秒）で競合検出に依存するのではなく、versionカラムを使用している
  - 同一マイクロ秒内の更新で誤検知の可能性を回避している
- [ ] ⚠️ **改善（データ整合性）**: knowledge_sources と knowledge_chunks の整合性が改善されている
  - `_update_source_status` で `retry_count < MAX_RETRY` 条件を追加している
  - retry_countが上限に達して諦められたチャンクを除外している
  - source_statusが'completed'でも、すべてのチャンクのembeddingがNOT NULLとは限らない可能性を回避している
- [ ] ⚠️ **改善（データ整合性）**: DLQへの移動ロジックが実装されている
  - `_move_to_dlq` メソッドが実装されている
  - `retry_count >= MAX_RETRY_COUNT` の場合にDLQへ移動するロジックが追加されている
  - knowledge_chunks_dlqテーブルへの移動処理が実装されている
- [ ] ⚠️ **改善（コード品質）**: メトリクス収集の具体実装が追加されている
  - prometheus-clientを使用したメトリクス定義が実装されている
  - ⚠️ 改善（運用性）: `/metrics`エンドポイントが実装されている（既存のヘルスチェックサーバーを拡張）
  - PrometheusメトリクスがHTTPエンドポイントで公開されている
  - `embedding_processing_duration` (Histogram)、`pending_chunks_gauge` (Gauge)、
    `embedding_errors_counter` (Counter) が定義されている
  - メトリクスの使用例（`@Histogram.time()`デコレータ等）が実装されている
- [ ] ⚠️ **改善（コード品質）**: ヘルスチェックが改善されている
  - pgvector拡張の動作確認が含まれている（`SELECT '[1,2,3]'::vector <=> '[1,2,3]'::vector`）
  - pgvector拡張のバージョン確認が含まれている
- [ ] ⚠️ **改善（コード品質）**: Graceful Shutdownが改善されている
  - session_archiverのGraceful Shutdownがembedding_processorと同様に詳細に定義されている
  - 処理中のアーカイブタスクの完了待機が実装されている
  - 並列処理中のタスクの完了待機が実装されている
- [ ] ⚠️ **改善（コード品質）**: 定数のハードコード散在が改善されている
  - pydantic-settingsで一元管理する計画が明確になっている
  - 環境変数からの読み込みが徹底されている
- [ ] ⚠️ **改善（コード品質）**: 型アノテーションが改善されている
  - `SearchResult` TypedDictが定義されている
  - `similarity_search` メソッドの戻り値が `list[SearchResult]` になっている
  - 型安全性が向上している
- [ ] ⚠️ **改善（コード品質）**: テスト計画の具体性が向上している
  - pytest-asyncioを使用した非同期フィクスチャの例が追加されている
  - pytest-dockerを使用したPostgreSQLコンテナの自動起動の例が追加されている
  - モックの具体実装例（バッチ処理、エラーケース、レート制限等）が追加されている
- [ ] ⚠️ **改善（テスト時のデータベースクリーンアップ）**: 並列テスト実行時の相互干渉を防ぐ実装がされている
  - TRUNCATE ... CASCADE を使用したクリーンアップ方式が実装されている（現段階では問題なし）
  - 将来的に pytest-xdist 等で並列テストを行う場合を考慮し、ロールバックパターンの実装例が提供されている
  - 各テストケースをトランザクション内で実行し、最後に
    ロールバックする方式（pytest-asyncio のフィクスチャで
    ロールバックパターン）が実装されている
  - ロールバックパターンを使用することで、並列テスト実行時でも
    相互干渉が発生せず、TRUNCATE よりも高速
- [ ] ⚠️ **改善（抽象化の粒度）**:
  DatabaseProtocolとKnowledgeBaseProtocolが分離されている
  - `DatabaseProtocol` はセッション管理のみを抽象化
    （`save_session`, `load_session`, `delete_session`,
    `load_all_sessions`）
  - `KnowledgeBaseProtocol` は知識ベース管理を抽象化
    （`similarity_search`, `save_source`, `save_chunk`）
  - 抽象化の粒度が均一になり、単一責任の原則に従っている
  - `PostgreSQLDatabase` が `DatabaseProtocol` と
    `KnowledgeBaseProtocol` の両方を実装している
- [ ] ⚠️ **改善（型定義の一貫性）**: sessionsテーブルのversionカラムの型定義が一貫している
  - DDLで `version INT DEFAULT 1` と定義されている
  - カラム詳細表でも `version INT DEFAULT 1` と記載されている
  - DDLのコメント部分にも `version INT DEFAULT 1` が含まれている
- [ ] ⚠️ **改善（セキュリティ）**: DATABASE_URL にパスワードを含める形式への依存を改善している
  - `asyncpg.create_pool()` で個別パラメータ（host, port, database, user, password）を使用できる
  - 本番環境では個別パラメータを使用し、パスワードを接続文字列に埋め込まない
  - 開発環境では接続文字列もサポート（後方互換性）
- [ ] ⚠️ **改善（セキュリティ）**: pgAdminの常時起動リスクを改善している
  - `PGADMIN_CONFIG_SERVER_MODE: 'True'` に設定されている（本番環境では必須、マルチユーザー認証を有効化）
  - `PGADMIN_CONFIG_ENHANCED_COOKIE_PROTECTION: 'True'` が設定されている（クッキー保護を強化）
  - `PGADMIN_CONFIG_LOGIN_BANNER: '"Authorized Access Only"'` が
    設定されている（ログインバナーを表示）
  - `profiles: ["admin"]` が設定されている（必要な時だけ起動）
- [ ] ⚠️ **改善（セキュリティ）**: エラーメッセージの情報漏洩リスクを改善している
  - `knowledge_sources` テーブルに `error_code` カラムが追加されている（エラーコードのみを保存）
  - `error_message` カラムには一般化されたメッセージのみを保存（詳細なスタックトレースはログのみに出力）
  - `_classify_error` メソッドが実装されている（エラーを分類してエラーコードを返す）
  - `_generalize_error_message` メソッドが実装されている（エラーメッセージを一般化する）
  - `_move_to_dlq` メソッドでエラーオブジェクトを受け取り、エラーコードと一般化されたメッセージのみを保存
- [ ] ⚠️ **改善（パフォーマンス）**: ハイブリッド検索のクエリ効率を改善している
  - `keyword_results` CTEにLIMITが設定されている（デフォルト: 100件）
  - 巨大なテーブルでも全文検索部分がボトルネックにならないように制限されている
  - `keyword_results`にも`embedding IS NOT NULL`条件が含まれている（コードレベルで強制）
- [ ] ⚠️ **改善（パフォーマンス）**: executemany のバッチサイズ制御が実装されている
  - チャンク一括登録時にバッチサイズを制限している（`KB_CHUNK_INSERT_BATCH_SIZE`、デフォルト: 100）
  - チャンク一括更新時にバッチサイズを制限している（`KB_CHUNK_UPDATE_BATCH_SIZE`、デフォルト: 100）
  - 巨大なセッション（数百チャンク）でもメモリ使用量を制御できる
- [ ] ⚠️ **改善（データ整合性）**: knowledge_sources と knowledge_chunks の整合性リスクを改善している
  - `source_status_enum`に`partial`ステータスを追加（一部のチャンクがDLQに移動した場合）
  - `_update_source_status`でDLQに移動したチャンクを確認し、`partial`ステータスを設定
  - `retry_count >= MAX_RETRY`のチャンクが存在する場合の扱いを明確化
- [ ] ⚠️ **改善（データ整合性）**: save_session での UPSERT ロジックを改善している
  - `save_session_with_optimistic_lock`メソッドを追加（楽観的ロック付きセッション保存）
  - `ON CONFLICT`で`version`をインクリメントする際、
    楽観的ロックのチェック（`WHERE version = $expected_version`）を実装
  - 通常のセッション更新では`save_session`を使用、
    アーカイブ処理など競合が発生する可能性がある場合は
    `save_session_with_optimistic_lock`を使用
- [ ] ⚠️ **改善（参照整合性）**: アーカイブ処理での参照整合性を改善している
  - ⚠️ 改善（疎結合）: `origin_session_id` カラム（外部キー）は削除し、`metadata` (JSONB) に記録
  - セッションアーカイブ時に `metadata` に `origin_session_id` と `origin_session_key` を記録
  - 理由: 「短期記憶（Sessions）」と「長期記憶（Knowledge）」はライフサイクルが異なるため、
    外部キー制約による強い依存関係を避け、知識として独立した存在として扱う
  - `metadata`内の`session_key`参照に加えて、外部キー参照も追加
- [ ] ⚠️ **改善（コード品質）**: 環境変数の os.getenv 呼び出しが分散している問題を改善している
  - `pydantic-settings`を最初から使用（Step 0で実装）
  - `src/kotonoha_bot/config.py`で`Settings`クラスを定義し、グローバルシングルトンとして管理
  - すべての設定管理で`os.getenv`の代わりに`settings`オブジェクトを使用
  - 型安全性とバリデーションが実装されている
  - デフォルト値が`Settings`クラスに一元管理されている
- [ ] ⚠️ **改善（コード品質）**: マジックナンバーの散在を改善している
  - `src/kotonoha_bot/constants.py`で定数を一箇所に集約（Step 0で実装例を追加済み）
  - タイムアウト値、LIMIT値、バッチサイズなどを定数化
  - SQL内のハードコードされた数値も定数から参照
  - すべての定数クラスが実装されている
    （`DatabaseConstants`, `SearchConstants`, `BatchConstants`,
    `EmbeddingConstants`, `ArchiveConstants`, `ErrorConstants`）
- [ ] ⚠️ **改善（コード品質）**: 例外処理の粒度が粗い問題を改善している
  - `src/kotonoha_bot/exceptions.py`で具体的な例外クラスを定義
  - `KotonohaError`基底クラスと、`DatabaseConnectionError`、
    `EmbeddingAPIError`などの具体的な例外
  - 広い`except Exception`を避け、具体的な例外をキャッチ
- [ ] ⚠️ **改善（パフォーマンス）**: 部分インデックスの活用が実装されている
  - `idx_chunks_queue` 部分インデックスが作成されている
    （WHERE embedding IS NULL AND retry_count < 3）
  - FOR UPDATE SKIP LOCKED を使うクエリで、テーブル全体をスキャンせずに
    処理対象を見つけられる
  - バッチ処理のパフォーマンスが最大化されている
- [ ] ⚠️ **改善（パフォーマンス）**: HNSWのビルドコストと maintenance_work_mem の対策が実装されている
  - docker-compose.yml または postgresql.conf で maintenance_work_mem が制限されている
  - インデックス構築時（INSERT/UPDATE時）とリストア時のOOM Killer対策が実装されている
  - システムメモリの10〜20%程度（最小128MB、最大1GB）に設定されている
- [ ] ベクトルインデックスの最適化が完了している（HNSW、パラメータ指定済み）
- [ ] 環境変数からHNSWパラメータが読み込まれる（`KB_HNSW_M`, `KB_HNSW_EF_CONSTRUCTION`）
- [ ] メタデータフィルタリング機能が動作する（チャンネルID、ユーザーIDなど）
- [ ] ENUMバリデーションによるSQLインジェクション対策が実装されている
- [ ] フィルタキーのAllow-list チェックが実装されている（`ALLOWED_FILTER_KEYS`）
- [ ] ⚠️ **重要**: 複数のソースタイプ指定に対応している（`source_types` フィルタ、IN句またはANY句を使用）
  - 例: `["web_page", "document_file"]` を指定した場合、
    `AND s.type = ANY($3::source_type_enum[])` を使用
  - ⚠️ 修正: `source_type = $x` ではなく
    `s.type = ANY($x::source_type_enum[])` を使用するようにSQLを修正
- [ ] 入力値の型チェックが実装されている（BIGINT型の検証）
- [ ] ⚠️ **重要**: ハイブリッド検索のクエリにも `embedding IS NOT NULL` 条件が含まれている
  - 安全チェック（コードレベルでの強制付与）が実装されている
- [ ] `KnowledgeBaseSearch` クラスが実装されている
- [ ] ⚠️ **重要**: halfvec固定採用でのINSERTとSELECTが正しく動作することを確認
  - `list[float]` から `halfvec` への型キャストが正しく動作することを確認
  - SQL内で `::halfvec(1536)` と明示的にキャストしていることを確認
  - ⚠️ **改善**: `constants.py` の `SearchConstants.VECTOR_CAST` と
    `SearchConstants.VECTOR_DIMENSION` を使用して統一

#### 知識ベーススキーマ（Step 4）

- [ ] `knowledge_sources` テーブルが作成される
- [ ] `knowledge_chunks` テーブルが作成される（`created_at` カラム含む）
- [ ] `KnowledgeBaseStorage` クラスが実装されている
- [ ] 高速保存機能（`save_message_fast`, `save_document_fast`）が動作する
- [ ] Source-Chunk構造が正しく実装されている
- [ ] ⚠️ **重要**: `knowledge_chunks.location` の構造が統一されている
  - 共通インターフェース（`url`, `label` フィールド）が定義されている
  - ソースタイプごとに適切な `url` と `label` が設定されている
  - 検索結果表示時にBotがリンクを生成できることを確認
- [ ] ⚠️ **重要**: halfvec固定採用でのembedding更新が正しく動作することを確認
  - `UPDATE knowledge_chunks SET embedding = $1::halfvec(1536)` が正しく動作することを確認

#### Embedding処理（Step 5）

- [ ] `EmbeddingProvider` インターフェースが定義されている
- [ ] `OpenAIEmbeddingProvider` が実装されている
- [ ] Embedding APIのリトライロジックが実装されている（tenacity使用）
- [ ] `EmbeddingProcessor` クラスが実装されている
- [ ] バックグラウンドタスクが動作する
- [ ] セマフォによる同時実行数制限が実装されている
  - EmbeddingProcessorの初期化時にセマフォを作成（max_concurrentで制限）
  - `_generate_embedding_with_limit`メソッド内で `async with self._semaphore:` を使用
  - SessionArchiverでも同様にセマフォを使用（DB_POOL_MAX_SIZEの20〜30%程度に制限）
- [ ] ⚠️ **重要**: `FOR UPDATE SKIP LOCKED` パターンが実装されている
  （DBレベルの排他制御、スケールアウト対応）
- [ ] ⚠️ **重要**: トランザクション内でのAPIコールを回避している
  - Tx1: FOR UPDATE SKIP LOCKED で対象行を取得し、IDとcontentをメモリに保持して即コミット
  - No Tx: OpenAI API コール（時間かかる処理、トランザクション外で実行）
  - Tx2: 結果を UPDATE（別トランザクション）
  - これにより、接続プールの枯渇や他のクエリのブロックを防ぐ
- [ ] asyncio.Lockによる競合状態対策が実装されている（単一プロセス用の補助）
- [ ] Graceful Shutdownが実装されている
- [ ] ⚠️ **重要**: halfvec固定採用でのembedding更新が正しく動作することを確認
  - `UPDATE knowledge_chunks SET embedding = $1::halfvec(1536)` が正しく動作することを確認
  - `list[float]` から `halfvec` への型キャストが正しく動作することを確認

#### セッション知識化処理（Step 5）

- [ ] `SessionArchiver` クラスが実装されている
- [ ] セッション知識化処理が動作する
  （非アクティブなセッションが自動的に知識ベースに変換される）
- [ ] ⚠️ **重要**: `SessionArchiver._archive_session` で、知識ベースへの登録と
  セッションステータス更新が同一トランザクション内で実行されている
  （アトミック性の保証）
- [ ] トランザクション分離レベルが `REPEATABLE READ` に設定されている
  （楽観的ロックのため）
- [ ] ⚠️ **重要**: 楽観的ロックの競合時の自動リトライが実装されている
  （tenacity ライブラリを使用、指数バックオフ付き、最大3回リトライ）
- [ ] ⚠️ **重要**: セッションアーカイブの並列処理で、セマフォの上限が
  DB_POOL_MAX_SIZE の20〜30%程度に厳密に制限されている
  （接続枯渇対策: Archive処理だけでプールを食い尽くすリスクを防止）
- [ ] ⚠️ **推奨**: 接続プールの分離を検討（大規模運用時）
  - バックグラウンドタスク（Embedding, Archive）用の asyncpg.Pool と、
    Web/Bot応答用のプールを分ける選択肢もある
  - 現状はセマフォによる動的制限で対応（小規模運用では十分）
- [ ] ⚠️ **重要**: Bot再起動時のバーストを防ぐため、セッションアーカイブタスクの
  before_loop にランダムな遅延（0〜60秒）を追加している
  （起動直後の大量アーカイブ処理を分散）
- [ ] トークン数チェックと分割処理が実装されている
- [ ] Recursive Character Splitter方式によるテキスト分割が実装されている
  （句読点・改行を優先）
- [ ] `langchain-text-splitters` の導入前提を理解し、実装に使用している
- [ ] フィルタリングロジック（短いセッション、Botのみのセッション除外）が実装されている

#### 依存関係とパッケージ管理

- [ ] `langchain-text-splitters>=1.1.0` がインストールされている
- [ ] `pydantic-settings>=2.12.0` がインストールされている
- [ ] `pgvector>=0.3.0` がインストールされている（asyncpgへの型登録用）
- [ ] `asyncpg>=0.31.0` がインストールされている（必須: 0.29.0未満だと問題が発生する可能性あり）
- [ ] `asyncpg-stubs>=0.31.1` がdev依存関係としてインストールされている
- [ ] `structlog>=25.5.0` がインストールされている（構造化ログ用）
- [ ] `prometheus-client>=0.24.1` がインストールされている（メトリクス収集用）
- [ ] `orjson>=3.11.5` がインストールされている（高速JSON処理用）
- [ ] `tenacity>=9.1.2` がインストールされている（リトライロジック用、楽観的ロック競合時の自動リトライに使用）
- [ ] ⚠️ **重要**: `alembic>=1.13.0` がインストールされている（スキーママイグレーション管理、フェーズ8開始時から必須）

#### Docker Compose（Step 6）

- [ ] `docker-compose.yml` に PostgreSQL サービスが追加されている
- [ ] ⚠️ **推奨**: `Dockerfile.postgres` でマルチステージビルドを使用している
  （ビルドキャッシュ最適化: ビルド依存関係とビルド済みpg_bigmを分離）
- [ ] ⚠️ **推奨**: Dockerのビルド時間短縮のため、レイヤーキャッシュが効くように
  Dockerfileの記述順序を最適化している（依存関係の変更が少ない順に配置）
- [ ] 各パッケージの導入前提と利用効果を理解している
- [ ] 型チェック（`ty` または `mypy`）で `asyncpg-stubs` の効果が確認できる
- [ ] `pgvector.asyncpg.register_vector()` による型登録が実装されている
- [ ] JSONBコーデック（orjson使用）が実装されている
- [ ] datetimeオブジェクトのシリアライズが正しく実装されている（`model_dump(mode='json')`使用）
- [ ] `pgvector/pgvector:0.8.1-pg18` イメージが使用されている、またはカスタムイメージがビルドされている
- [ ] 環境変数が正しく設定されている
  （`DATABASE_URL`, `DB_POOL_MIN_SIZE`, `DB_POOL_MAX_SIZE`,
  `DB_COMMAND_TIMEOUT`, `KB_HNSW_M`, `KB_HNSW_EF_CONSTRUCTION`等）
- [ ] ボリュームマウントとネットワーク設定が正しく設定されている
- [ ] 名前付きボリューム（`postgres_data`）を使用しており、バインドマウントによる権限問題を回避している
- [ ] メモリ設定が適切（HNSWインデックスとpg_dump実行時のメモリ使用量を考慮）
- [ ] PostgreSQL コンテナが起動する
- [ ] PostgreSQL のヘルスチェックが設定されている
- [ ] ⚠️ **推奨**: pgAdmin が追加されている
  （`dpage/pgadmin4` イメージ、`profiles: ["admin"]` で設定）
- [ ] pgAdmin の環境変数が設定されている（`PGADMIN_DEFAULT_EMAIL`, `PGADMIN_DEFAULT_PASSWORD`）
- [ ] pgAdmin のセキュリティ設定が適切（`PGADMIN_CONFIG_MASTER_PASSWORD_REQUIRED=True`）
- [ ] pgAdmin のポートマッピングが設定されている（例: `5050:80`）
- [ ] pgAdmin が起動し、PostgreSQL に接続できる（`docker-compose --profile admin up -d` で起動）
- [ ] バックアップ戦略が実装されている（pg_dump等）
- [ ] ⚠️ **重要**: バックアップスクリプトで権限問題への対策が実装されている
  - 推奨: `docker exec` + `docker cp` を使用した方法（権限問題を完全に回避）
- [ ] `.env.example` ファイルが作成されている

#### テスト（Step 7）

- [ ] PostgreSQL 用のテストフィクスチャが追加されている
- [ ] すべてのテストが通過する（既存の 137 テストケース + 新規テスト）
- [ ] 既存の機能が正常に動作する（回帰テスト）
- [ ] パフォーマンステストが実施されている（ベクトル検索の性能測定、HNSWインデックスの効果確認）
- [ ] インデックスの最適化が完了している（HNSWパラメータの調整、環境変数で制御）
- [ ] 接続プールの調整が完了している（`min_size`, `max_size`、環境変数で制御）
- [ ] OpenAI APIのモックが実装されている（CI/CD対応）
- [ ] 型チェック（`ty` または `mypy`）が通過する（`asyncpg-stubs` の効果を確認）

### 7.2 品質チェックコマンド

```bash
# 型チェック（asyncpg-stubs の効果を確認）
uv run ty src/

# リントチェック
uv run ruff check src/ tests/

# テスト実行（カバレッジ付き）
uv run pytest --cov=src/kotonoha_bot --cov-report=term-missing

# PostgreSQL接続確認
docker-compose exec postgres psql -U kotonoha -d kotonoha -c "SELECT version();"

# 依存関係の確認
uv pip list | grep -E "(langchain-text-splitters|pydantic-settings|" \
  "asyncpg-stubs)"
```

---

## 8. リスク管理

> **参照**: 詳細なリスク管理については、
> [PostgreSQL スキーマ設計書 - 16. リスク管理](../architecture/postgresql-schema-design.md#16-リスク管理)
> および
> [17. Synology NAS特有の課題と対策](../architecture/postgresql-schema-design.md#17-synology-nas特有の課題と対策)
> を参照してください。

このセクションでは、実装時に注意すべき主要なリスクと対策の概要を説明します。

### 8.1 主要なリスク概要

詳細なリスク一覧と対策については、
[PostgreSQL スキーマ設計書 - 16.1 リスク一覧](../architecture/postgresql-schema-design.md#161-リスク一覧)
を参照してください。

主なリスク：

- **リソース不足**: メモリ監視とリソース制限の適切な設定が必要
- **データ整合性の問題**: テストの実施とデータ検証の実装が必要
- **Embedding API のレート制限**: バッチ処理とレート制限対策が必要
- **トークン数超過エラー**: tiktokenによる事前チェックと分割処理が必要
- **SQLインジェクション**: ENUMバリデーションとパラメータ化クエリの徹底が必要
- **メモリ使用量の増大**: halfvecの採用とリソース監視が必要

### 8.2 Synology NAS特有の課題

Synology NAS特有の課題と対策の詳細については、
[PostgreSQL スキーマ設計書 - 17. Synology NAS特有の課題と対策](../architecture/postgresql-schema-design.md#17-synology-nas特有の課題と対策)
を参照してください。

主な課題：

- **postgres_data の権限問題**: 名前付きボリュームの使用を推奨
- **メモリ設定**: HNSWインデックスとpg_dump実行時のメモリ使用量を考慮した設定が必要

---

## 9. スキーマバージョン管理とコスト見積もり

### 9.1 スキーマバージョン管理

**決定事項**: ✅ **フェーズ8開始時からAlembicを導入する**（必須）

**Alembic の導入手順**:

1. **依存関係の追加**:

   ```toml
   # pyproject.toml
   dependencies = [
       # ... 既存の依存関係 ...
       "alembic>=1.13.0",  # スキーママイグレーション管理
   ]
   ```

2. **Alembicの初期化**（Step 0またはStep 2で実施）:

   ```bash
   # Alembicの初期化
   alembic init alembic
   ```

3. **初回マイグレーションの作成**:

   ```bash
   # 初回マイグレーション（スキーマ設計書のDDLをベースに作成）
   alembic revision --autogenerate -m "Initial schema"
   ```

4. **マイグレーションの適用**:

   ```bash
   # マイグレーションの適用
   alembic upgrade head
   ```

5. **PostgreSQLDatabase.initialize()での自動適用**:

   ```python
   # src/kotonoha_bot/db/postgres.py
   async def initialize(self) -> None:
       """データベースの初期化"""
       # ... 接続プールの作成 ...
       
       # Alembicマイグレーションの自動適用
       from alembic.config import Config
       from alembic import command
       
       alembic_cfg = Config("alembic.ini")
       command.upgrade(alembic_cfg, "head")
   ```

**スキーマ変更時の手順**:

1. スキーマを変更（テーブル追加、カラム追加など）
2. マイグレーションスクリプトを自動生成:

   ```bash
   alembic revision --autogenerate -m "Add new column to sessions"
   ```

3. 生成されたマイグレーションスクリプトをレビュー
4. マイグレーションを適用:

   ```bash
   alembic upgrade head
   ```

**注意事項**:

- **初回実装時**: スキーマ設計書のDDLをベースに初回マイグレーションを作成
- **スキーマ変更時**: 必ずAlembicマイグレーションを作成（手動DDL実行を避ける）
- **本番環境**: マイグレーション適用前にバックアップを取得

### 9.2 OpenAI Embedding API のコスト見積もり

> **参照**: 詳細なコスト見積もりについては、
> [PostgreSQL スキーマ設計書 - 15. コスト見積もり](../architecture/postgresql-schema-design.md#15-コスト見積もり)
> を参照してください。

**コスト見積もり概要**:

```text
# OpenAI text-embedding-3-small の料金（2026年1月時点）
- 料金: $0.02 / 1M tokens

# 想定シナリオ
- 1セッション平均: 1,000 tokens
- 1日あたりのセッション数: 1,000 セッション
- 1日あたりのコスト: $0.02
- 1ヶ月あたりのコスト: $0.60

# フィルタリング効果（短いセッション除外）
- フィルタリングにより50%削減を想定
- 1ヶ月あたりのコスト: $0.30
```

詳細なコスト管理の推奨事項については、上記の設計書を参照してください。

---

## 10. 導入・デプロイ手順

### 10.1 開発環境での導入

**docker-compose.yml による一括管理**:

`docker-compose.yml` があれば、3つのコンテナ（kotonoha-bot、postgres、pgadmin）を1つのコマンドで管理できます。

#### 方法1: すべてのコンテナを一括起動（推奨）

```bash
# すべてのサービスを起動
docker-compose up -d

# ログを確認
docker-compose logs -f

# すべてのサービスを停止
docker-compose down

# ボリュームも含めて完全に削除（注意: データが消えます）
docker-compose down -v
```

#### 方法2: 個別に起動

```bash
# PostgreSQL のみ起動
docker-compose up -d postgres

# pgAdmin のみ起動
docker-compose up -d pgadmin

# Bot のみ起動（PostgreSQLが起動している必要がある）
docker-compose up -d kotonoha-bot
```

#### 環境変数の設定

`.env` ファイルを作成（`.env.example` を参考に）:

```bash
# .env ファイル
DISCORD_TOKEN=your_discord_token_here
# 注意: パスワードは強固なものに変更してください（最低32文字推奨）
DATABASE_URL=postgresql://kotonoha:CHANGE_THIS_STRONG_PASSWORD_32CHARS_MIN@postgres:5432/kotonoha
POSTGRES_PASSWORD=CHANGE_THIS_STRONG_PASSWORD_32CHARS_MIN
OPENAI_API_KEY=your_openai_api_key_here
PGADMIN_EMAIL=admin@kotonoha.local
PGADMIN_PASSWORD=CHANGE_THIS_STRONG_PASSWORD_32CHARS_MIN
```

または、環境変数を直接設定:

```bash
# 注意: パスワードは強固なものに変更してください
export DATABASE_URL=postgresql://kotonoha:CHANGE_THIS_STRONG_PASSWORD_32CHARS_MIN@postgres:5432/kotonoha
export POSTGRES_PASSWORD=CHANGE_THIS_STRONG_PASSWORD_32CHARS_MIN
export OPENAI_API_KEY=your_api_key
```

#### 動作確認

```bash
# すべてのコンテナの状態を確認
docker-compose ps

# PostgreSQL のログを確認
docker-compose logs postgres

# Bot のログを確認
docker-compose logs kotonoha-bot

# pgAdmin にアクセス（ブラウザで）
# http://localhost:5050
```

**確認項目**:

- Botが正常に起動することを確認
- PostgreSQL に接続できることを確認
- 新規セッションが作成できることを確認
- pgAdmin から PostgreSQL に接続できることを確認

### 10.2 本番環境でのデプロイ

**docker-compose.yml による一括管理**:

本番環境でも、`docker-compose.yml` を使用してすべてのコンテナを一括管理できます。

1. **環境変数の設定**:
   - 本番環境の `.env` ファイルを作成（シークレットマネージャーから取得）
   - または、環境変数を直接設定
   - `DATABASE_URL` を本番環境のPostgreSQLに設定
   - `OPENAI_API_KEY` を設定
   - `POSTGRES_PASSWORD` を強力なパスワードに設定

2. **すべてのコンテナを一括起動**:

   ```bash
   # すべてのサービスを起動（バックグラウンド）
   docker-compose up -d
   
   # または、個別に起動
   docker-compose up -d postgres
   docker-compose up -d kotonoha-bot
   # 注意: 本番環境ではpgAdminは通常含めない
   ```

3. **コンテナの状態確認**:

   ```bash
   # すべてのコンテナの状態を確認
   docker-compose ps
   
   # ログを確認
   docker-compose logs -f kotonoha-bot
   docker-compose logs -f postgres
   
   # ヘルスチェックの確認
   docker-compose ps
   # postgres の STATUS が "healthy" になっていることを確認
   ```

4. **動作確認**:
   - Botが正常に起動することを確認
   - PostgreSQL に接続できることを確認
   - 既存機能が正常に動作することを確認
   - 新規機能（知識ベース、ベクトル検索）が動作することを確認

5. **メンテナンスコマンド**:

   ```bash
   # Botコンテナのみ再起動
   docker-compose restart kotonoha-bot
   
   # すべてのコンテナを再起動
   docker-compose restart
   
   # コンテナを停止（データは保持される）
   docker-compose stop
   
   # コンテナを起動
   docker-compose start
   ```

---

## 11. 将来の改善計画

### 11.1 Phase 8.5: ハイブリッド検索の実装（推奨）

**背景**: 現在の「ベクトル検索のみ」の実装は、特定のキーワード
（例：「エラーコード 500」「変数名 my_var」）の検索に弱点があります。
pg_bigm を使用したハイブリッド検索を実装することで、
検索品質が大幅に向上します。

⚠️ **重要**: 日本語検索においては、**pg_bigm** を強く推奨します。

#### 11.1.1 pg_bigm の採用

**pg_bigm の利点**:

- **2-gram（2文字単位）**: 日本語の多くは2文字以上の熟語で構成されるため、検索漏れがほぼゼロ
- **2文字の単語に対応**: 「設計」「開発」のような2文字の単語も確実に検索可能
- **LIKE演算子の高速化**: PostgreSQL標準の `LIKE '%...%'` 検索を爆速化
- **pg_trgm との違い**: pg_trgm（3-gram）は2文字の単語が検索漏れしたり、精度が出にくい場合がある

**pg_trgm の限界**:

- 3文字単位のため、「設計」「開発」のような2文字の単語の検索が苦手
- ひらがなの助詞などがノイズになりやすい

**実装方針**:

- Phase 8 の `_create_indexes` メソッドで既に pg_bigm 拡張とインデックスの作成を実装済み
- Phase 8.5 でハイブリッド検索クエリの実装を追加
- Dockerfile.postgres で pg_bigm をビルドしてカスタムイメージを作成

##### ⚠️ 改善（コード品質）: 定数と例外の定義

実装前に、以下のファイルを作成することを推奨します：

```python
# src/kotonoha_bot/constants.py
"""定数の一箇所集約（マジックナンバーの散在を防ぐ）"""

class DatabaseConstants:
    """データベース関連の定数"""
    POOL_ACQUIRE_TIMEOUT = 30.0  # 接続プール取得のタイムアウト（秒）
    GRACEFUL_SHUTDOWN_TIMEOUT = 60.0  # Graceful shutdownのタイムアウト（秒）

class SearchConstants:
    """検索関連の定数"""
    VECTOR_CAST = "halfvec"  # ベクトル型キャスト（halfvec固定採用）
    VECTOR_DIMENSION = 1536  # ベクトル次元数（OpenAI text-embedding-3-small）
    VECTOR_SEARCH_CANDIDATE_LIMIT = 50  # ベクトル検索の候補数（ハイブリッド検索用）
    KEYWORD_SEARCH_LIMIT = 100  # キーワード検索の上限（ハイブリッド検索用）

class BatchConstants:
    """バッチ処理関連の定数"""
    BATCH_INSERT_SIZE = 100  # チャンク一括登録のバッチサイズ
    BATCH_UPDATE_SIZE = 100  # チャンク一括更新のバッチサイズ
```

```python
# src/kotonoha_bot/exceptions.py
"""カスタム例外クラス（例外処理の粒度を細かく）"""

class KotonohaError(Exception):
    """基底例外クラス"""
    pass

class DatabaseError(KotonohaError):
    """データベース関連のエラー"""
    pass

class DatabaseConnectionError(DatabaseError):
    """DB接続エラー"""
    pass

class EmbeddingAPIError(KotonohaError):
    """Embedding API エラー"""
    pass

class EmbeddingRateLimitError(EmbeddingAPIError):
    """レート制限エラー"""
    pass

class EmbeddingTimeoutError(EmbeddingAPIError):
    """タイムアウトエラー"""
    pass

# 使用例
try:
    await self.embedding_provider.generate_embedding(text)
except openai.RateLimitError as e:
    raise EmbeddingRateLimitError(f"Rate limited: {e}") from e
except openai.APITimeoutError as e:
    raise EmbeddingTimeoutError(f"API timeout: {e}") from e
except openai.APIError as e:
    raise EmbeddingAPIError(f"API error: {e}") from e
except Exception as e:
    # 予期しないエラーは基底クラスでキャッチ
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise KotonohaError(f"Unexpected error: {e}") from e
```

**ハイブリッド検索の実装例**:

```python
# src/kotonoha_bot/features/knowledge_base/hybrid_search.py
"""ハイブリッド検索（ベクトル検索 + pg_bigm キーワード検索）"""

async def hybrid_search(
    self,
    query: str,
    query_embedding: list[float],
    top_k: int = 10,
    vector_weight: float = 0.7,
    keyword_weight: float = 0.3,
    ) -> list[SearchResult]:
        """ハイブリッド検索を実行
        
        ⚠️ 改善（コード品質）: 戻り値の型を明確化
        list[dict] は曖昧なため、SearchResult TypedDictを使用して型安全性を向上
    
    ⚠️ 重要: pg_bigm は LIKE 演算子でインデックスが効くため、
    クエリキーワードの前後に % をつけて部分一致にする
    
    Args:
        query: 検索クエリ（テキスト）
        query_embedding: クエリのベクトル（1536次元）
        top_k: 取得する結果の数
        vector_weight: ベクトル類似度の重み（デフォルト: 0.7）
        keyword_weight: キーワード類似度の重み（デフォルト: 0.3）
    
    Returns:
        検索結果のリスト（combined_score でソート済み）
    """
    # ⚠️ 改善（コード品質）: pydantic-settings と定数を使用
    from ..constants import SearchConstants
    
    # ⚠️ 重要: halfvec固定採用（constants.pyの定数を使用）
    vector_cast = SearchConstants.VECTOR_CAST
    vector_dimension = SearchConstants.VECTOR_DIMENSION
    
    # pg_bigm は LIKE 演算子でインデックスが効く
    # クエリキーワードの前後に % をつけて部分一致にする
    like_query = f"%{query}%"
    
    async with self.db.pool.acquire() as conn:
        # ベクトル検索とキーワード検索のスコアを組み合わせ（UNION ALL方式で最適化）
        # ⚠️ 改善: FULL OUTER JOINは両方のCTEを完全評価するため非効率
        # UNION ALLを使用した方が効率的
        # ⚠️ 重要: クエリ文字列を変数に保存して、安全チェックを実行
        query_str = f"""
            WITH vector_results AS (
                SELECT 
                    c.id,
                    c.source_id,
                    c.content,
                    s.type as source_type,
                    s.title,
                    s.uri,
                    s.metadata as source_metadata,
                    1 - (c.embedding <=> $1::{vector_cast}(
                        {vector_dimension})) AS vector_similarity
                FROM knowledge_chunks c
                JOIN knowledge_sources s ON c.source_id = s.id
                WHERE c.embedding IS NOT NULL
                    -- ⚠️ 必須: HNSWインデックス使用のため
                    -- （コードレベルで強制）
                ORDER BY c.embedding <=> $1::{vector_cast}(
                    {vector_dimension})
                LIMIT {SearchConstants.VECTOR_SEARCH_CANDIDATE_LIMIT}
                    -- ⚠️ 改善（コード品質）: マジックナンバーを定数化
            ),
            keyword_results AS (
                SELECT 
                    c.id,
                    c.source_id,
                    c.content,
                    s.type as source_type,
                    s.title,
                    s.uri,
                    s.metadata as source_metadata,
                    1.0 AS keyword_score  -- ヒットしたらスコア1.0（重み付けで調整）
                FROM knowledge_chunks c
                JOIN knowledge_sources s ON c.source_id = s.id
                WHERE c.content LIKE $2  -- pg_bigm インデックスが使用される
                  AND c.embedding IS NOT NULL
                      -- ⚠️ 必須: ハイブリッド検索でもベクトル検索結果と
                      -- 統合するため（コードレベルで強制）
                  -- ⚠️ 注意: pg_bigm はテキストに対するインデックスであり、embedding カラムとは無関係です。
                  -- キーワード検索（LIKE検索）自体は embedding が
                  -- NULL でも可能です（まだベクトル化されていない
                  -- 最新データなど）。
                  -- しかし、整合性を保つため「ベクトル化完了したもののみ検索対象」とする設計方針を採用しています。
                  -- この方針により、ベクトル検索結果とキーワード検索結果を統合する際の一貫性が保たれます。
                LIMIT {SearchConstants.KEYWORD_SEARCH_LIMIT}
                    -- ⚠️ 改善（コード品質）: マジックナンバーを定数化
            ),
            combined AS (
                SELECT 
                    id, source_id, content, source_type, title, uri, source_metadata,
                    vector_similarity * $3 AS score 
                FROM vector_results
                UNION ALL
                SELECT 
                    id, source_id, content, source_type, title, uri, source_metadata,
                    keyword_score * $4 AS score 
                FROM keyword_results
            )
            SELECT 
                id AS chunk_id,
                source_id,
                content,
                source_type,
                title,
                uri,
                source_metadata,
                SUM(score) AS combined_score
            FROM combined
            GROUP BY id, source_id, content, source_type, title, uri, source_metadata
            ORDER BY combined_score DESC
            LIMIT $5
        """
        
        # ⚠️ 安全チェック: クエリに embedding IS NOT NULL が含まれていることを確認
        # 実装漏れを防ぐための防御的プログラミング
        # ハイブリッド検索でもベクトル検索結果と統合するため、embedding IS NOT NULL 条件は必須
        if "embedding IS NOT NULL" not in query_str.upper():
            raise ValueError(
                "CRITICAL: embedding IS NOT NULL condition is missing "
                "in hybrid search query. "
                "This would cause full table scan and timeout in production.")
        
        rows = await conn.fetch(
            query_str, query_embedding, like_query, vector_weight,
            keyword_weight, top_k)
        
        return [
            {
                "chunk_id": row["chunk_id"],
                "source_id": row["source_id"],
                "content": row["content"],
                "source_type": row["source_type"],
                "title": row["title"],
                "uri": row["uri"],
                "source_metadata": row["source_metadata"],
                "combined_score": float(row["combined_score"]),
            }
            for row in rows
        ]
```

**Dockerfile.postgres の作成**:

pg_bigm は標準の PostgreSQL イメージには含まれていないため、
pgvector のイメージをベースにして、pg_bigm をコンパイルして追加した
カスタムイメージを作成する必要があります。

⚠️ **重要**: フェーズ8では開発環境・本番環境ともにpg_bigmを含む
カスタムイメージを使用します。標準のpgvectorイメージは使用せず、
常にこのカスタムイメージをビルドして使用してください。

```dockerfile
# Dockerfile.postgres
# ⚠️ ビルドキャッシュ最適化: マルチステージビルドとレイヤーキャッシュを活用

# Stage 1: ビルド環境（ビルド依存関係とpg_bigmのコンパイル）
# ⚠️ 重要（本番環境の推奨）: PostgreSQL 18は2025年Q3（秋）リリース予定で、運用実績が限定的
# pgvector 0.8.1 との組み合わせの本番実績が少ないため、本番環境ではPostgreSQL 17を推奨
# 開発・検証環境: pgvector/pgvector:0.8.1-pg18
# 本番環境推奨: pgvector/pgvector:0.8.0-pg17（postgresql-server-dev-17に変更）
FROM pgvector/pgvector:0.8.1-pg18 AS builder  # 開発・検証用（本番は0.8.0-pg17を推奨）

# pg_bigm のバージョン
ARG PG_BIGM_VERSION=1.2-20240606
ARG PG_BIGM_CHECKSUM=""  # オプション: チェックサム検証用
ARG PG_BIGM_URL="https://github.com/pgbigm/pg_bigm/archive/refs/tags/v${PG_BIGM_VERSION}.tar.gz"

USER root

# ビルド依存関係のインストール（レイヤーキャッシュのため、依存関係の変更が少ない順に配置）
RUN apt-get update && apt-get install -y \
    build-essential \
    postgresql-server-dev-18 \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# pg_bigm のダウンロードとインストール
# ⚠️ ビルドキャッシュ最適化: ダウンロードとビルドを分離して
# レイヤーキャッシュを活用
RUN wget -O pg_bigm.tar.gz "$PG_BIGM_URL" \
    && if [ -n "$PG_BIGM_CHECKSUM" ]; then \
        echo "$PG_BIGM_CHECKSUM  pg_bigm.tar.gz" | sha256sum -c - || exit 1; \
    fi \
    && mkdir -p /usr/src/pg_bigm \
    && tar -xzf pg_bigm.tar.gz -C /usr/src/pg_bigm --strip-components=1

# pg_bigm のビルド（ソースコードの変更がない限り、このレイヤーはキャッシュされる）
WORKDIR /usr/src/pg_bigm
RUN make USE_PGXS=1 && make USE_PGXS=1 install

# Stage 2: 実行環境（ビルド済みのpg_bigmのみを含む軽量イメージ）
# ⚠️ 重要（本番環境の推奨）: PostgreSQL 18は2025年Q3（秋）リリース予定で、運用実績が限定的
# 本番環境ではPostgreSQL 17を推奨（postgresql/18をpostgresql/17に変更）
FROM pgvector/pgvector:0.8.1-pg18  # 開発・検証用（本番は0.8.0-pg17を推奨）

USER root

# ビルド済みのpg_bigmをコピー（ビルド依存関係は含めない）
COPY --from=builder /usr/share/postgresql/18/extension/pg_bigm* /usr/share/postgresql/18/extension/
COPY --from=builder /usr/lib/postgresql/18/lib/pg_bigm.so /usr/lib/postgresql/18/lib/

# postgres ユーザーに戻す
USER postgres

# ⚠️ ビルドキャッシュ最適化のメリット:
# - ビルド依存関係のインストールレイヤーは、依存関係が変更されない限りキャッシュされる
# - pg_bigmのソースコードが変更されない限り、ビルドレイヤーもキャッシュされる
# - 実行環境は軽量で、ビルド依存関係を含まないため、イメージサイズが小さい
```

**docker-compose.yml の修正**:

フェーズ8では、開発環境・本番環境ともにpg_bigmを含むカスタムイメージを使用します。

```yaml
services:
  postgres:
    # ⚠️ 重要: 開発環境・本番環境ともにpg_bigmを含むカスタムイメージを使用
    # 標準のpgvectorイメージは使用せず、常にカスタムイメージをビルドして使用
    build:
      context: .
      dockerfile: Dockerfile.postgres
    container_name: kotonoha-postgres
    # ... (その他の設定はそのまま)
```

**注意点とデメリット**:

1. **インデックスサイズ**: pg_bigm のインデックスは pg_trgm よりも
   大きくなる傾向があります（2文字の組み合わせの方が3文字よりも
   多いため）
   - **対策**: NASのストレージ容量には注意してください。
     ただしテキストデータのみのインデックスなので、
     ベクトルデータ（HNSW）に比べればそこまで巨大にはなりません。

2. **更新速度**: インデックス作成・更新にかかるCPU負荷が若干高いです。
   - **対策**: Botの知識化処理はバックグラウンドで行われるため、ユーザー体験への影響は軽微です。

3. **1文字検索**: pg_bigm は「2文字」のインデックスですが、1文字の検索も可能です（全件スキャンよりはマシですが、少し遅くなります）。
   - **実用上の問題**: 日本語検索において1文字検索（例：「あ」だけ検索）の需要は低いため、実用上は問題ありません。

**完了基準**:

- [ ] Dockerfile.postgres で pg_bigm をビルドしてカスタムイメージを作成
- [ ] docker-compose.yml でカスタムイメージを使用
- [ ] pg_bigm 拡張が有効化されている
- [ ] `idx_chunks_content_bigm` インデックスが作成されている
- [ ] ハイブリッド検索メソッドが実装されている
- [ ] ベクトル検索とキーワード検索のスコアを組み合わせた検索が動作する
- [ ] 検索品質の向上が確認できる（固有名詞の検索精度が向上、2文字の単語も確実に検索可能）

### 11.2 Phase 9: Reranking の実装（オプション）

**背景**: ベクトル検索でTop-20を取得した後、軽量なCross-Encoder（Reranker）でTop-5に絞り込むと、精度が劇的に向上します。

**実装方針**:

- ベクトル検索でTop-20を取得
- Cross-Encoder（例: `cross-encoder/ms-marco-MiniLM-L-6-v2`）で再ランキング
- Top-5を返す

**注意事項**:

- Synology NASのCPU負荷が許せば検討に値します
- Reranker は CPU 集約的な処理のため、大量のリクエストがある場合は注意が必要
- オプション機能として実装し、環境変数で有効/無効を切り替え可能にする

**実装例**:

```python
# src/kotonoha_bot/features/knowledge_base/reranker.py
"""Reranking による検索精度向上"""

from sentence_transformers import CrossEncoder

class Reranker:
    """Cross-Encoder による再ランキング"""
    
    def __init__(
        self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    ):
        self.model = CrossEncoder(model_name)
    
    def rerank(
        self,
        query: str,
        candidates: list[dict],
        top_k: int = 5,
    ) -> list[SearchResult]:
        """検索候補を再ランキング
        
        Args:
            query: 検索クエリ
            candidates: 検索候補のリスト（各要素は content キーを持つ）
            top_k: 返す結果の数
        
        Returns:
            再ランキングされた結果のリスト
        """
        if not candidates:
            return []
        
        # Cross-Encoder でスコアを計算
        pairs = [[query, candidate["content"]] for candidate in candidates]
        scores = self.model.predict(pairs)
        
        # スコアでソート
        reranked = sorted(
            zip(candidates, scores),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Top-k を返す
        return [
            {**candidate, "rerank_score": float(score)}
            for candidate, score in reranked[:top_k]
        ]
```

**使用例**:

```python
# ベクトル検索でTop-20を取得
vector_results = await self.db.similarity_search(
    query_embedding=query_embedding,
    top_k=20,
)

# Reranker でTop-5に絞り込む
reranker = Reranker()
final_results = reranker.rerank(
    query=query,
    candidates=vector_results,
    top_k=5,
)
```

**完了基準**:

- [ ] Cross-Encoder モデルがロードされる
- [ ] Reranking メソッドが実装されている
- [ ] ベクトル検索の結果を再ランキングできる
- [ ] 環境変数で有効/無効を切り替え可能
- [ ] CPU負荷が許容範囲内であることを確認
- [ ] 検索精度の向上が確認できる

---

**作成日**: 2026年1月19日
**最終更新日**: 2026年1月19日
