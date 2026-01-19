# 外部インターフェース仕様書・API 仕様書

## 1. Discord API インターフェース

### 1.1 WebSocket 接続

**エンドポイント**: `wss://gateway.discord.gg`

**認証**: Bot Token を使用（環境変数 `DISCORD_TOKEN`）

**イベント**:

- `READY`: Bot が接続完了
- `MESSAGE_CREATE`: メッセージが作成された
- `THREAD_CREATE`: スレッドが作成された
- `THREAD_UPDATE`: スレッドが更新された
- `THREAD_DELETE`: スレッドが削除された

**必要な Intents**:

- `MESSAGE_CONTENT_INTENT`: メッセージ内容の読み取りに必須

### 1.2 HTTP API

#### 1.2.1 メッセージ送信

**エンドポイント**: `POST /channels/{channel_id}/messages`

**リクエスト**:

```json
{
  "content": "応答メッセージ",
  "thread_id": 1234567890 // オプション（スレッド内の場合）
}
```

**レスポンス**:

```json
{
  "id": "1234567890123456789",
  "channel_id": "9876543210987654321",
  "content": "応答メッセージ",
  "timestamp": "2024-01-15T10:30:00.000Z"
}
```

**実装**: `discord.py` ライブラリ経由で自動処理

#### 1.2.2 スレッド作成

**エンドポイント**: `POST /channels/{channel_id}/messages/{message_id}/threads`

**リクエスト**:

```json
{
  "name": "スレッド名",
  "type": 11, // パブリックスレッド
  "auto_archive_duration": 60 // オプション（分）。未設定の場合はサーバーのデフォルト値を使用
}
```

**レスポンス**:

```json
{
  "id": "1111111111111111111",
  "name": "スレッド名",
  "type": 11,
  "auto_archive_duration": 60
}
```

**実装**: `src/kotonoha_bot/bot/handlers.py` の `_create_thread_and_respond` メソッド

**設定**: 環境変数 `THREAD_AUTO_ARCHIVE_DURATION` で設定可能（未設定の場合はサーバーのデフォルト値を使用）

**有効な値**: 60 (1 時間), 1440 (1 日), 4320 (3 日), 10080 (7 日), 43200 (30 日)

#### 1.2.3 メッセージ履歴取得

**エンドポイント**: `GET /channels/{channel_id}/messages`

**クエリパラメータ**:

- `limit`: 取得件数（最大 100）
- `before`: このメッセージ ID より前を取得

**レスポンス**:

```json
[
  {
    "id": "1234567890123456789",
    "content": "メッセージ内容",
    "author": {
      "id": "9876543210987654321",
      "username": "ユーザー名"
    },
    "timestamp": "2024-01-15T10:30:00.000Z"
  }
]
```

**実装**: `discord.py` ライブラリ経由で自動処理（聞き耳型の `ConversationBuffer` で使用）

---

## 2. LLM API インターフェース（LiteLLM 経由）

LiteLLM を使用して、複数の LLM プロバイダーを統一インターフェースで利用する。

### 2.1 LiteLLM 統一インターフェース

**使用方法**: LiteLLM の `completion()` 関数を使用

```python
import litellm

response = litellm.completion(
    model="anthropic/claude-sonnet-4-5",  # デフォルトモデル
    messages=[
        {"role": "system", "content": "システムプロンプト"},
        {"role": "user", "content": "ユーザーメッセージ"}
    ],
    temperature=0.7,
    max_tokens=2048,
    fallbacks=["anthropic/claude-3-haiku-20240307"]  # オプション
)
```

**レスポンス**:

```python
{
    "choices": [
        {
            "message": {
                "role": "assistant",
                "content": "AI応答"
            },
            "finish_reason": "stop"
        }
    ],
    "usage": {
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150
    },
    "model": "anthropic/claude-sonnet-4-5"  # 実際に使用されたモデル名
}
```

**実装**: `src/kotonoha_bot/ai/litellm_provider.py`

### 2.2 対応プロバイダーとモデル

