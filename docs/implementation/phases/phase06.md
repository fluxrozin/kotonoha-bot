# Phase 6 実装完了報告 - 高度な機能（レート制限・コマンド・エラーハンドリング強化）

Kotonoha Discord Bot の Phase 6（高度な機能：レート制限・コマンド・エラーハンドリング強化）の実装完了報告

## 目次

1. [実装サマリー](#実装サマリー)
2. [Phase 6 の目標](#phase-6-の目標)
3. [前提条件](#前提条件)
4. [実装完了項目](#実装完了項目)
5. [実装ステップ](#実装ステップ)
6. [完了基準](#完了基準)
7. [技術仕様](#技術仕様)
8. [実装ファイル一覧](#実装ファイル一覧)
9. [テスト結果](#テスト結果)
10. [技術的な改善点](#技術的な改善点)
11. [変更点の詳細](#変更点の詳細)
12. [リスク管理](#リスク管理)
13. [次のフェーズへ](#次のフェーズへ)

---

## 実装サマリー

Phase 6（高度な機能：レート制限・コマンド・エラーハンドリング強化）の実装が完了しました。すべての主要機能が実装され、テストも通過しています。

**主な変更点**:

- `/chat start` コマンドは削除されました（メンションでスレッド作成と応答が可能なため冗長）
- リクエストキューの優先度は「聞き耳型 > メンション > スレッド」に変更されました
- レート制限使用率が Embed フッターに表示されるようになりました

---

## Phase 6 の目標

### 高度な機能の目的

**目標**: レート制限対応、スラッシュコマンド機能、エラーハンドリングの強化を実装し、運用性とユーザー体験を向上させる

**達成すべきこと**:

- レート制限の高度な管理（モニタリング、トークンバケット）
- スラッシュコマンド機能（`/chat reset`、`/chat status`）
- 応答メッセージにモデル情報フッターを追加
- エラーハンドリングの強化（Discord API エラー、データベースエラー、エラーメッセージの改善）
- リクエストキューイング（非同期処理による優先度管理）

**注意**: この実装計画書のコード例は、実際の既存実装（Phase 1-5）の構造に基づいて作成されています。実装時は既存のコード構造を確認し、整合性を保つようにしてください。

**スコープ外（Phase 7 以降）**:

- 完全リファクタリング（Phase 7 で実装予定）
- 高度なモニタリング機能（Phase 8 で実装予定）
- 設定管理機能（`/settings` コマンド、Phase 8 で実装予定）
- 自動更新機能（Phase 3 で実装済み）

---

## 前提条件

### 必要な環境

1. **Phase 1-5 の完了**

   - ✅ Phase 1: MVP（メンション応答型）完了
   - ✅ Phase 2: NAS デプロイ完了
   - ✅ Phase 3: CI/CD・運用機能完了
   - ✅ Phase 4: 機能改善完了
   - ✅ Phase 5: 会話の契機拡張完了

2. **開発環境**

   - Python 3.14
   - uv（推奨）または pip
   - Git
   - VSCode（推奨）

3. **動作確認環境**

   - Discord Bot が動作している環境
   - テスト用の Discord サーバー
   - スラッシュコマンドのテスト権限

### 必要な知識

- Python の基本的な知識
- Discord.py のスラッシュコマンド API
- レート制限アルゴリズム（トークンバケット）の基本的な知識
- 非同期プログラミング（asyncio、キューイング）

### 関連資料

- [コマンド仕様書](../../specifications/command-specification.md)
- [実装ロードマップ](../roadmap.md)
- [Phase 5 実装完了報告](./phase05.md)

---

## 実装完了項目

### 1. レート制限対応 ✅

#### 1.1 レート制限モニター (`src/kotonoha_bot/rate_limit/monitor.py`)

- ✅ API リクエスト数の追跡
- ✅ レート制限の接近を検知
- ✅ 警告ログの出力
- ✅ `LiteLLMProvider`への統合

#### 1.2 トークンバケットアルゴリズム (`src/kotonoha_bot/rate_limit/token_bucket.py`)

- ✅ リクエストレートの制御
- ✅ バースト対応
- ✅ トークンの自動補充
- ✅ `LiteLLMProvider`への統合

#### 1.3 リクエストキュー (`src/kotonoha_bot/rate_limit/request_queue.py`)

- ✅ リクエストのキューイング
- ✅ 優先度管理（聞き耳型 > メンション > スレッド）
- ✅ 非同期処理
- ✅ `MessageHandler`への統合

### 2. スラッシュコマンド ✅

#### 2.1 `/chat reset` コマンド (`src/kotonoha_bot/commands/chat.py`)

- ✅ 会話履歴のリセット
- ✅ すべてのセッションタイプに対応（メンション、スレッド、聞き耳型）

#### 2.2 `/chat status` コマンド

- ✅ セッション状態の表示
- ✅ 会話履歴件数の表示
- ✅ セッションタイプの表示

**注意**: `/chat start` コマンドは削除されました。メンションでスレッド作成と応答が可能なため、冗長でした。

### 3. 応答メッセージのフッター ✅

#### 3.1 モデル情報フッター (`src/kotonoha_bot/utils/message_formatter.py`)

- ✅ すべての応答メッセージに使用モデル名を表示（英語表記）
- ✅ レート制限使用率を表示（パーセンテージ形式）
- ✅ Embed 形式での表示
- ✅ `MessageHandler`への統合
- ✅ メッセージ分割時の対応（最初のメッセージのみ Embed、残りは通常メッセージ）

### 4. エラーハンドリングの強化 ✅

#### 4.1 Discord API エラーの分類 (`src/kotonoha_bot/errors/discord_errors.py`)

- ✅ エラータイプの分類（PERMISSION, RATE_LIMIT, NOT_FOUND, INVALID, SERVER_ERROR, UNKNOWN）
- ✅ ユーザーフレンドリーなエラーメッセージの生成
- ✅ 場面緘黙支援を考慮した表現

#### 4.2 データベースエラーの分類 (`src/kotonoha_bot/errors/database_errors.py`)

- ✅ エラータイプの分類（LOCKED, INTEGRITY, OPERATIONAL, UNKNOWN）
- ✅ ユーザーフレンドリーなエラーメッセージの生成

#### 4.3 ハンドラーへの統合

- ✅ メンション応答でのエラーハンドリング
- ✅ スレッド応答でのエラーハンドリング
- ✅ 聞き耳型応答でのエラーハンドリング（エラーメッセージを送信しない）

### 5. テスト ✅

#### 5.1 テスト結果サマリー

総テスト数: 63 テスト、すべて通過 ✅

詳細は[テスト結果](#テスト結果)セクションを参照してください。

---

## 実装ステップ

### Step 1: レート制限モニタリングの実装 (2-3 日)

#### 1.1 レート制限モニターの作成

`src/kotonoha_bot/rate_limit/__init__.py` と `src/kotonoha_bot/rate_limit/monitor.py` を作成します。

**機能**:

- API リクエスト数の追跡
- レート制限の接近を検知
- 警告ログの出力

**実装例**:

```python
"""レート制限モニター"""
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict

logger = logging.getLogger(__name__)


class RateLimitMonitor:
    """レート制限モニター

    API リクエスト数を追跡し、レート制限の接近を検知する。
    """

    def __init__(self, window_seconds: int = 60, warning_threshold: float = 0.8):
        """初期化

        Args:
            window_seconds: 監視ウィンドウ（秒）
            warning_threshold: 警告閾値（0.0-1.0、レート制限の何%で警告するか）
        """
        self.window_seconds = window_seconds
        self.warning_threshold = warning_threshold
        # リクエスト履歴: キー: エンドポイント、値: タイムスタンプのリスト
        self.request_history: Dict[str, list[datetime]] = defaultdict(list)
        # レート制限情報: キー: エンドポイント、値: (制限数, ウィンドウ秒)
        self.rate_limits: Dict[str, tuple[int, int]] = {}

    def record_request(self, endpoint: str) -> None:
        """リクエストを記録

        Args:
            endpoint: API エンドポイント（例: "claude-api"）
        """
        now = datetime.now()
        self.request_history[endpoint].append(now)

        # 古い履歴を削除
        cutoff = now - timedelta(seconds=self.window_seconds)
        self.request_history[endpoint] = [
            ts for ts in self.request_history[endpoint] if ts > cutoff
        ]

    def check_rate_limit(self, endpoint: str) -> tuple[bool, float]:
        """レート制限の接近をチェック

        Args:
            endpoint: API エンドポイント

        Returns:
            (警告が必要か, 使用率 0.0-1.0)
        """
        if endpoint not in self.rate_limits:
            return False, 0.0

        limit, window = self.rate_limits[endpoint]
        recent_requests = len(self.request_history[endpoint])
        usage_rate = recent_requests / limit if limit > 0 else 0.0

        if usage_rate >= self.warning_threshold:
            logger.warning(
                f"Rate limit approaching for {endpoint}: "
                f"{recent_requests}/{limit} requests in {window}s "
                f"({usage_rate * 100:.1f}%)"
            )
            return True, usage_rate

        return False, usage_rate

    def set_rate_limit(self, endpoint: str, limit: int, window_seconds: int) -> None:
        """レート制限を設定

        Args:
            endpoint: API エンドポイント
            limit: リクエスト数の制限
            window_seconds: ウィンドウ（秒）
        """
        self.rate_limits[endpoint] = (limit, window_seconds)
        logger.info(f"Set rate limit for {endpoint}: {limit} requests per {window_seconds}s")
```

#### 1.2 モニターの統合

`src/kotonoha_bot/ai/litellm_provider.py` を更新して、レート制限モニターを統合します。

**変更点**:

- `LiteLLMProvider` に `RateLimitMonitor` を追加
- `generate_response` メソッドでリクエストを記録
- レート制限接近時に警告ログを出力

#### Step 1 完了チェックリスト

- [x] `src/kotonoha_bot/rate_limit/__init__.py` が作成されている
- [x] `src/kotonoha_bot/rate_limit/monitor.py` が作成されている
- [x] レート制限モニターが実装されている
- [x] API リクエスト数の追跡が動作する
- [x] レート制限の接近検知が動作する
- [x] 警告ログが出力される
- [x] `litellm_provider.py` に統合されている

---

### Step 2: トークンバケットアルゴリズムの実装 (2-3 日)

#### 2.1 トークンバケットの実装

`src/kotonoha_bot/rate_limit/token_bucket.py` を作成します。

**機能**:

- リクエストレートの制御: API リクエストの送信速度を制限し、レート制限に達しないようにする
- バースト対応: 短時間に集中してリクエストが来ても、トークンが補充されるまで待機して処理する
- トークンの自動補充: 時間経過とともに自動的にトークンが補充され、リクエストを処理できるようになる

**実装例**:

```python
"""トークンバケットアルゴリズム"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class TokenBucket:
    """トークンバケット

    リクエストレートを制御するためのトークンバケットアルゴリズム。
    """

    def __init__(
        self,
        capacity: int,
        refill_rate: float,
        initial_tokens: Optional[int] = None,
    ):
        """初期化

        Args:
            capacity: バケットの容量（最大トークン数）
            refill_rate: 補充レート（トークン/秒）
            initial_tokens: 初期トークン数（None の場合は capacity）
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = initial_tokens if initial_tokens is not None else capacity
        self.last_refill = datetime.now()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> bool:
        """トークンを取得

        Args:
            tokens: 必要なトークン数

        Returns:
            トークンを取得できた場合 True
        """
        async with self._lock:
            # トークンを補充
            await self._refill()

            if self.tokens >= tokens:
                self.tokens -= tokens
                logger.debug(f"Acquired {tokens} tokens, remaining: {self.tokens}")
                return True

            logger.debug(
                f"Insufficient tokens: need {tokens}, have {self.tokens}"
            )
            return False

    async def wait_for_tokens(self, tokens: int = 1, timeout: Optional[float] = None) -> bool:
        """トークンが利用可能になるまで待機

        Args:
            tokens: 必要なトークン数
            timeout: タイムアウト（秒、None の場合は無制限）

        Returns:
            トークンを取得できた場合 True、タイムアウトした場合 False
        """
        start_time = datetime.now()

        while True:
            if await self.acquire(tokens):
                return True

            # タイムアウトチェック
            if timeout is not None:
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed >= timeout:
                    logger.warning(f"Timeout waiting for {tokens} tokens")
                    return False

            # 次のトークン補充まで待機
            await asyncio.sleep(1.0 / self.refill_rate)

    async def _refill(self) -> None:
        """トークンを補充"""
        now = datetime.now()
        elapsed = (now - self.last_refill).total_seconds()
        tokens_to_add = elapsed * self.refill_rate

        if tokens_to_add > 0:
            self.tokens = min(self.capacity, self.tokens + tokens_to_add)
            self.last_refill = now
            logger.debug(f"Refilled tokens: {self.tokens}/{self.capacity}")
```

#### 2.2 バケットの統合

`src/kotonoha_bot/ai/litellm_provider.py` を更新して、トークンバケットを統合します。

**変更点**:

- `LiteLLMProvider` に `TokenBucket` を追加
- `generate_response` メソッドでトークンを取得してから API 呼び出し
- トークンが不足している場合は待機

#### Step 2 完了チェックリスト

- [x] `src/kotonoha_bot/rate_limit/token_bucket.py` が作成されている
- [x] トークンバケットアルゴリズムが実装されている
- [x] リクエストレートの制御が動作する
- [x] バースト対応が動作する
- [x] トークンの自動補充が動作する
- [x] `litellm_provider.py` に統合されている

---

### Step 3: リクエストキューイングの実装

**目的**: 非同期処理による優先度管理を実装し、リクエストを効率的に処理する

**優先度**: 聞き耳型 > メンション > スレッド（聞き耳型が最高優先度）

**実装状況**:

- `src/kotonoha_bot/rate_limit/request_queue.py` は実装済み
- `src/kotonoha_bot/bot/handlers.py` に統合済み

#### 3.1 リクエストキューの実装（参考）

`src/kotonoha_bot/rate_limit/request_queue.py` は既に作成されていますが、使用していません。

**機能**（参考）:

- リクエストのキューイング
- 優先度管理（メンション > スレッド > 聞き耳型）
- 非同期処理

**実装例**:

```python
"""リクエストキュー"""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class RequestPriority(IntEnum):
    """リクエストの優先度"""

    THREAD = 1  # スレッド型（最低優先度）
    MENTION = 2  # メンション応答型（中優先度）
    EAVESDROP = 3  # 聞き耳型（最高優先度）


@dataclass
class QueuedRequest:
    """キューに追加されたリクエスト"""

    priority: RequestPriority
    func: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    future: Optional[asyncio.Future] = None


class RequestQueue:
    """リクエストキュー

    リクエストを優先度順に処理するキュー。
    """

    def __init__(self, max_size: int = 100):
        """初期化

        Args:
            max_size: キューの最大サイズ
        """
        self.max_size = max_size
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=max_size)
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        """ワーカーを開始"""
        if self._running:
            return

        self._running = True
        self._worker_task = asyncio.create_task(self._worker())
        logger.info("Request queue worker started")

    async def stop(self) -> None:
        """ワーカーを停止"""
        if not self._running:
            return

        self._running = False
        if self._worker_task:
            await self._worker_task
        logger.info("Request queue worker stopped")

    async def enqueue(
        self,
        priority: RequestPriority,
        func: Callable,
        *args,
        **kwargs,
    ) -> asyncio.Future:
        """リクエストをキューに追加

        Args:
            priority: リクエストの優先度
            func: 実行する関数
            *args: 関数の引数
            **kwargs: 関数のキーワード引数

        Returns:
            リクエストの結果を取得する Future
        """
        if self._queue.qsize() >= self.max_size:
            raise RuntimeError(f"Queue is full (max size: {self.max_size})")

        future = asyncio.Future()
        request = QueuedRequest(
            priority=priority,
            func=func,
            args=args,
            kwargs=kwargs,
            future=future,
        )

        # 優先度は高いほど先に処理される（負の値でソート）
        await self._queue.put((-priority.value, request))
        logger.debug(f"Enqueued request with priority {priority.name}")

        return future

    async def _worker(self) -> None:
        """ワーカーループ"""
        while self._running:
            try:
                # キューからリクエストを取得（タイムアウト: 1秒）
                try:
                    _, request = await asyncio.wait_for(
                        self._queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                # リクエストを実行
                try:
                    result = await request.func(*request.args, **request.kwargs)
                    if request.future and not request.future.done():
                        request.future.set_result(result)
                except Exception as e:
                    logger.exception(f"Error executing queued request: {e}")
                    if request.future and not request.future.done():
                        request.future.set_exception(e)

            except Exception as e:
                logger.exception(f"Error in request queue worker: {e}")
```

#### 3.2 キューの統合

`src/kotonoha_bot/bot/handlers.py` を更新して、リクエストキューを統合します。

**変更点**:

- `MessageHandler` に `RequestQueue` を追加
- 各ハンドラー（`handle_mention`、`handle_thread`、`handle_eavesdrop`）でキューを使用
- 優先度を設定（聞き耳型 > メンション > スレッド）
- 各ハンドラーを内部処理メソッド（`_process_mention`、`_process_thread_message`、`_process_eavesdrop`）に分離

#### Step 3 完了チェックリスト

- [x] `src/kotonoha_bot/rate_limit/request_queue.py` が作成されている
- [x] リクエストキューが実装されている
- [x] リクエストのキューイングが動作する
- [x] 優先度管理が動作する（聞き耳型 > メンション > スレッド）
- [x] 非同期処理が動作する
- [x] `handlers.py` に統合されている

---

### Step 4: スラッシュコマンドの実装 (2-3 日)

#### 4.1 コマンドモジュールの作成

`src/kotonoha_bot/commands/__init__.py` と `src/kotonoha_bot/commands/chat.py` を作成します。

**機能**:

- `/chat reset` コマンド（会話履歴リセット）
- `/chat status` コマンド（セッション状態表示）

**注意**: `/chat start` コマンドは削除されました。メンションでスレッド作成と応答が可能なため、冗長でした。

**実装例**:

```python
"""チャットコマンド"""
import logging
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from ..bot.handlers import MessageHandler
from ..session.models import MessageRole

logger = logging.getLogger(__name__)


class ChatCommands(commands.Cog):
    """チャットコマンド"""

    def __init__(self, bot: commands.Bot, handler: MessageHandler):
        self.bot = bot
        self.handler = handler

    @app_commands.command(name="reset", description="会話履歴をリセットします")
    async def chat_reset(self, interaction: discord.Interaction):
        """会話履歴をリセット

        Args:
            interaction: Discord インタラクション
        """
        await interaction.response.defer(ephemeral=True)

        try:
            # セッションキーを決定
            if isinstance(interaction.channel, discord.Thread):
                session_key = f"thread:{interaction.channel.id}"
            elif isinstance(interaction.channel, discord.DMChannel):
                session_key = f"dm:{interaction.channel.id}"
            else:
                session_key = f"mention:{interaction.user.id}"

            # セッションを取得
            session = self.handler.session_manager.get_session(session_key)
            if not session:
                await interaction.followup.send(
                    "会話履歴が見つかりませんでした。", ephemeral=True
                )
                return

            # 会話履歴をクリア（messagesリストを空にする）
            session.messages.clear()
            session.last_active_at = datetime.now()  # 最終アクセス時刻を更新
            self.handler.session_manager.save_session(session_key)

            await interaction.followup.send(
                "会話履歴をリセットしました。新しい会話として始めましょう。",
                ephemeral=True,
            )

        except Exception as e:
            logger.exception(f"Error in /chat reset: {e}")
            await interaction.followup.send(
                "会話履歴のリセットに失敗しました。", ephemeral=True
            )

    @app_commands.command(name="status", description="セッション状態を表示します")
    async def chat_status(self, interaction: discord.Interaction):
        """セッション状態を表示

        Args:
            interaction: Discord インタラクション
        """
        await interaction.response.defer(ephemeral=True)

        try:
            # セッションキーを決定
            if isinstance(interaction.channel, discord.Thread):
                session_key = f"thread:{interaction.channel.id}"
                session_type = "スレッド型"
            elif isinstance(interaction.channel, discord.DMChannel):
                session_key = f"dm:{interaction.channel.id}"
                session_type = "DM型"
            else:
                session_key = f"mention:{interaction.user.id}"
                session_type = "メンション応答型"

            # セッションを取得
            session = self.handler.session_manager.get_session(session_key)
            if not session:
                await interaction.followup.send(
                    "セッションが見つかりませんでした。", ephemeral=True
                )
                return

            # セッション情報を取得
            history = session.get_conversation_history()
            message_count = len(history)
            start_time = session.created_at.strftime("%Y-%m-%d %H:%M:%S")

            # 応答を送信
            await interaction.followup.send(
                f"現在のセッション情報:\n"
                f"- タイプ: {session_type}\n"
                f"- 会話履歴: {message_count}件\n"
                f"- 開始時刻: {start_time}",
                ephemeral=True,
            )

        except Exception as e:
            logger.exception(f"Error in /chat status: {e}")
            await interaction.followup.send(
                "セッション状態の取得に失敗しました。", ephemeral=True
            )


async def setup(bot: commands.Bot, handler: MessageHandler):
    """コマンドを登録

    Args:
        bot: Discord Bot（KotonohaBot）
        handler: メッセージハンドラー
    """
    await bot.add_cog(ChatCommands(bot, handler))
    # スラッシュコマンドを同期（グローバルコマンドとして登録）
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} slash command(s)")
    except Exception as e:
        logger.error(f"Failed to sync slash commands: {e}")
    logger.info("Chat commands registered")
```

#### 4.2 コマンドの登録

`src/kotonoha_bot/main.py` を更新して、スラッシュコマンドを登録します。

**変更点**:

- `main.py` で `setup` 関数を呼び出してコマンドを登録
- `on_ready` イベントでコマンドを同期（`bot.tree.sync()`）

**実装例**:

```python
# main.py の async_main 関数内
from kotonoha_bot.commands.chat import setup as setup_chat_commands

async def async_main():
    # ... 既存のコード ...

    # Botインスタンスの作成
    bot = KotonohaBot()

    # イベントハンドラーのセットアップ
    handler = setup_handlers(bot)

    # スラッシュコマンドを登録
    await setup_chat_commands(bot, handler)

    # ... 既存のコード ...
```

#### Step 4 完了チェックリスト

- [x] `src/kotonoha_bot/commands/__init__.py` が作成されている
- [x] `src/kotonoha_bot/commands/chat.py` が作成されている
- [x] `/chat reset` コマンドが実装されている
- [x] `/chat status` コマンドが実装されている
- [x] コマンドが正常に登録される
- [x] コマンドが正常に動作する（動作確認済み）

**注意**: `/chat start` コマンドは削除されました。メンションでスレッド作成と応答が可能なため、冗長でした。

---

### Step 4.5: 応答メッセージにモデル情報フッターを追加 (0.5 日)

#### 4.5.1 メッセージフォーマッターの実装

`src/kotonoha_bot/utils/message_formatter.py` を作成または更新します。

**機能**:

- Embed を使用したメッセージフォーマット
- フッターに使用モデル名を表示

**実装例**:

```python
"""メッセージフォーマッター"""
import discord


def create_response_embed(content: str, model_name: str) -> discord.Embed:
    """応答メッセージ用のEmbedを作成

    Args:
        content: 応答テキスト
        model_name: 使用したモデル名

    Returns:
        Embedオブジェクト
    """
    embed = discord.Embed(
        description=content,
        color=0x3498db  # 青色
    )
    # モデル名をフッターに表示
    embed.set_footer(text=f"モデル: {model_name}")
    return embed
```

#### 4.5.2 ハンドラーへの統合

`src/kotonoha_bot/bot/handlers.py` を更新して、すべての応答メッセージにフッターを追加します。

**変更点**:

- `generate_response` から使用モデル情報を取得
- `handle_mention`、`_handle_thread_message`、`handle_eavesdrop` で Embed を使用
- メッセージ分割時の対応（最初のメッセージのみフッターを表示、またはすべてに表示）

#### Step 4.5 完了チェックリスト

- [x] `message_formatter.py` が作成または更新されている
- [x] Embed を使用したメッセージフォーマットが実装されている
- [x] フッターに使用モデル名が表示される（英語表記）
- [x] フッターにレート制限使用率が表示される（パーセンテージ形式）
- [x] すべての応答メッセージ（mention、thread、eavesdrop）にフッターが追加されている
- [x] メッセージ分割時の対応が実装されている（最初のメッセージのみ Embed、残りは通常メッセージ）

---

### Step 5: エラーハンドリングの強化 (1-2 日)

#### 5.1 Discord API エラーの分類

`src/kotonoha_bot/errors/__init__.py` と `src/kotonoha_bot/errors/discord_errors.py` を作成します。

**機能**:

- Discord API エラーの分類
- エラータイプの判定
- 適切なエラーメッセージの生成

**実装例**:

```python
"""Discord API エラーの分類"""
import logging
from enum import Enum

import discord

logger = logging.getLogger(__name__)


class DiscordErrorType(Enum):
    """Discord エラーのタイプ"""

    PERMISSION = "permission"  # 権限エラー
    RATE_LIMIT = "rate_limit"  # レート制限
    NOT_FOUND = "not_found"  # リソースが見つからない
    INVALID = "invalid"  # 無効なリクエスト
    SERVER_ERROR = "server_error"  # サーバーエラー
    UNKNOWN = "unknown"  # 不明なエラー


def classify_discord_error(error: Exception) -> DiscordErrorType:
    """Discord エラーを分類

    Args:
        error: Discord エラー

    Returns:
        エラータイプ
    """
    if isinstance(error, discord.errors.Forbidden):
        return DiscordErrorType.PERMISSION
    elif isinstance(error, discord.errors.HTTPException):
        if error.status == 429:
            return DiscordErrorType.RATE_LIMIT
        elif error.status == 404:
            return DiscordErrorType.NOT_FOUND
        elif 400 <= error.status < 500:
            return DiscordErrorType.INVALID
        elif error.status >= 500:
            return DiscordErrorType.SERVER_ERROR
    elif isinstance(error, discord.errors.NotFound):
        return DiscordErrorType.NOT_FOUND

    return DiscordErrorType.UNKNOWN


def get_user_friendly_message(error_type: DiscordErrorType) -> str:
    """ユーザーフレンドリーなエラーメッセージを取得

    Args:
        error_type: エラータイプ

    Returns:
        エラーメッセージ
    """
    messages = {
        DiscordErrorType.PERMISSION: (
            "すみません。必要な権限がありません。"
            "サーバー管理者にご確認ください。"
        ),
        DiscordErrorType.RATE_LIMIT: (
            "すみません。リクエストが多すぎるため、"
            "しばらく待ってから再度お試しください。"
        ),
        DiscordErrorType.NOT_FOUND: (
            "すみません。リソースが見つかりませんでした。"
        ),
        DiscordErrorType.INVALID: (
            "すみません。リクエストが無効です。"
            "もう一度お試しください。"
        ),
        DiscordErrorType.SERVER_ERROR: (
            "すみません。Discord サーバーで問題が発生しています。"
            "しばらく待ってから再度お試しください。"
        ),
        DiscordErrorType.UNKNOWN: (
            "すみません。一時的に反応できませんでした。"
            "少し時間をおいて、もう一度試してみてください。"
        ),
    }

    return messages.get(error_type, messages[DiscordErrorType.UNKNOWN])
```

#### 5.2 データベースエラーの分類

`src/kotonoha_bot/errors/database_errors.py` を作成します。

**機能**:

- データベースエラーの分類
- エラータイプの判定
- 適切なエラーメッセージの生成

#### 5.3 エラーハンドリングの統合

`src/kotonoha_bot/bot/handlers.py` を更新して、エラーハンドリングを強化します。

**変更点**:

- 各ハンドラーでエラー分類を使用
- ユーザーフレンドリーなエラーメッセージを送信
- 場面緘黙支援を考慮した表現

#### Step 5 完了チェックリスト

- [x] `src/kotonoha_bot/errors/__init__.py` が作成されている
- [x] `src/kotonoha_bot/errors/discord_errors.py` が作成されている
- [x] `src/kotonoha_bot/errors/database_errors.py` が作成されている
- [x] Discord API エラーの分類が実装されている
- [x] データベースエラーの分類が実装されている
- [x] ユーザーフレンドリーなエラーメッセージが生成される
- [x] 場面緘黙支援を考慮した表現が使用される
- [x] `handlers.py` に統合されている（メンション、スレッド、聞き耳型すべてに対応）

---

### Step 6: テストの実装 (1-2 日)

#### 6.1 レート制限のテスト

`tests/unit/test_rate_limit.py` を作成します。

**テストケース**:

- レート制限モニターの動作
- トークンバケットの動作
- リクエストキューの動作

#### 6.2 コマンドのテスト

`tests/unit/test_commands.py` を作成します。

**テストケース**:

- `/chat reset` コマンドの動作
- `/chat status` コマンドの動作

#### 6.3 応答メッセージフッターのテスト

`tests/unit/test_message_formatter.py` を作成します。

**テストケース**:

- Embed の作成が正しく動作する
- フッターに使用モデル名が表示される
- メッセージ分割時のフッター表示が正しく動作する

#### 6.4 エラーハンドリングのテスト

`tests/unit/test_errors.py` を作成します。

**テストケース**:

- Discord エラーの分類
- データベースエラーの分類
- エラーメッセージの生成

#### Step 6 完了チェックリスト

- [x] レート制限のテストが実装されている（19 テスト: 基本 15 + 警告ログ 4）
- [x] コマンドのテストが実装されている（4 テスト）
- [x] 応答メッセージフッターのテストが実装されている（5 テスト）
- [x] エラーハンドリングのテストが実装されている（20 テスト）
- [x] ハンドラーの統合テストが実装されている（15 テスト: Embed 6 + エラー 5 + キュー 4）
- [x] すべてのテストが通過する（63 テスト、すべて通過 ✅）
- [x] テストカバレッジが適切である

---

### Step 7: 動作確認とドキュメント更新 (1 日)

#### 7.1 動作確認チェックリスト

1. **レート制限対応**

   - [x] レート制限モニターが動作する
   - [x] トークンバケットが動作する
   - [x] リクエストキューが動作する
   - [x] 優先度管理が動作する（聞き耳型 > メンション > スレッド）

2. **スラッシュコマンド**

   - [x] `/chat reset` コマンドが動作する
   - [x] `/chat status` コマンドが動作する

3. **応答メッセージのフッター**

   - [x] すべての応答メッセージに使用モデル名が表示される（英語表記）
   - [x] レート制限使用率が表示される（パーセンテージ形式）
   - [x] メッセージ分割時の対応が実装されている

4. **エラーハンドリング**

   - [x] Discord エラーが適切に分類される
   - [x] データベースエラーが適切に分類される
   - [x] ユーザーフレンドリーなエラーメッセージが表示される
   - [x] ハンドラーに統合されている（メンション、スレッド、聞き耳型すべてに対応）

#### 7.2 ドキュメント更新

- [x] `.env.example` にレート制限の設定を追加
- [x] README に Phase 6 の機能を追加（必要に応じて）
- [x] 実装ロードマップを更新（必要に応じて）

#### Step 7 完了チェックリスト

- [x] すべての動作確認項目が完了
- [x] ドキュメントが更新されている
- [x] 問題が発生した場合はトラブルシューティングを実施

---

## 完了基準

### Phase 6 完了の定義

以下の全ての条件を満たした時、Phase 6 が完了とする:

1. **レート制限対応** ✅

   - [x] レート制限モニターが実装されている
   - [x] トークンバケットアルゴリズムが実装されている
   - [x] リクエストキューが実装されている
   - [x] 優先度管理が動作する（聞き耳型 > メンション > スレッド）

2. **スラッシュコマンド** ✅

   - [x] `/chat reset` コマンドが動作する
   - [x] `/chat status` コマンドが動作する

3. **応答メッセージのフッター** ✅

   - [x] すべての応答メッセージに使用モデル名が表示される（英語表記）
   - [x] レート制限使用率が表示される（パーセンテージ形式）
   - [x] メッセージ分割時の対応が実装されている

4. **エラーハンドリングの強化** ✅

   - [x] Discord API エラーの分類が実装されている
   - [x] データベースエラーの分類が実装されている
   - [x] ユーザーフレンドリーなエラーメッセージが生成される
   - [x] 場面緘黙支援を考慮した表現が使用される
   - [x] ハンドラーに統合されている（メンション、スレッド、聞き耳型すべてに対応）

5. **テスト** ✅

   - [x] レート制限のテストが実装されている（19 テスト）
   - [x] コマンドのテストが実装されている（4 テスト）
   - [x] メッセージフォーマッターのテストが実装されている（5 テスト）
   - [x] エラーハンドリングのテストが実装されている（20 テスト）
   - [x] ハンドラーの統合テストが実装されている（15 テスト）
   - [x] すべてのテストが通過する（63 テスト、すべて通過 ✅）

**既に実装済みの機能**:

- ✅ API エラーの分類（RateLimitError、InternalServerError、AuthenticationError）: Phase 1 で実装済み
- ✅ リトライロジック（指数バックオフ）: Phase 1 で実装済み
  - ✅ 最大リトライ回数の設定（`LLM_MAX_RETRIES`、デフォルト: 3）
  - ✅ リトライ間隔の指数バックオフ（`LLM_RETRY_DELAY_BASE`、デフォルト: 1.0 秒）
  - ✅ `InternalServerError`（HTTP 529 Overloaded を含む）のリトライ対応
  - ✅ `RateLimitError`（HTTP 429）のリトライ対応
- ✅ フォールバック機能: Phase 1 で実装済み
  - ✅ フォールバックモデルへの自動切り替え（LiteLLM の`fallbacks`パラメータ）
  - ✅ フォールバック時のログ出力

---

## 技術仕様

### レート制限設定

| 設定項目               | デフォルト値 | 説明                                                  |
| ---------------------- | ------------ | ----------------------------------------------------- |
| `RATE_LIMIT_CAPACITY`  | 50           | レート制限の上限値（1 分間に 50 リクエストまで）      |
| `RATE_LIMIT_REFILL`    | 0.8          | 補充レート（リクエスト/秒、1 分間に約 48 リクエスト） |
| `RATE_LIMIT_WINDOW`    | 60           | 監視ウィンドウ（秒）                                  |
| `RATE_LIMIT_THRESHOLD` | 0.9          | 警告閾値（0.0-1.0）                                   |

### トークンバケットの動作

トークンバケットアルゴリズムは、API リクエストの送信速度を制御し、レート制限に達しないようにします。

#### 動作の仕組み

1. **トークンの管理**

   - 初期状態: 容量分のトークンが利用可能（デフォルト: 50 トークン）
   - リクエスト送信時: 1 リクエストにつき 1 トークンを消費
   - 自動補充: 時間経過とともに自動的にトークンが補充される（デフォルト: 0.8 トークン/秒）

2. **リクエスト処理の流れ**

   - トークンが十分な場合: すぐにリクエストを処理（即座に応答）
   - トークンが不足している場合: トークンが補充されるまで待機してから処理（最大約 1.25 秒待機）
   - タイムアウト: 30 秒以内にトークンが取得できない場合はエラー（通常は発生しない）

3. **ユーザーから見た動作**
   - **通常時**: すぐに応答（トークンが十分な場合）
   - **トークン不足時**: 最大約 1.25 秒待ってから応答（**無反応ではない**）
   - **極端な場合**: 30 秒待ってもトークンが取得できない場合はエラー

#### 具体例

```txt
10:00:00 - ユーザーAがリプライ → トークン50個ある → すぐに応答 ✅
10:00:01 - ユーザーBがリプライ → トークン49個ある → すぐに応答 ✅
...
10:00:50 - ユーザーZがリプライ → トークン0個 → 約1.25秒待機 → 応答 ✅
```

**重要なポイント**: トークンバケットはリクエストを拒否しません。トークンが不足している場合は、自動的に補充されるまで待機してから処理します。ユーザーから見ると、応答が少し遅れる可能性はありますが、**無反応になることはありません**。

### リクエスト優先度

| 優先度 | 会話の契機 | 説明                     |
| ------ | ---------- | ------------------------ |
| 高     | 聞き耳型   | 聞き耳型（最高優先度）   |
| 中     | メンション | メンション応答型         |
| 低     | スレッド   | スレッド型（最低優先度） |

### エラー分類

| エラータイプ   | 説明                   | 対応方法                   |
| -------------- | ---------------------- | -------------------------- |
| `PERMISSION`   | 権限エラー             | ユーザーに権限不足を通知   |
| `RATE_LIMIT`   | レート制限             | 待機してからリトライ       |
| `NOT_FOUND`    | リソースが見つからない | エラーメッセージを表示     |
| `INVALID`      | 無効なリクエスト       | エラーメッセージを表示     |
| `SERVER_ERROR` | サーバーエラー         | 待機してからリトライ       |
| `UNKNOWN`      | 不明なエラー           | 汎用エラーメッセージを表示 |

---

## 実装ファイル一覧

### 新規作成ファイル

1. **レート制限**

   - `src/kotonoha_bot/rate_limit/__init__.py`
   - `src/kotonoha_bot/rate_limit/monitor.py`
   - `src/kotonoha_bot/rate_limit/token_bucket.py`
   - `src/kotonoha_bot/rate_limit/request_queue.py`

2. **スラッシュコマンド**

   - `src/kotonoha_bot/commands/__init__.py`
   - `src/kotonoha_bot/commands/chat.py`

3. **エラーハンドリング**

   - `src/kotonoha_bot/errors/__init__.py`
   - `src/kotonoha_bot/errors/discord_errors.py`
   - `src/kotonoha_bot/errors/database_errors.py`

4. **メッセージフォーマッター**

   - `src/kotonoha_bot/utils/message_formatter.py`

5. **テスト**
   - `tests/unit/test_rate_limit.py`
   - `tests/unit/test_rate_limit_monitor_warning.py`
   - `tests/unit/test_commands.py`
   - `tests/unit/test_message_formatter.py`
   - `tests/unit/test_errors.py`
   - `tests/unit/test_handlers_embed.py`
   - `tests/unit/test_handlers_error_integration.py`
   - `tests/unit/test_handlers_queue_integration.py`

### 修正ファイル

1. **設定**

   - `src/kotonoha_bot/config.py` - レート制限設定の追加（デフォルト値: 容量 50、補充レート 0.8、警告閾値 0.9）

2. **AI プロバイダー**

   - `src/kotonoha_bot/ai/litellm_provider.py` - レート制限統合、非同期化、レート制限使用率取得メソッド追加

3. **メッセージハンドラー**

   - `src/kotonoha_bot/bot/handlers.py` - リクエストキュー統合、エラーハンドリング強化、モデル情報フッター追加、レート制限使用率表示

4. **LLM Judge**

   - `src/kotonoha_bot/eavesdrop/llm_judge.py` - 非同期化対応

5. **メイン**

   - `src/kotonoha_bot/main.py` - スラッシュコマンド登録

6. **環境変数テンプレート**
   - `.env.example` - レート制限設定の追加

---

## テスト結果

**実行日**: 2026 年 1 月 15 日  
**実行環境**: Python 3.14.2, pytest 9.0.2  
**実行コマンド**: `uv run pytest tests/unit/ -k "rate_limit or commands or message_formatter or errors or handlers_embed or handlers_error or handlers_queue"`

### テスト結果サマリー

- **総テスト数**: 63 テスト
- **通過**: 63 テスト ✅
- **失敗**: 0 テスト ✅

### 通過したテスト

- ✅ レート制限モニター: 5 テスト
- ✅ トークンバケット: 6 テスト
- ✅ リクエストキュー: 4 テスト
- ✅ レート制限モニター警告: 4 テスト
- ✅ コマンド: 4 テスト
- ✅ メッセージフォーマッター: 5 テスト
- ✅ エラーハンドリング: 20 テスト
- ✅ ハンドラー Embed: 6 テスト
- ✅ ハンドラーエラー統合: 5 テスト
- ✅ ハンドラーキュー統合: 4 テスト

**注意**: pytest は`pyproject.toml`の`dependency-groups.dev`に含まれており、`uv run pytest`コマンドで実行する必要があります。

---

## 技術的な改善点

### 1. 非同期処理の改善

- `LiteLLMProvider.generate_response`を非同期化
- リクエストキューによる非同期処理の管理
- 優先度管理による効率的なリクエスト処理

### 2. エラーハンドリングの統一

- Discord API エラーとデータベースエラーの分類を統一
- ユーザーフレンドリーなエラーメッセージの生成
- 場面緘黙支援を考慮した表現

### 3. レート制限の高度な管理

- トークンバケットアルゴリズムによる柔軟なレート制限
- 優先度管理によるリクエストの効率的な処理
- レート制限使用率の可視化

### 4. ユーザー体験の向上

- スラッシュコマンドによる直感的な操作
- モデル情報とレート制限使用率の表示による透明性の向上
- エラーメッセージの改善

### 5. テストの充実

- 単体テストの充実（63 テスト）
- 統合テストの追加（ハンドラー、エラーハンドリング、リクエストキュー）
- 警告ログのテスト追加

---

## 変更点の詳細

### 削除された機能

- `/chat start` コマンド: メンションでスレッド作成と応答が可能なため、冗長として削除

### 変更された機能

- リクエストキューの優先度: 「メンション > スレッド > 聞き耳型」から「聞き耳型 > メンション > スレッド」に変更
- レート制限のデフォルト値: 容量 50、補充レート 0.8、警告閾値 0.9 に変更

### 追加された機能

- レート制限使用率の表示（Embed フッター）
- 警告ログのテスト
- ハンドラーの統合テスト（Embed、エラーハンドリング、リクエストキュー）

---

## リスク管理

### リスク 1: レート制限の実装が複雑

**症状**:

- トークンバケットの実装が複雑
- リクエストキューの実装が複雑

**対策**:

- 段階的な実装（モニター → バケット → キュー）
- テストの充実
- 既存のライブラリの活用（可能な場合）

### リスク 2: スラッシュコマンドの実装が複雑

**症状**:

- Discord.py のスラッシュコマンド API が複雑
- コマンドの同期が失敗する

**対策**:

- Discord.py のドキュメントを参照
- 段階的な実装（1 コマンドずつ）
- 動作確認を徹底

### リスク 3: エラーハンドリングの実装が複雑

**症状**:

- エラーの分類が複雑
- エラーメッセージの生成が複雑

**対策**:

- 既存のエラーハンドリングを参考にする
- 段階的な実装（Discord → データベース）
- テストの充実

---

## 次のフェーズへ

### Phase 7（完全リファクタリング）の準備

Phase 6 が完了したら、**Phase 7（完全リファクタリング）** を実施することを推奨します。コードベースの品質向上と技術的負債の解消により、その後の Phase 8-10 の実装がより効率的になります。

**Phase 7 の主な内容**:

1. **コード構造の整理**

   - モジュール構造の最適化
   - クラス設計の改善
   - 関数・メソッドの整理

2. **アーキテクチャの改善**

   - 設計パターンの適用
   - エラーハンドリングの統一
   - 設定管理の改善

3. **パフォーマンス最適化**

   - データベースクエリの最適化
   - メモリ使用量の最適化
   - 非同期処理の最適化

4. **コード品質の向上**

   - 型ヒントの完全化
   - ドキュメントの充実
   - コードスタイルの統一

5. **テストの充実**

   - テストカバレッジの向上（目標: 80%以上）
   - テストの品質向上

6. **ドキュメントの更新**
   - アーキテクチャドキュメントの更新
   - API ドキュメントの更新

### Phase 8（高度な運用機能）の準備

Phase 7 完了後、以下の機能拡張を検討:

1. **高度なモニタリング機能（Phase 8）**

   - メトリクス収集機能
   - ダッシュボード機能（オプション）
   - アラート機能

2. **設定管理機能（Phase 8）**

   - `/settings` コマンド
   - チャンネルごとの設定
   - ユーザーごとの設定
   - グローバル設定（管理者のみ変更可能）

3. **パフォーマンス分析（Phase 8）**

   - パフォーマンスメトリクスの収集
   - 分析レポートの生成
   - ボトルネックの特定

4. **ログ出力の強化（Phase 8）**

   - 構造化ログの実装
   - ログの検索・フィルタリング機能
   - ログのエクスポート機能

5. **コスト管理機能（Phase 8）**
   - トークン使用量の詳細追跡
   - コスト計算機能
   - コストレポート機能

---

## 参考資料

- [Phase 6 実装完了報告](./phase6-completion-report.md)
- [コマンド仕様書](../../specifications/command-specification.md)
- [実装ロードマップ](../roadmap.md)
- [Phase 5 実装完了報告](./phase05.md)
- [Discord.py ドキュメント](https://discordpy.readthedocs.io/)
- [Discord API ドキュメント](https://discord.com/developers/docs/)

---

**実装者**: AI Agent  
**レビュー**: 未実施  
**デプロイ**: 未実施

---

**作成日**: 2026 年 1 月 15 日
**最終更新日**: 2026 年 1 月 15 日
**実装期間**: 2026 年 1 月 15 日
**対象フェーズ**: Phase 6（高度な機能）
**実装状況**: ✅ 完了
**前提条件**: Phase 1, 2, 3, 4, 5 完了済み ✅
**次のフェーズ**: Phase 7（完全リファクタリング）
**バージョン**: 1.0
**実装期間**: 約 1 日

**注意**: この実装計画書のコード例は、実際の既存実装（Phase 1-5）の構造に基づいて作成されています。実装時は既存のコード構造（`KotonohaBot`、`MessageHandler`、`SessionManager`、`ChatSession`など）を確認し、整合性を保つようにしてください。
