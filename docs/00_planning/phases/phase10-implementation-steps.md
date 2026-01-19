# Phase 10: 完全リファクタリング - 詳細実装計画

Phase 10 の各ステップ（Step 0-7）の詳細な実装手順とコード例を記載したドキュメント

**作成日**: 2026年1月19日  
**バージョン**: 2.0  
**対象プロジェクト**: kotonoha-bot v0.9.0  

**関連ドキュメント**:

- [Phase 10 基本方針](./phase10.md): リファクタリングの基本方針、目標、概要
- [Phase 10 実装ガイド（メイン）](./phase10-implementation.md): コーディング規約、リファクタリング方針、新フォルダ構造
- [Phase 10 テスト・完了基準・リスク管理](./phase10-implementation-testing.md): テストコードリファクタリング、完了基準、リスク管理、改善提案

---

## 6. 詳細実装計画

### 6.1 実装ステップ概要（コンポーネント単位の垂直統合移行）

**基本方針**: レイヤーごとに「実装移動 → テスト修正」をセットで行う。常に「コンパイル（型チェック）が通り、テストも通る」状態を維持し、手戻りを最小化する。

**詳細な修正版ロードマップ（推奨）**:

| Day | Step | 内容 | 期間 |
|-----|------|------|------|
| **Day 1** | 0 | 依存方向の確定（循環参照の防止） | 0.5日 |
| | 1 | **足場固め**: config.py (Pydantic化) + utils/, errors/ の作成・移動 → 即座に単体テスト移行・実行（Greenにする） | 0.5日 |
| **Day 2-3** | 2 | **データ層とビジネスロジック**: db/ の移動 + services/session.py の作成 → テスト移行・実行（Greenにする）+ テストファクトリー（SessionFactory）作成 | 2日 |
| **Day 4-5** | 3 | **AIサービスと抽象化**: services/ai.py の統合、例外ラッピング、戻り値変更 → テスト移行・実行（Greenにする）+ AI周りのモック戦略確定 | 2日 |
| **Day 6-7** | 4 | **プレゼンテーション層（最大の山場）**: bot/handlers/ の物理分割と setup_handlers (DI) の実装 → テスト移行・実行（Greenにする） | 2日 |
| **Day 8** | 5 | **結合と仕上げ**: main.py の実装、Graceful Shutdown、インポートパスの最終確認 | 0.5日 |
| | 6 | **結合テスト**: E2E的な動作確認 | 0.5日 |
| **Day 9** | 7 | **品質向上**: 型ヒント・docstring の完全化（ty check --strict） | 1日 |
| **合計** | | | **9日** |

**移行フローの説明（詳細な修正版ロードマップ）**:

1. **Day 1: 足場固め**（Step 0-1）:
   - Step 0: 依存方向の確定
   - Step 1: config.py (Pydantic化) + utils/, errors/ の作成・移動
   - **ここで tests/unit/utils/, tests/unit/errors/ も同時に移行し、Greenにする**

2. **Day 2-3: データ層とビジネスロジック**（Step 2）:
   - db/ の移動と services/session.py の作成
   - **tests/unit/db/, tests/unit/services/test_session.py を移行し、Greenにする**
   - **テストファクトリー (SessionFactory) はここで作る**

3. **Day 4-5: AIサービスと抽象化**（Step 3）:
   - services/ai.py の統合、例外ラッピング、戻り値変更
   - **tests/unit/services/test_ai.py を移行し、Greenにする**
   - **ここで AI 周りのモック戦略（例外を投げるモックなど）を確定させる**

4. **Day 6-7: プレゼンテーション層（最大の山場）**（Step 4）:
   - **ここで初めて handlers.py を解体する**
   - bot/handlers/ の物理分割と setup_handlers (DI) の実装
   - **tests/unit/bot/ を移行。ここが一番重いが、下層（Service/DB）はテスト済みなので、モックを使ったハンドラーのテストに集中できる**

5. **Day 8: 結合と仕上げ**（Step 5-6）:
   - Step 5: main.py の実装、Graceful Shutdown、インポートパスの最終確認
   - Step 6: 結合テスト、E2E的な動作確認

6. **Day 9: 品質向上**（Step 7）:
   - 型ヒント・docstring の完全化（ty check --strict）

**メリット**:

- 常に「コンパイル（型チェック）が通り、テストも通る」状態を維持
- 手戻りを最小化
- 各コンポーネントの完成度を段階的に確認可能
- 問題の早期発見が可能

### 6.2 Step 0: 依存方向の確定（Day 1、0.5日）

**目的**: 各モジュール間の import 関係を図示し、循環参照がないか確認する

**重要**: コードレビューで指摘された「依存関係の方向性の明確化」を確実に実施する。特に `services/ai.py` と `services/session.py` の相互依存を避けることが重要。

**リファクタリング・ワークフロー**:

依存関係の分析と設計レビューの後に、以下のコマンドで即座にチェックする:

```bash
# ワンライナーで全チェック（Ruff + ty）
uv run ruff check src/ && uv run ty check src/
```

- 循環参照を即座に検出（ty が親切なエラーメッセージを表示）
- インポートエラーを即座に検出
- エラーメッセージに従って設計を修正

**実施内容**:

1. **依存関係グラフの生成**:

   ```bash
   # 現在の依存関係を可視化
   uv run pydeps src/kotonoha_bot/ --show-deps -T svg -o deps_before.svg
   
   # 循環依存を検出
   uv run pydeps src/kotonoha_bot/ --show-cycles
   ```

2. **依存関係の方向性ルールを文書化**:
   - `services/ai.py` → `services/session.py` への依存は禁止
   - `services/session.py` → `services/ai.py` への依存は禁止
   - handlers 層が両方を統合（DI パターン）
   - **重要**: 循環参照を防止するため、依存の方向性を一方向に保つ

3. **依存関係マトリクスの作成**:

   | モジュール | 依存先 | 許可/禁止 |
   |-----------|--------|----------|
   | `services/ai.py` | `services/session.py` | ❌ 禁止 |
   | `services/session.py` | `services/ai.py` | ❌ 禁止 |
   | `bot/handlers.py` | `services/ai.py`, `services/session.py` | ✅ 許可 |
   | `services/eavesdrop.py` | `services/ai.py` | ✅ 許可 |

4. **設計レビュー**:
   - 循環参照のリスクがある箇所を特定
   - 必要に応じて設計を修正

5. **テスト汚染コードの検出**（新規追加）:
   - `src/` 以下の全文検索でテスト汚染コードを検出

   ```bash
   # テスト汚染コードの検出
   grep -r "test\|mock\|debug\|dummy" src/ --include="*.py" | grep -v "test_" | grep -v "__pycache__"
   ```

   - 検出した箇所をリストアップし、各Stepで解消する