| 用途           | プロバイダー | モデル名                            | 環境変数                | 料金（2026 年 1 月現在）              |
| -------------- | ------------ | ----------------------------------- | ----------------------- | ------------------------------------- |
| デフォルト     | Anthropic    | `anthropic/claude-sonnet-4-5`       | `LLM_MODEL`             | \$3/input MTok, \$15/output MTok      |
| フォールバック | Anthropic    | `anthropic/claude-3-haiku-20240307` | `LLM_FALLBACK_MODEL`    | \$0.25/input MTok, \$1.25/output MTok |
| 判定用         | Anthropic    | `anthropic/claude-haiku-4-5`        | `EAVESDROP_JUDGE_MODEL` | \$1.00/input MTok, \$5.00/output MTok |
| 本番用         | Anthropic    | `anthropic/claude-opus-4-5`         | `LLM_MODEL`（設定時）   | \$5/input MTok, \$25/output MTok      |

**実装状況**:

- デフォルトモデル: `anthropic/claude-sonnet-4-5`（`Config.LLM_MODEL`）
- フォールバックモデル: 環境変数 `LLM_FALLBACK_MODEL` で設定可能（未設定の場合は `None`）
- 判定用モデル: `anthropic/claude-haiku-4-5`（`Config.EAVESDROP_JUDGE_MODEL`）

### 2.3 エラーハンドリング

LiteLLM は各プロバイダーのエラーを統一形式で返す。

**レート制限エラー**:

```python
litellm.RateLimitError: Rate limit exceeded
```

**サーバーエラー（過負荷など）**:

```python
litellm.InternalServerError: AnthropicError - {"type":"error","error":{"type":"overloaded_error","message":"Overloaded"}}
# HTTP 529 エラーも InternalServerError として扱われる
```

**認証エラー**:

```python
litellm.AuthenticationError: Invalid API key
```

**フォールバック設定**:

```python
response = litellm.completion(
    model="anthropic/claude-sonnet-4-5",
    messages=messages,
    fallbacks=["anthropic/claude-3-haiku-20240307"]  # フォールバック先
)
```

**実装**: `src/kotonoha_bot/ai/litellm_provider.py` の `generate_response` メソッド

### 2.4 リトライロジック

一時的なエラー（`InternalServerError`, `RateLimitError`）に対して、指数バックオフで自動リトライを実行します。

**リトライ設定（環境変数）**:

```env
LLM_MAX_RETRIES=3              # 最大リトライ回数（デフォルト: 3）
LLM_RETRY_DELAY_BASE=1.0       # 指数バックオフのベース遅延（秒、デフォルト: 1.0）
```

**リトライ動作**:

- 1 回目: 即座にリトライ
- 2 回目: 1 秒待機後にリトライ
- 3 回目: 2 秒待機後にリトライ
- 4 回目: 4 秒待機後にリトライ（最大リトライ回数に達した場合はエラーを返す）

**リトライ対象のエラー**:

- `litellm.InternalServerError`: サーバーエラー（HTTP 500, 529 など）
- `litellm.RateLimitError`: レート制限超過（HTTP 429）

**リトライ対象外のエラー**:

- `litellm.AuthenticationError`: 認証エラー（即座に失敗）

**実装**: `src/kotonoha_bot/ai/litellm_provider.py` の `generate_response` メソッド

### 2.5 レート制限管理

**トークンバケットアルゴリズム**:

- 容量: デフォルト 50 リクエスト（`RATE_LIMIT_CAPACITY`）
- 補充レート: デフォルト 0.8 リクエスト/秒（`RATE_LIMIT_REFILL`）
- 監視ウィンドウ: デフォルト 60 秒（`RATE_LIMIT_WINDOW`）
- 警告閾値: デフォルト 0.9（`RATE_LIMIT_THRESHOLD`）

**実装**: `src/kotonoha_bot/rate_limit/token_bucket.py`, `src/kotonoha_bot/rate_limit/monitor.py`

**設定（環境変数）**:

```env
RATE_LIMIT_CAPACITY=50          # レート制限の上限値（1分間に50リクエストまで）
RATE_LIMIT_REFILL=0.8           # 補充レート（リクエスト/秒、1分間に約48リクエスト）
RATE_LIMIT_WINDOW=60            # 監視ウィンドウ（秒）
RATE_LIMIT_THRESHOLD=0.9        # 警告閾値（0.0-1.0）
```

