# 監査ログ機能の実装計画

**作成日**: 2026 年 1 月 15 日  
**ステータス**: 計画中  
**優先度**: 高（コスト管理の観点から重要）

## 概要

KOTONOHA Bot の監査ログ機能とトークン使用量追跡機能の実装計画。この機能により、以下の目的を達成します:

1. **コスト管理**: 月ごと、ユーザーごとのトークン使用量とコストを追跡
2. **文脈の永続化**: Bot を再起動しても過去の会話内容を参照可能
3. **ユーザー分析**: ヘビーユーザーの特定、利用状況の把握
4. **問題追跡**: エラー発生時の原因追跡、デバッグ支援

## 前提条件

- **aiosqlite への移行完了**: ADR-0006 の実装が完了していること
- **既存の SQLite インフラ**: `SQLiteDatabase` クラスが非同期対応済みであること

## 設計方針

### 1. ログの使い分け

**システムログ（ファイル）**:

- 開発者がデバッグするための情報
- DB 接続自体が死んだ時にも残る必要があるため、ファイルが最強
- 例: `Login successful`, `Connection lost`, `Error: ZeroDivision...`

**監査・統計データ（データベース）**:

- 「今月のトークン総量は？」「このユーザーの過去の会話は？」といった「集計・検索」が必要になるデータ
- 例: 「誰が」「いつ」「どのモデルで」「何トークン使ったか」

### 2. データベースに保存するメリット

1. **コスト管理ができる（重要）**

   - ログファイルだと「今月いくら掛かった？」を計算するには、テキストを全行読み込んで正規表現で解析...という地獄の作業が必要
   - DB なら `SELECT SUM(cost) FROM audit_logs WHERE date >= '2026-01-01'` 一発

2. **文脈（Context）の永続化**

   - Bot を再起動しても、「過去の会話内容」を DB から読み出して、会話を継続できるようになる
   - （現在はメモリ上にあるだけなので、再起動すると文脈を忘れる）

3. **ユーザー分析**
   - 「誰が一番 Bot を使っているか（ヘビーユーザー）」のランキングなどが即座に出せる

## 実装計画

### Phase 1: データベーススキーマの設計と実装

#### 1.1 テーブル設計

**`audit_logs` テーブル**:

```sql
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    event_type TEXT NOT NULL,  -- 'mention', 'thread', 'eavesdrop'
    session_key TEXT NOT NULL,
    user_id INTEGER,
    channel_id INTEGER,
    thread_id INTEGER,
    user_message_id INTEGER,  -- Discord メッセージID
    bot_message_id INTEGER,   -- Discord メッセージID
    user_message_content TEXT,
    bot_response_content TEXT,
    model_used TEXT NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    total_tokens INTEGER,
    estimated_cost REAL,  -- USD
    latency_ms INTEGER,   -- ミリ秒
    error_message TEXT,
    conversation_history_length INTEGER,
    system_prompt_used BOOLEAN DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_logs_session_key ON audit_logs(session_key);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_event_type ON audit_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_logs_model_used ON audit_logs(model_used);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);
```

**`monthly_usage` テーブル**（オプション、Phase 2 で実装）:

```sql
CREATE TABLE IF NOT EXISTS monthly_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,  -- 1-12
    total_input_tokens INTEGER DEFAULT 0,
    total_output_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    total_cost REAL DEFAULT 0.0,  -- USD
    request_count INTEGER DEFAULT 0,
    unique_users INTEGER DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(year, month)
);

CREATE INDEX IF NOT EXISTS idx_monthly_usage_year_month ON monthly_usage(year, month);
```

#### 1.2 スキーマ実装

- `SQLiteDatabase` クラスに `_init_audit_tables()` メソッドを追加
- `_init_database()` メソッドから呼び出す

### Phase 2: AuditLogger クラスの実装

#### 2.1 クラス設計

```python
# src/kotonoha_bot/audit/logger.py
class AuditLogger:
    """監査ログを記録するクラス"""

    def __init__(self, db: SQLiteDatabase):
        self.db = db

    async def log_interaction(
        self,
        session_key: str,
        event_type: str,
        user_id: int | None,
        channel_id: int | None,
        thread_id: int | None,
        user_message_id: int | None,
        bot_message_id: int | None,
        user_message: str,
        bot_response: str,
        token_info: dict,
        model_used: str,
        latency_ms: int,
        error: Exception | None = None,
        conversation_history_length: int = 0,
        system_prompt_used: bool = False,
    ) -> None:
        """やり取りをログに記録（非同期）"""
        pass

    async def get_monthly_usage(
        self, year: int, month: int
    ) -> dict | None:
        """月ごとの使用量を取得"""
        pass

    async def get_user_usage(
        self, user_id: int, start_date: datetime, end_date: datetime
    ) -> dict:
        """ユーザーごとの使用量を取得"""
        pass
```

