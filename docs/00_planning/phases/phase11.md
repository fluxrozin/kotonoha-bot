# Phase 11: ハイブリッド検索の実装

**作成日**: 2026年1月19日  
**バージョン**: 1.0  
**対象プロジェクト**: kotonoha-bot v0.9.0  
**前提条件**: Phase 8（PostgreSQL + pgvector 実装）完了済み、全テスト通過

---

## 目次

1. [エグゼクティブサマリー](#1-エグゼクティブサマリー)
2. [目的とスコープ](#2-目的とスコープ)
3. [設計方針](#3-設計方針)
4. [実装ステップ](#4-実装ステップ)
5. [完了基準](#5-完了基準)
6. [テスト計画](#6-テスト計画)
7. [導入・デプロイ手順](#7-導入デプロイ手順)
8. [今後の改善計画](#8-今後の改善計画)

---

## 1. エグゼクティブサマリー

### 1.1 目的

Phase 8で実装したベクトル検索に加えて、pg_bigmを使用したキーワード検索を組み合わせたハイブリッド検索を実装し、検索品質を向上させる。

### 1.2 背景

ベクトル検索は「概念的な類似」には強いですが、「固有名詞（例：プロジェクトコード名、特定のエラーコード）」の完全一致検索には弱いです。日本語検索においては、pg_bigmを使用した2-gram（2文字単位）によるキーワード検索を組み合わせることで、検索精度を大幅に向上させることができます。

### 1.3 主要な実装項目

| 項目 | 内容 |
|------|------|
| pg_bigm拡張の有効化 | Dockerfile.postgresでカスタムイメージを作成 |
| ハイブリッド検索メソッド | ベクトル検索とキーワード検索を組み合わせた検索 |
| スコアリング機能 | ベクトル類似度とキーワードスコアを組み合わせたスコア計算 |
| インデックス最適化 | pg_bigm用のGINインデックスの追加 |

### 1.4 実装期間

約 2-3 日

---

## 2. 目的とスコープ

### 2.1 目的

1. **検索品質の向上**: 固有名詞や特定のキーワードを含む検索の精度向上
2. **日本語検索の最適化**: pg_bigmによる2-gram検索による日本語検索の高速化
3. **ハイブリッド検索の実現**: ベクトル検索とキーワード検索を組み合わせた統合検索

### 2.2 スコープ

- **pg_bigm拡張の有効化**: Dockerfile.postgresでカスタムイメージを作成
- **ハイブリッド検索メソッドの実装**: `PostgreSQLDatabase`クラスに`hybrid_search`メソッドを追加
- **スコアリング機能**: ベクトル類似度とキーワードスコアを組み合わせたスコア計算
- **インデックス最適化**: pg_bigm用のGINインデックスの追加（Alembicマイグレーション）

### 2.3 スコープ外

- **pg_trgmの実装**: 日本語検索においてはpg_bigmを採用（2文字の単語に対応）
- **tsvector（FTS）の実装**: オプションとして将来の拡張に備える（今回は実装しない）
- **Reranking機能**: Phase 12で実装予定

---

## 3. 設計方針

### 3.1 pg_bigmの採用理由

**pg_bigmの利点**:

- **2-gram（2文字単位）**: 日本語の多くは2文字以上の熟語で構成されるため、検索漏れがほぼゼロ
- **2文字の単語に対応**: 「設計」「開発」のような2文字の単語も確実に検索可能
- **LIKE演算子の高速化**: PostgreSQL標準の `LIKE '%...%'` 検索を爆速化
- **pg_trgmとの違い**: pg_trgm（3-gram）は2文字の単語が検索漏れしたり、精度が出にくい場合がある

**pg_trgmの限界**:

- 3文字単位のため、「設計」「開発」のような2文字の単語の検索が苦手
- ひらがなの助詞などがノイズになりやすい

### 3.2 ハイブリッド検索の設計

**UNION ALL方式の採用**:

FULL OUTER JOINは両方のCTEを完全評価するため非効率です。UNION ALLを使用した方が効率的です。

**スコアリング方式**:

- **ベクトル類似度**: 0.7の重み（概念的な類似に強い）
- **キーワードスコア**: 0.3の重み（固有名詞の完全一致に強い）

**実装方針**:

1. ベクトル検索で上位50件を取得（候補を広めに取る）
2. キーワード検索で上位100件を取得（`LIKE '%キーワード%'`で検索）
3. 両方の結果をUNION ALLで結合
4. スコアを合計して降順にソート
5. 上位10件を返す

### 3.3 インデックス設計

**pg_bigm用のGINインデックス**:

```sql
CREATE INDEX idx_chunks_content_bigm ON knowledge_chunks 
USING gin (content gin_bigm_ops);
```

**注意点**:

- インデックスサイズが大きくなる傾向がある（2文字の組み合わせの方が3文字よりも多いため）
- 更新速度が若干遅くなる（バックグラウンド処理のため、ユーザー体験への影響は軽微）

---

## 4. 実装ステップ

### 4.1 実装ステップと完了状況

| Step | 内容 | 期間 | 完了状況 | 詳細ドキュメント |
|------|------|------|---------|------------------|
| 0 | 依存関係の確認と設計レビュー | 0.5日 | ⏳ 未実装 | - |
| 1 | Dockerfile.postgresの作成 | 0.5日 | ⏳ 未実装 | [PostgreSQL実装ガイド](../../50_implementation/51_guides/postgresql-implementation-guide.md#dockerfile-での-pg_bigm-の導入) |
| 2 | pg_bigm拡張の有効化（Alembicマイグレーション） | 0.5日 | ⏳ 未実装 | - |
| 3 | ハイブリッド検索メソッドの実装 | 1日 | ⏳ 未実装 | - |
| 4 | テストの実装 | 0.5日 | ⏳ 未実装 | - |
| **合計** | | **2-3日** | **⏳ 未実装** | |

### 4.2 各ステップの詳細

#### Step 0: 依存関係の確認と設計レビュー

**完了内容**:

- Phase 8の実装状況を確認
- pg_bigmのバージョンと互換性を確認
- 設計方針のレビュー

**確認事項**:

- PostgreSQL 18 + pgvector 0.8.1 が正常に動作していること
- `PostgreSQLDatabase`クラスの`similarity_search`メソッドが実装されていること
- `knowledge_chunks`テーブルが存在すること

#### Step 1: Dockerfile.postgresの作成

**完了内容**:

- `Dockerfile.postgres`の作成
- pg_bigmのビルドとインストール
- マルチステージビルドによる最適化

**実装ファイル**: `Dockerfile.postgres`

**参考**: [PostgreSQL実装ガイド - Dockerfileでのpg_bigmの導入](../../50_implementation/51_guides/postgresql-implementation-guide.md#dockerfile-での-pg_bigm-の導入)

**注意点**:

- pg_bigmのバージョンは`1.2-20240606`を使用
- GitHubリリースへの依存があるため、チェックサム検証を推奨
- 開発環境では標準のpgvectorイメージを使用（ビルド時間の短縮）

#### Step 2: pg_bigm拡張の有効化（Alembicマイグレーション）

**完了内容**:

- Alembicマイグレーションファイルの作成
- pg_bigm拡張の有効化
- GINインデックスの作成

**実装ファイル**: `alembic/versions/XXXXX_add_pg_bigm_extension.py`

**マイグレーション内容**:

```sql
-- pg_bigm拡張の有効化
CREATE EXTENSION IF NOT EXISTS pg_bigm;

-- knowledge_chunks.contentにGINインデックス（pg_bigm）を追加
CREATE INDEX idx_chunks_content_bigm ON knowledge_chunks 
USING gin (content gin_bigm_ops);
```

**注意点**:

- 既存のデータがある場合、インデックス作成に時間がかかる可能性がある
- 本番環境ではメンテナンスウィンドウを設けることを推奨

#### Step 3: ハイブリッド検索メソッドの実装

**完了内容**:

- `PostgreSQLDatabase`クラスに`hybrid_search`メソッドを追加
- ベクトル検索とキーワード検索を組み合わせた検索ロジックの実装
- スコアリング機能の実装

**実装ファイル**: `src/kotonoha_bot/db/postgres.py`

**メソッドシグネチャ**:

```python
async def hybrid_search(
    self,
    query_embedding: list[float],
    query_text: str,
    limit: int = 10,
    vector_weight: float = 0.7,
    keyword_weight: float = 0.3,
    **filters: Any,
) -> list[SearchResult]:
    """ハイブリッド検索（ベクトル検索 + キーワード検索）
    
    Args:
        query_embedding: クエリのベクトル（1536次元）
        query_text: クエリのテキスト（キーワード検索用）
        limit: 返却する結果の数（デフォルト: 10）
        vector_weight: ベクトル類似度の重み（デフォルト: 0.7）
        keyword_weight: キーワードスコアの重み（デフォルト: 0.3）
        **filters: フィルタ条件（source_type, channel_id, user_id等）
    
    Returns:
        検索結果のリスト（スコア順）
    """
```

**実装ロジック**:

1. ベクトル検索で上位50件を取得（`similarity_search`メソッドを使用）
2. キーワード検索で上位100件を取得（`LIKE '%キーワード%'`で検索）
3. 両方の結果をUNION ALLで結合
4. スコアを合計して降順にソート
5. 上位`limit`件を返す

**SQL実装例**:

```sql
WITH vector_results AS (
    SELECT 
        id,
        source_id,
        content,
        1 - (embedding <=> $1::halfvec(1536)) AS vector_similarity
    FROM knowledge_chunks
    WHERE embedding IS NOT NULL
    ORDER BY embedding <=> $1::halfvec(1536)
    LIMIT 50
),
keyword_results AS (
    SELECT 
        id,
        source_id,
        content,
        1.0 AS keyword_score
    FROM knowledge_chunks
    WHERE content LIKE $2
      AND embedding IS NOT NULL
    LIMIT 100
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

**注意点**:

- `embedding IS NOT NULL`条件を必ず付与（HNSWインデックス使用のため）
- キーワード検索にも上限を設ける（巨大なテーブルでのボトルネックを防ぐ）
- SQLインジェクション対策（Allow-list方式）を維持

#### Step 4: テストの実装

**完了内容**:

- ハイブリッド検索のユニットテスト
- 統合テストの実装
- パフォーマンステストの実施

**実装ファイル**:

- `tests/unit/test_postgres_hybrid_search.py`: ハイブリッド検索のユニットテスト
- `tests/integration/test_hybrid_search.py`: ハイブリッド検索の統合テスト
- `tests/performance/test_hybrid_search_performance.py`: パフォーマンステスト

**テスト項目**:

1. **基本機能テスト**:
   - ベクトル検索のみの結果が正しく返されること
   - キーワード検索のみの結果が正しく返されること
   - ハイブリッド検索の結果が正しく返されること
   - スコアリングが正しく計算されること

2. **フィルタリングテスト**:
   - `source_type`フィルタが正しく動作すること
   - `channel_id`フィルタが正しく動作すること
   - `user_id`フィルタが正しく動作すること

3. **パフォーマンステスト**:
   - 大量データ（10万件以上）での検索性能
   - インデックスが正しく使用されていること（EXPLAIN ANALYZE）

---

## 5. 完了基準

### 5.1 実装完了基準

- ✅ `Dockerfile.postgres`が作成されている
- ✅ pg_bigm拡張が有効化されている（Alembicマイグレーション）
- ✅ GINインデックス（pg_bigm）が作成されている
- ✅ `hybrid_search`メソッドが実装されている
- ✅ ベクトル検索とキーワード検索が正しく組み合わせられている
- ✅ スコアリングが正しく計算されている
- ✅ フィルタリング機能が正しく動作している
- ✅ テストが実装されている
- ✅ テストが通過する

### 5.2 品質基準

- **パフォーマンス**: 検索クエリが1秒以内に完了すること（10万件のデータで）
- **精度**: 固有名詞を含む検索の精度が向上していること
- **互換性**: 既存の`similarity_search`メソッドが正常に動作すること

---

## 6. テスト計画

### 6.1 ユニットテスト

**テストファイル**: `tests/unit/test_postgres_hybrid_search.py`

**テスト項目**:

1. `hybrid_search`メソッドの基本動作
2. スコアリングの計算ロジック
3. フィルタリング機能
4. エラーハンドリング

### 6.2 統合テスト

**テストファイル**: `tests/integration/test_hybrid_search.py`

**テスト項目**:

1. ベクトル検索とキーワード検索の組み合わせ
2. 大量データでの検索性能
3. インデックスの使用確認（EXPLAIN ANALYZE）

### 6.3 パフォーマンステスト

**テストファイル**: `tests/performance/test_hybrid_search_performance.py`

**テスト項目**:

1. 検索クエリの実行時間測定
2. インデックスサイズの確認
3. メモリ使用量の確認

### 6.4 テスト実行方法

```bash
# 全テスト実行
pytest tests/ -v

# ハイブリッド検索のテストのみ実行
pytest tests/unit/test_postgres_hybrid_search.py -v
pytest tests/integration/test_hybrid_search.py -v

# パフォーマンステスト
pytest tests/performance/test_hybrid_search_performance.py -v

# カバレッジ付きテスト実行
pytest tests/ -v --cov=src/kotonoha_bot --cov-report=term-missing
```

---

## 7. 導入・デプロイ手順

### 7.1 開発環境での導入

1. **Dockerfile.postgresの作成**

   ```bash
   # Dockerfile.postgresを作成
   # （実装ガイドを参照）
   ```

2. **docker-compose.ymlの更新**

   ```yaml
   services:
     postgres:
       # 開発環境では標準イメージを使用（ビルド時間の短縮）
       image: pgvector/pgvector:0.8.1-pg18
       # 本番環境ではカスタムイメージを使用
       # build:
       #   context: .
       #   dockerfile: Dockerfile.postgres
   ```

3. **Alembicマイグレーションの適用**

   ```bash
   # Bot起動時に自動適用されます
   # または手動で実行:
   alembic upgrade head
   ```

4. **Botの起動**

   ```bash
   docker compose up kotonoha-bot
   ```

### 7.2 本番環境でのデプロイ

1. **カスタムイメージのビルド**

   ```bash
   docker build -f Dockerfile.postgres -t kotonoha-postgres:latest .
   ```

2. **docker-compose.ymlの更新**

   ```yaml
   services:
     postgres:
       image: kotonoha-postgres:latest
       # または build: を使用
   ```

3. **データベースのメンテナンス**

   - メンテナンスウィンドウを設ける（インデックス作成に時間がかかる可能性がある）
   - バックアップを取得

4. **Alembicマイグレーションの適用**

   ```bash
   alembic upgrade head
   ```

5. **動作確認**

   - ハイブリッド検索が正常に動作することを確認
   - 既存のベクトル検索が正常に動作することを確認

---

## 8. 今後の改善計画

### 8.1 Phase 12: Rerankingの実装（オプション）

**目的**: Cross-Encoder（Reranker）を使用して検索精度を向上させる

**実装方法**: ベクトル検索の結果を再ランキング

**注意点**: CPU負荷を考慮

### 8.2 スコアリングの最適化

**目的**: ベクトル類似度とキーワードスコアの重みを動的に調整

**実装方法**: クエリの種類に応じて重みを変更

### 8.3 多言語対応

**目的**: 英語やその他の言語での検索精度向上

**実装方法**: 言語ごとに最適な検索方法を選択

---

## 参考資料

- **スキーマ設計書**: [PostgreSQL スキーマ設計書](../../40_design_detailed/42_db-schema-physical/postgresql-schema-overview.md)
- **実装ガイド**: [PostgreSQL実装ガイド](../../50_implementation/51_guides/postgresql-implementation-guide.md)
- **クエリガイド**: [PostgreSQLクエリガイド](../../50_implementation/51_guides/postgresql-query-guide.md)
- **Phase 8実装計画**: [Phase 8実装計画](./phase08.md)

---

**作成日**: 2026年1月19日  
**最終更新日**: 2026年1月19日  
**バージョン**: 1.0  
**作成者**: kotonoha-bot 開発チーム
