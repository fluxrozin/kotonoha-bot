# コード品質チェック・テスト実施マニュアル

## 概要

本マニュアルは、`pyproject.toml` に設定されているツールを活用して、以下の残存課題を解決するためのベストプラクティスをまとめたものである：

- 型ヒントの完全化（一部のファイルで不完全）
- docstring の完全化（一部の公開APIで不足）
- コードフォーマット（13ファイルがフォーマット必要）
- 型チェック（8エラー残存）
- テストカバレッジ（現在70%、目標80%未達）

## 関連ドキュメント

- [テスト計画書](../60_testing/test-plan.md)
- [テスト仕様書](../60_testing/test-specification.md)
- [CI/CD設定](../../.github/workflows/ci.yml)

## 1. 使用ツール一覧

本プロジェクトで使用しているコード品質ツールは以下の通りである：

| ツール | 用途 | 設定場所 |
|--------|------|----------|
| **Ruff** | リント・フォーマット・docstringチェック | `[tool.ruff]` |
| **ty** | 型チェック | `[tool.ty]` |
| **pytest** | テスト実行 | `[tool.pytest.ini_options]` |
| **pytest-cov** | カバレッジ測定 | `[tool.coverage.*]` |
| **deptry** | 依存関係チェック | `[tool.deptry]` |
| **pydeps** | 循環依存チェック | コマンドライン |

## 2. 日常的な開発ワークフロー

### 2.1 推奨チェック順序

コードをコミットする前に、以下の順序でチェックを実施することを推奨する：

```bash
# 1. フォーマット（自動修正可能）
uv run ruff format src/ tests/

# 2. リントチェック（自動修正可能なものは修正）
uv run ruff check src/ tests/ --fix

# 3. 自動修正できないエラーを確認
uv run ruff check src/ tests/

# 4. 型チェック
uv run ty check src/

# 5. テスト実行（カバレッジ付き）
uv run pytest --cov=src/kotonoha_bot --cov-report=term-missing
```

**注意**: ステップ2で自動修正できないエラーが残る場合は、ステップ3でエラー内容を確認し、手動で修正する必要がある。

### 2.2 ワンライナーコマンド

すべてのチェックを一度に実行する場合：

```bash
# チェックのみ（修正なし）
uv run ruff check src/ tests/ && \
uv run ruff format --check src/ tests/ && \
uv run ty check src/ && \
uv run pytest --cov=src/kotonoha_bot \
  --cov-report=term-missing --cov-fail-under=80

# 自動修正付き（推奨）
uv run ruff format src/ tests/ && \
uv run ruff check src/ tests/ --fix && \
uv run ty check src/ && \
uv run pytest --cov=src/kotonoha_bot \
  --cov-report=term-missing --cov-fail-under=80
```

### 2.3 シェルエイリアスの設定

開発効率を向上させるため、以下のエイリアスを `~/.bashrc` または `~/.zshrc` に追加することを推奨する：

```bash
# コード品質チェック（修正なし）
alias check="uv run ruff check src/ tests/ && \
  uv run ruff format --check src/ tests/ && \
  uv run ty check src/"

# コード品質チェック（自動修正付き）
alias check-fix="uv run ruff format src/ tests/ && \
  uv run ruff check src/ tests/ --fix && \
  uv run ty check src/"

# エラーをファイルに出力
alias check-errors="uv run ruff check src/ tests/ > ruff_errors.txt 2>&1 && \
  echo 'Errors saved to ruff_errors.txt'"

# テスト実行（カバレッジ付き）
alias test-cov="uv run pytest --cov=src/kotonoha_bot \
  --cov-report=term-missing --cov-fail-under=80"

# 全チェック（CI相当）
alias check-all="uv run ruff format src/ tests/ && \
  uv run ruff check src/ tests/ --fix && \
  uv run ty check src/ && \
  uv run pytest --cov=src/kotonoha_bot \
    --cov-report=term-missing --cov-fail-under=80"
```

### 2.4 エラー修正の効率的なワークフロー

大量のエラーが発生している場合の効率的な修正手順：

```bash
# 1. エラーをファイルに出力
uv run ruff check src/ tests/ > ruff_errors.txt 2>&1

# 2. エラーの種類ごとに集計
grep -o "ARG[0-9]*\|F[0-9]*\|SIM[0-9]*\|B[0-9]*" ruff_errors.txt | \
  sort | uniq -c | sort -rn

# 3. 自動修正可能なエラーを修正
uv run ruff check src/ tests/ --fix

# 4. 残りのエラーを確認
uv run ruff check src/ tests/

# 5. 特定のルールのエラーを確認（例: ARG001, ARG002）
uv run ruff check src/ tests/ --select ARG001,ARG002

# 6. エラーが発生しているファイルをリストアップ
grep "^.*\.py:" ruff_errors.txt | cut -d: -f1 | sort -u
```

