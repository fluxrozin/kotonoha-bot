# Phase 6 実装計画 - 高度な機能（レート制限・コマンド・エラーハンドリング強化）

Kotonoha Discord Bot の Phase 6（高度な機能：レート制限・コマンド・エラーハンドリング強化）の実装計画書

## 目次

1. [Phase 6 の目標](#phase-6-の目標)
2. [前提条件](#前提条件)
3. [実装ステップ](#実装ステップ)
4. [完了基準](#完了基準)
5. [技術仕様](#技術仕様)
6. [リスク管理](#リスク管理)
7. [次のフェーズへ](#次のフェーズへ)

---

## Phase 6 の目標

### 高度な機能の目的

**目標**: レート制限対応、スラッシュコマンド機能、エラーハンドリングの強化を実装し、運用性とユーザー体験を向上させる

**達成すべきこと**:

- レート制限の高度な管理（モニタリング、トークンバケット、キューイング）
- スラッシュコマンド機能（`/chat start`、`/chat reset`、`/chat status`）
- 応答メッセージにモデル情報フッターを追加
- エラーハンドリングの強化（Discord API エラー、データベースエラー、エラーメッセージの改善）

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
- [Phase 5 実装完了報告](./phase5.md)

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

- [ ] `src/kotonoha_bot/rate_limit/__init__.py` が作成されている
- [ ] `src/kotonoha_bot/rate_limit/monitor.py` が作成されている
- [ ] レート制限モニターが実装されている
- [ ] API リクエスト数の追跡が動作する
- [ ] レート制限の接近検知が動作する
- [ ] 警告ログが出力される
- [ ] `litellm_provider.py` に統合されている

---

### Step 2: トークンバケットアルゴリズムの実装 (2-3 日)

#### 2.1 トークンバケットの実装

`src/kotonoha_bot/rate_limit/token_bucket.py` を作成します。

**機能**:

- リクエストレートの制御
- バースト対応
- トークンの自動補充

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

- [ ] `src/kotonoha_bot/rate_limit/token_bucket.py` が作成されている
- [ ] トークンバケットアルゴリズムが実装されている
- [ ] リクエストレートの制御が動作する
- [ ] バースト対応が動作する
- [ ] トークンの自動補充が動作する
- [ ] `litellm_provider.py` に統合されている

---

### Step 3: リクエストキューイングの実装 (2-3 日)

#### 3.1 リクエストキューの実装

`src/kotonoha_bot/rate_limit/request_queue.py` を作成します。

**機能**:

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

    EAVESDROP = 1  # 聞き耳型（最低優先度）
    THREAD = 2  # スレッド型
    MENTION = 3  # メンション応答型（最高優先度）


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
- 優先度を設定（メンション > スレッド > 聞き耳型）

#### Step 3 完了チェックリスト

- [ ] `src/kotonoha_bot/rate_limit/request_queue.py` が作成されている
- [ ] リクエストキューが実装されている
- [ ] リクエストのキューイングが動作する
- [ ] 優先度管理が動作する（メンション > スレッド > 聞き耳型）
- [ ] 非同期処理が動作する
- [ ] `handlers.py` に統合されている

---

### Step 4: スラッシュコマンドの実装 (2-3 日)

#### 4.1 コマンドモジュールの作成

`src/kotonoha_bot/commands/__init__.py` と `src/kotonoha_bot/commands/chat.py` を作成します。

**機能**:

- `/chat start` コマンド（スレッド型開始）
- `/chat reset` コマンド（会話履歴リセット）
- `/chat status` コマンド（セッション状態表示）

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

    @app_commands.command(name="start", description="スレッド型の会話を開始します")
    @app_commands.describe(topic="会話のトピック（スレッド名として使用されます）")
    async def chat_start(
        self, interaction: discord.Interaction, topic: str | None = None
    ):
        """スレッド型の会話を開始

        Args:
            interaction: Discord インタラクション
            topic: 会話のトピック（オプション）
        """
        # インタラクションに応答（後で更新するため defer）
        await interaction.response.defer()

        try:
            # スレッド名を決定
            if topic:
                thread_name = topic[:50]  # 最大50文字
            else:
                thread_name = "会話"

            # スレッドを作成
            # 注意: interaction.response.defer() 後は followup.send() を使用
            # スレッドを作成するには、まずメッセージを送信する必要がある
            followup_message = await interaction.followup.send(
                "スレッドを作成中...", wait=True
            )
            thread = await followup_message.create_thread(
                name=thread_name, auto_archive_duration=60
            )

            # セッションキーを生成
            session_key = f"thread:{thread.id}"

            # セッションを取得または作成
            session = self.handler.session_manager.get_session(session_key)
            if not session:
                session = self.handler.session_manager.create_session(
                    session_key=session_key,
                    session_type="thread",
                    channel_id=interaction.channel.id,
                    thread_id=thread.id,
                    user_id=interaction.user.id,
                )
                logger.info(f"Created new thread session: {session_key}")

            # Bot が作成したスレッドを記録
            self.handler.router.register_bot_thread(thread.id)

            # 応答を送信
            await interaction.followup.send(
                f"スレッドを作成しました。ここからお話ししましょう。"
                f"何かお手伝いできることはありますか？",
                thread=thread,
            )

        except discord.errors.Forbidden:
            await interaction.followup.send(
                "スレッドを作成する権限がありません。", ephemeral=True
            )
        except Exception as e:
            logger.exception(f"Error in /chat start: {e}")
            await interaction.followup.send(
                "スレッドの作成に失敗しました。しばらく待ってから再度お試しください。",
                ephemeral=True,
            )

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

- [ ] `src/kotonoha_bot/commands/__init__.py` が作成されている
- [ ] `src/kotonoha_bot/commands/chat.py` が作成されている
- [ ] `/chat start` コマンドが実装されている
- [ ] `/chat reset` コマンドが実装されている
- [ ] `/chat status` コマンドが実装されている
- [ ] コマンドが正常に登録される
- [ ] コマンドが正常に動作する（動作確認済み）

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

- [ ] `message_formatter.py` が作成または更新されている
- [ ] Embed を使用したメッセージフォーマットが実装されている
- [ ] フッターに使用モデル名が表示される
- [ ] すべての応答メッセージ（mention、thread、eavesdrop）にフッターが追加されている
- [ ] メッセージ分割時の対応が実装されている

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

- [ ] `src/kotonoha_bot/errors/__init__.py` が作成されている
- [ ] `src/kotonoha_bot/errors/discord_errors.py` が作成されている
- [ ] `src/kotonoha_bot/errors/database_errors.py` が作成されている
- [ ] Discord API エラーの分類が実装されている
- [ ] データベースエラーの分類が実装されている
- [ ] ユーザーフレンドリーなエラーメッセージが生成される
- [ ] 場面緘黙支援を考慮した表現が使用される
- [ ] `handlers.py` に統合されている

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

- `/chat start` コマンドの動作
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

- [ ] レート制限のテストが実装されている
- [ ] コマンドのテストが実装されている
- [ ] 応答メッセージフッターのテストが実装されている
- [ ] エラーハンドリングのテストが実装されている
- [ ] すべてのテストが通過する
- [ ] テストカバレッジが適切である

---

### Step 7: 動作確認とドキュメント更新 (1 日)

#### 7.1 動作確認チェックリスト

1. **レート制限対応**

   - [ ] レート制限モニターが動作する
   - [ ] トークンバケットが動作する
   - [ ] リクエストキューが動作する
   - [ ] 優先度管理が動作する

2. **スラッシュコマンド**

   - [ ] `/chat start` コマンドが動作する
   - [ ] `/chat reset` コマンドが動作する
   - [ ] `/chat status` コマンドが動作する

3. **応答メッセージのフッター**

   - [ ] すべての応答メッセージに使用モデル名が表示される

4. **エラーハンドリング**

   - [ ] Discord エラーが適切に分類される
   - [ ] データベースエラーが適切に分類される
   - [ ] ユーザーフレンドリーなエラーメッセージが表示される

#### 7.2 ドキュメント更新

- [ ] `.env.example` にレート制限の設定を追加
- [ ] README に Phase 6 の機能を追加
- [ ] 実装ロードマップを更新

#### Step 7 完了チェックリスト

- [ ] すべての動作確認項目が完了
- [ ] ドキュメントが更新されている
- [ ] 問題が発生した場合はトラブルシューティングを実施

---

## 完了基準

### Phase 6 完了の定義

以下の全ての条件を満たした時、Phase 6 が完了とする:

1. **レート制限対応**

   - [ ] レート制限モニターが実装されている
   - [ ] トークンバケットアルゴリズムが実装されている
   - [ ] リクエストキューが実装されている
   - [ ] 優先度管理が動作する（メンション > スレッド > 聞き耳型）

2. **スラッシュコマンド**

   - [ ] `/chat start` コマンドが動作する
   - [ ] `/chat reset` コマンドが動作する
   - [ ] `/chat status` コマンドが動作する

3. **エラーハンドリングの強化**

   - [ ] Discord API エラーの分類が実装されている（新規実装）
   - [ ] データベースエラーの分類が実装されている（新規実装）
   - [ ] ユーザーフレンドリーなエラーメッセージが生成される（新規実装）
   - [ ] 場面緘黙支援を考慮した表現が使用される（新規実装）

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

1. **テスト**

   - [ ] レート制限のテストが実装されている
   - [ ] コマンドのテストが実装されている
   - [ ] エラーハンドリングのテストが実装されている
   - [ ] すべてのテストが通過する

---

## 技術仕様

### レート制限設定

| 設定項目               | デフォルト値 | 説明                      |
| ---------------------- | ------------ | ------------------------- |
| `RATE_LIMIT_CAPACITY`  | 100          | トークンバケットの容量    |
| `RATE_LIMIT_REFILL`    | 10.0         | 補充レート（トークン/秒） |
| `RATE_LIMIT_WINDOW`    | 60           | 監視ウィンドウ（秒）      |
| `RATE_LIMIT_THRESHOLD` | 0.8          | 警告閾値（0.0-1.0）       |

### リクエスト優先度

| 優先度 | 会話の契機 | 説明                   |
| ------ | ---------- | ---------------------- |
| 高     | メンション | メンション応答型       |
| 中     | スレッド   | スレッド型             |
| 低     | 聞き耳型   | 聞き耳型（最低優先度） |

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

- [コマンド仕様書](../../specifications/command-specification.md)
- [実装ロードマップ](../roadmap.md)
- [Phase 5 実装完了報告](./phase5.md)
- [Discord.py ドキュメント](https://discordpy.readthedocs.io/)
- [Discord API ドキュメント](https://discord.com/developers/docs/)

---

**作成日**: 2026 年 1 月 15 日
**最終更新日**: 2026 年 1 月 15 日
**対象フェーズ**: Phase 6（高度な機能）
**実装状況**: ⏳ 未実装
**前提条件**: Phase 1, 2, 3, 4, 5 完了済み ✅
**次のフェーズ**: Phase 7（完全リファクタリング）
**バージョン**: 1.0
**見積もり期間**: 約 8.5-10.5 日

**注意**: この実装計画書のコード例は、実際の既存実装（Phase 1-5）の構造に基づいて作成されています。実装時は既存のコード構造（`KotonohaBot`、`MessageHandler`、`SessionManager`、`ChatSession`など）を確認し、整合性を保つようにしてください。
