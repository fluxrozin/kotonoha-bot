# Phase 5 実装計画 - 会話の契機拡張（スレッド型・聞き耳型）

Kotonoha Discord Bot の Phase 5（会話の契機拡張：スレッド型・聞き耳型）の実装計画書

## 目次

1. [Phase 5 の目標](#phase-5-の目標)
2. [前提条件](#前提条件)
3. [実装ステップ](#実装ステップ)
4. [完了基準](#完了基準)
5. [技術仕様](#技術仕様)
6. [リスク管理](#リスク管理)
7. [次のフェーズへ](#次のフェーズへ)

---

## Phase 5 の目標

### 会話の契機拡張の目的

**目標**: 3 つの会話の契機（メンション/スレッド/聞き耳型）を実装し、多様な利用シーンに対応する

**達成すべきこと**:

- メンション応答型の維持（既存機能）
- スレッド型の実装（メンション時に自動スレッド作成）
- 聞き耳型の実装（LLM 判断による自然な会話参加）
- 統一インターフェースによる 3 つの方式の統合管理

**スコープ外（Phase 6 以降）**:

- スラッシュコマンド（Phase 6 で実装予定）
- 高度なレート制限管理（Phase 6 で実装予定）
- ルールベース判断機能（聞き耳型のアプローチ 2、オプション）

---

## 前提条件

### 必要な環境

1. **Phase 1-4 の完了**

   - ✅ Phase 1: MVP（メンション応答型）完了
   - ✅ Phase 2: NAS デプロイ完了
   - ✅ Phase 3: CI/CD・運用機能完了
   - ✅ Phase 4: 機能改善完了

2. **開発環境**

   - Python 3.14
   - uv（推奨）または pip
   - Git
   - VSCode（推奨）

3. **動作確認環境**

   - Discord Bot が動作している環境
   - テスト用の Discord サーバー
   - スレッド作成権限のあるチャンネル

### 必要な知識

- Python の基本的な知識
- Discord.py の基本的な知識（スレッド API）
- LLM API の基本的な知識（判定用プロンプトの設計）

### 関連資料

- [ADR-0005: 3 つの会話の契機](../../architecture/adr/0005-four-conversation-triggers.md)
- [会話の契機の詳細説明](../../requirements/conversation-triggers.md)
- [実装ロードマップ](../roadmap.md)

---

## 実装ステップ

### Step 1: メッセージルーターの実装 (2-3 日)

#### 1.1 メッセージルーターの作成

`src/kotonoha_bot/router/__init__.py` と `src/kotonoha_bot/router/message_router.py` を作成します。

**機能**:

- メッセージを受信し、会話の契機を判定
- メンション応答型、スレッド型、聞き耳型の判定ロジック
- 各方式へのルーティング

**実装例**:

```python
"""メッセージルーター"""
import logging
from typing import Literal

import discord

from ..bot.handlers import MessageHandler

logger = logging.getLogger(__name__)

ConversationTrigger = Literal["mention", "thread", "eavesdrop", "none"]


class MessageRouter:
    """メッセージルーター

    メッセージを受信し、会話の契機を判定して適切なハンドラーにルーティングする。
    """

    def __init__(self, handler: MessageHandler):
        self.handler = handler
        self.bot = handler.bot

    async def route(self, message: discord.Message) -> ConversationTrigger:
        """メッセージをルーティング

        Args:
            message: Discord メッセージ

        Returns:
            会話の契機の種類
        """
        # Bot自身のメッセージは無視
        if message.author.bot:
            return "none"

        # 1. メンション応答型の判定
        if self.bot.user in message.mentions:
            # スレッド型の判定（メンション + スレッド型が有効な場合）
            if await self._should_create_thread(message):
                return "thread"
            return "mention"

        # 2. スレッド型の判定（既存スレッド内での会話）
        if isinstance(message.channel, discord.Thread):
            # スレッドがBotによって作成されたものか確認
            if await self._is_bot_thread(message.channel):
                return "thread"

        # 3. 聞き耳型の判定
        if await self._should_eavesdrop(message):
            return "eavesdrop"

        return "none"

    async def _should_create_thread(self, message: discord.Message) -> bool:
        """スレッド型を有効にするか判定

        Args:
            message: Discord メッセージ

        Returns:
            スレッド型を有効にする場合 True
        """
        # TODO: 設定から読み込む（デフォルト: True）
        # 将来的にはチャンネルごとの設定に対応
        return True

    async def _is_bot_thread(self, thread: discord.Thread) -> bool:
        """Botによって作成されたスレッドか判定

        Args:
            thread: Discord スレッド

        Returns:
            Botによって作成されたスレッドの場合 True
        """
        # スレッドの作成者を確認
        # または、スレッド名に特定のプレフィックスがあるか確認
        # TODO: 実装
        return False

    async def _should_eavesdrop(self, message: discord.Message) -> bool:
        """聞き耳型を有効にするか判定

        Args:
            message: Discord メッセージ

        Returns:
            聞き耳型を有効にする場合 True
        """
        # TODO: チャンネルごとの設定から読み込む
        # デフォルト: False（聞き耳型は明示的に有効化が必要）
        return False
```

#### 1.2 ハンドラーの統合

`src/kotonoha_bot/bot/handlers.py` を更新して、メッセージルーターを統合します。

**変更点**:

- `MessageHandler` に `MessageRouter` を追加
- `on_message` イベントでルーターを使用
- 各方式のハンドラーメソッドを分離

#### Step 1 完了チェックリスト

- [ ] `src/kotonoha_bot/router/__init__.py` が作成されている
- [ ] `src/kotonoha_bot/router/message_router.py` が作成されている
- [ ] メッセージルーターが実装されている
- [ ] 会話の契機判定ロジックが実装されている
- [ ] `handlers.py` に統合されている
- [ ] メンション応答型が正常に動作する（既存機能の維持）

---

### Step 2: スレッド型の実装 (3-4 日)

#### 2.1 スレッド作成機能の実装

`src/kotonoha_bot/bot/handlers.py` に `handle_thread` メソッドを追加します。

**機能**:

- メンション検知時に自動スレッド作成
- スレッド名の生成（メッセージの最初の 100 文字）
- スレッド内での会話継続（メンション不要）

**実装例**:

```python
async def handle_thread(self, message: discord.Message):
    """スレッド型の処理"""
    # Bot自身のメッセージは無視
    if message.author.bot:
        return

    try:
        # 既存スレッド内での会話か、新規スレッド作成か判定
        if isinstance(message.channel, discord.Thread):
            # 既存スレッド内での会話
            await self._handle_thread_message(message)
        else:
            # メンション検知時の新規スレッド作成
            if self.bot.user in message.mentions:
                await self._create_thread_and_respond(message)

    except Exception as e:
        logger.exception(f"Error handling thread: {e}")
        await message.reply(
            "すみません。一時的に反応できませんでした。\n"
            "少し時間をおいて、もう一度試してみてください。"
        )

async def _create_thread_and_respond(self, message: discord.Message):
    """スレッドを作成して応答"""
    # スレッド名を生成（メッセージの最初の100文字）
    thread_name = message.content[:100] if message.content else "会話"
    if len(thread_name) < 10:
        thread_name = "会話"

    # スレッドを作成
    thread = await message.create_thread(name=thread_name, auto_archive_duration=60)

    # セッションキーを生成
    session_key = f"thread:{thread.id}"

    # セッションを取得または作成
    session = self.session_manager.get_session(session_key)
    if not session:
        session = self.session_manager.create_session(
            session_key=session_key,
            session_type="thread",
            channel_id=message.channel.id,
            thread_id=thread.id,
            user_id=message.author.id,
        )
        logger.info(f"Created new thread session: {session_key}")

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
    async with thread.typing():
        # 現在の日付情報を含むシステムプロンプトを生成
        now = datetime.now()
        weekday_names = ["月", "火", "水", "木", "金", "土", "日"]
        current_date_info = (
            f"\n\n【現在の日付情報】\n"
            f"現在の日時: {now.strftime('%Y年%m月%d日 %H:%M:%S')}\n"
            f"今日の曜日: {weekday_names[now.weekday()]}曜日\n"
            f"日付や曜日に関する質問には、この情報を基に具体的に回答してください。"
        )
        system_prompt = DEFAULT_SYSTEM_PROMPT + current_date_info

        # AI応答を生成
        response_text = self.ai_provider.generate_response(
            messages=session.get_conversation_history(),
            system_prompt=system_prompt,
        )

        # アシスタントメッセージを追加
        self.session_manager.add_message(
            session_key=session_key,
            role=MessageRole.ASSISTANT,
            content=response_text,
        )

        # セッションを保存
        self.session_manager.save_session(session_key)

        # スレッド内で返信（メッセージ分割対応）
        response_chunks = split_message(response_text)
        formatted_chunks = format_split_messages(
            response_chunks, len(response_chunks)
        )

        # 最初のメッセージは reply で送信
        if formatted_chunks:
            await thread.send(formatted_chunks[0])

            # 残りのメッセージは順次送信
            for chunk in formatted_chunks[1:]:
                await thread.send(chunk)
                await asyncio.sleep(0.5)

        logger.info(f"Sent response in thread: {thread.id}")

async def _handle_thread_message(self, message: discord.Message):
    """既存スレッド内でのメッセージ処理"""
    thread = message.channel
    session_key = f"thread:{thread.id}"

    # セッションを取得または作成
    session = self.session_manager.get_session(session_key)
    if not session:
        # スレッドが既に存在する場合、会話履歴を復元
        session = self.session_manager.create_session(
            session_key=session_key,
            session_type="thread",
            channel_id=thread.parent_id,
            thread_id=thread.id,
            user_id=message.author.id,
        )
        logger.info(f"Created thread session from existing thread: {session_key}")

    # ユーザーメッセージを追加
    self.session_manager.add_message(
        session_key=session_key,
        role=MessageRole.USER,
        content=message.content,
    )

    # AI応答を生成
    async with thread.typing():
        # 現在の日付情報を含むシステムプロンプトを生成
        now = datetime.now()
        weekday_names = ["月", "火", "水", "木", "金", "土", "日"]
        current_date_info = (
            f"\n\n【現在の日付情報】\n"
            f"現在の日時: {now.strftime('%Y年%m月%d日 %H:%M:%S')}\n"
            f"今日の曜日: {weekday_names[now.weekday()]}曜日\n"
        )
        system_prompt = DEFAULT_SYSTEM_PROMPT + current_date_info

        # AI応答を生成
        response_text = self.ai_provider.generate_response(
            messages=session.get_conversation_history(),
            system_prompt=system_prompt,
        )

        # アシスタントメッセージを追加
        self.session_manager.add_message(
            session_key=session_key,
            role=MessageRole.ASSISTANT,
            content=response_text,
        )

        # セッションを保存
        self.session_manager.save_session(session_key)

        # スレッド内で返信（メッセージ分割対応）
        response_chunks = split_message(response_text)
        formatted_chunks = format_split_messages(
            response_chunks, len(response_chunks)
        )

        # 最初のメッセージは reply で送信
        if formatted_chunks:
            await message.reply(formatted_chunks[0])

            # 残りのメッセージは順次送信
            for chunk in formatted_chunks[1:]:
                await thread.send(chunk)
                await asyncio.sleep(0.5)

        logger.info(f"Sent response in thread: {thread.id}")
```

#### 2.2 スレッドアーカイブ検知の実装

`src/kotonoha_bot/bot/handlers.py` に `on_thread_update` イベントハンドラーを追加します。

**機能**:

- スレッドアーカイブ検知
- アーカイブ時のセッション保存

**実装例**:

```python
@bot.event
async def on_thread_update(before: discord.Thread, after: discord.Thread):
    """スレッド更新時"""
    # アーカイブされた場合
    if after.archived and not before.archived:
        session_key = f"thread:{after.id}"
        try:
            # セッションを保存
            handler.session_manager.save_session(session_key)
            logger.info(f"Saved session on thread archive: {session_key}")
        except Exception as e:
            logger.error(f"Failed to save session on thread archive: {e}")
```

#### Step 2 完了チェックリスト

- [ ] メンション検知時の自動スレッド作成が実装されている
- [ ] スレッド名の生成が実装されている
- [ ] スレッド内での会話継続が実装されている（メンション不要）
- [ ] スレッドアーカイブ検知が実装されている
- [ ] アーカイブ時のセッション保存が実装されている
- [ ] スレッド型が正常に動作する（動作確認済み）

---

### Step 3: 聞き耳型の実装（アプローチ 1: LLM 判断） (4-5 日)

#### 3.1 聞き耳型モジュールの作成

`src/kotonoha_bot/eavesdrop/__init__.py` と `src/kotonoha_bot/eavesdrop/llm_judge.py` を作成します。

**機能**:

- 会話ログの一時保存（直近 10〜20 件）
- 判定フェーズ（裁判官）の実装
- 発言生成フェーズ（演者）の実装
- 判定用プロンプトの最適化

**実装例**:

```python
"""聞き耳型: LLM 判断機能"""
import logging
from typing import Literal

import discord

from ..ai.litellm_provider import LiteLLMProvider
from ..session.manager import SessionManager

logger = logging.getLogger(__name__)


class LLMJudge:
    """LLM 判断機能（アプローチ 1）

    会話ログを読み取り、LLM に「今、発言すべきか？」を判定させる。
    """

    def __init__(self, session_manager: SessionManager, ai_provider: LiteLLMProvider):
        self.session_manager = session_manager
        self.ai_provider = ai_provider
        # 判定用の軽量モデル（Gemini Flash など）
        self.judge_model = "google/gemini-2.0-flash-exp"
        # 応答生成用の通常モデル
        self.response_model = None  # デフォルトモデルを使用

    async def should_respond(
        self, channel_id: int, recent_messages: list[discord.Message]
    ) -> bool:
        """発言すべきか判定

        Args:
            channel_id: チャンネル ID
            recent_messages: 直近のメッセージリスト（10〜20 件）

        Returns:
            発言すべき場合 True
        """
        # 会話ログをフォーマット
        conversation_log = self._format_conversation_log(recent_messages)

        # 判定用プロンプト
        judge_prompt = self._create_judge_prompt(conversation_log)

        try:
            # 判定用 AI に問い合わせ（軽量モデルを使用）
            response = self.ai_provider.generate_response(
                messages=[{"role": "user", "content": judge_prompt}],
                system_prompt="",
                model=self.judge_model,
                max_tokens=10,  # YES/NO のみなので短く
            )

            # 応答を解析
            response_upper = response.strip().upper()
            return response_upper.startswith("YES")

        except Exception as e:
            logger.error(f"Error in judge phase: {e}")
            return False

    async def generate_response(
        self, channel_id: int, recent_messages: list[discord.Message]
    ) -> str | None:
        """応答を生成

        Args:
            channel_id: チャンネル ID
            recent_messages: 直近のメッセージリスト

        Returns:
            生成された応答（発言しない場合は None）
        """
        # 判定フェーズ
        should_respond = await self.should_respond(channel_id, recent_messages)
        if not should_respond:
            return None

        # 発言生成フェーズ
        conversation_log = self._format_conversation_log(recent_messages)
        response_prompt = self._create_response_prompt(conversation_log)

        try:
            # 通常の AI で応答を生成
            response = self.ai_provider.generate_response(
                messages=[{"role": "user", "content": response_prompt}],
                system_prompt=DEFAULT_SYSTEM_PROMPT,
                model=self.response_model,  # デフォルトモデル
            )

            return response

        except Exception as e:
            logger.error(f"Error in response generation phase: {e}")
            return None

    def _format_conversation_log(
        self, messages: list[discord.Message]
    ) -> str:
        """会話ログをフォーマット

        Args:
            messages: メッセージリスト

        Returns:
            フォーマットされた会話ログ
        """
        log_lines = []
        for msg in messages:
            author_name = msg.author.display_name
            content = msg.content
            log_lines.append(f"{author_name}: {content}")

        return "\n".join(log_lines)

    def _create_judge_prompt(self, conversation_log: str) -> str:
        """判定用プロンプトを作成

        Args:
            conversation_log: 会話ログ

        Returns:
            判定用プロンプト
        """
        return f"""あなたはDiscordのチャットボットです。
キャラクター設定: 場面緘黙支援に優しい、安心感のある応答を心がける。

以下の会話履歴を見て、あなたが「今すぐに発言して会話に割って入るべき状況」かどうかを判定してください。

判断基準:
- ユーザーが困っていて助けが必要そうな時: YES
- 誰かがあなたの名前を呼んだ時: YES
- 場を和らげる発言が適切な時: YES
- シリアスな話、プライベートな話、関係ない話題: NO
- 会話が途切れている、沈黙が続いている: NO

会話履歴:
{conversation_log}

回答は "YES" または "NO" の単語のみで答えてください。余計な説明は不要です。"""

    def _create_response_prompt(self, conversation_log: str) -> str:
        """応答生成用プロンプトを作成

        Args:
            conversation_log: 会話ログ

        Returns:
            応答生成用プロンプト
        """
        return f"""以下の会話履歴を見て、自然に会話に参加する返信を生成してください。

会話履歴:
{conversation_log}

自然で、場面緘黙支援に優しい、安心感のある応答を心がけてください。"""
```

#### 3.2 会話ログの一時保存機能

`src/kotonoha_bot/eavesdrop/conversation_buffer.py` を作成します。

**機能**:

- チャンネルごとの会話ログを一時保存（直近 10〜20 件）
- メッセージの追加・取得

**実装例**:

```python
"""聞き耳型: 会話ログバッファ"""
import logging
from collections import deque
from typing import Optional

import discord

logger = logging.getLogger(__name__)


class ConversationBuffer:
    """会話ログバッファ

    チャンネルごとの会話ログを一時保存する。
    """

    def __init__(self, max_size: int = 20):
        self.buffers: dict[int, deque[discord.Message]] = {}
        self.max_size = max_size

    def add_message(self, channel_id: int, message: discord.Message) -> None:
        """メッセージを追加

        Args:
            channel_id: チャンネル ID
            message: Discord メッセージ
        """
        if channel_id not in self.buffers:
            self.buffers[channel_id] = deque(maxlen=self.max_size)

        self.buffers[channel_id].append(message)

    def get_recent_messages(
        self, channel_id: int, limit: Optional[int] = None
    ) -> list[discord.Message]:
        """直近のメッセージを取得

        Args:
            channel_id: チャンネル ID
            limit: 取得件数（None の場合は全て）

        Returns:
            メッセージリスト
        """
        if channel_id not in self.buffers:
            return []

        messages = list(self.buffers[channel_id])
        if limit:
            return messages[-limit:]
        return messages

    def clear(self, channel_id: int) -> None:
        """バッファをクリア

        Args:
            channel_id: チャンネル ID
        """
        if channel_id in self.buffers:
            del self.buffers[channel_id]
```

#### 3.3 聞き耳型ハンドラーの実装

`src/kotonoha_bot/bot/handlers.py` に `handle_eavesdrop` メソッドを追加します。

**機能**:

- メッセージを受信し、会話ログに追加
- LLM 判断機能を呼び出し
- 応答を生成してメインチャンネルに投稿

**実装例**:

```python
from ..eavesdrop.llm_judge import LLMJudge
from ..eavesdrop.conversation_buffer import ConversationBuffer

class MessageHandler:
    def __init__(self, bot: KotonohaBot):
        self.bot = bot
        self.session_manager = SessionManager()
        self.ai_provider = LiteLLMProvider()
        # 聞き耳型の機能
        self.conversation_buffer = ConversationBuffer(max_size=20)
        self.llm_judge = LLMJudge(self.session_manager, self.ai_provider)
        # チャンネルごとの有効/無効設定（将来的には設定ファイルから読み込む）
        self.eavesdrop_enabled_channels: set[int] = set()

    async def handle_eavesdrop(self, message: discord.Message):
        """聞き耳型の処理"""
        # Bot自身のメッセージは無視
        if message.author.bot:
            return

        # 聞き耳型が有効なチャンネルか確認
        if message.channel.id not in self.eavesdrop_enabled_channels:
            return

        try:
            # 会話ログに追加
            self.conversation_buffer.add_message(message.channel.id, message)

            # 直近のメッセージを取得
            recent_messages = self.conversation_buffer.get_recent_messages(
                message.channel.id, limit=20
            )

            # LLM 判断機能を呼び出し
            response_text = await self.llm_judge.generate_response(
                message.channel.id, recent_messages
            )

            # 応答がある場合のみ投稿
            if response_text:
                # セッションキーを生成
                session_key = f"eavesdrop:{message.channel.id}"

                # セッションを取得または作成
                session = self.session_manager.get_session(session_key)
                if not session:
                    session = self.session_manager.create_session(
                        session_key=session_key,
                        session_type="eavesdrop",
                        channel_id=message.channel.id,
                    )
                    logger.info(f"Created new eavesdrop session: {session_key}")

                # 会話履歴を更新（直近のメッセージから）
                # 注意: 聞き耳型では、判定ログは保存しない
                # 実際に発言した場合のみ会話履歴に追加

                # アシスタントメッセージを追加
                self.session_manager.add_message(
                    session_key=session_key,
                    role=MessageRole.ASSISTANT,
                    content=response_text,
                )

                # セッションを保存
                self.session_manager.save_session(session_key)

                # メインチャンネルに直接投稿（メッセージ分割対応）
                response_chunks = split_message(response_text)
                formatted_chunks = format_split_messages(
                    response_chunks, len(response_chunks)
                )

                # 最初のメッセージを送信
                if formatted_chunks:
                    await message.channel.send(formatted_chunks[0])

                    # 残りのメッセージは順次送信
                    for chunk in formatted_chunks[1:]:
                        await message.channel.send(chunk)
                        await asyncio.sleep(0.5)

                logger.info(f"Sent eavesdrop response in channel: {message.channel.id}")

        except Exception as e:
            logger.exception(f"Error handling eavesdrop: {e}")
            # 聞き耳型ではエラーメッセージを送信しない（自然な会話参加のため）
```

#### 3.4 チャンネルごとの有効/無効設定

`src/kotonoha_bot/config.py` に聞き耳型の設定を追加します。

**実装例**:

```python
# 聞き耳型設定
EAVESDROP_ENABLED_CHANNELS: str = os.getenv(
    "EAVESDROP_ENABLED_CHANNELS", ""
)  # カンマ区切りのチャンネルID
EAVESDROP_JUDGE_MODEL: str = os.getenv(
    "EAVESDROP_JUDGE_MODEL", "google/gemini-2.0-flash-exp"
)  # 判定用モデル
EAVESDROP_BUFFER_SIZE: int = int(os.getenv("EAVESDROP_BUFFER_SIZE", "20"))  # バッファサイズ
EAVESDROP_MIN_MESSAGES: int = int(os.getenv("EAVESDROP_MIN_MESSAGES", "3"))  # 判定・応答生成に必要な最低メッセージ数
```

#### 3.5 プロンプトファイルの管理

プロンプトファイルは、プロジェクトルートの `prompts/` フォルダに集約されています。

**プロンプトファイル構成**:

```txt
prompts/
├── system_prompt.md                    # システムプロンプト
├── eavesdrop_judge_prompt.md           # 聞き耳型判定用プロンプト
└── eavesdrop_response_prompt.md       # 聞き耳型応答生成用プロンプト
```

**メリット**:

- プロンプトファイルを一箇所で管理
- Docker でマウント可能（コンテナ再起動なしで編集可能）
- バージョン管理しやすい
- コードとプロンプトの分離で保守性向上

詳細は [プロンプト管理ガイド](../../development/prompt-management.md) を参照してください。

#### 3.6 開発用コマンドの追加

開発・デバッグ用に、会話ログバッファを管理するコマンドを追加します。

**実装例**:

```python
@bot.command(name="eavesdrop")
async def eavesdrop_command(ctx, action: str | None = None):
    """聞き耳型の開発用コマンド

    使用方法:
    !eavesdrop clear - 現在のチャンネルの会話ログバッファをクリア
    !eavesdrop status - 現在のチャンネルのバッファ状態を表示
    """
    if action == "clear":
        # 現在のチャンネルのバッファをクリア
        handler.conversation_buffer.clear(ctx.channel.id)
        await ctx.send("✅ 会話ログバッファをクリアしました。")
        logger.info(f"Cleared conversation buffer for channel: {ctx.channel.id}")
    elif action == "status":
        # 現在のチャンネルのバッファ状態を表示
        recent_messages = handler.conversation_buffer.get_recent_messages(
            ctx.channel.id
        )
        message_count = len(recent_messages)
        await ctx.send(
            f"📊 現在のバッファ状態:\n"
            f"- メッセージ数: {message_count}件\n"
            f"- 最大サイズ: {Config.EAVESDROP_BUFFER_SIZE}件"
        )
    else:
        await ctx.send(
            "使用方法:\n"
            "`!eavesdrop clear` - 会話ログバッファをクリア\n"
            "`!eavesdrop status` - バッファ状態を表示"
        )
```

**機能**:

- `!eavesdrop clear`: 現在のチャンネルの会話ログバッファをクリア（開発・テスト用）
- `!eavesdrop status`: 現在のチャンネルのバッファ状態を表示（メッセージ数と最大サイズ）

**注意事項**:

- 開発用コマンドのため、必要に応じて管理者権限チェックを追加できます
- 本番環境では使用を制限することを推奨します

#### Step 3 完了チェックリスト

- [ ] `src/kotonoha_bot/eavesdrop/__init__.py` が作成されている
- [ ] `src/kotonoha_bot/eavesdrop/llm_judge.py` が作成されている
- [ ] `src/kotonoha_bot/eavesdrop/conversation_buffer.py` が作成されている
- [ ] 会話ログの一時保存が実装されている
- [ ] 判定フェーズ（裁判官）が実装されている
- [ ] 発言生成フェーズ（演者）が実装されている
- [ ] 判定用プロンプトが最適化されている（会話の雰囲気を理解できるように改善）
- [ ] チャンネルごとの有効/無効設定が実装されている
- [ ] メインチャンネルへの直接投稿が実装されている
- [ ] 最低メッセージ数のチェックが実装されている（`EAVESDROP_MIN_MESSAGES`）
- [ ] 開発用コマンド（`!eavesdrop`）が実装されている
- [ ] 聞き耳型が正常に動作する（動作確認済み）

---

### Step 4: 統一インターフェースの実装 (1-2 日)

#### 4.1 セッションキーの統一管理

`src/kotonoha_bot/session/manager.py` を確認し、各方式のセッションキー形式を統一します。

**セッションキー形式**:

- メンション応答型: `mention:{user_id}`
- スレッド型: `thread:{thread_id}`
- 聞き耳型: `eavesdrop:{channel_id}`

#### 4.2 ハンドラーの統合

`src/kotonoha_bot/bot/handlers.py` を更新して、3 つの方式を統一的に扱います。

**変更点**:

- `on_message` イベントでメッセージルーターを使用
- 各方式のハンドラーを呼び出し
- エラーハンドリングの統一

**実装例**:

```python
@bot.event
async def on_message(message: discord.Message):
    """メッセージ受信時"""
    # Bot自身のメッセージは無視
    if message.author.bot:
        await bot.process_commands(message)
        return

    # メッセージルーターで会話の契機を判定
    trigger = await handler.router.route(message)

    # 各方式のハンドラーを呼び出し
    if trigger == "mention":
        await handler.handle_mention(message)
    elif trigger == "thread":
        await handler.handle_thread(message)
    elif trigger == "eavesdrop":
        await handler.handle_eavesdrop(message)

    # コマンド処理（メンションでない場合のみ）
    if trigger != "mention" and trigger != "thread":
        await bot.process_commands(message)
```

#### Step 4 完了チェックリスト

- [ ] 3 つの方式を統一的に扱うインターフェースが実装されている
- [ ] セッションキーの統一管理が実装されている
- [ ] 各方式で会話履歴が正しく管理される
- [ ] エラーハンドリングが統一されている
- [ ] すべての方式が正常に動作する（動作確認済み）

---

### Step 5: テストの実装 (1-2 日)

#### 5.1 メッセージルーターのテスト

`tests/unit/test_message_router.py` を作成します。

**テストケース**:

- メンション応答型の判定
- スレッド型の判定
- 聞き耳型の判定
- Bot 自身のメッセージの無視

#### 5.2 スレッド型のテスト

`tests/unit/test_thread_handler.py` を作成します。

**テストケース**:

- スレッド作成機能
- スレッド内での会話継続
- スレッドアーカイブ検知

#### 5.3 聞き耳型のテスト

`tests/unit/test_eavesdrop.py` を作成します。

**テストケース**:

- 会話ログバッファの動作
- LLM 判断機能の動作（モックを使用）
- チャンネルごとの有効/無効設定

#### Step 5 完了チェックリスト

- [ ] メッセージルーターのテストが実装されている
- [ ] スレッド型のテストが実装されている
- [ ] 聞き耳型のテストが実装されている
- [ ] すべてのテストが通過する
- [ ] テストカバレッジが適切である

---

### Step 6: 動作確認とドキュメント更新 (1 日)

#### 6.1 動作確認チェックリスト

1. **メンション応答型**

   - [ ] メンション時に正常に応答する（既存機能の維持）
   - [ ] 会話履歴が正しく管理される

2. **スレッド型**

   - [ ] メンション時に自動スレッドが作成される
   - [ ] スレッド内で会話が継続する（メンション不要）
   - [ ] スレッドアーカイブ時にセッションが保存される

3. **聞き耳型**

   - [ ] 有効なチャンネルで聞き耳型が動作する
   - [ ] 適切なタイミングで会話に参加する（会話の雰囲気を理解してから）
   - [ ] 不適切なタイミングでは発言しない
   - [ ] 最低メッセージ数が溜まってから判定・応答生成を行う
   - [ ] 開発用コマンド（`!eavesdrop clear`、`!eavesdrop status`）が動作する

4. **統合動作**

   - [ ] 3 つの方式が同時に動作する
   - [ ] セッションキーが正しく管理される
   - [ ] エラーハンドリングが適切に動作する

#### 6.2 ドキュメント更新

- [ ] `.env.example` に聞き耳型の設定を追加
- [ ] README に Phase 5 の機能を追加
- [ ] 実装ロードマップを更新

#### Step 6 完了チェックリスト

- [ ] すべての動作確認項目が完了
- [ ] ドキュメントが更新されている
- [ ] 問題が発生した場合はトラブルシューティングを実施

---

## 完了基準

### Phase 5 完了の定義

以下の全ての条件を満たした時、Phase 5 が完了とする:

1. **メッセージルーター**

   - [ ] メッセージルーターが実装されている
   - [ ] 会話の契機判定ロジックが実装されている
   - [ ] 各方式へのルーティングが正常に動作する

2. **スレッド型**

   - [ ] メンション検知時の自動スレッド作成が動作する
   - [ ] スレッド内での会話継続が動作する（メンション不要）
   - [ ] スレッドアーカイブ検知が動作する
   - [ ] アーカイブ時のセッション保存が動作する

3. **聞き耳型（アプローチ 1）**

   - [ ] LLM 判断機能が実装されている
   - [ ] 会話ログの一時保存が動作する
   - [ ] 判定フェーズ（裁判官）が動作する
   - [ ] 発言生成フェーズ（演者）が動作する
   - [ ] チャンネルごとの有効/無効設定が動作する
   - [ ] メインチャンネルへの直接投稿が動作する

4. **統一インターフェース**

   - [ ] 3 つの方式を統一的に扱うインターフェースが実装されている
   - [ ] セッションキーの統一管理が実装されている
   - [ ] 各方式で会話履歴が正しく管理される

5. **テスト**

   - [ ] メッセージルーターのテストが実装されている
   - [ ] スレッド型のテストが実装されている
   - [ ] 聞き耳型のテストが実装されている
   - [ ] すべてのテストが通過する

---

## 技術仕様

### セッションキー形式

| 方式             | セッションキー形式       | 説明                 |
| ---------------- | ------------------------ | -------------------- |
| メンション応答型 | `mention:{user_id}`      | ユーザー ID ベース   |
| スレッド型       | `thread:{thread_id}`     | スレッド ID ベース   |
| 聞き耳型         | `eavesdrop:{channel_id}` | チャンネル ID ベース |

### 聞き耳型の判定用プロンプト

判定用プロンプトは以下の要素を含む必要があります:

**重要な改善点（実装済み）**:

- **会話の雰囲気を理解する**: 固定のメッセージ数ではなく、会話の雰囲気（場が荒れている、アドバイスが求められている、ファシリテートが必要など）を理解してから応答する
- **最低メッセージ数のチェック**: 会話の流れを理解するため、最低限のメッセージ数（デフォルト: 3 件）が溜まってから判定・応答生成を行う
- **店側スタッフからの注意喚起への対応**: ビジネス的な正式な連絡に対しては応答しない

**判定基準（YES と答える場合）**:

- 場が荒れている、緊張感が高い時（対立、感情的、不穏な空気）
- アドバイスや助言が求められている時（質問、相談、困っている様子）
- ファシリテートが必要な時（会話が停滞、方向性が定まらない、調整が必要）
- その他（名前を呼ばれた時、会話が途切れている時など）

**判定基準（NO と答える場合）**:

- 店側スタッフやイベント主催者からの注意喚起、苦言、ルール説明など（ビジネス的な正式な連絡）
- 会話が順調に進行している時（割り込む必要がない）
- 不適切なタイミング（シリアスな話、プライベートな会話など）

判定用プロンプトは以下の要素を含む必要があります:

- キャラクター設定（場面緘黙支援に優しい、安心感のある応答）
- 判断基準（YES/NO の条件）
- 会話履歴
- 回答形式（YES/NO のみ）

### 会話ログバッファ

- 最大サイズ: 20 件（デフォルト、`EAVESDROP_BUFFER_SIZE` で設定可能）
- 最低メッセージ数: 3 件（デフォルト、`EAVESDROP_MIN_MESSAGES` で設定可能）
  - 会話の流れを理解するため、最低限のメッセージ数が溜まってから判定・応答生成を行う
- チャンネルごとに独立管理
- メッセージの追加・取得が可能
- 開発用コマンド（`!eavesdrop clear`、`!eavesdrop status`）で管理可能

### スレッド作成設定

- スレッド名: メッセージの最初の 100 文字
- 自動アーカイブ: 60 分（デフォルト）
- スレッド作成権限: Bot に必要

---

## リスク管理

### リスク 1: スレッド作成の権限問題

**症状**:

- Bot にスレッド作成権限がない場合、エラーが発生する

**対策**:

- エラーハンドリングを実装
- 権限がない場合はメンション応答型にフォールバック
- ログに警告を出力

### リスク 2: 聞き耳型の判定精度の問題

**症状**:

- 不適切なタイミングで発言する
- 空気を読めない発言をする

**対策**:

- 判定用プロンプトの最適化
- 判断基準の明確化
- テストケースの充実

### リスク 3: LLM 判断のコスト増加

**症状**:

- 全てのメッセージに対して判定リクエストを送るため、API コストが増加

**対策**:

- 軽量モデル（Gemini Flash）を使用
- チャンネルごとの有効/無効設定
- 判定結果のキャッシュ（将来的に実装）

### リスク 4: メモリ使用量の増加

**症状**:

- 会話ログバッファがメモリを消費する

**対策**:

- バッファサイズの制限（デフォルト: 20 件）
- 定期的なクリーンアップ（将来的に実装）

---

## 次のフェーズへ

### Phase 6 の準備

Phase 5 が完了したら、以下の機能拡張を検討:

1. **高度な機能（Phase 6）**

   - レート制限対応（高度な管理）
   - スラッシュコマンド
   - エラーハンドリングの強化

2. **聞き耳型の改善（オプション）**

   - ルールベース判断機能（アプローチ 2）
   - 判定結果のキャッシュ
   - 判定精度の向上

---

## 参考資料

- [ADR-0005: 3 つの会話の契機](../../architecture/adr/0005-four-conversation-triggers.md)
- [会話の契機の詳細説明](../../requirements/conversation-triggers.md)
- [実装ロードマップ](../roadmap.md)
- [Phase 1 実装完了報告](./phase1.md)
- [Phase 2 実装完了報告](./phase2.md)
- [Phase 3 実装完了報告](./phase3.md)
- [Phase 4 実装完了報告](./phase4.md)
- [Discord.py ドキュメント](https://discordpy.readthedocs.io/)
- [Discord API ドキュメント](https://discord.com/developers/docs/)

---

**作成日**: 2026 年 1 月 15 日
**最終更新日**: 2026 年 1 月 15 日（開発用コマンド追加、判定プロンプト改善）
**対象フェーズ**: Phase 5（会話の契機拡張）
**実装状況**: ⏳ 未実装
**前提条件**: Phase 1, 2, 3, 4 完了済み ✅
**次のフェーズ**: Phase 6（高度な機能）
**バージョン**: 1.0
**見積もり期間**: 約 10-14 日