## 3. 各ツールの詳細使用方法

### 3.1 Ruff（リント・フォーマット・docstring）

#### 3.1.1 設定概要

`pyproject.toml` で以下のルールが有効になっている：

- **E, W**: pycodestyle（PEP 8準拠）
- **F**: pyflakes（未使用変数・インポート検出）
- **D**: pydocstyle（docstringチェック、Google Style強制）
- **I**: isort（インポート順序）
- **B**: flake8-bugbear（バグの可能性のあるコード検出）
- **C4**: flake8-comprehensions（内包表記の最適化）
- **UP**: pyupgrade（最新Python構文への自動アップグレード）
- **ARG**: flake8-unused-arguments（未使用引数検出）
- **SIM**: flake8-simplify（コード簡略化）

#### 3.1.2 基本的な使い方

```bash
# リントチェック（修正なし）
uv run ruff check src/ tests/

# リントチェック（自動修正可能な問題を修正）
uv run ruff check src/ tests/ --fix

# リントチェック（安全でない修正も含む、注意して使用）
uv run ruff check src/ tests/ --fix --unsafe-fixes

# エラーをファイルに出力して確認
uv run ruff check src/ tests/ > ruff_errors.txt

# フォーマットチェック（修正なし）
uv run ruff format --check src/ tests/

# フォーマット適用
uv run ruff format src/ tests/

# 特定のファイルのみチェック
uv run ruff check src/kotonoha_bot/bot/client.py

# 特定のルールのみチェック
uv run ruff check src/ --select D  # docstringのみ

# 特定のルールを除外
uv run ruff check src/ --ignore F841  # F841を無視
```

#### 3.1.3 docstring チェック（残存課題対応）

Google Style の docstring が強制されている。公開API（`def`、`class`）には docstring が必要である。

```bash
# docstring チェックのみ実行
uv run ruff check src/ --select D

# docstring エラーの詳細表示
uv run ruff check src/ --select D --output-format=full
```

**docstring の必須項目**：

```python
def example_function(param1: str, param2: int) -> bool:
    """関数の説明（1行目は簡潔に）。

    Args:
        param1: パラメータ1の説明
        param2: パラメータ2の説明

    Returns:
        戻り値の説明

    Raises:
        ValueError: エラーが発生した場合の説明
    """
    pass
```

**注意**: テストファイル（`tests/**/*.py`）と `__init__.py` の空の docstring は除外されている。

#### 3.1.4 フォーマット（残存課題対応）

13ファイルがフォーマット必要な状態を解消する：

```bash
# フォーマットが必要なファイルを確認
uv run ruff format --check src/ tests/

# すべてのファイルをフォーマット
uv run ruff format src/ tests/
```

### 3.2 ty（型チェック）

#### 3.2.1 設定概要

`ty` は Rust 製の高速な型チェッカーで、mypy の代替として使用している。
`pyproject.toml` が存在する場合、自動的にソースディレクトリを検出する。

#### 3.2.2 基本的な使い方

```bash
# 型チェック（全ソース）
uv run ty check src/

# 特定のファイルのみチェック
uv run ty check src/kotonoha_bot/bot/client.py

# エラーの詳細表示
uv run ty check src/ --verbose
```

#### 3.2.3 型ヒントの完全化（残存課題対応）

8エラー残存の状態を解消する：

```bash
# 型エラーを確認
uv run ty check src/

# エラーが発生しているファイルを特定
uv run ty check src/ | grep "error:"
```

**型ヒントのベストプラクティス**：

1. **関数の引数と戻り値に型ヒントを付与**：

   ```python
   def process_message(message: str, user_id: int) -> dict[str, Any]:
       pass
   ```

2. **クラスの属性に型ヒントを付与**：

   ```python
   class MessageHandler:
       client: discord.Client
       config: Config
   ```

3. **型エイリアスの活用**：

   ```python
   from typing import TypeAlias
   
   UserID: TypeAlias = int
   MessageContent: TypeAlias = str
   ```

4. **`TYPE_CHECKING` の活用**（循環インポート回避）：

   ```python
   from typing import TYPE_CHECKING
   
   if TYPE_CHECKING:
       from kotonoha_bot.bot.client import Client
   ```

