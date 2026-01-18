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

#### 約 10-15 日

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

**重要**: このフェーズは**新規設計**です。SQLiteからの移行ツールは作成せず、既存のデータは破棄します。

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

1. **拡張性**: 将来「動画検索」を入れたくなっても、`source_type` に `video` を足すだけで、テーブル構造を変える必要がありません
2. **メタデータの柔軟性**: JSONB (`metadata`, `location`) を使うことで、
   ファイルの種類ごとに異なる属性（PDFのページ番号、音声の秒数など）を
   無理なく管理できます
3. **状態管理**: `status` カラムがあるため、OCRやEmbeddingなどの「重い処理」を
   バックグラウンドワーカーに任せる設計（Producer-Consumerパターン）が
   容易に組めます

### 3.3 非同期Embedding処理

**高速保存パターン**:

1. **即時保存**: テキストのみ保存（`embedding=NULL`）
2. **バックグラウンド処理**: 定期タスクでベクトル化して更新
3. **検索時**: `embedding IS NOT NULL` のもののみ検索対象

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
       "pydantic-settings>=2.12.0", # 型安全な設定管理（⚠️ 即時導入推奨）
       "tiktoken>=0.12.0",          # トークン数カウント用
       "tenacity>=9.1.2",           # リトライロジック用
       "structlog>=25.5.0",         # 構造化ログ（JSON形式、パフォーマンス向上）
       "prometheus-client>=0.24.1", # メトリクス収集（パフォーマンス監視）
       "orjson>=3.11.5",            # 高速JSON処理（JSONB操作の高速化）
       "async-timeout>=4.0.0",      # Python 3.10以下対応のタイムアウト（⚠️ 重要）
   ]
   ```

   **注意: pgvector Pythonライブラリの導入**:
   - `pgvector` Pythonライブラリをインストールしておくと、asyncpg への型登録が楽になります
   - `import pgvector.asyncpg; await pgvector.asyncpg.register_vector(conn)`
     とするだけで、SQL内で手動キャストやエンコード/デコードが不要になります
   - 実装箇所: `PostgreSQLDatabase.initialize()` メソッド（Step 2）

   **各パッケージの導入意図と実装での利用効果**:

   - **`langchain-text-splitters`**:
     - **導入意図**: テキスト分割アルゴリズムの実装を簡素化し、検索精度を向上させる
     - **利用効果**:
       - `RecursiveCharacterTextSplitter` を使用して、句読点や改行を優先した意味を保持する分割が可能
       - 自前実装のメンテナンスコストを削減
       - チャンクサイズ、オーバーラップ、セパレータの優先順位などを柔軟に設定可能
       - 実装箇所: `SessionArchiver._split_content_by_tokens()` メソッド（Step 5.4）

   - **`pydantic-settings`**:
     - **導入意図**: 環境変数からの設定読み込みを型安全に行い、設定値の検証とデフォルト値管理を改善
     - **利用効果**:
       - 環境変数の型チェックとバリデーションが自動化される
       - IDEの型補完が効くため、設定値の誤りを早期発見
       - 設定クラスを定義することで、設定の一元管理が可能
       - 将来的な拡張: `.env.sample` から `Settings` クラスへの移行が容易
       - 実装箇所: 将来的に `PostgreSQLDatabase`、`EmbeddingProcessor`、
         `SessionArchiver` などの設定管理に適用可能

   - **`asyncpg-stubs`**:
     - **導入意図**: asyncpgの型情報を提供し、型チェックとIDE補完の精度を向上させる
     - **利用効果**:
       - `mypy` や `pyright` などの型チェッカーで asyncpg の使用箇所を正確に検証可能
       - IDE（VSCode、PyCharm等）での型補完とエラー検出が向上
       - `asyncpg.Connection`、`asyncpg.Pool` などの型情報が利用可能
       - 実装箇所: `PostgreSQLDatabase` クラス全体（Step 2）で型安全性が向上

   - **`structlog`**:
     - **導入意図**: 構造化ログによるデバッグ性と運用監視の向上、ログのパフォーマンス最適化
     - **利用効果**:
       - JSON形式の構造化ログにより、ログ解析ツール（ELK、Loki等）との連携が容易
       - コンテキスト情報（セッションID、ユーザーID、処理時間等）を自動的に付与可能
       - 標準の`logging`モジュールより高速（特に大量のログ出力時）
       - ログレベルの動的変更やフィルタリングが容易
       - 実装箇所: 全モジュールでログ出力を統一
         （`EmbeddingProcessor`、`SessionArchiver`、`PostgreSQLDatabase`等）
       - 実装時の便利な点:
         - `structlog.get_logger()`でロガーを取得し、
           `logger.info("message", key=value)`で構造化ログを出力
         - `structlog.configure()`で出力形式（JSON、コンソール等）を一元管理
         - バックグラウンドタスクの処理状況を構造化ログで追跡可能

   - **`prometheus-client`**:
     - **導入意図**: メトリクス収集によるパフォーマンス監視とリソース使用量の可視化
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

   - **`orjson`**:
     - **導入意図**: 高速なJSON処理により、JSONB操作のパフォーマンス向上と非同期処理の効率化
     - **利用効果**:
       - 標準の`json`モジュールより2-3倍高速（特に大量のJSON処理時）
       - `asyncpg`のJSONB型との連携が容易（`orjson.dumps()`でバイト列を生成し、`asyncpg`に渡す）
       - `sessions.messages`（JSONB）の読み書き処理が高速化
       - `knowledge_sources.metadata`、`knowledge_chunks.location`（JSONB）の処理が高速化
       - 実装箇所: `PostgreSQLDatabase.save_session()`、
         `PostgreSQLDatabase.save_knowledge_source()`等のJSONB操作
       - 実装時の便利な点:
         - `import orjson; orjson.dumps(obj)`でJSON文字列（バイト列）を生成
         - `orjson.loads(bytes)`でJSONをパース（標準の`json`と同様のAPI）
         - `asyncpg`の`JSONB`型に直接バイト列を渡せるため、エンコード/デコードのオーバーヘッドが削減
         - 非同期処理での大量のJSONB操作時にパフォーマンス向上が顕著

2. **設計レビュー**:
   - Source-Chunk構造の妥当性確認
   - 非同期処理パターンの確認
   - スキーマ設計の最終確認

**完了基準**:

- [ ] 依存関係が追加されている（`langchain-text-splitters`, `pydantic-settings`,
  `asyncpg-stubs`, `structlog`, `prometheus-client`, `orjson` を含む）
- [ ] 各パッケージの導入意図と利用効果を理解している
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
    """データベース操作のプロトコル（インターフェース）"""
    
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
    
    # 知識ベース関連メソッド（将来的な拡張性のため）
    @abstractmethod
    async def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[dict]:
        """類似度検索を実行"""
        pass
    
    @abstractmethod
    async def save_knowledge_source(
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
    async def save_knowledge_chunk(
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
import json
import logging
from typing import TYPE_CHECKING
from pathlib import Path

from .base import DatabaseProtocol

if TYPE_CHECKING:
    from ..session.models import ChatSession

logger = logging.getLogger(__name__)

# 注意: asyncpg-stubs がインストールされている場合、
# asyncpg.Connection, asyncpg.Pool などの型情報が利用可能になり、
# IDEの型補完と型チェッカー（mypy, pyright）の精度が向上します。

class PostgreSQLDatabase(DatabaseProtocol):
    """PostgreSQL データベース（非同期）"""
    
    # クラス定数としてデフォルト値を定義
    DEFAULT_POOL_MIN_SIZE = 5
    DEFAULT_POOL_MAX_SIZE = 20
    DEFAULT_COMMAND_TIMEOUT = 60
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.pool: asyncpg.Pool | None = None
    
    async def _init_connection(self, conn: asyncpg.Connection) -> None:
        """プールの各コネクション初期化時に呼ばれる（pgvector型登録用）
        
        ⚠️ 重要: コネクションプールを使用している場合、プールから取得される
        各コネクションに対して pgvector の型登録が必要です。
        このメソッドを init パラメータに渡すことで、プールから取得される
        すべてのコネクションに対して自動的に登録されます。
        """
        from pgvector.asyncpg import register_vector
        await register_vector(conn)
    
    async def initialize(self) -> None:
        """データベースの初期化"""
        # 環境変数から接続プール設定を読み込み（デフォルト値あり）
        min_size = int(os.getenv(
            "DB_POOL_MIN_SIZE", str(self.DEFAULT_POOL_MIN_SIZE)))
        max_size = int(os.getenv(
            "DB_POOL_MAX_SIZE", str(self.DEFAULT_POOL_MAX_SIZE)))
        command_timeout = int(os.getenv(
            "DB_COMMAND_TIMEOUT", str(self.DEFAULT_COMMAND_TIMEOUT)))
        
        # ⚠️ 重要: init パラメータを使用して、プールから取得される各コネクションに対して
        # pgvector の型登録を自動的に行います。
        # これにより、プールのすべてのコネクションで pgvector が使用可能になります。
        self.pool = await asyncpg.create_pool(
            self.connection_string,
            init=self._init_connection,  # ← これが重要！
            min_size=min_size,
            max_size=max_size,
            command_timeout=command_timeout,
        )
        
        # pgvector 拡張を有効化とバージョン確認（1つのコネクションで実行）
        async with self.pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            
            # ⚠️ 推奨: pg_trgm 拡張を有効化（ハイブリッド検索の準備）
            # Phase 8.5 でハイブリッド検索を実装する予定のため、ここで拡張を有効化します。
            # 固有名詞（エラーコード、変数名など）の検索精度向上に効果的です。
            try:
                await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
                logger.info("pg_trgm extension enabled for hybrid search")
            except Exception as e:
                # pg_trgm が利用できない環境でも動作するように
                logger.warning(f"pg_trgm extension could not be enabled: {e}. "
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
            
            await self._create_tables(conn)
    
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
                    'completed',    -- 検索可能
                    'failed'        -- エラー
                );
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """)
        
        # 短期記憶: sessions テーブル
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_key TEXT PRIMARY KEY,
                session_type TEXT NOT NULL,
                messages JSONB DEFAULT '[]'::jsonb NOT NULL,
                status session_status_enum DEFAULT 'active',  -- session_status_enumを使用
                guild_id BIGINT,        -- Discord Guild ID（Discord URL生成に必要）
                channel_id BIGINT,
                thread_id BIGINT,
                user_id BIGINT,
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
                error_message TEXT,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # 環境変数からhalfvecの使用を判定
        # ⚠️ 注意: pgvector 0.7.0以降で halfvec を使う場合は、
        # embedding halfvec(1536) と明示的に書く必要があります。
        # SQL文字列生成時にミスしやすいポイントのため、慎重に実装してください。
        use_halfvec = os.getenv("KB_USE_HALFVEC", "false").lower() == "true"
        vector_type = "halfvec(1536)" if use_halfvec else "vector(1536)"
        
        # 改善案: 環境変数を見て「使用するSQLファイル自体を切り替える」か、
        # pgvector-python の register_vector を使って型を抽象化することを推奨します。
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS knowledge_chunks (
                id BIGSERIAL PRIMARY KEY,
                source_id BIGINT REFERENCES knowledge_sources(id)
                    ON DELETE CASCADE,
                content TEXT NOT NULL,
                embedding {vector_type},
                location JSONB DEFAULT '{}'::jsonb,
                token_count INT,
                retry_count INT DEFAULT 0,  -- ⚠️ 追加: Dead Letter Queue対応
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # インデックスの作成
        await self._create_indexes(conn)
    
    async def _create_indexes(self, conn: asyncpg.Connection) -> None:
        """インデックスを作成"""
        # セッションテーブルのインデックス
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
        
        # 知識ベーステーブルのインデックス
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sources_metadata 
            ON knowledge_sources USING gin (metadata);
        """)
        
        # 環境変数からHNSWパラメータとhalfvecの使用を判定
        use_halfvec = os.getenv("KB_USE_HALFVEC", "false").lower() == "true"
        ops_type = "halfvec_cosine_ops" if use_halfvec else "vector_cosine_ops"
        
        # ⚠️ 重要: HNSWパラメータのバリデーション（SQLインジェクション対策）
        # pgvectorの推奨範囲内であることを確認
        VALID_HNSW_M_RANGE = range(4, 65)  # pgvectorの推奨範囲
        VALID_HNSW_EF_RANGE = range(16, 513)
        
        m = int(os.getenv("KB_HNSW_M", "16"))
        ef_construction = int(os.getenv("KB_HNSW_EF_CONSTRUCTION", "64"))
        
        if m not in VALID_HNSW_M_RANGE:
            raise ValueError(f"KB_HNSW_M must be between 4 and 64, got {m}")
        if ef_construction not in VALID_HNSW_EF_RANGE:
            raise ValueError(
                f"KB_HNSW_EF_CONSTRUCTION must be between 16 and 512, "
                f"got {ef_construction}")
        
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
        
        # ⚠️ 推奨: pg_trgm 拡張を有効化してハイブリッド検索の準備
        # ベクトル検索のみでは「固有名詞（エラーコード、変数名など）」の検索に弱いため、
        # 日本語の全文検索や部分一致において、ベクトル検索を補完する効果が絶大です。
        # Phase 8.5 でハイブリッド検索を実装する予定のため、ここでインデックスを準備します。
        try:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_chunks_content_trgm 
                ON knowledge_chunks USING gin (content gin_trgm_ops);
            """)
            logger.info(
                "pg_trgm extension enabled and index created for hybrid search")
        except Exception as e:
            # pg_trgm が利用できない環境（例: 古いPostgreSQL）でも動作するように
            logger.warning(f"pg_trgm extension could not be enabled: {e}. "
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
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_active_at: datetime = field(default_factory=datetime.utcnow)
```

