# 外部インターフェース仕様書・API 仕様書

## 1. Discord API インターフェース

### 1.1 WebSocket 接続

**エンドポイント**: `wss://gateway.discord.gg`

**認証**: Bot Token を使用

**イベント**:

- `READY`: Bot が接続完了
- `MESSAGE_CREATE`: メッセージが作成された
- `THREAD_CREATE`: スレッドが作成された
- `THREAD_UPDATE`: スレッドが更新された
- `THREAD_DELETE`: スレッドが削除された

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

#### 1.2.2 スレッド作成

**エンドポイント**: `POST /channels/{channel_id}/threads`

**リクエスト**:

```json
{
  "name": "スレッド名",
  "type": 11, // パブリックスレッド
  "message_id": 1234567890123456789
}
```

**レスポンス**:

```json
{
  "id": "1111111111111111111",
  "name": "スレッド名",
  "type": 11
}
```

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

---

## 2. LLM API インターフェース（LiteLLM 経由）

LiteLLM を使用して、複数の LLM プロバイダーを統一インターフェースで利用する。

### 2.1 LiteLLM 統一インターフェース

**使用方法**: LiteLLM の `completion()` 関数を使用

```python
import litellm

response = litellm.completion(
    model="anthropic/claude-3-haiku-20240307",  # 開発用（レガシー、超低コスト）、または anthropic/claude-opus-4-5（本番用）
    messages=[
        {"role": "system", "content": "システムプロンプト"},
        {"role": "user", "content": "ユーザーメッセージ"}
    ],
    temperature=0.7,
    max_tokens=2048
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
    }
}
```

### 2.2 対応プロバイダーとモデル

| フェーズ | プロバイダー | モデル名                            | 用途                                                 |
| -------- | ------------ | ----------------------------------- | ---------------------------------------------------- |
| 開発     | Anthropic    | `anthropic/claude-3-haiku-20240307` | 超低コストでの開発・テスト（制限なし）               |
| 調整     | Anthropic    | `anthropic/claude-sonnet-4-5`       | 品質調整・最適化（$3/input MTok, $15/output MTok）   |
| 本番     | Anthropic    | `anthropic/claude-opus-4-5`         | 最高品質の本番運用（$5/input MTok, $25/output MTok） |

### 2.3 Claude 3 Haiku API（レガシー・開発用）

**エンドポイント**: `POST https://api.anthropic.com/v1/messages`

**認証**: 環境変数 `ANTHROPIC_API_KEY`

**料金**（2026 年 1 月現在）:

- 入力: $1/100 万トークン
- 出力: $5/100 万トークン
- 1 回あたり約 0.3 セント（入力 500 トークン、出力 500 トークンの場合）

**コスト例**:

- 月 1,000 回: 約$3（約 450 円）
- 月 5,000 回: 約$15（約 2,250 円）

**メリット**: 無料枠の制限がなく、開発から本番まで同じプロバイダーで統一可能

### 2.4 Claude API（本番用）

**エンドポイント**: `POST https://api.anthropic.com/v1/messages`

**認証**: 環境変数 `ANTHROPIC_API_KEY`

**モデル**（[公式モデル一覧](https://platform.claude.com/docs/en/about-claude/models/overview)）:

- Claude 3 Haiku（レガシー）: `claude-3-haiku-20240307`（$0.25/input MTok, $1.25/output MTok）
- Claude Sonnet 4.5: `claude-sonnet-4-5`（$3/input MTok, $15/output MTok）
- Claude Opus 4.5: `claude-opus-4-5`（$5/input MTok, $25/output MTok）

### 2.5 エラーハンドリング

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
    model="anthropic/claude-opus-4-5",
    messages=messages,
    fallbacks=["anthropic/claude-3-haiku-20240307"]  # フォールバック先（本番でOpusがダウンした場合）
)
```

**リトライロジック**:

一時的なエラー（`InternalServerError`, `RateLimitError`）に対して、指数バックオフで自動リトライを実行します。

```python
# リトライ設定（環境変数）
LLM_MAX_RETRIES=3              # 最大リトライ回数（デフォルト: 3）
LLM_RETRY_DELAY_BASE=1.0       # 指数バックオフのベース遅延（秒、デフォルト: 1.0）

