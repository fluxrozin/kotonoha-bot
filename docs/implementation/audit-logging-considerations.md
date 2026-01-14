# 監査ログとトークン使用量追跡の検討

## 概要

Kotonoha Bot の監査ログ機能とトークン使用量の追跡機能についての検討ドキュメント。

## 目的

1. **監査ログ**: すべてのやり取りを記録し、問題発生時の原因追跡や利用状況の把握を可能にする
2. **トークン使用量追跡**: やり取りごと、月ごとのトークン使用量を記録し、コスト管理と利用状況の分析を可能にする

---

## 1. 監査ログの要件

### 1.1 記録すべき情報

#### 基本情報

- **タイムスタンプ**: イベント発生時刻（UTC 推奨）
- **イベントタイプ**: やり取りの種類（mention, thread, eavesdrop）
- **セッション ID**: セッションキー
- **ユーザー ID**: Discord ユーザー ID
- **チャンネル ID**: Discord チャンネル ID
- **スレッド ID**: スレッド型の場合のスレッド ID

#### メッセージ情報

- **ユーザーメッセージ**: ユーザーが送信したメッセージ内容
- **Bot 応答**: Bot が生成した応答内容
- **メッセージ ID**: Discord メッセージ ID（ユーザー、Bot 両方）

#### API 呼び出し情報

- **使用モデル**: 実際に使用された LLM モデル（フォールバック時も記録）
- **リクエスト時間**: API 呼び出し開始時刻
- **レスポンス時間**: API 呼び出し完了時刻
- **レイテンシ**: レスポンス時間 - リクエスト時間
- **エラー情報**: エラーが発生した場合の詳細

#### トークン使用量（詳細は後述）

- **入力トークン数**: リクエストに使用されたトークン数
- **出力トークン数**: レスポンスで生成されたトークン数
- **合計トークン数**: 入力 + 出力

#### メタデータ

- **コスト**: 推定コスト（USD）
- **会話履歴の長さ**: 会話履歴に含まれるメッセージ数
- **システムプロンプトの使用**: システムプロンプトが使用されたかどうか

### 1.2 ログの保存形式

#### オプション 1: SQLite データベース（推奨）

**メリット**:

- 既存の SQLite インフラを活用できる
- クエリによる検索・集計が容易
- トランザクション管理が可能
- データの整合性が保証される

**デメリット**:

- 大量のログでパフォーマンスが低下する可能性
- 定期的なアーカイブが必要

**スキーマ例**:

```sql
CREATE TABLE audit_logs (
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

CREATE INDEX idx_audit_logs_timestamp ON audit_logs(timestamp);
CREATE INDEX idx_audit_logs_session_key ON audit_logs(session_key);
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_event_type ON audit_logs(event_type);
CREATE INDEX idx_audit_logs_model_used ON audit_logs(model_used);
```

#### オプション 2: JSON Lines ファイル

**メリット**:

- シンプルな実装
- ストリーミング処理が容易
- 外部ツールでの解析が容易

**デメリット**:

- 検索・集計が困難
- ファイルサイズが大きくなる
- 並行書き込みの管理が必要

**形式例**:

```json
{
  "timestamp": "2026-01-15T10:30:00Z",
  "event_type": "mention",
  "session_key": "mention:123456",
  "user_id": 123456,
  "model_used": "anthropic/claude-3-haiku-20240307",
  "input_tokens": 150,
  "output_tokens": 200,
  "total_tokens": 350,
  "estimated_cost": 0.00025,
  "latency_ms": 1200
}
```

#### オプション 3: 構造化ログ（JSON 形式）

**メリット**:

- 既存のログシステムと統合可能
- ログ管理ツール（ELK、Loki 等）と連携可能

**デメリット**:

- 外部ツールの導入が必要
- セットアップが複雑

### 1.3 プライバシーとセキュリティ

#### 機密情報の取り扱い

- **メッセージ内容**: 完全に記録するか、要約のみ記録するか検討
- **ユーザー ID**: 記録は必要だが、匿名化オプションを提供
- **データ保持期間**: 設定可能な保持期間（例: 90 日、1 年）

#### アクセス制御

- **ログの閲覧**: 管理者のみアクセス可能
- **ログの削除**: 管理者のみ削除可能
- **ログのエクスポート**: 管理者のみエクスポート可能

#### データ保護

- **暗号化**: 機密情報を含むログは暗号化して保存
- **バックアップ**: 定期的なバックアップ
- **削除**: 保持期間を過ぎたログの自動削除

---

## 2. トークン使用量の追跡

### 2.1 LiteLLM からのトークン情報取得