6. **不要な依存関係の特定**（deptry を使用）:

   ```bash
   # 実はもう使っていないライブラリを特定
   uv run deptry .
   ```

   **効果**: numpy や langchain-text-splitters など、本当にコード内でインポートされているかを検査し、不要なら `pyproject.toml` から削除する根拠になります。

   **削除検討項目**:
   - **`psycopg2-binary`**: メインは `asyncpg` を使用しています。alembic の移行スクリプトも非同期設定にしている場合、同期的なDB操作が完全にないか確認し、不要なら削除してコンテナサイズを軽量化します。
     - 確認方法: `grep -r "psycopg2\|psycopg" src/ --include="*.py"` で使用箇所を確認
     - alembic の設定が非同期の場合、削除可能な可能性が高い
   - **`langchain-text-splitters`**: もし「長いメッセージを分割してDiscordに送る」ためだけに使っているなら、tiktoken（トークンカウント用に入っています）や単純な文字数分割で十分かもしれません。依存を減らすチャンスです。

**完了基準**:

- [ ] 依存関係グラフが生成されている
- [ ] 循環依存が検出されていない（特に `services/ai.py` と `services/session.py` の相互依存がないことを確認）
- [ ] 依存関係の方向性ルールが文書化されている
- [ ] 設計レビューが完了している
- [ ] 循環参照のリスクがある箇所が特定され、対策が決定されている
- [ ] テスト汚染コードの検出が完了し、解消計画が作成されている
- [ ] **不要な依存関係の特定が完了している（deptry を使用）**
- [ ] **`psycopg2-binary` の削除検討が完了している（asyncpg のみで動作することを確認）**

**注**: deptry は既に dev 依存関係に含まれています。

**注**: `psycopg2-binary` の削除は、alembic の非同期設定が完了していることを前提とします。削除後は `asyncpg` のみで動作することを確認してください。

### 6.3 Step 1: 足場固め - config.py (Pydantic化) + utils/, errors/ の作成・移動（Day 1、0.5日）

**基本方針**: Day 1 の後半で、config.py の Pydantic化と utils/, errors/ の作成・移動を実施し、対応するテストも同時に移行・実行する。常に「型チェックが通り、テストも通る」状態を維持する。

**リファクタリング・ワークフロー**:

各コンポーネントの作成・移動後に、以下のコマンドで即座にチェックする:

```bash
# ワンライナーで全チェック（Ruff + ty）
uv run ruff check src/ && uv run ty check src/

# 対応するテストを実行（Greenにする）
uv run pytest tests/unit/utils/ tests/unit/errors/ -v
```

**TDDサイクルの高速化（pytest-watcher を使用）**:

ファイル変更を検知してテストを自動実行する `pytest-watcher` があると、Step 1〜6 のリズムが良くなります。

```bash
# pytest-watcher は既に dev 依存関係に含まれています

# ファイルを保存するたびにテストが走る
uv run ptw .
```

- Ruff が Docstring の不足やインポート順序を指摘
- ty が型の不整合やインポートエラーを指摘
- テストが通過することを確認（Greenにする）
- エラーメッセージに従って修正

#### 6.3.1 config.py の Pydantic化

**実施内容**:

1. **Config クラスの Pydantic V2 化**:
   - Pydantic V2 の `model_config = SettingsConfigDict(...)` を使用
   - `get_config()` 関数は main.py でのみ使用（後方互換性のため）

   **実装例**:

   ```python
   # config.py
   from pydantic_settings import BaseSettings, SettingsConfigDict
   from pathlib import Path

   class Config(BaseSettings):
       """アプリケーション設定（Pydantic V2）"""
       discord_token: str
       anthropic_api_key: str
       openai_api_key: str
       llm_model: str = "claude-sonnet-4-5"
       database_path: Path = Path("./data/sessions.db")
       log_level: str = "INFO"
       # ... その他の設定
       
       model_config = SettingsConfigDict(
           env_file=".env",
           env_file_encoding="utf-8",
           extra="ignore"  # 余計な環境変数があってもエラーにしない
       )

   # グローバルインスタンス（main.py でのみ使用）
   _config_instance: Config | None = None

   def get_config() -> Config:
       """設定インスタンスを取得（main.py でのみ使用）
       
       Note:
           テスト容易性のため、main.py 以外では使用しないこと。
           全てのクラスはコンストラクタで config を受け取る。
       """
       global _config_instance
       if _config_instance is None:
           _config_instance = Config()
       return _config_instance
   ```

2. **チェック**:

   ```bash
   uv run ruff check src/kotonoha_bot/config.py && uv run ty check src/kotonoha_bot/config.py
   ```

#### 6.3.2 `utils/datetime.py` の作成

```python
"""日付・時刻ユーティリティ"""

from datetime import datetime

WEEKDAY_NAMES_JA = ["月", "火", "水", "木", "金", "土", "日"]


def format_datetime_for_prompt() -> str:
    """システムプロンプト用の現在日時情報を生成"""
    now = datetime.now()
    return (
        f"\n\n【現在の日付情報】\n"
        f"現在の日時: {now.strftime('%Y年%m月%d日 %H:%M:%S')}\n"
        f"今日の曜日: {WEEKDAY_NAMES_JA[now.weekday()]}曜日\n"
        f"日付や曜日に関する質問には、この情報を基に具体的に回答してください。"
        f"プレースホルダー（[明日の曜日]など）は使用せず、実際の日付や曜日を回答してください。"
    )
```

#### 6.3.3 `errors/messages.py` の作成

```python
"""ユーザー向けメッセージ定義（一元管理）"""


class ErrorMessages:
    """エラーメッセージ"""

    GENERIC = (
        "すみません。一時的に反応できませんでした。\n"
        "少し時間をおいて、もう一度試してみてください。"
    )
    PERMISSION = "すみません。必要な権限がありません。\nサーバー管理者にご確認ください。"
    RATE_LIMIT = "すみません。リクエストが多すぎるため、\nしばらく待ってから再度お試しください。"
    NOT_FOUND = "すみません。リソースが見つかりませんでした。"
    DISCORD_SERVER = "すみません。Discord サーバーで問題が発生しています。\nしばらく待ってから再度お試しください。"
    DB_LOCKED = "すみません。データベースが一時的に使用中です。\nしばらく待ってから再度お試しください。"
    DB_ERROR = "すみません。データベースで問題が発生しました。\n少し時間をおいて、もう一度試してみてください。"


class CommandMessages:
    """コマンド応答メッセージ"""

    RESET_SUCCESS = "会話履歴をリセットしました。\n新しい会話として始めましょう。"
    RESET_NOT_FOUND = "会話履歴が見つかりませんでした。"
    EAVESDROP_CLEARED = "✅ 会話ログバッファをクリアしました。"
    EAVESDROP_USAGE = (
        "使用方法:\n"
        "`!eavesdrop clear` - 会話ログバッファをクリア\n"
        "`!eavesdrop status` - バッファ状態を表示"
    )
```

#### 6.3.4 `utils/message.py`（統合）

```python
"""メッセージ処理ユーティリティ"""

# message_formatter.py と message_splitter.py を統合
# 既存のコードをそのまま1ファイルにまとめる
```

