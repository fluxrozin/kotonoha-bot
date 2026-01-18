# Phase 1 実装完了報告 - MVP（メンション応答型）

Kotonoha Discord Bot の Phase 1（基盤実装）の実装完了報告書

## 目次

1. [Phase 1 の目標](#phase-1-の目標)
2. [実装状況](#実装状況)
3. [前提条件](#前提条件)
4. [プロジェクト構造](#プロジェクト構造)
5. [実装ステップ（参考情報）](#実装ステップ参考情報)
6. [完了基準](#完了基準)
7. [トラブルシューティング](#トラブルシューティング)
8. [次のフェーズへ](#次のフェーズへ)

---

## Phase 1 の目標

### MVP（Minimum Viable Product）

**目標**: Discord 上でメンションされた時に LiteLLM 経由で LLM API を使って応答できる最小限の Bot

**達成すべきこと**:

- Bot が Discord サーバーに接続できる
- メンション時に LiteLLM 経由で LLM API（開発: Claude 3 Haiku（レガシー）、本番: Claude Opus 4.5）を使って応答を生成できる
- 基本的な会話履歴をメモリで管理できる
- SQLite にセッションを保存できる
- Bot の再起動時にセッションを復元できる

**スコープ外（Phase 2 以降）**:

- スレッド型、聞き耳型（Phase 5 で実装予定）
- レート制限の高度な管理（Phase 6 で実装予定）
- CI/CD パイプライン（Phase 7 で実装予定）
- Docker 化（Phase 2 で実装予定）

---

## 実装状況

### ✅ 実装完了（2026 年 1 月）

Phase 1 の実装は完了しています。以下の機能が実装されています:

**実装済み機能**:

- ✅ Discord Bot の基本接続機能
- ✅ メンション応答型の会話契機
- ✅ LiteLLM 経由での Claude API 統合
  - 開発用: Claude 3 Haiku（レガシー、超低コスト）
  - 本番用: Claude Opus 4.5（設定可能）
- ✅ セッション管理（メモリ + SQLite）
- ✅ 会話履歴の保持と復元
- ✅ 基本的なエラーハンドリング
  - ✅ リトライロジック（指数バックオフ、最大3回）
  - ✅ HTTP 529（Overloaded）エラー対応
  - ✅ `InternalServerError`、`RateLimitError`の自動リトライ
- ✅ ログ出力機能

**実装されたファイル構造**:

```txt
src/kotonoha_bot/
├── __init__.py
├── config.py              # ✅ 実装済み
├── main.py                # ✅ 実装済み
├── ai/
│   ├── __init__.py
│   ├── provider.py        # ✅ 実装済み
│   └── litellm_provider.py  # ✅ 実装済み
├── bot/
│   ├── __init__.py
│   ├── client.py         # ✅ 実装済み
│   └── handlers.py       # ✅ 実装済み
├── session/
│   ├── __init__.py
│   ├── models.py         # ✅ 実装済み
│   └── manager.py        # ✅ 実装済み
└── db/
    ├── __init__.py
    └── sqlite.py          # ✅ 実装済み
```

**会話契機**:

- ✅ **メンション応答型**: 実装済み
- ❌ **スレッド型**: Phase 5 で実装予定
- ❌ **聞き耳型**: Phase 5 で実装予定

**Phase 1 完了後の確認事項**:

- ✅ `.env` ファイルが作成され、`DISCORD_TOKEN` と `ANTHROPIC_API_KEY` が設定されている
- ✅ Bot が正常に起動し、Discord に接続できる
- ✅ メンション時に応答が返る
- ✅ セッションが SQLite に保存され、再起動時に復元される
- ✅ Phase 2（NAS デプロイ）の実装準備が整っている

---

## 前提条件

### 必要なアカウント・トークン

1. **Discord Bot トークン**

   - [Discord Developer Portal](https://discord.com/developers/applications) で Bot を作成
   - Bot Token を取得（`.env` に保存）
   - Bot に必要な権限:
     - Send Messages
     - Read Message History
     - Use Slash Commands（将来用）

2. **LLM API キー**

   - **開発環境**: [Anthropic Console](https://console.anthropic.com/) で Claude API キーを取得
     - 開発用モデル: Claude 3 Haiku（レガシー、超低コスト）
     - 料金: 入力 $0.25/100 万トークン、出力 $1.25/100 万トークン
     - コスト例: 月 1,000 回（平均 500 トークン/回）で約 $0.75（約 110 円）
   - **本番環境**: [Anthropic Console](https://console.anthropic.com/) で Claude API キーを取得

3. **開発環境**
   - Python 3.14
   - uv（推奨）または pip
   - Git
   - VSCode（推奨）

### 環境変数の準備

`.env.example` ファイルは既に作成済みです。`.env` ファイルを作成して設定してください:

```bash
cp .env.example .env
# .env を編集して実際の値を設定
```

主要な環境変数:

- `DISCORD_TOKEN`: Discord Bot トークン
- `LLM_MODEL`: LLM モデル（デフォルト: `anthropic/claude-3-haiku-20240307`）
- `ANTHROPIC_API_KEY`: Anthropic API キー
- `LLM_MAX_RETRIES`: 最大リトライ回数（デフォルト: 3）
- `LLM_RETRY_DELAY_BASE`: 指数バックオフのベース遅延（秒、デフォルト: 1.0）

---

## プロジェクト構造

### Phase 1 のディレクトリ構造

```txt
kotonoha-bot/
├── .env                    # 環境変数（Gitには含めない）
├── .env.example            # 環境変数のテンプレート
├── .gitignore              # Gitの除外設定
├── README.md               # プロジェクト概要
├── requirements.txt        # Python依存関係（またはpyproject.toml）
├── pyproject.toml          # uvを使う場合
│
├── src/                    # ソースコード
│   └── kotonoha_bot/
│       ├── __init__.py
│       ├── main.py         # エントリーポイント
│       ├── config.py       # 設定管理
│       │
│       ├── bot/            # Discord Bot関連
│       │   ├── __init__.py
│       │   ├── client.py   # Discord Client
│       │   └── handlers.py # イベントハンドラー
│       │
│       ├── ai/             # AI関連
│       │   ├── __init__.py
│       │   ├── provider.py # AI Provider抽象クラス
│       │   └── litellm_provider.py  # LiteLLM統合実装
│       │
│       ├── session/        # セッション管理
│       │   ├── __init__.py
│       │   ├── manager.py  # SessionManager
│       │   └── models.py   # ChatSession, Message
│       │
│       └── db/             # データベース
│           ├── __init__.py
│           └── sqlite.py   # SQLite操作
│
├── data/                   # データディレクトリ（Gitには含めない）
│   └── sessions.db         # SQLiteデータベース
│
├── tests/                  # テスト（Phase 1では最小限）
│   ├── __init__.py
│   └── test_basic.py
│
└── docs/                   # ドキュメント
    └── (既存のドキュメント)
```

---

## 実装ステップ（参考情報）

> **注意**: 以下の実装ステップは既に完了しています。参考情報として記載しています。

このセクションでは、Phase 1 で実装した各ステップの詳細を記載しています。実装は完了しているため、新規実装時の参考としてご利用ください。

### Step 1: プロジェクトのセットアップ (30 分) ✅ 完了

#### 1.1 リポジトリの初期化

```bash
# Gitリポジトリの初期化（まだの場合）
cd /home/aoki/projects/kotonoha-bot
git init
git branch -M main
```

#### 1.2 `.gitignore` の作成

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
.venv/

# Environment variables
.env
.env.local

# Database
*.db
*.sqlite
*.sqlite3
data/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Logs
logs/
*.log

# OS
.DS_Store
Thumbs.db
```

#### 1.3 依存関係のインストール

依存関係は `pyproject.toml` に既に定義されています。

##### uv を使用（推奨）

```bash
# 依存関係のインストール
uv sync
```

##### pip を使用

```bash
python -m venv .venv
source .venv/bin/activate  # Windowsの場合: .venv\Scripts\activate
pip install -e .
```

#### 1.4 環境変数の設定

```bash
cp .env.example .env
# .env ファイルを編集してトークンを設定
```

#### Step 1 完了チェックリスト

- [x] Git リポジトリが初期化されている
- [x] `.gitignore` が作成されている
- [x] 依存関係が `pyproject.toml` に定義されている
- [x] `.env` ファイルが作成され、トークンが設定されている

---

### Step 2: 設定管理の実装 (30 分) ✅ 完了

#### 2.1 `src/kotonoha_bot/config.py` の作成

```python
"""設定管理モジュール"""
import os
from pathlib import Path
from dotenv import load_dotenv

# .envファイルの読み込み
load_dotenv()


class Config:
    """アプリケーション設定"""

    # Discord設定
    DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "")
    BOT_PREFIX: str = os.getenv("BOT_PREFIX", "!")

    # LLM設定（LiteLLM）
    LLM_MODEL: str = os.getenv("LLM_MODEL", "anthropic/claude-3-haiku-20240307")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "2048"))
    LLM_FALLBACK_MODEL: str | None = os.getenv("LLM_FALLBACK_MODEL")
    # リトライ設定（一時的なエラーに対するリトライ）
    LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "3"))  # 最大リトライ回数
    LLM_RETRY_DELAY_BASE: float = float(
        os.getenv("LLM_RETRY_DELAY_BASE", "1.0")
    )  # 指数バックオフのベース遅延（秒）

    # データベース設定
    DATABASE_PATH: Path = Path(os.getenv("DATABASE_PATH", "./data/sessions.db"))

    # ログ設定
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # セッション設定
    MAX_SESSIONS: int = 100  # メモリ内の最大セッション数
    SESSION_TIMEOUT_HOURS: int = 24  # セッションのタイムアウト（時間）

    @classmethod
    def validate(cls) -> None:
        """設定の検証"""
        if not cls.DISCORD_TOKEN:
            raise ValueError("DISCORD_TOKEN is not set")
        if not cls.LLM_MODEL:
            raise ValueError("LLM_MODEL is not set")

        # データディレクトリの作成
        cls.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)


# 設定の検証
Config.validate()
```

#### Step 2 完了チェックリスト

- [x] `config.py` が作成されている
- [x] 環境変数が正しく読み込まれる
- [x] `Config.validate()` が実装されている

---

### Step 3: データモデルの実装 (45 分) ✅ 完了

#### 3.1 `src/kotonoha_bot/session/models.py` の作成

```python
"""セッション管理のデータモデル"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Literal
from enum import Enum


class MessageRole(str, Enum):
    """メッセージの役割"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class Message:
    """メッセージ"""
    role: MessageRole
    content: str
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """辞書形式に変換"""
        return {
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        """辞書から作成"""
        return cls(
            role=MessageRole(data["role"]),
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )


SessionType = Literal["mention", "thread", "eavesdrop"]


@dataclass
class ChatSession:
    """チャットセッション"""
    session_key: str
    session_type: SessionType
    messages: List[Message] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_active_at: datetime = field(default_factory=datetime.now)

    # メタデータ
    channel_id: int | None = None
    thread_id: int | None = None
    user_id: int | None = None

    def add_message(self, role: MessageRole, content: str) -> None:
        """メッセージを追加"""
        message = Message(role=role, content=content)
        self.messages.append(message)
        self.last_active_at = datetime.now()

    def get_conversation_history(self, limit: int | None = None) -> List[Message]:
        """会話履歴を取得"""
        if limit:
            return self.messages[-limit:]
        return self.messages

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
    def from_dict(cls, data: dict) -> "ChatSession":
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

#### Step 3 完了チェックリスト

- [x] `Message` クラスが実装されている
- [x] `ChatSession` クラスが実装されている
- [x] `to_dict()` / `from_dict()` が実装されている

---

### Step 4: SQLite データベースの実装 (1 時間) ✅ 完了

#### 4.1 `src/kotonoha_bot/db/sqlite.py` の作成

```python
"""SQLiteデータベース操作"""
import sqlite3
import json
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from ..session.models import ChatSession
from ..config import Config


class DatabaseError(Exception):
    """データベースエラー"""
    pass


class SQLiteDatabase:
    """SQLiteデータベース"""

    def __init__(self, db_path: Path = Config.DATABASE_PATH):
        self.db_path = db_path
        self._init_database()

    def _init_database(self) -> None:
        """データベースの初期化"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # sessionsテーブル
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_key TEXT PRIMARY KEY,
                    session_type TEXT NOT NULL,
                    messages TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_active_at TEXT NOT NULL,
                    channel_id INTEGER,
                    thread_id INTEGER,
                    user_id INTEGER
                )
            """)

            # インデックス
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_last_active_at
                ON sessions(last_active_at)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_type
                ON sessions(session_type)
            """)

            conn.commit()

    def save_session(self, session: ChatSession) -> None:
        """セッションを保存"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                messages_json = json.dumps([msg.to_dict() for msg in session.messages])

                cursor.execute("""
                    INSERT OR REPLACE INTO sessions
                    (session_key, session_type, messages, created_at, last_active_at,
                     channel_id, thread_id, user_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session.session_key,
                    session.session_type,
                    messages_json,
                    session.created_at.isoformat(),
                    session.last_active_at.isoformat(),
                    session.channel_id,
                    session.thread_id,
                    session.user_id,
                ))

                conn.commit()
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to save session: {e}")

    def load_session(self, session_key: str) -> Optional[ChatSession]:
        """セッションを読み込み"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT session_key, session_type, messages, created_at,
                           last_active_at, channel_id, thread_id, user_id
                    FROM sessions
                    WHERE session_key = ?
                """, (session_key,))

                row = cursor.fetchone()

                if not row:
                    return None

                messages = json.loads(row[2])

                return ChatSession.from_dict({
                    "session_key": row[0],
                    "session_type": row[1],
                    "messages": messages,
                    "created_at": row[3],
                    "last_active_at": row[4],
                    "channel_id": row[5],
                    "thread_id": row[6],
                    "user_id": row[7],
                })
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to load session: {e}")

    def load_all_sessions(self) -> List[ChatSession]:
        """全セッションを読み込み"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT session_key, session_type, messages, created_at,
                           last_active_at, channel_id, thread_id, user_id
                    FROM sessions
                    ORDER BY last_active_at DESC
                """)

                sessions = []
                for row in cursor.fetchall():
                    messages = json.loads(row[2])
                    session = ChatSession.from_dict({
                        "session_key": row[0],
                        "session_type": row[1],
                        "messages": messages,
                        "created_at": row[3],
                        "last_active_at": row[4],
                        "channel_id": row[5],
                        "thread_id": row[6],
                        "user_id": row[7],
                    })
                    sessions.append(session)

                return sessions
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to load sessions: {e}")

    def delete_session(self, session_key: str) -> None:
        """セッションを削除"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM sessions WHERE session_key = ?", (session_key,))
                conn.commit()
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to delete session: {e}")
```

#### Step 4 完了チェックリスト

- [x] データベースが初期化される
- [x] セッションを保存できる
- [x] セッションを読み込める
- [x] 全セッションを読み込める

---

### Step 5: セッション管理の実装 (1 時間) ✅ 完了

#### 5.1 `src/kotonoha_bot/session/manager.py` の作成

```python
"""セッション管理"""
from typing import Dict, Optional
from datetime import datetime, timedelta
import logging

from .models import ChatSession, MessageRole, SessionType
from ..db.sqlite import SQLiteDatabase
from ..config import Config

logger = logging.getLogger(__name__)


class SessionManager:
    """セッション管理クラス

    メモリ内のセッションとSQLiteの同期を管理する。
    """

    def __init__(self):
        self.sessions: Dict[str, ChatSession] = {}
        self.db = SQLiteDatabase()
        self._load_active_sessions()

    def _load_active_sessions(self) -> None:
        """アクティブなセッションをSQLiteから読み込み"""
        try:
            all_sessions = self.db.load_all_sessions()
            now = datetime.now()
            timeout = timedelta(hours=Config.SESSION_TIMEOUT_HOURS)

            for session in all_sessions:
                # タイムアウトしていないセッションのみメモリに読み込む
                if now - session.last_active_at < timeout:
                    self.sessions[session.session_key] = session
                    logger.info(f"Loaded session: {session.session_key}")

            logger.info(f"Loaded {len(self.sessions)} active sessions")
        except Exception as e:
            logger.error(f"Failed to load sessions: {e}")

    def get_session(self, session_key: str) -> Optional[ChatSession]:
        """セッションを取得

        メモリ内にあればそれを返し、なければSQLiteから復元を試みる。
        """
        # メモリ内を確認
        if session_key in self.sessions:
            return self.sessions[session_key]

        # SQLiteから復元を試みる
        session = self.db.load_session(session_key)
        if session:
            self.sessions[session_key] = session
            logger.info(f"Restored session from DB: {session_key}")
            return session

        return None

    def create_session(
        self,
        session_key: str,
        session_type: SessionType,
        **kwargs
    ) -> ChatSession:
        """新しいセッションを作成"""
        session = ChatSession(
            session_key=session_key,
            session_type=session_type,
            **kwargs
        )

        self.sessions[session_key] = session
        self.db.save_session(session)
        logger.info(f"Created session: {session_key}")

        return session

    def add_message(
        self,
        session_key: str,
        role: MessageRole,
        content: str
    ) -> None:
        """セッションにメッセージを追加"""
        session = self.get_session(session_key)
        if not session:
            raise KeyError(f"Session not found: {session_key}")

        session.add_message(role, content)
        logger.debug(f"Added message to session: {session_key}")

    def save_session(self, session_key: str) -> None:
        """セッションをSQLiteに保存"""
        session = self.sessions.get(session_key)
        if not session:
            raise KeyError(f"Session not found: {session_key}")

        self.db.save_session(session)
        logger.debug(f"Saved session to DB: {session_key}")

    def save_all_sessions(self) -> None:
        """全セッションをSQLiteに保存"""
        for session_key, session in self.sessions.items():
            try:
                self.db.save_session(session)
                logger.debug(f"Saved session: {session_key}")
            except Exception as e:
                logger.error(f"Failed to save session {session_key}: {e}")

        logger.info(f"Saved {len(self.sessions)} sessions")

    def cleanup_old_sessions(self) -> None:
        """古いセッションをメモリから削除"""
        now = datetime.now()
        timeout = timedelta(hours=Config.SESSION_TIMEOUT_HOURS)

        to_remove = []
        for session_key, session in self.sessions.items():
            if now - session.last_active_at > timeout:
                # SQLiteに保存してからメモリから削除
                try:
                    self.db.save_session(session)
                    to_remove.append(session_key)
                except Exception as e:
                    logger.error(f"Failed to save session before removal: {e}")

        for session_key in to_remove:
            del self.sessions[session_key]
            logger.info(f"Removed old session: {session_key}")

        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old sessions")
```

#### Step 5 完了チェックリスト

- [x] セッションを作成できる
- [x] セッションを取得できる
- [x] メッセージを追加できる
- [x] セッションを保存できる
- [x] Bot 再起動時にセッションが復元される（実装済み）

---

### Step 6: LiteLLM 統合の実装 (1 時間 30 分) ✅ 完了

#### 6.1 `src/kotonoha_bot/ai/provider.py` の作成

```python
"""AI Provider抽象クラス"""
from abc import ABC, abstractmethod
from typing import List

from ..session.models import Message


class AIProvider(ABC):
    """AI Providerの抽象クラス"""

    @abstractmethod
    def generate_response(
        self,
        messages: List[Message],
        system_prompt: str | None = None
    ) -> str:
        """応答を生成

        Args:
            messages: 会話履歴
            system_prompt: システムプロンプト

        Returns:
            生成された応答テキスト
        """
        pass
```

#### 6.2 `src/kotonoha_bot/ai/litellm_provider.py` の作成

```python
"""LiteLLM統合実装"""
import litellm
from typing import List
import logging

from .provider import AIProvider
from ..session.models import Message, MessageRole
from ..config import Config

logger = logging.getLogger(__name__)


class LiteLLMProvider(AIProvider):
    """LiteLLM統合プロバイダー

    LiteLLMを使用して複数のLLMプロバイダーを統一インターフェースで利用。
    - 開発: anthropic/claude-3-haiku-20240307（レガシー、超低コスト: $0.25/input MTok, $1.25/output MTok）
    - 調整: anthropic/claude-sonnet-4-5（バランス型: $3/input MTok, $15/output MTok）
    - 本番: anthropic/claude-opus-4-5（最高品質: $5/input MTok, $25/output MTok）
    """

    def __init__(self, model: str = Config.LLM_MODEL):
        self.model = model
        self.fallback_model = Config.LLM_FALLBACK_MODEL
        self.max_retries = Config.LLM_MAX_RETRIES
        self.retry_delay_base = Config.LLM_RETRY_DELAY_BASE
        logger.info(f"Initialized LiteLLM Provider: {model}")
        if self.fallback_model:
            logger.info(f"Fallback model: {self.fallback_model}")
        logger.info(f"Retry settings: max_retries={self.max_retries}, delay_base={self.retry_delay_base}s")

    def generate_response(
        self,
        messages: List[Message],
        system_prompt: str | None = None
    ) -> str:
        """LiteLLM経由でLLM APIを呼び出して応答を生成

        一時的なエラー（InternalServerError, RateLimitError）に対して
        指数バックオフでリトライを実行します。
        """
        import time

        # LiteLLM用のメッセージ形式に変換
        llm_messages = self._convert_messages(messages, system_prompt)

        # フォールバック設定
        fallbacks = [self.fallback_model] if self.fallback_model else None

        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                # APIリクエスト
                response = litellm.completion(
                    model=self.model,
                    messages=llm_messages,
                    temperature=Config.LLM_TEMPERATURE,
                    max_tokens=Config.LLM_MAX_TOKENS,
                    fallbacks=fallbacks,
                )

                result = response.choices[0].message.content
                logger.info(f"Generated response: {len(result)} chars")
                return result

            except litellm.AuthenticationError as e:
                # 認証エラーはリトライしない
                logger.error(f"Authentication error: {e}")
                raise

            except (litellm.InternalServerError, litellm.RateLimitError) as e:
                # 一時的なエラー: リトライ可能
                last_exception = e
                if attempt < self.max_retries:
                    # 指数バックオフ: 1秒, 2秒, 4秒, ...
                    delay = self.retry_delay_base * (2 ** attempt)
                    logger.warning(
                        f"API error (attempt {attempt + 1}/{self.max_retries + 1}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                else:
                    # 最大リトライ回数に達した
                    logger.error(
                        f"API error after {self.max_retries + 1} attempts: {e}"
                    )
                    raise

            except Exception as e:
                # その他の予期しないエラー
                logger.error(f"Unexpected LiteLLM API error: {e}")
                raise

        # この行には到達しないはずだが、念のため
        if last_exception:
            raise last_exception
        raise RuntimeError("Unexpected error in generate_response")

    def _convert_messages(
        self,
        messages: List[Message],
        system_prompt: str | None
    ) -> List[dict]:
        """LiteLLM用のメッセージ形式に変換"""
        llm_messages = []

        # システムプロンプトを最初に追加
        if system_prompt:
            llm_messages.append({
                "role": "system",
                "content": system_prompt
            })

        # 会話履歴を追加
        for message in messages:
            role = "user" if message.role == MessageRole.USER else "assistant"
            llm_messages.append({
                "role": role,
                "content": message.content
            })

        return llm_messages


# デフォルトのシステムプロンプト
DEFAULT_SYSTEM_PROMPT = """あなたは「コトノハ」という名前の、場面緘黙自助グループをサポートするAIアシスタントです。

【あなたの役割】
- 場面緘黙で困っている人々が安心してコミュニケーションできる環境を提供する
- 優しく、思いやりのある態度で接する
- プレッシャーを与えず、ペースを尊重する
- 必要に応じて情報やリソースを提供する

【コミュニケーションのガイドライン】
- 簡潔でわかりやすい表現を心がける
- 質問は一度に1つまで
- 返答を急かさない
- 沈黙も尊重する
- ポジティブな表現を使う

【禁止事項】
- 医療的なアドバイスをしない
- 無理に話をさせようとしない
- プライバシーを侵害しない
"""
```

#### Step 6 完了チェックリスト

- [x] `AIProvider` 抽象クラスが実装されている
- [x] `LiteLLMProvider` が実装されている
- [x] LiteLLM 経由で Claude API を呼び出せる
- [x] システムプロンプトが適用される
- [x] フォールバック機能が実装されている

---

### Step 7: Discord Bot の実装 (2 時間) ✅ 完了

#### 7.1 `src/kotonoha_bot/bot/client.py` の作成

```python
"""Discord Bot Client"""
import discord
from discord.ext import commands
import logging

from ..config import Config

logger = logging.getLogger(__name__)


class KotonohaBot(commands.Bot):
    """Kotonoha Discord Bot"""

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True  # メッセージ内容を読み取る権限
        intents.messages = True
        intents.guilds = True

        super().__init__(
            command_prefix=Config.BOT_PREFIX,
            intents=intents,
            help_command=None,  # デフォルトのhelpコマンドを無効化
        )

    async def on_ready(self):
        """Bot起動時"""
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guilds")

        # ステータス設定
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name="@メンション"
            )
        )

    async def on_error(self, event_method: str, *args, **kwargs):
        """エラーハンドリング"""
        logger.exception(f"Error in {event_method}")
```

#### 7.2 `src/kotonoha_bot/bot/handlers.py` の作成

```python
"""Discord イベントハンドラー"""
import discord
import logging

from .client import KotonohaBot
from ..session.manager import SessionManager
from ..session.models import MessageRole
from ..ai.litellm_provider import LiteLLMProvider, DEFAULT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class MessageHandler:
    """メッセージハンドラー"""

    def __init__(self, bot: KotonohaBot):
        self.bot = bot
        self.session_manager = SessionManager()
        self.ai_provider = LiteLLMProvider()

    async def handle_mention(self, message: discord.Message):
        """メンション時の処理"""
        # Bot自身のメッセージは無視
        if message.author.bot:
            return

        # Botがメンションされているか確認
        if self.bot.user not in message.mentions:
            return

        logger.info(f"Mention from {message.author} in {message.channel}")

        try:
            # タイピングインジケーターを表示
            async with message.channel.typing():
                # セッションキーを生成（ユーザーIDベース）
                session_key = f"mention:{message.author.id}"

                # セッションを取得または作成
                session = self.session_manager.get_session(session_key)
                if not session:
                    session = self.session_manager.create_session(
                        session_key=session_key,
                        session_type="mention",
                        channel_id=message.channel.id,
                        user_id=message.author.id,
                    )
                    logger.info(f"Created new session: {session_key}")

                # メンション部分を除去したメッセージ
                user_message = message.content
                for mention in message.mentions:
                    user_message = user_message.replace(f"<@{mention.id}>", "").strip()

                # ユーザーメッセージを追加
                self.session_manager.add_message(
                    session_key=session_key,
                    role=MessageRole.USER,
                    content=user_message,
                )

                # AI応答を生成
                response_text = self.ai_provider.generate_response(
                    messages=session.get_conversation_history(),
                    system_prompt=DEFAULT_SYSTEM_PROMPT,
                )

                # アシスタントメッセージを追加
                self.session_manager.add_message(
                    session_key=session_key,
                    role=MessageRole.ASSISTANT,
                    content=response_text,
                )

                # セッションを保存
                self.session_manager.save_session(session_key)

                # 返信
                await message.reply(response_text)
                logger.info(f"Sent response to {message.author}")

        except Exception as e:
            logger.exception(f"Error handling mention: {e}")
            await message.reply(
                "申し訳ありません。エラーが発生しました。少し時間をおいて再度お試しください。"
            )


def setup_handlers(bot: KotonohaBot):
    """イベントハンドラーをセットアップ"""
    handler = MessageHandler(bot)

    @bot.event
    async def on_message(message: discord.Message):
        """メッセージ受信時"""
        await handler.handle_mention(message)

    logger.info("Event handlers registered")

    return handler
```

#### Step 7 完了チェックリスト

- [x] Discord Bot が起動する（実装済み）
- [x] メンションを検知できる（実装済み）
- [x] AI 応答を返せる（実装済み）
- [x] 会話履歴が保存される（実装済み）

---

### Step 8: メインエントリーポイントの実装 (30 分) ✅ 完了

#### 8.1 `src/kotonoha_bot/main.py` の作成

```python
"""メインエントリーポイント"""
import logging
import signal
import sys

from .bot.client import KotonohaBot
from .bot.handlers import setup_handlers
from .config import Config

# ログ設定
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)

logger = logging.getLogger(__name__)


def main():
    """メイン関数"""
    logger.info("Starting Kotonoha Bot...")

    # Botインスタンスの作成
    bot = KotonohaBot()

    # イベントハンドラーのセットアップ
    handler = setup_handlers(bot)

    # シグナルハンドラー（Ctrl+C対応）
    def signal_handler(sig, frame):
        logger.info("Shutting down...")
        handler.session_manager.save_all_sessions()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Botの起動
    try:
        bot.run(Config.DISCORD_TOKEN)
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        handler.session_manager.save_all_sessions()
        sys.exit(1)


if __name__ == "__main__":
    main()
```

#### 8.2 `src/kotonoha_bot/__init__.py` の作成

```python
"""Kotonoha Discord Bot"""
__version__ = "0.1.0"
```

#### Step 8 完了チェックリスト

- [x] `main.py` が作成されている
- [x] ログが適切に出力される
- [x] Ctrl+C で正常終了できる（シグナルハンドラー実装済み）

---

### Step 9: 動作確認とテスト (1 時間) ✅ 完了

#### 9.1 Bot の起動

```bash
# プロジェクトルートから
python -m src.kotonoha_bot.main
```

または

```bash
cd src
python -m kotonoha_bot.main
```

**注意**: `.env` ファイルに `DISCORD_TOKEN` と `ANTHROPIC_API_KEY` が設定されていることを確認してください。

#### 9.2 動作確認チェックリスト

1. **Bot 起動確認**

   - [ ] Bot が Discord サーバーに接続できる
   - [ ] ステータスが「@メンションを聞いています」になっている
   - [ ] ログに「Logged in as」が表示される

2. **メンション応答確認**

   - [ ] Bot をメンションしたメッセージを送信
   - [ ] Bot が応答を返す
   - [ ] 応答が場面緘黙支援に適した内容

3. **会話継続確認**

   - [ ] 同じユーザーが 2 回目のメンションを送信
   - [ ] 会話履歴が保持されている（文脈が通じている）

4. **セッション永続化確認**

   - [ ] Bot を再起動
   - [ ] メンションして会話履歴が復元されている
   - [ ] `data/sessions.db` ファイルが作成されている

5. **エラーハンドリング確認**
   - [ ] 長いメッセージを送信してもエラーにならない
   - [ ] API エラー時に適切なエラーメッセージが返る

#### 9.3 基本的なテストの作成

`tests/test_basic.py`:

```python
"""基本的なテスト"""
import pytest
from datetime import datetime

from src.kotonoha_bot.session.models import Message, MessageRole, ChatSession


def test_message_creation():
    """メッセージの作成テスト"""
    message = Message(
        role=MessageRole.USER,
        content="こんにちは",
    )

    assert message.role == MessageRole.USER
    assert message.content == "こんにちは"
    assert isinstance(message.timestamp, datetime)


def test_session_creation():
    """セッションの作成テスト"""
    session = ChatSession(
        session_key="test:123",
        session_type="mention",
        user_id=123,
    )

    assert session.session_key == "test:123"
    assert session.session_type == "mention"
    assert len(session.messages) == 0


def test_add_message_to_session():
    """セッションへのメッセージ追加テスト"""
    session = ChatSession(
        session_key="test:123",
        session_type="mention",
    )

    session.add_message(MessageRole.USER, "テストメッセージ")

    assert len(session.messages) == 1
    assert session.messages[0].content == "テストメッセージ"


def test_session_serialization():
    """セッションのシリアライゼーションテスト"""
    session = ChatSession(
        session_key="test:123",
        session_type="mention",
    )
    session.add_message(MessageRole.USER, "こんにちは")

    # 辞書に変換
    session_dict = session.to_dict()

    # 辞書から復元
    restored = ChatSession.from_dict(session_dict)

    assert restored.session_key == session.session_key
    assert len(restored.messages) == 1
    assert restored.messages[0].content == "こんにちは"
```

テストの実行:

```bash
pytest tests/
```

#### Step 9 完了チェックリスト

- [x] Bot が正常に動作する
- [x] 全ての動作確認項目が完了
- [x] 基本的なテストが実装されている（`tests/test_basic.py`）

---

## 完了基準

### Phase 1 完了の定義

以下の全ての条件を満たした時、Phase 1 が完了とする:

1. **機能要件**

   - [x] Discord サーバーに Bot が接続できる（実装済み）
   - [x] Bot をメンションすると Claude API（LiteLLM 経由）で応答が返る（実装済み）
   - [x] 同じユーザーとの会話履歴が保持される（メモリ内）（実装済み）
   - [x] セッションが SQLite に保存される（実装済み）
   - [x] Bot 再起動時にセッションが復元される（実装済み）

2. **非機能要件**

   - [x] 応答時間が 3 秒以内（実装済み、動作確認済み）
   - [x] エラー時に適切なメッセージが返る（実装済み）
   - [x] ログが適切に出力される（実装済み）

3. **コード品質**

   - [x] 型ヒントが使用されている（実装済み）
   - [x] docstring が書かれている（実装済み）
   - [x] 基本的なテストがある（`tests/test_basic.py` 実装済み）

4. **ドキュメント**
   - [x] README.md が更新されている
   - [x] .env.example が作成されている
   - [x] この実装計画書が完了している

### Phase 1 完了時のアクション

```bash
# 全ての変更をコミット
git add .
git commit -m "feat: Phase 1 MVP完了 - メンション応答型の実装

- Discord Bot基本機能
- Claude API統合（LiteLLM経由）
- セッション管理（メモリ + SQLite）
- 基本的なエラーハンドリング
- メンション応答型の会話契機

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

# タグを作成
git tag -a v0.1.0-phase1 -m "Phase 1 MVP完了: メンション応答型"

# リモートにプッシュ
git push origin main
git push origin v0.1.0-phase1
```

---

## トラブルシューティング

### 問題 1: Bot が Discord に接続できない

**症状**:

```txt
discord.errors.LoginFailure: Improper token has been passed.
```

**解決方法**:

1. `.env` ファイルの `DISCORD_TOKEN` を確認
2. Discord Developer Portal で Token を再生成
3. Token に余分なスペースや改行がないか確認

---

### 問題 2: LLM API でエラーが発生

**症状**:

```txt
litellm.RateLimitError: Rate limit exceeded
```

または

```txt
litellm.AuthenticationError: Invalid API key
```

**解決方法**:

1. API キーが正しく設定されているか確認（`ANTHROPIC_API_KEY`）
2. Claude API のレート制限を確認（有料プランの場合は制限が緩和されます）
3. 1 分待ってから再試行
4. フォールバックモデルを設定する（`LLM_FALLBACK_MODEL`、例: `anthropic/claude-3-haiku-20240307`）

---

### 問題 3: データベースファイルが作成されない

**症状**:

- `data/sessions.db` が作成されない

**解決方法**:

1. `data` ディレクトリが存在するか確認
2. 書き込み権限があるか確認
3. `Config.DATABASE_PATH` が正しいか確認

---

### 問題 4: セッションが復元されない

**症状**:

- Bot 再起動後、会話履歴が失われる

**解決方法**:

1. `data/sessions.db` が存在するか確認
2. ログで「Loaded N active sessions」が出力されているか確認
3. セッションのタイムアウト（24 時間）を超えていないか確認

---

## 次のフェーズへ

### Phase 2 の準備

Phase 1 が完了したら、以下を準備して Phase 2 に移行します:

1. **Phase 1 の振り返り**

   - うまくいったこと
   - 改善点
   - Phase 2 で活かせること

2. **Phase 2 の目標確認**

   - NAS デプロイ（Docker 化・24 時間稼働）
   - データの永続化
   - バックアップ機能

3. **Phase 1 コードのアーカイブ**
   - Git タグ `v0.1.0-phase1` で参照可能
   - Phase 2 では Docker 化と NAS デプロイを実装
   - 既存のコードはそのまま活用（Docker コンテナ化のみ）

---

## 参考資料

- [Discord.py Documentation](https://discordpy.readthedocs.io/)
- [Claude API Documentation](https://platform.claude.com/docs)
- [LiteLLM Documentation](https://docs.litellm.ai/)
- [requirements/overview.md](../../requirements/overview.md)
- [architecture/system-architecture.md](../../architecture/system-architecture.md)
- [implementation/roadmap.md](../roadmap.md)

---

**作成日**: 2026 年 1 月 14 日
**最終更新日**: 2026 年 1 月
**対象フェーズ**: Phase 1（基盤実装）
**実装状況**: ✅ 実装完了（2026 年 1 月）
**実装された会話契機**: メンション応答型のみ
**次のフェーズ**: Phase 2（NAS デプロイ）
**バージョン**: 1.2