#### 2.2 コスト計算機能

```python
# src/kotonoha_bot/audit/cost_calculator.py
class CostCalculator:
    """トークン数からコストを計算するクラス"""

    # モデルごとの価格（2026年1月現在）
    PRICING = {
        "anthropic/claude-3-haiku-20240307": (0.25 / 1_000_000, 1.25 / 1_000_000),
        "anthropic/claude-haiku-4-5": (1.00 / 1_000_000, 5.00 / 1_000_000),
        "anthropic/claude-sonnet-4-5": (3.00 / 1_000_000, 15.00 / 1_000_000),
        "anthropic/claude-opus-4-5": (5.00 / 1_000_000, 25.00 / 1_000_000),
    }

    @classmethod
    def calculate_cost(
        cls, model: str, input_tokens: int, output_tokens: int
    ) -> float:
        """トークン数からコストを計算（USD）"""
        input_price, output_price = cls.PRICING.get(model, (0, 0))
        cost = (input_tokens * input_price) + (output_tokens * output_price)
        return round(cost, 6)
```

### Phase 3: LiteLLMProvider の拡張

#### 3.1 戻り値の変更

**変更前**:

```python
async def generate_response(...) -> str:
    # ...
    return result  # strのみ返す
```

**変更後**:

```python
async def generate_response(...) -> tuple[str, dict]:
    """応答とトークン情報を返す

    Returns:
        tuple[str, dict]: (応答テキスト, トークン情報)
        トークン情報の形式:
        {
            "input_tokens": int,
            "output_tokens": int,
            "total_tokens": int,
            "model_used": str,
            "latency_ms": int,
        }
    """
    import time
    start_time = time.time()

    response = litellm.completion(...)

    latency_ms = int((time.time() - start_time) * 1000)

    # トークン使用量を取得
    usage = response.usage
    token_info = {
        "input_tokens": usage.prompt_tokens,
        "output_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
        "model_used": response.model,
        "latency_ms": latency_ms,
    }

    result = response.choices[0].message.content
    return result, token_info
```

#### 3.2 既存のログ出力の維持

- 既存のログ出力（`logger.info()`）は維持する（デバッグ用）
- 新しい戻り値と併用

### Phase 4: MessageHandler での統合

#### 4.1 呼び出し箇所の修正

以下のメソッドを修正:

1. `handle_mention()`: メンション応答型
2. `_create_thread_and_respond()`: スレッド作成時
3. `_process_thread_message()`: スレッド内メッセージ
4. `LLMJudge.generate_response()`: 聞き耳型判定・応答生成

**変更例**:

```python
# 現在（194行目付近）:
response_text = await self.ai_provider.generate_response(
    messages=session.get_conversation_history(),
    system_prompt=system_prompt,
)

# 将来の実装:
response_text, token_info = await self.ai_provider.generate_response(
    messages=session.get_conversation_history(),
    system_prompt=system_prompt,
)

# 監査ログに記録（非同期、ブロッキングしない）
asyncio.create_task(
    self.audit_logger.log_interaction(
        session_key=session_key,
        event_type="mention",
        user_id=message.author.id,
        channel_id=message.channel.id,
        thread_id=None,
        user_message_id=message.id,
        bot_message_id=None,  # 後で更新
        user_message=user_message,
        bot_response=response_text,
        token_info=token_info,
        model_used=token_info["model_used"],
        latency_ms=token_info["latency_ms"],
        conversation_history_length=len(session.messages),
        system_prompt_used=system_prompt is not None,
    )
)
```

#### 4.2 非同期ログ記録の実装

- ログ記録は `asyncio.create_task()` で非同期実行
- 応答速度への影響を最小化
- エラーが発生しても Bot の動作に影響しない（ログに記録のみ）

### Phase 5: 月次集計機能（オプション）

#### 5.1 バッチ集計タスク

```python
@tasks.loop(hours=1)  # 1時間ごとに実行
async def monthly_aggregation_task(self):
    """月ごとの使用量を集計"""
    # 前時間のログを集計して monthly_usage テーブルを更新
    pass
```

#### 5.2 リアルタイム集計

- 各 API 呼び出し後に `monthly_usage` テーブルを更新
- または、バッチ集計で定期的に更新

## 実装ステップ

### Step 1: データベーススキーマの実装

- [ ] `SQLiteDatabase` クラスに `_init_audit_tables()` メソッドを追加
- [ ] `audit_logs` テーブルを作成
- [ ] インデックスを作成
- [ ] マイグレーションスクリプトを作成（既存データベースへの適用）