**注**: Step 1 で utils/, errors/ の作成・移動とテスト移行を実施するため、このセクションは Step 1 に統合済み。

**リファクタリング・ワークフロー**:

各コンポーネントの移動後に、以下のコマンドで即座にチェックする:

```bash
# ワンライナーで全チェック（Ruff + ty）
uv run ruff check src/ && uv run ty check src/

# 対応するテストを実行
uv run pytest tests/unit/utils/ tests/unit/errors/ -v
```

- Ruff が Docstring の不足やインポート順序を指摘
- ty が型の不整合やインポートエラーを指摘
- テストが通過することを確認
- エラーメッセージに従って修正

#### 6.3.1 utils/ の移動とテスト移行

**実施内容**:

1. **ファイル移動・統合**:

   ```bash
   # utils/ ディレクトリは既に存在するため、ファイルを移動・統合
   # message_formatter.py + message_splitter.py → utils/message.py
   # ai/prompts.py → utils/prompts.py
   # utils/datetime.py は Step 1 で作成済み
   ```

2. **インポートパスの更新**:
   - `utils/message.py`, `utils/prompts.py`, `utils/datetime.py` を使用している箇所のインポートパスを更新
   - `from ..utils.message import ...` の形式に統一

3. **テストの移行・実行**:

   ```bash
   # テストファイルを移動
   mv tests/unit/test_message_formatter.py tests/unit/utils/test_message.py
   mv tests/unit/test_message_splitter.py tests/unit/utils/test_message.py  # 統合
   mv tests/unit/test_prompts.py tests/unit/utils/test_prompts.py  # 存在する場合
   # utils/datetime.py のテストは新規作成
   
   # テストを実行して通過を確認
   uv run pytest tests/unit/utils/ -v
   ```

4. **チェック**:

   ```bash
   uv run ruff check src/kotonoha_bot/utils/ && uv run ty check src/kotonoha_bot/utils/
   uv run pytest tests/unit/utils/ -v
   ```

#### 6.3.2 errors/ の移動とテスト移行

**実施内容**:

1. **ファイル移動・統合**:

   ```bash
   # errors/ ディレクトリは既に存在するため、ファイルをリネーム・追加
   mv errors/discord_errors.py errors/discord.py
   mv errors/database_errors.py errors/database.py
   # errors/messages.py は Step 1 で作成済み
   # errors/ai.py は Step 3 で作成（例外ラッピングのため）
   ```

2. **インポートパスの更新**:
   - `errors/discord.py`, `errors/database.py`, `errors/messages.py` を使用している箇所のインポートパスを更新
   - `from ..errors.discord import ...` の形式に統一

3. **テストの移行・実行**:

   ```bash
   # テストファイルを移動（存在する場合）
   mv tests/unit/test_errors.py tests/unit/errors/test_errors.py
   # errors/messages.py のテストは新規作成
   
   # テストを実行して通過を確認
   uv run pytest tests/unit/errors/ -v
   ```

4. **チェック**:

   ```bash
   uv run ruff check src/kotonoha_bot/errors/ && uv run ty check src/kotonoha_bot/errors/
   uv run pytest tests/unit/errors/ -v
   ```

**完了基準**:

- [ ] `utils/` のファイル移動・統合が完了している
- [ ] `errors/` のファイル移動・統合が完了している
- [ ] インポートパスが更新されている
- [ ] 対応するテストが移行されている
- [ ] `ruff check` と `ty check` が通過している
- [ ] 対応するテストが通過している

### 6.4 Step 2: データ層とビジネスロジック - db/ の移動 + services/session.py の作成（Day 2-3、2日）

**基本方針**: db/ の移動と services/session.py の作成を実施し、対応するテストも同時に移行・実行する。テストファクトリー（SessionFactory）もここで作成する。常に「型チェックが通り、テストも通る」状態を維持する。

**リファクタリング・ワークフロー**:

db/ の移動後に、以下のコマンドで即座にチェックする:

```bash
# ワンライナーで全チェック（Ruff + ty）
uv run ruff check src/kotonoha_bot/db/ && uv run ty check src/kotonoha_bot/db/

# 対応するテストを実行
uv run pytest tests/unit/db/ -v
```

- Ruff が Docstring の不足やインポート順序を指摘
- ty が型の不整合やインポートエラーを指摘
- テストが通過することを確認
- エラーメッセージに従って修正

#### 6.4.1 db/ の移動とテスト移行

**実施内容**:

1. **ファイル移動**:

   ```bash
   # session/models.py → db/models.py
   mv session/models.py db/models.py
   # db/postgres.py は既に存在（そのまま維持）
   # 注: Phase 8 で PostgreSQL に移行済みのため、db/sqlite.py は参照しない
   ```

2. **インポートパスの更新**:
   - `db/models.py` を使用している箇所のインポートパスを更新
   - `from ..db.models import ...` の形式に統一
   - `session/models` への参照をすべて `db.models` に変更

3. **テストの移行・実行（Greenにする）**:

   ```bash
   # テストファイルを移動
   mv tests/unit/test_db.py tests/unit/db/test_postgres.py  # PostgreSQL 用テスト
   mv tests/unit/test_models.py tests/unit/db/test_models.py  # 存在する場合
   # または新規作成
   
   # テストを実行して通過を確認（Greenにする）
   uv run pytest tests/unit/db/ -v
   ```

4. **チェック**:

   ```bash
   uv run ruff check src/kotonoha_bot/db/ && uv run ty check src/kotonoha_bot/db/
   uv run pytest tests/unit/db/ -v
   ```

#### 6.4.2 services/session.py の作成とテスト移行

**実施内容**:

1. **ディレクトリ作成とファイル移動**:

   ```bash
   mkdir -p src/kotonoha_bot/services
   # session/manager.py → services/session.py
   mv session/manager.py services/session.py
   ```

2. **初期化状態の公開API化**:

   **重要**: Step 4 で `setup_handlers` 内で初期化チェックを行う際、プライベート属性（`_initialized`）を直接チェックするのではなく、公開プロパティを使用することを推奨します。

   ```python
   # services/session.py
   from ..db.base import DatabaseProtocol
   
   class SessionManager:
       def __init__(self, db: DatabaseProtocol, config: Config):
           self.db = db
           self.config = config
           self._initialized = False
           # ... その他の初期化
       
       @property
       def is_initialized(self) -> bool:
           """初期化済みかどうかを返す（公開API）
           
           Returns:
               初期化済みの場合は True、未初期化の場合は False
           """
           return self._initialized
       
       async def initialize(self) -> None:
           """セッションマネージャーを初期化する"""
           # 初期化処理
           self._initialized = True
   ```

3. **インポートパスの更新**:
   - `from ..session.manager import SessionManager` → `from ..services.session import SessionManager`
   - `db.models` のインポートパスも更新