---

## 3. 内部 API 仕様

### 3.1 Session Manager API

**実装ファイル**: `src/kotonoha_bot/session/manager.py`

#### 3.1.1 `get_session(session_key: str) -> ChatSession | None`

**説明**: セッションを取得します。メモリ内にあればそれを返し、なければ SQLite から復元を試みます。

**パラメータ**:

- `session_key`: セッションキー（形式: `mention:{user_id}`, `thread:{thread_id}`, `eavesdrop:{channel_id}`）

**戻り値**: `ChatSession` オブジェクト、または `None`

**例外**:

- `DatabaseError`: データベースエラー

#### 3.1.2 `create_session`

**シグネチャ**: `create_session(session_key: str, session_type: SessionType,
**kwargs) -> ChatSession`

**説明**: 新しいセッションを作成します。

**パラメータ**:

- `session_key`: セッションキー
- `session_type`: セッションタイプ（`"mention"`, `"thread"`, `"eavesdrop"`）
- `**kwargs`: 追加パラメータ（`channel_id`, `thread_id`, `user_id` など）

**戻り値**: `ChatSession` オブジェクト

**例外**:

- `ValueError`: 無効なパラメータ
- `DatabaseError`: データベースエラー

#### 3.1.3 `add_message(session_key: str, role: MessageRole, content: str) -> None`

**説明**: セッションにメッセージを追加します。

**パラメータ**:

- `session_key`: セッションキー
- `role`: メッセージの役割（`MessageRole.USER`, `MessageRole.ASSISTANT`, `MessageRole.SYSTEM`）
- `content`: メッセージ内容

**例外**:

- `KeyError`: セッションが見つからない

#### 3.1.4 `save_session(session_key: str) -> None`

**説明**: セッションを SQLite に保存します。

**パラメータ**:

- `session_key`: セッションキー

**例外**:

- `KeyError`: セッションが見つからない
- `DatabaseError`: データベースエラー

#### 3.1.5 `save_all_sessions() -> None`

**説明**: 全セッションを SQLite に保存します。

**例外**:

- `DatabaseError`: データベースエラー

#### 3.1.6 `cleanup_old_sessions() -> None`

**説明**: 古いセッションをメモリから削除します（タイムアウト時間を超えたセッション）。

**設定**: 環境変数 `SESSION_TIMEOUT_HOURS`（デフォルト: 24 時間）

---

### 3.2 AI Service API

**実装ファイル**: `src/kotonoha_bot/ai/litellm_provider.py`

#### 3.2.1 `generate_response`

**シグネチャ**: `generate_response(messages: list[Message],
system_prompt: str | None = None, model: str | None = None,
max_tokens: int | None = None) -> str`

**説明**: AI で応答を生成します。

**パラメータ**:

- `messages`: 会話履歴（`Message` オブジェクトのリスト）
- `system_prompt`: システムプロンプト（オプション）
- `model`: 使用するモデル名（オプション、未指定の場合はデフォルトモデル）
- `max_tokens`: 最大トークン数（オプション、未指定の場合は `Config.LLM_MAX_TOKENS`）

**戻り値**: AI が生成した応答テキスト

**例外**:

- `litellm.AuthenticationError`: 認証エラー
- `litellm.InternalServerError`: サーバーエラー（リトライ後も失敗した場合）
- `litellm.RateLimitError`: レート制限超過（リトライ後も失敗した場合）
- `RuntimeError`: トークンバケットからトークンを取得できなかった場合

**実装詳細**:

- レート制限チェックとトークン取得を自動実行
- 一時的なエラーに対して指数バックオフでリトライ
- フォールバックモデルが設定されている場合は自動切り替え

**実装ファイル**: `src/kotonoha_bot/ai/litellm_provider.py`

#### 3.2.2 `get_last_used_model() -> str`

**説明**: 最後に使用したモデル名を取得します。

**戻り値**: 最後に使用したモデル名（未使用の場合はデフォルトモデル）