LiteLLM のレスポンスには、使用トークン数が含まれています。

**レスポンス構造**:

```python
response = litellm.completion(...)
# response.usage に使用量情報が含まれる
# response.usage.prompt_tokens  # 入力トークン数
# response.usage.completion_tokens  # 出力トークン数
# response.usage.total_tokens  # 合計トークン数
```

**実装例**:

```python
def generate_response(self, messages: List[Message], system_prompt: str | None = None) -> tuple[str, dict]:
    """応答を生成し、トークン使用量も返す"""
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
        "model_used": response.model,  # 実際に使用されたモデル
        "latency_ms": latency_ms,
    }

    result = response.choices[0].message.content
    return result, token_info
```

### 2.2 コスト計算

各モデルの価格に基づいてコストを計算します。

**価格表（2026 年 1 月現在）**:

| モデル                              | 入力コスト           | 出力コスト           |
| ----------------------------------- | -------------------- | -------------------- |
| `anthropic/claude-3-haiku-20240307` | $0.25/100 万トークン | $1.25/100 万トークン |
| `anthropic/claude-haiku-4.5`        | $1/100 万トークン    | $5/100 万トークン    |
| `anthropic/claude-sonnet-4.5`       | $3/100 万トークン    | $15/100 万トークン   |
| `anthropic/claude-opus-4.5`         | $5/100 万トークン    | $25/100 万トークン   |
| `anthropic/claude-3-haiku-20240307` | $0.25/100 万トークン | $1.25/100 万トークン |

**コスト計算関数**:

```python
def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """トークン数からコストを計算（USD）"""
    pricing = {
        "anthropic/claude-3-haiku-20240307": (0.25 / 1_000_000, 1.25 / 1_000_000),
        "anthropic/claude-sonnet-4.5": (3.0 / 1_000_000, 15.0 / 1_000_000),
        "anthropic/claude-opus-4.5": (5.0 / 1_000_000, 25.0 / 1_000_000),
        "anthropic/claude-3-haiku-20240307": (0.25 / 1_000_000, 1.25 / 1_000_000),
    }

    input_price, output_price = pricing.get(model, (0, 0))
    cost = (input_tokens * input_price) + (output_tokens * output_price)
    return round(cost, 6)  # 小数点以下6桁まで
```

### 2.3 やり取りごとの記録

各 API 呼び出しごとに、以下の情報を記録します:

- セッションキー
- タイムスタンプ
- 使用モデル
- 入力トークン数
- 出力トークン数
- 合計トークン数
- 推定コスト
- レイテンシ

### 2.4 月ごとの集計

月ごとの累計トークン数とコストを集計します。

**集計テーブル（オプション）**:

```sql
CREATE TABLE monthly_usage (
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

CREATE INDEX idx_monthly_usage_year_month ON monthly_usage(year, month);
```

**集計方法**:

1. **リアルタイム集計**: 各 API 呼び出し後に集計テーブルを更新
2. **バッチ集計**: 定期的（例: 毎時、毎日）に集計を実行

---

## 3. 実装アプローチ

### 3.1 アーキテクチャ

```txt
┌─────────────────┐
│  LiteLLMProvider│
│  (generate_     │
│   response)     │
└────────┬────────┘
         │
         │ トークン情報を返す
         ▼
┌─────────────────┐
│  AuditLogger    │
│  (log_interaction)│
└────────┬────────┘
         │
         ├─→ SQLite (audit_logs)
         └─→ 月次集計更新
```

### 3.2 実装ステップ

#### Step 1: AuditLogger クラスの作成

```python
# src/kotonoha_bot/audit/logger.py
class AuditLogger:
    """監査ログを記録するクラス"""

    def log_interaction(
        self,
        session_key: str,
        event_type: str,
        user_id: int | None,
        channel_id: int | None,
        user_message: str,
        bot_response: str,
        token_info: dict,
        model_used: str,
        error: Exception | None = None,
    ) -> None:
        """やり取りをログに記録"""
        pass

    def get_monthly_usage(self, year: int, month: int) -> dict:
        """月ごとの使用量を取得"""
        pass
```

#### Step 2: LiteLLMProvider の拡張

```python
# src/kotonoha_bot/ai/litellm_provider.py
def generate_response(...) -> tuple[str, dict]:
    """応答とトークン情報を返す"""
    # 既存の実装を拡張
    # トークン情報を返すように変更
```

#### Step 3: MessageHandler での統合

```python
# src/kotonoha_bot/bot/handlers.py
response_text, token_info = self.ai_provider.generate_response(...)
self.audit_logger.log_interaction(...)
```

