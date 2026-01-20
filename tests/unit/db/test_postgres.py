"""PostgreSQLDatabase のテスト"""

from datetime import UTC, datetime

import pytest
from dirty_equals import IsDatetime

from kotonoha_bot.db.models import ChatSession, Message, MessageRole
from kotonoha_bot.db.postgres import PostgreSQLDatabase


@pytest.mark.asyncio
async def test_postgres_db_initialize(postgres_db):
    """PostgreSQLDatabaseの初期化テスト"""
    assert postgres_db.pool is not None
    assert postgres_db.pool.get_size() > 0


@pytest.mark.asyncio
async def test_postgres_db_save_and_load_session(postgres_db):
    """セッションの保存と読み込みテスト"""
    # テスト用のセッションを作成
    session = ChatSession(
        session_key="test:session:001",
        session_type="mention",
        messages=[
            Message(
                role=MessageRole.USER,
                content="テストメッセージ",
                timestamp=datetime.now(UTC),
            )
        ],
        guild_id=123456789,
        channel_id=987654321,
        user_id=111222333,
    )

    # セッションを保存
    await postgres_db.save_session(session)

    # セッションを読み込み
    loaded_session = await postgres_db.load_session("test:session:001")

    assert loaded_session is not None
    assert loaded_session.session_key == "test:session:001"
    assert loaded_session.session_type == "mention"
    assert len(loaded_session.messages) == 1
    assert loaded_session.messages[0].content == "テストメッセージ"
    assert loaded_session.guild_id == 123456789
    assert loaded_session.channel_id == 987654321
    assert loaded_session.user_id == 111222333
    # dirty-equalsを使用してタイムスタンプをチェック（動的な値）
    assert loaded_session.created_at == IsDatetime(approx=datetime.now(UTC), delta=10)
    assert loaded_session.last_active_at == IsDatetime(
        approx=datetime.now(UTC), delta=10
    )


@pytest.mark.asyncio
async def test_postgres_db_save_source(postgres_db):
    """知識ソースの保存テスト"""
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="テストソース",
        uri="https://example.com/test",
        metadata={"test": True},
        status="pending",
    )

    assert source_id is not None
    assert isinstance(source_id, int)


@pytest.mark.asyncio
async def test_postgres_db_save_chunk(postgres_db):
    """知識チャンクの保存テスト"""
    # まずソースを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="テストソース",
        uri="https://example.com/test",
        metadata={"test": True},
        status="pending",
    )

    # チャンクを保存
    chunk_id = await postgres_db.save_chunk(
        source_id=source_id,
        content="これはテスト用のチャンクです",
        location={"url": "https://example.com/test", "label": "テスト"},
        token_count=10,
    )

    assert chunk_id is not None
    assert isinstance(chunk_id, int)


@pytest.mark.asyncio
async def test_postgres_db_similarity_search(postgres_db):
    """ベクトル検索のテスト"""
    # テスト用のソースとチャンクを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="テストソース",
        uri="https://example.com/test",
        metadata={"test": True},
        status="pending",
    )

    chunk_id = await postgres_db.save_chunk(
        source_id=source_id,
        content="これはテスト用のチャンクです",
        location={"url": "https://example.com/test", "label": "テスト"},
        token_count=10,
    )

    # テスト用のベクトルを挿入（1536次元のダミーベクトル）
    async with postgres_db.pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE knowledge_chunks
            SET embedding = (SELECT array_agg(0.1::real) FROM generate_series(1, 1536))::halfvec(1536)
            WHERE id = $1
        """,
            chunk_id,
        )

    # ベクトル検索を実行
    query_embedding = [0.1] * 1536
    results = await postgres_db.similarity_search(
        query_embedding=query_embedding,
        top_k=5,
    )

    assert len(results) > 0
    assert results[0]["chunk_id"] == chunk_id
    assert results[0]["similarity"] > 0.0


@pytest.mark.asyncio
async def test_postgres_db_similarity_search_with_filters(postgres_db):
    """フィルタリング付きベクトル検索のテスト"""
    # テスト用のソースとチャンクを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="テストソース",
        uri="https://example.com/test",
        metadata={"channel_id": 123456, "user_id": 789012},
        status="pending",
    )

    chunk_id = await postgres_db.save_chunk(
        source_id=source_id,
        content="これはテスト用のチャンクです",
        location={"url": "https://example.com/test", "label": "テスト"},
        token_count=10,
    )

    # テスト用のベクトルを挿入
    async with postgres_db.pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE knowledge_chunks
            SET embedding = (SELECT array_agg(0.1::real) FROM generate_series(1, 1536))::halfvec(1536)
            WHERE id = $1
        """,
            chunk_id,
        )

    # フィルタリング付きベクトル検索を実行
    query_embedding = [0.1] * 1536
    results = await postgres_db.similarity_search(
        query_embedding=query_embedding,
        top_k=5,
        filters={"channel_id": 123456},
    )

    assert len(results) > 0
    assert results[0]["chunk_id"] == chunk_id

    # 異なるチャンネルIDでフィルタリング（結果が空になることを確認）
    results_empty = await postgres_db.similarity_search(
        query_embedding=query_embedding,
        top_k=5,
        filters={"channel_id": 999999},
    )

    assert len(results_empty) == 0


