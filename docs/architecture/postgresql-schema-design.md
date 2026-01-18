# PostgreSQL スキーマ設計書

**作成日**: 2026年1月19日  
**バージョン**: 1.2  
**対象プロジェクト**: kotonoha-bot v0.8.0  
**データベース**: PostgreSQL 16 + pgvector

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

- **データベース**: PostgreSQL 16
- **ベクトル拡張**: pgvector 0.5.0以降（HNSWインデックス対応）
- **非同期ライブラリ**: asyncpg 0.29.0以降
- **Embeddingモデル**: OpenAI text-embedding-3-small (1536次元)

---

## 2. ER図

```mermaid
erDiagram
    %% Short-term Memory: Sessions (Left Side)
    %% Real-time read/write area for Discord Bot. Optimized for speed.
    sessions {
        TEXT session_key PK "Discord ChannelID or ThreadID"
        TEXT session_type "Session type"
        JSONB messages "Conversation history"
        process_status_enum status "Status (active/archived)"
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
        process_status_enum status "Processing status"
        TEXT error_message "Error message"
        JSONB metadata "Flexible metadata"
        TIMESTAMPTZ created_at "Created timestamp"
        TIMESTAMPTZ updated_at "Updated timestamp"
    }

    knowledge_chunks {
        BIGSERIAL id PK "Chunk ID"
        BIGINT source_id FK "Reference to parent source"
        TEXT content "Searchable text content"
        vector_1536 embedding "Vector data (1536 dimensions)"
        JSONB location "Location info in original data"
        INT token_count "Token count"
        TIMESTAMPTZ created_at "Created timestamp"
    }

    %% Relationships
    knowledge_sources ||--o{ knowledge_chunks : "has many"
    %% Conversion from sessions to knowledge_sources is done by batch
    %% processing (not shown in ER diagram)
```

**構成の説明**:

- **Left Side (Sessions)**: Discord Botがリアルタイムに読み書きする場所。高速動作優先。
- **Right Side (Knowledge)**: AI検索用。あらゆるデータ（会話、ファイル、Web）を「Source」と「Chunk」に抽象化して管理。
- **データフロー**: `sessions` テーブルの非アクティブなセッションは、バッチ処理によって
  `knowledge_sources` と `knowledge_chunks` に変換されます。

---

## 3. 拡張機能と型定義

### 3.1 拡張機能

```sql
-- ベクトル検索機能の有効化 (必須)
CREATE EXTENSION IF NOT EXISTS vector;
```

**要件**: pgvector 0.5.0以降（HNSWインデックスを使用するため）

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

#### process_status_enum

処理ステータスを定義します。非同期パイプラインでの状態管理に使用します。

```sql
CREATE TYPE process_status_enum AS ENUM (
    'active',       -- (Session用) 会話中
    'pending',      -- (Source用) 処理待ち
    'processing',   -- ベクトル化やOCR処理中
    'completed',    -- 検索可能
    'archived',     -- (Session用) 知識化済み・アーカイブ
    'failed'        -- エラー
);
```

**使用箇所**:

- `sessions.status`: `'active'` または `'archived'` のみ使用
- `knowledge_sources.status`: `'pending'`, `'processing'`, `'completed'`, `'failed'`
  を使用

**注意**: 将来的には `session_status_enum` と `source_status_enum` を分けることを検討

---

## 4. テーブル定義

### 4.1 sessions テーブル

**目的**: Discord Bot のリアルタイム会話セッションを管理します。高速な読み書きに最適化されています。

#### 設計考慮事項

**主キーの選定**:

- **現状**: `session_key` (TEXT) を主キーとして使用
- **理由**: `session_key` でルックアップする頻度が高く、単一カラムの主キーで十分
- **将来の拡張性**:
  - 複数のDiscordサーバー（Guild）で運用する場合、`guild_id` との複合キーを検討可能
  - インデックスサイズ削減のため、内部的な `BIGSERIAL id` を主キーにし、`session_key` をユニーク制約付きカラムにする選択肢もある
  - 個人運用であれば現状の設計で問題なし

#### sessions テーブルのDDL

