"""Initial schema

Revision ID: ca650c17adda
Revises: 
Create Date: 2026-01-18 20:39:25.053404

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'ca650c17adda'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
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

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE session_status_enum AS ENUM (
                'active',
                'archived'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE source_status_enum AS ENUM (
                'pending',
                'processing',
                'completed',
                'partial',
                'failed'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # sessions テーブル
    op.create_table(
        'sessions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('session_key', sa.Text(), nullable=False),
        sa.Column('session_type', sa.Text(), nullable=False),
        sa.Column('messages', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
        sa.Column('status', postgresql.ENUM('active', 'archived', name='session_status_enum', create_type=False), server_default='active', nullable=True),
        sa.Column('guild_id', sa.BigInteger(), nullable=True),
        sa.Column('channel_id', sa.BigInteger(), nullable=True),
        sa.Column('thread_id', sa.BigInteger(), nullable=True),
        sa.Column('user_id', sa.BigInteger(), nullable=True),
        sa.Column('version', sa.Integer(), server_default='1', nullable=True),
        sa.Column('last_archived_message_index', sa.Integer(), server_default='0', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('last_active_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_key')
    )

    # knowledge_sources テーブル
    op.create_table(
        'knowledge_sources',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('type', postgresql.ENUM('discord_session', 'document_file', 'web_page', 'image_caption', 'audio_transcript', name='source_type_enum', create_type=False), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('uri', sa.Text(), nullable=True),
        sa.Column('status', postgresql.ENUM('pending', 'processing', 'completed', 'partial', 'failed', name='source_status_enum', create_type=False), server_default='pending', nullable=True),
        sa.Column('error_code', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # knowledge_chunks テーブル
    # ⚠️ 重要: embedding カラムは halfvec(1536) 型のため、Alembicでは直接サポートされない
    # テーブル作成時に直接SQLで実行する
    op.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_chunks (
            id BIGSERIAL PRIMARY KEY,
            source_id BIGINT NOT NULL REFERENCES knowledge_sources(id) ON DELETE CASCADE,
            content TEXT NOT NULL,
            embedding halfvec(1536),
            location JSONB DEFAULT '{}'::jsonb,
            token_count INT,
            retry_count INT DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # knowledge_chunks_dlq テーブル
    op.create_table(
        'knowledge_chunks_dlq',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('original_chunk_id', sa.BigInteger(), nullable=True),
        sa.Column('source_id', sa.BigInteger(), nullable=True),
        sa.Column('source_title', sa.Text(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('error_code', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), server_default='0', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('last_retry_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # インデックスの作成
    op.create_index('idx_sessions_status', 'sessions', ['status'])
    op.create_index('idx_sessions_last_active_at', 'sessions', ['last_active_at'])
    op.create_index('idx_sessions_channel_id', 'sessions', ['channel_id'])
    op.create_index('idx_sessions_archive_candidates', 'sessions', ['status', 'last_active_at'], postgresql_where=sa.text("status = 'active'"))

    op.create_index('idx_sources_metadata', 'knowledge_sources', ['metadata'], postgresql_using='gin')
    op.create_index('idx_sources_status', 'knowledge_sources', ['status'])
    op.create_index('idx_sources_type', 'knowledge_sources', ['type'])

    # HNSWインデックスは直接SQLで作成（Alembicでは直接サポートされない）
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_chunks_embedding 
        ON knowledge_chunks USING hnsw (embedding halfvec_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """)

    op.create_index('idx_chunks_source_id', 'knowledge_chunks', ['source_id'])
    op.create_index('idx_chunks_searchable', 'knowledge_chunks', ['source_id', 'created_at'], postgresql_where=sa.text('embedding IS NOT NULL AND token_count > 0'))
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_chunks_queue 
        ON knowledge_chunks(id)
        WHERE embedding IS NULL AND retry_count < 3;
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # インデックスの削除
    op.execute("DROP INDEX IF EXISTS idx_chunks_queue")
    op.drop_index('idx_chunks_searchable', table_name='knowledge_chunks')
    op.drop_index('idx_chunks_source_id', table_name='knowledge_chunks')
    op.execute("DROP INDEX IF EXISTS idx_chunks_embedding")

    op.drop_index('idx_sources_type', table_name='knowledge_sources')
    op.drop_index('idx_sources_status', table_name='knowledge_sources')
    op.drop_index('idx_sources_metadata', table_name='knowledge_sources')

    op.drop_index('idx_sessions_archive_candidates', table_name='sessions')
    op.drop_index('idx_sessions_channel_id', table_name='sessions')
    op.drop_index('idx_sessions_last_active_at', table_name='sessions')
    op.drop_index('idx_sessions_status', table_name='sessions')

    # テーブルの削除
    op.drop_table('knowledge_chunks_dlq')
    op.drop_table('knowledge_chunks')
    op.drop_table('knowledge_sources')
    op.drop_table('sessions')

    # ENUM型の削除
    op.execute("DROP TYPE IF EXISTS source_status_enum")
    op.execute("DROP TYPE IF EXISTS session_status_enum")
    op.execute("DROP TYPE IF EXISTS source_type_enum")

    # 拡張機能の削除
    op.execute("DROP EXTENSION IF EXISTS vector")