**変更理由**:

- `status`: セッションの状態管理（'active', 'archived'など）に必要
- `guild_id`: Discord URL生成（`/channels/{guild_id}/{channel_id}`）に必要

#### 2.3 セッション管理メソッドの実装

```python
async def save_session(self, session: "ChatSession") -> None:
    """セッションを保存（トランザクション付き）
    
    ⚠️ 重要: guild_id は Discord URL生成に必要です。
    handlers.py で明示的に取得・保存されていることを確認してください。
    DMの場合、guild_id は None になります。
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
                    guild_id = COALESCE(EXCLUDED.guild_id, sessions.guild_id)
                    -- guild_idも更新
            """,
                session.session_key,
                session.session_type,
                json.dumps(
                    [msg.model_dump() for msg in session.messages],
                    ensure_ascii=False),
                getattr(session, 'status', 'active'),  # デフォルトは 'active'
                getattr(session, 'guild_id', None),  # guild_idを追加（DMの場合はNone）
                session.channel_id,
                getattr(session, 'thread_id', None),
                session.user_id,
                session.created_at,
                session.last_active_at,
            )

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
            for msg in json.loads(row["messages"])
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
        )
```

**完了基準**:

- [ ] `PostgreSQLDatabase` クラスが実装されている
- [ ] `PostgreSQLDatabase` が `DatabaseProtocol` に適合している
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
    'source_type',  # VALID_SOURCE_TYPES でバリデーション済み
    'channel_id',   # BIGINT型
    'user_id',      # BIGINT型
}

