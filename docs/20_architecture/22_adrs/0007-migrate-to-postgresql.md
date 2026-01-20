# ADR-0007: PostgreSQL への移行

**ステータス**: Accepted

**日付**: 2026-01-16

**決定者**: kotonoha-bot 開発チーム

## コンテキスト

現在の実装では、`aiosqlite` を使用して SQLite データベースにアクセスしています（ADR-0006 参照）。しかし、将来的な機能拡張として以下の要件が発生しました:

1. **ベクトル検索・RAG機能**: ナレッジベース機能でセマンティック検索を実装する必要がある
2. **高性能なベクトル検索**: 会話要約から意味的に近い情報を高速に検索する必要がある
3. **スケーラビリティ**: 将来的なデータ増加や機能拡張に対応できるデータベースが必要
4. **非同期対応**: Discord Bot の非同期処理と整合性のあるデータベースアクセスが必要

### 現在の実装状況

- `src/kotonoha_bot/db/sqlite.py`: `aiosqlite` を使用した SQLite 実装
- `docs/implementation/knowledge-base-design.md`: ナレッジベース機能の設計（要約保存のみ）
- ベクトル検索機能は未実装

### 課題

SQLite でベクトル検索を実装する場合の制約:

1. **ベクトル検索の性能**: Python 側で類似度計算を行う必要があり、大規模データでは非効率
2. **インデックス機能**: ベクトル専用のインデックスが標準では利用できない
3. **拡張性**: sqlite-vss などの拡張を使用する場合、C拡張の管理が必要で複雑
4. **スケーラビリティ**: データが増加した場合の性能劣化が懸念される

## 決定

**PostgreSQL + pgvector への移行**を実施する。

### 移行方針

1. **データベース抽象化レイヤーの追加**: SQLite と PostgreSQL の両方に対応できる抽象化レイヤーを実装
2. **段階的移行**: 既存の SQLite 実装を維持しつつ、PostgreSQL 実装を追加
3. **設定による切り替え**: 環境変数でデータベースタイプを選択可能にする
4. **pgvector 拡張の活用**: ネイティブなベクトル検索機能を利用

## 理由

### 1. ネイティブベクトル検索（pgvector）

**pgvector 拡張の利点**:

- PostgreSQL の拡張として動作し、ネイティブなベクトル型をサポート
- IVFFlat や HNSW などの高性能インデックスが利用可能
- SQL クエリ内で直接ベクトル演算が可能（`<=>`, `<->` 演算子）
- ベクトル検索の性能が Python 側計算よりも大幅に高速

**実装例**:

```sql
-- ベクトル型の直接定義
CREATE TABLE knowledge_chunks (
    chunk_id TEXT PRIMARY KEY,
    text_content TEXT NOT NULL,
    embedding vector(1536),  -- 直接ベクトル型
    channel_id INTEGER
);

-- 高速なベクトルインデックス
CREATE INDEX ON knowledge_chunks 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- SQL クエリ内で直接検索
SELECT chunk_id, text_content,
       1 - (embedding <=> $1::vector) AS similarity
FROM knowledge_chunks
WHERE channel_id = $2
ORDER BY embedding <=> $1::vector
LIMIT 10;
```

### 2. 非同期対応（asyncpg）

**asyncpg の利点**:

- 純粋な非同期実装で、Discord Bot の非同期処理と完全に整合
- 接続プール管理が容易
- 高いパフォーマンス（C拡張ベース）
- `aiosqlite` と同様の使い勝手

**実装例**:

```python
import asyncpg

class PostgreSQLDatabase:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.pool: asyncpg.Pool | None = None
    
    async def initialize(self):
        self.pool = await asyncpg.create_pool(
            self.connection_string,
            min_size=5,
            max_size=20
        )
    
    async def similarity_search(
        self,
        query_embedding: list[float],
        channel_id: int,
        top_k: int = 10
    ) -> list[dict]:
        async with self.pool.acquire() as conn:
            results = await conn.fetch("""
                SELECT chunk_id, text_content,
                       1 - (embedding <=> $1::vector) AS similarity
                FROM knowledge_chunks
                WHERE channel_id = $2
                ORDER BY embedding <=> $1::vector
                LIMIT $3
            """, query_embedding, channel_id, top_k)
            return [dict(row) for row in results]
```

### 3. スケーラビリティ

**PostgreSQL の利点**:

- 大規模データに対応可能
- 同時書き込みに強い
- レプリケーション対応（将来の拡張）
- パーティショニング機能（時系列データの効率的管理）

### 4. 高度な機能

**追加で利用可能な機能**:

- **全文検索**: PostgreSQL の FTS（GIN インデックス）で高速な全文検索
- **JSON 操作**: JSONB 型で柔軟なメタデータ管理
- **複雑なクエリ**: ウィンドウ関数、CTE など高度な SQL 機能
- **トランザクション**: ACID 保証と同時実行制御

### 5. 将来の拡張性

**将来の機能拡張に対応**:

- マルチサーバー対応（レプリケーション）
- 読み取り専用レプリカでの負荷分散
- 時系列データのパーティショニング
- より高度な分析機能

## 代替案

### 代替案 A: SQLite 継続 + Python 側ベクトル検索

**メリット**:

- 既存の実装をそのまま使用できる
- 追加のインフラが不要
- シンプルな運用

**デメリット**:

- ベクトル検索の性能が劣る（Python 側で計算）
- 大規模データでは非効率（全候補をメモリに読み込む必要）
- ベクトル専用インデックスが利用できない
- スケーラビリティに限界がある

**採用しなかった理由**:

- **ベクトル検索の性能を優先**
- 将来的なデータ増加を考慮
- RAG 機能の本格的な実装には不十分

---

### 代替案 B: SQLite + sqlite-vss

**メリット**:

- SQLite の拡張として動作
- 既存の SQLite DB と統合可能

**デメリット**:

- C拡張の管理が必要（セットアップが複雑）
- `aiosqlite` から直接使用できない可能性
- Python ラッパーの追加が必要
- ドキュメントやコミュニティサポートが限定的
- スケーラビリティに限界がある

**採用しなかった理由**:

- **セットアップの複雑さと将来性を考慮**
- PostgreSQL の方が標準的でサポートが充実
- 将来的な拡張性を優先

---

### 代替案 C: Chroma（別プロセス）

**メリット**:

- ベクトル検索に特化したデータベース
- 軽量で組み込み可能
- 柔軟な検索機能

**デメリット**:

- 別プロセスが必要（HTTP API 経由）
- 既存の SQLite データとの統合が複雑
- リレーショナルデータの管理が不向き
- 運用が複雑になる（2つのデータベースを管理）

**採用しなかった理由**:

- **データベースの一元管理を優先**
- リレーショナルデータとベクトルデータを同じ DB で管理したい
- 運用の複雑さを避けたい

---

### 代替案 D: ハイブリッド方式（SQLite + PostgreSQL）

**メリット**:

- 既存の SQLite 実装を維持
- ベクトル検索のみ PostgreSQL を使用
- 段階的な移行が可能

**デメリット**:

- 2つのデータベースを管理する必要がある
- データの整合性管理が複雑
- 運用コストが増加
- トランザクションが跨れない

**採用しなかった理由**:

- **データベースの一元管理を優先**
- 運用の複雑さを避けたい
- 将来的には完全移行が必要になる

---

## 結果

### メリット

1. **高性能なベクトル検索**: pgvector によるネイティブなベクトル検索
2. **非同期対応**: asyncpg による完全な非同期実装
3. **スケーラビリティ**: 大規模データや将来の拡張に対応
4. **標準的な技術**: 広く使われている技術でサポートが充実
5. **高度な機能**: 全文検索、JSON 操作、パーティショニングなど