### 3.3 pytest（テスト実行）

#### 3.3.1 設定概要

`pyproject.toml` で以下の設定が有効になっている：

- テストパス: `tests/`
- テストファイル: `test_*.py`
- テスト関数: `test_*`
- asyncio モード: `auto`
- マーカー: `slow`（遅いテストのマーク）

#### 3.3.2 基本的な使い方

```bash
# すべてのテストを実行
uv run pytest

# 詳細出力
uv run pytest -v

# 特定のテストファイルのみ実行
uv run pytest tests/unit/test_session.py

# 特定のテスト関数のみ実行
uv run pytest tests/unit/test_session.py::test_create_session

# マーカーでフィルタリング（遅いテストを除外）
uv run pytest -m "not slow"

# 並列実行（高速化）
uv run pytest -n auto
```

#### 3.3.3 便利なコマンドオプション

##### テストの選択とフィルタリング

```bash
# キーワード式でテストをフィルタリング（柔軟な検索）
uv run pytest -k "session and not archive"  # "session"を含むが"archive"を含まない
uv run pytest -k "test_create or test_delete"  # 複数のキーワード
uv run pytest -k "session" -v  # 詳細出力付き

# マーカーでフィルタリング
uv run pytest -m "slow"  # slowマーカーが付いたテストのみ
uv run pytest -m "not slow"  # slowマーカーが付いていないテスト
uv run pytest -m "slow and integration"  # 複数マーカーの組み合わせ

# 特定のディレクトリ配下のテストのみ実行
uv run pytest tests/unit/  # ユニットテストのみ
uv run pytest tests/integration/  # 統合テストのみ
uv run pytest tests/performance/  # パフォーマンステストのみ

# 特定のクラス内のテストのみ実行
uv run pytest tests/unit/test_session.py::TestSessionManager

# 複数のテストを指定
uv run pytest tests/unit/test_session.py::test_create \
  tests/unit/test_session.py::test_delete

# パターンマッチング（ファイル名）
uv run pytest tests/unit/test_session*.py  # test_sessionで始まるファイル
```

##### 失敗したテストの再実行とデバッグ

```bash
# 前回失敗したテストのみ再実行（Last Failed）
uv run pytest --lf
# または
uv run pytest --last-failed

# 失敗したテストを最初に実行してから、残りを実行（Failed First）
uv run pytest --ff
# または
uv run pytest --failed-first

# 最初の失敗で停止
uv run pytest -x
# または
uv run pytest --exitfirst

# 指定した数の失敗で停止
uv run pytest --maxfail=3  # 3回失敗したら停止

# 失敗したテストの詳細なトレースバック表示
uv run pytest -vv  # より詳細な出力
uv run pytest --tb=short  # 短いトレースバック
uv run pytest --tb=long  # 長いトレースバック（デフォルト）
uv run pytest --tb=line  # 1行のみ
uv run pytest --tb=no  # トレースバックなし

# 失敗時にデバッガーを起動
uv run pytest --pdb  # 失敗時にpdbを起動
uv run pytest -x --pdb  # 最初の失敗で停止してpdbを起動
```

##### 出力の制御

