# Phase 8: PostgreSQL + pgvector 実装完了報告

**作成日**: 2026年1月19日  
**完了日**: 2026年1月（実装完了）  
**バージョン**: 2.0  
**対象プロジェクト**: kotonoha-bot v0.8.0  
**前提条件**: Phase 7（aiosqlite 実装）完了済み、全テスト通過

---

## 目次

1. [エグゼクティブサマリー](#1-エグゼクティブサマリー)
2. [実装完了サマリー](#2-実装完了サマリー)
3. [実装された機能](#3-実装された機能)
4. [完了基準の達成状況](#4-完了基準の達成状況)
5. [実装ステップと成果](#5-実装ステップと成果)
6. [データベーススキーマ設計](#6-データベーススキーマ設計)
7. [テスト結果](#7-テスト結果)
8. [導入・デプロイ手順](#8-導入デプロイ手順)
9. [今後の改善計画](#9-今後の改善計画)

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

### 1.4 実装期間

約 10-15 日（計画通り完了）

---

## 2. 実装完了サマリー

### 2.1 実装完了状況

Phase 8の実装は**完了**しました。以下の主要機能が実装され、動作確認済みです。

### 2.2 実装完了項目

| 項目 | 実装状況 | 備考 |
|------|---------|------|
| PostgreSQL実装 | ✅ 完了 | `PostgreSQLDatabase`クラス実装済み |
| 知識ベーススキーマ | ✅ 完了 | `knowledge_sources`と`knowledge_chunks`テーブル実装済み |
| ベクトル検索機能 | ✅ 完了 | pgvectorによる`similarity_search`実装済み |
| Embedding処理 | ✅ 完了 | `EmbeddingProcessor`によるバックグラウンド処理実装済み |
| セッション知識化 | ✅ 完了 | `SessionArchiver`による自動アーカイブ実装済み |
| Docker Compose | ✅ 完了 | PostgreSQLコンテナ追加済み |
| テスト | ✅ 完了 | 統合テスト・ユニットテスト実装済み |

### 2.3 実装ファイル一覧

主要な実装ファイル：

- `src/kotonoha_bot/db/postgres.py`: PostgreSQLDatabaseクラス
- `src/kotonoha_bot/db/base.py`: データベース抽象化レイヤー（Protocol定義）
- `src/kotonoha_bot/features/knowledge_base/embedding_processor.py`: Embedding処理
- `src/kotonoha_bot/features/knowledge_base/session_archiver.py`: セッション知識化処理
- `alembic/versions/`: データベースマイグレーション
- `docker-compose.yml`: PostgreSQLコンテナ設定

---

## 3. 実装された機能

### 3.1 PostgreSQL実装

**実装内容**:

- `PostgreSQLDatabase`クラスが`DatabaseProtocol`と`KnowledgeBaseProtocol`の両方を実装
- asyncpgによる非同期接続プール管理
- pgvector拡張の自動有効化
- JSONBコーデック（orjson）による高速シリアライゼーション
- Alembicによる自動マイグレーション適用

**実装ファイル**: `src/kotonoha_bot/db/postgres.py`

### 3.2 知識ベーススキーマ

**実装内容**:

- `knowledge_sources`テーブル: データの出処を管理（Source-Chunk構造の親）
- `knowledge_chunks`テーブル: 検索対象となるテキストとベクトルを管理
- `halfvec`型によるメモリ使用量50%削減
- JSONBによる柔軟なメタデータ管理

**実装ファイル**: `alembic/versions/ca650c17adda_initial_schema.py`

### 3.3 ベクトル検索機能

**実装内容**:

- `similarity_search`メソッドによるpgvector検索
- `halfvec`固定採用（メモリ効率化）
- `embedding IS NOT NULL`条件の強制付与
- フィルタリング機能（source_type, channel_id, user_id等）
- SQLインジェクション対策（Allow-list方式）

**実装ファイル**: `src/kotonoha_bot/db/postgres.py`（`similarity_search`メソッド）

### 3.4 Embedding処理

**実装内容**:

- `EmbeddingProvider`インターフェースの定義
- `OpenAIEmbeddingProvider`の実装（text-embedding-3-small）
- `EmbeddingProcessor`によるバックグラウンドタスク
- `FOR UPDATE SKIP LOCKED`パターンによる競合回避
- トランザクション内でのAPIコール回避（Tx1 → No Tx → Tx2）
- セマフォによる同時実行数制限
- Dead Letter Queue（DLQ）への移動ロジック
- Graceful Shutdownの実装

**実装ファイル**:

- `src/kotonoha_bot/features/knowledge_base/embedding_processor.py`
- `src/kotonoha_bot/external/embedding.py`

### 3.5 セッション知識化処理

**実装内容**:

- `SessionArchiver`による非アクティブセッションの自動アーカイブ
- スライディングウィンドウ（のりしろ）方式によるチャンク化
- 楽観的ロック（`version`カラム）による競合状態対策
- トランザクション分離レベル`REPEATABLE READ`の設定
- メッセージ単位/会話ターン単位でのチャンク化
- フィルタリングロジック（短いセッション、Botのみのセッション除外）
- Graceful Shutdownの実装

**実装ファイル**: `src/kotonoha_bot/features/knowledge_base/session_archiver.py`

### 3.6 Docker Compose

**実装内容**:

- PostgreSQLコンテナ（pgvector/pgvector:0.8.1-pg18）の追加
- ヘルスチェック設定
- ボリューム管理（postgres_data）
- ネットワーク設定（kotonoha-network）

**実装ファイル**: `docker-compose.yml`

---

## 4. 完了基準の達成状況

### 4.1 PostgreSQL実装（Step 2）

- ✅ `PostgreSQLDatabase`クラスが実装されている
- ✅ pgvector拡張が有効化されている
- ✅ JSONBコーデックが実装されている
- ✅ 接続プール管理が実装されている
- ✅ Alembicマイグレーションが自動適用される

### 4.2 ベクトル検索機能（Step 3）

- ✅ `similarity_search`メソッドが実装されている
- ✅ `halfvec`固定採用が実装されている
- ✅ `embedding IS NOT NULL`条件が強制付与されている
- ✅ フィルタリング機能が実装されている
- ✅ SQLインジェクション対策が実装されている

### 4.3 知識ベーススキーマ（Step 4）

- ✅ `knowledge_sources`テーブルが作成される
- ✅ `knowledge_chunks`テーブルが作成される
- ✅ `save_source`メソッドが実装されている
- ✅ `save_chunk`メソッドが実装されている

### 4.4 Embedding処理（Step 5）

- ✅ `EmbeddingProvider`インターフェースが定義されている
- ✅ `OpenAIEmbeddingProvider`が実装されている
- ✅ Embedding APIのリトライロジックが実装されている
- ✅ `EmbeddingProcessor`クラスが実装されている
- ✅ バックグラウンドタスクが動作する
- ✅ `FOR UPDATE SKIP LOCKED`パターンが実装されている
- ✅ トランザクション内でのAPIコールを回避している
- ✅ セマフォによる同時実行数制限が実装されている
- ✅ DLQへの移動ロジックが実装されている
- ✅ Graceful Shutdownが実装されている

### 4.5 セッション知識化処理（Step 5.4）

- ✅ `SessionArchiver`クラスが実装されている
- ✅ セッション知識化処理が動作する
- ✅ スライディングウィンドウ（のりしろ）方式が実装されている
- ✅ 楽観的ロック（`version`カラム）が実装されている
- ✅ トランザクション分離レベルが`REPEATABLE READ`に設定されている
- ✅ メッセージ単位でのチャンク化が実装されている
- ✅ フィルタリングロジック（短いセッション、Botのみのセッション除外）が実装されている
- ✅ Graceful Shutdownが実装されている

### 4.6 テスト（Step 7）

- ✅ PostgreSQL用のテストフィクスチャが追加されている
- ✅ 主要な機能のテストが実装されている
- ✅ 統合テストが実装されている（`tests/integration/`）
- ✅ テストが通過する

---

## 5. 実装ステップと成果

### 2.1 現在のデータベース実装

- **SQLite**: `src/kotonoha_bot/db/sqlite.py` - Phase 7で実装済み
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

---

## 3. 設計方針

### 3.1 PostgreSQL実装の方針

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

1. **拡張性**: 将来「動画検索」を追加する場合、`source_type` に `video` を追加するだけで、
   テーブル構造を変更する必要がありません
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
> [PostgreSQL スキーマ設計書](../../40_design_detailed/42_db-schema-physical/postgresql-schema-overview.md)
> を参照してください。

このセクションでは、実装に必要なスキーマ設計の概要を説明します。
詳細なDDL、ER図、データフロー、設計のメリットなどは、
上記の設計書を参照してください。

### 4.1 スキーマ設計の概要

データベーススキーマは、**「短期記憶（Sessions）」** と **「長期記憶（Knowledge）」** の2つのエリアで構成されます。

- **短期記憶（Sessions）**: Discord Botがリアルタイムに読み書きする場所。高速動作優先。
- **長期記憶（Knowledge）**: AI検索用。あらゆるデータ（会話、ファイル、Web）を「Source」と「Chunk」に抽象化して管理。

詳細なER図、テーブル定義、インデックス設計については、
[PostgreSQL スキーマ設計書 - 2. ER図](../../40_design_detailed/42_db-schema-physical/
postgresql-schema-overview.md#2-er図) および
[4. テーブル定義](../../40_design_detailed/42_db-schema-physical/
postgresql-schema-overview.md#4-テーブル定義) を参照してください。

### 4.2 データフローの概要

主なデータフロー：

1. **リアルタイム会話**: `sessions` テーブルにメッセージを追記（APIコストゼロ）
2. **知識化バッチ処理**: 非アクティブなセッションを `knowledge_sources` と `knowledge_chunks` に変換
3. **マルチモーダル入力**: PDF/画像などを `knowledge_sources` に登録し、バックグラウンドで処理
4. **統合検索**: pgvector によるベクトル類似度検索で、すべてのデータソースを横断検索

### 4.3 設計のメリット

主なメリット：

- **短期記憶と長期記憶の分離**: それぞれ最適化されたインデックスで管理
- **拡張性**: 将来の機能拡張に対応可能
- **メタデータの柔軟性**: JSONBによる柔軟な属性管理
- **状態管理**: Producer-Consumerパターンが容易
- **マルチモーダル対応**: すべてのデータを同じスキーマで管理
- **統合検索**: 1つのSQLクエリで横断検索

---

## 5. 実装ステップ概要

### 5.1 実装ステップと完了状況

| Step | 内容 | 期間 | 完了状況 | 詳細ドキュメント |
|------|------|------|---------|------------------|
| 0 | 依存関係の確認と設計レビュー | 0.5日 | ✅ 完了 | [PostgreSQL実装詳細](../../50_implementation/52_procedures/postgresql-implementation.md#step-0-依存関係の確認と設計レビュー) |
| 1 | データベース抽象化レイヤーの実装 | 2-3日 | ✅ 完了 | [PostgreSQL実装詳細](../../50_implementation/52_procedures/postgresql-implementation.md#step-1-データベース抽象化レイヤーの実装) |
| 2 | PostgreSQL 実装の追加 | 3-4日 | ✅ 完了 | [PostgreSQL実装詳細](../../50_implementation/52_procedures/postgresql-implementation.md#step-2-postgresql-実装の追加) |
| 3 | ベクトル検索機能の実装 | 2-3日 | ✅ 完了 | [PostgreSQL実装詳細](../../50_implementation/52_procedures/postgresql-implementation.md#step-3-ベクトル検索機能の実装) |
| 4 | 知識ベーススキーマの実装 | 2-3日 | ✅ 完了 | [PostgreSQL実装詳細](../../50_implementation/52_procedures/postgresql-implementation.md#step-4-知識ベーススキーマの実装) |
| 5 | Embedding処理の実装 | 2-3日 | ✅ 完了 | [Embedding処理詳細](../../50_implementation/52_procedures/postgresql-embedding-processing.md) |
| 5.4 | セッション知識化バッチ処理の実装 | 2-3日 | ✅ 完了 | [セッションアーカイブ詳細](../../50_implementation/52_procedures/postgresql-session-archiving.md) |
| 6 | Docker Compose の更新 | 1日 | ✅ 完了 | [PostgreSQL実装詳細](../../50_implementation/52_procedures/postgresql-implementation.md#step-6-docker-compose-の更新) |
| 7 | テストと最適化 | 1-2日 | ✅ 完了 | [テスト戦略](../../60_testing/postgresql-testing-strategy.md) |
| **合計** | | **10-15日** | **✅ 完了** | |

### 5.2 各ステップの実装成果

#### Step 0: 依存関係の確認と設計レビュー ✅

**完了内容**:

- 依存関係の追加（asyncpg, pgvector, pydantic-settings, alembic等）
- Alembicの初期化と初回マイグレーション実装
- `pydantic-settings`による環境変数の一元管理
- 設計レビュー完了

#### Step 1: データベース抽象化レイヤーの実装 ✅

**完了内容**:

- `DatabaseProtocol`インターフェースの定義（`src/kotonoha_bot/db/base.py`）
- `KnowledgeBaseProtocol`インターフェースの定義
- `SearchResult`型定義

#### Step 2: PostgreSQL 実装の追加 ✅

**完了内容**:

- `PostgreSQLDatabase`クラスの実装（`src/kotonoha_bot/db/postgres.py`）
- pgvector拡張の有効化と型登録
- JSONBコーデック（orjson）の設定
- セッション管理メソッドの実装
- Alembicマイグレーションの自動適用

#### Step 3: ベクトル検索機能の実装 ✅

**完了内容**:

- `similarity_search`メソッドの実装
- フィルタリング機能（source_type, channel_id, user_id等）
- SQLインジェクション対策（Allow-list方式）
- `halfvec`固定採用（メモリ使用量50%削減）
- `embedding IS NOT NULL`条件の強制付与

#### Step 4: 知識ベーススキーマの実装 ✅

**完了内容**:

- `save_source`メソッドの実装
- `save_chunk`メソッドの実装
- トークン数カウント機能（tiktoken使用）
- Alembicマイグレーションによるテーブル作成

#### Step 5: Embedding処理の実装 ✅

**完了内容**:

- `EmbeddingProvider`インターフェースの定義（`src/kotonoha_bot/external/embedding.py`）
- `OpenAIEmbeddingProvider`の実装
- `EmbeddingProcessor`クラスの実装（`src/kotonoha_bot/features/knowledge_base/embedding_processor.py`）
- `FOR UPDATE SKIP LOCKED`パターンの実装
- トランザクション内でのAPIコールを回避（Tx1 → No Tx → Tx2）
- セマフォによる同時実行数制限
- Dead Letter Queue（DLQ）への移動ロジック
- Graceful Shutdownの実装

#### Step 5.4: セッション知識化バッチ処理の実装 ✅

**完了内容**:

- `SessionArchiver`クラスの実装（`src/kotonoha_bot/features/knowledge_base/session_archiver.py`）
- スライディングウィンドウ（のりしろ）方式の実装
- 楽観的ロックによる競合状態対策（`version`カラム）
- トランザクション分離レベル`REPEATABLE READ`の設定
- メッセージ単位/会話ターン単位でのチャンク化
- フィルタリングロジック（短いセッション、Botのみのセッション除外）
- Graceful Shutdownの実装

#### Step 6: Docker Compose の更新 ✅

**完了内容**:

- PostgreSQLコンテナの追加（`docker-compose.yml`）
- 環境変数の設定
- ヘルスチェックの設定
- ボリューム管理（postgres_data）

#### Step 7: テストと最適化 ✅

**完了内容**:

- PostgreSQL用テストフィクスチャの追加（`tests/conftest.py`）
- ユニットテストの実装（`tests/unit/`）
- 統合テストの実装（`tests/integration/`）
- パフォーマンステストの実施（`tests/performance/`）

---

## 6. データベーススキーマ設計

> **参照**: 詳細なデータベーススキーマ設計については、
> [PostgreSQL スキーマ設計書](../../40_design_detailed/42_db-schema-physical/postgresql-schema-overview.md)
> を参照してください。

### 6.1 実装されたスキーマ概要

データベーススキーマは、**「短期記憶（Sessions）」** と **「長期記憶（Knowledge）」** の2つのエリアで構成されています。

- **短期記憶（Sessions）**: Discord Botがリアルタイムに読み書きする場所。高速動作優先。
- **長期記憶（Knowledge）**: AI検索用。あらゆるデータ（会話、ファイル、Web）を「Source」と「Chunk」に抽象化して管理。

### 6.2 実装されたテーブル

- `sessions`: セッション管理テーブル
- `knowledge_sources`: データの出処を管理（Source-Chunk構造の親）
- `knowledge_chunks`: 検索対象となるテキストとベクトルを管理

詳細なER図、テーブル定義、インデックス設計については、
[PostgreSQL スキーマ設計書](../../40_design_detailed/42_db-schema-physical/postgresql-schema-overview.md)
を参照してください。

---

## 7. テスト結果

### 7.1 実装されたテスト

#### ユニットテスト

- `tests/unit/test_postgres_db.py`: PostgreSQLDatabaseクラスのユニットテスト
- `tests/unit/test_embedding_processor.py`: EmbeddingProcessorのユニットテスト
- `tests/unit/test_session_archiver.py`: SessionArchiverのユニットテスト

#### 統合テスト

- `tests/integration/test_session_management.py`: セッション管理の統合テスト
- `tests/integration/test_vector_search.py`: ベクトル検索の統合テスト
- `tests/integration/test_embedding_processing.py`: Embedding処理の統合テスト
- `tests/integration/test_session_archiving.py`: セッション知識化の統合テスト
- `tests/integration/test_knowledge_base_storage.py`: 知識ベースストレージの統合テスト
- `tests/integration/test_concurrent_processing.py`: 並行処理の統合テスト

#### パフォーマンステスト

- `tests/performance/test_vector_search.py`: ベクトル検索のパフォーマンステスト
- `tests/performance/test_load.py`: 負荷テスト

### 7.2 テスト実行方法

```bash
# 全テスト実行
pytest tests/ -v

# 統合テストのみ実行
pytest tests/integration/ -v

# カバレッジ付きテスト実行
pytest tests/ -v --cov=src/kotonoha_bot --cov-report=term-missing

# 型チェック
mypy src/kotonoha_bot

# リンター
ruff check src/kotonoha_bot
```

### 7.3 テスト結果

すべてのテストが実装され、動作確認済みです。詳細なテスト仕様については、
[テスト戦略](../../60_testing/postgresql-testing-strategy.md)
を参照してください。

---

## 8. 導入・デプロイ手順

### 8.1 開発環境での導入

1. **依存関係のインストール**

   ```bash
   uv sync
   ```

2. **環境変数の設定**
   `.env`ファイルを作成し、必要な環境変数を設定

3. **PostgreSQLコンテナの起動**

   ```bash
   docker compose up -d postgres
   ```

4. **Alembicマイグレーションの適用**
   Bot起動時に自動適用されます

5. **Botの起動**

   ```bash
   docker compose up kotonoha-bot
   ```

### 8.2 本番環境でのデプロイ

1. **PostgreSQLコンテナの準備**
   - カスタムイメージ（pg_bigm含む）のビルド
   - 環境変数の設定

2. **データベースの初期化**
   - Alembicマイグレーションの適用

3. **Botのデプロイ**
   - 環境変数の設定
   - コンテナの起動

詳細は
[PostgreSQL実装詳細](../../50_implementation/52_procedures/postgresql-implementation.md#導入デプロイ手順)
を参照してください。

---

## 9. 今後の改善計画

### 9.1 Phase 8.5: ハイブリッド検索の実装（推奨）

**目的**: ベクトル検索とキーワード検索を組み合わせたハイブリッド検索を実装する

**背景**: ベクトル検索は「概念的な類似」には強いですが、「固有名詞（例：プロジェクトコード名、特定のエラーコード）」の完全一致検索には弱いです。

**推奨実装**: pg_bigm を使用した日本語検索

- **pg_bigm の利点**: 2-gram（2文字単位）による日本語検索の精度向上
- **実装方法**: Dockerfile.postgresでpg_bigmをビルドしたカスタムイメージを作成

詳細は
[PostgreSQL スキーマ設計書 - 10.4 ハイブリッド検索](../../40_design_detailed/42_db-schema-physical/postgresql-schema-overview.md#104-ハイブリッド検索hybrid-searchの導入)
を参照してください。

### 9.2 Phase 9: Reranking の実装（オプション）

**目的**: ベクトル検索の結果を再ランキングして精度を向上させる

**実装方法**: Cross-Encoderモデルを使用した再ランキング

---

## 参考資料

- **スキーマ設計書**: [PostgreSQL スキーマ設計書](../../40_design_detailed/42_db-schema-physical/postgresql-schema-overview.md)
- **実装詳細**:
  - [PostgreSQL実装詳細](../../50_implementation/52_procedures/postgresql-implementation.md)
  - [Embedding処理詳細](../../50_implementation/52_procedures/postgresql-embedding-processing.md)
  - [セッションアーカイブ詳細](../../50_implementation/52_procedures/postgresql-session-archiving.md)
  - [テスト戦略](../../60_testing/postgresql-testing-strategy.md)

---

**作成日**: 2026年1月19日  
**完了日**: 2026年1月（実装完了）  
**最終更新日**: 2026年1月（実装完了報告に更新）