#### 3.2.3 `get_rate_limit_usage(endpoint: str = "claude-api") -> float`

**説明**: レート制限の使用率を取得します。

**パラメータ**:

- `endpoint`: API エンドポイント（デフォルト: `"claude-api"`）

**戻り値**: 使用率（0.0-1.0、パーセンテージに変換する場合は \* 100）

---

### 3.3 Message Router API

**実装ファイル**: `src/kotonoha_bot/router/message_router.py`

#### 3.3.1 `route(message: discord.Message) -> ConversationTrigger`

**説明**: メッセージをルーティングし、会話の契機を判定します。

**パラメータ**:

- `message`: Discord メッセージオブジェクト

**戻り値**: 会話の契機（`"mention"`, `"thread"`, `"eavesdrop"`, `"none"`）

**処理**:

1. Bot 自身のメッセージは `"none"` を返す
2. Bot へのメンションがある場合は `"mention"` を返す
3. Bot が作成したスレッド内のメッセージの場合は `"thread"` を返す
4. 聞き耳型が有効なチャンネルの場合は `"eavesdrop"` を返す
5. それ以外の場合は `"none"` を返す

---

### 3.4 Database API

**実装ファイル**: `src/kotonoha_bot/db/sqlite.py`

#### 3.4.1 `save_session(session: ChatSession) -> None`

**説明**: セッションを SQLite に保存します。

**パラメータ**:

- `session`: `ChatSession` オブジェクト

**例外**:

- `DatabaseError`: データベースエラー

**実装詳細**:

- メッセージは JSON 形式で `messages` カラムに保存
- `INSERT OR REPLACE` を使用して既存セッションを更新

#### 3.4.2 `load_session(session_key: str) -> ChatSession | None`

**説明**: SQLite からセッションを取得します。

**パラメータ**:

- `session_key`: セッションキー

**戻り値**: `ChatSession` オブジェクト、または `None`

**例外**:

- `DatabaseError`: データベースエラー

**実装詳細**:

- JSON 形式のメッセージを `Message` オブジェクトに復元

#### 3.4.3 `load_all_sessions() -> list[ChatSession]`

**説明**: 全セッションを SQLite から取得します。

**戻り値**: `ChatSession` オブジェクトのリスト

**例外**:

- `DatabaseError`: データベースエラー

#### 3.4.4 `delete_session(session_key: str) -> None`

**説明**: セッションを SQLite から削除します。

**パラメータ**:

- `session_key`: セッションキー

**例外**:

- `DatabaseError`: データベースエラー

**データベース設定**:

- ファイル名: `sessions.db`（環境変数 `DATABASE_NAME` で設定可能）
- パス: `./data/sessions.db`（環境変数 `DATABASE_PATH` で設定可能）
- WAL モード: 有効（長時間稼働時のファイルロック問題を回避）
- タイムアウト: 30 秒

---

## 4. データ形式

### 4.1 Message オブジェクト

**実装ファイル**: `src/kotonoha_bot/session/models.py`

```python
@dataclass
class Message:
    role: MessageRole  # MessageRole.USER | MessageRole.ASSISTANT | MessageRole.SYSTEM
    content: str
    timestamp: datetime

    def to_dict(self) -> dict:
        """辞書形式に変換"""
        return {
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> Message:
        """辞書から作成"""
        return cls(
            role=MessageRole(data["role"]),
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )
```

### 4.2 ChatSession オブジェクト

**実装ファイル**: `src/kotonoha_bot/session/models.py`