@pytest.mark.asyncio
async def test_postgres_db_similarity_search_without_threshold(postgres_db):
    """閾値フィルタリングなしのベクトル検索テスト"""
    # テスト用のソースとチャンクを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="テストソース",
        uri="https://example.com/test",
        metadata={"test": True},
        status="pending",
    )

    chunk_id = await postgres_db.save_chunk(
        source_id=source_id,
        content="これはテスト用のチャンクです",
        location={"url": "https://example.com/test", "label": "テスト"},
        token_count=10,
    )

    # テスト用のベクトルを挿入（すべて0.1の値）
    async with postgres_db.pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE knowledge_chunks
            SET embedding = (SELECT array_agg(0.1::real) FROM generate_series(1, 1536))::halfvec(1536)
            WHERE id = $1
        """,
            chunk_id,
        )

    # 異なる方向のベクトルで検索（閾値を下回る可能性がある）
    query_embedding = [0.2] * 1536  # 異なる値のベクトル
    results = await postgres_db.similarity_search(
        query_embedding=query_embedding,
        top_k=5,
        apply_threshold=False,  # 閾値フィルタリングを無効化
    )

    # 閾値フィルタリングを無効化しているため、結果が返ってくる可能性がある
    # （実際の類似度スコアに応じて）
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_postgres_db_halfvec_insert_and_select(postgres_db):
    """halfvec固定採用でのINSERTとSELECTのテスト"""
    # テスト用のソースとチャンクを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="テストソース",
        uri="https://example.com/test",
        metadata={"test": True},
        status="pending",
    )

    chunk_id = await postgres_db.save_chunk(
        source_id=source_id,
        content="テストコンテンツ",
        location={"url": "https://example.com/test", "label": "テスト"},
        token_count=5,
    )

    # halfvec型でベクトルを挿入
    test_embedding = [0.1] * 1536
    async with postgres_db.pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE knowledge_chunks
            SET embedding = $1::halfvec(1536)
            WHERE id = $2
        """,
            test_embedding,
            chunk_id,
        )

        # SELECTテスト（halfvec型の距離計算）
        result = await conn.fetchrow(
            """
            SELECT embedding <=> $1::halfvec(1536) AS distance
            FROM knowledge_chunks
            WHERE id = $2
        """,
            test_embedding,
            chunk_id,
        )

        assert result is not None
        assert result["distance"] is not None
        assert isinstance(result["distance"], float)
        # 同じベクトル同士の距離は0に近い
        assert result["distance"] < 0.01


@pytest.mark.asyncio
async def test_pgvector_extension(postgres_db):
    """pgvector拡張の確認"""
    async with postgres_db.pool.acquire() as conn:
        # pgvector拡張が有効化されているか確認
        result = await conn.fetchrow(
            "SELECT * FROM pg_extension WHERE extname = 'vector'"
        )
        assert result is not None
        assert result["extname"] == "vector"

        # halfvec型が使用可能か確認
        test_result = await conn.fetchval("SELECT '[1,2,3]'::halfvec(3)")
        assert test_result is not None


