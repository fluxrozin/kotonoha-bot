# Phase 8 リファクタリング詳細計画書

**作成日**: 2026年1月18日
**バージョン**: 1.1
**対象プロジェクト**: kotonoha-bot v0.8.0
**前提条件**: Phase 7（aiosqlite 移行）完了済み、全テスト通過
**開発体制**: 1人開発（将来的に機能は倍増予定）

---

## 目次

1. [エグゼクティブサマリー](#1-エグゼクティブサマリー)
2. [現状分析](#2-現状分析)
3. [コーディング規約](#3-コーディング規約)
4. [リファクタリング方針](#4-リファクタリング方針)
5. [新フォルダ構造](#5-新フォルダ構造)
6. [詳細実装計画](#6-詳細実装計画)
7. [テストコードリファクタリング](#7-テストコードリファクタリング)
8. [完了基準とチェックリスト](#8-完了基準とチェックリスト)
9. [リスク管理](#9-リスク管理)

---

## 1. エグゼクティブサマリー

### 1.1 目的

機能や仕様を一切変更せず、コードベースの品質向上と技術的負債の解消を実現する。

### 1.2 スコープ

- 本体コード (`src/kotonoha_bot/`): 約3,649行
- テストコード (`tests/`): 約3,193行
- **後方互換性は不要**（完全リファクタリング）

### 1.3 主要な改善項目

| 項目 | 現状 | 目標 |
|------|------|------|
| handlers.py | 832行（単一ファイル） | 内部クラス分割（ファイルは維持） |
| 重複コード | 6箇所以上 | 0箇所 |
| 設定管理 | main.py にログ設定混在 | config.py に統合 |
| エラーメッセージ | 各所に散在 | errors/messages.py に一元管理 |
| テスト構造 | フラット | ソース構造に対応 |
| 型ヒント | 部分的 | 100%カバレッジ |

### 1.4 設計方針

**1人開発に適したシンプルな構造を維持**:

- ディレクトリ深度は最大2階層
- 1ファイル800-1000行は許容（超えたら分割検討）
- 関連コードは近くに配置（ファイル間の行き来を減らす）
- 過度な抽象化を避ける

---

## 2. 現状分析

### 2.1 現在のファイル構造

```
src/kotonoha_bot/           (3,649行)
├── main.py                 (175行) - エントリーポイント + ログ設定
├── config.py               (116行) - 設定管理
├── health.py               (106行) - ヘルスチェック
├── bot/
│   ├── client.py           (45行)
│   └── handlers.py         (832行) ← 最大の問題
├── ai/
│   ├── provider.py         (30行)
│   ├── litellm_provider.py (289行)
│   └── prompts.py          (45行)
├── db/
│   └── sqlite.py           (242行)
├── session/
│   ├── manager.py          (131行)
│   └── models.py           (99行)
├── router/
│   └── message_router.py   (165行) ← 1ファイルのみ
├── eavesdrop/
│   ├── llm_judge.py        (557行)
│   └── conversation_buffer.py (60行)
├── commands/
│   └── chat.py             (128行)
├── rate_limit/
│   ├── monitor.py          (82行)
│   ├── token_bucket.py     (93行)
│   └── request_queue.py    (133行)
├── errors/
│   ├── discord_errors.py   (78行)
│   └── database_errors.py  (65行)
└── utils/
    ├── message_formatter.py (29行)
    └── message_splitter.py  (99行)
```

### 2.2 テスト構造

```
tests/                      (3,193行)
├── conftest.py             (79行)
├── test_basic.py           (62行)
├── unit/                   (17ファイル)
│   ├── test_llm_judge.py   (453行) ← 最大
│   ├── test_thread_handler.py (373行)
│   ├── test_handlers_embed.py (325行)
│   └── ... (14ファイル)
├── integration/            (空)
└── performance/            (空)
```

### 2.3 重複コード詳細

#### 2.3.1 日付フォーマット（3箇所）

**場所**: `handlers.py` 183-192行, 453-460行, 554-560行

```python
# 同一パターンが3回出現
now = datetime.now()
weekday_names = ["月", "火", "水", "木", "金", "土", "日"]
current_date_info = (
    f"\n\n【現在の日付情報】\n"
    f"現在の日時: {now.strftime('%Y年%m月%d日 %H:%M:%S')}\n"
    f"今日の曜日: {weekday_names[now.weekday()]}曜日\n"
    ...
)
```

#### 2.3.2 プロンプト読み込み関数（2箇所）

**場所**: `ai/prompts.py:9-41`, `eavesdrop/llm_judge.py:19-51`

完全に同一の `_load_prompt_from_markdown()` 関数が存在。

#### 2.3.3 エラーメッセージ（10箇所以上）

**場所**: `handlers.py` 249-252行, 305-307行, 392-395行, 402-405行, 410-413行, 418-421行, 511-514行, 623-626行

```python
# 同一メッセージが複数箇所に散在
"すみません。一時的に反応できませんでした。\n"
"少し時間をおいて、もう一度試してみてください。"
```

#### 2.3.4 レスポンス送信パターン（4箇所）

**場所**: `handlers.py` 211-232行, 479-500行, 583-599行, 708-729行

```python
# 同一パターンが4回出現
response_chunks = split_message(response_text)
formatted_chunks = format_split_messages(response_chunks, len(response_chunks))
model_name = self.ai_provider.get_last_used_model()
rate_limit_usage = self.ai_provider.get_rate_limit_usage()
if formatted_chunks:
    embed = create_response_embed(formatted_chunks[0], model_name, rate_limit_usage)
    await channel.send(embed=embed)
    for chunk in formatted_chunks[1:]:
        await channel.send(chunk)
        await asyncio.sleep(0.5)
```

---

## 3. コーディング規約

### 3.1 基本規約

| 項目 | 規約 |
|------|------|
| Python バージョン | 3.14+ |
| 行長制限 | 88文字（ruff デフォルト） |
| インデント | スペース4つ |
| 文字コード | UTF-8 |
| 改行コード | LF |

### 3.2 命名規則

| 対象 | 規則 | 例 |
|------|------|-----|
| モジュール | snake_case | `message_handler.py` |
| クラス | PascalCase | `MessageHandler` |
| 関数/メソッド | snake_case | `handle_message()` |
| 定数 | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT` |
| プライベート | 先頭アンダースコア | `_internal_method()` |
| 型変数 | 大文字1文字または説明的な名前 | `T`, `MessageType` |

### 3.3 型ヒント規約

```python
# ✅ 推奨: Python 3.14+ スタイル
def process(items: list[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    return result

# ✅ 推奨: Union は | を使用
def get_value(key: str) -> str | None:
    return None

# ✅ 推奨: クラス属性にも型ヒント
class Handler:
    sessions: dict[str, Session]
    _cache: list[Message] | None = None

# ❌ 非推奨: typing モジュールの旧型
from typing import List, Dict, Optional  # 使用しない
```

### 3.4 docstring 規約

```python
def generate_response(
    self,
    messages: list[Message],
    system_prompt: str | None = None,
) -> tuple[str, TokenInfo]:
    """AI応答を生成する。

    会話履歴を基に AI からの応答を生成し、トークン使用情報も返す。

    Args:
        messages: 会話履歴のメッセージリスト
        system_prompt: システムプロンプト（省略時はデフォルト使用）

    Returns:
        生成された応答テキストとトークン情報のタプル

    Raises:
        AuthenticationError: API 認証に失敗した場合
        RateLimitError: レート制限に達した場合
    """
```

### 3.5 インポート規約

```python
# 標準ライブラリ（アルファベット順）
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path

# サードパーティ（アルファベット順）
import discord
import litellm
from discord.ext import tasks

# ローカル（相対インポート、アルファベット順）
from ..config import Config
from ..errors.messages import ErrorMessages
from .base import BaseHandler
```

### 3.6 エラーハンドリング規約

```python
# ✅ 推奨: 具体的な例外をキャッチ
try:
    await self.ai_provider.generate_response(messages)
except litellm.AuthenticationError:
    logger.error("Authentication failed")
    raise
except litellm.RateLimitError as e:
    logger.warning(f"Rate limited: {e}")
    await self._handle_rate_limit()

# ❌ 非推奨: 広範な例外キャッチ
try:
    ...
except Exception:  # 具体性がない
    pass  # 握りつぶし禁止
```

### 3.7 ログ規約

```python
# モジュールレベルでロガーを取得
logger = logging.getLogger(__name__)

# ログレベルの使い分け
logger.debug("Internal state: %s", state)      # 開発用詳細情報
logger.info("Session created: %s", session_id) # 通常の操作情報
logger.warning("Retry attempt %d", attempt)     # 注意が必要な状況
logger.error("Failed to connect: %s", error)    # エラー（回復可能）
logger.exception("Unexpected error")            # エラー（スタックトレース付き）
```

### 3.8 非同期規約

```python
# ✅ 推奨: async/await を一貫して使用
async def process_message(self, message: discord.Message) -> None:
    async with message.channel.typing():
        response = await self.generate_response(message)
        await self.send_response(message.channel, response)

# ✅ 推奨: 並行実行可能な場合は gather
results = await asyncio.gather(
    self.save_session(session_key),
    self.update_metrics(session_key),
)

# ❌ 非推奨: 同期的なスリープ
import time
time.sleep(1)  # イベントループをブロック

# ✅ 推奨: 非同期スリープ
await asyncio.sleep(1)
```

---

## 4. リファクタリング方針

### 4.1 設計原則

1. **単一責任の原則 (SRP)**: 各クラス・モジュールは1つの責務のみを持つ
2. **依存性逆転の原則 (DIP)**: 抽象に依存し、具象に依存しない
3. **関心の分離 (SoC)**: 各レイヤーは独立した責務を持つ
4. **DRY 原則**: 重複コードを排除
5. **KISS 原則**: シンプルさを維持

### 4.2 アーキテクチャレイヤー

```
┌─────────────────────────────────────────────────────────┐
│  Presentation Layer (bot/)                              │
│  - Discord イベントの受信・送信                          │
│  - ハンドラー、コマンド                                  │
├─────────────────────────────────────────────────────────┤
│  Application Layer (services/)                          │
│  - ビジネスロジック                                      │
│  - セッション管理、AI サービス                           │
├─────────────────────────────────────────────────────────┤
│  Domain Layer (data/)                                   │
│  - データモデル、リポジトリ                              │
├─────────────────────────────────────────────────────────┤
│  Infrastructure Layer (core/, external/, features/)     │
│  - 設定、ログ、外部サービス、機能モジュール              │
└─────────────────────────────────────────────────────────┘
```

### 4.3 依存性注入パターン

```python
# コンストラクタインジェクション
class MentionHandler(BaseHandler):
    def __init__(
        self,
        session_manager: SessionManager,
        ai_provider: AIProvider,
        response_sender: ResponseSender,
    ):
        self.session_manager = session_manager
        self.ai_provider = ai_provider
        self.response_sender = response_sender
```

---

## 5. 新フォルダ構造

### 5.1 プロジェクト全体構造

```
kotonoha-bot/
├── src/kotonoha_bot/     # ソースコード
├── tests/                # テストコード
├── docs/                 # ドキュメント
├── prompts/              # プロンプトファイル（Markdown）
├── scripts/              # 運用スクリプト（bash）
├── data/                 # ランタイムデータ（.gitignore）
├── logs/                 # ログファイル（.gitignore）
└── backups/              # バックアップ（.gitignore）
```

### 5.2 ソースコード構造（推奨案）

**1人開発に適したフラットな構造**（ディレクトリ深度: 最大2階層）

```txt
src/kotonoha_bot/
├── __init__.py
├── main.py                 # エントリーポイント
├── config.py               # 設定管理（ログ設定も含む）
├── health.py               # ヘルスチェック
│
├── bot/                    # Discord Bot（プレゼンテーション層）
│   ├── __init__.py
│   ├── client.py           # KotonohaBot クラス
│   ├── router.py           # MessageRouter（router/から移動）
│   ├── handlers.py         # 全ハンドラー（内部でクラス分割）
│   └── commands.py         # スラッシュコマンド（commands/chat.py から）
│
├── services/               # ビジネスロジック
│   ├── __init__.py
│   ├── session.py          # SessionManager（session/から移動）
│   ├── ai.py               # LiteLLMProvider（ai/から移動）
│   └── eavesdrop.py        # LLMJudge + ConversationBuffer 統合
│
├── db/                     # データ層（そのまま維持）
│   ├── __init__.py
│   ├── sqlite.py
│   └── models.py           # session/models.py から移動
│
├── errors/                 # エラー処理（そのまま維持 + 追加）
│   ├── __init__.py
│   ├── messages.py         # 【新規】エラーメッセージ一元管理
│   ├── discord.py          # discord_errors.py からリネーム
│   └── database.py         # database_errors.py からリネーム
│
├── rate_limit/             # レート制限（そのまま維持）
│   ├── __init__.py
│   ├── monitor.py
│   ├── token_bucket.py
│   └── request_queue.py
│
└── utils/                  # ユーティリティ
    ├── __init__.py
    ├── message.py          # formatter + splitter 統合
    ├── datetime.py         # 【新規】日付フォーマット
    └── prompts.py          # ai/prompts.py から移動
```

### 5.3 ファイル移動マッピング

| 現在のパス | 新しいパス | 変更内容 |
|-----------|-----------|----------|
| `router/message_router.py` | `bot/router.py` | 移動 |
| `commands/chat.py` | `bot/commands.py` | 移動+リネーム |
| `session/manager.py` | `services/session.py` | 移動 |
| `session/models.py` | `db/models.py` | 移動 |
| `ai/provider.py` | `services/ai.py` | 統合 |
| `ai/litellm_provider.py` | `services/ai.py` | 統合 |
| `ai/prompts.py` | `utils/prompts.py` | 移動 |
| `eavesdrop/llm_judge.py` | `services/eavesdrop.py` | 統合 |
| `eavesdrop/conversation_buffer.py` | `services/eavesdrop.py` | 統合 |
| `errors/discord_errors.py` | `errors/discord.py` | リネーム |
| `errors/database_errors.py` | `errors/database.py` | リネーム |
| `utils/message_formatter.py` | `utils/message.py` | 統合 |
| `utils/message_splitter.py` | `utils/message.py` | 統合 |
| (新規) | `errors/messages.py` | 新規作成 |
| (新規) | `utils/datetime.py` | 新規作成 |

### 5.4 削除対象ディレクトリ

- `router/` → `bot/router.py` に統合
- `ai/` → `services/ai.py` と `utils/prompts.py` に分割
- `session/` → `services/session.py` と `db/models.py` に分割
- `eavesdrop/` → `services/eavesdrop.py` に統合
- `commands/` → `bot/commands.py` に統合

### 5.5 構造比較

| 項目 | 現在 | リファクタリング後 |
|------|------|-------------------|
| ディレクトリ数 | 10 | 6 |
| ファイル数 | 22 | 19 |
| 最大深度 | 2階層 | 2階層 |
| handlers.py | 832行（1ファイル） | 内部クラス分割（1ファイル維持） |

---

## 6. 詳細実装計画

### 6.1 実装ステップ概要

| Step | 内容 | 期間 |
|------|------|------|
| 1 | 重複コード削除（utils/datetime.py, errors/messages.py） | 0.5日 |
| 2 | ファイル統合と移動 | 1日 |
| 3 | handlers.py 内部クラス分割 | 1日 |
| 4 | services/ai.py の戻り値変更 | 0.5日 |
| 5 | インポートパス更新と動作確認 | 1日 |
| 6 | テスト構造の整理 | 1日 |
| 7 | 型ヒント・docstring 追加 | 1日 |
| **合計** | | **6日** |

### 6.2 Step 1: 重複コード削除（0.5日）

#### 6.2.1 `utils/datetime.py` の作成

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

#### 6.2.2 `errors/messages.py` の作成

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

#### 6.2.3 `utils/message.py`（統合）

```python
"""メッセージ処理ユーティリティ"""

# message_formatter.py と message_splitter.py を統合
# 既存のコードをそのまま1ファイルにまとめる
```

### 6.3 Step 2: ファイル統合と移動（1日）

#### 移動対象

```bash
# ディレクトリ作成
mkdir -p src/kotonoha_bot/services

# ファイル移動
mv router/message_router.py bot/router.py
mv commands/chat.py bot/commands.py
mv session/manager.py services/session.py
mv session/models.py db/models.py

# 統合（手動でコード結合）
# ai/provider.py + ai/litellm_provider.py → services/ai.py
# eavesdrop/llm_judge.py + eavesdrop/conversation_buffer.py → services/eavesdrop.py

# プロンプト移動
mv ai/prompts.py utils/prompts.py

# リネーム
mv errors/discord_errors.py errors/discord.py
mv errors/database_errors.py errors/database.py

# 空ディレクトリ削除
rmdir router/ commands/ session/ ai/ eavesdrop/
```

### 6.4 Step 3: handlers.py 内部クラス分割（1日）

**ファイルは分割せず、内部でクラスを整理**:

```python
# bot/handlers.py（~800行を維持、内部でクラス分け）

"""Discord イベントハンドラー"""

import asyncio
import logging
from datetime import datetime, timedelta

import discord
from discord.ext import tasks

from ..config import Config
from ..services.session import SessionManager
from ..services.ai import LiteLLMProvider
from ..services.eavesdrop import LLMJudge, ConversationBuffer
from ..errors.messages import ErrorMessages
from ..utils.datetime import format_datetime_for_prompt

logger = logging.getLogger(__name__)


# ============================================================
# ハンドラークラス
# ============================================================

class MentionHandler:
    """メンション応答ハンドラー（~150行）"""

    def __init__(self, bot, session_manager, ai_provider, response_sender):
        self.bot = bot
        self.session_manager = session_manager
        self.ai_provider = ai_provider
        self.response_sender = response_sender

    async def handle(self, message: discord.Message) -> None:
        """メンション時の処理"""
        ...

    async def _process(self, message: discord.Message) -> None:
        """メンション処理の実装"""
        ...


class ThreadHandler:
    """スレッド型ハンドラー（~250行）"""

    def __init__(self, bot, session_manager, ai_provider, response_sender, router):
        ...

    async def handle(self, message: discord.Message) -> None:
        ...

    async def _create_thread_and_respond(self, message: discord.Message) -> bool:
        ...

    async def _process_thread_message(self, message: discord.Message) -> None:
        ...


class EavesdropHandler:
    """聞き耳型ハンドラー（~100行）"""

    def __init__(self, bot, session_manager, ai_provider, llm_judge, buffer):
        ...

    async def handle(self, message: discord.Message) -> None:
        ...


# ============================================================
# 統合クラス
# ============================================================

class MessageHandler:
    """メッセージハンドラー（統合）"""

    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.session_manager = SessionManager()
        self.ai_provider = LiteLLMProvider()
        # ... 初期化

        # 各ハンドラーのインスタンス化
        self.mention = MentionHandler(...)
        self.thread = ThreadHandler(...)
        self.eavesdrop = EavesdropHandler(...)

    # タスクとイベントハンドラー
    @tasks.loop(hours=1)
    async def cleanup_task(self):
        ...


def setup_handlers(bot):
    """イベントハンドラーをセットアップ"""
    handler = MessageHandler(bot)
    # ... イベント登録
    return handler
```

### 6.5 Step 4: services/ai.py の戻り値変更（0.5日）

```python
# services/ai.py

from typing import TypedDict


class TokenInfo(TypedDict):
    """トークン使用情報"""
    input_tokens: int
    output_tokens: int
    total_tokens: int
    model_used: str
    latency_ms: int


class LiteLLMProvider:
    """LiteLLM 統合プロバイダー"""

    async def generate_response(
        self,
        messages: list,
        system_prompt: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> tuple[str, TokenInfo]:
        """応答を生成し、トークン情報も返す"""
        ...
        return result, token_info
```

**呼び出し箇所の更新**（8箇所）:

```python
# Before
response_text = await self.ai_provider.generate_response(...)

# After
response_text, token_info = await self.ai_provider.generate_response(...)
```

---

## 7. テストコードリファクタリング

### 7.1 テスト構造（ソースと対応）

```txt
tests/
├── conftest.py                  # 共通フィクスチャ
├── fixtures/                    # テスト用フィクスチャ【新規】
│   ├── __init__.py
│   ├── discord.py              # Discord モック
│   └── database.py             # DB フィクスチャ
├── unit/                        # ユニットテスト
│   ├── bot/                    # bot/ に対応
│   │   ├── test_handlers.py    # handlers.py（統合テスト）
│   │   ├── test_router.py
│   │   └── test_commands.py
│   ├── services/               # services/ に対応
│   │   ├── test_session.py
│   │   ├── test_ai.py
│   │   └── test_eavesdrop.py
│   ├── db/                     # db/ に対応
│   │   ├── test_sqlite.py
│   │   └── test_models.py
│   ├── errors/                 # errors/ に対応
│   │   └── test_errors.py
│   ├── rate_limit/             # rate_limit/ に対応
│   │   └── test_rate_limit.py
│   └── utils/                  # utils/ に対応
│       ├── test_message.py
│       └── test_datetime.py
├── integration/                 # 統合テスト
│   └── test_message_flow.py
└── performance/                 # パフォーマンステスト（空）
```

### 7.2 テストファイル移動マッピング

| 現在のパス | 新しいパス |
|-----------|-----------|
| `unit/test_handlers_*.py` (4ファイル) | `unit/bot/test_handlers.py` (統合) |
| `unit/test_thread_handler.py` | `unit/bot/test_handlers.py` (統合) |
| `unit/test_llm_judge.py` | `unit/services/test_eavesdrop.py` |
| `unit/test_conversation_buffer.py` | `unit/services/test_eavesdrop.py` (統合) |
| `unit/test_rate_limit*.py` (2ファイル) | `unit/rate_limit/test_rate_limit.py` (統合) |
| `unit/test_message_router.py` | `unit/bot/test_router.py` |
| `unit/test_commands.py` | `unit/bot/test_commands.py` |
| `unit/test_session.py` | `unit/services/test_session.py` |
| `unit/test_db.py` | `unit/db/test_sqlite.py` |
| `unit/test_errors.py` | `unit/errors/test_errors.py` |
| `unit/test_message_*.py` (2ファイル) | `unit/utils/test_message.py` (統合) |
| `unit/test_main_shutdown.py` | `unit/test_main.py` |

### 7.3 conftest.py（現状維持 + 追加）

```python
# tests/fixtures/discord.py【新規】
"""Discord モック用ユーティリティ"""

from unittest.mock import AsyncMock, MagicMock
import discord


def create_mock_message(
    content: str = "test message",
    author_id: int = 123456789,
    channel_id: int = 987654321,
    author_bot: bool = False,
    mentions: list | None = None,
) -> MagicMock:
    """モックメッセージを作成"""
    message = MagicMock(spec=discord.Message)
    message.content = content
    message.author.id = author_id
    message.author.bot = author_bot
    message.author.display_name = "TestUser"
    message.channel.id = channel_id
    message.channel.typing = MagicMock(return_value=AsyncMock())
    message.mentions = mentions or []
    message.reply = AsyncMock()
    return message
```

### 7.4 pytest プラグイン活用

pyproject.toml に設定済み:

- **pytest-asyncio**: 非同期テスト対応
- **pytest-cov**: カバレッジ計測
- **pytest-xdist**: 並列実行（`-n auto`）
- **pytest-randomly**: ランダム順序実行
- **pytest-timeout**: タイムアウト設定
- **pytest-sugar**: 出力改善
- **pytest-mock**: モック機能拡張

---

## 8. 完了基準とチェックリスト

### 8.1 必須項目

#### コード構造

- [ ] 全ての重複コードが削除されている
- [ ] 新フォルダ構造に移行完了
- [ ] 不要なディレクトリが削除されている

#### コード品質

- [ ] 全ファイルに型ヒントが 100% 適用
- [ ] 全公開 API に docstring が存在
- [ ] `ruff check` が警告なしで通過
- [ ] `ruff format --check` が通過
- [ ] `ty` による型チェックが通過

#### テスト

- [ ] 全テストが通過（既存 137 + 新規）
- [ ] テストカバレッジ 80% 以上
- [ ] テスト構造がソースコード構造と対応

#### 機能

- [ ] 既存の全機能が正常動作（回帰テスト）
- [ ] services/ai.py の戻り値が `tuple[str, TokenInfo]`

### 8.2 品質チェックコマンド

```bash
# 型チェック
uv run ty src/

# リントチェック
uv run ruff check src/ tests/

# フォーマットチェック
uv run ruff format --check src/ tests/

# テスト実行（カバレッジ付き）
uv run pytest --cov=src/kotonoha_bot --cov-report=term-missing --cov-fail-under=80

# 全チェック
uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/ && uv run ty src/ && uv run pytest --cov=src/kotonoha_bot --cov-fail-under=80
```

### 8.3 各 Step の完了基準

| Step | 完了基準 |
|------|----------|
| Step 1 | utils/datetime.py, errors/messages.py 作成、全テスト通過 |
| Step 2 | ファイル移動・統合完了、全テスト通過 |
| Step 3 | handlers.py 内部クラス整理完了、全テスト通過 |
| Step 4 | services/ai.py 戻り値変更、全呼び出し箇所更新、全テスト通過 |
| Step 5 | インポートパス更新完了、全テスト通過 |
| Step 6 | テスト構造リファクタリング完了、全テスト通過 |
| Step 7 | 型ヒント完全化、docstring 追加、カバレッジ 80% 以上 |

---

## 9. リスク管理

### 9.1 リスク一覧

| リスク | 影響度 | 発生確率 | 対策 |
|--------|--------|----------|------|
| 回帰バグ | 高 | 中 | 各 Step で全テスト実行 |
| インポートエラー | 中 | 高 | 段階的移行、`__init__.py` での再エクスポート |
| テストの壊れ | 中 | 中 | テストも同時に移行 |
| 予想外の依存関係 | 中 | 低 | 事前の依存関係分析 |

### 9.2 ロールバック戦略

1. **Git ブランチ戦略**
   - `feature/phase8-refactoring` ブランチで作業
   - 各 Step 完了時にコミット
   - 問題発生時は直前のコミットに戻す

2. **段階的マージ**
   - Step 1-3 完了後に中間レビュー
   - Step 4-7 完了後に中間レビュー
   - 全 Step 完了後に最終レビュー

### 9.3 テスト戦略

```bash
# 各 Step 完了時に実行
uv run pytest -v --tb=short

# 特定のテストのみ実行（高速確認用）
uv run pytest tests/unit/bot/handlers/ -v

# 全テスト + カバレッジ（Step 完了時）
uv run pytest --cov=src/kotonoha_bot --cov-report=html
```

---

## 付録

### A. 依存関係グラフ（リファクタリング後）

```txt
main.py
├── config
├── health
├── bot/client
└── bot/handlers (→ services, errors, utils)

bot/
├── handlers.py (→ services, errors, utils, rate_limit)
├── router.py (→ config)
└── commands.py (→ services)

services/
├── session.py (→ db, config)
├── ai.py (→ config, rate_limit, db/models)
└── eavesdrop.py (→ services/ai, config)

db/
├── sqlite.py (→ config)
└── models.py (→ なし)

errors/
├── messages.py (→ なし)
├── discord.py (→ なし)
└── database.py (→ なし)

rate_limit/
├── monitor.py (→ config)
├── token_bucket.py (→ なし)
└── request_queue.py (→ なし)

utils/
├── message.py (→ なし)
├── datetime.py (→ なし)
└── prompts.py (→ なし)
```

### B. 実装優先度

1. **最優先**: 重複コード削除（日付フォーマット、エラーメッセージ）
2. **高優先**: ファイル移動・統合（ディレクトリ整理）
3. **中優先**: handlers.py 内部整理（クラス分割）
4. **低優先**: 型ヒント完全化、docstring 追加

---

**更新履歴**:

- v1.1 (2026-01-18): 1人開発向けにシンプルな構造に修正
- v1.0 (2026-01-18): 初版作成