### デメリット

1. **セットアップの複雑さ**: 別プロセス（PostgreSQL コンテナ）が必要
2. **リソース消費**: メモリ・ストレージの消費が増加
3. **運用コスト**: バックアップ戦略の見直しが必要
4. **移行コスト**: 既存データの移行が必要

### トレードオフ

- **シンプルさ vs 機能性**: 機能性と将来性を優先し、セットアップの複雑さを受け入れる
- **リソース vs 性能**: リソース消費を増やして、高性能なベクトル検索を実現
- **移行コスト vs 長期的メリット**: 短期的な移行コストを払って、長期的な拡張性を確保

### リソース要件

**PostgreSQL 追加時のリソース要件**:

| リソース | 最小 | 推奨 | 現在のBot |
|---------|------|------|----------|
| **メモリ** | 1GB | 2GB | 512MB |
| **ストレージ** | 500MB | 1GB | 100MB |
| **CPU** | 低負荷 | 中負荷 | 低負荷 |

**判断基準**:

- NAS 全体メモリの 25% 以上（2GB 以上）が利用可能
- ストレージに 1GB 以上の空き容量
- アイドル時 CPU 使用率が 20% 以下
- Docker 環境で運用可能

### 実装への影響

#### 1. データベース抽象化レイヤーの追加

```python
# src/kotonoha_bot/db/base.py
from abc import ABC, abstractmethod
from typing import Protocol

class DatabaseProtocol(Protocol):
    """データベースインターフェース"""
    async def initialize(self) -> None: ...
    async def save_session(self, session: ChatSession) -> None: ...
    async def load_session(self, session_key: str) -> ChatSession | None: ...
    async def similarity_search(
        self,
        query_embedding: list[float],
        channel_id: int | None,
        top_k: int
    ) -> list[dict]: ...
```

#### 2. PostgreSQL 実装の追加

```python
# src/kotonoha_bot/db/postgres.py
import asyncpg
from .base import DatabaseProtocol

class PostgreSQLDatabase(DatabaseProtocol):
    """PostgreSQL データベース（非同期）"""
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.pool: asyncpg.Pool | None = None
    
    async def initialize(self) -> None:
        """データベースの初期化"""
        self.pool = await asyncpg.create_pool(
            self.connection_string,
            min_size=5,
            max_size=20
        )
        # pgvector 拡張を有効化
        async with self.pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await self._create_tables(conn)
```

#### 3. 設定による切り替え

```python
# config.py
DATABASE_TYPE: str = os.getenv("DATABASE_TYPE", "sqlite")  # 'sqlite' or 'postgres'
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://kotonoha:password@localhost:5433/kotonoha"
)

# main.py
if Config.DATABASE_TYPE == "postgres":
    db = PostgreSQLDatabase(Config.DATABASE_URL)
else:
    db = SQLiteDatabase(Config.DATABASE_PATH)
```

#### 4. docker-compose.yml の更新

```yaml
services:
  kotonoha-bot:
    # ... 既存の設定 ...
    depends_on:
      - postgres
    environment:
      - DATABASE_TYPE=postgres
      - DATABASE_URL=postgresql://kotonoha:${POSTGRES_PASSWORD}@postgres:5433/kotonoha

  postgres:
    image: pgvector/pgvector:0.8.1-pg18
    container_name: kotonoha-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: kotonoha
      POSTGRES_USER: kotonoha
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - kotonoha-network
    deploy:
      resources:
        limits:
          memory: 1G

  pgadmin:
    image: dpage/pgadmin4:latest
    container_name: kotonoha-pgadmin
    restart: unless-stopped
    environment:
      PGADMIN_DEFAULT_EMAIL: ${PGADMIN_EMAIL:-admin@kotonoha.local}
      PGADMIN_DEFAULT_PASSWORD: ${PGADMIN_PASSWORD}
      PGADMIN_CONFIG_SERVER_MODE: 'False'
      PGADMIN_CONFIG_MASTER_PASSWORD_REQUIRED: 'False'
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

**pgAdmin の初期設定**:

1. ブラウザで `http://localhost:5050` にアクセス
2. ログイン（`PGADMIN_DEFAULT_EMAIL` と `PGADMIN_DEFAULT_PASSWORD`）
3. サーバーを追加:
   - **名前**: `kotonoha-postgres`（任意）
   - **ホスト名/アドレス**: `postgres`（Docker サービス名）
   - **ポート**: `5433`（ホスト側、コンテナ内は5432）
   - **メンテナンスデータベース**: `kotonoha`
   - **ユーザー名**: `kotonoha`
   - **パスワード**: `${POSTGRES_PASSWORD}` の値