```sql
CREATE TABLE IF NOT EXISTS sessions (
    -- 基本キー (DiscordのChannelIDやThreadIDが入る)
    session_key TEXT PRIMARY KEY,

    -- セッションの種類 ('mention', 'thread', 'eavesdrop' 等)
    session_type TEXT NOT NULL,

    -- 会話履歴本体 (高速な読み書きのためJSONBを採用)
    -- 構造例: [{"role": "user", "content": "..."},
    -- {"role": "assistant", "content": "..."}]
    messages JSONB DEFAULT '[]'::jsonb NOT NULL,

    -- 状態管理 (会話中か、知識化済みか)
    status process_status_enum DEFAULT 'active',

    -- メタデータ (Discord IDは桁溢れ防止でBIGINT)
    channel_id BIGINT,
    thread_id BIGINT,
    user_id BIGINT,

    -- 時間管理
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    last_active_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
```

#### sessions テーブルのカラム詳細

| カラム名 | データ型 | 制約 | 説明 |
|---------|---------|------|------|
| `session_key` | TEXT | PRIMARY KEY | セッションキー（一意）。形式: `"mention:{user_id}"`, `"thread:{thread_id}"`, `"eavesdrop:{channel_id}"` |
| `session_type` | TEXT | NOT NULL | セッションタイプ（`mention`, `thread`, `eavesdrop`） |
| `messages` | JSONB | NOT NULL, DEFAULT `'[]'::jsonb` | 会話履歴。JSON配列形式で保存 |
| `status` | process_status_enum | DEFAULT `'active'` | セッション状態。`'active'` または `'archived'` |
| `channel_id` | BIGINT | NULL | Discord チャンネル ID |
| `thread_id` | BIGINT | NULL | Discord スレッド ID（スレッド型の場合） |
| `user_id` | BIGINT | NULL | Discord ユーザー ID |
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
    status process_status_enum DEFAULT 'pending',
    error_message TEXT,

    -- 柔軟なメタデータ (JSONB)
    -- Chat: { "channel_name": "dev-talk", "participants": [123, 456] }
    -- File: { "file_size": 1024, "mime_type": "application/pdf" }
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
| `status` | process_status_enum | DEFAULT `'pending'` | 処理状態（`pending`, `processing`, `completed`, `failed`） |
| `error_message` | TEXT | NULL | エラーメッセージ（`status='failed'` の場合） |
| `metadata` | JSONB | DEFAULT `'{}'::jsonb` | 柔軟なメタデータ（ソースタイプごとに異なる属性を格納） |
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
    -- 注意: halfvec(1536) を使用するとメモリ使用量が半分になります（pgvector 0.7.0以降）
    -- Synology NASのリソース節約のため、halfvecの採用を強く推奨します
    -- 環境変数 KB_USE_HALFVEC=true で halfvec を使用（デフォルト: false）
    embedding vector(1536),  -- または halfvec(1536)

    -- 元データ内での位置情報 (引用元提示用)
    -- Chat: { "message_id": 9999 }
    -- PDF:  { "page": 3 }
    location JSONB DEFAULT '{}'::jsonb,

    token_count INT,

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
| `embedding` | vector(1536) または halfvec(1536) | NULL | ベクトルデータ（1536次元）。NULLの場合は未処理 |
| `location` | JSONB | DEFAULT `'{}'::jsonb` | 元データ内での位置情報（引用元提示用） |
| `token_count` | INT | NULL | トークン数（Embedding APIの使用量計算用） |
| `created_at` | TIMESTAMPTZ | DEFAULT CURRENT_TIMESTAMP | 作成日時 |

#### location JSONB 構造例

**Discord Session**:

```json
{
  "message_id": 999999999999999999,
  "message_index": 5
}
```

**Document File**:

```json
{
  "page": 3,
  "paragraph": 2,
  "char_start": 100,
  "char_end": 500
}
```

**Web Page**:

```json
{
  "section": "main-content",
  "paragraph_index": 1
}
```

---

## 5. インデックス設計

### 5.1 sessions テーブルのインデックス