async def similarity_search(
    self,
    query_embedding: list[float],
    top_k: int = 10,
    filters: dict | None = None,
) -> list[dict]:
    """類似度検索を実行
    
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
    # 接続プール枯渇時のタイムアウト処理
    try:
        # ⚠️ 重要: Python 3.11+ では asyncio.timeout、それ以前では asyncio.wait_for を使用
        # Python 3.10以下対応のため、async-timeout ライブラリの使用を推奨
        import sys
        if sys.version_info >= (3, 11):
            from asyncio import timeout as asyncio_timeout
        else:
            # Python 3.10以下では async-timeout ライブラリを使用（推奨）
            try:
                from async_timeout import timeout as asyncio_timeout
            except ImportError:
                # フォールバック: asyncio.wait_for を正しく使用
                async def _timeout_wrapper(seconds: float):
                    """Python 3.10以下用のタイムアウトコンテキストマネージャー"""
                    class TimeoutContext:
                        def __init__(self, seconds: float):
                            self.seconds = seconds
                        async def __aenter__(self):
                            return self
                        async def __aexit__(self, exc_type, exc_val, exc_tb):
                            pass
                    return TimeoutContext(seconds)
                asyncio_timeout = _timeout_wrapper
        
        # 接続取得にタイムアウトを設定
        conn = await asyncio.wait_for(
            self.pool.acquire(),
            timeout=30.0
        )
        try:
            async with conn:
                # ベースクエリ
                query = """
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
                        1 - (c.embedding <=> $1::vector) as similarity
                    FROM knowledge_chunks c
                    JOIN knowledge_sources s ON c.source_id = s.id
                    WHERE c.embedding IS NOT NULL
                """
                
                # 環境変数から類似度閾値とtop_kを読み込み
                similarity_threshold = float(
                    os.getenv("KB_SIMILARITY_THRESHOLD", "0.7"))
                top_k_limit = int(os.getenv("KB_DEFAULT_TOP_K", str(top_k)))
                
                params = [query_embedding, similarity_threshold]
                param_index = 3
                
                # フィルタの適用（Allow-list チェック + ENUMバリデーション）
                # セキュリティ: 許可されたキーのみを処理（SQLインジェクション対策）
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
                                f"Invalid source_type: {source_type}. "
                                f"Must be one of {VALID_SOURCE_TYPES}")
                        query += f" AND s.type = ${param_index}"
                        params.append(source_type)
                        param_index += 1
                    
                    if "channel_id" in filters:
                        # 型チェック: BIGINT型であることを確認
                        try:
                            channel_id = int(filters["channel_id"])
                        except (ValueError, TypeError):
                            raise ValueError(
                                f"Invalid channel_id: {filters['channel_id']}. "
                                f"Must be an integer.")
                        query += (
                            f" AND (s.metadata->>'channel_id')::bigint = "
                            f"${param_index}")
                        params.append(channel_id)
                        param_index += 1
                    
                    if "user_id" in filters:
                        # 型チェック: BIGINT型であることを確認
                        try:
                            user_id = int(filters["user_id"])
                        except (ValueError, TypeError):
                            raise ValueError(
                                f"Invalid user_id: {filters['user_id']}. "
                                f"Must be an integer.")
                        query += (
                            f" AND (s.metadata->>'author_id')::bigint = "
                            f"${param_index}")
                        params.append(user_id)
                        param_index += 1
                
                # 類似度でソート（環境変数から取得した閾値とtop_kを使用）
                query += f"""
                    AND 1 - (c.embedding <=> $1) > $2
                    ORDER BY similarity DESC
                    LIMIT ${param_index}
                """
                params.append(min(top_k, top_k_limit))
                
                rows = await conn.fetch(query, *params)
            finally:
                self.pool.release(conn)
    except asyncio.TimeoutError:
        logger.error("Failed to acquire database connection: pool exhausted")
        raise ConnectionError("Database connection pool exhausted")
    except asyncpg.exceptions.TooManyConnectionsError:
        logger.error("Connection pool exhausted")
        raise ConnectionError("Database is temporarily unavailable")
    except asyncpg.PostgresConnectionError as e:
        logger.error(f"Database connection failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Error during similarity search: {e}", exc_info=True)
        raise
    
    return [
            {
                "source_id": row["source_id"],
                "source_type": row["type"],
                "title": row["title"],
                "uri": row["uri"],
                # 注意: asyncpgはJSONBを自動的にPython dictにデコードするため、json.loadsは不要
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

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...db.postgres import PostgreSQLDatabase
    from ...external.embedding import EmbeddingProvider

logger = logging.getLogger(__name__)


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
    ) -> list[dict]:
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
            # source_types は複数指定可能だが、現状は1つずつ検索
            # 将来的には ANY 句で対応可能
            if len(source_types) == 1:
                search_filters["source_type"] = source_types[0]
        
        # 3. ベクトル検索
        results = await self.db.similarity_search(
            query_embedding=query_embedding,
            top_k=top_k,
            filters=search_filters,
        )
        
        logger.info(f"Search completed: {len(results)} results found")
        return results
    
    async def search_by_source_type(
        self,
        query: str,
        source_type: str,
        top_k: int = 5,
    ) -> list[dict]:
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

import json
import logging
from typing import TYPE_CHECKING
import tiktoken

if TYPE_CHECKING:
    from ...db.postgres import PostgreSQLDatabase

logger = logging.getLogger(__name__)

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
        
        Returns:
            (source_id, chunk_id) のタプル
        """
        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                # 1. Source登録（status='pending'）
                source_id = await conn.fetchval("""
                    INSERT INTO knowledge_sources (type, title, uri, metadata, status)
                    VALUES ($1, $2, $3, $4, 'pending')
                    RETURNING id
                """, source_type, title, uri, json.dumps(metadata))
                
                # 2. チャンク登録（embedding=NULL、token_countを計算）
                encoding = _get_encoding()
                token_count = len(encoding.encode(content))
                
                chunk_id = await conn.fetchval("""
                    INSERT INTO knowledge_chunks 
                    (source_id, content, embedding, location, token_count)
                    VALUES ($1, $2, NULL, $3, $4)
                    RETURNING id
                """,
                source_id, content,
                json.dumps(location or {}, ensure_ascii=False), token_count)
                
                return source_id, chunk_id
    
    async def save_document_fast(
        self,
        source_type: str,
        title: str,
        uri: str,
        chunks: list[dict[str, str]],
        metadata: dict,
    ) -> int:
        """ドキュメントを高速に保存（ベクトル化は後で）"""
        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                # 1. Source登録
                source_id = await conn.fetchval("""
                    INSERT INTO knowledge_sources (type, title, uri, metadata, status)
                    VALUES ($1, $2, $3, $4, 'pending')
                    RETURNING id
                """, source_type, title, uri, json.dumps(metadata))
                
                # 2. チャンク一括登録（embedding=NULL、token_countを計算）
                encoding = _get_encoding()
                chunk_data = [
                    (
                        source_id,
                        chunk["content"],
                        None,  # embeddingはNULL
                        json.dumps(
                            chunk.get("location", {}), ensure_ascii=False),
                        len(encoding.encode(chunk["content"])),  # token_count
                    )
                    for chunk in chunks
                ]
                
                await conn.executemany("""
                    INSERT INTO knowledge_chunks 
                    (source_id, content, embedding, location, token_count)
                    VALUES ($1, $2, $3, $4, $5)
                """, chunk_data)
                
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
import logging
import openai
from typing import TYPE_CHECKING
from tenacity import (
    retry, stop_after_attempt, wait_exponential, retry_if_exception_type)

