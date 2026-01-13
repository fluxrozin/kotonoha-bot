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

## 2. Gemini API インターフェース

### 2.1 チャット完了 API

**エンドポイント**: `POST https://generativeai.googleapis.com/v1beta/models/{model}:generateContent`

**認証**: API Key（`X-Goog-Api-Key` ヘッダー）

**リクエスト**:

```json
{
  "contents": [
    {
      "role": "user",
      "parts": [
        {
          "text": "ユーザーメッセージ"
        }
      ]
    }
  ],
  "generationConfig": {
    "temperature": 0.7,
    "maxOutputTokens": 2048
  }
}
```

**レスポンス**:

```json
{
  "candidates": [
    {
      "content": {
        "parts": [
          {
            "text": "AI応答"
          }
        ],
        "role": "model"
      },
      "finishReason": "STOP"
    }
  ]
}
```

### 2.2 モデル一覧

| モデル名           | 用途               | レート制限                 |
| ------------------ | ------------------ | -------------------------- |
| `gemini-1.5-flash` | 高速応答、判定処理 | 15 回/分（1,500 回/日）    |
| `gemini-1.5-pro`   | 高度なタスク       | 2 回/分（50 回/日）        |

### 2.3 エラーレスポンス

**429 Too Many Requests**:

```json
{
  "error": {
    "code": 429,
    "message": "Resource has been exhausted",
    "status": "RESOURCE_EXHAUSTED"
  }
}
```

**400 Bad Request**:

```json
{
  "error": {
    "code": 400,
    "message": "Invalid request",
    "status": "INVALID_ARGUMENT"
  }
}
```

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
- `session_type`: セッションタイプ（`mention`, `thread`, `dm`, `eavesdrop`）
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

**作成日**: 2026年1月14日
**バージョン**: 1.0
**作成者**: kotonoha-bot 開発チーム
