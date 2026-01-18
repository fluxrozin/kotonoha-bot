# Phase 8 リファクタリング詳細計画書

**作成日**: 2026年1月18日
**バージョン**: 1.2
**対象プロジェクト**: kotonoha-bot v0.8.0
**前提条件**: Phase 7（aiosqlite 移行）完了済み、全テスト通過
**開発体制**: 1人開発（将来的に機能は倍増予定）

**v1.2 更新内容**: フィードバック反映により以下の項目を必須スコープに格上げ

- handlers.py の物理分割（Step 3）
- Config のインスタンス化（Step 2）
- 例外のラッピング（抽象化の徹底）（Step 4）
- 終了処理（Graceful Shutdown）の明記（Step 8）
- テストデータファクトリーの導入（Step 6）
- aiosqlite テストのコネクション管理の詳細化（Step 6）
- 初期化順序の明確化（Step 3）

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
10. [改善提案（Nice to have）](#10-改善提案nice-to-have)

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
| handlers.py | 832行（単一ファイル） | 物理分割（handlers/パッケージ化） |
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

```text
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

```text
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

**場所**: `handlers.py` 249-252行, 305-307行, 392-395行, 402-405行,
410-413行, 418-421行, 511-514行, 623-626行

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

**重要**: 抽象化の徹底 - Handler層（プレゼンテーション層）は具体的なライブラリの例外を知らないようにする

```python
# ✅ 推奨: services/ai.py で例外をラッピング
# services/ai.py 内部
try:
    response = litellm.completion(...)
except litellm.AuthenticationError:
    raise errors.ai.AIAuthenticationError("API認証に失敗しました")
except litellm.RateLimitError as e:
    raise errors.ai.AIRateLimitError(f"レート制限: {e}")

# ✅ 推奨: Handler層では独自例外のみをキャッチ
# bot/handlers.py
try:
    await self.ai_provider.generate_response(messages)
except errors.ai.AIAuthenticationError:
    logger.error("Authentication failed")
    raise
except errors.ai.AIRateLimitError as e:
    logger.warning(f"Rate limited: {e}")
    await self._handle_rate_limit()

# ❌ 非推奨: Handler層で litellm の例外を直接キャッチ（抽象化の漏れ）
try:
    await self.ai_provider.generate_response(messages)
except litellm.AuthenticationError:  # 具体的なライブラリの例外を知っている
    logger.error("Authentication failed")
    raise
```

**理由**: 将来AIライブラリを変更する際に、Handler層の修正が不要になる。`kotonoha_bot.errors` の例外だけを知っていれば良い。

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

```text
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

```text
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
│   ├── handlers/        # ハンドラーパッケージ（handlers.py から物理分割）
│   │   ├── __init__.py    # MessageHandler（Facade）
│   │   ├── mention.py      # MentionHandler
│   │   ├── thread.py       # ThreadHandler
│   │   └── eavesdrop.py    # EavesdropHandler
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
│   ├── ai.py               # 【新規】AI関連の例外（抽象化の徹底）
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
| ディレクトリ数 | 10 | 7（handlers/パッケージ追加） |
| ファイル数 | 22 | 22（handlers分割により増加） |
| 最大深度 | 2階層 | 2階層 |
| handlers.py | 832行（1ファイル） | 物理分割（handlers/パッケージ、3ファイル） |

---

## 6. 詳細実装計画

### 6.1 実装ステップ概要

| Step | 内容 | 期間 |
|------|------|------|
| 0 | 依存方向の確定（循環参照の防止） | 0.5日 |
| 1 | 重複コード削除（utils/datetime.py, errors/messages.py） | 0.5日 |
| 2 | ファイル統合と移動 + Config インスタンス化 | 1.5日 |
| 3 | handlers.py 物理分割（DIパターン適用） | 1.5日 |
| 4 | services/ai.py の戻り値変更 + 例外ラッピング | 1日 |
| 5 | インポートパス更新と動作確認 | 1日 |
| 6 | テスト構造の整理（aiosqlite フィクスチャ + ファクトリー） | 1.5日 |
| 7 | 型ヒント・docstring 追加 | 1日 |
| 8 | 終了処理（Graceful Shutdown）の実装 | 0.5日 |
| **合計** | | **9日** |

### 6.1 Step 0: 依存方向の確定（0.5日）

**目的**: 各モジュール間の import 関係を図示し、循環参照がないか確認する

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

**完了基準**:

- [ ] 依存関係グラフが生成されている
- [ ] 循環依存が検出されていない
- [ ] 依存関係の方向性ルールが文書化されている
- [ ] 設計レビューが完了している

### 6.2 Step 1: 重複コード削除（0.5日）

**重要**: Step 0 で確定した依存関係の方向性ルールに従って実装する

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

### 6.3 Step 2: ファイル統合と移動 + Config インスタンス化（1.5日）

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

#### 6.3.1 Config のインスタンス化（必須スコープに格上げ）

**理由**: テスト並列実行時の環境変数切り替えが困難、DI（依存性注入）ができない問題を解決

**実装方針**: Pydantic Settings または dataclass によるインスタンス化

##### オプション1: Pydantic Settings（推奨）

```python
# config.py
from pydantic_settings import BaseSettings
from pathlib import Path

class Config(BaseSettings):
    """アプリケーション設定（Pydantic Settings）"""
    discord_token: str
    llm_model: str = "anthropic/claude-sonnet-4-5"
    database_path: Path = Path("./data/sessions.db")
    log_level: str = "INFO"
    # ... その他の設定
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# グローバルインスタンス（後方互換性のため）
_config_instance: Config | None = None

def get_config() -> Config:
    """設定インスタンスを取得（シングルトン）"""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance
```

##### オプション2: dataclass（シンプル）

```python
# config.py
from dataclasses import dataclass
from pathlib import Path
import os

@dataclass
class Config:
    """アプリケーション設定（インスタンス化可能）"""
    discord_token: str
    llm_model: str
    database_path: Path
    log_level: str
    # ... その他の設定
    
    @classmethod
    def from_env(cls) -> "Config":
        """環境変数から設定を読み込む"""
        return cls(
            discord_token=os.getenv("DISCORD_TOKEN", ""),
            llm_model=os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4-5"),
            database_path=Path(os.getenv("DATABASE_PATH", "./data/sessions.db")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            # ... その他の設定
        )
```

**main.py での使用**:

```python
# main.py
from kotonoha_bot.config import get_config

async def async_main():
    config = get_config()  # または Config.from_env()
    Config.validate(config)  # 検証メソッドもインスタンスメソッドに変更
    
    db = SQLiteDatabase(config.database_path)
    # ...
```

**テストでの使用**:

```python
# tests/conftest.py
@pytest.fixture
def test_config(tmp_path):
    """テスト用設定"""
    return Config(
        discord_token="test_token",
        llm_model="test_model",
        database_path=tmp_path / "test.db",
        log_level="DEBUG",
    )
```

### 6.4 Step 3: handlers.py 物理分割（必須スコープに格上げ）（1.5日）

**方針**: **物理ファイルに分割**。内部クラス分割ではなく、ファイル単位で責務を分離する。

**理由**:

- 認知負荷の低減: 1ファイル800行の中に3つの異なるクラスが混在すると、スクロールの移動が増え、認知負荷が下がりにくい
- Git管理: ファイル単位で責務が分かれている方が、将来的に変更履歴を追う際にノイズが減る
- 移行コスト: 内部クラスに分割する手間と、物理ファイルに分ける手間に大差はない（import文の調整のみ）

**重要**: 依存性注入パターンに従い、すべての依存を引数として受け取る

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

from .mention import MentionHandler
from .thread import ThreadHandler
from .eavesdrop import EavesdropHandler

class MessageHandler:
    """メッセージハンドラー（統合Facade）"""

    def __init__(
        self,
        bot: discord.Client,
        session_manager: SessionManager,
        ai_provider: LiteLLMProvider,
        router: MessageRouter | None = None,
        llm_judge: LLMJudge | None = None,
        buffer: ConversationBuffer | None = None,
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
    session_manager: SessionManager,
    ai_provider: LiteLLMProvider,
    router: MessageRouter | None = None,
    llm_judge: LLMJudge | None = None,
    buffer: ConversationBuffer | None = None,
) -> MessageHandler:
    """イベントハンドラーをセットアップ（依存関係を注入）"""
    handler = MessageHandler(
        bot, session_manager, ai_provider, router, llm_judge, buffer
    )
    # ... イベント登録
    return handler

__all__ = ["MessageHandler", "setup_handlers"]
```

```python
# bot/handlers/mention.py
"""メンション応答ハンドラー"""

import logging
import discord
from ..services.session import SessionManager
from ..services.ai import LiteLLMProvider

logger = logging.getLogger(__name__)


class MentionHandler:
    """メンション応答ハンドラー（~150行）"""

    def __init__(
        self,
        bot: discord.Client,
        session_manager: SessionManager,
        ai_provider: LiteLLMProvider,
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
   - `SQLiteDatabase` は他のサービスが依存するため、最初に初期化
   - `await db.initialize()` でテーブル作成と接続確立

2. **サービスの初期化**（依存関係順）
   - `SessionManager` は `SQLiteDatabase` に依存 →
     `await session_manager.initialize()` でDB接続とセッション読み込み
   - `LiteLLMProvider` は独立（初期化不要、または同期的な初期化のみ）
   - `LLMJudge` は `LiteLLMProvider` に依存（初期化不要、コンストラクタで依存注入）

3. **ハンドラーのセットアップ**（初期化済みサービスを使用）
   - `setup_handlers` は初期化済みのサービスインスタンスを受け取る
   - ハンドラー内で `session_manager.initialize()` を呼ぶ必要はない

**実装例**:

```python
# main.py
async def main():
    # 1. データベースの初期化（最優先）
    db = SQLiteDatabase()
    await db.initialize()  # テーブル作成と接続確立
    
    # 2. サービスの初期化（依存関係順）
    session_manager = SessionManager(db)  # DIパターン
    await session_manager.initialize()  # DB接続とセッション読み込み
    # 注: この時点で session_manager は使用可能な状態
    
    ai_provider = LiteLLMProvider()  # 初期化不要（必要に応じて同期的な初期化）
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
    ai_provider: LiteLLMProvider,
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
    if not hasattr(session_manager, '_initialized') or not session_manager._initialized:
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

**完了基準**:

- [ ] main.py で `await session_manager.initialize()` が呼ばれている
- [ ] 初期化順序が明確に文書化されている
- [ ] setup_handlers の docstring に初期化済みであることを前提とすることが記載されている
- [ ] on_ready イベント内での初期化処理が削除されている（既に初期化済みであるため）

**依存関係の組み立て（main.py または bot/client.py）**:

```python
# main.py または bot/client.py

from kotonoha_bot.db.sqlite import SQLiteDatabase
from kotonoha_bot.services.session import SessionManager
from kotonoha_bot.services.ai import LiteLLMProvider
from kotonoha_bot.services.eavesdrop import LLMJudge, ConversationBuffer
from kotonoha_bot.bot.router import MessageRouter
from kotonoha_bot.bot.handlers import setup_handlers

async def main():
    # 1. データベースの初期化
    db = SQLiteDatabase()
    await db.initialize()
    
    # 2. サービスの初期化（依存関係を組み立て）
    session_manager = SessionManager(db)  # ← DIパターン適用
    await session_manager.initialize()  # ← 明示的に初期化（重要）
    ai_provider = LiteLLMProvider()
    router = MessageRouter()
    llm_judge = LLMJudge(ai_provider)
    buffer = ConversationBuffer()
    
    # 3. Bot の初期化
    bot = KotonohaBot()
    
    # 4. ハンドラーのセットアップ（依存関係を注入）
    # 注: この時点で session_manager は既に初期化済みであることを保証
    handler = setup_handlers(
        bot=bot,
        session_manager=session_manager,
        ai_provider=ai_provider,
        router=router,
        llm_judge=llm_judge,
        buffer=buffer,
    )
    
    # 5. Bot の起動
    await bot.start(Config.DISCORD_TOKEN)
```

### 6.5 Step 4: services/ai.py の戻り値変更 + 例外ラッピング（1日）

#### 6.5.1 戻り値の変更

```python
# services/ai.py

from dataclasses import dataclass


@dataclass(frozen=True)
class TokenInfo:
    """トークン使用情報
    
    Attributes:
        input_tokens: 入力トークン数
        output_tokens: 出力トークン数
        total_tokens: 合計トークン数
        model_used: 使用したモデル名
        latency_ms: レイテンシ（ミリ秒）
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
        # TokenInfo インスタンスを作成
        token_info = TokenInfo(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            model_used=model_name,
            latency_ms=latency_ms,
        )
        return result, token_info
```

#### 6.5.2 例外のラッピング（抽象化の徹底）

**理由**: Handler層が litellm という具体的なライブラリの例外を知っている必要があるのは抽象化の漏れ（Leaky Abstraction）。将来AIライブラリを変える際にHandlerも修正が必要になる。

**実装**:

```python
# errors/ai.py（新規作成）
"""AI関連の例外"""

class AIError(Exception):
    """AI関連の基底例外"""
    pass

class AIAuthenticationError(AIError):
    """AI認証エラー"""
    pass

class AIRateLimitError(AIError):
    """AIレート制限エラー"""
    pass

class AIServiceError(AIError):
    """AIサービスエラー（一時的なエラー）"""
    pass
```

```python
# services/ai.py
import litellm
from ..errors.ai import (
    AIAuthenticationError,
    AIRateLimitError,
    AIServiceError,
)

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
        try:
            response = litellm.completion(...)
            # ...
        except litellm.AuthenticationError as e:
            # litellm の例外を独自例外に変換
            logger.error(f"AI authentication error: {e}")
            raise AIAuthenticationError("API認証に失敗しました") from e
        except litellm.RateLimitError as e:
            logger.warning(f"AI rate limit error: {e}")
            raise AIRateLimitError(f"レート制限に達しました: {e}") from e
        except (
            litellm.InternalServerError,
            litellm.ServiceUnavailableError
        ) as e:
            logger.warning(f"AI service error: {e}")
            raise AIServiceError(f"AIサービスで一時的なエラーが発生しました: {e}") from e
        # その他の litellm 例外も適切にラッピング
```

```python
# bot/handlers/mention.py（使用例）
from ..errors.ai import AIAuthenticationError, AIRateLimitError, AIServiceError

try:
    response_text, token_info = await self.ai_provider.generate_response(messages)
except AIAuthenticationError:
    # Handler層は kotonoha_bot.errors の例外だけを知っていれば良い
    logger.error("Authentication failed")
    await self._send_error_message(message.channel, ErrorMessages.AUTH_ERROR)
except AIRateLimitError as e:
    logger.warning(f"Rate limited: {e}")
    await self._handle_rate_limit()
except AIServiceError as e:
    logger.warning(f"Service error: {e}")
    await self._send_error_message(message.channel, ErrorMessages.SERVICE_ERROR)
```

**呼び出し箇所の更新**（8箇所）:

```python
# Before
response_text = await self.ai_provider.generate_response(...)

# After
response_text, token_info = await self.ai_provider.generate_response(...)
```

### 6.6 Step 5: `__init__.py` の整備とインポートパス更新（1日）

**実施内容**:

1. **各ディレクトリの `__init__.py` の作成**:

**bot/**init**.py**:

```python
"""Discord Bot プレゼンテーション層"""
from .client import KotonohaBot
from .handlers import MessageHandler, setup_handlers
from .router import MessageRouter
from .commands import setup_commands

__all__ = [
    "KotonohaBot",
    "MessageHandler",
    "setup_handlers",
    "MessageRouter",
    "setup_commands",
]
```

**services/**init**.py**:

```python
"""ビジネスロジック層"""
from .session import SessionManager
from .ai import LiteLLMProvider
from .eavesdrop import LLMJudge, ConversationBuffer

__all__ = [
    "SessionManager",
    "LiteLLMProvider",
    "LLMJudge",
    "ConversationBuffer",
]
```

**errors/**init**.py**:

```python
"""エラー処理"""
from .messages import ErrorMessages, CommandMessages
from .discord import DiscordError
from .database import DatabaseError

__all__ = [
    "ErrorMessages",
    "CommandMessages",
    "DiscordError",
    "DatabaseError",
]
```

**utils/**init**.py**:

```python
"""ユーティリティ"""
from .message import split_message, format_split_messages
from .datetime import format_datetime_for_prompt
from .prompts import load_prompt_from_markdown

__all__ = [
    "split_message",
    "format_split_messages",
    "format_datetime_for_prompt",
    "load_prompt_from_markdown",
]
```

1. **すべてのインポートパスの更新**:
   - ファイル移動に伴うインポートパスの一括置換
   - `__init__.py` での再エクスポートの確認

2. **インポートパス移行戦略**:
   - すべてのインポートを一度に新パスに更新
   - 旧パスのサポートは行わない（完全リファクタリングのため）
   - ファイル移動と同時にインポートパスを更新

3. **循環インポートの回避**:
   - 型ヒントには `TYPE_CHECKING` を使用
   - 遅延インポート（関数内インポート）を活用
   - 依存関係の方向を一方向に保つ

4. **動作確認**:
   - Bot の起動確認
   - 各機能の動作確認
   - エラーログの確認

5. **循環インポートの検証**:

   ```bash
   # 循環依存を検出
   uv run pydeps src/kotonoha_bot/ --show-cycles
   ```

**完了基準**:

- [ ] すべての `__init__.py` が作成されている
- [ ] `__all__` が適切に定義されている
- [ ] すべてのインポートパスが更新されている
- [ ] Bot が正常に起動する
- [ ] 循環依存が検出されていない
- [ ] 全テストが通過する

### 6.7 Step 6: テスト構造の整理 + テストデータファクトリー（1.5日）

**実施内容**:

1. **テストファイルの移動と統合**:
   - ソースコード構造に対応したテスト構造への移行
   - テストファイルの統合（重複テストの削除）

2. **aiosqlite 用フィクスチャの追加**:

```python
# tests/conftest.py に追加

import pytest
import aiosqlite
from pathlib import Path
from kotonoha_bot.db.sqlite import SQLiteDatabase

@pytest.fixture
async def temp_db_path(tmp_path):
    """一時的なデータベースパス"""
    db_path = tmp_path / "test.db"
    yield db_path
    # テスト後にファイルを削除（オプション）

@pytest.fixture
async def memory_db():
    """メモリ内データベースのフィクスチャ（高速テスト用）"""
    database = SQLiteDatabase(db_path=Path(":memory:"))
    await database.initialize()
    yield database
    # メモリDBは自動的にクリーンアップされる
    await database.close()  # 明示的にクローズ

@pytest.fixture
async def db(temp_db_path):
    """SQLite データベースのフィクスチャ（各テストで独立）"""
    database = SQLiteDatabase(db_path=temp_db_path)
    await database.initialize()
    yield database
    # テスト後にテーブルをクリア（データ汚染防止）
    async with aiosqlite.connect(str(temp_db_path)) as conn:
        await conn.execute("DELETE FROM sessions")
        await conn.commit()
    await database.close()  # 明示的にクローズ

@pytest.fixture
async def session_manager(memory_db):
    """SessionManager のフィクスチャ（メモリDB使用）"""
    from kotonoha_bot.services.session import SessionManager
    manager = SessionManager(memory_db)  # DIパターン
    manager.sessions = {}  # セッション辞書をクリア
    await manager.initialize()
    yield manager
```

**重要ルール**:

- アプリケーションコード（SQLiteDatabase クラスなど）は、外部から
  aiosqlite.Connection オブジェクトを受け取れるように設計するか、
  あるいは path を受け取るなら確実に close する責務を持つ
- テスト: フィクスチャで yield する前にテーブル作成（migrate）を済ませた
  状態のDBオブジェクトを渡すと、各テストで await db.initialize() を呼ぶ
  重複を排除できる

1. **テストデータファクトリーの導入（必須スコープに格上げ）**:

**理由**: テストコードのリファクタリングを行う際、最も時間がかかるのは「テストデータのセットアップ」。特に ChatSession のような複雑なオブジェクトを毎回手作りするのはバグの温床。

```python
# tests/fixtures/factories.py（新規作成）
"""テストデータファクトリー"""

from datetime import datetime
from kotonoha_bot.db.models import ChatSession, MessageRole

class SessionFactory:
    """ChatSession のテストデータを生成"""
    
    @staticmethod
    def create(
        session_key: str = "test_session_123",
        session_type: str = "mention",
        channel_id: int = 123456789,
        user_id: int = 987654321,
        messages: list | None = None,
    ) -> ChatSession:
        """ChatSession インスタンスを生成"""
        if messages is None:
            messages = [
                {
                    "role": MessageRole.USER,
                    "content": "テストメッセージ",
                    "timestamp": datetime.now().isoformat(),
                }
            ]
        
        return ChatSession(
            session_key=session_key,
            session_type=session_type,
            messages=messages,
            created_at=datetime.now(),
            last_active_at=datetime.now(),
            channel_id=channel_id,
            user_id=user_id,
        )
    
    @staticmethod
    def create_with_history(
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
        
        return SessionFactory.create(
            session_key=session_key,
            messages=messages,
        )

# 使用例
def test_session_loading():
    session = SessionFactory.create_with_history("test_123", message_count=10)
    # テスト実行...
```

1. **テストごとのDB状態リセット**:
   - 各テストで独立したDBインスタンスを使用
   - テスト後にDB状態をリセット（データ汚染防止）

**完了基準**:

- [ ] テスト構造がソースコード構造に対応している
- [ ] aiosqlite 用のフィクスチャが追加されている
- [ ] テストごとのDB状態リセットが確立されている
- [ ] 全テストが通過する
- [ ] テスト間でデータ汚染が発生していない

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

**注**: aiosqlite 用のフィクスチャは「6.7 Step 6」で追加されます。

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

### 7.4 テストデータファクトリー（推奨）

#### 詳細は「10.3 テストデータのファクトリー化」を参照

DBモデル（Session 等）のテストデータ生成を容易にするため、`tests/fixtures/factories.py` を作成することを推奨します。

### 6.8 Step 7: 型ヒント・docstring 追加（1日）

**実施内容**:

1. **型ヒントの完全化**:
   - すべての関数・メソッドの引数と戻り値に型ヒントを追加
   - クラス属性に型ヒントを追加
   - `TYPE_CHECKING` を使用した循環インポート回避

2. **docstring の追加**:
   - すべての公開クラス・関数・メソッドに docstring を追加
   - Google スタイルまたは NumPy スタイルに統一

3. **型チェックの実行**:

   ```bash
   # 型エラーの検出
   uv run ty check src/ --show-error-codes
   
   # 型エラーの修正後、再チェック
   uv run ty check src/
   ```

**完了基準**:

- [ ] 全ファイルに型ヒントが 100% 適用されている
- [ ] 全公開 API に docstring が存在する
- [ ] `ty check` が警告なしで通過する
- [ ] カバレッジが 80% 以上を維持している

### 6.9 Step 8: 終了処理（Graceful Shutdown）の実装（0.5日）

**目的**: リソース（DB接続、aiohttpセッションなど）を確実にクローズする

**実装**:

```python
# main.py
async def shutdown_gracefully(
    bot: KotonohaBot,
    handler: MessageHandler,
    health_server: HealthCheckServer,
    db: SQLiteDatabase,  # DBインスタンスを追加
):
    """適切なシャットダウン処理"""
    logger.info("Starting graceful shutdown...")

    try:
        # ヘルスチェックサーバーを停止
        health_server.stop()

        # セッションを保存
        await handler.session_manager.save_all_sessions()

        # Botを切断
        if not bot.is_closed():
            await bot.close()

        # DB接続をクローズ（重要）
        if db:
            await db.close()
            logger.info("Database connection closed")

        logger.info("Graceful shutdown completed")
    except Exception as e:
        logger.exception(f"Error during shutdown: {e}")
    finally:
        # ログハンドラーを閉じる
        for handler_instance in logging.root.handlers[:]:
            handler_instance.close()
            logging.root.removeHandler(handler_instance)
```

**DIコンテナ的な役割を果たす main.py で、生成した db インスタンスの close() を呼ぶ責任を持たせる**:

```python
# main.py
async def async_main():
    config = get_config()
    db = SQLiteDatabase(config.database_path)
    
    try:
        await db.initialize()
        # ... Bot起動処理
    finally:
        # 確実にクローズ
        await db.close()
```

**完了基準**:

- [ ] shutdown_gracefully に DB接続のクローズ処理が追加されている
- [ ] main.py で生成したすべてのリソース（DB、aiohttpセッションなど）が確実にクローズされる
- [ ] テストでリソースリークが発生していない

### 7.5 pytest プラグイン活用

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
uv run ruff check src/ tests/ && \
uv run ruff format --check src/ tests/ && \
uv run ty src/ && \
uv run pytest --cov=src/kotonoha_bot --cov-fail-under=80
```

### 8.3 各 Step の完了基準

| Step | 完了基準 |
|------|----------|
| Step 0 | 依存関係グラフ生成、循環依存なし、依存方向性ルール文書化 |
| Step 1 | utils/datetime.py, errors/messages.py 作成、全テスト通過 |
| Step 2 | ファイル移動・統合完了、Config インスタンス化完了、全テスト通過 |
| Step 3 | handlers.py 物理分割完了、DIパターン適用、初期化順序の明確化、全テスト通過 |
| Step 4 | services/ai.py 戻り値変更、例外ラッピング完了、全呼び出し箇所更新、全テスト通過 |
| Step 5 | `__init__.py` 整備完了、インポートパス更新完了、循環依存なし、全テスト通過 |
| Step 6 | テスト構造リファクタリング完了、aiosqlite フィクスチャ追加、テストデータファクトリー作成、全テスト通過 |
| Step 7 | 型ヒント完全化、docstring 追加、カバレッジ 80% 以上 |
| Step 8 | 終了処理（Graceful Shutdown）実装完了、リソースリークなし |

---

## 9. リスク管理

### 9.1 リスク一覧

| リスク | 影響度 | 発生確率 | 対策 |
|--------|--------|----------|------|
| 回帰バグ | 高 | 中 | 各 Step で全テスト実行 |
| インポートエラー | 中 | 高 | 段階的移行、`__init__.py` での再エクスポート |
| テストの壊れ | 中 | 中 | テストも同時に移行 |
| 予想外の依存関係 | 中 | 低 | 事前の依存関係分析 |
| 非同期DBテストの複雑性 | 中 | 中 | テストごとのDB状態リセット、適切なフィクスチャ設計 |
| 循環参照（循環インポート） | 高 | 中 | 依存の方向性を厳格に定義、TYPE_CHECKING の活用 |
| 初期化順序の不備 | 高 | 中 | 初期化順序の明確化、main.py での明示的な初期化、setup_handlers での前提条件の文書化 |

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

### 9.4 非同期DBテストの複雑性

**問題**: `aiosqlite` を使用しているため、テスト実行時も `pytest-asyncio` ループ内で
正しく DB コネクション（または `:memory:` DB）をセットアップ・ティアダウンする
必要があります。

**追加チェック項目**:

- [ ] テストごとのDB状態のリセット（他テストへのデータ汚染防止）が確立されているか
- [ ] `:memory:` DB を使用したテストフィクスチャが適切に設計されているか
- [ ] 非同期フィクスチャが正しく `async def` で定義されているか
- [ ] テスト間でDB接続が適切にクリーンアップされているか

**推奨実装**:

```python
# tests/conftest.py

import pytest
import aiosqlite
from pathlib import Path
from kotonoha_bot.db.sqlite import SQLiteDatabase

@pytest.fixture
async def temp_db_path(tmp_path):
    """一時的なデータベースパス"""
    db_path = tmp_path / "test.db"
    yield db_path
    # テスト後にファイルを削除（オプション）

@pytest.fixture
async def db(temp_db_path):
    """SQLite データベースのフィクスチャ（各テストで独立）"""
    database = SQLiteDatabase(db_path=temp_db_path)
    await database.initialize()
    yield database
    # テスト後にテーブルをクリア（データ汚染防止）
    async with aiosqlite.connect(str(temp_db_path)) as conn:
        await conn.execute("DELETE FROM sessions")
        await conn.commit()
    await database.close()  # 明示的にクローズ

@pytest.fixture
async def memory_db():
    """メモリ内データベースのフィクスチャ（高速テスト用）"""
    database = SQLiteDatabase(db_path=Path(":memory:"))
    await database.initialize()
    yield database
    # メモリDBも明示的にクローズ
    await database.close()
```

**追加ルール**:

- アプリケーションコード（SQLiteDatabase クラスなど）は、外部から
  aiosqlite.Connection オブジェクトを受け取れるように設計するか、
  あるいは path を受け取るなら確実に close する責務を持つ
- テスト: フィクスチャで yield する前にテーブル作成（migrate）を済ませた
  状態のDBオブジェクトを渡すと、各テストで await db.initialize() を呼ぶ
  重複を排除できる

**テスト実行時の注意点**:

- `pytest-asyncio` の `asyncio_mode = "auto"` が `pyproject.toml` に設定されていることを確認
- 各テストで独立したDBインスタンスを使用（データ汚染防止）
- テスト後にDB状態をリセット（DELETE または `:memory:` を使用）

### 9.5 循環参照（循環インポート）のリスク

**懸念**:

- `services/session.py` が `services/ai.py` を呼ぶ（要約などで）
- 逆に `services/ai.py` が `services/session.py` を呼ぶ（履歴取得などで）

これが発生すると import エラーになります。

**対策**: 「6.2 Step 1」の段階で、依存の方向性を厳格に定義

**依存関係の方向性ルール**:

1. **`services/ai.py` は純粋な関数として設計**
   - セッション管理や履歴取得は行わない
   - 会話履歴（メッセージリスト）を引数として受け取る
   - セッション管理は呼び出し元（handlers）が行う

2. **`services/session.py` はデータ管理のみ**
   - AI機能への直接依存は持たない
   - セッションの保存・読み込み・削除のみを担当

3. **循環参照を避けるためのパターン**:

```python
# ❌ 悪い例: 循環参照のリスク
# services/session.py
from ..services.ai import LiteLLMProvider  # 循環参照の可能性

class SessionManager:
    def __init__(self):
        self.ai_provider = LiteLLMProvider()  # 直接依存

# ✅ 良い例: 依存性注入
# services/session.py
class SessionManager:
    def __init__(self, db: SQLiteDatabase):
        self.db = db  # データ層のみに依存

# bot/handlers.py
class MessageHandler:
    def __init__(
        self,
        session_manager: SessionManager,
        ai_provider: LiteLLMProvider,  # 依存を注入
    ):
        self.session_manager = session_manager
        self.ai_provider = ai_provider
    
    async def handle_mention(self, message):
        # セッション管理とAI呼び出しを分離
        session = await self.session_manager.get_session(session_key)
        messages = session.get_conversation_history()
        response = await self.ai_provider.generate_response(messages)
        await self.session_manager.add_message(session_key, response)
```

1. **`TYPE_CHECKING` の活用**:

```python
# services/session.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..services.ai import LiteLLMProvider  # 型チェック時のみインポート

class SessionManager:
    def process_with_ai(self, ai_provider: "LiteLLMProvider"):  # 文字列型ヒント
        # 実装時は引数として受け取る（循環参照回避）
        pass
```

**チェックリスト**:

- [ ] `services/ai.py` が `services/session.py` をインポートしていない
- [ ] `services/session.py` が `services/ai.py` をインポートしていない
- [ ] 必要な場合は `TYPE_CHECKING` を使用
- [ ] 依存関係は handlers 層で組み立てる（DI パターン）
- [ ] 循環インポート検出ツールで確認（`pydeps --show-cycles`）

### 9.6 初期化順序のリスク

**問題**: DIパターンを適用する際、各サービスの初期化順序が不明確だと、ハンドラーが未初期化のサービスを使用してしまう可能性がある。

**対策**:

1. **初期化順序の明確化**:
   - データベース → セッションマネージャー → その他のサービス → ハンドラー
   - Step 3 に「初期化順序の明確化」セクションを追加

2. **main.py での明示的な初期化**:

   ```python
   db = SQLiteDatabase()
   await db.initialize()
   session_manager = SessionManager(db)
   await session_manager.initialize()  # 明示的に初期化
   ```

3. **setup_handlers での前提条件の文書化**:
   - docstring に「初期化済みであることを前提とする」と明記
   - オプションで初期化済みチェックを追加（デバッグ用）

4. **on_ready イベントでの初期化を削除**:
   - 現状のコードでは `on_ready` イベント内で `await handler.session_manager.initialize()` を呼んでいるが、DIパターン適用後は不要
   - main.py で既に初期化済みであるため

**チェックリスト**:

- [ ] main.py で `await session_manager.initialize()` が呼ばれている
- [ ] 初期化順序が明確に文書化されている
- [ ] setup_handlers の docstring に初期化済みであることを前提とすることが記載されている
- [ ] on_ready イベント内での初期化処理が削除されている

---

## 10. 改善提案（Nice to have）

以下の提案は必須ではありませんが、将来の拡張性や保守性を考慮すると検討に値します。

**注**: 以下の項目は Phase 8 の必須スコープに含まれています:

- handlers.py の物理分割（Step 3）
- Config のインスタンス化（Step 2）
- テストデータファクトリー（Step 6）
- 例外のラッピング（Step 4）
- 終了処理の明記（Step 8）

### 10.1 その他の改善提案（将来検討）

将来的に検討すべき改善項目:

- ログ設定の適用タイミングの分離（副作用分離）
- テストデータファクトリーのライブラリ化（polyfactory など）
- その他の最適化

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
├── ai.py (→ config, rate_limit, db/models, errors/ai)
└── eavesdrop.py (→ services/ai, config)

db/
├── sqlite.py (→ config)
└── models.py (→ なし)

errors/
├── messages.py (→ なし)
├── ai.py (→ なし)
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

- v1.2 (2026-01-18): フィードバック反映 - handlers.py物理分割、Configインスタンス化、例外ラッピング、終了処理、テストファクトリーを必須スコープに格上げ
- v1.1 (2026-01-18): 1人開発向けにシンプルな構造に修正
- v1.0 (2026-01-18): 初版作成
