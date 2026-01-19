# Phase 8: PostgreSQL + pgvector 実装計画書

**作成日**: 2026年1月19日  
**バージョン**: 2.0  
**対象プロジェクト**: kotonoha-bot v0.8.0  
**前提条件**: Phase 7（aiosqlite 実装）完了済み、全テスト通過

---

## 目次

1. [エグゼクティブサマリー](#1-エグゼクティブサマリー)
2. [現状分析](#2-現状分析)
3. [設計方針](#3-設計方針)
4. [データベーススキーマ設計](#4-データベーススキーマ設計)
5. [実装ステップ概要](#5-実装ステップ概要)
6. [完了基準](#6-完了基準)
7. [リスク管理](#7-リスク管理)
8. [導入・デプロイ手順](#8-導入デプロイ手順)
9. [将来の改善計画](#9-将来の改善計画)

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
2. **メタデータの柔軟性**: JSONB (`metadata`, `location`) を使用することで、ファイルの種類ごとに異なる属性（PDFのページ番号、音声の秒数など）を柔軟に管理できます
3. **状態管理**: `status` カラムにより、OCRやEmbeddingなどの重い処理をバックグラウンドワーカーに任せる設計（Producer-Consumerパターン）が容易に実装できます

### 3.3 非同期Embedding処理

**高速保存パターン**:

1. **即時保存**: テキストのみ保存（`embedding=NULL`）
2. **バックグラウンド処理**: 定期タスクでベクトル化して更新
3. **検索時**: `embedding IS NOT NULL` のレコードのみ検索対象

---

## 4. データベーススキーマ設計

> **参照**: 詳細なデータベーススキーマ設計については、
> [PostgreSQL スキーマ設計書](../../architecture/postgresql-schema-design.md)
> を参照してください。

このセクションでは、実装に必要なスキーマ設計の概要を説明します。
詳細なDDL、ER図、データフロー、設計のメリットなどは、
上記の設計書を参照してください。

### 4.1 スキーマ設計の概要

データベーススキーマは、**「短期記憶（Sessions）」** と **「長期記憶（Knowledge）」** の2つのエリアで構成されます。

- **短期記憶（Sessions）**: Discord Botがリアルタイムに読み書きする場所。高速動作優先。
- **長期記憶（Knowledge）**: AI検索用。あらゆるデータ（会話、ファイル、Web）を「Source」と「Chunk」に抽象化して管理。

詳細なER図、テーブル定義、インデックス設計については、
[PostgreSQL スキーマ設計書 - 2. ER図](../../architecture/postgresql-schema-design.md#2-er図)
および
[4. テーブル定義](../../architecture/postgresql-schema-design.md#4-テーブル定義)
を参照してください。

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

### 5.1 実装ステップ一覧

| Step | 内容 | 期間 | 詳細ドキュメント |
|------|------|------|------------------|
| 0 | 依存関係の確認と設計レビュー | 0.5日 | [PostgreSQL実装詳細](../postgresql-implementation.md#step-0-依存関係の確認と設計レビュー) |
| 1 | データベース抽象化レイヤーの実装 | 2-3日 | [PostgreSQL実装詳細](../postgresql-implementation.md#step-1-データベース抽象化レイヤーの実装) |
| 2 | PostgreSQL 実装の追加 | 3-4日 | [PostgreSQL実装詳細](../postgresql-implementation.md#step-2-postgresql-実装の追加) |
| 3 | ベクトル検索機能の実装 | 2-3日 | [PostgreSQL実装詳細](../postgresql-implementation.md#step-3-ベクトル検索機能の実装) |
| 4 | 知識ベーススキーマの実装 | 2-3日 | [PostgreSQL実装詳細](../postgresql-implementation.md#step-4-知識ベーススキーマの実装) |
| 5 | Embedding処理の実装 | 2-3日 | [Embedding処理詳細](../postgresql-embedding-processing.md) |
| 6 | Docker Compose の更新 | 1日 | [PostgreSQL実装詳細](../postgresql-implementation.md#step-6-docker-compose-の更新) |
| 7 | テストと最適化 | 1-2日 | [テスト戦略](../postgresql-testing-strategy.md) |
| **合計** | | **10-15日** | |

### 5.2 各ステップの概要

#### Step 0: 依存関係の確認と設計レビュー

**目的**: 実装前に設計を最終確認し、依存関係を整理する

**主要な作業**:

- 依存関係の追加確認（asyncpg, pgvector, pydantic-settings, alembic等）
- Alembicの初期化と初回マイグレーション
- `pydantic-settings`による環境変数の一元管理
- `constants.py`による定数管理
- 設計レビュー

**詳細**:
[PostgreSQL実装詳細](../postgresql-implementation.md#step-0-依存関係の確認と設計レビュー)
を参照

#### Step 1: データベース抽象化レイヤーの実装

**目的**: PostgreSQL実装のための抽象化レイヤーを定義し、将来の拡張性を確保する

**主要な作業**:

- `DatabaseProtocol`インターフェースの定義（セッション管理）
- `KnowledgeBaseProtocol`インターフェースの定義（知識ベース管理）
- `SearchResult`型定義

**詳細**:
[PostgreSQL実装詳細](../postgresql-implementation.md#step-1-データベース抽象化レイヤーの実装)
を参照

#### Step 2: PostgreSQL 実装の追加

**目的**: PostgreSQL + pgvector によるデータベース実装を追加する

**主要な作業**:

- `PostgreSQLDatabase`クラスの実装
- pgvector拡張の有効化と型登録
- JSONBコーデックの設定
- セッション管理メソッドの実装
- Alembicマイグレーションの自動適用

**詳細**:
[PostgreSQL実装詳細](../postgresql-implementation.md#step-2-postgresql-実装の追加)
を参照

#### Step 3: ベクトル検索機能の実装

**目的**: pgvector による類似度検索機能を実装する

**主要な作業**:

- `similarity_search`メソッドの実装
- フィルタリング機能（source_type, channel_id, user_id等）
- SQLインジェクション対策
- `halfvec`固定採用（メモリ使用量50%削減）
- `embedding IS NOT NULL`条件の強制付与

**詳細**: [PostgreSQL実装詳細](../postgresql-implementation.md#step-3-ベクトル検索機能の実装) を参照

#### Step 4: 知識ベーススキーマの実装

**目的**: Source-Chunk構造による知識ベーススキーマを実装する

**主要な作業**:

- `save_source`メソッドの実装
- `save_chunk`メソッドの実装
- トークン数カウント機能

**詳細**: [PostgreSQL実装詳細](../postgresql-implementation.md#step-4-知識ベーススキーマの実装) を参照

#### Step 5: Embedding処理の実装

**目的**: バックグラウンドタスクによる非同期Embedding処理を実装する

**主要な作業**:

- `EmbeddingProvider`インターフェースの定義
- `OpenAIEmbeddingProvider`の実装
- `EmbeddingProcessor`クラスの実装
- `FOR UPDATE SKIP LOCKED`パターンの実装
- トランザクション内でのAPIコールを回避（Tx1 → No Tx → Tx2）
- セマフォによる同時実行数制限
- Dead Letter Queue（DLQ）への移動ロジック
- Graceful Shutdownの実装

**詳細**: [Embedding処理詳細](../postgresql-embedding-processing.md) を参照

#### Step 5.4: セッション知識化バッチ処理の実装

**目的**: 非アクティブなセッションを知識ベースに変換する

**主要な作業**:

- `SessionArchiver`クラスの実装
- スライディングウィンドウ（のりしろ）方式の実装
- 楽観的ロックによる競合状態対策（`version`カラム）
- トランザクション分離レベル `REPEATABLE READ` の設定
- メッセージ単位/会話ターン単位でのチャンク化
- Graceful Shutdownの実装

**詳細**: [セッションアーカイブ詳細](../postgresql-session-archiving.md) を参照

#### Step 6: Docker Compose の更新

**目的**: PostgreSQLコンテナを追加し、開発環境を整備する

**主要な作業**:

- PostgreSQLコンテナの追加
- 環境変数の設定
- ヘルスチェックの設定

**詳細**:
[PostgreSQL実装詳細](../postgresql-implementation.md#step-6-docker-compose-の更新)
を参照

#### Step 7: テストと最適化

**目的**: テストを充実させ、パフォーマンスを最適化する

**主要な作業**:

- PostgreSQL用テストフィクスチャの追加
- ユニットテストの実装
- 統合テストの実装
- パフォーマンステストの実施
- インデックスの最適化
- 接続プールの調整

**詳細**: [テスト戦略](../postgresql-testing-strategy.md) を参照

---

## 6. 完了基準

### 6.1 必須項目

#### PostgreSQL実装（Step 2）

- `PostgreSQLDatabase`クラスが実装されている
- pgvector拡張が有効化されている
- JSONBコーデックが実装されている
- 接続プール管理が実装されている
- Alembicマイグレーションが自動適用される

#### ベクトル検索機能（Step 3）

- `similarity_search`メソッドが実装されている
- `halfvec`固定採用が実装されている
- `embedding IS NOT NULL`条件が強制付与されている
- フィルタリング機能が実装されている
- SQLインジェクション対策が実装されている

#### 知識ベーススキーマ（Step 4）

- `knowledge_sources`テーブルが作成される
- `knowledge_chunks`テーブルが作成される
- `save_source`メソッドが実装されている
- `save_chunk`メソッドが実装されている

#### Embedding処理（Step 5）

- `EmbeddingProvider`インターフェースが定義されている
- `OpenAIEmbeddingProvider`が実装されている
- Embedding APIのリトライロジックが実装されている
- `EmbeddingProcessor`クラスが実装されている
- バックグラウンドタスクが動作する
- `FOR UPDATE SKIP LOCKED`パターンが実装されている
- トランザクション内でのAPIコールを回避している
- セマフォによる同時実行数制限が実装されている
- DLQへの移動ロジックが実装されている
- Graceful Shutdownが実装されている

#### セッション知識化処理（Step 5.4）

- `SessionArchiver`クラスが実装されている
- セッション知識化処理が動作する
- スライディングウィンドウ（のりしろ）方式が実装されている
- 楽観的ロック（`version`カラム）が実装されている
- トランザクション分離レベルが`REPEATABLE READ`に設定されている
- メッセージ単位でのチャンク化が実装されている
- フィルタリングロジック（短いセッション、Botのみのセッション除外）が実装されている
- Graceful Shutdownが実装されている

#### テスト（Step 7）

- PostgreSQL用のテストフィクスチャが追加されている
- 主要な機能のテストが実装されている
- テストカバレッジが80%以上になっている
- すべてのテストが通過する

### 6.2 品質チェックコマンド

```bash
# テスト実行
pytest tests/ -v --cov=src/kotonoha_bot --cov-report=term-missing

# 型チェック
mypy src/kotonoha_bot

# リンター
ruff check src/kotonoha_bot
```

---

## 7. リスク管理

### 7.1 主要なリスク概要

| リスク | 影響度 | 対策 |
|--------|--------|------|
| PostgreSQL 18の新しさによる未知のバグ | 高 | テストスクリプトを充実させる |
| HNSWインデックスのメモリ消費 | 中 | `maintenance_work_mem`を制限 |
| 接続プール枯渇 | 中 | セマフォによる同時実行数制限 |
| Embedding APIのレート制限 | 中 | リトライロジックとバッチ処理 |

### 7.2 Synology NAS特有の課題

- **メモリ制約**: NASのメモリが少ない場合、HNSWインデックスの構築時にOOM Killerが発動する可能性
- **対策**: `maintenance_work_mem`を256MB〜512MB程度に制限

詳細は
[PostgreSQL スキーマ設計書 - 5. インデックス設計](../../architecture/postgresql-schema-design.md#5-インデックス設計)
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

詳細は [PostgreSQL実装詳細](../postgresql-implementation.md#導入デプロイ手順) を参照してください。

---

## 9. 将来の改善計画

### 9.1 Phase 8.5: ハイブリッド検索の実装（推奨）

**目的**: ベクトル検索とキーワード検索を組み合わせたハイブリッド検索を実装する

**背景**: ベクトル検索は「概念的な類似」には強いですが、「固有名詞（例：プロジェクトコード名、特定のエラーコード）」の完全一致検索には弱いです。

**推奨実装**: pg_bigm を使用した日本語検索

- **pg_bigm の利点**: 2-gram（2文字単位）による日本語検索の精度向上
- **実装方法**: Dockerfile.postgresでpg_bigmをビルドしたカスタムイメージを作成

詳細は
[PostgreSQL スキーマ設計書 - 10.4 ハイブリッド検索](../../architecture/postgresql-schema-design.md#104-ハイブリッド検索hybrid-searchの導入)
を参照してください。

### 9.2 Phase 9: Reranking の実装（オプション）

**目的**: ベクトル検索の結果を再ランキングして精度を向上させる

**実装方法**: Cross-Encoderモデルを使用した再ランキング

---

## 参考資料

- **スキーマ設計書**: [PostgreSQL スキーマ設計書](../../architecture/postgresql-schema-design.md)
- **実装詳細**:
  - [PostgreSQL実装詳細](../postgresql-implementation.md)
  - [Embedding処理詳細](../postgresql-embedding-processing.md)
  - [セッションアーカイブ詳細](../postgresql-session-archiving.md)
  - [テスト戦略](../postgresql-testing-strategy.md)

---

**作成日**: 2026年1月19日  
**最終更新日**: 2026年1月19日（v2.0 - 概要版に再構成）
