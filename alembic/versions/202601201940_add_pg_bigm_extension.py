"""add_pg_bigm_extension.

Revision ID: 202601201940
Revises: 202601182039
Create Date: 2026-01-20 19:40:10.268271

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "202601201940"
down_revision: str | Sequence[str] | None = "202601182039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # pg_bigm拡張の有効化（利用できない場合は警告を出して続行）
    op.execute("""
        DO $$ BEGIN
            CREATE EXTENSION IF NOT EXISTS pg_bigm;
        EXCEPTION
            WHEN OTHERS THEN
                -- 開発環境などでpg_bigm拡張が利用できない場合は警告を出して続行
                RAISE WARNING 'pg_bigm extension could not be enabled: %', SQLERRM;
        END $$;
    """)

    # knowledge_chunks.contentにGINインデックス（pg_bigm）を追加
    # pg_bigm拡張が利用できない場合はスキップ
    op.execute("""
        DO $$ BEGIN
            CREATE INDEX IF NOT EXISTS idx_chunks_content_bigm
            ON knowledge_chunks
            USING gin (content gin_bigm_ops);
        EXCEPTION
            WHEN OTHERS THEN
                -- pg_bigm拡張が利用できない場合はインデックス作成をスキップ
                RAISE WARNING 'pg_bigm index could not be created: %', SQLERRM;
        END $$;
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # インデックスの削除
    op.execute("DROP INDEX IF EXISTS idx_chunks_content_bigm")

    # pg_bigm拡張の削除（注意: 他のテーブルで使用されている場合はエラーになる）
    op.execute("""
        DO $$ BEGIN
            DROP EXTENSION IF EXISTS pg_bigm;
        EXCEPTION
            WHEN OTHERS THEN
                -- エラーを無視（拡張が存在しない場合など）
                NULL;
        END $$;
    """)