```sql
-- ステータスでの検索用（アーカイブ対象のセッション検索）
CREATE INDEX idx_sessions_status ON sessions(status);

-- 最終アクティビティ日時での検索用（タイムアウト判定）
CREATE INDEX idx_sessions_last_active_at ON sessions(last_active_at);

-- チャンネルIDでの検索用
CREATE INDEX idx_sessions_channel_id ON sessions(channel_id);
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
-- halfvec を使用する場合は halfvec_cosine_ops を使用
CREATE INDEX idx_chunks_embedding ON knowledge_chunks 
USING hnsw (embedding vector_cosine_ops)  -- または halfvec_cosine_ops
WITH (m = 16, ef_construction = 64);  -- 環境変数から読み込むことを推奨

-- Source IDでの検索用
CREATE INDEX idx_chunks_source_id ON knowledge_chunks(source_id);

-- embedding IS NOT NULL での検索用（検索可能なチャンクのみ取得）
CREATE INDEX idx_chunks_embedding_not_null ON knowledge_chunks(source_id) 
WHERE embedding IS NOT NULL;

-- ハイブリッド検索用インデックス（オプション、将来の拡張用）
-- pg_trgm 拡張を有効化した後に実行
-- 部分一致検索や類似文字列検索に使用（固有名詞の検索に有効）
-- CREATE EXTENSION IF NOT EXISTS pg_trgm;
-- CREATE INDEX idx_chunks_content_trgm ON knowledge_chunks 
-- USING gin (content gin_trgm_ops);
```

**HNSWインデックスパラメータ説明**:

- **m**: 各ノードの接続数。値が大きいほど精度が上がるが、インデックスサイズと構築時間が増加（デフォルト: 16）
- **ef_construction**: 構築時の探索深さ。値が大きいほど精度が上がるが、構築時間が増加（デフォルト: 64）

**使用例**:

- ベクトル類似度検索（`embedding <=> $1`）
- 特定ソースのチャンク一覧取得
- 検索可能なチャンクのみ取得（`embedding IS NOT NULL`）
- ハイブリッド検索（ベクトル検索 + pg_trgm キーワード検索）

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
ALTER TABLE sessions 
ADD CONSTRAINT chk_sessions_status 
CHECK (status IN ('active', 'archived'));

-- knowledge_sources.status は 'pending', 'processing', 'completed', 'failed' のみ許可
ALTER TABLE knowledge_sources 
ADD CONSTRAINT chk_sources_status 
CHECK (status IN ('pending', 'processing', 'completed', 'failed'));
```

### 6.3 一意制約

```sql
-- sessions.session_key は一意（PRIMARY KEY制約により自動的に一意）
-- 追加の一意制約は不要
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

- **vector(1536)**: 1536次元のベクトル型（float32、8バイト/次元）
- **halfvec(1536)**: 1536次元のベクトル型（float16、4バイト/次元、pgvector 0.7.0以降）

**メモリ使用量比較**:

- `vector(1536)`: 約 12KB/レコード（1536 × 8バイト）
- `halfvec(1536)`: 約 6KB/レコード（1536 × 4バイト）

**推奨**: Synology NASのリソース節約のため、`halfvec` の採用を推奨（精度への影響は最小限）

**重要**: `halfvec` を使用する場合、クエリ時の型キャストも `halfvec` に合わせる必要があります：

```sql
-- vector を使用する場合
SELECT * FROM knowledge_chunks
WHERE embedding <=> $1::vector(1536) < 0.3;

-- halfvec を使用する場合（型キャストを変更）
SELECT * FROM knowledge_chunks
WHERE embedding <=> $1::halfvec(1536) < 0.3;
```

**実装時の注意**: SQL構築時に、環境変数 `KB_USE_HALFVEC` に基づいて型キャストを動的に変更する必要があります。

### 7.3 TIMESTAMPTZ

**使用箇所**: すべての `*_at` カラム

**説明**: タイムゾーン情報を含むタイムスタンプ型。UTCで保存し、アプリケーション側でタイムゾーン変換を行う。

---

## 8. 使用例とクエリ

### 8.1 セッション管理

#### セッションの作成