### 3.3 データベーススキーマの追加

既存の `sessions.db` に `audit_logs` テーブルと `monthly_usage` テーブルを追加。

---

## 4. 実装の優先順位

### Phase 1 の拡張: 基本監査ログ（オプション）

- [ ] `AuditLogger` クラスの実装
- [ ] SQLite テーブルの追加（`audit_logs`）
- [ ] LiteLLM からのトークン情報取得
- [ ] 基本的なログ記録機能

### Phase 4 以降: トークン使用量追跡（オプション）

- [ ] コスト計算機能
- [ ] 月ごとの集計機能
- [ ] 使用量統計の表示機能（管理者コマンド）

### Phase 7 以降: 高度な機能（オプション）

- [ ] ログの検索・フィルタリング機能
- [ ] ログのエクスポート機能
- [ ] データ保持期間の自動管理
- [ ] アラート機能（使用量が閾値を超えた場合）

---

## 5. 設定オプション

### 環境変数

```bash
# 監査ログの有効化
AUDIT_LOG_ENABLED=true

# ログの保存先
AUDIT_LOG_DATABASE_PATH=./data/audit_logs.db

# データ保持期間（日数）
AUDIT_LOG_RETENTION_DAYS=90

# メッセージ内容の記録（true: 完全記録、false: 要約のみ）
AUDIT_LOG_FULL_MESSAGE=true

# 月次集計の有効化
MONTHLY_USAGE_TRACKING_ENABLED=true
```

---

## 6. パフォーマンスへの影響

### 考慮事項

- **非同期処理**: ログ記録を非同期で実行し、応答速度への影響を最小化
- **バッチ処理**: 複数のログをまとめて書き込む
- **インデックス**: 検索頻度の高いカラムにインデックスを設定
- **アーカイブ**: 古いログを別のテーブルやファイルに移動

### 最適化案

```python
# 非同期ログ記録
import asyncio
from queue import Queue

class AsyncAuditLogger:
    def __init__(self):
        self.log_queue = Queue()
        self.worker_task = None

    async def log_interaction_async(self, ...):
        """非同期でログを記録"""
        await self.log_queue.put(...)

    async def _worker(self):
        """バックグラウンドワーカー"""
        while True:
            # キューからログを取得して書き込み
            pass
```

---

## 7. セキュリティとコンプライアンス

### GDPR への対応

- **データ削除権**: ユーザーが自分のログを削除できる機能
- **データポータビリティ**: ユーザーが自分のログをエクスポートできる機能
- **同意の取得**: ログ記録についてユーザーに通知

### ログのセキュリティ保護

- **暗号化**: 機密情報を含むログの暗号化
- **アクセス制御**: ログへのアクセスを管理者のみに制限
- **監査**: ログへのアクセス自体も記録

---

## 8. 参考実装

### LiteLLM の使用量情報

```python
import litellm

response = litellm.completion(
    model="anthropic/claude-3-haiku-20240307",
    messages=[...],
)

# 使用量情報
print(response.usage.prompt_tokens)      # 入力トークン数
print(response.usage.completion_tokens)  # 出力トークン数
print(response.usage.total_tokens)       # 合計トークン数
print(response.model)                    # 実際に使用されたモデル
```

### コスト計算の実装例

```python
def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """トークン数からコストを計算"""
    # モデル名からプロバイダーとモデルを抽出
    if model.startswith("anthropic/"):
        model_name = model.replace("anthropic/", "")
        pricing = {
            "claude-3-haiku-20240307": (0.25 / 1_000_000, 1.25 / 1_000_000),
            "claude-sonnet-4.5": (3.0 / 1_000_000, 15.0 / 1_000_000),
            "claude-opus-4.5": (5.0 / 1_000_000, 25.0 / 1_000_000),
            "claude-3-haiku-20240307": (0.25 / 1_000_000, 1.25 / 1_000_000),
        }

        if model_name in pricing:
            input_price, output_price = pricing[model_name]
            return round((input_tokens * input_price) + (output_tokens * output_price), 6)

    return 0.0
```

---

## 9. 次のステップ

1. **要件の確定**: どの情報を記録するか、どの程度の詳細度が必要か
2. **実装フェーズの決定**: Phase 1 の拡張として実装するか、Phase 4 以降で実装するか
3. **データベース設計の確定**: スキーマの最終決定
4. **プライバシーポリシーの作成**: ログ記録についてのポリシー
5. **実装開始**: プロトタイプの作成とテスト

---

**作成日**: 2026 年 1 月
**ステータス**: 要検討
**優先度**: 中〜高（コスト管理の観点から重要）