```bash
# 静かな出力（最小限の情報のみ）
uv run pytest -q
# または
uv run pytest --quiet

# 詳細な出力
uv run pytest -v  # 各テストの結果を表示
uv run pytest -vv  # より詳細（フィクスチャ情報なども）

# print文の出力を表示（デフォルトではキャプチャされる）
uv run pytest -s
# または
uv run pytest --capture=no

# 標準出力のみキャプチャしない
uv run pytest --capture=sys  # sys.stdout/stderrのみキャプチャ
uv run pytest --capture=fd  # ファイルディスクリプタレベルでキャプチャ（デフォルト）

# テストの実行時間を表示
uv run pytest --durations=10  # 最も遅い10個のテストを表示
uv run pytest --durations=0  # すべてのテストの実行時間を表示
uv run pytest --durations=10 -v  # 詳細出力と組み合わせ

# テスト結果のサマリーを確認（パス、失敗、スキップ、警告の数）
uv run pytest  # 最後に自動的にサマリーが表示される
# 出力例:
# ===== 10 passed, 2 failed, 1 skipped, 3 warnings in 5.23s =====
# 
# 各項目の意味:
# - passed: 成功したテスト数
# - failed: 失敗したテスト数
# - skipped: スキップされたテスト数
# - warnings: 警告の数
# - 最後の数字: 実行時間

# サマリーのみを表示（トレースバックを非表示）
uv run pytest --tb=no  # トレースバックなしでサマリーに集中
uv run pytest --tb=line  # 1行のみのトレースバック

# 詳細なサマリー（各テストの結果を表示）
uv run pytest -v  # 各テストの結果を表示
uv run pytest -vv  # より詳細（フィクスチャ情報なども）

# テスト数を確認（収集のみ）
uv run pytest --collect-only -q  # 収集したテスト数を表示
# 出力例:
# ===== 25 tests collected =====
#
# より詳細な情報を表示
uv run pytest --collect-only  # 収集したテストの一覧を表示
uv run pytest --collect-only -v  # 各テストの詳細情報も表示

# 特定の結果タイプの数を確認
uv run pytest -r a  # すべての結果タイプを表示（passed, failed, skipped, xfailed, xpassed, error）
uv run pytest -r f  # 失敗のみ
uv run pytest -r s  # スキップのみ
uv run pytest -r x  # XFAIL（予期された失敗）のみ
uv run pytest -r E  # エラーのみ

# ワーニングの表示制御
uv run pytest  # デフォルトで警告が表示される
uv run pytest -W ignore  # すべての警告を無視
uv run pytest -W error  # 警告をエラーとして扱う
uv run pytest -W error::DeprecationWarning  # 特定の警告のみエラーとして扱う
uv run pytest -W default::DeprecationWarning  # 特定の警告のみデフォルト表示

# ワーニングの詳細表示
uv run pytest -W default  # すべての警告を表示（デフォルト）
uv run pytest -W always  # 警告を常に表示（重複も含む）
uv run pytest -W once  # 各警告を1回だけ表示
uv run pytest -W module  # 各モジュールごとに1回だけ表示

# サマリーをファイルに出力
uv run pytest > test_results.txt 2>&1
# または
uv run pytest --tb=short -v > test_results.txt 2>&1
```

##### テストの収集と情報表示

```bash
# テストを収集するだけで実行しない（どのテストが実行されるか確認）
uv run pytest --collect-only
# または
uv run pytest --co

# 収集したテストを詳細に表示
uv run pytest --collect-only -v

# 利用可能なフィクスチャを表示
uv run pytest --fixtures
# または
uv run pytest --fixtures -v  # 詳細な説明付き

# 特定のテストのフィクスチャを表示
uv run pytest --fixtures tests/unit/test_session.py

# マーカー一覧を表示
uv run pytest --markers

# プラグイン一覧を表示
uv run pytest --trace-config
```

##### テストの実行順序制御

```bash
# ランダムな順序で実行（テストの依存性を検出）
uv run pytest --random-order
# または
uv run pytest --random-order-seed=12345  # シードを指定して再現可能に

# テストを逆順で実行
uv run pytest --reverse

# アルファベット順で実行
uv run pytest --order=alphabetical
```

##### キャッシュとクリーンアップ

```bash
# キャッシュをクリア
uv run pytest --cache-clear

# キャッシュの情報を表示
uv run pytest --cache-show

# テスト実行後に一時ファイルをクリーンアップ
uv run pytest --cleanup  # pytest-cleanupプラグインが必要
```

##### スキップとXFAILの表示

```bash
# スキップされたテストの理由を表示
uv run pytest -rs
# または
uv run pytest -r s

# XFAIL（予期された失敗）の理由を表示
uv run pytest -rx
# または
uv run pytest -r x

# すべての理由を表示（skipped, failed, passed, xfailed, xpassed）
uv run pytest -ra

# ショートサマリーの表示オプション
uv run pytest -rN  # 表示しない（デフォルト）
uv run pytest -rf  # 失敗のみ
uv run pytest -rE  # エラーのみ
```

##### タイムアウト制御

```bash
# すべてのテストにタイムアウトを設定（pytest-timeoutプラグインが必要）
uv run pytest --timeout=300  # 300秒でタイムアウト

# 特定のテストのみタイムアウトを設定
uv run pytest --timeout=10 tests/unit/test_slow.py

# タイムアウトの方法を指定
uv run pytest --timeout=300 --timeout-method=thread  # スレッドベース
uv run pytest --timeout=300 --timeout-method=signal  # シグナルベース（デフォルト）
```

##### カバレッジとの組み合わせ

```bash
# カバレッジ測定と詳細出力
uv run pytest --cov=src/kotonoha_bot --cov-report=term-missing -v

# カバレッジと失敗したテストの再実行
uv run pytest --cov=src/kotonoha_bot --lf

# カバレッジと並列実行
uv run pytest --cov=src/kotonoha_bot -n auto

# 特定のモジュールのみカバレッジ測定
uv run pytest --cov=src/kotonoha_bot.bot --cov-report=term-missing
```