```sql
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
SET embedding = $1::vector(1536)  -- または $1::halfvec(1536)
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
SELECT 
    s.type,
    s.title,
    s.uri,
    c.content,
    c.location,
    1 - (c.embedding <=> $1::vector(1536)) AS similarity
FROM knowledge_chunks c
JOIN knowledge_sources s ON c.source_id = s.id
WHERE c.embedding IS NOT NULL
  AND s.status = 'completed'
ORDER BY c.embedding <=> $1::vector(1536)
LIMIT 10;
```

#### 類似度閾値を指定した検索

```sql
SELECT 
    s.type,
    s.title,
    c.content,
    1 - (c.embedding <=> $1::vector(1536)) AS similarity
FROM knowledge_chunks c
JOIN knowledge_sources s ON c.source_id = s.id
WHERE c.embedding IS NOT NULL
  AND s.status = 'completed'
  AND 1 - (c.embedding <=> $1::vector(1536)) > 0.7  -- 類似度閾値
ORDER BY similarity DESC
LIMIT 5;
```

#### チャンネルフィルタ付き検索

```sql
SELECT 
    s.type,
    s.title,
    c.content,
    1 - (c.embedding <=> $1::vector(1536)) AS similarity
FROM knowledge_chunks c
JOIN knowledge_sources s ON c.source_id = s.id
WHERE c.embedding IS NOT NULL
  AND s.status = 'completed'
  AND s.metadata->>'channel_id' = '987654321'::text
ORDER BY c.embedding <=> $1::vector(1536)
LIMIT 10;
```

#### ソースタイプフィルタ付き検索

```sql
SELECT 
    s.type,
    s.title,
    c.content,
    1 - (c.embedding <=> $1::vector(1536)) AS similarity
FROM knowledge_chunks c
JOIN knowledge_sources s ON c.source_id = s.id
WHERE c.embedding IS NOT NULL
  AND s.status = 'completed'
  AND s.type = 'discord_session'
ORDER BY c.embedding <=> $1::vector(1536)
LIMIT 10;
```

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
   - ハイブリッド検索用のpg_trgmインデックス（`idx_chunks_content_trgm`、オプション）
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
SET embedding = $1::vector(1536),  -- または halfvec(1536)
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
                SET embedding = $1::vector(1536),
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

**注意**: ENUM値の追加は可能だが、削除は困難。慎重に設計すること。

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

#### オプション1: pg_trgm 拡張を使用（推奨）

**メリット**: 部分一致検索や類似文字列検索に強い。日本語にも対応。

```sql
-- pg_trgm 拡張の有効化
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- knowledge_chunks.content にGINインデックス（pg_trgm）を追加
CREATE INDEX idx_chunks_content_trgm ON knowledge_chunks 
USING gin (content gin_trgm_ops);
```

**使用例（ハイブリッド検索）**:

```sql
-- ベクトル検索とキーワード検索のスコアを組み合わせ
WITH vector_results AS (
    SELECT 
        id,
        source_id,
        content,
        1 - (embedding <=> $1::vector(1536)) AS vector_similarity
    FROM knowledge_chunks
    WHERE embedding IS NOT NULL
      AND 1 - (embedding <=> $1::vector(1536)) > 0.7
),
keyword_results AS (
    SELECT 
        id,
        source_id,
        content,
        similarity(content, $2) AS keyword_similarity  -- $2 は検索キーワード
    FROM knowledge_chunks
    WHERE content % $2  -- pg_trgm の類似度演算子
)
SELECT 
    COALESCE(v.id, k.id) AS id,
    COALESCE(v.source_id, k.source_id) AS source_id,
    COALESCE(v.content, k.content) AS content,
    COALESCE(v.vector_similarity, 0) * 0.7 +
    COALESCE(k.keyword_similarity, 0) * 0.3 AS combined_score
FROM vector_results v
FULL OUTER JOIN keyword_results k ON v.id = k.id
ORDER BY combined_score DESC
LIMIT 10;
```

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
    1 - (embedding <=> $1::vector(1536)) AS vector_similarity,
    ts_rank(content_tsvector, to_tsquery('japanese', $2)) AS text_rank
