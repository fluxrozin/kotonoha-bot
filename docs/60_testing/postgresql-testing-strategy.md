# PostgreSQL テスト戦略

**作成日**: 2026年1月19日  
**対象プロジェクト**: kotonoha-bot v0.8.0

---

## 目次

1. [概要](#1-概要)
2. [テストフィクスチャ](#2-テストフィクスチャ)
3. [実装済みテストケース](#3-実装済みテストケース)
4. [未実装テストケース](#4-未実装テストケース)
5. [テスト実行方法](#5-テスト実行方法)
6. [テストツールと設定](#6-テストツールと設定)

---

## 1. 概要

### 1.1 テストの目的

- PostgreSQL + pgvector の実装が正しく動作することを確認
- ベクトル検索の精度とパフォーマンスを検証
- Embedding処理とセッションアーカイブ処理の動作を確認
- 既存機能への影響がないことを確認（回帰テスト）

### 1.2 テストカバレッジの目標

- **ユニットテスト**: 80%以上
- **統合テスト**: 主要な機能フローをカバー
- **パフォーマンステスト**: ベクトル検索、バッチ処理の性能測定

---

## 2. テストフィクスチャ

### 2.1 PostgreSQL用テストフィクスチャ

**実装ファイル**: `tests/conftest.py`

現在の実装では、以下の2つのフィクスチャが提供されています：

1. **`postgres_db`**: 通常のフィクスチャ（TRUNCATEでクリーンアップ）
   - 注意: 並列テスト実行時（pytest-xdist）にデータの競合が発生する可能性があります
   - 各テスト後に`TRUNCATE ... CASCADE`でクリーンアップ

2. **`postgres_db_with_rollback`**: ロールバックパターン（推奨）
   - 推奨: 並列テスト実行時でも安全
   - 各テストがトランザクション内で実行され、テスト終了時に自動的にロールバック
   - より高速で安全

**使用方法**:

```python
# 通常のフィクスチャ（順次実行時）
async def test_example(postgres_db):
    await postgres_db.save_session(session)

# ロールバックパターン（並列実行時推奨）
async def test_example_parallel(postgres_db_with_rollback):
    db, conn = postgres_db_with_rollback
    # テストコード（トランザクション内で実行）
    await conn.execute("INSERT INTO sessions ...")
    # テスト終了時に自動的にロールバックされる
```

### 2.2 Mock Embedding Provider

```python
# tests/conftest.py
@pytest.fixture
def mock_embedding_provider():
    """Mock Embedding Provider"""
    from unittest.mock import AsyncMock
    from kotonoha_bot.external.embedding import EmbeddingProvider
    
    provider = AsyncMock(spec=EmbeddingProvider)
    provider.generate_embedding = AsyncMock(
        return_value=[0.1] * 1536
    )
    provider.generate_embeddings_batch = AsyncMock(
        return_value=[[0.1] * 1536 for _ in range(10)]
    )
    provider.get_dimension = lambda: 1536
    
    return provider
```

---

## 3. 実装済みテストケース

### 3.1 PostgreSQLDatabase関連

**テストファイル**: `tests/unit/test_postgres_db.py`

#### 初期化・接続

- データベース初期化
- 接続初期化（pgvector型登録、JSONBコーデック）
- データベース接続のクローズ
- パラメータなし初期化
- 接続文字列での初期化
- 個別パラメータでの初期化
- デフォルトポート使用

#### セッション管理

- セッション保存・読み込み
- セッション削除
- すべてのセッション読み込み
- 存在しないセッション読み込み
- 存在しないセッション削除
- セッション保存のON CONFLICT処理
- thread_id付きセッション保存
- ステータス更新

#### 知識ベース

- 知識ソース保存
- 知識チャンク保存
- すべてのsource_type
- NULLのURI
- NULLのlocation
- チャンク保存のtoken_count自動計算
- 無効なsource_typeエラー

#### ベクトル検索

- 基本的なベクトル検索
- フィルタリング付き検索
- 閾値フィルタリングなしの検索
- source_typesフィルタリング
- user_idフィルタリング
- channel_idフィルタリング
- 複合フィルタリング
- 無効なフィルタキーでエラー
- 無効なsource_typeでエラー
- channel_idの型エラー
- user_idの型エラー
- source_types値エラー
- similarity_thresholdパラメータ
- 空結果の検索
- apply_threshold=Falseの詳細

#### pgvector拡張

- pgvector拡張の確認
- halfvec型のINSERT/SELECTテスト

### 3.2 EmbeddingProcessor関連

**テストファイル**: `tests/unit/test_embedding_processor.py`

#### 初期化・設定

- EmbeddingProcessor初期化
- バッチ処理設定
- セマフォ初期化
- インターバル設定

#### Embedding処理

- Embedding処理
- リトライロジック
- バッチ処理
- 空の保留チャンク
- バッチサイズを超えるデータの処理
- 小さいbatch_sizeでの処理

#### DLQ（Dead Letter Queue）

- DLQへの移動ロジック
- DLQ移動時のソース情報
- エラーコードとエラーメッセージの記録

#### Sourceステータス管理

- Sourceステータス更新（completed）
- Sourceステータス更新（partial with DLQ）
- Sourceステータス更新（pending状態）
- failed状態
- partial状態

#### エラーハンドリング

- データベース接続エラー
- エラー分類（タイムアウト、レート制限、認証エラー等）
- エラー分類のバリエーション
- エラーメッセージ一般化
- エラーメッセージ一般化（全タイプ）

#### バッチEmbedding生成

- バッチAPIを持たないプロバイダーでのフォールバック
- セマフォ制限付きEmbedding生成

#### ライフサイクル

- Graceful Shutdown
- ロックスキップ動作
- startメソッド

### 3.3 SessionArchiver関連

**テストファイル**: `tests/unit/test_session_archiver.py`

#### 初期化・設定

- SessionArchiver初期化
- 閾値時間設定

#### セッションアーカイブ

- セッションアーカイブ
- スライディングウィンドウ
- フィルタリングロジック
- 楽観的ロック
- 空セッションのアーカイブ
- すべてアーカイブ済みセッション
- メタデータ付きアーカイブ

#### チャンク化

- チャンク化戦略
- メッセージチャンク化の詳細
- チャンク化のオーバーラップ境界値
- コンテンツ分割のフォールバック
- 短いコンテンツの分割

#### メタデータ生成

- メッセージ整形
- タイトル生成（通常、長いメッセージ、Botのみ、空メッセージ）
- タイトル生成（各種パターン）
- Discord URI生成（guild_id、channel_id、thread_idの組み合わせ）
- DM用URI生成

#### アーカイブ判定

- アーカイブ判定の境界値
- 最小セッション長さの境界値
- ユーザーメッセージのみのセッション
- 不明なロールの処理

#### インデックス管理

- last_archived_message_indexのリセット
- 無効なインデックスの処理

#### ライフサイクル

- Graceful Shutdown
- startメソッド
- 処理フラグ
- 処理中セッション追跡

### 3.4 境界値テスト

**テストファイル**: `tests/unit/test_boundary_values.py`

#### ベクトル検索の境界値

- top_kの境界値（0, 1, デフォルト値, 非常に大きい値）
- similarity_thresholdの境界値（0.0, 1.0）
- 空のembeddingリスト
- 異なる次元数のembedding
- source_typesフィルタリングの境界値（空リスト、非リスト型）
- apply_threshold=Falseの詳細

#### Embedding処理の境界値

- batch_sizeの境界値（小さい値、大きい値、バッチサイズを超えるデータ）
- max_concurrentの境界値（最小値）

#### チャンク保存の境界値

- 空のcontent
- 非常に長いcontent
- チャンク化のオーバーラップ境界値

#### セッションアーカイブの境界値

- 最小セッション長さの境界値

### 3.5 統合テスト

#### セッションアーカイブの統合テスト

**テストファイル**: `tests/integration/test_session_archiving.py`

- セッションのアーカイブからEmbedding処理までの一連の流れ
- 複数セッションの並列アーカイブ
- エラーハンドリング

#### ベクトル検索の統合テスト

**テストファイル**: `tests/integration/test_vector_search.py`

- ベクトル検索の精度確認
- フィルタリング機能の動作確認
- HNSWインデックスの効果確認

#### 並行処理の統合テスト

**テストファイル**: `tests/integration/test_concurrent_processing.py`

- 複数セッションの同時アーカイブ
- 複数ソースの同時Embedding処理
- 大量データのバッチ処理（バッチサイズを超えるデータ）
- エラー伝播の確認
- セッション保存とアーカイブの同時実行
- 複数ソースのステータス更新
- 楽観的ロックの競合時リトライ
- エラーを含む完全なフロー
- Graceful Shutdownの統合テスト
- 知識検索のE2Eフロー
- 複数バッチのエラー回復
- アーカイブとベクトル検索フィルタリング
- DLQ回復フロー

#### 知識ベース保存の統合テスト

**テストファイル**: `tests/integration/test_knowledge_base_storage.py`

- 知識ベースへの保存と検索の一連の流れ

#### Embedding処理の統合テスト

**テストファイル**: `tests/integration/test_embedding_processing.py`

- Embedding処理の一連の流れ

#### セッション管理の統合テスト

**テストファイル**: `tests/integration/test_session_management.py`

- セッション管理の一連の流れ

### 3.6 パフォーマンステスト

#### ベクトル検索の性能測定

**テストファイル**: `tests/performance/test_vector_search.py`

- 検索速度（10件、100件、1000件のデータでの検索時間）
- HNSWインデックスの効果
- 大量データ（10万件以上）での性能

#### バッチ処理の性能測定

**テストファイル**: `tests/performance/test_load.py`

- Embedding処理のバッチサイズと処理速度の関係
- セッションアーカイブの並列処理性能

---

## 4. 未実装テストケース

以下の確認項目は、実際の環境での手動確認が必要、またはテストとして自動化困難な項目です：

### 4.1 Discord Bot経由での動作確認

- 実際のDiscord接続が必要
- 統合テストとして実装可能だが、Discord APIのモックが必要
- 実際のDiscord Bot経由でのセッション保存・読み込み
- 実際のDiscord Bot経由での知識ベース検索
- 実際のDiscord Bot経由でのセッションアーカイブ

### 4.2 バックグラウンドタスクの起動確認

- ログ解析が必要
- 部分的にテスト可能（タスクの開始状態を確認）
- EmbeddingProcessorのバックグラウンドタスク起動
- SessionArchiverのバックグラウンドタスク起動
- タスクの定期実行確認

### 4.3 Graceful Shutdownの実際の動作確認

- 実際のプロセス停止をシミュレートする必要がある
- 部分的にテスト可能（shutdownメソッドの呼び出しを確認）
- 実際のプロセス停止時のGraceful Shutdown
- 長時間実行中のプロセス停止
- 大量データ処理中のプロセス停止

### 4.4 実際の負荷テスト

- 実際の負荷が必要
- パフォーマンステストとして部分的に実装済み（`tests/performance/`）
- 実際のDiscord Bot負荷での動作確認
- 大量セッション同時処理
- 大量チャンク同時処理
- 接続プール枯渇時の動作

### 4.5 エッジケース（実装検討）

以下のエッジケースは、実装コードを精査した上で追加テストケースとして検討可能です：

- データベース接続プールの枯渇時の動作
- 非常に長いセッション（1000メッセージ以上）のアーカイブ
- 非常に大きなチャンク（トークン数上限付近）の処理
- ネットワークエラー時のリトライ動作
- データベースロック競合時の動作
- メモリ不足時の動作

---

## 5. テスト実行方法

### 5.1 テスト実行の方針

⚠️ **重要**: 本プロジェクトでは、以下の方針でテストを実行します：

- **データベース関連テスト**: **シリアル実行（順次実行）**を基本とする
- **それ以外のテスト**: **パラレル実行（並列実行）**を推奨

**データベース関連テストの定義**:

- `postgres_db` または `postgres_db_with_rollback` フィクスチャを使用するテスト
- `tests/integration/` 配下のテスト（統合テスト）
- `tests/performance/` 配下のテスト（パフォーマンステスト）
- ファイル名やテスト名に `postgres` が含まれるテスト
- `test_postgres_db.py`, `test_embedding_processor.py`, `test_session_archiver.py` など

**理由**:

- データベース関連テストを並列実行すると、データの競合や接続プールの枯渇が発生する可能性がある
- シリアル実行により、テストの安定性と再現性が向上する
- それ以外のテスト（ユニットテストなど）は並列実行により実行時間を大幅に短縮できる

### 5.2 すべてのテストを実行

```bash
# すべてのテストを実行（データベース関連はシリアル、それ以外はパラレル）
# 方法1: データベース関連テストを先にシリアル実行、その後それ以外をパラレル実行
pytest tests/ -k "postgres or integration or performance" -v
  # データベース関連（シリアル）
pytest tests/ -k "not (postgres or integration or performance)" \
  -n auto -v  # それ以外（パラレル）

# 方法2: すべてをシリアル実行（最も安全だが時間がかかる）
pytest tests/ -v

# 方法3: すべてをパラレル実行（非推奨：データベース関連テストで競合が発生する可能性）
# pytest tests/ -n auto -v  # ⚠️ 非推奨
```

### 5.3 特定のテストを実行

```bash
# PostgreSQL関連のテストのみ実行（シリアル実行）
pytest tests/ -k postgres -v

# 統合テストのみ実行（シリアル実行）
pytest tests/integration/ -v

# パフォーマンステストのみ実行（シリアル実行）
pytest tests/performance/ -v

# データベース関連以外のテストを並列実行
pytest tests/unit/ -k "not postgres" -n auto -v
```

### 5.4 pytest-xdistを使った並列テスト実行

**pytest-xdist**を使用することで、データベース関連以外のテストを並列実行し、実行時間を大幅に短縮できます。

⚠️ **重要**: データベース関連テストは**シリアル実行**を基本とします（5.1参照）。

#### 基本的な使用方法

```bash
# CPUコア数に応じて自動的に並列実行（データベース関連テストを除外）
pytest tests/ -k "not (postgres or integration or performance)" -n auto

# 指定した数のワーカーで並列実行
pytest tests/unit/ -k "not postgres" -n 4

# カバレッジ付きで並列実行
pytest tests/ -k "not (postgres or integration or performance)" \
  -n auto --cov=src/kotonoha_bot --cov-report=term-missing

# シリアル実行（並列実行を無効化）
pytest tests/ -n 0  # または -n オプションを指定しない
```

#### データベース関連テストをシリアル実行する理由

1. **データの競合を避ける**
   - 各テストワーカーが同じデータベースを共有する場合、データの競合が発生する可能性があります
   - 現在の実装では、`postgres_db`フィクスチャが各テスト後に`TRUNCATE ... CASCADE`でクリーンアップしていますが、並列実行時にはタイミングによって競合が発生する可能性があります

2. **接続プールの枯渇を防ぐ**
   - 各テストワーカーが同じPostgreSQLインスタンスに接続する場合、接続プールのサイズに注意が必要です
   - シリアル実行により、接続プールの枯渇を防ぎます

3. **テストの安定性と再現性**
   - シリアル実行により、テストの実行順序が一定になり、再現性が向上します
   - デバッグが容易になります

#### 推奨されるテスト実行パターン

```bash
# パターン1: データベース関連テストをシリアル実行、それ以外をパラレル実行（推奨）
pytest tests/ -k "postgres or integration or performance" -v
  # シリアル
pytest tests/ -k "not (postgres or integration or performance)" \
  -n auto -v  # パラレル

# パターン2: ディレクトリ単位で実行
pytest tests/integration/ -v  # 統合テスト（シリアル）
pytest tests/performance/ -v  # パフォーマンステスト（シリアル）
pytest tests/unit/ -k "not postgres" -n auto -v  # ユニットテスト（パラレル、DB関連を除外）

# パターン3: すべてをシリアル実行（最も安全だが時間がかかる）
pytest tests/ -v

# パターン4: 特定のテストマーカーで並列実行を制御
pytest tests/ -k "not (postgres or integration or performance)" \
  -n auto -m "not slow" -v
```

#### ロールバックパターンについて

`postgres_db_with_rollback`フィクスチャを使用することで、理論的には並列実行が可能ですが、本プロジェクトでは**データベース関連テストはシリアル実行を基本**とします。

**理由**:

- ロールバックパターンでも、接続プールの枯渇やトランザクションの競合が発生する可能性がある
- シリアル実行により、テストの安定性と再現性が向上する
- デバッグが容易になる

#### CI/CDでのテスト実行

GitHub Actionsでのテスト実行例（データベース関連はシリアル、それ以外はパラレル）：

```yaml
# .github/workflows/ci.yml
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
      
      # データベース関連テストをシリアル実行
      - name: Run database-related tests (serial)
        run: |
          pytest tests/ -k "postgres or integration or performance" \
            -v --cov=src/kotonoha_bot --cov-append
      
      # それ以外のテストを並列実行
      - name: Run other tests (parallel)
        run: |
          pytest tests/ \
            -k "not (postgres or integration or performance)" \
            -n auto -v --cov=src/kotonoha_bot --cov-append
      
      # カバレッジレポートを生成
      - name: Generate coverage report
        run: |
          pytest --cov=src/kotonoha_bot \
            --cov-report=term-missing --cov-report=xml
```

#### パフォーマンスの目安

- **全テストをシリアル実行**: 約5-10分
- **データベース関連テストをシリアル、それ以外をパラレル実行**: 約3-5分（約40-50%の時間短縮）
- **並列実行（4ワーカー、データベース関連を除外）**: 約2-3分（約50-70%の時間短縮）

**注意**: データベース関連テストはシリアル実行を基本とすることで、テストの安定性と再現性が向上します。

---

## 6. テストツールと設定

### 6.1 利用可能なテストツール

`pyproject.toml`の`[dependency-groups.dev]`に以下のテストツールが含まれています：

1. **pytest>=9.0.2** - テストフレームワーク（基本）
2. **pytest-asyncio>=1.3.0** - 非同期テスト対応
3. **pytest-cov>=7.0.0** - カバレッジ測定
4. **pytest-html>=4.1.1** - HTMLレポート生成
5. **pytest-mock>=3.15.1** - モック機能
6. **pytest-randomly>=4.0.1** - テストのランダム実行順序
7. **pytest-sugar>=1.1.1** - テスト出力の見やすさ向上
8. **pytest-timeout>=2.4.0** - テストのタイムアウト設定
9. **pytest-xdist>=3.8.0** - 並列テスト実行

### 6.2 各ツールの使用方法

#### pytest-asyncio（非同期テスト対応）

```bash
# 非同期テストを自動検出して実行
pytest tests/ -v

# pyproject.toml で asyncio_mode = "auto" が設定されているため、
# @pytest.mark.asyncio デコレータが自動的に適用されます
```

#### pytest-cov（カバレッジ測定）

```bash
# カバレッジを測定してターミナルに表示
pytest tests/ --cov=src/kotonoha_bot --cov-report=term-missing

# HTMLレポートを生成
pytest tests/ --cov=src/kotonoha_bot --cov-report=html

# XMLレポートを生成（CI/CD用）
pytest tests/ --cov=src/kotonoha_bot --cov-report=xml
```

#### pytest-html（HTMLレポート生成）

```bash
# HTMLレポートを生成
pytest tests/ --html=report.html --self-contained-html

# カバレッジとHTMLレポートを同時に生成
pytest tests/ --cov=src/kotonoha_bot --cov-report=html --html=report.html
```

#### pytest-mock（モック機能）

```python
# テストコードでの使用例
def test_example(mocker):
    # 関数をモック
    mock_func = mocker.patch('module.function')
    mock_func.return_value = 'mocked'

    # 非同期関数をモック
    mock_async = mocker.patch(
        'module.async_function', new_callable=AsyncMock
    )
    mock_async.return_value = 'mocked_async'
```

#### pytest-randomly（ランダム実行順序）

```bash
# テストをランダムな順序で実行（テストの独立性を確認）
pytest tests/ --randomly

# シードを指定して再現可能なランダム順序
pytest tests/ --randomly --randomly-seed=12345

# ランダム実行を無効化
pytest tests/ --randomly-dont-reorganize
```

#### pytest-sugar（見やすい出力）

```bash
# 自動的に有効化（インストールされている場合）
pytest tests/ -v

# より詳細な出力
pytest tests/ -vv
```

#### pytest-timeout（タイムアウト設定）

```bash
# すべてのテストにタイムアウトを設定（秒）
pytest tests/ --timeout=300

# 特定のテストにタイムアウトを設定
@pytest.mark.timeout(60)
async def test_long_running():
    # 60秒でタイムアウト
    pass
```

#### pytest-xdist（並列実行）

```bash
# CPUコア数に応じて自動並列実行
pytest tests/ -n auto

# 指定数のワーカーで並列実行
pytest tests/ -n 4

# 並列実行とカバレッジの組み合わせ
pytest tests/ -n auto --cov=src/kotonoha_bot
```

### 6.3 インストール方法

```bash
# 開発依存関係をインストール（uvを使用）
uv sync --group dev

# または、pipを使用
pip install -e ".[dev]"
```

### 6.4 pytest設定（pyproject.toml）

`pyproject.toml`の`[tool.pytest.ini_options]`セクションで以下の設定が行われています：

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]              # テストディレクトリ
python_files = ["test_*.py"]      # テストファイルのパターン
python_functions = ["test_*"]     # テスト関数のパターン
addopts = "-v --tb=short"         # デフォルトオプション（詳細出力、短いトレースバック）
asyncio_mode = "auto"             # 非同期テストの自動検出
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
]
```

**設定の説明**:

- `testpaths = ["tests"]`: テストファイルの検索ディレクトリ
- `python_files = ["test_*.py"]`: `test_`で始まるPythonファイルをテストファイルとして認識
- `python_functions = ["test_*"]`: `test_`で始まる関数をテスト関数として認識
- `addopts = "-v --tb=short"`: デフォルトで詳細出力（`-v`）と短いトレースバック（`--tb=short`）を有効化
- `asyncio_mode = "auto"`: 非同期関数を自動検出し、`@pytest.mark.asyncio`デコレータを自動適用

### 6.5 推奨されるテスト実行コマンド

```bash
# 基本的な実行（推奨）
pytest tests/ -v

# カバレッジ付きで実行
pytest tests/ --cov=src/kotonoha_bot --cov-report=term-missing

# 並列実行（高速化）
pytest tests/ -n auto --cov=src/kotonoha_bot

# HTMLレポート付きで実行
pytest tests/ --html=report.html --self-contained-html

# ランダム順序で実行（テストの独立性を確認）
pytest tests/ --randomly

# タイムアウト付きで実行（長時間実行されるテストを検出）
pytest tests/ --timeout=300

# slowマーカーのテストを除外
pytest tests/ -m "not slow"

# 特定のテストファイルのみ実行
pytest tests/unit/test_postgres_db.py -v

# 特定のテスト関数のみ実行
pytest tests/unit/test_postgres_db.py::test_postgres_db_initialize -v
```

---

**最終更新日**: 2026年1月19日