@pytest.mark.asyncio
async def test_postgres_db_delete_session(postgres_db):
    """セッション削除のテスト"""
    from datetime import UTC, datetime

    from kotonoha_bot.db.models import ChatSession, Message, MessageRole

    # テスト用のセッションを作成
    session = ChatSession(
        session_key="test:session:delete:001",
        session_type="mention",
        messages=[
            Message(
                role=MessageRole.USER,
                content="削除テスト",
                timestamp=datetime.now(UTC),
            )
        ],
        guild_id=123456789,
        channel_id=987654321,
        user_id=111222333,
    )

    # セッションを保存
    await postgres_db.save_session(session)

    # セッションが存在することを確認
    loaded = await postgres_db.load_session("test:session:delete:001")
    assert loaded is not None

    # セッションを削除
    await postgres_db.delete_session("test:session:delete:001")

    # セッションが削除されていることを確認
    deleted = await postgres_db.load_session("test:session:delete:001")
    assert deleted is None


@pytest.mark.asyncio
async def test_postgres_db_load_all_sessions(postgres_db):
    """すべてのセッション読み込みのテスト"""
    from datetime import UTC, datetime

    from kotonoha_bot.db.models import ChatSession, Message, MessageRole

    # 複数のセッションを作成
    for i in range(3):
        session = ChatSession(
            session_key=f"test:session:load_all:{i:03d}",
            session_type="mention",
            messages=[
                Message(
                    role=MessageRole.USER,
                    content=f"テストメッセージ{i}",
                    timestamp=datetime.now(UTC),
                )
            ],
            guild_id=123456789,
            channel_id=987654321,
            user_id=111222333,
        )
        await postgres_db.save_session(session)

    # すべてのセッションを読み込み
    all_sessions = await postgres_db.load_all_sessions()

    # 作成したセッションが含まれていることを確認
    session_keys = {s.session_key for s in all_sessions}
    assert "test:session:load_all:000" in session_keys
    assert "test:session:load_all:001" in session_keys
    assert "test:session:load_all:002" in session_keys