if TYPE_CHECKING:
    from . import EmbeddingProvider

logger = logging.getLogger(__name__)

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
            logger.error(
                f"Unexpected error in generate_embedding: {e}", exc_info=True)
            raise
    
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
import logging
from discord.ext import tasks
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...db.postgres import PostgreSQLDatabase
    from ...external.embedding import EmbeddingProvider

logger = logging.getLogger(__name__)


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
        self.batch_size = batch_size or int(
            os.getenv("KB_EMBEDDING_BATCH_SIZE", "100"))
        max_concurrent = max_concurrent or int(
            os.getenv("KB_EMBEDDING_MAX_CONCURRENT", "10"))
        self._semaphore = asyncio.Semaphore(max_concurrent)  # レート制限用セマフォ
        self._lock = asyncio.Lock()  # 競合状態対策
        
        # ⚠️ 重要: @tasks.loop デコレータのパラメータはクラス定義時に評価されるため、
        # 環境変数の遅延読み込みが必要な場合は、__init__で間隔を保存し、
        # start()メソッドでchange_interval()を呼び出します。
        import os
        self._interval = int(os.getenv("KB_EMBEDDING_INTERVAL_MINUTES", "1"))
    
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
            MAX_RETRY_COUNT = int(os.getenv("KB_EMBEDDING_MAX_RETRY", "3"))
            
            # pending状態のチャンクを取得（embedding IS NULL、retry_count未満のもの）
            async with self.db.pool.acquire() as conn:
                pending_chunks = await conn.fetch("""
                    SELECT id, content, source_id
                    FROM knowledge_chunks
                    WHERE embedding IS NULL
                    AND retry_count < $1
                    ORDER BY id ASC
                    LIMIT $2
                """, MAX_RETRY_COUNT, self.batch_size)
            
            if not pending_chunks:
                logger.debug("No pending chunks to process")
                return
            
            logger.info(f"Processing {len(pending_chunks)} pending chunks...")
            
            # ⚠️ 改善: OpenAI Embedding APIのバッチリクエストを使用（効率化）
            texts = [chunk["content"] for chunk in pending_chunks]
            try:
                embeddings = await self._generate_embeddings_batch(texts)
            except Exception as e:
                # Embedding API全体障害時の処理: 失敗したチャンクのretry_countをインクリメント
                logger.error(
                    f"Embedding API failed for batch: {e}", exc_info=True)
                async with self.db.pool.acquire() as conn:
                    async with conn.transaction():
                        for chunk in pending_chunks:
                            await conn.execute("""
                                UPDATE knowledge_chunks
                                SET retry_count = COALESCE(retry_count, 0) + 1
                                WHERE id = $1
                            """, chunk["id"])
                        
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
                                await conn.execute("""
                                    UPDATE knowledge_sources
                                    SET status = 'failed',
                                        error_message = $1,
                                        updated_at = CURRENT_TIMESTAMP
                                    WHERE id = $2
                                """,
                                (
                                    f"Embedding failed after "
                                    f"{MAX_RETRY_COUNT} retries"),
                                source_id)
                return  # 処理を中断
            
            # DB更新（バッチ処理 - executemanyを使用して効率化）
            async with self.db.pool.acquire() as conn:
                async with conn.transaction():
                    await conn.executemany("""
                        UPDATE knowledge_chunks
                        SET embedding = $1::vector,
                            retry_count = 0
                        WHERE id = $2
                    """, [
                        (emb, chunk["id"])
                        for emb, chunk in zip(embeddings, pending_chunks)])
            
            # Sourceのステータスも更新
            await self._update_source_status(pending_chunks)
            
            logger.info(f"Successfully processed {len(pending_chunks)} chunks")
    
    async def _generate_embedding_with_limit(self, text: str) -> list[float]:
        """セマフォで制限されたEmbedding生成（レート制限対策）"""
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
    
    async def _update_source_status(self, processed_chunks: list[dict]):
        """Sourceのステータスを更新"""
        source_ids = {chunk["source_id"] for chunk in processed_chunks}
        
        async with self.db.pool.acquire() as conn:
            for source_id in source_ids:
                # このSourceにpendingチャンクが残っているか確認（embedding IS NULLのもの）
                pending_count = await conn.fetchval("""
                    SELECT COUNT(*)
                    FROM knowledge_chunks
                    WHERE source_id = $1
                    AND embedding IS NULL
                """, source_id)
                
                if pending_count == 0:
                    # 全チャンクが完了したのでSourceも完了に
                    await conn.execute("""
                        UPDATE knowledge_sources
                        SET status = 'completed',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = $1
                    """, source_id)
                    logger.debug(f"Source {source_id} marked as completed")
    
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
                    await asyncio.wait_for(task, timeout=30.0)  # 最大30秒待機
                except asyncio.TimeoutError:
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
    db = PostgreSQLDatabase(os.getenv("DATABASE_URL"))
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