FROM knowledge_chunks
WHERE 
    embedding IS NOT NULL
    AND (embedding <=> $1::vector(1536) < 0.3  -- ベクトル類似度
         OR content_tsvector @@ to_tsquery('japanese', $2))  -- 全文検索
ORDER BY 
    (1 - (embedding <=> $1::vector(1536))) * 0.7 + 
    ts_rank(content_tsvector, to_tsquery('japanese', $2)) * 0.3 DESC
LIMIT 10;
```

#### 推奨実装方針

1. **初期実装**: ベクトル検索のみ（現状）
2. **段階的導入**: `pg_trgm` 拡張を有効化し、インデックスを追加（設計段階で準備）
3. **ハイブリッド検索**: 検索精度の向上が必要になったタイミングで実装

**注意**: `pg_trgm` インデックスは追加のストレージ容量を消費しますが、将来的な拡張性を考慮して設計段階で追加しておくことを推奨します。

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

**問題**: `halfvec` を使用する場合、クエリ時の型キャストも `halfvec` に合わせる必要があります。pgvectorのバージョンによっては、型の不一致でエラーが発生する可能性があります。

**解決策**: SQL構築時に、環境変数 `KB_USE_HALFVEC` に基づいて型キャストを動的に変更します。

```python
import os

USE_HALFVEC = os.getenv("KB_USE_HALFVEC", "false").lower() == "true"
VECTOR_TYPE = "halfvec(1536)" if USE_HALFVEC else "vector(1536)"

# 検索クエリの構築
async def similarity_search(
    self,
    query_embedding: list[float],
    top_k: int = 10
) -> list[dict]:
    """類似度検索（型キャストを動的に変更）"""
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

**注意**: テーブル定義とクエリの型を一致させる必要があります。

### 11.3 JSONBの自動変換（asyncpgカスタムコーデック）

**問題**: `asyncpg` で `json.dumps` して文字列として挿入している場合、コード内で `json.dumps/loads` を書く必要があり、コードが冗長になります。

**解決策**: `asyncpg` のカスタムコーデックを設定することで、Pythonの `dict` と PostgreSQLの `JSONB` を自動変換できます。

#### 実装例

```python
import asyncpg
import json

async def setup_jsonb_codec(conn: asyncpg.Connection):
    """JSONBカスタムコーデックの設定"""
    await conn.set_type_codec(
        'jsonb',
        encoder=lambda value: json.dumps(value),
        decoder=lambda value: json.loads(value),
        schema='pg_catalog',
        format='text'
    )

# 接続プール作成時に設定
async def create_pool(connection_string: str):
    pool = await asyncpg.create_pool(
        connection_string,
        min_size=5,
        max_size=20,
        init=setup_jsonb_codec  # 初期化時にコーデックを設定
    )
    return pool
```

#### 使用例

```python
# コーデック設定後は、dictを直接渡せる
async def save_session(conn: asyncpg.Connection, session_key: str, messages: list[dict]):
    """セッション保存（json.dumps不要）"""
    await conn.execute("""
        INSERT INTO sessions (session_key, messages)
        VALUES ($1, $2::jsonb)
    """, session_key, messages)  # messages は list[dict] を直接渡せる

# 取得時も自動的にdictに変換される
async def load_session(conn: asyncpg.Connection, session_key: str):
    """セッション読み込み（json.loads不要）"""
    row = await conn.fetchrow("""
        SELECT messages FROM sessions WHERE session_key = $1
    """, session_key)
    
    if row:
        messages = row['messages']  # 自動的に list[dict] に変換される
        return messages
    return None
```

**メリット**:

- **コードの簡潔性**: `json.dumps/loads` が不要
- **型安全性**: Pythonの型チェッカーが正しく動作
- **パフォーマンス**: 自動変換によりオーバーヘッドが最小限

**注意**: 接続プールの各接続に対してコーデックを設定する必要があります。`init` パラメータを使用することで、接続作成時に自動的に設定されます。