# リトライ動作
# 1回目: 即座にリトライ
# 2回目: 1秒待機後にリトライ
# 3回目: 2秒待機後にリトライ
# 4回目: 4秒待機後にリトライ（最大リトライ回数に達した場合はエラーを返す）
```

**リトライ対象のエラー**:

- `litellm.InternalServerError`: サーバーエラー（HTTP 500, 529 など）
- `litellm.RateLimitError`: レート制限超過（HTTP 429）

**リトライ対象外のエラー**:

- `litellm.AuthenticationError`: 認証エラー（即座に失敗）

---

## 3. 内部 API 仕様

### 3.1 Session Manager API

#### 3.1.1 `get_session(session_key: str) -> ChatSession | None`

**説明**: セッションを取得します。

**パラメータ**:

- `session_key`: セッションキー

**戻り値**: `ChatSession` オブジェクト、または `None`

**例外**:

- `DatabaseError`: データベースエラー

#### 3.1.2 `create_session(session_key: str, session_type: str, **kwargs) -> ChatSession`

**説明**: 新しいセッションを作成します。

**パラメータ**:

- `session_key`: セッションキー
- `session_type`: セッションタイプ（`mention`, `thread`, `eavesdrop`）
- `**kwargs`: 追加パラメータ（`channel_id`, `thread_id`, `user_id` など）

**戻り値**: `ChatSession` オブジェクト

**例外**:

- `ValueError`: 無効なパラメータ
- `DatabaseError`: データベースエラー

#### 3.1.3 `update_session(session_key: str, message: Message) -> None`

**説明**: セッションの会話履歴を更新します。

**パラメータ**:

- `session_key`: セッションキー
- `message`: メッセージオブジェクト

**例外**:

- `KeyError`: セッションが見つからない
- `DatabaseError`: データベースエラー

#### 3.1.4 `save_session(session_key: str) -> None`

**説明**: セッションを SQLite に保存します。

**パラメータ**:

- `session_key`: セッションキー

**例外**:

- `KeyError`: セッションが見つからない
- `DatabaseError`: データベースエラー

---

### 3.2 AI Service API

#### 3.2.1 `generate_response(messages: List[Message], system_prompt: str = None) -> str`

**説明**: AI で応答を生成します。

**パラメータ**:

- `messages`: 会話履歴
- `system_prompt`: システムプロンプト（オプション）

**戻り値**: AI が生成した応答テキスト

**例外**:

- `APIError`: API エラー
- `RateLimitError`: レート制限超過
- `TimeoutError`: タイムアウト

#### 3.2.2 `judge_should_respond(messages: List[Message]) -> bool`

**説明**: 聞き耳型で発言すべきか判定します（アプローチ 1）。

**パラメータ**:

- `messages`: 会話履歴（直近 10 件）

**戻り値**: `True`（発言すべき）または `False`（発言しない）

**例外**:

- `APIError`: API エラー
- `RateLimitError`: レート制限超過

---

### 3.3 Message Router API

#### 3.3.1 `route_message(message: discord.Message) -> None`

**説明**: メッセージをルーティングします。

**パラメータ**:

- `message`: Discord メッセージオブジェクト

**処理**:

1. 会話の契機を判定
2. 適切なハンドラーにメッセージを渡す

**例外**:

- `ValueError`: 無効なメッセージ

---

### 3.4 Database API

#### 3.4.1 `get_session(session_key: str) -> dict | None`

**説明**: SQLite からセッションを取得します。

**パラメータ**:

- `session_key`: セッションキー

**戻り値**: セッションデータ（辞書形式）、または `None`

**例外**:

- `DatabaseError`: データベースエラー

#### 3.4.2 `save_session(session_data: dict) -> None`

**説明**: セッションを SQLite に保存します。

**パラメータ**:

- `session_data`: セッションデータ（辞書形式）

**例外**:

- `DatabaseError`: データベースエラー

#### 3.4.3 `get_messages(session_key: str, limit: int = 50) -> List[dict]`

**説明**: メッセージ履歴を取得します。

**パラメータ**:

- `session_key`: セッションキー
- `limit`: 取得件数（デフォルト: 50）

**戻り値**: メッセージデータのリスト

**例外**:

- `DatabaseError`: データベースエラー

#### 3.4.4 `add_message(session_key: str, message_data: dict) -> None`

**説明**: メッセージを追加します。

**パラメータ**:

- `session_key`: セッションキー
- `message_data`: メッセージデータ（辞書形式）

**例外**:

- `DatabaseError`: データベースエラー

---

## 4. データ形式

### 4.1 Message オブジェクト

```python
@dataclass
class Message:
    role: str  # "user" | "assistant" | "system"
    content: str
    timestamp: datetime
    message_id: int | None = None
```

### 4.2 ChatSession オブジェクト

```python
@dataclass
class ChatSession:
    session_key: str
    session_type: str
    messages: List[Message]
    created_at: datetime
    last_activity: datetime
    channel_id: int | None = None
    thread_id: int | None = None
    user_id: int | None = None
```

---

## 5. エラーコード

### 5.1 内部エラーコード

| コード | 説明                     |
| ------ | ------------------------ |
| `E001` | セッションが見つからない |
| `E002` | 無効なセッションキー     |
| `E003` | データベースエラー       |
| `E004` | API エラー               |
| `E005` | レート制限超過           |
| `E006` | タイムアウト             |

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

---

**作成日**: 2026 年 1 月 14 日
**バージョン**: 1.0
**作成者**: kotonoha-bot 開発チーム