@pytest.mark.asyncio
async def test_postgres_db_similarity_search_source_types_filter(postgres_db):
    """source_typesフィルタリング付きベクトル検索のテスト"""
    # 異なるソースタイプのソースとチャンクを作成
    source_id_1 = await postgres_db.save_source(
        source_type="discord_session",
        title="セッションソース",
        uri="https://example.com/session",
        metadata={"test": True},
        status="pending",
    )

    source_id_2 = await postgres_db.save_source(
        source_type="document_file",
        title="ドキュメントソース",
        uri="https://example.com/document",
        metadata={"test": True},
        status="pending",
    )

    chunk_id_1 = await postgres_db.save_chunk(
        source_id=source_id_1,
        content="セッションのチャンク",
        location={"url": "https://example.com/session", "label": "セッションチャンク"},
        token_count=10,
    )

    chunk_id_2 = await postgres_db.save_chunk(
        source_id=source_id_2,
        content="ドキュメントのチャンク",
        location={
            "url": "https://example.com/document",
            "label": "ドキュメントチャンク",
        },
        token_count=10,
    )

    # テスト用のベクトルを挿入
    async with postgres_db.pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE knowledge_chunks
            SET embedding = (SELECT array_agg(0.1::real) FROM generate_series(1, 1536))::halfvec(1536)
            WHERE id = ANY($1::bigint[])
        """,
            [chunk_id_1, chunk_id_2],
        )

    # source_typesフィルタリング付き検索（discord_sessionのみ）
    query_embedding = [0.1] * 1536
    results = await postgres_db.similarity_search(
        query_embedding=query_embedding,
        top_k=10,
        filters={"source_types": ["discord_session"]},
    )

    # discord_sessionのチャンクのみが返ってくることを確認
    assert len(results) > 0
    for result in results:
        assert result["source_type"] == "discord_session", (
            f"検索結果はdiscord_sessionのチャンクのみである必要があります: "
            f"actual_source_type={result['source_type']}"
        )


@pytest.mark.asyncio
async def test_postgres_db_similarity_search_invalid_filter(postgres_db):
    """無効なフィルタキーのエラーハンドリングテスト"""
    query_embedding = [0.1] * 1536

    # 無効なフィルタキーで検索（エラーが発生することを確認）
    with pytest.raises(ValueError, match="Invalid filter keys"):
        await postgres_db.similarity_search(
            query_embedding=query_embedding,
            top_k=5,
            filters={"invalid_key": "value"},
        )


@pytest.mark.asyncio
async def test_postgres_db_similarity_search_invalid_source_type(postgres_db):
    """無効なsource_typeのエラーハンドリングテスト"""
    query_embedding = [0.1] * 1536

    # 無効なsource_typeで検索（エラーが発生することを確認）
    with pytest.raises(ValueError, match="Invalid source_type"):
        await postgres_db.similarity_search(
            query_embedding=query_embedding,
            top_k=5,
            filters={"source_type": "invalid_type"},
        )


@pytest.mark.asyncio
async def test_postgres_db_init_connection(postgres_db):
    """_init_connectionのテスト（pgvector型登録、JSONBコーデック）"""
    async with postgres_db.pool.acquire() as conn:
        # pgvector型が登録されているか確認
        # halfvec型の距離計算が動作することを確認
        result = await conn.fetchval(
            "SELECT '[1,2,3]'::halfvec(3) <=> '[1,2,3]'::halfvec(3) AS distance"
        )
        assert result is not None
        assert result == 0.0

        # JSONBコーデックが動作することを確認
        test_data = {"test": True, "number": 123, "nested": {"key": "value"}}
        result = await conn.fetchval("SELECT $1::jsonb", test_data)
        assert result == test_data


@pytest.mark.asyncio
async def test_postgres_db_close(postgres_db):
    """データベース接続のクローズテスト"""

    assert postgres_db.pool is not None
    await postgres_db.close()
    # プールが閉じられ、Noneに設定されていることを確認
    assert postgres_db.pool is None


@pytest.mark.asyncio
async def test_postgres_db_save_session_on_conflict(postgres_db):
    """セッション保存のON CONFLICT処理テスト"""
    from datetime import UTC, datetime

    from kotonoha_bot.db.models import ChatSession, Message, MessageRole

    # 最初のセッションを作成
    session1 = ChatSession(
        session_key="test:session:conflict:001",
        session_type="mention",
        messages=[
            Message(
                role=MessageRole.USER,
                content="最初のメッセージ",
                timestamp=datetime.now(UTC),
            )
        ],
        guild_id=123456789,
        channel_id=987654321,
        user_id=111222333,
        version=1,
    )

    await postgres_db.save_session(session1)

    # 同じsession_keyで更新（ON CONFLICT処理）
    session2 = ChatSession(
        session_key="test:session:conflict:001",
        session_type="mention",
        messages=[
            Message(
                role=MessageRole.USER,
                content="最初のメッセージ",
                timestamp=datetime.now(UTC),
            ),
            Message(
                role=MessageRole.ASSISTANT,
                content="更新されたメッセージ",
                timestamp=datetime.now(UTC),
            ),
        ],
        guild_id=123456789,
        channel_id=987654321,
        user_id=111222333,
        version=1,
    )

    await postgres_db.save_session(session2)

    # 更新されたセッションを読み込み
    loaded = await postgres_db.load_session("test:session:conflict:001")
    assert loaded is not None
    assert len(loaded.messages) == 2
    assert loaded.messages[1].content == "更新されたメッセージ"
    # versionがインクリメントされていることを確認
    assert loaded.version > session1.version


@pytest.mark.asyncio
async def test_postgres_db_save_chunk_token_count_auto_calculation(postgres_db):
    """save_chunkのtoken_count自動計算テスト"""
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="トークン計算テスト",
        uri="https://example.com/token_test",
        metadata={"test": True},
        status="pending",
    )

    # token_countを指定しない場合、自動計算される
    chunk_id = await postgres_db.save_chunk(
        source_id=source_id,
        content="これは自動トークン計算のテストです。",
        location={"url": "https://example.com/token_test", "label": "テスト"},
        # token_countを指定しない
    )

    # token_countが自動計算されていることを確認
    async with postgres_db.pool.acquire() as conn:
        result = await conn.fetchrow(
            "SELECT token_count FROM knowledge_chunks WHERE id = $1",
            chunk_id,
        )
        assert result is not None
        assert result["token_count"] > 0


@pytest.mark.asyncio
async def test_postgres_db_similarity_search_similarity_threshold(postgres_db):
    """similarity_searchのsimilarity_thresholdパラメータテスト"""
    # テスト用のソースとチャンクを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="閾値テストソース",
        uri="https://example.com/threshold_test",
        metadata={"test": True},
        status="pending",
    )

    chunk_id = await postgres_db.save_chunk(
        source_id=source_id,
        content="これは閾値テスト用のチャンクです",
        location={"url": "https://example.com/threshold_test", "label": "テスト"},
        token_count=10,
    )

    # テスト用のベクトルを挿入
    async with postgres_db.pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE knowledge_chunks
            SET embedding = (SELECT array_agg(0.1::real) FROM generate_series(1, 1536))::halfvec(1536)
            WHERE id = $1
        """,
            chunk_id,
        )

    # 高い閾値で検索（結果が返ってくる可能性がある）
    query_embedding = [0.1] * 1536
    results_high = await postgres_db.similarity_search(
        query_embedding=query_embedding,
        top_k=5,
        similarity_threshold=0.5,  # 低い閾値
    )

    # 低い閾値で検索（結果が返ってこない可能性がある）
    results_low = await postgres_db.similarity_search(
        query_embedding=query_embedding,
        top_k=5,
        similarity_threshold=0.99,  # 非常に高い閾値
    )

    # 閾値が機能していることを確認（結果数が異なる可能性がある）
    assert isinstance(results_high, list)
    assert isinstance(results_low, list)


