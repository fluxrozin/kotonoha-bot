"""メンションハンドラーの詳細テスト."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from kotonoha_bot.bot.handlers.mention import MentionHandler
from kotonoha_bot.db.models import ChatSession, MessageRole
from kotonoha_bot.errors.messages import ErrorMessages
from kotonoha_bot.rate_limit.request_queue import RequestPriority, RequestQueue
from kotonoha_bot.services.ai import TokenInfo


@pytest.fixture
def mock_bot():
    """モックBot."""
    bot = MagicMock()
    bot.user = MagicMock()
    bot.user.id = 123456789
    return bot


@pytest.fixture
def mock_session_manager():
    """モックSessionManager."""
    manager = MagicMock()
    session = MagicMock(spec=ChatSession)
    session.session_key = "mention:987654321"
    session.get_conversation_history = MagicMock(return_value=[])
    session.messages = []
    manager.get_session = AsyncMock(return_value=None)
    manager.create_session = AsyncMock(return_value=session)
    manager.add_message = AsyncMock()
    manager.save_session = AsyncMock()
    return manager


@pytest.fixture
def mock_ai_provider():
    """モックAIProvider."""
    provider = MagicMock()
    token_info = TokenInfo(
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
        model_used="anthropic/claude-3-haiku-20240307",
        latency_ms=100,
    )
    provider.generate_response = AsyncMock(return_value=("テスト応答", token_info))
    provider.get_last_used_model = MagicMock(
        return_value="anthropic/claude-3-haiku-20240307"
    )
    provider.get_rate_limit_usage = MagicMock(return_value=0.5)
    return provider


@pytest.fixture
def mock_request_queue():
    """モックRequestQueue."""
    queue = MagicMock(spec=RequestQueue)

    async def enqueue_side_effect(_priority, func, *args, **kwargs):
        result = await func(*args, **kwargs)
        future = asyncio.Future()
        future.set_result(result)
        return future

    queue.enqueue = AsyncMock(side_effect=enqueue_side_effect)
    return queue


@pytest.fixture
def mock_config():
    """モックConfig."""
    config = MagicMock()
    return config


@pytest.fixture
def mention_handler(
    mock_bot,
    mock_session_manager,
    mock_ai_provider,
    mock_request_queue,
    mock_config,
):
    """MentionHandler インスタンス."""
    return MentionHandler(
        bot=mock_bot,
        session_manager=mock_session_manager,
        ai_provider=mock_ai_provider,
        request_queue=mock_request_queue,
        config=mock_config,
    )


class TestMentionHandlerProcess:
    """_process メソッドのテスト."""

    @pytest.mark.asyncio
    async def test_process_success(self, mention_handler, mock_session_manager):
        """メンション処理が成功する."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.id = 987654321
        mock_message.content = "<@123456789> こんにちは"
        mock_message.mentions = [mention_handler.bot.user]
        mock_message.guild = MagicMock()
        mock_message.guild.id = 111222333
        mock_message.channel = MagicMock()
        mock_message.channel.id = 999888777
        # typing()は非同期コンテキストマネージャーとして動作する
        typing_context = AsyncMock()
        typing_context.__aenter__ = AsyncMock(return_value=None)
        typing_context.__aexit__ = AsyncMock(return_value=None)
        mock_message.channel.typing = MagicMock(return_value=typing_context)
        mock_message.reply = AsyncMock()
        mock_message.channel.send = AsyncMock()

        session = MagicMock(spec=ChatSession)
        session.get_conversation_history = MagicMock(return_value=[])
        mock_session_manager.get_session = AsyncMock(return_value=None)
        mock_session_manager.create_session = AsyncMock(return_value=session)

        await mention_handler._process(mock_message)

        # セッションが作成されたことを確認
        mock_session_manager.create_session.assert_called_once()
        # メッセージが追加されたことを確認
        assert mock_session_manager.add_message.call_count == 2  # USER と ASSISTANT
        # AI応答が生成されたことを確認
        mention_handler.ai_provider.generate_response.assert_called_once()
        # 応答が送信されたことを確認
        mock_message.reply.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_existing_session(
        self, mention_handler, mock_session_manager
    ):
        """既存セッションがある場合."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.id = 987654321
        mock_message.content = "<@123456789> 続きのメッセージ"
        mock_message.mentions = [mention_handler.bot.user]
        mock_message.guild = MagicMock()
        mock_message.guild.id = 111222333
        mock_message.channel = MagicMock()
        mock_message.channel.id = 999888777
        # typing()は非同期コンテキストマネージャーとして動作する
        typing_context = AsyncMock()
        typing_context.__aenter__ = AsyncMock(return_value=None)
        typing_context.__aexit__ = AsyncMock(return_value=None)
        mock_message.channel.typing = MagicMock(return_value=typing_context)
        mock_message.reply = AsyncMock()
        mock_message.channel.send = AsyncMock()

        session = MagicMock(spec=ChatSession)
        session.get_conversation_history = MagicMock(return_value=[])
        mock_session_manager.get_session = AsyncMock(return_value=session)

        await mention_handler._process(mock_message)

        # 新規セッションは作成されないことを確認
        mock_session_manager.create_session.assert_not_called()
        # メッセージが追加されたことを確認
        assert mock_session_manager.add_message.call_count == 2

    @pytest.mark.asyncio
    async def test_process_mention_removed_from_content(
        self, mention_handler, mock_session_manager
    ):
        """メンション部分がメッセージ内容から除去される."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.id = 987654321
        mock_message.content = "<@123456789> こんにちは"
        mock_message.mentions = [mention_handler.bot.user]
        mock_message.guild = MagicMock()
        mock_message.guild.id = 111222333
        mock_message.channel = MagicMock()
        mock_message.channel.id = 999888777
        # typing()は非同期コンテキストマネージャーとして動作する
        typing_context = AsyncMock()
        typing_context.__aenter__ = AsyncMock(return_value=None)
        typing_context.__aexit__ = AsyncMock(return_value=None)
        mock_message.channel.typing = MagicMock(return_value=typing_context)
        mock_message.reply = AsyncMock()
        mock_message.channel.send = AsyncMock()

        session = MagicMock(spec=ChatSession)
        session.get_conversation_history = MagicMock(return_value=[])
        mock_session_manager.get_session = AsyncMock(return_value=None)
        mock_session_manager.create_session = AsyncMock(return_value=session)

        await mention_handler._process(mock_message)

        # メンション部分が除去されたメッセージが追加されることを確認
        add_message_calls = mock_session_manager.add_message.call_args_list
        # USER メッセージの追加を確認（call_args は (args, kwargs) のタプル）
        user_calls = []
        for call in add_message_calls:
            args = call[0] if call[0] else []
            kwargs = call[1] if len(call) > 1 else {}
            # role が USER である呼び出しを探す
            if len(args) >= 2 and args[1] == MessageRole.USER or kwargs.get("role") == MessageRole.USER:
                user_calls.append(call)

        assert len(user_calls) > 0, (
            f"USER メッセージの追加が見つかりません。呼び出し: {add_message_calls}"
        )
        user_message_call = user_calls[0]
        # メンション部分が除去されていることを確認
        args = user_message_call[0] if user_message_call[0] else []
        kwargs = user_message_call[1] if len(user_message_call) > 1 else {}
        content = args[2] if len(args) >= 3 else kwargs.get("content", "")
        assert "<@123456789>" not in content, (
            f"メンション部分が除去されていません: {content}"
        )
        assert "こんにちは" in content or content.strip() == "こんにちは"

    @pytest.mark.asyncio
    async def test_process_discord_error(self, mention_handler, mock_session_manager):
        """Discordエラーが発生した場合."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.id = 987654321
        mock_message.content = "<@123456789> テスト"
        mock_message.mentions = [mention_handler.bot.user]
        mock_message.guild = MagicMock()
        mock_message.guild.id = 111222333
        mock_message.channel = MagicMock()
        mock_message.channel.id = 999888777
        # typing()は非同期コンテキストマネージャーとして動作する
        typing_context = AsyncMock()
        typing_context.__aenter__ = AsyncMock(return_value=None)
        typing_context.__aexit__ = AsyncMock(return_value=None)
        mock_message.channel.typing = MagicMock(return_value=typing_context)
        mock_message.reply = AsyncMock()

        session = MagicMock(spec=ChatSession)
        session.get_conversation_history = MagicMock(return_value=[])
        mock_session_manager.get_session = AsyncMock(return_value=None)
        mock_session_manager.create_session = AsyncMock(return_value=session)

        # Discordエラーを発生させる
        mention_handler.ai_provider.generate_response = AsyncMock(
            side_effect=discord.errors.Forbidden(MagicMock(), "Forbidden")
        )

        await mention_handler._process(mock_message)

        # エラーメッセージが送信されたことを確認
        mock_message.reply.assert_called()

    @pytest.mark.asyncio
    async def test_process_database_error(self, mention_handler, mock_session_manager):
        """データベースエラーが発生した場合."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.id = 987654321
        mock_message.content = "<@123456789> テスト"
        mock_message.mentions = [mention_handler.bot.user]
        mock_message.guild = MagicMock()
        mock_message.guild.id = 111222333
        mock_message.channel = MagicMock()
        mock_message.channel.id = 999888777
        # typing()は非同期コンテキストマネージャーとして動作する
        typing_context = AsyncMock()
        typing_context.__aenter__ = AsyncMock(return_value=None)
        typing_context.__aexit__ = AsyncMock(return_value=None)
        mock_message.channel.typing = MagicMock(return_value=typing_context)
        mock_message.reply = AsyncMock()

        session = MagicMock(spec=ChatSession)
        session.get_conversation_history = MagicMock(return_value=[])
        mock_session_manager.get_session = AsyncMock(return_value=None)
        mock_session_manager.create_session = AsyncMock(return_value=session)

        # データベースエラーを発生させる
        import sqlite3

        mock_session_manager.save_session = AsyncMock(
            side_effect=sqlite3.OperationalError("database is locked")
        )

        await mention_handler._process(mock_message)

        # エラーメッセージが送信されたことを確認
        mock_message.reply.assert_called()

    @pytest.mark.asyncio
    async def test_process_generic_error(self, mention_handler, mock_session_manager):
        """一般的なエラーが発生した場合."""

        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.id = 987654321
        mock_message.content = "<@123456789> テスト"
        mock_message.mentions = [mention_handler.bot.user]
        mock_message.guild = MagicMock()
        mock_message.guild.id = 111222333
        mock_message.channel = MagicMock()
        mock_message.channel.id = 999888777
        # typing()は非同期コンテキストマネージャーとして動作する
        typing_context = AsyncMock()
        typing_context.__aenter__ = AsyncMock(return_value=None)
        typing_context.__aexit__ = AsyncMock(return_value=None)
        mock_message.channel.typing = MagicMock(return_value=typing_context)
        mock_message.reply = AsyncMock()

        session = MagicMock(spec=ChatSession)
        session.get_conversation_history = MagicMock(return_value=[])
        mock_session_manager.get_session = AsyncMock(return_value=None)
        mock_session_manager.create_session = AsyncMock(return_value=session)

        # 一般的なエラーを発生させる
        mention_handler.ai_provider.generate_response = AsyncMock(
            side_effect=ValueError("Unexpected error")
        )

        await mention_handler._process(mock_message)

        # エラーメッセージが送信されたことを確認
        mock_message.reply.assert_called()
        # エラーメッセージの内容を確認
        call_args = mock_message.reply.call_args
        # call_args は tuple または kwargs を含む可能性がある
        error_message = (
            call_args[0][0] if call_args[0] else call_args.kwargs.get("content", "")
        )
        assert (
            ErrorMessages.GENERIC in str(error_message)
            or error_message == ErrorMessages.GENERIC
        )