#### 5. 依存関係の追加

```toml
# pyproject.toml
dependencies = [
    # ... 既存の依存関係 ...
    "asyncpg>=0.29.0",
]
```

### 移行計画

#### Phase 1: データベース抽象化レイヤーの実装

1. `DatabaseProtocol` インターフェースの定義
2. 既存の `SQLiteDatabase` を `DatabaseProtocol` に適合
3. 設定によるデータベース選択機能の実装

#### Phase 2: PostgreSQL 実装の追加

1. `PostgreSQLDatabase` クラスの実装
2. pgvector 拡張のセットアップ
3. テーブル定義とインデックスの作成
4. 基本的な CRUD 操作の実装

#### Phase 3: ベクトル検索機能の実装

1. `similarity_search` メソッドの実装
2. ベクトルインデックスの最適化
3. メタデータフィルタリング機能

#### Phase 4: データ移行

1. SQLite から PostgreSQL へのデータ移行ツールの作成
2. 移行スクリプトの実行
3. データ整合性の確認

#### Phase 5: テストと最適化

1. パフォーマンステスト
2. インデックスの最適化
3. 接続プールの調整

### リスクと対策

#### リスク 1: リソース不足

**リスク**: PostgreSQL コンテナが NAS のリソースを圧迫する

**対策**:

- リソース制限を適切に設定（`docker-compose.yml`）
- メモリ使用量を監視
- 必要に応じてリソース制限を調整

#### リスク 2: データ移行の失敗

**リスク**: SQLite から PostgreSQL への移行時にデータ損失が発生する

**対策**:

- 移行前に SQLite データベースのバックアップを取得
- 移行ツールのテストを十分に実施
- 移行後のデータ整合性チェックを実装

#### リスク 3: パフォーマンスの劣化

**リスク**: PostgreSQL への移行により、既存機能のパフォーマンスが劣化する

**対策**:

- パフォーマンステストを実施
- インデックスの最適化
- 接続プールの適切な設定

#### リスク 4: 運用の複雑化

**リスク**: PostgreSQL の運用が複雑になり、運用コストが増加する

**対策**:

- 適切なドキュメントの整備
- 自動バックアップの設定
- ヘルスチェックの実装

### 将来の拡張

PostgreSQL への移行により、以下の機能拡張が容易になります:

1. **レプリケーション**: 読み取り専用レプリカでの負荷分散
2. **パーティショニング**: 時系列データの効率的管理
3. **全文検索**: PostgreSQL の FTS 機能の活用
4. **分析機能**: ウィンドウ関数や CTE を活用した高度な分析

## 参考資料

- [ADR-0003: SQLite の採用](./0003-use-sqlite.md)
- [ADR-0006: aiosqlite への移行](./0006-migrate-to-aiosqlite.md)
- [pgvector Documentation](https://github.com/pgvector/pgvector)
- [asyncpg Documentation](https://magicstack.github.io/asyncpg/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [knowledge-base-design.md](../../implementation/knowledge-base-design.md)

---

**作成日**: 2026 年 1 月 16 日
**最終更新日**: 2026 年 1 月 16 日
