# PostgreSQL スキーマ設計書 - テーブル定義

**作成日**: 2026年1月19日  
**バージョン**: 1.22  
**対象プロジェクト**: kotonoha-bot v0.8.0

## 関連ドキュメント

- [概要](./postgresql-schema-overview.md)
- [インデックス設計](./postgresql-schema-indexes.md)
- [完全なDDLスクリプト](./postgresql-schema-ddl.md)
- [クエリガイド](../../50_implementation/51_guides/postgresql-query-guide.md)

---

## テーブル定義

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
    last_archived_message_index INT DEFAULT 0,
        -- ⚠️ 改善: アーカイブ済みメッセージのインデックス（0=未アーカイブ）

    -- 時間管理
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    last_active_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
```

#### sessions テーブルのカラム詳細

| カラム名 | データ型 | 制約 | 説明 |
|---------|---------|------|------|
| `id` | BIGSERIAL | PRIMARY KEY | セッションID（自動採番）。将来的な外部キー参照用 |
| `session_key` | TEXT | UNIQUE NOT NULL | セッションキー（一意）。形式: `"mention:{user_id}"`, |
  | | | | `"thread:{thread_id}"`, `"eavesdrop:{channel_id}"`。 |
  | | | | `"thread:{thread_id}"`, `"eavesdrop:{channel_id}"`。 |
  | | | | アプリケーション内部での参照用 |
| `session_type` | TEXT | NOT NULL | セッションタイプ（`mention`, `thread`, `eavesdrop`） |
| `messages` | JSONB | NOT NULL, DEFAULT `'[]'::jsonb` | 会話履歴。JSON配列形式で保存 |
| `status` | session_status_enum | DEFAULT `'active'` | セッション状態。`'active'` または `'archived'` |
| `guild_id` | BIGINT | NULL | Discord Guild ID（Discord URL生成に必要。DMの場合はNULL） |
| `channel_id` | BIGINT | NULL | Discord チャンネル ID |
| `thread_id` | BIGINT | NULL | Discord スレッド ID（スレッド型の場合） |
| `user_id` | BIGINT | NULL | Discord ユーザー ID |
| `version` | INT | DEFAULT 1 | ⚠️ 追加: 楽観的ロック用（更新ごとにインクリメント）。 |
  | | | | TIMESTAMPTZの精度（マイクロ秒）で競合検出に依存していると、 |
  | | | | TIMESTAMPTZの精度（マイクロ秒）で競合検出に依存していると、 |
  | | | | 同一マイクロ秒内の更新で誤検知の可能性があるため、 |
  | | | | versionカラムを使用する方が堅牢 |
| `last_archived_message_index` | INT | DEFAULT 0 | ⚠️ 改善: アーカイブ済みメッセージのインデックス（0=未アーカイブ）。 |
  | | | | 高頻度でチャットが続く場合でも、確定した過去部分だけをアーカイブでき、 |
  | | | | 高頻度でチャットが続く場合でも、確定した過去部分だけをアーカイブでき、 |
  | | | | リトライループに陥ることを防ぐ |
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
    error_code TEXT,
        -- ⚠️ 改善（セキュリティ）: エラーコード
        -- （例: 'EMBEDDING_API_TIMEOUT', 'RATE_LIMIT'）
    error_message TEXT,  -- ⚠️ 改善（セキュリティ）: 一般化されたメッセージのみ（詳細なスタックトレースはログのみに出力）

    -- 柔軟なメタデータ (JSONB)
    -- Chat: { "channel_name": "dev-talk", "participants": [123, 456],
    -- "origin_session_id": 123, "origin_session_key": "thread:999" }
    -- File: { "file_size": 1024, "mime_type": "application/pdf" }
    -- ⚠️ 改善（疎結合）: origin_session_id は外部キーではなく metadata に記録
    -- 理由: 「短期記憶（Sessions）」と「長期記憶（Knowledge）」はライフサイクルが異なるため、
    -- 外部キー制約による強い依存関係を避け、知識として独立した存在として扱う
    -- これにより、「削除時の挙動」を設計する必要がなくなり、シンプルな設計になる
    -- セッションからアーカイブされたソースの場合、
    -- metadata に origin_session_id と origin_session_key を記録
    metadata JSONB DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
```

#### knowledge_sources テーブルのカラム詳細

| カラム名 | データ型 | 制約 | 説明 |
|---------|---------|------|------|
| `id` | BIGSERIAL | PRIMARY KEY | 知識ソースID（自動採番） |
| `type` | source_type_enum | NOT NULL | ソースタイプ（`discord_session`, `document_file`, `web_page`, |
  | | | | `image_caption`, `audio_transcript`） |
  | | | | `image_caption`, `audio_transcript`） |
| `title` | TEXT | NOT NULL | 検索結果に表示する見出し |
| `uri` | TEXT | NULL | 元データへのリンク（Discord URL、S3 Path、Web URLなど） |
| `status` | source_status_enum | DEFAULT `'pending'` | 処理状態（`pending`, `processing`, `completed`, `partial`, `failed`）。 |
  | | | | `partial`は一部のチャンクがDLQに移動した場合 |
| `error_code` | TEXT | NULL | ⚠️ 改善（セキュリティ）: エラーコード |
  | | | | （例: 'EMBEDDING_API_TIMEOUT', 'RATE_LIMIT'）。 |
  | | | | 詳細なスタックトレースはログのみに出力し、 |
  | | | | データベースには保存しない |
| `error_message` | TEXT | NULL | ⚠️ 改善（セキュリティ）: 一般化されたエラーメッセージのみ |
  | | | | （`status='failed'` の場合）。 |
  | | | | APIエラーやスタックトレースが含まれる可能性があるため、 |
  | | | | 一般化されたメッセージのみを保存 |
| `metadata` | JSONB | DEFAULT `'{}'::jsonb` | 柔軟なメタデータ（ソースタイプごとに異なる属性を格納）。 |
  | | | | セッションからアーカイブされたソースの場合、 |
  | | | | `origin_session_id` と `origin_session_key` を含む。 |
  | | | | ⚠️ 改善（疎結合）: 外部キー制約ではなく metadata に記録することで、 |
  | | | | ライフサイクルの完全分離を実現 |
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

⚠️ **重要**: `location` フィールドは柔軟なJSONBですが、
検索結果を表示する際にBotが「どこへのリンクを生成すべきか」を
判断するために、**共通のインターフェース**を定義します。

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