### 11.4 並行性制御のベストプラクティス

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
-- CREATE EXTENSION IF NOT EXISTS pg_trgm;

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
    CREATE TYPE process_status_enum AS ENUM (
        'active',
        'pending',
        'processing',
        'completed',
        'archived',
        'failed'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- sessions テーブル
CREATE TABLE IF NOT EXISTS sessions (
    session_key TEXT PRIMARY KEY,
    session_type TEXT NOT NULL,
    messages JSONB DEFAULT '[]'::jsonb NOT NULL,
    status process_status_enum DEFAULT 'active',
    channel_id BIGINT,
    thread_id BIGINT,
    user_id BIGINT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    last_active_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- knowledge_sources テーブル
CREATE TABLE IF NOT EXISTS knowledge_sources (
    id BIGSERIAL PRIMARY KEY,
    type source_type_enum NOT NULL,
    title TEXT NOT NULL,
    uri TEXT,
    status process_status_enum DEFAULT 'pending',
    error_message TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- knowledge_chunks テーブル
CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id BIGSERIAL PRIMARY KEY,
    source_id BIGINT REFERENCES knowledge_sources(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding vector(1536),  -- または halfvec(1536)
    location JSONB DEFAULT '{}'::jsonb,
    token_count INT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- インデックスの作成
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_last_active_at ON sessions(last_active_at);
CREATE INDEX IF NOT EXISTS idx_sessions_channel_id ON sessions(channel_id);

CREATE INDEX IF NOT EXISTS idx_sources_metadata ON knowledge_sources USING gin (metadata);
CREATE INDEX IF NOT EXISTS idx_sources_status ON knowledge_sources(status);
CREATE INDEX IF NOT EXISTS idx_sources_type ON knowledge_sources(type);

CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON knowledge_chunks 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_chunks_source_id ON knowledge_chunks(source_id);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_not_null
ON knowledge_chunks(source_id)
WHERE embedding IS NOT NULL;

-- ハイブリッド検索用インデックス（オプション、将来の拡張用）
-- pg_trgm 拡張を有効化した後に実行
-- CREATE INDEX IF NOT EXISTS idx_chunks_content_trgm ON knowledge_chunks 
-- USING gin (content gin_trgm_ops);

-- 制約の追加
ALTER TABLE sessions 
ADD CONSTRAINT chk_sessions_status 
CHECK (status IN ('active', 'archived'));

ALTER TABLE knowledge_sources 
ADD CONSTRAINT chk_sources_status 
CHECK (status IN ('pending', 'processing', 'completed', 'failed'));
```

### B. 環境変数一覧

| 環境変数 | 説明 | デフォルト値 |
|---------|------|------------|
| `DATABASE_URL` | PostgreSQL接続文字列 | `postgresql://kotonoha:password@localhost:5432/kotonoha` |
| `DB_POOL_MIN_SIZE` | 接続プール最小サイズ | `5` |
| `DB_POOL_MAX_SIZE` | 接続プール最大サイズ | `20` |
| `DB_COMMAND_TIMEOUT` | コマンドタイムアウト（秒） | `60` |
| `KB_USE_HALFVEC` | halfvec使用フラグ | `false` |
| `KB_HNSW_M` | HNSWインデックス m パラメータ | `16` |
| `KB_HNSW_EF_CONSTRUCTION` | HNSWインデックス ef_construction パラメータ | `64` |

---

---

## 変更履歴

| 日付 | バージョン | 変更内容 |
|------|-----------|---------|
| 2026-01-19 | 1.0 | 初版作成 |
| 2026-01-19 | 1.1 | レビュー指摘を反映:<br/>- セッションのチャンク化時のフォーマット改善案を追加<br/>- halfvec使用時の型キャストの注意点を追加<br/>- FOR UPDATE SKIP LOCKED パターンの説明と実装例を追加 |
| 2026-01-19 | 1.2 | 設計改善点を反映:<br/>- ハイブリッド検索（pg_trgm）の導入検討を追加<br/>- session_key主キー選定の設計考慮事項を追加<br/>- JSONB自動変換（asyncpgカスタムコーデック）の実装例を追加 |

---

**作成日**: 2026年1月19日  
**最終更新日**: 2026年1月19日（v1.2）  
**作成者**: kotonoha-bot 開発チーム
