"""スレッドハンドラーの詳細テスト."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from kotonoha_bot.bot.handlers.mention import MentionHandler
from kotonoha_bot.bot.handlers.thread import ThreadHandler
from kotonoha_bot.db.models import ChatSession
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
    session.session_key = "thread:123"
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
def mock_router():
    """モックMessageRouter."""
    router = MagicMock()
    router.register_bot_thread = MagicMock()
    return router


@pytest.fixture
def mock_mention_handler():
    """モックMentionHandler."""
    handler = MagicMock(spec=MentionHandler)
    handler.handle = AsyncMock()
    return handler


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
    config.THREAD_AUTO_ARCHIVE_DURATION = None
    config.EAVESDROP_BUFFER_SIZE = 20
    config.EAVESDROP_MIN_MESSAGES = 3
    return config


@pytest.fixture
def thread_handler(
    mock_bot,
    mock_session_manager,
    mock_ai_provider,
    mock_router,
    mock_request_queue,
    mock_mention_handler,
    mock_config,
):
    """ThreadHandler インスタンス."""
    return ThreadHandler(
        bot=mock_bot,
        session_manager=mock_session_manager,
        ai_provider=mock_ai_provider,
        router=mock_router,
        request_queue=mock_request_queue,
        mention_handler=mock_mention_handler,
        config=mock_config,
    )


class TestThreadHandlerProcessMessage:
    """_process_message メソッドのテスト."""

    @pytest.mark.asyncio
    async def test_process_message_existing_thread(
        self, thread_handler, mock_session_manager
    ):
        """既存スレッド内でのメッセージ処理."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.id = 987654321
        mock_message.content = "テストメッセージ"

        mock_thread = MagicMock(spec=discord.Thread)
        mock_thread.id = 444555666
        mock_thread.guild = MagicMock()
        mock_thread.guild.id = 111222333
        mock_thread.parent_id = 999888777
        # typing()は非同期コンテキストマネージャーとして動作する
        typing_context = AsyncMock()
        typing_context.__aenter__ = AsyncMock(return_value=None)
        typing_context.__aexit__ = AsyncMock(return_value=None)
        mock_thread.typing = MagicMock(return_value=typing_context)
        mock_thread.send = AsyncMock()
        mock_message.channel = mock_thread
        mock_message.reply = AsyncMock()

        # セッションをモック
        session = MagicMock(spec=ChatSession)
        session.get_conversation_history = MagicMock(return_value=[])
        mock_session_manager.get_session = AsyncMock(return_value=session)

        await thread_handler._process_message(mock_message)

        # セッションにメッセージが追加されたことを確認
        mock_session_manager.add_message.assert_called()
        # AI応答が生成されたことを確認
        thread_handler.ai_provider.generate_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_message_new_session(
        self, thread_handler, mock_session_manager
    ):
        """既存スレッド内で新規セッションを作成."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.id = 987654321
        mock_message.content = "テストメッセージ"

        mock_thread = MagicMock(spec=discord.Thread)
        mock_thread.id = 444555666
        mock_thread.guild = MagicMock()
        mock_thread.guild.id = 111222333
        mock_thread.parent_id = 999888777
        # typing()は非同期コンテキストマネージャーとして動作する
        typing_context = AsyncMock()
        typing_context.__aenter__ = AsyncMock(return_value=None)
        typing_context.__aexit__ = AsyncMock(return_value=None)
        mock_thread.typing = MagicMock(return_value=typing_context)
        mock_thread.send = AsyncMock()
        mock_message.channel = mock_thread
        mock_message.reply = AsyncMock()

        # セッションが見つからない場合
        mock_session_manager.get_session = AsyncMock(return_value=None)
        session = MagicMock(spec=ChatSession)
        session.get_conversation_history = MagicMock(return_value=[])
        mock_session_manager.create_session = AsyncMock(return_value=session)

        await thread_handler._process_message(mock_message)

        # 新規セッションが作成されたことを確認
        mock_session_manager.create_session.assert_called_once()
        # セッションにメッセージが追加されたことを確認
        mock_session_manager.add_message.assert_called()

    @pytest.mark.asyncio
    async def test_process_message_not_thread(self, thread_handler):
        """Thread型でないチャンネルの場合."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.channel = MagicMock(spec=discord.TextChannel)

        await thread_handler._process_message(mock_message)

        # 処理が早期リターンされることを確認
        thread_handler.session_manager.get_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_message_discord_error(
        self, thread_handler, mock_session_manager
    ):
        """Discordエラーが発生した場合."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.id = 987654321
        mock_message.content = "テストメッセージ"

        mock_thread = MagicMock(spec=discord.Thread)
        mock_thread.id = 444555666
        mock_thread.guild = MagicMock()
        mock_thread.guild.id = 111222333
        mock_thread.parent_id = 999888777
        # typing()は非同期コンテキストマネージャーとして動作する
        typing_context = AsyncMock()
        typing_context.__aenter__ = AsyncMock(return_value=None)
        typing_context.__aexit__ = AsyncMock(return_value=None)
        mock_thread.typing = MagicMock(return_value=typing_context)
        mock_message.channel = mock_thread
        mock_message.reply = AsyncMock()

        session = MagicMock(spec=ChatSession)
        session.get_conversation_history = MagicMock(return_value=[])
        mock_session_manager.get_session = AsyncMock(return_value=session)

        # Discordエラーを発生させる
        thread_handler.ai_provider.generate_response = AsyncMock(
            side_effect=discord.errors.Forbidden(MagicMock(), "Forbidden")
        )

        await thread_handler._process_message(mock_message)

        # エラーメッセージが送信されたことを確認
        mock_message.reply.assert_called()

    @pytest.mark.asyncio
    async def test_process_message_database_error(
        self, thread_handler, mock_session_manager
    ):
        """データベースエラーが発生した場合."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.id = 987654321
        mock_message.content = "テストメッセージ"

        mock_thread = MagicMock(spec=discord.Thread)
        mock_thread.id = 444555666
        mock_thread.guild = MagicMock()
        mock_thread.guild.id = 111222333
        mock_thread.parent_id = 999888777
        # typing()は非同期コンテキストマネージャーとして動作する
        typing_context = AsyncMock()
        typing_context.__aenter__ = AsyncMock(return_value=None)
        typing_context.__aexit__ = AsyncMock(return_value=None)
        mock_thread.typing = MagicMock(return_value=typing_context)
        mock_message.channel = mock_thread
        mock_message.reply = AsyncMock()

        session = MagicMock(spec=ChatSession)
        session.get_conversation_history = MagicMock(return_value=[])
        mock_session_manager.get_session = AsyncMock(return_value=session)

        # データベースエラーを発生させる
        import sqlite3

        thread_handler.session_manager.save_session = AsyncMock(
            side_effect=sqlite3.OperationalError("database is locked")
        )

        await thread_handler._process_message(mock_message)

        # エラーメッセージが送信されたことを確認
        mock_message.reply.assert_called()