```python
@dataclass
class ChatSession:
    session_key: str  # 形式: "mention:{user_id}", "thread:{thread_id}", "eavesdrop:{channel_id}"
    session_type: SessionType  # "mention" | "thread" | "eavesdrop"
    messages: list[Message]
    created_at: datetime
    last_active_at: datetime
    channel_id: int | None = None
    thread_id: int | None = None
    user_id: int | None = None

    def add_message(self, role: MessageRole, content: str) -> None:
        """メッセージを追加"""
        message = Message(role=role, content=content)
        self.messages.append(message)
        self.last_active_at = datetime.now()

    def to_dict(self) -> dict:
        """辞書形式に変換"""
        return {
            "session_key": self.session_key,
            "session_type": self.session_type,
            "messages": [msg.to_dict() for msg in self.messages],
            "created_at": self.created_at.isoformat(),
            "last_active_at": self.last_active_at.isoformat(),
            "channel_id": self.channel_id,
            "thread_id": self.thread_id,
            "user_id": self.user_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ChatSession:
        """辞書から作成"""
        messages = [Message.from_dict(msg) for msg in data["messages"]]
        return cls(
            session_key=data["session_key"],
            session_type=data["session_type"],
            messages=messages,
            created_at=datetime.fromisoformat(data["created_at"]),
            last_active_at=datetime.fromisoformat(data["last_active_at"]),
            channel_id=data.get("channel_id"),
            thread_id=data.get("thread_id"),
            user_id=data.get("user_id"),
        )
```

### 4.3 セッションキーの形式

| セッションタイプ | 形式                     | 例                    |
| ---------------- | ------------------------ | --------------------- |
| メンション型     | `mention:{user_id}`      | `mention:123456789`   |
| スレッド型       | `thread:{thread_id}`     | `thread:987654321`    |
| 聞き耳型         | `eavesdrop:{channel_id}` | `eavesdrop:111222333` |

---

## 5. エラーコード

### 5.1 内部エラーコード

| コード | 説明                     | 実装ファイル                    |
| ------ | ------------------------ | ------------------------------- |
| `E001` | セッションが見つからない | `src/kotonoha_bot/session/`     |
| `E002` | 無効なセッションキー     | `src/kotonoha_bot/session/`     |
| `E003` | データベースエラー       | `src/kotonoha_bot/db/sqlite.py` |
| `E004` | API エラー               | `src/kotonoha_bot/ai/`          |
| `E005` | レート制限超過           | `src/kotonoha_bot/rate_limit/`  |
| `E006` | タイムアウト             | `src/kotonoha_bot/ai/`          |

### 5.2 エラーレスポンス形式

```python
{
    "error": {
        "code": "E001",
        "message": "セッションが見つかりませんでした",
        "details": {}
    }
}
```

**実装**: `src/kotonoha_bot/errors/` モジュール

---

## 6. ヘルスチェック API

**実装ファイル**: `src/kotonoha_bot/health.py`

### 6.1 `/health` エンドポイント

**説明**: Bot の健康状態を確認します。

**リクエスト**: `GET /health`

**レスポンス**:

```json
{
  "status": "healthy",
  "timestamp": "2026-01-15T10:30:00.000Z"
}
```

**HTTP ステータスコード**:

- `200 OK`: Bot が正常に動作している
- `503 Service Unavailable`: Bot が正常に動作していない

### 6.2 `/ready` エンドポイント

**説明**: Bot が準備完了しているか確認します。

**リクエスト**: `GET /ready`

**レスポンス**:

```json
{
  "status": "ready",
  "timestamp": "2026-01-15T10:30:00.000Z"
}
```

**HTTP ステータスコード**:

- `200 OK`: Bot が準備完了している
- `503 Service Unavailable`: Bot が準備完了していない

**設定**: 環境変数 `HEALTH_CHECK_ENABLED`（デフォルト: `true`）、`HEALTH_CHECK_PORT`（デフォルト: `8080`）

---

**作成日**: 2026 年 1 月 14 日  
**最終更新日**: 2026 年 1 月（現在の実装に基づいて改訂）  
**バージョン**: 2.0  
**作成者**: kotonoha-bot 開発チーム

### 更新履歴

- **v2.0** (2026-01): 現在の実装に基づいて改訂
  - モデル名を最新の実装に更新（Claude Sonnet 4.5, Claude Haiku 4.5）
  - セッションキーの形式を追加
  - データベースの実装詳細を追加（JSON 形式でのメッセージ保存）
  - レート制限管理の詳細を追加
  - リトライロジックの詳細を追加
  - 内部 API の実装ファイルパスを追加
  - ヘルスチェック API を追加
  - スレッド作成 API の `auto_archive_duration` 設定を追加
- **v1.0** (2026-01-14): 初版リリース