class TestMentionHandlerHandle:
    """handle メソッドのテスト."""

    @pytest.mark.asyncio
    async def test_handle_bot_message_ignored(self, mention_handler):
        """Bot自身のメッセージは無視される."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.bot = True

        await mention_handler.handle(mock_message)

        # リクエストキューに追加されないことを確認
        mention_handler.request_queue.enqueue.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_not_mentioned(self, mention_handler):
        """Botがメンションされていない場合."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.bot = False
        mock_message.mentions = []

        await mention_handler.handle(mock_message)

        # リクエストキューに追加されないことを確認
        mention_handler.request_queue.enqueue.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_success(self, mention_handler):
        """メンション処理が成功する."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.id = 987654321
        mock_message.author.bot = False
        mock_message.mentions = [mention_handler.bot.user]
        mock_message.channel = MagicMock()
        mock_message.channel.id = 999888777
        # typing()は非同期コンテキストマネージャーとして動作する
        typing_context = AsyncMock()
        typing_context.__aenter__ = AsyncMock(return_value=None)
        typing_context.__aexit__ = AsyncMock(return_value=None)
        mock_message.channel.typing = MagicMock(return_value=typing_context)
        mock_message.guild = None

        await mention_handler.handle(mock_message)

        # リクエストキューに追加されたことを確認
        mention_handler.request_queue.enqueue.assert_called_once()
        call_args = mention_handler.request_queue.enqueue.call_args
        assert call_args[0][0] == RequestPriority.MENTION

    @pytest.mark.asyncio
    async def test_handle_queue_error_fallback(self, mention_handler):
        """キューエラー時のフォールバック処理."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.bot = False
        mock_message.mentions = [mention_handler.bot.user]

        # キューエラーを発生させる
        mention_handler.request_queue.enqueue = AsyncMock(
            side_effect=RuntimeError("Queue is full")
        )

        # _process をモック
        mention_handler._process = AsyncMock()

        await mention_handler.handle(mock_message)

        # フォールバック処理が実行されたことを確認
        mention_handler._process.assert_called_once_with(mock_message)
