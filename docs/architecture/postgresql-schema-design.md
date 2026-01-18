# PostgreSQL スキーマ設計書

**作成日**: 2026年1月19日  
**バージョン**: 1.22  
**対象プロジェクト**: kotonoha-bot v0.8.0  
**データベース**: PostgreSQL 18 + pgvector 0.8.1

---

## 目次

1. [概要](#1-概要)
2. [ER図](#2-er図)
3. [拡張機能と型定義](#3-拡張機能と型定義)
4. [テーブル定義](#4-テーブル定義)
5. [インデックス設計](#5-インデックス設計)
6. [制約とリレーション](#6-制約とリレーション)
7. [データ型の説明](#7-データ型の説明)
8. [使用例とクエリ](#8-使用例とクエリ)
9. [パフォーマンス考慮事項](#9-パフォーマンス考慮事項)
10. [将来の拡張性](#10-将来の拡張性)
11. [実装上の注意事項とベストプラクティス](#11-実装上の注意事項とベストプラクティス)
12. [バックアップ戦略](#12-バックアップ戦略)

---

## 1. 概要

### 1.1 目的

このスキーマ設計書は、kotonoha-bot の PostgreSQL データベーススキーマを定義します。以下の機能を実現するための設計です：

- **短期記憶（Sessions）**: Discord Bot のリアルタイム会話セッション管理
- **長期記憶（Knowledge Base）**: ベクトル検索による統合知識ベース
- **マルチモーダル対応**: 会話、ファイル、Web、画像、音声など多様なデータソースの統合管理

### 1.2 設計思想

#### すべてのデータを「Source」と「Chunk」に抽象化する

- **Source（親）**: データの「出処」を管理（ファイルメタデータ、WebのURL、Discordのスレッド情報）
- **Chunk（子）**: 検索対象となる「テキスト実体」と「ベクトル」を管理

この設計により、将来の機能拡張（動画検索など）にも柔軟に対応できます。

### 1.3 技術スタック

- **データベース**: PostgreSQL 18（2024年9月リリース）
- **ベクトル拡張**: pgvector 0.8.1（HNSWインデックス対応、PostgreSQL 18 サポート）
  - **Pythonライブラリ**: `pgvector>=0.3.6`（pgvector 0.8.x 拡張に対応）
- **非同期ライブラリ**: asyncpg 0.29.0以降
- **Embeddingモデル**: OpenAI text-embedding-3-small (1536次元)

### 1.4 PostgreSQL 18 使用に伴うテスト戦略

PostgreSQL 18は比較的新しいバージョンであるため、本番環境での安定性を確保するために、**テストスクリプトを充実させる方針**を採用します。

#### テスト戦略の重点項目

1. **統合テストの充実**
   - PostgreSQL 18 + pgvector 0.8.1 の組み合わせでの動作確認
   - HNSWインデックスの構築・検索性能テスト
   - halfvec型の型キャストと演算のテスト

2. **パフォーマンステスト**
   - 大量データ（10万件以上）でのインデックス構築時間の測定
   - ベクトル検索のクエリ性能テスト
   - 接続プールの負荷テスト

3. **互換性テスト**
   - asyncpg 0.29.0以降との互換性確認
   - pgvector-python ライブラリとの型登録テスト
   - JSONBコーデックの動作確認

4. **回帰テスト**
   - 既存機能（SQLite移行前の機能）の動作確認
   - データマイグレーションスクリプトのテスト

5. **CI/CDでの自動テスト**
   - GitHub Actionsでの自動テスト実行
   - PostgreSQL 18コンテナを使用した統合テスト
   - テストカバレッジ80%以上の維持

**テスト実装の詳細**: テストスクリプトの実装方法については、
[11. 実装上の注意事項とベストプラクティス](#11-実装上の注意事項とベストプラクティス)
のセクションを参照してください。

---

## 2. ER図

```mermaid
erDiagram
    %% Short-term Memory: Sessions (Left Side)
    %% Real-time read/write area for Discord Bot. Optimized for speed.
    sessions {
        BIGSERIAL id PK "Session ID (for future foreign key references)"
        TEXT session_key UK "Discord ChannelID or ThreadID (for application lookup)"
        TEXT session_type "Session type"
        JSONB messages "Conversation history"
        session_status_enum status "Status (active/archived)"
        BIGINT guild_id "Discord Guild ID"
        BIGINT channel_id "Discord channel ID"
        BIGINT thread_id "Discord thread ID"
        BIGINT user_id "User ID"
        TIMESTAMPTZ created_at "Created timestamp"
        TIMESTAMPTZ last_active_at "Last active timestamp"
    }

    %% Long-term Memory: Knowledge (Right Side)
    %% AI search area. All data (conversations, files, web) abstracted as
    %% "Source" and "Chunk".
    knowledge_sources {
        BIGSERIAL id PK "Knowledge source ID"
        source_type_enum type "Source type"
        TEXT title "Title for search results"
        TEXT uri "Link to original data"
        source_status_enum status "Processing status"
        TEXT error_message "Error message"
        JSONB metadata "Flexible metadata"
        TIMESTAMPTZ created_at "Created timestamp"
        TIMESTAMPTZ updated_at "Updated timestamp"
    }

    knowledge_chunks {
        BIGSERIAL id PK "Chunk ID"
        BIGINT source_id FK "Reference to parent source"
        TEXT content "Searchable text content"
        vector_1536 embedding "Vector data (1536 dimensions, nullable)"
        JSONB location "Location info in original data"
        INT token_count "Token count"
        INT retry_count "Retry count for DLQ"
        TIMESTAMPTZ created_at "Created timestamp"
    }

    %% Relationships
    knowledge_sources ||--o{ knowledge_chunks : "has many"
    %% Conversion from sessions to knowledge_sources is done by batch
    %% processing (not shown in ER diagram)
```

**構成の説明**:

- **Left Side (Sessions)**: Discord Botがリアルタイムに読み書きする領域。高速動作を優先。
- **Right Side (Knowledge)**: AI検索用。あらゆるデータ（会話、ファイル、Web）を
  「Source」と「Chunk」に抽象化して管理。
- **データフロー**: `sessions` テーブルの非アクティブなセッションは、
  バッチ処理によって `knowledge_sources` と `knowledge_chunks` に変換されます。

---

## 3. 拡張機能と型定義

### 3.1 拡張機能

```sql
-- ベクトル検索機能の有効化 (必須)
CREATE EXTENSION IF NOT EXISTS vector;
```

**要件**: pgvector 0.8.1（PostgreSQL 18 サポート、HNSWインデックス対応）

### 3.2 ENUM型定義

#### source_type_enum

データソースの種類を定義します。将来の拡張に対応できるよう、ENUM型を使用しています。

```sql
CREATE TYPE source_type_enum AS ENUM (
    'discord_session',   -- 会話ログ
    'document_file',     -- PDF, Word, Txt
    'web_page',          -- URLスクレイピング
    'image_caption',     -- 画像説明文
    'audio_transcript'   -- 音声議事録
);
```

**使用箇所**: `knowledge_sources.type`

#### session_status_enum

セッションの状態を定義します。短期記憶（sessions）テーブル専用です。

```sql
CREATE TYPE session_status_enum AS ENUM (
    'active',    -- 会話中
    'archived'   -- 知識化済み・アーカイブ
);
```

**使用箇所**: `sessions.status`

#### source_status_enum

知識ソースの処理ステータスを定義します。非同期パイプラインでの状態管理に使用します。

```sql
CREATE TYPE source_status_enum AS ENUM (
    'pending',      -- 処理待ち
    'processing',   -- ベクトル化やOCR処理中
    'completed',    -- 検索可能（すべてのチャンクが正常に処理された）
    'partial',      -- ⚠️ 改善（データ整合性）: 一部のチャンクがDLQに移動した（検索可能だが不完全）
    'failed'        -- エラー
);
```

**使用箇所**: `knowledge_sources.status`

**設計理由**: 意味論的に異なるステータスを分離することで、型安全性と可読性が向上します。

---

## 4. テーブル定義

### 4.1 sessions テーブル

**目的**: Discord Bot のリアルタイム会話セッションを管理します。高速な読み書きに最適化されています。

#### 設計考慮事項

**主キーの選定**:

- **⚠️ 改善（Strong Recommendation）**: `id BIGSERIAL PRIMARY KEY` を追加し、
  `session_key` は `TEXT UNIQUE NOT NULL` に変更
- **理由**: 「新規設計で移行ツールを作らない」という前提であれば、最初から最適解を選ぶべき
- **問題点（TEXT型主キー）**:
  - インデックスサイズが肥大化し、将来的に外部キー参照を行う際にパフォーマンス（JOIN速度）とストレージ効率が悪化
  - 将来的に `sessions` テーブルに紐づく別テーブル（例：`session_tags` テーブルなど）を作る際に非効率
- **改善案（採用）**:
  - `id BIGSERIAL PRIMARY KEY` を追加
  - `session_key` は `TEXT UNIQUE NOT NULL` にする
  - アプリケーション内部での参照は `session_key` を使いつつ、将来的なリレーションは `id` を使う余地を残す
- **将来の拡張性**:
  - 複数のDiscordサーバー（Guild）で運用する場合、`guild_id` との複合キーを検討可能
  - 外部キー参照が必要になった場合、`id` を使用することで効率的なJOINが可能

#### sessions テーブルのDDL

```sql
CREATE TABLE IF NOT EXISTS sessions (
    -- ⚠️ 改善: id BIGSERIAL PRIMARY KEY を追加
    -- 理由: 「新規設計で移行ツールを作らない」という前提であれば、最初から最適解を選ぶべき
    -- TEXT型の主キーはインデックスサイズが肥大化し、将来的に外部キー参照を行う際に
    -- パフォーマンス（JOIN速度）とストレージ効率が悪化する
    id BIGSERIAL PRIMARY KEY,
    
    -- アプリケーション内部での参照用（UNIQUE NOT NULL）
    -- DiscordのChannelIDやThreadIDが入る
    session_key TEXT UNIQUE NOT NULL,

    -- セッションの種類 ('mention', 'thread', 'eavesdrop' 等)
    session_type TEXT NOT NULL,

    -- 会話履歴本体 (高速な読み書きのためJSONBを採用)
    -- 構造例: [{"role": "user", "content": "..."},
    -- {"role": "assistant", "content": "..."}]
    messages JSONB DEFAULT '[]'::jsonb NOT NULL,

    -- 状態管理 (会話中か、知識化済みか)
    status session_status_enum DEFAULT 'active',

    -- メタデータ (Discord IDは桁溢れ防止でBIGINT)
    guild_id BIGINT,        -- Discord Guild ID（Discord URL生成に必要）
    channel_id BIGINT,
    thread_id BIGINT,
    user_id BIGINT,

    -- 楽観的ロック用（更新ごとにインクリメント）
    version INT DEFAULT 1,  -- ⚠️ 追加: 楽観的ロック用（更新ごとにインクリメント）
    
    -- アーカイブ管理
    last_archived_message_index INT DEFAULT 0,  -- ⚠️ 改善: アーカイブ済みメッセージのインデックス（0=未アーカイブ）

    -- 時間管理
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    last_active_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
```

#### sessions テーブルのカラム詳細

| カラム名 | データ型 | 制約 | 説明 |
|---------|---------|------|------|
| `id` | BIGSERIAL | PRIMARY KEY | セッションID（自動採番）。将来的な外部キー参照用 |
| `session_key` | TEXT | UNIQUE NOT NULL | セッションキー（一意）。形式: `"mention:{user_id}"`, `"thread:{thread_id}"`, `"eavesdrop:{channel_id}"`。アプリケーション内部での参照用 |
| `session_type` | TEXT | NOT NULL | セッションタイプ（`mention`, `thread`, `eavesdrop`） |
| `messages` | JSONB | NOT NULL, DEFAULT `'[]'::jsonb` | 会話履歴。JSON配列形式で保存 |
| `status` | session_status_enum | DEFAULT `'active'` | セッション状態。`'active'` または `'archived'` |
| `guild_id` | BIGINT | NULL | Discord Guild ID（Discord URL生成に必要。DMの場合はNULL） |
| `channel_id` | BIGINT | NULL | Discord チャンネル ID |
| `thread_id` | BIGINT | NULL | Discord スレッド ID（スレッド型の場合） |
| `user_id` | BIGINT | NULL | Discord ユーザー ID |
| `version` | INT | DEFAULT 1 | ⚠️ 追加: 楽観的ロック用（更新ごとにインクリメント）。TIMESTAMPTZの精度（マイクロ秒）で競合検出に依存していると、同一マイクロ秒内の更新で誤検知の可能性があるため、versionカラムを使用する方が堅牢 |
| `last_archived_message_index` | INT | DEFAULT 0 | ⚠️ 改善: アーカイブ済みメッセージのインデックス（0=未アーカイブ）。高頻度でチャットが続く場合でも、確定した過去部分だけをアーカイブでき、リトライループに陥ることを防ぐ |
| `created_at` | TIMESTAMPTZ | DEFAULT CURRENT_TIMESTAMP | セッション作成日時 |
| `last_active_at` | TIMESTAMPTZ | DEFAULT CURRENT_TIMESTAMP | 最後のアクティビティ日時 |

#### messages JSONB 構造

```json
[
  {
    "role": "user",
    "content": "こんにちは",
    "timestamp": "2026-01-19T10:00:00Z"
  },
  {
    "role": "assistant",
    "content": "こんにちは！何かお手伝いできることはありますか？",
    "timestamp": "2026-01-19T10:00:01Z"
  }
]
```

### 4.2 knowledge_sources テーブル

**目的**: 知識の「出処」を管理します。会話ログもファイルも、ここを経由して管理します。

#### knowledge_sources テーブルのDDL

```sql
CREATE TABLE IF NOT EXISTS knowledge_sources (
    id BIGSERIAL PRIMARY KEY,

    -- 情報の種類とタイトル
    type source_type_enum NOT NULL,
    title TEXT NOT NULL,             -- 検索結果に表示する見出し
    uri TEXT,                        -- 元データへのリンク (Discord URL, S3 Path)

    -- 処理状態
    status source_status_enum DEFAULT 'pending',
    error_code TEXT,  -- ⚠️ 改善（セキュリティ）: エラーコード（例: 'EMBEDDING_API_TIMEOUT', 'RATE_LIMIT'）
    error_message TEXT,  -- ⚠️ 改善（セキュリティ）: 一般化されたメッセージのみ（詳細なスタックトレースはログのみに出力）

    -- 柔軟なメタデータ (JSONB)
    -- Chat: { "channel_name": "dev-talk", "participants": [123, 456],
    -- "origin_session_id": 123, "origin_session_key": "thread:999" }
    -- File: { "file_size": 1024, "mime_type": "application/pdf" }
    -- ⚠️ 改善（疎結合）: origin_session_id は外部キーではなく metadata に記録
    -- 理由: 「短期記憶（Sessions）」と「長期記憶（Knowledge）」はライフサイクルが異なるため、
    -- 外部キー制約による強い依存関係を避け、知識として独立した存在として扱う
    -- これにより、「削除時の挙動」を設計する必要がなくなり、シンプルな設計になる
    -- セッションからアーカイブされたソースの場合、metadata に origin_session_id と origin_session_key を記録
    metadata JSONB DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
```

#### knowledge_sources テーブルのカラム詳細

| カラム名 | データ型 | 制約 | 説明 |
|---------|---------|------|------|
| `id` | BIGSERIAL | PRIMARY KEY | 知識ソースID（自動採番） |
| `type` | source_type_enum | NOT NULL | ソースタイプ（`discord_session`, `document_file`, `web_page`, `image_caption`, `audio_transcript`） |
| `title` | TEXT | NOT NULL | 検索結果に表示する見出し |
| `uri` | TEXT | NULL | 元データへのリンク（Discord URL、S3 Path、Web URLなど） |
| `status` | source_status_enum | DEFAULT `'pending'` | 処理状態（`pending`, `processing`, `completed`, `partial`, `failed`）。`partial`は一部のチャンクがDLQに移動した場合 |
| `error_code` | TEXT | NULL | ⚠️ 改善（セキュリティ）: エラーコード（例: 'EMBEDDING_API_TIMEOUT', 'RATE_LIMIT'）。詳細なスタックトレースはログのみに出力し、データベースには保存しない |
| `error_message` | TEXT | NULL | ⚠️ 改善（セキュリティ）: 一般化されたエラーメッセージのみ（`status='failed'` の場合）。APIエラーやスタックトレースが含まれる可能性があるため、一般化されたメッセージのみを保存 |
| `metadata` | JSONB | DEFAULT `'{}'::jsonb` | 柔軟なメタデータ（ソースタイプごとに異なる属性を格納）。セッションからアーカイブされたソースの場合、`origin_session_id` と `origin_session_key` を含む。⚠️ 改善（疎結合）: 外部キー制約ではなく metadata に記録することで、ライフサイクルの完全分離を実現 |
| `created_at` | TIMESTAMPTZ | DEFAULT CURRENT_TIMESTAMP | 作成日時 |
| `updated_at` | TIMESTAMPTZ | DEFAULT CURRENT_TIMESTAMP | 更新日時 |

#### metadata JSONB 構造例

**Discord Session**:

```json
{
  "channel_name": "dev-talk",
  "participants": [123456789, 987654321],
  "message_count": 42
}
```

**Document File**:

```json
{
  "file_size": 1024000,
  "mime_type": "application/pdf",
  "page_count": 10,
  "uploaded_by": 123456789
}
```

**Web Page**:

```json
{
  "url": "https://example.com/article",
  "scraped_at": "2026-01-19T10:00:00Z",
  "content_length": 5000
}
```

### 4.3 knowledge_chunks テーブル

**目的**: 検索対象の「実体」です。テキストとベクトルが入ります。

#### knowledge_chunks テーブルのDDL

```sql
CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id BIGSERIAL PRIMARY KEY,

    -- 親テーブルへの参照 (親が消えたら道連れで消える)
    source_id BIGINT REFERENCES knowledge_sources(id) ON DELETE CASCADE,

    -- 検索対象のテキスト (会話の要約、PDFの本文など)
    content TEXT NOT NULL,

    -- ベクトルデータ (OpenAI text-embedding-3-small 用 1536次元)
    -- ⚠️ 重要: halfvec(1536) を固定採用（メモリ使用量50%削減、pgvector 0.7.0以降）
    -- Synology NASのリソース節約のため、halfvecを固定採用します
    -- ⚠️ 重要: NULL許容です。Embedding生成前のデータをINSERTし、後でUPDATEするフローを採用
    -- 理由: トランザクション分離のため（FOR UPDATE SKIP LOCKED + Tx分離パターン）
    -- 検索時は必ず embedding IS NOT NULL 条件を含めること（HNSWインデックス使用のため）
    embedding halfvec(1536),

    -- 元データ内での位置情報 (引用元提示用)
    -- Chat: { "message_id": 9999 }
    -- PDF:  { "page": 3 }
    location JSONB DEFAULT '{}'::jsonb,

    token_count INT,

    -- Dead Letter Queue対応（リトライ管理）
    retry_count INT DEFAULT 0,  -- Embedding処理失敗時のリトライ回数

    -- タイムスタンプ（チャンクの作成順序でのフィルタリング用）
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
```

#### knowledge_chunks テーブルのカラム詳細

| カラム名 | データ型 | 制約 | 説明 |
|---------|---------|------|------|
| `id` | BIGSERIAL | PRIMARY KEY | チャンクID（自動採番） |
| `source_id` | BIGINT | FOREIGN KEY, NOT NULL | 親ソースへの参照（`knowledge_sources.id`） |
| `content` | TEXT | NOT NULL | 検索対象のテキスト（会話の要約、PDFの本文など） |
| `embedding` | halfvec(1536) | NULL | ベクトルデータ（1536次元、halfvec固定採用）。NULLの場合は未処理 |
| `location` | JSONB | DEFAULT `'{}'::jsonb` | 元データ内での位置情報（引用元提示用） |
| `token_count` | INT | NULL | トークン数（Embedding APIの使用量計算用） |
| `retry_count` | INT | DEFAULT 0 | Embedding処理失敗時のリトライ回数（Dead Letter Queue対応） |
| `created_at` | TIMESTAMPTZ | DEFAULT CURRENT_TIMESTAMP | 作成日時 |

#### location JSONB 構造

⚠️ **重要**: `location` フィールドは柔軟なJSONBですが、検索結果を表示する際にBotが「どこへのリンクを生成すべきか」を判断するために、**共通のインターフェース**を定義します。

**共通インターフェース（必須フィールド）**:

- `url` (string, 推奨): チャンクへの直接リンク（DiscordメッセージURL、PDFページURLなど）
- `label` (string, 推奨): ユーザーに表示するラベル（例: "メッセージ #5", "ページ 3"）

**ソースタイプ別の構造例**:

**Discord Session**:

```json
{
  "url": "https://discord.com/channels/123456789/987654321/999999999999999999",
  "label": "メッセージ #5",
  "message_id": 999999999999999999,
  "message_index": 5,
  "channel_id": 987654321
}
```

**Document File**:

```json
{
  "url": "https://example.com/document.pdf#page=3",
  "label": "ページ 3",
  "page": 3,
  "paragraph": 2,
  "char_start": 100,
  "char_end": 500
}
```

**Web Page**:

```json
{
  "url": "https://example.com/article#section=main-content",
  "label": "セクション: main-content",
  "section": "main-content",
  "paragraph_index": 1
}
```

**実装時の注意**:

- `url` と `label` フィールドは、検索結果の表示ロジック（Discord表示）で使用されます
- ソースタイプごとに追加のメタデータ（`message_id`, `page`, `section` など）を含めることができます
- `url` が提供されない場合、`knowledge_sources.uri` をフォールバックとして使用できます

### 4.4 knowledge_chunks_dlq テーブル（Dead Letter Queue）

**目的**: Embedding処理が最大リトライ回数を超えて失敗したチャンクを管理します。手動での確認・再処理を可能にします。

#### knowledge_chunks_dlq テーブルのDDL

```sql
CREATE TABLE IF NOT EXISTS knowledge_chunks_dlq (
    id BIGSERIAL PRIMARY KEY,
    
    -- 元のチャンクID（参照用、元チャンクが削除されても保持）
    original_chunk_id BIGINT,
    
    -- ⚠️ 改善（データ整合性）: 元のソース情報を追加して追跡性を向上
    source_id BIGINT,           -- 元のソースID（外部キー制約なし、ソース削除後も追跡可能）
    source_title TEXT,           -- デバッグ用にソースのタイトルも保存
    
    -- 処理対象のコンテンツ
    content TEXT NOT NULL,
    
    -- エラー情報
    error_code TEXT,  -- ⚠️ 改善: エラーコードを分離して保存
                      -- （例: 'EMBEDDING_API_TIMEOUT', 'RATE_LIMIT'）
    error_message TEXT,         -- 一般化されたエラーメッセージ
    retry_count INT DEFAULT 0,
    
    -- タイムスタンプ
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    last_retry_at TIMESTAMPTZ
);
```

#### knowledge_chunks_dlq テーブルのカラム詳細

| カラム名 | データ型 | 制約 | 説明 |
|---------|---------|------|------|
| `id` | BIGSERIAL | PRIMARY KEY | DLQエントリID（自動採番） |
| `original_chunk_id` | BIGINT | NULL | 元のチャンクID（参照用） |
| `content` | TEXT | NOT NULL | 処理対象のコンテンツ |
| `error_message` | TEXT | NULL | エラーメッセージ |
| `retry_count` | INT | DEFAULT 0 | リトライ回数 |
| `created_at` | TIMESTAMPTZ | DEFAULT CURRENT_TIMESTAMP | 作成日時 |
| `last_retry_at` | TIMESTAMPTZ | NULL | 最終リトライ日時 |

**DLQ戦略**:

- **最大リトライ回数**: 環境変数 `KB_EMBEDDING_MAX_RETRY` で制御（推奨: 3回）
- **リトライ間隔**: Exponential Backoff（推奨: 1回目: 1分、2回目: 5分、3回目: 15分）
- **失敗時の通知**: DLQ投入時にアラート送信（オプション）

---

## 5. インデックス設計

### 5.1 sessions テーブルのインデックス

```sql
-- session_key での検索用（アプリケーション内部での参照用）
CREATE INDEX idx_sessions_session_key ON sessions(session_key);

-- ステータスでの検索用（アーカイブ対象のセッション検索）
CREATE INDEX idx_sessions_status ON sessions(status);

-- 最終アクティビティ日時での検索用（タイムアウト判定）
CREATE INDEX idx_sessions_last_active_at ON sessions(last_active_at);

-- チャンネルIDでの検索用
CREATE INDEX idx_sessions_channel_id ON sessions(channel_id);

-- アーカイブ対象セッション検索用の複合インデックス（パフォーマンス向上）
CREATE INDEX idx_sessions_archive_candidates ON sessions(status, last_active_at)
WHERE status = 'active';
```

**使用例**:

- `status='active'` かつ `last_active_at < 1時間前` のセッションを検索（アーカイブ処理）
- 特定チャンネルのセッション一覧取得

### 5.2 knowledge_sources テーブルのインデックス

```sql
-- JSONメタデータ内の検索用 (GINインデックス)
CREATE INDEX idx_sources_metadata ON knowledge_sources USING gin (metadata);

-- ステータスでの検索用（処理待ちのソース検索）
CREATE INDEX idx_sources_status ON knowledge_sources(status);

-- タイプでの検索用
CREATE INDEX idx_sources_type ON knowledge_sources(type);
```

**使用例**:

- `status='pending'` のソースを検索（バックグラウンド処理）
- `metadata->>'channel_name' = 'dev-talk'` での検索

### 5.3 knowledge_chunks テーブルのインデックス

```sql
-- ベクトル検索用インデックス (HNSW法)
-- 類似度計算には cosine distance (<=>) を使用
-- パラメータ: m=16 (各ノードの接続数), ef_construction=64 (構築時の探索深さ)
-- NASのメモリリソースを考慮しつつ、精度を確保する設定
-- 注意: 環境変数 KB_HNSW_M と KB_HNSW_EF_CONSTRUCTION で制御可能
-- ⚠️ 重要: halfvec固定採用のため、halfvec_cosine_ops を使用
CREATE INDEX idx_chunks_embedding ON knowledge_chunks 
USING hnsw (embedding halfvec_cosine_ops)
WITH (m = 16, ef_construction = 64);  -- 環境変数から読み込むことを推奨

-- Source IDでの検索用
CREATE INDEX idx_chunks_source_id ON knowledge_chunks(source_id);

-- embedding IS NOT NULL での検索用（検索可能なチャンクのみ取得）
-- ⚠️ 重要: この部分インデックスは必須です
-- 改善: embedding カラム自体を含め、created_at も含めることでソート性能を向上
CREATE INDEX idx_chunks_searchable ON knowledge_chunks(source_id, created_at)
WHERE embedding IS NOT NULL AND token_count > 0;

-- ⚠️ 改善（パフォーマンス）: 処理待ち行列専用の部分インデックス
-- FOR UPDATE SKIP LOCKED を使うクエリは WHERE embedding IS NULL を参照します。
-- knowledge_chunks が数百万件になった際、embedding IS NULL の行を探すのに
-- 時間がかかるとバッチ処理が遅延します。
-- 処理待ち行列専用の部分インデックスを作成することで、ワーカーはテーブル全体を
-- スキャンせず、インデックスのみを見て処理対象を即座に見つけられます。
-- リトライ上限未満（retry_count < 3）のみを含めることで、諦められたチャンクを除外
CREATE INDEX idx_chunks_queue ON knowledge_chunks(id)
WHERE embedding IS NULL AND retry_count < 3;

-- ハイブリッド検索用インデックス（オプション、将来の拡張用）
-- pg_bigm 拡張を有効化した後に実行
-- 部分一致検索や類似文字列検索に使用（固有名詞の検索に有効）
-- CREATE EXTENSION IF NOT EXISTS pg_bigm;
-- CREATE INDEX idx_chunks_content_bigm ON knowledge_chunks
-- USING gin (content gin_bigm_ops);
```

**⚠️ 重要: `embedding IS NOT NULL` 条件の必須性**:

- **理由**: HNSWインデックス（`idx_chunks_embedding`）は `embedding` が NULL でない場合にのみ有効です
- **リスク**: 検索クエリで `embedding IS NOT NULL` 条件を忘れると、HNSWインデックスが使われずフルスキャンになるリスクがあります。実装漏れが発生すると、意図せずフルスキャンが発生し、本番環境で突然死（タイムアウト）する原因になります。
- **改善案（Strong Recommendation）**:
  - クエリビルダーやラッパー関数（`similarity_search`）側で、強制的にこの条件が付与される仕組みをコードレベルで保証してください
  - アプリケーション実装者の注意深さに依存した設計ではなく、コードレベルで保証することで、実装漏れを防ぎます
  - すべてのベクトル検索クエリで必ず `WHERE embedding IS NOT NULL` を含める必要があります
- **実装時の注意**: クエリ構築時にこの条件を忘れないよう、コメントや定数化を推奨しますが、それだけでは不十分です。コードレベルで強制付与する仕組みを実装してください

**HNSWインデックスパラメータ説明**:

- **m**: 各ノードの接続数。値が大きいほど精度が上がるが、インデックスサイズと構築時間が増加（デフォルト: 16）
- **ef_construction**: 構築時の探索深さ。値が大きいほど精度が上がるが、構築時間が増加（デフォルト: 64）

**⚠️ 運用上の注意: HNSWインデックスのメモリ消費**:

- **現状**: `m=16`, `ef_construction=64` は初期運用には適切な設定です
- **メモリ消費の特性**:
  - `halfvec` で容量は減りますが、HNSWは高速化のためにグラフ構造をメモリに乗せようとします
  - データ量が増えると、インデックスのメモリ使用量が増加します
- **監視とチューニング**:
  - **初期は問題ありませんが、データが10万件を超えたあたりで監視が必要です**
  - `pg_stat_activity` やコンテナのメモリ使用量を監視してください
  - PostgreSQLの設定（`postgresql.conf`）チューニングが必要になる可能性があります
  - 特に以下のパラメータの調整を検討してください:
    - `maintenance_work_mem`: インデックス構築時のメモリ使用量（デフォルト: 64MB）
      - ⚠️ **重要**: インデックス構築時（INSERT/UPDATE時）とリストア時にOOM Killerが発動する可能性があります
      - NASのメモリが少ない場合、大量のデータを COPY や INSERT した直後のインデックス構築でOOM Killerが発動し、Postgresプロセスが落ちる可能性があります
      - **推奨設定**: システムメモリの10〜20%程度（最小128MB、最大1GB）
      - 例: NASのメモリが4GBなら、256MB〜512MB程度に抑える
      - **設定方法**:
        - docker-compose.yml: `POSTGRES_INITDB_ARGS: --maintenance-work-mem=256MB`（初期化時のみ）
        - postgresql.conf: `maintenance_work_mem = 256MB`（実行時も有効、推奨）
        - または: `ALTER SYSTEM SET maintenance_work_mem = '256MB';` + `SELECT pg_reload_conf();`
    - `work_mem`: クエリ実行時のメモリ使用量（デフォルト: 4MB）
    - `shared_buffers`: 共有バッファプールのサイズ（デフォルト: 128MB）
- **推奨監視項目**:
  - コンテナのメモリ使用量（`docker stats`）
  - PostgreSQLのメモリ使用量（`pg_stat_activity`）
  - インデックスサイズ（`pg_size_pretty(pg_relation_size('idx_chunks_embedding'))`）
  - クエリ実行時間（`EXPLAIN ANALYZE`）

**⚠️ 重要: HNSWのビルドコストと maintenance_work_mem**:

- **リスク**: 設計書には「データが増えるとメモリを食う」とありますが、具体的な危険性は**「インデックス構築時（INSERT/UPDATE時）」と「リストア時」**にあります
- **問題**: NASのメモリが少ない場合、大量のデータを COPY や INSERT した直後のインデックス構築でOOM Killerが発動し、Postgresプロセスが落ちる可能性があります
- **対策**: docker-compose.yml または postgresql.conf で `maintenance_work_mem` を制限してください
  - 例: NASのメモリが4GBなら、256MB〜512MB程度に抑える
  - デフォルトのままだと危険な場合があります
- **設定方法**:
  - **docker-compose.yml**: 環境変数 `POSTGRES_INITDB_ARGS` を使用
  - **postgresql.conf**: `maintenance_work_mem = 256MB` を設定
  - **推奨値**: システムメモリの10〜20%程度（最小128MB、最大1GB）

**使用例**:

- ベクトル類似度検索（`embedding <=> $1`）
- 特定ソースのチャンク一覧取得
- 検索可能なチャンクのみ取得（`embedding IS NOT NULL`）
- ハイブリッド検索（ベクトル検索 + pg_bigm キーワード検索）

---

## 6. 制約とリレーション

### 6.1 外部キー制約

```sql
-- knowledge_chunks.source_id -> knowledge_sources.id
-- 親ソースが削除された場合、子チャンクも自動的に削除される（CASCADE）
ALTER TABLE knowledge_chunks 
ADD CONSTRAINT fk_chunks_source 
FOREIGN KEY (source_id) 
REFERENCES knowledge_sources(id) 
ON DELETE CASCADE;
```

### 6.2 チェック制約

```sql
-- sessions.status は 'active' または 'archived' のみ許可
-- 注意: ENUM型を使用しているため、このCHECK制約は冗長ですが、明示性のために残しています
ALTER TABLE sessions 
ADD CONSTRAINT chk_sessions_status 
CHECK (status IN ('active', 'archived'));

-- knowledge_sources.status は 'pending', 'processing', 'completed',
-- 'partial', 'failed' を許可
-- 注意: ENUM型を使用しているため、このCHECK制約は冗長ですが、明示性のために残しています
ALTER TABLE knowledge_sources 
ADD CONSTRAINT chk_sources_status 
CHECK (status IN ('pending', 'processing', 'completed', 'partial', 'failed'));
```

### 6.3 一意制約

```sql
-- sessions.session_key は一意（UNIQUE制約により保証）
-- sessions.id は主キー（BIGSERIAL、自動採番）
-- アプリケーション内部での参照は session_key を使いつつ、
-- 将来的なリレーション（例：session_tags テーブルなど）は id を使う余地を残す
```

---

## 7. データ型の説明

### 7.1 JSONB

**使用箇所**: `sessions.messages`, `knowledge_sources.metadata`, `knowledge_chunks.location`

**メリット**:

- 柔軟なスキーマ（ソースタイプごとに異なる属性を格納可能）
- 高速な検索（GINインデックス対応）
- 部分更新が可能

**使用例**:

```sql
-- メタデータ内の検索
SELECT * FROM knowledge_sources 
WHERE metadata->>'channel_name' = 'dev-talk';

-- メタデータの更新
UPDATE knowledge_sources 
SET metadata = jsonb_set(metadata, '{participants}', '[123, 456]'::jsonb)
WHERE id = 1;
```

### 7.2 vector / halfvec

**使用箇所**: `knowledge_chunks.embedding`

**説明**:

- **halfvec(1536)**: 1536次元のベクトル型（float16、4バイト/次元、pgvector 0.7.0以降）を固定採用

**メモリ使用量**:

- `halfvec(1536)`: 約 6KB/レコード（1536 × 4バイト）
- 比較: `vector(1536)` は約 12KB/レコード（1536 × 8バイト）のため、halfvecでメモリ使用量が50%削減

**採用理由**: Synology NASのリソース節約のため、`halfvec` を固定採用（精度への影響は最小限）

**重要**: クエリ時の型キャストは `halfvec` を使用します：

```sql
-- halfvec固定採用
SELECT * FROM knowledge_chunks
WHERE embedding <=> $1::halfvec(1536) < 0.3;
```

### 7.3 TIMESTAMPTZ

**使用箇所**: すべての `*_at` カラム

**説明**: タイムゾーン情報を含むタイムスタンプ型。UTCで保存し、アプリケーション側でタイムゾーン変換を行う。

---

## 8. 使用例とクエリ

### 8.1 セッション管理

#### セッションの作成

```sql
-- ⚠️ 注意: id は自動採番されるため、INSERT文には含めない
-- アプリケーション内部での参照は session_key を使用
INSERT INTO sessions (session_key, session_type, channel_id, user_id)
VALUES ('mention:123456789', 'mention', 987654321, 123456789)
ON CONFLICT (session_key) DO NOTHING;
```

#### メッセージの追加

```sql
UPDATE sessions
SET 
    messages = messages || '{"role": "user", "content": "こんにちは"}'::jsonb,
    last_active_at = CURRENT_TIMESTAMP
WHERE session_key = 'mention:123456789';
```

#### セッションの取得

```sql
SELECT * FROM sessions WHERE session_key = 'mention:123456789';
```

#### 非アクティブセッションの検索（アーカイブ対象）

```sql
-- ⚠️ 注意: アプリケーション内部での参照は session_key を使用
-- id は将来的な外部キー参照用に残しておく
SELECT * FROM sessions
WHERE status = 'active'
  AND last_active_at < CURRENT_TIMESTAMP - INTERVAL '1 hour';
```

### 8.2 知識ベース管理

#### ソースの登録

```sql
INSERT INTO knowledge_sources (type, title, uri, metadata, status)
VALUES (
    'discord_session',
    '会話ログ: dev-talk チャンネル',
    'https://discord.com/channels/123/456',
    '{"channel_name": "dev-talk", "participants": [123, 456]}'::jsonb,
    'pending'
)
RETURNING id;
```

#### チャンクの登録（Embedding未処理）

```sql
INSERT INTO knowledge_chunks (source_id, content, location, token_count)
VALUES (
    1,
    '会話の要約テキスト...',
    '{"message_id": 999999999999999999}'::jsonb,
    150
);
```

#### Embeddingの更新

```sql
UPDATE knowledge_chunks
SET embedding = $1::halfvec(1536)
WHERE id = 1;
```

#### ソースのステータス更新

```sql
UPDATE knowledge_sources
SET 
    status = 'completed',
    updated_at = CURRENT_TIMESTAMP
WHERE id = 1;
```

### 8.3 ベクトル検索

#### 基本的な類似度検索

```sql
-- ⚠️ 重要: WHERE c.embedding IS NOT NULL 条件は必須です
-- この条件がないと、HNSWインデックス（idx_chunks_embedding）が使われずフルスキャンになります
SELECT 
    s.type,
    s.title,
    s.uri,
    c.content,
    c.location,
    1 - (c.embedding <=> $1::halfvec(1536)) AS similarity
FROM knowledge_chunks c
JOIN knowledge_sources s ON c.source_id = s.id
WHERE c.embedding IS NOT NULL  -- ⚠️ 必須: HNSWインデックス使用のため
  AND s.status = 'completed'
ORDER BY c.embedding <=> $1::halfvec(1536)
LIMIT 10;
```

#### 類似度閾値を指定した検索

```sql
-- ⚠️ 重要: WHERE c.embedding IS NOT NULL 条件は必須です
SELECT 
    s.type,
    s.title,
    c.content,
    1 - (c.embedding <=> $1::halfvec(1536)) AS similarity
FROM knowledge_chunks c
JOIN knowledge_sources s ON c.source_id = s.id
WHERE c.embedding IS NOT NULL  -- ⚠️ 必須: HNSWインデックス使用のため
  AND s.status = 'completed'
  AND 1 - (c.embedding <=> $1::halfvec(1536)) > 0.7  -- 類似度閾値
ORDER BY similarity DESC
LIMIT 5;
```

#### チャンネルフィルタ付き検索

```sql
-- ⚠️ 重要: WHERE c.embedding IS NOT NULL 条件は必須です
SELECT 
    s.type,
    s.title,
    c.content,
    1 - (c.embedding <=> $1::halfvec(1536)) AS similarity
FROM knowledge_chunks c
JOIN knowledge_sources s ON c.source_id = s.id
WHERE c.embedding IS NOT NULL  -- ⚠️ 必須: HNSWインデックス使用のため
  AND s.status = 'completed'
  AND s.metadata->>'channel_id' = '987654321'::text
ORDER BY c.embedding <=> $1::halfvec(1536)
LIMIT 10;
```

#### ソースタイプフィルタ付き検索（単一指定）

```sql
-- ⚠️ 重要: WHERE c.embedding IS NOT NULL 条件は必須です
SELECT 
    s.type,
    s.title,
    c.content,
    1 - (c.embedding <=> $1::halfvec(1536)) AS similarity
FROM knowledge_chunks c
JOIN knowledge_sources s ON c.source_id = s.id
WHERE c.embedding IS NOT NULL  -- ⚠️ 必須: HNSWインデックス使用のため
  AND s.status = 'completed'
  AND s.type = 'discord_session'
ORDER BY c.embedding <=> $1::halfvec(1536)
LIMIT 10;
```

#### ソースタイプフィルタ付き検索（複数指定）

```sql
-- ⚠️ 重要: WHERE c.embedding IS NOT NULL 条件は必須です
-- 複数のソースタイプ（例：「WebとPDFから検索したい」）を同時に指定する場合
SELECT 
    s.type,
    s.title,
    c.content,
    1 - (c.embedding <=> $1::halfvec(1536)) AS similarity
FROM knowledge_chunks c
JOIN knowledge_sources s ON c.source_id = s.id
WHERE c.embedding IS NOT NULL  -- ⚠️ 必須: HNSWインデックス使用のため
  AND s.status = 'completed'
  AND s.type = ANY($2::source_type_enum[])  -- ⚠️ 複数指定: IN句またはANY句を使用
ORDER BY c.embedding <=> $1::halfvec(1536)
LIMIT 10;
```

**使用例**: `$2 = ['web_page', 'document_file']` を指定すると、WebページとPDFファイルの両方から検索します。

#### Python API での使用例

```python
from kotonoha_bot.db.postgres import PostgreSQLDatabase

# データベースの初期化
db = PostgreSQLDatabase(connection_string=settings.database_url)
await db.initialize()

# 基本的な類似度検索（閾値フィルタリングあり）
query_embedding = [0.1] * 1536  # 1536次元のベクトル
results = await db.similarity_search(
    query_embedding=query_embedding,
    top_k=10
)

# カスタム閾値を指定
results = await db.similarity_search(
    query_embedding=query_embedding,
    top_k=10,
    similarity_threshold=0.8  # より厳しい閾値
)

# 閾値フィルタリングを無効化（生の類似度スコアを取得）
results_raw = await db.similarity_search(
    query_embedding=query_embedding,
    top_k=10,
    apply_threshold=False  # 閾値フィルタリングを無効化
)

# フィルタ付き検索
results = await db.similarity_search(
    query_embedding=query_embedding,
    top_k=10,
    filters={
        "source_type": "discord_session",
        "channel_id": 123456789
    }
)

# 複数のソースタイプを指定
results = await db.similarity_search(
    query_embedding=query_embedding,
    top_k=10,
    filters={
        "source_types": ["discord_session", "document_file"]
    }
)
```

**パラメータ説明**:

- `query_embedding` (list[float]): クエリのベクトル（1536次元）
- `top_k` (int): 取得する結果の数（デフォルト: 10）
- `filters` (dict | None): フィルタ条件
  - `source_type`: 単一のソースタイプを指定
  - `source_types`: 複数のソースタイプを指定（リスト）
  - `channel_id`: チャンネルIDでフィルタ
  - `user_id`: ユーザーIDでフィルタ
- `similarity_threshold` (float | None): 類似度閾値。`None`の場合は設定値（デフォルト0.7）を使用
- `apply_threshold` (bool): 閾値フィルタリングを適用するか。`False`の場合は閾値フィルタリングを無効化し、生の類似度スコアを返す（デフォルト: `True`）

### 8.4 バッチ処理用クエリ

#### 処理待ちのソース検索

```sql
SELECT * FROM knowledge_sources
WHERE status = 'pending'
ORDER BY created_at ASC
LIMIT 100;
```

#### Embedding未処理のチャンク検索（並行処理安全版）

**重要**: 複数のワーカープロセスが同時に実行される場合、`FOR UPDATE SKIP LOCKED` を使用してDBレベルで排他制御を行います。これにより、アプリケーションレベルのロック（`asyncio.Lock`）に依存せず、安全にバッチ処理が可能になります。

```sql
-- 取得と同時にロックする（他のワーカーはこの行をスキップする）
SELECT id, source_id, content, token_count
FROM knowledge_chunks
WHERE embedding IS NULL
ORDER BY id ASC
LIMIT 100
FOR UPDATE SKIP LOCKED;
```

**メリット**:

- **DBレベルでの排他制御**: アプリケーションレベルのロック不要
- **スケールアウト対応**: 複数のBotプロセスやワーカーが同時実行可能
- **再起動時の安全性**: Bot再起動や誤った2重起動時も競合が発生しない
- **パフォーマンス**: ロックされた行は自動的にスキップされ、待機しない

**注意**: `FOR UPDATE SKIP LOCKED` はトランザクション内で実行する必要があります。

#### Embedding未処理のチャンク検索（単一プロセス版）

単一プロセスでのみ実行される場合は、以下のシンプルなクエリでも問題ありません：

```sql
SELECT * FROM knowledge_chunks
WHERE embedding IS NULL
ORDER BY created_at ASC
LIMIT 100;
```

#### 処理中のソース検索（タイムアウト判定）

```sql
SELECT * FROM knowledge_sources
WHERE status = 'processing'
  AND updated_at < CURRENT_TIMESTAMP - INTERVAL '30 minutes';
```

---

## 9. パフォーマンス考慮事項

### 9.1 インデックス戦略

1. **HNSWインデックス**: ベクトル検索の高速化（`idx_chunks_embedding`）
2. **GINインデックス**:
   - JSONBメタデータの高速検索（`idx_sources_metadata`）
   - ハイブリッド検索用のpg_bigmインデックス（`idx_chunks_content_bigm`、推奨）
3. **B-treeインデックス**: 通常のカラム検索（`status`, `type`, `source_id`など）

### 9.2 クエリ最適化

1. **LIMIT句の使用**: 大量データ取得時は必ずLIMITを指定
2. **部分インデックス**: `embedding IS NOT NULL` 条件での検索を高速化
3. **JOIN最適化**: `knowledge_chunks` と `knowledge_sources` のJOINは外部キーインデックスで高速化

### 9.3 接続プール設定

**推奨設定**（環境変数）:

- `DB_POOL_MIN_SIZE`: 5（最小接続数）
- `DB_POOL_MAX_SIZE`: 20（最大接続数）
- `DB_COMMAND_TIMEOUT`: 60（コマンドタイムアウト秒）

### 9.4 メモリ使用量の最適化

1. **halfvecの使用**: `vector(1536)` の代わりに `halfvec(1536)` を使用（メモリ使用量50%削減）
2. **HNSWパラメータ調整**: `m` と `ef_construction` を環境に応じて調整
3. **定期的なVACUUM**: 不要なデータ削除後のVACUUM実行

### 9.5 並行性制御とロック戦略

#### FOR UPDATE SKIP LOCKED パターン

複数のワーカープロセスが同時に実行される場合、DBレベルでの排他制御が必須です。`FOR UPDATE SKIP LOCKED` を使用することで、アプリケーションレベルのロック（`asyncio.Lock`）に依存せず、安全にバッチ処理が可能になります。

**問題点（アプリケーションレベルのロック）**:

- 単一のBotプロセスでしか機能しない
- Bot再起動や誤った2重起動時に競合が発生
- スケールアウト時に同じチャンクを同時処理してしまう

**解決策（DBレベルのロック）**:

```sql
-- トランザクション内で実行
BEGIN;

-- 取得と同時にロック（他のワーカーはこの行をスキップ）
SELECT id, source_id, content, token_count
FROM knowledge_chunks
WHERE embedding IS NULL
ORDER BY id ASC
LIMIT 100
FOR UPDATE SKIP LOCKED;

-- Embedding処理後、更新
UPDATE knowledge_chunks
SET embedding = $1::halfvec(1536),
    token_count = $2
WHERE id = $3;

COMMIT;
```

**メリット**:

- **DBレベルでの排他制御**: アプリケーションレベルのロック不要
- **スケールアウト対応**: 複数のBotプロセスやワーカーが同時実行可能
- **再起動時の安全性**: Bot再起動や誤った2重起動時も競合が発生しない
- **パフォーマンス**: ロックされた行は自動的にスキップされ、待機しない

**実装例（Python/asyncpg）**:

```python
async def process_embedding_batch(conn: asyncpg.Connection, batch_size: int = 100):
    """並行処理安全なEmbeddingバッチ処理"""
    async with conn.transaction():
        # FOR UPDATE SKIP LOCKED で取得
        rows = await conn.fetch("""
            SELECT id, source_id, content, token_count
            FROM knowledge_chunks
            WHERE embedding IS NULL
            ORDER BY id ASC
            LIMIT $1
            FOR UPDATE SKIP LOCKED
        """, batch_size)
        
        for row in rows:
            # Embedding処理
            embedding = await generate_embedding(row['content'])
            
            # 更新
            await conn.execute("""
                UPDATE knowledge_chunks
                SET embedding = $1::halfvec(1536),
                    token_count = $2
                WHERE id = $3
            """, embedding, row['token_count'], row['id'])
```

---

## 10. 将来の拡張性

### 10.1 ソースタイプの追加

新しいソースタイプを追加する場合：

```sql
ALTER TYPE source_type_enum ADD VALUE 'video_transcript';
ALTER TYPE source_type_enum ADD VALUE 'code_repository';
```

**注意**: ENUM値の追加は可能ですが、削除は困難です。慎重に設計してください。

### 10.2 テーブルの追加

将来的に以下のテーブル追加を検討：

- **`knowledge_tags`**: タグ管理（マルチタグ対応）
- **`knowledge_relations`**: ソース間の関連性管理
- **`user_preferences`**: ユーザーごとの検索設定

### 10.3 パーティショニング

大規模データに対応するため、時系列パーティショニングを検討：

```sql
-- 月ごとのパーティショニング例
CREATE TABLE knowledge_chunks_2026_01 PARTITION OF knowledge_chunks
FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
```

### 10.4 ハイブリッド検索（Hybrid Search）の導入

**背景**: ベクトル検索は「概念的な類似」には強いですが、「固有名詞（例：プロジェクトコード名、特定のエラーコード）」の完全一致検索には弱いです。PostgreSQLの強みを生かし、全文検索を組み合わせたハイブリッド検索を設計段階で考慮することを推奨します。

⚠️ **重要**: 日本語検索においては、**pg_bigm** を強く推奨します。

#### 推奨: pg_bigm 拡張を使用（日本語検索に最適）

**pg_bigm の利点**:

- **2-gram（2文字単位）**: 日本語の多くは2文字以上の熟語で構成されるため、検索漏れがほぼゼロ
- **2文字の単語に対応**: 「設計」「開発」のような2文字の単語も確実に検索可能
- **LIKE演算子の高速化**: PostgreSQL標準の `LIKE '%...%'` 検索を爆速化
- **pg_trgm との違い**: pg_trgm（3-gram）は2文字の単語が検索漏れしたり、精度が出にくい場合がある

**pg_trgm の限界**:

- 3文字単位のため、「設計」「開発」のような2文字の単語の検索が苦手
- ひらがなの助詞などがノイズになりやすい

**Dockerfile での pg_bigm の導入**:

pg_bigm は標準の PostgreSQL イメージには含まれていないため、pgvector のイメージをベースにして、pg_bigm をコンパイルして追加したカスタムイメージを作成する必要があります。

```dockerfile
# Dockerfile.postgres

# pgvector の公式イメージ（PostgreSQL 18）をベースに使用
FROM pgvector/pgvector:0.8.1-pg18

# pg_bigm のバージョン
# ⚠️ 注意: GitHubリリースへの依存があり、削除リスクがあります
# 推奨: ソースを自プロジェクトに含めるか、チェックサム検証を追加
ARG PG_BIGM_VERSION=1.2-20240606
ARG PG_BIGM_CHECKSUM=""  # オプション: チェックサム検証用

USER root

# ビルド依存関係のインストール
RUN apt-get update && apt-get install -y \
    build-essential \
    postgresql-server-dev-18 \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# pg_bigm のダウンロードとインストール
# ⚠️ ビルドキャッシュ最適化: マルチステージビルドとレイヤーキャッシュを活用
# Stage 1: ビルド環境
FROM pgvector/pgvector:0.8.1-pg18 AS builder

ARG PG_BIGM_VERSION=1.2-20240606
ARG PG_BIGM_CHECKSUM=""

USER root

# ビルド依存関係のインストール（レイヤーキャッシュのため、依存関係の変更が少ない順に配置）
RUN apt-get update && apt-get install -y \
    build-essential \
    postgresql-server-dev-18 \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# pg_bigm のダウンロード（ダウンロードとビルドを分離して
# レイヤーキャッシュを活用）
RUN wget -O pg_bigm.tar.gz \
    https://github.com/pgbigm/pg_bigm/archive/refs/tags/\
v${PG_BIGM_VERSION}.tar.gz \
    && if [ -n "$PG_BIGM_CHECKSUM" ]; then \
        echo "$PG_BIGM_CHECKSUM  pg_bigm.tar.gz" | sha256sum -c - || exit 1; \
    fi \
    && mkdir -p /usr/src/pg_bigm \
    && tar -xzf pg_bigm.tar.gz -C /usr/src/pg_bigm --strip-components=1

# pg_bigm のビルド（ソースコードの変更がない限り、このレイヤーはキャッシュされる）
WORKDIR /usr/src/pg_bigm
RUN make USE_PGXS=1 && make USE_PGXS=1 install

# Stage 2: 実行環境（ビルド済みのpg_bigmのみを含む軽量イメージ）
FROM pgvector/pgvector:0.8.1-pg18

USER root

# ビルド済みのpg_bigmをコピー（ビルド依存関係は含めない）
COPY --from=builder /usr/share/postgresql/18/extension/pg_bigm* /usr/share/postgresql/18/extension/
COPY --from=builder /usr/lib/postgresql/18/lib/pg_bigm.so /usr/lib/postgresql/18/lib/

USER postgres

# ⚠️ ビルドキャッシュ最適化のメリット:
# - ビルド依存関係のインストールレイヤーは、依存関係が変更されない限りキャッシュされる
# - pg_bigmのソースコードが変更されない限り、ビルドレイヤーもキャッシュされる
# - 実行環境は軽量で、ビルド依存関係を含まないため、イメージサイズが小さい
# - マルチステージビルドにより、ビルド依存関係を実行環境に含めない
```

**docker-compose.yml の修正**:

```yaml
services:
  postgres:
    # ⚠️ 改善（開発効率）: 開発環境では標準の pgvector イメージを使用
    # pg_bigm のビルドは時間がかかるため、開発中に docker-compose up --build を
    # 頻繁に行うと開発効率が落ちます。
    # 開発環境では ENABLE_HYBRID_SEARCH=false に設定し、標準イメージを使用
    # 本番環境ではカスタムイメージをビルドして使用
    # 
    # 開発環境（ENABLE_HYBRID_SEARCH=false）:
    image: pgvector/pgvector:0.8.1-pg18
    # 
    # 本番環境（ENABLE_HYBRID_SEARCH=true）:
    # build:
    #   context: .
    #   dockerfile: Dockerfile.postgres
    container_name: kotonoha-postgres
    # ... (その他の設定はそのまま)
```

**拡張機能の有効化とインデックス作成**:

```sql
-- pg_bigm 拡張の有効化
CREATE EXTENSION IF NOT EXISTS pg_bigm;

-- knowledge_chunks.content にGINインデックス（pg_bigm）を追加
CREATE INDEX idx_chunks_content_bigm ON knowledge_chunks 
USING gin (content gin_bigm_ops);
```

**使用例（ハイブリッド検索）**:

pg_bigm の最大の特徴は、PostgreSQL標準の `LIKE` 演算子を使用した中間一致検索が高速になることです。

**推奨実装（UNION ALL方式）**:

FULL OUTER JOINは両方のCTEを完全評価するため非効率です。UNION ALLを使用した方が効率的です。

```sql
-- ベクトル検索とキーワード検索のスコアを組み合わせ（UNION ALL方式）
WITH vector_results AS (
    SELECT 
        id,
        source_id,
        content,
        1 - (embedding <=> $1::halfvec(1536)) AS vector_similarity
    FROM knowledge_chunks
    WHERE embedding IS NOT NULL
    ORDER BY embedding <=> $1::halfvec(1536)
    LIMIT 50  -- 候補を広めに取る
),
keyword_results AS (
    SELECT 
        id,
        source_id,
        content,
        1.0 AS keyword_score  -- ヒットしたらスコア1.0（重み付けで調整）
    FROM knowledge_chunks
    WHERE content LIKE $2  -- pg_bigm インデックスが使用される（$2 は '%検索キーワード%'）
      AND embedding IS NOT NULL  -- ⚠️ 必須: HNSWインデックス使用のため
    LIMIT 100  -- ⚠️ 改善（クエリ効率）: キーワード検索にも上限を設ける（巨大なテーブルでのボトルネックを防ぐ）
),
combined AS (
    SELECT id, source_id, content, vector_similarity * 0.7 AS score 
    FROM vector_results
    UNION ALL
    SELECT id, source_id, content, keyword_score * 0.3 AS score 
    FROM keyword_results
)
SELECT 
    id,
    source_id,
    content,
    SUM(score) AS combined_score
FROM combined
GROUP BY id, source_id, content
ORDER BY combined_score DESC
LIMIT 10;
```

**注意**: FULL OUTER JOIN方式も動作しますが、パフォーマンスが劣るため、UNION ALL方式を推奨します。

**注意点とデメリット**:

1. **インデックスサイズ**: pg_bigm のインデックスは pg_trgm よりも大きくなる傾向があります（2文字の組み合わせの方が3文字よりも多いため）
   - **対策**: NASのストレージ容量には注意してください。ただしテキストデータのみのインデックスなので、ベクトルデータ（HNSW）に比べればそこまで巨大にはなりません。

2. **更新速度**: インデックス作成・更新にかかるCPU負荷が若干高いです。
   - **対策**: Botの知識化処理はバックグラウンドで行われるため、ユーザー体験への影響は軽微です。

3. **1文字検索**: pg_bigm は「2文字」のインデックスですが、1文字の検索も可能です（全件スキャンよりはマシですが、少し遅くなります）。
   - **実用上の問題**: 日本語検索において1文字検索（例：「あ」だけ検索）の需要は低いため、実用上は問題ありません。

#### オプション2: tsvector を使用（FTS）

**メリット**: PostgreSQL標準の全文検索機能。言語固有の解析が可能。

```sql
-- 全文検索用カラムの追加
ALTER TABLE knowledge_chunks 
ADD COLUMN content_tsvector tsvector 
GENERATED ALWAYS AS (to_tsvector('japanese', content)) STORED;

-- GINインデックスの作成
CREATE INDEX idx_chunks_content_fts ON knowledge_chunks USING gin (content_tsvector);
```

**使用例**:

```sql
-- ベクトル検索と全文検索のハイブリッド
SELECT 
    id,
    source_id,
    content,
    1 - (embedding <=> $1::halfvec(1536)) AS vector_similarity,
    ts_rank(content_tsvector, to_tsquery('japanese', $2)) AS text_rank
FROM knowledge_chunks
WHERE 
    embedding IS NOT NULL
    AND (embedding <=> $1::halfvec(1536) < 0.3  -- ベクトル類似度
         OR content_tsvector @@ to_tsquery('japanese', $2))  -- 全文検索
ORDER BY 
    (1 - (embedding <=> $1::halfvec(1536))) * 0.7 + 
    ts_rank(content_tsvector, to_tsquery('japanese', $2)) * 0.3 DESC
LIMIT 10;
```

#### 推奨実装方針

1. **初期実装**: ベクトル検索のみ（現状）
2. **段階的導入**: `pg_bigm` 拡張を有効化し、インデックスを追加（設計段階で準備）
   - Dockerfile で pg_bigm をビルドしてカスタムイメージを作成
   - docker-compose.yml でカスタムイメージを使用
3. **ハイブリッド検索**: 検索精度の向上が必要になったタイミングで実装

**注意**: `pg_bigm` インデックスは追加のストレージ容量を消費しますが、
日本語検索の精度向上を考慮して設計段階で追加しておくことを強く推奨します。
特に kotonoha-bot のような日本語チャットログを扱うシステムには最適です。

---

## 11. 実装上の注意事項とベストプラクティス

### 11.1 セッションのチャンク化時のフォーマット改善

**問題**: 会話ログを単純に `\n` で結合すると、「誰が何を言ったか」の文脈がベクトル空間上で薄まる可能性があります。

**改善案**: チャンク化する際、以下のいずれかの形式を採用することを推奨します。

#### オプション1: Markdown形式

```python
def format_messages_for_knowledge(messages: list[dict]) -> str:
    """会話ログをMarkdown形式でフォーマット"""
    formatted = []
    for msg in messages:
        role = msg['role']
        content = msg['content']
        if role == 'user':
            formatted.append(f"**User**: {content}")
        elif role == 'assistant':
            formatted.append(f"**Assistant**: {content}")
        elif role == 'system':
            formatted.append(f"**System**: {content}")
    return "\n\n".join(formatted)
```

**出力例**:

```txt
**User**: こんにちは

**Assistant**: こんにちは！何かお手伝いできることはありますか？

**User**: Pythonのベストプラクティスを教えて
```

#### オプション2: メタデータに話者情報を含める

```python
def format_messages_for_knowledge(messages: list[dict]) -> tuple[str, dict]:
    """会話ログをフォーマットし、メタデータも返す"""
    content = "\n".join([msg['content'] for msg in messages])
    metadata = {
        "speakers": [msg['role'] for msg in messages],
        "message_count": len(messages),
        "first_speaker": messages[0]['role'] if messages else None
    }
    return content, metadata
```

**メリット**:

- ベクトル空間上で話者の文脈が保持される
- 検索結果の可読性が向上
- メタデータでのフィルタリングが可能

### 11.2 halfvec使用時の型キャスト

**問題**: `halfvec` 固定採用のため、クエリ時の型キャストも `halfvec` に合わせる必要があります。pgvectorのバージョンによっては、型の不一致でエラーが発生する可能性があります。

**解決策**: halfvec固定採用のため、SQL構築時に型キャストは `halfvec(1536)` を使用します。

```python
# ⚠️ 重要: halfvec固定採用
VECTOR_TYPE = "halfvec(1536)"

# 検索クエリの構築
async def similarity_search(
    self,
    query_embedding: list[float],
    top_k: int = 10
) -> list[dict]:
    """類似度検索（halfvec固定採用）"""
    query = f"""
        SELECT 
            s.type,
            s.title,
            c.content,
            1 - (c.embedding <=> $1::{VECTOR_TYPE}) AS similarity
        FROM knowledge_chunks c
        JOIN knowledge_sources s ON c.source_id = s.id
        WHERE c.embedding IS NOT NULL
          AND s.status = 'completed'
        ORDER BY c.embedding <=> $1::{VECTOR_TYPE}
        LIMIT $2
    """
    results = await self.pool.fetch(query, query_embedding, top_k)
    return [dict(row) for row in results]
```

**注意**: テーブル定義とクエリの型は `halfvec(1536)` で統一されています。

#### ⚠️ halfvec の入力型処理に関する重要な注意事項

**問題**: SQL文では `$1::halfvec(1536)` とキャストしていますが、
Python側（asyncpg）から渡すパラメータ `query_embedding` は `list[float]` です。
PostgreSQL側で `float[]` から `halfvec` へのキャストは自動で行われますが、
明示的なキャストがないと曖昧さのエラーが出る場合があります。

**解決策**:

1. **明示的な型キャスト**: SQL内で `::halfvec(1536)` と明示的にキャストする（現在の実装で対応済み、halfvec固定採用）

2. **pgvector-python の register_vector の動作**:
   - `pgvector.asyncpg.register_vector()` は `vector` 型と `halfvec` 型の両方をサポートします
   - ⚠️ **重要**: `register_vector()` は通常 `float32` として扱います
   - Python側から `list[float]` を渡すと、PostgreSQL側で `float32[] -> halfvec` のキャストが行われるため機能はします
   - ⚠️ **注意**: ドライバ層でのオーバーヘッドが微増しますが、許容範囲内です
   - 明示的な型キャスト（`$1::halfvec(1536)`）により、PostgreSQL側で適切に変換されます

3. **INSERT時の注意**:

   ```python
   # ✅ 正しい実装（明示的なキャスト、halfvec固定）
   vector_cast = "halfvec"
   await conn.execute(f"""
       UPDATE knowledge_chunks
       SET embedding = $1::{vector_cast}(1536)
       WHERE id = $2
   """, embedding_list, chunk_id)
   ```

4. **SELECT時の注意**:

   ```python
   # ✅ 正しい実装（明示的なキャスト）
   query = f"""
       SELECT embedding <=> $1::{vector_cast}(1536) AS distance
       FROM knowledge_chunks
   """
   ```

**テスト時の確認事項**:

⚠️ **重要**: 実装時には必ずhalfvec固定採用でのINSERTとSELECTが通るか確認してください。

```python
# テスト例
async def test_halfvec_insert_and_select():
    """halfvec固定採用でのINSERTとSELECTのテスト"""
    # 環境変数を設定
    # halfvec固定採用のため、環境変数の設定は不要
    
    # テスト用のベクトル
    test_embedding = [0.1] * 1536
    
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

### 11.3 pgvectorの型登録（asyncpg接続プール）

**問題**: `pgvector` Pythonライブラリを使用する場合、asyncpgの接続プールの各接続に対して型登録を行う必要があります。接続プール作成後に1つの接続に対してのみ登録すると、他の接続では型が認識されません。

**解決策**: `asyncpg.create_pool()` の `init` パラメータを使用して、各接続の初期化時に型登録を行います。

#### ❌ 誤った実装

```python
# 誤り: プール作成後に1つの接続にのみ登録
self.pool = await asyncpg.create_pool(...)
async with self.pool.acquire() as conn:
    await pgvector.asyncpg.register_vector(conn)  # この conn のみに登録される
    # プールの他のコネクションには登録されていない！
```

#### ✅ 正しい実装（pgvector-python公式ドキュメント推奨）

⚠️ **重要**: `asyncpg.create_pool()` の `init` パラメータには単一の関数しか渡せません。
pgvectorの型登録とJSONBコーデックの登録を両方行う場合は、ラッパー関数を作成する必要があります。

```python
async def _init_connection(self, conn: asyncpg.Connection):
    """コネクション初期化用ラッパー（ベクトル登録とJSONBコーデックを両方実行）"""
    # 1. pgvectorの型登録
    from pgvector.asyncpg import register_vector
    await register_vector(conn)
    
    # 2. JSONBコーデックの登録（orjsonを使用する場合）
    import orjson
    await conn.set_type_codec(
        'jsonb',
        encoder=lambda v: orjson.dumps(v).decode('utf-8'),
        decoder=lambda b: orjson.loads(
            b.encode('utf-8') if isinstance(b, str) else b
        ),
        schema='pg_catalog',
        format='text'
    )

async def initialize(self):
    self.pool = await asyncpg.create_pool(
        self.connection_string,
        init=self._init_connection,  # ← これが重要！
        min_size=min_size,
        max_size=max_size,
    )
```

**メリット**:

- **すべての接続で型登録**: プールの各接続が作成される際に自動的に型登録される
- **コードの簡潔性**: SQL内で手動キャストやエンコード/デコードが不要
- **型安全性**: Pythonの型チェッカーが正しく動作
- **JSONB自動変換**: dict/listを直接渡せる（orjsonによる高速処理）

**注意**: `init` パラメータは接続プール作成時に指定する必要があります。接続プール作成後に個別の接続に対して登録しても、プール内の他の接続には反映されません。

### 11.4 JSONBの自動変換（asyncpgカスタムコーデック）

**問題**: `asyncpg` で `json.dumps` して文字列として挿入している場合、コード内で `json.dumps/loads` を書く必要があり、コードが冗長になります。

**解決策**: `asyncpg` のカスタムコーデックを設定することで、Pythonの `dict` と PostgreSQLの `JSONB` を自動変換できます。

⚠️ **重要**: JSONBコーデックの登録は、pgvectorの型登録と同じ `_init_connection` 関数内で行います。
`asyncpg.create_pool()` の `init` パラメータには単一の関数しか渡せないため、両方を1つのラッパー関数にまとめる必要があります。

詳細は [11.3 pgvectorの型登録](#113-pgvectorの型登録asyncpg接続プール) の実装例を参照してください。

#### 使用例

```python
# コーデック設定後は、dictを直接渡せる
async def save_session(conn: asyncpg.Connection, session_key: str, messages: list[dict]):
    """セッション保存（orjson.dumps不要）"""
    await conn.execute("""
        INSERT INTO sessions (session_key, messages)
        VALUES ($1, $2::jsonb)
    """, session_key, messages)  # messages は list[dict] を直接渡せる

# 取得時も自動的にdictに変換される
async def load_session(conn: asyncpg.Connection, session_key: str):
    """セッション読み込み（orjson.loads不要）"""
    row = await conn.fetchrow("""
        SELECT messages FROM sessions WHERE session_key = $1
    """, session_key)
    
    if row:
        messages = row['messages']  # 自動的に list[dict] に変換される
        return messages
    return None
```

**メリット**:

- **コードの簡潔性**: `orjson.dumps/loads` が不要
- **型安全性**: Pythonの型チェッカーが正しく動作
- **パフォーマンス**: orjsonによる高速な自動変換

### 11.5 並行性制御のベストプラクティス

#### 推奨パターン: FOR UPDATE SKIP LOCKED

**理由**: アプリケーションレベルのロック（`asyncio.Lock`）では、以下の問題が発生します：

1. **単一プロセス制限**: 単一のBotプロセスでしか機能しない
2. **再起動時の競合**: Bot再起動や誤った2重起動時に同じチャンクを同時処理
3. **スケールアウト不可**: 複数のワーカーが同時実行できない

**解決策**: PostgreSQLの `FOR UPDATE SKIP LOCKED` を使用して、DBレベルで排他制御を行います。

```python
async def process_embedding_batch(
    self,
    batch_size: int = 100
) -> int:
    """並行処理安全なEmbeddingバッチ処理"""
    processed_count = 0
    
    async with self.pool.acquire() as conn:
        async with conn.transaction():
            # FOR UPDATE SKIP LOCKED で取得
            rows = await conn.fetch("""
                SELECT id, source_id, content, token_count
                FROM knowledge_chunks
                WHERE embedding IS NULL
                ORDER BY id ASC
                LIMIT $1
                FOR UPDATE SKIP LOCKED
            """, batch_size)
            
            if not rows:
                return 0
            
            # 各チャンクを処理
            for row in rows:
                try:
                    # Embedding生成
                    embedding = await self._generate_embedding(row['content'])
                    
                    # 更新（型キャストを動的に変更）
                    await conn.execute(f"""
                        UPDATE knowledge_chunks
                        SET embedding = $1::{VECTOR_TYPE},
                            token_count = $2
                        WHERE id = $3
                    """, embedding, row['token_count'], row['id'])
                    
                    processed_count += 1
                except Exception as e:
                    logger.error(f"Failed to process chunk {row['id']}: {e}")
                    # エラー時は次のチャンクに進む
    
    return processed_count
```

**メリット**:

- **DBレベルでの排他制御**: アプリケーションレベルのロック不要
- **スケールアウト対応**: 複数のBotプロセスやワーカーが同時実行可能
- **再起動時の安全性**: Bot再起動や誤った2重起動時も競合が発生しない
- **パフォーマンス**: ロックされた行は自動的にスキップされ、待機しない

**注意**: `FOR UPDATE SKIP LOCKED` はトランザクション内で実行する必要があります。

### 11.6 接続プール管理とバックグラウンドタスク

**問題**: バックグラウンドタスク（セッションアーカイブ処理など）で並列処理を
行う場合、各タスクがDB接続を取得するため、`DB_POOL_MAX_SIZE` が小さい場合、
バックグラウンドタスクだけでプールを食い尽くし、通常のチャット応答
（MessageHandler）がタイムアウトするリスクがあります。

#### 解決策1（推奨）: セマフォによる動的制限

バックグラウンドタスク用のセマフォの上限を `DB_POOL_MAX_SIZE` の20〜30%程度に厳密に制限します。

```python
# セッションアーカイブの並列処理例
import os

max_pool_size = int(os.getenv("DB_POOL_MAX_SIZE", "20"))
# 20〜30%程度に制限（最小1、最大5）
archive_concurrency = max(1, min(5, int(max_pool_size * 0.25)))
archive_semaphore = asyncio.Semaphore(archive_concurrency)
```

**推奨設定**:

- **通常のチャット応答**: プールの70〜80%を確保
- **バックグラウンドタスク**: プールの20〜30%に制限
- **緊急時の余裕**: 10%程度の余裕を持たせる

#### 解決策2（大規模運用時）: 接続プールの分離

バックグラウンドタスク（Embedding, Archive）用の `asyncpg.Pool` と、Web/Bot応答用のプールを分ける選択肢もあります。

```python
# 接続プールの分離例
class PostgreSQLDatabase:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.pool: asyncpg.Pool | None = None  # Web/Bot応答用
        self.background_pool: asyncpg.Pool | None = None  # バックグラウンドタスク用
    
    async def initialize(self) -> None:
        # Web/Bot応答用プール（通常のサイズ）
        self.pool = await asyncpg.create_pool(
            self.connection_string,
            init=self._init_connection,
            min_size=5,
            max_size=20,
        )
        
        # バックグラウンドタスク用プール（小さいサイズ）
        self.background_pool = await asyncpg.create_pool(
            self.connection_string,
            init=self._init_connection,
            min_size=2,
            max_size=5,  # バックグラウンドタスクは少ない接続で十分
        )
```

**選択基準**:

- **小規模運用（個人Bot）**: セマフォによる動的制限で十分
- **大規模運用（複数ワーカー、高負荷）**: 接続プールの分離を検討

**注意**: 接続プールを分ける場合、運用の複雑さが増すため、まずはセマフォによる制限を試し、必要に応じて分離を検討してください。

### 11.7 楽観的ロックの再試行ロジック

**問題**: 楽観的ロック（`UPDATE ... WHERE last_active_at = old_value`）が失敗した場合（0件更新）、例外を投げてロールバックしますが、自動リトライがない場合、Botが高頻度で使われている場合、アーカイブが何度も失敗し続ける可能性があります。

#### ⚠️ 改善（データ整合性）: versionカラムを使用した楽観的ロック

- **現状の問題**: TIMESTAMPTZの精度（マイクロ秒）で競合検出に依存していると、同一マイクロ秒内の更新で誤検知の可能性（極めて稀だが理論上あり得る）
- **改善案**: `version`カラム（INT、更新ごとにインクリメント）を追加する方が堅牢です
- **実装**: `UPDATE ... SET version = version + 1 WHERE version = $expected_version`

**解決策**: `tenacity` ライブラリを使用して、競合時のリトライ（指数バックオフ付き）を実装します。

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

@retry(
    stop=stop_after_attempt(3),  # 最大3回リトライ
    wait=wait_exponential(multiplier=1, min=1, max=10),  # 指数バックオフ: 1秒、2秒、4秒
    retry=retry_if_exception_type(ValueError),  # ValueError（楽観的ロック競合）のみリトライ
    reraise=True  # 最終的に失敗した場合は例外を再発生
)
async def _archive_session_with_retry():
    """楽観的ロック競合時の自動リトライ付きアーカイブ処理"""
    # UPDATE ... WHERE last_active_at = old_value が失敗した場合、
    # ValueError が発生し、自動的にリトライされる
    return await self._archive_session_impl(session_row)
```

**推奨設定**:

- **最大リトライ回数**: 3回
- **バックオフ**: 指数バックオフ（1秒、2秒、4秒）
- **リトライ対象**: 楽観的ロック競合（`ValueError`）のみ

**注意**: リトライ回数が多すぎると、逆に負荷が増加する可能性があるため、適切な上限を設定してください。

### 11.8 PostgreSQL 18 用テストスクリプトの実装

**背景**: PostgreSQL 18は比較的新しいバージョンであるため、本番環境での安定性を確保するために、テストスクリプトを充実させる方針を採用しています。

#### テストフィクスチャの実装

**推奨**: `testcontainers-python` を使用して、テスト時にPostgreSQL 18コンテナを自動起動します。

```python
# tests/conftest.py
import pytest
import pytest_asyncio
from testcontainers.postgres import PostgresContainer
from kotonoha_bot.db.postgres import PostgreSQLDatabase

@pytest.fixture(scope="session")
async def postgres_container():
    """テスト用PostgreSQL 18コンテナを起動"""
    with PostgresContainer("pgvector/pgvector:0.8.1-pg18") as postgres:
        yield postgres.get_connection_url()

@pytest_asyncio.fixture
async def postgres_db(postgres_container):
    """PostgreSQL データベースのフィクスチャ"""
    db = PostgreSQLDatabase(postgres_container)
    await db.initialize()
    
    # スキーマの初期化
    await db._create_schema()
    
    yield db
    
    # テスト後のクリーンアップ
    await db.close()
```

#### 重点テスト項目

1. **halfvec型の動作確認**

```python
# tests/unit/test_postgres_halfvec.py
async def test_halfvec_insert_and_search(postgres_db):
    """halfvec型のINSERTと検索のテスト"""
    # テスト用のベクトル
    test_embedding = [0.1] * 1536
    
    # INSERTテスト
    await postgres_db.pool.execute("""
        INSERT INTO knowledge_chunks (content, embedding)
        VALUES ($1, $2::halfvec(1536))
    """, "test content", test_embedding)
    
    # SELECTテスト（類似度検索）
    result = await postgres_db.pool.fetchrow("""
        SELECT embedding <=> $1::halfvec(1536) AS distance
        FROM knowledge_chunks
        WHERE content = 'test content'
    """, test_embedding)
    
    assert result is not None
    assert result['distance'] == 0.0  # 同じベクトルなので距離は0
```

1. **HNSWインデックスの動作確認**

```python
# tests/integration/test_hnsw_index.py
async def test_hnsw_index_performance(postgres_db):
    """HNSWインデックスの性能テスト"""
    # 大量のテストデータを挿入
    test_embeddings = [[0.1 * i] * 1536 for i in range(1000)]
    
    # バッチINSERT
    async with postgres_db.pool.acquire() as conn:
        async with conn.transaction():
            for i, emb in enumerate(test_embeddings):
                await conn.execute("""
                    INSERT INTO knowledge_chunks (content, embedding)
                    VALUES ($1, $2::halfvec(1536))
                """, f"test content {i}", emb)
    
    # インデックスが使用されているか確認（EXPLAIN ANALYZE）
    result = await postgres_db.pool.fetchrow("""
        EXPLAIN ANALYZE
        SELECT * FROM knowledge_chunks
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> $1::halfvec(1536)
        LIMIT 10
    """, test_embeddings[0])
    
    # インデックススキャンが使用されていることを確認
    assert "Index Scan using idx_chunks_embedding" in str(result)
```

1. **pgvector型登録の確認**

```python
# tests/unit/test_pgvector_registration.py
async def test_pgvector_type_registration(postgres_db):
    """pgvectorの型登録が正しく行われているか確認"""
    # 型登録が行われていれば、halfvec型を直接使用できる
    result = await postgres_db.pool.fetchval("""
        SELECT '[1,2,3]'::halfvec(3) <=> '[1,2,3]'::halfvec(3)
    """)
    
    assert result == 0.0  # 同じベクトルなので距離は0
```

1. **JSONBコーデックの動作確認**

```python
# tests/unit/test_jsonb_codec.py
async def test_jsonb_automatic_conversion(postgres_db):
    """JSONBコーデックが正しく動作しているか確認"""
    test_data = {"key": "value", "number": 123}
    
    # INSERT（dictを直接渡せる）
    await postgres_db.pool.execute("""
        INSERT INTO knowledge_sources (type, title, metadata)
        VALUES ($1, $2, $3::jsonb)
    """, "discord_session", "test", test_data)
    
    # SELECT（自動的にdictに変換される）
    result = await postgres_db.pool.fetchrow("""
        SELECT metadata FROM knowledge_sources WHERE title = 'test'
    """)
    
    assert result['metadata'] == test_data
    assert isinstance(result['metadata'], dict)
```

1. **並行性制御のテスト**

```python
# tests/integration/test_concurrency.py
async def test_for_update_skip_locked(postgres_db):
    """FOR UPDATE SKIP LOCKED の動作確認"""
    # 複数の未処理チャンクを挿入
    for i in range(10):
        await postgres_db.pool.execute("""
            INSERT INTO knowledge_chunks (source_id, content)
            VALUES ($1, $2)
        """, 1, f"test content {i}")
    
    # 2つのトランザクションで同時に取得を試みる
    async with postgres_db.pool.acquire() as conn1:
        async with postgres_db.pool.acquire() as conn2:
            async with conn1.transaction():
                rows1 = await conn1.fetch("""
                    SELECT id FROM knowledge_chunks
                    WHERE embedding IS NULL
                    LIMIT 5
                    FOR UPDATE SKIP LOCKED
                """)
                
                async with conn2.transaction():
                    rows2 = await conn2.fetch("""
                        SELECT id FROM knowledge_chunks
                        WHERE embedding IS NULL
                        LIMIT 5
                        FOR UPDATE SKIP LOCKED
                    """)
            
            # 2つのトランザクションで異なる行が取得されることを確認
            ids1 = {row['id'] for row in rows1}
            ids2 = {row['id'] for row in rows2}
            assert ids1.isdisjoint(ids2)  # 重複がないことを確認
```

#### テスト実行コマンド

```bash
# すべてのPostgreSQLテストを実行
pytest tests/ -k postgres -v

# 統合テストのみ実行
pytest tests/integration/ -v

# カバレッジ付きで実行
pytest tests/ --cov=src/kotonoha_bot --cov-report=term-missing

# PostgreSQL 18コンテナを使用したテスト
docker-compose -f docker-compose.test.yml up -d
pytest tests/integration/test_postgres.py -v
```

#### CI/CDでの自動テスト

GitHub Actionsでの自動テスト設定例：

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]

jobs:
  test-postgres18:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:0.8.1-pg18
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test_kotonoha
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -e ".[test]"
      - run: pytest tests/ -v --cov=src/kotonoha_bot
```

**推奨テストカバレッジ**: 80%以上（特にPostgreSQL関連のコード）

---

## 12. バックアップ戦略

### 12.1 バックアップ方法の選択

**推奨バックアップ方法**:

1. **pg_dump による定期バックアップ**（小規模〜中規模データ）
   - カスタムフォーマット（圧縮済み）を使用
   - 論理バックアップ（データとスキーマを含む）
   - リストア時にインデックスの再構築が必要

2. **物理バックアップ（WALアーカイブ）**（大規模データ）
   - ファイルシステムレベルのバックアップ
   - リストア時間が短い
   - より複雑な設定が必要

### 12.2 pg_dump によるバックアップ

**基本的なバックアップコマンド**:

```bash
# カスタムフォーマット（推奨、圧縮済み）
pg_dump -U kotonoha -F c -f kotonoha_backup.dump kotonoha

# プレーンテキスト形式（可読性が高い）
pg_dump -U kotonoha -F p -f kotonoha_backup.sql kotonoha
```

**リストアコマンド**:

```bash
# カスタムフォーマットからのリストア
pg_restore -U kotonoha -d kotonoha -c kotonoha_backup.dump

# プレーンテキスト形式からのリストア
psql -U kotonoha -d kotonoha < kotonoha_backup.sql
```

### 12.3 ⚠️ 重要: バックアップとリストアの整合性

#### 課題: pg_dump は論理バックアップです

- **pgvector のデータは復元されますが、インデックスの再構築がリストア時に走るため、リストア時間が非常に長くなる可能性があります**
- HNSWインデックス（`idx_chunks_embedding`）は、データ量に応じて構築時間が増加します
- 10万件を超えるデータの場合、インデックス再構築に数時間かかる可能性があります

#### 対策

1. **小規模データ（〜10万件）**:
   - `pg_dump` による論理バックアップで十分
   - リストア後のインデックス再構築時間を許容範囲として計算に入れておく
   - リストア時間の見積もり:
     - データ量: 10万件 → インデックス再構築: 約30分〜1時間（環境による）
     - データ量: 50万件 → インデックス再構築: 約2〜4時間（環境による）

2. **大規模データ（10万件超）**:
   - **物理バックアップ（WALアーカイブなど）を検討する**
   - ファイルシステムレベルのバックアップ（`pg_basebackup`）
   - リストア時間が大幅に短縮される
   - より複雑な設定と運用が必要

3. **ハイブリッドアプローチ**:
   - 定期的な `pg_dump` による論理バックアップ（データ整合性の確認用）
   - 日次または週次の物理バックアップ（高速リストア用）

**推奨バックアップ戦略**:

```bash
# 日次バックアップ（論理バックアップ）
0 2 * * * pg_dump -U kotonoha -F c \
  -f /backups/kotonoha_$(date +\%Y\%m\%d).dump kotonoha

# 週次物理バックアップ（大規模データの場合）
0 3 * * 0 pg_basebackup -U kotonoha \
  -D /backups/basebackup_$(date +\%Y\%m\%d) -Ft -z -P
```

**リストア時間の見積もり**:

| データ量 | 論理バックアップ（pg_dump） | 物理バックアップ（pg_basebackup） |
|---------|---------------------------|--------------------------------|
| 1万件 | 約5分 | 約2分 |
| 10万件 | 約30分〜1時間 | 約5分 |
| 50万件 | 約2〜4時間 | 約10分 |
| 100万件 | 約4〜8時間 | 約20分 |

**注意**: 上記の時間は環境（CPU、メモリ、ストレージ性能）によって大きく変動します。

---

## 付録

### A. 完全なDDLスクリプト

```sql
-- ============================================
-- kotonoha-bot PostgreSQL Schema
-- Version: 1.0
-- Created: 2026-01-19
-- ============================================

-- 拡張機能の有効化
CREATE EXTENSION IF NOT EXISTS vector;

-- ハイブリッド検索用（オプション、将来の拡張用）
-- CREATE EXTENSION IF NOT EXISTS pg_bigm;

-- ENUM型の定義
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

DO $$ BEGIN
    CREATE TYPE session_status_enum AS ENUM (
        'active',
        'archived'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE source_status_enum AS ENUM (
        'pending',
        'processing',
        'completed',
        'partial',  -- ⚠️ 改善（データ整合性）: 一部のチャンクがDLQに移動した（検索可能だが不完全）
        'failed'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- sessions テーブル
-- ⚠️ 改善（Strong Recommendation）: id BIGSERIAL PRIMARY KEY を追加し、
-- session_key は UNIQUE NOT NULL に変更
-- 理由: 「新規設計で移行ツールを作らない」という前提であれば、最初から最適解を選ぶべき
-- TEXT型の主キーはインデックスサイズが肥大化し、将来的に外部キー参照を行う際に
-- パフォーマンス（JOIN速度）とストレージ効率が悪化する
CREATE TABLE IF NOT EXISTS sessions (
    id BIGSERIAL PRIMARY KEY,
    session_key TEXT UNIQUE NOT NULL,  -- アプリケーション内部での参照用
    session_type TEXT NOT NULL,
    messages JSONB DEFAULT '[]'::jsonb NOT NULL,
    status session_status_enum DEFAULT 'active',
    guild_id BIGINT,        -- Discord Guild ID（Discord URL生成に必要）
    channel_id BIGINT,
    thread_id BIGINT,
    user_id BIGINT,
    version INT DEFAULT 1,  -- ⚠️ 追加: 楽観的ロック用（更新ごとにインクリメント）
    last_archived_message_index INT DEFAULT 0,  -- ⚠️ 改善: アーカイブ済みメッセージのインデックス（0=未アーカイブ）
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    last_active_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- knowledge_sources テーブル
CREATE TABLE IF NOT EXISTS knowledge_sources (
    id BIGSERIAL PRIMARY KEY,
    type source_type_enum NOT NULL,
    title TEXT NOT NULL,
    uri TEXT,
    status source_status_enum DEFAULT 'pending',
    error_code TEXT,  -- ⚠️ 改善（セキュリティ）: エラーコード（例: 'EMBEDDING_API_TIMEOUT', 'RATE_LIMIT'）
    error_message TEXT,  -- ⚠️ 改善（セキュリティ）: 一般化されたメッセージのみ（詳細なスタックトレースはログのみに出力）
    -- ⚠️ 改善（疎結合）: origin_session_id は外部キーではなく metadata に記録
    -- セッションからアーカイブされたソースの場合、metadata に origin_session_id と origin_session_key を記録
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- knowledge_chunks テーブル
-- ⚠️ 重要: embedding は NULL許容です
-- Embedding生成前のデータをINSERTし、後でUPDATEするフローを採用
-- 理由: トランザクション分離のため（FOR UPDATE SKIP LOCKED + Tx分離パターン）
-- 検索時は必ず embedding IS NOT NULL 条件を含めること（HNSWインデックス使用のため）
CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id BIGSERIAL PRIMARY KEY,
    source_id BIGINT REFERENCES knowledge_sources(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding halfvec(1536),  -- ⚠️ NULL許容、halfvec固定採用
    location JSONB DEFAULT '{}'::jsonb,
    token_count INT,
    retry_count INT DEFAULT 0,  -- Dead Letter Queue対応
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- knowledge_chunks_dlq テーブル（Dead Letter Queue）
CREATE TABLE IF NOT EXISTS knowledge_chunks_dlq (
    id BIGSERIAL PRIMARY KEY,
    original_chunk_id BIGINT,
    source_id BIGINT,           -- ⚠️ 改善: 元のソースID（外部キー制約なし）
    source_title TEXT,          -- ⚠️ 改善: デバッグ用にソースのタイトルも保存
    content TEXT NOT NULL,
    error_code TEXT,            -- ⚠️ 改善: エラーコードを分離して保存
    error_message TEXT,
    retry_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    last_retry_at TIMESTAMPTZ
);

-- インデックスの作成
CREATE INDEX IF NOT EXISTS idx_sessions_session_key ON sessions(session_key);
-- アプリケーション内部での参照用
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_last_active_at ON sessions(last_active_at);
CREATE INDEX IF NOT EXISTS idx_sessions_channel_id ON sessions(channel_id);
CREATE INDEX IF NOT EXISTS idx_sessions_archive_candidates ON sessions(status, last_active_at)
WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_sources_metadata ON knowledge_sources USING gin (metadata);
CREATE INDEX IF NOT EXISTS idx_sources_status ON knowledge_sources(status);
CREATE INDEX IF NOT EXISTS idx_sources_type ON knowledge_sources(type);

CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON knowledge_chunks 
USING hnsw (embedding halfvec_cosine_ops)
WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_chunks_source_id ON knowledge_chunks(source_id);
-- ⚠️ 重要: この部分インデックスは必須です
-- HNSWインデックス（idx_chunks_embedding）は embedding が NULL でない
-- 場合にのみ有効。検索クエリで embedding IS NOT NULL 条件を忘れると、
-- HNSWインデックスが使われずフルスキャンになる
CREATE INDEX IF NOT EXISTS \
idx_chunks_searchable ON knowledge_chunks(source_id, created_at)
WHERE embedding IS NOT NULL AND token_count > 0;

-- ⚠️ 改善（パフォーマンス）: 処理待ち行列専用の部分インデックス
-- FOR UPDATE SKIP LOCKED を使うクエリは WHERE embedding IS NULL を参照します。
-- knowledge_chunks が数百万件になった際、embedding IS NULL の行を探すのに
-- 時間がかかるとバッチ処理が遅延します。
-- 処理待ち行列専用の部分インデックスを作成することで、ワーカーはテーブル全体を
-- スキャンせず、インデックスのみを見て処理対象を即座に見つけられます。
-- リトライ上限未満（retry_count < 3）のみを含めることで、諦められたチャンクを除外
CREATE INDEX IF NOT EXISTS idx_chunks_queue ON knowledge_chunks(id)
WHERE embedding IS NULL AND retry_count < 3;

-- ハイブリッド検索用インデックス（オプション、将来の拡張用）
-- pg_bigm 拡張を有効化した後に実行
-- CREATE INDEX IF NOT EXISTS idx_chunks_content_trgm ON knowledge_chunks 
-- USING gin (content gin_trgm_ops);

-- 制約の追加
ALTER TABLE sessions 
ADD CONSTRAINT chk_sessions_status 
CHECK (status IN ('active', 'archived'));

ALTER TABLE knowledge_sources 
ADD CONSTRAINT chk_sources_status 
CHECK (status IN ('pending', 'processing', 'completed', 'partial', 'failed'));
```

### B. 環境変数一覧

**⚠️ 重要**: 本番環境では `DATABASE_URL` にパスワードを含める形式ではなく、以下のように分離することを推奨します：

```bash
# 推奨: パスワードを分離
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=kotonoha
POSTGRES_USER=kotonoha
POSTGRES_PASSWORD=<secret>
```

| 環境変数 | 説明 | デフォルト値 |
|---------|------|------------|
| `DATABASE_URL` | PostgreSQL接続文字列（開発環境用） | `postgresql://kotonoha:password@localhost:5432/kotonoha` |
| `POSTGRES_HOST` | PostgreSQLホスト（本番環境推奨） | - |
| `POSTGRES_PORT` | PostgreSQLポート（本番環境推奨） | `5432` |
| `POSTGRES_DB` | データベース名（本番環境推奨） | - |
| `POSTGRES_USER` | ユーザー名（本番環境推奨） | - |
| `POSTGRES_PASSWORD` | パスワード（本番環境推奨、シークレット管理） | - |
| `DB_POOL_MIN_SIZE` | 接続プール最小サイズ | `5` |
| `DB_POOL_MAX_SIZE` | 接続プール最大サイズ | `20` |
| `DB_COMMAND_TIMEOUT` | コマンドタイムアウト（秒） | `60` |
| ~~`KB_USE_HALFVEC`~~ | ~~halfvec使用フラグ~~ | ~~削除（halfvec固定採用）~~ |
| `KB_HNSW_M` | HNSWインデックス m パラメータ | `16` |
| `KB_HNSW_EF_CONSTRUCTION` | HNSWインデックス ef_construction パラメータ | `64` |
| `KB_SIMILARITY_THRESHOLD` | 類似度検索の閾値 | `0.7` |
| `KB_DEFAULT_TOP_K` | デフォルトの検索結果数 | `10` |
| `KB_EMBEDDING_MAX_RETRY` | Embedding処理の最大リトライ回数 | `3` |
| `KB_EMBEDDING_BATCH_SIZE` | Embedding処理のバッチサイズ | `100` |
| `KB_CHUNK_MAX_TOKENS` | チャンクの最大トークン数 | `4000` |
| `KB_CHUNK_OVERLAP_RATIO` | チャンクのオーバーラップ比率 | `0.2` |
| `KB_CHUNK_INSERT_BATCH_SIZE` | チャンク一括登録時のバッチサイズ | `100` |
| `KB_CHUNK_UPDATE_BATCH_SIZE` | チャンク一括更新時のバッチサイズ | `100` |

---

### C. ヘルスチェック実装

**目的**: データベース接続の確認を含むヘルスチェックエンドポイントを実装します。

⚠️ 改善（コード品質）: ヘルスチェックの不完全さを改善します。
pgvector拡張の動作確認が含まれていませんでした。

```python
# src/kotonoha_bot/health.py
"""ヘルスチェック機能（DB接続確認含む）"""

import asyncpg
import structlog
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .db.postgres import PostgreSQLDatabase

logger = structlog.get_logger(__name__)


async def health_check(db: "PostgreSQLDatabase") -> dict:
    """ヘルスチェック（DB接続確認含む）
    
    Returns:
        dict: ヘルスステータス
            - status: "healthy" または "unhealthy"
            - database: "connected" または "disconnected"
            - error: エラーメッセージ（unhealthyの場合）
    """
    try:
        async with db.pool.acquire() as conn:
            # 基本的な接続確認
            await conn.fetchval("SELECT 1")
            
            # ⚠️ 改善: pgvector の動作確認も含める
            # pgvector拡張が正しく動作していることを確認
            # ベクトル演算（<=>演算子）が使用可能であることを確認
            result = await conn.fetchval(
                "SELECT '[1,2,3]'::vector <=> '[1,2,3]'::vector"
            )
            if result is None:
                return {
                    "status": "unhealthy",
                    "database": "connected",
                    "pgvector": "not_working",
                    "error": "pgvector extension not working properly"
                }
            
            # pgvector拡張のバージョン確認（オプション）
            pgvector_version = await conn.fetchval(
                "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
            )
            
        return {
            "status": "healthy",
            "database": "connected",
            "pgvector": "working",
            "pgvector_version": pgvector_version
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }
```

**FastAPIエンドポイント例**:

```python
# src/kotonoha_bot/api/health.py
from fastapi import APIRouter, Depends
from ...health import health_check
from ...db.postgres import PostgreSQLDatabase

router = APIRouter()

@router.get("/health")
async def get_health(db: PostgreSQLDatabase = Depends(get_db)):
    """ヘルスチェックエンドポイント"""
    return await health_check(db)
```

**docker-compose.yml のヘルスチェック設定**:

```yaml
services:
  bot:
    # ... その他の設定
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

---

## 変更履歴

| 日付 | バージョン | 変更内容 |
|------|-----------|---------|
| 2026-01-19 | 1.22 | 初版作成 |

---

**作成日**: 2026年1月19日  
**最終更新日**: 2026年1月19日（v1.22）  
**作成者**: kotonoha-bot 開発チーム