4. **テストの移行・実行（Greenにする）**:

   ```bash
   # テストファイルを移動
   mv tests/unit/test_session.py tests/unit/services/test_session.py
   
   # テストを実行して通過を確認（Greenにする）
   uv run pytest tests/unit/services/test_session.py -v
   ```

5. **チェック**:

   ```bash
   uv run ruff check src/kotonoha_bot/services/ && uv run ty check src/kotonoha_bot/services/
   uv run pytest tests/unit/services/test_session.py -v
   ```

#### 6.4.3 テストファクトリー（SessionFactory）の作成（polyfactory を使用）

**実施内容**:

1. **polyfactory を使用したテストファクトリーの作成**:

   **メリット**: Pydanticモデルやdataclassから、ランダムなテストデータを自動生成してくれます。手書きコードを9割削減できます。

   ```python
   # tests/fixtures/factories.py（新規作成）
   """テストデータファクトリー（polyfactory を使用）"""

   from polyfactory.factories.pydantic_factory import ModelFactory
   from kotonoha_bot.db.models import ChatSession, MessageRole
   from datetime import datetime

   class SessionFactory(ModelFactory[ChatSession]):
       """ChatSession のテストデータを生成（polyfactory を使用）
       
       Note:
           polyfactory が型ヒントを解析して、自動的にランダムな値を埋めてくれます。
           特定の値だけ固定したい場合のみ記述します。
       """
       __model__ = ChatSession
       
       # デフォルト値を固定したい場合のみ記述
       session_key: str = "test_session_123"
       session_type: str = "mention"
       channel_id: int = 123456789
       user_id: int = 987654321
       created_at: datetime = datetime.now()
       last_active_at: datetime = datetime.now()
       
       @classmethod
       def create_with_history(
           cls,
           session_key: str,
           message_count: int = 5,
       ) -> ChatSession:
           """会話履歴を持つ ChatSession を生成"""
           messages = []
           for i in range(message_count):
               role = MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT
               messages.append({
                   "role": role,
                   "content": f"メッセージ {i+1}",
                   "timestamp": datetime.now().isoformat(),
               })
           
           return cls.build(
               session_key=session_key,
               messages=messages,
           )
   ```

   **従来の手書きコードとの比較**:

   ```python
   # ❌ 従来の手書きコード（50行以上）
   class SessionFactory:
       @staticmethod
       def create(...):
           # 大量の手書きコード
           pass
   
   # ✅ polyfactory を使用（10行程度）
   class SessionFactory(ModelFactory[ChatSession]):
       __model__ = ChatSession
       # 特定の値だけ固定したい場合のみ記述
   ```

2. **テストでの使用例**:

   ```python
   # tests/unit/services/test_session.py
   from tests.fixtures.factories import SessionFactory

   def test_session_loading():
       # ランダムなデータを持つインスタンスが即座に手に入る
       session = SessionFactory.build()  # polyfactory の build() メソッド
       
       # 特定の値だけ固定したい場合
       session = SessionFactory.build(session_key="test_123", channel_id=999)
       
       # 会話履歴を持つセッション
       session = SessionFactory.create_with_history("test_123", message_count=10)
       # テスト実行...
   ```

3. **テストフィクスチャでの使用**:

   ```python
   # tests/conftest.py
   @pytest.fixture(scope="function")  # 明示的に function スコープを指定
   async def session_manager(memory_db):
       """SessionManager のフィクスチャ（メモリDB使用）
       
       Note:
           scope="function" を明示的に指定することで、テストごと（関数ごと）に
           作成・破棄されることを保証します。scope="session" にしないよう注意してください
           （非同期テストでハマる原因No.1です）。
       """
       from kotonoha_bot.services.session import SessionManager
       manager = SessionManager(memory_db)  # DIパターン
       manager.sessions = {}  # セッション辞書をクリア
       await manager.initialize()
       yield manager
       # クリーンアップ処理（必要に応じて）
   ```

**完了基準**:

- [ ] `db/models.py` の移動が完了している
- [ ] `services/session.py` の移動が完了している
- [ ] **`SessionManager` に `is_initialized` プロパティが追加されている（初期化状態の公開API化）**
- [ ] インポートパスが更新されている（`session/models` → `db.models`, `session/manager` → `services.session`）
- [ ] 対応するテストが移行されている
- [ ] **テストが通過している（Green）**
- [ ] **テストファクトリー（SessionFactory）が polyfactory を使用して作成されている（手書きコードを9割削減）**
- [ ] **テストフィクスチャが `scope="function"` で定義されている（`scope="session"` にしていない）**
- [ ] `ruff check` と `ty check` が通過している

**注**: polyfactory は既に dev 依存関係に含まれているため、追加のインストールは不要です。

### 6.5 Step 3: AIサービスと抽象化 - services/ai.py の統合、例外ラッピング、戻り値変更（Day 4-5、2日）

**基本方針**: services/ai.py の統合、例外ラッピング、戻り値変更を実施し、対応するテストも同時に移行・実行する。AI周りのモック戦略（例外を投げるモックなど）を確定させる。常に「型チェックが通り、テストも通る」状態を維持する。

**リファクタリング・ワークフロー**:

各サービスの移動・統合後に、以下のコマンドで即座にチェックする:

```bash
# ワンライナーで全チェック（Ruff + ty）
uv run ruff check src/kotonoha_bot/services/ && uv run ty check src/kotonoha_bot/services/

# 対応するテストを実行
uv run pytest tests/unit/services/ -v
```

- Ruff が Docstring の不足やインポート順序を指摘
- ty が型の不整合やインポートエラーを指摘
- テストが通過することを確認
- エラーメッセージに従って修正

#### 6.5.1 services/ai.py の統合と例外ラッピング

**実施内容**:

1. **ファイル統合**:
   - `ai/provider.py` と `ai/anthropic_provider.py` を `services/ai.py` に統合
   - `AIProvider` 抽象クラスと `AnthropicProvider` 実装クラスを1ファイルにまとめる

2. **戻り値の変更**:
   - `generate_response` の戻り値を `tuple[str, dict]` から `tuple[str, TokenInfo]` に変更
   - `TokenInfo` dataclass を定義（`frozen=True, kw_only=True` を使用）

   **実装例**:

   ```python
   # services/ai.py
   from dataclasses import dataclass

   @dataclass(frozen=True, kw_only=True)
   class TokenInfo:
       """トークン使用情報
       
       Attributes:
           input_tokens: 入力トークン数
           output_tokens: 出力トークン数
           total_tokens: 合計トークン数
           model_used: 使用したモデル名
           latency_ms: レイテンシ（ミリ秒）
       
       Note:
           将来的に services/types.py に移動する可能性があります。
           現在は services/ai.py でのみ使用されていますが、Phase 13/14（コスト管理・監査ログ）で
           他のモジュールからも使用される予定です。
       """
       input_tokens: int
       output_tokens: int
       total_tokens: int
       model_used: str
       latency_ms: int
       
       def __str__(self) -> str:
           """ログ用の文字列表現"""
           return (
               f"TokenInfo(model={self.model_used}, "
               f"input={self.input_tokens}, output={self.output_tokens}, "
               f"total={self.total_tokens}, latency={self.latency_ms}ms)"
           )
   ```

   **重要**: `kw_only=True` (Python 3.10+) をつけると、初期化時の引数間違いを防ぎやすくなります。

   ```python
   # ❌ エラー: 位置引数は使用できない
   token_info = TokenInfo(100, 200, 300, "claude-sonnet-4-5", 500)

   # ✅ 正しい: キーワード引数のみ
   token_info = TokenInfo(
       input_tokens=100,
       output_tokens=200,
       total_tokens=300,
       model_used="claude-sonnet-4-5",
       latency_ms=500
   )
   ```