```python
# src/kotonoha_bot/features/knowledge_base/session_archiver.py
"""セッションの知識化処理"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from discord.ext import tasks
from typing import TYPE_CHECKING
import tiktoken

if TYPE_CHECKING:
    from ...db.postgres import PostgreSQLDatabase
    from ...external.embedding import EmbeddingProvider

logger = logging.getLogger(__name__)

# OpenAI text-embedding-3-small のトークン上限（環境変数から読み込み可能）
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
    
    @tasks.loop(hours=int(os.getenv("KB_ARCHIVE_INTERVAL_HOURS", "1")))  # 環境変数から読み込み
    async def archive_inactive_sessions(self):
        """非アクティブなセッションを知識ベースに変換"""
        if self._processing:
            logger.debug("Session archiving already in progress, skipping...")
            return
        
        try:
            self._processing = True
            logger.debug("Starting session archiving...")
            
            # 環境変数から閾値とバッチサイズを読み込み
            archive_threshold_hours = int(
                os.getenv("KB_ARCHIVE_THRESHOLD_HOURS",
                          str(self.archive_threshold_hours)))
            batch_size = int(os.getenv("KB_ARCHIVE_BATCH_SIZE", "10"))
            
            # 閾値時間以上非アクティブなセッションを取得
            threshold_time = datetime.now() - timedelta(
                hours=archive_threshold_hours)
            
            # 接続プール枯渇時のタイムアウト処理を追加
            try:
                # ⚠️ 重要: Python 3.11+ では asyncio.timeout、
                # それ以前では asyncio.wait_for を使用
                import sys
                if sys.version_info >= (3, 11):
                    from asyncio import timeout as asyncio_timeout
                else:
                    try:
                        from async_timeout import timeout as asyncio_timeout
                    except ImportError:
                        # フォールバック: asyncio.wait_for を正しく使用
                        async def _wait_with_timeout(coro, timeout):
                            return await asyncio.wait_for(coro, timeout=timeout)
                        asyncio_timeout = lambda t: _wait_with_timeout
                
                # 接続取得にタイムアウトを設定
                conn = await asyncio.wait_for(
                    self.db.pool.acquire(),
                    timeout=30.0
                )
                try:
                    async with conn:
                        inactive_sessions = await conn.fetch("""
                            SELECT session_key, session_type, messages,
                                   guild_id, channel_id, thread_id,
                                   user_id, last_active_at
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
            
            # ⚠️ 改善: セッションアーカイブの並列処理（高速化）
            # セマフォで同時実行数を制限しつつ並列処理（DBへの負荷に注意）
            archive_semaphore = asyncio.Semaphore(3)  # 同時実行数を3に制限
            
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
        """タスク開始前の待機"""
        pass
    
    async def _archive_session(self, session_row: dict):
        """セッションを知識ベースに変換"""
        session_key = session_row['session_key']
        messages = json.loads(session_row['messages'])
        original_last_active_at = session_row['last_active_at']
        
        if not messages:
            logger.debug(f"Skipping empty session: {session_key}")
            return
        
        # フィルタリング: 短すぎるセッションやBotのみのセッションを除外
        if not self._should_archive_session(messages):
            logger.debug(f"Skipping low-value session: {session_key}")
            # アーカイブしないが、statusは'archived'に更新（再処理を避ける）
            # 注意: この場合は知識ベースへの登録を行わないため、単純なUPDATEのみで問題ありません
            async with self.db.pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute("""
                        UPDATE sessions
                        SET status = 'archived'
                        WHERE session_key = $1
                    """, session_key)
            return
        
        # セッションの要約テキストを生成
        # 現状: メッセージを結合（将来的にはLLMで要約APIを使用して精度向上）
        # 注意: 生の会話ログ（「こんにちは」「了解です」など）はノイズが多く、
        #       ベクトル検索の精度（Semantic Search）が下がる可能性があります。
        #       将来的な改善案:
        #       1. LLMで「この会話のトピックと結論」を要約したテキストをcontentに入れる
        #       2. Hybrid Search: 生ログはそのまま保存しつつ、検索用の「キーワード」や
        #          「要約」を別カラム（またはMetadata）に持たせ、検索対象を工夫する
        #       今回は工数的に「まずは単純結合」で進め、将来的にLLM要約タスクを追加するのが現実的です。
        content = self._format_messages_for_knowledge(messages)
        
        # トークン数チェックと分割処理
        encoding = tiktoken.encoding_for_model("text-embedding-3-small")
        token_count = len(
            encoding.encode(content))
        
        if token_count > MAX_EMBEDDING_TOKENS:
            logger.warning(
                f"Session {session_key} exceeds token limit "
                f"({token_count} > {MAX_EMBEDDING_TOKENS}), splitting...")
            chunks = self._split_content_by_tokens(
                content, encoding, MAX_EMBEDDING_TOKENS)
        else:
            chunks = [content]
        
        # タイトルを生成（最初のユーザーメッセージから）
        title = self._generate_title(messages)
        
        # URIを生成（Discord URL）
        uri = self._generate_discord_uri(session_row)
        
        # メタデータを構築
        metadata = {
            "channel_id": session_row.get('channel_id'),
            "thread_id": session_row.get('thread_id'),
            "user_id": session_row.get('user_id'),
            "session_type": session_row['session_type'],
            "archived_at": datetime.now().isoformat(),
        }
        
        # ⚠️ 重要: すべての操作を1つのアトミックなトランザクション内で実行
        # これにより、「知識化はされたがセッションはactiveのまま」という不整合を防ぎます
        async with self.db.pool.acquire() as conn:
            # トランザクション分離レベルを REPEATABLE READ に設定（楽観的ロックのため）
            async with conn.transaction(isolation='repeatable_read'):
                # 1. knowledge_sources に登録（status='pending'）
                source_id = await conn.fetchval("""
                    INSERT INTO knowledge_sources (type, title, uri, metadata, status)
                    VALUES ($1, $2, $3, $4, 'pending')
                    RETURNING id
                """,
                'discord_session', title, uri,
                json.dumps(metadata, ensure_ascii=False))
                
                # 2. knowledge_chunks に登録（複数チャンクに対応）
                for i, chunk_content in enumerate(chunks):
                    chunk_token_count = len(encoding.encode(chunk_content))
                    await conn.execute("""
                        INSERT INTO knowledge_chunks
                        (source_id, content, embedding, location, token_count)
                        VALUES ($1, $2, NULL, $3, $4)
                    """, source_id, chunk_content, json.dumps({
                        "session_key": session_key,
                        "chunk_index": i,
                        "total_chunks": len(chunks)
                    }, ensure_ascii=False), chunk_token_count)
                
                # 3. sessions の status を 'archived' に更新（楽観的ロック）
                # ⚠️ 重要: last_active_at が変更されていない場合のみ更新（競合状態対策）
                # UPDATE が 0 件の場合は、トランザクション全体がロールバックされる
                result = await conn.execute("""
                    UPDATE sessions
                    SET status = 'archived'
                    WHERE session_key = $1
                    AND status = 'active'
                    AND last_active_at = $2
                """, session_key, original_last_active_at)
                
                # asyncpgのexecuteは "UPDATE N" 形式の文字列を返す
                if result == "UPDATE 0":
                    # セッションが他のプロセスによって更新された場合、トランザクション全体をロールバック
                    # ⚠️ 重要: 例外を発生させることで、asyncpgのトランザクションコンテキストマネージャーが
                    # 自動的にロールバックを実行します。これにより、
                    # knowledge_sources と knowledge_chunks への INSERT も
                    # 取り消され、データの不整合を防ぎます。
                    logger.warning(
                        f"Session {session_key} was updated during archiving, "
                        f"rolling back transaction to prevent duplicate "
                        f"archive")
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
        """Graceful Shutdown: 処理中のタスクが完了するまで待機"""
        logger.info("Stopping session archiver gracefully...")
        
        # タスクをキャンセル
        self.archive_inactive_sessions.cancel()
        
        # 処理中のタスクが完了するまで待機
        try:
            # タスクが存在する場合、完了を待つ
            task = getattr(self.archive_inactive_sessions, '_task', None)
            if task and not task.done():
                try:
                    # 最大60秒待機
                    # （アーカイブ処理は時間がかかる可能性があるため）
                    await asyncio.wait_for(task, timeout=60.0)
                except asyncio.TimeoutError:
                    logger.warning(
                        "Session archiving task did not complete "
                        "within timeout")
                except asyncio.CancelledError:
                    logger.debug("Session archiving task was cancelled")
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
- [ ] `langchain-text-splitters` の導入意図を理解し、将来的な移行計画がある（または既に使用している）
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
    image: pgvector/pgvector:0.8.1-pg18
    container_name: kotonoha-postgres
    restart: unless-stopped
    env_file:
      - .env
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-kotonoha}
      POSTGRES_USER: ${POSTGRES_USER:-kotonoha}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
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
      PGADMIN_CONFIG_SERVER_MODE: 'False'
      # セキュリティ: 本番環境では必ずマスターパスワードを要求する
      PGADMIN_CONFIG_MASTER_PASSWORD_REQUIRED: 'True'
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

**単一コンテナ構成の例**（非推奨）:

```yaml
services:
  kotonoha-bot:
    build: .
    # PostgreSQLをコンテナ内で起動（init systemが必要）
    # または、SQLiteに戻す
    # 注意: この構成は本番環境では推奨されません