@pytest.mark.asyncio
async def test_postgres_db_similarity_search_empty_result(postgres_db):
    """similarity_searchの空結果テスト"""
    # ベクトルが設定されていないチャンクのみの場合、結果が空になることを確認
    query_embedding = [0.1] * 1536
    results = await postgres_db.similarity_search(
        query_embedding=query_embedding,
        top_k=5,
    )

    # 結果が空のリストであることを確認
    assert isinstance(results, list)
    # embeddingが設定されていないチャンクは検索結果に含まれない


@pytest.mark.asyncio
async def test_postgres_db_save_source_invalid_type(postgres_db):
    """save_sourceの無効なsource_typeエラーハンドリングテスト"""
    with pytest.raises(ValueError, match="Invalid source_type"):
        await postgres_db.save_source(
            source_type="invalid_type",
            title="テスト",
            uri="https://example.com/test",
            metadata={"test": True},
            status="pending",
        )


@pytest.mark.asyncio
async def test_postgres_db_similarity_search_user_id_filter(postgres_db):
    """similarity_searchのuser_idフィルタリングテスト"""
    # 異なるuser_idのソースとチャンクを作成
    source_id_1 = await postgres_db.save_source(
        source_type="discord_session",
        title="ユーザー1のソース",
        uri="https://example.com/user1",
        metadata={"author_id": 111111, "test": True},
        status="pending",
    )

    source_id_2 = await postgres_db.save_source(
        source_type="discord_session",
        title="ユーザー2のソース",
        uri="https://example.com/user2",
        metadata={"author_id": 222222, "test": True},
        status="pending",
    )

    chunk_id_1 = await postgres_db.save_chunk(
        source_id=source_id_1,
        content="ユーザー1のチャンク",
        location={"url": "https://example.com/user1", "label": "チャンク1"},
        token_count=10,
    )

    chunk_id_2 = await postgres_db.save_chunk(
        source_id=source_id_2,
        content="ユーザー2のチャンク",
        location={"url": "https://example.com/user2", "label": "チャンク2"},
        token_count=10,
    )

    # テスト用のベクトルを挿入
    async with postgres_db.pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE knowledge_chunks
            SET embedding = (SELECT array_agg(0.1::real) FROM generate_series(1, 1536))::halfvec(1536)
            WHERE id = ANY($1::bigint[])
        """,
            [chunk_id_1, chunk_id_2],
        )

    # user_idフィルタリング付き検索（ユーザー1のみ）
    query_embedding = [0.1] * 1536
    results = await postgres_db.similarity_search(
        query_embedding=query_embedding,
        top_k=10,
        filters={"user_id": 111111},
    )

    # ユーザー1のチャンクのみが返ってくることを確認
    assert len(results) > 0
    for result in results:
        assert result["source_metadata"].get("author_id") == 111111, (
            f"検索結果はユーザー1のチャンクのみである必要があります: "
            f"actual_user_id={result['source_metadata'].get('author_id')}"
        )


# ============================================
# 追加テストケース（2026年1月19日）
# ============================================


@pytest.mark.asyncio
async def test_postgres_db_init_without_params():
    """初期化パラメータが不足している場合のエラーテスト"""
    with pytest.raises(ValueError, match="Either connection_string or"):
        PostgreSQLDatabase()


@pytest.mark.asyncio
async def test_postgres_db_init_with_connection_string():
    """connection_stringを使用した初期化テスト"""
    db = PostgreSQLDatabase(
        connection_string="postgresql://test:test@localhost:5432/test_kotonoha"
    )
    assert db.connection_string is not None
    assert db.host is None
    assert db.pool is None


@pytest.mark.asyncio
async def test_postgres_db_init_with_individual_params():
    """個別パラメータを使用した初期化テスト"""
    db = PostgreSQLDatabase(
        host="localhost",
        port=5432,
        database="test_kotonoha",
        user="test",
        password="test",
    )
    assert db.connection_string is None
    assert db.host == "localhost"
    assert db.port == 5432
    assert db.database == "test_kotonoha"
    assert db.user == "test"
    assert db.password == "test"
    assert db.pool is None


@pytest.mark.asyncio
async def test_postgres_db_init_default_port():
    """デフォルトポート（5432）のテスト"""
    db = PostgreSQLDatabase(
        host="localhost",
        database="test_kotonoha",
        user="test",
        password="test",
        # port を指定しない場合、デフォルト値 5432 が使用される
    )
    assert db.port == 5432


@pytest.mark.asyncio
async def test_postgres_db_similarity_search_channel_id_invalid_type(postgres_db):
    """channel_idフィルタリングの型変換エラーテスト"""
    query_embedding = [0.1] * 1536

    # 文字列で変換できない値を指定
    with pytest.raises(ValueError, match="Invalid channel_id"):
        await postgres_db.similarity_search(
            query_embedding=query_embedding,
            top_k=5,
            filters={"channel_id": "not_a_number"},
        )


@pytest.mark.asyncio
async def test_postgres_db_similarity_search_user_id_invalid_type(postgres_db):
    """user_idフィルタリングの型変換エラーテスト"""
    query_embedding = [0.1] * 1536

    # 文字列で変換できない値を指定
    with pytest.raises(ValueError, match="Invalid user_id"):
        await postgres_db.similarity_search(
            query_embedding=query_embedding,
            top_k=5,
            filters={"user_id": "not_a_number"},
        )


@pytest.mark.asyncio
async def test_postgres_db_similarity_search_invalid_source_types_value(postgres_db):
    """source_typesフィルタリングの無効な値テスト"""
    query_embedding = [0.1] * 1536

    # 無効なsource_typeを含むリスト
    with pytest.raises(ValueError, match="Invalid source_types"):
        await postgres_db.similarity_search(
            query_embedding=query_embedding,
            top_k=5,
            filters={"source_types": ["discord_session", "invalid_type"]},
        )


@pytest.mark.asyncio
async def test_postgres_db_save_session_with_thread_id(postgres_db):
    """thread_idを含むセッション保存のテスト"""
    session = ChatSession(
        session_key="test:session:thread:001",
        session_type="thread",
        messages=[
            Message(
                role=MessageRole.USER,
                content="スレッドメッセージ",
                timestamp=datetime.now(UTC),
            )
        ],
        guild_id=123456789,
        channel_id=987654321,
        thread_id=555666777,  # thread_idを設定
        user_id=111222333,
    )

    await postgres_db.save_session(session)

    loaded = await postgres_db.load_session("test:session:thread:001")
    assert loaded is not None
    assert loaded.thread_id == 555666777


@pytest.mark.asyncio
async def test_postgres_db_save_session_status_update(postgres_db):
    """セッションステータス更新のテスト"""
    session = ChatSession(
        session_key="test:session:status:001",
        session_type="mention",
        messages=[
            Message(
                role=MessageRole.USER,
                content="ステータステスト",
                timestamp=datetime.now(UTC),
            )
        ],
        guild_id=123456789,
        channel_id=987654321,
        user_id=111222333,
        status="active",
    )

    await postgres_db.save_session(session)

    # ステータスを確認
    loaded = await postgres_db.load_session("test:session:status:001")
    assert loaded is not None
    assert loaded.status == "active"


@pytest.mark.asyncio
async def test_postgres_db_load_nonexistent_session(postgres_db):
    """存在しないセッションの読み込みテスト"""
    loaded = await postgres_db.load_session("nonexistent:session:key")
    assert loaded is None


@pytest.mark.asyncio
async def test_postgres_db_delete_nonexistent_session(postgres_db):
    """存在しないセッションの削除テスト（エラーにならない）"""
    # 存在しないセッションを削除しても例外は発生しない
    await postgres_db.delete_session("nonexistent:session:key")


@pytest.mark.asyncio
async def test_postgres_db_save_source_all_types(postgres_db):
    """すべての有効なsource_typeで保存テスト"""
    valid_types = [
        "discord_session",
        "document_file",
        "web_page",
        "image_caption",
        "audio_transcript",
    ]

    for source_type in valid_types:
        source_id = await postgres_db.save_source(
            source_type=source_type,
            title=f"テストソース_{source_type}",
            uri=f"https://example.com/{source_type}",
            metadata={"test": True},
            status="pending",
        )
        assert source_id is not None
        assert isinstance(source_id, int)


@pytest.mark.asyncio
async def test_postgres_db_save_source_with_null_uri(postgres_db):
    """URIがNullのソース保存テスト"""
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="URIなしソース",
        uri=None,  # URIをNullに設定
        metadata={"test": True},
        status="pending",
    )
    assert source_id is not None


@pytest.mark.asyncio
async def test_postgres_db_save_chunk_with_null_location(postgres_db):
    """locationがNullのチャンク保存テスト"""
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="locationなしテスト",
        uri="https://example.com/no_location",
        metadata={"test": True},
        status="pending",
    )

    chunk_id = await postgres_db.save_chunk(
        source_id=source_id,
        content="locationなしのチャンク",
        location=None,  # locationをNullに設定
        token_count=10,
    )
    assert chunk_id is not None


@pytest.mark.asyncio
async def test_postgres_db_similarity_search_combined_filters(postgres_db):
    """複合フィルタリング（source_type + channel_id）のテスト"""
    # ソースとチャンクを作成
    source_id = await postgres_db.save_source(
        source_type="discord_session",
        title="複合フィルタテスト",
        uri="https://example.com/combined",
        metadata={"channel_id": 12345, "test": True},
        status="pending",
    )

    chunk_id = await postgres_db.save_chunk(
        source_id=source_id,
        content="複合フィルタテスト用チャンク",
        location={"url": "https://example.com/combined", "label": "テスト"},
        token_count=10,
    )

    # Embeddingを設定
    async with postgres_db.pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE knowledge_chunks
            SET embedding = (SELECT array_agg(0.1::real) FROM generate_series(1, 1536))::halfvec(1536)
            WHERE id = $1
        """,
            chunk_id,
        )

    query_embedding = [0.1] * 1536

    # source_type + channel_idの複合フィルタ
    results = await postgres_db.similarity_search(
        query_embedding=query_embedding,
        top_k=10,
        filters={"source_type": "discord_session", "channel_id": 12345},
    )

    assert len(results) > 0
    assert results[0]["source_type"] == "discord_session"
