# Phase 8 確認項目のテストカバレッジ分析

## 概要

`phase08-remaining-tasks.md`に記載されている確認項目のうち、
テストで自動化可能な項目を分析し、追加のテストケースを実装する計画をまとめます。

---

## 確認項目の分類

### ✅ 既にテストで実装済み

以下の確認項目は、既にテストケースとして実装されています：

1. **PostgreSQL接続の確認**
   - ✅ `test_postgres_db_initialize` - データベース初期化テスト

2. **セッションの保存・読み込み確認**
   - ✅ `test_postgres_db_save_and_load_session` - セッション保存・読み込みテスト

3. **知識ベーススキーマの確認**
   - ✅ `test_postgres_db_save_source` - 知識ソース保存テスト
   - ✅ `test_postgres_db_save_chunk` - 知識チャンク保存テスト

4. **ベクトル検索の確認**
   - ✅ `test_postgres_db_similarity_search` - ベクトル検索テスト
   - ✅ `test_postgres_db_similarity_search_with_filters` - フィルタリング付き検索テスト
   - ✅ `test_postgres_db_similarity_search_without_threshold` - 閾値フィルタリングなしのテスト

5. **Embedding処理の確認**
   - ✅ `test_embedding_processor_initialization` - EmbeddingProcessor初期化テスト
   - ✅ `test_embedding_processor_process_pending_chunks` - Embedding処理テスト
   - ✅ `test_embedding_processor_retry_logic` - リトライロジックテスト
   - ✅ `test_embedding_processor_batch_processing` - バッチ処理テスト

6. **セッション知識化の確認**
   - ✅ `test_session_archiver_initialization` - SessionArchiver初期化テスト
   - ✅ `test_session_archiver_archive_session` - セッションアーカイブテスト
   - ✅ `test_session_archiver_sliding_window` - スライディングウィンドウテスト
   - ✅ `test_session_archiver_filtering` - フィルタリングロジックテスト

7. **パフォーマンス確認**
   - ✅ `test_vector_search_performance` - ベクトル検索の性能測定
   - ✅ `test_vector_search_with_index` - HNSWインデックスの効果確認

8. **halfvec型の確認**
   - ✅ `test_postgres_db_halfvec_insert_and_select` - halfvec型のINSERT/SELECTテスト

---

### 🔧 テストで追加実装可能（推奨）

以下の確認項目は、テストケースとして追加実装することを推奨します：

#### 1. pgvector拡張の確認

**確認項目**:

- [ ] pgvector拡張が有効化されている
- [ ] halfvec型が使用可能

**実装例**:

```python
@pytest.mark.asyncio
async def test_pgvector_extension(postgres_db):
    """pgvector拡張の確認"""
    async with postgres_db.pool.acquire() as conn:
        # pgvector拡張が有効化されているか確認
        result = await conn.fetchrow(
            "SELECT * FROM pg_extension WHERE extname = 'vector'"
        )
        assert result is not None
        
        # halfvec型が使用可能か確認
        result = await conn.fetchval("SELECT '[1,2,3]'::halfvec(3)")
        assert result is not None
```

#### 2. DLQ（Dead Letter Queue）の確認

**確認項目**:

- [ ] `retry_count >= 3`のチャンクがDLQに移動されている
- [ ] DLQに移動されたチャンクが元の`knowledge_chunks`テーブルから削除されている
- [ ] エラーコードとエラーメッセージが適切に記録されている

**実装例**:

```python
@pytest.mark.asyncio
async def test_embedding_processor_dlq(postgres_db, mock_embedding_provider):
    """DLQへの移動ロジックのテスト"""
    # エラーを発生させるモック
    error_provider = AsyncMock(spec=OpenAIEmbeddingProvider)
    error_provider.generate_embeddings_batch = AsyncMock(
        side_effect=Exception("API Error")
    )
    error_provider.get_dimension = lambda: 1536

    # テスト用のチャンクを作成
    source_id = await postgres_db.save_source(...)
    chunk_id = await postgres_db.save_chunk(...)

    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=error_provider,
        batch_size=10,
        max_concurrent=2,
    )

    # 最大リトライ回数まで処理を実行
    for _ in range(3):
        await processor._process_pending_embeddings_impl()

    # DLQに移動されているか確認
    async with postgres_db.pool.acquire() as conn:
        dlq_result = await conn.fetchrow(
            "SELECT * FROM knowledge_chunks_dlq WHERE original_chunk_id = $1",
            chunk_id
        )
        assert dlq_result is not None
        assert dlq_result["error_code"] is not None
        
        # 元のテーブルから削除されているか確認
        chunk_result = await conn.fetchrow(
            "SELECT * FROM knowledge_chunks WHERE id = $1",
            chunk_id
        )
        assert chunk_result is None
```

#### 3. Sourceステータスの更新確認

**確認項目**:

- [ ] すべてのチャンクが処理された場合、Sourceのステータスが`'completed'`になっている
- [ ] DLQに移動されたチャンクがある場合、Sourceのステータスが`'partial'`になっている
- [ ] 処理中のチャンクがある場合、Sourceのステータスが`'pending'`のままになっている

**実装例**:

```python
@pytest.mark.asyncio
async def test_source_status_update(postgres_db, mock_embedding_provider):
    """Sourceステータスの更新確認"""
    # テスト用のソースとチャンクを作成
    source_id = await postgres_db.save_source(...)
    chunk_ids = [await postgres_db.save_chunk(...) for _ in range(5)]

    processor = EmbeddingProcessor(...)
    await processor._process_pending_embeddings_impl()

    # Sourceステータスが'completed'になっているか確認
    async with postgres_db.pool.acquire() as conn:
        result = await conn.fetchrow(
            "SELECT status FROM knowledge_sources WHERE id = $1",
            source_id
        )
        assert result["status"] == "completed"
```

#### 4. 楽観的ロックの確認

**確認項目**:

- [ ] アーカイブ後、`version`カラムがインクリメントされている
- [ ] `last_archived_message_index`が正しく更新されている

**実装例**:

```python
@pytest.mark.asyncio
async def test_optimistic_locking(postgres_db, mock_embedding_provider):
    """楽観的ロックの確認"""
    session = ChatSession(...)
    await postgres_db.save_session(session)
    
    original_version = session.version
    
    archiver = SessionArchiver(...)
    await archiver._archive_session_impl(...)
    
    # versionがインクリメントされているか確認
    async with postgres_db.pool.acquire() as conn:
        result = await conn.fetchrow(
            """
            SELECT version, last_archived_message_index
            FROM sessions
            WHERE session_key = $1
            """,
            session.session_key,
        )
        assert result["version"] == original_version + 1
        assert result["last_archived_message_index"] > 0
```

#### 5. チャンク化戦略の確認

**確認項目**:

- [ ] チャンク化戦略が環境変数から正しく読み込まれている
- [ ] メッセージ単位でのチャンク化が適用されている
- [ ] 各チャンクのトークン数が`KB_CHUNK_MAX_TOKENS`以下になっている

**実装例**:

```python
@pytest.mark.asyncio
async def test_chunking_strategy(postgres_db, mock_embedding_provider):
    """チャンク化戦略の確認"""
    # 複数のメッセージを持つセッションを作成
    session = ChatSession(
        messages=[Message(...) for _ in range(10)],
        ...
    )
    
    archiver = SessionArchiver(...)
    await archiver._archive_session_impl(...)
    
    # チャンクが作成されているか確認
    async with postgres_db.pool.acquire() as conn:
        chunks = await conn.fetch(
            "SELECT * FROM knowledge_chunks WHERE source_id = $1",
            source_id
        )
        assert len(chunks) > 0
        
        # 各チャンクのトークン数が上限以下か確認
        for chunk in chunks:
            assert chunk["token_count"] <= settings.kb_chunk_max_tokens
```