##### 実用的な組み合わせ例

```bash
# 開発中のクイックチェック（高速、詳細出力、最初の失敗で停止）
uv run pytest -x -v -k "not slow" -n auto

# デバッグモード（詳細出力、print表示、最初の失敗でpdb起動）
uv run pytest -vv -s -x --pdb

# CI相当の実行（カバレッジ、詳細出力、失敗時に停止）
uv run pytest --cov=src/kotonoha_bot --cov-report=term-missing \
  --cov-fail-under=80 -v --maxfail=1

# リファクタリング後の確認（失敗したテストを優先、詳細出力）
uv run pytest --ff -vv

# パフォーマンステストのみ実行（時間測定付き）
uv run pytest tests/performance/ --durations=0 -v

# 新しく追加したテストのみ実行（キーワードで絞り込み）
uv run pytest -k "new_feature" -v

# データベース関連テストを除外して高速実行
uv run pytest -k "not (postgres or integration)" -n auto -v
```

#### 3.3.4 並列テスト実行（pytest-xdist）

**pytest-xdist**を使用することで、テストの実行時間を大幅に短縮できる。

##### 基本的な使用方法

```bash
# CPUコア数に応じて自動的に並列実行
uv run pytest -n auto

# 指定した数のワーカーで並列実行
uv run pytest -n 4

# 並列実行とカバレッジの組み合わせ
uv run pytest -n auto --cov=src/kotonoha_bot \
  --cov-report=term-missing

# シリアル実行（並列実行を無効化）
uv run pytest -n 0  # または -n オプションを指定しない
```

##### 並列実行の注意事項

**重要**: データベース関連テストは**シリアル実行**を基本とする。

1. **データの競合を避ける**:
   - 各テストワーカーが同じデータベースを共有する場合、データの競合が発生する可能性がある
   - 現在の実装では、`postgres_db`フィクスチャが各テスト後に`TRUNCATE ... CASCADE`でクリーンアップしているが、並列実行時にはタイミングによって競合が発生する可能性がある

2. **接続プールの枯渇を防ぐ**:
   - 各テストワーカーが同じPostgreSQLインスタンスに接続する場合、接続プールのサイズに注意が必要
   - シリアル実行により、接続プールの枯渇を防ぐ

3. **テストの安定性と再現性**:
   - シリアル実行により、テストの実行順序が一定になり、再現性が向上する
   - デバッグが容易になる

##### 推奨されるテスト実行パターン

**キーワード式について**:
`-k` オプションは**キーワード式（keyword expression）**を使用してテストをフィルタリングする。
テストファイル名、テスト関数名、クラス名、ディレクトリ名などに含まれるキーワードで検索する。

- `postgres`: ファイル名やテスト名に「postgres」が含まれるテスト
  （例: `test_postgres_db.py`, `test_session_archiver.py`）
- `integration`: `tests/integration/` ディレクトリ配下のテスト
- `performance`: `tests/performance/` ディレクトリ配下のテスト

```bash
# パターン1: データベース関連テストをシリアル実行、
# それ以外をパラレル実行（推奨）
uv run pytest -k "postgres or integration or performance" -v
# シリアル実行

uv run pytest -k "not (postgres or integration or performance)" \
  -n auto -v
# パラレル実行

# パターン2: ディレクトリ単位で実行
uv run pytest tests/integration/ -v
# 統合テスト（シリアル）

uv run pytest tests/performance/ -v
# パフォーマンステスト（シリアル）

uv run pytest tests/unit/ -k "not postgres" -n auto -v
# ユニットテスト（パラレル、DB関連を除外）

# パターン3: すべてをシリアル実行（最も安全だが時間がかかる）
uv run pytest -v

# パターン4: 特定のテストマーカーで並列実行を制御
uv run pytest -k "not (postgres or integration or performance)" \
  -n auto -m "not slow" -v
```

##### パフォーマンスの目安

- **全テストをシリアル実行**: 約5-10分
- **データベース関連テストをシリアル、それ以外をパラレル実行**:
  約3-5分（約40-50%の時間短縮）
- **並列実行（4ワーカー、データベース関連を除外）**:
  約2-3分（約50-70%の時間短縮）

**注意**: データベース関連テストはシリアル実行を基本とすることで、
テストの安定性と再現性が向上する。

##### 並列実行時のトラブルシューティング

**問題**: 並列実行時にテストが失敗する