class TestThreadHandlerCreateThreadAndRespond:
    """_create_thread_and_respond メソッドのテスト."""

    @pytest.mark.asyncio
    async def test_create_thread_and_respond_success(
        self, thread_handler, mock_session_manager
    ):
        """スレッド作成と応答が成功する."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.id = 987654321
        mock_message.content = "<@123456789> こんにちは"
        mock_message.mentions = [thread_handler.bot.user]
        mock_message.id = 111222333
        mock_message.thread = None
        mock_message.reply = AsyncMock()
        mock_message.channel = MagicMock()
        mock_message.channel.id = 999888777
        mock_message.channel.fetch_message = AsyncMock(return_value=mock_message)

        mock_thread = MagicMock(spec=discord.Thread)
        mock_thread.id = 444555666
        mock_thread.guild = MagicMock()
        mock_thread.guild.id = 111222333
        # typing()は非同期コンテキストマネージャーとして動作する
        typing_context = AsyncMock()
        typing_context.__aenter__ = AsyncMock(return_value=None)
        typing_context.__aexit__ = AsyncMock(return_value=None)
        mock_thread.typing = MagicMock(return_value=typing_context)
        mock_thread.send = AsyncMock()
        _f = asyncio.Future()
        _f.set_result(mock_thread)
        mock_message.create_thread = MagicMock(return_value=_f)

        session = MagicMock(spec=ChatSession)
        session.get_conversation_history = MagicMock(return_value=[])
        mock_session_manager.get_session = AsyncMock(return_value=None)
        mock_session_manager.create_session = AsyncMock(return_value=session)

        result = await thread_handler._create_thread_and_respond(mock_message)

        assert result is True
        mock_message.create_thread.assert_called_once()
        thread_handler.router.register_bot_thread.assert_called_once_with(
            mock_thread.id
        )
        mock_session_manager.create_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_thread_and_respond_thread_already_exists(
        self, thread_handler, mock_session_manager
    ):
        """スレッドが既に存在する場合."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.id = 987654321
        mock_message.content = "<@123456789> こんにちは"
        mock_message.mentions = [thread_handler.bot.user]
        mock_message.id = 111222333

        mock_thread = MagicMock(spec=discord.Thread)
        mock_thread.id = 444555666
        mock_thread.guild = MagicMock()
        mock_thread.guild.id = 111222333
        # typing()は非同期コンテキストマネージャーとして動作する
        typing_context = AsyncMock()
        typing_context.__aenter__ = AsyncMock(return_value=None)
        typing_context.__aexit__ = AsyncMock(return_value=None)
        mock_thread.typing = MagicMock(return_value=typing_context)
        mock_thread.send = AsyncMock()
        mock_message.thread = mock_thread
        mock_message.reply = AsyncMock()

        session = MagicMock(spec=ChatSession)
        session.get_conversation_history = MagicMock(return_value=[])
        mock_session_manager.get_session = AsyncMock(return_value=None)
        mock_session_manager.create_session = AsyncMock(return_value=session)

        result = await thread_handler._create_thread_and_respond(mock_message)

        assert result is True
        # create_thread は呼ばれない（既存スレッドを使用）
        assert (
            not hasattr(mock_message, "create_thread")
            or not mock_message.create_thread.called
        )

    @pytest.mark.asyncio
    async def test_create_thread_and_respond_forbidden_error(
        self, thread_handler, mock_mention_handler
    ):
        """スレッド作成権限がない場合（Forbiddenエラー）."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.id = 987654321
        mock_message.content = "<@123456789> こんにちは"
        mock_message.mentions = [thread_handler.bot.user]
        mock_message.thread = None
        mock_message.reply = AsyncMock()

        mock_message.create_thread = AsyncMock(
            side_effect=discord.errors.Forbidden(MagicMock(), "Forbidden")
        )

        result = await thread_handler._create_thread_and_respond(mock_message)

        # メンション応答型にフォールバックしたので成功として扱う
        assert result is True
        mock_mention_handler.handle.assert_called_once_with(mock_message)

    @pytest.mark.asyncio
    async def test_create_thread_and_respond_http_exception_160004(
        self, thread_handler, mock_session_manager
    ):
        """HTTPException 160004（スレッドが既に作成されている）."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.id = 987654321
        mock_message.content = "<@123456789> こんにちは"
        mock_message.mentions = [thread_handler.bot.user]
        mock_message.id = 111222333
        mock_message.thread = None
        mock_message.reply = AsyncMock()
        mock_message.channel = MagicMock()
        mock_message.channel.id = 999888777

        mock_response = MagicMock()
        mock_response.status = 400
        http_exception = discord.errors.HTTPException(
            mock_response, "Thread already exists"
        )
        http_exception.code = 160004

        mock_message.create_thread = AsyncMock(side_effect=http_exception)

        # 再取得したメッセージにスレッドが存在する場合
        mock_thread = MagicMock(spec=discord.Thread)
        mock_thread.id = 444555666
        mock_thread.guild = MagicMock()
        mock_thread.guild.id = 111222333
        # typing()は非同期コンテキストマネージャーとして動作する
        typing_context = AsyncMock()
        typing_context.__aenter__ = AsyncMock(return_value=None)
        typing_context.__aexit__ = AsyncMock(return_value=None)
        mock_thread.typing = MagicMock(return_value=typing_context)
        mock_thread.send = AsyncMock()

        updated_message = MagicMock()
        updated_message.thread = mock_thread
        mock_message.channel.fetch_message = AsyncMock(return_value=updated_message)

        session = MagicMock(spec=ChatSession)
        session.get_conversation_history = MagicMock(return_value=[])
        mock_session_manager.get_session = AsyncMock(return_value=None)
        mock_session_manager.create_session = AsyncMock(return_value=session)

        result = await thread_handler._create_thread_and_respond(mock_message)

        assert result is True
        mock_session_manager.create_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_thread_and_respond_thread_name_generation(
        self, thread_handler, mock_session_manager
    ):
        """スレッド名の生成が正しく動作する."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.id = 987654321
        mock_message.content = "<@123456789> これはテストメッセージです。"
        mock_message.mentions = [thread_handler.bot.user]
        mock_message.id = 111222333
        mock_message.thread = None
        mock_message.reply = AsyncMock()
        mock_message.channel = MagicMock()
        mock_message.channel.id = 999888777
        mock_message.channel.fetch_message = AsyncMock(return_value=mock_message)

        mock_thread = MagicMock(spec=discord.Thread)
        mock_thread.id = 444555666
        mock_thread.guild = MagicMock()
        mock_thread.guild.id = 111222333
        # typing()は非同期コンテキストマネージャーとして動作する
        typing_context = AsyncMock()
        typing_context.__aenter__ = AsyncMock(return_value=None)
        typing_context.__aexit__ = AsyncMock(return_value=None)
        mock_thread.typing = MagicMock(return_value=typing_context)
        mock_thread.send = AsyncMock()
        mock_message.create_thread = AsyncMock(return_value=mock_thread)

        session = MagicMock(spec=ChatSession)
        session.get_conversation_history = MagicMock(return_value=[])
        mock_session_manager.get_session = AsyncMock(return_value=None)
        mock_session_manager.create_session = AsyncMock(return_value=session)

        result = await thread_handler._create_thread_and_respond(mock_message)

        assert result is True
        # スレッド名が正しく生成されていることを確認
        call_args = mock_message.create_thread.call_args
        assert "name" in call_args.kwargs
        thread_name = call_args.kwargs["name"]
        assert "テストメッセージ" in thread_name or len(thread_name) > 0

    @pytest.mark.asyncio
    async def test_create_thread_and_respond_empty_message(
        self, thread_handler, mock_session_manager
    ):
        """メンションのみでメッセージが空の場合."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.id = 987654321
        mock_message.content = "<@123456789>"
        mock_message.mentions = [thread_handler.bot.user]
        mock_message.id = 111222333
        mock_message.thread = None
        mock_message.reply = AsyncMock()
        mock_message.channel = MagicMock()
        mock_message.channel.id = 999888777
        mock_message.channel.fetch_message = AsyncMock(return_value=mock_message)

        mock_thread = MagicMock(spec=discord.Thread)
        mock_thread.id = 444555666
        mock_thread.guild = MagicMock()
        mock_thread.guild.id = 111222333
        # typing()は非同期コンテキストマネージャーとして動作する
        typing_context = AsyncMock()
        typing_context.__aenter__ = AsyncMock(return_value=None)
        typing_context.__aexit__ = AsyncMock(return_value=None)
        mock_thread.typing = MagicMock(return_value=typing_context)
        mock_thread.send = AsyncMock()
        mock_message.create_thread = AsyncMock(return_value=mock_thread)

        session = MagicMock(spec=ChatSession)
        session.get_conversation_history = MagicMock(return_value=[])
        mock_session_manager.get_session = AsyncMock(return_value=None)
        mock_session_manager.create_session = AsyncMock(return_value=session)

        result = await thread_handler._create_thread_and_respond(mock_message)

        assert result is True
        # デフォルト名「会話」が使用されることを確認
        call_args = mock_message.create_thread.call_args
        assert call_args.kwargs["name"] == "会話"

    @pytest.mark.asyncio
    async def test_create_thread_and_respond_with_auto_archive_duration(
        self, thread_handler, mock_session_manager, mock_config
    ):
        """auto_archive_duration が設定されている場合."""
        mock_config.THREAD_AUTO_ARCHIVE_DURATION = 1440

        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.id = 987654321
        mock_message.content = "<@123456789> テスト"
        mock_message.mentions = [thread_handler.bot.user]
        mock_message.id = 111222333
        mock_message.thread = None
        mock_message.reply = AsyncMock()
        mock_message.channel = MagicMock()
        mock_message.channel.id = 999888777
        mock_message.channel.fetch_message = AsyncMock(return_value=mock_message)

        mock_thread = MagicMock(spec=discord.Thread)
        mock_thread.id = 444555666
        mock_thread.guild = MagicMock()
        mock_thread.guild.id = 111222333
        # typing()は非同期コンテキストマネージャーとして動作する
        typing_context = AsyncMock()
        typing_context.__aenter__ = AsyncMock(return_value=None)
        typing_context.__aexit__ = AsyncMock(return_value=None)
        mock_thread.typing = MagicMock(return_value=typing_context)
        mock_thread.send = AsyncMock()
        mock_message.create_thread = AsyncMock(return_value=mock_thread)

        session = MagicMock(spec=ChatSession)
        session.get_conversation_history = MagicMock(return_value=[])
        mock_session_manager.get_session = AsyncMock(return_value=None)
        mock_session_manager.create_session = AsyncMock(return_value=session)

        result = await thread_handler._create_thread_and_respond(mock_message)

        assert result is True
        # auto_archive_duration が指定されていることを確認
        call_args = mock_message.create_thread.call_args
        assert "auto_archive_duration" in call_args.kwargs
        assert call_args.kwargs["auto_archive_duration"] == 1440