3. **リトライ処理の実装（tenacity を使用）**:

   **メリット**: 手書きのリトライロジックを削除し、tenacity デコレータで置き換えることでコードを削減できます。

   **重要: 例外ラッピングとTenacityの順序**:

   Tenacity はデコレータとして動作するため、メソッド内部の try-except でラッピングされた後の例外（`AIRateLimitError`）を catch する設定になっている必要があります。

   **正しい順序**: メソッド内で `AnthropicError` → `AIRateLimitError` に変換して raise → Tenacity が `AIRateLimitError` を検知してリトライ。

   ```python
   # services/ai.py
   from tenacity import (
       retry,
       stop_after_attempt,
       wait_exponential,
       retry_if_exception_type,
   )
   from kotonoha_bot.errors.ai import AIRateLimitError
   import anthropic

   class AnthropicProvider:
       @retry(
           stop=stop_after_attempt(3),
           wait=wait_exponential(multiplier=1, min=4, max=10),
           retry=retry_if_exception_type(AIRateLimitError),  # ラッピング後の例外を指定
           reraise=True,
       )
       async def generate_response(self, ...):
           """AIプロバイダーを使用して応答を生成する。
           
           Note:
               リトライ処理は tenacity デコレータで自動的に行われます。
               メソッド内で例外をラッピングしてから raise することで、
               Tenacity が正しくリトライを実行します。
           """
           try:
               # Anthropic SDK の呼び出し
               response = await self.client.messages.create(...)
           except anthropic.RateLimitError as e:
               # 例外をラッピングしてから raise（Tenacity がこれを検知）
               raise AIRateLimitError(f"レート制限: {e}") from e
           # その他の例外も同様にラッピング
   ```

   **従来の手書きコードとの比較**:

   ```python
   # ❌ 従来の手書きリトライロジック（30行以上）
   async def generate_response(self, ...):
       for attempt in range(3):
           try:
               # 呼び出し処理
               pass
           except AIRateLimitError:
               if attempt < 2:
                   await asyncio.sleep(2 ** attempt)
                   continue
               raise
   
   # ✅ tenacity を使用（デコレータ1行）
   @retry(...)
   async def generate_response(self, ...):
       # 純粋な呼び出し処理だけ
       pass
   ```

4. **例外のラッピング**:
   - `errors/ai.py` を作成（`AIError`, `AIAuthenticationError`, `AIRateLimitError`, `AIServiceError`）
   - `AnthropicProvider` で Anthropic SDK の例外を独自例外にラッピング

5. **API キーの取得方法の統一**:
   - `AnthropicProvider` が `Config` インスタンスから API キーを取得するように修正
   - 環境変数から直接取得するコードを削除

6. **テストの移行・実行（Greenにする）**:

   ```bash
   # テストファイルを移動
   mv tests/unit/test_anthropic_provider.py tests/unit/services/test_ai.py
   mv tests/integration/test_ai_provider.py tests/integration/test_services_ai.py  # 存在する場合
   
   # テストを実行して通過を確認（Greenにする）
   uv run pytest tests/unit/services/test_ai.py -v
   ```

7. **AI周りのモック戦略の確定**:
   - 例外を投げるモックの作成方法を確定
   - テストで使用するモックパターンを文書化

   **実装例**:

   ```python
   # tests/fixtures/ai.py（新規作成）
   """AI関連のモック"""

   from unittest.mock import AsyncMock
   from kotonoha_bot.errors.ai import AIAuthenticationError, AIRateLimitError, AIServiceError

   class MockAnthropicProvider:
       """AnthropicProvider のモック"""
       
       def __init__(self, should_raise: Exception | None = None):
           self.should_raise = should_raise
           self.generate_response = AsyncMock()
           
           if should_raise:
               self.generate_response.side_effect = should_raise
           else:
               self.generate_response.return_value = ("test response", TokenInfo(...))
   ```

#### 6.5.2 services/eavesdrop.py の統合（推奨: Step 3 で実施）

**推奨理由**: Step 4 は「ハンドラー分割」という最大の山場であり、ここでロジック層（Service）の変更まで混ぜるとデバッグが困難になります。Step 3（ビジネスロジック層の整理）で eavesdrop も片付けておくと、Step 4 は純粋にプレゼンテーション層の分割に集中できます。

**実施内容**:

1. **ファイル統合**:
   - `eavesdrop/llm_judge.py` と `eavesdrop/conversation_buffer.py` を `services/eavesdrop.py` に統合
   - `LLMJudge` と `ConversationBuffer` を1ファイルにまとめる

2. **インポートパスの更新**:
   - `from ..eavesdrop.llm_judge import LLMJudge` → `from ..services.eavesdrop import LLMJudge`
   - `from ..eavesdrop.conversation_buffer import ConversationBuffer` → `from ..services.eavesdrop import ConversationBuffer`

3. **テストの移行・実行**:

   ```bash
   # テストファイルを移動・統合
   mv tests/unit/test_llm_judge.py tests/unit/services/test_eavesdrop.py
   mv tests/unit/test_conversation_buffer.py tests/unit/services/test_eavesdrop.py  # 統合
   
   # テストを実行して通過を確認
   uv run pytest tests/unit/services/test_eavesdrop.py -v
   ```

4. **空ディレクトリ削除**:

   ```bash
   rmdir session/ ai/ eavesdrop/
   ```

**完了基準**:

- [ ] `services/ai.py` の統合が完了している
- [ ] **リトライ処理が tenacity デコレータで実装されている（手書きコードを削除）**
- [ ] `errors/ai.py` が作成されている
- [ ] `AnthropicProvider` で例外がラッピングされている
- [ ] API キーの取得方法が統一されている（Config インスタンスから取得）
- [ ] 戻り値が `tuple[str, TokenInfo]` に変更されている
- [ ] **`TokenInfo` dataclass が `frozen=True, kw_only=True` で定義されている（services/ai.py 内に定義、将来の分離は Phase 13/14 で検討）**
- [ ] **`services/eavesdrop.py` の統合が完了している（Step 3 で実施）**
- [ ] インポートパスが更新されている
- [ ] 対応するテストが移行されている
- [ ] **テストが通過している（Green）**
- [ ] **AI周りのモック戦略が確定している**
- [ ] `ruff check` と `ty check` が通過している