**対処法**:
- データベース関連テストを除外して並列実行:
  ```bash
  uv run pytest -k "not (postgres or integration or performance)" \
    -n auto
  ```
- ワーカー数を減らす:
  ```bash
  uv run pytest -n 2  # 4ワーカーから2ワーカーに減らす
  ```
- シリアル実行で再現性を確認:
  ```bash
  uv run pytest -n 0  # シリアル実行
  ```

**問題**: 並列実行時にカバレッジが正確に測定されない

**対処法**:
- `pytest-cov`は並列実行に対応しているが、正確な測定のためには
  シリアル実行を推奨:
  ```bash
  uv run pytest --cov=src/kotonoha_bot --cov-report=term-missing
  ```

### 3.4 pytest-cov（カバレッジ測定）

#### 3.4.1 設定概要

`pyproject.toml` で以下の設定が有効になっている：

- ソース: `src/kotonoha_bot`
- ブランチカバレッジ: 有効
- 除外行:
  - `pragma: no cover`
  - `def __repr__`
  - `raise NotImplementedError`
  - `if TYPE_CHECKING:`

#### 3.4.2 基本的な使い方

```bash
# カバレッジ測定（ターミナル出力）
uv run pytest --cov=src/kotonoha_bot --cov-report=term-missing

# カバレッジ測定（HTMLレポート生成）
uv run pytest --cov=src/kotonoha_bot --cov-report=html
# ブラウザで htmlcov/index.html を開く

# カバレッジ測定（80%未満で失敗）
uv run pytest --cov=src/kotonoha_bot \
  --cov-report=term-missing --cov-fail-under=80

# カバレッジ測定（XMLレポート生成、CI用）
uv run pytest --cov=src/kotonoha_bot --cov-report=xml
```

#### 3.4.3 カバレッジ向上のためのベストプラクティス（残存課題対応）

現在70%のカバレッジを80%以上に向上させる：

1. **カバレッジレポートの確認**：

   ```bash
   uv run pytest --cov=src/kotonoha_bot --cov-report=html
   open htmlcov/index.html
   ```

2. **カバーされていない行の特定**：

   ```bash
   uv run pytest --cov=src/kotonoha_bot \
     --cov-report=term-missing | grep "Missing"
   ```

3. **特定のファイルのカバレッジ確認**：

   ```bash
   uv run pytest --cov=src/kotonoha_bot \
     --cov-report=term-missing tests/unit/test_session.py
   ```

4. **カバレッジ除外の適切な使用**：

   ```python
   # テスト不可能なコードは除外
   if TYPE_CHECKING:  # 自動除外
       from typing import Protocol
   
   def __repr__(self) -> str:  # 自動除外
       return f"{self.__class__.__name__}()"
   
   # 意図的に除外する場合
   def experimental_feature(self):  # pragma: no cover
       pass
   ```

### 3.5 deptry（依存関係チェック）

#### 3.5.1 基本的な使い方

```bash
# 未使用の依存関係をチェック
uv run deptry .

# 詳細出力
uv run deptry . --verbose
```

**注意**: `pyproject.toml` で `known_first_party = ["kotonoha_bot"]` と
`per_rule_ignores` が設定されている。

### 3.6 pydeps（循環依存チェック）

#### 3.6.1 基本的な使い方

```bash
# 循環依存を検出
uv run pydeps src/kotonoha_bot/ --show-cycles --no-output

# 依存関係グラフを生成（SVG）
uv run pydeps src/kotonoha_bot/ --show-deps -o deps.svg
```

## 4. CI/CD との整合性

### 4.1 CI で実行されるチェック

`.github/workflows/ci.yml` で以下のチェックが自動実行される：

1. **lint ジョブ**:
   - `ruff check .`
   - `ruff format --check .`

2. **type-check ジョブ**:
   - `ty check src/`

3. **dependency-check ジョブ**:
   - `deptry .`
   - `pydeps src/kotonoha_bot/ --show-cycles --no-output`

4. **test ジョブ**:
   - `pytest --cov=src/kotonoha_bot --cov-report=xml --cov-report=term`

### 4.2 ローカルでCI相当のチェックを実行

```bash
# CI相当の全チェック
uv run ruff check . && \
uv run ruff format --check . && \
uv run ty check src/ && \
uv run deptry . && \
uv run pydeps src/kotonoha_bot/ --show-cycles --no-output && \
uv run pytest --cov=src/kotonoha_bot --cov-report=xml --cov-report=term
```

## 5. 残存課題の解決手順

### 5.1 型ヒントの完全化