```

**推奨構成**: 上記の複数コンテナ構成を維持し、必要に応じてpgAdminを削除する。

#### 6.2 データの永続化とバックアップ戦略

> **参照**: 詳細なバックアップ戦略については、
> [PostgreSQL スキーマ設計書 - 14. バックアップ戦略](../architecture/postgresql-schema-design.md#14-バックアップ戦略)
> を参照してください。

**重要**: SQLiteのように「ファイルをコピーすれば終わり」ではありません。PostgreSQLは適切なバックアップ戦略が必要です。

**推奨バックアップ方法の概要**:

1. **pg_dump による定期バックアップ**: カスタムフォーマット（圧縮済み）を使用
2. **自動バックアップスクリプト**: cron等で定期実行
3. **Synology Hyper Backup との連携**: `pg_dump`の結果をNASの別フォルダに出力

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

###### 方法 3: docker-compose.yml での初期化スクリプト

`docker-compose.yml` の `postgres` サービスに `entrypoint` を追加して、
起動時にバックアップディレクトリの権限を設定する方法もあります。

```yaml
postgres:
  image: pgvector/pgvector:0.8.1-pg18
  # ... 既存の設定 ...
  volumes:
    - postgres_data:/var/lib/postgresql/data
    - ./backups:/backups  # マウント先を /backups に変更
  entrypoint: |
    sh -c "
      # バックアップディレクトリの権限を設定
      mkdir -p /backups
      chmod 777 /backups
      # 通常の PostgreSQL エントリーポイントを実行
      docker-entrypoint.sh postgres
    "
```

**注意**: この方法は `docker-entrypoint.sh` の動作に依存するため、イメージによっては動作しない可能性があります。

**推奨**: 方法 2（docker exec + docker cp）を推奨します。最も確実で、権限問題を完全に回避できます。

詳細なバックアップスクリプトの実装例については、上記の設計書を参照してください。

#### 6.3 データベース・パフォーマンス設計（Synology NASへの最適化）

> **参照**: 詳細なパフォーマンス設計については、
> [PostgreSQL スキーマ設計書 - 17.3 データベース・パフォーマンス設計（Synology NASへの最適化）](../architecture/postgresql-schema-design.md#173-データベースパフォーマンス設計synology-nasへの最適化)
> を参照してください。

**halfvecの採用検討**:

pgvector 0.7.0以降では、`halfvec` (float16) 型がサポートされています。
これを使用するとストレージとメモリ使用量が半分になります。

**メリット**:

- **メモリ使用量の削減**: `vector(1536)`はfloat32を使用するため、
  1ベクトルあたり約6KB消費します。10万件で約600MBのインデックスサイズに
  なります。`halfvec(1536)`を使用すると約300MBに削減されます。
- **精度への影響**: OpenAIのEmbedding精度への影響は軽微です。

**使用方法**:

- 環境変数 `KB_USE_HALFVEC=true` を設定すると、`halfvec(1536)`が使用されます
- `pgvector/pgvector:0.8.1-pg18` イメージを使用します（PostgreSQL 18 + pgvector 0.8.1）
- NASのリソース節約のため強く推奨します

詳細な注意事項については、上記の設計書を参照してください。

#### 6.4 環境変数とシークレット管理

**重要**: 機密情報は環境変数経由で渡されますが、適切なシークレット管理が必要です。

> **参照**: 詳細な環境変数一覧については、
> [PostgreSQL スキーマ設計書 - 付録 B. 環境変数一覧](../architecture/postgresql-schema-design.md#b-環境変数一覧)
> を参照してください。

**推奨方法**:

1. **`.env.sample` ファイルの作成**: すべての環境変数のサンプルを提供（詳細は上記の設計書を参照）
2. **本番環境でのシークレット管理**: Docker Secrets または外部シークレットマネージャーの使用を検討
3. **将来的な改善**: `pydantic-settings` を使用した型安全な設定管理への移行を推奨

詳細な環境変数の説明と設定例については、上記の設計書を参照してください。

##### ⚠️ 重要: 設定クラスの即時導入推奨

`os.getenv()` がコード全体に散在しており、デフォルト値の重複や型変換のミスが発生しやすいため、
Phase 8の開始時点で `pydantic-settings` を導入することを強く推奨します。

   **`pydantic-settings` を使用した設定管理の例**:

   ```python
   # src/kotonoha_bot/config/settings.py
   from pydantic_settings import BaseSettings, SettingsConfigDict
   from typing import Optional
   
   class DatabaseSettings(BaseSettings):
       model_config = SettingsConfigDict(env_prefix="DB_")
       
       pool_min_size: int = 2
       pool_max_size: int = 10
       command_timeout: int = 60
   
   class KnowledgeBaseSettings(BaseSettings):
       model_config = SettingsConfigDict(env_prefix="KB_")
       
       use_halfvec: bool = False
       similarity_threshold: float = 0.7
       embedding_batch_size: int = 50
       embedding_max_concurrent: int = 5
       embedding_interval_minutes: int = 1
       archive_threshold_hours: int = 1
       archive_batch_size: int = 10
       min_session_length: int = 30
       chunk_overlap_ratio: float = 0.2
       default_top_k: int = 5
       max_embedding_tokens: int = 8191
       hnsw_m: int = 16
       hnsw_ef_construction: int = 64
   
   class Settings(BaseSettings):
       database: DatabaseSettings = DatabaseSettings()
       knowledge_base: KnowledgeBaseSettings = KnowledgeBaseSettings()
       
       postgres_user: str = "kotonoha"
       postgres_password: str
       postgres_db: str = "kotonoha"
       postgres_host: str = "postgres"
       postgres_port: int = 5432
       
       discord_token: str
       openai_api_key: str
   
   # 使用例
   settings = Settings()
   db = PostgreSQLDatabase(
       connection_string=(
           f"postgresql://{settings.postgres_user}:"
           f"{settings.postgres_password}@{settings.postgres_host}:"
           f"{settings.postgres_port}/{settings.postgres_db}")
   )
   ```

   **移行のメリット**:

- 型安全性: 設定値の型が保証される
- バリデーション: 不正な値の検出が自動化される
- IDE補完: 設定値へのアクセス時に補完が効く
- ドキュメント化: 設定クラスが自動的にドキュメントになる

1. **本番環境でのシークレット管理**:
   - Docker Secrets の使用を検討
   - 外部シークレットマネージャー（AWS Secrets Manager、HashiCorp Vault等）との連携
   - シークレットローテーション方針の策定

2. **`.env` ファイルの扱い**:
   - `.env` ファイルは `.gitignore` に追加（既に追加済みを想定）
   - 本番環境では環境変数を直接設定するか、シークレットマネージャーを使用

3. **pgAdminのセキュリティ**:
   - `PGADMIN_CONFIG_MASTER_PASSWORD_REQUIRED=True` は必須です
   - **推奨**: `profiles: ["admin"]` を使用して、必要な時だけ起動するように設定
     - 通常起動: `docker-compose up -d`（pgAdminは起動しない）
     - 管理ツール起動: `docker-compose --profile admin up -d`（pgAdminも起動）
     - これにより、メモリ節約（約200-500MB）とセキュリティ向上が実現できます
   - インターネット公開しないとしても、認証周りは厳格にしておくべきです
   - 本番環境では、pgAdminへのアクセスをVPN経由に制限することを推奨します
   - 強力なパスワードを設定し、定期的にローテーションしてください

4. **移行スクリプトについて**:
   - **重要**: このフェーズは**新規設計**のため、SQLiteからの移行ツールは作成しません
   - 既存のデータは破棄します
   - 将来的に移行が必要になった場合は、別途移行スクリプトを作成することを検討してください

**完了基準**:

- [ ] `docker-compose.yml` が更新されている（環境変数対応版）
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

```python
async def _init_connection(self, conn: asyncpg.Connection):
    """プールの各コネクション初期化時に呼ばれる"""
    from pgvector.asyncpg import register_vector
    await register_vector(conn)

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