### Step 2: AuditLogger クラスの実装

- [ ] `src/kotonoha_bot/audit/logger.py` を作成
- [ ] `log_interaction()` メソッドを実装
- [ ] `get_monthly_usage()` メソッドを実装
- [ ] `get_user_usage()` メソッドを実装
- [ ] エラーハンドリングを実装

### Step 3: CostCalculator クラスの実装

- [ ] `src/kotonoha_bot/audit/cost_calculator.py` を作成
- [ ] `calculate_cost()` メソッドを実装
- [ ] 価格表を更新可能にする（設定ファイルから読み込み）

### Step 4: LiteLLMProvider の拡張

- [ ] `generate_response()` の戻り値を `tuple[str, dict]` に変更
- [ ] トークン情報を取得して返す
- [ ] レイテンシを計測
- [ ] 既存のログ出力を維持
- [ ] 既存の呼び出し箇所をすべて修正

### Step 5: MessageHandler での統合

- [ ] `MessageHandler` に `AuditLogger` インスタンスを追加
- [ ] `handle_mention()` を修正
- [ ] `_create_thread_and_respond()` を修正
- [ ] `_process_thread_message()` を修正
- [ ] `LLMJudge.generate_response()` を修正
- [ ] 非同期ログ記録を実装

### Step 6: テストの実装

- [ ] `AuditLogger` のユニットテスト
- [ ] `CostCalculator` のユニットテスト
- [ ] 統合テスト（実際の DB 操作）
- [ ] パフォーマンステスト（大量のログ記録）

### Step 7: 月次集計機能（オプション）

- [ ] `monthly_usage` テーブルを作成
- [ ] バッチ集計タスクを実装
- [ ] 集計結果を取得するメソッドを実装

## 注意事項

### 1. 非同期処理の実装

- **絶対に守らなければならないルール**: 標準の `sqlite3` ライブラリをそのまま使ってはいけない
- **対策**: `aiosqlite` を使用（ADR-0006 参照）
- すべての DB 操作を非同期で実行

### 2. パフォーマンスへの配慮

- **非同期ログ記録**: ログ記録は `asyncio.create_task()` で非同期実行
- **バッチ処理**: 複数のログをまとめて書き込む（将来の最適化）
- **インデックス**: 検索頻度の高いカラムにインデックスを設定

### 3. エラーハンドリング

- ログ記録のエラーが Bot の動作に影響しないようにする
- エラーはログに記録するが、ユーザーには通知しない

### 4. プライバシーとセキュリティ

- **メッセージ内容の記録**: 設定で有効/無効を切り替え可能にする
- **データ保持期間**: 設定可能な保持期間（例: 90 日、1 年）
- **アクセス制御**: 管理者のみアクセス可能

### 5. 既存実装への影響

- `LiteLLMProvider.generate_response()` の戻り値変更は、すべての呼び出し箇所に影響
- テストコードも更新が必要

## 設定オプション

### 環境変数

```bash
# 監査ログの有効化
AUDIT_LOG_ENABLED=true

# ログの保存先（既存のデータベースを使用）
AUDIT_LOG_DATABASE_PATH=./data/sessions.db

# データ保持期間（日数）
AUDIT_LOG_RETENTION_DAYS=90

# メッセージ内容の記録（true: 完全記録、false: 要約のみ）
AUDIT_LOG_FULL_MESSAGE=true

# 月次集計の有効化
MONTHLY_USAGE_TRACKING_ENABLED=true
```

## パフォーマンス目標

- **ログ記録のレイテンシ**: 10ms 以内（非同期処理によりブロッキングなし）
- **月次集計の実行時間**: 1 秒以内（1000 件のログを集計）
- **クエリの実行時間**: 100ms 以内（インデックスを活用）

## 将来の拡張

### Phase 6: 高度な機能（オプション）

- [ ] ログの検索・フィルタリング機能
- [ ] ログのエクスポート機能（CSV、JSON）
- [ ] データ保持期間の自動管理（古いログの自動削除）
- [ ] アラート機能（使用量が閾値を超えた場合）
- [ ] ダッシュボード（使用量の可視化）

## 参考資料

- [audit-logging-considerations.md](./audit-logging-considerations.md): 詳細な検討内容
- [ADR-0006: aiosqlite への移行](../architecture/adr/0006-migrate-to-aiosqlite.md)
- [ADR-0003: SQLite の採用](../architecture/adr/0003-use-sqlite.md)
- [database-design.md](../architecture/database-design.md)

---

**作成日**: 2026 年 1 月 15 日  
**最終更新日**: 2026 年 1 月 15 日