**現状**: 一部のファイルで不完全

**解決手順**:

1. 型エラーを確認：

   ```bash
   uv run ty check src/ > type_errors.txt
   ```

2. エラーが発生しているファイルをリストアップ：

   ```bash
   cat type_errors.txt | grep "error:" | awk '{print $1}' | sort -u
   ```

3. ファイルごとに型ヒントを追加：
   - 関数の引数・戻り値
   - クラスの属性
   - 変数の型アノテーション（必要に応じて）

4. 再チェック：

   ```bash
   uv run ty check src/
   ```

### 5.2 docstring の完全化

**現状**: 一部の公開APIで不足

**解決手順**:

1. docstring エラーを確認：

   ```bash
   uv run ruff check src/ --select D > docstring_errors.txt
   ```

2. エラーが発生しているファイルをリストアップ：

   ```bash
   cat docstring_errors.txt | grep "D" | awk '{print $1}' | sort -u
   ```

3. ファイルごとに docstring を追加（Google Style）：
   - 関数・メソッド: 説明、Args、Returns、Raises
   - クラス: 説明、Attributes

4. 再チェック：

   ```bash
   uv run ruff check src/ --select D
   ```

### 5.3 コードフォーマット

**現状**: 13ファイルがフォーマット必要

**解決手順**:

1. フォーマットが必要なファイルを確認：

   ```bash
   uv run ruff format --check src/ tests/
   ```

2. すべてのファイルをフォーマット：

   ```bash
   uv run ruff format src/ tests/
   ```

3. 再チェック：

   ```bash
   uv run ruff format --check src/ tests/
   ```

### 5.4 型チェックエラーの解消

**現状**: 8エラー残存

**解決手順**:

1. 型エラーを確認：

   ```bash
   uv run ty check src/
   ```

2. エラーごとに修正：
   - 型ヒントの追加
   - 型の修正（`str` vs `int` など）
   - `# type: ignore` の適切な使用（最後の手段）

3. 再チェック：

   ```bash
   uv run ty check src/
   ```

### 5.5 テストカバレッジの向上

**現状**: 現在70%、目標80%未達

**解決手順**:

1. カバレッジレポートを生成：

   ```bash
   uv run pytest --cov=src/kotonoha_bot --cov-report=html
   open htmlcov/index.html
   ```

2. カバーされていないファイル・行を特定：
   - HTMLレポートで確認
   - または `--cov-report=term-missing` で確認

3. テストを追加：
   - カバーされていない関数・メソッドにテストを追加
   - エッジケースのテストを追加
   - 例外処理のテストを追加

4. カバレッジを再測定：

   ```bash
   uv run pytest --cov=src/kotonoha_bot \
     --cov-report=term-missing --cov-fail-under=80
   ```

## 6. トラブルシューティング

### 6.1 Ruff のエラーが解消されない

**問題**: `ruff check --fix` を実行してもエラーが残る

**対処法**:

- 手動で修正が必要なエラー（例: ロジックの修正）を確認
- `ruff check --select <ルールコード>` で特定のルールのみチェック
- エラーを無視する必要がある場合は、`# noqa: <ルールコード>` を追加（最小限に）

### 6.2 ty の型エラーが解消されない

**問題**: 型ヒントを追加してもエラーが残る

**対処法**:

- `ty check --verbose` で詳細なエラーメッセージを確認
- 型が複雑な場合は `typing.Protocol` や `typing.TypeVar` を活用
- どうしても解決できない場合は `# type: ignore[<エラーコード>]` を追加（コメントで理由を記載）

### 6.3 テストカバレッジが上がらない

**問題**: テストを追加してもカバレッジが上がらない

**対処法**:

- `--cov-report=html` で実際にカバーされている行を確認
- ブランチカバレッジ（`if/else` の両方）を確認
- テストが実際に実行されているか確認（`pytest -v`）

### 6.4 CI で失敗するがローカルでは成功する

**問題**: ローカルではチェックが通過するが、CI で失敗する

**対処法**:

- CI と同じコマンドをローカルで実行
- 依存関係のバージョンを確認（`uv.lock` が最新か）
- 環境変数の違いを確認

### 6.5 よくある Ruff エラーと対処法

#### ARG001, ARG002: 未使用の関数・メソッド引数

**エラー例**:

```text
ARG001 Unused function argument: `session_key`
ARG002 Unused method argument: `handler`
```

**対処法**:

- 引数が本当に不要な場合: 引数を削除する
- 引数が必要だが未使用の場合（テストのフィクスチャなど）: 引数名を `_` に変更する

  ```python
  # 修正前
  async def test_example(self, handler):
      pass
  
  # 修正後
  async def test_example(self, _handler):
      pass
  ```

- pytest のフィクスチャで未使用の場合: 引数名の前に `_` を付けるか、`# noqa: ARG002` を追加

#### F841: 未使用のローカル変数

**エラー例**:

```text
F841 Local variable `result` is assigned to but never used
```

**対処法**:

- 変数が本当に不要な場合: 代入を削除する

  ```python
  # 修正前
  result = await some_function()
  
  # 修正後（戻り値が不要な場合）
  await some_function()
  ```

- 変数が必要だが未使用の場合: 変数名を `_` に変更する

  ```python
  # 修正前
  synced = await mock_bot.tree.sync()
  
  # 修正後
  _synced = await mock_bot.tree.sync()
  ```

#### SIM105: try-except-pass の簡略化

**エラー例**:

```text
SIM105 Use `contextlib.suppress(TimeoutError, asyncio.CancelledError)` \
  instead of `try`-`except`-`pass`
```

**対処法**:

```python
# 修正前
try:
    await some_function()
except (TimeoutError, asyncio.CancelledError):
    pass

# 修正後
from contextlib import suppress

with suppress(TimeoutError, asyncio.CancelledError):
    await some_function()
```

#### SIM108: if-else ブロックの三項演算子化

**エラー例**:

```text
SIM108 Use ternary operator instead of `if`-`else`-block
```

**対処法**:

```python
# 修正前
if len(args) >= 3:
    content = args[2]
else:
    content = kwargs.get("content", "")

# 修正後
content = args[2] if len(args) >= 3 else kwargs.get("content", "")
```

#### SIM117: ネストした with 文の統合

**エラー例**:

```text
SIM117 Use a single `with` statement with multiple contexts \
  instead of nested `with` statements
```

**対処法**:

```python
# 修正前
with patch("pathlib.Path.exists", return_value=True):
    with patch("pathlib.Path.read_text", return_value=content):
        result = _load_prompt_from_markdown("test.md")

# 修正後
with (
    patch("pathlib.Path.exists", return_value=True),
    patch("pathlib.Path.read_text", return_value=content),
):
    result = _load_prompt_from_markdown("test.md")
```

#### B007: 未使用のループ変数

**エラー例**:

```text
B007 Loop control variable `call` not used within loop body
```

**対処法**:

```python
# 修正前
for call in mock_bot.event.call_args_list:
    pass

# 修正後
for _call in mock_bot.event.call_args_list:
    pass
```

#### 自動修正できないエラーの対処

**問題**: `ruff check --fix` を実行してもエラーが残る

**対処法**:

1. **`--unsafe-fixes` オプションを使用**（注意深く確認してから）:

   ```bash
   uv run ruff check src/ tests/ --fix --unsafe-fixes
   ```

2. **手動で修正**: エラーメッセージの `help:` セクションに従って手動で修正

3. **エラーを無視する場合**（最後の手段）:

   ```python
   # 特定の行のみ無視
   result = await some_function()  # noqa: F841
   
   # 特定のルールを無視
   async def test_example(self, handler):  # noqa: ARG002
       pass
   ```

## 7. ベストプラクティスまとめ

### 7.1 コミット前のチェックリスト

- [ ] `ruff format src/ tests/` を実行
- [ ] `ruff check src/ tests/ --fix` を実行
- [ ] `ty check src/` を実行（エラーなし）
- [ ] `pytest --cov=src/kotonoha_bot --cov-report=term-missing` を実行（全テスト通過）
- [ ] カバレッジが80%以上であることを確認

### 7.2 定期的なメンテナンス

- **週次**: カバレッジレポートを確認し、低下していないか確認
- **月次**: 依存関係の更新と `deptry` による未使用依存関係の確認
- **リリース前**: CI相当の全チェックを実行

### 7.3 チーム開発での推奨事項

- プルリクエスト作成前に `check-all` エイリアスを実行
- CI の失敗をローカルで再現してから修正
- 型エラーやリントエラーは早期に修正（技術的負債の蓄積を防ぐ）

## 8. 参考リンク

- [Ruff 公式ドキュメント](https://docs.astral.sh/ruff/)
- [ty 公式ドキュメント](https://github.com/typeddjango/ty)
- [pytest 公式ドキュメント](https://docs.pytest.org/)
- [coverage.py 公式ドキュメント](https://coverage.readthedocs.io/)
- [Google Style Guide (docstring)](
  https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