これはクリティカルな修正であり、設計書の2.1項に反映する必要があります。

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

```python
# tests/conftest.py
import pytest
import asyncpg
from kotonoha_bot.db.postgres import PostgreSQLDatabase

async def _cleanup_test_data(db: PostgreSQLDatabase):
    """テストデータのクリーンアップ"""
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            # 外部キー制約があるため、順序に注意
            await conn.execute("TRUNCATE knowledge_chunks CASCADE")
            await conn.execute("TRUNCATE knowledge_sources CASCADE")
            await conn.execute("TRUNCATE sessions CASCADE")

@pytest.fixture
async def postgres_db():
    """PostgreSQL データベースのフィクスチャ"""
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
```

#### 7.2 モックの実装

```python
# tests/conftest.py（追加）

from unittest.mock import AsyncMock
from kotonoha_bot.external.embedding import EmbeddingProvider

@pytest.fixture
def mock_embedding_provider():
    """OpenAI API のモック（CI/CDでテストが失敗しないように）"""
    provider = AsyncMock(spec=EmbeddingProvider)
    provider.generate_embedding = AsyncMock(return_value=[0.1] * 1536)
    provider.get_dimension = lambda: 1536
    return provider
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

3. **実装例（最低限のログベースメトリクス）**:

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

4. **将来的な拡張（Prometheusメトリクス）**:

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

#### データベース抽象化レイヤー

- [ ] データベース抽象化レイヤーが実装されている
- [ ] `DatabaseProtocol` インターフェースが定義されている
- [ ] `DatabaseProtocol` に知識ベース関連メソッドが含まれている
  （similarity_search, save_knowledge_source, save_knowledge_chunk）
- [ ] 依存性注入パターンが採用されている（循環インポート対策）
- [ ] `main.py` で一括初期化が実装されている

#### PostgreSQL実装

- [ ] `PostgreSQLDatabase` クラスが実装されている
- [ ] `PostgreSQLDatabase` が `DatabaseProtocol` に適合している
- [ ] pgvector 拡張が有効化されている
- [ ] pgvector のバージョン確認が実装されている（HNSW対応の確認）
- [ ] ⚠️ **推奨**: pg_trgm 拡張が有効化されている（ハイブリッド検索の準備、Phase 8.5 で実装予定）
- [ ] ⚠️ **重要**: `pgvector.asyncpg.register_vector()` が `init` パラメータ
  経由で正しく実装されている（プールの各コネクションに対して登録される）
- [ ] テーブルとインデックスが作成される
- [ ] ⚠️ **推奨**: pg_trgm 拡張が有効化されている（ハイブリッド検索の準備）
- [ ] ⚠️ **推奨**: `idx_chunks_content_trgm` インデックスが作成されている（Phase 8.5 で使用予定）
- [ ] セッション管理が動作する
- [ ] 接続プールの設定が環境変数から読み込まれる（`DB_POOL_MIN_SIZE`, `DB_POOL_MAX_SIZE`）

#### ベクトル検索機能

- [ ] `similarity_search` メソッドが実装されている
- [ ] pgvector の `<=>` 演算子を使用したベクトル検索が動作する
- [ ] ベクトルインデックスの最適化が完了している（HNSW、パラメータ指定済み）
- [ ] メタデータフィルタリング機能が動作する（チャンネルID、ユーザーIDなど）
- [ ] ENUMバリデーションによるSQLインジェクション対策が実装されている
- [ ] フィルタキーのAllow-list チェックが実装されている（`ALLOWED_FILTER_KEYS`）
- [ ] 入力値の型チェックが実装されている（BIGINT型の検証）

#### 知識ベース機能

- [ ] `knowledge_sources` テーブルが作成される
- [ ] `knowledge_chunks` テーブルが作成される（`created_at` カラム含む）
- [ ] 高速保存機能が動作する
- [ ] Embedding処理が動作する
- [ ] セッション知識化処理が動作する
  （非アクティブなセッションが自動的に知識ベースに変換される）
- [ ] Embedding APIのリトライロジックが実装されている（tenacity使用）
- [ ] セマフォによる同時実行数制限が実装されている
- [ ] asyncio.Lockによる競合状態対策が実装されている
- [ ] トランザクションが適切に使用されている（save_session等）
- [ ] ⚠️ **重要**: `SessionArchiver._archive_session` で、知識ベースへの登録と
  セッションステータス更新が同一トランザクション内で実行されている
  （アトミック性の保証）
- [ ] トークン数チェックと分割処理が実装されている
- [ ] Recursive Character Splitter方式によるテキスト分割が実装されている（句読点・改行を優先）
- [ ] `langchain-text-splitters` の導入意図を理解し、将来的な移行計画がある（または既に使用している）

#### 依存関係とパッケージ管理

- [ ] `langchain-text-splitters>=1.1.0` がインストールされている
- [ ] `pydantic-settings>=2.12.0` がインストールされている
- [ ] `pgvector>=0.3.0` がインストールされている（asyncpgへの型登録用）
- [ ] `asyncpg>=0.31.0` がインストールされている（必須: 0.29.0未満だと問題が発生する可能性あり）
- [ ] `asyncpg-stubs>=0.31.1` がdev依存関係としてインストールされている
- [ ] `structlog>=25.5.0` がインストールされている（構造化ログ用）
- [ ] `prometheus-client>=0.24.1` がインストールされている（メトリクス収集用）
- [ ] `orjson>=3.11.5` がインストールされている（高速JSON処理用）
- [ ] 各パッケージの導入意図と利用効果を理解している
- [ ] 型チェック（`ty` または `mypy`）で `asyncpg-stubs` の効果が確認できる
- [ ] `pgvector.asyncpg.register_vector()` による型登録が実装されている

#### Docker Compose

- [ ] `docker-compose.yml` に PostgreSQL サービスが追加されている
- [ ] `pgvector/pgvector:0.8.1-pg18` イメージが使用されている
- [ ] 環境変数が正しく設定されている（`DATABASE_URL`）
- [ ] ボリュームマウントとネットワーク設定が正しく設定されている
- [ ] 名前付きボリューム（`postgres_data`）を使用しており、バインドマウントによる権限問題を回避している
- [ ] メモリ設定が適切（HNSWインデックスとpg_dump実行時のメモリ使用量を考慮）
- [ ] PostgreSQL コンテナが起動する
- [ ] PostgreSQL のヘルスチェックが設定されている
- [ ] pgAdmin が追加されている（`dpage/pgadmin4` イメージ）
- [ ] pgAdmin が `profiles: ["admin"]` で設定されている（セキュリティ向上・メモリ節約）
- [ ] pgAdmin の環境変数が設定されている（`PGADMIN_DEFAULT_EMAIL`, `PGADMIN_DEFAULT_PASSWORD`）
- [ ] pgAdmin のセキュリティ設定が適切（`PGADMIN_CONFIG_MASTER_PASSWORD_REQUIRED=True`）
- [ ] pgAdmin のポートマッピングが設定されている（例: `5050:80`）
- [ ] pgAdmin が起動し、PostgreSQL に接続できる（`docker-compose --profile admin up -d` で起動）
- [ ] pgAdmin で PostgreSQL サーバーが登録されている
- [ ] バックアップ戦略が実装されている（pg_dump等）
- [ ] ⚠️ **重要**: バックアップスクリプトで権限問題への対策が実装されている
  - 推奨: `docker exec` + `docker cp` を使用した方法（権限問題を完全に回避）
  - 代替: ホスト側で `chmod 777 ./backups` または適切なオーナー設定（`chown 999:999 ./backups`）
- [ ] バックアップスクリプトが正常に動作する（手動実行で確認）
- [ ] 古いバックアップの自動削除機能が実装されている（保持日数の設定）
- [ ] `.env.example` ファイルが作成されている

#### テスト

- [ ] すべてのテストが通過する（既存の 137 テストケース + 新規テスト）
- [ ] 既存の機能が正常に動作する（回帰テスト）
- [ ] PostgreSQL用のテストフィクスチャが実装されている（クリーンアップ機能含む）
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

**問題**: スキーマのバージョン管理方針がない。

**改善案**: マイグレーションツール（Alembic）の導入

**推奨アプローチ**:

1. **Alembic の導入**:

   ```bash
   # Alembicの初期化
   alembic init alembic
   
   # マイグレーションの作成
   alembic revision --autogenerate -m "Initial schema"
   
   # マイグレーションの適用
   alembic upgrade head
   ```

2. **現状の対応**:
   - DDLスクリプトをバージョン管理
   - スキーマ変更時は手動でマイグレーションスクリプトを作成
   - 将来的にAlembicを導入する計画を立てる

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
pg_trgm を使用したハイブリッド検索を実装することで、
検索品質が大幅に向上します。

#### 11.1.1 pg_trgm の必須化

**現状**: pg_trgm は「オプション」として扱われていますが、**「推奨（将来的に必須）」**に格上げすることを検討してください。

**理由**:

- 日本語の全文検索や部分一致において、ベクトル検索を補完する効果が大きい
- 固有名詞（エラーコード、変数名、プロジェクトコード名など）の検索精度が向上
- PostgreSQL 標準拡張のため、追加の依存関係が不要

**実装方針**:

- Phase 8 の `_create_indexes` メソッドで既に pg_trgm 拡張とインデックスの作成を実装済み
- Phase 8.5 でハイブリッド検索クエリの実装を追加

**ハイブリッド検索の実装例**:

```python
# src/kotonoha_bot/features/knowledge_base/hybrid_search.py
"""ハイブリッド検索（ベクトル検索 + pg_trgm キーワード検索）"""