**注**: tenacity は既に dependencies に含まれています（dev 依存関係ではありません）。

**注**: `services/eavesdrop.py` の統合は **Step 3 で必須** とします。Step 4 はハンドラー分割という最大の山場のため、ロジック層の変更は混ぜないようにします。

### 6.6 Step 4: プレゼンテーション層（最大の山場） - bot/handlers/ の物理分割と setup_handlers (DI) の実装（Day 6-7、2日）

**基本方針**: ここで初めて handlers.py を解体する。bot/handlers/ の物理分割と setup_handlers (DI) の実装を実施し、対応するテストも同時に移行・実行する。下位レイヤー（utils, errors, db, services）はテスト済みなので、モックを使ったハンドラーのテストに集中できる。常に「型チェックが通り、テストも通る」状態を維持する。

**リファクタリング・ワークフロー**:

各ファイル分割後に、以下のコマンドで即座にチェックする:

```bash
# ワンライナーで全チェック（Ruff + ty）
uv run ruff check src/kotonoha_bot/bot/ && uv run ty check src/kotonoha_bot/bot/

# 対応するテストを実行
uv run pytest tests/unit/bot/ -v
```

- 分割後のインポートエラーを即座に検出
- 型の不整合を即座に検出
- テストが通過することを確認
- エラーメッセージに従って修正

**方針**: **物理ファイルに分割**。内部クラス分割ではなく、ファイル単位で責務を分離する。

**理由**:

- 認知負荷の低減: 1ファイル800行の中に3つの異なるクラスが混在すると、スクロールの移動が増え、認知負荷が下がりにくい
- Git管理: ファイル単位で責務が分かれている方が、将来的に変更履歴を追う際にノイズが減る
- 移行コスト: 内部クラスに分割する手間と、物理ファイルに分ける手間に大差はない（import文の調整のみ）

**重要**: 依存性注入パターンに従い、すべての依存を引数として受け取る

**テスト汚染コードの解消**（新規追加）:

DIパターンを適用する際、以下のテスト汚染コードを解消する:

1. **フラグ分岐の削除**:
   - `if is_testing:` や `if not self.is_test_mode:` などのフラグ分岐を削除
   - 代わりに、依存をDIで差し替える（本番はRealClient、テストはMockClient）
   - 例: `if not self.is_testing: self.api.send(data)` → `self.api_client.send(data)` に変更

2. **privateメソッドの公開を避ける**:
   - テストで `_private_method()` を呼んでいる箇所があれば、そのロジックを別クラス（utils）に移動
   - 例: `Handler._parse_date()` → `utils/datetime.py` に移動

3. **テスト用パラメータの削除**:
   - `__init__` に `force_admin_for_test=False` などのパラメータがあれば削除
   - テストデータは Factory パターンで作成（Step 6 で実装）

**推奨構成**:

```txt
bot/
├── handlers/              # パッケージ化
│   ├── __init__.py        # MessageHandlerクラス（Facade）を定義して外部には1つの顔を見せる
│   ├── base.py            # 共通の基底クラス（もしあれば）
│   ├── mention.py         # MentionHandler
│   ├── thread.py          # ThreadHandler
│   └── eavesdrop.py       # EavesdropHandler
```

**実装例**:

```python
# bot/handlers/__init__.py
"""Discord イベントハンドラー（Facade）"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..services.session import SessionManager
    from ..services.ai import AnthropicProvider
    from ..services.eavesdrop import LLMJudge, ConversationBuffer
    from ..bot.router import MessageRouter

from .mention import MentionHandler
from .thread import ThreadHandler
from .eavesdrop import EavesdropHandler

import discord
from discord.ext import tasks

class MessageHandler:
    """メッセージハンドラー（統合Facade）"""

    def __init__(
        self,
        bot: discord.Client,
        session_manager: "SessionManager",
        ai_provider: "AnthropicProvider",
        router: "MessageRouter | None" = None,
        llm_judge: "LLMJudge | None" = None,
        buffer: "ConversationBuffer | None" = None,
    ):
        self.bot = bot
        self.session_manager = session_manager
        self.ai_provider = ai_provider
        self.router = router or MessageRouter()

        # 各ハンドラーのインスタンス化（依存を渡す）
        self.mention = MentionHandler(bot, session_manager, ai_provider)
        self.thread = ThreadHandler(bot, session_manager, ai_provider, self.router)
        self.eavesdrop = EavesdropHandler(
            bot, session_manager, ai_provider, llm_judge, buffer)

    # タスクとイベントハンドラー
    @tasks.loop(hours=1)
    async def cleanup_task(self):
        ...


def setup_handlers(
    bot: discord.Client,
    session_manager: "SessionManager",
    ai_provider: "AnthropicProvider",
    router: "MessageRouter | None" = None,
    llm_judge: "LLMJudge | None" = None,
    buffer: "ConversationBuffer | None" = None,
) -> MessageHandler:
    """イベントハンドラーをセットアップ（依存関係を注入）
    
    Args:
        bot: Discord クライアント
        session_manager: セッションマネージャー
        ai_provider: AIプロバイダー
        router: メッセージルーター（オプション）
        llm_judge: LLM判定（オプション）
        buffer: 会話バッファ（オプション）
    
    Returns:
        MessageHandler インスタンス（Facade）
    
    Note:
        MessageHandler はあくまで Facade（窓口）であり、実体は MentionHandler 等です。
        循環参照を避けるため、TYPE_CHECKING ガードを使用しています。
    """
    handler = MessageHandler(
        bot, session_manager, ai_provider, router, llm_judge, buffer
    )
    # ... イベント登録
    return handler

__all__ = ["MessageHandler", "setup_handlers"]
```

**重要**: `setup_handlers` の戻り値は `MessageHandler` ですが、Python の循環参照を避けるために `bot/handlers/__init__.py` で `TYPE_CHECKING` ガードが必要になります。設計として、`MessageHandler` はあくまで Facade（窓口）であり、実体は `MentionHandler` 等なので、`setup_handlers` は `MessageHandler` インスタンスを返す、で正解です。

```python
# bot/handlers/mention.py
"""メンション応答ハンドラー"""

import logging
import discord
from ..services.session import SessionManager
from ..services.ai import AnthropicProvider

logger = logging.getLogger(__name__)


class MentionHandler:
    """メンション応答ハンドラー（~150行）"""

    def __init__(
        self,
        bot: discord.Client,
        session_manager: SessionManager,
        ai_provider: AnthropicProvider,
    ):
        self.bot = bot
        self.session_manager = session_manager
        self.ai_provider = ai_provider

    async def handle(self, message: discord.Message) -> None:
        """メンション時の処理"""
        ...

    async def _process(self, message: discord.Message) -> None:
        """メンション処理の実装"""
        ...
```

**外部からの使用**:

```python
# main.py など
from kotonoha_bot.bot.handlers import MessageHandler, setup_handlers
# インポートパスは変更なし（__init__.py で再エクスポート）
```

#### 6.4.1 初期化順序の明確化

**重要**: DIパターンを適用する際、各サービスの初期化順序を明確にする必要があります。

**初期化順序のルール**:

1. **データベースの初期化**（最優先）
   - `PostgreSQLDatabase` は他のサービスが依存するため、最初に初期化
   - `await db.initialize()` でテーブル作成と接続確立

2. **サービスの初期化**（依存関係順）
   - `SessionManager` は `DatabaseProtocol`（実装は `PostgreSQLDatabase`）に依存 →
     `await session_manager.initialize()` でDB接続とセッション読み込み
   - `AnthropicProvider` は独立（初期化不要、または同期的な初期化のみ）
   - `LLMJudge` は `AnthropicProvider` に依存（初期化不要、コンストラクタで依存注入）

3. **ハンドラーのセットアップ**（初期化済みサービスを使用）
   - `setup_handlers` は初期化済みのサービスインスタンスを受け取る
   - ハンドラー内で `session_manager.initialize()` を呼ぶ必要はない

**実装例**:

```python
# main.py
from kotonoha_bot.db.postgres import PostgreSQLDatabase

async def main():
    # 1. データベースの初期化（最優先）
    db = PostgreSQLDatabase(connection_string=config.database_url)
    await db.initialize()  # テーブル作成と接続確立
    
    # 2. サービスの初期化（依存関係順）
    session_manager = SessionManager(db)  # DIパターン
    await session_manager.initialize()  # DB接続とセッション読み込み
    # 注: この時点で session_manager は使用可能な状態
    
    ai_provider = AnthropicProvider()  # 初期化不要（必要に応じて同期的な初期化）
    router = MessageRouter()
    llm_judge = LLMJudge(ai_provider)  # コンストラクタで依存注入
    buffer = ConversationBuffer()
    
    # 3. Bot の初期化
    bot = KotonohaBot()
    
    # 4. ハンドラーのセットアップ（初期化済みサービスを使用）
    handler = setup_handlers(
        bot=bot,
        session_manager=session_manager,  # 既に初期化済み
        ai_provider=ai_provider,
        router=router,
        llm_judge=llm_judge,
        buffer=buffer,
    )
    
    # 5. Bot の起動
    await bot.start(Config.DISCORD_TOKEN)
```

**setup_handlers 内での保証**:

```python
# bot/handlers/__init__.py
def setup_handlers(
    bot: discord.Client,
    session_manager: SessionManager,  # 初期化済みであることを前提
    ai_provider: AnthropicProvider,
    router: MessageRouter | None = None,
    llm_judge: LLMJudge | None = None,
    buffer: ConversationBuffer | None = None,
) -> MessageHandler:
    """イベントハンドラーをセットアップ（依存関係を注入）
    
    Args:
        session_manager: 初期化済みの SessionManager インスタンス
        ai_provider: AIプロバイダー
        router: メッセージルーター
        llm_judge: LLM判定（オプション）
        buffer: 会話バッファ（オプション）
    
    Note:
        session_manager は main.py で既に initialize() が呼ばれていることを前提とする。
        ハンドラー内で再度初期化する必要はない。
    """
    # 初期化済みチェック（オプション、デバッグ用）
    # 公開プロパティを使用（プライベート属性を直接チェックしない）
    if not session_manager.is_initialized:
        logger.warning(
            "SessionManager may not be initialized. "
            "Ensure initialize() is called in main().")
    
    handler = MessageHandler(
        bot, session_manager, ai_provider, router, llm_judge, buffer
    )
    # ... イベント登録
    return handler
```

**on_ready イベントでの初期化は不要**:

```python
# ❌ 非推奨: on_ready イベント内で初期化
@bot.event
async def on_ready():
    await handler.session_manager.initialize()  # 不要（既に初期化済み）

# ✅ 推奨: main.py で初期化済み
# on_ready イベントでは初期化処理を行わない
@bot.event
async def on_ready():
    logger.info(f"Bot is ready! Logged in as {bot.user}")
    # タスクの開始のみ
    if not handler.cleanup_task.is_running():
        handler.cleanup_task.start()
```

#### 6.6.1 bot/handlers の物理分割

**実施内容**:

1. **handlers/ ディレクトリの作成**:

   ```bash
   mkdir -p src/kotonoha_bot/bot/handlers
   ```

2. **ファイル分割**:
   - `bot/handlers.py` を以下のファイルに分割:
     - `bot/handlers/__init__.py`: `MessageHandler` クラス（Facade）
     - `bot/handlers/mention.py`: `MentionHandler`
     - `bot/handlers/thread.py`: `ThreadHandler`
     - `bot/handlers/eavesdrop.py`: `EavesdropHandler`

3. **DIパターンの適用**:
   - 各ハンドラーは依存を引数として受け取る
   - `setup_handlers` 関数で依存関係を注入

4. **テスト汚染コードの解消**:
   - `if is_testing:` などのフラグ分岐を削除
   - privateメソッドをテストで直接呼んでいる箇所を解消
   - テスト用パラメータを削除

5. **テストの移行・実行**:

   ```bash
   # テストファイルを移動・統合
   mv tests/unit/test_handlers_*.py tests/unit/bot/test_handlers.py  # 統合
   mv tests/unit/test_thread_handler.py tests/unit/bot/test_handlers.py  # 統合
   
   # テストを実行して通過を確認
   uv run pytest tests/unit/bot/test_handlers.py -v
   ```

6. **チェック**:

   ```bash
   uv run ruff check src/kotonoha_bot/bot/ && uv run ty check src/kotonoha_bot/bot/
   uv run pytest tests/unit/bot/ -v
   ```

#### 6.6.2 bot/router.py と bot/commands.py の移動

**実施内容**:

1. **ファイル移動**:

   ```bash
   mv router/message_router.py bot/router.py
   mv commands/chat.py bot/commands.py
   ```

2. **インポートパスの更新**:
   - `from ..router.message_router import MessageRouter` → `from ..bot.router import MessageRouter`
   - `from ..commands.chat import setup as setup_chat_commands` → `from ..bot.commands import setup as setup_chat_commands`

3. **テストの移行・実行**:

   ```bash
   # テストファイルを移動
   mv tests/unit/test_message_router.py tests/unit/bot/test_router.py
   mv tests/unit/test_commands.py tests/unit/bot/test_commands.py
   
   # テストを実行して通過を確認
   uv run pytest tests/unit/bot/ -v
   ```

4. **空ディレクトリ削除**:

   ```bash
   rmdir router/ commands/
   ```

**完了基準**:

- [ ] `bot/handlers/` ディレクトリが作成されている
- [ ] `bot/handlers.py` が物理分割されている（`__init__.py`, `mention.py`, `thread.py`, `eavesdrop.py`）
- [ ] DIパターンが適用されている
- [ ] **`setup_handlers` の型ヒントで `TYPE_CHECKING` ガードが使用されている**
- [ ] **`bot/handlers/__init__.py` で循環参照が回避されている**
- [ ] **`setup_handlers` 内で `session_manager.is_initialized` プロパティを使用して初期化チェックを行っている（プライベート属性を直接チェックしていない）**
- [ ] テスト汚染コード（`if is_testing:` などのフラグ分岐）が削除されている
- [ ] privateメソッドをテストで直接呼んでいる箇所がなく、適切にロジックが移動されている
- [ ] テスト用パラメータ（`force_admin_for_test` など）が `__init__` から削除されている
- [ ] `bot/router.py` と `bot/commands.py` の移動が完了している
- [ ] インポートパスが更新されている
- [ ] 対応するテストが移行されている
- [ ] `ruff check` と `ty check` が通過している
- [ ] 対応するテストが通過している

### 6.7 Step 5: 結合と仕上げ - main.py の実装、Graceful Shutdown、インポートパスの最終確認（Day 8、0.5日）

**基本方針**: すべてのコンポーネントが完成しているため、main.py の実装、Graceful Shutdown、インポートパスの最終確認を実施する。

**リファクタリング・ワークフロー**:

整備後に、以下のコマンドで即座にチェックする:

```bash
# ワンライナーで全チェック（Ruff + ty）
uv run ruff check src/ && uv run ty check src/

# 全テストを実行
uv run pytest tests/ -v
```

- すべてのインポートパスが正しいことを確認
- 型チェックが通過することを確認
- 全テストが通過することを確認

#### 6.7.1 main.py の実装（依存関係の組み立て）

**実施内容**:

1. **依存関係の組み立て**:
   - Config の読み込み（`get_config()` を使用、main.py でのみ）
   - データベースの初期化
   - サービスの初期化（依存関係順、config を注入）
   - Bot の初期化（config を注入）
   - ハンドラーのセットアップ（依存関係を注入）

2. **初期化順序の明確化**:
   - main.py で `await session_manager.initialize()` を明示的に呼ぶ
   - 初期化順序を文書化

3. **終了処理（Graceful Shutdown）**:
   - DB接続のクローズ処理を追加
   - リソースリークを防止

**実装例**:

```python
# main.py
from kotonoha_bot.config import get_config, Config
from kotonoha_bot.db.postgres import PostgreSQLDatabase
from kotonoha_bot.services.session import SessionManager
from kotonoha_bot.services.ai import AnthropicProvider
from kotonoha_bot.services.eavesdrop import LLMJudge, ConversationBuffer
from kotonoha_bot.bot.router import MessageRouter
from kotonoha_bot.bot.handlers import setup_handlers

async def main():
    # 1. Config の読み込み（main.py でのみ get_config() を使用）
    config = get_config()
    
    # 2. データベースの初期化（PostgreSQL、config を注入）
    db = PostgreSQLDatabase(connection_string=config.database_url)
    # または個別パラメータ: db = PostgreSQLDatabase(host=..., port=..., database=..., user=..., password=...)
    await db.initialize()
    
    # 3. サービスの初期化（依存関係を組み立て、config を注入）
    session_manager = SessionManager(db=db, config=config)
    await session_manager.initialize()  # ← 明示的に初期化（重要）
    
    ai_provider = AnthropicProvider(api_key=config.anthropic_api_key)
    # または: ai_provider = AnthropicProvider(config=config)
    
    router = MessageRouter()
    llm_judge = LLMJudge(ai_provider=ai_provider)
    buffer = ConversationBuffer()
    
    # 4. Bot の初期化（config を注入）
    bot = KotonohaBot(config=config)  # または discord_token=config.discord_token
    
    # 5. ハンドラーのセットアップ（依存関係を注入）
    handler = setup_handlers(
        bot=bot,
        session_manager=session_manager,
        ai_provider=ai_provider,
        router=router,
        llm_judge=llm_judge,
        buffer=buffer,
    )
    
    try:
        # 6. Bot の起動
        await bot.start(config.discord_token)
    finally:
        # 7. Graceful Shutdown
        await db.close()
        # その他のリソースのクローズ処理
```

#### 6.7.2 インポートパスの最終確認

#### 6.7.3 `__init__.py` の整備

**実施内容**:

1. **各ディレクトリの `__init__.py` の作成**:
   - `bot/__init__.py`
   - `services/__init__.py`
   - `errors/__init__.py`
   - `utils/__init__.py`
   - `db/__init__.py`

2. **再エクスポート**:
   - 各 `__init__.py` で主要なクラス・関数を再エクスポート
   - `__all__` を適切に定義

3. **インポートパスの最終確認**:
   - すべてのインポートパスが更新されていることを確認
   - 循環依存がないことを確認

**完了基準**:

- [ ] main.py で依存関係が正しく組み立てられている（config を注入）
- [ ] **main.py 以外では `get_config()` を呼んでいない**
- [ ] **全てのクラス（Service, Handler, DB）がコンストラクタで config を受け取っている**
- [ ] 初期化順序が明確に文書化されている
- [ ] Graceful Shutdown が実装されている（DB接続のクローズ処理、main.py の try-finally で実装）
- [ ] すべての `__init__.py` が作成されている
- [ ] `__all__` が適切に定義されている
- [ ] すべてのインポートパスが更新されている
- [ ] Bot が正常に起動する
- [ ] 循環依存が検出されていない
- [ ] `ruff check` と `ty check` が通過している

### 6.8 Step 6: 結合テスト - E2E的な動作確認（Day 8、0.5日）

**基本方針**: すべてのコンポーネントが統合された状態で、E2E的な動作確認を実施する。

**実施内容**:

1. **結合テストの実行**:

   ```bash
   # 全テストを実行
   uv run pytest tests/ -v
   
   # 統合テストを実行
   uv run pytest tests/integration/ -v
   ```

2. **E2E的な動作確認**:
   - Bot の起動確認
   - メンション応答の確認
   - スレッド応答の確認
   - イavesdrop機能の確認
   - エラーハンドリングの確認

3. **パフォーマンステスト**（オプション）:

   ```bash
   uv run pytest tests/performance/ -v
   ```

**完了基準**:

- [ ] **dirty-equals が追加され、テストのアサーションで使用されている**
- [ ] 全テストが通過している
- [ ] 統合テストが通過している
- [ ] Bot が正常に起動する
- [ ] 各機能が正常に動作する
- [ ] エラーハンドリングが正常に動作する
- [ ] **不要な依存関係の最終確認が完了している（deptry を使用）**
- [ ] `ruff check` と `ty check` が通過している

**注**: dirty-equals、pytest-watcher、deptry は既に dev 依存関係に含まれています。

### 6.9 Step 7: 品質向上 - 型ヒント・docstring の完全化（Day 9、1日）

**目的**: コードレビューで指摘された「型ヒントの完全化」と「docstring の完全化」を実施する。`ty check --strict` を使用して厳格にチェックする。

---
