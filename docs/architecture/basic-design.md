# 基本設計書

## 1. システム概要

### 1.1 システムの目的

場面緘黙自助グループの Discord サーバー運営を支援するため、無料で利用可能なチャット AI 機能を統合した Discord ボット「Kotonoha（コトノハ）」を開発する。

### 1.2 システムの範囲

- Discord ボットアプリケーション
- AI チャット機能（Gemini API）
- 会話履歴管理（SQL + ChatSession ハイブリッド）
- 4 つの会話の契機（メンション/スレッド/DM/聞き耳型）
- CI/CD パイプライン
- Docker コンテナ化

### 1.3 システムの制約

- 無料 API のみを使用
- Python 3.14 を使用
- SQLite データベースを使用
- Synology NAS 上で動作

---

## 2. アーキテクチャ設計

### 2.1 システムアーキテクチャ

```mermaid
graph TB
    subgraph "アプリケーション層"
        Bot[Discord Bot Core]
        Router[Message Router]
        SessionMgr[Session Manager]
        AIService[AI Service]
        DBService[Database Service]
    end

    subgraph "データ層"
        MemSession[ChatSession Memory]
        SQLite[(SQLite Database)]
    end

    subgraph "外部サービス"
        Discord[Discord API]
        Gemini[Gemini API]
    end

    Bot --> Router
    Router --> SessionMgr
    Router --> AIService
    SessionMgr --> MemSession
    SessionMgr --> SQLite
    AIService --> Gemini
    Bot --> Discord
```

### 2.2 レイヤー構成

| レイヤー                 | 責務                         | 主要モジュール                  |
| ------------------------ | ---------------------------- | ------------------------------- |
| **プレゼンテーション層** | Discord イベントの受信・送信 | `bot.py`, `router/`             |
| **アプリケーション層**   | ビジネスロジック             | `session/`, `ai/`, `eavesdrop/` |
| **データアクセス層**     | データの永続化               | `database/`                     |
| **外部サービス層**       | 外部 API との通信            | `ai/gemini.py`                  |

---

## 3. モジュール設計

### 3.1 モジュール一覧

| モジュール                 | 責務                      | 依存関係                               |
| -------------------------- | ------------------------- | -------------------------------------- |
| `bot.py`                   | Discord Bot のメイン処理  | `router/`, `session/`, `ai/`           |
| `router/message_router.py` | メッセージのルーティング  | `session/`, `ai/`                      |
| `session/manager.py`       | セッション管理            | `session/chat_session.py`, `database/` |
| `session/chat_session.py`  | セッションクラス          | -                                      |
| `ai/base.py`               | AI プロバイダー抽象クラス | -                                      |
| `ai/gemini.py`             | Gemini API 実装           | `ai/base.py`                           |
| `eavesdrop/llm_judge.py`   | LLM 判断機能              | `ai/`                                  |
| `eavesdrop/rule_judge.py`  | ルールベース判断機能      | -                                      |
| `database/sqlite.py`       | SQLite 操作               | -                                      |
| `commands/chat.py`         | スラッシュコマンド        | `session/`                             |

### 3.2 モジュール間の依存関係

```mermaid
graph TD
    Bot[bot.py] --> Router[router/]
    Bot --> Session[session/]
    Bot --> AI[ai/]
    Bot --> Commands[commands/]

    Router --> Session
    Router --> AI
    Router --> Eavesdrop[eavesdrop/]

    Session --> DB[database/]
    Eavesdrop --> AI
    Commands --> Session
```

---

## 4. データ設計

### 4.1 データフロー

```mermaid
sequenceDiagram
    participant User as ユーザー
    participant Bot as Bot Core
    participant Router as Message Router
    participant Session as Session Manager
    participant AI as AI Service
    participant DB as Database

    User->>Bot: メッセージ送信
    Bot->>Router: メッセージルーティング
    Router->>Session: セッション取得
    Session->>DB: 履歴取得（必要時）
    DB-->>Session: 会話履歴
    Session-->>Router: セッション情報
    Router->>AI: プロンプト生成・API呼び出し
    AI-->>Router: AI応答
    Router->>Session: 履歴更新
    Session->>DB: 永続化（非同期）
    Router->>Bot: 応答メッセージ
    Bot->>User: メッセージ送信
```

### 4.2 データ構造

**セッション**:

```python
{
    "session_key": str,
    "session_type": str,
    "messages": List[Message],
    "created_at": datetime,
    "last_activity": datetime
}
```

**メッセージ**:

```python
{
    "role": str,  # "user" | "assistant" | "system"
    "content": str,
    "timestamp": datetime,
    "message_id": int | None
}
```

---

## 5. インターフェース設計

### 5.1 外部インターフェース

| インターフェース | プロトコル     | 用途             |
| ---------------- | -------------- | ---------------- |
| **Discord API**  | WebSocket/HTTP | Discord との通信 |
| **Gemini API**   | HTTP/REST      | AI 応答生成      |
| **SQLite**       | SQL            | データ永続化     |

### 5.2 内部インターフェース

| インターフェース    | 形式          | 用途                   |
| ------------------- | ------------- | ---------------------- |
| **Session Manager** | Python クラス | セッション管理         |
| **AI Service**      | Python クラス | AI 応答生成            |
| **Message Router**  | Python クラス | メッセージルーティング |

---

## 6. エラーハンドリング設計

### 6.1 エラー分類

| エラーレベル | 説明           | 処理                                           |
| ------------ | -------------- | ---------------------------------------------- |
| **ERROR**    | 通常のエラー   | エラーログ出力、ユーザーに通知                 |
| **CRITICAL** | 致命的なエラー | エラーログ出力、管理者に通知、Bot 停止の可能性 |

### 6.2 エラー処理フロー

```mermaid
flowchart TD
    A[エラー発生] --> B{エラータイプ}
    B -->|429 Rate Limit| C[待機してリトライ]
    B -->|400 Bad Request| D[エラーログ出力]
    B -->|500 Server Error| E[リトライ最大3回]
    B -->|503 Service Unavailable| F[フォールバックAPI]
    C --> G[リトライ]
    E --> G
    F --> G
    G --> H{成功?}
    H -->|Yes| I[正常処理継続]
    H -->|No| J[エラーメッセージ送信]
    D --> J
```

---

## 7. セキュリティ設計

### 7.1 認証・認可

- **Discord Bot Token**: 環境変数で管理
- **Gemini API Key**: 環境変数で管理
- **データベース**: ファイルシステムの権限で保護

### 7.2 データ保護

- **プライバシー保護**: ユーザーごとのセッション分離
- **データの最小化**: 必要最小限のデータのみ保存
- **入力のサニタイゼーション**: SQL インジェクション対策

---

## 8. パフォーマンス設計

### 8.1 応答時間目標

| 処理                               | 目標時間   |
| ---------------------------------- | ---------- |
| **メッセージ受信から応答送信まで** | 3 秒以内   |
| **セッション取得**                 | 100ms 以内 |
| **データベース操作**               | 50ms 以内  |

### 8.2 スケーラビリティ

- **同時セッション数**: 最大 100（メモリ内）
- **メッセージ処理**: 非同期処理で並行実行
- **データベース**: SQLite（将来的に PostgreSQL への移行を検討）

---

**作成日**: 2026 年 1 月 14 日
**バージョン**: 1.0
**作成者**: kotonoha-bot 開発チーム