class TestThreadHandlerHandle:
    """handle メソッドのテスト."""

    @pytest.mark.asyncio
    async def test_handle_bot_message_ignored(self, thread_handler):
        """Bot自身のメッセージは無視される."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.bot = True

        await thread_handler.handle(mock_message)

        # リクエストキューに追加されないことを確認
        thread_handler.request_queue.enqueue.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_existing_thread(self, thread_handler):
        """既存スレッド内でのメッセージ."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.bot = False
        mock_thread = MagicMock(spec=discord.Thread)
        mock_message.channel = mock_thread

        await thread_handler.handle(mock_message)

        # _process_message が呼ばれることを確認
        thread_handler.request_queue.enqueue.assert_called_once()
        call_args = thread_handler.request_queue.enqueue.call_args
        assert call_args[0][0] == RequestPriority.THREAD

    @pytest.mark.asyncio
    async def test_handle_mention_creates_thread(self, thread_handler):
        """メンション時に新規スレッドを作成."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.bot = False
        mock_message.mentions = [thread_handler.bot.user]
        mock_message.channel = MagicMock(spec=discord.TextChannel)

        await thread_handler.handle(mock_message)

        # _process_creation が呼ばれることを確認
        thread_handler.request_queue.enqueue.assert_called_once()
        call_args = thread_handler.request_queue.enqueue.call_args
        assert call_args[0][0] == RequestPriority.THREAD

    @pytest.mark.asyncio
    async def test_handle_no_mention_no_thread(self, thread_handler):
        """メンションされていない場合、処理しない."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.bot = False
        mock_message.mentions = []
        mock_message.channel = MagicMock(spec=discord.TextChannel)

        await thread_handler.handle(mock_message)

        # リクエストキューに追加されないことを確認
        thread_handler.request_queue.enqueue.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_queue_error_fallback(self, thread_handler):
        """キューエラー時のフォールバック処理."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.bot = False
        mock_thread = MagicMock(spec=discord.Thread)
        mock_message.channel = mock_thread

        # キューエラーを発生させる
        thread_handler.request_queue.enqueue = AsyncMock(
            side_effect=RuntimeError("Queue is full")
        )

        # _process_message をモック
        thread_handler._process_message = AsyncMock()

        await thread_handler.handle(mock_message)

        # フォールバック処理が実行されたことを確認
        thread_handler._process_message.assert_called_once_with(mock_message)