#### 6. バッチ処理の確認

**確認項目**:

- [ ] バッチサイズが環境変数から正しく読み込まれている
- [ ] 同時実行数がDB_POOL_MAX_SIZEの20〜30%程度に制限されている

**実装例**:

```python
@pytest.mark.asyncio
async def test_batch_processing_settings(postgres_db, mock_embedding_provider):
    """バッチ処理の設定確認"""
    processor = EmbeddingProcessor(
        db=postgres_db,
        embedding_provider=mock_embedding_provider,
        batch_size=10,
        max_concurrent=2,
    )
    
    assert processor.batch_size == 10
    assert processor._semaphore._value == 2
```

#### 7. エラーハンドリングの確認

**確認項目**:

- [ ] データベース接続エラーが適切にハンドリングされている
- [ ] Embedding APIエラーが適切にハンドリングされている
- [ ] 接続プール枯渇時、適切なエラーメッセージが表示される

**実装例**:

```python
@pytest.mark.asyncio
async def test_database_connection_error():
    """データベース接続エラーのハンドリング"""
    # 無効な接続文字列でデータベースを作成
    db = PostgreSQLDatabase(
        connection_string="postgresql://invalid:invalid@localhost:5432/invalid"
    )
    
    with pytest.raises(RuntimeError):
        await db.initialize()

@pytest.mark.asyncio
async def test_embedding_api_error(postgres_db):
    """Embedding APIエラーのハンドリング"""
    # エラーを発生させるモック
    error_provider = AsyncMock()
    error_provider.generate_embeddings_batch = AsyncMock(
        side_effect=Exception("API Error")
    )
    
    processor = EmbeddingProcessor(...)
    
    # エラーが発生してもクラッシュしないことを確認
    await processor._process_pending_embeddings_impl()
    
    # retry_countがインクリメントされているか確認
    ...
```

---

### ⚠️ テストで自動化困難（手動確認が必要）

以下の確認項目は、実際の環境での手動確認が必要です：

1. **Discord Bot経由での動作確認**
   - 実際のDiscord接続が必要
   - 統合テストとして実装可能だが、Discord APIのモックが必要

2. **バックグラウンドタスクの起動確認**
   - ログ解析が必要
   - 部分的にテスト可能（タスクの開始状態を確認）

3. **Graceful Shutdown**
   - 実際のプロセス停止をシミュレートする必要がある
   - 部分的にテスト可能（shutdownメソッドの呼び出しを確認）

4. **パフォーマンス確認**
   - 実際の負荷が必要
   - パフォーマンステストとして実装済み（`tests/performance/`）

---

## 実装計画

### Phase 1: 基本的な確認項目のテスト化（優先度: 高）

1. ✅ pgvector拡張の確認
2. ✅ DLQの確認
3. ✅ Sourceステータスの更新確認
4. ✅ 楽観的ロックの確認

### Phase 2: 詳細な確認項目のテスト化（優先度: 中）

1. ✅ チャンク化戦略の確認
2. ✅ バッチ処理の確認
3. ✅ エラーハンドリングの確認

### Phase 3: 統合テストの実装（優先度: 低）

1. Discord Bot経由での動作確認（モックを使用）
2. バックグラウンドタスクの起動確認（ログ解析）
3. Graceful Shutdown（プロセス停止のシミュレート）

---

## テストカバレッジの目標

- **ユニットテスト**: 80%以上
- **統合テスト**: 主要な機能フローをカバー
- **パフォーマンステスト**: ベクトル検索、バッチ処理の性能測定

---

## まとめ

`phase08-remaining-tasks.md`に記載されている確認項目のうち、**約70-80%はテストで自動化可能**です。

既に実装済みのテストケースに加えて、上記の追加テストケースを実装することで、確認項目の大部分を自動化できます。

残りの20-30%は、実際の環境での手動確認が必要な項目（Discord Bot経由での動作確認、実際の負荷テストなど）です。