async def hybrid_search(
    self,
    query: str,
    query_embedding: list[float],
    top_k: int = 10,
    vector_weight: float = 0.7,
    keyword_weight: float = 0.3,
) -> list[dict]:
    """ハイブリッド検索を実行
    
    Args:
        query: 検索クエリ（テキスト）
        query_embedding: クエリのベクトル（1536次元）
        top_k: 取得する結果の数
        vector_weight: ベクトル類似度の重み（デフォルト: 0.7）
        keyword_weight: キーワード類似度の重み（デフォルト: 0.3）
    
    Returns:
        検索結果のリスト（combined_score でソート済み）
    """
    async with self.db.pool.acquire() as conn:
        # ベクトル検索とキーワード検索のスコアを組み合わせ
        rows = await conn.fetch("""
            WITH vector_results AS (
                SELECT 
                    c.id,
                    c.source_id,
                    c.content,
                    s.type as source_type,
                    s.title,
                    s.uri,
                    s.metadata as source_metadata,
                    1 - (c.embedding <=> $1::vector) AS vector_similarity
                FROM knowledge_chunks c
                JOIN knowledge_sources s ON c.source_id = s.id
                WHERE c.embedding IS NOT NULL
                  AND 1 - (c.embedding <=> $1::vector) > 0.7
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
                    similarity(c.content, $2) AS keyword_similarity
                FROM knowledge_chunks c
                JOIN knowledge_sources s ON c.source_id = s.id
                WHERE c.content % $2  -- pg_trgm の類似度演算子
            )
            SELECT 
                COALESCE(v.id, k.id) AS chunk_id,
                COALESCE(v.source_id, k.source_id) AS source_id,
                COALESCE(v.content, k.content) AS content,
                COALESCE(v.source_type, k.source_type) AS source_type,
                COALESCE(v.title, k.title) AS title,
                COALESCE(v.uri, k.uri) AS uri,
                COALESCE(v.source_metadata, k.source_metadata)
                    AS source_metadata,
                COALESCE(v.vector_similarity, 0) * $3 +
                COALESCE(k.keyword_similarity, 0) * $4 AS combined_score
            FROM vector_results v
            FULL OUTER JOIN keyword_results k ON v.id = k.id
            ORDER BY combined_score DESC
            LIMIT $5
        """, query_embedding, query, vector_weight, keyword_weight, top_k)
        
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

**完了基準**:

- [ ] pg_trgm 拡張が有効化されている
- [ ] `idx_chunks_content_trgm` インデックスが作成されている
- [ ] ハイブリッド検索メソッドが実装されている
- [ ] ベクトル検索とキーワード検索のスコアを組み合わせた検索が動作する
- [ ] 検索品質の向上が確認できる（固有名詞の検索精度が向上）

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
    ) -> list[dict]:
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
